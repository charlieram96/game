"""Warden Hesper -- the village mentor (32x48, pivot 16,45).

An older woman with a slight stoop: silver-grey hair in a bun, deep plum coat to
the ankles with small brass buttons, light olive skin, a kind face with small
round spectacles, and a tall wooden staff topped by a small hanging lantern,
held in her right hand.
"""

from __future__ import annotations

import math
import sys

import numpy as np

import pix
from human import (H, PIVOT, W, HPose, add_head, arm_g, face_e, face_s, lantern, make_joints)
from kit import Canvas
from pix import col

sys.path.insert(0, "/home/user/game/tools")
from common.sheet import SheetBuilder  # noqa: E402

SKIN, HAIR, COAT, SHOE, WOOD = "skin_light", "hair_grey", "cloth_plum", "leather", "wood"
BLOUSE = "cloth_cream"

PROP = dict(hip_y=31.8, sh_y=21.8, head_y=13.4, neck_y=19.8, sh_dx=5.3, hip_dx=2.3, foot_dx=2.6,
            hand_y=29.8, hand_dx=6.7, e_sh_x=15.0, e_head_x=17.0, leg_l=4.9, arm_l=4.4)

HEAD_S = [
    "....bbbb....",
    "...bbbbbb...",
    "..hhbbbbhh..",
    ".hhhhhhhhhh.",
    "hhhhhhhhhhhh",
    "hhhsssssshhh",
    "hhsssssssshh",
    "hssssssssssh",
    "hssssssssssh",
    "hssssssssssh",
    ".ssssssssss.",
    "..ssssssss..",
    "...ssssss...",
]
HEAD_E = [
    ".bbb.........",
    "bbbbbhhhh....",
    "bbbbhhhhhhh..",
    "bbbhhhhhhhhh.",
    ".hhhhhhhhhhh.",
    ".hhhhhhhhhss.",
    ".hhhhhhhssss.",
    ".hhhheesssss.",
    "..hheessssss.",
    "..hhhssssssss",
    "..hhhsssssss.",
    "...hsssssss..",
    "....ssssss...",
]
HEAD_N = [
    "............",
    "....hhhh....",
    "..hhhhhhhh..",
    ".hhhbbbbhhh.",
    "hhhbbbbbbhhh",
    "hhhbbbbbbhhh",
    "hhhbbbbbbhhh",
    "hhhhbbbbhhhh",
    "ehhhhhhhhhhe",
    "ehhhhhhhhhhe",
    ".hhhhhhhhhh.",
    "..hhhhhhhh..",
    "...ssssss...",
]
HEAD_MATS = {
    "h": (HAIR, 2, {"group": "hair"}),
    "b": (HAIR, 3, {"group": "bun", "contour": 1}),
    "s": (SKIN, 4, {"group": "face", "light": 0.55, "bands": (0.10, 0.26, -0.30, -0.9)}),
    "e": (SKIN, 3, {"group": "face", "light": 0.55}),
}
FRAME = col("gold", 2)
GLASS = col("water", 6)


def _specs_s(cv, ox, oy):
    """Small round spectacles: thin frame segments, a glint on each lens and a bridge."""
    for ex in (ox + 3, ox + 8):
        cv.dot(ex - 1, oy + 8, FRAME)
        cv.dot(ex - 1, oy + 9, FRAME)
        cv.dot(ex + 1, oy + 9, FRAME)
        cv.dot(ex + 1, oy + 8, GLASS)
    cv.dot(ox + 5, oy + 8, FRAME)
    cv.dot(ox + 6, oy + 8, FRAME)


def _specs_e(cv, ox, oy):
    ex = ox + 10
    cv.dot(ex + 1, oy + 8, GLASS)
    cv.dot(ex + 1, oy + 9, FRAME)
    cv.dot(ex - 1, oy + 9, FRAME)
    for x in range(ox + 6, ex - 1):
        cv.dot(x, oy + 8, FRAME)


def staff(cv, x, top_y, foot_y, z, flick=0, hook_dir=1, lean=0.0):
    """Tall wooden staff with a hook and a hanging lantern."""
    pts = [(x + lean, top_y + 2.0), (x, foot_y)]
    cv.add(cv.tube(pts, [1.0, 1.0]), WOOD, 3, z, group="staff", contour=1)
    hx0 = x + lean
    hook = cv.tube([(hx0, top_y + 2.4), (hx0 + 0.6 * hook_dir, top_y + 0.4), (hx0 + 2.6 * hook_dir, top_y + 0.6)], [0.9, 0.9, 0.8])
    cv.add(hook, WOOD, 4, z + 0.1, group="staff", contour=1)
    lx = int(round(hx0 + 2.6 * hook_dir)) - (1 if hook_dir > 0 else 2)
    ly = int(round(top_y + 2.0))
    lantern(cv, lx, ly, z + 0.3, glow_r=7.5, flick=flick, big=True, frame="wood")


def draw_s(P: HPose):
    cv = Canvas(W, H)
    J = make_joints("s", P, PROP)
    nx, ny = J["neck"]
    sh_y = J["sh"][0][1]
    hem = 41.6 - P.lift
    sway = P.extra.get("sway", 0.0)
    # shoes peeking below the coat
    for k in range(2):
        fx, fy = J["feet"][k]
        cv.add(cv.ell(fx, fy + 0.2, 2.3, 1.4), SHOE, 2, 1, group=f"shoe{k}", contour=1)
    # long coat (A-line), with a front seam and brass buttons
    coat = cv.poly([(nx - 5.2, sh_y - 1.6), (nx + 5.2, sh_y - 1.6), (nx + 7.2 + sway, hem), (nx - 7.2 + sway, hem)], bevel=2.2)
    cv.add(coat, COAT, 3, 3, group="coat", contour=1)
    for yy in range(int(sh_y + 1), int(hem)):
        cv.dot(int(nx), yy, col(COAT, 2))
    for yy in (sh_y + 2.4, sh_y + 5.4, sh_y + 8.4, sh_y + 11.4):
        cv.dot(int(nx) + 1, int(yy), col("gold", 4))
    # blouse V at the collar
    cv.add(cv.poly([(nx - 1.8, sh_y - 1.8), (nx + 1.8, sh_y - 1.8), (nx, sh_y + 1.6)], bevel=1.0), BLOUSE, 4, 3.5, group="blouse")
    # staff in her right hand (screen left)
    hand_r = J["hands"][0]
    staff(cv, hand_r[0] - 0.4, 3.0 + P.extra.get("staff_dy", 0.0), 43.4 - P.lift, 4.5, flick=P.extra.get("flick", 0), hook_dir=-1)
    arm_g(cv, J["sh"][0], (hand_r[0] + 0.2, hand_r[1]), 5, COAT, SKIN, bend=1, group="armR", l1=4.4, l2=4.4)
    arm_g(cv, J["sh"][1], J["hands"][1], 5, COAT, SKIN, bend=-1, group="armL", l1=4.4, l2=4.4)
    cv.add(cv.ell(nx, sh_y - 0.6, 5.8, 1.8), COAT, 4, 4, group="collar", contour=1)
    hx, hy = J["head"]
    ox, oy = int(round(hx - 6)), int(round(hy - 7.5))
    add_head(cv, HEAD_S, ox, oy, HEAD_MATS, hx, hy + 0.2, 6.1, 6.4, 9)
    expr = P.expr
    face_s(cv, ox + 3, ox + 8, oy + 8, ox + 5, oy + 11, expr, SKIN)
    _specs_s(cv, ox, oy)
    cv.dots([(ox + 3, oy + 3), (ox + 4, oy + 3), (ox + 2, oy + 4)], col(HAIR, 4))
    return cv.render()


def draw_n(P: HPose):
    cv = Canvas(W, H)
    J = make_joints("n", P, PROP)
    nx, ny = J["neck"]
    sh_y = J["sh"][0][1]
    hem = 41.6 - P.lift
    sway = P.extra.get("sway", 0.0)
    for k in range(2):
        fx, fy = J["feet"][k]
        cv.add(cv.ell(fx, fy + 0.2, 2.3, 1.4), SHOE, 2, 1, group=f"shoe{k}", contour=1)
    hand_r = J["hands"][1]
    staff(cv, hand_r[0] + 0.4, 3.0 + P.extra.get("staff_dy", 0.0), 43.4 - P.lift, 3.6, flick=P.extra.get("flick", 0), hook_dir=1)
    coat = cv.poly([(nx - 5.2, sh_y - 1.6), (nx + 5.2, sh_y - 1.6), (nx + 7.2 + sway, hem), (nx - 7.2 + sway, hem)], bevel=2.2)
    cv.add(coat, COAT, 3, 3, group="coat", contour=1)
    for yy in range(int(sh_y + 9), int(hem)):
        cv.dot(int(nx), yy, col(COAT, 2))
    cv.add(cv.from_mask(cv.rect(int(nx) - 3, int(J["hip_y"]) - 2, int(nx) + 2, int(J["hip_y"]) - 1), 1.0), COAT, 4, 3.5,
           group="halfbelt", contour=1)
    arm_g(cv, J["sh"][0], J["hands"][0], 4, COAT, SKIN, bend=-1, group="armL", l1=4.4, l2=4.4)
    arm_g(cv, J["sh"][1], (hand_r[0] - 0.6, hand_r[1]), 4, COAT, SKIN, bend=1, group="armR", l1=4.4, l2=4.4)
    cv.add(cv.ell(nx, sh_y - 0.6, 5.8, 1.8), COAT, 4, 4.5, group="collar", contour=1)
    hx, hy = J["head"]
    ox, oy = int(round(hx - 6)), int(round(hy - 7.5))
    add_head(cv, HEAD_N, ox, oy, HEAD_MATS, hx, hy + 0.2, 6.1, 6.4, 9)
    return cv.render()


def draw_e(P: HPose):
    cv = Canvas(W, H)
    J = make_joints("e", P, PROP)
    nx, ny = J["neck"]
    sh = J["sh"][1]
    hip_y = J["hip_y"]
    hem = 41.6 - P.lift
    sway = P.extra.get("sway", 0.0)
    for k in range(2):
        fx, fy = J["feet"][k]
        cv.add(cv.ell(fx + 0.9, fy + 0.2, 2.8, 1.4), SHOE, 2, 1 + k * 0.1, group=f"shoe{k}", contour=1, offset=-1 if k == 0 else 0)
    # far arm (free hand) -- behind the body unless pointing
    point = P.extra.get("point", False)
    arm_g(cv, J["sh"][0], J["hands"][0], 2.5 if not point else 6.5, COAT, SKIN, bend=1, offset=-1, group="farm",
          l1=4.4, l2=4.4)
    # stooped coat: back curves, flares toward the hem
    coat = cv.poly([(nx - 3.4, sh[1] - 2.2), (nx + 2.0, sh[1] - 1.8), (nx + 3.2, sh[1] + 3.0), (nx + 3.4, hip_y),
                    (nx + 4.6 + sway, hem), (nx - 5.6 + sway, hem), (nx - 4.6, hip_y), (nx - 4.6, sh[1] + 2.0)], bevel=2.2)
    cv.add(coat, COAT, 3, 3, group="coat", contour=1)
    for yy in (sh[1] + 2.4, sh[1] + 5.4, sh[1] + 8.4):
        cv.dot(int(nx + 2.6), int(yy), col("gold", 4))
    cv.add(cv.ell(nx - 0.6, sh[1] - 1.2, 3.6, 1.8), COAT, 4, 4, group="collar", contour=1)
    hand = (J["hands"][1][0] + 3.0, J["hands"][1][1] - 1.6)
    staff(cv, hand[0] + 0.2, 3.0 + P.extra.get("staff_dy", 0.0), 43.4 - P.lift, 6, flick=P.extra.get("flick", 0), hook_dir=1,
          lean=P.extra.get("staff_lean", 0.0))
    arm_g(cv, J["sh"][1], hand, 6.5, COAT, SKIN, bend=-1, group="narm", l1=4.4, l2=4.4)
    hx, hy = J["head"]
    ox, oy = int(round(hx - 6.4)), int(round(hy - 7.5))
    add_head(cv, HEAD_E, ox, oy, HEAD_MATS, hx, hy + 0.2, 6.2, 6.4, 9)
    face_e(cv, ox + 10, oy + 8, ox + 10, oy + 11, P.expr, SKIN)
    _specs_e(cv, ox, oy)
    return cv.render()


D = {"s": draw_s, "n": draw_n, "e": draw_e}

STOOP_E = dict(lean=1.0, head=(0.6, 1.0))


def animations():
    A = {}

    def put(name, frames, fps, loop=True):
        A[name] = (frames, fps, loop)

    put("idle_s", [draw_s(HPose(expr="smile", head=(0, 0.6))), draw_s(HPose(expr="smile", head=(0, 0.6), extra={"breath": 1.0, "flick": 1}))], 2)
    put("idle_n", [draw_n(HPose(head=(0, 0.6))), draw_n(HPose(head=(0, 0.6), extra={"breath": 1.0, "flick": 1}))], 2)
    put("idle_e", [draw_e(HPose(expr="smile", **STOOP_E)), draw_e(HPose(expr="smile", **STOOP_E, extra={"breath": 1.0, "flick": 1}))], 2)
    # slow walk, staff planted and moved with the steps
    put("walk_s", [draw_s(HPose(bob=1, feet=((0, 0), (0, -1)), hands=((0, 0), (-0.4, -0.8)), head=(0, 0.6), expr="smile", extra={"sway": 0.6})),
                   draw_s(HPose(bob=0, feet=((0, 0), (0, -2)), head=(0, 0.6), expr="smile", extra={"staff_dy": -1, "flick": 1})),
                   draw_s(HPose(bob=1, feet=((0, -1), (0, 0)), hands=((0, 0), (-0.4, 0.8)), head=(0, 0.6), expr="smile", extra={"sway": -0.6})),
                   draw_s(HPose(bob=0, feet=((0, -2), (0, 0)), head=(0, 0.6), expr="smile", extra={"staff_dy": -1, "flick": 1}))], 6)
    put("walk_n", [draw_n(HPose(bob=1, feet=((0, -1), (0, 0)), head=(0, 0.6), extra={"sway": -0.6})),
                   draw_n(HPose(bob=0, feet=((0, -2), (0, 0)), head=(0, 0.6), extra={"staff_dy": -1, "flick": 1})),
                   draw_n(HPose(bob=1, feet=((0, 0), (0, -1)), head=(0, 0.6), extra={"sway": 0.6})),
                   draw_n(HPose(bob=0, feet=((0, 0), (0, -2)), head=(0, 0.6), extra={"staff_dy": -1, "flick": 1}))], 6)
    put("walk_e", [draw_e(HPose(bob=1, feet=((-2, 0), (2, 0)), hands=((1.6, -0.4), (1.4, 0)), **STOOP_E, expr="smile", extra={"sway": -0.8, "staff_lean": 1.0})),
                   draw_e(HPose(bob=0, feet=((1, -1), (-1, 0)), hands=((0.4, 0), (0.6, 0)), **STOOP_E, expr="smile", extra={"sway": -0.4, "flick": 1})),
                   draw_e(HPose(bob=1, feet=((2, 0), (-2, 0)), hands=((-1.0, -0.2), (-0.2, 0)), **STOOP_E, expr="smile", extra={"sway": -0.8, "staff_lean": -0.6})),
                   draw_e(HPose(bob=0, feet=((-1, 0), (1, -1)), hands=((0.0, 0), (0.4, 0)), **STOOP_E, expr="smile", extra={"sway": -0.4, "flick": 1}))], 6)
    # talking, free (left) hand gesturing
    put("talk_s", [draw_s(HPose(hands=((0, 0), (-2.6, -6.0)), head=(0, 0.6), expr="talk")),
                   draw_s(HPose(hands=((0, 0), (-1.6, -7.6)), head=(0, 0.6), expr="smile", extra={"flick": 1}))], 4)
    # pointing with the free hand
    put("point_e", [draw_e(HPose(hands=((9.6, -9.2), (0, 0)), lean=1.0, head=(0.8, 0.6), expr="determined", extra={"point": True}))], 4, False)
    return A


ORDER = ["idle_s", "idle_n", "idle_e", "walk_s", "walk_n", "walk_e", "talk_s", "point_e"]


def build(out_dir: str) -> SheetBuilder:
    A = animations()
    assert set(A) == set(ORDER), set(A) ^ set(ORDER)
    sb = SheetBuilder("hesper", W, H, PIVOT, columns=8, meta={"kind": "character", "role": "mentor",
                                                              "generator": "tools/sprite_forge/hesper.py"})
    for name in ORDER:
        frames, fps, loop = A[name]
        for i, f in enumerate(frames):
            pix.check_frame(f, f"hesper {name}[{i}]")
        sb.add_animation(name, frames, fps, loop)
    sb.save(out_dir)
    return sb


if __name__ == "__main__":
    import preview
    sb = build("/home/user/game/assets/sprites/characters")
    print(preview.strips(sb, scale=5))
