class_name SettingsPanel
extends VBoxContainer
## Settings controls shared by the title screen and the pause menu.

func _ready() -> void:
	add_theme_constant_override("separation", 8)
	_slider("Music", Settings.music_volume, func(v: float) -> void: Settings.music_volume = v)
	_slider("Sound effects", Settings.sfx_volume, func(v: float) -> void: Settings.sfx_volume = v)
	_slider("Screen shake", Settings.screen_shake, func(v: float) -> void: Settings.screen_shake = v)
	_option("Touch controls", ["Auto", "Always (simulate on desktop)", "Never"], int(Settings.touch_mode), func(i: int) -> void: Settings.touch_mode = i as Settings.TouchMode)
	_option("AI difficulty", ["Easy", "Normal", "Hard"], ["easy", "normal", "hard"].find(String(Settings.ai_difficulty)), func(i: int) -> void: Settings.ai_difficulty = StringName(["easy", "normal", "hard"][i]))
	_option("Graphics", ["High", "Low (faster)"], 1 if Settings.graphics_low else 0, func(i: int) -> void: Settings.graphics_low = i == 1)
	var checks := HBoxContainer.new()
	checks.add_theme_constant_override("separation", 8)
	add_child(checks)
	_check("Tilt-shift", Settings.tilt_shift, func(b: bool) -> void: Settings.tilt_shift = b, checks)
	_check("Show FPS", Settings.show_fps, func(b: bool) -> void: Settings.show_fps = b, checks)
	_check("Hitboxes (F3)", Settings.show_hitboxes, func(b: bool) -> void: Settings.show_hitboxes = b, checks)


func _row(text: String) -> HBoxContainer:
	var hb := HBoxContainer.new()
	hb.add_theme_constant_override("separation", 12)
	var l := UiTheme.label(text, 20)
	l.custom_minimum_size = Vector2(230, 0)
	hb.add_child(l)
	add_child(hb)
	return hb


func _slider(text: String, value: float, setter: Callable) -> void:
	var hb := _row(text)
	var s := HSlider.new()
	s.min_value = 0.0
	s.max_value = 1.0
	s.step = 0.05
	s.value = value
	s.custom_minimum_size = Vector2(240, 32)
	s.value_changed.connect(func(v: float) -> void:
		setter.call(v)
		Settings.save_settings())
	hb.add_child(s)


func _option(text: String, items: Array, selected: int, setter: Callable) -> void:
	var hb := _row(text)
	var o := OptionButton.new()
	for it in items:
		o.add_item(it)
	o.selected = maxi(0, selected)
	o.custom_minimum_size = Vector2(240, 40)
	o.item_selected.connect(func(i: int) -> void:
		setter.call(i)
		Settings.save_settings())
	hb.add_child(o)


func _check(text: String, value: bool, setter: Callable, parent: Control) -> void:
	var c := CheckBox.new()
	c.text = text
	c.button_pressed = value
	c.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	c.toggled.connect(func(b: bool) -> void:
		setter.call(b)
		Settings.save_settings())
	parent.add_child(c)
