"""Village NPCs: the farmer and the baker (32x48, pivot 16,45)."""

from __future__ import annotations

import sys

import numpy as np

import pix
from human import (ADULT, H, PIVOT, W, HPose, add_head, arm_g, face_e, face_s, legs_front_g, legs_side_g, make_joints)
from kit import Canvas
from pix import col

sys.path.insert(0, "/home/user/game/tools")
from common.sheet import SheetBuilder  # noqa: E402

# ============================================================================
# FARMER: wide straw hat, green overalls over a cream shirt, light skin, grey moustache

F_SKIN, F_HAIR, STRAW, OVER, SHIRT, BOOT = "skin_light", "hair_grey", "sand", "cloth_green", "cloth_cream", "wood"
FARM = dict(ADULT, sh_dx=5.9, hand_dx=7.4, hip_dx=2.5)

F_HEAD_S = [
    "............",
    "............",
    "............",
    "............",
    ".hhhhhhhhhh.",
    "hhssssssssshh",
    "hssssssssssh",
    "hssssssssssh",
    "hssssssssssh",
    "essssssssse.",
    ".ssssssssss.",
    "..ssssssss..",
    "...ssssss...",
]
F_HEAD_E = [
    ".............",
    ".............",
    ".............",
    ".............",
    "hhhhhhhhhh...",
    "hhhhhhhhsss..",
    "hhhhhhsssss..",
    "hhhheessssss.",
    ".hhheessssss.",
    ".hhhhssssssss",
    "..hhssssssss.",
    "...hsssssss..",
    "....ssssss...",
]
F_HEAD_N = [
    "............",
    "............",
    "............",
    "............",
    ".hhhhhhhhhh.",
    "hhhhhhhhhhhh",
    "hhhhhhhhhhhh",
    "hhhhhhhhhhhh",
    "ehhhhhhhhhhe",
    "ehhhhhhhhhhe",
    ".hhhhhhhhhh.",
    "..hhhhhhhh..",
    "...ssssss...",
]
F_MATS = {
    "h": (F_HAIR, 2, {"group": "hair"}),
    "s": (F_SKIN, 4, {"group": "face", "light": 0.55, "bands": (0.10, 0.26, -0.30, -0.9)}),
    "e": (F_SKIN, 3, {"group": "face", "light": 0.55}),
}
MOUST = col("hair_grey", 4)
MOUST_D = col("hair_grey", 2)


def straw_hat(cv, view, hx, hy, z):
    """Wide straw hat: brim + crown + a band. (hx, hy) = head centre."""
    if view in ("s", "n"):
        brim = cv.ell(hx, hy - 3.0, 9.6, 2.6)
        crown = cv.ell(hx, hy - 5.6, 4.6, 3.0) | cv.rrect(hx - 4.6, hy - 6.6, hx + 4.6, hy - 3.0, r=1.2)
    else:
        brim = cv.ell(hx - 0.4, hy - 3.2, 9.4, 1.9)
        crown = cv.ell(hx - 1.0, hy - 5.6, 4.6, 3.0) | cv.rrect(hx - 5.6, hy - 6.6, hx + 3.6, hy - 3.2, r=1.2)
    cv.add(brim, STRAW, 3, z, group="brim", contour=1, cast=2)
    cv.add(crown, STRAW, 4, z + 0.2, group="crown", contour=1, cast=1)
    bmask = cv.below([(0, hy - 5.2), (32, hy - 5.2)]) & cv.above([(0, hy - 3.6), (32, hy - 3.6)])
    band = crown.clip(bmask)
    cv.add(band, "leather", 3, z + 0.3, group="crown")
    # woven texture: a couple of darker straw ticks on the brim
    if view in ("s", "n"):
        for dx in (-7, -4, 4, 7):
            cv.dot(int(hx + dx), int(hy - 2.0), col(STRAW, 2))


def farmer_draw(view):
    def draw(P: HPose):
        cv = Canvas(W, H)
        J = make_joints(view, P, FARM)
        nx, ny = J["neck"]
        sh_y = J["sh"][0][1] if view != "e" else J["sh"][1][1]
        hip_y = J["hip_y"]
        hx, hy = J["head"]
        if view in ("s", "n"):
            legs_front_g(cv, J, 2, OVER, BOOT, boot_h=2.6, trous_base=3)
            if view == "n":
                for k in range(2):
                    arm_g(cv, J["sh"][k], J["hands"][k], 3, SHIRT, F_SKIN, bend=-1 if k == 0 else 1, group=f"arm{k}",
                          sleeve_to=0.75)
            shirt = cv.poly([(nx - 5.2, sh_y - 1.4), (nx + 5.2, sh_y - 1.4), (nx + 5.4, hip_y + 0.4), (nx - 5.4, hip_y + 0.4)], bevel=2.0)
            cv.add(shirt, SHIRT, 3, 3, group="shirt")
            # overalls: trousers top + bib + straps
            pants = cv.poly([(nx - 5.4, hip_y - 2.4), (nx + 5.4, hip_y - 2.4), (nx + 5.6, hip_y + 2.6), (nx - 5.6, hip_y + 2.6)], bevel=1.8)
            if view == "s":
                bib = cv.rrect(nx - 3.4, sh_y + 1.4, nx + 3.4, hip_y - 1.6, r=0.8, bevel=1.6)
                pants = pants | bib
            cv.add(pants, OVER, 3, 3.6, group="overalls", contour=1)
            for sgn in (-1, 1):
                strap = cv.tube([(nx + sgn * 3.0, sh_y + 1.8), (nx + sgn * 3.6, sh_y - 1.2)], [0.7, 0.7]) if view == "s" else \
                    cv.tube([(nx + sgn * 3.6, hip_y - 2.4), (nx + sgn * 1.0, sh_y + 2.0), (nx + sgn * 3.6, sh_y - 1.2)], [0.7, 0.7, 0.7])
                cv.add(strap, OVER, 3, 3.8, group="strap", contour=1)
                if view == "s":
                    cv.dot(int(nx + sgn * 3.0), int(sh_y + 2.0), col("gold", 4))
            if view == "s":
                cv.add(cv.from_mask(cv.rect(int(nx) - 1, int(sh_y + 4), int(nx), int(sh_y + 5)), 1.0), OVER, 2, 3.7, group="overalls")
                for k in range(2):
                    arm_g(cv, J["sh"][k], J["hands"][k], 5, SHIRT, F_SKIN, bend=1 if k == 0 else -1, group=f"arm{k}",
                          sleeve_to=0.75)
            cv.add(cv.ell(nx, sh_y - 1.3, 3.4, 1.4), SHIRT, 4, 5.5, group="collar", contour=1)
            ox, oy = int(round(hx - 6)), int(round(hy - 6.5))
            rows = F_HEAD_S if view == "s" else F_HEAD_N
            add_head(cv, rows, ox, oy, F_MATS, hx, hy + 0.3, 6.1, 6.3, 9)
            if view == "s":
                face_s(cv, ox + 3, ox + 8, oy + 8, ox + 5, oy + 12, P.expr if P.expr != "neutral" else "neutral", F_SKIN)
                # moustache
                cv.grid(["mmmmmm", "d....d"], ox + 3, oy + 10, {"m": MOUST, "d": MOUST_D})
                cv.dot(ox + 5, oy + 9, col(F_SKIN, 2))
            straw_hat(cv, view, hx, hy, 10)
        else:
            arm_g(cv, J["sh"][0], J["hands"][0], 0.5, SHIRT, F_SKIN, bend=1, offset=-1, group="farm", sleeve_to=0.75)
            legs_side_g(cv, J, P, 1.5, 2.5, OVER, BOOT)
            shirt = cv.poly([(nx - 3.6, sh_y - 1.6), (nx + 3.0, sh_y - 1.6), (nx + 4.0, hip_y - 1.0), (nx + 3.6, hip_y + 0.8),
                             (nx - 3.6, hip_y + 0.8), (nx - 3.8, sh_y + 2.0)], bevel=2.0)
            cv.add(shirt, SHIRT, 3, 3, group="shirt")
            over = cv.poly([(nx + 0.6, sh_y + 1.4), (nx + 3.8, sh_y + 1.4), (nx + 4.2, hip_y - 1.0), (nx + 4.0, hip_y + 2.6),
                            (nx - 3.8, hip_y + 2.6), (nx - 3.8, hip_y - 2.4)], bevel=1.8)
            cv.add(over, OVER, 3, 3.6, group="overalls", contour=1)
            strap = cv.tube([(nx + 1.4, sh_y + 1.6), (nx - 1.0, sh_y - 1.2)], [0.7, 0.7])
            cv.add(strap, OVER, 3, 3.8, group="strap", contour=1)
            arm_g(cv, J["sh"][1], J["hands"][1], 5, SHIRT, F_SKIN, bend=1, group="narm", sleeve_to=0.75)
            cv.add(cv.ell(nx, sh_y - 1.4, 2.6, 1.3), SHIRT, 4, 5.5, group="collar", contour=1)
            ox, oy = int(round(hx - 6.4)), int(round(hy - 6.5))
            add_head(cv, F_HEAD_E, ox, oy, F_MATS, hx, hy + 0.3, 6.2, 6.3, 9)
            face_e(cv, ox + 10, oy + 8, ox + 10, oy + 12, P.expr, F_SKIN)
            cv.grid(["mmm", ".md"], ox + 9, oy + 10, {"m": MOUST, "d": MOUST_D})
            straw_hat(cv, view, hx, hy, 10)
        return cv.render()
    return draw


# ============================================================================
# BAKER: cream apron over a red dress, red headscarf, tan skin, flour-dusted

B_SKIN, B_HAIR, DRESS, APRON, SCARF, SHOE = "skin_tan", "hair_brown", "cloth_red", "cloth_cream", "cloth_red", "leather"
BAKE = dict(ADULT, sh_dx=5.3, hand_dx=6.9)
FLOUR = col("cloth_cream", 5)

B_HEAD_S = [
    "............",
    "...kkkkkk...",
    "..kkkkkkkk..",
    ".kkkkkkkkkk.",
    "kkkkkkkkkkkk",
    "kkkkkkkkkkkk",
    "khhhhhhhhhhk",
    "hhsssssshssh",
    "hssssssssssh",
    "hssssssssssh",
    ".ssssssssss.",
    "..ssssssss..",
    "...ssssss...",
]
B_HEAD_E = [
    ".............",
    "...kkkkkk....",
    "..kkkkkkkkk..",
    ".kkkkkkkkkkk.",
    "kkkkkkkkkkkk.",
    "kkkkkkkkkkkk.",
    "kkkkkkkkhhss.",
    "kkhhheesssss.",
    ".hhhheesssss.",
    "..hhhssssssss",
    "..hhssssssss.",
    "...hsssssss..",
    "....ssssss...",
]
B_HEAD_N = [
    "............",
    "...kkkkkk...",
    "..kkkkkkkk..",
    ".kkkkkkkkkk.",
    "kkkkkkkkkkkk",
    "kkkkkkkkkkkk",
    "kkkkkkkkkkkk",
    "ekkkkkkkkkke",
    "ehhhhkkhhhhe",
    ".hhhkkkkhhh.",
    "..hhhkkhhh..",
    "...ssssss...",
]
B_MATS = {
    "k": (SCARF, 3, {"group": "scarf"}),
    "h": (B_HAIR, 2, {"group": "hair"}),
    "s": (B_SKIN, 4, {"group": "face", "light": 0.55, "bands": (0.10, 0.26, -0.30, -0.9)}),
    "e": (B_SKIN, 3, {"group": "face", "light": 0.55}),
}


def baker_draw(view):
    def draw(P: HPose):
        cv = Canvas(W, H)
        J = make_joints(view, P, BAKE)
        nx, ny = J["neck"]
        sh_y = J["sh"][0][1] if view != "e" else J["sh"][1][1]
        hip_y = J["hip_y"]
        hx, hy = J["head"]
        hem = 39.6 - P.lift
        sway = P.extra.get("sway", 0.0)
        if view in ("s", "n"):
            # stockings + shoes under the dress
            for k in range(2):
                fx, fy = J["feet"][k]
                cv.add(cv.tube([(fx, hem - 1.0), (fx, fy - 1.0)], [1.4, 1.4]), "cloth_cream", 2, 1.5, group=f"st{k}", contour=1)
                cv.add(cv.ell(fx, fy + 0.2, 2.2, 1.4), SHOE, 2, 1.6, group=f"shoe{k}", contour=1)
            if view == "n":
                for k in range(2):
                    arm_g(cv, J["sh"][k], J["hands"][k], 3, DRESS, B_SKIN, bend=-1 if k == 0 else 1, group=f"arm{k}",
                          sleeve_to=0.55)
            dress = cv.poly([(nx - 4.8, sh_y - 1.6), (nx + 4.8, sh_y - 1.6), (nx + 5.2, hip_y - 1.0), (nx + 7.4 + sway, hem),
                             (nx - 7.4 + sway, hem), (nx - 5.2, hip_y - 1.0)], bevel=2.2)
            cv.add(dress, DRESS, 3, 3, group="dress", contour=1)
            if view == "s":
                apron = cv.poly([(nx - 3.2, sh_y + 0.6), (nx + 3.2, sh_y + 0.6), (nx + 3.6, hip_y - 2.0), (nx + 5.2 + sway, hem - 1.6),
                                 (nx - 5.2 + sway, hem - 1.6), (nx - 3.6, hip_y - 2.0)], bevel=1.8)
                cv.add(apron, APRON, 4, 3.6, group="apron", contour=1)
                cv.add(cv.from_mask(cv.rect(int(nx) - 5, int(hip_y) - 3, int(nx) + 4, int(hip_y) - 2), 1.0), APRON, 3, 3.7,
                       group="apronband", contour=1)
                # flour dust
                cv.dots([(int(nx) - 2, int(hip_y) + 1), (int(nx) + 2, int(hip_y) + 3), (int(nx) - 1, int(hip_y) + 5),
                         (int(nx) + 1, int(sh_y) + 3)], col(APRON, 5))
                for k in range(2):
                    arm_g(cv, J["sh"][k], J["hands"][k], 5, DRESS, B_SKIN, bend=1 if k == 0 else -1, group=f"arm{k}",
                          sleeve_to=0.55)
                    hxk, hyk = J["hands"][k]
                    cv.dot(int(hxk), int(hyk - 2), FLOUR)
            else:
                cv.add(cv.from_mask(cv.rect(int(nx) - 5, int(hip_y) - 3, int(nx) + 4, int(hip_y) - 2), 1.0), APRON, 3, 3.7,
                       group="apronband", contour=1)
                bow = cv.ell(nx - 0.5, hip_y - 2.5, 2.2, 1.4)
                cv.add(bow, APRON, 4, 3.8, group="bow", contour=1)
                cv.add(cv.tube([(nx - 1.0, hip_y - 1.6), (nx - 2.0, hip_y + 2.4)], [0.8, 0.7]) |
                       cv.tube([(nx + 0.0, hip_y - 1.6), (nx + 1.0, hip_y + 2.6)], [0.8, 0.7]), APRON, 3, 3.75, group="bow", contour=1)
            cv.add(cv.ell(nx, sh_y - 1.3, 3.2, 1.3), DRESS, 4, 5.5, group="collar", contour=1)
            ox, oy = int(round(hx - 6)), int(round(hy - 6.5))
            rows = B_HEAD_S if view == "s" else B_HEAD_N
            add_head(cv, rows, ox, oy, B_MATS, hx, hy + 0.3, 6.1, 6.3, 9)
            if view == "s":
                face_s(cv, ox + 3, ox + 8, oy + 8, ox + 5, oy + 11, P.expr, B_SKIN)
                cv.dot(ox + 2, oy + 10, col(B_SKIN, 5))
                cv.dot(ox + 9, oy + 10, col(B_SKIN, 5))
                cv.dots([(ox + 3, oy + 2), (ox + 4, oy + 2), (ox + 2, oy + 3)], col(SCARF, 4))
                cv.dots([(ox + 9, oy + 2)], FLOUR)
        else:
            for k in range(2):
                fx, fy = J["feet"][k]
                cv.add(cv.tube([(fx - 0.2, hem - 1.0), (fx - 0.2, fy - 1.0)], [1.3, 1.3]), "cloth_cream", 2, 1.5 + k * 0.1,
                       group=f"st{k}", contour=1, offset=-1 if k == 0 else 0)
                cv.add(cv.ell(fx + 0.9, fy + 0.2, 2.7, 1.4), SHOE, 2, 1.6 + k * 0.1, group=f"shoe{k}", contour=1,
                       offset=-1 if k == 0 else 0)
            arm_g(cv, J["sh"][0], J["hands"][0], 0.5, DRESS, B_SKIN, bend=1, offset=-1, group="farm", sleeve_to=0.55)
            dress = cv.poly([(nx - 3.4, sh_y - 1.6), (nx + 2.8, sh_y - 1.6), (nx + 3.8, hip_y - 1.0), (nx + 5.2 + sway, hem),
                             (nx - 5.4 + sway, hem), (nx - 3.8, hip_y - 1.0)], bevel=2.2)
            cv.add(dress, DRESS, 3, 3, group="dress", contour=1)
            apron = cv.poly([(nx + 1.6, sh_y + 0.6), (nx + 3.4, sh_y + 0.8), (nx + 4.2, hip_y - 1.0), (nx + 5.6 + sway, hem - 1.6),
                             (nx + 0.4 + sway, hem - 1.6), (nx + 0.4, hip_y - 1.0)], bevel=1.6)
            cv.add(apron, APRON, 4, 3.6, group="apron", contour=1)
            cv.add(cv.from_mask(cv.rect(int(nx) - 3, int(hip_y) - 3, int(nx) + 3, int(hip_y) - 2), 1.0), APRON, 3, 3.7,
                   group="apronband", contour=1)
            cv.add(cv.ell(nx - 4.0, hip_y - 2.4, 1.6, 1.4), APRON, 4, 3.8, group="bow", contour=1)
            arm_g(cv, J["sh"][1], J["hands"][1], 5, DRESS, B_SKIN, bend=1, group="narm", sleeve_to=0.55)
            cv.add(cv.ell(nx, sh_y - 1.4, 2.6, 1.3), DRESS, 4, 5.5, group="collar", contour=1)
            ox, oy = int(round(hx - 6.4)), int(round(hy - 6.5))
            add_head(cv, B_HEAD_E, ox, oy, B_MATS, hx, hy + 0.3, 6.2, 6.3, 9)
            face_e(cv, ox + 10, oy + 8, ox + 10, oy + 11, P.expr, B_SKIN)
            # scarf knot tails at the back
            cv.add(cv.tube([(ox + 0.5, oy + 7.0), (ox - 1.2, oy + 9.6)], [0.9, 0.8]), SCARF, 3, 9.5, group="knot", contour=1)
        return cv.render()
    return draw


# ============================================================================
# animation tables (same set for both villagers)


def _anims(D, sway_key=True):
    A = {}

    def put(name, frames, fps, loop=True):
        A[name] = (frames, fps, loop)

    for d, fn in D.items():
        put(f"idle_{d}", [fn(HPose(expr="smile")), fn(HPose(expr="smile", extra={"breath": 1.0}))], 2)
    put("walk_s", [D["s"](HPose(bob=1, feet=((0, 0), (0, -1)), hands=((0.4, 1), (-0.4, -1)), expr="smile", extra={"sway": 0.6})),
                   D["s"](HPose(bob=0, feet=((0, 0), (0, -2)), expr="smile")),
                   D["s"](HPose(bob=1, feet=((0, -1), (0, 0)), hands=((0.4, -1), (-0.4, 1)), expr="smile", extra={"sway": -0.6})),
                   D["s"](HPose(bob=0, feet=((0, -2), (0, 0)), expr="smile"))], 6)
    put("walk_n", [D["n"](HPose(bob=1, feet=((0, -1), (0, 0)), hands=((0.4, -1), (-0.4, 1)), extra={"sway": -0.6})),
                   D["n"](HPose(bob=0, feet=((0, -2), (0, 0)))),
                   D["n"](HPose(bob=1, feet=((0, 0), (0, -1)), hands=((0.4, 1), (-0.4, -1)), extra={"sway": 0.6})),
                   D["n"](HPose(bob=0, feet=((0, 0), (0, -2))))], 6)
    put("walk_e", [D["e"](HPose(bob=1, feet=((-3, 0), (3, 0)), hands=((2.4, -0.6), (-2.6, -0.4)), expr="smile", extra={"sway": -0.6})),
                   D["e"](HPose(bob=0, feet=((1, -2), (-1, 0)), hands=((0.6, 0), (-0.6, 0)), expr="smile", extra={"sway": -0.3})),
                   D["e"](HPose(bob=1, feet=((3, 0), (-3, 0)), hands=((-2.4, -0.4), (2.6, -0.6)), expr="smile", extra={"sway": -0.6})),
                   D["e"](HPose(bob=0, feet=((-1, 0), (1, -2)), hands=((-0.6, 0), (0.6, 0)), expr="smile", extra={"sway": -0.3}))], 6)
    put("talk_s", [D["s"](HPose(hands=((0, 0), (-2.8, -6.0)), expr="talk")),
                   D["s"](HPose(hands=((0, 0), (-2.0, -7.0)), expr="smile"))], 4)
    return A


ORDER = ["idle_s", "idle_n", "idle_e", "walk_s", "walk_n", "walk_e", "talk_s"]


def _build(name, D, out_dir, role):
    A = _anims(D)
    assert set(A) == set(ORDER)
    sb = SheetBuilder(name, W, H, PIVOT, columns=8, meta={"kind": "character", "role": role,
                                                          "generator": "tools/sprite_forge/villagers.py"})
    for n in ORDER:
        frames, fps, loop = A[n]
        for i, f in enumerate(frames):
            pix.check_frame(f, f"{name} {n}[{i}]")
        sb.add_animation(n, frames, fps, loop)
    sb.save(out_dir)
    return sb


def build(out_dir: str):
    farmer = _build("villager_farmer", {v: farmer_draw(v) for v in "sne"}, out_dir, "villager")
    baker = _build("villager_baker", {v: baker_draw(v) for v in "sne"}, out_dir, "villager")
    return [farmer, baker]


if __name__ == "__main__":
    import preview
    for sb in build("/home/user/game/assets/sprites/characters"):
        print(preview.strips(sb, scale=4))
