extends Node3D
## Battle scene: owns the transport (simulation), input sources, view, HUD,
## touch controls, pause and results. The simulation steps exactly once per
## physics tick (60 Hz); rendering interpolates between ticks.

const SM := FighterSM.State

var setup: BattleSetup
var transport: LocalBattleTransport
var sim: BattleSim
var view: BattleView
var hud: BattleHUD
var touch: TouchControls
var post: PostFX
var player_input: LocalInputSource
var p2_input: LocalInputSource
var results: BattleResults
var pause_menu: PauseMenu
var training: TrainingDirector
var local_team := 0

var _slowmo := 0
var _slowmo_phase := 0
var _ended := false
var _end_timer := -1.0
var _shot_path := ""
var _demo := false


func _ready() -> void:
	setup = Game.take_pending_battle()
	if setup == null:
		setup = Game.quick_battle_setup(&"emberlyn", &"stoneback", Settings.ai_difficulty)
	_parse_dev_args()
	transport = LocalBattleTransport.new()
	transport.start(setup)
	sim = transport.sim
	post = PostFX.new()
	add_child(post)
	post.set_focus(0.5, 0.33)
	post.set_param("vignette", 0.28)
	view = BattleView.new()
	add_child(view)
	view.local_team = local_team
	view.build(sim, setup)
	view.feedback.connect(_on_feedback)
	hud = BattleHUD.new()
	add_child(hud)
	hud.build(sim, local_team, setup)
	hud.pause_requested.connect(_toggle_pause)
	touch = TouchControls.new()
	hud.root.add_child(touch)
	touch.setup(sim, local_team)
	_apply_touch_setting()
	Events.settings_changed.connect(_apply_touch_setting)
	_setup_inputs()
	results = BattleResults.new()
	add_child(results)
	results.rematch.connect(_rematch)
	results.continue_pressed.connect(_continue)
	pause_menu = PauseMenu.new()
	add_child(pause_menu)
	pause_menu.resumed.connect(_toggle_pause)
	pause_menu.quit_requested.connect(_quit_battle)
	if setup.mode == BattleSetup.Mode.TRAINING:
		training = TrainingDirector.new()
		add_child(training)
		training.begin(self)
	Audio.music(StringName(setup.metadata.get("music", "battle_theme")))
	if not setup.countdown:
		hud.show_message("FIGHT!", UiTheme.GOLD, 0.6)


func _parse_dev_args() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--shot="):
			_shot_path = arg.substr(7)
		if arg == "--demo":
			_demo = true


func _setup_inputs() -> void:
	player_input = LocalInputSource.new()
	player_input.camera = view.camera
	player_input.touch = touch
	if _demo:
		transport.set_input_source(0, CombatAI.new(AIProfile.preset(&"hard"), 77))
	elif String(setup.ai[0]) != "":
		transport.set_input_source(0, CombatAI.new(AIProfile.preset(setup.ai[0]), 17))
	else:
		transport.set_input_source(0, player_input)
	match setup.mode:
		BattleSetup.Mode.VERSUS:
			player_input.prefix = InputSetup.P1_PREFIX
			p2_input = LocalInputSource.new()
			p2_input.prefix = InputSetup.P2_PREFIX
			p2_input.allow_mouse = false
			transport.set_input_source(1, p2_input)
			InputSetup.assign_versus_pads()
			if not Input.joy_connection_changed.is_connected(_on_joy_changed):
				Input.joy_connection_changed.connect(_on_joy_changed)
		BattleSetup.Mode.TRAINING:
			pass  # TrainingDirector installs a TrainingAI
		_:
			var profile := AIProfile.preset(setup.ai[1] if String(setup.ai[1]) != "" else Settings.ai_difficulty)
			transport.set_input_source(1, CombatAI.new(profile, randi()))


func _on_joy_changed(_device: int, _connected: bool) -> void:
	InputSetup.assign_versus_pads()


func _apply_touch_setting() -> void:
	var on := Settings.touch_controls_enabled()
	touch.visible = on
	hud.set_touch_mode(on)
	Input.emulate_touch_from_mouse = false


func _input(event: InputEvent) -> void:
	if player_input:
		player_input.handle_input(event)
	if p2_input:
		p2_input.handle_input(event)
	if event.is_action_pressed(&"pause"):
		_toggle_pause()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed(&"debug_overlay"):
		Settings.show_hitboxes = not Settings.show_hitboxes
	elif event.is_action_pressed(&"toggle_touch"):
		Settings.touch_mode = Settings.TouchMode.NEVER if Settings.touch_controls_enabled() else Settings.TouchMode.ALWAYS
		Settings.save_settings()


func _physics_process(_delta: float) -> void:
	if get_tree().paused or _ended and _end_timer < 0.0:
		return
	if _slowmo > 0:
		_slowmo -= 1
		_slowmo_phase = (_slowmo_phase + 1) % 3
		if _slowmo_phase != 0:
			return
	if sim.is_finished():
		return
	transport.step()
	view.handle_events(sim.events)
	_handle_flow_events(sim.events)
	if training:
		training.on_tick(sim.events)


func _process(delta: float) -> void:
	var alpha := Engine.get_physics_interpolation_fraction()
	if _slowmo > 0:
		alpha = 1.0
	view.render(alpha, delta)
	hud.refresh(delta)
	if _end_timer >= 0.0:
		_end_timer -= delta
		if _end_timer < 0.0:
			_show_results()
	if _shot_path != "" and sim.tick > 260:
		var img := get_viewport().get_texture().get_image()
		img.save_png(_shot_path)
		_shot_path = ""
		get_tree().quit()


func _handle_flow_events(events: Array[BattleEvent]) -> void:
	for e in events:
		match e.type:
			BattleEvent.COUNTDOWN:
				hud.show_message(str(e.data.get("seconds", 3)), UiTheme.PARCHMENT, 0.55, 96)
			BattleEvent.FIGHT_START:
				hud.show_message("FIGHT!", UiTheme.GOLD, 0.7, 104)
			BattleEvent.KO:
				if not bool(e.data.get("training", false)):
					_slowmo = 54
					hud.show_message("K.O.!", UiTheme.DANGER, 1.4, 118)
			BattleEvent.TIMEOUT:
				hud.show_message("TIME!", UiTheme.PARCHMENT, 1.2, 104)
			BattleEvent.BATTLE_END:
				_ended = true
				_end_timer = 1.6
				var w := int(e.data.get("winner", -1))
				if w == -2:
					hud.show_message("DRAW", UiTheme.PARCHMENT, 1.4, 96)
				elif setup.mode == BattleSetup.Mode.VERSUS:
					hud.show_message("PLAYER %d WINS!" % (w + 1), UiTheme.GOLD, 1.4, 84)
				elif w == local_team:
					hud.show_message("VICTORY!", UiTheme.GOLD, 1.4, 104)
					Audio.music(&"victory_fanfare", 0.3)
				else:
					hud.show_message("DEFEAT", Color(0.75, 0.8, 0.95), 1.4, 104)
					Audio.sfx(&"defeat_jingle")


func _on_feedback(kind: StringName, data: Dictionary) -> void:
	hud.on_feedback(kind, data)


func _show_results() -> void:
	view.stop_audio()
	var result := _build_result()
	Game.apply_battle_progress(setup, result)
	results.show_results(result, setup)


func _build_result() -> Dictionary:
	var me := sim.active_fighter(local_team)
	var foe := sim.active_fighter(1 - local_team)
	return {
		"winner": sim.winner_team,
		"local_team": local_team,
		"reason": sim.end_reason,
		"mode": setup.mode,
		"story_battle_id": setup.story_battle_id,
		"duration_sec": float(sim.tick) / CombatConst.TICK_RATE,
		"record": me.record if me else {},
		"foe_record": foe.record if foe else {},
		"player_hp_ratio": me.hp_ratio() if me else 0.0,
	}


func _rematch() -> void:
	results.hide_results()
	_ended = false
	_end_timer = -1.0
	_slowmo = 0
	transport.restart()
	sim = transport.sim
	view.rebind(sim)
	hud.rebind(sim)
	touch.rebind(sim)
	Audio.music(StringName(setup.metadata.get("music", "battle_theme")), 0.5)


func _continue() -> void:
	results.hide_results()
	Game.return_from_battle(_build_result())


func _quit_battle() -> void:
	get_tree().paused = false
	view.stop_audio()
	Game.abandon_battle(setup)


func _toggle_pause() -> void:
	if results.visible:
		return
	var p := not get_tree().paused
	get_tree().paused = p
	if p:
		pause_menu.open(true)
	else:
		pause_menu.close()


func _exit_tree() -> void:
	Audio.stop_all_loops()
