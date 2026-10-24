class_name CreatureDefinition
extends Resource
## Immutable species data for a kith. Individual creatures (level, mastery,
## nickname) are CreatureInstance objects that reference a definition by id.

@export var id: StringName
@export var display_name: String = ""
@export_multiline var description: String = ""
@export var element: StringName = &"neutral"
@export var archetype: String = ""

@export_group("Base stats (values at level 50)")
@export var base_hp: float = 100.0
@export var base_attack: float = 10.0
@export var base_defense: float = 10.0

@export_group("Body and movement")
@export var movement: MovementProfile
@export var dash: DashProfile
@export var stamina: StaminaProfile
## Radius of the hurtbox (usually slightly larger than the collision radius).
@export var hurt_radius: float = 0.5

@export_group("Kit")
@export var basic_attack: AbilityDefinition
## Abilities this species can learn, with the level each becomes available.
@export var learnable: Array[AbilityDefinition] = []
## Not enforced in v0: every kith fights with its full kit so the prototype
## shows the whole moveset (see docs/roadmap.md).
@export var learn_levels: PackedInt32Array = PackedInt32Array()
@export var default_loadout: Array[StringName] = []
@export var passive: PassiveDefinition

@export_group("Presentation")
@export var sprite_manifest: String = ""
@export var portrait_manifest: String = ""
@export var icon_color: Color = Color.WHITE
@export var cry_sfx: StringName = &""
## Height of the sprite's visual center above the ground (for overhead UI).
@export var visual_height: float = 1.2

@export_group("World and journal")
@export var habitat: String = ""
@export_multiline var journal_entry: String = ""


func find_ability(ability_id: StringName) -> AbilityDefinition:
	if basic_attack and basic_attack.id == ability_id:
		return basic_attack
	for a in learnable:
		if a.id == ability_id:
			return a
	return null


func learn_level_of(ability_id: StringName) -> int:
	for i in learnable.size():
		if learnable[i].id == ability_id:
			return learn_levels[i] if i < learn_levels.size() else 1
	return 1


func abilities_known_at(level: int) -> Array[StringName]:
	var out: Array[StringName] = []
	for i in learnable.size():
		var need := learn_levels[i] if i < learn_levels.size() else 1
		if level >= need:
			out.append(learnable[i].id)
	return out
