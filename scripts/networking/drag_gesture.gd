class_name DragGesture
extends RefCounted
## One pointer's drag-to-dash gesture, in screen space (mouse or a finger).
##
##   press -> move past DRAG_START_PX  = aiming a dash (release to dash)
##   press -> release quickly in place = tap (basic attack)
##   press -> hold still for HOLD_MS   = hold (Focus on touch)
## Dragging back near the start point after aiming cancels the dash.

enum Phase { IDLE, PRESSED, AIMING, HOLDING }

const DRAG_START_PX := 14.0
const TAP_MAX_MS := 260
const HOLD_MS := 300

var phase: Phase = Phase.IDLE
var pointer := -1
var origin := Vector2.ZERO
var current := Vector2.ZERO
var started_ms := 0
var _farthest := 0.0


func is_down() -> bool:
	return phase != Phase.IDLE


func is_aiming() -> bool:
	return phase == Phase.AIMING


func is_holding() -> bool:
	return phase == Phase.HOLDING


## Dragged back to the start after aiming: releasing now does nothing.
func is_cancelled() -> bool:
	return phase == Phase.AIMING and _farthest > DRAG_START_PX * 2.5 and origin.distance_to(current) < DRAG_START_PX


func press(pos: Vector2, pointer_id: int = -1) -> void:
	phase = Phase.PRESSED
	pointer = pointer_id
	origin = pos
	current = pos
	started_ms = Time.get_ticks_msec()
	_farthest = 0.0


func move(pos: Vector2) -> void:
	if phase == Phase.IDLE:
		return
	current = pos
	var d := origin.distance_to(pos)
	_farthest = maxf(_farthest, d)
	if d > DRAG_START_PX and phase != Phase.AIMING:
		phase = Phase.AIMING


## Promotes a still press to a hold once HOLD_MS have passed. Returns true
## on the frame the hold begins.
func update_hold(now_ms: int) -> bool:
	if phase == Phase.PRESSED and now_ms - started_ms >= HOLD_MS:
		phase = Phase.HOLDING
		return true
	return false


## Ends the gesture: &"dash", &"tap", &"cancel" or &"none".
func release() -> StringName:
	var result := &"none"
	match phase:
		Phase.AIMING:
			result = &"cancel" if is_cancelled() else &"dash"
		Phase.PRESSED:
			if Time.get_ticks_msec() - started_ms <= TAP_MAX_MS:
				result = &"tap"
	phase = Phase.IDLE
	pointer = -1
	return result


func cancel() -> void:
	phase = Phase.IDLE
	pointer = -1
