extends WBTestCase
## The perspective battle camera: drag-to-dash depends on ground_point() being
## the exact inverse of the projection at the rest pose, and the board must
## fill the screen between the HUD bands at every supported aspect ratio
## while staying clear of the touch buttons.

const BOARD := Vector2(20, 12)
## Canvas sizes after stretch: 16:9 (1280x720, 1920x1080), wide phones
## (844x390 -> 1558x720, 1600x720), 16:10 and 4:3 tablets.
const CANVASES := [Vector2(1280, 720), Vector2(1558, 720), Vector2(1600, 720), Vector2(1280, 800), Vector2(1280, 960)]
const TOUCH_INSET := 300.0


func _corners() -> Array[Vector3]:
	var h := BOARD * 0.5
	return [Vector3(-h.x, 0, -h.y), Vector3(h.x, 0, -h.y), Vector3(-h.x, 0, h.y), Vector3(h.x, 0, h.y)]


func test_ground_point_inverts_the_projection_at_every_corner() -> void:
	var tree := Engine.get_main_loop() as SceneTree
	var cam := BattleCamera.new()
	tree.root.add_child(cam)
	cam.setup(BOARD)
	cam.make_current()
	await tree.process_frame
	var points: Array[Vector3] = _corners()
	points.append_array([Vector3.ZERO, Vector3(-7.5, 0, -0.5), Vector3(7.5, 0, 0.5), Vector3(9.5, 0, 5.5), Vector3(-9.5, 0, -5.5)])
	for p in points:
		var sp := cam.unproject_position(p)
		var g := cam.ground_point(sp)
		assert_lt(g.distance_to(p), 0.002, "ground_point(unproject(%s)) = %s" % [p, g])
		assert_lt(cam.rest_unproject(p).distance_to(sp), 0.05, "static projection matches the engine's at %s" % p)
	# Shake, kicks and zoom punches never move the aimed cell.
	var sp0 := cam.unproject_position(Vector3(3.5, 0, 2.5))
	cam.add_trauma(1.0)
	cam.kick(Vector2.RIGHT, 0.2)
	cam.zoom_punch(0.06)
	await tree.process_frame
	assert_lt(cam.ground_point(sp0).distance_to(Vector3(3.5, 0, 2.5)), 0.002, "aim uses the rest pose")
	cam.queue_free()
	await tree.process_frame


func test_board_fills_the_free_band_at_every_aspect() -> void:
	for vis: Vector2 in CANVASES:
		for touch in [false, true]:
			var insets := Vector2(0.0, TOUCH_INSET if touch else 0.0)
			var xf := BattleCamera.compute_rest(BOARD, vis, insets)
			var r := Rect2(BattleCamera.project(xf, BattleCamera.FOV_DEG, vis, _corners()[0]), Vector2.ZERO)
			for c in _corners():
				r = r.expand(BattleCamera.project(xf, BattleCamera.FOV_DEG, vis, c))
			var label := "%s%s" % [vis, " touch" if touch else ""]
			assert_ge(r.position.y, BattleCamera.HUD_TOP, "%s: back edge below the top bar (%s)" % [label, r])
			assert_le(r.end.y, vis.y - BattleCamera.HUD_BOTTOM, "%s: front edge above the ability bar (%s)" % [label, r])
			assert_ge(r.position.x, insets.x, "%s: left edge on screen (%s)" % [label, r])
			assert_le(r.end.x, vis.x - insets.y, "%s: clear of the right inset (%s)" % [label, r])
			# As large as it can be: tight against the bands or the sides.
			var free := Vector2(vis.x - insets.x - insets.y, vis.y - BattleCamera.HUD_TOP - BattleCamera.HUD_BOTTOM)
			var fill := maxf(r.size.x / free.x, r.size.y / free.y)
			assert_gt(fill, 0.95, "%s: the board fills the free area (%.3f)" % [label, fill])
			# Centred on the screen when nothing pushes it aside.
			if not touch:
				assert_near(r.get_center().x, vis.x * 0.5, 1.0, "%s: centred" % label)
			# The back edge really is narrower: perspective, not a flat board.
			var back := BattleCamera.project(xf, BattleCamera.FOV_DEG, vis, _corners()[1]).x - BattleCamera.project(xf, BattleCamera.FOV_DEG, vis, _corners()[0]).x
			var front := BattleCamera.project(xf, BattleCamera.FOV_DEG, vis, _corners()[3]).x - BattleCamera.project(xf, BattleCamera.FOV_DEG, vis, _corners()[2]).x
			assert_lt(back / front, 0.92, "%s: perspective (back/front = %.3f)" % [label, back / front])


func test_ground_point_round_trip_for_any_canvas() -> void:
	for vis: Vector2 in CANVASES:
		var xf := BattleCamera.compute_rest(BOARD, vis, Vector2(0, TOUCH_INSET))
		for c in _corners():
			var sp := BattleCamera.project(xf, BattleCamera.FOV_DEG, vis, c)
			var g := BattleCamera.ground_point_for(xf, vis, sp)
			assert_lt(g.distance_to(c), 0.002, "%s corner %s -> %s" % [vis, c, g])
