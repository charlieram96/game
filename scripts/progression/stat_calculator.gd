class_name StatCalculator
extends RefCounted
## Derives CombatStats from (species, individual, ruleset).
##
## Stats scale linearly around level 50: level 1 ≈ 41%, level 50 = 100%,
## level 100 = 160% of the species' base values. Ranked normalizes every
## creature to the ruleset's level, so stored progression never changes the
## result.

const LEVEL_SLOPE := 0.012


static func level_scale(level: int) -> float:
	return 1.0 + float(level - 50) * LEVEL_SLOPE


static func compute(species: CreatureDefinition, creature: CreatureInstance, ruleset: BattleRuleset) -> CombatStats:
	var s := CombatStats.new()
	s.species = species
	s.level_used = ruleset.effective_level(creature.level)
	var k := level_scale(s.level_used)
	s.max_hp = roundf(species.base_hp * k)
	s.attack = species.base_attack * k
	s.defense = species.base_defense * k
	# Movement, dash and stamina define species identity and are never
	# level-scaled, so ranked keeps creatures distinct but fair.
	s.movement = species.movement
	s.dash = species.dash
	s.stamina = species.stamina
	s.passive = species.passive
	s.hurt_radius = species.hurt_radius
	s.basic = species.basic_attack
	s.abilities = []
	for i in CreatureInstance.LOADOUT_SIZE:
		var ability_id: StringName = creature.equipped[i] if i < creature.equipped.size() else &""
		var base := species.find_ability(ability_id) if ability_id != &"" else null
		if base == null:
			s.abilities.append(null)
			continue
		var variant_id := creature.selected_variant(ability_id)
		var resolved := base
		if variant_id != &"":
			var variant := base.get_variant(variant_id)
			var unlocked := variant != null and creature.mastery_level(ability_id) >= variant.unlock_mastery
			var legal := variant != null and (variant.competitive_legal or ruleset.allow_illegal_variants)
			if unlocked and legal:
				resolved = base.with_variant(variant_id)
		s.abilities.append(resolved)
		s.power_mults[ability_id] = Mastery.power_mult(creature.mastery_level(ability_id), ruleset)
	if s.basic:
		s.power_mults[s.basic.id] = Mastery.power_mult(creature.mastery_level(s.basic.id), ruleset)
	return s


## Level difference summary shown before casual duels.
static func describe_level_gap(a: CreatureInstance, b: CreatureInstance) -> String:
	var gap := a.level - b.level
	if gap == 0:
		return "Even levels"
	if gap > 0:
		return "+%d levels advantage" % gap
	return "%d levels disadvantage" % gap
