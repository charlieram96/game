"""Battle-arena art: the floor "chessboard" tile atlases (laid exactly on the
1-unit logical cell grid), the rim slabs, the sun-crane inlay, scorch decals
and the textures for the arena's walls, coping, pillars, standing stones and
cloth banners. Used by scripts/combat/view/arena_builder.gd and
shaders/arena_floor.gdshader.

    python3 tools/env_forge/arena.py              # build everything + previews
    python3 tools/env_forge/arena.py --check      # validate the files on disk
    python3 tools/env_forge/arena.py tiles rim    # only some assets

Conventions (same as the rest of env_forge): 24 texels per unit (one floor
tile = one cell = 24x24 texels), master palette only, light from the upper
left. Each floor tile owns a 1px grout border on all four sides, so two
neighbouring tiles share a 2px grout line centred exactly on the cell
boundary. Outputs go to assets/environments/textures/arena_*.png; previews
to tools/env_forge/previews/ (gitignored).
"""

from __future__ import annotations

import importlib
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)  # outputs go next to this checkout, wherever it lives
sys.path.insert(0, TOOLS)
sys.path.insert(0, HERE)
# Load this checkout's palette before kit does, so kit reuses it.
importlib.import_module("common.palette")

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from kit import RA, _REV, bayer, canvas, fbm, grid, rng_for  # noqa: E402

OUT = os.path.join(ROOT, "assets", "environments", "textures")
PREVIEWS = os.path.join(HERE, "previews")
T = 24  # texels per cell


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------


def col(name: str, i: int) -> np.ndarray:
    r = RA[name]
    return r[int(np.clip(i, 0, len(r) - 1))]


def save(cv: np.ndarray, name: str) -> str:
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name + ".png")
    Image.fromarray(cv, "RGBA").save(p)
    return p


def preview(cv: np.ndarray, name: str, scale: int = 4, bg=(24, 22, 28, 255)) -> str:
    os.makedirs(PREVIEWS, exist_ok=True)
    im = Image.fromarray(cv, "RGBA")
    base = Image.new("RGBA", im.size, bg)
    base.alpha_composite(im)
    base = base.resize((im.width * scale, im.height * scale), Image.NEAREST)
    p = os.path.join(PREVIEWS, name + ".png")
    base.save(p)
    return p


class Pen:
    """Supersampled vector masks for shapes drawn at texel scale."""

    def __init__(self, w: int, h: int, ss: int = 4):
        self.w, self.h, self.ss = w, h, ss
        self.im = Image.new("L", (w * ss, h * ss), 0)
        self.d = ImageDraw.Draw(self.im)

    def poly(self, pts, v=255):
        s = self.ss
        self.d.polygon([(x * s, y * s) for x, y in pts], fill=v)
        return self

    def ellipse(self, cx, cy, rx, ry, v=255):
        s = self.ss
        self.d.ellipse([(cx - rx) * s, (cy - ry) * s, (cx + rx) * s, (cy + ry) * s], fill=v)
        return self

    def line(self, pts, width, v=255):
        s = self.ss
        P = [(x * s, y * s) for x, y in pts]
        self.d.line(P, fill=v, width=max(1, int(round(width * s))), joint="curve")
        r = width * s / 2
        for (x, y) in (P[0], P[-1]):
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=v)
        return self

    def mask(self, thr: int = 128) -> np.ndarray:
        return np.array(self.im.resize((self.w, self.h), Image.BOX)) >= thr


def walk(rng, x, y, ang, steps, wobble=0.55):
    """A meandering 8-connected pixel path (cracks, scratches)."""
    pts = []
    fx, fy = float(x), float(y)
    for _ in range(steps):
        pts.append((int(round(fx)), int(round(fy))))
        ang += rng.uniform(-wobble, wobble)
        fx += math.cos(ang)
        fy += math.sin(ang)
    out = []
    for p in pts:
        if not out or out[-1] != p:
            out.append(p)
    return out


# --------------------------------------------------------------------------
# floor tiles
# --------------------------------------------------------------------------

# Two subtly different warm stones for the chessboard. idx = face rung on `ramp`.
STONE_TONES = {
    # pale cream sandstone
    "a": {"ramp": "cloth_cream", "face": 3, "warm": ("sand", 4), "dim": ("cream", 2), "bright": ("cream", 3)},
    # greige limestone
    "b": {"ramp": "stone_warm", "face": 4, "warm": ("sand", 3), "dim": ("cloth_cream", 2), "bright": ("cloth_cream", 3)},
}
GROUT = ("stone_warm", 2)
GROUT_DEEP = ("stone_warm", 1)


def _blob(rng, cx, cy, rx, ry):
    xs, ys = grid(T, T)
    ang = np.arctan2(ys + 0.5 - cy, xs + 0.5 - cx)
    wob = 1.0 + 0.25 * np.sin(ang * 3 + rng.uniform(0, 6.3)) + 0.12 * np.sin(ang * 5 + rng.uniform(0, 6.3))
    return ((xs + 0.5 - cx) / rx) ** 2 + ((ys + 0.5 - cy) / ry) ** 2 < wob ** 2


def _face_field(rng, wear):
    """Ramp offsets for the face: a soft lit crown toward the upper left (each slab is very
    slightly convex), an occasional mineral stain, sparse grain."""
    off = np.zeros((T, T), int)
    f = fbm(T, T, 2, 2, rng)
    xs, ys = grid(T, T)
    crown = (xs + ys + (f - 0.5) * 9.0) < rng.uniform(13.0, 19.0) + 4.0 * wear
    off[crown] = 1
    if rng.random() < (0.35 if wear < 0.5 else 0.15):
        m = _blob(rng, rng.uniform(7, 17), rng.uniform(7, 17), rng.uniform(2.0, 4.5), rng.uniform(1.6, 3.5))
        off[m] = -1
    grain = rng.random((T, T))
    off[(grain < 0.007 * (1.0 - 0.5 * wear)) & (off == 0)] = -2
    off[(grain > 0.994) & (off == 0)] = 2
    return off, f


def stone_tile(tone: str, seed: int, wear: float = 0.0, feature: str = "clean", grout: str = "plain") -> np.ndarray:
    """One 24x24 flagstone (exactly one logical cell)."""
    spec = STONE_TONES[tone]
    ramp, face = spec["ramp"], spec["face"]
    rng = rng_for(f"arena_tile_{tone}_{feature}_{grout}_{wear:.1f}", seed)
    off, g = _face_field(rng, wear)
    idx = face + off
    xs, ys = grid(T, T)
    xs = xs.astype(int)
    ys = ys.astype(int)
    inner = (xs >= 1) & (xs <= 22) & (ys >= 1) & (ys <= 22)
    special = {}  # (x, y) -> rgba override drawn after the ramp pass

    # bevel: lit top/left lip, shaded bottom/right lip (house light: upper left)
    top = (ys == 1) & inner
    left = (xs == 1) & inner
    bot = (ys == 22) & inner
    right = (xs == 22) & inner
    idx[top | left] = face + 1
    idx[bot | right] = face - 1
    idx[(xs == 1) & (ys == 1)] = face + 2
    idx[(xs == 22) & (ys == 22)] = face - 2
    idx[(xs == 1) & (ys == 22)] = face
    idx[(xs == 22) & (ys == 1)] = face
    if wear > 0.0:
        # worn edges: the lit lip rubs away in places, the face polishes lighter
        rub = (top | left) & (rng.random((T, T)) < 0.35 * wear)
        idx[rub] = face
        cx = np.hypot((xs - 11.5) * 1.1, ys - 11.5 + rng.uniform(-1.5, 1.5))
        polish = inner & ~(top | left | bot | right) & (cx < 4.5 + 2.5 * wear) & (g > 0.35)
        idx[polish & (idx == face)] = face + 1

    # pits: 1px dark with a lit texel below-right (tiny depressions)
    for _ in range(int(rng.integers(1, 4)) if feature in ("pitted", "clean") else int(rng.integers(0, 2))):
        x, y = int(rng.integers(4, 19)), int(rng.integers(4, 19))
        idx[y, x] = face - 2
        idx[y + 1, x + 1] = face + 1

    deep_crack = col(ramp, face - 3) if face - 3 >= 0 else col(*GROUT)
    if feature in ("crack", "crack_chip"):
        # a crack running in from one edge, with a lit lower-right lip in places
        side = int(rng.integers(4))
        start = [(int(rng.integers(5, 18)), 2), (2, int(rng.integers(5, 18))), (int(rng.integers(5, 18)), 21),
                 (21, int(rng.integers(5, 18)))][side]
        ang = [math.pi / 2, 0.0, -math.pi / 2, math.pi][side] + rng.uniform(-0.5, 0.5)
        path = walk(rng, start[0], start[1], ang, int(rng.integers(9, 16)))
        for i, (x, y) in enumerate(path):
            if 2 <= x <= 21 and 2 <= y <= 21:
                special[(x, y)] = deep_crack
                if rng.random() < 0.45 and (x + 1, y + 1) not in special and x + 1 <= 21 and y + 1 <= 21:
                    idx[y + 1, x + 1] = face + 1
            if i == len(path) // 2 and rng.random() < 0.7:  # a short branch
                for (bx, by) in walk(rng, x, y, ang + rng.choice([-1.1, 1.1]), int(rng.integers(3, 6)))[1:]:
                    if 2 <= bx <= 21 and 2 <= by <= 21:
                        special[(bx, by)] = col(ramp, face - 2)
    if feature == "hairline":
        x0 = int(rng.integers(3, 10))
        path = walk(rng, x0, int(rng.integers(3, 20)), rng.uniform(-0.4, 0.4), int(rng.integers(8, 13)), 0.4)
        for (x, y) in path:
            if 2 <= x <= 21 and 2 <= y <= 21:
                special[(x, y)] = col(ramp, face - 1)
    if feature == "patch":
        # a slightly sunken, darker repair patch (lit lower-right rim)
        px, py = int(rng.integers(5, 12)), int(rng.integers(5, 12))
        pw, ph = int(rng.integers(5, 9)), int(rng.integers(4, 7))
        for y in range(py, py + ph):
            for x in range(px, px + pw):
                if 2 <= x <= 21 and 2 <= y <= 21:
                    idx[y, x] = face - 1
        for x in range(px, px + pw):
            if 2 <= x <= 21 and py + ph <= 21:
                idx[py + ph, x] = face + 1
        for y in range(py, py + ph):
            if 2 <= y <= 21 and px + pw <= 21:
                idx[y, px + pw] = face + 1
    if feature in ("chip", "crack_chip"):
        corner = int(rng.integers(4))
        cx = 1 if corner in (0, 2) else 22
        cy = 1 if corner in (0, 1) else 22
        sx = 1 if cx == 1 else -1
        sy = 1 if cy == 1 else -1
        size = int(rng.integers(2, 4))
        for dy in range(size + 1):
            for dx in range(size + 1 - dy):
                special[(cx + sx * dx, cy + sy * dy)] = col(*GROUT)
        # the fresh broken edge faces the light on the top/left corners, away from it otherwise
        lit = (sx > 0 and sy > 0)
        for d in range(size + 1):
            x, y = cx + sx * (size + 1 - d), cy + sy * d
            if 1 <= x <= 22 and 1 <= y <= 22 and (x, y) not in special:
                idx[y, x] = face - 1 if lit else face + 1
    if wear > 0.0:
        # scuffs: short light scratches from claws and feet
        for _ in range(int(rng.integers(1, 3 + int(2 * wear)))):
            path = walk(rng, int(rng.integers(4, 18)), int(rng.integers(4, 18)), rng.uniform(0, math.tau),
                        int(rng.integers(2, 5)), 0.2)
            for (x, y) in path:
                if 2 <= x <= 21 and 2 <= y <= 21 and (x, y) not in special:
                    idx[y, x] = face + 1

    face_px = inner & ~(top | left | bot | right)
    patch_dim = face_px & (off == -1) & (idx == face - 1)
    patch_bright = face_px & (off == 1) & (idx == face + 1)
    idx[face_px & (off == -2) & (idx == face - 2)] = face - 1
    idx[face_px & (off == 2) & (idx == face + 2)] = face + 1
    cv = canvas(T, T)
    R = RA[ramp]
    cv[:] = R[np.clip(idx, 0, len(R) - 1)]
    cv[patch_dim] = col(*spec["dim"])
    cv[patch_bright] = col(*spec["bright"])
    # warm sandy flecks in the face
    wr, wi = spec["warm"]
    fleck = inner & ~(top | left | bot | right) & (rng.random((T, T)) < 0.006) & (off == 0)
    cv[fleck] = col(wr, wi)
    for (x, y), c in special.items():
        cv[y, x] = c

    # grout ring (half of the 2px joint)
    ring = ~inner
    cv[ring] = col(*GROUT)
    gr = rng.random((T, T))
    cv[ring & (gr < 0.18)] = col(*GROUT_DEEP)
    if grout == "sand":
        sandy = ring & (fbm(T, T, 4, 1, rng) > 0.45)
        cv[sandy] = col("sand", 1)
        cv[sandy & (gr > 0.7)] = col("sand", 2)
    elif grout == "moss":
        mossy = ring & (fbm(T, T, 4, 1, rng) > 0.42)
        cv[mossy] = col("moss", 2)
        cv[mossy & (gr < 0.35)] = col("moss", 1)
        cv[mossy & (gr > 0.8)] = col("moss", 3)
        # tufts creeping onto the lip at a corner or two
        for _ in range(int(rng.integers(1, 3))):
            cx, cy = [(1, 1), (22, 1), (1, 22), (22, 22)][int(rng.integers(4))]
            for (dx, dy, k) in ((0, 0, 3), (1 if cx == 1 else -1, 0, 2), (0, 1 if cy == 1 else -1, 4)):
                cv[cy + dy, cx + dx] = col("moss", k)
    return cv


STONE_FEATURES = ["clean", "clean", "pitted", "crack", "chip", "hairline", "patch", "crack_chip"]
WORN_FEATURES = ["clean", "clean", "pitted", "clean", "chip", "hairline", "clean", "crack"]
STONE_COLS = 8
STONE_ROWS = 7  # see stone_atlas()


def stone_atlas() -> np.ndarray:
    """Rows: 0 A plain, 1 B plain, 2 A worn, 3 B worn, 4 A moss/sand grout, 5 B moss/sand grout,
    6 specials: plinth sockets (A, B) for standing-stone cells."""
    cv = canvas(STONE_COLS * T, STONE_ROWS * T)

    def put(r, c, tile):
        cv[r * T:(r + 1) * T, c * T:(c + 1) * T] = tile

    for ti, tone in enumerate("ab"):
        for c in range(STONE_COLS):
            put(ti, c, stone_tile(tone, c, 0.0, STONE_FEATURES[c]))
            put(2 + ti, c, stone_tile(tone, 100 + c, 1.0, WORN_FEATURES[c]))
            grout = "moss" if c < 4 else "sand"
            put(4 + ti, c, stone_tile(tone, 200 + c, 0.0, ["clean", "pitted", "hairline", "chip"][c % 4], grout))
        put(6, ti, plinth_tile(tone))
    for c in range(2, STONE_COLS):
        put(6, c, stone_tile("ab"[c % 2], 300 + c, 0.0, "clean"))
    return cv


def plinth_tile(tone: str) -> np.ndarray:
    """Cell under a standing stone: a carved socket ring around the monolith's base."""
    cv = stone_tile(tone, 77, 0.0, "clean", "moss")
    spec = STONE_TONES[tone]
    ramp, face = spec["ramp"], spec["face"]
    xs, ys = grid(T, T)
    r = np.hypot(xs + 0.5 - 12.0, ys + 0.5 - 12.0)
    groove = (r >= 9.0) & (r < 10.2)
    lit = groove & ((xs + 0.5 - 12.0) + (ys + 0.5 - 12.0) > 0)   # lower-right inner wall catches light
    cv[groove] = col(ramp, face - 2)
    cv[lit] = col(ramp, face - 1)
    lip = (r >= 10.2) & (r < 11.0) & ((xs + 0.5 - 12.0) + (ys + 0.5 - 12.0) < 0)
    cv[lip & (xs >= 2) & (xs <= 21) & (ys >= 2) & (ys <= 21)] = col(ramp, face + 1)
    inner = r < 9.0
    cv[inner] = col(ramp, face - 1)
    cv[inner & (r < 7.5) & ((xs + 0.5 - 12.0) + (ys + 0.5 - 12.0) < -3)] = col(ramp, face)
    return cv


# --------------------------------------------------------------------------
# training-yard tiles: packed earth pads framed by timber laths on the grid
# --------------------------------------------------------------------------

YARD_TONES = {
    "a": {"ramp": "cream", "face": 2},  # pale packed sand
    "b": {"ramp": "sand", "face": 2},   # darker trodden earth
}


def yard_tile(tone: str, seed: int, wear: float = 0.0, feature: str = "clean", grout: str = "plain") -> np.ndarray:
    spec = YARD_TONES[tone]
    ramp, face = spec["ramp"], spec["face"]
    rng = rng_for(f"arena_yard_{tone}_{feature}_{grout}_{wear:.1f}", seed)
    xs, ys = grid(T, T)
    xs = xs.astype(int)
    ys = ys.astype(int)
    idx = np.full((T, T), face)
    for k in range(int(rng.choice([0, 1, 1, 2]))):
        m = _blob(rng, rng.uniform(6, 18), rng.uniform(6, 18), rng.uniform(2.5, 5.0), rng.uniform(2.0, 3.5))
        idx[m] = face - 1 if k == 0 and rng.random() < 0.6 else face + 1
    grain = rng.random((T, T))
    idx[(grain < 0.02) & (idx == face)] = face - 1
    idx[(grain > 0.985) & (idx == face)] = face + 1
    inner = (xs >= 1) & (xs <= 22) & (ys >= 1) & (ys <= 22)
    # the laths stand proud of the earth: shadow along the earth's top/left edge
    idx[inner & ((xs == 1) | (ys == 1))] = face - 1
    idx[(xs == 1) & (ys == 1)] = face - 2
    special = {}
    if feature in ("pebbles", "clean"):
        for _ in range(int(rng.integers(1, 3)) if feature == "pebbles" else int(rng.integers(0, 2)) * int(rng.random() < 0.4)):
            x, y = int(rng.integers(4, 19)), int(rng.integers(4, 19))
            special[(x, y)] = col("stone_warm", 4)
            special[(x + 1, y)] = col("stone_warm", 3)
            special[(x, y + 1)] = col("stone_warm", 2)
    if feature == "prints":
        ang = rng.uniform(0, math.tau)
        for j in range(2):
            cx = 12 + math.cos(ang) * (j * 6 - 3) + math.sin(ang) * (2 if j else -2)
            cy = 12 + math.sin(ang) * (j * 6 - 3) - math.cos(ang) * (2 if j else -2)
            for (dx, dy) in ((0, 0), (1, 0), (0, 1), (1, 1), (0, -1)):
                x, y = int(cx + dx), int(cy + dy)
                if 2 <= x <= 21 and 2 <= y <= 21:
                    idx[y, x] = face - 1
            x, y = int(cx + 2), int(cy + 2)
            if 2 <= x <= 21 and 2 <= y <= 21:
                idx[y, x] = face + 1
    if feature == "cracked":
        for _ in range(2):
            path = walk(rng, int(rng.integers(5, 18)), int(rng.integers(5, 18)), rng.uniform(0, math.tau),
                        int(rng.integers(5, 9)), 0.9)
            for (x, y) in path:
                if 2 <= x <= 21 and 2 <= y <= 21:
                    idx[y, x] = face - 2
    if feature == "tuft":
        x, y = int(rng.integers(5, 18)), int(rng.integers(6, 18))
        for (dx, dy, k) in ((0, 0, 2), (-1, -1, 3), (1, -1, 4), (0, -2, 3), (1, 0, 1), (-1, 0, 2)):
            special[(x + dx, y + dy)] = col("leaf", k)
    if feature == "puddle":
        m = _blob(rng, rng.uniform(8, 16), rng.uniform(8, 16), rng.uniform(3, 5), rng.uniform(2, 3.5))
        idx[m & inner] = face - 1
    if wear > 0.0 or feature == "scuffs":
        for _ in range(int(rng.integers(2, 5))):
            path = walk(rng, int(rng.integers(4, 18)), int(rng.integers(4, 18)), rng.uniform(0, math.tau),
                        int(rng.integers(3, 6)), 0.25)
            for (x, y) in path:
                if 2 <= x <= 21 and 2 <= y <= 21:
                    idx[y, x] = face + 1
    R = RA[ramp]
    cv = canvas(T, T)
    cv[:] = R[np.clip(idx, 0, len(R) - 1)]
    for (x, y), c in special.items():
        if 1 <= x <= 22 and 1 <= y <= 22:
            cv[y, x] = c
    # timber lath halves: top/left = shaded half, bottom/right = lit half (light from the upper left)
    W = RA["wood"]
    cv[0, :] = W[2]
    cv[:, 0] = W[2]
    cv[T - 1, :] = W[4]
    cv[:, T - 1] = W[4]
    cv[T - 1, 0] = W[3]
    cv[0, T - 1] = W[3]
    ring = ~inner
    cv[ring & (grain < 0.12) & (ys == 0)] = W[1]
    cv[ring & (grain < 0.12) & (xs == 0)] = W[1]
    cv[ring & (grain > 0.9) & ((ys == T - 1) | (xs == T - 1))] = W[3]
    for (x, y) in ((0, 0), (T - 1, T - 1), (0, T - 1), (T - 1, 0)):
        cv[y, x] = col("metal", 2)  # nail heads at the crossings
    if grout == "moss":
        g = ring & (fbm(T, T, 4, 1, rng) > 0.55)
        cv[g] = col("moss", 2)
        cv[g & (grain > 0.6)] = col("moss", 3)
        sprout = inner & ((xs <= 2) | (ys <= 2) | (xs >= 21) | (ys >= 21)) & (fbm(T, T, 6, 1, rng) > 0.78)
        cv[sprout] = col("moss", 3)
    elif grout == "sand":
        g = ring & (fbm(T, T, 4, 1, rng) > 0.5)
        cv[g] = col("sand", 3)
        cv[g & (grain > 0.7)] = col("sand", 2)
    return cv


YARD_FEATURES = ["clean", "pebbles", "prints", "clean", "cracked", "tuft", "puddle", "scuffs"]


def yard_atlas() -> np.ndarray:
    cv = canvas(STONE_COLS * T, STONE_ROWS * T)

    def put(r, c, tile):
        cv[r * T:(r + 1) * T, c * T:(c + 1) * T] = tile

    for ti, tone in enumerate("ab"):
        for c in range(STONE_COLS):
            put(ti, c, yard_tile(tone, c, 0.0, YARD_FEATURES[c]))
            put(2 + ti, c, yard_tile(tone, 100 + c, 1.0, ["clean", "prints", "scuffs", "clean"][c % 4]))
            grout = "moss" if c < 4 else "sand"
            put(4 + ti, c, yard_tile(tone, 200 + c, 0.0, ["clean", "tuft", "pebbles", "clean"][c % 4], grout))
        put(6, ti, yard_tile(tone, 77, 0.0, "clean"))
    for c in range(2, STONE_COLS):
        put(6, c, yard_tile("ab"[c % 2], 300 + c, 0.0, "clean"))
    return cv


def yard_beam(w: int, h: int, seed: int, horizontal: bool) -> np.ndarray:
    """A heavy timber beam segment for the yard's rim (grain runs along the beam)."""
    rng = rng_for("arena_yard_rim", seed + (0 if horizontal else 50))
    W = RA["wood"]
    cv = canvas(w, h, W[2])
    xs, ys = grid(w, h)
    xs = xs.astype(int)
    ys = ys.astype(int)
    along = xs if horizontal else ys
    across = ys if horizontal else xs
    n_across = h if horizontal else w
    tone = int(rng.choice([2, 3, 3]))
    cv[:] = W[tone]
    # grain streaks
    for lane in range(1, n_across - 1):
        pos = int(rng.integers(-6, 4))
        L = w if horizontal else h
        while pos < L:
            seg, gap = int(rng.integers(3, 10)), int(rng.integers(2, 8))
            c = W[max(0, tone - 1)] if rng.random() < 0.7 else W[min(5, tone + 1)]
            for i in range(seg):
                p = pos + i
                if 0 <= p < L:
                    if horizontal:
                        cv[lane, p] = c
                    else:
                        cv[p, lane] = c
            pos += seg + gap
    # bevels and the joint at the segment's ends
    cv[(across == 0)] = W[min(5, tone + 1)]
    cv[(across == n_across - 1)] = W[max(0, tone - 2)]
    cv[(along == 0)] = W[0]
    cv[(along == (w if horizontal else h) - 1)] = W[max(0, tone - 1)]
    for (a, b) in ((2, 3), ((w if horizontal else h) - 3, n_across - 4)):
        if horizontal:
            cv[b, a] = col("metal", 3)
            cv[b + 1, a] = col("metal", 1)
        else:
            cv[a, b] = col("metal", 3)
            cv[a, b + 1] = col("metal", 1)
    return cv


def yard_rim_atlas() -> np.ndarray:
    """Same layout as rim_atlas(): horizontal beams, vertical beams, corner posts."""
    cv = canvas(RIM_W, RIM_H, col("wood", 1))
    for i in range(4):
        cv[0:12, i * 24:(i + 1) * 24] = yard_beam(24, 12, i, True)
        cv[12:36, i * 12:(i + 1) * 12] = yard_beam(12, 24, i, False)
    for i in range(2):
        post = yard_beam(12, 12, 90 + i, True)
        post[1:11, 1:11] = col("wood", 3)
        post[1, 1:11] = col("wood", 4)
        post[1:11, 1] = col("wood", 4)
        post[10, 1:11] = col("wood", 1)
        post[1:11, 10] = col("wood", 1)
        post[5:7, 5:7] = col("metal", 2)
        post[5, 5] = col("metal", 4)
        cv[12:24, 48 + i * 12:60 + i * 12] = post
    return cv


# --------------------------------------------------------------------------
# rim slabs (a 0.5-unit border; slab joints line up with the cell grid)
# --------------------------------------------------------------------------

RIM_RAMP, RIM_FACE = "stone_warm", 3


def rim_slab(w: int, h: int, seed: int, horizontal: bool) -> np.ndarray:
    rng = rng_for("arena_rim", seed + (0 if horizontal else 50))
    cv = canvas(w, h, col(*GROUT))
    xs, ys = grid(w, h)
    xs = xs.astype(int)
    ys = ys.astype(int)
    inner = (xs >= 1) & (xs <= w - 2) & (ys >= 1) & (ys <= h - 2)
    f = fbm(w, h, 2, 2, rng)
    idx = np.full((h, w), RIM_FACE)
    idx[(f + bayer(w, h, 4) * 0.04) < 0.15] = RIM_FACE - 1
    idx[(f + bayer(w, h, 4) * 0.04) > 0.88] = RIM_FACE + 1
    idx[inner & ((ys == 1) | (xs == 1))] = RIM_FACE + 1
    idx[inner & ((ys == h - 2) | (xs == w - 2))] = RIM_FACE - 1
    # carved groove along the slab's length, 1px dark + 1px lit below/right
    if horizontal:
        g = h // 2 - 1
        idx[g, 3:w - 3] = RIM_FACE - 2
        idx[g + 1, 3:w - 3] = RIM_FACE + 1
        for x in (3, w - 4):  # groove end caps
            idx[g - 1, x] = RIM_FACE - 1
    else:
        g = w // 2 - 1
        idx[3:h - 3, g] = RIM_FACE - 2
        idx[3:h - 3, g + 1] = RIM_FACE + 1
        for y in (3, h - 4):
            idx[y, g - 1] = RIM_FACE - 1
    R = RA[RIM_RAMP]
    face = R[np.clip(idx, 0, len(R) - 1)]
    cv[inner] = face[inner]
    for _ in range(int(rng.integers(1, 3))):
        x, y = int(rng.integers(2, w - 2)), int(rng.integers(2, h - 2))
        cv[y, x] = col(RIM_RAMP, RIM_FACE - 2)
    ring = ~inner
    cv[ring & (rng.random((h, w)) < 0.2)] = col(*GROUT_DEEP)
    _rim_studs(cv, horizontal)
    return cv


def _rim_studs(cv: np.ndarray, along_x: bool) -> None:
    """Half of a 2x2 bronze stud at each end of the slab; neighbouring slabs complete it,
    so a stud marks every cell boundary along the rim."""
    h, w = cv.shape[:2]
    if along_x:
        m = h // 2 - 1
        cv[m, 0], cv[m + 1, 0] = col("gold", 3), col("gold", 2)
        cv[m, w - 1], cv[m + 1, w - 1] = col("gold", 4), col("gold", 3)
    else:
        m = w // 2 - 1
        cv[0, m], cv[0, m + 1] = col("gold", 3), col("gold", 2)
        cv[h - 1, m], cv[h - 1, m + 1] = col("gold", 4), col("gold", 3)


def rim_corner(seed: int) -> np.ndarray:
    """12x12 corner block with a carved four-petal rosette."""
    n = 12
    cv = rim_slab(n, n, 90 + seed, True)
    R = RA[RIM_RAMP]
    xs, ys = grid(n, n)
    cv[1:n - 1, 1:n - 1] = R[RIM_FACE]
    cv[1, 1:n - 1] = R[RIM_FACE + 1]
    cv[1:n - 1, 1] = R[RIM_FACE + 1]
    cv[n - 2, 1:n - 1] = R[RIM_FACE - 1]
    cv[1:n - 1, n - 2] = R[RIM_FACE - 1]
    d = np.abs(xs + 0.5 - 6.0) + np.abs(ys + 0.5 - 6.0)
    cv[(d >= 2.5) & (d < 3.5)] = R[RIM_FACE - 2]
    cv[(d >= 3.5) & (d < 4.2) & ((xs + ys) > 11)] = R[RIM_FACE + 1]
    cv[(d < 1.2)] = col("gold", 3)
    cv[5, 5] = col("gold", 4)
    _rim_studs(cv, True)
    _rim_studs(cv, False)
    return cv


RIM_W, RIM_H = 96, 36


def rim_atlas() -> np.ndarray:
    """y 0..11: 4 horizontal slabs (24x12) at x = 0, 24, 48, 72.
    y 12..35: 4 vertical slabs (12x24) at x = 0, 12, 24, 36; corners (12x12) at x = 48, 60 (y 12..23)."""
    cv = canvas(RIM_W, RIM_H)
    for i in range(4):
        cv[0:12, i * 24:(i + 1) * 24] = rim_slab(24, 12, i, True)
        cv[12:36, i * 12:(i + 1) * 12] = rim_slab(12, 24, i, False)
    for i in range(2):
        cv[12:24, 48 + i * 12:60 + i * 12] = rim_corner(i)
    cv[24:36, 48:96] = col(*GROUT)
    cv[12:24, 72:96] = col(*GROUT)
    return cv


# --------------------------------------------------------------------------
# scorch decals (darkening overlays, quarter-step alpha)
# --------------------------------------------------------------------------


def scorch(seed: int) -> np.ndarray:
    """Soot stain: a soft dark heart, a ragged halo and a few streaks; alpha in quarter steps."""
    rng = rng_for("arena_scorch", seed)
    cv = canvas(T, T)
    xs, ys = grid(T, T)
    cx, cy = 12 + rng.uniform(-1.5, 1.5), 12 + rng.uniform(-1.5, 1.5)
    ang = np.arctan2(ys + 0.5 - cy, xs + 0.5 - cx)
    r = np.hypot(xs + 0.5 - cx, ys + 0.5 - cy)
    lobes = 1.0 + 0.18 * np.sin(ang * 3 + rng.uniform(0, 6)) + 0.1 * np.sin(ang * 7 + rng.uniform(0, 6))
    rr = r / (rng.uniform(8.0, 10.0) * lobes)
    n = fbm(T, T, 4, 2, rng)
    v = rr + (n - 0.5) * 0.5
    b = bayer(T, T, 4)
    a = np.zeros((T, T))
    a[v + b * 0.2 < 1.0] = 0.25
    a[v + b * 0.15 < 0.75] = 0.5
    a[v + b * 0.1 < 0.45] = 0.75
    for _ in range(int(rng.integers(3, 6))):  # streaks thrown out by the blast
        th = rng.uniform(0, math.tau)
        for i in range(int(rng.integers(3, 7))):
            x = int(round(cx + math.cos(th) * (7 + i)))
            y = int(round(cy + math.sin(th) * (7 + i)))
            if 1 <= x < T - 1 and 1 <= y < T - 1 and a[y, x] == 0:
                a[y, x] = 0.25
    S = RA["soot"]
    shade = np.where(a >= 0.75, 1, np.where(a >= 0.5, 2, 3))
    cv[..., :3] = S[shade][..., :3]
    cv[..., 3] = (a * 255).astype(np.uint8)
    return cv


def decal_atlas() -> np.ndarray:
    cv = canvas(4 * T, T)
    for i in range(4):
        cv[:, i * T:(i + 1) * T] = scorch(i)
    return cv


# --------------------------------------------------------------------------
# the sun-crane inlay (brass and verdigris set into the flagstones)
# --------------------------------------------------------------------------

EMB = 120  # texels (5 x 5 units)


def _crane_masks(n: int, c: float):
    """Top view of a crane flying north: (coverts+body, flight feathers, legs, head) masks."""
    body = Pen(n, n)
    body.poly([(c, c - 7.5), (c + 3.6, c - 3.0), (c + 3.4, c + 5.0), (c + 1.6, c + 10.5), (c, c + 12.0),
               (c - 1.6, c + 10.5), (c - 3.4, c + 5.0), (c - 3.6, c - 3.0)])
    body.line([(c, c - 6.0), (c, c - 16.5)], 2.4)                      # neck
    body.ellipse(c, c - 18.5, 2.3, 2.8)                                 # head
    body.poly([(c - 0.9, c - 20.5), (c + 0.9, c - 20.5), (c, c - 25.5)])  # beak
    coverts = Pen(n, n)
    flight = Pen(n, n)
    for sgn in (-1, 1):
        def P(x, y):
            return (c + sgn * x, c + y)
        # leading edge sweeps forward to the wrist, then back to the tip
        coverts.poly([P(2.5, -3.0), P(8.0, -7.0), P(14.0, -9.5), P(19.5, -10.0), P(23.5, -8.5), P(22.0, -5.0),
                      P(16.0, -2.5), P(9.0, -0.5), P(3.0, 1.5)])
        flight.poly([P(3.0, 0.0), P(9.0, -1.5), P(16.0, -3.5), P(22.0, -6.0), P(25.5, -8.0), P(28.5, -6.5),
                     P(28.0, -3.5), P(25.0, 0.5), P(20.0, 4.0), P(13.0, 6.5), P(6.0, 7.0), P(2.5, 5.5)])
    legs = Pen(n, n)
    legs.line([(c - 1.0, c + 10.0), (c - 2.0, c + 23.5)], 1.1)
    legs.line([(c + 1.0, c + 10.0), (c + 2.0, c + 23.5)], 1.1)
    b = body.mask(128)
    cov = coverts.mask(128) & ~b
    fl = flight.mask(128) & ~b & ~cov
    lg = legs.mask(120) & ~b & ~fl
    return b, cov, fl, lg


def emblem() -> np.ndarray:
    n = EMB
    c = n / 2.0
    xs, ys = grid(n, n)
    dx, dy = xs + 0.5 - c, ys + 0.5 - c
    r = np.hypot(dx, dy)
    ang = np.arctan2(dy, dx)
    cv = canvas(n, n)
    lit_side = (dx + dy) < 0  # upper-left half of a round feature faces the light

    def ring(r0, r1):
        return (r >= r0) & (r < r1)

    def brass_ring(r0, r1):
        m = ring(r0, r1)
        cv[m] = col("gold", 3)
        cv[m & (dx + dy < -0.45 * r)] = col("gold", 4)
        cv[m & (dx + dy > 0.6 * r)] = col("gold", 2)
        return m

    outer = brass_ring(54.5, 56.5)
    groove = ring(51.5, 52.5)
    cv[groove] = col("stone_warm", 2)
    # faceted sun rays (each ray has a lit and a shaded facet)
    k = 16
    t = (ang / (2 * math.pi) * k) % k
    idx = np.floor(t).astype(int)
    a = t - idx - 0.5                     # -0.5..0.5 across a ray slot
    axis = (idx + 0.5) / k * 2 * math.pi  # ray axis angle
    long_ray = idx % 2 == 0
    r_in = 35.0
    r_out = np.where(long_ray, 50.5, 44.5)
    half_w = 0.46 * (1.0 - (r - r_in) / (r_out - r_in))
    rays = (r >= r_in) & (r < r_out) & (np.abs(a) < half_w)
    side = np.sign(a)
    # facet normal: perpendicular to the ray axis on this side; lit if it faces the upper left
    nx = -np.sin(axis) * side
    ny = np.cos(axis) * side
    lit = (nx * -1 + ny * -1) > 0
    cv[rays & lit & long_ray] = col("gold", 3)
    cv[rays & ~lit & long_ray] = col("gold", 2)
    cv[rays & lit & ~long_ray] = col("gold", 2)
    cv[rays & ~lit & ~long_ray] = col("gold", 1)
    band = brass_ring(31.5, 33.5)
    disc = r < 31.5
    cv[disc] = col("stone_warm", 3)
    cv[disc & (r > 28.5) & ~lit_side] = col("stone_warm", 2)   # recessed field: shaded far wall
    cv[disc & (r > 29.5) & lit_side] = col("stone_warm", 2)
    body, cov, fl, legs = _crane_masks(n, c)
    fig = (body | cov | fl) & (r < 30.5)
    cv[fl & fig] = col("cloth_teal", 3)
    cv[fl & fig & (dy > 2.0)] = col("cloth_teal", 2)
    cv[cov & fig] = col("cloth_cream", 4)
    cv[cov & fig & (dy < -6.0)] = col("cloth_cream", 5)
    cv[body & fig] = col("cloth_cream", 5)
    cv[body & fig & (dx > 0.8) & (dy > -5)] = col("cloth_cream", 3)
    cv[legs & disc] = col("stone_warm", 1)
    cv[int(c - 19), int(c)] = col("cloth_red", 4)      # red crown
    cv[int(c - 20), int(c)] = col("cloth_red", 3)
    # brass edging around the inlaid figure (not along the slender neck and head)
    edge = fig & ~(np.roll(fig, 1, 0) & np.roll(fig, -1, 0) & np.roll(fig, 1, 1) & np.roll(fig, -1, 1))
    edge &= ~((dy < -7.0) & (np.abs(dx) < 3.5))
    cv[edge] = col("gold", 2)
    cv[edge & lit_side & (dy < -4)] = col("gold", 3)
    alpha = outer | groove | rays | band | disc
    cv[..., 3] = np.where(alpha, 255, 0).astype(np.uint8)
    cv[~alpha] = 0
    return cv


# --------------------------------------------------------------------------
# walls, coping, standing stones (triplanar textures, 24 texels / unit)
# --------------------------------------------------------------------------


def _ashlar_block(cv, rng, x0, y0, bw, bh, ramp, t, mortar, chisel=True):
    """One squared block with a 1px mortar joint on its top and left, bevelled from the upper left."""
    h, w = cv.shape[:2]
    R = RA[ramp]
    n = len(R)
    for yy in range(bh):
        for xx in range(bw):
            X, Y = (x0 + xx) % w, (y0 + yy) % h
            if yy == 0 or xx == 0:
                cv[Y, X] = mortar
                continue
            k = t
            if yy == 1 or xx == 1:
                k = t + 1
            if yy == bh - 1 or xx == bw - 1:
                k = t - 1
            if (yy == 1 and xx == bw - 1) or (yy == bh - 1 and xx == 1):
                k = t
            cv[Y, X] = R[int(np.clip(k, 0, n - 1))]
    if chisel:
        # tooling: short diagonal strokes across the face
        for _ in range(int(rng.integers(1, 4))):
            sx, sy = int(rng.integers(3, max(4, bw - 4))), int(rng.integers(3, max(4, bh - 3)))
            for i in range(int(rng.integers(2, 4))):
                X, Y = (x0 + sx + i) % w, (y0 + sy - i // 2) % h
                cv[Y, X] = R[max(0, t - 1)]
    for _ in range(int(rng.integers(0, 3))):  # pits
        px, py = int(rng.integers(2, max(3, bw - 2))), int(rng.integers(2, max(3, bh - 2)))
        cv[(y0 + py) % h, (x0 + px) % w] = R[max(0, t - 2)]
        cv[(y0 + py + 1) % h, (x0 + px + 1) % w] = R[min(n - 1, t + 1)]
    if rng.random() < 0.35:  # chipped corner
        cv[(y0 + bh - 1) % h, (x0 + bw - 1) % w] = mortar
        cv[(y0 + bh - 2) % h, (x0 + bw - 1) % w] = R[max(0, t - 1)]


def ashlar(name: str, seed: int, w: int, h: int, course: int, widths, ramp: str, tones, mortar,
           chisel: bool = True) -> np.ndarray:
    rng = rng_for(name, seed)
    cv = canvas(w, h)
    rows = h // course
    off = int(rng.integers(0, w))
    for r in range(rows):
        off = (off + int(rng.integers(w // 4, 3 * w // 4))) % w
        x = 0
        ws = []
        while x < w:
            bw = int(rng.choice(widths))
            if w - x - bw < min(widths):
                bw = w - x
            ws.append(bw)
            x += bw
        x = off
        for bw in ws:
            _ashlar_block(cv, rng, x, r * course, bw, course, ramp, int(rng.choice(tones)), mortar, chisel)
            x += bw
    return cv


def tex_block() -> np.ndarray:
    """Cool grey ashlar for side walls, pillars, the stage face and the stands (12 px = 0.5 unit
    courses); grey walls frame the warm sandstone board."""
    cv = ashlar("arena_block", 3, 48, 48, 12, [16, 20, 24, 28], "stone", [2, 3, 3], col("stone", 0))
    rng = rng_for("arena_block_moss", 1)
    joints = np.all(cv[..., :3] == col("stone", 0)[:3], axis=-1)
    m = joints & (fbm(48, 48, 4, 2, rng) > 0.7)
    cv[m] = col("moss", 1)
    cv[m & (rng.random((48, 48)) < 0.4)] = col("moss", 2)
    return cv


def tex_paving() -> np.ndarray:
    """Grey outdoor flagstones with grass in the joints (stage wings, stand floors)."""
    cv = ashlar("arena_paving", 8, 48, 48, 16, [16, 24, 32], "stone", [2, 2, 3], col("stone", 0), chisel=False)
    rng = rng_for("arena_paving_grass", 3)
    joints = np.all(cv[..., :3] == col("stone", 0)[:3], axis=-1)
    g = joints & (fbm(48, 48, 4, 2, rng) > 0.45)
    cv[g] = col("moss", 2)
    cv[g & (rng.random((48, 48)) < 0.35)] = col("moss", 3)
    return cv


def tex_coping() -> np.ndarray:
    """Pale capping slabs for wall tops, pillar caps, podiums and the stage wings."""
    cv = ashlar("arena_coping", 5, 48, 48, 16, [16, 24, 24, 32], "cloth_cream", [3, 3, 2], col("stone_warm", 2))
    rng = rng_for("arena_coping_crack", 2)
    for _ in range(3):
        path = walk(rng, int(rng.integers(0, 48)), int(rng.integers(0, 48)), rng.uniform(0, math.tau), 6, 0.6)
        for (x, y) in path:
            cv[y % 48, x % 48] = col("cloth_cream", 1)
    return cv


def tex_wall_bay() -> np.ndarray:
    """One 2-unit bay of the back wall (48 x 24 = the wall's full height): cornice, ashlar,
    a recessed panel with a carved sun roundel, base course."""
    w, h = 48, 24
    rng = rng_for("arena_wall", 9)
    cv = ashlar("arena_wall_field", 4, w, h, 8, [12, 16, 20], "stone", [2, 3, 3], col("stone", 0))
    # cornice (rows 0-2) and base course (rows 21-23)
    cv[0, :] = col("cloth_cream", 4)
    cv[1, :] = col("cloth_cream", 2)
    cv[2, :] = col("stone", 0)
    cv[21, :] = col("stone", 0)
    cv[22, :] = col("stone", 2)
    cv[23, :] = col("stone", 1)
    for x in range(0, w, 6):
        cv[22, x] = col("stone", 0)
        cv[23, x] = col("stone", 0)
    # recessed panel
    x0, x1, y0, y1 = 13, 35, 4, 20
    cv[y0:y1, x0:x1] = col("stone", 2)
    cv[y0, x0:x1] = col("stone", 0)        # top inner edge in shadow
    cv[y0:y1, x0] = col("stone", 0)        # left inner edge in shadow
    cv[y0 + 1, x0 + 1:x1] = col("stone", 1)
    cv[y0 + 1:y1, x0 + 1] = col("stone", 1)
    cv[y1 - 1, x0:x1] = col("stone", 4)    # bottom inner edge lit
    cv[y0:y1, x1 - 1] = col("stone", 4)
    # carved sun roundel in the panel
    xs, ys = grid(w, h)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    r = np.hypot(xs + 0.5 - cx, ys + 0.5 - cy)
    ang = np.arctan2(ys + 0.5 - cy, xs + 0.5 - cx)
    disc = r < 3.6
    rays = (r >= 4.6) & (r < 6.9) & ((np.cos(ang * 8) > 0.55))
    cv[disc] = col("gold", 3)
    cv[disc & ((xs + ys) > cx + cy + 1)] = col("gold", 2)
    cv[disc & ((xs + ys) < cx + cy - 3)] = col("gold", 4)
    cv[rays] = col("gold", 2)
    lip = np.roll(rays, 1, 0) & np.roll(rays, 1, 1) & ~rays & (r < 8)
    cv[lip] = col("stone", 1)
    # weathering streaks running down from the cornice
    for _ in range(4):
        x = int(rng.integers(0, w))
        for y in range(3, int(rng.integers(8, 16))):
            if not (x0 <= x < x1 and y0 <= y < y1) and rng.random() < 0.7:
                cv[y, x] = col("stone", 1)
    return cv


def tex_monolith() -> np.ndarray:
    """Cool grey standing-stone face: weathered vertical grain, carved spiral glyphs, lichen."""
    w = h = 48
    rng = rng_for("arena_monolith", 21)
    f = fbm(w, h, 3, 3, rng, cells_y=6)
    k = np.full((h, w), 3)
    k[f < 0.32] = 2
    k[f > 0.72] = 4
    streak = fbm(w, h, 12, 1, rng, cells_y=2) > 0.7
    k[streak & (k > 2)] -= 1
    cv = canvas(w, h)
    cv[:] = RA["stone"][k]
    # spiral glyphs: dark groove, lit lower-right lip
    for (gx, gy, turns) in ((12, 14, 2.2), (34, 36, 1.8), (36, 10, 1.4)):
        pts = []
        for i in range(70):
            t = i / 69.0
            a = t * turns * math.tau
            rr = 1.0 + t * 6.0
            pts.append((gx + math.cos(a) * rr, gy + math.sin(a) * rr * 0.9))
        groove = set()
        for (x, y) in pts:
            groove.add((int(round(x)) % w, int(round(y)) % h))
        for (x, y) in groove:
            cv[y, x] = col("stone", 1)
        for (x, y) in groove:
            if ((x + 1) % w, (y + 1) % h) not in groove:
                cv[(y + 1) % h, (x + 1) % w] = col("stone", 4)
    # lichen: mossy green and a few rusty-orange crusts
    lich = fbm(w, h, 6, 2, rng) > 0.8
    sp = lich & (rng.random((h, w)) < 0.4)
    cv[sp] = col("moss", 3)
    cv[sp & (rng.random((h, w)) < 0.35)] = col("moss", 4)
    rust = (fbm(w, h, 8, 1, rng) > 0.9) & (rng.random((h, w)) < 0.4)
    cv[rust] = col("leaf_autumn", 4)
    return cv


# --------------------------------------------------------------------------
# cloth banners hung on the back wall (team blue / team red)
# --------------------------------------------------------------------------

BANNER_W, BANNER_H = 16, 30


def banner_cloth(ramp: str, motif: str) -> np.ndarray:
    w, h = BANNER_W, BANNER_H
    cv = canvas(w, h)
    xs, ys = grid(w, h)
    xs = xs.astype(int)
    ys = ys.astype(int)
    # swallowtail: the hem rises toward the middle
    hem = h - 2 - np.maximum(0, 4 - np.abs(xs - 7.5) * 0.9).astype(int)
    cloth = (xs >= 1) & (xs <= 14) & (ys >= 2) & (ys <= hem)
    cv[cloth] = col(ramp, 2)
    cv[cloth & (xs <= 3)] = col(ramp, 3)                     # lit fold on the left
    cv[cloth & (xs >= 12)] = col(ramp, 1)                    # shaded right edge
    cv[cloth & ((xs == 7) | (xs == 8)) & (ys > 4)] = col(ramp, 1)  # central fold shadow
    cv[cloth & (xs == 6) & (ys > 4)] = col(ramp, 3)
    trim = cloth & ((xs == 2) | (xs == 13) | (ys == hem) | (ys == 3))
    cv[trim] = col("gold", 3)
    cv[trim & (xs == 13)] = col("gold", 2)
    # rod and finials
    cv[1, 0:16] = col("wood", 2)
    cv[0, 1:15] = col("wood", 3)
    cv[0:2, 0] = col("gold", 3)
    cv[0:2, 15] = col("gold", 3)
    # fringe below the hem
    for x in range(2, 14):
        if x % 2 == 0:
            cv[min(h - 1, hem[0, x] + 1), x] = col("gold", 2)
    # motif in gold
    cx, cy = 7.5, 12.5
    r = np.hypot(xs + 0.5 - cx - 0.5, ys + 0.5 - cy)
    if motif == "sun":
        ang = np.arctan2(ys + 0.5 - cy, xs + 0.5 - cx - 0.5)
        disc = r < 2.6
        rays = (r >= 3.4) & (r < 4.9) & (np.cos(ang * 6) > 0.35)
        cv[disc & cloth] = col("gold", 4)
        cv[disc & cloth & (xs + ys > 21)] = col("gold", 3)
        cv[rays & cloth] = col("gold", 3)
    else:
        # three stacked waves
        for k, yy in enumerate((9, 12, 15)):
            for x in range(4, 12):
                y = yy + int(round(math.sin((x - 4) / 7.0 * math.tau) * 1.0))
                cv[y, x] = col("gold", 4 if k == 1 else 3)
    return cv


def banners() -> np.ndarray:
    cv = canvas(BANNER_W * 2, BANNER_H)
    cv[:, :BANNER_W] = banner_cloth("cloth_blue", "wave")
    cv[:, BANNER_W:] = banner_cloth("cloth_red", "sun")
    return cv


PENNANT_W, PENNANT_H = 8, 9


def pennants() -> np.ndarray:
    """Bunting: three pennants (team blue, cream, team red), 8 px wide so a row of them
    shares one continuous rope along its top row."""
    cv = canvas(PENNANT_W * 3, PENNANT_H)
    for i, (ramp, hi) in enumerate((("cloth_blue", 4), ("cloth_cream", 5), ("cloth_red", 4))):
        x0 = i * PENNANT_W
        cv[0, x0:x0 + PENNANT_W] = col("wood", 1)
        for y in range(1, PENNANT_H):
            half = 3.5 * (1.0 - (y - 1) / (PENNANT_H - 1.0))
            for x in range(PENNANT_W):
                if abs(x + 0.5 - PENNANT_W / 2.0) <= half + 0.25:
                    k = hi - 1
                    if x + 0.5 < PENNANT_W / 2.0 - half + 1.2:
                        k = hi  # lit left edge
                    elif x + 0.5 > PENNANT_W / 2.0 + half - 1.2:
                        k = hi - 2  # shaded right edge
                    cv[y, x0 + x] = col(ramp, k)
        cv[1, x0 + 1:x0 + PENNANT_W - 1] = col("gold", 3)  # hem stitched over the rope
    return cv


# --------------------------------------------------------------------------
# board mock-up (preview only; the game composes the board in arena_floor.gdshader)
# --------------------------------------------------------------------------


def board_mock(cols: int = 14, rows: int = 9, stones=((-2.5, -2.0), (2.5, 2.0)), seed: int = 4242,
               yard: bool = False) -> np.ndarray:
    rng = np.random.default_rng(seed)
    atlas = yard_atlas() if yard else stone_atlas()
    rim = yard_rim_atlas() if yard else rim_atlas()
    dec = decal_atlas()
    emb = emblem() if not yard else canvas(EMB, EMB)
    rw = 12
    W, H = cols * T + 2 * rw, rows * T + 2 * rw
    cv = canvas(W, H)
    ox, oy = -cols / 2.0, -rows / 2.0
    stone_cells = {(int(math.floor(x - ox)), int(math.floor(y - oy))) for x, y in stones}
    for cy in range(rows):
        for cx in range(cols):
            tone = (cx + cy) % 2
            ccx, ccy = cx + 0.5 + ox, cy + 0.5 + oy
            d = math.hypot(ccx / (cols / 2.0), ccy / (rows / 2.0))
            edge = min(cx, cols - 1 - cx, cy)
            if (cx, cy) in stone_cells:
                r, c = 6, tone
            elif edge == 0 and rng.random() < 0.7:
                r, c = 4 + tone, int(rng.integers(0, 4))
            elif cy == rows - 1 and rng.random() < 0.5:
                r, c = 4 + tone, 4 + int(rng.integers(0, 4))
            elif d < 0.55 and rng.random() < 0.8 - d:
                r, c = 2 + tone, int(rng.integers(0, 8))
            else:
                r, c = tone, int(rng.choice(8, p=[0.2, 0.2, 0.14, 0.1, 0.1, 0.1, 0.08, 0.08]))
            tile = atlas[r * T:(r + 1) * T, c * T:(c + 1) * T]
            cv[rw + cy * T:rw + (cy + 1) * T, rw + cx * T:rw + (cx + 1) * T] = tile
    # emblem inlay over the faces (grout lines stay)
    e0x = rw + int(round((-EMB / 2.0) - ox * T))
    e0y = rw + int(round((-EMB / 2.0) - oy * T))
    for y in range(EMB):
        for x in range(EMB):
            if emb[y, x, 3] == 0:
                continue
            X, Y = e0x + x, e0y + y
            lx, ly = (X - rw) % T, (Y - rw) % T
            e = emb[y, x].astype(float)
            if lx in (0, T - 1) or ly in (0, T - 1):
                e[:3] *= 0.5
            elif lx == 1 or ly == 1:
                e[:3] = np.minimum(255, e[:3] * 1.12)
            elif lx == T - 2 or ly == T - 2:
                e[:3] *= 0.85
            cv[Y, X] = e.astype(np.uint8)
    # scorch marks (multiply)
    for (sx, sy, k) in ((3, 6, 0), (10, 2, 1), (11, 7, 2), (5, 1, 3)):
        sub = cv[rw + sy * T:rw + (sy + 1) * T, rw + sx * T:rw + (sx + 1) * T].astype(float)
        d = dec[:, k * T:(k + 1) * T].astype(float)
        a = d[..., 3:4] / 255.0
        mul = 1.0 - a * 0.85 * (1.0 - d[..., :3] / 255.0)
        sub[..., :3] = np.clip(sub[..., :3] * mul, 0, 255)
        cv[rw + sy * T:rw + (sy + 1) * T, rw + sx * T:rw + (sx + 1) * T] = sub.astype(np.uint8)
    # rim
    for cx in range(cols):
        v = int(rng.integers(0, 4))
        slab = rim[0:12, v * 24:(v + 1) * 24]
        cv[0:12, rw + cx * T:rw + (cx + 1) * T] = slab
        v = int(rng.integers(0, 4))
        cv[H - 12:H, rw + cx * T:rw + (cx + 1) * T] = rim[0:12, v * 24:(v + 1) * 24]
    for cy in range(rows):
        for xx in (0, W - 12):
            v = int(rng.integers(0, 4))
            cv[rw + cy * T:rw + (cy + 1) * T, xx:xx + 12] = rim[12:36, v * 12:(v + 1) * 12]
    for (xx, yy) in ((0, 0), (W - 12, 0), (0, H - 12), (W - 12, H - 12)):
        cv[yy:yy + 12, xx:xx + 12] = rim[12:24, 48:60]
    return cv


# --------------------------------------------------------------------------
# build / check
# --------------------------------------------------------------------------

ASSETS = {
    "arena_tiles": (stone_atlas, (STONE_COLS * T, STONE_ROWS * T), True),
    "arena_rim": (rim_atlas, (RIM_W, RIM_H), True),
    "arena_tiles_yard": (yard_atlas, (STONE_COLS * T, STONE_ROWS * T), True),
    "arena_rim_yard": (yard_rim_atlas, (RIM_W, RIM_H), True),
    "arena_decals": (decal_atlas, (4 * T, T), False),
    "arena_emblem": (emblem, (EMB, EMB), False),
    "arena_block": (tex_block, (48, 48), True),
    "arena_coping": (tex_coping, (48, 48), True),
    "arena_paving": (tex_paving, (48, 48), True),
    "arena_wall": (tex_wall_bay, (48, 24), True),
    "arena_monolith": (tex_monolith, (48, 48), True),
    "arena_banners": (banners, (BANNER_W * 2, BANNER_H), False),
    "arena_pennants": (pennants, (PENNANT_W * 3, PENNANT_H), False),
}


def check() -> list[str]:
    problems = []
    for name, (_, size, opaque) in ASSETS.items():
        p = os.path.join(OUT, name + ".png")
        if not os.path.exists(p):
            problems.append(f"missing {p}")
            continue
        a = np.array(Image.open(p).convert("RGBA"))
        if (a.shape[1], a.shape[0]) != tuple(size):
            problems.append(f"{name}: size {a.shape[1]}x{a.shape[0]} != {size}")
        vis = a[..., 3] > 0
        bad = {tuple(int(v) for v in c) for c in a[vis][:, :3]} - set(_REV)
        if bad:
            problems.append(f"{name}: {len(bad)} off-palette colours e.g. {list(bad)[:3]}")
        if opaque and not (a[..., 3] == 255).all():
            problems.append(f"{name}: must be fully opaque")
    return problems


def main(argv: list[str]) -> int:
    only = [a for a in argv if not a.startswith("--")]
    if "--check" not in argv:
        for name, (fn, _, _) in ASSETS.items():
            if only and not any(o in name for o in only):
                continue
            cv = fn()
            save(cv, name)
            preview(cv, name, 6 if cv.shape[0] < 80 else 4)
            print("wrote", name, cv.shape[1], "x", cv.shape[0])
    if "--mock" in argv or not only:
        preview(board_mock(), "arena_board_mock", 3)
        preview(board_mock(13, 9, (), yard=True), "arena_yard_mock", 3)
    problems = check()
    for p in problems:
        print("  -", p)
    print("all checks passed" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
