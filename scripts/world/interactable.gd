class_name Interactable
extends Node3D
## Something the explorer can talk to or inspect. The story director
## connects to `used` (or sets `action`) to decide what happens.

signal used(by: Node3D)

@export var prompt := "Inspect"
@export var radius := 1.0
@export var enabled := true
## Optional dialogue id played automatically when no handler is connected.
@export var dialogue_id := ""
var action: Callable


func _ready() -> void:
	add_to_group(&"interactable")


func interact(by: Node3D) -> void:
	if not enabled:
		return
	used.emit(by)
	if action.is_valid():
		action.call(by)


func prompt_position() -> Vector3:
	return global_position + Vector3(0, 2.0, 0)
