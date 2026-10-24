extends WBTestCase
## Drag-dash rules: dashes are the only movement. They travel whole cells
## along one board lane and land on cell centres; stamina pays base +
## per-cell; walls and stones cut them short; passing through a foe rams it;
## the plan the preview draws is exactly what happens.

const H := preload("res://tests/sim_helpers.gd")
const SM := FighterSM.State


func _open(a: String = H.EMBERLYN, b: String = H.STONEBACK) -> BattleSim:
	var sim := H.make_sim(a, b)
	H.place(sim, 1, Vector2(11, 8))
	return sim


func test_dashes_travel_whole_cells_along_one_lane() -> void:
	for dir in 4:
		for cells in range(1, 6):
			var sim := _open()
			var f := H.place(sim, 0, Vector2(0, 0))
			H.dash_and_settle(sim, 0, dir, cells)
			var expected := Cardinal.from_index(dir) * cells
			assert_near(f.pos.x, expected.x, 0.0001, "dir %d x %d cells: x" % [dir, cells])
			assert_near(f.pos.y, expected.y, 0.0001, "dir %d x %d cells: y" % [dir, cells])


func test_windup_gathers_onto_the_cell_centre_first() -> void:
	var sim := _open()
	var f := H.place(sim, 0, Vector2(0.3, -0.25))
	H.dash(sim, 0, H.E, 2)
	assert_eq(f.state, SM.DASH_START, "winding up")
	var ys: Array[float] = []
	while f.state != SM.DASH_RECOVERY:
		sim.step({})
		if f.state == SM.DASH_ACTIVE:
			ys.append(f.pos.y)
	for y in ys:
		assert_near(y, 0.0, 0.0001, "travels exactly along the lane")
	assert_near(f.pos.x, 2.0, 0.0001, "lands two cells east of its cell centre")


func test_cost_scales_with_cells_and_empty_stamina_blocks() -> void:
	var sim := _open()
	var f := H.place(sim, 0, Vector2(0, 0))
	var prof := f.stats.dash
	var before := f.stamina
	H.dash_and_settle(sim, 0, H.E, 3)
	assert_near(f.stamina, before - (prof.stamina_base + prof.stamina_per_cell * 3), 0.0001, "base + 3 cells")
	f.stamina = prof.cost_for(2) - 0.5
	var events := H.dash(sim, 0, H.W, 2)
	assert_ne(f.state, SM.DASH_START, "can't afford two cells")
	assert_eq(H.events_of(events, BattleEvent.DASH_NO_STAMINA).size(), 1, "feedback event")
	H.dash_and_settle(sim, 0, H.W, 1)
	assert_near(f.pos.x, 2.0, 0.0001, "one cell is still affordable")


func test_untrusted_dash_requests_are_clamped_or_ignored() -> void:
	var sim := _open()
	var f := H.place(sim, 0, Vector2(0, 0))
	H.dash_and_settle(sim, 0, H.E, 60)
	assert_near(f.pos.x, float(f.stats.dash.max_cells), 0.0001, "clamped to the longest dash")
	var bad := InputCommand.new()
	bad.dash_dir = 7
	bad.dash_cells = 2
	bad.held = InputCommand.DASH
	bad.pressed = InputCommand.DASH
	sim.step({0: bad})
	assert_ne(f.state, SM.DASH_START, "invalid direction ignored")
	var none := H.dash_cmd(H.E, 0)
	sim.step({0: none})
	assert_ne(f.state, SM.DASH_START, "zero cells ignored")


func test_walls_and_stones_cut_the_dash_short_and_cost_less() -> void:
	var sim := _open()
	var east := int(sim.geometry.bounds.end.x - 0.5)  # last column's centre
	var f := H.place(sim, 0, Vector2(east - 2, 0))
	var before := f.stamina
	H.dash_and_settle(sim, 0, H.E, 5)
	assert_near(f.pos.x, float(east), 0.0001, "stops on the last cell")
	assert_near(before - f.stamina, f.stats.dash.cost_for(2), 0.0001, "pays for the cells travelled")
	var sim2 := _open()
	sim2.geometry.add_circle(Vector2(3, 0), 0.45)
	var g := H.place(sim2, 0, Vector2(0, 0))
	H.dash_and_settle(sim2, 0, H.E, 5)
	assert_near(g.pos.x, 2.0, 0.0001, "stops in front of the stone")


func test_fully_blocked_dash_costs_nothing() -> void:
	var sim := _open()
	var east := sim.geometry.bounds.end.x - 0.5
	var f := H.place(sim, 0, Vector2(east, 0))
	var before := f.stamina
	var events := H.dash(sim, 0, H.E, 2)
	assert_eq(H.events_of(events, BattleEvent.DASH_BLOCKED).size(), 1, "blocked feedback")
	assert_eq(f.stamina, before, "no stamina spent")
	assert_ne(f.state, SM.DASH_START, "didn't start")


func test_ram_damages_dazes_and_then_protects() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var e := H.place(sim, 0, Vector2(-2, 0))
	var s := H.place(sim, 1, Vector2(0, 0), Vector2.LEFT)
	var hp := s.hp
	var events := H.dash_and_settle(sim, 0, H.E, 3)
	var through := H.events_of(events, BattleEvent.DASH_THROUGH)
	assert_eq(through.size(), 1, "one ram")
	assert_true(through[0].data["stunned"], "dazed")
	assert_gt(float(through[0].data["damage"]), 0.0, "ram damage")
	assert_lt(s.hp, hp, "hp went down")
	var hits := H.events_of(events, BattleEvent.HIT)
	assert_true(hits.size() == 1 and bool(hits[0].data.get("ram", false)), "reported as a ram hit")
	assert_near(e.pos.x, 1.0, 0.0001, "lands on the cell it aimed for")
	assert_gt(float(s.dash_through_immunity), 0.0, "protection running")
	# Ramming again inside the protection window does nothing.
	e.stamina = e.max_stamina()
	var hp2 := s.hp
	var events2 := H.dash_and_settle(sim, 0, H.W, 2)
	var through2 := H.events_of(events2, BattleEvent.DASH_THROUGH)
	assert_eq(through2.size(), 1, "passed through again")
	assert_false(through2[0].data["stunned"], "no second daze")
	assert_eq(s.hp, hp2, "no second damage")


func test_foe_on_the_landing_cell_carries_the_dash_one_cell_past() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var e := H.place(sim, 0, Vector2(0, 0))
	H.place(sim, 1, Vector2(2, 0))
	var p := DashSystem.plan(sim, e, H.E, 2)
	assert_true(p.ok() and p.extended, "plan extends")
	assert_eq(p.cells, 3, "three cells travelled")
	assert_near(p.cost, e.stats.dash.cost_for(2), 0.0001, "the extra cell is free")
	H.dash_and_settle(sim, 0, H.E, 2)
	assert_near(e.pos.x, 3.0, 0.0001, "landed one cell past the foe")


func test_foe_against_a_wall_makes_the_dash_stop_short() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var east := sim.geometry.bounds.end.x - 0.5
	var e := H.place(sim, 0, Vector2(east - 3, 0))
	var s := H.place(sim, 1, Vector2(east, 0))
	var p := DashSystem.plan(sim, e, H.E, 3)
	assert_true(p.ok(), "still a legal dash")
	assert_eq(p.cells, 2, "stops on the cell before the foe")
	assert_false(p.rams.has(s.id), "no ram if we can't pass")


func test_ram_is_detected_at_extreme_speed() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var e := H.place(sim, 0, Vector2(-3, 0))
	H.place(sim, 1, Vector2(0, 0))
	var fast := e.stats.dash.duplicate()
	fast.travel_ticks_base = 0.0
	fast.travel_ticks_per_cell = 0.1  # 5 cells in 2 ticks: far more than both radii per tick
	e.stats.dash = fast
	var events := H.dash_and_settle(sim, 0, H.E, 5)
	assert_eq(H.events_of(events, BattleEvent.DASH_THROUGH).size(), 1, "swept detection catches it")


func test_one_daze_per_dash_per_opponent() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	H.place(sim, 0, Vector2(-2, 0))
	H.place(sim, 1, Vector2(0, 0))
	var events := H.dash_and_settle(sim, 0, H.E, 4)
	assert_eq(H.events_of(events, BattleEvent.STUN).size(), 1, "exactly one stun")


func test_landing_never_overlaps_a_foe_that_moved_in() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var e := H.place(sim, 0, Vector2(0, 0))
	var s := H.place(sim, 1, Vector2(5, 3))
	H.dash(sim, 0, H.E, 3)
	s.pos = Vector2(3, 0)  # the foe "arrives" on the landing cell mid-dash
	s.prev_pos = s.pos
	for i in 40:
		sim.step({})
	assert_ge(e.pos.distance_to(s.pos), e.radius() + s.radius() - 0.001, "not overlapping")
	assert_true(sim.geometry.is_circle_free(e.pos, e.radius()), "inside the arena")
	var c := sim.setup.arena.cell_center(sim.setup.arena.cell_of(e.pos))
	assert_near(e.pos.distance_to(c), 0.0, 0.0001, "settled on a cell centre")


func test_guard_repels_a_frontal_dash_but_not_one_from_behind() -> void:
	for front in [true, false]:
		var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
		var e := H.place(sim, 0, Vector2(-3, 0))
		var face := Vector2.LEFT if front else Vector2.RIGHT
		var s := H.place(sim, 1, Vector2(0, 0), face)
		var guard := H.cmd(InputCommand.GUARD, InputCommand.GUARD, face, 2.0)
		var hold := H.cmd(InputCommand.GUARD, 0, face, 2.0)
		sim.step({1: guard})
		H.run(sim, 12, null, hold)
		sim.step({0: H.dash_cmd(H.E, 4), 1: hold})
		var events: Array[BattleEvent] = sim.events.duplicate()
		for i in 30:
			sim.step({1: hold})
			events.append_array(sim.events)
		if front:
			assert_eq(H.events_of(events, BattleEvent.DASH_REPELLED).size(), 1, "frontal dash repelled")
			assert_lt(e.pos.x, 0.0, "dasher stayed on its side")
		else:
			var through := H.events_of(events, BattleEvent.DASH_THROUGH)
			assert_true(through.size() == 1 and through[0].data["stunned"], "a dash from behind rams")
			assert_gt(e.pos.x, s.pos.x, "ended behind")


func test_head_on_dashes_clash_without_a_daze() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.EMBERLYN)
	var a := H.place(sim, 0, Vector2(-3, 0))
	var b := H.place(sim, 1, Vector2(3, 0))
	sim.step({0: H.dash_cmd(H.E, 5), 1: H.dash_cmd(H.W, 5)})
	var events: Array[BattleEvent] = sim.events.duplicate()
	events.append_array(H.run(sim, 40))
	assert_eq(H.events_of(events, BattleEvent.DASH_CLASH).size(), 1, "clash")
	assert_eq(H.events_of(events, BattleEvent.STUN).size(), 0, "no daze from a clash")
	assert_lt(a.pos.x, b.pos.x, "both bounced back to their own side")


func test_a_ram_never_guarantees_a_follow_up() -> void:
	# For every attacker: the victim regains control before the attacker can act.
	for path in [H.EMBERLYN, H.STONEBACK]:
		var sim := H.make_sim(path, H.STONEBACK)
		var a := H.place(sim, 0, Vector2(-1, 0))
		var v := H.place(sim, 1, Vector2(0, 0))
		H.dash(sim, 0, H.E, 2)
		var victim_free := -1
		var attacker_free := -1
		for i in 90:
			sim.step({})
			if victim_free < 0 and v.state == SM.STUNNED:
				victim_free = 0
			if victim_free == 0 and v.state != SM.STUNNED:
				victim_free = sim.tick
			if attacker_free < 0 and (FighterSM.is_actionable(a.state) or DashSystem.can_chain(a)):
				attacker_free = sim.tick
		assert_gt(victim_free, 0, "%s: victim was dazed and recovered" % path.get_file())
		assert_ge(attacker_free - victim_free, CombatConst.DASH_THROUGH_FOLLOWUP_MARGIN_TICKS, "%s: victim acts first" % path.get_file())


func test_dashes_chain_from_the_landing() -> void:
	var sim := _open()
	var f := H.place(sim, 0, Vector2(0, 0))
	H.dash(sim, 0, H.E, 1)
	while f.state != SM.DASH_RECOVERY:
		sim.step({})
	# Requested at once, it waits for the chain window, then goes.
	sim.step({0: H.dash_cmd(H.S, 2)})
	var waited := 0
	while f.state == SM.DASH_RECOVERY and waited < 30:
		sim.step({})
		waited += 1
	assert_eq(f.state, SM.DASH_START, "chained straight into the next dash")
	assert_lt(waited + 1, f.stats.dash.recovery_ticks, "before the recovery ran out")
	while f.state != SM.IDLE:
		sim.step({})
	assert_near(f.pos.distance_to(Vector2(1, 2)), 0.0, 0.0001, "both dashes landed")


func test_a_dash_released_mid_dash_waits_for_the_landing() -> void:
	var sim := _open()
	var f := H.place(sim, 0, Vector2(0, 0))
	H.dash(sim, 0, H.E, 5)
	while f.state != SM.DASH_ACTIVE:
		sim.step({})
	# Released at the very start of a long travel, longer ago than the input
	# buffer by the time the chain window opens: still chains.
	sim.step({0: H.dash_cmd(H.N, 2)})
	assert_gt(f.dash_travel_ticks + f.stats.dash.chain_after_ticks, CombatConst.INPUT_BUFFER_TICKS, "longer than the buffer")
	var guard := 0
	while f.state != SM.IDLE and guard < 120:
		sim.step({})
		guard += 1
	assert_near(f.pos.distance_to(Vector2(5, -2)), 0.0, 0.0001, "both dashes happened")
	# A request queued mid-dash is dropped if the dasher gets dazed.
	var sim2 := _open()
	var g := H.place(sim2, 0, Vector2(0, 0))
	H.dash(sim2, 0, H.E, 3)
	sim2.step({0: H.dash_cmd(H.S, 1)})
	assert_true(g.dash_queued, "queued")
	StunRules.apply(sim2, g, 20, &"test")
	assert_false(g.dash_queued, "a daze drops it")


func test_creatures_never_walk() -> void:
	var sim := _open()
	var f := H.place(sim, 0, Vector2(0, 0))
	var everything := InputCommand.ATTACK | InputCommand.GUARD
	H.run(sim, 5, H.cmd(0, 0, Vector2(1, 1), 3.0))
	H.run(sim, 60, H.cmd(everything & ~InputCommand.ATTACK, 0, Vector2(0, 1), 3.0))
	assert_near(f.pos.distance_to(Vector2.ZERO), 0.0, 0.0001, "aiming and guarding never move it")


func test_slows_shorten_dashes() -> void:
	var sim := _open()
	var f := H.place(sim, 0, Vector2(0, 0))
	var full := DashSystem.max_cells(f)
	var app := StatusApplication.new()
	app.status = load("res://resources/status/slow.tres")
	app.duration_ticks = 120
	StatusSystem.apply(sim, f, app, null)
	assert_lt(DashSystem.max_cells(f), full, "slow shortens the longest dash")
	var p := DashSystem.plan(sim, f, H.E, 1)
	var normal := f.stats.dash.travel_ticks_for(1.0)
	assert_gt(p.travel_ticks, normal, "and slows the travel")


func test_the_plan_is_exactly_what_happens() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 31
	for i in 40:
		var setup := BattleSetup.new()
		setup.ruleset = BattleRuleset.make(BattleRuleset.Kind.RANKED)
		setup.countdown = false
		setup.time_limit = false
		setup.arena = ArenaDefinition.ringstones()
		var e := H.creature(H.EMBERLYN)
		var s := H.creature(H.STONEBACK)
		setup.add_creature(0, e["creature"], e["species"])
		setup.add_creature(1, s["creature"], s["species"])
		var sim := BattleSim.new(setup)
		var arena := setup.arena
		var f := H.place(sim, 0, arena.cell_center(Vector2i(rng.randi_range(0, 13), rng.randi_range(0, 8))))
		f.pos = sim.geometry.push_out(f.pos, f.radius())
		H.place(sim, 1, Vector2(0.5, 4.0))
		var dir := rng.randi_range(0, 3)
		var cells := rng.randi_range(1, 5)
		var p := DashSystem.plan(sim, f, dir, cells)
		H.dash_and_settle(sim, 0, dir, cells)
		if p.ok():
			assert_near(f.pos.distance_to(p.target), 0.0, 0.0001, "case %d lands where planned" % i)
		else:
			assert_ne(f.state, SM.DASH_START, "case %d: a refused plan never starts" % i)


func test_lane_picking_has_hysteresis() -> void:
	assert_eq(Cardinal.pick(Vector2(1, 0.2)), 0, "east")
	assert_eq(Cardinal.pick(Vector2(-0.1, 1)), 1, "south")
	assert_eq(Cardinal.pick(Vector2(1, 1)), 0, "exact tie -> horizontal")
	assert_eq(Cardinal.pick(Vector2(1, 1.1), 0), 0, "near the diagonal keeps east")
	assert_eq(Cardinal.pick(Vector2(1, 1.1), -1), 1, "without memory south wins")
	assert_eq(Cardinal.pick(Vector2(0.5, 1), 0), 1, "a clear lean switches lanes")
