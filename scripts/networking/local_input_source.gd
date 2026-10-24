class_name LocalInputSource
extends InputSource
## Turns this device's input (keyboard + mouse, gamepad, touch) into
## InputCommands. Presses that happen between simulation ticks are latched
## so even a 1-frame tap is never lost.

const ACTIONS := {
	"attack": InputCommand.ATTACK,
	"dash": InputCommand.DASH,
	"focus": InputCommand.FOCUS,
	"guard": InputCommand.GUARD,
	"ability_1": InputCommand.ABILITY_1,
	"ability_2": InputCommand.ABILITY_2,
	"ability_3": InputCommand.ABILITY_3,
	"ability_4": InputCommand.ABILITY_4,
	"switch_1": InputCommand.SWITCH_1,
	"switch_2": InputCommand.SWITCH_2,
	"switch_3": InputCommand.SWITCH_3,
}

var camera: BattleCamera
var touch: TouchControls
var prefix := ""  # "p2_" for the second local player
var allow_mouse := true
var allow_gamepad := true
var gamepad_device := -1  # -1 = any
var enabled := true

var _prev_held := 0
var _pending := 0
var _axis_hint := Cardinal.AXIS_UNKNOWN
var _device: StringName = &"kbm"
var _last_aim := Vector2.ZERO


func reset() -> void:
	_prev_held = 0
	_pending = 0


## Feed from the scene's _input() so taps between ticks are latched.
func handle_input(event: InputEvent) -> void:
	if not enabled:
		return
	if event is InputEventMouseMotion and allow_mouse:
		_device = &"kbm"
	elif (event is InputEventJoypadButton or event is InputEventJoypadMotion) and allow_gamepad:
		if absf(event.get("axis_value") if event is InputEventJoypadMotion else 1.0) > 0.4:
			_device = &"pad"
	elif event is InputEventScreenTouch:
		_device = &"touch"
	if event.is_echo():
		return
	for action in ACTIONS.keys():
		var full := StringName(prefix + action)
		if InputMap.has_action(full) and event.is_action_pressed(full):
			_pending |= int(ACTIONS[action])
	for a in ["move_left", "move_right"]:
		if InputMap.has_action(prefix + a) and event.is_action_pressed(prefix + a):
			_axis_hint = Cardinal.AXIS_HORIZONTAL
	for a in ["move_up", "move_down"]:
		if InputMap.has_action(prefix + a) and event.is_action_pressed(prefix + a):
			_axis_hint = Cardinal.AXIS_VERTICAL


func get_command(sim: BattleSim, team: int) -> InputCommand:
	var cmd := InputCommand.new()
	if not enabled:
		_prev_held = 0
		return cmd
	var held := 0
	for action in ACTIONS.keys():
		var full := StringName(prefix + action)
		if InputMap.has_action(full) and Input.is_action_pressed(full):
			held |= int(ACTIONS[action])
	var move := Input.get_vector(StringName(prefix + "move_left"), StringName(prefix + "move_right"), StringName(prefix + "move_up"), StringName(prefix + "move_down"), 0.3)
	var aim := Vector2.ZERO
	var aim_dist := 0.0
	var me := sim.active_fighter(team)
	if touch and touch.is_active():
		var tm := touch.move_vector()
		if tm != Vector2.ZERO:
			move = tm
		held |= touch.held_bits()
		var tp := touch.consume_pressed()
		_pending |= tp
		var ta := touch.consume_aim()
		if ta != Vector2.ZERO:
			aim = ta
			aim_dist = 5.0
		if touch.joystick_axis_hint() != Cardinal.AXIS_UNKNOWN:
			_axis_hint = touch.joystick_axis_hint()
	if aim == Vector2.ZERO and allow_gamepad:
		var stick := Input.get_vector(&"aim_left", &"aim_right", &"aim_up", &"aim_down", 0.35)
		if stick != Vector2.ZERO and prefix == "":
			aim = stick.normalized()
			aim_dist = 4.0 + stick.length() * 3.0
			_device = &"pad"
	if aim == Vector2.ZERO and allow_mouse and _device == &"kbm" and camera and me and prefix == "":
		var vp := camera.get_viewport()
		var g := camera.ground_point(vp.get_mouse_position())
		var to := Vector2(g.x, g.z) - me.pos
		if to.length() > 0.05:
			aim = to.normalized()
			aim_dist = to.length()
	cmd.move_dir = CombatConst.vec_to_dir8(move, 0.3)
	if aim != Vector2.ZERO:
		cmd.set_aim(aim, aim_dist)
		_last_aim = aim
	cmd.held = held
	cmd.pressed = InputCommand.edges(_prev_held, held) | _pending
	cmd.axis_hint = _axis_hint
	_pending = 0
	_prev_held = held
	return cmd


func device() -> StringName:
	return _device
