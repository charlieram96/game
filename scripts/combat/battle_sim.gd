class_name BattleSim
extends RefCounted
## The authoritative battle simulation.
##
## Pure logic, no nodes: step() advances exactly one 60 Hz tick from a set of
## InputCommands (one per team) and records BattleEvents. The same object can
## run inside the local battle scene, a headless dedicated server, or a unit
## test. Rules live in the systems (movement, dash, stamina, abilities,
## damage); this class owns the tick order and the match flow.
##
## Tick order (deterministic):
##   1. inputs -> buffers/aim       2. each fighter: timers, statuses,
##   phase advance, actions, state logic, knockback   3. body separation
##   4. hit volumes move + clash    5. hits resolved (two-phase)
##   6. volumes age/expire          7. match flow (KO, timer)

const SM := FighterSM.State

enum Phase { COUNTDOWN, FIGHT, KO_SETTLE, FINISHED }

var setup: BattleSetup
var ruleset: BattleRuleset
var geometry: ArenaGeometry
var tick: int = 0
var phase: Phase = Phase.COUNTDOWN
var phase_ticks: int = 0
var match_ticks_left: int = 0
var fighters: Array[Fighter] = []
var teams: Array = [[], []]  # team -> Array[Fighter]
var volumes: Array[HitVolume] = []
var events: Array[BattleEvent] = []
var winner_team: int = -1  # -1 undecided, -2 draw
var end_reason: StringName = &""
var debug_illegal_transitions: int = 0

var _next_event_id: int = 1
var _next_volume_id: int = 1
var _empty_cmd := InputCommand.new()
var _pending_switch_in: Array[int] = []


func _init(p_setup: BattleSetup) -> void:
	setup = p_setup
	reset()


## Restores the battle to its starting state (used for rematches).
func reset() -> void:
	ruleset = setup.ruleset
	geometry = ArenaGeometry.from_definition(setup.arena)
	tick = 0
	volumes.clear()
	events.clear()
	fighters.clear()
	teams = [[], []]
	winner_team = -1
	end_reason = &""
	_next_event_id = 1
	_next_volume_id = 1
	_pending_switch_in.clear()
	var next_id := 0
	for team in 2:
		var entries: Array = setup.teams[team]
		for slot in entries.size():
			var entry: Dictionary = entries[slot]
			var f := Fighter.new()
			f.id = next_id
			next_id += 1
			f.team = team
			f.team_slot = slot
			f.creature = entry["creature"]
			f.species = entry["species"]
			f.stats = StatCalculator.compute(f.species, f.creature, ruleset)
			if team == setup.enemy_team and ruleset.enemy_hp_mult != 1.0:
				f.stats.max_hp = roundf(f.stats.max_hp * ruleset.enemy_hp_mult)
			f.hp = f.stats.max_hp
			f.stamina = f.stats.stamina.max_stamina
			f.label = f.creature.display_name(f.species)
			f.on_field = slot == 0
			var spawn := setup.arena.spawn_team0 if team == 0 else setup.arena.spawn_team1
			f.pos = geometry.push_out(spawn, f.radius())
			f.prev_pos = f.pos
			f.facing = Vector2.RIGHT if team == 0 else Vector2.LEFT
			f.cardinal_facing = Cardinal.snap(f.facing)
			f.aim = f.facing
			fighters.append(f)
			(teams[team] as Array).append(f)
	match_ticks_left = ruleset.match_time_sec * CombatConst.TICK_RATE if setup.time_limit and not setup.training else -1
	if setup.countdown:
		phase = Phase.COUNTDOWN
		phase_ticks = CombatConst.COUNTDOWN_TICKS
	else:
		phase = Phase.FIGHT
		phase_ticks = 0


# --- Public API ----------------------------------------------------------------------

## Advance one tick. `inputs` maps team index -> InputCommand.
func step(inputs: Dictionary = {}) -> void:
	events.clear()
	tick += 1
	match phase:
		Phase.COUNTDOWN:
			_step_countdown(inputs)
		Phase.FIGHT:
			_step_fight(inputs)
		Phase.KO_SETTLE:
			_step_settle(inputs)
		Phase.FINISHED:
			pass


func is_finished() -> bool:
	return phase == Phase.FINISHED


func active_fighter(team: int) -> Fighter:
	for f: Fighter in teams[team]:
		if f.on_field:
			return f
	return null


func opponent_of(f: Fighter) -> Fighter:
	return active_fighter(1 - f.team)


func on_field_fighters() -> Array[Fighter]:
	var out: Array[Fighter] = []
	for f in fighters:
		if f.on_field:
			out.append(f)
	return out


func fighter_by_id(fid: int) -> Fighter:
	if fid >= 0 and fid < fighters.size():
		return fighters[fid]
	return null


func is_enemy_side(team: int) -> bool:
	return setup.enemy_team == team


func team_alive(team: int) -> bool:
	for f: Fighter in teams[team]:
		if not f.is_ko():
			return true
	return false


func seconds_left() -> float:
	if match_ticks_left < 0:
		return -1.0
	return float(match_ticks_left) / CombatConst.TICK_RATE


## Guarded state change: refuses transitions not in FighterSM's table.
func set_state(f: Fighter, s: FighterSM.State, duration: int = 0) -> bool:
	if f.state != s and not FighterSM.can_transition(f.state, s):
		debug_illegal_transitions += 1
		if OS.is_debug_build():
			push_warning("Illegal transition %s -> %s for %s" % [FighterSM.state_name(f.state), FighterSM.state_name(s), f.label])
		return false
	var prev := f.state
	f.state = s
	f.state_tick = 0
	f.state_duration = duration
	if s != SM.DASH_START and s != SM.DASH_ACTIVE and s != SM.DASH_RECOVERY:
		f.dash_queued = false
	if prev != s:
		emit(BattleEvent.STATE, f, -1, f.pos, {"from": prev, "to": s})
	return true


func emit(type: StringName, f: Fighter, target_id: int, pos: Vector2, data: Dictionary) -> BattleEvent:
	var e := BattleEvent.new()
	e.id = _next_event_id
	_next_event_id += 1
	e.type = type
	e.tick = tick
	e.fighter_id = f.id if f else -1
	e.target_id = target_id
	e.pos = pos
	e.data = data
	events.append(e)
	return e


func new_volume(caster: Fighter, ability: AbilityDefinition, hit: HitSpec) -> HitVolume:
	var v := HitVolume.new()
	v.id = _next_volume_id
	_next_volume_id += 1
	v.owner_id = caster.id
	v.team = caster.team
	v.ability = ability
	v.hit = hit if hit else HitSpec.new()
	v.element = ability.element
	return v


func add_volume(v: HitVolume) -> void:
	volumes.append(v)
	emit(BattleEvent.VOLUME_SPAWN, fighter_by_id(v.owner_id), -1, v.pos, v.describe())


func emit_volume_end(v: HitVolume, reason: StringName) -> void:
	emit(BattleEvent.VOLUME_END, fighter_by_id(v.owner_id), -1, v.pos, {"volume": v.id, "reason": reason, "visual": v.visual})


## Scripted-scenario hook (the tutorial): sets a fighter's stamina, clamped
## to its maximum. Lives on the sim so presentation code never mutates fighter
## state directly; nothing in a ranked or online match calls it.
func script_set_stamina(f: Fighter, value: float) -> void:
	f.stamina = clampf(value, 0.0, f.max_stamina())


func knock_out(f: Fighter, by: Fighter) -> void:
	if f.is_ko():
		return
	if setup.training and f.team == 1:
		# Training partners never go down; they shrug it off and refill.
		f.hp = f.max_hp()
		emit(BattleEvent.KO, f, by.id if by else -1, f.pos, {"training": true})
		return
	f.hp = 0.0
	AbilitySystem.interrupt(self, f)
	set_state(f, SM.KNOCKED_OUT)
	f.vel = Vector2.ZERO
	f.statuses.clear()
	emit(BattleEvent.KO, f, by.id if by else -1, f.pos, {"team": f.team})
	if phase == Phase.FIGHT:
		phase = Phase.KO_SETTLE
		phase_ticks = CombatConst.KO_SETTLE_TICKS


## Deterministic digest of the whole simulation (for replay/determinism tests
## and future client/server desync detection).
func state_hash() -> int:
	var parts: Array = [tick, phase, winner_team]
	for f in fighters:
		parts.append(f.snapshot())
	for v in volumes:
		parts.append([v.id, snappedf(v.pos.x, 0.0001), snappedf(v.pos.y, 0.0001), v.age, v.dead])
	return hash(var_to_str(parts))


# --- Match flow ------------------------------------------------------------------------

func _step_countdown(inputs: Dictionary) -> void:
	for team in 2:
		var f := active_fighter(team)
		if f:
			f.prev_pos = f.pos
			_update_aim(f, inputs.get(team, _empty_cmd))
	if phase_ticks % CombatConst.TICK_RATE == 0:
		emit(BattleEvent.COUNTDOWN, null, -1, Vector2.ZERO, {"seconds": phase_ticks / CombatConst.TICK_RATE})
	phase_ticks -= 1
	if phase_ticks <= 0:
		phase = Phase.FIGHT
		for f in fighters:
			f.buffer.clear()
		emit(BattleEvent.FIGHT_START, null, -1, Vector2.ZERO, {})


func _step_fight(inputs: Dictionary) -> void:
	for f in fighters:
		if f.on_field:
			_step_fighter(f, inputs.get(f.team, _empty_cmd))
		else:
			_step_benched(f)
	MovementSystem.separate_bodies(self)
	AbilitySystem.update_volumes(self)
	DamageSystem.resolve_volume_hits(self)
	AbilitySystem.age_volumes(self)
	if phase != Phase.FIGHT:
		return
	if match_ticks_left > 0:
		match_ticks_left -= 1
		if match_ticks_left == 0:
			_on_timeout()


func _step_settle(inputs: Dictionary) -> void:
	# Survivors keep animating/moving but nobody can be hurt.
	for f in fighters:
		f.prev_pos = f.pos
		if f.on_field and not f.is_ko():
			var cmd: InputCommand = inputs.get(f.team, _empty_cmd)
			_update_aim(f, cmd)
			if f.hitstop > 0:
				f.hitstop -= 1
				continue
			_tick_timers(f)
			_advance_state(f)
			_state_logic(f, _empty_cmd)
		MovementSystem.apply_knockback(self, f)
	AbilitySystem.update_volumes(self)
	for v in volumes:
		v.dead = true
	AbilitySystem.age_volumes(self)
	phase_ticks -= 1
	if phase_ticks > 0:
		return
	# Decide: send in the next creature, or end the battle.
	for team in 2:
		var active := active_fighter(team)
		if active and active.is_ko() and team_alive(team):
			_send_next(team)
	if not team_alive(0) or not team_alive(1):
		_finish(0 if team_alive(0) else (1 if team_alive(1) else -2), &"ko")
	else:
		phase = Phase.FIGHT


func _on_timeout() -> void:
	var ratios := [0.0, 0.0]
	for team in 2:
		var total := 0.0
		var cur := 0.0
		for f: Fighter in teams[team]:
			total += f.max_hp()
			cur += f.hp
		ratios[team] = cur / maxf(1.0, total)
	emit(BattleEvent.TIMEOUT, null, -1, Vector2.ZERO, {"ratios": ratios})
	if absf(ratios[0] - ratios[1]) < 0.001:
		_finish(-2, &"timeout")
	else:
		_finish(0 if ratios[0] > ratios[1] else 1, &"timeout")


func _finish(winner: int, reason: StringName) -> void:
	winner_team = winner
	end_reason = reason
	phase = Phase.FINISHED
	emit(BattleEvent.BATTLE_END, null, -1, Vector2.ZERO, {"winner": winner, "reason": reason})


func _send_next(team: int) -> void:
	var old := active_fighter(team)
	for f: Fighter in teams[team]:
		if not f.is_ko() and not f.on_field:
			if old:
				old.on_field = false
				f.pos = geometry.push_out(old.pos, f.radius())
				f.facing = old.facing
			f.on_field = true
			f.prev_pos = f.pos
			f.state = SM.IDLE
			f.state_tick = 0
			f.wakeup_grace = CombatConst.WAKEUP_GRACE_TICKS * 3
			emit(BattleEvent.SWITCH_IN, f, -1, f.pos, {"slot": f.team_slot, "forced": true})
			return


# --- Fighter update ------------------------------------------------------------------------

func _step_fighter(f: Fighter, cmd: InputCommand) -> void:
	f.prev_pos = f.pos
	if f.is_ko():
		MovementSystem.apply_knockback(self, f)
		return
	f.held = cmd.held
	f.buffer.record(cmd.pressed, tick)
	if cmd.has_dash():
		f.dash_req_dir = cmd.dash_dir
		f.dash_req_cells = cmd.dash_cells
		f.dash_queued = f.state == SM.DASH_START or f.state == SM.DASH_ACTIVE or f.state == SM.DASH_RECOVERY
	_update_aim(f, cmd)
	if f.hitstop > 0:
		f.hitstop -= 1
		return
	_tick_timers(f)
	StatusSystem.tick(self, f)
	if f.is_ko():
		return
	_advance_state(f)
	_handle_actions(f, cmd)
	_state_logic(f, cmd)
	MovementSystem.apply_knockback(self, f)


func _step_benched(f: Fighter) -> void:
	f.prev_pos = f.pos
	if f.is_ko():
		return
	for key in f.cooldowns.keys():
		f.cooldowns[key] = maxi(0, int(f.cooldowns[key]) - 1)
	f.switch_cooldown = maxi(0, f.switch_cooldown - 1)
	StaminaSystem.bench_regen(f)


func _tick_timers(f: Fighter) -> void:
	for key in f.cooldowns.keys():
		var left := int(f.cooldowns[key])
		if left > 0:
			f.cooldowns[key] = left - 1
	if f.dash_through_immunity > 0:
		f.dash_through_immunity -= 1
	if f.wakeup_grace > 0:
		f.wakeup_grace -= 1
	if f.steadfast > 0:
		f.steadfast -= 1
	if f.guard_reentry > 0:
		f.guard_reentry -= 1
	if f.guard_lock > 0:
		f.guard_lock -= 1
	if f.switch_cooldown > 0:
		f.switch_cooldown -= 1


func _update_aim(f: Fighter, cmd: InputCommand) -> void:
	if cmd.aim != Vector2.ZERO:
		f.aim = cmd.aim
		f.aim_point = f.pos + cmd.aim * cmd.aim_distance
	else:
		# No aiming device: soft-lock onto the opponent.
		var o := opponent_of(f)
		if o and not o.is_ko():
			var to := o.pos - f.pos
			if to.length_squared() > 1e-4:
				f.aim = to.normalized()
			f.aim_point = o.pos
		else:
			f.aim = f.facing
			f.aim_point = f.pos + f.facing * 3.0
	# Facing follows the aim while able to turn; otherwise the action's direction.
	if FighterSM.is_actionable(f.state) or f.state == SM.GUARDING or FighterSM.is_focusing(f.state):
		f.facing = f.aim


## Time-driven phase transitions.
func _advance_state(f: Fighter) -> void:
	f.state_tick += 1
	match f.state:
		SM.FOCUS_ENTER:
			if f.state_tick >= f.state_duration:
				if f.focus_released or not (f.held & InputCommand.FOCUS):
					set_state(f, SM.FOCUS_EXIT, StaminaSystem.exit_ticks(f))
				else:
					set_state(f, SM.FOCUSING, 0)
		SM.FOCUS_EXIT:
			if f.state_tick >= f.state_duration:
				set_state(f, SM.IDLE)
		SM.DASH_START:
			if f.state_tick >= f.state_duration:
				DashSystem.begin_active(self, f)
		SM.DASH_RECOVERY:
			if f.state_tick >= f.state_duration:
				set_state(f, SM.IDLE)
		SM.ATTACK_START:
			if f.state_tick >= f.state_duration:
				if f.current_ability:
					AbilitySystem.begin_active(self, f)
				else:
					set_state(f, SM.ATTACK_ACTIVE, 1)
		SM.ATTACK_ACTIVE:
			if f.state_tick >= f.state_duration:
				if f.current_ability:
					AbilitySystem.begin_recovery(self, f)
				else:
					set_state(f, SM.ATTACK_RECOVERY, 1)
		SM.ATTACK_RECOVERY:
			if f.state_tick >= f.state_duration:
				AbilitySystem.finish(self, f)
		SM.STUNNED:
			if f.state_tick >= f.state_duration:
				set_state(f, SM.IDLE)
				StunRules.on_stun_end(self, f)
		SM.SWITCHING:
			if f.state_tick >= f.state_duration:
				_complete_switch(f)


## Starts new actions from buffered/held input when the state allows it.
func _handle_actions(f: Fighter, cmd: InputCommand) -> void:
	match f.state:
		SM.ATTACK_RECOVERY:
			AbilitySystem.try_cancel_recovery(self, f, cmd)
			return
		SM.FOCUS_ENTER, SM.FOCUSING:
			if not cmd.is_held(InputCommand.FOCUS):
				f.focus_released = true
				if f.state == SM.FOCUSING:
					set_state(f, SM.FOCUS_EXIT, StaminaSystem.exit_ticks(f))
			return
		SM.GUARDING:
			if not cmd.is_held(InputCommand.GUARD) and f.guard_lock <= 0:
				GuardSystem.release(self, f)
			else:
				return
		SM.DASH_RECOVERY:
			# Dash chaining: a dash buffered (or queued mid-dash) may cut the
			# landing short.
			if DashSystem.can_chain(f) and (f.dash_queued or f.buffer.has(InputCommand.DASH, tick)):
				f.buffer.consume(InputCommand.DASH)
				_try_dash(f)
			return
	if not FighterSM.is_actionable(f.state):
		return
	var b := f.buffer
	# 1) Switching
	if setup.allow_switching:
		for i in InputCommand.SWITCH_BITS.size():
			if b.has(InputCommand.SWITCH_BITS[i], tick):
				b.consume(InputCommand.SWITCH_BITS[i])
				if _try_switch(f, i):
					return
	# 2) Dash
	if b.has(InputCommand.DASH, tick):
		b.consume(InputCommand.DASH)
		if _try_dash(f):
			return
	# 3) Guard (hold)
	if cmd.is_held(InputCommand.GUARD) or b.has(InputCommand.GUARD, tick):
		b.consume(InputCommand.GUARD)
		if GuardSystem.try_start(self, f):
			return
	# 4) Specials
	for i in InputCommand.ABILITY_BITS.size():
		var bit: int = InputCommand.ABILITY_BITS[i]
		if b.has(bit, tick):
			b.consume(bit)
			if AbilitySystem.try_start(self, f, i):
				return
	# 5) Basic attack (press or hold to repeat)
	if b.has(InputCommand.ATTACK, tick) or cmd.is_held(InputCommand.ATTACK):
		b.consume(InputCommand.ATTACK)
		if AbilitySystem.try_start(self, f, -1):
			return
	# 6) Focus (hold)
	if cmd.is_held(InputCommand.FOCUS):
		StaminaSystem.try_enter(self, f)


func _try_dash(f: Fighter) -> bool:
	f.dash_queued = false
	var started := DashSystem.try_start(self, f, f.dash_req_dir, f.dash_req_cells)
	f.dash_req_dir = -1
	f.dash_req_cells = 0
	return started


## Per-tick behaviour of the current state. Nothing walks: creatures stand
## their ground unless a dash, a lunge or knockback moves them.
func _state_logic(f: Fighter, cmd: InputCommand) -> void:
	match f.state:
		SM.FOCUSING:
			StaminaSystem.regen(self, f)
		SM.DASH_START:
			DashSystem.step_windup(self, f)
		SM.DASH_ACTIVE:
			DashSystem.step_active(self, f)
		SM.ATTACK_START, SM.ATTACK_ACTIVE, SM.ATTACK_RECOVERY:
			AbilitySystem.step(self, f, cmd)
		SM.GUARDING:
			MovementSystem.decelerate(self, f, 60.0)
		_:
			MovementSystem.decelerate(self, f, 40.0)


# --- Switching (team battles) -------------------------------------------------------------

func _try_switch(f: Fighter, slot: int) -> bool:
	if f.switch_cooldown > 0 or FighterSM.blocks_switch(f.state):
		return false
	var team: Array = teams[f.team]
	if slot >= team.size():
		return false
	var target: Fighter = team[slot]
	if target == f or target.is_ko() or target.on_field:
		return false
	f.switch_target_slot = slot
	set_state(f, SM.SWITCHING, CombatConst.SWITCH_TICKS)
	emit(BattleEvent.SWITCH_START, f, target.id, f.pos, {"slot": slot})
	return true


func _complete_switch(f: Fighter) -> void:
	var team: Array = teams[f.team]
	var incoming: Fighter = team[f.switch_target_slot]
	StatusSystem.clear_on_switch(self, f)
	set_state(f, SM.IDLE)
	f.on_field = false
	f.dash_through_immunity = 0
	f.buffer.clear()
	incoming.on_field = true
	incoming.pos = geometry.push_out(f.pos, incoming.radius())
	incoming.prev_pos = incoming.pos
	incoming.facing = f.facing
	incoming.cardinal_facing = f.cardinal_facing
	incoming.state = SM.IDLE
	incoming.state_tick = 0
	incoming.switch_cooldown = CombatConst.SWITCH_COOLDOWN_TICKS
	incoming.buffer.clear()
	emit(BattleEvent.SWITCH_IN, incoming, f.id, incoming.pos, {"slot": incoming.team_slot, "forced": false})
