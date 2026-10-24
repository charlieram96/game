extends WBTestCase
## Plays Chapter 1 end to end in the real world scene (dialogue auto-
## advances, battles are simulated as won) and checks that every step's
## flags, party, journal and objective progress — so no cutscene or await
## can silently soft-lock the story.

## Real-time budget per story beat. Cutscene timers and tweens run at
## TIME_SCALE so the whole chapter plays in seconds.
const STEP_TIMEOUT_MS := 30000
const TIME_SCALE := 6.0


func _wait_idle(story: ChapterOne, tree: SceneTree) -> bool:
	var deadline := Time.get_ticks_msec() + STEP_TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		await tree.process_frame
		if not story.busy:
			return true
	return false


func test_chapter_one_can_be_completed() -> void:
	var tree := Engine.get_main_loop() as SceneTree
	var old_profile := SaveService.profile
	var old_path := SaveService.path
	SaveService.path = "user://test_story_save.json"
	SaveService.new_profile("Tester")
	Game.autoplay = true
	Game.autoplay_requests.clear()
	var old_scale := Engine.time_scale
	Engine.time_scale = TIME_SCALE
	Game.last_result = {}
	var world: Node = load("res://scenes/world/mossford.tscn").instantiate()
	tree.root.add_child(world)
	await tree.process_frame
	var story: ChapterOne = world.story
	var player: Explorer = world.player
	assert_eq(story.step(), "wake", "starts at wake")
	# 1. Meet Hesper (intro + Corin's arrival)
	story._on_hesper(player)
	assert_true(await _wait_idle(story, tree), "intro finished")
	assert_true(story.flag("met_hesper"), "met Hesper")
	assert_eq(story.step(), "find_kith", "now find a kith")
	# 2. Enter the clearing -> arrival cutscene
	player.global_position = story.b.anchors["clearing_entry"] + Vector3(-2.0, 0, -1.0)
	for i in 30:
		await tree.process_frame
	assert_true(await _wait_idle(story, tree), "arrival finished")
	assert_true(story.flag("forest_seen"), "saw the Emberlyn")
	# 3. Observe while sneaking
	Input.action_press(&"sneak")
	for i in 3:
		await tree.physics_frame
	story._on_log(player)
	assert_true(await _wait_idle(story, tree), "observe finished")
	Input.action_release(&"sneak")
	assert_true(story.flag("observed_emberlyn"), "observed")
	# 4. Gather kindlemoss, light the fire, sit, befriend
	for spot in story.moss_spots:
		story._on_moss(player, spot)
	assert_eq(int(story.flags().get("moss_count", 0)), 3, "gathered three bundles")
	story._on_fire(player)
	assert_true(await _wait_idle(story, tree), "fire lit")
	assert_true(story.flag("fire_lit"), "fire is lit")
	story._on_fire(player)
	assert_true(await _wait_idle(story, tree), "befriending finished")
	assert_true(story.flag("befriended"), "befriended")
	assert_eq(SaveService.profile.party.size(), 1, "Emberlyn joined the party")
	assert_true(bool(SaveService.profile.journal.get("emberlyn", {}).get("befriended", false)), "journal updated")
	assert_true(story.companion != null, "companion follows")
	# 5. Training: Hesper starts the training battle
	story._on_hesper(player)
	assert_true(await _wait_idle(story, tree), "training intro finished")
	assert_true(Game.autoplay_requests.size() >= 1 and Game.autoplay_requests[-1] is BattleSetup, "training battle requested")
	story.on_battle_result({"story_battle_id": &"training", "winner": 0, "local_team": 0})
	for i in 5:
		await tree.process_frame
	assert_true(await _wait_idle(story, tree), "after-training scene finished")
	assert_true(story.flag("training_done"), "training done")
	assert_eq(story.step(), "duel", "now the duel")
	# 6. The duel: lose once (retry offered), then win
	story._on_corin(player)
	assert_true(await _wait_idle(story, tree), "duel intro finished")
	var duel: BattleSetup = Game.autoplay_requests[-1]
	assert_eq(duel.story_battle_id, &"kindling_duel", "duel requested")
	story.on_battle_result({"story_battle_id": &"kindling_duel", "winner": 1, "local_team": 0})
	assert_true(await _wait_idle(story, tree), "loss scene finished")
	assert_false(story.flag("duel_won"), "a loss doesn't advance")
	story.on_battle_result({"story_battle_id": &"kindling_duel", "winner": 0, "local_team": 0})
	assert_true(await _wait_idle(story, tree), "victory scene finished")
	assert_true(story.flag("duel_won"), "duel won")
	assert_eq(story.step(), "ending", "now the ending")
	# 7. Walk to the shrine -> ending
	player.global_position = story.b.anchors["shrine_front"] + Vector3(0, 0, 1.0)
	for i in 30:
		await tree.process_frame
	assert_true(await _wait_idle(story, tree), "shrine scene finished")
	assert_true(story.flag("shrine_done"), "chapter complete")
	assert_true(Game.autoplay_requests.has(Game.TITLE_SCENE), "returns to the title")
	# Saved progress reloads.
	var reloaded := SaveService.read_profile(SaveService.path)
	assert_true(reloaded != null and bool(reloaded.flag("shrine_done")), "completion was saved")
	# Cleanup
	Engine.time_scale = old_scale
	Game.autoplay = false
	Game.autoplay_requests.clear()
	world.queue_free()
	await tree.process_frame
	if FileAccess.file_exists(SaveService.path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(SaveService.path))
	SaveService.path = old_path
	SaveService.profile = old_profile
