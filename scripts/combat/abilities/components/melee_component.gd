class_name MeleeComponent
extends AbilityComponent
## A hitbox attached to the caster for the ability's active frames
## (circle in front, cone/arc, or rectangle).

enum MeleeShape { CIRCLE, CONE, BOX }

@export var shape: MeleeShape = MeleeShape.CIRCLE
@export var radius: float = 1.0  ## CIRCLE radius / CONE reach.
@export var angle_deg: float = 90.0  ## CONE total angle.
@export var length: float = 1.5  ## BOX length.
@export var width: float = 1.0  ## BOX width.
@export var forward_offset: float = 0.6  ## Hitbox origin in front of the caster.
## 0 = lasts for the ability's active_ticks.
@export var active_ticks: int = 0
@export var hit: HitSpec
@export var visual: StringName = &""


func execute(sim: BattleSim, caster: Fighter, ability: AbilityDefinition, _phase_tick: int) -> void:
	var v := sim.new_volume(caster, ability, hit)
	v.motion = HitVolume.Motion.ATTACHED
	v.cancel_with_owner = true
	_shape(v, caster.pos, caster.ability_dir)
	v.active_ticks = active_ticks if active_ticks > 0 else ability.active_ticks
	v.visual = visual
	sim.add_volume(v)


## Would this hitbox, swung from `from` along `dir`, touch a body of radius
## `r` at `p`? (The AI checks its reach with this.)
func reaches(from: Vector2, dir: Vector2, p: Vector2, r: float) -> bool:
	var v := HitVolume.new()
	_shape(v, from, dir)
	return v.overlaps(p, r)


func _shape(v: HitVolume, from: Vector2, dir: Vector2) -> void:
	v.dir = dir
	v.forward_offset = forward_offset
	v.pos = from + dir * forward_offset
	match shape:
		MeleeShape.CIRCLE:
			v.shape = HitVolume.Shape.CIRCLE
			v.radius = radius
		MeleeShape.CONE:
			v.shape = HitVolume.Shape.CONE
			v.radius = radius
			v.half_angle = deg_to_rad(angle_deg) * 0.5
		MeleeShape.BOX:
			v.shape = HitVolume.Shape.BOX
			v.length = length
			v.width = width


func telegraph_shape(caster: Fighter, _ability: AbilityDefinition) -> Dictionary:
	var origin := caster.pos + caster.ability_dir * forward_offset
	match shape:
		MeleeShape.CONE:
			return {"shape": HitVolume.Shape.CONE, "pos": origin, "dir": caster.ability_dir, "radius": radius, "half_angle": deg_to_rad(angle_deg) * 0.5}
		MeleeShape.BOX:
			return {"shape": HitVolume.Shape.BOX, "pos": origin, "dir": caster.ability_dir, "length": length, "width": width}
	return {"shape": HitVolume.Shape.CIRCLE, "pos": origin, "dir": caster.ability_dir, "radius": radius}
