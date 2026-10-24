class_name PassiveDefinition
extends Resource
## A species' passive trait, expressed as data-driven modifiers.

@export var id: StringName
@export var display_name: String = ""
@export_multiline var description: String = ""
## Multiplies Focus enter/exit commitment (0.6 = 40% faster).
@export var focus_transition_mult: float = 1.0
@export var knockback_taken_mult: float = 1.0
@export var hitstun_taken_mult: float = 1.0
## Multiplies the dash-through stun this creature inflicts.
@export var dash_through_stun_mult: float = 1.0
## Extra dash speed (fraction) while stamina is below 30%.
@export var low_stamina_speed_bonus: float = 0.0
