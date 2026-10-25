"""Expression frames that differ from the locked neutral only where the face changes.

An expression generated with the approved neutral as a reference keeps the
design, but the model redraws the whole picture: hair strands, folds and
outlines wander a little, so a portrait sheet "jumps" whenever the dialogue
switches expression. `composite` registers the expression painting to the
neutral (uniform scale + shift, found by brute force on a small copy) and
blends only the face regions into the neutral painting, before pixelizing.
Everywhere else the pixelized frames come out identical.

Only pixels that are subject in both paintings are blended, so the backdrop
or a stray strand from one painting is never pulled across the other. The
expression is also colour-matched to the base over the blended region (mean
and spread per channel): models often repaint a face a little warmer or
cooler, which would otherwise snap to other palette shades (orange blotches
on skin) and show as a seam.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import pixelize as PX

WORK = 256  # registration resolution


def _small(img: np.ndarray, side: int) -> np.ndarray:
    return np.array(Image.fromarray(img).resize((side, side), Image.BILINEAR), dtype=np.float32)


def warp(img: np.ndarray, scale: float, dx: float, dy: float, size: tuple[int, int], fill: np.ndarray) -> np.ndarray:
    """out(x, y) = img((x - cx - dx) / scale + cx, (y - cy - dy) / scale + cy): scaled about the centre, then shifted."""
    h, w = img.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    ys, xs = np.mgrid[0:size[0], 0:size[1]].astype(np.float32)
    ix = np.round((xs - cx - dx) / scale + cx).astype(int)
    iy = np.round((ys - cy - dy) / scale + cy).astype(int)
    ok = (ix >= 0) & (ix < w) & (iy >= 0) & (iy < h)
    out = np.empty(size + img.shape[2:], dtype=img.dtype)
    out[:] = fill
    out[ok] = img[iy[ok], ix[ok]]
    return out


def register(base: np.ndarray, other: np.ndarray, base_mask: np.ndarray, other_mask: np.ndarray, work: int = WORK) -> tuple[float, float, float]:
    """(scale, dx, dy) in base pixels that best maps `other` onto `base` (RGB arrays of the same size).

    Searches scale 0.88-1.12 and a shift of up to 12/`work` of the width, then refines.
    """
    h, w = base.shape[:2]
    f = w / work
    b = _small(base[..., :3], work)
    o = _small(other[..., :3], work)
    bm = _small((base_mask * 255).astype(np.uint8), work) > 127
    om = _small((other_mask * 255).astype(np.uint8), work) > 127
    grey = np.array([128, 128, 128], np.float32)

    def score(s: float, dx: float, dy: float) -> float:
        wo = warp(o, s, dx, dy, (work, work), grey)
        wm = warp(om, s, dx, dy, (work, work), np.array(False))
        both = bm | wm
        return float(np.abs(wo - b).sum(-1)[both].mean() + 255.0 * (bm ^ wm).mean())

    best = min(((score(s, dx, dy), s, dx, dy) for s in np.arange(0.88, 1.121, 0.02) for dy in range(-12, 13, 2) for dx in range(-12, 13, 2)))
    _, s0, x0, y0 = best
    best = min(((score(s, dx, dy), s, dx, dy) for s in np.arange(s0 - 0.02, s0 + 0.021, 0.005) for dy in np.arange(y0 - 2, y0 + 2.1, 0.5) for dx in np.arange(x0 - 2, x0 + 2.1, 0.5)))
    _, s, dx, dy = best
    return float(s), float(dx * f), float(dy * f)


def match_colour(src: np.ndarray, ref: np.ndarray, where: np.ndarray) -> tuple[np.ndarray, list[float]]:
    """`src` (RGB float) shifted and scaled per channel so that its colours under `where` match `ref`'s."""
    out = src.copy()
    gains = []
    for c in range(3):
        s, r = src[..., c][where], ref[..., c][where]
        gain = float(np.clip(r.std() / max(s.std(), 1e-3), 0.8, 1.25))
        out[..., c] = (src[..., c] - s.mean()) * gain + r.mean()
        gains.append(round(float(r.mean() - s.mean()), 1))
    return np.clip(out, 0, 255), gains


def composite(base_path: str, expr_path: str, regions: list[tuple[int, int, int, int]], feather: float = 14.0, tolerance: float = 48.0, colour: bool = True) -> tuple[Image.Image, dict]:
    """The base painting with the expression's `regions` (ellipses x0, y0, x1, y1 in base pixels) blended in."""
    base = PX.load_rgba(base_path)
    expr = PX.load_rgba(expr_path)
    if expr.shape != base.shape:
        expr = np.array(Image.fromarray(expr).resize((base.shape[1], base.shape[0]), Image.LANCZOS))
    base_mask, base_bg = PX._foreground(base, tolerance)
    expr_mask, _ = PX._foreground(expr, tolerance)
    scale, dx, dy = register(base, expr, base_mask, expr_mask)
    h, w = base.shape[:2]
    fill = np.array(list(base_bg if base_bg is not None else (0, 0, 0)) + [255], dtype=np.uint8)
    aligned = warp(expr, scale, dx, dy, (h, w), fill)
    aligned_mask = warp(expr_mask, scale, dx, dy, (h, w), np.array(False))
    shape = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(shape)
    for box in regions:
        draw.ellipse(tuple(int(v) for v in box), fill=255)
    weight = np.array(shape.filter(ImageFilter.GaussianBlur(feather)), np.float32) / 255.0
    both = Image.fromarray(((base_mask & aligned_mask) * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(9))
    weight = (weight * (np.array(both, np.float32) / 255.0))[..., None]
    expr_rgb = aligned[..., :3].astype(np.float32)
    shift = None
    if colour:
        expr_rgb, shift = match_colour(expr_rgb, base[..., :3].astype(np.float32), weight[..., 0] > 0.5)
    out = base.astype(np.float32).copy()
    out[..., :3] = out[..., :3] * (1.0 - weight) + expr_rgb * weight
    info = {"scale": round(scale, 4), "dx": round(dx, 1), "dy": round(dy, 1), "regions": [list(map(int, r)) for r in regions], "feather": feather, "colour_shift": shift}
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA"), info
