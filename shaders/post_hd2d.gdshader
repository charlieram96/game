// HD-2D screen pass: tilt-shift depth of field (blur above and below a
// focus band), warm color grading, gentle bloom lift and vignette.
shader_type canvas_item;

uniform sampler2D screen : hint_screen_texture, filter_linear_mipmap;
uniform float focus_center = 0.52;
uniform float focus_width = 0.22;
uniform float blur_amount = 1.0;
uniform float max_lod = 3.0;
uniform float vignette = 0.35;
uniform float saturation = 1.08;
uniform float contrast = 1.05;
uniform vec3 shadow_tint = vec3(0.92, 0.95, 1.08);
uniform vec3 highlight_tint = vec3(1.06, 1.0, 0.92);
uniform float fade = 0.0;
uniform vec4 fade_color : source_color = vec4(0.0, 0.0, 0.0, 1.0);

void fragment() {
	float d = abs(SCREEN_UV.y - focus_center) - focus_width;
	float amount = clamp(d / max(0.001, 1.0 - focus_width - focus_center * 0.5), 0.0, 1.0);
	amount = amount * amount * blur_amount;
	vec3 col = textureLod(screen, SCREEN_UV, amount * max_lod).rgb;
	float l = dot(col, vec3(0.299, 0.587, 0.114));
	col = mix(vec3(l), col, saturation);
	col = (col - 0.5) * contrast + 0.5;
	col *= mix(shadow_tint, highlight_tint, smoothstep(0.2, 0.8, l));
	vec2 v = SCREEN_UV - 0.5;
	col *= 1.0 - vignette * dot(v, v) * 1.6;
	col = mix(col, fade_color.rgb, fade);
	COLOR = vec4(clamp(col, 0.0, 1.0), 1.0);
}
