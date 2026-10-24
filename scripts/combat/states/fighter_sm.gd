class_name FighterSM
extends RefCounted
## Explicit creature combat states and the table of legal transitions.
##
## The simulation never assigns a state directly: it calls
## BattleSim._set_state(), which consults can_transition() and refuses illegal
## moves (e.g. STUNNED -> DASH_START). Keeping the table here makes the rules
## reviewable in one place and testable in isolation.

enum State {
	IDLE,
	MOVING,  ## Unused since movement became dash-only; kept so state ids stay stable.
	FOCUS_ENTER,
	FOCUSING,
	FOCUS_EXIT,
	DASH_START,
	DASH_ACTIVE,
	DASH_RECOVERY,
	ATTACK_START,
	ATTACK_ACTIVE,
	ATTACK_RECOVERY,
	GUARDING,
	STUNNED,
	SWITCHING,
	KNOCKED_OUT,
}

const S := State

## from -> list of allowed destinations. Anything not listed is illegal.
static var _allowed: Dictionary = {
	S.IDLE: [S.FOCUS_ENTER, S.DASH_START, S.ATTACK_START, S.GUARDING, S.STUNNED, S.SWITCHING, S.KNOCKED_OUT],
	S.MOVING: [S.IDLE, S.STUNNED, S.KNOCKED_OUT],
	# Focus can only be left through its exit commitment, or by being hit.
	S.FOCUS_ENTER: [S.FOCUSING, S.FOCUS_EXIT, S.IDLE, S.STUNNED, S.KNOCKED_OUT],
	S.FOCUSING: [S.FOCUS_EXIT, S.IDLE, S.STUNNED, S.KNOCKED_OUT],
	S.FOCUS_EXIT: [S.IDLE, S.STUNNED, S.KNOCKED_OUT],
	# A dash in startup can still be interrupted; once active it is committed
	# (only a guard repel or a dash clash stops it).
	S.DASH_START: [S.DASH_ACTIVE, S.STUNNED, S.KNOCKED_OUT],
	S.DASH_ACTIVE: [S.DASH_RECOVERY, S.STUNNED, S.KNOCKED_OUT],
	# Landing recovery can chain straight into the next dash.
	S.DASH_RECOVERY: [S.IDLE, S.DASH_START, S.STUNNED, S.KNOCKED_OUT],
	S.ATTACK_START: [S.ATTACK_ACTIVE, S.STUNNED, S.KNOCKED_OUT],
	S.ATTACK_ACTIVE: [S.ATTACK_RECOVERY, S.STUNNED, S.KNOCKED_OUT],
	# Recovery is only cancellable when the ability explicitly allows it
	# (dash-cancel window, combo chain); the sim checks those rules.
	S.ATTACK_RECOVERY: [S.IDLE, S.DASH_START, S.ATTACK_START, S.STUNNED, S.KNOCKED_OUT],
	S.GUARDING: [S.IDLE, S.STUNNED, S.KNOCKED_OUT],
	S.STUNNED: [S.IDLE, S.STUNNED, S.KNOCKED_OUT],
	# A switch in progress can be interrupted by a hit (it is a real commitment).
	S.SWITCHING: [S.IDLE, S.STUNNED, S.KNOCKED_OUT],
	S.KNOCKED_OUT: [],
}


static func can_transition(from: State, to: State) -> bool:
	var allowed: Array = _allowed.get(from, [])
	return allowed.has(to)


static func state_name(s: State) -> String:
	return State.keys()[s]


## States in which a creature accepts new commands (dash, attack, ...).
static func is_actionable(s: State) -> bool:
	return s == S.IDLE


static func is_attacking(s: State) -> bool:
	return s == S.ATTACK_START or s == S.ATTACK_ACTIVE or s == S.ATTACK_RECOVERY


static func is_dashing(s: State) -> bool:
	return s == S.DASH_START or s == S.DASH_ACTIVE or s == S.DASH_RECOVERY


static func is_focusing(s: State) -> bool:
	return s == S.FOCUS_ENTER or s == S.FOCUSING or s == S.FOCUS_EXIT


## States where the creature is committed and cannot switch out.
static func blocks_switch(s: State) -> bool:
	return not is_actionable(s)
