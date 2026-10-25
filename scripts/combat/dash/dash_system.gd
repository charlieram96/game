class_name DashSystem
extends RefCounted
## Drag-dash movement. Creatures don't walk in battle: every move is a dash
## straight along a board direction, a chosen number of cells, landing on a
## cell centre (the arena is a board of 1-unit cells).
##
##   windup (DASH_START)   the creature gathers onto the centre of its cell
##   travel (DASH_ACTIVE)  eased out: explosive start, braking finish
##   recovery              a chained dash may start after chain_after_ticks
##
## Stamina pays base + per-cell when the dash starts. Walls and stones cut a
## dash short; passing through a foe rams it (damage, a short daze and a
## shared impact freeze, then one second of ram protection); head-on dashes
## clash; a guard facing the dasher repels it. plan() is pure, so the aiming
## preview shows exactly what the simulation will do.

const SM := FighterSM.State
const STOPPED := 1
const CONTINUE := 0
const NO_CELL := Vector2i(-9999, -9999)


# --- Planning ----------------------------------------------------------------------

## `from` overrides where the dash starts (the preview plans a dash queued
## mid-dash from the landing point); by default it is the creature's position.
static func plan(sim: BattleSim, f: Fighter, dir_index: int, cells: int, from: Vector2 = Vector2.INF) -> DashPlan:
	var p := DashPlan.new()
	var prof := f.stats.dash
	if dir_index < 0 or dir_index >= Cardinal.DIRS.size() or prof.max_cells <= 0 or cells <= 0:
		return p
	var arena := sim.setup.arena
	p.dir_index = dir_index
	p.dir = Cardinal.from_index(dir_index)
	p.cells_requested = clampi(cells, 1, max_cells(f))
	p.home_cell = home_cell(sim, f, f.pos if from == Vector2.INF else from)
	p.home = arena.cell_center(p.home_cell)
	var step := Vector2i(int(p.dir.x), int(p.dir.y))
	var prev := p.home
	var last := 0
	for k in range(1, p.cells_requested + 1):
		var c := p.home_cell + step * k
		if not _cell_open(sim, f, prev, c):
			p.blocked = true
			p.blocked_cell = c
			break
		p.path.append(c)
		prev = arena.cell_center(c)
		last = k
	# A foe standing on the landing cell: the ram carries us one cell past
	# it, or, if that cell is closed, we stop on the cell before it.
	var paid := last
	if last > 0 and _foe_at(sim, f, arena.cell_center(p.home_cell + step * last)) != null:
		var beyond := p.home_cell + step * (last + 1)
		if _cell_open(sim, f, arena.cell_center(p.home_cell + step * last), beyond) and _foe_at(sim, f, arena.cell_center(beyond)) == null:
			p.path.append(beyond)
			last += 1
			p.extended = true
		else:
			p.path.pop_back()
			last -= 1
			paid = last
	if last <= 0:
		p.result = DashPlan.Result.BLOCKED
		p.target_cell = p.home_cell
		p.target = p.home
		return p
	p.cells = last
	p.target_cell = p.home_cell + step * last
	p.target = arena.cell_center(p.target_cell)
	p.cost = prof.cost_for(paid)
	p.travel_ticks = int(ceil(prof.travel_ticks_for(p.home.distance_to(p.target)) / speed_mult(f)))
	for o in sim.on_field_fighters():
		if o == f or o.team == f.team or o.is_ko():
			continue
		if ArenaGeometry.segment_circle_t(p.home, p.target, o.pos, f.radius() + o.radius()) >= 0.0:
			p.crosses.append(o.id)
			if _rammable(o):
				p.rams.append(o.id)
	p.result = DashPlan.Result.OK if StaminaSystem.can_afford(f, p.cost) else DashPlan.Result.NO_STAMINA
	return p


## Longest dash right now: slowing statuses (Slow, Stone Guard) shorten it.
static func max_cells(f: Fighter) -> int:
	var slow := clampf(f.status_mult("move_speed_mult"), 0.2, 1.0)
	return maxi(1, int(floor(f.stats.dash.max_cells * slow + 0.001)))


## Travel speed factor: slowing statuses stretch the travel time; the
## Quickfoot passive speeds it up while stamina is low.
static func speed_mult(f: Fighter) -> float:
	var mult := clampf(f.status_mult("move_speed_mult"), 0.2, 1.0)
	var bonus := f.stats.passive.low_stamina_speed_bonus if f.stats.passive else 0.0
	if bonus > 0.0 and f.stamina_ratio() < 0.3:
		mult *= 1.0 + bonus
	return mult


## The cell a dash from `at` starts from: the one containing it, or the
## nearest open neighbour when knockback left the creature in a stone's cell.
static func home_cell(sim: BattleSim, f: Fighter, at: Vector2) -> Vector2i:
	var arena := sim.setup.arena
	var n := arena.cell_count()
	var c := arena.cell_of(at)
	c = Vector2i(clampi(c.x, 0, n.x - 1), clampi(c.y, 0, n.y - 1))
	if _reachable(sim, f, at, c):
		return c
	var best := c
	var best_d := INF
	for dy in [-1, 0, 1]:
		for dx in [-1, 0, 1]:
			var cc := c + Vector2i(dx, dy)
			if cc == c or not arena.has_cell(cc) or not _reachable(sim, f, at, cc):
				continue
			var d := at.distance_squared_to(arena.cell_center(cc))
			if d < best_d:
				best_d = d
				best = cc
	return best


static func _reachable(sim: BattleSim, f: Fighter, from: Vector2, c: Vector2i) -> bool:
	var center := sim.setup.arena.cell_center(c)
	return sim.geometry.is_circle_free(center, f.radius()) and not sim.geometry.sweep(from, center - from, f.radius()).hit


static func _cell_open(sim: BattleSim, f: Fighter, from: Vector2, c: Vector2i) -> bool:
	return sim.setup.arena.has_cell(c) and _reachable(sim, f, from, c)


static func _foe_at(sim: BattleSim, f: Fighter, p: Vector2) -> Fighter:
	for o in sim.on_field_fighters():
		if o != f and o.team != f.team and not o.is_ko() and o.pos.distance_to(p) < f.radius() + o.radius() - 0.01:
			return o
	return null


static func _rammable(o: Fighter) -> bool:
	return o.dash_through_immunity <= 0 and o.state != SM.DASH_ACTIVE and o.steadfast <= 0 and not o.status_flag("stun_immune")


# --- Execution ---------------------------------------------------------------------

static func try_start(sim: BattleSim, f: Fighter, dir_index: int, cells: int) -> bool:
	if f.status_flag("prevents_dash"):
		return false
	var p := plan(sim, f, dir_index, cells)
	match p.result:
		DashPlan.Result.INVALID:
			return false
		DashPlan.Result.BLOCKED:
			sim.emit(BattleEvent.DASH_BLOCKED, f, -1, f.pos, {"dir": p.dir})
			return false
		DashPlan.Result.NO_STAMINA:
			sim.emit(BattleEvent.DASH_NO_STAMINA, f, -1, f.pos, {"need": p.cost})
			return false
	var prof := f.stats.dash
	StaminaSystem.spend(f, p.cost)
	f.dash_dir = p.dir
	f.dash_from = f.pos
	f.dash_home = p.home
	f.dash_to = p.target
	f.dash_cells = p.cells
	f.dash_travel_ticks = p.travel_ticks
	f.dash_t = 0
	f.dash_passed.clear()
	f.dash_extra_recovery = 0
	f.dash_active_tick = 0
	f.vel = Vector2.ZERO
	# The dash takes over from any knockback still sliding the creature.
	f.knockback_ticks = 0
	f.knockback_vel = Vector2.ZERO
	f.facing = p.dir
	f.cardinal_facing = p.dir
	sim.set_state(f, SM.DASH_START, maxi(1, prof.startup_ticks))
	f.record["dashes"] += 1
	sim.emit(BattleEvent.DASH_START, f, -1, f.pos, {
		"dir": p.dir, "cells": p.cells, "from": p.home, "to": p.target,
		"windup": prof.startup_ticks, "travel": p.travel_ticks, "type": prof.dash_type, "extended": p.extended,
	})
	return true


## Windup: slide onto the home cell's centre while coiling: first across
## the lane, then along it. Each tick moves along one axis only.
static func step_windup(_sim: BattleSim, f: Fighter) -> void:
	var u := clampf(float(f.state_tick) / maxf(1.0, float(f.state_duration)), 0.0, 1.0)
	var across := CombatConst.perpendicular(f.dash_dir)
	var corner := f.dash_from + across * (f.dash_home - f.dash_from).dot(across)
	if absf((f.dash_home - f.pos).dot(across)) > 0.0005:
		f.pos = f.dash_from.lerp(corner, _smooth(minf(1.0, u * 2.0)))
	else:
		f.pos = corner.lerp(f.dash_home, _smooth(clampf(u * 2.0 - 1.0, 0.0, 1.0)))


static func _smooth(u: float) -> float:
	return u * u * (3.0 - 2.0 * u)


static func begin_active(sim: BattleSim, f: Fighter) -> void:
	# Finish lining up on the lane (across only); travel runs along it.
	var across := CombatConst.perpendicular(f.dash_dir)
	f.pos += across * (f.dash_home - f.pos).dot(across)
	sim.set_state(f, SM.DASH_ACTIVE, 0)
	f.dash_active_tick = 0


static func step_active(sim: BattleSim, f: Fighter) -> void:
	f.dash_active_tick += 1
	f.dash_t += 1
	var from := f.pos
	var to := f.dash_home.lerp(f.dash_to, f.stats.dash.travel_fraction(float(f.dash_t) / float(f.dash_travel_ticks)))
	if _interact_with_bodies(sim, f, from, to) == STOPPED:
		return
	f.pos = to
	if f.dash_t >= f.dash_travel_ticks:
		finish(sim, f)


static func finish(sim: BattleSim, f: Fighter) -> void:
	resolve_landing(sim, f)
	var rec := f.stats.dash.recovery_ticks + f.dash_extra_recovery
	sim.set_state(f, SM.DASH_RECOVERY, rec)
	sim.emit(BattleEvent.DASH_LAND, f, -1, f.pos, {"dir": f.dash_dir, "cells": f.dash_cells})


## True when a buffered dash may cut the landing recovery short.
static func can_chain(f: Fighter) -> bool:
	return f.state == SM.DASH_RECOVERY and f.state_tick >= f.stats.dash.chain_after_ticks + f.dash_extra_recovery


## True while the dash ignores projectiles (FAST dash trait): from the
## windup through the first travel ticks.
static func is_projectile_intangible(f: Fighter) -> bool:
	var n := f.stats.dash.projectile_intangible_ticks
	if n <= 0:
		return false
	return f.state == SM.DASH_START or (f.state == SM.DASH_ACTIVE and f.dash_active_tick <= n)


static func is_flinch_immune(f: Fighter) -> bool:
	var prof := f.stats.dash
	return prof.flinch_immune_while_active and (f.state == SM.DASH_START or f.state == SM.DASH_ACTIVE)


# --- Bodies ------------------------------------------------------------------------

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
		# Head-on dash clash: both bounce back, nobody is dazed.
		if o.state == SM.DASH_ACTIVE and o.dash_dir.dot(f.dash_dir) < -0.5:
			_clash(sim, f, o, contact)
			return STOPPED
		if _repels(o, f):
			_repel(sim, f, o, contact)
			return STOPPED
		_pass_through(sim, f, o)
	return CONTINUE


static func _repels(defender: Fighter, dasher: Fighter) -> bool:
	if defender.status_flag("repels_dash_through"):
		return true
	return defender.state == SM.GUARDING and GuardSystem.in_guard_arc(defender, dasher.pos)


## Bounce back toward the centre of the cell the dasher was leaving.
static func _bounce_back(sim: BattleSim, f: Fighter, distance_cap: float) -> void:
	var arena := sim.setup.arena
	var behind := arena.cell_center(arena.cell_of(f.pos - f.dash_dir * 0.5))
	var back := (behind - f.pos).dot(-f.dash_dir)
	MovementSystem.push(f, -f.dash_dir, clampf(back, 0.25, distance_cap))


static func _clash(sim: BattleSim, a: Fighter, b: Fighter, contact: Vector2) -> void:
	a.pos = contact
	b.dash_passed[a.id] = true
	sim.set_state(a, SM.DASH_RECOVERY, a.stats.dash.recovery_ticks)
	sim.set_state(b, SM.DASH_RECOVERY, b.stats.dash.recovery_ticks)
	_bounce_back(sim, a, 1.2)
	_bounce_back(sim, b, 1.2)
	a.hitstop = maxi(a.hitstop, CombatConst.DASH_CLASH_HITSTOP_TICKS)
	b.hitstop = maxi(b.hitstop, CombatConst.DASH_CLASH_HITSTOP_TICKS)
	sim.emit(BattleEvent.DASH_CLASH, a, b.id, (a.pos + b.pos) * 0.5, {"dir": a.dash_dir})


static func _repel(sim: BattleSim, dasher: Fighter, defender: Fighter, contact: Vector2) -> void:
	dasher.pos = contact
	var perfect := defender.state == SM.GUARDING and GuardSystem.is_perfect(defender)
	var stun := CombatConst.DASH_REPEL_STUN_TICKS + (9 if perfect else 0)
	if defender.state == SM.GUARDING and not perfect:
		StaminaSystem.spend(defender, CombatConst.GUARD_DASH_REPEL_STAMINA, true)
	StunRules.apply(sim, dasher, stun, &"repel")
	_bounce_back(sim, dasher, 0.9)
	defender.hitstop = maxi(defender.hitstop, CombatConst.DASH_CLASH_HITSTOP_TICKS)
	if perfect:
		defender.record["perfect_guards"] += 1
		sim.emit(BattleEvent.PERFECT_GUARD, defender, dasher.id, contact, {"vs": "dash"})
	sim.emit(BattleEvent.DASH_REPELLED, dasher, defender.id, contact, {"perfect": perfect, "dir": dasher.dash_dir})


static func _pass_through(sim: BattleSim, f: Fighter, o: Fighter) -> void:
	var prof := f.stats.dash
	var vulnerable := _rammable(o)
	var applied := 0
	var damage := 0.0
	if vulnerable:
		damage = _ram_damage(sim, f, o)
		o.dash_through_immunity = CombatConst.DASH_THROUGH_IMMUNITY_TICKS
		f.record["dash_throughs"] += 1
		if not o.is_ko():
			var mult := f.stats.passive.dash_through_stun_mult if f.stats.passive else 1.0
			applied = StunRules.apply(sim, o, int(round(prof.dash_through_stun_ticks * mult)), &"dash")
		# A shared freeze frame sells the impact.
		f.hitstop = maxi(f.hitstop, CombatConst.RAM_HITSTOP_TICKS)
		o.hitstop = maxi(o.hitstop, CombatConst.RAM_HITSTOP_TICKS)
	if applied > 0:
		# The daze gives position, never a guaranteed follow-up: the dasher's
		# recovery (and its chain window) stretches so the victim acts first.
		var dasher_free := f.hitstop + (f.dash_travel_ticks - f.dash_t) + prof.chain_after_ticks
		var victim_free := o.hitstop + applied + CombatConst.DASH_THROUGH_FOLLOWUP_MARGIN_TICKS
		f.dash_extra_recovery = maxi(f.dash_extra_recovery, victim_free - dasher_free)
	sim.emit(BattleEvent.DASH_THROUGH, f, o.id, o.pos, {
		"stunned": applied > 0, "immune": not vulnerable, "stun_ticks": applied, "damage": damage, "dir": f.dash_dir,
	})


## Ram damage uses the hit formula (power × attack / defense), no element.
static func _ram_damage(sim: BattleSim, f: Fighter, o: Fighter) -> float:
	var power := f.stats.dash.ram_power
	if power <= 0.0:
		return 0.0
	var dmg := power * (f.stats.attack / maxf(1.0, o.stats.defense)) * sim.ruleset.damage_scale
	if sim.is_enemy_side(f.team):
		dmg *= sim.ruleset.enemy_damage_mult
	dmg *= o.status_mult("damage_taken_mult")
	dmg = maxf(CombatConst.MIN_DAMAGE, snappedf(dmg, 0.1))
	o.hp = maxf(0.0, o.hp - dmg)
	o.record["damage_taken"] += dmg
	f.record["damage_dealt"] += dmg
	f.record["hits"] += 1
	var ko := o.hp <= 0.0
	sim.emit(BattleEvent.HIT, f, o.id, o.pos, {
		"damage": dmg, "eff": 1.0, "element": &"", "ability": &"ram", "heavy": true, "ko": ko,
		"armored": false, "sfx": &"", "vfx": &"", "dir": f.dash_dir, "ram": true,
	})
	if ko:
		MovementSystem.push(o, f.dash_dir, 0.8)
		sim.knock_out(o, f)
	else:
		StaminaSystem.interrupt(sim, o)
	return dmg


# --- Landing -----------------------------------------------------------------------

## A dash never leaves the creature inside an opponent or a wall. When the
## landing spot is taken (the foe moved there mid-dash), the nearest open
## cell centre is used: one further along, one back, then to the sides.
static func resolve_landing(sim: BattleSim, f: Fighter) -> void:
	if _overlapping_body(sim, f, f.pos) == null and sim.geometry.is_circle_free(f.pos, f.radius()):
		return
	var arena := sim.setup.arena
	var here := arena.cell_of(f.pos)
	var d := Vector2i(int(f.dash_dir.x), int(f.dash_dir.y)) if f.dash_dir != Vector2.ZERO else Vector2i(1, 0)
	var side := Vector2i(-d.y, d.x)
	for offset in [d, -d, side, -side, d + side, d - side, -d + side, -d - side, d * 2, -d * 2]:
		var c: Vector2i = here + offset
		if not arena.has_cell(c):
			continue
		var center := arena.cell_center(c)
		if not sim.geometry.is_circle_free(center, f.radius()) or _overlapping_body(sim, f, center) != null:
			continue
		if sim.geometry.sweep(f.pos, center - f.pos, f.radius()).hit:
			continue
		f.pos = center
		return
	var o := _overlapping_body(sim, f, f.pos)
	var away := (f.pos - o.pos).normalized() if o and f.pos != o.pos else -f.dash_dir
	f.pos = sim.geometry.push_out(f.pos + away * (f.radius() + (o.radius() if o else 0.0)), f.radius())


static func _overlapping_body(sim: BattleSim, f: Fighter, p: Vector2) -> Fighter:
	for o in sim.on_field_fighters():
		if o == f or o.is_ko():
			continue
		if p.distance_to(o.pos) < f.radius() + o.radius() - 0.001:
			return o
	return null
