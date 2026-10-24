extends WBTestCase
## Battle results reach the story only when the battle returns to the world:
## a Free Battle or Dash Training started from the title must not leave a
## result behind for a later New Journey or Continue to apply.


func test_results_only_survive_a_return_to_the_world() -> void:
	var was_autoplay := Game.autoplay
	Game.autoplay = true  # scene changes are recorded, not performed
	var won_training := {"story_battle_id": &"training", "winner": 0, "local_team": 0}
	Game._battle_return = Game.TITLE_SCENE
	Game.return_from_battle(won_training)
	assert_true(Game.last_result.is_empty(), "nothing left behind from a title-screen battle")
	Game.abandon_battle(null)
	assert_true(Game.last_result.is_empty(), "nor from abandoning one")
	Game._battle_return = Game.WORLD_SCENE
	Game.return_from_battle(won_training)
	assert_eq(Game.last_result.get("story_battle_id"), &"training", "a story battle's result reaches the world")
	Game.last_result = {}
	Game._battle_return = ""
	Game.autoplay = was_autoplay
	Game.autoplay_requests.clear()
