"""Props: the straw training totem (64x96 frames, pivot 32,90, 48 px/unit).

Drawn at 2x like the kith sheets: the rig keeps its 32x48 design coordinates and
is rasterised by kit.Canvas(32, 48, s=2, hd=True) (same world size as the old
32x48 @ 24 px/unit sheet), with straw strands, wood grain, a burlap weave on
the sack head, twisted rope ties and 2x stitching.
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np

import pix
from kit import Canvas, Xf, ell_x, hash01, local_uv, strand_tex, tube_uv, tube_x
from pix import col

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common.sheet import SheetBuilder  # noqa: E402
from portraits import installed_by_art_forge  # noqa: E402

S = 2
DW, DH = 32, 48
W, H = DW * S, DH * S
PIVOT = (16 * S, 45 * S)
PPU = 24 * S
WOOD, STRAW, ROPE, SACK, RED, CREAM = "wood", "sand", "leather", "cloth_cream", "cloth_red", "cloth_cream"
STITCH = col("leather", 1)


def canvas() -> Canvas:
    cv = Canvas(DW, DH, s=S, hd=True)
    cv.fig.floor = PIVOT[1]
    cv.fig.rim_dark = 1
    cv.fig.outline_shadow = 1
    cv.fig.outline_all = True   # 2px all round = the 1x props' 1px outline in world space
    return cv


def P(v: float) -> int:
    return int(math.floor(v * S))


def _weave(U, V, amp=0.1):
    """Burlap: a fine checker of over/under threads."""
    return amp * np.where((np.floor(U / 1.0) + np.floor(V / 1.0)) % 2 == 0, 1.0, -1.0) * \
        (hash01(np.floor(U / 2.0) * 31 + np.floor(V / 2.0) * 17, 4) > 0.35)


def _rope_tex(U, V, amp=0.22):
    """Twisted rope: diagonal strands."""
    return amp * np.where(((U + V) / 2.0) % 2.0 < 1.0, 1.0, -1.0)


def draw_totem(rot: float = 0.0, bits: int = 0):
    cv = canvas()
    xf = Xf(0.0, 0.0, rot, 16.0, 43.0)       # wobble about the base of the post
    Xl, Yl = xf.local(cv)
    # base: a squat wooden block and a little earth mound (not rotated)
    cv.add(cv.ell(16.0, 43.6, 7.4, 1.9), "earth", 3, 0.5, group="mound", contour=1)
    Ub, Vb = local_uv(cv, 16.0, 41.0, 0.0)
    cv.add(cv.rrect(12.6, 39.2, 19.4, 44.4, r=1.0, bevel=1.6), WOOD, 3, 1, group="base", contour=1,
           tex=strand_tex(Vb, Ub, width=1.5, length=5.0, amp=0.16, seed=1))
    # post with wood grain
    post_pts = [(16.0, 40.0), (16.0, 12.0)]
    post = tube_x(cv, xf, post_pts, [1.6, 1.5])
    Su, Rv = tube_uv(cv, xf.pts(post_pts))
    cv.add(post, WOOD, 3, 2, group="post", contour=1, tex=strand_tex(Su, Rv, width=1.2, length=7.0, amp=0.2, seed=2))
    # arms: one wooden beam through the body
    beam_pts = [(6.6, 20.6), (25.4, 20.6)]
    beam = tube_x(cv, xf, beam_pts, [1.7, 1.7])
    Su, Rv = tube_uv(cv, xf.pts(beam_pts))
    cv.add(beam, WOOD, 4, 3, group="beam", contour=1, tex=strand_tex(Su, Rv, width=1.2, length=7.0, amp=0.2, seed=3))
    for ex in (6.6, 25.4):
        cv.add(ell_x(cv, xf, ex, 20.6, 1.9, 2.0), WOOD, 4, 3.1, group="beam", contour=1)
        # end grain rings
        cx_, cy_ = xf.pt(ex + (-0.3 if ex < 16 else 0.3), 20.6)
        cv.grid([".r.", "r.r", ".r."], P(cx_) - 1, P(cy_) - 1, {"r": col(WOOD, 2)})
    # straw body bundle with strands
    body = ell_x(cv, xf, 16.0, 26.4, 7.0, 9.4)
    body = body.clip(Yl > 17.6)
    Us, Vs = local_uv(cv, *xf.pt(16.0, 17.0), rot)
    bp = cv.add(body, STRAW, 3, 4, group="straw", contour=1,
                tex=strand_tex(Vs, Us, width=1.3, length=6.0, amp=0.24, seed=5))
    idx = bp.indices().copy()
    for sx in (11.5, 14.5, 18.5, 21.0):
        streak = (np.abs(Xl - sx - 0.15 * (Yl - 26.0) * (1 if sx > 16 else -1)) < 0.35) & body.mask & (Yl > 19.0) & (Yl < 34.5)
        idx[streak] = np.maximum(idx[streak] - 2, 2)
    bp.idx = idx
    # ragged straw ends poking out at the bottom
    for k, (tx, ty) in enumerate(((10.6, 35.0), (12.0, 36.0), (13.4, 36.6), (15.0, 37.0), (16.6, 36.9), (18.2, 36.5),
                                  (19.8, 36.0), (21.4, 35.0))):
        tip = tube_x(cv, xf, [(tx, ty - 2.6), (tx + (k - 3.5) * 0.25, ty)], [0.8, 0.45])
        cv.add(tip, STRAW, 4 if k % 2 else 3.5, 3.9, group="straw", contour=1)
    # rope ties
    for ry in (19.0, 33.2):
        tie = body.clip(np.abs(Yl - ry) < 0.85)
        Ur, Vr = local_uv(cv, *xf.pt(16.0, ry), rot)
        cv.add(tie, ROPE, 3, 4.2, group="tie", tex=_rope_tex(Ur, Vr))
    # painted target on the chest
    tc = xf.pt(16.0, 26.6)
    rings = [(4.2, RED, 3), (3.0, CREAM, 4), (1.8, RED, 3), (0.8, CREAM, 5)]
    for i, (r, ramp, base) in enumerate(rings):
        disk = cv.ell(tc[0], tc[1], r, r * 0.95).clip(body.mask)
        cv.add(disk, ramp, base, 4.4 + i * 0.05, group="target", light=0.6)
    # burlap sack head with a rope collar and stitched face
    head = ell_x(cv, xf, 16.0, 12.2, 5.0, 4.8)
    Uh, Vh = local_uv(cv, *xf.pt(16.0, 12.2), rot)
    cv.add(head, SACK, 3, 5, group="head", contour=1, tex=_weave(Uh, Vh))
    cv.add(ell_x(cv, xf, 16.0, 7.4, 1.6, 1.4), SACK, 3, 4.9, group="head", contour=1, tex=_weave(Uh, Vh))   # tied top knot
    collar = ell_x(cv, xf, 16.0, 17.0, 3.4, 1.3)
    Uc, Vc = local_uv(cv, *xf.pt(16.0, 17.0), rot)
    cv.add(collar, ROPE, 3, 5.2, group="collar", contour=1, tex=_rope_tex(Uc, Vc))
    for ex in (13.6, 18.4):
        x, y = xf.pt(ex, 11.6)
        cv.grid(["s...s", ".s.s.", "..s..", ".s.s.", "s...s"], P(x) - 2, P(y) - 2, {"s": STITCH})
    mx, my = xf.pt(16.0, 14.8)
    cv.grid(["s.s.s.s.s", ".s.s.s.s."], P(mx) - 4, P(my), {"s": STITCH})
    # straw bits knocked loose
    if bits:
        pts = [(6, 15), (25, 13), (4, 22), (27, 24)] if bits == 1 else [(5, 12), (27, 16), (3, 25)]
        for (x, y) in pts:
            cv.grid(["s..", ".sS", "..S"], P(x), P(y), {"s": col(STRAW, 4), "S": col(STRAW, 3)}, post=True)
    return cv.render()


def build(out_dir: str):
    if installed_by_art_forge(out_dir, "training_totem"):
        print("  props       training_totem       kept (HD sheet from tools/art_forge)")
        return []
    sb = SheetBuilder("training_totem", W, H, PIVOT, columns=8, pixels_per_unit=PPU,
                      meta={"kind": "prop", "generator": "tools/sprite_forge/props.py", "scale": S})
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
    sb = build(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "sprites", "props"))
    print(preview.strips(sb, scale=6))
