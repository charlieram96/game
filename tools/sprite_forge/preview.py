"""Review previews (written only to tools/sprite_forge/previews/, which is gitignored)."""

from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, "/home/user/game/tools")
from common.sheet import SheetBuilder, contact_sheet  # noqa: E402

PREVIEW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "previews")


def _checker(w, h, cell=4):
    bg = Image.new("RGBA", (w, h), (70, 76, 88, 255))
    d = ImageDraw.Draw(bg)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            if ((x // cell) + (y // cell)) % 2:
                d.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(58, 64, 74, 255))
    return bg


def contact(png_path: str, scale: int = 4) -> str:
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    name = os.path.splitext(os.path.basename(png_path))[0]
    return contact_sheet(png_path, scale=scale, out_path=os.path.join(PREVIEW_DIR, f"{name}_contact.png"))


def strips(sb: SheetBuilder, anims: list[str] | None = None, scale: int = 4, tag: str = "anims",
           pivot_line: bool = True, max_cols: int = 4, bg_light: bool = False) -> str:
    """One row per animation (frames left to right) with the pivot marked."""
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    names = anims or list(sb._anims.keys())
    fw, fh = sb.frame_w, sb.frame_h
    label_w = 110
    ncols = max(len(sb._anims[n].frames) for n in names)
    ncols = max(ncols, 1)
    cw, ch = fw * scale, fh * scale
    img = Image.new("RGBA", (label_w + ncols * (cw + 4), len(names) * (ch + 4) + 4), (30, 32, 38, 255))
    d = ImageDraw.Draw(img)
    for r, n in enumerate(names):
        a = sb._anims[n]
        y0 = 4 + r * (ch + 4)
        d.text((4, y0 + 4), n, fill=(230, 230, 230, 255))
        d.text((4, y0 + 18), f"{len(a.frames)}f {a.fps}fps", fill=(160, 160, 170, 255))
        for c, fi in enumerate(a.frames):
            x0 = label_w + c * (cw + 4)
            bg = _checker(fw, fh, 4) if not bg_light else Image.new("RGBA", (fw, fh), (190, 196, 180, 255))
            bg.alpha_composite(sb._frames[fi])
            big = bg.resize((cw, ch), Image.NEAREST)
            img.paste(big, (x0, y0))
            if pivot_line:
                px, py = sb.pivot
                dd = ImageDraw.Draw(img)
                yy = y0 + (py + 1) * scale - 1
                dd.line([x0, yy, x0 + cw - 1, yy], fill=(255, 80, 80, 140), width=1)
                xx = x0 + px * scale + scale // 2
                dd.line([xx, yy - 6, xx, yy + 3], fill=(255, 80, 80, 200), width=1)
    out = os.path.join(PREVIEW_DIR, f"{sb.name}_{tag}.png")
    img.save(out)
    return out


def lineup(images: list[Image.Image], scale: int = 4, name: str = "lineup", labels=None) -> str:
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    w = sum(i.width for i in images) + 4 * (len(images) + 1)
    h = max(i.height for i in images) + 8
    canvas = Image.new("RGBA", (w, h + (12 if labels else 0)), (30, 32, 38, 255))
    x = 4
    for k, im in enumerate(images):
        bg = _checker(im.width, im.height, 4)
        bg.alpha_composite(im)
        canvas.paste(bg, (x, 4))
        x += im.width + 4
    big = canvas.resize((canvas.width * scale, canvas.height * scale), Image.NEAREST)
    if labels:
        d = ImageDraw.Draw(big)
        x = 4
        for k, im in enumerate(images):
            d.text((x * scale, (h + 1) * scale), labels[k], fill=(230, 230, 230, 255))
            x += im.width + 4
    out = os.path.join(PREVIEW_DIR, f"{name}.png")
    big.save(out)
    return out
