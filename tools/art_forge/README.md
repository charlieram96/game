# art_forge

Generated art for Wildbound through the [OpenRouter](https://openrouter.ai)
Image API, turned into clean, palette-locked pixel art that matches the
procedural sprites from `sprite_forge` and `env_forge`.

Image models paint about 1024 px images that only imitate pixel art: soft
block edges, an uneven "pixel" grid, off-palette colours. `pixelize.py`
rebuilds real pixel art from them. It keys out the background and crops to
the subject. It resamples on a grid aligned to the painting's own pixels,
where each cell takes its most common palette colour. It snaps colours to
the master palette (`tools/common/palette.py`), optionally limited to the
character's own ramps. Alpha is binary, and stray pixels and background
spill are removed. An optional outline uses the same rule as the sprite
forge: the darkest shade of the neighbouring ramp, never pure black.

## Setup

The client reads the key from the `OPENROUTER_API_KEY` environment variable.
Add it to the environment's secrets or variables, never to the repository or
a chat. It is sent only in the request header, and nothing writes or prints
it. Listing models needs no key.

Requires Python 3 with Pillow and numpy (the same as the other forges).

## Commands

```
python3 tools/art_forge/forge.py models                         # image models: batch size, references, options
python3 tools/art_forge/forge.py prompt emberlyn --view e       # the composed prompt
python3 tools/art_forge/forge.py gen emberlyn --view e --count 4
python3 tools/art_forge/forge.py gen emberlyn --view n --ref <approved_side_view.png>
python3 tools/art_forge/forge.py gen hesper_portrait --expr stern --ref <approved_neutral.png>
python3 tools/art_forge/forge.py bakeoff emberlyn --models google/gemini-3-pro-image,openai/gpt-5.4-image-2,black-forest-labs/flux-3-image
python3 tools/art_forge/forge.py review emberlyn                # tools/art_forge/_out/emberlyn/review.png
python3 tools/art_forge/forge.py pixelize <candidate.png> --brief emberlyn --out assets/...png
python3 tools/art_forge/forge.py composite <neutral.png> <smile.png> --face 300,360,690,700   # -> smile.composite.png
python3 tools/art_forge/forge.py pixelize <smile.composite.png> --brief hesper_portrait --out assets/sprites/portraits/portrait_hesper.png --frame 1
python3 tools/art_forge/forge.py pixelize <scene.png> --brief title_keyart --out export/web/keyart.png   # opaque brief
```

Useful flags:

- `--dry-run` prints the request without sending it.
- `--force` regenerates even when the exact request is cached.
- `--background transparent` works on models that support it.
- `--quality` and `--resolution` are passed through when the model accepts them.
- `pixelize --frame N` installs the result as frame N of a one-row sheet at
  `--out`, keeping its other frames (a sheet with another frame size is
  started afresh). Its provenance record lists every frame.
- `pixelize --despeckle` (default for briefs with `"despeckle": true`)
  replaces tiny low-contrast specks of a stray ramp, such as gold flecks in
  grey hair. Catchlights and accents stand out in brightness and stay.
- `pixelize --opaque` (default for briefs with `"opaque": true`) treats the
  picture as a whole scene: nothing is keyed out, it is centre-cropped to the
  brief's `size` and saved as a palette PNG with no border.

Every request is checked against the model's published parameters before it
is sent.

## Workflow

1. **Pick models.** Run a bake-off for one brief of each kind (a kith sprite,
   a portrait, an environment) and keep the models whose pixelized results
   look best. Set them as the defaults in `briefs.json` under `kinds`.
2. **Lock each design.** Generate a `concept` sheet or a strong `s` view.
   Pick one and keep it as the reference.
3. **Derive everything else from it.** Pass the approved image as `--ref`
   for the other views (`n`, `e`) and portrait expressions, so the design
   stays the same. For portraits, `composite` then blends only the face of
   each expression into the locked neutral painting (registered by scale and
   shift, colour-matched), so hair, clothes and outline stay pixel-identical
   across the sheet and only the face changes. Its sidecar records both
   generations and the face regions.
4. **Review.** `review` puts each painting next to its pixelized result at
   game size. Judge the pixelized result: that is what ships.
5. **Install.** `pixelize --out assets/...` writes the sprite into its
   frame (feet on the pivot row, 1px transparent border). It also records the
   prompt, model, parameters and source in `tools/art_forge/provenance/`.
   Note any hand clean-up after installing in the record's `cleanup` list.
6. **Animate.** The game's sheets need idle, walk, dash and cast frames per
   direction. Two routes:
   - Retune the `sprite_forge` rigs (colours, proportions, silhouettes) to
     match the approved design. This route is reliable.
   - Generate pose frames with the approved sprite as a reference, then check
     them for consistency frame by frame. This route is experimental.

   Run `python3 tools/sprite_forge/validate.py` on any sheet that changes.

Candidates and review sheets live in `tools/art_forge/_out/` (gitignored).
Only curated, pixelized results and their provenance records are committed.

## Originality rules

- Prompts describe designs in our own words and never name existing games,
  franchises, studios or characters. Every prompt ends with the originality
  clause in `briefs.json`.
- Before installing a design, check that it doesn't look like an existing
  character or creature. If it does, regenerate or redesign.
- Keep the provenance record for every installed asset.

## Briefs

`briefs.json` holds the following:

- **`kinds`**: one shared style per kind of image, with its default aspect
  ratio and model. The kinds are sprite, portrait, prop, concept,
  environment and keyart.
- **`views`**: the three sprite directions (`s`, `n`, `e`). West is the
  engine's mirror of east.
- **`briefs`**: one entry per character, kith, prop or place. Each has a
  `subject`, plus a target `size`, `pivot` and palette `ramps` where the
  result goes into the game. The current colours and silhouettes come from
  the existing sprites, so new art fits beside old.

## Installed art

- **Dialogue portraits** (`assets/sprites/portraits/portrait_*`, briefs
  `wren_portrait`, `hesper_portrait`, `corin_portrait`, `emberlyn_portrait`):
  128x128 frames at 2x (48 px per unit, pivot 64,126), one frame per
  expression in a row, painted by `openai/gpt-image-2`. It won a bake-off
  against `google/gemini-3-pro-image` and `bytedance-seed/seedream-4.5`: it
  paints a near-even 7-8 px grid at 1024 px, about 128 cells across, so it
  pixelizes to 128 cleanly. It also kept the flat backdrop and the
  established designs best, and cost the least. Each neutral was locked with
  the old procedural portrait (softened) as a reference, and the expressions
  were made with `--ref` and `composite`. `tools/sprite_forge/build.py`
  leaves these sheets alone.
- **Web loading key art** (`export/web/keyart.png`, brief `title_keyart`):
  480x270, opaque, palette PNG, shown behind the loading text by
  `export/web/shell.html` and copied next to `index.html` by
  `tools/package_web.py`.

## Tests

```
python3 -m unittest discover -s tools/art_forge -p "test_*.py"
```

The tests repaint a known sprite the way an image model would: enlarged on
an uneven 11.5× grid, blurred, with noise, on magenta. `pixelize` must
recover the original pixels. The tests also check that only palette colours
and binary alpha come out, that the border and outline rules hold, and that
background colour never bleeds into the edges.
