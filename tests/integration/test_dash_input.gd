extends WBTestCase
## Drag-to-dash input: a drag aims a dash along a board lane (its length
## picks the cells) and releasing dashes; a quick click is a basic attack;
## dragging back cancels; held keys charge a dash. Without a camera the
## input source maps 64 screen pixels to one cell.

const H := preload("res://tests/sim_helpers.gd")
const PX := 64.0


func _mouse_button(src: LocalInputSource, pos: Vector2, pressed: bool) -> void:
	var ev := InputEventMouseButton.new()
	ev.button_index = MOUSE_BUTTON_LEFT
	ev.position = pos
	ev.pressed = pressed
	src.handle_input(ev)


func _mouse_move(src: LocalInputSource, pos: Vector2) -> void:
	var ev := InputEventMouseMotion.new()
	ev.position = pos
	ev.button_mask = MOUSE_BUTTON_MASK_LEFT
	src.handle_input(ev)


func _key(keycode: Key, pressed: bool) -> void:
	var ev := InputEventKey.new()
	ev.keycode = keycode
	ev.physical_keycode = keycode
	ev.pressed = pressed
	Input.parse_input_event(ev)
	Input.flush_buffered_events()


func _source() -> LocalInputSource:
	InputSetup.ensure_actions()
	var src := LocalInputSource.new()
	src.allow_gamepad = false
	return src


func test_drag_aims_and_release_dashes() -> void:
	var sim := H.make_sim()
	var src := _source()
	var start := Vector2(400, 300)
	_mouse_button(src, start, true)
	_mouse_move(src, start + Vector2(PX * 1.5, 10))
	_mouse_move(src, start + Vector2(PX * 3.1, 20))
	src.get_command(sim, 0)
	assert_true(src.aim_state.active, "aiming while dragging")
	assert_eq(src.aim_state.dir_index, H.E, "east lane")
	assert_eq(src.aim_state.cells, 3, "three cells")
	_mouse_button(src, start + Vector2(PX * 3.1, 20), false)
	var c := src.get_command(sim, 0)
	assert_true(c.has_dash(), "released: dash")
	assert_eq(c.dash_dir, H.E, "east")
	assert_eq(c.dash_cells, 3, "three cells")
	assert_false(src.aim_state.active, "preview cleared")


func test_drag_length_is_capped_at_the_longest_dash() -> void:
	var sim := H.make_sim()
	var src := _source()
	_mouse_button(src, Vector2(100, 100), true)
	_mouse_move(src, Vector2(100, 100 - PX * 12))
	_mouse_button(src, Vector2(100, 100 - PX * 12), false)
	var c := src.get_command(sim, 0)
	assert_eq(c.dash_dir, H.N, "north")
	assert_eq(c.dash_cells, DashSystem.max_cells(sim.active_fighter(0)), "capped")


func test_quick_click_is_a_basic_attack_not_a_dash() -> void:
	var sim := H.make_sim()
	var src := _source()
	_mouse_button(src, Vector2(300, 300), true)
	_mouse_button(src, Vector2(302, 301), false)
	var c := src.get_command(sim, 0)
	assert_false(c.has_dash(), "no dash")
	assert_true(c.was_pressed(InputCommand.ATTACK), "basic attack")


func test_dragging_back_to_the_start_cancels() -> void:
	var sim := H.make_sim()
	var src := _source()
	var start := Vector2(300, 300)
	_mouse_button(src, start, true)
	_mouse_move(src, start + Vector2(0, PX * 2))
	_mouse_move(src, start + Vector2(2, 3))
	src.get_command(sim, 0)
	assert_true(src.aim_state.cancelled, "shown as cancelled")
	_mouse_button(src, start + Vector2(2, 3), false)
	var c := src.get_command(sim, 0)
	assert_false(c.has_dash(), "no dash")
	assert_false(c.was_pressed(InputCommand.ATTACK), "and no attack")


func test_slingshot_launches_the_other_way() -> void:
	var sim := H.make_sim()
	var src := _source()
	src.slingshot = true
	_mouse_button(src, Vector2(300, 300), true)
	_mouse_move(src, Vector2(300 - PX * 2, 300))
	_mouse_button(src, Vector2(300 - PX * 2, 300), false)
	var c := src.get_command(sim, 0)
	assert_eq(c.dash_dir, H.E, "pulled west, launched east")
	assert_eq(c.dash_cells, 2, "two cells")


func test_holding_a_key_charges_more_cells() -> void:
	var sim := H.make_sim()
	var src := _source()
	src.allow_mouse = false
	_key(KEY_S, true)
	for i in LocalInputSource.CHARGE_TICKS_PER_CELL * 2 + 1:
		src.get_command(sim, 0)
	assert_eq(src.aim_state.dir_index, H.S, "charging south")
	assert_eq(src.aim_state.cells, 3, "three cells after two charge steps")
	_key(KEY_S, false)
	var c := src.get_command(sim, 0)
	assert_true(c.has_dash() and c.dash_dir == H.S and c.dash_cells == 3, "released: three cells south")


func test_guard_cancels_a_charging_dash() -> void:
	var sim := H.make_sim()
	var src := _source()
	src.allow_mouse = false
	_key(KEY_A, true)
	src.get_command(sim, 0)
	_key(KEY_SPACE, true)
	src.get_command(sim, 0)
	_key(KEY_A, false)
	var c := src.get_command(sim, 0)
	_key(KEY_SPACE, false)
	assert_false(c.has_dash(), "guarding cancelled the dash")
	assert_true(c.is_held(InputCommand.GUARD), "guard held")
