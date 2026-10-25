"""Shared pieces of the HD sheet recipes: glow rules and the kith battle set."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent))
import animate as A  # noqa: E402
import keys as K  # noqa: E402

ROOT = HERE.parent.parent.parent
KITH_OUT = ROOT / "assets" / "sprites" / "kith"
CHAR_OUT = ROOT / "assets" / "sprites" / "characters"
PROP_OUT = ROOT / "assets" / "sprites" / "props"

# Normal maps for 112 px/unit sheets: wide inflation, firm part creases, a little emboss.
HD_NORMALS = {"scale": 1.6, "strength": 2.5, "detail": 1.5, "crease": 0.8}
# Lighting response of HD sheets: deeper shade on the side away from a light, a clear rim.
HD_LIGHTING = {"shade_floor": 0.3, "rim_strength": 1.2, "rim_power": 3.0}


def palette(sheet: str) -> list[tuple[int, int, int]]:
    """The sheet's own fitted palette (tools/common/palette_hd.py)."""
    H = K.hd_palettes()
    return [c[:3] for n in K.sheet_ramps(sheet) for c in H.RAMPS[n]]


def colour_classes(pal: list[tuple[int, int, int]], rule) -> dict[int, float]:
    """packed rgb -> value of `rule(L, C, h)` for every palette colour."""
    lab = K.oklab(np.array(pal))
    out = {}
    for c, l in zip(pal, lab):
        C = float(np.hypot(l[1], l[2]))
        h = float((np.degrees(np.arctan2(l[2], l[1])) + 360.0) % 360.0)
        out[(c[0] << 16) | (c[1] << 8) | c[2]] = rule(float(l[0]), C, h)
    return out


def per_pixel(rgba: np.ndarray, table: dict[int, float]) -> np.ndarray:
    rgb = rgba[..., :3].astype(np.int64)
    key = (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2]
    uniq, inv = np.unique(key, return_inverse=True)
    vals = np.array([table.get(int(k), 0.0) for k in uniq], dtype=np.float32)
    return np.where(rgba[..., 3] > 0, vals[inv.reshape(key.shape)], 0.0)


def grow(seed: np.ndarray, allowed: np.ndarray, steps: int) -> np.ndarray:
    out = seed & allowed
    for _ in range(steps):
        nxt = out.copy()
        nxt[1:] |= out[:-1]
        nxt[:-1] |= out[1:]
        nxt[:, 1:] |= out[:, :-1]
        nxt[:, :-1] |= out[:, 1:]
        nxt &= allowed
        if np.array_equal(nxt, out):
            break
        out = nxt
    return out


def flame_glow(sheet: str, min_px: int = 40, small: float = 0.3):
    """Emission for fire: vivid warm colours grown into the pale core. Big blobs (flames) glow fully,
    small ones (eyes, sparks, claw trails) only a little."""
    pal = palette(sheet)
    vivid = colour_classes(pal, lambda L, C, h: 1.0 if (C >= 0.16 and 25 <= h <= 100 and L >= 0.5) else 0.0)
    pale = colour_classes(pal, lambda L, C, h: 1.0 if (L >= 0.84 and 60 <= h <= 110) else 0.0)
    cache: dict[bytes, np.ndarray] = {}

    def rule(rgba: np.ndarray) -> np.ndarray:
        k = rgba.tobytes()
        if k in cache:
            return cache[k]
        v = per_pixel(rgba, vivid) > 0.5
        p = per_pixel(rgba, pale) > 0.5
        region = grow(v, v | p, 3)
        g = np.zeros(region.shape, dtype=np.float32)
        for comp in A.components(region):
            n = comp.sum()
            if n >= min_px:
                g[comp] = 1.0
            elif n >= 3:
                g[comp] = small
        # the core (pale) glows fully, the vivid tongues a little less
        g = np.where(p & (g > 0), 1.0, g * 0.75)
        cache[k] = g
        return g
    return rule
