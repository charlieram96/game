class_name InputCommand
extends RefCounted
## One tick of player intent — the only thing a client will ever send to an
## authoritative battle server. The simulation never reads Godot's Input.
##
## There is no walking: a DASH press carries the dash itself (a board
## direction and a number of cells), which the simulation validates and
## clamps like any other untrusted input. Aim is quantized so client
## prediction and server simulation see identical values. Encoded size is
## 17 bytes (see encode()).

const ATTACK := 1 << 0
const DASH := 1 << 1
const FOCUS := 1 << 2
const GUARD := 1 << 3
const ABILITY_1 := 1 << 4
const ABILITY_2 := 1 << 5
const ABILITY_3 := 1 << 6
const ABILITY_4 := 1 << 7
const SWITCH_1 := 1 << 8
const SWITCH_2 := 1 << 9
const SWITCH_3 := 1 << 10

const ABILITY_BITS: Array[int] = [ABILITY_1, ABILITY_2, ABILITY_3, ABILITY_4]
const SWITCH_BITS: Array[int] = [SWITCH_1, SWITCH_2, SWITCH_3]
const MAX_DASH_CELLS := 63

var tick: int = 0
var sequence: int = 0
## Dash direction (Cardinal.DIRS index: 0 E, 1 S, 2 W, 3 N) or -1, and cells.
var dash_dir: int = -1
var dash_cells: int = 0
## Unit aim direction on the ground plane, or ZERO when the device has no aim
## (the creature then aims along its facing / auto-target).
var aim: Vector2 = Vector2.ZERO
## Distance from the creature to the aimed ground point (targeted abilities).
var aim_distance: float = 0.0
var held: int = 0
var pressed: int = 0


func is_held(bit: int) -> bool:
	return (held & bit) != 0


func was_pressed(bit: int) -> bool:
	return (pressed & bit) != 0


func set_aim(dir: Vector2, distance: float) -> void:
	aim = CombatConst.quantize_aim(dir)
	aim_distance = snappedf(clampf(distance, 0.0, 600.0), 0.01)


## Requests a dash this tick.
func set_dash(dir_index: int, cells: int) -> void:
	dash_dir = dir_index
	dash_cells = cells
	held |= DASH
	pressed |= DASH


func has_dash() -> bool:
	return was_pressed(DASH) and dash_dir >= 0 and dash_dir < 4 and dash_cells > 0


func copy() -> InputCommand:
	var c := InputCommand.new()
	c.tick = tick
	c.sequence = sequence
	c.dash_dir = dash_dir
	c.dash_cells = dash_cells
	c.aim = aim
	c.aim_distance = aim_distance
	c.held = held
	c.pressed = pressed
	return c


func encode() -> PackedByteArray:
	var buf := StreamPeerBuffer.new()
	buf.put_u32(tick)
	buf.put_u32(sequence)
	# Dash: 0xFF = none, else cells (6 bits) << 2 | direction (2 bits).
	var dash := 0xFF
	if dash_dir >= 0 and dash_dir < 4 and dash_cells > 0:
		dash = (mini(dash_cells, MAX_DASH_CELLS) << 2) | dash_dir
	buf.put_u8(dash)
	var aim_q := 0xFFFF
	if aim != Vector2.ZERO:
		aim_q = int(round(fposmod(aim.angle(), TAU) / TAU * 4096.0)) % 4096
	buf.put_u16(aim_q)
	buf.put_u16(int(round(aim_distance * 100.0)))
	buf.put_u16(held)
	buf.put_u16(pressed)
	return buf.data_array


static func decode(bytes: PackedByteArray) -> InputCommand:
	var buf := StreamPeerBuffer.new()
	buf.data_array = bytes
	var c := InputCommand.new()
	c.tick = buf.get_u32()
	c.sequence = buf.get_u32()
	var dash := buf.get_u8()
	if dash != 0xFF:
		c.dash_dir = dash & 3
		c.dash_cells = dash >> 2
	var aim_q := buf.get_u16()
	if aim_q != 0xFFFF:
		var a := float(aim_q) / 4096.0 * TAU
		c.aim = Vector2(cos(a), sin(a))
	c.aim_distance = float(buf.get_u16()) / 100.0
	c.held = buf.get_u16()
	c.pressed = buf.get_u16()
	return c


## Builds the `pressed` edge mask from the previous held state.
static func edges(prev_held: int, now_held: int) -> int:
	return now_held & ~prev_held


func _to_string() -> String:
	return "Cmd(t=%d dash=%d×%d aim=%s held=%x pressed=%x)" % [tick, dash_dir, dash_cells, aim, held, pressed]
