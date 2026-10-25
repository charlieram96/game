"""Validate generated sheets against the art <-> engine contract.

Checks per sheet: frame size, pivot and pixels-per-unit (read from the manifest;
a sheet may be drawn at a whole-number resolution factor k -- 48x48 @ 24 px/unit
or 96x96 @ 48 px/unit -- as long as world size and pivot placement stay the
same), exact animation names, frame counts, fps/loop where the spec fixes them,
binary alpha, the 1px transparent border in every frame, no empty frames,
master-palette colours, and (for sheets that opt in) that grounded animations
keep their feet on the pivot row in every frame.

HD sheets (tools/art_forge/animate.py, 112 px per world unit) state their exact
geometry instead (`"geometry": (frame size, pivot, px/unit)`), must ship a
normal map in the sheet's layout (rgb = unit normal, alpha = emission mask in
128..255), and may set a `"footprint"`: the size on screen, in board cells, of
the frames of some animations (a cell is one world unit wide, and the camera's
sprite stretch shows upright sprites at their drawn proportions), so a
creature stays inside its cell.
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
HD_PPU = 112           # HD sheets (tools/art_forge/animate.py): texels near 1:1 with device pixels on phones

# (anim, frames, fps or None, loop or None)
S, N, E = "s", "n", "e"


def dirs(base, frames, fps, loop, ds=(S, N, E)):
    return [(f"{base}_{d}", frames, fps, loop) for d in ds]


# HD people stand on the pivot row in every frame of these (cheers hop)
GROUNDED_PEOPLE = ["idle_", "walk_", "sneak_", "interact_", "sit_", "talk_", "slump_", "point_", "surprised_"]

# battle movement set shared by the 2x kith (drag-to-dash: coil -> burst -> skid, ram)
DASH_SET = (dirs("dash_windup", 2, 12, False) + dirs("dash", 3, 18, True) + dirs("dash_land", 3, 14, False)
            + dirs("ram", 2, 16, False))

# key -> (1x frame size, 1x pivot, animations[, options])
# options: {"grounded": [anim prefixes whose every frame must reach exactly the pivot row],
#           "geometry": ((w, h), (px, py), px_per_unit)   exact HD geometry (the 1x size/pivot are then unused),
#           "footprint": {"anims": [prefixes], "max_w": cells, "h": (min, max) cells}}
SPEC = {
    "characters/explorer": ((32, 48), (16, 45),
                            dirs("idle", 2, 3, True) + dirs("walk", 4, 8, True) + dirs("sneak", 4, 6, True)
                            + dirs("interact", 2, 6, False) + [("sit_s", 2, 2, True), ("sit_e", 2, 2, True),
                                                                ("cheer_s", 2, 4, True), ("surprised_s", 1, None, None)],
                            {"geometry": ((128, 240), (64, 232), HD_PPU), "grounded": GROUNDED_PEOPLE,
                             "footprint": {"anims": ["idle_"], "max_w": 1.0, "h": (1.5, 1.95)}}),
    "characters/hesper": ((32, 48), (16, 45),
                          dirs("idle", 2, 2, True) + dirs("walk", 4, 6, True) + [("talk_s", 2, 4, True), ("point_e", 1, None, None)],
                          {"geometry": ((128, 240), (64, 232), HD_PPU), "grounded": GROUNDED_PEOPLE,
                             "footprint": {"anims": ["idle_"], "max_w": 1.0, "h": (1.5, 1.95)}}),
    "characters/corin": ((32, 48), (16, 45),
                         dirs("idle", 2, 3, None) + dirs("walk", 4, 9, None) + [("talk_s", 2, 4, None), ("cheer_s", 2, 5, None),
                                                                                  ("slump_s", 2, 2, None)],
                         {"geometry": ((128, 240), (64, 232), HD_PPU), "grounded": GROUNDED_PEOPLE,
                             "footprint": {"anims": ["idle_"], "max_w": 1.0, "h": (1.5, 1.95)}}),
    "characters/villager_farmer": ((32, 48), (16, 45), dirs("idle", 2, 2, None) + dirs("walk", 4, 6, None) + [("talk_s", 2, 4, None)],
                                   {"geometry": ((128, 240), (64, 232), HD_PPU), "grounded": GROUNDED_PEOPLE,
                             "footprint": {"anims": ["idle_"], "max_w": 1.0, "h": (1.5, 1.95)}}),
    "characters/villager_baker": ((32, 48), (16, 45), dirs("idle", 2, 2, None) + dirs("walk", 4, 6, None) + [("talk_s", 2, 4, None)],
                                  {"geometry": ((128, 240), (64, 232), HD_PPU), "grounded": GROUNDED_PEOPLE,
                             "footprint": {"anims": ["idle_"], "max_w": 1.0, "h": (1.5, 1.95)}}),
    "characters/sigilbinder": ((32, 48), (16, 45), [("idle_s", 2, 2, None), ("idle_e", 2, 2, None), ("run_e", 4, 10, None)],
                               {"geometry": ((160, 240), (80, 232), HD_PPU), "grounded": ["idle_"],
                                "footprint": {"anims": ["idle_"], "max_w": 1.0, "h": (1.5, 1.95)}}),
    "characters/crowd": ((24, 32), (12, 30), [(f"idle_v{i}", 2, 2, True) for i in range(8)] + [(f"cheer_v{i}", 2, 6, True) for i in range(8)]),
    "characters/crowd_back": ((32, 32), (16, 30), [(f"idle_v{i}", 2, 2, None) for i in range(6)] + [(f"cheer_v{i}", 2, 6, None) for i in range(6)]),
    "kith/emberlyn": ((48, 48), (24, 44),
                      dirs("idle", 4, 6, True) + dirs("ready", 6, 8, True) + dirs("move", 4, 12, True) + DASH_SET
                      + dirs("cast", 3, 10, False) + dirs("melee", 3, 10, False) + dirs("focus", 4, 8, True)
                      + dirs("guard", 2, 6, True) + dirs("hurt", 1, None, None)
                      + [("stunned_s", 2, 6, True), ("ko_s", 3, 6, False), ("victory_s", 4, 8, True), ("cower_s", 2, 3, True),
                         ("curl_s", 2, 2, True), ("happy_s", 4, 10, True)],
                      {"grounded": ["idle_", "ready_", "dash_windup_", "dash_land_", "ram_", "guard_", "focus_",
                                    "stunned_", "cower_", "curl_"],
                       "geometry": ((144, 152), (72, 144), HD_PPU),
                       "footprint": {"anims": ["idle_", "ready_", "guard_"], "max_w": 0.92, "h": (0.8, 1.25)}}),
    "kith/stoneback": ((48, 48), (24, 44),
                       dirs("idle", 4, 4, True) + dirs("ready", 6, 6, True) + dirs("move", 4, 8, True)
                       + [a for a in DASH_SET if not a[0].startswith("dash_") or a[0].startswith("dash_windup_") or a[0].startswith("dash_land_")]
                       + dirs("dash", 4, 24, True) + [("roll_s", 4, 16, True)]
                       + dirs("cast", 3, None, False) + dirs("melee", 3, None, False) + dirs("focus", 4, 6, True) + dirs("guard", 2, 6, None)
                       + dirs("hurt", 1, None, None) + [("stunned_s", 2, 6, None), ("ko_s", 3, None, False), ("victory_s", 4, 6, None),
                                                        ("sleep_s", 2, 2, True)],
                       {"grounded": ["idle_", "ready_", "dash_windup_", "dash_land_", "guard_", "focus_", "sleep_",
                                     "roll_", "dash_"],
                        "geometry": ((136, 128), (68, 120), HD_PPU),
                        "footprint": {"anims": ["idle_", "ready_"], "max_w": 0.92, "h": (0.55, 1.25)}}),
    "kith/mossling": ((32, 32), (16, 29), [("idle_s", 2, 3, None), ("idle_e", 2, 3, None)] + dirs("hop", 4, 10, True)
                      + [("alert_s", 2, 6, None), ("sleep_s", 2, 2, None)],
                      {"geometry": ((104, 104), (52, 98), HD_PPU), "grounded": ["idle_", "alert_", "sleep_"],
                       "footprint": {"anims": ["idle_"], "max_w": 0.8, "h": (0.45, 0.75)}}),
    "kith/lanternmoth": ((48, 48), (24, 46), [("hover_s", 4, 8, True), ("hover_e", 4, 8, True)],
                         {"geometry": ((128, 144), (64, 138), HD_PPU),
                          "footprint": {"anims": ["hover_"], "max_w": 1.0, "h": (0.55, 1.0)}}),
    "props/training_totem": ((32, 48), (16, 45), [("idle_s", 1, None, None), ("hit_s", 3, 12, False)],
                             {"geometry": ((112, 160), (56, 152), HD_PPU), "grounded": ["idle_", "hit_"],
                              "footprint": {"anims": ["idle_"], "max_w": 0.92, "h": (1.0, 1.4)}}),
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


def hd_geometry(key, man, geometry):
    (w, h), (px, py), ppu = geometry
    errs = []
    if man.get("pixels_per_unit") != ppu:
        errs.append(f"{key}: pixels_per_unit {man.get('pixels_per_unit')} != {ppu}")
    if tuple(man["frame_size"]) != (w, h):
        errs.append(f"{key}: frame_size {man['frame_size']} != {[w, h]}")
    if tuple(man["pivot"]) != (px, py):
        errs.append(f"{key}: pivot {man['pivot']} != {[px, py]}")
    return errs


def normal_map_errors(key, man, base, img):
    name = man.get("normal_map")
    if not name:
        return [f"{key}: HD sheets need a normal map (manifest 'normal_map')"]
    path = os.path.join(os.path.dirname(base), name)
    if not os.path.exists(path):
        return [f"{key}: missing normal map {name}"]
    nm = np.array(Image.open(path).convert("RGBA"))
    if nm.shape != img.shape:
        return [f"{key}: normal map {nm.shape[1]}x{nm.shape[0]} != sheet {img.shape[1]}x{img.shape[0]}"]
    errs = []
    if nm[..., 3].min() < 128:
        errs.append(f"{key}: normal map alpha (emission mask) below 128")
    opaque = img[..., 3] > 0
    n = nm[..., :3][opaque].astype(np.float32) / 255.0 * 2.0 - 1.0
    length = np.linalg.norm(n, axis=-1)
    if len(length) and (np.abs(length - 1.0) > 0.08).mean() > 0.01:
        errs.append(f"{key}: normal map vectors are not unit length")
    if len(n) and (n[:, 2] < -0.05).any():
        errs.append(f"{key}: normal map has normals facing away from the camera")
    return errs


def footprint_errors(key, man, img, fp):
    """Content size in board cells (world units) of every frame of the listed animations."""
    fw, fh = (int(v) for v in man["frame_size"])
    cols, ppu = man["columns"], float(man["pixels_per_unit"])
    errs = []
    for name, a in man["animations"].items():
        if not any(name.startswith(p) for p in fp["anims"]):
            continue
        for j, f in enumerate(a["frames"]):
            x0, y0 = (f % cols) * fw, (f // cols) * fh
            alpha = img[y0:y0 + fh, x0:x0 + fw, 3] > 0
            xs = np.nonzero(alpha.any(0))[0]
            ys = np.nonzero(alpha.any(1))[0]
            w = (xs.max() - xs.min() + 1) / ppu
            h = (ys.max() - ys.min() + 1) / ppu
            if w > fp["max_w"] + 1e-6:
                errs.append(f"{key}:{name}[{j}]: {w:.2f} cells wide > {fp['max_w']}")
            if not (fp["h"][0] - 1e-6 <= h <= fp["h"][1] + 1e-6):
                errs.append(f"{key}:{name}[{j}]: {h:.2f} cells tall, outside {fp['h']}")
    return errs


def check_sheet(key, spec):
    base_size, base_pivot, anims = spec[:3]
    opts = spec[3] if len(spec) > 3 else {}
    base = os.path.join(SPR, key)
    try:
        man = json.load(open(base + ".json"))
        img = np.array(Image.open(base + ".png").convert("RGBA"))
    except FileNotFoundError as e:
        return [f"{key}: missing {e.filename}"]
    if "geometry" in opts:
        errs = hd_geometry(key, man, opts["geometry"])
        errs += normal_map_errors(key, man, base, img)
    else:
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
    if "footprint" in opts:
        errs += footprint_errors(key, man, img, opts["footprint"])
    return errs


def palette_errors():
    """Every sheet uses the master palette; an HD sheet may also use its own fitted palette (palette_hd.py)."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from common.palette import all_colors
    from common import palette_hd
    master = {tuple(c[:3]) for c in all_colors()}
    errs = []
    for key in SPEC:
        img = np.array(Image.open(os.path.join(SPR, key + ".png")).convert("RGBA"))
        px = img[img[:, :, 3] > 0][:, :3]
        uniq = {tuple(int(v) for v in c) for c in np.unique(px, axis=0)}
        pal = master | {tuple(c[:3]) for c in palette_hd.sheet_colors(os.path.basename(key))}
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
