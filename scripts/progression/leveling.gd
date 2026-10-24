class_name Leveling
extends RefCounted
## Creature level curve (1-100) and experience rewards.


## Experience needed to go from `level` to `level + 1`.
static func xp_to_next(level: int) -> int:
	if level >= CreatureInstance.MAX_LEVEL:
		return 0
	return int(round(12.0 + 6.0 * pow(float(level), 1.45)))


## Adds experience and returns the list of levels gained (may be empty).
static func add_xp(creature: CreatureInstance, amount: int) -> Array[int]:
	var gained: Array[int] = []
	if amount <= 0 or creature.level >= CreatureInstance.MAX_LEVEL:
		return gained
	creature.xp += amount
	while creature.level < CreatureInstance.MAX_LEVEL and creature.xp >= xp_to_next(creature.level):
		creature.xp -= xp_to_next(creature.level)
		creature.level += 1
		gained.append(creature.level)
	if creature.level >= CreatureInstance.MAX_LEVEL:
		creature.xp = 0
	return gained


## XP awarded for defeating an opponent. Story/PvE rewards scale with the
## opponent's level and shrink when the winner heavily out-levels it.
static func battle_xp(winner_level: int, loser_level: int, won: bool) -> int:
	var base := 18.0 + loser_level * 4.0
	var gap := float(loser_level - winner_level)
	var mult := clampf(1.0 + gap * 0.08, 0.25, 2.0)
	if not won:
		mult *= 0.35
	return maxi(1, int(round(base * mult)))
