"""Emberlyn -- agile ember-element woodland kith (48x48, pivot 24,44).

A long, low stoat/ferret-like body: russet back, cream underside and muzzle, soot
bandit mask and soot paws, small round ears, big amber eyes, and a long bushy
tail that holds a glowing ember coal in a ring of fur. The coal flickers in every
animation (flame tongue varies 1-3px frame to frame).
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, replace

import pix
from kit import Canvas, flame
from pix import bezier, col

sys.path.insert(0, "/home/user/game/tools")
from common.sheet import SheetBuilder  # noqa: E402

W = H = 48
PIVOT = (24, 44)
GROUND = 43.0          # last fill row of planted paws (outline lands on the pivot row 44)

FUR, CREAM, SOOT = "fur_russet", "cream", "soot"


@dataclass
class Pose:
    x: float = 0.0          # whole body shift (screen px)
    y: float = 0.0          # whole body shift (screen px, + = down)
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
    eyes: str = "open"      # open | closed | squint | swirl | happy | wide | sleep
    mouth: str = "closed"   # closed | open | smile
    ears: str = "up"        # up | back | flat
    smear: tuple = ()       # melee smear marks
    sway: float = 0.0       # stunned head sway
    lift: float = 0.0       # whole-sprite hop height (paws too)
    stars: int = -1         # stunned stars phase
    tremble: int = 0
    tail_ctrl: tuple = ()   # explicit tail control points (east view), base excluded


# ----------------------------------------------------------------------------
# palette bits for hand-placed details

AMBER = col("ember", 4)
AMBER_HI = col("ember", 5)
AMBER_LO = col("ember", 3)
PUPIL = col("soot", 0)
GLINT = col("cream", 4)
NOSE = col("soot", 1)
NOSE_HI = col("soot", 3)
MOUTH = col("fur_russet", 0)
TONGUE = col("cloth_red", 4)
LID = col("soot", 0)
SMEAR1 = col("ember", 6)
SMEAR2 = col("cream", 4)


def _eye(cv: Canvas, x: int, y: int, state: str, facing: str = "s", mirror: bool = False):
    """Hand-placed eye; (x, y) = top-left of its 3x3 box."""
    pal = {"a": AMBER, "Y": AMBER_HI, "A": AMBER_LO, "p": PUPIL, "W": GLINT, "l": LID}
    if state in ("open", "wide"):
        if facing == "s":
            rows = ["aY.", "Wpa", ".aA"] if not mirror else [".Ya", "Wpa", "Aa."]
            if state == "wide":
                rows = ["aYa", "Wpa", "aaA"] if not mirror else ["aYa", "Wpa", "Aaa"]
        else:
            rows = ["YYa", "aWp", "Aaa"]
    elif state == "closed":
        rows = ["...", "lll", "..."] if facing == "s" else ["...", "lll", "..."]
    elif state == "sleep":
        rows = ["...", "l.l", ".l."] if facing == "s" else ["...", "l.l", ".l."]
    elif state == "happy":
        rows = ["...", ".l.", "l.l"] if facing == "s" else ["...", ".l.", "l.l"]
    elif state == "squint":
        if facing == "s":
            rows = ["l..", ".ll", "..."] if not mirror else ["..l", "ll.", "..."]
        else:
            rows = ["l..", ".ll", "..."]
    elif state == "swirl":
        rows = ["YYa", "a.Y", "Yaa"] if not mirror else ["aYY", "Y.a", "aaY"]
        pal = dict(pal, **{".": col("soot", 2)})
        cv.grid(rows, x, y, {k: v for k, v in pal.items()})
        return
    else:
        return
    cv.grid(rows, x, y, pal)


def _mouth_s(cv, nx, ny, state):
    if state == "open":
        cv.grid(["mttm", ".mm."], nx - 1, ny + 2, {"m": MOUTH, "t": TONGUE})
    elif state == "smile":
        cv.grid(["m..m", ".mm."], nx - 1, ny + 2, {"m": MOUTH})
    else:
        cv.grid([".mm."], nx - 1, ny + 2, {"m": col(CREAM, 1)})


# ----------------------------------------------------------------------------
# heads


def head_e(cv: Canvas, hx: float, hy: float, p: Pose, z: float = 9):
    ear_dy = {"up": 0.0, "back": 1.0, "flat": 2.0}[p.ears]
    ear_dx = {"up": 0.0, "back": -1.4, "flat": -2.6}[p.ears]
    ecx, ecy = hx - 3.0 + ear_dx, hy - 4.2 + ear_dy
    ear = cv.ell(ecx, ecy, 2.3, 2.4 - ear_dy * 0.4, angle=-0.3 - ear_dy * 0.4)
    cv.add(ear, FUR, 3, z - 1, group="ear", contour=1)
    skull = cv.ell(hx, hy, 5.4, 4.8)
    muzzle = cv.ell(hx + 4.3, hy + 1.6, 3.2, 2.4, angle=0.10)
    head = skull | muzzle
    cream_m = cv.below([(hx - 7, hy + 1.8), (hx + 0.5, hy + 2.2), (hx + 3.0, hy + 0.2), (hx + 9, hy - 0.4)])
    mask_band = cv.pmask([(hx - 3.4, hy - 1.4), (hx - 0.6, hy - 2.9), (hx + 2.8, hy - 2.4), (hx + 4.4, hy - 0.4),
                          (hx + 3.4, hy + 1.6), (hx + 0.6, hy + 2.0), (hx - 2.8, hy + 1.0)])
    cv.add(head.cut(cream_m | mask_band), FUR, 3, z, group="head")
    cv.add(head.clip(cream_m & ~mask_band), CREAM, 3, z + 0.1, group="head")
    cv.add(head.clip(mask_band), SOOT, 3, z + 0.2, group="head", lo=1)
    if p.ears == "up":
        cv.dot(int(math.floor(ecx)), int(math.floor(ecy)), col(FUR, 1))
        cv.dot(int(math.floor(ecx)), int(math.floor(ecy)) + 1, col(FUR, 1))
    nx, ny = int(math.floor(hx + 7.3)), int(math.floor(hy + 0.6))
    cv.grid(["hn", "nn"], nx - 1, ny - 1, {"n": NOSE, "h": NOSE_HI})
    if p.mouth == "open":
        cv.grid(["mmm", "mtt"], nx - 4, ny + 2, {"m": MOUTH, "t": TONGUE})
    elif p.mouth == "smile":
        cv.grid(["m..", ".mm"], nx - 4, ny + 2, {"m": MOUTH})
    else:
        cv.grid(["mm"], nx - 3, ny + 2, {"m": col(CREAM, 1)})
    _eye(cv, int(math.floor(hx + 0.2)), int(math.floor(hy - 1.8)), p.eyes, facing="e")


def head_s(cv: Canvas, hx: float, hy: float, p: Pose, z: float = 9, ears_z: float | None = None):
    ear_dy = {"up": 0.0, "back": 1.6, "flat": 3.0}[p.ears]
    ear_sp = {"up": 0.0, "back": 0.8, "flat": 1.8}[p.ears]
    for sgn in (-1, 1):
        ex = hx + sgn * (4.9 + ear_sp)
        ey = hy - 4.9 + ear_dy
        ear = cv.ell(ex, ey, 2.4, 2.5 - ear_dy * 0.25, angle=sgn * (0.35 + ear_dy * 0.2))
        cv.add(ear, FUR, 3, (z - 1) if ears_z is None else ears_z, group="ear", contour=1)
        if p.ears == "up":
            ix = int(math.floor(ex))
            cv.dot(ix, int(math.floor(ey)), col(FUR, 1))
            cv.dot(ix, int(math.floor(ey)) + 1, col(FUR, 1))
    skull = cv.ell(hx, hy, 6.6, 5.6)
    cheeks = cv.ell(hx, hy + 2.0, 7.2, 3.6)
    head = skull | cheeks
    muzzle = cv.ell(hx, hy + 3.4, 3.5, 2.5)
    mask = cv.pmask([(hx - 7.4, hy + 0.6), (hx - 5.6, hy - 1.6), (hx - 2.6, hy - 2.4), (hx - 0.6, hy - 1.0),
                     (hx + 0.6, hy - 1.0), (hx + 2.6, hy - 2.4), (hx + 5.6, hy - 1.6), (hx + 7.4, hy + 0.6),
                     (hx + 6.0, hy + 2.2), (hx + 2.4, hy + 2.2), (hx + 0.6, hy + 0.6), (hx - 0.6, hy + 0.6),
                     (hx - 2.4, hy + 2.2), (hx - 6.0, hy + 2.2)])
    cheek_cream = cv.below([(hx - 8, hy + 2.4), (hx - 3, hy + 2.0), (hx + 3, hy + 2.0), (hx + 8, hy + 2.4)])
    cv.add(head.cut(mask | cheek_cream), FUR, 3, z, group="head")
    cv.add(head.clip(cheek_cream & ~mask), CREAM, 3, z + 0.1, group="head")
    cv.add(head.clip(mask), SOOT, 3, z + 0.2, group="head", lo=1)
    cv.add(muzzle, CREAM, 3, z + 0.3, group="head")
    ey = int(math.floor(hy - 1.4))
    _eye(cv, int(math.floor(hx - 4.6)), ey, p.eyes, "s")
    _eye(cv, int(math.floor(hx + 1.6)), ey, p.eyes, "s", mirror=True)
    nx, ny = int(math.floor(hx - 1.0)), int(math.floor(hy + 2.2))
    cv.grid(["hn", "nn"], nx, ny, {"n": NOSE, "h": NOSE_HI})
    _mouth_s(cv, nx, ny, p.mouth)


def head_n(cv: Canvas, hx: float, hy: float, p: Pose, z: float = 5):
    ear_dy = {"up": 0.0, "back": 1.4, "flat": 2.6}[p.ears]
    for sgn in (-1, 1):
        ex, ey = hx + sgn * 4.7, hy - 3.4 + ear_dy
        ear = cv.ell(ex, ey, 2.1, 2.2 - ear_dy * 0.25, angle=sgn * 0.4)
        cv.add(ear, FUR, 3, z + 0.5, group="ear", contour=1)
    cv.add(cv.ell(hx, hy, 5.7, 4.7), FUR, 3, z, group="head", cast=2, contour=1)


# ----------------------------------------------------------------------------
# tail tip: fur ring cradling the ember coal + flame


def _ember_tip(cv, tip, p, z, lean=0.0, dx=0.0, scale=None):
    ring_c = (tip[0] + dx, tip[1] - 1.0)
    cv.add(cv.ell(ring_c[0], ring_c[1] - 0.6, 3.4, 2.3), CREAM, 1, z, group="tail", cast=0)
    er = 2.8 * (p.ember if scale is None else scale)
    flame(cv, ring_c[0], ring_c[1] - 2.2 - (er - 2.8) * 0.6, er, p.flick, lean=lean + p.lean, tongue=p.tongue,
          dim=p.dim, z=z + 1, glow_r=9.0 * min(1.4, max(0.7, er / 2.8)))
    ring_front = cv.ell(ring_c[0], ring_c[1] + 0.5, 3.8, 1.8) - cv.ell(ring_c[0], ring_c[1] - 1.1, 2.4, 1.3)
    cv.add(ring_front, CREAM, 2, z + 2, group="ring", cast=0)


def _tail(cv, ctrl, z, n=10, radii=None, contour=None, cast=1, tufts=True):
    """Long bushy tail: tapered tube + fur tufts along its outline + a few fur strokes."""
    pts = bezier(ctrl, n)
    if radii is None:
        base = [2.4, 2.9, 3.3, 3.6, 3.7, 3.6, 3.4, 3.2, 3.0, 2.9]
        radii = [base[min(len(base) - 1, int(k * len(base) / n))] for k in range(n)]
    shape = cv.tube(pts, radii)
    if tufts:
        # small bumps on alternating sides, swept toward the tip, so the outline reads as fluff
        for k in range(2, n - 1):
            (x0, y0), (x1, y1) = pts[k - 1], pts[k + 1]
            tx, ty = x1 - x0, y1 - y0
            L = math.hypot(tx, ty) or 1.0
            tx, ty = tx / L, ty / L
            nx_, ny_ = -ty, tx
            side = 1 if k % 2 else -1
            r = radii[k]
            cx_ = pts[k][0] + nx_ * side * (r - 0.4) + tx * 0.6
            cy_ = pts[k][1] + ny_ * side * (r - 0.4) + ty * 0.6
            shape = shape | cv.circ(cx_, cy_, 1.25)
    part = cv.add(shape, FUR, 3, z, group="tail", contour=contour, cast=cast)
    # fur strokes: short darker dashes following the tail, on the shaded side
    idx = part.indices().copy()
    for k in range(2, n - 1, 2):
        (x0, y0), (x1, y1) = pts[k - 1], pts[k + 1]
        tx, ty = x1 - x0, y1 - y0
        L = math.hypot(tx, ty) or 1.0
        tx, ty = tx / L, ty / L
        nx_, ny_ = -ty, tx
        # choose the normal pointing away from the light (down-right)
        if nx_ * 0.6 + ny_ * 0.8 < 0:
            nx_, ny_ = -nx_, -ny_
        for j in (0, 1):
            px_ = int(math.floor(pts[k][0] + nx_ * 1.4 + tx * (j - 0.5)))
            py_ = int(math.floor(pts[k][1] + ny_ * 1.4 + ty * (j - 0.5)))
            if 0 <= px_ < cv.w and 0 <= py_ < cv.h and shape.mask[py_, px_]:
                idx[py_, px_] = max(1, idx[py_, px_] - 1)
    part.idx = idx
    return pts


# ----------------------------------------------------------------------------
# small effects


def _smear(cv: Canvas, p: Pose):
    if not p.smear:
        return
    for (x, y) in p.smear:
        cv.fig.post.append((int(x), int(y), SMEAR1))


def claw_arcs(x0, y0, dirx=1, diry=0, n=3, length=5, spacing=2, curve=0.35):
    """Three parallel curved slash lines starting near (x0, y0)."""
    pts = []
    for k in range(n):
        for i in range(length):
            t = i / max(1, length - 1)
            if dirx:
                x = x0 + dirx * i
                y = y0 + k * spacing + int(round(-curve * (i - length / 2) ** 2 / 2 + curve * (length / 2) ** 2 / 2)) * -1
            else:
                y = y0 + diry * i
                x = x0 + k * spacing - int(round(curve * (i - length / 2) ** 2 / 2))
            pts.append((x, y))
    return tuple(pts)


def _stars(cv: Canvas, hx, hy, phase):
    if phase < 0:
        return
    star = [".s.", "sSs", ".s."]
    pal = {"s": col("gold", 4), "S": col("gold", 5)}
    pos = [(-7, -9), (4, -10), (-1, -12)] if phase % 2 == 0 else [(-4, -11), (6, -8), (-8, -7)]
    for dx, dy in pos[:2]:
        cv.grid(star, int(hx + dx), int(hy + dy), pal, post=True)


# ----------------------------------------------------------------------------
# EAST (side profile, facing right)


def _leg(cv, top, paw, r_top, r_mid, bend, z, offset=0, group=None, contour=None, front=True, fur_group=None, sock=3.2):
    """Leg: russet upper (blends into body), soot sock + paw at the bottom."""
    mx = top[0] + (paw[0] - top[0]) * 0.55 + bend
    my = top[1] + (paw[1] - top[1]) * 0.55
    leg = cv.tube([top, (mx, my), (paw[0], paw[1] - 0.6)], [r_top, r_mid, r_mid * 0.95])
    pawshape = cv.ell(paw[0] + (0.8 if front else 0.5), paw[1], 1.9, 1.15)
    sock_m = cv.disk(paw[0] + 0.4, paw[1] + 0.4, sock)
    full = leg | pawshape
    cv.add(full.cut(sock_m), FUR, 3, z, offset=offset, group=fur_group if fur_group else group, cast=0,
           contour=None if fur_group else contour)
    cv.add(full.clip(sock_m), SOOT, 3, z + 0.1, offset=offset, group=group, contour=contour, cast=1)


def draw_e(p: Pose):
    cv = Canvas(W, H)
    ox, oy = p.x + p.tremble, p.y - p.lift
    b = p.bob
    s = p.stretch
    hipc = (18.0 + ox - s * 0.5, 31.0 + oy + b + p.hip_dy)
    chc = (29.4 + ox + s * 0.5, 31.6 + oy + b + p.chest_dy)
    hx, hy = 36.0 + ox + s * 0.5 + p.head[0], 22.4 + oy + b + p.head[1]
    gy = GROUND - 0.4 + p.y - p.lift
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
        ctrl = [base, (base[0] - 6.0, base[1] + 1.5), (5.6 + ox + mdx, 21.0 + oy + mdy),
                (8.6 + ox + tdx, 15.4 + oy + tdy), (12.6 + ox + tdx, 15.0 + oy + tdy)]
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
    under = cv.below([(hx - 4.0, hy + 3.4), (chc[0] + 2.0, chc[1] - 2.6), (chc[0] + 8.0, chc[1] + 0.5)]) | \
        cv.below([(hipc[0] + 3.0, hipc[1] + 5.0), (chc[0] - 3.0, chc[1] + 3.2), (chc[0] + 2.0, chc[1] - 2.6)])
    cv.add(body.cut(under), FUR, 3, 5, group="body")
    cv.add(body.clip(under), CREAM, 3, 5.1, group="body")
    cv.add(cv.ell(hipc[0] + 0.3, hipc[1] + 1.4, 4.0, 4.3), FUR, 3, 6, group="thigh", cast=0)

    # near legs (in front of body)
    _leg(cv, (chc[0] + 0.8, chc[1] + 2.0), (31.6 + ox + s * 0.5 + pw[0][0], gy + pw[0][1]), 2.0, 1.5, -0.4, 7,
         group="nearleg", contour=1)
    _leg(cv, (hipc[0] - 0.2, hipc[1] + 3.0), (17.4 + ox - s * 0.5 + pw[2][0], gy + pw[2][1]), 2.3, 1.55, -1.6, 7,
         group="nearleg2", contour=1, front=False)

    head_e(cv, hx, hy, p, z=9)
    _smear(cv, p)
    _stars(cv, hx - 2, hy, p.stars)
    return cv.render()


# ----------------------------------------------------------------------------
# SOUTH (facing the camera)


def _front_leg_s(cv, top, paw, z, group, offset=0, r=(1.8, 1.55)):
    leg = cv.tube([top, (paw[0], paw[1] - 0.6)], list(r))
    pawshape = cv.ell(paw[0], paw[1], 1.95, 1.2)
    full = leg | pawshape
    sock = cv.below([(paw[0] - 5, paw[1] - 3.0), (paw[0] + 5, paw[1] - 3.0)])
    cv.add(full.cut(sock), FUR, 3, z, group=group, contour=1, offset=offset)
    cv.add(full.clip(sock), SOOT, 3, z + 0.1, group=group, contour=1, offset=offset)


def draw_s(p: Pose):
    cv = Canvas(W, H)
    ox, oy = p.x + p.tremble, p.y - p.lift
    b = p.bob
    s = p.stretch
    hx, hy = 24.0 + ox + p.head[0] + p.sway, 26.6 + oy + b + p.head[1] + s * 0.5
    gy = GROUND - 0.4 + p.y - p.lift
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
    cv.add(body, FUR, 3, 5, group="body")
    for k, sx in enumerate((17.8, 30.2)):
        hp = pw[2 + k]
        cv.add(cv.ell(sx + ox + hp[0], 36.6 + oy + b * 0.5 + hp[1], 2.3, 2.6), FUR, 3, 4.8, group=f"haunch{k}",
               offset=-1, contour=1)
        cv.add(cv.ell(sx + ox + (-0.3 if k == 0 else 0.3) + hp[0], 39.4 + oy + hp[1] - p.y * 0 + 0, 1.8, 1.1), SOOT, 3,
               4.9, group=f"haunch{k}", contour=1, offset=-1)

    # chest bib and short front legs
    cv.add(cv.ell(24.0 + ox, 35.2 + oy + b + s * 0.3, 4.4, 3.8), CREAM, 3, 6, group="chest", cast=1)
    for k, lx in enumerate((20.8, 27.2)):
        paw = (lx + ox + pw[k][0], gy + pw[k][1])
        top = (lx + ox + (0.5 if k == 0 else -0.5), 36.0 + oy + b)
        _front_leg_s(cv, top, paw, 7, f"fleg{k}")

    head_s(cv, hx, hy, p, z=9)
    _smear(cv, p)
    _stars(cv, hx, hy, p.stars)
    return cv.render()


# ----------------------------------------------------------------------------
# NORTH (facing away)


def draw_n(p: Pose):
    cv = Canvas(W, H)
    ox, oy = p.x + p.tremble, p.y - p.lift
    b = p.bob
    s = p.stretch
    pw = p.paws
    gy = GROUND - 0.4 + p.y - p.lift
    hx, hy = 24.0 + ox + p.head[0], 17.6 + oy + b + p.head[1] - s * 0.8

    # front paws peeking out ahead at the sides (furthest away)
    cv.add(cv.ell(19.4 + ox + pw[0][0], 29.6 + oy + pw[0][1] - s * 0.5, 1.8, 1.1), SOOT, 3, 0.5, group="fp", offset=-1)
    cv.add(cv.ell(28.6 + ox + pw[1][0], 29.6 + oy + pw[1][1] - s * 0.5, 1.8, 1.1), SOOT, 3, 0.5, group="fp2", offset=-1)
    # long back seen from behind: rump (near) -> shoulders -> neck (far)
    rump_y = 34.6 + oy + b
    sh_y = 25.0 + oy + b - s * 0.5
    spine = bezier([(24.0 + ox, rump_y), (24.0 + ox, rump_y - 5.0), (24.0 + ox, sh_y + 2.0), (24.0 + ox, sh_y - 3.0)], 10)
    radii = [6.6, 6.7, 6.5, 6.1, 5.7, 5.3, 4.9, 4.5, 4.0, 3.6]
    body = cv.tube(spine, radii) | cv.ell(24.0 + ox, rump_y + 0.6, 7.2, 5.2)
    cv.add(body, FUR, 3, 4, group="body")
    head_n(cv, hx, hy, p, z=5)
    # haunches + hind legs (closest)
    for k, sx in enumerate((18.6, 29.4)):
        cv.add(cv.ell(sx + ox, 35.4 + oy + b, 3.2, 3.8), FUR, 3, 5.5, group=f"haunch{k}", cast=0)
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
    return cv.render()


# ----------------------------------------------------------------------------
# special poses


def draw_sit_e(p: Pose):
    """Sitting upright on the haunches (focus)."""
    cv = Canvas(W, H)
    ox, oy, b = p.x, p.y, p.bob
    hipc = (19.0 + ox, 37.2 + oy)
    chc = (24.2 + ox, 28.6 + oy + b)
    hx, hy = 27.6 + ox + p.head[0], 19.4 + oy + b + p.head[1]
    tdx, tdy = p.tail
    # tail: sweeps back along the ground, then rises behind the back holding the ember
    ctrl = [(hipc[0] - 4.0, hipc[1] + 2.0), (6.6 + ox, 42.0 + oy), (4.2 + ox, 30.0 + oy), (7.4 + ox + tdx, 22.5 + oy + tdy),
            (10.8 + ox + tdx, 21.4 + oy + tdy)]
    pts = _tail(cv, ctrl, 2, n=11)
    _ember_tip(cv, pts[-1], p, z=3, lean=-0.2, dx=0.6)
    # far front leg
    _leg(cv, (chc[0] + 0.5, chc[1] + 3.0), (27.6 + ox, GROUND - 0.4 + oy), 1.8, 1.45, 0.0, 1, offset=-1, group="farleg")
    spine = bezier([(hipc[0] - 1.5, hipc[1] + 1.5), (hipc[0] + 0.5, hipc[1] - 3.0), (chc[0] - 1.0, chc[1] + 3.0),
                    (chc[0] + 1.6, chc[1] - 3.2)], 12)
    radii = [5.6, 5.8, 5.7, 5.5, 5.3, 5.1, 5.0, 4.9, 4.7, 4.5, 4.2, 4.0]
    body = cv.tube(spine, radii) | cv.tube([(chc[0] + 1.0, chc[1] - 1.0), (hx - 1.4, hy + 2.0)], [4.0, 3.4])
    under = cv.right_of([(hx - 2.5, hy + 2.0), (chc[0] + 1.6, chc[1] - 2.0), (chc[0] + 2.2, chc[1] + 3.0),
                         (hipc[0] + 4.0, hipc[1] - 1.0), (hipc[0] + 5.0, hipc[1] + 6.0)])
    cv.add(body.cut(under), FUR, 3, 5, group="body")
    cv.add(body.clip(under), CREAM, 3, 5.1, group="body")
    # haunch + hind paw flat on the ground
    cv.add(cv.ell(hipc[0] + 0.5, hipc[1] + 0.8, 4.4, 4.4), FUR, 3, 6, group="thigh", contour=1, cast=1)
    cv.add(cv.ell(hipc[0] + 4.2, GROUND - 0.5 + oy, 2.8, 1.15), SOOT, 3, 6.5, group="hpaw", contour=1)
    # near front leg straight down to the ground
    _leg(cv, (chc[0] + 1.6, chc[1] + 3.0), (29.0 + ox, GROUND - 0.4 + oy), 2.0, 1.5, 0.2, 7, group="nearleg", contour=1)
    head_e(cv, hx, hy, p, z=9)
    return cv.render()


def draw_sit_s(p: Pose):
    cv = Canvas(W, H)
    ox, oy, b = p.x, p.y, p.bob
    hx, hy = 24.0 + ox + p.head[0], 21.6 + oy + b + p.head[1]
    tdx, tdy = p.tail
    ctrl = [(27.0 + ox, 37.0 + oy), (37.0 + ox, 39.0 + oy), (39.5 + ox + tdx, 26.0 + oy + tdy), (34.6 + ox + tdx, 18.6 + oy + tdy)]
    pts = _tail(cv, ctrl, 1)
    _ember_tip(cv, pts[-1], p, z=2, lean=0.3, dx=-0.4)
    body = cv.ell(24.0 + ox, 33.0 + oy + b * 0.5, 6.8, 7.8)
    cv.add(body, FUR, 3, 5, group="body")
    cv.add(cv.ell(24.0 + ox, 33.6 + oy + b * 0.5, 4.2, 6.0), CREAM, 3, 5.1, group="body")
    for k, sx in enumerate((17.4, 30.6)):
        cv.add(cv.ell(sx + ox, 38.2 + oy, 3.4, 4.0), FUR, 3, 5.5, group=f"haunch{k}", contour=1)
        cv.add(cv.ell(sx + ox + (-1.0 if k == 0 else 1.0), GROUND - 0.5 + oy, 2.4, 1.15), SOOT, 3, 5.6,
               group=f"haunch{k}", contour=1)
    for k, lx in enumerate((22.0, 26.0)):
        _front_leg_s(cv, (lx + ox, 35.0 + oy + b), (lx + ox, GROUND - 0.4 + oy), 7, f"fleg{k}", r=(1.6, 1.4))
    head_s(cv, hx, hy, p, z=9)
    return cv.render()


def draw_sit_n(p: Pose):
    cv = Canvas(W, H)
    ox, oy, b = p.x, p.y, p.bob
    hx, hy = 24.0 + ox + p.head[0], 20.4 + oy + b + p.head[1]
    body = cv.ell(24.0 + ox, 32.4 + oy + b * 0.5, 7.0, 8.6)
    cv.add(body, FUR, 3, 4, group="body")
    head_n(cv, hx, hy, p, z=5)
    for k, sx in enumerate((17.6, 30.4)):
        cv.add(cv.ell(sx + ox, 38.4 + oy, 3.4, 4.0), FUR, 3, 5.5, group=f"haunch{k}", cast=0)
        cv.add(cv.ell(sx + ox, GROUND - 0.5 + oy, 2.3, 1.15), SOOT, 3, 5.6, group=f"hp{k}", contour=1)
    tdx, tdy = p.tail
    ctrl = [(24.5 + ox, 40.0 + oy), (35.0 + ox, 41.5 + oy), (39.0 + ox + tdx, 30.0 + oy + tdy), (35.0 + ox + tdx, 22.6 + oy + tdy)]
    pts = _tail(cv, ctrl, 8, contour=1)
    _ember_tip(cv, pts[-1], p, z=9, lean=-0.3, dx=-0.2)
    return cv.render()


def draw_curl_s(p: Pose, tight: bool = False):
    """Curled up in a ball: tail wrapped around the front, head resting on it, nose by the ember."""
    cv = Canvas(W, H)
    ox, oy, b = p.x + p.tremble, p.y - 1.0, p.bob
    rx = 9.0 if tight else 10.6
    cx = 23.0 + ox
    body = cv.ell(cx, 36.0 + oy + b * 0.5, rx, 7.0 - b * 0.5)
    cv.add(body, FUR, 3, 3, group="body")
    # haunch bump at the back-left
    cv.add(cv.ell(cx - rx + 4.4, 35.2 + oy + b * 0.5, 4.0, 4.4), FUR, 3, 3.5, group="haunch", contour=1, cast=1)
    # tail: from the back-left, around the front, tip at the front-right
    ctrl = [(cx - rx + 2.0, 31.0 + oy), (cx - rx - 3.0, 40.6 + oy), (cx - 2.0, 43.4 + oy), (cx + rx + 1.0, 42.2 + oy),
            (cx + rx + 2.4, 38.2 + oy)]
    pts = bezier(ctrl, 12)
    radii = [2.4, 2.8, 3.0, 3.1, 3.2, 3.2, 3.1, 3.0, 2.9, 2.8, 2.8, 2.8]
    cv.add(cv.tube(pts, radii), FUR, 3, 6, group="tail", contour=1, cast=1)
    _ember_tip(cv, pts[-1], p, z=7, lean=0.0, dx=0.0)
    # head in profile, chin resting on the tail
    hx = cx + (2.0 if tight else 3.0) + p.head[0]
    hy = 34.4 + oy + (1.0 if tight else 0.0) + p.head[1]
    head_e(cv, hx, hy, p, z=10)
    return cv.render()


def draw_lie(p: Pose):
    """Collapsed on its side (KO): side profile flat on the ground, belly toward camera."""
    q = replace(p, bob=6.0, head=(0.0, 9.0), paws=((4, -1), (5, 0), (3, -1), (4, 0)), ears="flat",
                tail_ctrl=((6.0, 38.0), (4.0, 38.5), (5.4, 36.0), (7.4, 35.0)))
    return draw_e(q)


# ----------------------------------------------------------------------------
# animation table


def _fl(i):
    return i % 4


def animations():
    A = {}  # name -> (frames(list of Image), fps, loop)

    def put(name, frames, fps, loop=True):
        A[name] = (frames, fps, loop)

    D = {"s": draw_s, "n": draw_n, "e": draw_e}
    SIT = {"s": draw_sit_s, "n": draw_sit_n, "e": draw_sit_e}

    # idle: breathing, tail sway, flicker
    for d, f in D.items():
        poses = [Pose(bob=0, tail=(0, 0), flick=0), Pose(bob=0, tail=(1, 0), tail_mid=(0, 0), flick=1),
                 Pose(bob=1, tail=(1, 1), tail_mid=(0, 1), flick=2), Pose(bob=1, tail=(0, 1), flick=3)]
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

    # dash: fully stretched low streak, ember trailing
    dash_e = [Pose(x=0, stretch=3, bob=2, lift=1, head=(0, 2), paws=((4, -1), (5, -2), (-4, -1), (-5, -2)),
                   tail=(-1, 8), tail_mid=(1, 4), ears="flat", lean=-2.5, tongue=4.0, flick=f) for f in (0, 2)]
    dash_e[1] = replace(dash_e[1], paws=((3, -2), (5, -1), (-3, -2), (-5, -1)), bob=2, lift=2)
    put("dash_e", [draw_e(q) for q in dash_e], 16)
    dash_s = [Pose(bob=2, stretch=2, ears="flat", paws=((-1, -1), (1, -1), (-1, -1), (1, -1)), tail=(-6, 2),
                   tail_mid=(-3, 0), tongue=4.0, lean=0.0, flick=f, lift=1) for f in (0, 2)]
    dash_s[1] = replace(dash_s[1], lift=2, paws=((-1, -2), (1, -2), (0, 0), (0, 0)))
    put("dash_s", [draw_s(q) for q in dash_s], 16)
    dash_n = [Pose(bob=2, stretch=3, ears="flat", paws=((0, -2), (0, -2), (-1, 0), (1, 0)), tail=(-6, 10),
                   tail_mid=(-4, 3), tongue=4.5, flick=f, lift=1) for f in (0, 2)]
    dash_n[1] = replace(dash_n[1], lift=2, paws=((0, -1), (0, -1), (-1, 1), (1, 1)))
    put("dash_n", [draw_n(q) for q in dash_n], 16)

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


ORDER = ["idle_s", "idle_n", "idle_e", "move_s", "move_n", "move_e", "dash_s", "dash_n", "dash_e",
         "cast_s", "cast_n", "cast_e", "melee_s", "melee_n", "melee_e", "focus_s", "focus_n", "focus_e",
         "guard_s", "guard_n", "guard_e", "hurt_s", "hurt_n", "hurt_e", "stunned_s", "ko_s", "victory_s",
         "cower_s", "curl_s", "happy_s"]


def build(out_dir: str) -> SheetBuilder:
    A = animations()
    assert set(A) == set(ORDER), set(A) ^ set(ORDER)
    sb = SheetBuilder("emberlyn", W, H, PIVOT, columns=8,
                      meta={"kind": "kith", "element": "ember", "generator": "tools/sprite_forge/emberlyn.py"})
    for name in ORDER:
        frames, fps, loop = A[name]
        for i, f in enumerate(frames):
            pix.check_frame(f, f"emberlyn {name}[{i}]")
        sb.add_animation(name, frames, fps, loop)
    sb.save(out_dir)
    return sb


if __name__ == "__main__":
    import preview
    out = "/home/user/game/assets/sprites/kith"
    sb = build(out)
    print(preview.contact(os.path.join(out, "emberlyn.png")))
    print(preview.strips(sb))
