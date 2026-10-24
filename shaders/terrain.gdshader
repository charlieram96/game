// Splat-mapped pixel terrain. A low-resolution splat map (one texel per
// world unit) chooses between up to five pixel textures; material borders
// are dithered per texel so transitions look hand-placed rather than
// blurred. Optional logical-cell grid overlay for arenas.
shader_type spatial;

uniform sampler2D base_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D tex_r : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D tex_g : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D tex_b : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D tex_a : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D splat : filter_linear, repeat_disable;
uniform vec4 splat_rect = vec4(-32.0, -32.0, 64.0, 64.0);  // x, z, width, depth
uniform float texels_per_unit = 24.0;
uniform vec2 tex_size = vec2(48.0, 48.0);
uniform vec4 tint : source_color = vec4(1.0);
uniform float grid_strength = 0.0;
uniform vec4 grid_rect = vec4(-8.0, -5.0, 16.0, 10.0);
uniform vec4 grid_color : source_color = vec4(0.25, 0.18, 0.1, 1.0);
uniform float dither = 0.55;

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

vec4 sample_px(sampler2D t, vec2 texel) {
	vec2 seam = floor(texel + 0.5);
	vec2 d = max(fwidth(texel), vec2(1e-4));
	vec2 p = seam + clamp((texel - seam) / d, -0.5, 0.5);
	return textureGrad(t, p / tex_size, dFdx(texel / tex_size), dFdy(texel / tex_size));
}

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

void fragment() {
	vec2 texel = wpos.xz * texels_per_unit;
	vec2 suv = (wpos.xz - splat_rect.xy) / splat_rect.zw;
	vec4 w = texture(splat, suv);
	// Per-texel dithered threshold so borders break up into pixel clusters.
	vec2 cluster = floor(texel / 2.0);
	float noise = (hash(cluster) - 0.5) * dither;
	vec4 c = sample_px(base_tex, texel);
	if (w.r + noise > 0.5) c = sample_px(tex_r, texel);
	if (w.g + noise > 0.5) c = sample_px(tex_g, texel);
	if (w.b + noise > 0.5) c = sample_px(tex_b, texel);
	if (w.a + noise > 0.5) c = sample_px(tex_a, texel);
	vec3 col = c.rgb * tint.rgb;
	if (grid_strength > 0.0) {
		vec2 g = wpos.xz - grid_rect.xy;
		if (g.x > 0.0 && g.y > 0.0 && g.x < grid_rect.z && g.y < grid_rect.w) {
			vec2 f = abs(fract(g + 0.5) - 0.5);
			float px = 1.0 / texels_per_unit;
			float line = step(min(f.x, f.y), px * 0.75);
			col = mix(col, grid_color.rgb, line * grid_strength);
		}
	}
	ALBEDO = col;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
}
