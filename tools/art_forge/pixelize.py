"""Turns a generated illustration into game-ready pixel art.

Image models paint at ~1024 px and only imitate pixel art: block edges are
soft, the "pixel" grid is uneven and colours drift off-palette. This rebuilds
a clean sprite:

1. Foreground mask: the image's own alpha when it has one (models that can
   return transparent backgrounds), otherwise the flat background colour is
   keyed out by flood-filling from the border (prompts ask for flat magenta).
2. Crop to the subject.
3. Resample to the target size. Each target cell is sampled away from its
   edges and every sample is snapped to the palette; the cell takes the most
   common colour, so boundaries never blend into muddy in-between pixels. The
   cell grid is shifted to line up with the source's own pixel grid.
4. Colours come only from the master palette (tools/common/palette.py),
   optionally limited to a few ramps so a character keeps its own colours.
5. Binary alpha, stray single pixels and pinholes removed, an optional 1px
   selective outline (darkest shade of the neighbouring ramp, never pure
   black) and the 1px transparent border the sheet contract requires.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import palette as P  # noqa: E402

# palette.nearest's perceptual weights for R, G, B
WEIGHTS = np.array([3.0, 4.0, 2.0], dtype=np.float32)
MASK_MAX_SIDE = 512


def load_rgba(path: str | Path) -> np.ndarray:
    return np.array(Image.open(path).convert("RGBA"), dtype=np.uint8)


def palette_for(ramps: list[str] | None = None) -> tuple[np.ndarray, list[str]]:
    """Palette colours (K, 3) and, for each, the ramp it belongs to."""
    names = ramps if ramps else list(P.RAMPS.keys())
    colors: list[tuple[int, int, int]] = []
    owners: list[str] = []
    for name in names:
        if name not in P.RAMPS:
            raise ValueError(f"unknown palette ramp '{name}'")
        for c in P.RAMPS[name]:
            colors.append(c[:3])
            owners.append(name)
    return np.array(colors, dtype=np.float32), owners


def _shift(m: np.ndarray, dy: int, dx: int) -> np.ndarray:
    out = np.zeros_like(m)
    h, w = m.shape
    out[max(dy, 0):h + min(dy, 0), max(dx, 0):w + min(dx, 0)] = m[max(-dy, 0):h + min(-dy, 0), max(-dx, 0):w + min(-dx, 0)]
    return out


def flood_from_border(candidate: np.ndarray) -> np.ndarray:
    """Cells of `candidate` 4-connected to the image border."""
    reach = np.zeros_like(candidate)
    reach[0, :] = candidate[0, :]
    reach[-1, :] = candidate[-1, :]
    reach[:, 0] |= candidate[:, 0]
    reach[:, -1] |= candidate[:, -1]
    while True:
        grown = reach.copy()
        for _ in range(8):
            grown = (grown | _shift(grown, 1, 0) | _shift(grown, -1, 0) | _shift(grown, 0, 1) | _shift(grown, 0, -1)) & candidate
        if np.array_equal(grown, reach):
            return reach
        reach = grown


def foreground_mask(img: np.ndarray, tolerance: float = 48.0) -> np.ndarray:
    return _foreground(img, tolerance)[0]


def _foreground(img: np.ndarray, tolerance: float) -> tuple[np.ndarray, np.ndarray | None]:
    """The subject mask, and the keyed background colour (None when the image had real alpha)."""
    alpha = img[..., 3]
    if (alpha < 128).mean() > 0.01:
        return alpha >= 128, None
    h, w = alpha.shape
    step = max(1, int(np.ceil(max(h, w) / MASK_MAX_SIDE)))
    rgb = img[::step, ::step, :3].astype(np.float32)
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    background_color = np.median(border, axis=0)
    distance = np.sqrt(((rgb - background_color) ** 2).sum(-1))
    background = flood_from_border(distance < tolerance)
    small = ~background
    return np.repeat(np.repeat(small, step, axis=0), step, axis=1)[:h, :w], background_color


def crop_to_mask(img: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        raise ValueError("no subject found: the whole image looks like background")
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    return img[y0:y1, x0:x1], mask[y0:y1, x0:x1]


def _edge_signal(img: np.ndarray, mask: np.ndarray, axis: int) -> np.ndarray:
    rgb = img[..., :3].astype(np.int32)
    diff = np.abs(np.diff(rgb, axis=axis)).sum(-1)
    inside = mask[:, 1:] & mask[:, :-1] if axis == 1 else mask[1:, :] & mask[:-1, :]
    edges = (diff > 36) & inside
    return edges.sum(axis=0 if axis == 1 else 1).astype(np.float64)


def _period(signal: np.ndarray, lo: int = 3, hi: int = 96) -> float | None:
    s = signal - signal.mean()
    if not np.any(s):
        return None
    ac = np.correlate(s, s, mode="full")[len(s) - 1:]
    hi = min(hi, len(ac) // 3)
    if hi <= lo + 1:
        return None
    window = ac[lo:hi]
    peak = window.max()
    if peak <= 0:
        return None
    for i in range(1, len(window) - 1):
        if window[i] >= window[i - 1] and window[i] >= window[i + 1] and window[i] >= 0.6 * peak:
            return float(lo + i)
    return None


def estimate_cell_size(img: np.ndarray, mask: np.ndarray) -> float | None:
    """Size in source pixels of the image's own 'pixels', when it imitates pixel art."""
    estimates = [p for p in (_period(_edge_signal(img, mask, 1)), _period(_edge_signal(img, mask, 0))) if p]
    return float(np.mean(estimates)) if estimates else None


def _best_phase(signal: np.ndarray, cell: float) -> float:
    """Grid offset in [-cell/2, cell/2) that puts cell boundaries on the source's edges."""
    best, best_score = 0.0, -1.0
    n = len(signal)
    for k in range(16):
        offset = (k / 16.0 - 0.5) * cell
        positions = np.arange(offset, n, cell)
        idx = np.clip(np.round(positions).astype(int), 0, n - 1)
        score = signal[idx].sum() + 0.5 * (signal[np.clip(idx - 1, 0, n - 1)].sum() + signal[np.clip(idx + 1, 0, n - 1)].sum())
        if score > best_score:
            best, best_score = offset, score
    return best


def _nearest_index(colors: np.ndarray, pal: np.ndarray) -> np.ndarray:
    """Index of the nearest palette colour for each row of `colors` (N, 3)."""
    out = np.empty(len(colors), dtype=np.int32)
    for start in range(0, len(colors), 8192):
        chunk = colors[start:start + 8192, None, :] - pal[None, :, :]
        out[start:start + 8192] = ((chunk ** 2) * WEIGHTS).sum(-1).argmin(1)
    return out


def resample(img: np.ndarray, mask: np.ndarray, out_w: int, out_h: int, pal: np.ndarray, phase: tuple[float, float] = (0.0, 0.0), samples: int = 5, background: np.ndarray | None = None, tolerance: float = 48.0) -> tuple[np.ndarray, np.ndarray]:
    """Palette indices (out_h, out_w) and coverage (out_h, out_w) of each target cell.

    With a keyed `background` colour, samples tinted toward it (anti-aliased
    edges where the subject blends into the backdrop) barely vote, so the
    backdrop never bleeds into edge pixels as a colour of its own.
    """
    h, w = mask.shape
    cw, ch = w / out_w, h / out_h
    frac = np.linspace(0.2, 0.8, samples)
    xs = np.clip(np.floor(phase[0] + (np.arange(out_w)[:, None] + frac[None, :]) * cw).astype(int), 0, w - 1)
    ys = np.clip(np.floor(phase[1] + (np.arange(out_h)[:, None] + frac[None, :]) * ch).astype(int), 0, h - 1)
    yy = ys[:, None, :, None]
    xx = xs[None, :, None, :]
    rgb = img[..., :3][yy, xx].astype(np.float32)  # (out_h, out_w, s, s, 3)
    inside = mask[yy, xx]  # (out_h, out_w, s, s)
    coverage = inside.mean(axis=(2, 3))
    idx = _nearest_index(rgb.reshape(-1, 3), pal).reshape(out_h, out_w, samples * samples)
    weight = inside.reshape(out_h, out_w, samples * samples).astype(np.float32)
    if background is not None:
        spill = np.sqrt(((rgb - background) ** 2).sum(-1)) < tolerance * 2.5
        weight *= np.where(spill.reshape(out_h, out_w, samples * samples), 0.02, 1.0).astype(np.float32)
    counts = np.zeros((out_h * out_w, len(pal)), dtype=np.float32)
    cell = np.repeat(np.arange(out_h * out_w), samples * samples)
    np.add.at(counts, (cell, idx.reshape(-1)), weight.reshape(-1))
    return counts.argmax(1).reshape(out_h, out_w), coverage


def _clean(indices: np.ndarray, opaque: np.ndarray) -> np.ndarray:
    """Drops opaque pixels with no opaque 4-neighbour and fills 1px transparent pinholes."""
    n = _shift(opaque, 1, 0).astype(int) + _shift(opaque, -1, 0) + _shift(opaque, 0, 1) + _shift(opaque, 0, -1)
    opaque = opaque & (n > 0)
    holes = ~opaque & (n == 4)
    for y, x in zip(*np.nonzero(holes)):
        neighbours = [indices[y + dy, x + dx] for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        indices[y, x] = max(set(neighbours), key=neighbours.count)
        opaque[y, x] = True
    return opaque


def _outline(indices: np.ndarray, opaque: np.ndarray, pal: np.ndarray, owners: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Adds a 1px outline outside the silhouette: the darkest shade of the darkest neighbour's ramp."""
    rgb = pal[indices]
    luminance = (rgb * np.array([0.3, 0.59, 0.11], dtype=np.float32)).sum(-1)
    lookup = {tuple(c): i for i, c in enumerate(pal.astype(int).tolist())}
    outline = np.zeros_like(opaque)
    out_idx = indices.copy()
    h, w = opaque.shape
    for y, x in zip(*np.nonzero(~opaque)):
        best = None
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            yy, xx = y + dy, x + dx
            if 0 <= yy < h and 0 <= xx < w and opaque[yy, xx] and (best is None or luminance[yy, xx] < luminance[best]):
                best = (yy, xx)
        if best is not None:
            darkest = P.darkest(owners[indices[best]])[:3]
            out_idx[y, x] = lookup.get(tuple(darkest), indices[best])
            outline[y, x] = True
    return out_idx, opaque | outline, outline


def to_image(indices: np.ndarray, opaque: np.ndarray, pal: np.ndarray, border: int = 1) -> Image.Image:
    h, w = opaque.shape
    out = np.zeros((h + 2 * border, w + 2 * border, 4), dtype=np.uint8)
    out[border:border + h, border:border + w, :3] = pal[indices].astype(np.uint8)
    out[border:border + h, border:border + w, 3] = np.where(opaque, 255, 0)
    out[out[..., 3] == 0] = 0
    return Image.fromarray(out, "RGBA")


def pixelize(
    source: str | Path | np.ndarray,
    height: int | None = None,
    width: int | None = None,
    ramps: list[str] | None = None,
    outline: bool = False,
    tolerance: float = 48.0,
    align_grid: bool = True,
) -> Image.Image:
    """Clean pixel art from a generated image.

    height/width set the subject's size in game pixels (the outline, when
    requested, is included in it); with neither, the image's own pixel grid
    is used. The result has a 1px transparent border on every side.
    """
    img = source if isinstance(source, np.ndarray) else load_rgba(source)
    mask, background = _foreground(img, tolerance)
    img, mask = crop_to_mask(img, mask)
    h, w = mask.shape
    pad = 2 if outline else 0
    if height is None and width is None:
        cell = estimate_cell_size(img, mask)
        if cell is None:
            raise ValueError("could not detect a pixel grid; pass height or width")
        out_h, out_w = max(1, round(h / cell)), max(1, round(w / cell))
    else:
        scale = min((height - pad) / h if height else np.inf, (width - pad) / w if width else np.inf)
        out_h, out_w = max(1, round(h * scale)), max(1, round(w * scale))
    pal, owners = palette_for(ramps)
    phase = (0.0, 0.0)
    if align_grid:
        phase = (_best_phase(_edge_signal(img, mask, 1), w / out_w), _best_phase(_edge_signal(img, mask, 0), h / out_h))
    indices, coverage = resample(img, mask, out_w, out_h, pal, phase, background=background, tolerance=tolerance)
    opaque = _clean(indices, coverage >= 0.5)
    if outline:
        indices = np.pad(indices, 1)
        opaque = np.pad(opaque, 1)
        indices, opaque, _ = _outline(indices, opaque, pal, owners)
    return to_image(indices, opaque, pal)


def fit_into_frame(sprite: Image.Image, frame_w: int, frame_h: int, pivot: tuple[int, int]) -> Image.Image:
    """Places a sprite in a frame with its lowest opaque row on the pivot row, centred on the pivot column."""
    box = sprite.getbbox()
    if box is None:
        raise ValueError("empty sprite")
    content = sprite.crop(box)
    cw, ch = content.size
    x = pivot[0] - cw // 2
    y = pivot[1] - ch + 1
    if x < 1 or y < 1 or x + cw > frame_w - 1 or y + ch > frame_h - 1:
        raise ValueError(f"a {cw}x{ch} sprite does not fit a {frame_w}x{frame_h} frame with pivot {pivot} and a 1px border")
    frame = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
    frame.paste(content, (x, y))
    return frame
