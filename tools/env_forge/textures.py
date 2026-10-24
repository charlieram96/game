"""Group A - tileable world textures (seamless in both axes, no outlines).

Every texture is drawn on a periodic canvas: noise is periodic, features are
stamped with wrap-around coordinates, so the tile repeats without seams.
Texel density: 24 texels / meter (a 48px tile covers 2 x 2 m).
"""

from __future__ import annotations

import math
import os

import numpy as np

from kit import (C, OUT_ENV, RA, spectral, bayer, canvas, dilate, edge_in, erode, fbm, grid, grid_preview, lambert, levels,
                 norm01, poisson, put, rng_for, save_png, shift, tile_preview, vnoise, voronoi, wrap_delta)

OUT = os.path.join(OUT_ENV, "textures")


# --------------------------------------------------------------------------
# small wrap-aware stamps
# --------------------------------------------------------------------------


def wput(cv, x, y, col):
    h, w = cv.shape[:2]
    cv[int(y) % h, int(x) % w] = col


def shaded_blob(cv, cx, cy, rx, ry, name, lo, hi, shadow=None, wrap=True, rim_dark=True, mask_out=None):
    """Small rounded pebble/stone: ellipse shaded from the upper-left between ramp idx lo..hi.

    shadow: (ramp, idx) colour of a 1px cast shadow toward the lower-right.
    """
    h, w = cv.shape[:2]
    x0, x1 = int(math.floor(cx - rx - 2)), int(math.ceil(cx + rx + 2))
    y0, y1 = int(math.floor(cy - ry - 2)), int(math.ceil(cy + ry + 2))
    L = np.array([-0.6, -0.75, 0.6])
    L = L / np.linalg.norm(L)
    pts = []
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            u = (x + 0.5 - cx) / rx
            v = (y + 0.5 - cy) / ry
            rr = u * u + v * v
            if rr <= 1.0:
                z = math.sqrt(max(0.0, 1 - rr))
                s = max(0.0, u * L[0] + v * L[1] + z * L[2])
                pts.append((x, y, s, rr))
    if shadow is not None:
        sn, si = shadow
        inside = {(x, y) for x, y, _, _ in pts}
        for x, y, _, _ in pts:
            for dx, dy in ((1, 1), (1, 0), (0, 1)):
                if (x + dx, y + dy) not in inside:
                    wput(cv, x + dx, y + dy, RA[sn][si]) if wrap else put(cv, x + dx, y + dy, RA[sn][si])
    n = hi - lo + 1
    for x, y, s, rr in pts:
        k = lo + min(n - 1, int(s * n * 1.05))
        if rim_dark and rr > 0.65 and s < 0.45:
            k = max(lo, k - 1)
        col = RA[name][k]
        if wrap:
            wput(cv, x, y, col)
        else:
            put(cv, x, y, col)
    return pts


def paint_idx(cv, mask, name, idx):
    r = RA[name]
    cv[mask] = r[np.clip(idx[mask], 0, len(r) - 1)]


# --------------------------------------------------------------------------
# grass family
# --------------------------------------------------------------------------


# Tone ladders: dark -> light; each rung is a list of interchangeable colours (picked per tuft).
LADDER_A = [[RA["leaf"][1]], [RA["leaf"][2]], [RA["leaf"][3]], [RA["leaf"][4]], [RA["leaf"][5]], [RA["leaf"][6]]]
LADDER_B = [[RA["leaf"][2]], [RA["leaf"][3]], [RA["leaf"][4]], [RA["ui_focus"][2], RA["leaf"][5]],
            [RA["ui_focus"][3], RA["moss"][5]], [RA["leaf"][6]]]
LADDER_DARK = [[RA["leaf"][0]], [RA["leaf"][1]], [RA["leaf"][2]], [RA["leaf"][3]], [RA["moss"][3], RA["leaf"][4]],
               [RA["leaf"][4]]]


def tuft(cv, rng, x, y, b, ladder, size=None, shade_only=False):
    """One blade cluster rooted at (x, y): blades fan out upward from a shared root;
    left blades lit, right blades in shade, dark pocket at the root. b = ladder rung of the ground."""
    top = len(ladder) - 1
    pick = {k: ladder[k][int(rng.integers(len(ladder[k])))] for k in range(len(ladder))}

    def col(k):
        return pick[int(np.clip(k, 0, top))]

    size = size if size is not None else int(rng.choice([1, 2, 2, 3, 3, 3]))
    dirs = {1: [0], 2: [-1, 1] if rng.random() < 0.5 else [-1, 0], 3: [-1, 0, 1]}[size]
    spread = rng.uniform(0.55, 0.95)
    wput(cv, x, y, col(b - 1))
    if size >= 2:
        wput(cv, x + 1, y, col(b - 1))
    for d in dirs:
        ln = int(rng.choice([2, 3, 3, 4])) if d == 0 else int(rng.choice([2, 2, 3]))
        lit = d < 0 or (d == 0 and rng.random() < 0.65)
        for i in range(ln):
            xx = x + int(round(d * (i + 0.5) * spread))
            yy = y - 1 - i
            if shade_only:
                k = b - 1 if i < ln - 1 else b
            elif lit:
                k = b + (2 if i == ln - 1 else 1)
            else:
                k = b + (1 if i == ln - 1 else 0)
            wput(cv, xx, yy, col(k))


def grass_layer(cv, rng, ladder, rung, density=4.4, skip=None, shade_frac=0.18):
    """Blade clusters painted in y order (front overlaps back); rung = per-pixel ground rung map."""
    h, w = cv.shape[:2]
    pts = poisson(w, h, density, rng)
    pts.sort(key=lambda p: p[1])
    for (px, py) in pts:
        x, y = int(px), int(py)
        if skip is not None and skip[y % h, x % w]:
            continue
        b = int(rung[y % h, x % w])
        tuft(cv, rng, x, y, b, ladder, shade_only=rng.random() < shade_frac)


def grass_base(rng, ladder, rungs=(1, 2, 3), t_lo=0.16, t_hi=0.70, w=48, h=48, base_pick=None):
    """Soft mottled ground: spectral noise thresholded into 3 rungs, dithered only at the borders."""
    f = spectral(w, h, rng, 1.0, 5.5, beta=0.9)
    b2 = bayer(w, h, 2)
    idx = (f + b2 * 0.05 >= t_lo).astype(int) + (f + b2 * 0.05 >= t_hi).astype(int)
    rung = np.array(rungs)[idx]
    cv = canvas(w, h)
    for i, r in enumerate(rungs):
        choice = ladder[r][0] if base_pick is None else base_pick.get(r, ladder[r][0])
        cv[idx == i] = choice
    return cv, rung, f


def tex_grass_a():
    rng = rng_for("grass_a")
    cv, rung, f = grass_base(rng, LADDER_A, (1, 2, 3))
    grass_layer(cv, rng, LADDER_A, rung, density=4.2)
    return cv


def tex_grass_b():
    rng = rng_for("grass_b", 3)
    cv, rung, f = grass_base(rng, LADDER_B, (1, 2, 3), t_lo=0.06, t_hi=0.6, base_pick={3: RA["ui_focus"][2]})
    grass_layer(cv, rng, LADDER_B, rung, density=3.8, shade_frac=0.14)
    return cv


def fallen_leaf(cv, x, y, ang, ln, wd, name, lo, hi, rng):
    """Small lens-shaped leaf lying flat: lit upper-left half, darker lower half, midrib, contact shadow."""
    ca, sa = math.cos(ang), math.sin(ang)
    cells = []
    R = int(ln) + 2
    for yy in range(-R, R + 1):
        for xx in range(-R, R + 1):
            u = (xx * ca + yy * sa) / (ln / 2)
            v = (-xx * sa + yy * ca) / (wd / 2)
            if abs(u) <= 1 and abs(v) <= (1 - u * u) ** 0.8 + 0.05:
                cells.append((xx, yy, u, v))
    occ = {(a, b) for a, b, _, _ in cells}
    for xx, yy, _, _ in cells:
        if (xx + 1, yy + 1) not in occ:
            wput(cv, x + xx + 1, y + yy + 1, RA["leaf"][0])
    for xx, yy, u, v in cells:
        nrm = -xx * sa + yy * ca  # side of the midrib
        k = hi if (nrm < -0.3 and v < 0) or (v < -0.25) else (lo + 1 if abs(v) < 0.35 else lo)
        if abs(v) < 0.25 and abs(u) < 0.8:
            k = lo  # midrib
        k = int(np.clip(k, lo, hi))
        wput(cv, x + xx, y + yy, RA[name][k])


def tex_grass_dark():
    """Forest floor: dark mossy grass, sparse tufts, fallen leaves lying flat."""
    rng = rng_for("grass_dark", 1)
    w = h = 48
    cv, rung, f = grass_base(rng, LADDER_DARK, (1, 2, 3), t_lo=0.22, t_hi=0.86)
    litter = spectral(w, h, rng, 2.0, 6.0, beta=0.6)
    soil = (litter > 0.72) & (f < 0.45) & (bayer(w, h, 2) > 0.1)
    cv[soil] = RA["earth"][1]
    grass_layer(cv, rng, LADDER_DARK, rung, density=5.4, shade_frac=0.3)
    kinds = [("earth", 2, 4), ("earth", 2, 4), ("earth", 1, 3), ("earth", 1, 3), ("leaf_autumn", 1, 3),
             ("leaf_autumn", 0, 2), ("moss", 2, 4)]
    for (px, py) in poisson(w, h, 5.0, rng):
        if litter[int(py), int(px)] < 0.46 + 0.12 * rng.random():
            continue
        name, lo, hi = kinds[int(rng.integers(len(kinds)))]
        fallen_leaf(cv, int(px), int(py), rng.uniform(0, math.pi), rng.uniform(3.6, 5.6), rng.uniform(2.0, 3.0),
                    name, lo, hi, rng)
    # a few blades growing over the litter
    grass_layer(cv, rng, LADDER_DARK, rung, density=11.0, shade_frac=0.2)
    return cv


def tex_flower_meadow():
    rng = rng_for("flower_meadow", 5)
    w = h = 48
    cv, rung, f = grass_base(rng, LADDER_A, (1, 2, 3))
    grass_layer(cv, rng, LADDER_A, rung, density=4.6)
    # tiny flowers: (ramp, light, shade) - centre dot contrasts
    flowers = [("cloth_cream", 5, 3), ("gold", 4, 3), ("sigil", 5, 4), ("cloth_blue", 5, 4), ("cloth_cream", 4, 2),
               ("cloth_plum", 5, 4)]
    pts = poisson(w, h, 4.3, rng)
    clus = spectral(w, h, rng, 2.0, 5.0, beta=0.6)
    for i, (px, py) in enumerate(pts):
        x, y = int(px), int(py)
        if clus[y, x] < 0.3 + 0.35 * rng.random():
            continue
        name, hi, lo = flowers[i % len(flowers)] if rng.random() < 0.7 else flowers[int(rng.integers(len(flowers)))]
        big = rng.random() < 0.4
        if big:
            # 5-px bloom: lit upper/left petals, shaded lower/right, warm centre, stem shadow
            wput(cv, x + 1, y + 2, RA["leaf"][1])
            wput(cv, x, y + 2, RA["leaf"][3])
            wput(cv, x, y - 1, RA[name][hi])
            wput(cv, x - 1, y, RA[name][hi])
            wput(cv, x + 1, y, RA[name][lo])
            wput(cv, x, y + 1, RA[name][lo])
            wput(cv, x, y, RA["gold"][5] if name not in ("gold",) else RA["ember"][4])
        else:
            wput(cv, x + 1, y + 1, RA["leaf"][1])
            wput(cv, x, y + 1, RA["leaf"][3])
            wput(cv, x, y, RA[name][hi])
            wput(cv, x + 1, y, RA[name][lo])
    return cv


# --------------------------------------------------------------------------
# earth / sand
# --------------------------------------------------------------------------


def tex_dirt_path():
    rng = rng_for("dirt_path", 2)
    w = h = 48
    f = spectral(w, h, rng, 1.0, 6.0, beta=0.8)
    b2 = bayer(w, h, 2)
    f2 = spectral(w, h, rng, 3.0, 8.0, beta=0.5)
    f = 0.75 * f + 0.25 * f2
    idx = (f + b2 * 0.05 >= 0.2).astype(int) + (f + b2 * 0.05 >= 0.74).astype(int)
    lut = np.array([2, 3, 4])
    cv = canvas(w, h)
    cv[:] = RA["earth"][lut[idx]]
    # shallow worn depressions: dark upper-left rim, light lower-right rim
    dep = spectral(w, h, rng, 2.0, 5.0, beta=0.5) > 0.84
    rim_dark = dep & ~shift(dep, 1, 1, wrap=True)
    rim_lit = shift(dep, 1, 1, wrap=True) & ~dep
    cv[dep] = RA["earth"][2]
    cv[rim_dark] = RA["earth"][1]
    cv[rim_lit] = RA["earth"][4]
    # grit: sparse 1px specks
    for (px, py) in poisson(w, h, 3.6, rng):
        k = int(idx[int(py), int(px)])
        if rng.random() < 0.55:
            wput(cv, px, py, RA["earth"][lut[k] - 1])
        else:
            wput(cv, px, py, RA["earth"][min(5, lut[k] + 1)])
    # pebbles: few, varied sizes, mostly warm stone, some half-buried
    pts = poisson(w, h, 8.5, rng)
    for i, (px, py) in enumerate(pts):
        if rng.random() < 0.45:
            continue
        big = rng.random() < 0.3
        rx = rng.uniform(1.8, 2.6) if big else rng.uniform(0.9, 1.5)
        ry = rx * rng.uniform(0.6, 0.8)
        name = "stone_warm" if rng.random() < 0.8 else "sand"
        lo, hi = (2, 4) if name == "stone_warm" else (1, 3)
        shaded_blob(cv, px, py, rx, ry, name, lo, hi, shadow=("earth", 1))
        if big and rng.random() < 0.6:
            # little companion grit around big pebbles
            wput(cv, px + rx + 1, py + 1, RA["stone_warm"][3])
    return cv


def dent(cv, cx, cy, rx, ry, ang, name, base, rim_only=True, strength=1.0):
    """Bowl-shaped depression lit from the upper-left: dark upper-left inner wall, lit lower-right wall."""
    ca, sa = math.cos(ang), math.sin(ang)
    R = int(max(rx, ry)) + 2
    for yy in range(-R, R + 1):
        for xx in range(-R, R + 1):
            px, py = xx + 0.5 - (cx - math.floor(cx)), yy + 0.5 - (cy - math.floor(cy))
            u = (px * ca + py * sa) / rx
            v = (-px * sa + py * ca) / ry
            r2 = u * u + v * v
            if r2 > 1.0:
                continue
            # slope direction in image space
            gx, gy = px / max(0.6, math.hypot(px, py)), py / max(0.6, math.hypot(px, py))
            lit = -(gx * -1 + gy * -1) * (r2 ** 0.5)  # >0 on lower-right wall
            k = base
            if lit < -0.35 * strength:
                k = base - 1
            elif lit > 0.45 * strength:
                k = base + 1
            elif rim_only:
                continue
            wput(cv, math.floor(cx) + xx, math.floor(cy) + yy, RA[name][k])


def tex_sand_arena():
    rng = rng_for("sand_arena", 4)
    w = h = 48
    f = spectral(w, h, rng, 1.0, 4.0, beta=0.8)
    cv = canvas(w, h, RA["sand"][4])
    idx = np.ones((h, w), int)
    # soft darker zones: sparse ordered-dither of the darker shade, no hard edges
    b4 = bayer(w, h, 4) + 0.5  # 0..1
    soft = (b4 < (0.38 - f) * 1.1)
    cv[soft] = RA["sand"][3]
    idx[soft] = 0
    # grain specks
    for (px, py) in poisson(w, h, 2.8, rng):
        r = rng.random()
        if r < 0.55:
            wput(cv, px, py, RA["sand"][3])
        elif r < 0.85:
            wput(cv, px, py, RA["sand"][5])
        else:
            wput(cv, px, py, RA["sand"][2])
    # sweeping drag scuffs: shallow arcs (dark inner edge, light outer edge)
    for _ in range(3):
        cx, cy = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.uniform(9, 15)
        a0 = rng.uniform(0, math.tau)
        span = rng.uniform(0.5, 0.9)
        n = int(r * span * 1.4)
        for i, t in enumerate(np.linspace(0, span, n)):
            x = cx + math.cos(a0 + t) * r
            y = cy + math.sin(a0 + t) * r * 0.6
            if 1 <= i < n - 1:
                wput(cv, x, y, RA["sand"][3])
                wput(cv, x + 1, y + 1, RA["sand"][5] if i % 3 else RA["sand"][4])
    # footprints: pairs of small oval dents along a walking line
    for (px, py) in poisson(w, h, 15, rng):
        ang = rng.uniform(0, math.tau)
        step_x, step_y = math.cos(ang) * 5, math.sin(ang) * 5
        side_x, side_y = -math.sin(ang) * 1.6, math.cos(ang) * 1.6
        for j in range(2):
            sgn = 1 if j % 2 else -1
            fx = px + step_x * j + side_x * sgn
            fy = py + step_y * j + side_y * sgn
            dent(cv, fx, fy, 3.0, 1.7, ang, "sand", 4, rim_only=False, strength=0.45)
    # grains and tiny pebbles
    for (px, py) in poisson(w, h, 4.6, rng):
        k = idx[int(py), int(px)]
        wput(cv, px, py, RA["sand"][5] if (rng.random() < 0.45) else RA["sand"][2 + min(k, 1)])
    for (px, py) in poisson(w, h, 13, rng):
        if rng.random() < 0.5:
            shaded_blob(cv, px, py, rng.uniform(0.8, 1.3), rng.uniform(0.6, 0.9), "stone_warm", 3, 5,
                        shadow=("sand", 2))
    return cv


# --------------------------------------------------------------------------
# masonry
# --------------------------------------------------------------------------


def tex_cobble():
    rng = rng_for("cobble", 7)
    w = h = 48
    pts = poisson(w, h, 8.4, rng)
    ids, d1, d2 = voronoi(w, h, pts)
    gap = d2 - d1
    # rounded stones: corners (where 3 cells meet) are eaten by a wider mortar band
    mortar = gap < 1.6
    hm = np.clip((gap - 1.0) / 4.0, 0, 1) ** 0.5
    hm += 0.15 * fbm(w, h, 12, 2, rng)
    sh = lambert(hm * 3.2, 1.0)
    tone = np.array([rng.uniform(-0.1, 0.1) for _ in pts])[ids]
    kinds = np.zeros(len(pts), int)
    chosen = []
    for i, (px, py) in enumerate(pts):
        far = all(math.hypot(wrap_delta(np.array(px - qx), w), wrap_delta(np.array(py - qy), h)) > 15
                  for qx, qy in chosen)
        if far and rng.random() < 0.6:
            kinds[i] = 1
            chosen.append((px, py))
    kind = kinds[ids]
    v = np.clip(sh * 0.95 + tone, 0, 1)
    k = levels(v, [0.36, 0.58, 0.76, 0.9], dither=0.08)
    cv = canvas(w, h)
    warm = RA["stone_warm"][np.clip(k + 1, 0, 5)]
    cool = RA["stone"][np.clip(k + 1, 0, 5)]
    cv[:] = np.where((kind == 1)[..., None], cool, warm)
    dn = fbm(w, h, 6, 2, rng)
    cv[mortar] = np.where((dn[mortar] > 0.5)[..., None], RA["earth"][1], RA["stone_warm"][1])
    # deepest shadow on the lower-right side of each stone (just outside it)
    ms = mortar & shift(~mortar, 1, 1, wrap=True)
    cv[ms] = RA["stone_warm"][0]
    # a lit lip at the upper-left edge of each stone
    lip = ~mortar & shift(mortar, 1, 1, wrap=True) & ~shift(mortar, -1, -1, wrap=True)
    cv[lip & (kind == 0)] = RA["stone_warm"][5]
    cv[lip & (kind == 1)] = RA["stone"][5]
    # tufts of moss in a few joints
    moss = mortar & ~ms & (spectral(w, h, rng, 2.0, 5.0) > 0.7)
    cv[moss] = RA["moss"][2]
    cv[moss & shift(moss, 0, 1, wrap=True) & (bayer(w, h) > 0)] = RA["moss"][3]
    return cv


def brick_rows(rng, w, h, row_h, widths_choices, offset_mode="random"):
    """Return list of rows: (y0, y1, [x0...]) with brick start positions summing to w (periodic)."""
    rows = []
    y = 0
    r = 0
    while y < h:
        rh = row_h[r % len(row_h)] if isinstance(row_h, (list, tuple)) else row_h
        xs = []
        x = 0
        widths = []
        while x < w:
            bw = int(rng.choice(widths_choices))
            if w - x - bw < min(widths_choices) and w - x - bw != 0:
                bw = w - x
            widths.append(bw)
            x += bw
        off = int(rng.integers(0, w)) if offset_mode == "random" else (w // 4 * (r % 2) * 2 // 2)
        acc = 0
        for bw in widths:
            xs.append((acc + off) % w)
            acc += bw
        rows.append((y, y + rh, sorted(xs), widths))
        y += rh
        r += 1
    return rows


def layout_blocks(rng, w, h, rows, widths, min_w):
    """Periodic running-bond layout. rows: list of row heights. Returns list of (x0, y0, bw, bh)."""
    blocks = []
    y = 0
    prev_off = 0
    for r, rh in enumerate(rows):
        off = (prev_off + int(rng.integers(min_w // 2, w - min_w // 2))) % w if r else int(rng.integers(0, w))
        prev_off = off
        x = 0
        ws = []
        while x < w:
            bw = int(rng.choice(widths))
            if w - x - bw < min_w:
                bw = w - x
            ws.append(bw)
            x += bw
        x = off
        for bw in ws:
            blocks.append((x, y, bw, rh))
            x += bw
        y += rh
    return blocks


def draw_block(cv, rng, x0, y0, bw, bh, name, t, mortar_col, chip=0.35, pits=True, noise=None, hi_top=True):
    """One masonry block with a 1px mortar line on its top and left; bevelled face lit from the upper-left."""
    h, w = cv.shape[:2]
    n = len(RA[name])
    for yy in range(bh):
        for xx in range(bw):
            X, Y = x0 + xx, y0 + yy
            if yy == 0 or xx == 0:
                wput(cv, X, Y, mortar_col)
                continue
            k = t
            if noise is not None:
                nv = noise[Y % h, X % w]
                if nv > 0.7:
                    k = t + 1
                elif nv < 0.25:
                    k = t - 1
            if yy == 1 or xx == 1:
                k = t + 1 if (yy == 1 and hi_top) or xx == 1 else k
            if yy == bh - 1 or xx == bw - 1:
                k = t - 1
            if yy == 1 and xx == 1:
                k = t + 1
            if yy == bh - 1 and xx == 1:
                k = t
            if yy == 1 and xx == bw - 1:
                k = t
            wput(cv, X, Y, RA[name][int(np.clip(k, 0, n - 1))])
    # chipped corners
    for (cx, cy, dx, dy) in ((1, 1, 1, 1), (bw - 1, 1, -1, 1), (1, bh - 1, 1, -1), (bw - 1, bh - 1, -1, -1)):
        if rng.random() < chip:
            wput(cv, x0 + cx, y0 + cy, mortar_col)
            if rng.random() < 0.5:
                wput(cv, x0 + cx + dx, y0 + cy, RA[name][max(0, t - 1)] if dx > 0 else RA[name][min(n - 1, t + 1)])
    if pits:
        for _ in range(int(rng.integers(0, 3))):
            px = x0 + int(rng.integers(2, max(3, bw - 2)))
            py = y0 + int(rng.integers(2, max(3, bh - 2)))
            wput(cv, px, py, RA[name][max(0, t - 2)])
            wput(cv, px + 1, py + 1, RA[name][min(n - 1, t + 1)])


def tex_stone_bricks():
    rng = rng_for("stone_bricks", 11)
    w = h = 48
    cv = canvas(w, h)
    noise = fbm(w, h, 8, 2, rng)
    blocks = layout_blocks(rng, w, h, [8, 8, 8, 8, 8, 8], [12, 16, 16, 20], 10)
    for (x0, y0, bw, bh) in blocks:
        t = int(rng.choice([2, 3, 3, 3]))
        draw_block(cv, rng, x0, y0, bw, bh, "stone", t, RA["stone"][0], noise=noise)
    # hairline cracks running across a couple of bricks
    for _ in range(2):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        ang = rng.uniform(0.6, 1.4)
        for i in range(int(rng.integers(4, 7))):
            ang += rng.uniform(-0.6, 0.6)
            x += math.cos(ang)
            y += abs(math.sin(ang))
            wput(cv, x, y, RA["stone"][1])
            wput(cv, x + 1, y, RA["stone"][4]) if rng.random() < 0.3 else None
    return cv


def moss_patch(cv, mask, rng, wrap=True, name="moss", shadow_on=None):
    """Render a boolean moss mask as soft shaded clumps (lit top-left, dark lower lip, cast shadow)."""
    h, w = mask.shape
    # thickness = distance into the patch (periodic)
    d = np.zeros((h, w))
    m = mask.copy()
    for _ in range(4):
        d += m
        m = erode(m, 1, wrap=wrap)
    hm = d / 4.0 + 0.5 * fbm(w, h, 12, 2, rng) * mask
    sh = lambert(hm * 2.2, 1.0, wrap=wrap)
    k = levels(sh, [0.42, 0.62, 0.8])
    lut = np.array([1, 2, 3, 4])
    cv[mask] = RA[name][lut[k[mask]]]
    # dark lower lip and cast shadow onto the stone below/right
    lip = mask & ~shift(mask, 0, -1, wrap=wrap)
    cv[lip] = RA[name][0]
    cast = shift(mask, 1, 1, wrap=wrap) & ~mask
    if shadow_on is not None:
        cv[cast] = shadow_on
    # bright moss tips on the upper edge
    tips = mask & ~shift(mask, 0, 1, wrap=wrap) & (rng.random((h, w)) < 0.5)
    cv[tips] = RA[name][4]
    sp = mask & (rng.random((h, w)) < 0.05) & (k >= 2)
    cv[sp] = RA[name][5]


def tex_mossy_stone():
    rng = rng_for("mossy_stone", 13)
    w = h = 48
    cv = canvas(w, h)
    noise = fbm(w, h, 6, 2, rng)
    blocks = layout_blocks(rng, w, h, [12, 12, 12, 12], [16, 20, 24, 28], 14)
    bid = np.zeros((h, w), int)
    for i, (x0, y0, bw, bh) in enumerate(blocks):
        t = int(rng.choice([2, 2, 3]))
        draw_block(cv, rng, x0, y0, bw, bh, "stone", t, RA["stone"][0], chip=0.7, noise=noise)
        for yy in range(bh):
            for xx in range(bw):
                bid[(y0 + yy) % h, (x0 + xx) % w] = i
    mort = (bid != np.roll(bid, 1, 1)) | (bid != np.roll(bid, 1, 0))
    # erosion: worn pits along the joints
    worn = dilate(mort, 1, wrap=True) & (fbm(w, h, 10, 2, rng) > 0.66) & ~mort
    cv[worn] = RA["stone"][1]
    # moss: grows along horizontal joints (ledges) and in a few creeping patches
    hj = (bid != np.roll(bid, 1, 0))
    near_h = np.zeros((h, w))
    m = hj.copy()
    for i in range(5):
        near_h += m
        m = dilate(m, 1, diag=False, wrap=True)
    near_h /= 5.0
    vj = (bid != np.roll(bid, 1, 1))
    near_v = dilate(vj, 1, diag=False, wrap=True)
    sp = spectral(w, h, rng, 2.0, 5.5, beta=0.6)
    # patch-driven: joints only bias where moss grows, so it doesn't line every joint
    moss = (near_h * 0.45 + sp * 0.85 > 0.72) | ((sp > 0.68) & near_v)
    moss = dilate(erode(moss, 1, wrap=True), 1, wrap=True) | (moss & (sp > 0.8))
    moss_patch(cv, moss, rng, shadow_on=RA["stone"][1])
    # creeping tendrils: thin moss strands running down from patches
    for (px, py) in poisson(w, h, 9, rng):
        if not moss[int(py), int(px)]:
            continue
        x, y = int(px), int(py)
        for i in range(int(rng.integers(2, 6))):
            y += 1
            x += int(rng.choice([0, 0, 1, -1]))
            if moss[y % h, x % w]:
                continue
            wput(cv, x, y, RA["moss"][3] if i % 2 == 0 else RA["moss"][2])
    return cv


def tex_plaster_timber():
    """Cream plaster with a dark timber post (left edge) and beam (top edge) -> tiles into half-timbering."""
    rng = rng_for("plaster_timber", 17)
    w = h = 48
    pw, bh = 6, 6  # post width, beam height (25 cm timbers)
    cv = canvas(w, h, RA["cloth_cream"][4])
    xs, ys = grid(w, h)
    b4 = bayer(w, h, 4) + 0.5
    # soft grime toward the bottom of the panel and next to the timbers (sparse ordered dither)
    grime = np.clip((ys - 30) / 18.0, 0, 1) * 0.35 + np.clip(1 - (xs - pw) / 6.0, 0, 1) * 0.25 + \
        np.clip(1 - (ys - bh) / 6.0, 0, 1) * 0.3
    grime *= 0.7 + 0.6 * fbm(w, h, 3, 2, rng)
    cv[b4 < grime * 0.8] = RA["cloth_cream"][3]
    # trowel marks: short horizontal-ish smudges, lighter (fresh) and darker (dirt)
    for (px, py) in poisson(w, h, 6.0, rng):
        if px < pw + 1 or py < bh + 1:
            continue
        ln = int(rng.integers(2, 5))
        dark = rng.random() < 0.55
        col = RA["cloth_cream"][3] if dark else RA["cloth_cream"][5]
        slope = rng.choice([0, 0, 1])
        for i in range(ln):
            x = px + i
            y = py + (i // 2 if slope else 0)
            if pw + 1 <= x < w and bh + 1 <= y < h:
                wput(cv, x, y, col)
    # hairline cracks from the frame corner
    x, y = pw + 1.0, bh + 1.0
    ang = 0.75
    for i in range(7):
        ang += rng.uniform(-0.4, 0.4)
        x += math.cos(ang)
        y += math.sin(ang)
        wput(cv, x, y, RA["cloth_cream"][2])
    x, y = w - 4.0, h - 1.0
    for i in range(5):
        x -= rng.uniform(0.2, 1.0)
        y -= 1
        wput(cv, x, y, RA["cloth_cream"][2])
    # cast shadows: below the beam and right of the post
    for x in range(pw, w):
        wput(cv, x, bh, RA["cloth_cream"][2])
        if x % 2 == 0:
            wput(cv, x, bh + 1, RA["cloth_cream"][3])
    for y in range(bh, h):
        wput(cv, pw, y, RA["cloth_cream"][2])
        if y % 2 == 1:
            wput(cv, pw + 1, y, RA["cloth_cream"][3])
    # timber (dark): body wood 1-2 with continuous grain streaks, lit top/left bevel, dark bottom/right
    post = xs < pw
    beam = ys < bh
    cv[beam] = RA["wood"][2]
    cv[post] = RA["wood"][2]

    def streaks(length_axis_len, lanes, horizontal):
        for lane in lanes:
            pos = int(rng.integers(0, length_axis_len))
            while pos < length_axis_len + 40:
                seg = int(rng.integers(5, 14))
                gap = int(rng.integers(2, 7))
                col = RA["wood"][1] if rng.random() < 0.75 else RA["wood"][3]
                for i in range(seg):
                    p = (pos + i) % length_axis_len
                    if horizontal:
                        cv[lane, p] = col
                    else:
                        cv[p, lane] = col
                pos += seg + gap

    streaks(w, [2, 3, 4], True)
    streaks(h, [1, 2, 3, 4], False)
    cv[post & (xs == 0)] = RA["wood"][3]
    cv[post & (xs == pw - 1)] = RA["wood"][0]
    cv[beam & (ys == 0)] = RA["wood"][3]
    cv[beam & (ys == 1) & (xs >= pw)] = RA["wood"][2]
    cv[beam & (ys == bh - 1)] = RA["wood"][0]
    # the post runs in front of the beam: redraw the post through the joint
    j = post & beam
    cv[j] = RA["wood"][2]
    cv[j & (xs == 0)] = RA["wood"][3]
    cv[j & (xs == pw - 1)] = RA["wood"][0]
    cv[0, :pw] = RA["wood"][3]
    cv[bh - 1, :pw] = RA["wood"][1]
    # wooden peg at the joint + knots
    cv[2, 2] = RA["wood"][4]
    cv[2, 3] = RA["wood"][3]
    cv[3, 2] = RA["wood"][3]
    cv[3, 3] = RA["wood"][0]
    for (kx, ky) in ((2, 21), (3, 38)):
        cv[ky, kx] = RA["wood"][0]
        cv[ky - 1, kx] = RA["wood"][1]
        cv[ky + 1, kx] = RA["wood"][3]
    for kx in (19, 35):
        cv[3, kx] = RA["wood"][0]
        cv[3, kx + 1] = RA["wood"][1]
        cv[4, kx] = RA["wood"][3]
    return cv


def plank_tex(name, seed, lo, mid, hi, rows=(8, 8, 8, 8, 8, 8), knots=3, nails=True, ramp_name="wood"):
    """Horizontal planks: per-board tone, long grain streaks, butt joints with nails, ring knots."""
    rng = rng_for(name, seed)
    w = h = 48
    R = RA[ramp_name]
    n = len(R)
    cv = canvas(w, h)
    y0 = 0
    for r, rh in enumerate(rows):
        nj = int(rng.integers(1, 3))
        while True:
            joints = sorted(int(v) for v in rng.choice(np.arange(0, w, 3), size=nj, replace=False))
            if nj == 1 or (16 <= joints[1] - joints[0] <= w - 16):
                break
        segs = list(zip(joints, joints[1:] + [joints[0] + w]))
        for (sx, ex) in segs:
            t = int(rng.choice([mid, mid, mid, hi if hi > mid else mid, lo + 1 if lo + 1 < mid else mid]))
            # board body
            for y in range(y0, y0 + rh):
                for x in range(sx, ex):
                    cv[y % h, x % w] = R[t]
            # grain streaks (darker) and sheen streaks (lighter)
            for lane in range(y0 + 1, y0 + rh - 1):
                pos = sx + int(rng.integers(-6, 4))
                while pos < ex:
                    seg = int(rng.integers(4, 16))
                    gap = int(rng.integers(3, 12))
                    dark = rng.random() < 0.7
                    col = R[max(0, t - 1)] if dark else R[min(n - 1, t + 1)]
                    for i in range(seg):
                        xx = pos + i
                        if sx < xx < ex:
                            cv[lane % h, xx % w] = col
                    pos += seg + gap
            # edges: lit top lip, dark gap at the bottom, joint lines
            for x in range(sx, ex):
                cv[y0 % h, x % w] = R[min(n - 1, t + 1)]
                cv[(y0 + rh - 1) % h, x % w] = R[0]
            for y in range(y0, y0 + rh - 1):
                cv[y % h, sx % w] = R[0]
                cv[y % h, (sx + 1) % w] = R[min(n - 1, t + 1)] if y > y0 else cv[y % h, (sx + 1) % w]
                cv[y % h, (ex - 1) % w] = R[max(0, t - 1)] if y > y0 else cv[y % h, (ex - 1) % w]
            if nails:
                for ny in (y0 + 2, y0 + rh - 3):
                    for nx in (sx + 2, ex - 2):
                        cv[ny % h, nx % w] = RA["metal"][1]
                        cv[(ny - 1) % h, nx % w] = RA["metal"][3]
        y0 += rh
    # ring knots
    for _ in range(knots):
        kx, ky = int(rng.integers(0, w)), int(rng.integers(0, h))
        row_top = sum(rows[:max(0, [i for i in range(len(rows)) if sum(rows[:i + 1]) > ky][0])])
        ky = row_top + rows[0] // 2
        for yy in range(-1, 2):
            for xx in range(-3, 4):
                d = (xx / 3.2) ** 2 + (yy / 1.3) ** 2
                if d <= 1:
                    cur = R[max(0, lo - 1)] if d > 0.45 else R[lo]
                    cv[(ky + yy) % h, (kx + xx) % w] = cur
        cv[ky % h, kx % w] = R[0]
        cv[(ky - 1) % h, (kx - 1) % w] = R[min(n - 1, hi)]
    return cv


def tex_wood_planks():
    return plank_tex("wood_planks", 19, 2, 3, 4)


def tex_wood_dark():
    return plank_tex("wood_dark", 23, 1, 2, 3, rows=(6, 6, 6, 6, 6, 6, 6, 6), knots=2, nails=False)


def tex_thatch_roof():
    """Straw thatch courses: vertical strands, shadowed tops, ragged lit fringes overlapping the course below."""
    rng = rng_for("thatch_roof", 29)
    w = h = 48
    row_h = 12
    # straw ladder: golden mustard in the shadows/mids, muted sand in the lights
    R = np.array([RA["cloth_mustard"][0], RA["cloth_mustard"][1], RA["cloth_mustard"][2], RA["sand"][2],
                  RA["sand"][3], RA["sand"][4]], np.uint8)
    cv = canvas(w, h)
    grad = [1, 1, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4]
    fr_all = []
    for r in range(h // row_h):
        y0 = r * row_h
        # strand tones persist for 1-3 columns
        strand = np.zeros(w, int)
        x = 0
        while x < w:
            run = int(rng.integers(1, 4))
            val = int(rng.choice([-1, 0, 0, 1]))
            strand[x:x + run] = val
            x += run
        lean = int(rng.choice([-1, 1]))
        # explicit strand separation lines (dark) and glossy straws (light)
        lines = np.zeros(w, int)
        x = int(rng.integers(0, 3))
        while x < w:
            lines[x % w] = -2 if rng.random() < 0.75 else 2
            x += int(rng.integers(2, 5))
        for ly in range(row_h):
            for x in range(w):
                sx = (x + (lean * ly) // 4) % w
                k = grad[ly] + strand[sx]
                if lines[sx] == -2 and ly >= 2:
                    k = grad[ly] - 1
                elif lines[sx] == 2 and ly >= 4:
                    k = grad[ly] + 1
                cv[(y0 + ly) % h, x] = R[int(np.clip(k, 1, 5))]
        # fringe lengths: bundles of similar length
        fr = np.zeros(w, int)
        x = int(rng.integers(0, 3))
        while x < w + 3:
            run = int(rng.integers(2, 5))
            L = int(rng.choice([1, 2, 2, 3]))
            for i in range(run):
                fr[(x + i) % w] = max(0, L - (1 if i == run - 1 else 0))
            x += run
        fr_all.append((y0, fr, strand, lean))
    # fringes on top of the next course
    for (y0, fr, strand, lean) in fr_all:
        yb = y0 + row_h
        for x in range(w):
            f = fr[x]
            for i in range(f):
                k = 4 + (1 if (i == f - 1 and strand[x] >= 0) else 0) - (1 if strand[x] < 0 else 0)
                cv[(yb + i) % h, x] = R[int(np.clip(k, 2, 5))]
            cv[(yb + f) % h, x] = R[0] if f >= 2 else R[1]
            if f >= 1:
                cv[(yb + f + 1) % h, x] = R[1] if rng.random() < 0.6 else cv[(yb + f + 1) % h, x]
    # occasional weathered (grey) straws and sun glints
    for (px, py) in poisson(w, h, 6, rng):
        x, y = int(px), int(py)
        if rng.random() < 0.35:
            for i in range(int(rng.integers(2, 4))):
                wput(cv, x, y + i, RA["sand"][4] if i == 0 else RA["sand"][3])
    return cv


def shingles(name, seed, ramp_name, base, tile_w=8, row_h=8, shape="round", bulge=2.0, tone_var=0.25,
             moss=0.0, lichen_ramp="moss"):
    """Overlapping roof courses. Each course's bottom edge (rounded or straight) lies on top of the
    course below and casts a shadow onto it. Ownership is computed per pixel so it tiles seamlessly."""
    rng = rng_for(name, seed)
    w = h = 48
    R = RA[ramp_name]
    n = len(R)
    rows = h // row_h
    cols = w // tile_w
    offs = [(r % 2) * (tile_w // 2) for r in range(rows)]
    tone = rng.choice([0, 0, 0, 0, 0, 1, -1], size=(rows, cols + 1)) if tone_var else np.zeros((rows, cols + 1), int)
    ext = rng.choice([0, 0, 1], size=(rows, cols + 1)) if shape == "flat" else np.zeros((rows, cols + 1), int)
    chip = rng.random((rows, cols + 1)) < (0.25 if shape == "flat" else 0.0)

    def tile_at(r, x):
        r %= rows
        lx = (x - offs[r]) % w
        c = lx // tile_w
        u = (lx % tile_w + 0.5) / tile_w
        return r, c, lx % tile_w, u

    def bottom_bulge(r, c, u, lx):
        if shape == "round":
            return bulge * math.sqrt(max(0.0, 1 - (2 * u - 1) ** 2)) - 0.35
        b = float(ext[r, c])
        if chip[r, c] and lx == tile_w - 1:
            b -= 1
        return b

    cv = canvas(w, h)
    for y in range(h):
        for x in range(w):
            r = y // row_h
            ly = y - r * row_h
            # does the course above reach down here with its bottom edge?
            ra, ca, lxa, ua = tile_at(r - 1, x)
            ba = bottom_bulge(ra, ca, ua, lxa)
            if ly < ba:
                rr, cc, lx, u = ra, ca, lxa, ua
                ly_t = ly + row_h  # local y within that tile's course
                bb = ba + row_h
            else:
                rr, cc, lx, u = tile_at(r, x)
                ly_t = ly
                bb = bottom_bulge(rr, cc, u, lx) + row_h
            t = base + int(tone[rr, cc])
            # curved surface: lit left, shaded right (flat slates: subtle streaks only)
            if shape == "round":
                k = t + (1 if u < 0.38 else 0) - (1 if u > 0.8 else 0)
            else:
                k = t - (1 if ((x * 7 + rr * 3) % 11 == 0 and ly_t > 3) else 0)
            # cast shadow from the course above (first rows of the visible part)
            rup, cup, lxu, uu = tile_at(rr - 1, x)
            bu = bottom_bulge(rup, cup, uu, lxu)
            if ly_t < bu + 1.0:
                k = t - 2
            elif ly_t < bu + 2.0:
                k = min(k, t - 1)
            # lit bottom rim
            if bb - 1.0 <= ly_t < bb:
                k = t + 1 if u < 0.7 else t
            # gap to the neighbour tile
            if lx == tile_w - 1:
                k = t - 2 if ly_t < bb - 1 else t - 1
            if lx == 0 and ly_t >= bu + 2:
                k = max(k, t + 1) if shape == "round" else k
            cv[y, x] = R[int(np.clip(k, 0, n - 1))]
    if moss:
        mm = (spectral(w, h, rng, 2.0, 6.0) > 1 - moss)
        sp = mm & (rng.random((h, w)) < 0.2)
        cv[sp] = RA[lichen_ramp][2]
        cv[sp & (rng.random((h, w)) < 0.4)] = RA[lichen_ramp][3]
    return cv


def tex_roof_tiles_red():
    return shingles("roof_tiles_red", 31, "fur_russet", 3, tile_w=8, row_h=8, shape="round", bulge=2.2, moss=0.12)


def tex_roof_tiles_slate():
    return shingles("roof_tiles_slate", 37, "stone", 2, tile_w=12, row_h=8, shape="flat", moss=0.08,
                    lichen_ramp="moss")


# --------------------------------------------------------------------------
# natural rock / bark / water
# --------------------------------------------------------------------------


def tex_bark():
    """Vertical bark: long interlocking ridges, deep furrows, fibrous streaks; lit from the left."""
    rng = rng_for("bark", 41)
    w = h = 48
    pts = poisson(w, h, 6.5, rng)
    ids, d1, d2 = voronoi(w, h, pts, sx=1.0, sy=0.22)
    gap = d2 - d1
    ridge = np.clip(gap / 2.4, 0, 1) ** 0.5
    fib = fbm(w, h, 16, 1, rng, cells_y=2)
    hm = ridge * 1.6 + 0.35 * fib
    sh = lambert(hm * 2.2, 1.0, light=(-1.0, -0.3, 0.9))
    tone = np.array([rng.uniform(-0.06, 0.06) for _ in pts])[ids]
    v = np.clip(sh + tone, 0, 1)
    k = levels(v, [0.3, 0.52, 0.74])
    lut = np.array([1, 2, 3, 4])
    cv = canvas(w, h)
    cv[:] = RA["bark"][lut[k]]
    furrow = gap < 0.75
    cv[furrow] = RA["bark"][0]
    cv[(gap < 1.3) & ~furrow & (k <= 1)] = RA["bark"][1]
    # small horizontal checks across some ridges
    for (px, py) in poisson(w, h, 9, rng):
        x, y = int(px), int(py)
        if gap[y % h, x % w] > 2.0:
            for i in range(int(rng.integers(2, 4))):
                wput(cv, x + i, y, RA["bark"][1])
            wput(cv, x, y + 1, RA["bark"][4])
    # a few moss flecks in the furrows
    lm = furrow & (spectral(w, h, rng, 1.0, 3.0) > 0.8) & (rng.random((h, w)) < 0.4)
    cv[lm] = RA["moss"][2]
    return cv


def crack_walk(cv, rng, x, y, ang, steps, dark, lip=None, wrap=True, jitter=0.5):
    for i in range(steps):
        ang += rng.uniform(-jitter, jitter)
        x += math.cos(ang)
        y += math.sin(ang)
        wput(cv, x, y, dark)
        if lip is not None and rng.random() < 0.7:
            wput(cv, x + 1, y + 1, lip)
    return x, y


def warped_voronoi(w, h, pts, rng, amp=3.0, cells=3, sx=1.0, sy=1.0):
    """Periodic Voronoi on domain-warped coordinates -> irregular, still seamless cell borders."""
    xs, ys = grid(w, h)
    wx = (fbm(w, h, cells, 2, rng) - 0.5) * 2 * amp
    wy = (fbm(w, h, cells, 2, rng) - 0.5) * 2 * amp
    P = np.asarray(pts, float)
    dx = wrap_delta(xs[None] + 0.5 + wx[None] - P[:, 0, None, None], w)
    dy = wrap_delta(ys[None] + 0.5 + wy[None] - P[:, 1, None, None], h)
    d = np.sqrt((dx * sx) ** 2 + (dy * sy) ** 2)
    order = np.argsort(d, axis=0)
    ids = order[0]
    d1 = np.take_along_axis(d, order[0:1], 0)[0]
    d2 = np.take_along_axis(d, order[1:2], 0)[0]
    return ids, d1, d2


def facet_shade(ids, n_cells, rng, tilt=0.9, base_field=None, weight=0.35):
    L = np.array([-1.0, -1.0, 1.25])
    L = L / np.linalg.norm(L)
    vals = []
    for _ in range(n_cells):
        a, b = rng.uniform(-tilt, tilt, 2)
        nrm = np.array([a, b, 1.0])
        nrm /= np.linalg.norm(nrm)
        vals.append(float(nrm @ L))
    v = np.array(vals)[ids]
    v = norm01(v)
    if base_field is not None:
        v = (1 - weight) * v + weight * base_field
    return v


def facet_edges(cv, ids, k, name, lut, wrap=True):
    """Bevel/crease where facets meet: lighter facet gets a lit lip, darker facet a dark crease."""
    h, w = ids.shape
    up = np.roll(ids, 1, 0)
    left = np.roll(ids, 1, 1)
    kup = np.roll(k, 1, 0)
    kleft = np.roll(k, 1, 1)
    bnd = (ids != up) | (ids != left)
    other = np.where(ids != up, kup, kleft)
    lit = bnd & (k > other)
    dark = bnd & (k <= other)
    n = len(RA[name])
    cv[lit] = RA[name][np.clip(lut[k[lit]] + 1, 0, n - 1)]
    cv[dark] = RA[name][np.clip(lut[k[dark]] - 1, 0, n - 1)]


def tex_rock():
    """Natural boulder rock: flat-shaded irregular facets, bevels and creases, a few cracks, lichen."""
    rng = rng_for("rock", 43)
    w = h = 48
    pts = poisson(w, h, 10.0, rng)
    ids, d1, d2 = warped_voronoi(w, h, pts, rng, amp=3.5, cells=3)
    base = spectral(w, h, rng, 1.0, 3.0)
    v = facet_shade(ids, len(pts), rng, base_field=base, weight=0.45)
    k = levels(v, [0.15, 0.5, 0.85])
    lut = np.array([1, 2, 3, 4])
    cv = canvas(w, h)
    cv[:] = RA["stone"][lut[k]]
    # within-facet mottling (clustered, no dither)
    mot = fbm(w, h, 12, 2, rng)
    lo = (mot < 0.25) & (k > 0)
    hi = (mot > 0.8) & (k < 3)
    cv[lo] = RA["stone"][lut[k[lo]] - 1]
    cv[hi] = RA["stone"][lut[k[hi]] + 1]
    facet_edges(cv, ids, k, "stone", lut)
    # open-ended cracks with a lit lower lip
    for _ in range(2):
        crack_walk(cv, rng, rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0, math.tau),
                   int(rng.integers(6, 11)), RA["stone"][0], RA["stone"][3])
    # lichen: small soft patches
    lich = spectral(w, h, rng, 2.0, 6.0) > 0.86
    lsp = lich & (rng.random((h, w)) < 0.5)
    cv[lsp] = RA["moss"][2]
    cv[lsp & (rng.random((h, w)) < 0.4)] = RA["moss"][3]
    return cv


def tex_cliff_rock():
    """Layered cliff face: wavy strata of varied thickness, lit ledge tops, dark undercuts,
    vertical fractures splitting each layer into blocks, moss clumps on some ledges."""
    rng = rng_for("cliff_rock", 47)
    w = h = 48
    xs, ys = grid(w, h)
    thick = [6, 11, 7, 13, 5, 6]
    bounds = np.cumsum([0] + thick[:-1])
    nb = len(bounds)
    wav = np.zeros((nb, w))
    for i in range(nb):
        ph = rng.uniform(0, math.tau)
        a = rng.uniform(0.5, 1.3)
        f1 = int(rng.integers(1, 3))
        wav[i] = bounds[i] + a * np.sin(xs[0] / w * math.tau * f1 + ph) + 0.6 * np.sin(xs[0] / w * math.tau * 3 + ph * 1.7)
    layer = np.zeros((h, w), int)
    local = np.zeros((h, w))
    th = np.zeros((h, w))
    for x in range(w):
        bs = list(wav[:, x]) + [wav[0, x] + h]
        for y in range(h):
            yy = y if y >= bs[0] else y + h
            for i in range(nb):
                if bs[i] <= yy < bs[i + 1]:
                    layer[y, x] = i
                    local[y, x] = yy - bs[i]
                    th[y, x] = bs[i + 1] - bs[i]
                    break
    # vertical fractures per layer -> block ids
    block = np.zeros((h, w), int)
    frac_x = {}
    for i in range(nb):
        nfr = int(rng.integers(2, 4))
        cuts = sorted(int(c) for c in rng.choice(np.arange(0, w), size=nfr, replace=False))
        frac_x[i] = cuts
    tones = {}
    for y in range(h):
        for x in range(w):
            i = layer[y, x]
            cuts = frac_x[i]
            j = sum(1 for c in cuts if x >= c)
            j = j % len(cuts)
            block[y, x] = i * 10 + j
            tones.setdefault(i * 10 + j, rng.uniform(-0.12, 0.12))
    t = local / np.maximum(th, 1)
    hm = np.sin(np.clip(t, 0, 1) * math.pi) ** 0.6 * 1.2 + 0.45 * fbm(w, h, 6, 2, rng, cells_y=3)
    sh = lambert(hm * 2.4, 1.0)
    tone = np.vectorize(lambda b: tones[b])(block)
    v = np.clip(sh + tone, 0, 1)
    k = levels(v, [0.3, 0.5, 0.7, 0.88])
    lut = np.array([1, 2, 3, 3, 4])
    cv = canvas(w, h)
    cv[:] = RA["stone_warm"][lut[k]]
    top = local < 1.0
    cv[top] = RA["stone_warm"][4]
    cv[top & (fbm(w, h, 8, 1, rng) > 0.6)] = RA["stone_warm"][5]
    under = (th - local) <= 1.0
    cv[under] = RA["stone_warm"][0]
    under2 = ((th - local) <= 2.0) & ~under
    cv[under2] = RA["stone_warm"][1]
    # fractures: dark groove + lit right wall, spanning the layer
    for i in range(nb):
        for c in frac_x[i]:
            x = c
            for y in range(h):
                if layer[y, x % w] != i or top[y, x % w]:
                    continue
                if rng.random() < 0.18:
                    x += int(rng.choice([-1, 1]))
                if not under[y, x % w]:
                    cv[y, x % w] = RA["stone_warm"][0]
                    cv[y, (x + 1) % w] = RA["stone_warm"][3] if local[y, (x + 1) % w] > 1 else cv[y, (x + 1) % w]
    # moss clumps on a few ledges
    ledge_m = np.zeros((h, w), bool)
    sp = spectral(w, h, rng, 1.5, 5.0)
    for y in range(h):
        for x in range(w):
            if top[y, x] and sp[y, x] > 0.68:
                for dy in range(0, 2 + (1 if sp[y, x] > 0.8 else 0)):
                    ledge_m[(y - 1 + dy) % h, x] = True
    moss_patch(cv, ledge_m, rng, shadow_on=RA["stone_warm"][1])
    return cv


def tex_water_base(base_idx=2):
    """Deep teal water: calm base, wavy dashed ripple crests (light) and troughs (dark), sparse glints."""
    rng = rng_for("water_base", 53)
    w = h = 64
    xs, ys = grid(w, h)
    base = spectral(w, h, rng, 1.0, 3.0, beta=0.8)
    b4 = bayer(w, h, 4) + 0.5
    cv = canvas(w, h, RA["water"][base_idx])
    phase = spectral(w, h, rng, 1.0, 3.0, beta=0.6) * 2.4 + spectral(w, h, rng, 3.0, 6.0, beta=0.6) * 0.5
    wave = np.sin(math.tau * (ys / h * 7 + xs / w * 1) + phase * math.tau * 0.5)
    dash = spectral(w, h, rng, 4.0, 9.0, beta=0.3, sx=1.0, sy=0.5) > 0.45
    crest = (wave > 0.86) & dash
    # keep crests thin: 1px tall
    crest &= ~shift(crest, 0, 1, wrap=True)
    trough = (wave < -0.9) & (spectral(w, h, rng, 4.0, 9.0, beta=0.3) > 0.55)
    trough &= ~shift(trough, 0, 1, wrap=True)
    cv[trough] = RA["water"][base_idx - 1]
    cv[crest] = RA["water"][base_idx + 1]
    lit = crest & (base > 0.4) & (spectral(w, h, rng, 3.0, 7.0) > 0.55)
    cv[lit] = RA["water"][base_idx + 2]
    for (px, py) in poisson(w, h, 15, rng):
        x, y = int(px), int(py)
        if crest[y, x]:
            wput(cv, x, y, RA["water"][min(6, base_idx + 3)])
    return cv


TEXTURES = {
    "grass_a": tex_grass_a,
    "grass_b": tex_grass_b,
    "grass_dark": tex_grass_dark,
    "dirt_path": tex_dirt_path,
    "cobble": tex_cobble,
    "sand_arena": tex_sand_arena,
    "stone_bricks": tex_stone_bricks,
    "mossy_stone": tex_mossy_stone,
    "plaster_timber": tex_plaster_timber,
    "wood_planks": tex_wood_planks,
    "wood_dark": tex_wood_dark,
    "thatch_roof": tex_thatch_roof,
    "roof_tiles_red": tex_roof_tiles_red,
    "roof_tiles_slate": tex_roof_tiles_slate,
    "bark": tex_bark,
    "rock": tex_rock,
    "cliff_rock": tex_cliff_rock,
    "water_base": tex_water_base,
    "flower_meadow": tex_flower_meadow,
}


def build(only=None, preview=True):
    out = []
    items = []
    for name, fn in TEXTURES.items():
        if only and name not in only:
            continue
        cv = fn()
        assert (cv[..., 3] == 255).all(), name
        p = save_png(cv, os.path.join(OUT, name + ".png"))
        out.append(p)
        if preview:
            tile_preview(cv, "tex_" + name, 3, 4)
            items.append((name, np.tile(cv, (2, 2, 1))))
    if preview and items:
        grid_preview(items, "textures_all" if not only else "textures_sel", scale=2, cols=5)
    return out


if __name__ == "__main__":
    import sys
    build(sys.argv[1:] or None)
