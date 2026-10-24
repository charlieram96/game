extends WBTestCase
## Spec test 18: save/load serialization (atomic writes, corrupt files,
## lossless round trip of the whole profile).

const PATH := "user://test_wildbound_save.json"


func after_each() -> void:
	if FileAccess.file_exists(PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(PATH))


func _sample_profile() -> PlayerProfile:
	var p := PlayerProfile.new()
	p.player_name = "Tamsin"
	p.story_step = "duel"
	p.set_flag("met_hesper")
	p.set_flag("kindlemoss", 3)
	var e := CreatureInstance.create(load("res://resources/creatures/emberlyn.tres"), 7, 99)
	e.nickname = "Cinder"
	e.mastery[&"ember_bolt"] = {"level": 3, "xp": 12}
	e.variants[&"ember_bolt"] = &"needle"
	p.party.append(e)
	p.journal_mark(&"emberlyn", "befriended")
	p.journal_mark(&"mossling", "seen")
	p.position = Vector3(1.5, 0, -3.25)
	p.scene = "res://scenes/world/mossford.tscn"
	p.play_time_sec = 321.5
	return p


func test_profile_round_trip() -> void:
	var p := _sample_profile()
	assert_true(SaveService.write_profile(p, PATH), "saved")
	var back := SaveService.read_profile(PATH)
	assert_true(back != null, "loaded")
	assert_eq(JSON.stringify(back.to_dict()), JSON.stringify(p.to_dict()), "lossless")
	assert_eq(back.party[0].nickname, "Cinder", "creature nickname")
	assert_eq(back.party[0].selected_variant(&"ember_bolt"), &"needle", "variant choice")
	assert_true(bool(back.flag("met_hesper")), "story flags")
	assert_false(FileAccess.file_exists(PATH + ".tmp"), "atomic write cleaned up")


func test_service_save_and_reload() -> void:
	var old_path := SaveService.path
	var old_profile := SaveService.profile
	SaveService.path = PATH
	SaveService.profile = _sample_profile()
	assert_true(SaveService.save(), "service save")
	SaveService.profile = null
	assert_true(SaveService.has_save(), "has save")
	assert_true(SaveService.load_profile(), "service load")
	assert_eq(SaveService.profile.player_name, "Tamsin", "name")
	SaveService.path = old_path
	SaveService.profile = old_profile


func test_corrupt_save_is_rejected() -> void:
	var f := FileAccess.open(PATH, FileAccess.WRITE)
	f.store_string("{ this is not json")
	f.close()
	assert_true(SaveService.read_profile(PATH) == null, "corrupt file rejected, no crash")


func test_untrusted_values_are_clamped() -> void:
	var p := PlayerProfile.from_dict({"player_name": "", "party": [{"species": "emberlyn", "level": -4}], "wins": -9})
	assert_eq(p.player_name, "Wren", "empty name defaults")
	assert_eq(p.party[0].level, 1, "level clamped")
	assert_eq(p.wins, 0, "wins clamped")
