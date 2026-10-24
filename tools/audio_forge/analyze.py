"""Measurement helpers: levels, loudness, loop seams, and spectrogram previews.

Since nobody can listen inside the build, every file is checked numerically:
peak / RMS, an approximate BS.1770 loudness (K-weighted momentary max and
gated integrated), DC offset, NaNs, clipping, edge samples (clicks), leading /
trailing silence and -- for loops -- the discontinuity at the wrap point.
"""

from __future__ import annotations

import math
import os

import numpy as np

import synth as S


# ---------------------------------------------------------------------------
# loudness (approximate ITU-R BS.1770 / EBU R128)
# ---------------------------------------------------------------------------

def k_weight(x: np.ndarray, sr: int) -> np.ndarray:
    y = S.biquad(x, "highshelf", 1681.97, sr, q=0.70718, gain_db=3.99984)
    return S.biquad(y, "hp", 38.135, sr, q=0.50033)


def loudness(x: np.ndarray, sr: int, loop: bool = False) -> tuple[float, float]:
    """Return (momentary max, integrated) loudness in LUFS (approximate)."""
    if loop:
        y = k_weight(np.concatenate([x, x]), sr)[len(x):]  # steady-state of the loop
        y = np.concatenate([y, y[:S.ns(0.4, sr)]])
    else:
        y = k_weight(x, sr)
    win, hop = S.ns(0.4, sr), S.ns(0.1, sr)
    if len(y) < win:
        y = np.concatenate([y, np.zeros(win - len(y))])
    c = np.concatenate([[0.0], np.cumsum(y * y)])
    starts = np.arange(0, len(y) - win + 1, hop)
    ms = (c[starts + win] - c[starts]) / win
    lm = -0.691 + 10.0 * np.log10(np.maximum(ms, 1e-20))
    mom_max = float(lm.max())
    keep = lm > -70.0
    if not keep.any():
        return mom_max, -120.0
    l_abs = -0.691 + 10.0 * math.log10(ms[keep].mean())
    keep = lm > max(-70.0, l_abs - 10.0)
    return mom_max, float(-0.691 + 10.0 * math.log10(ms[keep].mean()))


# ---------------------------------------------------------------------------
# per-file analysis
# ---------------------------------------------------------------------------

def analyze_signal(x: np.ndarray, sr: int, loop: bool = False) -> dict:
    d: dict = {}
    n = len(x)
    d["dur"] = n / sr
    d["nan"] = bool(not np.all(np.isfinite(x)))
    x = np.nan_to_num(x)
    a = np.abs(x)
    d["peak_db"] = S.a2db(a.max() if n else 0.0)
    d["rms_db"] = S.a2db(math.sqrt(float(np.mean(x * x))) if n else 0.0)
    d["dc"] = float(np.mean(x)) if n else 0.0
    d["clip"] = int(np.sum(a >= 32766.5 / 32767.0))
    d["first"] = float(a[0]) if n else 0.0
    d["last"] = float(a[-1]) if n else 0.0
    above = np.nonzero(a > S.db2a(-60.0))[0]
    d["lead_ms"] = 1000.0 * (above[0] / sr) if len(above) else d["dur"] * 1000
    above = np.nonzero(a > S.db2a(-66.0))[0]
    d["tail_ms"] = 1000.0 * ((n - 1 - above[-1]) / sr) if len(above) else d["dur"] * 1000
    d["attack_ms"] = 1000.0 * float(np.argmax(a)) / sr if n else 0.0
    mom, integ = loudness(x, sr, loop)
    d["lufs_m"] = mom
    d["lufs_i"] = integ
    spec = np.abs(np.fft.rfft(x * np.hanning(n))) if n > 16 else np.zeros(2)
    f = np.fft.rfftfreq(n, 1.0 / sr) if n > 16 else np.zeros(2)
    d["centroid"] = float(np.sum(f * spec) / (np.sum(spec) + 1e-12))
    if loop and n > 256:
        jump = abs(float(x[0] - x[-1]))
        local = max(float(np.max(np.abs(np.diff(x[-256:])))), float(np.max(np.abs(np.diff(x[:256])))), 1e-9)
        d["seam_jump"] = jump
        d["seam_ratio"] = jump / local
        # level step across the wrap vs. the level steps across every other 20 ms boundary
        w = S.ns(0.02, sr)
        k = n // w
        blocks = np.sqrt(np.mean(x[:k * w].reshape(k, w) ** 2, axis=1)) + 1e-9
        steps = np.abs(20.0 * np.log10(blocks[1:] / blocks[:-1]))
        r_end = math.sqrt(float(np.mean(x[-w:] ** 2))) + 1e-9
        seam = 20.0 * math.log10(blocks[0] / r_end)
        d["seam_rms_db"] = seam
        d["seam_rms_p99"] = float(np.percentile(steps, 99)) if len(steps) else 0.0
        d["seam_rms_max"] = float(np.max(steps)) if len(steps) else 0.0
    return d


def problems(d: dict, loop: bool, kind: str) -> list[str]:
    """Human-readable list of failed checks for one file."""
    p = []
    if d["nan"]:
        p.append("NaN")
    if d["clip"] > 0:
        p.append(f"clipped x{d['clip']}")
    if abs(d["dc"]) > 0.002:
        p.append(f"DC {d['dc']:+.4f}")
    if d["peak_db"] > -0.9:
        p.append(f"peak {d['peak_db']:.2f} dBFS > -1")
    if loop:
        if d.get("seam_ratio", 0) > 2.0 and d.get("seam_jump", 0) > 0.002:
            p.append(f"loop seam jump {d['seam_jump']:.4f} (x{d['seam_ratio']:.1f} local)")
        # every bar of music starts with an onset, so the wrap may legitimately carry a big
        # step; it is only suspicious if it exceeds every other 20 ms boundary in the file
        if abs(d.get("seam_rms_db", 0)) > max(6.0, d.get("seam_rms_max", 0.0) + 1.0):
            p.append(f"loop seam level step {d['seam_rms_db']:+.1f} dB (max elsewhere {d.get('seam_rms_max', 0):.1f})")
    else:
        if d["first"] > 0.002 or d["last"] > 0.002:
            p.append(f"edge sample {max(d['first'], d['last']):.4f}")
        if kind == "sfx" and d["lead_ms"] > 15.0:
            p.append(f"leading silence {d['lead_ms']:.0f} ms")
        if kind == "sfx" and d["tail_ms"] > 30.0:
            p.append(f"trailing silence {d['tail_ms']:.0f} ms")
    return p


# ---------------------------------------------------------------------------
# spectrogram preview (PNG) -- lets a human (or an agent) *look* at the sound
# ---------------------------------------------------------------------------

_CMAP = np.array([
    [8, 6, 20], [38, 18, 70], [92, 24, 110], [160, 44, 100], [215, 90, 60],
    [245, 160, 40], [252, 230, 130], [255, 255, 235]], dtype=float)


def _colorize(v: np.ndarray) -> np.ndarray:
    v = np.clip(v, 0.0, 1.0) * (len(_CMAP) - 1)
    i = np.minimum(np.floor(v).astype(int), len(_CMAP) - 2)
    fr = (v - i)[..., None]
    return (_CMAP[i] * (1 - fr) + _CMAP[i + 1] * fr).astype(np.uint8)


def spectrogram_png(x: np.ndarray, sr: int, path: str, title: str = "", width: int = 1100,
                    height: int = 380, fmin: float = 30.0, db_range: float = 90.0) -> None:
    from PIL import Image, ImageDraw

    n = len(x)
    wave_h = 70
    spec_h = height - wave_h - 18
    n_fft = 2048 if n > 8192 else (1024 if n > 2048 else 256)
    xp = np.concatenate([np.zeros(n_fft // 2), x, np.zeros(n_fft)])
    starts = np.linspace(0, max(len(xp) - n_fft - 1, 0), width).astype(int)
    win = np.hanning(n_fft)
    frames = np.stack([xp[s:s + n_fft] * win for s in starts])
    mag = np.abs(np.fft.rfft(frames, axis=1))
    db = 20 * np.log10(mag + 1e-9)
    db -= db.max()
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    rows = np.exp(np.linspace(math.log(sr / 2), math.log(fmin), spec_h))
    img_db = np.stack([np.interp(rows, freqs, db[c]) for c in range(width)], axis=1)
    rgb = _colorize((img_db + db_range) / db_range)
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:] = (14, 12, 22)
    canvas[18 + wave_h:, :] = rgb
    # waveform strip (min/max per column)
    edges = np.linspace(0, n, width + 1).astype(int)
    mid = 18 + wave_h // 2
    for c in range(width):
        seg = x[edges[c]:max(edges[c + 1], edges[c] + 1)]
        if len(seg) == 0:
            continue
        lo, hi = float(seg.min()), float(seg.max())
        y0 = int(mid - hi * (wave_h // 2 - 2))
        y1 = int(mid - lo * (wave_h // 2 - 2))
        canvas[max(18, y0):min(18 + wave_h, y1 + 1), c] = (120, 200, 170)
    img = Image.fromarray(canvas)
    dr = ImageDraw.Draw(img)
    dr.text((4, 3), title, fill=(230, 230, 230))
    for fl in [100, 1000, 10000]:
        if fl < sr / 2:
            yy = 18 + wave_h + int((math.log(sr / 2) - math.log(fl)) / (math.log(sr / 2) - math.log(fmin)) * spec_h)
            dr.line([(0, yy), (12, yy)], fill=(200, 200, 200))
            dr.text((14, yy - 6), f"{fl if fl < 1000 else str(fl // 1000) + 'k'}", fill=(200, 200, 200))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def format_report(rows: list[tuple[str, str, dict, bool]], header: str) -> str:
    """rows: (section, filename, stats, loop)."""
    out = [header, ""]
    sections: dict[str, list] = {}
    for sec, name, d, loop in rows:
        sections.setdefault(sec, []).append((name, d, loop))
    total_problems = 0
    for sec, items in sections.items():
        out.append(sec)
        out.append("-" * len(sec))
        out.append(f"{'file':34s} {'dur s':>7s} {'peak dBFS':>9s} {'RMS dBFS':>9s} {'LUFS-M':>7s} "
                   f"{'LUFS-I':>7s} {'DC':>8s} {'clip':>4s}  notes")
        for name, d, loop in items:
            notes = []
            if loop:
                notes.append(f"loop seam: jump {d.get('seam_jump', 0):.5f} (x{d.get('seam_ratio', 0):.2f} of local "
                             f"step), 20ms level step {d.get('seam_rms_db', 0):+.1f} dB "
                             f"(elsewhere p99 {d.get('seam_rms_p99', 0):.1f}, max {d.get('seam_rms_max', 0):.1f})")
            pr = d.get("problems", [])
            total_problems += len(pr)
            if pr:
                notes.append("PROBLEM: " + "; ".join(pr))
            out.append(f"{name:34s} {d['dur']:7.3f} {d['peak_db']:9.2f} {d['rms_db']:9.2f} {d['lufs_m']:7.1f} "
                       f"{d['lufs_i']:7.1f} {d['dc']:+8.5f} {d['clip']:4d}  {' '.join(notes)}")
        out.append("")
    out.append(f"Checks: {'all passed' if total_problems == 0 else str(total_problems) + ' problem(s) flagged'}"
               " (NaN, clipping, DC > 0.002, peak > -1 dBFS, edge samples > 0.002, leading silence > 15 ms,"
               " trailing (< -66 dBFS) > 30 ms, loop seam jump > 2x the local sample step or an unusual level step at the wrap).")
    return "\n".join(out) + "\n"
