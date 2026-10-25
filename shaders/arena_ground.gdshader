// The ground round the dais: worn paving on the lower ring (48 texels per
// unit) giving way to grass and trodden earth outside it, with soft contact
// shadows (ambient occlusion) at the foot of everything that stands on it.
//
// The occluders are footprints (`ao_rects`: x0, z0, x1, z1 and `ao_params`:
// strength, reach), so the contact shadow follows the dais, the steps, the
// stands and every pillar base without baking anything. Lambert, no specular.
shader_type spatial;
render_mode cull_back;

uniform sampler2D paving : source_color, filter_linear_mipmap, repeat_enable;
uniform vec2 paving_size = vec2(192.0, 192.0);
uniform float paving_texels = 48.0;
uniform vec4 paving_tint : source_color = vec4(1.0);
uniform sampler2D outer : source_color, filter_linear_mipmap, repeat_enable;
uniform vec2 outer_size = vec2(48.0, 48.0);
uniform sampler2D outer_b : source_color, filter_linear_mipmap, repeat_enable;
uniform vec2 outer_b_size = vec2(48.0, 48.0);
uniform float outer_texels = 24.0;
uniform vec4 outer_tint : source_color = vec4(1.0);
// paved area (x0, z0, x1, z1) and how ragged its border is
uniform vec4 paved_rect = vec4(-13.0, -9.0, 13.0, 9.0);
uniform float border = 1.2;
uniform vec4 ao_rects[16];
uniform vec2 ao_params[16];
uniform int ao_count = 0;

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}

vec4 sample_px(sampler2D t, vec2 size, vec2 texel) {
	vec2 seam = floor(texel + 0.5);
	vec2 d = max(fwidth(texel), vec2(1e-4));
	vec2 p = seam + clamp((texel - seam) / d, -0.5, 0.5);
	return textureGrad(t, p / size, dFdx(texel / size), dFdy(texel / size));
}

float rect_dist(vec2 p, vec4 r) {
	vec2 c = (r.xy + r.zw) * 0.5;
	vec2 h = (r.zw - r.xy) * 0.5;
	vec2 d = abs(p - c) - h;
	return length(max(d, vec2(0.0))) + min(max(d.x, d.y), 0.0);
}

void fragment() {
	vec2 p = wpos.xz;
	// texel-stepped position for the border dither and the AO
	vec2 q = (floor(p * outer_texels) + 0.5) / outer_texels;
	float out_d = rect_dist(q, paved_rect);
	float n = vnoise(q * 1.3) * 0.7 + vnoise(q * 4.1 + 3.0) * 0.3;
	float paved = step(out_d + (n - 0.5) * border * 1.6, 0.0);
	vec3 c;
	if (paved > 0.5) {
		c = sample_px(paving, paving_size, p * paving_texels).rgb * paving_tint.rgb;
	} else {
		vec3 g = sample_px(outer, outer_size, p * outer_texels).rgb;
		vec3 e = sample_px(outer_b, outer_b_size, p * outer_texels).rgb;
		float blend_n = vnoise(q * 0.35 + 11.0) + (hash(floor(q * outer_texels * 0.5)) - 0.5) * 0.25;
		c = (blend_n > 0.62 ? e : g) * outer_tint.rgb;
	}
	float ao = 1.0;
	for (int i = 0; i < ao_count; i++) {
		float d = max(rect_dist(q, ao_rects[i]), 0.0);
		vec2 prm = ao_params[i];
		ao *= 1.0 - prm.x * (1.0 - smoothstep(0.0, prm.y, d));
	}
	ALBEDO = c * ao;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
}

void light() {
	DIFFUSE_LIGHT += ATTENUATION * LIGHT_COLOR * clamp(dot(NORMAL, LIGHT), 0.0, 1.0) / PI;
}
