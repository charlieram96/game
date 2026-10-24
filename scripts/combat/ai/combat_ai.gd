class_name CombatAI
extends InputSource
## Opponent AI. It plays by the same rules as a human: it only emits
## InputCommands, sees its opponent through a reaction-time delay, aims with
## error, and must manage stamina with Focus.
##
## Each tick: perceive (delayed) -> react to threats (dodge / guard / step
## out) -> manage stamina -> pick an offensive option by utility -> move to
## keep its preferred range (kite vs brawl, by archetype).

const SM := FighterSM.State

var profile: AIProfile
var rng := RandomNumberGenerator.new()

var _seed := 7
var _history: Array[Dictionary] = []
var _next_decision := 0
var _strafe_sign := 1.0
var _strafe_flip_tick := 0
var _focusing := false
var _guard_until := -1
var _guard_aim := Vector2.ZERO
var _reactions: Dictionary = {}  # threat id -> chosen reaction
var _prev_held := 0
var _pending_press := 0
var _pending_move := -1
var _pending_aim := Vector2.ZERO
var _pending_aim_dist := 0.0
var _hold_attack_until := -1


func _init(p_profile: AIProfile = null, seed_value: int = 7) -> void:
	profile = p_profile if p_profile else AIProfile.preset(&"normal")
	_seed = seed_value
	rng.seed = seed_value


func reset() -> void:
	rng.seed = _seed
	_history.clear()
	_next_decision = 0
	_focusing = false
	_guard_until = -1
	_reactions.clear()
	_prev_held = 0
	_pending_press = 0
	_hold_attack_until = -1


func get_command(sim: BattleSim, team: int) -> InputCommand:
	var cmd := InputCommand.new()
	var me := sim.active_fighter(team)
	var foe := sim.active_fighter(1 - team)
	if me == null or foe == null or me.is_ko() or foe.is_ko() or sim.phase != BattleSim.Phase.FIGHT:
		_prev_held = 0
		return cmd
	_remember(sim, foe)
	var seen := _perceived(foe)
	var held := 0
	var press := 0
	var move := Vector2.ZERO
	var aim := (seen["pos"] - me.pos) as Vector2
	var aim_dist := aim.length()
	aim = aim.normalized() if aim_dist > 0.01 else me.facing
	var threat := _assess_threat(sim, me, foe)

	# --- Stunned: buffer a wake-up option -----------------------------------
	if me.state == SM.STUNNED:
		var left := me.state_duration - me.state_tick
		if left <= 5 and not threat.is_empty() and rng.randf() < profile.guard_chance:
			press |= InputCommand.GUARD
			held |= InputCommand.GUARD
		return _finish(cmd, -1, aim, aim_dist, held, press)

	# --- Guard currently held ---------------------------------------------------
	if sim.tick < _guard_until:
		held |= InputCommand.GUARD
		var g_aim := _guard_aim if _guard_aim != Vector2.ZERO else aim
		return _finish(cmd, -1, g_aim, 2.0, held, 0)

	# --- Threat reaction ----------------------------------------------------------
	if not threat.is_empty() and (FighterSM.is_actionable(me.state) or FighterSM.is_focusing(me.state)):
		var tid: int = threat["id"]
		if not _reactions.has(tid):
			_reactions[tid] = _choose_reaction(me, threat)
		var reaction: StringName = _reactions[tid]
		match reaction:
			&"dash":
				_focusing = false
				var d := _escape_cardinal(sim, me, threat)
				_reactions[tid] = &"done"
				return _finish(cmd, CombatConst.vec_to_dir8(d, 0.1), aim, aim_dist, InputCommand.DASH, InputCommand.DASH)
			&"guard":
				_focusing = false
				_guard_until = sim.tick + clampi(int(threat["ticks"]) + 10, 8, 40)
				_guard_aim = ((threat["source"] as Vector2) - me.pos).normalized()
				_reactions[tid] = &"done"
				return _finish(cmd, -1, _guard_aim, 2.0, InputCommand.GUARD, InputCommand.GUARD)
			&"walk":
				_focusing = false
				move = _escape_walk(sim, me, threat)
				return _finish(cmd, CombatConst.vec_to_dir8(move, 0.1), aim, aim_dist, 0, 0)
			_:
				pass

	# --- Focus / stamina management ------------------------------------------------
	var dist := me.pos.distance_to(seen["pos"])
	var vulnerable := _is_vulnerable(seen["state"])
	if _focusing:
		var done := me.stamina >= me.max_stamina() * 0.88
		var danger := not threat.is_empty() or dist < 2.6
		if done or danger:
			_focusing = false
		else:
			return _finish(cmd, -1, aim, aim_dist, InputCommand.FOCUS, 0)
	elif FighterSM.is_actionable(me.state) and me.stamina_ratio() < profile.focus_threshold and threat.is_empty():
		if dist > 4.5 or (vulnerable and seen["state"] != SM.FOCUSING):
			_focusing = true
			return _finish(cmd, -1, aim, aim_dist, InputCommand.FOCUS, InputCommand.FOCUS)

	# --- Continue a basic string -------------------------------------------------
	if sim.tick < _hold_attack_until and FighterSM.is_attacking(me.state):
		held |= InputCommand.ATTACK

	# --- Offense ----------------------------------------------------------------------
	if FighterSM.is_actionable(me.state) and sim.tick >= _next_decision:
		_next_decision = sim.tick + maxi(1, profile.decision_interval + rng.randi_range(-1, 2))
		var choice := _choose_offense(sim, me, foe, seen, dist, vulnerable)
		if not choice.is_empty():
			var kind: StringName = choice["kind"]
			if kind == &"dash_through":
				return _finish(cmd, CombatConst.vec_to_dir8(choice["dir"], 0.1), aim, aim_dist, InputCommand.DASH, InputCommand.DASH)
			var bit: int = choice["bit"]
			var a: Array = choice["aim"]
			if bit == InputCommand.ATTACK and rng.randf() < profile.combo_skill:
				_hold_attack_until = sim.tick + 50
			return _finish(cmd, -1, a[0], a[1], held | bit, bit)

	# --- Movement --------------------------------------------------------------------
	if FighterSM.is_actionable(me.state) or me.state == SM.ATTACK_RECOVERY:
		move = _movement(sim, me, seen, dist)
	return _finish(cmd, CombatConst.vec_to_dir8(move, 0.15), aim, aim_dist, held, press)


func _finish(cmd: InputCommand, move_dir: int, aim: Vector2, aim_dist: float, held: int, press: int) -> InputCommand:
	cmd.move_dir = move_dir
	if aim != Vector2.ZERO:
		var err := deg_to_rad(rng.randfn(0.0, profile.aim_error_deg * 0.35))
		cmd.set_aim(aim.rotated(err), aim_dist)
	cmd.held = held
	cmd.pressed = InputCommand.edges(_prev_held, held) | press
	_prev_held = held
	return cmd


# --- Perception -----------------------------------------------------------------

func _remember(sim: BattleSim, foe: Fighter) -> void:
	_history.append({
		"tick": sim.tick,
		"pos": foe.pos,
		"vel": foe.vel,
		"state": foe.state,
		"guarding": foe.state == SM.GUARDING,
		"facing": foe.facing,
	})
	var keep := profile.reaction_ticks + 2
	while _history.size() > keep:
		_history.pop_front()


func _perceived(foe: Fighter) -> Dictionary:
	if _history.is_empty():
		return {"pos": foe.pos, "vel": foe.vel, "state": foe.state, "guarding": false, "facing": foe.facing}
	var idx := maxi(0, _history.size() - 1 - profile.reaction_ticks)
	return _history[idx]


func _is_vulnerable(state: int) -> bool:
	return state in [SM.FOCUS_ENTER, SM.FOCUSING, SM.FOCUS_EXIT, SM.STUNNED, SM.ATTACK_RECOVERY, SM.DASH_RECOVERY]


func _assess_threat(sim: BattleSim, me: Fighter, foe: Fighter) -> Dictionary:
	var best := {}
	var best_ticks := 1e9
	var react := profile.reaction_ticks
	for v in sim.volumes:
		if v.dead or v.team == me.team:
			continue
		var t := {}
		if v.is_projectile():
			if v.age < react / 2:
				continue
			var spd2 := v.velocity.length_squared()
			if spd2 < 0.01:
				continue
			var rel := me.pos - v.pos
			var tsec := rel.dot(v.velocity) / spd2
			if tsec < 0.0 or tsec > 0.75:
				continue
			var closest := v.pos + v.velocity * tsec
			if closest.distance_to(me.pos) < me.hurt_radius() + v.radius + 0.35:
				t = {"kind": &"projectile", "ticks": tsec * 60.0, "dir": v.velocity.normalized(), "source": v.pos, "guardable": v.hit.guardable}
		elif v.motion == HitVolume.Motion.STATIC and v.delay_ticks > 0 and v.age < v.delay_ticks:
			if v.age < react:
				continue
			if me.pos.distance_to(v.pos) < v.radius + me.hurt_radius() + 0.35:
				t = {"kind": &"area", "ticks": float(v.delay_ticks - v.age), "center": v.pos, "radius": v.radius, "source": v.pos, "guardable": v.hit.guardable}
		elif v.motion == HitVolume.Motion.WAVE and v.age < v.delay_ticks + 4:
			if v.age < react:
				continue
			var local := me.pos - v.origin
			var along := local.dot(v.dir)
			var side := local.dot(CombatConst.perpendicular(v.dir))
			if along > -0.6 and along < v.wave_total + 0.6 and absf(side) < v.width * 0.5 + me.hurt_radius() + 0.35:
				t = {"kind": &"line", "ticks": float(v.delay_ticks - v.age) + along / maxf(1.0, v.wave_speed) * 60.0, "dir": v.dir, "side": signf(side) if side != 0.0 else 1.0, "source": v.origin, "guardable": v.hit.guardable}
		if not t.is_empty() and float(t["ticks"]) < best_ticks:
			t["id"] = v.id
			best = t
			best_ticks = float(t["ticks"])
	# Wind-ups the AI can see coming (after its reaction delay).
	if foe.current_ability and foe.state == SM.ATTACK_START and foe.state_tick >= react / 3:
		var ab := foe.current_ability
		var d := me.pos.distance_to(foe.pos)
		for c in ab.components:
			var reach := 0.0
			if c is SelfAreaComponent:
				reach = (c as SelfAreaComponent).radius
			elif c is MeleeComponent:
				var m := c as MeleeComponent
				reach = m.forward_offset + m.radius
			elif c is LungeComponent:
				reach = (c as LungeComponent).distance + 1.0
			if reach > 0.0 and d < reach + me.hurt_radius() + 0.3:
				var ticks := float(foe.state_duration - foe.state_tick)
				if ticks < best_ticks:
					best = {"kind": &"melee", "ticks": ticks, "center": foe.pos, "radius": reach, "source": foe.pos, "guardable": true, "id": -1000000 - foe.id * 1000 - (sim.tick - foe.state_tick) % 1000}
					best_ticks = ticks
	return best


# --- Reactions --------------------------------------------------------------------

func _choose_reaction(me: Fighter, threat: Dictionary) -> StringName:
	if rng.randf() < profile.mistake_chance:
		return &"none"
	var can_dash := StaminaSystem.can_afford(me, me.stats.dash.stamina_cost) and me.stats.dash.distance > 0.0
	if can_dash and rng.randf() < profile.dodge_chance:
		return &"dash"
	if bool(threat.get("guardable", true)) and rng.randf() < profile.guard_chance and me.stamina > 8.0:
		return &"guard"
	if float(threat["ticks"]) > 14.0:
		return &"walk"
	return &"none"


func _escape_cardinal(sim: BattleSim, me: Fighter, threat: Dictionary) -> Vector2:
	var options: Array[Vector2] = []
	match threat["kind"]:
		&"projectile", &"line":
			var d: Vector2 = threat["dir"]
			var p := Cardinal.snap(CombatConst.perpendicular(d))
			options = [p, -p]
			if threat.has("side"):
				options = [p * float(threat["side"]), -p * float(threat["side"])]
		_:
			var away: Vector2 = me.pos - (threat.get("center", me.pos) as Vector2)
			if away.length_squared() < 0.01:
				away = -me.facing
			var a := Cardinal.snap(away)
			options = [a, Cardinal.snap(CombatConst.perpendicular(a)), -Cardinal.snap(CombatConst.perpendicular(a))]
	var dist := me.stats.dash.distance
	for o in options:
		var target := me.pos + o * dist
		if sim.geometry.is_circle_free(target, me.radius()):
			return o
	return options[0]


func _escape_walk(sim: BattleSim, me: Fighter, threat: Dictionary) -> Vector2:
	var dir: Vector2
	match threat["kind"]:
		&"projectile", &"line":
			dir = CombatConst.perpendicular(threat["dir"])
			if threat.has("side"):
				dir *= float(threat["side"])
		_:
			dir = (me.pos - (threat.get("center", me.pos) as Vector2)).normalized()
	return _avoid_walls(sim, me, dir)


# --- Offense -------------------------------------------------------------------------

func _choose_offense(sim: BattleSim, me: Fighter, foe: Fighter, seen: Dictionary, dist: float, vulnerable: bool) -> Dictionary:
	var best := {}
	var best_score := 0.42 * profile.patience
	# Specials and basic attack
	for slot in range(-1, 4):
		var ability := me.ability_in_slot(slot)
		if ability == null or AbilitySystem.check_usable(me, ability) != &"":
			continue
		var score := _score_ability(sim, me, seen, ability, dist, vulnerable)
		if score <= 0.0:
			continue
		score *= lerpf(0.7, 1.15, profile.aggression)
		score += rng.randf_range(-0.12, 0.12)
		if score > best_score:
			best_score = score
			var bit: int = InputCommand.ATTACK if slot < 0 else InputCommand.ABILITY_BITS[slot]
			best = {"kind": &"ability", "bit": bit, "aim": _aim_for(me, seen, ability)}
	# Dash-through opportunity
	var dt := _dash_through_option(sim, me, foe, seen)
	if not dt.is_empty():
		var s := 0.55 + profile.dash_through_chance * 0.5 + rng.randf_range(-0.1, 0.1)
		if vulnerable:
			s += 0.15
		if s > best_score and rng.randf() < profile.dash_through_chance + 0.2:
			best = dt
	return best


func _score_ability(sim: BattleSim, me: Fighter, seen: Dictionary, ability: AbilityDefinition, dist: float, vulnerable: bool) -> float:
	var foe_r := 0.5
	var score := 0.0
	var lunge_reach := 0.0
	for c in ability.components:
		if c is LungeComponent:
			lunge_reach = (c as LungeComponent).distance
	for c in ability.components:
		if c is ProjectileComponent:
			var p := c as ProjectileComponent
			if dist > 1.6 and dist < p.max_range * 0.92 and _line_clear(sim, me.pos, seen["pos"], p.radius):
				score = maxf(score, 0.62 - dist * 0.012)
		elif c is MeleeComponent:
			var m := c as MeleeComponent
			var reach := m.forward_offset + m.radius + foe_r + lunge_reach
			if dist < reach * 0.92 and (lunge_reach == 0.0 or dist > 1.0):
				score = maxf(score, 0.85 if ability.kind == AbilityDefinition.Kind.BASIC else 0.8)
		elif c is TargetedAreaComponent:
			if dist < ability.max_range:
				score = maxf(score, 0.42 + (0.4 if vulnerable or _is_slowed(sim, me) else 0.0))
		elif c is SelfAreaComponent:
			if dist < (c as SelfAreaComponent).radius + foe_r - 0.25:
				score = maxf(score, 0.9)
		elif c is LineWaveComponent:
			var w := c as LineWaveComponent
			if dist > 1.4 and dist < w.length * 0.88:
				score = maxf(score, 0.45 + (0.35 if vulnerable else 0.0))
		elif c is SelfStatusComponent:
			# Defensive buff: use when something is coming or the foe is in our face.
			var foe := sim.opponent_of(me)
			var close := dist < 2.2 and foe and FighterSM.is_attacking(foe.state)
			var incoming := false
			for v in sim.volumes:
				if v.team != me.team and not v.dead and v.pos.distance_to(me.pos) < 3.5:
					incoming = true
			if close or incoming:
				score = maxf(score, 0.88)
	if vulnerable and score > 0.0:
		score += 0.15
	return score


func _aim_for(me: Fighter, seen: Dictionary, ability: AbilityDefinition) -> Array:
	var target: Vector2 = seen["pos"]
	var vel: Vector2 = seen["vel"]
	var lead_t := 0.0
	for c in ability.components:
		if c is ProjectileComponent:
			lead_t = me.pos.distance_to(target) / maxf(1.0, (c as ProjectileComponent).speed)
		elif c is TargetedAreaComponent:
			lead_t = float(ability.startup_ticks + (c as TargetedAreaComponent).delay_ticks) / 60.0 * 0.5
		elif c is LineWaveComponent:
			var w := c as LineWaveComponent
			lead_t = float(ability.startup_ticks + w.telegraph_ticks) / 60.0 * 0.4
	target += vel * lead_t * profile.lead_accuracy
	var to := target - me.pos
	if to.length() < 0.01:
		to = me.facing
	return [to.normalized(), to.length()]


func _dash_through_option(sim: BattleSim, me: Fighter, foe: Fighter, seen: Dictionary) -> Dictionary:
	var prof := me.stats.dash
	if prof.distance <= 0.0 or not StaminaSystem.can_afford(me, prof.stamina_cost + 10.0):
		return {}
	if foe.dash_through_immunity > 0 or foe.steadfast > 0:
		return {}
	var to: Vector2 = (seen["pos"] as Vector2) - me.pos
	var card := Cardinal.snap(to)
	var along := to.dot(card)
	var side := absf(to.dot(CombatConst.perpendicular(card)))
	if along < 0.5 or along > prof.distance + 0.4:
		return {}
	if side > me.radius() + foe.radius() - 0.15:
		return {}
	# Don't dash into a guard facing us.
	if bool(seen["guarding"]) and (seen["facing"] as Vector2).dot(-card) > 0.0:
		return {}
	return {"kind": &"dash_through", "dir": card}


# --- Movement --------------------------------------------------------------------------

func _style(me: Fighter) -> Vector2:
	if me.stamina_ratio() < profile.focus_threshold:
		return Vector2(5.0, 7.5)  # back off to make room to Focus
	match me.species.archetype:
		"Agile":
			return Vector2(3.2, 5.6)
		"Heavy":
			return Vector2(0.0, 1.8)
	return Vector2(1.5, 4.0)


func _movement(sim: BattleSim, me: Fighter, seen: Dictionary, dist: float) -> Vector2:
	if sim.tick >= _strafe_flip_tick:
		_strafe_sign = -_strafe_sign if rng.randf() < 0.6 else _strafe_sign
		_strafe_flip_tick = sim.tick + rng.randi_range(45, 120)
	var band := _style(me)
	var to: Vector2 = (seen["pos"] as Vector2) - me.pos
	var n := to.normalized() if to.length() > 0.01 else me.facing
	var perp := CombatConst.perpendicular(n) * _strafe_sign
	var desired: Vector2
	if dist > band.y:
		desired = n + perp * 0.35
	elif dist < band.x:
		desired = -n + perp * 0.5
	else:
		desired = perp + n * 0.2 * signf(dist - (band.x + band.y) * 0.5)
	return _avoid_walls(sim, me, desired.normalized())


func _avoid_walls(sim: BattleSim, me: Fighter, dir: Vector2) -> Vector2:
	if dir == Vector2.ZERO:
		return dir
	var probe := 1.2
	for step in [0, 45, -45, 90, -90, 135, -135]:
		var d: Vector2 = dir.rotated(deg_to_rad(step))
		var s := sim.geometry.sweep(me.pos, d * probe, me.radius())
		if not s.hit:
			if step != 0 and absf(step) >= 90:
				_strafe_sign = -_strafe_sign
			return d
	# Cornered: head for the arena center.
	return (sim.geometry.bounds.get_center() - me.pos).normalized()


func _line_clear(sim: BattleSim, from: Vector2, to: Vector2, radius: float) -> bool:
	var s := sim.geometry.sweep(from, to - from, radius, true)
	return not s.hit or s.t > 0.97


func _is_slowed(sim: BattleSim, me: Fighter) -> bool:
	var foe := sim.opponent_of(me)
	return foe != null and foe.status_mult("move_speed_mult") < 0.99
