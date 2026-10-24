"""Validate generated sheets against the art <-> engine contract.

Checks per sheet: frame size, pivot and pixels-per-unit (read from the manifest;
a sheet may be drawn at a whole-number resolution factor k -- 48x48 @ 24 px/unit
or 96x96 @ 48 px/unit -- as long as world size and pivot placement stay the
same), exact animation names, frame counts, fps/loop where the spec fixes them,
binary alpha, the 1px transparent border in every frame, no empty frames,
master-palette colours, and (for sheets that opt in) that grounded animations
keep their feet on the pivot row in every frame.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SPR = os.path.join(ROOT, "assets", "sprites")
BASE_PPU = 24          # the 1x contract: 24 px per world unit
SCALES = (1, 2, 3, 4)  # allowed resolution factors

# (anim, frames, fps or None, loop or None)
S, N, E = "s", "n", "e"


def dirs(base, frames, fps, loop, ds=(S, N, E)):
    return [(f"{base}_{d}", frames, fps, loop) for d in ds]


# battle movement set shared by the 2x kith (drag-to-dash: coil -> burst -> skid, ram)
DASH_SET = (dirs("dash_windup", 2, 12, False) + dirs("dash", 3, 18, True) + dirs("dash_land", 3, 14, False)
            + dirs("ram", 2, 16, False))

# key -> (1x frame size, 1x pivot, animations[, options])
# options: {"grounded": [anim prefixes whose every frame must reach exactly the pivot row]}
SPEC = {
    "characters/explorer": ((32, 48), (16, 45),
                            dirs("idle", 2, 3, True) + dirs("walk", 4, 8, True) + dirs("sneak", 4, 6, True)
                            + dirs("interact", 2, 6, False) + [("sit_s", 2, 2, True), ("sit_e", 2, 2, True),
                                                                ("cheer_s", 2, 4, True), ("surprised_s", 1, None, None)]),
    "characters/hesper": ((32, 48), (16, 45),
                          dirs("idle", 2, 2, True) + dirs("walk", 4, 6, True) + [("talk_s", 2, 4, True), ("point_e", 1, None, None)]),
    "characters/corin": ((32, 48), (16, 45),
                         dirs("idle", 2, 3, None) + dirs("walk", 4, 9, None) + [("talk_s", 2, 4, None), ("cheer_s", 2, 5, None),
                                                                                  ("slump_s", 2, 2, None)]),
    "characters/villager_farmer": ((32, 48), (16, 45), dirs("idle", 2, 2, None) + dirs("walk", 4, 6, None) + [("talk_s", 2, 4, None)]),
    "characters/villager_baker": ((32, 48), (16, 45), dirs("idle", 2, 2, None) + dirs("walk", 4, 6, None) + [("talk_s", 2, 4, None)]),
    "characters/sigilbinder": ((32, 48), (16, 45), [("idle_s", 2, 2, None), ("idle_e", 2, 2, None), ("run_e", 4, 10, None)]),
    "characters/crowd": ((24, 32), (12, 30), [(f"idle_v{i}", 2, 2, True) for i in range(8)] + [(f"cheer_v{i}", 2, 6, True) for i in range(8)]),
    "characters/crowd_back": ((32, 32), (16, 30), [(f"idle_v{i}", 2, 2, None) for i in range(6)] + [(f"cheer_v{i}", 2, 6, None) for i in range(6)]),
    "kith/emberlyn": ((48, 48), (24, 44),
                      dirs("idle", 4, 6, True) + dirs("ready", 6, 8, True) + dirs("move", 4, 12, True) + DASH_SET
                      + dirs("cast", 3, 10, False) + dirs("melee", 3, 10, False) + dirs("focus", 4, 8, True)
                      + dirs("guard", 2, 6, True) + dirs("hurt", 1, None, None)
                      + [("stunned_s", 2, 6, True), ("ko_s", 3, 6, False), ("victory_s", 4, 8, True), ("cower_s", 2, 3, True),
                         ("curl_s", 2, 2, True), ("happy_s", 4, 10, True)],
                      {"grounded": ["idle_", "ready_", "dash_windup_", "dash_land_", "ram_", "guard_", "focus_",
                                    "stunned_", "cower_", "curl_"]}),
    "kith/stoneback": ((48, 48), (24, 44),
                       dirs("idle", 4, 4, True) + dirs("ready", 6, 6, True) + dirs("move", 4, 8, True) + DASH_SET
                       + [("roll_s", 4, 16, True)]
                       + dirs("cast", 3, None, False) + dirs("melee", 3, None, False) + dirs("focus", 4, 6, True) + dirs("guard", 2, 6, None)
                       + dirs("hurt", 1, None, None) + [("stunned_s", 2, 6, None), ("ko_s", 3, None, False), ("victory_s", 4, 6, None),
                                                        ("sleep_s", 2, 2, True)],
                       {"grounded": ["idle_", "ready_", "dash_windup_", "dash_land_", "guard_", "focus_", "sleep_",
                                     "roll_", "dash_"]}),
    "kith/mossling": ((32, 32), (16, 29), [("idle_s", 2, 3, None), ("idle_e", 2, 3, None)] + dirs("hop", 4, 10, True)
                      + [("alert_s", 2, 6, None), ("sleep_s", 2, 2, None)]),
    "kith/lanternmoth": ((48, 48), (24, 46), [("hover_s", 4, 8, True), ("hover_e", 4, 8, True)]),
    "props/training_totem": ((32, 48), (16, 45), [("idle_s", 1, None, None), ("hit_s", 3, 12, False)]),
    "portraits/portrait_hesper": ((64, 64), (32, 63), [("neutral_s", 1, None, None), ("smile_s", 1, None, None), ("stern_s", 1, None, None)]),
    "portraits/portrait_corin": ((64, 64), (32, 63), [("grin_s", 1, None, None), ("determined_s", 1, None, None), ("sulk_s", 1, None, None)]),
    "portraits/portrait_player": ((64, 64), (32, 63), [("neutral_s", 1, None, None), ("smile_s", 1, None, None), ("determined_s", 1, None, None)]),
    "portraits/portrait_emberlyn": ((64, 64), (32, 63), [("scared_s", 1, None, None), ("happy_s", 1, None, None)]),
}


def sheet_scale(key, man, base_size, base_pivot):
    """Resolution factor k of a sheet, or (None, errors) if its geometry breaks the contract."""
    errs = []
    ppu = man.get("pixels_per_unit")
    if not isinstance(ppu, (int, float)) or ppu <= 0 or ppu % BASE_PPU:
        return None, [f"{key}: pixels_per_unit {ppu} is not a multiple of {BASE_PPU}"]
    k = int(ppu // BASE_PPU)
    if k not in SCALES:
        return None, [f"{key}: resolution factor {k} (pixels_per_unit {ppu}) not in {SCALES}"]
    want_size = (base_size[0] * k, base_size[1] * k)
    want_pivot = (base_pivot[0] * k, base_pivot[1] * k)
    if tuple(man["frame_size"]) != want_size:
        errs.append(f"{key}: frame_size {man['frame_size']} != {list(want_size)} for {ppu} px/unit "
                    f"(world size must stay {base_size[0] / BASE_PPU:g}x{base_size[1] / BASE_PPU:g} units)")
    if tuple(man["pivot"]) != want_pivot:
        errs.append(f"{key}: pivot {man['pivot']} != {list(want_pivot)} for {ppu} px/unit")
    return k, errs


def check_sheet(key, spec):
    base_size, base_pivot, anims = spec[:3]
    opts = spec[3] if len(spec) > 3 else {}
    base = os.path.join(SPR, key)
    try:
        man = json.load(open(base + ".json"))
        img = np.array(Image.open(base + ".png").convert("RGBA"))
    except FileNotFoundError as e:
        return [f"{key}: missing {e.filename}"]
    k, errs = sheet_scale(key, man, base_size, base_pivot)
    if k is None:
        return errs
    fw, fh = (int(v) for v in man["frame_size"])
    pivot_row = int(man["pivot"][1])
    want = {a[0]: a for a in anims}
    got = man["animations"]
    if set(got) != set(want):
        errs.append(f"{key}: animations differ: missing {sorted(set(want) - set(got))} extra {sorted(set(got) - set(want))}")
    for name, (_, nf, fps, loop) in want.items():
        if name not in got:
            continue
        a = got[name]
        if len(a["frames"]) != nf:
            errs.append(f"{key}:{name}: {len(a['frames'])} frames != {nf}")
        if fps is not None and abs(a["fps"] - fps) > 1e-6:
            errs.append(f"{key}:{name}: fps {a['fps']} != {fps}")
        if loop is not None and a["loop"] != loop:
            errs.append(f"{key}:{name}: loop {a['loop']} != {loop}")
        if any(not (0 <= f < man["frame_count"]) for f in a["frames"]):
            errs.append(f"{key}:{name}: frame index out of range")
    alpha = img[:, :, 3]
    bad_alpha = np.unique(alpha[(alpha != 0) & (alpha != 255)])
    if len(bad_alpha):
        errs.append(f"{key}: non-binary alpha values {bad_alpha[:5]}")
    cols = man["columns"]
    if img.shape[1] < cols * fw or img.shape[0] < -(-man["frame_count"] // cols) * fh:
        errs.append(f"{key}: image {img.shape[1]}x{img.shape[0]} too small for {man['frame_count']} frames of {fw}x{fh}")
        return errs
    lows = {}
    for i in range(man["frame_count"]):
        x0, y0 = (i % cols) * fw, (i // cols) * fh
        fr = alpha[y0:y0 + fh, x0:x0 + fw]
        if fr[0].any() or fr[-1].any() or fr[:, 0].any() or fr[:, -1].any():
            errs.append(f"{key}: frame {i} touches the border")
        if not fr.any():
            errs.append(f"{key}: frame {i} is empty")
            continue
        lows[i] = int(np.nonzero(fr.any(axis=1))[0].max())
    for prefix in opts.get("grounded", []):
        for name, a in got.items():
            if not name.startswith(prefix):
                continue
            off = [(j, lows.get(f)) for j, f in enumerate(a["frames"]) if lows.get(f) != pivot_row]
            if off:
                errs.append(f"{key}:{name}: frames {[j for j, _ in off]} do not stand on the pivot row {pivot_row} "
                            f"(lowest rows {[lo for _, lo in off]})")
    return errs


def palette_errors():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from common.palette import all_colors
    pal = {tuple(c[:3]) for c in all_colors()}
    errs = []
    for key in SPEC:
        img = np.array(Image.open(os.path.join(SPR, key + ".png")).convert("RGBA"))
        px = img[img[:, :, 3] > 0][:, :3]
        uniq = {tuple(int(v) for v in c) for c in np.unique(px, axis=0)}
        bad = sorted(uniq - pal)
        if bad:
            errs.append(f"{key}: {len(bad)} colours outside the master palette, e.g. {bad[:4]}")
    return errs


def main() -> int:
    all_errs = []
    for key, spec in SPEC.items():
        all_errs += check_sheet(key, spec)
    all_errs += palette_errors()
    if all_errs:
        print("CONTRACT ERRORS:")
        for e in all_errs:
            print("  " + e)
        return 1
    print(f"contract OK: {len(SPEC)} sheets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
