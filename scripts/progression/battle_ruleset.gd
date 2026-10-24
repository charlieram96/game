class_name BattleRuleset
extends Resource
## Which statistics a battle uses.
##
## RANKED  — every creature is normalized to the same level; no mastery
##           numbers; only competitive-legal variants. Species identity
##           (movement, dash, stamina, kit) is preserved.
## CASUAL  — consensual duels with real progression; level gap is displayed.
## PVE     — full progression vs wild kith, trainers and bosses.

enum Kind { RANKED, CASUAL, PVE }

@export var kind: Kind = Kind.PVE
@export var display_name: String = ""
@export var normalized_level: int = 50
@export var allow_mastery_bonuses: bool = true
@export var allow_illegal_variants: bool = true
@export var match_time_sec: int = 120
@export var damage_scale: float = 1.0
## Extra multipliers for PvE enemies (bosses can use > 1).
@export var enemy_hp_mult: float = 1.0
@export var enemy_damage_mult: float = 1.0


func effective_level(real_level: int) -> int:
	if kind == Kind.RANKED:
		return normalized_level
	return real_level


static func make(k: Kind) -> BattleRuleset:
	var r := BattleRuleset.new()
	r.kind = k
	match k:
		Kind.RANKED:
			r.display_name = "Ranked"
			r.allow_mastery_bonuses = false
			r.allow_illegal_variants = false
		Kind.CASUAL:
			r.display_name = "Casual Duel"
			r.allow_mastery_bonuses = true
			r.allow_illegal_variants = true
		Kind.PVE:
			r.display_name = "Adventure"
			r.allow_mastery_bonuses = true
			r.allow_illegal_variants = true
	return r
