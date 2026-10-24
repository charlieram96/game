class_name InputSetup
extends RefCounted
## Registers every input action in code (keyboard, mouse and gamepad), so
## bindings are typed, reviewable and easy to persist/rebind later.
##
## Desktop defaults (spec):
##   WASD move · Mouse aim · LMB basic · RMB dash · Shift (hold) focus
##   Q/E/R/F specials · Space guard · 1/2/3 switch
## Exploration: WASD move · Shift sneak · E / Space / Enter interact
## Gamepad: L-stick move · R-stick aim · RT basic · RB dash · LT focus ·
##   LB guard · A/B/X/Y specials · D-pad switch · Start pause

const P2_PREFIX := "p2_"


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
	# Combat
	_mouse(&"attack", MOUSE_BUTTON_LEFT)
	_axis(&"attack", JOY_AXIS_TRIGGER_RIGHT, 1.0)
	_key(&"attack", [KEY_J])
	_mouse(&"dash", MOUSE_BUTTON_RIGHT)
	_joy(&"dash", JOY_BUTTON_RIGHT_SHOULDER)
	_key(&"dash", [KEY_K])
	_key(&"focus", [KEY_SHIFT])
	_axis(&"focus", JOY_AXIS_TRIGGER_LEFT, 1.0)
	_key(&"guard", [KEY_SPACE])
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
	# Local versus: player 2 on the right side of the keyboard.
	_key(&"p2_move_up", [KEY_UP])
	_key(&"p2_move_down", [KEY_DOWN])
	_key(&"p2_move_left", [KEY_LEFT])
	_key(&"p2_move_right", [KEY_RIGHT])
	_key(&"p2_attack", [KEY_PERIOD])
	_key(&"p2_dash", [KEY_SLASH])
	_key(&"p2_focus", [KEY_SHIFT])  # replaced below with right shift via physical code
	_key(&"p2_guard", [KEY_CTRL])
	_key(&"p2_ability_1", [KEY_SEMICOLON])
	_key(&"p2_ability_2", [KEY_APOSTROPHE])
	_key(&"p2_ability_3", [KEY_BRACKETLEFT])
	_key(&"p2_ability_4", [KEY_BRACKETRIGHT])
	# Right-hand modifiers for player 2 (location-specific).
	InputMap.action_erase_events(&"p2_focus")
	var rshift := InputEventKey.new()
	rshift.keycode = KEY_SHIFT
	rshift.location = KEY_LOCATION_RIGHT
	InputMap.action_add_event(&"p2_focus", rshift)
	InputMap.action_erase_events(&"p2_guard")
	var rctrl := InputEventKey.new()
	rctrl.keycode = KEY_CTRL
	rctrl.location = KEY_LOCATION_RIGHT
	InputMap.action_add_event(&"p2_guard", rctrl)


static func _ensure(action: StringName) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action, 0.25)


static func _key(action: StringName, keys: Array) -> void:
	_ensure(action)
	for k in keys:
		var ev := InputEventKey.new()
		ev.keycode = k
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
