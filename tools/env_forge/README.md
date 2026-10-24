# env_forge

Procedural pixel-art generator for Wildbound's environment textures, foliage, props, VFX and UI.
Everything is drawn from the shared master palette (`tools/common/palette.py`) and animated
things are written with the shared sheet contract (`tools/common/sheet.py`).

```
python3 tools/env_forge/build.py              # regenerate everything + validate + previews
python3 tools/env_forge/build.py fx ui        # only some groups (textures, foliage, props, fx, ui)
python3 tools/env_forge/build.py --clean      # delete our known outputs first, then rebuild
python3 tools/env_forge/build.py --check      # validate the files on disk only
python3 tools/env_forge/textures.py grass_a   # any module can rebuild single assets by name
```

Requires Python 3 + Pillow + numpy. Output is deterministic (seeded per asset name).

## Modules

| file | contents |
|---|---|
| `kit.py` | palette access + reverse lookup, periodic value/spectral noise, Voronoi, Poisson-disc, ordered dither, height-map lighting, masks/strokes, selective outline pass, preview writers |
| `textures.py` | A: 48x48 (water 64x64) seamless textures -> `assets/environments/textures/` |
| `foliage.py` | B: trees (canopy "sphere of leaf clusters" renderer), bushes, ferns, reeds, tufts, flowers, mushrooms, rocks, stump, kindlemoss, lily pad, hollow log -> `assets/environments/foliage/` |
| `props.py` | C: props and the banner / campfire / brazier sheets -> `assets/environments/props/` |
| `mural.py` | C: `mural_dawncrane` + `_glow`, a carved relief built from an integer height field |
| `fx.py` | D: VFX sheets -> `assets/effects/` |
| `ui.py` | E: icons -> `assets/ui/icons/`, 9-slice panels, reticle, cursor -> `assets/ui/panels/` |
| `build.py` | runs everything and validates sizes, palette membership, alpha rules, borders, manifests |

## Conventions

* 24 texels per meter. Light from the upper-left. Sprites/icons get a 1px outline in the darkest
  shade of the adjacent material's ramp (`kit.outline`); textures have no outlines.
* Single sprites: plain PNG, pivot = bottom-centre, 1px transparent border, alpha 0/255.
* Prop sheets (banner, campfire, brazier): alpha 0/255. VFX sheets: alpha in quarter steps,
  composited with a palette-preserving "over" so every visible pixel is a palette colour.
* Ground VFX are top-down with their forward direction along +X; pivot = frame centre.
* 9-slice panels keep ornament in the corners; edge segments are constant along their length.
* Previews (4x zoom, 3x3 texture tiling, contact sheets) go to `tools/env_forge/previews/`
  (gitignored).

## VFX pivots

| sheet | frame | pivot | notes |
|---|---|---|---|
| hit_spark | 32x32 | (16,16) | centre |
| hit_heavy | 64x64 | (32,32) | centre |
| dust_puff | 24x24 | (12,23) | bottom-centre |
| stun_stars | 32x16 | (16,8) | centre, float above the head |
| ember_bolt | 32x16 | (16,8) | centre, faces +X |
| ember_impact | 32x32 | (16,16) | centre |
| flash_strike | 48x48 | (24,24) | centre |
| fire_pillar | 32x48 | (16,47) | bottom-centre |
| burn_flame | 16x16 | (8,15) | bottom-centre |
| boulder | 32x32 | (16,16) | centre, rolls clockwise (toward +X) |
| rock_burst | 48x48 | (24,47) | bottom-centre |
| fault_spike | 32x48 | (16,47) | bottom-centre |
| stone_guard | 64x64 | (32,60) | dome base |
| focus_aura | 48x64 | (24,60) | feet |
| perfect_flash | 64x64 | (32,32) | centre |
| guard_break | 48x48 | (24,24) | centre |
| ko_burst | 64x64 | (32,32) | centre |
| trust_motes | 16x16 | (8,8) | centre |
| sigil_glow | 32x32 | (16,16) | centre |
| emotes | 16x16 | (8,15) | bottom-centre |
| cinder_arc, heat_ring, shockwave | 96x96 | (48,48) | ground, top-down |
| ground_crack | 64x64 | (32,32) | ground decal |
| scorch | 48x48 | (24,24) | ground decal |
