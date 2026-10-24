extends WBTestCase
## Local versus keeps the two players' controls apart: player 2's arrows and
## right-hand modifiers never drive player 1, and each gamepad drives only the
## player it is assigned to.

const H := preload("res://tests/sim_helpers.gd")


func _key(keycode: Key, pressed: bool, location: KeyLocation = KEY_LOCATION_UNSPECIFIED) -> void:
	var ev := InputEventKey.new()
	ev.keycode = keycode
	ev.physical_keycode = keycode
	ev.location = location
	ev.pressed = pressed
	Input.parse_input_event(ev)
	Input.flush_buffered_events()


func _pad_button(device: int, button: JoyButton, pressed: bool) -> void:
	var ev := InputEventJoypadButton.new()
	ev.device = device
	ev.button_index = button
	ev.pressed = pressed
	Input.parse_input_event(ev)
	Input.flush_buffered_events()


func _pressed(action: String) -> bool:
	return Input.is_action_pressed(StringName(action))


func test_keyboard_sides_are_separate() -> void:
	InputSetup.ensure_actions()
	_key(KEY_LEFT, true)
	assert_true(_pressed("p2_move_left"), "arrow drives player 2")
	assert_false(_pressed("p1_move_left"), "arrow does not drive player 1")
	assert_true(_pressed("move_left"), "arrows still move in single player")
	_key(KEY_LEFT, false)
	_key(KEY_A, true)
	assert_true(_pressed("p1_move_left"), "A drives player 1")
	assert_false(_pressed("p2_move_left"), "A does not drive player 2")
	_key(KEY_A, false)
	_key(KEY_SHIFT, true, KEY_LOCATION_RIGHT)
	assert_true(_pressed("p2_focus"), "right Shift is player 2's focus")
	assert_false(_pressed("p1_focus"), "right Shift is not player 1's focus")
	_key(KEY_SHIFT, false, KEY_LOCATION_RIGHT)
	_key(KEY_SHIFT, true, KEY_LOCATION_LEFT)
	assert_true(_pressed("p1_focus"), "left Shift is player 1's focus")
	assert_false(_pressed("p2_focus"), "left Shift is not player 2's focus")
	_key(KEY_SHIFT, false, KEY_LOCATION_LEFT)
	_key(KEY_CTRL, true, KEY_LOCATION_RIGHT)
	assert_true(_pressed("p2_guard"), "right Ctrl is player 2's guard")
	assert_false(_pressed("p1_guard"), "right Ctrl is not player 1's guard")
	_key(KEY_CTRL, false, KEY_LOCATION_RIGHT)


func test_player_one_command_ignores_player_two_keys() -> void:
	InputSetup.ensure_actions()
	var sim := H.make_sim()
	var src := LocalInputSource.new()
	src.prefix = InputSetup.P1_PREFIX
	src.allow_mouse = false
	_key(KEY_RIGHT, true)
	var c := src.get_command(sim, 0)
	assert_eq(c.move_dir, -1, "player 1 stands still while player 2 holds an arrow")
	_key(KEY_RIGHT, false)
	_key(KEY_D, true)
	c = src.get_command(sim, 0)
	assert_eq(c.move_dir, CombatConst.vec_to_dir8(Vector2.RIGHT), "D moves player 1 east")
	_key(KEY_D, false)


func test_each_gamepad_drives_one_player() -> void:
	InputSetup.ensure_actions()
	InputSetup.bind_player_pad(InputSetup.P1_PREFIX, 0)
	InputSetup.bind_player_pad(InputSetup.P2_PREFIX, 1)
	_pad_button(1, JOY_BUTTON_A, true)
	assert_true(_pressed("p2_ability_1"), "pad 2 drives player 2")
	assert_false(_pressed("p1_ability_1"), "pad 2 does not drive player 1")
	_pad_button(1, JOY_BUTTON_A, false)
	_pad_button(0, JOY_BUTTON_RIGHT_SHOULDER, true)
	assert_true(_pressed("p1_dash"), "pad 1 drives player 1")
	assert_false(_pressed("p2_dash"), "pad 1 does not drive player 2")
	_pad_button(0, JOY_BUTTON_RIGHT_SHOULDER, false)
	# One pad only: it belongs to player 2, player 1 keeps keyboard + mouse.
	InputSetup.bind_player_pad(InputSetup.P1_PREFIX, -1)
	InputSetup.bind_player_pad(InputSetup.P2_PREFIX, 0)
	_pad_button(0, JOY_BUTTON_A, true)
	assert_true(_pressed("p2_ability_1"), "the only pad drives player 2")
	assert_false(_pressed("p1_ability_1"), "and not player 1")
	_pad_button(0, JOY_BUTTON_A, false)
	InputSetup.bind_player_pad(InputSetup.P2_PREFIX, -1)
