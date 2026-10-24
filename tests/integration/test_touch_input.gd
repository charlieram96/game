extends WBTestCase
## Touch drag-to-dash: a finger drag on the arena dashes once, a tap strikes,
## and the engine's emulated mouse copy of each touch is ignored (otherwise
## a phone would dash twice per drag). Without a camera, 64 screen pixels
## are one cell.

const H := preload("res://tests/sim_helpers.gd")
const PX := 64.0

var _layer: CanvasLayer


func _setup() -> Array:
	InputSetup.ensure_actions()
	_layer = CanvasLayer.new()
	Engine.get_main_loop().root.add_child(_layer)
	var host := Control.new()
	host.size = Vector2(1280, 720)
	_layer.add_child(host)
	var sim := H.make_sim()
	var touch := TouchControls.new()
	host.add_child(touch)
	touch.setup(sim, 0)
	touch.visible = true
	var src := LocalInputSource.new()
	src.allow_gamepad = false
	src.touch = touch
	return [sim, touch, src]


func _teardown() -> void:
	if _layer:
		_layer.queue_free()
		_layer = null


## One finger event, as the engine delivers it: the touch goes to the touch
## controls; its emulated mouse copy reaches both (as in the battle scene).
func _finger(touch: TouchControls, src: LocalInputSource, pos: Vector2, phase: String) -> void:
	var t: InputEvent
	var m: InputEventMouse
	match phase:
		"down", "up":
			var st := InputEventScreenTouch.new()
			st.index = 0
			st.position = pos
			st.pressed = phase == "down"
			t = st
			var mb := InputEventMouseButton.new()
			mb.button_index = MOUSE_BUTTON_LEFT
			mb.pressed = phase == "down"
			m = mb
		_:
			var sd := InputEventScreenDrag.new()
			sd.index = 0
			sd.position = pos
			t = sd
			var mm := InputEventMouseMotion.new()
			mm.button_mask = MOUSE_BUTTON_MASK_LEFT
			m = mm
	m.position = pos
	m.device = InputEvent.DEVICE_ID_EMULATION
	touch._input(t)
	touch._input(m)
	src.handle_input(m)


func test_finger_drag_dashes_exactly_once() -> void:
	var parts := _setup()
	var sim: BattleSim = parts[0]
	var touch: TouchControls = parts[1]
	var src: LocalInputSource = parts[2]
	var start := Vector2(400, 300)
	_finger(touch, src, start, "down")
	_finger(touch, src, start + Vector2(PX * 1.2, 4), "move")
	_finger(touch, src, start + Vector2(PX * 2.1, 6), "move")
	src.get_command(sim, 0)
	assert_true(src.aim_state.active, "aiming while the finger drags")
	assert_eq(src.aim_state.cells, 2, "two cells")
	_finger(touch, src, start + Vector2(PX * 2.1, 6), "up")
	var c := src.get_command(sim, 0)
	assert_true(c.has_dash(), "released: dash")
	assert_eq(c.dash_dir, H.E, "east")
	assert_eq(c.dash_cells, 2, "two cells")
	var again := src.get_command(sim, 0)
	assert_false(again.has_dash(), "no second dash from the emulated mouse copy")
	_teardown()


func test_finger_tap_strikes_once() -> void:
	var parts := _setup()
	var sim: BattleSim = parts[0]
	var touch: TouchControls = parts[1]
	var src: LocalInputSource = parts[2]
	_finger(touch, src, Vector2(500, 320), "down")
	_finger(touch, src, Vector2(501, 321), "up")
	var c := src.get_command(sim, 0)
	assert_false(c.has_dash(), "no dash")
	assert_true(c.was_pressed(InputCommand.ATTACK), "tap = basic attack")
	var again := src.get_command(sim, 0)
	assert_false(again.was_pressed(InputCommand.ATTACK), "one attack per tap")
	_teardown()


func test_drag_back_to_the_start_cancels() -> void:
	var parts := _setup()
	var sim: BattleSim = parts[0]
	var touch: TouchControls = parts[1]
	var src: LocalInputSource = parts[2]
	var start := Vector2(600, 300)
	_finger(touch, src, start, "down")
	_finger(touch, src, start + Vector2(0, -PX * 2.5), "move")
	_finger(touch, src, start + Vector2(2, -3), "move")
	src.get_command(sim, 0)
	assert_true(src.aim_state.cancelled, "preview shows the cancel")
	_finger(touch, src, start + Vector2(2, -3), "up")
	var c := src.get_command(sim, 0)
	assert_false(c.has_dash(), "cancelled")
	assert_false(c.was_pressed(InputCommand.ATTACK), "and not a tap either")
	_teardown()
