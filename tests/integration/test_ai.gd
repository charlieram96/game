extends WBTestCase
## Spec test 16: AI combat behaviour.

const H := preload("res://tests/sim_helpers.gd")
const SM := FighterSM.State


func _ai_battle(a_path: String, b_path: String, a_ai: InputSource, b_ai: InputSource, max_ticks: int = 7200, on_tick: Callable = Callable()) -> BattleSim:
	var setup := BattleSetup.new()
	setup.ruleset = BattleRuleset.make(BattleRuleset.Kind.RANKED)
	setup.countdown = false
	setup.arena = ArenaDefinition.ringstones()
	var a := H.creature(a_path)
	var b := H.creature(b_path)
	setup.add_creature(0, a["creature"], a["species"])
	setup.add_creature(1, b["creature"], b["species"])
	var transport := LocalBattleTransport.new()
	transport.start(setup)
	transport.set_input_source(0, a_ai)
	transport.set_input_source(1, b_ai)
	for i in max_ticks:
		transport.step()
		if on_tick.is_valid():
			on_tick.call(transport.sim)
		if transport.sim.is_finished():
			break
	return transport.sim


static func _diagonal(v: Vector2) -> bool:
	return minf(absf(v.x), absf(v.y)) > 0.001


func test_ai_beats_a_passive_opponent() -> void:
	for path in [H.EMBERLYN, H.STONEBACK]:
		var sim := _ai_battle(path, H.STONEBACK, CombatAI.new(AIProfile.preset(&"normal"), 3), InputSource.new())
		assert_true(sim.is_finished(), "%s finished" % path.get_file())
		assert_eq(sim.winner_team, 0, "%s AI won vs a passive dummy" % path.get_file())
		assert_eq(sim.end_reason, &"ko", "%s won by KO, not timeout" % path.get_file())


func test_ai_vs_ai_matches_complete() -> void:
	for pair in [[H.EMBERLYN, H.STONEBACK], [H.STONEBACK, H.EMBERLYN], [H.EMBERLYN, H.EMBERLYN]]:
		var sim := _ai_battle(pair[0], pair[1], CombatAI.new(AIProfile.preset(&"normal"), 11), CombatAI.new(AIProfile.preset(&"normal"), 29))
		assert_true(sim.is_finished(), "%s vs %s finished" % [pair[0].get_file(), pair[1].get_file()])
		var dealt := 0.0
		for f in sim.fighters:
			dealt += float(f.record["damage_dealt"])
		assert_gt(dealt, 50.0, "both sides fought")


## Nothing travels diagonally: dashes, lunges, knockback, body pushes,
## projectiles and every attack's direction follow the board's rows and
## columns.
func test_nothing_moves_diagonally() -> void:
	var bad: Array[String] = []
	var last := {}
	var check := func(sim: BattleSim) -> void:
		for f in sim.fighters:
			var step: Vector2 = f.pos - (last.get(f.id, f.pos) as Vector2)
			last[f.id] = f.pos
			if _diagonal(step):
				bad.append("tick %d: fighter %d moved %s (%s)" % [sim.tick, f.id, step, FighterSM.State.keys()[f.state]])
			if _diagonal(f.facing) or (FighterSM.is_attacking(f.state) and _diagonal(f.ability_dir)):
				bad.append("tick %d: fighter %d faces %s / aims %s" % [sim.tick, f.id, f.facing, f.ability_dir])
		for v in sim.volumes:
			if _diagonal(v.dir) or _diagonal(v.velocity):
				bad.append("tick %d: volume %s dir %s vel %s" % [sim.tick, v.ability.id if v.ability else &"?", v.dir, v.velocity])
	for pair in [[H.EMBERLYN, H.STONEBACK], [H.STONEBACK, H.EMBERLYN]]:
		last.clear()
		var sim := _ai_battle(pair[0], pair[1], CombatAI.new(AIProfile.preset(&"hard"), 17), CombatAI.new(AIProfile.preset(&"normal"), 41), 7200, check)
		assert_true(sim.is_finished(), "%s vs %s finished" % [pair[0].get_file(), pair[1].get_file()])
	assert_eq(bad.size(), 0, "no diagonal motion: %s" % [bad.slice(0, 6)])


func test_ai_focuses_when_out_of_stamina() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var me := H.place(sim, 1, Vector2(8, 0))
	H.place(sim, 0, Vector2(-8, 0))
	me.stamina = 0.0
	var ai := CombatAI.new(AIProfile.preset(&"normal"), 5)
	var focused := false
	for i in 120:
		sim.step({1: ai.get_command(sim, 1)})
		if me.state == SM.FOCUSING:
			focused = true
			break
	assert_true(focused, "AI recovered stamina with Focus")


func test_ai_uses_its_whole_kit() -> void:
	var used := {}
	for seed_value in [1, 2, 3]:
		var sim := _ai_battle(H.STONEBACK, H.EMBERLYN, CombatAI.new(AIProfile.preset(&"hard"), seed_value), CombatAI.new(AIProfile.preset(&"normal"), seed_value + 10))
		var f := sim.active_fighter(0)
		for k in (f.record["ability_usage"] as Dictionary).keys():
			used[k] = true
	assert_ge(float(used.size()), 4.0, "uses most of its abilities: %s" % [used.keys()])


func test_hard_ai_dodges_some_projectiles() -> void:
	var dodged := 0
	var shots := 12
	for i in shots:
		var sim := H.make_sim(H.STONEBACK, H.EMBERLYN)
		H.place(sim, 0, Vector2(-5, 0), Vector2.RIGHT)
		var target := H.place(sim, 1, Vector2(3, 0), Vector2.LEFT)
		var ai := CombatAI.new(AIProfile.preset(&"hard"), 100 + i)
		var hp := target.hp
		sim.step({0: H.cmd(InputCommand.ABILITY_1, InputCommand.ABILITY_1, Vector2.RIGHT, 8.0), 1: ai.get_command(sim, 1)})
		for t in 80:
			sim.step({1: ai.get_command(sim, 1)})
		if target.hp >= hp - 0.01:
			dodged += 1
	assert_gt(float(dodged), 0.0, "dodged at least one boulder (%d/%d)" % [dodged, shots])
