class_name Fighter
extends RefCounted
## Runtime combat state of one creature in a battle.
##
## Pure data plus small helpers; all rules live in the systems
## (movement, dash, stamina, abilities, damage). Positions are on the XZ
## plane as Vector2(x, z).

const SM := FighterSM.State

# --- Identity -----------------------------------------------------------------
var id: int = 0
var team: int = 0
var team_slot: int = 0
var creature: CreatureInstance
var species: CreatureDefinition
var stats: CombatStats
var on_field: bool = true
var label: String = ""

# --- Kinematics ----------------------------------------------------------------
var pos: Vector2 = Vector2.ZERO
var prev_pos: Vector2 = Vector2.ZERO
var vel: Vector2 = Vector2.ZERO
var facing: Vector2 = Vector2.RIGHT
## Board direction of the last dash (or the cardinal nearest the facing).
var cardinal_facing: Vector2 = Cardinal.EAST
var aim: Vector2 = Vector2.RIGHT
var aim_point: Vector2 = Vector2.ZERO

# --- State machine ---------------------------------------------------------------
var state: FighterSM.State = SM.IDLE
var state_tick: int = 0
var state_duration: int = 0

# --- Resources -------------------------------------------------------------------
var hp: float = 100.0
var stamina: float = 100.0
var cooldowns: Dictionary = {}  # ability id -> ticks remaining
var focus_released: bool = false

# --- Current action ------------------------------------------------------------
var current_ability: AbilityDefinition = null
var current_slot: int = -1  # -1 basic, 0..3 specials
var ability_dir: Vector2 = Vector2.RIGHT
var ability_point: Vector2 = Vector2.ZERO
var ability_hit_landed: bool = false
var lunge_dir: Vector2 = Vector2.ZERO
var lunge_speed: float = 0.0
var lunge_ticks: int = 0
var lunge_stop_on_hit: bool = true

# --- Dash -----------------------------------------------------------------------
## The latest requested dash (direction index + cells), kept with the
## buffered DASH press so a dash queued during recovery still knows where to go.
var dash_req_dir: int = -1
var dash_req_cells: int = 0
## A dash requested mid-dash waits for the landing's chain window (however
## long the current dash is) instead of expiring with the input buffer.
var dash_queued: bool = false
var dash_dir: Vector2 = Vector2.ZERO
var dash_from: Vector2 = Vector2.ZERO  # where the windup started
var dash_home: Vector2 = Vector2.ZERO  # cell centre the travel starts from
var dash_to: Vector2 = Vector2.ZERO  # landing cell centre
var dash_cells: int = 0
var dash_travel_ticks: int = 0
var dash_t: int = 0
var dash_passed: Dictionary = {}  # fighter id -> true (already passed this dash)
var dash_through_immunity: int = 0
var dash_extra_recovery: int = 0
var dash_active_tick: int = 0

# --- Defense -----------------------------------------------------------------------
var guard_tick: int = 0
var guard_lock: int = 0
var guard_reentry: int = 0
var stun_kind: StringName = &""
var stun_chain: int = 0
var last_stun_end_tick: int = -100000
var steadfast: int = 0
var steadfast_pending: bool = false
var wakeup_grace: int = 0
var hitstop: int = 0
var knockback_vel: Vector2 = Vector2.ZERO
var knockback_ticks: int = 0
var statuses: Array[StatusInstance] = []
var switch_cooldown: int = 0
var switch_target_slot: int = -1

# --- Input --------------------------------------------------------------------------
var buffer: InputBuffer = InputBuffer.new()
var held: int = 0

# --- Records (progression, mastery, post-match stats) --------------------------------
var record := {
	"damage_dealt": 0.0,
	"damage_taken": 0.0,
	"hits": 0,
	"dashes": 0,
	"dash_throughs": 0,
	"perfect_guards": 0,
	"blocks": 0,
	"focus_ticks": 0,
	"ability_usage": {},  # ability id -> {"uses", "hits", "ko"}
}


func radius() -> float:
	return stats.collision_radius()


func hurt_radius() -> float:
	return stats.hurt_radius


func max_hp() -> float:
	return stats.max_hp


func max_stamina() -> float:
	return stats.stamina.max_stamina


func hp_ratio() -> float:
	return clampf(hp / maxf(1.0, max_hp()), 0.0, 1.0)


func stamina_ratio() -> float:
	return clampf(stamina / maxf(1.0, max_stamina()), 0.0, 1.0)


func is_ko() -> bool:
	return state == SM.KNOCKED_OUT


func is_active_in_battle() -> bool:
	return on_field and not is_ko()


func ability_in_slot(slot: int) -> AbilityDefinition:
	if slot < 0:
		return stats.basic
	if slot < stats.abilities.size():
		return stats.abilities[slot]
	return null


func cooldown_of(ability: AbilityDefinition) -> int:
	if ability == null:
		return 0
	return int(cooldowns.get(ability.id, 0))


func has_status(status_id: StringName) -> bool:
	for s in statuses:
		if s.def.id == status_id:
			return true
	return false


func status_flag(flag: String) -> bool:
	for s in statuses:
		if s.def.get(flag):
			return true
	return false


func status_mult(prop: String) -> float:
	var m := 1.0
	for s in statuses:
		m *= float(s.def.get(prop))
	return m


func usage_for(ability_id: StringName) -> Dictionary:
	var usage: Dictionary = record["ability_usage"]
	if not usage.has(ability_id):
		usage[ability_id] = {"uses": 0, "hits": 0, "ko": 0}
	return usage[ability_id]


## Compact, order-stable summary used for determinism checks and snapshots.
func snapshot() -> Dictionary:
	return {
		"id": id,
		"pos": [snappedf(pos.x, 0.0001), snappedf(pos.y, 0.0001)],
		"state": int(state),
		"state_tick": state_tick,
		"hp": snappedf(hp, 0.001),
		"stamina": snappedf(stamina, 0.001),
		"facing": [snappedf(facing.x, 0.001), snappedf(facing.y, 0.001)],
		"cooldowns": cooldowns.duplicate(),
	}
