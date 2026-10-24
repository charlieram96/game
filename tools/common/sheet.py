"""Sprite-sheet packer and manifest writer (the art <-> engine contract).

The Godot side (scripts/presentation/sprite_sheet.gd) reads exactly this format.

Manifest (`<name>.json`, next to `<name>.png`):

{
  "version": 1,
  "image": "<name>.png",
  "frame_size": [w, h],            # every frame is the same size
  "columns": N,                    # frames are packed row-major, N per row
  "frame_count": K,
  "pivot": [px, py],               # pixel (from top-left of a frame) that sits on the ground
  "pixels_per_unit": 24,           # sprite pixels per world unit (meter); shared by all sprites
  "animations": {
    "<anim>_<dir>": {"frames": [i, ...], "fps": 8, "loop": true},
    ...
  },
  "meta": {...}                    # free-form, ignored by the engine
}

Direction suffixes: _s (facing the camera / south), _n (facing away / north),
_e (facing right / east). West is rendered by mirroring _e. An animation that
does not depend on direction may be authored only as `<anim>_s`; the engine
falls back to `_s` when a direction is missing.

Rules every frame must follow:
  * keep a fully transparent 1px border inside each frame (no pixel touches the
    frame edge) so the engine's smooth-pixel filter never bleeds neighbours;
  * the pivot is the same for all frames of a sheet;
  * only straight alpha 0 or 255 (no semi-transparent pixels) for characters,
    creatures and props. Effects (VFX) may use partial alpha.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field

from PIL import Image

PIXELS_PER_UNIT = 24


@dataclass
class _Anim:
    frames: list[int]
    fps: float
    loop: bool


@dataclass
class SheetBuilder:
    name: str
    frame_w: int
    frame_h: int
    pivot: tuple[int, int]
    columns: int = 8
    pixels_per_unit: int = PIXELS_PER_UNIT
    meta: dict = field(default_factory=dict)
    _frames: list[Image.Image] = field(default_factory=list)
    _anims: dict[str, _Anim] = field(default_factory=dict)

    def add_frame(self, img: Image.Image) -> int:
        if img.size != (self.frame_w, self.frame_h):
            raise ValueError(
                f"{self.name}: frame size {img.size} != {(self.frame_w, self.frame_h)}"
            )
        self._frames.append(img.convert("RGBA"))
        return len(self._frames) - 1

    def add_animation(
        self, anim_name: str, frames: list[Image.Image], fps: float = 8.0, loop: bool = True
    ) -> list[int]:
        """Append frames and register them under `anim_name` (e.g. "walk_s")."""
        if anim_name in self._anims:
            raise ValueError(f"{self.name}: duplicate animation {anim_name}")
        idx = [self.add_frame(f) for f in frames]
        self._anims[anim_name] = _Anim(idx, fps, loop)
        return idx

    def alias(self, anim_name: str, frame_indices: list[int], fps: float = 8.0, loop: bool = True) -> None:
        """Register an animation that reuses already-added frames."""
        self._anims[anim_name] = _Anim(list(frame_indices), fps, loop)

    def _check_border(self) -> list[str]:
        problems = []
        for i, f in enumerate(self._frames):
            px = f.load()
            w, h = f.size
            for x in range(w):
                if px[x, 0][3] or px[x, h - 1][3]:
                    problems.append(f"frame {i} touches top/bottom edge")
                    break
            for y in range(h):
                if px[0, y][3] or px[w - 1, y][3]:
                    problems.append(f"frame {i} touches left/right edge")
                    break
        return problems

    def save(self, out_dir: str, strict_border: bool = True) -> str:
        if not self._frames:
            raise ValueError(f"{self.name}: no frames")
        problems = self._check_border()
        if problems and strict_border:
            raise ValueError(f"{self.name}: " + "; ".join(problems[:5]))
        os.makedirs(out_dir, exist_ok=True)
        cols = max(1, min(self.columns, len(self._frames)))
        rows = math.ceil(len(self._frames) / cols)
        sheet = Image.new("RGBA", (cols * self.frame_w, rows * self.frame_h), (0, 0, 0, 0))
        for i, f in enumerate(self._frames):
            sheet.paste(f, ((i % cols) * self.frame_w, (i // cols) * self.frame_h))
        png_path = os.path.join(out_dir, f"{self.name}.png")
        sheet.save(png_path)
        manifest = {
            "version": 1,
            "image": f"{self.name}.png",
            "frame_size": [self.frame_w, self.frame_h],
            "columns": cols,
            "frame_count": len(self._frames),
            "pivot": [int(self.pivot[0]), int(self.pivot[1])],
            "pixels_per_unit": self.pixels_per_unit,
            "animations": {
                k: {"frames": v.frames, "fps": v.fps, "loop": v.loop}
                for k, v in sorted(self._anims.items())
            },
            "meta": self.meta,
        }
        with open(os.path.join(out_dir, f"{self.name}.json"), "w") as fh:
            json.dump(manifest, fh, indent=1)
        return png_path


def contact_sheet(png_path: str, scale: int = 4, out_path: str | None = None) -> str:
    """Upscale a sheet with nearest-neighbour on a checker background for review."""
    img = Image.open(png_path).convert("RGBA")
    w, h = img.size
    bg = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    px = bg.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (58, 64, 74, 255) if ((x // 4 + y // 4) % 2) else (78, 86, 98, 255)
    bg.alpha_composite(img)
    bg = bg.resize((w * scale, h * scale), Image.NEAREST)
    out = out_path or png_path.replace(".png", "_preview.png")
    bg.save(out)
    return out
