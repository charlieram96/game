extends Node
## Loads every species definition (autoload "Registry").

const CREATURE_DIR := "res://resources/creatures/"

var species: Dictionary = {}  # StringName -> CreatureDefinition


func _ready() -> void:
	reload()


func reload() -> void:
	species.clear()
	for file in DirAccess.get_files_at(CREATURE_DIR):
		# Exported builds list "x.tres.remap"; load the original path.
		var name := file.trim_suffix(".remap")
		if not name.ends_with(".tres") and not name.ends_with(".res"):
			continue
		var def := load(CREATURE_DIR + name) as CreatureDefinition
		if def:
			species[def.id] = def


func get_species(species_id: StringName) -> CreatureDefinition:
	if species.is_empty():
		reload()
	return species.get(species_id)


func make_creature(species_id: StringName, level: int, nickname: String = "") -> CreatureInstance:
	var def := get_species(species_id)
	if def == null:
		push_error("Unknown species %s" % species_id)
		return null
	var c := CreatureInstance.create(def, level)
	c.nickname = nickname
	return c
