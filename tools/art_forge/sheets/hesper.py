"""Warden Hesper, HD sheet: see _human.py. Key poses in tools/art_forge/keys/hesper/."""

from __future__ import annotations

from _human import A, base_sheet, bob, idle_walk, lantern_glow

NAME = "hesper"


def build() -> A.Sheet:
    sh = base_sheet(NAME, lantern_glow(NAME), {"role": "mentor"})
    idle_walk(sh, 2, 6)
    bob(sh, "talk_s", "talk_s", 4, True)
    sh.add("point_e", [sh.place("point_e")], 1, True)
    return sh
