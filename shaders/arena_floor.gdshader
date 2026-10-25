// The battle board: one beveled flagstone per logical cell (real geometry,
// built by ArenaBuilder), the rim slabs round it and the mortar bed between
// them, all in one mesh with one material.
//
// * Vertex data: UV = texels in the floor atlas (each stone's face is mapped
//   from above, so its bevel and sides continue the face), COLOR.rgb = the
//   stone's tint, COLOR.a = what it is (1 face, 0.6 rim, 0.3 mortar).
// * Per-cell data (`cells`, one texel per cell): G = scorch decal (low 3 bits
//   = index + 1, bits 3-4 = flip), A = highlight strength (0 = none; see
//   ArenaBuilder.set_cell_highlight).
// * The sun-crane inlay is painted over the stones' faces only, so the joints
//   (real gaps) keep the cell grid readable through it; a slow glint sweeps
//   across its brass.
// * Contact darkening along the walls and round the standing stones, drifting
//   cloud shadows that only dim the sun, rare quartz grains that twinkle.
//   Lambert lighting, no specular (pixel-art friendly), "smooth pixel"
//   sampling with mipmaps (crisp texels up close, no shimmer far away).
shader_type spatial;
render_mode cull_back;

uniform sampler2D atlas : source_color, filter_linear_mipmap, repeat_disable;
uniform vec2 atlas_size = vec2(448.0, 448.0);
uniform sampler2D cells : filter_nearest, repeat_disable;
uniform vec4 board_rect = vec4(-10.0, -6.0, 20.0, 12.0);  // x, z, width, depth (world)
uniform float texels = 48.0;  // texels per cell (= per unit)
uniform sampler2D decals : source_color, filter_linear, repeat_disable;
uniform vec2 decals_size = vec2(192.0, 48.0);
uniform sampler2D emblem : source_color, filter_linear_mipmap, repeat_disable;
uniform vec2 emblem_size = vec2(240.0, 240.0);
uniform vec4 emblem_rect = vec4(0.0);  // x, z, width, depth (world); width 0 = no inlay
uniform float emblem_strength = 0.92;
uniform float emblem_sheen = 0.9;
uniform vec4 tint : source_color = vec4(1.0);
uniform vec4 wall_ao = vec4(0.45, 0.0, 0.3, 0.3);  // north, south, west, east strength
uniform float wall_ao_reach = 0.9;  // units in from the board's edge
uniform vec4 stones[6];  // x, z, radius, strength
uniform int stone_count = 0;
uniform float stone_ao_reach = 0.6;
uniform vec4 highlight_color : source_color = vec4(1.0, 0.9, 0.55, 1.0);
// slow, soft cloud shadows drifting over the board (fraction of sunlight blocked)
uniform float cloud_shadow = 0.0;
uniform vec2 cloud_wind = vec2(0.05, 0.022);
uniform float cloud_scale = 0.15;
uniform float edge_dim = 0.12;
// rare quartz grains that catch the sun and twinkle (fraction of face texels)
uniform float glints = 0.0;
// the joints darken toward the mortar bed (ambient occlusion in the gaps)
uniform float joint_ao = 0.6;
uniform float mortar_y = -0.075;

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

// Crisp texels with one-pixel anti-aliased edges; mip-mapped when minified.
vec4 sample_px(sampler2D t, vec2 size, vec2 texel) {
	vec2 seam = floor(texel + 0.5);
	vec2 d = max(fwidth(texel), vec2(1e-4));
	vec2 p = seam + clamp((texel - seam) / d, -0.5, 0.5);
	return textureGrad(t, p / size, dFdx(texel / size), dFdy(texel / size));
}

vec4 sample_px_lod0(sampler2D t, vec2 size, vec2 texel) {
	vec2 seam = floor(texel + 0.5);
	vec2 d = max(fwidth(texel), vec2(1e-4));
	vec2 p = seam + clamp((texel - seam) / d, -0.5, 0.5);
	return textureLod(t, p / size, 0.0);
}

float falloff(float dist, float reach) {
	return 1.0 - smoothstep(0.0, reach, dist);
}

void fragment() {
	float kind = COLOR.a;
	vec3 c = sample_px(atlas, atlas_size, UV).rgb * COLOR.rgb * tint.rgb;
	vec2 p = wpos.xz - board_rect.xy;
	vec2 size = board_rect.zw;
	vec2 tx = p * texels;
	// texel centre (board-local units) for texel-stepped shading terms
	vec2 q = (floor(tx) + 0.5) / texels;
	bool face = kind > 0.8;
	bool inside = p.x >= 0.0 && p.y >= 0.0 && p.x < size.x && p.y < size.y;
	if (face && inside) {
		ivec2 n = ivec2(size + 0.5);
		ivec2 cell = clamp(ivec2(floor(p)), ivec2(0), n - 1);
		vec4 cd = texelFetch(cells, cell, 0);
		vec2 local = (p - vec2(cell)) * texels;
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
			vec4 s = sample_px_lod0(decals, decals_size, vec2(float(di - 1) * texels, 0.0) + l);
			c *= mix(vec3(1.0), s.rgb * 1.2, s.a * 0.85);
		}
		if (emblem_rect.z > 0.0) {
			vec2 ep = (wpos.xz - emblem_rect.xy) / emblem_rect.zw;
			if (ep.x >= 0.0 && ep.y >= 0.0 && ep.x < 1.0 && ep.y < 1.0) {
				vec4 e = sample_px(emblem, emblem_size, ep * emblem_size);
				if (e.a > 0.5) {
					c = mix(c, e.rgb * tint.rgb, emblem_strength);
					if (emblem_sheen > 0.0 && e.r > e.b * 1.5) {
						vec2 et = floor(ep * emblem_size) / emblem_size;
						float phase = fract(TIME / 6.0) * 4.0 - 1.5;
						float band = 1.0 - smoothstep(0.0, 0.04, abs((et.x + et.y) * 0.5 - phase));
						EMISSION += vec3(1.0, 0.85, 0.5) * band * emblem_sheen;
					}
				}
			}
		}
		if (glints > 0.0) {
			vec2 tq = floor(tx);
			float hg = hash(tq * 0.731 + vec2(3.1, 7.7));
			if (hg < glints) {
				float tw = pow(max(0.0, sin(TIME * (0.6 + hg / max(glints, 1e-4) * 0.7) + hg * 628.0)), 24.0);
				EMISSION += vec3(1.0, 0.92, 0.75) * tw * 0.9;
			}
		}
		if (cd.a > 0.0) {
			// a lit border round the cell, a fainter fill
			float e = min(min(local.x, local.y), min(texels - local.x, texels - local.y));
			float ring = e < 5.0 ? 1.0 : 0.35;
			c = mix(c, highlight_color.rgb, cd.a * ring * 0.6);
			EMISSION += highlight_color.rgb * cd.a * ring * 0.22;
		}
	}
	// contact darkening along the walls (measured from the board's edges)
	float ao = 1.0;
	ao *= 1.0 - wall_ao.x * falloff(max(q.y, 0.0), wall_ao_reach);
	ao *= 1.0 - wall_ao.y * falloff(max(size.y - q.y, 0.0), wall_ao_reach);
	ao *= 1.0 - wall_ao.z * falloff(max(q.x, 0.0), wall_ao_reach);
	ao *= 1.0 - wall_ao.w * falloff(max(size.x - q.x, 0.0), wall_ao_reach);
	vec2 wq = q + board_rect.xy;
	for (int i = 0; i < stone_count; i++) {
		vec4 s = stones[i];
		float dist = length(wq - s.xy) - s.z;
		ao *= 1.0 - s.w * falloff(max(dist, 0.0), stone_ao_reach);
	}
	// down in the joints: the stones' sides darken toward the mortar bed
	ao *= mix(joint_ao, 1.0, smoothstep(mortar_y, mortar_y + 0.04, wpos.y));
	// stage light: the board's middle reads a touch brighter than its edges
	vec2 sp = (q - size * 0.5) / (size * 0.5);
	ao *= 1.0 - edge_dim * smoothstep(0.35, 1.1, length(sp * vec2(0.9, 1.0)));
	ALBEDO = c * ao;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
}

// Cloud shadows only dim the sun (and the sky fill), never the braziers. The
// mask is rebuilt here from the fragment's world position, texel-stepped:
// values written in fragment() never reach light() in the Compatibility renderer.
float cloud_sun(vec3 w) {
	vec2 q = (floor(w.xz * texels) + 0.5) / texels;
	vec2 cp = q * cloud_scale + TIME * cloud_wind;
	float nn = vnoise(cp) * 0.65 + vnoise(cp * 2.1 + 7.3) * 0.35;
	return 1.0 - cloud_shadow * smoothstep(0.42, 0.72, nn);
}

void light() {
	float ndl = clamp(dot(NORMAL, LIGHT), 0.0, 1.0);
	float sun = (LIGHT_IS_DIRECTIONAL && cloud_shadow > 0.0) ? cloud_sun(wpos) : 1.0;
	DIFFUSE_LIGHT += ATTENUATION * LIGHT_COLOR * ndl * sun / PI;
}
