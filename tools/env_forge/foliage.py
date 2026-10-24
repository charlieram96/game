"""Group B - foliage and nature sprites (single PNGs, pivot bottom-centre).

Trees are billboard cut-outs built from:
  * limbs  - tapered polylines with cylinder shading (bark ramp), grain and roots
  * canopy - a "sphere of leaf clusters": clusters near the canopy centre sit in front,
             every cluster is a union of small leaf blobs (scalloped edge + scaly texture),
             shading = global volume + cluster volume + leaf bumps, front clusters cast
             shadows down-right onto the ones behind, the underside falls into deep shade.
Light comes from the upper-left; outlines use the darkest shade of the local ramp.
"""

from __future__ import annotations

import math
import os

import numpy as np

from kit import (C, LIGHT, OUT_ENV, RA, alpha, bezier, binarize, border_ok, canvas, clear_border, composite, dilate,
                 ellipse_mask, erode, fbm, grid, grid_preview, levels, norm01, outline, poisson, poly_mask, preview,
                 put, ramp_of, rng_for, save_png, scene_preview, shift, spectral, stroke, taper_mask)

OUT = os.path.join(OUT_ENV, "foliage")
MODE = os.environ.get("CANOPY_MODE", "bands")

L3 = LIGHT  # (x right, y down, z toward viewer)


# --------------------------------------------------------------------------
# limbs (trunks, branches, roots)
# --------------------------------------------------------------------------


def limb_field(w, h, path, w0, w1):
    """Distance field of a tapered polyline. Returns (inside, u, t): u in -1..1 across, t 0..1 along."""
    xs, ys = grid(w, h)
    px = xs + 0.5
    py = ys + 0.5
    P = np.asarray(path, float)
    seg_len = np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1]))
    cum = np.concatenate([[0], np.cumsum(seg_len)])
    total = cum[-1]
    best = np.full((h, w), 1e9)
    U = np.zeros((h, w))
    T = np.zeros((h, w))
    for i in range(len(P) - 1):
        ax, ay = P[i]
        bx, by = P[i + 1]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy + 1e-9
        s = np.clip(((px - ax) * dx + (py - ay) * dy) / L2, 0, 1)
        cx = ax + s * dx
        cy = ay + s * dy
        t = (cum[i] + s * seg_len[i]) / total
        half = (w0 + (w1 - w0) * t) / 2
        ex, ey = px - cx, py - cy
        d = np.hypot(ex, ey)
        nd = d / np.maximum(half, 0.3)
        # signed side: cross product sign (left of direction = negative u)
        side = np.sign(dx * ey - dy * ex)
        upd = nd < best
        best = np.where(upd, nd, best)
        U = np.where(upd, side * nd, U)
        T = np.where(upd, t, T)
    inside = best <= 1.0
    return inside, U, T


def draw_limb(cv, path, w0, w1, rng, name="bark", lo=1, hi=4, grain=True, zbuf=None, light_side=-1, dark_edge=True,
              furrows=0):
    """Cylinder-shaded limb. light_side=-1: the lit side is image-left. furrows: number of bark furrows."""
    h, w = cv.shape[:2]
    inside, U, T = limb_field(w, h, path, w0, w1)
    # cylinder normal across the limb; light from the left/up-left
    nx = np.clip(U, -1, 1)
    # orientation of the limb: for mostly vertical limbs, u<0 is left side
    P = np.asarray(path, float)
    dirx = P[-1, 0] - P[0, 0]
    diry = P[-1, 1] - P[0, 1]
    # flip so that negative u means the side facing image-left/up
    flip = 1.0
    if abs(dirx) > abs(diry):
        flip = -1.0 if dirx > 0 else 1.0  # horizontal limb going right: left side of travel is up
    else:
        flip = 1.0 if diry < 0 else -1.0
    nx = nx * flip
    nz = np.sqrt(np.clip(1 - nx * nx, 0, 1))
    sh = np.clip(-nx * 0.75 + nz * 0.55, 0, 1)
    if grain:
        g = fbm(w, h, 12, 2, rng, cells_y=3)
        sh = sh + (g - 0.5) * 0.35
    n = hi - lo + 1
    k = lo + np.clip((sh * n).astype(int), 0, n - 1)
    if furrows:
        total = float(np.hypot(np.diff(np.asarray(path)[:, 0]), np.diff(np.asarray(path)[:, 1])).sum())
        wob = np.sin(T * total / 5.0 + rng.uniform(0, 6)) * 0.12 + np.sin(T * total / 2.3 + rng.uniform(0, 6)) * 0.06
        ph = (U * flip + wob) * furrows * 0.5 + 0.5
        fr = np.abs(ph - np.round(ph))  # 0 on a furrow line
        # broken furrows: gaps along the length
        gap = np.sin(T * total / 3.1 + U * 3 + rng.uniform(0, 6)) > 0.72
        furrow = (fr < 0.11) & ~gap & (np.abs(U) < 0.92)
        ridge = (fr >= 0.11) & (fr < 0.22) & ~gap & (U * flip < 0.3)
        k = np.where(furrow, np.maximum(lo, k - 2), k)
        k = np.where(ridge & ~furrow, np.minimum(hi, k + 1), k)
    if dark_edge:
        k = np.where(nx > 0.72, lo, k)
    cols = RA[name][np.clip(k, 0, len(RA[name]) - 1)]
    cv[inside] = cols[inside]
    return inside


def bark_marks(cv, mask, rng, name="bark", n=10, vertical=True):
    """Short vertical bark furrows inside a mask."""
    h, w = mask.shape
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return
    for _ in range(n):
        i = int(rng.integers(len(xs)))
        x, y = xs[i], ys[i]
        L = int(rng.integers(2, 6))
        for j in range(L):
            yy = y + j if vertical else y
            xx = x if vertical else x + j
            if 0 <= xx < w and 0 <= yy < h and mask[yy, xx]:
                info = ramp_of(cv[yy, xx])
                if info and info[0] == name:
                    cv[yy, xx] = RA[name][max(0, info[1] - 1)]


# --------------------------------------------------------------------------
# canopy
# --------------------------------------------------------------------------


class Canopy:
    """Accumulates leaf clusters, then renders them with depth-sorted shading."""

    def __init__(self, w, h, cx, cy, rx, ry, rng, ramp="leaf", leaf_r=(1.6, 2.5), leaf_spacing=2.3):
        self.w, self.h = w, h
        self.cx, self.cy, self.rx, self.ry = cx, cy, rx, ry
        self.rng = rng
        self.ramp = ramp
        self.leaf_r = leaf_r
        self.leaf_spacing = leaf_spacing
        self.clusters: list[dict] = []
        self.stack = -0.6

    def add(self, x, y, r, z=None, tone=0.0, squash=1.0):
        # keep the cluster (plus its bumpy rim and outline) inside the canvas
        margin = 2.0 + 0.1 * r
        r = min(r, (self.w - 2 * margin) / 2)
        x = min(max(x, margin + r), self.w - margin - r)  # nudge inward instead of clipping
        y = max(y, margin + r * squash)
        if z is None:
            u = (x - self.cx) / self.rx
            v = (y - self.cy) / self.ry
            zs = math.sqrt(max(0.0, 1 - min(1.0, u * u + v * v)))
            if self.stack >= 0:
                zh = 0.5 - 0.5 * max(-1.0, min(1.0, v))  # upper clusters overhang the lower ones
            else:
                zh = 0.5 + 0.5 * max(-1.0, min(1.0, v))  # lower clusters in front (lit tops over dark bottoms)
            st = abs(self.stack)
            z = st * zh + (1 - st) * zs + self.rng.uniform(-0.06, 0.06)
        self.clusters.append(dict(x=x, y=y, r=r, z=z, tone=tone, squash=squash))

    def fill_envelope(self, spacing, rmin, rmax, envelope=None, rim_bias=0.0):
        """Poisson-fill the canopy ellipse (or a custom envelope mask) with clusters."""
        pts = poisson(self.w, self.h, spacing, self.rng, wrap=False)
        for (x, y) in pts:
            u = (x - self.cx) / self.rx
            v = (y - self.cy) / self.ry
            inside = (u * u + v * v) <= 1.0 if envelope is None else envelope[int(y), int(x)]
            if inside:
                rr = self.rng.uniform(rmin, rmax)
                self.add(x, y, rr)

    def _blobs(self, c):
        rng = self.rng
        x0, y0, r, sq = c["x"], c["y"], c["r"], c["squash"]
        blobs = []
        n_rim = max(6, int(2 * math.pi * r / self.leaf_spacing))
        a0 = rng.uniform(0, math.tau)
        for k in range(n_rim):
            a = a0 + k * math.tau / n_rim + rng.uniform(-0.15, 0.15)
            rr = r - rng.uniform(0.6, 1.6)
            blobs.append((x0 + math.cos(a) * rr, y0 + math.sin(a) * rr * sq, rng.uniform(*self.leaf_r)))
        inner = poisson(int(2 * r + 2), int(2 * r + 2), self.leaf_spacing * 1.05, rng, wrap=False)
        for (ix, iy) in inner:
            bx = x0 - r - 1 + ix
            by = y0 + (iy - r - 1) * sq
            if (bx - x0) ** 2 + ((by - y0) / sq) ** 2 <= (r - 1.2) ** 2:
                blobs.append((bx, by, rng.uniform(*self.leaf_r)))
        # nearer the cluster centre = in front; lower blobs slightly in front
        blobs.sort(key=lambda b: -((b[0] - x0) ** 2 + ((b[1] - y0) / sq) ** 2) + b[1] * 0.08)
        return blobs

    def render(self, cv, light_w=(0.36, 0.44, 0.0), under=0.6, ao=0.5, thresholds=None, lut=None,
               cast=0.28, holes=0, hole_col=1, micro=(0.42, 0.78), edge_dark=True, lo_idx=1, hi_idx=None):
        w, h = self.w, self.h
        rng = self.rng
        Lx, Ly, Lz = L3
        R = RA[self.ramp]
        hi_idx = len(R) - 1 if hi_idx is None else hi_idx
        own = np.full((h, w), -1)
        ownz = np.full((h, w), -1.0)
        blob_id = np.full((h, w), -1)
        mic = np.zeros((h, w), int)
        blobs_all = []  # (cluster, bx, by, br, macro)
        order = sorted(range(len(self.clusters)), key=lambda i: self.clusters[i]["z"])
        for ci in order:
            c = self.clusters[ci]
            x0, y0, r, sq = c["x"], c["y"], c["r"], c["squash"]
            for (bx, by, br) in self._blobs(c):
                cu = (bx - x0) / (r + 1)
                cv_ = (by - y0) / ((r + 1) * sq)
                cz = math.sqrt(max(0.0, 1 - min(1.0, cu * cu + cv_ * cv_)))
                sc = cu * Lx + cv_ * Ly + cz * Lz
                gu = (bx - self.cx) / self.rx
                gv = (by - self.cy) / self.ry
                gz = math.sqrt(max(0.0, 1 - min(1.0, gu * gu + gv * gv)))
                sg = gu * Lx + gv * Ly + gz * Lz
                m = light_w[0] * sg + light_w[1] * sc - ao * (1 - c["z"]) * 0.5 + c["tone"] - under * max(0.0, gv) ** 2
                bi = len(blobs_all)
                blobs_all.append([ci, bx, by, br, m])
                xa, xb = int(math.floor(bx - br)), int(math.ceil(bx + br))
                ya, yb = int(math.floor(by - br)), int(math.ceil(by + br))
                for py in range(max(0, ya), min(h, yb + 1)):
                    for px in range(max(0, xa), min(w, xb + 1)):
                        lu = (px + 0.5 - bx) / br
                        lv = (py + 0.5 - by) / br
                        rr2 = lu * lu + lv * lv
                        if rr2 > 1.0:
                            continue
                        lz = math.sqrt(1 - rr2)
                        sl = lu * Lx + lv * Ly + lz * Lz
                        own[py, px] = ci
                        ownz[py, px] = c["z"]
                        blob_id[py, px] = bi
                        mic[py, px] = (1 if sl > micro[1] else 0) - (1 if sl < micro[0] else 0)
        mask = own >= 0
        # cast shadows from nearer clusters: per blob (so leaf scales stay coherent)
        shadowed = np.zeros((h, w), bool)
        contact = np.zeros((h, w), bool)
        for (dx, dy) in ((1, 1), (0, 1), (1, 0), (2, 2), (1, 2), (2, 1), (3, 3), (2, 3), (3, 2), (4, 4), (3, 4)):
            src_z = shift(ownz, dx, dy, fill=-1.0)
            src_o = shift(own, dx, dy, fill=-1)
            hit = mask & (src_o >= 0) & (src_o != own) & (src_z > ownz + 0.02)
            shadowed |= hit
            if max(dx, dy) <= 1:
                contact |= hit
        for bi, b in enumerate(blobs_all):
            bx, by = int(b[1]), int(b[2])
            if 0 <= bx < w and 0 <= by < h and shadowed[by, bx]:
                b[4] -= cast
        thresholds = thresholds or [0.1, 0.3, 0.47, 0.64, 0.8, 0.93]
        lut = lut or [1, 2, 3, 4, 5, 6, 6]
        base = np.zeros(len(blobs_all), int)
        for bi, b in enumerate(blobs_all):
            k = sum(1 for t in thresholds if b[4] >= t)
            base[bi] = lut[k]
        idx = np.zeros((h, w), int)
        idx[mask] = base[blob_id[mask]] + mic[mask]
        # top highlight only on blobs that are already bright; dark rims stay >= lo_idx
        idx = np.clip(idx, lo_idx, hi_idx)
        if edge_dark:
            idx = np.where(contact, np.clip(idx - 1, lo_idx, hi_idx), idx)
        if holes:
            for _ in range(holes):
                cand = mask & (idx <= 3) & erode(mask, 4)
                ys, xs = np.nonzero(cand)
                if len(xs) == 0:
                    break
                i = int(rng.integers(len(xs)))
                hx, hy = xs[i], ys[i]
                hr = rng.uniform(1.6, 2.4)
                hm = ellipse_mask(w, h, hx + 0.5, hy + 0.5, hr * 1.3, hr) & mask
                idx = np.where(hm, hole_col, idx)
                rim = shift(hm, 1, 1) & ~hm & mask
                idx = np.where(rim, np.clip(idx + 1, lo_idx, hi_idx), idx)
        out = R[np.clip(idx, 0, len(R) - 1)]
        cv[mask] = out[mask]
        self.mask = mask
        self.idx = idx
        return mask


def leaf_lattice(w, h, rng, spacing=4.2, jitter=0.7, squash=0.8):
    """Hex lattice of small leaf domes. Returns (height 0..1, lambert 0..1) fields."""
    pts = []
    row = 0
    y = -spacing
    while y < h + spacing:
        x = -spacing + (spacing / 2 if row % 2 else 0)
        while x < w + spacing:
            pts.append((x + rng.uniform(-jitter, jitter), y + rng.uniform(-jitter, jitter)))
            x += spacing
        y += spacing * squash
        row += 1
    P = np.array(pts)
    xs, ys = grid(w, h)
    best = np.full((h, w), 1e9)
    bx = np.zeros((h, w))
    by = np.zeros((h, w))
    for (qx, qy) in P:
        d = (xs + 0.5 - qx) ** 2 + ((ys + 0.5 - qy) / squash) ** 2
        upd = d < best
        best = np.where(upd, d, best)
        bx = np.where(upd, xs + 0.5 - qx, bx)
        by = np.where(upd, (ys + 0.5 - qy) / squash, by)
    r = spacing * 0.62
    u = bx / r
    v = by / r
    rr = np.clip(u * u + v * v, 0, 1)
    hgt = np.sqrt(1 - rr)
    Lx, Ly, Lz = L3
    lam = np.clip(u * Lx + v * Ly + hgt * Lz, 0, 1)
    return hgt, lam


def render_bands(can, cv, light_w=(0.3, 0.55), leaf_amp=0.16, edge_amp=0.22, under=0.5, ao=0.35,
                 thresholds=None, lut=None, contact=0.16, spacing=4.2, lo_idx=1, top_light=0.0, rim_light=True):
    """Clean banded canopy: cluster spheres quantised into bands, leafy band edges from a leaf lattice."""
    w, h = can.w, can.h
    rng = can.rng
    Lx, Ly, Lz = L3
    R = RA[can.ramp]
    hgt, lam = leaf_lattice(w, h, rng, spacing=spacing)
    xs, ys = grid(w, h)
    own = np.full((h, w), -1)
    ownz = np.full((h, w), -9.0)
    shade = np.zeros((h, w))
    order = sorted(range(len(can.clusters)), key=lambda i: can.clusters[i]["z"])
    gu = (xs + 0.5 - can.cx) / can.rx
    gv = (ys + 0.5 - can.cy) / can.ry
    gz = np.sqrt(np.clip(1 - gu * gu - gv * gv, 0, 1))
    sg = gu * Lx + gv * Ly + gz * Lz
    for ci in order:
        c = can.clusters[ci]
        x0, y0, r, sq = c["x"], c["y"], c["r"], c["squash"]
        cu = (xs + 0.5 - x0) / r
        cv_ = (ys + 0.5 - y0) / (r * sq)
        d = np.sqrt(cu * cu + cv_ * cv_)
        inside = d < 1.0 + edge_amp * (hgt - 0.55)
        cz = np.sqrt(np.clip(1 - np.minimum(d, 1) ** 2, 0, 1))
        sc = np.clip(cu, -1, 1) * Lx + np.clip(cv_, -1, 1) * Ly + cz * Lz
        sval = light_w[0] * sg + light_w[1] * sc + leaf_amp * (lam - 0.5) - ao * (1 - c["z"]) * 0.5 + c["tone"] \
            - under * np.clip(gv, 0, None) ** 2 + top_light * np.clip(-gv, 0, None)
        own = np.where(inside, ci, own)
        ownz = np.where(inside, c["z"], ownz)
        shade = np.where(inside, sval, shade)
    mask = own >= 0
    # contact shade: back cluster pixels hugging a nearer cluster's edge
    cmask = np.zeros((h, w), bool)
    for (dx, dy) in ((0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1), (0, 2), (2, 0), (0, -2),
                     (-2, 0)):
        so = shift(own, dx, dy, fill=-1)
        sz = shift(ownz, dx, dy, fill=-9.0)
        cmask |= mask & (so >= 0) & (so != own) & (sz > ownz + 0.01)
    shade = np.where(cmask, shade - contact, shade)
    thresholds = thresholds or [0.04, 0.2, 0.37, 0.54, 0.72, 0.87]
    lut = lut or [1, 2, 3, 4, 5, 6, 6]
    k = np.zeros((h, w), int)
    for t in thresholds:
        k += (shade >= t).astype(int)
    idx = np.array(lut)[k]
    idx = np.maximum(idx, lo_idx)
    if rim_light:
        # front cluster's lit upper-left edge against the cluster behind it
        rim = np.zeros((h, w), bool)
        for (dx, dy) in ((-1, 0), (0, -1)):
            so = shift(own, -dx, -dy, fill=-1)
            sz = shift(ownz, -dx, -dy, fill=-9.0)
            rim |= mask & (so >= 0) & (so != own) & (sz < ownz - 0.01)
        idx = np.where(rim & (idx >= 3), np.minimum(idx + 1, len(R) - 1), idx)
    out = R[np.clip(idx, 0, len(R) - 1)]
    cv[mask] = out[mask]
    can.mask = mask
    can.idx = idx
    can.own = own
    return mask


# --------------------------------------------------------------------------
# shared finishing
# --------------------------------------------------------------------------


def finish(cv, outline_mode="outer", lit_index=0):
    cv = binarize(cv)
    if outline_mode:
        cv = outline(cv, outline_mode, lit_index=lit_index)
    cv = clear_border(cv)
    return cv


def grass_tuft_px(cv, x, y, rng, ramp="leaf", base=3, size=3, tall=4):
    """A small fan of blades rooted at (x, y): left blades lit, right blades shaded."""
    dirs = {1: [0], 2: [-1, 1], 3: [-1, 0, 1], 4: [-2, -1, 1, 2], 5: [-2, -1, 0, 1, 2]}[size]
    for d in dirs:
        ln = max(2, tall - abs(d) + int(rng.integers(-1, 1)))
        lit = d < 0 or (d == 0 and rng.random() < 0.6)
        for i in range(ln):
            xx = x + int(round(d * (i + 1) * 0.45))
            yy = y - i
            k = base + (1 if lit else 0) + (1 if i == ln - 1 else 0)
            put(cv, xx, yy, RA[ramp][min(len(RA[ramp]) - 1, k)])


def base_grass(cv, cx, y, half_w, rng, n=10, ramp="leaf"):
    """A few grass tufts around a trunk base so trees sit in the ground."""
    k = max(2, n // 4)
    for i in range(k):
        x = int(cx - half_w + (2 * half_w) * (i + 0.5) / k + rng.uniform(-1.5, 1.5))
        grass_tuft_px(cv, x, y, rng, ramp, base=3, size=int(rng.choice([2, 3, 3])), tall=int(rng.integers(3, 5)))


# --------------------------------------------------------------------------
# trees
# --------------------------------------------------------------------------


def fill_layers(can, env, layers, rim_band=None, squash=1.0):
    """Fill an envelope with clusters in several passes: [(spacing, rmin, rmax, where)] where in
    {"all", "rim", "core"}. rim = within `rim_band` px of the envelope edge."""
    h, w = env.shape
    inner = erode(env, rim_band or 6)
    for (sp, rmin, rmax, where) in layers:
        pts = poisson(w, h, sp, can.rng, wrap=False)
        for (x, y) in pts:
            xi, yi = int(x), int(y)
            if not env[yi, xi]:
                continue
            if where == "rim" and inner[yi, xi]:
                continue
            if where == "core" and not inner[yi, xi]:
                continue
            can.add(x, y, can.rng.uniform(rmin, rmax), squash=squash)


def darken_under(cv, cmask, region, name="bark", steps=2, reach=8, dx=2):
    below = np.zeros_like(cmask)
    for d in range(1, reach + 1):
        below |= shift(cmask, dx, d)
    sh = region & ~cmask & below
    ys, xs = np.nonzero(sh)
    for y, x in zip(ys, xs):
        info = ramp_of(cv[y, x])
        if info and info[0] == name:
            cv[y, x] = RA[name][max(0, info[1] - steps)]


def roots(cv, cx, ground, rng, spread=7.0, n=2, w0=4.5, name="bark", lo=1, hi=4):
    for side in (-1, 1):
        for k in range(n):
            rx0 = cx + side * rng.uniform(1.5, 3.5)
            rpath = bezier([(rx0, ground - 6 - 2 * k), (rx0 + side * spread * 0.5, ground - 2),
                            (rx0 + side * (spread + 3 * k), ground + 0.5)], 8)
            draw_limb(cv, rpath, w0 - k, 1.5, rng, name=name, lo=lo, hi=hi)


def broadleaf(name, W, H, seed, env_lobes, trunk, branches, layers, ramp="leaf", bark="bark", bark_lo=1, bark_hi=4,
              inner=None, under=0.38, thresholds=None, lut=None, grass=12, root_spread=7.0, extra=None, trunk_w=(14, 9),
              top_light=0.0, rim_band=7, furrows=4, squash=1.0, contact=0.16, leaf_amp=0.16, spacing=4.2,
              trunk_fn=None):
    rng = rng_for(name, seed)
    cv = canvas(W, H)
    cx = W / 2
    ground = H - 2
    env = np.zeros((H, W), bool)
    for lobe in env_lobes:
        env |= ellipse_mask(W, H, *lobe)
    # dark inner canopy (behind everything): the envelope shrunk so it never pokes out
    if inner is not None:
        fx, fy, frx, fry = _env_frame(env)
        xs_, ys_ = grid(W, H)
        im = erode(env, inner) & (ys_ > fy - fry * 0.2)
        cv[im] = RA[ramp][1]
    # trunk, roots, branches
    if callable(trunk_fn):
        trunk_fn(cv, rng)
    else:
        draw_limb(cv, bezier(trunk, 12), trunk_w[0], trunk_w[1], rng, name=bark, lo=bark_lo, hi=bark_hi,
                  furrows=furrows)
    roots(cv, trunk[0][0], ground, rng, spread=root_spread, name=bark, lo=bark_lo, hi=bark_hi)
    for b in branches:
        draw_limb(cv, bezier(b[0], 10), b[1], b[2], rng, name=bark, lo=max(0, bark_lo - 1), hi=bark_hi - 1)
    wood = alpha(cv) & ~np.all(cv == RA[ramp][1], axis=-1)
    bark_marks(cv, wood, rng, name=bark, n=16)
    # canopy
    can = Canopy(W, H, *_env_frame(env), rng, ramp=ramp)
    fill_layers(can, env, layers, rim_band=rim_band, squash=squash)
    cmask = render_bands(can, cv, under=under, thresholds=thresholds, lut=lut, top_light=top_light, contact=contact,
                         leaf_amp=leaf_amp, spacing=spacing)
    darken_under(cv, cmask, wood, name=bark)
    if extra is not None:
        extra(cv, can, rng)
    if grass:
        base_grass(cv, trunk[0][0], ground, trunk_w[0] * 0.9, rng, n=grass)
    return finish(cv)


def _env_frame(env):
    ys, xs = np.nonzero(env)
    cx = (xs.min() + xs.max() + 1) / 2
    cy = (ys.min() + ys.max() + 1) / 2
    return cx, cy, (xs.max() - xs.min() + 1) / 2, (ys.max() - ys.min() + 1) / 2


def tree_oak_a():
    W, H = 96, 128
    return broadleaf(
        "tree_oak_a", W, H, 1,
        env_lobes=[(48, 50, 34, 30), (28, 36, 18, 18), (66, 30, 19, 18), (46, 22, 16, 14), (22, 60, 14, 12),
                   (74, 58, 14, 13)],
        trunk=[(48, 127), (47, 104), (49, 84), (48, 70)],
        branches=[([(46, 86), (38, 76), (28, 66)], 6, 3), ([(50, 84), (60, 74), (70, 66)], 6, 3),
                  ([(48, 80), (49, 70), (52, 58)], 5, 3)],
        layers=[(15.0, 13.0, 17.0, "core"), (9.0, 7.0, 10.0, "rim")],
        inner=5, trunk_w=(15, 9), squash=0.8, contact=0.24)


def tree_oak_b():
    W, H = 88, 112
    return broadleaf(
        "tree_oak_b", W, H, 2,
        env_lobes=[(42, 40, 28, 28), (24, 52, 16, 14), (62, 48, 18, 16), (40, 18, 18, 14), (58, 24, 14, 12)],
        trunk=[(44, 111), (42, 92), (40, 78), (41, 66)],
        branches=[([(41, 76), (32, 66), (24, 58)], 5, 2.5), ([(42, 74), (54, 66), (62, 56)], 5, 2.5)],
        layers=[(12.0, 10.0, 13.5, "core"), (7.5, 5.5, 8.5, "rim")],
        inner=5, trunk_w=(12, 8), squash=0.82, contact=0.26, under=0.5)


# ---- pine -------------------------------------------------------------------


def tree_pine():
    """Conifer built from stacked drooping tiers with serrated needle hems."""
    W, H = 64, 128
    rng = rng_for("tree_pine", 3)
    cv = canvas(W, H)
    cx = W / 2
    ground = H - 2
    draw_limb(cv, [(cx, ground + 1), (cx, 70)], 7, 5, rng)
    roots(cv, cx, ground, rng, spread=5.0, n=1, w0=3.5)
    wood = alpha(cv).copy()
    tiers = 7
    top = 3
    bottom = 104
    Lx, Ly, Lz = L3
    xs, ys = grid(W, H)
    hgt, lam = leaf_lattice(W, H, rng, spacing=3.4, squash=1.25)
    own = np.full((H, W), -1)
    shade = np.zeros((H, W))
    for t in range(tiers):
        f0 = t / tiers
        f1 = (t + 1) / tiers
        y_top = top + (bottom - top) * (f0 ** 1.15) - (2 if t else 0)
        y_bot = top + (bottom - top) * (f1 ** 1.15) + 4
        half = 5 + 25 * (f1 ** 0.9)
        th = y_bot - y_top
        for y in range(max(0, int(y_top)), min(H, int(y_bot) + 4)):
            for x in range(W):
                v = (y + 0.5 - y_top) / th  # 0 top .. 1 bottom
                u = (x + 0.5 - cx) / half
                if v < 0:
                    continue
                # tier silhouette: concave flanks, drooping serrated hem
                width_here = v ** 0.85
                hem = 1.0 + 0.10 * math.cos(u * 9.0 + t) - 0.07 * abs(u) + 0.06 * (hgt[y, x] - 0.5)
                if abs(u) > width_here * (1.02 + 0.08 * (hgt[y, x] - 0.5)) or v < 0 or v > hem:
                    continue
                # needles droop: hem tips point down/out
                nz = math.sqrt(max(0.0, 1 - min(1.0, u * u)))
                s = 0.55 * (u * Lx + (v - 0.4) * 0.6 * Ly + nz * Lz) + 0.45 * (1 - t / tiers) * 0.4
                s += 0.18 * (lam[y, x] - 0.5)
                s -= 0.35 * max(0.0, 0.25 - v) * 4 * 0.5  # under the tier above
                s -= 0.25 * max(0.0, v - 0.85) * 3
                own[y, x] = t
                shade[y, x] = s
    mask = own >= 0
    # contact shadow under each tier's hem onto the tier below
    contact = mask & (shift(own, 0, 1, fill=-1) >= 0) & (shift(own, 0, 1, fill=-1) < own)
    contact |= mask & (shift(own, 0, 2, fill=-1) >= 0) & (shift(own, 0, 2, fill=-1) < own)
    shade = np.where(contact, shade - 0.22, shade)
    th_ = [0.05, 0.2, 0.34, 0.48, 0.62]
    lut = np.array([0, 1, 2, 3, 4, 5])
    k = np.zeros((H, W), int)
    for tt in th_:
        k += (shade >= tt).astype(int)
    idx = np.maximum(lut[k], 1)
    out = RA["leaf"][idx]
    cv[mask] = out[mask]
    darken_under(cv, mask, wood, steps=2, reach=6)
    base_grass(cv, cx, ground, 6, rng, n=8)
    return finish(cv)


# ---- birch -------------------------------------------------------------------


def birch_bark(cv, mask, rng):
    """White birch bark: cream/grey cylinder with dark horizontal lenticel dashes."""
    h, w = mask.shape
    ys, xs = np.nonzero(mask)
    for _ in range(int(len(xs) / 9)):
        i = int(rng.integers(len(xs)))
        x, y = xs[i], ys[i]
        L = int(rng.integers(1, 4))
        for j in range(L):
            if 0 <= x + j < w and mask[y, x + j]:
                cv[y, x + j] = RA["ink"][2] if rng.random() < 0.6 else RA["stone"][1]


def tree_birch():
    """Slender white birch with an airy canopy of separate small leaf lobes around the branch tips."""
    W, H = 64, 112
    rng = rng_for("tree_birch", 4)
    cv = canvas(W, H)
    cx = W / 2
    ground = H - 2
    trunk = bezier([(cx, ground + 1), (cx - 1, 84), (cx + 2, 58), (cx, 30)], 14)
    tm = draw_limb(cv, trunk, 7, 4, rng, name="cloth_cream", lo=1, hi=5, grain=False)
    branches = [[(cx + 1, 66), (cx - 6, 56), (cx - 13, 46)], [(cx + 1, 60), (cx + 8, 50), (cx + 14, 40)],
                [(cx, 50), (cx - 5, 40), (cx - 9, 28)], [(cx + 1, 44), (cx + 6, 32), (cx + 8, 20)],
                [(cx + 1, 76), (cx + 7, 70), (cx + 12, 64)]]
    bm = np.zeros_like(tm)
    for b in branches:
        bm |= draw_limb(cv, bezier(b, 10), 2.6, 1.2, rng, name="cloth_cream", lo=1, hi=4, grain=False)
    birch_bark(cv, tm | bm, rng)
    for y in range(ground - 7, ground + 1):
        for x in range(W):
            if tm[y, x] and rng.random() < 0.55 + (y - ground + 7) * 0.06:
                cv[y, x] = RA["stone"][1] if rng.random() < 0.5 else RA["ink"][3]
    roots(cv, cx, ground, rng, spread=4, n=1, w0=3.0, name="stone_warm", lo=1, hi=3)
    wood = alpha(cv).copy()
    env = np.zeros((H, W), bool)
    for lobe in [(32, 14, 13, 11), (17, 32, 11, 10), (47, 30, 12, 10), (20, 52, 10, 8), (46, 52, 11, 9),
                 (33, 34, 10, 10), (45, 66, 7, 6)]:
        env |= ellipse_mask(W, H, *lobe)
    can = Canopy(W, H, *_env_frame(env), rng)
    fill_layers(can, env, [(8.5, 6.5, 8.5, "core"), (6.0, 4.0, 6.0, "rim")], rim_band=4, squash=0.85)
    cmask = render_bands(can, cv, under=0.3, thresholds=[0.04, 0.2, 0.36, 0.52, 0.68, 0.84],
                         lut=[2, 3, 3, 4, 5, 6, 6], spacing=3.4, contact=0.22)
    darken_under(cv, cmask, wood, name="cloth_cream", steps=2, reach=5)
    base_grass(cv, cx, ground, 5, rng, n=8)
    return finish(cv)


# ---- glimmerwood ---------------------------------------------------------------


def glimmer_extra(cv, can, rng):
    """Glowing motes around the canopy, glowing lichen on the trunk, hanging glow strands."""
    H, W = cv.shape[:2]
    m = can.mask
    # hanging luminous strands from the canopy underside (irregular, swaying, glowing tips)
    ys, xs = np.nonzero(m & ~shift(m, 0, -1))
    order = rng.permutation(len(xs))
    used_x = []
    for i in order:
        x, y = int(xs[i]), int(ys[i])
        if y < can.cy + can.ry * 0.15 or len(used_x) >= 11:
            continue
        if any(abs(x - ux) < 5 for ux in used_x) or rng.random() < 0.3:
            continue
        used_x.append(x)
        edge = abs(x - can.cx) / can.rx
        L = int(rng.integers(3, 8) + edge * 7)
        sway = int(rng.choice([-1, 1]))
        bend = int(rng.integers(L // 3 + 1, L + 1))
        px_ = x
        for j in range(1, L + 1):
            if j == bend:
                px_ += sway
            yy = y + j
            if yy >= H - 3 or not (0 < px_ < W - 1):
                break
            if cv[yy, px_, 3] and not m[yy, px_]:
                break
            if m[yy, px_]:
                continue
            t = j / L
            k = 2 if t < 0.4 else (3 if t < 0.8 else 4)
            cv[yy, px_] = RA["glow_moss"][k]
        tip_y = min(H - 3, y + L + 1)
        if not cv[tip_y, px_, 3]:
            cv[tip_y, px_] = RA["glow_moss"][5]
    # motes: small sparkles in and around the canopy
    pts = poisson(W, H, 9, rng, wrap=False)
    n = 0
    for (x, y) in pts:
        x, y = int(x), int(y)
        if y > can.cy + can.ry * 0.9 or y < 3 or x < 3 or x > W - 4 or n >= 11:
            continue
        inside = m[y, x]
        near = m[max(0, y - 6):y + 7, max(0, x - 6):x + 7].any()
        if not near:
            continue
        n += 1
        cv[y, x] = RA["glow_moss"][5]
        if rng.random() < 0.6:
            for (dx, dy) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if inside or not cv[y + dy, x + dx, 3]:
                    cv[y + dy, x + dx] = RA["glow_moss"][4]


def tree_glimmer():
    """Glimmerwood: wide teal umbrella canopy, hanging luminous strands, twisted twin trunk with glowing lichen."""
    W, H = 96, 128

    def extra(cv, can, rng):
        glimmer_extra(cv, can, rng)
        trunk_px = np.zeros(cv.shape[:2], bool)
        for y in range(60, 124):
            for x in range(24, 72):
                info = ramp_of(cv[y, x])
                if info and info[0] == "stone":
                    trunk_px[y, x] = True
        ys, xs = np.nonzero(trunk_px)
        for _ in range(6):
            i = int(rng.integers(len(xs)))
            x, y = xs[i], ys[i]
            for (dx, dy) in ((0, 0), (1, 0), (0, 1), (-1, 1), (1, 1), (0, 2)):
                yy, xx = min(H - 1, y + dy), min(W - 1, x + dx)
                if trunk_px[yy, xx] and rng.random() < 0.8:
                    cv[yy, xx] = RA["glow_moss"][4] if (dx + dy) % 2 == 0 else RA["glow_moss"][3]
            cv[y, x] = RA["glow_moss"][5]

    def twin_trunk(cv, rng):
        b = bezier([(55, 127), (43, 110), (55, 92), (45, 70)], 16)
        draw_limb(cv, b, 9, 6, rng, name="stone", lo=1, hi=3, furrows=2)
        a = bezier([(41, 127), (53, 108), (41, 90), (51, 70)], 16)
        draw_limb(cv, a, 10, 6, rng, name="stone", lo=1, hi=4, furrows=2)

    return broadleaf(
        "tree_glimmer", W, H, 5,
        env_lobes=[(48, 44, 44, 22), (32, 26, 20, 14), (62, 24, 20, 14), (48, 16, 16, 11), (14, 52, 11, 8),
                   (82, 52, 11, 8)],
        trunk=[(48, 127), (47, 100), (48, 70)],
        branches=[([(47, 76), (34, 66), (18, 58)], 6, 3), ([(49, 74), (62, 66), (78, 58)], 6, 3)],
        layers=[(14.0, 12.0, 16.0, "core"), (8.5, 6.5, 9.5, "rim")],
        inner=5, ramp="glow_moss", bark="stone", bark_lo=1, bark_hi=4,
        thresholds=[0.04, 0.2, 0.37, 0.54, 0.72, 0.87], lut=[1, 2, 2, 3, 4, 5, 5], extra=extra, trunk_w=(14, 9),
        grass=10, squash=0.72, contact=0.24, under=0.45, trunk_fn=twin_trunk, root_spread=9.0)


# ---- dead tree -----------------------------------------------------------------


def gnarled(cv, x, y, ang, length, width, depth, rng, name="wood_grey", lo=1, hi=4, masks=None):
    """Recursive twisted branch: curved tapering segments that fork."""
    pts = [(x, y)]
    a = ang
    seg = max(2, int(length / 3))
    cx, cy = x, y
    for i in range(seg):
        a += rng.uniform(-0.35, 0.35)
        cx += math.cos(a) * length / seg
        cy += math.sin(a) * length / seg
        pts.append((cx, cy))
    w1 = max(1.0, width * 0.55)
    m = draw_limb(cv, pts, width, w1 if depth > 0 else 0.9, rng, name=name, lo=lo, hi=hi, grain=width > 3)
    if masks is not None:
        masks.append(m)
    if depth <= 0 or width < 1.2:
        return
    nb = 2 if (rng.random() < 0.7 or depth <= 1) else 3
    for j in range(nb):
        da = rng.uniform(0.35, 0.8) * (1 if j % 2 else -1)
        gnarled(cv, cx, cy, a + da, length * rng.uniform(0.55, 0.78), w1 * rng.uniform(0.7, 0.9), depth - 1, rng,
                name, lo, hi, masks)


def tree_dead():
    """Gnarled bare tree for the ruins: twisted trunk with a hollow, curving limbs, sparse twigs."""
    W, H = 64, 96
    rng = rng_for("tree_dead", 6)
    cv = canvas(W, H)
    cx = W / 2
    ground = H - 2
    trunk = bezier([(cx, ground + 1), (cx + 4, 78), (cx - 5, 60), (cx + 1, 44)], 16)
    draw_limb(cv, trunk, 12, 6, rng, name="wood_grey", lo=0, hi=3, furrows=3)
    roots(cv, cx, ground, rng, spread=9, n=2, w0=5.0, name="wood_grey", lo=0, hi=3)

    def clampp(p):
        return (min(W - 4.0, max(3.0, p[0])), min(H - 4.0, max(3.0, p[1])))

    def twig(p0, ang, L, w0=1.8):
        p1 = clampp((p0[0] + math.cos(ang) * L, p0[1] + math.sin(ang) * L))
        mid = ((p0[0] + p1[0]) / 2 + math.cos(ang + 1.3) * L * 0.12, (p0[1] + p1[1]) / 2 + math.sin(ang + 1.3) * L * 0.12)
        draw_limb(cv, bezier([p0, mid, p1], 8), w0, 0.9, rng, name="wood_grey", lo=0, hi=3, grain=False)
        return p1

    limbs = [  # control points, w0, w1, twig angles along the limb
        ([(cx + 1, 47), (cx - 4, 36), (cx - 12, 26), (cx - 16, 13)], 5.2, 2.0, [(0.45, -2.3), (0.7, -1.2)]),
        ([(cx + 1, 46), (cx + 7, 35), (cx + 14, 24), (cx + 19, 11)], 5.0, 2.0, [(0.5, -0.5), (0.75, -1.9)]),
        ([(cx - 2, 61), (cx - 10, 58), (cx - 18, 52), (cx - 25, 47)], 3.6, 1.5, [(0.55, -2.0)]),
        ([(cx + 2, 68), (cx + 10, 64), (cx + 16, 58), (cx + 22, 56)], 3.2, 1.6, [(0.6, -1.1)]),
    ]
    for (ctrl, w0, w1, twigs) in limbs:
        ctrl = [clampp(p) for p in ctrl]
        path = bezier(ctrl, 18)
        draw_limb(cv, path, w0, w1, rng, name="wood_grey", lo=0, hi=3, grain=w0 > 4)
        for (t, ang) in twigs:
            i = int(t * (len(path) - 1))
            twig(path[i], ang + rng.uniform(-0.15, 0.15), rng.uniform(6, 9), 1.8)
        # Y-fork at the tip
        end = path[-1]
        prev = path[-3]
        a = math.atan2(end[1] - prev[1], end[0] - prev[0])
        twig(end, a - 0.45, rng.uniform(4, 6), 1.4)
        twig(end, a + 0.5, rng.uniform(3.5, 5.5), 1.4)
    # broken stub on the right limb
    put(cv, cx + 23, 55, RA["wood_grey"][3])
    # knot hole in the trunk
    hole = ellipse_mask(W, H, cx - 1.5, 72, 2.4, 3.6)
    cv[hole] = RA["wood_grey"][0]
    rim = shift(hole, 1, 1) & ~hole & alpha(cv)
    cv[rim] = RA["wood_grey"][3]
    cv[ellipse_mask(W, H, cx - 2.0, 71.5, 1.3, 2.2)] = RA["ink"][0]
    bark_marks(cv, alpha(cv), rng, name="wood_grey", n=18)
    for y in range(ground - 6, ground + 1):
        for x in range(W):
            if cv[y, x, 3] and rng.random() < 0.2 + (y - ground + 6) * 0.07:
                info = ramp_of(cv[y, x])
                if info and info[0] == "wood_grey":
                    cv[y, x] = RA["moss"][min(3, info[1] + 1)]
    for i in range(3):
        x = int(cx - 9 + 9 * i + rng.uniform(-1, 1))
        grass_tuft_px(cv, x, ground, rng, ramp="moss", base=2, size=2, tall=3)
    return finish(cv)


# --------------------------------------------------------------------------
# small-sprite helpers
# --------------------------------------------------------------------------


def blade(cv, base, tip, ctrl, ramp, k0, k1, width=1):
    """Curved 1px blade from base to tip, colour ramping from k0 (base) to k1 (tip)."""
    from kit import pixel_perfect
    pts = bezier([base, ctrl, tip], 24)
    seq = []
    for (x, y) in pts:
        p = (int(math.floor(x)), int(math.floor(y)))
        if not seq or seq[-1] != p:
            seq.append(p)
    seq = pixel_perfect(seq)
    n = len(seq)
    for i, (x, y) in enumerate(seq):
        t = i / max(1, n - 1)
        k = int(round(k0 + (k1 - k0) * t))
        put(cv, x, y, RA[ramp][k])
        if width > 1 and t < 0.5:
            put(cv, x + 1, y, RA[ramp][max(0, k - 1)])
    return seq


def shade_blob(cv, cx, cy, rx, ry, ramp, lo, hi, light=None, rim=True, spec=True):
    """Sphere-shaded ellipse quantised between ramp lo..hi; optional specular pixel."""
    h, w = cv.shape[:2]
    Lx, Ly, Lz = L3 if light is None else light
    pts = []
    for y in range(int(cy - ry - 1), int(cy + ry + 2)):
        for x in range(int(cx - rx - 1), int(cx + rx + 2)):
            u = (x + 0.5 - cx) / rx
            v = (y + 0.5 - cy) / ry
            rr = u * u + v * v
            if rr > 1.0 or not (0 <= x < w and 0 <= y < h):
                continue
            z = math.sqrt(1 - rr)
            sh = max(0.0, u * Lx + v * Ly + z * Lz)
            n = hi - lo + 1
            k = lo + min(n - 1, int(sh * n * 1.1))
            if rim and rr > 0.7 and sh < 0.5:
                k = max(lo, k - 1)
            cv[y, x] = RA[ramp][k]
            pts.append((x, y, sh))
    if spec and pts:
        x, y, _ = max(pts, key=lambda p: p[2])
        cv[y, x] = RA[ramp][min(len(RA[ramp]) - 1, hi + 1)]
    return pts


def heightmap_sprite(cv, mask, hm, ramp, lut, thresholds, strength=2.0):
    from kit import lambert
    sh = lambert(hm * strength, 1.0, wrap=False)
    k = np.zeros(mask.shape, int)
    for t in thresholds:
        k += (sh >= t).astype(int)
    idx = np.array(lut)[k]
    cv[mask] = RA[ramp][idx[mask]]
    return idx


# --------------------------------------------------------------------------
# bushes
# --------------------------------------------------------------------------


def bush(name, W, H, seed, lobes, layers, ramp="leaf", thresholds=None, lut=None, under=0.55, squash=0.85,
         berries=0, spacing=3.4):
    rng = rng_for(name, seed)
    cv = canvas(W, H)
    env = np.zeros((H, W), bool)
    for lobe in lobes:
        env |= ellipse_mask(W, H, *lobe)
    xs, ys = grid(W, H)
    env &= ys < H - 2
    can = Canopy(W, H, *_env_frame(env), rng, ramp=ramp)
    fill_layers(can, env, layers, rim_band=3, squash=squash)
    covered = np.zeros((H, W), bool)
    for c in can.clusters:
        covered |= ellipse_mask(W, H, c["x"], c["y"], c["r"] * 0.85, c["r"] * 0.85 * c["squash"])
    inner = erode(env, 2) & (ys > H * 0.5) & covered
    cv[inner] = RA[ramp][1]
    cmask = render_bands(can, cv, under=under, thresholds=thresholds, lut=lut, spacing=spacing, contact=0.22)
    cv[(ys >= H - 3) & alpha(cv)] = RA[ramp][1]
    if berries:
        ys_, xs_ = np.nonzero(cmask & erode(cmask, 2) & (can.idx >= 2) & (ys < H - 5))
        placed = []
        for i in rng.permutation(len(xs_)):
            x, y = int(xs_[i]), int(ys_[i])
            if any(abs(x - px) + abs(y - py) < 5 for px, py in placed):
                continue
            placed.append((x, y))
            # 2x2 berry: lit top-left, dark bottom-right, glint
            cv[y, x] = RA["ember"][4]
            cv[y, x + 1] = RA["ember"][3]
            cv[y + 1, x] = RA["ember"][3]
            cv[y + 1, x + 1] = RA["ember"][2]
            if rng.random() < 0.7:
                cv[y, x] = RA["ember"][6]
            if len(placed) >= berries:
                break
    return finish(cv)


def bush_a():
    return bush("bush_a", 40, 28, 7, [(20, 17, 17, 10), (11, 18, 9, 8), (29, 17, 10, 8), (20, 10, 11, 7)],
                [(8.0, 6.0, 8.0, "core"), (5.0, 3.5, 5.0, "rim")])


def bush_b():
    return bush("bush_b", 32, 24, 8, [(16, 14, 13, 9), (10, 15, 7, 7), (22, 13, 8, 8), (16, 8, 8, 6)],
                [(7.0, 5.5, 7.0, "core"), (4.5, 3.0, 4.5, "rim")],
                thresholds=[0.04, 0.2, 0.36, 0.52, 0.7, 0.86], lut=[1, 2, 2, 3, 4, 5, 6])


def bush_berry():
    return bush("bush_berry", 32, 24, 9, [(16, 14, 13, 9), (9, 15, 7, 7), (23, 14, 8, 8), (15, 8, 8, 6)],
                [(7.0, 5.5, 7.0, "core"), (4.5, 3.0, 4.5, "rim")], ramp="cloth_green",
                thresholds=[0.04, 0.2, 0.36, 0.52, 0.7, 0.86], lut=[1, 2, 2, 3, 4, 5, 5], berries=7)


# --------------------------------------------------------------------------
# ferns, reeds, tufts
# --------------------------------------------------------------------------


def frond(cv, base, ctrl, tip, maxw, ramp, k, rng, serr=3):
    """Tapered serrated fern frond along a curve; upper side lit, midrib dark."""
    pts = bezier([base, ctrl, tip], 40)
    n = len(pts)
    for i in range(n - 1):
        t = i / (n - 1)
        x, y = pts[i]
        x2, y2 = pts[i + 1]
        dx, dy = x2 - x, y2 - y
        L = math.hypot(dx, dy) + 1e-9
        dx, dy = dx / L, dy / L
        nx, ny = -dy, dx
        width = maxw * (math.sin(math.pi * min(1.0, t * 1.25 + 0.08)) ** 0.6) * (1 - 0.55 * t)
        if t < 0.12:
            width *= t / 0.12
        if int(t * 40) % serr == 0:
            width *= 0.3
        for side in (-1, 1):
            sx, sy = nx * side, ny * side
            up = sy < 0 or (abs(sy) < 0.2 and sx < 0)
            steps = int(round(width))
            for q in range(1, steps + 1):
                px_ = x + sx * q + dx * q * 0.6  # leaflets angle toward the tip
                py_ = y + sy * q + dy * q * 0.6
                kk = k + (1 if up else 0) + (1 if (q == steps and up and t < 0.7) else 0)
                put(cv, px_, py_, RA[ramp][min(len(RA[ramp]) - 1, kk)])
        put(cv, x, y, RA[ramp][max(0, k - 1)])
    put(cv, tip[0], tip[1], RA[ramp][min(len(RA[ramp]) - 1, k + 1)])


def fern(name, seed, ramp="leaf", k_back=2, k_front=3, spread=1.0):
    W, H = 24, 20
    rng = rng_for(name, seed)
    cv = canvas(W, H)
    bx, by = 12, 18
    # (tip, ctrl, width, front?)  back fronds first
    layout = [((3, 6), (6, 4), 1.6, False), ((21, 7), (18, 3), 1.6, False), ((13, 1.5), (11, 6), 1.5, False),
              ((1.5, 14), (5, 8), 1.8, True), ((22.5, 14), (18, 8), 1.8, True)]
    for (tip, ctrl, mw, front) in layout:
        tx = bx + (tip[0] - bx) * spread
        cx_ = bx + (ctrl[0] - bx) * spread
        frond(cv, (bx, by), (cx_, ctrl[1]), (tx, tip[1]), mw, ramp, k_front if front else k_back, rng)
    for x in range(bx - 2, bx + 3):
        put(cv, x, by, RA[ramp][1])
    return finish(cv)


def fern_a():
    return fern("fern_a", 10, "leaf", 2, 3)


def fern_b():
    return fern("fern_b", 11, "cloth_green", 2, 3, spread=0.92)


def reeds(name, seed, cattails=2, n=6, ramp="leaf"):
    W, H = 16, 24
    rng = rng_for(name, seed)
    cv = canvas(W, H)
    by = H - 2
    blades = []
    for i in range(n):
        x0 = 4 + (i * 8) / max(1, n - 1) + rng.uniform(-0.6, 0.6)
        tip_x = x0 + rng.uniform(-3.5, 3.5)
        tip_y = rng.uniform(2, 9)
        blades.append((x0, tip_x, tip_y))
    blades.sort(key=lambda b: b[2])  # taller (smaller tip_y) behind
    for (x0, tx, ty) in blades:
        lit = tx < x0 + 0.5
        ctrl = (x0 + (tx - x0) * 0.2, (by + ty) / 2)
        blade(cv, (x0, by), (tx, ty), ctrl, ramp, 2, 5 if lit else 4)
    for c in range(cattails):
        x = 6 + c * 4 + rng.uniform(-0.5, 0.5)
        top = rng.uniform(3, 6)
        for y in range(int(top) + 5, by):
            put(cv, x, y, RA["moss"][3] if y < by - 3 else RA["moss"][2])
        for y in range(int(top), int(top) + 5):
            put(cv, x - 1, y, RA["wood"][3] if y > top else RA["wood"][4])
            put(cv, x, y, RA["wood"][2])
        put(cv, x - 1, top - 1, RA["moss"][3])
    return finish(cv)


def reeds_a():
    return reeds("reeds_a", 12, cattails=2, n=6)


def reeds_b():
    return reeds("reeds_b", 13, cattails=0, n=8, ramp="moss")


def grass_tuft(name, seed, n, h_range, spread, ramp="leaf", lo=2, hi=5, flower=None):
    W, H = 16, 16
    rng = rng_for(name, seed)
    cv = canvas(W, H)
    by = H - 2
    blades = []
    for i in range(n):
        t = (i + 0.5) / n
        x0 = 8 + (t - 0.5) * 6 + rng.uniform(-0.5, 0.5)
        hh = rng.uniform(*h_range) * (0.7 + 0.3 * math.sin(math.pi * t))
        tx = x0 + (t - 0.5) * spread * 2 + rng.uniform(-1, 1)
        blades.append((x0, tx, by - hh, t))
    blades.sort(key=lambda b: abs(b[3] - 0.5), reverse=True)
    for (x0, tx, ty, t) in blades:
        lit = t < 0.55
        ctrl = (x0 + (tx - x0) * 0.25, (by + ty) / 2)
        blade(cv, (x0, by), (tx, ty), ctrl, ramp, lo, hi if lit else hi - 1)
    if flower:
        fr, fx, fy = flower
        put(cv, fx, fy, RA[fr][5])
        put(cv, fx + 1, fy, RA[fr][4])
        put(cv, fx, fy + 1, RA[fr][3])
    for x in range(5, 12):
        if cv[by, x, 3]:
            cv[by, x] = RA[ramp][1]
    return finish(cv)


def grass_tuft_a():
    return grass_tuft("grass_tuft_a", 14, 9, (7, 11), 5)


def grass_tuft_b():
    return grass_tuft("grass_tuft_b", 15, 7, (9, 13), 3, lo=2, hi=6)


def grass_tuft_c():
    return grass_tuft("grass_tuft_c", 16, 11, (4, 7), 6, ramp="moss", lo=2, hi=5)


def grass_tuft_d():
    return grass_tuft("grass_tuft_d", 17, 8, (6, 10), 5, ramp="cloth_green", lo=1, hi=5)


# --------------------------------------------------------------------------
# flowers
# --------------------------------------------------------------------------

FLOWER_RAMPS = {
    "red": ("cloth_red", 3, 5),
    "yellow": ("gold", 3, 5),
    "blue": ("cloth_blue", 3, 5),
    "white": ("cloth_cream", 3, 5),
    "pink": ("cloth_plum", 4, 5),
}


def flowers(name, seed, color):
    W, H = 16, 16
    rng = rng_for(name, seed)
    cv = canvas(W, H)
    by = H - 2
    fr, flo, fhi = FLOWER_RAMPS[color]
    for (x0, tx, ty) in ((7, 3, 11), (8, 12, 10), (8, 6, 9), (9, 11, 12), (7, 9, 11)):
        blade(cv, (x0, by), (tx, ty), (x0 + (tx - x0) * 0.2, ty + 1), "leaf", 2, 4)
    heads = [(5, 6), (10, 4), (8, 9), (12, 8)] if color != "white" else [(4, 7), (9, 4), (12, 9), (7, 10)]
    heads = heads[:3 + (1 if rng.random() < 0.6 else 0)]
    for (hx, hy) in heads:
        for y in range(hy + 2, by):
            put(cv, hx, y, RA["leaf"][3] if y < by - 2 else RA["leaf"][2])
        petals = [(0, -1, fhi), (-1, 0, fhi), (1, 0, flo + 1 if fhi - flo > 1 else flo), (0, 1, flo),
                  (-1, -1, fhi), (1, 1, flo), (1, -1, flo + 1 if fhi - flo > 1 else fhi), (-1, 1, flo)]
        for (dx, dy, k) in petals:
            put(cv, hx + dx, hy + dy, RA[fr][k])
        centre = RA["gold"][4] if color not in ("yellow",) else RA["ember"][3]
        put(cv, hx, hy, centre)
    return finish(cv)


# --------------------------------------------------------------------------
# mushrooms, rocks, stump
# --------------------------------------------------------------------------


def mushroom_shape(cv, x, base_y, cap_w, cap_h, stem_h, cap_ramp, cap_lo, cap_hi, stem_ramp="cloth_cream",
                   spots=None, rng=None):
    sw = max(2, cap_w // 3)
    for y in range(base_y - stem_h, base_y + 1):
        for dx in range(sw):
            k = 4 if dx == 0 else (3 if dx < sw - 1 else 2)
            put(cv, x - sw // 2 + dx, y, RA[stem_ramp][k])
    cy = base_y - stem_h
    for dx in range(-cap_w // 2 + 1, cap_w // 2):
        put(cv, x + dx, cy, RA[stem_ramp][1])  # gill shadow under the cap
    for yy in range(cap_h):
        for xx in range(-cap_w // 2, cap_w // 2 + 1):
            u = (xx + 0.5) / (cap_w / 2 + 0.5)
            v = (cap_h - yy - 0.5) / cap_h
            if u * u + v * v > 1.0:
                continue
            z = math.sqrt(max(0.0, 1 - u * u - v * v))
            sh = max(0.0, u * L3[0] + -v * L3[1] * 0.9 + z * L3[2])
            n = cap_hi - cap_lo + 1
            k = cap_lo + min(n - 1, int(sh * n * 1.05))
            if yy == cap_h - 1:
                k = max(cap_lo, k - 1)
            put(cv, x + xx, cy - 1 - (cap_h - 1 - yy), RA[cap_ramp][k])
    if spots and rng is not None:
        sr, sk = spots
        for _ in range(3):
            sx = x + int(rng.integers(-cap_w // 2 + 1, cap_w // 2))
            sy = cy - 1 - int(rng.integers(1, max(2, cap_h - 1)))
            if cv[sy, sx, 3]:
                cv[sy, sx] = RA[sr][sk]


def mushroom_a():
    rng = rng_for("mushroom_a", 18)
    cv = canvas(16, 16)
    mushroom_shape(cv, 6, 14, 8, 4, 4, "leather", 2, 5, rng=rng)
    mushroom_shape(cv, 11, 14, 5, 3, 2, "leather", 2, 5, rng=rng)
    return finish(cv)


def mushroom_b():
    rng = rng_for("mushroom_b", 19)
    cv = canvas(16, 16)
    mushroom_shape(cv, 9, 14, 7, 3, 6, "cloth_cream", 2, 5, stem_ramp="cloth_cream", rng=rng,
                   spots=("cloth_cream", 1))
    mushroom_shape(cv, 4, 14, 5, 2, 3, "sand", 2, 5, stem_ramp="cloth_cream", rng=rng)
    return finish(cv)


def mushroom_glow():
    rng = rng_for("mushroom_glow", 20)
    cv = canvas(16, 16)
    mushroom_shape(cv, 6, 14, 7, 4, 4, "glow_moss", 2, 5, stem_ramp="cloth_cream", rng=rng,
                   spots=("glow_moss", 5))
    mushroom_shape(cv, 11, 14, 5, 3, 2, "glow_moss", 2, 5, stem_ramp="cloth_cream", rng=rng)
    mushroom_shape(cv, 3, 14, 3, 2, 1, "glow_moss", 3, 5, stem_ramp="cloth_cream", rng=rng)
    cv = finish(cv)
    # glow sparkles floating above (opaque single pixels)
    for (x, y) in ((4, 4), (12, 6), (9, 2)):
        if not cv[y, x, 3]:
            cv[y, x] = RA["glow_moss"][5]
    return clear_border(cv)


def faceted(cv, mask, hm, rng, ramp="stone", cell=5.0, tilt=0.35, lut=(1, 2, 3, 4, 5),
            thresholds=(0.3, 0.5, 0.68, 0.84), edges=True, warp=1.5):
    """Flat-shaded facets over a height field: each warped-Voronoi cell takes the dome normal at its
    centre plus a random tilt -> crisp chiselled planes. Returns the per-pixel level map."""
    from textures import warped_voronoi
    H, W = mask.shape
    ys_, xs_ = np.nonzero(mask)
    pts = [(x + 0.5, y + 0.5) for (x, y) in poisson(W, H, cell, rng, wrap=False) if mask[int(y), int(x)]]
    if len(pts) < 2:
        pts = [(xs_.mean(), ys_.mean()), (xs_.mean() + 1, ys_.mean())]
    ids, d1, d2 = warped_voronoi(W, H, pts, rng, amp=warp, cells=3)
    gy, gx = np.gradient(hm)
    L = np.array(L3)
    vals = []
    for i, (px, py) in enumerate(pts):
        sel = (ids == i) & mask
        if sel.any():
            nx_ = -gx[sel].mean()
            ny_ = -gy[sel].mean()
        else:
            nx_ = ny_ = 0.0
        nx_ += rng.uniform(-tilt, tilt)
        ny_ += rng.uniform(-tilt, tilt)
        n = np.array([nx_, ny_, 1.0])
        n /= np.linalg.norm(n)
        vals.append(float(n @ L))
    v = np.array(vals)[ids]
    k = np.zeros(mask.shape, int)
    for t in thresholds:
        k += (v >= t).astype(int)
    idx = np.array(lut)[k]
    if edges:
        up = np.roll(ids, 1, 0)
        left = np.roll(ids, 1, 1)
        kup = np.roll(idx, 1, 0)
        kl = np.roll(idx, 1, 1)
        bnd = mask & ((ids != up) & np.roll(mask, 1, 0) | (ids != left) & np.roll(mask, 1, 1))
        other = np.where(ids != up, kup, kl)
        n = len(RA[ramp])
        idx = np.where(bnd & (idx > other), np.minimum(idx + 1, n - 1), idx)
        idx = np.where(bnd & (idx <= other), np.maximum(idx - 1, 1), idx)
    cv[mask] = RA[ramp][idx[mask]]
    return idx


def rock_small(name, seed, parts, moss=0.0, ramp="stone"):
    W, H = 24, 16
    rng = rng_for(name, seed)
    cv = canvas(W, H)
    xs, ys = grid(W, H)
    hm = np.zeros((H, W))
    mask = np.zeros((H, W), bool)
    for (cx, cy, rx, ry) in parts:
        u = (xs + 0.5 - cx) / rx
        v = (ys + 0.5 - cy) / ry
        rr = u * u + v * v
        inside = rr < 1.0
        hh = np.sqrt(np.clip(1 - rr, 0, 1)) * ry
        hm = np.where(inside, np.maximum(hm, hh), hm)
        mask |= inside
    mask &= (ys < H - 1) & (ys >= 1)
    idx = faceted(cv, mask, hm * 1.3, rng, ramp=ramp, cell=4.0, tilt=0.3, lut=(1, 2, 3, 3, 4),
                  thresholds=(0.45, 0.62, 0.78, 0.9))
    # ground contact: bottom row darkest
    bot = mask & ~shift(mask, 0, -1)
    cv[bot] = RA[ramp][1]
    # a crack
    cx0 = int(parts[0][0] + rng.uniform(-2, 2))
    y = int(parts[0][1] - parts[0][3] * 0.4)
    for i in range(4):
        x = cx0 + (i // 2)
        if mask[y + i, x] and mask[y + i, x + 1]:
            cv[y + i, x] = RA[ramp][0]
            cv[y + i, x + 1] = RA[ramp][min(5, idx[y + i, x + 1] + 1)]
    if moss:
        top = mask & (~shift(mask, 0, 1) | ~shift(mask, 0, 2))
        mm = top & (fbm(W, H, 4, 2, rng) > 1 - moss)
        cv[mm] = RA["moss"][4]
        cv[mm & ~shift(mm, 1, 0)] = RA["moss"][5]
        cv[shift(mm, 0, 1) & mask & ~mm] = RA["moss"][2]
    return finish(cv)


def rock_small_a():
    return rock_small("rock_small_a", 21, [(12, 9.5, 9, 6.5)])


def rock_small_b():
    return rock_small("rock_small_b", 22, [(10, 9, 7.5, 6.0), (17, 11, 5, 4)], moss=0.5)


def rock_small_c():
    return rock_small("rock_small_c", 23, [(12, 11, 10, 4.5), (8, 9, 4, 3.5)])


def stump():
    """Cut tree stump: ringed top face seen from above-front, furrowed bark, flaring roots, moss."""
    W, H = 24, 20
    rng = rng_for("stump", 24)
    cv = canvas(W, H)
    cx = 12
    top_y = 6.5
    ground = H - 2
    xs, ys = grid(W, H)
    half = 7.0 + np.clip((ys - top_y) / (ground - top_y), 0, 1) ** 2 * 2.5
    u = (xs + 0.5 - cx) / half
    body = (np.abs(u) <= 1.0) & (ys >= top_y) & (ys <= ground)
    nz = np.sqrt(np.clip(1 - u * u, 0, 1))
    sh = np.clip(-u * 0.7 + nz * 0.55, 0, 1)
    fur = np.abs(np.sin((u * 2.4 + 0.15 * np.sin(ys * 0.9)) * math.pi)) < 0.22
    k = 1 + np.clip((sh * 4).astype(int), 0, 3)
    k = np.where(fur, np.maximum(1, k - 2), k)
    cv[body] = RA["bark"][k[body]]
    roots(cv, cx, ground, rng, spread=5, n=1, w0=3.6)
    rx, ry = 7.2, 3.0
    fu = (xs + 0.5 - cx) / rx
    fv = (ys + 0.5 - top_y) / ry
    fd = np.sqrt(fu * fu + fv * fv)
    face = fd <= 1.0
    ring = np.floor(fd * 4.5).astype(int)
    rk = np.where(ring % 2 == 0, 5, 4)
    rk = np.where((fu > 0.25) & (rk == 5), 4, rk)
    rk = np.where(fd > 0.82, 3, rk)
    cv[face] = RA["wood"][rk[face]]
    cv[face & (fd > 0.93)] = RA["bark"][3]
    cv[int(top_y), cx] = RA["wood"][2]
    for i in range(1, 6):
        x = cx + i
        y = int(top_y + i * 0.3)
        if face[y, x]:
            cv[y, x] = RA["wood"][2]
    for y in range(int(top_y) + 3, ground - 1):
        for x in range(cx + 3, cx + 10):
            if body[y, x] and not face[y, x] and rng.random() < 0.35 + 0.05 * (y - top_y):
                cv[y, x] = RA["moss"][2] if rng.random() < 0.6 else RA["moss"][3]
    return finish(cv)


# --------------------------------------------------------------------------
# kindlemoss, lily pad, hollow log
# --------------------------------------------------------------------------


def kindlemoss():
    """A tied bundle of dry golden moss fibres (frayed ends, twine at the waist, faint glow):
    the quest item gathered to light a fire."""
    W = H = 16
    rng = rng_for("kindlemoss", 31)
    cv = canvas(W, H)
    xs, ys = grid(W, H)
    left = ellipse_mask(W, H, 5.0, 9.0, 3.6, 3.8)
    right = ellipse_mask(W, H, 11.0, 8.6, 3.8, 4.2)
    waist = (np.abs(xs + 0.5 - 8.0) < 1.6) & (np.abs(ys + 0.5 - 8.8) < 2.4)
    body = left | right | waist
    v = (ys + 0.5 - 8.8) / 4.2
    sh = 0.66 - v * 0.45 - ((xs + 0.5 - 8) / 8.0) * 0.1
    k = np.zeros((H, W), int)
    for t in (0.25, 0.45, 0.62, 0.8):
        k += (sh >= t).astype(int)
    idx = np.array([1, 2, 3, 4, 5])[k]
    # lengthwise fibre streaks: darker runs on alternate rows
    for y in range(0, H, 2):
        x = int(rng.integers(0, 3))
        while x < W:
            run = int(rng.integers(2, 4))
            for i in range(run):
                if 0 <= x + i < W and body[y, x + i]:
                    idx[y, x + i] = max(1, idx[y, x + i] - 1)
            x += run + int(rng.integers(1, 3))
    cv[body] = RA["gold"][idx[body]]
    # frayed fibre tips fanning out at both ends
    for (x0, y0, dx, dy, L) in ((1.5, 7, -1, -0.5, 2), (1.2, 9, -1, 0, 2), (1.6, 11, -1, 0.5, 2),
                                (14.6, 6, 1, -0.6, 2), (14.9, 8.5, 1, 0, 1), (14.6, 11, 1, 0.5, 2)):
        for i in range(L):
            x = int(round(x0 + dx * i))
            y = int(round(y0 + dy * i))
            if 0 < x < W - 1 and 0 < y < H - 1 and not body[y, x]:
                put(cv, x, y, RA["gold"][4] if y <= 9 else RA["gold"][3])
    # twine wrapped twice around the waist, loose end hanging
    for y in range(6, 12):
        for x in (7, 8):
            if body[y, x]:
                cv[y, x] = RA["leather"][3] if x == 7 else RA["leather"][2]
    put(cv, 7, 7, RA["leather"][4])
    put(cv, 7, 10, RA["leather"][4])
    put(cv, 9, 12, RA["leather"][2])
    put(cv, 10, 13, RA["leather"][3])
    cv = finish(cv)
    # glow glints after the outline so they stay bright
    for (x, y) in ((4, 7), (11, 6), (12, 7), (5, 8)):
        cv[y, x] = RA["gold"][5]
    cv[6, 10] = RA["ember"][6]
    return clear_border(cv)


def lily_pad():
    """Top-down floating lily pad with a notch, radiating veins and a small blossom."""
    W, H = 16, 16
    cv = canvas(W, H)
    cx, cy, r = 7.5, 8.0, 6.3
    xs, ys = grid(W, H)
    u = xs + 0.5 - cx
    v = ys + 0.5 - cy
    d = np.hypot(u, v)
    ang = np.arctan2(v, u)
    notch = (np.abs(((ang - 0.55) + math.pi) % math.tau - math.pi) < 0.32)
    pad = (d <= r) & ~notch
    sh = -(u * 0.6 + v * 0.75) / r * 0.5 + 0.55 - (d / r) ** 3 * 0.25
    k = np.zeros((H, W), int)
    for t in (0.3, 0.5, 0.7):
        k += (sh >= t).astype(int)
    lut = np.array([2, 3, 4, 5])
    cv[pad] = RA["leaf"][lut[k[pad]]]
    for a in np.linspace(0, math.tau, 9, endpoint=False):
        if abs(((a - 0.55) + math.pi) % math.tau - math.pi) < 0.45:
            continue
        for t in np.linspace(1.5, r - 1.2, 6):
            x = int(cx + math.cos(a) * t)
            y = int(cy + math.sin(a) * t)
            if pad[y, x]:
                cv[y, x] = RA["leaf"][max(2, lut[k[y, x]] - 1)]
    for (dx, dy, kk) in ((0, -1, 5), (-1, 0, 5), (1, 0, 4), (0, 1, 4)):
        cv[5 + dy, 5 + dx] = RA["sigil"][kk]
    cv[5, 5] = RA["gold"][5]
    return finish(cv)


def log_hollow():
    """Fallen hollow log, side view, bark on top, cut end with dark opening on the right."""
    W, H = 64, 32
    rng = rng_for("log_hollow", 27)
    cv = canvas(W, H)
    cy = 17.5
    ry = 11.0
    x0, x1 = 4, 54
    xs, ys = grid(W, H)
    left_edge = x0 + 2 * np.sin(ys * 1.3) + (np.abs(ys + 0.5 - cy) < 4) * 1.5
    body = (xs >= left_edge) & (xs <= x1) & (np.abs(ys + 0.5 - cy) <= ry)
    v = (ys + 0.5 - cy) / ry
    nz = np.sqrt(np.clip(1 - v * v, 0, 1))
    sh = np.clip(-v * 0.75 + nz * 0.5, 0, 1)
    rid = np.sin(v * 9 + fbm(W, H, 6, 2, rng, cells_y=2) * 4) > 0.55
    sh = sh + np.where(rid, -0.22, 0) + 0.15 * (fbm(W, H, 10, 2, rng) - 0.5)
    k = np.clip((sh * 4).astype(int), 0, 3) + 1
    cv[body] = RA["bark"][k[body]]
    ex, erx = x1 + 0.5, 6.5
    face = ((xs + 0.5 - ex) / erx) ** 2 + ((ys + 0.5 - cy) / ry) ** 2 <= 1.0
    fd = np.sqrt(((xs + 0.5 - ex) / erx) ** 2 + ((ys + 0.5 - cy) / ry) ** 2)
    ring = (fd * 5).astype(int)
    wood_k = np.array([4, 4, 5, 4, 3, 2])[np.clip(ring, 0, 5)]
    cv[face] = RA["wood"][wood_k[face]]
    cv[face & (fd > 0.86)] = RA["bark"][2]
    hole = ((xs + 0.5 - (ex + 0.3)) / (erx * 0.62)) ** 2 + ((ys + 0.5 - (cy + 0.6)) / (ry * 0.66)) ** 2 <= 1.0
    cv[hole] = RA["ink"][1]
    deep = ((xs + 0.5 - (ex + 0.9)) / (erx * 0.42)) ** 2 + ((ys + 0.5 - (cy + 1.0)) / (ry * 0.48)) ** 2 <= 1.0
    cv[deep] = RA["ink"][0]
    lip = shift(hole, 1, 1) & ~hole & face
    cv[lip] = RA["wood"][5]
    top = body & (v < -0.55) & (fbm(W, H, 6, 2, rng) > 0.42)
    cv[top] = RA["moss"][4]
    cv[top & (v < -0.8)] = RA["moss"][5]
    cv[shift(top, 0, 1) & body & ~top] = RA["moss"][2]
    bot = body & (v > 0.85)
    cv[bot] = RA["bark"][0]
    mushroom_shape(cv, 20, int(cy - ry), 3, 2, 1, "leather", 2, 5)
    mushroom_shape(cv, 24, int(cy - ry) + 1, 3, 2, 1, "leather", 2, 5)
    grass_tuft_px(cv, 38, int(cy - ry) + 1, rng, ramp="leaf", base=3, size=3, tall=4)
    return finish(cv)


TREES = {
    "tree_oak_a": tree_oak_a,
    "tree_oak_b": tree_oak_b,
    "tree_pine": tree_pine,
    "tree_birch": tree_birch,
    "tree_glimmer": tree_glimmer,
    "tree_dead": tree_dead,
}

ALL = {}
ALL.update(TREES)
ALL.update({
    "bush_a": bush_a, "bush_b": bush_b, "bush_berry": bush_berry,
    "fern_a": fern_a, "fern_b": fern_b, "reeds_a": reeds_a, "reeds_b": reeds_b,
    "grass_tuft_a": grass_tuft_a, "grass_tuft_b": grass_tuft_b, "grass_tuft_c": grass_tuft_c,
    "grass_tuft_d": grass_tuft_d,
    "flowers_red": lambda: flowers("flowers_red", 30, "red"),
    "flowers_yellow": lambda: flowers("flowers_yellow", 31, "yellow"),
    "flowers_blue": lambda: flowers("flowers_blue", 32, "blue"),
    "flowers_white": lambda: flowers("flowers_white", 33, "white"),
    "flowers_pink": lambda: flowers("flowers_pink", 34, "pink"),
    "mushroom_a": mushroom_a, "mushroom_b": mushroom_b, "mushroom_glow": mushroom_glow,
    "rock_small_a": rock_small_a, "rock_small_b": rock_small_b, "rock_small_c": rock_small_c,
    "stump": stump, "kindlemoss": kindlemoss, "lily_pad": lily_pad, "log_hollow": log_hollow,
})


def build(only=None, preview_on=True):
    os.makedirs(OUT, exist_ok=True)
    items = []
    for name, fn in ALL.items():
        if only and name not in only:
            continue
        cv = fn()
        assert border_ok(cv), name
        assert set(np.unique(cv[..., 3])) <= {0, 255}, name
        save_png(cv, os.path.join(OUT, name + ".png"))
        items.append((name, cv))
    if preview_on and items:
        grid_preview(items, "foliage_sel" if only else "foliage_all", scale=4 if only else 3, cols=4)
    return items


if __name__ == "__main__":
    import sys
    build(sys.argv[1:] or None)
