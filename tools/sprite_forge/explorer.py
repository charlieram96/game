"""Explorer -- the player, a young apprentice Warden (32x48, pivot 16,45).

Teal hooded travel cloak (hood down) to mid-thigh, cream tunic, brown trousers,
sturdy dark boots, leather satchel on the right hip, tiny glowing lantern
clipped to the belt, warm orange scarf, tousled dark-brown hair, tan skin.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import replace

import numpy as np

import pix
from human import (FOOT_Y, H, PIVOT, W, HPose, add_head, face_e, face_s, ik2, lantern)
from kit import Canvas
from pix import col

sys.path.insert(0, "/home/user/game/tools")
from common.sheet import SheetBuilder  # noqa: E402

SKIN, HAIR = "skin_tan", "hair_brown"
CLOAK, TUNIC, TROUS, BOOT = "cloth_teal", "cloth_cream", "earth", "soot"
LEATH, SCARF = "leather", "cloth_red"

# ----------------------------------------------------------------------------
# heads (12-13 px wide, 13 tall). h hair, s skin, e ear

HEAD_S = [
    "....h..h....",
    "...hhhhhhh..",
    "..hhhhhhhhh.",
    ".hhhhhhhhhhh",
    "hhhhhhhhhhhh",
    "hhhhhhhhhhhh",
    "hhhshhhhhshh",
    "hhssshhssssh",
    "hssssssssssh",
    "hssssssssssh",
    ".ssssssssss.",
    "..ssssssss..",
    "...ssssss...",
]
HEAD_E = [
    "....h.h......",
    "...hhhhhh....",
    "..hhhhhhhhh..",
    ".hhhhhhhhhhh.",
    "hhhhhhhhhhhh.",
    "hhhhhhhhhhhhh",
    "hhhhhhhhhhshh",
    "hhhhheehssss.",
    "hhhheessssss.",
    ".hhhhssssssss",
    ".hhhssssssss.",
    "..hhsssssss..",
    "...ssssss....",
]
HEAD_N = [
    "....h..h....",
    "...hhhhhhh..",
    "..hhhhhhhhh.",
    ".hhhhhhhhhhh",
    "hhhhhhhhhhhh",
    "hhhhhhhhhhhh",
    "hhhhhhhhhhhh",
    "hhhhhhhhhhhh",
    "ehhhhhhhhhhe",
    "ehhhhhhhhhhe",
    ".hhhhhhhhhh.",
    "..hhhhhhhh..",
    "...ssssss...",
]
HEAD_MATS = {
    "h": (HAIR, 2, {"group": "hair", "contour": None}),
    "s": (SKIN, 4, {"group": "face", "light": 0.55, "bands": (0.10, 0.26, -0.30, -0.9)}),
    "e": (SKIN, 3, {"group": "face", "light": 0.55}),
}


def hair_shine(cv, view, ox, oy):
    """A couple of hand-placed strand highlights on the lit (upper-left) side."""
    c = col(HAIR, 4)
    if view == "s":
        cv.dots([(ox + 3, oy + 2), (ox + 4, oy + 2), (ox + 2, oy + 3), (ox + 5, oy + 1)], c)
    elif view == "e":
        cv.dots([(ox + 4, oy + 2), (ox + 5, oy + 2), (ox + 3, oy + 3), (ox + 6, oy + 1)], c)
    else:
        cv.dots([(ox + 3, oy + 2), (ox + 4, oy + 2), (ox + 2, oy + 3), (ox + 5, oy + 1)], c)


# ----------------------------------------------------------------------------
# skeleton


def joints(view: str, P: HPose):
    br = P.extra.get("breath", 0.0)
    x = P.x
    lift = P.lift
    hip_y = 31.5 + P.hip_dy + P.bob - lift
    up = P.bob - lift
    J = {"hip_y": hip_y}
    if view in ("s", "n"):
        J["hips"] = [(13.6 + x + P.lean * 0.5, hip_y), (18.4 + x + P.lean * 0.5, hip_y)]
        J["feet"] = [(13.0 + x + P.feet[0][0], 43.2 + P.feet[0][1] - lift), (19.0 + x + P.feet[1][0], 43.2 + P.feet[1][1] - lift)]
        J["sh"] = [(10.4 + x + P.lean, 21.2 + up + br + P.hip_dy), (21.6 + x + P.lean, 21.2 + up + br + P.hip_dy)]
        J["hands"] = [(8.9 + x + P.lean + P.hands[0][0], 29.6 + up + br + P.hip_dy + P.hands[0][1]),
                      (23.1 + x + P.lean + P.hands[1][0], 29.6 + up + br + P.hip_dy + P.hands[1][1])]
        J["head"] = (16.0 + x + P.lean + P.head[0], 12.5 + up + br + P.hip_dy + P.head[1])
        J["neck"] = (16.0 + x + P.lean, 19.2 + up + br + P.hip_dy)
    else:
        J["hips"] = [(15.6 + x, hip_y), (16.4 + x, hip_y)]
        J["feet"] = [(15.0 + x + P.feet[0][0], 43.2 + P.feet[0][1] - lift), (17.0 + x + P.feet[1][0], 43.2 + P.feet[1][1] - lift)]
        J["sh"] = [(15.2 + x + P.lean, 21.4 + up + br + P.hip_dy), (16.0 + x + P.lean, 21.4 + up + br + P.hip_dy)]
        J["hands"] = [(15.0 + x + P.lean + P.hands[0][0], 30.0 + up + br + P.hip_dy + P.hands[0][1]),
                      (16.4 + x + P.lean + P.hands[1][0], 30.0 + up + br + P.hip_dy + P.hands[1][1])]
        J["head"] = (16.4 + x + P.lean * 1.2 + P.head[0], 12.5 + up + br + P.hip_dy + P.head[1])
        J["neck"] = (16.2 + x + P.lean, 19.2 + up + br + P.hip_dy)
    return J


# ----------------------------------------------------------------------------
# body pieces


def legs_front(cv, J, z, back=False, knees=(0.0, 0.0)):
    """Trousers + boots, front/back view. knees: outward knee spread (crouch)."""
    for k in range(2):
        hx, hy = J["hips"][k]
        fx, fy = J["feet"][k]
        ank = (fx, fy - 2.6)
        sgn = -1 if k == 0 else 1
        kn = ((hx + ank[0]) / 2 + sgn * knees[k], (hy + ank[1]) / 2)
        trous = cv.tube([(hx, hy), kn, ank], [2.2, 2.1, 1.9])
        cv.add(trous, TROUS, 4, z, group=f"leg{k}", contour=1)
        shaft = cv.tube([(fx, fy - 3.0), (fx, fy - 0.8)], [2.1, 2.1])
        foot = cv.ell(fx + (0.0 if back else 0.0), fy, 2.4, 1.55)
        cv.add(shaft | foot, BOOT, 2, z + 0.2, group=f"boot{k}", contour=1)


def legs_side(cv, J, P, z_far, z_near):
    for k, z in ((0, z_far), (1, z_near)):
        hx, hy = J["hips"][k]
        fx, fy = J["feet"][k]
        ank = (fx - 0.4, fy - 2.4)
        k1 = ik2((hx, hy), ank, 4.9, 4.9, -1)
        k2 = ik2((hx, hy), ank, 4.9, 4.9, 1)
        knee = k1 if k1[0] >= k2[0] else k2          # knees always bend forward
        knee = (knee[0] + P.knees[k], min(knee[1], ank[1] - 1.0))
        off = -1 if k == 0 else 0
        trous = cv.tube([(hx, hy), knee, ank], [2.4, 2.0, 1.8])
        cv.add(trous, TROUS, 4, z, group=f"leg{k}", contour=1, offset=off)
        shaft = cv.tube([(ank[0], ank[1] - 1.6), (fx - 0.4, fy - 0.8)], [2.0, 2.0])
        foot = cv.ell(fx + 0.9, fy, 2.9, 1.55)
        cv.add(shaft | foot, BOOT, 2, z + 0.2, group=f"boot{k}", contour=1, offset=off)


def arm(cv, sh, hand, z, sleeve=CLOAK, bend=1, offset=0, group=None, l1=4.5, l2=4.5, glove=None):
    """Teal cloak sleeve with a cream tunic cuff at the wrist, tan hand."""
    elbow = ik2(sh, hand, l1, l2, bend)
    sl = cv.tube([sh, elbow, hand], [1.6, 1.5, 1.35])
    cv.add(sl, CLOAK, 3, z, group=group, contour=1, offset=offset)
    # cuff: the last ~1.5px of the forearm in the tunic colour
    dx, dy = hand[0] - elbow[0], hand[1] - elbow[1]
    L = math.hypot(dx, dy) or 1.0
    c0 = (hand[0] - dx / L * 1.6, hand[1] - dy / L * 1.6)
    cuff = cv.tube([c0, hand], [1.45, 1.35])
    cv.add(cuff, TUNIC, 4, z + 0.05, group=group, contour=1, offset=offset)
    hs = cv.circ(hand[0] + dx / L * 0.6, hand[1] + dy / L * 0.6 + 0.2, 1.35)
    cv.add(hs, glove or SKIN, 4, z + 0.1, group=group, contour=1, offset=offset)
    return elbow


# ----------------------------------------------------------------------------
# views


def draw_s(P: HPose):
    cv = Canvas(W, H)
    J = joints("s", P)
    nx, ny = J["neck"]
    sh_y = J["sh"][0][1]
    hem_y = 35.6 + P.bob * 0.5 - P.lift + P.hip_dy * 0.6
    if P.sit:
        return draw_sit_s(P)
    # cloak inside/back panel visible between the legs
    back = cv.poly([(nx - 6.4, sh_y - 1.0), (nx + 6.4, sh_y - 1.0), (nx + 8.2, hem_y), (nx - 8.2, hem_y)], bevel=1.5)
    cv.add(back, CLOAK, 2, 1, group="cloakb", offset=-1)
    legs_front(cv, J, 2, knees=P.knees)
    # tunic
    tun = cv.poly([(nx - 5.0, sh_y - 1.6), (nx + 5.0, sh_y - 1.6), (nx + 5.2, J["hip_y"] + 1.8), (nx - 5.2, J["hip_y"] + 1.8)],
                  bevel=2.0)
    cv.add(tun, TUNIC, 3, 3, group="tunic")
    # belt + strap
    by = int(round(J["hip_y"] - 2.0))
    cv.add(cv.from_mask(cv.rect(int(nx) - 5, by, int(nx) + 4, by + 1), 1.0), LEATH, 3, 3.4, group="belt")
    cv.dot(int(nx), by, col("gold", 4))
    # cloak front (open), drawn over tunic sides
    outer = cv.pmask([(nx - 6.6, sh_y - 1.4), (nx + 6.6, sh_y - 1.4), (nx + 8.4, hem_y), (nx - 8.4, hem_y)])
    opening = cv.pmask([(nx - 1.8, sh_y - 2.0), (nx + 1.8, sh_y - 2.0), (nx + 3.6, hem_y + 1), (nx - 3.6, hem_y + 1)])
    cloak = cv.from_mask(outer & ~opening, bevel=2.2)
    cv.add(cloak, CLOAK, 3, 4, group="cloak", contour=1)
    # satchel (character's right hip = screen left) and lantern (front-left of belt = screen right)
    sx, sy = nx - 5.6, J["hip_y"] - 0.8
    sat = cv.rrect(sx - 2.2, sy, sx + 2.2, sy + 3.8, r=1.2, bevel=1.6)
    cv.add(sat, LEATH, 4, 4.5, group="satchel", contour=1)
    cv.add(cv.from_mask(cv.rect(int(sx - 2), int(sy), int(sx + 1), int(sy + 1)), 1.0), LEATH, 3, 4.6, group="satchel")
    lantern(cv, int(round(nx + 0.6)), by + 1, 4.6, glow_r=6.5, flick=P.extra.get("flick", 0))
    # arms
    for k in range(2):
        arm(cv, J["sh"][k], J["hands"][k], 5, sleeve=TUNIC, bend=1 if k == 0 else -1, group=f"arm{k}")
    # mantle over the shoulders + scarf
    mant = cv.ell(nx, sh_y + 0.6, 7.4, 3.1)
    cv.add(mant, CLOAK, 3, 6, group="mantle", contour=1)
    hood = cv.ell(nx, sh_y - 2.6, 5.2, 2.0)
    cv.add(hood, CLOAK, 3, 1.5, group="hood", offset=-1)
    sc = cv.ell(nx, sh_y - 1.4, 4.2, 1.7)
    tail = cv.tube([(nx + 2.4, sh_y - 0.6), (nx + 2.8, sh_y + 3.8)], [1.2, 1.0])
    cv.add(sc | tail, SCARF, 4, 7, group="scarf", contour=1)
    # head
    hx, hy = J["head"]
    ox, oy = int(round(hx - 6)), int(round(hy - 6.5))
    add_head(cv, HEAD_S, ox, oy, HEAD_MATS, hx, hy + 0.3, 6.1, 6.3, 9)
    hair_shine(cv, "s", ox, oy)
    face_s(cv, ox + 3, ox + 8, oy + 8, ox + 5, oy + 11, P.expr, SKIN)
    return cv.render()


def draw_n(P: HPose):
    cv = Canvas(W, H)
    J = joints("n", P)
    nx, ny = J["neck"]
    sh_y = J["sh"][0][1]
    hem_y = 35.6 + P.bob * 0.5 - P.lift + P.hip_dy * 0.6
    legs_front(cv, J, 2, back=True, knees=P.knees)
    for k in range(2):
        arm(cv, J["sh"][k], J["hands"][k], 3, sleeve=TUNIC, bend=-1 if k == 0 else 1, group=f"arm{k}")
    # satchel on the character's right hip (screen right), partly behind the cloak
    sx, sy = nx + 5.4, J["hip_y"] - 1.6
    cv.add(cv.rrect(sx - 2.4, sy, sx + 2.6, sy + 4.4, r=1.2, bevel=1.6), LEATH, 4, 3.5, group="satchel", contour=1)
    cloak = cv.poly([(nx - 6.6, sh_y - 1.4), (nx + 6.6, sh_y - 1.4), (nx + 8.4, hem_y), (nx - 8.4, hem_y)], bevel=2.4)
    cv.add(cloak, CLOAK, 3, 4, group="cloak", contour=1)
    # a centre fold line
    for yy in range(int(sh_y + 4), int(hem_y)):
        cv.dot(int(nx) - (1 if yy > sh_y + 9 else 0), yy, col(CLOAK, 2))
    mant = cv.ell(nx, sh_y + 0.6, 7.4, 3.1)
    cv.add(mant, CLOAK, 3, 5, group="mantle", contour=1)
    hood = cv.ell(nx, sh_y + 0.6, 4.6, 2.8)
    cv.add(hood, CLOAK, 4, 6, group="hood", contour=1)
    sc = cv.ell(nx, sh_y - 1.6, 3.8, 1.4)
    cv.add(sc, SCARF, 4, 6.5, group="scarf", contour=1)
    hx, hy = J["head"]
    ox, oy = int(round(hx - 6)), int(round(hy - 6.5))
    add_head(cv, HEAD_N, ox, oy, HEAD_MATS, hx, hy + 0.3, 6.1, 6.3, 9)
    hair_shine(cv, "n", ox, oy)
    return cv.render()


def draw_e(P: HPose):
    cv = Canvas(W, H)
    J = joints("e", P)
    if P.sit:
        return draw_sit_e(P)
    nx, ny = J["neck"]
    sh = J["sh"][1]
    hip_y = J["hip_y"]
    hem_y = 35.6 + P.bob * 0.5 - P.lift + P.hip_dy * 0.6
    flow = P.extra.get("flow", 0.0)
    # far arm (behind everything)
    arm(cv, J["sh"][0], J["hands"][0], 0.5, sleeve=TUNIC, bend=1, offset=-1, group="farm")
    # cloak hanging down the back, flaring behind
    cl = cv.poly([(nx - 2.4, sh[1] - 2.0), (nx + 1.6, sh[1] - 1.4), (nx + 2.0, sh[1] + 2.0), (nx + 0.6, hem_y),
                  (nx - 6.6 - flow, hem_y + 0.2), (nx - 5.2 - flow * 0.6, sh[1] + 6.0), (nx - 4.0, sh[1] - 0.4)], bevel=2.4)
    cv.add(cl, CLOAK, 3, 1, group="cloakb")
    legs_side(cv, J, P, 1.5, 2.5)
    # tunic torso
    tun = cv.poly([(nx - 2.8, sh[1] - 1.6), (nx + 2.6, sh[1] - 1.6), (nx + 3.6, hip_y - 1.0), (nx + 3.4, hip_y + 2.0),
                   (nx - 3.0, hip_y + 2.0), (nx - 3.2, sh[1] + 2.0)], bevel=2.0)
    cv.add(tun, TUNIC, 3, 3, group="tunic")
    by = int(round(hip_y - 2.0))
    cv.add(cv.from_mask(cv.rect(int(nx) - 3, by, int(nx) + 3, by + 1), 1.0), LEATH, 3, 3.4, group="belt")
    # cloak side panel over the back half of the torso
    side = cv.poly([(nx - 3.6, sh[1] - 1.8), (nx + 0.8, sh[1] - 1.6), (nx + 1.2, sh[1] + 3.0), (nx - 0.2, hem_y),
                    (nx - 5.4 - flow * 0.5, hem_y), (nx - 4.6, sh[1] + 3.0)], bevel=2.2)
    cv.add(side, CLOAK, 3, 4, group="cloak", contour=1)
    # lantern at the front of the belt, satchel on the (near) right hip
    lantern(cv, int(round(nx + 2.4)), by + 1, 4.6, glow_r=6.5, flick=P.extra.get("flick", 0))
    sx, sy = nx - 2.6, hip_y - 1.0
    cv.add(cv.rrect(sx - 2.4, sy, sx + 2.0, sy + 4.0, r=1.2, bevel=1.6), LEATH, 4, 4.5, group="satchel", contour=1)
    cv.add(cv.from_mask(cv.rect(int(sx - 2), int(sy), int(sx + 1), int(sy + 1)), 1.0), LEATH, 3, 4.55, group="satchel")
    strap = cv.tube([(nx + 1.4, sh[1] - 1.0), (sx + 0.6, sy + 0.4)], [0.6, 0.6])
    cv.add(strap, LEATH, 2, 4.4, group="strap", cast=0)
    # near arm
    arm(cv, J["sh"][1], J["hands"][1], 5, sleeve=TUNIC, bend=1, group="narm")
    mant = cv.ell(sh[0] - 0.4, sh[1] + 0.2, 4.0, 2.8)
    cv.add(mant, CLOAK, 3, 6, group="mantle", contour=1)
    hood = cv.ell(nx - 3.0, sh[1] - 1.2, 2.6, 2.4)
    cv.add(hood, CLOAK, 3, 5.8, group="hood", contour=1)
    sc = cv.ell(nx + 0.2, sh[1] - 2.0, 3.0, 1.5)
    tail = cv.tube([(nx - 1.6, sh[1] - 1.6), (nx - 4.2 - flow * 0.5, sh[1] + 0.6 - flow * 0.3)], [1.1, 0.9])
    cv.add(sc | tail, SCARF, 4, 7, group="scarf", contour=1)
    hx, hy = J["head"]
    ox, oy = int(round(hx - 6.4)), int(round(hy - 6.5))
    add_head(cv, HEAD_E, ox, oy, HEAD_MATS, hx, hy + 0.3, 6.2, 6.3, 9)
    hair_shine(cv, "e", ox, oy)
    face_e(cv, ox + 10, oy + 8, ox + 10, oy + 11, P.expr, SKIN)
    return cv.render()


# ----------------------------------------------------------------------------
# sitting cross-legged


def draw_sit_s(P: HPose):
    cv = Canvas(W, H)
    br = P.extra.get("breath", 0.0)
    nx = 16.0
    sh_y = 29.0 + br
    # cloak pooled on the ground behind
    cv.add(cv.ell(nx, 41.4, 11.0, 2.8), CLOAK, 2, 0.5, group="cloakb", offset=-1)
    # thighs out to the knees, shins folded across the front, boots crossed at the centre
    for k, sgn in enumerate((-1, 1)):
        cv.add(cv.tube([(nx + sgn * 2.4, 39.6), (nx + sgn * 7.4, 41.2)], [2.4, 2.3]), TROUS, 3, 1.8, group=f"thigh{k}", contour=1)
    cv.add(cv.tube([(nx - 7.2, 41.8), (nx + 1.6, 42.8)], [2.0, 1.8]), TROUS, 2, 2.0, group="shinL", contour=1)
    cv.add(cv.tube([(nx + 7.2, 41.8), (nx - 1.6, 42.8)], [2.0, 1.8]), TROUS, 3, 2.2, group="shinR", contour=1)
    cv.add(cv.ell(nx + 2.8, 42.8, 2.2, 1.3), BOOT, 2, 2.1, group="bootL", contour=1)
    cv.add(cv.ell(nx - 2.8, 42.8, 2.2, 1.3), BOOT, 2, 2.3, group="bootR", contour=1)
    # torso
    tun = cv.poly([(nx - 5.0, sh_y - 1.6), (nx + 5.0, sh_y - 1.6), (nx + 5.4, 40.0), (nx - 5.4, 40.0)], bevel=2.0)
    cv.add(tun, TUNIC, 3, 3, group="tunic")
    by = int(round(37.0 + br * 0.5))
    cv.add(cv.from_mask(cv.rect(11, by, 20, by + 1), 1.0), LEATH, 3, 3.4, group="belt")
    cv.dot(int(nx), by, col("gold", 4))
    outer = cv.pmask([(nx - 6.6, sh_y - 1.4), (nx + 6.6, sh_y - 1.4), (nx + 8.0, 40.4), (nx - 8.0, 40.4)])
    opening = cv.pmask([(nx - 1.8, sh_y - 2.0), (nx + 1.8, sh_y - 2.0), (nx + 3.4, 42), (nx - 3.4, 42)])
    cv.add(cv.from_mask(outer & ~opening, bevel=2.2), CLOAK, 3, 4, group="cloak", contour=1)
    lantern(cv, 18, by + 1, 4.6, glow_r=6.5, flick=P.extra.get("flick", 0))
    # hands resting on the knees
    arm(cv, (nx - 5.6, sh_y + 0.4), (nx - 7.4, 38.4 + br * 0.5), 5, bend=1, group="armL", l1=4.6, l2=4.6)
    arm(cv, (nx + 5.6, sh_y + 0.4), (nx + 7.4, 38.4 + br * 0.5), 5, bend=-1, group="armR", l1=4.6, l2=4.6)
    cv.add(cv.ell(nx, sh_y + 0.6, 7.4, 3.1), CLOAK, 3, 6, group="mantle", contour=1)
    sc = cv.ell(nx, sh_y - 1.4, 4.2, 1.7) | cv.tube([(nx + 2.4, sh_y - 0.6), (nx + 2.8, sh_y + 3.8)], [1.2, 1.0])
    cv.add(sc, SCARF, 4, 7, group="scarf", contour=1)
    hx, hy = nx, sh_y - 8.7
    ox, oy = int(round(hx - 6)), int(round(hy - 6.5))
    add_head(cv, HEAD_S, ox, oy, HEAD_MATS, hx, hy + 0.3, 6.1, 6.3, 9)
    hair_shine(cv, "s", ox, oy)
    face_s(cv, ox + 3, ox + 8, oy + 8, ox + 5, oy + 11, P.expr, SKIN)
    return cv.render()


def draw_sit_e(P: HPose):
    cv = Canvas(W, H)
    br = P.extra.get("breath", 0.0)
    nx = 14.6
    sh_y = 30.4 + br
    cv.add(cv.poly([(nx - 2.0, sh_y - 1.6), (nx - 9.4, 44.4), (nx + 1.0, 44.4)], bevel=2.0), CLOAK, 2, 0.5, group="cloakb")
    # crossed legs in profile: far knee, near shin crossing in front, boot tips
    cv.add(cv.tube([(nx + 0.4, 41.6), (nx + 8.0, 41.4)], [2.4, 2.2]), TROUS, 3, 1.5, group="far", offset=-1, contour=1)
    cv.add(cv.ell(nx + 9.2, 43.4, 2.6, 1.5), BOOT, 2, 1.6, group="farb", offset=-1, contour=1)
    cv.add(cv.tube([(nx + 0.4, 42.6), (nx + 7.4, 43.2)], [2.5, 2.2]), TROUS, 3, 2.5, group="near", contour=1)
    cv.add(cv.ell(nx + 3.2, 43.6, 2.6, 1.3), BOOT, 2, 2.6, group="nearb", contour=1)
    tun = cv.poly([(nx - 2.8, sh_y - 1.6), (nx + 2.6, sh_y - 1.6), (nx + 3.6, 38.0), (nx + 3.2, 42.0), (nx - 3.2, 42.0),
                   (nx - 3.2, sh_y + 2.0)], bevel=2.0)
    cv.add(tun, TUNIC, 3, 3, group="tunic")
    cv.add(cv.from_mask(cv.rect(int(nx) - 3, 38, int(nx) + 3, 39), 1.0), LEATH, 3, 3.4, group="belt")
    side = cv.poly([(nx - 3.6, sh_y - 1.8), (nx + 0.8, sh_y - 1.6), (nx + 1.0, 42.4), (nx - 5.0, 42.6), (nx - 4.4, sh_y + 3.0)],
                   bevel=2.2)
    cv.add(side, CLOAK, 3, 4, group="cloak", contour=1)
    lantern(cv, int(round(nx + 2.4)), 39, 4.6, glow_r=6.5, flick=P.extra.get("flick", 0))
    arm(cv, (nx + 0.2, sh_y + 0.6), (nx + 7.6, 39.8 + br * 0.5), 5, bend=1, group="narm", l1=4.4, l2=4.8)
    cv.add(cv.ell(nx - 0.2, sh_y + 0.2, 4.0, 2.8), CLOAK, 3, 6, group="mantle", contour=1)
    cv.add(cv.ell(nx - 3.0, sh_y - 1.2, 2.6, 2.4), CLOAK, 3, 5.8, group="hood", contour=1)
    sc = cv.ell(nx + 0.2, sh_y - 2.0, 3.0, 1.5) | cv.tube([(nx - 1.6, sh_y - 1.6), (nx - 4.2, sh_y + 0.6)], [1.1, 0.9])
    cv.add(sc, SCARF, 4, 7, group="scarf", contour=1)
    hx, hy = nx + 0.4, sh_y - 8.7
    ox, oy = int(round(hx - 6.4)), int(round(hy - 6.5))
    add_head(cv, HEAD_E, ox, oy, HEAD_MATS, hx, hy + 0.3, 6.2, 6.3, 9)
    hair_shine(cv, "e", ox, oy)
    face_e(cv, ox + 10, oy + 8, ox + 10, oy + 11, P.expr, SKIN)
    return cv.render()


# ----------------------------------------------------------------------------
# animations

D = {"s": draw_s, "n": draw_n, "e": draw_e}


def animations():
    A = {}

    def put(name, frames, fps, loop=True):
        A[name] = (frames, fps, loop)

    for d, fn in D.items():
        put(f"idle_{d}", [fn(HPose(extra={"flick": 0})), fn(HPose(extra={"breath": 1.0, "flick": 1}))], 3)

    # walk: contact -> passing -> contact -> passing
    put("walk_s", [draw_s(HPose(bob=1, feet=((0, 0), (0, -1)), hands=((0.4, 1), (-0.4, -1)), extra={"flick": 0})),
                   draw_s(HPose(bob=0, feet=((0, 0), (0, -2)), hands=((0, 0), (0, 0)), extra={"flick": 1})),
                   draw_s(HPose(bob=1, feet=((0, -1), (0, 0)), hands=((0.4, -1), (-0.4, 1)), extra={"flick": 0})),
                   draw_s(HPose(bob=0, feet=((0, -2), (0, 0)), hands=((0, 0), (0, 0)), extra={"flick": 1}))], 8)
    put("walk_n", [draw_n(HPose(bob=1, feet=((0, -1), (0, 0)), hands=((0.4, -1), (-0.4, 1)))),
                   draw_n(HPose(bob=0, feet=((0, -2), (0, 0)))),
                   draw_n(HPose(bob=1, feet=((0, 0), (0, -1)), hands=((0.4, 1), (-0.4, -1)))),
                   draw_n(HPose(bob=0, feet=((0, 0), (0, -2))))], 8)
    put("walk_e", [draw_e(HPose(bob=1, feet=((-3, 0), (3, 0)), hands=((2.4, -0.6), (-2.6, -0.4)), extra={"flow": 1.0})),
                   draw_e(HPose(bob=0, feet=((1, -2), (-1, 0)), hands=((0.6, 0), (-0.6, 0)), extra={"flow": 0.5, "flick": 1})),
                   draw_e(HPose(bob=1, feet=((3, 0), (-3, 0)), hands=((-2.4, -0.4), (2.6, -0.6)), extra={"flow": 1.0})),
                   draw_e(HPose(bob=0, feet=((-1, 0), (1, -2)), hands=((-0.6, 0), (0.6, 0)), extra={"flow": 0.5, "flick": 1}))], 8)

    # sneak: crouched ~6px lower, careful tiptoe, hands raised
    sn = dict(bob=5, hip_dy=1, knees=(2.0, 2.0), head=(0, 1))
    hs = ((1.2, -8.0), (-1.2, -8.0))
    put("sneak_s", [draw_s(HPose(**sn, feet=((-1, 0), (1, -2)), hands=((1.2, -8.0), (-1.2, -9.0)), expr="determined")),
                    draw_s(HPose(**sn, feet=((-1, 0), (1, 0)), hands=hs, expr="determined")),
                    draw_s(HPose(**sn, feet=((-1, -2), (1, 0)), hands=((1.2, -9.0), (-1.2, -8.0)), expr="determined")),
                    draw_s(HPose(**sn, feet=((-1, 0), (1, 0)), hands=hs, expr="determined"))], 6)
    put("sneak_n", [draw_n(HPose(**sn, feet=((-1, -2), (1, 0)), hands=((3.4, -6.0), (-3.4, -7.0)))),
                    draw_n(HPose(**sn, feet=((-1, 0), (1, 0)), hands=((3.4, -6.0), (-3.4, -6.0)))),
                    draw_n(HPose(**sn, feet=((-1, 0), (1, -2)), hands=((3.4, -7.0), (-3.4, -6.0)))),
                    draw_n(HPose(**sn, feet=((-1, 0), (1, 0)), hands=((3.4, -6.0), (-3.4, -6.0))))], 6)
    se = dict(bob=5, hip_dy=1, lean=2.0)
    put("sneak_e", [draw_e(HPose(**se, feet=((-3, 0), (2, -2)), knees=(1.0, 1.5), hands=((3.0, -6), (4.0, -5)), expr="determined", extra={"flow": 0.6})),
                    draw_e(HPose(**se, feet=((-2, 0), (2, 0)), knees=(1.0, 1.0), hands=((3.0, -6), (4.0, -6)), expr="determined", extra={"flow": 0.4})),
                    draw_e(HPose(**se, feet=((2, -2), (-3, 0)), knees=(1.5, 1.0), hands=((3.0, -5), (4.0, -6)), expr="determined", extra={"flow": 0.6})),
                    draw_e(HPose(**se, feet=((2, 0), (-2, 0)), knees=(1.0, 1.0), hands=((3.0, -6), (4.0, -6)), expr="determined", extra={"flow": 0.4}))], 6)

    # interact: reaching forward
    put("interact_s", [draw_s(HPose(hands=((0, 0), (1.6, -5.0)), lean=0, bob=0, expr="open")),
                       draw_s(HPose(hands=((0.4, 0), (2.4, -7.0)), bob=1, head=(0, 1), expr="open"))], 6, False)
    put("interact_n", [draw_n(HPose(hands=((0, 0), (-3.4, -9.0)))),
                       draw_n(HPose(hands=((0, 0), (-3.8, -11.0)), bob=0, head=(0, -1)))], 6, False)
    put("interact_e", [draw_e(HPose(hands=((1.0, 0), (6.0, -7.0)), lean=0.5)),
                       draw_e(HPose(hands=((1.4, 0), (8.0, -6.4)), lean=1.2, bob=1))], 6, False)

    # sitting cross-legged, gentle breathing
    put("sit_s", [draw_s(HPose(sit=True, expr="smile")), draw_s(HPose(sit=True, expr="smile", extra={"breath": 1.0, "flick": 1}))], 2)
    put("sit_e", [draw_e(HPose(sit=True, expr="smile")), draw_e(HPose(sit=True, expr="smile", extra={"breath": 1.0, "flick": 1}))], 2)

    # cheer: arms raised
    put("cheer_s", [draw_s(HPose(hands=((-1.4, -15.0), (1.4, -15.0)), expr="cheer")),
                    draw_s(HPose(hands=((-2.4, -17.0), (2.4, -17.0)), expr="cheer", lift=2, extra={"flick": 1}))], 4)
    # surprised: startled, arms up, wide eyes
    put("surprised_s", [draw_s(HPose(hands=((-2.6, -8.0), (2.6, -8.0)), expr="surprised", bob=-1, head=(0, -1)))], 8, False)
    return A


ORDER = ["idle_s", "idle_n", "idle_e", "walk_s", "walk_n", "walk_e", "sneak_s", "sneak_n", "sneak_e",
         "interact_s", "interact_n", "interact_e", "sit_s", "sit_e", "cheer_s", "surprised_s"]


def build(out_dir: str) -> SheetBuilder:
    A = animations()
    assert set(A) == set(ORDER), set(A) ^ set(ORDER)
    sb = SheetBuilder("explorer", W, H, PIVOT, columns=8, meta={"kind": "character", "role": "player",
                                                                 "generator": "tools/sprite_forge/explorer.py"})
    for name in ORDER:
        frames, fps, loop = A[name]
        for i, f in enumerate(frames):
            pix.check_frame(f, f"explorer {name}[{i}]")
        sb.add_animation(name, frames, fps, loop)
    sb.save(out_dir)
    return sb


if __name__ == "__main__":
    from preview import lineup
    imgs = [draw_s(HPose()), draw_n(HPose()), draw_e(HPose()), draw_s(HPose(sit=True)), draw_e(HPose(sit=True))]
    print(lineup(imgs, 6, "explorer_test"))
