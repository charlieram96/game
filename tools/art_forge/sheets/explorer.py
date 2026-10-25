"""Wren (explorer), HD sheet: see _human.py. Key poses in tools/art_forge/keys/explorer/."""

from __future__ import annotations

from _human import A, base_sheet, bob, idle_walk, lantern_glow

NAME = "explorer"


def build() -> A.Sheet:
    sh = base_sheet(NAME, lantern_glow(NAME), {"role": "player"})
    idle_walk(sh, 3, 8)
    for v in "sne":
        sneak_a, sneak_b = sh.place(f"sneak_a_{v}"), sh.place(f"sneak_b_{v}")
        sh.add(f"sneak_{v}", [sneak_a, A.breathe(sneak_a, 1, 0.45), sneak_b, A.breathe(sneak_b, 1, 0.45)], 6, True)
        sh.add(f"interact_{v}", [sh.place(f"idle_{v}"), sh.place(f"interact_{v}")], 6, False)
    for v in "se":
        bob(sh, f"sit_{v}", f"sit_{v}", 2, True, 1, 0.6)
    cheer = sh.place("cheer_s")
    sh.add("cheer_s", [cheer, A.lift(cheer, 4)], 4, True)
    sh.add("surprised_s", [sh.place("surprised_s")], 1, True)
    return sh
