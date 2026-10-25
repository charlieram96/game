"""Stoneback, HD sheet: 136x128 frames, pivot (68, 120), 112 px per world unit.

Key poses: tools/art_forge/keys/stoneback/<pose>_<view>.png (gpt-image-2
paintings pixelized at 0.92 of their own grid with the fitted hd_stoneback_*
palette, see keys.py and provenance/keys_stoneback.json). Standing, Stoneback
is about 0.85 x 0.72 world units from the front and 0.79 x 0.72 in profile: a
low, heavy dome inside one board cell. Its dash is the rolled-up ball: the
shell's surface rolls inside a fixed silhouette (`animate.roll`).
"""

from __future__ import annotations

import numpy as np

from _common import HD_LIGHTING, HD_NORMALS, KITH_OUT, A, colour_classes, palette, per_pixel

NAME = "stoneback"
FRAME = (136, 128)
PIVOT = (68, 120)
PPU = 112


def glow_rules():
    pal = palette(NAME)
    # amber eyes and the flowers' yellow hearts glow; the moss glows too while focusing
    eyes = colour_classes(pal, lambda L, C, h: 0.85 if (C >= 0.15 and 25 <= h <= 110 and L >= 0.55) else 0.0)
    moss = colour_classes(pal, lambda L, C, h: 0.55 if (C >= 0.11 and 105 <= h <= 135 and L >= 0.5) else 0.0)

    def base(rgba: np.ndarray) -> np.ndarray:
        return per_pixel(rgba, eyes)

    def focusing(rgba: np.ndarray) -> np.ndarray:
        return np.maximum(per_pixel(rgba, eyes), per_pixel(rgba, moss))
    return base, focusing


def build() -> A.Sheet:
    glow, focus_glow = glow_rules()
    sh = A.Sheet(NAME, FRAME, PIVOT, PPU, KITH_OUT, kind="kith",
                 meta={"element": "stone", "route": "art_forge (gpt-image-2 key poses)"}, glow_rule=glow,
                 normal_params=HD_NORMALS, lighting=HD_LIGHTING)
    pal = palette(NAME)
    for v in "sne":
        sh.set_reference(v, f"stand_{v}")

    def brighter(f, steps, rule=focus_glow):
        return A.glow_shift(f, rule, steps, pal)

    # the round front-view ball rolls in every direction (the side view's tail-club hub breaks the circle)
    ball = sh.place("ball_s")
    rolls = {"e": [A.roll(ball, a, "z", palette=pal) for a in (0, 90, 180, 270)],
             "s": [A.roll(ball, a, "x", palette=pal) for a in (0, 50, 100, 150)],
             "n": [A.roll(ball, -a, "x", palette=pal) for a in (0, 50, 100, 150)]}
    for v in "sne":
        stand = sh.place(f"stand_{v}")
        ready = sh.place(f"ready_{v}")
        sh.add(f"idle_{v}", [A.breathe(stand, b) for b in (0, 0, 1, 1)], 4, True)
        sh.add(f"ready_{v}", [A.breathe(ready, b) for b in (0, -1, -1, 0, 1, 1)], 6, True)
        sh.add(f"move_{v}", [sh.place(f"walk_a_{v}"), A.breathe(stand, 1), sh.place(f"walk_b_{v}"), A.breathe(stand, 1)], 8, True)
        crouch = sh.place(f"crouch_{v}")
        sh.add(f"dash_windup_{v}", [crouch, rolls[v][0]], 12, False)
        sh.add(f"dash_{v}", rolls[v], 24, True)
        land = sh.place(f"land_{v}")
        sh.add(f"dash_land_{v}", [land, A.breathe(land, -1), ready], 14, False)
        # the rolling ball slams in (squashed, with the painted ram's burst of chips), then pops open
        ram = sh.place(f"ram_{v}")
        slam = A.under(A.squash(rolls[v][0], 1.12, 0.88, PIVOT), A.debris(ram))
        sh.add(f"ram_{v}", [slam, ram], 16, False)
        sh.add(f"cast_{v}", [sh.place(f"cast_wind_{v}"), sh.place(f"cast_{v}"), ready], 10, False)
        sh.add(f"melee_{v}", [sh.place(f"melee_wind_{v}"), sh.place(f"melee_{v}"), ready], 10, False)
        focus = sh.place(f"focus_{v}")
        sh.add(f"focus_{v}", [focus, brighter(focus, 1), brighter(A.breathe(focus, 1), 2), brighter(focus, 1)], 6, True, glow=focus_glow)
        guard = sh.place(f"guard_{v}")
        sh.add(f"guard_{v}", [guard, A.breathe(guard, -1)], 6, True)
        sh.add(f"hurt_{v}", [sh.place(f"hurt_{v}")], 8, True)
    sh.add("roll_s", rolls["s"], 16, True)
    dizzy = sh.place("dizzy_s")
    sh.add("stunned_s", [dizzy, A.nudge(dizzy, 1)], 6, True)
    ko = sh.place("ko_lie_s")
    sh.add("ko_s", [sh.place("ko_fall_s"), ko, A.breathe(ko, -1, 0.5)], 6, False)
    victory = sh.place("victory_s")
    sh.add("victory_s", [victory, A.lift(victory, 2), A.lift(victory, 3), A.lift(victory, 1)], 6, True)
    sleep = sh.place("sleep_s")
    sh.add("sleep_s", [sleep, A.breathe(sleep, 1, 0.6)], 2, True)
    return sh
