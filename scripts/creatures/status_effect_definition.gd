class_name StatusEffectDefinition
extends Resource
## Data for a status effect (burn, slow, stone guard armor, ...).

enum Stacking { REFRESH, EXTEND, IGNORE }

@export var id: StringName
@export var display_name: String = ""
@export_multiline var description: String = ""
@export var icon_path: String = ""
@export var default_duration_ticks: int = 60
@export var stacking: Stacking = Stacking.REFRESH
@export var is_debuff: bool = true
@export_group("Periodic damage")
@export var tick_interval_ticks: int = 0  ## 0 = no periodic effect.
@export var tick_power: float = 0.0  ## Power per tick (uses the damage formula, no hitstun).
@export_group("Modifiers")
## Below 1 shortens dashes (max cells) and stretches their travel time.
@export var move_speed_mult: float = 1.0
@export var damage_taken_mult: float = 1.0
@export var knockback_taken_mult: float = 1.0
@export var flinch_immune: bool = false
@export var stun_immune: bool = false
@export var repels_dash_through: bool = false
@export var prevents_attacks: bool = false
@export var prevents_dash: bool = false
@export_group("Rules")
## Whether the status stays on a creature that is switched out.
@export var persists_on_switch: bool = false
@export_group("Presentation")
@export var vfx_id: StringName
@export var tint: Color = Color(1, 1, 1, 0)
