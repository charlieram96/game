class_name PlayerProfile
extends RefCounted
## Everything persisted about a player. Local JSON for v0; the same
## dictionary shape is what a backend would store (see docs/architecture.md).
## Never trust these values from a client in online play — the server owns them.

const VERSION := 1

var player_name: String = "Wren"
var story_step: String = "prologue"
var flags: Dictionary = {}
var party: Array[CreatureInstance] = []
## species id -> {"seen": bool, "befriended": bool, "observed": bool}
var journal: Dictionary = {}
var scene: String = ""
var position: Vector3 = Vector3.ZERO
var play_time_sec: float = 0.0
var created_unix: int = 0
var wins: int = 0
var losses: int = 0


func set_flag(flag: String, value: Variant = true) -> void:
	flags[flag] = value


func flag(flag: String, default: Variant = false) -> Variant:
	return flags.get(flag, default)


func lead_creature() -> CreatureInstance:
	return party[0] if not party.is_empty() else null


func journal_mark(species_id: StringName, key: String) -> bool:
	var sid := String(species_id)
	var entry: Dictionary = journal.get(sid, {"seen": false, "befriended": false, "observed": false})
	var changed := not bool(entry.get(key, false))
	entry[key] = true
	if key != "seen":
		entry["seen"] = true
	journal[sid] = entry
	return changed


func to_dict() -> Dictionary:
	var party_data: Array = []
	for c in party:
		party_data.append(c.to_dict())
	return {
		"version": VERSION,
		"player_name": player_name,
		"story_step": story_step,
		"flags": flags.duplicate(true),
		"party": party_data,
		"journal": journal.duplicate(true),
		"scene": scene,
		"position": [position.x, position.y, position.z],
		"play_time_sec": play_time_sec,
		"created_unix": created_unix,
		"wins": wins,
		"losses": losses,
	}


static func from_dict(d: Dictionary) -> PlayerProfile:
	var p := PlayerProfile.new()
	p.player_name = str(d.get("player_name", "Wren")).substr(0, 16)
	if p.player_name.strip_edges() == "":
		p.player_name = "Wren"
	p.story_step = str(d.get("story_step", "prologue"))
	p.flags = _ints_restored(d.get("flags", {}))
	p.party = []
	for c in d.get("party", []):
		if c is Dictionary:
			p.party.append(CreatureInstance.from_dict(c))
	p.journal = d.get("journal", {})
	p.scene = str(d.get("scene", ""))
	var pos: Array = d.get("position", [0, 0, 0])
	if pos.size() == 3:
		p.position = Vector3(float(pos[0]), float(pos[1]), float(pos[2]))
	p.play_time_sec = maxf(0.0, float(d.get("play_time_sec", 0.0)))
	p.created_unix = int(d.get("created_unix", 0))
	p.wins = maxi(0, int(d.get("wins", 0)))
	p.losses = maxi(0, int(d.get("losses", 0)))
	return p


## JSON has a single number type; restore whole-number values to ints so
## flags like "kindlemoss": 3 round-trip exactly.
static func _ints_restored(d: Dictionary) -> Dictionary:
	var out := {}
	for k in d.keys():
		var v: Variant = d[k]
		if typeof(v) == TYPE_FLOAT and is_equal_approx(v, roundf(v)) and absf(v) < 1e9:
			out[k] = int(v)
		elif v is Dictionary:
			out[k] = _ints_restored(v)
		else:
			out[k] = v
	return out
