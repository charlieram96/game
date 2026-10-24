class_name InputSetup
extends RefCounted
## Registers every input action in code (keyboard, mouse and gamepad), so
## bindings are typed, reviewable and easy to persist/rebind later.
##
## Battle (no walking — movement is drag-to-dash, see LocalInputSource):
##   Mouse drag = dash (release to go) · click = basic attack · mouse aims
##   Hold WASD / arrows = charge a dash, release to go · J = basic attack
##   Q/E/R/F specials · Space or right mouse (hold) guard · Shift (hold) focus
## Exploration: WASD move · Shift sneak · E / Space / Enter interact
## Gamepad: hold L-stick / D-pad = charge a dash · R-stick aim · RT basic ·
##   LT focus · LB guard · A/B/X/Y specials · Start pause

const P1_PREFIX := "p1_"
const P2_PREFIX := "p2_"
## Gamepad-driven actions each versus player gets on their assigned pad.
const PAD_BUTTONS := {
	"guard": JOY_BUTTON_LEFT_SHOULDER,
	"ability_1": JOY_BUTTON_A, "ability_2": JOY_BUTTON_B,
	"ability_3": JOY_BUTTON_X, "ability_4": JOY_BUTTON_Y,
	"move_up": JOY_BUTTON_DPAD_UP, "move_down": JOY_BUTTON_DPAD_DOWN,
	"move_left": JOY_BUTTON_DPAD_LEFT, "move_right": JOY_BUTTON_DPAD_RIGHT,
}
const PAD_AXES := {
	"move_up": [JOY_AXIS_LEFT_Y, -1.0], "move_down": [JOY_AXIS_LEFT_Y, 1.0],
	"move_left": [JOY_AXIS_LEFT_X, -1.0], "move_right": [JOY_AXIS_LEFT_X, 1.0],
	"aim_up": [JOY_AXIS_RIGHT_Y, -1.0], "aim_down": [JOY_AXIS_RIGHT_Y, 1.0],
	"aim_left": [JOY_AXIS_RIGHT_X, -1.0], "aim_right": [JOY_AXIS_RIGHT_X, 1.0],
	"attack": [JOY_AXIS_TRIGGER_RIGHT, 1.0], "focus": [JOY_AXIS_TRIGGER_LEFT, 1.0],
}


static func ensure_actions() -> void:
	if InputMap.has_action(&"move_up"):
		return
	# Movement (keyboard, arrows also work in single player)
	_key(&"move_up", [KEY_W, KEY_UP])
	_key(&"move_down", [KEY_S, KEY_DOWN])
	_key(&"move_left", [KEY_A, KEY_LEFT])
	_key(&"move_right", [KEY_D, KEY_RIGHT])
	_axis(&"move_up", JOY_AXIS_LEFT_Y, -1.0)
	_axis(&"move_down", JOY_AXIS_LEFT_Y, 1.0)
	_axis(&"move_left", JOY_AXIS_LEFT_X, -1.0)
	_axis(&"move_right", JOY_AXIS_LEFT_X, 1.0)
	_joy(&"move_up", JOY_BUTTON_DPAD_UP)
	_joy(&"move_down", JOY_BUTTON_DPAD_DOWN)
	_joy(&"move_left", JOY_BUTTON_DPAD_LEFT)
	_joy(&"move_right", JOY_BUTTON_DPAD_RIGHT)
	# Gamepad aim
	_axis(&"aim_up", JOY_AXIS_RIGHT_Y, -1.0)
	_axis(&"aim_down", JOY_AXIS_RIGHT_Y, 1.0)
	_axis(&"aim_left", JOY_AXIS_RIGHT_X, -1.0)
	_axis(&"aim_right", JOY_AXIS_RIGHT_X, 1.0)
	# Combat (a mouse click attacks through the drag gesture, not an action)
	_axis(&"attack", JOY_AXIS_TRIGGER_RIGHT, 1.0)
	_key(&"attack", [KEY_J])
	_key(&"focus", [KEY_SHIFT])
	_axis(&"focus", JOY_AXIS_TRIGGER_LEFT, 1.0)
	_key(&"guard", [KEY_SPACE])
	_mouse(&"guard", MOUSE_BUTTON_RIGHT)
	_joy(&"guard", JOY_BUTTON_LEFT_SHOULDER)
	_key(&"ability_1", [KEY_Q])
	_joy(&"ability_1", JOY_BUTTON_A)
	_key(&"ability_2", [KEY_E])
	_joy(&"ability_2", JOY_BUTTON_B)
	_key(&"ability_3", [KEY_R])
	_joy(&"ability_3", JOY_BUTTON_X)
	_key(&"ability_4", [KEY_F])
	_joy(&"ability_4", JOY_BUTTON_Y)
	_key(&"switch_1", [KEY_1])
	_key(&"switch_2", [KEY_2])
	_key(&"switch_3", [KEY_3])
	# Exploration
	_key(&"interact", [KEY_E, KEY_ENTER, KEY_KP_ENTER])
	_joy(&"interact", JOY_BUTTON_A)
	_key(&"sneak", [KEY_SHIFT])
	_joy(&"sneak", JOY_BUTTON_LEFT_SHOULDER)
	_key(&"journal", [KEY_J, KEY_TAB])
	_joy(&"journal", JOY_BUTTON_BACK)
	# UI
	_key(&"advance", [KEY_SPACE, KEY_ENTER, KEY_E, KEY_KP_ENTER])
	_joy(&"advance", JOY_BUTTON_A)
	_mouse(&"advance", MOUSE_BUTTON_LEFT)
	_key(&"pause", [KEY_ESCAPE, KEY_P])
	_joy(&"pause", JOY_BUTTON_START)
	_key(&"debug_overlay", [KEY_F3])
	_key(&"toggle_touch", [KEY_F6])
	# Local versus: player 1 keeps the left side of the keyboard and the mouse
	# (no arrows or right-hand modifiers, which belong to player 2).
	_key(&"p1_move_up", [KEY_W])
	_key(&"p1_move_down", [KEY_S])
	_key(&"p1_move_left", [KEY_A])
	_key(&"p1_move_right", [KEY_D])
	_key(&"p1_attack", [KEY_J])
	_key_at(&"p1_focus", KEY_SHIFT, KEY_LOCATION_LEFT)
	_key(&"p1_guard", [KEY_SPACE])
	_mouse(&"p1_guard", MOUSE_BUTTON_RIGHT)
	_key(&"p1_ability_1", [KEY_Q])
	_key(&"p1_ability_2", [KEY_E])
	_key(&"p1_ability_3", [KEY_R])
	_key(&"p1_ability_4", [KEY_F])
	for a in ["aim_up", "aim_down", "aim_left", "aim_right"]:
		_ensure(StringName(P1_PREFIX + a))
		_ensure(StringName(P2_PREFIX + a))
	# Player 2 on the right side of the keyboard.
	_key(&"p2_move_up", [KEY_UP])
	_key(&"p2_move_down", [KEY_DOWN])
	_key(&"p2_move_left", [KEY_LEFT])
	_key(&"p2_move_right", [KEY_RIGHT])
	_key(&"p2_attack", [KEY_PERIOD, KEY_SLASH])
	_key_at(&"p2_focus", KEY_SHIFT, KEY_LOCATION_RIGHT)
	_key_at(&"p2_guard", KEY_CTRL, KEY_LOCATION_RIGHT)
	_key(&"p2_ability_1", [KEY_SEMICOLON])
	_key(&"p2_ability_2", [KEY_APOSTROPHE])
	_key(&"p2_ability_3", [KEY_BRACKETLEFT])
	_key(&"p2_ability_4", [KEY_BRACKETRIGHT])


## Gives each versus player their own gamepad: with two pads the first is
## player 1's and the second player 2's; a single pad goes to player 2 (player
## 1 has the keyboard and mouse). Call again when pads are (dis)connected.
static func assign_versus_pads() -> Array:
	var pads := Input.get_connected_joypads()
	var p1 := -1
	var p2 := -1
	if pads.size() >= 2:
		p1 = pads[0]
		p2 = pads[1]
	elif pads.size() == 1:
		p2 = pads[0]
	bind_player_pad(P1_PREFIX, p1)
	bind_player_pad(P2_PREFIX, p2)
	return [p1, p2]


## Rebinds one versus player's gamepad events to `device` (-1 = no pad).
static func bind_player_pad(prefix: String, device: int) -> void:
	var names: Array = PAD_BUTTONS.keys() + PAD_AXES.keys()
	for n in names:
		var action := StringName(prefix + String(n))
		_ensure(action)
		for ev in InputMap.action_get_events(action):
			if ev is InputEventJoypadButton or ev is InputEventJoypadMotion:
				InputMap.action_erase_event(action, ev)
	if device < 0:
		return
	for n in PAD_BUTTONS:
		var b := InputEventJoypadButton.new()
		b.button_index = PAD_BUTTONS[n]
		b.device = device
		InputMap.action_add_event(StringName(prefix + String(n)), b)
	for n in PAD_AXES:
		var m := InputEventJoypadMotion.new()
		m.axis = PAD_AXES[n][0]
		m.axis_value = PAD_AXES[n][1]
		m.device = device
		InputMap.action_add_event(StringName(prefix + String(n)), m)


static func _ensure(action: StringName) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action, 0.25)


static func _key(action: StringName, keys: Array) -> void:
	_ensure(action)
	for k in keys:
		var ev := InputEventKey.new()
		ev.keycode = k
		InputMap.action_add_event(action, ev)


## A key on one side of the keyboard only (left/right Shift, Ctrl...). Godot
## only honours the location for physical-key bindings.
static func _key_at(action: StringName, key: Key, location: KeyLocation) -> void:
	_ensure(action)
	var ev := InputEventKey.new()
	ev.physical_keycode = key
	ev.location = location
	InputMap.action_add_event(action, ev)


static func _mouse(action: StringName, button: MouseButton) -> void:
	_ensure(action)
	var ev := InputEventMouseButton.new()
	ev.button_index = button
	InputMap.action_add_event(action, ev)


static func _joy(action: StringName, button: JoyButton) -> void:
	_ensure(action)
	var ev := InputEventJoypadButton.new()
	ev.button_index = button
	InputMap.action_add_event(action, ev)


static func _axis(action: StringName, axis: JoyAxis, value: float) -> void:
	_ensure(action)
	var ev := InputEventJoypadMotion.new()
	ev.axis = axis
	ev.axis_value = value
	InputMap.action_add_event(action, ev)
