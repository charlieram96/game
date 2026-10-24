class_name AbilityVariant
extends Resource
## A mastery-unlocked sidegrade of an ability (never a strict upgrade).
##
## `overrides` maps property paths to values applied to a copy of the base
## ability, e.g. {"components/0/speed": 24.0, "components/0/hit/power": 5.0}.
## Paths walk resource properties and array indices separated by "/".

@export var id: StringName
@export var display_name: String = ""
@export_multiline var description: String = ""
@export var unlock_mastery: int = 3
## Ranked play only allows variants marked legal (all sidegrades should be).
@export var competitive_legal: bool = true
@export var overrides: Dictionary = {}
@export_group("Cosmetic")
@export var vfx_tint: Color = Color(1, 1, 1, 1)
