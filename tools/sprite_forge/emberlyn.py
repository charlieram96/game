"""Emberlyn -- agile ember-element woodland kith (96x96 frames, pivot 48,88, 48 px/unit).

A long, low stoat/ferret-like body: russet back, cream underside and muzzle, soot
bandit mask and soot paws, small round ears, big amber eyes, and a long bushy
tail that holds a glowing ember coal in a ring of fur. The coal flickers in every
animation (flame tongue varies frame to frame).

Drawn at 2x: the rig is laid out in 48px *design* coordinates (same numbers as
the original 48x48 sheet) and rasterised by kit.Canvas(48, 48, s=2, hd=True),
so the creature keeps its exact proportions and world size (48 px per unit)
while the extra resolution goes into half-step shading ramps, fur clumps that
follow the body/tail, pointed tail tufts, a layered flame and 2x faces.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, replace

import numpy as np

import pix
from kit import Canvas, fx_dust, fx_impact, fx_sparks, fx_speed, local_uv, strand_tex, tube_uv
from pix import bezier, col

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common.sheet import SheetBuilder  # noqa: E402

S = 2                    # raster pixels per design pixel
DW = DH = 48             # design frame (rig coordinates)
W, H = DW * S, DH * S    # raster frame
PIVOT = (24 * S, 44 * S)
PPU = 24 * S             # pixels per world unit (same world size as the 48px sheet)
GROUND = 43.0            # design row of the planted paw soles (outline lands on the pivot row)

FUR, CREAM, SOOT = "fur_russet", "cream", "soot"


@dataclass
class Pose:
    x: float = 0.0          # whole body shift (design px)
    y: float = 0.0          # whole body shift (design px, + = down)
    bob: float = 0.0        # body/head vertical offset (paws stay planted)
    stretch: float = 0.0    # body elongation along the facing axis
    hip_dy: float = 0.0     # extra hip height offset (+ down)
    chest_dy: float = 0.0
    head: tuple = (0.0, 0.0)
    paws: tuple = ((0, 0), (0, 0), (0, 0), (0, 0))   # [near/left-front, far/right-front, near/left-hind, far/right-hind]
    tail: tuple = (0.0, 0.0)      # tail tip offset
    tail_mid: tuple = (0.0, 0.0)  # tail middle offset
    flick: int = 0          # flame tongue variant 0..3
    ember: float = 1.0      # ember coal scale
    tongue: float = 3.5     # flame tongue height
    lean: float = 0.0       # flame lean (px)
    dim: int = 0            # 0 blazing, 1 weak, 2 nearly out
    eyes: str = "open"      # open | closed | squint | swirl | happy | wide | sleep | fierce
    mouth: str = "closed"   # closed | open | smile | grit
    ears: str = "up"        # up | back | flat
    smear: tuple = ()       # melee smear marks (design px)
    sway: float = 0.0       # stunned head sway
    lift: float = 0.0       # whole-sprite hop height (paws too)
    stars: int = -1         # stunned stars phase
    tremble: int = 0
    tail_ctrl: tuple = ()   # explicit tail control points (east view), base excluded
    # effects for the dash set (design coords)
    streak: float = 0.0     # ember streak length trailing behind the coal (dash)
    streak_dir: tuple = (-1.0, 0.0)
    sparks: tuple = ()      # loose ember sparks ((x, y, size), ...)
    dust: tuple = ()        # dust puffs ((x, y, r), ...)
    speed: tuple = ()       # speed lines ((x, y, length), ...)
    impact: tuple = ()      # impact burst (x, y, r, phase)


# ----------------------------------------------------------------------------
# palette bits for hand-placed details

AMBER = col("ember", 4)
AMBER_HI = col("ember", 5)
AMBER_LO = col("ember", 3)
AMBER_DK = col("ember", 2)
PUPIL = col("soot", 0)
GLINT = col("cream", 4)
GLINT2 = col("cream", 3)
NOSE = col("soot", 1)
NOSE_HI = col("soot", 3)
MOUTH = col("fur_russet", 0)
MOUTH_IN = col("ember", 1)
TONGUE = col("cloth_red", 4)
LID = col("soot", 0)
SMEAR1 = col("ember", 6)
SMEAR2 = col("ember", 5)
SMEAR3 = col("cream", 4)
WHISKER = col("cream", 3)
SPARK = col("ember", 6)
SPARK2 = col("ember", 5)
SPARK3 = col("ember", 4)
DUST = (col("sand", 5), col("sand", 4), col("sand", 3), col("sand", 2))
SPEED = col("cream", 4)
SPEED2 = col("cream", 3)


def canvas() -> Canvas:
    cv = Canvas(DW, DH, s=S, hd=True)
    cv.fig.floor = PIVOT[1]     # nothing fills the ground row: planted paws' outline lands on the pivot
    cv.fig.rim_dark = 1         # weight on the shadow side of the silhouette
    cv.fig.outline_shadow = 1   # one extra outline ring ...
    cv.fig.outline_all = True   # ... all round: 2px = the 1x sprites' 1px outline in world space
    return cv


def P(v: float) -> int:
    """Design coordinate -> raster pixel."""
    return int(math.floor(v * S))


# ----------------------------------------------------------------------------
# faces (2x pixel art)

# south-facing eyes, 6x6, viewer's left eye; the right eye is its mirror
_EYE_S = {
    "open": [".AppA.",
             "AWWppA",
             "aWWppa",
             "apppYa",
             "aAppYa",
             ".aYYa."],
    "wide": [".AppA.",
             "AWWppA",
             "aWWppa",
             "appppa",
             "aYppYa",
             ".aYYa."],
    "fierce": ["l.....",
               ".llll.",
               "aWWppl",
               "aWpppa",
               "aAppYa",
               ".aYYa."],
    "alert": [".llll.",
              "lWWppl",
              "aWWppa",
              "apppYa",
              "aAppYa",
              ".aYYa."],
    "closed": ["......",
               "......",
               "......",
               ".llll.",
               "l....l",
               "......"],
    "sleep": ["......",
              "......",
              "l....l",
              ".llll.",
              "......",
              "......"],
    "happy": ["......",
              "..ll..",
              ".l..l.",
              "l....l",
              "......",
              "......"],
    "squint": ["l.....",
               ".ll...",
               "...ll.",
               ".ll..l",
               "l.....",
               "......"],
    "swirl": [".aYYa.",
              "Ya..aY",
              "a.YY.a",
              "a.Y..a",
              "Ya.aaY",
              ".aYYa."],
}

# east-facing (profile) eye, 5x6
_EYE_E = {
    "open": [".App.",
             "AWWpp",
             "aWWpp",
             "apppa",
             ".aYa.",
             "....."],
    "wide": [".App.",
             "AWWpp",
             "aWWpp",
             "apppa",
             "aYYa.",
             ".aa.."],
    "fierce": ["ll...",
               ".llll",
               "aWWpp",
               "aWppa",
               ".aYa.",
               "....."],
    "alert": [".lll.",
              "lWWpp",
              "aWWpp",
              "apppa",
              ".aYa.",
              "....."],
    "closed": [".....",
               ".....",
               ".....",
               "lllll",
               ".....",
               "....."],
    "sleep": [".....",
              ".....",
              "l...l",
              ".lll.",
              ".....",
              "....."],
    "happy": [".....",
              ".lll.",
              "l...l",
              ".....",
              ".....",
              "....."],
    "squint": [".....",
               "ll...",
               "..lll",
               "ll...",
               ".....",
               "....."],
    "swirl": [".YaY.",
              "a.Y.a",
              "Y.a.Y",
              "a.Y.a",
              ".YaY.",
              "....."],
}

_EYE_PAL = {"a": AMBER, "Y": AMBER_HI, "A": AMBER_LO, "D": AMBER_DK, "p": PUPIL, "W": GLINT, "w": GLINT2,
            "l": LID}


# right-eye overrides where a plain mirror would move the glint to the wrong side
_EYE_S_R = {
    "open": [".AppA.",
             "AWWppA",
             "aWWppa",
             "aYpppa",
             "aYppAa",
             ".aYYa."],
    "wide": [".AppA.",
             "AWWppA",
             "aWWppa",
             "appppa",
             "aYppYa",
             ".aYYa."],
    "fierce": [".....l",
               ".llll.",
               "lWWppa",
               "aWpppa",
               "aYppAa",
               ".aYYa."],
    "alert": [".llll.",
              "lWWppl",
              "aWWppa",
              "aYpppa",
              "aYppAa",
              ".aYYa."],
}


def _mirror(rows):
    return [r[::-1] for r in rows]


def _eyes_s(cv: Canvas, c: int, y0: int, state: str):
    """Both south-facing eyes; c = raster column of the face centre line."""
    rows = _EYE_S.get(state, _EYE_S["open"])
    right = _EYE_S_R.get(state) or _mirror(rows)
    cv.grid(rows, c - 9, y0, _EYE_PAL)
    cv.grid(right, c + 3, y0, _EYE_PAL)


def _mouth_s(cv, c, y, state):
    """Mouth below the nose; c = raster face centre (between columns c-1 and c), y = first row under the nose."""
    if state == "open":
        cv.grid(["m.mm.m", "mMMMMm", ".MttM.", "..mm.."], c - 3, y, {"m": MOUTH, "M": MOUTH_IN, "t": TONGUE})
    elif state == "smile":
        cv.grid(["..mm..", "m.mm.m", ".m..m."], c - 3, y, {"m": MOUTH})
    elif state == "grit":
        cv.grid(["mmmmmm", "mWWWWm", ".mmmm."], c - 3, y, {"m": MOUTH, "W": GLINT})
    else:
        cv.grid(["..mm..", ".m..m."], c - 3, y, {"m": col(CREAM, 0)})


def _nose_s(cv, c, y):
    cv.grid([".hn.", "nnnn", ".nn."], c - 2, y, {"n": NOSE, "h": NOSE_HI})


# ----------------------------------------------------------------------------
# heads


def head_e(cv: Canvas, hx: float, hy: float, p: Pose, z: float = 9):
    ear_dy = {"up": 0.0, "back": 1.0, "flat": 2.0}[p.ears]
    ear_dx = {"up": 0.0, "back": -1.4, "flat": -2.6}[p.ears]
    ecx, ecy = hx - 3.0 + ear_dx, hy - 4.2 + ear_dy
    ang = -0.3 - ear_dy * 0.4
    ear = cv.ell(ecx, ecy, 2.3, 2.4 - ear_dy * 0.4, angle=ang)
    cv.add(ear, FUR, 3, z - 1, group="ear", contour=1)
    if p.ears != "flat":
        inner = cv.ell(ecx + 0.55, ecy + 0.35, 1.15, 1.45 - ear_dy * 0.35, angle=ang).clip(ear.mask)
        cv.add(inner, FUR, 1, z - 0.95, group="ear", cast=0, recv=False, outline=False, light=0.5)
        cv.add(cv.ell(ecx + 0.9, ecy + 1.2, 0.8, 0.7).clip(ear.mask), CREAM, 3, z - 0.9, group="ear", cast=0,
               outline=False, light=0.5)
    skull = cv.ell(hx, hy, 5.4, 4.8)
    muzzle = cv.ell(hx + 4.3, hy + 1.6, 3.2, 2.4, angle=0.10)
    cheek = cv.poly([(hx - 3.2, hy + 1.0), (hx - 6.4, hy + 4.2), (hx - 2.0, hy + 3.6)], bevel=0.8)
    head = skull | muzzle | cheek
    cream_m = cv.below([(hx - 7, hy + 1.8), (hx + 0.5, hy + 2.2), (hx + 3.0, hy + 0.2), (hx + 9, hy - 0.4)])
    mask_band = cv.pmask([(hx - 3.4, hy - 1.4), (hx - 0.6, hy - 2.9), (hx + 2.8, hy - 2.4), (hx + 4.4, hy - 0.4),
                          (hx + 3.4, hy + 1.6), (hx + 0.6, hy + 2.0), (hx - 2.8, hy + 1.0)])
    U, V = local_uv(cv, hx, hy, 0.25)
    tex = _fur(U, V, amp=0.11, seed=11)
    cv.add(head.cut(cream_m | mask_band), FUR, 3, z, group="head", tex=tex)
    cv.add(head.clip(cream_m & ~mask_band), CREAM, 3, z + 0.1, group="head")
    cv.add(head.clip(mask_band), SOOT, 3, z + 0.2, group="head", lo=1)
    # nose at the muzzle tip, mouth line, eye
    nx, ny = P(hx + 7.3), P(hy + 0.6)
    cv.grid([".hn", "nnn", ".nn"], nx - 2, ny - 2, {"n": NOSE, "h": NOSE_HI})
    if p.mouth == "open":
        cv.grid(["mmmmm.", "mMMtt.", ".mmm.."], nx - 7, ny + 2, {"m": MOUTH, "M": MOUTH_IN, "t": TONGUE})
    elif p.mouth == "smile":
        cv.grid(["m....", ".mmmm"], nx - 7, ny + 3, {"m": MOUTH})
    elif p.mouth == "grit":
        cv.grid(["mmmmm", "mWWWm"], nx - 6, ny + 2, {"m": MOUTH, "W": GLINT})
    else:
        cv.grid(["mmmm"], nx - 6, ny + 3, {"m": col(CREAM, 1)})
    ex, ey = P(hx + 0.2), P(hy - 1.8)
    rows = _EYE_E.get(p.eyes, _EYE_E["open"])
    cv.grid(rows, ex, ey, _EYE_PAL)


def head_s(cv: Canvas, hx: float, hy: float, p: Pose, z: float = 9, ears_z: float | None = None):
    ear_dy = {"up": 0.0, "back": 1.6, "flat": 3.0}[p.ears]
    ear_sp = {"up": 0.0, "back": 0.8, "flat": 1.8}[p.ears]
    for sgn in (-1, 1):
        ex = hx + sgn * (4.9 + ear_sp)
        ey = hy - 4.9 + ear_dy
        ang = sgn * (0.35 + ear_dy * 0.2)
        ear = cv.ell(ex, ey, 2.4, 2.5 - ear_dy * 0.25, angle=ang)
        ez = (z - 1) if ears_z is None else ears_z
        cv.add(ear, FUR, 3, ez, group="ear", contour=1)
        if p.ears != "flat":
            # dark inner ear with a cream tuft at its base
            inner = cv.ell(ex + sgn * 0.15, ey - 0.15 + ear_dy * 0.2, 1.25, 1.35 - ear_dy * 0.3, angle=ang)
            cv.add(inner.clip(ear.mask), FUR, 1, ez + 0.05, group="ear", cast=0, recv=False, outline=False,
                   light=0.4, lo=1)
            tuft = cv.poly([(ex - 0.9, ey + 1.2), (ex + sgn * 0.4, ey - 0.4), (ex + 0.9, ey + 1.2)], bevel=0.5)
            cv.add(tuft.clip(ear.mask), CREAM, 3, ez + 0.1, group="ear", cast=0, outline=False, light=0.6)
    skull = cv.ell(hx, hy, 6.6, 5.6)
    cheeks = cv.ell(hx, hy + 2.0, 7.2, 3.6)
    # fluffy cheek ruff: one swept tuft per side, kept a shade down (it sits under the head's curve)
    tufts = cv.empty()
    for sgn in (-1, 1):
        tufts = tufts | cv.poly([(hx + sgn * 5.4, hy + 1.9), (hx + sgn * 7.2, hy + 2.7), (hx + sgn * 8.1, hy + 4.3),
                                 (hx + sgn * 6.3, hy + 4.5), (hx + sgn * 4.6, hy + 5.3)], bevel=1.0)
    head = skull | cheeks
    muzzle = cv.ell(hx, hy + 3.4, 3.5, 2.5)
    mask = cv.pmask([(hx - 7.4, hy + 0.6), (hx - 5.6, hy - 1.6), (hx - 2.6, hy - 2.4), (hx - 0.6, hy - 1.0),
                     (hx + 0.6, hy - 1.0), (hx + 2.6, hy - 2.4), (hx + 5.6, hy - 1.6), (hx + 7.4, hy + 0.6),
                     (hx + 6.0, hy + 2.2), (hx + 2.4, hy + 2.2), (hx + 0.6, hy + 0.6), (hx - 0.6, hy + 0.6),
                     (hx - 2.4, hy + 2.2), (hx - 6.0, hy + 2.2)])
    cheek_cream = cv.below([(hx - 9, hy + 2.4), (hx - 3, hy + 2.0), (hx + 3, hy + 2.0), (hx + 9, hy + 2.4)])
    U, V = local_uv(cv, hx, hy - 6.0, 0.0)
    tex = _fur(V, U, amp=0.11, seed=12)
    cv.add(head.cut(mask | cheek_cream), FUR, 3, z, group="head", tex=tex)
    cv.add(head.clip(cheek_cream & ~mask), CREAM, 3, z + 0.1, group="head")
    cv.add(head.clip(mask), SOOT, 3, z + 0.2, group="head", lo=1)
    cv.add(muzzle, CREAM, 3, z + 0.3, group="head")
    cv.add(tufts.cut(head.mask), CREAM, 2.5, z + 0.05, group="head", light=0.7)
    c = int(round(hx * S))
    ey = P(hy - 1.4) - 1
    _eyes_s(cv, c, ey, p.eyes)
    ny = P(hy + 2.2)
    _nose_s(cv, c, ny)
    _mouth_s(cv, c, ny + 3, p.mouth)


def head_n(cv: Canvas, hx: float, hy: float, p: Pose, z: float = 5):
    ear_dy = {"up": 0.0, "back": 1.4, "flat": 2.6}[p.ears]
    for sgn in (-1, 1):
        ex, ey = hx + sgn * 4.7, hy - 3.4 + ear_dy
        ear = cv.ell(ex, ey, 2.1, 2.2 - ear_dy * 0.25, angle=sgn * 0.4)
        cv.add(ear, FUR, 3, z + 0.5, group="ear", contour=1)
    U, V = local_uv(cv, hx, hy - 5.0, 0.0)
    tex = _fur(V, U, amp=0.15, seed=13)
    cv.add(cv.ell(hx, hy, 5.7, 4.7), FUR, 3, z, group="head", cast=2, contour=1, tex=tex)


# ----------------------------------------------------------------------------
# ember: coal + layered flame


def _flame(cv: Canvas, x, y, r, flick=0, lean=0.0, tongue=3.5, dim=0, z=50.0, glow_r=9.0,
           streak=0.0, sdir=(-1.0, 0.0)):
    """Glowing coal at (x, y) (design px) with a flickering, layered flame.

    The tongue rises (or, with streak > 0, trails along sdir) and has a white-hot
    core, a yellow body and an orange/red rim; variants split the tongue tip.
    """
    X, Y = cv.XY
    var = [(0.0, 0.0, 0), (1.2, 0.6, 1), (2.2, -0.4, -1), (0.8, -0.8, 1)][flick % 4]
    th = max(0.0, tongue + var[0] - dim * 1.6)
    if streak > 0:
        # flame dragged behind the coal: axis along sdir, a little upward
        ax = np.array(sdir, float)
        ax = ax / (np.linalg.norm(ax) + 1e-9)
        length = r + streak + var[0] * 0.8
        bend = 0.8 * var[1]
    else:
        ax = np.array([lean * 0.12 + var[1] * 0.08, -1.0])
        ax = ax / np.linalg.norm(ax)
        length = r + th
        bend = lean + var[1]
    nxv, nyv = -ax[1], ax[0]                      # perpendicular
    dx, dy = X - x, Y - y
    a = dx * ax[0] + dy * ax[1]                    # along the flame
    b = dx * nxv + dy * nyv                        # across
    coal = (dx * dx) / (r * r) + (dy * dy) / (r * r * 0.92) <= 1.0
    m = coal.copy()
    t = (a + 0.3) / max(length - 0.3, 0.5)         # 0 at the coal centre -> 1 at the tip
    tc = np.clip(t, 0, 1)
    if length > r + 0.3:
        centre = bend * tc ** 1.6
        half = r * 0.95 * np.clip(1.0 - tc, 0, 1) ** 0.85
        tong = (t >= 0) & (t <= 1.0) & (np.abs(b - centre) <= half + 0.05)
        m |= tong
        if var[2] and streak <= 0:
            # split tip: a small side tongue licking up beside the main one
            t2 = (a - r * 0.2) / max(length * 0.62, 0.5)
            c2 = var[2] * (r * 0.75) + bend * 0.5 * np.clip(t2, 0, 1)
            h2 = r * 0.42 * np.clip(1 - t2, 0, 1) ** 0.8
            m |= (t2 >= 0) & (t2 <= 1) & (np.abs(b - c2) <= h2 + 0.05)
    else:
        centre = np.zeros_like(X)
        half = np.full_like(X, r)
    m = pix.despike(m)
    # heat: distance from the hot core, stretched along the flame
    dc = np.sqrt((dx / max(r, 0.5)) ** 2 + ((dy - 0.2) / (max(r, 0.5) * 1.25)) ** 2)
    across = np.abs(b - centre) / np.maximum(half, 0.3)
    heat = np.where(t > 0.15, (1.0 - tc) * (1.0 - 0.75 * across ** 2), 1.0 - dc)
    idx = np.full((cv.h, cv.w), 4)
    idx[heat > 0.12] = 4
    idx[heat > 0.38] = 5
    idx[heat > 0.62] = 6
    idx[(t > 0.78) & m & ~coal] = 3
    idx[(across > 0.82) & (t > 0.35) & m & ~coal] = 3
    idx[coal & (dc > 0.86)] = 4
    if dim == 1:
        idx = np.clip(idx - 1, 3, 5)
    elif dim >= 2:
        idx = np.clip(idx - 2, 2, 4)
    shape = pix.Shape(m)
    part = cv.add(shape, "ember", 4, z, idx=idx, oc=col("ember", 1 + (1 if dim >= 2 else 0)), cast=0, recv=False,
                  glow=False, group="flame")
    if glow_r > 0 and dim < 2:
        cv.glow(x, y, glow_r * (0.7 if dim else 1.0), 2)
    return part


def _ember_tip(cv, tip, p, z, lean=0.0, dx=0.0, scale=None):
    ring_c = (tip[0] + dx, tip[1] - 1.0)
    back = cv.ell(ring_c[0], ring_c[1] - 0.6, 3.4, 2.3)
    cv.add(back, CREAM, 1, z, group="tail", cast=0)
    er = 2.8 * (p.ember if scale is None else scale)
    # a flame streaming toward the camera (dashing away) passes in front of the fur cup
    fz = z + 3 if (p.streak > 0 and p.streak_dir[1] > 0.3) else z + 1
    _flame(cv, ring_c[0], ring_c[1] - 2.2 - (er - 2.8) * 0.6, er, p.flick, lean=lean + p.lean, tongue=p.tongue,
           dim=p.dim, z=fz, glow_r=9.0 * min(1.4, max(0.7, er / 2.8)), streak=p.streak, sdir=p.streak_dir)
    _calyx(cv, ring_c[0], ring_c[1], z + 2)


def _calyx(cv, cx, cy, z):
    """Cup of cream fur cradling the coal: a crescent with three tufts licking up around it."""
    front = cv.ell(cx, cy + 0.5, 3.8, 1.8) - cv.ell(cx, cy - 1.1, 2.4, 1.3)
    for (ddx, ddy, lean, h) in ((-2.9, 0.1, -0.55, 1.6), (0.0, 0.9, 0.0, 1.3), (2.9, 0.1, 0.55, 1.6)):
        bx, by = cx + ddx, cy + ddy
        front = front | cv.poly([(bx - 1.0, by + 0.7), (bx - 0.5 + lean * 0.6, by - h * 0.55),
                                 (bx + lean * 1.2, by - h), (bx + 0.5 + lean * 0.6, by - h * 0.55),
                                 (bx + 1.0, by + 0.7)], bevel=0.7)
    cv.add(front, CREAM, 2, z, group="ring", cast=0)


# ----------------------------------------------------------------------------
# tail

TAIL_R = [2.4, 2.9, 3.3, 3.6, 3.7, 3.6, 3.4, 3.2, 3.0, 2.9]


def _fur(S_, R_, amp=0.17, seed=0, width=1.6, length=6.0):
    return strand_tex(S_, R_, width=width, length=length, amp=amp, seed=seed)


def _tail(cv, ctrl, z, n=10, radii=None, contour=None, cast=1, tufts=True, seed=0, period=5.2, depth=(2.2, 1.4),
          crease=0.32):
    """Long bushy tail: a tapered tube whose outline breaks into big swept flicks
    (sawtooth radius along the tail, teeth pointing to the tip), a crease running
    in from every notch, and hair strands that follow the tail's curve."""
    pts = bezier(ctrl, n)
    if radii is None:
        radii = [TAIL_R[min(len(TAIL_R) - 1, int(k * len(TAIL_R) / n))] for k in range(n)]
    s = cv.s
    Su, Rv = tube_uv(cv, pts)
    tex = _fur(Su, Rv, amp=0.17, seed=21 + seed)
    if not tufts:
        shape = cv.tube(pts, radii)
    else:
        seglen = [0.0]
        for i in range(1, len(pts)):
            seglen.append(seglen[-1] + math.dist(pts[i], pts[i - 1]) * s)
        total = max(seglen[-1], 1.0)
        rS = np.interp(Su, seglen, [r * s for r in radii])
        # which side is the outside of the curl gets the bigger flicks
        turn = 0.0
        for i in range(1, len(pts) - 1):
            ax, ay = pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]
            bx, by = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
            turn += ax * by - ay * bx
        d_pos, d_neg = (depth[1], depth[0]) if turn > 0 else (depth[0], depth[1])
        dmax = max(depth)
        big = cv.tube(pts, [r + dmax for r in radii])
        t = Su / total
        env = np.clip((t - 0.12) / 0.1, 0, 1) * np.clip((0.95 - t) / 0.1, 0, 1)
        dside = np.where(Rv >= 0, d_pos, d_neg) * s
        P_ = period * s
        f = (Su / P_ + np.where(Rv >= 0, 0.0, 0.5) + 0.37 * seed) % 1.0
        edge = rS + dside * env * f ** 0.4
        shape = big.clip(np.abs(Rv) <= edge)
        if crease:
            # a short crease from every notch, running inward and toward the tip
            a_, b_ = 3.0 * s, 2.6 * s
            r_in = (rS + dside * env) - np.abs(Rv)
            tt = f * P_ / a_
            on = (tt <= 1.0) & (np.abs(r_in - tt * b_ - 0.5) < 0.75) & (env > 0.5)
            tex = tex - crease * on
    cv.add(shape, FUR, 3, z, group="tail", contour=contour, cast=cast, tex=tex)
    return pts


# ----------------------------------------------------------------------------
# small effects


def _smear(cv: Canvas, p: Pose):
    if not p.smear:
        return
    for (x, y) in p.smear:
        xi, yi = P(x), P(y)
        cv.fig.post.append((xi, yi, SMEAR1))
        cv.fig.post.append((xi + 1, yi, SMEAR1))
        cv.fig.post.append((xi, yi + 1, SMEAR2))


def claw_arcs(x0, y0, dirx=1, diry=0, n=3, length=5, spacing=2, curve=0.35):
    """Three parallel curved slash lines starting near (x0, y0) (design px, sampled at half steps)."""
    pts = []
    for k in range(n):
        steps = length * 2
        for i in range(steps):
            u = i / 2.0
            if dirx:
                x = x0 + dirx * u
                y = y0 + k * spacing - curve * (u - length / 2) ** 2 / 2 + curve * (length / 2) ** 2 / 2
                y = -y + 2 * (y0 + k * spacing)
            else:
                y = y0 + diry * u
                x = x0 + k * spacing - curve * (u - length / 2) ** 2 / 2
            pts.append((x, y))
    return tuple(pts)


def _stars(cv: Canvas, hx, hy, phase):
    if phase < 0:
        return
    star = ["..s..", ".sSs.", "sSWSs", ".sSs.", "..s.."]
    pal = {"s": col("gold", 3), "S": col("gold", 4), "W": col("gold", 5)}
    pos = [(-7, -9), (4, -10), (-1, -12)] if phase % 2 == 0 else [(-4, -11), (6, -8), (-8, -7)]
    for dx, dy in pos[:2]:
        cv.grid(star, P(hx + dx), P(hy + dy), pal, post=True)


def _fx(cv: Canvas, p: Pose):
    fx_dust(cv, p.dust)
    fx_sparks(cv, p.sparks)
    fx_speed(cv, p.speed)
    if p.impact:
        fx_impact(cv, *p.impact)


# ----------------------------------------------------------------------------
# EAST (side profile, facing right)


def _leg(cv, top, paw, r_top, r_mid, bend, z, offset=0, group=None, contour=None, front=True, fur_group=None, sock=2.8,
         toes=True):
    """Leg: russet upper (blends into body), soot sock + paw at the bottom.

    Near legs get a contour only on their shadow side (right/bottom), so they
    separate from the body without looking like pasted-on tubes."""
    mx = top[0] + (paw[0] - top[0]) * 0.55 + bend
    my = top[1] + (paw[1] - top[1]) * 0.55
    legpts = [top, (mx, my), (paw[0], paw[1] - 0.6)]
    leg = cv.tube(legpts, [r_top, r_mid, r_mid * 0.95])
    fx = paw[0] + (0.8 if front else 0.5)
    pawshape = cv.ell(fx, paw[1], 2.0, 1.15) | cv.ell(fx + 1.0, paw[1] + 0.15, 1.1, 1.0)
    sock_m = cv.disk(paw[0] + 0.4, paw[1] + 0.9, sock)
    full = leg | pawshape
    Su, Rv = tube_uv(cv, legpts)
    tex = _fur(Su, Rv, amp=0.13, seed=31)
    cdirs = ("r", "b") if contour is not None else None
    cv.add(full.cut(sock_m), FUR, 3, z, offset=offset, group=fur_group if fur_group else group, cast=0,
           contour=None if fur_group else contour, tex=tex, contour_dirs=cdirs)
    cv.add(full.clip(sock_m), SOOT, 3, z + 0.1, offset=offset, group=group, contour=contour, cast=1,
           contour_dirs=cdirs)
    if toes and offset == 0:
        # toe split on the front of the paw
        tx_, ty_ = P(fx + 0.9), P(paw[1] + 0.1)
        cv.dot(tx_, ty_, col(SOOT, 0))
        cv.dot(tx_, ty_ + 1, col(SOOT, 0))


def _gy(p: Pose) -> float:
    return GROUND - 0.25 + p.y - p.lift


def draw_e(p: Pose):
    cv = canvas()
    ox, oy = p.x + p.tremble, p.y - p.lift
    b = p.bob
    s = p.stretch
    hipc = (18.0 + ox - s * 0.5, 31.0 + oy + b + p.hip_dy)
    chc = (29.4 + ox + s * 0.5, 31.6 + oy + b + p.chest_dy)
    hx, hy = 36.0 + ox + s * 0.5 + p.head[0], 22.4 + oy + b + p.head[1]
    gy = _gy(p)
    pw = p.paws

    # far legs (behind body, one shade darker)
    _leg(cv, (chc[0] - 1.5, chc[1] + 2.0), (29.0 + ox + s * 0.5 + pw[1][0], gy + pw[1][1]), 1.9, 1.45, -0.4, 1,
         offset=-1, group="farleg")
    _leg(cv, (hipc[0] + 2.0, hipc[1] + 2.5), (20.4 + ox - s * 0.5 + pw[3][0], gy + pw[3][1]), 2.0, 1.5, -1.4, 1,
         offset=-1, group="farleg2", front=False)

    # tail (behind body): base at rump, S-curve rising, tip curling forward
    tdx, tdy = p.tail
    mdx, mdy = p.tail_mid
    base = (hipc[0] - 4.0, hipc[1] - 2.0)
    if p.tail_ctrl:
        ctrl = [base] + [(x + ox, y + oy) for (x, y) in p.tail_ctrl]
    else:
        ctrl = [base, (base[0] - 5.4, base[1] + 1.5), (6.6 + ox + mdx, 21.0 + oy + mdy),
                (9.4 + ox + tdx, 15.4 + oy + tdy), (13.0 + ox + tdx, 15.0 + oy + tdy)]
    pts = _tail(cv, ctrl, 2)
    _ember_tip(cv, pts[-1], p, z=3, lean=-0.4, dx=0.8)

    # body: one smooth tube along the spine + neck (many samples -> no shading seams)
    n = 14
    spine = bezier([(hipc[0] - 4.0, hipc[1] - 0.2), (hipc[0] + 2.0, hipc[1] - 0.4), (chc[0] - 3.6, chc[1] + 1.6),
                    (chc[0] + 3.4, chc[1] - 1.4)], n)
    radii = []
    for k in range(n):
        t = k / (n - 1.0)
        r = 4.2 + 1.8 * math.sin(min(1.0, k / 4.0) * math.pi / 2)
        r = min(r, 6.0 - 1.1 * math.sin(min(1, max(0, (t - 0.25) / 0.3)) * math.pi / 2)
                + 0.7 * max(0.0, min(1.0, (t - 0.55) / 0.2)) - 1.4 * max(0.0, (t - 0.85) / 0.15))
        radii.append(r)
    body = cv.tube(spine, radii)
    neck = cv.tube([(chc[0] + 1.5, chc[1] - 1.0), (hx - 1.6, hy + 1.8)], [4.0, 3.4])
    body = body | neck
    # cream throat/chest (right of a line down the front of the neck) + belly strip
    under = cv.right_of([(hx - 3.4, hy + 1.6), (hx - 3.9, hy + 4.2), (chc[0] + 1.6, chc[1] - 2.2),
                         (chc[0] + 0.6, chc[1] + 1.4), (chc[0] - 1.0, chc[1] + 6.0)], zig=(0.6, 2.2)) | \
        cv.below([(hipc[0] + 3.0, hipc[1] + 5.0), (chc[0] - 3.0, chc[1] + 3.4), (chc[0] + 1.2, chc[1] + 2.4)],
                 zig=(0.6, 2.6, 0.3))
    flow = [(hx - 1.6, hy + 1.8), (chc[0] + 1.5, chc[1] - 1.0)] + list(reversed(spine))
    Su, Rv = tube_uv(cv, flow)
    tex = _fur(Su, Rv, amp=0.18, seed=1)
    cv.add(body.cut(under), FUR, 3, 5, group="body", tex=tex)
    cv.add(body.clip(under), CREAM, 3, 5.1, group="body", tex=tex * 0.6)
    U, V = local_uv(cv, hipc[0] + 0.3, hipc[1] - 3.0, 1.2)
    cv.add(cv.ell(hipc[0] + 0.3, hipc[1] + 1.4, 4.0, 4.3), FUR, 3, 6, group="thigh", cast=0,
           tex=_fur(U, V, amp=0.15, seed=2))

    # near legs (in front of body)
    _leg(cv, (chc[0] + 0.8, chc[1] + 2.0), (31.6 + ox + s * 0.5 + pw[0][0], gy + pw[0][1]), 2.0, 1.5, -0.4, 7,
         group="nearleg", contour=1)
    _leg(cv, (hipc[0] - 0.2, hipc[1] + 3.0), (17.4 + ox - s * 0.5 + pw[2][0], gy + pw[2][1]), 2.3, 1.55, -1.6, 7,
         group="nearleg2", contour=1, front=False)

    head_e(cv, hx, hy, p, z=9)
    _smear(cv, p)
    _stars(cv, hx - 2, hy, p.stars)
    _fx(cv, p)
    return cv.render()


# ----------------------------------------------------------------------------
# SOUTH (facing the camera)


def _front_leg_s(cv, top, paw, z, group, offset=0, r=(1.8, 1.55)):
    legpts = [top, (paw[0], paw[1] - 0.6)]
    leg = cv.tube(legpts, [r[0] * 1.06, r[1] * 0.97])
    pawshape = cv.ell(paw[0], paw[1] + 0.05, 2.05, 1.25)
    full = leg | pawshape
    sock = cv.below([(paw[0] - 5, paw[1] - 2.6), (paw[0] + 5, paw[1] - 2.6)], zig=(0.55, 1.3, 0.5))
    Su, Rv = tube_uv(cv, legpts)
    cv.add(full.cut(sock), FUR, 3, z, group=group, contour=1, offset=offset, contour_dirs=("r", "b"),
           tex=_fur(Su, Rv, amp=0.13, seed=41))
    cv.add(full.clip(sock), SOOT, 3, z + 0.1, group=group, contour=1, offset=offset, contour_dirs=("r", "b", "l"))
    if offset == 0:
        # toes: two little splits on the paw front
        bx, by = int(round(paw[0] * S)), P(paw[1] + 0.25)
        for dx in (-2, 1):
            cv.dot(bx + dx, by, col(SOOT, 0))
            cv.dot(bx + dx, by + 1, col(SOOT, 0))


def draw_s(p: Pose):
    cv = canvas()
    ox, oy = p.x + p.tremble, p.y - p.lift
    b = p.bob
    s = p.stretch
    hx, hy = 24.0 + ox + p.head[0] + p.sway, 26.6 + oy + b + p.head[1] + s * 0.5
    gy = _gy(p)
    pw = p.paws

    # tail behind everything: rises from behind the body, curling up on the right
    tdx, tdy = p.tail
    mdx, mdy = p.tail_mid
    base = (27.0 + ox, 29.0 + oy + b - s * 0.5)
    ctrl = [base, (35.5 + ox + mdx, 30.0 + oy + mdy), (38.0 + ox + tdx, 20.0 + oy + tdy), (33.6 + ox + tdx, 15.2 + oy + tdy)]
    pts = _tail(cv, ctrl, 1)
    _ember_tip(cv, pts[-1], p, z=2, lean=0.3, dx=-0.4)

    # body behind the head; hind feet tucked behind the front legs
    body = cv.ell(24.0 + ox, 31.0 + oy + b - s * 0.3, 7.0, 6.6)
    U, V = local_uv(cv, 24.0 + ox, 24.0 + oy + b, 0.0)
    cv.add(body, FUR, 3, 5, group="body", tex=_fur(V, U, amp=0.18, seed=3))
    for k, sx in enumerate((17.8, 30.2)):
        hp = pw[2 + k]
        cv.add(cv.ell(sx + ox + hp[0], 36.6 + oy + b * 0.5 + hp[1], 2.3, 2.6), FUR, 3, 4.8, group=f"haunch{k}",
               offset=-1, contour=1)
        cv.add(cv.ell(sx + ox + (-0.3 if k == 0 else 0.3) + hp[0], 39.4 + oy + hp[1], 1.8, 1.1), SOOT, 3,
               4.9, group=f"haunch{k}", contour=1, offset=-1)

    # chest bib and short front legs
    bcx, bcy = 24.0 + ox, 35.0 + oy + b + s * 0.3
    bib = cv.ell(bcx, bcy, 3.9, 3.6) | cv.poly([(bcx - 1.4, bcy + 2.8), (bcx, bcy + 4.0), (bcx + 1.4, bcy + 2.8)], bevel=0.8)
    cv.add(bib, CREAM, 3, 6, group="chest", cast=1)
    for k, lx in enumerate((20.8, 27.2)):
        paw = (lx + ox + pw[k][0], gy + pw[k][1])
        top = (lx + ox + (0.5 if k == 0 else -0.5), 36.0 + oy + b)
        _front_leg_s(cv, top, paw, 7, f"fleg{k}")

    head_s(cv, hx, hy, p, z=9)
    _smear(cv, p)
    _stars(cv, hx, hy, p.stars)
    _fx(cv, p)
    return cv.render()


# ----------------------------------------------------------------------------
# NORTH (facing away)


def draw_n(p: Pose):
    cv = canvas()
    ox, oy = p.x + p.tremble, p.y - p.lift
    b = p.bob
    s = p.stretch
    pw = p.paws
    gy = _gy(p)
    hx, hy = 24.0 + ox + p.head[0], 17.6 + oy + b + p.head[1] - s * 0.8

    # front paws peeking out ahead at the sides (furthest away)
    for k, fx_ in enumerate((19.2, 28.8)):
        fp = (fx_ + ox + pw[k][0], 30.2 + oy + max(-1.0, pw[k][1]))     # far paws stay tucked behind the body
        cv.add(cv.ell(fp[0], fp[1], 2.0, 1.2) | cv.ell(fp[0], fp[1] - 1.4, 1.4, 1.2), SOOT, 3, 0.5, group=f"fp{k}",
               light=0.7)
    # long back seen from behind: rump (near) -> shoulders -> neck (far)
    rump_y = 34.6 + oy + b
    sh_y = 25.0 + oy + b - s * 0.5
    spine = bezier([(24.0 + ox, rump_y), (24.0 + ox, rump_y - 5.0), (24.0 + ox, sh_y + 2.0), (24.0 + ox, sh_y - 3.0)], 10)
    radii = [6.6, 6.7, 6.5, 6.1, 5.7, 5.3, 4.9, 4.5, 4.0, 3.6]
    body = cv.tube(spine, radii) | cv.ell(24.0 + ox, rump_y + 0.6, 7.2, 5.2)
    Su, Rv = tube_uv(cv, list(reversed(spine)))
    cv.add(body, FUR, 3, 4, group="body", tex=_fur(Su, Rv, amp=0.18, seed=4))
    head_n(cv, hx, hy, p, z=5)
    # haunches + hind legs (closest)
    for k, sx in enumerate((18.6, 29.4)):
        U, V = local_uv(cv, sx + ox, 31.0 + oy + b, 0.0)
        cv.add(cv.ell(sx + ox, 35.4 + oy + b, 3.2, 3.8), FUR, 3, 5.5, group=f"haunch{k}", cast=0,
               tex=_fur(V, U, amp=0.15, seed=5 + k))
    for k, lx in enumerate((19.8, 28.2)):
        paw = (lx + ox + pw[2 + k][0], gy + pw[2 + k][1])
        top = (lx + ox, 37.0 + oy + b)
        _front_leg_s(cv, top, paw, 6, f"hleg{k}", r=(1.9, 1.6))

    # tail in front: from the rump, curling up the right side
    tdx, tdy = p.tail
    mdx, mdy = p.tail_mid
    base = (25.0 + ox, 35.4 + oy + b)
    ctrl = [base, (35.0 + ox + mdx, 36.5 + oy + mdy), (38.6 + ox + tdx, 25.0 + oy + tdy), (34.4 + ox + tdx, 18.5 + oy + tdy)]
    pts = _tail(cv, ctrl, 8, contour=1)
    _ember_tip(cv, pts[-1], p, z=9, lean=-0.3, dx=-0.2)
    _smear(cv, p)
    _stars(cv, hx, hy + 2, p.stars)
    _fx(cv, p)
    return cv.render()


# ----------------------------------------------------------------------------
# special poses


def draw_sit_e(p: Pose):
    """Sitting upright on the haunches (focus)."""
    cv = canvas()
    ox, oy, b = p.x, p.y, p.bob
    hipc = (19.0 + ox, 37.2 + oy)
    chc = (24.2 + ox, 28.6 + oy + b)
    hx, hy = 27.6 + ox + p.head[0], 19.4 + oy + b + p.head[1]
    tdx, tdy = p.tail
    gy = GROUND - 0.25 + oy
    # tail: sweeps back along the ground, then rises behind the back holding the ember
    ctrl = [(hipc[0] - 4.0, hipc[1] + 1.5), (7.6 + ox, 40.6 + oy), (5.8 + ox, 30.0 + oy), (8.4 + ox + tdx, 22.5 + oy + tdy),
            (11.4 + ox + tdx, 21.4 + oy + tdy)]
    pts = _tail(cv, ctrl, 2, n=11)
    _ember_tip(cv, pts[-1], p, z=3, lean=-0.2, dx=0.6)
    # far front leg
    _leg(cv, (chc[0] + 0.5, chc[1] + 3.0), (27.6 + ox, gy), 1.8, 1.45, 0.0, 1, offset=-1, group="farleg")
    spine = bezier([(hipc[0] - 1.5, hipc[1] + 1.5), (hipc[0] + 0.5, hipc[1] - 3.0), (chc[0] - 1.0, chc[1] + 3.0),
                    (chc[0] + 1.6, chc[1] - 3.2)], 12)
    radii = [5.6, 5.8, 5.7, 5.5, 5.3, 5.1, 5.0, 4.9, 4.7, 4.5, 4.2, 4.0]
    body = cv.tube(spine, radii) | cv.tube([(chc[0] + 1.0, chc[1] - 1.0), (hx - 1.4, hy + 2.0)], [4.0, 3.4])
    under = cv.right_of([(hx - 2.5, hy + 2.0), (chc[0] + 1.6, chc[1] - 2.0), (chc[0] + 2.2, chc[1] + 3.0),
                         (hipc[0] + 4.0, hipc[1] - 1.0), (hipc[0] + 5.0, hipc[1] + 6.0)])
    Su, Rv = tube_uv(cv, [(hx - 1.4, hy + 2.0)] + list(reversed(spine)))
    tex = _fur(Su, Rv, amp=0.18, seed=6)
    cv.add(body.cut(under), FUR, 3, 5, group="body", tex=tex)
    cv.add(body.clip(under), CREAM, 3, 5.1, group="body", tex=tex * 0.6)
    # haunch + hind paw flat on the ground
    U, V = local_uv(cv, hipc[0] + 0.5, hipc[1] - 3.0, 1.0)
    cv.add(cv.ell(hipc[0] + 0.5, hipc[1] + 0.8, 4.4, 4.4), FUR, 3, 6, group="thigh", contour=1, cast=1,
           tex=_fur(U, V, amp=0.15, seed=7))
    cv.add(cv.ell(hipc[0] + 4.2, GROUND - 0.4 + oy, 2.8, 1.15), SOOT, 3, 6.5, group="hpaw", contour=1)
    # near front leg straight down to the ground
    _leg(cv, (chc[0] + 1.6, chc[1] + 3.0), (29.0 + ox, gy), 2.0, 1.5, 0.2, 7, group="nearleg", contour=1)
    head_e(cv, hx, hy, p, z=9)
    return cv.render()


def draw_sit_s(p: Pose):
    cv = canvas()
    ox, oy, b = p.x, p.y, p.bob
    hx, hy = 24.0 + ox + p.head[0], 21.6 + oy + b + p.head[1]
    tdx, tdy = p.tail
    gy = GROUND - 0.25 + oy
    ctrl = [(27.0 + ox, 37.0 + oy), (37.0 + ox, 39.0 + oy), (39.5 + ox + tdx, 26.0 + oy + tdy), (34.6 + ox + tdx, 18.6 + oy + tdy)]
    pts = _tail(cv, ctrl, 1)
    _ember_tip(cv, pts[-1], p, z=2, lean=0.3, dx=-0.4)
    body = cv.ell(24.0 + ox, 33.0 + oy + b * 0.5, 6.8, 7.8)
    U, V = local_uv(cv, 24.0 + ox, 25.0 + oy, 0.0)
    cv.add(body, FUR, 3, 5, group="body", tex=_fur(V, U, amp=0.18, seed=8))
    belly = cv.ell(24.0 + ox, 33.6 + oy + b * 0.5, 4.2, 6.0)
    belly = belly.cut(~cv.below([(18.0 + ox, 28.6 + oy + b * 0.5), (30.0 + ox, 28.6 + oy + b * 0.5)], zig=(0.8, 1.6, 0.25)))
    cv.add(belly, CREAM, 3, 5.1, group="body")
    for k, sx in enumerate((17.4, 30.6)):
        U, V = local_uv(cv, sx + ox, 34.0 + oy, 0.0)
        cv.add(cv.ell(sx + ox, 38.2 + oy, 3.4, 4.0), FUR, 3, 5.5, group=f"haunch{k}", contour=1,
               tex=_fur(V, U, amp=0.15, seed=9 + k))
        cv.add(cv.ell(sx + ox + (-1.0 if k == 0 else 1.0), GROUND - 0.4 + oy, 2.4, 1.15), SOOT, 3, 5.6,
               group=f"haunch{k}", contour=1)
    for k, lx in enumerate((22.0, 26.0)):
        _front_leg_s(cv, (lx + ox, 35.0 + oy + b), (lx + ox, gy), 7, f"fleg{k}", r=(1.6, 1.4))
    head_s(cv, hx, hy, p, z=9)
    return cv.render()


def draw_sit_n(p: Pose):
    cv = canvas()
    ox, oy, b = p.x, p.y, p.bob
    hx, hy = 24.0 + ox + p.head[0], 20.4 + oy + b + p.head[1]
    body = cv.ell(24.0 + ox, 32.4 + oy + b * 0.5, 7.0, 8.6)
    U, V = local_uv(cv, 24.0 + ox, 24.0 + oy, 0.0)
    cv.add(body, FUR, 3, 4, group="body", tex=_fur(V, U, amp=0.18, seed=10))
    head_n(cv, hx, hy, p, z=5)
    for k, sx in enumerate((17.6, 30.4)):
        cv.add(cv.ell(sx + ox, 38.4 + oy, 3.4, 4.0), FUR, 3, 5.5, group=f"haunch{k}", cast=0)
        cv.add(cv.ell(sx + ox, GROUND - 0.4 + oy, 2.3, 1.15), SOOT, 3, 5.6, group=f"hp{k}", contour=1)
    tdx, tdy = p.tail
    ctrl = [(24.5 + ox, 40.0 + oy), (35.0 + ox, 41.5 + oy), (39.0 + ox + tdx, 30.0 + oy + tdy), (35.0 + ox + tdx, 22.6 + oy + tdy)]
    pts = _tail(cv, ctrl, 8, contour=1)
    _ember_tip(cv, pts[-1], p, z=9, lean=-0.3, dx=-0.2)
    return cv.render()


def draw_curl_s(p: Pose, tight: bool = False):
    """Curled up in a ball: tail wrapped around the front, head resting on it, nose by the ember."""
    cv = canvas()
    ox, oy, b = p.x + p.tremble, p.y - 1.0, p.bob
    rx = 9.0 if tight else 10.6
    cx = 23.0 + ox
    body = cv.ell(cx, 36.0 + oy + b * 0.5, rx, 7.0 - b * 0.5)
    U, V = local_uv(cv, cx, 29.0 + oy, 0.0)
    cv.add(body, FUR, 3, 3, group="body", tex=_fur(V, U, amp=0.18, seed=14))
    # haunch bump at the back-left
    cv.add(cv.ell(cx - rx + 4.4, 35.2 + oy + b * 0.5, 4.0, 4.4), FUR, 3, 3.5, group="haunch", contour=1, cast=1)
    # tail: from the back-left, around the front, tip at the front-right
    ctrl = [(cx - rx + 2.0, 31.0 + oy), (cx - rx - 3.0, 40.6 + oy), (cx - 2.0, 43.4 + oy), (cx + rx + 1.0, 42.2 + oy),
            (cx + rx + 2.4, 38.2 + oy)]
    radii = [2.4, 2.8, 3.0, 3.1, 3.2, 3.2, 3.1, 3.0, 2.9, 2.8, 2.8, 2.8]
    pts = _tail(cv, ctrl, 6, n=12, radii=radii, contour=1, cast=1, seed=3, depth=(1.6, 1.0), period=4.6)
    _ember_tip(cv, pts[-1], p, z=7, lean=0.0, dx=0.0)
    # head in profile, chin resting on the tail
    hx = cx + (2.0 if tight else 3.0) + p.head[0]
    hy = 34.4 + oy + (1.0 if tight else 0.0) + p.head[1]
    head_e(cv, hx, hy, p, z=10)
    return cv.render()


def draw_lie(p: Pose):
    """Collapsed on its side (KO): side profile flat on the ground, belly toward camera."""
    q = replace(p, bob=6.0, head=(0.0, 9.0), paws=((4, -1), (5, 0), (3, -1), (4, 0)), ears="flat",
                tail_ctrl=((7.4, 37.6), (5.6, 38.0), (6.8, 35.8), (8.8, 34.8)))
    return draw_e(q)


# ----------------------------------------------------------------------------
# battle set: ready stance + the drag-to-dash moves (coil -> burst -> skid, ram)

# tail swept back and up while dashing (east view, relative to the body shift)
TAIL_DASH = ((9.4, 26.4), (7.8, 21.0), (8.6, 15.8), (11.2, 13.4))
TAIL_SKID = ((9.4, 29.6), (6.4, 26.8), (7.6, 20.8), (11.6, 18.6))


def battle_animations(put):
    D = {"s": draw_s, "n": draw_n, "e": draw_e}

    # ready: alert battle stance -- weight forward, tail high, ember lively; gentle breathing
    bob = [0.0, 0.5, 1.0, 1.0, 0.5, 0.0]
    sway = [(0.0, 0.0), (0.5, 0.0), (1.0, 0.5), (1.0, 0.5), (0.5, 0.0), (0.0, 0.0)]
    flk = [0, 1, 2, 3, 1, 2]
    tng = [4.0, 4.6, 5.0, 4.4, 4.0, 4.8]
    ready_e = [Pose(bob=bob[i], chest_dy=1.0, hip_dy=-1.0, head=(1.0, 1.5), paws=((1.5, 0), (2.5, 0), (-1.0, 0), (0, 0)),
                    tail=(1.0 + sway[i][0], -1.5 + sway[i][1]), tail_mid=(0.5, -1.5), ember=1.15, tongue=tng[i] - 0.3,
                    flick=flk[i], eyes="alert") for i in range(6)]
    ready_s = [Pose(bob=bob[i], head=(0, 1.0), paws=((-1.0, 0), (1.0, 0), (-0.5, 0), (0.5, 0)),
                    tail=(sway[i][0] - 0.5, -1.5 + sway[i][1]), tail_mid=(0, -1.0), ember=1.15, tongue=tng[i],
                    flick=flk[i], eyes="alert") for i in range(6)]
    ready_n = [Pose(bob=bob[i], paws=((-1.0, 0), (1.0, 0), (-0.5, 0), (0.5, 0)),
                    tail=(sway[i][0], -1.5 + sway[i][1]), tail_mid=(0.5, -1.0), ember=1.15, tongue=tng[i], flick=flk[i])
               for i in range(6)]
    for d, poses in (("s", ready_s), ("n", ready_n), ("e", ready_e)):
        put(f"ready_{d}", [D[d](q) for q in poses], 8)

    # dash_windup: coil -- body sinks back over the hind legs, front paws braced ahead, tail
    # cocked high and the ember flaring
    wind_e = [Pose(x=-1.0, bob=1.5, stretch=-1.5, hip_dy=0.5, chest_dy=1.0, head=(0.5, 2.0),
                   paws=((3.0, 0), (3.0, 0), (2.0, 0), (2.5, 0)), ears="back", eyes="fierce",
                   tail=(2.0, -1.0), tail_mid=(1.0, -1.0), ember=1.25, tongue=5.0, flick=1),
              Pose(x=-2.0, bob=2.5, stretch=-2.5, hip_dy=0.5, chest_dy=1.5, head=(0.5, 3.0),
                   paws=((4.5, 0), (4.5, 0), (3.0, 0), (3.5, 0)), ears="flat", eyes="fierce",
                   tail=(3.0, 0.0), tail_mid=(1.5, -1.0), ember=1.4, tongue=4.4, flick=2,
                   sparks=((16.0, 6.0, 0), (10.0, 8.5, 1)), dust=((14.5, 42.6, 1.1),))]
    wind_s = [Pose(bob=1.5, head=(0, 1.5), paws=((-1.0, 0), (1.0, 0), (-1.0, 0), (1.0, 0)), ears="back", eyes="fierce",
                   tail=(1.0, -2.0), tail_mid=(1.0, -1.0), ember=1.25, tongue=5.0, flick=1),
              Pose(bob=2.5, head=(0, 2.5), paws=((-1.5, 0), (1.5, 0), (-1.5, 0), (1.5, 0)), ears="flat", eyes="fierce",
                   tail=(2.0, 0.5), tail_mid=(1.0, -0.5), ember=1.4, tongue=4.6, flick=2,
                   sparks=((31.0, 8.5, 0), (37.5, 11.0, 1)))]
    wind_n = [Pose(bob=1.5, paws=((-1.0, 0), (1.0, 0), (-1.0, 0), (1.0, 0)), ears="back",
                   tail=(1.0, -2.0), tail_mid=(1.0, -1.0), ember=1.25, tongue=5.0, flick=1),
              Pose(bob=2.5, paws=((-1.5, 0), (1.5, 0), (-1.5, 0), (1.5, 0)), ears="flat",
                   tail=(2.0, -2.0), tail_mid=(1.5, -1.5), ember=1.4, tongue=5.5, flick=2,
                   sparks=((31.5, 9.0, 0), (38.0, 11.5, 1)))]
    for d, poses in (("s", wind_s), ("n", wind_n), ("e", wind_e)):
        put(f"dash_windup_{d}", [D[d](q) for q in poses], 12, False)

    # dash: explosive bounding leap, long and low; ember streaks behind (loops at 18 fps)
    tr_e = dict(ears="flat", eyes="fierce", tail_ctrl=TAIL_DASH, streak_dir=(-1.0, -0.3), tongue=4.0)
    dash_e = [Pose(x=-1.0, stretch=3.0, lift=1.0, bob=1.0, hip_dy=-0.5, chest_dy=0.5, head=(1.0, 2.0),
                   paws=((5.0, -1.5), (6.0, -2.0), (-5.0, -1.0), (-6.0, -1.5)), streak=4.5, flick=0,
                   sparks=((2.5, 9.0, 0), (4.0, 6.5, 1)), speed=((1.0, 31.5, 6.0), (2.0, 35.5, 5.0)), **tr_e),
              Pose(x=-1.0, stretch=2.0, lift=2.5, bob=1.0, head=(1.0, 1.5),
                   paws=((1.0, -2.5), (2.0, -3.0), (2.0, -3.0), (3.0, -2.5)), streak=5.0, flick=2,
                   sparks=((2.0, 7.5, 1), (5.5, 5.0, 0)), speed=((1.0, 33.0, 7.0),), **tr_e),
              Pose(x=-1.0, stretch=0.5, lift=1.0, bob=0.5, hip_dy=-1.0, head=(1.0, 1.5),
                   paws=((3.0, 0.0), (4.0, -1.0), (3.0, -2.0), (4.0, -1.5)), streak=4.0, flick=1,
                   sparks=((1.5, 10.0, 0), (4.5, 7.0, 0)), speed=((1.0, 30.5, 5.0), (2.0, 34.5, 6.0)), **tr_e)]
    tr_s = dict(ears="flat", eyes="fierce", streak_dir=(0.1, -1.0), tongue=4.0, tail=(-2.5, -0.5), tail_mid=(-2.0, 0.0))
    dash_s = [Pose(bob=1.5, stretch=1.5, lift=1.0, head=(0, 2.0), paws=((-2.0, 0.5), (1.5, -2.0), (-0.5, -1.5), (0.5, -1.5)),
                   streak=5.0, flick=0, sparks=((33.0, 3.5, 0), (36.5, 6.0, 1)), **tr_s),
              Pose(bob=1.5, stretch=0.5, lift=2.5, head=(0, 1.5), paws=((-1.0, -2.0), (1.0, -2.0), (-0.5, -2.0), (0.5, -2.0)),
                   streak=5.5, flick=2, sparks=((35.0, 4.0, 1), (31.5, 6.5, 0)), **tr_s),
              Pose(bob=1.5, stretch=1.0, lift=1.0, head=(0, 2.0), paws=((-1.5, -2.0), (2.0, 0.5), (-0.5, -1.5), (0.5, -1.5)),
                   streak=4.5, flick=1, sparks=((34.0, 5.0, 0), (37.0, 3.0, 0)), **tr_s)]
    tr_n = dict(ears="flat", tongue=2.6, lean=0.6, ember=1.15)
    dash_n = [Pose(bob=1.5, stretch=3.0, lift=1.0, paws=((0, -2.0), (0, -1.0), (-1.0, 1.0), (1.0, -1.0)),
                   tail=(1.0, 2.0), tail_mid=(0.0, 1.0), flick=0, sparks=((36.5, 24.0, 1), (34.5, 27.5, 0), (37.5, 29.0, 0)),
                   **tr_n),
              Pose(bob=1.5, stretch=2.0, lift=2.5, paws=((0, -2.5), (0, -2.5), (-0.5, -1.5), (0.5, -1.5)),
                   tail=(1.0, 2.5), tail_mid=(0.0, 1.0), flick=2, sparks=((37.0, 25.5, 0), (35.0, 28.5, 1), (36.0, 31.0, 0)),
                   **tr_n),
              Pose(bob=1.5, stretch=2.5, lift=1.0, paws=((0, -1.0), (0, -2.0), (-1.0, -1.0), (1.0, 1.0)),
                   tail=(1.0, 2.0), tail_mid=(0.0, 1.0), flick=1, sparks=((35.5, 25.0, 0), (37.5, 27.0, 1), (34.0, 30.0, 0)),
                   **tr_n)]
    for d, poses in (("s", dash_s), ("n", dash_n), ("e", dash_e)):
        put(f"dash_{d}", [D[d](q) for q in poses], 18)

    # dash_land: braking skid -- paws braced ahead, body thrown back, dust kicked up -> settle
    land_e = [Pose(x=-1.0, bob=0.5, chest_dy=-1.5, hip_dy=1.0, head=(-1.0, -1.0), paws=((5.5, 0), (6.5, 0), (0.5, 0), (1.5, 0)),
                   ears="back", eyes="squint", tail_ctrl=TAIL_SKID, lean=3.0, tongue=4.0, flick=3,
                   dust=((41.0, 42.4, 1.9), (44.5, 41.6, 1.4)), speed=((1.0, 34.0, 2.5),)),
              Pose(x=-0.5, bob=1.5, chest_dy=0.5, hip_dy=0.5, head=(0, 1.5), paws=((3.5, 0), (4.5, 0), (0.5, 0), (1.0, 0)),
                   ears="back", eyes="open", tail=(3.0, 0.0), tail_mid=(1.5, 0.0), lean=1.5, tongue=4.5, flick=0,
                   dust=((42.0, 41.2, 2.2), (45.0, 40.4, 1.3), (38.5, 42.6, 1.1))),
              replace(ready_e[1], dust=((43.5, 39.2, 1.5),))]
    land_s = [Pose(bob=0.5, head=(0, -1.0), paws=((-2.0, 0), (2.0, 0), (-1.0, 0), (1.0, 0)), ears="back", eyes="squint",
                   tail=(1.0, 2.0), tail_mid=(0.5, 1.0), lean=-2.0, tongue=4.0, flick=3,
                   dust=((15.5, 42.4, 1.7), (32.5, 42.4, 1.7), (13.5, 40.8, 1.1))),
              Pose(bob=1.5, head=(0, 1.0), paws=((-1.5, 0), (1.5, 0), (-1.0, 0), (1.0, 0)), ears="back", eyes="open",
                   tail=(0.5, 0.5), lean=-1.0, tongue=4.5, flick=0,
                   dust=((14.5, 41.4, 2.0), (33.5, 41.4, 2.0))),
              replace(ready_s[1], dust=((13.5, 39.8, 1.4), (34.5, 39.8, 1.4)))]
    land_n = [Pose(bob=0.5, head=(0, 1.0), paws=((-1.5, 0), (1.5, 0), (-1.5, 0), (1.5, 0)), ears="back",
                   tail=(-1.0, -2.0), tail_mid=(0, -1.0), lean=-2.0, tongue=4.0, flick=3,
                   dust=((15.8, 42.4, 1.6), (32.2, 42.4, 1.6))),
              Pose(bob=1.5, paws=((-1.0, 0), (1.0, 0), (-1.0, 0), (1.0, 0)), ears="back",
                   tail=(0, -1.0), lean=-1.0, tongue=4.5, flick=0,
                   dust=((15.0, 41.6, 1.9), (33.0, 41.6, 1.9))),
              replace(ready_n[1], dust=((14.5, 40.4, 1.3), (33.5, 40.4, 1.3)))]
    for d, poses in (("s", land_s), ("n", land_n), ("e", land_e)):
        put(f"dash_land_{d}", [D[d](q) for q in poses], 14, False)

    # ram: shoulder-first slam through a foe -> follow-through with sparks
    ram_e = [Pose(x=-2.0, stretch=2.0, bob=1.5, hip_dy=-1.0, chest_dy=1.0, head=(1.0, 3.0),
                  paws=((4.0, -1.0), (3.0, 0), (-4.0, -1.0), (-5.0, 0)), ears="flat", eyes="squint", mouth="grit",
                  tail_ctrl=TAIL_DASH, streak=3.0, streak_dir=(-1.0, -0.3), ember=1.35, tongue=4.5, flick=2,
                  impact=(41.5, 22.5, 5.0, 0)),
             Pose(x=-1.0, stretch=2.5, bob=1.0, head=(1.0, 2.0), paws=((5.0, -1.0), (5.0, 0), (-5.0, -1.0), (-5.0, 0)),
                  ears="flat", eyes="fierce", mouth="grit", tail_ctrl=TAIL_DASH, streak=4.0, streak_dir=(-1.0, -0.3),
                  ember=1.3, tongue=4.5, flick=0, impact=(42.0, 22.5, 5.0, 1),
                  sparks=((45.0, 15.0, 1), (46.0, 30.0, 0), (38.0, 13.0, 0)))]
    ram_s = [Pose(bob=2.0, head=(0, 3.0), paws=((-1.0, 0), (1.0, 0), (-1.0, 0), (1.0, 0)), ears="flat", eyes="squint",
                  mouth="grit", tail=(-2.0, -1.0), streak=3.0, streak_dir=(0.1, -1.0), ember=1.35, tongue=4.5, flick=2,
                  impact=(24.0, 34.0, 5.5, 0)),
             Pose(bob=1.0, head=(0, 2.0), paws=((-1.5, 0), (1.5, 0), (-1.0, 0), (1.0, 0)), ears="flat", eyes="fierce",
                  mouth="grit", tail=(-2.0, -1.0), streak=4.0, streak_dir=(0.1, -1.0), ember=1.3, tongue=4.5, flick=0,
                  impact=(24.0, 34.0, 6.0, 1), sparks=((13.5, 30.0, 1), (35.0, 29.0, 0), (32.0, 39.5, 0)))]
    ram_n = [Pose(bob=1.0, stretch=3.0, head=(0, -1.0), paws=((0, -2.0), (0, -2.0), (-1.0, 0), (1.0, 0)), ears="flat",
                  tail=(1.0, 2.0), tail_mid=(0.0, 1.0), ember=1.3, tongue=2.8, lean=0.6, flick=2,
                  sparks=((36.0, 24.5, 0), (35.0, 28.0, 1)), impact=(24.0, 7.5, 4.0, 0)),
             Pose(bob=1.0, stretch=2.0, paws=((0, -1.0), (0, -1.0), (-1.0, 0), (1.0, 0)), ears="flat",
                  tail=(1.0, 2.0), tail_mid=(0.0, 1.0), ember=1.25, tongue=3.0, lean=0.4, flick=0,
                  impact=(24.0, 7.0, 5.0, 1), sparks=((15.0, 9.0, 1), (33.0, 8.0, 0), (30.0, 3.0, 0), (36.5, 26.0, 0)))]
    for d, poses in (("s", ram_s), ("n", ram_n), ("e", ram_e)):
        put(f"ram_{d}", [D[d](q) for q in poses], 16, False)


# ----------------------------------------------------------------------------
# animation table


def animations():
    A = {}  # name -> (frames(list of Image), fps, loop)

    def put(name, frames, fps, loop=True):
        A[name] = (frames, fps, loop)

    D = {"s": draw_s, "n": draw_n, "e": draw_e}
    SIT = {"s": draw_sit_s, "n": draw_sit_n, "e": draw_sit_e}

    # idle: breathing, tail sway, flicker (calm; used in the overworld)
    for d, f in D.items():
        # half-pixel steps (1 raster px) keep the 2x breathing smooth
        poses = [Pose(bob=0, tail=(0, 0), flick=0), Pose(bob=0.5, tail=(1, 0), tail_mid=(0, 0), flick=1),
                 Pose(bob=1, tail=(1, 1), tail_mid=(0, 1), flick=2), Pose(bob=0.5, tail=(0, 1), flick=3)]
        put(f"idle_{d}", [f(q) for q in poses], 6)

    # move: bounding gallop (gather -> push -> stretch -> land)
    move_e = [
        Pose(stretch=-3, hip_dy=-2, head=(0, 1), paws=((-3, 0), (-2, 0), (4, 0), (5, 0)), tail=(1, 2), tail_mid=(1, 1), flick=0),
        Pose(stretch=2, lift=2, head=(1, -1), paws=((4, -1), (3, 0), (-3, 2), (-2, 2)), tail=(-1, 1), flick=1),
        Pose(stretch=3, lift=1, head=(1, 0), paws=((4, 1), (5, 0), (-4, -1), (-3, -1)), tail=(-2, 3), tail_mid=(-1, 2), flick=2),
        Pose(stretch=0, hip_dy=-1, paws=((1, 0), (2, 0), (1, -2), (2, -2)), tail=(0, 2), tail_mid=(0, 1), flick=3),
    ]
    put("move_e", [draw_e(q) for q in move_e], 12)
    move_s = [
        Pose(bob=1, head=(0, 1), paws=((0, 0), (0, 0), (0, 1), (0, 1)), tail=(0, 1), flick=0, ears="back"),
        Pose(lift=2, stretch=-1, paws=((-1, -1), (1, -1), (0, 2), (0, 2)), tail=(-1, 2), flick=1, ears="back"),
        Pose(lift=1, stretch=1, head=(0, 1), paws=((0, 1), (0, 1), (0, -1), (0, -1)), tail=(-2, 3), flick=2, ears="back"),
        Pose(bob=0, paws=((0, 0), (0, 0), (0, -1), (0, -1)), tail=(-1, 1), flick=3, ears="back"),
    ]
    put("move_s", [draw_s(q) for q in move_s], 12)
    move_n = [
        Pose(bob=-1, paws=((0, 0), (0, 0), (0, -2), (0, -2)), tail=(1, -1), flick=0, ears="back"),
        Pose(lift=2, stretch=1, paws=((0, -1), (0, -1), (0, 2), (0, 2)), tail=(2, 1), flick=1, ears="back"),
        Pose(lift=1, stretch=2, head=(0, -1), paws=((0, 0), (0, 0), (0, 0), (0, 0)), tail=(1, 2), flick=2, ears="back"),
        Pose(bob=0, stretch=0, paws=((0, 0), (0, 0), (0, -1), (0, -1)), tail=(0, 0), flick=3, ears="back"),
    ]
    put("move_n", [draw_n(q) for q in move_n], 12)

    battle_animations(put)

    # cast: windup (rear back, ember flares) -> release (lunge, mouth open) -> recover
    cast_e = [Pose(x=-2, chest_dy=-3, hip_dy=1, head=(-1, -3), paws=((-1, -2), (-1, -1), (0, 0), (0, 0)),
                   ember=1.3, tongue=5.0, flick=1, tail=(1, 1)),
              Pose(x=0, stretch=2, head=(1, 1), mouth="open", paws=((3, 0), (3, 0), (-1, 0), (-1, 0)),
                   ember=1.2, tongue=4.5, flick=2, tail=(-1, 1)),
              Pose(x=0, stretch=1, head=(1, 0), ember=1.05, tongue=3.5, flick=3)]
    put("cast_e", [draw_e(q) for q in cast_e], 10, False)
    cast_s = [Pose(bob=-1, head=(0, -2), ember=1.3, tongue=4.5, flick=1, tail=(1, 1), paws=((0, -1), (0, -1), (0, 0), (0, 0))),
              Pose(bob=1, stretch=2, head=(0, 2), mouth="open", ember=1.2, tongue=4.5, flick=2),
              Pose(stretch=1, head=(0, 1), ember=1.05, flick=3)]
    put("cast_s", [draw_s(q) for q in cast_s], 10, False)
    cast_n = [Pose(bob=-1, head=(0, 1), ember=1.3, tongue=5.0, flick=1, tail=(1, -1)),
              Pose(stretch=2, head=(0, -2), ember=1.2, tongue=4.5, flick=2, tail=(-1, 1)),
              Pose(stretch=1, head=(0, -1), ember=1.05, flick=3)]
    put("cast_n", [draw_n(q) for q in cast_n], 10, False)

    # melee: windup -> strike (claw swipe with smear) -> recover
    mel_e = [Pose(x=-1, bob=1, head=(-1, 1), paws=((-2, -4), (0, 0), (1, 0), (1, 0)), tail=(1, 1), flick=0, ears="back"),
             Pose(x=1, stretch=1, head=(0, 0), mouth="open", paws=((5, -7), (2, 0), (-1, 0), (-1, 0)), flick=1,
                  smear=claw_arcs(39, 29, 1, 0, n=3, length=4, spacing=2)),
             Pose(x=1, stretch=0, paws=((2, -1), (1, 0), (0, 0), (0, 0)), flick=2)]
    put("melee_e", [draw_e(q) for q in mel_e], 10, False)
    mel_s = [Pose(bob=1, head=(0, -1), paws=((-1, -5), (0, 0), (0, 0), (0, 0)), flick=0, ears="back"),
             Pose(bob=1, head=(0, 1), mouth="open", paws=((3, -2), (0, 0), (0, 0), (0, 0)), flick=1,
                  smear=claw_arcs(16, 34, 0, 1, n=3, length=4, spacing=2)),
             Pose(paws=((1, -1), (0, 0), (0, 0), (0, 0)), flick=2)]
    put("melee_s", [draw_s(q) for q in mel_s], 10, False)
    mel_n = [Pose(bob=1, head=(0, 1), paws=((0, 0), (0, 0), (0, 0), (0, 0)), flick=0, ears="back", tail=(2, 1)),
             Pose(stretch=2, head=(0, -2), paws=((1, -4), (-1, -4), (0, 0), (0, 0)), flick=1,
                  smear=claw_arcs(19, 7, 1, 0, n=3, length=5, spacing=2)),
             Pose(stretch=1, head=(0, -1), flick=2)]
    put("melee_n", [draw_n(q) for q in mel_n], 10, False)

    # focus: sitting upright, eyes closed, ember enlarged and pulsing brighter
    for d, f in SIT.items():
        scales = [1.25, 1.35, 1.45, 1.35]
        tongues = [4.5, 5.0, 5.5, 5.0]
        poses = [Pose(eyes="closed", ember=scales[i], tongue=tongues[i], flick=i, bob=(0 if i < 2 else 1),
                      tail=(0, 0)) for i in range(4)]
        put(f"focus_{d}", [f(q) for q in poses], 8)

    # guard: low braced stance, ears back
    g_e = [Pose(bob=2, x=-1, head=(-2, 3), paws=((2, 0), (2, 0), (-2, 0), (-2, 0)), ears="back", tail=(1, 3), tail_mid=(0, 2), flick=f)
           for f in (0, 2)]
    g_e[1] = replace(g_e[1], bob=3, head=(-2, 4))
    put("guard_e", [draw_e(q) for q in g_e], 6)
    g_s = [Pose(bob=2, head=(0, 1), paws=((-1, 0), (1, 0), (-1, 0), (1, 0)), ears="back", flick=f) for f in (0, 2)]
    g_s[1] = replace(g_s[1], bob=3)
    put("guard_s", [draw_s(q) for q in g_s], 6)
    g_n = [Pose(bob=2, head=(0, 1), paws=((-1, 0), (1, 0), (-1, 0), (1, 0)), ears="back", flick=f) for f in (0, 2)]
    g_n[1] = replace(g_n[1], bob=3)
    put("guard_n", [draw_n(q) for q in g_n], 6)

    # hurt: recoil, squint
    put("hurt_e", [draw_e(Pose(x=-1, head=(-2, -2), chest_dy=-1, eyes="squint", mouth="open", ears="flat",
                               paws=((-1, -2), (-1, -1), (0, 0), (0, 0)), tail=(0, -1), flick=2))], 8, False)
    put("hurt_s", [draw_s(Pose(bob=-1, head=(0, -2), eyes="squint", mouth="open", ears="flat", flick=2,
                               paws=((-1, -1), (1, -1), (0, 0), (0, 0))))], 8, False)
    put("hurt_n", [draw_n(Pose(bob=-1, head=(0, 2), ears="flat", flick=2, tail=(1, -1)))], 8, False)

    # stunned: dizzy sway, swirly eyes, little stars
    put("stunned_s", [draw_s(Pose(sway=-1, x=1, eyes="swirl", ears="back", mouth="open", flick=0, stars=0, bob=1)),
                      draw_s(Pose(sway=1, x=-1, eyes="swirl", ears="back", mouth="open", flick=2, stars=1, bob=1))], 6)

    # ko: wobble -> collapse -> lying on its side, ember tiny and dim
    put("ko_s", [draw_s(Pose(bob=1, sway=-1, head=(0, 2), eyes="squint", ears="back", flick=1, dim=1)),
                 draw_s(Pose(bob=4, head=(0, 5), eyes="closed", ears="flat", paws=((-2, 0), (2, 0), (-1, 0), (1, 0)),
                             flick=2, dim=1, ember=0.8)),
                 draw_lie(Pose(eyes="closed", ember=0.6, dim=2, flick=0, tongue=1.0))], 6, False)

    # victory: happy hop, ember flares
    put("victory_s", [draw_s(Pose(bob=2, ears="back", eyes="happy", mouth="smile", flick=0, ember=1.1)),
                      draw_s(Pose(lift=3, stretch=-1, eyes="happy", mouth="open", flick=1, ember=1.25, tongue=4.5,
                                  paws=((0, 1), (0, 1), (0, 0), (0, 0)), tail=(0, 2), tail_mid=(0, 1))),
                      draw_s(Pose(lift=4, eyes="happy", mouth="open", flick=0, ember=1.3, tongue=4.0,
                                  paws=((-1, -2), (1, -2), (0, 0), (0, 0)), tail=(1, 3), tail_mid=(0, 2))),
                      draw_s(Pose(bob=1, eyes="happy", mouth="smile", flick=3, ember=1.2, tongue=4.5))], 8)

    # cower: curled tight, ears flat, trembling, ember small and weak
    put("cower_s", [draw_curl_s(Pose(eyes="wide", ears="flat", ember=0.6, dim=1, flick=0, tongue=1.5, tremble=0), tight=True),
                    draw_curl_s(Pose(eyes="wide", ears="flat", ember=0.6, dim=1, flick=1, tongue=1.5, tremble=1), tight=True)], 3)
    # curl: asleep, ember steady and warm
    put("curl_s", [draw_curl_s(Pose(eyes="sleep", ears="back", ember=0.9, flick=0, tongue=2.0, bob=0)),
                   draw_curl_s(Pose(eyes="sleep", ears="back", ember=0.9, flick=1, tongue=2.2, bob=1))], 2)
    # happy: bouncing in place
    put("happy_s", [draw_s(Pose(bob=1, eyes="happy", mouth="smile", flick=0, tail=(-1, 0))),
                    draw_s(Pose(lift=2, eyes="happy", mouth="open", flick=1, tail=(1, 1))),
                    draw_s(Pose(lift=3, stretch=-1, eyes="happy", mouth="open", flick=2, tail=(2, 2), tail_mid=(0, 1))),
                    draw_s(Pose(lift=1, eyes="happy", mouth="smile", flick=3, tail=(0, 0)))], 10)
    return A


ORDER = ["idle_s", "idle_n", "idle_e", "ready_s", "ready_n", "ready_e", "move_s", "move_n", "move_e",
         "dash_windup_s", "dash_windup_n", "dash_windup_e", "dash_s", "dash_n", "dash_e",
         "dash_land_s", "dash_land_n", "dash_land_e", "ram_s", "ram_n", "ram_e",
         "cast_s", "cast_n", "cast_e", "melee_s", "melee_n", "melee_e", "focus_s", "focus_n", "focus_e",
         "guard_s", "guard_n", "guard_e", "hurt_s", "hurt_n", "hurt_e", "stunned_s", "ko_s", "victory_s",
         "cower_s", "curl_s", "happy_s"]


def build(out_dir: str) -> SheetBuilder:
    A = animations()
    assert set(A) == set(ORDER), set(A) ^ set(ORDER)
    sb = SheetBuilder("emberlyn", W, H, PIVOT, columns=8, pixels_per_unit=PPU,
                      meta={"kind": "kith", "element": "ember", "generator": "tools/sprite_forge/emberlyn.py",
                            "scale": S})
    for name in ORDER:
        frames, fps, loop = A[name]
        for i, f in enumerate(frames):
            pix.check_frame(f, f"emberlyn {name}[{i}]")
        sb.add_animation(name, frames, fps, loop)
    sb.save(out_dir)
    return sb


if __name__ == "__main__":
    import preview
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "sprites", "kith")
    sb = build(out)
    print(preview.contact(os.path.join(out, "emberlyn.png")))
    print(preview.strips(sb))
