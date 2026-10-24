class_name StaminaSystem
extends RefCounted
## Stamina and Focus.
##
## Stamina never regenerates by itself. Holding Focus roots the creature:
##   FOCUS_ENTER (commitment, no regen) -> FOCUSING (regen) -> FOCUS_EXIT.
## Attacks and dashes are unavailable throughout; any damage interrupts.

const SM := FighterSM.State


static func can_afford(f: Fighter, cost: float) -> bool:
	return f.stamina + 0.0001 >= cost


## Spends stamina; with `allow_partial` it drains to zero instead of failing.
static func spend(f: Fighter, amount: float, allow_partial: bool = false) -> bool:
	if amount <= 0.0:
		return true
	if not allow_partial and not can_afford(f, amount):
		return false
	f.stamina = clampf(f.stamina - amount, 0.0, f.max_stamina())
	return true


static func enter_ticks(f: Fighter) -> int:
	var mult := f.stats.passive.focus_transition_mult if f.stats.passive else 1.0
	return maxi(1, int(round(f.stats.stamina.focus_enter_ticks * mult)))


static func exit_ticks(f: Fighter) -> int:
	var mult := f.stats.passive.focus_transition_mult if f.stats.passive else 1.0
	return maxi(1, int(round(f.stats.stamina.focus_exit_ticks * mult)))


static func try_enter(sim: BattleSim, f: Fighter) -> bool:
	f.focus_released = false
	f.vel = Vector2.ZERO
	if not sim.set_state(f, SM.FOCUS_ENTER, enter_ticks(f)):
		return false
	sim.emit(BattleEvent.FOCUS_START, f, -1, f.pos, {})
	return true


## Called every FOCUSING tick.
static func regen(sim: BattleSim, f: Fighter) -> void:
	var before := f.stamina
	var max_s := f.max_stamina()
	f.stamina = minf(max_s, f.stamina + f.stats.stamina.focus_rate * CombatConst.TICK_DT)
	f.record["focus_ticks"] += 1
	if before < max_s and f.stamina >= max_s:
		sim.emit(BattleEvent.STAMINA_FULL, f, -1, f.pos, {})


## Benched teammates slowly recover stamina (a reason to tag out).
static func bench_regen(f: Fighter) -> void:
	f.stamina = minf(f.max_stamina(), f.stamina + f.stats.stamina.focus_rate * 0.25 * CombatConst.TICK_DT)


static func interrupt(sim: BattleSim, f: Fighter) -> void:
	if FighterSM.is_focusing(f.state):
		sim.set_state(f, SM.IDLE)
		sim.emit(BattleEvent.FOCUS_INTERRUPTED, f, -1, f.pos, {})
