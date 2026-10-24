// Landing reticle for an aimed dash: corner brackets that snap onto the
// landing cell, a pulsing core diamond, a slowly turning dashed ring and an
// optional charge ring (held key / stick: fills toward the next cell).
// Bright shapes on a soft dark halo, so it reads on any floor.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_mix, shadows_disabled, fog_disabled;

uniform vec4 color : source_color = vec4(0.4, 0.95, 1.0, 1.0);
uniform vec4 core_color : source_color = vec4(1.0, 1.0, 1.0, 1.0);
uniform vec4 ink_color : source_color = vec4(0.03, 0.05, 0.09, 1.0);
uniform float opacity = 1.0;
// Compensates the scene tonemapper so the colours stay vivid.
uniform float energy = 1.45;
// 0 -> 1 as the brackets snap onto a new cell.
uniform float lock = 1.0;
// 0..1 charge toward the next cell; negative hides the charge ring.
uniform float charge = -1.0;
// World units covered by the quad.
uniform float quad_size = 1.7;

float sd_box(vec2 p, vec2 b) {
	vec2 d = abs(p) - b;
	return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}

float sd_segment(vec2 p, vec2 a, vec2 b) {
	vec2 pa = p - a;
	vec2 ba = b - a;
	float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
	return length(pa - ba * h);
}

vec4 over(vec4 dst, vec3 c, float a) {
	float oa = a + dst.a * (1.0 - a);
	vec3 rgb = (c * a + dst.rgb * dst.a * (1.0 - a)) / max(oa, 0.0001);
	return vec4(rgb, oa);
}

void fragment() {
	vec2 p = (UV - 0.5) * quad_size;
	float aa = max(fwidth(p.x), 0.0005) * 1.25;
	float l = clamp(lock, 0.0, 1.0);
	float ease = 1.0 - pow(1.0 - l, 3.0);
	float t = TIME;
	// Corner brackets: they start wide and snap in, then breathe.
	float half_s = 0.52 + (1.0 - ease) * 0.3 + 0.02 * sin(t * 5.5);
	vec2 q = abs(p);
	float arm = 0.22 + 0.04 * (1.0 - ease);
	float th = 0.05;
	float br = min(sd_segment(q, vec2(half_s), vec2(half_s - arm, half_s)), sd_segment(q, vec2(half_s), vec2(half_s, half_s - arm))) - th;
	float a_br = smoothstep(aa, -aa, br);
	float br_halo = smoothstep(0.08, 0.0, br) * (1.0 - a_br);
	// Core diamond.
	float pulse = 0.5 + 0.5 * sin(t * 7.0);
	vec2 r = vec2(p.x + p.y, p.x - p.y) * 0.70710678;
	float dia = sd_box(r, vec2(0.08 + 0.02 * pulse)) - 0.01;
	float a_dia = smoothstep(aa, -aa, dia);
	float dia_halo = smoothstep(0.07, 0.0, dia) * (1.0 - a_dia);
	// Dashed ring, turning.
	float rad = length(p);
	float ring = abs(rad - 0.27) - 0.02;
	float ang = atan(p.y, p.x);
	float dashes = step(0.45, fract((ang + t * 1.4) / 6.2831853 * 10.0));
	float a_ring = smoothstep(aa, -aa, ring) * dashes * ease;
	vec4 o = vec4(0.0);
	o = over(o, ink_color.rgb, br_halo * 0.5);
	o = over(o, ink_color.rgb, dia_halo * 0.45);
	o = over(o, color.rgb, a_ring * 0.9);
	o = over(o, mix(color.rgb, vec3(1.0), 0.35), a_br);
	o = over(o, core_color.rgb, a_dia);
	// Charge ring: fills clockwise from north.
	if (charge >= 0.0) {
		float cr = abs(rad - 0.72) - 0.032;
		float band = smoothstep(aa, -aa, cr);
		float band_halo = smoothstep(0.06, 0.0, cr) * (1.0 - band);
		float u = fract(atan(p.x, -p.y) / 6.2831853 + 1.0);
		o = over(o, ink_color.rgb, band_halo * 0.4 + band * 0.35);
		o = over(o, core_color.rgb, band * step(u, charge));
	}
	ALBEDO = o.rgb * energy;
	ALPHA = clamp(o.a, 0.0, 1.0) * opacity;
}
