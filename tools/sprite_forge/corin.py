"""Corin -- the rival apprentice, an energetic teen (32x48, pivot 16,45).

Spiky copper hair with a red headband, deep brown skin, sleeveless mustard vest
over a dark shirt, fingerless gloves, blue trousers rolled at the shins, boots.
"""

from __future__ import annotations

import sys

import pix
from human import (H, PIVOT, W, HPose, add_head, arm_g, face_e, face_s, legs_front_g, legs_side_g, make_joints)
from kit import Canvas
from pix import col

sys.path.insert(0, "/home/user/game/tools")
from common.sheet import SheetBuilder  # noqa: E402

SKIN, HAIR, BAND = "skin_deep", "hair_copper", "cloth_red"
VEST, SHIRT, TROUS, BOOT, GLOVE = "cloth_mustard", "stone", "cloth_blue", "leather", "leather"

TEEN = dict(hip_y=32.6, sh_y=23.2, head_y=14.6, neck_y=21.0, sh_dx=5.2, hip_dx=2.3, foot_dx=3.2,
            hand_y=31.0, hand_dx=6.8, e_sh_x=15.6, e_head_x=16.4, leg_l=4.4, arm_l=4.2)

HEAD_S = [
    "..h...h..h..",
    ".hh.hhhhhh..",
    ".hhhhhhhhhhh",
    "hhhhhhhhhhhh",
    "hhhhhhhhhhhh",
    "bbbbbbbbbbbb",
    "hhsssssssshh",
    "hssssssssssh",
    "hssssssssssh",
    "hssssssssssh",
    ".ssssssssss.",
    "..ssssssss..",
    "...ssssss...",
]
HEAD_E = [
    "...h.h.h.....",
    "..hhhhhhhh...",
    ".hhhhhhhhhh..",
    "hhhhhhhhhhhh.",
    "hhhhhhhhhhhh.",
    "bbbbbbbbbbbbb",
    "bhhhhhhhssss.",
    "bbhhheesssss.",
    "b.hhheesssss.",
    "..hhhssssssss",
    "..hhssssssss.",
    "...hsssssss..",
    "....ssssss...",
]
HEAD_N = [
    "..h...h..h..",
    ".hh.hhhhhh..",
    ".hhhhhhhhhhh",
    "hhhhhhhhhhhh",
    "hhhhhhhhhhhh",
    "bbbbbbbbbbbb",
    "hhhhhhbbhhhh",
    "ehhhhhhbhhhe",
    "ehhhhhhhbhhe",
    ".hhhhhhhhhh.",
    "..hhhhhhhh..",
    "...ssssss...",
]
HEAD_MATS = {
    "h": (HAIR, 4, {"group": "hair"}),
    "b": (BAND, 2, {"group": "band", "contour": None, "lo": 1, "hi": 3}),
    "s": (SKIN, 4, {"group": "face", "light": 0.55, "bands": (0.10, 0.26, -0.30, -0.9)}),
    "e": (SKIN, 3, {"group": "face", "light": 0.55}),
}


def _shine(cv, view, ox, oy):
    c = col(HAIR, 5)
    pts = [(ox + 3, oy + 2), (ox + 4, oy + 2), (ox + 2, oy + 3)] if view != "e" else [(ox + 4, oy + 2), (ox + 5, oy + 2), (ox + 3, oy + 3)]
    cv.dots(pts, c)


def _gloves(cv, J, z):
    for k in range(2):
        hx, hy = J["hands"][k]
        cv.dot(int(hx), int(hy + 1.6), col(SKIN, 4))


def draw_s(P: HPose):
    cv = Canvas(W, H)
    J = make_joints("s", P, TEEN)
    nx, ny = J["neck"]
    sh_y = J["sh"][0][1]
    hip_y = J["hip_y"]
    legs_front_g(cv, J, 2, TROUS, BOOT, knees=P.knees, boot_h=2.4, roll=TROUS, bare=SKIN)
    shirt = cv.poly([(nx - 4.6, sh_y - 1.4), (nx + 4.6, sh_y - 1.4), (nx + 4.6, hip_y + 0.8), (nx - 4.6, hip_y + 0.8)], bevel=2.0)
    cv.add(shirt, SHIRT, 2, 3, group="shirt", hi=3)
    cv.add(cv.from_mask(cv.rect(int(nx) - 5, int(hip_y) - 1, int(nx) + 4, int(hip_y)), 1.0), "leather", 2, 3.3, group="belt")
    vl = cv.poly([(nx - 5.0, sh_y - 1.6), (nx - 1.0, sh_y - 1.0), (nx - 1.6, hip_y - 0.6), (nx - 5.2, hip_y - 0.2)], bevel=1.8)
    vr = cv.poly([(nx + 1.0, sh_y - 1.0), (nx + 5.0, sh_y - 1.6), (nx + 5.2, hip_y - 0.2), (nx + 1.6, hip_y - 0.6)], bevel=1.8)
    cv.add(vl, VEST, 3, 4, group="vestl", contour=1)
    cv.add(vr, VEST, 3, 4, group="vestr", contour=1)
    for k in range(2):
        arm_g(cv, J["sh"][k], J["hands"][k], 5, SHIRT, SKIN, bend=1 if k == 0 else -1, group=f"arm{k}",
              l1=TEEN["arm_l"], l2=TEEN["arm_l"], glove=GLOVE, sleeve_to=0.35, fist=P.extra.get("fist", False))
    _gloves(cv, J, 5)
    # collar
    cv.add(cv.ell(nx, sh_y - 1.4, 3.0, 1.2), SHIRT, 2, 5.5, group="collar", contour=1)
    hx, hy = J["head"]
    ox, oy = int(round(hx - 6)), int(round(hy - 7.5))
    cv.add(cv.tube([(nx, oy + 11.0), (nx, sh_y - 0.5)], [2.0, 2.0]), SKIN, 3, 5.4, group="neck", contour=1)
    add_head(cv, HEAD_S, ox, oy, HEAD_MATS, hx, hy - 0.2, 6.1, 6.6, 9)
    _shine(cv, "s", ox, oy)
    face_s(cv, ox + 3, ox + 8, oy + 8, ox + 5, oy + 11, P.expr, SKIN)
    return cv.render()


def draw_n(P: HPose):
    cv = Canvas(W, H)
    J = make_joints("n", P, TEEN)
    nx, ny = J["neck"]
    sh_y = J["sh"][0][1]
    hip_y = J["hip_y"]
    legs_front_g(cv, J, 2, TROUS, BOOT, knees=P.knees, boot_h=2.4, roll=TROUS, bare=SKIN)
    for k in range(2):
        arm_g(cv, J["sh"][k], J["hands"][k], 3, SHIRT, SKIN, bend=-1 if k == 0 else 1, group=f"arm{k}",
              l1=TEEN["arm_l"], l2=TEEN["arm_l"], glove=GLOVE, sleeve_to=0.35)
    vest = cv.poly([(nx - 5.0, sh_y - 1.6), (nx + 5.0, sh_y - 1.6), (nx + 5.2, hip_y + 0.4), (nx - 5.2, hip_y + 0.4)], bevel=2.2)
    cv.add(vest, VEST, 3, 4, group="vest", contour=1)
    for yy in range(int(sh_y + 1), int(hip_y)):
        cv.dot(int(nx) - 1, yy, col(VEST, 2))
    hx, hy = J["head"]
    ox, oy = int(round(hx - 6)), int(round(hy - 7.5))
    cv.add(cv.tube([(nx, oy + 10.0), (nx, sh_y - 0.5)], [2.0, 2.0]), SKIN, 3, 3.6, group="neck", contour=1)
    cv.add(cv.ell(nx, sh_y - 1.2, 3.2, 1.3), SHIRT, 2, 4.5, group="collar", contour=1)
    add_head(cv, HEAD_N, ox, oy, HEAD_MATS, hx, hy - 0.2, 6.1, 6.6, 9)
    _shine(cv, "n", ox, oy)
    return cv.render()


def draw_e(P: HPose):
    cv = Canvas(W, H)
    J = make_joints("e", P, TEEN)
    nx, ny = J["neck"]
    sh = J["sh"][1]
    hip_y = J["hip_y"]
    arm_g(cv, J["sh"][0], J["hands"][0], 0.5, SHIRT, SKIN, bend=1, offset=-1, group="farm", l1=TEEN["arm_l"],
          l2=TEEN["arm_l"], glove=GLOVE, sleeve_to=0.35)
    legs_side_g(cv, J, P, 1.5, 2.5, TROUS, BOOT, roll=TROUS, leg_l=TEEN["leg_l"], bare=SKIN)
    shirt = cv.poly([(nx - 3.4, sh[1] - 1.6), (nx + 3.0, sh[1] - 1.6), (nx + 3.8, hip_y - 1.0), (nx + 3.4, hip_y + 0.8),
                     (nx - 3.4, hip_y + 0.8), (nx - 3.8, sh[1] + 2.0)], bevel=2.0)
    cv.add(shirt, SHIRT, 2, 3, group="shirt", hi=3)
    vest = cv.poly([(nx - 3.8, sh[1] - 1.8), (nx + 1.8, sh[1] - 1.6), (nx + 2.6, hip_y - 0.8), (nx - 3.6, hip_y)], bevel=2.0)
    cv.add(vest, VEST, 3, 4, group="vest", contour=1)
    cv.add(cv.from_mask(cv.rect(int(nx) - 3, int(hip_y) - 1, int(nx) + 3, int(hip_y)), 1.0), "leather", 2, 4.2, group="belt")
    arm_g(cv, J["sh"][1], J["hands"][1], 5, SHIRT, SKIN, bend=1, group="narm", l1=TEEN["arm_l"], l2=TEEN["arm_l"],
          glove=GLOVE, sleeve_to=0.35)
    hx, hy = J["head"]
    ox, oy = int(round(hx - 6.4)), int(round(hy - 7.5))
    cv.add(cv.tube([(nx + 0.4, oy + 11.0), (nx, sh[1] - 0.5)], [2.0, 2.0]), SKIN, 3, 4.6, group="neck", contour=1)
    add_head(cv, HEAD_E, ox, oy, HEAD_MATS, hx, hy - 0.2, 6.2, 6.6, 9)
    _shine(cv, "e", ox, oy)
    flap = P.extra.get("flap", 0)
    if flap:
        cv.dots([(ox - 1, oy + 7 + (flap % 2)), (ox - 2, oy + 7)], col(BAND, 3))
    face_e(cv, ox + 10, oy + 8, ox + 10, oy + 11, P.expr, SKIN)
    return cv.render()


D = {"s": draw_s, "n": draw_n, "e": draw_e}


def animations():
    A = {}

    def put(name, frames, fps, loop=True):
        A[name] = (frames, fps, loop)

    for d, fn in D.items():
        put(f"idle_{d}", [fn(HPose(expr="smile")), fn(HPose(expr="smile", extra={"breath": 1.0}))], 3)
    # bouncy energetic walk
    put("walk_s", [draw_s(HPose(bob=1, feet=((0, 0), (0, -1)), hands=((0.6, 1.4), (-0.6, -1.4)), expr="smile")),
                   draw_s(HPose(bob=-1, feet=((0, 0), (0, -2)), hands=((0, 0), (0, 0)), expr="smile")),
                   draw_s(HPose(bob=1, feet=((0, -1), (0, 0)), hands=((0.6, -1.4), (-0.6, 1.4)), expr="smile")),
                   draw_s(HPose(bob=-1, feet=((0, -2), (0, 0)), hands=((0, 0), (0, 0)), expr="smile"))], 9)
    put("walk_n", [draw_n(HPose(bob=1, feet=((0, -1), (0, 0)), hands=((0.6, -1.4), (-0.6, 1.4)))),
                   draw_n(HPose(bob=-1, feet=((0, -2), (0, 0)))),
                   draw_n(HPose(bob=1, feet=((0, 0), (0, -1)), hands=((0.6, 1.4), (-0.6, -1.4)))),
                   draw_n(HPose(bob=-1, feet=((0, 0), (0, -2))))], 9)
    put("walk_e", [draw_e(HPose(bob=1, feet=((-3, 0), (3, 0)), hands=((3.0, -1.0), (-3.0, -0.6)), expr="smile", extra={"flap": 1})),
                   draw_e(HPose(bob=-1, feet=((1, -2), (-1, 0)), hands=((0.8, 0), (-0.8, 0)), expr="smile", extra={"flap": 2})),
                   draw_e(HPose(bob=1, feet=((3, 0), (-3, 0)), hands=((-3.0, -0.6), (3.0, -1.0)), expr="smile", extra={"flap": 1})),
                   draw_e(HPose(bob=-1, feet=((-1, 0), (1, -2)), hands=((-0.8, 0), (0.8, 0)), expr="smile", extra={"flap": 2}))], 9)
    # talking with a gesturing hand
    put("talk_s", [draw_s(HPose(hands=((0, 0), (-3.0, -6.0)), expr="talk", extra={"fist": True})),
                   draw_s(HPose(hands=((0, 0), (-2.4, -7.4)), expr="grin", extra={"breath": 0.0}))], 4)
    # fist pump
    put("cheer_s", [draw_s(HPose(hands=((0, 0), (-0.6, -17.0)), expr="cheer", lift=1, extra={"fist": True})),
                    draw_s(HPose(hands=((0, 0), (-1.0, -9.0)), expr="grin", bob=1, extra={"fist": True}))], 5)
    # disappointed slump, head down
    put("slump_s", [draw_s(HPose(bob=1, head=(0, 1.0), hands=((0.8, 1.4), (-0.8, 1.4)), expr="sulk")),
                    draw_s(HPose(bob=2, head=(0, 1.0), hands=((0.8, 2.0), (-0.8, 2.0)), expr="sulk"))], 2)
    return A


ORDER = ["idle_s", "idle_n", "idle_e", "walk_s", "walk_n", "walk_e", "talk_s", "cheer_s", "slump_s"]


def build(out_dir: str) -> SheetBuilder:
    A = animations()
    assert set(A) == set(ORDER), set(A) ^ set(ORDER)
    sb = SheetBuilder("corin", W, H, PIVOT, columns=8, meta={"kind": "character", "role": "rival",
                                                             "generator": "tools/sprite_forge/corin.py"})
    for name in ORDER:
        frames, fps, loop = A[name]
        for i, f in enumerate(frames):
            pix.check_frame(f, f"corin {name}[{i}]")
        sb.add_animation(name, frames, fps, loop)
    sb.save(out_dir)
    return sb


if __name__ == "__main__":
    import preview
    sb = build("/home/user/game/assets/sprites/characters")
    print(preview.strips(sb, scale=5))
