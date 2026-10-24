class_name CreatureInstance
extends RefCounted
## One individual kith owned by a player (or spawned in the wild).
##
## Holds only progression and identity. Combat numbers are always derived by
## StatCalculator for a given BattleRuleset, so ranked normalization never
## touches stored progression.

const MAX_LEVEL := 100
const LOADOUT_SIZE := 4

var uid: String = ""
var species_id: StringName = &""
var nickname: String = ""
var level: int = 5
var xp: int = 0
var bond: int = 0  ## Trust earned with its Warden (0-100).
var equipped: Array[StringName] = []
## ability id -> {"level": int, "xp": int}
var mastery: Dictionary = {}
## ability id -> selected variant id (&"" = base)
var variants: Dictionary = {}
var met_location: String = ""
var met_story_step: String = ""


static func create(species: CreatureDefinition, at_level: int, rng_seed: int = 0) -> CreatureInstance:
	var c := CreatureInstance.new()
	c.uid = _make_uid(species.id, rng_seed)
	c.species_id = species.id
	c.level = clampi(at_level, 1, MAX_LEVEL)
	c.equipped = []
	for ability_id in species.default_loadout:
		c.equipped.append(ability_id)
	for ability_id in c.equipped:
		c.mastery[ability_id] = {"level": 1, "xp": 0}
	if species.basic_attack:
		c.mastery[species.basic_attack.id] = {"level": 1, "xp": 0}
	return c


static func _make_uid(species: StringName, rng_seed: int) -> String:
	var rng := RandomNumberGenerator.new()
	if rng_seed != 0:
		rng.seed = rng_seed
	else:
		rng.randomize()
	return "%s-%08x" % [species, rng.randi()]


func display_name(species: CreatureDefinition = null) -> String:
	if nickname != "":
		return nickname
	return species.display_name if species else String(species_id)


func mastery_level(ability_id: StringName) -> int:
	var m: Dictionary = mastery.get(ability_id, {})
	return int(m.get("level", 1))


func selected_variant(ability_id: StringName) -> StringName:
	return StringName(variants.get(ability_id, &""))


func to_dict() -> Dictionary:
	var eq: Array = []
	for a in equipped:
		eq.append(String(a))
	var mast := {}
	for k in mastery.keys():
		mast[String(k)] = {"level": int(mastery[k].get("level", 1)), "xp": int(mastery[k].get("xp", 0))}
	var vars := {}
	for k in variants.keys():
		vars[String(k)] = String(variants[k])
	return {
		"uid": uid,
		"species": String(species_id),
		"nickname": nickname,
		"level": level,
		"xp": xp,
		"bond": bond,
		"equipped": eq,
		"mastery": mast,
		"variants": vars,
		"met_location": met_location,
		"met_story_step": met_story_step,
	}


static func from_dict(d: Dictionary) -> CreatureInstance:
	var c := CreatureInstance.new()
	c.uid = str(d.get("uid", ""))
	c.species_id = StringName(str(d.get("species", "")))
	c.nickname = str(d.get("nickname", ""))
	c.level = clampi(int(d.get("level", 1)), 1, MAX_LEVEL)
	c.xp = maxi(0, int(d.get("xp", 0)))
	c.bond = clampi(int(d.get("bond", 0)), 0, 100)
	c.equipped = []
	for a in d.get("equipped", []):
		c.equipped.append(StringName(str(a)))
	c.mastery = {}
	var mast: Dictionary = d.get("mastery", {})
	for k in mast.keys():
		var m: Dictionary = mast[k]
		c.mastery[StringName(str(k))] = {
			"level": clampi(int(m.get("level", 1)), 1, Mastery.MAX_LEVEL),
			"xp": maxi(0, int(m.get("xp", 0))),
		}
	c.variants = {}
	var vars: Dictionary = d.get("variants", {})
	for k in vars.keys():
		c.variants[StringName(str(k))] = StringName(str(vars[k]))
	c.met_location = str(d.get("met_location", ""))
	c.met_story_step = str(d.get("met_story_step", ""))
	return c
