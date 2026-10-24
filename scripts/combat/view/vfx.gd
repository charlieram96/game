class_name Vfx
extends MeshInstance3D
## One visual effect: plays an effects sheet once (or loops), as a camera-
## facing billboard or flat on the ground, then frees itself. Missing sheets
## fall back to a small particle burst so gameplay feedback never disappears.

const SHADER := preload("res://shaders/vfx_sprite.gdshader")
const DIR := "res://assets/effects/"

## id -> {sheet, height (above ground), ground (flat), glow, scale, rotate}
const DEFS := {
	&"hit_spark": {"sheet": "hit_spark", "height": 0.55, "glow": 0.6},
	&"hit_heavy": {"sheet": "hit_heavy", "height": 0.6, "glow": 0.8, "scale": 1.1},
	&"dust_puff": {"sheet": "dust_puff", "height": 0.05},
	&"ember_impact": {"sheet": "ember_impact", "height": 0.5, "glow": 1.0},
	&"flash_strike": {"sheet": "flash_strike", "height": 0.55, "glow": 0.9, "rotate": true},
	&"fire_pillar": {"sheet": "fire_pillar", "height": 0.0, "glow": 1.0},
	&"rock_burst": {"sheet": "rock_burst", "height": 0.4},
	&"fault_spike": {"sheet": "fault_spike", "height": 0.0},
	&"perfect_flash": {"sheet": "perfect_flash", "height": 0.6, "glow": 1.4},
	&"guard_break": {"sheet": "guard_break", "height": 0.6, "glow": 0.6},
	&"ko_burst": {"sheet": "ko_burst", "height": 0.6, "glow": 1.0, "scale": 1.3},
	&"trust_motes": {"sheet": "trust_motes", "height": 1.0, "glow": 0.8},
	&"sigil_glow": {"sheet": "sigil_glow", "height": 0.4, "glow": 1.2},
	&"cinder_arc": {"sheet": "cinder_arc", "ground": true, "glow": 1.0, "rotate": true},
	&"heat_ring": {"sheet": "heat_ring", "ground": true, "glow": 1.2},
	&"shockwave": {"sheet": "shockwave", "ground": true, "glow": 0.3, "scale": 1.0},
	&"ground_crack": {"sheet": "ground_crack", "ground": true},
	&"scorch": {"sheet": "scorch", "ground": true},
}

var sheet: SpriteSheet
var anim := ""
var loop := false
var speed := 1.0
var _time := 0.0
var _frames: Array = []
var _fps := 12.0
var _mat: ShaderMaterial


static func spawn(parent: Node, id: StringName, pos: Vector3, dir: Vector2 = Vector2.RIGHT, tint: Color = Color.WHITE, scale_mult: float = 1.0, looping: bool = false) -> Node3D:
	var def: Dictionary = DEFS.get(id, {})
	var path := DIR + String(def.get("sheet", id)) + ".json"
	var s := SpriteSheet.load_sheet(path)
	if not s.valid:
		return null if looping else _fallback(parent, pos, tint)
	var v := Vfx.new()
	v.sheet = s
	v.loop = looping
	parent.add_child(v)
	v.position = pos + Vector3(0, float(def.get("height", 0.4)), 0)
	var ground := bool(def.get("ground", false))
	if ground:
		v.position.y = 0.03
	var anim_name: String = s.resolve("loop" if looping else "play", "s")[0]
	if anim_name == "":
		anim_name = s.animations.keys()[0] if not s.animations.is_empty() else ""
	v._configure(anim_name, ground, dir, tint, float(def.get("glow", 0.0)), float(def.get("scale", 1.0)) * scale_mult, bool(def.get("rotate", false)))
	return v


static func _fallback(parent: Node, pos: Vector3, tint: Color) -> Node3D:
	var p := CPUParticles3D.new()
	p.one_shot = true
	p.emitting = true
	p.amount = 10
	p.lifetime = 0.35
	p.explosiveness = 1.0
	p.direction = Vector3.UP
	p.spread = 180.0
	p.initial_velocity_min = 1.5
	p.initial_velocity_max = 3.0
	p.gravity = Vector3(0, -4, 0)
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE * 0.08
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.albedo_color = tint
	quad.material = m
	p.mesh = quad
	parent.add_child(p)
	p.position = pos + Vector3(0, 0.5, 0)
	p.finished.connect(p.queue_free)
	return p


func _configure(anim_name: String, ground: bool, dir: Vector2, tint: Color, glow: float, scale_mult: float, rotate: bool) -> void:
	anim = anim_name
	mesh = QuadMesh.new()
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_mat = ShaderMaterial.new()
	_mat.shader = SHADER
	_mat.set_shader_parameter("sheet", sheet.texture)
	_mat.set_shader_parameter("sheet_size", sheet.texture.get_size())
	_mat.set_shader_parameter("frame_size", sheet.frame_size)
	_mat.set_shader_parameter("columns", float(sheet.columns))
	_mat.set_shader_parameter("pivot", sheet.frame_size * 0.5 if ground else sheet.pivot)
	_mat.set_shader_parameter("pixel_size", 1.0 / sheet.pixels_per_unit)
	_mat.set_shader_parameter("flat_on_ground", ground)
	_mat.set_shader_parameter("modulate", tint)
	_mat.set_shader_parameter("additive_glow", glow)
	_mat.set_shader_parameter("scale", scale_mult)
	if rotate:
		var angle: float
		if ground:
			angle = atan2(-dir.y, dir.x)
		else:
			angle = screen_angle(dir)
		_mat.set_shader_parameter("rotation", angle)
	material_override = _mat
	extra_cull_margin = 4.0
	_frames = sheet.frames_of(anim)
	_fps = sheet.fps_of(anim)
	if not loop and not sheet.loops(anim):
		loop = false
	_set_frame(0)


## Screen-space angle of a ground direction for the fixed-yaw cameras.
static func screen_angle(dir: Vector2, pitch_deg: float = 44.0) -> float:
	return atan2(-dir.y * sin(deg_to_rad(pitch_deg)), dir.x)


func set_rotation_angle(angle: float) -> void:
	if _mat:
		_mat.set_shader_parameter("rotation", angle)


func set_tint(tint: Color) -> void:
	if _mat:
		_mat.set_shader_parameter("modulate", tint)


func _process(delta: float) -> void:
	if _frames.is_empty():
		queue_free()
		return
	_time += delta * _fps * speed
	var idx := int(_time)
	if idx >= _frames.size():
		if loop:
			idx = idx % _frames.size()
		else:
			queue_free()
			return
	_set_frame(idx)


func _set_frame(i: int) -> void:
	if _frames.is_empty():
		return
	_mat.set_shader_parameter("frame", float(_frames[clampi(i, 0, _frames.size() - 1)]))


## Little particle helpers -------------------------------------------------------------

static func burst(parent: Node, pos: Vector3, color: Color, amount: int = 12, speed: float = 2.5, size: float = 0.07, lifetime: float = 0.45, gravity: float = -5.0) -> CPUParticles3D:
	var p := CPUParticles3D.new()
	p.one_shot = true
	p.amount = amount
	p.lifetime = lifetime
	p.explosiveness = 0.95
	p.direction = Vector3.UP
	p.spread = 75.0
	p.initial_velocity_min = speed * 0.5
	p.initial_velocity_max = speed
	p.gravity = Vector3(0, gravity, 0)
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE * size
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.albedo_color = color
	m.emission_enabled = true
	m.emission = color
	m.emission_energy_multiplier = 1.4
	quad.material = m
	p.mesh = quad
	parent.add_child(p)
	p.position = pos
	p.emitting = true
	p.finished.connect(p.queue_free)
	return p


static func trail(color: Color, size: float = 0.06, amount: int = 16, lifetime: float = 0.35) -> CPUParticles3D:
	var p := CPUParticles3D.new()
	p.amount = amount
	p.lifetime = lifetime
	p.local_coords = false
	p.direction = Vector3.UP
	p.spread = 180.0
	p.initial_velocity_min = 0.1
	p.initial_velocity_max = 0.5
	p.gravity = Vector3(0, 0.6, 0)
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE * size
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.albedo_color = color
	m.emission_enabled = true
	m.emission = color
	m.emission_energy_multiplier = 1.6
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	quad.material = m
	p.mesh = quad
	var g := Gradient.new()
	g.set_color(0, Color(1, 1, 1, 1))
	g.set_color(1, Color(1, 1, 1, 0))
	p.color_ramp = g
	return p
