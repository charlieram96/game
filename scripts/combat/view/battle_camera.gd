class_name BattleCamera
extends Camera3D
## Fixed perspective battle camera: the HD-2D diorama view.
##
## A narrow field of view and a fixed pitch give the board real depth (the
## back row is a little smaller than the front row, walls and pillars rise
## out of it) while keeping distances easy to read. The camera never
## rotates during a match.
##
## Framing: the board (with its flush rim) is made as large as it can be
## while its whole floor stays between the HUD bands (top bar, ability bar)
## and clear of the side insets (e.g. the touch button cluster). The board is
## centred between the bands and, horizontally, on the screen unless an inset
## pushes it aside. Height is the limit on wide phones, width at 16:9 and on
## 4:3 tablets. Everything is solved numerically from the real projection, so
## board_screen_rect() and ground_point() are exact.
##
## Feel: shake (`add_trauma`) offsets the view, `kick` nudges the camera
## along the ground and springs back, `zoom_punch` briefly narrows the field
## of view. All three are recomputed from the rest pose every frame, so they
## compose freely and can never drift; aiming always uses the rest pose.

## Angle of the view below the horizon. Read by Vfx.screen_angle() and used
## for the upright-sprite stretch (global shader parameter `sprite_stretch`).
const PITCH_DEG := 48.0
## Vertical field of view (the horizontal one follows the aspect ratio).
const FOV_DEG := 25.0
## HUD bands in canvas pixels (the canvas is 720 px tall at 16:9 and wider).
const HUD_TOP := 86.0
const HUD_BOTTOM := 98.0
## Canvas pixels kept between the board's floor and the HUD bands.
const BAND_PAD := 4.0
## World units kept visible beside the board's floor (the rim, a little stone).
const SIDE_ROOM := 0.35
## Room kept between the board and a side inset (world units: the rim plus a little).
const INSET_ROOM := 0.6
const NEAR := 6.0
const FAR := 150.0
const KICK_RISE := 0.03
const KICK_TIME := 0.14
const PUNCH_RISE := 0.05
const PUNCH_TIME := 0.26

var arena_size := Vector2(20, 12)
var focus := Vector3.ZERO
## Screen strips (canvas pixels) on the left and right that UI covers.
var side_insets := Vector2.ZERO
var _trauma := 0.0
var _shake_time := 0.0
var _rest := Transform3D(Basis.from_euler(Vector3(-deg_to_rad(PITCH_DEG), 0.0, 0.0)), Vector3(0.0, 20.0, 18.0))
var _kicks: Array[Dictionary] = []  # {"offset": Vector2, "t": float}
var _punches: Array[Dictionary] = []  # {"amount": float, "t": float}


func _ready() -> void:
	projection = PROJECTION_PERSPECTIVE
	keep_aspect = KEEP_HEIGHT
	fov = FOV_DEG
	near = NEAR
	far = FAR
	get_viewport().size_changed.connect(_reframe)
	_reframe()
	RenderingServer.global_shader_parameter_set("sprite_stretch", 1.0 / cos(pitch()))
	RenderingServer.global_shader_parameter_set("occluder_active", 0.0)


static func pitch() -> float:
	return deg_to_rad(PITCH_DEG)


static func rest_basis() -> Basis:
	return Basis.from_euler(Vector3(-pitch(), 0.0, 0.0))


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


## The rest pose (camera transform) that frames `board` (world units, centred
## on `p_focus`) for a visible canvas of `vis` pixels with side `insets`.
static func compute_rest(board: Vector2, vis: Vector2, insets: Vector2 = Vector2.ZERO, p_focus: Vector3 = Vector3.ZERO) -> Transform3D:
	vis = Vector2(maxf(vis.x, 64.0), maxf(vis.y, 64.0))
	var room := Vector2(SIDE_ROOM if insets.x <= 0.0 else INSET_ROOM, SIDE_ROOM if insets.y <= 0.0 else INSET_ROOM)
	var corners := _framed_corners(board, room, p_focus)
	var allowed := Rect2(insets.x, HUD_TOP + BAND_PAD, maxf(32.0, vis.x - insets.x - insets.y), maxf(32.0, vis.y - HUD_TOP - HUD_BOTTOM - BAND_PAD * 2.0))
	# Bisection on the distance: the closest camera whose framed board fits.
	var lo := 2.0
	var hi := 600.0
	for _i in 48:
		var mid := (lo + hi) * 0.5
		var r := _bounds(_placed(corners, vis, allowed, p_focus, mid), corners, vis)
		if _fits(r, allowed):
			hi = mid
		else:
			lo = mid
	return _placed(corners, vis, allowed, p_focus, hi)


## Board corners that must stay in the allowed area: the floor plus the side room.
static func _framed_corners(board: Vector2, room: Vector2, p_focus: Vector3) -> PackedVector3Array:
	var h := board * 0.5
	var c := Vector3(p_focus.x, 0.0, p_focus.z)
	return PackedVector3Array([
		c + Vector3(-h.x - room.x, 0.0, -h.y), c + Vector3(h.x + room.y, 0.0, -h.y),
		c + Vector3(-h.x - room.x, 0.0, h.y), c + Vector3(h.x + room.y, 0.0, h.y),
	])


## Camera at `dist` from the focus along the view axis, shifted across the
## view so the framed board sits centred between the bands and (if it can)
## centred on the screen, else just clear of the insets.
static func _placed(corners: PackedVector3Array, vis: Vector2, allowed: Rect2, p_focus: Vector3, dist: float) -> Transform3D:
	var b := rest_basis()
	var origin := Vector3(p_focus.x, 0.0, p_focus.z) + b.z * dist
	var k := tan(deg_to_rad(FOV_DEG) * 0.5)
	for _i in 8:
		var xf := Transform3D(b, origin)
		var r := _bounds(xf, corners, vis)
		var want_x := clampf(vis.x * 0.5, allowed.position.x + r.size.x * 0.5, allowed.end.x - r.size.x * 0.5)
		if r.size.x > allowed.size.x:
			want_x = allowed.get_center().x
		var want := Vector2(want_x, allowed.get_center().y)
		var err := want - r.get_center()
		if err.length() < 0.01:
			break
		# pixels per world unit across the view at the board's depth
		var ppu := vis.y * 0.5 / (dist * k)
		origin += -b.x * (err.x / ppu) + b.y * (err.y / ppu)
	return Transform3D(b, origin)


static func _bounds(xf: Transform3D, pts: PackedVector3Array, vis: Vector2) -> Rect2:
	var r := Rect2(project(xf, FOV_DEG, vis, pts[0]), Vector2.ZERO)
	for i in range(1, pts.size()):
		r = r.expand(project(xf, FOV_DEG, vis, pts[i]))
	return r


static func _fits(r: Rect2, allowed: Rect2) -> bool:
	return r.position.x >= allowed.position.x - 0.01 and r.end.x <= allowed.end.x + 0.01 and r.position.y >= allowed.position.y - 0.01 and r.end.y <= allowed.end.y + 0.01


## Canvas position of world point `p` for a camera at `xf` (KEEP_HEIGHT
## perspective with a vertical field of view of `fov_deg`), the same mapping
## as Camera3D.unproject_position().
static func project(xf: Transform3D, fov_deg: float, vis: Vector2, p: Vector3) -> Vector2:
	var v := xf.affine_inverse() * p
	var k := tan(deg_to_rad(fov_deg) * 0.5)
	var depth := maxf(-v.z, 1e-4)
	var aspect := vis.x / maxf(1.0, vis.y)
	var nx := v.x / (depth * k * aspect)
	var ny := v.y / (depth * k)
	return Vector2((nx + 1.0) * 0.5 * vis.x, (1.0 - ny) * 0.5 * vis.y)


func _reframe() -> void:
	var vis := get_viewport().get_visible_rect().size
	_rest = compute_rest(arena_size, vis, side_insets, focus)
	_apply()


## The camera's rest pose (no shake, kick or zoom punch).
func rest_transform() -> Transform3D:
	return _rest


func add_trauma(amount: float) -> void:
	_trauma = clampf(_trauma + amount * Settings.screen_shake, 0.0, 1.0)


## Quick nudge of the whole view along `dir` (world XZ: x east, y south) by
## `amount` units; springs back to rest in ~KICK_TIME seconds.
func kick(dir: Vector2, amount: float) -> void:
	if dir.length_squared() < 1e-6 or amount <= 0.0:
		return
	_kicks.append({"offset": dir.normalized() * amount * Settings.screen_shake, "t": 0.0})


## Briefly zoom in by `amount` (fraction of the field of view, e.g. 0.04)
## and ease back over ~PUNCH_TIME seconds.
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
	transform = Transform3D(_rest.basis, _rest.origin + Vector3(nudge.x, 0.0, nudge.y))
	fov = FOV_DEG * (1.0 - clampf(punch, 0.0, 0.3))
	if _trauma <= 0.0:
		h_offset = 0.0
		v_offset = 0.0
		return
	var amp := _trauma * _trauma * 0.35
	h_offset = amp * sin(_shake_time * 1.7) * cos(_shake_time * 0.9)
	v_offset = amp * cos(_shake_time * 1.3) * sin(_shake_time * 1.1)


## World point on the ground plane (y = 0) under a screen position (canvas
## coordinates, as from Viewport.get_mouse_position()). Exact for the rest
## pose, so shake, kicks and zoom punches never move the aimed cell.
func ground_point(screen_pos: Vector2) -> Vector3:
	return ground_point_for(_rest, get_viewport().get_visible_rect().size, screen_pos)


static func ground_point_for(xf: Transform3D, vis: Vector2, screen_pos: Vector2) -> Vector3:
	var k := tan(deg_to_rad(FOV_DEG) * 0.5)
	var aspect := vis.x / maxf(1.0, vis.y)
	var nx := screen_pos.x / maxf(1.0, vis.x) * 2.0 - 1.0
	var ny := 1.0 - screen_pos.y / maxf(1.0, vis.y) * 2.0
	var b := xf.basis
	var dir := -b.z + b.x * (nx * k * aspect) + b.y * (ny * k)
	if dir.y > -1e-5:
		# At or above the horizon (never on screen with this pitch): clamp far away.
		dir.y = -1e-5
	return xf.origin + dir * (-xf.origin.y / dir.y)


## Canvas position of a world point at the rest pose.
func rest_unproject(p: Vector3) -> Vector2:
	return project(_rest, FOV_DEG, get_viewport().get_visible_rect().size, p)


## Screen rectangle (canvas pixels) covered by the board's floor at rest:
## the bounding box of its four corners (the front edge is the widest).
func board_screen_rect() -> Rect2:
	var vis := get_viewport().get_visible_rect().size
	var h := arena_size * 0.5
	var c := Vector3(focus.x, 0.0, focus.z)
	var pts := PackedVector3Array([c + Vector3(-h.x, 0.0, -h.y), c + Vector3(h.x, 0.0, -h.y), c + Vector3(-h.x, 0.0, h.y), c + Vector3(h.x, 0.0, h.y)])
	return _bounds(_rest, pts, vis)
