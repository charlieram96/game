class_name ArenaMesh
extends RefCounted
## Geometry kit for the battle diorama: beveled prisms (flagstones, rim
## slabs, steps, pillars, wall courses), boxes, cylinders and quads, all
## written into SurfaceTools so the arena builder can merge every static
## piece that shares a material into one mesh (one draw call).
##
## Vertex data used by the arena shaders (arena_floor / arena_stone):
## * UV   = texture coordinates in texels (floor atlas) or unused (triplanar).
## * UV2  = (local floor height, contact-shadow strength): the stone shader
##          darkens a surface near the floor it stands on.
## * COLOR = per-piece tint (rgb) and a free channel (a), e.g. wear.

## Inset of a convex polygon by `d` along each edge's inward normal (mitred
## corners). Polygons here are listed with a positive signed area in (x, z),
## e.g. (x0, z0) -> (x1, z0) -> (x1, z1) -> (x0, z1): prism() relies on it.
static func inset_polygon(poly: PackedVector2Array, d: float) -> PackedVector2Array:
	var n := poly.size()
	var out := PackedVector2Array()
	out.resize(n)
	var area := 0.0
	for i in n:
		var a := poly[i]
		var b := poly[(i + 1) % n]
		area += a.x * b.y - b.x * a.y
	var s := 1.0 if area > 0.0 else -1.0
	for i in n:
		var p0 := poly[(i - 1 + n) % n]
		var p1 := poly[i]
		var p2 := poly[(i + 1) % n]
		var e0 := (p1 - p0).normalized()
		var e1 := (p2 - p1).normalized()
		# inward normal of an edge for this winding
		var n0 := Vector2(-e0.y, e0.x) * s
		var n1 := Vector2(-e1.y, e1.x) * s
		var m := n0 + n1
		var k := 1.0 + n0.dot(n1)
		out[i] = p1 + (m / maxf(k, 0.2)) * d
	return out


## Rectangle footprint with chamfered corners (c = chamfer per corner:
## x0z0, x1z0, x1z1, x0z1). Corners with a chamfer under 4 mm stay square.
static func chamfered_rect(x0: float, z0: float, x1: float, z1: float, c: Vector4 = Vector4.ZERO) -> PackedVector2Array:
	var pts := PackedVector2Array()
	var corners := [Vector2(x0, z0), Vector2(x1, z0), Vector2(x1, z1), Vector2(x0, z1)]
	var cs := [c.x, c.y, c.z, c.w]
	for i in 4:
		var p: Vector2 = corners[i]
		var prev: Vector2 = corners[(i + 3) % 4]
		var next: Vector2 = corners[(i + 1) % 4]
		var ch: float = cs[i]
		if ch < 0.004:
			pts.append(p)
		else:
			pts.append(p + (prev - p).normalized() * ch)
			pts.append(p + (next - p).normalized() * ch)
	return pts


## Regular polygon footprint (pillars, bowls): `sides` corners, radius `r`.
static func ngon(center: Vector2, r: float, sides: int, phase: float = 0.0) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for i in sides:
		var a := phase + TAU * float(i) / float(sides)
		pts.append(center + Vector2(cos(a), sin(a)) * r)
	return pts


## A vertical prism over `poly` (x/z) from y0 to y1 with a bevel of
## `bevel` (width = depth) round its top. `tilt` tips the top face:
## height += tilt.x * (x - cx) + tilt.y * (z - cz). `uv_of` maps a world
## point to UV (or null for none). No bottom face (never seen).
static func prism(st: SurfaceTool, poly: PackedVector2Array, y0: float, y1: float, bevel: float, color: Color = Color.WHITE, floor_ao: Vector2 = Vector2(-100.0, 0.0), uv_of: Callable = Callable(), tilt: Vector2 = Vector2.ZERO, sides: bool = true) -> void:
	var n := poly.size()
	var c := Vector2.ZERO
	for p in poly:
		c += p
	c /= float(n)
	var top_poly := inset_polygon(poly, bevel) if bevel > 0.0 else poly
	var y_edge := y1 - bevel
	var h := func(p: Vector2, y: float) -> Vector3:
		return Vector3(p.x, y + tilt.x * (p.x - c.x) + tilt.y * (p.y - c.y), p.y)
	# top face (fan)
	var top: Array[Vector3] = []
	for p in top_poly:
		top.append(h.call(p, y1))
	for i in range(1, n - 1):
		_tri(st, top[0], top[i + 1], top[i], color, floor_ao, uv_of)
	# bevel ring
	if bevel > 0.0:
		for i in n:
			var j := (i + 1) % n
			var a: Vector3 = h.call(poly[i], y_edge)
			var b: Vector3 = h.call(poly[j], y_edge)
			_quad(st, b, a, top[i], top[j], color, floor_ao, uv_of)
	if not sides:
		return
	for i in n:
		var j := (i + 1) % n
		var a2 := Vector3(poly[i].x, y0, poly[i].y)
		var b2 := Vector3(poly[j].x, y0, poly[j].y)
		var a3: Vector3 = h.call(poly[i], y_edge)
		var b3: Vector3 = h.call(poly[j], y_edge)
		_quad(st, b2, a2, a3, b3, color, floor_ao, uv_of)


## Axis-aligned box, all faces but the bottom (EnvKit.box placement: `pos`
## is the bottom centre). Optional bevel round the top.
static func box(st: SurfaceTool, size: Vector3, pos: Vector3, color: Color = Color.WHITE, floor_ao: Vector2 = Vector2(-100.0, 0.0), bevel: float = 0.0, chamfer: float = 0.0) -> void:
	var hx := size.x * 0.5
	var hz := size.z * 0.5
	var poly := chamfered_rect(pos.x - hx, pos.z - hz, pos.x + hx, pos.z + hz, Vector4.ONE * chamfer)
	prism(st, poly, pos.y, pos.y + size.y, bevel, color, floor_ao)


## Closed-top tapered cylinder (n sides) from y0 to y1.
static func cylinder(st: SurfaceTool, center: Vector3, r0: float, r1: float, height: float, sides: int, color: Color = Color.WHITE, floor_ao: Vector2 = Vector2(-100.0, 0.0), top: bool = true) -> void:
	var lo := ngon(Vector2(center.x, center.z), r0, sides)
	var hi := ngon(Vector2(center.x, center.z), r1, sides)
	var y0 := center.y
	var y1 := center.y + height
	for i in sides:
		var j := (i + 1) % sides
		_quad(st, Vector3(lo[j].x, y0, lo[j].y), Vector3(lo[i].x, y0, lo[i].y), Vector3(hi[i].x, y1, hi[i].y), Vector3(hi[j].x, y1, hi[j].y), color, floor_ao, Callable())
	if top:
		for i in range(1, sides - 1):
			_tri(st, Vector3(hi[0].x, y1, hi[0].y), Vector3(hi[i + 1].x, y1, hi[i + 1].y), Vector3(hi[i].x, y1, hi[i].y), color, floor_ao, Callable())


## A round strut from `a` to `b` (tripod legs, poles), open ends.
static func strut(st: SurfaceTool, a: Vector3, b: Vector3, r0: float, r1: float, sides: int, color: Color = Color.WHITE) -> void:
	var axis := (b - a).normalized()
	var ref := Vector3.UP if absf(axis.y) < 0.9 else Vector3.RIGHT
	var u := axis.cross(ref).normalized()
	var v := axis.cross(u).normalized()
	for i in sides:
		var t0 := TAU * float(i) / sides
		var t1 := TAU * float(i + 1) / sides
		var d0 := u * cos(t0) + v * sin(t0)
		var d1 := u * cos(t1) + v * sin(t1)
		var p0 := a + d1 * r0
		var p1 := a + d0 * r0
		var p2 := b + d0 * r1
		var p3 := b + d1 * r1
		if (p1 - p0).cross(p2 - p0).dot(d0 + d1) < 0.0:
			_quad(st, p1, p0, p3, p2, color, Vector2(-100.0, 0.0), Callable())
		else:
			_quad(st, p0, p1, p2, p3, color, Vector2(-100.0, 0.0), Callable())


## Upward-facing quad (x/z rectangle at height y).
static func flat(st: SurfaceTool, rect: Rect2, y: float, color: Color = Color.WHITE, floor_ao: Vector2 = Vector2(-100.0, 0.0), uv_of: Callable = Callable()) -> void:
	var a := Vector3(rect.position.x, y, rect.position.y)
	var b := Vector3(rect.end.x, y, rect.position.y)
	var c := Vector3(rect.end.x, y, rect.end.y)
	var d := Vector3(rect.position.x, y, rect.end.y)
	_quad(st, d, c, b, a, color, floor_ao, uv_of)


## Quad a-b-c-d (counter-clockwise seen from its front), flat-shaded.
static func _quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3, color: Color, floor_ao: Vector2, uv_of: Callable) -> void:
	_tri(st, a, b, c, color, floor_ao, uv_of)
	_tri(st, a, c, d, color, floor_ao, uv_of)


## One triangle a-b-c, counter-clockwise seen from its front (Godot's front
## faces are clockwise in screen space, so the vertices go in as a, c, b).
static func _tri(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, color: Color, floor_ao: Vector2, uv_of: Callable) -> void:
	var nrm := (b - a).cross(c - a)
	if nrm.length_squared() < 1e-14:
		return
	nrm = nrm.normalized()
	for v: Vector3 in [a, c, b]:
		st.set_normal(nrm)
		st.set_color(color)
		st.set_uv2(floor_ao)
		if uv_of.is_valid():
			st.set_uv(uv_of.call(v))
		st.add_vertex(v)


static func begin() -> SurfaceTool:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	return st
