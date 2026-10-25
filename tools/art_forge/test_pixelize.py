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

    def test_opaque_scene_fills_the_exact_size_with_palette_colours(self) -> None:
        # A 16:10 "painting" (a dark sky over a lit ground, a bright fire) for a 16:9 target:
        # nothing is keyed out, the centre is kept and every cell is filled.
        scene = Image.new("RGBA", (640, 400), P.ramp("night", 1))
        d = ImageDraw.Draw(scene)
        d.rectangle((0, 250, 639, 399), fill=P.ramp("moss", 2))
        d.ellipse((300, 220, 340, 260), fill=P.ramp("ember", 5))
        d.rectangle((0, 0, 19, 399), fill=(255, 0, 255, 255))  # cropped away by the 16:9 centre crop
        arr = np.array(scene.filter(ImageFilter.GaussianBlur(1.0)))
        result = np.array(PX.pixelize(arr, height=36, width=64, ramps=["night", "moss", "ember"], opaque=True))
        self.assertEqual(result.shape[:2], (36, 64))
        self.assertTrue((result[..., 3] == 255).all(), "fully opaque, no border")
        allowed = {c[:3] for name in ("night", "moss", "ember") for c in P.RAMPS[name]}
        self.assertTrue({tuple(c) for c in result[..., :3].reshape(-1, 3).tolist()} <= allowed, "only the chosen ramps")
        self.assertEqual(tuple(result[2, 32, :3]), P.ramp("night", 1)[:3], "sky on top")
        self.assertEqual(tuple(result[33, 32, :3]), P.ramp("moss", 2)[:3], "ground below")
        self.assertEqual(tuple(result[21, 32, :3]), P.ramp("ember", 5)[:3], "the fire survives")

    def test_save_indexed_is_lossless(self) -> None:
        import tempfile

        img = PX.pixelize(painted(make_sprite()), height=30, width=20, opaque=True)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scene.png"
            PX.save_indexed(img, path)
            back = Image.open(path)
            self.assertEqual(back.mode, "P")
            self.assertTrue((np.array(back.convert("RGB")) == np.array(img.convert("RGB"))).all())


class DespeckleTest(unittest.TestCase):
    def test_removes_low_contrast_specks_but_keeps_catchlights(self) -> None:
        ramps = ["hair_grey", "gold", "water", "cloth_cream"]
        pal, owners = PX.palette_for(ramps)
        index = {(name, i): owners.index(name) + i for name in ramps for i in range(len(P.RAMPS[name]))}
        grid = np.full((12, 20), index[("hair_grey", 4)])
        grid[3, 4] = index[("gold", 4)]  # a gold fleck in grey hair, about as bright as the hair
        grid[:, 12:] = index[("water", 1)]  # a dark iris...
        grid[6, 15] = index[("cloth_cream", 5)]  # ...with a bright catchlight
        grid[8:10, 2:9] = index[("gold", 3)]  # a gold clasp: big enough to stay
        opaque = np.ones(grid.shape, dtype=bool)
        out, fixed = PX.despeckle(grid.copy(), opaque, pal, owners)
        self.assertEqual(owners[out[3, 4]], "hair_grey", "the fleck takes the hair's ramp")
        self.assertEqual(out[6, 15], index[("cloth_cream", 5)], "the catchlight stays")
        self.assertTrue((out[8:10, 2:9] == index[("gold", 3)]).all(), "the clasp stays")
        self.assertEqual(fixed, 1)


class CompositeTest(unittest.TestCase):
    def test_register_finds_scale_and_shift(self) -> None:
        import composite as CP

        base = Image.new("RGBA", (320, 320), (255, 0, 255, 255))
        d = ImageDraw.Draw(base)
        d.ellipse((90, 60, 230, 200), fill=P.ramp("skin_tan", 3))
        d.rectangle((70, 190, 250, 319), fill=P.ramp("cloth_teal", 3))
        d.ellipse((120, 110, 140, 130), fill=P.ramp("ink", 0))
        d.ellipse((180, 110, 200, 130), fill=P.ramp("ink", 0))
        b = np.array(base)
        fill = np.array([255, 0, 255, 255], np.uint8)
        # The "expression" painting: the same figure 5% smaller, moved 10 px left and 6 px down.
        other = CP.warp(b, 1 / 1.05, -10 / 1.05, 6 / 1.05, (320, 320), fill)
        bm = PX.foreground_mask(b)
        om = PX.foreground_mask(other)
        s, dx, dy = CP.register(b, other, bm, om, work=80)
        self.assertAlmostEqual(s, 1.05, delta=0.02)
        self.assertAlmostEqual(dx, 10, delta=4)
        self.assertAlmostEqual(dy, -6, delta=4)


class SheetInstallTest(unittest.TestCase):
    def test_frames_install_into_a_row_and_replace_an_older_sheet(self) -> None:
        import tempfile

        import forge

        a = Image.new("RGBA", (8, 8), (10, 20, 30, 255))
        b = Image.new("RGBA", (8, 8), (40, 50, 60, 255))
        with tempfile.TemporaryDirectory() as tmp:
            sheet = Path(tmp) / "sheet.png"
            Image.new("RGBA", (12, 4), (1, 2, 3, 255)).save(sheet)  # an older sheet with another frame size
            forge.install_frame(b, sheet, 1, 8, 8).save(sheet)
            got = forge.install_frame(a, sheet, 0, 8, 8)
            self.assertEqual(got.size, (16, 8))
            self.assertEqual(got.getpixel((0, 0)), (10, 20, 30, 255))
            self.assertEqual(got.getpixel((8, 0)), (40, 50, 60, 255))
            with self.assertRaises(ValueError):
                forge.install_frame(Image.new("RGBA", (4, 4)), sheet, 0, 8, 8)


if __name__ == "__main__":
    unittest.main()
