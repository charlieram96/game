class_name DashProfile
extends Resource
## How a species dashes. Dashes are the only way to move in battle: straight
## along a board direction, 1..max_cells cells, landing on a cell centre.
##
## Timeline: windup (startup_ticks; the creature gathers onto its cell) ->
## travel (eased out: explosive start, braking finish) -> recovery (a
## chained dash may start after chain_after_ticks).

enum DashType {
	STANDARD,
	FAST,  ## Longer and quicker; brief intangibility to projectiles.
	ARMORED,  ## Short; ignores flinch and takes reduced damage while active.
}

enum CollisionBehavior {
	PASS_THROUGH,  ## Passes through enemy bodies (rams them).
	STOP_AT_BODY,  ## Stops on contact with enemy bodies.
}

@export var dash_type: DashType = DashType.STANDARD
## Longest dash, in cells.
@export var max_cells: int = 4
@export_group("Stamina")
## Cost = stamina_base + stamina_per_cell × cells travelled.
@export var stamina_base: float = 6.0
@export var stamina_per_cell: float = 5.0
@export_group("Timing")
@export var startup_ticks: int = 3
## Travel time = travel_ticks_base + travel_ticks_per_cell × distance.
@export var travel_ticks_base: float = 4.0
@export var travel_ticks_per_cell: float = 1.8
## Ease-out exponent of the travel curve (higher = harder brake at the end).
@export var ease_power: float = 2.4
@export var recovery_ticks: int = 7
## Ticks into recovery after which another dash may start (dash chaining).
@export var chain_after_ticks: int = 3
@export_group("Ram")
## Damage power when the dash passes through a foe (same formula as hits:
## power × attack / defense), followed by a short daze.
@export var ram_power: float = 6.0
@export var collision_behavior: CollisionBehavior = CollisionBehavior.PASS_THROUGH
@export var dash_through_stun_ticks: int = CombatConst.DASH_THROUGH_STUN_TICKS
@export_group("Traits")
## FAST: number of travel ticks during which projectiles pass through.
@export var projectile_intangible_ticks: int = 0
## ARMORED: damage multiplier while the dash is active.
@export var armor_damage_mult: float = 1.0
@export var flinch_immune_while_active: bool = false
@export var trait_name: String = ""
@export_multiline var trait_description: String = ""


func cost_for(cells: int) -> float:
	if cells <= 0:
		return 0.0
	return stamina_base + stamina_per_cell * cells


## Cheapest possible dash (one cell).
func min_cost() -> float:
	return cost_for(1)


func travel_ticks_for(distance: float) -> int:
	return maxi(2, int(round(travel_ticks_base + travel_ticks_per_cell * distance)))


## Fraction of the path covered after `u` (0..1) of the travel time.
func travel_fraction(u: float) -> float:
	return 1.0 - pow(1.0 - clampf(u, 0.0, 1.0), ease_power)
