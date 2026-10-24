class_name UiTheme
extends RefCounted
## Builds the shared pixel-art UI theme (font, panels, buttons, bars).
## Uses the generated 9-slice art when present, flat styles otherwise.

const FONT_REGULAR := preload("res://assets/fonts/PixelifySans-Regular.ttf")
const FONT_BOLD := preload("res://assets/fonts/PixelifySans-Bold.ttf")
const PANEL_DIR := "res://assets/ui/panels/"
const ICON_DIR := "res://assets/ui/icons/"

const INK := Color(0.07, 0.05, 0.09)
const PARCHMENT := Color(0.96, 0.91, 0.8)
const GOLD := Color(0.95, 0.78, 0.36)
const TEAL := Color(0.35, 0.9, 0.95)
const DANGER := Color(1.0, 0.45, 0.38)

static var _theme: Theme = null
static var _icons: Dictionary = {}


static func get_theme() -> Theme:
	if _theme:
		return _theme
	var t := Theme.new()
	t.default_font = FONT_REGULAR
	t.default_font_size = 20
	t.set_color("font_color", "Label", PARCHMENT)
	t.set_color("font_outline_color", "Label", INK)
	t.set_constant("outline_size", "Label", 6)
	t.set_font("font", "Button", FONT_BOLD)
	t.set_font_size("font_size", "Button", 22)
	t.set_color("font_color", "Button", PARCHMENT)
	t.set_color("font_hover_color", "Button", Color(1.0, 0.95, 0.75))
	t.set_color("font_pressed_color", "Button", GOLD)
	t.set_color("font_focus_color", "Button", Color(1.0, 0.95, 0.75))
	t.set_color("font_outline_color", "Button", INK)
	t.set_constant("outline_size", "Button", 6)
	t.set_stylebox("normal", "Button", button_box("button", Color(0.16, 0.24, 0.26)))
	t.set_stylebox("hover", "Button", button_box("button_hover", Color(0.22, 0.34, 0.36)))
	t.set_stylebox("pressed", "Button", button_box("button_pressed", Color(0.12, 0.18, 0.2)))
	t.set_stylebox("focus", "Button", focus_box())
	t.set_stylebox("disabled", "Button", button_box("button", Color(0.12, 0.12, 0.14)))
	t.set_stylebox("panel", "PanelContainer", panel_box("panel_wood"))
	t.set_stylebox("panel", "Panel", panel_box("panel_wood"))
	t.set_font("font", "LineEdit", FONT_BOLD)
	t.set_font_size("font_size", "LineEdit", 28)
	t.set_color("font_color", "LineEdit", PARCHMENT)
	var le := StyleBoxFlat.new()
	le.bg_color = Color(0.08, 0.1, 0.12, 0.92)
	le.border_color = GOLD
	le.set_border_width_all(3)
	le.set_content_margin_all(10)
	t.set_stylebox("normal", "LineEdit", le)
	t.set_stylebox("focus", "LineEdit", le)
	t.set_font_size("font_size", "CheckBox", 20)
	t.set_color("font_color", "CheckBox", PARCHMENT)
	t.set_font_size("font_size", "OptionButton", 20)
	_theme = t
	return t


static func _tex(name: String) -> Texture2D:
	var path := PANEL_DIR + name + ".png"
	return load(path) if ResourceLoader.exists(path) else null


static func panel_box(name: String = "panel_wood", fallback: Color = Color(0.09, 0.13, 0.15, 0.94)) -> StyleBox:
	var tex := _tex(name)
	if tex:
		var sb := StyleBoxTexture.new()
		sb.texture = tex
		sb.set_texture_margin_all(16)
		sb.set_content_margin_all(18)
		sb.axis_stretch_horizontal = StyleBoxTexture.AXIS_STRETCH_MODE_TILE_FIT
		sb.axis_stretch_vertical = StyleBoxTexture.AXIS_STRETCH_MODE_TILE_FIT
		return sb
	var f := StyleBoxFlat.new()
	f.bg_color = fallback
	f.border_color = Color(0.55, 0.42, 0.25)
	f.set_border_width_all(4)
	f.set_content_margin_all(16)
	return f


static func parchment_box() -> StyleBox:
	var tex := _tex("panel_parchment")
	if tex:
		var sb := StyleBoxTexture.new()
		sb.texture = tex
		sb.set_texture_margin_all(16)
		sb.set_content_margin_all(20)
		return sb
	var f := StyleBoxFlat.new()
	f.bg_color = Color(0.93, 0.87, 0.72)
	f.border_color = Color(0.36, 0.25, 0.15)
	f.set_border_width_all(4)
	f.set_content_margin_all(18)
	return f


static func button_box(name: String, fallback: Color) -> StyleBox:
	var tex := _tex(name)
	if tex:
		var sb := StyleBoxTexture.new()
		sb.texture = tex
		sb.set_texture_margin_all(8)
		sb.content_margin_left = 18
		sb.content_margin_right = 18
		sb.content_margin_top = 8
		sb.content_margin_bottom = 10
		return sb
	var f := StyleBoxFlat.new()
	f.bg_color = fallback
	f.border_color = Color(0.62, 0.48, 0.26)
	f.set_border_width_all(3)
	f.content_margin_left = 18
	f.content_margin_right = 18
	f.content_margin_top = 8
	f.content_margin_bottom = 10
	return f


static func focus_box() -> StyleBox:
	var f := StyleBoxFlat.new()
	f.draw_center = false
	f.border_color = GOLD
	f.set_border_width_all(3)
	return f


## Cached: a texture loaded inside _draw() and dropped right away is freed
## before the frame renders, which draws a white square instead of the icon.
static func icon(name: String) -> Texture2D:
	if _icons.has(name):
		return _icons[name]
	var path := ICON_DIR + name + ".png"
	var tex: Texture2D = load(path) if ResourceLoader.exists(path) else null
	_icons[name] = tex
	return tex


static func label(text: String, size: int = 20, color: Color = PARCHMENT, bold: bool = false, outline: int = 6) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.add_theme_color_override("font_outline_color", INK)
	l.add_theme_constant_override("outline_size", outline)
	if bold:
		l.add_theme_font_override("font", FONT_BOLD)
	return l


## Pins a control to an anchor point (0..1 of the parent) with a pixel
## offset for its top-left corner and a fixed size. Layout-independent of the
## parent's size at build time.
static func place(c: Control, anchor: Vector2, offset: Vector2, size: Vector2) -> void:
	c.anchor_left = anchor.x
	c.anchor_right = anchor.x
	c.anchor_top = anchor.y
	c.anchor_bottom = anchor.y
	c.offset_left = offset.x
	c.offset_top = offset.y
	c.offset_right = offset.x + size.x
	c.offset_bottom = offset.y + size.y


static func element_color(element: StringName) -> Color:
	var chart := ElementChart.get_default()
	return chart.colors.get(String(element), PARCHMENT)
