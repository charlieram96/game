extends Node3D
## Dev scene: sprite sheets standing on a lit battle arena, for art review.
## The arena, lighting and post-processing are the real battle ones; the
## camera is the battle camera (or a closer one with the same pitch).
##
##   --shot=<path>          save a screenshot and quit (after --frames, default 30)
##   --sheets=a,b,...       sheets to show (kith/<a>.json, characters/<a>.json or props/<a>.json)
##   --anim=<name>          animation for every sprite (default ready, else idle)
##   --dirs=s,e,n,w         one row per sheet with these facings (default e)
##   --frame=<i>            hold frame i instead of playing
##   --shadows              sprites cast real shadows (the blob shadow is lighter)
##   --light[=x,y,z]        a warm, flickering point light (like a brazier), offset from the row's centre
##   --energy=<e>           its energy (default 1.4)
##   --lighting=<preset>    a LightingRig preset (default: the arena's)
##   --zoom=<cells>         camera shows this many cells across (default: battle framing)
##   --spacing=<cells>      cells between neighbouring sprites (default 1)
##   --layout=row           every sheet and facing in one row (side-by-side comparisons)
##   --at=<x>,<z>           centre of the sprites on the board (default: two cells from the left spawn)
##   --arena=<id>           ringstones (default) or training_yard
##   --measure              print each sprite's on-screen size in pixels and in board cells

var _args := {}
var _flags: Array[String] = []
var _sprites: Array[PixelSprite3D] = []
var _light: OmniLight3D
var _t := 0.0


func _ready() -> void:
	_parse_args()
	var def := ArenaDefinition.by_id(StringName(_args.get("arena", "ringstones")))
	var rig := LightingRig.new()
	add_child(rig)
	rig.apply(StringName(_args.get("lighting", "golden" if def.crowd else "day")))
	var builder := ArenaBuilder.new()
	builder.build(self, def)
	var post := PostFX.new()
	add_child(post)
	ArenaBuilder.apply_post(post, def)
	var centre := Vector3(def.spawn_team0.x + 2.0, 0.0, def.spawn_team0.y)
	if _args.has("at"):  # --at=x,z: the row's centre on the board (a cell centre)
		var at: PackedStringArray = String(_args["at"]).split(",")
		centre = Vector3(float(at[0]), 0.0, float(at[1]))
	_spawn(centre)
	_make_camera(def, centre)
	if _flags.has("light") or _args.has("light"):
		_light = OmniLight3D.new()
		_light.light_color = Color(1.0, 0.62, 0.3)
		_light.light_energy = float(_args.get("energy", "1.4"))
		_light.omni_range = 4.5
		_light.shadow_enabled = true
		var off := Vector3(-1.2, 1.1, 0.6)
		if _args.has("light"):
			var p: PackedStringArray = String(_args["light"]).split(",")
			off = Vector3(float(p[0]), float(p[1]), float(p[2]))
		_light.position = centre + off
		add_child(_light)
	for i in int(_args.get("frames", "30")):
		await get_tree().process_frame
	if _flags.has("measure"):
		_measure()
	if _args.has("shot"):
		get_viewport().get_texture().get_image().save_png(_args["shot"])
		get_tree().quit()


func _process(delta: float) -> void:
	_t += delta
	if _light:
		var e := float(_args.get("energy", "1.4"))
		_light.light_energy = e * (1.0 + 0.1 * sin(_t * 13.0) + 0.06 * sin(_t * 31.0))


func _parse_args() -> void:
	for arg in OS.get_cmdline_user_args():
		if not arg.begins_with("--"):
			continue
		if arg.contains("="):
			_args[arg.substr(2, arg.find("=") - 2)] = arg.substr(arg.find("=") + 1)
		else:
			_flags.append(arg.substr(2))


func _manifest(sheet_name: String) -> String:
	if sheet_name.contains("/"):  # a path under assets/sprites/, e.g. a copy of an older sheet
		return "res://assets/sprites/%s.json" % sheet_name
	for dir in ["kith", "characters", "props"]:
		var p := "res://assets/sprites/%s/%s.json" % [dir, sheet_name]
		if FileAccess.file_exists(p):
			return p
	return ""


func _spawn(centre: Vector3) -> void:
	var names := String(_args.get("sheets", "emberlyn,stoneback")).split(",")
	var dirs := String(_args.get("dirs", "e")).split(",")
	var shadows := _flags.has("shadows")
	# every sprite stands on a cell centre: one row per sheet (--layout=row: all in one row),
	# `--spacing` cells apart
	var spacing := int(_args.get("spacing", "1"))
	var one_row := String(_args.get("layout", "")) == "row"
	var per_row := names.size() * dirs.size() if one_row else dirs.size()
	for r in names.size():
		for c in dirs.size():
			var s := PixelSprite3D.new()
			s.load_manifest(_manifest(names[r]))
			var col := r * dirs.size() + c if one_row else c
			var row := 0 if one_row else r
			s.position = centre + Vector3(roundf((float(col) - float(per_row - 1) * 0.5) * float(spacing)), 0.0, float(row * 2 - ((names.size() - 1) if not one_row else 0)))
			s.set_param("emission_strength", 1.8)
			s.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			add_child(s)
			var anim := String(_args.get("anim", "ready"))
			if not s.has_animation(anim):
				anim = "idle"
			if _args.has("frame"):
				s.show_frame(anim, dirs[c], int(_args["frame"]))
			else:
				s.play(anim, dirs[c])
			EnvKit.blob_shadow(self, 0.45, 0.25 if shadows else 0.5).position = s.position + Vector3(0, 0.015, 0)
			s.set_meta("label", "%s %s_%s" % [names[r], anim, dirs[c]])
			_sprites.append(s)


func _make_camera(def: ArenaDefinition, centre: Vector3) -> void:
	if not _args.has("zoom"):
		var cam := BattleCamera.new()
		add_child(cam)
		cam.make_current()
		cam.setup(def.size)
		return
	# Same pitch as the battle camera, closer: `zoom` cells across the screen.
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.keep_aspect = Camera3D.KEEP_WIDTH
	cam.size = float(_args["zoom"])
	var pitch := BattleCamera.pitch()
	cam.rotation = Vector3(-pitch, 0.0, 0.0)
	cam.position = centre + Vector3(0.0, 0.45, 0.0) + Vector3(0.0, sin(pitch), cos(pitch)) * 20.0
	cam.near = 0.1
	cam.far = 80.0
	add_child(cam)
	cam.make_current()
	RenderingServer.global_shader_parameter_set("sprite_stretch", 1.0 / cos(pitch))


## On-screen size of each sprite's current frame, in pixels and in board cells
## (a cell's on-screen width is measured with the same camera).
func _measure() -> void:
	var cam := get_viewport().get_camera_3d()
	var cell_px := cam.unproject_position(Vector3(1, 0, 0)).x - cam.unproject_position(Vector3(0, 0, 0)).x
	print("cell width on screen: %.1f px (viewport %s)" % [cell_px, get_viewport().get_visible_rect().size])
	for s in _sprites:
		var sheet := s.sheet
		var img := sheet.texture.get_image()
		var f := int(s.get_param("frame"))
		var fs := Vector2i(sheet.frame_size)
		var rect := Rect2i(Vector2i(f % sheet.columns, f / sheet.columns) * fs, fs)
		var used := img.get_region(rect).get_used_rect()
		var w_cells := used.size.x / sheet.pixels_per_unit
		var h_cells := used.size.y / sheet.pixels_per_unit
		print("%-34s %3dx%3d texels -> %.2f x %.2f cells, %.0f x %.0f px" % [s.get_meta("label"), used.size.x, used.size.y, w_cells, h_cells, w_cells * cell_px, h_cells * cell_px])
