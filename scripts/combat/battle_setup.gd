class_name BattleSetup
extends RefCounted
## Everything needed to start a battle. Built by the game layer (story, free
## battle, versus, tests) and handed to BattleSim / the battle scene.

enum Mode { STORY, FREE, VERSUS, TRAINING, SIM }

var mode: Mode = Mode.FREE
var ruleset: BattleRuleset = BattleRuleset.make(BattleRuleset.Kind.PVE)
var arena: ArenaDefinition = ArenaDefinition.ringstones()
## team index -> Array of {"creature": CreatureInstance, "species": CreatureDefinition}
var teams: Array = [[], []]
var team_names: Array[String] = ["Player", "Rival"]
var countdown: bool = true
var time_limit: bool = true
## Training: team 1 can't be knocked out (HP refills) and there is no timer.
var training: bool = false
var allow_switching: bool = false
## Which team is "the enemy" for PvE multipliers (-1 = none).
var enemy_team: int = 1
## AI difficulty profile id per team ("" = human-controlled).
var ai: Array[StringName] = [&"", &"normal"]
var story_battle_id: StringName = &""
var seed: int = 1
var metadata: Dictionary = {}


func add_creature(team: int, creature: CreatureInstance, species: CreatureDefinition) -> void:
	(teams[team] as Array).append({"creature": creature, "species": species})


func team_size(team: int) -> int:
	return (teams[team] as Array).size()
