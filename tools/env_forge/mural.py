"""Key story image: "Aurelune the Dawncrane" - an ancient carved relief on a mossy wall slab.

The relief is modelled as a height field built from vector shapes (raised border, recessed
field, raised sun disc, incised rays, raised crane figure with incised feather detail,
ribbon tail feathers, stylised cloud bands). It is lit from the upper-left, then weathered:
erosion, pits, cracks, faded ochre/teal pigment remnants and creeping moss.

mural_dawncrane_glow re-uses the same carving with the incised lines and the sun awakened
in gold/aether light.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from kit import (RA, alpha, bezier, canvas, clear_border, dilate, erode, fbm, grid, lambert, outline, poisson,
                 rng_for, shift)

W, H = 128, 96
SS = 4  # supersampling for vector shapes


# --------------------------------------------------------------------------
# vector helpers (supersampled masks)
# --------------------------------------------------------------------------


class Pen:
    def __init__(self):
        self.im = Image.new("L", (W * SS, H * SS), 0)
        self.d = ImageDraw.Draw(self.im)

    def poly(self, pts, v=255):
        self.d.polygon([(x * SS, y * SS) for x, y in pts], fill=v)

    def ellipse(self, cx, cy, rx, ry, v=255):
        self.d.ellipse([(cx - rx) * SS, (cy - ry) * SS, (cx + rx) * SS, (cy + ry) * SS], fill=v)

    def line(self, pts, width, v=255):
        P = [(x * SS, y * SS) for x, y in pts]
        self.d.line(P, fill=v, width=max(1, int(round(width * SS))), joint="curve")
        r = width * SS / 2
        for (x, y) in (P[0], P[-1]):
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=v)

    def taper(self, pts, w0, w1, v=255):
        n = len(pts)
        for i, (x, y) in enumerate(pts):
            t = i / max(1, n - 1)
            r = (w0 + (w1 - w0) * t) * SS / 2
            self.d.ellipse([x * SS - r, y * SS - r, x * SS + r, y * SS + r], fill=v)

    def mask(self, thr=128):
        small = self.im.resize((W, H), Image.BOX)
        return np.array(small) >= thr


def m_poly(pts):
    p = Pen()
    p.poly(pts)
    return p.mask()


def m_ellipse(cx, cy, rx, ry):
    p = Pen()
    p.ellipse(cx, cy, rx, ry)
    return p.mask()


def m_line(pts, width, thr=110):
    p = Pen()
    p.line(pts, width)
    return p.mask(thr)


def m_taper(pts, w0, w1, thr=110):
    p = Pen()
    p.taper(pts, w0, w1)
    return p.mask(thr)


def mirror(pts, cx=64.0):
    return [(2 * cx - x, y) for (x, y) in pts]


# --------------------------------------------------------------------------
# composition
# --------------------------------------------------------------------------

CX = 64.0


def wing_shape(side=-1):
    """Left (side=-1) or right wing: one clean shape with a scalloped trailing edge of feather tips.
    Returns (polygon points, feather-groove polylines, covert line)."""
    def M(p):
        return p if side < 0 else (2 * CX - p[0], p[1])
    shoulder = (57.5, 41.0)
    lead = bezier([(57.5, 39.5), (48, 30), (38, 20.5), (24, 13), (9, 9)], 30)
    # feather tips along the trailing edge (outer -> inner)
    tips = [(6.5, 13.5), (7.0, 20.0), (9.5, 26.5), (13.5, 32.5), (19.0, 37.5), (25.5, 41.5), (32.5, 45.0),
            (39.5, 48.0), (46.5, 50.5), (53.0, 52.5)]
    trail = []
    for i in range(len(tips) - 1):
        a, b = tips[i], tips[i + 1]
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        # notch between feathers pulls inward toward the arm
        nx, ny = mx + (shoulder[0] - mx) * 0.07 + 1.2, my + (shoulder[1] - my) * 0.07 - 1.0
        trail += [a, (a[0] + (nx - a[0]) * 0.55 + 0.6, a[1] + (ny - a[1]) * 0.55 + 0.9), (nx, ny)]
    trail.append(tips[-1])
    trail.append((58.0, 52.0))
    poly = [M(p) for p in lead] + [M(p) for p in tips[:1]] + [M(p) for p in trail] + [M(shoulder)]
    # feather separation grooves: from the arm toward each notch
    hub_pts = bezier([(52, 43), (42, 34), (31, 25), (20, 19)], 9)
    grooves = []
    for i in range(len(tips) - 1):
        a, b = tips[i], tips[i + 1]
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        nx, ny = mx + (shoulder[0] - mx) * 0.07 + 1.2, my + (shoulder[1] - my) * 0.07 - 1.0
        hx, hy = hub_pts[min(len(hub_pts) - 1, len(tips) - 2 - i)]
        L = math.hypot(nx - hx, ny - hy)
        t0 = 0.0
        sx, sy = hx + (nx - hx) * t0, hy + (ny - hy) * t0
        grooves.append([M((sx, sy)), M((nx - (nx - hx) / L * 0.8, ny - (ny - hy) / L * 0.8))])
    covert = [M(p) for p in bezier([(55, 45), (47, 37.5), (37, 29), (25, 21.5), (15, 17)], 24)]
    covert2 = [M(p) for p in bezier([(56, 42), (49, 35.5), (41, 28), (33, 23)], 16)]
    return poly, grooves, covert, covert2


def crane_shapes():
    """Return dict of raised masks and groove polylines (incised detail)."""
    raised = {}
    grooves = []
    for side, key in ((-1, "wing_l"), (1, "wing_r")):
        poly, fg, cov, cov2 = wing_shape(side)
        raised[key] = m_poly(poly)
        for g in fg:
            grooves.append((g, 0.8))
        grooves.append((cov, 0.8))
        # small covert scallops between the two covert lines
        grooves.append((cov2, 0.7))
    body = m_ellipse(CX, 50.5, 7.2, 12.0) | m_poly([(CX - 6.5, 50), (CX + 6.5, 50), (CX + 2.5, 64), (CX - 2.5, 64)])
    raised["body"] = body
    neck_pts = bezier([(CX + 0.5, 43), (CX + 6.5, 35), (CX + 2.0, 26.5), (CX - 3.5, 21.0)], 24)
    raised["neck"] = m_taper(neck_pts, 7.4, 4.8, thr=120)
    raised["head"] = m_ellipse(CX - 5.0, 18.8, 4.6, 3.7)
    raised["beak"] = m_poly([(CX - 8.8, 16.9), (CX - 24.0, 19.6), (CX - 8.8, 21.6)])
    cm = np.zeros((H, W), bool)
    crest = []
    for (tx, ty) in ((CX + 13, 8.5), (CX + 16, 13.5), (CX + 9, 5.0)):
        pts = bezier([(CX - 2.5, 16.5), (CX + 2, 11.5), (tx - 3, ty + 1.5), (tx, ty)], 20)
        crest.append(pts)
        cm |= m_taper(pts, 2.8, 1.0, thr=110)
    raised["crest"] = cm
    # breast chevrons + neck line
    for k in range(3):
        y = 47.5 + k * 4.2
        grooves.append(([(CX - 4.2 + k * 0.7, y), (CX, y + 2.0), (CX + 4.2 - k * 0.7, y)], 0.75))
    grooves.append((bezier([(CX + 3.5, 41.5), (CX + 5.5, 34.5), (CX + 1.0, 27.5), (CX - 2.0, 23.5)], 16), 0.7))
    # tail ribbons
    ribbons = []
    for side in (-1, 1):
        r1 = bezier([(CX + side * 2.5, 61), (CX + side * 7, 74), (CX + side * 22, 79), (CX + side * 35, 71),
                     (CX + side * 44, 76), (CX + side * 40, 85), (CX + side * 33, 83)], 70)
        r2 = bezier([(CX + side * 1.0, 63), (CX + side * 2.5, 80), (CX + side * 12, 89), (CX + side * 21, 87),
                     (CX + side * 22, 82)], 60)
        ribbons += [r1, r2]
    ribbons.append(bezier([(CX, 63), (CX - 0.5, 77), (CX + 1.5, 88)], 30))
    rm = np.zeros((H, W), bool)
    for r in ribbons:
        rm |= m_taper(r, 4.6, 1.8, thr=115)
    raised["ribbons"] = rm
    for r in ribbons:
        grooves.append((r[4:-6], 0.7))
    return raised, grooves, (int(CX - 5.0), 18)


def build_height(rng):
    """Integer height steps: field 0, sun 1, clouds/rays per motif, figure 2, border 2; grooves cut 1 deep."""
    xs, ys = grid(W, H)
    slab = np.ones((H, W), bool)
    slab[:2] = slab[-2:] = False
    slab[:, :2] = slab[:, -2:] = False
    slab &= ~m_poly([(103, 0), (128, 0), (128, 23), (121, 18), (116, 13), (111, 8), (106, 4)])
    slab &= ~m_poly([(0, 83), (5, 88), (4, 96), (0, 96)])
    slab &= ~m_poly([(52, 96), (55, 93), (60, 93.5), (63, 96)])
    hgt = np.zeros((H, W), int)
    region = np.zeros((H, W), int)  # 0 field, 1 border, 2 sun, 3 rays, 4 clouds, 5 figure
    inner = erode(slab, 6)
    field = erode(slab, 7)
    border = slab & ~field
    hgt[border] = 2
    region[border] = 1
    bgroove = erode(slab, 3) & ~erode(slab, 4)
    # sun disc (raised) with a rim groove
    sun = m_ellipse(CX, 45, 25, 25) & field
    hgt[sun] = 1
    region[sun] = 2
    sun_groove = sun & ~m_ellipse(CX, 45, 22.6, 22.6) & m_ellipse(CX, 45, 23.8, 23.8)
    # sunburst rays: short tapered wedges between the disc and the frame
    rays = np.zeros((H, W), bool)
    for k in range(16):
        a = -math.pi + (k + 0.5) * math.tau / 16
        long_ = k % 2 == 0
        r0, r1 = 27.5, (40.0 if long_ else 34.0)
        p0 = (CX + math.cos(a) * r0, 45 + math.sin(a) * r0)
        p1 = (CX + math.cos(a) * r1, 45 + math.sin(a) * r1)
        rays |= m_taper(bezier([p0, p1], 12), 3.4 if long_ else 2.6, 0.8, thr=110)
    rays &= field & ~sun
    hgt[rays] = 1
    region[rays] = 3
    # cloud scrolls at the bottom corners (raised bands)
    clouds = np.zeros((H, W), bool)
    for side in (-1, 1):
        for (y0, x0, x1, amp, ph) in ((80, 10, 50, 1.6, 0.0), (86, 14, 44, 1.4, 1.6)):
            xa, xb = (x0, x1) if side < 0 else (W - x1, W - x0)
            pts = [(x, y0 + amp * math.sin(x / 5.0 + ph)) for x in np.linspace(xa, xb, 40)]
            clouds |= m_line(pts, 2.6, thr=110)
        # spiral curl at the outer end
        cxs = 12 if side < 0 else W - 12
        sp = [(cxs + side * -1 * 0 + math.cos(t) * (0.8 + t * 0.55) * (-side), 78 + math.sin(t) * (0.8 + t * 0.55))
              for t in np.linspace(0, 3.6 * math.pi / 1.0, 40)]
        clouds |= m_line(sp, 1.8, thr=110)
    clouds &= field
    hgt[clouds] = 1
    region[clouds] = 4
    raised, grooves, eye = crane_shapes()
    fig = np.zeros((H, W), bool)
    for m in raised.values():
        fig |= m
    fig &= field
    hgt[fig] = 2
    region[fig] = 5
    groove_m = np.zeros((H, W), bool)
    for (pts, wd) in grooves:
        groove_m |= m_line(pts, wd, thr=100)
    groove_m &= erode(fig, 1)
    hgt[groove_m] -= 1
    hgt[sun_groove & ~fig] -= 1
    hgt[bgroove] -= 1
    hgt[eye[1], eye[0]] -= 1
    return dict(slab=slab, hgt=hgt, region=region, border=border, field=field, sun=sun & ~fig, rays=rays & ~fig,
                clouds=clouds & ~fig, fig=fig, raised=raised, grooves=groove_m, eye=eye, bgroove=bgroove,
                sun_groove=sun_groove & ~fig)


BASE_TONE = {0: 2, 1: 3, 2: 3, 3: 2, 4: 3, 5: 3}


def shade_relief(g, rng, dark_shift=0):
    """Flat tone per carved plane + crisp 1px edge light from integer height steps."""
    hgt = g["hgt"].astype(float)
    slab = g["slab"]
    region = g["region"]
    idx = np.zeros((H, W), int)
    for r, t in BASE_TONE.items():
        idx[region == r] = t
    hl = shift(hgt, 1, 0, fill=-9)  # value of the left neighbour at each pixel
    hu = shift(hgt, 0, 1, fill=-9)  # up neighbour
    hr = shift(hgt, -1, 0, fill=-9)
    hd = shift(hgt, 0, -1, fill=-9)
    hul = shift(shift(hgt, 1, 0, fill=-9), 0, 1, fill=-9)
    lit = ((hgt > hl) & (hl > -9)) | ((hgt > hu) & (hu > -9))
    shade_edge = ((hgt > hr) & (hr > -9)) | ((hgt > hd) & (hd > -9))
    cast = ((hgt < hl) & (hl > -9)) | ((hgt < hu) & (hu > -9)) | ((hgt < hul) & (hul > -9))
    idx = np.where(lit, idx + 1, idx)
    idx = np.where(lit & ((hgt > hl) & (hgt > hu)), idx + 1, idx)
    idx = np.where(shade_edge & ~lit, idx - 1, idx)
    idx = np.where(cast & ~lit, idx - 1, idx)
    # weathering: worn highlights and soft mottling
    wear = fbm(W, H, 5, 3, rng)
    idx = np.where(lit & (wear > 0.7), idx - 1, idx)
    # sparse grain: tiny dark pits and light specks on flat planes
    flat = ~lit & ~shade_edge & ~cast & slab
    for (px, py) in poisson(W, H, 4.6, rng, wrap=False):
        x, y = int(px), int(py)
        if flat[y, x]:
            idx[y, x] += 1 if rng.random() < 0.4 else -1
    # large soft stains: one shade darker in a few weathered areas (field only)
    stain = (fbm(W, H, 4, 2, rng) < 0.14) & (region == 0) & flat
    idx = np.where(stain, idx - 1, idx)
    idx = np.clip(idx - dark_shift, 1, 5)
    return idx


def pigment(cv, mask, idx, ramp, rng, coverage=0.5, cells=4, shift_lum=0, flake=0.12):
    """Faded paint remnants: stone shade index -> pigment ramp index, in soft patches with flaking."""
    n = len(RA[ramp])
    f = fbm(W, H, cells, 3, rng)
    f = 0.55 * (f + f[:, ::-1]) / 2 + 0.45 * f  # partly symmetric so both wings keep some paint
    f = (f - f.min()) / (f.max() - f.min() + 1e-9)
    patch = f > (1 - coverage)
    # ragged dithered patch borders
    edge = (f > (1 - coverage) - 0.06) & ~patch & ((np.indices((H, W)).sum(0)) % 2 == 0)
    flakes = rng.random((H, W)) < flake
    m = mask & (patch | edge) & ~flakes
    pidx = np.clip(np.round(idx * (n - 1) / 5.0).astype(int) + shift_lum, 0, n - 1)
    cv[m] = RA[ramp][pidx[m]]
    return m


def cracks(rng):
    lines = []
    for (x, y, ang, L) in ((104, 5, 2.2, 30), (3, 34, 0.15, 22), (90, 93, -1.9, 18)):
        pts = [(x, y)]
        d = 0
        while d < L:
            ang += rng.uniform(-0.4, 0.4)
            x += math.cos(ang) * 1.5
            y += math.sin(ang) * 1.5
            d += 1.5
            pts.append((x, y))
        lines.append(pts)
    return lines


def moss_layer(cv, slab, rng):
    """Moss creeping in from the bottom edge and the lower-left / broken top-right corners."""
    xs, ys = grid(W, H)
    grow = fbm(W, H, 6, 3, rng)
    d1 = (H - 3 - ys) / 9.0
    d2 = np.hypot(xs - 2, ys - (H - 2)) / 26.0
    d3 = np.hypot(xs - 108, ys - 2) / 16.0
    d4 = np.hypot(xs - 2, ys - 2) / 12.0
    score = grow - np.minimum(np.minimum(np.minimum(d1, d2), d3), d4) * 0.8
    m = slab & (score > 0.45)
    m = dilate(erode(m, 1), 1) & slab
    d = np.zeros((H, W))
    mm = m.copy()
    for _ in range(3):
        d += mm
        mm = erode(mm, 1)
    hm = d / 3.0 + 0.5 * fbm(W, H, 16, 2, rng)
    lam = lambert(hm * 2.0, 1.0, wrap=False)
    k = np.zeros((H, W), int)
    for t in (0.45, 0.62, 0.78):
        k += (lam >= t).astype(int)
    lut = np.array([1, 2, 3, 4])
    cv[m] = RA["moss"][lut[k[m]]]
    cv[m & ~shift(m, 0, -1)] = RA["moss"][0]
    cv[m & ~shift(m, 0, 1) & (rng.random((H, W)) < 0.5)] = RA["moss"][5]
    # a few trailing tendrils down the face
    for (x0, y0, L) in ((4, 40, 9), (122, 24, 12), (110, 6, 7)):
        x, y = x0, y0
        for i in range(L):
            if 0 <= x < W and 0 <= y < H and slab[y, x]:
                cv[y, x] = RA["moss"][3 if i % 2 else 2]
            y += 1
            x += 1 if (i % 4 == 3) else 0
    return m


def mural(glow=False):
    rng = rng_for("mural_dawncrane", 7)
    g = build_height(rng)
    idx = shade_relief(g, rng_for("mural_shade", 3), dark_shift=1 if glow else 0)
    slab = g["slab"]
    cv = canvas(W, H)
    cv[slab] = RA["stone_warm"][idx[slab]]
    if not glow:
        prng = rng_for("mural_pigment", 5)
        pigment(cv, g["sun"], idx, "gold", prng, coverage=0.7, cells=3, shift_lum=-1)
        pigment(cv, g["rays"], idx, "gold", prng, coverage=0.55, cells=4, shift_lum=-1)
        wings = g["fig"] & (g["raised"]["wing_l"] | g["raised"]["wing_r"])
        pigment(cv, wings, idx, "cloth_teal", prng, coverage=0.55, cells=5, shift_lum=0, flake=0.07)
        pigment(cv, g["fig"] & g["raised"]["ribbons"], idx, "cloth_teal", prng, coverage=0.5, cells=5, flake=0.06)
        pigment(cv, g["fig"] & g["raised"]["crest"], idx, "fur_russet", prng, coverage=0.8, cells=6)
        pigment(cv, g["fig"] & g["raised"]["beak"], idx, "gold", prng, coverage=0.85, cells=6, shift_lum=-1,
                flake=0.0)
        pigment(cv, g["fig"] & (g["raised"]["head"] | g["raised"]["neck"]) & ~g["raised"]["crest"], idx,
                "cloth_cream", prng, coverage=0.45, cells=6, shift_lum=0)
    # pits
    for (px, py) in poisson(W, H, 9, rng_for("mural_pits", 1), wrap=False):
        x, y = int(px), int(py)
        if slab[y, x] and slab[min(H - 1, y + 1), min(W - 1, x + 1)]:
            cv[y, x] = RA["stone_warm"][1]
            cv[y + 1, x + 1] = RA["stone_warm"][4]
    for pts in cracks(rng_for("mural_cracks", 2)):
        for (x, y) in pts:
            xi, yi = int(x), int(y)
            if 0 <= xi < W - 1 and 0 <= yi < H - 1 and slab[yi, xi]:
                cv[yi, xi] = RA["stone_warm"][0]
                if slab[yi + 1, xi + 1] and not np.array_equal(cv[yi + 1, xi + 1], RA["stone_warm"][0]):
                    cv[yi + 1, xi + 1] = RA["stone_warm"][4]
    ex, ey = g["eye"]
    cv[ey, ex] = RA["stone_warm"][0]
    cv[ey - 1, ex - 1] = RA["stone_warm"][5]
    if glow:
        apply_glow(cv, g, idx)
    moss_layer(cv, slab, rng_for("mural_moss", 4))
    out = outline(cv, "inner")
    return clear_border(out)


def apply_glow(cv, g, idx):
    """Awaken the carving: grooves and contours burn gold, the sun blazes, rays shine in aether."""
    slab = g["slab"]
    fig = g["fig"]
    contour = fig & ~erode(fig, 1)
    lines = (g["grooves"] | contour) & slab
    halo = dilate(lines, 1) & ~lines & slab & ~fig
    gi = np.clip(idx + 1, 1, 5)
    cv[halo] = RA["gold"][gi[halo]]
    cv[contour] = RA["gold"][4]
    cv[g["grooves"]] = RA["ember"][6]
    # the figure's face takes a warm under-glow
    inner = fig & ~contour & ~g["grooves"]
    gi2 = np.clip(idx, 1, 4)
    cv[inner] = RA["stone_warm"][np.clip(idx[inner] + 1, 1, 5)]
    # sun: radial blaze
    xs, ys = grid(W, H)
    d = np.hypot(xs + 0.5 - CX, ys + 0.5 - 45) / 25.0
    sk = np.clip(((1.0 - d) * 5.5).astype(int) + 1, 2, 5)
    sun = g["sun"]
    cv[sun] = RA["gold"][sk[sun]]
    cv[g["sun_groove"]] = RA["ember"][6]
    rays = g["rays"]
    cv[rays] = RA["aether"][4]
    cv[rays & ~erode(rays, 1)] = RA["aether"][5]
    rh = dilate(rays, 1) & ~rays & g["field"] & ~fig & ~sun
    ai = np.clip(idx, 1, 3)
    cv[rh] = RA["aether"][ai[rh]]
    cv[g["clouds"]] = RA["aether"][3]
    cv[g["bgroove"] & slab] = RA["gold"][3]
    ex, ey = g["eye"]
    cv[ey, ex] = RA["cloth_cream"][5]


MURALS = {
    "mural_dawncrane": lambda: mural(False),
    "mural_dawncrane_glow": lambda: mural(True),
}


if __name__ == "__main__":
    import os
    import sys
    from kit import OUT_ENV, grid_preview, save_png, preview
    for name, fn in MURALS.items():
        cv = fn()
        save_png(cv, os.path.join(OUT_ENV, "props", name + ".png"))
        preview(cv, name, scale=6)
