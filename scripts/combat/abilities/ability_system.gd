class_name AbilitySystem
extends RefCounted
## Runs abilities through startup -> active -> recovery, triggers their
## components, enforces cooldowns, stamina costs, cancel rules and combo
## chains, and advances live hit volumes.

const SM := FighterSM.State
const Trigger := AbilityComponent.Trigger


static func check_usable(f: Fighter, ability: AbilityDefinition) -> StringName:
	if ability == null:
		return &"empty"
	if f.cooldown_of(ability) > 0:
		return &"cooldown"
	if not StaminaSystem.can_afford(f, ability.stamina_cost):
		return &"stamina"
	if f.status_flag("prevents_attacks"):
		return &"status"
	return &""


static func try_start(sim: BattleSim, f: Fighter, slot: int) -> bool:
	var ability := f.ability_in_slot(slot)
	var reason := check_usable(f, ability)
	if reason != &"":
		if ability != null:
			sim.emit(BattleEvent.ABILITY_DENIED, f, -1, f.pos, {"ability": ability.id, "reason": reason, "slot": slot})
		return false
	StaminaSystem.spend(f, ability.stamina_cost)
	if ability.cooldown_ticks > 0:
		f.cooldowns[ability.id] = ability.cooldown_ticks
	start(sim, f, ability, slot)
	return true


static func start(sim: BattleSim, f: Fighter, ability: AbilityDefinition, slot: int) -> void:
	f.current_ability = ability
	f.current_slot = slot
	f.ability_hit_landed = false
	f.lunge_ticks = 0
	capture_aim(f, ability)
	f.vel = Vector2.ZERO
	sim.set_state(f, SM.ATTACK_START, ability.startup_ticks)
	f.usage_for(ability.id)["uses"] += 1
	sim.emit(BattleEvent.ABILITY_START, f, -1, f.pos, {
		"ability": ability.id,
		"slot": slot,
		"dir": f.ability_dir,
		"point": f.ability_point,
		"startup": ability.startup_ticks,
		"anim": ability.anim,
		"sfx": ability.cast_sfx,
	})
	_run(sim, f, ability, Trigger.STARTUP_BEGIN, 0)
	if ability.telegraph:
		for c in ability.components:
			var shape := c.telegraph_shape(f, ability)
			if not shape.is_empty():
				shape["ticks"] = ability.startup_ticks
				sim.emit(BattleEvent.TELEGRAPH, f, -1, f.pos, shape)


static func capture_aim(f: Fighter, ability: AbilityDefinition) -> void:
	var dir := f.aim if f.aim != Vector2.ZERO else f.facing
	f.ability_dir = dir.normalized()
	match ability.aim_mode:
		AbilityDefinition.AimMode.TARGET_POINT:
			var dist := clampf(f.pos.distance_to(f.aim_point), 0.0, ability.max_range)
			f.ability_point = f.pos + f.ability_dir * dist
		AbilityDefinition.AimMode.SELF:
			f.ability_point = f.pos
		_:
			f.ability_point = f.pos + f.ability_dir * ability.max_range
	f.facing = f.ability_dir


## Per-tick logic while in an attack state (called after phase advance).
static func step(sim: BattleSim, f: Fighter, cmd: InputCommand) -> void:
	var ability := f.current_ability
	if ability == null:
		return
	match f.state:
		SM.ATTACK_START:
			if ability.can_aim_during_startup:
				capture_aim(f, ability)
		SM.ATTACK_ACTIVE:
			_run(sim, f, ability, Trigger.ACTIVE_TICK, f.state_tick)
			_step_lunge(sim, f)
	if f.lunge_ticks <= 0:
		MovementSystem.decelerate(sim, f, 80.0)


static func begin_active(sim: BattleSim, f: Fighter) -> void:
	var ability := f.current_ability
	sim.set_state(f, SM.ATTACK_ACTIVE, ability.active_ticks)
	sim.emit(BattleEvent.ABILITY_ACTIVE, f, -1, f.pos, {"ability": ability.id, "dir": f.ability_dir, "point": f.ability_point})
	_run(sim, f, ability, Trigger.ACTIVE_BEGIN, 0)


static func begin_recovery(sim: BattleSim, f: Fighter) -> void:
	var ability := f.current_ability
	f.lunge_ticks = 0
	sim.set_state(f, SM.ATTACK_RECOVERY, ability.recovery_ticks)
	_run(sim, f, ability, Trigger.RECOVERY_BEGIN, 0)


static func finish(sim: BattleSim, f: Fighter) -> void:
	f.current_ability = null
	f.current_slot = -1
	sim.set_state(f, SM.IDLE)


## Combo chain and dash-cancel windows during recovery. Returns true if the
## recovery was cancelled into something else.
static func try_cancel_recovery(sim: BattleSim, f: Fighter, cmd: InputCommand) -> bool:
	var ability := f.current_ability
	if ability == null or f.state != SM.ATTACK_RECOVERY:
		return false
	if ability.chain_next and f.state_tick < ability.chain_window_ticks:
		if f.buffer.has(InputCommand.ATTACK, sim.tick) or cmd.is_held(InputCommand.ATTACK):
			f.buffer.consume(InputCommand.ATTACK)
			start(sim, f, ability.chain_next, -1)
			return true
	if ability.dash_cancel_from_recovery_tick >= 0 and f.state_tick >= ability.dash_cancel_from_recovery_tick:
		if f.buffer.has(InputCommand.DASH, sim.tick):
			f.buffer.consume(InputCommand.DASH)
			if DashSystem.try_start(sim, f, f.dash_req_dir, f.dash_req_cells):
				f.dash_req_dir = -1
				f.dash_req_cells = 0
				f.current_ability = null
				f.current_slot = -1
				return true
	return false


## Cancels the current ability (stun, KO, switch): removes its attached hitboxes.
static func interrupt(sim: BattleSim, f: Fighter) -> void:
	if f.current_ability == null:
		return
	for v in sim.volumes:
		if v.owner_id == f.id and v.cancel_with_owner and not v.dead:
			v.dead = true
			sim.emit_volume_end(v, &"interrupted")
	f.current_ability = null
	f.current_slot = -1
	f.lunge_ticks = 0


static func _run(sim: BattleSim, f: Fighter, ability: AbilityDefinition, trigger: int, phase_tick: int) -> void:
	for c in ability.components:
		if c != null and c.trigger == trigger:
			c.execute(sim, f, ability, phase_tick)


static func _step_lunge(sim: BattleSim, f: Fighter) -> void:
	if f.lunge_ticks <= 0:
		return
	if f.lunge_stop_on_hit and f.ability_hit_landed:
		f.lunge_ticks = 0
		return
	var from := f.pos
	var res := sim.geometry.move_until_blocked(from, f.lunge_dir * f.lunge_speed, f.radius())
	var to: Vector2 = res["pos"]
	# Lunges stop at enemy bodies instead of passing through them.
	for o in sim.on_field_fighters():
		if o.team == f.team or o.is_ko():
			continue
		var reach := f.radius() + o.radius()
		var t := ArenaGeometry.segment_circle_t(from, to, o.pos, reach)
		if t >= 0.0:
			to = from.lerp(to, maxf(0.0, t - 0.02))
			f.lunge_ticks = 0
	f.pos = to
	f.lunge_ticks -= 1
	if res["hit"]:
		f.lunge_ticks = 0


# --- Hit volumes -------------------------------------------------------------------

## Moves projectiles, attached swings and waves; resolves projectile clashes.
static func update_volumes(sim: BattleSim) -> void:
	for v in sim.volumes:
		if v.dead:
			continue
		var owner := sim.fighter_by_id(v.owner_id)
		v.prev_pos = v.pos
		match v.motion:
			HitVolume.Motion.PROJECTILE:
				if v.age < v.delay_ticks:
					continue
				var step := v.velocity * CombatConst.TICK_DT
				var res := sim.geometry.move_until_blocked(v.pos, step, v.radius, true)
				var moved: Vector2 = res["pos"]
				v.travel += v.pos.distance_to(moved)
				v.pos = moved
				if res["hit"]:
					v.dead = true
					sim.emit(BattleEvent.PROJECTILE_BLOCKED, owner, -1, v.pos, {"volume": v.id, "visual": v.visual})
					sim.emit_volume_end(v, &"blocked")
				elif v.travel >= v.max_travel:
					v.dead = true
					sim.emit_volume_end(v, &"range")
			HitVolume.Motion.ATTACHED:
				if owner:
					v.dir = owner.ability_dir
					v.pos = owner.pos + v.dir * v.forward_offset
			HitVolume.Motion.WAVE:
				if v.age >= v.delay_ticks:
					var t := float(v.age - v.delay_ticks + 1)
					v.wave_front = minf(v.wave_total, t * v.wave_speed * CombatConst.TICK_DT)
					var back := maxf(0.0, v.wave_front - v.segment_length)
					v.pos = v.origin + v.dir * back
					v.length = v.wave_front - back
	_resolve_clashes(sim)


## Age volumes and drop expired ones (after hit resolution).
static func age_volumes(sim: BattleSim) -> void:
	for v in sim.volumes:
		if v.dead:
			continue
		var owner := sim.fighter_by_id(v.owner_id)
		if v.motion == HitVolume.Motion.ATTACHED and owner and owner.hitstop > 0:
			continue
		v.age += 1
		if v.motion != HitVolume.Motion.PROJECTILE and v.age >= v.delay_ticks + v.active_ticks:
			v.dead = true
			sim.emit_volume_end(v, &"expired")
	var alive: Array[HitVolume] = []
	for v in sim.volumes:
		if not v.dead:
			alive.append(v)
	sim.volumes = alive


static func _resolve_clashes(sim: BattleSim) -> void:
	var projectiles: Array[HitVolume] = []
	for v in sim.volumes:
		if not v.dead and v.is_projectile() and v.age >= v.delay_ticks:
			projectiles.append(v)
	for i in projectiles.size():
		for j in range(i + 1, projectiles.size()):
			var a := projectiles[i]
			var b := projectiles[j]
			if a.dead or b.dead or a.team == b.team:
				continue
			var d := ArenaGeometry.segment_segment_distance(a.prev_pos, a.pos, b.prev_pos, b.pos)
			if d > a.radius + b.radius:
				continue
			var at := (a.pos + b.pos) * 0.5
			if a.clash_weight == b.clash_weight:
				a.dead = true
				b.dead = true
			elif a.clash_weight > b.clash_weight:
				b.dead = true
				a.clash_weight -= b.clash_weight
			else:
				a.dead = true
				b.clash_weight -= a.clash_weight
			sim.emit(BattleEvent.PROJECTILE_CLASH, sim.fighter_by_id(a.owner_id), b.owner_id, at, {"a": a.id, "b": b.id})
			if a.dead:
				sim.emit_volume_end(a, &"clash")
			if b.dead:
				sim.emit_volume_end(b, &"clash")
