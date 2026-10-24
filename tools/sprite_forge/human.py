"""Shared humanoid rig for the 32x48 people sprites (pivot 16,45).

Bodies are built from tubes/polygons positioned by a tiny skeleton so walk
cycles keep constant volumes; heads are hand-authored ASCII silhouettes per
view (hair / skin / ears ...) shaded with the head's ellipsoid normals, plus
hand-placed eyes and mouths per expression.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

import pix
from kit import Canvas
from pix import Shape, col

W, H = 32, 48
PIVOT = (16, 45)
FOOT_Y = 44.0          # last fill row of planted boots; outline lands on the pivot row 45


@dataclass
class HPose:
    bob: float = 0.0                 # torso + head vertical offset (feet stay planted)
    lean: float = 0.0                # shoulders/head shift along the facing axis (E) or sideways (S/N)
    hip_dy: float = 0.0              # extra hip drop (crouch / sit)
    head: tuple = (0.0, 0.0)
    feet: tuple = ((0.0, 0.0), (0.0, 0.0))     # offsets from rest; [screen-left|far, screen-right|near]
    hands: tuple = ((0.0, 0.0), (0.0, 0.0))
    knees: tuple = (0.0, 0.0)        # extra knee push (E view: forward)
    elbows: tuple = (0.0, 0.0)
    expr: str = "neutral"
    lift: float = 0.0                # whole sprite hop
    x: float = 0.0
    sit: bool = False
    extra: dict = field(default_factory=dict)


# ----------------------------------------------------------------------------
# geometry helpers


def ik2(a, b, l1, l2, bend):
    """Two-bone IK: joint between a and b; bend=+1/-1 picks the side (screen space)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy)
    if d < 1e-6:
        return (a[0], a[1] + l1)
    d = min(d, l1 + l2 - 1e-3)
    x = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, l1 * l1 - x * x))
    ux, uy = dx / d, dy / d
    return (a[0] + ux * x - uy * h * bend, a[1] + uy * x + ux * h * bend)


def head_shape(cv: Canvas, mask, cx, cy, rx, ry):
    """Give a hand-drawn head mask ellipsoid normals (bevel outside the ellipsoid)."""
    e = pix.ellipse(cv.w, cv.h, cx, cy, rx, ry, smooth=False)
    b = pix.from_mask(mask, bevel=2.0)
    s = b.copy()
    inside = e.mask & mask
    s.nx[inside], s.ny[inside], s.nz[inside] = e.nx[inside], e.ny[inside], e.nz[inside]
    s.h[inside] = e.h[inside] + 2.0
    s.mask = mask.copy()
    return s


def grid_masks(cv: Canvas, rows, ox, oy):
    """ASCII grid -> {char: mask}."""
    out = {}
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch in ". ":
                continue
            x, y = ox + i, oy + j
            if 0 <= x < cv.w and 0 <= y < cv.h:
                out.setdefault(ch, np.zeros((cv.h, cv.w), bool))[y, x] = True
    return out


def add_head(cv: Canvas, rows, ox, oy, mats: dict, cx, cy, rx, ry, z, flip=False):
    """Paint an ASCII head. mats: char -> (ramp, base, kwargs)."""
    if flip:
        rows = [r[::-1] for r in rows]
    masks = grid_masks(cv, rows, ox, oy)
    allm = np.zeros((cv.h, cv.w), bool)
    for m in masks.values():
        allm |= m
    base = head_shape(cv, allm, cx, cy, rx, ry)
    parts = {}
    for ch, m in masks.items():
        if ch not in mats:
            continue
        ramp, b, kw = mats[ch]
        kw = dict(kw)
        zz = z + kw.pop("dz", 0.0)
        parts[ch] = cv.add(base.clip(m), ramp, b, zz, **kw)
    return parts, masks


def limb(cv: Canvas, pts, radii, ramp, base, z, **kw):
    return cv.add(cv.tube(pts, radii), ramp, base, z, **kw)


def seg_mask(cv: Canvas, pts, radii):
    return cv.tube(pts, radii)


# ----------------------------------------------------------------------------
# faces (hand placed per expression)

INK_EYE = col("ink", 1)
WHITE = col("cloth_cream", 5)


def face_s(cv: Canvas, ex0: int, ex1: int, ey: int, mx: int, my: int, expr: str, skin: str, eye=INK_EYE,
           brows=None, lash=False):
    """Front face: eyes at columns ex0/ex1 (1px wide, 2px tall from ey), mouth centred at mx (2px) on row my."""
    dk = col(skin, 1)
    md = col(skin, 2)
    if expr in ("neutral", "talk", "determined", "stern", "smile", "grin", "sad", "sulk", "open"):
        for x in (ex0, ex1):
            cv.dot(x, ey, eye)
            cv.dot(x, ey + 1, eye)
    elif expr in ("closed", "happy", "cheer"):
        for x in (ex0, ex1):
            cv.dot(x - 1, ey + 1, eye)
            cv.dot(x, ey, eye)
            cv.dot(x + 1, ey + 1, eye)
    elif expr == "surprised":
        for x in (ex0, ex1):
            cv.dot(x, ey - 1, eye)
            cv.dot(x, ey, eye)
            cv.dot(x, ey + 1, eye)
    if expr in ("determined", "stern"):
        cv.dot(ex0 - 1, ey - 2, dk)
        cv.dot(ex0, ey - 1, dk)
        cv.dot(ex1 + 1, ey - 2, dk)
        cv.dot(ex1, ey - 1, dk)
    if expr in ("sad", "sulk"):
        cv.dot(ex0 + 1, ey - 2, dk)
        cv.dot(ex0, ey - 1, dk)
        cv.dot(ex1 - 1, ey - 2, dk)
        cv.dot(ex1, ey - 1, dk)
    # mouths
    if expr in ("neutral", "determined", "stern"):
        cv.dot(mx, my, md)
        cv.dot(mx + 1, my, md)
    elif expr in ("smile", "happy", "grin"):
        cv.dot(mx - 1, my - 1, md)
        cv.dot(mx, my, dk)
        cv.dot(mx + 1, my, dk)
        cv.dot(mx + 2, my - 1, md)
    elif expr in ("cheer", "talk", "open"):
        cv.dot(mx, my, dk)
        cv.dot(mx + 1, my, dk)
        cv.dot(mx, my + 1, col("cloth_red", 3))
        cv.dot(mx + 1, my + 1, col("cloth_red", 3))
    elif expr == "surprised":
        cv.dot(mx, my, dk)
        cv.dot(mx + 1, my, dk)
        cv.dot(mx, my + 1, dk)
        cv.dot(mx + 1, my + 1, dk)
    elif expr in ("sad", "sulk"):
        cv.dot(mx - 1, my + 1, md)
        cv.dot(mx, my, dk)
        cv.dot(mx + 1, my, dk)
        cv.dot(mx + 2, my + 1, md)
    elif expr == "closed":
        cv.dot(mx, my, md)
        cv.dot(mx + 1, my, md)


def face_e(cv: Canvas, ex: int, ey: int, mx: int, my: int, expr: str, skin: str, eye=INK_EYE):
    """Profile face looking right: eye column ex (2 tall from ey), mouth pixel at (mx, my)."""
    dk = col(skin, 1)
    md = col(skin, 2)
    if expr in ("closed", "happy", "cheer"):
        cv.dot(ex - 1, ey + 1, eye)
        cv.dot(ex, ey, eye)
        cv.dot(ex + 1, ey + 1, eye)
    elif expr == "surprised":
        for k in (-1, 0, 1):
            cv.dot(ex, ey + k, eye)
    else:
        cv.dot(ex, ey, eye)
        cv.dot(ex, ey + 1, eye)
    if expr in ("determined", "stern"):
        cv.dot(ex - 1, ey - 2, dk)
        cv.dot(ex, ey - 1, dk)
    if expr in ("cheer", "talk", "open", "surprised"):
        cv.dot(mx, my, dk)
        cv.dot(mx - 1, my, dk)
    elif expr in ("smile", "happy", "grin"):
        cv.dot(mx, my, dk)
        cv.dot(mx - 1, my + 0, md)
    else:
        cv.dot(mx, my, md)


# ----------------------------------------------------------------------------
# glow helpers (lanterns)


def lantern(cv: Canvas, x: int, y: int, z: float, glow_r: float = 6.0, flick: int = 0, big: bool = False,
            frame: str = "metal"):
    """Tiny belt/staff lantern: metal cap and base around a glowing core. (x, y) = top-left of the 3-wide body."""
    metal = frame
    if not big:
        rows = [".m.", "mgm", "mGm", ".m."]
    else:
        rows = [".mm.", "mggm", "mGGm", "mggm", ".mm."]
    pal_core = {"g": 5 if flick % 2 == 0 else 4, "G": 6}
    masks = grid_masks(cv, rows, x, y)
    if "m" in masks:
        cv.add(Shape(masks["m"]), metal, 3, z, idx=np.where(masks["m"], 3, 0), oc=col(metal, 0), cast=0, glow=False)
    core = np.zeros((cv.h, cv.w), bool)
    idx = np.zeros((cv.h, cv.w), int)
    for ch in ("g", "G"):
        if ch in masks:
            core |= masks[ch]
            idx[masks[ch]] = pal_core[ch]
    cv.add(Shape(core), "gold", 5, z + 0.1, idx=idx, oc=col("gold", 1), cast=0, recv=False, glow=False)
    cx = x + (1.5 if not big else 2.0)
    cy = y + (2.0 if not big else 2.5)
    cv.fig.glows.append((cx, cy, glow_r, 1))


# ----------------------------------------------------------------------------
# generic skeleton + body parts (used by every person module)

ADULT = dict(hip_y=31.5, sh_y=21.2, head_y=12.5, neck_y=19.2, sh_dx=5.6, hip_dx=2.4, foot_dx=3.0,
             hand_y=29.6, hand_dx=7.1, e_sh_x=15.6, e_head_x=16.4, leg_l=4.9, arm_l=4.5)


def make_joints(view: str, P: HPose, prop: dict = ADULT):
    br = P.extra.get("breath", 0.0)
    x = P.x
    lift = P.lift
    hip_y = prop["hip_y"] + P.hip_dy + P.bob - lift
    up = P.bob - lift + P.hip_dy
    J = {"hip_y": hip_y, "prop": prop}
    sh_y = prop["sh_y"] + up + br
    if view in ("s", "n"):
        J["hips"] = [(16.0 - prop["hip_dx"] + x + P.lean * 0.5, hip_y), (16.0 + prop["hip_dx"] + x + P.lean * 0.5, hip_y)]
        J["feet"] = [(16.0 - prop["foot_dx"] + x + P.feet[0][0], 43.2 + P.feet[0][1] - lift),
                     (16.0 + prop["foot_dx"] + x + P.feet[1][0], 43.2 + P.feet[1][1] - lift)]
        J["sh"] = [(16.0 - prop["sh_dx"] + x + P.lean, sh_y), (16.0 + prop["sh_dx"] + x + P.lean, sh_y)]
        hy = prop["hand_y"] + up + br
        J["hands"] = [(16.0 - prop["hand_dx"] + x + P.lean + P.hands[0][0], hy + P.hands[0][1]),
                      (16.0 + prop["hand_dx"] + x + P.lean + P.hands[1][0], hy + P.hands[1][1])]
        J["head"] = (16.0 + x + P.lean + P.head[0], prop["head_y"] + up + br + P.head[1])
        J["neck"] = (16.0 + x + P.lean, prop["neck_y"] + up + br)
    else:
        J["hips"] = [(15.6 + x, hip_y), (16.4 + x, hip_y)]
        J["feet"] = [(15.0 + x + P.feet[0][0], 43.2 + P.feet[0][1] - lift), (17.0 + x + P.feet[1][0], 43.2 + P.feet[1][1] - lift)]
        ex = prop["e_sh_x"]
        J["sh"] = [(ex - 0.4 + x + P.lean, sh_y + 0.2), (ex + 0.4 + x + P.lean, sh_y + 0.2)]
        hy = prop["hand_y"] + 0.4 + up + br
        J["hands"] = [(ex - 0.6 + x + P.lean + P.hands[0][0], hy + P.hands[0][1]),
                      (ex + 0.8 + x + P.lean + P.hands[1][0], hy + P.hands[1][1])]
        J["head"] = (prop["e_head_x"] + x + P.lean * 1.2 + P.head[0], prop["head_y"] + up + br + P.head[1])
        J["neck"] = (prop["e_head_x"] - 0.2 + x + P.lean, prop["neck_y"] + up + br)
    return J


def legs_front_g(cv, J, z, trous, boot, knees=(0.0, 0.0), boot_h=3.0, trous_base=3, boot_base=2, roll=None,
                 bare=None):
    """Front/back legs. roll: ramp for rolled trouser cuffs; bare: skin ramp showing between cuff and boot."""
    for k in range(2):
        hx, hy = J["hips"][k]
        fx, fy = J["feet"][k]
        ank = (fx, fy - 2.6)
        sgn = -1 if k == 0 else 1
        kn = ((hx + ank[0]) / 2 + sgn * knees[k], (hy + ank[1]) / 2)
        if trous:
            end = ank if not roll else (fx, fy - boot_h - 2.4)
            cv.add(cv.tube([(hx, hy), kn, end], [2.2, 2.1, 1.9]), trous, trous_base, z, group=f"leg{k}", contour=1)
            if roll:
                cuff = cv.ell(fx, fy - boot_h - 2.0, 2.4, 1.2)
                cv.add(cuff, roll, 4, z + 0.05, group=f"leg{k}", contour=1)
            if bare:
                cv.add(cv.tube([(fx, fy - boot_h - 1.4), (fx, fy - boot_h + 0.2)], [1.6, 1.6]), bare, 3, z - 0.1,
                       group=f"shin{k}", contour=1)
        shaft = cv.tube([(fx, fy - boot_h), (fx, fy - 0.8)], [2.1, 2.1])
        foot = cv.ell(fx, fy, 2.4, 1.55)
        cv.add(shaft | foot, boot, boot_base, z + 0.2, group=f"boot{k}", contour=1)


def legs_side_g(cv, J, P, z_far, z_near, trous, boot, boot_h=1.6, trous_base=3, boot_base=2, roll=None, leg_l=4.9,
                bare=None):
    for k, z in ((0, z_far), (1, z_near)):
        hx, hy = J["hips"][k]
        fx, fy = J["feet"][k]
        ank = (fx - 0.4, fy - 2.4)
        k1 = ik2((hx, hy), ank, leg_l, leg_l, -1)
        k2 = ik2((hx, hy), ank, leg_l, leg_l, 1)
        knee = k1 if k1[0] >= k2[0] else k2
        knee = (knee[0] + P.knees[k], min(knee[1], ank[1] - 1.0))
        off = -1 if k == 0 else 0
        if trous:
            end = ank if not roll else (ank[0], ank[1] - 1.6)
            cv.add(cv.tube([(hx, hy), knee, end], [2.4, 2.0, 1.8]), trous, trous_base, z, group=f"leg{k}", contour=1,
                   offset=off)
            if roll:
                cv.add(cv.ell(end[0], end[1] + 0.2, 2.2, 1.1), roll, 4, z + 0.05, group=f"leg{k}", contour=1, offset=off)
            if bare:
                cv.add(cv.tube([(end[0], end[1] + 0.6), (ank[0], ank[1])], [1.5, 1.5]), bare, 3, z - 0.1,
                       group=f"shin{k}", contour=1, offset=off)
        shaft = cv.tube([(ank[0], ank[1] - boot_h), (fx - 0.4, fy - 0.8)], [2.0, 2.0])
        foot = cv.ell(fx + 0.9, fy, 2.9, 1.55)
        cv.add(shaft | foot, boot, boot_base, z + 0.2, group=f"boot{k}", contour=1, offset=off)


def arm_g(cv, sh, hand, z, sleeve, skin, bend=1, offset=0, group=None, l1=4.5, l2=4.5, glove=None,
          sleeve_to=1.0, r=(1.55, 1.45, 1.3), hand_r=1.35, fist=False):
    """Arm from shoulder to hand. sleeve_to: fraction of the arm covered by the sleeve (0.5 = short sleeve)."""
    elbow = ik2(sh, hand, l1, l2, bend)
    if sleeve_to >= 0.99:
        cv.add(cv.tube([sh, elbow, hand], list(r)), sleeve, 3, z, group=group, contour=1, offset=offset)
    else:
        cut = (sh[0] + (elbow[0] - sh[0]) * sleeve_to * 2, sh[1] + (elbow[1] - sh[1]) * sleeve_to * 2) if sleeve_to <= 0.5 \
            else (elbow[0] + (hand[0] - elbow[0]) * (sleeve_to - 0.5) * 2, elbow[1] + (hand[1] - elbow[1]) * (sleeve_to - 0.5) * 2)
        bare = cv.tube([sh, elbow, hand], [r[0] * 0.9, r[1] * 0.9, r[2] * 0.95])
        cv.add(bare, skin, 3, z, group=group, contour=1, offset=offset)
        if sleeve:
            pts = [sh, cut] if sleeve_to <= 0.5 else [sh, elbow, cut]
            rr = [r[0], r[0] * 0.95] if sleeve_to <= 0.5 else [r[0], r[1], r[1]]
            cv.add(cv.tube(pts, rr), sleeve, 3, z + 0.05, group=group, contour=1, offset=offset)
    hs = cv.circ(hand[0], hand[1] + 0.4, hand_r + (0.15 if fist else 0.0))
    cv.add(hs, glove or skin, 3, z + 0.1, group=group, contour=1, offset=offset)
    return elbow
