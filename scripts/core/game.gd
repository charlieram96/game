extends Node
## Game flow (autoload "Game"): scene routing with fades, battle setup and
## hand-off, progression after battles, play-time tracking.

const TITLE_SCENE := "res://scenes/ui/title.tscn"
const WORLD_SCENE := "res://scenes/world/mossford.tscn"
const BATTLE_SCENE := "res://scenes/combat/battle.tscn"

var last_result: Dictionary = {}
var _pending_battle: BattleSetup = null
var _battle_return := ""
var _fade_layer: CanvasLayer
var _fade_rect: ColorRect
var _busy := false


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_fade_layer = CanvasLayer.new()
	_fade_layer.layer = 100
	add_child(_fade_layer)
	_fade_rect = ColorRect.new()
	_fade_rect.color = Color(0.03, 0.02, 0.05, 0.0)
	_fade_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_fade_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_fade_layer.add_child(_fade_rect)


func _process(delta: float) -> void:
	if SaveService.profile and not get_tree().paused:
		SaveService.profile.play_time_sec += delta


# --- Scene routing --------------------------------------------------------------------

func goto_scene(path: String, fade_time: float = 0.35) -> void:
	if _busy:
		return
	_busy = true
	get_tree().paused = false
	var tw := create_tween()
	tw.tween_property(_fade_rect, "color:a", 1.0, fade_time)
	await tw.finished
	get_tree().change_scene_to_file(path)
	await get_tree().process_frame
	await get_tree().process_frame
	var tw2 := create_tween()
	tw2.tween_property(_fade_rect, "color:a", 0.0, fade_time)
	_busy = false


func flash_white(duration: float = 0.25) -> void:
	_fade_rect.color = Color(1, 1, 1, 0.8)
	var tw := create_tween()
	tw.tween_property(_fade_rect, "color", Color(1, 1, 1, 0.0), duration)
	tw.tween_callback(func() -> void: _fade_rect.color = Color(0.03, 0.02, 0.05, 0.0))


# --- Battles -------------------------------------------------------------------------------

func start_battle(setup: BattleSetup, return_scene: String = "") -> void:
	_pending_battle = setup
	_battle_return = return_scene
	Audio.sfx(&"fight_start", -6.0)
	goto_scene(BATTLE_SCENE, 0.45)


func take_pending_battle() -> BattleSetup:
	var s := _pending_battle
	_pending_battle = null
	return s


func return_from_battle(result: Dictionary) -> void:
	last_result = result
	Events.battle_finished.emit(result)
	goto_scene(_battle_return if _battle_return != "" else TITLE_SCENE)


func abandon_battle(_setup: BattleSetup) -> void:
	last_result = {"abandoned": true}
	goto_scene(_battle_return if _battle_return != "" else TITLE_SCENE)


## Free battle: ranked-style normalized stats so any pairing is fair.
func quick_battle_setup(player_species: StringName, enemy_species: StringName, difficulty: StringName, arena_id: StringName = &"ringstones") -> BattleSetup:
	var s := BattleSetup.new()
	s.mode = BattleSetup.Mode.FREE
	s.ruleset = BattleRuleset.make(BattleRuleset.Kind.RANKED)
	s.ruleset.display_name = "Free Battle"
	s.arena = ArenaDefinition.by_id(arena_id)
	var mine := _player_creature_of(player_species)
	s.add_creature(0, mine, Registry.get_species(player_species))
	s.add_creature(1, Registry.make_creature(enemy_species, 50), Registry.get_species(enemy_species))
	s.ai = [&"", difficulty]
	s.team_names = [_player_name(), "Wild challenger"]
	s.metadata = {"trainer_sprites": ["explorer", ""], "lighting": "golden"}
	return s


func versus_setup(p1_species: StringName, p2_species: StringName) -> BattleSetup:
	var s := quick_battle_setup(p1_species, p2_species, &"")
	s.mode = BattleSetup.Mode.VERSUS
	s.ai = [&"", &""]
	s.ruleset.display_name = "Local Versus"
	s.team_names = ["Player 1", "Player 2"]
	s.metadata = {"trainer_sprites": ["explorer", "corin"], "lighting": "golden"}
	return s


func training_setup() -> BattleSetup:
	var s := BattleSetup.new()
	s.mode = BattleSetup.Mode.TRAINING
	s.training = true
	s.countdown = false
	s.time_limit = false
	s.ruleset = BattleRuleset.make(BattleRuleset.Kind.PVE)
	s.ruleset.display_name = "Training"
	s.arena = ArenaDefinition.training_yard()
	s.add_creature(0, _player_creature_of(&"emberlyn"), Registry.get_species(&"emberlyn"))
	s.add_creature(1, Registry.make_creature(&"training_totem", 5), Registry.get_species(&"training_totem"))
	s.ai = [&"", &""]
	s.story_battle_id = &"training"
	s.metadata = {"trainer_sprites": ["explorer", "hesper"], "lighting": "day", "music": "village_theme"}
	return s


## The Kindling duel against Corin's Stoneback.
func story_duel_setup(relaxed: bool = false) -> BattleSetup:
	var s := BattleSetup.new()
	s.mode = BattleSetup.Mode.STORY
	s.ruleset = BattleRuleset.make(BattleRuleset.Kind.PVE)
	s.ruleset.display_name = "The Kindling"
	s.ruleset.match_time_sec = 150
	s.arena = ArenaDefinition.ringstones()
	var mine := _player_creature_of(&"emberlyn")
	s.add_creature(0, mine, Registry.get_species(&"emberlyn"))
	var biscuit := Registry.make_creature(&"stoneback", maxi(5, mine.level), "Biscuit")
	s.add_creature(1, biscuit, Registry.get_species(&"stoneback"))
	s.ai = [&"", &"easy" if relaxed else &"story"]
	s.story_battle_id = &"kindling_duel"
	s.team_names = [_player_name(), "Corin"]
	s.metadata = {"trainer_sprites": ["explorer", "corin"], "lighting": "golden"}
	return s


func _player_name() -> String:
	return SaveService.profile.player_name if SaveService.profile else "Wren"


func _player_creature_of(species_id: StringName) -> CreatureInstance:
	if SaveService.profile:
		for c in SaveService.profile.party:
			if c.species_id == species_id:
				return c
	var level := 50 if SaveService.profile == null else 5
	return Registry.make_creature(species_id, level)


## Awards experience and mastery after story / adventure battles (never in
## versus). Results are written into `result["progress"]` for the UI.
func apply_battle_progress(setup: BattleSetup, result: Dictionary) -> void:
	if SaveService.profile == null or setup.mode == BattleSetup.Mode.VERSUS:
		return
	var creature: CreatureInstance = (setup.teams[0] as Array)[0]["creature"]
	if not SaveService.profile.party.has(creature):
		return
	var foe: CreatureInstance = (setup.teams[1] as Array)[0]["creature"]
	var won := int(result.get("winner", -1)) == 0
	var progress := {"name": creature.display_name(Registry.get_species(creature.species_id))}
	if setup.mode == BattleSetup.Mode.STORY:
		var xp := Leveling.battle_xp(creature.level, foe.level, won)
		progress["xp"] = xp
		progress["levels"] = Leveling.add_xp(creature, xp)
	var rec: Dictionary = result.get("record", {})
	progress["mastery"] = Mastery.award_from_battle(creature, rec.get("ability_usage", {}))
	if won:
		SaveService.profile.wins += 1
	else:
		SaveService.profile.losses += 1
	result["progress"] = progress
	SaveService.save()
