class_name LungeComponent
extends AbilityComponent
## Moves the caster forward during the active phase (stops at bodies/walls).

@export var distance: float = 2.0
@export var ticks: int = 6
@export var stop_on_hit: bool = true


func execute(sim: BattleSim, caster: Fighter, _ability: AbilityDefinition, _phase_tick: int) -> void:
	caster.lunge_dir = caster.ability_dir
	caster.lunge_ticks = maxi(1, ticks)
	caster.lunge_speed = distance / float(caster.lunge_ticks)
	caster.lunge_stop_on_hit = stop_on_hit
	sim.emit(BattleEvent.LUNGE, caster, -1, caster.pos, {"dir": caster.lunge_dir, "distance": distance})
