// Pixel-art water for streams and ponds: tiled water texture scrolling with
// the flow, pixel-quantized ripples, darker deep middle, foamy banks and
// sun glints. UV.x runs across the stream (0..1), UV.y along it (world units).
shader_type spatial;
render_mode cull_disabled, depth_draw_opaque;

uniform sampler2D water_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform vec2 tex_size = vec2(64.0, 64.0);
uniform float texels_per_unit = 24.0;
uniform vec4 shallow : source_color = vec4(0.30, 0.58, 0.62, 1.0);
uniform vec4 deep : source_color = vec4(0.10, 0.24, 0.34, 1.0);
uniform vec4 foam : source_color = vec4(0.86, 0.95, 0.92, 1.0);
uniform float flow_speed = 0.35;
uniform bool radial = false;  // ponds: UV is centered (0.5, 0.5)
uniform float glint = 1.0;

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(41.3, 289.1))) * 43758.5453);
}

void fragment() {
	vec2 texel = floor(wpos.xz * texels_per_unit);
	vec2 flow = radial ? vec2(0.12, 0.07) : vec2(0.0, -flow_speed);
	vec2 uv = (texel / texels_per_unit + flow * TIME) * texels_per_unit / tex_size;
	vec3 base = texture(water_tex, uv).rgb;
	float edge;
	if (radial) {
		edge = clamp(1.0 - length(UV - 0.5) * 2.0, 0.0, 1.0);
	} else {
		edge = clamp(1.0 - abs(UV.x - 0.5) * 2.0, 0.0, 1.0);
	}
	vec3 col = mix(shallow.rgb, deep.rgb, smoothstep(0.1, 0.85, edge));
	col = mix(col, base, 0.45);
	// Foam band along the banks, animated and pixel-dithered.
	float f = step(edge, 0.12 + 0.05 * sin(TIME * 2.0 + texel.y * 0.35 + texel.x * 0.2));
	col = mix(col, foam.rgb, f * 0.85);
	// Sparkling glints
	float g = step(0.995, hash(texel + floor(TIME * 3.0)));
	col += vec3(g) * glint * (1.0 - f);
	ALBEDO = col;
	ROUGHNESS = 0.25;
	SPECULAR = 0.6;
	EMISSION = vec3(g) * 0.6 * glint;
}
