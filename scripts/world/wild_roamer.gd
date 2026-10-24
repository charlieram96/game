class_name WildRoamer
extends Node3D
## A wild kith wandering its habitat (the Mossling). It grazes and hops
## between spots, notices running footsteps within its hearing range and
## bolts; a Warden who sneaks close can observe it calmly (journal entry).

signal observed

enum Mode { GRAZE, HOP, ALERT, FLEE, CALM }

var species_id := &"mossling"
var home := Vector3.ZERO
var home_radius := 5.0
var hearing := 6.5
var player: Explorer
var sprite: PixelSprite3D
var interact: Interactable
var mode := Mode.GRAZE
var rng := RandomNumberGenerator.new()
var _timer := 1.0
var _hop_target := Vector3.ZERO
var _dir := "s"
var _calm_left := 0.0
var _observed := false


func setup(p_home: Vector3, p_player: Explorer) -> void:
	home = p_home
	player = p_player
	position = p_home
	rng.seed = 31
	sprite = PixelSprite3D.new()
	sprite.load_manifest("res://assets/sprites/kith/mossling.json")
	sprite.set_param("emission_strength", 0.5)
	add_child(sprite)
	EnvKit.blob_shadow(self, 0.26, 0.4)
	interact = Interactable.new()
	interact.prompt = "Observe the Mossling"
	interact.radius = 1.2
	add_child(interact)
	interact.used.connect(_on_observe)
	sprite.play("idle", "s")


func _process(delta: float) -> void:
	if player == null:
		return
	var to_player := Vector2(player.global_position.x - global_position.x, player.global_position.z - global_position.z)
	var dist := to_player.length()
	# Only a sneaking Warden may get close enough to observe it.
	interact.enabled = player.sneaking and mode != Mode.FLEE and mode != Mode.ALERT
	if mode != Mode.FLEE and mode != Mode.ALERT and mode != Mode.CALM:
		if dist < hearing and player.is_running():
			mode = Mode.ALERT
			_timer = 0.35
			sprite.play("alert", "s")
			Audio.sfx(&"mossling_squeak", -6.0)
			NPC.show_emote(self, "exclaim", 0.6, 1.1)
	_timer -= delta
	match mode:
		Mode.GRAZE:
			sprite.play("idle", "e" if _dir == "w" else _dir)
			if _timer <= 0.0:
				_pick_hop()
		Mode.HOP:
			_move_toward(_hop_target, 1.6, delta)
			if global_position.distance_to(_hop_target) < 0.1:
				mode = Mode.GRAZE
				_timer = rng.randf_range(1.5, 3.5)
		Mode.ALERT:
			if _timer <= 0.0:
				mode = Mode.FLEE
				var away := -to_player.normalized()
				var t := global_position + Vector3(away.x, 0, away.y) * 5.0
				_hop_target = _clamp_home(t, home_radius + 3.0)
				_timer = 3.0
		Mode.FLEE:
			_move_toward(_hop_target, 5.5, delta)
			if global_position.distance_to(_hop_target) < 0.15 or _timer <= 0.0:
				mode = Mode.GRAZE
				_timer = 2.5
		Mode.CALM:
			_calm_left -= delta
			sprite.play("idle", "s")
			if _calm_left <= 0.0:
				mode = Mode.GRAZE


func _pick_hop() -> void:
	var a := rng.randf() * TAU
	var r := rng.randf_range(0.5, home_radius)
	_hop_target = home + Vector3(cos(a) * r, 0, sin(a) * r)
	mode = Mode.HOP


func _clamp_home(p: Vector3, r: float) -> Vector3:
	var d := p - home
	if d.length() > r:
		d = d.normalized() * r
	return home + d


func _move_toward(t: Vector3, speed: float, delta: float) -> void:
	var d := t - global_position
	d.y = 0
	if d.length() < 0.001:
		return
	var step := minf(d.length(), speed * delta)
	global_position += d.normalized() * step
	if absf(d.x) > absf(d.z):
		_dir = "e" if d.x > 0 else "w"
	else:
		_dir = "s" if d.z > 0 else "n"
	sprite.play("hop", _dir)


func _on_observe(_by: Node3D) -> void:
	mode = Mode.CALM
	_calm_left = 4.0
	NPC.show_emote(self, "heart", 1.2, 1.1)
	Audio.sfx(&"mossling_squeak", -4.0)
	if not _observed:
		_observed = true
		observed.emit()
