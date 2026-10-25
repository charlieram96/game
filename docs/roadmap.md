# Roadmap

## Milestones from the brief

The original brief lists milestones 1-3; the text breaks off partway
through Milestone 3.

**Milestone 1, Foundation: complete**

* [x] Working Godot project (4.7.2) that launches and is playable
* [x] Organized, modular architecture (see architecture.md)
* [x] Fixed-angle orthographic arena camera
* [x] Controllable creature with 8-direction movement
* [x] Strict 4-direction dash with tie-break rules
* [x] Collision and boundaries (exact swept circles, stones and walls)
* [x] Battle HUD

**Milestone 2, Combat: complete**

* [x] Stamina and Focus (enter and exit commitment, interruption)
* [x] Dash-through stun with immunity, safe landing and no guaranteed
  follow-up
* [x] Basic attack strings for both kith
* [x] Four specials per creature, all built from reusable components
* [x] Health, damage, guard and perfect guard, statuses, elements
* [x] AI opponent with Easy / Normal / Hard / Story profiles
* [x] Knockout, timeout and rematch
* [x] Explicit 15-state machine with a transition table, plus an input buffer

**Milestone 3, HD-2D exploration: complete for v0**

* [x] Small explorable 3D region (village, forest, stream and bridge,
  meadow and pond, training yard, arena, shrine)
* [x] Pixel-art explorer with walk and sneak
* [x] Creature in the world: a befriendable wild Emberlyn that becomes a
  following companion, plus a roaming Mossling
* [x] NPCs, dialogue with portraits and choices, field journal

**Delivered beyond the listed milestones (the v0 slice)**

* [x] Chapter 1 story with cutscenes, from morning to night
* [x] 7-step tutorial and the story duel
* [x] Title screen, Free Battle, Local Versus, settings, pause, local saves
* [x] Landscape touch controls (also usable with a mouse on desktop) and
  gamepad
* [x] Progression: levels, mastery, variants, Ranked / Casual / PvE rulesets
* [x] Fully generated original art, SFX and music
* [x] 92 automated tests, including an end-to-end Chapter 1 playthrough, and
  an AI-vs-AI balance harness
* [x] Shareable builds: export presets for Web, Windows, Linux and macOS,
  a branded web loading page, a gzipped ~15 MB web package for itch.io or
  any static host (`tools/export.sh`), and a CI workflow that tests, builds
  and deploys to GitHub Pages. The workflow has not run on GitHub yet.

## Known gaps and limitations

**Not built yet (by design for v0)**

* No online play (networking phases B-D in architecture.md).
* Three-creature teams and switching exist in the sim and are tested, but no
  mode enables them. There are no switch controls on the HUD or touch
  layout.
* The Casual ruleset isn't used by any mode.
* Mossling and Lanternmoth have no battle kit.
* Only Ember Bolt has mastery variants, and there is no variant or mastery
  screen.
* Bond has no gameplay effect, and there is no evolution.
* Ability learn levels are in the data but not enforced; loadouts are always
  the full default four.

**Balance and feel (AI-vs-AI data, n = 150; see architecture.md)**

* The Stoneback mirror averages ~84 s and half its matches time out.
  Options: more chip pressure, a stamina drain on long guards, or a
  sudden-death rule.
* Emberlyn vs Stoneback is 55/45 overall with no side bias (the Emberlyn
  mirror splits 74 / 74).
* A new-player proxy (Easy AI) beats story Corin 32% of the time after
  softening his profile. The "go a little easier" retry exists, but
  first-duel difficulty should be checked with real players.

**Fixed since the first docs pass**

* Local Versus input: player 1 no longer listens to the arrows or the
  right-hand Shift/Ctrl, and each gamepad drives one player
  (`tests/integration/test_versus_input.gd`).
* Settings: the unused `aim_assist` field is gone; `show_fps` is wired to an
  FPS readout, and a Graphics High/Low option (hard shadows, no MSAA, no
  tilt-shift blur; Low by default on phones) was added for weak GPUs.
* The battle HUD's element emblem drew as a white square (the icon was freed
  before the frame rendered); icons are now cached.

**Known issues**

* Music is stored as ~19 MB of WAV in the repository. Exports compress it
  (the web data pack is ~4.5 MB), so this only affects repository size.

**Tech debt**

* The tutorial director (presentation layer) tops up the player's stamina
  through `BattleSim.script_set_stamina`. Before online play this should
  become a sim-side training rule set on `BattleSetup`.
* Determinism is verified within one binary only, not across platforms.

**Untested (no claims)**

* Frame rate on real phones, browsers and low-end PCs.
* Touch controls on physical devices.
* Anything networked: latency, packet loss, capacity.

## Next steps (suggested order)

1. **Playtest v0 with friends.** That is the point of this build. Watch for:
   * whether dash-through and Focus feel good and readable;
   * whether the tutorial teaches guard and perfect guard clearly;
   * how hard the first duel is;
   * whether players understand the befriending without hints.
2. **Address the Stoneback-mirror timeouts** and anything playtesting turns
   up.
3. **Art pass with `tools/art_forge`**:
   * pick models with a bake-off (done for portraits: `openai/gpt-image-2`);
   * lock each character and kith design with a concept sheet;
   * generate props and the mural (the 128x128 dialogue portraits and the
     web loading key art are done);
   * retune the sprite rigs to the approved designs.
4. **Teams of three:** switching UI on the HUD and touch, a team-select
   screen, and the 3-5 minute match target from the brief.
5. **Content:**
   * battle kits for Mossling (Grove) and Lanternmoth (Aether);
   * one Tide and one Gale kith;
   * variants for every special, and a mastery and variant screen.
6. **Online 1v1 prototype (Phase B):**
   * a headless Godot battle server and a `NetworkBattleTransport`;
   * prediction and reconciliation;
   * tests under simulated latency and packet loss before any capacity
     claims.
7. **Chapter 2:** leave Mossford on the Sigilbinders' trail (see the hooks in
   story-and-world.md).
8. **Profile performance** on target devices and set real budgets.
