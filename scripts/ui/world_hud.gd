class_name WorldHUD
extends CanvasLayer
## Exploration HUD: objective tracker, floating interact prompt, toasts,
## trust meter, control hints, and touch controls (joystick, interact,
## sneak toggle, journal, menu).

signal menu_requested
signal journal_requested

var root: Control
var objective_panel: PanelContainer
var objective_label: RichTextLabel
var prompt: PanelContainer
var prompt_label: Label
var toast_box: VBoxContainer
var trust_panel: PanelContainer
var trust_bar: ProgressBar
var hints: Label
var explorer: Explorer
var camera: ExplorationCamera
var touch: WorldTouch
var _objective := ""


func _ready() -> void:
	layer = 10
	root = Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.theme = UiTheme.get_theme()
	add_child(root)
	objective_panel = PanelContainer.new()
	objective_panel.add_theme_stylebox_override("panel", UiTheme.panel_box("panel_wood"))
	UiTheme.place(objective_panel, Vector2(0, 0), Vector2(14, 12), Vector2(430, 0))
	objective_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(objective_panel)
	var vb := VBoxContainer.new()
	objective_panel.add_child(vb)
	vb.add_child(UiTheme.label("OBJECTIVE", 14, UiTheme.GOLD, true))
	objective_label = RichTextLabel.new()
	objective_label.bbcode_enabled = true
	objective_label.fit_content = true
	objective_label.scroll_active = false
	objective_label.custom_minimum_size = Vector2(400, 0)
	objective_label.add_theme_font_override("normal_font", UiTheme.FONT_REGULAR)
	objective_label.add_theme_font_override("bold_font", UiTheme.FONT_BOLD)
	objective_label.add_theme_font_size_override("normal_font_size", 19)
	objective_label.add_theme_font_size_override("bold_font_size", 19)
	objective_label.add_theme_color_override("default_color", UiTheme.PARCHMENT)
	objective_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vb.add_child(objective_label)
	prompt = PanelContainer.new()
	var ps := StyleBoxFlat.new()
	ps.bg_color = Color(0.07, 0.05, 0.09, 0.85)
	ps.border_color = UiTheme.GOLD
	ps.set_border_width_all(2)
	ps.set_content_margin_all(6)
	prompt.add_theme_stylebox_override("panel", ps)
	prompt.mouse_filter = Control.MOUSE_FILTER_IGNORE
	prompt_label = UiTheme.label("", 18, UiTheme.PARCHMENT, true)
	prompt.add_child(prompt_label)
	prompt.visible = false
	root.add_child(prompt)
	toast_box = VBoxContainer.new()
	toast_box.alignment = BoxContainer.ALIGNMENT_BEGIN
	UiTheme.place(toast_box, Vector2(0.5, 0), Vector2(-300, 90), Vector2(600, 200))
	toast_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(toast_box)
	trust_panel = PanelContainer.new()
	UiTheme.place(trust_panel, Vector2(0.5, 1), Vector2(-200, -250), Vector2(400, 60))
	trust_panel.visible = false
	trust_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(trust_panel)
	var tv := VBoxContainer.new()
	trust_panel.add_child(tv)
	tv.add_child(UiTheme.label("Trust", 16, Color(1.0, 0.75, 0.6), true))
	trust_bar = ProgressBar.new()
	trust_bar.show_percentage = false
	trust_bar.custom_minimum_size = Vector2(360, 16)
	var fill := StyleBoxFlat.new()
	fill.bg_color = Color(1.0, 0.55, 0.45)
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0.12, 0.08, 0.1)
	trust_bar.add_theme_stylebox_override("fill", fill)
	trust_bar.add_theme_stylebox_override("background", bg)
	tv.add_child(trust_bar)
	hints = UiTheme.label("WASD move · Shift sneak · E interact · J journal · Esc menu", 14, Color(0.9, 0.86, 0.75, 0.85))
	UiTheme.place(hints, Vector2(0, 1), Vector2(16, -32), Vector2(700, 24))
	root.add_child(hints)
	touch = WorldTouch.new()
	root.add_child(touch)
	touch.menu_pressed.connect(func() -> void: menu_requested.emit())
	touch.journal_pressed.connect(func() -> void: journal_requested.emit())
	_apply_touch()
	Events.settings_changed.connect(_apply_touch)


func _apply_touch() -> void:
	var on := Settings.touch_controls_enabled()
	touch.visible = on
	hints.visible = not on


func set_objective(text: String) -> void:
	if text == _objective:
		return
	var first := _objective == ""
	_objective = text
	objective_label.text = text
	objective_panel.visible = text != ""
	if not first and text != "":
		Audio.sfx(&"quest_update", -4.0)
		objective_panel.modulate = Color(1.6, 1.4, 0.9)
		var tw := create_tween()
		tw.tween_property(objective_panel, "modulate", Color.WHITE, 0.8)


func toast(text: String, color: Color = UiTheme.PARCHMENT) -> void:
	var p := PanelContainer.new()
	p.add_theme_stylebox_override("panel", UiTheme.panel_box("panel_wood"))
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var l := UiTheme.label(text, 20, color, true)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	p.add_child(l)
	toast_box.add_child(p)
	p.modulate.a = 0.0
	var tw := p.create_tween()
	tw.tween_property(p, "modulate:a", 1.0, 0.2)
	tw.tween_interval(2.6)
	tw.tween_property(p, "modulate:a", 0.0, 0.4)
	tw.tween_callback(p.queue_free)


func show_trust(visible_now: bool, value: float = 0.0) -> void:
	trust_panel.visible = visible_now
	trust_bar.value = value * 100.0


func _process(_delta: float) -> void:
	if explorer == null or camera == null:
		return
	explorer.touch_move = touch.move_vector() if touch.visible else Vector2.ZERO
	explorer.touch_sneak = touch.sneak_on and touch.visible
	var f := explorer.current_focus()
	if f and explorer.controllable and not camera.is_position_behind(f.prompt_position()):
		var key := "Tap" if touch.visible else "E"
		prompt_label.text = "[%s] %s" % [key, f.prompt]
		var sp := camera.unproject_position(f.prompt_position())
		var vp_scale := root.get_global_transform_with_canvas().affine_inverse()
		var local := vp_scale * sp
		prompt.position = local - Vector2(prompt.size.x * 0.5, prompt.size.y)
		prompt.visible = true
		touch.interact_visible = true
	else:
		prompt.visible = false
		touch.interact_visible = false
	if touch.consume_interact():
		explorer.try_interact()


## Minimal exploration touch layer.
class WorldTouch:
	extends Control
	signal menu_pressed
	signal journal_pressed
	var sneak_on := false
	var interact_visible := false
	var _joy_touch := -2
	var _joy_center := Vector2.ZERO
	var _joy_vec := Vector2.ZERO
	var _interact_pressed := false

	func _init() -> void:
		set_anchors_preset(Control.PRESET_FULL_RECT)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func move_vector() -> Vector2:
		return _joy_vec

	func consume_interact() -> bool:
		var p := _interact_pressed
		_interact_pressed = false
		return p

	func _buttons() -> Dictionary:
		return {
			"interact": [size + Vector2(-110, -120), 58.0],
			"sneak": [size + Vector2(-240, -80), 40.0],
			"journal": [Vector2(size.x - 160, 54), 32.0],
			"menu": [Vector2(size.x - 70, 54), 32.0],
		}

	func _input(event: InputEvent) -> void:
		if not visible:
			return
		var idx := -2
		var pos := Vector2.ZERO
		var pressed := false
		var drag := false
		if event is InputEventScreenTouch:
			idx = event.index
			pos = event.position
			pressed = event.pressed
		elif event is InputEventScreenDrag:
			idx = event.index
			pos = event.position
			drag = true
		elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and Settings.touch_mode == Settings.TouchMode.ALWAYS:
			idx = -10
			pos = event.position
			pressed = event.pressed
		elif event is InputEventMouseMotion and Settings.touch_mode == Settings.TouchMode.ALWAYS and (event.button_mask & MOUSE_BUTTON_MASK_LEFT):
			idx = -10
			pos = event.position
			drag = true
		else:
			return
		pos = get_global_transform_with_canvas().affine_inverse() * pos
		if drag:
			if idx == _joy_touch:
				var d := pos - _joy_center
				if d.length() > 86.0:
					_joy_center = pos - d.normalized() * 86.0
					d = pos - _joy_center
				_joy_vec = d / 86.0 if d.length() > 18.0 else Vector2.ZERO
			return
		if pressed:
			var b := _buttons()
			for key in b.keys():
				if pos.distance_to(b[key][0]) <= float(b[key][1]) + 10.0:
					match key:
						"interact":
							_interact_pressed = true
						"sneak":
							sneak_on = not sneak_on
						"journal":
							journal_pressed.emit()
						"menu":
							menu_pressed.emit()
					get_viewport().set_input_as_handled()
					queue_redraw()
					return
			if pos.x < size.x * 0.5 and _joy_touch == -2:
				_joy_touch = idx
				_joy_center = pos
				_joy_vec = Vector2.ZERO
		elif idx == _joy_touch:
			_joy_touch = -2
			_joy_vec = Vector2.ZERO
		queue_redraw()

	func _process(_d: float) -> void:
		if visible:
			queue_redraw()

	func _draw() -> void:
		var home := Vector2(150, size.y - 150) if _joy_touch == -2 else _joy_center
		draw_circle(home, 86, Color(0.05, 0.05, 0.08, 0.35))
		draw_arc(home, 86, 0, TAU, 40, Color(0.95, 0.9, 0.75, 0.55), 3.0)
		draw_circle(home + _joy_vec * 86.0, 32, Color(0.95, 0.9, 0.75, 0.6))
		var b := _buttons()
		for key in b.keys():
			var c: Vector2 = b[key][0]
			var r: float = b[key][1]
			var lit: bool = (key == "sneak" and sneak_on) or (key == "interact" and interact_visible)
			draw_circle(c, r, Color(0.08, 0.1, 0.12, 0.7 if lit else 0.5))
			draw_arc(c, r, 0, TAU, 32, UiTheme.GOLD if lit else Color(0.95, 0.9, 0.75, 0.6), 3.0)
			var label: String = {"interact": "ACT", "sneak": "SNEAK", "journal": "JRNL", "menu": "II"}[key]
			var fz := 18 if r > 40 else 14
			var tw := UiTheme.FONT_BOLD.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, fz).x
			draw_string(UiTheme.FONT_BOLD, c + Vector2(-tw * 0.5, fz * 0.35), label, HORIZONTAL_ALIGNMENT_LEFT, -1, fz, UiTheme.PARCHMENT)
