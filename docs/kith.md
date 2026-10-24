# Kith (creature design)

A species is a `CreatureDefinition` resource (`resources/creatures/*.tres`);
every `.tres` in that folder is registered automatically. An individual
creature is a `CreatureInstance` (level, XP, bond, nickname, equipped
abilities, mastery, selected variants) that references its species by id.
Combat numbers are always derived from the pair by `StatCalculator` for the
battle's ruleset (see progression-and-rulesets.md), so the stored
progression never changes when a ranked match normalizes it.

Base stats are the values at level 50. Movement, dash, stamina, passive and
kit are species identity: they are never scaled by level, even in Ranked.

## Roster

| Kith | Element | Archetype | Base HP / ATK / DEF | Battle-ready | Where |
| --- | --- | --- | --- | --- | --- |
| Emberlyn | Ember | Agile | 110 / 12 / 9 | Yes | Glimmerwood (the player's partner) |
| Stoneback | Stone | Heavy | 170 / 12.5 / 12 | Yes | Riverbeds (Corin's Biscuit) |
| Training Totem | Neutral | Dummy | 80 / 8 / 10 | Training only | Training yard |
| Mossling | Grove | Shy | 70 / 7 / 8 | No kit (world and journal only) | North meadow |
| Lanternmoth | Aether | Guide | 90 / 9 / 10 | No kit (world and journal only) | Lumen, Hesper's companion |

## Body, movement, dash and stamina

| | Emberlyn | Stoneback |
| --- | --- | --- |
| Walk speed | 7.0 u/s | 4.2 u/s |
| Acceleration / deceleration | 45 / 60 u/s^2 | 25 / 32 u/s^2 |
| Turn acceleration (reversing, angle > 90 deg) | 95 u/s^2 | 30 u/s^2 |
| Collision radius / hurt radius | 0.42 / 0.48 | 0.55 / 0.60 |
| Mass (body pushing) | 1.0 | 2.2 |
| Max stamina | 80 | 140 |
| Focus regen | 28 /s (empty to full in ~2.9 s) | 15 /s (~9.3 s) |
| Focus enter / exit | 4 / 4 ticks (~67 ms, Quickfoot) | 7 / 7 ticks (~117 ms) |
| Guard stamina factor (stamina lost per point blocked) | 1.25 | 0.8 |
| Dash trait | **Phase Step** (FAST) | **Rolling Fortress** (ARMORED) |
| Dash distance | 4.0 u | 2.0 u |
| Dash startup / active / recovery | 2 / 11 / 8 ticks (33 / 183 / 133 ms) | 3 / 13 / 10 ticks (50 / 217 / 167 ms) |
| Dash speed | ~21.8 u/s | ~9.2 u/s |
| Dash cost | 25 (3 dashes per full bar) | 40 (3 per full bar) |
| Dash special | Projectiles pass through during the first 5 active ticks (83 ms) | Can't be flinched during startup and active; takes x0.5 damage while active |
| Dash-through stun inflicted | 15 ticks (250 ms) | 18 ticks (300 ms, from Bedrock) |

**Passives**

* **Quickfoot** (Emberlyn): Focus enter and exit take x0.55 as long (7 -> 4
  ticks), and Emberlyn walks 10% faster while below 30% stamina.
* **Bedrock** (Stoneback): takes half knockback, recovers from flinches 20%
  faster (hitstun x0.8), and its dash-through stuns last 20% longer.

Body contact: a heavier creature walking into a lighter one shoves it. The
lighter one takes up to 40% of the overlap correction, scaled by mass ratio;
Stoneback against Emberlyn gives 24%. Otherwise bodies are solid and the
mover takes the correction (see combat.md).

## Ability frame data

Every ability runs startup -> active -> recovery. The cooldown starts and
the stamina is paid when the ability is activated. "Total" is the time until
the creature can act again, not counting hitstop. All v0 abilities root the
caster and keep tracking the aim during startup. Basic-attack strings chain
when attack is pressed (or held) during the first N ticks of recovery, and
can be dash-cancelled from a given recovery tick.

### Emberlyn

Default loadout and keys: Q Ember Bolt, E Cinder Arc, R Flash Strike, F Heat
Ring. Basic attack on left click.

| Ability | Startup | Active | Recovery | Total | Cooldown | Cost | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tail Swipe 1 | 5 (83) | 3 (50) | 11 (183) | 19 (317) | - | 0 | chain window 9, dash-cancel from recovery tick 5 |
| Tail Swipe 2 | 4 (67) | 3 (50) | 11 (183) | 18 (300) | - | 0 | chain window 9, dash-cancel from 5 |
| Tail Swipe 3 (finisher) | 7 (117) | 4 (67) | 16 (267) | 27 (450) | - | 0 | dash-cancel from 8 |
| Ember Bolt | 7 (117) | 1 (17) | 10 (167) | 18 (300) | 54 (0.9 s) | 0 | - |
| Cinder Arc | 9 (150) | 4 (67) | 16 (267) | 29 (483) | 210 (3.5 s) | 8 | - |
| Flash Strike | 4 (67) | 7 (117) | 15 (250) | 26 (433) | 300 (5 s) | 10 | - |
| Heat Ring | 10 (167) | 1 (17) | 14 (233) | 25 (417) | 420 (7 s) | 15 | - |

| Ability | Power | Dmg vs Stoneback / Emberlyn | Hitstun | Hitstop | Knockback | Hitbox | Effects |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tail Swipe 1, 2 | 4 | ~3.6 / ~4.8 | 11 | 3 | 0.35 | 120 deg cone, reach 1.25 | - |
| Tail Swipe 3 | 6.5 | ~5.9 / ~7.8 | 18 | 6 | 1.3 | 140 deg cone, reach 1.45 | - |
| Ember Bolt | 7 | ~6.3 / ~8.4 | 10 | 2 | 0.45 | Projectile, 16 u/s, radius 0.22, range 9 | Clash weight 1 |
| Cinder Arc | 10 | ~9.0 / ~12.0 | 14 | 4 | 0.9 | 110 deg cone, reach 2.4 | Burn 120 ticks (2 s) |
| Flash Strike | 13 | ~11.7 / ~15.6 | 18 | 6 | 1.4 | Lunge 2.4 u over 6 ticks (stops on hit, bodies, walls), then a radius 0.85 circle 0.6 ahead for 7 ticks | - |
| Heat Ring | 17 | ~15.3 / ~20.4 | 20 | 6 | 1.1 radial | Circle radius 1.7 at the aimed point (max 7 u). Telegraphed for 40 ticks (667 ms), then live for 6 ticks. | Burn 150 ticks (2.5 s) |

The full Tail Swipe string deals about 13 to a Stoneback and about 17 to an
Emberlyn. Burn deals 1.0 power every 30 ticks (about 1 per tick on a
Stoneback, 1.3 on an Emberlyn). Cinder Arc's burn ticks 4 times and Heat
Ring's 5 times.

### Stoneback

Default loadout and keys: Q Boulder Toss, E Ground Pound, R Stone Guard, F
Fault Line.

| Ability | Startup | Active | Recovery | Total | Cooldown | Cost | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Shell Bash 1 | 8 (133) | 4 (67) | 14 (233) | 26 (433) | - | 0 | chain window 10, dash-cancel from 7 |
| Shell Bash 2 | 9 (150) | 5 (83) | 20 (333) | 34 (567) | - | 0 | dash-cancel from 10 |
| Boulder Toss | 14 (233) | 1 (17) | 16 (267) | 31 (517) | 240 (4 s) | 10 | - |
| Ground Pound | 18 (300) | 3 (50) | 20 (333) | 41 (683) | 300 (5 s) | 12 | Armored (can't be flinched) during startup; radius telegraphed to both players |
| Stone Guard | 6 (100) | 1 (17) | 6 (100) | 13 (217) | 720 (12 s) | 20 | - |
| Fault Line | 12 (200) | 1 (17) | 18 (300) | 31 (517) | 480 (8 s) | 18 | - |

| Ability | Power | Dmg vs Emberlyn / Stoneback | Hitstun | Hitstop | Knockback | Hitbox | Effects |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Shell Bash 1 | 6 | ~9.2 / ~6.3 | 13 | 4 | 0.7 | Radius 1.0 circle, 0.75 ahead | - |
| Shell Bash 2 | 8.5 | ~13.0 / ~8.9 | 18 | 7 | 1.6 | Radius 1.15 circle, 0.8 ahead | - |
| Boulder Toss | 14 | ~21.4 / ~14.6 | 22 | 6 | 2.0 | Projectile, 9.5 u/s, radius 0.5, range 8 | Clash weight 3: smashes through smaller projectiles |
| Ground Pound | 13 | ~19.9 / ~13.5 | 16 | 6 | 1.6 radial | Radius 2.3 burst around self, 3 ticks | Slow 90 ticks (1.5 s, move x0.65) |
| Stone Guard | - | - | - | - | - | Self | Stone Guard status for 80 ticks (1.33 s): takes x0.45 damage, x0.3 knockback, can't be flinched, repels dash-throughs from any side, moves x0.6 |
| Fault Line | 16 | ~24.4 / ~16.7 | 26 | 5 | 0.6 | Line 9 long (clipped at walls), 1.1 wide. Telegraphed for 30 ticks (500 ms), then a damaging band 1.4 deep sweeps outward at 20 u/s (~27 ticks to reach the end). | - |

Rough time-to-KO at equal levels: about 27 Ember Bolts to drop a Stoneback,
and 6 Boulder Tosses to drop an Emberlyn. Emberlyn wins by volume and
mobility; Stoneback wins by making each mistake expensive.

### Training Totem

It can't move, dash (cost 9999) or Focus (regen 0), and has mass 50. Its one
ability is **Acorn Shot**: startup 20 (333 ms), active 1, recovery 20,
cooldown 90 (1.5 s), projectile 7 u/s with range 10, power 3, hitstun 8,
hitstop 2, knockback 0.3. It is driven by a scripted `TrainingAI` (idle /
shoot every 100 ticks / hold guard). In training it can't be knocked out: its
HP refills and "Reset!" pops up.

### How damage numbers are derived

`damage = power x (ATK / DEF) x element multiplier` (plus mastery and
ruleset multipliers; see combat.md). At equal levels the level scale
cancels out, so the multipliers above hold at any level:

* Emberlyn -> Stoneback: 12/12 x 0.9 (ember > stone) = 0.90
* Emberlyn -> Emberlyn: 12/9 x 0.9 (ember > ember) = 1.20
* Stoneback -> Emberlyn: 12.5/9 x 1.1 (stone > ember) = 1.53
* Stoneback -> Stoneback: 12.5/12 x 1.0 = 1.04

## Mastery variants

Variants are sidegrades unlocked by ability mastery (1-10). They are never
strict upgrades, and all v0 variants are legal in Ranked.

| Ability | Variant | Unlocks at mastery | Changes |
| --- | --- | --- | --- |
| Ember Bolt | **Needle Bolt** | 3 | Speed 16 -> 22, radius 0.22 -> 0.17, power 7 -> 5.5. A thin, very fast poke. |
| Ember Bolt | **Blaze Bolt** | 6 | Speed 16 -> 12, radius 0.22 -> 0.32, power 7 -> 9, clash weight 1 -> 2. A heavy fireball that wins clashes. |

The other seven specials have no variants yet (Planned). Variants are
applied with copy-on-write overrides, so a variant never mutates the base
resource (this is unit-tested).

**Learn levels** are recorded in the data: Emberlyn has Ember Bolt and Cinder
Arc at level 1, Flash Strike at 4 and Heat Ring at 7; Stoneback has Boulder
Toss and Ground Pound at 1, Stone Guard at 5 and Fault Line at 8. They are
**not enforced in v0**: every creature spawns with its full default loadout
equipped, so the level-5 story kith use all four specials. Planned: gate the
loadout by learn level once more than four abilities exist per species.

## Befriending (trust-based acquisition)

There are no capture items. The one acquisition in v0, the Glimmerwood
Emberlyn, follows the brief's trust loop:

1. **Discover the habitat:** enter the clearing and see the kith.
2. **Observe:** approach softly (hold Shift; running nearby spooks it) and
   learn what it needs (it is cold and wet).
3. **Environmental interaction:** gather three kindlemoss and light the
   fire ring.
4. **Earn trust:** sit still while it creeps closer (moving resets it), then
   time "offer your hand" on a closing ring. The window is forgiving, there
   are three tries, and the beat can't fail.
5. **Optional challenge:** Planned (for example, a gentle spar for some
   species).
6. **Join:** name it. It joins your party at level 5 with bond 30, follows you
   in the world, and its journal entry becomes "Befriended".

The Mossling shows the observation half of the loop: it hears running
footsteps within 6.5 units and bolts, but a sneaking Warden can get close
and record it in the journal.

**Field journal:** each species is in one of three states: seen, observed or
befriended. Observed or befriended species show their full journal text
instead of the short description.

## Adding a kith

1. Add a `CreatureDefinition` `.tres` in `resources/creatures/` (stats,
   movement, dash, stamina and passive sub-resources, kit, sprite manifest).
   The registry picks it up automatically.
2. Build its abilities as `AbilityDefinition` `.tres` files from the existing
   components (projectile, melee, lunge, targeted area, self area, line
   wave, self status). Combat code changes are only needed for a genuinely
   new component type.
3. Generate sprites through `tools/sprite_forge` (the manifest contract is
   in architecture.md).
4. Add it to the Free Battle species list (`SPECIES` in
   `scripts/ui/title_screen.gd`) and the journal order (`ORDER` in
   `scripts/ui/journal_screen.gd`).
5. Run `tools/run_tests.sh` and the balance harness.
