class_name SpriteSheet
extends RefCounted
## Runtime view of an art sheet: texture + manifest (see tools/common/sheet.py).
## Direction fallback: <anim>_<dir> -> <anim>_s -> <anim>. West mirrors east.

const LIGHTING_KEYS := ["shade_floor", "normal_strength", "rim_strength", "rim_power"]

static var _cache: Dictionary = {}

var path: String = ""
var texture: Texture2D
## Optional normal map in the sheet's layout (manifest "normal_map"): rgb is
## the screen-aligned normal, alpha the emission mask (see pixel_sprite.gdshader).
var normal_texture: Texture2D
var frame_size := Vector2(48, 48)
var columns := 1
var frame_count := 1
var pivot := Vector2(24, 44)
var pixels_per_unit := 24.0
var animations: Dictionary = {}  # name -> {"frames": Array, "fps": float, "loop": bool}
## Per-sheet lighting response (manifest "lighting"): shader parameters such as
## shade_floor, normal_strength, rim_strength and rim_power (see pixel_sprite.gdshader).
var lighting: Dictionary = {}
var valid := false


static func load_sheet(manifest_path: String) -> SpriteSheet:
	if _cache.has(manifest_path):
		return _cache[manifest_path]
	var s := SpriteSheet.new()
	s.path = manifest_path
	s._load(manifest_path)
	_cache[manifest_path] = s
	return s


## A single-frame "sheet" for a plain PNG (props, foliage). Pivot = bottom-center.
static func from_texture(png_path: String, pivot_override: Vector2 = Vector2(-1, -1)) -> SpriteSheet:
	var key := png_path + "#single"
	if _cache.has(key):
		return _cache[key]
	var s := SpriteSheet.new()
	s.path = png_path
	if ResourceLoader.exists(png_path):
		s.texture = load(png_path)
	if s.texture:
		s.frame_size = s.texture.get_size()
		s.pivot = pivot_override if pivot_override.x >= 0.0 else Vector2(s.frame_size.x * 0.5, s.frame_size.y - 1.0)
		s.columns = 1
		s.frame_count = 1
		s.animations = {"idle_s": {"frames": [0], "fps": 1.0, "loop": true}}
		s.valid = true
	_cache[key] = s
	return s


func _load(manifest_path: String) -> void:
	if not FileAccess.file_exists(manifest_path):
		return
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
	if not data is Dictionary:
		push_warning("Bad sprite manifest: %s" % manifest_path)
		return
	var image_path := manifest_path.get_base_dir().path_join(str(data.get("image", "")))
	if not ResourceLoader.exists(image_path):
		push_warning("Missing sprite image: %s" % image_path)
		return
	texture = load(image_path)
	var normal_name := str(data.get("normal_map", ""))
	if normal_name != "":
		var normal_path := manifest_path.get_base_dir().path_join(normal_name)
		if ResourceLoader.exists(normal_path):
			normal_texture = load(normal_path)
		else:
			push_warning("Missing normal map: %s" % normal_path)
	var fs: Array = data.get("frame_size", [48, 48])
	frame_size = Vector2(float(fs[0]), float(fs[1]))
	columns = int(data.get("columns", 1))
	frame_count = int(data.get("frame_count", 1))
	var pv: Array = data.get("pivot", [frame_size.x * 0.5, frame_size.y - 1.0])
	pivot = Vector2(float(pv[0]), float(pv[1]))
	pixels_per_unit = float(data.get("pixels_per_unit", 24))
	animations = data.get("animations", {})
	var light_data: Variant = data.get("lighting", {})
	if light_data is Dictionary:
		for k: String in light_data:
			if k in LIGHTING_KEYS:
				lighting[k] = float(light_data[k])
	valid = texture != null


func has_anim(anim_name: String) -> bool:
	return animations.has(anim_name)


## Resolves "<anim>" + direction ("s", "n", "e", "w") to an existing animation
## name. Returns [name, flip_h].
func resolve(anim: String, dir: String) -> Array:
	var flip := dir == "w"
	var d := "e" if dir == "w" else dir
	var candidates := ["%s_%s" % [anim, d], "%s_s" % anim, anim]
	for c in candidates:
		if animations.has(c):
			return [c, flip and c.ends_with("_e")]
	return ["", false]


func frames_of(anim_name: String) -> Array:
	var a: Dictionary = animations.get(anim_name, {})
	return a.get("frames", [0])


func fps_of(anim_name: String) -> float:
	var a: Dictionary = animations.get(anim_name, {})
	return float(a.get("fps", 8.0))


func loops(anim_name: String) -> bool:
	var a: Dictionary = animations.get(anim_name, {})
	return bool(a.get("loop", true))


func duration_of(anim_name: String) -> float:
	return float(frames_of(anim_name).size()) / maxf(0.1, fps_of(anim_name))


func world_height() -> float:
	return frame_size.y / pixels_per_unit
