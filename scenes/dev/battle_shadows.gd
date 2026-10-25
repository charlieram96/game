extends Node
## Dev scene: the battle scene with fighters casting real shadows, i.e. what the
## proposed fighter_view.gd change does (sprite.cast_shadow ON, a lighter blob
## shadow), applied at runtime so it can be reviewed before that file changes.
## Takes the battle scene's own arguments (--shot, --demo, --seq, --aim, --training).
##
##   --blob=<opacity>   blob shadow opacity under each fighter (default 0.3)


func _ready() -> void:
	var battle: Node = load("res://scenes/combat/battle.tscn").instantiate()
	add_child(battle)
	var blob := 0.3
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--blob="):
			blob = float(arg.substr(7))
	await get_tree().process_frame
	for v: Node in battle.find_children("*", "FighterView", true, false):
		var view := v as FighterView
		view.sprite.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		(view.shadow.material_override as ShaderMaterial).set_shader_parameter("opacity", blob)
