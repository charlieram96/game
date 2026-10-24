class_name LightingRig
extends Node3D
## Sun, ambient, fog, glow and tonemapping presets for the HD-2D look.
## Presets: morning, day, golden, dusk, night.

var sun: DirectionalLight3D
var world_env: WorldEnvironment
var env: Environment
var preset_name: StringName = &""

const PRESETS := {
	&"morning": {"sun_color": Color(1.0, 0.86, 0.7), "energy": 1.15, "pitch": -28.0, "yaw": -35.0, "ambient": Color(0.62, 0.68, 0.8), "ambient_energy": 0.62, "fog": Color(0.86, 0.85, 0.82), "fog_density": 0.005, "bg": Color(0.55, 0.66, 0.74), "glow": 0.55, "exposure": 1.0},
	&"day": {"sun_color": Color(1.0, 0.95, 0.85), "energy": 1.25, "pitch": -52.0, "yaw": -30.0, "ambient": Color(0.6, 0.7, 0.85), "ambient_energy": 0.6, "fog": Color(0.75, 0.83, 0.9), "fog_density": 0.004, "bg": Color(0.5, 0.65, 0.8), "glow": 0.45, "exposure": 1.0},
	&"golden": {"sun_color": Color(1.0, 0.78, 0.52), "energy": 1.3, "pitch": -34.0, "yaw": -40.0, "ambient": Color(0.5, 0.56, 0.78), "ambient_energy": 0.52, "fog": Color(0.95, 0.78, 0.6), "fog_density": 0.004, "bg": Color(0.86, 0.66, 0.5), "glow": 0.7, "exposure": 1.0},
	&"dusk": {"sun_color": Color(1.0, 0.55, 0.45), "energy": 0.85, "pitch": -14.0, "yaw": -60.0, "ambient": Color(0.48, 0.42, 0.66), "ambient_energy": 0.62, "fog": Color(0.55, 0.38, 0.5), "fog_density": 0.014, "bg": Color(0.35, 0.25, 0.4), "glow": 0.85, "exposure": 1.05},
	&"night": {"sun_color": Color(0.55, 0.65, 1.0), "energy": 0.5, "pitch": -48.0, "yaw": 25.0, "ambient": Color(0.25, 0.32, 0.55), "ambient_energy": 0.7, "fog": Color(0.08, 0.1, 0.2), "fog_density": 0.02, "bg": Color(0.04, 0.05, 0.1), "glow": 1.0, "exposure": 1.1},
}


func _ready() -> void:
	if sun == null:
		_build()


func _apply_settings() -> void:
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_ORTHOGONAL if Settings.graphics_low else DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS


func _build() -> void:
	sun = DirectionalLight3D.new()
	sun.name = "Sun"
	sun.shadow_enabled = true
	sun.shadow_bias = 0.04
	sun.shadow_normal_bias = 1.2
	sun.shadow_blur = 1.2
	sun.directional_shadow_max_distance = 60.0
	add_child(sun)
	_apply_settings()
	Events.settings_changed.connect(_apply_settings)
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


func apply(p_name: StringName, duration: float = 0.0) -> void:
	if sun == null:
		_build()
	preset_name = p_name
	var p: Dictionary = PRESETS.get(p_name, PRESETS[&"day"])
	var target_rot := Vector3(deg_to_rad(p["pitch"]), deg_to_rad(p["yaw"]), 0.0)
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
