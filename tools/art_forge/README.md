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
```

Useful flags:

- `--dry-run` prints the request without sending it.
- `--force` regenerates even when the exact request is cached.
- `--background transparent` works on models that support it.
- `--quality` and `--resolution` are passed through when the model accepts them.

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
   stays the same.
4. **Review.** `review` puts each painting next to its pixelized result at
   game size. Judge the pixelized result: that is what ships.
5. **Install.** `pixelize --out assets/...` writes the sprite into its
   frame (feet on the pivot row, 1px transparent border). It also records the
   prompt, model, parameters and source in `tools/art_forge/provenance/`.
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

## Tests

```
python3 -m unittest discover -s tools/art_forge -p "test_*.py"
```

The tests repaint a known sprite the way an image model would: enlarged on
an uneven 11.5× grid, blurred, with noise, on magenta. `pixelize` must
recover the original pixels. The tests also check that only palette colours
and binary alpha come out, that the border and outline rules hold, and that
background colour never bleeds into the edges.
