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
shader_type spatial;
render_mode cull_disabled, depth_draw_opaque;

global uniform float sprite_stretch;
global uniform vec2 occluder_uv;
global uniform float occluder_z;
global uniform float occluder_active;

uniform sampler2D sheet : source_color, filter_linear, repeat_disable;
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
uniform float dissolve : hint_range(0.0, 1.0) = 0.0;
uniform float emission_threshold = 0.84;
uniform float emission_strength = 0.0;
uniform float shade_floor = 0.62;
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
	if (upright) {
		vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), INV_VIEW_MATRIX[2].xyz));
		vec3 back = normalize(cross(right, vec3(0.0, 1.0, 0.0)));
		MODELVIEW_MATRIX = VIEW_MATRIX * mat4(vec4(right * scale.x, 0.0), vec4(0.0, scale.y, 0.0, 0.0), vec4(back * scale.z, 0.0), MODEL_MATRIX[3]);
	} else {
		MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0] * scale.x, INV_VIEW_MATRIX[1] * scale.y, INV_VIEW_MATRIX[2] * scale.z, MODEL_MATRIX[3]);
	}
	MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
}

vec4 sample_px(vec2 uv) {
	vec2 tex_px = uv * sheet_size;
	vec2 seam = floor(tex_px + 0.5);
	vec2 d = max(fwidth(tex_px), vec2(1e-4));
	tex_px = seam + clamp((tex_px - seam) / d, -0.5, 0.5);
	return texture(sheet, tex_px / sheet_size);
}

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void fragment() {
	vec4 c = sample_px(UV);
	vec3 col = c.rgb * modulate.rgb;
	float a = c.a * modulate.a;
	if (outline > 0.0 && a < 0.5) {
		vec2 t = 1.0 / sheet_size;
		float n = texture(sheet, UV + vec2(t.x, 0.0)).a + texture(sheet, UV - vec2(t.x, 0.0)).a
			+ texture(sheet, UV + vec2(0.0, t.y)).a + texture(sheet, UV - vec2(0.0, t.y)).a;
		if (n > 0.5) {
			col = outline_color.rgb;
			a = outline;
			EMISSION = outline_color.rgb * outline * 1.5;
		}
	}
	if (dissolve > 0.0) {
		vec2 cellp = floor(UV * sheet_size);
		if (hash(cellp) < dissolve) {
			a = 0.0;
		}
	}
	// See-through foliage: only in the main (perspective) pass, so shadows stay intact.
	if (can_occlude && occluder_active > 0.5 && v_perspective > 0.5 && v_origin_z > occluder_z + 0.35) {
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
	float bright = max(max(c.r, c.g), c.b);
	EMISSION += col * smoothstep(emission_threshold, 1.0, bright) * emission_strength + flash_color.rgb * flash * 0.5;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
	NORMAL = vec3(0.0, 0.0, 1.0);
}

void light() {
	float ndl = dot(NORMAL, LIGHT);
	float wrap = mix(shade_floor, 1.0, clamp(ndl * 0.5 + 0.5, 0.0, 1.0));
	DIFFUSE_LIGHT += ATTENUATION * LIGHT_COLOR * wrap / PI;
}
