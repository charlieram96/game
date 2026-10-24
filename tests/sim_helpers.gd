class_name SimHelpers
extends RefCounted
## Builders for deterministic battle-simulation tests.

const EMBERLYN := "res://resources/creatures/emberlyn.tres"
const STONEBACK := "res://resources/creatures/stoneback.tres"
const TOTEM := "res://resources/creatures/training_totem.tres"
## Dash directions (Cardinal.DIRS indices).
const E := 0
const S := 1
const W := 2
const N := 3


static func species(path: String) -> CreatureDefinition:
	return load(path)


static func creature(path: String, level: int = 50) -> Dictionary:
	var sp := species(path)
	return {"creature": CreatureInstance.create(sp, level, 1234), "species": sp}


## A ready-to-fight sim (no countdown, no timer) on an open arena whose
## cell centres sit on whole numbers (so (-5, 0) and (5, 0) are centres).
static func make_sim(a_path: String = EMBERLYN, b_path: String = STONEBACK, open_arena: bool = true, kind: BattleRuleset.Kind = BattleRuleset.Kind.RANKED) -> BattleSim:
	var setup := BattleSetup.new()
	setup.ruleset = BattleRuleset.make(kind)
	setup.countdown = false
	setup.time_limit = false
	if open_arena:
		var arena := ArenaDefinition.new()
		arena.size = Vector2(31, 21)
		arena.spawn_team0 = Vector2(-5, 0)
		arena.spawn_team1 = Vector2(5, 0)
		setup.arena = arena
	var a := creature(a_path)
	var b := creature(b_path)
	setup.add_creature(0, a["creature"], a["species"])
	setup.add_creature(1, b["creature"], b["species"])
	return BattleSim.new(setup)


static func cmd(held: int = 0, pressed: int = 0, aim: Vector2 = Vector2.ZERO, aim_distance: float = 0.0) -> InputCommand:
	var c := InputCommand.new()
	c.held = held
	c.pressed = pressed
	if aim != Vector2.ZERO:
		c.set_aim(aim, aim_distance)
	return c


## A command that requests a dash of `cells` cells in direction `dir` (E/S/W/N).
static func dash_cmd(dir: int, cells: int, held: int = 0, pressed: int = 0) -> InputCommand:
	var c := cmd(held, pressed)
	c.set_dash(dir, cells)
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
static func tap(sim: BattleSim, team: int, bits: int, aim: Vector2 = Vector2.ZERO, aim_distance: float = 0.0) -> Array[BattleEvent]:
	var c := cmd(bits, bits, aim, aim_distance)
	var inputs := {team: c}
	sim.step(inputs)
	return sim.events.duplicate()


## Requests a dash for one tick (the press is buffered like any input).
static func dash(sim: BattleSim, team: int, dir: int, cells: int) -> Array[BattleEvent]:
	sim.step({team: dash_cmd(dir, cells)})
	return sim.events.duplicate()


## Dashes and keeps stepping until the dasher is idle again (or `max_ticks`).
static func dash_and_settle(sim: BattleSim, team: int, dir: int, cells: int, max_ticks: int = 90) -> Array[BattleEvent]:
	var all := dash(sim, team, dir, cells)
	var f := sim.active_fighter(team)
	for i in max_ticks:
		if f.state == FighterSM.State.IDLE and i > 0:
			break
		sim.step({})
		all.append_array(sim.events)
	return all


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
