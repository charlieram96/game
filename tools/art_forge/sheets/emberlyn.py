"""Emberlyn, HD sheet: 144x152 frames, pivot (72, 144), 112 px per world unit.

Key poses: tools/art_forge/keys/emberlyn/<pose>_<view>.png (gpt-image-2
paintings pixelized with the fitted hd_emberlyn_* palette, see keys.py and
provenance/keys_emberlyn.json). Standing, Emberlyn is about 0.75 x 1.1 world
units seen from the front and 0.9 x 1.1 in profile: inside one board cell.
"""

from __future__ import annotations

from _common import HD_LIGHTING, HD_NORMALS, KITH_OUT, A, flame_glow, palette

NAME = "emberlyn"
FRAME = (144, 152)
PIVOT = (72, 144)
PPU = 112


def build() -> A.Sheet:
    glow = flame_glow(NAME)
    sh = A.Sheet(NAME, FRAME, PIVOT, PPU, KITH_OUT, kind="kith",
                 meta={"element": "ember", "route": "art_forge (gpt-image-2 key poses)"}, glow_rule=glow,
                 normal_params=HD_NORMALS, lighting=HD_LIGHTING)
    pal = palette(NAME)
    for v in "sne":
        sh.set_reference(v, f"stand_{v}")

    def fl(f, k):
        return A.flicker(f, k, glow)

    def brighter(f, steps):
        return A.glow_shift(f, glow, steps, pal)

    for v in "sne":
        stand = sh.place(f"stand_{v}")
        ready = sh.place(f"ready_{v}")
        sh.add(f"idle_{v}", [fl(A.breathe(stand, b), k) for k, b in enumerate((0, 0, 1, 1))], 6, True)
        sh.add(f"ready_{v}", [fl(A.breathe(ready, b), k) for k, b in enumerate((0, -1, -2, -2, -1, 0))], 8, True)
        sh.add(f"move_{v}", [fl(sh.place(f"walk_a_{v}"), 0), fl(A.breathe(stand, 1), 1),
                             fl(sh.place(f"walk_b_{v}"), 2), fl(A.breathe(stand, 1), 3)], 12, True)
        crouch = sh.place(f"crouch_{v}")
        sh.add(f"dash_windup_{v}", [fl(crouch, 0), brighter(fl(A.breathe(crouch, -2), 1), 1)], 12, False)
        leap = sh.place(f"leap_{v}")
        sh.add(f"dash_{v}", [leap, fl(leap, 1), fl(leap, 2)], 18, True)
        land = sh.place(f"land_{v}")
        sh.add(f"dash_land_{v}", [land, fl(A.breathe(land, -2), 1), fl(ready, 2)], 14, False)
        ram = sh.place(f"ram_{v}")
        sh.add(f"ram_{v}", [ram, A.squash(ram, 1.04, 0.95, PIVOT)], 16, False)
        sh.add(f"cast_{v}", [brighter(sh.place(f"cast_wind_{v}"), 1), brighter(sh.place(f"cast_{v}"), 1), fl(ready, 3)], 10, False)
        sh.add(f"melee_{v}", [sh.place(f"melee_wind_{v}"), sh.place(f"melee_{v}"), fl(ready, 1)], 10, False)
        focus = sh.place(f"focus_{v}")
        sh.add(f"focus_{v}", [fl(focus, 0), brighter(fl(focus, 1), 1), brighter(fl(A.breathe(focus, 1), 2), 2), brighter(fl(focus, 3), 1)], 8, True)
        guard = sh.place(f"guard_{v}")
        sh.add(f"guard_{v}", [fl(guard, 0), fl(A.breathe(guard, -1), 2)], 6, True)
        sh.add(f"hurt_{v}", [sh.place(f"hurt_{v}")], 8, True)
    dizzy = sh.place("dizzy_s")
    sh.add("stunned_s", [fl(dizzy, 0), fl(A.nudge(dizzy, 1), 2)], 6, True)
    ko = sh.place("ko_lie_s")
    sh.add("ko_s", [sh.place("ko_fall_s"), ko, brighter(ko, -2)], 6, False)
    victory = sh.place("victory_s")
    sh.add("victory_s", [fl(victory, 0), fl(A.lift(victory, 2), 1), fl(A.lift(victory, 3), 2), fl(A.lift(victory, 1), 3)], 8, True)
    cower = sh.place("cower_s")
    sh.add("cower_s", [cower, A.nudge(cower, 1)], 3, True)
    curl = sh.place("curl_s")
    sh.add("curl_s", [fl(curl, 0), fl(A.breathe(curl, 1, 0.5), 2)], 2, True)
    happy = sh.place("happy_s")
    sh.add("happy_s", [fl(happy, 0), fl(A.lift(happy, 3), 1), fl(A.lift(happy, 5), 2), fl(A.lift(happy, 2), 3)], 10, True)
    return sh
