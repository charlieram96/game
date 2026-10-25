class_name PostFX
extends CanvasLayer
## Full-screen HD-2D pass (tilt-shift, grading, vignette) drawn over the 3D
## view and under the UI. Also used for fades and impact frames.
##
## Battle mode (ArenaBuilder.apply_post): the tilt-shift follows the board's
## rows on screen, read from the current BattleCamera every frame, and is only
## used when the arena's depth-aware pass is off (low graphics); with high
## graphics this pass grades and adds god rays, film grain and a little
## corner fringing (low graphics switches those three off).

const SHADER := preload("res://shaders/post_hd2d.gdshader")
## Battle-mode extras that low graphics switches off (and back on).
const LOW_OFF: Array[String] = ["grain", "aberration", "shafts"]

var rect: ColorRect
var mat: ShaderMaterial
var battle_mode := false
var _impact_tween: Tween
var _impact_flashing := false


func _ready() -> void:
	layer = 0
	rect = ColorRect.new()
	rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	mat = ShaderMaterial.new()
	mat.shader = SHADER
	rect.material = mat
	add_child(rect)
	_apply_settings()
	Events.settings_changed.connect(_apply_settings)


func _apply_settings() -> void:
	if battle_mode:
		# high graphics: the arena's depth pass blurs; low: the board band here
		mat.set_shader_parameter("blur_amount", 1.0 if Settings.tilt_shift and Settings.graphics_low else 0.0)
		for p: String in LOW_OFF:
			mat.set_shader_parameter(p, 0.0 if Settings.graphics_low else float(mat.get_meta(p, 0.0)))
	else:
		mat.set_shader_parameter("blur_amount", 1.0 if Settings.tilt_shift and not Settings.graphics_low else 0.0)


## Battle grading and the board-following tilt-shift band.
func set_battle_mode(on: bool) -> void:
	battle_mode = on
	mat.set_shader_parameter("board_band", on)
	_apply_settings()


func set_focus(center: float, width: float) -> void:
	mat.set_shader_parameter("focus_center", center)
	mat.set_shader_parameter("focus_width", width)


func set_param(param: String, value: Variant) -> void:
	if battle_mode and param in LOW_OFF:
		# remembered so low graphics can switch them off and back on
		mat.set_meta(param, value)
		_apply_settings()
		return
	mat.set_shader_parameter(param, value)


func _process(_delta: float) -> void:
	if not battle_mode:
		return
	var cam := get_viewport().get_camera_3d()
	if cam is BattleCamera:
		var r := (cam as BattleCamera).board_screen_rect()
		var h := maxf(1.0, get_viewport().get_visible_rect().size.y)
		mat.set_shader_parameter("band_top", r.position.y / h)
		mat.set_shader_parameter("band_bottom", r.end.y / h)


func fade_to(amount: float, duration: float, color: Color = Color.BLACK) -> Tween:
	mat.set_shader_parameter("fade_color", color)
	var tw := create_tween()
	tw.tween_method(func(v: float) -> void: mat.set_shader_parameter("fade", v), _fade_now(), amount, duration)
	return tw


## Impact frame for a big hit: a quick radial colour split around
## `screen_uv` (0..1) and a faint flash. Scaled by the screen-shake setting.
func impact(strength: float, screen_uv: Vector2 = Vector2(0.5, 0.5), flash_color: Color = Color(1.0, 0.97, 0.88)) -> void:
	var k := clampf(strength, 0.0, 1.0) * Settings.screen_shake
	if k <= 0.0:
		return
	if _impact_tween and _impact_tween.is_valid():
		_impact_tween.kill()
		if _impact_flashing:
			mat.set_shader_parameter("fade", 0.0)
	mat.set_shader_parameter("impact_center", screen_uv)
	# Only flash when no fade (scene transition) is in progress.
	_impact_flashing = _fade_now() <= 0.001
	if _impact_flashing:
		mat.set_shader_parameter("fade_color", flash_color)
	_impact_tween = create_tween().set_parallel(true)
	_impact_tween.tween_method(func(v: float) -> void: mat.set_shader_parameter("impact", v), k, 0.0, 0.22).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_QUAD)
	if _impact_flashing:
		_impact_tween.tween_method(func(v: float) -> void: mat.set_shader_parameter("fade", v), 0.16 * k, 0.0, 0.1)
	_impact_tween.chain().tween_callback(func() -> void: _impact_flashing = false)


func _fade_now() -> float:
	var v: Variant = mat.get_shader_parameter("fade")
	return float(v) if v != null else 0.0
