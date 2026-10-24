"""env_forge drawing toolkit.

Small numpy/Pillow helpers shared by every generator module:

* palette access (`C`, `RA`, reverse lookup `ramp_of`, vectorised `snap`)
* periodic (tileable) value noise, fBm, Voronoi and Poisson-disc sampling
* ordered dithering / quantisation of float fields into ramp indices
* height-map shading with the house light (upper-left, toward the viewer)
* sprite helpers: masks, pixel-perfect strokes, selective outline pass,
  1px transparent-border enforcement, alpha binarisation
* preview writers (4x zoom, 3x3 tiling, labelled contact grids)

Canvases are numpy uint8 arrays shaped (H, W, 4) in straight RGBA.
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, "/home/user/game/tools")
from common.palette import RAMPS, nearest, ramp  # noqa: E402,F401
from common.sheet import SheetBuilder, contact_sheet  # noqa: E402,F401

ROOT = "/home/user/game"
OUT_ENV = os.path.join(ROOT, "assets", "environments")
OUT_FX = os.path.join(ROOT, "assets", "effects")
OUT_UI = os.path.join(ROOT, "assets", "ui")
PREVIEW_DIR = os.path.join(ROOT, "tools", "env_forge", "previews")
FONT_PATH = os.path.join(ROOT, "assets", "fonts", "PixelifySans-Regular.ttf")
PPU = 24  # texels per world unit (meter)

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------

RA: dict[str, np.ndarray] = {n: np.array(c, dtype=np.uint8) for n, c in RAMPS.items()}
_REV: dict[tuple[int, int, int], tuple[str, int]] = {}
for _n, _cs in RAMPS.items():
    for _i, _c in enumerate(_cs):
        _REV.setdefault(_c[:3], (_n, _i))
_ALL = np.array([c[:3] for cs in RAMPS.values() for c in cs], dtype=np.int32)
_ALL_NAMES = [(n, i) for n, cs in RAMPS.items() for i in range(len(cs))]


def C(name: str, i: int, a: int = 255) -> np.ndarray:
    """Ramp colour as a uint8 RGBA array (index clamps; negative = from light end)."""
    return np.array(ramp(name, i, a), dtype=np.uint8)


def nramp(name: str) -> int:
    return len(RAMPS[name])


def ramp_of(rgb) -> tuple[str, int] | None:
    return _REV.get((int(rgb[0]), int(rgb[1]), int(rgb[2])))


def snap(rgb: np.ndarray, ramps: list[str] | None = None) -> np.ndarray:
    """Vectorised nearest-palette snap of an (...,3) array (same metric as palette.nearest)."""
    if ramps is None:
        pal = _ALL
    else:
        pal = np.array([c[:3] for n in ramps for c in RAMPS[n]], dtype=np.int32)
    flat = rgb.reshape(-1, 3).astype(np.int32)
    d = ((flat[:, None, :] - pal[None, :, :]) ** 2 * np.array([3, 4, 2])).sum(-1)
    return pal[np.argmin(d, axis=1)].reshape(rgb.shape).astype(np.uint8)


def off_palette(canvas: np.ndarray) -> int:
    """Number of visible pixels whose RGB is not in the master palette."""
    m = canvas[..., 3] > 0
    if not m.any():
        return 0
    cols = canvas[m][:, :3]
    return int(sum(1 for c in cols if (int(c[0]), int(c[1]), int(c[2])) not in _REV))


# --------------------------------------------------------------------------
# Random / noise (all periodic over the canvas size => seamless tiles)
# --------------------------------------------------------------------------


def rng_for(name: str, salt: int = 0) -> np.random.Generator:
    seed = (sum((i + 1) * ord(ch) for i, ch in enumerate(name)) * 7919 + salt * 104729) % (2**32)
    return np.random.default_rng(seed)


def vnoise(w: int, h: int, cx: int, cy: int, rng: np.random.Generator, smooth: bool = True) -> np.ndarray:
    """Periodic value noise with a cx x cy lattice spread over the w x h canvas. Range 0..1."""
    g = rng.random((cy, cx))
    xs = (np.arange(w) + 0.5) * (cx / w)
    ys = (np.arange(h) + 0.5) * (cy / h)
    x0 = np.floor(xs).astype(int)
    y0 = np.floor(ys).astype(int)
    fx = xs - x0
    fy = ys - y0
    if smooth:
        fx = fx * fx * (3 - 2 * fx)
        fy = fy * fy * (3 - 2 * fy)
    x0 %= cx
    y0 %= cy
    x1 = (x0 + 1) % cx
    y1 = (y0 + 1) % cy
    a = g[np.ix_(y0, x0)]
    b = g[np.ix_(y0, x1)]
    c = g[np.ix_(y1, x0)]
    d = g[np.ix_(y1, x1)]
    fx = fx[None, :]
    fy = fy[:, None]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(w: int, h: int, cells: int, octaves: int, rng: np.random.Generator,
        gain: float = 0.5, cells_y: int | None = None) -> np.ndarray:
    """Periodic fractal value noise normalised to 0..1. `cells` doubles every octave."""
    tot = np.zeros((h, w))
    amp = 1.0
    norm = 0.0
    cxs = cells
    cys = cells_y if cells_y is not None else max(1, round(cells * h / w))
    for _ in range(octaves):
        tot += amp * vnoise(w, h, cxs, cys, rng)
        norm += amp
        amp *= gain
        cxs *= 2
        cys *= 2
    return norm01(tot / norm)


def spectral(w: int, h: int, rng: np.random.Generator, kmin: float = 1.0, kmax: float = 4.0,
             beta: float = 1.0, sx: float = 1.0, sy: float = 1.0) -> np.ndarray:
    """Periodic isotropic noise: sum of waves with integer frequencies (no lattice artefacts).

    kmin/kmax: frequency band in cycles per tile; beta: spectral falloff; sx/sy squash the
    frequency metric (sy < 1 favours horizontal streaks... i.e. more variation along y).
    Range 0..1.
    """
    xs, ys = grid(w, h)
    out = np.zeros((h, w))
    K = int(math.ceil(kmax / min(sx, sy))) + 1
    for kx in range(-K, K + 1):
        for ky in range(0, K + 1):
            if ky == 0 and kx <= 0:
                continue
            k = math.hypot(kx * sx, ky * sy)
            if k < kmin or k > kmax:
                continue
            amp = k ** -beta * abs(rng.normal(1.0, 0.35))
            ph = rng.uniform(0, math.tau)
            out += amp * np.cos(math.tau * (kx * xs / w + ky * ys / h) + ph)
    return norm01(out)


def norm01(a: np.ndarray) -> np.ndarray:
    lo, hi = float(a.min()), float(a.max())
    if hi - lo < 1e-9:
        return np.zeros_like(a, dtype=float)
    return (a - lo) / (hi - lo)


def wrap_delta(d: np.ndarray, period: float) -> np.ndarray:
    return (d + period / 2) % period - period / 2


def grid(w: int, h: int) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.mgrid[0:h, 0:w]
    return xs.astype(float), ys.astype(float)


def poisson(w: int, h: int, r: float, rng: np.random.Generator, k: int = 30,
            wrap: bool = True, n_max: int = 100000, margin: float = 0.0) -> list[tuple[float, float]]:
    """Dart-throwing Poisson-disc sample (periodic distance when wrap=True)."""
    pts: list[tuple[float, float]] = []
    fails = 0
    while fails < k * 40 and len(pts) < n_max:
        x = rng.uniform(margin, w - margin)
        y = rng.uniform(margin, h - margin)
        ok = True
        for (px, py) in pts:
            dx = x - px
            dy = y - py
            if wrap:
                dx = (dx + w / 2) % w - w / 2
                dy = (dy + h / 2) % h - h / 2
            if dx * dx + dy * dy < r * r:
                ok = False
                break
        if ok:
            pts.append((x, y))
            fails = 0
        else:
            fails += 1
    return pts


def voronoi(w: int, h: int, pts, wrap: bool = True, sx: float = 1.0, sy: float = 1.0):
    """Return (cell id, F1, F2) maps. Periodic when wrap=True. sx/sy stretch the metric."""
    P = np.asarray(pts, dtype=float)
    xs, ys = grid(w, h)
    dx = xs[None] + 0.5 - P[:, 0, None, None]
    dy = ys[None] + 0.5 - P[:, 1, None, None]
    if wrap:
        dx = wrap_delta(dx, w)
        dy = wrap_delta(dy, h)
    d = np.sqrt((dx * sx) ** 2 + (dy * sy) ** 2)
    order = np.argsort(d, axis=0)
    ids = order[0]
    d1 = np.take_along_axis(d, order[0:1], 0)[0]
    d2 = np.take_along_axis(d, order[1:2], 0)[0]
    return ids, d1, d2


# --------------------------------------------------------------------------
# Dither / quantise
# --------------------------------------------------------------------------

_B4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], float) / 16.0 - 0.5
_B2 = np.array([[0, 2], [3, 1]], float) / 4.0 - 0.5


def bayer(w: int, h: int, size: int = 4) -> np.ndarray:
    m = _B4 if size == 4 else _B2
    s = m.shape[0]
    return np.tile(m, (h // s + 1, w // s + 1))[:h, :w]


def quant(v: np.ndarray, n: int, dither: float = 0.0, size: int = 4) -> np.ndarray:
    """Quantise a 0..1 field into n integer levels with optional ordered dither."""
    h, w = v.shape
    q = v * n
    if dither:
        q = q + bayer(w, h, size) * dither
    return np.clip(np.floor(q), 0, n - 1).astype(int)


def levels(v: np.ndarray, thresholds: list[float], dither: float = 0.0) -> np.ndarray:
    """Map a field to level index by explicit thresholds (len(thresholds)+1 levels)."""
    h, w = v.shape
    vv = v + (bayer(w, h) * dither if dither else 0)
    out = np.zeros(v.shape, int)
    for t in thresholds:
        out += (vv >= t).astype(int)
    return out


# --------------------------------------------------------------------------
# Shading
# --------------------------------------------------------------------------

LIGHT = np.array([-1.0, -1.0, 1.25])
LIGHT = LIGHT / np.linalg.norm(LIGHT)


def normals(hm: np.ndarray, strength: float = 1.0, wrap: bool = True) -> np.ndarray:
    if wrap:
        gx = (np.roll(hm, -1, 1) - np.roll(hm, 1, 1)) * 0.5
        gy = (np.roll(hm, -1, 0) - np.roll(hm, 1, 0)) * 0.5
    else:
        gy, gx = np.gradient(hm)
    n = np.stack([-gx * strength, -gy * strength, np.ones_like(hm)], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def lambert(hm: np.ndarray, strength: float = 1.0, wrap: bool = True, light=None, ambient: float = 0.0) -> np.ndarray:
    L = LIGHT if light is None else np.asarray(light, float) / np.linalg.norm(light)
    n = normals(hm, strength, wrap)
    return np.clip(ambient + (1 - ambient) * (n @ L), 0, 1)


def sphere_shade(xs, ys, cx, cy, rx, ry, light=None):
    """Lambert of an ellipsoid cap; returns (inside mask, shade 0..1)."""
    L = LIGHT if light is None else np.asarray(light, float) / np.linalg.norm(light)
    u = (xs + 0.5 - cx) / rx
    v = (ys + 0.5 - cy) / ry
    rr = u * u + v * v
    inside = rr <= 1.0
    z = np.sqrt(np.clip(1 - rr, 0, 1))
    sh = np.clip(u * L[0] + v * L[1] + z * L[2], 0, 1)
    return inside, sh


# --------------------------------------------------------------------------
# Canvas helpers
# --------------------------------------------------------------------------


def canvas(w: int, h: int, fill=None) -> np.ndarray:
    c = np.zeros((h, w, 4), np.uint8)
    if fill is not None:
        c[:] = fill
    return c


def paint(cv: np.ndarray, mask: np.ndarray, color) -> None:
    cv[mask] = np.asarray(color, np.uint8)


def paint_ramp(cv: np.ndarray, mask: np.ndarray, name: str, idx: np.ndarray) -> None:
    """cv[mask] = ramp colour at idx (idx is a full-size int array or scalar)."""
    r = RA[name]
    if np.isscalar(idx):
        cv[mask] = r[int(np.clip(idx, 0, len(r) - 1))]
    else:
        cv[mask] = r[np.clip(idx[mask], 0, len(r) - 1)]


def put(cv: np.ndarray, x: float, y: float, color, wrap: bool = False) -> None:
    h, w = cv.shape[:2]
    xi, yi = int(math.floor(x)), int(math.floor(y))
    if wrap:
        cv[yi % h, xi % w] = color
    elif 0 <= xi < w and 0 <= yi < h:
        cv[yi, xi] = color


def get(cv: np.ndarray, x: int, y: int, wrap: bool = False):
    h, w = cv.shape[:2]
    if wrap:
        return cv[y % h, x % w]
    if 0 <= x < w and 0 <= y < h:
        return cv[y, x]
    return None


def ellipse_mask(w: int, h: int, cx: float, cy: float, rx: float, ry: float, wrap: bool = False) -> np.ndarray:
    xs, ys = grid(w, h)
    dx = xs + 0.5 - cx
    dy = ys + 0.5 - cy
    if wrap:
        dx = wrap_delta(dx, w)
        dy = wrap_delta(dy, h)
    return (dx / rx) ** 2 + (dy / ry) ** 2 <= 1.0


def poly_mask(w: int, h: int, pts, ss: int = 1) -> np.ndarray:
    """Polygon fill mask. pts in pixel coordinates (float ok)."""
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).polygon([(x * ss, y * ss) for x, y in pts], fill=255)
    if ss > 1:
        im = im.resize((w, h), Image.BOX)
    return np.array(im) >= 128


def rect_mask(w: int, h: int, x0: int, y0: int, x1: int, y1: int) -> np.ndarray:
    m = np.zeros((h, w), bool)
    m[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = True
    return m


def bezier(pts, n: int = 64) -> list[tuple[float, float]]:
    """Evaluate a Bezier curve of any degree."""
    P = np.asarray(pts, float)
    out = []
    for t in np.linspace(0, 1, n):
        Q = P.copy()
        while len(Q) > 1:
            Q = Q[:-1] * (1 - t) + Q[1:] * t
        out.append((float(Q[0][0]), float(Q[0][1])))
    return out


def raster_path(pts, closed: bool = False) -> list[tuple[int, int]]:
    """Turn a dense float polyline into a connected list of integer pixels (8-connected)."""
    seq: list[tuple[int, int]] = []
    P = list(pts) + ([pts[0]] if closed else [])
    for (x0, y0), (x1, y1) in zip(P[:-1], P[1:]):
        steps = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
        for s in range(steps + 1):
            t = s / steps
            p = (int(math.floor(x0 + (x1 - x0) * t)), int(math.floor(y0 + (y1 - y0) * t)))
            if not seq or seq[-1] != p:
                seq.append(p)
    return pixel_perfect(seq)


def pixel_perfect(seq: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Remove L-shaped corner pixels so 1px strokes stay clean (Aseprite 'pixel perfect')."""
    if len(seq) < 3:
        return seq
    out = [seq[0]]
    i = 1
    while i < len(seq) - 1:
        a, b, c = out[-1], seq[i], seq[i + 1]
        if (a[0] == b[0] or a[1] == b[1]) and (b[0] == c[0] or b[1] == c[1]) and a[0] != c[0] and a[1] != c[1]:
            i += 1
            continue
        out.append(b)
        i += 1
    out.append(seq[-1])
    return out


def stroke(cv: np.ndarray, pts, color, width: int = 1, wrap: bool = False, closed: bool = False) -> list[tuple[int, int]]:
    px = raster_path(pts, closed)
    r = width // 2
    for (x, y) in px:
        if width == 1:
            put(cv, x, y, color, wrap)
        else:
            for oy in range(-r, width - r):
                for ox in range(-r, width - r):
                    put(cv, x + ox, y + oy, color, wrap)
    return px


def stroke_mask(w: int, h: int, pts, width: float = 1.0, ss: int = 1) -> np.ndarray:
    """Thick polyline mask (round joints)."""
    im = Image.new("L", (w * ss, h * ss), 0)
    d = ImageDraw.Draw(im)
    P = [(x * ss, y * ss) for x, y in pts]
    if width <= 1.01 and ss == 1:
        m = np.zeros((h, w), bool)
        for (x, y) in raster_path(pts):
            if 0 <= x < w and 0 <= y < h:
                m[y, x] = True
        return m
    d.line(P, fill=255, width=max(1, int(round(width * ss))), joint="curve")
    rr = width * ss / 2
    for (x, y) in (P[0], P[-1]):
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=255)
    if ss > 1:
        im = im.resize((w, h), Image.BOX)
    return np.array(im) >= 128


def taper_mask(w: int, h: int, pts, w0: float, w1: float, ss: int = 4) -> np.ndarray:
    """Mask of a stroke whose width tapers linearly from w0 to w1 along the path."""
    im = Image.new("L", (w * ss, h * ss), 0)
    d = ImageDraw.Draw(im)
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        t = i / max(1, n - 1)
        r = (w0 + (w1 - w0) * t) * ss / 2
        d.ellipse([x * ss - r, y * ss - r, x * ss + r, y * ss + r], fill=255)
    im = im.resize((w, h), Image.BOX)
    return np.array(im) >= 110


def shift(m: np.ndarray, dx: int, dy: int, wrap: bool = False, fill=False) -> np.ndarray:
    """Shift a 2D array by (dx, dy). Positive dx moves content right."""
    if wrap:
        return np.roll(np.roll(m, dy, 0), dx, 1)
    out = np.full_like(m, fill)
    h, w = m.shape[:2]
    ys0, ys1 = max(0, dy), min(h, h + dy)
    xs0, xs1 = max(0, dx), min(w, w + dx)
    out[ys0:ys1, xs0:xs1] = m[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
    return out


def dilate(m: np.ndarray, r: int = 1, diag: bool = True, wrap: bool = False) -> np.ndarray:
    out = m.copy()
    for _ in range(r):
        cur = out.copy()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) + (((1, 1), (-1, 1), (1, -1), (-1, -1)) if diag else ()):
            cur |= shift(out, dx, dy, wrap)
        out = cur
    return out


def erode(m: np.ndarray, r: int = 1, diag: bool = False, wrap: bool = False) -> np.ndarray:
    """Morphological erosion. Off-canvas counts as background unless wrap=True."""
    if wrap or r <= 0:
        return ~dilate(~m, r, diag, wrap)
    pad = np.pad(m, r, constant_values=False)
    out = ~dilate(~pad, r, diag, False)
    return out[r:-r, r:-r]


def edge_in(m: np.ndarray, wrap: bool = False, diag: bool = False) -> np.ndarray:
    """Pixels of m that touch a non-m pixel."""
    return m & ~erode(m, 1, diag, wrap)


def alpha(cv: np.ndarray) -> np.ndarray:
    return cv[..., 3] > 0


def binarize(cv: np.ndarray, thr: int = 128) -> np.ndarray:
    a = cv[..., 3] >= thr
    cv[..., 3] = np.where(a, 255, 0)
    cv[~a] = 0
    return cv


def clear_border(cv: np.ndarray, px: int = 1) -> np.ndarray:
    cv[:px] = 0
    cv[-px:] = 0
    cv[:, :px] = 0
    cv[:, -px:] = 0
    return cv


def border_ok(cv: np.ndarray) -> bool:
    a = cv[..., 3]
    return not (a[0].any() or a[-1].any() or a[:, 0].any() or a[:, -1].any())


def outline(cv: np.ndarray, mode: str = "outer", diag: bool = False, color=None,
            lit_index: int = 0, only=None) -> np.ndarray:
    """Selective outline using the darkest shade of the adjacent material's ramp.

    mode="outer": grows the silhouette by 1px (transparent pixels next to opaque ones).
    mode="inner": recolours the silhouette's own edge pixels.
    lit_index>0 uses that ramp index instead of 0 on edges facing the light (top/left).
    `only` (bool mask) restricts where outline pixels may be placed.
    """
    a = alpha(cv)
    h, w = a.shape
    out = cv.copy()
    dirs = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # neighbour offsets (dx, dy): below, right, above, left
    if diag:
        dirs += [(1, 1), (-1, 1), (1, -1), (-1, -1)]
    if mode == "outer":
        cand = np.zeros_like(a)
        for dx, dy in dirs:
            cand |= shift(a, -dx, -dy) & ~a
    else:
        cand = np.zeros_like(a)
        for dx, dy in dirs[:4]:
            cand |= a & ~shift(a, -dx, -dy, fill=False)
    if only is not None:
        cand &= only
    ys, xs = np.nonzero(cand)
    for y, x in zip(ys, xs):
        if color is not None:
            out[y, x] = color
            continue
        src = None
        lit = False
        if mode == "outer":
            for dx, dy in dirs:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and a[ny, nx]:
                    src = cv[ny, nx]
                    lit = dx > 0 or dy > 0  # the shape lies to the right/below -> this is its lit side
                    break
        else:
            src = cv[y, x]
            lit = (x > 0 and not a[y, x - 1]) or (y > 0 and not a[y - 1, x])
        info = ramp_of(src) if src is not None else None
        if info is None:
            info = ramp_of(nearest(tuple(int(v) for v in src))) if src is not None else ("ink", 0)
        name = info[0] if info else "ink"
        idx = lit_index if (lit and lit_index) else 0
        out[y, x] = C(name, idx)
    return out


def darken(cv: np.ndarray, mask: np.ndarray, steps: int = 1) -> None:
    """Move masked pixels `steps` shades down their own ramp."""
    ys, xs = np.nonzero(mask & alpha(cv))
    for y, x in zip(ys, xs):
        info = ramp_of(cv[y, x])
        if info:
            cv[y, x] = C(info[0], max(0, info[1] - steps), cv[y, x][3])


def lighten(cv: np.ndarray, mask: np.ndarray, steps: int = 1) -> None:
    ys, xs = np.nonzero(mask & alpha(cv))
    for y, x in zip(ys, xs):
        info = ramp_of(cv[y, x])
        if info:
            n = nramp(info[0])
            cv[y, x] = C(info[0], min(n - 1, info[1] + steps), cv[y, x][3])


def composite(dst: np.ndarray, src: np.ndarray, ox: int = 0, oy: int = 0) -> np.ndarray:
    """Paste opaque pixels of src onto dst (binary alpha)."""
    h, w = src.shape[:2]
    H, W = dst.shape[:2]
    for y in range(h):
        ty = y + oy
        if not 0 <= ty < H:
            continue
        for x in range(w):
            tx = x + ox
            if 0 <= tx < W and src[y, x, 3] > 0:
                dst[ty, tx] = src[y, x]
    return dst


def over(dst: np.ndarray, src: np.ndarray) -> np.ndarray:
    """Straight-alpha 'over' compositing (float) - for VFX layers."""
    sa = src[..., 3:4].astype(float) / 255
    da = dst[..., 3:4].astype(float) / 255
    oa = sa + da * (1 - sa)
    rgb = (src[..., :3] * sa + dst[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-6)
    out = np.concatenate([rgb, oa * 255], -1)
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def flip_h(cv: np.ndarray) -> np.ndarray:
    return cv[:, ::-1].copy()


# --------------------------------------------------------------------------
# I/O and previews
# --------------------------------------------------------------------------


def save_png(cv: np.ndarray, path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(cv, "RGBA").save(path)
    return path


def to_image(cv: np.ndarray) -> Image.Image:
    return Image.fromarray(cv, "RGBA")


def _checker(w: int, h: int, cell: int = 4) -> Image.Image:
    xs, ys = grid(w, h)
    m = ((xs // cell + ys // cell) % 2).astype(bool)
    a = np.zeros((h, w, 4), np.uint8)
    a[m] = (58, 64, 74, 255)
    a[~m] = (78, 86, 98, 255)
    return Image.fromarray(a, "RGBA")


def zoom(cv: np.ndarray, scale: int = 4, bg: str | tuple = "checker") -> Image.Image:
    im = to_image(cv)
    w, h = im.size
    if bg == "checker":
        base = _checker(w, h)
    else:
        base = Image.new("RGBA", (w, h), bg)
    base.alpha_composite(im)
    return base.resize((w * scale, h * scale), Image.NEAREST)


def preview(cv: np.ndarray, name: str, scale: int = 4, bg="checker") -> str:
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    p = os.path.join(PREVIEW_DIR, name + ".png")
    zoom(cv, scale, bg).save(p)
    return p


def tile_preview(cv: np.ndarray, name: str, n: int = 3, scale: int = 4) -> str:
    h, w = cv.shape[:2]
    big = np.tile(cv, (n, n, 1))
    return preview(big, name, scale)


_FONT = None


def _font(size: int = 16):
    global _FONT
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:  # pragma: no cover
        return ImageFont.load_default()


def grid_preview(items: list[tuple[str, np.ndarray]], name: str, scale: int = 4, cols: int = 6,
                 pad: int = 6, bg=(40, 44, 52, 255), cell_bg="checker", label: bool = True) -> str:
    """Labelled contact grid of several canvases (each zoomed `scale`x); rows packed by their own height."""
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    zs = [(lab, zoom(cv, scale, cell_bg)) for lab, cv in items]
    cols = max(1, min(cols, len(zs)))
    rows = [zs[i:i + cols] for i in range(0, len(zs), cols)]
    lab_h = 18 if label else 0
    f = _font(14)
    col_w = [0] * cols
    for row in rows:
        for j, (lab, z) in enumerate(row):
            tw = int(f.getlength(lab)) if label else 0
            col_w[j] = max(col_w[j], z.size[0], tw)
    row_h = [max(z.size[1] for _, z in row) for row in rows]
    W = sum(col_w) + pad * (cols + 1)
    H = sum(row_h) + (pad + lab_h) * len(rows) + pad
    out = Image.new("RGBA", (W, H), bg)
    d = ImageDraw.Draw(out)
    y = pad
    for r, row in enumerate(rows):
        x = pad
        for j, (lab, z) in enumerate(row):
            if label:
                d.text((x, y), lab, fill=(230, 230, 230, 255), font=f)
            out.alpha_composite(z, (x, y + lab_h + (row_h[r] - z.size[1])))
            x += col_w[j] + pad
        y += row_h[r] + lab_h + pad
    p = os.path.join(PREVIEW_DIR, name + ".png")
    out.save(p)
    return p


def scene_preview(bg: np.ndarray, sprites: list[tuple[np.ndarray, int, int]], name: str, scale: int = 3) -> str:
    """Composite sprites (bottom-center pivot at x, y) over a background canvas for an in-context check."""
    cv = bg.copy()
    for spr, x, y in sprites:
        h, w = spr.shape[:2]
        composite(cv, spr, int(x - w // 2), int(y - h + 1))
    return preview(cv, name, scale, bg=(0, 0, 0, 255))
