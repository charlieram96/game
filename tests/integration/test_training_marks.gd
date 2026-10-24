extends WBTestCase
## The tutorial's "dash to move" marks are reachable on the training yard's
## board with the straight dashes the tip describes.

const H := preload("res://tests/sim_helpers.gd")


func test_move_marks_are_reachable_with_straight_dashes() -> void:
	var setup := BattleSetup.new()
	setup.ruleset = BattleRuleset.make(BattleRuleset.Kind.CASUAL)
	setup.countdown = false
	setup.time_limit = false
	setup.arena = ArenaDefinition.training_yard()
	var a := H.creature(H.EMBERLYN)
	var b := H.creature(H.TOTEM)
	setup.add_creature(0, a["creature"], a["species"])
	setup.add_creature(1, b["creature"], b["species"])
	var sim := BattleSim.new(setup)
	var f := sim.active_fighter(0)
	var arena := setup.arena
	for p in TrainingDirector.MOVE_MARKS:
		assert_near(p.distance_to(arena.cell_center(arena.cell_of(p))), 0.0, 0.0001, "mark %s on a cell centre" % p)
	var route := [Vector2i(H.N, 3), Vector2i(H.E, 4), Vector2i(H.S, 5)]
	for i in route.size():
		f.stamina = f.max_stamina()
		H.dash_and_settle(sim, 0, route[i].x, route[i].y)
		assert_near(f.pos.distance_to(TrainingDirector.MOVE_MARKS[i]), 0.0, 0.0001, "landed on mark %d" % (i + 1))
