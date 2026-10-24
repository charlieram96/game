extends Node
## Player settings (autoload "Settings"), persisted to user://settings.cfg.

const PATH := "user://settings.cfg"

enum TouchMode { AUTO, ALWAYS, NEVER }

var music_volume: float = 0.7
var sfx_volume: float = 0.85
var screen_shake: float = 1.0
var touch_mode: TouchMode = TouchMode.AUTO
var show_hitboxes: bool = false
var show_fps: bool = false
var ai_difficulty: StringName = &"normal"
var tilt_shift: bool = true
var aim_assist: bool = true


func _ready() -> void:
	InputSetup.ensure_actions()
	load_settings()


func touch_controls_enabled() -> bool:
	match touch_mode:
		TouchMode.ALWAYS:
			return true
		TouchMode.NEVER:
			return false
	return DisplayServer.is_touchscreen_available() or OS.has_feature("mobile") or OS.has_feature("web_android") or OS.has_feature("web_ios")


func load_settings() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(PATH) != OK:
		_apply_audio()
		return
	music_volume = clampf(float(cfg.get_value("audio", "music", music_volume)), 0.0, 1.0)
	sfx_volume = clampf(float(cfg.get_value("audio", "sfx", sfx_volume)), 0.0, 1.0)
	screen_shake = clampf(float(cfg.get_value("video", "screen_shake", screen_shake)), 0.0, 1.0)
	tilt_shift = bool(cfg.get_value("video", "tilt_shift", tilt_shift))
	touch_mode = int(cfg.get_value("input", "touch_mode", touch_mode)) as TouchMode
	aim_assist = bool(cfg.get_value("input", "aim_assist", aim_assist))
	ai_difficulty = StringName(str(cfg.get_value("gameplay", "ai_difficulty", ai_difficulty)))
	show_hitboxes = bool(cfg.get_value("debug", "show_hitboxes", show_hitboxes))
	show_fps = bool(cfg.get_value("debug", "show_fps", show_fps))
	_apply_audio()


func save_settings() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("audio", "music", music_volume)
	cfg.set_value("audio", "sfx", sfx_volume)
	cfg.set_value("video", "screen_shake", screen_shake)
	cfg.set_value("video", "tilt_shift", tilt_shift)
	cfg.set_value("input", "touch_mode", int(touch_mode))
	cfg.set_value("input", "aim_assist", aim_assist)
	cfg.set_value("gameplay", "ai_difficulty", String(ai_difficulty))
	cfg.set_value("debug", "show_hitboxes", show_hitboxes)
	cfg.set_value("debug", "show_fps", show_fps)
	cfg.save(PATH)
	_apply_audio()
	Events.settings_changed.emit()


func _apply_audio() -> void:
	_set_bus("Music", music_volume)
	_set_bus("SFX", sfx_volume)


func _set_bus(bus_name: String, linear: float) -> void:
	var idx := AudioServer.get_bus_index(bus_name)
	if idx < 0:
		idx = AudioServer.bus_count
		AudioServer.add_bus(idx)
		AudioServer.set_bus_name(idx, bus_name)
		AudioServer.set_bus_send(idx, &"Master")
	AudioServer.set_bus_volume_db(idx, linear_to_db(maxf(linear, 0.0001)))
	AudioServer.set_bus_mute(idx, linear <= 0.001)
