"""Stoneback -- heavy stone-element kith (96x96 frames, pivot 48,88, 48 px/unit).

A compact pangolin/armadillo-like quadruped: overlapping slate plates down its
back, a thick moss ridge with tiny flowers, stubby warm-hide legs, a broad
blunt snout, small glowing amber eyes under a heavy stone brow and a short tail
ending in a stone club. Stubborn and sleepy; it can curl into a rolling ball.

Drawn at 2x like Emberlyn: the rig keeps its 48px design coordinates and is
rasterised by kit.Canvas(48, 48, s=2, hd=True). The extra resolution goes into
half-step stone/hide/moss ramps, bevelled plate rims with grain and chips, a
tufted moss ridge with real little flowers, hide wrinkles and claws, and a
true 3D rolling ball (plates are wedges around the rolling axis, the moss ridge
runs along the spine) so the charge can roll in every direction.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, replace

import numpy as np

import pix
from kit import (Canvas, Xf, ell_x, fx_dust, fx_impact, fx_sparks, fx_speed, hash01, local_uv, rim_highlight,
                 strand_tex, tube_x)
from pix import col

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common.sheet import SheetBuilder  # noqa: E402
from portraits import installed_by_art_forge  # noqa: E402

S = 2                    # raster pixels per design pixel
DW = DH = 48             # design frame (rig coordinates)
W, H = DW * S, DH * S    # raster frame
PIVOT = (24 * S, 44 * S)
PPU = 24 * S
GROUND = 43.0
STONE, HIDE, MOSS, GMOSS = "stone", "stone_warm", "moss", "glow_moss"

EYE = col("ember", 5)
EYE_HI = col("ember", 6)
EYE_LO = col("ember", 4)
EYE_RIM = col("ember", 3)
LID = col("stone", 1)
NOSE = col("stone_warm", 0)
NOSE_HI = col("stone_warm", 2)
MOUTH = col("stone_warm", 1)
CLAW = col("cream", 2)
CLAW_HI = col("cream", 3)
PETAL = col("cloth_cream", 5)
PETAL_SH = col("cloth_cream", 3)
PETAL_Y = col("gold", 5)
PETAL_YS = col("gold", 3)
POLLEN = col("gold", 4)
POLLEN_O = col("ember", 4)
STEAM = col("cloth_cream", 4)
STEAM2 = col("cloth_cream", 3)
SMEAR = col("cloth_cream", 5)
SMEAR2 = col("cloth_cream", 3)
BUB = col("water", 5)
BUB_HI = col("water", 6)
BUB_LO = col("water", 4)
CRACK = col("stone", 1)
CRACK_HI = col("stone", 4)
CHIP = (col("stone", 3), col("stone", 4), col("stone_warm", 3))


@dataclass
class Pose:
    x: float = 0.0
    y: float = 0.0
    lift: float = 0.0
    bob: float = 0.0
    rot: float = 0.0                 # whole-rig rotation (radians), about (rpx, rpy)
    rpx: float = 24.0
    rpy: float = 44.0
    head: tuple = (0.0, 0.0)
    tuck: float = 0.0                # 0..1 head pulled under the shell
    feet: tuple = ((0, 0), (0, 0), (0, 0), (0, 0))
    eyes: str = "sleepy"             # sleepy | open | closed | squint | swirl | happy | fierce
    mouth: str = "closed"            # closed | open | grit
    tail: tuple = (0.0, 0.0)
    plates: float = 0.0              # raised plates (guard)
    glow: int = 0                    # moss glow level (focus) 0..2
    smear: tuple = ()
    rock: tuple = ()                 # (x, y) of a lifted rock chunk
    dust: tuple = ()                 # dust puffs: (x, y) small, or (x, y, r)
    stars: int = -1
    steam: bool = False
    breath: float = 0.0              # shell swell (px)
    feet_rot: bool = False           # feet follow the body rotation (tipping over)
    bubble: int = 0                  # sleep bubble size (0 none)
    curl_tail: bool = False          # tail wrapped around the front (sleeping)
    sparks: tuple = ()
    speed: tuple = ()
    impact: tuple = ()
    sway: float = 0.0                # flower sway (ready)


def canvas() -> Canvas:
    cv = Canvas(DW, DH, s=S, hd=True)
    cv.fig.floor = PIVOT[1]         # nothing fills the ground row: planted feet's outline lands on the pivot
    cv.fig.rim_dark = 1             # weight on the shadow side of the silhouette
    cv.fig.outline_shadow = 1       # one extra outline ring ...
    cv.fig.outline_all = True       # ... all round: 2px = the 1x sprites' 1px outline in world space
    return cv


def P(v: float) -> int:
    return int(math.floor(v * S))


# ----------------------------------------------------------------------------
# details (2x pixel art)

_EYE_F = {   # front-facing, 4x3
    "sleepy": ["LLLL", "ehhe", ".EE."],
    "open": [".ee.", "ehhe", ".EE."],
    "fierce": ["LL..", "eLLL", ".hE."],
    "closed": ["....", "LLLL", "...."],
    "happy": [".LL.", "L..L", "...."],
    "squint": ["LL..", "..LL", "...."],
    "swirl": ["hE..", "E.hE", ".Eh."],
}
_EYE_S = {   # side view (facing right), 3x3
    "sleepy": ["LLL", "ehh", ".EE"],
    "open": [".ee", "ehh", ".EE"],
    "fierce": ["LL.", ".LL", "hEE"],
    "closed": ["...", "LLL", "..."],
    "happy": [".L.", "L.L", "..."],
    "squint": ["L..", ".LL", "..."],
    "swirl": ["hE.", "E.h", ".Eh"],
}
_EYE_PAL = {"L": LID, "e": EYE, "h": EYE_HI, "E": EYE_LO, "r": EYE_RIM}


def _eye_front(cv, cx, cy, state, mirror=False):
    rows = _EYE_F.get(state, _EYE_F["sleepy"])
    if mirror:
        rows = [r[::-1] for r in rows]
    cv.grid(rows, int(round(cx * S)) - 2, int(round(cy * S)) - 1, _EYE_PAL)


def _eye_side(cv, cx, cy, state):
    rows = _EYE_S.get(state, _EYE_S["sleepy"])
    cv.grid(rows, int(round(cx * S)) - 1, int(round(cy * S)) - 1, _EYE_PAL)


def _flower(cv, x, y, kind=0):
    """Tiny flowers in the moss: cream daisy, gold buttercup, or a closed bud."""
    xi, yi = int(round(x * S)), int(round(y * S))
    if kind == 0:
        cv.grid([".pp.", "pccp", "sccs", ".ss."], xi - 2, yi - 2, {"p": PETAL, "s": PETAL_SH, "c": POLLEN})
    elif kind == 1:
        cv.grid([".pp.", "pcop", "scos", ".ss."], xi - 2, yi - 2, {"p": PETAL_Y, "s": PETAL_YS, "c": POLLEN_O,
                                                                    "o": col("ember", 3)})
    else:
        cv.grid([".p.", "psp", ".s."], xi - 1, yi - 2, {"p": PETAL, "s": PETAL_SH})


def _dust(cv, pts):
    puffs = []
    for d in pts:
        if len(d) == 2:
            puffs.append((d[0], d[1] - 0.6, 1.3))
        else:
            puffs.append(d)
    fx_dust(cv, puffs)


def _steam(cv, x, y):
    cv.grid([".s..", "sSs.", ".s.s", "..s."], P(x), P(y), {"s": STEAM2, "S": STEAM}, post=True)


def _stars(cv, hx, hy, phase):
    if phase < 0:
        return
    star = ["..s..", ".sSs.", "sSWSs", ".sSs.", "..s.."]
    pal = {"s": col("gold", 3), "S": col("gold", 4), "W": col("gold", 5)}
    pos = [(-9, -6), (6, -8)] if phase % 2 == 0 else [(-5, -9), (9, -5)]
    for dx, dy in pos:
        cv.grid(star, P(hx + dx) - 2, P(hy + dy) - 2, pal, post=True)


def _rock(cv, x, y, z=20):
    pts = [(x - 4.0, y + 1.0), (x - 2.6, y - 2.8), (x + 1.0, y - 3.6), (x + 4.0, y - 1.2), (x + 3.6, y + 2.4), (x - 0.6, y + 3.2)]
    U, V = local_uv(cv, x, y, 0.4)
    cv.add(cv.poly(pts, bevel=2.0), HIDE, 2.5, z, group="rock", contour=1, tex=_grain(U, V, 31))
    # a couple of chips and a crack on the lifted rock
    cv.grid(["c.", ".cC"], P(x - 1.0), P(y - 0.6), {"c": CRACK, "C": CRACK_HI})


def _smear_pts(cv, pts):
    for (x, y) in pts:
        xi, yi = P(x), P(y)
        cv.fig.post.append((xi, yi, SMEAR))
        cv.fig.post.append((xi + 1, yi, SMEAR))
        cv.fig.post.append((xi, yi + 1, SMEAR2))


def arc_pts(cx, cy, r, a0, a1, n=14, thick=1):
    out = []
    n = n * 2
    for i in range(n):
        a = a0 + (a1 - a0) * i / (n - 1)
        for t in range(thick):
            out.append((cx + (r - t * 0.5) * math.cos(a), cy + (r - t * 0.5) * math.sin(a)))
    return tuple(out)


def _fx(cv, p):
    fx_sparks(cv, p.sparks, hot=col("gold", 5), warm=col("stone", 4))
    fx_speed(cv, p.speed)
    if p.impact:
        fx_impact(cv, *p.impact)


# ----------------------------------------------------------------------------
# textures


def _grain(U, V, seed=0, amp=0.15):
    """Slate grain: sparse 2x1 light/dark specks (raster px coords, riding on the rig)."""
    cx = np.floor(U / 2.0)
    cy = np.floor(V)
    h = hash01(cx * 7349 + cy * 1931, seed)
    return amp * np.where(h > 0.94, 1.0, np.where(h < 0.06, -1.0, 0.0))


def _hide_tex(U, V, seed=0, amp=0.12):
    """Hide wrinkles: short horizontal creases (U along the crease)."""
    row = np.floor(V / 2.5)
    u = U / 6.0 + hash01(row, seed)
    fu = u - np.floor(u)
    crease = (np.abs((V / 2.5 - row) - 0.5) < 0.22) & (fu > 0.2) & (fu < 0.75)
    return -amp * crease


def _moss_tex(U, V, seed=0):
    """Moss: little upright tufts (strands running vertically) with a clumpy top."""
    return strand_tex(V, U, width=1.4, length=3.0, amp=0.15, seed=seed)


# ----------------------------------------------------------------------------
# shell plates


def _bands(cv, shell, keyfn, bounds, z, front_dir, base=2.5, raised=0.0, glowing=False, grain_uv=None, seed=0):
    """Split `shell` into plate bands via keyfn(pixel)->scalar and boundaries; add parts.

    front_dir=+1: bands with larger key are in front (drawn later, rim lit on their low-key edge).
    """
    key = keyfn
    edges = [-1e9] + list(bounds) + [1e9]
    parts = []
    order = range(len(edges) - 1)
    for k in order:
        m = (key >= edges[k]) & (key < edges[k + 1])
        band = shell.clip(m)
        zz = z + (k if front_dir > 0 else (len(edges) - 2 - k)) * 0.05
        tex = _grain(grain_uv[0], grain_uv[1], seed + k) if grain_uv is not None else None
        parts.append(cv.add(band, STONE, base, zz, group=f"plate{k}", contour=1, cast=1, tex=tex))
    for k in range(len(parts)):
        nbr = k - 1 if front_dir > 0 else k + 1
        if 0 <= nbr < len(parts):
            rim_highlight(parts[k], [parts[nbr].shape.mask], steps=1, amount=1)
    return parts


def _moss_ridge(cv, centers, z, glow=0, flowers=(), sway=0.0):
    ramp = GMOSS if glow else MOSS
    m = cv.empty()
    for (x, y, rx, ry) in centers:
        m = m | cv.ell(x, y, rx, ry)
    bb = m.bbox()
    U, V = local_uv(cv, 0.0, 0.0, 0.0)
    part = cv.add(m, ramp, 3 + (1 if glow >= 2 else 0), z, group="moss", contour=1, cast=1, hi=5,
                  tex=_moss_tex(U, V, 3))
    # grass tufts poking up from the ridge top
    if bb is not None:
        X, Y = cv.XY
        top = np.full(cv.w, 10 ** 6)
        mm = m.mask
        cols = np.nonzero(mm.any(axis=0))[0]
        for c in cols:
            top[c] = np.nonzero(mm[:, c])[0].min()
        tuft = np.zeros_like(mm)
        for c in cols[1:-1]:
            hh = hash01(c * 37 + 11, 9)
            if hh > 0.7:
                L = 1 + int((hh - 0.7) * 6.0)
                y0 = top[c]
                for j in range(1, L + 1):
                    if y0 - j >= 0:
                        tuft[y0 - j, c] = True
        if tuft.any():
            sh = pix.Shape(tuft).flat(-0.3, -0.6)
            cv.add(sh, ramp, 4 + (1 if glow >= 2 else 0), z + 0.01, group="moss", outline=False, cast=0, hi=5,
                   idx=np.full(tuft.shape, 4 + (1 if glow >= 2 else 0)))
    for (x, y, k) in flowers:
        _flower(cv, x + sway * (0.5 if k == 1 else 0.3), y, k)
    if glow and bb is not None:
        cv.fig.glows.append(((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, (8 + glow * 2) * S, 2))
    return part


def _cracks(cv, xf, segs):
    """Hairline cracks on the plates: dark line with a lit lower lip (rig-local design coords)."""
    for (x0, y0, x1, y1) in segs:
        a, b = xf.pt(x0, y0), xf.pt(x1, y1)
        n = max(2, int(math.dist(a, b) * S) + 1)
        last = None
        for i in range(n):
            t = i / (n - 1)
            px_, py_ = int(math.floor((a[0] + (b[0] - a[0]) * t) * S)), int(math.floor((a[1] + (b[1] - a[1]) * t) * S))
            if (px_, py_) == last:
                continue
            last = (px_, py_)
            cv.dot(px_, py_, CRACK)
            cv.dot(px_, py_ + 1, CRACK_HI)


# ----------------------------------------------------------------------------
# legs


def _claws_side(cv, ft, fr):
    cx = ft[0] + 0.8 + fr[0] - 0.7
    y = P(ft[1] + 0.3)
    for dx in (0.0, -1.2):
        x = P(cx + dx)
        cv.dot(x, y, CLAW_HI)
        cv.dot(x + 1, y, CLAW)
        cv.dot(x + 1, y + 1, CLAW)


def _claws_front(cv, ft):
    y = P(ft[1] + 0.35)
    for dx in (-1.4, 0.0, 1.4):
        x = int(round((ft[0] + dx) * S))
        cv.dot(x, y, CLAW_HI)
        cv.dot(x, y + 1, CLAW)


# ----------------------------------------------------------------------------
# EAST


def draw_e(p: Pose):
    cv = canvas()
    xf = Xf(p.x + 1.0, p.y - p.lift + p.bob, p.rot, p.rpx, p.rpy)
    gx = Xf(p.x + 1.0, p.y - p.lift, p.rot if p.feet_rot else 0.0, p.rpx, p.rpy)   # feet frame (no bob)
    Xl, Yl = xf.local(cv)
    f = p.feet
    br = p.breath
    tuck = p.tuck
    U0, V0 = local_uv(cv, xf.pt(22.0, 30.0)[0], xf.pt(22.0, 30.0)[1], p.rot)

    def leg(top, foot, r, z, offset=0, group=None, contour=1, fr=(3.1, 1.3)):
        ft = gx.pt(foot[0], foot[1])
        tp = xf.pt(*top)
        s = cv.tube([tp, (ft[0], ft[1] + 0.3 - r * 0.95)], [r, r * 0.95]) | cv.ell(ft[0] + 0.8, ft[1], fr[0], fr[1])
        U, V = local_uv(cv, tp[0], tp[1], 0.0)
        cv.add(s, HIDE, 3.0, z, offset=offset, group=group, contour=contour, tex=_hide_tex(U, V, len(group or "")),
               contour_dirs=("r", "b") if contour is not None else None)
        if offset == 0:
            _claws_side(cv, ft, fr)

    # far legs
    leg((28.4, 36.0), (28.6 + f[1][0], GROUND - 0.4 + f[1][1]), 2.4, 1, offset=-1, group="fl", contour=None)
    leg((17.6, 36.0), (17.8 + f[3][0], GROUND - 0.4 + f[3][1]), 2.6, 1, offset=-1, group="hl", contour=None)

    # tail + club
    t = p.tail
    tail = tube_x(cv, xf, [(11.0, 35.5), (8.4, 38.0), (6.8 + t[0] * 0.5, 39.0 + t[1] * 0.5)], [2.9, 2.5, 2.2])
    cv.add(tail, STONE, 2.5, 2, group="tail", contour=1, tex=_grain(U0, V0, 51))
    cly = 39.0 + t[1]
    cly -= max(0.0, xf.pt(5.4 + t[0], cly + 3.0)[1] - 43.2)
    club = ell_x(cv, xf, 5.4 + t[0], cly, 3.2, 3.0)
    cv.add(club, STONE, 2, 2.5, group="club", contour=1, spec=True, tex=_grain(U0, V0, 52))
    _cracks(cv, xf, [(4.2 + t[0], cly - 1.2, 5.6 + t[0], cly + 0.2)])

    # head (under the front lip of the shell)
    hx, hy = 36.2 + p.head[0] - tuck * 4.0, 34.6 + p.head[1] + tuck * 2.0
    hy -= max(0.0, max(xf.pt(hx + 4.4, hy + 5.1)[1], xf.pt(hx, hy + 4.8)[1]) - 43.2)
    skull = ell_x(cv, xf, hx, hy, 5.4, 4.8)
    snout = ell_x(cv, xf, hx + 4.4, hy + 2.0, 4.0, 3.1)
    Uh, Vh = local_uv(cv, *xf.pt(hx, hy), p.rot)
    cv.add(skull | snout, HIDE, 3.0, 4, group="head", contour=1, tex=_hide_tex(Uh, Vh, 7, 0.08))
    brow = ell_x(cv, xf, hx - 0.2, hy - 3.6, 5.4, 2.4, angle=-0.16)
    cv.add(brow, STONE, 2.5, 4.5, group="brow", contour=1, cast=2, tex=_grain(U0, V0, 53))
    ex, ey = xf.pt(hx + 2.2, hy - 0.8)
    _eye_side(cv, ex, ey, p.eyes)
    nx, ny = xf.pt(hx + 7.4, hy + 0.6)
    cv.grid(["hn.", "nnn", ".nn"], P(nx) - 2, P(ny) - 1, {"n": NOSE, "h": NOSE_HI})
    mx, my = xf.pt(hx + 4.2, hy + 3.6)
    if p.mouth == "open":
        cv.grid(["mmmmmm", ".MMMMm", "..mmm."], P(mx), P(my), {"m": MOUTH, "M": col("stone_warm", 0)})
    elif p.mouth == "grit":
        cv.grid(["mmmmmm", "mWWWWm"], P(mx), P(my), {"m": MOUTH, "W": CLAW_HI})
    else:
        cv.grid(["mmmmm.", ".....m"], P(mx), P(my), {"m": MOUTH})

    # near legs (behind the shell rim, in front of the far side)
    leg((31.6, 36.0), (32.2 + f[0][0], GROUND - 0.4 + f[0][1]), 2.7, 4.8, group="nfl")
    leg((14.6, 36.0), (14.8 + f[2][0], GROUND - 0.4 + f[2][1]), 2.9, 4.8, group="nhl")

    # shell: dome + scalloped rim, cut into transverse plates (front plates overlap rear ones)
    cx, cy = 22.0, 37.6
    rx, ry = 12.6 + p.plates * 1.0 + br * 0.3, 13.0 + p.plates * 1.0 + br
    dome = ell_x(cv, xf, cx, cy, rx, ry, rz=10.0).clip(Yl < 38.8 + p.plates * 0.6)
    scal = cv.empty()
    for bx in (11.8, 16.6, 21.4, 26.2, 31.0):
        scal = scal | ell_x(cv, xf, bx + 0.6, 38.6 + p.plates * 0.6, 2.9 + p.plates * 0.3, 1.9 + p.plates * 0.6)
    scal = scal.clip((Xl > cx - rx + 0.6) & (Xl < cx + rx - 0.4))
    shell = dome | scal
    key = Xl + 1.5 * ((Yl - 30.0) / 9.0) ** 2
    row_line = 32.2 + 0.9 * np.cos((Xl - cx) / rx * 1.4)          # upper row overlaps the lower row
    upper = Yl < row_line
    _bands(cv, shell.clip(~upper), key, [12.0, 16.8, 21.6, 26.4, 31.2], 5, +1, grain_uv=(U0, V0), seed=60)
    _bands(cv, shell.clip(upper), key, [14.2, 19.0, 23.8, 28.6], 5.5, +1, grain_uv=(U0, V0), seed=70)
    _cracks(cv, xf, [(17.6, 33.4, 18.8, 35.0), (27.4, 34.0, 26.6, 35.6)])

    # moss ridge with flowers along the top
    top = lambda x: cy - ry * math.sqrt(max(0.0, 1 - ((x - cx) / rx) ** 2))  # noqa: E731
    cents = []
    for i, (mx_, rr) in enumerate([(13.2, 2.0), (15.8, 2.4), (18.6, 2.6), (21.6, 2.8), (24.6, 2.6), (27.4, 2.4), (30.0, 2.0)]):
        px_, py_ = xf.pt(mx_, top(mx_) + 0.9)
        cents.append((px_, py_, rr + 0.2, 2.0 + (0.3 if i % 2 else 0.0)))
    fl = [xf.pt(17.4, top(17.4) - 0.6) + (0,), xf.pt(24.0, top(24.0) - 0.8) + (1,), xf.pt(28.6, top(28.6) - 0.2) + (0,),
          xf.pt(14.4, top(14.4) + 0.2) + (2,)]
    _moss_ridge(cv, cents, 6, p.glow, fl, p.sway)

    if p.rock:
        _rock(cv, *p.rock)
    _dust(cv, p.dust)
    if p.steam:
        _steam(cv, nx + 1, ny - 5)
    _smear_pts(cv, p.smear)
    _stars(cv, hx, hy - 6, p.stars)
    _fx(cv, p)
    return cv.render()


# ----------------------------------------------------------------------------
# SOUTH


def draw_s(p: Pose):
    cv = canvas()
    xf = Xf(p.x, p.y - p.lift + p.bob, p.rot, p.rpx, p.rpy)
    gx = Xf(p.x, p.y - p.lift, p.rot if p.feet_rot else 0.0, p.rpx, p.rpy)
    Xl, Yl = xf.local(cv)
    f = p.feet
    br = p.breath
    tuck = p.tuck
    U0, V0 = local_uv(cv, *xf.pt(24.0, 30.0), p.rot)

    def leg(top, foot, r, z, group, offset=0, claws=True):
        ft = gx.pt(*foot)
        tp = xf.pt(*top)
        s = cv.tube([tp, (ft[0], ft[1] + 0.3 - r * 0.95)], [r, r * 0.95]) | cv.ell(ft[0], ft[1], 3.4, 1.4)
        U, V = local_uv(cv, tp[0], tp[1], 0.0)
        cv.add(s, HIDE, 3.0, z, group=group, contour=1, offset=offset, tex=_hide_tex(U, V, len(group)),
               contour_dirs=("r", "b", "l"))
        if claws and offset == 0:
            _claws_front(cv, ft)

    # hind feet peeking far back at the sides
    leg((12.6, 37.0), (12.0 + f[2][0], 41.2 + f[2][1]), 2.4, 1, "hl", offset=-1, claws=False)
    leg((35.4, 37.0), (36.0 + f[3][0], 41.2 + f[3][1]), 2.4, 1, "hr", offset=-1, claws=False)

    cx, cy = 24.0, 33.4
    rx, ry = 13.6 + p.plates + br * 0.3, 10.8 + p.plates + br
    dome = ell_x(cv, xf, cx, cy, rx, ry, rz=10.0).clip(Yl < 39.4 + p.plates * 0.6)
    scal = cv.empty()
    for bx in (12.6, 17.0, 31.0, 35.4):
        scal = scal | ell_x(cv, xf, bx, 39.0 + p.plates * 0.6, 2.8 + p.plates * 0.3, 1.9 + p.plates * 0.5)
    scal = scal.clip((Xl > cx - rx + 0.8) & (Xl < cx + rx - 0.8))
    shell = dome | scal
    key = Yl - 0.05 * (Xl - cx) ** 2
    _bands(cv, shell, key, [26.6, 30.2, 33.8, 37.0], 5, +1, grain_uv=(U0, V0), seed=80)
    _cracks(cv, xf, [(14.2, 33.0, 15.4, 34.6), (33.4, 31.6, 32.4, 33.2)])
    cents = [(cx, 24.6, 5.6, 2.6), (cx - 4.0, 25.6, 2.6, 2.0), (cx + 4.2, 25.4, 2.6, 2.0), (cx - 1.4, 23.2, 2.8, 1.8),
             (cx + 1.8, 23.4, 2.4, 1.8)]
    cents = [xf.pt(x, y) + (a, b) for (x, y, a, b) in cents]
    fl = [xf.pt(cx - 3.4, 23.4) + (0,), xf.pt(cx + 3.0, 22.6) + (1,), xf.pt(cx + 0.4, 25.8) + (2,)]
    _moss_ridge(cv, cents, 6, p.glow, fl, p.sway)

    # front legs at the sides, emerging from under the shell rim
    leg((15.8, 37.6), (15.2 + f[0][0], GROUND - 0.4 + f[0][1]), 2.8, 4.6, "lf")
    leg((32.2, 37.6), (32.8 + f[1][0], GROUND - 0.4 + f[1][1]), 2.8, 4.6, "rf")

    # head emerging under the front lip
    hx, hy = cx + p.head[0], 36.2 + p.head[1] + tuck * 3.0
    hy -= max(0.0, xf.pt(hx, hy + 5.8)[1] - 43.2)
    hz = 8 if tuck < 0.5 else 4
    skull = ell_x(cv, xf, hx, hy, 6.8, 4.8)
    snout = ell_x(cv, xf, hx, hy + 2.8, 5.0, 3.0)
    Uh, Vh = local_uv(cv, *xf.pt(hx, hy), p.rot)
    cv.add(skull | snout, HIDE, 3.0, hz, group="head", contour=1, tex=_hide_tex(Uh, Vh, 9, 0.08))
    brow = ell_x(cv, xf, hx, hy - 3.2, 7.4, 2.5)
    cv.add(brow, STONE, 2.5, hz + 0.5, group="brow", contour=1, cast=2, tex=_grain(U0, V0, 91))
    if tuck < 0.8:
        e1, e2 = xf.pt(hx - 3.4, hy - 0.8), xf.pt(hx + 3.4, hy - 0.8)
        _eye_front(cv, e1[0], e1[1], p.eyes)
        _eye_front(cv, e2[0], e2[1], p.eyes, mirror=True)
        n1 = xf.pt(hx, hy + 2.2)
        c = int(round(n1[0] * S))
        cv.grid(["nn....nn", "Hn....nH"], c - 4, P(n1[1]), {"n": NOSE, "H": NOSE_HI})
        m1 = xf.pt(hx, hy + 4.2)
        c = int(round(m1[0] * S))
        if p.mouth == "open":
            cv.grid([".mmmmmm.", "mMMMMMMm", ".mmmmmm."], c - 4, P(m1[1]), {"m": MOUTH, "M": col("stone_warm", 0)})
        elif p.mouth == "grit":
            cv.grid(["mmmmmmmm", "mWWWWWWm", ".mmmmmm."], c - 4, P(m1[1]), {"m": MOUTH, "W": CLAW_HI})
        else:
            cv.grid(["m......m", ".mmmmmm."], c - 4, P(m1[1]), {"m": MOUTH})
        if p.steam:
            _steam(cv, hx - 11, hy - 1)
            _steam(cv, hx + 8, hy - 2)
        if p.bubble:
            bx, by = P(n1[0]) + 8, P(n1[1]) - 1
            if p.bubble == 1:
                cv.grid(["..bbb.", ".bwbbb", "bwbbbb", "bbbbbL", ".bbbL.", "..LL.."], bx, by - 4,
                        {"b": BUB, "w": BUB_HI, "L": BUB_LO}, post=True)
            else:
                cv.grid(["....bbbb....", "..bbbbbbbb..", ".bwwbbbbbbb.", ".bwbbbbbbbb.", "bwbbbbbbbbbb", "bbbbbbbbbbbL",
                         "bbbbbbbbbbbL", "bbbbbbbbbbLL", ".bbbbbbbbbL.", ".bbbbbbbLL..", "..bbbLLL....", "....LL......"],
                        bx, by - 10, {"b": BUB, "w": BUB_HI, "L": BUB_LO}, post=True)
    if p.curl_tail:
        # tail wrapped round the front-left, club resting by the snout
        ct = tube_x(cv, gx, [(11.6, 37.0), (9.6, 39.6), (11.6, 41.0), (14.6, 41.0)], [2.6, 2.6, 2.4, 2.2])
        cv.add(ct, STONE, 2.5, 8.6, group="ctail", contour=1, tex=_grain(U0, V0, 93))
        cv.add(ell_x(cv, gx, 16.2, 40.4, 2.9, 2.5), STONE, 2, 8.7, group="cclub", contour=1, spec=True,
               tex=_grain(U0, V0, 94))
    if p.rock:
        _rock(cv, *p.rock)
    _dust(cv, p.dust)
    _smear_pts(cv, p.smear)
    _stars(cv, hx, hy - 10, p.stars)
    _fx(cv, p)
    return cv.render()


# ----------------------------------------------------------------------------
# NORTH


def draw_n(p: Pose):
    cv = canvas()
    xf = Xf(p.x, p.y - p.lift + p.bob, p.rot, p.rpx, p.rpy)
    gx = Xf(p.x, p.y - p.lift, p.rot if p.feet_rot else 0.0, p.rpx, p.rpy)
    Xl, Yl = xf.local(cv)
    f = p.feet
    br = p.breath
    U0, V0 = local_uv(cv, *xf.pt(24.0, 30.0), p.rot)

    def leg(top, foot, r, z, group, offset=0):
        ft = gx.pt(*foot)
        tp = xf.pt(*top)
        s = cv.tube([tp, (ft[0], ft[1] + 0.3 - r * 0.95)], [r, r * 0.95]) | cv.ell(ft[0], ft[1], 3.0, 1.3)
        U, V = local_uv(cv, tp[0], tp[1], 0.0)
        cv.add(s, HIDE, 3.0, z, group=group, contour=1, offset=offset, tex=_hide_tex(U, V, len(group)),
               contour_dirs=("r", "b", "l"))

    # front feet far ahead at the sides
    leg((13.0, 34.0), (12.6 + f[0][0], 38.6 + f[0][1]), 2.2, 1, "lf", offset=-1)
    leg((35.0, 34.0), (35.4 + f[1][0], 38.6 + f[1][1]), 2.2, 1, "rf", offset=-1)
    cx, cy = 24.0, 33.2
    rx, ry = 13.6 + p.plates + br * 0.3, 11.0 + p.plates + br
    dome = ell_x(cv, xf, cx, cy, rx, ry, rz=10.0).clip(Yl < 39.4 + p.plates * 0.6)
    scal = cv.empty()
    for bx in (12.6, 17.0, 21.5, 26.5, 31.0, 35.4):
        scal = scal | ell_x(cv, xf, bx, 39.0 + p.plates * 0.6, 2.8 + p.plates * 0.3, 1.9 + p.plates * 0.5)
    scal = scal.clip((Xl > cx - rx + 0.8) & (Xl < cx + rx - 0.8))
    shell = dome | scal
    key = Yl - 0.05 * (Xl - cx) ** 2
    # far plates (smaller key) overlap the nearer ones
    _bands(cv, shell, key, [26.6, 30.2, 33.8, 37.0], 5, -1, grain_uv=(U0, V0), seed=100)
    _cracks(cv, xf, [(15.0, 34.0, 16.0, 35.6), (31.6, 30.6, 32.8, 32.0)])
    cents = [(cx, 24.4, 5.6, 2.6), (cx - 4.0, 25.4, 2.6, 2.0), (cx + 4.2, 25.6, 2.6, 2.0), (cx - 1.0, 23.0, 2.6, 1.8),
             (cx + 1.6, 26.6, 3.0, 1.8)]
    cents = [xf.pt(x, y) + (a, b) for (x, y, a, b) in cents]
    fl = [xf.pt(cx - 2.6, 23.4) + (1,), xf.pt(cx + 3.6, 24.6) + (0,), xf.pt(cx - 4.6, 25.6) + (2,)]
    _moss_ridge(cv, cents, 6, p.glow, fl, p.sway)
    # hind legs (near)
    leg((16.4, 37.6), (16.0 + f[2][0], GROUND - 0.4 + f[2][1]), 2.7, 4.6, "hl")
    leg((31.6, 37.6), (32.0 + f[3][0], GROUND - 0.4 + f[3][1]), 2.7, 4.6, "hr")
    # tail with club, toward the camera
    t = p.tail
    cly = 40.0 + t[1] * 0.5
    cly -= max(0.0, xf.pt(27.0 + t[0], cly + 2.8)[1] - 43.2)
    tail = tube_x(cv, xf, [(23.0, 35.0), (24.6 + t[0] * 0.5, 37.6), (26.4 + t[0], cly - 0.6)], [2.8, 2.5, 2.2])
    cv.add(tail, STONE, 2.5, 8, group="tail", contour=1, tex=_grain(U0, V0, 111))
    club = ell_x(cv, xf, 27.6 + t[0], cly, 3.2, 2.8)
    cv.add(club, STONE, 2, 8.5, group="club", contour=1, spec=True, tex=_grain(U0, V0, 112))
    _cracks(cv, xf, [(26.6 + t[0], cly - 1.0, 28.0 + t[0], cly + 0.4)])
    if p.rock:
        _rock(cv, *p.rock)
    _dust(cv, p.dust)
    _smear_pts(cv, p.smear)
    _stars(cv, cx, 22, p.stars)
    _fx(cv, p)
    return cv.render()


# ----------------------------------------------------------------------------
# the stone ball: true 3D roll (plates are wedges around the rolling axis)

_AXES = {"s": (-1.0, 0.0, 0.0), "n": (1.0, 0.0, 0.0)}   # top of the ball moves toward the travel
_PITCH = 0.62                     # camera looks down: the e-roll axis tilts toward the viewer


def _axis(view):
    if view == "e":
        # rolling right: axis along the world depth axis = down-on-screen + toward the camera
        a = np.array([0.0, math.sin(_PITCH), math.cos(_PITCH)])
        return a / np.linalg.norm(a)
    return np.array(_AXES[view])


def _rotate(v, axis, ang):
    """Rodrigues rotation of vectors v (..., 3) about unit axis by ang."""
    k = np.asarray(axis, float)
    c, s = math.cos(ang), math.sin(ang)
    kv = np.cross(np.broadcast_to(k, v.shape), v)
    kd = (v @ k)[..., None]
    return v * c + kv * s + k * kd * (1 - c)


NBANDS = 14
BAND = 2 * math.pi / NBANDS


def draw_ball(phase: float, face: str = "", breath: float = 0.0, x: float = 0.0, glow: int = 0, view: str = "s",
              squash: tuple = (1.0, 1.0), lift: float = 0.0, p: Pose | None = None, spin: float | None = None):
    """Curled into a stone ball rolling toward `view` ('s' camera, 'n' away, 'e' right).

    phase in [0, 1) advances the roll by one plate (so 3 evenly spaced phases loop seamlessly).
    squash = (sx, sy) scales the ball (impact squash / stretch); the ball stays on the ground.
    """
    p = p or Pose()
    cv = canvas()
    r = 10.6 + breath * 0.5
    sx, sy = squash
    rx, ry = r * sx, r * sy
    cx = 24.0 + x
    cy = GROUND + 0.75 - ry - lift          # bottom of the ball on the ground row
    X, Y = cv.XY
    u = (X - cx) / rx
    v = (Y - cy) / ry
    d2 = u * u + v * v
    disc = d2 <= 1.0
    w = np.sqrt(np.clip(1.0 - d2, 0.0, 1.0))
    ball = cv.ell(cx, cy, rx, ry, rz=min(rx, ry))
    disc &= ball.mask
    # material coordinates: rotate the visible surface point back by the roll angle
    axis = _axis(view)
    ang = phase * BAND
    Pv = np.stack([u, v, w], axis=-1)
    M = _rotate(Pv, axis, -ang)
    # basis perpendicular to the axis: ref1 = up (screen -y) projected, ref2 = axis x ref1
    up = np.array([0.0, -1.0, 0.0])
    ref1 = up - axis * (up @ axis)
    if np.linalg.norm(ref1) < 1e-6:
        ref1 = np.array([1.0, 0.0, 0.0])
    ref1 /= np.linalg.norm(ref1)
    ref2 = np.cross(axis, ref1)
    lat = M @ axis                              # along the axis (flanks at +-1)
    psi = np.arctan2(M @ ref2, M @ ref1)        # around the axis
    band = np.floor((psi + math.pi) / BAND).astype(int) % NBANDS
    # moss along the spine (lat ~ 0), lumpy, one flower per plate so the roll loops seamlessly
    fpsi = (psi + math.pi) / BAND
    within = fpsi - np.floor(fpsi)              # 0..1 inside a plate
    lump = 0.20 + 0.06 * np.cos(within * 2 * math.pi)
    moss = disc & (np.abs(lat) < lump)
    # plates
    U, V = local_uv(cv, cx, cy, 0.0)
    plate_parts = []
    for k in range(NBANDS):
        m = disc & (band == k) & ~moss
        if not m.any():
            continue
        sh = ball.clip(m)
        part = cv.add(sh, STONE, 2.5, 5 + 0.01 * k, group=f"bp{k}", contour=1, cast=1, tex=_grain(U, V, 200 + k))
        plate_parts.append((k, part))
    # raised leading rim on each plate (the edge toward the next plate in roll order)
    for k, part in plate_parts:
        nxt = [pp for kk, pp in plate_parts if kk == (k + 1) % NBANDS]
        if nxt:
            rim_highlight(part, [nxt[0].shape.mask], steps=1, amount=1)
    cv.add(ball.clip(moss), GMOSS if glow else MOSS, 3 + (1 if glow >= 2 else 0), 7, group="moss", contour=1, cast=1,
           hi=5, tex=_moss_tex(U, V, 5))
    if axis[2] > 0.3:
        # the tail club tucked in at the flank sits on the rolling axis: a hub the plates spin around
        hx_, hy_ = cx + axis[0] * rx * 0.97, cy + axis[1] * ry * 0.97
        hub = cv.ell(hx_, hy_, 2.9 * axis[2] ** 0.5 + 0.6, 2.7 * axis[2] ** 0.5 + 0.5)
        cv.add(hub.clip(disc), STONE, 2, 8, group="hub", contour=1, cast=2, spec=True, tex=_grain(U, V, 230))
        _cracks(cv, Xf(), [(hx_ - 1.2, hy_ - 1.0, hx_ - 0.2, hy_ + 0.2)])
    if glow:
        cv.glow(cx, cy, 10 + glow * 2, glow)
    # flowers: one per plate at its centre on the spine, drawn only where they face the camera
    for k in range(NBANDS):
        a = -math.pi + (k + 0.5) * BAND
        Mp = ref1 * math.cos(a) + ref2 * math.sin(a)       # material point on the spine
        Pp = _rotate(Mp[None, :], axis, ang)[0]
        if Pp[2] > 0.35:
            fx_, fy_ = cx + Pp[0] * rx, cy + Pp[1] * ry
            _flower(cv, fx_, fy_, 0)
    if face:
        # face peeking out at the bottom of the curl (only when resting toward the camera)
        hx, hy = cx, cy + ry * 0.72
        snout = cv.ell(hx, hy + 0.6, 5.6, 2.6)
        brow = cv.ell(hx, hy - 1.8, 6.6, 1.9)
        cv.add(snout, HIDE, 2.5, 9, group="face", contour=1)
        cv.add(brow, STONE, 2.5, 9.5, group="brow", contour=1, cast=1)
        st = {"sleepy": "closed"}.get(face, face)
        if st in ("closed", "sleep"):
            cv.grid([".LLLL.", "L....L"], P(hx - 3.0) - 3, P(hy - 0.4), {"L": LID})
            cv.grid([".LLLL.", "L....L"], P(hx + 3.0) - 3, P(hy - 0.4), {"L": LID})
        else:
            _eye_front(cv, hx - 3.0, hy - 0.2, st)
            _eye_front(cv, hx + 3.0, hy - 0.2, st, mirror=True)
        cv.grid(["nn..nn"], P(hx) - 3, P(hy + 1.6), {"n": NOSE})
    if spin is not None:
        # spin arcs trailing over the back of the ball (side view): they advance with the roll
        R = (max(rx, ry) + 1.5) * S
        ccx, ccy = cx * S, cy * S
        for j, (a0, span) in enumerate(((188.0, 46.0), (246.0, 32.0))):
            a0 = math.radians(a0 + spin * 14.0)
            n = int(math.radians(span) * R)
            for i in range(n):
                t = i / max(1, n - 1)
                a = a0 + math.radians(span) * t
                rr = R + j * 2.0
                c = col("cream", 2) if t < 0.35 else (col("cream", 3) if t < 0.75 else col("cream", 4))
                cv.fig.post.append((int(round(ccx + rr * math.cos(a))), int(round(ccy + rr * math.sin(a))), c))
    _dust(cv, p.dust)
    _fx(cv, p)
    return cv.render()


def draw_flop(p: Pose):
    """KO: flopped onto its back -- shell rocking on the ground, belly up, stubby legs splayed out."""
    cv = canvas()
    cx, cy = 24.0, 38.0
    X, Y = cv.XY
    U0, V0 = local_uv(cv, cx, cy, 0.0)
    bowl = cv.ell(cx, cy, 13.0, 6.0, rz=8.0).clip(Y > cy - 3.0)
    key = X - 0.04 * (Y - cy) ** 2
    _bands(cv, bowl, key, [14.0, 19.2, 24.4, 29.6], 3, +1, grain_uv=(U0, V0), seed=120)
    # domed belly with soft hide plates
    belly = cv.ell(cx, cy - 3.2, 11.0, 4.6)
    cv.add(belly, HIDE, 2.5, 6, group="belly", contour=1, tex=_hide_tex(U0, V0, 3, 0.1))
    for xx in (19.0, 24.0, 29.0):
        cv.dots([(P(xx), P(cy - 4.6 + abs(xx - cx) * 0.12) + k) for k in range(5)], col(HIDE, 2))
    # four short stubby legs splayed outward (front pair big, hind pair small)
    legs = [((15.0, 35.6), (11.6, 33.4), 2.6), ((33.0, 35.6), (36.4, 33.4), 2.6),
            ((18.6, 32.0), (17.4, 29.2), 2.2), ((29.4, 32.0), (30.6, 29.2), 2.2)]
    for k, (a, b, r) in enumerate(legs):
        s = cv.tube([a, b], [r, r * 0.9]) | cv.ell(b[0], b[1], r * 1.05, r * 0.9)
        cv.add(s, HIDE, 2.5, 7 if k < 2 else 5.5, group=f"leg{k}", contour=1, offset=0 if k < 2 else -1)
        cv.grid(["pp", "pp"], P(b[0]) - 1, P(b[1]) - 1, {"p": col(HIDE, 1)})
    # head lolling out at the front with dizzy x-eyes
    hx, hy = 24.0, 41.6
    cv.add(cv.ell(hx, hy - 0.4, 5.0, 2.6), HIDE, 2.5, 8, group="head", contour=1)
    cv.add(cv.ell(hx, hy - 2.4, 5.6, 1.6), STONE, 2.5, 8.5, group="brow", contour=1)
    xe = ["L..L", ".LL.", ".LL.", "L..L"]
    cv.grid(xe, P(hx - 3.0) - 2, P(hy) - 3, {"L": LID})
    cv.grid(xe, P(hx + 3.0) - 2, P(hy) - 3, {"L": LID})
    _stars(cv, hx, 31, p.stars if p.stars >= 0 else 0)
    return cv.render()


def draw_sleep(phase: int):
    """Snoozing: settled flat, chin on the ground, eyes shut, a nose bubble swelling and shrinking."""
    q = Pose(bob=3.0, breath=0.4 * phase, eyes="closed", head=(0.0, 1.0), feet=((0, -1), (0, -1), (0, -1), (0, -1)),
             bubble=1 + phase, curl_tail=True)
    return draw_s(q)


def draw_settle(view: str, p: Pose):
    """Settled down (focus): body lowered onto the ground, legs tucked, eyes closed."""
    q = replace(p, bob=p.bob + 3.0, feet=((0, -1), (0, -1), (0, -1), (0, -1)))
    return {"s": draw_s, "n": draw_n, "e": draw_e}[view](q)


# ----------------------------------------------------------------------------
# animations


def animations():
    A = {}

    def put(name, frames, fps, loop=True):
        A[name] = (frames, fps, loop)

    D = {"s": draw_s, "n": draw_n, "e": draw_e}

    # idle: slow breathing, sleepy blink (calm; used in the overworld)
    for d, fn in D.items():
        poses = [Pose(breath=0, eyes="sleepy"), Pose(breath=0.6, eyes="sleepy"), Pose(breath=1.0, eyes="closed", bob=0),
                 Pose(breath=0.6, eyes="sleepy")]
        put(f"idle_{d}", [fn(q) for q in poses], 4)

    battle_animations(put)

    # move: heavy plodding steps (diagonal pairs), body dips on contact
    put("move_e", [draw_e(Pose(bob=1, feet=((2, 0), (-2, 0), (-2, 0), (2, 0)), rot=0.02)),
                   draw_e(Pose(bob=0, feet=((0, -2), (0, 0), (0, 0), (0, -2)), rot=0.0)),
                   draw_e(Pose(bob=1, feet=((-2, 0), (2, 0), (2, 0), (-2, 0)), rot=-0.02)),
                   draw_e(Pose(bob=0, feet=((0, 0), (0, -2), (0, -2), (0, 0)), rot=0.0))], 8)
    put("move_s", [draw_s(Pose(bob=1, x=-1, rot=-0.03, feet=((0, 0), (0, -3), (0, -1), (0, 0)))),
                   draw_s(Pose(bob=0, x=0, feet=((0, 0), (0, -1), (0, 0), (0, 0)))),
                   draw_s(Pose(bob=1, x=1, rot=0.03, feet=((0, -3), (0, 0), (0, 0), (0, -1)))),
                   draw_s(Pose(bob=0, x=0, feet=((0, -1), (0, 0), (0, 0), (0, 0))))], 8)
    put("move_n", [draw_n(Pose(bob=1, x=-1, feet=((0, 0), (0, 0), (0, -2), (0, 0)), tail=(2, 0))),
                   draw_n(Pose(bob=0, feet=((0, 0), (0, 0), (0, 0), (0, 0)), tail=(0, 0))),
                   draw_n(Pose(bob=1, x=1, feet=((0, 0), (0, 0), (0, 0), (0, -2)), tail=(-2, 0))),
                   draw_n(Pose(bob=0, feet=((0, 0), (0, 0), (0, 0), (0, 0)), tail=(0, 0)))], 8)

    # cast: windup (rear up lifting a rock) -> release (slam) -> recover
    put("cast_e", [draw_e(Pose(rot=-0.24, rpx=13, rpy=43, head=(0, -1), eyes="open", mouth="open", rock=(38, 17))),
                   draw_e(Pose(rot=0.03, rpx=13, rpy=43, bob=1, eyes="squint", dust=((36, 42), (29, 43)))),
                   draw_e(Pose(bob=0, eyes="open"))], 10, False)
    put("cast_s", [draw_s(Pose(bob=-3, head=(0, -1), eyes="open", mouth="open", feet=((0, -3), (0, -3), (0, 0), (0, 0)), rock=(24, 14))),
                   draw_s(Pose(bob=1, eyes="squint", dust=((14, 43), (34, 43)))),
                   draw_s(Pose(eyes="open"))], 10, False)
    put("cast_n", [draw_n(Pose(bob=-3, feet=((0, -3), (0, -3), (0, 0), (0, 0)), rock=(24, 14))),
                   draw_n(Pose(bob=1, dust=((12, 40), (36, 40)))),
                   draw_n(Pose())], 10, False)

    # melee: windup -> shell bash with smear -> recover
    put("melee_e", [draw_e(Pose(x=-1, rot=-0.08, rpx=14, tuck=0.4, eyes="squint")),
                    draw_e(Pose(x=0, rot=0.10, rpx=30, eyes="squint", smear=arc_pts(25, 34, 15, -1.25, 0.12, 18))),
                    draw_e(Pose(x=0, rot=0.03, rpx=30, eyes="open"))], 10, False)
    put("melee_s", [draw_s(Pose(bob=-1, tuck=0.5, eyes="squint")),
                    draw_s(Pose(bob=2, eyes="squint", smear=arc_pts(24, 30, 13.6, 0.35, 2.8, 22))),
                    draw_s(Pose(bob=1, eyes="open"))], 10, False)
    put("melee_n", [draw_n(Pose(bob=1)),
                    draw_n(Pose(bob=-2, smear=arc_pts(24, 34, 15, -2.8, -0.35, 22))),
                    draw_n(Pose(bob=-1))], 10, False)

    # focus: settled down, moss glowing, eyes closed
    for d in "sne":
        frames = [draw_settle(d, Pose(eyes="closed", glow=g, breath=b)) for g, b in ((1, 0), (2, 0.5), (2, 1.0), (1, 0.5))]
        put(f"focus_{d}", frames, 6)

    # guard: plates raised, head tucked
    put("guard_e", [draw_e(Pose(bob=2, plates=1.0, tuck=1.0, eyes="squint")),
                    draw_e(Pose(bob=2, plates=1.0, tuck=1.0, eyes="squint", x=-1))], 6)
    put("guard_s", [draw_s(Pose(bob=2, plates=1.0, tuck=1.0)), draw_s(Pose(bob=2, plates=1.0, tuck=1.0, breath=0.5))], 6)
    put("guard_n", [draw_n(Pose(bob=2, plates=1.0)), draw_n(Pose(bob=2, plates=1.0, breath=0.5))], 6)

    # hurt
    put("hurt_e", [draw_e(Pose(x=-1, rot=-0.10, rpx=14, head=(-1, -1), eyes="squint", mouth="open"))], 8, False)
    put("hurt_s", [draw_s(Pose(bob=-1, head=(0, -1), eyes="squint", mouth="open", x=0))], 8, False)
    put("hurt_n", [draw_n(Pose(bob=-1, rot=0.04))], 8, False)

    # stunned
    put("stunned_s", [draw_s(Pose(rot=-0.05, eyes="swirl", mouth="open", stars=0)),
                      draw_s(Pose(rot=0.05, eyes="swirl", mouth="open", stars=1))], 6)

    # ko: wobble -> tip over -> flopped on its back
    put("ko_s", [draw_s(Pose(rot=0.06, eyes="swirl", mouth="open")),
                 draw_s(Pose(rot=0.30, rpx=34, rpy=43, eyes="closed", mouth="open", feet_rot=True)),
                 draw_flop(Pose())], 6, False)

    # victory: stomps and huffs
    put("victory_s", [draw_s(Pose(feet=((0, -4), (0, 0), (0, 0), (0, 0)), rot=0.07, rpx=33, bob=-1, eyes="happy")),
                      draw_s(Pose(bob=1, eyes="happy", mouth="open", dust=((13, 43),))),
                      draw_s(Pose(feet=((0, 0), (0, -4), (0, 0), (0, 0)), rot=-0.07, rpx=15, bob=-1, eyes="happy")),
                      draw_s(Pose(bob=1, eyes="happy", mouth="open", dust=((35, 43),), steam=True))], 6)

    # roll: curled ball rolling toward the camera, plates rotating
    put("roll_s", [draw_ball(k / 4.0 * 2.0, view="s") for k in range(4)], 16)
    # sleep: curled and snoozing
    put("sleep_s", [draw_sleep(0), draw_sleep(1)], 2)
    return A


# ----------------------------------------------------------------------------
# battle set: ready stance + the drag-to-dash moves (tuck -> roll -> unroll skid, ram)


def battle_animations(put):
    D = {"s": draw_s, "n": draw_n, "e": draw_e}

    # ready: awake and braced -- eyes open under the brow, weight low; it draws a deep breath (rising,
    # head up, shell swelling) and huffs it out (dipping, head nodding), club ticking -- six distinct frames
    br = [0.2, 0.5, 0.8, 0.4, 0.0, 0.0]
    bob = [0.5, 0.0, 0.0, 1.0, 1.0, 0.5]
    hd = [0.5, 0.0, -0.5, 1.0, 1.0, 0.5]
    tl = [0.0, 0.5, 1.0, 0.5, 0.0, -0.5]
    for d, fn in D.items():
        poses = [Pose(bob=bob[i], breath=br[i], eyes="open", plates=0.25, head=(1.0 if d == "e" else 0.0, hd[i]),
                      feet=((1.0, 0), (0.5, 0), (-1.0, 0), (-0.5, 0)) if d == "e" else ((-1.0, 0), (1.0, 0), (0, 0), (0, 0)),
                      tail=(tl[i], -1.0), sway=0.5 * math.sin(i * math.pi / 3)) for i in range(6)]
        put(f"ready_{d}", [fn(q) for q in poses], 6)

    # dash_windup: hunker down and tuck in -> snap into a ball (squashed, loaded)
    wind = {
        "e": [draw_e(Pose(bob=2.5, tuck=0.7, plates=0.6, eyes="fierce", rot=0.04, rpx=14, feet=((1, 0), (1, 0), (1.5, 0), (1, 0)),
                          dust=((12.0, 43.0, 1.0),))),
              draw_ball(0.0, view="e", squash=(1.1, 0.88), p=Pose(dust=((11.0, 42.6, 1.4), (37.0, 42.8, 1.0))))],
        "s": [draw_s(Pose(bob=2.5, tuck=0.5, plates=0.6, eyes="fierce", feet=((-1, 0), (1, 0), (0, 0), (0, 0)))),
              draw_ball(0.0, view="s", squash=(1.1, 0.88), face="fierce", p=Pose(dust=((11.5, 42.6, 1.2), (36.5, 42.6, 1.2))))],
        "n": [draw_n(Pose(bob=2.5, plates=0.6, feet=((0, 0), (0, 0), (-1, 0), (1, 0)))),
              draw_ball(0.0, view="n", squash=(1.1, 0.88), p=Pose(dust=((11.5, 42.6, 1.2), (36.5, 42.6, 1.2))))],
    }
    for d in "sne":
        put(f"dash_windup_{d}", wind[d], 12, False)

    # dash: charging roll -- plates spin one third of a plate per frame (seamless loop)
    dash = {
        "e": [draw_ball(k / 3.0, view="e", squash=(1.04, 0.97), spin=k,
                        p=Pose(dust=((8.0 - k * 0.8, 42.4, 1.2 + 0.2 * k),),
                               speed=((2.0, 26.0 + 4 * k % 6, 6.0), (1.0, 34.0 - 2 * k, 7.0)))) for k in range(3)],
        "s": [draw_ball(k / 3.0, view="s", p=Pose(dust=((12.0, 41.0 - k * 0.5, 1.2), (36.0, 41.0 - k * 0.5, 1.2)))) for k in range(3)],
        "n": [draw_ball(k / 3.0, view="n", p=Pose(dust=((13.0, 42.6, 1.3 + 0.2 * k), (35.0, 42.6, 1.3 + 0.2 * k)))) for k in range(3)],
    }
    for d in "sne":
        put(f"dash_{d}", dash[d], 18)

    # dash_land: pop out of the ball into a braced skid, dust spraying ahead -> settle
    land = {
        "e": [draw_e(Pose(rot=-0.10, rpx=14, bob=1.0, plates=0.5, eyes="squint", head=(1, 0), feet=((3, 0), (3, 0), (1, 0), (1, 0)),
                          dust=((42.0, 42.2, 1.8), (45.0, 41.4, 1.2)))),
              draw_e(Pose(rot=-0.04, rpx=14, bob=2.0, plates=0.2, eyes="open", feet=((2, 0), (2, 0), (0.5, 0), (0.5, 0)),
                          dust=((43.0, 41.0, 2.2), (39.5, 42.4, 1.2)))),
              draw_e(Pose(bob=0.5, eyes="open", head=(0.5, -0.5), dust=((44.0, 39.4, 1.4),)))],
        "s": [draw_s(Pose(rot=0.0, bob=1.0, plates=0.5, eyes="squint", feet=((-1.5, 0), (1.5, 0), (0, 0), (0, 0)),
                          dust=((10.5, 42.2, 1.7), (37.5, 42.2, 1.7)))),
              draw_s(Pose(bob=2.0, plates=0.2, eyes="open", feet=((-1, 0), (1, 0), (0, 0), (0, 0)),
                          dust=((9.5, 41.0, 2.0), (38.5, 41.0, 2.0)))),
              draw_s(Pose(bob=0.5, eyes="open", head=(0, -0.5), dust=((9.0, 39.6, 1.3), (39.0, 39.6, 1.3))))],
        "n": [draw_n(Pose(bob=1.0, plates=0.5, feet=((0, 0), (0, 0), (-1.5, 0), (1.5, 0)),
                          dust=((11.5, 42.2, 1.6), (36.5, 42.2, 1.6)))),
              draw_n(Pose(bob=2.0, plates=0.2, feet=((0, 0), (0, 0), (-1, 0), (1, 0)),
                          dust=((10.5, 41.0, 1.9), (37.5, 41.0, 1.9)))),
              draw_n(Pose(bob=0.5, dust=((10.0, 39.6, 1.3), (38.0, 39.6, 1.3))))],
    }
    for d in "sne":
        put(f"dash_land_{d}", land[d], 14, False)

    # ram: the rolling ball slams into a foe -- squash against the impact, then rebound with chips flying
    chips = ((40.0, 20.0, 1), (44.0, 30.0, 0), (38.0, 16.0, 0))
    ram = {
        "e": [draw_ball(0.5, view="e", squash=(0.84, 1.12), x=1.5, p=Pose(impact=(35.5, 31.0, 5.0, 0))),
              draw_ball(0.85, view="e", squash=(1.08, 0.95), x=-0.5, p=Pose(impact=(37.5, 30.0, 5.5, 1), sparks=chips))],
        "s": [draw_ball(0.5, view="s", squash=(1.12, 0.86), p=Pose(impact=(24.0, 38.0, 5.0, 0))),
              draw_ball(0.85, view="s", squash=(0.96, 1.05), p=Pose(impact=(24.0, 38.5, 5.5, 1),
                                                                    sparks=((14.0, 36.0, 1), (34.0, 35.0, 0), (31.0, 41.0, 0))))],
        "n": [draw_ball(0.5, view="n", squash=(1.12, 0.86), p=Pose(impact=(24.0, 18.0, 5.0, 0))),
              draw_ball(0.85, view="n", squash=(0.96, 1.05), p=Pose(impact=(24.0, 16.5, 5.5, 1),
                                                                    sparks=((15.0, 14.0, 1), (33.0, 13.0, 0), (30.0, 9.0, 0))))],
    }
    for d in "sne":
        put(f"ram_{d}", ram[d], 16, False)


ORDER = ["idle_s", "idle_n", "idle_e", "ready_s", "ready_n", "ready_e", "move_s", "move_n", "move_e",
         "dash_windup_s", "dash_windup_n", "dash_windup_e", "dash_s", "dash_n", "dash_e",
         "dash_land_s", "dash_land_n", "dash_land_e", "ram_s", "ram_n", "ram_e", "roll_s",
         "cast_s", "cast_n", "cast_e", "melee_s", "melee_n", "melee_e", "focus_s", "focus_n", "focus_e",
         "guard_s", "guard_n", "guard_e", "hurt_s", "hurt_n", "hurt_e", "stunned_s", "ko_s", "victory_s", "sleep_s"]


def build(out_dir: str):
    if installed_by_art_forge(out_dir, "stoneback"):
        print("  kith        stoneback            kept (HD sheet from tools/art_forge)")
        return []
    A = animations()
    assert set(A) == set(ORDER), set(A) ^ set(ORDER)
    sb = SheetBuilder("stoneback", W, H, PIVOT, columns=8, pixels_per_unit=PPU,
                      meta={"kind": "kith", "element": "stone", "generator": "tools/sprite_forge/stoneback.py",
                            "scale": S})
    for name in ORDER:
        frames, fps, loop = A[name]
        for i, fr in enumerate(frames):
            pix.check_frame(fr, f"stoneback {name}[{i}]")
        sb.add_animation(name, frames, fps, loop)
    sb.save(out_dir)
    return sb


if __name__ == "__main__":
    from preview import lineup
    imgs = [draw_s(Pose()), draw_n(Pose()), draw_e(Pose()), draw_ball(0.0), draw_flop(Pose())]
    print(lineup(imgs, 5, "stoneback_test"))
