// Ground ring under a creature: team colour + an angular stamina gauge,
// a facing notch (aim direction) and dash-cost tick marks. While a dash is
// aimed, the stretch it would spend blinks (or, if stamina is short, the
// missing stretch blinks red).
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_mix;

uniform vec4 team_color : source_color = vec4(0.3, 0.85, 0.9, 1.0);
uniform vec4 gauge_color : source_color = vec4(0.5, 0.9, 1.0, 1.0);
uniform vec4 empty_color : source_color = vec4(0.1, 0.1, 0.15, 1.0);
uniform float fill : hint_range(0.0, 1.0) = 1.0;
uniform float facing_angle = 0.0;  // radians, 0 = +X, increasing toward +Z
uniform float ticks = 0.0;  // number of dash-cost segments
uniform float opacity = 0.8;
uniform float pulse = 0.0;
uniform float pixel_grid = 48.0;
// Gauge stretch to highlight (0..1, same scale as fill); spend_to < 0 = none.
uniform float spend_from = 0.0;
uniform float spend_to = -1.0;
uniform vec4 spend_color : source_color = vec4(1.0, 0.98, 0.88, 1.0);

void fragment() {
	vec2 p = (floor((UV - 0.5) * pixel_grid) + 0.5) / pixel_grid * 2.0;
	float r = length(p);
	float ang = atan(p.y, p.x);
	float outer = step(r, 1.0) * step(0.82, r);
	float gauge = step(r, 0.78) * step(0.66, r);
	if (outer + gauge < 0.5) {
		// Facing notch just outside the ring.
		float da = abs(mod(ang - facing_angle + PI, TAU) - PI);
		if (r < 1.0 && r > 0.6 && da < 0.18) {
			ALBEDO = team_color.rgb * 1.3;
			ALPHA = opacity;
		} else {
			discard;
		}
	} else {
		// Gauge fills clockwise from the top (north).
		float t = mod(-(ang + PI * 0.5) + TAU * 2.0, TAU) / TAU;
		t = 1.0 - t;
		vec3 col = team_color.rgb;
		float a = opacity * (0.75 + 0.25 * pulse);
		if (gauge > 0.5) {
			col = t <= fill ? gauge_color.rgb : empty_color.rgb;
			if (spend_to >= 0.0 && t > spend_from && t <= spend_to) {
				float blink = 0.5 + 0.5 * sin(TIME * 14.0);
				col = mix(col, spend_color.rgb, 0.45 + 0.5 * blink);
			}
			if (ticks > 0.5) {
				float seg = fract(t * ticks);
				if (seg < 0.04 || seg > 0.96) {
					col *= 0.35;
				}
			}
		}
		ALBEDO = col;
		ALPHA = a;
	}
}
