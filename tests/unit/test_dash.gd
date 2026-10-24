extends WBTestCase
## Spec tests 3, 4, 9, 10, 11: strict four-way dash, tie-breaking,
## dash-through detection, landing placement, walls.

const H := preload("res://tests/sim_helpers.gd")
const SM := FighterSM.State


func _dash(sim: BattleSim, move_dir: int, axis_hint: int = Cardinal.AXIS_UNKNOWN) -> void:
	H.tap(sim, 0, InputCommand.DASH, move_dir, Vector2.ZERO, 0.0, axis_hint)


func test_dash_is_always_cardinal() -> void:
	for d in range(-1, 8):
		var sim := H.make_sim()
		var f := H.place(sim, 0, Vector2(0, 0), Vector2(0.6, -0.8))
		H.place(sim, 1, Vector2(12, 8))
		_dash(sim, d)
		assert_true(Cardinal.is_cardinal(f.dash_dir), "dir %d -> cardinal %s" % [d, f.dash_dir])
		var start := f.pos
		H.run(sim, 30, H.cmd(d))
		var moved := f.pos - start
		# The dash itself is purely along one axis (walking after it may add more).
		assert_true(absf(f.dash_dir.x) + absf(f.dash_dir.y) == 1.0, "unit cardinal")
		if f.dash_dir.x != 0.0:
			assert_gt(absf(moved.x), 3.0, "dir %d travelled horizontally" % d)
		else:
			assert_gt(absf(moved.y), 3.0, "dir %d travelled vertically" % d)


func test_pure_dash_displacement_has_no_diagonal_component() -> void:
	var sim := H.make_sim()
	var f := H.place(sim, 0, Vector2(0, 0))
	H.place(sim, 1, Vector2(12, 8))
	_dash(sim, 1)  # SE held -> tie -> horizontal (east)
	var start := f.pos
	while f.state != SM.DASH_RECOVERY:
		sim.step({0: H.cmd(-1)})
	assert_near(f.pos.y, start.y, 0.0001, "no vertical drift")
	assert_near(f.pos.x - start.x, f.stats.dash.distance, 0.01, "full dash distance")


func test_tie_break_rules() -> void:
	var fallback := Cardinal.SOUTH
	var ne := CombatConst.dir8_to_vec(7)
	assert_eq(Cardinal.from_input(ne, Cardinal.AXIS_HORIZONTAL, fallback), Cardinal.EAST, "newest key horizontal")
	assert_eq(Cardinal.from_input(ne, Cardinal.AXIS_VERTICAL, fallback), Cardinal.NORTH, "newest key vertical")
	assert_eq(Cardinal.from_input(ne, Cardinal.AXIS_UNKNOWN, fallback), Cardinal.EAST, "unknown -> horizontal")
	assert_eq(Cardinal.from_input(Vector2(0.9, 0.3), Cardinal.AXIS_VERTICAL, fallback), Cardinal.EAST, "dominant axis beats hint")
	assert_eq(Cardinal.from_input(Vector2(-0.2, -0.95), Cardinal.AXIS_HORIZONTAL, fallback), Cardinal.NORTH, "dominant vertical")
	assert_eq(Cardinal.from_input(Vector2.ZERO, Cardinal.AXIS_UNKNOWN, Vector2(-0.7, 0.2)), Cardinal.WEST, "no input -> facing")


func test_dash_without_input_uses_last_cardinal_facing() -> void:
	var sim := H.make_sim()
	var f := H.place(sim, 0, Vector2(0, 0))
	H.place(sim, 1, Vector2(12, 8))
	H.run(sim, 10, H.cmd(6))  # walk north, no aim device -> facing north... aim soft-locks
	H.run(sim, 20, H.cmd(-1, 0, 0, Vector2(0, 1), 3.0))  # aim south with the mouse
	H.tap(sim, 0, InputCommand.DASH, -1, Vector2(0, 1), 3.0)
	assert_eq(f.dash_dir, Cardinal.SOUTH, "dashes toward last cardinal facing")


func test_stamina_cost_and_insufficient_stamina() -> void:
	var sim := H.make_sim()
	var f := H.place(sim, 0, Vector2(0, 0))
	H.place(sim, 1, Vector2(12, 8))
	var cost := f.stats.dash.stamina_cost
	var before := f.stamina
	_dash(sim, 0)
	assert_near(f.stamina, before - cost, 0.0001, "dash costs stamina")
	H.run(sim, 40, H.idle())
	f.stamina = cost - 1.0
	var events := H.tap(sim, 0, InputCommand.DASH, 0)
	assert_eq(f.state != SM.DASH_START, true, "can't dash without stamina")
	assert_eq(H.events_of(events, BattleEvent.DASH_NO_STAMINA).size(), 1, "feedback event")
	assert_ge(f.stamina, 0.0, "stamina never negative")


func test_dash_through_stuns_and_grants_immunity() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var e := H.place(sim, 0, Vector2(-2, 0))
	var s := H.place(sim, 1, Vector2(0, 0), Vector2.LEFT)
	var events := H.tap(sim, 0, InputCommand.DASH, 0)
	events.append_array(H.run(sim, 14, H.idle()))
	var through := H.events_of(events, BattleEvent.DASH_THROUGH)
	assert_eq(through.size(), 1, "one dash-through")
	assert_true(through[0].data["stunned"], "stunned")
	assert_eq(int(through[0].data["stun_ticks"]), CombatConst.DASH_THROUGH_STUN_TICKS, "250 ms stun")
	assert_gt(float(s.dash_through_immunity), 40.0, "protection running")
	assert_gt(e.pos.x, s.pos.x, "attacker ended on the far side")
	# Second dash-through within the protection window does not stun.
	H.run(sim, 30, H.idle())
	e.stamina = e.max_stamina()
	var events2 := H.tap(sim, 0, InputCommand.DASH, 4)
	events2.append_array(H.run(sim, 14, H.idle()))
	var through2 := H.events_of(events2, BattleEvent.DASH_THROUGH)
	assert_eq(through2.size(), 1, "passed through again")
	assert_false(through2[0].data["stunned"], "protected from a second stun")


func test_dash_through_detects_at_extreme_speed() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var e := H.place(sim, 0, Vector2(-6, 0))
	H.place(sim, 1, Vector2(0, 0))
	var fast := e.stats.dash.duplicate()
	fast.distance = 12.0
	fast.duration_ticks = 2  # 6 units per tick: far more than both radii
	e.stats.dash = fast
	var events := H.tap(sim, 0, InputCommand.DASH, 0)
	events.append_array(H.run(sim, 10, H.idle()))
	assert_eq(H.events_of(events, BattleEvent.DASH_THROUGH).size(), 1, "swept detection catches it")


func test_one_stun_per_dash_per_opponent() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	H.place(sim, 0, Vector2(-2, 0))
	H.place(sim, 1, Vector2(0, 0))
	var events := H.tap(sim, 0, InputCommand.DASH, 0)
	events.append_array(H.run(sim, 20, H.idle()))
	assert_eq(H.events_of(events, BattleEvent.STUN).size(), 1, "exactly one stun")


func test_landing_is_about_one_cell_beyond_and_never_overlapping() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var e := H.place(sim, 0, Vector2(-1.2, 0))
	var s := H.place(sim, 1, Vector2(0, 0))
	# Short remaining dash: the landing extension must carry it past.
	var short := e.stats.dash.duplicate()
	short.distance = 1.5
	e.stats.dash = short
	H.tap(sim, 0, InputCommand.DASH, 0)
	H.run(sim, 20, H.idle())
	var gap := e.pos.x - s.pos.x
	assert_ge(gap, CombatConst.CELL_SIZE - 0.01, "at least one cell beyond")
	assert_ge(e.pos.distance_to(s.pos), e.radius() + s.radius() - 0.001, "not overlapping")


func test_landing_blocked_by_wall_finds_safe_spot() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var right_wall := sim.geometry.bounds.end.x
	var s := H.place(sim, 1, Vector2(right_wall - 0.6, 0))
	var e := H.place(sim, 0, Vector2(right_wall - 3.0, 0))
	H.tap(sim, 0, InputCommand.DASH, 0)
	H.run(sim, 25, H.idle())
	assert_true(sim.geometry.is_circle_free(e.pos, e.radius()), "inside arena, not in a wall")
	assert_ge(e.pos.distance_to(s.pos), e.radius() + s.radius() - 0.001, "not inside the opponent")


func test_landing_blocked_by_stone_never_clips() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	sim.geometry.add_circle(Vector2(1.4, 0), 0.6)
	var s := H.place(sim, 1, Vector2(0, 0))
	var e := H.place(sim, 0, Vector2(-2, 0))
	H.tap(sim, 0, InputCommand.DASH, 0)
	H.run(sim, 25, H.idle())
	assert_true(sim.geometry.is_circle_free(e.pos, e.radius()), "not clipped into the stone")
	assert_ge(e.pos.distance_to(s.pos), e.radius() + s.radius() - 0.001, "not inside the opponent")


func test_dash_stops_at_walls() -> void:
	var sim := H.make_sim()
	var e := H.place(sim, 0, Vector2(sim.geometry.bounds.end.x - 1.0, 0))
	H.place(sim, 1, Vector2(-12, 8))
	H.tap(sim, 0, InputCommand.DASH, 0)
	H.run(sim, 20, H.idle())
	assert_true(sim.geometry.is_inside_bounds(e.pos, e.radius()), "dash clamped by wall")


func test_guard_repels_frontal_dash_but_not_from_behind() -> void:
	# Front: defender guards facing the dasher.
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var e := H.place(sim, 0, Vector2(-2.5, 0))
	H.place(sim, 1, Vector2(0, 0), Vector2.LEFT)
	var guard := H.cmd(-1, InputCommand.GUARD, InputCommand.GUARD, Vector2.LEFT, 2.0)
	sim.step({1: guard})
	H.run(sim, 12, null, H.cmd(-1, InputCommand.GUARD, 0, Vector2.LEFT, 2.0))
	sim.step({0: H.cmd(0, InputCommand.DASH, InputCommand.DASH), 1: H.cmd(-1, InputCommand.GUARD, 0, Vector2.LEFT, 2.0)})
	var events: Array[BattleEvent] = sim.events.duplicate()
	for i in 14:
		sim.step({1: H.cmd(-1, InputCommand.GUARD, 0, Vector2.LEFT, 2.0)})
		events.append_array(sim.events)
	assert_eq(H.events_of(events, BattleEvent.DASH_REPELLED).size(), 1, "frontal dash repelled")
	assert_eq(e.state, SM.STUNNED, "dasher stunned by the repel")
	assert_lt(e.pos.x, 0.0, "dasher stayed on its side")
	# Behind: defender guards facing away.
	var sim2 := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var e2 := H.place(sim2, 0, Vector2(-2.5, 0))
	var s2 := H.place(sim2, 1, Vector2(0, 0), Vector2.RIGHT)
	sim2.step({1: H.cmd(-1, InputCommand.GUARD, InputCommand.GUARD, Vector2.RIGHT, 2.0)})
	H.run(sim2, 12, null, H.cmd(-1, InputCommand.GUARD, 0, Vector2.RIGHT, 2.0))
	sim2.step({0: H.cmd(0, InputCommand.DASH, InputCommand.DASH), 1: H.cmd(-1, InputCommand.GUARD, 0, Vector2.RIGHT, 2.0)})
	var ev2: Array[BattleEvent] = sim2.events.duplicate()
	for i in 14:
		sim2.step({1: H.cmd(-1, InputCommand.GUARD, 0, Vector2.RIGHT, 2.0)})
		ev2.append_array(sim2.events)
	var through := H.events_of(ev2, BattleEvent.DASH_THROUGH)
	assert_eq(through.size(), 1, "dash from behind passes")
	assert_true(through.size() == 1 and through[0].data["stunned"], "and stuns")
	assert_gt(e2.pos.x, s2.pos.x, "ended behind")


func test_head_on_dashes_clash_without_stun() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.EMBERLYN)
	H.place(sim, 0, Vector2(-2.5, 0))
	H.place(sim, 1, Vector2(2.5, 0))
	sim.step({0: H.cmd(0, InputCommand.DASH, InputCommand.DASH), 1: H.cmd(4, InputCommand.DASH, InputCommand.DASH)})
	var events: Array[BattleEvent] = sim.events.duplicate()
	events.append_array(H.run(sim, 20, H.idle(), H.idle()))
	assert_eq(H.events_of(events, BattleEvent.DASH_CLASH).size(), 1, "clash")
	assert_eq(H.events_of(events, BattleEvent.STUN).size(), 0, "no stun from a clash")


func test_dash_through_never_guarantees_a_follow_up() -> void:
	# For every attacker: the victim regains control before the attacker's
	# fastest possible attack can even start.
	for path in [H.EMBERLYN, H.STONEBACK]:
		var sim := H.make_sim(path, H.STONEBACK)
		var a := H.place(sim, 0, Vector2(-1.5, 0))
		var v := H.place(sim, 1, Vector2(0, 0))
		H.tap(sim, 0, InputCommand.DASH, 0)
		var victim_free_tick := -1
		var attacker_free_tick := -1
		for i in 80:
			sim.step({})
			if victim_free_tick < 0 and v.state != SM.STUNNED and sim.tick > 3:
				victim_free_tick = sim.tick
			if attacker_free_tick < 0 and FighterSM.is_actionable(a.state):
				attacker_free_tick = sim.tick
		assert_gt(victim_free_tick, 0, "victim recovered")
		assert_ge(attacker_free_tick - victim_free_tick, CombatConst.DASH_THROUGH_FOLLOWUP_MARGIN_TICKS, "%s: victim acts first" % path.get_file())
