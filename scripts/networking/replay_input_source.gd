class_name ReplayInputSource
extends InputSource
## Plays back recorded commands (tests, determinism checks, kill-cams later).

var commands: Array[InputCommand] = []
var _index := 0


func _init(recorded: Array[InputCommand] = []) -> void:
	commands = recorded


func get_command(_sim: BattleSim, _team: int) -> InputCommand:
	if _index >= commands.size():
		return InputCommand.new()
	var c := commands[_index]
	_index += 1
	return c


func reset() -> void:
	_index = 0
