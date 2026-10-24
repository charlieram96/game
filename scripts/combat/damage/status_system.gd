class_name StatusSystem
extends RefCounted
## Applies, ticks and expires status effects.


static func apply(sim: BattleSim, f: Fighter, app: StatusApplication, source: Fighter) -> void:
	if app == null or app.status == null or f.is_ko():
		return
	var def := app.status
	var duration := app.resolved_duration()
	for s in f.statuses:
		if s.def.id == def.id:
			match def.stacking:
				StatusEffectDefinition.Stacking.REFRESH:
					s.ticks_left = maxi(s.ticks_left, duration)
				StatusEffectDefinition.Stacking.EXTEND:
					s.ticks_left += duration
				_:
					pass
			s.duration = maxi(s.duration, s.ticks_left)
			return
	var inst := StatusInstance.new()
	inst.def = def
	inst.ticks_left = duration
	inst.duration = duration
	inst.source_id = source.id if source else -1
	inst.source_attack = source.stats.attack if source else 10.0
	f.statuses.append(inst)
	sim.emit(BattleEvent.STATUS_APPLIED, f, inst.source_id, f.pos, {"status": def.id, "ticks": duration})


static func tick(sim: BattleSim, f: Fighter) -> void:
	if f.statuses.is_empty():
		return
	for s in f.statuses.duplicate():
		if s.def.tick_interval_ticks > 0:
			s.interval_counter += 1
			if s.interval_counter >= s.def.tick_interval_ticks:
				s.interval_counter = 0
				DamageSystem.apply_dot(sim, f, s)
				if f.is_ko():
					return
		s.ticks_left -= 1
		if s.ticks_left <= 0:
			f.statuses.erase(s)
			sim.emit(BattleEvent.STATUS_ENDED, f, -1, f.pos, {"status": s.def.id})


## Switching out clears statuses that don't persist across switches.
static func clear_on_switch(sim: BattleSim, f: Fighter) -> void:
	for s in f.statuses.duplicate():
		if not s.def.persists_on_switch:
			f.statuses.erase(s)
			sim.emit(BattleEvent.STATUS_ENDED, f, -1, f.pos, {"status": s.def.id})
