class_name SelfAreaComponent
extends AbilityComponent
## A burst centered on the caster (e.g. Ground Pound). Pair with the
## ability's `telegraph` flag to show the radius during startup.

@export var radius: float = 2.2
@export var active_ticks: int = 3
@export var hit: HitSpec
@export var visual: StringName = &""


func execute(sim: BattleSim, caster: Fighter, ability: AbilityDefinition, _phase_tick: int) -> void:
	var v := sim.new_volume(caster, ability, hit)
	v.motion = HitVolume.Motion.STATIC
	v.shape = HitVolume.Shape.CIRCLE
	v.pos = caster.pos
	v.dir = caster.ability_dir
	v.radius = radius
	v.active_ticks = active_ticks
	v.visual = visual
	sim.add_volume(v)
	sim.emit(BattleEvent.AREA_BURST, caster, -1, caster.pos, {"radius": radius, "visual": visual, "ability": ability.id})


func telegraph_shape(caster: Fighter, _ability: AbilityDefinition) -> Dictionary:
	return {"shape": HitVolume.Shape.CIRCLE, "pos": caster.pos, "dir": caster.ability_dir, "radius": radius, "follow": true}
