class_name CombatConst
extends RefCounted
## Shared combat constants and direction helpers.
##
## The battle simulation runs at a fixed 60 Hz tick. Every timing in data
## (abilities, dashes, stuns) is expressed in ticks: 1 tick = 16.67 ms.
## Positions live on the flat XZ plane, stored as Vector2(x = east, y = south),
## so the camera angle can never influence distances, ranges or hit detection.

const TICK_RATE: int = 60
const TICK_DT: float = 1.0 / 60.0
const CELL_SIZE: float = 1.0

# --- Input ------------------------------------------------------------------
const INPUT_BUFFER_TICKS: int = 8

# --- Focus ------------------------------------------------------------------
const DEFAULT_FOCUS_ENTER_TICKS: int = 7  # ~120 ms
const DEFAULT_FOCUS_EXIT_TICKS: int = 7

# --- Dash-through -----------------------------------------------------------
const DASH_THROUGH_STUN_TICKS: int = 15  # 250 ms
const DASH_THROUGH_IMMUNITY_TICKS: int = 60  # 1 s of protection
const DASH_THROUGH_LANDING_CELLS: float = 1.0
## The dasher's recovery is extended so the victim always regains control at
## least this many ticks before the dasher can act: the stun creates an
## advantage, never a guaranteed follow-up.
const DASH_THROUGH_FOLLOWUP_MARGIN_TICKS: int = 3
const DASH_REPEL_STUN_TICKS: int = 21
## Shared freeze frame when a ram connects, and when dashes clash or bounce.
const RAM_HITSTOP_TICKS: int = 5
const DASH_CLASH_HITSTOP_TICKS: int = 4

# --- Stun / combo protection ------------------------------------------------
const WAKEUP_GRACE_TICKS: int = 6
const STUN_CHAIN_WINDOW_TICKS: int = 90
const STUN_CHAIN_MULTS: Array[float] = [1.0, 0.75, 0.5]
const STEADFAST_CHAIN: int = 3
const STEADFAST_TICKS: int = 75
const MIN_STUN_TICKS: int = 4

# --- Guard ------------------------------------------------------------------
const GUARD_ARC_DEG: float = 200.0
const PERFECT_GUARD_TICKS: int = 8
const GUARD_CHIP: float = 0.15
const GUARD_BREAK_STUN_TICKS: int = 54
const PERFECT_GUARD_STAGGER_TICKS: int = 24
const GUARD_REENTRY_TICKS: int = 6
const GUARD_DASH_REPEL_STAMINA: float = 10.0
const BLOCKSTUN_FACTOR: float = 0.5

# --- Hits -------------------------------------------------------------------
const KNOCKBACK_TICKS: int = 8
const MAX_HITSTOP_TICKS: int = 10
const MIN_DAMAGE: float = 1.0

# --- Surge ------------------------------------------------------------------
## Specials are paid for in stages of Surge instead of waiting on cooldowns.
const SURGE_PER_STAGE: float = 100.0
const SURGE_STAGES: int = 4
## Earned by fighting: every hit that connects (basic hits most, so quick
## strings build it fastest), every ram that connects (a whole stage), and
## a trickle for every dash.
const SURGE_PER_BASIC_HIT: float = 40.0
const SURGE_PER_SPECIAL_HIT: float = 15.0
const SURGE_PER_RAM: float = 120.0
const SURGE_PER_DASH: float = 4.0

# --- Match flow -------------------------------------------------------------
const COUNTDOWN_TICKS: int = 180
const KO_SETTLE_TICKS: int = 90
const SWITCH_TICKS: int = 30
const SWITCH_COOLDOWN_TICKS: int = 300

# --- Directions ---------------------------------------------------------------
## Eight-way indices go clockwise on screen starting east:
## 0=E, 1=SE, 2=S, 3=SW, 4=W, 5=NW, 6=N, 7=NE (y grows toward the camera/south).
const DIR8_NAMES: Array[String] = ["E", "SE", "S", "SW", "W", "NW", "N", "NE"]


static func sec_to_ticks(seconds: float) -> int:
	return int(round(seconds * TICK_RATE))


static func ticks_to_sec(ticks: int) -> float:
	return float(ticks) / TICK_RATE


static func dir8_to_vec(index: int) -> Vector2:
	if index < 0:
		return Vector2.ZERO
	var angle := float(index % 8) * PI / 4.0
	var v := Vector2(cos(angle), sin(angle))
	# Snap tiny float residue so straight directions are exact.
	if absf(v.x) < 1e-6:
		v.x = 0.0
	if absf(v.y) < 1e-6:
		v.y = 0.0
	return v.normalized()


static func vec_to_dir8(v: Vector2, deadzone: float = 0.2) -> int:
	if v.length() < deadzone:
		return -1
	var angle := fposmod(v.angle(), TAU)
	return int(round(angle / (PI / 4.0))) % 8


## Quantize an aim direction to 1/4096 of a turn so client and server see the
## exact same value after network encoding.
static func quantize_aim(v: Vector2) -> Vector2:
	if v.length_squared() < 1e-8:
		return Vector2.ZERO
	var steps := 4096.0
	var a := roundf(fposmod(v.angle(), TAU) / TAU * steps) / steps * TAU
	return Vector2(cos(a), sin(a))


static func perpendicular(v: Vector2) -> Vector2:
	return Vector2(-v.y, v.x)
