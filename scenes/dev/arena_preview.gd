extends Node3D
## Dev scene: renders a battle arena with both kith and the trainers, lit and
## post-processed like a real battle, for visual checks.
##
##   --shot=<path>            save a screenshot and quit
##   --arena=<id>             ringstones (default) or training_yard
##   --lighting=<preset>      default: the arena's battle preset
##   --guides                 outline the HUD bands, the board and every cell boundary
##   --frames=<n>             frames to wait before the shot (default 20)
##   --low                    preview with Settings.graphics_low
##   --insets=<l>,<r>         side insets for the camera (canvas px), e.g. touch buttons
##   --stats                  print draw calls / objects / nodes after the frames
##   --highlight              light up a few cells (ArenaBuilder.set_cell_highlight)
##   --nosun                  switch the sun and sky fill off (see the point lights alone)

var _args := {}
var _flags: Array[String] = []


func _ready() -> void:
	_parse_args()
	if _flags.has("low"):
		Settings.graphics_low = true
	var def := ArenaDefinition.by_id(StringName(_args.get("arena", "ringstones")))
	var rig := LightingRig.new()
	add_child(rig)
	rig.apply(StringName(_args.get("lighting", "golden" if def.crowd else "day")))
	var builder := ArenaBuilder.new()
	builder.build(self, def)
	var cam := _make_camera(def)
	var post := PostFX.new()
	add_child(post)
	ArenaBuilder.apply_post(post, def)
	_spawn_kith(def)
	_spawn_trainers(builder, def)
	if _flags.has("nosun"):
		# only the braziers, lanterns and ambient: check the point lights' pools
		rig.sun.visible = false
		rig.fill.visible = false
	if _flags.has("guides"):
		_add_guides(cam)
	if _flags.has("highlight"):
		var from := def.cell_of(def.spawn_team0 + Vector2(1.0, 0.0))
		for i in 4:
			builder.set_cell_highlight(from + Vector2i(i + 1, 0), 1.0 - i * 0.2)
	if _args.has("shot") or _flags.has("stats"):
		for i in int(_args.get("frames", "20")):
			await get_tree().process_frame
		if _flags.has("stats"):
			_print_stats()
		if _args.has("shot"):
			get_viewport().get_texture().get_image().save_png(_args["shot"])
		get_tree().quit()


func _parse_args() -> void:
	for arg in OS.get_cmdline_user_args():
		if not arg.begins_with("--"):
			continue
		if arg.contains("="):
			_args[arg.substr(2, arg.find("=") - 2)] = arg.substr(arg.find("=") + 1)
		else:
			_flags.append(arg.substr(2))


func _make_camera(def: ArenaDefinition) -> BattleCamera:
	var cam := BattleCamera.new()
	add_child(cam)
	cam.make_current()
	cam.setup(def.size)
	if _args.has("insets"):
		var parts: PackedStringArray = String(_args["insets"]).split(",")
		cam.set_side_insets(float(parts[0]), float(parts[1]) if parts.size() > 1 else 0.0)
	return cam


func _spawn_kith(def: ArenaDefinition) -> void:
	var kith := [["res://assets/sprites/kith/emberlyn.json", def.spawn_team0 + Vector2(1.0, 0.0), "e"], ["res://assets/sprites/kith/stoneback.json", def.spawn_team1 + Vector2(-1.0, -1.0), "w"]]
	for data in kith:
		var p: Vector2 = data[1]
		var s := PixelSprite3D.new()
		s.load_manifest(data[0])
		s.position = Vector3(p.x, 0, p.y)
		s.set_param("emission_strength", 1.8)
		s.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(s)
		s.play("idle", data[2])
		EnvKit.blob_shadow(self, 0.55, 0.5).position = s.position + Vector3(0, 0.015, 0)


func _spawn_trainers(builder: ArenaBuilder, def: ArenaDefinition) -> void:
	var trainers := ["explorer", "corin" if def.crowd else "hesper"]
	for team in 2:
		var t := PixelSprite3D.new()
		t.load_manifest("res://assets/sprites/characters/%s.json" % trainers[team])
		t.position = builder.trainer_spots[team]
		add_child(t)
		t.play("idle", "e" if team == 0 else "w")
		EnvKit.blob_shadow(self, 0.35, 0.4).position = builder.trainer_spots[team] + Vector3(0, 0.015, 0)


func _print_stats() -> void:
	var rs := RenderingServer
	var vp := get_viewport()
	for t: Array in [["visible", Viewport.RENDER_INFO_TYPE_VISIBLE], ["shadow", Viewport.RENDER_INFO_TYPE_SHADOW], ["canvas", Viewport.RENDER_INFO_TYPE_CANVAS]]:
		print("%s pass: %d draw calls, %d objects, %d primitives" % [t[0], vp.get_render_info(t[1], Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME), vp.get_render_info(t[1], Viewport.RENDER_INFO_OBJECTS_IN_FRAME), vp.get_render_info(t[1], Viewport.RENDER_INFO_PRIMITIVES_IN_FRAME)])
	var lights := 0
	for n in find_children("*", "OmniLight3D", true, false):
		lights += 1
	print("omni lights: ", lights)
	print("draw calls: ", rs.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME))
	print("objects: ", rs.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME))
	print("primitives: ", rs.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME))
	print("nodes: ", get_tree().get_node_count())
	print("video mem: ", rs.get_rendering_info(RenderingServer.RENDERING_INFO_VIDEO_MEM_USED) / 1048576, " MB")


func _add_guides(cam: BattleCamera) -> void:
	var layer := CanvasLayer.new()
	layer.layer = 5
	add_child(layer)
	var vis := get_viewport().get_visible_rect().size
	var ins := cam.side_insets
	for r: Rect2 in [Rect2(0, 0, vis.x, BattleCamera.HUD_TOP), Rect2(0, vis.y - BattleCamera.HUD_BOTTOM, vis.x, BattleCamera.HUD_BOTTOM), Rect2(0, 0, ins.x, vis.y), Rect2(vis.x - ins.y, 0, ins.y, vis.y)]:
		_rect(layer, r, Color(0.1, 0.4, 1.0, 0.18))
	var br := cam.board_screen_rect()
	var board := ReferenceRect.new()
	board.border_color = Color(1.0, 0.2, 0.6)
	board.border_width = 2.0
	board.editor_only = false
	board.position = br.position
	board.size = br.size
	layer.add_child(board)
	# a 1px guide on every cell boundary, projected through the real camera:
	# it must sit on the joints between the flagstones
	var lines := Line2DLayer.new()
	var h := cam.arena_size * 0.5
	for i in range(0, int(cam.arena_size.x) + 1):
		var x := -h.x + i
		lines.segments.append([cam.rest_unproject(Vector3(x, 0, -h.y)), cam.rest_unproject(Vector3(x, 0, h.y))])
	for j in range(0, int(cam.arena_size.y) + 1):
		var z := -h.y + j
		lines.segments.append([cam.rest_unproject(Vector3(-h.x, 0, z)), cam.rest_unproject(Vector3(h.x, 0, z))])
	layer.add_child(lines)


## Draws the projected cell boundaries as 1 px lines.
class Line2DLayer:
	extends Control
	var segments: Array = []

	func _ready() -> void:
		set_anchors_preset(Control.PRESET_FULL_RECT)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		for s in segments:
			draw_line(s[0], s[1], Color(0.0, 1.0, 1.0, 0.8), 1.0)


func _rect(layer: CanvasLayer, r: Rect2, color: Color) -> void:
	var c := ColorRect.new()
	c.color = color
	c.position = r.position
	c.size = r.size
	layer.add_child(c)
