class_name InputBuffer
extends RefCounted
## Remembers recent button presses for a few ticks so an input made slightly
## too early (during recovery, hitstop or stun) still comes out on the first
## frame it becomes legal. Each press is consumed at most once.

var window: int = CombatConst.INPUT_BUFFER_TICKS
var _press_tick: Dictionary = {}  # bit -> tick it was pressed


func record(pressed_bits: int, tick: int) -> void:
	if pressed_bits == 0:
		return
	var bit := 1
	while bit <= pressed_bits:
		if (pressed_bits & bit) != 0:
			_press_tick[bit] = tick
		bit <<= 1


func has(bit: int, tick: int) -> bool:
	if not _press_tick.has(bit):
		return false
	return tick - int(_press_tick[bit]) <= window


func consume(bit: int) -> void:
	_press_tick.erase(bit)


func clear() -> void:
	_press_tick.clear()
