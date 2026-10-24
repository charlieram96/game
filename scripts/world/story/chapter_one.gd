class_name ChapterOne
extends Node
## Chapter 1, "The Kindling": steps, objectives, NPC placement, triggers and
## cutscenes. Progress lives in PlayerProfile.flags so it saves and resumes.
##
## Steps: wake -> find_kith -> training -> duel -> ending -> complete

const SM := FighterSM.State

var world: Node  # world_scene.gd
var b: MossfordBuilder
var player: Explorer
var hud: WorldHUD
var dialogue: DialogueBox
var cam: ExplorationCamera

var hesper: NPC
var lumen: PixelSprite3D
var corin: NPC
var biscuit: PixelSprite3D
var baker: NPC
var farmer: NPC
var wild_emberlyn: PixelSprite3D
var log_spot: Interactable
var fire_spot: Interactable
var moss_spots: Array[Interactable] = []
var companion: Companion
var mossling: WildRoamer
var sigilbinder: PixelSprite3D
var spectators: Array[PixelSprite3D] = []
var busy := false
var _spook_cooldown := 0.0


func flags() -> Dictionary:
	return SaveService.profile.flags


func flag(name: String) -> bool:
	return bool(flags().get(name, false))


func set_flag(name: String, value: Variant = true) -> void:
	SaveService.profile.set_flag(name, value)


func step() -> String:
	if not flag("met_hesper"):
		return "wake"
	if not flag("befriended"):
		return "find_kith"
	if not flag("training_done"):
		return "training"
	if not flag("duel_won"):
		return "duel"
	if not flag("shrine_done"):
		return "ending"
	return "complete"


func begin(p_world: Node) -> void:
	world = p_world
	b = world.builder
	player = world.player
	hud = world.hud
	dialogue = world.dialogue
	cam = world.camera
	_spawn_static_npcs()
	_spawn_interactables()
	_setup_for_step()
	refresh_objective()


# --- Setup ---------------------------------------------------------------------------------

func _npc(p_name: String, manifest: String, pos: Vector3, dir: String = "s") -> NPC:
	var n := NPC.new()
	world.add_child(n)
	n.setup(p_name, manifest)
	n.global_position = pos
	n.set_dir(dir)
	return n


func _spawn_static_npcs() -> void:
	baker = _npc("Wynn", "res://assets/sprites/characters/villager_baker.json", b.anchors["baker"], "s")
	baker.action = func(_by: Node3D) -> void: _talk_simple(baker, "baker_after" if flag("befriended") else "baker")
	farmer = _npc("Bram", "res://assets/sprites/characters/villager_farmer.json", b.anchors["farmer"], "w")
	farmer.action = func(_by: Node3D) -> void: _talk_simple(farmer, "farmer")
	hesper = _npc("Hesper", "res://assets/sprites/characters/hesper.json", b.anchors["hesper_square"], "s")
	hesper.action = _on_hesper
	lumen = PixelSprite3D.new()
	lumen.load_manifest("res://assets/sprites/kith/lanternmoth.json")
	lumen.set_param("emission_strength", 2.0)
	lumen.set_param("emission_threshold", 0.7)
	lumen.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	world.add_child(lumen)
	lumen.play("hover", "s")
	corin = _npc("Corin", "res://assets/sprites/characters/corin.json", b.anchors["corin_arena"], "s")
	corin.action = _on_corin
	biscuit = PixelSprite3D.new()
	biscuit.load_manifest("res://assets/sprites/kith/stoneback.json")
	world.add_child(biscuit)
	EnvKit.blob_shadow(biscuit, 0.55, 0.45)
	biscuit.play("sleep", "s")
	mossling = WildRoamer.new()
	world.add_child(mossling)
	mossling.setup(b.anchors["mossling_home"], player)
	mossling.observed.connect(_on_mossling_observed)


func _spawn_interactables() -> void:
	_simple_spot(b.anchors["player_door"] + Vector3(0, 0, 0.3), "Inspect your home", "player_house", 0.9)
	_simple_spot(b.anchors["notice"] + Vector3(0, 0, 0.4), "Read the notice board", "notice_board", 1.0)
	_simple_spot(b.anchors["well"], "Inspect the well", "well", 1.2)
	_simple_spot(b.anchors["signpost"], "Read the signpost", "signpost", 0.8)
	_simple_spot(b.anchors["snare"], "Inspect the snare", "", 0.9).action = _on_snare
	var gate := _simple_spot(b.anchors["training_gate"], "Training yard", "", 1.2)
	gate.action = func(_by: Node3D) -> void:
		if step() == "training":
			_on_hesper(_by)
		else:
			_say("training_gate_early")
	var arena := _simple_spot(b.anchors["arena_gate"], "The Ringstones", "", 1.4)
	arena.action = func(_by: Node3D) -> void:
		if step() == "duel":
			_on_corin(_by)
		elif step() == "find_kith" or step() == "wake" or step() == "training":
			_say("arena_gate_early")
	var mural := _simple_spot(b.anchors["shrine_mural"] + Vector3(0, 0, 3.4), "Study the mural", "", 1.6)
	mural.action = func(_by: Node3D) -> void:
		if step() != "ending":
			_say("shrine_early")
	log_spot = _simple_spot(b.anchors["log_mouth"], "Approach the hollow log", "", 1.3)
	log_spot.action = _on_log
	fire_spot = _simple_spot(b.anchors["fire_ring"], "Fire ring", "", 1.2)
	fire_spot.action = _on_fire
	for i in 3:
		var key := "moss_%d" % (i + 1)
		var spot := _simple_spot(b.anchors[key], "Gather kindlemoss", "", 1.0)
		var s := EnvKit.foliage(spot, "kindlemoss", Vector3.ZERO, 1.2, false)
		s.set_param("emission_strength", 1.6)
		s.set_param("emission_threshold", 0.6)
		spot.set_meta("key", key)
		spot.action = _on_moss.bind(spot)
		moss_spots.append(spot)
		spot.visible = not flag(key)
		spot.enabled = not flag(key)
	var lumen_spot := Interactable.new()
	lumen_spot.prompt = "Greet Lumen"
	lumen_spot.radius = 0.9
	lumen.add_child(lumen_spot)
	lumen_spot.action = func(_by: Node3D) -> void:
		Audio.sfx(&"lanternmoth_flutter")
		_say("lanternmoth")


func _simple_spot(pos: Vector3, p_prompt: String, dialogue_id: String, radius: float) -> Interactable:
	var it := Interactable.new()
	it.prompt = p_prompt
	it.radius = radius
	world.add_child(it)
	it.global_position = pos
	if dialogue_id != "":
		it.action = func(_by: Node3D) -> void: _say(dialogue_id)
	return it


func _setup_for_step() -> void:
	var s := step()
	# Lighting by story progress.
	match s:
		"wake", "find_kith":
			world.set_time_of_day(&"morning" if not flag("befriended") else &"day")
		"training":
			world.set_time_of_day(&"day")
		"duel":
			world.set_time_of_day(&"golden")
		"ending", "complete":
			world.set_time_of_day(&"night")
	# Hesper, Corin, Biscuit placement.
	match s:
		"wake", "find_kith":
			hesper.global_position = b.anchors["hesper_square"]
		"training":
			hesper.global_position = b.anchors["hesper_training"]
			hesper.set_dir("w")
		"duel":
			hesper.global_position = b.anchors["hesper_arena"]
			hesper.set_dir("s")
		"ending", "complete":
			hesper.global_position = b.anchors["shrine_hesper"] + Vector3(0, 0, 2.5)
	var corin_pos: Vector3 = b.anchors["corin_arena"]
	if s == "wake":
		corin.visible = false
		corin.enabled = false
	elif s == "ending" or s == "complete":
		corin_pos = b.anchors["shrine_corin"] + Vector3(0, 0, 2.5)
	corin.global_position = corin_pos
	biscuit.global_position = corin_pos + Vector3(1.0, 0, -0.3)
	biscuit.visible = s != "wake"
	# The wild Emberlyn hides in its log until befriended.
	if not flag("befriended"):
		wild_emberlyn = PixelSprite3D.new()
		wild_emberlyn.load_manifest("res://assets/sprites/kith/emberlyn.json")
		wild_emberlyn.set_param("emission_strength", 1.0)
		world.add_child(wild_emberlyn)
		wild_emberlyn.global_position = b.anchors["log_mouth"] + Vector3(0.1, 0, 0.1)
		wild_emberlyn.play("cower", "s")
		wild_emberlyn.visible = flag("forest_seen")
	else:
		_spawn_companion()
	if flag("fire_lit"):
		b.light_campfire()
	if s == "duel":
		_spawn_spectators()


func _spawn_companion() -> void:
	if companion:
		return
	companion = Companion.new()
	world.add_child(companion)
	companion.setup(Registry.get_species(&"emberlyn"), player)


func _spawn_spectators() -> void:
	var sheet := SpriteSheet.load_sheet("res://assets/sprites/characters/crowd.json")
	var c := Vector3(MossfordBuilder.RINGSTONES.x, 0, MossfordBuilder.RINGSTONES.y)
	for i in 9:
		var a := float(i) / 9.0 * TAU
		var s := PixelSprite3D.new()
		s.set_sheet(sheet)
		world.add_child(s)
		s.global_position = c + Vector3(cos(a) * 5.4, 0, sin(a) * 5.4)
		var v := i % 8
		s.play("idle_v%d" % v, "s")
		spectators.append(s)


func refresh_objective() -> void:
	var text := ""
	match step():
		"wake":
			text = "Meet Warden Hesper by the great oak in the village square."
		"find_kith":
			if not flag("forest_seen"):
				text = "Find a wild kith in the [b]Glimmerwood[/b] — west, across the bridge."
			elif not flag("observed_emberlyn"):
				text = "Approach the frightened kith [b]softly[/b] (hold Shift) and observe it."
			elif int(flags().get("moss_count", 0)) < 3:
				text = "Gather dry [b]kindlemoss[/b] around the clearing (%d/3)." % int(flags().get("moss_count", 0))
			elif not flag("fire_lit"):
				text = "Light the old [b]fire ring[/b] with your Warden's Lantern."
			else:
				text = "Sit by the fire and wait for the kith to come to you."
		"training":
			text = "Meet Hesper at the [b]training grounds[/b], east of the village."
		"duel":
			text = "Face Corin at the [b]Ringstones[/b] (north-east)."
		"ending":
			text = "Follow Hesper to the [b]Dawn Shrine[/b] (north)."
		"complete":
			text = "Chapter 1 complete. Explore freely, or return to the title for Free Battle."
	hud.set_objective(text)


# --- Per frame triggers ----------------------------------------------------------------------

func _process(delta: float) -> void:
	if player == null:
		return
	# Lumen hovers around Hesper.
	var t := Time.get_ticks_msec() / 1000.0
	lumen.global_position = hesper.global_position + Vector3(cos(t * 0.9) * 0.9, 0.9 + sin(t * 1.7) * 0.15, sin(t * 0.9) * 0.5 - 0.2)
	if busy:
		return
	_spook_cooldown = maxf(0.0, _spook_cooldown - delta)
	var p := player.global_position
	var s := step()
	if s == "find_kith":
		if not flag("forest_seen") and Vector2(p.x, p.z).distance_to(MossfordBuilder.CLEARING) < 7.5:
			_forest_arrival()
		elif flag("forest_seen") and not flag("observed_emberlyn") and _spook_cooldown <= 0.0:
			var d := p.distance_to(b.anchors["log_mouth"])
			if d < 5.0 and player.is_running():
				_spook()
	elif s == "ending":
		if p.distance_to(b.anchors["shrine_front"]) < 3.5:
			_shrine_scene()


# --- Helpers ------------------------------------------------------------------------------------

func _lock(on: bool) -> void:
	busy = on
	player.controllable = not on


func _say(id: String) -> String:
	_lock(true)
	var r := await dialogue.play(id)
	_lock(false)
	return r


func _talk_simple(n: NPC, id: String) -> void:
	n.face(player.global_position)
	n.play("talk")
	await _say(id)
	n.play("idle")


func _save() -> void:
	SaveService.profile.position = player.global_position
	SaveService.profile.story_step = step()
	SaveService.save()


# --- Step: wake ---------------------------------------------------------------------------------

func _on_hesper(_by: Node3D) -> void:
	if busy:
		return
	hesper.face(player.global_position)
	match step():
		"wake":
			await _intro_scene()
		"find_kith":
			await _talk_simple(hesper, "hesper_idle_find")
		"training":
			await _training_scene()
		"duel":
			await _talk_simple(hesper, "corin_waiting")
		_:
			pass


func _intro_scene() -> void:
	_lock(true)
	hesper.play("talk")
	await dialogue.play("hesper_intro")
	hesper.play("idle")
	# Corin bursts in from the east with Biscuit lumbering behind.
	corin.visible = true
	corin.global_position = b.anchors["corin_enter"]
	biscuit.visible = true
	biscuit.global_position = b.anchors["corin_enter"] + Vector3(1.6, 0, 0.4)
	biscuit.play("move", "w")
	cam.override_point = (b.anchors["hesper_square"] + b.anchors["corin_square"]) * 0.5
	var biscuit_tw := biscuit.create_tween()
	biscuit_tw.tween_property(biscuit, "global_position", b.anchors["corin_square"] + Vector3(1.2, 0, 0.3), 3.6)
	await corin.walk_to(b.anchors["corin_square"], 4.5)
	corin.face(player.global_position)
	corin.emote("exclaim")
	await biscuit_tw.finished
	biscuit.play("idle", "w")
	Audio.sfx(&"stoneback_grunt")
	corin.play("talk")
	await dialogue.play("corin_intro")
	corin.play("cheer")
	await get_tree().create_timer(0.6).timeout
	# Corin heads for the Ringstones.
	var dest: Vector3 = b.anchors["corin_arena"]
	var mid := Vector3(6, 0, 8)
	biscuit.play("move", "e")
	var tw2 := biscuit.create_tween()
	tw2.tween_property(biscuit, "global_position", mid + Vector3(1.0, 0, 0), 1.8)
	await corin.walk_to(mid, 4.5)
	corin.global_position = dest
	biscuit.global_position = dest + Vector3(1.0, 0, -0.3)
	biscuit.play("sleep", "s")
	cam.release_focus()
	hesper.face(player.global_position)
	hesper.play("talk")
	await dialogue.play("hesper_send_off")
	hesper.play("idle")
	hud.toast("Received: Warden's Lantern", UiTheme.GOLD)
	Audio.sfx(&"item_pickup")
	set_flag("met_hesper")
	corin.enabled = true
	_lock(false)
	refresh_objective()
	_save()


# --- Step: find_kith (the befriending) --------------------------------------------------------------

func _forest_arrival() -> void:
	_lock(true)
	set_flag("forest_seen")
	SaveService.profile.journal_mark(&"emberlyn", "seen")
	wild_emberlyn.visible = true
	wild_emberlyn.play("idle", "e")
	await cam.focus_on(b.anchors["log"], 1.2)
	Audio.sfx(&"emberlyn_chirp", -4.0)
	await dialogue.play("forest_arrival")
	wild_emberlyn.play("cower", "s")
	Audio.sfx(&"emberlyn_hiss", -6.0)
	cam.release_focus()
	_lock(false)
	refresh_objective()
	_save()


func _spook() -> void:
	_spook_cooldown = 6.0
	wild_emberlyn.play("cower", "s")
	Audio.sfx(&"emberlyn_hiss", -6.0)
	NPC.show_emote(wild_emberlyn, "sweat", 1.0, 1.2)
	hud.toast("Too loud! Hold Shift to sneak.", Color(1.0, 0.7, 0.6))


func _on_log(_by: Node3D) -> void:
	if busy or step() != "find_kith" or not flag("forest_seen"):
		if step() == "find_kith" and not flag("forest_seen"):
			_forest_arrival()
		return
	if flag("observed_emberlyn"):
		await _say("observe_emberlyn")
		return
	if not player.sneaking:
		_spook()
		await _say("emberlyn_spooked")
		return
	_lock(true)
	player.force_animation("interact")
	await dialogue.play("observe_emberlyn")
	player.force_animation("")
	set_flag("observed_emberlyn")
	SaveService.profile.journal_mark(&"emberlyn", "observed")
	hud.toast("Field Journal updated: Emberlyn", Color(0.75, 0.95, 0.75))
	_lock(false)
	refresh_objective()
	_save()


func _on_moss(_by: Node3D, spot: Interactable) -> void:
	if busy:
		return
	var key: String = spot.get_meta("key")
	if flag(key):
		return
	set_flag(key)
	var count := int(flags().get("moss_count", 0)) + 1
	set_flag("moss_count", count)
	Audio.sfx(&"item_pickup")
	Vfx.burst(world, spot.global_position + Vector3(0, 0.4, 0), Color(1.0, 0.85, 0.4), 10, 1.6)
	spot.visible = false
	spot.enabled = false
	hud.toast("Gathered dry kindlemoss (%d/3)" % count, UiTheme.GOLD)
	refresh_objective()


func _on_fire(_by: Node3D) -> void:
	if busy:
		return
	if flag("befriended"):
		return
	var count := int(flags().get("moss_count", 0))
	if not flag("fire_lit"):
		if count < 3:
			await _say("fire_ring_empty")
			return
		_lock(true)
		player.force_animation("interact")
		await dialogue.play("fire_lit")
		player.force_animation("")
		b.light_campfire()
		Audio.sfx(&"fire_light")
		Audio.loop_start(&"campfire", &"fire_crackle_loop", -10.0)
		set_flag("fire_lit")
		wild_emberlyn.play("idle", "e")
		NPC.show_emote(wild_emberlyn, "question", 1.4, 1.2)
		_lock(false)
		refresh_objective()
		_save()
		return
	await _sit_scene()


func _sit_scene() -> void:
	_lock(true)
	player.global_position = b.anchors["sit_spot"]
	player.face_towards(b.anchors["fire_ring"])
	player.force_animation("sit")
	await dialogue.play("sit_down")
	hud.show_trust(true, 0.0)
	# The wild Emberlyn creeps closer in stages; moving breaks the spell.
	var start: Vector3 = wild_emberlyn.global_position
	var goal: Vector3 = b.anchors["fire_ring"] + Vector3(-0.9, 0, 0.5)
	var ok := true
	var stages := 5
	for i in stages:
		await get_tree().create_timer(0.9).timeout
		if Input.get_vector(&"move_left", &"move_right", &"move_up", &"move_down", 0.3) != Vector2.ZERO or hud.touch.move_vector() != Vector2.ZERO:
			ok = false
			break
		var p := start.lerp(goal, float(i + 1) / stages)
		wild_emberlyn.play("move", "e" if goal.x > start.x else "w")
		var tw := wild_emberlyn.create_tween()
		tw.tween_property(wild_emberlyn, "global_position", p, 0.5)
		await tw.finished
		wild_emberlyn.play("idle", "e")
		hud.show_trust(true, float(i + 1) / stages * 0.7)
		Audio.sfx(&"trust_up", -8.0)
	if not ok:
		hud.show_trust(false)
		player.force_animation("")
		wild_emberlyn.global_position = start
		wild_emberlyn.play("cower", "s")
		await dialogue.play("sit_moved")
		_lock(false)
		return
	wild_emberlyn.play("curl", "s")
	await dialogue.play("emberlyn_close")
	var ring := world.timing_ring as TimingRing
	var success := false
	for attempt in 3:
		success = await ring.run()
		if success:
			break
		await dialogue.play("offer_fail")
	if not success:
		# Never hard-fail a story beat: a third miss still works, gently.
		success = true
	hud.show_trust(true, 1.0)
	player.force_animation("")
	Vfx.spawn(world, &"trust_motes", wild_emberlyn.global_position, Vector2.RIGHT, Color.WHITE, 1.4)
	NPC.show_emote(wild_emberlyn, "heart", 1.8, 1.2)
	wild_emberlyn.play("happy", "s")
	Audio.sfx(&"befriend_success")
	Audio.sfx(&"emberlyn_chirp", -2.0)
	await dialogue.play("befriended")
	hud.show_trust(false)
	var nickname: String = await world.ask_name("Name your Emberlyn?", "Emberlyn")
	var creature := Registry.make_creature(&"emberlyn", 5, "" if nickname == "Emberlyn" else nickname)
	creature.bond = 30
	creature.met_location = "Glimmerwood"
	creature.met_story_step = "kindling"
	SaveService.profile.party.insert(0, creature)
	SaveService.profile.journal_mark(&"emberlyn", "befriended")
	Events.creature_befriended.emit(creature)
	set_flag("befriended")
	hud.toast("%s joined you!" % (nickname if nickname != "" else "Emberlyn"), UiTheme.GOLD)
	var pos := wild_emberlyn.global_position
	wild_emberlyn.queue_free()
	wild_emberlyn = null
	_spawn_companion()
	companion.global_position = pos
	Audio.loop_stop(&"campfire")
	world.set_time_of_day(&"day", 3.0)
	_lock(false)
	refresh_objective()
	_save()


func _on_snare(_by: Node3D) -> void:
	await _say("snare")
	set_flag("snare_seen")


func _on_mossling_observed() -> void:
	if flag("mossling_observed"):
		return
	set_flag("mossling_observed")
	SaveService.profile.journal_mark(&"mossling", "observed")
	await _say("mossling_observed")


# --- Step: training --------------------------------------------------------------------------------

func _training_scene() -> void:
	_lock(true)
	hesper.play("talk")
	await dialogue.play("hesper_training_intro")
	if flag("snare_seen"):
		await dialogue.play("hesper_training_snare")
	hesper.play("idle")
	_lock(false)
	_save()
	world.start_battle(Game.training_setup())


func on_battle_result(result: Dictionary) -> void:
	if result.is_empty() or result.get("abandoned", false):
		return
	var id: StringName = result.get("story_battle_id", &"")
	var won := int(result.get("winner", -1)) == int(result.get("local_team", 0))
	if id == &"training" and won and not flag("training_done"):
		set_flag("training_done")
		await get_tree().create_timer(0.5).timeout
		_lock(true)
		hesper.face(player.global_position)
		hesper.play("talk")
		await dialogue.play("hesper_after_training")
		hesper.play("idle")
		world.set_time_of_day(&"golden", 4.0)
		_lock(false)
		refresh_objective()
		_save()
		# Hesper heads to the Ringstones.
		await hesper.walk_to(b.anchors["training_gate"] + Vector3(-1.5, 0, 0), 3.0)
		hesper.global_position = b.anchors["hesper_arena"]
		_spawn_spectators()
	elif id == &"kindling_duel":
		if won:
			await _duel_won_scene()
		else:
			await _duel_lost_scene()


# --- Step: duel ------------------------------------------------------------------------------------

func _on_corin(_by: Node3D) -> void:
	if busy:
		return
	corin.face(player.global_position)
	match step():
		"wake", "find_kith", "training":
			await _say("arena_gate_early")
		"duel":
			_lock(true)
			corin.play("talk")
			await dialogue.play("corin_duel")
			corin.play("idle")
			_lock(false)
			_save()
			world.start_battle(Game.story_duel_setup(false))
		_:
			await _talk_simple(corin, "corin_waiting")


func _duel_won_scene() -> void:
	set_flag("duel_won")
	_lock(true)
	await get_tree().create_timer(0.4).timeout
	for s in spectators:
		var v := spectators.find(s) % 8
		s.play("cheer_v%d" % v, "s")
	Audio.sfx(&"crowd_cheer", -6.0)
	corin.face(player.global_position)
	corin.play("slump")
	await dialogue.play("duel_won")
	corin.play("idle")
	player.force_animation("cheer")
	hud.toast("You are now a Warden of Mossford!", UiTheme.GOLD)
	Audio.sfx(&"quest_update")
	await get_tree().create_timer(1.6).timeout
	player.force_animation("")
	# The tremor
	cam.shake(0.9)
	Audio.sfx(&"tremor")
	for s in spectators:
		s.play("idle_v%d" % (spectators.find(s) % 8), "s")
	await get_tree().create_timer(1.0).timeout
	await dialogue.play("tremor")
	world.set_time_of_day(&"dusk", 3.0)
	_lock(false)
	refresh_objective()
	_save()
	await get_tree().create_timer(3.2).timeout
	world.set_time_of_day(&"night", 4.0)
	hesper.global_position = b.anchors["shrine_hesper"] + Vector3(0, 0, 2.5)
	corin.global_position = b.anchors["shrine_corin"] + Vector3(0, 0, 2.5)
	biscuit.global_position = b.anchors["shrine_corin"] + Vector3(1.0, 0, 2.6)
	biscuit.play("idle", "n")


func _duel_lost_scene() -> void:
	_lock(true)
	await get_tree().create_timer(0.4).timeout
	corin.play("cheer")
	var choice := await dialogue.play("duel_lost")
	corin.play("idle")
	_lock(false)
	match choice:
		"retry":
			world.start_battle(Game.story_duel_setup(false))
		"relaxed":
			world.start_battle(Game.story_duel_setup(true))


# --- Step: ending ------------------------------------------------------------------------------------

func _shrine_scene() -> void:
	_lock(true)
	Audio.music(&"shrine_theme", 2.0)
	player.global_position = b.anchors["shrine_player"]
	player.face_towards(b.anchors["shrine_mural"])
	if companion:
		companion.set_scripted(true)
		companion.global_position = b.anchors["shrine_player"] + Vector3(-0.9, 0, 0.4)
		companion.play("idle", "n")
	hesper.global_position = b.anchors["shrine_hesper"]
	hesper.set_dir("n")
	corin.global_position = b.anchors["shrine_corin"]
	corin.set_dir("n")
	biscuit.global_position = b.anchors["shrine_corin"] + Vector3(1.0, 0, 0.3)
	await cam.focus_on(b.anchors["shrine_mural"] + Vector3(0, 0, 2.0), 1.4)
	Audio.sfx(&"mural_awaken")
	var tw := create_tween()
	tw.tween_method(b.set_mural_glow, 0.0, 1.0, 2.4)
	await tw.finished
	await dialogue.play("shrine_arrival")
	if companion:
		companion.play("focus", "n")
		NPC.show_emote(companion, "exclaim", 1.6, 1.2)
		Vfx.spawn(world, &"trust_motes", companion.global_position, Vector2.RIGHT, Color(1, 0.8, 0.5), 1.2)
	Audio.sfx(&"emberlyn_chirp")
	await dialogue.play("shrine_ember")
	# The Sigilbinder on the broken wall.
	sigilbinder = PixelSprite3D.new()
	sigilbinder.load_manifest("res://assets/sprites/characters/sigilbinder.json")
	sigilbinder.set_param("emission_strength", 2.0)
	sigilbinder.set_param("emission_threshold", 0.6)
	world.add_child(sigilbinder)
	sigilbinder.global_position = b.anchors["sigil_spot"]
	sigilbinder.play("idle", "s")
	Vfx.spawn(world, &"sigil_glow", b.anchors["sigil_spot"] + Vector3(0, 0.5, 0.2))
	Audio.sfx(&"guard_break", -8.0)
	corin.emote("exclaim")
	hesper.emote("exclaim")
	await cam.focus_on(b.anchors["sigil_spot"] + Vector3(-1.5, -2.6, 2.0), 0.8)
	var lines: Array = DialogueBox.data()["sigilbinder_seen"]
	await dialogue.play_lines([lines[0]])
	sigilbinder.play("run", "e")
	var run := sigilbinder.create_tween()
	run.tween_property(sigilbinder, "global_position", b.anchors["sigil_spot"] + Vector3(7.0, 0, 0), 1.0)
	await run.finished
	sigilbinder.queue_free()
	cam.release_focus()
	await dialogue.play_lines(lines.slice(1))
	set_flag("shrine_done")
	SaveService.profile.story_step = "complete"
	_save()
	await world.chapter_card()
	_lock(false)
	Game.goto_scene(Game.TITLE_SCENE, 1.0)
