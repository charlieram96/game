# sprite_forge

Procedural generator for Wildbound's original character, creature, prop and
portrait sprite sheets. Everything is drawn from code (no source art), using
the shared palette (`tools/common/palette.py`) and written through the shared
sheet contract (`tools/common/sheet.py` -> `<name>.png` + `<name>.json`).

## Regenerate

```
python3 tools/sprite_forge/build.py              # all sheets + contract validation
python3 tools/sprite_forge/build.py --previews   # also write review previews
python3 tools/sprite_forge/validate.py           # re-check the manifests only
```

Requires Python 3 + Pillow + numpy. A full build takes a few seconds (about
20 s with previews). Review images go to `tools/sprite_forge/previews/`
(gitignored); 2x sheets also get `<name>_review_{grey,sand}_pN.png`: every
animation as a row of frames at 4x on a mid-grey and on the arena's sand
colour, with the pivot row marked, for critical review.

## How it draws

1. **Shapes with volume** (`pix.py`): ellipsoids, tapered tubes along
   polylines/Béziers, polygons and hand-made masks. Every shape carries a
   height field and surface normals, and unions keep the higher surface, so
   bodies blend smoothly.
2. **Parts** = shape + material ramp + base shade + z order. The renderer
   (`pix.Figure.render`) builds a z-buffer, lights every part from the upper
   left (quantised into 3-5 ramp shades, hue shift comes from the ramps),
   removes orphan shade pixels, casts 1-3px shadows from front parts onto the
   parts behind them, draws interior contour lines where it helps readability,
   applies point lights from glowing things (ember coal, lanterns, sigil chain,
   glowing moss), stamps hand-placed decals (eyes, mouths, buttons, sparks)
   and finally adds a 1px outline using the darkest shade of the neighbouring
   material (never pure black). Alpha is strictly 0/255.
3. **Rigs** per character family pose those parts per frame:
   - `human.py`: skeleton for 32x48 people (hips/feet/shoulders/hands with
     2-bone IK for knees and elbows), hand-authored ASCII head silhouettes per
     view shaded with the head's ellipsoid normals, per-expression faces.
   - `emberlyn.py`, `stoneback.py`, `mossling.py`, `lanternmoth.py`: creature
     rigs with pose dataclasses (bob, stretch, head/paw/tail offsets, ember
     flicker, eye/ear/mouth states) plus special poses (sitting, curled,
     lying, rolling ball). `kit.Xf` lets a rig rotate (rearing, tipping over).
   - `explorer.py`, `corin.py`, `hesper.py`, `villagers.py`,
     `sigilbinder.py`, `crowd.py`, `props.py`, `portraits.py`.
4. **Validation** (`validate.py`): exact animation names, frame counts,
   fps/loop where specified, frame size / pivot / pixels-per-unit (read from
   the manifest; see 2x below), binary alpha, 1px transparent border,
   non-empty frames, master-palette colours, and for the kith that opt in,
   that grounded animations (idle, ready, dash windup/land, guard ...) stand
   exactly on the pivot row in every frame.

Conventions: light from the upper-left; `_s` faces the camera, `_n` away,
`_e` right (west = engine mirror of `_e`); feet/paws rest on the pivot row
(their outline lands on it) in every frame; directions are 3/4 top-down.

## 2x sheets (Emberlyn, Stoneback, training totem)

These are drawn at twice the density: 96x96 frames (totem 64x96), pivot
(48,88) (totem (32,90)) and **48 px per world unit**, so they stand exactly as
large in the world as the old 48x48 @ 24 px/unit sheets while showing twice
the detail. The engine reads `pixels_per_unit`, `frame_size` and `pivot` from
the manifest; `validate.py` accepts any whole resolution factor k (24·k px per
unit) as long as frame size and pivot are the 1x values times k.

- **Same rigs, scaled**: `kit.Canvas(48, 48, s=2, hd=True)` takes the rigs'
  48px *design* coordinates and rasterises them at 2x, so proportions and
  poses are unchanged; only hand-placed pixel decals (`cv.grid`/`cv.dot`,
  which stay in raster pixels) are authored at 2x (eyes, noses, mouths,
  claws, flowers, stitching, sparks). `P(v)` / `cv.px(v)` convert design to
  raster coordinates.
- **Softer multi-shade ramps**: materials with a `<ramp>_hd` version in the
  master palette (fur_russet, cream, soot, stone, stone_warm, moss, glow_moss,
  wood, sand, leather, cloth_cream, cloth_red, earth) are painted with it:
  every original shade i sits at index 2·i with an OKLab midpoint between
  neighbours, and `pix.HD_LEVELS` quantises the light in half steps. Rig code
  keeps using original shade numbers (`base=3`, `offset=-1`, half steps such
  as `base=3.5` are allowed).
- **Texture that rides on the rig**: `kit.strand_tex` (hair strands along a
  limb, using `kit.tube_uv` arc-length coordinates, so fur follows the tail's
  curve), slate grain and cracks (Stoneback), hide wrinkles, moss tufts,
  straw/wood grain, burlap weave and twisted rope (totem). Textures perturb
  the light term, so they show where shades meet instead of as noise.
- **Silhouette**: the bushy tail is a tube whose radius follows a sawtooth
  (big swept flicks pointing to the tip, with a crease from each notch);
  `Figure.floor` keeps every part off the ground row so planted feet always
  land on the pivot; `Figure.outline_shadow` adds a second outline ring on
  the shadow (right/bottom) side, or all round with `Figure.outline_all`
  (used by the 2x sheets: 2px at 48 px/unit is the same world-space weight
  as the 1px outline of every 1x sprite, which keeps the silhouettes crisp
  in-engine), and `Figure.rim_dark` adds a darker inner rim on the shadow
  side; `Part.contour_dirs` draws interior contours only on a part's shadow
  side.
- **Effects** (`kit.fx_*`): dust puffs, sparks, speed lines and impact
  flashes in design coordinates; post-pass effects never touch the 1px
  border (`Figure.post_margin`).
- **Stoneback's ball** is a small 3D projection: plates are wedges around the
  true rolling axis and the moss ridge runs along the spine, so the ball can
  roll toward the camera, away, or sideways (with the tail club as the hub);
  one roll phase step = one third of a plate, so 3 frames loop seamlessly.

## Outputs

| folder | sheets |
| --- | --- |
| `assets/sprites/characters/` | explorer, hesper, corin, villager_farmer, villager_baker, sigilbinder, crowd, crowd_back |
| `assets/sprites/kith/` | emberlyn (2x), stoneback (2x), mossling, lanternmoth |
| `assets/sprites/props/` | training_totem (2x) |
| `assets/sprites/portraits/` | portrait_hesper, portrait_corin, portrait_player, portrait_emberlyn |

Kith battle set (Emberlyn and Stoneback, all of `_s/_n/_e`): `ready` (battle
stance, 6 frames, loops; the calmer `idle` stays for the overworld),
`dash_windup` (2, 12 fps), `dash` (3, 18 fps, loops), `dash_land` (3, 14 fps),
`ram` (2, 16 fps), plus Stoneback's `roll_s`.

Ground shadows are not baked in (the engine places blob shadows under
billboards); glow light is baked only onto the sprite's own pixels.
