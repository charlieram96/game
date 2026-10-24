class_name BattleEvent
extends RefCounted
## Something that happened in a simulation tick. The presentation layer turns
## events into animation, VFX, sound and UI; a network server would send them
## (with their stable ids) to clients for cosmetic playback.

const COUNTDOWN := &"countdown"
const FIGHT_START := &"fight_start"
const STATE := &"state"
const DASH_START := &"dash_start"
const DASH_THROUGH := &"dash_through"
const DASH_REPELLED := &"dash_repelled"
const DASH_CLASH := &"dash_clash"
const DASH_NO_STAMINA := &"dash_no_stamina"
const ABILITY_START := &"ability_start"
const ABILITY_ACTIVE := &"ability_active"
const ABILITY_DENIED := &"ability_denied"
const TELEGRAPH := &"telegraph"
const VOLUME_SPAWN := &"volume_spawn"
const VOLUME_END := &"volume_end"
const PROJECTILE_BLOCKED := &"projectile_blocked"
const PROJECTILE_CLASH := &"projectile_clash"
const AREA_BURST := &"area_burst"
const HIT := &"hit"
const EVADE := &"evade"
const GUARD_START := &"guard_start"
const BLOCK := &"block"
const PERFECT_GUARD := &"perfect_guard"
const GUARD_BREAK := &"guard_break"
const STUN := &"stun"
const STUN_RESISTED := &"stun_resisted"
const STATUS_APPLIED := &"status_applied"
const STATUS_ENDED := &"status_ended"
const DOT := &"dot"
const FOCUS_START := &"focus_start"
const FOCUS_INTERRUPTED := &"focus_interrupted"
const STAMINA_FULL := &"stamina_full"
const LUNGE := &"lunge"
const SWITCH_START := &"switch_start"
const SWITCH_IN := &"switch_in"
const KO := &"ko"
const TIMEOUT := &"timeout"
const BATTLE_END := &"battle_end"

var id: int = 0
var type: StringName = &""
var tick: int = 0
var fighter_id: int = -1
var target_id: int = -1
var pos: Vector2 = Vector2.ZERO
var data: Dictionary = {}


func _to_string() -> String:
	return "Event#%d(%s t=%d f=%d->%d %s)" % [id, type, tick, fighter_id, target_id, data]
