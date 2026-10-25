# Architecture

## Stack (exact versions used to build v0)

| Tool | Version | Use |
| --- | --- | --- |
| Godot | 4.7.2 stable (official build `ed1daf0bf`) | Engine, typed GDScript, GL Compatibility renderer (chosen for web and mobile reach) |
| Python | 3.13 | Asset generators (`tools/*_forge`) |
| Pillow / numpy | 12.3.0 / 2.5.3 | Image and audio synthesis in the forges |

There are no other runtime dependencies. The backend technologies in the
brief (ENet dedicated server, PostgreSQL, Redis, a Go or TypeScript
backend, Docker) are **Planned** and not part of v0. Build and export
instructions are in the top-level README.

## Layout

```
project.godot        autoloads, input defaults, shader globals, renderer settings
scenes/              boot, title (ui), world (mossford), combat (battle), dev previews
scripts/
  core/              autoloads: Events, Settings, Audio, Game; input setup; boot
  combat/            the pure battle simulation
    movement/ dash/ stamina/ abilities/ (+components/) damage/ states/
    ai/              CombatAI, AIProfile, TrainingAI (InputSources)
    view/            presentation of a battle: camera, arena, fighters, VFX, tutorial
  creatures/         data classes: CreatureDefinition, AbilityDefinition, profiles,
                     HitSpec, AbilityVariant, CreatureInstance, the Registry autoload
  progression/       Leveling, Mastery, BattleRuleset, StatCalculator, CombatStats
  networking/        InputSource, LocalInputSource, ReplayInputSource,
                     BattleTransport, LocalBattleTransport
  persistence/       PlayerProfile, SaveService (autoload)
  presentation/      shared HD-2D kit: PixelSprite3D, SpriteSheet, EnvKit, LightingRig, PostFX
  world/             explorer, NPCs, interactables, camera, companion, wild roamer,
                     region builder, story/chapter_one.gd
  ui/                theme, HUDs, touch controls, dialogue, menus, journal
resources/           creatures/, abilities/, status/, balance/ (element chart), dialogue/
shaders/             pixel sprite, world, terrain, water, telegraph, arena (floor, stone,
                     ground, depth of field, fire, cloth), post (tilt-shift, grade), ...
assets/              generated sprites, environments, effects, UI, audio; Pixelify Sans font
tests/               unit/, integration/, tools/balance_sim.gd, runner scene
tools/               sprite_forge/, env_forge/, audio_forge/, common/, run_tests.sh
docs/                these documents
```

## Layers

```
 Godot Input / touch / gamepad          CombatAI          (future) network peer
            |                               |                     |
     LocalInputSource                       |              RemoteInputSource (Planned)
            \______________ InputSource ____/_____________________/
                                 |  one InputCommand per team per tick
                          BattleTransport  (LocalBattleTransport in v0)
                                 |
                            BattleSim  -- pure RefCounted logic, no nodes, no Input,
                                 |        systems: movement, dash, stamina, abilities,
                                 |        damage/guard/stun/status; FighterSM table
                                 |  BattleEvents (+ readable state)
                                 v
          BattleView / FighterView / HUD / audio  -- cosmetic only, interpolated
```

* **Simulation and presentation are separate.** `BattleSim` and its
  systems are plain `RefCounted` classes. They never touch nodes, `Input`
  or time, and they run identically inside the battle scene, a headless test
  or a future dedicated server. The view reads sim state every frame,
  interpolating between ticks, and reacts to `BattleEvent`s (hit, stun,
  block, KO, ...) for VFX, SFX, popups and shake.
* **Rules live in systems, not in one big script.** `BattleSim` owns only
  the tick order and the match flow. Movement, dash, stamina, guard, stun,
  status, damage and ability logic each live in their own file. Abilities
  are composed from reusable components.
* **Game layer:** the `Game` autoload routes scenes (with fades), builds
  `BattleSetup`s for each mode, hands them to the battle scene and applies
  progression afterwards. The world and story layer never reaches into the
  sim. It starts battles and reacts to their results.

**Autoloads:**

| Autoload | Role |
| --- | --- |
| `Events` | Global signal bus |
| `Settings` | Persisted player settings |
| `Registry` | Species registry |
| `SaveService` | Profile load/save |
| `Audio` | SFX pool, loops, music crossfades |
| `Game` | Flow and rewards |

## Data-driven content

* Species, abilities, statuses and the element chart are `.tres` resources
  (see kith.md). Balancing means editing data, not code. Every v0 creature
  and ability was tuned this way with the balance harness.
* Immutable definitions (`CreatureDefinition`, `AbilityDefinition`) are
  separate from individual creatures (`CreatureInstance`). `StatCalculator`
  derives per-battle `CombatStats` from both plus a `BattleRuleset`.
* Mastery variants are data overrides applied copy-on-write along property
  paths, e.g. `{"components/0/speed": 22.0}`.
* Dialogue is JSON (`resources/dialogue/chapter1.json`), keyed by id, with
  speakers, portrait expressions, choices with ids and replies, and a
  `{player}` token.
* The region layout and anchor points live in
  `scripts/world/mossford_builder.gd`, and art comes from `assets/`.

## Input commands and transports

* `InputCommand` is the only thing a client would ever send: tick, sequence
  number, 8-way move index, quantized aim and aim distance, held and pressed
  bit masks, and an axis hint. It encodes to **16 bytes**. Aim is quantized
  to 1/4096 of a turn so the client and server see the same value. A unit
  test checks the encode/decode round trip.
* `InputSource` produces one command per tick per team. Implementations:
  local device (keyboard, mouse, gamepad and touch, with presses latched
  between ticks), `CombatAI`, `TrainingAI` and `ReplayInputSource`.
* `BattleTransport` decides where the authoritative sim runs.
  `LocalBattleTransport` (v0) steps it in-process and stamps sequence
  numbers exactly as a server would expect. It can record every command for
  replays.

## Determinism

* Fixed tick and fixed tick order, with seeded RNG only. The AI owns a
  seeded `RandomNumberGenerator`, and the sim itself uses no randomness.
  Two-phase hit resolution removes update-order bias in trades.
* `BattleSim.state_hash()` digests every fighter snapshot and live volume.
  `test_same_inputs_same_result` replays identical input streams and
  compares hashes, and rematches use `reset()` to rebuild the identical
  starting state.
* This is same-binary determinism. Cross-platform float determinism has
  **not** been verified. The online plan relies on server authority plus
  reconciliation, not on lockstep.

## Networking roadmap

| Phase | Scope (from the brief) | Status |
| --- | --- | --- |
| **A. Local simulation** | Full combat loop vs AI, fixed tick, structured input commands, transport abstraction | **Done in v0** (plus local versus) |
| **B. Online 1v1** | Headless Godot dedicated battle server over ENet. Input sequence numbers, 60 Hz server ticks, authoritative snapshots at a configurable ~15-20 Hz, client-side prediction of the local creature, server reconciliation, remote interpolation, event ids for damage and stuns, disconnect handling. Test under simulated latency and packet loss. | **Planned.** The sim, commands and sequence numbers are ready for it, and a `NetworkBattleTransport` would replace the local one without changing the view. |
| **C. Shared world** | Zone servers, local player visibility, interest management, transfers into battle instances | **Planned** |
| **D. Persistence** | Accounts, creature ownership, progression, inventory, transactional match rewards. PostgreSQL for persistent data, Redis for ephemeral sessions and matchmaking. | **Planned.** `PlayerProfile.to_dict()` is the intended schema. |

**Authority rule for B-D:** the server decides positions, dash direction and
stamina, Surge, attack legality, hits, damage, stuns, outcomes, XP and
rewards. It never trusts client-provided inventory, XP, damage or results.

## Rendering (HD-2D)

* **Sprites:** `PixelSprite3D` is an upright, Y-axis billboard quad with a
  pixel-art shader. "Smooth pixel" sampling keeps texels crisp at any scale
  and anti-aliases texel edges by one screen pixel, so pixels don't
  shimmer (when a texel is smaller than a pixel it takes a plain bilinear
  tap). The shader also does hit flash, outline glow, dithered dissolve,
  auto-emission for the brightest pixels (embers, lanterns, eyes) and wind
  sway. A height stretch of
  1/cos(camera pitch) keeps sprites from looking squashed. In the overworld,
  foliage between the camera and the explorer dithers out
  (shader globals `occluder_*`).
* **Sprite lighting:** a sheet with a normal map (the HD sheets) is lit
  through it by the sun and every point light: each texel has its own
  screen-aligned normal, a wrap term keeps the painted shading readable on
  the dark side, and a rim light picks out the silhouette's edges on the
  side facing a light (brightest for lights behind the sprite, such as a
  brazier). The normal map's alpha marks what glows (flames, lanterns,
  eyes), so only those pixels bloom. In the shadow pass the card keeps the
  main camera's orientation (`MAIN_CAM_INV_VIEW_MATRIX`), so a sprite that
  casts shadows casts the silhouette that is on screen and never shadows
  itself. Sheets without a normal map are lit as before.
* **Sprite sheet contract:** a PNG plus a JSON manifest with frame size,
  columns, pivot (feet), pixels per unit (24 for the procedural sheets, 112
  for the HD sheets), and animations as `<name>_<dir>` with directions
  `s` / `n` / `e` (west mirrors east). Each animation has frame lists, fps
  and a loop flag. Optional: `normal_map` (a PNG in the sheet's layout) and
  `lighting` (the sheet's shade floor and rim strength).
* **World:** a triplanar pixel-textured world shader, splat-mapped terrain,
  MultiMesh foliage, water, blob shadows, directional sun shadows, and
  lighting presets (morning, day, golden, dusk, night) with fog and glow.
* **Battle arena (HD-2D diorama):** `ArenaBuilder` builds the board as real
  geometry with `ArenaMesh`: one beveled flagstone per cell (the joints are
  the cell lines; stone tops stay below 4 mm so the dash lanes at 26 mm and
  the telegraphs always draw over them), a flush rim, steps down to a paved
  lower ring, the back wall with banners and torches, corner pillars with
  braziers, tripod braziers and banner poles on the side rings, tiered
  stands with a MultiMesh crowd, the front row's backs, trees. Textures are
  48 texels per unit (`tools/env_forge/arena_hd.py`; the banners come from
  `tools/art_forge`), mip-mapped at load. Every static piece sharing a
  material is merged into one mesh: a battle's 3D view is about 70 draw
  calls with the creatures and trainers, the only shadowed light is the sun.
  `shaders/arena_floor` (stones, inlay, scorch, highlights, contact shadows,
  cloud shadows), `arena_stone` (triplanar pieces with floor-contact AO),
  `arena_ground` (paving and lawn with footprint AO), `arena_dof` (below).
  `test_arena_builder.gd` checks the stone heights, the joints, that nothing
  but the standing stones rises inside the board, and the draw-call budget.
* **Battle light:** the `arena_golden` / `arena_day` presets: a low warm sun
  (31-38 deg) from the west-south-west with soft shadows in one orthographic
  map fitted to the battle camera, a cool shadowless sky fill from the other
  side, flickering brazier, torch and lantern omni lights (no shadows; four
  of them on low graphics), glow on flames and emissive pixels, depth fog
  past the stands, a filmic tonemap.
* **Post:** on high graphics the battle's tilt-shift is `arena_dof`, a
  depth-aware pass drawn right after the opaque geometry: it rebuilds each
  pixel's world position and keeps everything over the board (and its rim,
  steps and back wall) sharp, blurring the stands behind and the front row
  in front with a 16-tap gather that never smears sharp things. Transparent
  effects draw over it, sharp. On low graphics the screen pass blurs above
  and below the board's rows on screen instead (cheap, mip-based). The
  screen pass (`post_hd2d`) also grades (S-curve, split toning, vignette,
  grain, slight corner fringing) and adds god rays from the upper left.
  Tilt-shift can be turned off in Settings.
* **Cameras:** battle is a fixed perspective camera, 48 deg pitch and a
  25 deg vertical field of view, framed by bisection on its distance so the
  board's floor is as large as possible between the HUD bands at any aspect
  ratio (side insets keep it clear of the touch buttons; the back row is
  about 0.77 the width of the front row). `ground_point()` is the exact
  inverse of the projection at the rest pose (`test_battle_camera.gd`). Shake
  is a translation; kicks and zoom punches (a field-of-view squeeze) are
  added on top of the rest pose and never move the aimed cell. The
  overworld is a perspective follow camera at a 32 deg pitch, distance 23,
  FOV 30, with cutscene focus points.

## Tests

Run all tests headless (it imports first so new `class_name` scripts are
registered):

```
tools/run_tests.sh            # everything
tools/run_tests.sh dash       # only tests whose "file.method" contains "dash"
```

The runner is a scene (`tests/run_tests.tscn`) so autoloads exist. Tests
extend `WBTestCase`, and `tests/sim_helpers.gd` builds sims and scripted
inputs. The current suite has **92 tests** (76 unit, 16 integration), and all
pass as of 2026-10-24.

Coverage of the 20 test categories required by the brief:

| # | Required | Where |
| --- | --- | --- |
| 1 | Eight-direction walking | `test_movement.test_walks_in_all_eight_directions` |
| 2 | Normalized diagonal speed | `test_movement.test_diagonal_speed_is_normalized`, `test_input_command.test_eight_way_vectors_are_unit_length` |
| 3 | Strict four-direction dashing | `test_dash.test_dash_is_always_cardinal`, `..._pure_dash_displacement_has_no_diagonal_component` |
| 4 | Dash tie-breaking | `test_dash.test_tie_break_rules`, `..._dash_without_input_uses_last_cardinal_facing` |
| 5 | Stamina consumption | `test_dash.test_stamina_cost_and_insufficient_stamina`, `test_stamina_focus.test_stamina_never_exceeds_maximum` |
| 6 | Focus-only regeneration | `test_stamina_focus.test_stamina_does_not_regenerate_without_focus`, `..._focus_regenerates_and_has_commitment`, `..._focus_blocks_movement_attacks_and_dash` |
| 7 | Different recovery rates | `test_stamina_focus.test_recovery_rates_differ_by_creature`, `..._quickfoot_passive_shortens_focus_commitment` |
| 8 | Focus interruption | `test_stamina_focus.test_damage_interrupts_focus`, `..._burn_ticks_interrupt_focus` |
| 9 | Dash-through detection | `test_dash.test_dash_through_stuns_and_grants_immunity`, `..._dash_through_detects_at_extreme_speed`, `..._one_stun_per_dash_per_opponent` |
| 10 | Dash-through landing | `test_dash.test_landing_is_about_one_cell_beyond_and_never_overlapping`, `..._landing_blocked_by_wall_finds_safe_spot`, `..._landing_blocked_by_stone_never_clips` |
| 11 | Boundaries and obstacles | `test_movement.test_cannot_leave_arena_bounds`, `..._obstacles_block_walking`, `..._box_obstacle_sweep_is_exact`, `test_dash.test_dash_stops_at_walls`, `test_abilities.test_projectiles_are_blocked_by_stones` |
| 12 | Stun duration and immunity | `test_stun_and_states.*` (exact duration, chained diminishing returns and Steadfast, wake-up grace, guard break, perfect guard), `test_dash.test_dash_through_never_guarantees_a_follow_up` |
| 13 | Attack costs (Surge, no cooldowns) | `test_abilities.test_specials_cost_surge_and_have_no_cooldown`, `..._hits_rams_and_dashes_fill_surge` |
| 14 | Ability hit detection | `test_abilities.*`: one test per special, plus strings, variants and the FAST-dash evade |
| 15 | Knockouts | `test_ko_and_match.test_knockout_ends_battle_with_winner`, `..._knocked_out_creature_ignores_input`, `..._timeout_decides_by_health_ratio` |
| 16 | AI behaviour | `test_ai.*`: beats a passive foe, AI-vs-AI completes, focuses when empty, uses its whole kit, hard AI dodges projectiles |
| 17 | Ranked normalization | `test_progression.test_ranked_normalizes_levels`, `..._identity_preserved_under_normalization`, `..._mastery_bonus_never_applies_in_ranked`, `..._casual_and_pve_use_real_levels` |
| 18 | Save/load | `test_save_load.*` (round trip, reload, corrupt file rejected, untrusted values clamped), `test_progression.test_creature_instance_round_trip`, `..._from_dict_rejects_out_of_range_values` |
| 19 | Restart and rematch | `test_ko_and_match.test_reset_restores_starting_state_for_rematch`, `..._same_inputs_same_result` |
| 20 | Mobile HUD scaling | `test_hud_scaling.test_hud_layout_at_aspect_ratios` (16:9, 19.5:9, 20:9, 16:10, 4:3), `..._touch_controls_fit_and_are_large_enough` |

Additional tests:

* Every script compiles and every shader loads (`test_scripts_compile`).
* The state transition table rejects illegal moves.
* A buffered input fires on the first free tick.
* Team switching rules.
* Mastery variants don't mutate their base resource.
* Leveling curve and cap, and mastery from battle usage.
* Keyboard input drives the player creature in the real battle scene.
* **An end-to-end Chapter 1 playthrough** (`test_story_flow`) runs in the
  real world scene with dialogue auto-advanced and battles reported as won.
  It checks every story step, flag, the party, the journal and the save.

## Balance harness

```
N=40 godot --headless --path . -s res://tests/tools/balance_sim.gd
ONLY=easy-story N=150 godot --headless --path . -s res://tests/tools/balance_sim.gd
```

The harness runs N AI-vs-AI matches per pairing (Ranked level 50, the
Ringstones, 120 s limit, fixed seeds) and prints win rates, average length,
timeouts, damage, Surge earned and spent, rams and per-ability hit rates.
`ONLY=<ai>-<ai>` restricts it to pairings with those two AI profiles.
Results measured on 2026-10-25 on the 20 x 12 board with board-aligned
attacks and Surge (n = 150 per row; wins are listed as team 0 / team 1 /
draw; Surge per match is team 0 / team 1):

| Pairing (AI profile) | Wins | Avg length | Timeouts | Surge earned | Stages spent |
| --- | --- | --- | --- | --- | --- |
| Emberlyn (normal) vs Stoneback (normal) | 70 / 80 / 0 | 32.2 s | 15 | 1159 / 407 | 10.0 / 2.8 |
| Stoneback (normal) vs Emberlyn (normal) | 76 / 74 / 0 | 29.7 s | 11 | 411 / 1168 | 3.0 / 10.0 |
| Emberlyn vs Emberlyn (normal) | 67 / 83 / 0 | 20.2 s | 7 | 603 / 630 | 4.7 / 5.0 |
| Stoneback vs Stoneback (normal) | 70 / 80 / 0 | 42.3 s | 4 | 783 / 773 | 6.5 / 6.4 |
| Emberlyn (normal) vs Stoneback (story) | 128 / 22 / 0 | 25.3 s | 4 | 1229 / 325 | 10.7 / 2.4 |
| Emberlyn (easy) vs Stoneback (story) | 37 / 113 / 0 | 24.4 s | 3 | 985 / 421 | 8.3 / 3.2 |

How to read it:

* Across both sides Emberlyn beats Stoneback **48%** of the time (144 of
  300): 47% from the left spawn and 49% from the right. Getting there took
  Quickfoot's +45% Surge (Emberlyn hits fast but light and lives on its
  specials), Stoneback's HP from 170 to 155 and a softer Shell Bash. A
  Stoneback spends about 3 stages a match (mostly Ground Pound), an
  Emberlyn about 10.
* Both mirrors are within noise. The Stoneback mirror is the longest
  (42 s), and only 4 of its 150 matches time out (it was 39 before the AI
  learned to break stand-offs).
* An Easy-profile Emberlyn, standing in for a weak player, beats story Corin
  25% of the time; a Normal-profile one 85%. The story duel also offers a
  "go a little easier" retry that switches Corin to the Easy profile.
* The AIs rarely reach their 4-stage moves (Heat Ring about once every
  eight matches, Fault Line almost never); human players save up on
  purpose.

These are AI proxies, not human playtests.

## Asset pipeline

All audio and most art is generated from code. There are no source art
files, no samples and no borrowed melodies. Builds are deterministic (seeded
per asset name), and each forge validates its own output. The exceptions are
the HD character and kith sheets, the dialogue portraits and the web loading
key art: image-model paintings rebuilt as palette-locked pixel art by
`tools/art_forge`, each with a provenance record.

| Forge | Produces | Command |
| --- | --- | --- |
| `tools/sprite_forge` | The crowd, plus procedural fallbacks for the characters, kith, totem and portraits (shaded volumetric parts, rigs per character family, 1 px material outlines, binary alpha); it never writes over a sheet art_forge installed | `python3 tools/sprite_forge/build.py` |
| `tools/env_forge` | 48x48 seamless textures, foliage, props, the Dawncrane mural, VFX sheets, UI icons and 9-slice panels | `python3 tools/env_forge/build.py` |
| `tools/audio_forge` | 89 SFX (44.1 kHz mono) and 6 music cues (32 kHz mono; loops carry `smpl` loop points and are rendered circularly) | `python3 tools/audio_forge/build.py` |

`tools/art_forge` adds generated art through the OpenRouter Image API. It
writes prompts from the briefs in `briefs.json`, checks each request against
the model's published parameters and records provenance. `pixelize.py` turns
the paintings into palette-locked pixel art in the same sheet contract. It
made the HD sheets of the kith, the people and the training totem (112 px
per unit, each with a normal map: key poses painted per view, then
registered, in-betweened and normal-mapped by `animate.py`), the 128x128
dialogue portraits (`assets/sprites/portraits/`) and the web loading key art
(`export/web/keyart.png`). The API key is read from `OPENROUTER_API_KEY` and
never stored. See its README.

Shared palette and sheet-contract code is in `tools/common/`. See each
forge's README for details. The music is stored as WAV in the repository;
exports compress it to QOA at import time, so the whole web download is
about 15 MB (`tools/package_web.py` also gzips the engine and data).

## Not yet tested (no claims)

* **No performance numbers are claimed.** The 60 FPS target has not been
  profiled on real phones, low-end PCs or browsers. Development rendering
  ran under a software rasterizer (Xvfb and llvmpipe) for screenshots only.
* **No multiplayer capacity is claimed.** There is no online code yet, so
  latency, packet loss and server load have not been tested.
* Touch controls are layout-tested (sizes, aspect ratios) and work with a
  simulated touch mouse. Hands-on testing on real devices is still to do.
* Balance figures come from AI-vs-AI runs, not human play.
