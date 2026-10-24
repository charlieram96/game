class_name LineWaveComponent
extends AbilityComponent
## A telegraphed line along the aim direction; after the telegraph a
## damaging front travels outward along it (e.g. Fault Line).

@export var length: float = 9.0
@export var width: float = 1.1
@export var telegraph_ticks: int = 30
@export var travel_speed: float = 20.0  ## units/second of the eruption front.
@export var segment_length: float = 1.4  ## Depth of the dangerous band.
@export var start_offset: float = 0.4
@export var hit: HitSpec
@export var visual: StringName = &""


func execute(sim: BattleSim, caster: Fighter, ability: AbilityDefinition, _phase_tick: int) -> void:
	var v := sim.new_volume(caster, ability, hit)
	v.motion = HitVolume.Motion.WAVE
	v.shape = HitVolume.Shape.BOX
	v.dir = caster.ability_dir
	v.origin = caster.pos + v.dir * start_offset
	# Clip the line at walls so the telegraph never lies about its reach.
	var clipped := sim.geometry.move_until_blocked(v.origin, v.dir * length, 0.05, true)
	v.wave_total = v.origin.distance_to(clipped["pos"])
	v.pos = v.origin
	v.length = 0.0
	v.width = width
	v.wave_speed = travel_speed
	v.segment_length = segment_length
	v.delay_ticks = telegraph_ticks
	var travel_ticks := int(ceil(v.wave_total / maxf(0.1, travel_speed) * CombatConst.TICK_RATE))
	v.active_ticks = travel_ticks + 4
	v.visual = visual
	v.telegraph = true
	sim.add_volume(v)


func telegraph_shape(caster: Fighter, _ability: AbilityDefinition) -> Dictionary:
	return {"shape": HitVolume.Shape.BOX, "pos": caster.pos + caster.ability_dir * start_offset, "dir": caster.ability_dir, "length": length, "width": width}
