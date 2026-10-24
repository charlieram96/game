extends WBTestCase
## Spec test 17 (ranked normalization) plus leveling, mastery and the
## creature-instance serialization round trip.

const H := preload("res://tests/sim_helpers.gd")


func test_ranked_normalizes_levels() -> void:
	var sp := H.species(H.EMBERLYN)
	var low := CreatureInstance.create(sp, 5, 1)
	var high := CreatureInstance.create(sp, 80, 2)
	var ranked := BattleRuleset.make(BattleRuleset.Kind.RANKED)
	var a := StatCalculator.compute(sp, low, ranked)
	var b := StatCalculator.compute(sp, high, ranked)
	assert_eq(a.level_used, 50, "normalized level")
	assert_near(a.max_hp, b.max_hp, 0.0001, "same HP")
	assert_near(a.attack, b.attack, 0.0001, "same attack")
	assert_near(a.max_hp, sp.base_hp, 0.0001, "equals base at 50")
	assert_eq(low.level, 5, "stored progression untouched")
	assert_eq(high.level, 80, "stored progression untouched")


func test_casual_and_pve_use_real_levels() -> void:
	var sp := H.species(H.STONEBACK)
	var low := CreatureInstance.create(sp, 5, 1)
	var high := CreatureInstance.create(sp, 80, 2)
	for kind in [BattleRuleset.Kind.CASUAL, BattleRuleset.Kind.PVE]:
		var r := BattleRuleset.make(kind)
		var a := StatCalculator.compute(sp, low, r)
		var b := StatCalculator.compute(sp, high, r)
		assert_gt(b.max_hp, a.max_hp * 2.0, "higher level is much stronger (%s)" % r.display_name)
	assert_eq(StatCalculator.describe_level_gap(high, low), "+75 levels advantage", "level gap shown")


func test_identity_preserved_under_normalization() -> void:
	var ranked := BattleRuleset.make(BattleRuleset.Kind.RANKED)
	var e := StatCalculator.compute(H.species(H.EMBERLYN), CreatureInstance.create(H.species(H.EMBERLYN), 50, 1), ranked)
	var s := StatCalculator.compute(H.species(H.STONEBACK), CreatureInstance.create(H.species(H.STONEBACK), 50, 1), ranked)
	assert_gt(e.movement.speed, s.movement.speed, "Emberlyn stays faster")
	assert_gt(s.max_hp, e.max_hp, "Stoneback stays tankier")
	assert_gt(s.stamina.max_stamina, e.stamina.max_stamina, "different stamina pools")


func test_mastery_bonus_never_applies_in_ranked() -> void:
	var sp := H.species(H.EMBERLYN)
	var c := CreatureInstance.create(sp, 50, 1)
	c.mastery[&"ember_bolt"] = {"level": 10, "xp": 0}
	var ranked := StatCalculator.compute(sp, c, BattleRuleset.make(BattleRuleset.Kind.RANKED))
	var pve := StatCalculator.compute(sp, c, BattleRuleset.make(BattleRuleset.Kind.PVE))
	assert_near(ranked.power_mult(&"ember_bolt"), 1.0, 0.0001, "no mastery numbers in ranked")
	assert_gt(pve.power_mult(&"ember_bolt"), 1.0, "PvE mastery bonus")


func test_variants_require_mastery() -> void:
	var sp := H.species(H.EMBERLYN)
	var c := CreatureInstance.create(sp, 50, 1)
	c.variants[&"ember_bolt"] = &"needle"
	var locked := StatCalculator.compute(sp, c, BattleRuleset.make(BattleRuleset.Kind.RANKED))
	assert_near((locked.abilities[0].components[0] as ProjectileComponent).speed, 16.0, 0.001, "locked at mastery 1")
	c.mastery[&"ember_bolt"] = {"level": 3, "xp": 0}
	var unlocked := StatCalculator.compute(sp, c, BattleRuleset.make(BattleRuleset.Kind.RANKED))
	assert_near((unlocked.abilities[0].components[0] as ProjectileComponent).speed, 22.0, 0.001, "needle unlocked at 3")


func test_leveling_curve_and_cap() -> void:
	var c := CreatureInstance.create(H.species(H.EMBERLYN), 1, 1)
	var gained := Leveling.add_xp(c, Leveling.xp_to_next(1) + Leveling.xp_to_next(2))
	assert_eq(gained, [2, 3] as Array[int], "two level-ups")
	assert_eq(c.level, 3, "level 3")
	Leveling.add_xp(c, 100000000)
	assert_eq(c.level, CreatureInstance.MAX_LEVEL, "capped at 100")
	assert_eq(c.xp, 0, "no overflow xp at cap")


func test_mastery_from_battle_usage() -> void:
	var c := CreatureInstance.create(H.species(H.EMBERLYN), 10, 1)
	var ups := Mastery.award_from_battle(c, {&"ember_bolt": {"uses": 10, "hits": 6, "ko": 1}})
	assert_gt(float(c.mastery_level(&"ember_bolt")), 1.0, "mastery rose")
	assert_true(ups.has(&"ember_bolt"), "reported")


func test_creature_instance_round_trip() -> void:
	var c := CreatureInstance.create(H.species(H.STONEBACK), 12, 77)
	c.nickname = "Biscuit"
	c.xp = 33
	c.bond = 40
	c.mastery[&"boulder_toss"] = {"level": 4, "xp": 9}
	c.variants[&"boulder_toss"] = &"base"
	var json := JSON.stringify(c.to_dict())
	var back := CreatureInstance.from_dict(JSON.parse_string(json))
	assert_eq(back.to_dict(), c.to_dict(), "lossless")
	assert_eq(back.nickname, "Biscuit", "nickname")
	assert_eq(back.mastery_level(&"boulder_toss"), 4, "mastery")


func test_from_dict_rejects_out_of_range_values() -> void:
	var back := CreatureInstance.from_dict({"species": "emberlyn", "level": 999, "xp": -5, "bond": 500, "mastery": {"ember_bolt": {"level": 99}}})
	assert_eq(back.level, 100, "level clamped")
	assert_eq(back.xp, 0, "xp clamped")
	assert_eq(back.bond, 100, "bond clamped")
	assert_eq(back.mastery_level(&"ember_bolt"), 10, "mastery clamped")
