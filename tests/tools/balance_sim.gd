extends SceneTree
## AI-vs-AI balance harness. Runs N headless matches per matchup and prints
## win rates, average match length, timeouts, damage and per-ability hit rates.
##
##   N=40 godot --headless --path . -s res://tests/tools/balance_sim.gd
##   ONLY=easy-story N=150 godot ...   # only matchups with these two AI profiles

func _init() -> void:
	process_frame.connect(_go, CONNECT_ONE_SHOT)

func _go() -> void:
	var e: CreatureDefinition = load("res://resources/creatures/emberlyn.tres")
	var s: CreatureDefinition = load("res://resources/creatures/stoneback.tres")
	var n := int(OS.get_environment("N")) if OS.get_environment("N") != "" else 40
	var only := OS.get_environment("ONLY")
	for pair in [[e, s, "normal", "normal"], [s, e, "normal", "normal"], [e, e, "normal", "normal"], [s, s, "normal", "normal"], [e, s, "normal", "story"], [e, s, "easy", "story"]]:
		if only != "" and "%s-%s" % [pair[2], pair[3]] != only:
			continue
		var wins := [0, 0, 0]
		var total_ticks := 0
		var timeouts := 0
		var dmg := [0.0, 0.0]
		var surge := [0.0, 0.0]
		var spent := [0.0, 0.0]
		var rams := [0.0, 0.0]
		var usage := {}
		for i in n:
			var setup := BattleSetup.new()
			setup.ruleset = BattleRuleset.make(BattleRuleset.Kind.RANKED)
			setup.countdown = false
			setup.arena = ArenaDefinition.ringstones()
			setup.add_creature(0, CreatureInstance.create(pair[0], 50, 1), pair[0])
			setup.add_creature(1, CreatureInstance.create(pair[1], 50, 2), pair[1])
			var tr := LocalBattleTransport.new()
			tr.start(setup)
			tr.set_input_source(0, CombatAI.new(AIProfile.preset(pair[2]), 1000 + i))
			tr.set_input_source(1, CombatAI.new(AIProfile.preset(pair[3]), 5000 + i))
			for t in 9000:
				tr.step()
				if tr.sim.is_finished():
					break
			var w: int = tr.sim.winner_team
			wins[w if w >= 0 else 2] += 1
			total_ticks += tr.sim.tick
			if tr.sim.end_reason == &"timeout": timeouts += 1
			for k in 2:
				var f: Fighter = tr.sim.active_fighter(k)
				dmg[k] += float(f.record["damage_dealt"])
				surge[k] += float(f.record["surge_gained"])
				spent[k] += float(f.record["surge_spent"])
				rams[k] += float(f.record["dash_throughs"])
				for a in (f.record["ability_usage"] as Dictionary).keys():
					var u: Dictionary = f.record["ability_usage"][a]
					var key := "%d:%s" % [k, a]
					if not usage.has(key): usage[key] = [0, 0]
					usage[key][0] += int(u["uses"]); usage[key][1] += int(u["hits"])
		var acc := []
		for k in usage.keys():
			acc.append("%s %d/%d" % [k, usage[k][1], usage[k][0]])
		print("%s(%s) vs %s(%s): wins %s  avg %.1fs  timeouts %d  avgdmg %.0f/%.0f" % [pair[0].id, pair[2], pair[1].id, pair[3], wins, float(total_ticks) / n / 60.0, timeouts, dmg[0]/n, dmg[1]/n])
		print("   surge gained %.0f/%.0f  stages spent %.1f/%.1f  rams %.1f/%.1f (per match)" % [surge[0]/n, surge[1]/n, spent[0]/n, spent[1]/n, rams[0]/n, rams[1]/n])
		print("   hits/uses: ", ", ".join(acc))
	quit()
