class_name NPC
extends Interactable
## A villager or companion standing in the world: sprite, contact shadow,
## collision, emotes, facing and scripted walking for cutscenes.

var sprite: PixelSprite3D
var display_name := ""
var walk_speed := 3.2
var _dir := "s"
var _body: StaticBody3D
var _anim := "idle"
var _emote: Node3D


func setup(p_name: String, manifest: String, p_prompt: String = "Talk") -> void:
	display_name = p_name
	prompt = "%s %s" % [p_prompt, p_name] if p_name != "" else p_prompt
	radius = 1.1
	sprite = PixelSprite3D.new()
	sprite.load_manifest(manifest)
	sprite.set_param("emission_strength", 0.8)
	add_child(sprite)
	EnvKit.blob_shadow(self, 0.36, 0.42)
	_body = StaticBody3D.new()
	_body.collision_layer = 1
	var cs := CollisionShape3D.new()
	var cyl := CylinderShape3D.new()
	cyl.radius = 0.32
	cyl.height = 1.2
	cs.shape = cyl
	cs.position.y = 0.6
	_body.add_child(cs)
	add_child(_body)
	sprite.play("idle", _dir)


func set_dir(d: String) -> void:
	_dir = d
	sprite.play(_anim, _dir)


func face(p: Vector3) -> void:
	var d := Vector2(p.x - global_position.x, p.z - global_position.z)
	if d.length() < 0.01:
		return
	if absf(d.x) > absf(d.y):
		_dir = "e" if d.x > 0 else "w"
	else:
		_dir = "s" if d.y > 0 else "n"
	sprite.play(_anim, _dir)


func play(anim: String) -> void:
	_anim = anim if sprite.has_animation(anim) else "idle"
	sprite.play(_anim, _dir, true)


## Walks in a straight line to `target` (world XZ). Awaitable.
func walk_to(target: Vector3, speed: float = -1.0) -> void:
	var spd := walk_speed if speed <= 0.0 else speed
	_body.process_mode = Node.PROCESS_MODE_DISABLED
	var start := global_position
	var dist := Vector2(target.x - start.x, target.z - start.z).length()
	if dist < 0.05:
		return
	face(target)
	_anim = "walk"
	sprite.play("walk", _dir)
	var tw := create_tween()
	tw.tween_property(self, "global_position", Vector3(target.x, 0, target.z), dist / spd)
	await tw.finished
	_anim = "idle"
	sprite.play("idle", _dir)
	_body.process_mode = Node.PROCESS_MODE_INHERIT


## Shows an emote bubble ("exclaim", "question", "heart", "note", "sweat", "anger", "zzz").
func emote(kind: String, seconds: float = 1.4) -> void:
	show_emote(self, kind, seconds, 1.95)


static func show_emote(host: Node3D, kind: String, seconds: float, height: float) -> void:
	var sheet := SpriteSheet.load_sheet("res://assets/effects/emotes.json")
	if not sheet.valid:
		return
	var s := PixelSprite3D.new()
	s.set_sheet(sheet)
	s.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	s.set_param("emission_strength", 0.6)
	host.add_child(s)
	s.position = Vector3(0, height, 0)
	s.play(kind, "s")
	Audio.sfx(&"ui_select", -14.0)
	var tw := s.create_tween()
	tw.tween_property(s, "position:y", height + 0.15, 0.15)
	tw.tween_interval(seconds)
	tw.tween_callback(s.queue_free)
