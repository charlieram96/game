// Drag-dash lane: the board cells a dash will cross, one inset tile per cell,
// with scrolling chevrons and a travelling sheen. A single quad covers the
// lane; its local X runs along the dash, so UV.x 0..1 = 0..cell_span cells
// and UV.y runs across it.
//
// Tiles are layered for contrast on any floor: a soft dark halo, a deep
// translucent fill, a bright rim, white chevrons on top.
//
// cell_state, per cell: 0 hidden, 1 path, 2 landing, 3 ram (a foe the dash
// will hit), 4 cut off (asked for but out of reach), 5 wall (the dash stops
// at this cell's near edge).
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_mix, shadows_disabled, fog_disabled;

const int MAX_CELLS = 12;

uniform float cell_span = 6.0;
uniform float cell_state[12];
// Cells shown so far: tiles pop in one after another as this grows.
uniform float reveal = 12.0;
// Cells already travelled (committed dashes): tiles flare and fade behind
// the dasher. Negative = nothing travelled yet.
uniform float consumed = -1.0;
uniform vec4 main_color : source_color = vec4(0.35, 0.9, 0.95, 1.0);
uniform vec4 accent_color : source_color = vec4(1.0, 1.0, 1.0, 1.0);
uniform vec4 ram_color : source_color = vec4(1.0, 0.8, 0.32, 1.0);
uniform vec4 block_color : source_color = vec4(1.0, 0.36, 0.3, 1.0);
uniform vec4 ink_color : source_color = vec4(0.03, 0.05, 0.09, 1.0);
uniform float opacity = 1.0;
// Compensates the scene tonemapper so the colours stay vivid.
uniform float energy = 1.45;
// Hazard stripes for an opponent's committed dash.
uniform float danger = 0.0;
// Whitening flash when a dash commits.
uniform float flash = 0.0;
uniform float scroll_speed = 1.5;

float sd_round_box(vec2 p, vec2 b, float r) {
	vec2 q = abs(p) - b + r;
	return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

float sd_segment(vec2 p, vec2 a, vec2 b) {
	vec2 pa = p - a;
	vec2 ba = b - a;
	float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
	return length(pa - ba * h);
}

float ease_out_back(float x) {
	float c1 = 1.9;
	float c3 = c1 + 1.0;
	float y = x - 1.0;
	return 1.0 + c3 * y * y * y + c1 * y * y;
}

// A ">" pointing along +x.
float sd_chevron(vec2 p, float size, float thick) {
	vec2 apex = vec2(size * 0.42, 0.0);
	float d1 = sd_segment(p, apex, vec2(-size * 0.3, size * 0.62));
	float d2 = sd_segment(p, apex, vec2(-size * 0.3, -size * 0.62));
	return min(d1, d2) - thick;
}

// Porter-Duff "over": paint colour c with coverage a on top of dst.
vec4 over(vec4 dst, vec3 c, float a) {
	float oa = a + dst.a * (1.0 - a);
	vec3 rgb = (c * a + dst.rgb * dst.a * (1.0 - a)) / max(oa, 0.0001);
	return vec4(rgb, oa);
}

void fragment() {
	float s = UV.x * cell_span;
	float t = UV.y - 0.5;
	int k = clamp(int(floor(s)), 0, MAX_CELLS - 1);
	float state = cell_state[k];
	float appear = clamp(reveal - float(k), 0.0, 1.0);
	if (state < 0.5 || appear <= 0.0) {
		discard;
	}
	vec2 q = vec2(fract(s) - 0.5, t);
	float aa = max(fwidth(s), 0.0005) * 1.25;
	float pop = ease_out_back(appear);
	float half_size = 0.42 * pop;
	float d = sd_round_box(q, vec2(half_size), 0.11 * pop);
	float inside = smoothstep(aa, -aa, d);
	float halo = smoothstep(0.075, 0.0, d) * (1.0 - inside);
	float pulse = 0.5 + 0.5 * sin(TIME * 8.0);
	vec4 o = vec4(0.0);
	if (state > 4.5) {
		// Wall: a hard bar across the near edge, hatching behind it.
		float bar = sd_round_box(q - vec2(-0.43, 0.0), vec2(0.045, 0.4 * pop), 0.03);
		float zone = sd_round_box(q - vec2(-0.28, 0.0), vec2(0.11, 0.4 * pop), 0.02);
		float hatch = step(0.5, fract((q.y - q.x) * 8.0)) * smoothstep(aa, -aa, zone);
		float bar_halo = smoothstep(0.07, 0.0, bar);
		o = over(o, ink_color.rgb, bar_halo * 0.5);
		o = over(o, block_color.rgb * 0.7, hatch * 0.45);
		o = over(o, mix(block_color.rgb, vec3(1.0), 0.25 * pulse), smoothstep(aa, -aa, bar));
	} else if (state > 3.5) {
		// Out of reach: a dashed outline on a dark wash.
		float ang = atan(q.y, q.x);
		float dashes = step(0.42, fract(ang / 6.2831853 * 12.0));
		float edge = smoothstep(aa, -aa, abs(d + 0.025) - 0.024);
		o = over(o, ink_color.rgb, inside * 0.18);
		o = over(o, block_color.rgb, edge * dashes * 0.85);
	} else {
		bool landing = state > 1.5 && state < 2.5;
		bool ram = state > 2.5;
		vec3 base = ram ? ram_color.rgb : main_color.rgb;
		vec3 light = mix(base, vec3(1.0), 0.4);
		float border_w = landing ? 0.05 : 0.032;
		float border = smoothstep(aa, -aa, abs(d + border_w) - border_w);
		float glow = exp(-max(-d, 0.0) * 9.0) * inside;
		// A shaded panel (darker than any floor) lit by its coloured rim.
		float shade = landing ? 0.42 : 0.3;
		if (ram) {
			shade = 0.34 + 0.12 * pulse;
		}
		o = over(o, ink_color.rgb, halo * 0.45);
		o = over(o, ink_color.rgb, shade * inside);
		o = over(o, base, glow * (landing ? 0.75 : 0.6));
		if (ram || landing) {
			o = over(o, base, inside * (ram ? 0.22 + 0.18 * pulse : 0.2));
		}
		if (danger > 0.0) {
			float stripes = step(0.5, fract((s + t) * 2.6 - TIME * 3.2));
			o = over(o, base, stripes * inside * 0.35 * danger);
		}
		// A sheen sweeping from the creature to the landing cell.
		float head = fract(TIME * 0.85) * (min(reveal, cell_span) + 1.6) - 0.8;
		float sheen = exp(-pow((s - head) * 2.4, 2.0));
		o = over(o, light, sheen * inside * 0.35);
		o = over(o, light, border);
		if (!landing) {
			// One chevron per tile, lit in sequence like runway lights.
			float wave_head = fract(TIME * scroll_speed * 0.5) * (min(reveal, cell_span) + 2.0) - 1.0;
			float lit = exp(-pow((float(k) + 0.5 - wave_head) * 1.3, 2.0));
			float nudge = 0.05 * lit;
			float cd = sd_chevron(q - vec2(nudge, 0.0), 0.36 * pop, 0.042 * pop);
			if (ram) {
				cd = min(sd_chevron(q - vec2(nudge - 0.1, 0.0), 0.3 * pop, 0.036 * pop), sd_chevron(q - vec2(nudge + 0.1, 0.0), 0.3 * pop, 0.036 * pop));
			}
			float ca = smoothstep(aa, -aa, cd);
			float c_halo = smoothstep(0.05, 0.0, cd) * (1.0 - ca);
			o = over(o, ink_color.rgb, c_halo * 0.35);
			o = over(o, mix(light, accent_color.rgb, 0.35 + 0.65 * lit), ca * (0.72 + 0.28 * lit));
		} else {
			// Landing: an inner frame, so the target cell reads at a glance.
			float inner = smoothstep(aa, -aa, abs(sd_round_box(q, vec2(half_size * 0.62), 0.06) ) - 0.018);
			o = over(o, light, inner * 0.75);
		}
	}
	if (consumed >= 0.0) {
		float passed = clamp((consumed - float(k) - 0.3) * 2.6, 0.0, 1.0);
		float flare = passed * (1.0 - passed) * 4.0;
		o.rgb = mix(o.rgb, accent_color.rgb, flare * 0.6);
		o.a = o.a * (1.0 - passed) + flare * inside * 0.35;
	}
	o.rgb = mix(o.rgb, accent_color.rgb, flash * 0.75);
	o.a = max(o.a, inside * flash * 0.6);
	ALBEDO = o.rgb * energy;
	ALPHA = clamp(o.a, 0.0, 1.0) * opacity;
}
