"""The Sigilbinder -- mysterious hooded antagonist (32x48, pivot 16,45).

Dark ink/soot cloak with a tattered hem, face lost in the hood's shadow except
two faint glowing eyes, and a glowing magenta sigil chain wound around the right
arm (bright link pixels + a soft light on the cloth around it).
"""

from __future__ import annotations

import math
import sys

import numpy as np

import pix
from human import (ADULT, H, PIVOT, W, HPose, add_head, ik2, make_joints)
from kit import Canvas
from pix import col

sys.path.insert(0, "/home/user/game/tools")
from common.sheet import SheetBuilder  # noqa: E402
from portraits import installed_by_art_forge  # noqa: E402

CLOAK, INNER, BOOT, SIG = "ink", "soot", "soot", "sigil"
TALL = dict(ADULT, hip_y=31.0, sh_y=20.6, head_y=11.8, neck_y=18.6, sh_dx=5.8, hand_dx=7.2, hand_y=29.4)

HOOD_S = [
    ".....hh.....",
    "....hhhh....",
    "...hhhhhh...",
    "..hhhhhhhh..",
    ".hhhhhhhhhh.",
    ".hhhddddhhh.",
    "hhhddddddhhh",
    "hhddddddddhh",
    "hhddddddddhh",
    "hhddddddddhh",
    "hhhddddddhhh",
    ".hhhddddhhh.",
    "..hhhhhhhh..",
]
HOOD_E = [
    "..hhh........",
    ".hhhhhh......",
    "..hhhhhhh....",
    "..hhhhhhhhh..",
    ".hhhhhhhhhhh.",
    "hhhhhhhhhhhh.",
    "hhhhhhhhhddh.",
    "hhhhhhhhdddh.",
    "hhhhhhhdddd..",
    "hhhhhhhdddd..",
    "hhhhhhhhdddh.",
    ".hhhhhhhhhh..",
    "..hhhhhhhh...",
]
HOOD_MATS = {
    "h": (CLOAK, 2, {"group": "hood", "lo": 1, "hi": 3}),
    "d": (INNER, 0, {"group": "face", "idx": None, "lo": 0, "hi": 0}),
}
EYE = col(SIG, 5)
EYE_D = col(SIG, 3)
LINK_HI = col(SIG, 5)
LINK = col(SIG, 4)
LINK_LO = col(SIG, 3)


def _line(x0, y0, x1, y1):
    n = int(max(abs(x1 - x0), abs(y1 - y0)) * 1.0) + 1
    out = []
    for i in range(n + 1):
        t = i / max(1, n)
        p = (int(math.floor(x0 + (x1 - x0) * t)), int(math.floor(y0 + (y1 - y0) * t)))
        if not out or out[-1] != p:
            out.append(p)
    return out


def chain_on_arm(cv, a, b, phase, bright, dangle=True, wraps=2):
    """Glowing chain wound around the forearm a->b: diagonal front wraps + a dangling end."""
    ax, ay = a
    bx, by = b
    L = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / L, (by - ay) / L
    px, py = -uy, ux
    w = 2.0
    pix_set = []
    off = (phase % 1.0)
    for k in range(wraps):
        t0 = (k + 0.1 + off * 0.3) / (wraps + 0.3)
        t1 = t0 + 0.5 / (wraps + 0.3)
        x0, y0 = ax + ux * L * t0 - px * w, ay + uy * L * t0 - py * w
        x1, y1 = ax + ux * L * t1 + px * w, ay + uy * L * t1 + py * w
        pix_set += _line(x0, y0, x1, y1)
    for i, (x, y) in enumerate(pix_set):
        c = LINK_HI if (i + bright) % 3 == 0 else LINK
        cv.fig.post.append((x, y, c))
    if dangle:
        for k in range(4):
            x = bx + 0.8 * math.sin(phase * 1.7 + k * 0.6)
            y = by + 1.6 + k
            cv.fig.post.append((int(math.floor(x)), int(math.floor(y)), LINK_HI if (k + bright) % 2 == 0 else LINK_LO))
    cv.fig.glows.append(((ax + bx) / 2, (ay + by) / 2, 6.0 + bright % 2, 1))


def tattered(cv, pts_top_left, pts_top_right, hem_y, x0, x1, teeth, phase=0.0):
    """Polygon for a cloak with a zig-zag tattered hem between x0 and x1."""
    pts = [pts_top_left, pts_top_right, (x1, hem_y - 1.0)]
    n = teeth
    for i in range(n, -1, -1):
        x = x0 + (x1 - x0) * i / n
        dy = 1.6 if (i + int(phase)) % 2 == 0 else -0.6
        pts.append((x, hem_y + dy))
    pts.append((x0, hem_y - 1.0))
    return pts


def draw_s(P: HPose):
    cv = Canvas(W, H)
    J = make_joints("s", P, TALL)
    nx, ny = J["neck"]
    sh_y = J["sh"][0][1]
    pulse = P.extra.get("pulse", 0)
    # boots
    for k in range(2):
        fx, fy = J["feet"][k]
        cv.add(cv.ell(fx, fy + 0.2, 2.3, 1.4), BOOT, 1, 1, group=f"boot{k}", contour=1)
    # cloak to the ankles, tattered hem
    pts = tattered(cv, (nx - 5.6, sh_y - 2.0), (nx + 5.6, sh_y - 2.0), 41.8, nx - 8.6, nx + 8.6, 8, phase=pulse)
    cv.add(cv.poly(pts, bevel=2.4), CLOAK, 2, 3, group="cloak", contour=1, lo=1)
    # front parting line
    for yy in range(int(sh_y + 2), 41):
        cv.dot(int(nx) + (1 if yy > 32 else 0), yy, col(CLOAK, 1))
    # left arm folded inside the cloak (a bulge), right arm hanging with the chain
    sh = J["sh"][0]
    hand = J["hands"][0]
    elbow = ik2(sh, hand, 4.5, 4.5, 1)
    cv.add(cv.tube([sh, elbow, hand], [2.2, 2.0, 1.8]), CLOAK, 2, 5, group="armR", contour=1, lo=1)
    cv.add(cv.circ(hand[0], hand[1] + 0.8, 1.3), INNER, 2, 5.1, group="armR", contour=1)
    chain_on_arm(cv, elbow, hand, phase=pulse * 1.3, bright=pulse)
    cv.add(cv.ell(nx + 4.0, sh_y + 7.0, 2.6, 3.6), CLOAK, 2, 4, group="armL", contour=1, lo=1)
    # mantle + hood
    cv.add(cv.ell(nx, sh_y + 0.4, 7.2, 3.0), CLOAK, 3, 6, group="mantle", contour=1, lo=1)
    hx, hy = J["head"]
    ox, oy = int(round(hx - 6)), int(round(hy - 6.5))
    add_head(cv, HOOD_S, ox, oy, HOOD_MATS, hx, hy + 0.3, 6.2, 6.6, 9)
    ey = oy + 8
    for ex in (ox + 4, ox + 7):
        cv.dot(ex, ey, EYE if pulse % 2 == 0 else EYE_D)
    return cv.render()


def draw_e(P: HPose):
    cv = Canvas(W, H)
    J = make_joints("e", P, TALL)
    nx, ny = J["neck"]
    sh = J["sh"][1]
    hip_y = J["hip_y"]
    pulse = P.extra.get("pulse", 0)
    flow = P.extra.get("flow", 0.0)
    run = P.extra.get("run", False)
    # far arm
    fsh, fh = J["sh"][0], J["hands"][0]
    fel = ik2(fsh, fh, 4.5, 4.5, 1)
    cv.add(cv.tube([fsh, fel, fh], [2.0, 1.8, 1.6]), CLOAK, 1, 0.5, group="farm", contour=1, lo=1)
    # legs (only visible when running) + boots
    for k in range(2):
        hx_, hy_ = J["hips"][k]
        fx, fy = J["feet"][k]
        ank = (fx - 0.4, fy - 2.4)
        k1 = ik2((hx_, hy_), ank, 4.9, 4.9, -1)
        k2 = ik2((hx_, hy_), ank, 4.9, 4.9, 1)
        knee = k1 if k1[0] >= k2[0] else k2
        off = -1 if k == 0 else 0
        cv.add(cv.tube([(hx_, hy_), knee, ank], [2.2, 1.9, 1.7]), INNER, 2, 1.0 + k, group=f"leg{k}", contour=1, offset=off)
        cv.add(cv.ell(fx + 0.9, fy, 2.8, 1.5) | cv.tube([ank, (fx - 0.2, fy - 0.6)], [1.8, 1.8]), BOOT, 1, 1.2 + k,
               group=f"boot{k}", contour=1, offset=off)
    # cloak: hangs from the shoulders, streams back when running
    hem = 41.8 if not run else 36.0
    back = nx - 6.0 - flow * 1.6
    pts = [(nx - 3.0, sh[1] - 2.4), (nx + 2.4, sh[1] - 1.8), (nx + 3.4, sh[1] + 4.0), (nx + 3.0 + (0 if not run else -0.5), hem - 1.0)]
    n = 6
    for i in range(n + 1):
        x = (nx + 3.0) + (back - (nx + 3.0)) * i / n
        dy = 1.4 if (i + pulse) % 2 == 0 else -0.6
        pts.append((x, hem + dy - (i * flow * 0.5 if run else 0)))
    pts.append((back + 1.0, sh[1] + 6.0 - flow * 0.4))
    cv.add(cv.poly(pts, bevel=2.4), CLOAK, 2, 3, group="cloak", contour=1, lo=1)
    # near (chain) arm
    hand = J["hands"][1]
    el = ik2(sh, hand, 4.5, 4.5, 1)
    cv.add(cv.tube([sh, el, hand], [2.2, 2.0, 1.8]), CLOAK, 2, 5, group="narm", contour=1, lo=1)
    cv.add(cv.circ(hand[0] + 0.3, hand[1] + 0.6, 1.3), INNER, 2, 5.1, group="narm", contour=1)
    chain_on_arm(cv, el, hand, phase=pulse * 1.3, bright=pulse, dangle=not run)
    cv.add(cv.ell(sh[0] - 0.4, sh[1] + 0.2, 4.2, 2.8), CLOAK, 3, 6, group="mantle", contour=1, lo=1)
    hx, hy = J["head"]
    ox, oy = int(round(hx - 6.4)), int(round(hy - 6.5))
    add_head(cv, HOOD_E, ox, oy, HOOD_MATS, hx, hy + 0.3, 6.2, 6.6, 9)
    cv.dot(ox + 10, oy + 8, EYE if pulse % 2 == 0 else EYE_D)
    return cv.render()


def animations():
    A = {}

    def put(name, frames, fps, loop=True):
        A[name] = (frames, fps, loop)

    put("idle_s", [draw_s(HPose(extra={"pulse": 0})), draw_s(HPose(extra={"pulse": 1, "breath": 1.0}))], 2)
    put("idle_e", [draw_e(HPose(extra={"pulse": 0})), draw_e(HPose(extra={"pulse": 1, "breath": 1.0}))], 2)
    run = []
    cyc = [dict(bob=1, feet=((-5, 0), (4, -1)), hands=((5.0, -4.0), (-4.0, -2.0)), extra={"pulse": 0, "flow": 3.0, "run": True}),
           dict(bob=-1, feet=((-1, -3), (0, 0)), hands=((1.0, -2.0), (-1.0, -3.0)), extra={"pulse": 1, "flow": 4.0, "run": True}),
           dict(bob=1, feet=((4, -1), (-5, 0)), hands=((-4.0, -2.0), (5.0, -4.0)), extra={"pulse": 2, "flow": 3.0, "run": True}),
           dict(bob=-1, feet=((0, 0), (-1, -3)), hands=((-1.0, -3.0), (1.0, -2.0)), extra={"pulse": 3, "flow": 4.0, "run": True})]
    for c in cyc:
        run.append(draw_e(HPose(lean=2.0, head=(0.6, 0.4), **c)))
    put("run_e", run, 10)
    return A


ORDER = ["idle_s", "idle_e", "run_e"]


def build(out_dir: str):
    if installed_by_art_forge(out_dir, "sigilbinder"):
        print("  characters  sigilbinder          kept (HD sheet from tools/art_forge)")
        return []
    A = animations()
    sb = SheetBuilder("sigilbinder", W, H, PIVOT, columns=8, meta={"kind": "character", "role": "antagonist",
                                                                   "generator": "tools/sprite_forge/sigilbinder.py"})
    for name in ORDER:
        frames, fps, loop = A[name]
        for i, f in enumerate(frames):
            pix.check_frame(f, f"sigilbinder {name}[{i}]")
        sb.add_animation(name, frames, fps, loop)
    sb.save(out_dir)
    return sb


if __name__ == "__main__":
    import preview
    sb = build("/home/user/game/assets/sprites/characters")
    print(preview.strips(sb, scale=6))
