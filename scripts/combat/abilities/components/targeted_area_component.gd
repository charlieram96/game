class_name TargetedAreaComponent
extends AbilityComponent
## A delayed area at the aimed ground point: a visible telegraph for
## `delay_ticks`, then a burst (circle, or ring when inner_radius > 0).

@export var radius: float = 1.6
@export var inner_radius: float = 0.0
@export var delay_ticks: int = 40
@export var active_ticks: int = 6
@export var hit: HitSpec
@export var visual: StringName = &""


func execute(sim: BattleSim, caster: Fighter, ability: AbilityDefinition, _phase_tick: int) -> void:
	var v := sim.new_volume(caster, ability, hit)
	v.motion = HitVolume.Motion.STATIC
	v.shape = HitVolume.Shape.RING if inner_radius > 0.0 else HitVolume.Shape.CIRCLE
	v.pos = caster.ability_point
	v.dir = caster.ability_dir
	v.radius = radius
	v.inner_radius = inner_radius
	v.delay_ticks = delay_ticks
	v.active_ticks = active_ticks
	v.visual = visual
	v.telegraph = true
	sim.add_volume(v)


func telegraph_shape(caster: Fighter, _ability: AbilityDefinition) -> Dictionary:
	return {"shape": HitVolume.Shape.CIRCLE, "pos": caster.ability_point, "dir": caster.ability_dir, "radius": radius}
