class_name ExplorationCamera
extends Camera3D
## HD-2D exploration camera: perspective with a narrow field of view and a
## fixed angle (never rotates), smooth follow with look-ahead, gentle idle
## sway, region clamping and scripted focus for cutscenes.

const PITCH_DEG := 32.0
const DISTANCE := 23.0

var target: Node3D
var bounds := Rect2(-27, -30, 54, 50)
var look_ahead := 1.4
var smoothing := 4.5
var override_point: Variant = null  # Vector3 while a cutscene holds focus
var _focus := Vector3.ZERO
var _vel := Vector3.ZERO
var _trauma := 0.0
var _t := 0.0


func _ready() -> void:
	fov = 30.0
	near = 0.5
	far = 160.0
	rotation = Vector3(deg_to_rad(-PITCH_DEG), 0.0, 0.0)
	RenderingServer.global_shader_parameter_set("sprite_stretch", 1.0 / cos(deg_to_rad(PITCH_DEG)))
	if target:
		_focus = target.global_position
		_place(0.0)


func snap() -> void:
	if target:
		_focus = _clamp(target.global_position)
	_place(0.0)


func shake(amount: float) -> void:
	_trauma = clampf(_trauma + amount * Settings.screen_shake, 0.0, 1.0)


func _process(delta: float) -> void:
	_t += delta
	if target:
		var vp := get_viewport().get_visible_rect().size
		var sp := unproject_position(target.global_position + Vector3(0, 0.9, 0))
		RenderingServer.global_shader_parameter_set("occluder_uv", sp / vp)
		RenderingServer.global_shader_parameter_set("occluder_z", target.global_position.z)
		RenderingServer.global_shader_parameter_set("occluder_active", 1.0)
	var goal := _focus
	if override_point != null:
		goal = override_point
	elif target:
		goal = target.global_position
		if target is CharacterBody3D:
			var v: Vector3 = (target as CharacterBody3D).velocity
			goal += Vector3(v.x, 0, v.z).normalized() * look_ahead * clampf(v.length() / 5.0, 0.0, 1.0)
	goal = _clamp(goal)
	_focus = _focus.lerp(goal, 1.0 - exp(-smoothing * delta))
	_place(delta)


func _clamp(p: Vector3) -> Vector3:
	return Vector3(clampf(p.x, bounds.position.x, bounds.end.x), 0.0, clampf(p.z, bounds.position.y, bounds.end.y))


func _place(delta: float) -> void:
	var pitch := deg_to_rad(PITCH_DEG)
	var back := Vector3(0.0, sin(pitch), cos(pitch)) * DISTANCE
	var sway := Vector3(sin(_t * 0.35) * 0.08, sin(_t * 0.5) * 0.05, 0.0)
	position = _focus + back + sway
	if _trauma > 0.0:
		var a := _trauma * _trauma * 0.35
		h_offset = a * sin(_t * 47.0)
		v_offset = a * cos(_t * 39.0)
		_trauma = maxf(0.0, _trauma - delta * 1.6)
	else:
		h_offset = 0.0
		v_offset = 0.0


## Smoothly moves the view to a point (cutscenes). Awaitable.
func focus_on(p: Vector3, seconds: float = 1.0) -> void:
	override_point = _clamp(p)
	await get_tree().create_timer(seconds).timeout


func release_focus() -> void:
	override_point = null


## Screen position of a world point (for UI prompts).
func screen_of(p: Vector3) -> Vector2:
	return unproject_position(p)
