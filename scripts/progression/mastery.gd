class_name Mastery
extends RefCounted
## Ability mastery (levels 1-10), earned by using abilities, training and
## combat milestones. Mastery unlocks sidegrade variants and cosmetics; its
## small numeric bonus applies only where the ruleset allows it (never ranked).

const MAX_LEVEL := 10
## Bonus power per mastery level above 1 (PvE / casual only).
const PVE_POWER_PER_LEVEL := 0.015

const XP_PER_USE := 2
const XP_PER_HIT := 3
const XP_PER_KO_BLOW := 10


static func xp_to_next(level: int) -> int:
	if level >= MAX_LEVEL:
		return 0
	return 20 + level * level * 8


## Adds mastery XP to one ability; returns the new levels reached.
static func add_xp(creature: CreatureInstance, ability_id: StringName, amount: int) -> Array[int]:
	var gained: Array[int] = []
	if amount <= 0:
		return gained
	var m: Dictionary = creature.mastery.get(ability_id, {"level": 1, "xp": 0})
	var lvl := int(m.get("level", 1))
	var cur := int(m.get("xp", 0)) + amount
	while lvl < MAX_LEVEL and cur >= xp_to_next(lvl):
		cur -= xp_to_next(lvl)
		lvl += 1
		gained.append(lvl)
	if lvl >= MAX_LEVEL:
		cur = 0
	creature.mastery[ability_id] = {"level": lvl, "xp": cur}
	return gained


static func power_mult(level: int, ruleset: BattleRuleset) -> float:
	if ruleset == null or not ruleset.allow_mastery_bonuses:
		return 1.0
	return 1.0 + PVE_POWER_PER_LEVEL * float(clampi(level, 1, MAX_LEVEL) - 1)


## Variants of `ability` the creature may select under `ruleset`.
static func available_variants(creature: CreatureInstance, ability: AbilityDefinition, ruleset: BattleRuleset = null) -> Array[AbilityVariant]:
	var out: Array[AbilityVariant] = []
	var lvl := creature.mastery_level(ability.id)
	for v in ability.variants:
		if lvl < v.unlock_mastery:
			continue
		if ruleset != null and ruleset.kind == BattleRuleset.Kind.RANKED and not v.competitive_legal:
			continue
		out.append(v)
	return out


## Converts per-ability usage counters from a finished battle into mastery XP.
## `usage` maps ability id -> {"uses": int, "hits": int, "ko": int}.
static func award_from_battle(creature: CreatureInstance, usage: Dictionary) -> Dictionary:
	var level_ups := {}
	for ability_id in usage.keys():
		var u: Dictionary = usage[ability_id]
		var amount := int(u.get("uses", 0)) * XP_PER_USE + int(u.get("hits", 0)) * XP_PER_HIT + int(u.get("ko", 0)) * XP_PER_KO_BLOW
		var gained := add_xp(creature, ability_id, amount)
		if not gained.is_empty():
			level_ups[ability_id] = gained
	return level_ups
