class_name ArenaBuilder
extends RefCounted
## Builds the battle arena around an ArenaDefinition as an HD-2D diorama.
##
## The Ringstones: the board is a raised stone dais with one beveled
## flagstone per cell (real geometry; the joints are the cell lines, so lanes
## read at a glance), worn and very slightly uneven but never by more than
## 4 mm above the floor plane the gameplay draws on. A flush rim of slabs
## (joints on the columns and rows, bronze studs) frames it; three steps go
## down to a paved lower ring at the front and sides; a carved back wall with
## team banners and torches closes the back. Pillars with braziers stand at
## the corners and tripod braziers at the sides, so warm flickering pools
## light the board's edges; tall banner poles on the side rings lay long
## shadows across it. Tiered stands with the crowd rise behind the back wall
## and along both sides, a low barrier and the backs of the front row frame
## the bottom, and trees fall away into the depth of field. The standing
## stones use exactly the simulation's radii.
##
## The training yard is the same board in packed earth framed by flush
## timber laths on the cell lines, on a timber deck with sleeper steps down
## to the lawn, fenced, with lantern posts, hay, barrels and a few villagers.
##
## Light and atmosphere: the lighting rig's arena preset (a low warm sun with
## soft shadows and a cool sky fill), brazier and lantern point lights that
## flicker, glows and embers, god rays, drifting dust, contact shadows where
## walls meet floors, and a depth-aware tilt-shift pass (high graphics) that
## keeps the whole board sharp. apply_post() sets the matching screen grade.
##
## Every static piece that shares a material is merged into one mesh, the
## crowd is one MultiMesh per sheet, so the arena costs a few dozen draw
## calls. With Settings.graphics_low: fewer lights, no god rays, embers or
## depth pass (the screen-space tilt-shift band is used instead), fewer motes.

const CROWD_SHEET := "res://assets/sprites/characters/crowd.json"
const CROWD_BACK_SHEET := "res://assets/sprites/characters/crowd_back.json"
const FLOOR_SHADER := preload("res://shaders/arena_floor.gdshader")
const STONE_SHADER := preload("res://shaders/arena_stone.gdshader")
const GROUND_SHADER := preload("res://shaders/arena_ground.gdshader")
const FIRE_SHADER := preload("res://shaders/arena_fire.gdshader")
const GLOW_SHADER := preload("res://shaders/arena_glow.gdshader")
const CLOTH_SHADER := preload("res://shaders/arena_cloth.gdshader")
const DOF_SHADER := preload("res://shaders/arena_dof.gdshader")
const SPRITE_SHADER := preload("res://shaders/pixel_sprite.gdshader")
const BANNERS: Array[String] = ["arena_banner_teal", "arena_banner_red", "arena_banner_gold"]

## Board geometry (world units; 1 cell = 1 unit = 48 texels).
const TEXELS := 48.0
const RIM := 0.5
## Half the joint between two flagstones (the joint is centred on the cell line).
const JOINT := 0.026
const BEVEL := 0.042
const MORTAR_Y := -0.075
## Flagstone tops stay between these heights: the dash lanes (y 0.026) and
## telegraphs (0.03) always draw above them, blob shadows (0.015) too.
const TILE_TOP_MAX := 0.003
const TILE_TOP_MIN := -0.014
const STEP_RISE := 0.18
const STEP_RUN := 0.32
const STEPS := 3
const RING_Y := -0.54
const BACK_WALL_T := 0.42
const BACK_WALL_H := 1.05
## Trainers' podium rugs: the team colours (BattleView.TEAM_COLORS), darkened.
const TEAM_RUGS: Array[Color] = [Color(0.175, 0.45, 0.475), Color(0.5, 0.225, 0.19)]

## Floor atlas layout (tools/env_forge/arena_hd.py): 56 px cells, 4 px gutters.
const ATLAS_CELL := 56.0
const ATLAS_GUTTER := 4.0
const ROW_A := 0
const ROW_B := 2
const ROW_WORN := 4
const ROW_SPECIAL := 5
const ROW_RIM := 6
const ROW_RIM2 := 7
const SPECIAL_PLINTH := 0
const SPECIAL_EDGE := 3  # 3..6: moss A, moss B, sand A, sand B
const MORTAR_CELL := Vector2(2, 7)

var root: Node3D
var def: ArenaDefinition
var trainer_spots: Array[Vector3] = [Vector3(-12.3, RING_Y, -2.3), Vector3(12.3, RING_Y, -2.3)]
var rng := RandomNumberGenerator.new()
var floor_material: ShaderMaterial
var cell_image: Image
var cell_texture: ImageTexture
var _flicker: _Flicker
var _crowds: Array[CrowdLayer] = []
var _stone := true
var _mat := {}
var _st := {}  # material key -> SurfaceTool (merged into one mesh per material)
var _ao_rects: Array[Vector4] = []
var _ao_params: Array[Vector2] = []
var _tex_cache := {}


## Flickers the brazier and lantern lights.
class _Flicker:
	extends Node
	var lights: Array[OmniLight3D] = []
	var base_energy: Array[float] = []
	var _t := 0.0

	func _process(delta: float) -> void:
		_t += delta
		for i in lights.size():
			var ph := float(i) * 1.913
			var f := 1.0 + 0.07 * sin(_t * 8.7 + ph) + 0.05 * sin(_t * 14.1 + ph * 2.3) + 0.035 * sin(_t * 23.0 + ph * 0.7)
			lights[i].light_energy = base_energy[i] * f


## One sheet's worth of spectators drawn as a single MultiMesh: every member
## plays its own variant's idle (or cheer) loop with its own phase and speed.
class CrowdLayer:
	extends MultiMeshInstance3D
	var sheet: SpriteSheet
	var variants: PackedInt32Array = []
	var phases: PackedFloat32Array = []
	var speeds: PackedFloat32Array = []
	var _frames: PackedInt32Array = []
	# per variant: [idle frames, idle fps, cheer frames, cheer fps]
	var _anims: Dictionary = {}
	var _cheer_left := 0.0
	var _t := 0.0
	var _last_tick := -1

	func setup(p_sheet: SpriteSheet, members: Array, modulate: Color) -> void:
		sheet = p_sheet
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_custom_data = true
		mm.mesh = QuadMesh.new()
		mm.instance_count = members.size()
		variants.resize(members.size())
		phases.resize(members.size())
		speeds.resize(members.size())
		_frames.resize(members.size())
		var lo := Vector3(INF, INF, INF)
		var hi := -lo
		for i in members.size():
			var m: Dictionary = members[i]
			var pos: Vector3 = m["pos"]
			var s: float = m.get("scale", 1.0)
			mm.set_instance_transform(i, Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * s), pos))
			variants[i] = int(m["variant"])
			phases[i] = float(m.get("phase", 0.0))
			speeds[i] = float(m.get("speed", 1.0))
			_frames[i] = -1
			lo = lo.min(pos)
			hi = hi.max(pos)
			if not _anims.has(variants[i]):
				var idle: String = sheet.resolve("idle_v%d" % variants[i], "s")[0]
				var cheer: String = sheet.resolve("cheer_v%d" % variants[i], "s")[0]
				if cheer == "":
					cheer = idle
				_anims[variants[i]] = [sheet.frames_of(idle), sheet.fps_of(idle), sheet.frames_of(cheer), sheet.fps_of(cheer)]
		multimesh = mm
		var mat := ShaderMaterial.new()
		mat.shader = SPRITE_SHADER
		mat.set_shader_parameter("sheet", sheet.texture)
		mat.set_shader_parameter("sheet_size", sheet.texture.get_size())
		mat.set_shader_parameter("frame_size", sheet.frame_size)
		mat.set_shader_parameter("columns", float(sheet.columns))
		mat.set_shader_parameter("pivot", sheet.pivot)
		mat.set_shader_parameter("pixel_size", 1.0 / sheet.pixels_per_unit)
		mat.set_shader_parameter("instance_frame", true)
		mat.set_shader_parameter("modulate", modulate)
		material_override = mat
		cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		custom_aabb = AABB(lo - Vector3(2, 1, 2), hi - lo + Vector3(4, 5, 4))
		_update(true)

	func cheer(seconds: float) -> void:
		_cheer_left = maxf(_cheer_left, seconds)

	func _process(delta: float) -> void:
		_t += delta
		if _cheer_left > 0.0:
			_cheer_left -= delta
		# frames change at most a dozen times a second: no need to look every frame
		var tick := int(_t * 24.0)
		if tick != _last_tick:
			_last_tick = tick
			_update(false)

	func _update(force: bool) -> void:
		if sheet == null or not sheet.valid:
			return
		var k0 := 2 if _cheer_left > 0.0 else 0
		for i in variants.size():
			var a: Array = _anims.get(variants[i], [])
			if a.is_empty():
				continue
			var frames: Array = a[k0]
			if frames.is_empty():
				continue
			var k := int((_t * speeds[i] + phases[i]) * float(a[k0 + 1])) % frames.size()
			var f := int(frames[k])
			if f != _frames[i] or force:
				_frames[i] = f
				multimesh.set_instance_custom_data(i, Color(float(f), 0.0, 0.0, 0.0))


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
	_board(b)
	_steps(b)
	if _stone:
		_back_wall(b)
		_pillars(b)
		_side_braziers(b)
		_banner_poles(b)
		_ring_props(b)
		for c in def.circles:
			_standing_stone(Vector3(c.x, 0, c.y), c.z)
	else:
		_yard_fences(b)
		_yard_lanterns(b)
	_podiums(b)
	if def.crowd:
		_back_stands(b)
		_side_stands(b)
		_front_row(b)
	else:
		_yard_props(b)
		_yard_cottages(b)
	_ground(b)
	_trees(b)
	_weeds(b)
	_atmosphere(b)
	_flush_meshes()
	_depth_of_field(b)
	_tune_lighting(parent)
	return root


# --- Materials ------------------------------------------------------------------------

func _make_materials() -> void:
	_mat["iron"] = _metal(Color(0.11, 0.095, 0.09), 0.4, 0.5)
	var canvas_mat := StandardMaterial3D.new()
	canvas_mat.vertex_color_use_as_albedo = true
	canvas_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	canvas_mat.roughness = 1.0
	canvas_mat.specular_mode = BaseMaterial3D.SPECULAR_DISABLED
	_mat["canvas"] = canvas_mat
	_mat["bronze"] = _metal(Color(0.6, 0.42, 0.18), 0.55, 0.42)
	var hot := StandardMaterial3D.new()
	hot.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	hot.albedo_color = Color(1.0, 0.45, 0.14)
	_mat["coals"] = hot
	_mat["clay"] = _metal(Color(0.62, 0.36, 0.24), 0.0, 0.85)
	if _stone:
		_mat["wall"] = _stone_mat("arena_hd_ashlar", Color(0.95, 0.93, 0.92), "arena_hd_dressed", Color(1.0, 0.99, 0.97))
		_mat["dressed"] = _stone_mat("arena_hd_dressed", Color(0.92, 0.91, 0.9), "arena_hd_dressed", Color(1.0, 0.99, 0.97))
		_mat["step"] = _stone_mat("arena_hd_ashlar", Color(0.82, 0.8, 0.8), "arena_hd_dressed", Color(0.95, 0.93, 0.9))
		_mat["pillar"] = _stone_mat("arena_hd_dressed", Color(0.86, 0.86, 0.9), "arena_hd_dressed", Color(0.95, 0.95, 0.98))
		_mat["dark"] = _stone_mat("arena_hd_ashlar", Color(0.55, 0.53, 0.56), "arena_hd_dressed", Color(0.7, 0.68, 0.7))
		_mat["wood"] = _stone_mat("arena_hd_wood", Color(0.92, 0.9, 0.9), "arena_hd_wood", Color.WHITE)
		_mat["monolith"] = _stone_mat("arena_hd_monolith", Color.WHITE, "arena_hd_monolith", Color(0.95, 1.0, 0.92))
	else:
		_mat["wall"] = _stone_mat("arena_hd_timber", Color(0.95, 0.93, 0.9), "arena_hd_timber", Color.WHITE)
		_mat["dressed"] = _mat["wall"]
		_mat["step"] = _stone_mat("arena_hd_timber", Color(0.8, 0.78, 0.76), "arena_hd_wood", Color(0.95, 0.93, 0.9))
		_mat["pillar"] = _stone_mat("arena_hd_timber", Color(0.78, 0.76, 0.74), "arena_hd_timber", Color.WHITE)
		_mat["dark"] = _stone_mat("arena_hd_timber", Color(0.6, 0.58, 0.56), "arena_hd_timber", Color(0.7, 0.68, 0.66))
		_mat["wood"] = _stone_mat("arena_hd_wood", Color(0.92, 0.9, 0.9), "arena_hd_wood", Color.WHITE)
		_mat["monolith"] = _stone_mat("arena_hd_dressed", Color.WHITE, "", Color.WHITE)
		_mat["plaster"] = _stone_mat_lo("plaster_timber", Color(0.95, 0.93, 0.9))
		_mat["roof"] = _stone_mat_lo("thatch_roof", Color(0.95, 0.92, 0.88))


## Triplanar arena material at 48 texels per unit (`top` textures upward faces).
func _stone_mat(tex_name: String, tint: Color, top: String, top_tint: Color) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = STONE_SHADER
	var t := _hd_tex(tex_name)
	m.set_shader_parameter("tex", t)
	m.set_shader_parameter("tex_size", t.get_size())
	m.set_shader_parameter("tint", tint)
	if top != "":
		var tt := _hd_tex(top)
		m.set_shader_parameter("use_top_tex", true)
		m.set_shader_parameter("top_tex", tt)
		m.set_shader_parameter("top_tex_size", tt.get_size())
		m.set_shader_parameter("top_tint", top_tint)
	return m


## The same material for the 24-texel env_forge textures (distant pieces).
func _stone_mat_lo(tex_name: String, tint: Color) -> ShaderMaterial:
	var m := _stone_mat(tex_name, tint, "", Color.WHITE)
	m.set_shader_parameter("texels_per_unit", 24.0)
	return m


## A texture with mipmaps built at load (pixel-art textures import without
## them; the perspective view needs them for distant, minified surfaces).
func _hd_tex(tex_name: String) -> Texture2D:
	if _tex_cache.has(tex_name):
		return _tex_cache[tex_name]
	var base := EnvKit.tex(tex_name)
	var img := base.get_image()
	var t: Texture2D = base
	if img != null:
		img = img.duplicate()
		if img.is_compressed():
			img.decompress()
		img.convert(Image.FORMAT_RGBA8)
		img.generate_mipmaps()
		t = ImageTexture.create_from_image(img)
	_tex_cache[tex_name] = t
	return t


func _surface(key: String) -> SurfaceTool:
	if not _st.has(key):
		_st[key] = ArenaMesh.begin()
	return _st[key]


## One mesh (one draw call) per material for every piece written so far.
func _flush_meshes() -> void:
	for key: String in _st.keys():
		var st: SurfaceTool = _st[key]
		var mi := MeshInstance3D.new()
		mi.name = "Merged_" + key
		mi.mesh = st.commit()
		mi.material_override = _mat[key]
		if key == "coals":
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(mi)
	_st.clear()


## A contact shadow on the lower ground round this footprint (x0, z0, x1, z1).
func _ground_ao(r: Rect2, strength: float, reach: float) -> void:
	if _ao_rects.size() >= 16:
		return
	_ao_rects.append(Vector4(r.position.x, r.position.y, r.end.x, r.end.y))
	_ao_params.append(Vector2(strength, reach))


# --- The board: flagstones (or earth pads), rim and mortar in one mesh ----------------

func _atlas(cell: Vector2) -> Vector2:
	return cell * ATLAS_CELL + Vector2.ONE * ATLAS_GUTTER


func _board(b: Rect2) -> void:
	var st := ArenaMesh.begin()
	var n := def.cell_count()
	_build_cells(b)
	var stone_cells := {}
	for c in def.circles:
		stone_cells[def.cell_of(Vector2(c.x, c.y))] = true
	for y in n.y:
		for x in n.x:
			var cell := Vector2i(x, y)
			if _stone:
				_flagstone(st, b, cell, n, stone_cells.has(cell))
			else:
				_earth_pad(st, b, cell, n)
	if not _stone:
		_laths(st, b)
	_rim(st, b)
	_mortar(st, b)
	var mi := MeshInstance3D.new()
	mi.name = "Board"
	mi.mesh = st.commit()
	# the board only receives shadows: casting would just self-shadow it (acne)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	floor_material = _floor_material(b)
	mi.material_override = floor_material
	root.add_child(mi)


func _floor_material(b: Rect2) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = FLOOR_SHADER
	var atlas := _hd_tex("arena_hd_floor" if _stone else "arena_hd_yard")
	m.set_shader_parameter("atlas", atlas)
	m.set_shader_parameter("atlas_size", atlas.get_size())
	m.set_shader_parameter("cells", cell_texture)
	m.set_shader_parameter("board_rect", Vector4(b.position.x, b.position.y, b.size.x, b.size.y))
	m.set_shader_parameter("texels", TEXELS)
	m.set_shader_parameter("mortar_y", MORTAR_Y)
	var dec := EnvKit.tex("arena_hd_decals")
	m.set_shader_parameter("decals", dec)
	m.set_shader_parameter("decals_size", dec.get_size())
	m.set_shader_parameter("cloud_shadow", 0.0 if Settings.graphics_low else 0.4)
	m.set_shader_parameter("glints", 0.003 if _stone else 0.0)
	if _stone:
		var e := _hd_tex("arena_hd_emblem")
		m.set_shader_parameter("emblem", e)
		m.set_shader_parameter("emblem_size", e.get_size())
		var es := e.get_size() / TEXELS
		var c := b.get_center()
		m.set_shader_parameter("emblem_rect", Vector4(c.x - es.x * 0.5, c.y - es.y * 0.5, es.x, es.y))
		m.set_shader_parameter("wall_ao", Vector4(0.42, 0.0, 0.12, 0.12))
		m.set_shader_parameter("tint", Color(0.96, 0.93, 0.89))
	else:
		m.set_shader_parameter("wall_ao", Vector4(0.25, 0.0, 0.12, 0.12))
		m.set_shader_parameter("tint", Color(0.97, 0.94, 0.9))
	var stones: Array[Vector4] = []
	for c in def.circles:
		stones.append(Vector4(c.x, c.y, c.z, 0.45))
	while stones.size() < 6:
		stones.append(Vector4.ZERO)
	m.set_shader_parameter("stones", stones)
	m.set_shader_parameter("stone_count", mini(def.circles.size(), 6))
	return m


## Per-cell data for the floor shader: scorch decals and highlights.
func _build_cells(b: Rect2) -> void:
	var n := def.cell_count()
	cell_image = Image.create(n.x, n.y, false, Image.FORMAT_RGBA8)
	cell_image.fill(Color(0, 0, 0, 0))
	var stone_cells := {}
	for c in def.circles:
		stone_cells[def.cell_of(Vector2(c.x, c.y))] = true
	var spawn_cells := [def.cell_of(def.spawn_team0), def.cell_of(def.spawn_team1)]
	var placed := 0
	var tries := 0
	var used: Array[Vector2i] = []
	var want := 6 if _stone else 3
	var drng := RandomNumberGenerator.new()
	drng.seed = 99
	while placed < want and tries < 300:
		tries += 1
		var cell := Vector2i(drng.randi_range(1, n.x - 2), drng.randi_range(1, n.y - 2))
		if stone_cells.has(cell) or spawn_cells.has(cell) or def.cell_center(cell).distance_to(b.get_center()) < 3.2:
			continue
		var near := false
		for u in used:
			if absi(u.x - cell.x) + absi(u.y - cell.y) < 4:
				near = true
		if near:
			continue
		used.append(cell)
		var g := (placed % 4 + 1) | (drng.randi_range(0, 3) << 3)
		cell_image.set_pixelv(cell, Color8(0, g, 0, 0))
		placed += 1
	cell_texture = ImageTexture.create_from_image(cell_image)


## Light up cells on the floor (e.g. for move previews): strength 0..1, 0 clears.
func set_cell_highlight(cell: Vector2i, strength: float) -> void:
	if cell_image == null or not def.has_cell(cell):
		return
	var px := cell_image.get_pixelv(cell)
	cell_image.set_pixelv(cell, Color8(px.r8, px.g8, px.b8, int(clampf(strength, 0.0, 1.0) * 255.0)))
	cell_texture.update(cell_image)


## Which atlas face a cell gets: the chessboard tone, polished wear toward
## the middle, moss and blown sand along the walls, a socket under a stone.
func _pick_face(cell: Vector2i, n: Vector2i, is_stone: bool) -> Vector2:
	var tone := (cell.x + cell.y) % 2
	if is_stone and _stone:
		return Vector2(SPECIAL_PLINTH + tone, ROW_SPECIAL)
	var centre := (Vector2(cell) + Vector2(0.5, 0.5)) - Vector2(n) * 0.5
	var d := Vector2(centre.x / (n.x * 0.5), centre.y / (n.y * 0.5)).length()
	var at_back := cell.y == 0
	var at_side := cell.x == 0 or cell.x == n.x - 1
	if (at_back or at_side) and rng.randf() < (0.45 if at_back else 0.3):
		var kind := 0 if (at_back or not _stone) else 2  # moss by the back wall, sand at the sides
		return Vector2(SPECIAL_EDGE + kind + tone, ROW_SPECIAL)
	if d < 0.55 and rng.randf() < 0.85 - d:
		return Vector2(tone * 4 + rng.randi_range(0, 3), ROW_WORN)
	var weights := [0.16, 0.1, 0.07, 0.05, 0.06, 0.04, 0.03, 0.03, 0.12, 0.05, 0.1, 0.05, 0.04, 0.06, 0.02, 0.02]
	var r := rng.randf()
	var k := 0
	while k < weights.size() - 1 and r > weights[k]:
		r -= weights[k]
		k += 1
	var row := (ROW_A if tone == 0 else ROW_B) + k / 8
	return Vector2(k % 8, row)


func _flagstone(st: SurfaceTool, b: Rect2, cell: Vector2i, n: Vector2i, is_stone: bool) -> void:
	var x0 := b.position.x + cell.x
	var z0 := b.position.y + cell.y
	var face := _pick_face(cell, n, is_stone)
	var worn := face.y == ROW_WORN
	# corner chamfers: rounded a touch, now and then a chipped corner
	var ch := Vector4.ONE * 0.012
	if rng.randf() < 0.16:
		var k := rng.randi_range(0, 3)
		ch[k] = rng.randf_range(0.05, 0.1)
	var poly := ArenaMesh.chamfered_rect(x0 + JOINT, z0 + JOINT, x0 + 1.0 - JOINT, z0 + 1.0 - JOINT, ch)
	var top := rng.randf_range(-0.006, TILE_TOP_MAX)
	if worn:
		top -= rng.randf_range(0.002, 0.007)
	var tilt := Vector2(rng.randf_range(-0.005, 0.005), rng.randf_range(-0.005, 0.005))
	# keep every corner inside the allowed band
	var reach := (absf(tilt.x) + absf(tilt.y)) * 0.5
	top = clampf(top, TILE_TOP_MIN + reach, TILE_TOP_MAX - reach)
	var jitter := 1.0 + rng.randf_range(-0.065, 0.065)
	var warm := rng.randf_range(-0.025, 0.025)
	var col := Color(jitter + warm, jitter, jitter - warm, 1.0)
	var origin := _atlas(face)
	var uv := func(v: Vector3) -> Vector2:
		return origin + Vector2(v.x - x0, v.z - z0) * TEXELS
	ArenaMesh.prism(st, poly, MORTAR_Y, top, BEVEL + rng.randf_range(-0.006, 0.008), col, Vector2(-100, 0), uv, tilt)


## Yard: a packed-earth pad inside each cell (the laths frame it).
func _earth_pad(st: SurfaceTool, b: Rect2, cell: Vector2i, n: Vector2i) -> void:
	var x0 := b.position.x + cell.x
	var z0 := b.position.y + cell.y
	var face := _pick_face(cell, n, false)
	var lath := 0.05
	var poly := ArenaMesh.chamfered_rect(x0 + lath, z0 + lath, x0 + 1.0 - lath, z0 + 1.0 - lath, Vector4.ONE * 0.02)
	var top := rng.randf_range(-0.012, -0.006)
	var jitter := 1.0 + rng.randf_range(-0.05, 0.05)
	var col := Color(jitter, jitter, jitter, 1.0)
	var origin := _atlas(face)
	var uv := func(v: Vector3) -> Vector2:
		return origin + Vector2(v.x - x0, v.z - z0) * TEXELS
	ArenaMesh.prism(st, poly, MORTAR_Y, top, 0.03, col, Vector2(-100, 0), uv)


## Yard: flush timber laths on every cell line (the grid you dash along):
## one board per cell edge, nailed to a square cap at every crossing.
func _laths(st: SurfaceTool, b: Rect2) -> void:
	var w := 0.05
	var n := def.cell_count()
	var span := 1.0 - 2.0 * w
	for j in n.y + 1:
		var z := b.position.y + j
		for i in n.x:
			var x0 := b.position.x + i + w
			var origin := _atlas(Vector2((i + j) % 4, ROW_RIM))
			var uvh := func(v: Vector3) -> Vector2:
				return origin + Vector2((v.x - x0) / span * TEXELS, (v.z - z + w) * TEXELS + 9.6)
			ArenaMesh.prism(st, ArenaMesh.chamfered_rect(x0, z - w, x0 + span, z + w), MORTAR_Y, 0.002, 0.012, _lath_tint(), Vector2(-100, 0), uvh)
	for i in n.x + 1:
		var x := b.position.x + i
		for j in n.y:
			var z0 := b.position.y + j + w
			var origin2 := _atlas(Vector2(4 + (i * 3 + j) % 4, ROW_RIM))
			var uvv := func(v: Vector3) -> Vector2:
				return origin2 + Vector2((v.x - x + w) * TEXELS + 9.6, (v.z - z0) / span * TEXELS)
			ArenaMesh.prism(st, ArenaMesh.chamfered_rect(x - w, z0, x + w, z0 + span), MORTAR_Y, 0.001, 0.012, _lath_tint(), Vector2(-100, 0), uvv)
	var cap := _atlas(Vector2(0, ROW_RIM2))
	for j in n.y + 1:
		for i in n.x + 1:
			var x := b.position.x + i
			var z := b.position.y + j
			var uvc := func(v: Vector3) -> Vector2:
				return cap + Vector2(v.x - x + w, v.z - z + w) * TEXELS + Vector2(7.2, 7.2)
			ArenaMesh.prism(st, ArenaMesh.chamfered_rect(x - w, z - w, x + w, z + w), MORTAR_Y, 0.0025, 0.01, _lath_tint(), Vector2(-100, 0), uvc)


func _lath_tint() -> Color:
	var j := rng.randf_range(0.88, 1.0)
	return Color(j, j * 0.98, j * 0.96, 0.6)


## The flush rim: one slab per column / row (joints on the cell lines) and
## corner blocks; its outer faces are the first riser of the steps.
func _rim(st: SurfaceTool, b: Rect2) -> void:
	var n := def.cell_count()
	var y0 := -STEP_RISE
	var top := -0.002
	var col := Color(1, 1, 1, 0.6)
	for i in n.x:
		var x0 := b.position.x + i
		for side in 2:
			var z0 := b.position.y - RIM if side == 0 else b.end.y
			var origin := _atlas(Vector2(rng.randi_range(0, 3), ROW_RIM))
			var uv := func(v: Vector3) -> Vector2:
				return origin + Vector2(v.x - x0, v.z - z0) * TEXELS
			var poly := ArenaMesh.chamfered_rect(x0 + JOINT, z0 + JOINT, x0 + 1.0 - JOINT, z0 + RIM - JOINT, Vector4.ONE * 0.01)
			ArenaMesh.prism(st, poly, y0, top + rng.randf_range(-0.004, 0.0), 0.03, _rim_tint(col), Vector2(-100, 0), uv)
	for j in n.y:
		var z0 := b.position.y + j
		for side in 2:
			var x0 := b.position.x - RIM if side == 0 else b.end.x
			var origin := _atlas(Vector2(4 + rng.randi_range(0, 3), ROW_RIM))
			var uv := func(v: Vector3) -> Vector2:
				return origin + Vector2(v.x - x0, v.z - z0) * TEXELS
			var poly := ArenaMesh.chamfered_rect(x0 + JOINT, z0 + JOINT, x0 + RIM - JOINT, z0 + 1.0 - JOINT, Vector4.ONE * 0.01)
			ArenaMesh.prism(st, poly, y0, top + rng.randf_range(-0.004, 0.0), 0.03, _rim_tint(col), Vector2(-100, 0), uv)
	for corner in 4:
		var x0 := b.position.x - RIM if corner % 2 == 0 else b.end.x
		var z0 := b.position.y - RIM if corner < 2 else b.end.y
		var origin := _atlas(Vector2(corner % 2, ROW_RIM2))
		var uv := func(v: Vector3) -> Vector2:
			return origin + Vector2(v.x - x0, v.z - z0) * TEXELS
		var poly := ArenaMesh.chamfered_rect(x0 + JOINT, z0 + JOINT, x0 + RIM - JOINT, z0 + RIM - JOINT, Vector4.ONE * 0.02)
		ArenaMesh.prism(st, poly, y0, top, 0.03, col, Vector2(-100, 0), uv)


func _rim_tint(base: Color) -> Color:
	var j := 1.0 + rng.randf_range(-0.04, 0.04)
	return Color(base.r * j, base.g * j, base.b * j, base.a)


## The mortar bed under the joints: one quad per cell (so its texture repeats).
func _mortar(st: SurfaceTool, b: Rect2) -> void:
	var origin := _atlas(MORTAR_CELL)
	var col := Color(0.82, 0.8, 0.78, 0.3)
	var r := b.grow(RIM)
	var x := r.position.x
	while x < r.end.x - 0.001:
		var z := r.position.y
		var w := minf(1.0, r.end.x - x)
		while z < r.end.y - 0.001:
			var d := minf(1.0, r.end.y - z)
			var cx := x
			var cz := z
			var uv := func(v: Vector3) -> Vector2:
				return origin + Vector2(v.x - cx, v.z - cz) * TEXELS
			ArenaMesh.flat(st, Rect2(x, z, w, d), MORTAR_Y, col, Vector2(-100, 0), uv)
			z += d
		x += w


# --- Dais steps, back wall, pillars ----------------------------------------------------

## Steps down from the rim to the lower ring at the front and both sides
## (and behind, for the yard's deck). The flights meet edge to edge, never
## overlapping, so their treads can't fight.
func _steps(b: Rect2) -> void:
	var st := _surface("step")
	var x_in := b.size.x * 0.5 + RIM
	var cx := b.get_center().x
	var z_front := b.end.y + RIM
	var z_back := b.position.y - RIM
	var tuck := 0.05
	for k in range(1, STEPS):
		var top := -STEP_RISE * k
		var run := STEP_RUN * k
		var ao := Vector2(-STEP_RISE * (k + 1), 0.42)
		# front flight (it owns the corners)
		ArenaMesh.prism(st, ArenaMesh.chamfered_rect(cx - x_in - run, z_front - tuck, cx + x_in + run, z_front + run), RING_Y, top, 0.022, _jit(0.03), ao)
		var zs0 := z_back - BACK_WALL_T
		if not _stone:
			# the yard deck has no back wall: a flight behind too
			ArenaMesh.prism(st, ArenaMesh.chamfered_rect(cx - x_in - run, z_back - run, cx + x_in + run, z_back + tuck), RING_Y, top, 0.022, _jit(0.03), ao)
			zs0 = z_back + tuck
		for s: float in [-1.0, 1.0]:
			var x0 := (cx + x_in - 0.2) if s > 0.0 else (cx - x_in - run)
			var x1 := (cx + x_in + run) if s > 0.0 else (cx - x_in + 0.2)
			ArenaMesh.prism(st, ArenaMesh.chamfered_rect(x0, zs0, x1, z_front - tuck), RING_Y, top, 0.022, _jit(0.03), ao)
	var run_max := STEP_RUN * (STEPS - 1)
	var zb := z_back - (BACK_WALL_T if _stone else run_max)
	_ground_ao(Rect2(cx - x_in - run_max, zb, (x_in + run_max) * 2.0, z_front + run_max - zb), 0.38, 0.55)


func _jit(amount: float) -> Color:
	var j := 1.0 + rng.randf_range(-amount, amount)
	return Color(j, j, j, 1.0)


## The carved back wall: ashlar with a coping, pilasters, banners and torches.
func _back_wall(b: Rect2) -> void:
	var cx := b.get_center().x
	var x_half := b.size.x * 0.5 + RIM + STEP_RUN * (STEPS - 1) + 0.35
	var z1 := b.position.y - RIM
	var z0 := z1 - BACK_WALL_T
	var st := _surface("wall")
	var ao := Vector2(0.0, 0.45)
	ArenaMesh.prism(st, ArenaMesh.chamfered_rect(cx - x_half, z0, cx + x_half, z1), RING_Y, BACK_WALL_H, 0.0, Color.WHITE, ao)
	var dressed := _surface("dressed")
	ArenaMesh.prism(dressed, ArenaMesh.chamfered_rect(cx - x_half - 0.06, z0 - 0.06, cx + x_half + 0.06, z1 + 0.07), BACK_WALL_H, BACK_WALL_H + 0.12, 0.03)
	# a moulded base course where the wall meets the rim
	ArenaMesh.prism(_surface("dark"), ArenaMesh.chamfered_rect(cx - x_half, z1 - 0.02, cx + x_half, z1 + 0.035), -0.02, 0.1, 0.02, Color.WHITE, Vector2(0.0, 0.5))
	# pilasters every four columns, each with a capital
	var xs: Array[float] = []
	var x := b.position.x
	while x <= b.end.x + 0.01:
		xs.append(x)
		x += 4.0
	for px in xs:
		ArenaMesh.prism(st, ArenaMesh.chamfered_rect(cx + px - 0.2, z1 - 0.02, cx + px + 0.2, z1 + 0.1, Vector4.ONE * 0.03), -0.02, BACK_WALL_H, 0.0, _jit(0.03), ao)
		ArenaMesh.prism(dressed, ArenaMesh.chamfered_rect(cx + px - 0.26, z1 - 0.02, cx + px + 0.26, z1 + 0.15), BACK_WALL_H - 0.12, BACK_WALL_H, 0.02)
	# banners between the pilasters: teal (team 0) on the left, red (team 1)
	# on the right, the arena's own gold one in the middle
	var slots := [-8.0, -4.0, 0.0, 4.0, 8.0]
	for i in slots.size():
		var bx: float = cx + slots[i]
		var design := 0 if slots[i] < -1.0 else (1 if slots[i] > 1.0 else 2)
		_banner(design, Vector3(bx, BACK_WALL_H + 0.02, z1 + 0.05), Vector2(0.64, 1.0), float(i) * 1.7)
	# wall torches on the two inner pilasters
	for px in xs:
		if absf(px) > 0.1 and absf(px) < 5.0:
			_torch(Vector3(cx + px, 0.78, z1 + 0.2), not Settings.graphics_low)
	_ground_ao(Rect2(cx - x_half, z0, x_half * 2.0, BACK_WALL_T), 0.4, 0.7)


## A cloth banner hanging from its rod at `top`: 0 teal, 1 red, 2 gold
## (painted with tools/art_forge, see its provenance records).
func _banner(design: int, top: Vector3, size: Vector2, seed: float) -> MeshInstance3D:
	var tex := _hd_tex(BANNERS[clampi(design, 0, BANNERS.size() - 1)])
	var mi := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = size
	q.center_offset = Vector3(0, -size.y * 0.5, 0)
	q.subdivide_depth = 6
	mi.mesh = q
	var m := ShaderMaterial.new()
	m.shader = CLOTH_SHADER
	m.set_shader_parameter("atlas", tex)
	m.set_shader_parameter("atlas_size", tex.get_size())
	m.set_shader_parameter("region", Vector4(0.0, 0.0, tex.get_width(), tex.get_height()))
	m.set_shader_parameter("seed", seed)
	m.set_shader_parameter("sway", 0.035)
	mi.material_override = m
	mi.position = top
	root.add_child(mi)
	return mi


## A small iron sconce with a flame on the wall (lights the back rows).
func _torch(pos: Vector3, with_light: bool) -> void:
	var iron := _surface("iron")
	ArenaMesh.cylinder(iron, pos + Vector3(0, -0.06, 0), 0.05, 0.09, 0.12, 8)
	ArenaMesh.strut(iron, pos + Vector3(0, -0.04, -0.18), pos + Vector3(0, -0.02, 0), 0.018, 0.018, 4)
	ArenaMesh.cylinder(_surface("coals"), pos + Vector3(0, 0.055, 0), 0.075, 0.075, 0.01, 8)
	_fire(pos + Vector3(0, 0.05, 0.02), Vector2(0.3, 0.46), 32.0)
	_glow(pos + Vector3(0, 0.28, 0.05), 1.3, Color(1.0, 0.6, 0.28), 0.3)
	if with_light:
		_light(pos + Vector3(0, 0.35, 0.4), Color(1.0, 0.6, 0.3), 2.4, 5.4)


## Corner pillars with braziers: tall ones at the back, shorter at the front.
func _pillars(b: Rect2) -> void:
	var cx := b.get_center().x
	var x_out := b.size.x * 0.5 + RIM + STEP_RUN * (STEPS - 1) + 0.5
	var low := Settings.graphics_low
	for sz: float in [-1.0, 1.0]:
		for sx: float in [-1.0, 1.0]:
			var back := sz < 0.0
			var px := cx + sx * (x_out + (0.1 if back else 0.0))
			var pz := (b.position.y - RIM - BACK_WALL_T * 0.5) if back else (b.end.y + RIM + STEP_RUN * (STEPS - 1) + 0.35)
			var h := 2.25 if back else 1.45
			var base := Vector3(px, RING_Y, pz)
			_pillar(base, h)
			# every brazier carries a light on high; on low only the front pair (they
			# light the most board) and the back pair are kept, without embers
			_brazier(Vector3(px, h + 0.16, pz), true, not low)
			_ground_ao(Rect2(px - 0.5, pz - 0.5, 1.0, 1.0), 0.45, 0.6)


func _pillar(base: Vector3, top_y: float) -> void:
	var st := _surface("pillar")
	var dressed := _surface("dressed")
	var c := Vector2(base.x, base.z)
	var ao := Vector2(base.y, 0.45)
	ArenaMesh.prism(dressed, _square(c, 0.44, 0.04), base.y, base.y + 0.26, 0.035, _jit(0.03), ao)
	ArenaMesh.prism(st, _square(c, 0.34, 0.06), base.y + 0.26, top_y - 0.16, 0.0, _jit(0.02), Vector2(base.y + 0.26, 0.3))
	# a carved band two thirds of the way up
	var band_y := lerpf(base.y + 0.26, top_y - 0.16, 0.66)
	ArenaMesh.prism(dressed, _square(c, 0.37, 0.05), band_y, band_y + 0.08, 0.02)
	ArenaMesh.prism(dressed, _square(c, 0.42, 0.05), top_y - 0.16, top_y, 0.03, _jit(0.02))


static func _square(c: Vector2, half: float, chamfer: float) -> PackedVector2Array:
	return ArenaMesh.chamfered_rect(c.x - half, c.y - half, c.x + half, c.y + half, Vector4.ONE * chamfer)


## Tall banner poles on the side rings. With the sun low in the west their
## poles and pennants lay long, soft shadows across the board's left side.
func _banner_poles(b: Rect2) -> void:
	var cx := b.get_center().x
	var x_out := b.size.x * 0.5 + RIM + STEP_RUN * (STEPS - 1) + 1.4
	var iron := _surface("iron")
	var wood := _surface("pillar")
	var i := 0
	for sx: float in [-1.0, 1.0]:
		for z: float in [-1.4, 4.4]:
			var p := Vector3(cx + sx * x_out, RING_Y, b.get_center().y + z)
			var top := RING_Y + 3.7
			ArenaMesh.prism(wood, _square(Vector2(p.x, p.z), 0.16, 0.03), RING_Y, RING_Y + 0.3, 0.02, _jit(0.03), Vector2(RING_Y, 0.4))
			ArenaMesh.strut(iron, p + Vector3(0, 0.3, 0), Vector3(p.x, top, p.z), 0.05, 0.04, 6)
			ArenaMesh.cylinder(_surface("bronze"), Vector3(p.x, top, p.z), 0.07, 0.0, 0.16, 6)
			# a crossbar toward the board, the pennant hanging from it
			var arm := Vector3(p.x - sx * 0.85, top - 0.22, p.z)
			ArenaMesh.strut(iron, Vector3(p.x, top - 0.22, p.z), arm, 0.025, 0.025, 4)
			_banner(0 if sx < 0.0 else 1, Vector3(p.x - sx * 0.45, top - 0.2, p.z + 0.03), Vector2(0.72, 1.12), 3.0 + float(i) * 2.3).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
			_ground_ao(Rect2(p.x - 0.3, p.z - 0.3, 0.6, 0.6), 0.3, 0.35)
			i += 1


## Small things on the side rings, where the frame shows them beside the
## board's back half: bronze-banded urns, a weapon rack, a water barrel.
func _ring_props(b: Rect2) -> void:
	var cx := b.get_center().x
	var x_ring := b.size.x * 0.5 + RIM + STEP_RUN * (STEPS - 1)
	for sx: float in [-1.0, 1.0]:
		# a pair of urns between the corner pillar and the podium
		for k in 2:
			var p := Vector3(cx + sx * (x_ring + 0.45 + k * 0.5), RING_Y, b.position.y - 0.05 + k * 0.32)
			_urn(p, 0.85 + 0.15 * k)
		# a weapon rack with staves, in front of the podium
		var rack := Vector3(cx + sx * (x_ring + 1.0), RING_Y, b.position.y + 3.35)
		var wood := _surface("pillar")
		for dz: float in [-0.42, 0.42]:
			ArenaMesh.prism(wood, _square(Vector2(rack.x, rack.z + dz), 0.04, 0.01), RING_Y, RING_Y + 0.9, 0.01, _jit(0.04))
		ArenaMesh.prism(wood, ArenaMesh.chamfered_rect(rack.x - 0.035, rack.z - 0.46, rack.x + 0.035, rack.z + 0.46), RING_Y + 0.7, RING_Y + 0.76, 0.01)
		ArenaMesh.prism(wood, ArenaMesh.chamfered_rect(rack.x - 0.035, rack.z - 0.46, rack.x + 0.035, rack.z + 0.46), RING_Y + 0.14, RING_Y + 0.2, 0.01)
		for i in 4:
			var z := rack.z - 0.3 + i * 0.2
			var lean := sx * 0.12
			ArenaMesh.strut(_surface("iron" if i == 2 else "pillar"), Vector3(rack.x + lean * 0.2, RING_Y + 0.05, z), Vector3(rack.x - lean, RING_Y + 1.05 + 0.05 * (i % 2), z), 0.022, 0.018, 4)
		_ground_ao(Rect2(rack.x - 0.15, rack.z - 0.5, 0.3, 1.0), 0.25, 0.3)
		EnvKit.prop(root, "barrel", Vector3(cx + sx * (x_ring + 0.55), RING_Y, b.position.y + 6.25), 1.0, true)


## A bronze-banded clay urn (merged into the arena's meshes).
func _urn(p: Vector3, s: float) -> void:
	var clay := _surface("clay")
	ArenaMesh.cylinder(clay, p, 0.12 * s, 0.2 * s, 0.14 * s, 10, Color.WHITE, Vector2(p.y, 0.3))
	ArenaMesh.cylinder(clay, p + Vector3(0, 0.14 * s, 0), 0.2 * s, 0.17 * s, 0.2 * s, 10, Color.WHITE, Vector2(p.y, 0.3))
	ArenaMesh.cylinder(clay, p + Vector3(0, 0.34 * s, 0), 0.17 * s, 0.09 * s, 0.1 * s, 10, Color.WHITE, Vector2(p.y, 0.3))
	ArenaMesh.cylinder(clay, p + Vector3(0, 0.44 * s, 0), 0.09 * s, 0.11 * s, 0.06 * s, 10)
	ArenaMesh.cylinder(_surface("bronze"), p + Vector3(0, 0.2 * s, 0), 0.205 * s, 0.2 * s, 0.04 * s, 10, Color.WHITE, Vector2(-100, 0), false)
	_ground_ao(Rect2(p.x - 0.22 * s, p.z - 0.22 * s, 0.44 * s, 0.44 * s), 0.3, 0.25)


## Tripod braziers on the side rings: warm light reaching the outer columns.
func _side_braziers(b: Rect2) -> void:
	var cx := b.get_center().x
	var x_out := b.size.x * 0.5 + RIM + STEP_RUN * (STEPS - 1) + 0.75
	var iron := _surface("iron")
	for sx: float in [-1.0, 1.0]:
		var p := Vector3(cx + sx * x_out, RING_Y, b.get_center().y + 1.6)
		for i in 3:
			var a := TAU * float(i) / 3.0 + 0.4
			var foot := p + Vector3(cos(a) * 0.32, 0.0, sin(a) * 0.32)
			var head := p + Vector3(cos(a) * 0.1, 1.12, sin(a) * 0.1)
			ArenaMesh.strut(iron, foot, head, 0.035, 0.025, 5)
		ArenaMesh.cylinder(iron, p + Vector3(0, 0.45, 0), 0.2, 0.2, 0.03, 8)
		_ground_ao(Rect2(p.x - 0.35, p.z - 0.35, 0.7, 0.7), 0.3, 0.4)
		_brazier(p + Vector3(0, 1.1, 0), not Settings.graphics_low, not Settings.graphics_low, 0.8)


func _brazier(top: Vector3, with_light: bool, embers: bool, scale: float = 1.0) -> void:
	_brazier_bowl(top, scale)
	_fire(top + Vector3(0, 0.14 * scale, 0), Vector2(0.7, 1.02) * scale, 32.0)
	_glow(top + Vector3(0, 0.62 * scale, 0), 2.6 * scale, Color(1.0, 0.55, 0.22), 0.32)
	if with_light:
		_light(top + Vector3(0, 0.65 * scale, 0), Color(1.0, 0.55, 0.25), 4.4 * scale, 9.5 * scale)
	if embers:
		_embers(top + Vector3(0, 0.45 * scale, 0))


## Iron bowl with a bronze lip and a bed of glowing coals (merged meshes).
func _brazier_bowl(top: Vector3, scale: float = 1.0) -> void:
	ArenaMesh.cylinder(_surface("iron"), top, 0.16 * scale, 0.32 * scale, 0.22 * scale, 12, Color.WHITE, Vector2(-100, 0), false)
	ArenaMesh.cylinder(_surface("iron"), top + Vector3(0, -0.06 * scale, 0), 0.1 * scale, 0.16 * scale, 0.06 * scale, 12)
	var bronze := _surface("bronze")
	ArenaMesh.cylinder(bronze, top + Vector3(0, 0.2 * scale, 0), 0.33 * scale, 0.35 * scale, 0.05 * scale, 12, Color.WHITE, Vector2(-100, 0), true)
	ArenaMesh.cylinder(_surface("coals"), top + Vector3(0, 0.205 * scale, 0), 0.29 * scale, 0.29 * scale, 0.05 * scale, 12)


func _fire(pos: Vector3, size: Vector2, texels: float = 24.0) -> MeshInstance3D:
	var fire := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = size
	q.center_offset = Vector3(0, size.y * 0.5, 0)
	fire.mesh = q
	var fm := ShaderMaterial.new()
	fm.shader = FIRE_SHADER
	fm.set_shader_parameter("quad_size", size)
	fm.set_shader_parameter("texels", texels)
	fm.set_shader_parameter("seed", rng.randf() * 10.0)
	fm.set_shader_parameter("intensity", 2.4)
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
	light.omni_attenuation = 1.35
	light.shadow_enabled = false
	light.light_specular = 0.0
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
	p.amount = 12
	p.lifetime = 1.8
	p.preprocess = 1.8
	p.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	p.emission_sphere_radius = 0.16
	p.direction = Vector3(0, 1, 0)
	p.spread = 25.0
	p.initial_velocity_min = 0.5
	p.initial_velocity_max = 1.1
	p.gravity = Vector3(0.2, 0.25, 0)
	p.damping_min = 0.3
	p.damping_max = 0.6
	p.mesh = _speck_mesh(2.4)
	var g := Gradient.new()
	g.set_color(0, Color(2.2, 1.5, 0.6, 1.0))
	g.add_point(0.5, Color(1.6, 0.6, 0.16, 0.9))
	g.set_color(g.get_point_count() - 1, Color(0.6, 0.15, 0.05, 0.0))
	p.color_ramp = g
	p.position = pos
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(p)


# --- Standing stones --------------------------------------------------------------------

## A carved menhir on its cell with a bronze ring (the Ringstones), using the
## simulation's obstacle radius for its footprint.
func _standing_stone(pos: Vector3, radius: float) -> void:
	var h := 1.05
	_menhir(_surface("monolith"), pos + Vector3(0, -0.01, 0), radius * 0.94, radius * 0.66, h, rng.randf() * TAU)
	ArenaMesh.cylinder(_surface("bronze"), pos + Vector3(0, h * 0.53, 0), radius * 0.84, radius * 0.8, 0.07, 14)


## A weathered, slightly irregular menhir: a tapering seven-sided prism with
## a sloped, chamfered top (flat-shaded so the faces read under the sun).
static func _menhir(st: SurfaceTool, pos: Vector3, r0: float, r1: float, h: float, yaw: float) -> void:
	var sides := 7
	var jitter := [1.0, 0.86, 1.08, 0.93, 1.04, 0.9, 0.97]
	var lift := [0.1, 0.02, -0.07, -0.04, 0.05, 0.12, 0.03]
	var rings: Array = [[], [], []]
	for i in sides:
		var a := TAU * float(i) / sides + yaw
		var j: float = jitter[i]
		var d := Vector3(cos(a), 0.0, sin(a))
		rings[0].append(pos + d * r0 * j)
		rings[1].append(pos + d * r1 * j + Vector3(0.0, h * 0.8 + float(lift[i]) * 0.4, 0.0))
		rings[2].append(pos + d * r1 * j * 0.7 + Vector3(0.0, h + float(lift[i]), 0.0))
	var ao := Vector2(pos.y, 0.4)
	for k in 2:
		var lo: Array = rings[k]
		var hi: Array = rings[k + 1]
		for i in sides:
			var j2 := (i + 1) % sides
			ArenaMesh._quad(st, lo[j2], lo[i], hi[i], hi[j2], Color.WHITE, ao, Callable())
	var top := pos + Vector3(0.03, h + 0.1, -0.02)
	var r2: Array = rings[2]
	for i in sides:
		ArenaMesh._tri(st, top, r2[(i + 1) % sides], r2[i], Color.WHITE, ao, Callable())


# --- Trainers' podiums -------------------------------------------------------------------

func _podiums(b: Rect2) -> void:
	var cx := b.get_center().x
	var x := b.size.x * 0.5 + RIM + STEP_RUN * (STEPS - 1) + 1.1
	var z := b.get_center().y - 4.3
	var h := 0.3
	trainer_spots = [Vector3(cx - x, RING_Y + h, z), Vector3(cx + x, RING_Y + h, z)]
	for i in 2:
		var p := trainer_spots[i]
		ArenaMesh.prism(_surface("dressed"), ArenaMesh.chamfered_rect(p.x - 0.55, p.z - 0.65, p.x + 0.55, p.z + 0.65, Vector4.ONE * 0.05), RING_Y, RING_Y + h, 0.03, Color.WHITE, Vector2(RING_Y, 0.4))
		var rug := PlaneMesh.new()
		rug.size = Vector2(0.7, 1.05)
		_mesh(rug, _metal(TEAM_RUGS[i], 0.0, 1.0), p + Vector3(0, 0.004, 0))
		_ground_ao(Rect2(p.x - 0.55, p.z - 0.65, 1.1, 1.3), 0.35, 0.45)


# --- Stands and crowd --------------------------------------------------------------------

## Tiered stands rising behind the back wall, packed with spectators.
func _back_stands(b: Rect2) -> void:
	var cx := b.get_center().x
	# a walkway behind the wall, then the tiers
	var z := b.position.y - RIM - BACK_WALL_T - 1.1
	var half := b.size.x * 0.5 + 3.6
	var members: Array = []
	var st := _surface("wall")
	var seats := _surface("wood")
	ArenaMesh.prism(_surface("dressed"), ArenaMesh.chamfered_rect(b.get_center().x - half, z, b.get_center().x + half, z + 1.1), RING_Y, 0.1, 0.0)
	for tier in 4:
		var top := 0.55 + tier * 0.52
		var depth := 0.86
		var z1 := z - tier * depth
		var z0 := z1 - depth
		ArenaMesh.prism(st, ArenaMesh.chamfered_rect(cx - half, z0, cx + half, z1), RING_Y, top - 0.1, 0.0, _jit(0.03), Vector2(top - 0.62, 0.5))
		ArenaMesh.prism(seats, ArenaMesh.chamfered_rect(cx - half, z1 - 0.42, cx + half, z1 - 0.02), top - 0.1, top, 0.015, _jit(0.04))
		var x := -half + rng.randf_range(0.1, 0.5)
		while x < half - 0.2:
			if rng.randf() < 0.88:
				members.append({"pos": Vector3(cx + x, top - 0.04, z1 - 0.3), "variant": rng.randi_range(0, 7), "phase": rng.randf() * 4.0, "speed": rng.randf_range(0.7, 1.3)})
			x += rng.randf_range(0.6, 0.85)
	_awning(Rect2(cx - half, z - 4 * 0.86 - 0.2, half * 2.0, 4 * 0.86 + 0.5), 4.3, 5.1)
	_crowd(CROWD_SHEET, members, Color(0.76, 0.73, 0.82))


## A striped canvas awning over the stands (mostly above the frame: what
## shows is the cool shade it throws over the crowd).
func _awning(r: Rect2, front_y: float, back_y: float) -> void:
	var st := _surface("canvas")
	var stripes := int(r.size.x / 1.0)
	for i in stripes:
		var x0 := r.position.x + i * r.size.x / stripes
		var x1 := x0 + r.size.x / stripes
		var col := Color(0.93, 0.88, 0.78) if i % 2 == 0 else Color(0.72, 0.24, 0.2)
		var a := Vector3(x0, front_y, r.end.y)
		var b2 := Vector3(x1, front_y, r.end.y)
		var c := Vector3(x1, back_y, r.position.y)
		var d := Vector3(x0, back_y, r.position.y)
		ArenaMesh._quad(_surface("canvas"), b2, a, d, c, col, Vector2(-100, 0), Callable())
		# scalloped valance hanging from the front edge
		ArenaMesh._quad(st, a, b2, b2 + Vector3(0, -0.28, 0), a + Vector3(0, -0.36 if i % 2 == 0 else -0.22, 0), col * 0.92, Vector2(-100, 0), Callable())
	# masts at the back of the stands, out of the crowd's way
	var x := r.position.x
	while x <= r.end.x + 0.01:
		ArenaMesh.strut(_surface("iron"), Vector3(x, RING_Y, r.position.y), Vector3(x, back_y, r.position.y), 0.05, 0.04, 5)
		x += 6.0


## Lower wooden stands along both sides of the ring, facing the board.
func _side_stands(b: Rect2) -> void:
	var cx := b.get_center().x
	var x_in := b.size.x * 0.5 + RIM + STEP_RUN * (STEPS - 1) + 2.35
	var members: Array = []
	var st := _surface("wall")
	var seats := _surface("wood")
	for s: float in [-1.0, 1.0]:
		for tier in 4:
			var top := RING_Y + 0.5 + tier * 0.45
			var x0 := cx + s * (x_in + tier * 0.8)
			var x1 := x0 + s * 0.8
			var z0 := b.position.y - RIM - 0.2
			var z1 := b.end.y + RIM + 1.2
			ArenaMesh.prism(st, ArenaMesh.chamfered_rect(minf(x0, x1), z0, maxf(x0, x1), z1), RING_Y, top - 0.09, 0.0, _jit(0.03), Vector2(top - 0.54, 0.45))
			ArenaMesh.prism(seats, ArenaMesh.chamfered_rect(minf(x0, x1) + (0.38 if s < 0 else 0.02), z0, maxf(x0, x1) - (0.02 if s < 0 else 0.38), z1), top - 0.09, top, 0.015, _jit(0.04))
			var zz := z0 + rng.randf_range(0.1, 0.6)
			while zz < z1 - 0.3:
				if rng.randf() < 0.82:
					members.append({"pos": Vector3((x0 + x1) * 0.5, top - 0.04, zz), "variant": rng.randi_range(0, 7), "phase": rng.randf() * 4.0, "speed": rng.randf_range(0.7, 1.3)})
				zz += rng.randf_range(0.65, 0.95)
		var xa := cx + s * x_in
		_ground_ao(Rect2(minf(xa, xa + s * 3.2), b.position.y - RIM - 0.2, 3.2, b.size.y + RIM * 2.0 + 1.4), 0.4, 0.7)
	_crowd(CROWD_SHEET, members, Color(0.82, 0.8, 0.88))


## The front: a low barrier and the backs of the front row (silhouettes,
## deep in the depth of field) framing the bottom of the screen.
func _front_row(b: Rect2) -> void:
	var cx := b.get_center().x
	var z := b.end.y + RIM + STEP_RUN * (STEPS - 1) + 1.3
	var half := b.size.x * 0.5 + 6.0
	ArenaMesh.prism(_surface("wall"), ArenaMesh.chamfered_rect(cx - half, z, cx + half, z + 0.36), RING_Y, RING_Y + 0.55, 0.0, Color(0.9, 0.9, 0.9), Vector2(RING_Y, 0.4))
	ArenaMesh.prism(_surface("dressed"), ArenaMesh.chamfered_rect(cx - half, z - 0.04, cx + half, z + 0.4), RING_Y + 0.55, RING_Y + 0.65, 0.02)
	_ground_ao(Rect2(cx - half, z, half * 2.0, 0.36), 0.4, 0.6)
	var members: Array = []
	var x := -half
	while x < half:
		members.append({"pos": Vector3(cx + x, RING_Y - 0.1, z + 0.9 + rng.randf_range(0.0, 0.35)), "variant": rng.randi_range(0, 5), "phase": rng.randf() * 4.0, "speed": rng.randf_range(0.7, 1.3), "scale": 1.25})
		x += rng.randf_range(0.8, 1.1)
	_crowd(CROWD_BACK_SHEET, members, Color(0.5, 0.47, 0.55))


func _crowd(sheet_path: String, members: Array, modulate: Color) -> void:
	if members.is_empty():
		return
	var sheet := SpriteSheet.load_sheet(sheet_path)
	if not sheet.valid:
		return
	var layer := CrowdLayer.new()
	layer.name = "Crowd"
	root.add_child(layer)
	layer.setup(sheet, members, modulate)
	_crowds.append(layer)


## Crowd reaction (cheer for a while, then settle).
func cheer(seconds: float = 2.0) -> void:
	for c in _crowds:
		if is_instance_valid(c):
			c.cheer(seconds)


# --- Training yard -----------------------------------------------------------------------

func _yard_fences(b: Rect2) -> void:
	var cx := b.get_center().x
	var x_half := b.size.x * 0.5 + RIM + STEP_RUN * (STEPS - 1) + 0.9
	var z_back := b.position.y - RIM - STEP_RUN * (STEPS - 1) - 0.9
	var z_front := b.end.y + RIM + STEP_RUN * (STEPS - 1) + 1.3
	var posts := _surface("pillar")
	var rails := _surface("wall")
	# back fence: a post every two columns, two rails
	var x := -x_half
	while x <= x_half + 0.01:
		ArenaMesh.prism(posts, _square(Vector2(cx + x, z_back), 0.07, 0.015), RING_Y, RING_Y + 1.05, 0.02, _jit(0.06), Vector2(RING_Y, 0.4))
		x += 2.0
	for h: float in [0.42, 0.82]:
		ArenaMesh.prism(rails, ArenaMesh.chamfered_rect(cx - x_half, z_back - 0.04, cx + x_half, z_back + 0.04), RING_Y + h, RING_Y + h + 0.09, 0.012)
	# side fences
	for s: float in [-1.0, 1.0]:
		var z := z_back
		while z <= z_front + 0.01:
			ArenaMesh.prism(posts, _square(Vector2(cx + s * x_half, z), 0.065, 0.015), RING_Y, RING_Y + 0.85, 0.02, _jit(0.06), Vector2(RING_Y, 0.4))
			z += 2.0
		for h2: float in [0.36, 0.7]:
			ArenaMesh.prism(rails, ArenaMesh.chamfered_rect(cx + s * x_half - 0.035, z_back, cx + s * x_half + 0.035, z_front), RING_Y + h2, RING_Y + h2 + 0.08, 0.012)


func _yard_lanterns(b: Rect2) -> void:
	var cx := b.get_center().x
	var x_out := b.size.x * 0.5 + RIM + STEP_RUN * (STEPS - 1) + 0.45
	var low := Settings.graphics_low
	for sz: float in [-1.0, 1.0]:
		for sx: float in [-1.0, 1.0]:
			var z := (b.position.y - RIM - STEP_RUN * (STEPS - 1) - 0.45) if sz < 0.0 else (b.end.y + RIM + STEP_RUN * (STEPS - 1) + 0.45)
			_lantern(Vector3(cx + sx * x_out, RING_Y, z), not low or sz > 0.0)
	for sx: float in [-1.0, 1.0]:
		_lantern(Vector3(cx + sx * x_out, RING_Y, b.get_center().y + 0.5), not low)


## A lantern post standing on the lawn.
func _lantern(base: Vector3, with_light: bool) -> void:
	var s := EnvKit.prop(root, "lantern_post", base, 1.0, true)
	s.set_param("emission_strength", 2.6)
	s.set_param("emission_threshold", 0.7)
	var top := base + Vector3(0, 1.8, 0)
	_glow(top, 1.6, Color(1.0, 0.78, 0.45), 0.28)
	if with_light:
		_light(top + Vector3(0, 0.0, 0.25), Color(1.0, 0.76, 0.48), 1.6, 6.5)


## Training-yard dressing on the lawn beside the board: hay, barrels, crates
## and a couple of villagers watching.
func _yard_props(b: Rect2) -> void:
	var x_out := b.size.x * 0.5 + RIM + STEP_RUN * (STEPS - 1) + 1.6
	var cx := b.get_center().x
	var z0 := b.position.y
	var y := RING_Y
	EnvKit.prop(root, "hay_bale", Vector3(cx - x_out - 0.4, y, z0 + 0.6))
	EnvKit.prop(root, "hay_bale", Vector3(cx - x_out - 1.3, y, z0 + 1.3), 0.9)
	EnvKit.prop(root, "barrel", Vector3(cx + x_out + 0.3, y, z0 + 0.5))
	EnvKit.prop(root, "crate", Vector3(cx + x_out + 1.1, y, z0 + 0.9))
	EnvKit.prop(root, "barrel", Vector3(cx + x_out + 0.7, y, b.end.y - 0.9), 0.9)
	EnvKit.prop(root, "crate", Vector3(cx - x_out - 0.7, y, b.end.y - 0.6))
	EnvKit.prop(root, "signpost", Vector3(cx - x_out - 0.9, y, b.end.y + 1.2))
	var folk := [["villager_farmer", Vector3(cx - x_out - 1.4, y, z0 + 3.4), "e"], ["villager_baker", Vector3(cx + x_out + 1.4, y, b.end.y - 2.6), "w"]]
	for f in folk:
		var s := PixelSprite3D.new()
		s.load_manifest("res://assets/sprites/characters/%s.json" % f[0])
		s.position = f[1]
		root.add_child(s)
		s.play("idle", f[2])
		EnvKit.blob_shadow(root, 0.32, 0.35).position = (f[1] as Vector3) + Vector3(0, 0.015, 0)


## A few cottages beyond the back fence (deep in the depth of field).
func _yard_cottages(b: Rect2) -> void:
	var cx := b.get_center().x
	var z := b.position.y - 5.6
	var walls := _surface("plaster")
	var roofs := _surface("roof")
	for i in 4:
		var x := cx - 12.0 + i * 8.0 + rng.randf_range(-1.0, 1.0)
		var w := rng.randf_range(3.2, 4.4)
		var d := rng.randf_range(2.6, 3.2)
		var h := rng.randf_range(1.6, 2.1)
		var zz := z - rng.randf_range(0.0, 1.5)
		ArenaMesh.prism(walls, ArenaMesh.chamfered_rect(x - w * 0.5, zz - d * 0.5, x + w * 0.5, zz + d * 0.5), RING_Y, RING_Y + h, 0.0, _jit(0.05), Vector2(RING_Y, 0.4))
		# a simple gable roof as two sloped slabs
		var ridge := RING_Y + h + 1.2
		var eave := RING_Y + h - 0.05
		for s: float in [-1.0, 1.0]:
			var a := Vector3(x - w * 0.5 - 0.25, eave, zz + s * (d * 0.5 + 0.3))
			var bb := Vector3(x + w * 0.5 + 0.25, eave, zz + s * (d * 0.5 + 0.3))
			var c := Vector3(x + w * 0.5 + 0.25, ridge, zz)
			var dd := Vector3(x - w * 0.5 - 0.25, ridge, zz)
			if s > 0.0:
				ArenaMesh._quad(roofs, a, bb, c, dd, Color.WHITE, Vector2(-100, 0), Callable())
			else:
				ArenaMesh._quad(roofs, bb, a, dd, c, Color.WHITE, Vector2(-100, 0), Callable())


# --- Ground, trees, weeds ----------------------------------------------------------------

func _ground(b: Rect2) -> void:
	var rect := Rect2(-34, -30, 68, 56)
	var mi := MeshInstance3D.new()
	mi.name = "Ground"
	var pm := PlaneMesh.new()
	pm.size = rect.size
	mi.mesh = pm
	mi.position = Vector3(rect.get_center().x, RING_Y, rect.get_center().y)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var m := ShaderMaterial.new()
	m.shader = GROUND_SHADER
	var pav := _hd_tex("arena_hd_paving")
	m.set_shader_parameter("paving", pav)
	m.set_shader_parameter("paving_size", pav.get_size())
	var g1 := _hd_tex("grass_a")
	var g2 := _hd_tex("dirt_path" if _stone else "grass_b")
	m.set_shader_parameter("outer", g1)
	m.set_shader_parameter("outer_size", g1.get_size())
	m.set_shader_parameter("outer_b", g2)
	m.set_shader_parameter("outer_b_size", g2.get_size())
	var x_half := b.size.x * 0.5 + RIM + STEP_RUN * (STEPS - 1)
	if _stone:
		m.set_shader_parameter("paved_rect", Vector4(b.get_center().x - x_half - 5.5, b.position.y - 9.0, b.get_center().x + x_half + 5.5, b.end.y + 4.6))
		m.set_shader_parameter("paving_tint", Color(0.9, 0.88, 0.86))
	else:
		# the yard: a trodden earth apron round the deck, lawn beyond
		var dirt := _hd_tex("dirt_path")
		m.set_shader_parameter("paving", dirt)
		m.set_shader_parameter("paving_size", dirt.get_size())
		m.set_shader_parameter("paving_texels", 24.0)
		m.set_shader_parameter("paved_rect", Vector4(b.get_center().x - x_half - 0.6, b.position.y - 1.8, b.get_center().x + x_half + 0.6, b.end.y + 2.0))
		m.set_shader_parameter("border", 1.6)
	var rects: Array[Vector4] = _ao_rects.duplicate()
	var params: Array[Vector2] = _ao_params.duplicate()
	var count := rects.size()
	while rects.size() < 16:
		rects.append(Vector4.ZERO)
		params.append(Vector2.ZERO)
	m.set_shader_parameter("ao_rects", rects)
	m.set_shader_parameter("ao_params", params)
	m.set_shader_parameter("ao_count", count)
	mi.material_override = m
	root.add_child(mi)


## Trees behind the stands and beyond the sides, falling into the depth of field.
func _trees(b: Rect2) -> void:
	var kinds := ["tree_oak_a", "tree_oak_b", "tree_pine", "tree_birch"]
	var items: Array = []
	var x := b.position.x - 14.0
	while x < b.end.x + 14.0:
		var z := b.position.y - 8.6 - rng.randf_range(0.0, 2.4)
		if not def.crowd:
			# the yard: a ragged treeline among the cottages behind the fence
			z = b.position.y - 4.6 - rng.randf_range(0.0, 3.4)
		items.append([Vector3(x, RING_Y, z), rng.randi_range(0, 3), rng.randf_range(1.15, 1.5)])
		x += rng.randf_range(1.3, 2.2)
	for s: float in [-1.0, 1.0]:
		var z2 := b.position.y - 6.0
		while z2 < b.end.y + 5.0:
			items.append([Vector3(b.get_center().x + s * rng.randf_range(19.5, 22.0), RING_Y, z2), rng.randi_range(0, 3), rng.randf_range(1.1, 1.4)])
			z2 += rng.randf_range(1.6, 2.6)
	var atlas := EnvKit.atlas(kinds)
	EnvKit.scatter(root, atlas, items, false, 0.9)


## Grass and weeds where stone meets ground (one MultiMesh).
func _weeds(b: Rect2) -> void:
	var atlas := EnvKit.atlas(["grass_tuft_a", "grass_tuft_b", "grass_tuft_c", "grass_tuft_d", "rock_small_a", "flowers_yellow", "flowers_white"])
	var items: Array = []
	var x_steps := b.size.x * 0.5 + RIM + STEP_RUN * (STEPS - 1)
	var z_front := b.end.y + RIM + STEP_RUN * (STEPS - 1)
	# along the foot of the front and side steps
	var x2 := b.position.x - RIM - 1.0
	while x2 < b.end.x + RIM + 1.0:
		if rng.randf() < 0.55:
			items.append([Vector3(x2, RING_Y, z_front + rng.randf_range(0.04, 0.3)), _weed_index(), rng.randf_range(0.75, 1.0)])
		x2 += rng.randf_range(0.6, 1.5)
	for s: float in [-1.0, 1.0]:
		var z := b.position.y - RIM
		while z < z_front:
			if rng.randf() < 0.6:
				items.append([Vector3(b.get_center().x + s * (x_steps + rng.randf_range(0.04, 0.3)), RING_Y, z), _weed_index(), rng.randf_range(0.7, 1.0)])
			z += rng.randf_range(0.6, 1.6)
	if not _stone:
		# tufts along the deck's laths at the edges
		for i in 24:
			items.append([Vector3(rng.randf_range(b.position.x - 3.0, b.end.x + 3.0), RING_Y, b.end.y + RIM + 1.2 + rng.randf_range(0.0, 1.2)), _weed_index(), rng.randf_range(0.8, 1.1)])
	EnvKit.scatter(root, atlas, items, false, 0.5)


func _weed_index() -> int:
	var r := rng.randf()
	if r < 0.7:
		return rng.randi_range(0, 3)
	return rng.randi_range(4, 6)


# --- Atmosphere ------------------------------------------------------------------------------

func _atmosphere(b: Rect2) -> void:
	_motes(b)


## Sunlit dust drifting over the arena.
func _motes(b: Rect2) -> void:
	var p := CPUParticles3D.new()
	p.amount = 24 if Settings.graphics_low else 70
	p.lifetime = 9.0
	p.preprocess = 9.0
	p.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	p.emission_box_extents = Vector3(b.size.x * 0.5 + 2.0, 1.1, b.size.y * 0.5 + 1.5)
	p.position = Vector3(b.get_center().x, 1.9, b.get_center().y)
	p.direction = Vector3(0.6, 0.2, -0.25)
	p.spread = 60.0
	p.initial_velocity_min = 0.06
	p.initial_velocity_max = 0.26
	p.gravity = Vector3(0, 0.012, 0)
	p.mesh = _speck_mesh(2.4)
	p.scale_amount_min = 0.5
	p.scale_amount_max = 1.25
	var g := Gradient.new()
	g.set_color(0, Color(1.9, 1.6, 1.1, 0.0))
	g.add_point(0.2, Color(1.9, 1.6, 1.1, 0.85))
	g.add_point(0.8, Color(1.7, 1.45, 1.0, 0.85))
	g.set_color(g.get_point_count() - 1, Color(1.5, 1.3, 0.9, 0.0))
	p.color_ramp = g
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(p)


static func _speck_mesh(texels: float) -> QuadMesh:
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE * texels / TEXELS
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	quad.material = m
	return quad


## The depth-aware tilt-shift pass (high graphics; low uses PostFX's band).
func _depth_of_field(b: Rect2) -> void:
	var mi := MeshInstance3D.new()
	mi.name = "DepthOfField"
	mi.mesh = QuadMesh.new()
	var m := ShaderMaterial.new()
	m.shader = DOF_SHADER
	m.render_priority = -127
	# sharp: the board, its rim, the back wall and everything standing on the
	# steps and side rings; the stands behind the wall start to soften at once
	var x_half := b.size.x * 0.5 + RIM + STEP_RUN * (STEPS - 1) + 0.25
	var z_back := b.position.y - RIM - (BACK_WALL_T + 0.05 if _stone else 0.6)
	var z_front := b.end.y + RIM + STEP_RUN * (STEPS - 1) + 0.1
	m.set_shader_parameter("focus_rect", Vector4(b.get_center().x - x_half, z_back, b.get_center().x + x_half, z_front))
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.custom_aabb = AABB(Vector3(-1e4, -1e4, -1e4), Vector3(2e4, 2e4, 2e4))
	root.add_child(mi)
	var apply := func() -> void:
		mi.visible = Settings.tilt_shift and not Settings.graphics_low
	apply.call()
	Events.settings_changed.connect(apply)
	mi.tree_exiting.connect(func() -> void:
		if Events.settings_changed.is_connected(apply):
			Events.settings_changed.disconnect(apply))


# --- Lighting and post ---------------------------------------------------------------------

## Switch a LightingRig built next to the arena to its arena variant.
func _tune_lighting(parent: Node) -> void:
	for c in parent.get_children():
		if c is LightingRig:
			var rig := c as LightingRig
			var arena_preset := StringName("arena_" + String(rig.preset_name))
			if LightingRig.PRESETS.has(arena_preset):
				rig.apply(arena_preset)


## Battle grading for this arena: warm highlights, cool shadows, a filmic
## curve and a firm vignette. The tilt-shift band (used when the depth pass
## is off, i.e. on low graphics) follows the board's rows on screen, which the
## battle camera publishes.
static func apply_post(post: PostFX, p_def: ArenaDefinition) -> void:
	var stone := p_def.floor_style != &"dirt"
	post.set_battle_mode(true)
	post.set_param("vignette", 0.62)
	post.set_param("saturation", 1.15)
	post.set_param("contrast", 1.08)
	post.set_param("shadow_tint", Vector3(0.86, 0.93, 1.1))
	post.set_param("highlight_tint", Vector3(1.06, 1.0, 0.92) if stone else Vector3(1.04, 1.0, 0.95))
	post.set_param("filmic", 0.2)
	# soft god rays slanting in from the upper left, where the sun is
	post.set_param("shaft_dir", Vector2(0.62, 1.0))
	post.set_param("shaft_color", Color(1.0, 0.84, 0.58) if stone else Color(1.0, 0.94, 0.8))
	post.set_param("shafts", 0.12 if stone else 0.09)
	post.set_param("grain", 0.025)
	post.set_param("aberration", 0.6)


# --- Helpers -----------------------------------------------------------------------------------

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
