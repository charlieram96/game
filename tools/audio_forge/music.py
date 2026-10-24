"""Wildbound music: a tiny step sequencer plus the six original cues.

Notation (see :func:`mel`): whitespace-separated ``pitch:beats`` tokens, e.g.
``"A4:.5 D5:.5 F#5:1.5 | B4:2 r:2 |"``.  ``r`` is a rest, ``-`` ties onto the
previous note, ``C4+E4+G4`` is a chord, a trailing ``!`` accents and ``?``
softens.  ``|`` bar lines are validated against the time signature, so a
mis-counted bar is a build error rather than a silent rhythm bug.

Loops are rendered *circularly*: every note tail, delay echo and reverb tail
that runs past the end of the loop is wrapped onto the beginning, so the file
plays seamlessly end -> start.  Stems are balanced "by numbers": each track
can declare a target loudness (``level``, LUFS of the stem) and is scaled to it.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

import instruments as I
import synth as S

SR = S.MUSIC_SR


# ---------------------------------------------------------------------------
# notes & notation
# ---------------------------------------------------------------------------

@dataclass
class Note:
    beat: float
    dur: float
    midi: float
    vel: float = 0.8
    kw: dict = field(default_factory=dict)


def _num(s: str) -> float:
    if "/" in s:
        a, b = s.split("/")
        return float(a) / float(b)
    return float(s)


def mel(text: str, start: float = 0.0, vel: float = 0.8, bar: float | None = None,
        transpose: int = 0, kw: dict | None = None) -> list[Note]:
    """Parse melody notation into notes (see module docstring)."""
    notes: list[Note] = []
    t = start
    bar_t = 0.0
    bar_no = 1
    last: list[Note] | None = None
    for tok in text.split():
        if tok == "|":
            if bar is not None and abs(bar_t - bar) > 1e-6:
                raise ValueError(f"bar {bar_no} has {bar_t} beats (expected {bar}): {text[:60]!r}")
            bar_t = 0.0
            bar_no += 1
            continue
        acc = 1.0
        while tok[-1] in "!?":
            acc *= 1.18 if tok[-1] == "!" else 0.72
            tok = tok[:-1]
        p, d = tok.split(":")
        dur = _num(d)
        if p == "r":
            last = None
        elif p == "-":
            if last is None:
                raise ValueError("tie without a previous note")
            for nt in last:
                nt.dur += dur
        else:
            group = []
            for name in p.split("+"):
                nt = Note(t, dur, S.note_midi(name) + transpose, min(1.0, vel * acc), dict(kw or {}))
                notes.append(nt)
                group.append(nt)
            last = group
        t += dur
        bar_t += dur
    if bar is not None and bar_t > 1e-6 and abs(bar_t - bar) > 1e-6:
        raise ValueError(f"last bar has {bar_t} beats (expected {bar})")
    return notes


def hits(pattern: str, bars, beats_per_bar: float = 4, steps_per_beat: int = 2, vel: float = 0.8,
         midi: float = 60, kw: dict | None = None, start_bar: int = 0) -> list[Note]:
    """Drum-style step pattern per bar: 'X' accent, 'x' hit, 'o' ghost, '.' rest."""
    out = []
    step = 1.0 / steps_per_beat
    for b in bars:
        for i, ch in enumerate(pattern.replace(" ", "")):
            if ch == ".":
                continue
            v = vel * {"X": 1.2, "x": 1.0, "o": 0.55}[ch]
            out.append(Note((b - start_bar) * beats_per_bar + i * step, step, midi, min(v, 1.0), dict(kw or {})))
    return out


# ---------------------------------------------------------------------------
# harmony helpers
# ---------------------------------------------------------------------------

CHORDS = {
    "": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11), "m7": (0, 3, 7, 10),
    "sus4": (0, 5, 7), "sus2": (0, 2, 7), "add9": (0, 4, 7, 14), "madd9": (0, 3, 7, 14),
    "6": (0, 4, 7, 9), "m6": (0, 3, 7, 9), "9": (0, 4, 7, 10, 14), "m9": (0, 3, 7, 10, 14),
    "maj9": (0, 4, 7, 11, 14), "7sus4": (0, 5, 7, 10), "dim": (0, 3, 6),
}


def parse_chord(sym: str) -> tuple[int, tuple[int, ...], int]:
    """'F#m7/C#' -> (root pc, intervals, bass pc)."""
    main, _, bass = sym.partition("/")
    i = 1
    while i < len(main) and main[i] in "#b":
        i += 1
    root = S.note_midi(main[:i] + "4") % 12
    ints = CHORDS[main[i:]]
    bass_pc = S.note_midi(bass + "4") % 12 if bass else root
    return root, ints, bass_pc


def voice_lead(symbols: list[str], n: int = 4, lo: int = 54, hi: int = 72, center: float = 63.0,
               first: list[int] | None = None) -> list[list[int]]:
    """Close-position voicings with minimal total voice movement between chords."""
    out: list[list[int]] = []
    prev = first
    for sym in symbols:
        root, ints, _ = parse_chord(sym)
        pcs = [(root + iv) % 12 for iv in ints]
        if len(pcs) > n:  # drop the fifth first
            pcs = [p for j, p in enumerate(pcs) if j != 2]
        third = pcs[1] if len(pcs) > 1 else None
        cands = [m for m in range(lo, hi + 1) if m % 12 in pcs]
        best, best_cost = None, 1e9
        for min_gap, max_gap in ((2, 9), (2, 12), (1, 12)):  # relax spacing only if nothing fits
            for combo in itertools.combinations(cands, n):
                got = {m % 12 for m in combo}
                if got != set(pcs):
                    continue
                gaps = np.diff(combo)
                if gaps.min() < min_gap or gaps.max() > max_gap:
                    continue
                if prev is None:
                    cost = abs(float(np.mean(combo)) - center) * 2.0
                else:
                    cost = float(np.sum(np.abs(np.array(combo) - np.array(prev))))
                    cost += 0.15 * abs(float(np.mean(combo)) - center)
                if third is not None and sum(1 for m in combo if m % 12 == third) > 1:
                    cost += 3.0
                if cost < best_cost:
                    best, best_cost = list(combo), cost
            if best is not None:
                break
        if best is None:
            raise ValueError(f"no voicing for {sym} in [{lo},{hi}]")
        out.append(best)
        prev = best
    return out


def chord_ladder(sym: str, root_lo: int, octaves: int = 3) -> list[int]:
    """Chord tones from the root (lowest root >= root_lo) upward."""
    root, ints, _ = parse_chord(sym)
    r = root_lo + ((root - root_lo) % 12)
    tones = sorted({iv % 12 for iv in ints})
    ladder = []
    for o in range(octaves):
        for iv in tones:
            ladder.append(r + 12 * o + iv)
    return ladder


def arpeggio(segments: list[tuple[float, float, str]], pattern: list[int], step: float = 0.5,
             root_lo: int = 45, vel: float = 0.7, accent_every: int = 0, dur_mult: float = 1.0,
             vel_pattern: list[float] | None = None) -> list[Note]:
    """Broken-chord notes over (beat, beats, chord) segments using ladder indices."""
    out = []
    for beat, beats, sym in segments:
        lad = chord_ladder(sym, root_lo)
        steps = int(round(beats / step))
        for i in range(steps):
            idx = pattern[i % len(pattern)]
            v = vel * (vel_pattern[i % len(vel_pattern)] if vel_pattern else 1.0)
            if accent_every and i % accent_every == 0:
                v *= 1.12
            out.append(Note(beat + i * step, step * dur_mult, lad[min(idx, len(lad) - 1)], min(v, 1.0)))
    return out


def chord_notes(segments, voicings, vel=0.6, dur_scale=1.0, kw=None, strum=0.0):
    out = []
    for (beat, beats, _), v in zip(segments, voicings):
        for j, m in enumerate(v):
            out.append(Note(beat + j * strum, beats * dur_scale - j * strum, m, vel, dict(kw or {})))
    return out


def segs(spec: list, beats_per_bar: float = 4) -> list[tuple[float, float, str]]:
    """['D', 'Bm', ('D','A/C#')] -> [(beat, beats, sym), ...] (tuples split the bar evenly)."""
    out = []
    t = 0.0
    for item in spec:
        parts = item if isinstance(item, tuple) else (item,)
        d = beats_per_bar / len(parts)
        for p in parts:
            out.append((t, d, p))
            t += d
    return out


# ---------------------------------------------------------------------------
# tracks, songs, rendering
# ---------------------------------------------------------------------------

@dataclass
class Track:
    name: str
    voice: Callable
    notes: list[Note]
    drum: bool = False
    gain: float = 1.0
    level: float | None = None      # target integrated loudness (LUFS) of the stem
    reverb: float = 0.0             # send amounts
    delay: float = 0.0
    kw: dict = field(default_factory=dict)
    gate: float = 1.0               # gate = beats * gate
    humanize_ms: float = 0.0
    vel_jitter: float = 0.0
    swing: bool = False
    variants: int = 0               # >0: reuse renders of identical notes (cycling variants)
    chorus: dict | None = None
    post: Callable | None = None    # fn(x, sr, loop) -> x


@dataclass
class Song:
    name: str
    bpm: float
    beats: float
    tracks: list[Track]
    sr: int = SR
    loop: bool = True
    swing: float = 0.5              # 0.5 = straight; 0.6 = light swing on 8ths
    reverb_rt60: float = 2.2
    reverb_predelay: float = 0.02
    reverb_damping: float = 0.5
    delay_beats: float = 0.75
    delay_fb: float = 0.35
    delay_damp: float = 4000.0
    delay_to_reverb: float = 0.4
    tail: float = 3.0               # extra render time for non-loops
    beds: list = field(default_factory=list)  # [(fn(n, sr, rng) -> x, level LUFS, reverb send)]
    master_hp: float = 30.0


def _swing_map(t: float, ratio: float) -> float:
    """Piecewise-linear time warp: the off-beat 8th (x.5) moves to x.ratio."""
    whole = math.floor(t + 1e-9)
    frac = t - whole
    if frac < 0.5:
        return whole + frac * 2.0 * ratio
    return whole + ratio + (frac - 0.5) * 2.0 * (1.0 - ratio)


def _swing(beat: float, dur: float, ratio: float) -> tuple[float, float]:
    b0 = _swing_map(beat, ratio)
    b1 = _swing_map(beat + dur, ratio)
    return b0, max(b1 - b0, 0.05)


def stem_loudness(x: np.ndarray, sr: int) -> float:
    """Gated integrated loudness of a stem via a zero-phase K-weighting (fast, FFT)."""
    def kmag(f):
        out = np.ones_like(f)
        for kind, f0, q, g in (("highshelf", 1681.97, 0.70718, 3.99984), ("hp", 38.135, 0.50033, 0.0)):
            b0, b1, b2, a1, a2 = S._rbj(kind, f0, sr, q, g)
            z = np.exp(-1j * S.TAU * f / sr)
            out = out * np.abs((b0 + b1 * z + b2 * z * z) / (1 + a1 * z + a2 * z * z))
        return out
    y = S.fft_filter(x, sr, kmag, circular=True)
    win, hop = S.ns(0.4, sr), S.ns(0.1, sr)
    c = np.concatenate([[0.0], np.cumsum(y * y)])
    starts = np.arange(0, max(len(y) - win, 0) + 1, hop)
    ms = (c[starts + win] - c[starts]) / win
    lm = -0.691 + 10 * np.log10(np.maximum(ms, 1e-20))
    keep = lm > -70
    if not keep.any():
        return -120.0
    l_abs = -0.691 + 10 * math.log10(ms[keep].mean())
    keep = lm > max(-70.0, l_abs - 10.0)
    return float(-0.691 + 10 * math.log10(ms[keep].mean()))


def render_track(tr: Track, song: Song, total: int) -> np.ndarray:
    sr = song.sr
    spb = 60.0 / song.bpm
    out = np.zeros(total)
    rng_h = S.rng_for(song.name, tr.name, "humanize")
    cache: dict = {}
    for i, nt in enumerate(tr.notes):
        beat, dur = nt.beat, nt.dur
        if tr.swing and song.swing != 0.5:
            beat, dur = _swing(beat, dur, song.swing)
        t0 = beat * spb
        if tr.humanize_ms:
            t0 += rng_h.normal(0.0, tr.humanize_ms / 1000.0)
        vel = nt.vel
        if tr.vel_jitter:
            vel = float(np.clip(vel * (1.0 + tr.vel_jitter * rng_h.uniform(-1, 1)), 0.05, 1.0))
            vel = round(vel * 40) / 40  # quantise so identical notes can share renders
        kw = {**tr.kw, **nt.kw}
        gate = dur * spb * tr.gate
        var = (i % tr.variants) if tr.variants else i
        key = (round(nt.midi, 3), round(gate, 4), round(vel, 4), tuple(sorted(kw.items())), var)
        w = cache.get(key)
        if w is None:
            rng = S.rng_for(song.name, tr.name, *key)
            if tr.drum:
                w = tr.voice(vel, sr, rng, **kw)
            else:
                w = tr.voice(float(S.midi_hz(nt.midi)), gate, vel, sr, rng, **kw)
            cache[key] = w
        st = S.ns(t0, sr)
        if song.loop:
            S.place_circ(out, w, st)
        else:
            S.place(out, w, max(st, 0))
    return out


def render_song(song: Song, stems: bool = False):
    sr = song.sr
    spb = 60.0 / song.bpm
    L = S.ns(song.beats * spb, sr)
    total = L if song.loop else L + S.ns(song.tail, sr)
    dry = np.zeros(total)
    rev_bus = np.zeros(total)
    del_bus = np.zeros(total)
    stem_out = {}
    for tr in song.tracks:
        x = render_track(tr, song, total)
        if tr.chorus:
            x = S.chorus(x, sr, circular=song.loop, **tr.chorus)
        if tr.post:
            x = tr.post(x, sr, song.loop)
        if tr.level is not None:
            lu = stem_loudness(x, sr)
            if lu > -100:
                x = x * S.db2a(tr.level - lu)
        x = x * tr.gain
        stem_out[tr.name] = x
        dry += x
        if tr.reverb:
            rev_bus += tr.reverb * x
        if tr.delay:
            del_bus += tr.delay * x
    for j, (fn, level, send) in enumerate(song.beds):
        x = fn(total, sr, S.rng_for(song.name, "bed", j))
        lu = stem_loudness(x, sr)
        x = x * S.db2a(level - lu)
        stem_out[f"bed{j}"] = x
        dry += x
        rev_bus += send * x
    if np.any(del_bus):
        d = S.echo(del_bus, sr, song.delay_beats * spb, song.delay_fb, 1.0, song.delay_damp, circular=song.loop)
        d = S.pad_to(d, total)
        dry += d
        rev_bus += song.delay_to_reverb * d
    ir = S.make_ir(sr, song.reverb_rt60, song.reverb_predelay, song.reverb_damping,
                   rng=S.rng_for(song.name, "ir"))
    wet = S.convolve_circular(rev_bus, ir) if song.loop else S.convolve(rev_bus, ir)[:total]
    mix = dry + wet
    mix = S.remove_dc(mix, sr, song.master_hp, circular=song.loop)
    if stems:
        stem_out["reverb"] = wet
        return mix, stem_out
    return mix


# ---------------------------------------------------------------------------
# loop-safe beds (drones / air): every oscillator snaps to whole cycles per loop
# ---------------------------------------------------------------------------

def drone(partials: list[tuple[float, float]], am_rate: float = 0.1, am_depth: float = 0.3,
          harmonics: int = 4, bright: float = 0.35):
    """Sustained loop-periodic drone: list of (freq, amp); each partial gets soft harmonics."""
    def fn(n, sr, rng):
        T = n / sr
        t = np.arange(n) / sr
        out = np.zeros(n)
        for f, a in partials:
            cyc = max(1, round(f * T))
            for h in range(1, harmonics + 1):
                fh = cyc * h / T
                if fh > 0.45 * sr:
                    break
                out += a * (bright ** (h - 1)) * np.sin(S.TAU * fh * t + rng.uniform(0, S.TAU))
        am = 1.0 - am_depth + am_depth * (0.5 + 0.5 * S.lfo_noise(n, sr, am_rate, rng))
        return out * am
    return fn


def air(lo: float = 300.0, hi: float = 2500.0, rate: float = 0.12, depth: float = 0.6, color: float = 1.0):
    """Wind/air noise bed (periodic in the loop length)."""
    def fn(n, sr, rng):
        x = S.colored(n, rng, color, sr)
        x = S.fft_filter(x, sr, S.mag_bp(lo, hi, 1.5), circular=True)
        am = 1.0 - depth + depth * (0.5 + 0.5 * S.lfo_noise(n, sr, rate, rng))
        return x * am
    return fn


# ---------------------------------------------------------------------------
# voice adaptors
# ---------------------------------------------------------------------------

def _timp(f, dur, vel, sr, rng, **kw):
    return I.timpani(f, vel, sr, rng, **kw)


def _tom(f, dur, vel, sr, rng, **kw):
    return I.tom(f, vel, sr, rng, **kw)


def _lp_post(fc):
    def post(x, sr, loop):
        return S.fft_filter(x, sr, S.mag_lp(fc, 1.5), circular=loop)
    return post


# ---------------------------------------------------------------------------
# 1. title theme -- D major, 84 BPM, 16 bars
# ---------------------------------------------------------------------------

def title_theme() -> Song:
    chords = ["D", "Bm", "G", "A", "D", "F#m", "G", "A",
              "Bm", "G", "D", "A", "G", "A", "D", ("D", "A/C#")]
    sg = segs(chords)
    lead = mel("""
        A4:.5 D5:.5 F#5:1.5 E5:.5 D5:.5 E5:.5 | F#5:1.5 D5:.5 B4:2 |
        G4:.5 D5:.5 G5:1.5 F#5:.5 E5:.5 D5:.5 | E5:3 r:1 |
        A4:.5 D5:.5 F#5:1.5 E5:.5 F#5:.5 A5:.5 | C#6:1.5! B5:.5 A5:2 |
        B5:.5 A5:.5 G5:.5 F#5:.5 G5:1 B5:1 | A5:2.5 G5:.5 F#5:.5 E5:.5 |
        D5:1 F#5:1 B5:2 | A5:1 G5:1 D5:1.5 E5:.5 |
        F#5:1 A5:1 D6:2! | C#6:1 B5:.5 A5:.5 E5:2 |
        G5:1.5 F#5:.5 E5:1 D5:1 | E5:1.5 F#5:.5 E5:1 C#5:1 |
        D5:3 r:1 | r:4 |""", bar=4, vel=0.78)
    glock = mel("""
        r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4 |
        r:4 | r:4 | r:2 F#6:.5 E6:.5 D6:1 | r:4 |
        r:2 E6:.5 D6:.5 B5:1 | r:4 | r:2 A5:.5 D6:.5 F#6:1 | E6:1 D6:1 C#6:1 A5:1 |""", bar=4, vel=0.62)
    bass = mel("""
        D2:2 A1:2 | B1:2 F#2:2 | G1:2 D2:2 | A1:2 E2:2 |
        D2:2 A1:2 | F#2:2 C#2:2 | G1:2 D2:2 | A1:2 C#2:1 E2:1 |
        B1:2 F#2:2 | G1:2 D2:2 | D2:2 F#2:2 | A1:2 E2:2 |
        G1:2 B1:2 | A1:2 C#2:2 | D2:4 | D2:2 C#2:2 |""", bar=4, vel=0.75)
    pat_a = [0, 2, 3, 4, 5, 4, 3, 2]
    pat_b = [0, 2, 3, 4, 5, 6, 5, 3]
    harp = arpeggio([s for s in sg if s[0] < 32] + [s for s in sg if s[0] >= 56], pat_a, 0.5, root_lo=45,
                    vel=0.6, vel_pattern=[1.0, 0.8, 0.85, 0.8, 0.9, 0.8, 0.85, 0.8])
    harp += arpeggio([s for s in sg if 32 <= s[0] < 56], pat_b, 0.5, root_lo=45, vel=0.62,
                     vel_pattern=[1.0, 0.8, 0.85, 0.8, 0.9, 0.85, 0.85, 0.8])
    pad_v = voice_lead([s[2] for s in sg], 4, 54, 71, 62)
    pad = chord_notes(sg, pad_v, vel=0.6)
    shaker = hits("xoxoxoxo", range(4, 8), vel=0.5) + hits("xoxoxoxo", range(8, 15), vel=0.7)
    kick = hits("x...x...", range(8, 15), vel=0.55)
    snare = hits("..x...x.", range(8, 15), vel=0.5)
    timp = [Note(32, 1, S.note_midi("B2"), 0.55), Note(40, 1, S.note_midi("D3"), 0.65),
            Note(59, 1, S.note_midi("A2"), 0.4), Note(59.5, 0.5, S.note_midi("A2"), 0.45)]
    crash = [Note(40, 1, 60, 0.35)]
    tracks = [
        Track("lead", I.lead, lead, level=-20.0, reverb=0.28, delay=0.22, gate=0.93,
              kw=dict(vib_depth=0.16, vib_rate=5.2, vib_delay=0.3)),
        Track("harp", I.harp, harp, level=-25.5, reverb=0.35, variants=2, humanize_ms=4),
        Track("pad", I.pad, pad, level=-27.0, reverb=0.4, kw=dict(cutoff=1300.0, attack=0.9, release=1.4),
              chorus=dict(voices=2, base_ms=14, depth_ms=4, rate_hz=0.3, mix=0.5)),
        Track("bass", I.bass, bass, level=-25.0, reverb=0.08, gate=0.95, kw=dict(pluck_amt=0.35)),
        Track("glock", I.glock, glock, level=-29.0, reverb=0.45, delay=0.3),
        Track("shaker", I.shaker, shaker, drum=True, level=-35.0, reverb=0.15, swing=False, humanize_ms=3),
        Track("kick", lambda v, sr, rng: I.kick(v, sr, rng, soft=True), kick, drum=True, level=-29.0, reverb=0.05),
        Track("snare", lambda v, sr, rng: I.snare(v, sr, rng, brush=True), snare, drum=True, level=-31.0,
              reverb=0.2, humanize_ms=3),
        Track("timpani", _timp, timp, level=-30.0, reverb=0.35),
        Track("crash", lambda v, sr, rng: I.crash(v, sr, rng, 2.6, 0.7), crash, drum=True, level=-34.0, reverb=0.3),
    ]
    return Song("title_theme", 84, 64, tracks, reverb_rt60=2.4, delay_beats=0.75, delay_fb=0.32)


# ---------------------------------------------------------------------------
# 2. village theme -- G major, 100 BPM, 20 bars, light swing
# ---------------------------------------------------------------------------

def village_theme() -> Song:
    chords = ["G", "Em7", "Cmaj7", "D7", "G", "E7", ("Am7", "D7"), "G",
              "Cmaj7", "Bm7", "Em7", "A7", "Am7", "D7", ("Bm7", "E7"), ("Am7", "D7"),
              "G", "Em7", ("Am7", "D7"), ("G", "D7")]
    sg = segs(chords)
    melody = mel("""
        D5:.5 E5:.5 D5:1 B4:.5 A4:.5 G4:1 | E5:.5 F#5:.5 G5:1 E5:.5 D5:.5 B4:1 |
        G5:1.5 E5:.5 C5:1 E5:1 | F#5:.5 G5:.5 A5:1 F#5:1 D5:1 |
        D5:.5 E5:.5 D5:1 B4:.5 A4:.5 G4:1 | B4:.5 D5:.5 E5:1 D5:.5 B4:.5 G#4:1 |
        A4:.5 B4:.5 C5:.5 E5:.5 D5:.5 C5:.5 B4:.5 A4:.5 | G4:2 r:1 G4:.5 A4:.5 |
        B4:1.5 C5:.5 E5:1 G5:1 | F#5:1.5 E5:.5 D5:1 B4:1 |
        G5:1.5 F#5:.5 E5:1 B4:1 | C#5:1 E5:.5 G5:.5 F#5:1 E5:1 |
        C5:1.5 B4:.5 A4:1 E5:1 | F#5:1.5 E5:.5 D5:1 C5:1 |
        B4:.5 D5:.5 F#5:1 E5:.5 D5:.5 B4:.5 G#4:.5 | A4:.5 C5:.5 E5:1 D5:.5 C5:.5 A4:.5 C5:.5 |
        D5:.5 E5:.5 D5:1 B4:.5 A4:.5 G4:1 | E5:.5 F#5:.5 G5:1 E5:.5 D5:.5 B4:1 |
        C5:.5 E5:.5 A5:1 F#5:.5 E5:.5 D5:.5 C5:.5 | B4:1 G4:1 r:1 A4:.5 C5:.5 |""", bar=4, vel=0.8)
    glock = mel("""
        r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4 | r:4 |
        r:2 G6:.5 E6:.5 D6:.5 B5:.5 | A5:2 r:1 D6:.5 F#6:.5 |
        G6:2 r:1 B5:.5 D6:.5 | E6:1 C#6:1 r:1 A5:.5 C#6:.5 |
        E6:2 r:1 C6:.5 E6:.5 | D6:2 r:1 A5:.5 C6:.5 |
        D6:1 F#6:1 G#6:1 B6:1 | A6:1 E6:1 F#6:1 D6:1 |
        G6:1 D6:1 B5:2 | r:1 B5:.5 E6:.5 G6:2 |
        E6:1 C6:1 D6:1 F#6:1 | G6:2 r:2 |""", bar=4, vel=0.55)
    bass = mel("""
        G2:1 B2:1 A2:1 F#2:1 | E2:1 G2:1 A2:1 B2:1 | C3:1 G2:1 E2:1 C#2:1 | D2:1 F#2:1 A2:1 F#2:1 |
        G2:1 B2:1 A2:1 F#2:1 | E2:1 G#2:1 B2:1 G#2:1 | A2:1 E2:1 D2:1 F#2:1 | G2:1 B2:1 D3:1 B2:1 |
        C3:1 E3:1 D3:1 C3:1 | B2:1 A2:1 G2:1 F#2:1 | E2:1 F#2:1 G2:1 G#2:1 | A2:1 C#3:1 E3:1 B2:1 |
        A2:1 C3:1 G2:1 E2:1 | D2:1 F#2:1 A2:1 C3:1 | B2:1 D3:1 E2:1 G#2:1 | A2:1 C3:1 D2:1 F#2:1 |
        G2:1 B2:1 A2:1 F#2:1 | E2:1 F#2:1 G2:1 B2:1 | A2:1 C3:1 D2:1 F#2:1 | G2:1 B2:1 D2:1 F#2:1 |""",
               bar=4, vel=0.75)
    # soft flute-ish doubling of the B section melody (sustain under the plucks)
    doubling = [Note(n.beat, n.dur, n.midi, n.vel * 0.8) for n in melody if 32 <= n.beat < 64]
    # ukulele-ish chops on beats 2 and 4 (half-bar chords split across them)
    comp_v = voice_lead([s[2] for s in sg], 3, 57, 71, 64)
    comp = []
    for (beat, beats, sym), v in zip(sg, comp_v):
        targets = [beat + 1.0, beat + 3.0] if beats == 4 else [beat + 1.0]
        for tb in targets:
            for j, m in enumerate(v):
                comp.append(Note(tb + j * 0.025, 0.4, m, 0.55 + 0.05 * j))
    pad_v = voice_lead([s[2] for s in sg], 4, 52, 72, 61)
    pad = chord_notes(sg, pad_v, vel=0.5)
    allbars = range(20)
    kick = hits("x...x...", allbars, vel=0.6) + [Note(b * 4 + 3.5, 0.5, 60, 0.4) for b in (3, 7, 11, 15, 19)]
    snare = hits("..x...x.", allbars, vel=0.55) + [Note(b * 4 + 3.5, 0.5, 60, 0.35) for b in (7, 15, 19)]
    shaker = hits("xoxoxoxo", allbars, vel=0.6)
    tracks = [
        Track("melody", lambda f, d, v, sr, rng: I.pluck(f, d, v, sr, rng, bright=0.8), melody, level=-20.5,
              reverb=0.22, delay=0.1, swing=True, humanize_ms=4, variants=2),
        Track("doubling", lambda f, d, v, sr, rng: I.soft_sine(f, d, v, sr, rng, attack=0.04, release=0.15),
              doubling, level=-30.0, reverb=0.3, swing=True, gate=0.9),
        Track("glock", I.glock, glock, level=-26.5, reverb=0.35, delay=0.18, swing=True, humanize_ms=3),
        Track("bass", I.bass, bass, level=-24.0, reverb=0.06, gate=0.78, kw=dict(pluck_amt=0.75),
              humanize_ms=3),
        Track("comp", lambda f, d, v, sr, rng: I.pluck(f, d, v, sr, rng, t60=0.5, bright=0.55), comp,
              level=-29.0, reverb=0.2, swing=True, variants=2, humanize_ms=2),
        Track("pad", I.pad, pad, level=-31.0, reverb=0.3, kw=dict(cutoff=1100.0, attack=0.5, release=0.9)),
        Track("kick", lambda v, sr, rng: I.kick(v, sr, rng, soft=True), kick, drum=True, level=-29.0,
              reverb=0.05, swing=True),
        Track("snare", lambda v, sr, rng: I.snare(v, sr, rng, brush=True), snare, drum=True, level=-30.5,
              reverb=0.15, swing=True, humanize_ms=3),
        Track("shaker", I.shaker, shaker, drum=True, level=-33.0, reverb=0.1, swing=True, humanize_ms=3,
              vel_jitter=0.15),
    ]
    return Song("village_theme", 100, 80, tracks, swing=0.6, reverb_rt60=1.6, reverb_damping=0.6,
                delay_beats=0.5, delay_fb=0.25)


# ---------------------------------------------------------------------------
# 3. forest theme -- E dorian, 72 BPM, 12 bars, sparse & airy
# ---------------------------------------------------------------------------

def forest_theme() -> Song:
    # (bar, bars, voicing above the E drone)
    pads = [(0, 2, [59, 62, 66, 67]),   # Em9      B3 D4 F#4 G4
            (2, 2, [57, 61, 64, 69]),   # A/E      A3 C#4 E4 A4  (dorian IV)
            (4, 2, [59, 62, 66, 67]),   # Em9
            (6, 2, [60, 64, 67, 71]),   # Cmaj7/E  C4 E4 G4 B4
            (8, 2, [62, 64, 66, 69]),   # D/E      D4 E4 F#4 A4
            (10, 2, [59, 62, 66, 69])]  # Bm7/E    B3 D4 F#4 A4  -> resolves A4->G4 at the loop
    pad = [Note(b * 4, n * 4, m, 0.55) for b, n, v in pads for m in v]
    bells = mel("""
        B4:1.5 E5:.5 F#5:2 | r:4 | C#5:1.5 E5:.5 B4:2 | r:4 |
        B4:1.5 E5:.5 G5:2 | F#5:2 r:2 | r:2 E5:1 G5:1 | B5:3 r:1 |
        A5:1.5 F#5:.5 D5:2 | E5:4 | D5:1.5 B4:.5 A4:2 | r:4 |""", bar=4, vel=0.6)
    harp_segs = [(4, "Em"), (12, "A"), (20, "Em"), (28, "C"), (36, "D"), (44, "Bm")]
    harp = []
    for beat, sym in harp_segs:
        lad = chord_ladder(sym, 52)
        for i, idx in enumerate([0, 1, 2, 3, 4, 5]):
            harp.append(Note(beat + 0.5 * i, 0.5, lad[idx], 0.42 + 0.03 * i))
    rng = S.rng_for("forest", "twinkles")
    tw_pitches = ["E7", "F#7", "B6", "E6", "B7", "F#6"]
    twinkles = []
    for k in range(18):
        beat = float(rng.uniform(0, 48))
        twinkles.append(Note(round(beat * 4) / 4, 0.25, S.note_midi(tw_pitches[k % len(tw_pitches)]),
                             float(rng.uniform(0.35, 0.7))))
    tracks = [
        Track("pad", I.pad, pad, level=-25.0, reverb=0.45,
              kw=dict(cutoff=950.0, attack=2.2, release=2.6, detune=10.0, open_amt=0.7),
              chorus=dict(voices=2, base_ms=16, depth_ms=5, rate_hz=0.2, mix=0.6)),
        Track("bells", lambda f, d, v, sr, rng: I.bell(f, d, v, sr, rng, ratio=1.4, index=1.6, t60=3.6),
              bells, level=-25.0, reverb=0.6, delay=0.35, humanize_ms=6),
        Track("harp", I.harp, harp, level=-31.0, reverb=0.55, humanize_ms=8),
        Track("twinkle", I.twinkle, twinkles, level=-37.0, reverb=0.8, delay=0.4),
    ]
    beds = [
        (drone([(S.hz("E2"), 1.0), (S.hz("B2"), 0.45), (S.hz("E1"), 0.22)], am_rate=0.08, am_depth=0.35,
               harmonics=4, bright=0.3), -29.5, 0.15),
        (air(500.0, 5000.0, 0.1, 0.7), -36.0, 0.3),
    ]
    return Song("forest_theme", 72, 48, tracks, beds=beds, reverb_rt60=3.6, reverb_predelay=0.03,
                reverb_damping=0.45, delay_beats=1.5, delay_fb=0.38, delay_damp=3200.0)


# ---------------------------------------------------------------------------
# 4. battle theme -- A minor, 150 BPM, 32 bars
# ---------------------------------------------------------------------------

def battle_theme() -> Song:
    chords = ["Am", "F", "G", "Am", "Am", "F", "G", "E",
              "Am", "F", "G", "Am", "Dm", "F", "Esus4", "E",
              "F", "G", "Em", "Am", "F", "G", "E", "E",
              "C", "G", "F", "G",
              "Am", "F", "Dm", "E"]
    sg = segs(chords)
    a_phrase = """ E5:.5 A5:1 B5:.5 C6:1 B5:.5 A5:.5 | C6:.5 F5:1 G5:.5 A5:1.5 G5:.5 |
                  D5:.5 G5:1 A5:.5 B5:1 A5:.5 G5:.5 | A5:1.5 E5:.5 C5:1 E5:1 | """
    lead = mel(a_phrase + """
        E5:.5 A5:1 B5:.5 C6:1 B5:.5 A5:.5 | C6:.5 A5:1 C6:.5 F6:1 E6:.5 D6:.5 |
        D6:1 B5:.5 G5:.5 D6:1 C6:.5 B5:.5 | B5:1.5 G#5:.5 E5:1 G#5:.5 B5:.5 |""" + a_phrase + """
        F5:.5 A5:1 D6:.5 F6:1 E6:.5 D6:.5 | C6:1.5 A5:.5 F5:1 A5:1 |
        E6:1 D6:.5 C6:.5 B5:1 A5:1 | G#5:2 B5:1 E6:1 |
        A5:2 C6:1.5 A5:.5 | B5:2 D6:1.5 B5:.5 | E6:3! D6:.5 B5:.5 | C6:2 A5:2 |
        A5:1 C6:1 F6:1.5! E6:.5 | D6:1 B5:1 G5:1 D6:1 | E6:1.5 D6:.5 B5:1 G#5:1 | B5:2 r:1 G#5:.5 B5:.5 |
        C6:1 E6:1 G6:1.5! E6:.5 | D6:1.5 B5:.5 G5:1 B5:1 | C6:1 A5:1 F6:1.5 E6:.5 | D6:2 G5:1 B5:1 |
        C6:1.5 B5:.5 A5:1 E5:1 | F5:1.5 G5:.5 A5:1 C6:1 | D6:1.5 C6:.5 A5:1 F5:1 | E5:1 G#5:1 B5:1.5 r:.5 |
        """, bar=4, vel=0.8)
    # bass: driving 8ths, octave pops
    bass = []
    for beat, beats, sym in sg:
        root, _, _ = parse_chord(sym)
        r = 33 + ((root - 33) % 12)
        half_time = 96 <= beat < 112
        for i in range(8):
            m = r + (12 if i in (2, 6) else 0)
            v = 0.85 if i % 2 == 0 else 0.7
            if half_time:
                v *= 0.85
            bass.append(Note(beat + 0.5 * i, 0.5, m, v))
    # pluck ostinato from bar 9
    ost = arpeggio([s for s in sg if s[0] >= 32], [0, 2, 3, 2, 4, 2, 3, 2], 0.5, root_lo=57, vel=0.55,
                   vel_pattern=[1.0, 0.75, 0.9, 0.75, 0.95, 0.75, 0.9, 0.75])
    pad_v = voice_lead([s[2] for s in sg], 4, 55, 72, 63)
    pad = chord_notes(sg, pad_v, vel=0.55)
    # brass stabs in the B section and return; sustained brass in the bridge
    brass = []
    for (beat, beats, sym), v in zip(sg, pad_v):
        bar_i = int(beat // 4)
        if 16 <= bar_i < 24 or 28 <= bar_i < 31:
            for m in v[1:]:
                brass.append(Note(beat, 0.45, m, 0.7))
                brass.append(Note(beat + 1.5, 0.45, m, 0.62))
        elif 24 <= bar_i < 28:
            for m in v[1:]:
                brass.append(Note(beat, 3.8, m, 0.6))
    main_k, main_s = "x..xx...", "..x...x."
    kick = hits(main_k, list(range(0, 16)) + list(range(28, 32)), vel=0.85)
    kick += hits("x.x.x.x.", range(16, 24), vel=0.85)
    kick += hits("x......x", range(24, 28), vel=0.8)
    snare = hits(main_s, [b for b in range(0, 16) if b not in (7, 15)] + [28, 29, 30], vel=0.8)
    snare += hits(main_s, range(16, 24), vel=0.82)
    snare += hits("....x...", range(24, 28), vel=0.85)
    # fills
    snare += hits("..x...x.", [7], vel=0.8) + [Note(7 * 4 + 3.5, 0.25, 60, 0.5), Note(7 * 4 + 3.75, 0.25, 60, 0.62)]
    snare += hits("..x.....", [15], vel=0.8)
    snare += [Note(31 * 4 + 2 + 0.25 * k, 0.25, 60, 0.4 + 0.07 * k) for k in range(8)]
    snare += [Note(23 * 4 + 3 + 0.25 * k, 0.25, 60, 0.5 + 0.1 * k) for k in range(4)]
    toms = [Note(15 * 4 + 3 + 0.25 * k, 0.25, m, 0.7) for k, m in enumerate([50, 47, 43, 40])]
    toms += [Note(27 * 4 + 2 + 0.5 * k, 0.5, m, 0.7) for k, m in enumerate([52, 50, 47, 43])]
    hat = hits("oxoxoxox", [b for b in range(32)], vel=0.55)
    ohat = [Note(b * 4 + 3.5, 0.5, 60, 0.5) for b in range(8, 24, 2)]
    crash = [Note(b * 4, 1, 60, 0.75) for b in (0, 8, 16, 24)] + [Note(28 * 4, 1, 60, 0.5)]
    timp = [Note(b * 4, 1, S.note_midi(n), 0.75) for b, n in ((24, "C3"), (25, "G2"), (26, "F2"), (27, "G2"))]
    tracks = [
        Track("lead", I.lead, lead, level=-19.5, reverb=0.2, delay=0.14, gate=0.9,
              kw=dict(vib_depth=0.14, vib_rate=5.8, vib_delay=0.22, width=0.3, attack=0.008, release=0.1)),
        Track("bass", I.bass, bass, level=-22.5, gate=0.8, kw=dict(pluck_amt=0.9, release=0.05, bright=1.3),
              variants=2),
        Track("ostinato", lambda f, d, v, sr, rng: I.pluck(f, d, v, sr, rng, t60=0.6, bright=0.7), ost,
              level=-28.0, reverb=0.25, delay=0.12, variants=2, humanize_ms=2),
        Track("pad", I.pad, pad, level=-28.5, reverb=0.3, kw=dict(cutoff=1600.0, attack=0.25, release=0.6),
              chorus=dict(voices=2, base_ms=12, depth_ms=3, rate_hz=0.4, mix=0.5)),
        Track("brass", lambda f, d, v, sr, rng: I.brass(f, d, v, sr, rng, voices=2, release=0.12), brass,
              level=-27.0, reverb=0.25),
        Track("kick", I.kick, kick, drum=True, level=-23.5, reverb=0.03),
        Track("snare", I.snare, snare, drum=True, level=-25.5, reverb=0.16, humanize_ms=2),
        Track("toms", _tom, toms, level=-29.0, reverb=0.2),
        Track("hat", I.hat, hat, drum=True, level=-33.0, reverb=0.05, humanize_ms=2, vel_jitter=0.1),
        Track("ohat", lambda v, sr, rng: I.hat(v, sr, rng, open_=True), ohat, drum=True, level=-35.0, reverb=0.1),
        Track("crash", I.crash, crash, drum=True, level=-31.0, reverb=0.2),
        Track("timpani", _timp, timp, level=-28.0, reverb=0.3),
    ]
    return Song("battle_theme", 150, 128, tracks, reverb_rt60=1.5, reverb_damping=0.6, delay_beats=0.75,
                delay_fb=0.28, delay_damp=3500.0)


# ---------------------------------------------------------------------------
# 5. shrine theme -- D minor / modal, 60 BPM, 3/4, 12 bars
# ---------------------------------------------------------------------------

def shrine_theme() -> Song:
    B = 3
    choir_chords = [  # (bar, bars, voicing, vowel, vowel_to)
        (0, 2, [50, 57, 62, 65], "u", "o"),   # Dm
        (2, 2, [50, 58, 62, 69], "o", "a"),   # Bbmaj7/D
        (4, 2, [50, 59, 62, 67], "a", "o"),   # G/D (dorian IV)
        (6, 2, [50, 57, 62, 65], "o", "u"),   # Dm
        (8, 2, [51, 58, 63, 67], "u", "a"),   # Eb/D (phrygian bII over the pedal)
        (10, 1, [52, 57, 62, 64], "a", "o"),  # Asus4
        (11, 1, [52, 57, 60, 64], "o", "u"),  # Am -> back to Dm
    ]
    choir = []
    for bar, nb, v, va, vb in choir_chords:
        for m in v:
            choir.append(Note(bar * B, nb * B, m, 0.6, dict(vowel=va, vowel_to=vb)))
    bells = mel("""
        D4:3 | r:3 | r:1 A4:1 F4:1 | r:3 | D5:1 B4:2 | r:3 |
        D4:3 | r:1 F4:1 E4:1 | Eb5:2 D5:1 | r:3 | A4:1.5 G4:.5 E4:1 | r:3 |""", bar=3, vel=0.6)
    heart = [Note(b * B, 1, 60, 0.85 if b % 2 == 0 else 0.75) for b in range(12)]
    rng = S.rng_for("shrine", "twinkles")
    tw = [Note(float(round(rng.uniform(0, 36) * 2) / 2), 0.5, S.note_midi(p), float(rng.uniform(0.3, 0.55)))
          for p in ["A6", "D7", "E6", "A6", "F6", "D7"]]

    def bell_voice(f, d, v, sr, rng):
        y = I.bell(f, d, v, sr, rng, ratio=1.41, index=1.6, t60=4.5, warm=0.5)
        return S.onepole_lp(y, sr, 4200.0)

    tracks = [
        Track("choir", lambda f, d, v, sr, rng, **kw: I.choir(f, d, v, sr, rng, attack=1.8, release=2.4,
                                                              voices=4, bright=1.4, **kw),
              choir, level=-23.0, reverb=0.5),
        Track("bells", bell_voice, bells, level=-27.5, reverb=0.85, delay=0.25),
        Track("heart", I.heartbeat, heart, drum=True, level=-27.0, reverb=0.12),
        Track("twinkle", I.twinkle, tw, level=-40.0, reverb=0.9),
    ]
    beds = [
        (drone([(S.hz("D2"), 1.0), (S.hz("A2"), 0.4), (S.hz("D1"), 0.25)], am_rate=0.09, am_depth=0.4,
               harmonics=5, bright=0.35), -30.0, 0.2),
        (air(250.0, 3000.0, 0.08, 0.7, color=1.2), -36.5, 0.4),
    ]
    return Song("shrine_theme", 60, 36, tracks, beds=beds, reverb_rt60=4.2, reverb_predelay=0.04,
                reverb_damping=0.5, delay_beats=1.5, delay_fb=0.4, delay_damp=2500.0)


# ---------------------------------------------------------------------------
# 6. victory fanfare -- C major, 120 BPM, one-shot (~6 s)
# ---------------------------------------------------------------------------

def victory_fanfare(sr: int = SR) -> Song:
    melody = mel("G4:.5 C5:.5 E5:1! D5:.5 E5:.5 G5:1.5 F5:.5 E5:.5 F5:.5 D5:1 G5:.5 B5:.5 C6:2!", vel=0.85)
    sg = [(0, 4, "C"), (4, 2, "F"), (6, 2, "G"), (8, 2, "C")]
    voicings = [[60, 64, 67], [60, 65, 69], [59, 62, 67], [60, 64, 67, 72]]
    brass = chord_notes(sg, voicings, vel=0.7)
    bass = mel("C2:2 G2:2 F2:2 G2:2 C2:2", vel=0.8)
    timp = [Note(0, 1, S.note_midi("C3"), 0.7), Note(4, 1, S.note_midi("F2"), 0.6)]
    timp += [Note(6 + 0.25 * k, 0.25, S.note_midi("G2"), 0.3 + 0.05 * k) for k in range(8)]
    timp += [Note(8, 1, S.note_midi("C3"), 0.95)]
    gliss = mel(" ".join(f"{p}:.125" for p in
                         "G3 A3 B3 C4 D4 E4 F4 G4 A4 B4 C5 D5 E5 F5 G5 A5".split()), start=6, vel=0.5)
    glock = mel("C6:.25 E6:.25 G6:.25 C7:1.25", start=8, vel=0.6)
    snare = [Note(7 + 0.125 * k, 0.125, 60, 0.25 + 0.06 * k) for k in range(8)] + [Note(0, 1, 60, 0.6)]
    crash = [Note(8, 1, 60, 0.85), Note(0, 1, 60, 0.45)]
    tracks = [
        Track("melody", lambda f, d, v, s_, rng: I.brass(f, d, v, s_, rng, voices=3, release=0.25), melody,
              level=-17.0, reverb=0.25, gate=0.95),
        Track("brass", lambda f, d, v, s_, rng: I.brass(f, d, v, s_, rng, voices=2, release=0.3, bright=0.8),
              brass, level=-21.0, reverb=0.3),
        Track("bass", I.bass, bass, level=-22.0, kw=dict(pluck_amt=0.3)),
        Track("timpani", _timp, timp, level=-23.0, reverb=0.3),
        Track("harp", I.harp, gliss, level=-25.0, reverb=0.35, kw=dict(ring=1.4)),
        Track("glock", I.glock, glock, level=-25.0, reverb=0.4),
        Track("snare", I.snare, snare, drum=True, level=-28.0, reverb=0.2),
        Track("crash", I.crash, crash, drum=True, level=-27.0, reverb=0.25),
    ]
    return Song("victory_fanfare", 120, 10, tracks, sr=sr, loop=False, tail=2.4, reverb_rt60=1.8)


# ---------------------------------------------------------------------------
# short jingles used by the SFX set (rendered at 44.1 kHz by sfx.py)
# ---------------------------------------------------------------------------

def victory_jingle_song(sr: int) -> Song:
    lead = mel("C5:.25 E5:.25 G5:.25 B5:.25 C6:1! G5:.5 C6:.5 E6:2.5!", vel=0.85)
    chip_arp = mel(" ".join(f"{p}:.25" for p in "C6 E6 G6 C7 G6 E6 C6 E6 G6 C7".split()), start=3, vel=0.45)
    sg = [(1, 1, "C"), (2, 1, "G"), (3, 2.5, "C")]
    brass = chord_notes(sg, [[60, 64, 67], [59, 62, 67], [60, 64, 67, 72]], vel=0.72)
    timp = [Note(1, 1, S.note_midi("C3"), 0.8), Note(2, 1, S.note_midi("G2"), 0.7), Note(3, 1, S.note_midi("C3"), 1.0)]
    snare = [Note(2 + 0.125 * k, 0.125, 60, 0.3 + 0.07 * k) for k in range(8)]
    crash = [Note(3, 1, 60, 0.8)]
    bass = mel("C2:1 G2:1 C2:2.5", start=1, vel=0.8)
    tracks = [
        Track("chip", lambda f, d, v, s_, rng: I.chip(f, d, v, s_, rng, duty=0.25), lead, level=-20.0,
              reverb=0.15, gate=0.9),
        Track("lead", lambda f, d, v, s_, rng: I.brass(f, d, v, s_, rng, voices=2), lead, level=-19.0, reverb=0.2),
        Track("arp", lambda f, d, v, s_, rng: I.chip(f, d, v, s_, rng, duty=0.125), chip_arp, level=-29.0,
              reverb=0.3, gate=0.7),
        Track("brass", lambda f, d, v, s_, rng: I.brass(f, d, v, s_, rng, voices=2, bright=0.8), brass,
              level=-22.0, reverb=0.25),
        Track("bass", I.bass, bass, level=-23.0),
        Track("timpani", _timp, timp, level=-23.0, reverb=0.25),
        Track("snare", I.snare, snare, drum=True, level=-29.0, reverb=0.15),
        Track("crash", I.crash, crash, drum=True, level=-27.0, reverb=0.2),
    ]
    return Song("victory_jingle", 150, 5.5, tracks, sr=sr, loop=False, tail=1.6, reverb_rt60=1.4)


def defeat_jingle_song(sr: int) -> Song:
    lead = mel("E5:.75 D5:.25 C5:.5 B4:.5 A4:2", vel=0.7)
    sg = [(0, 1.5, "Fmaj7"), (1.5, 0.5, "E"), (2, 2, "Am")]
    pad = chord_notes(sg, [[57, 60, 64, 65], [56, 59, 64, 68], [57, 60, 64, 71]], vel=0.5)
    harp = mel("F3:.25 C4:.25 E4:.25 A4:.25 C5:.5 E3:.25 G#3:.25 A2:.5 E3:.5 B3:.5 C4:.5", vel=0.5)
    bass = mel("F2:1.5 E2:.5 A1:2", vel=0.7)
    tracks = [
        Track("lead", lambda f, d, v, s_, rng: I.soft_sine(f, d, v, s_, rng, attack=0.05, release=0.45), lead,
              level=-20.0, reverb=0.35, gate=0.95),
        Track("pad", I.pad, pad, level=-25.0, reverb=0.35, kw=dict(cutoff=1000.0, attack=0.25, release=1.2)),
        Track("harp", I.harp, harp, level=-26.0, reverb=0.4, kw=dict(ring=2.0)),
        Track("bass", I.bass, bass, level=-26.0, kw=dict(pluck_amt=0.2, release=0.6)),
    ]
    return Song("defeat_jingle", 80, 4, tracks, sr=sr, loop=False, tail=1.8, reverb_rt60=2.0)


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

MUSIC = {
    "title_theme": title_theme,
    "village_theme": village_theme,
    "forest_theme": forest_theme,
    "battle_theme": battle_theme,
    "shrine_theme": shrine_theme,
    "victory_fanfare": victory_fanfare,
}
