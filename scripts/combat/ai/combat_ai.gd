class_name CombatAI
extends InputSource
## Opponent AI. It plays by the same rules as a human: it only emits
## InputCommands, sees its opponent through a reaction-time delay, aims with
## error, and must manage stamina with Focus and Surge for its specials.
## Like the player it cannot walk: every move is a planned dash along a
## board lane, and every attack runs along a row or column.
##
## Each tick: perceive (delayed) -> react to threats (sidestep dash / guard)
## -> manage stamina -> pick an offensive option by utility (abilities or a
## ram through the foe) -> now and then reposition with a dash scored by
## preferred range (kite vs brawl, by archetype), lane danger (cells the foe
## can ram from where it stands), walls and stamina cost.

const SM := FighterSM.State
## Stamina it keeps for dodging when it repositions (share of the maximum).
const RESERVE := 0.25

var profile: AIProfile
var rng := RandomNumberGenerator.new()

var _seed := 7
var _history: Array[Dictionary] = []
var _next_decision := 0
var _next_move := 0
var _focusing := false
var _guard_until := -1
var _guard_aim := Vector2.ZERO
var _reactions: Dictionary = {}  # threat id -> chosen reaction
var _prev_held := 0
var _hold_attack_until := -1
## Surge stages to bank before spending on cheaper specials (re-rolled after
## each special), so it sometimes saves up for its big moves.
var _surge_goal := 1
var _goal_ready_tick := -1
## Last tick it attacked or rammed: the longer it goes without, the more
## risk it takes to line up (see _pressure).
var _last_offense_tick := 0


func _init(p_profile: AIProfile = null, seed_value: int = 7) -> void:
	profile = p_profile if p_profile else AIProfile.preset(&"normal")
	_seed = seed_value
	rng.seed = seed_value


func reset() -> void:
	rng.seed = _seed
	_history.clear()
	_next_decision = 0
	_next_move = 0
	_focusing = false
	_guard_until = -1
	_reactions.clear()
	_prev_held = 0
	_hold_attack_until = -1
	_surge_goal = _roll_surge_goal()
	_goal_ready_tick = -1
	_last_offense_tick = 0


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
		return _finish(cmd, aim, aim_dist, held, press)

	# --- Guard currently held ---------------------------------------------------
	if sim.tick < _guard_until:
		held |= InputCommand.GUARD
		var g_aim := _guard_aim if _guard_aim != Vector2.ZERO else aim
		return _finish(cmd, g_aim, 2.0, held, 0)

	# --- Threat reaction ----------------------------------------------------------
	if not threat.is_empty() and (FighterSM.is_actionable(me.state) or FighterSM.is_focusing(me.state) or DashSystem.can_chain(me)):
		var tid: int = threat["id"]
		if not _reactions.has(tid):
			_reactions[tid] = _choose_reaction(sim, me, threat)
		var reaction: StringName = _reactions[tid]
		match reaction:
			&"dash":
				var dodge := _dodge(sim, me, seen, threat)
				_reactions[tid] = &"done"
				if dodge.x >= 0:
					_focusing = false
					_next_move = sim.tick + _move_gap()
					return _finish(cmd, aim, aim_dist, 0, 0, dodge)
			&"guard":
				_focusing = false
				_guard_until = sim.tick + clampi(int(threat["ticks"]) + 10, 8, 40)
				_guard_aim = ((threat["source"] as Vector2) - me.pos).normalized()
				_reactions[tid] = &"done"
				return _finish(cmd, _guard_aim, 2.0, InputCommand.GUARD, InputCommand.GUARD)

	# --- Focus / stamina management ------------------------------------------------
	var dist := me.pos.distance_to(seen["pos"])
	var vulnerable := _is_vulnerable(seen["state"])
	if _focusing:
		var done := me.stamina >= me.max_stamina() * 0.9
		var danger := not threat.is_empty() or dist < 2.2 or _in_ram_lane(sim, me.pos, foe, seen)
		if done or danger:
			_focusing = false
		else:
			return _finish(cmd, aim, aim_dist, InputCommand.FOCUS, 0)
	elif FighterSM.is_actionable(me.state) and _low_stamina(me) and threat.is_empty():
		# Same danger test as above, so it never starts a Focus it would drop
		# on the next tick (two creatures doing that side by side deadlock).
		# (After a long stand-off it takes the risk of Focusing in a ram lane.)
		var safe := dist >= 2.2 and (_pressure(sim) >= 0.85 or not _in_ram_lane(sim, me.pos, foe, seen))
		var stranded := me.stamina < me.stats.dash.min_cost()  # can't even dash away
		if safe and (dist > 3.5 or stranded or (vulnerable and not FighterSM.is_focusing(seen["state"]))):
			_focusing = true
			return _finish(cmd, aim, aim_dist, InputCommand.FOCUS, InputCommand.FOCUS)

	# --- Continue a basic string -------------------------------------------------
	if sim.tick < _hold_attack_until and FighterSM.is_attacking(me.state):
		held |= InputCommand.ATTACK

	# --- Offense ----------------------------------------------------------------------
	if FighterSM.is_actionable(me.state) and sim.tick >= _next_decision:
		_next_decision = sim.tick + maxi(1, profile.decision_interval + rng.randi_range(-1, 2))
		var choice := _choose_offense(sim, me, foe, seen, vulnerable)
		if not choice.is_empty():
			_last_offense_tick = sim.tick
			if choice["kind"] == &"ram":
				_next_move = sim.tick + _move_gap()
				return _finish(cmd, aim, aim_dist, held, 0, choice["dash"])
			var bit: int = choice["bit"]
			var a: Array = choice["aim"]
			if bit == InputCommand.ATTACK and rng.randf() < profile.combo_skill:
				_hold_attack_until = sim.tick + 50
			return _finish(cmd, a[0], a[1], held | bit, bit)

	# --- Repositioning (a dash, never a walk) ----------------------------------------
	if (FighterSM.is_actionable(me.state) or DashSystem.can_chain(me)) and sim.tick >= _next_move:
		var move := _reposition(sim, me, foe, seen, dist)
		_next_move = sim.tick + _move_gap()
		if move.x >= 0:
			return _finish(cmd, aim, aim_dist, held, press, move)
	return _finish(cmd, aim, aim_dist, held, press)


func _finish(cmd: InputCommand, aim: Vector2, aim_dist: float, held: int, press: int, dash := Vector2i(-1, 0)) -> InputCommand:
	if aim != Vector2.ZERO:
		var err := deg_to_rad(rng.randfn(0.0, profile.aim_error_deg * 0.35))
		cmd.set_aim(aim.rotated(err), aim_dist)
	cmd.held = held
	cmd.pressed = InputCommand.edges(_prev_held, held) | press
	_prev_held = held
	if dash.x >= 0:
		cmd.set_dash(dash.x, dash.y)
	return cmd


## Time to Focus: below the profile's threshold, or unable to reposition
## without dipping into the reserve (otherwise it could stall in between,
## too full to Focus and too empty to move).
func _low_stamina(me: Fighter) -> bool:
	return me.stamina_ratio() < profile.focus_threshold or me.stamina - me.stats.dash.min_cost() < me.max_stamina() * RESERVE


## Ticks between voluntary repositioning dashes.
func _move_gap() -> int:
	return int(round((14.0 + profile.decision_interval * 2.5) * profile.patience)) + rng.randi_range(0, 18)


# --- Perception -----------------------------------------------------------------

func _remember(sim: BattleSim, foe: Fighter) -> void:
	_history.append({
		"tick": sim.tick,
		"pos": foe.pos,
		"vel": (foe.pos - foe.prev_pos) * CombatConst.TICK_RATE,
		"state": foe.state,
		"guarding": foe.state == SM.GUARDING,
		"facing": foe.facing,
		"stamina": foe.stamina,
	})
	var keep := profile.reaction_ticks + 2
	while _history.size() > keep:
		_history.pop_front()


func _perceived(foe: Fighter) -> Dictionary:
	if _history.is_empty():
		return {"pos": foe.pos, "vel": Vector2.ZERO, "state": foe.state, "guarding": false, "facing": foe.facing, "stamina": foe.stamina}
	var idx := maxi(0, _history.size() - 1 - profile.reaction_ticks)
	return _history[idx]


func _is_vulnerable(state: int) -> bool:
	return state in [SM.FOCUS_ENTER, SM.FOCUSING, SM.FOCUS_EXIT, SM.STUNNED, SM.ATTACK_RECOVERY, SM.DASH_RECOVERY]


## True when the foe could ram `p` from where it is seen: same row or column,
## within its dash reach, with stamina for it.
func _in_ram_lane(sim: BattleSim, p: Vector2, foe: Fighter, seen: Dictionary) -> bool:
	var fp: Vector2 = seen["pos"]
	var d := p - fp
	var aligned := absf(d.x) < 0.5 or absf(d.y) < 0.5
	if not aligned:
		return false
	var reach := float(DashSystem.max_cells(foe)) + 0.5
	if d.length() > reach or float(seen["stamina"]) < foe.stats.dash.cost_for(maxi(1, int(round(d.length())))):
		return false
	return not sim.geometry.sweep(fp, d, 0.3).hit


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
	# An incoming ram: the foe is winding up a dash down our lane.
	if foe.state == SM.DASH_START and foe.state_tick >= react / 3:
		var lane := ArenaGeometry.segment_circle_t(foe.dash_home, foe.dash_to, me.pos, foe.radius() + me.radius())
		if lane >= 0.0:
			var ticks2 := float(foe.state_duration - foe.state_tick) + 3.0
			if ticks2 < best_ticks:
				best = {"kind": &"ram", "ticks": ticks2, "dir": foe.dash_dir, "source": foe.pos, "guardable": true, "id": -2000000 - foe.id * 1000 - (sim.tick - foe.state_tick) % 1000}
	return best


# --- Reactions --------------------------------------------------------------------

func _choose_reaction(sim: BattleSim, me: Fighter, threat: Dictionary) -> StringName:
	if rng.randf() < profile.mistake_chance:
		return &"none"
	var can_dash := StaminaSystem.can_afford(me, me.stats.dash.min_cost()) and me.stats.dash.max_cells > 0
	if can_dash and rng.randf() < profile.dodge_chance:
		return &"dash"
	if bool(threat.get("guardable", true)) and rng.randf() < profile.guard_chance and me.stamina > 8.0:
		return &"guard"
	if can_dash and float(threat["ticks"]) > 16.0 and rng.randf() < 0.5:
		return &"dash"
	return &"none"


## The best short dash out of a threat's path (projectile, line, area or ram).
func _dodge(sim: BattleSim, me: Fighter, seen: Dictionary, threat: Dictionary) -> Vector2i:
	var best := Vector2i(-1, 0)
	var best_score := -INF
	for dir in 4:
		for cells in range(1, mini(3, DashSystem.max_cells(me)) + 1):
			var p := DashSystem.plan(sim, me, dir, cells)
			if not p.ok():
				continue
			var score := _escape_score(p.target, me, threat) - p.cost * 0.01 - cells * 0.05
			score += _band_score(me, p.target, seen) * 0.5
			if score > best_score:
				best_score = score
				best = Vector2i(dir, cells)
	return best


func _escape_score(p: Vector2, me: Fighter, threat: Dictionary) -> float:
	match threat["kind"]:
		&"projectile", &"line", &"ram":
			var d: Vector2 = threat["dir"]
			var src: Vector2 = threat["source"]
			var off := absf((p - src).dot(CombatConst.perpendicular(d)))
			return clampf(off / (me.hurt_radius() + 0.8), 0.0, 1.5)
		_:
			var c: Vector2 = threat.get("center", me.pos)
			var r := float(threat.get("radius", 1.5))
			return clampf((p.distance_to(c) - r) / 1.5 + 1.0, 0.0, 1.5)


# --- Offense -------------------------------------------------------------------------

func _choose_offense(sim: BattleSim, me: Fighter, foe: Fighter, seen: Dictionary, vulnerable: bool) -> Dictionary:
	# Saved up too long (the big move never lined up): settle for less.
	if _surge_goal > 1 and SurgeSystem.stages(me) >= _surge_goal:
		if _goal_ready_tick < 0:
			_goal_ready_tick = sim.tick
		elif sim.tick - _goal_ready_tick > 360:
			_surge_goal = 1
	else:
		_goal_ready_tick = -1
	var best := {}
	var best_score := 0.42 * profile.patience
	# Specials and basic attack
	for slot in range(-1, 4):
		var ability := me.ability_in_slot(slot)
		if ability == null or AbilitySystem.check_usable(me, ability) != &"":
			continue
		if _saving_for_more(me, ability) and not vulnerable:
			continue
		var score := _score_ability(sim, me, me.pos, seen["pos"], ability, vulnerable)
		if score <= 0.0:
			continue
		score *= lerpf(0.7, 1.15, profile.aggression)
		score += 0.04 * ability.surge_stages + rng.randf_range(-0.12, 0.12)
		if score > best_score:
			best_score = score
			var bit: int = InputCommand.ATTACK if slot < 0 else InputCommand.ABILITY_BITS[slot]
			best = {"kind": &"ability", "bit": bit, "aim": _aim_for(me, seen, ability), "surge": ability.surge_stages if slot >= 0 else 0}
	# Ram opportunity (the surest way to earn Surge)
	var ram := _ram_option(sim, me, foe, seen)
	if ram.x >= 0:
		var hungry := not _can_shoot(me)
		var s := 0.55 + profile.dash_through_chance * 0.5 + rng.randf_range(-0.1, 0.1)
		if vulnerable:
			s += 0.2
		if hungry:
			s += 0.15
		if s > best_score and rng.randf() < profile.dash_through_chance + (0.45 if hungry else 0.2):
			best = {"kind": &"ram", "dash": ram}
	if int(best.get("surge", 0)) > 0:
		_surge_goal = _roll_surge_goal()
		_goal_ready_tick = -1
	return best


## How many stages to bank before spending: mostly one or two, sometimes
## the whole meter for the biggest move.
func _roll_surge_goal() -> int:
	var r := rng.randf()
	if r < 0.35:
		return 1
	if r < 0.65:
		return 2
	if r < 0.85:
		return 3
	return 4


## Saving up: `_surge_goal` stages stay banked for a move that costs that
## much; a cheaper special may only spend what is above that reserve.
func _saving_for_more(me: Fighter, ability: AbilityDefinition) -> bool:
	var cost := ability.surge_stages
	return cost > 0 and cost < _surge_goal and SurgeSystem.stages(me) - cost < _surge_goal


## Has a ranged special it can pay for and is willing to spend on.
func _can_shoot(me: Fighter) -> bool:
	for slot in 4:
		var ability := me.ability_in_slot(slot)
		if ability == null or AbilitySystem.check_usable(me, ability) != &"" or _saving_for_more(me, ability):
			continue
		for c in ability.components:
			if c is ProjectileComponent or c is LineWaveComponent or c is TargetedAreaComponent:
				return true
	return false


## What using `ability` from `from` on a foe seen at `target` is worth
## (0 = it would miss). Attacks run along the row or column toward the foe,
## so most only connect when it is lined up.
func _score_ability(sim: BattleSim, me: Fighter, from: Vector2, target: Vector2, ability: AbilityDefinition, vulnerable: bool) -> float:
	var foe_r := 0.5
	var to := target - from
	var dist := to.length()
	var lane := Cardinal.snap(to)
	var along := to.dot(lane)
	var off := absf(to.dot(CombatConst.perpendicular(lane)))
	var score := 0.0
	var lunge_reach := 0.0
	for c in ability.components:
		if c is LungeComponent:
			lunge_reach = (c as LungeComponent).distance
	for c in ability.components:
		if c is ProjectileComponent:
			var p := c as ProjectileComponent
			if along > 1.2 and along < p.max_range * 0.92 and off < p.radius + foe_r - 0.1 and _line_clear(sim, from, from + lane * along, p.radius):
				score = maxf(score, 0.62 - along * 0.012)
		elif c is MeleeComponent:
			if (lunge_reach == 0.0 or along > 1.0) and _melee_reaches(c as MeleeComponent, from, lane, target, foe_r * 0.8, lunge_reach):
				score = maxf(score, 0.85 if ability.kind == AbilityDefinition.Kind.BASIC else 0.8)
		elif c is TargetedAreaComponent:
			# It lands on a whole cell down the lane.
			var cells := clampf(roundf(along), 1.0, maxf(1.0, floorf(ability.max_range + 0.001)))
			if along > 0.5 and (from + lane * cells).distance_to(target) < (c as TargetedAreaComponent).radius + foe_r * 0.5:
				score = maxf(score, 0.42 + (0.4 if vulnerable or _is_slowed(sim, me) else 0.0))
		elif c is SelfAreaComponent:
			if dist < (c as SelfAreaComponent).radius + foe_r - 0.25:
				score = maxf(score, 0.9)
		elif c is LineWaveComponent:
			var w := c as LineWaveComponent
			if along > 1.4 and along < w.length * 0.88 and off < w.width * 0.5 + foe_r - 0.15:
				score = maxf(score, 0.45 + (0.35 if vulnerable else 0.0))
		elif c is SelfStatusComponent:
			# Defensive buff: use when something is coming or the foe is in our face.
			var foe := sim.opponent_of(me)
			var close := dist < 2.2 and foe and FighterSM.is_attacking(foe.state)
			var incoming := false
			for v in sim.volumes:
				if v.team != me.team and not v.dead and v.pos.distance_to(from) < 3.5:
					incoming = true
			if close or incoming:
				score = maxf(score, 0.88)
	if vulnerable and score > 0.0:
		score += 0.15
	return score


## Does a swing down `lane` reach a body at `target`? A lunge carries the
## hitbox forward, so the swing is checked along the lunge too.
func _melee_reaches(m: MeleeComponent, from: Vector2, lane: Vector2, target: Vector2, r: float, lunge: float) -> bool:
	var s := 0.0
	while s < lunge:
		if m.reaches(from + lane * s, lane, target, r):
			return true
		s += 0.5
	return m.reaches(from + lane * lunge, lane, target, r)


## The best attack the AI would throw from `from`: ones it can pay for and
## isn't saving Surge on (buffs don't count: they don't care where it stands).
func _strike_value(sim: BattleSim, me: Fighter, from: Vector2, seen: Dictionary) -> float:
	var best := 0.0
	for slot in range(-1, 4):
		var ability := me.ability_in_slot(slot)
		if ability == null or _is_buff(ability) or AbilitySystem.check_usable(me, ability) != &"" or _saving_for_more(me, ability):
			continue
		best = maxf(best, _score_ability(sim, me, from, seen["pos"], ability, false))
	if _ram_lane_from(sim, me, from, seen):
		best = maxf(best, 0.62 if _can_shoot(me) else 0.8)
	return best


## Could it ram the foe from `from`: lined up within dash reach, a clear
## lane, and the foe open to it (geometry only, for scoring landing cells).
func _ram_lane_from(sim: BattleSim, me: Fighter, from: Vector2, seen: Dictionary) -> bool:
	var foe := sim.opponent_of(me)
	if foe == null or me.stats.dash.max_cells <= 0 or foe.dash_through_immunity > 0 or foe.steadfast > 0:
		return false
	var to: Vector2 = (seen["pos"] as Vector2) - from
	var lane := Cardinal.snap(to)
	if absf(to.dot(CombatConst.perpendicular(lane))) > me.radius() + foe.radius() - 0.2:
		return false
	var along := to.dot(lane)
	if along < 0.75 or along > float(DashSystem.max_cells(me)) - 0.25:
		return false
	if bool(seen["guarding"]) and (seen["facing"] as Vector2).dot(-lane) > 0.0:
		return false
	return not sim.geometry.sweep(from, to, 0.3).hit


func _is_buff(ability: AbilityDefinition) -> bool:
	for c in ability.components:
		if c is SelfStatusComponent:
			return true
	return false


## Aim straight down the row or column toward the foe. The distance (for
## targeted areas: which cell) leads a little along that lane.
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
	var to := target - me.pos
	var lane := Cardinal.snap(to) if to.length_squared() > 1e-4 else Cardinal.snap(me.facing)
	# Dashes are short bursts: only lead a little, or we aim past the landing.
	target += vel * minf(lead_t, 0.15) * profile.lead_accuracy
	return [lane, maxf(1.0, (target - me.pos).dot(lane))]


## A dash whose path runs through the foe (it must be rammable and not
## guarding toward us), with stamina left over.
func _ram_option(sim: BattleSim, me: Fighter, foe: Fighter, seen: Dictionary) -> Vector2i:
	if me.stats.dash.max_cells <= 0 or foe.dash_through_immunity > 0 or foe.steadfast > 0:
		return Vector2i(-1, 0)
	var to: Vector2 = (seen["pos"] as Vector2) - me.pos
	var dir := Cardinal.index_of(to)
	var card := Cardinal.from_index(dir)
	if absf(to.dot(CombatConst.perpendicular(card))) > me.radius() + foe.radius() - 0.2:
		return Vector2i(-1, 0)
	var cells := int(ceil(to.dot(card) - 0.25))
	if cells < 1 or cells > DashSystem.max_cells(me):
		return Vector2i(-1, 0)
	# Don't dash into a guard facing us.
	if bool(seen["guarding"]) and (seen["facing"] as Vector2).dot(-card) > 0.0:
		return Vector2i(-1, 0)
	# A foe knocked off-centre can straddle two cells: one more cell may be
	# what carries the dash through it.
	for n in [cells, cells + 1]:
		if n > DashSystem.max_cells(me):
			break
		var p := DashSystem.plan(sim, me, dir, n)
		if p.ok() and p.rams.has(foe.id) and me.stamina - p.cost >= 6.0:
			return Vector2i(dir, n)
	return Vector2i(-1, 0)


# --- Repositioning ----------------------------------------------------------------------

func _style(me: Fighter) -> Vector2:
	if _low_stamina(me):
		return Vector2(4.5, 7.5)  # back off to make room to Focus
	match me.species.archetype:
		"Agile":
			# A kiter needs Surge to shoot with: without it, it hunts for rams
			# (and the odd string) to earn some.
			return Vector2(3.0, 5.5) if _can_shoot(me) else Vector2(2.5, float(DashSystem.max_cells(me)) + 0.4)
		"Heavy":
			return Vector2(0.9, 2.1)
	return Vector2(1.5, 4.0)


## 0 inside the preferred range band, falling linearly with every unit
## outside it (so a far-off creature always wants to close in).
func _band_score(me: Fighter, p: Vector2, seen: Dictionary) -> float:
	var band := _style(me)
	var d := p.distance_to(seen["pos"])
	var outside := maxf(0.0, maxf(band.x - d, d - band.y))
	return -outside * 0.18


## Scores standing still against every legal dash and returns the best dash
## if it beats staying put by a margin.
func _reposition(sim: BattleSim, me: Fighter, foe: Fighter, seen: Dictionary, dist: float) -> Vector2i:
	# Impatience eats into the reserve too, so a long stand-off always ends;
	# and anything goes to get out of a lane the foe can ram.
	var reserve := me.max_stamina() * (0.05 if _low_stamina(me) else RESERVE * (1.0 - _pressure(sim)))
	if _in_ram_lane(sim, me.pos, foe, seen):
		reserve = 0.0
	var stay := _spot_score(sim, me, foe, seen, me.pos)
	var best := Vector2i(-1, 0)
	var best_score := stay + 0.06 + 0.06 * profile.patience
	for dir in 4:
		for cells in range(1, DashSystem.max_cells(me) + 1):
			var p := DashSystem.plan(sim, me, dir, cells)
			if not p.ok() or p.cells != cells:
				continue
			if me.stamina - p.cost < reserve and dist > 2.0:
				continue
			var score := _spot_score(sim, me, foe, seen, p.target)
			score -= p.cost / me.max_stamina() * 0.3
			score += rng.randf_range(-0.08, 0.08) * (1.0 + profile.mistake_chance * 3.0)
			if score > best_score:
				best_score = score
				best = Vector2i(dir, cells)
	return best


func _spot_score(sim: BattleSim, me: Fighter, foe: Fighter, seen: Dictionary, p: Vector2) -> float:
	var score := _band_score(me, p, seen)
	var pressure := _pressure(sim)
	# Lined up to strike (a row or column the foe is on, in range)...
	score += _strike_value(sim, me, p, seen) * (0.45 + 0.35 * pressure)
	# ...which usually means standing in the foe's ram lane too.
	if _in_ram_lane(sim, p, foe, seen):
		score -= 0.45 * (1.15 - profile.aggression * 0.5) * (1.0 - pressure)
	# Room to manoeuvre: edges and corners are traps.
	var b := sim.geometry.bounds
	var edge := minf(minf(p.x - b.position.x, b.end.x - p.x), minf(p.y - b.position.y, b.end.y - p.y))
	if edge < 1.0:
		score -= 0.18
	if edge < 1.0 and minf(p.x - b.position.x, b.end.x - p.x) < 1.0 and minf(p.y - b.position.y, b.end.y - p.y) < 1.0:
		score -= 0.2
	return score


## 0 -> 0.85 as the AI goes 2 to 6 seconds without attacking: impatience
## that breaks stand-offs where lining up looks too risky.
func _pressure(sim: BattleSim) -> float:
	return clampf(float(sim.tick - _last_offense_tick - 120) / 240.0, 0.0, 0.85)


func _line_clear(sim: BattleSim, from: Vector2, to: Vector2, radius: float) -> bool:
	var s := sim.geometry.sweep(from, to - from, radius, true)
	return not s.hit or s.t > 0.97


func _is_slowed(sim: BattleSim, me: Fighter) -> bool:
	var foe := sim.opponent_of(me)
	return foe != null and foe.status_mult("move_speed_mult") < 0.99
