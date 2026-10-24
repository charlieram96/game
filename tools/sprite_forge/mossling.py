"""Mossling -- small grove-element kith of the meadow (32x32, pivot 16,29).

A round moss-covered puffball with long floppy lop-rabbit leaf ears, a tiny
two-leaf sprout on its head, stubby feet, shiny dark eyes and a pink-ish nose.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass

import numpy as np

import pix
from kit import Canvas
from pix import bezier, col

sys.path.insert(0, "/home/user/game/tools")
from common.sheet import SheetBuilder  # noqa: E402

W = H = 32
PIVOT = (16, 29)
BODY, BELLY, LEAF, FOOT = "glow_moss", "glow_moss", "leaf", "moss"
EYE = col("ink", 0)
EYE2 = col("ink", 2)
GLINT = col("cloth_cream", 5)
NOSE = col("sigil", 5)
NOSE_D = col("sigil", 4)
BLUSH = col("sigil", 5)


@dataclass
class MPose:
    lift: float = 0.0
    squash: float = 0.0       # + wider/shorter, - taller/narrower
    ears: float = 0.0         # 0 floppy down, 1 perked up
    ear_sway: float = 0.0
    sprout: float = 0.0       # sprout lean
    eyes: str = "open"        # open | wide | closed
    feet_up: float = 0.0
    x: float = 0.0


def _ear(cv, root, tip, mid_bulge, z, flip=False, offset=0):
    """Leaf-shaped ear from root to tip: a fat bezier tube with a darker midrib."""
    rx, ry = root
    tx, ty = tip
    mx = (rx + tx) / 2 + mid_bulge[0]
    my = (ry + ty) / 2 + mid_bulge[1]
    pts = bezier([root, (mx, my), tip], 9)
    radii = [1.4, 2.0, 2.4, 2.5, 2.4, 2.1, 1.6, 1.0, 0.6]
    s = cv.tube(pts, radii)
    cv.add(s, LEAF, 4, z, group=f"ear{z}", contour=1, offset=offset)
    # midrib (vein) pixels
    for (x, y) in pts[2:-2]:
        cv.dot(int(math.floor(x)), int(math.floor(y)), col(LEAF, 3 + offset))


def _sprout(cv, x, y, lean, z):
    stem = cv.tube([(x, y), (x + lean * 0.5, y - 2.6)], [0.6, 0.6])
    cv.add(stem, LEAF, 3, z, group="sprout", contour=1)
    tx, ty = x + lean * 0.5, y - 2.6
    l1 = cv.ell(tx - 2.0, ty - 0.8, 2.0, 1.1, angle=0.5)
    l2 = cv.ell(tx + 2.0, ty - 1.2, 2.0, 1.1, angle=-0.5)
    cv.add(l1 | l2, LEAF, 5, z + 0.1, group="sprout", contour=1)


def _fuzz(cv, cx, cy, rx, ry, n=14, phase=0.0):
    """Small bumps around the silhouette so it reads as a mossy puff."""
    s = cv.empty()
    for i in range(n):
        a = phase + i * 2 * math.pi / n
        if math.sin(a) > 0.75:      # leave the bottom (feet) smooth
            continue
        s = s | cv.circ(cx + (rx - 0.6) * math.cos(a), cy + (ry - 0.6) * math.sin(a), 1.5)
    return s


def draw(view: str, p: MPose):
    cv = Canvas(W, H)
    sq = p.squash
    cx = 16.0 + p.x
    ground = 28.0
    rx, ry = 7.6 + sq, 7.2 - sq
    cy = ground - ry - 0.6 - p.lift
    # feet
    fy = ground - 0.6 - p.lift + p.feet_up
    if view == "e":
        for k, dx in enumerate((-3.0, 2.4)):
            cv.add(cv.ell(cx + dx + 0.6, fy, 2.2, 1.3), FOOT, 3, 1 + k * 4, group=f"foot{k}", contour=1, offset=-1 if k == 0 else 0)
    else:
        for k, dx in enumerate((-3.4, 3.4)):
            cv.add(cv.ell(cx + dx, fy, 2.2, 1.3), FOOT, 3, 1, group=f"foot{k}", contour=1)
    # ears: floppy (down the sides) -> perked (up)
    e = p.ears
    sw = p.ear_sway
    if view == "s" or view == "n":
        zf = 6 if view == "s" else 2
        for sgn in (-1, 1):
            root = (cx + sgn * 3.8, cy - ry + 2.2)
            down_tip = (cx + sgn * (rx + 0.6) + sgn * sw, cy + 5.2)
            up_tip = (cx + sgn * 5.0 + sgn * sw, cy - ry - 8.0)
            tip = (down_tip[0] * (1 - e) + up_tip[0] * e, down_tip[1] * (1 - e) + up_tip[1] * e)
            bulge = (sgn * 2.6 * (1 - e) + sgn * 0.6 * e, -2.2 * (1 - e))
            _ear(cv, root, tip, bulge, zf if e < 0.5 else 2.5, offset=0)
    else:
        # far ear behind, near ear in front
        root_f = (cx - 1.6, cy - ry + 2.0)
        root_n = (cx - 0.4, cy - ry + 2.4)
        down_f = (cx - 6.0 + sw, cy - 1.0)
        down_n = (cx - 3.6 + sw, cy + 3.6)
        up_f = (cx - 5.4 + sw, cy - ry - 7.0)
        up_n = (cx - 3.0 + sw, cy - ry - 7.4)
        lerp = lambda a, b: (a[0] * (1 - e) + b[0] * e, a[1] * (1 - e) + b[1] * e)  # noqa: E731
        _ear(cv, root_f, lerp(down_f, up_f), (-1.4 * (1 - e), -1.0 * (1 - e)), 2, offset=-1)
        _ear(cv, root_n, lerp(down_n, up_n), (-1.8 * (1 - e), -0.6 * (1 - e)), 7 if e < 0.5 else 2.6)
    # body puff
    body = cv.ell(cx, cy, rx, ry) | _fuzz(cv, cx, cy, rx, ry, 16, 0.2)
    cv.add(body, BODY, 3, 4, group="body", contour=None)
    if view == "s":
        belly = cv.ell(cx, cy + 2.4, rx * 0.62, ry * 0.58)
        cv.add(belly, BELLY, 4, 4.2, group="body")
    elif view == "e":
        belly = cv.ell(cx + 2.6, cy + 2.2, rx * 0.55, ry * 0.55)
        cv.add(belly, BELLY, 4, 4.2, group="body")
        tail = cv.circ(cx - rx - 0.4, cy + 2.0, 1.8)
        cv.add(tail, BODY, 4, 3.5, group="tail", contour=1)
    else:
        tail = cv.circ(cx, cy + ry * 0.55, 2.0)
        cv.add(tail, BODY, 4, 4.4, group="tail", contour=1)
    # sprout on top
    top_y = cy - ry + 0.6
    _sprout(cv, cx + (-0.6 if view == "e" else 0.0), top_y, p.sprout, 5)
    # face
    if view == "s":
        ex0, ex1, ey = int(cx - 4), int(cx + 2), int(cy - 1)
        _eyes(cv, [(ex0, ey), (ex1, ey)], p.eyes)
        cv.grid(["nn"], int(cx) - 1, ey + 3, {"n": NOSE})
        cv.dot(int(cx) - 1, ey + 4, NOSE_D)
        cv.dot(int(cx), ey + 4, NOSE_D)
        cv.dot(ex0 - 1, ey + 3, BLUSH)
        cv.dot(ex1 + 2, ey + 3, BLUSH)
    elif view == "e":
        ex, ey = int(cx + 3), int(cy - 1)
        _eyes(cv, [(ex, ey)], p.eyes)
        cv.dot(int(cx + rx) - 1, ey + 3, NOSE)
        cv.dot(int(cx + rx) - 2, ey + 3, NOSE_D)
        cv.dot(ex + 2, ey + 3, BLUSH)
    return cv.render()


def _eyes(cv, pts, state):
    for (x, y) in pts:
        if state == "open":
            cv.grid(["Wd", "dd", "ee"], x, y, {"W": GLINT, "d": EYE, "e": EYE2})
        elif state == "wide":
            cv.grid(["Wd", "dd", "dd", "ee"], x, y - 1, {"W": GLINT, "d": EYE, "e": EYE2})
        elif state == "closed":
            cv.grid(["..", "dd", ".."], x, y, {"d": EYE2})
        elif state == "happy":
            cv.grid([".d", "d."], x, y + 1, {"d": EYE2})


def animations():
    A = {}

    def put(name, frames, fps, loop=True):
        A[name] = (frames, fps, loop)

    put("idle_s", [draw("s", MPose()), draw("s", MPose(squash=0.6, ear_sway=0.6, sprout=0.6))], 3)
    put("idle_e", [draw("e", MPose()), draw("e", MPose(squash=0.6, ear_sway=0.6, sprout=0.6))], 3)
    hop = [MPose(squash=1.4, ear_sway=0.4), MPose(lift=4, squash=-1.0, ears=0.35, sprout=-0.6, feet_up=1),
           MPose(lift=5, squash=-0.4, ears=0.2, sprout=0.4), MPose(lift=0, squash=1.0, ear_sway=1.0, sprout=0.8)]
    for v in "sne":
        put(f"hop_{v}", [draw(v, q) for q in hop], 10)
    put("alert_s", [draw("s", MPose(ears=1.0, eyes="wide", lift=1, squash=-0.6)),
                    draw("s", MPose(ears=1.0, eyes="wide", lift=0, squash=-0.4, x=0.6, ear_sway=-0.4))], 6)
    put("sleep_s", [draw("s", MPose(squash=1.2, eyes="closed", ear_sway=0.6, sprout=1.4)),
                    draw("s", MPose(squash=1.6, eyes="closed", ear_sway=0.9, sprout=1.8))], 2)
    return A


ORDER = ["idle_s", "idle_e", "hop_s", "hop_n", "hop_e", "alert_s", "sleep_s"]


def build(out_dir: str) -> SheetBuilder:
    A = animations()
    sb = SheetBuilder("mossling", W, H, PIVOT, columns=8, meta={"kind": "kith", "element": "grove",
                                                                "generator": "tools/sprite_forge/mossling.py"})
    for name in ORDER:
        frames, fps, loop = A[name]
        for i, f in enumerate(frames):
            pix.check_frame(f, f"mossling {name}[{i}]")
        sb.add_animation(name, frames, fps, loop)
    sb.save(out_dir)
    return sb


if __name__ == "__main__":
    import preview
    sb = build("/home/user/game/assets/sprites/kith")
    print(preview.strips(sb, scale=6))
