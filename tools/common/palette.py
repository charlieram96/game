"""Shared Wildbound master palette.

Every generated sprite, texture, effect and icon draws from these ramps so the
whole game reads as one art direction. Ramps run darkest -> lightest and are
hue-shifted: shadows lean cool/purple, highlights lean warm/yellow.

Light direction convention for all baked shading: key light from the UPPER-LEFT
of the image (toward the viewer), so lit edges are top/left, shadowed edges are
bottom/right.

Outline convention: 1px "selective" outlines using the darkest shade of the
local material ramp (or INK for silhouettes against busy backgrounds). Never
pure #000000.
"""

from __future__ import annotations


def hex_to_rgba(h: str, a: int = 255) -> tuple[int, int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


_RAMPS_HEX: dict[str, list[str]] = {
    # Neutrals and outlines
    "ink": ["#120e17", "#1f1826", "#2f2538", "#43364d"],
    "stone": ["#262734", "#3d3f4f", "#5a5c6d", "#7d8090", "#a6a8b2", "#d2d3d6"],
    "stone_warm": ["#2d2622", "#4a3f37", "#6b5d50", "#8f8070", "#b5a794", "#dacfbd"],
    "earth": ["#2a1b18", "#472c22", "#6a4330", "#8e5e3d", "#b38452", "#d8ad78"],
    "sand": ["#5f4630", "#836343", "#a9855a", "#cbab76", "#e6cf9c", "#f6ecc8"],
    "wood": ["#2b1a15", "#48291c", "#683c25", "#8a5530", "#aa7240", "#c99459"],
    "wood_grey": ["#2b2827", "#45403c", "#625a52", "#827869", "#a39883"],
    # Vegetation
    "leaf": ["#11231c", "#1a3828", "#255432", "#36723a", "#4f9142", "#7cb24a", "#b3d465"],
    "leaf_autumn": ["#3a1a14", "#6a2d1a", "#9a4a1f", "#c46e25", "#e0993a", "#f2c45e"],
    "moss": ["#20301d", "#334826", "#4c6530", "#6b843c", "#91a54c", "#bcc66a"],
    "glow_moss": ["#16302c", "#1f5047", "#2f7a62", "#4ea67a", "#86d293", "#cdf3b5"],
    "bark": ["#1e1512", "#33231b", "#4b3326", "#654634", "#7f5c45"],
    # Water and sky
    "water": ["#0f1f30", "#143149", "#1b4a66", "#286a83", "#438f9e", "#7bbfc0", "#c6ecdf"],
    "sky_day": ["#5b8fc4", "#7fb0dc", "#a9cfe9", "#d6ecf5"],
    "sky_dusk": ["#3b2a52", "#7a3f63", "#c45f5c", "#ec955c", "#f7cf80"],
    "night": ["#0a0d1c", "#121a33", "#1c2a4d", "#2c4170", "#4a6596", "#8aa5c9"],
    # Elements and magic
    "ember": ["#3a1116", "#691d1b", "#a1301c", "#d1541e", "#ef8829", "#f8be47", "#fff0a3"],
    "aether": ["#1b1438", "#2e2163", "#47359a", "#6a55c9", "#9a86e6", "#cdbff7", "#f3eeff"],
    "sigil": ["#1d0b1e", "#3d1238", "#6d1b52", "#a8285e", "#e0466a", "#ff8c96"],
    "gold": ["#3b2410", "#6b4314", "#a06a1a", "#cf9a2a", "#eec657", "#fff0a0"],
    # Creature fur / hide
    "fur_russet": ["#36191a", "#5a2a22", "#863f29", "#b05d33", "#d08645", "#e8b26c"],
    "cream": ["#6f5a49", "#9c8268", "#c5ae8d", "#e4d0ad", "#f8eed7"],
    "soot": ["#16121a", "#272029", "#3b313c", "#524652"],
    # People
    "skin_light": ["#4a2a24", "#7a4636", "#a9684d", "#cf8f6c", "#ebb995", "#f8dcc2"],
    "skin_tan": ["#3c2219", "#643826", "#8f5534", "#b5774a", "#d39e6d", "#ebc497"],
    "skin_deep": ["#24130f", "#3f241a", "#5c3726", "#7b4c33", "#9a6644", "#b98458"],
    "hair_brown": ["#1d120f", "#33201a", "#4e3125", "#6d4632", "#8d5e40"],
    "hair_copper": ["#3a140f", "#65231a", "#933a21", "#bf5a2a", "#e0843b", "#f2ad5c"],
    "hair_grey": ["#2f2c33", "#4f4b55", "#75717d", "#9e9aa5", "#c9c6cf", "#efedf2"],
    "hair_black": ["#0f0d14", "#1c1924", "#2c2836", "#403a4d"],
    # Cloth
    "cloth_teal": ["#0f2629", "#173f42", "#1f5a5a", "#2c7a72", "#46998a", "#73b9a2"],
    "cloth_plum": ["#1f0f20", "#3a1a37", "#57274f", "#753869", "#944e83", "#b36e9f"],
    "cloth_mustard": ["#3b2a0f", "#644716", "#8f681f", "#b88c2c", "#d8b244", "#efd27a"],
    "cloth_red": ["#2e0e12", "#561a1b", "#822722", "#ab3a2b", "#cf5a3c", "#e88a5c"],
    "cloth_blue": ["#0f1630", "#18254d", "#243a70", "#33548f", "#4b73ad", "#7499c8"],
    "cloth_cream": ["#5e5040", "#857360", "#ab9a80", "#cdbfa3", "#e8dec8", "#faf6ec"],
    "cloth_green": ["#122012", "#1d361d", "#2b4f27", "#3e6a33", "#588a45", "#7eab5f"],
    "leather": ["#24140f", "#3d2418", "#5a3622", "#7a4b2e", "#9b653d", "#bb8653"],
    "metal": ["#1f2226", "#363b42", "#525963", "#737b86", "#9aa3ad", "#c9d0d6"],
    # HD (half-step) creature ramps for 2x sprites: every original shade i sits at
    # index 2*i with an OKLab midpoint between neighbours (softer multi-shade
    # ramps, same colours and hue shift as the base ramps above).
    "fur_russet_hd": ["#36191a", "#48211e", "#5a2a22", "#703426", "#863f29", "#9b4e2e", "#b05d33", "#c0713c",
                      "#d08645", "#dc9c59", "#e8b26c"],
    "cream_hd": ["#6f5a49", "#856e58", "#9c8268", "#b0987a", "#c5ae8d", "#d4bf9d", "#e4d0ad", "#eedfc2", "#f8eed7"],
    "soot_hd": ["#16121a", "#1e1921", "#272029", "#312832", "#3b313c", "#463b47", "#524652"],
    "stone_hd": ["#262734", "#313341", "#3d3f4f", "#4b4d5e", "#5a5c6d", "#6b6e7e", "#7d8090", "#9194a1", "#a6a8b2",
                 "#bcbdc4", "#d2d3d6"],
    "stone_warm_hd": ["#2d2622", "#3b322c", "#4a3f37", "#5a4e43", "#6b5d50", "#7d6e60", "#8f8070", "#a29382",
                      "#b5a794", "#c7bba8", "#dacfbd"],
    "moss_hd": ["#20301d", "#293c22", "#334826", "#3f562b", "#4c6530", "#5b7436", "#6b843c", "#7e9444", "#91a54c",
                "#a6b55b", "#bcc66a"],
    "glow_moss_hd": ["#16302c", "#1b4039", "#1f5047", "#276554", "#2f7a62", "#3e906e", "#4ea67a", "#6bbc86", "#86d293",
                     "#aae3a4", "#cdf3b5"],
    # HD ramps for 2x props (training totem)
    "wood_hd": ["#2b1a15", "#392119", "#48291c", "#583221", "#683c25", "#79482a", "#8a5530", "#9a6338", "#aa7240",
                "#b9834c", "#c99459"],
    "sand_hd": ["#5f4630", "#715439", "#836343", "#96744e", "#a9855a", "#ba9868", "#cbab76", "#d8bd89", "#e6cf9c",
                "#eeddb2", "#f6ecc8"],
    "leather_hd": ["#24140f", "#301c13", "#3d2418", "#4b2d1d", "#5a3622", "#6a4028", "#7a4b2e", "#8a5835", "#9b653d",
                   "#ab7548", "#bb8653"],
    "cloth_cream_hd": ["#5e5040", "#716150", "#857360", "#988670", "#ab9a80", "#bcac91", "#cdbfa3", "#daceb5", "#e8dec8",
                       "#f1eada", "#faf6ec"],
    "cloth_red_hd": ["#2e0e12", "#421417", "#561a1b", "#6c201f", "#822722", "#963027", "#ab3a2b", "#bd4a33", "#cf5a3c",
                     "#dc724c", "#e88a5c"],
    "earth_hd": ["#2a1b18", "#38231d", "#472c22", "#583729", "#6a4330", "#7c5036", "#8e5e3d", "#a07147", "#b38452",
                 "#c59865", "#d8ad78"],
    # UI
    "ui_parchment": ["#5a4632", "#8a6e4e", "#bfa27a", "#e3cfa6", "#f5ead0", "#fffaf0"],
    "ui_hp": ["#3d0f17", "#7a1d27", "#c23a3a", "#ef6a4f", "#ffa178"],
    "ui_stamina": ["#0f2a3d", "#1a4d6b", "#2a7aa0", "#45a8c8", "#86d6e4"],
    "ui_focus": ["#1e2a10", "#3a5a18", "#64921f", "#9ccc3a", "#d4f07a"],
}

RAMPS: dict[str, list[tuple[int, int, int, int]]] = {
    name: [hex_to_rgba(c) for c in colors] for name, colors in _RAMPS_HEX.items()
}

TRANSPARENT = (0, 0, 0, 0)


def ramp(name: str, index: int, alpha: int = 255) -> tuple[int, int, int, int]:
    """Return shade `index` of ramp `name`. Negative indices count from the light end."""
    colors = RAMPS[name]
    r, g, b, _ = colors[max(-len(colors), min(len(colors) - 1, index))]
    return (r, g, b, alpha)


def ramp_len(name: str) -> int:
    return len(RAMPS[name])


def darkest(name: str) -> tuple[int, int, int, int]:
    return RAMPS[name][0]


def lightest(name: str) -> tuple[int, int, int, int]:
    return RAMPS[name][-1]


def all_colors() -> list[tuple[int, int, int, int]]:
    out: list[tuple[int, int, int, int]] = []
    for colors in RAMPS.values():
        out.extend(colors)
    return out


def nearest(color: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Snap an arbitrary RGBA color to the closest master-palette color (alpha kept)."""
    r, g, b, a = color
    if a == 0:
        return TRANSPARENT
    best = None
    best_d = 1 << 30
    for c in all_colors():
        d = (c[0] - r) ** 2 * 3 + (c[1] - g) ** 2 * 4 + (c[2] - b) ** 2 * 2
        if d < best_d:
            best_d = d
            best = c
    assert best is not None
    return (best[0], best[1], best[2], a)
