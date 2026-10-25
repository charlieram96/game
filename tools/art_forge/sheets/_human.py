"""HD people: 128x240 frames, pivot (64, 232), 112 px per world unit (about 1.6-1.8 world units tall).

Every person is built from key poses idle/walk_a/walk_b per view plus their own
extras; the walk's passing frames are the idle with the legs straightened (the
body rises 2 px), so a 4-frame cycle needs only two drawn strides.
"""

from __future__ import annotations

import numpy as np

from _common import CHAR_OUT, HD_LIGHTING, HD_NORMALS, A, colour_classes, grow, palette, per_pixel

FRAME = (128, 240)
PIVOT = (64, 232)
PPU = 112


def lantern_glow(sheet: str):
    """A lantern's warm glass glows: pale warm yellow cores grown a little into vivid warm neighbours."""
    pal = palette(sheet)
    core = colour_classes(pal, lambda L, C, h: 1.0 if (L >= 0.86 and C >= 0.09 and 75 <= h <= 110) else 0.0)
    warm = colour_classes(pal, lambda L, C, h: 1.0 if (C >= 0.13 and 40 <= h <= 100 and L >= 0.62) else 0.0)

    def rule(rgba: np.ndarray) -> np.ndarray:
        c = per_pixel(rgba, core) > 0.5
        w = per_pixel(rgba, warm) > 0.5
        region = grow(c, c | w, 2)
        g = np.zeros(region.shape, np.float32)
        for comp in A.components(region):
            if 3 <= comp.sum() <= 260:   # lantern glass, not a whole sunlit jacket
                g[comp] = 0.9
        return g
    return rule


def no_glow(rgba: np.ndarray) -> np.ndarray:
    return np.zeros(rgba.shape[:2], np.float32)


def base_sheet(name: str, glow=None, meta: dict | None = None) -> A.Sheet:
    sh = A.Sheet(name, FRAME, PIVOT, PPU, CHAR_OUT, kind="character",
                 meta={"route": "art_forge (gpt-image-2 key poses)", **(meta or {})},
                 glow_rule=glow or no_glow, normal_params=HD_NORMALS, lighting=HD_LIGHTING)
    for v in "sne":
        sh.set_reference(v, f"idle_{v}")
    return sh


def idle_walk(sh: A.Sheet, idle_fps: float, walk_fps: float, loop_idle=True, loop_walk=True, views="sne") -> None:
    for v in views:
        idle = sh.place(f"idle_{v}")
        sh.add(f"idle_{v}", [idle, A.breathe(idle, 1, 0.4)], idle_fps, loop_idle)
        passing = A.breathe(idle, 2, 0.45)
        sh.add(f"walk_{v}", [sh.place(f"walk_a_{v}"), passing, sh.place(f"walk_b_{v}"), passing], walk_fps, loop_walk)


def bob(sh: A.Sheet, anim: str, key: str, fps: float, loop: bool, n: int = 1, frac: float = 0.4) -> None:
    f = sh.place(key)
    sh.add(anim, [f, A.breathe(f, n, frac)], fps, loop)
