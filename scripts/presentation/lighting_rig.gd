class_name LightingRig
extends Node3D
## Sun, sky fill, ambient, fog, glow and tonemapping presets for the HD-2D
## look. Presets: morning, day, golden, dusk, night; arena_golden and
## arena_day are the battle-arena variants.
##
## The arena presets light the board like a miniature on a workbench: a low
## warm sun from the left (and a little from the front, so upright sprites
## face the light) throws long soft shadows across the board, a cool sky fill
## from the other side keeps the shadowed sides readable, and the shadow map
## is fitted to the fixed battle camera (one orthographic map, so softness
## never changes across the board). Glow picks up the flames and emissive
## bits; fog adds depth to what lies beyond the stands.

var sun: DirectionalLight3D
## A second, shadowless directional light from the sky side (arena presets).
var fill: DirectionalLight3D
var world_env: WorldEnvironment
var env: Environment
var preset_name: StringName = &""

const PRESETS := {
	&"morning": {"sun_color": Color(1.0, 0.86, 0.7), "energy": 1.15, "pitch": -28.0, "yaw": -35.0, "ambient": Color(0.62, 0.68, 0.8), "ambient_energy": 0.62, "fog": Color(0.86, 0.85, 0.82), "fog_density": 0.005, "bg": Color(0.55, 0.66, 0.74), "glow": 0.55, "exposure": 1.0},
	&"day": {"sun_color": Color(1.0, 0.95, 0.85), "energy": 1.25, "pitch": -52.0, "yaw": -30.0, "ambient": Color(0.6, 0.7, 0.85), "ambient_energy": 0.6, "fog": Color(0.75, 0.83, 0.9), "fog_density": 0.004, "bg": Color(0.5, 0.65, 0.8), "glow": 0.45, "exposure": 1.0},
	&"golden": {"sun_color": Color(1.0, 0.78, 0.52), "energy": 1.3, "pitch": -34.0, "yaw": -40.0, "ambient": Color(0.5, 0.56, 0.78), "ambient_energy": 0.52, "fog": Color(0.95, 0.78, 0.6), "fog_density": 0.004, "bg": Color(0.86, 0.66, 0.5), "glow": 0.7, "exposure": 1.0},
	&"dusk": {"sun_color": Color(1.0, 0.55, 0.45), "energy": 0.85, "pitch": -14.0, "yaw": -60.0, "ambient": Color(0.48, 0.42, 0.66), "ambient_energy": 0.62, "fog": Color(0.55, 0.38, 0.5), "fog_density": 0.014, "bg": Color(0.35, 0.25, 0.4), "glow": 0.85, "exposure": 1.05},
	&"night": {"sun_color": Color(0.55, 0.65, 1.0), "energy": 0.5, "pitch": -48.0, "yaw": 25.0, "ambient": Color(0.25, 0.32, 0.55), "ambient_energy": 0.7, "fog": Color(0.08, 0.1, 0.2), "fog_density": 0.02, "bg": Color(0.04, 0.05, 0.1), "glow": 1.0, "exposure": 1.1},
	# Battle arenas: sun 31 / 38 deg up, from the west-south-west (yaw -64 / -62);
	# their fog is depth fog, so "fog_density" is its strength at full depth.
	&"arena_golden": {"sun_color": Color(1.0, 0.77, 0.54), "energy": 1.4, "pitch": -31.0, "yaw": -64.0, "ambient": Color(0.42, 0.46, 0.7), "ambient_energy": 0.37, "fog": Color(0.92, 0.74, 0.58), "fog_density": 0.5, "bg": Color(0.42, 0.34, 0.36), "glow": 0.8, "exposure": 1.0, "shadow_distance": 62.0, "fill_color": Color(0.55, 0.66, 1.0), "fill_energy": 0.28, "arena": true},
	&"arena_day": {"sun_color": Color(1.0, 0.93, 0.8), "energy": 1.5, "pitch": -38.0, "yaw": -62.0, "ambient": Color(0.56, 0.64, 0.82), "ambient_energy": 0.46, "fog": Color(0.78, 0.84, 0.9), "fog_density": 0.45, "bg": Color(0.5, 0.62, 0.76), "glow": 0.6, "exposure": 1.0, "shadow_distance": 62.0, "fill_color": Color(0.6, 0.72, 1.0), "fill_energy": 0.3, "arena": true},
}


func _ready() -> void:
	if sun == null:
		_build()


func _is_arena() -> bool:
	return bool(PRESETS.get(preset_name, {}).get("arena", false))


func _apply_settings() -> void:
	if _is_arena():
		# The battle camera never moves: one orthographic map over the board
		# and stands is sharper than splits and has no seam across the board.
		sun.directional_shadow_mode = DirectionalLight3D.SHADOW_ORTHOGONAL
		sun.shadow_blur = 1.0 if Settings.graphics_low else 1.9
		env.set("glow_levels/1", 0.0)
		env.set("glow_levels/2", 0.6 if Settings.graphics_low else 0.9)
		env.set("glow_levels/3", 1.0)
		env.set("glow_levels/4", 0.6 if Settings.graphics_low else 0.85)
		env.set("glow_levels/5", 0.0 if Settings.graphics_low else 0.45)
	else:
		sun.directional_shadow_mode = DirectionalLight3D.SHADOW_ORTHOGONAL if Settings.graphics_low else DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS
		sun.shadow_blur = 1.2


func _build() -> void:
	sun = DirectionalLight3D.new()
	sun.name = "Sun"
	sun.shadow_enabled = true
	sun.shadow_bias = 0.04
	sun.shadow_normal_bias = 1.2
	sun.shadow_blur = 1.2
	sun.directional_shadow_max_distance = 60.0
	add_child(sun)
	fill = DirectionalLight3D.new()
	fill.name = "SkyFill"
	fill.shadow_enabled = false
	fill.light_specular = 0.0
	fill.light_energy = 0.0
	fill.visible = false
	add_child(fill)
	env = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_white = 6.0
	env.glow_enabled = true
	env.glow_intensity = 0.6
	env.glow_strength = 1.0
	env.glow_bloom = 0.08
	env.glow_hdr_threshold = 0.9
	env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SOFTLIGHT
	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_EXPONENTIAL
	env.fog_sky_affect = 0.0
	env.adjustment_enabled = true
	env.adjustment_saturation = 1.05
	env.adjustment_contrast = 1.1
	world_env = WorldEnvironment.new()
	world_env.environment = env
	add_child(world_env)
	_apply_settings()
	Events.settings_changed.connect(_apply_settings)


func apply(p_name: StringName, duration: float = 0.0) -> void:
	if sun == null:
		_build()
	preset_name = p_name
	var p: Dictionary = PRESETS.get(p_name, PRESETS[&"day"])
	var target_rot := Vector3(deg_to_rad(p["pitch"]), deg_to_rad(p["yaw"]), 0.0)
	sun.directional_shadow_max_distance = float(p.get("shadow_distance", 60.0))
	var arena := bool(p.get("arena", false))
	_apply_arena_env(arena, p)
	_apply_settings()
	if duration <= 0.0:
		sun.rotation = target_rot
		sun.light_color = p["sun_color"]
		sun.light_energy = p["energy"]
		env.ambient_light_color = p["ambient"]
		env.ambient_light_energy = p["ambient_energy"]
		env.fog_light_color = p["fog"]
		env.fog_density = p["fog_density"]
		env.background_color = p["bg"]
		env.glow_intensity = p["glow"]
		env.tonemap_exposure = p["exposure"]
		return
	var tw := create_tween().set_parallel(true).set_trans(Tween.TRANS_SINE)
	tw.tween_property(sun, "rotation", target_rot, duration)
	tw.tween_property(sun, "light_color", p["sun_color"], duration)
	tw.tween_property(sun, "light_energy", p["energy"], duration)
	tw.tween_property(env, "ambient_light_color", p["ambient"], duration)
	tw.tween_property(env, "ambient_light_energy", p["ambient_energy"], duration)
	tw.tween_property(env, "fog_light_color", p["fog"], duration)
	tw.tween_property(env, "fog_density", p["fog_density"], duration)
	tw.tween_property(env, "background_color", p["bg"], duration)
	tw.tween_property(env, "glow_intensity", p["glow"], duration)
	tw.tween_property(env, "tonemap_exposure", p["exposure"], duration)


## The battle look on top of a preset: sky fill, shadow tuning, filmic curve,
## brighter glow on the flames, fog that only thickens past the stands.
func _apply_arena_env(arena: bool, p: Dictionary) -> void:
	fill.visible = arena
	if not arena:
		return
	var yaw := deg_to_rad(float(p["yaw"])) + PI
	fill.rotation = Vector3(deg_to_rad(-52.0), yaw, 0.0)
	fill.light_color = p.get("fill_color", Color(0.6, 0.7, 1.0))
	fill.light_energy = float(p.get("fill_energy", 0.3))
	sun.shadow_bias = 0.025
	sun.shadow_normal_bias = 1.6
	sun.light_angular_distance = 0.0
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_white = 5.0
	env.glow_strength = 1.05
	env.glow_bloom = 0.04
	env.glow_hdr_threshold = 1.05
	env.glow_hdr_scale = 2.0
	env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SCREEN
	env.adjustment_saturation = 1.04
	env.adjustment_contrast = 1.06
	# depth fog that starts past the board's far edge at every aspect ratio:
	# only the far stands, trees and backdrop take on the haze
	env.fog_mode = Environment.FOG_MODE_DEPTH
	env.fog_depth_begin = 36.0
	env.fog_depth_end = 82.0
	env.fog_depth_curve = 1.0
	env.fog_light_energy = 1.0
