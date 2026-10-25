#!/usr/bin/env python3
"""HD sprite sheets from key poses: registration, in-betweens, normal maps.

    python3 tools/art_forge/animate.py emberlyn            # build one sheet (recipe in sheets/<name>.py)
    python3 tools/art_forge/animate.py emberlyn --review   # + 4x review pages in tools/art_forge/_out/review/
    python3 tools/art_forge/animate.py --all

A recipe (tools/art_forge/sheets/<name>.py) names the sheet's frame size,
pivot and pixels per unit, and lists every animation as frames built from the
key poses in tools/art_forge/keys/<name>/ (see keys.py) with the operations
below. Everything here is deterministic: rebuilding gives the same sheet.

Key poses are drawn by an image model one at a time, so two keys never line
up by themselves. `place` registers a key onto the frame: the lowest opaque
row (the paws) goes on the pivot row and the key is shifted sideways to best
overlap the view's reference key (its `stand` pose), so the body doesn't
swim between frames. In-betweens only move existing pixels (rows shifted or
repeated), so every frame keeps the key's palette and pixel clusters:

* `breathe(frame, n)`  the body above the legs rises n px (sinks for n < 0);
  the legs stretch or compress by repeating or dropping one row, so the feet
  stay planted;
* `lift(frame, n)`     the whole sprite n px up (hops; not for grounded anims);
* `flicker(frame, k)`  flame tongues sway and stretch by a pixel (phase k);
* `squash(frame, sx, sy)` nearest-neighbour scale about the pivot;
* `glow(frame, steps)` the emissive pixels one palette shade lighter/darker.

Each frame gets a normal map (normals.py) whose alpha is the emission mask
from the recipe's `glow` rule. Identical frames are stored once.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import keys as K  # noqa: E402
import normals as NM  # noqa: E402

KEYS = HERE / "keys"
OUT_REVIEW = HERE / "_out" / "review"


# --- small image helpers ------------------------------------------------------------------

def load_key(sheet: str, name: str) -> np.ndarray:
    path = KEYS / sheet / f"{name}.png"
    if not path.exists():
        raise SystemExit(f"missing key pose {path.relative_to(ROOT)}")
    return np.array(Image.open(path).convert("RGBA"))


def mask_of(img: np.ndarray) -> np.ndarray:
    return img[..., 3] > 0


def bbox(img: np.ndarray) -> tuple[int, int, int, int] | None:
    m = mask_of(img)
    if not m.any():
        return None
    ys = np.nonzero(m.any(1))[0]
    xs = np.nonzero(m.any(0))[0]
    return int(xs[0]), int(ys[0]), int(xs[-1]) + 1, int(ys[-1]) + 1


def crop(img: np.ndarray) -> np.ndarray:
    b = bbox(img)
    return img[b[1]:b[3], b[0]:b[2]].copy()


def shift(img: np.ndarray, dx: int, dy: int) -> np.ndarray:
    out = np.zeros_like(img)
    h, w = img.shape[:2]
    ys0, ys1 = max(0, dy), min(h, h + dy)
    xs0, xs1 = max(0, dx), min(w, w + dx)
    out[ys0:ys1, xs0:xs1] = img[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
    return out


def lowest_row(img: np.ndarray) -> int:
    return int(np.nonzero(mask_of(img).any(1))[0].max())


def components(mask: np.ndarray) -> list[np.ndarray]:
    """8-connected components of a boolean mask (each a boolean mask)."""
    h, w = mask.shape
    seen = np.zeros_like(mask)
    out = []
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        comp = np.zeros_like(mask)
        stack = [(y, x)]
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            comp[cy, cx] = True
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        out.append(comp)
    return out


# --- the sheet ----------------------------------------------------------------------------

@dataclass
class Sheet:
    name: str
    frame: tuple[int, int]
    pivot: tuple[int, int]
    ppu: int
    out_dir: Path
    kind: str = "kith"
    meta: dict = field(default_factory=dict)
    columns: int = 8
    glow_rule: object = None          # fn(rgba) -> glow (H, W) float in 0..1
    normal_params: dict = field(default_factory=dict)
    lighting: dict = field(default_factory=dict)        # manifest "lighting": shader response of this sheet
    anims: dict = field(default_factory=dict)          # name -> (frames, fps, loop)
    _keys: dict = field(default_factory=dict)
    _ref: dict = field(default_factory=dict)            # view -> reference key name

    # keys ---------------------------------------------------------------------------------
    def key(self, name: str) -> np.ndarray:
        if name not in self._keys:
            self._keys[name] = crop(load_key(self.name, name))
        return self._keys[name]

    def set_reference(self, view: str, key_name: str) -> None:
        self._ref[view] = key_name

    def blank(self) -> np.ndarray:
        return np.zeros((self.frame[1], self.frame[0], 4), dtype=np.uint8)

    def place(self, key_name: str, dx: int = 0, dy: int = 0, register: bool = True, anchor: str = "overlap",
              flip: bool = False) -> np.ndarray:
        """The key in a full frame: paws on the pivot row, registered sideways to its view's reference.
        `flip` mirrors the key first (a symmetric subject leaning the other way)."""
        img = self.key(key_name)
        if flip:
            img = img[:, ::-1].copy()
        h, w = img.shape[:2]
        x = self.pivot[0] - w // 2
        if register:
            view = key_name.rsplit("_", 1)[1]
            ref_name = self._ref.get(view)
            if ref_name and ref_name != key_name:
                x = self._register_x(img, self.key(ref_name), x)
            elif anchor == "legs":
                x = self.pivot[0] - int(round(self._legs_centre(img)))
        y = self.pivot[1] - (h - 1)
        out = self.blank()
        x += dx
        y += dy
        # a registered key that would leave the frame is pushed back inside (1px border kept)
        x = min(max(x, 1), self.frame[0] - 1 - w)
        fh, fw = out.shape[:2]
        sx0, sy0 = max(0, -x), max(0, -y)
        sx1, sy1 = min(w, fw - x), min(h, fh - y)
        if sx1 - sx0 < w or sy1 - sy0 < h:
            raise SystemExit(f"{self.name}: key {key_name} ({w}x{h}) at {x},{y} does not fit the {fw}x{fh} frame")
        out[y + sy0:y + sy1, x + sx0:x + sx1] = img[sy0:sy1, sx0:sx1]
        return out

    def place_on(self, key_name: str, ref_frame: np.ndarray, match, reach: int = 24) -> np.ndarray:
        """The key in a full frame, shifted (x and y) so that its `match(rgba)` mask best overlaps the
        same mask of `ref_frame` (a placed frame): for subjects with no feet on the ground (a hovering
        moth registered on its body, whatever the wings do)."""
        img = self.key(key_name)
        h, w = img.shape[:2]
        fh, fw = self.frame[1], self.frame[0]
        target = match(ref_frame)
        km = match(img)
        if not target.any() or not km.any():
            raise SystemExit(f"{self.name}: nothing to register {key_name} on")
        ty, tx = (float(v.mean()) for v in np.nonzero(target))
        ky, kx = (float(v.mean()) for v in np.nonzero(km))
        x0, y0 = int(round(tx - kx)), int(round(ty - ky))
        best, best_xy = -1.0, (x0, y0)
        for y in range(y0 - reach // 3, y0 + reach // 3 + 1):
            for x in range(x0 - reach // 3, x0 + reach // 3 + 1):
                if x < 1 or y < 1 or x + w > fw - 1 or y + h > fh - 1:
                    continue
                cand = np.zeros((fh, fw), dtype=bool)
                cand[y:y + h, x:x + w] = km
                score = (cand & target).sum() / max((cand | target).sum(), 1)
                if score > best:
                    best, best_xy = score, (x, y)
        x, y = best_xy
        if not (1 <= x and x + w <= fw - 1 and 1 <= y and y + h <= fh - 1):
            raise SystemExit(f"{self.name}: key {key_name} ({w}x{h}) does not fit the {fw}x{fh} frame")
        out = self.blank()
        out[y:y + h, x:x + w] = img
        return out

    def _legs_centre(self, img: np.ndarray) -> float:
        m = mask_of(img)
        h = m.shape[0]
        lower = m[int(h * 0.6):]
        xs = np.nonzero(lower)[1]
        return float(xs.mean()) if len(xs) else img.shape[1] / 2

    def _register_x(self, img: np.ndarray, ref: np.ndarray, x_default: int) -> int:
        """x of `img` (bottom-aligned with `ref`) that best overlaps `ref` placed at the pivot."""
        ref_x = self.pivot[0] - ref.shape[1] // 2
        H = max(img.shape[0], ref.shape[0])
        W = self.frame[0] * 2
        base = np.zeros((H, W), dtype=bool)
        rm = mask_of(ref)
        base[H - rm.shape[0]:, ref_x + W // 4:ref_x + W // 4 + rm.shape[1]] = rm
        im = mask_of(img)
        best, best_x = -1.0, x_default
        for x in range(x_default - 24, x_default + 25):
            cand = np.zeros_like(base)
            xx = x + W // 4
            if xx < 0 or xx + im.shape[1] > W:
                continue
            cand[H - im.shape[0]:, xx:xx + im.shape[1]] = im
            inter = (cand & base).sum()
            union = (cand | base).sum()
            score = inter / max(union, 1) - 0.002 * abs(x - x_default)
            if score > best:
                best, best_x = score, x
        return best_x

    # animations -----------------------------------------------------------------------------
    def add(self, name: str, frames: list[np.ndarray], fps: float, loop: bool, glow=None) -> None:
        """`glow`: an emission rule for these frames instead of the sheet's (e.g. moss that glows while focusing)."""
        if name in self.anims:
            raise SystemExit(f"{self.name}: duplicate animation {name}")
        for i, f in enumerate(frames):
            if f.shape[:2] != (self.frame[1], self.frame[0]):
                raise SystemExit(f"{self.name}:{name}[{i}] is {f.shape[1]}x{f.shape[0]}, not {self.frame}")
        self.anims[name] = ([f.copy() for f in frames], fps, loop, glow)

    # output ---------------------------------------------------------------------------------
    def build(self, review: bool = False) -> dict:
        frames: list[np.ndarray] = []
        rules: list = []
        index: dict[str, int] = {}
        table = {}
        for name in sorted(self.anims):
            fr, fps, loop, glow = self.anims[name]
            rule = glow or self.glow_rule
            ids = []
            for f in fr:
                _check_border(self.name, name, f)
                h = hashlib.sha1(f.tobytes() + str(id(rule)).encode()).hexdigest()
                if h not in index:
                    index[h] = len(frames)
                    frames.append(f)
                    rules.append(rule)
                ids.append(index[h])
            table[name] = {"frames": ids, "fps": fps, "loop": loop}
        fw, fh = self.frame
        cols = self.columns
        rows = -(-len(frames) // cols)
        sheet = np.zeros((rows * fh, cols * fw, 4), dtype=np.uint8)
        nsheet = np.zeros_like(sheet)
        nsheet[..., 0:2] = 128
        nsheet[..., 2] = 255
        nsheet[..., 3] = 255
        for i, f in enumerate(frames):
            y0, x0 = (i // cols) * fh, (i % cols) * fw
            sheet[y0:y0 + fh, x0:x0 + fw] = f
            g = rules[i](f) if rules[i] else None
            nm = NM.frame_normal_map(f, glow_colors=None, **self.normal_params)
            if g is not None:
                nm[..., 3] = np.clip(np.round(255.0 - 127.0 * np.clip(g, 0, 1)), 128, 255).astype(np.uint8)
            nsheet[y0:y0 + fh, x0:x0 + fw] = nm
        self.out_dir.mkdir(parents=True, exist_ok=True)
        png = self.out_dir / f"{self.name}.png"
        npng = self.out_dir / f"{self.name}_normal.png"
        Image.fromarray(sheet, "RGBA").save(png, optimize=True)
        Image.fromarray(nsheet, "RGBA").save(npng, optimize=True)
        _normal_import_flags(npng)
        manifest = {
            "version": 1,
            "image": png.name,
            "normal_map": npng.name,
            "frame_size": [fw, fh],
            "columns": cols,
            "frame_count": len(frames),
            "pivot": [int(self.pivot[0]), int(self.pivot[1])],
            "pixels_per_unit": self.ppu,
            "animations": table,
            **({"lighting": self.lighting} if self.lighting else {}),
            "meta": {"kind": self.kind, **self.meta, "generator": "tools/art_forge/animate.py",
                     "recipe": f"tools/art_forge/sheets/{self.name}.py", "keys": f"tools/art_forge/keys/{self.name}/",
                     "provenance": f"tools/art_forge/provenance/keys_{self.name}.json"},
        }
        (self.out_dir / f"{self.name}.json").write_text(json.dumps(manifest, indent=1))
        if review:
            for p in review_pages(self, frames, table, nsheet):
                print(f"  review: {p.relative_to(ROOT)}")
        return manifest


def _normal_import_flags(npng: Path) -> None:
    """A normal map imports as plain data: never treated as a normal-map texture, alpha border left alone."""
    imp = npng.with_name(npng.name + ".import")
    if not imp.exists():
        print(f"  note: import {npng.relative_to(ROOT)} in Godot, then rebuild to set its import flags")
        return
    text = imp.read_text()
    new = text.replace("compress/normal_map=0", "compress/normal_map=2").replace("process/fix_alpha_border=true", "process/fix_alpha_border=false")
    if new != text:
        imp.write_text(new)


def _check_border(sheet: str, anim: str, f: np.ndarray) -> None:
    a = f[..., 3]
    if a[0].any() or a[-1].any() or a[:, 0].any() or a[:, -1].any():
        raise SystemExit(f"{sheet}:{anim}: a frame touches the 1px border")


# --- operations ---------------------------------------------------------------------------

def body_split(f: np.ndarray, frac: float = 0.34) -> int:
    """Row between the legs and the body: `frac` of the sprite height above its lowest row."""
    b = bbox(f)
    return int(round(b[3] - 1 - (b[3] - b[1]) * frac))


def breathe(f: np.ndarray, n: int, frac: float = 0.34) -> np.ndarray:
    """Everything above the split row moves up n px (down for n < 0); the feet stay where they are."""
    if n == 0:
        return f.copy()
    s = body_split(f, frac)
    out = f.copy()
    if n > 0:
        # rows [top..s] move up by n; row s is repeated n times to fill the gap
        out[:s + 1 - n] = f[n:s + 1]
        out[s + 1 - n:s + 1] = f[s:s + 1]
    else:
        n = -n
        # rows above s move down by n, dropping n rows just above s
        out[n:s + 1] = f[0:s + 1 - n]
        out[:n] = 0
    return out


def lift(f: np.ndarray, n: int) -> np.ndarray:
    return shift(f, 0, -n)


def nudge(f: np.ndarray, dx: int, dy: int = 0) -> np.ndarray:
    return shift(f, dx, dy)


def squash(f: np.ndarray, sx: float, sy: float, pivot: tuple[int, int]) -> np.ndarray:
    """Nearest-neighbour scale about the pivot (bottom centre)."""
    h, w = f.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    src_x = np.round(pivot[0] + (xs - pivot[0]) / sx).astype(int)
    src_y = np.round(pivot[1] + (ys - pivot[1]) / sy).astype(int)
    ok = (src_x >= 0) & (src_x < w) & (src_y >= 0) & (src_y < h)
    out = np.zeros_like(f)
    out[ok] = f[src_y[ok], src_x[ok]]
    return out


def flame_region(f: np.ndarray, glow: np.ndarray, min_px: int = 14) -> list[tuple[int, int, int, int]]:
    """Bounding boxes of the big glowing blobs (flames), largest first."""
    comps = [c for c in components(glow > 0.5) if c.sum() >= min_px]
    boxes = []
    for c in sorted(comps, key=lambda c: -c.sum()):
        ys, xs = np.nonzero(c)
        boxes.append((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    return boxes


def flicker(f: np.ndarray, k: int, glow_rule, amount: int = 1) -> np.ndarray:
    """Flame tongues: the top part of each flame sways sideways and stretches by a pixel (phase k)."""
    if glow_rule is None:
        return f.copy()
    g = glow_rule(f)
    out = f.copy()
    sway = (0, amount, 0, -amount)[k % 4]
    stretch = (0, 1, 1, 0, 0, 1)[k % 6] * amount
    for x0, y0, x1, y1 in flame_region(f, g)[:2]:
        fh = y1 - y0
        if fh < 6:
            continue
        # the flame's own columns, padded by its outline
        xa, xb = max(0, x0 - 2), min(f.shape[1], x1 + 2)
        top = max(0, y0 - 2)
        tip = y0 + int(fh * 0.45)    # rows above this are the free-standing tongue
        region = f[top:tip, xa:xb].copy()
        # only move rows that hold nothing but the flame (and its outline) in these columns
        if (mask_of(region) & ~(_dilate(g[top:tip, xa:xb] > 0.25, 2))).sum() > 3:
            continue
        moved = np.zeros_like(region)
        rh = region.shape[0]
        for r in range(rh):
            dx = sway if r < rh * 0.6 else 0
            moved[r] = np.roll(region[r], dx, axis=0) if dx else region[r]
        if stretch and top - stretch >= 1:
            out[top - stretch:top] = 0
            # repeat the middle row of the tongue: the tip rises
            mid = rh // 2
            moved = np.concatenate([moved[:mid], moved[mid:mid + 1].repeat(stretch, axis=0), moved[mid:]], axis=0)
            dst0 = top - stretch
        else:
            dst0 = top
        clear = out[dst0:tip, xa:xb]
        keep = ~_dilate(g[dst0:tip, xa:xb] > 0.25, 2) & mask_of(clear)
        new = moved[:tip - dst0]
        merged = np.where(keep[..., None], clear, new)
        out[dst0:tip, xa:xb] = merged
    return out


def _dilate(m: np.ndarray, n: int) -> np.ndarray:
    out = m.copy()
    for _ in range(n):
        nxt = out.copy()
        nxt[1:] |= out[:-1]
        nxt[:-1] |= out[1:]
        nxt[:, 1:] |= out[:, :-1]
        nxt[:, :-1] |= out[:, 1:]
        out = nxt
    return out


def glow_shift(f: np.ndarray, glow_rule, steps: int, palette: list[tuple[int, int, int]]) -> np.ndarray:
    """Emissive pixels moved `steps` shades along the palette's lightness order (brighter for steps > 0)."""
    if glow_rule is None or steps == 0:
        return f.copy()
    g = glow_rule(f) > 0.25
    pal = np.array(palette, dtype=np.int64)
    lab = K.oklab(pal)
    order = np.argsort(lab[:, 0])
    rank = {tuple(pal[i]): r for r, i in enumerate(order)}
    out = f.copy()
    for y, x in zip(*np.nonzero(g)):
        c = tuple(int(v) for v in f[y, x, :3])
        r = rank.get(c)
        if r is None:
            continue
        # nearest colour of similar hue in the requested direction
        base = lab[order[r]]
        cands = []
        for rr in range(r + (1 if steps > 0 else -1), r + steps * 6 + (1 if steps > 0 else -1), 1 if steps > 0 else -1):
            if 0 <= rr < len(order):
                lc = lab[order[rr]]
                if np.hypot(lc[1] - base[1], lc[2] - base[2]) < 0.06:
                    cands.append(order[rr])
        if cands:
            out[y, x, :3] = pal[cands[min(abs(steps), len(cands)) - 1]]
    return out


def roll(f: np.ndarray, angle: float, axis: str = "z", keep_rim: int = 2, palette=None) -> np.ndarray:
    """A ball sprite rolled by `angle` degrees: its silhouette and outline stay, the surface inside moves.

    axis "z": spinning in the picture plane (rolling sideways; 90-degree steps are exact).
    axis "x": rolling toward the viewer (positive angle: the top comes forward and goes down) or away.
    Nearest-neighbour, so every pixel keeps a palette colour. With the sheet's `palette`, the baked
    light stays put while the surface turns (see below).
    """
    b = bbox(f)
    x0, y0, x1, y1 = b
    m = mask_of(f)
    inner = m.copy()
    for _ in range(keep_rim):
        inner = inner & np.roll(inner, 1, 0) & np.roll(inner, -1, 0) & np.roll(inner, 1, 1) & np.roll(inner, -1, 1)
    cx, cy = (x0 + x1 - 1) / 2.0, (y0 + y1 - 1) / 2.0
    r = max(x1 - x0, y1 - y0) / 2.0
    a = np.radians(angle)
    ys, xs = np.nonzero(inner)
    dx, dy = xs - cx, ys - cy
    if axis == "z":
        sx = cx + dx * np.cos(-a) - dy * np.sin(-a)
        sy = cy + dx * np.sin(-a) + dy * np.cos(-a)
    else:
        dz = np.sqrt(np.clip(r * r - dx * dx - dy * dy, 0.0, None))
        # rotate the visible point back to where it was at angle 0 (image y points down)
        src_y = dy * np.cos(a) - dz * np.sin(a)
        src_z = dy * np.sin(a) + dz * np.cos(a)
        # the hidden back half looks like the front turned over (the moss shows once per turn)
        sy = cy + np.where(src_z >= 0.0, src_y, -src_y)
        sx = cx + dx
    sx = np.clip(np.round(sx).astype(int), 0, f.shape[1] - 1)
    sy = np.clip(np.round(sy).astype(int), 0, f.shape[0] - 1)
    ok = inner[sy, sx]
    out = f.copy()
    out[ys[ok], xs[ok]] = f[sy[ok], sx[ok]]
    if palette is not None:
        # keep the light where it was: the rolled surface takes the shading of where it is now
        # (lightness + broad shading at the destination - broad shading at the source), snapped
        # to the palette colour of the same hue
        pal = np.array(palette, dtype=np.int64)
        plab = K.oklab(pal)
        lut = {(int(c[0]) << 16) | (int(c[1]) << 8) | int(c[2]): i for i, c in enumerate(pal)}
        rgb = f[..., :3].astype(np.int64)
        key = (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2]
        idx = np.vectorize(lambda k: lut.get(int(k), -1))(key)
        lab = np.where((idx >= 0)[..., None], plab[np.clip(idx, 0, None)], 0.0)
        light = NM.blur(np.where(inner, lab[..., 0], 0.0), 4.0) / np.maximum(NM.blur(inner.astype(np.float32), 4.0), 1e-3)
        yy, xx = ys[ok], xs[ok]
        qy, qx = sy[ok], sx[ok]
        target = lab[qy, qx].copy()
        target[:, 0] = target[:, 0] + (light[yy, xx] - light[qy, qx])
        d = ((target[:, None, :] - plab[None, :, :]) ** 2 * np.array([1.0, 2.0, 2.0])).sum(-1)
        out[yy, xx, :3] = pal[d.argmin(1)]
    return out


def debris(f: np.ndarray, keep_largest: int = 1) -> np.ndarray:
    """Only the small loose bits of a frame (flying chips, sparks, dust): every 8-connected
    opaque component except the `keep_largest` biggest ones (the body)."""
    comps = sorted(components(mask_of(f)), key=lambda c: -int(c.sum()))
    out = np.zeros_like(f)
    for c in comps[keep_largest:]:
        out[c] = f[c]
    return out


def under(f: np.ndarray, back: np.ndarray) -> np.ndarray:
    """`back` drawn behind `f` (where f is transparent)."""
    out = f.copy()
    hole = ~mask_of(f) & mask_of(back)
    out[hole] = back[hole]
    return out


def overlay(f: np.ndarray, sprite: np.ndarray, x: int, y: int) -> np.ndarray:
    out = f.copy()
    h, w = sprite.shape[:2]
    a = sprite[..., 3] > 0
    region = out[y:y + h, x:x + w]
    region[a[:region.shape[0], :region.shape[1]]] = sprite[:region.shape[0], :region.shape[1]][a[:region.shape[0], :region.shape[1]]]
    return out


# --- review -------------------------------------------------------------------------------

BACKGROUNDS = {"grey": (128, 128, 128, 255), "sand": (214, 190, 140, 255)}


def review_pages(sheet: Sheet, frames, table, nsheet, scale: int = 4) -> list[Path]:
    """Review pages in _out/review/: <sheet>_overview.png (every animation, 1x, with its lit preview) and
    <sheet>_4x_pN.png (every animation at `scale`x, one row each, on grey and sand alternately, the
    pivot row marked in red)."""
    OUT_REVIEW.mkdir(parents=True, exist_ok=True)
    for old in OUT_REVIEW.glob(f"{sheet.name}_*.png"):
        old.unlink()
    fw, fh = sheet.frame
    names = list(table)
    ncols = max(len(table[n]["frames"]) for n in names)
    out = []
    # overview: all animations at 1x plus the frame lit from the left (normal map at work)
    rows = len(names)
    ov = Image.new("RGBA", (170 + (ncols + 1) * (fw + 4), rows * (fh + 4) + 4), (26, 28, 34, 255))
    d = ImageDraw.Draw(ov)
    for r, n in enumerate(names):
        a = table[n]
        y0 = 4 + r * (fh + 4)
        d.text((6, y0 + 4), n, fill=(235, 235, 235, 255))
        d.text((6, y0 + 20), f"{len(a['frames'])}f {a['fps']:g}fps {'loop' if a['loop'] else 'once'}", fill=(170, 170, 180, 255))
        for c, fi in enumerate(a["frames"]):
            tile = Image.new("RGBA", (fw, fh), BACKGROUNDS["grey"])
            tile.alpha_composite(Image.fromarray(frames[fi], "RGBA"))
            ov.paste(tile, (170 + c * (fw + 4), y0))
        fi = a["frames"][0]
        cols = sheet.columns
        nm = nsheet[(fi // cols) * fh:(fi // cols) * fh + fh, (fi % cols) * fw:(fi % cols) * fw + fw]
        lit = Image.new("RGBA", (fw, fh), (40, 42, 52, 255))
        lit.alpha_composite(Image.fromarray(NM.relight(frames[fi], nm, light=(-0.8, 0.35, 0.5), ambient=0.25, floor=0.35, rim=1.2), "RGBA"))
        ov.paste(lit, (170 + ncols * (fw + 4), y0))
    p = OUT_REVIEW / f"{sheet.name}_overview.png"
    ov.save(p)
    out.append(p)
    # 4x pages
    cw, ch = fw * scale, fh * scale
    rows_per_page = max(1, 2600 // (ch + 8))
    pages = [names[i:i + rows_per_page] for i in range(0, len(names), rows_per_page)]
    for pi, page in enumerate(pages):
        img = Image.new("RGBA", (190 + ncols * (cw + 8), len(page) * (ch + 8) + 8), (26, 28, 34, 255))
        d = ImageDraw.Draw(img)
        for r, n in enumerate(page):
            a = table[n]
            y0 = 8 + r * (ch + 8)
            d.text((8, y0 + 6), n, fill=(235, 235, 235, 255))
            d.text((8, y0 + 22), f"{len(a['frames'])} frames  {a['fps']:g} fps", fill=(170, 170, 180, 255))
            d.text((8, y0 + 38), "loop" if a["loop"] else "once", fill=(170, 170, 180, 255))
            for c, fi in enumerate(a["frames"]):
                x0 = 190 + c * (cw + 8)
                tile = Image.new("RGBA", (fw, fh), BACKGROUNDS["grey"] if (pi * rows_per_page + r) % 2 == 0 else BACKGROUNDS["sand"])
                tile.alpha_composite(Image.fromarray(frames[fi], "RGBA"))
                img.paste(tile.resize((cw, ch), Image.NEAREST), (x0, y0))
                yy = y0 + sheet.pivot[1] * scale + scale - 1
                d.line([x0, yy, x0 + cw - 1, yy], fill=(220, 60, 60, 255), width=1)
        p = OUT_REVIEW / f"{sheet.name}_4x_p{pi + 1}.png"
        img.save(p)
        out.append(p)
    return out


# --- CLI ----------------------------------------------------------------------------------

def load_recipe(name: str):
    sys.path.insert(0, str(HERE / "sheets"))
    return importlib.import_module(name)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheets", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--review", action="store_true")
    args = ap.parse_args()
    names = args.sheets
    if args.all:
        names = sorted(p.stem for p in (HERE / "sheets").glob("*.py") if not p.stem.startswith("_"))
    t0 = time.time()
    for n in names:
        recipe = load_recipe(n)
        sheet = recipe.build()
        man = sheet.build(review=args.review)
        print(f"{n}: {man['frame_count']} frames of {man['frame_size'][0]}x{man['frame_size'][1]} @ {man['pixels_per_unit']} px/unit, "
              f"{len(man['animations'])} animations -> {sheet.out_dir.relative_to(ROOT)}")
    print(f"built in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
