class_name BattleHUD
extends CanvasLayer
## Battle HUD: creature panels (HP with delayed "ghost" damage, stamina
## segmented by dash cost, status icons), match timer, ability bar with
## cooldown sweeps and key hints, big centre messages, tutorial tips.
## All layout is anchor-based so it adapts from 16:9 to tall-phone aspect
## ratios; the root Control can be sized directly for tests.

signal pause_requested

const SM := FighterSM.State

var sim: BattleSim
var local_team := 0
var root: Control
var panels: Array = []  # [FighterPanel, FighterPanel]
var timer_label: Label
var mode_label: Label
var center_label: Label
var sub_label: Label
var ability_bar: HBoxContainer
var slots: Array = []
var tip_panel: PanelContainer
var tip_label: RichTextLabel
var pause_button: Button
var touch_mode := false
## Seconds the full tip stays up before it shrinks to its one-line summary.
const TIP_FULL_SECONDS := 9.0
var _tip_summary := ""
var _tip_full_left := 0.0
var _msg_tween: Tween


func _init() -> void:
	layer = 10


func build(p_sim: BattleSim, p_local_team: int, setup: BattleSetup, host: Control = null) -> void:
	sim = p_sim
	local_team = p_local_team
	root = Control.new()
	root.name = "HUDRoot"
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.theme = UiTheme.get_theme()
	if host:
		host.add_child(root)
	else:
		add_child(root)
	for team in 2:
		var p := FighterPanel.new()
		p.mirrored = team == 1
		p.team_color = BattleView.TEAM_COLORS[team]
		root.add_child(p)
		var psize := p.custom_minimum_size
		if team == 0:
			UiTheme.place(p, Vector2(0, 0), Vector2(14, 12), psize)
		else:
			UiTheme.place(p, Vector2(1, 0), Vector2(-14 - psize.x, 12), psize)
		panels.append(p)
	# Timer plaque
	var plaque := PanelContainer.new()
	plaque.add_theme_stylebox_override("panel", UiTheme.panel_box("panel_wood"))
	plaque.custom_minimum_size = Vector2(108, 64)
	UiTheme.place(plaque, Vector2(0.5, 0), Vector2(-54, 8), Vector2(108, 64))
	plaque.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(plaque)
	var vb := VBoxContainer.new()
	vb.alignment = BoxContainer.ALIGNMENT_CENTER
	vb.add_theme_constant_override("separation", -4)
	plaque.add_child(vb)
	timer_label = UiTheme.label("--", 30, UiTheme.PARCHMENT, true)
	timer_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vb.add_child(timer_label)
	mode_label = UiTheme.label(setup.ruleset.display_name, 13, Color(0.85, 0.8, 0.65))
	mode_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vb.add_child(mode_label)
	# Centre messages
	center_label = UiTheme.label("", 76, UiTheme.GOLD, true, 14)
	center_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	center_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	UiTheme.place(center_label, Vector2(0.5, 0.5), Vector2(-450, -170), Vector2(900, 130))
	center_label.pivot_offset = Vector2(450, 65)
	root.add_child(center_label)
	sub_label = UiTheme.label("", 26, UiTheme.PARCHMENT, true, 8)
	sub_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	UiTheme.place(sub_label, Vector2(0.5, 0.5), Vector2(-450, -40), Vector2(900, 40))
	root.add_child(sub_label)
	# Ability bar
	ability_bar = HBoxContainer.new()
	ability_bar.add_theme_constant_override("separation", 8)
	ability_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(ability_bar)
	_build_ability_bar()
	# Tutorial tip panel
	tip_panel = PanelContainer.new()
	tip_panel.add_theme_stylebox_override("panel", UiTheme.parchment_box())
	tip_panel.custom_minimum_size = Vector2(600, 0)
	UiTheme.place(tip_panel, Vector2(0.5, 0), Vector2(-300, 84), Vector2(600, 0))
	tip_panel.visible = false
	tip_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(tip_panel)
	tip_label = RichTextLabel.new()
	tip_label.bbcode_enabled = true
	tip_label.fit_content = true
	tip_label.scroll_active = false
	tip_label.add_theme_font_override("normal_font", UiTheme.FONT_REGULAR)
	tip_label.add_theme_font_override("bold_font", UiTheme.FONT_BOLD)
	tip_label.add_theme_font_size_override("normal_font_size", 20)
	tip_label.add_theme_font_size_override("bold_font_size", 20)
	tip_label.add_theme_color_override("default_color", Color(0.18, 0.12, 0.08))
	tip_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tip_panel.add_child(tip_label)
	# Pause button (always reachable on touch screens)
	pause_button = Button.new()
	pause_button.text = "II"
	pause_button.custom_minimum_size = Vector2(56, 48)
	UiTheme.place(pause_button, Vector2(0.5, 0), Vector2(64, 16), Vector2(56, 48))
	pause_button.focus_mode = Control.FOCUS_NONE
	pause_button.pressed.connect(func() -> void: pause_requested.emit())
	root.add_child(pause_button)
	set_touch_mode(false)


func _build_ability_bar() -> void:
	for c in ability_bar.get_children():
		c.queue_free()
	slots.clear()
	var f := sim.active_fighter(local_team)
	if f == null:
		return
	var defs := [
		[-1, f.stats.basic, "Click"],
		[0, f.stats.abilities[0], "Q"],
		[1, f.stats.abilities[1], "E"],
		[2, f.stats.abilities[2], "R"],
		[3, f.stats.abilities[3], "F"],
	]
	for d in defs:
		var s := AbilitySlot.new()
		s.slot = d[0]
		s.ability = d[1]
		s.key_hint = d[2]
		ability_bar.add_child(s)
		slots.append(s)
	for extra in [["dash", "Drag", "Dash"], ["focus", "Shift", "Focus"], ["guard", "Space", "Guard"]]:
		var u := AbilitySlot.new()
		u.utility = extra[0]
		u.key_hint = extra[1]
		u.small = true
		ability_bar.add_child(u)
		slots.append(u)
	var bar_size := Vector2(5 * 68 + 3 * 54 + 7 * 8, 68)
	UiTheme.place(ability_bar, Vector2(0.5, 1.0), Vector2(-bar_size.x * 0.5, -bar_size.y - 14), bar_size)
	ability_bar.alignment = BoxContainer.ALIGNMENT_CENTER


func rebind(p_sim: BattleSim) -> void:
	sim = p_sim
	_build_ability_bar()


func set_touch_mode(on: bool) -> void:
	touch_mode = on
	ability_bar.visible = not on
	pause_button.visible = true


# --- Per frame ----------------------------------------------------------------------

func refresh(delta: float) -> void:
	if sim == null:
		return
	for team in 2:
		var f := sim.active_fighter(team)
		if f:
			(panels[team] as FighterPanel).bind(f, sim)
			(panels[team] as FighterPanel).tick(delta)
	var secs := sim.seconds_left()
	if secs < 0.0:
		timer_label.text = "∞"
	else:
		var s := int(ceil(secs))
		timer_label.text = "%d:%02d" % [s / 60, s % 60]
		timer_label.add_theme_color_override("font_color", UiTheme.DANGER if s <= 10 else UiTheme.PARCHMENT)
	var me := sim.active_fighter(local_team)
	for s in slots:
		(s as AbilitySlot).update_from(me)
	if _tip_full_left > 0.0:
		_tip_full_left -= delta
		if _tip_full_left <= 0.0:
			collapse_tip()


## Show on `team`'s stamina bar what the dash being aimed would spend
## (`preview` = (cost, affordable); cost 0 = nothing aimed).
func set_dash_cost_preview(team: int, preview: Vector2) -> void:
	if team >= 0 and team < panels.size():
		var p := panels[team] as FighterPanel
		p.cost_preview = preview.x
		p.cost_ok = preview.y > 0.5


func show_message(text: String, color: Color = UiTheme.GOLD, duration: float = 0.9, size: int = 76) -> void:
	center_label.text = text
	center_label.add_theme_color_override("font_color", color)
	center_label.add_theme_font_size_override("font_size", size)
	center_label.modulate.a = 1.0
	center_label.scale = Vector2.ONE * 1.6
	if _msg_tween:
		_msg_tween.kill()
	_msg_tween = create_tween()
	_msg_tween.tween_property(center_label, "scale", Vector2.ONE, 0.18).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	if duration > 0.0:
		_msg_tween.tween_interval(duration)
		_msg_tween.tween_property(center_label, "modulate:a", 0.0, 0.3)


func show_sub(text: String, duration: float = 2.0) -> void:
	sub_label.text = text
	sub_label.modulate.a = 1.0
	var tw := create_tween()
	tw.tween_interval(duration)
	tw.tween_property(sub_label, "modulate:a", 0.0, 0.4)


## A tutorial tip. With a `summary`, the full text shows for a few seconds
## and then shrinks to that one line at the top edge, so it stops covering
## the board.
func show_tip(bbcode: String, summary: String = "") -> void:
	tip_panel.visible = bbcode != ""
	tip_label.text = bbcode
	_tip_summary = summary
	_tip_full_left = TIP_FULL_SECONDS if summary != "" else 0.0
	_layout_tip(false)


## Shrink the current tip to its summary now (e.g. once the player acts).
func collapse_tip() -> void:
	_tip_full_left = 0.0
	if _tip_summary == "" or not tip_panel.visible:
		return
	tip_label.text = _tip_summary
	_tip_summary = ""
	_layout_tip(true)


func _layout_tip(compact: bool) -> void:
	var w := 560.0 if compact else 600.0
	var font := 16 if compact else 20
	tip_label.add_theme_font_size_override("normal_font_size", font)
	tip_label.add_theme_font_size_override("bold_font_size", font)
	tip_panel.custom_minimum_size = Vector2(w, 0)
	tip_panel.size = Vector2(w, 0)
	UiTheme.place(tip_panel, Vector2(0.5, 0), Vector2(-w * 0.5, 82 if compact else 84), Vector2(w, 0))
	tip_panel.modulate.a = 0.88 if compact else 1.0


func on_feedback(kind: StringName, data: Dictionary) -> void:
	match kind:
		&"no_stamina":
			(panels[local_team] as FighterPanel).pulse_stamina()
		&"denied":
			for s in slots:
				var slot := s as AbilitySlot
				if slot.ability and slot.ability.id == data.get("ability", &""):
					slot.shake()
		&"hit":
			pass


## Every interactive or informative rect, for layout tests.
func layout_rects() -> Dictionary:
	var out := {}
	out["panel_left"] = (panels[0] as Control).get_global_rect()
	out["panel_right"] = (panels[1] as Control).get_global_rect()
	out["pause"] = pause_button.get_global_rect()
	if ability_bar.visible:
		out["ability_bar"] = ability_bar.get_global_rect()
	return out


# === Inner widgets ==================================================================

class FighterPanel:
	extends Control
	var mirrored := false
	var team_color := Color.WHITE
	var fighter: Fighter
	var sim_ref: BattleSim
	var ghost_hp := 1.0
	var shown_hp := 1.0
	var cost_preview := 0.0
	var cost_ok := true
	var _stamina_pulse := 0.0
	var _name_label: Label
	var _level_label: Label
	var _status_box: HBoxContainer
	var _last_statuses := ""

	func _init() -> void:
		custom_minimum_size = Vector2(360, 92)
		size = custom_minimum_size
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		_name_label = UiTheme.label("", 22, UiTheme.PARCHMENT, true)
		_name_label.position = Vector2(56, 0)
		add_child(_name_label)
		_level_label = UiTheme.label("", 16, Color(0.9, 0.85, 0.7))
		add_child(_level_label)
		_status_box = HBoxContainer.new()
		_status_box.add_theme_constant_override("separation", 3)
		add_child(_status_box)

	func bind(f: Fighter, s: BattleSim) -> void:
		if fighter != f:
			fighter = f
			ghost_hp = f.hp_ratio()
			shown_hp = f.hp_ratio()
		sim_ref = s

	func pulse_stamina() -> void:
		_stamina_pulse = 1.0

	func tick(delta: float) -> void:
		if fighter == null:
			return
		var target := fighter.hp_ratio()
		shown_hp = move_toward(shown_hp, target, delta * 2.5)
		if target < ghost_hp:
			ghost_hp = move_toward(ghost_hp, target, delta * 0.45)
		else:
			ghost_hp = target
		_stamina_pulse = maxf(0.0, _stamina_pulse - delta * 2.5)
		_name_label.text = fighter.label
		_level_label.text = "Lv.%d" % fighter.stats.level_used
		var name_w := _name_label.get_combined_minimum_size().x
		if mirrored:
			_name_label.position = Vector2(size.x - 56 - name_w, 0)
			_level_label.position = Vector2(size.x - 56 - name_w - 58, 5)
		else:
			_name_label.position = Vector2(56, 0)
			_level_label.position = Vector2(64 + name_w, 5)
		_update_statuses()
		queue_redraw()

	func _update_statuses() -> void:
		var key := ""
		for s in fighter.statuses:
			key += String(s.def.id) + ","
		if fighter.dash_through_immunity > 0:
			key += "protect,"
		if fighter.steadfast > 0:
			key += "steadfast,"
		if key == _last_statuses:
			return
		_last_statuses = key
		for c in _status_box.get_children():
			c.queue_free()
		for id in key.split(",", false):
			var icon_name: String = {"burn": "status_burn", "slow": "status_slow", "stoneguard": "status_armor", "protect": "status_immune", "steadfast": "status_immune"}.get(id, "")
			var tex := UiTheme.icon(icon_name)
			if tex:
				var tr := TextureRect.new()
				tr.texture = tex
				tr.custom_minimum_size = Vector2(24, 24)
				tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
				tr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
				_status_box.add_child(tr)
			else:
				var l := UiTheme.label(id.substr(0, 4).to_upper(), 12, Color(1, 0.9, 0.6))
				_status_box.add_child(l)
		_status_box.position = Vector2(size.x - 56 - _status_box.get_combined_minimum_size().x if not mirrored else 56, 72) if not mirrored else Vector2(56, 72)

	func _draw() -> void:
		if fighter == null:
			return
		var w := size.x
		# Emblem
		var emblem_x := w - 48.0 if mirrored else 0.0
		var ecol := UiTheme.element_color(fighter.species.element)
		draw_rect(Rect2(emblem_x, 2, 46, 46), UiTheme.INK)
		draw_rect(Rect2(emblem_x + 3, 5, 40, 40), team_color.darkened(0.55))
		draw_rect(Rect2(emblem_x + 6, 8, 34, 34), ecol.darkened(0.2))
		var etex := UiTheme.icon("element_" + String(fighter.species.element))
		if etex:
			draw_texture_rect(etex, Rect2(emblem_x + 7, 9, 32, 32), false)
		# HP bar
		var bar_x := 56.0 if not mirrored else 8.0
		var bar_w := w - 64.0
		_bar(Rect2(bar_x, 30, bar_w, 18), shown_hp, ghost_hp, Color(0.38, 0.86, 0.42) if shown_hp > 0.35 else (Color(0.98, 0.78, 0.25) if shown_hp > 0.15 else Color(0.95, 0.3, 0.28)), mirrored)
		var hp_text := "%d / %d" % [int(ceil(fighter.hp)), int(fighter.max_hp())]
		var font := UiTheme.FONT_BOLD
		var tw := font.get_string_size(hp_text, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
		var tx := bar_x + bar_w - tw - 6 if not mirrored else bar_x + 6
		draw_string_outline(font, Vector2(tx, 44), hp_text, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, 4, UiTheme.INK)
		draw_string(font, Vector2(tx, 44), hp_text, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, UiTheme.PARCHMENT)
		# Stamina bar, segmented by dash cost
		var st_rect := Rect2(bar_x, 52, bar_w * 0.82, 12)
		if mirrored:
			st_rect.position.x = bar_x + bar_w * 0.18
		var ratio := fighter.stamina_ratio()
		var cost := fighter.stats.dash.min_cost()
		var can_dash := fighter.stamina >= cost
		var scol := Color(0.45, 0.85, 1.0) if can_dash else Color(1.0, 0.5, 0.4)
		if fighter.state == SM.FOCUSING:
			scol = scol.lerp(Color(0.9, 1.0, 1.0), 0.5 + 0.5 * sin(Time.get_ticks_msec() * 0.015))
		if _stamina_pulse > 0.0:
			scol = scol.lerp(Color(1, 0.2, 0.2), _stamina_pulse)
		_bar(st_rect, ratio, ratio, scol, mirrored)
		if cost_preview > 0.0:
			# The aimed dash: the stretch it would spend blinks; if stamina is
			# short, the missing stretch blinks red.
			var maxs := maxf(1.0, fighter.max_stamina())
			var blink := 0.5 + 0.5 * sin(Time.get_ticks_msec() * 0.016)
			if cost_ok:
				_span(st_rect, maxf(0.0, fighter.stamina - cost_preview) / maxs, fighter.stamina / maxs, Color(1.0, 0.97, 0.86, 0.45 + 0.4 * blink), mirrored)
			else:
				_span(st_rect, fighter.stamina / maxs, minf(1.0, cost_preview / maxs), Color(1.0, 0.3, 0.25, 0.35 + 0.4 * blink), mirrored)
		if cost > 0.0 and cost < 999.0:
			var segs := int(floor(fighter.max_stamina() / cost))
			for i in range(1, segs + 1):
				var fx := st_rect.position.x + st_rect.size.x * (cost * i / fighter.max_stamina())
				if mirrored:
					fx = st_rect.end.x - st_rect.size.x * (cost * i / fighter.max_stamina())
				draw_rect(Rect2(fx - 1, st_rect.position.y, 2, st_rect.size.y), UiTheme.INK)

	func _span(r: Rect2, from: float, to: float, col: Color, from_right: bool) -> void:
		var a := clampf(from, 0.0, 1.0) * r.size.x
		var b := clampf(to, 0.0, 1.0) * r.size.x
		if b <= a:
			return
		var x := r.position.x + a if not from_right else r.end.x - b
		draw_rect(Rect2(x, r.position.y, b - a, r.size.y), col)

	func _bar(r: Rect2, fill: float, ghost: float, col: Color, from_right: bool) -> void:
		draw_rect(r.grow(3), UiTheme.INK)
		draw_rect(r.grow(1), Color(0.55, 0.45, 0.3))
		draw_rect(r, Color(0.12, 0.1, 0.14))
		var gw := r.size.x * clampf(ghost, 0.0, 1.0)
		var fw := r.size.x * clampf(fill, 0.0, 1.0)
		var gx := r.position.x if not from_right else r.end.x - gw
		var fx := r.position.x if not from_right else r.end.x - fw
		draw_rect(Rect2(gx, r.position.y, gw, r.size.y), Color(1.0, 0.92, 0.75))
		draw_rect(Rect2(fx, r.position.y, fw, r.size.y), col)
		draw_rect(Rect2(fx, r.position.y, fw, 3), col.lightened(0.35))
		draw_rect(Rect2(fx, r.end.y - 3, fw, 3), col.darkened(0.3))


class AbilitySlot:
	extends Control
	var slot := -2
	var ability: AbilityDefinition
	var utility := ""
	var key_hint := ""
	var small := false
	var _cd_ratio := 0.0
	var _cd_secs := 0.0
	var _ready_flash := 0.0
	var _no_cost := false
	var _shake := 0.0
	var _active := false
	var _icon: Texture2D

	func _ready() -> void:
		custom_minimum_size = Vector2(54, 54) if small else Vector2(68, 68)
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		if ability:
			_icon = UiTheme.icon("ability_" + String(ability.id).trim_suffix("_2").trim_suffix("_3"))
			if _icon == null and ability.icon_path != "" and ResourceLoader.exists(ability.icon_path):
				_icon = load(ability.icon_path)
		elif utility != "":
			_icon = UiTheme.icon("ability_" + utility)

	func shake() -> void:
		_shake = 1.0

	func update_from(f: Fighter) -> void:
		if f == null:
			return
		var was := _cd_ratio
		if ability:
			var left := f.cooldown_of(ability)
			_cd_ratio = float(left) / maxf(1.0, float(ability.cooldown_ticks)) if ability.cooldown_ticks > 0 else 0.0
			_cd_secs = float(left) / 60.0
			_no_cost = f.stamina < ability.stamina_cost
			_active = f.current_ability != null and (f.current_ability == ability or (slot == -1 and f.current_slot == -1))
		else:
			_cd_ratio = 0.0
			match utility:
				"dash":
					_no_cost = f.stamina < f.stats.dash.min_cost()
					_active = FighterSM.is_dashing(f.state)
				"focus":
					_no_cost = false
					_active = FighterSM.is_focusing(f.state)
				"guard":
					_no_cost = f.stamina <= 0.0
					_active = f.state == FighterSM.State.GUARDING
		if was > 0.0 and _cd_ratio <= 0.0:
			_ready_flash = 1.0
		_ready_flash = maxf(0.0, _ready_flash - get_process_delta_time() * 3.0)
		_shake = maxf(0.0, _shake - get_process_delta_time() * 4.0)
		queue_redraw()

	func _draw() -> void:
		var s := size
		var off := Vector2(sin(Time.get_ticks_msec() * 0.08) * 4.0 * _shake, 0)
		var r := Rect2(off, s)
		var c := s * 0.5 + off
		var rad := s.x * 0.5 - 2.0
		draw_circle(c, rad + 2.0, UiTheme.INK)
		var ring_col := Color(0.62, 0.48, 0.26)
		if _active:
			ring_col = UiTheme.GOLD
		draw_circle(c, rad, ring_col)
		var bg := Color(0.13, 0.17, 0.19)
		if ability:
			bg = UiTheme.element_color(ability.element).darkened(0.62)
		draw_circle(c, rad - 3.0, bg)
		if _icon:
			var isz := s.x * 0.62
			draw_texture_rect(_icon, Rect2(c - Vector2(isz, isz) * 0.5, Vector2(isz, isz)), false, Color(0.45, 0.45, 0.5) if _no_cost else Color.WHITE)
		else:
			var txt := (ability.display_name if ability else utility.capitalize()).substr(0, 5)
			var fz := 12 if small else 14
			var tw := UiTheme.FONT_BOLD.get_string_size(txt, HORIZONTAL_ALIGNMENT_LEFT, -1, fz).x
			draw_string(UiTheme.FONT_BOLD, c + Vector2(-tw * 0.5, 5), txt, HORIZONTAL_ALIGNMENT_LEFT, -1, fz, UiTheme.PARCHMENT)
		if _cd_ratio > 0.0:
			var pts := PackedVector2Array([c])
			var steps := 32
			for i in steps + 1:
				var a := -PI * 0.5 + TAU * _cd_ratio * float(i) / steps
				pts.append(c + Vector2(cos(a), sin(a)) * (rad - 3.0))
			draw_colored_polygon(pts, Color(0.02, 0.02, 0.05, 0.72))
			var secs := "%.1f" % _cd_secs if _cd_secs < 1.0 else str(int(ceil(_cd_secs)))
			var fz2 := 18 if not small else 14
			var tw2 := UiTheme.FONT_BOLD.get_string_size(secs, HORIZONTAL_ALIGNMENT_LEFT, -1, fz2).x
			draw_string_outline(UiTheme.FONT_BOLD, c + Vector2(-tw2 * 0.5, 7), secs, HORIZONTAL_ALIGNMENT_LEFT, -1, fz2, 4, UiTheme.INK)
			draw_string(UiTheme.FONT_BOLD, c + Vector2(-tw2 * 0.5, 7), secs, HORIZONTAL_ALIGNMENT_LEFT, -1, fz2, UiTheme.PARCHMENT)
		if _ready_flash > 0.0:
			draw_arc(c, rad + 1.0, 0, TAU, 32, Color(1, 1, 0.8, _ready_flash), 3.0)
		if _no_cost and ability and ability.stamina_cost > 0.0:
			draw_arc(c, rad - 1.0, 0, TAU, 32, Color(1, 0.35, 0.3, 0.9), 2.0)
		# Key hint badge
		var kf := 12
		var kw := UiTheme.FONT_BOLD.get_string_size(key_hint, HORIZONTAL_ALIGNMENT_LEFT, -1, kf).x + 8
		var kr := Rect2(Vector2(s.x - kw + 4, s.y - 16) + off, Vector2(kw, 17))
		draw_rect(kr, UiTheme.INK)
		draw_rect(kr.grow(-1), Color(0.25, 0.2, 0.15))
		draw_string(UiTheme.FONT_BOLD, kr.position + Vector2(4, 13), key_hint, HORIZONTAL_ALIGNMENT_LEFT, -1, kf, UiTheme.GOLD)
		if ability and ability.stamina_cost > 0.0 and not small:
			var cost := str(int(ability.stamina_cost))
			draw_string_outline(UiTheme.FONT_BOLD, Vector2(2, 12) + off, cost, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, 4, UiTheme.INK)
			draw_string(UiTheme.FONT_BOLD, Vector2(2, 12) + off, cost, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.55, 0.88, 1.0))
