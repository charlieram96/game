class_name ArenaBuilder
extends RefCounted
## Builds the HD-2D battle arena around an ArenaDefinition: splat terrain
## with a logical-cell grid, curbs, standing stones (obstacles use exactly the
## simulation's radii), bleachers with an animated crowd, trainers' spots,
## braziers, banners, trees and drifting motes.

const CROWD_SHEET := "res://assets/sprites/characters/crowd.json"
const CROWD_BACK_SHEET := "res://assets/sprites/characters/crowd_back.json"

var root: Node3D
var crowd: Array[PixelSprite3D] = []
var trainer_spots: Array[Vector3] = [Vector3(-8.35, 0, 0.9), Vector3(8.35, 0, 0.9)]
var rng := RandomNumberGenerator.new()


func build(parent: Node3D, def: ArenaDefinition) -> Node3D:
	rng.seed = 4242
	root = Node3D.new()
	root.name = "Arena"
	parent.add_child(root)
	var half := def.size * 0.5
	_terrain(def, half)
	_emblem()
	_curbs(half, def)
	for c in def.circles:
		_obstacle_stone(Vector3(c.x, 0, c.y), c.z)
	if def.crowd:
		_ringstones(half)
		_bleachers(half)
		_foreground_crowd(half)
		_banners(half)
	else:
		_training_props(half)
	_braziers(half)
	_trees(half, def.crowd)
	_motes(half)
	return root


func _terrain(def: ArenaDefinition, half: Vector2) -> void:
	var rect := Rect2(-32, -26, 64, 48)
	var res := 2  # splat texels per unit
	var img := Image.create(int(rect.size.x) * res, int(rect.size.y) * res, false, Image.FORMAT_RGBA8)
	var floor_pad := 0.45
	var border := 0.9
	for y in img.get_height():
		for x in img.get_width():
			var wx := rect.position.x + (x + 0.5) / res
			var wz := rect.position.y + (y + 0.5) / res
			var dx := absf(wx) - (half.x + floor_pad)
			var dz := absf(wz) - (half.y + floor_pad)
			var r := 0.0
			var g := 0.0
			var b := 0.0
			var a := 0.0
			if dx <= 0.0 and dz <= 0.0:
				r = 1.0
			elif dx <= border and dz <= border:
				g = 1.0
			else:
				# Cobble path to the south entrance and to the stands.
				if absf(wx) < 1.4 and wz > half.y:
					g = 1.0
				var n := EnvKit.noise2(wx * 0.35, wz * 0.35, 7)
				var n2 := EnvKit.noise2(wx * 0.6 + 40.0, wz * 0.6, 3)
				if n > 0.62:
					b = 1.0
				if n2 > 0.86 and g < 0.5:
					a = 1.0
			img.set_pixel(x, y, Color(r, g, b, a))
	var floor_tex := "sand_arena" if def.floor_style == &"sand" else "dirt_path"
	var t := EnvKit.terrain(root, rect, img, ["grass_a", floor_tex, "cobble", "grass_b", "flower_meadow"])
	var m: ShaderMaterial = t.material_override
	m.set_shader_parameter("grid_strength", 0.16)
	m.set_shader_parameter("grid_rect", Vector4(-half.x, -half.y, def.size.x, def.size.y))
	m.set_shader_parameter("grid_color", Color(0.42, 0.3, 0.18))


func _emblem() -> void:
	var mi := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(4.6, 4.6)
	mi.mesh = pm
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/telegraph.gdshader")
	m.set_shader_parameter("shape", 1)
	m.set_shader_parameter("inner", 0.86)
	m.set_shader_parameter("color", Color(0.98, 0.93, 0.8))
	m.set_shader_parameter("fill_color", Color(0.9, 0.8, 0.6))
	m.set_shader_parameter("progress", 0.0)
	m.set_shader_parameter("opacity", 0.35)
	m.set_shader_parameter("edge_px", 1.0)
	m.set_shader_parameter("quad_size", Vector2(4.6, 4.6))
	mi.material_override = m
	mi.position.y = 0.01
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(mi)


func _curbs(half: Vector2, def: ArenaDefinition) -> void:
	var stone := EnvKit.material("stone_bricks", Color(0.95, 0.93, 0.9), "", Color.WHITE, 0.2)
	var pad := 0.6
	var w := half.x + pad
	var d := half.y + pad
	var t := 0.3
	# North (back) curb is taller, south (front) is low so it never hides the action.
	EnvKit.box(root, Vector3(w * 2.0 + t, 0.42, t), Vector3(0, 0, -d), stone)
	EnvKit.box(root, Vector3(w * 2.0 + t, 0.14, t), Vector3(0, 0, d), stone)
	EnvKit.box(root, Vector3(t, 0.3, d * 2.0), Vector3(-w, 0, 0), stone)
	EnvKit.box(root, Vector3(t, 0.3, d * 2.0), Vector3(w, 0, 0), stone)
	var wood := EnvKit.material("wood_dark" if ResourceLoader.exists(EnvKit.TEX_DIR + "wood_dark.png") else "bark")
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			EnvKit.box(root, Vector3(0.36, 0.9 if sz < 0 else 0.4, 0.36), Vector3(sx * w, 0, sz * d), wood)


func _obstacle_stone(pos: Vector3, radius: float) -> void:
	var mat := EnvKit.material("rock", Color(0.92, 0.92, 0.95), "mossy_stone", Color(0.9, 1.0, 0.85), 0.3)
	EnvKit.cylinder(root, radius, radius * 0.72, 1.5, pos, mat, 7, rng.randf() * TAU)
	EnvKit.cylinder(root, radius * 0.7, radius * 0.45, 0.5, pos + Vector3(0, 1.5, 0), mat, 7, rng.randf() * TAU)
	EnvKit.blob_shadow(root, radius * 1.6, 0.35).position = pos + Vector3(0, 0.012, 0)
	for i in 3:
		var a := rng.randf() * TAU
		var p := pos + Vector3(cos(a), 0, sin(a)) * (radius + 0.2)
		EnvKit.foliage(root, ["rock_small_a", "rock_small_b", "rock_small_c", "grass_tuft_b"][i % 4], p, 0.8, false)


func _ringstones(half: Vector2) -> void:
	var mat := EnvKit.material("mossy_stone", Color(0.9, 0.9, 0.95), "", Color.WHITE, 0.4)
	var count := 14
	for i in count:
		var ang := PI + float(i) / float(count - 1) * PI  # north semicircle
		var pos := Vector3(cos(ang) * (half.x + 4.2), 0, sin(ang) * (half.y + 2.6) - 0.6)
		var h := rng.randf_range(2.0, 2.9)
		var stone := EnvKit.cylinder(root, 0.45, 0.32, h, pos, mat, 4, PI * 0.25 + rng.randf_range(-0.2, 0.2))
		stone.rotation.z = rng.randf_range(-0.06, 0.06)


func _bleachers(half: Vector2) -> void:
	var wood := EnvKit.material("wood_planks", Color(0.95, 0.9, 0.85), "", Color.WHITE, 0.45)
	var sheet := SpriteSheet.load_sheet(CROWD_SHEET)
	var z0 := -half.y - 2.2
	for tier in 3:
		var h := 0.35 + tier * 0.42
		var z := z0 - tier * 0.85
		EnvKit.box(root, Vector3(half.x * 2.0 - 1.0, h, 0.85), Vector3(0, 0, z), wood)
		var x := -half.x + 1.2 + rng.randf_range(0.0, 0.4)
		while x < half.x - 1.0:
			if rng.randf() < 0.82:
				var s := PixelSprite3D.new()
				s.set_sheet(sheet)
				s.position = Vector3(x, h - 0.05, z + 0.12)
				s.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
				root.add_child(s)
				var v := rng.randi_range(0, 7)
				s.set_meta("variant", v)
				s.play("idle_v%d" % v, "s")
				s.speed_scale = rng.randf_range(0.7, 1.3)
				crowd.append(s)
			x += rng.randf_range(0.75, 1.05)
	# Side spectators standing at ground level.
	for side in [-1.0, 1.0]:
		for i in 4:
			var s2 := PixelSprite3D.new()
			s2.set_sheet(sheet)
			s2.position = Vector3(side * (half.x + 2.3 + rng.randf_range(0, 1.4)), 0, -half.y + 1.0 + i * 2.2 + rng.randf_range(-0.4, 0.4))
			root.add_child(s2)
			var v2 := rng.randi_range(0, 7)
			s2.set_meta("variant", v2)
			s2.play("idle_v%d" % v2, "s")
			crowd.append(s2)


func _foreground_crowd(half: Vector2) -> void:
	var sheet := SpriteSheet.load_sheet(CROWD_BACK_SHEET)
	var x := -half.x - 2.0
	while x < half.x + 2.0:
		var s := PixelSprite3D.new()
		s.set_sheet(sheet)
		s.position = Vector3(x, 0, half.y + 2.2 + rng.randf_range(0.0, 0.5))
		s.scale = Vector3.ONE * 1.25
		s.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(s)
		var v := rng.randi_range(0, 5)
		s.set_meta("variant", v)
		s.set_meta("back", true)
		s.play("idle_v%d" % v, "s")
		crowd.append(s)
		x += rng.randf_range(0.9, 1.3)


func _banners(half: Vector2) -> void:
	for i in 4:
		var x := lerpf(-half.x + 1.0, half.x - 1.0, float(i) / 3.0)
		var sheet_name := "banner_blue" if i < 2 else "banner_red"
		EnvKit.animated_prop(root, sheet_name, "wave", Vector3(x, 1.6, -half.y - 4.9), true)


func _training_props(half: Vector2) -> void:
	var wood := EnvKit.material("wood_planks")
	for i in 7:
		EnvKit.box(root, Vector3(0.14, 0.7, 0.14), Vector3(-half.x + i * (half.x * 2.0 / 6.0), 0, -half.y - 1.4), wood)
	EnvKit.box(root, Vector3(half.x * 2.0, 0.08, 0.1), Vector3(0, 0.5, -half.y - 1.4), wood)
	for p in [Vector3(-half.x - 1.6, 0, -half.y - 2.2), Vector3(half.x + 1.4, 0, -half.y - 2.0)]:
		EnvKit.prop(root, "hay_bale", p)
	EnvKit.prop(root, "barrel", Vector3(half.x + 2.0, 0, -1.0))
	EnvKit.prop(root, "crate", Vector3(-half.x - 2.0, 0, 1.6))


func _braziers(half: Vector2) -> void:
	var stone := EnvKit.material("stone_bricks", Color(0.8, 0.78, 0.8))
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			var p := Vector3(sx * (half.x + 1.6), 0, sz * (half.y + 1.4))
			EnvKit.cylinder(root, 0.32, 0.26, 0.55, p, stone, 8)
			var fire := EnvKit.animated_prop(root, "brazier", "lit", p + Vector3(0, 0.5, 0))
			fire.set_param("emission_strength", 2.2)
			fire.set_param("emission_threshold", 0.55)
			var light := OmniLight3D.new()
			light.light_color = Color(1.0, 0.62, 0.3)
			light.light_energy = 1.4
			light.omni_range = 5.0
			light.position = p + Vector3(0, 1.3, 0)
			root.add_child(light)


func _trees(half: Vector2, crowded: bool) -> void:
	var kinds := ["tree_oak_a", "tree_oak_b", "tree_pine", "tree_birch"]
	var back_z := -half.y - (6.4 if crowded else 3.5)
	var x := -half.x - 8.0
	while x < half.x + 8.0:
		EnvKit.foliage(root, kinds[rng.randi() % kinds.size()], Vector3(x, 0, back_z - rng.randf_range(0, 2.0)), rng.randf_range(1.0, 1.25), true, 1.2)
		x += rng.randf_range(1.6, 2.6)
	for side in [-1.0, 1.0]:
		var z := -half.y - 2.0
		while z < half.y + 4.0:
			EnvKit.foliage(root, kinds[rng.randi() % kinds.size()], Vector3(side * (half.x + rng.randf_range(5.2, 7.5)), 0, z), rng.randf_range(0.95, 1.2), true, 1.2)
			z += rng.randf_range(1.8, 2.8)
	# Low bushes and flowers to soften edges.
	var items: Array = []
	var atlas := EnvKit.atlas(["grass_tuft_a", "grass_tuft_b", "grass_tuft_c", "grass_tuft_d", "flowers_red", "flowers_yellow", "flowers_white", "flowers_blue"])
	for i in 420:
		var p := Vector3(rng.randf_range(-22, 22), 0, rng.randf_range(-18, 12))
		if absf(p.x) < half.x + 1.8 and absf(p.z) < half.y + 1.8:
			continue
		if absf(p.x) < 1.6 and p.z > half.y:
			continue
		var idx := rng.randi_range(0, 3) if rng.randf() < 0.75 else rng.randi_range(4, 7)
		items.append([p, idx, rng.randf_range(0.9, 1.2)])
	EnvKit.scatter(root, atlas, items, false, 0.7)
	for side in [-1.0, 1.0]:
		for i in 3:
			EnvKit.foliage(root, ["bush_a", "bush_b", "bush_berry"][i], Vector3(side * (half.x + 3.4 + i * 0.9), 0, half.y + 1.6 - i * 2.4), 1.0, true, 0.5)


func _motes(half: Vector2) -> void:
	var p := CPUParticles3D.new()
	p.amount = 60
	p.lifetime = 7.0
	p.preprocess = 7.0
	p.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	p.emission_box_extents = Vector3(half.x + 4.0, 1.2, half.y + 3.0)
	p.position = Vector3(0, 1.4, 0)
	p.direction = Vector3(0.4, 0.3, 0.1)
	p.spread = 60.0
	p.initial_velocity_min = 0.1
	p.initial_velocity_max = 0.35
	p.gravity = Vector3(0, 0.02, 0)
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE * 0.05
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.albedo_color = Color(1.0, 0.92, 0.62, 0.9)
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	quad.material = m
	p.mesh = quad
	p.color_ramp = _fade_ramp()
	root.add_child(p)


static func _fade_ramp() -> Gradient:
	var g := Gradient.new()
	g.set_color(0, Color(1, 1, 1, 0))
	g.add_point(0.2, Color(1, 1, 1, 1))
	g.add_point(0.8, Color(1, 1, 1, 1))
	g.set_color(g.get_point_count() - 1, Color(1, 1, 1, 0))
	return g


## Crowd reaction (cheer for a while, then settle).
func cheer(seconds: float = 2.0) -> void:
	for s in crowd:
		var v: int = s.get_meta("variant", 0)
		s.play("cheer_v%d" % v, "s")
	var tree := root.get_tree()
	if tree == null:
		return
	await tree.create_timer(seconds).timeout
	for s in crowd:
		if is_instance_valid(s):
			s.play("idle_v%d" % int(s.get_meta("variant", 0)), "s")
