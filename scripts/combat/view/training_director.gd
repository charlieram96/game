class_name TrainingDirector
extends Node
## Hesper's combat tutorial, run inside a training battle against a totem.
## Each step shows a tip and completes from real simulation events, so the
## tutorial teaches exactly the rules the game enforces.

const SM := FighterSM.State
## The "dash to move" marks: cell centres a few straight dashes apart in the
## training yard (N 3, E 4, S 5 from the start).
const MOVE_MARKS: Array[Vector2] = [Vector2(-4, -3), Vector2(0, -3), Vector2(0, 2)]

var scene: Node  # battle_scene.gd
var sim: BattleSim
var totem_ai: TrainingAI
var step := -1
var _markers: Array = []
var _counter := 0
var _used: Dictionary = {}
var _advance_at := -1
var _done := false

const STEPS := [
	{"id": "move", "short": "Drag along a row or column to dash · land on all 3 marks", "tip": "[b]Dash to move[/b] — creatures don't walk. [b]Drag[/b] from anywhere along a row or column and let go: the longer the drag, the more cells you cross. Land on all three glowing marks. [color=#6b5134](Keys: hold a direction, release to dash.)[/color]"},
	{"id": "dash", "short": "Dash 3 more times · longer dashes cost more stamina", "tip": "[b]Stamina[/b] — every dash costs stamina, more for longer ones: the lane shows the cost and the ring under you drains. Dash 3 more times. Drag back to where you started to cancel."},
	{"id": "basic", "short": "Dash next to the totem, then click or tap it 3 times", "tip": "[b]Strike[/b] — dash next to the totem, then [b]click[/b] (or tap) toward it three times to land a three-hit string."},
	{"id": "specials", "short": "Use all four specials: Q · E · R · F", "tip": "[b]Specials[/b] — use all four: [b]Q[/b] Ember Bolt, [b]E[/b] Cinder Arc, [b]R[/b] Flash Strike, [b]F[/b] Heat Ring. They aim at the pointer."},
	{"id": "focus", "short": "Hold Shift (or press and hold still) until the ring is full", "tip": "[b]Focus[/b] — stamina never refills on its own. Hold [b]Shift[/b] (or press and hold still on the arena) until the ring under you is full. You're open while you focus!"},
	{"id": "dash_through", "short": "Ram: dash straight through the totem", "tip": "[b]Ram[/b] — dash straight [b]through[/b] the totem: its tile turns gold and [b]RAM![/b] shows when you'll hit. A rammed foe is dazed, then protected for a moment."},
	{"id": "guard", "short": "Hold Space or Right Click to guard · block 2 acorns", "tip": "[b]Guard[/b] — the totem throws acorns now. Hold [b]Space[/b] or [b]Right Click[/b] to guard your front. Guard right before impact for a [b]Perfect Guard[/b]. Block 2 acorns."},
]


func begin(battle_scene: Node) -> void:
	scene = battle_scene
	sim = battle_scene.sim
	totem_ai = TrainingAI.new()
	battle_scene.transport.set_input_source(1, totem_ai)
	_next_step()


func _player() -> Fighter:
	return sim.active_fighter(0)


func _next_step() -> void:
	step += 1
	_counter = 0
	_used.clear()
	_clear_markers()
	if step >= STEPS.size():
		_finish()
		return
	var s: Dictionary = STEPS[step]
	scene.hud.show_tip("%s\n[color=#6b5134]Step %d of %d[/color]" % [s["tip"], step + 1, STEPS.size()], "[b]%d/%d[/b]  %s" % [step + 1, STEPS.size(), s["short"]])
	totem_ai.mode = TrainingAI.Mode.IDLE
	match s["id"]:
		"move":
			for p in MOVE_MARKS:
				_add_marker(p)
		"focus":
			sim.script_set_stamina(_player(), minf(_player().stamina, 12.0))
		"guard":
			totem_ai.mode = TrainingAI.Mode.SHOOT
			totem_ai.shoot_interval_ticks = 110


func _add_marker(p: Vector2) -> void:
	var d := GroundDecal.new()
	scene.view.add_child(d)
	d.position = Vector3(p.x, 0.03, p.y)
	d.set_circle(0.6, GroundDecal.Shape.RING, 0.6)
	d.set_colors(Color(1.0, 0.9, 0.45), Color(1.0, 0.85, 0.4), 0.9)
	d.set_progress(1.0)
	d.set_meta("pos", p)
	_markers.append(d)


func _clear_markers() -> void:
	for m in _markers:
		if is_instance_valid(m):
			m.queue_free()
	_markers.clear()


func on_tick(events: Array[BattleEvent]) -> void:
	if _done:
		return
	if _advance_at >= 0:
		if sim.tick >= _advance_at:
			_advance_at = -1
			_next_step()
		return
	var me := _player()
	var id: String = STEPS[step]["id"]
	match id:
		"move":
			for m in _markers.duplicate():
				var p: Vector2 = m.get_meta("pos")
				if me.state != SM.DASH_ACTIVE and me.state != SM.DASH_START and me.pos.distance_to(p) < 0.35:
					Audio.sfx(&"item_pickup")
					m.queue_free()
					_markers.erase(m)
			if _markers.is_empty():
				_complete()
		"dash":
			for e in events:
				if e.type == BattleEvent.DASH_START and e.fighter_id == me.id:
					_counter += 1
			if _counter >= 3:
				_complete()
		"basic":
			for e in events:
				if e.type == BattleEvent.HIT and e.fighter_id == me.id and String(e.data.get("ability", "")).begins_with("tail_swipe"):
					_counter += 1
			if _counter >= 3:
				_complete()
		"specials":
			for e in events:
				if e.type == BattleEvent.ABILITY_START and e.fighter_id == me.id and int(e.data.get("slot", -1)) >= 0:
					_used[e.data["ability"]] = true
			if _used.size() >= 4:
				_complete()
			elif not _used.is_empty():
				scene.hud.show_sub("%d / 4 specials used" % _used.size(), 0.1)
		"focus":
			if me.stamina >= me.max_stamina() * 0.95:
				_complete()
		"dash_through":
			for e in events:
				if e.type == BattleEvent.DASH_THROUGH and e.fighter_id == me.id and bool(e.data.get("stunned", false)):
					_complete()
		"guard":
			for e in events:
				if e.target_id == me.id or e.fighter_id == me.id:
					if e.type == BattleEvent.BLOCK and e.fighter_id == me.id:
						_counter += 1
					elif e.type == BattleEvent.PERFECT_GUARD and e.fighter_id == me.id:
						_counter += 2
			if _counter >= 2:
				_complete()
	# Keep the player topped up outside the stamina lesson so nothing stalls.
	if id != "focus" and id != "dash_through" and me.stamina < me.stats.dash.min_cost() and not FighterSM.is_focusing(me.state):
		sim.script_set_stamina(me, me.stamina + 0.6)


func _complete() -> void:
	Audio.sfx(&"quest_update")
	scene.hud.show_message("Nice!", UiTheme.GOLD, 0.5, 64)
	_advance_at = sim.tick + 50
	totem_ai.mode = TrainingAI.Mode.IDLE


func _finish() -> void:
	_done = true
	scene.hud.show_tip("[b]Training complete![/b] Hesper nods. \"You're ready for the Ringstones.\"")
	Audio.sfx(&"befriend_success")
	await get_tree().create_timer(2.4).timeout
	Game.return_from_battle({"winner": 0, "local_team": 0, "mode": BattleSetup.Mode.TRAINING, "story_battle_id": &"training", "record": _player().record})
