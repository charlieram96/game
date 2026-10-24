extends WBTestCase
## Spec tests 5, 6, 7, 8: stamina consumption, Focus-only regeneration,
## per-creature recovery rates, Focus interruption.

const H := preload("res://tests/sim_helpers.gd")
const SM := FighterSM.State


func _focus_cmd() -> InputCommand:
	return H.cmd(InputCommand.FOCUS, 0)


func test_stamina_does_not_regenerate_without_focus() -> void:
	var sim := H.make_sim()
	var f := H.place(sim, 0, Vector2(0, 0))
	H.place(sim, 1, Vector2(12, 8))
	f.stamina = 30.0
	H.run(sim, 120, H.idle())
	assert_near(f.stamina, 30.0, 0.0001, "idle: no regen")
	H.dash_and_settle(sim, 0, H.E, 2)
	H.run(sim, 120, H.idle())
	assert_near(f.stamina, 30.0 - f.stats.dash.cost_for(2), 0.0001, "after a dash: no regen")


func test_focus_regenerates_and_has_commitment() -> void:
	var sim := H.make_sim(H.STONEBACK, H.TOTEM)
	var f := H.place(sim, 0, Vector2(0, 0))
	H.place(sim, 1, Vector2(12, 8))
	f.stamina = 10.0
	sim.step({0: H.cmd(InputCommand.FOCUS, InputCommand.FOCUS)})
	assert_eq(f.state, SM.FOCUS_ENTER, "enter state")
	var enter_ticks := 1
	while f.state == SM.FOCUS_ENTER:
		assert_near(f.stamina, 10.0, 0.0001, "no regen while entering")
		sim.step({0: _focus_cmd()})
		enter_ticks += 1
	assert_eq(f.state, SM.FOCUSING, "focusing")
	assert_eq(enter_ticks, 1 + CombatConst.DEFAULT_FOCUS_ENTER_TICKS, "120 ms entry")
	H.run(sim, 60, _focus_cmd())
	assert_gt(f.stamina, 10.0, "regenerated")
	# Release -> exit commitment, then idle.
	sim.step({0: H.idle()})
	assert_eq(f.state, SM.FOCUS_EXIT, "exit state")
	var exit_ticks := 1
	while f.state == SM.FOCUS_EXIT:
		sim.step({0: H.idle()})
		exit_ticks += 1
	assert_eq(exit_ticks, 1 + CombatConst.DEFAULT_FOCUS_EXIT_TICKS, "120 ms exit")
	assert_eq(f.state, SM.IDLE, "back to idle")


func test_focus_blocks_movement_attacks_and_dash() -> void:
	var sim := H.make_sim()
	var f := H.place(sim, 0, Vector2(0, 0))
	H.place(sim, 1, Vector2(12, 8))
	f.stamina = 30.0
	H.run(sim, 20, _focus_cmd())
	assert_eq(f.state, SM.FOCUSING, "focusing")
	var pos := f.pos
	var all := InputCommand.FOCUS | InputCommand.ATTACK | InputCommand.ABILITY_1
	H.run(sim, 10, H.dash_cmd(H.E, 2, all, InputCommand.ATTACK | InputCommand.ABILITY_1))
	assert_eq(f.state, SM.FOCUSING, "still focusing")
	assert_eq(f.pos, pos, "rooted")
	assert_eq(f.cooldown_of(f.stats.abilities[0]), 0, "no ability fired")


func test_stamina_never_exceeds_maximum() -> void:
	var sim := H.make_sim()
	var f := H.place(sim, 0, Vector2(0, 0))
	H.place(sim, 1, Vector2(12, 8))
	f.stamina = f.max_stamina() - 1.0
	var events := H.run(sim, 200, _focus_cmd())
	assert_near(f.stamina, f.max_stamina(), 0.0001, "clamped at max")
	assert_eq(H.events_of(events, BattleEvent.STAMINA_FULL).size(), 1, "announced once")


func test_recovery_rates_differ_by_creature() -> void:
	var gains := {}
	for path in [H.EMBERLYN, H.STONEBACK]:
		var sim := H.make_sim(path, H.TOTEM)
		var f := H.place(sim, 0, Vector2(0, 0))
		H.place(sim, 1, Vector2(12, 8))
		f.stamina = 0.0
		sim.step({0: H.cmd(InputCommand.FOCUS, InputCommand.FOCUS)})
		while f.state != SM.FOCUSING:
			sim.step({0: _focus_cmd()})
		var before := f.stamina
		H.run(sim, 60, _focus_cmd())
		gains[path] = f.stamina - before
	assert_near(gains[H.EMBERLYN], 50.0, 0.6, "Emberlyn 50/s")
	assert_near(gains[H.STONEBACK], 40.0, 0.6, "Stoneback 40/s")


func test_quickfoot_passive_shortens_focus_commitment() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.TOTEM)
	var f := sim.active_fighter(0)
	assert_lt(StaminaSystem.enter_ticks(f), CombatConst.DEFAULT_FOCUS_ENTER_TICKS, "faster entry")
	assert_lt(StaminaSystem.exit_ticks(f), CombatConst.DEFAULT_FOCUS_EXIT_TICKS, "faster exit")


func test_damage_interrupts_focus() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var e := H.place(sim, 0, Vector2(0, 0))
	H.place(sim, 1, Vector2(4, 0), Vector2.LEFT)
	e.stamina = 0.0
	H.run(sim, 30, _focus_cmd())
	assert_eq(e.state, SM.FOCUSING, "focusing")
	# Stoneback throws a boulder at the focusing Emberlyn.
	var events: Array[BattleEvent] = []
	sim.step({0: _focus_cmd(), 1: H.cmd(InputCommand.ABILITY_1, InputCommand.ABILITY_1, Vector2.LEFT, 4.0)})
	events.append_array(sim.events)
	for i in 60:
		sim.step({0: _focus_cmd()})
		events.append_array(sim.events)
	assert_gt(H.events_of(events, BattleEvent.HIT).size(), 0, "was hit")
	assert_gt(H.events_of(events, BattleEvent.FOCUS_INTERRUPTED).size(), 0, "focus interrupted")


func test_burn_ticks_interrupt_focus() -> void:
	var sim := H.make_sim(H.STONEBACK, H.EMBERLYN)
	var s := H.place(sim, 0, Vector2(0, 0))
	var burn: StatusEffectDefinition = load("res://resources/status/burn.tres")
	var app := StatusApplication.new()
	app.status = burn
	StatusSystem.apply(sim, s, app, sim.active_fighter(1))
	s.stamina = 0.0
	var events := H.run(sim, 40, _focus_cmd())
	assert_gt(H.events_of(events, BattleEvent.DOT).size(), 0, "burn ticked")
	assert_gt(H.events_of(events, BattleEvent.FOCUS_INTERRUPTED).size(), 0, "burn interrupted focus")
