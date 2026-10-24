# Progression and rulesets

Code: `scripts/progression/` (Leveling, Mastery, BattleRuleset,
StatCalculator, CombatStats), `scripts/creatures/creature_instance.gd`,
`scripts/core/game.gd` (rewards) and `scripts/persistence/` (saves).

Each kith has two independent progression tracks: **creature level
(1-100)** and **ability mastery (1-10 per ability)**. Neither may ever be a
numeric advantage in Ranked play.

## Creature level

**XP to the next level:** `xp_to_next(L) = round(12 + 6 x L^1.45)`. Level
100 is the cap, and XP resets to 0 there.

| From level | XP to next | Total XP to reach the next level |
| --- | --- | --- |
| 1 | 18 | 18 |
| 5 | 74 | 219 |
| 10 | 181 | ~897 |
| 20 | 474 | ~4,244 |
| 30 | 844 | ~10,964 |
| 50 | 1,756 | ~37,076 |
| 75 | 3,152 | ~98,609 |
| 99 | 4,709 | ~193,338 (level 100) |

**Battle XP** (story/PvE battles): `base = 18 + 4 x loser_level`, multiplied
by `clamp(1 + 0.08 x (loser_level - winner_level), 0.25, 2.0)`, and by 0.35
on a loss, with a minimum of 1. Beating a much lower-level foe is worth a
quarter of the base; beating a much higher one is worth up to double. For
example, winning the Kindling duel at level 5 against level 5 gives 38 XP
(74 are needed for level 6), and a loss gives 13.

**What level changes:** HP, ATK and DEF scale linearly around level 50:

```
level_scale(L) = 1 + (L - 50) x 0.012
  level 1 -> 0.412   level 5 -> 0.46   level 25 -> 0.70
  level 50 -> 1.00   level 75 -> 1.30  level 100 -> 1.60
max_hp = round(base_hp x scale), attack = base_attack x scale, defense = base_defense x scale
```

The story Emberlyn (level 5) therefore has 51 HP, and Biscuit (level 5) has
78 HP. Movement, dash, stamina, passive and kit are never level-scaled.
They are the species' identity.

Planned uses of level, from the brief: unlocking abilities (learn levels
already exist in the data but aren't enforced; see kith.md), evolution
eligibility, exploration capabilities and training opportunities.

## Ability mastery

Mastery is tracked per ability (the basic attack included) in
`CreatureInstance.mastery`.

| Source (implemented) | Mastery XP |
| --- | --- |
| Each use of the ability | 2 |
| Each hit it lands | 3 |
| Each knockout blow | 10 |

Mastery XP needed for the next level is `20 + 8 x level^2`: 28, 52, 92,
148, 220, 308, 412, 532 and 668, for a total of 2,460 from mastery 1 to 10.
Usage is counted by the simulation (`Fighter.record.ability_usage`) and
converted after Free Battles and story battles (not Versus, and not the
tutorial).

**What mastery gives:**

* **Variants (sidegrades):** unlocked at a mastery threshold and selectable
  per ability. Example: Ember Bolt's Needle Bolt (mastery 3) is faster,
  thinner and weaker, while Blaze Bolt (mastery 6) is slower, bigger and
  stronger, and wins clashes. A variant must be a trade-off, never a strict
  upgrade. Each variant carries a `competitive_legal` flag, and Ranked only
  allows legal ones.
* **PvE / Casual power bonus:** +1.5% power per mastery level above 1 (up
  to +13.5% at mastery 10). It is **never applied in Ranked**.
* Planned: alternate animations and cosmetic effects; mastery from training
  challenges, creature-specific exercises and exploration feats; a UI for
  choosing variants (in v0 the variant is stored on the creature but there is
  no selection screen yet).

## Rulesets

`StatCalculator.compute(species, creature, ruleset)` builds the numbers a
creature fights with. Normalization is computed per battle and never
written back to the stored creature. A unit test checks that stored levels
are untouched after ranked stats are computed.

| | Ranked | Casual duel | PvE (Adventure) |
| --- | --- | --- | --- |
| Level used | Normalized to 50 | Real level | Real level |
| Mastery power bonus | No | Yes | Yes |
| Variants | Unlocked and competitive-legal only | Any unlocked | Any unlocked |
| Species identity (movement, dash, stamina, kit, passive) | Preserved | Preserved | Preserved |
| Level gap | - | Shown before the duel (`describe_level_gap`) | - |
| Extra knobs | - | - | `enemy_hp_mult` and `enemy_damage_mult` for bosses (1.0 in v0) |
| Paid advantages | None, by design | None | None |

**v0 modes:**

| Mode | Ruleset | Notes |
| --- | --- | --- |
| Free Battle | Ranked (normalized to level 50), 120 s | Your party kith if you own that species. Awards mastery, wins and losses. |
| Local Versus | Ranked, 120 s | Two humans. No progression. |
| Training (tutorial) | PvE, no timer, no countdown | Level 5 totem that can't be knocked out. No rewards. |
| The Kindling duel | PvE, 150 s | Biscuit's level = max(5, your kith's level). Awards XP and mastery. |
| Casual duel | - | Planned (needs other players) |

## Bond

`CreatureInstance.bond` (0-100) records the trust between a kith and its
Warden. The befriended Emberlyn starts at 30. It has **no gameplay effect in
v0** (Planned: story and field uses, never ranked stats).

## Saves

* Local JSON at `user://wildbound_save.json`, written atomically (a temp
  file, then a rename). Settings are saved separately in
  `user://settings.cfg`.
* The profile holds the player name, party (creature instances), story
  flags and step, journal, world position, play time, and wins and losses.
* Loading **validates and clamps everything**: levels to 1-100, mastery to
  1-10, bond to 0-100, no negative XP. A corrupt file is rejected rather
  than half-loaded. Whole numbers are restored to ints after the JSON round
  trip. All of this is covered by tests.

## Server authority (principle)

In v0 everything runs locally, so a player can edit their own save. This is
acceptable for an offline prototype and **must not carry over to online
play**. The rule for every online feature:

> Never trust client-provided inventory, XP, damage, positions or match
> results.

* The client only ever sends `InputCommand`s. The battle server runs the
  same `BattleSim` and decides positions, dash direction and stamina,
  attack legality, hits, damage, stuns, cooldowns and outcomes.
* XP, mastery and rewards are granted by the server from the server's own
  battle record (`Fighter.record`), transactionally, and stored
  server-side. `PlayerProfile.to_dict()` is the intended shared schema.
* Ranked normalization runs on the server from server-owned creature data.

See architecture.md for the networking phases.
