"""Tests for pixelize: a known sprite is enlarged, blurred, noised and put on a
flat magenta background the way an image model would paint it; pixelize must
recover the original pixels.

    python3 -m unittest discover -s tools/art_forge -p "test_*.py"
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pixelize as PX  # noqa: E402
from common import palette as P  # noqa: E402

SCALE = 12


def make_sprite() -> Image.Image:
    """A 20x28 creature-like sprite in palette colours with a 1px transparent border."""
    img = Image.new("RGBA", (20, 28), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 10, 17, 25), fill=P.ramp("fur_russet", 3))
    d.ellipse((5, 15, 14, 24), fill=P.ramp("cream", 3))
    d.ellipse((4, 2, 15, 12), fill=P.ramp("fur_russet", 4))
    d.rectangle((6, 5, 7, 7), fill=P.ramp("ink", 0))
    d.rectangle((12, 5, 13, 7), fill=P.ramp("ink", 0))
    d.rectangle((15, 18, 18, 20), fill=P.ramp("ember", 5))
    d.rectangle((4, 25, 6, 26), fill=P.ramp("soot", 1))
    d.rectangle((13, 25, 15, 26), fill=P.ramp("soot", 1))
    return img


def painted(sprite: Image.Image, blur: float = 1.2, noise: int = 6, transparent: bool = False) -> np.ndarray:
    big = sprite.resize((sprite.width * SCALE, sprite.height * SCALE), Image.NEAREST)
    if transparent:
        return np.array(big)
    canvas = Image.new("RGBA", big.size, (255, 0, 255, 255))
    canvas.alpha_composite(big)
    canvas = canvas.filter(ImageFilter.GaussianBlur(blur)) if blur else canvas
    arr = np.array(canvas).astype(np.int16)
    rng = np.random.default_rng(7)
    arr[..., :3] += rng.integers(-noise, noise + 1, size=arr[..., :3].shape, dtype=np.int16)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    arr[..., 3] = 255
    return arr


def content(img: Image.Image) -> np.ndarray:
    a = np.array(img)
    box = img.getbbox()
    return a[box[1]:box[3], box[0]:box[2]]


class PixelizeTest(unittest.TestCase):
    def assert_recovers(self, result: Image.Image, original: Image.Image, min_color_match: float) -> None:
        got, want = content(result), content(original)
        self.assertEqual(got.shape, want.shape, "subject size")
        got_a, want_a = got[..., 3] > 0, want[..., 3] > 0
        iou = (got_a & want_a).sum() / (got_a | want_a).sum()
        self.assertGreaterEqual(iou, 0.95, f"silhouette IoU {iou:.3f}")
        both = got_a & want_a
        match = (got[..., :3][both] == want[..., :3][both]).all(-1).mean()
        self.assertGreaterEqual(match, min_color_match, f"colour match {match:.3f}")

    def test_recovers_a_blurred_noisy_sprite_on_magenta(self) -> None:
        original = make_sprite()
        result = PX.pixelize(painted(original), height=original.getbbox()[3] - original.getbbox()[1])
        self.assert_recovers(result, original, 0.9)

    def test_recovers_an_uneven_grid(self) -> None:
        # Image models rarely paint whole-pixel blocks: 11.5x gives 11/12px cells.
        original = make_sprite()
        big = original.resize((round(original.width * 11.5), round(original.height * 11.5)), Image.NEAREST)
        canvas = Image.new("RGBA", (big.width + 37, big.height + 23), (255, 0, 255, 255))
        canvas.alpha_composite(big, (17, 9))
        arr = np.array(canvas.filter(ImageFilter.GaussianBlur(1.0)))
        arr[..., 3] = 255
        result = PX.pixelize(arr, height=original.getbbox()[3] - original.getbbox()[1])
        self.assert_recovers(result, original, 0.9)

    def test_background_does_not_bleed_into_edges(self) -> None:
        # Scaling 26 rows up to 43 makes cells straddle blurred magenta edges.
        result = np.array(PX.pixelize(painted(make_sprite()), height=43, ramps=["fur_russet", "cream", "soot", "ember", "gold", "ink"]))
        ember = {c[:3] for c in P.RAMPS["ember"]}
        opaque = result[..., 3] == 255
        is_ember = np.array([[tuple(px) in ember for px in row] for row in result[..., :3].tolist()]) & opaque
        rows = np.nonzero(is_ember.any(1))[0]
        top, bottom = np.nonzero(opaque.any(1))[0][[0, -1]]
        # The only ember in the sprite is the tail patch (source rows 18-20 of 1-26).
        self.assertTrue(len(rows) > 0, "the ember tail survives")
        self.assertLess(rows.max(), bottom - 4, "no ember-coloured fringe along the feet")
        self.assertGreater(rows.min(), top + 20, "no ember-coloured fringe along the head")

    def test_uses_real_alpha_when_present(self) -> None:
        original = make_sprite()
        result = PX.pixelize(painted(original, transparent=True), height=original.getbbox()[3] - original.getbbox()[1])
        self.assert_recovers(result, original, 0.99)

    def test_detects_the_source_pixel_grid(self) -> None:
        original = make_sprite()
        arr = painted(original, blur=0, noise=0)
        mask = PX.foreground_mask(arr)
        img, mask = PX.crop_to_mask(arr, mask)
        cell = PX.estimate_cell_size(img, mask)
        self.assertIsNotNone(cell)
        self.assertAlmostEqual(cell, SCALE, delta=1.0)
        auto = PX.pixelize(arr)
        self.assert_recovers(auto, original, 0.97)

    def test_output_is_palette_only_with_binary_alpha_and_border(self) -> None:
        result = np.array(PX.pixelize(painted(make_sprite()), height=26, ramps=["fur_russet", "cream", "ink", "ember", "soot"]))
        allowed = {c[:3] for name in ("fur_russet", "cream", "ink", "ember", "soot") for c in P.RAMPS[name]}
        opaque = result[..., 3] == 255
        self.assertTrue(set(np.unique(result[..., 3])) <= {0, 255}, "alpha is 0 or 255")
        self.assertTrue({tuple(c) for c in result[..., :3][opaque].tolist()} <= allowed, "only the chosen ramps")
        self.assertFalse(opaque[0].any() or opaque[-1].any() or opaque[:, 0].any() or opaque[:, -1].any(), "1px transparent border")

    def test_outline_uses_the_darkest_shade_of_the_neighbouring_ramp(self) -> None:
        result = np.array(PX.pixelize(painted(make_sprite()), height=28, outline=True))
        opaque = result[..., 3] == 255
        darkest = {P.darkest(name)[:3] for name in P.RAMPS}
        rows = np.nonzero(opaque.any(1))[0]
        cols = np.nonzero(opaque[rows[0]])[0]
        self.assertIn(tuple(result[rows[0], cols[0], :3].tolist()), darkest, "top edge is an outline colour")
        self.assertNotIn((0, 0, 0), {tuple(c) for c in result[..., :3][opaque].tolist()}, "never pure black")

    def test_fit_into_frame_puts_the_feet_on_the_pivot_row(self) -> None:
        sprite = PX.pixelize(painted(make_sprite()), height=26)
        frame = PX.fit_into_frame(sprite, 48, 48, (24, 44))
        self.assertEqual(frame.size, (48, 48))
        self.assertEqual(frame.getbbox()[3] - 1, 44)
        with self.assertRaises(ValueError):
            PX.fit_into_frame(sprite, 16, 16, (8, 14))


if __name__ == "__main__":
    unittest.main()
