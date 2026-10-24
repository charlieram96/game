extends WBTestCase
## Spec tests 1, 2, 11: eight-direction walking, normalized diagonals,
## arena boundaries and obstacles.

const H := preload("res://tests/sim_helpers.gd")


func test_walks_in_all_eight_directions() -> void:
	for d in 8:
		var sim := H.make_sim()
		var f := H.place(sim, 0, Vector2(0, 0))
		H.place(sim, 1, Vector2(12, 8))
		H.run(sim, 40, H.cmd(d))
		var moved := f.pos - Vector2.ZERO
		var expected := CombatConst.dir8_to_vec(d)
		assert_gt(moved.length(), 1.0, "dir %d moved" % d)
		assert_near(rad_to_deg(absf(moved.normalized().angle_to(expected))), 0.0, 0.5, "dir %d heading" % d)
		assert_eq(f.state, FighterSM.State.MOVING, "dir %d state" % d)


func test_diagonal_speed_is_normalized() -> void:
	var speeds: Array[float] = []
	for d in [0, 1, 2, 3]:
		var sim := H.make_sim()
		var f := H.place(sim, 0, Vector2(0, 0))
		H.place(sim, 1, Vector2(12, 8))
		H.run(sim, 60, H.cmd(d))
		speeds.append(f.vel.length())
		assert_le(f.vel.length(), f.stats.movement.speed + 0.001, "never exceeds top speed (dir %d)" % d)
	assert_near(speeds[1], speeds[0], 0.001, "SE equals E")
	assert_near(speeds[3], speeds[2], 0.001, "SW equals S")
	assert_near(speeds[0], 7.0, 0.001, "Emberlyn top speed")


func test_heavy_creature_turns_slower() -> void:
	# Run east at full speed, then reverse: count ticks until moving west.
	var results := {}
	for path in [H.EMBERLYN, H.STONEBACK]:
		var sim := H.make_sim(path, H.TOTEM)
		var f := H.place(sim, 0, Vector2(-6, 0))
		H.place(sim, 1, Vector2(12, 8))
		H.run(sim, 60, H.cmd(0))
		var ticks := 0
		while f.vel.x > -0.5 * f.stats.movement.speed and ticks < 200:
			sim.step({0: H.cmd(4)})
			ticks += 1
		results[path] = ticks
	assert_lt(results[H.EMBERLYN], results[H.STONEBACK], "Emberlyn reverses faster than Stoneback")


func test_cannot_leave_arena_bounds() -> void:
	var sim := H.make_sim()
	var f := sim.active_fighter(0)
	for d in 8:
		H.run(sim, 240, H.cmd(d))
		assert_true(sim.geometry.is_inside_bounds(f.pos, f.radius()), "inside bounds after walking dir %d" % d)


func test_obstacles_block_walking() -> void:
	var sim := H.make_sim()
	sim.geometry.add_circle(Vector2(0, 0), 1.0)
	var f := H.place(sim, 0, Vector2(-4, 0))
	H.place(sim, 1, Vector2(12, 8))
	H.run(sim, 120, H.cmd(0))
	assert_ge(f.pos.distance_to(Vector2.ZERO), 1.0 + f.radius() - 0.01, "stopped at the stone")
	assert_lt(f.pos.x, 0.0, "did not pass through the stone")


func test_box_obstacle_sweep_is_exact() -> void:
	var g := ArenaGeometry.new()
	g.bounds = Rect2(-20, -20, 40, 40)
	g.add_box(Vector2(0, 0), Vector2(1, 1))
	var r := 0.5
	# Straight at the face.
	var s := g.sweep(Vector2(-5, 0), Vector2(10, 0), r)
	assert_true(s.hit, "face hit")
	assert_near(-5.0 + 10.0 * s.t, -1.5, 0.001, "face contact point")
	# Glancing past the rounded corner (misses).
	var miss := g.sweep(Vector2(-5, 1.6), Vector2(10, 0), r)
	assert_false(miss.hit, "passes above the rounded corner")
	# Hits the rounded corner.
	var corner := g.sweep(Vector2(-5, 1.3), Vector2(10, 0), r)
	assert_true(corner.hit, "corner hit")


func test_bodies_are_solid_and_only_heavy_creatures_shove() -> void:
	# Light Emberlyn walking into Stoneback: Stoneback doesn't budge.
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var e := H.place(sim, 0, Vector2(-3, 0))
	var s := H.place(sim, 1, Vector2(0, 0))
	var start_s := s.pos
	H.run(sim, 90, H.cmd(0))
	assert_ge(e.pos.distance_to(s.pos), e.radius() + s.radius() - 0.01, "no overlap")
	assert_lt(s.pos.distance_to(start_s), 0.05, "Stoneback can't be shoved by a light creature")
	# Heavy Stoneback walking into Emberlyn nudges her slowly.
	var sim2 := H.make_sim(H.STONEBACK, H.EMBERLYN)
	var s2 := H.place(sim2, 0, Vector2(-3, 0))
	var e2 := H.place(sim2, 1, Vector2(0, 0))
	H.run(sim2, 90, H.cmd(0))
	assert_ge(s2.pos.distance_to(e2.pos), s2.radius() + e2.radius() - 0.01, "no overlap")
	assert_gt(e2.pos.x, 0.2, "heavy creature nudges a light one")
	assert_lt(e2.pos.x, 2.0, "but only slowly")
