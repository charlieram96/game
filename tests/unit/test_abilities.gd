extends WBTestCase
## Spec tests 13 and 14: cooldowns and per-ability hit detection for all
## eight specials (plus basics, clashes, armor).

const H := preload("res://tests/sim_helpers.gd")
const SM := FighterSM.State


## Casts slot `slot` from team 0 aimed at `aim_dir`/`aim_dist`, steps `ticks`,
## and returns the events.
func _cast(sim: BattleSim, slot: int, aim_dir: Vector2, aim_dist: float, ticks: int = 90) -> Array[BattleEvent]:
	var bit: int = InputCommand.ATTACK if slot < 0 else InputCommand.ABILITY_BITS[slot]
	var events: Array[BattleEvent] = []
	sim.step({0: H.cmd(bit, bit, aim_dir, aim_dist)})
	events.append_array(sim.events)
	for i in ticks:
		sim.step({0: H.cmd(0, 0, aim_dir, aim_dist)})
		events.append_array(sim.events)
	return events


func _hits_on(events: Array[BattleEvent], target_id: int) -> int:
	var n := 0
	for e in H.events_of(events, BattleEvent.HIT):
		if e.target_id == target_id:
			n += 1
	return n


func _ember_vs(target_pos: Vector2) -> BattleSim:
	var sim := H.make_sim(H.EMBERLYN, H.STONEBACK)
	H.place(sim, 0, Vector2(0, 0), Vector2.RIGHT)
	H.place(sim, 1, target_pos)
	return sim


func _stone_vs(target_pos: Vector2) -> BattleSim:
	var sim := H.make_sim(H.STONEBACK, H.EMBERLYN)
	H.place(sim, 0, Vector2(0, 0), Vector2.RIGHT)
	H.place(sim, 1, target_pos)
	return sim


func test_cooldown_blocks_reuse_until_expired() -> void:
	var sim := _ember_vs(Vector2(8, 6))
	var f := sim.active_fighter(0)
	var bolt := f.stats.abilities[0]
	_cast(sim, 0, Vector2.RIGHT, 5.0, 20)
	var left := f.cooldown_of(bolt)
	assert_gt(float(left), 0.0, "cooldown running")
	var events := _cast(sim, 0, Vector2.RIGHT, 5.0, 1)
	assert_eq(H.events_of(events, BattleEvent.ABILITY_DENIED).size(), 1, "denied while cooling down")
	assert_eq(f.cooldown_of(bolt), left - 2, "ticks down every tick")
	H.run(sim, left, H.idle())
	var events2 := _cast(sim, 0, Vector2.RIGHT, 5.0, 2)
	assert_eq(H.events_of(events2, BattleEvent.ABILITY_START).size(), 1, "usable again")


func test_ember_bolt_hits_in_line_and_misses_off_line() -> void:
	var sim := _ember_vs(Vector2(6, 0))
	assert_eq(_hits_on(_cast(sim, 0, Vector2.RIGHT, 6.0), 1), 1, "hits target in line")
	var sim2 := _ember_vs(Vector2(6, 2.0))
	assert_eq(_hits_on(_cast(sim2, 0, Vector2.RIGHT, 6.0), 1), 0, "misses target 2 units off line")
	var sim3 := _ember_vs(Vector2(11, 0))
	assert_eq(_hits_on(_cast(sim3, 0, Vector2.RIGHT, 11.0), 1), 0, "fizzles beyond 9 units")


func test_cinder_arc_cone() -> void:
	var inside := _ember_vs(Vector2(1.7, 0.8))  # ~25° off-axis, within 2.4
	assert_eq(_hits_on(_cast(inside, 1, Vector2.RIGHT, 2.0), 1), 1, "inside cone")
	var behind := _ember_vs(Vector2(-1.8, 0))
	assert_eq(_hits_on(_cast(behind, 1, Vector2.RIGHT, 2.0), 1), 0, "behind the cone")
	var far := _ember_vs(Vector2(3.6, 0))
	assert_eq(_hits_on(_cast(far, 1, Vector2.RIGHT, 2.0), 1), 0, "beyond reach")
	var burned := false
	for e in H.events_of(_cast(_ember_vs(Vector2(1.5, 0)), 1, Vector2.RIGHT, 2.0), BattleEvent.STATUS_APPLIED):
		if e.data["status"] == &"burn":
			burned = true
	assert_true(burned, "applies burn")


func test_flash_strike_lunges_to_reach() -> void:
	var sim := _ember_vs(Vector2(2.9, 0))
	var e := sim.active_fighter(0)
	var events := _cast(sim, 2, Vector2.RIGHT, 3.0)
	assert_eq(_hits_on(events, 1), 1, "lunge connects at 2.9 units")
	assert_gt(e.pos.x, 1.0, "moved forward")
	var miss := _ember_vs(Vector2(5.5, 0))
	assert_eq(_hits_on(_cast(miss, 2, Vector2.RIGHT, 5.5), 1), 0, "out of lunge range")


func test_heat_ring_only_hits_after_delay() -> void:
	var sim := _ember_vs(Vector2(5, 0))
	var target := sim.active_fighter(1)
	var hp := target.hp
	_cast(sim, 3, Vector2.RIGHT, 5.0, 35)  # startup 10 + ~25 of the 40-tick telegraph
	assert_near(target.hp, hp, 0.0001, "no damage during telegraph")
	var events := H.run(sim, 30, H.idle())
	assert_eq(_hits_on(events, 1), 1, "erupts after the delay")
	var dodge := _ember_vs(Vector2(5, 0))
	_cast(dodge, 3, Vector2.RIGHT, 5.0, 20)
	var t := dodge.active_fighter(1)
	t.pos = Vector2(5, 4)  # stepped out of the ring
	assert_eq(_hits_on(H.run(dodge, 40, H.idle()), 1), 0, "dodged by leaving the ring")


func test_heat_ring_target_point_clamped_to_range() -> void:
	var sim := _ember_vs(Vector2(12, 0))
	var f := sim.active_fighter(0)
	sim.step({0: H.cmd(InputCommand.ABILITY_4, InputCommand.ABILITY_4, Vector2.RIGHT, 20.0)})
	assert_near(f.ability_point.distance_to(f.pos), 7.0, 0.01, "clamped to max range")


func test_boulder_toss_hits_and_beats_ember_bolt() -> void:
	var sim := _stone_vs(Vector2(6, 0))
	assert_eq(_hits_on(_cast(sim, 0, Vector2.RIGHT, 6.0), 1), 1, "boulder hits")
	# Clash: both fire at each other; the heavier boulder survives and hits.
	var duel := H.make_sim(H.STONEBACK, H.EMBERLYN)
	H.place(duel, 0, Vector2(-4, 0), Vector2.RIGHT)
	H.place(duel, 1, Vector2(4, 0), Vector2.LEFT)
	var events: Array[BattleEvent] = []
	duel.step({0: H.cmd(InputCommand.ABILITY_1, InputCommand.ABILITY_1, Vector2.RIGHT, 8.0)})
	events.append_array(duel.events)
	H.run(duel, 6, H.idle())
	duel.step({1: H.cmd(InputCommand.ABILITY_1, InputCommand.ABILITY_1, Vector2.LEFT, 8.0)})
	events.append_array(duel.events)
	events.append_array(H.run(duel, 90, H.idle(), H.idle()))
	assert_eq(H.events_of(events, BattleEvent.PROJECTILE_CLASH).size(), 1, "projectiles clashed")
	assert_eq(_hits_on(events, 1), 1, "boulder continued and hit Emberlyn")
	assert_eq(_hits_on(events, 0), 0, "ember bolt was destroyed")


func test_projectiles_are_blocked_by_stones() -> void:
	var sim := _stone_vs(Vector2(6, 0))
	sim.geometry.add_circle(Vector2(3, 0), 0.6)
	var events := _cast(sim, 0, Vector2.RIGHT, 6.0)
	assert_eq(_hits_on(events, 1), 0, "blocked")
	assert_eq(H.events_of(events, BattleEvent.PROJECTILE_BLOCKED).size(), 1, "impact event")


func test_ground_pound_radius_and_slow() -> void:
	var near := _stone_vs(Vector2(2.0, 0.5))
	var events := _cast(near, 1, Vector2.RIGHT, 1.0)
	assert_eq(_hits_on(events, 1), 1, "inside radius")
	assert_true(near.active_fighter(1).has_status(&"slow") or H.events_of(events, BattleEvent.STATUS_APPLIED).size() > 0, "slowed")
	var far := _stone_vs(Vector2(3.6, 0))
	assert_eq(_hits_on(_cast(far, 1, Vector2.RIGHT, 1.0), 1), 0, "outside radius")
	assert_eq(H.events_of(_cast(_stone_vs(Vector2(3, 0)), 1, Vector2.RIGHT, 1.0), BattleEvent.TELEGRAPH).size(), 1, "telegraphed")


func test_ground_pound_has_startup_armor() -> void:
	var sim := H.make_sim(H.STONEBACK, H.EMBERLYN)
	var s := H.place(sim, 0, Vector2(0, 0), Vector2.RIGHT)
	H.place(sim, 1, Vector2(1.4, 0), Vector2.LEFT)
	sim.step({0: H.cmd(InputCommand.ABILITY_2, InputCommand.ABILITY_2, Vector2.RIGHT, 1.0)})
	H.run(sim, 2, H.idle())
	# Emberlyn swipes during the windup: Stoneback takes damage but keeps going.
	var events: Array[BattleEvent] = []
	sim.step({1: H.cmd(InputCommand.ATTACK, InputCommand.ATTACK, Vector2.LEFT, 1.4)})
	events.append_array(sim.events)
	for i in 30:
		sim.step({})
		events.append_array(sim.events)
	assert_gt(float(_hits_on(events, 0)), 0.0, "armor still takes damage")
	assert_eq(_hits_on(events, 1), 1, "pound still came out")


func test_stone_guard_reduces_damage_and_repels_dash() -> void:
	var base := _ember_vs(Vector2(6, 0))
	var target := base.active_fighter(1)
	var hp0 := target.hp
	_cast(base, 0, Vector2.RIGHT, 6.0, 40)
	var plain_damage := hp0 - target.hp
	var guarded := _ember_vs(Vector2(6, 0))
	var s := guarded.active_fighter(1)
	guarded.step({1: H.cmd(InputCommand.ABILITY_3, InputCommand.ABILITY_3, Vector2.LEFT, 1.0)})
	H.run(guarded, 8, H.idle())
	assert_true(s.has_status(&"stoneguard"), "stone guard active")
	var hp1 := s.hp
	_cast(guarded, 0, Vector2.RIGHT, 6.0, 40)
	var reduced_damage := hp1 - s.hp
	assert_lt(reduced_damage, plain_damage * 0.5, "much less damage")
	# Dash into Stone Guard bounces off.
	var dash_sim := _ember_vs(Vector2(2.0, 0))
	dash_sim.step({1: H.cmd(InputCommand.ABILITY_3, InputCommand.ABILITY_3, Vector2.LEFT, 1.0)})
	H.run(dash_sim, 8, H.idle())
	var ev := H.dash(dash_sim, 0, H.E, 3)
	ev.append_array(H.run(dash_sim, 15, H.idle()))
	assert_eq(H.events_of(ev, BattleEvent.DASH_REPELLED).size(), 1, "dash repelled")


func test_fault_line_hits_along_line_after_telegraph() -> void:
	var sim := _stone_vs(Vector2(6, 0))
	var target := sim.active_fighter(1)
	var hp := target.hp
	var early := _cast(sim, 3, Vector2.RIGHT, 6.0, 35)
	assert_eq(_hits_on(early, 1), 0, "telegraph first")
	assert_near(target.hp, hp, 0.0001, "no damage yet")
	var later := H.run(sim, 40, H.idle())
	assert_eq(_hits_on(later, 1), 1, "eruption reaches the target")
	var off := _stone_vs(Vector2(6, 1.6))
	assert_eq(_hits_on(_cast(off, 3, Vector2.RIGHT, 6.0, 90), 1), 0, "outside the line width")


func test_basic_attack_string_chains() -> void:
	var sim := _ember_vs(Vector2(1.2, 0))
	var events: Array[BattleEvent] = []
	for i in 70:
		sim.step({0: H.cmd(InputCommand.ATTACK, InputCommand.ATTACK if i % 4 == 0 else 0, Vector2.RIGHT, 1.2)})
		events.append_array(sim.events)
	var ids: Array = []
	for e in H.events_of(events, BattleEvent.ABILITY_START):
		ids.append(e.data["ability"])
	assert_true(ids.has(&"tail_swipe") and ids.has(&"tail_swipe_2") and ids.has(&"tail_swipe_3"), "three-hit string: %s" % [ids])


func test_variant_overrides_do_not_mutate_base() -> void:
	var bolt: AbilityDefinition = load("res://resources/abilities/emberlyn/ember_bolt.tres")
	var needle := bolt.with_variant(&"needle")
	var base_proj: ProjectileComponent = bolt.components[0]
	var needle_proj: ProjectileComponent = needle.components[0]
	assert_near(needle_proj.speed, 22.0, 0.001, "variant speed")
	assert_near(needle_proj.hit.power, 5.5, 0.001, "variant power")
	assert_near(base_proj.speed, 16.0, 0.001, "base speed untouched")
	assert_near(base_proj.hit.power, 7.0, 0.001, "base power untouched")


func test_fast_dash_evades_projectiles() -> void:
	var sim := H.make_sim(H.STONEBACK, H.EMBERLYN)
	H.place(sim, 0, Vector2(-3, 0), Vector2.RIGHT)
	var e := H.place(sim, 1, Vector2(1.0, 0), Vector2.LEFT)
	sim.step({0: H.cmd(InputCommand.ABILITY_1, InputCommand.ABILITY_1, Vector2.RIGHT, 4.0)})
	var events: Array[BattleEvent] = []
	# Wait until the boulder is close, then phase-step through it (dash west).
	for i in 40:
		var close := false
		for v in sim.volumes:
			if v.is_projectile() and v.pos.distance_to(e.pos) < 1.4:
				close = true
		if close and e.state == SM.IDLE:
			sim.step({1: H.dash_cmd(H.W, 2)})
		else:
			sim.step({})
		events.append_array(sim.events)
	assert_gt(float(H.events_of(events, BattleEvent.EVADE).size()), 0.0, "phase step evaded")
	assert_eq(_hits_on(events, 1), 0, "not hit")
