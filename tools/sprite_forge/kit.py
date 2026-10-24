"""Shared helpers on top of pix: a canvas-bound shape factory and common details."""

from __future__ import annotations

import math

import numpy as np

import pix
from pix import Figure, Shape, col


class Canvas:
    """Binds shape constructors to one frame size so rigs read cleanly."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.fig = Figure(w, h)

    # shapes
    def ell(self, cx, cy, rx, ry, rz=None, angle=0.0, smooth=True) -> Shape:
        return pix.ellipse(self.w, self.h, cx, cy, rx, ry, rz, angle, smooth)

    def circ(self, cx, cy, r, rz=None) -> Shape:
        return pix.ellipse(self.w, self.h, cx, cy, r, r, rz)

    def tube(self, pts, radii, rz_scale=1.0) -> Shape:
        return pix.tube(self.w, self.h, pts, radii, rz_scale)

    def poly(self, pts, bevel=2.5, dome=False) -> Shape:
        return pix.poly(self.w, self.h, pts, bevel, dome)

    def pmask(self, pts) -> np.ndarray:
        return pix.polygon_mask(self.w, self.h, pts)

    def rect(self, x0, y0, x1, y1) -> np.ndarray:
        return pix.rect_mask(self.w, self.h, x0, y0, x1, y1)

    def rrect(self, x0, y0, x1, y1, r=1.5, bevel=2.0, dome=False) -> Shape:
        return pix.rrect(self.w, self.h, x0, y0, x1, y1, r, bevel, dome)

    def from_mask(self, m, bevel=2.5, dome=False) -> Shape:
        return pix.from_mask(m, bevel, dome)

    def ascii(self, rows, ox, oy, chars="#") -> np.ndarray:
        return pix.ascii_mask(self.w, self.h, rows, ox, oy, chars)

    def empty(self) -> Shape:
        return pix.empty(self.w, self.h)

    def below(self, pts) -> np.ndarray:
        """Mask of pixels below a polyline (y greater than the line), spanning the line's x range."""
        X, Y = pix._grid(self.w, self.h)
        m = np.zeros((self.h, self.w), bool)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x1 == x0:
                continue
            lo, hi = min(x0, x1), max(x0, x1)
            t = (X - x0) / (x1 - x0)
            yl = y0 + t * (y1 - y0)
            m |= (X >= lo) & (X < hi) & (Y > yl)
        return m

    def above(self, pts) -> np.ndarray:
        X, Y = pix._grid(self.w, self.h)
        m = np.zeros((self.h, self.w), bool)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x1 == x0:
                continue
            lo, hi = min(x0, x1), max(x0, x1)
            t = (X - x0) / (x1 - x0)
            yl = y0 + t * (y1 - y0)
            m |= (X >= lo) & (X < hi) & (Y < yl)
        return m

    def right_of(self, pts) -> np.ndarray:
        """Pixels right of a polyline given top-to-bottom as (x, y) points (rows outside its y-span: none)."""
        X, Y = pix._grid(self.w, self.h)
        m = np.zeros((self.h, self.w), bool)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if y1 == y0:
                continue
            lo, hi = min(y0, y1), max(y0, y1)
            t = (Y - y0) / (y1 - y0)
            xl = x0 + t * (x1 - x0)
            m |= (Y >= lo) & (Y < hi) & (X > xl)
        return m

    def halfplane(self, p0, p1) -> np.ndarray:
        """Pixels on the left side of the directed line p0->p1 (image coords)."""
        X, Y = pix._grid(self.w, self.h)
        (x0, y0), (x1, y1) = p0, p1
        return ((x1 - x0) * (Y - y0) - (y1 - y0) * (X - x0)) < 0

    def disk(self, cx, cy, r) -> np.ndarray:
        X, Y = pix._grid(self.w, self.h)
        return (X - cx) ** 2 + (Y - cy) ** 2 <= r * r

    # parts
    def add(self, shape, ramp, base=3, z=0.0, **kw):
        return self.fig.add(shape, ramp, base, z, **kw)

    def dot(self, x, y, c, post=False):
        self.fig.dot(x, y, c, post)

    def dots(self, pts, c, post=False):
        for (x, y) in pts:
            self.fig.dot(x, y, c, post)

    def grid(self, rows: list[str], ox: int, oy: int, pal: dict, post=False):
        """Stamp a hand-authored pixel grid. '.' or ' ' = skip."""
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch in ". ":
                    continue
                c = pal[ch]
                if c is None:
                    self.fig.erase.append((ox + i, oy + j))
                else:
                    self.fig.dot(ox + i, oy + j, c, post)

    def render(self):
        return self.fig.render()


# --------------------------------------------------------------------------
# glowing ember (Emberlyn's tail coal, lantern flames)


def flame(cv: Canvas, x: float, y: float, r: float = 2.4, flick: int = 0, lean: float = 0.0,
          tongue: float = 3.0, dim: int = 0, z: float = 50, glow_r: float = 7.0, ring=None,
          oc_index: int = 1):
    """A glowing coal at (x, y) with a flickering flame tongue rising above it.

    flick: 0..3 selects the tongue variant; tongue: base tongue height in px.
    dim:   0 = full blaze, 1 = weak, 2 = nearly out (KO).
    """
    W, H = cv.w, cv.h
    X, Y = pix._grid(W, H)
    # tongue heights vary 1-3px between variants, with a slight sway
    var = [(0.0, 0.0), (1.2, 0.6), (2.2, -0.4), (0.8, -0.8)][flick % 4]
    th = max(0.0, tongue + var[0] - dim * 1.6)
    lx = lean + var[1]
    coal = (X - x) ** 2 / (r * r) + (Y - y) ** 2 / (r * r * 0.92) <= 1.0
    m = coal.copy()
    if th > 0.3:
        tip = (x + lx, y - r - th)
        # teardrop: interpolate half width from coal radius to 0 at the tip
        ty = (Y - (y - 0.3)) / (tip[1] - (y - 0.3))  # 0 at coal centre, 1 at tip
        cxl = x + lx * np.clip(ty, 0, 1)
        half = r * 0.95 * np.clip(1.0 - ty, 0, 1) ** 0.85
        tong = (ty >= 0) & (ty <= 1.0) & (np.abs(X - cxl) <= half + 0.05)
        m |= tong
    m = pix.despike(m)
    # brightness by distance to a hot core slightly below centre
    d = np.sqrt(((X - x) / max(r, 0.5)) ** 2 + ((Y - (y + 0.2)) / (max(r, 0.5) * 1.25)) ** 2)
    hgt = np.clip((y - Y) / max(th + r, 1.0), 0, 1)   # 0 at core level -> 1 at tip
    idx = np.full((H, W), 4)
    idx[d < 0.95] = 5
    idx[d < 0.55] = 6
    idx[(hgt > 0.55) & (idx > 4)] = 5
    idx[(hgt > 0.8)] = 4
    if dim == 1:
        idx = np.clip(idx - 1, 3, 5)
    elif dim >= 2:
        idx = np.clip(idx - 2, 2, 4)
    shape = Shape(m)
    p = cv.add(shape, "ember", 4, z, idx=idx, oc=col("ember", oc_index + (1 if dim >= 2 else 0)), cast=0, recv=False, glow=False)
    if glow_r > 0 and dim < 2:
        cv.fig.glows.append((x, y, glow_r * (0.7 if dim else 1.0), 1))
    return p


# --------------------------------------------------------------------------
# local rig transform: lets a whole rig rotate/translate (rearing, tipping over)


class Xf:
    """local -> screen: p' = R(rot) (p - pivot) + pivot + (ox, oy)."""

    def __init__(self, ox=0.0, oy=0.0, rot=0.0, px=24.0, py=44.0):
        self.ox, self.oy, self.rot, self.px, self.py = ox, oy, rot, px, py
        self.c, self.s = math.cos(rot), math.sin(rot)

    def pt(self, x, y):
        dx, dy = x - self.px, y - self.py
        return (self.px + self.c * dx - self.s * dy + self.ox, self.py + self.s * dx + self.c * dy + self.oy)

    def pts(self, ps):
        return [self.pt(x, y) for (x, y) in ps]

    def local_grid(self, w, h):
        X, Y = pix._grid(w, h)
        dx, dy = X - self.px - self.ox, Y - self.py - self.oy
        return (self.px + self.c * dx + self.s * dy, self.py - self.s * dx + self.c * dy)


def ell_x(cv: Canvas, xf: Xf, cx, cy, rx, ry, rz=None, angle=0.0, smooth=True):
    x, y = xf.pt(cx, cy)
    return cv.ell(x, y, rx, ry, rz, angle + xf.rot, smooth)


def tube_x(cv: Canvas, xf: Xf, pts, radii, rz_scale=1.0):
    return cv.tube(xf.pts(pts), radii, rz_scale)


def rim_highlight(part, neighbor_masks, steps=1, amount=1):
    """Brighten the pixels of `part` that border any of `neighbor_masks` (raised plate edges)."""
    idx = part.indices().copy()
    m = part.shape.mask
    edge = np.zeros_like(m)
    for nm in neighbor_masks:
        grown = nm.copy()
        for _ in range(steps):
            g = grown.copy()
            for dx, dy in pix.N4:
                g |= pix.nb(grown, dx, dy, False)
            grown = g
        edge |= grown & m
    idx[edge] = np.minimum(idx[edge] + amount, part.hi)
    part.idx = idx
    return part
