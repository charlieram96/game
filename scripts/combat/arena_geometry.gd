class_name ArenaGeometry
extends RefCounted
## Flat collision world for battles, on the XZ plane (Vector2(x, z)).
##
## Everything is a circle moving through a rectangle with circle and box
## obstacles. Sweeps are exact (Minkowski sums), so fast dashes and
## projectiles can never tunnel through walls or stones.

const EPS := 0.0005


class Obstacle:
	extends RefCounted
	const CIRCLE := 0
	const BOX := 1
	var kind: int = CIRCLE
	var center: Vector2 = Vector2.ZERO
	var radius: float = 0.5
	var half: Vector2 = Vector2.ONE * 0.5
	var blocks_projectiles: bool = true
	var tag: StringName = &""


class Sweep:
	extends RefCounted
	var hit: bool = false
	var t: float = 1.0
	var normal: Vector2 = Vector2.ZERO
	var obstacle: Obstacle = null
	var is_bounds: bool = false


var bounds: Rect2 = Rect2(-8, -5, 16, 10)
var obstacles: Array[Obstacle] = []


static func from_definition(def: ArenaDefinition) -> ArenaGeometry:
	var g := ArenaGeometry.new()
	g.bounds = Rect2(-def.size * 0.5, def.size)
	for c in def.circles:
		g.add_circle(Vector2(c.x, c.y), c.z)
	for b in def.boxes:
		g.add_box(b.get_center(), b.size * 0.5)
	return g


func add_circle(center: Vector2, radius: float, tag: StringName = &"stone") -> Obstacle:
	var o := Obstacle.new()
	o.kind = Obstacle.CIRCLE
	o.center = center
	o.radius = radius
	o.tag = tag
	obstacles.append(o)
	return o


func add_box(center: Vector2, half: Vector2, tag: StringName = &"box") -> Obstacle:
	var o := Obstacle.new()
	o.kind = Obstacle.BOX
	o.center = center
	o.half = half
	o.tag = tag
	obstacles.append(o)
	return o


# --- Queries ------------------------------------------------------------------

func inner_bounds(r: float) -> Rect2:
	return Rect2(bounds.position + Vector2(r, r), bounds.size - Vector2(r, r) * 2.0)


func is_inside_bounds(p: Vector2, r: float) -> bool:
	var ib := inner_bounds(r)
	return p.x >= ib.position.x - EPS and p.x <= ib.end.x + EPS and p.y >= ib.position.y - EPS and p.y <= ib.end.y + EPS


func overlaps_obstacle(p: Vector2, r: float, projectile_only: bool = false) -> Obstacle:
	for o in obstacles:
		if projectile_only and not o.blocks_projectiles:
			continue
		if o.kind == Obstacle.CIRCLE:
			if p.distance_to(o.center) < o.radius + r - EPS:
				return o
		else:
			var closest := _closest_on_box(p, o)
			if p.distance_to(closest) < r - EPS:
				return o
	return null


func is_circle_free(p: Vector2, r: float) -> bool:
	return is_inside_bounds(p, r) and overlaps_obstacle(p, r) == null


## Push a circle out of obstacles and back inside the bounds.
func push_out(p: Vector2, r: float) -> Vector2:
	var q := p
	for _i in 4:
		var moved := false
		for o in obstacles:
			if o.kind == Obstacle.CIRCLE:
				var d := q - o.center
				var dist := d.length()
				var need := o.radius + r
				if dist < need:
					var n := d / dist if dist > 1e-5 else Vector2.RIGHT
					q = o.center + n * (need + EPS)
					moved = true
			else:
				var closest := _closest_on_box(q, o)
				var d2 := q - closest
				var dist2 := d2.length()
				if dist2 < r:
					var n2: Vector2
					if dist2 > 1e-5:
						n2 = d2 / dist2
						q = closest + n2 * (r + EPS)
					else:
						q = _escape_box(q, o, r)
					moved = true
		var ib := inner_bounds(r)
		var clamped := Vector2(clampf(q.x, ib.position.x, ib.end.x), clampf(q.y, ib.position.y, ib.end.y))
		if clamped != q:
			q = clamped
			moved = true
		if not moved:
			break
	return q


## Earliest contact of a circle of radius `r` moving from `p0` by `delta`.
func sweep(p0: Vector2, delta: Vector2, r: float, projectile: bool = false) -> Sweep:
	var best := Sweep.new()
	if delta.length_squared() < 1e-12:
		return best
	# Arena bounds (the circle center must stay inside the inner rectangle).
	var ib := inner_bounds(r)
	_sweep_bounds(p0, delta, ib, best)
	for o in obstacles:
		if projectile and not o.blocks_projectiles:
			continue
		var res: Sweep
		if o.kind == Obstacle.CIRCLE:
			res = _sweep_circle(p0, delta, o.center, o.radius + r)
		else:
			res = _sweep_box(p0, delta, o, r)
		if res.hit and res.t < best.t:
			best.hit = true
			best.t = res.t
			best.normal = res.normal
			best.obstacle = o
			best.is_bounds = false
	return best


## Moves with up to three slide iterations. Returns the final position.
func move_and_slide(p0: Vector2, delta: Vector2, r: float) -> Vector2:
	var p := p0
	var remaining := delta
	for _i in 3:
		if remaining.length_squared() < 1e-10:
			break
		var s := sweep(p, remaining, r)
		if not s.hit:
			p += remaining
			break
		var travel := maxf(0.0, s.t - 0.001)
		p += remaining * travel
		var rest := remaining * (1.0 - travel)
		# Remove the component going into the surface; keep the slide.
		remaining = rest - s.normal * rest.dot(s.normal)
	return push_out(p, r)


## Straight-line travel that stops at the first wall (no sliding).
## Returns {"pos": Vector2, "hit": bool, "normal": Vector2}.
func move_until_blocked(p0: Vector2, delta: Vector2, r: float, projectile: bool = false) -> Dictionary:
	var s := sweep(p0, delta, r, projectile)
	if not s.hit:
		return {"pos": p0 + delta, "hit": false, "normal": Vector2.ZERO, "t": 1.0}
	var travel := maxf(0.0, s.t - 0.001)
	return {"pos": p0 + delta * travel, "hit": true, "normal": s.normal, "t": travel}


# --- Static geometry helpers ------------------------------------------------------

## Parametric t in [0,1] where segment p0->p1 first comes within `radius` of
## `center`; -1 if it never does. t = 0 if it starts inside.
static func segment_circle_t(p0: Vector2, p1: Vector2, center: Vector2, radius: float) -> float:
	var d := p1 - p0
	var f := p0 - center
	var c := f.dot(f) - radius * radius
	if c <= 0.0:
		return 0.0
	var a := d.dot(d)
	if a < 1e-12:
		return -1.0
	var b := 2.0 * f.dot(d)
	var disc := b * b - 4.0 * a * c
	if disc < 0.0:
		return -1.0
	var t := (-b - sqrt(disc)) / (2.0 * a)
	if t < 0.0 or t > 1.0:
		return -1.0
	return t


static func segment_segment_distance(a0: Vector2, a1: Vector2, b0: Vector2, b1: Vector2) -> float:
	var pa := Geometry2D.get_closest_points_between_segments(a0, a1, b0, b1)
	return pa[0].distance_to(pa[1])


# --- Internals --------------------------------------------------------------------

func _sweep_bounds(p0: Vector2, d: Vector2, ib: Rect2, best: Sweep) -> void:
	var candidates: Array = []
	if d.x > 0.0 and p0.x + d.x > ib.end.x:
		candidates.append([(ib.end.x - p0.x) / d.x, Vector2.LEFT])
	if d.x < 0.0 and p0.x + d.x < ib.position.x:
		candidates.append([(ib.position.x - p0.x) / d.x, Vector2.RIGHT])
	if d.y > 0.0 and p0.y + d.y > ib.end.y:
		candidates.append([(ib.end.y - p0.y) / d.y, Vector2.UP])
	if d.y < 0.0 and p0.y + d.y < ib.position.y:
		candidates.append([(ib.position.y - p0.y) / d.y, Vector2.DOWN])
	for c in candidates:
		var t := clampf(float(c[0]), 0.0, 1.0)
		if t < best.t:
			best.hit = true
			best.t = t
			best.normal = c[1]
			best.is_bounds = true
			best.obstacle = null


static func _sweep_circle(p0: Vector2, d: Vector2, center: Vector2, radius: float) -> Sweep:
	var s := Sweep.new()
	var f := p0 - center
	var c := f.dot(f) - radius * radius
	if c < 0.0:
		# Already overlapping: block only motion that goes further in.
		if f.dot(d) < 0.0:
			s.hit = true
			s.t = 0.0
			s.normal = f.normalized() if f.length_squared() > 1e-10 else -d.normalized()
		return s
	var a := d.dot(d)
	var b := 2.0 * f.dot(d)
	var disc := b * b - 4.0 * a * c
	if disc < 0.0 or a < 1e-12:
		return s
	var t := (-b - sqrt(disc)) / (2.0 * a)
	if t >= 0.0 and t <= 1.0:
		s.hit = true
		s.t = t
		s.normal = (p0 + d * t - center).normalized()
	return s


static func _closest_on_box(p: Vector2, o: Obstacle) -> Vector2:
	return Vector2(
		clampf(p.x, o.center.x - o.half.x, o.center.x + o.half.x),
		clampf(p.y, o.center.y - o.half.y, o.center.y + o.half.y)
	)


static func _escape_box(p: Vector2, o: Obstacle, r: float) -> Vector2:
	# Center is inside the box: leave through the nearest face.
	var dx_left := p.x - (o.center.x - o.half.x)
	var dx_right := (o.center.x + o.half.x) - p.x
	var dy_top := p.y - (o.center.y - o.half.y)
	var dy_bottom := (o.center.y + o.half.y) - p.y
	var m := minf(minf(dx_left, dx_right), minf(dy_top, dy_bottom))
	if m == dx_left:
		return Vector2(o.center.x - o.half.x - r - EPS, p.y)
	if m == dx_right:
		return Vector2(o.center.x + o.half.x + r + EPS, p.y)
	if m == dy_top:
		return Vector2(p.x, o.center.y - o.half.y - r - EPS)
	return Vector2(p.x, o.center.y + o.half.y + r + EPS)


static func _sweep_box(p0: Vector2, d: Vector2, o: Obstacle, r: float) -> Sweep:
	var s := Sweep.new()
	var closest := _closest_on_box(p0, o)
	var sep := p0 - closest
	if sep.length() < r:
		# Starting in contact: block motion into the box only.
		var n := sep.normalized() if sep.length_squared() > 1e-10 else -d.normalized()
		if n.dot(d) < 0.0:
			s.hit = true
			s.t = 0.0
			s.normal = n
		return s
	var lo := o.center - o.half
	var hi := o.center + o.half
	var best_t := 2.0
	var best_n := Vector2.ZERO
	# Faces (expanded by r), valid only within the box's extent on the other axis.
	if d.x > 0.0:
		var t := (lo.x - r - p0.x) / d.x
		var y := p0.y + d.y * t
		if t >= 0.0 and t <= 1.0 and y >= lo.y and y <= hi.y and t < best_t:
			best_t = t
			best_n = Vector2.LEFT
	if d.x < 0.0:
		var t := (hi.x + r - p0.x) / d.x
		var y := p0.y + d.y * t
		if t >= 0.0 and t <= 1.0 and y >= lo.y and y <= hi.y and t < best_t:
			best_t = t
			best_n = Vector2.RIGHT
	if d.y > 0.0:
		var t := (lo.y - r - p0.y) / d.y
		var x := p0.x + d.x * t
		if t >= 0.0 and t <= 1.0 and x >= lo.x and x <= hi.x and t < best_t:
			best_t = t
			best_n = Vector2.UP
	if d.y < 0.0:
		var t := (hi.y + r - p0.y) / d.y
		var x := p0.x + d.x * t
		if t >= 0.0 and t <= 1.0 and x >= lo.x and x <= hi.x and t < best_t:
			best_t = t
			best_n = Vector2.DOWN
	# Rounded corners.
	for corner in [lo, Vector2(hi.x, lo.y), hi, Vector2(lo.x, hi.y)]:
		var cs := _sweep_circle(p0, d, corner, r)
		if cs.hit and cs.t < best_t:
			best_t = cs.t
			best_n = cs.normal
	if best_t <= 1.0:
		s.hit = true
		s.t = best_t
		s.normal = best_n
	return s
