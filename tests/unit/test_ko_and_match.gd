extends WBTestCase
## Spec tests 15 and 19: knockouts, match end, timeout, restart/rematch,
## determinism, team switching rules.

const H := preload("res://tests/sim_helpers.gd")
const SM := FighterSM.State


func test_knockout_ends_battle_with_winner() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	H.place(sim, 0, Vector2(0, 0), Vector2.RIGHT)
	var s := H.place(sim, 1, Vector2(1.2, 0))
	s.hp = 1.0
	var events: Array[BattleEvent] = []
	sim.step({0: H.cmd(-1, InputCommand.ATTACK, InputCommand.ATTACK, Vector2.RIGHT, 1.2)})
	events.append_array(sim.events)
	for i in 200:
		sim.step({})
		events.append_array(sim.events)
		if sim.is_finished():
			break
	assert_eq(s.state, SM.KNOCKED_OUT, "knocked out")
	assert_eq(H.events_of(events, BattleEvent.KO).size(), 1, "KO event")
	assert_true(sim.is_finished(), "battle finished")
	assert_eq(sim.winner_team, 0, "team 0 wins")
	assert_eq(sim.end_reason, &"ko", "by KO")


func test_knocked_out_creature_ignores_input() -> void:
	var sim := H.make_sim()
	var f := H.place(sim, 0, Vector2(0, 0))
	sim.knock_out(f, null)
	var pos := f.pos
	H.run(sim, 30, H.cmd(0, InputCommand.DASH | InputCommand.ATTACK, InputCommand.DASH | InputCommand.ATTACK))
	assert_eq(f.state, SM.KNOCKED_OUT, "stays KO")
	assert_true(f.pos.distance_to(pos) < 1.0, "doesn't walk or dash")


func test_timeout_decides_by_health_ratio() -> void:
	var setup := BattleSetup.new()
	setup.ruleset = BattleRuleset.make(BattleRuleset.Kind.RANKED)
	setup.ruleset.match_time_sec = 2
	setup.countdown = false
	var a := H.creature(H.EMBERLYN)
	var b := H.creature(H.STONEBACK)
	setup.add_creature(0, a["creature"], a["species"])
	setup.add_creature(1, b["creature"], b["species"])
	var sim := BattleSim.new(setup)
	sim.active_fighter(1).hp *= 0.5
	H.run(sim, 130, H.idle())
	assert_true(sim.is_finished(), "timed out")
	assert_eq(sim.end_reason, &"timeout", "reason")
	assert_eq(sim.winner_team, 0, "healthier side wins")


func test_countdown_blocks_actions() -> void:
	var setup := BattleSetup.new()
	setup.countdown = true
	var a := H.creature(H.EMBERLYN)
	var b := H.creature(H.STONEBACK)
	setup.add_creature(0, a["creature"], a["species"])
	setup.add_creature(1, b["creature"], b["species"])
	var sim := BattleSim.new(setup)
	var f := sim.active_fighter(0)
	var pos := f.pos
	H.run(sim, 60, H.cmd(0, InputCommand.DASH, InputCommand.DASH))
	assert_eq(f.pos, pos, "frozen during countdown")
	var events := H.run(sim, CombatConst.COUNTDOWN_TICKS, H.idle())
	assert_eq(H.events_of(events, BattleEvent.FIGHT_START).size(), 1, "fight starts")


func test_reset_restores_starting_state_for_rematch() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK, false)
	var f0 := sim.active_fighter(0)
	var start0 := f0.pos
	H.run(sim, 60, H.cmd(0, InputCommand.DASH, InputCommand.DASH))
	sim.active_fighter(1).hp = 3.0
	sim.knock_out(sim.active_fighter(1), f0)
	H.run(sim, 200, H.idle())
	assert_true(sim.is_finished(), "first match over")
	sim.reset()
	var g0 := sim.active_fighter(0)
	var g1 := sim.active_fighter(1)
	assert_eq(sim.tick, 0, "tick reset")
	assert_false(sim.is_finished(), "not finished")
	assert_eq(sim.winner_team, -1, "no winner")
	assert_near(g1.hp, g1.max_hp(), 0.0001, "full HP")
	assert_near(g0.stamina, g0.max_stamina(), 0.0001, "full stamina")
	assert_eq(g0.pos, start0, "back at spawn")
	assert_eq(g1.state, SM.IDLE, "not KO")
	assert_true(sim.volumes.is_empty(), "no stray hitboxes")


func test_same_inputs_same_result() -> void:
	var hashes: Array[int] = []
	for run in 2:
		var sim := H.make_sim(H.EMBERLYN, H.STONEBACK, false)
		var rng := RandomNumberGenerator.new()
		rng.seed = 99
		for i in 600:
			var c0 := H.cmd(rng.randi_range(-1, 7), 0, 0, Vector2.from_angle(rng.randf() * TAU), rng.randf_range(1, 8))
			var c1 := H.cmd(rng.randi_range(-1, 7), 0, 0, Vector2.from_angle(rng.randf() * TAU), rng.randf_range(1, 8))
			var bits := [InputCommand.ATTACK, InputCommand.DASH, InputCommand.ABILITY_1, InputCommand.ABILITY_2, InputCommand.ABILITY_3, InputCommand.ABILITY_4, InputCommand.FOCUS, InputCommand.GUARD, 0, 0]
			var b0: int = bits[rng.randi() % bits.size()]
			var b1: int = bits[rng.randi() % bits.size()]
			c0.held = b0
			c0.pressed = b0
			c1.held = b1
			c1.pressed = b1
			sim.step({0: c0, 1: c1})
		hashes.append(sim.state_hash())
	assert_eq(hashes[0], hashes[1], "deterministic replay")


func test_team_switching_rules() -> void:
	var setup := BattleSetup.new()
	setup.ruleset = BattleRuleset.make(BattleRuleset.Kind.RANKED)
	setup.countdown = false
	setup.time_limit = false
	setup.allow_switching = true
	var e := H.creature(H.EMBERLYN)
	var s := H.creature(H.STONEBACK)
	var foe := H.creature(H.STONEBACK)
	setup.add_creature(0, e["creature"], e["species"])
	setup.add_creature(0, s["creature"], s["species"])
	setup.add_creature(1, foe["creature"], foe["species"])
	var sim := BattleSim.new(setup)
	var first := sim.active_fighter(0)
	first.cooldowns[&"ember_bolt"] = 100
	# Can't switch while stunned.
	StunRules.apply(sim, first, 20, &"hit")
	H.run(sim, 2, H.cmd(-1, InputCommand.SWITCH_2, InputCommand.SWITCH_2))
	assert_eq(sim.active_fighter(0), first, "no switch while stunned")
	H.run(sim, 30, H.idle())
	var events := H.tap(sim, 0, InputCommand.SWITCH_2)
	assert_eq(first.state, SM.SWITCHING, "switch animation (commitment)")
	events.append_array(H.run(sim, CombatConst.SWITCH_TICKS + 2, H.idle()))
	var second := sim.active_fighter(0)
	assert_ne(second, first, "switched in")
	assert_eq(second.species.id, &"stoneback", "the selected slot")
	assert_gt(float(second.switch_cooldown), 0.0, "switch cooldown")
	assert_eq(H.events_of(events, BattleEvent.SWITCH_IN).size(), 1, "event")
	assert_lt(float(first.cooldown_of(first.stats.abilities[0])), 100.0, "benched cooldowns keep ticking")
	H.tap(sim, 0, InputCommand.SWITCH_1)
	assert_ne(second.state, SM.SWITCHING, "switch on cooldown")
