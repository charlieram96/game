extends Node
## Dev only (battle scene with --drag-demo): plays scripted mouse drags as
## player 1, so the aim preview, dashes and rams can be captured with --seq
## and reviewed frame by frame. Each step drags from the creature toward a
## cell `cells` away along `dir`, holds, then releases (or drags back to
## cancel).

const STEPS := [
	{"dir": 0, "cells": 3},
	{"dir": 3, "cells": 2},
	{"dir": 0, "cells": 5},
	{"dir": 1, "cells": 4, "cancel": true},
	{"dir": 2, "cells": 4},
	{"dir": 1, "cells": 3},
]
const DRAG_FRAMES := 14
const HOLD_FRAMES := 16
const GAP_FRAMES := 26

var scene: Node  # battle_scene.gd
var _step := 0
var _frame := 0
var _from := Vector2.ZERO
var _to := Vector2.ZERO


func _process(_delta: float) -> void:
	if scene == null or scene.sim == null or _step >= STEPS.size():
		return
	var sim: BattleSim = scene.sim
	if sim.tick < 200:
		return
	var s: Dictionary = STEPS[_step]
	var src: LocalInputSource = scene.player_input
	var cam: BattleCamera = scene.view.camera
	var f := sim.active_fighter(0)
	if _frame == 0:
		var dir := Cardinal.from_index(int(s["dir"]))
		var target := f.pos + dir * float(s["cells"])
		_from = cam.unproject_position(Vector3(f.pos.x, 0.0, f.pos.y))
		_to = cam.unproject_position(Vector3(target.x, 0.0, target.y))
		_button(src, _from, true)
	elif _frame <= DRAG_FRAMES:
		var u := float(_frame) / DRAG_FRAMES
		_move(src, _from.lerp(_to, 1.0 - pow(1.0 - u, 2.0)))
	elif _frame <= DRAG_FRAMES + HOLD_FRAMES:
		if bool(s.get("cancel", false)):
			var u2 := float(_frame - DRAG_FRAMES) / HOLD_FRAMES
			_move(src, _to.lerp(_from, minf(1.0, u2 * 1.5)))
	elif _frame == DRAG_FRAMES + HOLD_FRAMES + 1:
		var end := _from if bool(s.get("cancel", false)) else _to
		_button(src, end, false)
	elif _frame > DRAG_FRAMES + HOLD_FRAMES + GAP_FRAMES:
		_step += 1
		_frame = -1
	_frame += 1


func _button(src: LocalInputSource, pos: Vector2, pressed: bool) -> void:
	var ev := InputEventMouseButton.new()
	ev.button_index = MOUSE_BUTTON_LEFT
	ev.position = pos
	ev.pressed = pressed
	src.handle_input(ev)


func _move(src: LocalInputSource, pos: Vector2) -> void:
	var ev := InputEventMouseMotion.new()
	ev.position = pos
	ev.button_mask = MOUSE_BUTTON_MASK_LEFT
	src.handle_input(ev)
