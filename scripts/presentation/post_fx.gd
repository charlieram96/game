class_name PostFX
extends CanvasLayer
## Full-screen HD-2D pass (tilt-shift, grading, vignette) drawn over the 3D
## view and under the UI. Also used for fades and impact frames.

const SHADER := preload("res://shaders/post_hd2d.gdshader")

var rect: ColorRect
var mat: ShaderMaterial
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
	mat.set_shader_parameter("blur_amount", 1.0 if Settings.tilt_shift and not Settings.graphics_low else 0.0)


func set_focus(center: float, width: float) -> void:
	mat.set_shader_parameter("focus_center", center)
	mat.set_shader_parameter("focus_width", width)


func set_param(param: String, value: Variant) -> void:
	mat.set_shader_parameter(param, value)


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
