"""Lanternmoth (Lumen), HD sheet: 128x144 frames, pivot (64, 138), 112 px per world unit.

Hovering about 0.35 world units above its ground point with a wingspan of about
0.85 (the old sheet: 1.6). Two wingbeat keys per view (wings up, wings down)
from gpt-image-2, registered on the body (thorax and lantern abdomen) so only
the wings move; the body bobs a little with each beat. The abdomen glows.
"""

from __future__ import annotations

import numpy as np

from _common import HD_LIGHTING, HD_NORMALS, KITH_OUT, A, colour_classes, palette, per_pixel

NAME = "lanternmoth"
FRAME = (128, 144)
PIVOT = (64, 138)
PPU = 112
HOVER = 40   # px between the lowest pixel of the wings-up pose and the ground


def build() -> A.Sheet:
    pal = palette(NAME)
    gold = colour_classes(pal, lambda L, C, h: 0.85 if (C >= 0.09 and 70 <= h <= 110 and L >= 0.62) else 0.0)
    body = colour_classes(pal, lambda L, C, h: 1.0 if ((C >= 0.09 and 70 <= h <= 110 and L >= 0.55) or (L >= 0.7 and C < 0.07)) else 0.0)

    def glow(rgba: np.ndarray) -> np.ndarray:
        return per_pixel(rgba, gold)

    def body_mask(rgba: np.ndarray) -> np.ndarray:
        return per_pixel(rgba, body) > 0.5

    sh = A.Sheet(NAME, FRAME, PIVOT, PPU, KITH_OUT, kind="kith",
                 meta={"element": "light", "partner_of": "hesper", "route": "art_forge (gpt-image-2 key poses)"},
                 glow_rule=glow, normal_params=HD_NORMALS, lighting=HD_LIGHTING)
    for v in "se":
        up = sh.place(f"wings_up_{v}", register=False, dy=-HOVER)
        down = sh.place_on(f"wings_down_{v}", up, body_mask)
        sh.add(f"hover_{v}", [up, A.lift(down, 2), A.lift(up, 3), A.lift(down, 1)], 8, True)
    return sh
