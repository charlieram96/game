"""Shared helpers on top of pix: a canvas-bound shape factory and common details."""

from __future__ import annotations

import math

import numpy as np

import pix
from pix import HD_LEVELS, RAMPS, Figure, Shape, col


class Canvas:
    """Binds shape constructors to one frame size so rigs read cleanly.

    Rigs work in *design* coordinates (the 48px layout). `s` is the resolution
    factor: Canvas(48, 48, s=2) rasterises a 96x96 frame from the same rig
    numbers, so geometry scales exactly and only hand-placed pixel decals
    (cv.grid / cv.dot, which stay in raster pixels) need 2x authoring.
    With `hd=True`, materials that have a half-step `<ramp>_hd` version in the
    master palette are painted with it (softer, multi-shade ramps); rig code
    keeps using original shade numbers (base=3, offset=-1, contour=1 ...).
    """

    def __init__(self, w: int, h: int, s: int = 1, hd: bool = False):
        self.s = s
        self.dw, self.dh = w, h
        self.w, self.h = int(w * s), int(h * s)
        self.hd = hd
        self.fig = Figure(self.w, self.h, scale=s)
        if hd:
            self.fig.glow_unit = 2
            self.fig.post_margin = 1    # effects may run off-frame; keep the contract's 1px clear border
        self._XY = None

    # design-space pixel centres
    @property
    def XY(self):
        if self._XY is None:
            X, Y = pix._grid(self.w, self.h)
            self._XY = (X / self.s, Y / self.s) if self.s != 1 else (X, Y)
        return self._XY

    def px(self, v: float) -> int:
        """Design coordinate -> raster pixel index."""
        return int(math.floor(v * self.s))

    # shapes
    def ell(self, cx, cy, rx, ry, rz=None, angle=0.0, smooth=True) -> Shape:
        s = self.s
        return pix.ellipse(self.w, self.h, cx * s, cy * s, rx * s, ry * s, None if rz is None else rz * s, angle, smooth)

    def circ(self, cx, cy, r, rz=None) -> Shape:
        s = self.s
        return pix.ellipse(self.w, self.h, cx * s, cy * s, r * s, r * s, None if rz is None else rz * s)

    def tube(self, pts, radii, rz_scale=1.0) -> Shape:
        s = self.s
        if s != 1:
            pts = [(x * s, y * s) for (x, y) in pts]
            radii = radii * s if np.isscalar(radii) else [r * s for r in radii]
        return pix.tube(self.w, self.h, pts, radii, rz_scale)

    def poly(self, pts, bevel=2.5, dome=False) -> Shape:
        s = self.s
        if s != 1:
            pts = [(x * s, y * s) for (x, y) in pts]
        return pix.poly(self.w, self.h, pts, bevel * s, dome)

    def pmask(self, pts) -> np.ndarray:
        s = self.s
        if s != 1:
            pts = [(x * s, y * s) for (x, y) in pts]
        return pix.polygon_mask(self.w, self.h, pts)

    def rect(self, x0, y0, x1, y1) -> np.ndarray:
        s = self.s
        if s == 1:
            return pix.rect_mask(self.w, self.h, x0, y0, x1, y1)
        return pix.rect_mask(self.w, self.h, int(x0) * s, int(y0) * s, int(x1) * s + s - 1, int(y1) * s + s - 1)

    def rrect(self, x0, y0, x1, y1, r=1.5, bevel=2.0, dome=False) -> Shape:
        s = self.s
        return pix.rrect(self.w, self.h, x0 * s, y0 * s, x1 * s, y1 * s, r * s, bevel * s, dome)

    def from_mask(self, m, bevel=2.5, dome=False) -> Shape:
        return pix.from_mask(m, bevel * self.s, dome)

    def ascii(self, rows, ox, oy, chars="#") -> np.ndarray:
        return pix.ascii_mask(self.w, self.h, rows, ox, oy, chars)

    def empty(self) -> Shape:
        return pix.empty(self.w, self.h)

    def below(self, pts, zig=None) -> np.ndarray:
        """Mask of pixels below a polyline (y greater than the line), spanning the line's x range.

        zig=(amp, period[, phase]) in design px turns the border into a sawtooth of
        fur tufts hanging down from the part above (e.g. russet back over a cream belly).
        """
        X, Y = self.XY
        m = np.zeros((self.h, self.w), bool)
        if zig is not None:
            amp, period = zig[0], zig[1]
            ph = zig[2] if len(zig) > 2 else 0.0
            f = (X / period + ph) % 1.0
            off = amp * (1.0 - np.abs(2.0 * f - 1.0) ** 0.8)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x1 == x0:
                continue
            lo, hi = min(x0, x1), max(x0, x1)
            t = (X - x0) / (x1 - x0)
            yl = y0 + t * (y1 - y0)
            if zig is not None:
                yl = yl + off
            m |= (X >= lo) & (X < hi) & (Y > yl)
        return m

    def above(self, pts) -> np.ndarray:
        X, Y = self.XY
        m = np.zeros((self.h, self.w), bool)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x1 == x0:
                continue
            lo, hi = min(x0, x1), max(x0, x1)
            t = (X - x0) / (x1 - x0)
            yl = y0 + t * (y1 - y0)
            m |= (X >= lo) & (X < hi) & (Y < yl)
        return m

    def right_of(self, pts, zig=None) -> np.ndarray:
        """Pixels right of a polyline given top-to-bottom as (x, y) points (rows outside its y-span: none).

        zig=(amp, period[, phase]) pushes the border right in a sawtooth (fur tufts of the
        left part reaching over the right one)."""
        X, Y = self.XY
        m = np.zeros((self.h, self.w), bool)
        if zig is not None:
            amp, period = zig[0], zig[1]
            ph = zig[2] if len(zig) > 2 else 0.0
            f = (Y / period + ph) % 1.0
            off = amp * (1.0 - np.abs(2.0 * f - 1.0) ** 0.8)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if y1 == y0:
                continue
            lo, hi = min(y0, y1), max(y0, y1)
            t = (Y - y0) / (y1 - y0)
            xl = x0 + t * (x1 - x0)
            if zig is not None:
                xl = xl + off
            m |= (Y >= lo) & (Y < hi) & (X > xl)
        return m

    def halfplane(self, p0, p1) -> np.ndarray:
        """Pixels on the left side of the directed line p0->p1 (image coords)."""
        X, Y = self.XY
        (x0, y0), (x1, y1) = p0, p1
        return ((x1 - x0) * (Y - y0) - (y1 - y0) * (X - x0)) < 0

    def disk(self, cx, cy, r) -> np.ndarray:
        X, Y = self.XY
        return (X - cx) ** 2 + (Y - cy) ** 2 <= r * r

    def glow(self, x, y, r, steps=1):
        """Warm point light (design coords). On HD canvases each step is a half shade."""
        s = self.s
        self.fig.glows.append((x * s, y * s, r * s, steps * (2 if self.hd else 1)))

    # parts
    def add(self, shape, ramp, base=3, z=0.0, **kw):
        if self.hd and (ramp + "_hd") in RAMPS:
            kw = dict(kw)
            ramp = ramp + "_hd"
            base = int(round(base * 2))     # half-step bases (e.g. 3.5) land on the in-between shade
            kw["lo"] = kw.get("lo", 1) * 2
            if kw.get("hi") is not None:
                kw["hi"] = kw["hi"] * 2
            if kw.get("offset"):
                kw["offset"] = kw["offset"] * 2
            if kw.get("contour") is not None:
                kw["contour"] = kw["contour"] * 2
            if kw.get("idx") is not None:
                kw["idx"] = np.asarray(kw["idx"]) * 2
            if kw.get("bands") is None and kw.get("levels") is None:
                kw["levels"] = HD_LEVELS
            kw["k"] = 2
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
    X, Y = cv.XY
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
        cv.glow(x, y, glow_r * (0.7 if dim else 1.0), 1)
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

    def local(self, cv: "Canvas"):
        """Rig-local design coordinates of every pixel centre of a (possibly scaled) canvas."""
        X, Y = cv.XY
        dx, dy = X - self.px - self.ox, Y - self.py - self.oy
        return (self.px + self.c * dx + self.s * dy, self.py - self.s * dx + self.c * dy)


def ell_x(cv: Canvas, xf: Xf, cx, cy, rx, ry, rz=None, angle=0.0, smooth=True):
    x, y = xf.pt(cx, cy)
    return cv.ell(x, y, rx, ry, rz, angle + xf.rot, smooth)


def tube_x(cv: Canvas, xf: Xf, pts, radii, rz_scale=1.0):
    return cv.tube(xf.pts(pts), radii, rz_scale)


# --------------------------------------------------------------------------
# procedural texture (2x sprites): deterministic hash + fur / grain fields


def hash01(a, seed: int = 0) -> np.ndarray:
    """Deterministic integer hash -> [0, 1) (same result on every machine)."""
    a = np.asarray(a)
    shp = a.shape
    x = np.atleast_1d(a).astype(np.int64).ravel() & 0xFFFFFFFF
    x = x.astype(np.uint64)
    m = np.uint64(0xFFFFFFFF)
    x = (x * np.uint64(0x27D4EB2D) + np.uint64((seed * 0x165667B1 + 0x9E3779B9) & 0xFFFFFFFF)) & m
    x ^= x >> np.uint64(15)
    x = (x * np.uint64(0x85EBCA6B)) & m
    x ^= x >> np.uint64(13)
    x = (x * np.uint64(0xC2B2AE35)) & m
    x ^= x >> np.uint64(16)
    out = (x & np.uint64(0xFFFFFF)).astype(np.float64) / float(0x1000000)
    return out.reshape(shp) if shp else float(out[0])


def fur_tex(S, R, width=3.0, seg=7.0, amp=0.08, seed=0, bias=0.45):
    """Light-term perturbation that breaks smooth shade borders into fur clumps.

    S runs along the fur (root -> tip), R across it, both in raster pixels (e.g.
    from pix.tube_coords, so the pattern rides on the limb). Strands `width` px
    wide are cut into staggered clumps `seg` px long; a clump is brightest on
    its centre line near the root and fades toward its tip, so band borders
    become pointed tufts lying in the fur direction.
    """
    row = np.floor(R / width)
    fr = R / width - row
    u = S / seg + hash01(row, seed)
    si = np.floor(u)
    fu = u - si
    ridge = 1.0 - np.abs(2.0 * fr - 1.0)
    shape = ridge * (1.0 - 0.6 * fu)
    jit = hash01(row * 7919 + si * 104729, seed + 1) - 0.5
    return amp * (shape - bias + 0.5 * jit)


def strand_tex(S, R, width=1.6, length=6.0, amp=0.18, seed=0):
    """Hair strands: 1-2px wide, `length` px long streaks along S, each randomly
    lighter or darker (tapered at both ends). Added to the light term, they turn
    shade borders into interleaved strands; flat areas stay clean unless amp is large.
    """
    row = np.floor(R / width)
    u = S / length + hash01(row, seed)
    si = np.floor(u)
    fu = u - si
    val = hash01(row * 7919 + si * 104729, seed + 1) * 2.0 - 1.0
    env = np.sin(np.clip(fu, 0.0, 1.0) * np.pi) ** 0.5
    return amp * val * env


def local_uv(cv: Canvas, cx, cy, angle=0.0):
    """Raster-pixel coordinates (along, across) relative to a design point, rotated by angle."""
    X, Y = pix._grid(cv.w, cv.h)
    dx, dy = X - cx * cv.s, Y - cy * cv.s
    ca, sa = math.cos(angle), math.sin(angle)
    return dx * ca + dy * sa, -dx * sa + dy * ca


def tube_uv(cv: Canvas, pts):
    """(arc length, signed distance) in raster pixels along a design-space polyline."""
    s = cv.s
    return pix.tube_coords(cv.w, cv.h, [(x * s, y * s) for (x, y) in pts])


# --------------------------------------------------------------------------
# effect decals for 2x creature sheets (design coordinates; drawn in the post pass)


def _post(cv: Canvas, x, y, c):
    cv.fig.post.append((int(round(x)), int(round(y)), c))


def fx_dust(cv: Canvas, puffs, z=30.0):
    """Kicked-up dust: pale clouds with lit tops and a light sandy outline, plus grit."""
    for k, (x, y, r) in enumerate(puffs):
        j = [float(hash01(k * 5 + i, 21)) for i in range(4)]
        blob = cv.ell(x, y, r, r * 0.78)
        blob = blob | cv.ell(x - r * (0.65 + 0.2 * j[0]), y + r * 0.3, r * (0.5 + 0.2 * j[1]), r * 0.5)
        blob = blob | cv.ell(x + r * (0.6 + 0.2 * j[2]), y + r * 0.32, r * (0.45 + 0.2 * j[3]), r * 0.45)
        blob = blob | cv.ell(x + r * 0.15, y - r * 0.55, r * 0.45, r * 0.38)
        cv.add(blob, "cloth_cream", 4.5, z + k * 0.01, group=f"dust{k}", cast=0, recv=False, glow=False,
               oc=col("sand", 3), light=1.2, lo=3, hi=5)
        for j in range(3):
            gx = x + (float(hash01(k * 11 + j, 3)) - 0.5) * r * 3.2
            gy = y - r * (0.5 + float(hash01(k * 13 + j, 4)) * 1.1)
            cv.dot(int(math.floor(gx * cv.s)), int(math.floor(gy * cv.s)), col("sand", 3 if j % 2 else 4), post=True)


def fx_sparks(cv: Canvas, pts, hot=None, warm=None):
    hot = hot or col("ember", 6)
    warm = warm or col("ember", 5)
    for (x, y, sz) in pts:
        xi, yi = int(math.floor(x * cv.s)), int(math.floor(y * cv.s))
        if sz >= 2:
            cv.grid([".s.", "sSs", ".s."], xi - 1, yi - 1, {"s": warm, "S": hot}, post=True)
        elif sz == 1:
            cv.grid(["Ss", "ss"], xi, yi, {"S": hot, "s": warm}, post=True)
        else:
            cv.dot(xi, yi, warm, post=True)


def fx_speed(cv: Canvas, lines):
    """Speed lines (x, y, length[, 'h'|'v'|'^']) in design px: faint at the trailing end.
    'h' trails to the left (dash to the right), 'v' trails upward (dash toward the camera),
    '^' trails downward (dash away)."""
    ramp = [col("cream", 2), col("cream", 3), col("cream", 4)]
    for ln in lines:
        x, y, L = ln[:3]
        kind = ln[3] if len(ln) > 3 else "h"
        x0, y0 = int(math.floor(x * cv.s)), int(math.floor(y * cv.s))
        n = max(2, int(L * cv.s))
        for i in range(n):
            t = i / (n - 1)
            c = ramp[0] if t < 0.3 else (ramp[1] if t < 0.7 else ramp[2])
            if kind == "h":
                _post(cv, x0 + i, y0, c)
            elif kind == "v":
                _post(cv, x0, y0 + i, c)
            else:
                _post(cv, x0, y0 + n - 1 - i, c)


def fx_impact(cv: Canvas, x, y, r, phase=0):
    """Impact flash at (x, y): phase 0 = white-hot star with long rays, phase 1 = broken
    shock ring with ray stubs flying outward."""
    s = cv.s
    cx, cy, R = x * s, y * s, r * s
    core, hot, warm = col("cream", 4), col("gold", 5), col("gold", 4)
    if phase == 0:
        for k in range(8):
            a = k * math.pi / 4 + 0.26
            L = R if k % 2 == 0 else R * 0.55
            n = max(2, int(L))
            for i in range(n):
                t = i / (n - 1)
                c = core if t < 0.4 else (hot if t < 0.75 else warm)
                px_, py_ = cx + i * math.cos(a), cy + i * math.sin(a)
                _post(cv, px_, py_, c)
                if t < 0.45 and k % 2 == 0:
                    _post(cv, px_ - math.sin(a), py_ + math.cos(a), c)
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                if abs(dx) + abs(dy) <= 3:
                    _post(cv, cx + dx, cy + dy, core)
    else:
        # the star bursts apart: rays detach from the centre and fly outward in two dashes
        for k in range(8):
            a = k * math.pi / 4 + 0.26 + (math.pi / 8 if k % 2 else 0.0)
            L = R * (1.2 if k % 2 == 0 else 0.85)
            r0 = R * 0.42
            n = max(2, int(L - r0))
            for i in range(n):
                t = i / (n - 1)
                if 0.42 < t < 0.58:
                    continue
                c = core if t < 0.3 else (hot if t < 0.75 else warm)
                _post(cv, cx + (r0 + i) * math.cos(a), cy + (r0 + i) * math.sin(a), c)
        for k in range(6):
            a = k * math.pi / 3 + 0.5
            rr = R * (0.7 + 0.25 * (k % 2))
            _post(cv, cx + rr * math.cos(a), cy + rr * math.sin(a), hot)
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                if abs(dx) + abs(dy) <= 1:
                    _post(cv, cx + dx, cy + dy, col("cream", 3))


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
    idx[edge] = np.minimum(idx[edge] + amount * part.k, part.hi)
    part.idx = idx
    return part
