"""The Sigilbinder, HD sheet: 160x240 frames (wide for the streaming cloak), pivot (80, 232), 112 px per world unit.

About 1.75 world units tall, like the old sheet. Key poses in
tools/art_forge/keys/sigilbinder/. The eyes in the hood and the rune chain on
the arm glow.
"""

from __future__ import annotations

import numpy as np

from _common import CHAR_OUT, HD_LIGHTING, HD_NORMALS, A, colour_classes, palette, per_pixel

NAME = "sigilbinder"
FRAME = (160, 240)
PIVOT = (80, 232)
PPU = 112


def build() -> A.Sheet:
    pal = palette(NAME)
    sigil = colour_classes(pal, lambda L, C, h: 0.8 if (C >= 0.1 and (h >= 320 or h <= 30) and L >= 0.45) else 0.0)

    def glow(rgba: np.ndarray) -> np.ndarray:
        return per_pixel(rgba, sigil)

    sh = A.Sheet(NAME, FRAME, PIVOT, PPU, CHAR_OUT, kind="character",
                 meta={"role": "antagonist", "route": "art_forge (gpt-image-2 key poses)"},
                 glow_rule=glow, normal_params=HD_NORMALS, lighting=HD_LIGHTING)
    for v in "se":
        sh.set_reference(v, f"idle_{v}")
        idle = sh.place(f"idle_{v}")
        sh.add(f"idle_{v}", [idle, A.breathe(idle, 1, 0.4)], 2, True)
    run_a, run_b = sh.place("run_a_e"), sh.place("run_b_e")
    sh.add("run_e", [run_a, A.lift(run_a, 4), run_b, A.lift(run_b, 4)], 10, True)
    return sh
