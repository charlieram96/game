class_name TouchControls
extends Control
## Landscape mobile controls. There is no joystick: the arena itself is the
## movement surface.
##
## * Drag anywhere on the arena to aim a dash (the length picks the cells),
##   release to dash; drag back to where you started to cancel.
## * Tap the arena for a basic attack toward that spot; press and hold still
##   to Focus (regain stamina) for as long as you hold.
## * Buttons (right): attack, the four specials (tap = auto-aim, drag from
##   the button = aim, release to cast), Guard and Focus (hold).
## Works with real touch or with the mouse ("simulated touch" on desktop).

const MIN_BUTTON := 64.0

var sim: BattleSim
var team := 0
var buttons: Array = []
## The arena drag gesture (read by LocalInputSource for the dash preview).
var gesture := DragGesture.new()
var _gestures_done: Array[Dictionary] = []
var _pressed_bits := 0
var _aim_out := Vector2.ZERO
var _mouse_touch_id := -10


class TouchButton:
	var name := ""
	var bit := 0
	var center := Vector2.ZERO  # relative to the bottom-right anchor
	var radius := 40.0
	var hold := false
	var aimable := false
	var touch := -2
	var start := Vector2.ZERO
	var drag := Vector2.ZERO
	var press_time := 0.0
	var ability: AbilityDefinition
	var label := ""
	var icon: Texture2D


func _init() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func setup(p_sim: BattleSim, p_team: int) -> void:
	sim = p_sim
	team = p_team
	buttons.clear()
	var f := sim.active_fighter(team)
	_add("attack", InputCommand.ATTACK, Vector2(-118, -112), 62, true, false, f.stats.basic if f else null, "ATK")
	_add("guard", InputCommand.GUARD, Vector2(-62, -250), 36, true, false, null, "GRD")
	_add("focus", InputCommand.FOCUS, Vector2(-250, -70), 40, true, false, null, "FOC")
	var ab_pos := [Vector2(-244, -170), Vector2(-206, -262), Vector2(-120, -312), Vector2(-292, -262)]
	for i in 4:
		var ab: AbilityDefinition = f.stats.abilities[i] if f and i < f.stats.abilities.size() else null
		_add("ability_%d" % (i + 1), InputCommand.ABILITY_BITS[i], ab_pos[i], 36, false, true, ab, str(i + 1))
	queue_redraw()


func rebind(p_sim: BattleSim) -> void:
	setup(p_sim, team)


func _add(id: String, bit: int, center: Vector2, radius: float, hold: bool, aimable: bool, ability: AbilityDefinition, label_text: String) -> void:
	var b := TouchButton.new()
	b.name = id
	b.bit = bit
	b.center = center
	b.radius = maxf(radius, MIN_BUTTON * 0.5)
	b.hold = hold
	b.aimable = aimable
	b.ability = ability
	b.label = label_text
	if ability:
		b.icon = UiTheme.icon("ability_" + String(ability.id).trim_suffix("_2").trim_suffix("_3"))
	else:
		b.icon = UiTheme.icon("ability_" + id)
	buttons.append(b)


func is_active() -> bool:
	return visible


func held_bits() -> int:
	var bits := 0
	for b in buttons:
		var tb := b as TouchButton
		if tb.touch != -2 and tb.hold:
			bits |= tb.bit
	if gesture.is_holding():
		bits |= InputCommand.FOCUS
	return bits


func consume_pressed() -> int:
	var p := _pressed_bits
	_pressed_bits = 0
	return p


func consume_aim() -> Vector2:
	var a := _aim_out
	_aim_out = Vector2.ZERO
	return a


## Finished arena gestures since the last call: {"kind": &"dash"/&"tap", "from", "to"}
## (viewport coordinates).
func consume_gestures() -> Array[Dictionary]:
	var out := _gestures_done.duplicate()
	_gestures_done.clear()
	return out


func button_rect(b: TouchButton) -> Rect2:
	var c := _button_center(b)
	return Rect2(c - Vector2(b.radius, b.radius), Vector2(b.radius, b.radius) * 2.0)


func _button_center(b: TouchButton) -> Vector2:
	return size + b.center


func _input(event: InputEvent) -> void:
	if not visible:
		return
	var idx := -2
	var pos := Vector2.ZERO
	var pressed := false
	var is_drag := false
	if event is InputEventScreenTouch:
		idx = event.index
		pos = event.position
		pressed = event.pressed
	elif event is InputEventScreenDrag:
		idx = event.index
		pos = event.position
		is_drag = true
	elif event is InputEventMouse and event.device == InputEvent.DEVICE_ID_EMULATION:
		return  # the engine's mouse copy of a touch handled above
	elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and Settings.touch_mode == Settings.TouchMode.ALWAYS:
		idx = _mouse_touch_id
		pos = event.position
		pressed = event.pressed
	elif event is InputEventMouseMotion and Settings.touch_mode == Settings.TouchMode.ALWAYS and (event.button_mask & MOUSE_BUTTON_MASK_LEFT):
		idx = _mouse_touch_id
		pos = event.position
		is_drag = true
	else:
		return
	# Gestures keep viewport coordinates (the camera maps those to the ground);
	# buttons use this control's local space.
	var local := get_global_transform_with_canvas().affine_inverse() * pos
	if is_drag:
		_on_drag(idx, pos, local)
	elif pressed:
		_on_press(idx, pos, local)
	else:
		_on_release(idx)
	get_viewport().set_input_as_handled()
	queue_redraw()


func _on_press(idx: int, pos: Vector2, local: Vector2) -> void:
	for b in buttons:
		var tb := b as TouchButton
		if tb.touch == -2 and local.distance_to(_button_center(tb)) <= tb.radius + 10.0:
			tb.touch = idx
			tb.start = local
			tb.drag = Vector2.ZERO
			tb.press_time = Time.get_ticks_msec() / 1000.0
			if not tb.aimable:
				_pressed_bits |= tb.bit
			return
	if not gesture.is_down():
		gesture.press(pos, idx)


func _on_drag(idx: int, pos: Vector2, local: Vector2) -> void:
	if idx == gesture.pointer and gesture.is_down():
		gesture.move(pos)
		return
	for b in buttons:
		var tb := b as TouchButton
		if tb.touch == idx:
			tb.drag = local - tb.start


func _on_release(idx: int) -> void:
	if idx == gesture.pointer and gesture.is_down():
		var from := gesture.origin
		var to := gesture.current
		var kind := gesture.release()
		if kind == &"dash" or kind == &"tap":
			_gestures_done.append({"kind": kind, "from": from, "to": to})
		return
	for b in buttons:
		var tb := b as TouchButton
		if tb.touch == idx:
			if tb.aimable:
				if tb.drag.length() > 22.0:
					# Screen drag -> ground direction (screen up = north = -Z).
					_aim_out = Vector2(tb.drag.x, tb.drag.y).normalized()
				_pressed_bits |= tb.bit
			tb.touch = -2
			tb.drag = Vector2.ZERO


func _process(_delta: float) -> void:
	if visible:
		gesture.update_hold(Time.get_ticks_msec())
		queue_redraw()


func _draw() -> void:
	var f: Fighter = sim.active_fighter(team) if sim else null
	_draw_gesture()
	for b in buttons:
		_draw_button(b as TouchButton, f)


## A light rubber band under the finger; the dash itself is previewed on the
## arena by the battle view.
func _draw_gesture() -> void:
	var xf := get_global_transform_with_canvas().affine_inverse()
	var o := xf * gesture.origin
	var c := xf * gesture.current
	if gesture.is_aiming():
		var col := Color(1.0, 0.45, 0.4, 0.55) if gesture.is_cancelled() else Color(1.0, 0.92, 0.7, 0.5)
		draw_circle(o, 10.0, Color(col.r, col.g, col.b, 0.35))
		draw_line(o, c, col, 3.0, true)
		draw_arc(c, 18.0, 0, TAU, 28, col, 2.5)
	elif gesture.is_holding():
		var pulse := 0.5 + 0.5 * sin(Time.get_ticks_msec() * 0.012)
		draw_arc(c, 34.0 + pulse * 6.0, 0, TAU, 40, Color(0.6, 0.95, 1.0, 0.75), 3.0)


func _draw_button(tb: TouchButton, f: Fighter) -> void:
	var c := _button_center(tb)
	var pressed := tb.touch != -2
	var base := Color(0.08, 0.1, 0.12, 0.62 if not pressed else 0.85)
	draw_circle(c, tb.radius, base)
	var ring := Color(0.95, 0.78, 0.36, 0.95) if pressed else Color(0.95, 0.9, 0.75, 0.6)
	draw_arc(c, tb.radius, 0, TAU, 36, ring, 3.0)
	if tb.icon:
		var isz := tb.radius * 1.15
		draw_texture_rect(tb.icon, Rect2(c - Vector2(isz, isz) * 0.5, Vector2(isz, isz)), false)
	else:
		var tw := UiTheme.FONT_BOLD.get_string_size(tb.label, HORIZONTAL_ALIGNMENT_LEFT, -1, 18).x
		draw_string(UiTheme.FONT_BOLD, c + Vector2(-tw * 0.5, 6), tb.label, HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color(0.98, 0.94, 0.85))
	if f and tb.ability and tb.ability.surge_stages > 0:
		var need := float(tb.ability.surge_stages) * SurgeSystem.PER_STAGE
		var wait := clampf(1.0 - f.surge / need, 0.0, 1.0)
		UiTheme.draw_wait_sweep(self, c, tb.radius - 2.0, wait)
		UiTheme.draw_surge_pips(self, c, tb.radius, tb.ability.surge_stages, wait <= 0.0)
	if tb.aimable and tb.touch != -2 and tb.drag.length() > 22.0:
		# Attacks run along a row or column: show the lane the drag picks.
		var dir := Cardinal.snap(tb.drag)
		draw_line(c, c + dir * (tb.radius + 70.0), Color(1.0, 0.85, 0.4, 0.9), 5.0)
		draw_circle(c + dir * (tb.radius + 70.0), 9, Color(1.0, 0.85, 0.4, 0.9))
