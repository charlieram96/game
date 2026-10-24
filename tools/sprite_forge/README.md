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

Requires Python 3 + Pillow + numpy. A full build takes a couple of seconds.
Review images go to `tools/sprite_forge/previews/` (gitignored).

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
   fps/loop where specified, frame size, pivot, 24 px/unit, binary alpha,
   1px transparent border and non-empty frames for every sheet.

Conventions: light from the upper-left; `_s` faces the camera, `_n` away,
`_e` right (west = engine mirror of `_e`); feet/paws rest on the pivot row
(their outline lands on it) in every frame; directions are 3/4 top-down.

## Outputs

| folder | sheets |
| --- | --- |
| `assets/sprites/characters/` | explorer, hesper, corin, villager_farmer, villager_baker, sigilbinder, crowd, crowd_back |
| `assets/sprites/kith/` | emberlyn, stoneback, mossling, lanternmoth |
| `assets/sprites/props/` | training_totem |
| `assets/sprites/portraits/` | portrait_hesper, portrait_corin, portrait_player, portrait_emberlyn |

Ground shadows are not baked in (the engine places blob shadows under
billboards); glow light is baked only onto the sprite's own pixels.
