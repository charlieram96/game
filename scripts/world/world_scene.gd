extends Node3D
## Exploration scene root: builds the region, the explorer, camera, lighting,
## HUD, dialogue and the story director; owns time of day, music zones,
## autosave, pause and the journal.

var builder: MossfordBuilder
var rig: LightingRig
var post: PostFX
var player: Explorer
var camera: ExplorationCamera
var hud: WorldHUD
var dialogue: DialogueBox
var pause_menu: PauseMenu
var journal: JournalScreen
var timing_ring: TimingRing
var story: ChapterOne
var _night := 0.0
var _autosave := 30.0
var _shot_path := ""
var _shot_frames := -1


func _ready() -> void:
	if SaveService.profile == null:
		# Started directly (dev): make a fresh profile.
		SaveService.new_profile("Wren")
	_apply_dev_args()
	rig = LightingRig.new()
	add_child(rig)
	builder = MossfordBuilder.new()
	builder.build(self)
	player = Explorer.new()
	add_child(player)
	player.surface_lookup = builder.surface_at
	var spawn: Vector3 = builder.anchors["spawn_home"]
	if SaveService.profile.position != Vector3.ZERO:
		spawn = SaveService.profile.position
	player.global_position = spawn
	player.facing = Vector2(0, 1)
	camera = ExplorationCamera.new()
	camera.target = player
	add_child(camera)
	camera.make_current()
	camera.snap()
	post = PostFX.new()
	add_child(post)
	post.set_focus(0.55, 0.2)
	hud = WorldHUD.new()
	add_child(hud)
	hud.explorer = player
	hud.camera = camera
	hud.menu_requested.connect(_open_pause)
	hud.journal_requested.connect(_open_journal)
	dialogue = DialogueBox.new()
	add_child(dialogue)
	pause_menu = PauseMenu.new()
	add_child(pause_menu)
	pause_menu.resumed.connect(_close_pause)
	pause_menu.quit_requested.connect(_quit_to_title)
	journal = JournalScreen.new()
	add_child(journal)
	timing_ring = TimingRing.new()
	add_child(timing_ring)
	story = ChapterOne.new()
	add_child(story)
	story.begin(self)
	SaveService.profile.scene = Game.WORLD_SCENE
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--shot="):
			_shot_path = arg.substr(7)
			_shot_frames = 40
	# Returning from a battle?
	if not Game.last_result.is_empty():
		var result := Game.last_result
		Game.last_result = {}
		story.on_battle_result(result)


## Dev helpers: --at=x,z places the explorer, --step=<name> fast-forwards the story.
func _apply_dev_args() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--at="):
			var p := arg.substr(5).split(",")
			SaveService.profile.position = Vector3(float(p[0]), 0, float(p[1]))
		elif arg.begins_with("--step="):
			var order := ["met_hesper", "forest_seen", "observed_emberlyn", "moss_1", "moss_2", "moss_3", "fire_lit", "befriended", "training_done", "duel_won", "shrine_done"]
			var stop := {"find_kith": 1, "forest": 2, "fire": 6, "befriend": 7, "training": 8, "duel": 9, "ending": 10, "complete": 11}
			var n := int(stop.get(arg.substr(7), 0))
			for i in n:
				SaveService.profile.set_flag(order[i])
			if n >= 6:
				SaveService.profile.set_flag("moss_count", 3)
			if n >= 8 and SaveService.profile.party.is_empty():
				SaveService.profile.party.append(Registry.make_creature(&"emberlyn", 5))


func _process(delta: float) -> void:
	_update_music()
	_autosave -= delta
	if _autosave <= 0.0:
		_autosave = 60.0
		if not story.busy:
			SaveService.profile.position = player.global_position
			SaveService.save()
	if _shot_frames > 0:
		_shot_frames -= 1
		if _shot_frames == 0:
			get_viewport().get_texture().get_image().save_png(_shot_path)
			get_tree().quit()


func _update_music() -> void:
	if story.busy and Audio.current_music() == &"shrine_theme":
		return
	var p := player.global_position
	var track := &"village_theme"
	if _night > 0.5:
		track = &"shrine_theme"
	elif p.x < -16.5:
		track = &"forest_theme"
	Audio.music(track, 1.6)


func set_time_of_day(preset: StringName, duration: float = 0.0) -> void:
	rig.apply(preset, duration)
	var target := 1.0 if preset == &"night" else (0.55 if preset == &"dusk" else 0.0)
	if duration <= 0.0:
		_night = target
		builder.set_night_amount(target)
		return
	var tw := create_tween()
	tw.tween_method(func(v: float) -> void:
		_night = v
		builder.set_night_amount(v), _night, target, duration)


func start_battle(setup: BattleSetup) -> void:
	SaveService.profile.position = player.global_position
	SaveService.save()
	Game.start_battle(setup, Game.WORLD_SCENE)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed(&"pause") and not dialogue.active:
		_open_pause()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed(&"journal") and not dialogue.active and not story.busy:
		_open_journal()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed(&"toggle_touch"):
		Settings.touch_mode = Settings.TouchMode.NEVER if Settings.touch_controls_enabled() else Settings.TouchMode.ALWAYS
		Settings.save_settings()


func _open_pause() -> void:
	if journal.visible:
		return
	get_tree().paused = true
	pause_menu.open(false)


func _close_pause() -> void:
	pause_menu.close()
	get_tree().paused = false


func _open_journal() -> void:
	journal.open()


func _quit_to_title() -> void:
	get_tree().paused = false
	SaveService.profile.position = player.global_position
	SaveService.save()
	Audio.stop_all_loops()
	Game.goto_scene(Game.TITLE_SCENE)


## Simple name prompt. Awaitable; returns the entered (or default) name.
func ask_name(title: String, default_name: String) -> String:
	if Game.autoplay:
		return default_name
	var layer := CanvasLayer.new()
	layer.layer = 40
	add_child(layer)
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.theme = UiTheme.get_theme()
	layer.add_child(root)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(center)
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(460, 0)
	center.add_child(panel)
	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 12)
	panel.add_child(vb)
	vb.add_child(UiTheme.label(title, 26, UiTheme.GOLD, true))
	var edit := LineEdit.new()
	edit.text = default_name
	edit.max_length = 14
	edit.select_all_on_focus = true
	vb.add_child(edit)
	var ok := Button.new()
	ok.text = "OK"
	ok.custom_minimum_size = Vector2(140, 48)
	vb.add_child(ok)
	edit.grab_focus()
	var done := [false]
	ok.pressed.connect(func() -> void: done[0] = true)
	edit.text_submitted.connect(func(_t: String) -> void: done[0] = true)
	while not done[0]:
		await get_tree().process_frame
	Audio.sfx(&"ui_select")
	var result := edit.text.strip_edges()
	layer.queue_free()
	return result if result != "" else default_name


## The end-of-chapter card. Awaitable.
func chapter_card() -> void:
	if Game.autoplay:
		return
	var layer := CanvasLayer.new()
	layer.layer = 60
	add_child(layer)
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.theme = UiTheme.get_theme()
	layer.add_child(root)
	var bg := ColorRect.new()
	bg.color = Color(0.03, 0.02, 0.06, 0.0)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(bg)
	var tw := create_tween()
	tw.tween_property(bg, "color:a", 0.92, 1.2)
	await tw.finished
	var vb := VBoxContainer.new()
	vb.alignment = BoxContainer.ALIGNMENT_CENTER
	vb.set_anchors_preset(Control.PRESET_FULL_RECT)
	vb.add_theme_constant_override("separation", 18)
	root.add_child(vb)
	var lines := [["WILDBOUND", 72, UiTheme.GOLD], ["Chapter 1 — The Kindling", 34, UiTheme.PARCHMENT], ["complete", 24, Color(0.8, 0.78, 0.7)], ["", 18, Color.WHITE], ["Thank you for playing this early prototype!", 22, UiTheme.PARCHMENT], ["Free Battle and Local Versus are waiting on the title screen.", 20, Color(0.8, 0.78, 0.7)], ["", 14, Color.WHITE], ["Press any key", 16, Color(0.7, 0.68, 0.6)]]
	for l in lines:
		var lab := UiTheme.label(l[0], l[1], l[2], true, 8)
		lab.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lab.modulate.a = 0.0
		vb.add_child(lab)
		var t2 := create_tween()
		t2.tween_property(lab, "modulate:a", 1.0, 0.6)
		await get_tree().create_timer(0.35).timeout
	Audio.music(&"title_theme", 2.0)
	await get_tree().create_timer(1.0).timeout
	var pressed := [false]
	var cb := func(e: InputEvent) -> void:
		if (e is InputEventKey or e is InputEventMouseButton or e is InputEventScreenTouch or e is InputEventJoypadButton) and e.is_pressed():
			pressed[0] = true
	root.gui_input.connect(cb)
	while not pressed[0]:
		if Input.is_anything_pressed():
			pressed[0] = true
		await get_tree().process_frame
