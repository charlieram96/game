class_name FighterView
extends Node3D
## Visual representation of one Fighter. Reads simulation state every frame
## (interpolated between ticks) and turns it into animation and feedback:
## phase-driven attack frames, hit flash + hitstop jitter, squash/stretch,
## dash afterimages, focus aura, directional guard arc, stun stars,
## status tints, a ground ring that doubles as the stamina gauge.

const SM := FighterSM.State
const RING_SHADER := preload("res://shaders/ring_gauge.gdshader")

var fighter: Fighter
var sprite: PixelSprite3D
var shadow: MeshInstance3D
var ring: MeshInstance3D
var guard_arc: GroundDecal
var team_color := Color(0.35, 0.9, 0.95)
var victory := false

var _ring_mat: ShaderMaterial
var _dir := "e"
var _flash := 0.0
var _last_state := -1
var _ghost_clock := 0.0
var _burn_fx: CPUParticles3D = null
var _squash := Vector2.ONE
var _ko_time := 0.0


func setup(f: Fighter, color: Color) -> void:
	fighter = f
	team_color = color
	name = "Fighter%d" % f.id
	shadow = EnvKit.blob_shadow(self, f.radius() * 1.45, 0.5)
	ring = MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2.ONE * (f.radius() * 2.0 + 0.55)
	ring.mesh = pm
	_ring_mat = ShaderMaterial.new()
	_ring_mat.shader = RING_SHADER
	_ring_mat.set_shader_parameter("team_color", color)
	_ring_mat.set_shader_parameter("gauge_color", color.lightened(0.35))
	var dash_cost := f.stats.dash.min_cost()
	_ring_mat.set_shader_parameter("ticks", floor(f.max_stamina() / dash_cost) if dash_cost > 0.0 and dash_cost < 999.0 else 0.0)
	ring.material_override = _ring_mat
	ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	ring.position.y = 0.02
	add_child(ring)
	guard_arc = GroundDecal.new()
	guard_arc.set_circle(f.radius() + 0.75, GroundDecal.Shape.CONE, 0.0, deg_to_rad(CombatConst.GUARD_ARC_DEG * 0.5))
	guard_arc.set_colors(Color(0.65, 0.95, 1.0), Color(0.4, 0.75, 1.0), 0.7)
	guard_arc.set_progress(1.0)
	guard_arc.visible = false
	add_child(guard_arc)
	sprite = PixelSprite3D.new()
	sprite.load_manifest(f.species.sprite_manifest)
	sprite.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	sprite.set_param("emission_strength", 1.8)
	add_child(sprite)
	_dir = "e" if f.facing.x >= 0.0 else "w"
	sprite.play("idle", _dir)
	position = Vector3(f.pos.x, 0, f.pos.y)


func flash(amount: float = 1.0, color: Color = Color.WHITE) -> void:
	_flash = maxf(_flash, amount)
	sprite.set_param("flash_color", color)


func squash(x: float, y: float) -> void:
	_squash = Vector2(x, y)


func update_view(alpha: float, delta: float) -> void:
	var f := fighter
	visible = f.on_field or f.state == SM.SWITCHING
	var p := f.prev_pos.lerp(f.pos, alpha)
	position = Vector3(p.x, 0, p.y)
	_update_direction()
	_update_animation(delta)
	_update_effects(delta)
	# Flash decay, squash recovery, hitstop jitter.
	_flash = maxf(0.0, _flash - delta * 7.0)
	sprite.set_param("flash", _flash)
	_squash = _squash.lerp(Vector2.ONE, minf(1.0, delta * 12.0))
	sprite.scale = Vector3(_squash.x, _squash.y, 1.0)
	if f.hitstop > 0 and f.state != SM.ATTACK_ACTIVE:
		sprite.set_param("jitter", Vector2(randf_range(-1.0, 1.0), 0.0).round())
	else:
		sprite.set_param("jitter", Vector2.ZERO)
	sprite.speed_scale = 0.0 if f.hitstop > 0 else 1.0
	# Ground ring = stamina gauge + facing notch.
	_ring_mat.set_shader_parameter("fill", f.stamina_ratio())
	_ring_mat.set_shader_parameter("facing_angle", atan2(f.facing.y, f.facing.x))
	var low := f.stamina < f.stats.dash.min_cost()
	_ring_mat.set_shader_parameter("gauge_color", Color(1.0, 0.45, 0.35) if low else team_color.lightened(0.35))
	_ring_mat.set_shader_parameter("pulse", 1.0 if f.state == SM.FOCUSING else 0.0)
	ring.visible = not f.is_ko()


func _update_direction() -> void:
	var fv := fighter.facing
	if fighter.state == SM.DASH_ACTIVE or fighter.state == SM.DASH_START:
		fv = fighter.dash_dir
	var ax := absf(fv.x)
	var az := absf(fv.y)
	if ax > az * 1.15:
		_dir = "e" if fv.x > 0.0 else "w"
	elif az > ax * 1.15:
		_dir = "s" if fv.y > 0.0 else "n"


func _update_animation(delta: float) -> void:
	var f := fighter
	var st := f.state
	if st != _last_state:
		_on_state_enter(st)
		_last_state = st
	if victory and FighterSM.is_actionable(st):
		sprite.play("victory", "s")
		return
	match st:
		SM.IDLE:
			sprite.play("idle", _dir)
		SM.DASH_START:
			sprite.show_frame("dash", _dir, 0)
		SM.DASH_ACTIVE:
			if sprite.has_animation("roll"):
				sprite.play("roll", "s")
			else:
				sprite.play("dash", _dir)
			_ghost_clock -= delta
			if _ghost_clock <= 0.0:
				_ghost_clock = 0.035
				_spawn_ghost()
		SM.DASH_RECOVERY:
			sprite.play("idle", _dir)
		SM.ATTACK_START, SM.ATTACK_ACTIVE, SM.ATTACK_RECOVERY:
			var anim := String(f.current_ability.anim) if f.current_ability else "cast"
			if not sprite.has_animation(anim):
				anim = "cast"
			var n := sprite.frame_count_of(anim)
			var idx := 0
			if st == SM.ATTACK_ACTIVE:
				idx = mini(1, n - 1)
			elif st == SM.ATTACK_RECOVERY:
				idx = mini(2, n - 1)
			sprite.show_frame(anim, _dir, idx)
		SM.FOCUS_ENTER, SM.FOCUSING, SM.FOCUS_EXIT:
			sprite.play("focus", _dir)
		SM.GUARDING:
			sprite.play("guard", _dir)
		SM.STUNNED:
			if f.stun_kind == &"hit" and f.state_tick < 10:
				sprite.play("hurt", _dir)
			else:
				sprite.play("stunned", "s")
		SM.SWITCHING:
			sprite.play("idle", _dir)
		SM.KNOCKED_OUT:
			sprite.play("ko", "s")


func _on_state_enter(st: int) -> void:
	match st:
		SM.DASH_START:
			squash(1.18, 0.82)
		SM.DASH_ACTIVE:
			squash(1.25, 0.8)
		SM.DASH_RECOVERY:
			squash(0.88, 1.12)
		SM.ATTACK_ACTIVE:
			squash(1.12, 0.92)
		SM.KNOCKED_OUT:
			_ko_time = 0.0
			flash(1.0)


func _update_effects(delta: float) -> void:
	var f := fighter
	var st := f.state
	var stunned := st == SM.STUNNED and not (f.stun_kind == &"hit" and f.state_duration < 16)
	_loop_fx(&"stun", &"stun_stars", stunned, Vector3(0, f.species.visual_height + 0.2, 0), Color.WHITE)
	var focusing := st == SM.FOCUSING or st == SM.FOCUS_ENTER
	_loop_fx(&"focus", &"focus_aura", focusing, Vector3(0, 0.02, 0.05), Color(0.75, 1.0, 1.0, 0.85))
	var armored := f.has_status(&"stoneguard")
	_loop_fx(&"armor", &"stone_guard", armored, Vector3(0, 0.02, 0.1), Color(1, 1, 1, 0.9))
	# Guard arc (brighter during the perfect-guard window).
	guard_arc.visible = st == SM.GUARDING
	if guard_arc.visible:
		guard_arc.aim(f.facing)
		var perfect := f.state_tick < CombatConst.PERFECT_GUARD_TICKS
		guard_arc.set_colors(Color(1.0, 1.0, 0.85) if perfect else Color(0.6, 0.92, 1.0), Color(0.45, 0.78, 1.0), 0.9 if perfect else 0.6)
	# Burn embers
	var burning := f.has_status(&"burn")
	if burning and _burn_fx == null:
		_burn_fx = Vfx.trail(Color(1.0, 0.55, 0.2), 0.06, 12, 0.5)
		add_child(_burn_fx)
		_burn_fx.position = Vector3(0, 0.5, 0)
		_burn_fx.emitting = true
	elif not burning and _burn_fx != null:
		_burn_fx.queue_free()
		_burn_fx = null
	# Tints: status colour, focus shimmer, steadfast outline.
	var tint := Color.WHITE
	if f.has_status(&"slow"):
		tint = Color(0.82, 0.74, 0.62)
	if burning:
		tint = tint * Color(1.15, 0.9, 0.8)
	if focusing:
		tint = tint.lerp(Color(1.25, 1.35, 1.45), 0.5 + 0.5 * sin(Time.get_ticks_msec() * 0.012))
	sprite.set_param("modulate", tint)
	sprite.set_param("outline", 0.85 if f.steadfast > 0 else 0.0)
	# KO: keep the body visible for a moment, then dim it.
	if st == SM.KNOCKED_OUT:
		_ko_time += delta
		sprite.set_param("dissolve", clampf((_ko_time - 1.6) * 0.5, 0.0, 0.55))
	else:
		sprite.set_param("dissolve", 0.0)


var _loops: Dictionary = {}
var _missing_loops: Dictionary = {}


func _loop_fx(key: StringName, vfx_id: StringName, active: bool, offset: Vector3, tint: Color) -> void:
	var node: Node3D = _loops.get(key)
	if active:
		if node == null and not _missing_loops.has(vfx_id):
			node = Vfx.spawn(self, vfx_id, Vector3.ZERO, Vector2.RIGHT, tint, 1.0, true)
			if node == null:
				_missing_loops[vfx_id] = true
				return
			node.position = offset
			_loops[key] = node
	elif node != null:
		if is_instance_valid(node):
			node.queue_free()
		_loops.erase(key)


func _spawn_ghost() -> void:
	if sprite.sheet == null or not sprite.sheet.valid:
		return
	var g := PixelSprite3D.new()
	g.set_sheet(sprite.sheet)
	g.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	get_parent().add_child(g)
	g.global_position = global_position
	g.set_param("frame", sprite.get_param("frame"))
	g.set_param("flip_h", sprite.get_param("flip_h"))
	g.playing = false
	g.set_param("modulate", team_color.lightened(0.2))
	g.set_param("flash", 0.55)
	g.set_param("flash_color", team_color.lightened(0.4))
	g.set_param("dissolve", 0.35)
	var tw := g.create_tween()
	tw.tween_method(func(v: float) -> void: g.set_param("dissolve", v), 0.35, 1.0, 0.22)
	tw.tween_callback(g.queue_free)
