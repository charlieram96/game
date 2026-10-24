class_name BattleCamera
extends Camera3D
## Fixed overhead orthographic battle camera.
##
## The view is angled for depth, but the camera never rotates during a match
## and uses an orthographic projection, so creatures keep the same apparent
## size everywhere and on-screen distances are uniform per axis.
##
## Framing: the board fills as much of the screen as it can while the whole
## floor stays between the HUD bands (top bar, ability bar), the top of the
## back wall stays on screen and the trainers beside the board still fit.
## Height is the limit at 16:9 and on wide phones, width on 4:3 tablets.
## Side insets (e.g. the touch button cluster) push the board aside first and
## only shrink it when it can't fit beside them.
##
## Feel: shake (`add_trauma`) offsets the view, `kick` nudges the camera
## along the ground and springs back, `zoom_punch` briefly tightens the ortho
## size. All three are recomputed from the rest pose every frame, so they
## compose freely and can never drift.

const PITCH_DEG := 54.0
## HUD bands in canvas pixels (the canvas is 720 px tall at 16:9 and wider).
const HUD_TOP := 86.0
const HUD_BOTTOM := 98.0
const DISTANCE := 24.0
## Room kept between the board and a side inset (world units: the rim plus a little).
const INSET_ROOM := 0.6
const KICK_RISE := 0.03
const KICK_TIME := 0.14
const PUNCH_RISE := 0.05
const PUNCH_TIME := 0.26

var arena_size := Vector2(16, 10)
## Room kept visible around the board: x = world units beside it on each side
## (the trainers' podiums), y = screen height in world units above its back
## edge (rim + the top of the back wall).
var margin := Vector2(1.75, 1.0)
var focus := Vector3.ZERO
## Screen strips (canvas pixels) on the left and right that UI covers.
var side_insets := Vector2.ZERO
var _trauma := 0.0
var _shake_time := 0.0
var _rest_position := Vector3.ZERO
var _rest_size := 10.0
var _kicks: Array[Dictionary] = []  # {"offset": Vector2, "t": float}
var _punches: Array[Dictionary] = []  # {"amount": float, "t": float}


func _ready() -> void:
	projection = PROJECTION_ORTHOGONAL
	keep_aspect = KEEP_HEIGHT
	near = 0.1
	far = DISTANCE * 3.0
	rotation = Vector3(-pitch(), 0.0, 0.0)
	get_viewport().size_changed.connect(_reframe)
	_reframe()
	RenderingServer.global_shader_parameter_set("sprite_stretch", 1.0 / cos(pitch()))
	RenderingServer.global_shader_parameter_set("occluder_active", 0.0)


static func pitch() -> float:
	return deg_to_rad(PITCH_DEG)


func setup(p_arena_size: Vector2, p_focus: Vector3 = Vector3.ZERO) -> void:
	arena_size = p_arena_size
	focus = p_focus
	if is_inside_tree():
		_reframe()


## Reserve screen strips (canvas pixels) on the left and right that UI covers,
## e.g. the touch buttons: the whole board is kept clear of them. 0 = none.
func set_side_insets(left_px: float, right_px: float) -> void:
	side_insets = Vector2(maxf(0.0, left_px), maxf(0.0, right_px))
	if is_inside_tree():
		_reframe()


## Rest-pose framing for a visible canvas of `vis` (canvas pixels):
## x = ortho size, y = view-space height of the board centre, z = horizontal
## offset (world units, + = right) of the board centre from the screen centre.
static func compute_framing(board: Vector2, vis: Vector2, side_room: float, top_room: float, insets: Vector2 = Vector2.ZERO) -> Vector3:
	var p := deg_to_rad(PITCH_DEG)
	var top_frac := HUD_TOP / maxf(1.0, vis.y)
	var bottom_frac := HUD_BOTTOM / maxf(1.0, vis.y)
	var depth := board.y * sin(p)  # board's on-screen height in view units
	var size_h := depth / maxf(0.2, 1.0 - top_frac - bottom_frac)
	var size_wall := (depth + top_room) / maxf(0.2, 1.0 - bottom_frac)
	# Width: the board plus room on each side must fit between the insets. A
	# side covered by UI only needs the rim's room, not the trainer's.
	var room_l := side_room if insets.x <= 0.0 else INSET_ROOM
	var room_r := side_room if insets.y <= 0.0 else INSET_ROOM
	var avail := maxf(1.0, vis.x - insets.x - insets.y)
	var size_w := (board.x + room_l + room_r) * vis.y / avail
	var s := maxf(maxf(size_h, size_wall), size_w)
	# Board centre's height in view space: centred in the free band, but never
	# so high that the back wall leaves the screen.
	var lo := -s * (0.5 - bottom_frac) + depth * 0.5
	var hi := minf(s * (0.5 - top_frac) - depth * 0.5, s * 0.5 - depth * 0.5 - top_room)
	# Horizontal: centred, then shifted just enough to clear the insets.
	var ppu := vis.y / s
	var half_px := board.x * 0.5 * ppu
	var cx := vis.x * 0.5
	cx = minf(cx, vis.x - insets.y - room_r * ppu - half_px)
	cx = maxf(cx, insets.x + room_l * ppu + half_px)
	return Vector3(s, (lo + hi) * 0.5, (cx - vis.x * 0.5) / ppu)


func _reframe() -> void:
	var vis := get_viewport().get_visible_rect().size
	var f := compute_framing(arena_size, vis, margin.x, margin.y, side_insets)
	_rest_size = f.x
	var back := Vector3(0.0, sin(pitch()), cos(pitch()))
	var up := Vector3(0.0, cos(pitch()), -sin(pitch()))
	_rest_position = focus + back * DISTANCE - up * f.y - Vector3.RIGHT * f.z
	_apply()


func add_trauma(amount: float) -> void:
	_trauma = clampf(_trauma + amount * Settings.screen_shake, 0.0, 1.0)


## Quick nudge of the whole view along `dir` (world XZ: x east, y south) by
## `amount` units; springs back to rest in ~KICK_TIME seconds.
func kick(dir: Vector2, amount: float) -> void:
	if dir.length_squared() < 1e-6 or amount <= 0.0:
		return
	_kicks.append({"offset": dir.normalized() * amount * Settings.screen_shake, "t": 0.0})


## Briefly zoom in by `amount` (fraction of the ortho size, e.g. 0.04) and
## ease back over ~PUNCH_TIME seconds.
func zoom_punch(amount: float) -> void:
	if amount <= 0.0:
		return
	_punches.append({"amount": amount * Settings.screen_shake, "t": 0.0})


func _process(delta: float) -> void:
	# A frame hitch must not swallow a whole kick: effects advance at most 1/30 s per frame.
	var dt := minf(delta, 1.0 / 30.0)
	if not _kicks.is_empty():
		for k in _kicks:
			k["t"] = float(k["t"]) + dt
		_kicks = _kicks.filter(func(k: Dictionary) -> bool: return float(k["t"]) < KICK_TIME)
	if not _punches.is_empty():
		for pu in _punches:
			pu["t"] = float(pu["t"]) + dt
		_punches = _punches.filter(func(pu: Dictionary) -> bool: return float(pu["t"]) < PUNCH_TIME)
	if _trauma > 0.0:
		_shake_time += delta * 40.0
		_trauma = maxf(0.0, _trauma - delta * 2.2)
	_apply()


## Envelope: fast ease-in to 1 over `rise`, then an ease-out back to 0 at `total`.
static func _envelope(t: float, rise: float, total: float) -> float:
	if t < rise:
		return sin(t / rise * PI * 0.5)
	var u := clampf((t - rise) / maxf(0.001, total - rise), 0.0, 1.0)
	return (1.0 - u) * (1.0 - u) * (1.0 + 2.0 * u)


func _apply() -> void:
	var nudge := Vector2.ZERO
	for k in _kicks:
		nudge += (k["offset"] as Vector2) * _envelope(float(k["t"]), KICK_RISE, KICK_TIME)
	var punch := 0.0
	for pu in _punches:
		punch += float(pu["amount"]) * _envelope(float(pu["t"]), PUNCH_RISE, PUNCH_TIME)
	position = _rest_position + Vector3(nudge.x, 0.0, nudge.y)
	size = _rest_size * (1.0 - clampf(punch, 0.0, 0.3))
	if _trauma <= 0.0:
		h_offset = 0.0
		v_offset = 0.0
		return
	var amp := _trauma * _trauma * 0.35
	h_offset = amp * sin(_shake_time * 1.7) * cos(_shake_time * 0.9)
	v_offset = amp * cos(_shake_time * 1.3) * sin(_shake_time * 1.1)


## World point on the ground plane (y = 0) under a screen position (canvas
## coordinates, as from Viewport.get_mouse_position()). Uses the camera's rest
## pose, so shake, kicks and zoom punches never move the aimed cell.
func ground_point(screen_pos: Vector2) -> Vector3:
	var vis := get_viewport().get_visible_rect().size
	var aspect := vis.x / maxf(1.0, vis.y)
	var n := Vector2(screen_pos.x / maxf(1.0, vis.x) - 0.5, 0.5 - screen_pos.y / maxf(1.0, vis.y))
	var right := Vector3.RIGHT
	var up := Vector3(0.0, cos(pitch()), -sin(pitch()))
	var dir := Vector3(0.0, -sin(pitch()), -cos(pitch()))
	var from := _rest_position + right * (n.x * _rest_size * aspect) + up * (n.y * _rest_size)
	var t := -from.y / dir.y
	return from + dir * t


## Screen rectangle (canvas pixels) covered by the board's floor at rest.
func board_screen_rect() -> Rect2:
	var vis := get_viewport().get_visible_rect().size
	var a := _rest_unproject(Vector3(-arena_size.x * 0.5, 0.0, -arena_size.y * 0.5) + Vector3(focus.x, 0.0, focus.z), vis)
	var b := _rest_unproject(Vector3(arena_size.x * 0.5, 0.0, arena_size.y * 0.5) + Vector3(focus.x, 0.0, focus.z), vis)
	return Rect2(a, b - a)


func _rest_unproject(p: Vector3, vis: Vector2) -> Vector2:
	var aspect := vis.x / maxf(1.0, vis.y)
	var up := Vector3(0.0, cos(pitch()), -sin(pitch()))
	var rel := p - _rest_position
	var nx := rel.x / (_rest_size * aspect)
	var ny := rel.dot(up) / _rest_size
	return Vector2((nx + 0.5) * vis.x, (0.5 - ny) * vis.y)
