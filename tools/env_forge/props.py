"""Group C - props (single PNGs, pivot bottom-centre) and animated prop sheets.

All props are opaque cut-outs (alpha 0/255) with 1px selective outlines in the darkest
shade of the local material ramp. Light from the upper-left.
"""

from __future__ import annotations

import math
import os

import numpy as np

from foliage import (blade, draw_limb, faceted, finish, grass_tuft_px, heightmap_sprite, roots, shade_blob)
from kit import (C, LIGHT, OUT_ENV, PREVIEW_DIR, RA, SheetBuilder, alpha, bezier, binarize,
                 border_ok, canvas, clear_border, contact_sheet, dilate, ellipse_mask, erode, fbm, grid, grid_preview,
                 lambert, outline, poisson, poly_mask, put, ramp_of, rng_for, save_png, shift, spectral, stroke,
                 to_image)

OUT = os.path.join(OUT_ENV, "props")
L3 = LIGHT


def rect(cv, x0, y0, x1, y1, col):
    cv[max(0, y0):y1, max(0, x0):x1] = col


def vline(cv, x, y0, y1, col):
    cv[y0:y1, x] = col


def hline(cv, y, x0, x1, col):
    cv[y, x0:x1] = col


def wood_board(cv, x0, y0, x1, y1, rng, ramp="wood", base=3, vertical=True, grain=True, bevel=True):
    """Plank with bevels (lit top/left) and grain streaks along its length."""
    R = RA[ramp]
    n = len(R)
    cv[y0:y1, x0:x1] = R[base]
    if grain:
        L = (y1 - y0) if vertical else (x1 - x0)
        lanes = range(x0 + 1, x1 - 1) if vertical else range(y0 + 1, y1 - 1)
        for lane in lanes:
            pos = int(rng.integers(-4, 2))
            while pos < L:
                seg = int(rng.integers(3, 9))
                gap = int(rng.integers(2, 7))
                col = R[max(0, base - 1)] if rng.random() < 0.7 else R[min(n - 1, base + 1)]
                for i in range(seg):
                    p = pos + i
                    if 0 <= p < L:
                        if vertical:
                            cv[y0 + p, lane] = col
                        else:
                            cv[lane, x0 + p] = col
                pos += seg + gap
    if bevel:
        if vertical:
            cv[y0:y1, x0] = R[min(n - 1, base + 1)]
            cv[y0:y1, x1 - 1] = R[max(0, base - 1)]
            cv[y0, x0:x1] = R[min(n - 1, base + 1)]
        else:
            cv[y0, x0:x1] = R[min(n - 1, base + 1)]
            cv[y1 - 1, x0:x1] = R[max(0, base - 1)]


def nail(cv, x, y):
    put(cv, x, y, RA["metal"][1])
    put(cv, x - 1, y - 1, RA["metal"][4])


# --------------------------------------------------------------------------
# single-image props
# --------------------------------------------------------------------------


def lantern_post():
    W, H = 16, 48
    rng = rng_for("lantern_post")
    cv = canvas(W, H)
    # stone footing
    for y in range(43, 47):
        for x in range(4, 12):
            k = 3 if x < 7 else 2
            if y == 43:
                k = 4 if x < 9 else 3
            cv[y, x] = RA["stone"][k]
    # wooden post
    wood_board(cv, 6, 15, 10, 43, rng, base=2)
    cv[15:43, 6] = RA["wood"][3]
    # bracket arms under the lantern
    hline(cv, 15, 4, 12, RA["metal"][2])
    put(cv, 4, 14, RA["metal"][2])
    put(cv, 11, 14, RA["metal"][2])
    # lantern: cap
    cap = [(8, 1), (5, 4), (11, 4)]
    m = poly_mask(W, H, [(7.5, 1), (4.5, 5), (11.5, 5)], ss=4)
    cv[m] = RA["metal"][2]
    cv[m & (grid(W, H)[0] < 8)] = RA["metal"][3]
    put(cv, 7, 1, RA["metal"][4])
    hline(cv, 5, 4, 12, RA["metal"][1])
    # glass box with iron frame
    for y in range(6, 13):
        for x in range(5, 11):
            if x in (5, 10) or y in (6, 12):
                cv[y, x] = RA["metal"][1] if x == 10 or y == 12 else RA["metal"][3]
            elif x == 8:
                cv[y, x] = RA["metal"][2]
            else:
                # warm glass: hottest in the middle
                d = abs(x - 7.2) + abs(y - 9) * 0.7
                cv[y, x] = RA["ember"][6] if d < 1.2 else (RA["gold"][5] if d < 2.4 else RA["gold"][4])
    # flame core
    put(cv, 7, 9, RA["cloth_cream"][5])
    hline(cv, 13, 5, 11, RA["metal"][2])
    hline(cv, 14, 6, 10, RA["metal"][1])
    # warm light spill on the post just below
    for y in range(16, 20):
        put(cv, 7, y, RA["wood"][4])
        put(cv, 8, y, RA["wood"][3])
    return finish(cv)


def signpost():
    W, H = 24, 32
    rng = rng_for("signpost")
    cv = canvas(W, H)
    wood_board(cv, 10, 3, 14, 31, rng, base=2)
    cv[3, 10:14] = RA["wood"][3]
    # board pointing left
    pts = [(2, 9), (5.5, 5), (19, 5), (19, 13), (5.5, 13)]
    m = poly_mask(W, H, pts, ss=4)
    tmp = canvas(W, H)
    wood_board(tmp, 1, 5, 20, 13, rng, base=3, vertical=False)
    cv[m] = tmp[m]
    # board pointing right
    pts2 = [(22, 19), (18.5, 15), (5, 15), (5, 23), (18.5, 23)]
    m2 = poly_mask(W, H, pts2, ss=4)
    tmp2 = canvas(W, H)
    wood_board(tmp2, 4, 15, 23, 23, rng, base=3, vertical=False)
    cv[m2] = tmp2[m2]
    # carved glyph strokes (abstract lettering) and nails
    for (y, xs_) in ((8, [(7, 10), (11, 13), (14, 17)]), (10, [(7, 9), (10, 15)]),
                     (18, [(7, 11), (12, 14), (15, 17)]), (20, [(7, 9), (10, 16)])):
        for (a, b) in xs_:
            hline(cv, y, a, b, RA["wood"][1])
    nail(cv, 12, 6)
    nail(cv, 12, 16)
    # grass at the base
    grass_tuft_px(cv, 9, 30, rng, base=3, size=3, tall=3)
    grass_tuft_px(cv, 15, 30, rng, base=3, size=2, tall=3)
    return finish(cv)


def barrel():
    W, H = 20, 24
    rng = rng_for("barrel")
    cv = canvas(W, H)
    cx = 10
    top, bot = 4, 22
    for y in range(top, bot + 1):
        t = (y - top) / (bot - top)
        half = 7.0 + 1.6 * math.sin(math.pi * t)
        for x in range(W):
            u = (x + 0.5 - cx) / half
            if abs(u) > 1:
                continue
            nz = math.sqrt(1 - u * u)
            sh = -u * 0.7 + nz * 0.55
            k = 1 + min(3, int(max(0.0, sh) * 4.2))
            # stave seams
            st = (u * 3.2 + 3.2) % 1.0
            if st < 0.12 and abs(u) < 0.9:
                k = max(1, k - 1)
            cv[y, x] = RA["wood"][k]
    # iron hoops
    for hy in (6, 12, 19):
        for x in range(W):
            if cv[hy, x, 3]:
                u = (x + 0.5 - cx) / 8.5
                k = 3 if u < -0.2 else (2 if u < 0.4 else 1)
                cv[hy, x] = RA["metal"][k]
                if cv[hy + 1, x, 3]:
                    cv[hy + 1, x] = RA["metal"][max(0, k - 1)]
    # top: lid ellipse
    for y in range(1, 7):
        for x in range(W):
            u = (x + 0.5 - cx) / 7.2
            v = (y + 0.5 - 4.0) / 2.4
            if u * u + v * v <= 1.0:
                k = 4 if (x // 2) % 2 == 0 else 3
                if u * u + v * v > 0.7:
                    k = 2 if v > 0 else 3
                cv[y, x] = RA["wood"][k]
    cv[4, 9:12] = RA["wood"][2]
    return finish(cv)


def crate():
    W, H = 24, 24
    rng = rng_for("crate")
    cv = canvas(W, H)
    x0, x1, y0, y1 = 2, 22, 5, 23
    # top face (slightly visible)
    for y in range(2, 5):
        for x in range(x0 + (4 - y), x1 - (4 - y) + 2 if False else x1):
            cv[y, x] = RA["wood"][4] if (x // 4) % 2 == 0 else RA["wood"][5]
    cv[2, x0 + 1:x1 - 1] = RA["wood"][5]
    # front planks (horizontal)
    for i, (ya, yb) in enumerate(((5, 11), (11, 17), (17, 23))):
        wood_board(cv, x0, ya, x1, yb, rng, base=3, vertical=False)
    # frame posts and diagonal brace
    wood_board(cv, x0, y0, x0 + 3, y1, rng, base=2)
    wood_board(cv, x1 - 3, y0, x1, y1, rng, base=2)
    brace = poly_mask(W, H, [(x0 + 3, y1 - 3), (x0 + 3, y1), (x1 - 3, y0 + 3), (x1 - 3, y0)], ss=4)
    cv[brace] = RA["wood"][2]
    edge = brace & ~shift(brace, 0, -1)
    cv[edge] = RA["wood"][3]
    # metal corners
    for (cx, cy) in ((x0 + 1, y0 + 1), (x1 - 2, y0 + 1), (x0 + 1, y1 - 2), (x1 - 2, y1 - 2)):
        cv[cy - 1:cy + 1, cx - 1:cx + 1] = RA["metal"][2]
        put(cv, cx - 1, cy - 1, RA["metal"][4])
    return finish(cv)


def hay_bale():
    """Rectangular straw bale: lighter top, cut-straw front face, twine bands, loose straws."""
    W, H = 32, 24
    rng = rng_for("hay_bale")
    cv = canvas(W, H)
    x0, x1 = 2, 30
    top0, front0, y1 = 6, 11, 22
    S = RA["sand"]
    M = RA["cloth_mustard"]
    # top face
    for y in range(top0, front0):
        for x in range(x0 + 1, x1 - 1):
            cv[y, x] = S[4] if y < front0 - 1 else S[3]
    # front face base
    for y in range(front0, y1):
        for x in range(x0, x1):
            cv[y, x] = M[3] if y < front0 + 3 else S[2]
    # rounded corners
    for (x, y) in ((x0, front0), (x1 - 1, front0), (x0, y1 - 1), (x1 - 1, y1 - 1), (x0 + 1, top0), (x1 - 2, top0)):
        cv[y, x] = 0
    # straw strokes: along x on top, short vertical-ish ends on the front
    for (px, py) in poisson(W, H, 1.6, rng, wrap=False):
        x, y = int(px), int(py)
        if top0 <= y < front0 - 1 and x0 + 1 < x < x1 - 3:
            col = S[5] if rng.random() < 0.45 else M[3]
            for i in range(int(rng.integers(2, 4))):
                put(cv, x + i, y, col)
        elif front0 + 1 <= y < y1 - 1 and x0 < x < x1 - 1:
            r = rng.random()
            col = S[3] if r < 0.4 else (M[2] if r < 0.75 else S[4])
            put(cv, x, y, col)
            if rng.random() < 0.5:
                put(cv, x + int(rng.choice([-1, 1])), y + 1, col)
    hline(cv, front0, x0 + 1, x1 - 1, S[5])
    cv[front0:y1 - 1, x0] = M[4]
    cv[front0:y1 - 1, x1 - 1] = S[1]
    hline(cv, y1 - 1, x0 + 1, x1 - 1, S[1])
    # twine bands
    for bx in (9, 21):
        for y in range(top0, y1):
            if cv[y, bx, 3]:
                cv[y, bx] = RA["leather"][2] if y < front0 else RA["leather"][1]
                cv[y, bx + 1] = RA["leather"][3] if y < front0 else RA["leather"][2]
    # loose straws
    for (x, y, dx, dy, L) in ((4, 6, -1, -1, 3), (13, 5, 0, -1, 2), (25, 5, 1, -1, 3), (29, 14, 1, 0, 2),
                              (1, 17, -1, 1, 2), (18, 22, 1, 0, 2)):
        for i in range(L):
            put(cv, x + dx * i, y + dy * i, S[4] if i == L - 1 else M[3])
    return finish(cv)


def flower_planter():
    W, H = 32, 20
    rng = rng_for("flower_planter")
    cv = canvas(W, H)
    # box
    wood_board(cv, 2, 11, 30, 19, rng, base=3, vertical=False)
    hline(cv, 11, 2, 30, RA["wood"][4])
    hline(cv, 15, 2, 30, RA["wood"][2])
    cv[11:19, 2] = RA["wood"][3]
    cv[11:19, 29] = RA["wood"][2]
    for (x, y) in ((4, 13), (27, 13), (4, 17), (27, 17)):
        nail(cv, x, y)
    # soil line
    hline(cv, 10, 3, 29, RA["earth"][1])
    # foliage spilling over
    for (x0, tx, ty) in ((5, 2, 9), (7, 5, 5), (10, 12, 4), (13, 10, 7), (16, 18, 3), (19, 17, 6), (22, 25, 4),
                         (24, 27, 8), (27, 30, 10), (8, 6, 12), (25, 28, 13)):
        blade(cv, (x0, 10), (tx, ty), (x0 + (tx - x0) * 0.3, ty + 2), "leaf", 2, 4)
    # flowers
    cols = [("cloth_red", 5, 4), ("gold", 5, 4), ("cloth_cream", 5, 4), ("cloth_plum", 5, 4), ("cloth_red", 5, 4),
            ("gold", 5, 4)]
    for i, (x, y) in enumerate(((6, 5), (11, 3), (15, 6), (19, 3), (24, 5), (28, 8))):
        r, hi, lo = cols[i]
        put(cv, x, y - 1, RA[r][hi])
        put(cv, x - 1, y, RA[r][hi])
        put(cv, x + 1, y, RA[r][lo])
        put(cv, x, y + 1, RA[r][lo])
        put(cv, x, y, RA["gold"][4] if r != "gold" else RA["ember"][4])
    return finish(cv)


def snare_broken():
    """Broken iron jaw trap lying open on the ground (seen from above at an angle): toothed jaw ring
    with a snapped-off section lying aside, spring arms, chain, faint magenta sigil on the pan."""
    W, H = 24, 16
    rng = rng_for("snare_broken")
    cv = canvas(W, H)
    cx, cy, rx, ry = 11.0, 8.5, 8.0, 4.6
    broken = (-0.55, 0.65)  # angle range (radians) of the missing jaw piece

    def on_gap(a):
        a = (a + math.pi) % math.tau - math.pi
        return broken[0] <= a <= broken[1]

    # spring arms to the left (under the ring)
    for x in range(1, 5):
        put(cv, x, 7, RA["metal"][3])
        put(cv, x, 8, RA["metal"][1])
        put(cv, x, 10, RA["metal"][2])
        put(cv, x, 11, RA["metal"][1])
    put(cv, 1, 9, RA["metal"][2])
    # jaw ring (2px thick, teeth pointing inward)
    for i in range(72):
        a = i * math.tau / 72
        if on_gap(a):
            continue
        x = cx + math.cos(a) * rx
        y = cy + math.sin(a) * ry
        lit = math.sin(a) < 0.1
        put(cv, x, y, RA["metal"][4] if lit else RA["metal"][2])
        put(cv, x, y + 1, RA["metal"][2] if lit else RA["metal"][1])
        if i % 6 == 0:
            tx = cx + math.cos(a) * (rx - 1.6)
            ty = cy + math.sin(a) * (ry - 1.3)
            put(cv, tx, ty, RA["metal"][4] if lit else RA["metal"][3])
    # snapped-off jaw piece lying to the right, bent
    for i in range(6):
        x = 19 + i * 0.7
        y = 11 + i * 0.6 - (0.8 if i in (2, 3) else 0)
        put(cv, x, y, RA["metal"][3])
        put(cv, x, y + 1, RA["metal"][1])
        if i % 2 == 0:
            put(cv, x - 1, y, RA["metal"][4])
    # pan with the faint sigil glyph
    xs, ys = grid(W, H)
    pan = ((xs + 0.5 - cx) / 3.2) ** 2 + ((ys + 0.5 - cy - 0.5) / 1.8) ** 2 <= 1.0
    cv[pan] = RA["metal"][2]
    cv[pan & (ys < cy)] = RA["metal"][3]
    for (x, y, k) in ((10, 8, 3), (11, 8, 4), (12, 9, 3), (11, 9, 2), (10, 9, 4)):
        cv[y, x] = RA["sigil"][k]
    # chain links trailing down-left
    for (x, y) in ((5, 13), (7, 13), (9, 14)):
        put(cv, x, y, RA["metal"][3])
        put(cv, x + 1, y, RA["metal"][1])
    return finish(cv)


def well_bucket():
    W, H = 16, 16
    rng = rng_for("well_bucket")
    cv = canvas(W, H)
    cx = 8
    for y in range(6, 15):
        t = (y - 6) / 8
        half = 5.6 - 1.2 * t
        for x in range(W):
            u = (x + 0.5 - cx) / half
            if abs(u) > 1:
                continue
            sh = -u * 0.7 + math.sqrt(1 - u * u) * 0.5
            k = 1 + min(3, int(max(0.0, sh) * 4.2))
            if ((u + 1) * 3) % 1 < 0.15:
                k = max(1, k - 1)
            cv[y, x] = RA["wood"][k]
    for hy in (7, 12):
        for x in range(W):
            if cv[hy, x, 3]:
                cv[hy, x] = RA["metal"][3 if x < cx else 1]
    # water surface
    for x in range(3, 13):
        u = (x + 0.5 - cx) / 5.0
        if abs(u) <= 1:
            cv[5, x] = RA["water"][4] if x < 7 else RA["water"][3]
    put(cv, 5, 5, RA["water"][6])
    hline(cv, 6, 3, 13, RA["wood"][4])
    # rope handle
    for i in range(9):
        a = math.pi * i / 8
        put(cv, cx + math.cos(a) * 5.0, 5 - math.sin(a) * 4.0, RA["sand"][3] if i < 5 else RA["sand"][2])
    return finish(cv)


def door_wood():
    """Front-view arched plank door with iron strap hinges and a ring pull (flat wall decal)."""
    W, H = 24, 36
    rng = rng_for("door_wood")
    cv = canvas(W, H)
    xs, ys = grid(W, H)
    cx = 12
    # frame (dark timber) with arched top
    outer = ((xs + 0.5 - cx) / 11.0) ** 2 + ((ys + 0.5 - 12) / 11.0) ** 2 <= 1.0
    outer |= (np.abs(xs + 0.5 - cx) <= 11.0) & (ys >= 12) & (ys <= 34)
    inner = ((xs + 0.5 - cx) / 8.6) ** 2 + ((ys + 0.5 - 12.5) / 9.0) ** 2 <= 1.0
    inner |= (np.abs(xs + 0.5 - cx) <= 8.6) & (ys >= 12) & (ys <= 33)
    cv[outer] = RA["wood"][1]
    cv[outer & (xs < cx) & ~inner] = RA["wood"][2]
    # planks
    planks = canvas(W, H)
    for i, x0 in enumerate(range(4, 21, 4)):
        wood_board(planks, x0, 2, min(21, x0 + 4), 34, rng, base=3 if i % 2 == 0 else 2)
    cv[inner] = planks[inner]
    # inner shadow under the arch and at the right jamb
    sh = inner & ~shift(inner, 0, 1)
    cv[inner & ~shift(inner, 0, 2) & (ys < 14)] = RA["wood"][1]
    cv[inner & ~shift(inner, -1, 0)] = RA["wood"][1]
    # iron strap hinges (left) extending across
    for hy in (10, 26):
        for x in range(4, 17):
            if inner[hy, x]:
                cv[hy, x] = RA["metal"][3] if x < 10 else RA["metal"][2]
                cv[hy + 1, x] = RA["metal"][1]
        for x in (5, 9, 13):
            put(cv, x, hy, RA["metal"][4])
        cv[hy - 1:hy + 2, 3] = RA["metal"][2]
    # ring pull (right)
    for (dx, dy) in ((0, 0), (1, 1), (0, 2), (-1, 1)):
        put(cv, 17 + dx, 18 + dy, RA["metal"][3] if dx <= 0 else RA["metal"][1])
    put(cv, 17, 17, RA["metal"][2])
    # threshold step
    hline(cv, 34, 1, 23, RA["stone"][3])
    hline(cv, 34, 12, 23, RA["stone"][2])
    return finish(cv)


def window(lit=True):
    W, H = 20, 20
    rng = rng_for("window_lit" if lit else "window_dark")
    cv = canvas(W, H)
    # frame
    rect(cv, 1, 1, 19, 18, RA["wood"][2])
    hline(cv, 1, 1, 19, RA["wood"][3])
    cv[1:18, 1] = RA["wood"][3]
    cv[1:18, 18] = RA["wood"][1]
    # panes
    for (x0, y0) in ((3, 3), (11, 3), (3, 10), (11, 10)):
        for y in range(y0, y0 + 6):
            for x in range(x0, x0 + 6):
                if lit:
                    d = math.hypot(x - 9.5, y - 9.5)
                    k = RA["ember"][6] if d < 3.2 else (RA["gold"][5] if d < 6.0 else RA["gold"][4])
                    cv[y, x] = k
                else:
                    cv[y, x] = RA["night"][2] if (x + y) % 9 else RA["night"][3]
        # inner shadow on the pane's top/left (the frame casts it)
        hline(cv, y0, x0, x0 + 6, RA["gold"][3] if lit else RA["night"][1])
        cv[y0:y0 + 6, x0] = RA["gold"][3] if lit else RA["night"][1]
    if not lit:
        # cool diagonal reflection
        for i in range(4):
            put(cv, 13 + i, 8 - i, RA["night"][4])
            put(cv, 5 + i, 15 - i, RA["night"][4])
    else:
        # curtain hint on the upper-left pane
        for y in range(3, 9):
            put(cv, 3, y, RA["cloth_red"][3])
            put(cv, 4, y, RA["cloth_red"][4] if y < 6 else RA["cloth_red"][3])
    # sill
    rect(cv, 0, 17, 20, 19, RA["wood"][3])
    hline(cv, 17, 0, 20, RA["wood"][4])
    hline(cv, 18, 0, 20, RA["wood"][2])
    return finish(cv)


def standing_stone():
    """Tall weathered standing stone with carved spiral runes, lichen and a grassy base."""
    W, H = 32, 64
    rng = rng_for("standing_stone")
    cv = canvas(W, H)
    xs, ys = grid(W, H)
    # silhouette: tapered slab with a rounded, slightly leaning top
    def half_w(y):
        t = (y - 4) / 58
        return 9.5 + 3.5 * t - 2.2 * (1 - t) ** 6
    mask = np.zeros((H, W), bool)
    for y in range(3, 62):
        hw = half_w(y)
        c = 16 + (1 - (y - 3) / 59) * 1.5
        for x in range(W):
            if abs(x + 0.5 - c) <= hw:
                mask[y, x] = True
    top = ellipse_mask(W, H, 16.8, 10, 9.2, 8)
    mask = (mask & (ys >= 9)) | (top & (ys < 12))
    nz = fbm(W, H, 4, 3, rng)
    mask &= ~((nz > 0.72) & ~erode(mask, 2))
    # height field: rounded slab
    d = np.zeros((H, W))
    m = mask.copy()
    for i in range(6):
        d += m
        m = erode(m, 1)
    hm = d / 6.0 + 0.4 * fbm(W, H, 6, 2, rng)
    faceted(cv, mask, hm * 2.0, rng, ramp="stone", cell=5.5, tilt=0.25, lut=(1, 2, 3, 3, 4),
            thresholds=(0.45, 0.62, 0.78, 0.9))
    # carved spiral runes (incised: dark groove, lit lower-right lip)
    def spiral(cx, cy, r0, turns, n=60):
        pts = []
        for i in range(n):
            t = i / (n - 1)
            a = t * turns * math.tau
            r = 0.6 + r0 * t
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r * 1.05))
        return pts
    grooves = np.zeros((H, W), bool)
    from kit import raster_path
    for (cx, cy, r0, tr) in ((16, 22, 4.6, 2.2), (14, 40, 3.6, 1.8), (19, 50, 2.6, 1.4)):
        for (x, y) in raster_path(spiral(cx, cy, r0, tr)):
            if 0 <= x < W and 0 <= y < H:
                grooves[y, x] = True
    for (y0, y1, x) in ((29, 34, 12), (29, 34, 20)):
        for y in range(y0, y1):
            grooves[y, x] = True
    for x in range(12, 21):
        grooves[31, x] = True
    grooves &= erode(mask, 1)
    lip = shift(grooves, 1, 1) & ~grooves & mask
    cv[lip] = RA["stone"][4]
    cv[grooves] = RA["stone"][0]
    # lichen and moss
    lich = mask & (fbm(W, H, 5, 2, rng) > 0.72) & ~grooves & ~lip
    cv[lich & (rng.random((H, W)) < 0.6)] = RA["moss"][2]
    cv[lich & (rng.random((H, W)) < 0.25)] = RA["moss"][3]
    base = mask & (ys > 55) & (rng.random((H, W)) < 0.35 + (ys - 55) * 0.08)
    cv[base] = RA["moss"][2]
    out = finish(cv)
    for x in (6, 11, 19, 25):
        grass_tuft_px(out, x, 62, rng, base=3, size=3, tall=4)
    return clear_border(out)


# --------------------------------------------------------------------------
# animated prop sheets
# --------------------------------------------------------------------------


def save_sheet(name, fw, fh, pivot, anims, meta=None):
    sb = SheetBuilder(name, fw, fh, pivot, columns=8, meta=meta or {})
    for (an, frames, fps, loop) in anims:
        sb.add_animation(an, [to_image(f) for f in frames], fps=fps, loop=loop)
    png = sb.save(OUT)
    contact_sheet(png, scale=4, out_path=os.path.join(PREVIEW_DIR, "prop_" + name + ".png"))
    return png


def banner(name, ramp, emblem):
    """Cloth standard on a central pole (pivot = pole base at the frame's bottom-centre):
    finial, crossbar, cloth hanging in front of the pole with ripples travelling down."""
    W, H = 16, 48
    frames = []
    for f in range(4):
        cv = canvas(W, H)
        # pole (behind the cloth) and finial
        for y in range(3, 47):
            put(cv, 7, y, RA["wood"][3])
            put(cv, 8, y, RA["wood"][1])
        put(cv, 7, 1, RA["gold"][5])
        put(cv, 8, 1, RA["gold"][3])
        put(cv, 7, 2, RA["gold"][4])
        put(cv, 8, 2, RA["gold"][2])
        # crossbar with gold caps
        for x in range(2, 14):
            put(cv, x, 4, RA["wood"][3])
            put(cv, x, 5, RA["wood"][1])
        put(cv, 1, 4, RA["gold"][4])
        put(cv, 14, 4, RA["gold"][3])
        put(cv, 1, 5, RA["gold"][2])
        put(cv, 14, 5, RA["gold"][2])
        # cloth: ripples travel down; amplitude grows toward the hem
        top, bottom = 6, 37
        ph = f * math.tau / 4
        for y in range(top, bottom + 4):
            t = (y - top) / (bottom - top)
            amp = 0.3 + 1.4 * t
            off = amp * math.sin(y * 0.38 - ph)
            slope = math.cos(y * 0.38 - ph)
            x0 = 2.5 + off * 0.6
            x1 = 13.0 + off
            if y > bottom - 5:  # swallowtail hem
                notch = (y - (bottom - 5)) * 0.9
                for x in range(int(round(x0)), int(round(x1)) + 1):
                    mid = (x0 + x1) / 2
                    if abs(x - mid) < notch or y > bottom + 2:
                        continue
                    put(cv, x, y, RA[ramp][3])
                continue
            for x in range(int(round(x0)), int(round(x1)) + 1):
                u = (x - x0) / max(1.0, (x1 - x0))
                k = 3 + (1 if slope > 0.35 else 0) - (1 if slope < -0.35 else 0)
                if u < 0.12:
                    k += 1
                if u > 0.9:
                    k -= 1
                put(cv, x, y, RA[ramp][int(np.clip(k, 1, 5))])
        # gold trim along the top edge and the hem points
        for x in range(3, 14):
            put(cv, x, 6, RA["gold"][4] if x % 2 else RA["gold"][3])
        # emblem rides the ripple
        ey = 18 + int(round(0.9 * math.sin(18 * 0.38 - ph)))
        ex = 8 + int(round(0.9 * math.sin(18 * 0.38 - ph) * 0.8))
        for (dx, dy, k) in emblem:
            put(cv, ex + dx, ey + dy, RA["gold"][k])
        frames.append(finish(cv))
    return save_sheet(name, W, H, (8, 47), [("wave_s", frames, 6, True)],
                      meta={"kind": "prop", "pivot": "base of the central pole"})


SUN = [(0, -3, 5), (-2, -2, 4), (2, -2, 4), (-3, 0, 4), (3, 0, 3), (-2, 2, 3), (2, 2, 3), (0, 3, 3),
       (0, 0, 5), (-1, 0, 5), (1, 0, 4), (0, -1, 5), (0, 1, 4), (-1, -1, 5), (1, 1, 4), (1, -1, 4), (-1, 1, 4)]
WAVE = [(-3, 1, 4), (-2, 0, 5), (-1, 0, 5), (0, 1, 4), (1, 2, 4), (2, 1, 3), (3, 0, 4),
        (-3, 4, 4), (-2, 3, 5), (-1, 3, 5), (0, 4, 4), (1, 5, 3), (2, 4, 3), (3, 3, 4),
        (0, -3, 5), (-1, -2, 4), (1, -2, 4)]


def campfire_frame(lit, f, rng_seed=0):
    W, H = 32, 32
    rng = rng_for("campfire", rng_seed)
    cv = canvas(W, H)
    cx, cy = 16, 26
    xs, ys = grid(W, H)
    ash = ellipse_mask(W, H, cx, cy, 8, 2.6)
    cv[ash] = RA["soot"][2]
    cv[ash & (ys < cy - 0.5)] = RA["soot"][3]
    stones = []
    for i in range(10):
        a = math.tau * i / 10 + 0.15
        stones.append((cy + math.sin(a) * 3.6, cx + math.cos(a) * 10.0, i))

    def draw_stone(sx, sy, i):
        tmp = canvas(W, H)
        r = 2.6 + 0.6 * ((i * 7) % 3) / 2
        shade_blob(tmp, sx, sy - 0.5, r + 0.3, r * 0.72, "stone", 1, 4, spec=False)
        m = alpha(tmp)
        cv[m] = tmp[m]
        if lit:
            ys_, xs_ = np.nonzero(m & ~shift(m, 0, 1))
            for y, x in zip(ys_, xs_):
                if sy > cy - 1:
                    cv[y, x] = RA["stone_warm"][4]

    for (sy, sx, i) in sorted(stones):
        if sy < cy:
            draw_stone(sx, sy, i)
    # teepee of logs
    logs = [((cx - 7, cy + 1), (cx + 1, cy - 11)), ((cx + 7, cy + 1), (cx - 1, cy - 11)),
            ((cx - 2, cy + 2), (cx + 0.5, cy - 12)), ((cx + 3, cy + 2), (cx - 0.5, cy - 10))]
    for (a, b) in logs:
        draw_limb(cv, [a, b], 3.6, 2.6, rng, name="bark", lo=1, hi=4, grain=False)
    for (a, b) in logs:
        put(cv, b[0], b[1], RA["wood"][4])
    if not lit:
        # charred tips
        for (a, b) in logs:
            put(cv, b[0], b[1] + 1, RA["soot"][1])
    if lit:
        P = 32
        nz = fbm(W, P, 3, 3, rng_for("campfire_noise"), cells_y=4)
        rows = (ys.astype(int) + f * 8) % P
        n = nz[rows, xs.astype(int)]
        base = cy - 0.5
        hgt = 20
        v = (base - (ys + 0.5)) / hgt
        u = (xs + 0.5 - cx) / 7.0
        env = np.sin(np.clip(v * 0.85 + 0.15, 0, 1) * math.pi) ** 0.55 * (1 - np.clip(v, 0, 1)) ** 0.45
        env = env + (n - 0.5) * 0.8 * np.clip(v, 0, 1)
        inside = (np.abs(u) < env) & (v > -0.02) & (v < 1.0 + (n - 0.5) * 0.6)
        heat = 1.05 - np.abs(u) / np.maximum(env, 1e-3) * 0.55 - np.clip(v, 0, 1) * 0.8 + (n - 0.5) * 0.35
        grad = [RA["ember"][2], RA["ember"][3], RA["ember"][4], RA["ember"][5], RA["ember"][6]]
        k = np.clip((heat * len(grad)).astype(int), 0, len(grad) - 1)
        fl = np.array(grad, np.uint8)[k]
        # let the outer logs peek through the flame edges
        cv[inside] = fl[inside]
        for (a, b) in logs[:2]:
            for t in (0.15, 0.3):
                x = a[0] + (b[0] - a[0]) * t
                y = a[1] + (b[1] - a[1]) * t
                put(cv, x, y, RA["bark"][2])
        for (x, y) in ((cx - 4, cy), (cx + 3, cy), (cx, cy + 1)):
            put(cv, x, y, RA["ember"][4])
        for i in range(3):
            sx = cx + int(round(math.sin(f * 1.7 + i * 2.1) * 4))
            sy = int(base - hgt - 1 - ((f * 3 + i * 4) % 6))
            if 1 <= sy < H - 1:
                put(cv, sx, sy, RA["ember"][5] if i % 2 else RA["ember"][6])
    for (sy, sx, i) in sorted(stones):
        if sy >= cy:
            draw_stone(sx, sy, i)
    return finish(cv)


def campfire():
    unlit = [campfire_frame(False, 0)]
    lit = [campfire_frame(True, f) for f in range(4)]
    return save_sheet("campfire", 32, 32, (16, 29), [("unlit_s", unlit, 1, False), ("lit_s", lit, 10, True)],
                      meta={"kind": "prop", "pivot": "ground under the fire ring"})


def brazier_frame(f):
    W, H = 24, 32
    rng = rng_for("brazier", 0)
    cv = canvas(W, H)
    cx = 12
    # tripod legs
    draw_limb(cv, [(12, 18), (5, 30)], 2.2, 1.8, rng, name="metal", lo=1, hi=3, grain=False)
    draw_limb(cv, [(12, 18), (19, 30)], 2.2, 1.8, rng, name="metal", lo=1, hi=3, grain=False)
    draw_limb(cv, [(12, 18), (12, 30)], 2.4, 2.0, rng, name="metal", lo=1, hi=4, grain=False)
    # feet
    for x in (4, 5, 12, 13, 19, 20):
        put(cv, x, 30, RA["metal"][1])
    # ring between legs
    for x in range(8, 17):
        put(cv, x, 24, RA["metal"][2])
    # bowl
    for y in range(13, 20):
        t = (y - 13) / 6
        half = 8.5 - 4.5 * t ** 1.6
        for x in range(W):
            u = (x + 0.5 - cx) / half
            if abs(u) > 1:
                continue
            sh = -u * 0.7 + math.sqrt(1 - u * u) * 0.5
            k = 1 + min(3, int(max(0.0, sh) * 4.3))
            cv[y, x] = RA["metal"][k]
    # rim and rivets
    for x in range(3, 22):
        put(cv, x, 13, RA["metal"][4] if x < 12 else RA["metal"][3])
    for x in (6, 12, 18):
        put(cv, x, 16, RA["gold"][3])
    # coals
    for x in range(5, 20):
        put(cv, x, 12, RA["ember"][2] if x % 3 else RA["ember"][4])
    for x in range(7, 18, 2):
        put(cv, x, 11, RA["ember"][3])
    # flames
    P = 32
    nz = fbm(W, P, 3, 3, rng_for("brazier_noise"), cells_y=4)
    xs, ys = grid(W, H)
    rows = (ys.astype(int) + f * 8) % P
    n = nz[rows, xs.astype(int)]
    base, hgt = 12.0, 11
    v = (base - (ys + 0.5)) / hgt
    u = (xs + 0.5 - cx) / 6.0
    env = np.sin(np.clip(v * 0.85 + 0.15, 0, 1) * math.pi) ** 0.6 * (1 - np.clip(v, 0, 1)) ** 0.4
    env = env + (n - 0.5) * 0.7 * np.clip(v, 0, 1)
    inside = (np.abs(u) < env) & (v > -0.05) & (v < 1.0 + (n - 0.5) * 0.5)
    heat = 1.05 - np.abs(u) / np.maximum(env, 1e-3) * 0.55 - np.clip(v, 0, 1) * 0.8 + (n - 0.5) * 0.35
    grad = [RA["ember"][2], RA["ember"][3], RA["ember"][4], RA["ember"][5], RA["ember"][6]]
    k = np.clip((heat * len(grad)).astype(int), 0, len(grad) - 1)
    fl = np.array(grad, np.uint8)[k]
    cv[inside] = fl[inside]
    for i in range(2):
        sx = cx + int(round(math.sin(f * 1.9 + i * 2.5) * 3))
        sy = int(base - hgt - 1 - ((f * 2 + i * 3) % 4))
        if 1 <= sy:
            put(cv, sx, sy, RA["ember"][5])
    # warm light on the rim
    for x in range(5, 19):
        put(cv, x, 13, RA["gold"][4] if x < 12 else RA["gold"][3])
    return finish(cv)


def brazier():
    lit = [brazier_frame(f) for f in range(4)]
    return save_sheet("brazier", 24, 32, (12, 30), [("lit_s", lit, 10, True)],
                      meta={"kind": "prop", "pivot": "between the tripod feet"})


SINGLES = {
    "lantern_post": lantern_post,
    "signpost": signpost,
    "barrel": barrel,
    "crate": crate,
    "hay_bale": hay_bale,
    "flower_planter": flower_planter,
    "snare_broken": snare_broken,
    "well_bucket": well_bucket,
    "door_wood": door_wood,
    "window_lit": lambda: window(True),
    "window_dark": lambda: window(False),
    "standing_stone": standing_stone,
}

SHEETS = {
    "banner_red": lambda: banner("banner_red", "cloth_red", SUN),
    "banner_blue": lambda: banner("banner_blue", "cloth_blue", WAVE),
    "campfire": campfire,
    "brazier": brazier,
}


def build(only=None, preview_on=True):
    os.makedirs(OUT, exist_ok=True)
    items = []
    singles = dict(SINGLES)
    try:
        import mural
        singles.update(mural.MURALS)
    except ImportError:
        pass
    for name, fn in singles.items():
        if only and name not in only:
            continue
        cv = fn()
        assert border_ok(cv), name
        assert set(np.unique(cv[..., 3])) <= {0, 255}, name
        save_png(cv, os.path.join(OUT, name + ".png"))
        items.append((name, cv))
    for name, fn in SHEETS.items():
        if only and name not in only:
            continue
        fn()
    if preview_on and items:
        grid_preview(items, "props_sel" if only else "props_all", scale=4, cols=6)
    return items


if __name__ == "__main__":
    import sys
    build(sys.argv[1:] or None)
