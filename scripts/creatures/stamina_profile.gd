class_name StaminaProfile
extends Resource
## Stamina never regenerates on its own: the creature must hold Focus.

@export var max_stamina: float = 100.0
@export var focus_rate: float = 20.0  ## Stamina recovered per second while FOCUSING.
@export var focus_enter_ticks: int = CombatConst.DEFAULT_FOCUS_ENTER_TICKS
@export var focus_exit_ticks: int = CombatConst.DEFAULT_FOCUS_EXIT_TICKS
## Stamina lost per point of damage absorbed by Guard.
@export var guard_stamina_factor: float = 1.0
