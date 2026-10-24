class_name CombatStats
extends RefCounted
## The numbers one creature fights with in one battle, derived from its
## species definition, its individual progression and the battle ruleset.

var species: CreatureDefinition
var level_used: int = 50
var max_hp: float = 100.0
var attack: float = 10.0
var defense: float = 10.0
var movement: MovementProfile
var dash: DashProfile
var stamina: StaminaProfile
var passive: PassiveDefinition
var hurt_radius: float = 0.5
var basic: AbilityDefinition
## Four equipped specials (variants already applied). May contain nulls.
var abilities: Array[AbilityDefinition] = []
## ability id -> power multiplier from mastery (1.0 in ranked).
var power_mults: Dictionary = {}


func collision_radius() -> float:
	return movement.collision_radius if movement else 0.45


func power_mult(ability_id: StringName) -> float:
	return float(power_mults.get(ability_id, 1.0))
