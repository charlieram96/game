"""Lanternmoth -- Hesper's partner kith (48x48, pivot 24,46).

A large, gentle moth: dusky plum wings with aether-tinted edges and eye-spots, a
fuzzy cream thorax, feathery antennae, and a softly glowing lantern-like abdomen.
It hovers (body centre around y=22) with a four-frame wing flap.
"""

from __future__ import annotations

import math
import sys

import numpy as np

import pix
from kit import Canvas
from pix import Shape, bezier, col

sys.path.insert(0, "/home/user/game/tools")
from common.sheet import SheetBuilder  # noqa: E402
from portraits import installed_by_art_forge  # noqa: E402

W = H = 48
PIVOT = (24, 46)
WING, EDGE, FUZZ = "cloth_plum", "aether", "cream"
SPOT_RING = col("cloth_plum", 0)
SPOT_IN = col("aether", 4)
SPOT_HI = col("aether", 6)
EYE = col("ink", 0)
EYE_HI = col("aether", 5)


def _wing(cv, pts, z, base=3, offset=0, group="wing"):
    s = cv.poly(pts, bevel=2.6)
    return cv.add(s, WING, base, z, group=group, contour=1, offset=offset)


def _edge(cv, wing_part, pts_line, z):
    """Aether-tinted leading edge band inside the wing."""
    m = wing_part.shape.mask & cv.tube(pts_line, [1.2] * len(pts_line)).mask
    if m.any():
        cv.add(wing_part.shape.clip(m), EDGE, 3, z, group=wing_part.group)


def _spot(cv, x, y, r=2.0, z=None):
    x, y = int(round(x)), int(round(y))
    if r >= 2.0:
        cv.grid([".ooo.", "oiiio", "oiWio", "oiiio", ".ooo."], x - 2, y - 2, {"o": SPOT_RING, "i": SPOT_IN, "W": SPOT_HI})
    else:
        cv.grid([".o.", "oWo", ".o."], x - 1, y - 1, {"o": SPOT_RING, "W": SPOT_IN})


def _abdomen(cv, top, length, z, tilt=0.0, glow=1.0, pulse=0):
    """Segmented glowing lantern abdomen hanging from (top) downward."""
    tx, ty = top
    pts = [(tx, ty), (tx + tilt * 0.5, ty + length * 0.5), (tx + tilt, ty + length)]
    s = cv.tube(pts, [2.6, 3.2, 1.8])
    X, Y = pix._grid(cv.w, cv.h)
    d = (Y - ty) / max(1.0, length)
    idx = np.full((cv.h, cv.w), 4)
    idx[d > (0.25 - 0.12 * pulse)] = 5
    idx[d > (0.55 - 0.14 * pulse)] = 6
    idx[d > 0.92] = 5
    # segment rings
    for k in (0.3, 0.55, 0.78):
        ring = np.abs(Y - (ty + length * k)) < 0.5
        idx[ring & s.mask] = 3
    part = cv.add(s, "gold", 5, z, idx=idx, oc=col("gold", 1), cast=0, recv=False, glow=False, group="abd")
    cv.fig.glows.append((tx + tilt * 0.7, ty + length * 0.7, (9.0 + pulse) * glow, 1))
    return part


def _antenna(cv, base, tip, bend, z):
    pts = bezier([base, ((base[0] + tip[0]) / 2 + bend[0], (base[1] + tip[1]) / 2 + bend[1]), tip], 8)
    line = []
    for (x, y) in pts:
        p = (int(math.floor(x)), int(math.floor(y)))
        if not line or line[-1] != p:
            line.append(p)
    c = col(FUZZ, 3)
    barb = col(FUZZ, 2)
    for i, (x, y) in enumerate(line):
        cv.dot(x, y, c, post=False)
        if 1 <= i < len(line) - 1 and i % 2 == 0:
            dx = 1 if tip[0] > base[0] else -1
            cv.dot(x + dx, y + 1, barb)
            cv.dot(x - dx, y - 1 if i > 3 else y + 1, barb)


# wing keyframes (right side, S view): forewing / hindwing polygons per flap phase
def _wings_s(phase):
    """phase 0 up, 1 mid, 2 down, 3 mid (recovering)."""
    up = [1.0, 0.45, -0.25, 0.45][phase]
    fy = 20 - 15 * up       # forewing tip y
    fx = 44 - 3 * abs(up - 0.4)
    fore = [(25.0, 18.0), (29.0, 13.0 - 6 * up), (36.0, fy - 1.0), (fx, fy + 1.0), (fx - 1.0, fy + 6.0), (38.0, 21.0 - 1 * up),
            (32.0, 23.0), (26.0, 22.0)]
    hy = 30 - 4 * up
    hind = [(25.0, 22.0), (33.0, 22.0 - up), (39.0, hy - 3.0), (37.0, hy + 2.0), (31.0, hy + 2.6), (26.0, 27.0)]
    spot = ((36.0 + fx) / 2 - 1.0, (fy + 21.0) / 2 + 0.6)
    hspot = (33.4, hy - 1.0)
    return fore, hind, spot, hspot, up


def draw_s(phase: int, bob: float = 0.0, pulse: int = 0):
    cv = Canvas(W, H)
    fore, hind, spot, hspot, up = _wings_s(phase)
    oy = bob
    sh = lambda pts: [(x, y + oy) for (x, y) in pts]  # noqa: E731
    mirror = lambda pts: [(48.0 - x, y) for (x, y) in pts]  # noqa: E731
    parts = []
    for side in (0, 1):
        f = sh(fore) if side else sh(mirror(fore))
        h = sh(hind) if side else sh(mirror(hind))
        hp = _wing(cv, h, 1, base=3, offset=-1, group=f"hind{side}")
        fp = _wing(cv, f, 2, base=3, group=f"fore{side}")
        lead = [f[0], f[1], f[2], f[3]]
        _edge(cv, fp, lead, 2.1)
        sx, sy = spot
        _spot(cv, sx if side else 48.0 - sx, sy + oy, 2.0)
        hx, hy = hspot
        _spot(cv, hx if side else 48.0 - hx, hy + oy, 1.0)
    # body: abdomen lantern, fuzzy thorax, head, antennae
    _abdomen(cv, (24.0, 22.0 + oy), 10.0, 3, pulse=pulse)
    thor = cv.ell(24.0, 18.6 + oy, 3.6, 3.4)
    for a in range(10):
        ang = a * 2 * math.pi / 10
        thor = thor | cv.circ(24.0 + 3.2 * math.cos(ang), 18.6 + oy + 3.0 * math.sin(ang), 1.2)
    cv.add(thor, FUZZ, 3, 4, group="thorax", contour=1)
    head = cv.ell(24.0, 14.0 + oy, 2.8, 2.4)
    cv.add(head, FUZZ, 4, 5, group="head", contour=1)
    for ex in (21, 25):
        cv.grid(["ee", "eh"], ex, int(13 + oy), {"e": EYE, "h": EYE_HI})
    _frond(cv, (22.6, 12.0 + oy), (17.0, 5.0 + oy), (-1.2, 1.4), side=-1)
    _frond(cv, (25.4, 12.0 + oy), (31.0, 5.0 + oy), (1.2, 1.4), side=1)
    return cv.render()


def _frond(cv, base, tip, bend, side=1):
    """Short feathery antenna: a curved stem with barbs on one side."""
    pts = bezier([base, ((base[0] + tip[0]) / 2 + bend[0], (base[1] + tip[1]) / 2 + bend[1]), tip], 7)
    line = []
    for (x, y) in pts:
        p = (int(math.floor(x)), int(math.floor(y)))
        if not line or line[-1] != p:
            line.append(p)
    for i, (x, y) in enumerate(line):
        cv.dot(x, y, col(FUZZ, 3))
        if 1 <= i < len(line) - 1 and i % 2 == 1:
            cv.dot(x - side, y, col(FUZZ, 2))


# near forewing keyframes (east view): up, mid, down, mid
FORE_E = [
    [(25.0, 18.0), (24.5, 10.0), (20.0, 4.6), (13.6, 4.4), (10.6, 8.6), (12.6, 15.0), (19.0, 20.6), (23.6, 21.0)],
    [(25.0, 18.4), (21.6, 13.0), (14.0, 10.6), (8.4, 12.4), (8.0, 17.0), (12.6, 20.6), (20.6, 22.0)],
    [(25.0, 19.0), (20.6, 17.4), (13.0, 17.6), (7.6, 20.4), (8.6, 24.6), (14.0, 26.0), (21.6, 23.6)],
    [(25.0, 18.4), (21.6, 13.6), (14.0, 11.4), (8.4, 13.2), (8.0, 17.8), (12.6, 21.2), (20.6, 22.4)],
]
HIND_E = [
    [(23.0, 22.0), (16.6, 22.4), (12.4, 26.6), (14.6, 31.0), (20.6, 28.0)],
    [(23.0, 22.0), (16.0, 23.4), (11.6, 27.4), (14.0, 31.4), (20.6, 28.4)],
    [(23.0, 22.4), (16.6, 25.6), (13.4, 30.0), (16.4, 33.0), (21.6, 28.6)],
    [(23.0, 22.0), (16.0, 23.6), (11.6, 27.6), (14.0, 31.6), (20.6, 28.4)],
]


def draw_e(phase: int, bob: float = 0.0, pulse: int = 0):
    """Side view facing right."""
    cv = Canvas(W, H)
    oy = bob
    sh = lambda pts, dx=0.0, dy=0.0: [(x + dx, y + oy + dy) for (x, y) in pts]  # noqa: E731
    # far wings peek out behind (offset up/back, darker)
    _wing(cv, sh(FORE_E[phase], -2.0, -1.4), 1, base=2, offset=-1, group="farfore")
    _wing(cv, sh(HIND_E[phase], -1.4, -0.6), 0.5, base=2, offset=-1, group="farhind")
    # abdomen lantern hanging down-back
    _abdomen(cv, (22.4, 21.6 + oy), 9.4, 3, tilt=-2.6, pulse=pulse)
    thor = cv.ell(24.4, 19.4 + oy, 3.4, 3.2)
    for a in range(10):
        ang = a * 2 * math.pi / 10
        thor = thor | cv.circ(24.4 + 3.0 * math.cos(ang), 19.4 + oy + 2.8 * math.sin(ang), 1.2)
    cv.add(thor, FUZZ, 3, 4, group="thorax", contour=1)
    head = cv.ell(28.8, 17.6 + oy, 2.6, 2.4)
    cv.add(head, FUZZ, 4, 5, group="head", contour=1)
    cv.grid(["ee", "eh"], 29, int(16 + oy), {"e": EYE, "h": EYE_HI})
    _frond(cv, (29.4, 15.4 + oy), (34.6, 9.0 + oy), (1.4, 0.4), side=1)
    _frond(cv, (28.2, 15.2 + oy), (31.6, 8.0 + oy), (0.6, 0.6), side=1)
    # near wings
    hp = _wing(cv, sh(HIND_E[phase]), 6, base=3, group="nhind")
    fp = _wing(cv, sh(FORE_E[phase]), 7, base=3, group="nfore")
    _edge(cv, fp, sh(FORE_E[phase])[:4], 7.1)
    bb = fp.shape.bbox()
    if bb:
        _spot(cv, (bb[0] + bb[2]) / 2 - 0.4, (bb[1] + bb[3]) / 2 + 0.4, 2.0)
    hb = hp.shape.bbox()
    if hb:
        _spot(cv, (hb[0] + hb[2]) / 2, (hb[1] + hb[3]) / 2 + 0.5, 1.0)
    return cv.render()


def animations():
    A = {}
    bobs = [0.0, 0.0, 1.0, 1.0]
    pulses = [0, 1, 1, 0]
    A["hover_s"] = ([draw_s(k, bobs[k], pulses[k]) for k in range(4)], 8, True)
    A["hover_e"] = ([draw_e(k, bobs[k], pulses[k]) for k in range(4)], 8, True)
    return A


ORDER = ["hover_s", "hover_e"]


def build(out_dir: str):
    if installed_by_art_forge(out_dir, "lanternmoth"):
        print("  kith        lanternmoth          kept (HD sheet from tools/art_forge)")
        return []
    A = animations()
    sb = SheetBuilder("lanternmoth", W, H, PIVOT, columns=8, meta={"kind": "kith", "element": "light", "partner_of": "hesper",
                                                                   "generator": "tools/sprite_forge/lanternmoth.py"})
    for name in ORDER:
        frames, fps, loop = A[name]
        for i, f in enumerate(frames):
            pix.check_frame(f, f"lanternmoth {name}[{i}]")
        sb.add_animation(name, frames, fps, loop)
    sb.save(out_dir)
    return sb


if __name__ == "__main__":
    import preview
    sb = build("/home/user/game/assets/sprites/kith")
    print(preview.strips(sb, scale=5))
