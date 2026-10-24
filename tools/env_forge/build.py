"""Regenerate every env_forge asset and validate the results.

    python3 tools/env_forge/build.py                 # everything (+ previews)
    python3 tools/env_forge/build.py textures fx     # only some groups
    python3 tools/env_forge/build.py --clean         # delete our known outputs first, then rebuild
    python3 tools/env_forge/build.py --no-preview    # skip preview images
    python3 tools/env_forge/build.py --check         # only validate what is on disk

Groups: textures, foliage, props, fx, ui. Outputs go to assets/environments/, assets/effects/
and assets/ui/; previews to tools/env_forge/previews/ (gitignored).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import foliage  # noqa: E402
import fx  # noqa: E402
import props  # noqa: E402
import textures  # noqa: E402
import ui  # noqa: E402
from kit import OUT_ENV, OUT_FX, OUT_UI, _REV  # noqa: E402

# --------------------------------------------------------------------------
# expected outputs (name -> (size, kind))  kind: tex | sprite | sheet | fxsheet | ui
# --------------------------------------------------------------------------

TEX = {n: ((64, 64) if n == "water_base" else (48, 48)) for n in textures.TEXTURES}

FOLIAGE = {
    "tree_oak_a": (96, 128), "tree_oak_b": (88, 112), "tree_pine": (64, 128), "tree_birch": (64, 112),
    "tree_glimmer": (96, 128), "tree_dead": (64, 96), "bush_a": (40, 28), "bush_b": (32, 24),
    "bush_berry": (32, 24), "fern_a": (24, 20), "fern_b": (24, 20), "reeds_a": (16, 24), "reeds_b": (16, 24),
    "grass_tuft_a": (16, 16), "grass_tuft_b": (16, 16), "grass_tuft_c": (16, 16), "grass_tuft_d": (16, 16),
    "flowers_red": (16, 16), "flowers_yellow": (16, 16), "flowers_blue": (16, 16), "flowers_white": (16, 16),
    "flowers_pink": (16, 16), "mushroom_a": (16, 16), "mushroom_b": (16, 16), "mushroom_glow": (16, 16),
    "rock_small_a": (24, 16), "rock_small_b": (24, 16), "rock_small_c": (24, 16), "stump": (24, 20),
    "kindlemoss": (16, 16), "lily_pad": (16, 16), "log_hollow": (64, 32),
}

PROPS = {
    "lantern_post": (16, 48), "signpost": (24, 32), "barrel": (20, 24), "crate": (24, 24), "hay_bale": (32, 24),
    "flower_planter": (32, 20), "snare_broken": (24, 16), "well_bucket": (16, 16), "door_wood": (24, 36),
    "window_lit": (20, 20), "window_dark": (20, 20), "standing_stone": (32, 64), "mural_dawncrane": (128, 96),
    "mural_dawncrane_glow": (128, 96),
}

PROP_SHEETS = {  # name -> (frame size, pivot, {anim: (frames, fps, loop)})
    "banner_red": ((16, 48), (8, 47), {"wave_s": (4, 6, True)}),
    "banner_blue": ((16, 48), (8, 47), {"wave_s": (4, 6, True)}),
    "campfire": ((32, 32), (16, 29), {"unlit_s": (1, None, None), "lit_s": (4, 10, True)}),
    "brazier": ((24, 32), (12, 30), {"lit_s": (4, 10, True)}),
}

FX_SHEETS = {  # name -> (frame size, {anim: (frames, fps, loop)}, required pivot or None)
    "hit_spark": ((32, 32), {"play_s": (6, 24, False)}, None),
    "hit_heavy": ((64, 64), {"play_s": (7, 20, False)}, None),
    "dust_puff": ((24, 24), {"play_s": (6, 16, False)}, None),
    "stun_stars": ((32, 16), {"loop_s": (6, 10, True)}, None),
    "ember_bolt": ((32, 16), {"loop_s": (4, 16, True)}, (16, 8)),
    "ember_impact": ((32, 32), {"play_s": (5, 20, False)}, None),
    "flash_strike": ((48, 48), {"play_s": (4, 20, False)}, None),
    "fire_pillar": ((32, 48), {"play_s": (6, 14, False)}, None),
    "burn_flame": ((16, 16), {"loop_s": (4, 12, True)}, None),
    "boulder": ((32, 32), {"loop_s": (4, 12, True)}, (16, 16)),
    "rock_burst": ((48, 48), {"play_s": (6, 18, False)}, None),
    "fault_spike": ((32, 48), {"play_s": (6, 16, False)}, None),
    "stone_guard": ((64, 64), {"loop_s": (4, 8, True)}, (32, 60)),
    "focus_aura": ((48, 64), {"loop_s": (6, 12, True)}, (24, 60)),
    "perfect_flash": ((64, 64), {"play_s": (6, 24, False)}, None),
    "guard_break": ((48, 48), {"play_s": (6, 18, False)}, None),
    "ko_burst": ((64, 64), {"play_s": (8, 16, False)}, None),
    "trust_motes": ((16, 16), {"loop_s": (4, 8, True)}, None),
    "sigil_glow": ((32, 32), {"loop_s": (4, 8, True)}, None),
    "emotes": ((16, 16), {a + "_s": (2, 4, True) for a in ("exclaim", "question", "heart", "note", "sweat", "anger",
                                                          "zzz")}, (8, 15)),
    "cinder_arc": ((96, 96), {"play_s": (5, 20, False)}, (48, 48)),
    "heat_ring": ((96, 96), {"play_s": (8, 16, False)}, (48, 48)),
    "shockwave": ((96, 96), {"play_s": (6, 18, False)}, (48, 48)),
    "ground_crack": ((64, 64), {"play_s": (4, 6, False)}, (32, 32)),
    "scorch": ((48, 48), {"play_s": (4, 4, False)}, (24, 24)),
}

UI_ICONS = {}
for _n in ui.ABILITIES:
    UI_ICONS["ability_" + _n] = (32, 32)
for _n in ui.ELEMENTS:
    UI_ICONS["element_" + _n] = (16, 16)
for _n in ui.STATUS:
    UI_ICONS["status_" + _n] = (16, 16)

UI_PANELS = {
    "panel_parchment": (48, 48), "panel_wood": (48, 48), "button": (48, 24), "button_hover": (48, 24),
    "button_pressed": (48, 24), "bar_frame": (64, 12), "aim_reticle": (32, 32), "name_plate": (64, 16),
    "cursor_hand": (16, 16),
}


def expected_files():
    out = []
    out += [os.path.join(OUT_ENV, "textures", n + ".png") for n in TEX]
    out += [os.path.join(OUT_ENV, "foliage", n + ".png") for n in FOLIAGE]
    out += [os.path.join(OUT_ENV, "props", n + ".png") for n in PROPS]
    for n in PROP_SHEETS:
        out += [os.path.join(OUT_ENV, "props", n + ext) for ext in (".png", ".json")]
    for n in FX_SHEETS:
        out += [os.path.join(OUT_FX, n + ext) for ext in (".png", ".json")]
    out += [os.path.join(OUT_UI, "icons", n + ".png") for n in UI_ICONS]
    out += [os.path.join(OUT_UI, "panels", n + ".png") for n in UI_PANELS]
    return out


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------


def _load(path):
    return np.array(Image.open(path).convert("RGBA"))


def _palette_ok(a):
    vis = a[..., 3] > 0
    cols = {tuple(int(v) for v in c) for c in a[vis][:, :3]}
    return [c for c in cols if c not in _REV]


def _border_ok(a):
    al = a[..., 3]
    return not (al[0].any() or al[-1].any() or al[:, 0].any() or al[:, -1].any())


def check():
    problems = []

    def chk_png(path, size, opaque=False, binary=True, border=True):
        if not os.path.exists(path):
            problems.append(f"missing {path}")
            return None
        a = _load(path)
        if (a.shape[1], a.shape[0]) != tuple(size):
            problems.append(f"{path}: size {a.shape[1]}x{a.shape[0]} != {size[0]}x{size[1]}")
        bad = _palette_ok(a)
        if bad:
            problems.append(f"{path}: {len(bad)} off-palette colours e.g. {bad[:3]}")
        if opaque and not (a[..., 3] == 255).all():
            problems.append(f"{path}: texture must be fully opaque")
        if binary and not set(np.unique(a[..., 3])) <= {0, 255}:
            problems.append(f"{path}: partial alpha in a sprite")
        if border and not _border_ok(a):
            problems.append(f"{path}: touches the 1px border")
        return a

    for n, size in TEX.items():
        chk_png(os.path.join(OUT_ENV, "textures", n + ".png"), size, opaque=True, border=False)
    for n, size in FOLIAGE.items():
        chk_png(os.path.join(OUT_ENV, "foliage", n + ".png"), size)
    for n, size in PROPS.items():
        chk_png(os.path.join(OUT_ENV, "props", n + ".png"), size)

    def chk_sheet(folder, n, fsize, anims, pivot, binary):
        jp = os.path.join(folder, n + ".json")
        pp = os.path.join(folder, n + ".png")
        if not (os.path.exists(jp) and os.path.exists(pp)):
            problems.append(f"missing sheet {n}")
            return
        man = json.load(open(jp))
        if tuple(man["frame_size"]) != tuple(fsize):
            problems.append(f"{n}: frame size {man['frame_size']} != {fsize}")
        if pivot is not None and tuple(man["pivot"]) != tuple(pivot):
            problems.append(f"{n}: pivot {man['pivot']} != {pivot}")
        if man.get("pixels_per_unit") != 24:
            problems.append(f"{n}: pixels_per_unit != 24")
        for an, (cnt, fps, loop) in anims.items():
            if an not in man["animations"]:
                problems.append(f"{n}: missing animation {an}")
                continue
            A = man["animations"][an]
            if len(A["frames"]) != cnt:
                problems.append(f"{n}.{an}: {len(A['frames'])} frames != {cnt}")
            if fps is not None and A["fps"] != fps:
                problems.append(f"{n}.{an}: fps {A['fps']} != {fps}")
            if loop is not None and A["loop"] != loop:
                problems.append(f"{n}.{an}: loop {A['loop']} != {loop}")
        a = _load(pp)
        bad = _palette_ok(a)
        if bad:
            problems.append(f"{n}: {len(bad)} off-palette colours e.g. {bad[:3]}")
        if binary and not set(np.unique(a[..., 3])) <= {0, 255}:
            problems.append(f"{n}: partial alpha in a prop sheet")
        fw, fh = fsize
        cols = man["columns"]
        for i in range(man["frame_count"]):
            fr = a[(i // cols) * fh:(i // cols + 1) * fh, (i % cols) * fw:(i % cols + 1) * fw]
            if not _border_ok(fr):
                problems.append(f"{n}: frame {i} touches the border")
            if not (fr[..., 3] > 0).any():
                problems.append(f"{n}: frame {i} is empty")

    for n, (fs, pv, anims) in PROP_SHEETS.items():
        chk_sheet(os.path.join(OUT_ENV, "props"), n, fs, anims, pv, binary=True)
    for n, (fs, anims, pv) in FX_SHEETS.items():
        chk_sheet(OUT_FX, n, fs, anims, pv, binary=False)
    for n, size in UI_ICONS.items():
        chk_png(os.path.join(OUT_UI, "icons", n + ".png"), size)
    for n, size in UI_PANELS.items():
        # 9-slice panels may use the full frame (no transparent border requirement)
        chk_png(os.path.join(OUT_UI, "panels", n + ".png"), size, border=False)
    return problems


# --------------------------------------------------------------------------


GROUPS = {
    "textures": lambda pv: textures.build(None, pv),
    "foliage": lambda pv: foliage.build(None, pv),
    "props": lambda pv: props.build(None, pv),
    "fx": lambda pv: fx.build(None),
    "ui": lambda pv: ui.build(None, pv),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("groups", nargs="*", help="subset of: " + ", ".join(GROUPS))
    ap.add_argument("--clean", action="store_true", help="delete our known output files before building")
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--check", action="store_true", help="only validate the files on disk")
    args = ap.parse_args()
    if not args.check:
        if args.clean:
            n = 0
            for p in expected_files():
                if os.path.exists(p):
                    os.remove(p)
                    n += 1
            print(f"removed {n} previously generated files")
        for g in (args.groups or list(GROUPS)):
            t0 = time.time()
            GROUPS[g](not args.no_preview)
            print(f"[{g}] built in {time.time() - t0:.1f}s")
    problems = check()
    files = expected_files()
    present = sum(os.path.exists(p) for p in files)
    print(f"{present}/{len(files)} expected files present")
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
