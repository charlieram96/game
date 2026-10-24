extends Node
## Entry point: settings and services are autoloads; go to the title screen
## (or straight into a dev battle with `-- --battle`).

func _ready() -> void:
	await get_tree().process_frame
	for arg in OS.get_cmdline_user_args():
		if arg == "--battle":
			Game.start_battle(Game.quick_battle_setup(&"emberlyn", &"stoneback", Settings.ai_difficulty))
			return
	if ResourceLoader.exists(Game.TITLE_SCENE):
		Game.goto_scene(Game.TITLE_SCENE, 0.2)
	else:
		Game.start_battle(Game.quick_battle_setup(&"emberlyn", &"stoneback", Settings.ai_difficulty))
