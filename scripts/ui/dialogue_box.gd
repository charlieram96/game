class_name DialogueBox
extends CanvasLayer
## Story dialogue: typewriter text with voice blips, speaker name plate,
## pixel portraits, inline choices. Usage:  var choice := await box.play("id")

signal line_advanced
signal finished(choice_id: String)

const DATA_PATH := "res://resources/dialogue/chapter1.json"
const CHARS_PER_SEC := 48.0

static var _data: Dictionary = {}

var active := false
var panel: PanelContainer
var name_plate: Label
var text_label: RichTextLabel
var portrait: TextureRect
var choices_box: VBoxContainer
var arrow: Label
var _visible_chars := 0.0
var _typing := false
var _choice_result := ""
var _waiting_choice := false
var _blip_counter := 0
var _portrait_cache: Dictionary = {}


static func data() -> Dictionary:
	if _data.is_empty():
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(DATA_PATH))
		_data = parsed if parsed is Dictionary else {}
	return _data


static func has_dialogue(id: String) -> bool:
	return data().has(id)


func _ready() -> void:
	layer = 30
	process_mode = Node.PROCESS_MODE_ALWAYS
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.theme = UiTheme.get_theme()
	add_child(root)
	panel = PanelContainer.new()
	panel.add_theme_stylebox_override("panel", UiTheme.parchment_box())
	panel.anchor_left = 0.5
	panel.anchor_right = 0.5
	panel.anchor_top = 1.0
	panel.anchor_bottom = 1.0
	panel.offset_left = -470
	panel.offset_right = 470
	panel.offset_top = -214
	panel.offset_bottom = -22
	panel.gui_input.connect(_on_panel_input)
	root.add_child(panel)
	var hb := HBoxContainer.new()
	hb.add_theme_constant_override("separation", 16)
	panel.add_child(hb)
	portrait = TextureRect.new()
	portrait.custom_minimum_size = Vector2(128, 128)
	portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	portrait.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	portrait.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hb.add_child(portrait)
	var vb := VBoxContainer.new()
	vb.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vb.add_theme_constant_override("separation", 6)
	hb.add_child(vb)
	name_plate = UiTheme.label("", 24, Color(0.42, 0.22, 0.12), true, 0)
	vb.add_child(name_plate)
	text_label = RichTextLabel.new()
	text_label.bbcode_enabled = true
	text_label.fit_content = true
	text_label.scroll_active = false
	text_label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	text_label.add_theme_font_override("normal_font", UiTheme.FONT_REGULAR)
	text_label.add_theme_font_override("bold_font", UiTheme.FONT_BOLD)
	text_label.add_theme_font_size_override("normal_font_size", 24)
	text_label.add_theme_font_size_override("bold_font_size", 24)
	text_label.add_theme_color_override("default_color", Color(0.17, 0.11, 0.08))
	text_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vb.add_child(text_label)
	choices_box = VBoxContainer.new()
	choices_box.add_theme_constant_override("separation", 6)
	vb.add_child(choices_box)
	arrow = UiTheme.label("▼", 20, Color(0.42, 0.22, 0.12), true, 0)
	arrow.anchor_left = 1.0
	arrow.anchor_right = 1.0
	arrow.anchor_top = 1.0
	arrow.anchor_bottom = 1.0
	arrow.offset_left = -44
	arrow.offset_top = -40
	panel.add_child(arrow)
	visible = false


## Plays a dialogue by id; returns the id of the chosen option (or "").
func play(id: String) -> String:
	var lines: Array = data().get(id, [])
	if lines.is_empty():
		push_warning("Missing dialogue: %s" % id)
		return ""
	return await play_lines(lines)


func play_lines(lines: Array) -> String:
	active = true
	visible = true
	Events.dialogue_started.emit("")
	var result := ""
	for line in lines:
		var r := await _show_line(line)
		if r != "":
			result = r
	visible = false
	active = false
	Events.dialogue_finished.emit("")
	finished.emit(result)
	return result


func _show_line(line: Dictionary) -> String:
	var speaker := str(line.get("speaker", ""))
	name_plate.text = speaker
	name_plate.visible = speaker != ""
	_set_portrait(str(line.get("portrait", "")))
	var text := str(line.get("text", "")).replace("{player}", _player_name())
	if speaker == "":
		text = "[i]" + text + "[/i]" if not text.begins_with("[") else text
	text_label.text = text
	text_label.visible_characters = 0
	_visible_chars = 0.0
	_typing = true
	arrow.visible = false
	for c in choices_box.get_children():
		c.queue_free()
	await line_advanced
	var choices: Array = line.get("choices", [])
	if choices.is_empty():
		return ""
	# Show options
	_waiting_choice = true
	_choice_result = ""
	arrow.visible = false
	var first: Button = null
	for i in choices.size():
		var ch: Dictionary = choices[i]
		var b := Button.new()
		b.text = "%d. %s" % [i + 1, str(ch.get("text", ""))]
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.custom_minimum_size = Vector2(0, 44)
		b.pressed.connect(_pick.bind(i))
		choices_box.add_child(b)
		if first == null:
			first = b
	if first:
		first.grab_focus()
	while _waiting_choice:
		await get_tree().process_frame
	var chosen: Dictionary = choices[int(_choice_result)]
	for c in choices_box.get_children():
		c.queue_free()
	var reply: Array = chosen.get("reply", [])
	for r in reply:
		await _show_line(r)
	return str(chosen.get("id", str(_choice_result)))


func _pick(i: int) -> void:
	Audio.sfx(&"ui_select")
	_choice_result = str(i)
	_waiting_choice = false


func _process(delta: float) -> void:
	if Game.autoplay and active:
		if _waiting_choice:
			_pick(0)
		else:
			_advance()
		return
	if not active or not _typing:
		return
	var total := text_label.get_total_character_count()
	_visible_chars += delta * CHARS_PER_SEC
	var shown := int(_visible_chars)
	if shown != text_label.visible_characters:
		text_label.visible_characters = shown
		_blip_counter += 1
		if _blip_counter % 3 == 0 and name_plate.visible:
			Audio.sfx(&"dialogue_blip", -10.0, 0.06, 40)
	if shown >= total:
		_typing = false
		text_label.visible_characters = -1
		arrow.visible = true


func _unhandled_input(event: InputEvent) -> void:
	if not active or _waiting_choice:
		return
	var advance := event.is_action_pressed(&"advance") or event.is_action_pressed(&"interact")
	if event is InputEventScreenTouch and event.pressed:
		advance = true
	if advance:
		get_viewport().set_input_as_handled()
		_advance()


func _on_panel_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT and not _waiting_choice:
		_advance()


func _advance() -> void:
	if _typing:
		_typing = false
		text_label.visible_characters = -1
		arrow.visible = true
		return
	Audio.sfx(&"ui_move", -8.0)
	line_advanced.emit()


func _set_portrait(spec: String) -> void:
	if spec == "":
		portrait.visible = false
		return
	var parts := spec.split(":")
	var who := parts[0]
	var expr := parts[1] if parts.size() > 1 else "neutral"
	var key := spec
	if not _portrait_cache.has(key):
		var sheet := SpriteSheet.load_sheet("res://assets/sprites/portraits/portrait_%s.json" % who)
		var tex: Texture2D = null
		if sheet.valid:
			var anim: String = sheet.resolve(expr, "s")[0]
			if anim == "":
				anim = sheet.animations.keys()[0]
			var frame: int = sheet.frames_of(anim)[0]
			var at := AtlasTexture.new()
			at.atlas = sheet.texture
			var col := frame % sheet.columns
			var row := frame / sheet.columns
			at.region = Rect2(Vector2(col, row) * sheet.frame_size, sheet.frame_size)
			tex = at
		_portrait_cache[key] = tex
	portrait.texture = _portrait_cache[key]
	portrait.visible = portrait.texture != null


func _player_name() -> String:
	return SaveService.profile.player_name if SaveService.profile else "Wren"
