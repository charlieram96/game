class_name InputSource
extends RefCounted
## Produces one InputCommand per simulation tick for one team.
##
## Local keyboard/touch players, the AI, recorded replays and (later) remote
## players over the network all implement this, so the combat rules never
## know where intent comes from.


func get_command(_sim: BattleSim, _team: int) -> InputCommand:
	return InputCommand.new()


func reset() -> void:
	pass
