// Triplanar pixel-art texturing for 3D environment meshes (walls, roofs,
// stones, crates). Textures are projected in world space at a fixed texel
// density, so every surface shares the sprites' pixel scale without UVs.
// Includes a ground-contact ambient-occlusion gradient and optional
// stepped (toon) light bands.
shader_type spatial;

uniform sampler2D tex : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D top_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform bool use_top_tex = false;
uniform vec2 tex_size = vec2(48.0, 48.0);
uniform vec2 top_tex_size = vec2(48.0, 48.0);
uniform float texels_per_unit = 24.0;
uniform vec4 tint : source_color = vec4(1.0);
uniform vec4 top_tint : source_color = vec4(1.0);
uniform vec2 uv_offset = vec2(0.0);
uniform float ao_height = 0.7;
uniform float ao_strength = 0.35;
uniform float ground_y = 0.0;
uniform float light_steps = 0.0;
uniform float emission_strength = 0.0;
uniform vec4 emission_color : source_color = vec4(1.0, 0.7, 0.3, 1.0);

varying vec3 wpos;
varying vec3 wnorm;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnorm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

vec4 sample_px(sampler2D t, vec2 size, vec2 texel) {
	vec2 seam = floor(texel + 0.5);
	vec2 d = max(fwidth(texel), vec2(1e-4));
	vec2 p = seam + clamp((texel - seam) / d, -0.5, 0.5);
	return textureGrad(t, p / size, dFdx(texel / size), dFdy(texel / size));
}

void fragment() {
	vec3 n = abs(wnorm);
	vec2 coord;
	bool top = false;
	if (n.y >= n.x && n.y >= n.z) {
		coord = wpos.xz;
		top = true;
	} else if (n.x >= n.z) {
		coord = vec2(wpos.z * sign(wnorm.x), -wpos.y);
	} else {
		coord = vec2(-wpos.x * sign(wnorm.z), -wpos.y);
	}
	vec2 texel = (coord + uv_offset) * texels_per_unit;
	vec4 c;
	if (top && use_top_tex) {
		c = sample_px(top_tex, top_tex_size, texel) * top_tint;
	} else {
		c = sample_px(tex, tex_size, texel) * tint;
	}
	float h = clamp((wpos.y - ground_y) / max(ao_height, 0.01), 0.0, 1.0);
	float ao = mix(1.0 - ao_strength, 1.0, smoothstep(0.0, 1.0, h));
	if (top) {
		ao = 1.0;
	}
	ALBEDO = c.rgb * ao;
	EMISSION = emission_color.rgb * emission_strength;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
}

void light() {
	float ndl = clamp(dot(NORMAL, LIGHT), 0.0, 1.0);
	if (light_steps > 0.5) {
		ndl = floor(ndl * light_steps + 0.5) / light_steps;
	}
	DIFFUSE_LIGHT += ATTENUATION * LIGHT_COLOR * ndl / PI;
}
