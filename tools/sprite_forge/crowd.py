"""Arena crowd: seated spectators seen from the front (24x32, pivot 12,30) and
head-and-shoulders silhouettes seen from behind (32x32, pivot 16,30)."""

from __future__ import annotations

import math
import sys

import numpy as np

import pix
from human import ik2
from kit import Canvas
from pix import col

sys.path.insert(0, "/home/user/game/tools")
from common.sheet import SheetBuilder  # noqa: E402

INK_EYE = col("ink", 1)

# variant specs: skin, hair ramp, hair style, top ramp, bottom ramp, scale (1 adult / 0.8 kid), extras
FRONT = [
    dict(skin="skin_light", hair="hair_brown", style="short", top="cloth_blue", legs="earth", kid=False),
    dict(skin="skin_deep", hair="hair_black", style="long", top="cloth_mustard", legs="cloth_blue", kid=False),
    dict(skin="skin_tan", hair="hair_copper", style="short", top="cloth_green", legs="earth", kid=True, flag=True),
    dict(skin="skin_tan", hair="hair_grey", style="bald", top="cloth_plum", legs="stone_warm", kid=False, moustache=True),
    dict(skin="skin_light", hair="hair_copper", style="pony", top="cloth_teal", legs="cloth_cream", kid=False),
    dict(skin="skin_deep", hair="hair_black", style="puff", top="cloth_red", legs="cloth_blue", kid=True),
    dict(skin="skin_light", hair="hair_grey", style="bun", top="cloth_cream", legs="cloth_plum", kid=False, shawl=True),
    dict(skin="skin_deep", hair="hair_brown", style="cap", top="earth", legs="stone", kid=False, cap="cloth_red"),
]


def _hair_front(cv, st, hx, hy, r, hair, z):
    """Hair shapes for a front-facing head of radius r centred at (hx, hy)."""
    top = cv.ell(hx, hy - r * 0.35, r * 1.08, r * 0.82)
    cut = cv.below([(hx - r * 2, hy - r * 0.15), (hx - r * 0.3, hy - r * 0.35), (hx + r * 0.4, hy - r * 0.15), (hx + r * 2, hy - r * 0.3)])
    if st == "short":
        m = top.cut(cut) | cv.ell(hx - r * 0.95, hy, r * 0.25, r * 0.5) | cv.ell(hx + r * 0.95, hy, r * 0.25, r * 0.5)
        m = m | cv.ell(hx - r * 0.3, hy - r * 1.0, r * 0.3, r * 0.3)
    elif st == "long":
        m = top.cut(cut) | cv.rrect(hx - r * 1.2, hy - r * 0.4, hx - r * 0.75, hy + r * 1.45, r=0.8) | \
            cv.rrect(hx + r * 0.75, hy - r * 0.4, hx + r * 1.2, hy + r * 1.45, r=0.8)
    elif st == "bald":
        m = cv.ell(hx - r * 0.95, hy - r * 0.05, r * 0.28, r * 0.42) | cv.ell(hx + r * 0.95, hy - r * 0.05, r * 0.28, r * 0.42)
    elif st == "pony":
        m = top.cut(cut) | cv.ell(hx + r * 1.15, hy + r * 0.2, r * 0.4, r * 0.75)
    elif st == "puff":
        m = cv.ell(hx, hy - r * 0.45, r * 1.35, r * 1.0).cut(cut)
    elif st == "bun":
        m = top.cut(cut) | cv.circ(hx, hy - r * 1.0, r * 0.42)
    else:  # cap: hair only at the sides
        m = cv.ell(hx - r * 0.95, hy, r * 0.25, r * 0.45) | cv.ell(hx + r * 0.95, hy, r * 0.25, r * 0.45)
    if m.area():
        cv.add(m, hair, 3, z, group="hair", contour=None)


def draw_front(spec, pose: str, frame: int):
    W, H = 24, 32
    cv = Canvas(W, H)
    kid = spec.get("kid", False)
    s = 0.82 if kid else 1.0
    bob = (1 if frame == 1 else 0) if pose == "idle" else (0 if frame == 0 else -1)
    cx = 12.0
    hip_y = 23.6 + (1.6 if kid else 0.0)
    sh_y = (15.2 if not kid else 17.6) + bob
    hr = 4.9 * (0.94 if kid else 1.0)
    hx, hy = cx, sh_y - hr - 0.6
    skin, top, legs = spec["skin"], spec["top"], spec["legs"]
    # seated legs: knees toward the camera, shins down to the feet on the pivot line
    for k, sgn in enumerate((-1, 1)):
        kx = cx + sgn * 2.4 * s
        cv.add(cv.tube([(kx, hip_y), (kx + sgn * 0.3, 27.0), (kx + sgn * 0.3, 28.6)], [2.0 * s, 1.9 * s, 1.8 * s]), legs, 3, 1,
               group=f"leg{k}", contour=1)
        cv.add(cv.ell(kx + sgn * 0.4, 29.0, 2.1 * s, 1.15), "leather", 2, 1.2, group=f"shoe{k}", contour=1)
    # torso
    tw = 5.0 * s
    torso = cv.poly([(cx - tw, sh_y - 0.6), (cx + tw, sh_y - 0.6), (cx + tw + 0.4, hip_y + 0.6), (cx - tw - 0.4, hip_y + 0.6)], bevel=2.0)
    cv.add(torso, top, 3, 2, group="torso", contour=1)
    if spec.get("shawl"):
        cv.add(cv.poly([(cx - tw - 0.6, sh_y - 1.0), (cx + tw + 0.6, sh_y - 1.0), (cx, sh_y + 5.0)], bevel=1.6), "cloth_teal", 3, 2.5,
               group="shawl", contour=1)
    # arms
    shs = [(cx - tw + 0.4, sh_y + 0.6), (cx + tw - 0.4, sh_y + 0.6)]
    if pose == "idle":
        hands = [(cx - 3.0 * s, hip_y - 0.6 + bob * 0.0), (cx + 3.0 * s, hip_y - 0.6)]
    else:
        up = 8.6 if frame == 0 else 9.8
        hands = [(cx - 7.4 * s, sh_y - up * s), (cx + 7.4 * s, sh_y - up * s)]
        if spec.get("flag"):
            hands[1] = (cx + 5.0, sh_y - up * s + 1.0)
    for k in range(2):
        el = ik2(shs[k], hands[k], 3.8 * s, 3.8 * s, 1 if k == 0 else -1)
        cv.add(cv.tube([shs[k], el, hands[k]], [1.4 * s, 1.3 * s, 1.2 * s]), top, 3, 4, group=f"arm{k}", contour=1)
        cv.add(cv.circ(hands[k][0], hands[k][1], 1.3 * s), skin, 3, 4.1, group=f"arm{k}", contour=1)
    # flag held by the kid
    if spec.get("flag"):
        fx, fy = hands[1]
        pole_top = fy - (6.0 if pose == "cheer" else 9.0)
        cv.add(cv.tube([(fx, fy + 1.0), (fx, pole_top)], [0.6, 0.6]), "wood", 4, 3.9, group="pole", contour=1)
        wave = (frame % 2) * 0.8 if pose == "cheer" else 0.0
        flag = cv.poly([(fx + 0.4, pole_top), (fx + 5.0, pole_top + 1.2 + wave), (fx + 4.6, pole_top + 3.0 + wave),
                        (fx + 0.4, pole_top + 4.0)], bevel=1.4)
        cv.add(flag, "cloth_teal", 4, 3.95, group="flag", contour=1)
        cv.dot(int(fx + 3), int(pole_top + 2 + wave * 0.5), col("gold", 4))
    # neck + head
    cv.add(cv.tube([(hx, hy + hr * 0.6), (hx, sh_y - 0.4)], [1.6 * s, 1.6 * s]), skin, 3, 4.5, group="neck", contour=1)
    head = cv.ell(hx, hy, hr, hr * 1.02)
    cv.add(head, skin, 4, 5, group="face", light=0.55, bands=(0.10, 0.26, -0.30, -0.9))
    _hair_front(cv, spec["style"], hx, hy, hr, spec["hair"], 5.5)
    if spec.get("cap"):
        capm = cv.ell(hx, hy - hr * 0.55, hr * 1.05, hr * 0.62).clip(cv.above([(0, hy - hr * 0.2), (24, hy - hr * 0.2)]))
        cv.add(capm, spec["cap"], 3, 5.6, group="cap", contour=1)
        cv.add(cv.ell(hx, hy - hr * 0.2, hr * 1.1, 0.9), spec["cap"], 2, 5.7, group="capb", contour=1)
    # face
    ey = int(round(hy - 0.2))
    ex0, ex1 = int(round(hx - 2.0 * s)) - 1, int(round(hx + 2.0 * s))
    my = int(round(hy + hr * 0.62))
    if pose == "cheer":
        for x in (ex0, ex1):
            cv.dot(x - 1, ey + 1, INK_EYE)
            cv.dot(x, ey, INK_EYE)
            cv.dot(x + 1, ey + 1, INK_EYE)
        cv.dot(int(hx) - 1, my, col(skin, 1))
        cv.dot(int(hx), my, col(skin, 1))
        cv.dot(int(hx) - 1, my + 1, col("cloth_red", 3))
        cv.dot(int(hx), my + 1, col("cloth_red", 3))
    else:
        for x in (ex0, ex1):
            cv.dot(x, ey, INK_EYE)
            cv.dot(x, ey + 1, INK_EYE)
        cv.dot(int(hx) - 1, my, col(skin, 2))
        cv.dot(int(hx), my, col(skin, 2))
    if spec.get("moustache"):
        cv.grid(["mmmm"], int(hx) - 2, my - 1, {"m": col("hair_grey", 4)})
    return cv.render()


# ----------------------------------------------------------------------------
# back view: head and shoulders (foreground silhouettes)

BACK = [
    dict(hair="hair_brown", style="short", top="cloth_blue", skin="skin_tan"),
    dict(hair="hair_black", style="bun", top="cloth_red", skin="skin_deep"),
    dict(hair="hair_copper", style="pony", top="cloth_green", skin="skin_light"),
    dict(hair="hair_grey", style="bald", top="cloth_plum", skin="skin_light"),
    dict(hair="hair_brown", style="cap", top="cloth_mustard", skin="skin_deep", cap="cloth_teal"),
    dict(hair="hair_black", style="puff", top="cloth_teal", skin="skin_tan"),
]


def draw_back(spec, pose: str, frame: int):
    W, H = 32, 32
    cv = Canvas(W, H)
    bob = (1 if frame == 1 else 0) if pose == "idle" else (-1 if frame == 1 else 0)
    cx = 16.0
    sh_y = 22.0 + bob
    hx, hy = cx, 13.0 + bob
    r = 6.4
    top, skin, hair = spec["top"], spec["skin"], spec["hair"]
    # shoulders cut off by the frame bottom (pivot row)
    sh = cv.ell(cx, sh_y + 8.0, 13.6, 9.6).clip(cv.above([(0, 30.5), (32, 30.5)]))
    cv.add(sh, top, 3, 2, group="sh", contour=1)
    if pose == "cheer":
        up = 9.0 if frame == 0 else 11.0
        for sgn in (-1, 1):
            a = (cx + sgn * 10.0, sh_y + 3.0)
            hnd = (cx + sgn * 11.6, sh_y - up)
            cv.add(cv.tube([a, (cx + sgn * 11.0, sh_y - 3.0), hnd], [2.3, 2.1, 1.9]), top, 3, 3, group=f"arm{sgn}", contour=1)
            cv.add(cv.circ(hnd[0], hnd[1] - 1.0, 1.9), skin, 3, 3.1, group=f"arm{sgn}", contour=1)
    cv.add(cv.tube([(hx, hy + 4.0), (hx, sh_y + 1.0)], [3.0, 3.0]), skin, 2, 2.5, group="neck", contour=1)
    for sgn in (-1, 1):
        cv.add(cv.ell(hx + sgn * r * 0.98, hy + 0.8, 1.3, 1.9), skin, 3, 3.5, group="ears", contour=1)
    st = spec["style"]
    head = cv.ell(hx, hy, r, r * 1.04)
    if st == "bald":
        cv.add(head, skin, 3, 4, group="scalp", spec=True)
        cv.add(cv.ell(hx, hy + r * 0.55, r * 1.0, r * 0.5).clip(cv.below([(0, hy + 1.0), (32, hy + 1.0)])), hair, 3, 4.5,
               group="hair")
    else:
        hm = head
        if st == "puff":
            hm = cv.ell(hx, hy - 1.0, r * 1.3, r * 1.15)
        elif st == "bun":
            hm = head | cv.circ(hx, hy - r * 0.55, r * 0.5)
        elif st == "pony":
            hm = head | cv.tube([(hx, hy + 1.0), (hx + 0.6, hy + r + 2.4)], [2.0, 1.4])
        cv.add(hm, hair, 3, 4, group="hair", contour=1)
        if st == "bun":
            cv.add(cv.circ(hx, hy - r * 0.55, r * 0.5), hair, 4, 4.2, group="bun", contour=1)
        if st == "cap":
            capm = cv.ell(hx, hy - 1.4, r * 1.04, r * 0.78).clip(cv.above([(0, hy + 0.6), (32, hy + 0.6)]))
            cv.add(capm, spec["cap"], 3, 4.5, group="cap", contour=1)
            cv.add(cv.tube([(hx - 3.0, hy + 0.6), (hx + 3.0, hy + 0.6)], [0.8, 0.8]), spec["cap"], 2, 4.6, group="capb", contour=1)
    return cv.render()


def build(out_dir: str):
    sbf = SheetBuilder("crowd", 24, 32, (12, 30), columns=8, meta={"kind": "crowd", "view": "front",
                                                                    "generator": "tools/sprite_forge/crowd.py"})
    for v, spec in enumerate(FRONT):
        for pose, fps in (("idle", 2), ("cheer", 6)):
            frames = [draw_front(spec, pose, f) for f in range(2)]
            for i, f in enumerate(frames):
                pix.check_frame(f, f"crowd {pose}_v{v}[{i}]")
            sbf.add_animation(f"{pose}_v{v}", frames, fps, True)
    sbf.save(out_dir)
    sbb = SheetBuilder("crowd_back", 32, 32, (16, 30), columns=8, meta={"kind": "crowd", "view": "back",
                                                                         "generator": "tools/sprite_forge/crowd.py"})
    for v, spec in enumerate(BACK):
        for pose, fps in (("idle", 2), ("cheer", 6)):
            frames = [draw_back(spec, pose, f) for f in range(2)]
            for i, f in enumerate(frames):
                pix.check_frame(f, f"crowd_back {pose}_v{v}[{i}]")
            sbb.add_animation(f"{pose}_v{v}", frames, fps, True)
    sbb.save(out_dir)
    return [sbf, sbb]


if __name__ == "__main__":
    import preview
    out = "/home/user/game/assets/sprites/characters"
    for sb in build(out):
        print(preview.contact(f"{out}/{sb.name}.png", scale=5))
