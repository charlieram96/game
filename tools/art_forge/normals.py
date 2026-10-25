"""Normal maps for pixel-art sprite frames (HD-2D lighting in pixel_sprite.gdshader).

The engine lights every texel through a screen-aligned normal (x right, y up,
z toward the camera). For painted or pixelized art there is no 3D model, so
the normal comes from what the frame shows:

1. **Silhouette inflation.** The opaque mask is blurred at several scales and
   the blurs are summed into a height field. Thick parts (the body) become
   high domes, thin parts (legs, ears, tail tips) small rounded ridges, and
   every edge slopes away, so the rim light finds the silhouette.
2. **Part creases.** Dark contour lines inside the silhouette (the art's own
   outlines between tail and body, legs and belly) are treated as part
   boundaries at a smaller scale, so overlapping parts read as separate forms.
3. **Surface detail.** A little of the albedo's high-passed luminance is
   embossed into the height, so fur clumps, stone plates and folds catch the
   light without turning into noise.

The normal is the gradient of that height. The map's alpha is an emission
mask: 255 = no glow, 128 = full glow (alpha never reaches 0, so the import's
alpha-border fix can't touch the normals).

Pure numpy (like the other forges): blurs are separable box-filter passes.
"""

from __future__ import annotations

import numpy as np

LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float32)


def _box1d(a: np.ndarray, r: int, axis: int) -> np.ndarray:
    if r <= 0:
        return a
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode="constant"), axis=axis, dtype=np.float64)
    n = a.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def blur(a: np.ndarray, sigma: float) -> np.ndarray:
    """Approximate Gaussian blur (three box passes per axis), zero outside the image."""
    if sigma <= 0:
        return a.astype(np.float32)
    # box radius for 3 passes with the given sigma
    r = max(1, int(round((np.sqrt(4.0 * sigma * sigma + 1.0) - 1.0) / 2.0)))
    out = a.astype(np.float32)
    for _ in range(3):
        out = _box1d(out, r, 0)
        out = _box1d(out, r, 1)
    return out


def contour_lines(rgb: np.ndarray, mask: np.ndarray, darkness: float = 0.62, max_luma: float = 0.32) -> np.ndarray:
    """Interior pixels that are much darker than their surroundings (drawn contour lines)."""
    luma = (rgb.astype(np.float32) / 255.0 * LUMA).sum(-1)
    local = blur(np.where(mask, luma, 0.0), 2.0) / np.maximum(blur(mask.astype(np.float32), 2.0), 1e-3)
    return mask & (luma < local * darkness) & (luma < max_luma)


def height_field(rgb: np.ndarray, mask: np.ndarray, scale: float = 1.0, detail: float = 0.9,
                 crease: float = 0.45, sigmas=(1.5, 3.0, 6.0, 12.0)) -> np.ndarray:
    """Height (in pixels, roughly) of every texel; `scale` stretches the blur radii for bigger sprites."""
    m = mask.astype(np.float32)
    h = np.zeros(mask.shape, dtype=np.float32)
    total = 0.0
    for s in sigmas:
        w = s  # bigger scales lift the body more
        h += w * blur(m, s * scale)
        total += w
    h *= (sigmas[-1] * scale) / total * 1.6
    if crease > 0:
        lines = contour_lines(rgb, mask)
        parts = (mask & ~lines).astype(np.float32)
        for s in sigmas[:2]:
            h += crease * s * (blur(parts, s * scale) - blur(m, s * scale)) * 2.0
    if detail > 0:
        luma = (rgb.astype(np.float32) / 255.0 * LUMA).sum(-1)
        luma = np.where(mask, luma, 0.0)
        fill = blur(luma, 1.2) / np.maximum(blur(m, 1.2), 1e-3)
        hp = np.where(mask, luma - blur(np.where(mask, luma, fill), 1.6), 0.0)
        h += detail * 4.0 * hp
    return h


def normals_from_height(h: np.ndarray, mask: np.ndarray, strength: float = 1.0, smooth: float = 0.7) -> np.ndarray:
    """Unit normals (H, W, 3), x right, y up, z out of the screen; flat outside the mask."""
    gx = np.zeros_like(h)
    gy = np.zeros_like(h)
    gx[:, 1:-1] = (h[:, 2:] - h[:, :-2]) * 0.5
    gy[1:-1, :] = (h[2:, :] - h[:-2, :]) * 0.5
    n = np.stack([-gx * strength, gy * strength, np.ones_like(h)], axis=-1)
    if smooth > 0:
        m = mask.astype(np.float32)
        wsum = np.maximum(blur(m, smooth), 1e-4)
        for c in range(2):
            n[..., c] = blur(np.where(mask, n[..., c], 0.0), smooth) / wsum
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    n[~mask] = (0.0, 0.0, 1.0)
    return n


def encode(normals: np.ndarray, glow: np.ndarray | None = None) -> np.ndarray:
    """RGBA uint8: rgb = n * 0.5 + 0.5, a = 255 - 127 * glow (never 0)."""
    out = np.empty(normals.shape[:2] + (4,), dtype=np.uint8)
    out[..., :3] = np.clip(np.round((normals * 0.5 + 0.5) * 255.0), 0, 255).astype(np.uint8)
    g = np.zeros(normals.shape[:2], dtype=np.float32) if glow is None else np.clip(glow, 0.0, 1.0)
    out[..., 3] = np.clip(np.round(255.0 - 127.0 * g), 128, 255).astype(np.uint8)
    return out


def glow_mask(rgb: np.ndarray, mask: np.ndarray, colors: list[tuple[int, int, int]] | None, weights: list[float] | None = None) -> np.ndarray:
    """Emission per texel: `colors` (exact palette colours) glow with their `weights` (default 1)."""
    g = np.zeros(mask.shape, dtype=np.float32)
    if not colors:
        return g
    weights = weights or [1.0] * len(colors)
    flat = rgb.reshape(-1, 3).astype(np.int32)
    key = (flat[:, 0] << 16) | (flat[:, 1] << 8) | flat[:, 2]
    lut = {(int(c[0]) << 16) | (int(c[1]) << 8) | int(c[2]): float(w) for c, w in zip(colors, weights)}
    vals = np.array([lut.get(int(k), 0.0) for k in np.unique(key)], dtype=np.float32)
    uniq, inv = np.unique(key, return_inverse=True)
    g = vals[inv].reshape(mask.shape)
    return np.where(mask, g, 0.0)


def frame_normal_map(rgba: np.ndarray, scale: float = 1.0, strength: float = 1.0, detail: float = 0.9, crease: float = 0.45,
                     glow_colors=None, glow_weights=None) -> np.ndarray:
    """The encoded normal map (H, W, 4) of one RGBA frame."""
    mask = rgba[..., 3] > 0
    rgb = rgba[..., :3]
    h = height_field(rgb, mask, scale=scale, detail=detail, crease=crease)
    n = normals_from_height(h, mask, strength=strength)
    g = glow_mask(rgb, mask, glow_colors, glow_weights)
    return encode(n, g)


def relight(rgba: np.ndarray, nmap: np.ndarray, light=(-0.5, 0.55, 0.65), color=(1.0, 0.95, 0.85), ambient=0.45,
            floor=0.62, rim=0.9, rim_power=2.2) -> np.ndarray:
    """Preview: the shader's lighting on the CPU (one light + ambient), for review sheets."""
    l = np.array(light, dtype=np.float32)
    l /= np.linalg.norm(l)
    n = nmap[..., :3].astype(np.float32) / 255.0 * 2.0 - 1.0
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-4)
    ndl = (n * l).sum(-1)
    wrap = floor + (1.0 - floor) * np.clip(ndl * 0.5 + 0.5, 0.0, 1.0)
    edge = np.clip(1.0 - n[..., 2], 0.0, 1.0) ** rim_power
    side = np.linalg.norm(l[:2])
    nxy = n[..., :2] / np.maximum(np.linalg.norm(n[..., :2], axis=-1, keepdims=True), 1e-5)
    toward = np.clip((nxy * (l[:2] / max(side, 1e-4))).sum(-1), 0.0, None)
    behind = 0.45 + 0.55 * np.clip(0.5 - l[2], 0.0, 1.0)
    r = edge * toward * behind * rim
    albedo = rgba[..., :3].astype(np.float32) / 255.0
    c = np.array(color, dtype=np.float32)
    lit = albedo * (ambient + c * (wrap + r * 0.6)[..., None]) + c * (r * 0.08)[..., None]
    glow = (255.0 - nmap[..., 3].astype(np.float32)) / 127.0
    lit += albedo * glow[..., None] * 0.6
    out = rgba.copy()
    out[..., :3] = np.clip(lit * 255.0 / (1.0 + ambient * 0.6), 0, 255).astype(np.uint8)
    return out
