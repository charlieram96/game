class_name Explorer
extends CharacterBody3D
## The player's explorer in the overworld: smooth eight-direction walking,
## sneaking (quiet, slower), four-direction sprite animation, surface-aware
## footsteps and interaction with nearby interactables.

signal interacted(target: Interactable)

const WALK_SPEED := 5.0
const SNEAK_SPEED := 2.1
const ACCEL := 32.0
const INTERACT_RANGE := 1.7

var controllable := true
var sneaking := false
var surface_lookup: Callable
var touch_move := Vector2.ZERO
var touch_sneak := false
var sprite: PixelSprite3D
var facing := Vector2(0, 1)
var _dir := "s"
var _step_clock := 0.0
var _focus: Interactable = null
var _forced_anim := ""


func _ready() -> void:
	collision_layer = 2
	collision_mask = 1
	var cs := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.32
	cap.height = 1.1
	cs.shape = cap
	cs.position.y = 0.55
	add_child(cs)
	sprite = PixelSprite3D.new()
	sprite.load_manifest("res://assets/sprites/characters/explorer.json")
	sprite.set_param("emission_strength", 0.6)
	add_child(sprite)
	EnvKit.blob_shadow(self, 0.38, 0.45)
	sprite.play("idle", "s")


func _physics_process(delta: float) -> void:
	var input := Vector2.ZERO
	if controllable:
		input = Input.get_vector(&"move_left", &"move_right", &"move_up", &"move_down", 0.25)
		if touch_move != Vector2.ZERO:
			input = touch_move
		sneaking = Input.is_action_pressed(&"sneak") or touch_sneak
	else:
		sneaking = false
	# Eight-way, normalized: diagonals are never faster.
	var dir8 := CombatConst.vec_to_dir8(input, 0.25)
	var move := CombatConst.dir8_to_vec(dir8)
	var speed := SNEAK_SPEED if sneaking else WALK_SPEED
	var target := Vector3(move.x, 0, move.y) * speed
	var v := Vector3(velocity.x, 0, velocity.z).move_toward(target, ACCEL * delta)
	velocity = v
	move_and_slide()
	position.y = 0.0
	if move != Vector2.ZERO:
		facing = move
	_animate(move != Vector2.ZERO, delta)
	_update_focus()


func _animate(moving: bool, delta: float) -> void:
	if _forced_anim != "":
		sprite.play(_forced_anim, _dir)
		return
	var ax := absf(facing.x)
	var az := absf(facing.y)
	if ax > az * 1.1:
		_dir = "e" if facing.x > 0 else "w"
	elif az > ax * 1.1:
		_dir = "s" if facing.y > 0 else "n"
	if moving:
		sprite.play("sneak" if sneaking and sprite.has_animation("sneak") else "walk", _dir)
		_step_clock -= delta
		if _step_clock <= 0.0:
			_step_clock = 0.42 if sneaking else 0.3
			var surface := "grass"
			if surface_lookup.is_valid():
				surface = surface_lookup.call(global_position)
			Audio.sfx(StringName("step_" + surface), -16.0 if sneaking else -9.0, 0.08, 60)
	else:
		sprite.play("idle", _dir)
		_step_clock = 0.0


## Plays a pose until cleared ("sit", "cheer", "interact", "surprised").
func force_animation(anim: String) -> void:
	_forced_anim = anim
	if anim == "":
		return
	if not sprite.has_animation(anim):
		_forced_anim = ""
		return
	sprite.play(anim, _dir if anim != "cheer" and anim != "surprised" else "s", true)


func face_towards(p: Vector3) -> void:
	var d := Vector2(p.x - global_position.x, p.z - global_position.z)
	if d.length() > 0.01:
		facing = d.normalized()
	_animate(false, 0.0)


func horizontal_speed() -> float:
	return Vector2(velocity.x, velocity.z).length()


func is_running() -> bool:
	return horizontal_speed() > SNEAK_SPEED + 0.6


# --- Interaction ---------------------------------------------------------------------------

func _update_focus() -> void:
	var best: Interactable = null
	var best_score := 1e9
	if controllable:
		for node in get_tree().get_nodes_in_group(&"interactable"):
			var it := node as Interactable
			if it == null or not it.enabled or not it.is_visible_in_tree():
				continue
			var to := Vector2(it.global_position.x - global_position.x, it.global_position.z - global_position.z)
			var dist := to.length()
			if dist > it.radius + INTERACT_RANGE * 0.5:
				continue
			var score := dist - (0.6 if to.normalized().dot(facing) > 0.4 else 0.0)
			if score < best_score:
				best_score = score
				best = it
	if best != _focus:
		_focus = best


func current_focus() -> Interactable:
	return _focus


func _unhandled_input(event: InputEvent) -> void:
	if not controllable:
		return
	if event.is_action_pressed(&"interact"):
		try_interact()


func try_interact() -> void:
	if _focus and controllable:
		get_viewport().set_input_as_handled()
		face_towards(_focus.global_position)
		Audio.sfx(&"interact", -6.0)
		interacted.emit(_focus)
		_focus.interact(self)
