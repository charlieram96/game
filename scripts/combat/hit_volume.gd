class_name HitVolume
extends RefCounted
## A live hitbox in the simulation: projectile, melee swing, delayed area,
## travelling line wave. Created by ability components; owned by the sim.

enum Shape { CIRCLE, CONE, BOX, RING }
enum Motion {
	STATIC,  ## Stays where it was spawned (areas, delayed bursts).
	PROJECTILE,  ## Moves with velocity; dies on walls or at max travel.
	ATTACHED,  ## Follows its owner (melee swings).
	WAVE,  ## A box that sweeps forward from an origin (Fault Line).
}

var id: int = 0
var owner_id: int = -1
var team: int = 0
var ability: AbilityDefinition
var hit: HitSpec
var element: StringName = &"neutral"
var shape: Shape = Shape.CIRCLE
var motion: Motion = Motion.STATIC

var pos: Vector2 = Vector2.ZERO
var prev_pos: Vector2 = Vector2.ZERO
var dir: Vector2 = Vector2.RIGHT
var radius: float = 0.5
var inner_radius: float = 0.0
var half_angle: float = PI / 4.0
var length: float = 1.0
var width: float = 1.0
var forward_offset: float = 0.0

var velocity: Vector2 = Vector2.ZERO
var travel: float = 0.0
var max_travel: float = 10.0

var age: int = 0
## Ticks before the volume becomes dangerous (telegraph window).
var delay_ticks: int = 0
## Ticks the volume stays dangerous after the delay (projectiles ignore this).
var active_ticks: int = 1

var clash_weight: int = 0
var pierce: bool = false
var hits: Dictionary = {}  # fighter id -> tick of last hit
var dead: bool = false
var cancel_with_owner: bool = false

# Wave motion
var origin: Vector2 = Vector2.ZERO
var wave_front: float = 0.0
var wave_speed: float = 0.0
var wave_total: float = 0.0
var segment_length: float = 1.0

var visual: StringName = &""
var telegraph: bool = false


func is_projectile() -> bool:
	return motion == Motion.PROJECTILE


func is_live() -> bool:
	if dead:
		return false
	if motion == Motion.PROJECTILE:
		return age >= delay_ticks
	return age >= delay_ticks and age < delay_ticks + active_ticks


func ticks_until_live() -> int:
	return maxi(0, delay_ticks - age)


## Does the volume overlap a body circle at `p` with radius `r`?
func overlaps(p: Vector2, r: float) -> bool:
	match shape:
		Shape.CIRCLE:
			return pos.distance_to(p) <= radius + r
		Shape.RING:
			var d := pos.distance_to(p)
			return d <= radius + r and d >= inner_radius - r
		Shape.CONE:
			var to := p - pos
			var dist := to.length()
			if dist <= r:
				return true
			if dist > radius + r:
				return false
			var ang := absf(dir.angle_to(to))
			var margin := asin(clampf(r / dist, 0.0, 1.0))
			return ang <= half_angle + margin
		Shape.BOX:
			var local := p - pos
			var fwd := dir
			var side := CombatConst.perpendicular(dir)
			var lx := local.dot(fwd)
			var ly := local.dot(side)
			var cx := clampf(lx, 0.0, length)
			var cy := clampf(ly, -width * 0.5, width * 0.5)
			return Vector2(lx - cx, ly - cy).length() <= r
	return false


## Projectiles: swept test along prev_pos -> pos so fast shots never skip a target.
func swept_overlaps(p: Vector2, r: float) -> bool:
	if motion != Motion.PROJECTILE:
		return overlaps(p, r)
	return ArenaGeometry.segment_circle_t(prev_pos, pos, p, radius + r) >= 0.0


## The ground-space description used by telegraph rendering and the AI.
func describe() -> Dictionary:
	return {
		"id": id,
		"shape": shape,
		"motion": motion,
		"pos": pos,
		"dir": dir,
		"radius": radius,
		"inner_radius": inner_radius,
		"half_angle": half_angle,
		"length": length,
		"width": width,
		"delay": delay_ticks,
		"age": age,
		"origin": origin,
		"wave_total": wave_total,
		"visual": visual,
		"team": team,
	}
