class_name InputCommand
extends RefCounted
## One tick of player intent — the only thing a client will ever send to an
## authoritative battle server. The simulation never reads Godot's Input.
##
## Encoded size is 16 bytes (see encode()). Movement is an eight-way index so
## diagonal speed normalization is guaranteed by construction; aim is
## quantized so client prediction and server simulation see identical values.

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

var tick: int = 0
var sequence: int = 0
## Eight-way movement index (CombatConst.DIR8_NAMES) or -1 for none.
var move_dir: int = -1
## Unit aim direction on the ground plane, or ZERO when the device has no aim
## (the creature then aims along its facing / auto-target).
var aim: Vector2 = Vector2.ZERO
## Distance from the creature to the aimed ground point (targeted abilities).
var aim_distance: float = 0.0
var held: int = 0
var pressed: int = 0
## Which movement axis was pressed most recently (Cardinal.AXIS_*).
var axis_hint: int = Cardinal.AXIS_UNKNOWN


func move_vector() -> Vector2:
	return CombatConst.dir8_to_vec(move_dir)


func is_held(bit: int) -> bool:
	return (held & bit) != 0


func was_pressed(bit: int) -> bool:
	return (pressed & bit) != 0


func set_aim(dir: Vector2, distance: float) -> void:
	aim = CombatConst.quantize_aim(dir)
	aim_distance = snappedf(clampf(distance, 0.0, 600.0), 0.01)


func copy() -> InputCommand:
	var c := InputCommand.new()
	c.tick = tick
	c.sequence = sequence
	c.move_dir = move_dir
	c.aim = aim
	c.aim_distance = aim_distance
	c.held = held
	c.pressed = pressed
	c.axis_hint = axis_hint
	return c


func encode() -> PackedByteArray:
	var buf := StreamPeerBuffer.new()
	buf.put_u32(tick)
	buf.put_u32(sequence)
	buf.put_8(move_dir)
	var has_aim := aim != Vector2.ZERO
	var aim_q := 0xFFFF
	if has_aim:
		aim_q = int(round(fposmod(aim.angle(), TAU) / TAU * 4096.0)) % 4096
	buf.put_u16(aim_q)
	buf.put_u16(int(round(aim_distance * 100.0)))
	buf.put_u16(held)
	buf.put_u16(pressed)
	buf.put_8(axis_hint)
	return buf.data_array


static func decode(bytes: PackedByteArray) -> InputCommand:
	var buf := StreamPeerBuffer.new()
	buf.data_array = bytes
	var c := InputCommand.new()
	c.tick = buf.get_u32()
	c.sequence = buf.get_u32()
	c.move_dir = buf.get_8()
	var aim_q := buf.get_u16()
	if aim_q != 0xFFFF:
		var a := float(aim_q) / 4096.0 * TAU
		c.aim = Vector2(cos(a), sin(a))
	c.aim_distance = float(buf.get_u16()) / 100.0
	c.held = buf.get_u16()
	c.pressed = buf.get_u16()
	c.axis_hint = buf.get_8()
	return c


## Builds the `pressed` edge mask from the previous held state.
static func edges(prev_held: int, now_held: int) -> int:
	return now_held & ~prev_held


func _to_string() -> String:
	return "Cmd(t=%d move=%d aim=%s held=%x pressed=%x)" % [tick, move_dir, aim, held, pressed]
