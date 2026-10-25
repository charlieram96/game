"""Fitted palettes of the HD sprite sheets (tools/art_forge; written by `keys.py palette`).

Each HD sheet (tools/art_forge/animate.py) is painted with its own palette,
fitted to its key paintings (k-means in OKLab) and maybe graded afterwards:
ramps `hd_<sheet>_<i>`, each dark -> light. They are kept apart from the master
palette (palette.py), so the other forges' nearest-colour snapping and
`palette.all_colors()` never change when a sheet is refitted. The sheet
validator accepts a sheet's own `hd_<sheet>_*` colours on top of the master
palette.
"""

from __future__ import annotations

from .palette import hex_to_rgba

_RAMPS_HEX: dict[str, list[str]] = {
    # >>> art_forge HD sheet palettes (tools/art_forge/keys.py palette; do not edit by hand)
    "hd_stoneback_0": ["#d8550e"],
    "hd_stoneback_1": ["#2b190e", "#3b2414", "#4a2e1a", "#583820", "#674326", "#764e2d", "#865a34", "#95683c", "#a67746", "#b98752", "#d1985d", "#e5ad66", "#efc693", "#ebdac6"],
    "hd_stoneback_2": ["#877957", "#eedf37"],
    "hd_stoneback_3": ["#162208", "#24340b", "#31450e", "#3f5510", "#506812", "#647b14", "#7b8f18", "#94a31b", "#afba1f"],
    "hd_stoneback_4": ["#120e17", "#181214", "#1e1b22", "#28252c", "#322f36", "#3b373f", "#423e47", "#494550", "#504d5a", "#585563", "#615e6d", "#6a6876", "#74727e", "#7e7c86", "#8a878e", "#949196", "#a09c9d", "#afa9a8", "#c9beb7", "#fbf5e7"],
    "hd_emberlyn_0": ["#2b1a15", "#3a1f16", "#472519", "#53291b", "#5f2f1d", "#68321f", "#6f3520", "#793922", "#823d24", "#8c4226", "#944829", "#9e4d2c", "#c13716", "#e34915", "#f26211"],
    "hd_emberlyn_1": ["#7d5339", "#a7532e", "#936644", "#b05a31", "#b86034", "#a5764f", "#c06637", "#c66d3a", "#cc743c", "#b6865a", "#d17a3f", "#d58242", "#f97c11", "#d88745", "#c59666", "#e18f45", "#d3a573", "#fba51d", "#ecbb7b"],
    "hd_emberlyn_2": ["#fcbd2a", "#f6cb8d", "#fdd344", "#fcdca4", "#fde387", "#fdebbe"],
    "hd_emberlyn_3": ["#0c0911", "#1d1513", "#2b2522", "#372f2c", "#463b36", "#554842", "#62554f", "#73625b"],
    "hd_training_totem_0": ["#7b2010", "#962511", "#b12f14", "#ca441b", "#dc6124"],
    "hd_training_totem_1": ["#261709", "#301d0f", "#3e2411", "#4c2b16", "#5b2d15", "#61381b", "#723818", "#6d4b28", "#81421b", "#904c1f", "#7e5a30", "#9f5925", "#8d6739", "#96703f", "#ae672c", "#a37840", "#bc7735", "#ac844c", "#ba8d4c", "#cb873c"],
    "hd_training_totem_2": ["#997c53", "#b19467", "#c39858", "#d09f56", "#c2a677", "#d6ac65", "#cfb485", "#deb872", "#dac193", "#e7c683", "#e6ce9f", "#f1d599", "#f0dcb3", "#f4e7cb", "#fbeabe"],
    "hd_explorer_0": ["#721813", "#992219", "#bc3220", "#dd4f2a"],
    "hd_explorer_1": ["#381e12", "#462616", "#522d19", "#60351c", "#6c3b1f", "#794222", "#864b24", "#925328", "#9e5b2b", "#866c57", "#ad642f", "#b5733e", "#c67c3c", "#b69671", "#db8944", "#dfa15e", "#ecac5c", "#dbbd96"],
    "hd_explorer_2": ["#fbd16b", "#f3e3c5"],
    "hd_explorer_3": ["#113a37", "#144a47", "#135653", "#186461", "#187170", "#237e7b", "#1e8b8a", "#2e9690", "#57a796"],
    "hd_explorer_4": ["#120e17", "#1a1310", "#281812", "#0f2523", "#2c2522", "#362f2d", "#443c3a", "#534843", "#67574e"],
    "hd_corin_0": ["#200f09", "#301509", "#431c0c", "#55230e", "#66290f", "#862012", "#a12a13", "#c3281c", "#b6400e", "#cf520f", "#df3921"],
    "hd_corin_1": ["#743411", "#833d13", "#914714", "#9f5018", "#ab5a1a", "#b66621", "#c16f1e", "#cd781b", "#e56617", "#d9841c", "#f2811b", "#e29317", "#f29d20"],
    "hd_corin_2": ["#fab537", "#fdd06a"],
    "hd_corin_3": ["#165f2a", "#47b152"],
    "hd_corin_4": ["#141e2f", "#162a52", "#1c396d", "#254886", "#2f599c", "#416eb0", "#6a8fc2"],
    "hd_corin_5": ["#120e17", "#303339", "#44474e", "#5a5c63", "#6c6e73", "#8a8b8f", "#b0bbc9", "#f4eede"],
    "hd_villager_baker_0": ["#1e0b07", "#271009", "#360d08", "#2f170e", "#3a1b10", "#46100b", "#462012", "#56120d", "#522515", "#64140e", "#602c18", "#731710", "#821a11", "#71351c", "#931e13", "#854021", "#a42417", "#9b4b26", "#b62c1c", "#c83924", "#d64529", "#e15331", "#e9613a"],
    "hd_villager_baker_1": ["#5b483d", "#705a4c", "#856c5a", "#af5a30", "#9a7e68", "#c76e3d", "#ad8f77", "#e18751", "#c0a38a", "#f1a26a", "#d4b89e", "#fabd85", "#e3cab0", "#f0dbc2"],
    "hd_villager_baker_2": ["#120e17", "#392a24", "#463831", "#fcf0de"],
    "hd_villager_farmer_0": ["#27170b", "#342113", "#472512", "#592d16", "#6e381b", "#814621", "#965326", "#a8602c", "#987b55", "#ba6d33", "#c97d3c", "#d59048", "#e2a055", "#eab161"],
    "hd_villager_farmer_1": ["#af9167", "#c4a87c", "#d7be91", "#f2c171", "#e8d5a9", "#f9d186", "#fcdd98", "#f9eab7", "#fdf5d2"],
    "hd_villager_farmer_2": ["#081906", "#0d250b", "#163612", "#1c4516", "#24531b", "#2a621e", "#326f22", "#3d7d28", "#438929", "#519830", "#60a837"],
    "hd_villager_farmer_3": ["#120e17", "#3a342a", "#4b443b", "#5b554e", "#73685b", "#838382", "#a6a5a4", "#cccac9", "#fdfbf0"],
    "hd_hesper_0": ["#954773", "#a24c7f", "#ab5681", "#c0688f"],
    "hd_hesper_1": ["#2d191a", "#3d2013"],
    "hd_hesper_2": ["#3b2135", "#4e2443", "#592a4b", "#662d55", "#74335f", "#873b70", "#8e3f72"],
    "hd_hesper_3": ["#4d2917", "#5e321b", "#6f3b1f", "#804523", "#905029", "#a05b2f", "#b06635", "#c0723d", "#cf7f45", "#dd8e51", "#e89d5e", "#efaf79", "#f4c08c"],
    "hd_hesper_4": ["#a38c6a", "#f7b448", "#fcd46e", "#fadca8"],
    "hd_hesper_5": ["#120e17", "#211315", "#494450", "#605a67", "#756f7b", "#89848e", "#9c979e", "#afa9ac", "#bfbbbe", "#d0cccc", "#e2dedb", "#faf5e5"],
    "hd_mossling_0": ["#cd4a4e", "#ec6565", "#f69586"],
    "hd_mossling_1": ["#50612b", "#677730", "#809136", "#64a537", "#7aaf3d", "#86b73f", "#91bf41", "#a2c949", "#bbd559", "#caeeb6"],
    "hd_mossling_2": ["#092415", "#0d311c", "#113b1f", "#1e4928", "#2b5630", "#25672a", "#2e772d", "#277558", "#328462", "#3c8632", "#328e67", "#499235", "#3c9c70", "#559c35", "#52a777", "#51af7d", "#60b882", "#65c088", "#70c691", "#81c38e", "#81d094", "#a6dfa2"],
    "hd_mossling_3": ["#24654e"],
    "hd_mossling_4": ["#120e17", "#403031", "#f9faf7"],
    "hd_lanternmoth_0": ["#b27a92"],
    "hd_lanternmoth_1": ["#432922"],
    "hd_lanternmoth_2": ["#412879", "#5239a2", "#67428a", "#664bb8", "#7d5ec8", "#9171db", "#9d81e6", "#aa8cea", "#c5a8f2"],
    "hd_lanternmoth_3": ["#211321", "#2b182a", "#381c33", "#43203c", "#4e2444", "#59294c", "#642c55", "#6a325a", "#753a65", "#864470", "#964f7e", "#a25d88"],
    "hd_lanternmoth_4": ["#633c26", "#81532e", "#8e6d50", "#aa681b", "#a4835e", "#ca8425", "#b7966f", "#cbab80"],
    "hd_lanternmoth_5": ["#e2a030", "#dcbf92", "#f7c342", "#ecd3a5", "#fde262", "#f9e9c2", "#fef29e", "#fdf6d9"],
    "hd_lanternmoth_6": ["#120e17"],
    "hd_sigilbinder_0": ["#311123", "#4e1c2f", "#6a253e", "#8c2d4d", "#b42a51", "#bd5669", "#da305d", "#eb456c", "#f45d7b", "#cf8990", "#f8758a", "#fa8e9b"],
    "hd_sigilbinder_1": ["#fba5aa", "#fbc5c1"],
    "hd_sigilbinder_2": ["#302c3d", "#443c53"],
    "hd_sigilbinder_3": ["#580a53", "#413343", "#4b374a", "#513c51", "#5a4156"],
    "hd_sigilbinder_4": ["#120e17", "#141314", "#19161e", "#191719", "#1d1a20", "#201e23", "#252028", "#29242d", "#302731", "#2c2838", "#312c34", "#362a37", "#3a2e3b", "#473d49", "#4b414e", "#564e5d"],
    # <<< art_forge HD sheet palettes
}

RAMPS: dict[str, list[tuple[int, int, int, int]]] = {
    name: [hex_to_rgba(c) for c in colors] for name, colors in _RAMPS_HEX.items()
}


def sheet_ramps(sheet: str) -> list[str]:
    """The ramp names of one sheet's palette, in order."""
    return sorted((n for n in RAMPS if n.startswith(f"hd_{sheet}_") and n[len(f"hd_{sheet}_"):].isdigit()),
                  key=lambda n: int(n.rsplit("_", 1)[1]))


def sheet_colors(sheet: str) -> list[tuple[int, int, int, int]]:
    """Every colour of one sheet's palette."""
    return [c for n in sheet_ramps(sheet) for c in RAMPS[n]]
