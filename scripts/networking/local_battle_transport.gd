class_name LocalBattleTransport
extends BattleTransport
## Runs the authoritative simulation locally (single player vs AI, local
## versus, training). Sequence numbers are stamped exactly as a server would
## expect them, so the same command stream could be replayed remotely.

var sim: BattleSim
var sources: Array[InputSource] = [null, null]
var _sequence: Array[int] = [0, 0]
## Optional recording of every command fed to the sim (replays/debugging).
var recording: Array = [[], []]
var record_inputs := false


func start(setup: BattleSetup) -> void:
	sim = BattleSim.new(setup)
	_sequence = [0, 0]
	recording = [[], []]


func set_input_source(team: int, source: InputSource) -> void:
	sources[team] = source


func step() -> void:
	var inputs := {}
	for team in 2:
		var src := sources[team]
		var cmd: InputCommand = src.get_command(sim, team) if src else InputCommand.new()
		_sequence[team] += 1
		cmd.sequence = _sequence[team]
		cmd.tick = sim.tick + 1
		inputs[team] = cmd
		if record_inputs:
			(recording[team] as Array).append(cmd.copy())
	sim.step(inputs)
	tick_completed.emit(sim.events)


func view_sim() -> BattleSim:
	return sim


func restart() -> void:
	sim.reset()
	_sequence = [0, 0]
	recording = [[], []]
	for src in sources:
		if src:
			src.reset()
