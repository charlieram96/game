class_name ElementChart
extends Resource
## Elemental strengths and weaknesses, as data.
##
## `table` keys are "attacker>defender" (e.g. "ember>grove") with multipliers.
## Missing pairs are neutral (1.0). Multipliers are deliberately mild so
## matchups shape strategy without deciding fights on their own.

const DEFAULT_PATH := "res://resources/balance/element_chart.tres"
const EFFECTIVE_THRESHOLD := 1.05
const RESISTED_THRESHOLD := 0.95

@export var table: Dictionary = {}
@export var display_names: Dictionary = {}
@export var colors: Dictionary = {}

static var _default: ElementChart = null


static func get_default() -> ElementChart:
	if _default == null:
		if ResourceLoader.exists(DEFAULT_PATH):
			_default = load(DEFAULT_PATH)
		else:
			_default = ElementChart.new()
	return _default


func multiplier_of(attacker: StringName, defender: StringName) -> float:
	var key := "%s>%s" % [attacker, defender]
	return float(table.get(key, 1.0))


static func multiplier(attacker: StringName, defender: StringName) -> float:
	return get_default().multiplier_of(attacker, defender)


static func effectiveness_label(mult: float) -> String:
	if mult >= EFFECTIVE_THRESHOLD:
		return "Effective!"
	if mult <= RESISTED_THRESHOLD:
		return "Resisted"
	return ""
