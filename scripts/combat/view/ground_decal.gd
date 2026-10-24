class_name GroundDecal
extends MeshInstance3D
## A procedural shape drawn flat on the ground (telegraphs, guard arcs,
## debug hitboxes) using shaders/telegraph.gdshader.

const SHADER := preload("res://shaders/telegraph.gdshader")

enum Shape { CIRCLE = 0, RING = 1, CONE = 2, BOX = 3 }

var _mat: ShaderMaterial
var _size := Vector2.ONE


func _init() -> void:
	mesh = PlaneMesh.new()
	_mat = ShaderMaterial.new()
	_mat.shader = SHADER
	material_override = _mat
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	position.y = 0.025


## Circle/ring/cone centered on the node. Radius in world units.
func set_circle(radius: float, shape: Shape = Shape.CIRCLE, inner_fraction: float = 0.0, half_angle: float = PI * 0.25) -> void:
	_size = Vector2(radius * 2.0, radius * 2.0)
	(mesh as PlaneMesh).size = _size
	(mesh as PlaneMesh).center_offset = Vector3.ZERO
	_mat.set_shader_parameter("shape", int(shape))
	_mat.set_shader_parameter("inner", inner_fraction)
	_mat.set_shader_parameter("half_angle", half_angle)
	_mat.set_shader_parameter("quad_size", _size)


## Box starting at the node and extending `length` along +X (rotate the node to aim).
func set_box(length: float, width: float) -> void:
	_size = Vector2(length, width)
	var pm := mesh as PlaneMesh
	pm.size = _size
	pm.center_offset = Vector3(length * 0.5, 0, 0)
	_mat.set_shader_parameter("shape", int(Shape.BOX))
	_mat.set_shader_parameter("quad_size", _size)


## Aim the decal: direction on the ground plane (x = east, y = south).
func aim(dir: Vector2) -> void:
	rotation.y = -atan2(dir.y, dir.x)


func set_colors(edge: Color, fill: Color, opacity: float = 0.85) -> void:
	_mat.set_shader_parameter("color", edge)
	_mat.set_shader_parameter("fill_color", fill)
	_mat.set_shader_parameter("opacity", opacity)


func set_progress(p: float) -> void:
	_mat.set_shader_parameter("progress", clampf(p, 0.0, 1.0))


func set_opacity(a: float) -> void:
	_mat.set_shader_parameter("opacity", a)
