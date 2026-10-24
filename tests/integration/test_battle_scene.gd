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
	Input.action_press(&"move_up")
	for i in 30:
		await tree.physics_frame
	Input.action_release(&"move_up")
	assert_lt(me.pos.y, start.y - 1.0, "walked north with W")
	var stamina := me.stamina
	Input.action_press(&"dash")
	await tree.physics_frame
	await tree.physics_frame
	Input.action_release(&"dash")
	assert_lt(me.stamina, stamina, "right-click dash spent stamina")
	for i in 30:
		await tree.physics_frame
	scene._rematch()
	assert_eq(scene.sim.tick, 0, "rematch reset the simulation")
	assert_near(scene.sim.active_fighter(0).hp, scene.sim.active_fighter(0).max_hp(), 0.001, "full HP after rematch")
	scene.queue_free()
	await tree.process_frame
