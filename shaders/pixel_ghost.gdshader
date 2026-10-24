// Translucent silhouette of a pixel sprite, for the dash preview's ghost and
// for dash afterimages: the tint with a little of the sprite's own shading,
// a brighter rim, smooth opacity. Same billboard transform as
// pixel_sprite.gdshader (it takes the same sheet parameters).
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_mix, shadows_disabled, fog_disabled;

global uniform float sprite_stretch;

uniform sampler2D sheet : source_color, filter_nearest, repeat_disable;
uniform vec2 sheet_size = vec2(48.0, 48.0);
uniform vec2 frame_size = vec2(48.0, 48.0);
uniform float columns = 1.0;
uniform float frame = 0.0;
uniform bool flip_h = false;
uniform vec2 pivot = vec2(24.0, 44.0);
uniform float pixel_size = 0.0416667;
uniform bool upright = true;
// Rim thickness in sheet texels (2 on 48 px/unit sheets, like the outline).
uniform float outline_texels = 1.0;
uniform vec4 tint : source_color = vec4(0.4, 0.95, 1.0, 1.0);
uniform vec4 rim_color : source_color = vec4(1.0, 1.0, 1.0, 1.0);
uniform float opacity = 0.5;
// How much of the sprite's own shading shows through the tint.
uniform float detail = 0.45;
// Compensates the scene tonemapper so the tint stays vivid.
uniform float energy = 1.4;

void vertex() {
	vec2 px = (VERTEX.xy + vec2(0.5)) * frame_size;
	vec2 local = vec2(px.x - pivot.x, px.y - (frame_size.y - pivot.y)) * pixel_size;
	if (upright) {
		local.y *= max(sprite_stretch, 1.0);
	}
	VERTEX = vec3(local, 0.0);
	float f = floor(frame + 0.5);
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
}

void fragment() {
	vec4 c = texture(sheet, UV);
	if (c.a < 0.5) {
		discard;
	}
	vec2 t = outline_texels / sheet_size;
	float n = min(min(texture(sheet, UV + vec2(t.x, 0.0)).a, texture(sheet, UV - vec2(t.x, 0.0)).a),
		min(texture(sheet, UV + vec2(0.0, t.y)).a, texture(sheet, UV - vec2(0.0, t.y)).a));
	float rim = 1.0 - step(0.5, n);
	float luma = dot(c.rgb, vec3(0.299, 0.587, 0.114));
	vec3 col = tint.rgb * mix(1.0, 0.5 + luma * 0.9, detail);
	col = mix(col, rim_color.rgb, rim * 0.75);
	ALBEDO = col * energy;
	ALPHA = clamp(opacity * (0.8 + 0.35 * rim), 0.0, 1.0);
}
