extends WBTestCase
## Spec test 20: the battle HUD and touch controls fit and stay usable at
## 16:9 and taller/wider landscape aspect ratios (canvas units after
## stretch), with touch targets of at least 64 px and no overlaps.

const H := preload("res://tests/sim_helpers.gd")
const SIZES := [Vector2(1280, 720), Vector2(1560, 720), Vector2(1600, 720), Vector2(1280, 800), Vector2(1280, 960)]


func test_hud_layout_at_aspect_ratios() -> void:
	for size in SIZES:
		var host := Control.new()
		host.size = size
		var layer := CanvasLayer.new()
		Engine.get_main_loop().root.add_child(layer)
		layer.add_child(host)
		var sim := H.make_sim()
		var hud := BattleHUD.new()
		layer.add_child(hud)
		hud.build(sim, 0, BattleSetup.new(), host)
		hud.refresh(0.016)
		await Engine.get_main_loop().process_frame
		await Engine.get_main_loop().process_frame
		var bounds := Rect2(Vector2.ZERO, size)
		var rects := hud.layout_rects()
		for key in rects.keys():
			var r: Rect2 = rects[key]
			assert_true(bounds.encloses(r), "%s inside %s (got %s)" % [key, size, r])
		var keys := rects.keys()
		for i in keys.size():
			for j in range(i + 1, keys.size()):
				var a: Rect2 = rects[keys[i]]
				var b: Rect2 = rects[keys[j]]
				assert_false(a.intersects(b), "%s overlaps %s at %s" % [keys[i], keys[j], size])
		layer.queue_free()


func test_touch_controls_fit_and_are_large_enough() -> void:
	for size in SIZES:
		var host := Control.new()
		host.size = size
		var layer := CanvasLayer.new()
		Engine.get_main_loop().root.add_child(layer)
		layer.add_child(host)
		var sim := H.make_sim()
		var touch := TouchControls.new()
		host.add_child(touch)
		touch.setup(sim, 0)
		await Engine.get_main_loop().process_frame
		var bounds := Rect2(Vector2.ZERO, size)
		var rects: Array[Rect2] = []
		for b in touch.buttons:
			var r := touch.button_rect(b)
			assert_true(bounds.encloses(r), "%s inside at %s" % [b.name, size])
			assert_ge(r.size.x, TouchControls.MIN_BUTTON, "%s >= 64px" % b.name)
			rects.append(r)
		for i in rects.size():
			for j in range(i + 1, rects.size()):
				var ci := rects[i].get_center()
				var cj := rects[j].get_center()
				var min_gap := rects[i].size.x * 0.5 + rects[j].size.x * 0.5
				assert_ge(ci.distance_to(cj), min_gap - 0.5, "buttons %d/%d don't overlap at %s" % [i, j, size])
		var joy := Rect2(Vector2(150, size.y - 150) - Vector2(90, 90), Vector2(180, 180))
		for r in rects:
			assert_false(joy.intersects(r), "joystick zone clear of buttons at %s" % size)
		layer.queue_free()
