class_name BattleView
extends Node3D
## Presentation of a BattleSim: arena, camera, creature views, projectile and
## telegraph visuals, and all event feedback (VFX, SFX, damage numbers,
## camera shake, crowd). Purely cosmetic — it never changes the simulation.

signal feedback(kind: StringName, data: Dictionary)

const TEAM_COLORS: Array[Color] = [Color(0.35, 0.9, 0.95), Color(1.0, 0.45, 0.38)]
const FONT := preload("res://assets/fonts/PixelifySans-Bold.ttf")
const SM := FighterSM.State
## A minor label (size < 1) shows at most once per this long per spot.
const MINOR_POPUP_MS := 1000

var sim: BattleSim
var setup: BattleSetup
var camera: BattleCamera
var rig: LightingRig
var arena: ArenaBuilder
var fighter_views: Dictionary = {}  # fighter id -> FighterView
var volume_views: Dictionary = {}  # volume id -> {"node": Node3D, "kind": StringName, ...}
var telegraphs: Array = []  # [{node, fighter, start, ticks}]
var trainer_sprites: Array[PixelSprite3D] = []
var local_team := 0
## Teams played on this device (both in local versus): their dashes are drawn
## in team colours, everyone else's as a hazard.
var friendly_teams: Array[int] = [0]
var preview: DashPreview
## Teams with a player on this device (empty in the AI-vs-AI demo): their
## "blocked" and "out of stamina" feedback is shown.
var local_input_teams: Array[int] = [0]
var debug_draw: MeshInstance3D
var _focus_loops: Dictionary = {}
var _recent_popups: Array = []
var _minor_popups: Dictionary = {}  # "text@x,z" -> msec shown


func build(p_sim: BattleSim, p_setup: BattleSetup) -> void:
	sim = p_sim
	setup = p_setup
	rig = LightingRig.new()
	add_child(rig)
	rig.apply(StringName(setup.metadata.get("lighting", "golden")))
	arena = ArenaBuilder.new()
	arena.build(self, setup.arena)
	camera = BattleCamera.new()
	add_child(camera)
	camera.setup(setup.arena.size)
	camera.make_current()
	for f in sim.fighters:
		_add_fighter_view(f)
	_add_trainers()
	preview = DashPreview.new()
	add_child(preview)
	preview.setup(self)
	debug_draw = MeshInstance3D.new()
	debug_draw.mesh = ImmediateMesh.new()
	var dm := StandardMaterial3D.new()
	dm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	dm.vertex_color_use_as_albedo = true
	dm.no_depth_test = true
	debug_draw.material_override = dm
	add_child(debug_draw)


## Rebuild per-fighter views after a rematch (the sim recreates fighters).
func rebind(p_sim: BattleSim) -> void:
	sim = p_sim
	for v in fighter_views.values():
		(v as Node).queue_free()
	fighter_views.clear()
	for v in volume_views.values():
		var n: Node = v["node"]
		if is_instance_valid(n):
			n.queue_free()
	volume_views.clear()
	for t in telegraphs:
		if is_instance_valid(t["node"]):
			(t["node"] as Node).queue_free()
	telegraphs.clear()
	for f in sim.fighters:
		_add_fighter_view(f)
	preview.rebind()
	for key in _focus_loops.keys():
		Audio.loop_stop(key)
	_focus_loops.clear()
	for s in trainer_sprites:
		s.play("idle", "e" if s.position.x < 0 else "w")


func _add_fighter_view(f: Fighter) -> void:
	var v := FighterView.new()
	add_child(v)
	v.setup(f, TEAM_COLORS[f.team])
	fighter_views[f.id] = v


func _add_trainers() -> void:
	var names: Array = setup.metadata.get("trainer_sprites", [])
	for team in 2:
		if team >= names.size() or str(names[team]) == "":
			continue
		var s := PixelSprite3D.new()
		s.load_manifest("res://assets/sprites/characters/%s.json" % names[team])
		s.position = arena.trainer_spots[team]
		s.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		add_child(s)
		s.play("idle", "e" if team == 0 else "w")
		EnvKit.blob_shadow(self, 0.35, 0.4).position = arena.trainer_spots[team] + Vector3(0, 0.015, 0)
		trainer_sprites.append(s)


func view_of(fid: int) -> FighterView:
	return fighter_views.get(fid)


func is_friendly(team: int) -> bool:
	return team in friendly_teams


## Screen position (0..1) of a world point, for screen-space impact effects.
func screen_uv(p: Vector3) -> Vector2:
	var vp := get_viewport().get_visible_rect().size
	if camera == null or vp.x <= 0.0 or vp.y <= 0.0:
		return Vector2(0.5, 0.5)
	return camera.unproject_position(p) / vp


# --- Per-frame -------------------------------------------------------------------------

func render(alpha: float, delta: float) -> void:
	for v in fighter_views.values():
		(v as FighterView).update_view(alpha, delta)
	preview.update_preview(delta)
	_update_volume_views(alpha)
	_update_telegraphs()
	_update_focus_audio()
	if Settings.show_hitboxes:
		_draw_debug()
	elif debug_draw.visible:
		(debug_draw.mesh as ImmediateMesh).clear_surfaces()
		debug_draw.visible = false


func _update_volume_views(alpha: float) -> void:
	var live := {}
	for vol in sim.volumes:
		live[vol.id] = vol
	for id in volume_views.keys():
		var info: Dictionary = volume_views[id]
		var node: Node3D = info["node"]
		if not is_instance_valid(node):
			volume_views.erase(id)
			continue
		if not live.has(id):
			continue
		var vol: HitVolume = live[id]
		match info["kind"]:
			&"projectile":
				var p := vol.prev_pos.lerp(vol.pos, alpha)
				node.position = Vector3(p.x, 0, p.y)
			&"area":
				var decal: GroundDecal = info["decal"]
				decal.set_progress(float(vol.age) / maxf(1.0, float(vol.delay_ticks)))
				if vol.age >= vol.delay_ticks and not bool(info.get("burst", false)):
					info["burst"] = true
					decal.visible = false
					on_area_live(vol)
			&"wave":
				var wd: GroundDecal = info["decal"]
				wd.set_progress(float(vol.age) / maxf(1.0, float(vol.delay_ticks)))
				if vol.age >= vol.delay_ticks:
					var next: float = info.get("next_spike", 0.0)
					if vol.wave_front >= next:
						var at := vol.origin + vol.dir * maxf(0.3, next)
						Vfx.spawn(self, &"fault_spike", Vector3(at.x, 0, at.y))
						info["next_spike"] = next + 0.75
						if int(info.get("spikes", 0)) % 3 == 0:
							Audio.sfx(&"fault_line_erupt", -4.0, 0.08, 60)
						info["spikes"] = int(info.get("spikes", 0)) + 1


func _update_telegraphs() -> void:
	for t in telegraphs.duplicate():
		var node: GroundDecal = t["node"]
		var f: Fighter = sim.fighter_by_id(t["fighter"])
		var elapsed := sim.tick - int(t["start"])
		var ticks := int(t["ticks"])
		var cancelled := f == null or f.current_ability == null or not FighterSM.is_attacking(f.state)
		if elapsed > ticks + 2 or (cancelled and elapsed > 1):
			node.queue_free()
			telegraphs.erase(t)
			continue
		if bool(t.get("follow", false)) and f:
			node.position = Vector3(f.pos.x, 0.03, f.pos.y)
		node.set_progress(float(elapsed) / maxf(1.0, float(ticks)))


func _update_focus_audio() -> void:
	for f in sim.fighters:
		var key := StringName("focus_%d" % f.id)
		var focusing := f.on_field and (f.state == SM.FOCUSING)
		if focusing and not _focus_loops.has(key):
			_focus_loops[key] = true
			Audio.loop_start(key, &"focus_loop", -8.0 if f.team != local_team else -4.0)
		elif not focusing and _focus_loops.has(key):
			_focus_loops.erase(key)
			Audio.loop_stop(key)


func stop_audio() -> void:
	for key in _focus_loops.keys():
		Audio.loop_stop(key)
	_focus_loops.clear()


# --- Events ------------------------------------------------------------------------------

func handle_events(events: Array[BattleEvent]) -> void:
	for e in events:
		_handle(e)


func _fv(id: int) -> FighterView:
	return fighter_views.get(id)


func _pos3(p: Vector2, h: float = 0.0) -> Vector3:
	return Vector3(p.x, h, p.y)


func _handle(e: BattleEvent) -> void:
	var f := sim.fighter_by_id(e.fighter_id)
	match e.type:
		BattleEvent.COUNTDOWN:
			Audio.sfx(&"countdown_tick")
		BattleEvent.FIGHT_START:
			Audio.sfx(&"fight_start")
			arena.cheer(1.6)
			Audio.sfx(&"crowd_cheer", -10.0)
		BattleEvent.DASH_START:
			# The coil: a little dust gathers under the creature.
			Vfx.spawn(self, &"dust_puff", _pos3(e.pos), Vector2.RIGHT, Color(1, 1, 1, 0.8), 0.6)
		BattleEvent.DASH_LAND:
			_on_dash_land(f, e)
		BattleEvent.DASH_THROUGH:
			_on_ram(f, e)
		BattleEvent.DASH_REPELLED:
			var guard := sim.fighter_by_id(e.target_id)
			Audio.sfx(&"stone_guard_block" if guard and guard.has_status(&"stoneguard") else &"guard_block")
			Vfx.spawn(self, &"perfect_flash" if bool(e.data.get("perfect", false)) else &"hit_spark", _pos3(e.pos), Vector2.RIGHT, Color(0.7, 0.95, 1.0))
			Vfx.spawn(self, &"shockwave", _pos3(e.pos, 0.02), Vector2.RIGHT, Color(0.7, 0.95, 1.0), 0.45)
			popup(_pos3(e.pos, 1.3), "REPELLED!", Color(0.6, 0.9, 1.0), 1.1)
			var rdir: Vector2 = e.data.get("dir", Vector2.ZERO)
			if f:
				_fv(f.id).impact(-rdir, 0.7)
			camera.add_trauma(0.22)
			_camera_kick(-rdir, 0.1)
		BattleEvent.DASH_CLASH:
			Audio.sfx(&"dash_clash", -2.0, 0.03)
			Vfx.spawn(self, &"hit_heavy", _pos3(e.pos), Vector2.RIGHT, Color(1, 1, 1))
			Vfx.spawn(self, &"shockwave", _pos3(e.pos, 0.02), Vector2.RIGHT, Color(1, 1, 1), 0.6)
			Vfx.burst(self, _pos3(e.pos, 0.5), Color(1.0, 0.95, 0.8), 18, 4.0, 0.06, 0.35, -6.0)
			popup(_pos3(e.pos, 1.2), "CLASH!", Color(1, 1, 1), 1.1)
			var cdir: Vector2 = e.data.get("dir", Vector2.RIGHT)
			if f:
				_fv(f.id).impact(-cdir, 0.8)
			var other := _fv(e.target_id)
			if other:
				other.impact(cdir, 0.8)
			camera.add_trauma(0.32)
			_zoom_punch(0.04)
			feedback.emit(&"impact", {"strength": 0.55, "screen": screen_uv(_pos3(e.pos, 0.5)), "teams": _teams_of(f, e.target_id)})
		BattleEvent.DASH_BLOCKED:
			if f and is_friendly(f.team) and _is_local_input(f.team):
				Audio.sfx(&"dash_blocked", -6.0, 0.0, 200)
				popup(_pos3(f.pos, f.species.visual_height + 0.3), "Blocked", Color(1.0, 0.55, 0.45), 0.7)
		BattleEvent.DASH_NO_STAMINA:
			if f and is_friendly(f.team) and _is_local_input(f.team):
				Audio.sfx(&"stamina_empty", -2.0, 0.0, 250)
				popup(_pos3(f.pos, f.species.visual_height + 0.3), "Out of stamina", Color(1.0, 0.5, 0.42), 0.72)
				_fv(f.id).flash(0.6, Color(1.0, 0.4, 0.35))
				feedback.emit(&"no_stamina", {"team": f.team})
		BattleEvent.ABILITY_START:
			var sfx: StringName = e.data.get("sfx", &"")
			if String(sfx).ends_with("_charge"):
				Audio.sfx(sfx, -1.0)
			if f and int(e.data.get("surge", 0)) >= 3:
				# A big special spends its Surge: a swell, a gold flash, a punch-in.
				Audio.sfx(&"surge_release", -2.0 if is_friendly(f.team) else -4.0)
				_fv(f.id).flash(0.45, UiTheme.SURGE)
				_zoom_punch(0.03 * float(int(e.data["surge"]) - 2))
		BattleEvent.SURGE_STAGE:
			if f:
				var st := int(e.data.get("stages", 1))
				var mine := is_friendly(f.team) and _is_local_input(f.team)
				# Each stage rings a step higher (a rising arpeggio to full).
				Audio.sfx(&"surge_stage", -3.0 if mine else -10.0, 0.0, 60, [1.0, 1.122, 1.26, 1.498][clampi(st - 1, 0, 3)])
				_fv(f.id).flash(0.3, UiTheme.SURGE)
				if bool(e.data.get("full", false)):
					popup(_pos3(f.pos, f.species.visual_height + 0.35), "Surge full!", UiTheme.SURGE, 0.8)
		BattleEvent.ABILITY_ACTIVE:
			_on_ability_active(f, e)
		BattleEvent.ABILITY_DENIED:
			if f and f.team == local_team:
				feedback.emit(&"denied", e.data)
				if e.data.get("reason", &"") == &"surge":
					var need := int(e.data.get("surge", 0))
					Audio.sfx(&"stamina_empty", -6.0, 0.0, 250, 1.25)
					popup(_pos3(f.pos, f.species.visual_height + 0.3), "Needs %d Surge" % need, UiTheme.SURGE, 0.7)
		BattleEvent.TELEGRAPH:
			_spawn_telegraph(f, e.data)
		BattleEvent.VOLUME_SPAWN:
			_on_volume_spawn(e.data)
		BattleEvent.VOLUME_END:
			_on_volume_end(e.data)
		BattleEvent.AREA_BURST:
			Vfx.spawn(self, &"shockwave", _pos3(e.pos), Vector2.RIGHT, Color.WHITE, float(e.data.get("radius", 2.0)) / 2.0)
			Vfx.spawn(self, &"rock_burst", _pos3(e.pos))
			Vfx.spawn(self, &"ground_crack", _pos3(e.pos))
			Audio.sfx(&"ground_pound")
			camera.add_trauma(0.45)
		BattleEvent.PROJECTILE_BLOCKED:
			var visual: StringName = e.data.get("visual", &"")
			Vfx.spawn(self, &"rock_burst" if visual == &"boulder" else &"ember_impact", _pos3(e.pos))
			Audio.sfx(&"boulder_impact" if visual == &"boulder" else &"ember_bolt_impact", -3.0)
		BattleEvent.PROJECTILE_CLASH:
			Vfx.spawn(self, &"hit_spark", _pos3(e.pos), Vector2.RIGHT, Color(1.0, 0.8, 0.5))
			Audio.sfx(&"projectile_clash")
			popup(_pos3(e.pos, 1.0), "CLASH", Color(1.0, 0.85, 0.6), 0.8)
		BattleEvent.HIT:
			_on_hit(e)
		BattleEvent.EVADE:
			popup(_pos3(e.pos, 1.3), "EVADE", Color(0.6, 1.0, 0.95), 0.9)
		BattleEvent.BLOCK:
			Audio.sfx(&"guard_block")
			Vfx.spawn(self, &"hit_spark", _pos3(e.pos), Vector2.RIGHT, Color(0.6, 0.85, 1.0))
			popup(_pos3(e.pos, 1.3), "BLOCK", Color(0.6, 0.85, 1.0), 0.85)
			camera.add_trauma(0.1)
		BattleEvent.PERFECT_GUARD:
			Audio.sfx(&"perfect_guard")
			Vfx.spawn(self, &"perfect_flash", _pos3(e.pos))
			if f:
				_fv(f.id).flash(1.0, Color(1.0, 0.95, 0.7))
			popup(_pos3(e.pos, 1.5), "PERFECT!", Color(1.0, 0.92, 0.45), 1.3)
			feedback.emit(&"perfect_guard", {"team": f.team if f else -1})
		BattleEvent.GUARD_BREAK:
			Audio.sfx(&"guard_break")
			Vfx.spawn(self, &"guard_break", _pos3(e.pos))
			popup(_pos3(e.pos, 1.5), "GUARD BREAK!", Color(1.0, 0.45, 0.35), 1.2)
			camera.add_trauma(0.45)
		BattleEvent.STUN_RESISTED:
			if f and f.steadfast > 0:
				popup(_pos3(f.pos, 1.5), "STEADFAST", Color(1.0, 1.0, 0.9), 0.85)
		BattleEvent.STATUS_APPLIED:
			var sid: StringName = e.data.get("status", &"")
			var label: String = {&"burn": "Burn", &"slow": "Slowed", &"stoneguard": "Stone Guard"}.get(sid, "")
			if label != "" and f:
				popup(_pos3(f.pos, 1.6), label, Color(1.0, 0.65, 0.3) if sid == &"burn" else (Color(0.8, 0.95, 0.7) if sid == &"stoneguard" else Color(0.85, 0.75, 0.6)), 0.8)
		BattleEvent.DOT:
			if f:
				popup(_pos3(f.pos, 1.1), str(int(ceil(float(e.data.get("damage", 1))))), Color(1.0, 0.6, 0.3), 0.75)
				Audio.sfx(&"burn_tick", -8.0)
		BattleEvent.FOCUS_START:
			Audio.sfx(&"focus_start", -4.0)
		BattleEvent.FOCUS_INTERRUPTED:
			if f:
				popup(_pos3(f.pos, 1.5), "Focus broken!", Color(1.0, 0.5, 0.5), 0.85)
		BattleEvent.STAMINA_FULL:
			if f:
				Audio.sfx(&"focus_full", -2.0)
				_fv(f.id).flash(0.5, Color(0.6, 1.0, 1.0))
		BattleEvent.LUNGE:
			Vfx.spawn(self, &"dust_puff", _pos3(e.pos))
		BattleEvent.SWITCH_START:
			Audio.sfx(&"ui_select")
		BattleEvent.SWITCH_IN:
			if f:
				Vfx.spawn(self, &"dust_puff", _pos3(f.pos))
				_fv(f.id).flash(1.0)
		BattleEvent.KO:
			_on_ko(f, e)
		BattleEvent.BATTLE_END:
			var winner := int(e.data.get("winner", -1))
			for v in fighter_views.values():
				var fv := v as FighterView
				fv.victory = fv.fighter.team == winner and not fv.fighter.is_ko()
			for i in trainer_sprites.size():
				var s := trainer_sprites[i]
				s.play("cheer" if i == winner else ("slump" if s.has_animation("slump") else "idle"), "s")


func _on_ability_active(f: Fighter, e: BattleEvent) -> void:
	if f == null or f.current_ability == null:
		return
	var ab := f.current_ability
	var sfx := ab.cast_sfx
	if sfx != &"" and not String(sfx).ends_with("_charge"):
		Audio.sfx(sfx, -1.0)
	elif ab.kind == AbilityDefinition.Kind.BASIC:
		Audio.sfx(&"flash_strike" if ab.id == &"tail_swipe_3" else &"dash_whoosh", -8.0, 0.12)
	for c in ab.components:
		if c is MeleeComponent:
			var m := c as MeleeComponent
			var origin := f.pos + f.ability_dir * m.forward_offset
			if m.visual == &"cinder_arc":
				Vfx.spawn(self, &"cinder_arc", _pos3(f.pos), f.ability_dir, Color.WHITE, m.radius / 2.0)
			elif m.visual == &"flash_strike":
				Vfx.spawn(self, &"flash_strike", _pos3(origin), f.ability_dir)
			else:
				_swipe_decal(f, m)
		elif c is SelfStatusComponent:
			Vfx.spawn(self, &"dust_puff", _pos3(f.pos))


## Landing: dust where it touches down; heavy creatures thud.
func _on_dash_land(f: Fighter, e: BattleEvent) -> void:
	if f == null:
		return
	var heavy := f.stats.dash.dash_type == DashProfile.DashType.ARMORED
	var dir: Vector2 = e.data.get("dir", Vector2.RIGHT)
	Vfx.spawn(self, &"dust_puff", _pos3(e.pos), dir, Color(1, 1, 1, 0.85), 0.95 if heavy else 0.7)
	Audio.sfx(&"dash_land", -2.0 if heavy else -5.0, 0.04, 40, 0.84 if heavy else 1.0)
	if heavy:
		camera.add_trauma(0.08)
		_camera_kick(dir, 0.05)


## A ram (dash through a foe): the signature hit. Freeze frame (the sim's
## hitstop), a slash along the lane, sparks, a shockwave, a camera punch and
## an impact frame.
func _on_ram(f: Fighter, e: BattleEvent) -> void:
	var target := _fv(e.target_id)
	var dir: Vector2 = e.data.get("dir", Vector2.RIGHT)
	var at := _pos3(e.pos)
	if not bool(e.data.get("stunned", false)):
		Audio.sfx(&"ram_whiff", -3.0)
		Vfx.spawn(self, &"hit_spark", at, dir, Color(0.75, 0.82, 0.95), 0.7)
		popup(at + Vector3(0, 1.3, 0), "Protected", Color(0.75, 0.8, 0.9), 0.75)
		return
	Audio.sfx(&"ram_impact", 0.0, 0.04)
	var gold := Color(1.0, 0.86, 0.45)
	Vfx.spawn(self, &"hit_heavy", at, dir, Color(1.0, 0.97, 0.85), 1.15)
	Vfx.spawn(self, &"flash_strike", at + Vector3(0, 0.1, 0), dir, Color(1.0, 0.95, 0.8), 1.25)
	Vfx.spawn(self, &"shockwave", at + Vector3(0, 0.02, 0), Vector2.RIGHT, gold, 0.75)
	Vfx.burst(self, at + Vector3(0, 0.55, 0), gold, 22, 5.0, 0.07, 0.4, -7.0)
	if target:
		target.impact(dir, 1.0)
	if f:
		_fv(f.id).flash(0.65, Color(1.0, 0.98, 0.9))
		_fv(f.id).ram_pose()
	popup(at + Vector3(0, 1.8, 0), "RAM!", gold, 1.3)
	camera.add_trauma(0.38)
	_camera_kick(dir, 0.2)
	_zoom_punch(0.06)
	arena.cheer(1.0)
	Audio.sfx(&"crowd_gasp", -12.0, 0.05, 400)
	feedback.emit(&"impact", {"strength": 1.0, "screen": screen_uv(at + Vector3(0, 0.5, 0)), "teams": _teams_of(f, e.target_id)})


## Teams of the two creatures in an exchange (for haptics on local players).
func _teams_of(f: Fighter, other_id: int) -> Array[int]:
	var out: Array[int] = []
	if f:
		out.append(f.team)
	var o := sim.fighter_by_id(other_id)
	if o:
		out.append(o.team)
	return out


func _camera_kick(dir: Vector2, amount: float) -> void:
	if camera.has_method(&"kick"):
		camera.call(&"kick", dir, amount)


func _zoom_punch(amount: float) -> void:
	if camera.has_method(&"zoom_punch"):
		camera.call(&"zoom_punch", amount)


## True when a player on this device controls `team` (set by the scene).
func _is_local_input(team: int) -> bool:
	return team in local_input_teams


## A brief translucent arc showing exactly where a basic attack can hit.
func _swipe_decal(f: Fighter, m: MeleeComponent) -> void:
	var d := GroundDecal.new()
	add_child(d)
	var origin := f.pos + f.ability_dir * m.forward_offset
	d.position = Vector3(origin.x, 0.03, origin.y)
	if m.shape == MeleeComponent.MeleeShape.CONE:
		d.set_circle(m.radius, GroundDecal.Shape.CONE, 0.0, deg_to_rad(m.angle_deg) * 0.5)
	else:
		d.set_circle(m.radius, GroundDecal.Shape.CIRCLE)
	d.aim(f.ability_dir)
	var col := BattleView.TEAM_COLORS[f.team].lightened(0.5)
	d.set_colors(col, col, 0.55)
	d.set_progress(1.0)
	var tw := d.create_tween()
	tw.tween_method(d.set_opacity, 0.55, 0.0, 0.14)
	tw.tween_callback(d.queue_free)


func _spawn_telegraph(f: Fighter, data: Dictionary) -> void:
	if f == null:
		return
	var d := GroundDecal.new()
	add_child(d)
	var shape: int = data.get("shape", HitVolume.Shape.CIRCLE)
	var pos: Vector2 = data.get("pos", f.pos)
	var dir: Vector2 = data.get("dir", Vector2.RIGHT)
	d.position = Vector3(pos.x, 0.03, pos.y)
	match shape:
		HitVolume.Shape.BOX:
			d.set_box(float(data.get("length", 3.0)), float(data.get("width", 1.0)))
		HitVolume.Shape.CONE:
			d.set_circle(float(data.get("radius", 2.0)), GroundDecal.Shape.CONE, 0.0, float(data.get("half_angle", 0.8)))
		_:
			d.set_circle(float(data.get("radius", 2.0)))
	d.aim(dir)
	var col := Color(1.0, 0.45, 0.25) if f.team != local_team else Color(1.0, 0.75, 0.35)
	d.set_colors(col, col)
	telegraphs.append({"node": d, "fighter": f.id, "start": sim.tick, "ticks": int(data.get("ticks", 20)), "follow": bool(data.get("follow", false))})


func _on_volume_spawn(data: Dictionary) -> void:
	var id: int = data.get("id", -1)
	var motion: int = data.get("motion", 0)
	var pos: Vector2 = data.get("pos", Vector2.ZERO)
	var dir: Vector2 = data.get("dir", Vector2.RIGHT)
	var visual: StringName = data.get("visual", &"")
	var team: int = data.get("team", 0)
	match motion:
		HitVolume.Motion.PROJECTILE:
			var holder := Node3D.new()
			add_child(holder)
			holder.position = Vector3(pos.x, 0, pos.y)
			var is_boulder := visual == &"boulder"
			var radius: float = data.get("radius", 0.25)
			var fx := Vfx.spawn(holder, &"boulder" if is_boulder else &"ember_bolt", Vector3.ZERO, dir, Color.WHITE, radius / 0.5 if is_boulder else 1.0, true)
			if fx is Vfx:
				var vfx := fx as Vfx
				vfx.position = Vector3(0, 0.5 if not is_boulder else radius, 0)
				if not is_boulder:
					vfx.set_rotation_angle(Vfx.screen_angle(dir))
			var trail := Vfx.trail(Color(0.75, 0.65, 0.5) if is_boulder else Color(1.0, 0.55, 0.2), 0.08 if is_boulder else 0.06, 18, 0.4)
			holder.add_child(trail)
			trail.position = Vector3(0, 0.4, 0)
			trail.emitting = true
			EnvKit.blob_shadow(holder, maxf(0.18, radius), 0.35)
			volume_views[id] = {"node": holder, "kind": &"projectile"}
		HitVolume.Motion.STATIC:
			var delay: int = data.get("delay", 0)
			if delay > 0:
				var d := GroundDecal.new()
				add_child(d)
				d.position = Vector3(pos.x, 0.03, pos.y)
				d.set_circle(float(data.get("radius", 1.5)))
				var col := Color(1.0, 0.4, 0.2) if team != local_team else Color(1.0, 0.7, 0.3)
				d.set_colors(col, col)
				volume_views[id] = {"node": d, "kind": &"area", "decal": d, "visual": visual, "pos": pos, "radius": data.get("radius", 1.5)}
		HitVolume.Motion.WAVE:
			var w := GroundDecal.new()
			add_child(w)
			var origin: Vector2 = data.get("origin", pos)
			w.position = Vector3(origin.x, 0.03, origin.y)
			w.set_box(float(data.get("wave_total", 6.0)), float(data.get("width", 1.0)))
			w.aim(dir)
			var wc := Color(0.95, 0.75, 0.4) if team == local_team else Color(1.0, 0.5, 0.3)
			w.set_colors(wc, wc)
			volume_views[id] = {"node": w, "kind": &"wave", "decal": w, "next_spike": 0.3}


func _on_volume_end(data: Dictionary) -> void:
	var id: int = data.get("volume", -1)
	if not volume_views.has(id):
		return
	var info: Dictionary = volume_views[id]
	var node: Node3D = info["node"]
	volume_views.erase(id)
	if info["kind"] == &"area" and StringName(data.get("reason", &"")) == &"expired":
		pass
	if is_instance_valid(node):
		node.queue_free()


## Delayed areas become live: burst visuals (called from the HIT-agnostic
## volume age check in BattleScene via live transitions).
func on_area_live(vol: HitVolume) -> void:
	var p := Vector3(vol.pos.x, 0, vol.pos.y)
	if vol.visual == &"heat_ring":
		Vfx.spawn(self, &"heat_ring", p, Vector2.RIGHT, Color.WHITE, vol.radius / 1.7)
		for i in 6:
			var a := float(i) / 6.0 * TAU
			Vfx.spawn(self, &"fire_pillar", p + Vector3(cos(a), 0, sin(a)) * vol.radius * 0.7)
		Vfx.spawn(self, &"scorch", p)
		Audio.sfx(&"heat_ring_burst")
		camera.add_trauma(0.3)


func _on_hit(e: BattleEvent) -> void:
	var target := _fv(e.target_id)
	var dmg := float(e.data.get("damage", 0.0))
	var eff := float(e.data.get("eff", 1.0))
	var heavy := bool(e.data.get("heavy", false))
	var p3 := _pos3(e.pos, 0.0)
	if bool(e.data.get("ram", false)):
		# The ram's own impact (DASH_THROUGH) sells it; just the number here.
		popup(p3 + Vector3(0, 1.1, 0), str(int(ceil(dmg))), Color(1.0, 0.92, 0.7), 1.25)
		feedback.emit(&"hit", {"target": e.target_id, "damage": dmg, "heavy": true})
		return
	var vfx_id: StringName = e.data.get("vfx", &"hit_spark")
	if vfx_id == &"cinder_arc" or vfx_id == &"heat_ring" or vfx_id == &"shockwave" or vfx_id == &"fault_spike":
		vfx_id = &"hit_heavy" if heavy else &"hit_spark"
	Vfx.spawn(self, vfx_id, p3)
	Audio.sfx(e.data.get("sfx", &"hit_light"), 0.0 if heavy else -2.0)
	var color := Color(1, 1, 1)
	var label := str(int(ceil(dmg)))
	if eff >= ElementChart.EFFECTIVE_THRESHOLD:
		color = Color(1.0, 0.72, 0.3)
		Audio.sfx(&"hit_effective", -6.0)
	elif eff <= ElementChart.RESISTED_THRESHOLD:
		color = Color(0.72, 0.74, 0.8)
		Audio.sfx(&"hit_resisted", -8.0)
	popup(p3 + Vector3(0, 1.1, 0), label, color, 1.3 if heavy else 1.0)
	var eff_label := ElementChart.effectiveness_label(eff)
	if eff_label != "":
		popup(p3 + Vector3(0, 1.55, 0), eff_label, color, 0.7)
	if target:
		target.flash(1.0)
		target.squash(0.86, 1.1)
	if bool(e.data.get("armored", false)):
		popup(p3 + Vector3(0, 1.75, 0), "ARMOR", Color(0.85, 0.85, 0.75), 0.7)
	camera.add_trauma(0.32 if heavy else 0.12)
	feedback.emit(&"hit", {"target": e.target_id, "damage": dmg, "heavy": heavy})


func _on_ko(f: Fighter, e: BattleEvent) -> void:
	if f == null:
		return
	if bool(e.data.get("training", false)):
		popup(_pos3(f.pos, 1.6), "Reset!", Color(0.9, 0.9, 0.8), 0.9)
		return
	Audio.sfx(&"ko_hit")
	Vfx.spawn(self, &"ko_burst", _pos3(f.pos))
	camera.add_trauma(0.8)
	arena.cheer(3.0)
	Audio.sfx(&"crowd_cheer", -6.0)
	feedback.emit(&"ko", {"team": f.team})
	var tree := get_tree()
	if tree:
		await tree.create_timer(0.45).timeout
		Audio.sfx(&"ko_fall")


## Floating combat text (damage numbers, RAM!, PERFECT!, ...). Texts that
## would land on top of a recent one stack above it instead.
func popup(pos: Vector3, text: String, color: Color, size_mult: float = 1.0) -> void:
	var now := Time.get_ticks_msec()
	# Minor labels ("Resisted", "Focus broken!") repeat on every burn tick or
	# multi-hit: show each one once a second per spot. Callouts and numbers
	# always show.
	if size_mult < 1.0 and not text.is_valid_int():
		for k in _minor_popups.keys():
			if now - int(_minor_popups[k]) > MINOR_POPUP_MS:
				_minor_popups.erase(k)
		var key := "%s@%d,%d" % [text, roundi(pos.x), roundi(pos.z)]
		if _minor_popups.has(key):
			return
		_minor_popups[key] = now
	_recent_popups = _recent_popups.filter(func(r: Dictionary) -> bool: return now - int(r["t"]) < 450)
	var lift := 0.0
	for r in _recent_popups:
		var rp: Vector3 = r["pos"]
		if absf(rp.x - pos.x) < 1.1 and absf(rp.z - pos.z) < 0.9 and absf(rp.y + float(r["lift"]) - (pos.y + lift)) < 0.34:
			lift = rp.y + float(r["lift"]) - pos.y + 0.36
	_recent_popups.append({"pos": pos, "lift": lift, "t": now})
	pos.y += lift
	var l := Label3D.new()
	l.text = text
	l.font = FONT
	l.font_size = int(44 * size_mult)
	l.outline_size = 10
	l.outline_modulate = Color(0.08, 0.05, 0.1)
	l.modulate = color
	l.pixel_size = 0.0105
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	l.render_priority = 10
	l.outline_render_priority = 9
	l.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	l.position = pos + Vector3(randf_range(-0.2, 0.2), 0, 0)
	add_child(l)
	l.scale = Vector3.ONE * 1.5
	var tw := l.create_tween()
	tw.set_parallel(true)
	tw.tween_property(l, "scale", Vector3.ONE, 0.12).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_property(l, "position:y", pos.y + 0.75, 0.75).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tw.chain().tween_property(l, "modulate:a", 0.0, 0.25)
	tw.chain().tween_callback(l.queue_free)


# --- Debug overlay (F3 / settings): hurtboxes, hitboxes, logical cells ------------

func _draw_debug() -> void:
	debug_draw.visible = true
	var im := debug_draw.mesh as ImmediateMesh
	im.clear_surfaces()
	im.surface_begin(Mesh.PRIMITIVE_LINES)
	for f in sim.on_field_fighters():
		_circle(im, f.pos, f.radius(), Color(0.3, 1.0, 0.4))
		_circle(im, f.pos, f.hurt_radius(), Color(1.0, 1.0, 0.3))
	for v in sim.volumes:
		var col := Color(1.0, 0.25, 0.25) if v.is_live() else Color(1.0, 0.6, 0.2, 0.5)
		match v.shape:
			HitVolume.Shape.CIRCLE:
				_circle(im, v.pos, v.radius, col)
			HitVolume.Shape.RING:
				_circle(im, v.pos, v.radius, col)
				_circle(im, v.pos, v.inner_radius, col)
			HitVolume.Shape.CONE:
				_circle(im, v.pos, v.radius, col, v.dir.angle() - v.half_angle, v.dir.angle() + v.half_angle)
				_line(im, v.pos, v.pos + v.dir.rotated(v.half_angle) * v.radius, col)
				_line(im, v.pos, v.pos + v.dir.rotated(-v.half_angle) * v.radius, col)
			HitVolume.Shape.BOX:
				var side := CombatConst.perpendicular(v.dir) * v.width * 0.5
				var a := v.pos + side
				var b := v.pos + v.dir * v.length + side
				var c := v.pos + v.dir * v.length - side
				var d := v.pos - side
				_line(im, a, b, col)
				_line(im, b, c, col)
				_line(im, c, d, col)
				_line(im, d, a, col)
	for o in sim.geometry.obstacles:
		if o.kind == ArenaGeometry.Obstacle.CIRCLE:
			_circle(im, o.center, o.radius, Color(0.6, 0.6, 1.0))
	im.surface_end()


func _circle(im: ImmediateMesh, c: Vector2, r: float, col: Color, a0: float = 0.0, a1: float = TAU) -> void:
	var n := 24
	for i in n:
		var t0 := lerpf(a0, a1, float(i) / n)
		var t1 := lerpf(a0, a1, float(i + 1) / n)
		_line(im, c + Vector2(cos(t0), sin(t0)) * r, c + Vector2(cos(t1), sin(t1)) * r, col)


func _line(im: ImmediateMesh, a: Vector2, b: Vector2, col: Color) -> void:
	im.surface_set_color(col)
	im.surface_add_vertex(Vector3(a.x, 0.06, a.y))
	im.surface_set_color(col)
	im.surface_add_vertex(Vector3(b.x, 0.06, b.y))
