"""Stoneback -- heavy stone-element kith (48x48, pivot 24,44).

A compact pangolin/armadillo-like quadruped: overlapping slate plates down its
back, a thick moss ridge with tiny flowers, stubby warm-hide legs, a broad
blunt snout, small glowing amber eyes under a heavy stone brow and a short tail
ending in a stone club. Stubborn and sleepy; it can curl into a rolling ball.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, replace

import numpy as np

import pix
from kit import Canvas, Xf, ell_x, rim_highlight, tube_x
from pix import col

sys.path.insert(0, "/home/user/game/tools")
from common.sheet import SheetBuilder  # noqa: E402

W = H = 48
PIVOT = (24, 44)
GROUND = 43.0
STONE, HIDE, MOSS, GMOSS = "stone", "stone_warm", "moss", "glow_moss"

EYE = col("ember", 5)
EYE_HI = col("ember", 6)
EYE_LO = col("ember", 4)
LID = col("stone", 1)
NOSE = col("stone_warm", 0)
NOSE_HI = col("stone_warm", 2)
MOUTH = col("stone_warm", 1)
CLAW = col("cream", 2)
PETAL = col("cloth_cream", 5)
PETAL_Y = col("gold", 5)
POLLEN = col("gold", 4)
POLLEN_O = col("ember", 4)
DUST = col("sand", 4)
DUST2 = col("sand", 3)
STEAM = col("cloth_cream", 4)
SMEAR = col("cloth_cream", 5)
BUB = col("water", 5)
BUB_HI = col("water", 6)


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
    eyes: str = "sleepy"             # sleepy | open | closed | squint | swirl | happy
    mouth: str = "closed"            # closed | open
    tail: tuple = (0.0, 0.0)
    plates: float = 0.0              # raised plates (guard)
    glow: int = 0                    # moss glow level (focus) 0..2
    smear: tuple = ()
    rock: tuple = ()                 # (x, y) of a lifted rock chunk
    dust: tuple = ()                 # dust puff centres
    stars: int = -1
    steam: bool = False
    breath: float = 0.0              # shell swell (px)
    feet_rot: bool = False           # feet follow the body rotation (tipping over)
    bubble: int = 0                  # sleep bubble size (0 none)
    curl_tail: bool = False          # tail wrapped around the front (sleeping)


# ----------------------------------------------------------------------------
# details


def _eyes(cv, pts, state, side=False):
    for (x, y) in pts:
        x, y = int(math.floor(x)), int(math.floor(y))
        if state == "sleepy":
            cv.grid(["LL", "eE"], x, y, {"L": LID, "e": EYE, "E": EYE_LO})
        elif state == "open":
            cv.grid(["eh", "eE"], x, y, {"e": EYE, "h": EYE_HI, "E": EYE_LO})
        elif state == "closed":
            cv.grid(["..", "LL"], x, y, {"L": LID})
        elif state == "happy":
            cv.grid([".L", "L."] if side else ["LL", ".."], x, y, {"L": LID})
        elif state == "squint":
            cv.grid(["L.", ".L"], x, y, {"L": LID})
        elif state == "swirl":
            cv.grid(["hE", "Eh"], x, y, {"h": EYE_HI, "E": EYE_LO})


def _flower(cv, x, y, kind=0):
    x, y = int(round(x)), int(round(y))
    if kind == 0:
        cv.grid([".p.", "pcp", ".p."], x - 1, y - 1, {"p": PETAL, "c": POLLEN})
    elif kind == 1:
        cv.grid([".p.", "pcp", ".p."], x - 1, y - 1, {"p": PETAL_Y, "c": POLLEN_O})
    else:
        cv.grid(["pp", "pc"], x, y - 1, {"p": PETAL, "c": POLLEN})


def _dust(cv, pts):
    for (x, y) in pts:
        cv.grid([".dd.", "dDDd", ".dd."], int(x) - 2, int(y) - 1, {"d": DUST2, "D": DUST}, post=True)


def _steam(cv, x, y):
    cv.grid([".s.", "s.s", ".s."], int(x), int(y), {"s": STEAM}, post=True)


def _stars(cv, hx, hy, phase):
    if phase < 0:
        return
    star = [".s.", "sSs", ".s."]
    pal = {"s": col("gold", 4), "S": col("gold", 5)}
    pos = [(-9, -6), (6, -8)] if phase % 2 == 0 else [(-5, -9), (9, -5)]
    for dx, dy in pos:
        cv.grid(star, int(hx + dx), int(hy + dy), pal, post=True)


def _rock(cv, x, y, z=20):
    pts = [(x - 4.0, y + 1.0), (x - 2.6, y - 2.8), (x + 1.0, y - 3.6), (x + 4.0, y - 1.2), (x + 3.6, y + 2.4), (x - 0.6, y + 3.2)]
    cv.add(cv.poly(pts, bevel=2.0), HIDE, 3, z, group="rock", contour=1)


def _smear_pts(cv, pts):
    for (x, y) in pts:
        cv.fig.post.append((int(x), int(y), SMEAR))


def arc_pts(cx, cy, r, a0, a1, n=14, thick=1):
    out = []
    for i in range(n):
        a = a0 + (a1 - a0) * i / (n - 1)
        for t in range(thick):
            out.append((cx + (r - t) * math.cos(a), cy + (r - t) * math.sin(a)))
    return tuple(out)


# ----------------------------------------------------------------------------
# shell plates


def _bands(cv, shell, keyfn, bounds, z, front_dir, base=3, raised=0.0, glowing=False):
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
        parts.append(cv.add(band, STONE, base, zz, group=f"plate{k}", contour=1, cast=1))
    for k in range(len(parts)):
        nbr = k - 1 if front_dir > 0 else k + 1
        if 0 <= nbr < len(parts):
            rim_highlight(parts[k], [parts[nbr].shape.mask], steps=1, amount=1)
    return parts


def _moss_ridge(cv, centers, z, glow=0, flowers=()):
    ramp = GMOSS if glow else MOSS
    m = cv.empty()
    for (x, y, rx, ry) in centers:
        m = m | cv.ell(x, y, rx, ry)
    part = cv.add(m, ramp, 3 + (1 if glow >= 2 else 0), z, group="moss", contour=1, cast=1, hi=5)
    for (x, y, k) in flowers:
        _flower(cv, x, y, k)
    if glow:
        bb = m.bbox()
        if bb:
            cv.fig.glows.append(((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, 8 + glow * 2, 1))
    return part


# ----------------------------------------------------------------------------
# EAST


def draw_e(p: Pose):
    cv = Canvas(W, H)
    xf = Xf(p.x + 1.0, p.y - p.lift + p.bob, p.rot, p.rpx, p.rpy)
    gx = Xf(p.x + 1.0, p.y - p.lift, p.rot if p.feet_rot else 0.0, p.rpx, p.rpy)   # feet frame (no bob)
    Xl, Yl = xf.local_grid(W, H)
    f = p.feet
    br = p.breath
    tuck = p.tuck

    def leg(top, foot, r, z, offset=0, group=None, contour=1, fr=(3.1, 1.3)):
        ft = gx.pt(foot[0], foot[1])
        tp = xf.pt(*top)
        s = cv.tube([tp, (ft[0], ft[1] + 0.3 - r * 0.95)], [r, r * 0.95]) | cv.ell(ft[0] + 0.8, ft[1], fr[0], fr[1])
        cv.add(s, HIDE, 4, z, offset=offset, group=group, contour=contour)
        if offset == 0:
            cx = int(math.floor(ft[0] + 0.8 + fr[0] - 0.6))
            cv.dot(cx, int(math.floor(ft[1] + 0.6)), CLAW)
            cv.dot(cx - 2, int(math.floor(ft[1] + 0.6)), CLAW)

    # far legs
    leg((28.4, 36.0), (28.6 + f[1][0], GROUND - 0.4 + f[1][1]), 2.4, 1, offset=-1, group="fl", contour=None)
    leg((17.6, 36.0), (17.8 + f[3][0], GROUND - 0.4 + f[3][1]), 2.6, 1, offset=-1, group="hl", contour=None)

    # tail + club
    t = p.tail
    tail = tube_x(cv, xf, [(11.0, 35.5), (8.4, 38.0), (6.8 + t[0] * 0.5, 39.0 + t[1] * 0.5)], [2.9, 2.5, 2.2])
    cv.add(tail, STONE, 3, 2, group="tail", contour=1)
    cly = 39.0 + t[1]
    cly -= max(0.0, xf.pt(5.4 + t[0], cly + 3.0)[1] - 43.2)
    club = ell_x(cv, xf, 5.4 + t[0], cly, 3.2, 3.0)
    cv.add(club, STONE, 2, 2.5, group="club", contour=1, spec=True)

    # head (under the front lip of the shell)
    hx, hy = 36.2 + p.head[0] - tuck * 4.0, 34.6 + p.head[1] + tuck * 2.0
    hy -= max(0.0, max(xf.pt(hx + 4.4, hy + 5.1)[1], xf.pt(hx, hy + 4.8)[1]) - 43.2)
    skull = ell_x(cv, xf, hx, hy, 5.4, 4.8)
    snout = ell_x(cv, xf, hx + 4.4, hy + 2.0, 4.0, 3.1)
    cv.add(skull | snout, HIDE, 4, 4, group="head", contour=1)
    brow = ell_x(cv, xf, hx - 0.2, hy - 3.6, 5.4, 2.4, angle=-0.16)
    cv.add(brow, STONE, 3, 4.5, group="brow", contour=1, cast=1)
    ex, ey = xf.pt(hx + 1.2, hy - 1.6)
    _eyes(cv, [(ex, ey)], p.eyes, side=True)
    nx, ny = xf.pt(hx + 7.4, hy + 0.6)
    cv.grid(["nh", "nn"], int(nx) - 1, int(ny), {"n": NOSE, "h": NOSE_HI})
    mx, my = xf.pt(hx + 4.2, hy + 3.6)
    if p.mouth == "open":
        cv.grid(["mmm", ".mm"], int(mx), int(my), {"m": MOUTH})
    else:
        cv.grid(["mmm"], int(mx), int(my), {"m": MOUTH})

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
    lower_parts = _bands(cv, shell.clip(~upper), key, [12.0, 16.8, 21.6, 26.4, 31.2], 5, +1)
    upper_parts = _bands(cv, shell.clip(upper), key, [14.2, 19.0, 23.8, 28.6], 5.5, +1)

    # moss ridge with flowers along the top
    top = lambda x: cy - ry * math.sqrt(max(0.0, 1 - ((x - cx) / rx) ** 2))
    cents = []
    for i, (mx_, rr) in enumerate([(13.2, 2.0), (15.8, 2.4), (18.6, 2.6), (21.6, 2.8), (24.6, 2.6), (27.4, 2.4), (30.0, 2.0)]):
        px_, py_ = xf.pt(mx_, top(mx_) + 0.9)
        cents.append((px_, py_, rr + 0.2, 2.0 + (0.3 if i % 2 else 0.0)))
    fl = [xf.pt(17.4, top(17.4) - 1.0) + (0,), xf.pt(24.0, top(24.0) - 1.2) + (1,), xf.pt(28.6, top(28.6) - 0.6) + (0,)]
    _moss_ridge(cv, cents, 6, p.glow, fl)

    if p.rock:
        _rock(cv, *p.rock)
    _dust(cv, p.dust)
    if p.steam:
        _steam(cv, nx + 2, ny - 4)
    _smear_pts(cv, p.smear)
    _stars(cv, hx, hy - 6, p.stars)
    return cv.render()


# ----------------------------------------------------------------------------
# SOUTH


def draw_s(p: Pose):
    cv = Canvas(W, H)
    xf = Xf(p.x, p.y - p.lift + p.bob, p.rot, p.rpx, p.rpy)
    gx = Xf(p.x, p.y - p.lift, p.rot if p.feet_rot else 0.0, p.rpx, p.rpy)
    Xl, Yl = xf.local_grid(W, H)
    f = p.feet
    br = p.breath
    tuck = p.tuck

    def leg(top, foot, r, z, group, offset=0, claws=True):
        ft = gx.pt(*foot)
        tp = xf.pt(*top)
        s = cv.tube([tp, (ft[0], ft[1] + 0.3 - r * 0.95)], [r, r * 0.95]) | cv.ell(ft[0], ft[1], 3.4, 1.4)
        cv.add(s, HIDE, 4, z, group=group, contour=1, offset=offset)
        if claws and offset == 0:
            y = int(math.floor(ft[1] + 0.7))
            for dx in (-1, 1):
                cv.dot(int(math.floor(ft[0])) + dx, y, CLAW)

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
    _bands(cv, shell, key, [26.6, 30.2, 33.8, 37.0], 5, +1)
    cents = [(cx, 24.6, 5.6, 2.6), (cx - 4.0, 25.6, 2.6, 2.0), (cx + 4.2, 25.4, 2.6, 2.0), (cx - 1.4, 23.2, 2.8, 1.8),
             (cx + 1.8, 23.4, 2.4, 1.8)]
    cents = [xf.pt(x, y) + (a, b) for (x, y, a, b) in cents]
    fl = [xf.pt(cx - 3.4, 23.6) + (0,), xf.pt(cx + 3.0, 22.6) + (1,), xf.pt(cx + 0.4, 25.8) + (2,)]
    _moss_ridge(cv, cents, 6, p.glow, fl)

    # front legs at the sides, emerging from under the shell rim
    leg((15.8, 37.6), (15.2 + f[0][0], GROUND - 0.4 + f[0][1]), 2.8, 4.6, "lf")
    leg((32.2, 37.6), (32.8 + f[1][0], GROUND - 0.4 + f[1][1]), 2.8, 4.6, "rf")

    # head emerging under the front lip
    hx, hy = cx + p.head[0], 36.2 + p.head[1] + tuck * 3.0
    hy -= max(0.0, xf.pt(hx, hy + 5.8)[1] - 43.2)
    hz = 8 if tuck < 0.5 else 4
    skull = ell_x(cv, xf, hx, hy, 6.8, 4.8)
    snout = ell_x(cv, xf, hx, hy + 2.8, 5.0, 3.0)
    cv.add(skull | snout, HIDE, 4, hz, group="head", contour=1)
    brow = ell_x(cv, xf, hx, hy - 3.2, 7.4, 2.5)
    cv.add(brow, STONE, 3, hz + 0.5, group="brow", contour=1, cast=1)
    if tuck < 0.8:
        _eyes(cv, [xf.pt(hx - 4.4, hy - 1.4), xf.pt(hx + 2.4, hy - 1.4)], p.eyes)
        n1 = xf.pt(hx - 1.6, hy + 2.0)
        cv.grid(["n..n", "...."], int(n1[0]), int(n1[1]), {"n": NOSE})
        m1 = xf.pt(hx - 2.0, hy + 4.2)
        if p.mouth == "open":
            cv.grid([".mmm.", "mmmmm"], int(m1[0]) - 1, int(m1[1]), {"m": MOUTH})
        else:
            cv.grid(["mmmmm"], int(m1[0]) - 1, int(m1[1]), {"m": MOUTH})
        if p.steam:
            _steam(cv, hx - 11, hy + 0)
            _steam(cv, hx + 8, hy - 1)
        if p.bubble:
            bx, by = int(n1[0]) + 5, int(n1[1]) - 1
            if p.bubble == 1:
                cv.grid([".bb.", "bwbb", "bbbb", ".bb."], bx, by - 2, {"b": BUB, "w": BUB_HI}, post=True)
            else:
                cv.grid(["..bbb..", ".bwwbb.", "bwbbbbb", "bbbbbbb", "bbbbbbb", ".bbbbb.", "..bbb.."], bx, by - 5,
                        {"b": BUB, "w": BUB_HI}, post=True)
    if p.curl_tail:
        # tail wrapped round the front-left, club resting by the snout
        ct = tube_x(cv, gx, [(11.6, 37.0), (9.6, 39.6), (11.6, 41.0), (14.6, 41.0)], [2.6, 2.6, 2.4, 2.2])
        cv.add(ct, STONE, 3, 8.6, group="ctail", contour=1)
        cv.add(ell_x(cv, gx, 16.2, 40.4, 2.9, 2.5), STONE, 2, 8.7, group="cclub", contour=1, spec=True)
    if p.rock:
        _rock(cv, *p.rock)
    _dust(cv, p.dust)
    _smear_pts(cv, p.smear)
    _stars(cv, hx, hy - 10, p.stars)
    return cv.render()


# ----------------------------------------------------------------------------
# NORTH


def draw_n(p: Pose):
    cv = Canvas(W, H)
    xf = Xf(p.x, p.y - p.lift + p.bob, p.rot, p.rpx, p.rpy)
    gx = Xf(p.x, p.y - p.lift, p.rot if p.feet_rot else 0.0, p.rpx, p.rpy)
    Xl, Yl = xf.local_grid(W, H)
    f = p.feet
    br = p.breath

    def leg(top, foot, r, z, group, offset=0):
        ft = gx.pt(*foot)
        tp = xf.pt(*top)
        s = cv.tube([tp, (ft[0], ft[1] + 0.3 - r * 0.95)], [r, r * 0.95]) | cv.ell(ft[0], ft[1], 3.0, 1.3)
        cv.add(s, HIDE, 4, z, group=group, contour=1, offset=offset)

    # front feet far ahead at the sides
    leg((13.0, 34.0), (12.6 + f[0][0], 38.6 + f[0][1]), 2.2, 1, "lf", offset=-1)
    leg((35.0, 34.0), (35.4 + f[1][0], 38.6 + f[1][1]), 2.2, 1, "rf", offset=-1)
    # the brow plate of the head peeks over the far edge when rearing
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
    _bands(cv, shell, key, [26.6, 30.2, 33.8, 37.0], 5, -1)
    cents = [(cx, 24.4, 5.6, 2.6), (cx - 4.0, 25.4, 2.6, 2.0), (cx + 4.2, 25.6, 2.6, 2.0), (cx - 1.0, 23.0, 2.6, 1.8),
             (cx + 1.6, 26.6, 3.0, 1.8)]
    cents = [xf.pt(x, y) + (a, b) for (x, y, a, b) in cents]
    fl = [xf.pt(cx - 2.6, 23.6) + (1,), xf.pt(cx + 3.6, 24.8) + (0,)]
    _moss_ridge(cv, cents, 6, p.glow, fl)
    # hind legs (near)
    leg((16.4, 37.6), (16.0 + f[2][0], GROUND - 0.4 + f[2][1]), 2.7, 4.6, "hl")
    leg((31.6, 37.6), (32.0 + f[3][0], GROUND - 0.4 + f[3][1]), 2.7, 4.6, "hr")
    # tail with club, toward the camera
    t = p.tail
    cly = 40.0 + t[1] * 0.5
    cly -= max(0.0, xf.pt(27.0 + t[0], cly + 2.8)[1] - 43.2)
    tail = tube_x(cv, xf, [(23.0, 35.0), (24.6 + t[0] * 0.5, 37.6), (26.4 + t[0], cly - 0.6)], [2.8, 2.5, 2.2])
    cv.add(tail, STONE, 3, 8, group="tail", contour=1)
    club = ell_x(cv, xf, 27.6 + t[0], cly, 3.2, 2.8)
    cv.add(club, STONE, 2, 8.5, group="club", contour=1, spec=True)
    if p.rock:
        _rock(cv, *p.rock)
    _dust(cv, p.dust)
    _smear_pts(cv, p.smear)
    _stars(cv, cx, 22, p.stars)
    return cv.render()


# ----------------------------------------------------------------------------
# special poses


def draw_ball(phase: float, face: str = "", breath: float = 0.0, x: float = 0.0, glow: int = 0):
    """Curled into a stone ball. phase in [0,1) rotates the plates (rolling toward the camera)."""
    cv = Canvas(W, H)
    cx, cy, r = 24.0 + x, 33.0 - breath * 0.5, 10.6 + breath * 0.5
    X, Y = pix._grid(W, H)
    ball = cv.ell(cx, cy, r, r, rz=r)
    # latitude seams sweep downward as the ball rolls toward the camera
    spacing = 0.62  # radians between seams
    seams = []
    for k in range(-6, 7):
        th = (k + phase) * spacing
        if -1.45 < th < 1.45:
            seams.append(cy + r * math.sin(th) * 0.98)
    key = Y - 0.035 * (X - cx) ** 2 * (1.0 - 0.0)
    seams = sorted(seams)
    _bands(cv, ball, key, seams, 5, +1)
    # moss stripe along the spine (rolling plane) -- stays centred, flowers ride the rotation
    stripe = cv.empty()
    for k in range(-4, 5):
        th = (k * 0.5 + phase * 0.5 * 2) * 0.62
        if -1.35 < th < 1.35:
            yy = cy + r * math.sin(th) * 0.98
            ww = 1.7 * math.cos(th) + 0.7 + (0.5 if k % 2 else 0.0)
            stripe = stripe | cv.ell(cx + (0.5 if k % 2 else -0.5), yy, ww, 1.7)
    stripe = stripe.clip(ball.mask)
    part = cv.add(stripe, GMOSS if glow else MOSS, 3, 6, group="moss", contour=1, cast=1)
    th_f = ((phase * 0.62) + 0.2)
    for k, off in enumerate((-0.9, 0.35)):
        th = off + phase * 0.62 * 2
        th = (th + 1.4) % 2.8 - 1.4
        if -1.1 < th < 1.1:
            _flower(cv, cx + (1 if k else -1), cy + r * math.sin(th) * 0.98, k)
    if face:
        # sleepy face peeking out at the bottom of the curl, chin on the ground
        hx, hy = cx, cy + 7.6
        snout = cv.ell(hx, hy + 0.6, 5.6, 2.6)
        brow = cv.ell(hx, hy - 1.8, 6.6, 1.9)
        cv.add(snout, HIDE, 3, 7, group="face", contour=1)
        cv.add(brow, STONE, 3, 7.5, group="brow", contour=1, cast=1)
        cv.grid([".LL.", "L..L"], int(hx) - 6, int(hy) - 1, {"L": LID})
        cv.grid([".LL.", "L..L"], int(hx) + 2, int(hy) - 1, {"L": LID})
        cv.grid(["n..n"], int(hx) - 2, int(hy + 1.6), {"n": NOSE})
    return cv.render()


def draw_flop(p: Pose):
    """KO: flopped onto its back -- shell rocking on the ground, belly up, stubby legs splayed out."""
    cv = Canvas(W, H)
    cx, cy = 24.0, 38.0
    X, Y = pix._grid(W, H)
    bowl = cv.ell(cx, cy, 13.0, 6.0, rz=8.0).clip(Y > cy - 3.0)
    key = X - 0.04 * (Y - cy) ** 2
    _bands(cv, bowl, key, [14.0, 19.2, 24.4, 29.6], 3, +1)
    # domed belly with soft hide plates
    belly = cv.ell(cx, cy - 3.2, 11.0, 4.6)
    bp = cv.add(belly, HIDE, 3, 6, group="belly", contour=1)
    for xx in (19.0, 24.0, 29.0):
        cv.dots([(int(xx), int(cy - 4.6 + abs(xx - cx) * 0.12) + k) for k in range(3)], col(HIDE, 2))
    # four short stubby legs splayed outward (front pair big, hind pair small)
    legs = [((15.0, 35.6), (11.6, 33.4), 2.6), ((33.0, 35.6), (36.4, 33.4), 2.6),
            ((18.6, 32.0), (17.4, 29.2), 2.2), ((29.4, 32.0), (30.6, 29.2), 2.2)]
    for k, (a, b, r) in enumerate(legs):
        s = cv.tube([a, b], [r, r * 0.9]) | cv.ell(b[0], b[1], r * 1.05, r * 0.9)
        cv.add(s, HIDE, 3, 7 if k < 2 else 5.5, group=f"leg{k}", contour=1, offset=0 if k < 2 else -1)
        cv.dot(int(b[0]), int(b[1]), col(HIDE, 1))
    # head lolling out at the front with dizzy x-eyes
    hx, hy = 24.0, 41.6
    cv.add(cv.ell(hx, hy - 0.4, 5.0, 2.6), HIDE, 3, 8, group="head", contour=1)
    cv.add(cv.ell(hx, hy - 2.4, 5.6, 1.6), STONE, 3, 8.5, group="brow", contour=1)
    cv.grid(["L.L", ".L.", "L.L"], int(hx) - 4, int(hy) - 2, {"L": LID})
    cv.grid(["L.L", ".L.", "L.L"], int(hx) + 2, int(hy) - 2, {"L": LID})
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

    # idle: slow breathing, sleepy blink
    for d, fn in D.items():
        poses = [Pose(breath=0, eyes="sleepy"), Pose(breath=0.6, eyes="sleepy"), Pose(breath=1.0, eyes="closed", bob=0),
                 Pose(breath=0.6, eyes="sleepy")]
        put(f"idle_{d}", [fn(q) for q in poses], 4)

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

    # dash: tucked and charging
    speed = lambda x0, y0: tuple((x0 - i, y0 + 3 * k) for k in range(3) for i in range(3 + (k % 2) * 2))  # noqa: E731
    put("dash_e", [draw_e(Pose(bob=2, rot=0.05, rpx=14, tuck=0.6, eyes="squint", feet=((3, -1), (-2, 0), (-3, 0), (2, -1)),
                               smear=speed(7, 26))),
                   draw_e(Pose(bob=2, rot=0.05, rpx=14, tuck=0.6, eyes="squint", feet=((-1, 0), (3, -1), (2, -1), (-3, 0)),
                               smear=speed(6, 27)))], 12)
    put("dash_s", [draw_s(Pose(bob=2, tuck=0.3, eyes="open", feet=((0, -2), (0, 0), (0, 0), (0, 0)), dust=((11, 42),))),
                   draw_s(Pose(bob=2, tuck=0.3, eyes="open", feet=((0, 0), (0, -2), (0, 0), (0, 0)), dust=((37, 42),)))], 12)
    put("dash_n", [draw_n(Pose(bob=2, feet=((0, 0), (0, 0), (0, -2), (0, 0)), tail=(1, 1))),
                   draw_n(Pose(bob=2, feet=((0, 0), (0, 0), (0, 0), (0, -2)), tail=(-1, 1)))], 12)

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
                    draw_s(Pose(bob=2, eyes="squint", smear=arc_pts(24, 30, 15, 0.35, 2.8, 22))),
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

    # roll: curled ball rolling, plates rotating
    put("roll_s", [draw_ball(k / 4.0) for k in range(4)], 16)
    # sleep: curled and snoozing
    put("sleep_s", [draw_sleep(0), draw_sleep(1)], 2)
    return A


ORDER = ["idle_s", "idle_n", "idle_e", "move_s", "move_n", "move_e", "dash_s", "dash_n", "dash_e", "roll_s",
         "cast_s", "cast_n", "cast_e", "melee_s", "melee_n", "melee_e", "focus_s", "focus_n", "focus_e",
         "guard_s", "guard_n", "guard_e", "hurt_s", "hurt_n", "hurt_e", "stunned_s", "ko_s", "victory_s", "sleep_s"]


def build(out_dir: str) -> SheetBuilder:
    A = animations()
    assert set(A) == set(ORDER), set(A) ^ set(ORDER)
    sb = SheetBuilder("stoneback", W, H, PIVOT, columns=8,
                      meta={"kind": "kith", "element": "stone", "generator": "tools/sprite_forge/stoneback.py"})
    for name in ORDER:
        frames, fps, loop = A[name]
        for i, fr in enumerate(frames):
            pix.check_frame(fr, f"stoneback {name}[{i}]")
        sb.add_animation(name, frames, fps, loop)
    sb.save(out_dir)
    return sb


if __name__ == "__main__":
    import preview
    from preview import lineup
    imgs = [draw_s(Pose()), draw_n(Pose()), draw_e(Pose()), draw_ball(0.0), draw_flop(Pose())]
    print(lineup(imgs, 5, "stoneback_test"))
