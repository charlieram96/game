class_name DashPreview
extends Node3D
## Shows dashes on the board.
##
## * Aim: while a local player drags (or holds a direction), the lane of
##   tiles the dash will cross, a reticle and a ghost of the creature on the
##   landing cell, the stamina it costs, RAM! over a foe it will hit, and
##   where a wall or stone cuts it short. Drawn from DashSystem.plan(), the
##   same plan the simulation executes on release.
## * Committed: every creature's dash flashes its lane on the windup
##   (an opponent's with hazard stripes) and the tiles flare and fade as the
##   creature passes over them.
## Purely cosmetic: reads the simulation, never changes it.

const LANE_SHADER := preload("res://shaders/dash_lane.gdshader")
const RETICLE_SHADER := preload("res://shaders/dash_reticle.gdshader")
const BEAM_SHADER := preload("res://shaders/dash_beam.gdshader")
const GHOST_SHADER := preload("res://shaders/pixel_ghost.gdshader")
const FONT := preload("res://assets/fonts/PixelifySans-Bold.ttf")
const SM := FighterSM.State

const NO_STAMINA_COLOR := Color(1.0, 0.42, 0.32)
const CANCEL_COLOR := Color(0.62, 0.64, 0.7)
const DANGER_COLOR := Color(1.0, 0.44, 0.3)
const RAM_COLOR := Color(1.0, 0.8, 0.32)
const FADE_TIME := 0.28

var view: BattleView
var _aims: Array[AimMarker] = []
var _committed: Dictionary = {}  # fighter id -> {"lane": DashLane, "fade": float, "flash": float, "start_tick": int}


func setup(p_view: BattleView) -> void:
	view = p_view


## Show the aim of a local input source (one per local player).
func add_source(source: LocalInputSource, team: int) -> void:
	var m := AimMarker.new()
	add_child(m)
	m.build(source, team, BattleView.TEAM_COLORS[team])
	_aims.append(m)


func clear_sources() -> void:
	for m in _aims:
		m.queue_free()
	_aims.clear()


## After a rematch the simulation (and its fighters) is new.
func rebind() -> void:
	for info in _committed.values():
		(info["lane"] as Node).queue_free()
	_committed.clear()
	for m in _aims:
		m.reset()


## (cost, affordable) of the dash `team` is aiming, or (0, true) if none.
func cost_preview(team: int) -> Vector2:
	for m in _aims:
		if m.team == team and m.showing and not m.cancelled:
			return Vector2(m.cost, 1.0 if m.affordable else 0.0)
	return Vector2(0.0, 1.0)


func update_preview(delta: float) -> void:
	var sim := view.sim
	if sim == null:
		return
	for m in _aims:
		m.refresh(view, sim, delta)
	_update_committed(sim, delta)


# --- Committed dashes --------------------------------------------------------------

func _update_committed(sim: BattleSim, delta: float) -> void:
	for f in sim.fighters:
		var dashing := f.on_field and (f.state == SM.DASH_START or f.state == SM.DASH_ACTIVE)
		var info: Dictionary = _committed.get(f.id, {})
		if dashing:
			# A new dash: first sight of it, or a windup that started on a later tick.
			var start_tick := sim.tick - f.state_tick if f.state == SM.DASH_START else int(info.get("start_tick", -1))
			var fresh := info.is_empty() or bool(info.get("done", false))
			if f.state == SM.DASH_START and int(info.get("start_tick", -1)) != start_tick:
				fresh = true
			if fresh:
				info = _begin_committed(sim, f, info)
				info["start_tick"] = start_tick
				_committed[f.id] = info
			var lane: DashLane = info["lane"]
			lane.visible = true
			var along := 0.0
			if f.state == SM.DASH_ACTIVE:
				along = (f.pos - f.dash_home).dot(f.dash_dir)
			# Tile k spans [k, k + 1) from the home cell's far edge: the creature
			# is over tile k once it has travelled k + 0.5 cells.
			lane.set_param(&"consumed", along - 0.5 if f.state == SM.DASH_ACTIVE else -1.0)
			info["flash"] = maxf(0.0, float(info["flash"]) - delta * 5.0)
			lane.set_param(&"flash", float(info["flash"]))
			lane.set_param(&"opacity", 1.0)
			lane.advance(delta)
		elif not info.is_empty():
			var lane2: DashLane = info["lane"]
			info["fade"] = float(info["fade"]) + delta
			var k := clampf(float(info["fade"]) / FADE_TIME, 0.0, 1.0)
			lane2.set_param(&"consumed", float(lane2.span) + 0.5)
			lane2.set_param(&"opacity", 1.0 - k)
			if k >= 1.0 and not bool(info.get("done", false)):
				lane2.hide_lane()
				info["start_tick"] = -1
				info["done"] = true


func _begin_committed(sim: BattleSim, f: Fighter, info: Dictionary) -> Dictionary:
	var lane: DashLane = info.get("lane")
	if lane == null:
		lane = DashLane.new()
		add_child(lane)
	var arena := sim.setup.arena
	var dir_index := Cardinal.index_of(f.dash_dir)
	var home_cell := arena.cell_of(f.dash_home)
	var cells := maxi(1, f.dash_cells)
	lane.hide_lane()
	lane.layout(f.dash_home, home_cell, dir_index, cells)
	var foes := {}
	for o in sim.on_field_fighters():
		if o.team != f.team and not o.is_ko():
			foes[arena.cell_of(o.pos)] = true
	var states: Array[int] = []
	var step := Vector2i(int(f.dash_dir.x), int(f.dash_dir.y))
	for k in range(1, cells + 1):
		var c := home_cell + step * k
		states.append(DashLane.Cell.LANDING if k == cells else (DashLane.Cell.RAM if foes.has(c) else DashLane.Cell.PATH))
	lane.set_cells(states)
	var local := view.is_friendly(f.team)
	var col: Color = BattleView.TEAM_COLORS[f.team] if local else DANGER_COLOR
	lane.set_colors(col.lightened(0.1), Color(1.0, 1.0, 0.95))
	lane.set_param(&"danger", 0.0 if local else 1.0)
	lane.set_param(&"ram_color", RAM_COLOR)
	lane.set_param(&"scroll_speed", 3.5)
	lane.reveal_target = float(cells)
	# Your own dash takes over from the aim lane at full size; an opponent's
	# shoots out from it so the windup reads.
	lane.reveal = float(cells) if local else 0.0
	lane.visible = true
	return {"lane": lane, "fade": 0.0, "flash": 1.0 if local else 0.6, "start_tick": -1, "done": false}


# --- Aim marker (one per local player) -----------------------------------------------

class AimMarker:
	extends Node3D

	var source: LocalInputSource
	var team := 0
	var team_color := Color.WHITE
	var lane: DashLane
	var reticle: MeshInstance3D
	var beam: MeshInstance3D
	var ghost: PixelSprite3D
	var label: Label3D
	var ram_labels: Array[Label3D] = []
	var showing := false
	var cancelled := false
	var affordable := true
	var cost := 0.0
	var _reticle_mat: ShaderMaterial
	var _beam_mat: ShaderMaterial
	var _marker_pos := Vector3.ZERO
	var _marker_cell := Vector2i(-9999, -9999)
	var _lock := 1.0
	var _last_key := Vector3i(-1, -1, -1)
	var _ghost_fighter := -1
	var _fade := 0.0

	func build(p_source: LocalInputSource, p_team: int, color: Color) -> void:
		source = p_source
		team = p_team
		team_color = color
		lane = DashLane.new()
		add_child(lane)
		reticle = MeshInstance3D.new()
		var pm := PlaneMesh.new()
		pm.size = Vector2.ONE * 1.7
		reticle.mesh = pm
		_reticle_mat = ShaderMaterial.new()
		_reticle_mat.shader = RETICLE_SHADER
		_reticle_mat.render_priority = -1
		reticle.material_override = _reticle_mat
		reticle.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(reticle)
		beam = MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.3
		cm.bottom_radius = 0.36
		cm.height = 1.0
		cm.radial_segments = 24
		cm.rings = 1
		cm.cap_top = false
		cm.cap_bottom = false
		beam.mesh = cm
		_beam_mat = ShaderMaterial.new()
		_beam_mat.shader = BEAM_SHADER
		beam.material_override = _beam_mat
		beam.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(beam)
		ghost = PixelSprite3D.new()
		ghost.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(ghost)
		label = _make_label(46)
		add_child(label)
		_hide_all()

	func reset() -> void:
		_ghost_fighter = -1
		_last_key = Vector3i(-1, -1, -1)
		_hide_all()

	func _make_label(font_size: int) -> Label3D:
		var l := Label3D.new()
		l.font = FONT
		l.font_size = font_size
		l.outline_size = 9
		l.outline_modulate = Color(0.06, 0.05, 0.1, 0.95)
		l.pixel_size = 0.0098
		l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		l.no_depth_test = true
		l.render_priority = 12
		l.outline_render_priority = 11
		l.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
		return l

	func _hide_all() -> void:
		showing = false
		cancelled = false
		cost = 0.0
		affordable = true
		lane.hide_lane()
		reticle.visible = false
		beam.visible = false
		ghost.visible = false
		label.visible = false
		for l in ram_labels:
			l.visible = false

	func refresh(view: BattleView, sim: BattleSim, delta: float) -> void:
		var aim := source.aim_state
		var f := sim.active_fighter(team)
		if f == null or not f.on_field or f.is_ko() or not aim.active or aim.dir_index < 0 or not source.enabled:
			if showing:
				_hide_all()
			_last_key = Vector3i(-1, -1, -1)
			return
		# While the creature is mid-dash its committed lane is on screen; the
		# next aim appears once it lands.
		if f.state == SM.DASH_START or f.state == SM.DASH_ACTIVE:
			_hide_all()
			return
		var plan := DashSystem.plan(sim, f, aim.dir_index, aim.cells)
		var arena := sim.setup.arena
		showing = true
		cancelled = aim.cancelled
		cost = plan.cost
		affordable = plan.result != DashPlan.Result.NO_STAMINA
		_sounds(plan, aim)
		# Lane tiles.
		var states := _lane_states(sim, f, plan)
		lane.layout(plan.home, plan.home_cell, plan.dir_index, states.size())
		lane.set_cells(states)
		var main := team_color
		var opacity := 1.0
		if cancelled:
			main = CANCEL_COLOR
			opacity = 0.4
		elif not affordable:
			main = NO_STAMINA_COLOR
		# Aiming while the creature can't dash yet (stunned, mid-attack): dimmed.
		var busy := f.state == SM.STUNNED or f.state == SM.SWITCHING or f.state == SM.ATTACK_START or f.state == SM.ATTACK_ACTIVE
		if busy:
			opacity *= 0.55
		lane.set_colors(main.lightened(0.12), Color(1.0, 1.0, 0.96))
		lane.set_param(&"ram_color", RAM_COLOR)
		lane.set_param(&"opacity", opacity)
		lane.set_param(&"danger", 0.0)
		lane.set_param(&"flash", 0.0)
		lane.set_param(&"consumed", -1.0)
		lane.set_param(&"scroll_speed", 1.5)
		lane.reveal_target = float(states.size())
		lane.visible = true
		lane.advance(delta)
		# Reticle, beam and ghost on the landing cell.
		var landed := plan.cells > 0 and not cancelled
		var target3 := Vector3(plan.target.x, 0.0, plan.target.y)
		if plan.target_cell != _marker_cell:
			var jump := _marker_cell.x < -999 or (plan.target_cell - _marker_cell).abs().x + (plan.target_cell - _marker_cell).abs().y > 1
			if jump:
				_marker_pos = target3
			_marker_cell = plan.target_cell
			_lock = 0.0
		_marker_pos = _marker_pos.lerp(target3, 1.0 - exp(-delta * 32.0))
		_lock = minf(1.0, _lock + delta * 7.0)
		reticle.visible = landed
		beam.visible = landed and affordable
		var rc := team_color.lightened(0.25) if affordable else NO_STAMINA_COLOR
		reticle.position = _marker_pos + Vector3(0, 0.03, 0)
		_reticle_mat.set_shader_parameter("color", rc)
		_reticle_mat.set_shader_parameter("lock", _lock)
		_reticle_mat.set_shader_parameter("opacity", opacity)
		_reticle_mat.set_shader_parameter("charge", aim.charge_fraction if aim.device == &"charge" and aim.cells < DashSystem.max_cells(f) else -1.0)
		beam.position = _marker_pos + Vector3(0, 0.5, 0)
		_beam_mat.set_shader_parameter("color", team_color.lightened(0.2))
		_beam_mat.set_shader_parameter("opacity", 0.75 * opacity)
		_update_ghost(view, f, plan, landed, opacity)
		# Cost readout above the ghost.
		label.visible = plan.cost > 0.0 or cancelled
		label.position = _marker_pos + Vector3(0, f.species.visual_height + 0.42, 0)
		if cancelled:
			label.text = "Cancel"
			label.modulate = Color(0.85, 0.86, 0.9)
		elif not affordable:
			label.text = "Need %d" % int(ceil(plan.cost))
			label.modulate = NO_STAMINA_COLOR.lightened(0.15)
		elif plan.cells > 0:
			label.text = "-%d" % int(ceil(plan.cost))
			label.modulate = team_color.lightened(0.55)
		else:
			label.visible = false
		# RAM! over each foe the dash will hit.
		var n := 0
		if not cancelled:
			for id in plan.rams:
				var o := sim.fighter_by_id(id)
				if o == null:
					continue
				var l := _ram_label(n)
				l.visible = true
				l.text = "RAM!"
				l.modulate = RAM_COLOR if affordable else RAM_COLOR.darkened(0.3)
				var bob := 0.06 * sin(Time.get_ticks_msec() * 0.012)
				l.position = Vector3(o.pos.x, o.species.visual_height + 0.5 + bob, o.pos.y)
				n += 1
			for id in plan.crosses:
				if id in plan.rams:
					continue
				var o2 := sim.fighter_by_id(id)
				if o2 == null:
					continue
				var l2 := _ram_label(n)
				l2.visible = true
				l2.text = "Protected"
				l2.modulate = Color(0.78, 0.82, 0.9)
				l2.position = Vector3(o2.pos.x, o2.species.visual_height + 0.5, o2.pos.y)
				n += 1
		for i in range(n, ram_labels.size()):
			ram_labels[i].visible = false
		# Stamina gauges show what the dash will spend.
		var fv := view.view_of(f.id)
		if fv:
			fv.set_cost_preview(0.0 if cancelled else plan.cost, affordable)

	func _ram_label(i: int) -> Label3D:
		while ram_labels.size() <= i:
			var l := _make_label(30)
			add_child(l)
			ram_labels.append(l)
		return ram_labels[i]

	func _update_ghost(view: BattleView, f: Fighter, plan: DashPlan, landed: bool, opacity: float) -> void:
		var fv := view.view_of(f.id)
		if fv == null or fv.sprite.sheet == null or not fv.sprite.sheet.valid:
			ghost.visible = false
			return
		if _ghost_fighter != f.id:
			_ghost_fighter = f.id
			ghost.set_sheet(fv.sprite.sheet)
			ghost.use_shader(GHOST_SHADER)
		ghost.visible = landed
		if not landed:
			return
		var dir_name: String = ["e", "s", "w", "n"][plan.dir_index]
		ghost.play("idle", dir_name)
		ghost.position = _marker_pos + Vector3(0, 0.0, 0.001)
		var c := team_color if affordable else NO_STAMINA_COLOR
		ghost.set_param("tint", c)
		ghost.set_param("opacity", (0.42 + 0.08 * sin(Time.get_ticks_msec() * 0.009)) * opacity)

	func _sounds(plan: DashPlan, aim: DashAim) -> void:
		var key := Vector3i(plan.dir_index, plan.cells, 1 if aim.cancelled else 0)
		if key == _last_key:
			return
		var first := _last_key.x < 0
		var was_cancelled := _last_key.z == 1
		_last_key = key
		if aim.cancelled and not was_cancelled and not first:
			Audio.sfx(&"ui_back", -12.0, 0.0, 60)
			return
		if aim.cancelled:
			return
		if plan.cells <= 0:
			Audio.sfx(&"dash_blocked", -12.0, 0.0, 80)
			return
		# A semitone per cell, so the length can be felt as well as seen.
		Audio.sfx(&"dash_aim_tick", -6.0 if not first else -8.0, 0.0, 0, pow(2.0, float(plan.cells - 1) / 12.0))

	## Tile states along the lane: the path, then (if the dash was cut short)
	## a wall marker and the cells that were out of reach.
	static func _lane_states(sim: BattleSim, f: Fighter, plan: DashPlan) -> Array[int]:
		var arena := sim.setup.arena
		var states: Array[int] = []
		var ram_cells := {}
		for id in plan.rams:
			var o := sim.fighter_by_id(id)
			if o:
				ram_cells[arena.cell_of(o.pos)] = true
		var n := plan.path.size()
		if plan.cells <= 0:
			n = 0
		for i in n:
			var c: Vector2i = plan.path[i]
			if i == n - 1:
				states.append(DashLane.Cell.LANDING)
			elif ram_cells.has(c):
				states.append(DashLane.Cell.RAM)
			else:
				states.append(DashLane.Cell.PATH)
		if n < plan.cells_requested:
			# Cut short: a wall marker on the first cell it can't enter, then
			# the cells that were out of reach (on the board).
			var step := Vector2i(int(plan.dir.x), int(plan.dir.y))
			for k in range(n + 1, plan.cells_requested + 1):
				var c2 := plan.home_cell + step * k
				if k == n + 1:
					states.append(DashLane.Cell.WALL)
				elif arena.has_cell(c2):
					states.append(DashLane.Cell.CUT)
				if not arena.has_cell(c2):
					break
		if states.is_empty():
			states.append(DashLane.Cell.WALL)
		return states
