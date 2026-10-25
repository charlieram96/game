extends WBTestCase
## The HD-2D arena keeps the board honest: flagstones stay under the lanes
## and telegraphs drawn on the floor, the joints between them sit on the
## cell lines, nothing but the standing stones rises inside the board, and
## the static scene stays merged into a small number of draw calls.

const DASH_LANE_Y := 0.026  # DashLane.HEIGHT
## Upper bound on renderable nodes the arena adds (each is about one draw call).
const MAX_RENDERABLES := 72


func _build(def: ArenaDefinition) -> Array:
	var host := Node3D.new()
	(Engine.get_main_loop() as SceneTree).root.add_child(host)
	var b := ArenaBuilder.new()
	var arena := b.build(host, def)
	return [host, b, arena]


func _board_mesh(arena: Node3D) -> Mesh:
	var mi := arena.get_node_or_null("Board") as MeshInstance3D
	return mi.mesh if mi else null


func test_flagstones_stay_under_the_floor_markings_and_on_the_grid() -> void:
	for def: ArenaDefinition in [ArenaDefinition.ringstones(), ArenaDefinition.training_yard()]:
		var built := _build(def)
		var mesh := _board_mesh(built[2])
		assert_true(mesh != null, "%s: the board mesh exists" % def.id)
		if mesh == null:
			(built[0] as Node).queue_free()
			continue
		var arrays := mesh.surface_get_arrays(0)
		var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
		var bounds := def.bounds()
		var highest := -INF
		var off_grid := 0
		for i in verts.size():
			var v := verts[i]
			highest = maxf(highest, v.y)
			# the top faces of the cells' stones (or earth pads): never on a cell line
			var inside := v.x > bounds.position.x + 0.01 and v.x < bounds.end.x - 0.01 and v.z > bounds.position.y + 0.01 and v.z < bounds.end.y - 0.01
			if inside and normals[i].y > 0.999 and v.y > -0.02:
				var fx := v.x - bounds.position.x
				var fz := v.z - bounds.position.y
				var dx := absf(fx - roundf(fx))
				var dz := absf(fz - roundf(fz))
				# a joint (and the bevel's lip) separates every face from the line
				if (dx < ArenaBuilder.JOINT + 0.012 or dz < ArenaBuilder.JOINT + 0.012) and def.floor_style != &"dirt":
					off_grid += 1
		assert_lt(highest, DASH_LANE_Y - 0.015, "%s: the board stays under the dash lanes (top %.4f)" % [def.id, highest])
		assert_le(highest, ArenaBuilder.TILE_TOP_MAX + 0.0005, "%s: no stone above the allowed top" % def.id)
		assert_eq(off_grid, 0, "%s: no flagstone face crosses a cell line" % def.id)
		(built[0] as Node).queue_free()
	await (Engine.get_main_loop() as SceneTree).process_frame


func test_nothing_but_the_standing_stones_rises_inside_the_board() -> void:
	for def: ArenaDefinition in [ArenaDefinition.ringstones(), ArenaDefinition.training_yard()]:
		var built := _build(def)
		var arena: Node3D = built[2]
		var bounds := def.bounds()
		var intruders: Array[String] = []
		for n in arena.find_children("*", "MeshInstance3D", true, false):
			var mi := n as MeshInstance3D
			if mi.name == "Board" or mi.name == "DepthOfField" or mi.mesh == null:
				continue
			for s in mi.mesh.get_surface_count():
				var verts: PackedVector3Array = mi.mesh.surface_get_arrays(s)[Mesh.ARRAY_VERTEX]
				for v0 in verts:
					var v: Vector3 = mi.global_transform * v0
					if v.y < 0.01:
						continue
					if v.x <= bounds.position.x or v.x >= bounds.end.x or v.z <= bounds.position.y or v.z >= bounds.end.y:
						continue
					var on_stone := false
					for c in def.circles:
						if Vector2(v.x, v.z).distance_to(Vector2(c.x, c.y)) <= c.z + 0.01:
							on_stone = true
					if not on_stone:
						intruders.append("%s at %s" % [mi.name, v])
						break
		assert_eq(intruders.size(), 0, "%s: only the standing stones stand on the board: %s" % [def.id, intruders.slice(0, 3)])
		(built[0] as Node).queue_free()
	await (Engine.get_main_loop() as SceneTree).process_frame


func test_static_geometry_is_merged() -> void:
	for def: ArenaDefinition in [ArenaDefinition.ringstones(), ArenaDefinition.training_yard()]:
		var built := _build(def)
		var arena: Node3D = built[2]
		var renderables := 0
		for n in arena.find_children("*", "GeometryInstance3D", true, false):
			renderables += 1
		assert_le(float(renderables), float(MAX_RENDERABLES), "%s: %d renderable nodes" % [def.id, renderables])
		assert_gt(float(renderables), 10.0, "%s: the arena was built" % def.id)
		(built[0] as Node).queue_free()
	await (Engine.get_main_loop() as SceneTree).process_frame


func test_cell_highlights_and_trainer_spots() -> void:
	var built := _build(ArenaDefinition.ringstones())
	var b: ArenaBuilder = built[1]
	b.set_cell_highlight(Vector2i(3, 4), 1.0)
	assert_near(b.cell_image.get_pixel(3, 4).a, 1.0, 0.01, "highlight stored for the floor shader")
	b.set_cell_highlight(Vector2i(3, 4), 0.0)
	assert_near(b.cell_image.get_pixel(3, 4).a, 0.0, 0.01, "highlight cleared")
	b.set_cell_highlight(Vector2i(99, 99), 1.0)  # off the board: ignored
	assert_eq(b.trainer_spots.size(), 2, "two trainer spots")
	for p in b.trainer_spots:
		assert_gt(absf(p.x), ArenaDefinition.ringstones().size.x * 0.5 + 0.5, "trainers stand beside the board, off its cells")
	b.cheer(0.5)
	(built[0] as Node).queue_free()
	await (Engine.get_main_loop() as SceneTree).process_frame
