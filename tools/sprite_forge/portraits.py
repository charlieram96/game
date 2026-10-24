"""Dialogue portraits (64x64, pivot 32,63): bust shots with larger, more detailed faces.

Same designs as the sprites, drawn with the full ramps: head volume from an
ellipsoid, hand-authored eyes/brows/mouths per expression, hair built from locks.
"""

from __future__ import annotations

import math
import sys

import numpy as np

import pix
from kit import Canvas
from pix import bezier, col

sys.path.insert(0, "/home/user/game/tools")
from common.sheet import SheetBuilder  # noqa: E402

W = H = 64
PIVOT = (32, 63)
BOTTOM = 61.0          # last fill row of the bust (outline lands on row 62)


# ----------------------------------------------------------------------------
# shared face pieces


def head_base(cv, skin, cx=32.0, cy=28.0, z=10, jaw=1.0, ears=True, ear_dy=0.0):
    skull = cv.ell(cx, cy - 1.6, 12.6, 13.4)
    jawm = cv.ell(cx, cy + 6.6, 9.4 * jaw, 8.6)
    cheek = cv.ell(cx, cy + 3.0, 11.6 * jaw, 7.0)
    face = skull | jawm | cheek
    # hand-tuned shading: flat base, soft upper-left highlight, clean shadow crescent on the lower-right contour
    m = face.mask
    idx = np.full(m.shape, 4)
    hl = cv.ell(cx - 4.6, cy - 2.0, 6.4, 5.4).mask
    idx[hl & m] = 5
    inner1 = pix.nb(m, 2, 1, False) & pix.nb(m, 1, 2, False)
    idx[m & ~inner1] = 3
    inner2 = pix.nb(m, 1, 1, False)
    idx[m & ~inner2 & (idx == 3)] = 3
    p = cv.add(face, skin, 4, z, group="face", idx=idx)
    if ears:
        for sgn in (-1, 1):
            e = cv.ell(cx + sgn * 12.2, cy + 2.6 + ear_dy, 2.4, 3.8)
            cv.add(e, skin, 4, z - 0.5, group="ears", contour=1)
            cv.dot(int(cx + sgn * 12.2), int(cy + 2.6 + ear_dy), col(skin, 2))
            cv.dot(int(cx + sgn * 12.2), int(cy + 3.6 + ear_dy), col(skin, 2))
    return p, face


def neck(cv, skin, cx=32.0, top=38.0, bottom=52.0, r=5.2, z=5):
    s = cv.tube([(cx, top), (cx, bottom)], [r, r + 0.6])
    cv.add(s, skin, 3, z, group="neck", contour=1)
    # jaw shadow on the neck
    return s


EYE_SHAPES = {
    # 7 wide x 6 tall, for the LEFT eye; the right eye is mirrored (highlight kept on the lit left side)
    "open": [
        ".LLLLL.",
        "LLIIILL",
        "wIHPIIw",
        "wIPPPIw",
        ".wIIIw.",
        "..lll..",
    ],
    "wide": [
        ".LLLLL.",
        "LwIIIwL",
        "wIHPIIw",
        "wIPPPIw",
        "wwIIIww",
        ".lllll.",
    ],
    "smile": [
        ".......",
        ".LLLLL.",
        "LLIIILL",
        "wIHPIIw",
        ".llllll",
        ".......",
    ],
    "happy": [
        ".......",
        ".......",
        "..LLL..",
        ".L...L.",
        "L.....L",
        ".......",
    ],
    "narrow": [
        ".......",
        ".......",
        "LLLLLLL",
        "wIHPIIw",
        ".wIIIw.",
        "..lll..",
    ],
    "down": [
        ".......",
        ".LLLLL.",
        "LLLLLLL",
        "wwIHIIw",
        ".wIPPw.",
        "..lll..",
    ],
    "closed": [
        ".......",
        ".......",
        ".......",
        "LLLLLLL",
        ".l...l.",
        ".......",
    ],
}


def eyes(cv, shape, cx, ey, sep, iris_ramp, skin, lash, mirror_hl=True):
    rows = EYE_SHAPES[shape]
    pal = {"L": lash, "w": col("cloth_cream", 5), "I": col(iris_ramp, 3), "H": col("cloth_cream", 5),
           "P": col(iris_ramp, 1), "l": col(skin, 3)}
    lx = int(round(cx - sep / 2 - 3.5))
    rx = int(round(cx + sep / 2 - 3.5))
    cv.grid(rows, lx, ey, pal)
    mrows = [r[::-1] for r in rows]
    if mirror_hl:
        # keep the highlight on the lit (left) side of the iris in the mirrored eye
        mrows = [r.replace("IIPHI", "IHPII") for r in mrows]
    cv.grid(mrows, rx, ey, pal)
    # iris depth: darker top row of the iris (lid shadow)
    return lx, rx


def brows(cv, cx, by, sep, color, kind="neutral", w=6):
    """Eyebrows: neutral arcs, raised (worried/sad), angry (lowered toward the centre)."""
    for side in (-1, 1):
        x0 = cx + side * sep / 2
        pts = []
        for i in range(w):
            t = i / (w - 1)
            x = x0 - side * (w / 2) + side * i if side > 0 else x0 + (w / 2) - i
            if kind == "neutral":
                dy = -1 if 1 <= i <= w - 3 else 0
            elif kind == "angry":
                inner = (i if side > 0 else (w - 1 - i))
                dy = -2 + (2 - inner * 0.5)
                dy = int(round((inner - (w - 1)) * -0.45)) - 1
            elif kind == "worried":
                inner = (i if side > 0 else (w - 1 - i))
                dy = int(round((w - 1 - inner) * 0.4)) - 2
            else:
                dy = -1 if 1 <= i <= w - 3 else 0
            pts.append((int(round(x)), int(by + dy)))
        for (x, y) in pts:
            cv.dot(x, y, color)
            if kind != "thin":
                cv.dot(x, y + 1, color) if (x - pts[0][0]) * side in (1, 2) else None


def mouth(cv, cx, my, skin, kind="neutral", lip=None, teeth=True):
    d = col(skin, 1)
    m = col(skin, 2)
    lipc = lip or col("cloth_red", 4)
    x = int(round(cx))
    if kind == "neutral":
        cv.grid([".dddd.", "..mm.."], x - 3, my, {"d": d, "m": m})
    elif kind == "smile":
        cv.grid(["d....d", ".dddd.", "..mm.."], x - 3, my - 1, {"d": d, "m": m})
    elif kind == "grin":
        cv.grid(["dddddddd", "dtttttd.", ".dRRRd..", "..ddd..."], x - 4, my - 1,
                {"d": d, "t": col("cloth_cream", 5), "R": col("cloth_red", 3)})
    elif kind == "open":
        cv.grid([".dddd.", "dRRRRd", ".dRRd.", "..dd.."], x - 3, my - 1, {"d": d, "R": col("cloth_red", 2)})
    elif kind == "flat":
        cv.grid(["dddddd"], x - 3, my, {"d": d})
    elif kind == "frown":
        cv.grid(["..dd..", ".d..d.", "d....d"], x - 3, my, {"d": d})
    elif kind == "pout":
        cv.grid([".ddd..", "d...d.", ".mm..."], x - 2, my, {"d": d, "m": m})
    elif kind == "determined":
        cv.grid(["dddddd", ".m..m."], x - 3, my, {"d": d, "m": m})


def nose(cv, cx, ny, skin):
    cv.dot(int(cx) + 1, ny, col(skin, 3))
    cv.dot(int(cx) + 1, ny + 1, col(skin, 2))
    cv.dot(int(cx), ny + 2, col(skin, 2))
    cv.dot(int(cx) - 1, ny + 2, col(skin, 5))


def blush(cv, cx, by, sep, skin):
    for side in (-1, 1):
        x = int(round(cx + side * (sep / 2 + 1.0)))
        cv.dot(x - 1, by, col("cloth_red", 5))
        cv.dot(x, by, col("cloth_red", 5))
        cv.dot(x + 1, by, col("cloth_red", 5))


def locks(cv, ramp, base, z, items, group="hair", contour=None):
    """Hair locks: list of (pts, radii)."""
    s = cv.empty()
    for pts, radii in items:
        s = s | cv.tube(pts, radii)
    return cv.add(s, ramp, base, z, group=group, contour=contour)


def strands(cv, ramp, items, shade):
    for pts in items:
        for (x, y) in bezier(pts, 12):
            cv.dot(int(math.floor(x)), int(math.floor(y)), col(ramp, shade))


# ----------------------------------------------------------------------------
# PLAYER


def player(expr: str):
    cv = Canvas(W, H)
    skin, hair, cloak, scarf, tunic = "skin_tan", "hair_brown", "cloth_teal", "cloth_red", "cloth_cream"
    # shoulders: teal mantle + cloak, cream tunic V, orange scarf
    sh = cv.poly([(6.0, BOTTOM), (10.0, 50.0), (20.0, 45.6), (44.0, 45.6), (54.0, 50.0), (58.0, BOTTOM)], bevel=3.0)
    cv.add(sh, cloak, 3, 2, group="cloak", contour=1)
    hood = cv.ell(32.0, 47.0, 15.0, 4.6)
    cv.add(hood, cloak, 4, 2.5, group="hood", contour=1)
    tun = cv.poly([(25.0, BOTTOM), (28.0, 50.0), (36.0, 50.0), (39.0, BOTTOM)], bevel=2.0)
    cv.add(tun, tunic, 4, 3, group="tunic", contour=1)
    neck(cv, skin, top=36.0, bottom=50.0, z=4)
    sc = cv.ell(32.0, 49.0, 11.6, 4.4) | cv.tube([(37.0, 50.0), (39.6, 56.0), (38.8, 58.0)], [3.0, 2.8, 2.4])
    cv.add(sc, scarf, 4, 6, group="scarf", contour=1)
    for (a, b) in (((24.0, 48.0), (29.0, 51.4)), ((31.0, 48.4), (36.0, 51.6)), ((38.4, 53.0), (40.4, 57.0))):
        strands(cv, scarf, [[a, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.6), b]], 2)
    # strap + satchel buckle hint
    cv.add(cv.tube([(44.0, 47.0), (37.2, BOTTOM - 1.0)], [1.0, 1.0]), "leather", 3, 6.5, group="strap", contour=1)
    # head
    head_base(cv, skin, z=10)
    # hair: back mass + tousled locks + fringe
    back = cv.ell(32.0, 21.0, 15.4, 12.6)
    cv.add(back.clip(cv.above([(0, 30.0), (64, 30.0)])), hair, 1, 9.5, group="hairback")
    fr = [
        ([(19.0, 22.0), (18.0, 30.0), (19.4, 35.0)], [3.6, 3.0, 1.6]),
        ([(45.0, 22.0), (46.0, 30.0), (44.8, 35.0)], [3.6, 3.0, 1.6]),
        ([(24.0, 12.0), (21.4, 18.0), (21.6, 23.4)], [4.0, 3.4, 1.2]),
        ([(30.0, 11.0), (28.4, 17.0), (27.0, 21.6)], [4.0, 3.2, 1.0]),
        ([(36.0, 11.0), (35.4, 17.0), (34.0, 21.0)], [4.0, 3.0, 1.0]),
        ([(41.0, 13.0), (42.4, 18.0), (41.6, 23.6)], [3.8, 3.2, 1.2]),
        ([(30.0, 13.0), (24.0, 8.4), (21.0, 7.0)], [3.0, 2.0, 1.0]),
        ([(34.0, 12.0), (38.0, 7.0), (41.0, 6.4)], [3.0, 2.0, 1.0]),
        ([(32.0, 13.0), (31.6, 7.6), (33.0, 4.6)], [3.0, 2.2, 1.0]),
        ([(25.0, 16.0), (32.0, 13.6), (40.0, 16.0)], [5.0, 5.4, 5.0]),
    ]
    locks(cv, hair, 2, 12, fr, group="hair", contour=None)
    strands(cv, hair, [[(23.4, 11.6), (21.6, 15.0), (21.8, 19.0)], [(29.0, 10.6), (28.0, 13.6), (27.8, 17.0)]], 4)
    strands(cv, hair, [[(36.0, 12.0), (36.0, 16.0), (35.0, 19.0)], [(40.6, 15.0), (41.6, 18.0), (41.0, 21.0)]], 0)
    _face(cv, expr, skin, iris="earth", lash=col("hair_brown", 0), brow=col(hair, 1), cy=28.0)
    return cv.render()


def _face(cv, expr, skin, iris, lash, brow, cy=28.0, sep=12.0, freckles=False):
    ey = int(cy + 0.0)
    shape = {"neutral": "open", "smile": "smile", "determined": "narrow", "grin": "happy", "sulk": "down",
             "stern": "narrow", "happy": "happy", "scared": "wide"}[expr]
    eyes(cv, shape, 32.0, ey - 2, sep, iris, skin, lash)
    bk = {"neutral": "neutral", "smile": "neutral", "determined": "angry", "grin": "neutral", "sulk": "worried",
          "stern": "angry", "happy": "neutral", "scared": "worried"}[expr]
    brows(cv, 32.0, ey - 4, sep, brow, bk)
    nose(cv, 32.0, ey + 6, skin)
    mk = {"neutral": "neutral", "smile": "smile", "determined": "determined", "grin": "grin", "sulk": "pout",
          "stern": "flat", "happy": "open", "scared": "open"}[expr]
    mouth(cv, 32.0, ey + 10, skin, mk)
    if expr in ("smile", "grin", "happy"):
        blush(cv, 32.0, ey + 6, sep + 2, skin)


# ----------------------------------------------------------------------------
# CORIN


def corin(expr: str):
    cv = Canvas(W, H)
    skin, hair, band, vest, shirt = "skin_deep", "hair_copper", "cloth_red", "cloth_mustard", "stone"
    sh = cv.poly([(6.0, BOTTOM), (9.0, 51.0), (19.0, 46.4), (45.0, 46.4), (55.0, 51.0), (58.0, BOTTOM)], bevel=3.0)
    cv.add(sh, shirt, 2, 2, group="shirt", contour=1, hi=3)
    for sgn in (-1, 1):
        v = cv.poly([(32 + sgn * 6.0, 47.0), (32 + sgn * 15.0, 47.4), (32 + sgn * 22.0, 52.0), (32 + sgn * 24.6, BOTTOM),
                     (32 + sgn * 8.0, BOTTOM)], bevel=2.4)
        cv.add(v, vest, 3, 3, group=f"vest{sgn}", contour=1)
    neck(cv, skin, top=36.0, bottom=50.0, z=4)
    cv.add(cv.ell(32.0, 47.4, 7.4, 2.4), shirt, 2, 4.5, group="collar", contour=1, hi=3)
    head_base(cv, skin, z=10)
    # spiky copper hair: a back mass + big overlapping triangular spikes (each outlined from the next)
    back = cv.ell(32.0, 21.0, 14.6, 11.6)
    cv.add(back.clip(cv.above([(0, 26.0), (64, 26.0)])), hair, 2, 9.5, group="hairback")
    spikes = [  # (base centre, half width, tip, z)
        ((21.0, 21.0), 4.0, (11.6, 17.0), 11.0),
        ((43.0, 21.0), 4.0, (52.6, 16.4), 11.0),
        ((24.0, 17.6), 5.0, (15.0, 7.4), 11.4),
        ((40.4, 17.6), 5.0, (49.6, 7.8), 11.4),
        ((28.0, 15.6), 5.2, (23.0, 2.8), 11.8),
        ((36.4, 15.6), 5.2, (42.4, 3.0), 11.8),
        ((32.0, 15.0), 5.0, (32.6, 1.6), 12.2),
    ]
    for (bx, by), hw, (tx, ty), z in spikes:
        dx, dy = tx - bx, ty - by
        L = math.hypot(dx, dy)
        px, py = -dy / L, dx / L
        pts = [(bx + px * hw, by + py * hw), (tx, ty), (bx - px * hw, by - py * hw), (bx - dx * 0.25, by - dy * 0.25 + 3.0)]
        cv.add(cv.poly(pts, bevel=2.4), hair, 4, z, group=f"spike{z}{bx}", contour=1, contour_col=col(hair, 1))
    cap = cv.ell(32.0, 18.6, 12.4, 6.0)
    cv.add(cap, hair, 4, 12.4, group="cap", contour=None)
    strands(cv, hair, [[(26.0, 13.0), (24.4, 8.0), (23.4, 4.6)], [(31.0, 12.0), (31.6, 6.0), (32.4, 3.0)]], 5)
    # headband across the forehead + knot tails
    bandm = cv.empty()
    bandm = cv.tube([(19.4, 21.6), (32.0, 19.8), (44.6, 21.6)], [1.4, 1.5, 1.4])
    cv.add(bandm, band, 3, 13, group="band", contour=1)
    tails = cv.tube([(44.6, 21.0), (49.6, 24.0), (52.6, 28.4)], [1.6, 1.4, 1.0]) | cv.tube([(44.6, 22.0), (48.0, 27.6), (49.0, 31.6)], [1.4, 1.2, 0.8])
    cv.add(tails, band, 3, 8.5, group="tails", contour=1)
    _face(cv, expr, skin, iris="leaf", lash=col("hair_black", 0), brow=col(hair, 1), cy=28.0)
    return cv.render()


# ----------------------------------------------------------------------------
# HESPER


def hesper(expr: str):
    cv = Canvas(W, H)
    skin, hair, coat, blouse = "skin_light", "hair_grey", "cloth_plum", "cloth_cream"
    sh = cv.poly([(5.0, BOTTOM), (8.0, 51.6), (18.0, 46.6), (46.0, 46.6), (56.0, 51.6), (59.0, BOTTOM)], bevel=3.0)
    cv.add(sh, coat, 3, 2, group="coat", contour=1)
    # high collar flaps
    for sgn in (-1, 1):
        cf = cv.poly([(32 + sgn * 4.0, 44.0), (32 + sgn * 11.0, 45.0), (32 + sgn * 9.0, 52.0), (32 + sgn * 3.0, 55.0)], bevel=2.0)
        cv.add(cf, coat, 4, 4.5, group=f"collar{sgn}", contour=1)
    bl = cv.poly([(27.0, 46.0), (37.0, 46.0), (32.0, 55.0)], bevel=1.6)
    cv.add(bl, blouse, 4, 4, group="blouse", contour=1)
    for by in (57.0, 60.0):
        cv.grid([".g.", "gGg", ".g."], 31, int(by) - 1, {"g": col("gold", 3), "G": col("gold", 5)})
    neck(cv, skin, top=36.0, bottom=48.0, z=3.5, r=4.6)
    head_base(cv, skin, z=10)
    # silver hair pulled back: smooth cap with a centre part, side wings, bun on top
    cap = cv.ell(32.0, 21.4, 14.0, 11.4).clip(cv.above([(0, 24.6), (20, 21.0), (32, 17.6), (44, 21.0), (64, 24.6)]))
    sides = cv.tube([(19.4, 18.0), (18.4, 26.0), (19.6, 31.0)], [3.4, 3.0, 1.8]) | \
        cv.tube([(44.6, 18.0), (45.6, 26.0), (44.4, 31.0)], [3.4, 3.0, 1.8])
    cv.add(cap | sides, hair, 2, 12, group="hair")
    bun = cv.ell(32.0, 8.6, 7.0, 5.4)
    cv.add(bun, hair, 3, 11.5, group="bun", contour=1)
    strands(cv, hair, [[(32.0, 11.0), (31.6, 15.0), (32.0, 18.0)]], 0)
    strands(cv, hair, [[(30.0, 12.0), (24.0, 13.6), (20.6, 18.0)], [(34.0, 12.4), (40.0, 14.0), (43.4, 18.0)]], 4)
    strands(cv, hair, [[(27.0, 5.6), (30.0, 4.4), (34.0, 4.8)], [(26.6, 9.6), (29.0, 12.0), (34.0, 12.4)]], 4)
    _face(cv, expr, skin, iris="water", lash=col("hair_grey", 0), brow=col(hair, 2), cy=28.0)
    # smile lines
    cv.dot(23, 34, col(skin, 3))
    cv.dot(41, 34, col(skin, 3))
    # small round spectacles
    frame = col("gold", 2)
    for ex in (26, 38):
        ring = cv.ell(ex, 26.6, 4.4, 3.8)
        inner = cv.ell(ex, 26.6, 3.4, 2.8)
        rm = ring.mask & ~inner.mask
        ys, xs = np.nonzero(rm)
        for x, y in zip(xs, ys):
            cv.dot(int(x), int(y), frame, post=True)
        cv.dot(ex - 2, 25, col("water", 6), post=True)
        cv.dot(ex - 1, 24, col("water", 6), post=True)
    cv.dots([(30, 26), (31, 25), (32, 25), (33, 26)], frame, post=True)
    return cv.render()


# ----------------------------------------------------------------------------
# EMBERLYN (creature bust)


def emberlyn(expr: str):
    cv = Canvas(W, H)
    FUR, CREAM, SOOT = "fur_russet", "cream", "soot"
    scared = expr == "scared"
    # tail ember peeking over the right shoulder
    from kit import flame
    tail = cv.tube([(46.0, 56.0), (53.0, 44.0), (54.0, 30.0)], [4.0, 4.6, 4.2])
    cv.add(tail, FUR, 3, 1, group="tail", contour=1)
    cv.add(cv.ell(54.0, 27.0, 5.0, 3.2), CREAM, 2, 1.5, group="ring", contour=1)
    if scared:
        flame(cv, 54.0, 24.4, 2.6, 1, tongue=1.5, dim=1, z=1.6, glow_r=8.0)
    else:
        flame(cv, 54.0, 22.0, 4.2, 2, tongue=6.0, z=1.6, glow_r=12.0)
    cv.add(cv.ell(54.0, 28.0, 5.4, 2.4) - cv.ell(54.0, 25.6, 3.6, 1.8), CREAM, 3, 1.7, group="ringf", contour=1)
    # shoulders + chest bib
    body = cv.ell(32.0, 62.0, 22.0, 15.0).clip(cv.above([(0, BOTTOM + 0.5), (64, BOTTOM + 0.5)]))
    cv.add(body, FUR, 3, 2, group="body", contour=1)
    bib = cv.ell(32.0, 60.0, 11.0, 12.0).clip(cv.above([(0, BOTTOM + 0.5), (64, BOTTOM + 0.5)]))
    cv.add(bib, CREAM, 4, 2.2, group="body")
    # ears
    ear_dy = 6.0 if scared else 0.0
    ear_dx = 3.0 if scared else 0.0
    for sgn in (-1, 1):
        e = cv.ell(32 + sgn * (13.0 + ear_dx), 13.0 + ear_dy, 5.6, 5.8 - ear_dy * 0.3, angle=sgn * (0.3 + ear_dy * 0.12))
        cv.add(e, FUR, 3, 4, group=f"ear{sgn}", contour=1)
        ie = cv.ell(32 + sgn * (13.0 + ear_dx), 14.0 + ear_dy, 2.8, 3.2 - ear_dy * 0.2, angle=sgn * 0.3)
        cv.add(ie, FUR, 1, 4.1, group=f"ear{sgn}")
    # head: big rounded head with cheek fluff
    skull = cv.ell(32.0, 30.0, 18.0, 15.0)
    cheeks = cv.ell(32.0, 36.0, 19.6, 9.0)
    tufts = cv.empty()
    for sgn in (-1, 1):
        tufts = tufts | cv.poly([(32 + sgn * 17.0, 33.0), (32 + sgn * 22.0, 38.0), (32 + sgn * 16.0, 42.0)], bevel=1.5)
    head = skull | cheeks | tufts
    mask = cv.pmask([(10.0, 31.0), (16.0, 24.0), (24.0, 22.4), (29.6, 26.6), (34.4, 26.6), (40.0, 22.4), (48.0, 24.0),
                     (54.0, 31.0), (50.0, 36.0), (42.0, 36.6), (35.0, 33.0), (29.0, 33.0), (22.0, 36.6), (14.0, 36.0)])
    cream_m = cv.below([(8.0, 37.0), (20.0, 36.0), (32.0, 35.0), (44.0, 36.0), (56.0, 37.0)])
    cv.add(head.cut(mask | cream_m), FUR, 3, 6, group="head", bands=(0.14, 0.4, -0.2, -0.7))
    cv.add(head.clip(cream_m & ~mask), CREAM, 4, 6.1, group="head")
    cv.add(head.clip(mask), SOOT, 3, 6.2, group="head", lo=1)
    muzzle = cv.ell(32.0, 38.4, 7.4, 5.4)
    cv.add(muzzle, CREAM, 4, 6.3, group="head")
    # eyes: big amber
    A1, A2, A3 = col("ember", 5), col("ember", 4), col("ember", 3)
    P, Wt = col("soot", 0), col("cream", 4)
    if expr == "happy":
        for ex in (23, 41):
            cv.grid(["..ppp..", ".p...p.", "p.....p"], ex - 3, 28, {"p": P})
    else:
        rows = [
            "..YYY..",
            ".YaaaY.",
            "YaWWaaY",
            "aaWPPaa",
            "aaPPPaA",
            ".aaPaA.",
            "..AAA..",
        ] if not scared else [
            "..YYY..",
            ".YaaaY.",
            "YaaaaaY",
            "aaaPaaa",
            "aaaaaaA",
            ".aaaaA.",
            "..AAA..",
        ]
        pal = {"Y": A1, "a": A2, "A": A3, "P": P, "W": Wt}
        cv.grid(rows, 20, 26, pal)
        cv.grid([r[::-1].replace("WWa", "aWW") if False else r for r in rows], 38, 26, pal)
        if scared:
            cv.dot(23, 28, Wt)
            cv.dot(41, 28, Wt)
    # nose + mouth
    cv.grid([".nnnn.", "nNNNNn", ".nnnn."], 29, 35, {"n": col("soot", 1), "N": col("soot", 2)})
    cv.dot(30, 35, col("soot", 3))
    if expr == "happy":
        cv.grid(["m......m", ".mRRRRm.", "..mRRm.."], 28, 39, {"m": col(FUR, 0), "R": col("cloth_red", 4)})
        for bx in (16, 46):
            cv.dots([(bx, 37), (bx + 1, 37), (bx + 2, 37)], col("cloth_red", 5))
    else:
        cv.grid(["..mm..", ".mRRm.", ".mmmm."], 29, 39, {"m": col(FUR, 0), "R": col("cloth_red", 3)})
        # sweat drop
        cv.grid([".w.", "wbw", "wbb", ".w."], 46, 18, {"w": col("water", 6), "b": col("water", 5)}, post=True)
    return cv.render()


# ----------------------------------------------------------------------------
# build


def build(out_dir: str):
    sheets = []
    specs = [
        ("portrait_hesper", hesper, ["neutral", "smile", "stern"]),
        ("portrait_corin", corin, ["grin", "determined", "sulk"]),
        ("portrait_player", player, ["neutral", "smile", "determined"]),
        ("portrait_emberlyn", emberlyn, ["scared", "happy"]),
    ]
    for name, fn, exprs in specs:
        sb = SheetBuilder(name, W, H, PIVOT, columns=4, meta={"kind": "portrait", "generator": "tools/sprite_forge/portraits.py"})
        for e in exprs:
            f = fn(e)
            pix.check_frame(f, f"{name} {e}")
            sb.add_animation(f"{e}_s", [f], 1, False)
        sb.save(out_dir)
        sheets.append(sb)
    return sheets


if __name__ == "__main__":
    import preview
    out = "/home/user/game/assets/sprites/portraits"
    for sb in build(out):
        print(preview.contact(f"{out}/{sb.name}.png", scale=5))
