class_name DashLane
extends MeshInstance3D
## One dash lane on the board: a single flat quad from the edge of the home
## cell along the dash, which dash_lane.gdshader draws as one tile per cell
## (path, landing, ram, out of reach, wall). Tiles pop in one after another
## as `reveal` grows.

const SHADER := preload("res://shaders/dash_lane.gdshader")
const MAX_CELLS := 12
const HEIGHT := 0.026
const REVEAL_SPEED := 30.0  # cells per second

enum Cell { HIDDEN, PATH, LANDING, RAM, CUT, WALL }

var mat: ShaderMaterial
var span := 1
var reveal := 0.0
var reveal_target := 0.0
var dir_index := -1
var home_cell := Vector2i(-9999, -9999)
var _states := PackedFloat32Array()


func _init() -> void:
	var pm := PlaneMesh.new()
	pm.size = Vector2.ONE
	mesh = pm
	mat = ShaderMaterial.new()
	mat.shader = SHADER
	mat.render_priority = -2
	material_override = mat
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_states.resize(MAX_CELLS)
	visible = false


## Place the lane: `home` is the centre of the cell the dash starts from,
## `cells` how many tiles it spans. A new direction or start cell restarts
## the pop-in from the creature.
func layout(home: Vector2, p_home_cell: Vector2i, p_dir_index: int, cells: int) -> void:
	var dir := Cardinal.from_index(p_dir_index)
	if p_dir_index != dir_index or p_home_cell != home_cell:
		reveal = 0.0
		dir_index = p_dir_index
		home_cell = p_home_cell
	span = clampi(cells, 1, MAX_CELLS)
	var mid := home + dir * (span * 0.5 + 0.5)
	position = Vector3(mid.x, HEIGHT, mid.y)
	rotation = Vector3(0.0, -atan2(dir.y, dir.x), 0.0)
	scale = Vector3(span, 1.0, 1.0)
	mat.set_shader_parameter("cell_span", float(span))


func set_cells(states: Array[int]) -> void:
	for i in MAX_CELLS:
		_states[i] = float(states[i]) if i < states.size() else 0.0
	mat.set_shader_parameter("cell_state", _states)


func set_colors(main: Color, accent: Color = Color.WHITE) -> void:
	mat.set_shader_parameter("main_color", main)
	mat.set_shader_parameter("accent_color", accent)


func set_param(param: StringName, value: Variant) -> void:
	mat.set_shader_parameter(param, value)


func advance(delta: float) -> void:
	reveal = move_toward(reveal, reveal_target, delta * REVEAL_SPEED)
	mat.set_shader_parameter("reveal", reveal)


func hide_lane() -> void:
	visible = false
	dir_index = -1
	home_cell = Vector2i(-9999, -9999)
	reveal = 0.0
