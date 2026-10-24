"""Instrument voices shared by the music sequencer and the jingle-like SFX.

Every melodic voice has the signature ``voice(freq, dur, vel, sr, rng, **kw)``
where ``dur`` is the gate (note-on) time in seconds; the returned buffer may be
longer (release / ring-out).  Percussion voices take ``(vel, sr, rng, **kw)``.
Output peaks are roughly vel-scaled around 0.3..1.0 so mixes stay predictable.
"""

from __future__ import annotations

import math

import numpy as np

import synth as S


# ---------------------------------------------------------------------------
# melodic voices
# ---------------------------------------------------------------------------

def harp(f, dur, vel, sr, rng, t60=None, bright=None, ring=None):
    """Karplus-Strong harp: soft pluck position, pitch-dependent ring time."""
    if t60 is None:
        t60 = float(np.clip(3.2 * (220.0 / f) ** 0.5, 0.7, 4.5))
    if bright is None:
        bright = 0.25 + 0.45 * vel
    length = max(dur, min(t60 * 0.9, ring if ring is not None else 3.0))
    n = S.ns(length, sr)
    y = S.karplus(f, n, sr, rng, t60=t60, brightness=bright, pluck_pos=0.31)
    y = S.onepole_lp(y, sr, min(7000.0, f * 14.0))
    # gentle body warmth: a quiet sine at the fundamental with the same decay
    t = np.arange(n) / sr
    y = y + 0.18 * np.sin(S.TAU * f * t) * np.exp(-S.LN1000 * t / t60)
    env = np.ones(n)
    a = S.ns(0.0015, sr)
    env[:a] = np.linspace(0, 1, a)
    fo = S.ns(min(0.25, length * 0.3), sr)
    env[-fo:] *= np.linspace(1, 0, fo) ** 2
    return y * env * (0.55 * vel ** 1.3)


def pluck(f, dur, vel, sr, rng, t60=None, bright=0.75):
    """Brighter, shorter pluck (mandolin / ukulele-ish) for the village melody."""
    if t60 is None:
        t60 = float(np.clip(1.4 * (330.0 / f) ** 0.4, 0.45, 2.0))
    length = max(dur + 0.15, min(t60, 1.6))
    n = S.ns(length, sr)
    y = S.karplus(f, n, sr, rng, t60=t60, brightness=bright * (0.6 + 0.4 * vel), pluck_pos=0.17)
    t = np.arange(n) / sr
    body = np.sin(S.TAU * f * t) * np.exp(-S.LN1000 * t / (t60 * 0.7))
    y = 0.85 * y + 0.3 * body
    # damp after the gate like a palm-muted string
    damp = np.where(t < dur + 0.05, 1.0, np.exp(-(t - dur - 0.05) / 0.06))
    env = damp
    a = S.ns(0.001, sr)
    env[:a] *= np.linspace(0, 1, a)
    fo = S.ns(0.02, sr)
    env[-fo:] *= np.linspace(1, 0, fo)
    return S.onepole_lp(y * env, sr, 6500.0) * (0.6 * vel ** 1.2)


def lead(f, dur, vel, sr, rng, vib_depth=0.17, vib_rate=5.3, vib_delay=0.28, width=0.33,
         bright=1.0, attack=0.014, release=0.16, scoop=True):
    """Soft pulse/triangle lead with delayed vibrato and a gentle swept lowpass."""
    n = S.ns(dur + release, sr)
    t = np.arange(n) / sr
    vib_env = np.clip((t - vib_delay) / 0.3, 0.0, 1.0) ** 1.5
    rate = vib_rate * (1.0 + 0.04 * rng.uniform(-1, 1))
    cents = vib_depth * 100.0 * vib_env * np.sin(S.TAU * rate * t + rng.uniform(0, S.TAU))
    if scoop:
        cents = cents - 22.0 * np.exp(-t / 0.035)
    fr = f * 2.0 ** (cents / 1200.0)
    pw = width + 0.06 * np.sin(S.TAU * 0.9 * t)
    osc = 0.62 * S.pulse(fr, n, sr, pw) + 0.5 * S.tri(fr, n, sr)
    amp = S.adsr(n, sr, a=attack, d=0.35, s=0.78, r=release, gate=dur)
    fc = np.minimum(f * 4.5 + 900.0, 4200.0) * bright * (0.55 + 0.45 * amp) * (0.75 + 0.25 * vel)
    y = S.svf(osc, sr, fc, 0.6, "lp")
    return y * amp * (0.42 * vel)


def chip(f, dur, vel, sr, rng, duty=0.25, vib_depth=0.12, release=0.08):
    """Chiptune-flavoured pulse, softened (used sparingly in jingles)."""
    n = S.ns(dur + release, sr)
    t = np.arange(n) / sr
    cents = vib_depth * 100.0 * np.clip((t - 0.15) / 0.2, 0, 1) * np.sin(S.TAU * 6.0 * t)
    fr = f * 2.0 ** (cents / 1200.0)
    y = S.pulse(fr, n, sr, duty)
    y = S.svf(y, sr, min(f * 6.0, 6500.0), 0.7, "lp")
    amp = S.adsr(n, sr, a=0.004, d=0.12, s=0.7, r=release, gate=dur)
    return y * amp * 0.32 * vel


def bass(f, dur, vel, sr, rng, pluck_amt=0.6, release=0.09, bright=1.0):
    """Warm triangle/sine bass with a plucky brightness envelope (additive, alias-free)."""
    n = S.ns(dur + release, sr)
    t = np.arange(n) / sr
    fr = f * (1.0 + 0.018 * pluck_amt * np.exp(-t / 0.012))
    amps = 0.75 * S.harmonic_amps("tri", 16) + 0.25 * S.harmonic_amps("saw", 16)
    amps[0] += 0.6
    fc = f * (1.6 + bright * (2.0 + 9.0 * pluck_amt * vel * np.exp(-t / 0.09)))
    y = S.additive(fr, n, sr, amps, lowpass=np.minimum(fc, 3000.0), order=1.5)
    amp = S.adsr(n, sr, a=0.004, d=0.35, s=1.0 - 0.45 * pluck_amt, r=release, gate=dur)
    return y * amp * (0.5 * vel)


def pad(f, dur, vel, sr, rng, cutoff=1500.0, attack=0.7, release=1.2, detune=8.0, voices=3,
        sustain=0.85, sub=0.0, open_amt=0.6):
    """Mellow pad: detuned saws through a slowly opening lowpass (additive)."""
    n = S.ns(dur + release, sr)
    t = np.arange(n) / sr
    amp = S.adsr(n, sr, a=attack, d=1.0, s=sustain, r=release, gate=dur)
    fc = cutoff * (1.0 - open_amt + open_amt * np.clip(t / (attack * 1.6 + 1e-3), 0, 1) ** 0.7)
    fc = np.minimum(fc, cutoff * (0.6 + 0.4 * amp / max(amp.max(), 1e-9)) + 50.0)
    kmax = int(min(48, (0.45 * sr) / f))
    amps = S.harmonic_amps("saw", max(kmax, 1))
    y = np.zeros(n)
    for v in range(voices):
        c = 0.0 if voices == 1 else detune * (2.0 * v / (voices - 1) - 1.0)
        drift = 2.0 * np.sin(S.TAU * (0.13 + 0.05 * v) * t + rng.uniform(0, S.TAU))
        fr = f * 2.0 ** ((c + drift) / 1200.0)
        y += S.additive(fr, n, sr, amps, phase0=rng.uniform(0, 1), lowpass=fc, order=2.0)
    if sub > 0:
        y += sub * np.sin(S.TAU * S.phase_cycles(f * 0.5, n, sr))
    return y * amp * (0.22 * vel / math.sqrt(voices))


def choir(f, dur, vel, sr, rng, vowel="a", vowel_to=None, attack=1.0, release=1.6, voices=4,
          detune=7.0, breath=0.08, bw_scale=1.6, bright=1.0):
    """Choir-like pad: ensemble of saw-source voices through vowel formants.

    The vowel can morph (vowel -> vowel_to) over the note.  Each voice has its
    own slow vibrato and pitch drift, which gives the ensemble shimmer.
    """
    n = S.ns(dur + release, sr)
    t = np.arange(n) / sr
    amp = S.adsr(n, sr, a=attack, d=1.2, s=0.9, r=release, gate=dur)
    fa = S.VOWELS[vowel]
    fb = S.VOWELS[vowel_to] if vowel_to else fa
    # formants evaluated on a coarse grid then interpolated (cheap & smooth)
    step = 64
    grid = np.arange(0, n + step, step)
    u = np.clip(grid / max(n - 1, 1), 0, 1)
    u = 0.5 - 0.5 * np.cos(np.pi * u)
    kmax = int(min(60, (0.45 * sr) / f))
    k_idx = np.arange(1, max(kmax, 1) + 1)
    # saw source with a gentle extra rolloff (softer than a raw saw)
    amps = S.harmonic_amps("saw", max(kmax, 1)) / (1.0 + (k_idx * f / (3500.0 * bright)) ** 2)
    out = np.zeros(n)
    sample_idx = np.arange(n)

    for v in range(voices):
        c = detune * (2.0 * v / max(voices - 1, 1) - 1.0) + rng.uniform(-2, 2)
        vr = 4.6 + 0.8 * rng.uniform()
        vib = 11.0 * np.clip((t - 0.35) / 0.6, 0, 1) * np.sin(S.TAU * vr * t + rng.uniform(0, S.TAU))
        drift = 3.0 * S.lfo_noise(n, sr, 0.7, rng)
        fr = f * 2.0 ** ((c + vib + drift) / 1200.0)
        fmean = f * 2.0 ** (c / 1200.0)

        def spectral(fk, k, fmean=fmean):
            # formant gain at the (mean) harmonic frequency; vowel morph = gain crossfade
            fkm = np.array([k * fmean])
            ga = float(S.formant_gain(fkm, fa, bw_scale)[0])
            if fb is fa:
                return ga
            gb = float(S.formant_gain(fkm, fb, bw_scale)[0])
            return np.interp(sample_idx, grid, ga + (gb - ga) * u)

        out += S.additive(fr, n, sr, amps, phase0=rng.uniform(0, 1), spectral=spectral)
    if breath > 0:
        noise = S.fft_filter(rng.standard_normal(n), sr,
                             lambda fr_: S.formant_gain(fr_, fa, 2.5, floor=0.0) * (fr_ > 200))
        out += breath * noise / (np.std(noise) + 1e-9) * 0.25
    return out * amp * (0.16 * vel / math.sqrt(voices))


def glock(f, dur, vel, sr, rng, t60=None, bright=1.0):
    """Glockenspiel: struck-bar modes (1, 2.76, 5.40, 8.93) + mallet tick."""
    base = float(np.clip(1.9 * (1000.0 / f) ** 0.35, 0.7, 2.6)) if t60 is None else t60
    n = S.ns(base * 1.05, sr)
    ratios = [1.0, 2.756, 5.404, 8.933]
    amps = [1.0, 0.32 * bright, 0.12 * bright, 0.05 * bright]
    decs = [base, base * 0.32, base * 0.14, base * 0.07]
    y = S.modal([f * r for r in ratios], decs, amps, n, sr, rng, attack=0.0008)
    tick = S.fft_filter(rng.standard_normal(S.ns(0.006, sr)), sr, S.mag_hp(3000.0)) * \
        S.perc(S.ns(0.006, sr), sr, 0.0003, 0.004)
    y[:len(tick)] += 0.08 * bright * tick
    return y * 0.42 * vel


def bell(f, dur, vel, sr, rng, ratio=1.4, index=2.2, t60=3.2, index_t60=1.2, warm=0.35):
    """FM bell (inharmonic) with a warm octave partial; long natural decay."""
    n = S.ns(t60 * 1.05, sr)
    t = np.arange(n) / sr
    idx = index * (0.25 + 0.75 * np.exp(-S.LN1000 * t / index_t60)) * (0.6 + 0.4 * vel)
    y = S.fm(f, n, sr, ratio, idx) * S.perc(n, sr, 0.0015, t60)
    y += warm * S.modal([f * 2.0, f * 0.5], [t60 * 0.6, t60 * 1.1], [0.5, 0.35], n, sr, rng, attack=0.004)
    return y * 0.33 * vel


def celesta(f, dur, vel, sr, rng, t60=None):
    """Warm chime (celesta / music-box tine): near-harmonic partials, soft attack."""
    base = float(np.clip(1.6 * (800.0 / f) ** 0.4, 0.6, 2.4)) if t60 is None else t60
    n = S.ns(base * 1.05, sr)
    y = S.modal([f, f * 2.0, f * 3.0, f * 4.07, f * 6.3], [base, base * 0.5, base * 0.3, base * 0.18, base * 0.06],
                [1.0, 0.28, 0.1, 0.05, 0.06], n, sr, rng, attack=0.0025)
    return y * 0.45 * vel


def twinkle(f, dur, vel, sr, rng):
    """Tiny high glint (forest sparkles): sine + light FM, quick decay."""
    n = S.ns(0.9, sr)
    t = np.arange(n) / sr
    idx = 1.2 * np.exp(-t / 0.05)
    y = S.fm(f, n, sr, 3.01, idx) * S.perc(n, sr, 0.002, 0.8)
    return y * 0.25 * vel


def brass(f, dur, vel, sr, rng, voices=2, release=0.2, bright=1.0, vib=True):
    """Synth brass: saws with a fast-opening lowpass "blat", pitch scoop, delayed vibrato."""
    n = S.ns(dur + release, sr)
    t = np.arange(n) / sr
    amp = S.adsr(n, sr, a=0.022, d=0.25, s=0.82, r=release, gate=dur)
    open_env = 1.0 - np.exp(-t / 0.035)
    settle = 0.7 + 0.3 * np.exp(-t / 0.25)
    fc = f * (1.2 + bright * (2.0 + 4.5 * vel) * open_env * settle) * (0.4 + 0.6 * amp / max(amp.max(), 1e-9))
    fc = np.minimum(fc, 7000.0)
    kmax = int(min(40, (0.45 * sr) / f))
    amps = S.harmonic_amps("saw", max(kmax, 1))
    y = np.zeros(n)
    for v in range(voices):
        c = 0.0 if voices == 1 else 6.0 * (2.0 * v / (voices - 1) - 1.0)
        cents = c - 35.0 * np.exp(-t / 0.03)
        if vib:
            cents = cents + 12.0 * np.clip((t - 0.3) / 0.3, 0, 1) * np.sin(S.TAU * 5.0 * t + v)
        y += S.additive(f * 2.0 ** (cents / 1200.0), n, sr, amps, phase0=rng.uniform(0, 1),
                        lowpass=fc, order=2.0)
    return y * amp * (0.3 * vel / math.sqrt(voices))


def soft_sine(f, dur, vel, sr, rng, attack=0.02, release=0.3, harm=0.15):
    """Flute-ish soft sine with a touch of 2nd/3rd harmonic (defeat jingle, hums)."""
    n = S.ns(dur + release, sr)
    t = np.arange(n) / sr
    vibc = 9.0 * np.clip((t - 0.25) / 0.3, 0, 1) * np.sin(S.TAU * 4.8 * t)
    fr = f * 2.0 ** (vibc / 1200.0)
    ph = S.phase_cycles(fr, n, sr)
    y = np.sin(S.TAU * ph) + harm * np.sin(2 * S.TAU * ph) + 0.4 * harm * np.sin(3 * S.TAU * ph)
    amp = S.adsr(n, sr, a=attack, d=0.4, s=0.85, r=release, gate=dur)
    return y * amp * 0.4 * vel


# ---------------------------------------------------------------------------
# percussion
# ---------------------------------------------------------------------------

def kick(vel, sr, rng, soft=False, length=0.45):
    n = S.ns(length, sr)
    f = S.pitch_drop(125.0 if soft else 165.0, 46.0, 0.03 if soft else 0.026, n, sr)
    body = np.sin(S.TAU * S.phase_cycles(f, n, sr)) * S.perc(n, sr, 0.0012, 0.32 if soft else 0.4, curve_pow=1.4)
    nc = S.ns(0.006, sr)
    click = S.fft_filter(rng.standard_normal(nc), sr, S.mag_bp(800.0, 5000.0)) * S.perc(nc, sr, 0.0003, 0.005)
    y = body
    y[:nc] += (0.05 if soft else 0.16) * click
    y = S.softclip(y * 1.2, 1.4)
    return y * 0.9 * vel


def snare(vel, sr, rng, brush=False, length=None):
    if brush:
        n = S.ns(length or 0.32, sr)
        noise = S.fft_filter(rng.standard_normal(n), sr, S.mag_mul(S.mag_bp(1200.0, 7000.0, 1.5),
                                                                    S.mag_reso(3500.0, 5000.0, 0.4)))
        noise /= np.std(noise) + 1e-9
        env = S.perc(n, sr, 0.006, 0.24, curve_pow=0.9)
        tone = np.sin(S.TAU * 190.0 * np.arange(n) / sr) * S.perc(n, sr, 0.002, 0.08)
        return (0.32 * noise * env + 0.18 * tone) * vel
    n = S.ns(length or 0.36, sr)
    noise = S.fft_filter(rng.standard_normal(n), sr, S.mag_bp(900.0, 9000.0, 1.5))
    noise /= np.std(noise) + 1e-9
    nenv = S.perc(n, sr, 0.0008, 0.26, curve_pow=1.15)
    tf = S.pitch_drop(240.0, 182.0, 0.02, n, sr)
    tone = np.sin(S.TAU * S.phase_cycles(tf, n, sr)) * S.perc(n, sr, 0.0008, 0.11)
    tone += 0.4 * np.sin(S.TAU * S.phase_cycles(tf * 1.68, n, sr)) * S.perc(n, sr, 0.0008, 0.06)
    y = 0.42 * noise * nenv + 0.6 * tone
    return S.softclip(y, 1.6) * 0.75 * vel


def hat(vel, sr, rng, open_=False, length=None):
    n = S.ns(length or (0.42 if open_ else 0.09), sr)
    ratios = [1.0, 1.4471, 1.6170, 1.9265, 2.5028, 2.6637]
    metal = sum(S.pulse(330.0 * r * (1 + 0.002 * rng.uniform(-1, 1)), n, sr, 0.5, rng.uniform()) for r in ratios)
    noise = rng.standard_normal(n)
    y = 0.5 * metal / 6.0 + 0.6 * noise
    y = S.fft_filter(y, sr, S.mag_mul(S.mag_hp(7000.0, 2.0), S.mag_lp(15000.0, 1.0)))
    y /= np.std(y) + 1e-9
    env = S.perc(n, sr, 0.0006, 0.3 if open_ else 0.045, curve_pow=1.2)
    return y * env * 0.16 * vel


def shaker(vel, sr, rng, length=0.12):
    n = S.ns(length, sr)
    noise = S.fft_filter(rng.standard_normal(n), sr, S.mag_bp(4500.0, 11000.0, 2.0))
    noise /= np.std(noise) + 1e-9
    t = np.arange(n) / sr
    env = np.clip(t / 0.012, 0, 1) ** 1.5 * np.exp(-S.LN1000 * np.maximum(t - 0.012, 0) / 0.09)
    return noise * env * 0.09 * vel


def crash(vel, sr, rng, length=2.2, bright=1.0):
    n = S.ns(length, sr)
    k = 48
    freqs = np.exp(rng.uniform(math.log(2200.0), math.log(11000.0), k))
    metal = S.modal(freqs, rng.uniform(0.6, 1.7, k) * length * 0.7, rng.uniform(0.3, 1.0, k) / k * 4, n, sr, rng)
    noise = S.fft_filter(rng.standard_normal(n), sr, S.mag_bp(3000.0, 14000.0, 1.0))
    noise /= np.std(noise) + 1e-9
    y = 0.6 * metal + 0.25 * noise * S.perc(n, sr, 0.001, length * 0.8)
    y *= S.perc(n, sr, 0.0015, length)
    y = S.onepole_lp(y, sr, 9000.0 * bright)
    return y * 0.35 * vel


def timpani(f, vel, sr, rng, length=1.6):
    n = S.ns(length, sr)
    t = np.arange(n) / sr
    pe = 1.0 + 0.04 * np.exp(-t / 0.03)
    ratios = [1.0, 1.504, 1.742, 2.0, 2.245, 2.494]
    decs = [1.5, 1.0, 0.75, 0.65, 0.5, 0.4]
    amps = [1.0, 0.55, 0.3, 0.28, 0.16, 0.1]
    y = S.modal([f * r for r in ratios], [d * length / 1.6 for d in decs], amps, n, sr, rng, pitch_env=pe,
                attack=0.002)
    nm = S.ns(0.05, sr)
    thump = S.fft_filter(rng.standard_normal(nm), sr, S.mag_lp(500.0, 2.0)) * S.perc(nm, sr, 0.001, 0.04)
    y[:nm] += 0.4 * thump / (np.std(thump) + 1e-9) * 0.3
    return S.softclip(y * 0.6, 1.2) * 0.8 * vel


def tom(f, vel, sr, rng, length=0.6):
    n = S.ns(length, sr)
    fr = S.pitch_drop(f * 1.5, f, 0.045, n, sr)
    y = np.sin(S.TAU * S.phase_cycles(fr, n, sr)) * S.perc(n, sr, 0.001, length * 0.8)
    nn = S.ns(0.08, sr)
    noise = S.fft_filter(rng.standard_normal(nn), sr, S.mag_bp(300.0, 3000.0)) * S.perc(nn, sr, 0.0005, 0.06)
    y[:nn] += 0.25 * noise / (np.std(noise) + 1e-9) * 0.4
    return S.softclip(y, 1.3) * 0.7 * vel


def heartbeat(vel, sr, rng):
    """Deep 'lub-dub' pulse (shrine)."""
    def thump(f0, f1, t60, n):
        fr = S.pitch_drop(f0, f1, 0.04, n, sr)
        body = np.sin(S.TAU * S.phase_cycles(fr, n, sr)) * S.perc(n, sr, 0.006, t60, curve_pow=1.3)
        noise = S.fft_filter(rng.standard_normal(n), sr, S.mag_lp(180.0, 2.0))
        noise /= np.std(noise) + 1e-9
        return body + 0.12 * noise * S.perc(n, sr, 0.004, t60 * 0.6)
    n1 = S.ns(0.5, sr)
    lub = thump(72.0, 44.0, 0.32, n1)
    dub = thump(80.0, 50.0, 0.26, n1)
    out = np.zeros(S.ns(0.85, sr))
    S.place(out, lub, 0, 1.0)
    S.place(out, dub, S.ns(0.27, sr), 0.7)
    return out * 0.8 * vel


def clap(vel, sr, rng, length=0.3):
    n = S.ns(length, sr)
    noise = S.fft_filter(rng.standard_normal(n), sr, S.mag_bp(900.0, 4000.0, 1.5))
    noise /= np.std(noise) + 1e-9
    t = np.arange(n) / sr
    env = np.zeros(n)
    for i, off in enumerate([0.0, 0.009, 0.019, 0.028]):
        env += (0.7 if i < 3 else 1.0) * np.where(t >= off, np.exp(-(t - off) / (0.006 if i < 3 else 0.09)), 0.0)
    return noise * env * 0.25 * vel
