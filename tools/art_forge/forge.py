#!/usr/bin/env python3
"""art_forge: generated art for Wildbound through the OpenRouter Image API.

    python3 tools/art_forge/forge.py models                       # image models and their options (no key needed)
    python3 tools/art_forge/forge.py prompt hesper_portrait --expr stern
    python3 tools/art_forge/forge.py gen emberlyn --view e --count 4
    python3 tools/art_forge/forge.py gen hesper_portrait --expr smile --ref <neutral.png>
    python3 tools/art_forge/forge.py bakeoff emberlyn --models google/gemini-3-pro-image,openai/gpt-5.4-image-2
    python3 tools/art_forge/forge.py review emberlyn              # contact sheet: painting + pixelized result
    python3 tools/art_forge/forge.py pixelize <candidate.png> --brief emberlyn --out assets/...png
    python3 tools/art_forge/forge.py composite <neutral.png> <expr.png> --face x0,y0,x1,y1   # face onto the locked neutral
    python3 tools/art_forge/forge.py pixelize <expr.composite.png> --brief hesper_portrait --out <sheet.png> --frame 1

Candidates land in tools/art_forge/_out/<brief>/ (gitignored) with a JSON
sidecar each. Only curated, pixelized results go into assets/, and each one
gets a provenance record in tools/art_forge/provenance/.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import openrouter_images as OR  # noqa: E402
import pixelize as PX  # noqa: E402

OUT = HERE / "_out"
PROVENANCE = HERE / "provenance"
MODELS_CACHE = OUT / "models.json"


def load_briefs() -> dict:
    return json.loads((HERE / "briefs.json").read_text())


def get_brief(briefs: dict, brief_id: str) -> dict:
    if brief_id not in briefs["briefs"]:
        sys.exit(f"unknown brief '{brief_id}'. Known: {', '.join(sorted(briefs['briefs']))}")
    return briefs["briefs"][brief_id]


def compose_prompt(briefs: dict, brief_id: str, view: str | None = None, expr: str | None = None, with_refs: bool = False,
                   pose: str | None = None, note: str | None = None) -> str:
    brief = get_brief(briefs, brief_id)
    kind = briefs["kinds"][brief["kind"]]
    parts = [kind["style"]]
    # the brief may override the kind's framing (how big the subject is drawn), the kind the shared views
    framing = brief.get("framing", kind.get("framing"))
    if framing:
        parts.append(framing)
    views = kind.get("views", briefs["views"])
    if view:
        if view not in views:
            sys.exit(f"unknown view '{view}' (use {', '.join(views)})")
        parts.append(views[view])
    if with_refs:
        parts.append("Keep the exact design of the character in the reference image(s): the same proportions, colours, outfit and markings.")
    parts.append("Subject: " + brief["subject"])
    if expr:
        expressions = brief.get("expressions", {})
        if expr not in expressions:
            sys.exit(f"brief '{brief_id}' has no expression '{expr}' (has: {', '.join(expressions) or 'none'})")
        parts.append("Expression: " + expressions[expr] + ".")
    if pose:
        poses = brief.get("poses", {})
        if pose not in poses:
            sys.exit(f"brief '{brief_id}' has no pose '{pose}' (has: {', '.join(poses) or 'none'})")
        text = poses[pose]
        if isinstance(text, dict):  # per-view wording, with an optional shared "all"
            text = " ".join(t for t in (text.get("all"), text.get(view or "s")) if t)
        parts.append("Pose: " + text)
    if note:
        parts.append(note)
    parts.append(briefs["originality"])
    return " ".join(parts)


def models() -> list[dict]:
    return OR.list_models(MODELS_CACHE)


def cmd_models(args: argparse.Namespace) -> None:
    if args.refresh and MODELS_CACHE.exists():
        MODELS_CACHE.unlink()
    for m in sorted(models(), key=lambda m: m.get("id", "")):
        sp = m.get("supported_parameters", {})
        extras = []
        if "background" in sp:
            extras.append("background=" + "/".join(sp["background"].get("values", [])))
        if "quality" in sp:
            extras.append("quality=" + "/".join(sp["quality"].get("values", [])))
        if "resolution" in sp:
            extras.append("resolution=" + "/".join(sp["resolution"].get("values", [])))
        refs = sp.get("input_references", {}).get("max", 0)
        print(f"{m['id']:44s} n<={OR.max_batch(m):<2d} refs<={refs:<2d} {'  '.join(extras)}")


def generate(briefs: dict, brief_id: str, model: str, count: int, args: argparse.Namespace, tag_extra: str = "") -> list[Path]:
    brief = get_brief(briefs, brief_id)
    kind = briefs["kinds"][brief["kind"]]
    refs = [Path(r) for r in (args.ref or [])]
    prompt = compose_prompt(briefs, brief_id, args.view, args.expr, bool(refs), getattr(args, "pose", None), getattr(args, "note", None))
    entry = OR.find_model(model, models())
    batch = OR.max_batch(entry)
    tag = "_".join(x for x in (getattr(args, "pose", None), args.view, args.expr, tag_extra) if x)
    saved: list[Path] = []
    rounds = 0
    while len(saved) < count:
        n = min(batch, count - len(saved))
        options = {
            "n": n,
            "aspect_ratio": args.aspect or brief.get("aspect_ratio", kind.get("aspect_ratio")),
            "resolution": args.resolution,
            "quality": args.quality,
            "background": args.background,
            "seed": (args.seed + rounds) if args.seed is not None else None,
        }
        round_tag = f"{tag}_r{rounds}" if tag else f"r{rounds}"
        paths = OR.generate(prompt, model, OUT / brief_id, tag=round_tag, references=refs, models=models(), dry_run=args.dry_run, force=args.force, **options)
        if args.dry_run:
            break
        saved.extend(paths)
        rounds += 1
        for p in paths:
            print(p.relative_to(ROOT))
    return saved


def cmd_prompt(args: argparse.Namespace) -> None:
    print(compose_prompt(load_briefs(), args.brief, args.view, args.expr, bool(args.ref), args.pose, args.note))


def cmd_gen(args: argparse.Namespace) -> None:
    briefs = load_briefs()
    brief = get_brief(briefs, args.brief)
    model = args.model or briefs["kinds"][brief["kind"]]["model"]
    generate(briefs, args.brief, model, args.count, args)


def cmd_bakeoff(args: argparse.Namespace) -> None:
    briefs = load_briefs()
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        try:
            generate(briefs, args.brief, model, args.count, args)
        except OR.ImageAPIError as e:
            print(f"{model}: {e}", file=sys.stderr)
    if not args.dry_run:
        cmd_review(args)


def _candidates(brief_id: str) -> list[Path]:
    folder = OUT / brief_id
    return sorted((p for p in folder.glob("*") if p.suffix.lower() in (".png", ".jpg", ".webp") and ".pixel" not in p.name and p.name != "review.png"), key=lambda p: p.stat().st_mtime)


def _pixel_preview(path: Path, brief: dict, scale: int) -> Image.Image | None:
    if "size" not in brief:
        return None
    try:
        if brief.get("opaque"):
            sprite = PX.pixelize(path, height=brief["size"][1], width=brief["size"][0], ramps=brief.get("ramps"), opaque=True)
            scale = max(1, scale // 2)
        else:
            sprite = PX.pixelize(path, height=content_height(brief), width=brief["size"][0] - 2, ramps=brief.get("ramps"), clean_specks=bool(brief.get("despeckle")))
    except ValueError:
        return None
    return sprite.resize((sprite.width * scale, sprite.height * scale), Image.NEAREST)


def content_height(brief: dict) -> int:
    if "pivot" in brief:
        return brief["pivot"][1] - 1
    return brief["size"][1] - 2


def cmd_review(args: argparse.Namespace) -> None:
    briefs = load_briefs()
    brief = get_brief(briefs, args.brief)
    items = _candidates(args.brief)
    if not items:
        sys.exit(f"no candidates for '{args.brief}' yet")
    thumb, scale = 320, 4
    cells = []
    for i, path in enumerate(items):
        painting = Image.open(path).convert("RGBA")
        painting.thumbnail((thumb, thumb))
        pixel = _pixel_preview(path, brief, scale)
        w = thumb + (pixel.width + 12 if pixel else 0)
        h = max(thumb, pixel.height if pixel else 0) + 22
        cell = Image.new("RGBA", (w, h), (40, 36, 46, 255))
        cell.alpha_composite(painting, (0, 22))
        if pixel:
            checker = Image.new("RGBA", pixel.size, (70, 66, 76, 255))
            checker.alpha_composite(pixel)
            cell.alpha_composite(checker, (thumb + 12, 22))
        sidecar = path.with_suffix(".json")
        model = json.loads(sidecar.read_text()).get("model", "?") if sidecar.exists() else "?"
        ImageDraw.Draw(cell).text((4, 4), f"[{i}] {path.name[:44]}  ({model})", fill=(240, 230, 210, 255))
        cells.append(cell)
    cols = 2 if cells[0].width > 500 else 3
    cw = max(c.width for c in cells) + 8
    ch = max(c.height for c in cells) + 8
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGBA", (cw * cols, ch * rows), (24, 20, 28, 255))
    for i, c in enumerate(cells):
        sheet.alpha_composite(c, ((i % cols) * cw + 4, (i // cols) * ch + 4))
    out = OUT / args.brief / "review.png"
    sheet.save(out)
    print(out.relative_to(ROOT))
    for i, path in enumerate(items):
        print(f"  [{i}] {path.relative_to(ROOT)}")


def cmd_composite(args: argparse.Namespace) -> None:
    import composite as CP

    base, expr = Path(args.base), Path(args.expr)
    regions = [tuple(int(v) for v in r.split(",")) for r in args.face]
    image, info = CP.composite(str(base), str(expr), regions, feather=args.feather, tolerance=args.tolerance, colour=not args.keep_colour)
    out = Path(args.out) if args.out else expr.with_name(expr.stem + ".composite.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    # The sidecar is the expression's generation record plus how it was combined, so
    # `pixelize --out` puts the whole story in the provenance record.
    sidecar = lambda p: json.loads(p.with_suffix(".json").read_text()) if p.with_suffix(".json").exists() else None  # noqa: E731
    record = sidecar(expr) or {}
    record["composite"] = {"base": base.name, "base_generation": sidecar(base), "face_from": expr.name, **info}
    out.with_suffix(".json").write_text(json.dumps(record, indent=1))
    print(f"{out} (expression scaled {info['scale']}, shifted {info['dx']}, {info['dy']} px onto the base)")


def install_frame(sprite: Image.Image, sheet_path: Path, frame: int, frame_w: int, frame_h: int) -> Image.Image:
    """The sheet at `sheet_path` (frames in one row) with `sprite` as frame `frame`.

    The other frames of a sheet with this frame size are kept; a sheet with a
    different frame size (an older version of the asset) is started afresh.
    """
    if sprite.size != (frame_w, frame_h):
        raise ValueError(f"a {sprite.width}x{sprite.height} image is not a {frame_w}x{frame_h} frame")
    old = Image.open(sheet_path).convert("RGBA") if sheet_path.exists() else None
    if old is not None and (old.height != frame_h or old.width % frame_w):
        old = None
    sheet = Image.new("RGBA", (max(frame_w * (frame + 1), old.width if old else 0), frame_h), (0, 0, 0, 0))
    if old is not None:
        sheet.paste(old, (0, 0))
    sheet.paste(sprite, (frame * frame_w, 0))
    return sheet


def write_provenance(out: Path, record: dict, frame: int | None) -> None:
    """One record per installed file; a sheet keeps one entry per frame."""
    PROVENANCE.mkdir(exist_ok=True)
    path = PROVENANCE / (out.stem + ".json")
    if frame is not None:
        old = json.loads(path.read_text()) if path.exists() else {}
        frames = old.get("frames", {}) if old.get("asset") == record["asset"] else {}
        frames[str(frame)] = {k: v for k, v in record.items() if k != "asset"}
        record = {"asset": record["asset"], "frames": {k: frames[k] for k in sorted(frames, key=int)}}
    path.write_text(json.dumps(record, indent=1))


def cmd_pixelize(args: argparse.Namespace) -> None:
    briefs = load_briefs()
    brief = get_brief(briefs, args.brief)
    source = Path(args.image)
    opaque = args.opaque or bool(brief.get("opaque"))
    if args.frame is not None and not args.out:
        sys.exit("--frame needs --out: the sheet to install the frame into")
    if opaque:
        height = args.height or (brief["size"][1] if "size" in brief else None)
        width = args.width or (brief["size"][0] if "size" in brief else None)
    else:
        height = args.height or (content_height(brief) if "size" in brief else None)
        width = args.width or (brief["size"][0] - 2 if "size" in brief else None)
    ramps = None if args.all_colors else brief.get("ramps")
    despeckle = args.despeckle or bool(brief.get("despeckle"))
    sprite = PX.pixelize(source, height=height, width=width, ramps=ramps, outline=args.outline, tolerance=args.tolerance, opaque=opaque, clean_specks=despeckle)
    if "pivot" in brief and not args.no_frame and not opaque:
        sprite = PX.fit_into_frame(sprite, brief["size"][0], brief["size"][1], tuple(brief["pivot"]))
    out = Path(args.out) if args.out else source.with_name(source.stem + ".pixel.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.frame is not None:
        frame_w, frame_h = brief["size"] if "size" in brief else sprite.size
        install_frame(sprite, out, args.frame, frame_w, frame_h).save(out)
    elif opaque:
        PX.save_indexed(sprite, out)
    else:
        sprite.save(out)
    stem = out.stem + (f".f{args.frame}" if args.frame is not None else "")
    preview = out.with_name(stem + ".x4.png") if not args.out else OUT / args.brief / (stem + ".x4.png")
    preview.parent.mkdir(parents=True, exist_ok=True)
    sprite.resize((sprite.width * 4, sprite.height * 4), Image.NEAREST).save(preview)
    where = f" frame {args.frame}" if args.frame is not None else ""
    print(f"{out}{where} ({sprite.width}x{sprite.height}); preview {preview}")
    if args.out:
        sidecar = source.with_suffix(".json")
        record = {
            "asset": str(out.resolve().relative_to(ROOT)) if out.resolve().is_relative_to(ROOT) else str(out),
            "source_image": source.name,
            "generation": json.loads(sidecar.read_text()) if sidecar.exists() else None,
            "pixelize": {"brief": args.brief, "height": height, "width": width, "outline": args.outline, "ramps": ramps, "tolerance": args.tolerance, "opaque": opaque, "despeckle": despeckle},
            "installed": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        write_provenance(out, record, args.frame)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("models", help="list image models and their options")
    p.add_argument("--refresh", action="store_true")
    p.set_defaults(func=cmd_models)

    def gen_options(p: argparse.ArgumentParser) -> None:
        p.add_argument("brief")
        p.add_argument("--view", choices=["s", "n", "e"])
        p.add_argument("--expr")
        p.add_argument("--pose", help="a pose from the brief's `poses` (sprite_hd briefs)")
        p.add_argument("--note", help="extra direction appended to the prompt (kept in the sidecar's prompt)")
        p.add_argument("--ref", nargs="*", help="reference images for a consistent design")
        p.add_argument("--count", type=int, default=2)
        p.add_argument("--aspect")
        p.add_argument("--resolution")
        p.add_argument("--quality")
        p.add_argument("--background", help="e.g. transparent, on models that support it")
        p.add_argument("--seed", type=int)
        p.add_argument("--dry-run", action="store_true", help="print the request instead of sending it")
        p.add_argument("--force", action="store_true", help="regenerate even if this exact request is cached")

    p = sub.add_parser("prompt", help="print the composed prompt")
    p.add_argument("brief")
    p.add_argument("--view", choices=["s", "n", "e"])
    p.add_argument("--expr")
    p.add_argument("--pose")
    p.add_argument("--note")
    p.add_argument("--ref", nargs="*")
    p.set_defaults(func=cmd_prompt)

    p = sub.add_parser("gen", help="generate candidates for a brief")
    gen_options(p)
    p.add_argument("--model")
    p.set_defaults(func=cmd_gen)

    p = sub.add_parser("bakeoff", help="the same brief on several models, then a review sheet")
    gen_options(p)
    p.add_argument("--models", required=True, help="comma-separated model ids")
    p.set_defaults(func=cmd_bakeoff)

    p = sub.add_parser("review", help="contact sheet of a brief's candidates with pixelized previews")
    p.add_argument("brief")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("pixelize", help="turn a candidate into game pixel art (and install it with --out)")
    p.add_argument("image")
    p.add_argument("--brief", required=True)
    p.add_argument("--out")
    p.add_argument("--height", type=int)
    p.add_argument("--width", type=int)
    p.add_argument("--outline", action="store_true")
    p.add_argument("--all-colors", action="store_true", help="use the whole master palette, not just the brief's ramps")
    p.add_argument("--tolerance", type=float, default=48.0, help="background key tolerance")
    p.add_argument("--no-frame", action="store_true", help="don't place the sprite in the brief's frame")
    p.add_argument("--frame", type=int, help="install as frame N of the one-row sheet at --out (other frames are kept)")
    p.add_argument("--opaque", action="store_true", help="a whole scene (key art): no keying, exact brief size, no border, palette PNG")
    p.add_argument("--despeckle", action="store_true", help="remove tiny low-contrast specks of a stray ramp (on by default for briefs with \"despeckle\")")
    p.set_defaults(func=cmd_pixelize)

    p = sub.add_parser("composite", help="blend an expression's face into the locked neutral painting (before pixelize)")
    p.add_argument("base", help="the locked neutral painting")
    p.add_argument("expr", help="the expression painting, generated with the neutral as --ref")
    p.add_argument("--face", action="append", required=True, help="x0,y0,x1,y1 ellipse in base pixels; repeat for more regions")
    p.add_argument("--feather", type=float, default=14.0)
    p.add_argument("--keep-colour", action="store_true", help="don't colour-match the expression to the base")
    p.add_argument("--tolerance", type=float, default=48.0, help="background key tolerance")
    p.add_argument("--out")
    p.set_defaults(func=cmd_composite)

    args = ap.parse_args()
    try:
        args.func(args)
    except OR.ImageAPIError as e:
        sys.exit(str(e))
    except BrokenPipeError:  # output piped into head and friends
        sys.stderr.close()


if __name__ == "__main__":
    main()
