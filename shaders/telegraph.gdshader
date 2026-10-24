// Procedural ground telegraphs and indicators drawn on a flat quad:
// circle, ring, cone and box shapes with a fill that grows as the attack
// approaches, pulsing edges and pixel-quantized edges.
// shape: 0 circle, 1 ring, 2 cone, 3 box (box spans +X from the quad's left edge)
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_mix;

uniform int shape = 0;
uniform vec4 color : source_color = vec4(1.0, 0.35, 0.2, 1.0);
uniform vec4 fill_color : source_color = vec4(1.0, 0.45, 0.2, 1.0);
uniform float progress : hint_range(0.0, 1.0) = 0.0;
uniform float inner = 0.0;  // ring inner radius fraction
uniform float half_angle = 0.785;  // cone half angle (radians)
uniform float edge_px = 2.0;
uniform float opacity = 0.85;
uniform float pixel_grid = 24.0;  // texels per unit along the quad (quantization)
uniform vec2 quad_size = vec2(2.0, 2.0);  // world size of the quad

void fragment() {
	// Quantize to the shared pixel grid for crisp, pixel-art edges.
	vec2 world = (UV - 0.5) * quad_size;
	world = (floor(world * pixel_grid) + 0.5) / pixel_grid;
	vec2 p = world / (quad_size * 0.5);  // -1..1
	float edge = edge_px / (pixel_grid * quad_size.x * 0.5);
	float inside = 0.0;
	float border = 0.0;
	float fill_amt = 0.0;
	if (shape == 0 || shape == 1 || shape == 2) {
		float r = length(p);
		float in_r = shape == 1 ? inner : 0.0;
		inside = step(r, 1.0) * step(in_r, r);
		border = inside * (step(1.0 - edge, r) + (shape == 1 ? step(r, in_r + edge) : 0.0));
		fill_amt = step(r, progress);
		if (shape == 2) {
			float ang = abs(atan(p.y, p.x));
			float in_cone = step(ang, half_angle);
			inside *= in_cone;
			border = inside * max(step(1.0 - edge, r), step(half_angle - edge * 1.5 / max(r, 0.05), ang));
		}
	} else {
		// Box occupying the whole quad; fill sweeps from the left edge.
		vec2 q = UV;
		inside = 1.0;
		float ex = edge_px / (pixel_grid * quad_size.x);
		float ey = edge_px / (pixel_grid * quad_size.y);
		border = max(max(step(q.x, ex), step(1.0 - ex, q.x)), max(step(q.y, ey), step(1.0 - ey, q.y)));
		fill_amt = step(q.x, progress);
	}
	if (inside < 0.5) {
		discard;
	}
	float pulse = 0.75 + 0.25 * sin(TIME * 14.0);
	vec3 col = mix(fill_color.rgb * 0.55, fill_color.rgb, fill_amt);
	float a = mix(0.18, 0.45, fill_amt);
	col = mix(col, color.rgb, border);
	a = mix(a, 1.0 * pulse, border);
	ALBEDO = col;
	ALPHA = a * opacity;
}
