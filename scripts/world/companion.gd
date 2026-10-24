class_name Companion
extends Node3D
## A befriended kith that follows its Warden through the world, trailing a
## short way behind along the Warden's own path.

var target: Explorer
var sprite: PixelSprite3D
var follow_distance := 1.3
var speed := 6.0
var _trail: Array[Vector3] = []
var _dir := "s"
var _sample := 0.0
var _idle_time := 0.0
var _scripted := false


func setup(species: CreatureDefinition, p_target: Explorer) -> void:
	target = p_target
	sprite = PixelSprite3D.new()
	sprite.load_manifest(species.sprite_manifest)
	sprite.set_param("emission_strength", 1.8)
	add_child(sprite)
	EnvKit.blob_shadow(self, 0.36, 0.42)
	global_position = target.global_position + Vector3(-0.8, 0, 0.6)
	sprite.play("idle", "s")


## Disable following while a cutscene positions the companion.
func set_scripted(on: bool) -> void:
	_scripted = on


func play(anim: String, dir: String = "s") -> void:
	sprite.play(anim, dir, true)


func _process(delta: float) -> void:
	if target == null or _scripted:
		return
	_sample -= delta
	if _sample <= 0.0:
		_sample = 0.08
		if _trail.is_empty() or _trail[_trail.size() - 1].distance_to(target.global_position) > 0.2:
			_trail.append(target.global_position)
			if _trail.size() > 60:
				_trail.pop_front()
	var to_target := target.global_position - global_position
	to_target.y = 0
	var moving := false
	if to_target.length() > follow_distance:
		var goal := target.global_position
		for p in _trail:
			if p.distance_to(target.global_position) <= follow_distance + 0.4:
				goal = p
				break
		var d := goal - global_position
		d.y = 0
		var spd := speed if to_target.length() < 4.0 else speed * 1.6
		if d.length() > 0.05:
			global_position += d.normalized() * minf(d.length(), spd * delta)
			moving = true
			if absf(d.x) > absf(d.z):
				_dir = "e" if d.x > 0 else "w"
			else:
				_dir = "s" if d.z > 0 else "n"
		if to_target.length() > 9.0:
			global_position = target.global_position - to_target.normalized() * follow_distance
	if moving:
		_idle_time = 0.0
		sprite.play("move", _dir)
	else:
		_idle_time += delta
		if _idle_time > 6.0 and sprite.has_animation("happy"):
			sprite.play("happy", "s")
			if _idle_time > 7.2:
				_idle_time = 0.0
		else:
			sprite.play("idle", _dir)
