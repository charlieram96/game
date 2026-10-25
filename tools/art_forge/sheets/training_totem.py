"""Training totem, HD sheet: 112x160 frames, pivot (56, 152), 112 px per world unit.

Key poses: tools/art_forge/keys/training_totem/ (gpt-image-2 paintings
pixelized at 0.78 of their own grid with the fitted hd_training_totem_*
palette). About 0.77 x 1.3 world units: it stands inside one board cell like
a creature. The hit wobbles back, then springs the other way (the rebound key
mirrored) and settles.
"""

from __future__ import annotations

import numpy as np

from _common import HD_LIGHTING, HD_NORMALS, PROP_OUT, A

NAME = "training_totem"
FRAME = (112, 160)
PIVOT = (56, 152)
PPU = 112


def build() -> A.Sheet:
    sh = A.Sheet(NAME, FRAME, PIVOT, PPU, PROP_OUT, kind="prop", meta={"route": "art_forge (gpt-image-2 key poses)"},
                 glow_rule=lambda f: np.zeros(f.shape[:2], np.float32), normal_params=HD_NORMALS, lighting=HD_LIGHTING)
    sh.set_reference("s", "idle_s")
    idle = sh.place("idle_s")
    sh.add("idle_s", [idle], 1, True)
    sh.add("hit_s", [sh.place("hit_back_s"), sh.place("hit_forward_s", flip=True), A.breathe(idle, -1, 0.7)], 12, False)
    return sh
