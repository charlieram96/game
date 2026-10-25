class_name FighterView
extends Node3D
## Visual representation of one Fighter. Reads simulation state every frame
## (interpolated between ticks) and turns it into animation and feedback:
## phase-driven attack frames, hit flash + hitstop jitter, spring
## squash/stretch, the dash (crouch and lean on the windup, stretch, hop,
## afterimages and a ground smear on the travel, a springy landing), focus
## aura, directional guard arc, stun stars, status tints, and a ground ring
## that doubles as the stamina gauge (and previews what an aimed dash costs).

const SM := FighterSM.State
const RING_SHADER := preload("res://shaders/ring_gauge.gdshader")
const SMEAR_SHADER := preload("res://shaders/dash_smear.gdshader")
const GHOST_SHADER := preload("res://shaders/pixel_ghost.gdshader")
## Squash spring: stiffness and damping (a little overshoot reads as alive).
const SPRING_K := 560.0
const SPRING_C := 27.0
## Afterimage spacing along a dash, in world units.
const GHOST_SPACING := 0.34
const SMEAR_FADE := 0.24

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
var _burn_fx: CPUParticles3D = null
var _squash := Vector2.ONE
var _squash_vel := Vector2.ZERO
var _ko_time := 0.0
var _knock := Vector3.ZERO
var _ghost_travel := 0.0
var _last_pos := Vector3.ZERO
var _smear: MeshInstance3D
var _smear_mat: ShaderMaterial
var _smear_fade := -1.0
var _cost_preview := 0.0
var _cost_ok := true
var _cost_frame := -10
var _ram_pose := false
## The landing skid plays to its end, even into IDLE.
var _landing := false


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
	sprite.animation_finished.connect(func(anim: String) -> void:
		if anim == "ram":
			_ram_pose = false
		elif anim == "dash_land":
			_landing = false)
	position = Vector3(f.pos.x, 0, f.pos.y)
	_last_pos = position
	_smear = MeshInstance3D.new()
	_smear.mesh = PlaneMesh.new()
	(_smear.mesh as PlaneMesh).size = Vector2.ONE
	_smear_mat = ShaderMaterial.new()
	_smear_mat.shader = SMEAR_SHADER
	_smear_mat.set_shader_parameter("color", color.lightened(0.25))
	_smear_mat.set_shader_parameter("seed", float(f.id))
	_smear.material_override = _smear_mat
	_smear.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_smear.top_level = true
	_smear.visible = false
	add_child(_smear)


func flash(amount: float = 1.0, color: Color = Color.WHITE) -> void:
	_flash = maxf(_flash, amount)
	sprite.set_param("flash_color", color)


func squash(x: float, y: float) -> void:
	_squash = Vector2(x, y)
	_squash_vel = Vector2.ZERO


## This creature's dash just rammed a foe: the impact pose plays once.
func ram_pose() -> void:
	if sprite.has_animation("ram"):
		_ram_pose = true
		sprite.play("ram", _dir, true)


## Rammed or struck hard: squashed, knocked a little along `dir`, flashed.
func impact(dir: Vector2, strength: float = 1.0) -> void:
	squash(lerpf(1.0, 0.72, strength), lerpf(1.0, 1.24, strength))
	_knock = Vector3(dir.x, 0.0, dir.y) * 0.16 * strength
	flash(1.0)


## What the dash being aimed will spend (drawn on the ring for one frame).
func set_cost_preview(cost: float, affordable: bool) -> void:
	_cost_preview = cost
	_cost_ok = affordable
	_cost_frame = Engine.get_process_frames()


func update_view(alpha: float, delta: float) -> void:
	var f := fighter
	visible = f.on_field or f.state == SM.SWITCHING
	var p := f.prev_pos.lerp(f.pos, alpha)
	position = Vector3(p.x, 0, p.y)
	_update_direction()
	_update_animation(delta)
	_update_dash(delta)
	_update_effects(delta)
	# Flash decay, squash spring, knock recovery, hitstop jitter.
	_flash = maxf(0.0, _flash - delta * 7.0)
	sprite.set_param("flash", _flash)
	var dt := minf(delta, 1.0 / 30.0)
	_squash_vel += ((Vector2.ONE - _squash) * SPRING_K - _squash_vel * SPRING_C) * dt
	_squash += _squash_vel * dt
	sprite.scale = Vector3(_squash.x, _squash.y, 1.0)
	_knock = _knock.lerp(Vector3.ZERO, minf(1.0, delta * 14.0))
	if f.hitstop > 0 and f.state != SM.ATTACK_ACTIVE:
		var amp := 2.0 if f.state == SM.STUNNED else 1.0
		# In 24-px/unit sprite pixels, so 2x sheets shake as far.
		var px_scale := sprite.sheet.pixels_per_unit / 24.0 if sprite.sheet else 1.0
		sprite.set_param("jitter", (Vector2(randf_range(-1.0, 1.0), randf_range(-0.4, 0.4)) * amp).round() * px_scale)
	else:
		sprite.set_param("jitter", Vector2.ZERO)
	sprite.speed_scale = 0.0 if f.hitstop > 0 else 1.0
	# Ground ring = stamina gauge + facing notch + the aimed dash's cost.
	_ring_mat.set_shader_parameter("fill", f.stamina_ratio())
	_ring_mat.set_shader_parameter("surge", f.surge / SurgeSystem.PER_STAGE)
	_ring_mat.set_shader_parameter("facing_angle", atan2(f.facing.y, f.facing.x))
	var low := f.stamina < f.stats.dash.min_cost()
	_ring_mat.set_shader_parameter("gauge_color", Color(1.0, 0.45, 0.35) if low else team_color.lightened(0.35))
	_ring_mat.set_shader_parameter("pulse", 1.0 if f.state == SM.FOCUSING else 0.0)
	var previewing := Engine.get_process_frames() - _cost_frame <= 1 and _cost_preview > 0.0
	var max_st := maxf(1.0, f.max_stamina())
	if previewing and _cost_ok:
		_ring_mat.set_shader_parameter("spend_from", maxf(0.0, f.stamina - _cost_preview) / max_st)
		_ring_mat.set_shader_parameter("spend_to", f.stamina / max_st)
		_ring_mat.set_shader_parameter("spend_color", Color(1.0, 0.98, 0.88))
	elif previewing:
		_ring_mat.set_shader_parameter("spend_from", f.stamina / max_st)
		_ring_mat.set_shader_parameter("spend_to", minf(1.0, _cost_preview / max_st))
		_ring_mat.set_shader_parameter("spend_color", Color(1.0, 0.3, 0.25))
	else:
		_ring_mat.set_shader_parameter("spend_to", -1.0)
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


func _update_animation(_delta: float) -> void:
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
			# Battle stance; the calm idle stays for the overworld and switching.
			if _landing:
				sprite.play("dash_land", _dir)
			else:
				sprite.play("ready" if sprite.has_animation("ready") else "idle", _dir)
		SM.DASH_START:
			if sprite.has_animation("dash_windup"):
				sprite.play("dash_windup", _dir)
			else:
				sprite.show_frame("dash", _dir, 0)
		SM.DASH_ACTIVE:
			sprite.play("ram" if _ram_pose else "dash", _dir)
		SM.DASH_RECOVERY:
			if _ram_pose:
				sprite.play("ram", _dir)
			elif _landing:
				sprite.play("dash_land", _dir)
			else:
				sprite.play("ready" if sprite.has_animation("ready") else "idle", _dir)
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
	var prev := _last_state
	if st != SM.IDLE and st != SM.DASH_RECOVERY:
		_landing = false
	match st:
		SM.DASH_START:
			squash(1.1, 0.9)
			var heavy_windup := fighter.stats.dash.dash_type == DashProfile.DashType.ARMORED
			Audio.sfx(&"dash_windup", -4.0, 0.05, 40, 0.8 if heavy_windup else 1.0)
		SM.DASH_ACTIVE:
			_launch()
		SM.DASH_RECOVERY:
			if prev == SM.DASH_ACTIVE:
				var heavy := fighter.stats.dash.dash_type == DashProfile.DashType.ARMORED
				squash(1.28 if heavy else 1.24, 0.78 if heavy else 0.82)
				if sprite.has_animation("dash_land") and not _ram_pose:
					_landing = true
					sprite.play("dash_land", _dir, true)
			else:
				squash(0.9, 1.1)
		SM.ATTACK_ACTIVE:
			squash(1.12, 0.92)
		SM.KNOCKED_OUT:
			_ko_time = 0.0
			flash(1.0)


## Travel begins: dust kicked back, an echo left behind, the whoosh.
func _launch() -> void:
	var f := fighter
	var heavy := f.stats.dash.dash_type == DashProfile.DashType.ARMORED
	var home := Vector3(f.dash_home.x, 0.0, f.dash_home.y)
	var world := get_parent()
	Vfx.spawn(world, &"dust_puff", home, -f.dash_dir, Color(1, 1, 1, 0.9), 1.15 if heavy else 0.9)
	Vfx.spawn(world, &"shockwave", home + Vector3(0, 0.02, 0), Vector2.RIGHT, team_color.lightened(0.4), 0.32 if heavy else 0.26)
	_spawn_ghost(home, 0.6, 0.3)
	_ghost_travel = 0.0
	_last_pos = home
	# Longer dashes travel faster: the tear pitches up (up to ~1.2x).
	var cells := maxi(1, f.dash_cells)
	if heavy:
		Audio.sfx(&"dash_roll", -4.0, 0.05, 30)
		Audio.sfx(&"dash_launch", -7.0, 0.03, 30, 0.82)
	else:
		Audio.sfx(&"dash_launch", -1.0, 0.03, 30, 1.0 + 0.05 * float(cells - 1))
	if heavy:
		squash(0.86, 1.12)
	elif f.dash_dir.y != 0.0:
		squash(0.8, 1.26)
	else:
		squash(1.32, 0.76)


## Dash poses that hold over a state (the spring handles the rest).
func _update_dash(delta: float) -> void:
	var f := fighter
	var heavy := f.stats.dash.dash_type == DashProfile.DashType.ARMORED
	var offset := Vector3.ZERO
	if f.state == SM.DASH_START:
		# Coil: crouch and lean away from the lane, glowing a little.
		var u := clampf(float(f.state_tick) / maxf(1.0, float(f.state_duration)), 0.0, 1.0)
		_squash = _squash.lerp(Vector2(1.0 + 0.2 * u, 1.0 - 0.2 * u), 0.45)
		_squash_vel = Vector2.ZERO
		offset = -Vector3(f.dash_dir.x, 0.0, f.dash_dir.y) * 0.09 * u
		_flash = maxf(_flash, 0.35 * u)
		sprite.set_param("flash_color", team_color.lightened(0.55))
	elif f.state == SM.DASH_ACTIVE:
		var u := clampf(float(f.dash_t) / maxf(1.0, float(f.dash_travel_ticks)), 0.0, 1.0)
		# Stretched along the motion while it's fast, a hop for light creatures.
		var stretch := Vector2(0.82, 1.24) if f.dash_dir.y != 0.0 else Vector2(1.3, 0.8)
		if heavy:
			stretch = Vector2(1.12, 0.9)
		var k := pow(1.0 - u, 1.4)
		_squash = Vector2.ONE.lerp(stretch, k)
		_squash_vel = Vector2.ZERO
		if not heavy:
			offset.y = sin(u * PI) * 0.12
		# Afterimages every GHOST_SPACING along the path, placed where each was
		# due on this frame's segment (so low frame rates don't stack them).
		var seg := position - _last_pos
		var seg_len := seg.length()
		_ghost_travel += seg_len
		var made := 0
		while _ghost_travel >= GHOST_SPACING and made < 4:
			_ghost_travel -= GHOST_SPACING
			var due := seg_len - _ghost_travel
			_spawn_ghost(_last_pos + seg * (due / seg_len) if seg_len > 0.0001 else position, 0.42, 0.2)
			made += 1
		_ghost_travel = minf(_ghost_travel, GHOST_SPACING)
		_layout_smear(Vector3(f.dash_home.x, 0.0, f.dash_home.y), position, 1.0)
		_smear_fade = 0.0
	elif _smear_fade >= 0.0:
		_smear_fade += delta
		var k2 := clampf(_smear_fade / SMEAR_FADE, 0.0, 1.0)
		_smear_mat.set_shader_parameter("opacity", 1.0 - k2)
		if k2 >= 1.0:
			_smear.visible = false
			_smear_fade = -1.0
	_last_pos = position
	sprite.position = offset + _knock


func _layout_smear(from: Vector3, to: Vector3, opacity: float) -> void:
	var d := to - from
	var length := Vector2(d.x, d.z).length()
	if length < 0.08:
		_smear.visible = false
		return
	var dir := Vector2(d.x, d.z) / length
	_smear.visible = true
	_smear.global_position = (from + to) * 0.5 + Vector3(0, 0.03, 0)
	_smear.global_rotation = Vector3(0.0, -atan2(dir.y, dir.x), 0.0)
	var width := fighter.radius() * 1.7
	_smear.scale = Vector3(length + fighter.radius(), 1.0, width)
	_smear_mat.set_shader_parameter("opacity", opacity)
	_smear_mat.set_shader_parameter("length_units", length)


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


## A translucent afterimage of the current frame at `at`, fading from
## `start_opacity` over `life` seconds.
func _spawn_ghost(at: Vector3, start_opacity: float, life: float) -> void:
	if sprite.sheet == null or not sprite.sheet.valid:
		return
	var g := PixelSprite3D.new()
	g.set_sheet(sprite.sheet)
	g.use_shader(GHOST_SHADER)
	g.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	get_parent().add_child(g)
	g.global_position = at + sprite.position
	g.scale = sprite.scale
	g.set_param("frame", sprite.get_param("frame"))
	g.set_param("flip_h", sprite.get_param("flip_h"))
	g.playing = false
	g.set_param("tint", team_color)
	g.set_param("opacity", start_opacity)
	var tw := g.create_tween()
	tw.tween_method(func(v: float) -> void: g.set_param("opacity", v), start_opacity, 0.0, life).set_ease(Tween.EASE_IN)
	tw.tween_callback(g.queue_free)
