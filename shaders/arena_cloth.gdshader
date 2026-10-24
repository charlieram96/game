// Pixel-art cloth banner hanging from a rod: one region of a banner atlas on
// a quad (UV y = 0 at the rod), crisp texels, alpha-scissored silhouette,
// gentle wind sway that grows toward the hem, lit like the walls.
shader_type spatial;
render_mode cull_disabled;

uniform sampler2D atlas : source_color, filter_linear, repeat_disable;
uniform vec2 atlas_size = vec2(32.0, 30.0);
uniform vec4 region = vec4(0.0, 0.0, 16.0, 30.0);  // x, y, w, h in texels
uniform float sway = 0.05;  // world units at the hem
uniform float seed = 0.0;
uniform vec4 tint : source_color = vec4(1.0);

void vertex() {
	float t = UV.y * UV.y;
	float ph = TIME * 1.6 + seed + VERTEX.x * 1.7;
	VERTEX.x += sin(ph) * sway * t;
	VERTEX.z += (0.5 + 0.5 * sin(ph * 1.3 + 1.0)) * sway * 0.6 * t;
}

void fragment() {
	vec2 tex_px = region.xy + UV * region.zw;
	vec2 seam = floor(tex_px + 0.5);
	vec2 d = max(fwidth(tex_px), vec2(1e-4));
	tex_px = seam + clamp((tex_px - seam) / d, -0.5, 0.5);
	vec4 c = textureLod(atlas, tex_px / atlas_size, 0.0);
	ALPHA = c.a;
	ALPHA_SCISSOR_THRESHOLD = 0.5;
	ALBEDO = c.rgb * tint.rgb;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
}

void light() {
	float ndl = dot(NORMAL, LIGHT);
	DIFFUSE_LIGHT += ATTENUATION * LIGHT_COLOR * mix(0.55, 1.0, clamp(ndl * 0.5 + 0.5, 0.0, 1.0)) / PI;
}
