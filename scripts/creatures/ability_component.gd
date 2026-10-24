class_name AbilityComponent
extends Resource
## Base class for reusable ability building blocks.
##
## Components are immutable data; any runtime state they create lives in the
## simulation (HitVolumes, Fighter fields). An ability runs its components at
## the phase given by `trigger`.

enum Trigger {
	STARTUP_BEGIN,  ## The tick the ability is activated.
	ACTIVE_BEGIN,  ## First active tick.
	ACTIVE_TICK,  ## Every active tick (continuous effects such as lunges).
	RECOVERY_BEGIN,  ## First recovery tick.
}

@export var trigger: Trigger = Trigger.ACTIVE_BEGIN


## Called by AbilitySystem at the component's trigger phase.
## `phase_tick` is the tick index within the current phase (0-based).
func execute(_sim: BattleSim, _caster: Fighter, _ability: AbilityDefinition, _phase_tick: int) -> void:
	pass


## Describes the danger zone for telegraphs and AI threat assessment.
## Returns {} when the component has no area worth telegraphing.
func telegraph_shape(_caster: Fighter, _ability: AbilityDefinition) -> Dictionary:
	return {}
