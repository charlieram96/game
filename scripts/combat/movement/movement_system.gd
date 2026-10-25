class_name MovementSystem
extends RefCounted
## Leftover velocity, collision against the arena, body separation and
## knockback. Creatures never walk in battle (see DashSystem): they stand
## their ground unless a dash, a lunge or a hit moves them.

const SM := FighterSM.State

## Geometric decay used for knockback velocity each tick.
const KNOCKBACK_DECAY := 0.85


static func decelerate(sim: BattleSim, f: Fighter, rate: float = -1.0) -> void:
	if f.vel == Vector2.ZERO:
		return
	var r := rate if rate >= 0.0 else f.stats.movement.deceleration
	f.vel = f.vel.move_toward(Vector2.ZERO, r * CombatConst.TICK_DT)
	integrate(sim, f)


static func integrate(sim: BattleSim, f: Fighter) -> void:
	if f.vel == Vector2.ZERO:
		return
	var delta := f.vel * CombatConst.TICK_DT
	var new_pos := sim.geometry.move_and_slide(f.pos, delta, f.radius())
	var actual := new_pos - f.pos
	# Don't keep pushing velocity into a wall.
	if actual.length() < delta.length() * 0.999:
		f.vel = actual / CombatConst.TICK_DT
	f.pos = new_pos


static func apply_knockback(sim: BattleSim, f: Fighter) -> void:
	if f.knockback_ticks <= 0:
		return
	var step := f.knockback_vel * CombatConst.TICK_DT
	var res := sim.geometry.move_until_blocked(f.pos, step, f.radius())
	f.pos = res["pos"]
	f.knockback_ticks -= 1
	f.knockback_vel *= KNOCKBACK_DECAY
	if res["hit"]:
		f.knockback_ticks = 0
		f.knockback_vel = Vector2.ZERO


## Sets knockback so the fighter travels `distance` units along `dir`,
## snapped to the board (nothing moves diagonally).
static func push(f: Fighter, dir: Vector2, distance: float) -> void:
	if distance <= 0.0 or dir == Vector2.ZERO:
		return
	var n := CombatConst.KNOCKBACK_TICKS
	var series := (1.0 - pow(KNOCKBACK_DECAY, n)) / (1.0 - KNOCKBACK_DECAY)
	f.knockback_vel = Cardinal.snap(dir) * distance / (CombatConst.TICK_DT * series)
	f.knockback_ticks = n


## Resolve body overlap between opposing creatures, along a board axis.
##
## Bodies are solid: whoever walks into the other takes the correction, so you
## can't shove an opponent around — except that a much heavier creature
## nudges a lighter one (up to 40% of its push), which is part of Stoneback's
## identity. If neither is moving in, the overlap is split by mass.
static func separate_bodies(sim: BattleSim) -> void:
	var active := sim.on_field_fighters()
	for i in active.size():
		for j in range(i + 1, active.size()):
			var a := active[i]
			var b := active[j]
			if a.is_ko() or b.is_ko():
				continue
			if _passing_through(a) or _passing_through(b):
				continue
			var d := b.pos - a.pos
			var need := a.radius() + b.radius()
			if d.length() >= need:
				continue
			# Separate along one board axis (nothing moves diagonally): the
			# dominant axis of the offset, by just enough to clear the bodies.
			var n := Cardinal.snap(d) if d.length_squared() > 1e-10 else Vector2.RIGHT
			var along := absf(d.dot(n))
			var across := absf(d.dot(Vector2(-n.y, n.x)))
			var overlap := sqrt(maxf(0.0, need * need - across * across)) - along
			if overlap <= 0.0:
				continue
			var ma := a.stats.movement.mass
			var mb := b.stats.movement.mass
			var a_in := maxf(0.0, _motion(a).dot(n))
			var b_in := maxf(0.0, -_motion(b).dot(n))
			var wa: float
			if a_in + b_in < 0.01:
				wa = mb / (ma + mb)
			else:
				wa = a_in / (a_in + b_in)
				var yield_b := clampf((ma / mb - 1.0) * 0.2, 0.0, 0.4)
				var yield_a := clampf((mb / ma - 1.0) * 0.2, 0.0, 0.4)
				wa = wa * (1.0 - yield_b) + (1.0 - wa) * yield_a
			# A dashing creature holds its lane; the other one makes room.
			if _dashing(a) != _dashing(b):
				wa = 0.0 if _dashing(a) else 1.0
			a.pos = sim.geometry.push_out(a.pos - n * overlap * wa, a.radius())
			b.pos = sim.geometry.push_out(b.pos + n * overlap * (1.0 - wa), b.radius())


static func _motion(f: Fighter) -> Vector2:
	var v := f.vel
	if f.knockback_ticks > 0:
		v += f.knockback_vel
	if f.lunge_ticks > 0:
		v += f.lunge_dir * f.lunge_speed * CombatConst.TICK_RATE
	return v


static func _dashing(f: Fighter) -> bool:
	return f.state == SM.DASH_START or f.state == SM.DASH_ACTIVE


static func _passing_through(f: Fighter) -> bool:
	return f.state == SM.DASH_ACTIVE and f.stats.dash.collision_behavior == DashProfile.CollisionBehavior.PASS_THROUGH
