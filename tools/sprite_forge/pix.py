"""Tiny procedural pixel-art kit used by every Wildbound sprite generator.

Pipeline for one frame:

    shapes (ellipsoids, tubes, polygons, hand-made masks) carry a height field
        -> Part = shape + material ramp + base shade + z order + line rules
        -> Figure.render():
             1. painter's z-buffer of parts (owner map)
             2. per-part directional lighting (key light from the upper-left,
                toward the viewer) quantised into ramp indices
             3. orphan-pixel cleanup (no lonely single shade pixels)
             4. soft cast shadows of front parts onto parts behind them
             5. interior contour lines where a front part overlaps another
             6. explicit pixel decals (eyes, buttons, sparkles ...)
             7. 1px external outline, coloured with the darkest shade of the
                neighbouring material (never pure black)

Everything is integer-exact and deterministic: translating a shape by whole
pixels gives an identical raster, so volumes stay constant between frames.
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common.palette import RAMPS  # noqa: E402

# --------------------------------------------------------------------------
# basics


def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


# Vector pointing from a surface toward the key light: left (-x), up (-y)
# and toward the viewer (+z). Image space: x right, y down, z out of screen.
LIGHT = _unit((-0.62, -0.78, 0.95))
FLAT_S = float(LIGHT[2])


def col(ramp_name: str, i: int) -> tuple[int, int, int, int]:
    r = RAMPS[ramp_name]
    if i < 0:
        i = len(r) + i
    return r[max(0, min(len(r) - 1, i))]


def nramp(ramp_name: str) -> int:
    return len(RAMPS[ramp_name])


def lum(c) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def nb(a: np.ndarray, dx: int, dy: int, fill):
    """out[y, x] = a[y + dy, x + dx] (fill outside)."""
    out = np.full_like(a, fill)
    h, w = a.shape[:2]
    if abs(dx) >= w or abs(dy) >= h:
        return out
    ys_o = slice(max(0, -dy), h - max(0, dy))
    xs_o = slice(max(0, -dx), w - max(0, dx))
    ys_i = slice(max(0, dy), h - max(0, -dy))
    xs_i = slice(max(0, dx), w - max(0, -dx))
    out[ys_o, xs_o] = a[ys_i, xs_i]
    return out


N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
N8 = N4 + ((1, 1), (-1, -1), (1, -1), (-1, 1))


# --------------------------------------------------------------------------
# shapes: mask + height field + normals


class Shape:
    """A raster region with a height field (pixel units) and unit normals."""

    __slots__ = ("mask", "h", "nx", "ny", "nz")

    def __init__(self, mask, h=None, nx=None, ny=None, nz=None):
        self.mask = mask.astype(bool)
        shp = self.mask.shape
        self.h = np.zeros(shp) if h is None else h
        self.nx = np.zeros(shp) if nx is None else nx
        self.ny = np.zeros(shp) if ny is None else ny
        self.nz = np.ones(shp) if nz is None else nz

    @property
    def shape(self):
        return self.mask.shape

    def copy(self):
        return Shape(self.mask.copy(), self.h.copy(), self.nx.copy(), self.ny.copy(), self.nz.copy())

    def __or__(self, other: "Shape") -> "Shape":
        """Union; where both exist the higher surface wins (smooth blend of volumes)."""
        take_o = other.mask & (~self.mask | (other.h > self.h))
        out = self.copy()
        out.mask = self.mask | other.mask
        for a in ("h", "nx", "ny", "nz"):
            getattr(out, a)[take_o] = getattr(other, a)[take_o]
        return out

    def __sub__(self, other: "Shape") -> "Shape":
        out = self.copy()
        out.mask = self.mask & ~other.mask
        return out

    def __and__(self, other: "Shape") -> "Shape":
        out = self.copy()
        out.mask = self.mask & other.mask
        return out

    def cut(self, mask) -> "Shape":
        out = self.copy()
        out.mask = self.mask & ~mask
        return out

    def clip(self, mask) -> "Shape":
        out = self.copy()
        out.mask = self.mask & mask
        return out

    def shifted(self, dx: int, dy: int) -> "Shape":
        out = Shape(nb(self.mask, -dx, -dy, False))
        out.h = nb(self.h, -dx, -dy, 0.0)
        out.nx = nb(self.nx, -dx, -dy, 0.0)
        out.ny = nb(self.ny, -dx, -dy, 0.0)
        out.nz = nb(self.nz, -dx, -dy, 1.0)
        return out

    def flipped_x(self) -> "Shape":
        out = Shape(self.mask[:, ::-1].copy(), self.h[:, ::-1].copy(), -self.nx[:, ::-1].copy(),
                    self.ny[:, ::-1].copy(), self.nz[:, ::-1].copy())
        return out

    def tilt(self, tx: float = 0.0, ty: float = 0.0) -> "Shape":
        """Bend all normals (e.g. ty<0 makes a surface face upward = brighter)."""
        out = self.copy()
        nx, ny, nz = out.nx + tx, out.ny + ty, out.nz
        ln = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-9
        out.nx, out.ny, out.nz = nx / ln, ny / ln, nz / ln
        return out

    def flat(self, nxv=0.0, nyv=0.0) -> "Shape":
        """Replace normals with one constant direction."""
        out = self.copy()
        v = _unit((nxv, nyv, 1.0))
        out.nx = np.full(self.shape, v[0])
        out.ny = np.full(self.shape, v[1])
        out.nz = np.full(self.shape, v[2])
        return out

    def area(self) -> int:
        return int(self.mask.sum())

    def bbox(self):
        ys, xs = np.nonzero(self.mask)
        if len(xs) == 0:
            return None
        return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _grid(w, h):
    ys, xs = np.mgrid[0:h, 0:w].astype(float)
    return xs + 0.5, ys + 0.5


def empty(w, h) -> Shape:
    return Shape(np.zeros((h, w), bool))


def ellipse(w, h, cx, cy, rx, ry, rz=None, angle=0.0, smooth=True) -> Shape:
    """Ellipsoid cap. (cx, cy) in continuous pixel coords (pixel i spans [i, i+1))."""
    X, Y = _grid(w, h)
    dx, dy = X - cx, Y - cy
    if angle:
        ca, sa = math.cos(angle), math.sin(angle)
        u = (dx * ca + dy * sa) / rx
        v = (-dx * sa + dy * ca) / ry
    else:
        ca, sa = 1.0, 0.0
        u, v = dx / rx, dy / ry
    d2 = u * u + v * v
    mask = d2 <= 1.0 + 1e-9
    if rz is None:
        rz = min(rx, ry)
    t = np.sqrt(np.clip(1.0 - d2, 0.0, 1.0))
    hgt = rz * t
    # gradient of implicit ellipsoid in local frame
    gu, gv, gz = u / rx, v / ry, t / rz
    gx = gu * ca - gv * sa
    gy = gu * sa + gv * ca
    ln = np.sqrt(gx * gx + gy * gy + gz * gz) + 1e-9
    s = Shape(mask, hgt * mask, gx / ln, gy / ln, gz / ln)
    if smooth:
        s.mask = despike(s.mask)
    return s


def circle(w, h, cx, cy, r, rz=None) -> Shape:
    return ellipse(w, h, cx, cy, r, r, rz)


def _seg_dist(X, Y, x0, y0, x1, y1):
    vx, vy = x1 - x0, y1 - y0
    L2 = vx * vx + vy * vy
    if L2 < 1e-12:
        t = np.zeros_like(X)
    else:
        t = np.clip(((X - x0) * vx + (Y - y0) * vy) / L2, 0.0, 1.0)
    px, py = x0 + t * vx, y0 + t * vy
    return X - px, Y - py, t


def tube(w, h, pts, radii, rz_scale=1.0, caps=True) -> Shape:
    """Tapered tube along a polyline. radii: one value per point (or scalar)."""
    if np.isscalar(radii):
        radii = [float(radii)] * len(pts)
    X, Y = _grid(w, h)
    out = empty(w, h)
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        r0, r1 = radii[i], radii[i + 1]
        ox, oy, t = _seg_dist(X, Y, x0, y0, x1, y1)
        r = r0 + (r1 - r0) * t
        d = np.sqrt(ox * ox + oy * oy)
        mask = d <= r + 1e-9
        if not caps:
            mask &= (t > 0.0) | (i > 0)
            mask &= (t < 1.0) | (i < len(pts) - 2)
        tt = np.sqrt(np.clip(1.0 - (d / np.maximum(r, 1e-6)) ** 2, 0.0, 1.0))
        hgt = r * tt * rz_scale
        nx = ox / np.maximum(r, 1e-6)
        ny = oy / np.maximum(r, 1e-6)
        nz = tt / max(rz_scale, 1e-6)
        ln = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-9
        seg = Shape(mask, hgt * mask, nx / ln, ny / ln, nz / ln)
        out = out | seg
    return out


def polygon_mask(w, h, pts) -> np.ndarray:
    """Even-odd point-in-polygon test at pixel centres."""
    X, Y = _grid(w, h)
    inside = np.zeros((h, w), bool)
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if y0 == y1:
            continue
        cond = (Y >= min(y0, y1)) & (Y < max(y0, y1))
        xint = x0 + (Y - y0) * (x1 - x0) / (y1 - y0)
        inside ^= cond & (X < xint)
    return inside


def dist_inside(mask: np.ndarray) -> np.ndarray:
    """Euclidean distance (pixel centres) from inside pixels to the nearest outside pixel."""
    h, w = mask.shape
    pad = np.zeros((h + 2, w + 2), bool)
    pad[1:-1, 1:-1] = mask
    outside = ~pad
    # boundary outside pixels only
    border = outside & (nb(pad, 1, 0, False) | nb(pad, -1, 0, False) | nb(pad, 0, 1, False) | nb(pad, 0, -1, False))
    oy, ox = np.nonzero(border)
    iy, ix = np.nonzero(mask)
    d = np.zeros((h, w))
    if len(ix) == 0 or len(ox) == 0:
        return d
    dy = (iy + 1)[:, None] - oy[None, :]
    dx = (ix + 1)[:, None] - ox[None, :]
    dd = np.sqrt(dx * dx + dy * dy).min(axis=1)
    d[iy, ix] = dd - 0.5
    return d


def from_mask(mask: np.ndarray, bevel: float = 2.5, dome: bool = False) -> Shape:
    """Give an arbitrary mask a rounded-edge height field (or a full dome)."""
    mask = mask.astype(bool)
    d = dist_inside(mask)
    if dome:
        R = max(1.0, float(d.max()))
    else:
        R = float(bevel)
    dc = np.clip(d, 0, R)
    hgt = np.sqrt(np.clip(R * R - (R - dc) ** 2, 0, None)) * mask
    gy, gx = np.gradient(hgt)
    nx, ny, nz = -gx, -gy, np.ones_like(hgt)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    return Shape(mask, hgt, nx / ln, ny / ln, nz / ln)


def poly(w, h, pts, bevel=2.5, dome=False) -> Shape:
    return from_mask(polygon_mask(w, h, pts), bevel=bevel, dome=dome)


def rect_mask(w, h, x0, y0, x1, y1) -> np.ndarray:
    """Inclusive integer rectangle."""
    m = np.zeros((h, w), bool)
    x0, x1 = max(0, int(x0)), min(w - 1, int(x1))
    y0, y1 = max(0, int(y0)), min(h - 1, int(y1))
    if x1 >= x0 and y1 >= y0:
        m[y0:y1 + 1, x0:x1 + 1] = True
    return m


def rrect(w, h, x0, y0, x1, y1, r=1.5, bevel=2.0, dome=False) -> Shape:
    """Rounded rectangle over the continuous box [x0, x1] x [y0, y1]."""
    X, Y = _grid(w, h)
    cx = np.clip(X, x0 + r, x1 - r)
    cy = np.clip(Y, y0 + r, y1 - r)
    m = ((X - cx) ** 2 + (Y - cy) ** 2 <= r * r + 1e-9) & (X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1)
    return from_mask(m, bevel=bevel, dome=dome)


def ascii_mask(w, h, rows: list[str], ox: int, oy: int, chars: str = "#") -> np.ndarray:
    m = np.zeros((h, w), bool)
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch in chars:
                x, y = ox + i, oy + j
                if 0 <= x < w and 0 <= y < h:
                    m[y, x] = True
    return m


def despike(mask: np.ndarray) -> np.ndarray:
    """Remove single-pixel nubs (pixels with <=1 orthogonal neighbour) from smooth shapes."""
    m = mask.copy()
    for _ in range(2):
        cnt = sum(nb(m, dx, dy, False).astype(int) for dx, dy in N4)
        kill = m & (cnt <= 1)
        if not kill.any():
            break
        # keep isolated tiny shapes (cnt==0) only if the whole shape is tiny
        if m.sum() <= 3:
            break
        m &= ~kill
    return m


# --------------------------------------------------------------------------
# parts


class Part:
    """A shape painted with one material ramp.

    HD parts (k=2) use a half-step ramp (`<ramp>_hd`, see common/palette.py): every
    original shade i sits at index 2*i, with an in-between shade at the odd indices.
    `levels` then quantises the light into half steps (softer, multi-shade ramps);
    `tex` is an additive perturbation of the light term (fur clumps, stone grain)
    that makes band borders follow a texture instead of a smooth curve.
    """

    def __init__(self, shape: Shape, ramp: str, base: int = 3, z: float = 0.0, *, name: str = "",
                 lo: int = 1, hi: int | None = None, idx: np.ndarray | None = None,
                 outline: bool = True, oc=None, contour: int | None = None, contour_col=None,
                 cast: int = 1, recv: bool = True, group=None, bands=None, spec: bool = False,
                 light: float = 1.0, offset: int = 0, cast_dirs=None, glow: bool = True,
                 levels=None, tex: np.ndarray | None = None, k: int = 1, spec_cap: int | None = None,
                 contour_dirs=None):
        self.shape = shape
        self.ramp = ramp
        self.base = base
        self.z = z
        self.name = name
        self.lo = lo
        self.hi = nramp(ramp) - 1 if hi is None else hi
        self.idx = idx
        self.outline = outline
        self.oc = oc if oc is not None else col(ramp, 0)
        self.contour = contour
        self.contour_col = contour_col
        self.cast = cast
        self.recv = recv
        self.group = group if group is not None else id(self)
        # (hi1, hi2, lo1, lo2) thresholds on (N.L - flat)
        self.bands = bands or (0.10, 0.26, -0.20, -0.58)
        self.spec = spec
        self.light = light
        self.offset = offset
        self.cast_dirs = cast_dirs
        self.glow = glow
        # half-step quantisation: (edges, offsets) with len(offsets) == len(edges) + 1
        self.levels = levels
        self.tex = tex
        self.k = k                  # shade-index units per original ramp step (1, or 2 for HD ramps)
        self.spec_cap = spec_cap    # max positive offset without `spec` (HD); None = derive from levels
        # selective interior contour: only on these sides of the part, e.g. ("r", "b") = the
        # shadow side (light comes from the upper left); None = all around
        self.contour_dirs = contour_dirs

    def light_term(self) -> np.ndarray:
        s = self.shape
        lit = s.nx * LIGHT[0] + s.ny * LIGHT[1] + s.nz * LIGHT[2]
        t = (lit - FLAT_S) * self.light
        if self.tex is not None:
            t = t + self.tex
        return t

    def indices(self) -> np.ndarray:
        if self.idx is not None:
            return self.idx.astype(int)
        s = self.shape
        if self.levels is not None:
            t = self.light_term()
            edges, offs = self.levels
            off = np.asarray(offs, int)[np.searchsorted(np.asarray(edges, float), t)]
            cap = self.spec_cap if self.spec_cap is not None else (max(offs) if self.spec else self.k)
            off = np.minimum(off, cap)
            out = self.base + off + self.offset
            return np.clip(out, self.lo, self.hi)
        lit = s.nx * LIGHT[0] + s.ny * LIGHT[1] + s.nz * LIGHT[2]
        t = (lit - FLAT_S) * self.light
        if self.tex is not None:
            t = t + self.tex
        hi1, hi2, lo1, lo2 = self.bands
        off = np.zeros(s.shape, int)
        off[t > hi1] = 1
        if self.spec:
            off[t > hi2] = 2
        off[t < lo1] = -1
        off[t < lo2] = -2
        out = self.base + off + self.offset
        return np.clip(out, self.lo, self.hi)


# Half-step light levels for HD ramps: t = N.L - flat, offsets in HD indices
# (2 = one original ramp step). Without `spec` the top is capped at +2.
HD_LEVELS = ((-0.57, -0.36, -0.21, -0.08, 0.06, 0.14, 0.21, 0.28), (-4, -3, -2, -1, 0, 1, 2, 3, 4))


def tube_coords(w, h, pts):
    """Arc length s along a polyline and signed distance r from it (pixel units), per pixel.

    Used to make textures (fur strands, plate grain) follow a curved limb or tail.
    """
    X, Y = _grid(w, h)
    best_d = np.full((h, w), 1e9)
    S = np.zeros((h, w))
    R = np.zeros((h, w))
    acc = 0.0
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        ox, oy, t = _seg_dist(X, Y, x0, y0, x1, y1)
        L = math.hypot(x1 - x0, y1 - y0)
        d = np.sqrt(ox * ox + oy * oy)
        better = d < best_d
        best_d = np.where(better, d, best_d)
        side = np.sign((x1 - x0) * (Y - y0) - (y1 - y0) * (X - x0))
        S = np.where(better, acc + t * L, S)
        R = np.where(better, d * np.where(side == 0, 1.0, side), R)
        acc += L
    return S, R


# --------------------------------------------------------------------------
# figure / renderer


# Cast-shadow sample offsets per `cast` level: a pixel is shaded when the pixel at
# (x+dx, y+dy) belongs to a part in front. Scale 1 = the original 48px look;
# scale 2 doubles the reach (same world size on a 2x sheet).
_CAST_OFFSETS = {
    1: ((-1, -1, 1), (0, -1, 1), (-1, 0, 1), (0, -2, 2), (-1, -2, 2), (-2, -2, 3), (0, -3, 3), (-1, -3, 3)),
    2: ((-1, -1, 1), (0, -1, 1), (-1, 0, 1), (-2, -2, 1), (0, -2, 1), (-1, -2, 1), (-2, -1, 1),
        (0, -3, 2), (-1, -3, 2), (0, -4, 2), (-1, -4, 2), (-2, -3, 2), (-2, -4, 2),
        (-3, -3, 3), (-4, -4, 3), (0, -5, 3), (-1, -5, 3), (0, -6, 3), (-1, -6, 3), (-2, -5, 3), (-2, -6, 3)),
}


class Figure:
    def __init__(self, w: int, h: int, scale: int = 1):
        self.w, self.h = w, h
        self.scale = scale
        self.parts: list[Part] = []
        self.decals: list = []      # (x, y, rgba) drawn over fills, before outline
        self.post: list = []        # (x, y, rgba) drawn after everything
        self.erase: list = []       # (x, y) cleared before outline
        self.outline_on = True
        self.selout = False
        self.glows: list = []       # (x, y, radius, steps): warm point light from a glowing object
        self.glow_unit = 1          # glow steps per original ramp step (2 on HD canvases)
        self.outline_fn = None      # optional hook(out, owner) -> out, run after the outline
        self.post_margin = 0        # post-pass effects (sparks, rays) never land within this many px of the edge
        self.floor = None           # ground row: no part fills it or anything below (the outline lands on it)
        # shadow-side rim: fill pixels whose right/lower neighbour is outside the silhouette get one
        # shade darker, so the silhouette carries weight on its shadow side (light comes from the upper left)
        self.rim_dark = 0
        self.outline_shadow = 0     # extra outline pixels on the shadow (right/bottom) side
        self.outline_all = False    # ... or on every side (2x sheets: same world-space weight as a 1x outline)

    # convenience -----------------------------------------------------------
    def add(self, shape: Shape, ramp: str, base: int = 3, z: float = 0.0, **kw) -> Part:
        p = Part(shape, ramp, base, z, **kw)
        self.parts.append(p)
        return p

    def dot(self, x, y, c, post=False):
        (self.post if post else self.decals).append((int(x), int(y), c))

    def dots(self, pts, c, post=False):
        for x, y in pts:
            self.dot(x, y, c, post)

    # rendering ---------------------------------------------------------------
    def render(self) -> Image.Image:
        W, H = self.w, self.h
        parts = self.parts
        if self.floor is not None:
            for p in parts:
                if p.shape.mask[self.floor:].any():
                    p.shape = p.shape.copy()
                    p.shape.mask[self.floor:] = False
        order = sorted(range(len(parts)), key=lambda i: (parts[i].z, i))
        rank = np.full(len(parts) + 1, -1)
        owner = np.full((H, W), -1, int)
        idx = np.zeros((H, W), int)
        for r, i in enumerate(order):
            p = parts[i]
            m = p.shape.mask
            if not m.any():
                continue
            owner[m] = i
            idx[m] = p.indices()[m]
            rank[i] = r
        rank_map = np.where(owner >= 0, rank[owner], -1)

        # point lights (lanterns, embers): brighten nearby receiving parts
        if self.glows:
            X, Y = _grid(W, H)
            boost = np.zeros((H, W), int)
            for (gx, gy, gr, steps) in self.glows:
                d = np.sqrt((X - gx) ** 2 + (Y - gy) ** 2)
                for k in range(1, steps + 1):
                    boost = np.maximum(boost, np.where(d <= gr * (steps - k + 1) / steps, k, 0))
            hi_arr = np.array([p.hi for p in parts] + [0])
            gl_arr = np.array([p.glow and p.idx is None for p in parts] + [False])
            ok = (owner >= 0) & gl_arr[np.maximum(owner, 0)]
            if self.glow_unit != 1:
                k_arr = np.array([p.k for p in parts] + [1])
                kk = k_arr[np.maximum(owner, 0)]
                boost = -((-boost * kk) // self.glow_unit)     # ceil: HD parts get every step
            idx = np.where(ok, np.minimum(idx + boost, hi_arr[np.maximum(owner, 0)]), idx)

        # 3. orphan cleanup inside each part (a lone shade pixel surrounded by one other shade)
        for _ in range(2):
            same = [(nb(owner, dx, dy, -2) == owner) for dx, dy in N4]
            vals = [nb(idx, dx, dy, -99) for dx, dy in N4]
            cnt_same = sum(s.astype(int) for s in same)
            changed = False
            for k in range(4):
                v = vals[k]
                agree = np.ones((H, W), bool)
                for j in range(4):
                    agree &= (~same[j]) | (vals[j] == v)
                cand = (owner >= 0) & same[k] & agree & (cnt_same >= 3) & (v != idx)
                if self.parts and cand.any():
                    idx[cand] = v[cand]
                    changed = True
            if not changed:
                break

        # 4. cast shadows (front part shades the part behind it, toward lower-right)
        shadow = np.zeros((H, W), bool)
        lo_arr = np.array([p.lo for p in parts] + [0])
        cast_arr = np.array([p.cast for p in parts] + [0])
        recv_arr = np.array([p.recv for p in parts] + [False])
        grp = [p.group for p in parts]
        grp_id = {}
        gid_arr = np.array([grp_id.setdefault(g, len(grp_id)) for g in grp] + [-5])
        for (dx, dy, need) in _CAST_OFFSETS[self.scale]:
            o2 = nb(owner, dx, dy, -1)
            r2 = np.where(o2 >= 0, rank[o2], -1)
            cond = (owner >= 0) & (o2 >= 0) & (r2 > rank_map)
            cond &= cast_arr[o2] >= need
            cond &= recv_arr[owner]
            cond &= gid_arr[o2] != gid_arr[np.maximum(owner, 0)]
            shadow |= cond
        step = np.array([p.k for p in parts] + [1])[np.maximum(owner, 0)]
        idx = np.where(shadow, np.maximum(idx - step, lo_arr[np.maximum(owner, 0)]), idx)

        if self.rim_dark:
            inside = owner >= 0
            edge = np.zeros((H, W), bool)
            for dx, dy in ((1, 0), (0, 1), (1, 1)):
                edge |= inside & ~nb(inside, dx, dy, False)
            ok_arr = np.array([p.idx is None and p.glow for p in parts] + [False])
            edge &= ok_arr[np.maximum(owner, 0)]
            dk = np.array([p.k for p in parts] + [1])[np.maximum(owner, 0)] * self.rim_dark
            idx = np.where(edge, np.maximum(idx - dk, lo_arr[np.maximum(owner, 0)]), idx)

        # compose colours
        out = np.zeros((H, W, 4), np.uint8)
        for i, p in enumerate(parts):
            m = owner == i
            if not m.any():
                continue
            pal = np.array(RAMPS[p.ramp], np.uint8)
            out[m] = pal[np.clip(idx[m], 0, len(pal) - 1)]

        # 5. interior contours
        for i, p in enumerate(parts):
            if p.contour is None:
                continue
            m = owner == i
            if not m.any():
                continue
            cc = p.contour_col if p.contour_col is not None else col(p.ramp, p.contour)
            touch = np.zeros((H, W), bool)
            dirs = N4
            if p.contour_dirs is not None:
                side = {"r": (-1, 0), "l": (1, 0), "b": (0, -1), "t": (0, 1)}
                dirs = [side[d] for d in p.contour_dirs]
            for dx, dy in dirs:
                touch |= nb(m, dx, dy, False)
            behind = touch & (owner >= 0) & (owner != i) & (rank_map < rank[i])
            behind &= gid_arr[np.maximum(owner, 0)] != gid_arr[i]
            out[behind] = cc

        # 6. decals
        for (x, y, c) in self.decals:
            if 0 <= x < W and 0 <= y < H:
                out[y, x] = c
                if owner[y, x] < 0:
                    owner[y, x] = len(parts)  # anonymous filled pixel
        for (x, y) in self.erase:
            if 0 <= x < W and 0 <= y < H:
                out[y, x] = (0, 0, 0, 0)
                owner[y, x] = -1

        # 7. external outline
        if self.outline_on:
            filled = out[:, :, 3] > 0
            best_l = np.full((H, W), 1e9)
            best_c = np.zeros((H, W, 4), np.uint8)
            oc_arr = np.array([p.oc for p in parts] + [col("ink", 1)], np.uint8)
            ol_arr = np.array([p.outline for p in parts] + [True])
            lum_arr = np.array([lum(c) for c in oc_arr])
            for dx, dy in N4:
                o2 = nb(owner, dx, dy, -1)
                f2 = nb(filled, dx, dy, False)
                ok = (~filled) & f2 & (o2 >= 0)
                ok &= ol_arr[np.maximum(o2, 0)]
                l2 = lum_arr[np.maximum(o2, 0)]
                better = ok & (l2 < best_l)
                best_l = np.where(better, l2, best_l)
                best_c[better] = oc_arr[np.maximum(o2, 0)][better]
            edge = best_l < 1e8
            out[edge] = best_c[edge]
            if self.outline_shadow:
                # second outline pixel on the shadow side (right / below), or all round with
                # outline_all, same colour as the outline it extends: silhouettes keep their
                # weight when drawn at 2x density (never onto the 1px border or below the floor)
                dirs = ((-1, 0), (0, -1)) if not self.outline_all else ((-1, 0), (0, -1), (1, 0), (0, 1))
                for _ in range(self.outline_shadow):
                    filled = out[:, :, 3] > 0
                    grow = np.zeros((H, W), bool)
                    src = np.zeros((H, W, 4), np.uint8)
                    for dx, dy in dirs:
                        e2 = nb(edge, dx, dy, False)
                        c2 = nb(out, dx, dy, 0)
                        g = (~filled) & e2 & ~grow
                        src[g] = c2[g]
                        grow |= g
                    grow[:, -1] = False
                    grow[-1, :] = False
                    grow[:, 0] = False
                    grow[0, :] = False
                    if self.floor is not None:
                        grow[self.floor + 1:] = False
                    out[grow] = src[grow]
                    edge = grow

        if self.outline_fn is not None:
            out = self.outline_fn(out, owner)

        m = self.post_margin
        for (x, y, c) in self.post:
            if m <= x < W - m and m <= y < H - m:
                out[y, x] = c
        out[out[:, :, 3] < 128] = 0
        out[:, :, 3] = np.where(out[:, :, 3] > 0, 255, 0)
        return Image.fromarray(out, "RGBA")


# --------------------------------------------------------------------------
# frame utilities


def check_frame(img: Image.Image, name: str = "") -> None:
    a = np.array(img)[:, :, 3]
    if a[0].any() or a[-1].any() or a[:, 0].any() or a[:, -1].any():
        raise ValueError(f"{name}: frame touches the 1px border")


def bbox(img: Image.Image):
    a = np.array(img)[:, :, 3] > 0
    ys, xs = np.nonzero(a)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def flip(img: Image.Image) -> Image.Image:
    return img.transpose(Image.FLIP_LEFT_RIGHT)


def shift_img(img: Image.Image, dx: int, dy: int) -> Image.Image:
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (dx, dy))
    return out


def lerp(a, b, t):
    return a + (b - a) * t


def lerp2(p, q, t):
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def bezier(pts, n):
    """Sample a polyline of n points along a Bezier curve with control points pts."""
    out = []
    k = len(pts) - 1
    for s in range(n):
        t = s / (n - 1)
        x = y = 0.0
        for i, (px, py) in enumerate(pts):
            b = math.comb(k, i) * (t ** i) * ((1 - t) ** (k - i))
            x += b * px
            y += b * py
        out.append((x, y))
    return out
