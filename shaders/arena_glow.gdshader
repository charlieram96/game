// Soft additive light halo / haze on a camera-facing quad: brazier glows and
// the sun haze over the arena. A smooth radial (or vertical "shaft") falloff
// with a slow breathing flicker; it only ever adds light.
shader_type spatial;
render_mode unshaded, cull_disabled, blend_add, depth_draw_never, shadows_disabled;

uniform vec4 color : source_color = vec4(1.0, 0.6, 0.25, 1.0);
uniform float intensity = 0.35;
uniform float falloff = 2.2;
uniform float flicker = 0.12;
uniform float seed = 0.0;
uniform bool shaft = false;  // vertical beam instead of a round halo
uniform bool billboard = true;

void vertex() {
	if (billboard) {
		vec3 sc = vec3(length(MODEL_MATRIX[0].xyz), length(MODEL_MATRIX[1].xyz), length(MODEL_MATRIX[2].xyz));
		MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0] * sc.x, INV_VIEW_MATRIX[1] * sc.y, INV_VIEW_MATRIX[2] * sc.z, MODEL_MATRIX[3]);
		MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
	}
}

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float a;
	if (shaft) {
		float across = 1.0 - smoothstep(0.0, 1.0, abs(p.x));
		float along = smoothstep(-1.0, -0.2, -p.y) * (1.0 - smoothstep(0.6, 1.0, p.y));
		a = pow(across, falloff) * along;
	} else {
		a = pow(max(1.0 - length(p), 0.0), falloff);
	}
	float f = 1.0 + flicker * (sin(TIME * 7.3 + seed) * 0.6 + sin(TIME * 12.9 + seed * 2.1) * 0.4);
	ALBEDO = color.rgb * intensity * f;
	ALPHA = clamp(a, 0.0, 1.0);
}
