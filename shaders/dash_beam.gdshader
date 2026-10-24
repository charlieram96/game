// A soft column of light standing on a dash's landing cell. Additive, with
// faint bands drifting upward; brightest at the floor.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_add, shadows_disabled, fog_disabled;

uniform vec4 color : source_color = vec4(0.4, 0.95, 1.0, 1.0);
uniform float opacity = 1.0;

void fragment() {
	// CylinderMesh: UV.y is 0 at the top rim, 1 at the bottom.
	float h = 1.0 - UV.y;
	float fade = pow(1.0 - h, 2.2);
	float bands = 0.75 + 0.25 * sin((h * 9.0 - TIME * 3.0) * 6.2831853 * 0.5);
	// Edges of the column (seen side-on) glow a little more than its middle.
	float rim = 0.6 + 0.4 * pow(abs(UV.x * 2.0 - 1.0), 0.5);
	ALBEDO = color.rgb * fade * bands * rim * 0.55 * opacity;
}
