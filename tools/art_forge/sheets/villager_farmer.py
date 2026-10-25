"""Bram the farmer, HD sheet: see _human.py. Key poses in tools/art_forge/keys/villager_farmer/."""

from __future__ import annotations

from _human import A, base_sheet, bob, idle_walk

NAME = "villager_farmer"


def build() -> A.Sheet:
    sh = base_sheet(NAME, meta={"role": "villager"})
    idle_walk(sh, 2, 6)
    bob(sh, "talk_s", "talk_s", 4, True)
    return sh
