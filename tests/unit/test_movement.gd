extends WBTestCase
## Bodies on the board: nothing walks, every creature fits one cell,
## knockback respects walls and stones, and overlapping bodies separate
## (only heavy creatures shove).

const H := preload("res://tests/sim_helpers.gd")


func test_every_creature_fits_inside_one_cell() -> void:
	for path in [H.EMBERLYN, H.STONEBACK, H.TOTEM]:
		var sp := H.species(path)
		assert_lt(sp.movement.collision_radius, CombatConst.CELL_SIZE * 0.5, "%s fits a cell" % path.get_file())


func test_arenas_put_spawns_and_stones_on_cell_centres() -> void:
	for def: ArenaDefinition in [ArenaDefinition.ringstones(), ArenaDefinition.training_yard()]:
		for p in [def.spawn_team0, def.spawn_team1]:
			var c := def.cell_center(def.cell_of(p))
			assert_near(p.distance_to(c), 0.0, 0.0001, "%s spawn on a centre" % def.id)
		for circle in def.circles:
			var at := Vector2(circle.x, circle.y)
			assert_near(at.distance_to(def.cell_center(def.cell_of(at))), 0.0, 0.0001, "%s stone on a centre" % def.id)
			assert_lt(circle.z, 0.5, "stone fits its cell")


func test_cell_helpers_round_trip() -> void:
	var def := ArenaDefinition.ringstones()
	var n := def.cell_count()
	assert_eq(n, Vector2i(20, 12), "20 x 12 board")
	for y in n.y:
		for x in n.x:
			var c := Vector2i(x, y)
			assert_eq(def.cell_of(def.cell_center(c)), c, "cell %s" % c)
	assert_false(def.has_cell(Vector2i(20, 0)), "off the board")


func test_knockback_never_leaves_the_arena() -> void:
	var sim := H.make_sim()
	var f := H.place(sim, 0, Vector2(sim.geometry.bounds.end.x - 1.0, 0))
	MovementSystem.push(f, Vector2.RIGHT, 5.0)
	H.run(sim, 30)
	assert_true(sim.geometry.is_inside_bounds(f.pos, f.radius()), "inside bounds")


func test_knockback_stops_at_stones() -> void:
	var sim := H.make_sim()
	sim.geometry.add_circle(Vector2(0, 0), 0.45)
	var f := H.place(sim, 0, Vector2(-2, 0))
	H.place(sim, 1, Vector2(12, 8))
	MovementSystem.push(f, Vector2.RIGHT, 4.0)
	H.run(sim, 30)
	assert_ge(f.pos.distance_to(Vector2.ZERO), 0.45 + f.radius() - 0.01, "stopped at the stone")
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


func test_bodies_separate_and_only_heavy_creatures_shove() -> void:
	# Light Emberlyn knocked into Stoneback: Stoneback doesn't budge.
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var e := H.place(sim, 0, Vector2(-2, 0))
	var s := H.place(sim, 1, Vector2(0, 0))
	MovementSystem.push(e, Vector2.RIGHT, 3.0)
	H.run(sim, 40)
	assert_ge(e.pos.distance_to(s.pos), e.radius() + s.radius() - 0.01, "no overlap")
	assert_lt(s.pos.distance_to(Vector2.ZERO), 0.15, "Stoneback barely moves when a light creature is knocked into it")
	# Heavy Stoneback knocked into Emberlyn nudges her.
	var sim2 := H.make_sim(H.STONEBACK, H.EMBERLYN)
	var s2 := H.place(sim2, 0, Vector2(-2, 0))
	var e2 := H.place(sim2, 1, Vector2(0, 0))
	MovementSystem.push(s2, Vector2.RIGHT, 3.0)
	H.run(sim2, 40)
	assert_ge(s2.pos.distance_to(e2.pos), s2.radius() + e2.radius() - 0.01, "no overlap")
	assert_gt(e2.pos.x, 0.1, "heavy creature nudges a light one")
