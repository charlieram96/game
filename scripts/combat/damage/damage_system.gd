class_name DamageSystem
extends RefCounted
## Hit detection between live hit volumes and hurtboxes, damage formula,
## armor, guard, hitstop, flinch, knockback, statuses and knockouts.
##
## Damage = power × mastery_mult × (attack / defense) × element_mult
##          × status / armor multipliers × ruleset scale   (min 1)

const SM := FighterSM.State


static func compute_raw(sim: BattleSim, attacker: Fighter, target: Fighter, v: HitVolume) -> Dictionary:
	var hit := v.hit
	var atk := attacker.stats.attack if attacker else 10.0
	var def := maxf(1.0, target.stats.defense)
	var power := hit.power
	if attacker and v.ability:
		power *= attacker.stats.power_mult(v.ability.id)
	var element := hit.element if hit.element != &"" else v.element
	var eff := ElementChart.multiplier(element, target.species.element)
	var dmg := power * (atk / def) * eff * sim.ruleset.damage_scale
	if attacker and sim.is_enemy_side(attacker.team):
		dmg *= sim.ruleset.enemy_damage_mult
	return {"damage": maxf(CombatConst.MIN_DAMAGE, dmg), "eff": eff, "element": element}


## Two-phase resolution: collect every overlap first, then apply, so neither
## fighter benefits from update order.
static func resolve_volume_hits(sim: BattleSim) -> void:
	var pending: Array = []
	for v in sim.volumes:
		if not v.is_live():
			continue
		for f in sim.on_field_fighters():
			if f.team == v.team or f.is_ko():
				continue
			if v.hits.has(f.id):
				var interval := v.hit.rehit_interval_ticks
				if interval <= 0 or sim.tick - int(v.hits[f.id]) < interval:
					continue
			if v.swept_overlaps(f.pos, f.hurt_radius()):
				pending.append([v, f])
	for pair in pending:
		var v: HitVolume = pair[0]
		var f: Fighter = pair[1]
		if v.dead or f.is_ko():
			continue
		v.hits[f.id] = sim.tick
		apply_hit(sim, v, f)
		if v.is_projectile() and not v.pierce:
			v.dead = true
			sim.emit_volume_end(v, &"hit")


static func apply_hit(sim: BattleSim, v: HitVolume, target: Fighter) -> void:
	var attacker := sim.fighter_by_id(v.owner_id)
	var hit := v.hit
	var contact := _contact_point(v, target)
	# FAST dash: projectiles pass straight through during the evade window.
	if v.is_projectile() and DashSystem.is_projectile_intangible(target):
		v.hits[target.id] = sim.tick + 100000
		sim.emit(BattleEvent.EVADE, target, v.owner_id, target.pos, {"ability": v.ability.id if v.ability else &""})
		return
	var raw := compute_raw(sim, attacker, target, v)
	var dmg: float = raw["damage"]
	var source_pos := attacker.pos if (attacker and v.motion == HitVolume.Motion.ATTACHED) else v.pos
	if v.motion == HitVolume.Motion.PROJECTILE:
		source_pos = v.prev_pos
	# Guard
	if target.state == SM.GUARDING and hit.guardable and GuardSystem.in_guard_arc(target, source_pos):
		GuardSystem.on_block(sim, target, attacker, v, dmg, contact)
		return
	# Armor and damage reduction
	var flinch_immune := target.status_flag("flinch_immune") or DashSystem.is_flinch_immune(target)
	if target.current_ability:
		if target.state == SM.ATTACK_START and target.current_ability.armor_during_startup:
			flinch_immune = true
		if target.state == SM.ATTACK_ACTIVE and target.current_ability.armor_during_active:
			flinch_immune = true
	dmg *= target.status_mult("damage_taken_mult")
	if target.state == SM.DASH_ACTIVE:
		dmg *= target.stats.dash.armor_damage_mult
	dmg = maxf(CombatConst.MIN_DAMAGE, snappedf(dmg, 0.1))
	target.hp = maxf(0.0, target.hp - dmg)
	target.record["damage_taken"] += dmg
	if attacker:
		attacker.record["damage_dealt"] += dmg
		attacker.record["hits"] += 1
		if v.ability:
			attacker.usage_for(v.ability.id)["hits"] += 1
			if v.ability == attacker.current_ability:
				attacker.ability_hit_landed = true
	# Hitstop: always on the target; on the attacker only for attached melee.
	var stop := mini(hit.hitstop_ticks, CombatConst.MAX_HITSTOP_TICKS)
	target.hitstop = maxi(target.hitstop, stop)
	if attacker and v.motion == HitVolume.Motion.ATTACHED:
		attacker.hitstop = maxi(attacker.hitstop, stop)
	var ko := target.hp <= 0.0
	sim.emit(BattleEvent.HIT, attacker if attacker else target, target.id, contact, {
		"damage": dmg,
		"eff": raw["eff"],
		"element": raw["element"],
		"ability": v.ability.id if v.ability else &"",
		"heavy": hit.hitstop_ticks >= 5,
		"ko": ko,
		"armored": flinch_immune,
		"sfx": hit.hit_sfx,
		"vfx": hit.hit_vfx,
		"dir": v.dir,
	})
	if ko:
		if attacker and v.ability:
			attacker.usage_for(v.ability.id)["ko"] += 1
		var kb_dir := _knockback_dir(v, target)
		MovementSystem.push(target, kb_dir, maxf(hit.knockback, 0.8))
		sim.knock_out(target, attacker)
		return
	StaminaSystem.interrupt(sim, target)
	if hit.hitstun_ticks > 0 and not flinch_immune:
		var mult := target.stats.passive.hitstun_taken_mult if target.stats.passive else 1.0
		StunRules.apply(sim, target, int(round(hit.hitstun_ticks * mult)), &"hit")
	if hit.knockback > 0.0 and hit.knockback_mode != HitSpec.KnockbackMode.NONE:
		var kb := hit.knockback * target.status_mult("knockback_taken_mult")
		if target.stats.passive:
			kb *= target.stats.passive.knockback_taken_mult
		if DashSystem.is_flinch_immune(target):
			kb = 0.0  # an armored dash holds its lane
		elif flinch_immune:
			kb *= 0.3
		MovementSystem.push(target, _knockback_dir(v, target), kb)
	for app in hit.statuses:
		StatusSystem.apply(sim, target, app, attacker)


## Periodic status damage (burn): no hitstun, but it does interrupt Focus.
static func apply_dot(sim: BattleSim, f: Fighter, s: StatusInstance) -> void:
	var dmg := s.def.tick_power * (s.source_attack / maxf(1.0, f.stats.defense)) * sim.ruleset.damage_scale
	dmg = maxf(0.5, snappedf(dmg, 0.1))
	f.hp = maxf(0.0, f.hp - dmg)
	f.record["damage_taken"] += dmg
	var source := sim.fighter_by_id(s.source_id)
	if source:
		source.record["damage_dealt"] += dmg
	sim.emit(BattleEvent.DOT, f, s.source_id, f.pos, {"damage": dmg, "status": s.def.id})
	if f.hp <= 0.0:
		sim.knock_out(f, source)
		return
	StaminaSystem.interrupt(sim, f)


## Knockback runs along a row or column like every other move: radial hits
## push along the dominant axis away from their centre.
static func _knockback_dir(v: HitVolume, target: Fighter) -> Vector2:
	var radial := v.hit.knockback_mode == HitSpec.KnockbackMode.RADIAL
	if radial or (v.shape == HitVolume.Shape.CIRCLE and v.motion == HitVolume.Motion.STATIC):
		var d := target.pos - v.pos
		return Cardinal.snap(d) if d.length_squared() > 1e-6 else Cardinal.snap(v.dir)
	return Cardinal.snap(v.dir)


static func _contact_point(v: HitVolume, target: Fighter) -> Vector2:
	var d := v.pos - target.pos
	if d.length_squared() < 1e-6:
		return target.pos
	return target.pos + d.normalized() * minf(target.hurt_radius(), d.length())
