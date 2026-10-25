class_name AIProfile
extends Resource
## Difficulty and personality knobs for CombatAI.

@export var id: StringName = &"normal"
@export var display_name: String = "Normal"
## How stale (in ticks) the AI's view of its opponent is — its reaction time.
@export var reaction_ticks: int = 14
## Ticks between re-plans when nothing urgent happens.
@export var decision_interval: int = 6
@export var aim_error_deg: float = 7.0
## 0..1: how well projectiles and areas are led onto a moving target.
@export var lead_accuracy: float = 0.8
@export var dodge_chance: float = 0.55
@export var guard_chance: float = 0.35
@export var dash_through_chance: float = 0.35
@export var aggression: float = 0.6
## Start focusing below this stamina ratio when it's safe.
@export var focus_threshold: float = 0.35
@export var mistake_chance: float = 0.08
@export var combo_skill: float = 0.6
## Multiplies how long the AI holds back: the bar an attack must clear and
## the gaps between repositioning dashes.
@export var patience: float = 1.0


static func preset(preset_id: StringName) -> AIProfile:
	var p := AIProfile.new()
	p.id = preset_id
	match preset_id:
		&"easy":
			p.display_name = "Easy"
			p.reaction_ticks = 26
			p.decision_interval = 12
			p.aim_error_deg = 16.0
			p.lead_accuracy = 0.3
			p.dodge_chance = 0.2
			p.guard_chance = 0.15
			p.dash_through_chance = 0.15
			p.aggression = 0.4
			p.focus_threshold = 0.45
			p.mistake_chance = 0.25
			p.combo_skill = 0.3
			p.patience = 1.6
		&"hard":
			p.display_name = "Hard"
			p.reaction_ticks = 9
			p.decision_interval = 4
			p.aim_error_deg = 3.0
			p.lead_accuracy = 1.0
			p.dodge_chance = 0.8
			p.guard_chance = 0.55
			p.dash_through_chance = 0.55
			p.aggression = 0.75
			p.focus_threshold = 0.3
			p.mistake_chance = 0.03
			p.combo_skill = 0.9
			p.patience = 0.8
		&"story":
			p.display_name = "Corin"
			p.reaction_ticks = 28
			p.decision_interval = 12
			p.aim_error_deg = 15.0
			p.lead_accuracy = 0.38
			p.dodge_chance = 0.2
			p.guard_chance = 0.16
			p.dash_through_chance = 0.18
			p.aggression = 0.44
			p.focus_threshold = 0.44
			p.mistake_chance = 0.27
			p.combo_skill = 0.34
			p.patience = 1.35
		_:
			p.display_name = "Normal"
	return p
