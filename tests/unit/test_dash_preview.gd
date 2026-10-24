extends WBTestCase
## The aim preview's lane: one tile per cell the dash will cross, built from
## the same plan the simulation executes, so what the player sees while
## dragging is what happens on release.

const H := preload("res://tests/sim_helpers.gd")
const C := DashLane.Cell


func _states(sim: BattleSim, f: Fighter, dir: int, cells: int) -> Array[int]:
	return DashPreview.AimMarker._lane_states(sim, f, DashSystem.plan(sim, f, dir, cells))


func _far_away(sim: BattleSim) -> void:
	H.place(sim, 1, Vector2(-12, 8))


func test_open_lane_ends_on_the_landing_cell() -> void:
	var sim := H.make_sim()
	_far_away(sim)
	var f := H.place(sim, 0, Vector2(0, 0))
	assert_eq(_states(sim, f, H.E, 3), [C.PATH, C.PATH, C.LANDING] as Array[int], "path, then landing")
	assert_eq(_states(sim, f, H.N, 1), [C.LANDING] as Array[int], "a one-cell step")


func test_wall_marks_where_the_dash_stops() -> void:
	var sim := H.make_sim()
	_far_away(sim)
	var east := int(sim.geometry.bounds.end.x - 0.5)
	var f := H.place(sim, 0, Vector2(east - 2, 0))
	assert_eq(_states(sim, f, H.E, 5), [C.PATH, C.LANDING, C.WALL] as Array[int], "stops at the board edge")
	var g := H.place(sim, 0, Vector2(east, 0))
	assert_eq(_states(sim, g, H.E, 2), [C.WALL] as Array[int], "nowhere to go: just the wall")


func test_stone_cuts_the_lane_and_shows_what_is_out_of_reach() -> void:
	var sim := H.make_sim()
	_far_away(sim)
	sim.geometry.add_circle(Vector2(2, 0), 0.45)
	var f := H.place(sim, 0, Vector2(0, 0))
	assert_eq(_states(sim, f, H.E, 4), [C.LANDING, C.WALL, C.CUT, C.CUT] as Array[int], "landing before the stone, the rest out of reach")


func test_foe_on_the_lane_is_marked_for_a_ram() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var f := H.place(sim, 0, Vector2(0, 0))
	H.place(sim, 1, Vector2(2, 0))
	assert_eq(_states(sim, f, H.E, 4), [C.PATH, C.RAM, C.PATH, C.LANDING] as Array[int], "ram tile under the foe")
	# A foe on the landing cell carries the dash one cell past it.
	assert_eq(_states(sim, f, H.E, 2), [C.PATH, C.RAM, C.LANDING] as Array[int], "extended past the foe")


func test_protected_foe_is_crossed_but_not_marked() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var f := H.place(sim, 0, Vector2(0, 0))
	var o := H.place(sim, 1, Vector2(2, 0))
	o.dash_through_immunity = 30
	var plan := DashSystem.plan(sim, f, H.E, 4)
	assert_true(o.id in plan.crosses, "crossed")
	assert_false(o.id in plan.rams, "not rammable")
	assert_eq(DashPreview.AimMarker._lane_states(sim, f, plan), [C.PATH, C.PATH, C.PATH, C.LANDING] as Array[int], "no ram tile")


func test_preview_cost_matches_what_the_dash_spends() -> void:
	var sim := H.make_sim()
	_far_away(sim)
	var f := H.place(sim, 0, Vector2(0, 0))
	var plan := DashSystem.plan(sim, f, H.S, 3)
	var before := f.stamina
	H.dash_and_settle(sim, 0, H.S, 3)
	assert_near(before - f.stamina, plan.cost, 0.0001, "spent what the preview showed")
	assert_near(f.pos.distance_to(plan.target), 0.0, 0.0001, "landed where the preview showed")
