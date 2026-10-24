"""Group D - VFX sprite sheets (SheetBuilder; partial alpha allowed).

Effects are painted as float fields (intensity 0..1, alpha 0..1) and mapped through
palette gradients, so every visible pixel is a master-palette colour. Alpha is quantised
to quarter steps for a crisp pixel-art look. Layers are composited back to front.

BILLBOARD effects are drawn as seen by the camera. GROUND effects are drawn top-down,
centred in the frame, with the effect's forward direction pointing RIGHT (+X).
"""

from __future__ import annotations

import math
import os

import numpy as np

from kit import (OUT_FX, PREVIEW_DIR, RA, SheetBuilder, bezier, canvas, clear_border, contact_sheet, fbm, grid,
                 grid_preview, norm01, over, poly_mask, rng_for, shift, spectral, to_image)

# --------------------------------------------------------------------------
# gradients (dark -> bright), all master-palette colours
# --------------------------------------------------------------------------

G = {
    "fire": [RA["ember"][i] for i in (1, 2, 3, 4, 5, 6)],
    "fire_hot": [RA["ember"][i] for i in (3, 4, 5, 6)] + [RA["cloth_cream"][5]],
    "spark": [RA["ember"][3], RA["gold"][3], RA["gold"][4], RA["gold"][5], RA["ember"][6], RA["cloth_cream"][5]],
    "white": [RA["gold"][4], RA["ember"][6], RA["cloth_cream"][5], RA["aether"][6]],
    "whitegold": [RA["gold"][3], RA["gold"][4], RA["gold"][5], RA["ember"][6], RA["cloth_cream"][5]],
    "dust": [RA["stone_warm"][i] for i in (1, 2, 3, 4, 5)],
    "dirt": [RA["earth"][i] for i in (1, 2, 3, 4, 5)],
    "stone": [RA["stone"][i] for i in (0, 1, 2, 3, 4, 5)],
    "smoke": [RA["soot"][1], RA["soot"][2], RA["soot"][3], RA["stone"][2], RA["stone"][3]],
    "aether": [RA["aether"][i] for i in (2, 3, 4, 5, 6)],
    "cyan": [RA["water"][3], RA["water"][4], RA["water"][5], RA["ui_stamina"][4], RA["water"][6],
             RA["cloth_cream"][5]],
    "moss_glow": [RA["glow_moss"][i] for i in (1, 2, 3, 4, 5)],
    "sigil": [RA["sigil"][i] for i in (1, 2, 3, 4, 5)] + [RA["cloth_cream"][5]],
    "heart": [RA["sigil"][2], RA["sigil"][3], RA["sigil"][4], RA["sigil"][5], RA["cloth_cream"][5]],
    "soot": [RA["ink"][0], RA["soot"][0], RA["soot"][1], RA["soot"][2], RA["soot"][3]],
}

ALPHA_STEPS = 4  # alpha quantised to 0, .25, .5, .75, 1


def qalpha(a, steps=ALPHA_STEPS):
    return np.round(np.clip(a, 0, 1) * steps) / steps


def colorize(inten, alph, grad, steps=ALPHA_STEPS):
    """Map intensity (0..1) to gradient colour; alpha quantised. Returns uint8 RGBA."""
    g = np.array(grad, np.uint8)
    n = len(g)
    idx = np.clip(np.floor(np.clip(inten, 0, 0.9999) * n), 0, n - 1).astype(int)
    out = g[idx].copy()
    a = qalpha(alph, steps)
    out[..., 3] = (a * 255).astype(np.uint8)
    out[a <= 0] = 0
    return out


def pover(dst, src):
    """Palette-preserving 'over': combined alpha is exact, colour is taken from whichever layer
    contributes more at that pixel, so every visible pixel stays a master-palette colour."""
    sa = src[..., 3].astype(float) / 255
    da = dst[..., 3].astype(float) / 255
    oa = sa + da * (1 - sa)
    use_src = sa >= da * (1 - sa)
    rgb = np.where(use_src[..., None], src[..., :3], dst[..., :3])
    out = np.concatenate([rgb, np.round(oa * 255)[..., None]], -1).astype(np.uint8)
    out[oa <= 0] = 0
    return out


def stack(layers, w, h):
    cv = canvas(w, h)
    for L in layers:
        cv = pover(cv, L)
    # re-snap colours of blended semi-transparent overlaps: keep top colour where opaque layers mix
    return cv


def finish_frame(cv):
    cv = cv.copy()
    a = np.round(cv[..., 3].astype(float) / 255 * ALPHA_STEPS) / ALPHA_STEPS
    cv[..., 3] = (a * 255).astype(np.uint8)
    cv[cv[..., 3] == 0] = 0
    return clear_border(cv)


# --------------------------------------------------------------------------
# field primitives
# --------------------------------------------------------------------------


def fgrid(w, h):
    xs, ys = grid(w, h)
    return xs + 0.5, ys + 0.5


def disc(w, h, cx, cy, r, soft=1.0):
    xs, ys = fgrid(w, h)
    d = np.hypot(xs - cx, ys - cy)
    return np.clip((r - d) / max(soft, 1e-3) + 0.5, 0, 1)


def ellipse_f(w, h, cx, cy, rx, ry, soft=1.0):
    xs, ys = fgrid(w, h)
    d = np.hypot((xs - cx) / rx, (ys - cy) / ry)
    return np.clip((1 - d) * min(rx, ry) / max(soft, 1e-3) + 0.5, 0, 1)


def ring(w, h, cx, cy, r, thick, soft=0.8, sy=1.0):
    xs, ys = fgrid(w, h)
    d = np.hypot(xs - cx, (ys - cy) / sy)
    return np.clip((thick / 2 - np.abs(d - r)) / max(soft, 1e-3) + 0.5, 0, 1)


def ring_profile(w, h, cx, cy, r, thick, sy=1.0):
    """Ring coverage (0/1) and the across-coordinate u (-1 inner edge .. +1 outer edge)."""
    xs, ys = fgrid(w, h)
    d = np.hypot(xs - cx, (ys - cy) / sy)
    u = (d - r) / max(thick / 2, 1e-3)
    cov = (np.abs(u) <= 1.0).astype(float)
    return cov, np.clip(u, -1, 1)


def seg(w, h, x0, y0, x1, y1, r0, r1=None, soft=0.7):
    """Capsule along a segment with radius tapering r0 -> r1."""
    r1 = r0 if r1 is None else r1
    xs, ys = fgrid(w, h)
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy + 1e-9
    t = np.clip(((xs - x0) * dx + (ys - y0) * dy) / L2, 0, 1)
    d = np.hypot(xs - (x0 + t * dx), ys - (y0 + t * dy))
    r = r0 + (r1 - r0) * t
    return np.clip((r - d) / max(soft, 1e-3) + 0.5, 0, 1)


def polyline(w, h, pts, r0, r1=None, soft=0.7):
    r1 = r0 if r1 is None else r1
    out = np.zeros((h, w))
    n = len(pts) - 1
    for i in range(n):
        a = r0 + (r1 - r0) * i / n
        b = r0 + (r1 - r0) * (i + 1) / n
        out = np.maximum(out, seg(w, h, *pts[i], *pts[i + 1], a, b, soft))
    return out


def star(w, h, cx, cy, n, r_long, r_short, width, rot=0.0, falloff=1.0, lengths=None, with_t=False):
    """n-pointed star burst: thin tapered rays. lengths: per-ray length multipliers.
    with_t=True also returns the normalised distance along the ray (0 centre .. 1 tip)."""
    xs, ys = fgrid(w, h)
    dx, dy = xs - cx, ys - cy
    d = np.hypot(dx, dy) + 1e-6
    a = np.arctan2(dy, dx) - rot
    out = np.zeros((h, w))
    tt = np.ones((h, w))
    for i in range(n):
        ang = i * math.tau / n
        L = (r_long if i % 2 == 0 else r_short) * (lengths[i] if lengths is not None else 1.0)
        diff = np.abs((a - ang + math.pi) % math.tau - math.pi)
        lateral = diff * d
        wd = width * np.clip(1 - d / L, 0, 1) ** falloff
        cov = np.clip(wd - lateral + 0.5, 0, 1) * (d < L)
        upd = cov > out
        out = np.where(upd, cov, out)
        tt = np.where(upd, d / L, tt)
    if with_t:
        return out, tt
    return out


def ray_intensity(cov, t, hot=1.0):
    """Ray colour: hot near the centre, cooling toward the tips."""
    return np.where(cov > 0, np.clip(hot * (1.0 - 0.8 * t) + 0.12, 0, 1), 0)


def noise(w, h, rng, cells=4, octaves=3):
    return fbm(w, h, cells, octaves, rng)


def polygon_f(w, h, pts):
    return poly_mask(w, h, pts, ss=4).astype(float)


def frames_to_sheet(name, fw, fh, pivot, anims, meta=None):
    """anims: list of (anim_name, frames, fps, loop)."""
    sb = SheetBuilder(name, fw, fh, pivot, columns=8, meta=meta or {})
    for (an, frames, fps, loop) in anims:
        sb.add_animation(an, [to_image(finish_frame(f)) for f in frames], fps=fps, loop=loop)
    png = sb.save(OUT_FX)
    contact_sheet(png, scale=4, out_path=os.path.join(PREVIEW_DIR, "fx_" + name + ".png"))
    return png


# --------------------------------------------------------------------------
# billboard effects
# --------------------------------------------------------------------------


def hit_spark():
    """White-gold star burst with speed lines. 32x32, centre pivot."""
    W = H = 32
    cx, cy = 16, 16
    rng = rng_for("hit_spark")
    frames = []
    lines = [(i * math.tau / 7 + rng.uniform(-0.2, 0.2), rng.uniform(0.7, 1.0)) for i in range(7)]
    spec = [  # core r, ray long, ray short, ray width, line r0, line r1, alpha
        (2.5, 7, 4, 1.8, 5, 8, 1.0),
        (3.0, 12, 7, 2.4, 7, 12, 1.0),
        (2.4, 14, 9, 2.2, 9, 14, 1.0),
        (1.6, 11, 7, 1.6, 11, 15, 1.0),
        (1.0, 6, 4, 1.1, 13, 15, 0.75),
        (0.0, 0, 0, 0.0, 14, 15, 0.5),
    ]
    heat = [1.0, 1.0, 0.95, 0.8, 0.65, 0.5]
    for f, (cr, rl, rs, rw, l0, l1, al) in enumerate(spec):
        inten = np.zeros((H, W))
        alph = np.zeros((H, W))
        if rl:
            cov, t = star(W, H, cx, cy, 8, rl, rs, rw, rot=0.0, with_t=True)
            inten = np.maximum(inten, ray_intensity(cov, t, heat[f]))
            alph = np.maximum(alph, (cov > 0.35).astype(float))
        if cr:
            c = disc(W, H, cx, cy, cr, 0.8)
            glow = disc(W, H, cx, cy, cr + 2.5, 2.0)
            inten = np.maximum(inten, np.where(c > 0.5, 1.0, glow * 0.55))
            alph = np.maximum(alph, np.maximum((c > 0.5).astype(float), glow * 0.6))
        for (ang, ln) in lines:
            x0 = cx + math.cos(ang) * l0
            y0 = cy + math.sin(ang) * l0
            x1 = cx + math.cos(ang) * (l0 + (l1 - l0) * ln)
            y1 = cy + math.sin(ang) * (l0 + (l1 - l0) * ln)
            sgm = seg(W, H, x0, y0, x1, y1, 0.8, 0.5)
            inten = np.maximum(inten, (sgm > 0.4) * (0.62 * heat[f] + 0.1))
            alph = np.maximum(alph, (sgm > 0.4).astype(float))
        frames.append(colorize(inten, alph * al, G["spark"]))
    return frames_to_sheet("hit_spark", W, H, (16, 16), [("play_s", frames, 24, False)],
                           meta={"kind": "billboard", "pivot": "center"})


def hit_heavy():
    """Big impact burst + expanding ring. 64x64, centre pivot."""
    W = H = 64
    cx, cy = 32, 32
    rng = rng_for("hit_heavy")
    lens = rng.uniform(0.65, 1.0, 12)
    sparks = [(i * math.tau / 11 + rng.uniform(-0.2, 0.2), rng.uniform(0.85, 1.15)) for i in range(11)]
    brk = noise(W, H, rng, 10, 1)
    frames = []
    spec = [  # core, ray long, ray short, ray w, ring r, ring thick, ring heat, spark r, alpha
        (7, 15, 9, 3.2, 0, 0, 0, 0, 1.0),
        (6, 27, 16, 3.6, 11, 5.0, 1.0, 15, 1.0),
        (4, 29, 18, 3.0, 17, 4.0, 0.9, 21, 1.0),
        (2.5, 20, 12, 2.2, 22, 3.0, 0.75, 26, 1.0),
        (1.2, 11, 7, 1.4, 26, 2.2, 0.6, 28, 1.0),
        (0, 0, 0, 0, 28.5, 1.6, 0.45, 29.5, 0.75),
        (0, 0, 0, 0, 0, 0, 0, 30, 0.5),
    ]
    for f, (cr, rl, rs, rw, rr, rt, rh, sr, al) in enumerate(spec):
        inten = np.zeros((H, W))
        alph = np.zeros((H, W))
        if rr:
            cov, u = ring_profile(W, H, cx, cy, rr, rt)
            if f >= 4:
                cov = cov * (brk > 0.35)
            ri = np.clip(rh * (0.62 - 0.5 * u) + 0.05, 0, 1)
            inten = np.where(cov > 0, ri, inten)
            alph = np.maximum(alph, cov)
        if rl:
            cov, t = star(W, H, cx, cy, 12, rl, rs, rw, rot=0.13, lengths=lens, with_t=True)
            m = cov > 0.35
            inten = np.where(m, np.maximum(inten, ray_intensity(cov, t, 1.0)), inten)
            alph = np.maximum(alph, m.astype(float))
        if cr:
            glow = disc(W, H, cx, cy, cr + 3, 1.0)
            c = disc(W, H, cx, cy, cr, 1.0)
            inten = np.where(glow > 0.5, 0.75, inten)
            inten = np.where(c > 0.5, 1.0, inten)
            alph = np.maximum(alph, (glow > 0.5).astype(float))
        if sr:
            for (ang, k) in sparks:
                r = sr * k
                x, y = cx + math.cos(ang) * r, cy + math.sin(ang) * r
                tail = seg(W, H, x - math.cos(ang) * 4, y - math.sin(ang) * 4, x, y, 0.45, 1.0) > 0.4
                inten = np.where(tail, np.maximum(inten, 0.62 if f < 5 else 0.45), inten)
                alph = np.maximum(alph, tail.astype(float))
        frames.append(colorize(inten, alph * al, G["spark"]))
    return frames_to_sheet("hit_heavy", W, H, (32, 32), [("play_s", frames, 20, False)],
                           meta={"kind": "billboard", "pivot": "center"})


def dust_puff():
    """Soft brown-grey puff rising and fading. 24x24, bottom-centre pivot."""
    W = H = 24
    rng = rng_for("dust_puff")
    blobs = [(-4.5, 0.0, 4.2), (4.0, 0.5, 4.0), (0.0, -2.0, 5.0), (-1.5, 1.5, 3.4), (2.5, -4.5, 3.0)]
    frames = []
    for f in range(6):
        t = f / 5
        grow = 0.65 + 0.6 * t
        rise = 3.0 + 6.0 * t
        al = [1.0, 1.0, 1.0, 0.75, 0.5, 0.25][f]
        inten = np.zeros((H, W))
        alph = np.zeros((H, W))
        for (bx, by, br) in blobs:
            x = 12 + bx * (0.8 + 0.5 * t)
            y = 20 - rise + by
            r = br * grow
            d = disc(W, H, x, y, r, 1.0)
            # lit from upper-left: lighter toward the top-left of each blob
            xs, ys = fgrid(W, H)
            lit = np.clip(0.55 - ((xs - x) * 0.6 + (ys - y) * 0.8) / (r * 2.2), 0, 1)
            inten = np.where(d > 0.01, np.maximum(inten, lit * d + 0.15 * d), inten)
            alph = np.maximum(alph, d)
        n = noise(W, H, rng, 3, 2)
        alph = (alph > 0.5).astype(float)
        if f >= 3:
            alph = alph * (n > 0.12 * (f - 2))
        frames.append(colorize(inten * 0.95 + 0.05, alph * al, G["dust"]))
    return frames_to_sheet("dust_puff", W, H, (12, 23), [("play_s", frames, 16, False)],
                           meta={"kind": "billboard", "pivot": "bottom-center"})


# --------------------------------------------------------------------------
# fire helpers
# --------------------------------------------------------------------------


def periodic_noise(w, period, rng, cells_x=4, cells_y=4, octaves=3):
    """Noise periodic over `period` rows (for looping upward scroll) and w columns."""
    return fbm(w, period, cells_x, octaves, rng, cells_y=cells_y)


def flame(w, h, cx, base_y, height, width, nz, off, core=1.0, lean=0.0, tongue=0.55):
    """Upward flame: returns (intensity, coverage). nz: periodic noise (rows = period), off: scroll offset."""
    xs, ys = fgrid(w, h)
    P = nz.shape[0]
    rows = (np.floor(ys).astype(int) + int(off)) % P
    cols = np.clip(np.floor(xs).astype(int), 0, nz.shape[1] - 1)
    n = nz[rows, cols]
    v = (base_y - ys) / max(height, 1e-3)  # 0 at base .. 1 at the top
    u = (xs - cx - lean * np.clip(v, 0, 1) * height * 0.3) / max(width / 2, 1e-3)
    env = np.sin(np.clip(v * 0.82 + 0.18, 0, 1) * math.pi) ** 0.55 * (1 - np.clip(v, 0, 1)) ** 0.35
    env = env + (n - 0.5) * tongue * np.clip(v, 0, 1)
    inside = (np.abs(u) < env) & (v > -0.08) & (v < 1.05 + (n - 0.5) * 0.4)
    heat = core * (1.05 - np.abs(u) / np.maximum(env, 1e-3) * 0.55 - np.clip(v, 0, 1) * 0.75) + (n - 0.5) * 0.4
    return np.where(inside, np.clip(heat, 0, 1), 0), inside.astype(float)


def blob_f(w, h, cx, cy, r, rng=None):
    return disc(w, h, cx, cy, r, 1.0)


# --------------------------------------------------------------------------
# remaining billboard effects
# --------------------------------------------------------------------------

STAR5 = ["..o..", ".oho.", "ohhho", ".oho.", "..o.."]
STAR7 = ["...o...", "..oho..", "..oho..", "ohhwhho", "..oho..", "..oho..", "...o..."]


def stamp(cv, x, y, bitmap, cols, alpha=1.0):
    """Paint an ASCII bitmap; cols maps chars to RGBA colours ('.' transparent)."""
    h, w = cv.shape[:2]
    bh = len(bitmap)
    bw = len(bitmap[0])
    for j, row in enumerate(bitmap):
        for i, ch in enumerate(row):
            if ch == "." or ch == " ":
                continue
            X, Y = int(x) + i - bw // 2, int(y) + j - bh // 2
            if 0 <= X < w and 0 <= Y < h:
                c = np.array(cols[ch], np.uint8).copy()
                c[3] = int(c[3] * alpha)
                cv[Y, X] = c


def stun_stars():
    """Three little stars circling on a tilted orbit. 32x16, loops (120 degrees per cycle)."""
    W, H = 32, 16
    cx, cy, rx, ry = 16, 8, 11.5, 3.6
    frames = []
    big = {"o": RA["gold"][1], "h": RA["gold"][5], "w": RA["cloth_cream"][5]}
    small = {"o": RA["gold"][1], "h": RA["gold"][4]}
    for f in range(6):
        cv = canvas(W, H)
        # faint orbit dots (behind)
        for k in range(24):
            a = k * math.tau / 24
            x, y = cx + math.cos(a) * rx, cy + math.sin(a) * ry
            if (k + f) % 3 == 0:
                c = RA["gold"][3].copy()
                c[3] = 128
                if 0 <= int(y) < H and 0 <= int(x) < W:
                    cv[int(y), int(x)] = c
        stars = []
        for k in range(3):
            a = k * math.tau / 3 + f * (math.tau / 3) / 6
            stars.append((math.sin(a), cx + math.cos(a) * rx, cy + math.sin(a) * ry, a))
        stars.sort()
        for (depth, x, y, a) in stars:
            # trail sparkle one step behind
            ta = a - (math.tau / 3) / 6
            tx, ty = cx + math.cos(ta) * rx, cy + math.sin(ta) * ry
            c = RA["gold"][4].copy()
            c[3] = 128
            if 0 <= int(ty) < H and 0 <= int(tx) < W:
                cv[int(ty), int(tx)] = c
            if depth > -0.2:
                stamp(cv, x, y, STAR7 if depth > 0.45 else STAR5, big)
            else:
                stamp(cv, x, y, STAR5, small, alpha=0.75)
        frames.append(cv)
    return frames_to_sheet("stun_stars", W, H, (16, 8), [("loop_s", frames, 10, True)],
                           meta={"kind": "billboard", "pivot": "center (sits above the head)"})


def ember_bolt():
    """Fiery bolt flying RIGHT: hot core head, flickering tail. 32x16, centre pivot, loops."""
    W, H = 32, 16
    rng = rng_for("ember_bolt")
    nz = fbm(W, H, 4, 3, rng, cells_y=2)  # periodic in x -> scroll left per frame
    xs, ys = fgrid(W, H)
    frames = []
    embers = [(rng.uniform(0, W), rng.uniform(4, 12)) for _ in range(5)]
    for f in range(4):
        sh = int(f * W / 4)
        n = np.roll(nz, -sh, axis=1)
        hx, hy = 24.0, 8.0
        # head: teardrop pointing right
        dx = xs - hx
        dy = ys - hy
        # tail half-width shrinks to the left with flicker
        t = np.clip((hx - xs) / 21.0, 0, 1)
        half = np.where(xs <= hx, 4.2 * (1 - t) ** 0.7 + (n - 0.5) * 3.2 * t, np.sqrt(np.clip(16 - dx * dx * 1.6, 0, None)))
        wob = np.sin(xs * 0.6 + f * math.pi / 2) * 0.8 * t
        inside = (np.abs(dy - wob) < half) & (xs > 2.5) & (xs < hx + 3.6)
        heat = 1.05 - np.abs(dy - wob) / np.maximum(half, 0.5) * 0.45 - t * 0.85 + (n - 0.5) * 0.35
        core = ((dx / 3.2) ** 2 + (dy / 2.1) ** 2) <= 1.0
        inten = np.where(inside, np.clip(heat, 0.02, 1), 0)
        inten = np.where(core, 1.0, inten)
        alph = inside | core
        layers = [colorize(inten, alph.astype(float), G["fire_hot"])]
        # glow halo around the head
        halo = ellipse_f(W, H, hx - 1, hy, 7.0, 5.0, 1.0)
        hl = colorize(np.full((H, W), 0.45), (halo > 0.5) * 0.5 * (~alph), G["fire_hot"])
        cv = pover(hl, layers[0])
        # trailing embers
        for (ex, ey) in embers:
            x = (ex - f * W / 4) % (W - 8) + 2
            if x < hx - 4:
                c = G["fire"][3 + (int(x) % 2)].copy()
                if 0 < int(ey) < H - 1:
                    cv[int(ey), int(x)] = c
        frames.append(cv)
    return frames_to_sheet("ember_bolt", W, H, (16, 8), [("loop_s", frames, 16, True)],
                           meta={"kind": "billboard projectile", "pivot": "center", "faces": "+X (right)"})


def ember_impact():
    """Fireball burst with flame tongues, smoke and embers. 32x32, centre pivot."""
    W = H = 32
    cx, cy = 16, 16
    rng = rng_for("ember_impact")
    nz = noise(W, H, rng, 5, 3)
    xs, ys = fgrid(W, H)
    ang = np.arctan2(ys - cy, xs - cx)
    d = np.hypot(xs - cx, ys - cy)
    tong = np.sin(ang * 7 + 1.3) * 0.5 + np.sin(ang * 11 + 0.4) * 0.3
    sparks = [(rng.uniform(0, math.tau), rng.uniform(0.8, 1.2)) for _ in range(9)]
    frames = []
    spec = [(5, 1.0, 0.0), (9, 1.0, 0.1), (12, 0.8, 0.35), (13, 0.55, 0.6), (13.5, 0.3, 0.85)]
    for f, (r, heat, smoke) in enumerate(spec):
        rr = r * (1 + 0.18 * tong * min(1, f) + (nz - 0.5) * 0.35)
        inside = d < rr
        if f >= 3:
            inside &= nz > 0.25 + 0.15 * (f - 3)
        hv = heat * (1.1 - d / np.maximum(rr, 1) * 0.8) + (nz - 0.5) * 0.3
        inten = np.where(inside, np.clip(hv, 0, 1), 0)
        cv = canvas(W, H)
        if smoke:
            sm = (d < rr + 2) & ~inside & (nz > 0.45) & (ys < cy + 4)
            sm |= inside & (hv < 0.15)
            smk = colorize(np.clip(0.3 + (1 - ys / H) * 0.4, 0, 1), sm * (0.75 if f < 4 else 0.5), G["smoke"])
            cv = pover(cv, smk)
        cv = pover(cv, colorize(inten, inside.astype(float) * (1.0 if f < 4 else 0.75), G["fire_hot"]))
        if f == 0:
            cv = pover(cv, colorize(np.ones((H, W)), (star(W, H, cx, cy, 8, 11, 6, 1.6) > 0.4) * 1.0,
                                   G["fire_hot"]))
        if f >= 1:
            for (a, k) in sparks:
                rs = (r + 3 + f * 1.5) * k
                x, y = cx + math.cos(a) * rs, cy + math.sin(a) * rs
                if 1 <= x < W - 1 and 1 <= y < H - 1:
                    c = G["fire"][5 if f < 3 else 3].copy()
                    c[3] = 255 if f < 4 else 160
                    cv[int(y), int(x)] = c
        frames.append(cv)
    return frames_to_sheet("ember_impact", W, H, (16, 16), [("play_s", frames, 20, False)],
                           meta={"kind": "billboard", "pivot": "center"})


def slash_arc(w, h, p0, p1, bulge, width, t0=0.0, t1=1.0):
    """Crescent slash from p0 to p1 bowed sideways by `bulge`; returns (coverage, across u)."""
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    nx, ny = -dy / L, dx / L
    ctrl = (mx + nx * bulge, my + ny * bulge)
    pts = bezier([p0, ctrl, p1], 40)
    out = np.zeros((h, w))
    xs, ys = fgrid(w, h)
    n = len(pts)
    for i in range(int(t0 * (n - 1)), int(t1 * (n - 1))):
        t = i / (n - 1)
        r = width * math.sin(math.pi * t) ** 0.85 + 0.35
        out = np.maximum(out, seg(w, h, *pts[i], *pts[i + 1], r, width * math.sin(math.pi * (i + 1) / (n - 1)) ** 0.85 + 0.35, 0.6))
    return out


def flash_strike():
    """Three bright claw-slash streaks (upper-right to lower-left). 48x48, centre pivot."""
    W = H = 48
    frames = []
    slashes = [((40, 6), (10, 38), 5.5), ((43, 12), (14, 43), 5.5), ((35, 3), (5, 33), 5.5)]
    order = [1, 0, 2]
    spec = [(0.0, 0.55, 2.6, 1.0), (0.0, 1.0, 3.0, 1.0), (0.1, 1.0, 2.0, 0.9), (0.35, 1.0, 1.2, 0.6)]
    for f, (t0, t1, wd, heat) in enumerate(spec):
        cv = canvas(W, H)
        for k in order:
            p0, p1, b = slashes[k]
            cov = slash_arc(W, H, p0, p1, b, wd, t0, t1)
            core = slash_arc(W, H, p0, p1, b, max(0.4, wd - 1.4), t0, t1)
            inten = np.where(cov > 0.4, 0.45 * heat, 0)
            inten = np.where(core > 0.4, 0.95 * heat if f < 2 else 0.7 * heat, inten)
            cv = pover(cv, colorize(inten + 0.04, (cov > 0.4) * 1.0 * (1.0 if f < 3 else 0.75), G["spark"]))
        if f == 1:
            for (p0, p1, b) in slashes:
                x, y = p1
                cv = pover(cv, colorize(np.ones((H, W)) * 0.9, (star(W, H, x, y, 4, 3.2, 3.2, 0.9) > 0.4) * 1.0,
                                       G["spark"]))
        frames.append(cv)
    return frames_to_sheet("flash_strike", W, H, (24, 24), [("play_s", frames, 20, False)],
                           meta={"kind": "billboard", "pivot": "center"})


def fire_pillar():
    """Flames erupt upward then die down. 32x48, bottom-centre pivot."""
    W, H = 32, 48
    rng = rng_for("fire_pillar")
    P = 48
    nz = periodic_noise(W, P, rng, 4, 6)
    frames = []
    spec = [(12, 18, 0.9), (30, 15, 1.0), (44, 14, 1.0), (42, 14, 0.9), (28, 12, 0.7), (11, 10, 0.5)]
    embers = [(rng.uniform(8, 24), rng.uniform(0, 1)) for _ in range(8)]
    for f, (hgt, wid, heat) in enumerate(spec):
        inten, cov = flame(W, H, 16, 46.5, hgt, wid, nz, f * 7, core=heat, tongue=0.7)
        base_f = ellipse_f(W, H, 16, 45.5, wid * 0.62, 2.2, 1.0)
        inten = np.maximum(inten, base_f * 0.55 * heat)
        cov = np.maximum(cov, (base_f > 0.5).astype(float))
        cv = canvas(W, H)
        if f >= 3:
            sm = flame(W, H, 16, 46.5 - hgt * 0.75, hgt * 0.5, wid * 0.9, nz, f * 7 + 13, core=0.6, tongue=0.9)[1]
            sm = sm * (1 - cov)
            cv = pover(cv, colorize(np.full((H, W), 0.45), sm * 0.5, G["smoke"]))
        cv = pover(cv, colorize(inten, cov * (1.0 if f < 5 else 0.75), G["fire_hot"]))
        if f >= 2:
            for (ex, ph) in embers:
                y = 46 - hgt * (0.6 + 0.5 * ((ph + f * 0.17) % 1.0))
                x = ex + math.sin(ph * 9 + f) * 2
                if 1 <= y < H - 1:
                    c = G["fire"][5].copy()
                    c[3] = 255 if f < 5 else 128
                    cv[int(y), int(x)] = c
        frames.append(cv)
    return frames_to_sheet("fire_pillar", W, H, (16, 47), [("play_s", frames, 14, False)],
                           meta={"kind": "billboard", "pivot": "bottom-center"})


def burn_flame():
    """Tiny looping flame for the burn status. 16x16, bottom-centre pivot."""
    W = H = 16
    rng = rng_for("burn_flame")
    P = 16
    nz = periodic_noise(W, P, rng, 3, 4)
    frames = []
    for f in range(4):
        inten, cov = flame(W, H, 8, 14.5, 12, 9, nz, f * 4, core=1.0, tongue=0.65)
        frames.append(colorize(inten, cov, G["fire_hot"]))
    return frames_to_sheet("burn_flame", W, H, (8, 15), [("loop_s", frames, 12, True)],
                           meta={"kind": "billboard status", "pivot": "bottom-center"})


def boulder():
    """Mossy boulder rolling RIGHT (clockwise): fixed lighting, surface details rotate 45 deg/frame
    with 180-degree-symmetric features so 4 frames loop seamlessly. 32x32, centre pivot."""
    W = H = 32
    cx, cy, R = 16, 16, 13.2
    rng = rng_for("boulder")
    xs, ys = fgrid(W, H)
    dx, dy = xs - cx, ys - cy
    d = np.hypot(dx, dy)
    # lumpy silhouette (rotates with the rock, also 180-deg symmetric)
    lumps = [(rng.uniform(0, math.pi), rng.uniform(0.015, 0.03)) for _ in range(3)]
    cracks = []
    for _ in range(3):
        a = rng.uniform(0, math.tau)
        r0 = rng.uniform(2, 6)
        pts = [(math.cos(a) * r0, math.sin(a) * r0)]
        ang = a + rng.uniform(-0.5, 0.5)
        for i in range(5):
            ang += rng.uniform(-0.6, 0.6)
            pts.append((pts[-1][0] + math.cos(ang) * 1.8, pts[-1][1] + math.sin(ang) * 1.8))
        cracks.append(pts)
    moss = [(rng.uniform(0, math.tau), rng.uniform(5, 11), rng.uniform(3, 4.5)) for _ in range(2)]
    frames = []
    for f in range(4):
        th = f * math.pi / 4
        # rotate screen -> surface coords
        su = dx * math.cos(-th) - dy * math.sin(-th)
        sv = dx * math.sin(-th) + dy * math.cos(-th)
        sa = np.arctan2(sv, su)
        rr = R * (1 + sum(amp * np.cos(2 * (sa - ph)) for ph, amp in lumps))
        inside = d <= rr
        nzv = np.sqrt(np.clip(1 - (d / rr) ** 2, 0, 1))
        lam = np.clip((dx / rr) * -0.58 + (dy / rr) * -0.58 + nzv * 0.6, 0, 1)
        k = np.zeros((H, W), int)
        for t in (0.18, 0.4, 0.6, 0.78):
            k += (lam >= t).astype(int)
        idx = np.array([1, 2, 3, 4, 5])[k]
        cv = canvas(W, H)
        cv[inside] = RA["stone_warm"][idx[inside]]
        # moss patches (and their 180-degree twins)
        for (a, r0, mr) in moss:
            for flip in (0, math.pi):
                mx, my = math.cos(a + flip) * r0, math.sin(a + flip) * r0
                mm = inside & (np.hypot(su - mx, sv - my) < mr)
                mk = np.clip(idx - 1, 1, 5)
                cv[mm] = RA["moss"][mk[mm]]
        # cracks (and twins): dark line + lit lower-right lip in screen space
        for pts in cracks:
            for flip in (1, -1):
                P = [(px * flip, py * flip) for (px, py) in pts]
                # rotate surface -> screen
                Q = [(cx + px * math.cos(th) - py * math.sin(th), cy + px * math.sin(th) + py * math.cos(th))
                     for (px, py) in P]
                line = polyline(W, H, Q, 0.55) > 0.5
                line &= inside & (d < rr - 1)
                lip = shift(line, 1, 1) & ~line & inside
                cv[lip] = RA["stone_warm"][5]
                cv[line] = RA["stone_warm"][0]
        # outline: darkest of the material
        from kit import outline as _outline
        cv = _outline(cv, "outer")
        frames.append(cv)
    return frames_to_sheet("boulder", W, H, (16, 16), [("loop_s", frames, 12, True)],
                           meta={"kind": "billboard projectile", "pivot": "center", "rolls": "clockwise (toward +X)"})


def rock_shard(w, h, x, y, size, rot, ramp="stone_warm"):
    """Small angular rock chunk polygon, lit from the upper-left. Returns RGBA."""
    pts = []
    n = 5
    for i in range(n):
        a = rot + i * math.tau / n
        rr = size * (0.75 + 0.35 * ((i * 7 + int(size * 10)) % 3) / 2)
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr * 0.85))
    m = polygon_f(w, h, pts) > 0.5
    cv = canvas(w, h)
    xs, ys = fgrid(w, h)
    lit = ((xs - x) + (ys - y)) < 0
    cv[m] = RA[ramp][3]
    cv[m & lit] = RA[ramp][4]
    edge = m & ~shift(m, -1, -1)
    cv[edge & ~lit] = RA[ramp][1]
    cv[m & ~shift(m, 1, 1) & lit] = RA[ramp][5]
    return cv, m


def puff_layer(W, H, blobs, rng_noise, al, dissolve=0.0):
    """Round dust puffs, each lit from its own upper-left; returns an RGBA layer (dust gradient)."""
    xs, ys = fgrid(W, H)
    inten = np.zeros((H, W))
    cov = np.zeros((H, W), bool)
    for (x, y, r) in sorted(blobs, key=lambda b: b[1]):
        d = np.hypot(xs - x, ys - y)
        m = d < r
        lit = np.clip(0.62 - ((xs - x) * 0.6 + (ys - y) * 0.8) / (r * 2.0), 0, 1)
        inten = np.where(m, lit * 0.85 + 0.1, inten)
        cov |= m
    if dissolve:
        cov &= rng_noise > dissolve
    return colorize(inten, cov * al, G["dust"])


def rock_burst():
    """Stone debris explosion from the ground: chunks fly up and out, dust puffs billow. 48x48."""
    W = H = 48
    rng = rng_for("rock_burst")
    ox, oy = 24, 41
    chunks = []
    for i in range(9):
        vx = rng.uniform(-13, 13)
        vy = -rng.uniform(32, 46)
        chunks.append((vx, vy, rng.uniform(2.0, 3.4), rng.uniform(0, 6)))
    nz = noise(W, H, rng, 4, 2)
    ts = [0.12, 0.38, 0.64, 0.9, 1.16, 1.42]
    base_blobs = [(-7, 0, 4.0), (7, 0, 4.0), (0, -3, 5.0), (-12, 2, 3.0), (12, 2, 3.0), (-4, -6, 3.4), (5, -6, 3.0)]
    frames = []
    for f in range(6):
        t = ts[f]
        g = 0.55 + 0.25 * f
        blobs = [(ox + bx * g, oy + by * g - f * 1.0, br * (0.7 + 0.18 * f)) for (bx, by, br) in base_blobs]
        al = [1.0, 1.0, 1.0, 0.75, 0.5, 0.25][f]
        cv = puff_layer(W, H, blobs, nz, al, dissolve=0.0 if f < 3 else 0.1 * (f - 2))
        for (vx, vy, sz, rot) in chunks:
            x = ox + vx * t
            y = oy + vy * t + 22.0 * t * t
            if 2 < x < W - 3 and 2 < y < H - 2:
                ch, m = rock_shard(W, H, x, y, sz, rot + f * 1.1, ramp="stone")
                if f == 5:
                    ch[..., 3] = np.where(m, 192, 0)
                cv = pover(cv, ch)
        frames.append(cv)
    return frames_to_sheet("rock_burst", W, H, (24, 47), [("play_s", frames, 18, False)],
                           meta={"kind": "billboard", "pivot": "bottom-center"})


def spike_poly(cx, base, height, half_w, rng_seed, jag=1.0):
    r = np.random.default_rng(rng_seed)
    left = []
    right = []
    n = 6
    for i in range(n + 1):
        t = i / n
        y = base - height * t
        wd = half_w * (1 - t) ** 0.9
        jl = r.uniform(-1, 1) * jag * (1 - t)
        jr = r.uniform(-1, 1) * jag * (1 - t)
        left.append((cx - wd + jl, y))
        right.append((cx + wd + jr, y))
    tip = (cx + r.uniform(-1, 1), base - height - 1.5)
    return left + [tip] + right[::-1]


def fault_spike():
    """Jagged rock spikes erupt from the ground, then crumble. 32x48, bottom-centre pivot."""
    W, H = 32, 48
    rng = rng_for("fault_spike")
    base = 45.5
    spikes = [(16, 37, 6.0, 11), (8, 22, 4.2, 12), (24.5, 27, 4.6, 13)]
    hfrac = [0.3, 0.75, 1.0, 1.0, 0.85, 0.35]
    nz = noise(W, H, rng, 6, 2)
    frames = []
    for f in range(6):
        cv = canvas(W, H)
        xs, ys = fgrid(W, H)
        for (cx, ht, hw, seed) in spikes:
            h_ = ht * hfrac[f]
            if h_ < 2:
                continue
            poly = spike_poly(cx, base, h_, hw, seed)
            m = polygon_f(W, H, poly) > 0.5
            if f >= 4:
                m &= ys > base - h_ * (0.65 if f == 4 else 0.4) + (nz - 0.5) * 6
            ridge = cx + (xs - cx) * 0 + np.sin((base - ys) * 0.45 + seed) * 0.8
            left = xs < ridge
            k = np.where(left, 4, 2)
            k = np.where(np.abs(xs - ridge) < 0.8, 5, k)
            k = np.where((base - ys) < 3, k - 1, k)
            k = np.where(m & ~shift(m, 1, 0), 1, k)
            if f in (3, 4):
                crack = (np.abs(np.sin(ys * 0.9 + xs * 0.5 + seed)) < 0.12) & m
                k = np.where(crack, 0, k)
            spk = canvas(W, H)
            spk[m] = RA["stone_warm"][np.clip(k[m], 0, 5)]
            from kit import outline as _outline
            spk = _outline(spk, "outer")
            cv = pover(cv, spk)
        # falling chunks while crumbling
        if f >= 4:
            for i, (cx, ht, hw, seed) in enumerate(spikes):
                for j in range(2):
                    x = cx + (j * 2 - 1) * (hw + 1 + (f - 4) * 2)
                    y = base - ht * (0.6 - 0.25 * (f - 4)) + j * 3
                    ch, m = rock_shard(W, H, x, y, 1.6, seed + j + f)
                    cv = pover(cv, ch)
        # dust at the base
        dal = [0.75, 1.0, 0.75, 0.5, 0.75, 0.5][f]
        dust = np.zeros((H, W))
        for (bx, br) in ((-9, 3.5), (0, 4.5), (9, 3.5)):
            dust = np.maximum(dust, ellipse_f(W, H, 16 + bx * (1 + f * 0.08), base - 1, br * (1 + f * 0.1), 2.6, 1.0))
        cv = pover(colorize(np.full((H, W), 0.55), (dust > 0.5) * dal, G["dust"]), cv) if f < 4 else \
            pover(cv, colorize(np.full((H, W), 0.6), (dust > 0.5) * dal, G["dust"]))
        frames.append(cv)
    return frames_to_sheet("fault_spike", W, H, (16, 47), [("play_s", frames, 16, False)],
                           meta={"kind": "billboard", "pivot": "bottom-center"})


def hex_cells(qx, qy):
    """Pointy-top hex tiling (circumradius 1) -> (cell q, cell r, hex norm 0 centre .. 1 edge)."""
    q = math.sqrt(3) / 3 * qx - qy / 3
    r = 2 / 3 * qy
    x_, z_ = q, r
    y_ = -x_ - z_
    rx_, ry_, rz_ = np.round(x_), np.round(y_), np.round(z_)
    dxh, dyh, dzh = np.abs(rx_ - x_), np.abs(ry_ - y_), np.abs(rz_ - z_)
    c1 = (dxh > dyh) & (dxh > dzh)
    c2 = ~c1 & (dyh > dzh)
    rx_ = np.where(c1, -ry_ - rz_, rx_)
    rz_ = np.where(~c1 & ~c2, -rx_ - ry_, rz_)
    cxh = math.sqrt(3) * (rx_ + rz_ / 2)
    cyh = 1.5 * rz_
    dx = qx - cxh
    dy = qy - cyh
    # pointy-top hexagon: edge normals at 0, 60, 120 degrees; inradius sqrt(3)/2
    norm = np.maximum(np.abs(dx), np.abs(dx) * 0.5 + np.abs(dy) * math.sqrt(3) / 2) / (math.sqrt(3) / 2)
    return rx_, rz_, norm


def stone_guard():
    """Translucent dome of hexagonal stone plates with moss-glow seams; a glow band sweeps up. 64x64."""
    W = H = 64
    cx, cy, rx, ry = 32, 60, 29, 46
    xs, ys = fgrid(W, H)
    nx = (xs - cx) / rx
    ny = (ys - cy) / ry
    rr = nx * nx + ny * ny
    inside = (rr <= 1.0) & (ys <= cy + 0.5)
    nzv = np.sqrt(np.clip(1 - rr, 0, 1))
    lon = np.arctan2(nx, np.maximum(nzv, 1e-3))
    lat = np.arcsin(np.clip(-ny, -1, 1))
    S = 0.27
    cq, cr, norm = hex_cells(lon / S, lat / S)
    seam = norm > 0.84
    cell_tone = ((cq * 7 + cr * 13) % 5) / 5.0
    rim = inside & ~(((xs - cx) / (rx - 1.6)) ** 2 + ((ys - cy) / (ry - 1.6)) ** 2 <= 1.0)
    frames = []
    for f in range(4):
        band = np.exp(-((lat - (f / 4) * 1.6 - 0.05) ** 2) / 0.035)
        cv = canvas(W, H)
        pa = np.clip(0.25 + (1 - nzv) * 0.35 + band * 0.25, 0, 0.75)
        pi = np.clip(0.55 + cell_tone * 0.25 + band * 0.25 - (1 - nzv) * 0.1, 0, 1)
        cv = pover(cv, colorize(pi, (inside & ~seam) * pa, G["stone"]))
        si = np.clip(0.5 + band * 0.5 + (1 - nzv) * 0.15, 0, 1)
        cv = pover(cv, colorize(si, (inside & seam) * np.clip(0.75 + band, 0, 1), G["moss_glow"]))
        cv = pover(cv, colorize(np.full((H, W), 0.85), rim * 1.0, G["moss_glow"]))
        gr = ring(W, H, cx, cy - 0.5, rx - 1, 1.8, 0.6, sy=0.16) * (ys >= cy - 4)
        cv = pover(cv, colorize(np.full((H, W), 0.95), (gr > 0.5) * 0.75, G["moss_glow"]))
        frames.append(cv)
    return frames_to_sheet("stone_guard", W, H, (32, 60), [("loop_s", frames, 8, True)],
                           meta={"kind": "billboard", "pivot": "base centre of the dome"})


def ellipse_ring_3d(W, H, cx, cy, rx, ry, thick=1.8):
    """Elliptical ring split into front (lower) and back (upper) arcs."""
    xs, ys = fgrid(W, H)
    r = ring(W, H, cx, cy, rx, thick, 0.8, sy=ry / rx) > 0.35
    return r & (ys >= cy), r & (ys < cy)


def focus_aura():
    """Rising cyan-white wisps and rings around a creature. 48x64, pivot (24,60), loops."""
    W, H = 48, 64
    wisps = [(-13, 0.0, 18), (9, 0.17, 20), (-4, 0.33, 16), (14, 0.5, 18), (-9, 0.67, 17), (4, 0.83, 21)]
    xs, ys = fgrid(W, H)
    frames = []
    for f in range(6):
        cv = canvas(W, H)
        pulse = 0.5 + 0.5 * math.cos(f / 6 * math.tau)
        # faint aura column
        col = (np.abs(xs - 24) < 13 - (58 - ys) * 0.06) & (ys < 58) & (ys > 12)
        chk = ((xs.astype(int) + ys.astype(int)) % 2 == 0)
        colal = np.where(ys > 38, 0.25, np.where(ys > 24, 0.25 * chk, 0))
        cv = pover(cv, colorize(np.full((H, W), 0.4), col * colal, G["cyan"]))
        inner = ellipse_f(W, H, 24, 58, 15, 4.4, 1.0)
        cv = pover(cv, colorize(np.full((H, W), 0.45), (inner > 0.5) * 0.5, G["cyan"]))
        front, back = ellipse_ring_3d(W, H, 24, 58, 15 + pulse, 4.6 + pulse * 0.3)
        cv = pover(cv, colorize(np.full((H, W), 0.7), back * 0.75, G["cyan"]))
        cv = pover(cv, colorize(np.full((H, W), 0.97), front * 1.0, G["cyan"]))
        for ph in (0.0, 0.5):
            t = ((f / 6) + ph) % 1.0
            y = 56 - t * 36
            fr, bk = ellipse_ring_3d(W, H, 24, y, 15 - t * 5, 4.2 - t * 1.2, 1.6)
            al = 1.0 if t < 0.45 else (0.75 if t < 0.75 else 0.5)
            cv = pover(cv, colorize(np.full((H, W), 0.6), bk * al * 0.5, G["cyan"]))
            cv = pover(cv, colorize(np.full((H, W), 0.9), fr * al, G["cyan"]))
        for (x0, ph, L) in wisps:
            t = ((f / 6) + ph) % 1.0
            yh = 54 - t * 44
            xh = 24 + x0 * (1 - 0.3 * t)
            pts = [(xh + math.sin(j * 0.32 + x0 + t * 6) * 1.3, yh + j) for j in range(0, L + 1)]
            fade = 1.0 if t < 0.6 else (0.75 if t < 0.85 else 0.5)
            for (j0, j1, inten, al) in ((0, 4, 0.97, 1.0), (3, 9, 0.85, 0.75), (8, 14, 0.7, 0.5), (13, L, 0.6, 0.25)):
                segpts = pts[j0:j1 + 1]
                if len(segpts) >= 2:
                    cov = polyline(W, H, segpts, 0.65, 0.55) > 0.35
                    cv = pover(cv, colorize(np.full((H, W), inten), cov * al * fade, G["cyan"]))
        for k in range(3):
            t = ((f / 6) + k / 3 + 0.1) % 1.0
            x = 24 + math.sin(k * 2.3 + 1) * 10
            y = 50 - t * 40
            sp = star(W, H, x, y, 4, 2.6, 2.6, 0.9) > 0.4
            cv = pover(cv, colorize(np.full((H, W), 0.97), sp * (1.0 if t < 0.7 else 0.5), G["cyan"]))
        frames.append(cv)
    return frames_to_sheet("focus_aura", W, H, (24, 60), [("loop_s", frames, 12, True)],
                           meta={"kind": "billboard", "pivot": "feet centre"})


def perfect_flash():
    """Crisp white-gold starburst 'ting' for a perfect guard. 64x64, centre pivot."""
    W = H = 64
    cx, cy = 32, 32
    frames = []
    spec = [  # long, short, width, core, ring r, alpha
        (22, 0, 1.6, 3, 0, 1.0),
        (30, 17, 2.4, 4, 9, 1.0),
        (30, 19, 1.8, 3, 15, 1.0),
        (22, 13, 1.2, 2, 20, 0.9),
        (12, 7, 0.9, 1, 24, 0.7),
        (0, 0, 0, 0, 26, 0.45),
    ]
    for f, (rl, rs, wd, core, rr, al) in enumerate(spec):
        cv = canvas(W, H)
        if rr:
            cov, u = ring_profile(W, H, cx, cy, rr, 1.6 if f < 4 else 1.1)
            cv = pover(cv, colorize(np.clip(0.85 - 0.3 * u, 0, 1), cov * al, G["whitegold"]))
        if rl:
            n = 4 if rs == 0 else 8
            cov, t = star(W, H, cx, cy, n, rl, rs if rs else rl, wd, rot=0.0, falloff=1.4, with_t=True)
            inten = np.clip(1.05 - 0.75 * t, 0, 1)
            cv = pover(cv, colorize(inten, (cov > 0.35) * al, G["whitegold"]))
        if core:
            c = disc(W, H, cx, cy, core, 0.8)
            cv = pover(cv, colorize(np.ones((H, W)), (c > 0.5) * 1.0, G["whitegold"]))
        if 2 <= f <= 4:
            for k in range(4):
                a = math.pi / 4 + k * math.pi / 2
                rs_ = 12 + f * 4
                x, y = cx + math.cos(a) * rs_, cy + math.sin(a) * rs_
                sp = star(W, H, x, y, 4, 4 - (f - 2), 4 - (f - 2), 1.0)
                cv = pover(cv, colorize(np.full((H, W), 0.9), (sp > 0.4) * al, G["whitegold"]))
        frames.append(cv)
    return frames_to_sheet("perfect_flash", W, H, (32, 32), [("play_s", frames, 24, False)],
                           meta={"kind": "billboard", "pivot": "center"})


def hexagon(cx, cy, r, rot=0.0):
    return [(cx + math.cos(rot + k * math.pi / 3) * r, cy + math.sin(rot + k * math.pi / 3) * r) for k in range(6)]


def guard_break():
    """A guard plate cracks and shatters into shards. 48x48, centre pivot."""
    W = H = 48
    cx, cy, R = 24, 24, 14
    rng = rng_for("guard_break")
    hexp = hexagon(cx, cy, R, math.pi / 6)
    # shards: fan triangles from an off-centre impact point to pairs of rim points
    ip = (cx + 1.5, cy - 1.0)
    rim = []
    for k in range(6):
        a, b = hexp[k], hexp[(k + 1) % 6]
        rim.append(a)
        m = rng.uniform(0.35, 0.65)
        rim.append((a[0] + (b[0] - a[0]) * m, a[1] + (b[1] - a[1]) * m))
    shards = [[ip, rim[i], rim[(i + 1) % len(rim)]] for i in range(len(rim))]
    frames = []
    for f in range(6):
        cv = canvas(W, H)
        if f <= 1:
            m = polygon_f(W, H, hexp) > 0.5
            edge = m & ~(polygon_f(W, H, hexagon(cx, cy, R - 2, math.pi / 6)) > 0.5)
            cv = pover(cv, colorize(np.full((H, W), 0.45), m * 0.5, G["cyan"]))
            cv = pover(cv, colorize(np.full((H, W), 0.85), edge * 1.0, G["cyan"]))
            # cracks from the impact point
            for i in range(0, len(rim), 2 if f == 0 else 1):
                ln = seg(W, H, *ip, *rim[i], 0.55)
                cv = pover(cv, colorize(np.ones((H, W)), (ln > 0.5) * m * 1.0, G["cyan"]))
            if f == 1:
                cv = pover(cv, colorize(np.ones((H, W)), (star(W, H, *ip, 8, 12, 7, 1.8) > 0.4) * 1.0, G["white"]))
        else:
            t = (f - 1) / 4
            for i, tri in enumerate(shards):
                gx = sum(p[0] for p in tri) / 3
                gy = sum(p[1] for p in tri) / 3
                vx, vy = gx - ip[0], gy - ip[1]
                L = math.hypot(vx, vy) + 1e-6
                spd = 0.7 + 0.6 * ((i * 37) % 10) / 10
                dist = (4 + 15 * t) * spd
                ox, oy = vx / L * dist, vy / L * dist + 9 * t * t
                rot = (i % 2 * 2 - 1) * t * (0.8 + 1.6 * ((i * 53) % 7) / 7)
                pts = []
                for (px, py) in tri:
                    qx, qy = px - gx, py - gy
                    qx, qy = qx * math.cos(rot) - qy * math.sin(rot), qx * math.sin(rot) + qy * math.cos(rot)
                    pts.append((gx + ox + qx * (1 - 0.2 * t), gy + oy + qy * (1 - 0.2 * t)))
                m = polygon_f(W, H, pts) > 0.5
                e = m & ~(shift(m, 1, 1) & shift(m, -1, -1))
                al = [1, 1, 1, 0.75, 0.5, 0.25][f]
                cv = pover(cv, colorize(np.full((H, W), 0.5), m * 0.75 * al, G["cyan"]))
                cv = pover(cv, colorize(np.full((H, W), 0.95), e * al, G["cyan"]))
        frames.append(cv)
    return frames_to_sheet("guard_break", W, H, (24, 24), [("play_s", frames, 18, False)],
                           meta={"kind": "billboard", "pivot": "center"})


def feather(w, h, x, y, ang, L, width):
    """Feather-like streak: a lens-shaped vane (widest near the base third) with a quill.
    Returns (vane coverage, shaft coverage)."""
    ca, sa = math.cos(ang), math.sin(ang)
    nx, ny = -sa, ca
    left, right = [], []
    for k in range(9):
        t = k / 8
        wd = width * 2.0 * math.sin(math.pi * min(1.0, t * 1.15)) ** 0.7 * (1 - 0.35 * t)
        px, py = x + ca * L * t, y + sa * L * t
        left.append((px + nx * wd, py + ny * wd))
        right.append((px - nx * wd * 0.8, py - ny * wd * 0.8))
    vane = polygon_f(w, h, left + right[::-1]) > 0.5
    shaft = seg(w, h, x - ca * 2, y - sa * 2, x + ca * L * 0.85, y + sa * L * 0.85, 0.5) > 0.5
    return vane, shaft


def ko_burst():
    """Big KO burst with feather-like streaks flying outward. 64x64, centre pivot."""
    W = H = 64
    cx, cy = 32, 32
    rng = rng_for("ko_burst")
    feathers = [(k * math.tau / 9 + rng.uniform(-0.15, 0.15), rng.uniform(0.85, 1.15)) for k in range(9)]
    frames = []
    for f in range(8):
        cv = canvas(W, H)
        t = f / 7
        if f == 0:
            cov, tt = star(W, H, cx, cy, 8, 16, 9, 2.6, with_t=True)
            cv = pover(cv, colorize(np.clip(1.05 - 0.7 * tt, 0, 1), (cov > 0.35) * 1.0, G["whitegold"]))
            c = disc(W, H, cx, cy, 5, 1.0)
            cv = pover(cv, colorize(np.ones((H, W)), (c > 0.5) * 1.0, G["whitegold"]))
        if 1 <= f <= 3:
            rr = 6 + f * 7
            cov, u = ring_profile(W, H, cx, cy, rr, 4.2 - f)
            cv = pover(cv, colorize(np.clip(0.9 - 0.4 * u, 0, 1), cov * (1.0 if f < 3 else 0.75), G["aether"]))
        if f == 1:
            c = disc(W, H, cx, cy, 6, 1.0)
            cv = pover(cv, colorize(np.ones((H, W)), (c > 0.5) * 1.0, G["whitegold"]))
        if 1 <= f <= 6:
            for (a, k) in feathers:
                r0 = (6 + 21 * t ** 0.7) * k
                L = (8 + 5 * math.sin(t * math.pi)) * k
                x, y = cx + math.cos(a) * r0, cy + math.sin(a) * r0 + 5 * t * t
                fa = a + 0.4 * t
                vane, shaft = feather(W, H, x, y, fa, L, 1.25)
                al = 1.0 if f < 5 else (0.75 if f == 5 else 0.5)
                grad = G["whitegold"] if f < 4 else G["aether"]
                cv = pover(cv, colorize(np.full((H, W), 0.85 - 0.25 * t), vane * al, grad))
                cv = pover(cv, colorize(np.full((H, W), 0.35), (shaft & vane) * al, grad))
        if f >= 4:
            for k in range(7):
                a = k * 0.9 + 0.3
                r = 18 + 10 * t + (k % 3) * 3
                x, y = cx + math.cos(a) * r, cy + math.sin(a) * r + (f - 4) * 2
                sp = star(W, H, x, y, 4, 2.5, 2.5, 0.9)
                cv = pover(cv, colorize(np.full((H, W), 0.9), (sp > 0.4) * (1.0 if f < 7 else 0.5), G["aether"]))
        frames.append(cv)
    return frames_to_sheet("ko_burst", W, H, (32, 32), [("play_s", frames, 16, False)],
                           meta={"kind": "billboard", "pivot": "center"})


HEART = [".hh.hh.", "hwhhhhs", "hhhhhhs", ".hhhhs.", "..hhs..", "...s..."]
HEART_S = [".h.h.", "hwhhs", ".hhs.", "..s.."]


def trust_motes():
    """Tiny warm hearts and sparkles floating up. 16x16, centre pivot, loops."""
    W = H = 16
    frames = []
    cols = {"h": RA["sigil"][4], "w": RA["sigil"][5], "s": RA["sigil"][3]}
    for f in range(4):
        cv = canvas(W, H)
        for (x, ph, bm) in ((5, 0.0, HEART), (11, 0.5, HEART_S)):
            t = ((f / 4) + ph) % 1.0
            y = 12 - t * 8
            al = 1.0 if t < 0.6 else 0.5
            stamp(cv, x + (1 if (f % 2 and ph) else 0), y, bm, cols, alpha=al)
        for (x, ph) in ((9, 0.25), (3, 0.75)):
            t = ((f / 4) + ph) % 1.0
            y = 13 - t * 10
            c = RA["gold"][5].copy()
            c[3] = 255 if t < 0.5 else 128
            if 1 <= int(y) < H - 1:
                cv[int(y), x] = c
                if t < 0.5:
                    for (dx, dy) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        c2 = RA["gold"][4].copy()
                        c2[3] = 128
                        if 1 <= int(y) + dy < H - 1:
                            cv[int(y) + dy, x + dx] = c2
        frames.append(cv)
    return frames_to_sheet("trust_motes", W, H, (8, 8), [("loop_s", frames, 8, True)],
                           meta={"kind": "billboard", "pivot": "center"})


def sigil_glow():
    """A magenta sigil circle pulsing. 32x32, centre pivot, loops."""
    W = H = 32
    cx, cy = 16, 16
    frames = []
    for f in range(4):
        p = [0.55, 0.85, 1.0, 0.8][f]
        cv = canvas(W, H)
        halo = ring(W, H, cx, cy, 12.5, 5.0, 1.5)
        cv = pover(cv, colorize(np.full((H, W), 0.35 * p), halo * 0.25 * p * 2, G["sigil"]))
        outer, u = ring_profile(W, H, cx, cy, 12.5, 2.2)
        cv = pover(cv, colorize(np.clip(0.55 + 0.35 * p - 0.2 * u, 0, 1), outer * 1.0, G["sigil"]))
        inner, u2 = ring_profile(W, H, cx, cy, 8.5, 1.1)
        cv = pover(cv, colorize(np.full((H, W), 0.5 + 0.35 * p), inner * 1.0, G["sigil"]))
        # rune ticks between the rings
        for k in range(8):
            a = k * math.tau / 8 + math.pi / 8
            x0, y0 = cx + math.cos(a) * 9.6, cy + math.sin(a) * 9.6
            x1, y1 = cx + math.cos(a + 0.18) * 11.2, cy + math.sin(a + 0.18) * 11.2
            tk = seg(W, H, x0, y0, x1, y1, 0.5) > 0.5
            cv = pover(cv, colorize(np.full((H, W), 0.6 + 0.3 * p), tk * 1.0, G["sigil"]))
        # inner triangle
        tri = [(cx + math.cos(-math.pi / 2 + k * math.tau / 3) * 7, cy + math.sin(-math.pi / 2 + k * math.tau / 3) * 7)
               for k in range(3)]
        for k in range(3):
            ln = seg(W, H, *tri[k], *tri[(k + 1) % 3], 0.55) > 0.5
            cv = pover(cv, colorize(np.full((H, W), 0.5 + 0.4 * p), ln * 1.0, G["sigil"]))
        c = disc(W, H, cx, cy, 1.6, 0.6)
        cv = pover(cv, colorize(np.full((H, W), 0.7 + 0.3 * p), (c > 0.5) * 1.0, G["sigil"]))
        frames.append(cv)
    return frames_to_sheet("sigil_glow", W, H, (16, 16), [("loop_s", frames, 8, True)],
                           meta={"kind": "billboard", "pivot": "center"})


# ---- emotes ---------------------------------------------------------------------

EMOTES = {
    "exclaim": ("gold", [
        "..oooo..",
        "..ohho..",
        "..ohho..",
        "..ohso..",
        "..ohso..",
        "..ohso..",
        "...oo...",
        "..oooo..",
        "..ohso..",
        "..oooo..",
    ]),
    "question": ("cloth_cream", [
        "..oooo..",
        ".ohhhho.",
        "ohsoohso",
        ".oo.ohso",
        "...ohso.",
        "..ohso..",
        "..ooo...",
        "..oooo..",
        "..ohso..",
        "..oooo..",
    ]),
    "heart": ("sigil", [
        ".ooo.ooo.",
        "ohwhohhho",
        "ohhhhhhso",
        "ohhhhhhso",
        ".ohhhhso.",
        "..ohhso..",
        "...oso...",
        "....o....",
    ]),
    "note": ("cloth_blue", [
        "....oooo.",
        "....ohho.",
        "....ohoho",
        "....oo.oo",
        "....o....",
        "..ooo....",
        ".ohhho...",
        ".ohhso...",
        "..ooo....",
    ]),
    "sweat": ("water", [
        "..o...",
        ".oho..",
        ".ohho.",
        "ohwhso",
        "ohhhso",
        ".ohso.",
        "..oo..",
    ]),
    "anger": ("cloth_red", [
        ".oo..oo.",
        "ohho.ohho",
        "oho...oho",
        ".........",
        "oho...oho",
        "ohho.ohho",
        ".oo..oo..",
    ]),
    "zzz": ("aether", [
        "........ooooo",
        "........ohhho",
        "........oohoo",
        "........ohooo",
        "ooooooo.ohhho",
        "ohhhhho.ooooo",
        "ooooho.......",
        "..ohho.......",
        ".ohoooo......",
        "ohhhhho......",
        "ooooooo......",
    ]),
}


def emote_cols(rname):
    n = len(RA[rname])
    cols = {"o": RA[rname][0] if rname not in ("cloth_cream",) else RA["ink"][1],
            "s": RA[rname][max(1, n - 3)], "h": RA[rname][n - 2], "w": RA[rname][n - 1]}
    if rname == "cloth_blue":  # brighter note so it reads on dark scenes
        cols["h"] = RA[rname][n - 1]
        cols["s"] = RA[rname][n - 2]
    return cols


def anger_mark(cv, cx, cy, r=4.2, spread=4.6):
    """Classic 'popping vein' mark: four arcs bulging toward the centre, with gaps between them."""
    xs, ys = fgrid(16, 16)
    m = np.zeros((16, 16), bool)
    for sx in (-1, 1):
        for sy in (-1, 1):
            ox, oy = cx + sx * spread, cy + sy * spread
            d = np.hypot(xs - ox, ys - oy)
            # keep only the quarter of the circle that faces the centre
            facing = ((cx - ox) * (xs - ox) > 0) & ((cy - oy) * (ys - oy) > 0)
            m |= (np.abs(d - r) < 0.85) & facing
    hi = m & (shift(~m, 1, 0) | shift(~m, 0, 1))
    cv[m] = RA["cloth_red"][4]
    cv[hi] = RA["cloth_red"][5]
    from kit import outline as _outline
    out = _outline(cv, "outer")
    cv[...] = out


def emotes():
    W = H = 16
    sb = SheetBuilder("emotes", W, H, (8, 15), columns=8, meta={"kind": "billboard emotes", "pivot": "bottom-center"})
    for name, (rname, bm) in EMOTES.items():
        frames = []
        for f in range(2):
            cv = canvas(W, H)
            bh = len(bm)
            y = 14 - bh // 2 - (1 if f == 1 else 0)
            x = 8
            if name == "sweat":
                x, y = 5, 7 + f
            if name == "zzz":
                x = 8 + (1 if f else 0)
            if name == "anger":
                anger_mark(cv, 8.0, 8.5 - f * 0.5, r=3.0 + f * 0.25, spread=5.0 + f * 0.25)
            else:
                stamp(cv, x, y - (bh // 2) + bh // 2, bm, emote_cols(rname))
            frames.append(to_image(finish_frame(cv)))
        sb.add_animation(name + "_s", frames, fps=4, loop=True)
    png = sb.save(OUT_FX)
    contact_sheet(png, scale=4, out_path=os.path.join(PREVIEW_DIR, "fx_emotes.png"))
    return png


# --------------------------------------------------------------------------
# ground effects (top-down, forward = +X, pivot = frame centre)
# --------------------------------------------------------------------------


def polar(w, h, cx, cy):
    xs, ys = fgrid(w, h)
    dx, dy = xs - cx, ys - cy
    return np.hypot(dx, dy), np.arctan2(dy, dx)


def polar_noise(w, h, cx, cy, rng, n_ang=24, n_rad=6, scroll=0.0):
    """Noise sampled in polar coordinates (radial streaks) - periodic in angle."""
    d, a = polar(w, h, cx, cy)
    base = fbm(64, 64, 4, 3, rng)
    u = ((a / math.tau) % 1.0) * 64 * (n_ang / 24)
    v = (d / (w / 2)) * 64 * (n_rad / 6) + scroll
    return base[(v.astype(int)) % 64, (u.astype(int)) % 64]


def streak_noise(w, h, cx, cy, rng, ang_cycles=40, rad_cycles=2.0, rad_scale=48.0):
    """Polar noise with many angular cycles and few radial ones -> radial flame streaks."""
    d, a = polar(w, h, cx, cy)
    tex = fbm(128, 64, 8, 3, rng, cells_y=4)
    u = ((a / math.tau) % 1.0) * 128 * (ang_cycles / 8)
    v = (d / rad_scale) * 64 * (rad_cycles / 4)
    return tex[(v.astype(int)) % 64, (u.astype(int)) % 128]


def cinder_arc():
    """Fan of fire ~110 degrees wide sweeping open toward +X, apex at the centre. 96x96."""
    W = H = 96
    cx = cy = 48
    rng = rng_for("cinder_arc")
    d, a = polar(W, H, cx, cy)
    half = math.radians(55)
    st = streak_noise(W, H, cx, cy, rng, 44, 1.5)
    tip = streak_noise(W, H, cx, cy, rng, 70, 0.5)
    mott = noise(W, H, rng, 6, 2)
    frames = []
    spec = [(-half, -half * 0.2, 38, 1.0, 1.0), (-half, half * 0.5, 42, 1.0, 1.0), (-half, half, 44, 1.0, 1.0),
            (-half, half, 45, 0.75, 1.0), (-half, half, 46, 0.5, 0.75)]
    for f, (a0, a1, R, heat, al) in enumerate(spec):
        r_out = R * (0.78 + 0.3 * tip)
        r_in = 7 + 4 * st
        ang_ok = (a >= a0) & (a <= a1)
        # soften the fan's side edges with tongues as well
        side = np.minimum(a - a0, a1 - a)
        inside = ang_ok & (d <= r_out) & (d >= r_in) & (side * d > (1 - st) * 2.0)
        t = np.clip((d - r_in) / np.maximum(r_out - r_in, 1), 0, 1)
        lead = np.clip(1 - (a1 - a) / math.radians(45), 0, 1) if f < 2 else np.zeros_like(a)
        hv = heat * (0.08 + 0.62 * t ** 1.1 + 0.4 * (st - 0.5) + 0.22 * lead) - 0.12 * (t > 0.93)
        if f >= 3:
            inside &= mott > 0.22 + 0.15 * (f - 3)
        cv = canvas(W, H)
        if f >= 2:
            sc = ang_ok & (d <= R * 0.9) & (d >= 6) & (mott > 0.3)
            cv = pover(cv, colorize(np.full((H, W), 0.35), sc * (0.5 if f < 4 else 0.25), G["soot"]))
        cv = pover(cv, colorize(np.clip(hv, 0, 1), inside * al, G["fire_hot"]))
        if f >= 2:
            for k in range(16):
                ang = -half + (k + 0.5) / 16 * 2 * half
                rr = R + 1 + (f - 2) * 3 + (k % 3) * 2
                x, y = cx + math.cos(ang) * rr, cy + math.sin(ang) * rr
                if 1 <= x < W - 1 and 1 <= y < H - 1:
                    c = G["fire"][5 if f < 4 else 3].copy()
                    c[3] = 255 if f < 4 else 128
                    cv[int(y), int(x)] = c
        frames.append(cv)
    return frames_to_sheet("cinder_arc", W, H, (48, 48), [("play_s", frames, 20, False)],
                           meta={"kind": "ground (top-down)", "pivot": "center", "forward": "+X",
                                 "arc_degrees": 110})


def heat_ring():
    """A ring of fire erupting outward from the centre and fading. 96x96, top-down."""
    W = H = 96
    cx = cy = 48
    rng = rng_for("heat_ring")
    d, a = polar(W, H, cx, cy)
    pn = polar_noise(W, H, cx, cy, rng, 48, 8)
    frames = []
    spec = [(6, 7, 1.0), (13, 8, 1.0), (21, 8, 1.0), (28, 7, 0.95), (34, 6, 0.8), (39, 5, 0.65), (43, 4, 0.45),
            (45, 3, 0.3)]
    for f, (R, th, heat) in enumerate(spec):
        tong = (pn - 0.5) * th * 1.2
        u = (d - R - tong * 0.5) / (th / 2)
        inside = (np.abs(u) <= 1) | ((u > 1) & (u < 1 + (pn - 0.45) * 2.5))
        hv = heat * (0.85 - 0.35 * np.clip(u, -1, 1.5)) + (pn - 0.5) * 0.3
        if f >= 5:
            inside &= pn > 0.2 + 0.1 * (f - 5)
        al = 1.0 if f < 6 else (0.75 if f == 6 else 0.5)
        cv = canvas(W, H)
        if f >= 2:
            sc = (d < R - th * 0.6) & (d > R - th * 0.6 - 6) & (pn > 0.4)
            cv = pover(cv, colorize(np.full((H, W), 0.35), sc * 0.25, G["soot"]))
        cv = pover(cv, colorize(np.clip(hv, 0, 1), inside * al, G["fire_hot"]))
        frames.append(cv)
    return frames_to_sheet("heat_ring", W, H, (48, 48), [("play_s", frames, 16, False)],
                           meta={"kind": "ground (top-down)", "pivot": "center"})


def crack_lines(w, h, cx, cy, rng, n=6, length=30, branch=True, jitter=0.45):
    """Radial jagged cracks from (cx, cy): returns list of polylines."""
    out = []
    for k in range(n):
        a = k * math.tau / n + rng.uniform(-0.3, 0.3)
        pts = [(cx + math.cos(a) * 3, cy + math.sin(a) * 3)]
        L = length * rng.uniform(0.7, 1.1)
        step = 3.0
        x, y = pts[0]
        ang = a
        dist = 0
        while dist < L:
            ang += rng.uniform(-jitter, jitter)
            ang = a + max(-0.6, min(0.6, ang - a))
            x += math.cos(ang) * step
            y += math.sin(ang) * step
            dist += step
            pts.append((x, y))
            if branch and rng.random() < 0.18 and dist > 8:
                b = ang + rng.choice([-1, 1]) * rng.uniform(0.5, 0.9)
                bp = [(x, y)]
                bx, by = x, y
                for _ in range(int(rng.integers(2, 4))):
                    bx += math.cos(b) * step
                    by += math.sin(b) * step
                    bp.append((bx, by))
                out.append(bp)
        out.append(pts)
    return out


def draw_cracks(w, h, cracks, frac=1.0, width=0.6):
    """Coverage of cracks revealed up to `frac` of their length."""
    cov = np.zeros((h, w))
    for pts in cracks:
        n = max(2, int(round(len(pts) * frac)))
        if n >= 2:
            cov = np.maximum(cov, polyline(w, h, pts[:n], width, width * 0.6))
    return cov > 0.5


def shockwave():
    """Dusty shockwave ring expanding, with cracks spreading. 96x96, top-down."""
    W = H = 96
    cx = cy = 48
    rng = rng_for("shockwave")
    d, a = polar(W, H, cx, cy)
    pn = polar_noise(W, H, cx, cy, rng, 40, 6)
    cracks = crack_lines(W, H, cx, cy, rng, n=7, length=30)
    frames = []
    spec = [(9, 9, 1.0), (17, 9, 1.0), (25, 8, 0.9), (32, 7, 0.75), (38, 6, 0.55), (43, 5, 0.35)]
    for f, (R, th, al) in enumerate(spec):
        cv = canvas(W, H)
        cr = draw_cracks(W, H, cracks, frac=min(1.0, 0.35 + f * 0.25))
        lip = shift(cr, 1, 1) & ~cr
        cv = pover(cv, colorize(np.full((H, W), 0.75), lip * min(1.0, al + 0.25), G["dirt"]))
        cv = pover(cv, colorize(np.full((H, W), 0.05), cr * min(1.0, al + 0.25), G["dirt"]))
        u = (d - R) / (th / 2)
        band = (np.abs(u) <= 1) & (pn > 0.18 + 0.08 * f)
        # dust: bright leading edge, darker trailing inside
        hv = 0.75 - 0.3 * u + (pn - 0.5) * 0.3
        cv = pover(cv, colorize(np.clip(hv, 0, 1), band * al, G["dust"]))
        # debris specks on the front
        for k in range(16):
            ang = k * math.tau / 16 + 0.2 * f
            rr = R + th * 0.6 + (k % 3)
            x, y = cx + math.cos(ang) * rr, cy + math.sin(ang) * rr
            if 1 <= x < W - 1 and 1 <= y < H - 1:
                c = RA["stone_warm"][4 if k % 2 else 2].copy()
                c[3] = int(255 * min(1.0, al + 0.25))
                cv[int(y), int(x)] = c
        frames.append(cv)
    return frames_to_sheet("shockwave", W, H, (48, 48), [("play_s", frames, 18, False)],
                           meta={"kind": "ground (top-down)", "pivot": "center"})


def ground_crack():
    """Cracked-earth decal that fades out over the frames. 64x64, top-down."""
    W = H = 64
    cx = cy = 32
    rng = rng_for("ground_crack")
    d, a = polar(W, H, cx, cy)
    cracks = crack_lines(W, H, cx, cy, rng, n=8, length=26, jitter=0.5)
    cr = draw_cracks(W, H, cracks, 1.0, 0.7)
    wide = draw_cracks(W, H, cracks[:4], 0.5, 1.2)
    pn = noise(W, H, rng, 6, 2)
    crater = (d < 6.5 + (pn - 0.5) * 3)
    rim = (d < 9 + (pn - 0.5) * 3) & ~crater
    frames = []
    for f, al in enumerate([1.0, 0.75, 0.5, 0.25]):
        cv = canvas(W, H)
        # trampled earth around the impact
        dirt = (d < 14 + (pn - 0.5) * 8) & (pn > 0.3)
        cv = pover(cv, colorize(np.full((H, W), 0.25), dirt * al * 0.5, G["dirt"]))
        cv = pover(cv, colorize(np.full((H, W), 0.7), rim * al, G["dirt"]))
        cv = pover(cv, colorize(np.full((H, W), 0.15), crater * al, G["dirt"]))
        lip = shift(cr | wide, 1, 1) & ~(cr | wide)
        cv = pover(cv, colorize(np.full((H, W), 0.8), lip * al, G["dirt"]))
        cv = pover(cv, colorize(np.full((H, W), 0.02), (cr | wide) * al, G["dirt"]))
        frames.append(cv)
    return frames_to_sheet("ground_crack", W, H, (32, 32), [("play_s", frames, 6, False)],
                           meta={"kind": "ground decal (top-down)", "pivot": "center"})


def scorch():
    """Scorch mark with dying embers, fading. 48x48, top-down."""
    W = H = 48
    cx = cy = 24
    rng = rng_for("scorch")
    d, a = polar(W, H, cx, cy)
    pn = noise(W, H, rng, 5, 3)
    pn2 = noise(W, H, rng, 10, 2)
    R = 15 * (0.85 + 0.35 * pn)
    blot = d < R
    inten = np.clip(0.15 + (d / R) * 0.55 + (pn2 - 0.5) * 0.3, 0, 1)
    embers = blot & (pn2 > 0.72) & (d < R * 0.8)
    frames = []
    for f, al in enumerate([1.0, 0.75, 0.5, 0.25]):
        cv = canvas(W, H)
        edge = blot & (d > R * 0.7)
        a_field = np.where(edge, 0.75, 1.0) * al
        cv = pover(cv, colorize(inten, blot * a_field, G["soot"]))
        if f < 3:
            em = embers & (pn2 > 0.72 + f * 0.06)
            cv = pover(cv, colorize(np.full((H, W), 0.55 - 0.15 * f), em * 1.0, G["fire"]))
        frames.append(cv)
    return frames_to_sheet("scorch", W, H, (24, 24), [("play_s", frames, 4, False)],
                           meta={"kind": "ground decal (top-down)", "pivot": "center"})


FX = {
    "hit_spark": hit_spark,
    "hit_heavy": hit_heavy,
    "dust_puff": dust_puff,
    "stun_stars": stun_stars,
    "ember_bolt": ember_bolt,
    "ember_impact": ember_impact,
    "flash_strike": flash_strike,
    "fire_pillar": fire_pillar,
    "burn_flame": burn_flame,
    "boulder": boulder,
    "rock_burst": rock_burst,
    "fault_spike": fault_spike,
    "stone_guard": stone_guard,
    "focus_aura": focus_aura,
    "perfect_flash": perfect_flash,
    "guard_break": guard_break,
    "ko_burst": ko_burst,
    "trust_motes": trust_motes,
    "sigil_glow": sigil_glow,
    "emotes": emotes,
    "cinder_arc": cinder_arc,
    "heat_ring": heat_ring,
    "shockwave": shockwave,
    "ground_crack": ground_crack,
    "scorch": scorch,
}


def build(only=None):
    out = []
    for name, fn in FX.items():
        if only and name not in only:
            continue
        out.append(fn())
    return out


if __name__ == "__main__":
    import sys
    build(sys.argv[1:] or None)
