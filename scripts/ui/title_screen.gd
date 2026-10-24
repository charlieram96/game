extends Node3D
## Title screen: a small HD-2D diorama (a Warden and their Emberlyn by a
## campfire at dusk) behind the logo and menus.

const SPECIES := [&"emberlyn", &"stoneback"]

var rig: LightingRig
var cam: Camera3D
var ui: Control
var menu: VBoxContainer
var panel: PanelContainer
var _t := 0.0
var _shot_path := ""
var _shot_frames := -1


func _ready() -> void:
	_build_diorama()
	_build_ui()
	_main_menu()
	Audio.music(&"title_theme", 1.5)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--shot="):
			_shot_path = arg.substr(7)
			_shot_frames = 50


func _process(delta: float) -> void:
	_t += delta
	cam.position = Vector3(-2.6 + sin(_t * 0.07) * 1.2, 5.0 + sin(_t * 0.11) * 0.15, 11.5)
	cam.look_at(Vector3(-2.2 + sin(_t * 0.07) * 0.5, 0.6, 0.0))
	if _shot_frames > 0:
		_shot_frames -= 1
		if _shot_frames == 0:
			get_viewport().get_texture().get_image().save_png(_shot_path)
			get_tree().quit()


func _build_diorama() -> void:
	rig = LightingRig.new()
	add_child(rig)
	rig.apply(&"dusk")
	var post := PostFX.new()
	add_child(post)
	post.set_focus(0.62, 0.14)
	post.set_param("vignette", 0.5)
	var img := Image.create(40, 40, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	for y in 40:
		for x in 40:
			var w := Vector2(x - 20, y - 20) * 0.5
			if w.length() < 1.6:
				img.set_pixel(x, y, Color(1, 0, 0, 0))
			elif EnvKit.noise2(w.x * 0.5, w.y * 0.5, 9) > 0.6:
				img.set_pixel(x, y, Color(0, 0, 0, 1))
	EnvKit.terrain(self, Rect2(-10, -10, 20, 20), img, ["grass_a", "dirt_path", "cobble", "grass_dark", "flower_meadow"])
	var rng := RandomNumberGenerator.new()
	rng.seed = 5
	EnvKit.foliage(self, "tree_oak_a", Vector3(-3.0, 0, -2.2), 1.3, true, 1.0)
	for p in [Vector3(4.2, 0, -3.5), Vector3(-6.5, 0, -4.5), Vector3(6.5, 0, -1.0), Vector3(-7.5, 0, 0.5), Vector3(1.5, 0, -6.0)]:
		EnvKit.foliage(self, ["tree_pine", "tree_glimmer", "tree_oak_b"][rng.randi() % 3], p, rng.randf_range(1.0, 1.2), true, 1.0)
	for i in 30:
		var p2 := Vector3(rng.randf_range(-8, 8), 0, rng.randf_range(-6, 4))
		if Vector2(p2.x, p2.z).length() < 2.2:
			continue
		EnvKit.foliage(self, ["grass_tuft_a", "grass_tuft_b", "flowers_yellow", "flowers_blue", "fern_a", "bush_b"][i % 6], p2, 1.0, false, 0.6)
	var fire := EnvKit.animated_prop(self, "campfire", "lit", Vector3(0.0, 0, 0.0))
	fire.set_param("emission_strength", 2.5)
	fire.set_param("emission_threshold", 0.55)
	var light := OmniLight3D.new()
	light.light_color = Color(1.0, 0.6, 0.3)
	light.light_energy = 2.6
	light.omni_range = 7.0
	light.position = Vector3(0, 1.0, 0.3)
	add_child(light)
	var flicker := create_tween().set_loops()
	flicker.tween_property(light, "light_energy", 2.0, 0.35)
	flicker.tween_property(light, "light_energy", 2.7, 0.25)
	var warden := PixelSprite3D.new()
	warden.load_manifest("res://assets/sprites/characters/explorer.json")
	warden.position = Vector3(-1.3, 0, 0.5)
	add_child(warden)
	warden.play("sit", "e")
	var ember := PixelSprite3D.new()
	ember.load_manifest("res://assets/sprites/kith/emberlyn.json")
	ember.set_param("emission_strength", 2.0)
	ember.position = Vector3(1.2, 0, 0.6)
	add_child(ember)
	ember.play("curl", "s")
	var moth := PixelSprite3D.new()
	moth.load_manifest("res://assets/sprites/kith/lanternmoth.json")
	moth.set_param("emission_strength", 2.0)
	moth.position = Vector3(2.4, 1.2, -0.6)
	add_child(moth)
	moth.play("hover", "s")
	var bob := create_tween().set_loops()
	bob.tween_property(moth, "position:y", 1.4, 1.4).set_trans(Tween.TRANS_SINE)
	bob.tween_property(moth, "position:y", 1.1, 1.4).set_trans(Tween.TRANS_SINE)
	var flies := CPUParticles3D.new()
	flies.amount = 30
	flies.lifetime = 6.0
	flies.preprocess = 6.0
	flies.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	flies.emission_box_extents = Vector3(7, 1.2, 4)
	flies.position = Vector3(0, 1.4, -1)
	flies.spread = 180.0
	flies.initial_velocity_min = 0.05
	flies.initial_velocity_max = 0.2
	flies.gravity = Vector3.ZERO
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE * 0.06
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.albedo_color = Color(0.9, 1.0, 0.6)
	m.emission_enabled = true
	m.emission = Color(0.8, 1.0, 0.5)
	m.emission_energy_multiplier = 2.0
	quad.material = m
	flies.mesh = quad
	add_child(flies)
	cam = Camera3D.new()
	cam.fov = 34.0
	add_child(cam)
	cam.make_current()
	RenderingServer.global_shader_parameter_set("sprite_stretch", 1.1)
	RenderingServer.global_shader_parameter_set("occluder_active", 0.0)


func _build_ui() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 10
	add_child(layer)
	ui = Control.new()
	ui.set_anchors_preset(Control.PRESET_FULL_RECT)
	ui.theme = UiTheme.get_theme()
	layer.add_child(ui)
	var logo := UiTheme.label("WILDBOUND", 104, UiTheme.GOLD, true, 18)
	logo.add_theme_color_override("font_outline_color", Color(0.18, 0.08, 0.05))
	logo.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	UiTheme.place(logo, Vector2(0.5, 0), Vector2(-500, 28), Vector2(1000, 120))
	ui.add_child(logo)
	var sub := UiTheme.label("a tale of trust between people and kith", 22, Color(0.95, 0.88, 0.75), false, 8)
	sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	UiTheme.place(sub, Vector2(0.5, 0), Vector2(-500, 140), Vector2(1000, 32))
	ui.add_child(sub)
	var tag := UiTheme.label("v0 prototype · Chapter 1: The Kindling", 14, Color(0.85, 0.8, 0.7, 0.8))
	UiTheme.place(tag, Vector2(1, 1), Vector2(-330, -30), Vector2(320, 24))
	tag.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	ui.add_child(tag)
	panel = PanelContainer.new()
	UiTheme.place(panel, Vector2(0, 1), Vector2(48, -420), Vector2(380, 380))
	ui.add_child(panel)
	menu = VBoxContainer.new()
	menu.add_theme_constant_override("separation", 8)
	menu.alignment = BoxContainer.ALIGNMENT_CENTER
	panel.add_child(menu)


func _clear() -> void:
	for c in menu.get_children():
		c.queue_free()


func _button(text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(320, 46)
	b.pressed.connect(func() -> void:
		Audio.sfx(&"ui_select")
		cb.call())
	b.focus_entered.connect(func() -> void: Audio.sfx(&"ui_move", -10.0))
	menu.add_child(b)
	return b


func _main_menu() -> void:
	_clear()
	var first: Button = null
	if SaveService.has_save():
		first = _button("Continue", _continue)
	var nb := _button("New Journey", _new_journey)
	if first == null:
		first = nb
	_button("Free Battle", _free_battle_menu)
	_button("Local Versus", _versus_menu)
	_button("Settings", _settings)
	_button("How to Play", _how_to_play)
	if not OS.has_feature("web"):
		_button("Quit", func() -> void: get_tree().quit())
	first.grab_focus()


func _continue() -> void:
	if SaveService.load_profile():
		Game.goto_scene(Game.WORLD_SCENE, 0.6)


func _new_journey() -> void:
	if SaveService.has_save():
		_clear()
		menu.add_child(UiTheme.label("Start over? Your current\njourney will be replaced.", 20))
		_button("Yes, begin anew", _ask_name).grab_focus()
		_button("Back", _main_menu)
		return
	_ask_name()


func _ask_name() -> void:
	_clear()
	menu.add_child(UiTheme.label("What do they call you?", 22, UiTheme.GOLD, true))
	var edit := LineEdit.new()
	edit.text = "Wren"
	edit.max_length = 14
	edit.select_all_on_focus = true
	menu.add_child(edit)
	var go := func() -> void:
		var player_name := edit.text.strip_edges()
		SaveService.new_profile(player_name if player_name != "" else "Wren")
		SaveService.save()
		_intro()
	edit.text_submitted.connect(func(_t: String) -> void: go.call())
	_button("Begin", go)
	_button("Back", _main_menu)
	edit.grab_focus()


func _intro() -> void:
	panel.visible = false
	var fade := ColorRect.new()
	fade.color = Color(0.02, 0.01, 0.04, 0.0)
	fade.set_anchors_preset(Control.PRESET_FULL_RECT)
	ui.add_child(fade)
	var tw := create_tween()
	tw.tween_property(fade, "color:a", 0.88, 1.0)
	await tw.finished
	var box := DialogueBox.new()
	add_child(box)
	await box.play("intro_card")
	Game.goto_scene(Game.WORLD_SCENE, 1.0)


func _free_battle_menu() -> void:
	_clear()
	menu.add_child(UiTheme.label("Free Battle", 26, UiTheme.GOLD, true))
	var mine := _option("Your kith", ["Emberlyn", "Stoneback"], 0)
	var foe := _option("Opponent", ["Emberlyn", "Stoneback"], 1)
	var diff := _option("AI", ["Easy", "Normal", "Hard"], ["easy", "normal", "hard"].find(String(Settings.ai_difficulty)))
	_button("Fight!", func() -> void:
		var d: StringName = [&"easy", &"normal", &"hard"][diff.selected]
		Game.start_battle(Game.quick_battle_setup(SPECIES[mine.selected], SPECIES[foe.selected], d), Game.TITLE_SCENE)).grab_focus()
	_button("Back", _main_menu)


func _versus_menu() -> void:
	_clear()
	menu.add_child(UiTheme.label("Local Versus", 26, UiTheme.GOLD, true))
	var p1 := _option("Player 1", ["Emberlyn", "Stoneback"], 0)
	var p2 := _option("Player 2", ["Emberlyn", "Stoneback"], 1)
	var note := UiTheme.label("P1: WASD + mouse  ·  P2: arrows, . attack,\n/ dash, ; ' [ ] specials, R-Ctrl guard, R-Shift focus.\nGamepads work for both.", 13, Color(0.85, 0.8, 0.7))
	menu.add_child(note)
	_button("Fight!", func() -> void:
		Game.start_battle(Game.versus_setup(SPECIES[p1.selected], SPECIES[p2.selected]), Game.TITLE_SCENE)).grab_focus()
	_button("Back", _main_menu)


func _option(label_text: String, items: Array, selected: int) -> OptionButton:
	var hb := HBoxContainer.new()
	var l := UiTheme.label(label_text, 18)
	l.custom_minimum_size = Vector2(120, 0)
	hb.add_child(l)
	var o := OptionButton.new()
	for it in items:
		o.add_item(it)
	o.selected = maxi(0, selected)
	o.custom_minimum_size = Vector2(190, 40)
	hb.add_child(o)
	menu.add_child(hb)
	return o


func _settings() -> void:
	_clear()
	panel.offset_top = -600
	panel.offset_right = 48 + 560
	menu.add_child(SettingsPanel.new())
	_button("Back", func() -> void:
		panel.offset_top = -420
		panel.offset_right = 48 + 380
		_main_menu()).grab_focus()


func _how_to_play() -> void:
	_clear()
	panel.offset_right = 48 + 880
	panel.offset_top = -600
	var rt := RichTextLabel.new()
	rt.bbcode_enabled = true
	rt.fit_content = true
	rt.custom_minimum_size = Vector2(820, 0)
	rt.add_theme_font_override("normal_font", UiTheme.FONT_REGULAR)
	rt.add_theme_font_override("bold_font", UiTheme.FONT_BOLD)
	rt.add_theme_font_size_override("normal_font_size", 16)
	rt.add_theme_font_size_override("bold_font_size", 18)
	rt.text = PauseMenu.CONTROLS_TEXT
	menu.add_child(rt)
	_button("Back", func() -> void:
		panel.offset_right = 48 + 380
		panel.offset_top = -420
		_main_menu()).grab_focus()
