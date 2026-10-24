class_name DashSystem
extends RefCounted
## Four-direction dash, dash-through stuns, clashes, guard repels and safe
## landing placement.
##
## Dash phases: DASH_START (startup) -> DASH_ACTIVE (constant speed, swept
## collision) -> DASH_RECOVERY. Stamina is paid when the dash starts.

const SM := FighterSM.State
const STOPPED := 1
const CONTINUE := 0


static func try_start(sim: BattleSim, f: Fighter, cmd: InputCommand) -> bool:
	var prof := f.stats.dash
	if f.status_flag("prevents_dash"):
		return false
	if not StaminaSystem.can_afford(f, prof.stamina_cost):
		sim.emit(BattleEvent.DASH_NO_STAMINA, f, -1, f.pos, {"need": prof.stamina_cost})
		return false
	var dir := Cardinal.from_input(cmd.move_vector(), cmd.axis_hint, f.cardinal_facing)
	StaminaSystem.spend(f, prof.stamina_cost)
	f.dash_dir = dir
	f.dash_remaining = prof.distance
	f.dash_speed_tick = prof.speed_per_tick()
	f.dash_passed.clear()
	f.dash_extra_recovery = 0
	f.dash_active_tick = 0
	f.vel = Vector2.ZERO
	f.cardinal_facing = dir
	f.facing = dir
	sim.set_state(f, SM.DASH_START, prof.startup_ticks)
	f.record["dashes"] += 1
	sim.emit(BattleEvent.DASH_START, f, -1, f.pos, {"dir": dir, "type": prof.dash_type})
	return true


static func begin_active(sim: BattleSim, f: Fighter) -> void:
	sim.set_state(f, SM.DASH_ACTIVE, 0)
	f.dash_active_tick = 0


static func step_active(sim: BattleSim, f: Fighter) -> void:
	f.dash_active_tick += 1
	var step_len := minf(f.dash_speed_tick, f.dash_remaining)
	var from := f.pos
	var res := sim.geometry.move_until_blocked(from, f.dash_dir * step_len, f.radius())
	var to: Vector2 = res["pos"]
	if _interact_with_bodies(sim, f, from, to) == STOPPED:
		return
	f.pos = to
	f.dash_remaining -= from.distance_to(to)
	if res["hit"]:
		f.dash_remaining = 0.0
	# Safety: never let a dash run more than twice its nominal duration.
	if f.dash_remaining <= 0.001 or f.dash_active_tick > f.stats.dash.duration_ticks * 2 + 30:
		finish(sim, f)


static func finish(sim: BattleSim, f: Fighter) -> void:
	resolve_landing(sim, f)
	f.dash_remaining = 0.0
	var rec := f.stats.dash.recovery_ticks + f.dash_extra_recovery
	sim.set_state(f, SM.DASH_RECOVERY, rec)


## True while the dash ignores projectiles (FAST dash trait).
static func is_projectile_intangible(f: Fighter) -> bool:
	return f.state == SM.DASH_ACTIVE and f.dash_active_tick <= f.stats.dash.projectile_intangible_ticks


static func is_flinch_immune(f: Fighter) -> bool:
	var prof := f.stats.dash
	return prof.flinch_immune_while_active and (f.state == SM.DASH_START or f.state == SM.DASH_ACTIVE)


static func _interact_with_bodies(sim: BattleSim, f: Fighter, from: Vector2, to: Vector2) -> int:
	var prof := f.stats.dash
	for o in sim.on_field_fighters():
		if o == f or o.team == f.team or o.is_ko():
			continue
		if f.dash_passed.has(o.id):
			continue
		var reach := f.radius() + o.radius()
		var t := ArenaGeometry.segment_circle_t(from, to, o.pos, reach)
		if t < 0.0:
			continue
		var contact := from.lerp(to, maxf(0.0, t - 0.02))
		if prof.collision_behavior == DashProfile.CollisionBehavior.STOP_AT_BODY:
			f.pos = contact
			finish(sim, f)
			return STOPPED
		f.dash_passed[o.id] = true
		# Head-on dash clash: both bounce, nobody is stunned.
		if o.state == SM.DASH_ACTIVE and o.dash_dir.dot(f.dash_dir) < -0.5:
			_clash(sim, f, o, contact)
			return STOPPED
		if _repels(o, f):
			_repel(sim, f, o, contact)
			return STOPPED
		_pass_through(sim, f, o, from)
	return CONTINUE


static func _repels(defender: Fighter, dasher: Fighter) -> bool:
	if defender.status_flag("repels_dash_through"):
		return true
	return defender.state == SM.GUARDING and GuardSystem.in_guard_arc(defender, dasher.pos)


static func _clash(sim: BattleSim, a: Fighter, b: Fighter, contact: Vector2) -> void:
	a.pos = contact
	b.dash_passed[a.id] = true
	var n := (a.pos - b.pos).normalized()
	if n == Vector2.ZERO:
		n = -a.dash_dir
	a.dash_remaining = 0.0
	b.dash_remaining = 0.0
	finish(sim, a)
	finish(sim, b)
	MovementSystem.push(a, n, CombatConst.DASH_CLASH_KNOCKBACK)
	MovementSystem.push(b, -n, CombatConst.DASH_CLASH_KNOCKBACK)
	sim.emit(BattleEvent.DASH_CLASH, a, b.id, (a.pos + b.pos) * 0.5, {})


static func _repel(sim: BattleSim, dasher: Fighter, defender: Fighter, contact: Vector2) -> void:
	dasher.pos = contact
	dasher.dash_remaining = 0.0
	var perfect := defender.state == SM.GUARDING and GuardSystem.is_perfect(defender)
	var stun := CombatConst.DASH_REPEL_STUN_TICKS + (9 if perfect else 0)
	if defender.state == SM.GUARDING and not perfect:
		StaminaSystem.spend(defender, CombatConst.GUARD_DASH_REPEL_STAMINA, true)
	StunRules.apply(sim, dasher, stun, &"repel")
	MovementSystem.push(dasher, -dasher.dash_dir, 0.5)
	if perfect:
		defender.record["perfect_guards"] += 1
		sim.emit(BattleEvent.PERFECT_GUARD, defender, dasher.id, contact, {"vs": "dash"})
	sim.emit(BattleEvent.DASH_REPELLED, dasher, defender.id, contact, {"perfect": perfect})


static func _pass_through(sim: BattleSim, f: Fighter, o: Fighter, from: Vector2) -> void:
	var prof := f.stats.dash
	var vulnerable := (
		o.dash_through_immunity <= 0
		and o.state != SM.DASH_ACTIVE
		and o.steadfast <= 0
		and not o.status_flag("stun_immune")
	)
	var applied := 0
	if vulnerable:
		var mult := f.stats.passive.dash_through_stun_mult if f.stats.passive else 1.0
		applied = StunRules.apply(sim, o, int(round(prof.dash_through_stun_ticks * mult)), &"dash")
		o.dash_through_immunity = CombatConst.DASH_THROUGH_IMMUNITY_TICKS
		if applied > 0:
			f.record["dash_throughs"] += 1
	# Land about one logical cell beyond the opponent (or keep the full dash
	# if it already goes further).
	var reach := f.radius() + o.radius()
	var landing := maxf(CombatConst.CELL_SIZE * CombatConst.DASH_THROUGH_LANDING_CELLS, reach + 0.1)
	var along := (o.pos - from).dot(f.dash_dir)
	f.dash_remaining = maxf(f.dash_remaining, along + landing)
	if applied > 0:
		# The stun gives positional advantage, never a guaranteed follow-up:
		# extend recovery so the victim always gets control back first.
		var remaining_ticks := int(ceil(maxf(0.0, f.dash_remaining - f.dash_speed_tick) / f.dash_speed_tick))
		var earliest := remaining_ticks + prof.recovery_ticks
		var needed := applied + CombatConst.DASH_THROUGH_FOLLOWUP_MARGIN_TICKS
		f.dash_extra_recovery = maxi(f.dash_extra_recovery, needed - earliest)
	sim.emit(BattleEvent.DASH_THROUGH, f, o.id, o.pos, {"stunned": applied > 0, "immune": not vulnerable, "stun_ticks": applied})


## Make sure a finished dash never leaves the creature inside an opponent
## or a wall. Candidates are tried around the opponent (preferring the travel
## direction); a candidate is only accepted if it is free and reachable in a
## straight line without crossing an obstacle.
static func resolve_landing(sim: BattleSim, f: Fighter) -> void:
	for o in sim.on_field_fighters():
		if o == f or o.is_ko():
			continue
		var reach := f.radius() + o.radius()
		if f.pos.distance_to(o.pos) >= reach - 0.001:
			continue
		var base := f.dash_dir if f.dash_dir != Vector2.ZERO else (f.pos - o.pos).normalized()
		if base == Vector2.ZERO:
			base = Vector2.RIGHT
		var placed := false
		for deg in [0, 25, -25, 50, -50, 75, -75, 90, -90, 115, -115, 140, -140, 165, -165, 180]:
			var dir: Vector2 = base.rotated(deg_to_rad(deg))
			var candidate: Vector2 = o.pos + dir * (reach + 0.02)
			if not sim.geometry.is_circle_free(candidate, f.radius()):
				continue
			if _overlaps_any_body(sim, f, candidate):
				continue
			if sim.geometry.sweep(f.pos, candidate - f.pos, f.radius()).hit:
				continue
			f.pos = candidate
			placed = true
			break
		if not placed:
			f.pos = sim.geometry.push_out(o.pos - base * (reach + 0.02), f.radius())


static func _overlaps_any_body(sim: BattleSim, f: Fighter, p: Vector2) -> bool:
	for o in sim.on_field_fighters():
		if o == f or o.is_ko():
			continue
		if p.distance_to(o.pos) < f.radius() + o.radius():
			return true
	return false
