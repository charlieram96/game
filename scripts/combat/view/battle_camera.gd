class_name BattleCamera
extends Camera3D
## Fixed overhead orthographic battle camera.
##
## The view is angled for depth, but the camera never rotates during a match
## and uses an orthographic projection, so creatures keep the same apparent
## size everywhere and on-screen distances are uniform per axis. Shake is a
## pure translation (h/v offset), never a rotation.

const PITCH_DEG := 44.0

var arena_size := Vector2(16, 10)
var margin := Vector2(2.4, 2.6)
var focus := Vector3.ZERO
var _trauma := 0.0
var _shake_time := 0.0


func _ready() -> void:
	projection = PROJECTION_ORTHOGONAL
	keep_aspect = KEEP_HEIGHT
	near = 0.1
	far = 120.0
	rotation = Vector3(deg_to_rad(-PITCH_DEG), 0.0, 0.0)
	get_viewport().size_changed.connect(_reframe)
	_reframe()
	RenderingServer.global_shader_parameter_set("sprite_stretch", 1.0 / cos(deg_to_rad(PITCH_DEG)))
	RenderingServer.global_shader_parameter_set("occluder_active", 0.0)


func setup(p_arena_size: Vector2, p_focus: Vector3 = Vector3.ZERO) -> void:
	arena_size = p_arena_size
	focus = p_focus
	_reframe()


func _reframe() -> void:
	var vp := get_viewport().get_visible_rect().size
	var aspect := vp.x / maxf(1.0, vp.y)
	var pitch := deg_to_rad(PITCH_DEG)
	var need_w := arena_size.x + margin.x * 2.0
	var need_depth := arena_size.y + margin.y * 2.0
	# Ortho "size" is the visible height; ground depth appears scaled by sin(pitch).
	size = maxf(need_depth * sin(pitch), need_w / aspect)
	var back := Vector3(0.0, sin(pitch), cos(pitch)) * 40.0
	position = focus + back + Vector3(0.0, 0.0, -0.45)


func add_trauma(amount: float) -> void:
	_trauma = clampf(_trauma + amount * Settings.screen_shake, 0.0, 1.0)


func _process(delta: float) -> void:
	if _trauma <= 0.0:
		h_offset = 0.0
		v_offset = 0.0
		return
	_shake_time += delta * 40.0
	var amp := _trauma * _trauma * 0.35
	h_offset = amp * sin(_shake_time * 1.7) * cos(_shake_time * 0.9)
	v_offset = amp * cos(_shake_time * 1.3) * sin(_shake_time * 1.1)
	_trauma = maxf(0.0, _trauma - delta * 2.2)


## World point on the ground plane (y = 0) under a screen position.
func ground_point(screen_pos: Vector2) -> Vector3:
	var from := project_ray_origin(screen_pos)
	var dir := project_ray_normal(screen_pos)
	if absf(dir.y) < 1e-5:
		return Vector3.ZERO
	var t := -from.y / dir.y
	return from + dir * t
