extends WBTestCase
## End-to-end: the real battle scene with keyboard input flowing through
## LocalInputSource -> transport -> simulation, plus rematch through the UI path.


func test_keyboard_input_drives_the_player_creature() -> void:
	var setup := Game.quick_battle_setup(&"emberlyn", &"stoneback", &"easy")
	setup.countdown = false
	Game._pending_battle = setup
	var scene: Node = load("res://scenes/combat/battle.tscn").instantiate()
	Engine.get_main_loop().root.add_child(scene)
	var tree := Engine.get_main_loop() as SceneTree
	await tree.process_frame
	var sim: BattleSim = scene.sim
	var me := sim.active_fighter(0)
	var start := me.pos
	var stamina := me.stamina
	# Hold W to charge a dash north, release to go.
	Input.action_press(&"move_up")
	for i in 20:
		await tree.physics_frame
	assert_eq(me.pos, start, "holding a direction doesn't walk")
	Input.action_release(&"move_up")
	for i in 40:
		await tree.physics_frame
	assert_lt(me.pos.y, start.y - 1.0, "dashed north on release")
	assert_lt(me.stamina, stamina, "the dash spent stamina")
	scene._rematch()
	assert_eq(scene.sim.tick, 0, "rematch reset the simulation")
	assert_near(scene.sim.active_fighter(0).hp, scene.sim.active_fighter(0).max_hp(), 0.001, "full HP after rematch")
	scene.queue_free()
	await tree.process_frame
