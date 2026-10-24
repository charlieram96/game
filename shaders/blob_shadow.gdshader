// Soft contact shadow under characters and creatures. Pixel-quantized so it
// matches the art, and it always marks the true gameplay position (feet).
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_mix;

uniform float opacity = 0.45;
uniform float softness = 0.35;
uniform float steps = 4.0;

void fragment() {
	vec2 p = (UV - 0.5) * 2.0;
	float r = length(p);
	float a = 1.0 - smoothstep(1.0 - softness, 1.0, r);
	a = floor(a * steps + 0.5) / steps;
	if (a <= 0.0) {
		discard;
	}
	ALBEDO = vec3(0.05, 0.03, 0.08);
	ALPHA = a * opacity;
}
