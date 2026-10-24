// HD-2D screen pass: tilt-shift depth of field (blur above and below a
// focus band), warm color grading, gentle bloom lift and vignette, plus a
// brief radial colour split for big impacts.
shader_type canvas_item;

uniform sampler2D screen : hint_screen_texture, filter_linear_mipmap;
uniform float focus_center = 0.52;
uniform float focus_width = 0.22;
uniform float blur_amount = 1.0;
uniform float max_lod = 3.0;
// > 0: blur reaches full strength this far (in screen height) past the focus
// band's edge. The default keeps the original ramp.
uniform float blur_ramp = -1.0;
uniform float vignette = 0.35;
uniform float saturation = 1.08;
uniform float contrast = 1.05;
uniform vec3 shadow_tint = vec3(0.92, 0.95, 1.08);
uniform vec3 highlight_tint = vec3(1.06, 1.0, 0.92);
uniform float fade = 0.0;
uniform vec4 fade_color : source_color = vec4(0.0, 0.0, 0.0, 1.0);
// Impact frame: 0..1 strength of a radial RGB split around impact_center.
uniform float impact = 0.0;
uniform vec2 impact_center = vec2(0.5, 0.5);
// Optional sun shafts (off by default): soft additive beams travelling along
// `shaft_dir` (screen space, y down) from the corner they come from, fading
// out along their length.
uniform float shafts = 0.0;
uniform vec2 shaft_dir = vec2(0.42, 1.0);
uniform float shaft_reach = 1.1;
uniform vec4 shaft_color : source_color = vec4(1.0, 0.86, 0.62, 1.0);

vec3 sun_shafts(vec2 uv, float aspect) {
	vec2 dir = normalize(shaft_dir);
	vec2 p = vec2(uv.x * aspect, uv.y);
	// distance travelled from the source corner, and position across the beams
	vec2 src = vec2(dir.x > 0.0 ? 0.0 : aspect, dir.y > 0.0 ? 0.0 : 1.0);
	float along = dot(p - src, dir);
	float across = dot(p - src, vec2(-dir.y, dir.x));
	float t = TIME * 0.05;
	float beams = smoothstep(0.25, 0.95, 0.5 + 0.5 * sin(across * 6.5 + t * 2.0 + 0.8));
	beams *= 0.55 + 0.45 * sin(across * 15.0 - t * 3.0 + 2.1);
	float fall = 1.0 - smoothstep(0.0, shaft_reach, along);
	return shaft_color.rgb * beams * fall;
}

void fragment() {
	float d = abs(SCREEN_UV.y - focus_center) - focus_width;
	float amount = clamp(d / max(0.001, 1.0 - focus_width - focus_center * 0.5), 0.0, 1.0);
	if (blur_ramp > 0.0) {
		amount = clamp(d / blur_ramp, 0.0, 1.0);
	}
	amount = amount * amount * blur_amount;
	vec3 col = textureLod(screen, SCREEN_UV, amount * max_lod).rgb;
	if (impact > 0.001) {
		vec2 dc = SCREEN_UV - impact_center;
		vec2 off = dc * impact * 0.014;
		col.r = textureLod(screen, SCREEN_UV + off, amount * max_lod).r;
		col.b = textureLod(screen, SCREEN_UV - off, amount * max_lod).b;
	}
	if (shafts > 0.0) {
		float aspect = SCREEN_PIXEL_SIZE.y / SCREEN_PIXEL_SIZE.x;
		col += sun_shafts(SCREEN_UV, aspect) * shafts * (1.0 - col * 0.5);
	}
	float l = dot(col, vec3(0.299, 0.587, 0.114));
	col = mix(vec3(l), col, saturation);
	col = (col - 0.5) * contrast + 0.5;
	col *= mix(shadow_tint, highlight_tint, smoothstep(0.2, 0.8, l));
	vec2 v = SCREEN_UV - 0.5;
	col *= 1.0 - vignette * dot(v, v) * 1.6;
	col = mix(col, fade_color.rgb, fade);
	COLOR = vec4(clamp(col, 0.0, 1.0), 1.0);
}
