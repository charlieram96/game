#!/usr/bin/env python3
"""Key poses for HD sprite sheets: palette fitting and installing pixelized poses.

An HD sheet (see animate.py) is built from *key poses*: one painting per pose
and view from `forge.py gen <brief> --pose <pose> --view <s|n|e> --ref ...`,
pixelized at the painting's own grid and kept as a small PNG in
tools/art_forge/keys/<sheet>/<pose>_<view>.png. Everything else (frame
registration, in-betweens, effects, normal maps) is deterministic and lives
in animate.py, so a key can be swapped or hand-fixed and the sheet rebuilt.

    python3 tools/art_forge/keys.py palette emberlyn <painting> ... [--k 44]
        fit the sheet's shared palette to its key paintings (k-means in OKLab)
        and write it into tools/common/palette_hd.py as ramps hd_<sheet>_*
    python3 tools/art_forge/keys.py install emberlyn ready_e <painting> [--cell 7] [--scale 1]
        pixelize a painting with that palette into keys/emberlyn/ready_e.png
        and record it in provenance/keys_emberlyn.json
    python3 tools/art_forge/keys.py list emberlyn
    python3 tools/art_forge/keys.py scale emberlyn walk_a_s walk_b_s --ref stand_s --head 8,20,62,64 [--apply]
        find how much bigger each key is drawn than the reference (its head, matched
        by normalized cross-correlation at 0.8-1.25x) and re-install it to match
    python3 tools/art_forge/keys.py grade emberlyn --chroma 0.84 --light -0.025 --hue -3
        shift the palette (all but its vivid flame colours) and remap every key, e.g. to match the portrait

`--cell` is the size in painting pixels of one sprite pixel. gpt-image-2
paints a near-even 6.5-7.5 px grid, so the default keeps the painting's own
pixels; a larger cell shrinks the subject. The model doesn't always keep the
scale it was asked for (a stride drawn 10% bigger than the stance), so
`scale` measures each key against its view's reference and re-installs it.
The provenance keeps the fitted palette (before any grade), so a re-installed
key is pixelized and graded exactly like the rest.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import pixelize as PX  # noqa: E402

KEYS = HERE / "keys"
PROVENANCE = HERE / "provenance"
PALETTE_PY = HERE.parent / "common" / "palette_hd.py"   # the sheets' fitted palettes (never the master)
BEGIN = "    # >>> art_forge HD sheet palettes (tools/art_forge/keys.py palette; do not edit by hand)\n"
END = "    # <<< art_forge HD sheet palettes\n"


# --- colour science ----------------------------------------------------------------------

def _to_linear(c: np.ndarray) -> np.ndarray:
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055) * 255.0


def oklab(rgb: np.ndarray) -> np.ndarray:
    """sRGB uint8 (N, 3) -> OKLab (N, 3)."""
    lin = _to_linear(rgb.astype(np.float64))
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                   [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    lms = np.cbrt(lin @ m1.T)
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                   [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return lms @ m2.T


def oklab_to_rgb(lab: np.ndarray) -> np.ndarray:
    m2i = np.array([[1.0, 0.3963377774, 0.2158037573],
                    [1.0, -0.1055613458, -0.0638541728],
                    [1.0, -0.0894841775, -1.2914855480]])
    lms = (lab @ m2i.T) ** 3
    m1i = np.array([[4.0767416621, -3.3077115913, 0.2309699292],
                    [-1.2684380046, 2.6097574011, -0.3413193965],
                    [-0.0041960863, -0.7034186147, 1.7076147010]])
    return np.round(_to_srgb(lms @ m1i.T)).astype(np.int64)


def kmeans(points: np.ndarray, k: int, iters: int = 30, seed: int = 7) -> np.ndarray:
    """k-means++ seeded k-means (points (N, 3)); returns the centres sorted by lightness."""
    rng = np.random.default_rng(seed)
    centres = [points[rng.integers(len(points))]]
    d2 = ((points - centres[0]) ** 2).sum(-1)
    for _ in range(1, k):
        c = points[rng.choice(len(points), p=d2 / d2.sum())]
        centres.append(c)
        d2 = np.minimum(d2, ((points - c) ** 2).sum(-1))
    centres = np.array(centres)
    for _ in range(iters):
        idx = np.empty(len(points), dtype=np.int64)
        for s in range(0, len(points), 65536):
            chunk = points[s:s + 65536]
            idx[s:s + 65536] = ((chunk[:, None, :] - centres[None]) ** 2).sum(-1).argmin(1)
        moved = 0.0
        for j in range(k):
            sel = points[idx == j]
            if len(sel):
                new = sel.mean(0)
                moved = max(moved, float(np.abs(new - centres[j]).max()))
                centres[j] = new
        if moved < 1e-4:
            break
    return centres[np.argsort(centres[:, 0])]


def painting_samples(path: Path, step: int = 3, erode: int = 3) -> np.ndarray:
    """Interior subject pixels of a painting (away from the keyed background), sRGB (N, 3)."""
    img = PX.load_rgba(path)
    mask, bg = PX._foreground(img, 48.0, holes=True)
    core = mask.copy()
    for _ in range(erode):
        core = core & PX._shift(core, 1, 0) & PX._shift(core, -1, 0) & PX._shift(core, 0, 1) & PX._shift(core, 0, -1)
    rgb = img[..., :3][::step, ::step][core[::step, ::step]]
    if bg is not None:
        # backdrop spill (magenta-tinted glow and fringes) never becomes a palette colour
        lab = oklab(rgb)
        blab = oklab(np.asarray(bg, dtype=np.float64)[None])[0]
        hue = np.arctan2(lab[:, 2], lab[:, 1])
        bhue = np.arctan2(blab[2], blab[1])
        near_hue = np.abs((hue - bhue + np.pi) % (2 * np.pi) - np.pi) < np.radians(40)
        # (plum or violet cloth is far less chromatic than the keyed backdrop and stays)
        rgb = rgb[~(near_hue & (np.hypot(lab[:, 1], lab[:, 2]) > 0.17))]
    return rgb


def group_ramps(rgb: np.ndarray) -> list[list[tuple[int, int, int]]]:
    """Palette colours grouped into ramps by hue family (dark -> light)."""
    lab = oklab(rgb)
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    hue = (np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) + 360.0) % 360.0
    groups: dict[str, list[int]] = {}
    for i in range(len(rgb)):
        if chroma[i] < 0.03:
            key = "neutral"
        else:
            key = f"h{int(((hue[i] + 15.0) % 360.0) // 30.0)}"   # 30-degree hue sectors
        groups.setdefault(key, []).append(i)
    ramps = []
    for key in sorted(groups):
        ids = sorted(groups[key], key=lambda i: lab[i, 0])
        ramps.append([tuple(int(v) for v in rgb[i]) for i in ids])
    return ramps


def write_palette(sheet: str, ramps: list[list[tuple[int, int, int]]]) -> list[str]:
    """Replaces the sheet's hd_<sheet>_* ramps in tools/common/palette_hd.py; returns the ramp names."""
    text = PALETTE_PY.read_text()
    if BEGIN not in text:
        raise SystemExit("palette_hd.py: the HD sheet palette markers are missing")
    start = text.index(BEGIN) + len(BEGIN)
    stop = text.index(END)
    block = text[start:stop]
    block = re.sub(rf'    "hd_{sheet}_[a-z0-9]+": \[[^\]]*\],\n', "", block)
    names = []
    for i, ramp in enumerate(ramps):
        name = f"hd_{sheet}_{i}"
        names.append(name)
        hexes = ", ".join(f'"#{r:02x}{g:02x}{b:02x}"' for r, g, b in ramp)
        block += f'    "{name}": [{hexes}],\n'
    PALETTE_PY.write_text(text[:start] + block + text[stop:])
    return names


def hd_palettes():
    """tools/common/palette_hd.py, re-read (a palette may have just been written)."""
    import importlib
    import common.palette_hd as H
    return importlib.reload(H)


def sheet_ramps(sheet: str) -> list[str]:
    names = hd_palettes().sheet_ramps(sheet)
    if not names:
        raise SystemExit(f"no palette for '{sheet}' yet: run `keys.py palette {sheet} <paintings>` first")
    return names


# --- keys ---------------------------------------------------------------------------------

def pixelize_key(painting: Path, ramps: list[str], cell: float = 7.0, scale: float = 1.0, tolerance: float = 48.0) -> Image.Image:
    img = PX.load_rgba(painting)
    mask, _ = PX._foreground(img, tolerance, holes=True)
    ys = np.nonzero(mask.any(1))[0]
    height = max(8, int(round((ys.max() - ys.min() + 1) / cell * scale)))
    sprite = PX.pixelize(img, height=height, ramps=ramps, tolerance=tolerance, holes=True)
    content = sprite.crop(sprite.getbbox())
    out = Image.new("RGBA", (content.width + 2, content.height + 2), (0, 0, 0, 0))
    out.paste(content, (1, 1))
    return out


def record_key(sheet: str, key: str, painting: Path, params: dict) -> None:
    data = provenance(sheet)
    sidecar = painting.with_suffix(".json")
    gen = json.loads(sidecar.read_text()) if sidecar.exists() else None
    if gen:
        # references are recorded by name and hash only
        gen["references"] = [{"file": Path(r["file"]).name, "sha256": r["sha256"]} for r in gen.get("references", [])]
    try:
        source_path = str(painting.resolve().relative_to(HERE / "_out"))
    except ValueError:
        source_path = painting.name
    data["keys"][key] = {"source_image": painting.name, "source_path": source_path, "generation": gen, "pixelize": params,
                         "installed": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cleanup": data["keys"].get(key, {}).get("cleanup", [])}
    save_provenance(sheet, data)


def install_key(sheet: str, key: str, painting: Path, cell: float, scale: float = 1.0, tolerance: float = 48.0, extra: dict | None = None) -> Image.Image:
    """Pixelize `painting` with the sheet's fitted palette, apply the sheet's grades, save it as keys/<sheet>/<key>.png."""
    H = hd_palettes()
    data = provenance(sheet)
    if "palette" in data:   # the fitted (pre-grade) palette, so grades apply exactly as they did to every other key
        ramps = []
        for i, ramp in enumerate(data["palette"]["ramps"]):
            name = f"_fit_{sheet}_{i}"
            H.RAMPS[name] = [H.hex_to_rgba(h) for h in ramp]   # this process only
            ramps.append(name)
    else:
        ramps = sheet_ramps(sheet)
    sprite = remap_to_palette(pixelize_key(painting, ramps, cell, scale, tolerance), sheet)
    out = KEYS / sheet / f"{key}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sprite.save(out)
    record_key(sheet, key, painting, {"cell": cell, "scale": scale, "tolerance": tolerance, **(extra or {})})
    return sprite


def fit_palette(paintings: list[Path], k: int) -> list[list[tuple[int, int, int]]]:
    """About `k` colours fitted to the paintings (k-means in OKLab), grouped into ramps."""
    samples = np.concatenate([painting_samples(Path(p)) for p in paintings])
    rng = np.random.default_rng(3)
    if len(samples) > 400_000:
        samples = samples[rng.choice(len(samples), 400_000, replace=False)]
    centres = kmeans(oklab(samples), k)
    # outlines are never pure black: the darkest colours are lifted to the master ink's darkest shade
    ink = oklab(np.array([[0x12, 0x0E, 0x17]]))[0]
    dark = centres[:, 0] < ink[0]
    centres[dark] = ink
    rgb = np.unique(np.clip(oklab_to_rgb(centres), 0, 255), axis=0)
    return group_ramps(rgb)


def _hex(ramps) -> list[list[str]]:
    return [[f"#{r:02x}{g:02x}{b:02x}" for r, g, b in ramp] for ramp in ramps]


def provenance(sheet: str) -> dict:
    path = PROVENANCE / f"keys_{sheet}.json"
    return json.loads(path.read_text()) if path.exists() else {"asset": f"tools/art_forge/keys/{sheet}/", "keys": {}}


def save_provenance(sheet: str, data: dict) -> None:
    PROVENANCE.mkdir(exist_ok=True)
    data["keys"] = {k: data["keys"][k] for k in sorted(data["keys"])}
    (PROVENANCE / f"keys_{sheet}.json").write_text(json.dumps(data, indent=1))


def cmd_palette(args: argparse.Namespace) -> None:
    ramps = fit_palette([Path(p) for p in args.paintings], args.k)
    names = write_palette(args.sheet, ramps)
    data = provenance(args.sheet)
    data["palette"] = {"sources": [Path(p).name for p in args.paintings], "k": args.k, "ramps": _hex(ramps)}
    data.pop("grades", None)   # a new palette starts ungraded
    save_provenance(args.sheet, data)
    print(f"{sum(len(r) for r in ramps)} colours in {len(names)} ramps -> tools/common/palette_hd.py: {', '.join(names)}")


# --- scale matching -------------------------------------------------------------------------

def _gray(img: np.ndarray) -> np.ndarray:
    rgb = img[..., :3].astype(np.float64) / 255.0
    return np.where(img[..., 3] > 0, rgb @ np.array([0.299, 0.587, 0.114]), 0.0)


def _resize(a: np.ndarray, s: float) -> np.ndarray:
    h, w = a.shape
    return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((max(2, round(w * s)), max(2, round(h * s))), Image.BILINEAR))


def ncc_best(image: np.ndarray, templ: np.ndarray) -> float:
    """Highest normalized cross-correlation of `templ` anywhere inside `image` (both 2D float)."""
    H, W = image.shape
    h, w = templ.shape
    if h > H or w > W:
        return -1.0
    t = templ - templ.mean()
    tn = np.sqrt((t * t).sum()) + 1e-9
    shape = (H + h, W + w)
    corr = np.fft.irfft2(np.fft.rfft2(image, s=shape) * np.fft.rfft2(t[::-1, ::-1], s=shape), s=shape)[h - 1:H, w - 1:W]
    c1 = np.pad(image, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    c2 = np.pad(image * image, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    s1 = c1[h:, w:] - c1[:-h, w:] - c1[h:, :-w] + c1[:-h, :-w]
    s2 = c2[h:, w:] - c2[:-h, w:] - c2[h:, :-w] + c2[:-h, :-w]
    var = np.maximum(s2 - s1 * s1 / (h * w), 1e-9)
    return float((corr / (np.sqrt(var) * tn)).max())


def match_scale(key: np.ndarray, ref: np.ndarray, box: tuple[int, int, int, int], lo: float = 0.8, hi: float = 1.25) -> tuple[float, float]:
    """How much bigger `key` is drawn than `ref`: the scale of ref's `box` (its head) that best matches inside key."""
    templ = _gray(ref)[box[1]:box[3], box[0]:box[2]]
    image = np.pad(_gray(key), 8)
    best = (-2.0, 1.0)
    for s in np.arange(lo, hi + 1e-6, 0.01):
        score = ncc_best(image, _resize(templ, s))
        if score > best[0]:
            best = (score, float(s))
    return round(best[1], 2), round(best[0], 3)


def cmd_scale(args: argparse.Namespace) -> None:
    """Re-install keys drawn at another scale than their view's reference (matched on the reference's head)."""
    ref = np.array(Image.open(KEYS / args.sheet / f"{args.ref}.png").convert("RGBA"))
    box = tuple(int(v) for v in args.head.split(","))
    prov = provenance(args.sheet)
    for key in args.keys:
        img = np.array(Image.open(KEYS / args.sheet / f"{key}.png").convert("RGBA"))
        s, score = match_scale(img, ref, box, args.lo, args.hi)
        rec = prov["keys"][key]
        line = f"{key:16s} drawn x{s:.2f} (match {score:.2f})"
        at_bound = s <= args.lo + 0.025 or s >= args.hi - 0.025   # a best match at (or next to) the search limit is no match
        if at_bound:
            line += " (at the search limit: ignored)"
        if args.apply and abs(s - 1.0) >= args.min and score >= args.min_score and not at_bound:
            src = HERE / "_out" / rec["source_path"]
            cell = round(rec["pixelize"]["cell"] * s, 3)
            sprite = install_key(args.sheet, key, src, cell, rec["pixelize"].get("scale", 1.0), rec["pixelize"].get("tolerance", 48.0),
                                 {"matched_scale": s, "matched_to": args.ref})
            line += f" -> re-installed at cell {cell} ({sprite.width}x{sprite.height})"
        print(line, flush=True)


def remap_to_palette(sprite: Image.Image, sheet: str) -> Image.Image:
    """Apply the sheet's recorded grades to a freshly pixelized key (keys are graded after install)."""
    prov = PROVENANCE / f"keys_{sheet}.json"
    grades = json.loads(prov.read_text()).get("grades", []) if prov.exists() else []
    if not grades:
        return sprite
    img = np.array(sprite.convert("RGBA"))
    for g in grades:
        cache: dict = {}
        flat = img[..., :3].reshape(-1, 3)
        for i, c in enumerate(map(tuple, flat)):
            if c not in cache:
                cache[c] = grade_colour(c, g["light"], g["chroma"], g["hue"], g["keep_vivid"], g.get("max_light", 1.0))
            flat[i] = cache[c]
        img[..., :3] = flat.reshape(img.shape[:2] + (3,))
    return Image.fromarray(img, "RGBA")


def grade_colour(rgb: tuple[int, int, int], d_light: float, k_chroma: float, d_hue: float, keep_vivid: float,
                 max_light: float = 1.0) -> tuple[int, int, int]:
    lab = oklab(np.array([rgb]))[0]
    chroma = float(np.hypot(lab[1], lab[2]))
    if chroma >= keep_vivid or lab[0] > max_light:
        return rgb
    hue = np.arctan2(lab[2], lab[1]) + np.radians(d_hue)
    chroma *= k_chroma
    new = np.array([[lab[0] + d_light, chroma * np.cos(hue), chroma * np.sin(hue)]])
    return tuple(int(v) for v in np.clip(oklab_to_rgb(new)[0], 0, 255))


def cmd_grade(args: argparse.Namespace) -> None:
    """Shift a sheet's palette (all but its vivid colours) and remap every installed key the same way."""
    H = hd_palettes()
    names = sheet_ramps(args.sheet)
    mapping = {}
    ramps = []
    for n in names:
        ramp = []
        for c in H.RAMPS[n]:
            old = tuple(int(v) for v in c[:3])
            new = grade_colour(old, args.light, args.chroma, args.hue, args.keep_vivid, args.max_light)
            mapping[old] = new
            ramp.append(new)
        ramps.append(ramp)
    write_palette(args.sheet, ramps)
    for p in sorted((KEYS / args.sheet).glob("*.png")):
        img = np.array(Image.open(p).convert("RGBA"))
        rgb = img[..., :3].reshape(-1, 3)
        out = rgb.copy()
        for old, new in mapping.items():
            hit = (rgb == old).all(1)
            out[hit] = new
        img[..., :3] = out.reshape(img.shape[:2] + (3,))
        Image.fromarray(img, "RGBA").save(p)
    data = provenance(args.sheet)
    data.setdefault("grades", []).append({"light": args.light, "chroma": args.chroma, "hue": args.hue, "keep_vivid": args.keep_vivid,
                                          "max_light": args.max_light,
                                          "reason": args.reason, "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    save_provenance(args.sheet, data)
    changed = sum(1 for o, n in mapping.items() if o != n)
    print(f"{args.sheet}: {changed} of {len(mapping)} palette colours graded; keys remapped")


def cmd_install(args: argparse.Namespace) -> None:
    sprite = install_key(args.sheet, args.key, Path(args.painting), args.cell, args.scale, args.tolerance)
    print(f"{(KEYS / args.sheet / (args.key + '.png')).relative_to(ROOT)} ({sprite.width}x{sprite.height})")


def cmd_list(args: argparse.Namespace) -> None:
    for p in sorted((KEYS / args.sheet).glob("*.png")):
        im = Image.open(p)
        print(f"{p.stem:22s} {im.width}x{im.height}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("palette")
    p.add_argument("sheet")
    p.add_argument("paintings", nargs="+")
    p.add_argument("--k", type=int, default=44)
    p.set_defaults(func=cmd_palette)
    p = sub.add_parser("install")
    p.add_argument("sheet")
    p.add_argument("key")
    p.add_argument("painting")
    p.add_argument("--cell", type=float, default=7.0)
    p.add_argument("--scale", type=float, default=1.0)
    p.add_argument("--tolerance", type=float, default=48.0)
    p.set_defaults(func=cmd_install)
    p = sub.add_parser("list")
    p.add_argument("sheet")
    p.set_defaults(func=cmd_list)
    p = sub.add_parser("scale", help="match keys' scale to a reference key (its head) and optionally re-install them")
    p.add_argument("sheet")
    p.add_argument("keys", nargs="+")
    p.add_argument("--ref", required=True, help="the reference key, e.g. stand_s")
    p.add_argument("--head", required=True, help="x0,y0,x1,y1: the head in the reference key's pixels")
    p.add_argument("--apply", action="store_true", help="re-install keys drawn at another scale")
    p.add_argument("--min", type=float, default=0.03, help="ignore scale errors smaller than this")
    p.add_argument("--min-score", type=float, default=0.55, help="ignore weak matches (a turned or hidden head)")
    p.add_argument("--lo", type=float, default=0.8, help="smallest scale searched")
    p.add_argument("--hi", type=float, default=1.25, help="largest scale searched")
    p.set_defaults(func=cmd_scale)
    p = sub.add_parser("grade", help="shift the sheet's palette (OKLab) and remap its keys, e.g. to match a portrait")
    p.add_argument("sheet")
    p.add_argument("--light", type=float, default=0.0, help="lightness offset (OKLab L, 0..1)")
    p.add_argument("--chroma", type=float, default=1.0, help="chroma factor")
    p.add_argument("--hue", type=float, default=0.0, help="hue shift in degrees")
    p.add_argument("--keep-vivid", type=float, default=0.165, help="colours at least this chromatic (flames) are left alone")
    p.add_argument("--max-light", type=float, default=1.0, help="colours lighter than this (OKLab L: flame cores, glints) are left alone")
    p.add_argument("--reason", default="")
    p.set_defaults(func=cmd_grade)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
