class_name StatusApplication
extends Resource
## "Apply this status for this long" — attached to hits and buff components.

@export var status: StatusEffectDefinition
## 0 = use the status' default duration.
@export var duration_ticks: int = 0


func resolved_duration() -> int:
	if duration_ticks > 0:
		return duration_ticks
	return status.default_duration_ticks if status else 0
