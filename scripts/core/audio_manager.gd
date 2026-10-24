extends Node
## Audio playback (autoload "Audio"): pooled SFX, crossfaded looping music.
## Missing files are ignored so the game runs before every asset exists.

const SFX_DIR := "res://assets/audio/sfx/"
const MUSIC_DIR := "res://assets/audio/music/"
const POOL_SIZE := 20

var _pool: Array[AudioStreamPlayer] = []
var _next := 0
var _cache: Dictionary = {}  # name -> Array[AudioStream] (variants)
var _music_a: AudioStreamPlayer
var _music_b: AudioStreamPlayer
var _music_current: StringName = &""
var _loops: Dictionary = {}  # key -> AudioStreamPlayer
var _last_play_ms: Dictionary = {}


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	for i in POOL_SIZE:
		var p := AudioStreamPlayer.new()
		p.bus = &"SFX"
		add_child(p)
		_pool.append(p)
	_music_a = AudioStreamPlayer.new()
	_music_b = AudioStreamPlayer.new()
	for m in [_music_a, _music_b]:
		m.bus = &"Music"
		m.volume_db = -80.0
		add_child(m)


## Plays a sound by name. Looks for `<name>.wav`, or variants `<name>_1..4.wav`.
func sfx(sound: StringName, volume_db: float = 0.0, pitch_jitter: float = 0.04, min_interval_ms: int = 30) -> void:
	if sound == &"":
		return
	var now := Time.get_ticks_msec()
	if now - int(_last_play_ms.get(sound, -1000)) < min_interval_ms:
		return
	_last_play_ms[sound] = now
	var streams := _streams(sound)
	if streams.is_empty():
		return
	var p := _pool[_next]
	_next = (_next + 1) % _pool.size()
	p.stream = streams[randi() % streams.size()]
	p.volume_db = volume_db
	p.pitch_scale = 1.0 + randf_range(-pitch_jitter, pitch_jitter)
	p.play()


func has_sfx(sound: StringName) -> bool:
	return not _streams(sound).is_empty()


## Starts (or keeps) a looping sound identified by `key`.
func loop_start(key: StringName, sound: StringName, volume_db: float = 0.0) -> void:
	if _loops.has(key):
		return
	var streams := _streams(sound)
	if streams.is_empty():
		return
	var stream: AudioStream = streams[0]
	if stream is AudioStreamWAV:
		stream = _as_loop(stream)
	var p := AudioStreamPlayer.new()
	p.bus = &"SFX"
	p.stream = stream
	p.volume_db = volume_db
	add_child(p)
	p.play()
	_loops[key] = p


func loop_stop(key: StringName) -> void:
	if not _loops.has(key):
		return
	var p: AudioStreamPlayer = _loops[key]
	_loops.erase(key)
	var tw := create_tween()
	tw.tween_property(p, "volume_db", -40.0, 0.15)
	tw.tween_callback(p.queue_free)


func stop_all_loops() -> void:
	for key in _loops.keys():
		loop_stop(key)


func music(track: StringName, fade: float = 1.2, volume_db: float = -4.0) -> void:
	if track == _music_current:
		return
	_music_current = track
	var path := MUSIC_DIR + String(track) + ".wav"
	var incoming := _music_b if _music_a.playing else _music_a
	var outgoing := _music_a if incoming == _music_b else _music_b
	if outgoing.playing:
		var tw_out := create_tween()
		tw_out.tween_property(outgoing, "volume_db", -60.0, fade)
		tw_out.tween_callback(outgoing.stop)
	if track == &"" or not ResourceLoader.exists(path):
		return
	var stream: AudioStream = load(path)
	if stream is AudioStreamWAV and not String(track).ends_with("fanfare"):
		stream = _as_loop(stream)
	incoming.stream = stream
	incoming.volume_db = -50.0
	incoming.play()
	var tw_in := create_tween()
	tw_in.tween_property(incoming, "volume_db", volume_db, fade)


func stop_music(fade: float = 1.0) -> void:
	music(&"", fade)


func current_music() -> StringName:
	return _music_current


func _streams(sound: StringName) -> Array:
	if _cache.has(sound):
		return _cache[sound]
	var out: Array = []
	var base := SFX_DIR + String(sound)
	if ResourceLoader.exists(base + ".wav"):
		out.append(load(base + ".wav"))
	for i in range(1, 5):
		var p := "%s_%d.wav" % [base, i]
		if ResourceLoader.exists(p):
			out.append(load(p))
	_cache[sound] = out
	return out


func _as_loop(stream: AudioStreamWAV) -> AudioStreamWAV:
	if stream.loop_mode != AudioStreamWAV.LOOP_DISABLED:
		return stream
	var s: AudioStreamWAV = stream.duplicate()
	s.loop_mode = AudioStreamWAV.LOOP_FORWARD
	s.loop_begin = 0
	s.loop_end = int(round(stream.get_length() * stream.mix_rate))
	return s
