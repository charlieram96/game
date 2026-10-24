class_name TouchControls
extends Control
## Landscape mobile controls: virtual joystick (left), action cluster (right).
##
## * Joystick: floating — it appears where the left thumb lands.
## * Attack: hold to keep attacking (strings chain automatically).
## * Abilities: tap = auto-aim at the opponent; press-and-drag = aim, release
##   to cast. A ground-direction arrow shows the drag aim.
## * Dash uses the joystick direction (strict 4-way rule applies), Focus and
##   Guard are hold buttons.
## Works with real touch or with the mouse ("simulated touch" on desktop).

const MIN_BUTTON := 64.0

var sim: BattleSim
var team := 0
var buttons: Array = []
var _joy_center := Vector2.ZERO
var _joy_vec := Vector2.ZERO
var _joy_touch := -2
var _joy_radius := 86.0
var _joy_home := Vector2.ZERO
var _pressed_bits := 0
var _aim_out := Vector2.ZERO
var _axis_hint := Cardinal.AXIS_UNKNOWN
var _active := false
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
	_add("dash", InputCommand.DASH, Vector2(-250, -70), 42, false, false, null, "DASH")
	_add("guard", InputCommand.GUARD, Vector2(-62, -250), 36, true, false, null, "GRD")
	_add("focus", InputCommand.FOCUS, Vector2(-330, -170), 36, true, false, null, "FOC")
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


func move_vector() -> Vector2:
	return _joy_vec


func joystick_axis_hint() -> int:
	return _axis_hint


func held_bits() -> int:
	var bits := 0
	for b in buttons:
		var tb := b as TouchButton
		if tb.touch != -2 and tb.hold:
			bits |= tb.bit
	return bits


func consume_pressed() -> int:
	var p := _pressed_bits
	_pressed_bits = 0
	return p


func consume_aim() -> Vector2:
	var a := _aim_out
	_aim_out = Vector2.ZERO
	return a


func button_rect(b: TouchButton) -> Rect2:
	var c := _button_center(b)
	return Rect2(c - Vector2(b.radius, b.radius), Vector2(b.radius, b.radius) * 2.0)


func _button_center(b: TouchButton) -> Vector2:
	return size + b.center


func _joystick_home() -> Vector2:
	return Vector2(150, size.y - 150)


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
	pos = get_global_transform_with_canvas().affine_inverse() * pos
	if is_drag:
		_on_drag(idx, pos)
	elif pressed:
		_on_press(idx, pos)
	else:
		_on_release(idx, pos)
	get_viewport().set_input_as_handled()
	queue_redraw()


func _on_press(idx: int, pos: Vector2) -> void:
	for b in buttons:
		var tb := b as TouchButton
		if tb.touch == -2 and pos.distance_to(_button_center(tb)) <= tb.radius + 10.0:
			tb.touch = idx
			tb.start = pos
			tb.drag = Vector2.ZERO
			tb.press_time = Time.get_ticks_msec() / 1000.0
			if not tb.aimable:
				_pressed_bits |= tb.bit
			return
	if pos.x < size.x * 0.45 and _joy_touch == -2:
		_joy_touch = idx
		_joy_center = pos
		_joy_vec = Vector2.ZERO


func _on_drag(idx: int, pos: Vector2) -> void:
	if idx == _joy_touch:
		var d := pos - _joy_center
		if d.length() > _joy_radius:
			_joy_center = pos - d.normalized() * _joy_radius
			d = pos - _joy_center
		var v := d / _joy_radius
		_joy_vec = v if v.length() > 0.25 else Vector2.ZERO
		if _joy_vec != Vector2.ZERO:
			_axis_hint = Cardinal.AXIS_HORIZONTAL if absf(_joy_vec.x) >= absf(_joy_vec.y) else Cardinal.AXIS_VERTICAL
		return
	for b in buttons:
		var tb := b as TouchButton
		if tb.touch == idx:
			tb.drag = pos - tb.start


func _on_release(idx: int, _pos: Vector2) -> void:
	if idx == _joy_touch:
		_joy_touch = -2
		_joy_vec = Vector2.ZERO
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
		queue_redraw()


func _draw() -> void:
	var f: Fighter = sim.active_fighter(team) if sim else null
	# Joystick
	var home := _joystick_home() if _joy_touch == -2 else _joy_center
	draw_circle(home, _joy_radius, Color(0.05, 0.05, 0.08, 0.35))
	draw_arc(home, _joy_radius, 0, TAU, 40, Color(0.95, 0.9, 0.75, 0.55), 3.0)
	draw_circle(home + _joy_vec * _joy_radius, 34, Color(0.95, 0.9, 0.75, 0.75 if _joy_touch != -2 else 0.45))
	# Buttons
	for b in buttons:
		var tb := b as TouchButton
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
		if f and tb.ability and tb.ability.cooldown_ticks > 0:
			var left := f.cooldown_of(tb.ability)
			if left > 0:
				var ratio := float(left) / float(tb.ability.cooldown_ticks)
				var pts := PackedVector2Array([c])
				for i in 25:
					var a := -PI * 0.5 + TAU * ratio * float(i) / 24.0
					pts.append(c + Vector2(cos(a), sin(a)) * (tb.radius - 2.0))
				draw_colored_polygon(pts, Color(0, 0, 0, 0.6))
		if tb.aimable and pressed and tb.drag.length() > 22.0:
			var dir := tb.drag.normalized()
			draw_line(c, c + dir * (tb.radius + 70.0), Color(1.0, 0.85, 0.4, 0.9), 5.0)
			draw_circle(c + dir * (tb.radius + 70.0), 9, Color(1.0, 0.85, 0.4, 0.9))
