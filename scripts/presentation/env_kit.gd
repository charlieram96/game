class_name EnvKit
extends RefCounted
## Builders for the HD-2D environment: pixel-textured meshes, billboard
## props, terrain, scattered foliage, contact shadows. Shared by the battle
## arena and the exploration region.

const WORLD_SHADER := preload("res://shaders/world_pixel.gdshader")
const TERRAIN_SHADER := preload("res://shaders/terrain.gdshader")
const BLOB_SHADER := preload("res://shaders/blob_shadow.gdshader")
const SPRITE_SHADER := preload("res://shaders/pixel_sprite.gdshader")
const TEX_DIR := "res://assets/environments/textures/"
const FOLIAGE_DIR := "res://assets/environments/foliage/"
const PROP_DIR := "res://assets/environments/props/"

static var _materials: Dictionary = {}
static var _textures: Dictionary = {}
static var _atlases: Dictionary = {}


static func tex(tex_name: String) -> Texture2D:
	if _textures.has(tex_name):
		return _textures[tex_name]
	var path := TEX_DIR + tex_name + ".png"
	var t: Texture2D = load(path) if ResourceLoader.exists(path) else _fallback_texture()
	_textures[tex_name] = t
	return t


static func _fallback_texture() -> Texture2D:
	var img := Image.create(8, 8, false, Image.FORMAT_RGBA8)
	img.fill(Color(0.6, 0.55, 0.5))
	return ImageTexture.create_from_image(img)


## Triplanar pixel material for meshes. `top` optionally textures upward faces.
static func material(tex_name: String, tint: Color = Color.WHITE, top: String = "", top_tint: Color = Color.WHITE, ao: float = 0.35) -> ShaderMaterial:
	var key := "%s|%s|%s|%s|%s" % [tex_name, tint, top, top_tint, ao]
	if _materials.has(key):
		return _materials[key]
	var m := ShaderMaterial.new()
	m.shader = WORLD_SHADER
	var t := tex(tex_name)
	m.set_shader_parameter("tex", t)
	m.set_shader_parameter("tex_size", t.get_size())
	m.set_shader_parameter("tint", tint)
	m.set_shader_parameter("ao_strength", ao)
	if top != "":
		var tt := tex(top)
		m.set_shader_parameter("use_top_tex", true)
		m.set_shader_parameter("top_tex", tt)
		m.set_shader_parameter("top_tex_size", tt.get_size())
		m.set_shader_parameter("top_tint", top_tint)
	_materials[key] = m
	return m


static func box(parent: Node, size: Vector3, pos: Vector3, mat: Material, rot_y: float = 0.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.material_override = mat
	mi.position = pos + Vector3(0, size.y * 0.5, 0)
	mi.rotation.y = rot_y
	parent.add_child(mi)
	return mi


static func cylinder(parent: Node, radius_bottom: float, radius_top: float, height: float, pos: Vector3, mat: Material, segments: int = 8, rot_y: float = 0.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.bottom_radius = radius_bottom
	cm.top_radius = radius_top
	cm.height = height
	cm.radial_segments = segments
	cm.rings = 1
	mi.mesh = cm
	mi.material_override = mat
	mi.position = pos + Vector3(0, height * 0.5, 0)
	mi.rotation.y = rot_y
	parent.add_child(mi)
	return mi


## Gable roof: a triangular prism spanning `size` (x = width, y = height, z = depth).
static func gable_roof(parent: Node, size: Vector3, pos: Vector3, mat: Material, rot_y: float = 0.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var pm := PrismMesh.new()
	pm.size = size
	mi.mesh = pm
	mi.material_override = mat
	mi.position = pos + Vector3(0, size.y * 0.5, 0)
	mi.rotation.y = rot_y
	parent.add_child(mi)
	return mi


## A pixel-art billboard prop/foliage sprite planted at `pos`.
static func sprite(parent: Node, png_path: String, pos: Vector3, scale: float = 1.0, shadows: bool = true, sway: float = 0.0) -> PixelSprite3D:
	var s := PixelSprite3D.new()
	s.load_texture(png_path)
	s.position = pos
	if scale != 1.0:
		s.scale = Vector3.ONE * scale
	s.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	if sway > 0.0:
		s.set_param("sway", sway)
	parent.add_child(s)
	return s


static func foliage(parent: Node, foliage_name: String, pos: Vector3, scale: float = 1.0, shadows: bool = true, sway: float = 0.0) -> PixelSprite3D:
	return sprite(parent, FOLIAGE_DIR + foliage_name + ".png", pos, scale, shadows, sway)


static func prop(parent: Node, prop_name: String, pos: Vector3, scale: float = 1.0, shadows: bool = true) -> PixelSprite3D:
	return sprite(parent, PROP_DIR + prop_name + ".png", pos, scale, shadows)


static func animated_prop(parent: Node, sheet_name: String, anim: String, pos: Vector3, shadows: bool = false) -> PixelSprite3D:
	var s := PixelSprite3D.new()
	s.load_manifest(PROP_DIR + sheet_name + ".json")
	s.position = pos
	s.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(s)
	s.play(anim, "s")
	return s


static func blob_shadow(parent: Node, radius: float, opacity: float = 0.45) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(radius * 2.0, radius * 1.6)
	mi.mesh = pm
	var m := ShaderMaterial.new()
	m.shader = BLOB_SHADER
	m.set_shader_parameter("opacity", opacity)
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.position.y = 0.015
	parent.add_child(mi)
	return mi


## Flat terrain with a splat map (RGBA weights). `layers` = [base, r, g, b, a] texture names.
static func terrain(parent: Node, rect: Rect2, splat: Image, layers: Array, tint: Color = Color.WHITE) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = rect.size
	pm.subdivide_width = 0
	pm.subdivide_depth = 0
	mi.mesh = pm
	mi.position = Vector3(rect.position.x + rect.size.x * 0.5, 0.0, rect.position.y + rect.size.y * 0.5)
	var m := ShaderMaterial.new()
	m.shader = TERRAIN_SHADER
	var names := ["base_tex", "tex_r", "tex_g", "tex_b", "tex_a"]
	for i in names.size():
		var layer_name: String = layers[i] if i < layers.size() else layers[0]
		m.set_shader_parameter(names[i], tex(layer_name))
	m.set_shader_parameter("tex_size", tex(layers[0]).get_size())
	m.set_shader_parameter("splat", ImageTexture.create_from_image(splat))
	m.set_shader_parameter("splat_rect", Vector4(rect.position.x, rect.position.y, rect.size.x, rect.size.y))
	m.set_shader_parameter("tint", tint)
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(mi)
	return mi


## Packs several single-image sprites into one atlas (bottom-center aligned cells).
static func atlas(names: Array, dir: String = FOLIAGE_DIR) -> Dictionary:
	var key := dir + ",".join(names)
	if _atlases.has(key):
		return _atlases[key]
	var images: Array[Image] = []
	var cell := Vector2i(1, 1)
	for n in names:
		var path: String = dir + n + ".png"
		var img: Image = null
		if ResourceLoader.exists(path):
			img = (load(path) as Texture2D).get_image()
		if img == null:
			img = Image.create(8, 8, false, Image.FORMAT_RGBA8)
		if img.is_compressed():
			img.decompress()
		img.convert(Image.FORMAT_RGBA8)
		images.append(img)
		cell = Vector2i(maxi(cell.x, img.get_width()), maxi(cell.y, img.get_height()))
	var cols := images.size()
	var out := Image.create(cell.x * cols, cell.y, false, Image.FORMAT_RGBA8)
	out.fill(Color(0, 0, 0, 0))
	for i in images.size():
		var img := images[i]
		var dst := Vector2i(i * cell.x + (cell.x - img.get_width()) / 2, cell.y - img.get_height())
		out.blit_rect(img, Rect2i(Vector2i.ZERO, img.get_size()), dst)
	var result := {"texture": ImageTexture.create_from_image(out), "cell": Vector2(cell), "columns": cols, "count": images.size()}
	_atlases[key] = result
	return result


## Scatters many small billboard sprites in one draw call. `items` is an
## array of [Vector3 position, int atlas_index, float scale].
static func scatter(parent: Node, atlas_info: Dictionary, items: Array, shadows: bool = false, sway: float = 0.6, can_occlude: bool = false) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.mesh = QuadMesh.new()
	mm.instance_count = items.size()
	for i in items.size():
		var it: Array = items[i]
		var t := Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * float(it[2])), it[0])
		mm.set_instance_transform(i, t)
		mm.set_instance_custom_data(i, Color(float(it[1]), 0, 0, 0))
	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh = mm
	var m := ShaderMaterial.new()
	m.shader = SPRITE_SHADER
	var tex2d: Texture2D = atlas_info["texture"]
	m.set_shader_parameter("sheet", tex2d)
	m.set_shader_parameter("sheet_size", tex2d.get_size())
	m.set_shader_parameter("frame_size", atlas_info["cell"])
	m.set_shader_parameter("columns", float(atlas_info["columns"]))
	var cell: Vector2 = atlas_info["cell"]
	m.set_shader_parameter("pivot", Vector2(cell.x * 0.5, cell.y - 1.0))
	m.set_shader_parameter("pixel_size", 1.0 / 24.0)
	m.set_shader_parameter("instance_frame", true)
	m.set_shader_parameter("sway", sway)
	m.set_shader_parameter("can_occlude", can_occlude)
	mmi.material_override = m
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(mmi)
	return mmi


## Deterministic value noise helper for layout scattering.
static func noise2(x: float, y: float, seed_value: int = 0) -> float:
	var h := int(floor(x)) * 374761393 + int(floor(y)) * 668265263 + seed_value * 982451653
	h = (h ^ (h >> 13)) * 1274126177
	h = h ^ (h >> 16)
	return float(h & 0xFFFF) / 65535.0
