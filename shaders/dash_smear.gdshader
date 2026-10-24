// Ground smear left by a dash: a streak from where the dash started to the
// creature, bright at the head and tapering toward the tail, with soft
// speed lines. The quad's local X runs along the dash (UV.x 0 = tail).
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_add, shadows_disabled, fog_disabled;

uniform vec4 color : source_color = vec4(0.4, 0.95, 1.0, 1.0);
uniform float opacity = 1.0;
uniform float length_units = 3.0;
uniform float seed = 0.0;

float hash(float n) {
	return fract(sin(n) * 43758.5453);
}

void fragment() {
	float x = UV.x;
	float y = UV.y * 2.0 - 1.0;
	// Taper: thin tail, full width near the head.
	float width = mix(0.25, 1.0, smoothstep(0.0, 0.85, x));
	float body = 1.0 - smoothstep(width * 0.35, width, abs(y));
	float along = smoothstep(0.0, 0.6, x) * (1.0 - smoothstep(0.94, 1.0, x));
	// Speed lines: a few thin streaks across the width.
	float lane = floor((y * 0.5 + 0.5) * 7.0);
	float streak = step(0.55, hash(lane + seed * 13.1)) * smoothstep(0.0, 0.08, fract((y * 0.5 + 0.5) * 7.0)) * (1.0 - smoothstep(0.18, 0.32, fract((y * 0.5 + 0.5) * 7.0)));
	float a = body * along * (0.45 + 0.55 * streak);
	ALBEDO = color.rgb * a * opacity;
}
