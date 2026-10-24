class_name ProjectileComponent
extends AbilityComponent
## Fires a straight projectile along the ability direction.

@export var speed: float = 14.0  ## units/second
@export var radius: float = 0.25
@export var max_range: float = 9.0
@export var spawn_offset: float = 0.5  ## Distance in front of the caster.
## Projectile clashes: heavier projectiles destroy lighter ones and continue.
@export var clash_weight: int = 1
@export var pierce: bool = false
@export var hit: HitSpec
@export var visual: StringName = &""


func execute(sim: BattleSim, caster: Fighter, ability: AbilityDefinition, _phase_tick: int) -> void:
	var v := sim.new_volume(caster, ability, hit)
	v.motion = HitVolume.Motion.PROJECTILE
	v.shape = HitVolume.Shape.CIRCLE
	v.dir = caster.ability_dir
	v.radius = radius
	# Spawn just in front, but never inside a wall.
	var spawn := sim.geometry.move_until_blocked(caster.pos, v.dir * spawn_offset, radius, true)
	v.pos = spawn["pos"]
	v.prev_pos = caster.pos
	v.velocity = v.dir * speed
	v.max_travel = max_range
	v.clash_weight = clash_weight
	v.pierce = pierce
	v.visual = visual
	sim.add_volume(v)


func telegraph_shape(caster: Fighter, _ability: AbilityDefinition) -> Dictionary:
	return {"shape": HitVolume.Shape.BOX, "pos": caster.pos, "dir": caster.ability_dir, "length": max_range, "width": radius * 2.0}
