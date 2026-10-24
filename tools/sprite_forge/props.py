"""Props: the straw training totem (32x48, pivot 16,45)."""

from __future__ import annotations

import math
import sys

import numpy as np

import pix
from kit import Canvas, Xf, ell_x, tube_x
from pix import col

sys.path.insert(0, "/home/user/game/tools")
from common.sheet import SheetBuilder  # noqa: E402

W, H = 32, 48
PIVOT = (16, 45)
WOOD, STRAW, ROPE, SACK, RED, CREAM = "wood", "sand", "leather", "cloth_cream", "cloth_red", "cloth_cream"


def draw_totem(rot: float = 0.0, bits: int = 0):
    cv = Canvas(W, H)
    xf = Xf(0.0, 0.0, rot, 16.0, 43.0)       # wobble about the base of the post
    Xl, Yl = xf.local_grid(W, H)
    # base: a squat wooden block and a little earth mound (not rotated)
    cv.add(cv.ell(16.0, 43.0, 7.0, 1.9), "earth", 3, 0.5, group="mound", contour=1)
    cv.add(cv.rrect(12.6, 39.2, 19.4, 43.4, r=1.0, bevel=1.6), WOOD, 3, 1, group="base", contour=1)
    # post
    post = tube_x(cv, xf, [(16.0, 40.0), (16.0, 12.0)], [1.6, 1.5])
    cv.add(post, WOOD, 3, 2, group="post", contour=1)
    # arms: one wooden beam through the body
    beam = tube_x(cv, xf, [(6.6, 20.6), (25.4, 20.6)], [1.7, 1.7])
    cv.add(beam, WOOD, 4, 3, group="beam", contour=1)
    for ex in (6.6, 25.4):
        cv.add(ell_x(cv, xf, ex, 20.6, 1.9, 2.0), WOOD, 4, 3.1, group="beam", contour=1)
    # straw body bundle
    body = ell_x(cv, xf, 16.0, 26.4, 7.0, 9.4)
    body = body.clip(Yl > 17.6)
    bp = cv.add(body, STRAW, 3, 4, group="straw", contour=1)
    # straw strands: darker vertical streaks (sparse, not noisy)
    idx = bp.indices().copy()
    for sx in (11.5, 14.5, 18.5, 21.0):
        streak = (np.abs(Xl - sx - 0.15 * (Yl - 26.0) * (1 if sx > 16 else -1)) < 0.5) & body.mask & (Yl > 19.0) & (Yl < 34.5)
        idx[streak] = np.maximum(idx[streak] - 1, 1)
    bp.idx = idx
    # ragged straw ends poking out at the bottom
    for k, (tx, ty) in enumerate(((10.6, 35.0), (13.0, 36.4), (16.0, 36.8), (19.0, 36.4), (21.4, 35.0))):
        tip = tube_x(cv, xf, [(tx, ty - 2.4), (tx + (k - 2) * 0.4, ty)], [0.9, 0.6])
        cv.add(tip, STRAW, 4, 3.9, group="straw", contour=1)
    # rope ties
    for ry in (19.0, 33.2):
        tie = body.clip(np.abs(Yl - ry) < 0.75)
        cv.add(tie, ROPE, 3, 4.2, group="tie")
    # painted target on the chest
    tc = xf.pt(16.0, 26.6)
    rings = [(4.2, RED, 3), (3.0, CREAM, 4), (1.8, RED, 3), (0.8, CREAM, 5)]
    for i, (r, ramp, base) in enumerate(rings):
        disk = cv.ell(tc[0], tc[1], r, r * 0.95).clip(body.mask)
        cv.add(disk, ramp, base, 4.4 + i * 0.05, group="target", light=0.6)
    # burlap sack head with a rope collar and stitched face
    head = ell_x(cv, xf, 16.0, 12.2, 5.0, 4.8)
    cv.add(head, SACK, 3, 5, group="head", contour=1)
    cv.add(ell_x(cv, xf, 16.0, 7.4, 1.6, 1.4), SACK, 3, 4.9, group="head", contour=1)   # tied top knot
    collar = ell_x(cv, xf, 16.0, 17.0, 3.4, 1.3)
    cv.add(collar, ROPE, 3, 5.2, group="collar", contour=1)
    st = col("leather", 1)
    for ex in (13.6, 18.4):
        x, y = xf.pt(ex, 11.6)
        cv.grid(["s.s", ".s.", "s.s"], int(round(x)) - 1, int(round(y)) - 1, {"s": st})
    mx, my = xf.pt(16.0, 14.6)
    cv.grid(["s.s.s"], int(round(mx)) - 2, int(round(my)), {"s": st})
    # straw bits knocked loose
    if bits:
        pts = [(6, 15), (25, 13), (4, 22), (27, 24)] if bits == 1 else [(5, 12), (27, 16), (3, 25)]
        for (x, y) in pts:
            cv.grid(["s.", ".S"], x, y, {"s": col(STRAW, 4), "S": col(STRAW, 3)}, post=True)
    return cv.render()


def build(out_dir: str) -> SheetBuilder:
    sb = SheetBuilder("training_totem", W, H, PIVOT, columns=8, meta={"kind": "prop", "generator": "tools/sprite_forge/props.py"})
    idle = [draw_totem(0.0)]
    hit = [draw_totem(-0.12, bits=1), draw_totem(0.08, bits=2), draw_totem(-0.03)]
    for name, frames, fps, loop in (("idle_s", idle, 1, True), ("hit_s", hit, 12, False)):
        for i, f in enumerate(frames):
            pix.check_frame(f, f"training_totem {name}[{i}]")
        sb.add_animation(name, frames, fps, loop)
    sb.save(out_dir)
    return sb


if __name__ == "__main__":
    import preview
    sb = build("/home/user/game/assets/sprites/props")
    print(preview.strips(sb, scale=6))
