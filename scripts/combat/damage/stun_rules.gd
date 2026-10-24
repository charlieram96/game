class_name StunRules
extends RefCounted
## Every stun (hit flinch, dash-through, repel, guard break, stagger) goes
## through here so combo protection is applied uniformly:
##   * stuns landing within STUN_CHAIN_WINDOW of the previous one are
##     shortened (100% -> 75% -> 50%);
##   * the third chained stun grants "Steadfast": stun immunity for a while;
##   * for a few ticks after any stun ends, new stuns are ignored (wake-up
##     grace), so the victim always gets at least one buffered action out.
## Together these make infinite stun loops impossible.

const SM := FighterSM.State


## Applies a stun and returns the ticks actually applied (0 if resisted).
static func apply(sim: BattleSim, f: Fighter, base_ticks: int, kind: StringName, force: bool = false) -> int:
	if f.is_ko() or base_ticks <= 0:
		return 0
	if not force:
		if f.steadfast > 0 or f.status_flag("stun_immune") or f.wakeup_grace > 0:
			sim.emit(BattleEvent.STUN_RESISTED, f, -1, f.pos, {"kind": kind})
			return 0
	var chained := f.state == SM.STUNNED or (sim.tick - f.last_stun_end_tick) <= CombatConst.STUN_CHAIN_WINDOW_TICKS
	var chain := f.stun_chain + 1 if chained else 1
	var mults := CombatConst.STUN_CHAIN_MULTS
	var mult: float = mults[mini(chain - 1, mults.size() - 1)]
	var ticks := maxi(CombatConst.MIN_STUN_TICKS, int(round(base_ticks * mult)))
	if force:
		ticks = base_ticks
	f.stun_chain = chain
	if chain >= CombatConst.STEADFAST_CHAIN:
		f.steadfast_pending = true
	var was_focusing := FighterSM.is_focusing(f.state)
	AbilitySystem.interrupt(sim, f)
	f.vel = Vector2.ZERO
	f.stun_kind = kind
	sim.set_state(f, SM.STUNNED, ticks)
	if was_focusing:
		sim.emit(BattleEvent.FOCUS_INTERRUPTED, f, -1, f.pos, {})
	sim.emit(BattleEvent.STUN, f, -1, f.pos, {"ticks": ticks, "kind": kind, "chain": chain})
	return ticks


## Called when a stun runs out.
static func on_stun_end(sim: BattleSim, f: Fighter) -> void:
	f.last_stun_end_tick = sim.tick
	f.wakeup_grace = CombatConst.WAKEUP_GRACE_TICKS
	if f.steadfast_pending:
		f.steadfast_pending = false
		f.steadfast = CombatConst.STEADFAST_TICKS
		f.stun_chain = 0
