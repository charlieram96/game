class_name BattleTransport
extends RefCounted
## Where the authoritative simulation runs.
##
## LocalBattleTransport (v0) steps a BattleSim in-process. The planned
## NetworkBattleTransport will send this client's InputCommands (with
## sequence numbers) to a headless Godot battle server over ENet, receive
## authoritative snapshots + events, predict the local creature and
## reconcile — without the presentation layer changing. See docs/architecture.md.

signal tick_completed(events: Array[BattleEvent])


func start(_setup: BattleSetup) -> void:
	pass


## The input source for each team (local player, AI, remote).
func set_input_source(_team: int, _source: InputSource) -> void:
	pass


func step() -> void:
	pass


## The simulation the presentation should render (local: authoritative;
## online: the predicted/interpolated client view).
func view_sim() -> BattleSim:
	return null


func restart() -> void:
	pass
