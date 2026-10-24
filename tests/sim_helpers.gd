class_name SimHelpers
extends RefCounted
## Builders for deterministic battle-simulation tests.

const EMBERLYN := "res://resources/creatures/emberlyn.tres"
const STONEBACK := "res://resources/creatures/stoneback.tres"
const TOTEM := "res://resources/creatures/training_totem.tres"


static func species(path: String) -> CreatureDefinition:
	return load(path)


static func creature(path: String, level: int = 50) -> Dictionary:
	var sp := species(path)
	return {"creature": CreatureInstance.create(sp, level, 1234), "species": sp}


## A ready-to-fight sim (no countdown, no timer) on an open arena.
static func make_sim(a_path: String = EMBERLYN, b_path: String = STONEBACK, open_arena: bool = true, kind: BattleRuleset.Kind = BattleRuleset.Kind.RANKED) -> BattleSim:
	var setup := BattleSetup.new()
	setup.ruleset = BattleRuleset.make(kind)
	setup.countdown = false
	setup.time_limit = false
	if open_arena:
		var arena := ArenaDefinition.new()
		arena.size = Vector2(30, 20)
		arena.spawn_team0 = Vector2(-5, 0)
		arena.spawn_team1 = Vector2(5, 0)
		setup.arena = arena
	var a := creature(a_path)
	var b := creature(b_path)
	setup.add_creature(0, a["creature"], a["species"])
	setup.add_creature(1, b["creature"], b["species"])
	return BattleSim.new(setup)


static func cmd(move_dir: int = -1, held: int = 0, pressed: int = 0, aim: Vector2 = Vector2.ZERO, aim_distance: float = 0.0, axis_hint: int = Cardinal.AXIS_UNKNOWN) -> InputCommand:
	var c := InputCommand.new()
	c.move_dir = move_dir
	c.held = held
	c.pressed = pressed
	c.axis_hint = axis_hint
	if aim != Vector2.ZERO:
		c.set_aim(aim, aim_distance)
	return c


static func idle() -> InputCommand:
	return InputCommand.new()


## Step `ticks` times with fixed commands for team 0 and team 1.
static func run(sim: BattleSim, ticks: int, c0: InputCommand = null, c1: InputCommand = null) -> Array[BattleEvent]:
	var all: Array[BattleEvent] = []
	for i in ticks:
		var inputs := {}
		if c0:
			inputs[0] = c0
		if c1:
			inputs[1] = c1
		sim.step(inputs)
		all.append_array(sim.events)
	return all


## Press (one tick) then release.
static func tap(sim: BattleSim, team: int, bits: int, move_dir: int = -1, aim: Vector2 = Vector2.ZERO, aim_distance: float = 0.0, axis_hint: int = Cardinal.AXIS_UNKNOWN) -> Array[BattleEvent]:
	var c := cmd(move_dir, bits, bits, aim, aim_distance, axis_hint)
	var inputs := {team: c}
	sim.step(inputs)
	return sim.events.duplicate()


static func events_of(events: Array[BattleEvent], type: StringName) -> Array[BattleEvent]:
	var out: Array[BattleEvent] = []
	for e in events:
		if e.type == type:
			out.append(e)
	return out


static func place(sim: BattleSim, team: int, pos: Vector2, facing: Vector2 = Vector2.ZERO) -> Fighter:
	var f := sim.active_fighter(team)
	f.pos = pos
	f.prev_pos = pos
	f.vel = Vector2.ZERO
	if facing != Vector2.ZERO:
		f.facing = facing
		f.aim = facing
		f.cardinal_facing = Cardinal.snap(facing)
	return f
