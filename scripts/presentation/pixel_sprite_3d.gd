class_name PixelSprite3D
extends MeshInstance3D
## A pixel-art sprite standing in the 3D world (see shaders/pixel_sprite).
## Plays manifest animations by name + facing direction, or is driven frame
## by frame (attack phases). Includes hit flash, outline glow and dissolve.

const SHADER := preload("res://shaders/pixel_sprite.gdshader")

signal animation_finished(anim: String)

var sheet: SpriteSheet
var current_anim: String = ""
var current_dir: String = "s"
var playing := true
var speed_scale := 1.0
var _resolved: String = ""
var _flip := false
var _time := 0.0
var _frame_idx := 0
var _finished := false
var _mat: ShaderMaterial


func _init() -> void:
	mesh = QuadMesh.new()
	_mat = ShaderMaterial.new()
	_mat.shader = SHADER
	material_override = _mat
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	extra_cull_margin = 2.0


func set_sheet(s: SpriteSheet) -> void:
	sheet = s
	if s == null or not s.valid:
		_use_placeholder()
		return
	_mat.set_shader_parameter("sheet", s.texture)
	# HD-2D lighting through the sheet's normal map, when it has one.
	_mat.set_shader_parameter("normal_sheet", s.normal_texture)
	_mat.set_shader_parameter("has_normal_map", s.normal_texture != null)
	for k: String in s.lighting:
		_mat.set_shader_parameter(k, s.lighting[k])
	_mat.set_shader_parameter("sheet_size", s.texture.get_size())
	_mat.set_shader_parameter("frame_size", s.frame_size)
	_mat.set_shader_parameter("columns", float(s.columns))
	_mat.set_shader_parameter("pivot", s.pivot)
	_mat.set_shader_parameter("pixel_size", 1.0 / s.pixels_per_unit)
	_mat.set_shader_parameter("outline_texels", s.pixels_per_unit / 24.0)
	_update_aabb()
	if current_anim != "":
		var a := current_anim
		current_anim = ""
		play(a, current_dir)


## Draw with another sprite shader that takes the same sheet parameters
## (e.g. the translucent ghost used for dash previews and afterimages).
func use_shader(shader: Shader) -> void:
	_mat.shader = shader
	if sheet:
		set_sheet(sheet)


func load_manifest(manifest_path: String) -> void:
	set_sheet(SpriteSheet.load_sheet(manifest_path))


func load_texture(png_path: String) -> void:
	set_sheet(SpriteSheet.from_texture(png_path))


func set_param(param: String, value: Variant) -> void:
	_mat.set_shader_parameter(param, value)


func get_param(param: String) -> Variant:
	return _mat.get_shader_parameter(param)


func set_upright(value: bool) -> void:
	_mat.set_shader_parameter("upright", value)


func play(anim: String, dir: String = "", restart: bool = false) -> void:
	if dir == "":
		dir = current_dir
	if anim == current_anim and dir == current_dir and not restart:
		return
	current_anim = anim
	current_dir = dir
	if sheet == null or not sheet.valid:
		return
	var r := sheet.resolve(anim, dir)
	var changed_anim: bool = r[0] != _resolved
	_resolved = r[0]
	_flip = r[1]
	_mat.set_shader_parameter("flip_h", _flip)
	if changed_anim or restart:
		_time = 0.0
		_frame_idx = 0
		_finished = false
	playing = true
	_apply_frame()


## Show a specific frame index of an animation (phase-driven attacks).
func show_frame(anim: String, dir: String, index: int) -> void:
	current_anim = anim
	current_dir = dir
	playing = false
	if sheet == null or not sheet.valid:
		return
	var r := sheet.resolve(anim, dir)
	_resolved = r[0]
	_flip = r[1]
	_mat.set_shader_parameter("flip_h", _flip)
	var frames := sheet.frames_of(_resolved)
	_frame_idx = clampi(index, 0, frames.size() - 1)
	_apply_frame()


func has_animation(anim: String) -> bool:
	return sheet != null and sheet.valid and sheet.resolve(anim, "s")[0] != ""


func frame_count_of(anim: String) -> int:
	if sheet == null or not sheet.valid:
		return 1
	return sheet.frames_of(sheet.resolve(anim, "s")[0]).size()


func _process(delta: float) -> void:
	if not playing or sheet == null or not sheet.valid or _resolved == "" or _finished:
		return
	var fps := sheet.fps_of(_resolved) * speed_scale
	var frames := sheet.frames_of(_resolved)
	if frames.size() <= 1:
		return
	_time += delta * fps
	var idx := int(_time)
	if sheet.loops(_resolved):
		idx = idx % frames.size()
	elif idx >= frames.size():
		idx = frames.size() - 1
		_finished = true
		animation_finished.emit(current_anim)
	if idx != _frame_idx:
		_frame_idx = idx
		_apply_frame()


func _apply_frame() -> void:
	if _resolved == "":
		return
	var frames := sheet.frames_of(_resolved)
	if frames.is_empty():
		return
	_mat.set_shader_parameter("frame", float(frames[clampi(_frame_idx, 0, frames.size() - 1)]))


func _update_aabb() -> void:
	if sheet == null:
		return
	var w := sheet.frame_size.x / sheet.pixels_per_unit
	var h := sheet.frame_size.y / sheet.pixels_per_unit * 2.0
	custom_aabb = AABB(Vector3(-w, -0.5, -w), Vector3(w * 2.0, h + 1.0, w * 2.0))


## Procedural stand-in so missing art never breaks a scene.
func _use_placeholder() -> void:
	var img := Image.create(32, 40, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	for y in range(6, 38):
		for x in range(6, 26):
			var dx := (x - 16.0) / 10.0
			var dy := (y - 24.0) / 16.0
			if dx * dx + dy * dy <= 1.0:
				img.set_pixel(x, y, Color(0.85, 0.5, 0.75) if dx * dx + dy * dy < 0.8 else Color(0.25, 0.1, 0.25))
	var tex := ImageTexture.create_from_image(img)
	_mat.set_shader_parameter("sheet", tex)
	_mat.set_shader_parameter("has_normal_map", false)
	_mat.set_shader_parameter("sheet_size", Vector2(32, 40))
	_mat.set_shader_parameter("frame_size", Vector2(32, 40))
	_mat.set_shader_parameter("columns", 1.0)
	_mat.set_shader_parameter("pivot", Vector2(16, 38))
	_mat.set_shader_parameter("pixel_size", 1.0 / 24.0)
	_mat.set_shader_parameter("frame", 0.0)
