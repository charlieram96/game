class_name JournalScreen
extends CanvasLayer
## The Field Journal: every kith the player has seen, observed or befriended,
## with notes, habitat and — for companions — level and mastered abilities.

const ORDER := [&"emberlyn", &"stoneback", &"mossling", &"lanternmoth"]

var _root: Control


func _ready() -> void:
	layer = 45
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false


func open() -> void:
	_build()
	visible = true
	get_tree().paused = true
	Audio.sfx(&"ui_select")


func close() -> void:
	visible = false
	get_tree().paused = false
	Audio.sfx(&"ui_back")


func _unhandled_input(event: InputEvent) -> void:
	if visible and (event.is_action_pressed(&"journal") or event.is_action_pressed(&"pause")):
		get_viewport().set_input_as_handled()
		close()


func _build() -> void:
	if _root:
		_root.queue_free()
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.theme = UiTheme.get_theme()
	add_child(_root)
	var dim := ColorRect.new()
	dim.color = Color(0.03, 0.02, 0.05, 0.7)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(center)
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", UiTheme.parchment_box())
	panel.custom_minimum_size = Vector2(900, 520)
	center.add_child(panel)
	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 10)
	panel.add_child(vb)
	var title := UiTheme.label("Field Journal", 36, Color(0.35, 0.2, 0.1), true, 0)
	vb.add_child(title)
	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 24)
	grid.add_theme_constant_override("v_separation", 14)
	vb.add_child(grid)
	var profile := SaveService.profile
	for sid in ORDER:
		var def := Registry.get_species(sid)
		if def == null:
			continue
		var entry: Dictionary = profile.journal.get(String(sid), {}) if profile else {}
		grid.add_child(_entry(def, entry, profile))
	var close_b := Button.new()
	close_b.text = "Close"
	close_b.custom_minimum_size = Vector2(160, 48)
	close_b.pressed.connect(close)
	vb.add_child(close_b)
	close_b.grab_focus()


func _entry(def: CreatureDefinition, entry: Dictionary, profile: PlayerProfile) -> Control:
	var hb := HBoxContainer.new()
	hb.custom_minimum_size = Vector2(420, 150)
	hb.add_theme_constant_override("separation", 12)
	var seen := bool(entry.get("seen", false))
	var icon := TextureRect.new()
	icon.custom_minimum_size = Vector2(96, 96)
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	icon.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	var sheet := SpriteSheet.load_sheet(def.sprite_manifest)
	if sheet.valid:
		var anim: String = sheet.resolve("idle", "s")[0]
		if anim == "":
			anim = sheet.resolve("hover", "s")[0]
		if anim != "":
			var frame: int = sheet.frames_of(anim)[0]
			var at := AtlasTexture.new()
			at.atlas = sheet.texture
			at.region = Rect2(Vector2(frame % sheet.columns, frame / sheet.columns) * sheet.frame_size, sheet.frame_size)
			icon.texture = at
	icon.modulate = Color.WHITE if seen else Color(0, 0, 0, 0.55)
	hb.add_child(icon)
	var vb := VBoxContainer.new()
	vb.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hb.add_child(vb)
	var dark := Color(0.2, 0.13, 0.08)
	var name_text := def.display_name if seen else "???"
	vb.add_child(UiTheme.label(name_text, 24, dark, true, 0))
	if seen:
		var status := "Befriended" if bool(entry.get("befriended", false)) else ("Observed" if bool(entry.get("observed", false)) else "Seen")
		vb.add_child(UiTheme.label("%s · %s · %s" % [ElementChart.get_default().display_names.get(String(def.element), String(def.element)), def.archetype, status], 16, Color(0.45, 0.3, 0.18), false, 0))
		var body := Label.new()
		body.text = def.journal_entry if (bool(entry.get("observed", false)) or bool(entry.get("befriended", false))) else def.description
		body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		body.custom_minimum_size = Vector2(300, 0)
		body.add_theme_font_size_override("font_size", 15)
		body.add_theme_color_override("font_color", dark)
		vb.add_child(body)
		if profile:
			for c in profile.party:
				if c.species_id == def.id:
					vb.add_child(UiTheme.label("%s · Lv.%d" % [c.display_name(def), c.level], 16, Color(0.6, 0.25, 0.1), true, 0))
	else:
		vb.add_child(UiTheme.label("Not yet encountered.", 16, Color(0.45, 0.3, 0.18), false, 0))
	return hb
