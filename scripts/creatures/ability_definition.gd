class_name AbilityDefinition
extends Resource
## Immutable definition of an attack or special ability.
##
## Behaviour is composed from reusable AbilityComponents (projectile, melee,
## lunge, targeted area, self area, line wave, self status). Every ability
## shares the same phase model:
##   startup (telegraphed windup) -> active (can hit) -> recovery (vulnerable)
## Nothing has a cooldown: specials are paid for in stages of Surge (see
## SurgeSystem), basic attacks are free.

enum Kind { BASIC, SPECIAL }

enum AimMode {
	DIRECTION,  ## Uses the aim direction (projectiles, cones, lines).
	TARGET_POINT,  ## Uses an aimed ground point clamped to max_range.
	SELF,  ## Centered on the caster.
}

@export var id: StringName
@export var display_name: String = ""
@export_multiline var description: String = ""
@export var element: StringName = &"neutral"
@export var kind: Kind = Kind.SPECIAL
@export var aim_mode: AimMode = AimMode.DIRECTION
@export var icon_path: String = ""

@export_group("Frame data (ticks @ 60 Hz)")
@export var startup_ticks: int = 6
@export var active_ticks: int = 3
@export var recovery_ticks: int = 10
## Surge stages spent to use it (0-4; 0 = free, like basic attacks).
@export_range(0, 4) var surge_stages: int = 0
@export var stamina_cost: float = 0.0
## Max aim distance for TARGET_POINT abilities; informational for others.
@export var max_range: float = 6.0

@export_group("Rules")
@export var can_aim_during_startup: bool = true
@export var armor_during_startup: bool = false
@export var armor_during_active: bool = false
## Recovery tick from which a dash may cancel the recovery (-1 = never).
@export var dash_cancel_from_recovery_tick: int = -1
## Basic-attack strings: a press during the first `chain_window_ticks` of
## recovery chains into `chain_next`.
@export var chain_next: AbilityDefinition
@export var chain_window_ticks: int = 0
## Show a ground telegraph to both players during startup.
@export var telegraph: bool = false
@export var components: Array[AbilityComponent] = []

@export_group("Presentation")
## Sprite animation used while casting: &"cast" or &"melee".
@export var anim: StringName = &"cast"
@export var cast_sfx: StringName = &""
@export var cast_vfx: StringName = &""

@export_group("Mastery")
@export var variants: Array[AbilityVariant] = []

var _variant_cache: Dictionary = {}


func total_ticks() -> int:
	return startup_ticks + active_ticks + recovery_ticks


func get_variant(variant_id: StringName) -> AbilityVariant:
	for v in variants:
		if v.id == variant_id:
			return v
	return null


## Returns a copy of this ability with a variant's overrides applied
## (copy-on-write along each overridden path). Cached per variant.
func with_variant(variant_id: StringName) -> AbilityDefinition:
	if variant_id == &"" or variant_id == &"base":
		return self
	if _variant_cache.has(variant_id):
		return _variant_cache[variant_id]
	var variant := get_variant(variant_id)
	if variant == null:
		push_warning("Ability %s has no variant %s" % [id, variant_id])
		return self
	var copy: AbilityDefinition = duplicate(false)
	copy.components = components.duplicate()
	copy.variants = []
	for path: String in variant.overrides.keys():
		_apply_override(copy, path.split("/"), variant.overrides[path])
	_variant_cache[variant_id] = copy
	return copy


static func _apply_override(root: Object, parts: PackedStringArray, value: Variant) -> void:
	var current: Variant = root
	for i in range(parts.size() - 1):
		var key := parts[i]
		var next: Variant
		if current is Array:
			var arr: Array = current
			var idx := int(key)
			var item: Variant = arr[idx]
			if item is Resource:
				item = (item as Resource).duplicate(false)
				arr[idx] = item
			next = item
		else:
			var obj: Object = current
			next = obj.get(key)
			if next is Resource:
				next = (next as Resource).duplicate(false)
				obj.set(key, next)
			elif next is Array:
				next = (next as Array).duplicate()
				obj.set(key, next)
		current = next
	var last := parts[parts.size() - 1]
	if current is Array:
		(current as Array)[int(last)] = value
	else:
		(current as Object).set(last, value)
