class_name GuardSystem
extends RefCounted
## Directional guard with perfect-guard timing and guard break.
##
## Guard blocks guardable hits arriving within a wide frontal arc. Blocked
## damage becomes a small chip plus stamina loss; running out of stamina
## breaks the guard (long stun). Guarding in the first PERFECT_GUARD_TICKS
## negates the hit entirely and staggers melee attackers.

const SM := FighterSM.State


static func try_start(sim: BattleSim, f: Fighter) -> bool:
	if f.guard_reentry > 0:
		return false
	if not sim.set_state(f, SM.GUARDING, 0):
		return false
	f.guard_tick = 0
	f.guard_lock = 0
	f.vel = Vector2.ZERO
	sim.emit(BattleEvent.GUARD_START, f, -1, f.pos, {})
	return true


static func release(sim: BattleSim, f: Fighter) -> void:
	if sim.set_state(f, SM.IDLE):
		f.guard_reentry = CombatConst.GUARD_REENTRY_TICKS


static func in_guard_arc(f: Fighter, from_pos: Vector2) -> bool:
	var to := from_pos - f.pos
	if to.length_squared() < 0.0001:
		return true
	return absf(f.facing.angle_to(to)) <= deg_to_rad(CombatConst.GUARD_ARC_DEG * 0.5)


static func is_perfect(f: Fighter) -> bool:
	return f.state == SM.GUARDING and f.state_tick < CombatConst.PERFECT_GUARD_TICKS


## Resolve a guarded hit. `raw_damage` is the unguarded damage.
static func on_block(sim: BattleSim, target: Fighter, attacker: Fighter, v: HitVolume, raw_damage: float, contact: Vector2) -> void:
	var hit := v.hit
	if is_perfect(target):
		target.record["perfect_guards"] += 1
		target.hitstop = maxi(target.hitstop, 5)
		if v.is_projectile():
			v.dead = true
		elif attacker and hit.staggers_on_perfect_guard and v.motion == HitVolume.Motion.ATTACHED:
			attacker.hitstop = maxi(attacker.hitstop, 5)
			StunRules.apply(sim, attacker, CombatConst.PERFECT_GUARD_STAGGER_TICKS, &"stagger")
		sim.emit(BattleEvent.PERFECT_GUARD, target, attacker.id if attacker else -1, contact, {"ability": v.ability.id if v.ability else &""})
		return
	target.record["blocks"] += 1
	var chip := raw_damage * CombatConst.GUARD_CHIP
	# Chip damage can't knock a creature out.
	target.hp = maxf(1.0, target.hp - chip) if target.hp > 1.0 else target.hp
	StaminaSystem.spend(target, raw_damage * target.stats.stamina.guard_stamina_factor, true)
	target.hitstop = maxi(target.hitstop, mini(hit.hitstop_ticks, 4))
	if v.is_projectile():
		v.dead = true
	if target.stamina <= 0.0:
		StunRules.apply(sim, target, CombatConst.GUARD_BREAK_STUN_TICKS, &"guard_break", true)
		sim.emit(BattleEvent.GUARD_BREAK, target, attacker.id if attacker else -1, contact, {})
		return
	target.guard_lock = maxi(target.guard_lock, int(round(hit.hitstun_ticks * CombatConst.BLOCKSTUN_FACTOR)))
	var push_dir := (target.pos - (attacker.pos if attacker else v.pos)).normalized()
	MovementSystem.push(target, push_dir, hit.knockback * 0.5)
	sim.emit(BattleEvent.BLOCK, target, attacker.id if attacker else -1, contact, {"chip": chip, "ability": v.ability.id if v.ability else &""})
