#!/usr/bin/env python3
"""Regenerate every Wildbound character / creature / prop / portrait sprite sheet.

    python3 tools/sprite_forge/build.py              # sheets only
    python3 tools/sprite_forge/build.py --previews   # + review previews in tools/sprite_forge/previews/

Outputs (PNG + JSON manifest per sheet, via tools/common/sheet.py):
    assets/sprites/characters/  explorer, hesper, corin, villager_farmer, villager_baker, sigilbinder, crowd, crowd_back
    assets/sprites/kith/        emberlyn, stoneback, mossling, lanternmoth
    assets/sprites/props/       training_totem
    assets/sprites/portraits/   portrait_hesper, portrait_corin, portrait_player, portrait_emberlyn
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

import corin  # noqa: E402
import crowd  # noqa: E402
import emberlyn  # noqa: E402
import explorer  # noqa: E402
import hesper  # noqa: E402
import lanternmoth  # noqa: E402
import mossling  # noqa: E402
import portraits  # noqa: E402
import preview  # noqa: E402
import props  # noqa: E402
import sigilbinder  # noqa: E402
import stoneback  # noqa: E402
import validate  # noqa: E402
import villagers  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = {
    "characters": os.path.join(ROOT, "assets", "sprites", "characters"),
    "kith": os.path.join(ROOT, "assets", "sprites", "kith"),
    "props": os.path.join(ROOT, "assets", "sprites", "props"),
    "portraits": os.path.join(ROOT, "assets", "sprites", "portraits"),
}

JOBS = [
    ("kith", emberlyn.build),
    ("kith", stoneback.build),
    ("kith", mossling.build),
    ("kith", lanternmoth.build),
    ("characters", explorer.build),
    ("characters", corin.build),
    ("characters", hesper.build),
    ("characters", villagers.build),
    ("characters", sigilbinder.build),
    ("characters", crowd.build),
    ("props", props.build),
    ("portraits", portraits.build),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--previews", action="store_true", help="also write review previews (contact sheets + strips)")
    args = ap.parse_args()
    t0 = time.time()
    built = []
    for folder, fn in JOBS:
        res = fn(OUT[folder])
        sheets = res if isinstance(res, list) else [res]
        for sb in sheets:
            png = os.path.join(OUT[folder], f"{sb.name}.png")
            with open(os.path.join(OUT[folder], f"{sb.name}.json")) as fh:
                man = json.load(fh)
            built.append((folder, sb.name, man["frame_count"], len(man["animations"])))
            if args.previews:
                preview.contact(png, scale=4)
                preview.strips(sb, scale=4)
    for folder, name, n, a in built:
        print(f"  {folder:11s} {name:20s} {n:4d} frames  {a:3d} animations")
    print(f"built {len(built)} sheets in {time.time() - t0:.1f}s")
    return validate.main()


if __name__ == "__main__":
    sys.exit(main())
