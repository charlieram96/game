class_name PauseMenu
extends CanvasLayer
## Pause overlay: resume, controls reference, settings, quit.

signal resumed
signal quit_requested

const CONTROLS_TEXT := """[b]Battle[/b]
WASD — move (8 directions)      Mouse — aim
Left click — basic attack (press again to chain)
Right click — dash (always N/S/E/W; dash THROUGH a foe to daze it)
Shift (hold) — Focus: recover stamina (you're rooted while focusing)
Q / E / R / F — special abilities      Space (hold) — guard (tap just before a hit for a Perfect Guard)
F3 — show hitboxes and logical cells

[b]Exploring[/b]
WASD — walk      Shift — sneak (wild kith notice running)
E / Enter — talk, inspect      J / Tab — field journal

[b]Gamepad[/b]  L-stick move · R-stick aim · RT attack · RB dash · LT focus · LB guard · A/B/X/Y specials
[b]Touch[/b]  Left thumb moves · tap an ability to auto-aim, or drag it to aim and release"""

var panel: PanelContainer
var body: VBoxContainer
var _quit_label := "Quit to title"


func _ready() -> void:
	layer = 50
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false


func open(in_battle: bool) -> void:
	_quit_label = "Leave battle" if in_battle else "Save and quit to title"
	_build()
	visible = true
	Audio.sfx(&"ui_select")


func close() -> void:
	visible = false


func _build() -> void:
	for c in get_children():
		c.queue_free()
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.theme = UiTheme.get_theme()
	add_child(root)
	var dim := ColorRect.new()
	dim.color = Color(0.02, 0.02, 0.05, 0.6)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(center)
	panel = PanelContainer.new()
	panel.custom_minimum_size = Vector2(520, 0)
	center.add_child(panel)
	body = VBoxContainer.new()
	body.add_theme_constant_override("separation", 12)
	panel.add_child(body)
	_main()


func _clear_body() -> void:
	for c in body.get_children():
		c.queue_free()


func _main() -> void:
	_clear_body()
	var t := UiTheme.label("Paused", 44, UiTheme.GOLD, true, 10)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	body.add_child(t)
	var first := _button("Resume", func() -> void:
		Audio.sfx(&"ui_select")
		resumed.emit())
	_button("Controls", _controls)
	_button("Settings", _settings)
	_button(_quit_label, func() -> void:
		Audio.sfx(&"ui_back")
		quit_requested.emit())
	first.grab_focus()


func _controls() -> void:
	_clear_body()
	var rt := RichTextLabel.new()
	rt.bbcode_enabled = true
	rt.fit_content = true
	rt.custom_minimum_size = Vector2(760, 0)
	rt.add_theme_font_override("normal_font", UiTheme.FONT_REGULAR)
	rt.add_theme_font_override("bold_font", UiTheme.FONT_BOLD)
	rt.add_theme_font_size_override("normal_font_size", 18)
	rt.add_theme_font_size_override("bold_font_size", 20)
	rt.text = CONTROLS_TEXT
	body.add_child(rt)
	_button("Back", _main).grab_focus()


func _settings() -> void:
	_clear_body()
	body.add_child(SettingsPanel.new())
	_button("Back", _main).grab_focus()


func _button(text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(300, 52)
	b.pressed.connect(cb)
	body.add_child(b)
	return b
