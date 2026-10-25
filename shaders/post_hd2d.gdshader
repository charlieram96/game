// HD-2D screen pass, drawn over the 3D view and under the UI:
// * tilt-shift blur: either a band round `focus_center` (the overworld) or,
//   in battle, the board's own rows on screen (`band_top`/`band_bottom`, set
//   by PostFX from the battle camera) so the whole board stays sharp and
//   only what lies behind and in front of it softens. (With high graphics
//   the battle uses the depth-aware pass in the scene instead: blur 0 here.)
// * filmic grade: a gentle S-curve, saturation, split toning (cool shadows,
//   warm highlights), vignette, a whisper of film grain and of colour
//   fringing toward the corners;
// * a brief radial colour split for big impacts, fades and flashes.
shader_type canvas_item;

uniform sampler2D screen : hint_screen_texture, filter_linear_mipmap;
uniform float focus_center = 0.52;
uniform float focus_width = 0.22;
uniform float blur_amount = 1.0;
uniform float max_lod = 3.0;
// > 0: blur reaches full strength this far (in screen height) past the focus
// band's edge. The default keeps the original ramp.
uniform float blur_ramp = -1.0;
// battle: the board's band on screen (0..1 from the top); band_ramp = how far
// past it (screen heights) the blur reaches full strength above / below
uniform bool board_band = false;
uniform float band_top = 0.15;
uniform float band_bottom = 0.85;
uniform vec2 band_ramp = vec2(0.16, 0.12);
// keep this much (screen heights) above the board's back edge sharp: what
// stands on the back rows rises above it
uniform float band_head = 0.07;
uniform float vignette = 0.35;
uniform float saturation = 1.08;
uniform float contrast = 1.05;
uniform vec3 shadow_tint = vec3(0.92, 0.95, 1.08);
uniform vec3 highlight_tint = vec3(1.06, 1.0, 0.92);
uniform float grain = 0.0;
// strength of the S-curve (0 = off)
uniform float filmic = 0.0;
// colour fringing at the corners, in pixels (0 = off)
uniform float aberration = 0.0;
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
	vec2 src = vec2(dir.x > 0.0 ? 0.0 : aspect, dir.y > 0.0 ? 0.0 : 1.0);
	float along = dot(p - src, dir);
	float across = dot(p - src, vec2(-dir.y, dir.x));
	float t = TIME * 0.05;
	float beams = smoothstep(0.25, 0.95, 0.5 + 0.5 * sin(across * 6.5 + t * 2.0 + 0.8));
	beams *= 0.55 + 0.45 * sin(across * 15.0 - t * 3.0 + 2.1);
	float fall = 1.0 - smoothstep(0.0, shaft_reach, along);
	return shaft_color.rgb * beams * fall;
}

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

vec3 blurred(vec2 uv, float lod, vec2 px) {
	if (lod < 0.01) {
		return textureLod(screen, uv, 0.0).rgb;
	}
	// four taps round the mip-mapped sample smooth out the mip blocks
	vec2 o = px * exp2(lod) * 0.5;
	vec3 c = textureLod(screen, uv + vec2(o.x, o.y), lod).rgb;
	c += textureLod(screen, uv + vec2(-o.x, o.y), lod).rgb;
	c += textureLod(screen, uv + vec2(o.x, -o.y), lod).rgb;
	c += textureLod(screen, uv + vec2(-o.x, -o.y), lod).rgb;
	return c * 0.25;
}

void fragment() {
	vec2 uv = SCREEN_UV;
	float amount;
	if (board_band) {
		float above = (band_top - band_head - uv.y) / max(band_ramp.x, 0.001);
		float below = (uv.y - band_bottom) / max(band_ramp.y, 0.001);
		amount = clamp(max(above, below), 0.0, 1.0);
	} else {
		float d = abs(uv.y - focus_center) - focus_width;
		amount = clamp(d / max(0.001, 1.0 - focus_width - focus_center * 0.5), 0.0, 1.0);
		if (blur_ramp > 0.0) {
			amount = clamp(d / blur_ramp, 0.0, 1.0);
		}
	}
	amount = amount * amount * blur_amount;
	float lod = amount * max_lod;
	vec3 col;
	vec2 dc = uv - 0.5;
	float edge = dot(dc, dc);
	if (aberration > 0.0 || impact > 0.001) {
		vec2 off = dc * SCREEN_PIXEL_SIZE * aberration * edge * 4.0 / max(length(dc), 1e-3);
		off += (uv - impact_center) * impact * 0.014;
		col.r = blurred(uv + off, lod, SCREEN_PIXEL_SIZE).r;
		col.g = blurred(uv, lod, SCREEN_PIXEL_SIZE).g;
		col.b = blurred(uv - off, lod, SCREEN_PIXEL_SIZE).b;
	} else {
		col = blurred(uv, lod, SCREEN_PIXEL_SIZE);
	}
	if (shafts > 0.0) {
		float aspect = SCREEN_PIXEL_SIZE.y / SCREEN_PIXEL_SIZE.x;
		col += sun_shafts(uv, aspect) * shafts * (1.0 - col * 0.5);
	}
	float l = dot(col, vec3(0.299, 0.587, 0.114));
	col = mix(vec3(l), col, saturation);
	// filmic S-curve round mid grey, then contrast
	if (filmic > 0.0) {
		vec3 s = clamp(col, 0.0, 1.0);
		col = mix(col, s * s * (3.0 - 2.0 * s), filmic);
	}
	col = (col - 0.5) * contrast + 0.5;
	col *= mix(shadow_tint, highlight_tint, smoothstep(0.2, 0.8, l));
	col *= 1.0 - vignette * edge * 1.6;
	if (grain > 0.0) {
		float g = hash(floor(FRAGCOORD.xy) + fract(TIME * 7.13) * 91.7) - 0.5;
		col += g * grain * (1.0 - l * 0.6);
	}
	col = mix(col, fade_color.rgb, fade);
	COLOR = vec4(clamp(col, 0.0, 1.0), 1.0);
}
