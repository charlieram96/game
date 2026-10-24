class_name MossfordBuilder
extends RefCounted
## Builds the first region: Mossford village, the stream and bridge, the
## Glimmerwood clearing, the north meadow and pond, the training yard, the
## Ringstones and the Dawn Shrine. Returns named anchor points used by the
## story director. Layout is data in this file; art comes from assets/.
##
## Coordinates: X = east, Z = south (the camera looks north).

const STREAM := [Vector2(-15, -44), Vector2(-14, -26), Vector2(-16.5, -14), Vector2(-15, -4), Vector2(-14.6, 4), Vector2(-16, 14), Vector2(-18.5, 32)]
const STREAM_WIDTH := 3.0
const BRIDGE_Z := 2.0
const POND_CENTER := Vector2(-6, -12)
const POND_RADIUS := 2.6
const CLEARING := Vector2(-25, -2)
const RINGSTONES := Vector2(17, -16)
const SHRINE := Vector2(-1, -28)
const TRAINING := Rect2(17, 3, 10, 10)
const BOUNDS := Rect2(-34, -36, 68, 62)

var root: Node3D
var statics: StaticBody3D
var anchors: Dictionary = {}
var lantern_lights: Array[OmniLight3D] = []
var window_mats: Array[StandardMaterial3D] = []
var fireflies: Array[CPUParticles3D] = []
var campfire: PixelSprite3D
var campfire_light: OmniLight3D
var mural: MeshInstance3D
var mural_glow_mat: StandardMaterial3D
var splat_image: Image
var splat_rect := Rect2(-40, -42, 80, 74)
var rng := RandomNumberGenerator.new()
var _tree_items: Dictionary = {}  # tree name -> Array of [pos, 0, scale]
var _blocked: Array = []  # [Vector2 center, float radius] no-tree zones


func build(parent: Node3D) -> Node3D:
	rng.seed = 1977
	root = Node3D.new()
	root.name = "Mossford"
	parent.add_child(root)
	statics = StaticBody3D.new()
	statics.name = "Colliders"
	root.add_child(statics)
	_anchors()
	_terrain()
	_water()
	_bridge()
	_village()
	_training_yard()
	_ringstones()
	_shrine()
	_glimmerwood()
	_meadow()
	_trees()
	_ground_cover()
	_boundary()
	_ambient()
	return root


func _anchors() -> void:
	anchors = {
		"spawn_home": Vector3(-9, 0, 18.9),
		"oak": Vector3(0.5, 0, 7.0),
		"hesper_square": Vector3(1.8, 0, 9.2),
		"corin_enter": Vector3(14, 0, 9.5),
		"corin_square": Vector3(3.6, 0, 9.6),
		"baker": Vector3(-7.2, 0, 7.6),
		"farmer": Vector3(12.2, 0, 7.2),
		"bridge": Vector3(-14.8, 0, BRIDGE_Z),
		"clearing": Vector3(CLEARING.x, 0, CLEARING.y),
		"clearing_entry": Vector3(-19.5, 0, 0.5),
		"log": Vector3(-27.2, 0, -5.0),
		"log_mouth": Vector3(-25.6, 0, -4.6),
		"fire_ring": Vector3(-24.0, 0, -1.4),
		"sit_spot": Vector3(-24.0, 0, 0.0),
		"snare": Vector3(-22.4, 0, -4.4),
		"moss_1": Vector3(-29.6, 0, 2.4),
		"moss_2": Vector3(-20.6, 0, -7.8),
		"moss_3": Vector3(-28.6, 0, -9.6),
		"hesper_training": Vector3(19.2, 0, 8.6),
		"training_gate": Vector3(16.6, 0, 9.0),
		"arena_gate": Vector3(13.4, 0, -10.6),
		"corin_arena": Vector3(16.4, 0, -14.6),
		"hesper_arena": Vector3(14.6, 0, -12.6),
		"shrine_front": Vector3(-1, 0, -23.6),
		"shrine_mural": Vector3(-1, 0, -31.0),
		"shrine_hesper": Vector3(-2.6, 0, -26.4),
		"shrine_corin": Vector3(0.8, 0, -26.2),
		"shrine_player": Vector3(-1, 0, -25.4),
		"sigil_spot": Vector3(4.6, 2.6, -31.2),
		"mossling_home": Vector3(-2.5, 0, -8.0),
		"signpost": Vector3(-3.8, 0, 4.2),
		"notice": Vector3(3.6, 0, 6.6),
		"well": Vector3(-3.4, 0, 12.2),
		"player_door": Vector3(-9, 0, 18.0),
	}


# --- Terrain -------------------------------------------------------------------------------

func _terrain() -> void:
	var res := 2
	var img := Image.create(int(splat_rect.size.x) * res, int(splat_rect.size.y) * res, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	# Forest floor west of the stream (b), meadow flowers (a) via noise.
	for y in img.get_height():
		for x in img.get_width():
			var w := _texel_to_world(x, y, res)
			var c := Color(0, 0, 0, 0)
			var stream_x := _stream_x_at(w.y)
			if w.x < stream_x - 1.0:
				c.b = 1.0
			elif w.y < -2.0 and w.y > -22.0 and w.x > -13.0 and w.x < 11.0:
				if EnvKit.noise2(w.x * 0.45, w.y * 0.45, 5) > 0.55:
					c.a = 1.0
			if w.distance_to(CLEARING) < 6.0:
				c.b = 1.0
			img.set_pixel(x, y, c)
	# Paths (dirt = r), village square and streets (cobble = g).
	var paths := [
		[Vector2(-9, 19), Vector2(-7, 14), Vector2(-3, 11), Vector2(0, 10)],
		[Vector2(0, 10), Vector2(5, 10), Vector2(11, 9.5), Vector2(17.5, 9)],
		[Vector2(0, 7), Vector2(0, 0), Vector2(-1, -8), Vector2(-1.5, -16), Vector2(-1, -23.5)],
		[Vector2(-1, -8), Vector2(5, -9), Vector2(10, -10.5), Vector2(14, -11)],
		[Vector2(-3, 10), Vector2(-8, 5), Vector2(-12, 2.5), Vector2(-17.5, 1.5), Vector2(-21, 0.5), Vector2(-23.5, -0.5)],
		[Vector2(8.5, 17.5), Vector2(6, 13), Vector2(3, 10.5)],
		[Vector2(10, 6), Vector2(7, 8.5)],
	]
	for p in paths:
		_paint_polyline(img, p, 1.5, 0, res)
	_paint_circle(img, Vector2(0.3, 9.4), 5.0, 1, res)
	_paint_circle(img, Vector2(-9.5, 7.6), 1.6, 1, res)
	_paint_circle(img, Vector2(-9, 18.6), 1.2, 1, res)
	_paint_circle(img, Vector2(8.5, 18.0), 1.4, 1, res)
	_paint_circle(img, RINGSTONES, 6.2, 0, res)
	_paint_rect(img, Rect2(TRAINING.position + Vector2(0.4, 0.4), TRAINING.size - Vector2(0.8, 0.8)), 0, res)
	splat_image = img
	var t := EnvKit.terrain(root, splat_rect, img, ["grass_a", "dirt_path", "cobble", "grass_dark", "flower_meadow"])
	t.name = "Terrain"


func _texel_to_world(x: int, y: int, res: int) -> Vector2:
	return Vector2(splat_rect.position.x + (x + 0.5) / res, splat_rect.position.y + (y + 0.5) / res)


func _paint(img: Image, x: int, y: int, channel: int) -> void:
	if x < 0 or y < 0 or x >= img.get_width() or y >= img.get_height():
		return
	var c := img.get_pixel(x, y)
	c.r = 1.0 if channel == 0 else 0.0
	c.g = 1.0 if channel == 1 else 0.0
	c.b = 0.0
	c.a = 0.0
	img.set_pixel(x, y, c)


func _paint_circle(img: Image, center: Vector2, radius: float, channel: int, res: int) -> void:
	var c := (center - splat_rect.position) * res
	var r := radius * res
	for y in range(int(c.y - r) - 1, int(c.y + r) + 2):
		for x in range(int(c.x - r) - 1, int(c.x + r) + 2):
			if Vector2(x + 0.5, y + 0.5).distance_to(c) <= r:
				_paint(img, x, y, channel)


func _paint_rect(img: Image, r: Rect2, channel: int, res: int) -> void:
	var p := (r.position - splat_rect.position) * res
	for y in range(int(p.y), int(p.y + r.size.y * res)):
		for x in range(int(p.x), int(p.x + r.size.x * res)):
			_paint(img, x, y, channel)


func _paint_polyline(img: Image, pts: Array, width: float, channel: int, res: int) -> void:
	for i in pts.size() - 1:
		var a: Vector2 = pts[i]
		var b: Vector2 = pts[i + 1]
		var steps := int(a.distance_to(b) * 2.0) + 1
		for s in steps + 1:
			var p := a.lerp(b, float(s) / steps)
			var wob := (EnvKit.noise2(p.x * 1.3, p.y * 1.3, 11) - 0.5) * 0.5
			_paint_circle(img, p, width * 0.5 + wob, channel, res)
	for p in pts:
		_blocked.append([p, 0.0])
	for i in pts.size() - 1:
		var a2: Vector2 = pts[i]
		var b2: Vector2 = pts[i + 1]
		var n := int(a2.distance_to(b2) / 1.5) + 1
		for s in n + 1:
			_blocked.append([a2.lerp(b2, float(s) / n), width * 0.5 + 0.9])


## Material under a world position (for footstep sounds): "dirt", "stone", "grass", "wood".
func surface_at(p: Vector3) -> String:
	if absf(p.z - BRIDGE_Z) < 1.3 and absf(p.x - _stream_x_at(p.z)) < STREAM_WIDTH * 0.5 + 0.6:
		return "wood"
	if splat_image == null:
		return "grass"
	var x := int((p.x - splat_rect.position.x) * 2.0)
	var y := int((p.z - splat_rect.position.y) * 2.0)
	if x < 0 or y < 0 or x >= splat_image.get_width() or y >= splat_image.get_height():
		return "grass"
	var c := splat_image.get_pixel(x, y)
	if c.g > 0.5:
		return "stone"
	if c.r > 0.5:
		return "dirt"
	return "grass"


# --- Water ------------------------------------------------------------------------------

func _stream_x_at(z: float) -> float:
	for i in STREAM.size() - 1:
		var a: Vector2 = STREAM[i]
		var b: Vector2 = STREAM[i + 1]
		if z >= a.y and z <= b.y:
			return lerpf(a.x, b.x, (z - a.y) / maxf(0.001, b.y - a.y))
	return STREAM[0].x


func _water_material(radial: bool) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/water.gdshader")
	var tex := EnvKit.tex("water_base")
	m.set_shader_parameter("water_tex", tex)
	m.set_shader_parameter("tex_size", tex.get_size())
	m.set_shader_parameter("radial", radial)
	return m


func _water() -> void:
	# Stream: a strip mesh along the centre line.
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var pts: Array[Vector2] = []
	for i in STREAM.size() - 1:
		var a: Vector2 = STREAM[i]
		var b: Vector2 = STREAM[i + 1]
		var n := int(a.distance_to(b) / 0.8) + 1
		for s in n:
			pts.append(a.lerp(b, float(s) / n))
	pts.append(STREAM[STREAM.size() - 1])
	var along := 0.0
	for i in pts.size() - 1:
		var a2 := pts[i]
		var b2 := pts[i + 1]
		var dir := (b2 - a2).normalized()
		var side := Vector2(-dir.y, dir.x) * STREAM_WIDTH * 0.5
		var len := a2.distance_to(b2)
		var w0 := 1.0 + 0.12 * sin(along * 0.7)
		var w1 := 1.0 + 0.12 * sin((along + len) * 0.7)
		var v := [
			[a2 - side * w0, Vector2(0, along)], [a2 + side * w0, Vector2(1, along)],
			[b2 - side * w1, Vector2(0, along + len)], [b2 + side * w1, Vector2(1, along + len)],
		]
		for idx in [0, 1, 2, 2, 1, 3]:
			st.set_normal(Vector3.UP)
			st.set_uv(v[idx][1])
			st.add_vertex(Vector3(v[idx][0].x, 0.03, v[idx][0].y))
		along += len
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	mi.material_override = _water_material(false)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.name = "Stream"
	root.add_child(mi)
	# Stream colliders (left out at the bridge).
	for i in pts.size() - 1:
		var mid := (pts[i] + pts[i + 1]) * 0.5
		if absf(mid.y - BRIDGE_Z) < 1.6:
			continue
		var seg_len := pts[i].distance_to(pts[i + 1])
		var angle := atan2(pts[i + 1].x - pts[i].x, pts[i + 1].y - pts[i].y)
		_collider_box(Vector3(mid.x, 0.5, mid.y), Vector3(STREAM_WIDTH - 0.4, 1.0, seg_len + 0.3), angle)
	# Bank details: reeds and rocks.
	for i in range(0, pts.size(), 2):
		var p := pts[i]
		if absf(p.y - BRIDGE_Z) < 2.0:
			continue
		for s in [-1.0, 1.0]:
			if rng.randf() < 0.55:
				var q := p + Vector2(s * (STREAM_WIDTH * 0.5 + rng.randf_range(0.0, 0.5)), rng.randf_range(-0.4, 0.4))
				EnvKit.foliage(root, ["reeds_a", "reeds_b", "rock_small_a", "rock_small_b"][rng.randi() % 4], Vector3(q.x, 0, q.y), 1.0, false, 0.4)
	# Pond in the meadow.
	var pond := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2.ONE * POND_RADIUS * 2.0
	pond.mesh = pm
	var circle_mat := _water_material(true)
	pond.material_override = circle_mat
	pond.position = Vector3(POND_CENTER.x, 0.03, POND_CENTER.y)
	pond.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(pond)
	# Ring the pond with bank stones and reeds.
	for i in 18:
		var a := float(i) / 18.0 * TAU
		var p2 := POND_CENTER + Vector2(cos(a), sin(a)) * (POND_RADIUS + 0.05)
		EnvKit.foliage(root, ["rock_small_a", "rock_small_b", "rock_small_c", "reeds_a"][i % 4], Vector3(p2.x, 0, p2.y), 0.9, false, 0.3)
	var collider := CollisionShape3D.new()
	var cyl := CylinderShape3D.new()
	cyl.radius = POND_RADIUS - 0.3
	cyl.height = 1.0
	collider.shape = cyl
	collider.position = Vector3(POND_CENTER.x, 0.5, POND_CENTER.y)
	statics.add_child(collider)
	for i in 3:
		EnvKit.foliage(root, "lily_pad", Vector3(POND_CENTER.x + rng.randf_range(-1.2, 1.2), 0.05, POND_CENTER.y + rng.randf_range(-1.0, 1.0)), 1.0, false)
	_blocked.append([POND_CENTER, POND_RADIUS + 1.2])


func _bridge() -> void:
	var x := _stream_x_at(BRIDGE_Z)
	var wood := EnvKit.material("wood_planks", Color(0.95, 0.88, 0.8))
	var dark := EnvKit.material("wood_dark" if ResourceLoader.exists(EnvKit.TEX_DIR + "wood_dark.png") else "bark")
	EnvKit.box(root, Vector3(STREAM_WIDTH + 2.2, 0.16, 2.2), Vector3(x, 0.0, BRIDGE_Z), wood)
	for s in [-1.0, 1.0]:
		EnvKit.box(root, Vector3(STREAM_WIDTH + 2.2, 0.1, 0.12), Vector3(x, 0.62, BRIDGE_Z + s * 1.05), dark)
		for px in [-1.0, 0.0, 1.0]:
			EnvKit.box(root, Vector3(0.16, 0.75, 0.16), Vector3(x + px * (STREAM_WIDTH * 0.5 + 0.9), 0.0, BRIDGE_Z + s * 1.05), dark)
		_collider_box(Vector3(x, 0.5, BRIDGE_Z + s * 1.25), Vector3(STREAM_WIDTH + 2.0, 1.0, 0.3), 0.0)
	_blocked.append([Vector2(x, BRIDGE_Z), 3.0])


# --- Village -----------------------------------------------------------------------------

func _village() -> void:
	_house(Vector2(-9, 16), Vector2(4.6, 3.6), 2.3, "thatch_roof", Color(1, 1, 1), true)
	_house(Vector2(8.5, 15.2), Vector2(5.6, 4.0), 2.6, "roof_tiles_red", Color(1, 0.97, 0.94), true)
	_house(Vector2(-9.6, 4.6), Vector2(5.0, 3.6), 2.4, "roof_tiles_slate", Color(1, 0.96, 0.9), true)
	_house(Vector2(10.6, 3.2), Vector2(4.4, 3.4), 2.2, "thatch_roof", Color(0.98, 0.95, 0.9), false)
	# The great oak in the square
	_tree_at("tree_oak_a", Vector2(0.5, 7.0), 1.55)
	EnvKit.blob_shadow(root, 2.2, 0.35).position = Vector3(0.5, 0.012, 7.0)
	# Well
	var stone := EnvKit.material("stone_bricks", Color(0.92, 0.9, 0.88))
	var wood := EnvKit.material("wood_planks")
	var w: Vector3 = anchors["well"]
	EnvKit.cylinder(root, 0.75, 0.75, 0.7, w, stone, 10)
	for s in [-1.0, 1.0]:
		EnvKit.box(root, Vector3(0.12, 1.5, 0.12), w + Vector3(s * 0.62, 0, 0), wood)
	EnvKit.gable_roof(root, Vector3(1.0, 0.45, 1.6), w + Vector3(0, 1.5, 0), EnvKit.material("roof_tiles_red"), PI * 0.5)
	_collider_cyl(Vector3(w.x, 0.5, w.z), 0.85)
	# Notice board and signpost
	EnvKit.box(root, Vector3(1.4, 0.9, 0.1), anchors["notice"] + Vector3(0, 0.6, 0), wood)
	for s in [-1.0, 1.0]:
		EnvKit.box(root, Vector3(0.1, 1.5, 0.1), anchors["notice"] + Vector3(s * 0.62, 0, 0), wood)
	_collider_box(anchors["notice"] + Vector3(0, 0.5, 0), Vector3(1.5, 1, 0.3), 0)
	EnvKit.prop(root, "signpost", anchors["signpost"])
	# Lanterns around the square and paths
	for p in [Vector2(-4.2, 6.2), Vector2(5.2, 6.4), Vector2(-4.4, 13.6), Vector2(5.0, 13.4), Vector2(-12.6, 2.6), Vector2(14.6, 8.2), Vector2(-0.6, -21.8), Vector2(12.4, -9.6)]:
		_lantern(Vector3(p.x, 0, p.y))
	# Fences around gardens
	_fence_line(Vector2(-12.6, 13.2), Vector2(-12.6, 19.6))
	_fence_line(Vector2(-12.6, 19.6), Vector2(-6.2, 19.6), true)
	_fence_line(Vector2(5.0, 18.6), Vector2(12.2, 18.6))
	_fence_line(Vector2(13.4, 1.0), Vector2(13.4, 6.4))
	# Clutter
	for item in [["barrel", Vector2(-6.8, 5.0)], ["barrel", Vector2(-6.3, 5.6)], ["crate", Vector2(-12.6, 6.6)], ["hay_bale", Vector2(13.0, 7.8)], ["hay_bale", Vector2(8.0, 2.0)], ["flower_planter", Vector2(-9.0, 18.3)], ["flower_planter", Vector2(6.8, 17.6)], ["barrel", Vector2(11.2, 17.6)], ["crate", Vector2(-11.0, 18.0)]]:
		EnvKit.prop(root, item[0], Vector3(item[1].x, 0, item[1].y))
		_collider_cyl(Vector3(item[1].x, 0.5, item[1].y), 0.4)
	# Farm field rows east of the farmhouse
	for i in 5:
		var z := 0.6 + i * 1.1
		for j in 6:
			EnvKit.foliage(root, ["fern_a", "fern_b"][(i + j) % 2], Vector3(14.8 + j * 0.8, 0, z), 0.9, false, 0.4)
	for c in [Vector2(-9, 16), Vector2(8.5, 15.2), Vector2(-9.6, 4.6), Vector2(10.6, 3.2), Vector2(0.5, 7)]:
		_blocked.append([c, 4.0])
	_blocked.append([Vector2(0.3, 9.4), 5.5])


func _house(c: Vector2, size: Vector2, wall_h: float, roof: String, tint: Color, chimney: bool) -> void:
	var walls := EnvKit.material("plaster_timber", tint, "", Color.WHITE, 0.3)
	var stone := EnvKit.material("stone_bricks", Color(0.9, 0.88, 0.86))
	var roof_mat := EnvKit.material(roof, Color.WHITE, "", Color.WHITE, 0.0)
	var base := Vector3(c.x, 0, c.y)
	EnvKit.box(root, Vector3(size.x + 0.16, 0.45, size.y + 0.16), base, stone)
	EnvKit.box(root, Vector3(size.x, wall_h, size.y), base, walls)
	var roof_h := size.y * 0.55
	EnvKit.gable_roof(root, Vector3(size.y + 0.8, roof_h, size.x + 0.7), base + Vector3(0, wall_h, 0), roof_mat, PI * 0.5)
	if chimney:
		EnvKit.box(root, Vector3(0.6, roof_h + 0.8, 0.6), base + Vector3(size.x * 0.28, wall_h, -size.y * 0.15), stone)
	# Door and windows as flat decals on the south (camera-facing) wall.
	var front_z := c.y + size.y * 0.5 + 0.012
	_wall_decal("door_wood", Vector3(c.x, 0.0, front_z), Vector2(1.0, 1.5))
	for s in [-1.0, 1.0]:
		var wx: float = c.x + s * size.x * 0.3
		if absf(wx - c.x) > 0.9:
			_wall_decal("window_lit", Vector3(wx, 1.05, front_z), Vector2(0.84, 0.84), true)
	_collider_box(Vector3(c.x, 1.0, c.y), Vector3(size.x + 0.2, 2.0, size.y + 0.2), 0.0)


func _wall_decal(prop_name: String, pos: Vector3, size: Vector2, is_window: bool = false) -> void:
	var path := EnvKit.PROP_DIR + prop_name + ".png"
	if not ResourceLoader.exists(path):
		return
	var mi := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = size
	mi.mesh = q
	var m := StandardMaterial3D.new()
	m.albedo_texture = load(path)
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	m.roughness = 1.0
	if is_window:
		m.emission_enabled = true
		m.emission_texture = m.albedo_texture
		m.emission = Color(1.0, 0.75, 0.45)
		m.emission_energy_multiplier = 0.0
		window_mats.append(m)
	mi.material_override = m
	mi.position = pos + Vector3(0, size.y * 0.5, 0)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(mi)


func _lantern(p: Vector3) -> void:
	var s := EnvKit.prop(root, "lantern_post", p)
	s.set_param("emission_strength", 1.5)
	s.set_param("emission_threshold", 0.7)
	var l := OmniLight3D.new()
	l.light_color = Color(1.0, 0.7, 0.4)
	l.light_energy = 0.0
	l.omni_range = 5.5
	l.position = p + Vector3(0, 1.9, 0.2)
	root.add_child(l)
	lantern_lights.append(l)
	_collider_cyl(Vector3(p.x, 0.5, p.z), 0.2)


func _fence_line(a: Vector2, b: Vector2, gap_middle: bool = false) -> void:
	var dark := EnvKit.material("wood_dark" if ResourceLoader.exists(EnvKit.TEX_DIR + "wood_dark.png") else "bark")
	var n := int(a.distance_to(b) / 1.0)
	for i in n + 1:
		var p := a.lerp(b, float(i) / n)
		if gap_middle and absf(float(i) - n * 0.5) < 1.1:
			continue
		EnvKit.box(root, Vector3(0.14, 0.8, 0.14), Vector3(p.x, 0, p.y), dark)
	var dir := b - a
	var angle := atan2(dir.x, dir.y)
	var mid := (a + b) * 0.5
	if gap_middle:
		for half in [[a, a.lerp(b, 0.4)], [a.lerp(b, 0.6), b]]:
			var m2: Vector2 = (half[0] + half[1]) * 0.5
			var l2: float = (half[0] as Vector2).distance_to(half[1])
			EnvKit.box(root, Vector3(0.08, 0.08, l2), Vector3(m2.x, 0.55, m2.y), dark, angle)
			_collider_box(Vector3(m2.x, 0.5, m2.y), Vector3(0.25, 1, l2), angle)
		return
	EnvKit.box(root, Vector3(0.08, 0.08, a.distance_to(b)), Vector3(mid.x, 0.55, mid.y), dark, angle)
	EnvKit.box(root, Vector3(0.08, 0.08, a.distance_to(b)), Vector3(mid.x, 0.28, mid.y), dark, angle)
	_collider_box(Vector3(mid.x, 0.5, mid.y), Vector3(0.25, 1.0, a.distance_to(b)), angle)


# --- Training yard, Ringstones, Shrine -------------------------------------------------

func _training_yard() -> void:
	var r := TRAINING
	# Fence with a gate gap on the west side.
	_fence_line(Vector2(r.position.x, r.position.y), Vector2(r.end.x, r.position.y))
	_fence_line(Vector2(r.end.x, r.position.y), Vector2(r.end.x, r.end.y))
	_fence_line(Vector2(r.position.x, r.end.y), Vector2(r.end.x, r.end.y))
	_fence_line(Vector2(r.position.x, r.position.y), Vector2(r.position.x, 7.8))
	_fence_line(Vector2(r.position.x, 10.2), Vector2(r.position.x, r.end.y))
	for p in [Vector2(21.5, 5.6), Vector2(24.2, 8.0), Vector2(21.5, 10.6)]:
		var s := PixelSprite3D.new()
		s.load_manifest("res://assets/sprites/props/training_totem.json")
		s.position = Vector3(p.x, 0, p.y)
		root.add_child(s)
		s.play("idle", "s")
		_collider_cyl(Vector3(p.x, 0.5, p.y), 0.35)
	EnvKit.prop(root, "hay_bale", Vector3(25.6, 0, 4.2))
	EnvKit.prop(root, "barrel", Vector3(18.0, 0, 12.0))
	_blocked.append([r.get_center(), 7.5])


func _ringstones() -> void:
	var c := RINGSTONES
	var mat := EnvKit.material("mossy_stone", Color(0.92, 0.92, 0.96), "", Color.WHITE, 0.4)
	for i in 12:
		var a := float(i) / 12.0 * TAU + 0.26
		var p := c + Vector2(cos(a), sin(a)) * 7.0
		if p.distance_to(Vector2(anchors["arena_gate"].x, anchors["arena_gate"].z)) < 2.4:
			continue
		var h := rng.randf_range(2.2, 3.0)
		EnvKit.cylinder(root, 0.5, 0.36, h, Vector3(p.x, 0, p.y), mat, 4, a)
		_collider_cyl(Vector3(p.x, 0.5, p.y), 0.55)
	# Entrance arch
	var g: Vector3 = anchors["arena_gate"]
	var stone := EnvKit.material("stone_bricks", Color(0.9, 0.9, 0.92))
	for s in [-1.0, 1.0]:
		EnvKit.box(root, Vector3(0.6, 2.6, 0.6), g + Vector3(s * 1.4, 0, 0), stone)
		_collider_box(g + Vector3(s * 1.4, 0.5, 0), Vector3(0.7, 1, 0.7), 0)
	EnvKit.box(root, Vector3(3.6, 0.5, 0.7), g + Vector3(0, 2.6, 0), stone)
	EnvKit.animated_prop(root, "banner_red", "wave", g + Vector3(-1.4, 2.0, 0.36))
	EnvKit.animated_prop(root, "banner_blue", "wave", g + Vector3(1.4, 2.0, 0.36))
	for p in [Vector2(11.5, -16), Vector2(22.5, -16), Vector2(17, -21.5)]:
		var fire := EnvKit.animated_prop(root, "brazier", "lit", Vector3(p.x, 0.5, p.y))
		fire.set_param("emission_strength", 2.0)
		EnvKit.cylinder(root, 0.3, 0.25, 0.55, Vector3(p.x, 0, p.y), stone, 8)
		_collider_cyl(Vector3(p.x, 0.5, p.y), 0.35)
	_blocked.append([c, 8.2])


func _shrine() -> void:
	var c := SHRINE
	var mossy := EnvKit.material("mossy_stone", Color(0.88, 0.9, 0.95), "", Color.WHITE, 0.45)
	var bricks := EnvKit.material("stone_bricks", Color(0.8, 0.82, 0.88), "mossy_stone", Color(0.9, 1, 0.9), 0.4)
	# Platform and steps
	EnvKit.box(root, Vector3(14, 0.3, 8), Vector3(c.x, 0, c.y - 0.6), bricks)
	EnvKit.box(root, Vector3(4, 0.15, 1.2), Vector3(c.x, 0, c.y + 4.0), bricks)
	# Back wall with gaps (ruins)
	for seg in [[-6.0, -3.0, 3.2], [-2.6, 2.6, 4.0], [3.0, 6.2, 2.4]]:
		var w: float = seg[1] - seg[0]
		EnvKit.box(root, Vector3(w, seg[2], 0.8), Vector3(c.x + (seg[0] + seg[1]) * 0.5, 0, c.y - 4.2), mossy)
	_collider_box(Vector3(c.x, 1.0, c.y - 4.2), Vector3(13, 2, 1.0), 0)
	# The mural on the central wall, facing the camera.
	mural = MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = Vector2(5.0, 3.75)
	mural.mesh = q
	var m := StandardMaterial3D.new()
	if ResourceLoader.exists(EnvKit.PROP_DIR + "mural_dawncrane.png"):
		m.albedo_texture = load(EnvKit.PROP_DIR + "mural_dawncrane.png")
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	m.roughness = 1.0
	m.emission_enabled = true
	m.emission = Color(1, 0.85, 0.5)
	m.emission_energy_multiplier = 0.0
	if ResourceLoader.exists(EnvKit.PROP_DIR + "mural_dawncrane_glow.png"):
		m.emission_texture = load(EnvKit.PROP_DIR + "mural_dawncrane_glow.png")
	mural_glow_mat = m
	mural.material_override = m
	mural.position = Vector3(c.x, 2.1, c.y - 3.78)
	mural.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(mural)
	# Pillars, some broken
	for i in 6:
		var px := c.x - 5.5 + i * 2.2
		var h: float = [3.0, 1.2, 3.2, 2.0, 0.8, 2.8][i]
		EnvKit.cylinder(root, 0.42, 0.38, h, Vector3(px, 0.3, c.y + 1.8), mossy, 8)
		_collider_cyl(Vector3(px, 0.5, c.y + 1.8), 0.45)
	# Fallen pillar and rubble
	var fallen := EnvKit.cylinder(root, 0.4, 0.4, 2.6, Vector3(c.x + 7.6, 0.4, c.y + 0.5), mossy, 8)
	fallen.rotation = Vector3(0, 0.6, PI * 0.5)
	for i in 6:
		EnvKit.foliage(root, ["rock_small_a", "rock_small_b", "rock_small_c"][i % 3], Vector3(c.x + rng.randf_range(-7, 7), 0.3, c.y + rng.randf_range(-2, 3)), 1.0, false)
	for p in [Vector2(-9, -30), Vector2(7.5, -29.5), Vector2(-8, -24.5), Vector2(9, -25.5)]:
		_tree_at("tree_dead", p, 1.1)
	_blocked.append([c, 9.0])


# --- Forest and meadow ------------------------------------------------------------------

func _glimmerwood() -> void:
	# Hollow log (the frightened Emberlyn's hiding place)
	var log_pos: Vector3 = anchors["log"]
	EnvKit.foliage(root, "log_hollow", log_pos, 1.0, true)
	_collider_box(log_pos + Vector3(0, 0.5, 0), Vector3(2.4, 1, 0.9), 0)
	# Fire ring
	campfire = EnvKit.animated_prop(root, "campfire", "unlit", anchors["fire_ring"])
	campfire.set_param("emission_strength", 0.0)
	campfire_light = OmniLight3D.new()
	campfire_light.light_color = Color(1.0, 0.6, 0.3)
	campfire_light.light_energy = 0.0
	campfire_light.omni_range = 6.0
	campfire_light.position = anchors["fire_ring"] + Vector3(0, 1.0, 0.3)
	root.add_child(campfire_light)
	_collider_cyl(anchors["fire_ring"] + Vector3(0, 0.5, 0), 0.45)
	# Stump for the first kindlemoss, rocks and mushrooms near the others
	EnvKit.foliage(root, "stump", anchors["moss_1"] + Vector3(0.2, 0, -0.4))
	for p in [anchors["moss_2"], anchors["moss_3"]]:
		EnvKit.foliage(root, "mushroom_glow", p + Vector3(0.5, 0, -0.3), 1.0, false)
		EnvKit.foliage(root, "rock_small_b", p + Vector3(-0.6, 0, -0.2), 1.0, false)
	EnvKit.prop(root, "snare_broken", anchors["snare"], 1.0, false)
	_blocked.append([CLEARING, 7.0])
	for p in [anchors["moss_1"], anchors["moss_2"], anchors["moss_3"]]:
		_blocked.append([Vector2(p.x, p.z), 1.4])
	# Low bushes and ferns fill the sight-line south of the clearing.
	for i in 26:
		var q := Vector2(rng.randf_range(-32, -18), rng.randf_range(CLEARING.y + 6.0, CLEARING.y + 11.0))
		if absf(q.y - 0.8) < 1.6 and q.x > -24.0:
			continue
		EnvKit.foliage(root, ["bush_a", "bush_b", "fern_a", "fern_b", "bush_berry"][i % 5], Vector3(q.x, 0, q.y), 1.0, true, 0.5)
	# Glowing mushrooms and ferns under the trees
	for i in 60:
		var p2 := Vector2(rng.randf_range(-33, -18), rng.randf_range(-30, 22))
		if p2.distance_to(CLEARING) < 4.5:
			continue
		EnvKit.foliage(root, ["mushroom_glow", "mushroom_a", "fern_a", "fern_b", "mushroom_b", "bush_b"][i % 6], Vector3(p2.x, 0, p2.y), 1.0, false, 0.4).set_param("emission_strength", 1.2 if i % 6 == 0 else 0.0)


func _meadow() -> void:
	for p in [Vector2(-10, -16), Vector2(8, -18), Vector2(6, -4)]:
		_tree_at("tree_birch", p, 1.0)
	for i in 14:
		var p2 := Vector2(rng.randf_range(-12, 10), rng.randf_range(-21, -3))
		if p2.distance_to(POND_CENTER) < POND_RADIUS + 1.0:
			continue
		EnvKit.foliage(root, ["bush_a", "bush_berry", "bush_b"][i % 3], Vector3(p2.x, 0, p2.y), 1.0, true, 0.5)


func _tree_at(tree_name: String, p: Vector2, scale: float) -> void:
	if not _tree_items.has(tree_name):
		_tree_items[tree_name] = []
	(_tree_items[tree_name] as Array).append([Vector3(p.x, 0, p.y), 0, scale])
	_collider_cyl(Vector3(p.x, 0.5, p.y), 0.38 * scale)


func _is_blocked(p: Vector2, margin: float = 0.0) -> bool:
	for b in _blocked:
		if p.distance_to(b[0]) < float(b[1]) + margin:
			return true
	if absf(p.x - _stream_x_at(p.y)) < STREAM_WIDTH * 0.5 + 1.0:
		return true
	return false


func _trees() -> void:
	var placed: Array[Vector2] = []
	# Dense forest west of the stream. A sight-line south of the clearing and
	# the forest path stays free of tall trees so the camera can see in.
	var sight := Rect2(-33, CLEARING.y - 1.0, 18, 12.5)
	for i in 900:
		var p := Vector2(rng.randf_range(-34, -17), rng.randf_range(-35, 25))
		if p.x > _stream_x_at(p.y) - 2.0:
			continue
		if sight.has_point(p) or _is_blocked(p) or _too_close(placed, p, 2.3):
			continue
		placed.append(p)
		var roll := rng.randf()
		var kind := "tree_glimmer" if roll < 0.35 else ("tree_pine" if roll < 0.65 else ("tree_oak_a" if roll < 0.85 else "tree_oak_b"))
		_tree_at(kind, p, rng.randf_range(0.95, 1.25))
	# Village and meadow edges, east and north boundary lines
	for i in 700:
		var p2 := Vector2(rng.randf_range(-16, 34), rng.randf_range(-35, 25))
		var edge := p2.x > 28.0 or p2.y < -31.0 or (p2.y > 22.5 and absf(p2.x) > 16.0) or (p2.x > 23.0 and p2.y < -2.0)
		var scatter := rng.randf() < 0.05
		if not edge and not scatter:
			continue
		if _is_blocked(p2, 0.5) or _too_close(placed, p2, 1.9):
			continue
		placed.append(p2)
		_tree_at(["tree_oak_a", "tree_oak_b", "tree_pine", "tree_birch"][rng.randi() % 4], p2, rng.randf_range(0.95, 1.2))
	for tree_name in _tree_items.keys():
		var atlas := EnvKit.atlas([tree_name])
		var mm := EnvKit.scatter(root, atlas, _tree_items[tree_name], true, 1.4, true)
		mm.name = "Trees_" + tree_name


func _too_close(placed: Array[Vector2], p: Vector2, d: float) -> bool:
	for q in placed:
		if q.distance_squared_to(p) < d * d:
			return true
	return false


func _ground_cover() -> void:
	var grass := EnvKit.atlas(["grass_tuft_a", "grass_tuft_b", "grass_tuft_c", "grass_tuft_d", "flowers_red", "flowers_yellow", "flowers_white", "flowers_blue", "flowers_pink"])
	var items: Array = []
	for i in 2600:
		var p := Vector2(rng.randf_range(-34, 34), rng.randf_range(-35, 25))
		var surface := surface_at(Vector3(p.x, 0, p.y))
		if surface != "grass":
			continue
		if absf(p.x - _stream_x_at(p.y)) < STREAM_WIDTH * 0.5 + 0.3:
			continue
		if p.distance_to(POND_CENTER) < POND_RADIUS + 0.3:
			continue
		var in_meadow := p.y < -2 and p.y > -22 and p.x > -13 and p.x < 11
		var flower_chance := 0.35 if in_meadow else 0.12
		var idx := rng.randi_range(4, 8) if rng.randf() < flower_chance else rng.randi_range(0, 3)
		items.append([Vector3(p.x, 0, p.y), idx, rng.randf_range(0.85, 1.15)])
	EnvKit.scatter(root, grass, items, false, 0.8).name = "GroundCover"


func _boundary() -> void:
	var b := BOUNDS
	_collider_box(Vector3(b.get_center().x, 1, b.position.y), Vector3(b.size.x, 2, 1), 0)
	_collider_box(Vector3(b.get_center().x, 1, b.end.y), Vector3(b.size.x, 2, 1), 0)
	_collider_box(Vector3(b.position.x, 1, b.get_center().y), Vector3(1, 2, b.size.y), 0)
	_collider_box(Vector3(b.end.x, 1, b.get_center().y), Vector3(1, 2, b.size.y), 0)
	# Cliffs along the north edge
	var cliff := EnvKit.material("cliff_rock", Color(0.9, 0.9, 0.95), "grass_dark", Color(0.9, 1, 0.9), 0.5)
	var x := -40.0
	while x < 40.0:
		var w := rng.randf_range(3.0, 5.0)
		EnvKit.box(root, Vector3(w, rng.randf_range(2.6, 4.0), 3.0), Vector3(x + w * 0.5, 0, -37.5 - rng.randf_range(0, 1.0)), cliff)
		x += w


func _ambient() -> void:
	for center in [CLEARING, Vector2(-26, -18), Vector2(-26, 12), POND_CENTER]:
		var p := CPUParticles3D.new()
		p.amount = 26
		p.lifetime = 5.0
		p.preprocess = 5.0
		p.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
		p.emission_box_extents = Vector3(6, 1.0, 6)
		p.position = Vector3(center.x, 1.2, center.y)
		p.direction = Vector3(0, 1, 0)
		p.spread = 180.0
		p.initial_velocity_min = 0.05
		p.initial_velocity_max = 0.25
		p.gravity = Vector3.ZERO
		var quad := QuadMesh.new()
		quad.size = Vector2.ONE * 0.07
		var m := StandardMaterial3D.new()
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
		m.albedo_color = Color(0.85, 1.0, 0.6)
		m.emission_enabled = true
		m.emission = Color(0.75, 1.0, 0.5)
		m.emission_energy_multiplier = 2.0
		quad.material = m
		p.mesh = quad
		root.add_child(p)
		fireflies.append(p)


# --- Colliders -------------------------------------------------------------------------------

func _collider_box(pos: Vector3, size: Vector3, rot_y: float) -> void:
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = size
	cs.shape = bs
	cs.position = pos
	cs.rotation.y = rot_y
	statics.add_child(cs)


func _collider_cyl(pos: Vector3, radius: float) -> void:
	var cs := CollisionShape3D.new()
	var c := CylinderShape3D.new()
	c.radius = radius
	c.height = 1.0
	cs.shape = c
	cs.position = pos
	statics.add_child(cs)


## Time-of-day dependent dressing (lanterns, windows, fireflies, campfire).
func set_night_amount(t: float) -> void:
	for l in lantern_lights:
		l.light_energy = lerpf(0.0, 1.6, t)
	for m in window_mats:
		m.emission_energy_multiplier = lerpf(0.0, 1.6, t)
	for f in fireflies:
		f.emitting = t > 0.3 or f.position.distance_to(Vector3(CLEARING.x, 1.2, CLEARING.y)) < 1.0


func light_campfire() -> void:
	campfire.play("lit", "s")
	campfire.set_param("emission_strength", 2.2)
	campfire.set_param("emission_threshold", 0.55)
	var tw := campfire_light.create_tween()
	tw.tween_property(campfire_light, "light_energy", 2.2, 0.8)


func set_mural_glow(amount: float) -> void:
	if mural_glow_mat:
		mural_glow_mat.emission_energy_multiplier = amount * 0.55
