class_name BattleResults
extends CanvasLayer
## Post-battle summary: outcome, combat stats, experience and mastery gains,
## Rematch / Continue.

signal rematch
signal continue_pressed

var panel: PanelContainer
var title: Label
var subtitle: Label
var stats_grid: GridContainer
var progress_box: VBoxContainer
var rematch_button: Button
var continue_button: Button


func _ready() -> void:
	layer = 40
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.theme = UiTheme.get_theme()
	add_child(root)
	var dim := ColorRect.new()
	dim.color = Color(0.03, 0.02, 0.05, 0.55)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(center)
	panel = PanelContainer.new()
	panel.custom_minimum_size = Vector2(560, 0)
	center.add_child(panel)
	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 10)
	panel.add_child(vb)
	title = UiTheme.label("VICTORY!", 56, UiTheme.GOLD, true, 12)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vb.add_child(title)
	subtitle = UiTheme.label("", 20, UiTheme.PARCHMENT)
	subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vb.add_child(subtitle)
	stats_grid = GridContainer.new()
	stats_grid.columns = 2
	stats_grid.add_theme_constant_override("h_separation", 40)
	stats_grid.add_theme_constant_override("v_separation", 4)
	vb.add_child(stats_grid)
	progress_box = VBoxContainer.new()
	vb.add_child(progress_box)
	var hb := HBoxContainer.new()
	hb.alignment = BoxContainer.ALIGNMENT_CENTER
	hb.add_theme_constant_override("separation", 16)
	vb.add_child(hb)
	rematch_button = Button.new()
	rematch_button.text = "Rematch"
	rematch_button.custom_minimum_size = Vector2(180, 56)
	rematch_button.pressed.connect(func() -> void:
		Audio.sfx(&"ui_select")
		rematch.emit())
	hb.add_child(rematch_button)
	continue_button = Button.new()
	continue_button.text = "Continue"
	continue_button.custom_minimum_size = Vector2(180, 56)
	continue_button.pressed.connect(func() -> void:
		Audio.sfx(&"ui_select")
		continue_pressed.emit())
	hb.add_child(continue_button)


func show_results(result: Dictionary, setup: BattleSetup) -> void:
	var w := int(result.get("winner", -1))
	var local := int(result.get("local_team", 0))
	if w == -2:
		title.text = "DRAW"
		title.add_theme_color_override("font_color", UiTheme.PARCHMENT)
	elif setup.mode == BattleSetup.Mode.VERSUS:
		title.text = "PLAYER %d WINS" % (w + 1)
		title.add_theme_color_override("font_color", UiTheme.GOLD)
	elif w == local:
		title.text = "VICTORY!"
		title.add_theme_color_override("font_color", UiTheme.GOLD)
	else:
		title.text = "DEFEAT"
		title.add_theme_color_override("font_color", Color(0.75, 0.8, 0.95))
	var reason: StringName = result.get("reason", &"")
	subtitle.text = "Knockout" if reason == &"ko" else ("Time up — decided on remaining health" if reason == &"timeout" else "")
	if setup.mode == BattleSetup.Mode.STORY and w != local:
		subtitle.text = "Tip: ram Stoneback (dash THROUGH it, away from its guard): every ram earns over a stage of Surge for your specials."
	for c in stats_grid.get_children():
		c.queue_free()
	var rec: Dictionary = result.get("record", {})
	var rows := [
		["Damage dealt", str(int(round(float(rec.get("damage_dealt", 0.0)))))],
		["Hits landed", str(int(rec.get("hits", 0)))],
		["Rams", str(int(rec.get("dash_throughs", 0)))],
		["Surge spent", "%d stages" % int(rec.get("surge_spent", 0))],
		["Perfect guards", str(int(rec.get("perfect_guards", 0)))],
		["Blocks", str(int(rec.get("blocks", 0)))],
		["Battle time", "%.1f s" % float(result.get("duration_sec", 0.0))],
	]
	for r in rows:
		stats_grid.add_child(UiTheme.label(r[0], 20, Color(0.85, 0.8, 0.68)))
		var v := UiTheme.label(r[1], 20, UiTheme.PARCHMENT, true)
		v.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		stats_grid.add_child(v)
	for c in progress_box.get_children():
		c.queue_free()
	var prog: Dictionary = result.get("progress", {})
	if prog.has("xp"):
		progress_box.add_child(UiTheme.label("%s gained %d XP" % [prog.get("name", "Your kith"), int(prog["xp"])], 20, Color(0.75, 0.95, 0.75), true))
		for lv in prog.get("levels", []):
			progress_box.add_child(UiTheme.label("Level up! Now Lv.%d" % int(lv), 20, UiTheme.GOLD, true))
	for ability_id in (prog.get("mastery", {}) as Dictionary).keys():
		var levels: Array = prog["mastery"][ability_id]
		progress_box.add_child(UiTheme.label("%s mastery %d" % [String(ability_id).capitalize(), int(levels[-1])], 18, Color(0.7, 0.9, 1.0)))
	var story := setup.mode == BattleSetup.Mode.STORY
	continue_button.text = "Continue" if (story and w == local) or not story else "Back"
	rematch_button.text = "Try again" if story and w != local else "Rematch"
	visible = true
	(rematch_button if story and w != local else continue_button).grab_focus()


func hide_results() -> void:
	visible = false
