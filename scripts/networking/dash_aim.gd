class_name DashAim
extends RefCounted
## The dash a local player is aiming right now (drag, held direction or
## stick), published by the input source for the preview to draw. Only
## presentation reads it: the simulation gets the dash on release.

var active := false
var dir_index := -1
var cells := 0
## Dragged back to the start: releasing will not dash.
var cancelled := false
## &"drag" (mouse or finger) or &"charge" (held key / stick: hold longer to go farther).
var device: StringName = &""
## 0..1 progress toward the next cell while charging (for a filling pip).
var charge_fraction := 0.0


func clear() -> void:
	active = false
	dir_index = -1
	cells = 0
	cancelled = false
	device = &""
	charge_fraction = 0.0
