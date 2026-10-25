# Arena combat

Rules live in the pure simulation under `scripts/combat/`. Tunables are in
`scripts/combat/combat_const.gd` and in the species and ability resources.
Presentation is in `scripts/combat/view/`.

## Pillars

1. **Readable and fair.** Every danger is visible before it hits
   (telegraphs, wind-ups, projectiles in flight). Hit detection is pure 2D
   math, independent of the camera.
2. **Positioning and resource decisions win**, not button mashing. Dashes
   are strong but cost stamina, and the only way to recover stamina is to
   stand still and Focus.
3. **No unavoidable loops.** Every stun goes through one set of rules with
   diminishing returns, immunity and a wake-up guarantee.
4. **Species identity.** An agile glass cannon and a slow fortress play
   differently even under normalized ranked stats.

## Simulation model

* A fixed **60 Hz** tick (1 tick = 16.7 ms). `BattleSim.step(inputs)`
  advances exactly one tick from one `InputCommand` per team. Rendering
  interpolates between ticks.
* The arena is a **flat plane**. Positions are `Vector2(x = east, y =
  south)` in world units (1 unit = 1 logical cell = 24 sprite pixels). The
  perspective camera is pitched 48 deg with a narrow 25 deg field of view and
  never rotates; the back row looks a little smaller than the front row, but
  drags are mapped back to the ground exactly. Sprites are stretched by
  1/cos(pitch) so they keep their proportions. The camera can't affect
  ranges, distances or hits.
* **Collision is exact:** circles move through a rectangle with circle and
  box obstacles using swept Minkowski tests. Fast dashes and projectiles
  can't tunnel.

**Tick order** (deterministic):

1. Inputs -> buffers and aim.
2. Each on-field fighter: timers, statuses, phase advance, new actions,
   state logic, knockback. Benched fighters keep their Surge and regenerate
   stamina.
3. Body separation.
4. Hit volumes move, then projectile clashes.
5. Hits are collected, then applied (two-phase).
6. Volumes age and expire.
7. Match timer.

## The board and movement

* The arena floor is a **board of 1-unit cells** (the Ringstones and the
  training yard are both 20 x 12). Spawns and standing stones sit on cell
  centres, and every creature fits inside one cell.
* **Creatures never walk.** Every move is a **dash**: straight along a row
  or column (east, south, west or north), a whole number of cells, landing
  on a cell centre. Knockback is the only other way a creature moves.
* **Nothing moves diagonally.** Dashes, lunges, projectiles, lines and
  knockback all run along rows and columns. A dash's wind-up slides onto
  its cell centre across the lane first, then along it.
* **Bodies are solid.** Knockback stops at walls and stones; a heavier
  creature knocked into a lighter one nudges it (scaled by mass), never the
  other way round. Overlapping bodies are separated along one axis, and a
  dashing creature holds its lane while the other makes room.

## Dash

**Input.** Drag from anywhere on the screen (mouse or finger) along a row or
column and release. The drag direction picks the lane (with a little
hysteresis, so it doesn't flicker between two lanes near a diagonal) and the
drag length picks the cells, up to the species' maximum (Emberlyn 5,
Stoneback 3). Dragging back to the start cancels; so does right-click. A
quick tap is a basic attack toward the tapped spot, and pressing and holding
still Focuses. On keys, D-pad or stick, hold a direction to charge (one
cell, then one more every 7 ticks) and release to dash, so a tap is a
one-cell step. Settings can flip the drag to "slingshot" (pull back to
launch the other way).

**Plan.** `DashSystem.plan()` works the dash out from the board before it
starts, and it is pure: the aiming preview draws exactly the plan the
simulation executes on release.

* The dash starts from the creature's cell (the nearest open neighbour if
  knockback left it in a stone's cell).
* **Walls and stones cut it short**; the cost only counts cells travelled.
  A dash with nowhere to go doesn't start and costs nothing ("Blocked").
* **A foe on the landing cell** carries the dash one cell past it (that
  extra cell is free), or, if the cell beyond is closed, the dash stops on
  the cell before the foe.
* **Cost** = base + per cell (Emberlyn 6 + 5/cell, Stoneback 9 + 8/cell),
  paid when the dash starts. Not enough stamina: no dash, the gauges flash
  and an "empty" sound plays.
* **Slows** (Slow, Stone Guard) shorten the maximum and stretch the travel
  time; Emberlyn's Quickfoot speeds the travel while stamina is low.
* Requests are validated: the simulation clamps the cells and ignores bad
  directions (InputCommand carries direction and cells; nothing else).

**Phases.**

| Phase | What happens |
| --- | --- |
| DASH_START (windup) | 3 ticks (Emberlyn) / 5 (Stoneback). The creature gathers onto its cell centre (smoothstep). Readable as a crouch and lean. |
| DASH_ACTIVE (travel) | `travel_ticks = base + per_cell x cells` (Emberlyn 4 + 1.7/cell, Stoneback 6 + 2.6/cell), eased out: `1 - (1 - u)^ease` (explosive start, braking finish). Committed: only a clash, a repel or a KO ends it early. |
| DASH_RECOVERY | 7 / 10 ticks. Another dash may **chain** after 3 / 5 ticks (`chain_after_ticks`). |

Traits: **Phase Step** (Emberlyn) is long and quick, and projectiles pass
through it during the windup and the first 5 travel ticks. **Rolling
Fortress** (Stoneback) is short, can't be flinched and halves damage while
it rolls. Per-species numbers are in kith.md.

### Ram (dash through a foe)

Passing through an opponent's body **rams** it, if the victim isn't
protected (ram immunity, Steadfast, a stun-immune status) and isn't mid-dash
itself, and the dasher hasn't already passed it this dash:

| Rule | Value |
| --- | --- |
| Damage | `ram_power x attack / defense x damage scale` (Emberlyn 6.5, Stoneback 9), no element |
| Daze | 15 ticks (250 ms) x the dasher's passive (Stoneback 1.2 -> 18 ticks), through the stun rules (diminishing returns) |
| Impact | both creatures freeze for 5 ticks (shared hitstop) |
| Protection | 60 ticks (1 s) of ram immunity ("Protected" pops if hit again) |
| No guaranteed follow-up | The dasher's recovery (and its chain window) is extended so the victim always acts at least **3 ticks before** the dasher can. A ram buys position, not a free combo. |
| Landing | Always on a free cell centre: if the foe moved onto the landing cell, the nearest free centre (further along, back, then to the sides). Nothing teleports through walls. |

**Counters:**

* **Guard repel:** dashing into a guarding opponent's front arc stops the
  dash, dazes the dasher for 21 ticks (30 on a perfect guard) and bounces
  it back toward the cell it came from. A non-perfect guard pays 10 stamina.
  Dashing in from behind still works.
* **Stone Guard** repels rams from any side.
* **Head-on clash:** two dashes meeting head-on both stop, freeze for 4
  ticks and bounce back to the cells behind them; nobody is dazed.

### Dash presentation

* **Aim preview** (`DashPreview`, `DashLane`): while dragging, the lane of
  tiles the dash will cross pops in cell by cell from the creature, with
  runway-light chevrons; the landing cell gets a reticle (brackets snap onto
  it, a charge ring fills for held keys), a translucent ghost of the
  creature and the stamina cost. A foe the dash will ram turns its tile
  gold with **RAM!** over it ("Protected" when it can't be rammed); a wall
  or stone shows a red stop bar and the out-of-reach cells as dashed
  outlines; red means not enough stamina, grey means the release will
  cancel. The stamina bar and the ring under the creature blink the stretch
  the dash would spend. A tick sound rises in pitch with the cells.
* **Committed dashes:** every creature's lane flashes on the windup (an
  opponent's in red with hazard stripes) and the tiles flare and fade as it
  passes over them.
* **Motion:** coil (crouch, lean back, glow) on the windup; a stretch along
  the motion, a hop for light creatures, distance-spaced translucent
  afterimages and a ground smear on the travel; a springy squash on landing
  with dust (and a thud for heavy creatures).
* **Ram impact:** the shared freeze, a slash along the lane, sparks and a
  gold shockwave, the victim squashed and knocked, a camera kick along the
  dash plus a zoom punch, and a brief impact frame (radial colour split).

## Stamina and Focus

* Stamina **never regenerates on its own**. It can't go below 0 or above
  the maximum. Uses: dashes and guard (blocked damage drains it). Specials
  are paid for with Surge instead (below).
* **Focus** (hold): FOCUS_ENTER (7 ticks / ~117 ms of commitment, no regen)
  -> FOCUSING (regen at the species rate: Emberlyn 37/s, Stoneback 30/s,
  about a quarter slower than before Surge) -> FOCUS_EXIT (7 ticks). The
  creature is rooted and can't attack, dash or guard. Releasing during the
  enter phase still plays the whole enter and exit.
* **Any damage interrupts Focus**, including burn ticks. A hit that stuns
  sends the creature to STUNNED; otherwise it returns to IDLE.
* Benched teammates (team battles) regenerate at 25% of their Focus rate.
* Emberlyn's Quickfoot shortens the enter and exit to 4 ticks.

## Guard

* Hold Guard to block guardable hits arriving within a **200 deg frontal
  arc**. The creature is rooted (guard move multiplier 0 for both species).
* **Blocked hit:** 15% chip damage, which can't knock out (HP floors at 1).
  Stamina loss = raw damage x the species' guard factor (Emberlyn 1.25,
  Stoneback 0.8). Blockstun (guard can't be released) lasts hitstun x 0.5.
  Push-back is knockback x 0.5. Blocked projectiles are destroyed.
* **Guard break:** if the stamina hits 0 while blocking, a forced 54-tick
  (900 ms) stun that bypasses diminishing returns.
* **Perfect guard:** the first 8 ticks (133 ms) of a guard negate the hit
  entirely. A projectile is destroyed. A melee attacker (attached hitbox)
  takes 5 ticks of hitstop and a 24-tick (400 ms) stagger. The defender takes
  5 ticks of hitstop.
* After releasing guard there is a 6-tick lockout before guarding again, so
  you can't mash perfect guards.

## Surge

Specials have **no cooldowns**. They are paid for with **Surge**, a meter of
**four stages** (100 points each, 400 in all) shown in gold under each
stamina bar.

* **Costs:** every special costs whole stages, the stronger the move the
  more: Ember Bolt 1, Cinder Arc 2, Flash Strike 3, Heat Ring 4; Ground
  Pound 1, Boulder Toss 2, Stone Guard 3, Fault Line 4. Basic attacks are
  free. A special can be used as often as it can be paid for, back to back.
* **Earning it:** fighting fills it.

  | Source | Surge |
  | --- | --- |
  | A basic hit that connects (each hit of a string) | 40 |
  | A special hit that connects | 15 |
  | A ram that connects (dash through a foe) | 120 |
  | Any dash | 4 |

  Blocked hits, burn ticks and getting hit earn nothing. Emberlyn's
  Quickfoot passive earns 45% more of everything (it hits fast but light,
  so it lives on its specials).
* A battle starts with **no Surge**; it caps at four stages and never
  drains on its own. A benched creature keeps its Surge.
* **Feedback:** each stage that fills rings a chime a step higher than the
  last and flashes the creature gold ("Surge full!" at four). Ability
  slots and touch buttons show their cost as diamonds, lit when affordable;
  the share still to earn darkens the slot and sweeps away as the meter
  climbs. A 3- or 4-stage special swells, flashes gold and punches the
  camera in when it starts. Pressing one you can't pay for shakes its slot,
  pulses the meter red and says how many stages it needs.

## Attacks and abilities

* Each creature has a basic attack string, four equipped specials, a
  passive, a dash, Focus and guard.
* Shared phase model: **startup** (wind-up, telegraphed for big moves) ->
  **active** (hitbox live) -> **recovery** (vulnerable). Surge (and any
  stamina cost) is paid when the ability starts. If it can't be paid it is
  denied (Surge, stamina or status) and its HUD slot shakes.
* **Attacks follow the board.** The aim picks a row or column (its dominant
  axis, with the same hysteresis as dashes), so projectiles, lunges, cones
  and lines always point east, south, west or north.
* **Aim modes:** direction (projectiles, cones, lines), target point (Heat
  Ring: it lands on a whole cell along the lane, 1 cell up to its max range)
  and self (Ground Pound, Stone Guard). Aim keeps updating during startup
  and is fixed from the active frame on.
* **Components:** abilities are built from reusable parts rather than
  bespoke code: projectile, melee (circle, cone or box attached to the
  caster), lunge, targeted area (delayed circle or ring), self area, line
  wave (telegraphed travelling line) and self status. All eight specials are
  compositions of these.
* **Cancel rules:** recovery can only be cancelled where the data allows
  it. Basic strings chain if attack is pressed or held in the first N ticks
  of recovery, and a dash can cancel recovery from a given tick. Specials
  have no cancels in v0.
* **Armor:** an ability can be unflinchable during startup or active (Ground
  Pound's wind-up). Armored creatures still take damage, and their knockback
  is cut to 30% (an armored dash takes none: it holds its lane).
* **Telegraphs:** Ground Pound shows its radius during startup. Heat Ring
  marks its circle for 40 ticks, and Fault Line marks its line for 30 ticks,
  before they become dangerous.

## Hit resolution

**Two-phase:** every overlap between live hit volumes and hurt circles is
collected first, then applied, so update order never decides a trade. Each
target can be hit once per volume unless a re-hit interval is set.
Non-piercing projectiles die on their first hit.

**Damage:**

```
damage = power x mastery_mult x (ATK / DEF) x element_mult x ruleset.damage_scale
         (x ruleset.enemy_damage_mult if the attacker is the PvE enemy side)
         x target status damage_taken_mult (Stone Guard 0.45)
         x dash armor (ARMORED dash while active: 0.5)
         -> snapped to 0.1, minimum 1
```

**Order of checks on contact:**

1. FAST-dash evade (projectiles only).
2. Guard (if the target is guarding and the source is in its arc).
3. Damage.
4. Hitstop.
5. KO check.
6. Focus interrupt.
7. Hitstun (unless flinch-immune).
8. Knockback.
9. Statuses.

| Effect | Rule |
| --- | --- |
| Hitstop | Freezes the target for the hit's hitstop ticks (max 10). It also freezes the attacker for attached melee, which gives melee its weight. Frozen fighters' timers pause, and an attached hitbox doesn't age while its owner is frozen. Hits with hitstop >= 5 count as "heavy" for feedback. |
| Hitstun | The hit's hitstun x the target's passive (Bedrock 0.8), applied as a stun through the stun rules below. Skipped if the target is flinch-immune (Stone Guard, ARMORED dash, ability armor). |
| Knockback | Distance = knockback x status mult x passive mult (x0.3 if flinch-immune, none during an armored dash). It is spread over 8 ticks with geometric decay 0.85 per tick (the first tick covers ~21% of the distance) and stops at walls. Always along a row or column: the hitbox's direction, or for radial hits (static circles are always radial) the dominant axis from its centre to the target. Starting a dash ends any knockback still sliding the creature. A KO blow pushes at least 0.8. |
| Chip | Blocked hits only: 15% of raw damage, can't KO. |

**Projectiles:**

* Swept circle tests from the previous to the current position each tick,
  so a fast bolt can't skip a target.
* Walls and standing stones stop projectiles.
* Range is limited by travel distance.
* **Clash:** opposing projectiles whose paths cross collide. Equal weights
  destroy each other. Otherwise the heavier one survives, losing the
  lighter one's weight. Ember Bolt is 1, Blaze Bolt 2, Boulder 3, Acorn 1.

## Stun and combo protection

Every stun (hit flinch, dash-through, repel, perfect-guard stagger, guard
break) goes through `StunRules`:

| Rule | Value |
| --- | --- |
| Chain window | A stun that starts while already stunned, or within 90 ticks (1.5 s) of the last stun ending, chains |
| Diminishing returns | 1st 100%, 2nd 75%, 3rd and later 50% (minimum 4 ticks) |
| Steadfast | When the 3rd chained stun ends, the creature gets 75 ticks (1.25 s) of stun immunity and the chain resets. It shows an outline glow, and resisted stuns pop "STEADFAST". |
| Wake-up grace | For 6 ticks (100 ms) after any stun ends, new stuns are ignored, so the victim always gets one buffered action out |
| Forced stuns | Guard break ignores all of the above |

Damage still applies while stun-immune; only the flinch is removed.

## Status effects

| Status | Default duration | Effect | Source |
| --- | --- | --- | --- |
| Burn | 180 ticks (set to 120 by Cinder Arc, 150 by Heat Ring) | 1.0 power every 30 ticks, using the attacker's ATK over the target's DEF, with no element. No hitstun, but it interrupts Focus. | Cinder Arc, Heat Ring |
| Slowed | 90 ticks | Dashes x0.65 (fewer cells, slower travel) | Ground Pound |
| Stone Guard (buff) | 80 ticks | Damage taken x0.45, knockback x0.3, flinch immune, repels rams, dashes x0.6 | Stone Guard |

Reapplying a status refreshes its duration to the longer one. Statuses
are cleared when a creature switches out (none persist across switches in
v0).

## Elements

The multiplier is attacker element > defender element. Missing pairs are
1.0. The values are deliberately mild so matchups shape play without
deciding it.

| Attacker \ Defender | Ember | Grove | Stone | Tide | Gale |
| --- | --- | --- | --- | --- | --- |
| Ember | 0.9 | 1.25 | 0.9 | 0.8 | 1.0 |
| Grove | 0.8 | 1.0 | 1.2 | 1.25 | 0.85 |
| Stone | 1.1 | 0.85 | 1.0 | 1.0 | 1.25 |
| Tide | 1.25 | 0.8 | 1.1 | 1.0 | 1.0 |
| Gale | 1.0 | 1.25 | 0.8 | 1.1 | 1.0 |

Aether and Neutral have no entries (always 1.0). At 1.05 or above the hit
shows "Effective!", at 0.95 or below "Resisted". Only Ember and Stone have
battle-ready kith in v0; the other elements exist in data for future kith.

## State machine

There are 15 explicit states (`scripts/combat/states/fighter_sm.gd`;
MOVING is kept for save/replay compatibility but nothing enters it, since
nothing walks). The
sim never assigns a state directly: `BattleSim.set_state()` checks the
transition table and refuses illegal moves (counted and logged in debug
builds).

| From | Allowed destinations |
| --- | --- |
| IDLE | FOCUS_ENTER, DASH_START, ATTACK_START, GUARDING, STUNNED, SWITCHING, KNOCKED_OUT |
| FOCUS_ENTER | FOCUSING (held), FOCUS_EXIT (released), IDLE (interrupted), STUNNED, KNOCKED_OUT |
| FOCUSING | FOCUS_EXIT, IDLE (interrupted), STUNNED, KNOCKED_OUT |
| FOCUS_EXIT | IDLE, STUNNED, KNOCKED_OUT |
| DASH_START | DASH_ACTIVE, STUNNED, KNOCKED_OUT |
| DASH_ACTIVE | DASH_RECOVERY, STUNNED, KNOCKED_OUT (committed: only a repel, a clash or a KO end it early) |
| DASH_RECOVERY | IDLE, DASH_START (chain window only), STUNNED, KNOCKED_OUT |
| ATTACK_START | ATTACK_ACTIVE, STUNNED, KNOCKED_OUT |
| ATTACK_ACTIVE | ATTACK_RECOVERY, STUNNED, KNOCKED_OUT |
| ATTACK_RECOVERY | IDLE, DASH_START (dash-cancel window only), ATTACK_START (string chain only), STUNNED, KNOCKED_OUT |
| GUARDING | IDLE, STUNNED, KNOCKED_OUT |
| STUNNED | IDLE, STUNNED (re-stun with diminishing returns), KNOCKED_OUT |
| SWITCHING | IDLE, STUNNED (a switch can be interrupted), KNOCKED_OUT |
| KNOCKED_OUT | none (receives no input) |

New commands are only accepted in IDLE (plus the dash chain in
DASH_RECOVERY and the cancels in ATTACK_RECOVERY). Hitstop is a freeze
counter, not a state.

## Input

* **InputCommand** is one tick of intent and the only thing a future client
  would send. It holds a dash request (direction 0-3 and cells, or none),
  an aim direction quantized to 1/4096 of a turn, an aim distance, and held
  and pressed button masks. It encodes to 17 bytes. The simulation clamps
  the cells and ignores invalid requests. Presses between ticks are latched,
  so a 1-frame tap is never lost.
* **Input buffer:** presses are remembered for **8 ticks (133 ms)**, and each
  is consumed once. An input made a little early (in recovery, hitstop or
  stun) comes out on the first legal tick.
* **Priority** when actionable: switch > dash > guard > specials (slots 1-4)
  > basic attack (press, or hold to repeat) > Focus (hold). In recovery only
  the string chain and the dash-cancel are checked. In Focus, releasing the
  button starts the exit. In guard, releasing returns to IDLE after
  blockstun.
* **Aim:** mouse or right-stick aim when present. Otherwise the creature
  soft-locks onto the opponent. Facing follows the aim's row or column while
  actionable, guarding or focusing.

## Match flow

| Phase | Rules |
| --- | --- |
| Countdown | 180 ticks (3, 2, 1). Only aim updates, and buffers clear at "FIGHT!". Training skips it. |
| Fight | Timer from the ruleset: 120 s for Free Battle and Versus, 150 s for the story duel, none in training |
| KO settle | 90 ticks (1.5 s) after a KO. Nobody can be hurt, and live volumes are removed. Then the next healthy teammate is sent in (with 18 ticks of stun grace) or the battle ends. |
| Timeout | The team with the higher total HP ratio wins. Within 0.001 it is a draw. |
| Rematch | `BattleSim.reset()` rebuilds the identical starting state |

In training the totem can't be knocked out: its HP refills.

## Teams and switching (data model; no v0 mode enables it)

`BattleSetup` holds up to three creatures per team. With `allow_switching`
on (tests only in v0):

* Switch keys 1, 2 and 3 are honored only when actionable, so you can't
  switch while stunned, attacking, dashing, focusing or guarding.
* A switch takes 30 ticks (500 ms) and can be interrupted by a hit.
* The incoming creature can't switch again for 300 ticks (5 s).
* The outgoing creature loses its statuses and dash immunity.
* A benched creature keeps its Surge and regenerates stamina at 25% of its
  Focus rate.
* Victory requires knocking out the whole opposing team.

The brief targets 3-5 minute matches once full teams exist (Planned).

## AI

`CombatAI` plays by the same rules as a human: it only emits InputCommands,
sees the opponent through a reaction-time delay, aims with error and
manages stamina with Focus and Surge for its specials. Each tick it:

1. Perceives the delayed opponent state.
2. Reacts to threats (dodge-dash, guard, step away, or nothing). The
   reaction is chosen once per threat.
3. Manages Focus (it focuses when low and safe, and stops near 88% or on
   danger).
4. Continues basic strings.
5. Picks an offensive option by utility every decision interval. It sets
   itself a Surge goal after each special (1 stage 35%, 2 30%, 3 20%,
   4 15%) and keeps that much banked for a move of that cost, spending on
   cheaper ones only above it (or on a vulnerable foe); after 6 s at the
   goal without an opening it settles for less. Rams score higher while it
   has nothing to shoot with, since a ram earns more than a stage.
6. Holds its preferred range band with planned dashes (it never walks
   either): Agile 3.0-5.5 u (kite) when it can pay for a ranged special,
   otherwise 2.5 u to its dash reach (hunting rams); Heavy 0.9-2.1 u
   (brawl); anything else 1.5-4.0 u. It backs off to 4.5-7.5 u when it needs
   to Focus (below its threshold, or when any dash would dip under a 25%
   stamina reserve). Candidate
   landing cells are scored by the band, by the best attack it could throw
   from there (attacks run along rows and columns, so it lines up on the
   foe's row or column), lanes the foe could ram, edges and corners, and
   the stamina the dash costs; it dodges with short dashes and takes rams
   when a plan shows one. An attack is only chosen when its hitbox, swung
   down that lane, would reach the foe.
7. Breaks stand-offs: after 2 s without attacking, impatience builds over
   4 s, weighting attack lanes up and the fear of ram lanes and the stamina
   reserve down, until it attacks or Focuses even in a ram lane.

| Preset | Reaction | Decision | Aim error | Lead | Dodge | Guard | Dash-through | Aggression | Focus below | Mistakes | Combo skill | Patience |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Easy | 26 | 12 | 16 deg | 0.3 | 0.20 | 0.15 | 0.15 | 0.40 | 45% | 0.25 | 0.3 | 1.6 |
| Normal | 14 | 6 | 7 deg | 0.8 | 0.55 | 0.35 | 0.35 | 0.60 | 35% | 0.08 | 0.6 | 1.0 |
| Hard | 9 | 4 | 3 deg | 1.0 | 0.80 | 0.55 | 0.55 | 0.75 | 30% | 0.03 | 0.9 | 0.8 |
| Story (Corin) | 28 | 12 | 15 deg | 0.38 | 0.20 | 0.16 | 0.18 | 0.44 | 44% | 0.27 | 0.34 | 1.35 |

Reaction and decision are in ticks. The AI has a seeded RNG, so AI-vs-AI
runs are reproducible. Free Battle offers Easy, Normal and Hard. The story
duel uses Story, or Easy after a loss with "go a little easier".

## Tutorial (training yard)

`TrainingDirector` shows one tip per step and completes each step from real
simulation events, so it teaches exactly the rules the game enforces:

1. **Dash to move:** land on three glowing marks (cell centres a straight
   dash apart: north 3, east 4, south 5 from the start).
2. **Stamina:** dash 3 more times, watching the cost on the lane and the
   ring.
3. **Strike:** land 3 Tail Swipe hits (click or tap toward the totem).
4. **Specials:** use all four (Q, E, R, F).
5. **Focus:** hold Shift (or press and hold still) until stamina is at
   least 95%.
6. **Ram:** daze the totem by dashing through it.
7. **Guard:** the totem shoots acorns. Block 2 (a perfect guard counts
   double).

Outside the Focus and ram steps the director tops up stamina so
nothing stalls. When the last step completes, Hesper says "You're ready for
the Ringstones."

## Game feel (as implemented)

Everything below is cosmetic and never changes the simulation.

* **Interpolated rendering** between 60 Hz ticks for smooth motion at any
  frame rate.
* **Hitstop** is real sim freeze frames (above). During hitstop the sprite
  jitters (harder when stunned).
* **Hit flash and squash:** a white flash on the hit sprite (decays quickly)
  plus a squash (0.86 x 1.1) that springs back on a damped spring, so it
  overshoots slightly. The dash has its own poses (see Dash presentation).
* **Camera feel:** besides shake, `kick` nudges the view along a direction
  and `zoom_punch` briefly tightens it (rams, clashes, heavy landings);
  all scale with the Screen Shake setting, as does the impact frame.
* **Camera trauma:** shake is a pure translation (never rotation), with
  amplitude trauma^2 and fast decay, scaled by the Screen Shake setting.
  Trauma per event:

  | Event | Trauma |
  | --- | --- |
  | Light hit | 0.12 |
  | Heavy hit | 0.32 |
  | Ram | 0.38 |
  | Repel | 0.22 |
  | Clash | 0.32 |
  | Block | 0.1 |
  | Heat Ring burst | 0.3 |
  | Guard break | 0.45 |
  | Ground Pound | 0.45 |
  | KO | 0.8 |

* **Popups** (pixel-font Label3D that pops in and floats up; a popup that
  would land on a recent one stacks above it):
  * damage numbers, warm for effective hits and cool grey for resisted;
  * "Effective!" and "Resisted";
  * RAM!, Protected, REPELLED!, CLASH!, Blocked, Out of stamina, EVADE,
    BLOCK, PERFECT!, GUARD BREAK!, STEADFAST, ARMOR;
  * status names and burn tick numbers;
  * "Focus broken!".
* **Telegraphs:** ground decals with a dedicated shader for Ground Pound's
  radius, Heat Ring's target circle and Fault Line's line, timed to the
  sim's delay. Spikes erupt along the Fault Line as the wave front passes.
* **Status visuals:**
  * burn embers trail;
  * slow tint;
  * Stone Guard dome;
  * Focus aura and shimmer;
  * stun stars (hidden for short flinches under 16 ticks);
  * Steadfast outline;
  * a guard arc decal that brightens during the perfect-guard window;
  * a ground ring under each creature that doubles as its stamina gauge.
* **KO:**
  * the sim runs at 1/3 speed for 54 frames;
  * a "K.O.!" banner, a KO burst and a crowd cheer;
  * a delayed body-fall sound;
  * after 1.6 s the body dithers out until it is 55% dissolved.
* **Audio layering:**
  * every ability has a cast sound and every hit spec an impact sound;
  * "effective" and "resisted" stingers layer on top;
  * Focus start -> loop -> full chains;
  * countdown ticks, the fight start and crowd reactions;
  * random variants and pitch jitter, with a per-sound minimum interval
    against stacking.
* **HUD:**
  * HP bars with delayed "ghost" damage;
  * stamina bars segmented by dash cost;
  * status icons and the match timer;
  * a four-stage Surge meter under each stamina bar;
  * an ability bar with Surge cost diamonds (the share still to earn sweeps
    away as the meter fills) and key hints;
  * big centre messages (3-2-1, FIGHT!, K.O.!, VICTORY/DEFEAT).
* **Debug:** F3 draws hurtboxes, hitboxes and the logical cell grid.

## Controls

| Action | Keyboard and mouse | Gamepad | Touch (landscape) |
| --- | --- | --- | --- |
| Dash (move) | Drag with the left button along a row or column, release | Hold a D-pad / stick direction to charge, release | Drag on the arena, release |
| Cancel a dash | Drag back to the start, or right click | Guard or Focus | Drag back to the start |
| Aim | Mouse | Right stick | Drag an ability button, or auto-aim on tap |
| Basic attack | Click (quick tap) / J | RT | Tap the arena or the attack button |
| Focus (hold) | Shift | LT | Press and hold still on the arena, or the Focus button |
| Guard (hold) | Space / right mouse button | LB | Guard button (hold) |
| Specials 1-4 | Q / E / R / F | A / B / X / Y | Four buttons, 64 px minimum |
| Switch 1-3 | 1 / 2 / 3 | - | Planned |
| Pause | Esc / P | Start | Menu button |

Keys also dash: hold W/A/S/D (or the arrows) to charge one cell, then one
more every 7 ticks, and release.

In Local Versus the keyboard is split. Player 1 keeps the mouse, WASD
(charge dashes), left Shift (Focus), Space (guard), Q/E/R/F and J; arrows
and the right-hand modifiers do nothing for player 1. Player 2 charges
dashes with the arrows and uses `.` or `/` to attack, right Shift Focus,
right Ctrl guard, and `;` `'` `[` `]` for specials. Gamepads are assigned per player (`InputSetup.assign_versus_pads`):
with one pad connected it plays player 2, with two the first is player 1's.
The touch controls can be forced on in Settings (or with F6) to test them with
a mouse.

## Arenas

| Arena | Size | Obstacles | Spawns |
| --- | --- | --- | --- |
| The Ringstones | 14 x 9 cells | Two standing stones (radius 0.45) on the cell centres (-2.5, -2) and (2.5, 2), point-symmetric so neither side is favored | (-4.5, 0) and (4.5, 0) |
| Mossford Training Yard | 13 x 9 cells | None | (-4, 0) and (3, 0) |

The Ringstones floor is laid with one flagstone per cell, so the board's
lanes are visible at a glance; the training yard is packed sand on the same
grid.
