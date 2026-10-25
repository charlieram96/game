// Tilt-shift depth of field for the battle diorama, drawn as a full-screen
// pass right after the opaque geometry (render_priority -127, so every
// transparent effect - lanes, telegraphs, flames' halos, numbers - is drawn
// over it, sharp).
//
// Each pixel's world position is rebuilt from the depth buffer. Everything
// over the board's footprint (plus a margin for what stands on it) stays
// perfectly sharp - pixels there are discarded, untouched. Outside, the
// blur grows with the distance behind, in front of or beside the board,
// like a lens tilted so its plane of focus lies on the arena floor.
//
// The blur is a 16-tap golden-angle gather. Each tap counts by its own
// circle of confusion, so sharp things (the board, a pillar beside it)
// never smear into the blurred background round them.
shader_type spatial;
render_mode unshaded, depth_test_disabled, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;

uniform sampler2D screen_tex : hint_screen_texture, filter_linear, repeat_disable;
uniform sampler2D depth_tex : hint_depth_texture, filter_nearest, repeat_disable;
// world x/z rectangle kept sharp: x0, z0, x1, z1
uniform vec4 focus_rect = vec4(-11.0, -7.0, 11.0, 7.0);
// world units past the sharp rectangle where the blur reaches full strength
uniform float ramp_back = 2.3;
uniform float ramp_front = 2.6;
uniform float ramp_side = 7.0;
// heights well under the board (the lower ring, the ground) blur too
uniform float floor_y = -1.2;
uniform float ramp_below = 1.6;
// full-strength blur radius in pixels at 720 screen lines
uniform float max_radius = 7.0;
uniform float strength = 1.0;

const int TAPS = 16;

void vertex() {
	POSITION = vec4(VERTEX.xy * 2.0, 1.0, 1.0);
}

float coc_of(vec2 uv, mat4 inv_proj, mat4 inv_view) {
	float d = textureLod(depth_tex, uv, 0.0).r;
	if (d >= 0.99999) {
		return 1.0;
	}
	vec4 ndc = vec4(uv * 2.0 - 1.0, d * 2.0 - 1.0, 1.0);
	vec4 v = inv_proj * ndc;
	v.xyz /= v.w;
	vec3 w = (inv_view * vec4(v.xyz, 1.0)).xyz;
	float back = (focus_rect.y - w.z) / ramp_back;
	float front = (w.z - focus_rect.w) / ramp_front;
	float side = max(focus_rect.x - w.x, w.x - focus_rect.z) / ramp_side;
	float below = (floor_y - w.y) / ramp_below;
	float t = clamp(max(max(back, front), max(side, below)), 0.0, 1.0);
	return t * t * (3.0 - 2.0 * t);
}

float ign(vec2 p) {
	// interleaved gradient noise: decorrelates the taps between neighbouring pixels
	return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715))));
}

void fragment() {
	float coc = coc_of(SCREEN_UV, INV_PROJECTION_MATRIX, INV_VIEW_MATRIX) * strength;
	if (coc < 0.004) {
		discard;
	}
	float radius = coc * max_radius * VIEWPORT_SIZE.y / 720.0;
	vec2 px = 1.0 / VIEWPORT_SIZE;
	vec3 acc = textureLod(screen_tex, SCREEN_UV, 0.0).rgb;
	float wsum = 1.0;
	float rot = ign(FRAGCOORD.xy) * 6.2831853;
	for (int i = 0; i < TAPS; i++) {
		float fi = float(i) + 0.5;
		float r = sqrt(fi / float(TAPS)) * radius;
		float a = fi * 2.3999632 + rot;
		vec2 uv = SCREEN_UV + vec2(cos(a), sin(a)) * r * px;
		float tc = coc_of(uv, INV_PROJECTION_MATRIX, INV_VIEW_MATRIX) * strength;
		// a tap counts if its own blur would reach this pixel
		float w = clamp((tc * max_radius * VIEWPORT_SIZE.y / 720.0 - r * 0.5) / max(r * 0.5, 0.5), 0.0, 1.0);
		acc += textureLod(screen_tex, uv, 0.0).rgb * w;
		wsum += w;
	}
	ALBEDO = acc / wsum;
}
