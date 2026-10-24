class_name ArenaBuilder
extends RefCounted
## Builds the HD-2D battle arena around an ArenaDefinition.
##
## The board is a raised stage: flagstones laid exactly on the logical cell
## grid (shaders/arena_floor.gdshader), a 0.5-unit rim whose slab joints (and
## bronze studs) line up with the columns and rows, carved walls on three
## sides with a merlon on every row, banners and bunting on the back wall,
## corner pillars with braziers, the trainers' podiums on the wings, the crowd
## behind the back wall and in the foreground, standing stones that use
## exactly the simulation's radii, and the light and atmosphere (sun, warm
## brazier pools, glows, embers, dust motes). The training yard is the same
## board in packed earth framed by timber, on a lawn with lantern posts.
##
## Call apply_post() for the matching screen grading, and set_cell_highlight()
## to light up cells on the floor itself.
##
## Everything is static geometry with baked or procedural textures; a single
## tiny node flickers the brazier lights. With Settings.graphics_low only the
## two front braziers carry lights and the embers are skipped.

const CROWD_SHEET := "res://assets/sprites/characters/crowd.json"
const CROWD_BACK_SHEET := "res://assets/sprites/characters/crowd_back.json"
const FLOOR_SHADER := preload("res://shaders/arena_floor.gdshader")
const FIRE_SHADER := preload("res://shaders/arena_fire.gdshader")
const GLOW_SHADER := preload("res://shaders/arena_glow.gdshader")
const CLOTH_SHADER := preload("res://shaders/arena_cloth.gdshader")

## Rim around the board (world units; 12 texels, see the rim atlas).
const RIM := 0.5
## Height of the stage's open front face (the ground in front is lower).
const STAGE_DROP := 0.42
const BACK_WALL_H := 1.0
const BACK_WALL_T := 0.45
const SIDE_WALL_H := 0.4
const SIDE_WALL_T := 0.34
const WING := 3.6
const PILLAR := 0.62
const PILLAR_H := 1.3
const FLOOR_Y := 0.003
## Trainers' podium rugs: the team colours (BattleView.TEAM_COLORS), darkened.
const TEAM_RUGS: Array[Color] = [Color(0.175, 0.45, 0.475), Color(0.5, 0.225, 0.19)]

## Atlas rows of arena_tiles / arena_tiles_yard (see tools/env_forge/arena.py).
const ROW_PLAIN := 0
const ROW_WORN := 2
const ROW_GROUT := 4
const ROW_SPECIAL := 6
const TILE_COLUMNS := 8

var root: Node3D
var def: ArenaDefinition
var crowd: Array[PixelSprite3D] = []
var trainer_spots: Array[Vector3] = [Vector3(-8.35, 0, 0.9), Vector3(8.35, 0, 0.9)]
var rng := RandomNumberGenerator.new()
var floor_material: ShaderMaterial
var cell_image: Image
var cell_texture: ImageTexture
var _flicker: _Flicker
var _stone := true
var _mat := {}
var _batches := {}  # material key -> Array[AABB], merged into one mesh per material


## Flickers the brazier lights.
class _Flicker:
	extends Node
	var lights: Array[OmniLight3D] = []
	var base_energy: Array[float] = []
	var _t := 0.0

	func _process(delta: float) -> void:
		_t += delta
		for i in lights.size():
			var ph := float(i) * 1.913
			var f := 1.0 + 0.06 * sin(_t * 8.7 + ph) + 0.045 * sin(_t * 14.1 + ph * 2.3) + 0.03 * sin(_t * 23.0 + ph * 0.7)
			lights[i].light_energy = base_energy[i] * f


func build(parent: Node3D, p_def: ArenaDefinition) -> Node3D:
	def = p_def
	_stone = def.floor_style != &"dirt"
	rng.seed = 4242
	root = Node3D.new()
	root.name = "Arena"
	parent.add_child(root)
	_flicker = _Flicker.new()
	_flicker.name = "Flicker"
	root.add_child(_flicker)
	_make_materials()
	var b := def.bounds()
	_floor(b)
	_stage(b)
	if _stone:
		_stone_walls(b)
		_wall_banners(b)
		_bunting(b)
	else:
		_yard_fences(b)
	_corner_pillars(b)
	for c in def.circles:
		_standing_stone(Vector3(c.x, 0, c.y), c.z)
	_podiums(b)
	_wings(b)
	if def.crowd:
		_stands(b)
		_foreground_crowd(b)
	else:
		_yard_props(b)
	_surroundings(b)
	_weeds(b)
	_atmosphere(b)
	_flush_batches()
	_tune_lighting(parent)
	return root


func _make_materials() -> void:
	if _stone:
		_mat["wall"] = _wall_material("arena_wall", Color(0.86, 0.86, 0.9), "", Color.WHITE, 0.35, Vector2(1.0, BACK_WALL_H))
		_mat["block"] = _wall_material("arena_block", Color(0.96, 0.96, 1.0), "arena_coping", Color(0.62, 0.63, 0.7), 0.3, Vector2(0.0, SIDE_WALL_H))
		_mat["pillar"] = _wall_material("arena_block", Color(0.86, 0.86, 0.9), "arena_coping", Color(0.78, 0.8, 0.86), 0.32, Vector2.ZERO)
		_mat["cap"] = _wall_material("arena_coping", Color(0.66, 0.67, 0.74), "arena_coping", Color(0.7, 0.71, 0.78), 0.0, Vector2.ZERO)
		_mat["coping"] = _wall_material("arena_coping", Color(1.0, 0.98, 0.95), "arena_coping", Color.WHITE, 0.0, Vector2.ZERO)
		_mat["stage"] = _wall_material("arena_block", Color(0.72, 0.72, 0.78), "arena_paving", Color(0.74, 0.75, 0.8), 0.4, Vector2(0.0, 0.0))
		_mat["monolith"] = _wall_material("arena_monolith", Color.WHITE, "mossy_stone", Color(0.9, 1.0, 0.85), 0.45, Vector2.ZERO)
	else:
		_mat["wall"] = _wall_material("wood_planks", Color.WHITE, "", Color.WHITE, 0.3, Vector2.ZERO)
		_mat["block"] = _wall_material("wood_dark", Color.WHITE, "wood_planks", Color.WHITE, 0.3, Vector2.ZERO)
		_mat["pillar"] = _wall_material("bark", Color.WHITE, "wood_dark", Color.WHITE, 0.3, Vector2.ZERO)
		_mat["cap"] = _wall_material("wood_planks", Color.WHITE, "wood_planks", Color.WHITE, 0.0, Vector2.ZERO)
		_mat["coping"] = _mat["cap"]
		_mat["stage"] = _wall_material("wood_dark", Color(0.85, 0.85, 0.85), "grass_a", Color(0.92, 0.95, 0.9), 0.4, Vector2.ZERO)
		_mat["monolith"] = _wall_material("rock", Color.WHITE, "mossy_stone", Color.WHITE, 0.45, Vector2.ZERO)


# --- Floor ---------------------------------------------------------------------------------

func _floor(b: Rect2) -> void:
	var mi := MeshInstance3D.new()
	mi.name = "Floor"
	var pm := PlaneMesh.new()
	pm.size = b.size + Vector2.ONE * RIM * 2.0
	mi.mesh = pm
	mi.position = Vector3(b.get_center().x, FLOOR_Y, b.get_center().y)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var m := ShaderMaterial.new()
	m.shader = FLOOR_SHADER
	_set_tex(m, "tiles", "arena_tiles" if _stone else "arena_tiles_yard")
	m.set_shader_parameter("tile_columns", float(TILE_COLUMNS))
	_set_tex(m, "rim", "arena_rim" if _stone else "arena_rim_yard")
	m.set_shader_parameter("rim_width", RIM)
	_set_tex(m, "decals", "arena_decals")
	m.set_shader_parameter("board_rect", Vector4(b.position.x, b.position.y, b.size.x, b.size.y))
	m.set_shader_parameter("cloud_shadow", 0.0 if Settings.graphics_low else 0.24)
	m.set_shader_parameter("glints", 0.004 if _stone else 0.0)
	if _stone:
		var es := _set_tex(m, "emblem", "arena_emblem") / 24.0
		var c := b.get_center()
		m.set_shader_parameter("emblem_rect", Vector4(c.x - es.x * 0.5, c.y - es.y * 0.5, es.x, es.y))
	else:
		m.set_shader_parameter("tint", Color(0.86, 0.84, 0.82))
		m.set_shader_parameter("tone_b", Color(0.9, 0.88, 0.86))
		m.set_shader_parameter("wall_ao", Vector4(0.3, 0.0, 0.25, 0.25))
	var stones: Array[Vector4] = []
	for c in def.circles:
		stones.append(Vector4(c.x, c.y, c.z, 0.4))
	while stones.size() < 6:
		stones.append(Vector4.ZERO)
	m.set_shader_parameter("stones", stones)
	m.set_shader_parameter("stone_count", mini(def.circles.size(), 6))
	_build_cells(b)
	m.set_shader_parameter("cells", cell_texture)
	mi.material_override = m
	floor_material = m
	root.add_child(mi)


## Per-cell data for the floor shader (see arena_floor.gdshader).
func _build_cells(b: Rect2) -> void:
	var n := def.cell_count()
	cell_image = Image.create(n.x, n.y, false, Image.FORMAT_RGBA8)
	var stone_cells := {}
	for c in def.circles:
		stone_cells[def.cell_of(Vector2(c.x, c.y))] = true
	var spawn_cells := [def.cell_of(def.spawn_team0), def.cell_of(def.spawn_team1)]
	for y in n.y:
		for x in n.x:
			var cell := Vector2i(x, y)
			var tile := _pick_tile(cell, n, stone_cells.has(cell))
			cell_image.set_pixel(x, y, Color8(tile, 0, 0, 0))
	_scatter_scorch(n, stone_cells, spawn_cells, b)
	cell_texture = ImageTexture.create_from_image(cell_image)


func _pick_tile(cell: Vector2i, n: Vector2i, is_stone: bool) -> int:
	var tone := (cell.x + cell.y) % 2
	if is_stone:
		return ROW_SPECIAL * TILE_COLUMNS + tone
	var centre := (Vector2(cell) + Vector2(0.5, 0.5)) - Vector2(n) * 0.5
	var d := Vector2(centre.x / (n.x * 0.5), centre.y / (n.y * 0.5)).length()
	var at_wall := cell.x == 0 or cell.x == n.x - 1 or cell.y == 0
	if at_wall and rng.randf() < 0.65:
		return (ROW_GROUT + tone) * TILE_COLUMNS + rng.randi_range(0, 3)
	if cell.y == n.y - 1 and rng.randf() < 0.55:
		return (ROW_GROUT + tone) * TILE_COLUMNS + rng.randi_range(4, 7)
	if d < 0.62 and rng.randf() < 0.9 - d:
		return (ROW_WORN + tone) * TILE_COLUMNS + rng.randi_range(0, TILE_COLUMNS - 1)
	var weights := [0.2, 0.2, 0.14, 0.1, 0.1, 0.1, 0.08, 0.08]
	var r := rng.randf()
	var col := 0
	while col < TILE_COLUMNS - 1 and r > weights[col]:
		r -= weights[col]
		col += 1
	return (ROW_PLAIN + tone) * TILE_COLUMNS + col


func _scatter_scorch(n: Vector2i, stone_cells: Dictionary, spawn_cells: Array, b: Rect2) -> void:
	var placed := 0
	var tries := 0
	var used: Array[Vector2i] = []
	var want := 5 if _stone else 2
	while placed < want and tries < 200:
		tries += 1
		var cell := Vector2i(rng.randi_range(1, n.x - 2), rng.randi_range(1, n.y - 2))
		if stone_cells.has(cell) or spawn_cells.has(cell) or def.cell_center(cell).distance_to(b.get_center()) < 2.9:
			continue
		var near := false
		for u in used:
			if absi(u.x - cell.x) + absi(u.y - cell.y) < 4:
				near = true
		if near:
			continue
		used.append(cell)
		var px := cell_image.get_pixelv(cell)
		var g := (placed % 4 + 1) | (rng.randi_range(0, 3) << 3)
		cell_image.set_pixelv(cell, Color8(px.r8, g, px.b8, px.a8))
		placed += 1


## Light up cells on the floor (e.g. for move previews): strength 0..1, 0 clears.
func set_cell_highlight(cell: Vector2i, strength: float) -> void:
	if cell_image == null or not def.has_cell(cell):
		return
	var px := cell_image.get_pixelv(cell)
	cell_image.set_pixelv(cell, Color8(px.r8, px.g8, px.b8, int(clampf(strength, 0.0, 1.0) * 255.0)))
	cell_texture.update(cell_image)


# --- Stage, walls, pillars ------------------------------------------------------------------

func _stage(b: Rect2) -> void:
	var half_w := b.size.x * 0.5 + RIM + WING
	var front := b.end.y + RIM
	var back := b.position.y - RIM - BACK_WALL_T - 3.6  # also under the stands
	var stage := _box(Vector3(half_w * 2.0, STAGE_DROP, front - back), Vector3(b.get_center().x, -STAGE_DROP, (front + back) * 0.5), _mat["stage"])
	# flat under the floor: casting would only self-shadow the board (acne)
	stage.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# a darker plinth course along the open front gives the stage edge some weight
	_queue(AABB(Vector3(b.get_center().x - half_w, -STAGE_DROP, front - 0.02), Vector3(half_w * 2.0, 0.1, 0.08)), "cap")


func _stone_walls(b: Rect2) -> void:
	var x_in := b.size.x * 0.5 + RIM
	var z_back := b.position.y - RIM
	var z_front := b.end.y + RIM
	var cx := b.get_center().x
	# Back wall, its coping, and a pilaster on every second column line.
	var bw := (x_in + PILLAR) * 2.0
	_queue_box(Vector3(bw, BACK_WALL_H, BACK_WALL_T), Vector3(cx, 0.0, z_back - BACK_WALL_T * 0.5), "wall")
	_queue_box(Vector3(bw + 0.1, 0.14, BACK_WALL_T + 0.16), Vector3(cx, BACK_WALL_H, z_back - BACK_WALL_T * 0.5 + 0.03), "coping")
	var x := b.position.x
	while x <= b.end.x + 0.01:
		_queue(AABB(Vector3(x - 0.17, 0.0, z_back - 0.02), Vector3(0.34, BACK_WALL_H, 0.14)), "pillar")
		_queue(AABB(Vector3(x - 0.21, BACK_WALL_H - 0.12, z_back - 0.02), Vector3(0.42, 0.12, 0.19)), "cap")
		x += 2.0
	# Side walls on the rim's outer edge with a merlon on every row, so the
	# walls read as rulers along the board.
	for s: float in [-1.0, 1.0]:
		var x0 := cx + s * (x_in + SIDE_WALL_T * 0.5) - SIDE_WALL_T * 0.5
		_queue(AABB(Vector3(x0, 0.0, z_back), Vector3(SIDE_WALL_T, SIDE_WALL_H, z_front - z_back)), "block")
		for r in def.cell_count().y:
			var z := b.position.y + r + 0.5
			_queue(AABB(Vector3(x0 - 0.03, SIDE_WALL_H, z - 0.28), Vector3(SIDE_WALL_T + 0.06, 0.17, 0.56)), "cap")


func _wall_banners(b: Rect2) -> void:
	var tex := EnvKit.tex("arena_banners")
	var z := b.position.y - RIM + 0.02
	var xs := [-6.0, -2.0, 2.0, 6.0]
	for i in xs.size():
		var x: float = b.get_center().x + xs[i]
		if absf(xs[i]) > b.size.x * 0.5:
			continue
		var mi := MeshInstance3D.new()
		var q := QuadMesh.new()
		q.size = Vector2(16.0, 30.0) / 24.0
		q.center_offset = Vector3(0, -q.size.y * 0.5, 0)
		mi.mesh = q
		var m := ShaderMaterial.new()
		m.shader = CLOTH_SHADER
		m.set_shader_parameter("atlas", tex)
		m.set_shader_parameter("atlas_size", tex.get_size())
		m.set_shader_parameter("region", Vector4(0.0 if xs[i] < 0.0 else 16.0, 0.0, 16.0, 30.0))
		m.set_shader_parameter("seed", float(i) * 1.7)
		mi.material_override = m
		mi.position = Vector3(x, BACK_WALL_H - 0.04, z + 0.06)
		root.add_child(mi)


## Festival bunting strung along the top of the back wall, sagging between
## the pilasters (one mesh, one draw call).
func _bunting(b: Rect2) -> void:
	var tex := EnvKit.tex("arena_pennants")
	var pw := 8.0 / 24.0
	var ph := 9.0 / 24.0
	var z := b.position.y - RIM + 0.16
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var count := int(round(b.size.x / pw))
	for i in count:
		var x0 := b.position.x + i * pw
		var t := fposmod(x0 + pw * 0.5 - b.position.x, 2.0) / 2.0  # position within a 2-unit span
		var y_top := BACK_WALL_H - 0.03 - 0.13 * 4.0 * t * (1.0 - t)
		var u0 := float(i % 3) / 3.0
		var quad := [Vector3(x0, y_top, z), Vector3(x0 + pw, y_top, z), Vector3(x0 + pw, y_top - ph, z), Vector3(x0, y_top - ph, z)]
		var uvs := [Vector2(u0, 0.0), Vector2(u0 + 1.0 / 3.0, 0.0), Vector2(u0 + 1.0 / 3.0, 1.0), Vector2(u0, 1.0)]
		for k: int in [0, 1, 2, 0, 2, 3]:
			st.set_normal(Vector3.BACK)
			st.set_uv(uvs[k])
			st.add_vertex(quad[k])
	var m := ShaderMaterial.new()
	m.shader = CLOTH_SHADER
	m.set_shader_parameter("atlas", tex)
	m.set_shader_parameter("atlas_size", tex.get_size())
	m.set_shader_parameter("region", Vector4(0.0, 0.0, tex.get_size().x, tex.get_size().y))
	m.set_shader_parameter("sway", 0.025)
	var mi := _mesh(st.commit(), m, Vector3.ZERO)
	mi.name = "Bunting"
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF


func _yard_fences(b: Rect2) -> void:
	var x_in := b.size.x * 0.5 + RIM
	var z_back := b.position.y - RIM
	var z_front := b.end.y + RIM
	var cx := b.get_center().x
	var posts: Array[AABB] = []
	var rails: Array[AABB] = []
	# back fence: posts on every column line, two rails
	var x := b.position.x
	while x <= b.end.x + 0.01:
		posts.append(AABB(Vector3(cx + x - 0.08, 0.0, z_back - 0.2), Vector3(0.16, 0.95, 0.16)))
		x += 1.0
	for h: float in [0.4, 0.78]:
		rails.append(AABB(Vector3(cx - x_in - 0.1, h, z_back - 0.18), Vector3((x_in + 0.1) * 2.0, 0.1, 0.08)))
	# side fences: low posts on every row line, one rail
	for s: float in [-1.0, 1.0]:
		var xs := cx + s * (x_in + 0.12)
		var z := b.position.y
		while z <= b.end.y + 0.01:
			posts.append(AABB(Vector3(xs - 0.07, 0.0, z - 0.07), Vector3(0.14, 0.5, 0.14)))
			z += 1.0
		rails.append(AABB(Vector3(xs - 0.04, 0.3, z_back), Vector3(0.08, 0.09, z_front - z_back)))
	for bx in posts:
		_queue(bx, "pillar")
	for bx in rails:
		_queue(bx, "block")


func _corner_pillars(b: Rect2) -> void:
	var x_in := b.size.x * 0.5 + RIM
	var low := Settings.graphics_low
	for sz: float in [-1.0, 1.0]:
		for sx: float in [-1.0, 1.0]:
			var px := b.get_center().x + sx * (x_in + PILLAR * 0.5 - 0.02)
			var pz := (b.position.y - RIM - BACK_WALL_T * 0.5) if sz < 0.0 else (b.end.y + RIM - PILLAR * 0.5)
			var h := PILLAR_H + (0.5 if sz < 0.0 else 0.0)
			var p := Vector3(px, 0.0, pz)
			if _stone:
				_queue_box(Vector3(PILLAR + 0.12, 0.16, PILLAR + 0.12), p, "cap")
				_queue_box(Vector3(PILLAR, h, PILLAR), p, "pillar")
				_queue_box(Vector3(PILLAR + 0.16, 0.13, PILLAR + 0.16), p + Vector3(0, h, 0), "cap")
				_brazier(p + Vector3(0, h + 0.13, 0), not low or sz > 0.0)
			else:
				_lantern(p + Vector3(sx * 0.15, 0.0, 0.0), not low or sz > 0.0)


func _brazier(top: Vector3, with_light: bool) -> void:
	_brazier_bowl(top)
	_fire(top + Vector3(0, 0.14, 0), Vector2(0.72, 1.04))
	_glow(top + Vector3(0, 0.6, 0), 2.8, Color(1.0, 0.55, 0.22), 0.34)
	if with_light:
		_light(top + Vector3(0, 0.7, 0), Color(1.0, 0.56, 0.26), 2.8, 6.5)
	if not Settings.graphics_low:
		_embers(top + Vector3(0, 0.45, 0))


## Iron bowl with a bronze lip and a bed of glowing coals.
func _brazier_bowl(top: Vector3) -> void:
	var bowl := CylinderMesh.new()
	bowl.top_radius = 0.3
	bowl.bottom_radius = 0.16
	bowl.height = 0.2
	bowl.radial_segments = 10
	bowl.rings = 1
	_mesh(bowl, _metal(Color(0.1, 0.085, 0.08), 0.35, 0.5), top + Vector3(0, 0.1, 0))
	var lip := TorusMesh.new()
	lip.inner_radius = 0.27
	lip.outer_radius = 0.32
	lip.rings = 12
	lip.ring_segments = 4
	_mesh(lip, _metal(Color(0.62, 0.43, 0.18), 0.5, 0.45), top + Vector3(0, 0.2, 0))
	var coals := CylinderMesh.new()
	coals.top_radius = 0.26
	coals.bottom_radius = 0.26
	coals.height = 0.02
	coals.radial_segments = 10
	coals.rings = 1
	var hot := StandardMaterial3D.new()
	hot.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	hot.albedo_color = Color(1.0, 0.42, 0.12)
	_mesh(coals, hot, top + Vector3(0, 0.19, 0)).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF


## A lantern post standing on the deck (yard corners).
func _lantern(base: Vector3, with_light: bool) -> void:
	var s := EnvKit.prop(root, "lantern_post", base, 1.0, true)
	s.set_param("emission_strength", 2.2)
	s.set_param("emission_threshold", 0.7)
	var top := base + Vector3(0, 1.75, 0)
	_glow(top, 1.4, Color(1.0, 0.78, 0.45), 0.22)
	if with_light:
		_light(top, Color(1.0, 0.78, 0.5), 1.1, 4.5)


func _fire(pos: Vector3, size: Vector2) -> MeshInstance3D:
	var fire := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = size
	q.center_offset = Vector3(0, size.y * 0.5, 0)
	fire.mesh = q
	var fm := ShaderMaterial.new()
	fm.shader = FIRE_SHADER
	fm.set_shader_parameter("quad_size", size)
	fm.set_shader_parameter("seed", rng.randf() * 10.0)
	fire.material_override = fm
	fire.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	fire.position = pos
	root.add_child(fire)
	return fire


func _light(pos: Vector3, color: Color, energy: float, reach: float) -> OmniLight3D:
	var light := OmniLight3D.new()
	light.light_color = color
	light.light_energy = energy
	light.omni_range = reach
	light.omni_attenuation = 1.2
	light.shadow_enabled = false
	light.position = pos
	root.add_child(light)
	_flicker.lights.append(light)
	_flicker.base_energy.append(energy)
	return light


func _glow(pos: Vector3, size: float, color: Color, intensity: float) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = Vector2.ONE * size
	mi.mesh = q
	var m := ShaderMaterial.new()
	m.shader = GLOW_SHADER
	m.set_shader_parameter("color", color)
	m.set_shader_parameter("intensity", intensity)
	m.set_shader_parameter("seed", rng.randf() * 10.0)
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.position = pos
	root.add_child(mi)
	return mi


func _embers(pos: Vector3) -> void:
	var p := CPUParticles3D.new()
	p.amount = 10
	p.lifetime = 1.6
	p.preprocess = 1.6
	p.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	p.emission_sphere_radius = 0.16
	p.direction = Vector3(0, 1, 0)
	p.spread = 25.0
	p.initial_velocity_min = 0.5
	p.initial_velocity_max = 1.0
	p.gravity = Vector3(0.15, 0.25, 0)
	p.damping_min = 0.3
	p.damping_max = 0.6
	p.mesh = _speck_mesh(1.4)
	var g := Gradient.new()
	g.set_color(0, Color(1.6, 1.2, 0.5, 1.0))
	g.add_point(0.5, Color(1.3, 0.55, 0.15, 0.9))
	g.set_color(g.get_point_count() - 1, Color(0.6, 0.15, 0.05, 0.0))
	p.color_ramp = g
	p.position = pos
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(p)


# --- Standing stones ----------------------------------------------------------------------

## A carved menhir on its cell with a bronze ring (the Ringstones), using the
## simulation's obstacle radius for its footprint.
func _standing_stone(pos: Vector3, radius: float) -> void:
	var h := 1.22
	var mi := MeshInstance3D.new()
	mi.mesh = _menhir_mesh(radius * 0.96, radius * 0.7, h)
	mi.material_override = _mat["monolith"]
	mi.position = pos
	mi.rotation.y = rng.randf() * TAU
	root.add_child(mi)
	var band := CylinderMesh.new()
	band.top_radius = radius * 0.83
	band.bottom_radius = radius * 0.85
	band.height = 0.06
	band.radial_segments = 12
	band.rings = 1
	_mesh(band, _metal(Color(0.55, 0.38, 0.18), 0.4, 0.55), pos + Vector3(0, h * 0.58, 0))
	EnvKit.blob_shadow(root, radius * 1.45, 0.32).position = pos + Vector3(0, 0.014, 0)


## A weathered, slightly irregular menhir: a tapering hexagonal prism with a
## sloped, chamfered top (flat-shaded so the faces read under the sun).
static func _menhir_mesh(r0: float, r1: float, h: float) -> ArrayMesh:
	var sides := 6
	var jitter := [1.0, 0.86, 1.08, 0.93, 1.04, 0.9]
	var lift := [0.1, 0.02, -0.07, -0.04, 0.05, 0.12]
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var ring0: Array[Vector3] = []
	var ring1: Array[Vector3] = []
	var ring2: Array[Vector3] = []
	for i in sides:
		var a := TAU * float(i) / sides + 0.3
		var j: float = jitter[i]
		var d := Vector3(cos(a), 0.0, sin(a))
		ring0.append(d * r0 * j)
		ring1.append(d * r1 * j + Vector3(0.0, h * 0.8 + float(lift[i]) * 0.4, 0.0))
		ring2.append(d * r1 * j * 0.7 + Vector3(0.0, h + float(lift[i]), 0.0))
	_menhir_band(st, ring0, ring1)
	_menhir_band(st, ring1, ring2)
	var top := Vector3(0.03, h + 0.1, -0.02)
	for i in sides:
		var p0 := ring2[i]
		var p1 := ring2[(i + 1) % sides]
		var n := (p1 - top).cross(p0 - top).normalized()
		for v in [top, p0, p1]:
			st.set_normal(n)
			st.add_vertex(v)
	return st.commit()


static func _menhir_band(st: SurfaceTool, lo: Array[Vector3], hi: Array[Vector3]) -> void:
	var n_sides := lo.size()
	for i in n_sides:
		var p0 := lo[i]
		var p1 := lo[(i + 1) % n_sides]
		var p2 := hi[(i + 1) % n_sides]
		var p3 := hi[i]
		var n := (p1 - p0).cross(p3 - p0).normalized() * -1.0
		for v in [p0, p1, p2, p0, p2, p3]:
			st.set_normal(n)
			st.add_vertex(v)


# --- Trainers' podiums and the wings ----------------------------------------------------------

func _podiums(b: Rect2) -> void:
	var x := b.size.x * 0.5 + RIM + SIDE_WALL_T + 0.5
	var z := b.get_center().y + 0.5
	var h := 0.14
	trainer_spots = [Vector3(b.get_center().x - x, h, z), Vector3(b.get_center().x + x, h, z)]
	for i in 2:
		var p := trainer_spots[i]
		_queue_box(Vector3(0.95, h, 1.2), Vector3(p.x, 0.0, p.z), "coping")
		var rug := PlaneMesh.new()
		rug.size = Vector2(0.6, 0.95)
		_mesh(rug, _metal(TEAM_RUGS[i], 0.0, 1.0), p + Vector3(0, 0.004, 0))


## Decorations on the stage wings beyond the side walls; mostly seen on wide
## (phone) screens: standing team banners and a few spectators.
func _wings(b: Rect2) -> void:
	var x_out := b.size.x * 0.5 + RIM + SIDE_WALL_T + 1.35
	for i in 2:
		var s := -1.0 if i == 0 else 1.0
		for z: float in [-3.2, 3.6]:
			var p := Vector3(b.get_center().x + s * x_out, 0.0, b.get_center().y + z)
			EnvKit.animated_prop(root, "banner_blue" if i == 0 else "banner_red", "wave", p, true)
	if not def.crowd:
		return
	var sheet := SpriteSheet.load_sheet(CROWD_SHEET)
	for i in 2:
		var s := -1.0 if i == 0 else 1.0
		var z := b.position.y + 0.6
		while z < b.end.y:
			var x := b.size.x * 0.5 + RIM + SIDE_WALL_T + rng.randf_range(2.2, 3.2)
			if rng.randf() < 0.75:
				_crowd_member(sheet, Vector3(b.get_center().x + s * x, 0.0, z), false)
			z += rng.randf_range(1.0, 1.6)


## Training-yard dressing on the lawn beside the board: hay, barrels, crates and
## a couple of villagers watching.
func _yard_props(b: Rect2) -> void:
	var x_out := b.size.x * 0.5 + RIM + 0.9
	var cx := b.get_center().x
	var z0 := b.position.y
	EnvKit.prop(root, "hay_bale", Vector3(cx - x_out - 0.6, 0.0, z0 + 0.4))
	EnvKit.prop(root, "hay_bale", Vector3(cx - x_out - 1.4, 0.0, z0 + 1.0), 0.9)
	EnvKit.prop(root, "barrel", Vector3(cx + x_out + 0.5, 0.0, z0 + 0.3))
	EnvKit.prop(root, "crate", Vector3(cx + x_out + 1.3, 0.0, z0 + 0.6))
	EnvKit.prop(root, "barrel", Vector3(cx + x_out + 0.9, 0.0, b.end.y - 0.6), 0.9)
	EnvKit.prop(root, "crate", Vector3(cx - x_out - 0.9, 0.0, b.end.y - 0.4))
	var folk := [["villager_farmer", Vector3(cx - x_out - 1.6, 0.0, z0 + 2.6), "e"], ["villager_baker", Vector3(cx + x_out + 1.7, 0.0, b.end.y - 2.2), "w"]]
	for f in folk:
		var s := PixelSprite3D.new()
		s.load_manifest("res://assets/sprites/characters/%s.json" % f[0])
		s.position = f[1]
		root.add_child(s)
		s.play("idle", f[2])
		EnvKit.blob_shadow(root, 0.32, 0.35).position = (f[1] as Vector3) + Vector3(0, 0.015, 0)


# --- Crowd ------------------------------------------------------------------------------------

func _stands(b: Rect2) -> void:
	var sheet := SpriteSheet.load_sheet(CROWD_SHEET)
	var z0 := b.position.y - RIM - BACK_WALL_T - 0.5
	var half := b.size.x * 0.5 + 1.0
	for tier in 3:
		var h := BACK_WALL_H * 0.55 + tier * 0.5
		var z := z0 - tier * 0.8
		_queue_box(Vector3(half * 2.0 + 2.0, h, 0.8), Vector3(b.get_center().x, 0.0, z), "stage")
		var x := -half + rng.randf_range(0.0, 0.5)
		while x < half:
			if rng.randf() < 0.85:
				_crowd_member(sheet, Vector3(b.get_center().x + x, h - 0.04, z + 0.1), false)
			x += rng.randf_range(0.7, 1.0)


func _foreground_crowd(b: Rect2) -> void:
	var sheet := SpriteSheet.load_sheet(CROWD_BACK_SHEET)
	var x := b.position.x - 4.0
	while x < b.end.x + 4.0:
		var s := _crowd_member(sheet, Vector3(x, -STAGE_DROP, b.end.y + RIM + 1.5 + rng.randf_range(0.0, 0.4)), true)
		s.scale = Vector3.ONE * 1.2
		s.set_param("modulate", Color(0.58, 0.55, 0.62))
		x += rng.randf_range(0.85, 1.2)


func _crowd_member(sheet: SpriteSheet, pos: Vector3, back: bool) -> PixelSprite3D:
	var s := PixelSprite3D.new()
	s.set_sheet(sheet)
	s.position = pos
	s.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(s)
	var v := rng.randi_range(0, 5 if back else 7)
	s.set_meta("variant", v)
	if back:
		s.set_meta("back", true)
	s.play("idle_v%d" % v, "s")
	s.speed_scale = rng.randf_range(0.7, 1.3)
	crowd.append(s)
	return s


# --- Surroundings and atmosphere ---------------------------------------------------------------

func _surroundings(b: Rect2) -> void:
	var rect := Rect2(-30, -24, 60, 46)
	var img := Image.create(int(rect.size.x), int(rect.size.y), false, Image.FORMAT_RGBA8)
	for y in img.get_height():
		for x in img.get_width():
			var wx := rect.position.x + x + 0.5
			var wz := rect.position.y + y + 0.5
			var g := 0.0
			var bl := 0.0
			# a trodden earth apron in front of the stage, cobbles here and there
			if wz > b.end.y and wz < b.end.y + 4.0 and absf(wx) < b.size.x * 0.5 + 5.0:
				g = 1.0
			elif EnvKit.noise2(wx * 0.4, wz * 0.4, 5) > 0.7:
				bl = 1.0
			img.set_pixel(x, y, Color(0.0, g, bl, 0.0))
	var t := EnvKit.terrain(root, rect, img, ["grass_a", "sand_arena", "dirt_path", "grass_b", "flower_meadow"])
	t.position.y = -STAGE_DROP
	var kinds := ["tree_oak_a", "tree_oak_b", "tree_pine", "tree_birch"]
	var x := b.position.x - 9.0
	while x < b.end.x + 9.0:
		EnvKit.foliage(root, kinds[rng.randi() % kinds.size()], Vector3(x, -STAGE_DROP, b.position.y - 6.8 - rng.randf_range(0, 2.0)), rng.randf_range(1.0, 1.25), false, 1.2)
		x += rng.randf_range(1.6, 2.6)


## Grass and weeds where stone meets stone: along the outer foot of the side
## walls, the back wall's ends and the stage's open front (one MultiMesh).
func _weeds(b: Rect2) -> void:
	var atlas := EnvKit.atlas(["grass_tuft_a", "grass_tuft_b", "grass_tuft_c", "grass_tuft_d", "rock_small_a", "flowers_yellow", "flowers_white"])
	var items: Array = []
	var x_wall := b.size.x * 0.5 + RIM + SIDE_WALL_T
	for s: float in [-1.0, 1.0]:
		var z := b.position.y - RIM + rng.randf_range(0.0, 0.5)
		while z < b.end.y + RIM:
			var x := b.get_center().x + s * (x_wall + rng.randf_range(0.04, 0.3))
			items.append([Vector3(x, 0.0, z), _weed_index(), rng.randf_range(0.7, 1.0)])
			z += rng.randf_range(0.5, 1.4)
	var x2 := b.position.x - RIM - 2.5
	while x2 < b.end.x + RIM + 2.5:
		if rng.randf() < 0.7:
			var idx := rng.randi_range(0, 3) if rng.randf() < 0.75 else rng.randi_range(5, 6)
			items.append([Vector3(x2, -STAGE_DROP, b.end.y + RIM + rng.randf_range(0.06, 0.5)), idx, rng.randf_range(0.75, 1.0)])
		x2 += rng.randf_range(0.5, 1.4)
	EnvKit.scatter(root, atlas, items, false, 0.5)


func _weed_index() -> int:
	var r := rng.randf()
	if r < 0.7:
		return rng.randi_range(0, 3)
	return rng.randi_range(4, 6)


func _atmosphere(b: Rect2) -> void:
	var p := CPUParticles3D.new()
	p.amount = 24 if Settings.graphics_low else 70
	p.lifetime = 8.0
	p.preprocess = 8.0
	p.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	p.emission_box_extents = Vector3(b.size.x * 0.5 + 1.5, 1.0, b.size.y * 0.5 + 1.0)
	p.position = Vector3(b.get_center().x, 1.2, b.get_center().y)
	p.direction = Vector3(0.5, 0.25, -0.2)
	p.spread = 70.0
	p.initial_velocity_min = 0.08
	p.initial_velocity_max = 0.3
	p.gravity = Vector3(0, 0.015, 0)
	p.mesh = _speck_mesh(1.0)
	var g := Gradient.new()
	g.set_color(0, Color(1.3, 1.15, 0.8, 0.0))
	g.add_point(0.2, Color(1.3, 1.15, 0.8, 0.85))
	g.add_point(0.8, Color(1.2, 1.05, 0.75, 0.85))
	g.set_color(g.get_point_count() - 1, Color(1.2, 1.0, 0.7, 0.0))
	p.color_ramp = g
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(p)


static func _speck_mesh(texels: float) -> QuadMesh:
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE * texels / 24.0
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	quad.material = m
	return quad


# --- Lighting and post ---------------------------------------------------------------------------

## Switch a LightingRig built next to the arena to its arena variant (higher
## sun for short, crisp shadows; battle-camera shadow range).
func _tune_lighting(parent: Node) -> void:
	for c in parent.get_children():
		if c is LightingRig:
			var rig := c as LightingRig
			var arena_preset := StringName("arena_" + String(rig.preset_name))
			if LightingRig.PRESETS.has(arena_preset):
				rig.apply(arena_preset)


## Battle post-processing for this arena: the sharp band covers the board
## and the HUD bands above and below soften; warm highlights, cool shadows, a
## firmer vignette and faint sun shafts (skipped with Settings.graphics_low).
static func apply_post(post: PostFX, p_def: ArenaDefinition) -> void:
	var stone := p_def.floor_style != &"dirt"
	post.set_focus(0.49, 0.36)
	post.set_param("blur_ramp", 0.11)
	post.set_param("vignette", 0.46)
	post.set_param("saturation", 1.18)
	post.set_param("contrast", 1.12)
	post.set_param("shadow_tint", Vector3(0.88, 0.94, 1.12))
	post.set_param("highlight_tint", Vector3(1.05, 1.0, 0.93) if stone else Vector3(1.03, 1.0, 0.96))
	post.set_param("shafts", 0.0 if Settings.graphics_low else (0.14 if stone else 0.1))
	post.set_param("shaft_color", Color(1.0, 0.85, 0.6) if stone else Color(1.0, 0.95, 0.82))


# --- Helpers ----------------------------------------------------------------------------------------

## Sets texture `param` (and `param`_size) on `m`; returns the texture size.
static func _set_tex(m: ShaderMaterial, param: String, tex_name: String) -> Vector2:
	var t := EnvKit.tex(tex_name)
	m.set_shader_parameter(param, t)
	m.set_shader_parameter(param + "_size", t.get_size())
	return t.get_size()


## Triplanar pixel material; `align` = uv offset so courses and bays line up with the geometry.
static func _wall_material(tex_name: String, tint: Color, top: String, top_tint: Color, ao: float, align: Vector2) -> ShaderMaterial:
	var m := EnvKit.material(tex_name, tint, top, top_tint, ao).duplicate() as ShaderMaterial
	m.set_shader_parameter("uv_offset", align)
	return m


static func _metal(albedo: Color, metallic: float, roughness: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = albedo
	m.metallic = metallic
	m.roughness = roughness
	return m


func _mesh(mesh: Mesh, mat: Material, pos: Vector3) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = mat
	mi.position = pos
	root.add_child(mi)
	return mi


func _box(size: Vector3, pos: Vector3, mat: Material) -> MeshInstance3D:
	return EnvKit.box(root, size, pos, mat)


## Queue a static box (EnvKit.box placement: `pos` is its bottom centre) for batching.
func _queue_box(size: Vector3, pos: Vector3, key: String) -> void:
	_queue(AABB(pos - Vector3(size.x * 0.5, 0.0, size.z * 0.5), size), key)


func _queue(bx: AABB, key: String) -> void:
	if not _batches.has(key):
		var boxes: Array[AABB] = []
		_batches[key] = boxes
	(_batches[key] as Array[AABB]).append(bx)


## One mesh per material for every queued box (one draw call each).
func _flush_batches() -> void:
	for key: String in _batches.keys():
		_merged(_batches[key], _mat[key], "Batch_" + key)
	_batches.clear()


## One mesh (one draw call) from many axis-aligned boxes.
func _merged(boxes: Array[AABB], mat: Material, node_name: String) -> MeshInstance3D:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for bx in boxes:
		_add_box(st, bx)
	var mi := MeshInstance3D.new()
	mi.name = node_name
	mi.mesh = st.commit()
	mi.material_override = mat
	root.add_child(mi)
	return mi


static func _add_box(st: SurfaceTool, bx: AABB) -> void:
	var p := bx.position
	var e := bx.end
	var faces := [
		[Vector3(0, 0, 1), [Vector3(p.x, p.y, e.z), Vector3(e.x, p.y, e.z), Vector3(e.x, e.y, e.z), Vector3(p.x, e.y, e.z)]],
		[Vector3(0, 0, -1), [Vector3(e.x, p.y, p.z), Vector3(p.x, p.y, p.z), Vector3(p.x, e.y, p.z), Vector3(e.x, e.y, p.z)]],
		[Vector3(1, 0, 0), [Vector3(e.x, p.y, e.z), Vector3(e.x, p.y, p.z), Vector3(e.x, e.y, p.z), Vector3(e.x, e.y, e.z)]],
		[Vector3(-1, 0, 0), [Vector3(p.x, p.y, p.z), Vector3(p.x, p.y, e.z), Vector3(p.x, e.y, e.z), Vector3(p.x, e.y, p.z)]],
		[Vector3(0, 1, 0), [Vector3(p.x, e.y, e.z), Vector3(e.x, e.y, e.z), Vector3(e.x, e.y, p.z), Vector3(p.x, e.y, p.z)]],
		[Vector3(0, -1, 0), [Vector3(p.x, p.y, p.z), Vector3(e.x, p.y, p.z), Vector3(e.x, p.y, e.z), Vector3(p.x, p.y, e.z)]],
	]
	for f in faces:
		var n: Vector3 = f[0]
		var v: Array = f[1]
		for i: int in [0, 2, 1, 0, 3, 2]:
			st.set_normal(n)
			st.add_vertex(v[i])


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
