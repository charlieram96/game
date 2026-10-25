"""Corin, HD sheet: see _human.py. Key poses in tools/art_forge/keys/corin/."""

from __future__ import annotations

from _human import A, base_sheet, bob, idle_walk

NAME = "corin"


def build() -> A.Sheet:
    sh = base_sheet(NAME, meta={"role": "rival"})
    idle_walk(sh, 3, 9)
    bob(sh, "talk_s", "talk_s", 4, True)
    cheer = sh.place("cheer_s")
    sh.add("cheer_s", [cheer, A.lift(cheer, 3)], 5, True)
    bob(sh, "slump_s", "slump_s", 2, True, -1)
    return sh
