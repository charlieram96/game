class_name PostFX
extends CanvasLayer
## Full-screen HD-2D pass (tilt-shift, grading, vignette) drawn over the 3D
## view and under the UI. Also used for fades.

const SHADER := preload("res://shaders/post_hd2d.gdshader")

var rect: ColorRect
var mat: ShaderMaterial


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
	mat.set_shader_parameter("blur_amount", 1.0 if Settings.tilt_shift else 0.0)


func set_focus(center: float, width: float) -> void:
	mat.set_shader_parameter("focus_center", center)
	mat.set_shader_parameter("focus_width", width)


func set_param(param: String, value: Variant) -> void:
	mat.set_shader_parameter(param, value)


func fade_to(amount: float, duration: float, color: Color = Color.BLACK) -> Tween:
	mat.set_shader_parameter("fade_color", color)
	var tw := create_tween()
	tw.tween_method(func(v: float) -> void: mat.set_shader_parameter("fade", v), float(mat.get_shader_parameter("fade")), amount, duration)
	return tw
