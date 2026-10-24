class_name LocalInputSource
extends InputSource
## Turns this device's input into InputCommands. There is no walking in
## battle; movement is drag-to-dash:
##   * mouse or finger: drag from anywhere to aim a dash along a board
##     direction (the drag length picks the cells), release to dash; a quick
##     tap is a basic attack toward the pointer; drag back to the start (or
##     right-click) to cancel;
##   * keys, D-pad or stick: hold a direction to charge (one cell, then one
##     more every CHARGE_TICKS_PER_CELL), release to dash, so a tap is a
##     one-cell step.
## Presses that happen between simulation ticks are latched so even a
## 1-frame tap is never lost. `aim_state` publishes the dash being aimed for
## the preview to draw.

const ACTIONS := {
	"attack": InputCommand.ATTACK,
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
const MOVE_ACTIONS := ["move_left", "move_right", "move_up", "move_down"]
const CHARGE_TICKS_PER_CELL := 7
const STICK_DEADZONE := 0.45
## A tap-attack keeps aiming at the tapped spot for this many ticks.
const TAP_AIM_TICKS := 12

var camera: BattleCamera
var touch: TouchControls
## "" in single player; "p1_" / "p2_" in local versus, whose actions keep the
## two players' keys and gamepads apart (see InputSetup).
var prefix := ""
var allow_mouse := true
var allow_gamepad := true
var enabled := true
## Slingshot drag: pull back and release to launch the other way.
var slingshot := false
var aim_state := DashAim.new()

var _prev_held := 0
var _pending := 0
var _device: StringName = &"kbm"
var _last_aim := Vector2.ZERO
var _gesture := DragGesture.new()
var _drag_dir_memory := -1
var _released_drags: Array[Vector2] = []  # world drag vectors waiting for the next tick
var _tap_screen := Vector2.ZERO
var _tap_aim_ticks := 0
var _guard_blocked := false
var _charge_dir := -1
var _charge_ticks := 0
var _charge_blocked := false
var _charge_tapped := -1  # a direction pressed and released between ticks


func reset() -> void:
	_prev_held = 0
	_pending = 0
	_gesture.cancel()
	_released_drags.clear()
	_charge_dir = -1
	_charge_ticks = 0
	_charge_tapped = -1
	aim_state.clear()


## Feed from the scene's _input() so taps between ticks are latched.
func handle_input(event: InputEvent) -> void:
	if not enabled:
		return
	# On touch screens the engine also sends each touch as an emulated mouse
	# event; the touch controls already handle the real one.
	if event is InputEventMouse and event.device == InputEvent.DEVICE_ID_EMULATION and touch and touch.is_active():
		return
	if event is InputEventMouseMotion and allow_mouse:
		_device = &"kbm"
		if _gesture.is_down():
			_gesture.move(event.position)
	elif event is InputEventMouseButton and allow_mouse and not _touch_owns_mouse():
		_on_mouse_button(event)
	elif (event is InputEventJoypadButton or event is InputEventJoypadMotion) and allow_gamepad and _owns_pad_event(event):
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
	# A direction tapped faster than a tick still makes a one-cell step.
	if _charge_dir < 0 and not _charge_blocked:
		for a in MOVE_ACTIONS:
			var full := StringName(prefix + a)
			if InputMap.has_action(full) and event.is_action_pressed(full):
				_charge_tapped = Cardinal.pick(_move_vector_of(a))


func _on_mouse_button(event: InputEventMouseButton) -> void:
	if event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			_device = &"kbm"
			_drag_dir_memory = -1
			_gesture.press(event.position)
		elif _gesture.is_down():
			var from := _gesture.origin
			var to := _gesture.current
			match _gesture.release():
				&"dash":
					_released_drags.append(_world_drag(from, to))
				&"tap":
					_pending |= InputCommand.ATTACK
					_tap_screen = event.position
					_tap_aim_ticks = TAP_AIM_TICKS
	elif event.button_index == MOUSE_BUTTON_RIGHT and event.pressed and _gesture.is_aiming():
		# Right-click cancels an aimed dash (and doesn't start a guard).
		_gesture.cancel()
		_guard_blocked = true


func get_command(sim: BattleSim, team: int) -> InputCommand:
	var cmd := InputCommand.new()
	if not enabled:
		_prev_held = 0
		aim_state.clear()
		return cmd
	var me := sim.active_fighter(team)
	var max_cells := DashSystem.max_cells(me) if me else 1
	var held := _held_actions()
	if touch and touch.is_active():
		held |= touch.held_bits()
		_pending |= touch.consume_pressed()
		for g in touch.consume_gestures():
			match g["kind"]:
				&"dash":
					_released_drags.append(_world_drag(g["from"], g["to"]))
				&"tap":
					_pending |= InputCommand.ATTACK
					_tap_screen = g["to"]
					_tap_aim_ticks = TAP_AIM_TICKS
	var dash := Vector2i(-1, 0)
	if not _released_drags.is_empty():
		# Same lane memory as the preview, so the dash goes where it was shown.
		dash = _drag_to_dash(_released_drags.pop_front(), max_cells, _drag_dir_memory)
	var charged := _update_charge(held, max_cells)
	if dash.x < 0:
		dash = charged
	_update_aim_state(max_cells)
	var aim := _aim_vector(me)
	var aim_dir := Vector2(aim.x, aim.y)
	var aim_dist := aim.z
	if aim_dir == Vector2.ZERO and aim_state.active and aim_state.dir_index >= 0:
		# Turn to face the lane being aimed: the windup reads before release.
		aim_dir = Cardinal.from_index(aim_state.dir_index)
		aim_dist = float(aim_state.cells)
	if aim_dir != Vector2.ZERO:
		cmd.set_aim(aim_dir, aim_dist)
		_last_aim = aim_dir
	cmd.held = held
	cmd.pressed = InputCommand.edges(_prev_held, held) | _pending
	_pending = 0
	_prev_held = held
	if dash.x >= 0:
		cmd.set_dash(dash.x, dash.y)
	return cmd


func device() -> StringName:
	return _device


func _held_actions() -> int:
	var held := 0
	for action in ACTIONS.keys():
		var full := StringName(prefix + action)
		if InputMap.has_action(full) and Input.is_action_pressed(full):
			held |= int(ACTIONS[action])
	if _guard_blocked:
		if held & InputCommand.GUARD:
			held &= ~InputCommand.GUARD
		else:
			_guard_blocked = false
	return held


# --- Dash from a drag ----------------------------------------------------------------

## World-space (ground plane) vector between two screen points.
func _world_drag(from: Vector2, to: Vector2) -> Vector2:
	if camera == null:
		return (to - from) / 64.0
	var a := camera.ground_point(from)
	var b := camera.ground_point(to)
	return Vector2(b.x - a.x, b.z - a.z)


## Direction index + cells for a world drag (cells = length along the lane).
func _drag_to_dash(w: Vector2, max_cells: int, previous: int) -> Vector2i:
	var v := -w if slingshot else w
	var d := Cardinal.pick(v, previous)
	if d < 0:
		return Vector2i(-1, 0)
	var along := absf(v.dot(Cardinal.from_index(d)))
	return Vector2i(d, clampi(int(round(along / CombatConst.CELL_SIZE)), 1, max_cells))


# --- Dash from a held direction (keys, D-pad, stick) ------------------------------------

func _move_vector() -> Vector2:
	return Input.get_vector(StringName(prefix + "move_left"), StringName(prefix + "move_right"), StringName(prefix + "move_up"), StringName(prefix + "move_down"), STICK_DEADZONE)


static func _move_vector_of(action: String) -> Vector2:
	match action:
		"move_left":
			return Vector2.LEFT
		"move_right":
			return Vector2.RIGHT
		"move_up":
			return Vector2.UP
	return Vector2.DOWN


## Hold a direction to charge, release to dash. Guard or Focus cancels.
func _update_charge(held: int, max_cells: int) -> Vector2i:
	var v := _move_vector()
	if held & (InputCommand.GUARD | InputCommand.FOCUS):
		_charge_dir = -1
		_charge_tapped = -1
		_charge_blocked = v != Vector2.ZERO
		return Vector2i(-1, 0)
	if _charge_blocked:
		_charge_blocked = v != Vector2.ZERO
		return Vector2i(-1, 0)
	if v != Vector2.ZERO:
		if _charge_dir < 0:
			_charge_dir = Cardinal.pick(v)
			_charge_ticks = 0
		else:
			_charge_dir = Cardinal.pick(v, _charge_dir)
			_charge_ticks += 1
		_charge_tapped = -1
		return Vector2i(-1, 0)
	var fire := Vector2i(-1, 0)
	if _charge_dir >= 0:
		fire = Vector2i(_charge_dir, _charge_cells(max_cells))
	elif _charge_tapped >= 0:
		fire = Vector2i(_charge_tapped, 1)
	_charge_dir = -1
	_charge_ticks = 0
	_charge_tapped = -1
	return fire


func _charge_cells(max_cells: int) -> int:
	return clampi(1 + _charge_ticks / CHARGE_TICKS_PER_CELL, 1, max_cells)


# --- Preview + aim ---------------------------------------------------------------------

func _update_aim_state(max_cells: int) -> void:
	aim_state.clear()
	var g: DragGesture = null
	if _gesture.is_aiming():
		g = _gesture
	elif touch and touch.is_active() and touch.gesture.is_aiming():
		g = touch.gesture
	if g:
		var r := _drag_to_dash(_world_drag(g.origin, g.current), max_cells, _drag_dir_memory)
		_drag_dir_memory = r.x
		aim_state.active = r.x >= 0
		aim_state.dir_index = r.x
		aim_state.cells = r.y
		aim_state.cancelled = g.is_cancelled()
		aim_state.device = &"drag"
		return
	_drag_dir_memory = -1
	if _charge_dir >= 0:
		aim_state.active = true
		aim_state.dir_index = _charge_dir
		aim_state.cells = _charge_cells(max_cells)
		aim_state.device = &"charge"
		aim_state.charge_fraction = 1.0 if aim_state.cells >= max_cells else float(_charge_ticks % CHARGE_TICKS_PER_CELL) / CHARGE_TICKS_PER_CELL


## Ability/attack aim as (x, y, distance); zero when the device has none.
func _aim_vector(me: Fighter) -> Vector3:
	if me == null:
		return Vector3.ZERO
	if _tap_aim_ticks > 0:
		_tap_aim_ticks -= 1
		var t := _ground_from_screen(_tap_screen) - me.pos
		if t.length() > 0.05:
			return Vector3(t.normalized().x, t.normalized().y, t.length())
	if touch and touch.is_active():
		var ta := touch.consume_aim()
		if ta != Vector2.ZERO:
			return Vector3(ta.x, ta.y, 5.0)
	if allow_gamepad:
		var stick := Input.get_vector(StringName(prefix + "aim_left"), StringName(prefix + "aim_right"), StringName(prefix + "aim_up"), StringName(prefix + "aim_down"), 0.35)
		if stick != Vector2.ZERO:
			_device = &"pad"
			var n := stick.normalized()
			return Vector3(n.x, n.y, 4.0 + stick.length() * 3.0)
	if allow_mouse and _device == &"kbm" and camera and not _gesture.is_aiming():
		var to := _ground_from_screen(camera.get_viewport().get_mouse_position()) - me.pos
		if to.length() > 0.05:
			var n2 := to.normalized()
			return Vector3(n2.x, n2.y, to.length())
	return Vector3.ZERO


func _ground_from_screen(p: Vector2) -> Vector2:
	if camera == null:
		return Vector2.ZERO
	var g := camera.ground_point(p)
	return Vector2(g.x, g.z)


## Simulated-touch mode routes the mouse through the touch controls instead.
func _touch_owns_mouse() -> bool:
	return touch != null and touch.is_active() and Settings.touch_mode == Settings.TouchMode.ALWAYS


## True when gamepad `device` drives this source (any pad in single player).
func owns_pad(device: int) -> bool:
	if not allow_gamepad:
		return false
	if prefix == "":
		return true
	var ev := InputEventJoypadButton.new()
	ev.device = device
	for a in InputSetup.PAD_BUTTONS.keys():
		ev.button_index = InputSetup.PAD_BUTTONS[a]
		var action := StringName(prefix + String(a))
		if InputMap.has_action(action) and InputMap.event_is_action(ev, action):
			return true
	return false


## In versus each player has their own pad; the other player's stick must not
## switch this player away from mouse aiming.
func _owns_pad_event(event: InputEvent) -> bool:
	if prefix == "":
		return true
	for a in InputSetup.PAD_BUTTONS.keys() + InputSetup.PAD_AXES.keys():
		var action := StringName(prefix + String(a))
		if InputMap.has_action(action) and InputMap.event_is_action(event, action):
			return true
	return false
