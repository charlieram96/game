// Arena board floor: one flagstone per logical cell, laid exactly on the
// cell grid (each tile owns a 1px grout border, so the 2px joint between two
// tiles is centred on the cell boundary), plus the 0.5-unit rim around the
// board whose slab joints line up with the columns and rows.
//
// * Per-cell data (`cells`, one texel per cell, built by ArenaBuilder):
//   R = tile index into the atlas, G = scorch decal (low 3 bits = index + 1,
//   bits 3-4 = flip), B = extra wear, A = highlight strength (0 = none; see
//   ArenaBuilder.set_cell_highlight).
// * The sun-crane inlay is composited over the tile faces; inside it the
//   grout turns into thin dark seams so the cell grid stays readable. A slow
//   glint sweeps across its brass every few seconds.
// * Texel-stepped contact darkening along the walls and around standing
//   stones, a soft polish toward the worn centre and a gentle falloff toward
//   the edges, per-cell tonal jitter, drifting cloud shadows (they only dim
//   the sun), rare twinkling quartz grains. Lambert lighting with no specular
//   (pixel-art friendly), smooth-pixel sampling (no shimmer when the camera
//   kicks or zooms).
shader_type spatial;

uniform sampler2D tiles : source_color, filter_linear, repeat_disable;
uniform vec2 tiles_size = vec2(192.0, 168.0);
uniform float tile_columns = 8.0;
uniform sampler2D cells : filter_nearest, repeat_disable;
uniform vec4 board_rect = vec4(-7.0, -4.5, 14.0, 9.0);  // x, z, width, depth (world)
uniform float texels = 24.0;  // texels per cell (= per unit)
uniform sampler2D rim : source_color, filter_linear, repeat_disable;
uniform vec2 rim_size = vec2(96.0, 36.0);
uniform float rim_width = 0.5;
uniform sampler2D decals : source_color, filter_linear, repeat_disable;
uniform vec2 decals_size = vec2(96.0, 24.0);
uniform sampler2D emblem : source_color, filter_linear, repeat_disable;
uniform vec2 emblem_size = vec2(120.0, 120.0);
uniform vec4 emblem_rect = vec4(0.0);  // x, z, width, depth (world); width 0 = no inlay
uniform float emblem_strength = 0.85;
uniform float emblem_saturation = 0.85;
// a slow glint sweeping across the brass every few seconds
uniform float emblem_sheen = 0.9;
uniform vec4 tint : source_color = vec4(0.79, 0.74, 0.68, 1.0);
// multiplier for the second chessboard tone (cells where x + y is odd)
uniform vec4 tone_b : source_color = vec4(0.88, 0.87, 0.88, 1.0);
uniform vec4 rim_tint : source_color = vec4(0.74, 0.72, 0.74, 1.0);
uniform vec4 wall_ao = vec4(0.42, 0.0, 0.36, 0.36);  // north, south, west, east strength
uniform float wall_ao_reach = 0.85;  // units from the rim's outer edge
uniform vec4 stones[6];  // x, z, radius, strength
uniform int stone_count = 0;
uniform float stone_ao_reach = 0.55;
uniform float centre_polish = 0.07;
// "Stage light": the board's edges fall off a little so the middle reads brightest.
uniform float edge_dim = 0.3;
uniform vec4 highlight_color : source_color = vec4(1.0, 0.9, 0.55, 1.0);
// per-cell tonal jitter (fraction of brightness)
uniform float cell_jitter = 0.05;
// slow, soft cloud shadows drifting over the board (fraction of sunlight blocked)
uniform float cloud_shadow = 0.0;
uniform vec2 cloud_wind = vec2(0.05, 0.022);
uniform float cloud_scale = 0.13;
// rare quartz grains that catch the sun and twinkle (fraction of texels)
uniform float glints = 0.0;

varying vec3 wpos;
varying float v_sun;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

// Crisp texels at any scale; `d` = screen-space texel derivative (passed in so
// it stays continuous when the atlas lookup jumps between cells).
vec4 sample_px(sampler2D t, vec2 size, vec2 texel, vec2 d) {
	vec2 seam = floor(texel + 0.5);
	texel = seam + clamp((texel - seam) / d, -0.5, 0.5);
	return textureLod(t, texel / size, 0.0);
}

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

vec3 board_tile(vec2 p, vec2 d, out vec2 local, out vec4 cd) {
	ivec2 n = ivec2(board_rect.zw + 0.5);
	ivec2 cell = clamp(ivec2(floor(p)), ivec2(0), n - 1);
	cd = texelFetch(cells, cell, 0);
	float idx = floor(cd.r * 255.0 + 0.5);
	vec2 atlas = vec2(mod(idx, tile_columns), floor(idx / tile_columns)) * texels;
	local = (p - vec2(cell)) * texels;
	vec3 c = sample_px(tiles, tiles_size, atlas + local, d).rgb;
	int g = int(cd.g * 255.0 + 0.5);
	int di = g & 7;
	if (di > 0) {
		int flip = (g >> 3) & 3;
		vec2 l = local;
		if (flip == 1 || flip == 3) {
			l.x = texels - l.x;
		}
		if (flip >= 2) {
			l.y = texels - l.y;
		}
		vec4 s = sample_px(decals, decals_size, vec2(float(di - 1) * texels, 0.0) + l, d);
		c *= mix(vec3(1.0), s.rgb * 1.15, s.a * 0.85);
	}
	if (((cell.x + cell.y) & 1) == 1) {
		c *= tone_b.rgb;
	}
	c *= 1.0 + (hash(vec2(cell) + vec2(17.0, 3.0)) - 0.5) * 2.0 * cell_jitter;
	return c * tint.rgb;
}

vec3 rim_slab(vec2 p, vec2 d) {
	vec2 size = board_rect.zw;
	bool out_x = p.x < 0.0 || p.x >= size.x;
	bool out_y = p.y < 0.0 || p.y >= size.y;
	vec2 texel;
	if (out_x && out_y) {
		vec2 l = vec2(p.x < 0.0 ? p.x + rim_width : p.x - size.x, p.y < 0.0 ? p.y + rim_width : p.y - size.y);
		texel = vec2(48.0, 12.0) + l * texels;
	} else if (out_y) {
		float k = floor(p.x);
		float side = p.y < 0.0 ? 0.0 : 1.0;
		float v = floor(hash(vec2(k, side + 3.0)) * 4.0);
		vec2 l = vec2(p.x - k, p.y < 0.0 ? p.y + rim_width : p.y - size.y);
		texel = vec2(v * 24.0, 0.0) + l * texels;
	} else {
		float k = floor(p.y);
		float side = p.x < 0.0 ? 0.0 : 1.0;
		float v = floor(hash(vec2(side + 7.0, k)) * 4.0);
		vec2 l = vec2(p.x < 0.0 ? p.x + rim_width : p.x - size.x, p.y - k);
		texel = vec2(v * 12.0, 12.0) + l * texels;
	}
	return sample_px(rim, rim_size, texel, d).rgb * rim_tint.rgb;
}

float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}

float falloff(float dist, float reach) {
	return 1.0 - smoothstep(0.0, reach, dist);
}

void fragment() {
	vec2 p = wpos.xz - board_rect.xy;
	vec2 tx = p * texels;
	vec2 d = max(fwidth(tx), vec2(1e-4));
	vec2 size = board_rect.zw;
	// texel centre (board-local units) for texel-stepped shading terms
	vec2 q = (floor(tx) + 0.5) / texels;
	vec3 c;
	bool inside = p.x >= 0.0 && p.y >= 0.0 && p.x < size.x && p.y < size.y;
	if (inside) {
		vec2 local;
		vec4 cd;
		c = board_tile(p, d, local, cd);
		vec2 lt = floor(local);
		bool grout = lt.x < 1.0 || lt.y < 1.0 || lt.x > texels - 2.0 || lt.y > texels - 2.0;
		bool lit = !grout && (lt.x < 2.0 || lt.y < 2.0);
		bool shade = !grout && (lt.x > texels - 3.0 || lt.y > texels - 3.0);
		if (emblem_rect.z > 0.0) {
			vec2 ep = (wpos.xz - emblem_rect.xy) / emblem_rect.zw;
			if (ep.x >= 0.0 && ep.y >= 0.0 && ep.x < 1.0 && ep.y < 1.0) {
				vec4 e = sample_px(emblem, emblem_size, ep * emblem_size, d);
				if (e.a > 0.5) {
					vec3 ec = mix(vec3(dot(e.rgb, vec3(0.299, 0.587, 0.114))), e.rgb, emblem_saturation) * tint.rgb;
					if (grout) {
						ec *= 0.5;
					} else if (lit) {
						ec = min(ec * 1.12, vec3(1.0));
					} else if (shade) {
						ec *= 0.85;
					}
					c = mix(c, ec, emblem_strength);
					if (emblem_sheen > 0.0 && !grout && e.r > e.b * 1.5) {
						vec2 et = floor(ep * emblem_size) / emblem_size;
						float phase = fract(TIME / 6.0) * 4.0 - 1.5;
						float band = 1.0 - smoothstep(0.0, 0.05, abs((et.x + et.y) * 0.5 - phase));
						EMISSION += vec3(1.0, 0.85, 0.5) * band * emblem_sheen;
					}
				}
			}
		}
		// worn, polished centre (stepped per texel)
		vec2 rel = (q - size * 0.5) / (size * 0.5);
		float polish = (1.0 - smoothstep(0.15, 0.85, length(rel))) * centre_polish + cd.b * 0.08;
		c = mix(c, c * 1.1 + vec3(0.015, 0.012, 0.0), polish);
		if (glints > 0.0 && !grout) {
			vec2 tq = floor(tx);
			float hg = hash(tq * 0.731 + vec2(3.1, 7.7));
			if (hg < glints) {
				float tw = pow(max(0.0, sin(TIME * (0.6 + hg * 9.0 / max(glints, 1e-4) * 0.08) + hg * 628.0)), 24.0);
				EMISSION += vec3(1.0, 0.92, 0.75) * tw * 0.9;
			}
		}
		if (cd.a > 0.0 && !grout) {
			float ring = (lt.x < 3.0 || lt.y < 3.0 || lt.x > texels - 4.0 || lt.y > texels - 4.0) ? 1.0 : 0.35;
			c = mix(c, highlight_color.rgb, cd.a * ring * 0.6);
			EMISSION += highlight_color.rgb * cd.a * ring * 0.22;
		}
	} else {
		c = rim_slab(p, d);
	}
	// contact darkening along the walls (measured from the rim's outer edge)
	float ao = 1.0;
	ao *= 1.0 - wall_ao.x * falloff(q.y + rim_width, wall_ao_reach);
	ao *= 1.0 - wall_ao.y * falloff(size.y + rim_width - q.y, wall_ao_reach);
	ao *= 1.0 - wall_ao.z * falloff(q.x + rim_width, wall_ao_reach);
	ao *= 1.0 - wall_ao.w * falloff(size.x + rim_width - q.x, wall_ao_reach);
	vec2 wq = q + board_rect.xy;
	for (int i = 0; i < stone_count; i++) {
		vec4 s = stones[i];
		float dist = length(wq - s.xy) - s.z;
		ao *= 1.0 - s.w * falloff(max(dist, 0.0), stone_ao_reach);
	}
	v_sun = 1.0;
	if (cloud_shadow > 0.0) {
		vec2 cp = (q + board_rect.xy) * cloud_scale + TIME * cloud_wind;
		float n = vnoise(cp) * 0.65 + vnoise(cp * 2.1 + 7.3) * 0.35;
		v_sun = 1.0 - cloud_shadow * smoothstep(0.42, 0.72, n);
	}
	vec2 sp = (q - size * 0.5) / (size * 0.5 + rim_width);
	ao *= 1.0 - edge_dim * smoothstep(0.45, 1.05, length(sp * vec2(0.92, 1.0)));
	ALBEDO = c * ao;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
}

void light() {
	float ndl = clamp(dot(NORMAL, LIGHT), 0.0, 1.0);
	float sun = LIGHT_IS_DIRECTIONAL ? v_sun : 1.0;
	DIFFUSE_LIGHT += ATTENUATION * LIGHT_COLOR * ndl * sun / PI;
}
