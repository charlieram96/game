// Procedural pixel-art flame on a camera-facing quad (arena braziers).
// The flame is evaluated on the shared 24-texels-per-unit grid: a teardrop
// silhouette swayed by rising value noise, cut into four ember-palette bands
// with a crisp alpha edge. Bright bands are pushed over 1.0 so they bloom.
// The quad's pivot is its bottom centre (QuadMesh centre_offset y = 0.5).
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque;

uniform vec2 quad_size = vec2(0.7, 1.0);  // world units (must match the mesh)
uniform float texels = 24.0;
uniform float seed = 0.0;
uniform float speed = 1.0;
uniform float intensity = 1.6;
uniform vec4 core : source_color = vec4(1.0, 0.941, 0.639, 1.0);   // ember 6
uniform vec4 hot : source_color = vec4(0.973, 0.745, 0.278, 1.0);  // ember 5
uniform vec4 warm : source_color = vec4(0.937, 0.533, 0.161, 1.0); // ember 4
uniform vec4 rim : source_color = vec4(0.82, 0.329, 0.118, 1.0);   // ember 3

void vertex() {
	vec3 sc = vec3(length(MODEL_MATRIX[0].xyz), length(MODEL_MATRIX[1].xyz), length(MODEL_MATRIX[2].xyz));
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0] * sc.x, INV_VIEW_MATRIX[1] * sc.y, INV_VIEW_MATRIX[2] * sc.z, MODEL_MATRIX[3]);
	MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
}

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(41.37, 289.13))) * 43758.5453);
}

float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = hash(i);
	float b = hash(i + vec2(1.0, 0.0));
	float c = hash(i + vec2(0.0, 1.0));
	float d = hash(i + vec2(1.0, 1.0));
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

void fragment() {
	vec2 grid = quad_size * texels;
	vec2 px = floor(vec2(UV.x, 1.0 - UV.y) * grid) + 0.5;  // y up, in texels
	float t = TIME * speed + seed * 13.0;
	float v = px.y / grid.y;  // 0 bottom .. 1 top
	float sway = (sin(v * 5.0 - t * 4.3 + seed) * 0.6 + sin(v * 9.0 - t * 7.1) * 0.35) * v * 1.6;
	float n = vnoise(vec2(px.x * 0.45 + seed * 3.0, px.y * 0.32 - t * 6.0));
	float n2 = vnoise(vec2(px.x * 0.9 - seed, px.y * 0.6 - t * 9.0));
	float half_w = grid.x * 0.5 * pow(max(1.0 - v, 0.0), 0.75) * (0.82 + 0.18 * sin(t * 3.1 + seed));
	float dx = abs(px.x - grid.x * 0.5 - sway);
	float body = 1.0 - dx / max(half_w, 0.5);
	float heat = body * (1.15 - v * 0.65) + (n - 0.5) * 0.75 * (0.35 + v) + (n2 - 0.5) * 0.3;
	// detached licks near the tip
	heat -= smoothstep(0.55, 1.0, v) * (0.35 + 0.4 * n2);
	if (heat < 0.1) {
		discard;
	}
	vec3 c = rim.rgb;
	float glow = 1.0;
	if (heat > 0.78) {
		c = core.rgb;
		glow = 1.6;
	} else if (heat > 0.52) {
		c = hot.rgb;
		glow = 1.35;
	} else if (heat > 0.3) {
		c = warm.rgb;
		glow = 1.15;
	}
	ALBEDO = c * mix(1.0, intensity, (glow - 1.0) / 0.6);
}
