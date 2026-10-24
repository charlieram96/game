extends WBTestCase
## Spec test 12 plus the combat state machine: stun duration, chain
## reduction, Steadfast immunity, wake-up grace, illegal transitions.

const H := preload("res://tests/sim_helpers.gd")
const SM := FighterSM.State


func test_transition_table_rejects_illegal_moves() -> void:
	assert_false(FighterSM.can_transition(SM.STUNNED, SM.DASH_START), "stunned can't dash")
	assert_false(FighterSM.can_transition(SM.FOCUSING, SM.ATTACK_START), "focusing can't attack")
	assert_false(FighterSM.can_transition(SM.ATTACK_ACTIVE, SM.DASH_START), "active attack can't dash")
	assert_false(FighterSM.can_transition(SM.KNOCKED_OUT, SM.IDLE), "KO is final")
	assert_false(FighterSM.can_transition(SM.STUNNED, SM.SWITCHING), "no switching while stunned")
	assert_true(FighterSM.can_transition(SM.ATTACK_RECOVERY, SM.DASH_START), "dash-cancel is allowed by table (gated by data)")
	assert_true(FighterSM.can_transition(SM.FOCUSING, SM.FOCUS_EXIT), "focus exit")


func test_sim_refuses_illegal_transition() -> void:
	var sim := H.make_sim()
	var f := sim.active_fighter(0)
	sim.set_state(f, SM.STUNNED, 10)
	var ok := sim.set_state(f, SM.DASH_START, 2)
	assert_false(ok, "refused")
	assert_eq(f.state, SM.STUNNED, "unchanged")


func test_stunned_creature_cannot_dash_or_attack() -> void:
	var sim := H.make_sim()
	var f := H.place(sim, 0, Vector2(0, 0))
	H.place(sim, 1, Vector2(12, 8))
	StunRules.apply(sim, f, 30, &"hit")
	var stamina := f.stamina
	H.run(sim, 10, H.dash_cmd(H.E, 2, InputCommand.ATTACK, InputCommand.ATTACK))
	assert_eq(f.state, SM.STUNNED, "still stunned")
	assert_near(f.stamina, stamina, 0.0001, "no dash paid")


func test_stun_lasts_exact_duration() -> void:
	var sim := H.make_sim()
	var f := H.place(sim, 0, Vector2(0, 0))
	H.place(sim, 1, Vector2(12, 8))
	var applied := StunRules.apply(sim, f, 15, &"dash")
	assert_eq(applied, 15, "full first stun")
	var ticks := 0
	while f.state == SM.STUNNED and ticks < 100:
		sim.step({})
		ticks += 1
	assert_eq(ticks, 15, "250 ms at 60 Hz")


func test_chained_stuns_shrink_then_grant_steadfast() -> void:
	var sim := H.make_sim()
	var f := H.place(sim, 0, Vector2(0, 0))
	H.place(sim, 1, Vector2(12, 8))
	var a1 := StunRules.apply(sim, f, 20, &"hit")
	var a2 := StunRules.apply(sim, f, 20, &"hit")
	var a3 := StunRules.apply(sim, f, 20, &"hit")
	assert_eq(a1, 20, "100%")
	assert_eq(a2, 15, "75%")
	assert_eq(a3, 10, "50%")
	H.run(sim, 20, H.idle())
	assert_gt(float(f.steadfast), 0.0, "steadfast after the third chained stun")
	var a4 := StunRules.apply(sim, f, 20, &"hit")
	assert_eq(a4, 0, "steadfast resists")


func test_wakeup_grace_prevents_instant_restun() -> void:
	var sim := H.make_sim()
	var f := H.place(sim, 0, Vector2(0, 0))
	H.place(sim, 1, Vector2(12, 8))
	StunRules.apply(sim, f, 10, &"hit")
	while f.state == SM.STUNNED:
		sim.step({})
	assert_eq(StunRules.apply(sim, f, 10, &"hit"), 0, "grace window")
	H.run(sim, CombatConst.WAKEUP_GRACE_TICKS + 1, H.idle())
	assert_gt(float(StunRules.apply(sim, f, 10, &"hit")), 0.0, "stunnable again")


func test_buffered_input_comes_out_on_first_free_tick() -> void:
	var sim := H.make_sim()
	var f := H.place(sim, 0, Vector2(0, 0))
	H.place(sim, 1, Vector2(12, 8))
	StunRules.apply(sim, f, 12, &"hit")
	H.run(sim, 8, H.idle())
	# Press dash 4 ticks before the stun ends.
	sim.step({0: H.dash_cmd(H.E, 2)})
	var waited := 0
	while f.state == SM.STUNNED and waited < 20:
		sim.step({0: H.idle()})
		waited += 1
	assert_eq(f.state, SM.DASH_START, "buffered dash executed on wake-up")


func test_guard_break_on_empty_stamina() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var e := H.place(sim, 0, Vector2(0, 0), Vector2.RIGHT)
	H.place(sim, 1, Vector2(1.6, 0), Vector2.LEFT)
	e.stamina = 3.0
	var guard := H.cmd(InputCommand.GUARD, InputCommand.GUARD, Vector2.RIGHT, 2.0)
	sim.step({0: guard})
	H.run(sim, 12, H.cmd(InputCommand.GUARD, 0, Vector2.RIGHT, 2.0))
	var events: Array[BattleEvent] = []
	sim.step({0: H.cmd(InputCommand.GUARD, 0, Vector2.RIGHT, 2.0), 1: H.cmd(InputCommand.ATTACK, InputCommand.ATTACK, Vector2.LEFT, 1.6)})
	events.append_array(sim.events)
	for i in 30:
		sim.step({0: H.cmd(InputCommand.GUARD, 0, Vector2.RIGHT, 2.0)})
		events.append_array(sim.events)
	assert_eq(H.events_of(events, BattleEvent.GUARD_BREAK).size(), 1, "guard broke")
	assert_eq(e.state, SM.STUNNED, "long stun")


func test_perfect_guard_negates_and_staggers_melee() -> void:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	var e := H.place(sim, 0, Vector2(0, 0), Vector2.RIGHT)
	var s := H.place(sim, 1, Vector2(1.6, 0), Vector2.LEFT)
	# Stoneback starts its 8-tick shell bash; Emberlyn guards 3 ticks before impact.
	sim.step({1: H.cmd(InputCommand.ATTACK, InputCommand.ATTACK, Vector2.LEFT, 1.6)})
	H.run(sim, 5, H.idle())
	var hp := e.hp
	var events: Array[BattleEvent] = []
	sim.step({0: H.cmd(InputCommand.GUARD, InputCommand.GUARD, Vector2.RIGHT, 2.0)})
	events.append_array(sim.events)
	for i in 10:
		sim.step({0: H.cmd(InputCommand.GUARD, 0, Vector2.RIGHT, 2.0)})
		events.append_array(sim.events)
	assert_eq(H.events_of(events, BattleEvent.PERFECT_GUARD).size(), 1, "perfect guard")
	assert_near(e.hp, hp, 0.0001, "no chip")
	assert_eq(s.state, SM.STUNNED, "attacker staggered")
