extends Node3D
## Dev scene: renders the battle arena with both kith for visual checks.
## Run with --shot=<path> to save a screenshot and quit.

func _ready() -> void:
	var rig := LightingRig.new()
	add_child(rig)
	rig.apply(&"golden")
	var builder := ArenaBuilder.new()
	builder.build(self, ArenaDefinition.ringstones())
	var cam := BattleCamera.new()
	add_child(cam)
	cam.make_current()
	cam.setup(Vector2(14, 9))
	add_child(PostFX.new())
	for data in [["res://assets/sprites/kith/emberlyn.json", Vector3(-3, 0, 0.5), "e"], ["res://assets/sprites/kith/stoneback.json", Vector3(3, 0, -0.5), "w"]]:
		var s := PixelSprite3D.new()
		s.load_manifest(data[0])
		s.position = data[1]
		s.set_param("emission_strength", 1.6)
		s.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(s)
		s.play("idle", data[2])
		EnvKit.blob_shadow(self, 0.55).position = data[1] + Vector3(0, 0.015, 0)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--shot="):
			for i in 12:
				await get_tree().process_frame
			get_viewport().get_texture().get_image().save_png(arg.substr(7))
			get_tree().quit()
