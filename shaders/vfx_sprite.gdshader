// Effects sprite: sheet frame on a camera-facing (or ground-flat) quad,
// unshaded, alpha or additive blending, optional screen-space rotation so
// projectiles and slashes point along their travel direction.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_mix;

uniform sampler2D sheet : source_color, filter_linear, repeat_disable;
uniform vec2 sheet_size = vec2(32.0, 32.0);
uniform vec2 frame_size = vec2(32.0, 32.0);
uniform float columns = 1.0;
uniform float frame = 0.0;
uniform vec2 pivot = vec2(16.0, 16.0);
uniform float pixel_size = 0.0416667;
uniform float rotation = 0.0;  // radians, in the billboard plane
uniform bool flat_on_ground = false;
uniform vec4 modulate : source_color = vec4(1.0);
uniform float additive_glow = 0.0;  // 0 = plain alpha, >0 brightens (fake additive)
uniform float scale = 1.0;

void vertex() {
	vec2 px = (VERTEX.xy + vec2(0.5)) * frame_size;
	vec2 local = vec2(px.x - pivot.x, px.y - (frame_size.y - pivot.y)) * pixel_size * scale;
	float c = cos(rotation);
	float s = sin(rotation);
	local = vec2(local.x * c - local.y * s, local.x * s + local.y * c);
	float f = floor(frame + 0.5);
	vec2 cell = vec2(mod(f, columns), floor(f / columns));
	UV = (cell * frame_size + UV * frame_size) / sheet_size;
	if (flat_on_ground) {
		// Lie on the XZ plane: local.x -> +X, local.y -> -Z (up in the image is north).
		VERTEX = vec3(local.x, 0.0, -local.y);
	} else {
		VERTEX = vec3(local, 0.0);
		MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
		MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
	}
}

vec4 sample_px(vec2 uv) {
	vec2 tex_px = uv * sheet_size;
	vec2 seam = floor(tex_px + 0.5);
	vec2 d = max(fwidth(tex_px), vec2(1e-4));
	tex_px = seam + clamp((tex_px - seam) / d, -0.5, 0.5);
	return texture(sheet, tex_px / sheet_size);
}

void fragment() {
	vec4 c = sample_px(UV) * modulate;
	if (c.a < 0.02) {
		discard;
	}
	ALBEDO = c.rgb * (1.0 + additive_glow);
	ALPHA = c.a;
}
