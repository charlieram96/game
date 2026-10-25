// Pixel-art sprite on a billboarded quad (characters, kith, props, foliage).
//
// * Reads one frame of a sprite sheet (row-major grid).
// * Upright (Y-axis) billboard so sprites stand in the 3D world and sort
//   correctly against walls; height is stretched by 1/cos(camera pitch)
//   (global `sprite_stretch`) so they keep their drawn proportions.
// * "Smooth pixel" sampling: crisp texels at any (non-integer) scale with
//   1-screen-pixel anti-aliasing on texel edges, so pixels never shimmer.
// * Hit flash, outline glow, dithered dissolve, auto-emission for the
//   brightest pixels (embers, lanterns, eyes) so they bloom.
// * HD-2D lighting (sheets with a normal map): every texel is lit by the
//   scene's sun and point lights through its own normal (screen-aligned:
//   x right, y up, z toward the camera), with a soft wrap so the baked
//   shading never goes muddy, and a rim light on the edges that turn toward
//   a light (strongest for lights behind the sprite). The normal map's alpha
//   is an emission mask (255 = none, 128 = full glow), so only the pixels the
//   artist marked bloom. Sheets without a normal map render as before.
// * Shadows: the shadow pass orients the card like the main camera sees it
//   (MAIN_CAM_INV_VIEW_MATRIX), so a sprite casts the silhouette that is on
//   screen and never shadows itself; alpha scissor cuts the shape.
shader_type spatial;
render_mode cull_disabled, depth_draw_opaque;

global uniform float sprite_stretch;
global uniform vec2 occluder_uv;
global uniform float occluder_z;
global uniform float occluder_active;

uniform sampler2D sheet : source_color, filter_linear, repeat_disable;
// Optional normal map with the sheet's layout: rgb = normal * 0.5 + 0.5, a = 1 - emission / 2.
uniform sampler2D normal_sheet : filter_linear, repeat_disable;
uniform bool has_normal_map = false;
uniform vec2 sheet_size = vec2(48.0, 48.0);
uniform vec2 frame_size = vec2(48.0, 48.0);
uniform float columns = 1.0;
uniform float frame = 0.0;
uniform bool flip_h = false;
uniform vec2 pivot = vec2(24.0, 44.0);
uniform float pixel_size = 0.0416667;
uniform bool upright = true;
uniform vec4 modulate : source_color = vec4(1.0);
uniform vec4 flash_color : source_color = vec4(1.0, 1.0, 1.0, 1.0);
uniform float flash : hint_range(0.0, 1.0) = 0.0;
uniform vec4 outline_color : source_color = vec4(1.0, 0.95, 0.7, 1.0);
uniform float outline : hint_range(0.0, 1.0) = 0.0;
// Outline and dissolve grain in sheet texels per 24-px/unit sprite pixel, so
// HD sheets (48, 112 px/unit) keep the same world-space thickness.
uniform float outline_texels = 1.0;
uniform float dissolve : hint_range(0.0, 1.0) = 0.0;
uniform float emission_threshold = 0.84;
uniform float emission_strength = 0.0;
// Lowest diffuse response (light from behind the texel's normal).
uniform float shade_floor = 0.62;
// How far the normal map bends the light (0 = flat, as without a map).
uniform float normal_strength : hint_range(0.0, 1.0) = 1.0;
uniform float rim_strength : hint_range(0.0, 4.0) = 0.9;
uniform float rim_power : hint_range(0.5, 8.0) = 3.0;
uniform float sway = 0.0;  // foliage wind sway amplitude (pixels at the top)
uniform vec2 jitter = vec2(0.0);  // hitstop shake, in pixels
uniform bool instance_frame = false;  // MultiMesh: frame comes from INSTANCE_CUSTOM.r
uniform bool can_occlude = false;  // dither away when standing between camera and player

varying float v_height;
varying float v_origin_z;
varying float v_perspective;

void vertex() {
	v_origin_z = MODEL_MATRIX[3].z;
	v_perspective = PROJECTION_MATRIX[3][3] < 0.5 ? 1.0 : 0.0;
	vec2 px = (VERTEX.xy + vec2(0.5)) * frame_size;
	vec2 local = vec2(px.x - pivot.x, px.y - (frame_size.y - pivot.y)) + jitter;
	v_height = clamp(px.y / frame_size.y, 0.0, 1.0);
	if (sway > 0.0) {
		local.x += sin(TIME * 1.3 + MODEL_MATRIX[3].x * 0.7 + MODEL_MATRIX[3].z * 0.4) * sway * v_height * v_height;
	}
	local *= pixel_size;
	if (upright) {
		local.y *= max(sprite_stretch, 1.0);
	}
	VERTEX = vec3(local, 0.0);
	float f = floor((instance_frame ? INSTANCE_CUSTOM.r : frame) + 0.5);
	vec2 cell = vec2(mod(f, columns), floor(f / columns));
	vec2 uv = UV;
	if (flip_h) {
		uv.x = 1.0 - uv.x;
	}
	UV = (cell * frame_size + uv * frame_size) / sheet_size;
	vec3 scale = vec3(length(MODEL_MATRIX[0].xyz), length(MODEL_MATRIX[1].xyz), length(MODEL_MATRIX[2].xyz));
	// The main camera's basis in every pass: in the shadow pass the card keeps
	// the orientation the player sees, so its shadow matches the sprite.
	mat4 cam = MAIN_CAM_INV_VIEW_MATRIX;
	if (upright) {
		vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), cam[2].xyz));
		vec3 back = normalize(cross(right, vec3(0.0, 1.0, 0.0)));
		MODELVIEW_MATRIX = VIEW_MATRIX * mat4(vec4(right * scale.x, 0.0), vec4(0.0, scale.y, 0.0, 0.0), vec4(back * scale.z, 0.0), MODEL_MATRIX[3]);
	} else {
		MODELVIEW_MATRIX = VIEW_MATRIX * mat4(cam[0] * scale.x, cam[1] * scale.y, cam[2] * scale.z, MODEL_MATRIX[3]);
	}
	MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
}

// The texels a screen pixel covers, box-filtered: one bilinear tap at a
// remapped position gives the exact area average of a nearest-neighbour texture
// over a footprint up to one texel wide (crisp texels, a one-pixel blend on
// their seams). Magnified sprites take one such tap. Minified ones (the HD
// sheets, 112 texels per unit, on 1080p screens and phones) take four, each
// covering a quarter of the pixel's footprint: sharper than a bilinear point
// sample and steady in motion (no texels skipped as the sprite moves).
vec4 smooth_tap(sampler2D tex, vec2 tex_px, vec2 d) {
	vec2 seam = floor(tex_px + 0.5);
	return texture(tex, (seam + clamp((tex_px - seam) / d, -0.5, 0.5)) / sheet_size);
}

vec4 sample_px(sampler2D tex, vec2 uv) {
	vec2 tex_px = uv * sheet_size;
	vec2 fw = max(fwidth(tex_px), vec2(1e-4));
	if (max(fw.x, fw.y) <= 1.0) {
		return smooth_tap(tex, tex_px, fw);
	}
	vec2 q = fw * 0.25;
	vec2 d = min(fw * 0.5, vec2(1.0));
	return 0.25 * (smooth_tap(tex, tex_px + vec2(-q.x, -q.y), d) + smooth_tap(tex, tex_px + vec2(q.x, -q.y), d)
		+ smooth_tap(tex, tex_px + vec2(-q.x, q.y), d) + smooth_tap(tex, tex_px + vec2(q.x, q.y), d));
}

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void fragment() {
	vec4 c = sample_px(sheet, UV);
	vec3 col = c.rgb * modulate.rgb;
	float a = c.a * modulate.a;
	if (outline > 0.0 && a < 0.5 && !IN_SHADOW_PASS) {
		vec2 t = outline_texels / sheet_size;
		float n = texture(sheet, UV + vec2(t.x, 0.0)).a + texture(sheet, UV - vec2(t.x, 0.0)).a
			+ texture(sheet, UV + vec2(0.0, t.y)).a + texture(sheet, UV - vec2(0.0, t.y)).a;
		if (n > 0.5) {
			col = outline_color.rgb;
			a = outline;
			EMISSION = outline_color.rgb * outline * 1.5;
		}
	}
	if (dissolve > 0.0) {
		vec2 cellp = floor(UV * sheet_size / outline_texels);
		if (hash(cellp) < dissolve) {
			a = 0.0;
		}
	}
	// See-through foliage: only in the main (perspective) pass, so shadows stay intact.
	if (can_occlude && occluder_active > 0.5 && v_perspective > 0.5 && !IN_SHADOW_PASS && v_origin_z > occluder_z + 0.35) {
		vec2 d = (SCREEN_UV - occluder_uv) * vec2(VIEWPORT_SIZE.x / VIEWPORT_SIZE.y, 1.0);
		float r = length(d);
		if (r < 0.17) {
			float keep = smoothstep(0.08, 0.17, r);
			vec2 cell = floor(FRAGCOORD.xy / 2.0);
			float pattern = mod(cell.x + cell.y, 2.0) * 0.5 + 0.25;
			if (keep < pattern) {
				a = 0.0;
			}
		}
	}
	ALPHA = a;
	ALPHA_SCISSOR_THRESHOLD = 0.5;
	col = mix(col, flash_color.rgb, flash);
	ALBEDO = col;
	vec3 nrm = vec3(0.0, 0.0, 1.0);
	float glow = 0.0;
	if (has_normal_map) {
		vec4 nm = sample_px(normal_sheet, UV);
		vec3 m = nm.rgb * 2.0 - 1.0;
		if (flip_h) {
			m.x = -m.x;
		}
		nrm = normalize(mix(vec3(0.0, 0.0, 1.0), m, normal_strength));
		glow = clamp((1.0 - nm.a) * 2.0, 0.0, 1.0);
	} else {
		float bright = max(max(c.r, c.g), c.b);
		glow = smoothstep(emission_threshold, 1.0, bright);
	}
	EMISSION += col * glow * emission_strength + flash_color.rgb * flash * 0.5;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
	NORMAL = nrm;
}

void light() {
	float ndl = dot(NORMAL, LIGHT);
	float wrap = mix(shade_floor, 1.0, clamp(ndl * 0.5 + 0.5, 0.0, 1.0));
	DIFFUSE_LIGHT += ATTENUATION * LIGHT_COLOR * wrap / PI;
	// Rim: texels near the silhouette (normal turned sideways, away from the
	// camera) whose normal leans toward the light's side; lights behind the
	// sprite (LIGHT.z < 0) give the brightest rim. Zero for flat normals.
	float edge = pow(clamp(length(NORMAL.xy), 0.0, 1.0), rim_power);
	float side = length(LIGHT.xy);
	if (rim_strength > 0.0 && edge > 1e-3 && side > 1e-3) {
		float toward = max(dot(normalize(NORMAL.xy), LIGHT.xy / side), 0.0);
		float behind = mix(0.45, 1.0, clamp(0.5 - LIGHT.z, 0.0, 1.0));
		float rim = edge * toward * behind * rim_strength;
		DIFFUSE_LIGHT += ATTENUATION * LIGHT_COLOR * rim * 0.6 / PI;
		SPECULAR_LIGHT += ATTENUATION * LIGHT_COLOR * rim * 0.08;
	}
}
