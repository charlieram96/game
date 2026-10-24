class_name SelfStatusComponent
extends AbilityComponent
## Applies a status to the caster (e.g. Stone Guard's damage reduction).

@export var status: StatusApplication


func execute(sim: BattleSim, caster: Fighter, _ability: AbilityDefinition, _phase_tick: int) -> void:
	StatusSystem.apply(sim, caster, status, caster)
