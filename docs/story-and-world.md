# Story and world

All story text lives in `resources/dialogue/chapter1.json`. The chapter logic
(steps, triggers, cutscenes) is `scripts/world/story/chapter_one.gd`, and the
region is built by `scripts/world/mossford_builder.gd`.

## Theme and tone

**Trust is earned, never taken.** Warden Hesper says it in the first scene:

> "Trust, mind you. Not nets, not cages, not bribes. A kith that follows you
> out of fear isn't bound to you. It's just waiting to leave."

The mechanics carry the theme:

* You befriend a kith by reading its needs and being patient: sneak, observe,
  warm it, sit still, offer your hand. There is no capture item.
* In battle you fight *beside* your kith ("never as if it were a sword"): the
  player steers the creature, and the duel tests the bond.
* Stamina only comes back while you hold Focus, so catching your breath is a
  decision with risk. The same patience runs through the whole chapter.

**Tone:** warm and cozy village life with a slowly growing mystery. Small
details make the place feel lived in: the kettle is still warm, and "C +
BISCUIT" has been freshly scratched into the well. Against that, iron snares
with burnt-in sigils turn up in the forest, the ground shakes, and a hooded
figure is waiting at the old shrine. The chapter runs from one morning to
that night, and the lighting follows it.

**Look:** an HD-2D storybook diorama. Pixel-art sprites stand in a lit 3D
world with tilt-shift depth of field, fog, fireflies, lanterns and lit
windows. The duel takes place at golden hour and the reveal under moonlight.

## Lore (as told in Chapter 1)

* **The Accord:** long ago, people and kith lived side by side, bound by a
  promise called the Accord.
* **The Sundering:** the Accord broke. The kith fled into the wild places,
  and trust turned to fear.
* **Wardens** keep the old ways, earning a kith's trust one bond at a time.
  Apprentices become Wardens at **the Kindling**: they must earn the trust of
  a wild kith before sundown, then prove the bond in a duel at the
  Ringstones.
* **Aurelune, the Dawncrane:** the great crane-like kith on the Dawn Shrine
  mural. The old songs say it sealed the Accord and vanished the day the
  Accord broke.
* **Lanternmoths** were the first kith to return to people after the
  Sundering (journal entry).
* **The Sigilbinders:** people who bind kith with sigil-chains. Hesper had
  hoped they were only a story told to frighten apprentices. Their snares in
  the Glimmerwood were not catching kith at random; they were hunting for
  Aurelune.

## The Mossford region

The region is about 68 x 62 units. Coordinates below are overworld (x, z),
with X east and Z south.

```
                    N
          Dawn Shrine (-1,-28)
                                     Ringstones (17,-16)
     north meadow + pond (-6,-12)
     (Mosslings graze here)
 Glimmerwood     | stream |      village square        training yard
 clearing        | bridge |      great oak (0.5,7)     (17..27, 3..13)
 (-25,-2)        | (-15,2)|
                                player's home (-9,19)
                    S
```

| Place | What is there | Story use |
| --- | --- | --- |
| Mossford village | Great oak, notice board, well, signpost, the player's home, Wynn the baker, Bram the farmer, Hesper with her Lanternmoth Lumen | Start of the chapter, flavor interactions, NPC hints |
| Stream and bridge | A north-south stream at about x = -15 with one bridge | The threshold into the wild. Music switches to the forest theme west of it. |
| The Glimmerwood | A clearing with a hollow log, an old fire ring, three bundles of dry kindlemoss and a broken iron snare. Sight lines into the clearing are kept free of tall trees, and foliage dithers when it would hide the player. | The befriending |
| North meadow and pond | Clover, a pond, a roaming Mossling | Optional observation (journal) |
| Training yard | Straw training totems | Combat tutorial |
| The Ringstones | An old circle of standing stones "where Wardens have dueled for generations" | The Kindling duel. The battle arena is 14 x 9 with two standing stones. |
| The Dawn Shrine | Crumbling walls and a carved mural of Aurelune before a rising sun | The chapter ending |

The signpost reads: "West: the Glimmerwood. North: the Dawn Shrine. East: the
training grounds. North-east: the Ringstones."

**Music:** `village_theme` by default, `forest_theme` west of the stream,
`shrine_theme` at night, `battle_theme` in duels (training uses the village
theme), `title_theme` on the title screen, and `victory_fanfare` after a win.

**Time of day by story step:** morning (wake, find a kith) -> day (after
befriending, training) -> golden hour (duel) -> dusk (after the tremor) ->
night (ending).

## Chapter 1, "The Kindling": beat sheet as implemented

Progress is stored as flags in the save profile, so the chapter resumes from
any point. The current step is derived from those flags:
`wake -> find_kith -> training -> duel -> ending -> complete`.

| # | Step / flags set | Trigger | What happens | Dialogue ids |
| --- | --- | --- | --- | --- |
| 0 | (new profile) | Title -> New Journey -> name entry (default "Wren") | Four narration cards set up the Accord, the Sundering and the Wardens. | `intro_card` |
| 1 | wake -> `met_hesper` | Talk to Hesper in the square | Hesper explains the Kindling and the rule of trust, and mentions iron snares with strange burnt-in signs (one reply choice, flavor only). Corin bursts in with Biscuit, boasts, and heads for the Ringstones. Hesper points west, teaches sneaking (hold Shift) and gives you the Warden's Lantern. | `hesper_intro`, `corin_intro`, `hesper_send_off` |
| 2a | find_kith -> `forest_seen` | Walk within 7.5 units of the Glimmerwood clearing | The camera finds a small kith peering out of a hollow log, its tail ember barely alive. It shrinks back. Journal: Emberlyn "seen". | `forest_arrival` |
| 2b | `observed_emberlyn` | Inspect the log while sneaking. Running within 5 units of the log spooks it (6 s cooldown, toast hint). | You kneel and watch: it is soaked and shivering, and it needs warmth. Dry kindlemoss grows around the clearing, and there is an old fire ring. Journal: "observed". | `emberlyn_spooked`, `observe_emberlyn` |
| 2c | `moss_1..3`, `moss_count` | Pick up three glowing kindlemoss bundles | Pickup toasts with a count (n/3). | - |
| 2d | `fire_lit` | Use the fire ring with 3/3 moss | The Lantern lights the fire. Warm light, crackle loop; the Emberlyn looks up. | `fire_ring_empty`, `fire_lit` |
| 2e | `befriended` | Use the fire again to sit | The kith creeps closer in 5 stages while a trust meter fills. Moving breaks the spell (it retreats, and you can retry). Then comes the "Offer your hand" timing ring: up to three tries, and a third miss still succeeds ("never hard-fail a story beat"). You name your Emberlyn, it joins at level 5 with bond 30, and it follows you from then on. Time shifts to day. | `sit_down`, `sit_moved`, `emberlyn_close`, `offer_fail`, `befriended` |
| opt | `snare_seen` | Inspect the snare near the log | A broken iron snare, still faintly warm, with a scorched sigil and "a few singed russet hairs". This unlocks an extra Hesper line in training. | `snare`, `hesper_training_snare` |
| opt | `mossling_observed` | Sneak up to the meadow Mossling (it bolts from running footsteps within 6.5 units) | It sniffs you and goes back to grazing. Journal: Mossling "observed". | `mossling_observed` |
| 3 | training -> `training_done` | Talk to Hesper at the training yard (or use the gate) | Hesper is delighted, and then the tutorial battle runs: 7 steps against a training totem (see combat.md). Afterwards Hesper gives practical advice for fighting a heavy kith. Golden hour begins, and villagers gather at the Ringstones. | `hesper_training_intro`, `hesper_after_training` |
| 4 | duel -> `duel_won` | Talk to Corin at the Ringstones | The Kindling duel: your Emberlyn against Biscuit (same level as your kith, minimum 5), with a 150 s limit and Corin's "story" AI. **Loss:** choose Again, Again but easier (the Easy AI), or In a moment. **Win:** Corin sulks, then grins. Hesper names you both Wardens of Mossford. XP and mastery are awarded. A tremor comes from the north, then dusk falls, then night. | `corin_duel`, `duel_lost`, `duel_won`, `tremor` |
| 5 | ending -> `shrine_done` | Walk to the Dawn Shrine (within 3.5 units) | The mural awakens and glows. Hesper names Aurelune. Your Emberlyn's ember answers the mural. A Sigilbinder on the broken wall flees. Hesper explains the snares. Chapter card, then back to the title. | `shrine_arrival`, `shrine_ember`, `sigilbinder_seen` |
| 6 | complete | - | Explore freely. The title screen offers Free Battle and Local Versus. | - |

Flavor interactions available throughout: the player's house, the notice
board, the well, the signpost, Wynn and Bram (who give hints for the
befriending and the Mossling), greeting Lumen, and early visits to the
yard, the arena gate or the shrine.

## Characters

| Character | Role | Personality | Arc in Chapter 1 |
| --- | --- | --- | --- |
| **The player** (default name Wren) | Apprentice on the morning of the Kindling. A silent protagonist who answers through dialogue choices. | Defined by the player's choices and patience | Earns a kith's trust, learns to fight beside it, becomes a Warden, and witnesses the first sign of the Sigilbinders. Hesper calls them "Sprout". |
| **Warden Hesper** | Mentor, and the elder Warden of Mossford | Warm, dry humor, stern about the ethics of trust | Guides the Kindling, runs the training, officiates the duel, and leads the apprentices to the shrine. Her line "I haven't seen the mural glow since I was younger than you" hints at a past. |
| **Lumen** | Hesper's Lanternmoth (an aether kith) | Gentle; glows "like a lamp left on for you" | Has guided Mossford's lost for forty years. Hovers around Hesper and minds the training totem. |
| **Corin** | Rival and friend, also an apprentice | Excitable, boastful, good-hearted and a good loser ("Next time I'm winning.") | Befriended a Stoneback by sitting with it for an hour, the right way, which mirrors the theme. Duels you, then stands with you at the shrine. |
| **Biscuit** | Corin's Stoneback | Sleepy, stubborn, "loyal to the bone"; "hits like a landslide" | Your first real opponent. Falls asleep after losing. |
| **Your Emberlyn** | The player's partner kith (nickname optional) | Frightened and cold at first; brightens with trust | Saved from the cold, befriended, fights at your side, and its ember answers the mural at the shrine. |
| **Wynn** | Village baker | Cheerful | Hint: "A cold Emberlyn is a scared Emberlyn. Warm one up and it'll purr like my oven." |
| **Bram** | Farmer | Gruff, teasing | Hint: Mosslings bolt at stomping, "unless you creep like a cat". |
| **Aurelune, the Dawncrane** | Mythic kith on the shrine mural | - | Sealed the Accord and vanished at the Sundering. The Sigilbinders are hunting it. |
| **A Sigilbinder** | Antagonist faction member | Silent, hooded, glowing sigil-chain | Seen on the shrine wall at night, then flees. |

Art and portraits: the explorer, Hesper, Corin, the villagers, the
Sigilbinder and the crowd have sprite sheets. Hesper, Corin, the player and
Emberlyn have dialogue portraits with expressions (Corin's include grin,
determined and sulk). See `tools/art_forge/README.md` (the HD sheets and
the portraits) and `tools/sprite_forge/README.md` (the crowd and the
procedural fallbacks).

## Hooks for later chapters (Planned)

Everything in this section is design intent, not implemented.

* **The Sigilbinders:** who they are, what a sigil-chain does to a kith, and
  why they want Aurelune. Hesper ends the chapter with "Tomorrow, we have a
  long road ahead." Chapter 2 leaves Mossford.
* **The singed russet hairs** in the warm snare suggest the frightened
  Emberlyn may have escaped a Sigilbinder snare just before you found it. This
  could be revealed later and tie the partner kith into the main plot.
* **Why the ember answers the mural:** an ember/dawn link between Emberlyn
  and Aurelune, which could tie into evolution or a story-gated ability.
* **Hesper's past:** when she last saw the mural glow.
* **Corin and Biscuit** as a recurring companion rival with their own growth.
* **Bond:** each kith already stores a bond value (0-100; the befriended
  Emberlyn starts at 30). It has no gameplay effect yet. Possible uses are
  story gates, cosmetics or field abilities. Ranked combat stats must never
  depend on it.
* **World design goals** from the brief: habitats, day/night and weather
  encounters, hidden passages, environmental puzzles, creature traversal
  abilities, ancient ruins, cooperative exploration and social spaces.
