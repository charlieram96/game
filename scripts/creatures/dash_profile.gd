class_name DashProfile
extends Resource
## Four-direction dash attributes for a species.

enum DashType {
	STANDARD,
	FAST,  ## Longer and quicker; brief intangibility to projectiles.
	ARMORED,  ## Short; ignores flinch and takes reduced damage while active.
}

enum CollisionBehavior {
	PASS_THROUGH,  ## Passes through enemy bodies (can trigger dash-through stun).
	STOP_AT_BODY,  ## Stops on contact with enemy bodies.
}

@export var dash_type: DashType = DashType.STANDARD
@export var distance: float = 3.0  ## World units travelled during the active phase.
@export var duration_ticks: int = 11  ## Active phase length.
@export var startup_ticks: int = 2
@export var recovery_ticks: int = 8
@export var stamina_cost: float = 25.0
@export var collision_behavior: CollisionBehavior = CollisionBehavior.PASS_THROUGH
@export var dash_through_stun_ticks: int = CombatConst.DASH_THROUGH_STUN_TICKS
@export_group("Traits")
## FAST: number of active ticks during which projectiles pass through.
@export var projectile_intangible_ticks: int = 0
## ARMORED: damage multiplier while the dash is active.
@export var armor_damage_mult: float = 1.0
@export var flinch_immune_while_active: bool = false
@export var trait_name: String = ""
@export_multiline var trait_description: String = ""


## Dash speed in world units per second (derived: distance / duration).
func speed() -> float:
	return distance / maxf(1.0, float(duration_ticks)) * CombatConst.TICK_RATE


func speed_per_tick() -> float:
	return distance / maxf(1.0, float(duration_ticks))
