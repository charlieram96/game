"""HD battle-arena art (48 texels per unit, twice the env_forge density) for
the HD-2D diorama board built by scripts/combat/view/arena_builder.gd.

    python3 tools/env_forge/arena_hd.py              # build everything + previews
    python3 tools/env_forge/arena_hd.py floor yard   # only some assets
    python3 tools/env_forge/arena_hd.py --check      # validate the files on disk

The board is real geometry now (one beveled flagstone per cell, the joints
are gaps between the stones), so the floor atlases hold only the stones'
faces: no grout ring and no baked bevel. Light still comes from the upper
left for the small details (pits, cracks, chips), like the rest of the art.

Floor atlases (arena_hd_floor, arena_hd_yard): 8 x 8 cells of 56 x 56 px,
each a 48 x 48 face plus a 4 px gutter that repeats the face's edge (so
mipmaps never bleed between cells). Rows (see ATLAS_* in arena_builder.gd):

    0-1  tone A faces (16 variants)      2-3  tone B faces (16 variants)
    4    worn faces (A 0-3, B 4-7)       5    specials (see SPECIAL_*)
    6    rim pieces: 0-3 along x (48 x 24, top half), 4-7 along z (24 x 48, left half)
    7    0-1 rim corners (24 x 24, top-left), 2 mortar, 3-7 spare faces

Seamless material textures (triplanar on walls, steps, pillars, stands):
arena_hd_ashlar, arena_hd_dressed, arena_hd_paving, arena_hd_wood,
arena_hd_timber, arena_hd_monolith; the 48-texel sun-crane inlay and scorch
decals (arena_hd_emblem, arena_hd_decals). The cloth banners are painted with
tools/art_forge (briefs arena_banner_*).
Outputs go to assets/environments/textures/; previews to
tools/env_forge/previews/ (gitignored).
"""

from __future__ import annotations

import importlib
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
sys.path.insert(0, HERE)
importlib.import_module("common.palette")

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from kit import RA, _REV, bayer, canvas, fbm, grid, rng_for, voronoi, poisson  # noqa: E402

OUT = os.path.join(ROOT, "assets", "environments", "textures")
PREVIEWS = os.path.join(HERE, "previews")
T = 48  # texels per unit (one cell)
G = 4  # gutter
CELL = T + 2 * G  # atlas cell pitch
COLS = 8
ROWS = 8


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def col(name: str, i: int) -> np.ndarray:
    r = RA[name]
    return r[int(np.clip(i, 0, len(r) - 1))]


def ramp_img(name: str, idx: np.ndarray) -> np.ndarray:
    r = RA[name]
    return r[np.clip(idx, 0, len(r) - 1)]


def save(cv: np.ndarray, name: str) -> str:
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name + ".png")
    Image.fromarray(cv, "RGBA").save(p)
    return p


def preview(cv: np.ndarray, name: str, scale: int = 3) -> str:
    os.makedirs(PREVIEWS, exist_ok=True)
    im = Image.fromarray(cv, "RGBA")
    base = Image.new("RGBA", im.size, (24, 22, 28, 255))
    base.alpha_composite(im)
    base = base.resize((im.width * scale, im.height * scale), Image.NEAREST)
    p = os.path.join(PREVIEWS, name + ".png")
    base.save(p)
    return p


def walk(rng, x, y, ang, steps, wobble=0.5):
    """A meandering 8-connected pixel path (cracks, veins, scratches)."""
    pts = []
    fx, fy = float(x), float(y)
    for _ in range(steps):
        p = (int(round(fx)), int(round(fy)))
        if not pts or pts[-1] != p:
            pts.append(p)
        ang += rng.uniform(-wobble, wobble)
        fx += math.cos(ang)
        fy += math.sin(ang)
    return pts


def blob(w, h, rng, cx, cy, rx, ry, lobes=3):
    xs, ys = grid(w, h)
    ang = np.arctan2(ys + 0.5 - cy, xs + 0.5 - cx)
    wob = 1.0 + 0.22 * np.sin(ang * lobes + rng.uniform(0, 6.3)) + 0.1 * np.sin(ang * (lobes + 2) + rng.uniform(0, 6.3))
    return ((xs + 0.5 - cx) / rx) ** 2 + ((ys + 0.5 - cy) / ry) ** 2 < wob ** 2


def put_cell(atlas: np.ndarray, r: int, c: int, face: np.ndarray, ox: int = 0, oy: int = 0) -> None:
    """Face (h x w) into atlas cell (r, c) at content offset (ox, oy); the gutter repeats its edge."""
    h, w = face.shape[:2]
    x0 = c * CELL + G + ox
    y0 = r * CELL + G + oy
    atlas[y0:y0 + h, x0:x0 + w] = face
    # gutter: replicate edges (and corners) of this face's rectangle
    padded = np.pad(face, ((G, G), (G, G), (0, 0)), mode="edge")
    sub = atlas[y0 - G:y0 + h + G, x0 - G:x0 + w + G]
    mask = np.ones(padded.shape[:2], bool)
    mask[G:G + h, G:G + w] = False
    sub[mask] = padded[mask]


# --------------------------------------------------------------------------
# Ringstones flagstones
# --------------------------------------------------------------------------

# tone -> (ramp, face rung). A: pale cream sandstone, B: greige limestone.
STONE = {
    "a": ("cloth_cream_hd", 6),
    "b": ("stone_warm_hd", 7),
}
SAND = "sand_hd"
MOSS = "moss_hd"


def stone_face(tone: str, seed: int, feature: str = "clean", wear: float = 0.0) -> np.ndarray:
    """One 48 x 48 flagstone face (exactly one cell)."""
    ramp, face = STONE[tone]
    rng = rng_for(f"hd_flag_{tone}_{feature}_{wear:.1f}", seed)
    xs, ys = grid(T, T)
    xi = xs.astype(int)
    yi = ys.astype(int)
    # broad, quiet mottling either side of the face rung (soft dithered edges)
    f = fbm(T, T, 2, 2, rng)
    g = fbm(T, T, 6, 2, rng)
    v = f * 0.62 + g * 0.38
    b = bayer(T, T) * 0.07
    idx = np.full((T, T), face)
    idx[v + b < 0.22] = face - 1
    idx[v + b > 0.81] = face + 1
    if tone == "a" and rng.random() < 0.55:
        # faint bedding planes in some of the sandstone
        band = np.sin((ys * 0.92 + xs * 0.18 + f * 9.0) * 0.3 + rng.uniform(0, 6.3))
        broken = fbm(T, T, 4, 1, rng) > 0.45
        idx[(band > 0.985) & (idx == face) & broken] = face + 1
        idx[(band < -0.99) & (idx == face) & broken] = face - 1
    # weathered edge: the outer 2 texels a step darker, broken up
    edge_d = np.minimum(np.minimum(xi, yi), np.minimum(T - 1 - xi, T - 1 - yi))
    rough = rng.random((T, T))
    idx[(edge_d == 0) & (rough < 0.8)] -= 1
    idx[(edge_d == 1) & (rough < 0.35)] -= 1
    inner = edge_d >= 3
    special: dict[tuple[int, int], np.ndarray] = {}

    def dark(x, y, k=2):
        if 2 <= x < T - 2 and 2 <= y < T - 2:
            idx[y, x] = min(idx[y, x], face - k)

    def lit(x, y, k=1):
        if 2 <= x < T - 2 and 2 <= y < T - 2 and (x, y) not in special:
            idx[y, x] = max(idx[y, x], face + k)

    # grain: sparse dark and light specks, a few warm sand flecks
    grain = rng.random((T, T))
    idx[inner & (grain < 0.012 * (1.0 - 0.6 * wear))] = face - 2
    idx[inner & (grain > 0.992)] = face + 2
    for _ in range(int(rng.integers(3, 8))):
        x, y = int(rng.integers(4, T - 4)), int(rng.integers(4, T - 4))
        special[(x, y)] = col(SAND, int(rng.integers(5, 8)))
    # pits: a dark texel with a lit one below-right
    n_pits = {"pitted": int(rng.integers(5, 10)), "clean": int(rng.integers(1, 4))}.get(feature, int(rng.integers(0, 3)))
    for _ in range(n_pits):
        x, y = int(rng.integers(5, T - 6)), int(rng.integers(5, T - 6))
        dark(x, y, 2)
        if rng.random() < 0.5:
            dark(x + 1, y, 1)
        lit(x + 1, y + 1)
    if feature in ("crack", "crack_chip", "cracked"):
        side = int(rng.integers(4))
        start = [(int(rng.integers(10, 38)), 2), (2, int(rng.integers(10, 38))), (int(rng.integers(10, 38)), T - 3), (T - 3, int(rng.integers(10, 38)))][side]
        ang = [math.pi / 2, 0.0, -math.pi / 2, math.pi][side] + rng.uniform(-0.5, 0.5)
        path = walk(rng, start[0], start[1], ang, int(rng.integers(18, 34)), 0.45)
        for i, (x, y) in enumerate(path):
            dark(x, y, 3)
            if rng.random() < 0.4:
                lit(x + 1, y + 1)
            if i in (len(path) // 3, 2 * len(path) // 3) and rng.random() < 0.8:
                for (bx, by) in walk(rng, x, y, ang + rng.choice([-1.0, 1.0]), int(rng.integers(5, 11)), 0.5)[1:]:
                    dark(bx, by, 2)
        if feature == "cracked":  # a second, finer crack
            path = walk(rng, int(rng.integers(8, 40)), int(rng.integers(8, 40)), rng.uniform(0, math.tau), int(rng.integers(10, 18)), 0.6)
            for (x, y) in path:
                dark(x, y, 2)
    if feature == "hairline":
        path = walk(rng, int(rng.integers(6, 20)), int(rng.integers(6, 42)), rng.uniform(-0.4, 0.4), int(rng.integers(16, 28)), 0.3)
        for (x, y) in path:
            dark(x, y, 1)
    if feature == "veined":  # pale calcite veins
        for _ in range(2):
            path = walk(rng, int(rng.integers(2, 46)), 2, rng.uniform(1.2, 1.9), int(rng.integers(24, 44)), 0.18)
            for (x, y) in path:
                lit(x, y, 2)
                if rng.random() < 0.3:
                    lit(x + 1, y, 1)
    if feature == "patch":
        px, py = int(rng.integers(10, 24)), int(rng.integers(10, 24))
        pw, ph = int(rng.integers(10, 17)), int(rng.integers(8, 13))
        m = (xi >= px) & (xi < px + pw) & (yi >= py) & (yi < py + ph)
        idx[m] = face - 1
        idx[(yi == py + ph) & (xi >= px) & (xi <= px + pw)] = face + 1
        idx[(xi == px + pw) & (yi >= py) & (yi < py + ph)] = face + 1
        idx[(yi == py) & (xi >= px) & (xi < px + pw)] = face - 2
    if feature in ("chip", "crack_chip"):
        corner = int(rng.integers(4))
        cx = 0 if corner in (0, 3) else T - 1
        cy = 0 if corner in (0, 1) else T - 1
        sx = 1 if cx == 0 else -1
        sy = 1 if cy == 0 else -1
        size = int(rng.integers(4, 8))
        for dy in range(size + 1):
            for dx in range(size + 1 - dy):
                x, y = cx + sx * dx, cy + sy * dy
                idx[y, x] = face - 3 + (1 if rng.random() < 0.3 else 0)
        for d in range(size + 2):
            x, y = cx + sx * (size + 1 - d), cy + sy * d
            if 0 <= x < T and 0 <= y < T:
                idx[y, x] = face - 1 if (sx > 0 and sy > 0) else face + 1
    if feature == "fossil":  # a little spiral shell imprint
        cx, cy = rng.uniform(14, 34), rng.uniform(14, 34)
        for k in range(26):
            a = k * 0.55
            r = 0.6 + k * 0.17
            dark(int(cx + math.cos(a) * r), int(cy + math.sin(a) * r), 1 if k > 6 else 2)
    if feature == "lichen":
        for _ in range(int(rng.integers(2, 4))):
            m = blob(T, T, rng, rng.uniform(4, 44), rng.uniform(4, 44), rng.uniform(2.0, 4.5), rng.uniform(1.6, 3.5))
            dots = m & (rng.random((T, T)) < 0.75)
            for (y, x) in zip(*np.nonzero(dots)):
                special[(int(x), int(y))] = col("cloth_mustard", int(rng.integers(3, 6))) if rng.random() < 0.6 else col("moss_hd", int(rng.integers(6, 10)))
    if wear > 0.0:
        # polished, paler centre and short light scuffs from claws and feet
        cr = np.hypot((xs - 23.5) * 1.05, ys - 23.5 + rng.uniform(-3, 3))
        polish = inner & (cr < 11 + 6 * wear) & (fbm(T, T, 3, 2, rng) > 0.32)
        idx[polish & (idx <= face)] = face + 1
        for _ in range(int(rng.integers(3, 6 + int(3 * wear)))):
            path = walk(rng, int(rng.integers(8, 40)), int(rng.integers(8, 40)), rng.uniform(0, math.tau), int(rng.integers(4, 9)), 0.15)
            for (x, y) in path:
                lit(x, y, 2)
    cv = canvas(T, T)
    cv[:] = ramp_img(ramp, idx)
    for (x, y), c in special.items():
        if 0 <= x < T and 0 <= y < T:
            cv[y, x] = c
    return cv


def edge_growth(cv: np.ndarray, rng, kind: str) -> np.ndarray:
    """Moss or blown sand creeping in from one or two edges (cells by walls)."""
    out = cv.copy()
    xs, ys = grid(T, T)
    n = fbm(T, T, 6, 2, rng)
    sides = rng.choice(4, size=int(rng.integers(1, 3)), replace=False)
    for s in sides:
        d = [ys, T - 1 - xs, T - 1 - ys, xs][int(s)]
        reach = 3.0 + n * 7.0
        m = d < reach
        dots = m & (rng.random((T, T)) < np.clip(1.2 - d / reach, 0, 1))
        if kind == "moss":
            out[dots] = col(MOSS, 5)
            out[dots & (n > 0.55)] = col(MOSS, 7)
            out[dots & (rng.random((T, T)) < 0.2)] = col(MOSS, 3)
        else:
            out[dots] = col(SAND, 6)
            out[dots & (n > 0.5)] = col(SAND, 8)
    return out


def plinth_face(tone: str) -> np.ndarray:
    """Cell under a standing stone: a carved socket ring round the monolith's foot."""
    cv = stone_face(tone, 77, "clean")
    ramp, face = STONE[tone]
    xs, ys = grid(T, T)
    r = np.hypot(xs + 0.5 - 24.0, ys + 0.5 - 24.0)
    d = (xs + 0.5 - 24.0) + (ys + 0.5 - 24.0)
    groove = (r >= 18.0) & (r < 20.5)
    cv[groove] = col(ramp, face - 3)
    cv[groove & (d > 0)] = col(ramp, face - 2)
    lip = (r >= 20.5) & (r < 22.0)
    cv[lip & (d < 0)] = col(ramp, face + 1)
    cv[lip & (d > 0)] = col(ramp, face - 1)
    inner = r < 18.0
    cv[inner] = col(ramp, face - 1)
    cv[inner & (r < 15.0) & (d < -6)] = col(ramp, face)
    # bronze pins at the four diagonals
    for a in (0.25, 0.75, 1.25, 1.75):
        x = int(24 + math.cos(a * math.pi) * 21.2)
        y = int(24 + math.sin(a * math.pi) * 21.2)
        cv[y, x] = col("gold", 4)
        cv[y + 1, x + 1] = col("gold", 1)
    return cv


def mortar_face(seed: int, ramp: str = "sand_hd", base: int = 3) -> np.ndarray:
    rng = rng_for("hd_mortar", seed)
    n = fbm(T, T, 6, 2, rng)
    idx = np.full((T, T), base)
    idx[n > 0.62] = base + 1
    idx[n < 0.3] = base - 1
    cv = canvas(T, T)
    cv[:] = ramp_img(ramp, idx)
    sand = rng.random((T, T)) < 0.05
    cv[sand] = col(SAND, 3)
    return cv


def rim_piece(w: int, h: int, seed: int, along_x: bool, ramp: str = "stone_warm_hd", face: int = 5) -> np.ndarray:
    """A rim slab (w x h texels) with a carved groove along it and bronze studs at its ends."""
    rng = rng_for("hd_rim", seed + (0 if along_x else 50))
    xs, ys = grid(w, h)
    xi = xs.astype(int)
    yi = ys.astype(int)
    f = fbm(w, h, 2, 3, rng)
    b = bayer(w, h) * 0.08
    idx = np.full((h, w), face)
    idx[f + b < 0.28] = face - 1
    idx[f + b > 0.76] = face + 1
    grain = rng.random((h, w))
    idx[grain < 0.015] = face - 2
    idx[grain > 0.99] = face + 2
    edge_d = np.minimum(np.minimum(xi, yi), np.minimum(w - 1 - xi, h - 1 - yi))
    idx[(edge_d == 0) & (grain < 0.85)] -= 1
    L = w if along_x else h
    if along_x:
        g = h // 2
        idx[g - 1, 5:w - 5] = face - 3
        idx[g, 5:w - 5] = face + 1
    else:
        g = w // 2
        idx[5:h - 5, g - 1] = face - 3
        idx[5:h - 5, g] = face + 1
    cv = canvas(w, h)
    cv[:] = ramp_img(ramp, idx)
    # bronze studs a little in from each end, on the groove line
    for t in (2, L - 4):
        x, y = (t, h // 2 - 2) if along_x else (w // 2 - 2, t)
        cv[y:y + 2, x:x + 2] = col("gold", 3)
        cv[y, x] = col("gold", 5)
        cv[y + 1, x + 1] = col("gold", 1)
    return cv


def rim_corner(seed: int, ramp: str = "stone_warm_hd", face: int = 5) -> np.ndarray:
    cv = rim_piece(24, 24, 90 + seed, True, ramp, face)
    # a bronze boss
    xs, ys = grid(24, 24)
    r = np.hypot(xs + 0.5 - 12, ys + 0.5 - 12)
    cv[(r < 6.0)] = col("gold", 2)
    cv[(r < 5.0)] = col("gold", 3)
    cv[(r < 5.0) & ((xs - 12) + (ys - 12) < -2)] = col("gold", 4)
    cv[(r < 2.0)] = col("gold", 5)
    cv[(r >= 6.0) & (r < 7.0)] = col(ramp, face - 3)
    return cv


STONE_FEATURES_A = ["clean", "pitted", "crack", "chip", "hairline", "patch", "crack_chip", "fossil",
                    "clean", "lichen", "clean", "veined", "pitted", "clean", "cracked", "hairline"]
STONE_FEATURES_B = ["clean", "pitted", "veined", "chip", "hairline", "patch", "crack", "clean",
                    "lichen", "clean", "crack_chip", "pitted", "veined", "clean", "cracked", "fossil"]


def floor_atlas() -> np.ndarray:
    atlas = canvas(COLS * CELL, ROWS * CELL, col("stone_warm_hd", 2))
    for i in range(16):
        put_cell(atlas, i // 8, i % 8, stone_face("a", i, STONE_FEATURES_A[i]))
        put_cell(atlas, 2 + i // 8, i % 8, stone_face("b", 20 + i, STONE_FEATURES_B[i]))
    for i in range(8):
        tone = "a" if i < 4 else "b"
        put_cell(atlas, 4, i, stone_face(tone, 100 + i, ["clean", "pitted", "hairline", "clean"][i % 4], 1.0))
    put_cell(atlas, 5, 0, plinth_face("a"))
    put_cell(atlas, 5, 1, plinth_face("b"))
    put_cell(atlas, 5, 2, mortar_face(0))
    for i, (tone, kind) in enumerate((("a", "moss"), ("b", "moss"), ("a", "sand"), ("b", "sand"))):
        put_cell(atlas, 5, 3 + i, edge_growth(stone_face(tone, 200 + i, "clean"), rng_for("hd_edge", i), kind))
    put_cell(atlas, 5, 7, mortar_face(1))
    for i in range(4):
        put_cell(atlas, 6, i, rim_piece(48, 24, i, True))
        put_cell(atlas, 6, 4 + i, rim_piece(24, 48, i, False))
    put_cell(atlas, 7, 0, rim_corner(0))
    put_cell(atlas, 7, 1, rim_corner(1))
    put_cell(atlas, 7, 2, mortar_face(2))
    for i in range(5):
        put_cell(atlas, 7, 3 + i, stone_face("ab"[i % 2], 300 + i, "clean"))
    return atlas


# --------------------------------------------------------------------------
# training yard: packed earth pads framed by timber laths on the grid
# --------------------------------------------------------------------------

EARTH = {"a": ("sand_hd", 5), "b": ("earth_hd", 7)}


def earth_face(tone: str, seed: int, feature: str = "clean", wear: float = 0.0) -> np.ndarray:
    ramp, face = EARTH[tone]
    rng = rng_for(f"hd_earth_{tone}_{feature}_{wear:.1f}", seed)
    xs, ys = grid(T, T)
    xi = xs.astype(int)
    yi = ys.astype(int)
    f = fbm(T, T, 3, 3, rng)
    b = bayer(T, T) * 0.1
    idx = np.full((T, T), face)
    idx[f + b < 0.33] = face - 1
    idx[f + b > 0.72] = face + 1
    grain = rng.random((T, T))
    idx[grain < 0.03] = face - 1
    idx[grain < 0.008] = face - 2
    idx[grain > 0.975] = face + 1
    # the timber laths stand proud of the earth: a soft shadow along the top/left edges
    idx[(yi <= 1) | (xi <= 1)] -= 1
    special: dict[tuple[int, int], np.ndarray] = {}
    if feature in ("pebbles", "clean"):
        for _ in range(int(rng.integers(3, 7)) if feature == "pebbles" else int(rng.integers(0, 3))):
            x, y = int(rng.integers(5, 42)), int(rng.integers(5, 42))
            r = int(rng.integers(1, 3))
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if dx * dx + dy * dy <= r * r:
                        k = 8 if dx + dy < 0 else (6 if dx + dy == 0 else 4)
                        special[(x + dx, y + dy)] = col("stone_warm_hd", k)
            special[(x + r, y + r + 1)] = col(ramp, face - 2)
    if feature == "prints":
        ang = rng.uniform(0, math.tau)
        for j in range(3):
            cx = 24 + math.cos(ang) * (j * 12 - 12) + math.sin(ang) * (4 if j % 2 else -4)
            cy = 24 + math.sin(ang) * (j * 12 - 12) - math.cos(ang) * (4 if j % 2 else -4)
            for (dx, dy) in ((0, 0), (1, 0), (0, 1), (1, 1), (-1, 0), (0, -1), (2, -2), (-2, -2), (0, -3)):
                x, y = int(cx + dx), int(cy + dy)
                if 3 <= x < 45 and 3 <= y < 45:
                    idx[y, x] = face - 1
            x, y = int(cx + 2), int(cy + 2)
            if 3 <= x < 45 and 3 <= y < 45:
                idx[y, x] = face + 1
    if feature == "cracked":
        for _ in range(3):
            for (x, y) in walk(rng, int(rng.integers(8, 40)), int(rng.integers(8, 40)), rng.uniform(0, math.tau), int(rng.integers(8, 16)), 0.9):
                if 3 <= x < 45 and 3 <= y < 45:
                    idx[y, x] = face - 2
    if feature == "tuft":
        for _ in range(int(rng.integers(1, 3))):
            x, y = int(rng.integers(8, 40)), int(rng.integers(10, 40))
            for k in range(int(rng.integers(5, 9))):
                h = int(rng.integers(2, 6))
                dx = int(rng.integers(-3, 4))
                for t in range(h):
                    special[(x + dx + (t // 3) * (1 if dx > 0 else -1), y - t)] = col("leaf", 2 + min(4, t + int(rng.integers(0, 2))))
    if feature == "puddle":
        m = blob(T, T, rng, rng.uniform(16, 32), rng.uniform(16, 32), rng.uniform(6, 10), rng.uniform(4, 7))
        idx[m] = face - 1
        idx[m & (rng.random((T, T)) < 0.2)] = face - 2
    if wear > 0.0 or feature == "scuffs":
        for _ in range(int(rng.integers(4, 9))):
            for (x, y) in walk(rng, int(rng.integers(6, 42)), int(rng.integers(6, 42)), rng.uniform(0, math.tau), int(rng.integers(4, 10)), 0.2):
                if 3 <= x < 45 and 3 <= y < 45:
                    idx[y, x] = face + 1
    cv = canvas(T, T)
    cv[:] = ramp_img(ramp, idx)
    for (x, y), c in special.items():
        if 0 <= x < T and 0 <= y < T:
            cv[y, x] = c
    return cv


def timber_piece(w: int, h: int, seed: int, along_x: bool, tone: int = 6) -> np.ndarray:
    """A heavy timber beam (grain runs along the beam), nail heads near the ends."""
    rng = rng_for("hd_timber", seed + (0 if along_x else 50))
    W = "wood_hd"
    L, A = (w, h) if along_x else (h, w)
    idx = np.full((A, L), tone)
    n = fbm(L, A, 3, 2, rng, cells_y=1)
    idx[n < 0.3] = tone - 1
    idx[n > 0.75] = tone + 1
    for lane in range(1, A - 1):
        pos = int(rng.integers(-8, 4))
        while pos < L:
            seg, gap = int(rng.integers(6, 20)), int(rng.integers(3, 12))
            d = -2 if rng.random() < 0.7 else 1
            idx[lane, max(0, pos):min(L, pos + seg)] = tone + d
            pos += seg + gap
    # a knot or two
    for _ in range(int(rng.integers(0, 2))):
        kx, ky = int(rng.integers(6, L - 6)), int(rng.integers(1, A - 1))
        idx[ky, kx - 1:kx + 2] = tone - 3
        idx[max(0, ky - 1), kx] = tone - 2
    idx[0, :] = tone + 2
    idx[A - 1, :] = tone - 3
    idx[:, 0] = tone - 3
    idx[:, L - 1] = tone - 2
    cv = canvas(L, A)
    cv[:] = ramp_img(W, idx)
    for x in (3, L - 5):
        y = A // 2 - 1
        cv[y:y + 2, x:x + 2] = col("metal", 2)
        cv[y, x] = col("metal", 4)
    if not along_x:
        cv = np.ascontiguousarray(np.transpose(cv, (1, 0, 2)))
    return cv


EARTH_FEATURES = ["clean", "pebbles", "prints", "clean", "cracked", "tuft", "puddle", "scuffs",
                  "clean", "pebbles", "clean", "prints", "cracked", "clean", "tuft", "pebbles"]


def yard_atlas() -> np.ndarray:
    atlas = canvas(COLS * CELL, ROWS * CELL, col("earth_hd", 3))
    for i in range(16):
        put_cell(atlas, i // 8, i % 8, earth_face("a", i, EARTH_FEATURES[i]))
        put_cell(atlas, 2 + i // 8, i % 8, earth_face("b", 20 + i, EARTH_FEATURES[(i + 5) % 16]))
    for i in range(8):
        put_cell(atlas, 4, i, earth_face("ab"[i // 4], 100 + i, ["clean", "prints", "scuffs", "clean"][i % 4], 1.0))
    put_cell(atlas, 5, 0, earth_face("a", 77, "pebbles"))
    put_cell(atlas, 5, 1, earth_face("b", 78, "pebbles"))
    put_cell(atlas, 5, 2, mortar_face(5, "earth_hd", 3))
    for i in range(4):
        base = earth_face("ab"[i % 2], 200 + i, "tuft")
        put_cell(atlas, 5, 3 + i, edge_growth(base, rng_for("hd_yard_edge", i), "moss"))
    put_cell(atlas, 5, 7, mortar_face(6, "earth_hd", 3))
    for i in range(4):
        put_cell(atlas, 6, i, timber_piece(48, 24, i, True))
        put_cell(atlas, 6, 4 + i, timber_piece(24, 48, i, False))
    for i in range(2):
        post = timber_piece(24, 24, 90 + i, True, 5)
        post[10:14, 10:14] = col("metal", 2)
        post[10, 10] = col("metal", 4)
        put_cell(atlas, 7, i, post)
    put_cell(atlas, 7, 2, mortar_face(7, "earth_hd", 3))
    for i in range(5):
        put_cell(atlas, 7, 3 + i, earth_face("ab"[i % 2], 300 + i, "clean"))
    return atlas


# --------------------------------------------------------------------------
# seamless material textures
# --------------------------------------------------------------------------


def ashlar(size: int = 96, seed: int = 0, ramp: str = "stone_warm_hd", face: int = 6, course: int = 24) -> np.ndarray:
    """Dressed ashlar courses (0.5 unit tall), staggered joints, 2 px mortar."""
    rng = rng_for("hd_ashlar", seed)
    w = h = size
    xs, ys = grid(w, h)
    xi = xs.astype(int)
    yi = ys.astype(int)
    idx = np.full((h, w), face)
    block_id = np.zeros((h, w), int)
    joints = np.zeros((h, w), bool)
    bid = 0
    for r in range(h // course):
        y0 = r * course
        x = int(rng.integers(0, 24))
        lengths = []
        total = 0
        while total < w:
            L = int(rng.choice([36, 42, 48, 54, 60]))
            lengths.append(L)
            total += L
        # make the course wrap exactly: stretch the last block
        lengths[-1] -= total - w
        xpos = x
        for L in lengths:
            for dx in range(L):
                xx = (xpos + dx) % w
                block_id[y0:y0 + course, xx] = bid
            joints[y0:y0 + course, xpos % w] = True
            joints[y0:y0 + course, (xpos + 1) % w] = True
            xpos += L
            bid += 1
        joints[y0, :] = True
        joints[(y0 + 1) % h, :] = True
    tone = rng.integers(-1, 2, size=bid + 1)
    f = fbm(w, h, 4, 3, rng)
    b = bayer(w, h) * 0.1
    idx = face + tone[block_id]
    idx[f + b < 0.25] -= 1
    idx[f + b > 0.8] += 1
    grain = rng.random((h, w))
    idx[grain < 0.015] -= 2
    idx[grain > 0.99] += 1
    # per block: lit top edge, shaded bottom edge (upper-left light)
    below_joint = np.roll(joints, 1, axis=0) & ~joints
    above_joint = np.roll(joints, -1, axis=0) & ~joints
    right_of_joint = np.roll(joints, 1, axis=1) & ~joints
    idx[below_joint] += 1
    idx[right_of_joint & ~below_joint] += 1
    idx[above_joint] -= 1
    cv = canvas(w, h)
    cv[:] = ramp_img(ramp, idx)
    m = joints
    cv[m] = col(ramp, 2)
    cv[m & (grain < 0.3)] = col(ramp, 1)
    # chips at some block corners
    for _ in range(10):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h // course)) * course + 2
        for d in range(int(rng.integers(2, 4))):
            cv[(y + d) % h, (x - d) % w] = col(ramp, 3)
    return cv


def dressed(size: int = 96, seed: int = 0, ramp: str = "stone_warm_hd", face: int = 7) -> np.ndarray:
    """Smooth dressed stone (coping, treads, capitals): fine grain, faint slab joints every unit."""
    rng = rng_for("hd_dressed", seed)
    w = h = size
    f = fbm(w, h, 3, 3, rng)
    g = fbm(w, h, 8, 2, rng)
    b = bayer(w, h) * 0.08
    idx = np.full((h, w), face)
    v = f * 0.7 + g * 0.3
    idx[v + b < 0.3] = face - 1
    idx[v + b > 0.76] = face + 1
    grain = rng.random((h, w))
    idx[grain < 0.012] = face - 2
    idx[grain > 0.993] = face + 2
    xs, ys = grid(w, h)
    xi = xs.astype(int)
    joint = (xi % T == 0)
    idx[joint] = face - 3
    idx[(xi % T == 1)] = face + 1
    cv = canvas(w, h)
    cv[:] = ramp_img(ramp, idx)
    return cv


def paving(size: int = 192, seed: int = 0) -> np.ndarray:
    """Irregular worn paving for the lower ring: Voronoi flags with sandy joints."""
    rng = rng_for("hd_paving", seed)
    w = h = size
    pts = poisson(w, h, 30.0, rng, wrap=True)
    ids, d1, d2 = voronoi(w, h, pts, wrap=True)
    edge = (d2 - d1) < 2.2
    tone = rng.integers(-1, 2, size=len(pts))
    ramp = "stone_warm_hd"
    face = 6
    f = fbm(w, h, 6, 3, rng)
    b = bayer(w, h) * 0.1
    idx = face + tone[ids]
    idx[f + b < 0.28] -= 1
    idx[f + b > 0.78] += 1
    grain = rng.random((h, w))
    idx[grain < 0.02] -= 2
    idx[grain > 0.99] += 1
    # lit upper-left lip of each flag, shaded lower-right
    lip = ((d2 - d1) >= 2.2) & ((d2 - d1) < 3.6)
    xs, ys = grid(w, h)
    P = np.asarray(pts)
    cxp = P[ids, 0]
    cyp = P[ids, 1]
    dx = ((xs + 0.5 - cxp + w / 2) % w) - w / 2
    dy = ((ys + 0.5 - cyp + h / 2) % h) - h / 2
    idx[lip & (dx + dy < 0)] += 1
    idx[lip & (dx + dy > 0)] -= 1
    cv = canvas(w, h)
    cv[:] = ramp_img(ramp, idx)
    cv[edge] = col(SAND, 3)
    cv[edge & (grain < 0.4)] = col(SAND, 2)
    cv[edge & (grain > 0.85)] = col("moss_hd", 4)
    return cv


def planks(size: int = 96, seed: int = 0, plank: int = 12, ramp: str = "wood_hd", tone: int = 6) -> np.ndarray:
    """Weathered planks (bench seats and boards), grain along x, 1 px gaps."""
    rng = rng_for("hd_planks", seed)
    w = h = size
    idx = np.full((h, w), tone)
    for r in range(h // plank):
        y0 = r * plank
        t = tone + int(rng.integers(-1, 2))
        idx[y0:y0 + plank, :] = t
        for lane in range(y0 + 1, y0 + plank - 1):
            pos = int(rng.integers(-8, 4))
            while pos < w:
                seg, gap = int(rng.integers(6, 22)), int(rng.integers(3, 12))
                d = -1 if rng.random() < 0.75 else 1
                for i in range(seg):
                    idx[lane, (pos + i) % w] = t + d
                pos += seg + gap
        idx[y0, :] = t + 1
        idx[y0 + plank - 1, :] = t - 2
        # butt joint somewhere along the plank
        jx = int(rng.integers(0, w))
        idx[y0:y0 + plank, jx] = t - 3
        for nx in (jx - 3, jx + 2):
            idx[y0 + plank // 2 - 1, nx % w] = 1
    cv = canvas(w, h)
    cv[:] = ramp_img(ramp, idx)
    return cv


def monolith(size: int = 96, seed: int = 0) -> np.ndarray:
    """Rough weathered standing-stone surface with lichen and faint carved spirals."""
    rng = rng_for("hd_monolith", seed)
    w = h = size
    ramp = "stone_hd"
    face = 6
    f = fbm(w, h, 3, 4, rng)
    g = fbm(w, h, 10, 2, rng)
    b = bayer(w, h) * 0.1
    v = f * 0.65 + g * 0.35
    idx = np.full((h, w), face)
    idx[v + b < 0.25] = face - 2
    idx[(v + b >= 0.25) & (v + b < 0.42)] = face - 1
    idx[v + b > 0.72] = face + 1
    idx[v + b > 0.86] = face + 2
    grain = rng.random((h, w))
    idx[grain < 0.02] -= 2
    cv = canvas(w, h)
    cv[:] = ramp_img(ramp, idx)
    # carved spirals
    for _ in range(2):
        cx, cy = rng.uniform(16, 80), rng.uniform(16, 80)
        for k in range(60):
            a = k * 0.32
            r = 1.0 + k * 0.2
            x, y = int(cx + math.cos(a) * r) % w, int(cy + math.sin(a) * r) % h
            cv[y, x] = col(ramp, face - 3)
            cv[(y + 1) % h, (x + 1) % w] = col(ramp, face + 1)
    # lichen and moss
    for _ in range(6):
        m = blob(w, h, rng, rng.uniform(0, w), rng.uniform(0, h), rng.uniform(3, 7), rng.uniform(2, 5))
        dots = m & (rng.random((h, w)) < 0.7)
        cv[dots] = col("moss_hd", int(rng.integers(5, 9)))
        cv[dots & (rng.random((h, w)) < 0.25)] = col("cloth_mustard", 4)
    return cv


# --------------------------------------------------------------------------
# the sun-crane inlay and scorch decals at 48 texels per unit (same designs as
# arena.py's 24-texel versions, drawn at twice the resolution)
# --------------------------------------------------------------------------

EMB_HD = 240  # texels (5 x 5 units)


def _crane_masks_hd(n: int, c: float, s: float):
    from arena import Pen  # noqa: E402  (env_forge's supersampled pen)

    body = Pen(n, n)
    body.poly([(c, c - 7.5 * s), (c + 3.6 * s, c - 3.0 * s), (c + 3.4 * s, c + 5.0 * s), (c + 1.6 * s, c + 10.5 * s), (c, c + 12.0 * s),
               (c - 1.6 * s, c + 10.5 * s), (c - 3.4 * s, c + 5.0 * s), (c - 3.6 * s, c - 3.0 * s)])
    body.line([(c, c - 6.0 * s), (c, c - 16.5 * s)], 2.4 * s)
    body.ellipse(c, c - 18.5 * s, 2.3 * s, 2.8 * s)
    body.poly([(c - 0.9 * s, c - 20.5 * s), (c + 0.9 * s, c - 20.5 * s), (c, c - 25.5 * s)])
    coverts = Pen(n, n)
    flight = Pen(n, n)
    for sgn in (-1, 1):
        def P(x, y):
            return (c + sgn * x * s, c + y * s)
        coverts.poly([P(2.5, -3.0), P(8.0, -7.0), P(14.0, -9.5), P(19.5, -10.0), P(23.5, -8.5), P(22.0, -5.0),
                      P(16.0, -2.5), P(9.0, -0.5), P(3.0, 1.5)])
        flight.poly([P(3.0, 0.0), P(9.0, -1.5), P(16.0, -3.5), P(22.0, -6.0), P(25.5, -8.0), P(28.5, -6.5),
                     P(28.0, -3.5), P(25.0, 0.5), P(20.0, 4.0), P(13.0, 6.5), P(6.0, 7.0), P(2.5, 5.5)])
        # feather separations on the flight feathers
        for f in range(5):
            flight.line([P(9.0 + f * 3.6, 0.5 - f * 0.9), P(12.0 + f * 3.4, 5.0 - f * 1.6)], 0.35 * s, 0)
    legs = Pen(n, n)
    legs.line([(c - 1.0 * s, c + 10.0 * s), (c - 2.0 * s, c + 23.5 * s)], 1.1 * s)
    legs.line([(c + 1.0 * s, c + 10.0 * s), (c + 2.0 * s, c + 23.5 * s)], 1.1 * s)
    b = body.mask(128)
    cov = coverts.mask(128) & ~b
    fl = flight.mask(128) & ~b & ~cov
    lg = legs.mask(120) & ~b & ~fl
    return b, cov, fl, lg


def emblem_hd() -> np.ndarray:
    n = EMB_HD
    s = n / 120.0
    c = n / 2.0
    xs, ys = grid(n, n)
    dx, dy = xs + 0.5 - c, ys + 0.5 - c
    r = np.hypot(dx, dy)
    ang = np.arctan2(dy, dx)
    cv = canvas(n, n)
    lit_side = (dx + dy) < 0
    G6 = "gold"

    def ring(r0, r1):
        return (r >= r0 * s) & (r < r1 * s)

    def brass_ring(r0, r1):
        m = ring(r0, r1)
        cv[m] = col(G6, 3)
        cv[m & (dx + dy < -0.45 * r)] = col(G6, 4)
        cv[m & (dx + dy > 0.6 * r)] = col(G6, 2)
        cv[m & (r >= (r1 - 0.5) * s) & lit_side] = col(G6, 5)
        return m

    outer = brass_ring(54.5, 56.5)
    groove = ring(51.5, 52.5)
    cv[groove] = col("stone_warm_hd", 4)
    k = 16
    t = (ang / (2 * math.pi) * k) % k
    idx = np.floor(t).astype(int)
    a = t - idx - 0.5
    axis = (idx + 0.5) / k * 2 * math.pi
    long_ray = idx % 2 == 0
    r_in = 35.0 * s
    r_out = np.where(long_ray, 50.5, 44.5) * s
    half_w = 0.46 * (1.0 - (r - r_in) / (r_out - r_in))
    rays = (r >= r_in) & (r < r_out) & (np.abs(a) < half_w)
    side = np.sign(a)
    nx = -np.sin(axis) * side
    ny = np.cos(axis) * side
    lit = (nx * -1 + ny * -1) > 0
    ridge = rays & (np.abs(a) < 0.06)
    cv[rays & lit & long_ray] = col(G6, 3)
    cv[rays & ~lit & long_ray] = col(G6, 2)
    cv[rays & lit & ~long_ray] = col(G6, 2)
    cv[rays & ~lit & ~long_ray] = col(G6, 1)
    cv[ridge & long_ray] = col(G6, 4)
    band = brass_ring(31.5, 33.5)
    disc = r < 31.5 * s
    cv[disc] = col("stone_warm_hd", 6)
    cv[disc & (r > 28.5 * s) & ~lit_side] = col("stone_warm_hd", 4)
    cv[disc & (r > 29.5 * s) & lit_side] = col("stone_warm_hd", 5)
    body, cov, fl, legs = _crane_masks_hd(n, c, s)
    fig = (body | cov | fl) & (r < 30.5 * s)
    cv[fl & fig] = col("cloth_teal", 3)
    cv[fl & fig & (dy > 2.0 * s)] = col("cloth_teal", 2)
    cv[cov & fig] = col("cloth_cream_hd", 8)
    cv[cov & fig & (dy < -6.0 * s)] = col("cloth_cream_hd", 9)
    cv[body & fig] = col("cloth_cream_hd", 9)
    cv[body & fig & (dx > 0.8 * s) & (dy > -5 * s)] = col("cloth_cream_hd", 7)
    cv[legs & disc] = col("stone_warm_hd", 2)
    for (yy, xx, kk) in ((-19, 0, 4), (-20, 0, 3), (-19, 1, 4), (-20, 1, 3)):
        cv[int(c + yy * s), int(c + xx)] = col("cloth_red", kk)
    edge = fig & ~(np.roll(fig, 1, 0) & np.roll(fig, -1, 0) & np.roll(fig, 1, 1) & np.roll(fig, -1, 1))
    edge &= ~((dy < -7.0 * s) & (np.abs(dx) < 3.5 * s))
    cv[edge] = col(G6, 2)
    cv[edge & lit_side & (dy < -4 * s)] = col(G6, 3)
    alpha = outer | groove | rays | band | disc
    cv[..., 3] = np.where(alpha, 255, 0).astype(np.uint8)
    cv[~alpha] = 0
    return cv


def scorch_hd(seed: int) -> np.ndarray:
    """Soot stain at 48 px: a dark heart, a ragged halo and streaks; alpha in quarter steps."""
    rng = rng_for("hd_scorch", seed)
    cv = canvas(T, T)
    xs, ys = grid(T, T)
    cx, cy = 24 + rng.uniform(-3, 3), 24 + rng.uniform(-3, 3)
    ang = np.arctan2(ys + 0.5 - cy, xs + 0.5 - cx)
    r = np.hypot(xs + 0.5 - cx, ys + 0.5 - cy)
    lobes = 1.0 + 0.18 * np.sin(ang * 3 + rng.uniform(0, 6)) + 0.1 * np.sin(ang * 7 + rng.uniform(0, 6))
    rr = r / (rng.uniform(16.0, 20.0) * lobes)
    n = fbm(T, T, 6, 2, rng)
    v = rr + (n - 0.5) * 0.45
    b = bayer(T, T, 4)
    a = np.zeros((T, T))
    a[v + b * 0.2 < 1.0] = 0.25
    a[v + b * 0.15 < 0.75] = 0.5
    a[v + b * 0.1 < 0.45] = 0.75
    for _ in range(int(rng.integers(4, 8))):
        th = rng.uniform(0, math.tau)
        for i in range(int(rng.integers(5, 12))):
            x = int(round(cx + math.cos(th) * (14 + i)))
            y = int(round(cy + math.sin(th) * (14 + i)))
            if 1 <= x < T - 1 and 1 <= y < T - 1 and a[y, x] == 0:
                a[y, x] = 0.25
    S = RA["soot"]
    shade = np.where(a >= 0.75, 1, np.where(a >= 0.5, 2, 3))
    cv[..., :3] = S[shade][..., :3]
    cv[..., 3] = (a * 255).astype(np.uint8)
    return cv


def decals_hd() -> np.ndarray:
    cv = canvas(4 * T, T)
    for i in range(4):
        cv[:, i * T:(i + 1) * T] = scorch_hd(i)
    return cv


# --------------------------------------------------------------------------
# build / check / previews
# --------------------------------------------------------------------------

ASSETS = {
    "floor": ("arena_hd_floor", floor_atlas),
    "yard": ("arena_hd_yard", yard_atlas),
    "ashlar": ("arena_hd_ashlar", lambda: ashlar()),
    "dressed": ("arena_hd_dressed", lambda: dressed()),
    "paving": ("arena_hd_paving", lambda: paving()),
    "wood": ("arena_hd_wood", lambda: planks()),
    "timber": ("arena_hd_timber", lambda: planks(96, 7, 24, "wood_hd", 5)),
    "monolith": ("arena_hd_monolith", lambda: monolith()),
    "emblem": ("arena_hd_emblem", emblem_hd),
    "decals": ("arena_hd_decals", decals_hd),
}
# textures with see-through texels (everything else is opaque)
ALPHA_OK = {"arena_hd_emblem", "arena_hd_decals"}


def board_mockup(atlas: np.ndarray, cols: int = 10, rows: int = 6, seed: int = 3) -> np.ndarray:
    """A patch of board: random faces with 3 px dark joints (what the geometry gives)."""
    rng = np.random.default_rng(seed)
    out = canvas(cols * T, rows * T, (40, 32, 30, 255))
    for r in range(rows):
        for c in range(cols):
            tone_row = 0 if (r + c) % 2 == 0 else 2
            k = int(rng.integers(0, 16))
            ar, ac = tone_row + k // 8, k % 8
            face = atlas[ar * CELL + G:ar * CELL + G + T, ac * CELL + G:ac * CELL + G + T]
            out[r * T + 2:r * T + T - 1, c * T + 2:c * T + T - 1] = face[2:T - 1, 2:T - 1]
    return out


def check(name: str, cv: np.ndarray) -> list[str]:
    problems = []
    vis = cv[..., 3] > 0
    if name not in ALPHA_OK and not vis.all():
        problems.append(f"{name}: transparent texels in an opaque texture")
    a = cv[..., 3]
    if name != "arena_hd_decals" and ((a > 0) & (a < 255)).any():
        problems.append(f"{name}: partial alpha")
    cols_ = cv[vis][:, :3]
    off = sum(1 for c in {tuple(int(v) for v in c) for c in cols_} if c not in _REV)
    if off:
        problems.append(f"{name}: {off} colours off the master palette")
    return problems


def main(argv: list[str]) -> int:
    only = [a for a in argv if not a.startswith("--")]
    if "--check" in argv:
        bad = []
        for key, (name, _fn) in ASSETS.items():
            p = os.path.join(OUT, name + ".png")
            if not os.path.exists(p):
                bad.append(f"{name}: missing")
                continue
            bad += check(name, np.array(Image.open(p).convert("RGBA")))
        for b in bad:
            print(b)
        return 1 if bad else 0
    for key, (name, fn) in ASSETS.items():
        if only and key not in only:
            continue
        cv = fn()
        probs = check(name, cv)
        for p in probs:
            print("WARN", p)
        print(save(cv, name), cv.shape[1], "x", cv.shape[0])
        preview(cv, name)
        if key in ("floor", "yard"):
            preview(board_mockup(cv), name + "_board", 2)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
