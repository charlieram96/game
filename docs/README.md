# Wildbound - design documentation

Wildbound (working title, not trademark-checked) is an original HD-2D
creature action RPG. You play an apprentice Warden in the village of
Mossford, where people and the wild creatures called **kith** once lived side
by side under a promise called the Accord. Kith are never captured: a Warden
earns a kith's trust through patience, observation and care, then fights
*beside* it in real-time arena duels in which the player steers the creature
directly. Combat is a precise top-down action game (mechanically inspired by
the Flash-era arena game Nindou, nothing else borrowed): smooth 8-way movement,
strictly 4-way dashes that can pass *through* an opponent to daze it, stamina
that only comes back while you hold Focus, and telegraphed abilities with real
frame data. Exploration is a lit 3D storybook diorama with pixel-art
characters, in the spirit of HD-2D.

All names, characters, art, sound and music in the project are original. Art
and audio are generated from code (see `tools/*_forge`); the font is Pixelify
Sans (SIL Open Font License).

## Documents

| Document | Contents |
| --- | --- |
| [story-and-world.md](story-and-world.md) | Theme and tone, lore, the Mossford region, the Chapter 1 beat sheet as implemented, characters, hooks for later chapters |
| [kith.md](kith.md) | Creature design: stats, movement/dash/stamina profiles, passives, full frame data for every ability, mastery variants, trust-based befriending |
| [combat.md](combat.md) | Arena combat rules: tick model, movement, dash and dash-through, Focus, guard, hit resolution, stun protection, statuses, elements, state machine, input buffer, AI, tutorial, game feel |
| [progression-and-rulesets.md](progression-and-rulesets.md) | Levels 1-100, ability mastery 1-10, Ranked / Casual / PvE rulesets, stat formulas, saves, server authority |
| [architecture.md](architecture.md) | Project layout, simulation vs presentation, data-driven resources, input commands and transports, determinism, networking roadmap, tests, balance harness, asset pipeline |
| [roadmap.md](roadmap.md) | Milestone status against the original brief, known gaps, next steps |

## v0 scope

The v0 build is a proof of concept meant to be shared with friends: the
tutorial, the first story chapter and an arena.

**Playable now**

* Title screen: Continue, New Journey, Free Battle (Emberlyn or Stoneback vs
  an AI on Easy / Normal / Hard), Dash Training (the training-yard tutorial on
  its own), Local Versus (two players on one keyboard), Settings, How to Play.
* Chapter 1, "The Kindling": the Mossford region (village, stream and bridge,
  the Glimmerwood, north meadow and pond, training yard, the Ringstones, the
  Dawn Shrine) with a morning-to-night progression.
* One trust-based befriending (the wild Emberlyn), an optional Mossling
  observation, and a field journal.
* A 7-step combat tutorial against a training totem.
* The story duel against Corin and his Stoneback, Biscuit, with retry and
  "go easier" options after a loss.
* Two battle-ready kith (Emberlyn, Stoneback), 8 special abilities, 2 basic
  attack strings, 3 status effects, 2 arenas.
* Keyboard and mouse, gamepad, landscape touch controls (also usable with a
  mouse on desktop), local save file, settings.

**Planned (not in v0)**

* Online play on an authoritative server, a shared world, accounts and a
  backend.
* Three-creature teams in a real mode. The data model and switching rules
  exist in the simulation and are unit-tested, but no v0 mode turns them on.
* Casual duels. The ruleset exists but nothing uses it yet.
* More kith, abilities and variants; evolution; gameplay effects for bond;
  further chapters.

## Conventions used in these docs

* **Time:** the battle simulation runs at a fixed 60 Hz. 1 tick = 1/60 s, about
  16.7 ms. Frame data is given as `ticks (ms)` with ms rounded.
* **Distance:** world units. 1 unit = 1 logical cell = 24 sprite pixels.
* **Coordinates:** battles run on a flat plane stored as `Vector2(x = east,
  y = south)`. The overworld uses Godot XZ with X east and Z south (the camera
  looks north).
* **"Planned"** marks design intent that is not implemented.
* **Source of truth:** the data files (`resources/`) and scripts. These docs
  describe the repository as of 2026-10-24; where they disagree with the data,
  the data wins and the doc should be fixed.
