"""Group E - UI: ability / element / status icons and 9-slice panels.

Icons: bold glyphs on a transparent background, cel-shaded from the upper-left, outlined
with the darkest shade of each material ramp. Ability icons keep the glyph inside a ~26px
circle (they sit in a round button). Colours by element: ember = orange/red, stone =
grey/brown with a moss accent, utility = teal/white.

Panels: 9-slice textures whose edge segments are constant along their length, so they
stretch or tile cleanly; ornament lives in the corners only.
"""

from __future__ import annotations

import math
import os

import numpy as np
from PIL import Image, ImageDraw

from kit import (OUT_UI, RA, alpha, bezier, binarize, border_ok, canvas, clear_border, dilate, erode, grid,
                 grid_preview, outline, put, rng_for, save_png, shift)

OUT_ICONS = os.path.join(OUT_UI, "icons")
OUT_PANELS = os.path.join(OUT_UI, "panels")
SS = 4


# --------------------------------------------------------------------------
# vector mask helpers (supersampled)
# --------------------------------------------------------------------------


XF = [16.0, 16.0, 1.0]  # (cx, cy, scale) applied to all Pen coordinates (per-icon fit)


def fit(scale):
    """Decorator: draw the icon's vector shapes scaled about the frame centre."""
    def deco(fn):
        def wrapped():
            old = XF[2]
            XF[2] = scale
            try:
                return fn()
            finally:
                XF[2] = old
        wrapped.__name__ = fn.__name__
        return wrapped
    return deco


def T(x, y):
    return (XF[0] + (x - XF[0]) * XF[2], XF[1] + (y - XF[1]) * XF[2])


class Pen:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.im = Image.new("L", (w * SS, h * SS), 0)
        self.d = ImageDraw.Draw(self.im)
        self.k = XF[2] if (w, h) == (32, 32) else 1.0

    def _t(self, x, y):
        if self.k == 1.0:
            return x, y
        return T(x, y)

    def poly(self, pts, v=255):
        self.d.polygon([tuple(c * SS for c in self._t(x, y)) for x, y in pts], fill=v)
        return self

    def ellipse(self, cx, cy, rx, ry, v=255):
        cx, cy = self._t(cx, cy)
        rx, ry = rx * self.k, ry * self.k
        self.d.ellipse([(cx - rx) * SS, (cy - ry) * SS, (cx + rx) * SS, (cy + ry) * SS], fill=v)
        return self

    def line(self, pts, width, v=255, caps=True):
        P = [tuple(c * SS for c in self._t(x, y)) for x, y in pts]
        width = width * self.k
        self.d.line(P, fill=v, width=max(1, int(round(width * SS))), joint="curve")
        if caps:
            r = width * SS / 2
            for (x, y) in (P[0], P[-1]):
                self.d.ellipse([x - r, y - r, x + r, y + r], fill=v)
        return self

    def blob(self, x, y, r, v=255):
        """Filled circle of radius r (transformed)."""
        x, y = self._t(x, y)
        r = r * self.k * SS
        self.d.ellipse([x * SS - r, y * SS - r, x * SS + r, y * SS + r], fill=v)
        return self

    def taper(self, pts, w0, w1, v=255):
        n = len(pts)
        for i, (x, y) in enumerate(pts):
            t = i / max(1, n - 1)
            x, y = self._t(x, y)
            r = (w0 + (w1 - w0) * t) * self.k * SS / 2
            self.d.ellipse([x * SS - r, y * SS - r, x * SS + r, y * SS + r], fill=v)
        return self

    def mask(self, thr=128):
        return np.array(self.im.resize((self.w, self.h), Image.BOX)) >= thr


def P(w=32, h=32):
    return Pen(w, h)


def tput(cv, x, y, col):
    """put() with the current icon fit transform."""
    x, y = T(x, y)
    put(cv, x, y, col)


def cel(cv, mask, ramp, lo, hi, light_bias=0.0, bevel=True, gloss=False, flat=None):
    """Cel-shade a mask: diagonal gradient (upper-left light) quantised to lo..hi, with 1px bevels."""
    h, w = mask.shape
    if not mask.any():
        return
    ys, xs = np.nonzero(mask)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    X, Y = grid(w, h)
    u = (X + 0.5 - x0) / max(1, x1 - x0)
    v = (Y + 0.5 - y0) / max(1, y1 - y0)
    g = 1.0 - (u * 0.45 + v * 0.55) + light_bias
    if flat is not None:
        g = np.full((h, w), flat)
    n = hi - lo + 1
    k = lo + np.clip((g * n).astype(int), 0, n - 1)
    if bevel:
        top_left = mask & (~shift(mask, 1, 0) | ~shift(mask, 0, 1))
        bot_right = mask & (~shift(mask, -1, 0) | ~shift(mask, 0, -1))
        k = np.where(top_left & ~bot_right, np.minimum(k + 1, hi), k)
        k = np.where(bot_right & ~top_left, np.maximum(k - 1, lo), k)
    cv[mask] = RA[ramp][np.clip(k[mask], 0, len(RA[ramp]) - 1)]
    if gloss:
        # small specular glint near the upper-left of the shape
        gx = int(x0 + (x1 - x0) * 0.3)
        gy = int(y0 + (y1 - y0) * 0.28)
        if 0 <= gy < h and 0 <= gx < w and mask[gy, gx]:
            cv[gy, gx] = RA[ramp][min(len(RA[ramp]) - 1, hi + 1)]


def icon_finish(cv, radius=None):
    cv = binarize(cv)
    cv = outline(cv, "outer")
    cv = clear_border(cv)
    if radius is not None:
        h, w = cv.shape[:2]
        X, Y = grid(w, h)
        out = np.hypot(X + 0.5 - w / 2, Y + 0.5 - h / 2) > radius + 0.5
        n = int((cv[out, 3] > 0).sum())
        if n:
            SAFE_WARN.append(n)
    return cv


SAFE_WARN: list[int] = []


# --------------------------------------------------------------------------
# ability icons (32x32, glyph inside r=13)
# --------------------------------------------------------------------------

R_SAFE = 13.0


def flame_mask(w, h, cx, base_y, height, width, tongues=((0.0, 1.0),), lean=0.0):
    """Stylised flame: teardrop body with pointed tongues. tongues: (x offset fraction, height fraction)."""
    p = Pen(w, h)
    p.ellipse(cx, base_y - width * 0.45, width / 2, width * 0.45)
    for (dx, hf) in tongues:
        tip = (cx + dx * width * 0.5 + lean * height * hf, base_y - height * hf)
        pts = [(cx - width * 0.5 * (1 - abs(dx) * 0.6), base_y - width * 0.4),
               (tip[0] - width * 0.18, base_y - height * hf * 0.55), tip,
               (tip[0] + width * 0.18, base_y - height * hf * 0.5),
               (cx + width * 0.5 * (1 - abs(dx) * 0.6), base_y - width * 0.4)]
        p.poly(pts)
    return p.mask()


def fire_fill(cv, mask, cx, cy, hot_r):
    """Fill a flame mask: white-hot core near (cx, cy), yellow -> orange -> red toward the edges/top."""
    h, w = mask.shape
    X, Y = grid(w, h)
    d = np.hypot(X + 0.5 - cx, (Y + 0.5 - cy) * 0.8) / hot_r
    edge = mask & ~erode(mask, 1)
    edge2 = mask & ~erode(mask, 2) & ~edge
    k = np.where(d < 0.45, 6, np.where(d < 0.8, 5, np.where(d < 1.2, 4, 3)))
    k = np.where(edge2, np.minimum(k, 4), k)
    k = np.where(edge, np.minimum(k, 3), k)
    cv[mask] = RA["ember"][k[mask]]


@fit(0.76)
def ab_ember_bolt():
    cv = canvas(32, 32)
    # fireball travelling up-right with a flaring tail
    p = P()
    p.taper(bezier([(6.5, 25.5), (11, 22), (15, 18), (19.5, 13.5)], 24), 2.0, 9.0)
    for (a, L) in ((-0.5, 8), (0.35, 7)):
        sx, sy = 14, 18
        p.taper(bezier([(sx, sy), (sx - 4 + a * 3, sy + 4 - a * 3), (sx - L + a * 4, sy + L - a * 6)], 12), 3.2, 0.8)
    m = p.mask()
    head = P().ellipse(20.5, 12.0, 6.6, 6.6).mask()
    m |= head
    fire_fill(cv, m, 21.0, 11.5, 7.0)
    # bright rim on the leading edge
    lead = head & ~shift(head, 1, -1)
    cv[lead & (grid(32, 32)[0] > 20)] = RA["ember"][6]
    # trailing sparks
    for (x, y) in ((5, 19), (9, 28), (12, 25)):
        tput(cv, x, y, RA["ember"][5])
    return icon_finish(cv, R_SAFE)


def ab_cinder_arc():
    """A fan of fire sweeping open to the right from a pivot, flame tongues along the rim."""
    cv = canvas(32, 32)
    X, Y = grid(32, 32)
    px, py = 9.5, 16.0
    d = np.hypot(X + 0.5 - px, Y + 0.5 - py)
    a = np.arctan2(Y + 0.5 - py, X + 0.5 - px)
    half = math.radians(54)
    tong = 1.4 * np.cos(a * 11.0)
    fan = (np.abs(a) <= half) & (d <= 13.4 + tong) & (d >= 3.6)
    k = np.where(d > 10.4 + tong, 6, np.where(d > 8.0, 5, np.where(d > 5.8, 4, 3)))
    k = np.where(np.abs(a) > half - 0.16, np.minimum(k, 4), k)
    cv[fan] = RA["ember"][k[fan]]
    arc = (np.abs(d - 8.2) < 0.55) & (np.abs(a) <= half - 0.14)
    cv[arc] = RA["ember"][3]
    dot = np.hypot(X + 0.5 - px, Y + 0.5 - py) < 1.7
    cv[dot] = RA["ember"][5]
    return icon_finish(cv, R_SAFE)


@fit(0.76)
def ab_flash_strike():
    cv = canvas(32, 32)
    for i, off in enumerate((-6.0, 0.0, 6.0)):
        pts = bezier([(22 + off, 4.5 + abs(off) * 0.2), (17 + off * 1.1, 14), (9 + off, 27 - abs(off) * 0.2)], 30)
        outer = P().taper(pts[3:-3], 1.2, 1.2).taper(pts, 4.6, 1.0).mask()
        # crescent: widest in the middle
        p = Pen(32, 32)
        n = len(pts)
        for j, (x, y) in enumerate(pts):
            t = j / (n - 1)
            p.blob(x, y, (0.6 + 3.2 * math.sin(math.pi * t) ** 0.8) / 2)
        m = p.mask()
        core = erode(m, 1)
        cv[m] = RA["ember"][4]
        cv[core] = RA["gold"][5]
        cv[erode(core, 1)] = RA["cloth_cream"][5]
    return icon_finish(cv, R_SAFE)


def ab_heat_ring():
    cv = canvas(32, 32)
    X, Y = grid(32, 32)
    d = np.hypot(X + 0.5 - 16, Y + 0.5 - 16)
    a = np.arctan2(Y + 0.5 - 16, X + 0.5 - 16)
    tong = np.clip(np.cos(a * 8.0), 0, 1) ** 2 * 2.6
    ring_m = (d >= 6.0) & (d <= 9.4 + tong)
    k = np.where(d < 7.4, 6, np.where(d < 8.8, 5, np.where(d < 10.2, 4, 3)))
    cv[ring_m] = RA["ember"][k[ring_m]]
    cv[d < 3.8] = RA["ember"][4]
    cv[d < 2.0] = RA["ember"][6]
    return icon_finish(cv, R_SAFE)


@fit(0.86)
def ab_tail_swipe():
    """Bushy fiery fox tail hooking through a swipe, cream tip with a lick of flame, motion arc."""
    cv = canvas(32, 32)
    path = bezier([(11, 26), (5.5, 18), (8.5, 9), (17, 6.5), (22.5, 10.5)], 50)
    p = Pen(32, 32)
    n = len(path)
    for j, (x, y) in enumerate(path):
        t = j / (n - 1)
        p.blob(x, y, 1.4 + 3.6 * math.sin(math.pi * min(1.0, t * 0.92)) ** 0.75)
    tail = p.mask()
    X, Y = grid(32, 32)
    # light on the outer (upper-left) side, shade inside the hook
    ix, iy = T(14.5, 16.5)
    inner_side = np.hypot(X + 0.5 - ix, Y + 0.5 - iy) < 6.0 * XF[2]
    cel(cv, tail, "fur_russet", 2, 5)
    cv[tail & inner_side] = RA["fur_russet"][2]
    # cream tip over the last stretch
    tx_, ty_ = T(21.0, 9.5)
    tipm = tail & (np.hypot(X + 0.5 - tx_, Y + 0.5 - ty_) < 4.2 * XF[2])
    cel(cv, tipm, "cream", 2, 4)
    # fur clumps
    for (a, b, c) in (((8, 20), (6.5, 16), (7.5, 12.5)), ((11, 10), (14, 8), (17.5, 8))):
        for (x, y) in bezier([a, b, c], 10):
            x, y = T(x, y)
            if tail[int(y), int(x)]:
                cv[int(y), int(x)] = RA["fur_russet"][3]
    # lick of flame at the tip
    fl = flame_mask(32, 32, 24.0, 11.0, 6.5, 4.2, tongues=((0.0, 1.0), (0.6, 0.65)), lean=0.25)
    fire_fill(cv, fl & ~tail, *T(24.0, 9.5), 3.0)
    # swipe arc
    arc = bezier([(13.5, 27), (21, 25.5), (25.5, 19.5)], 24)
    m = P().taper(arc, 2.2, 0.7).mask() & ~tail
    cv[m] = RA["gold"][5]
    return icon_finish(cv, R_SAFE)


def boulder_glyph(cv, cx, cy, r, moss=True):
    X, Y = grid(32, 32)
    cx, cy = T(cx, cy)
    r = r * XF[2]
    m = P().ellipse(cx, cy, r, r * 0.92).mask()
    d = np.hypot(X + 0.5 - cx, Y + 0.5 - cy) / r
    u = (X + 0.5 - cx) / r
    v = (Y + 0.5 - cy) / r
    z = np.sqrt(np.clip(1 - d * d, 0, 1))
    sh = np.clip(-u * 0.58 - v * 0.58 + z * 0.6, 0, 1)
    k = 1 + np.clip((sh * 4.6).astype(int), 0, 4)
    cv[m] = RA["stone_warm"][k[m]]
    # facet cracks
    m = np.hypot((X + 0.5 - cx) / r, (Y + 0.5 - cy) / (r * 0.92)) <= 1.0
    for pts in (((cx - 1, cy - r * 0.6), (cx + 0.5, cy), (cx - 1.5, cy + r * 0.5)), ((cx + 0.5, cy), (cx + r * 0.65, cy + 1))):
        for (x, y) in bezier(list(pts), 12):
            if m[int(y), int(x)]:
                cv[int(y), int(x)] = RA["stone_warm"][1]
    if moss:
        mm = m & (Y + 0.5 < cy - r * 0.35) & (X + 0.5 < cx + r * 0.3)
        mm &= ((X + Y) % 3 != 0) | (Y + 0.5 < cy - r * 0.6)
        cv[mm] = RA["moss"][4]
        cv[mm & (Y + 0.5 < cy - r * 0.7)] = RA["moss"][5]
    return m


@fit(0.88)
def ab_boulder_toss():
    cv = canvas(32, 32)
    # dashed arc trajectory
    arc = bezier([(5, 25), (9, 8), (19, 9)], 30)
    for j, (x, y) in enumerate(arc):
        if (j // 3) % 2 == 0:
            tput(cv, x, y, RA["moss"][4])
    boulder_glyph(cv, 20, 18, 8.0)
    # motion lines
    for (x0, y0) in ((6, 19), (7, 23)):
        for i in range(4):
            tput(cv, x0 + i, y0 - i * 0.2, RA["stone_warm"][4])
    return icon_finish(cv, R_SAFE)


@fit(0.95)
def ab_ground_pound():
    """Heavy downward strike into cracked ground with shock arcs."""
    cv = canvas(32, 32)
    arrow = P().poly([(12.5, 4), (19.5, 4), (19.5, 11.5), (23.5, 11.5), (16, 19.5), (8.5, 11.5), (12.5, 11.5)]).mask()
    cel(cv, arrow, "stone_warm", 2, 5)
    X, Y = grid(32, 32)
    cv[arrow & (Y < 6)] = RA["moss"][4]
    cv[arrow & (Y < 5)] = RA["moss"][5]
    gnd = P().poly([(5.5, 21.5), (26.5, 21.5), (25, 25.5), (7, 25.5)]).mask()
    cel(cv, gnd, "stone", 2, 4)
    for pts in (((16, 21.5), (15, 23.5), (16.5, 25.5)), ((16, 21.5), (12, 23), (9, 25)),
                ((16, 21.5), (20, 23), (23, 25))):
        for (x, y) in bezier(list(pts), 10):
            put(cv, x, y, RA["stone"][0])
    for side in (-1, 1):
        arc = [(16 + side * (6 + t * 4), 20.5 - math.sin(t * math.pi) * 4) for t in np.linspace(0, 1, 10)]
        m = P().line(arc, 1.3).mask() & ~arrow & ~gnd
        cv[m] = RA["gold"][4]
    for (x, y) in ((6, 17), (25, 17), (8, 14), (24, 14)):
        put(cv, x, y, RA["stone_warm"][4])
    return icon_finish(cv, R_SAFE)


def hexagon_pts(cx, cy, r, rot=math.pi / 6):
    return [(cx + math.cos(rot + k * math.pi / 3) * r, cy + math.sin(rot + k * math.pi / 3) * r) for k in range(6)]


@fit(0.97)
def ab_stone_guard():
    cv = canvas(32, 32)
    # hex-plate shield: central hex + six partial neighbours, moss-glow seams
    outer = P().poly(hexagon_pts(16, 16, 12.5)).mask()
    cv[outer] = RA["glow_moss"][4]
    plates = []
    centre = P().poly(hexagon_pts(16, 16, 4.6)).mask()
    plates.append(centre)
    for k in range(6):
        a = k * math.pi / 3
        cx, cy = 16 + math.cos(a) * 8.0, 16 + math.sin(a) * 8.0
        pl = P().poly(hexagon_pts(cx, cy, 4.6)).mask() & erode(outer, 1)
        plates.append(pl)
    for pl in plates:
        cel(cv, pl, "stone", 2, 4, gloss=True)
    cv[outer & ~erode(outer, 1)] = RA["glow_moss"][3]
    return icon_finish(cv, R_SAFE)


@fit(0.82)
def ab_fault_line():
    """A dark fissure tearing across the ground, rock spikes erupting along it, moss-glow seam."""
    cv = canvas(32, 32)
    X, Y = grid(32, 32)
    gnd = P().poly([(4.5, 22), (27.5, 15.5), (27.5, 21), (4.5, 27)]).mask()
    cel(cv, gnd, "stone_warm", 1, 3, bevel=False)
    crack = [(5, 24.5), (9, 21.5), (12, 23.5), (16.5, 19.5), (20, 21.5), (26.5, 17.5)]
    cm = P().line(crack, 1.8).mask()
    glow = dilate(cm, 1) & gnd & ~cm
    cv[glow] = RA["glow_moss"][3]
    cv[cm] = RA["ink"][1]
    for (x, y, hgt, wd) in ((9.5, 21.5, 11, 6), (16.5, 19.5, 14, 7), (23, 19, 9.5, 5.4)):
        sp = P().poly([(x - wd / 2, y + 1), (x - 1.2, y - hgt * 0.55), (x - 0.4, y - hgt), (x + wd / 2, y + 1)]).mask()
        TX, _ = T(x, y)
        left = sp & (X + 0.5 < TX - 0.2)
        cv[sp & ~left] = RA["stone_warm"][2]
        cv[left] = RA["stone_warm"][4]
        cv[sp & ~shift(sp, 0, 1) & left] = RA["stone_warm"][5]
    return icon_finish(cv, R_SAFE)


@fit(0.9)
def ab_shell_bash():
    """Domed shell with clear raised scutes and a mossy crown, ramming into an impact burst."""
    cv = canvas(32, 32)
    X, Y = grid(32, 32)
    cx, base = 14.0, 21.0
    dome = P().ellipse(cx, base, 10.5, 11.0).mask() & (Y + 0.5 < base)
    rim = P().ellipse(cx, base + 0.4, 11.4, 2.6).mask()
    cel(cv, rim, "stone_warm", 1, 3)
    # scutes: a central crown plate, two flanking plates, marginal plates along the rim
    plates = [
        [(cx - 3.2, 11.0), (cx + 3.2, 11.0), (cx + 4.2, 15.6), (cx, 17.6), (cx - 4.2, 15.6)],
        [(cx - 4.6, 12.0), (cx - 9.0, 15.8), (cx - 8.6, 19.6), (cx - 4.0, 19.6), (cx - 4.8, 16.4)],
        [(cx + 4.6, 12.0), (cx + 9.0, 15.8), (cx + 8.6, 19.6), (cx + 4.0, 19.6), (cx + 4.8, 16.4)],
        [(cx - 3.4, 18.4), (cx + 3.4, 18.4), (cx + 3.0, 20.6), (cx - 3.0, 20.6)],
    ]
    cv[dome] = RA["stone_warm"][1]  # seams show through between plates
    for pts in plates:
        m = P().poly(pts).mask() & dome
        cel(cv, m, "stone_warm", 2, 5, gloss=True)
    cap = dome & (Y + 0.5 < 11.2)
    cel(cv, cap, "moss", 3, 5)
    burst = P().poly([(26.0, 10.5), (27.1, 14.4), (30.0, 15.5), (27.1, 16.6), (26.0, 20.5), (24.9, 16.6),
                      (22.2, 15.5), (24.9, 14.4)]).mask() & ~dome & ~rim
    cv[burst] = RA["gold"][5]
    cv[burst & ~erode(burst, 1) & (X + Y > 41)] = RA["gold"][3]
    return icon_finish(cv, R_SAFE)


@fit(0.82)
def ab_dash():
    cv = canvas(32, 32)
    # forward chevron with speed streaks
    ch = P().poly([(14, 7), (26, 16), (14, 25), (14, 20.5), (20, 16), (14, 11.5)]).mask()
    cel(cv, ch, "cloth_teal", 3, 5, gloss=False)
    ch2 = P().poly([(7, 9.5), (16, 16), (7, 22.5), (7, 18.6), (11, 16), (7, 13.4)]).mask()
    cel(cv, ch2, "water", 4, 6, bevel=True)
    for (y, x0, L) in ((8, 3, 6), (24, 3, 6)):
        for i in range(L):
            tput(cv, x0 + i, y, RA["cloth_cream"][5] if i > 1 else RA["water"][5])
    return icon_finish(cv, R_SAFE)


@fit(0.95)
def ab_focus():
    cv = canvas(32, 32)
    # stylised eye with a star pupil and radiating ticks
    eye = P().poly([(4, 16)] + [(16 + math.cos(t) * 12, 16 - math.sin(t) * 7.5) for t in np.linspace(0, math.pi, 16)]
                   + [(16 + math.cos(t) * 12, 16 + math.sin(t) * 7.5) for t in np.linspace(math.pi, 0, 16)][1:]).mask()
    cel(cv, eye, "cloth_cream", 3, 5, bevel=True)
    iris = P().ellipse(16, 16, 5.2, 5.2).mask() & eye
    cel(cv, iris, "cloth_teal", 2, 5)
    pupil = P().poly([(16, 12.5), (17.1, 15), (19.5, 16), (17.1, 17), (16, 19.5), (14.9, 17), (12.5, 16), (14.9, 15)]).mask()
    cv[pupil] = RA["cloth_cream"][5]
    for (x, y) in ((16, 4), (16, 5), (8, 6), (24, 6), (16, 27), (16, 28)):
        tput(cv, x, y, RA["water"][5])
    return icon_finish(cv, R_SAFE)


def shield_pts(cx, top, w, h):
    pts = [(cx - w / 2, top), (cx + w / 2, top), (cx + w / 2, top + h * 0.45)]
    pts += [(cx + w / 2 * math.cos(t), top + h * 0.45 + (h * 0.55) * math.sin(t)) for t in np.linspace(0, math.pi / 2, 8)]
    pts += [(cx - w / 2 * math.cos(t), top + h * 0.45 + (h * 0.55) * math.sin(t)) for t in np.linspace(math.pi / 2, 0, 8)]
    return pts


@fit(0.86)
def ab_guard():
    cv = canvas(32, 32)
    sh = P().poly(shield_pts(16, 5, 19, 22)).mask()
    cel(cv, sh, "cloth_teal", 2, 5)
    inner = erode(sh, 2)
    cel(cv, inner, "water", 4, 6)
    # emblem: vertical bar + crossbar
    cv[P().poly([(15, 9), (17, 9), (17, 23), (15, 23)]).mask() & inner] = RA["cloth_cream"][5]
    cv[P().poly([(10, 13), (22, 13), (22, 15), (10, 15)]).mask() & inner] = RA["cloth_cream"][5]
    return icon_finish(cv, R_SAFE)


@fit(1.0)
def ab_switch():
    cv = canvas(32, 32)
    # two curved arrows chasing each other in a circle
    for k, ramp in ((0, "cloth_teal"), (1, "water")):
        a0 = math.pi * k
        arc = [(16 + math.cos(a0 + t) * 9.0, 16 + math.sin(a0 + t) * 9.0) for t in np.linspace(0.35, 2.55, 20)]
        m = P().line(arc, 3.2).mask()
        end = arc[-1]
        ang = a0 + 2.55 + math.pi / 2
        tip = (end[0] + math.cos(ang) * 4.6, end[1] + math.sin(ang) * 4.6)
        perp = (math.cos(ang + math.pi / 2), math.sin(ang + math.pi / 2))
        head = P().poly([(end[0] + perp[0] * 4.0, end[1] + perp[1] * 4.0), tip,
                         (end[0] - perp[0] * 4.0, end[1] - perp[1] * 4.0)]).mask()
        cel(cv, m | head, ramp, 3, 5 if ramp == "cloth_teal" else 6)
    return icon_finish(cv, R_SAFE)


ABILITIES = {
    "ember_bolt": ab_ember_bolt,
    "cinder_arc": ab_cinder_arc,
    "flash_strike": ab_flash_strike,
    "heat_ring": ab_heat_ring,
    "tail_swipe": ab_tail_swipe,
    "boulder_toss": ab_boulder_toss,
    "ground_pound": ab_ground_pound,
    "stone_guard": ab_stone_guard,
    "fault_line": ab_fault_line,
    "shell_bash": ab_shell_bash,
    "dash": ab_dash,
    "focus": ab_focus,
    "guard": ab_guard,
    "switch": ab_switch,
}


# --------------------------------------------------------------------------
# element icons (16x16)
# --------------------------------------------------------------------------


def el_ember():
    cv = canvas(16, 16)
    m = flame_mask(16, 16, 8, 14.0, 12.0, 9.0, tongues=((0.0, 1.0), (-0.6, 0.62), (0.65, 0.55)))
    fire_fill(cv, m, 8, 11.0, 4.5)
    return icon_finish(cv)


def el_stone():
    cv = canvas(16, 16)
    m = P(16, 16).poly([(3, 9), (6, 3.5), (11, 2.5), (13.5, 7), (12.5, 13), (5, 13.5)]).mask()
    X, Y = grid(16, 16)
    cv[m] = RA["stone_warm"][3]
    cv[m & (X + Y < 13)] = RA["stone_warm"][4]
    cv[m & (X - Y > 3)] = RA["stone_warm"][2]
    cv[m & (Y > 10) & (X > 7)] = RA["stone_warm"][2]
    cv[m & (X + Y < 9)] = RA["stone_warm"][5]
    moss = m & (Y < 6) & (X > 5) & (X < 11)
    cv[moss] = RA["moss"][4]
    return icon_finish(cv)


def el_grove():
    cv = canvas(16, 16)
    pts = [(3, 13)] + [(3 + 10 * t + 2.5 * math.sin(math.pi * t), 13 - 10 * t - 2.5 * math.sin(math.pi * t))
                       for t in np.linspace(0, 1, 8)][1:]
    leaf = P(16, 16).poly([(3.5, 13), (5, 7), (9, 3.5), (13.5, 2.5), (12.5, 7), (9.5, 11), (5, 12.8)]).mask()
    cel(leaf_cv := cv, leaf, "leaf", 3, 6)
    for (x, y) in bezier([(4.5, 12), (8, 8), (12.5, 3.5)], 12):
        put(cv, x, y, RA["leaf"][2])
    put(cv, 3, 14, RA["wood"][3])
    put(cv, 2, 14, RA["wood"][2])
    return icon_finish(cv)


def el_tide():
    cv = canvas(16, 16)
    drop = P(16, 16).poly([(8, 1.5), (12.5, 8.5)] + [(8 + math.cos(t) * 4.6, 10 + math.sin(t) * 4.2)
                                                      for t in np.linspace(0, math.pi, 12)] + [(3.5, 8.5)]).mask()
    cel(cv, drop, "water", 3, 6)
    put(cv, 6, 8, RA["water"][6])
    put(cv, 6, 9, RA["water"][6])
    put(cv, 7, 7, RA["water"][5])
    return icon_finish(cv)


def el_gale():
    cv = canvas(16, 16)
    hi, lo = RA["water"][6], RA["water"][4]
    # gust 1: line with an upward curl
    for x in range(2, 12):
        put(cv, x, 5, hi)
    for (x, y) in ((12, 5), (13, 4), (13, 3), (12, 2), (11, 2), (10, 3)):
        put(cv, x, y, hi)
    # gust 2: short line in the middle
    for x in range(4, 10):
        put(cv, x, 8, lo)
    # gust 3: long line with a downward curl
    for x in range(1, 12):
        put(cv, x, 11, hi)
    for (x, y) in ((12, 11), (13, 12), (13, 13), (12, 14), (11, 14), (10, 13)):
        put(cv, x, y, hi)
    return clear_border(outline(cv, "outer"))


def el_aether():
    cv = canvas(16, 16)
    star = P(16, 16).poly([(8, 1.5), (9.6, 6.4), (14.5, 8), (9.6, 9.6), (8, 14.5), (6.4, 9.6), (1.5, 8), (6.4, 6.4)]).mask()
    cel(cv, star, "aether", 3, 6)
    cv[7:9, 7:9] = RA["aether"][6]
    for (x, y) in ((12, 3), (3, 12)):
        put(cv, x, y, RA["aether"][5])
    return icon_finish(cv)


ELEMENTS = {"ember": el_ember, "stone": el_stone, "grove": el_grove, "tide": el_tide, "gale": el_gale,
            "aether": el_aether}


# --------------------------------------------------------------------------
# status icons (16x16)
# --------------------------------------------------------------------------


def st_stun():
    cv = canvas(16, 16)
    # dizzy spiral + small star
    pts = [(8 + math.cos(t) * (0.5 + t * 0.55), 9 + math.sin(t) * (0.5 + t * 0.5)) for t in np.linspace(0, 3.6 * math.pi / 1.0, 50)]
    m = P(16, 16).line(pts, 1.5).mask()
    cv[m] = RA["gold"][5]
    cv[m & ~shift(m, 0, -1)] = RA["gold"][3]
    for (dx, dy) in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        put(cv, 13 + dx, 3 + dy, RA["gold"][5] if (dx, dy) == (0, 0) else RA["gold"][4])
    return icon_finish(cv)


def st_burn():
    cv = canvas(16, 16)
    m = flame_mask(16, 16, 7.5, 14.5, 12.5, 8.0, tongues=((0.0, 1.0), (0.7, 0.6)), lean=-0.1)
    fire_fill(cv, m, 7.5, 12.0, 3.2)
    # cooler red outer flames for 'burning' (status) vs ember element
    edge = m & ~erode(m, 1)
    cv[edge] = RA["ember"][2]
    put(cv, 12, 3, RA["ember"][5])
    put(cv, 3, 5, RA["ember"][4])
    return icon_finish(cv)


def st_slow():
    cv = canvas(16, 16)
    # hourglass: wooden caps, glass bulbs, trickling sand
    for y in (1, 2, 13, 14):
        for x in range(3, 13):
            put(cv, x, y, RA["wood"][4] if y in (1, 13) else RA["wood"][2])
    glass = P(16, 16).poly([(4, 3), (12, 3), (8.6, 8), (12, 13), (4, 13), (7.4, 8)]).mask()
    cv[glass] = RA["water"][5]
    X, Y = grid(16, 16)
    cv[glass & (X + 0.5 < 7)] = RA["water"][6]
    sand = glass & (((Y >= 4) & (Y <= 5)) | (Y >= 10))
    cv[sand] = RA["sand"][4]
    cv[sand & (X >= 8)] = RA["sand"][3]
    put(cv, 8, 8, RA["sand"][4])
    put(cv, 8, 9, RA["sand"][4])
    return icon_finish(cv)


def st_armor():
    cv = canvas(16, 16)
    plate = P(16, 16).poly([(3, 3), (6, 2), (8, 4), (10, 2), (13, 3), (13, 9), (8, 14), (3, 9)]).mask()
    cel(cv, plate, "metal", 2, 5, gloss=True)
    X, Y = grid(16, 16)
    cv[plate & (np.abs(X + 0.5 - 8) < 0.6) & (Y > 4) & (Y < 12)] = RA["metal"][1]
    for (x, y) in ((5, 5), (11, 5)):
        put(cv, x, y, RA["gold"][4])
    return icon_finish(cv)


def st_immune():
    cv = canvas(16, 16)
    sh = P(16, 16).poly(shield_pts(8, 2, 11, 12.5)).mask()
    cel(cv, sh, "gold", 3, 5)
    inner = erode(sh, 1)
    cel(cv, inner, "cloth_cream", 3, 5)
    # check mark
    m = P(16, 16).line([(5, 8), (7, 10.5), (11, 5.5)], 1.6).mask() & inner
    cv[m] = RA["cloth_teal"][3]
    return icon_finish(cv)


def st_focus():
    cv = canvas(16, 16)
    X, Y = grid(16, 16)
    d = np.hypot(X + 0.5 - 8, Y + 0.5 - 8)
    ring1 = (d > 4.6) & (d < 6.6)
    cv[ring1] = RA["water"][5]
    cv[ring1 & (X + Y > 16)] = RA["water"][4]
    cv[d < 2.2] = RA["cloth_cream"][5]
    for (x, y) in ((8, 1), (8, 14), (1, 8), (14, 8)):
        put(cv, x, y, RA["cloth_cream"][5])
    return icon_finish(cv)


def st_guard_break():
    cv = canvas(16, 16)
    sh = P(16, 16).poly(shield_pts(8, 2, 11, 12.5)).mask()
    cel(cv, sh, "cloth_teal", 2, 5)
    # jagged crack splitting the shield
    crack = P(16, 16).line([(8.5, 1.5), (7, 5), (9.5, 8), (7.5, 11), (8.5, 14.5)], 1.6).mask()
    cv[crack] = 0
    for (x, y) in ((12, 3), (3, 12)):
        put(cv, x, y, RA["cloth_red"][4])
    return icon_finish(cv)


STATUS = {"stun": st_stun, "burn": st_burn, "slow": st_slow, "armor": st_armor, "immune": st_immune,
          "focus": st_focus, "guard_break": st_guard_break}


# --------------------------------------------------------------------------
# 9-slice panels
# --------------------------------------------------------------------------


def nine_slice(w, h, b, edge_top, edge_left, corner, centre):
    """Assemble a 9-slice texture.

    edge_top(y) -> colour for row y of the top border (constant along x); edge_left(x) similarly.
    corner(x, y) -> colour or None for the top-left corner (mirrored for the others, with light flip).
    centre -> colour of the interior.
    The bottom/right edges reuse the top/left profiles flipped with darker shading supplied by the
    callables (they receive side names).
    """
    cv = canvas(w, h)
    cv[b:h - b, b:w - b] = centre
    for side in ("top", "bottom"):
        for i in range(b):
            col = edge_top(i, side)
            if col is None:
                continue
            y = i if side == "top" else h - 1 - i
            cv[y, b:w - b] = col
    for side in ("left", "right"):
        for i in range(b):
            col = edge_left(i, side)
            if col is None:
                continue
            x = i if side == "left" else w - 1 - i
            cv[b:h - b, x] = col
    for (cxs, cys, sx, sy) in (("l", "t", 1, 1), ("r", "t", -1, 1), ("l", "b", 1, -1), ("r", "b", -1, -1)):
        for j in range(b):
            for i in range(b):
                col = corner(i, j, cxs + cys)
                if col is None:
                    continue
                x = i if sx > 0 else w - 1 - i
                y = j if sy > 0 else h - 1 - j
                cv[y, x] = col
    return cv


def frame_profile(i, side, layers):
    """layers: list of (thickness, (lit_colour, shade_colour)) from the outside in."""
    pos = 0
    for (t, (lit, dark)) in layers:
        if i < pos + t:
            return lit if side in ("top", "left") else dark
        pos += t
    return None


def panel(name, b, layers, centre, corner_fn):
    w = h = 48

    def edge(i, side):
        return frame_profile(i, side, layers)

    def corner(i, j, which):
        c = corner_fn(i, j, which)
        if c is not None:
            return c
        # default: the frame bands meet at a mitre
        side_h = "top" if which[1] == "t" else "bottom"
        side_v = "left" if which[0] == "l" else "right"
        if j <= i:
            return edge(j, side_h) if edge(j, side_h) is not None else (centre if i >= b and j >= b else None)
        return edge(i, side_v)

    cv = nine_slice(w, h, b, edge, edge, corner, centre)
    return cv


def C_(ramp, i):
    return RA[ramp][i]


def panel_parchment():
    """Warm parchment with a dark-wood frame, brass inner line and ornate brass corners."""
    b = 16
    layers = [
        (1, (C_("wood", 0), C_("wood", 0))),
        (1, (C_("wood", 3), C_("wood", 1))),
        (3, (C_("wood", 2), C_("wood", 1))),
        (1, (C_("wood", 1), C_("wood", 0))),
        (1, (C_("gold", 4), C_("gold", 2))),
        (1, (C_("gold", 2), C_("gold", 3))),
        (1, (C_("ui_parchment", 1), C_("ui_parchment", 1))),
        (1, (C_("ui_parchment", 2), C_("ui_parchment", 2))),
        (8, (C_("ui_parchment", 3), C_("ui_parchment", 3))),
    ]
    centre = C_("ui_parchment", 3)

    def corner(i, j, which):
        # ornate brass corner bracket: an L-shaped plate along both edges, a rivet, and a curl
        lit = (i + j) < 10
        # L-bracket arms (over the wood band, 3px thick, 11px long)
        if (2 <= j <= 4 and 2 <= i <= 12) or (2 <= i <= 4 and 2 <= j <= 12):
            if j == 2 or i == 2:
                return C_("gold", 5) if lit else C_("gold", 4)
            if j == 4 and i > 4 or i == 4 and j > 4:
                return C_("gold", 2)
            return C_("gold", 4) if lit else C_("gold", 3)
        # bracket arm ends: small spade points
        if (j == 3 and i == 13) or (i == 3 and j == 13):
            return C_("gold", 3)
        if (1 <= j <= 5 and i == 1) or (1 <= i <= 5 and j == 1):
            return C_("gold", 1)
        # rivet boss in the corner
        r = math.hypot(i - 3.0, j - 3.0)
        if r < 1.6:
            return C_("gold", 5) if (i + j) <= 6 else C_("gold", 2)
        # curl flourish inside the corner (on the parchment margin)
        cr = math.hypot(i - 8.5, j - 8.5)
        if 1.6 < cr < 2.7 and not (i > 8.5 and j > 8.5):
            return C_("gold", 3) if (i + j) < 17 else C_("gold", 2)
        return None

    return panel("panel_parchment", b, layers, centre, corner)


def panel_wood():
    """Dark carved-wood frame with a deep teal-ink interior (for HUD panels and menus)."""
    b = 16
    layers = [
        (1, (C_("wood", 0), C_("wood", 0))),
        (1, (C_("wood", 3), C_("wood", 1))),
        (1, (C_("wood", 2), C_("wood", 1))),
        (1, (C_("wood", 1), C_("wood", 0))),  # carved groove
        (2, (C_("wood", 2), C_("wood", 1))),
        (1, (C_("wood", 3), C_("wood", 2))),
        (1, (C_("wood", 0), C_("wood", 0))),
        (1, (C_("ink", 0), C_("ink", 0))),
        (7, (C_("cloth_teal", 0), C_("cloth_teal", 0))),
    ]
    centre = C_("cloth_teal", 0)

    def corner(i, j, which):
        # carved rosette knot in the corner
        r = math.hypot(i - 3.5, j - 3.5)
        if r < 4.2:
            if r > 3.2:
                return C_("wood", 0)
            if r < 1.4:
                return C_("gold", 4) if (i + j) < 7 else C_("gold", 2)
            return C_("wood", 3) if (i + j) < 7 else C_("wood", 2)
        return None

    cv = panel("panel_wood", b, layers, centre, corner)
    # carved notches along the frame band (period 8 divides the 16px edge segment -> tiles cleanly)
    for x in range(b, 48 - b):
        if (x - b) % 8 == 3:
            for (y, col) in ((4, C_("wood", 3)), (5, C_("wood", 1))):
                cv[y, x] = col
                cv[47 - y, x] = C_("wood", 2) if y == 4 else C_("wood", 0)
                cv[x, y] = col
                cv[x, 47 - y] = C_("wood", 2) if y == 4 else C_("wood", 0)
    return cv


def button(state="normal"):
    """48x24 9-slice (8px borders): carved wood plate with a brass rim."""
    w, h, b = 48, 24, 8
    if state == "normal":
        rim = (C_("gold", 4), C_("gold", 2))
        face = C_("wood", 3)
        face_lit = C_("wood", 4)
        face_dark = C_("wood", 2)
    elif state == "hover":
        rim = (C_("gold", 5), C_("gold", 3))
        face = C_("wood", 4)
        face_lit = C_("wood", 5)
        face_dark = C_("wood", 3)
    else:
        rim = (C_("gold", 2), C_("gold", 3))
        face = C_("wood", 2)
        face_lit = C_("wood", 1)  # pressed: inverted bevel
        face_dark = C_("wood", 3)
    cv = canvas(w, h)
    X, Y = grid(w, h)
    # rounded rectangle body
    body = np.ones((h, w), bool)
    for (cx, cy) in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        body[cy, cx] = False
    body[0, 1] = body[1, 0] = body[0, w - 2] = body[1, w - 1] = False
    body[h - 1, 1] = body[h - 2, 0] = body[h - 1, w - 2] = body[h - 2, w - 1] = False
    cv[body] = C_("wood", 0)
    rim_m = erode(body, 1)
    top_left = rim_m & ((Y <= 2) | (X <= 2))
    cv[rim_m] = rim[1]
    cv[top_left & (Y < h - 3) & (X < w - 3)] = rim[0]
    inner = erode(body, 3)
    cv[erode(body, 2) & ~inner] = C_("wood", 0) if state != "pressed" else C_("wood", 0)
    cv[inner] = face
    ins = inner & ~erode(inner, 1)
    tl = ins & ((Y == Y[inner].min()) | (X == X[inner].min()))
    br = ins & ~tl
    cv[tl] = face_lit
    cv[br] = face_dark
    # carved groove running inside the border (within the 8px slice margins)
    g_out = erode(body, 5)
    groove = g_out & ~erode(body, 6)
    gt = groove & ((Y == Y[g_out].min()) | (X == X[g_out].min()))
    gb = groove & ~gt
    if state != "pressed":
        cv[gt] = face_dark
        cv[gb] = face_lit
    else:
        cv[gt] = face_dark
        cv[gb] = face_lit
    if state == "pressed":
        # content sits lower: deeper top shadow
        cv[inner & (Y == Y[inner].min() + 1)] = C_("wood", 1)
    if state == "hover":
        # warm glint on the rim corners
        cv[2, 3] = C_("ember", 6)
        cv[3, 2] = C_("gold", 5)
    return clear_border(cv) if False else cv


def bar_frame():
    """64x12 9-slice (4px borders): thin metal frame; transparent interior so the fill shows through."""
    w, h = 64, 12
    cv = canvas(w, h)
    X, Y = grid(w, h)
    body = np.ones((h, w), bool)
    for (x, y) in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        body[y, x] = False
    cv[body] = C_("metal", 0)
    ring1 = erode(body, 1)
    cv[ring1] = C_("metal", 3)
    cv[ring1 & ((Y >= h - 3) | (X >= w - 3))] = C_("metal", 2)
    cv[ring1 & (Y <= 1)] = C_("metal", 4)
    ring2 = erode(body, 2)
    cv[ring2] = C_("metal", 1)
    hole = erode(body, 3)
    cv[hole] = 0
    # end caps: small rivets
    for x in (1, w - 2):
        cv[h // 2 - 1:h // 2 + 1, x] = C_("gold", 4)
    return cv


def aim_reticle():
    """Crisp ring reticle with four inward ticks and a centre dot."""
    w = h = 32
    cv = canvas(w, h)
    X, Y = grid(w, h)
    d = np.hypot(X + 0.5 - 16, Y + 0.5 - 16)
    ring_m = (d >= 9.0) & (d <= 10.6)
    cv[ring_m] = C_("cloth_cream", 5)
    for (x0, y0, dx, dy) in ((16, 3, 0, 1), (16, 28, 0, -1), (3, 16, 1, 0), (28, 16, -1, 0)):
        for i in range(5):
            xx, yy = x0 + dx * i, y0 + dy * i
            cv[yy, xx] = C_("cloth_cream", 5)
            cv[yy - (1 if dx else 0) if dx else yy, xx - (1 if dy else 0) if dy else xx] = C_("cloth_cream", 5)
    cv[15:17, 15:17] = C_("cloth_cream", 5)
    out = outline(cv, "outer", color=C_("ink", 1))
    return clear_border(out)


def name_plate():
    """64x16 9-slice (6px borders): small brass plate with rounded ends and rivets."""
    w, h = 64, 16
    cv = canvas(w, h)
    X, Y = grid(w, h)
    body = np.zeros((h, w), bool)
    body[1:h - 1, 3:w - 3] = True
    for (cx, side) in ((6.0, -1), (w - 6.0, 1)):
        body |= ((X + 0.5 - cx) ** 2 / 36 + (Y + 0.5 - h / 2) ** 2 / 49 <= 1.0) & (side * (X + 0.5 - cx) >= 0)
    cv[body] = C_("gold", 1)
    inner = erode(body, 1)
    cv[inner] = C_("gold", 3)
    cv[inner & (Y <= 3)] = C_("gold", 4)
    cv[inner & (Y == 2)] = C_("gold", 5)
    cv[inner & (Y >= h - 4)] = C_("gold", 2)
    face = erode(body, 3)
    cv[face] = C_("gold", 3)
    cv[face & (Y == Y[face].min())] = C_("gold", 2)
    for x in (3, w - 4):
        cv[7:9, x] = C_("gold", 5)
        cv[8, x] = C_("gold", 2)
    return cv


def cursor_hand():
    """16x16 pointer glove (hotspot at the fingertip, top-left)."""
    w = h = 16
    cv = canvas(w, h)
    bm = [
        "..oo..........",
        ".ohho.........",
        ".ohho.........",
        ".ohhooooo.....",
        ".ohhohhohooo..",
        ".ohhohhohohho.",
        "oohhhhhhhhhho.",
        "ohhhhhhhhhhho.",
        "ohhhhhhhhhhso.",
        ".ohhhhhhhhhso.",
        ".ohhhhhhhhso..",
        "..ohhhhhhsso..",
        "...oooooooo...",
        "...ossssssso..",
        "...oooooooo...",
    ]
    cols = {"o": C_("ink", 1), "h": C_("cloth_cream", 5), "s": C_("cloth_cream", 3)}
    for j, row in enumerate(bm):
        for i, ch in enumerate(row):
            if ch in cols:
                cv[j + 1, i + 1] = cols[ch]
    # cuff
    for i in range(4, 12):
        if cv[14, i, 3] and cols["s"] is not None:
            cv[14, i] = C_("cloth_teal", 3)
    return clear_border(cv)


PANELS = {
    "panel_parchment": panel_parchment,
    "panel_wood": panel_wood,
    "button": lambda: button("normal"),
    "button_hover": lambda: button("hover"),
    "button_pressed": lambda: button("pressed"),
    "bar_frame": bar_frame,
    "aim_reticle": aim_reticle,
    "name_plate": name_plate,
    "cursor_hand": cursor_hand,
}


def build(only=None, preview_on=True):
    items_ab, items_small, items_pan = [], [], []
    for name, fn in ABILITIES.items():
        if only and ("ability_" + name) not in only and name not in only:
            continue
        SAFE_WARN.clear()
        cv = fn()
        if SAFE_WARN:
            print(f"ability_{name}: {SAFE_WARN[0]} px outside the r={R_SAFE} safe circle")
        assert set(np.unique(cv[..., 3])) <= {0, 255}
        save_png(cv, os.path.join(OUT_ICONS, "ability_" + name + ".png"))
        items_ab.append((name, cv))
    for prefix, table in (("element_", ELEMENTS), ("status_", STATUS)):
        for name, fn in table.items():
            if only and (prefix + name) not in only:
                continue
            cv = fn()
            save_png(cv, os.path.join(OUT_ICONS, prefix + name + ".png"))
            items_small.append((prefix + name, cv))
    for name, fn in PANELS.items():
        if only and name not in only:
            continue
        cv = fn()
        save_png(cv, os.path.join(OUT_PANELS, name + ".png"))
        items_pan.append((name, cv))
    if preview_on:
        if items_ab:
            grid_preview(items_ab, "ui_abilities", scale=4, cols=7, cell_bg=(46, 52, 64, 255))
            # same icons inside a mock round button, with the safe circle drawn
            mock = []
            X, Y = grid(32, 32)
            d = np.hypot(X + 0.5 - 16, Y + 0.5 - 16)
            for name, cv in items_ab:
                bg = canvas(32, 32)
                bg[d <= 15.5] = RA["cloth_teal"][0]
                bg[(d > 14.5) & (d <= 15.5)] = RA["gold"][2]
                bg[(np.abs(d - (R_SAFE + 0.5)) < 0.5)] = RA["ink"][3]
                from kit import over as _over
                mock.append((name, _over(bg, cv)))
            grid_preview(mock, "ui_abilities_button", scale=4, cols=7, cell_bg=(30, 34, 40, 255))
        if items_small:
            grid_preview(items_small, "ui_small_icons", scale=5, cols=7, cell_bg=(46, 52, 64, 255))
        if items_pan:
            grid_preview(items_pan, "ui_panels", scale=4, cols=5)
    return items_ab + items_small + items_pan


if __name__ == "__main__":
    import sys
    build(sys.argv[1:] or None)
