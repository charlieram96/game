extends Node
## Global event bus (autoload "Events") for loosely coupled game-level
## signals. Combat uses BattleSim events instead; this is for UI, story and
## world systems that shouldn't reference each other directly.

signal dialogue_started(dialogue_id: String)
signal dialogue_finished(dialogue_id: String)
signal quest_updated(objective_text: String)
signal toast(text: String, kind: StringName)
signal journal_updated(species_id: StringName)
signal creature_befriended(creature: CreatureInstance)
signal battle_requested(setup: BattleSetup)
signal battle_finished(result: Dictionary)
signal story_flag_changed(flag: String, value: Variant)
signal settings_changed
signal input_device_changed(device: StringName)
