class_name SurgeSystem
extends RefCounted
## Surge: the four-stage meter that pays for specials.
##
## Specials have no cooldowns. Each one costs whole stages of Surge (1 to 4:
## the stronger the move, the more stages), and a creature can use any
## special it can pay for, as often as it can pay. Surge is earned by
## fighting: landing hits (basic strings build it fastest), connecting rams,
## and a trickle for every dash. Basic attacks are free.

const PER_STAGE := CombatConst.SURGE_PER_STAGE


static func max_surge() -> float:
	return PER_STAGE * CombatConst.SURGE_STAGES


## Full stages banked.
static func stages(f: Fighter) -> int:
	return int(floor(f.surge / PER_STAGE + 0.0001))


static func can_afford(f: Fighter, cost_stages: int) -> bool:
	return cost_stages <= 0 or stages(f) >= cost_stages


static func spend(f: Fighter, cost_stages: int) -> void:
	if cost_stages <= 0:
		return
	f.surge = maxf(0.0, f.surge - PER_STAGE * cost_stages)
	f.record["surge_spent"] += cost_stages


## Adds Surge and announces each stage that fills.
static func gain(sim: BattleSim, f: Fighter, amount: float, source: StringName) -> void:
	if amount <= 0.0 or f.is_ko() or f.surge >= max_surge():
		return
	if f.stats.passive:
		amount *= f.stats.passive.surge_gain_mult
	var before := stages(f)
	var after_gain := minf(max_surge(), f.surge + amount)
	f.record["surge_gained"] += after_gain - f.surge
	f.surge = after_gain
	var after := stages(f)
	if after > before:
		sim.emit(BattleEvent.SURGE_STAGE, f, -1, f.pos, {"stages": after, "source": source, "full": after >= CombatConst.SURGE_STAGES})


## A hit that connected (not blocked).
static func on_hit(sim: BattleSim, attacker: Fighter, ability: AbilityDefinition) -> void:
	if attacker == null or ability == null:
		return
	var amount := CombatConst.SURGE_PER_BASIC_HIT if ability.kind == AbilityDefinition.Kind.BASIC else CombatConst.SURGE_PER_SPECIAL_HIT
	gain(sim, attacker, amount, ability.id)
