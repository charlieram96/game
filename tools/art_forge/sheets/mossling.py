"""Mossling, HD sheet: 104x104 frames, pivot (52, 98), 112 px per world unit.

A tiny puffball: about 0.6 x 0.6 world units sitting (the old sheet was 0.9).
Key poses in tools/art_forge/keys/mossling/ (gpt-image-2, pixelized at 12 px of
painting per sprite pixel). The hop is a squash on the take-off, the airborne
key lifted twice, and the landing.
"""

from __future__ import annotations

from _common import HD_LIGHTING, HD_NORMALS, KITH_OUT, A

NAME = "mossling"
FRAME = (104, 104)
PIVOT = (52, 98)
PPU = 112


def build() -> A.Sheet:
    sh = A.Sheet(NAME, FRAME, PIVOT, PPU, KITH_OUT, kind="kith", meta={"element": "grove", "route": "art_forge (gpt-image-2 key poses)"},
                 normal_params=HD_NORMALS, lighting=HD_LIGHTING)
    for v in "sne":
        sh.set_reference(v, f"stand_{v}")
    for v in "se":
        stand = sh.place(f"stand_{v}")
        sh.add(f"idle_{v}", [stand, A.breathe(stand, 1, 0.5)], 3, True)
    for v in "sne":
        stand = sh.place(f"stand_{v}")
        hop = sh.place(f"hop_{v}")
        sh.add(f"hop_{v}", [A.squash(stand, 1.1, 0.88, PIVOT), A.lift(hop, 7), A.lift(hop, 12), A.lift(hop, 4)], 10, True)
    alert = sh.place("alert_s")
    sh.add("alert_s", [alert, A.breathe(alert, 1, 0.5)], 6, True)
    sleep = sh.place("sleep_s")
    sh.add("sleep_s", [sleep, A.breathe(sleep, 1, 0.6)], 2, True)
    return sh
