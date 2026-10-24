class_name TrainingAI
extends InputSource
## Scripted sparring partner for the tutorial (a training totem).
## Modes are switched by the tutorial director.

enum Mode { IDLE, SHOOT, GUARD }

var mode: Mode = Mode.IDLE
var shoot_interval_ticks := 100
var _last_shot := -1000
var _prev_held := 0


func reset() -> void:
	_last_shot = -1000
	_prev_held = 0


func get_command(sim: BattleSim, team: int) -> InputCommand:
	var cmd := InputCommand.new()
	var me := sim.active_fighter(team)
	var foe := sim.active_fighter(1 - team)
	if me == null or foe == null or sim.phase != BattleSim.Phase.FIGHT:
		return cmd
	var to := foe.pos - me.pos
	if to.length() > 0.01:
		cmd.set_aim(to.normalized(), to.length())
	var held := 0
	match mode:
		Mode.SHOOT:
			if sim.tick - _last_shot >= shoot_interval_ticks and FighterSM.is_actionable(me.state):
				_last_shot = sim.tick
				held |= InputCommand.ABILITY_1
		Mode.GUARD:
			held |= InputCommand.GUARD
	cmd.held = held
	cmd.pressed = InputCommand.edges(_prev_held, held)
	_prev_held = held
	return cmd
