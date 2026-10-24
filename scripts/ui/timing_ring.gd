class_name TimingRing
extends CanvasLayer
## "Offer your hand" mini-game: an outer ring closes in on a target ring;
## press when they meet. Forgiving window, three tries per attempt.

signal resolved(success: bool)

const TARGET := 64.0
const START := 190.0
const DURATION := 1.7
const WINDOW := 15.0

var _ring := START
var _t := 0.0
var _active := false
var _draw_node: Control
var _flash := 0.0
var _result_color := Color.WHITE


func _ready() -> void:
	layer = 35
	visible = false
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	_draw_node = Control.new()
	_draw_node.set_anchors_preset(Control.PRESET_FULL_RECT)
	_draw_node.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_draw_node.draw.connect(_draw_rings)
	root.add_child(_draw_node)
	var hint := UiTheme.label("Offer your hand — press [E] / tap when the rings meet", 22, UiTheme.PARCHMENT, true)
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	UiTheme.place(hint, Vector2(0.5, 0.5), Vector2(-400, 150), Vector2(800, 40))
	root.add_child(hint)


## Runs one attempt. Awaitable: returns true on success.
func run() -> bool:
	visible = true
	_ring = START
	_t = 0.0
	_active = true
	_flash = 0.0
	var ok: bool = await resolved
	await get_tree().create_timer(0.45).timeout
	visible = false
	return ok


func _process(delta: float) -> void:
	_flash = maxf(0.0, _flash - delta * 2.5)
	if _active:
		_t += delta
		_ring = lerpf(START, 20.0, clampf(_t / DURATION, 0.0, 1.0))
		if _t >= DURATION:
			_finish(false)
	_draw_node.queue_redraw()


func _input(event: InputEvent) -> void:
	if not _active:
		return
	var press := event.is_action_pressed(&"interact") or event.is_action_pressed(&"advance")
	if event is InputEventScreenTouch and event.pressed:
		press = true
	if press:
		get_viewport().set_input_as_handled()
		_finish(absf(_ring - TARGET) <= WINDOW)


func _finish(ok: bool) -> void:
	_active = false
	_flash = 1.0
	_result_color = Color(1.0, 0.85, 0.4) if ok else Color(1.0, 0.4, 0.35)
	Audio.sfx(&"trust_up" if ok else &"ui_error")
	resolved.emit(ok)


func _draw_rings() -> void:
	var c := _draw_node.size * 0.5
	_draw_node.draw_circle(c, START + 30, Color(0.03, 0.02, 0.05, 0.45))
	_draw_node.draw_arc(c, TARGET, 0, TAU, 64, Color(1.0, 0.85, 0.45, 0.95), 6.0)
	_draw_node.draw_arc(c, TARGET + WINDOW, 0, TAU, 64, Color(1.0, 0.85, 0.45, 0.25), 2.0)
	_draw_node.draw_arc(c, TARGET - WINDOW, 0, TAU, 64, Color(1.0, 0.85, 0.45, 0.25), 2.0)
	var near := absf(_ring - TARGET) <= WINDOW
	_draw_node.draw_arc(c, _ring, 0, TAU, 64, Color(1.0, 0.95, 0.8) if near else Color(0.85, 0.85, 0.95), 5.0)
	if _flash > 0.0:
		_draw_node.draw_circle(c, TARGET * (1.0 + (1.0 - _flash) * 0.6), Color(_result_color.r, _result_color.g, _result_color.b, _flash * 0.35))
	var heart := "♥"
	_draw_node.draw_string(UiTheme.FONT_BOLD, c + Vector2(-14, 14), heart, HORIZONTAL_ALIGNMENT_LEFT, -1, 40, Color(1.0, 0.55, 0.45))
