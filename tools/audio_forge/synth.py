"""Wildbound audio forge -- a tiny, numpy-only DSP / synthesis toolkit.

Conventions
-----------
* Signals are mono float64 numpy arrays, nominal range [-1, 1].
* Every function takes an explicit sample rate ``sr``; there is no global state.
* Randomness always comes from an explicit ``np.random.Generator`` (see
  :func:`rng_for`) so that every build is bit-for-bit deterministic.
* Any "frequency", "cutoff", "width", ... parameter may be a scalar or a
  per-sample array (a *curve*); see :func:`as_curve` / :func:`curve`.
* Recursive filters (biquad, SVF, one-pole) run as tight pure-Python loops
  (~3M samples/s on CPython 3.13) so that cutoffs can be swept per sample.
  Everything that can be vectorised (oscillators, additive synthesis, FFT
  filtering, convolution reverb, circular delays) is vectorised.
* "Circular" variants (``circular=True``) treat the buffer as a loop: tails
  wrap around to the start, which is how seamless loops are rendered.
"""

from __future__ import annotations

import hashlib
import math
import struct
import wave
from typing import Callable, Sequence

import numpy as np

TAU = 2.0 * math.pi
SFX_SR = 44100
MUSIC_SR = 32000
LN1000 = math.log(1000.0)  # exp(-LN1000 * t / t60) reaches -60 dB at t60


# ---------------------------------------------------------------------------
# basics
# ---------------------------------------------------------------------------

def rng_for(*keys) -> np.random.Generator:
    """Deterministic RNG seeded from any description (stable across runs)."""
    digest = hashlib.sha256("|".join(str(k) for k in keys).encode("utf-8")).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "little"))


def ns(dur: float, sr: int) -> int:
    """Seconds -> sample count (rounded, never negative)."""
    return max(0, int(round(dur * sr)))


def tvec(n: int, sr: int) -> np.ndarray:
    return np.arange(n) / sr


def db2a(db: float) -> float:
    return 10.0 ** (db / 20.0)


def a2db(a: float) -> float:
    return 20.0 * math.log10(max(abs(float(a)), 1e-12))


def midi_hz(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=float) - 69.0) / 12.0)


_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def note_midi(name: str) -> int:
    """'C4' -> 60, 'F#5' -> 78, 'Bb3' -> 58."""
    name = name.strip()
    pc = _PC[name[0].upper()]
    i = 1
    while i < len(name) and name[i] in "#b":
        pc += 1 if name[i] == "#" else -1
        i += 1
    return 12 * (int(name[i:]) + 1) + pc


def hz(name: str) -> float:
    return float(midi_hz(note_midi(name)))


def as_curve(v, n: int) -> np.ndarray:
    """Scalar -> constant array; array of another length -> resampled to n."""
    a = np.asarray(v, dtype=float)
    if a.ndim == 0:
        return np.full(n, float(a))
    if len(a) == n:
        return a
    if len(a) == 0:
        return np.zeros(n)
    return np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a)


def curve(points: Sequence[tuple[float, float]], n: int, sr: int, mode: str = "lin") -> np.ndarray:
    """Piecewise curve through (time_s, value) points, holding the end values.

    mode: 'lin' linear, 'exp' geometric (frequencies; values > 0),
          'cos' cosine-eased segments (smooth, zero slope at each point).
    """
    ts = np.array([p[0] for p in points], dtype=float)
    vs = np.array([p[1] for p in points], dtype=float)
    t = np.arange(n) / sr
    if len(ts) == 1:
        return np.full(n, vs[0])
    if mode == "exp":
        return np.exp(np.interp(t, ts, np.log(np.maximum(vs, 1e-12))))
    if mode == "cos":
        idx = np.clip(np.searchsorted(ts, t, side="right") - 1, 0, len(ts) - 2)
        t0, t1 = ts[idx], ts[idx + 1]
        u = np.clip((t - t0) / np.maximum(t1 - t0, 1e-12), 0.0, 1.0)
        u = 0.5 - 0.5 * np.cos(np.pi * u)
        return vs[idx] + (vs[idx + 1] - vs[idx]) * u
    return np.interp(t, ts, vs)


def pitch_drop(f_start: float, f_end: float, tau: float, n: int, sr: int) -> np.ndarray:
    """Exponential approach from f_start to f_end with time constant tau (kick/thud bodies)."""
    t = np.arange(n) / sr
    return f_end + (f_start - f_end) * np.exp(-t / max(tau, 1e-6))


def lfo_noise(n: int, sr: int, rate: float, rng: np.random.Generator) -> np.ndarray:
    """Smooth random control signal (~rate Hz bandwidth), normalised to peak 1.

    Generated in the FFT domain, so it is periodic in n: safe for loops.
    """
    if n < 4:
        return np.zeros(n)
    spec = rng.standard_normal(n // 2 + 1) + 1j * rng.standard_normal(n // 2 + 1)
    f = np.fft.rfftfreq(n, 1.0 / sr)
    spec *= np.exp(-0.5 * (f / max(rate, 1e-3)) ** 2)
    spec[0] = 0.0
    x = np.fft.irfft(spec, n)
    return x / (np.max(np.abs(x)) + 1e-12)


# ---------------------------------------------------------------------------
# envelopes
# ---------------------------------------------------------------------------

def adsr(n: int, sr: int, a: float = 0.005, d: float = 0.1, s: float = 0.7, r: float = 0.1,
         gate: float | None = None, a_shape: float = 1.0) -> np.ndarray:
    """ADSR with linear attack and exponential decay/release.

    ``d``/``r`` are the times to (almost) reach the target (4-5 time constants).
    ``gate`` is the note-on time in seconds (default: n/sr - r).
    """
    t = np.arange(n) / sr
    if gate is None:
        gate = max(0.0, n / sr - r)

    def held(tt):
        if a > 0:
            att = np.clip(tt / a, 0.0, 1.0) ** a_shape
        else:
            att = np.ones_like(tt)
        dec = s + (1.0 - s) * np.exp(-np.maximum(tt - a, 0.0) / max(d / 4.0, 1e-5))
        return np.where(tt < a, att, dec)

    env = held(t)
    lg = float(held(np.array([gate]))[0])
    rel = lg * np.exp(-np.maximum(t - gate, 0.0) / max(r / 5.0, 1e-5))
    env = np.where(t >= gate, rel, env)
    m = min(n, ns(0.003, sr))
    if m > 1:
        env[-m:] *= np.linspace(1.0, 0.0, m)
    return env


def perc(n: int, sr: int, attack: float = 0.002, t60: float = 0.5, hold: float = 0.0,
         curve_pow: float = 1.0) -> np.ndarray:
    """Percussive envelope: fast (sine-shaped) attack, optional hold, exponential decay to -60 dB at t60.

    curve_pow > 1 makes the decay start slower and finish faster (more "solid" body).
    """
    t = np.arange(n) / sr
    if attack > 0:
        att = np.sin(0.5 * np.pi * np.clip(t / attack, 0.0, 1.0))
    else:
        att = np.ones(n)
    td = np.maximum(t - attack - hold, 0.0)
    if curve_pow == 1.0:
        dec = np.exp(-LN1000 * td / t60)
    else:
        dec = np.exp(-LN1000 * (td / t60) ** curve_pow)
    return att * dec


def swell(n: int, sr: int, rise: float, fall: float, peak_at: float | None = None,
          shape: float = 2.0) -> np.ndarray:
    """Smooth bell-ish envelope: rises over `rise` s (power curve) then decays over `fall` s."""
    t = np.arange(n) / sr
    p = rise if peak_at is None else peak_at
    up = np.clip(t / max(p, 1e-6), 0.0, 1.0) ** shape
    down = np.exp(-LN1000 * np.maximum(t - p, 0.0) / max(fall, 1e-6))
    return np.where(t < p, up, down)


# ---------------------------------------------------------------------------
# oscillators
# ---------------------------------------------------------------------------

def phase_cycles(freq, n: int, sr: int, phase0: float = 0.0) -> np.ndarray:
    """Running phase in cycles (unwrapped); first sample = phase0."""
    f = as_curve(freq, n)
    ph = np.empty(n)
    if n == 0:
        return ph
    ph[0] = 0.0
    np.cumsum(f[:-1], out=ph[1:])
    ph /= sr
    ph += phase0
    return ph


def _frac(x: np.ndarray) -> np.ndarray:
    return x - np.floor(x)


def sine(freq, n: int, sr: int, phase0: float = 0.0) -> np.ndarray:
    return np.sin(TAU * phase_cycles(freq, n, sr, phase0))


def tri(freq, n: int, sr: int, phase0: float = 0.0) -> np.ndarray:
    """Naive triangle (harmonics fall at 12 dB/oct, aliasing is negligible). Starts at 0, rising."""
    p = _frac(phase_cycles(freq, n, sr, phase0 + 0.25))
    return 1.0 - 4.0 * np.abs(p - 0.5)


def _blep(p: np.ndarray, dt: np.ndarray) -> np.ndarray:
    out = np.zeros_like(p)
    m = p < dt
    x = p[m] / dt[m]
    out[m] = x + x - x * x - 1.0
    m = p > 1.0 - dt
    x = (p[m] - 1.0) / dt[m]
    out[m] = x * x + x + x + 1.0
    return out


def saw(freq, n: int, sr: int, phase0: float = 0.0) -> np.ndarray:
    """PolyBLEP band-limited sawtooth (rising)."""
    f = as_curve(freq, n)
    dt = np.clip(np.abs(f) / sr, 1e-9, 0.5)
    p = _frac(phase_cycles(f, n, sr, phase0))
    return 2.0 * p - 1.0 - _blep(p, dt)


def pulse(freq, n: int, sr: int, width=0.5, phase0: float = 0.0) -> np.ndarray:
    """PolyBLEP band-limited pulse; ``width`` may be a curve (PWM). DC-free."""
    f = as_curve(freq, n)
    dt = np.clip(np.abs(f) / sr, 1e-9, 0.5)
    p = _frac(phase_cycles(f, n, sr, phase0))
    w = np.clip(as_curve(width, n), 0.03, 0.97)
    y = np.where(p < w, 1.0, -1.0)
    y += _blep(p, dt)
    y -= _blep(_frac(p - w), dt)
    return y - (2.0 * w - 1.0)


def harmonic_amps(kind: str, k_max: int, width: float = 0.5) -> np.ndarray:
    """Harmonic amplitude series for additive synthesis (index 0 = fundamental)."""
    k = np.arange(1, k_max + 1, dtype=float)
    if kind == "saw":
        return 1.0 / k
    if kind == "square":
        return np.where(k % 2 == 1, 1.0 / k, 0.0)
    if kind == "tri":
        return np.where(k % 2 == 1, ((-1.0) ** ((k - 1) // 2)) / (k * k), 0.0)
    if kind == "pulse":
        return np.abs(np.sin(np.pi * k * width)) / k
    if kind == "sine":
        a = np.zeros(k_max)
        a[0] = 1.0
        return a
    raise ValueError(kind)


def additive(freq, n: int, sr: int, amps, phase0: float = 0.0, lowpass=None, order: float = 2.0,
             spectral: Callable[[np.ndarray, int], np.ndarray] | None = None) -> np.ndarray:
    """Band-limited additive oscillator.

    amps:     harmonic amplitudes (k = 1..K).
    lowpass:  optional cutoff (Hz, scalar or curve) applied per harmonic as a
              smooth Butterworth-like magnitude 1/sqrt(1+(fk/fc)^(2*order)).
              This is how "detuned saws through a swept lowpass" are rendered
              without recursive filters.
    spectral: optional fn(fk_curve, k) -> gain curve (formants, tilts ...).
    Harmonics are generated by complex recurrence z_k = z_1^k (exact for
    time-varying pitch) and faded out smoothly towards Nyquist.
    """
    f = as_curve(freq, n)
    if n == 0:
        return np.zeros(0)
    z1 = np.exp(1j * TAU * _frac(phase_cycles(f, n, sr, phase0)))
    zk = np.ones(n, dtype=np.complex128)
    out = np.zeros(n)
    nyq = 0.5 * sr
    fmin = float(np.min(f))
    fc = None if lowpass is None else np.maximum(as_curve(lowpass, n), 1.0)
    for k in range(1, len(amps) + 1):
        zk *= z1
        a = float(amps[k - 1])
        if a == 0.0:
            continue
        if k * fmin >= 0.95 * nyq:
            break
        fk = k * f
        g = a * np.clip((0.95 * nyq - fk) / (0.15 * nyq), 0.0, 1.0)
        if fc is not None:
            g = g / np.sqrt(1.0 + (fk / fc) ** (2.0 * order))
        if spectral is not None:
            g = g * spectral(fk, k)
        out += g * zk.imag
    return out


# ---------------------------------------------------------------------------
# noise
# ---------------------------------------------------------------------------

def white(n: int, rng: np.random.Generator) -> np.ndarray:
    return rng.standard_normal(n)


def colored(n: int, rng: np.random.Generator, exponent: float = 1.0, sr: int = SFX_SR,
            fmin: float = 15.0) -> np.ndarray:
    """Gaussian noise with a 1/f^exponent power spectrum (0 white, 1 pink, 2 brown).

    Built in the FFT domain, so it is exactly periodic in n (seamless loops).
    Normalised to unit standard deviation.
    """
    if n < 2:
        return np.zeros(n)
    m = n // 2 + 1
    spec = rng.standard_normal(m) + 1j * rng.standard_normal(m)
    f = np.fft.rfftfreq(n, 1.0 / sr)
    spec *= 1.0 / np.maximum(f, fmin) ** (exponent / 2.0)
    spec[0] = 0.0
    x = np.fft.irfft(spec, n)
    return x / (np.std(x) + 1e-12)


def pink(n: int, rng: np.random.Generator, sr: int = SFX_SR) -> np.ndarray:
    return colored(n, rng, 1.0, sr)


def brown(n: int, rng: np.random.Generator, sr: int = SFX_SR) -> np.ndarray:
    return colored(n, rng, 2.0, sr)


# ---------------------------------------------------------------------------
# filters
# ---------------------------------------------------------------------------

def _rbj(kind: str, f0: float, sr: int, q: float = 0.7071, gain_db: float = 0.0):
    w0 = TAU * min(max(f0, 1.0), 0.49 * sr) / sr
    cw, sw = math.cos(w0), math.sin(w0)
    alpha = sw / (2.0 * q)
    A = 10.0 ** (gain_db / 40.0)
    if kind == "lp":
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "hp":
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "bp":  # constant 0 dB peak gain
        b = [alpha, 0.0, -alpha]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "notch":
        b = [1.0, -2 * cw, 1.0]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "peak":
        b = [1 + alpha * A, -2 * cw, 1 - alpha * A]
        a = [1 + alpha / A, -2 * cw, 1 - alpha / A]
    elif kind == "lowshelf":
        sa = 2 * math.sqrt(A) * alpha
        b = [A * ((A + 1) - (A - 1) * cw + sa), 2 * A * ((A - 1) - (A + 1) * cw),
             A * ((A + 1) - (A - 1) * cw - sa)]
        a = [(A + 1) + (A - 1) * cw + sa, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - sa]
    elif kind == "highshelf":
        sa = 2 * math.sqrt(A) * alpha
        b = [A * ((A + 1) + (A - 1) * cw + sa), -2 * A * ((A - 1) + (A + 1) * cw),
             A * ((A + 1) + (A - 1) * cw - sa)]
        a = [(A + 1) - (A - 1) * cw + sa, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - sa]
    else:
        raise ValueError(kind)
    return (b[0] / a[0], b[1] / a[0], b[2] / a[0], a[1] / a[0], a[2] / a[0])


def biquad(x: np.ndarray, kind: str, f0: float, sr: int, q: float = 0.7071, gain_db: float = 0.0) -> np.ndarray:
    """Static RBJ-cookbook biquad (transposed direct form II, causal)."""
    b0, b1, b2, a1, a2 = _rbj(kind, f0, sr, q, gain_db)
    xs = np.asarray(x, dtype=float).tolist()
    out = [0.0] * len(xs)
    z1 = z2 = 0.0
    for i, xi in enumerate(xs):
        yi = b0 * xi + z1
        z1 = b1 * xi - a1 * yi + z2
        z2 = b2 * xi - a2 * yi
        out[i] = yi
    return np.array(out)


def svf(x: np.ndarray, sr: int, fc, q=0.7071, mode: str = "lp") -> np.ndarray:
    """Time-varying state-variable filter (Simper/Zavalishin TPT form).

    fc and q may be curves. mode: 'lp', 'bp' (unity peak gain), 'hp', 'notch'.
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n == 0:
        return x.copy()
    fcv = np.clip(as_curve(fc, n), 5.0, 0.49 * sr)
    k = 1.0 / np.maximum(as_curve(q, n), 0.05)
    g = np.tan(np.pi * fcv / sr)
    a1 = 1.0 / (1.0 + g * (g + k))
    a2 = g * a1
    a3 = g * a2
    xs, A1, A2, A3 = x.tolist(), a1.tolist(), a2.tolist(), a3.tolist()
    lp = [0.0] * n
    bp = [0.0] * n
    ic1 = ic2 = 0.0
    for i in range(n):
        v3 = xs[i] - ic2
        v1 = A1[i] * ic1 + A2[i] * v3
        v2 = ic2 + A2[i] * ic1 + A3[i] * v3
        ic1 = 2.0 * v1 - ic1
        ic2 = 2.0 * v2 - ic2
        lp[i] = v2
        bp[i] = v1
    lpa, bpa = np.array(lp), np.array(bp)
    if mode == "lp":
        return lpa
    if mode == "bp":
        return k * bpa
    if mode == "hp":
        return x - k * bpa - lpa
    if mode == "notch":
        return x - k * bpa
    raise ValueError(mode)


def onepole_lp(x: np.ndarray, sr: int, fc) -> np.ndarray:
    """One-pole lowpass (6 dB/oct); fc may be a curve."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    a = (1.0 - np.exp(-TAU * np.clip(as_curve(fc, n), 0.5, 0.49 * sr) / sr)).tolist()
    xs = x.tolist()
    out = [0.0] * n
    y = 0.0
    for i in range(n):
        y += a[i] * (xs[i] - y)
        out[i] = y
    return np.array(out)


def onepole_hp(x: np.ndarray, sr: int, fc) -> np.ndarray:
    return np.asarray(x, dtype=float) - onepole_lp(x, sr, fc)


def _next_len(n: int) -> int:
    m = 1
    while m < n:
        m <<= 1
    return m


def fft_filter(x: np.ndarray, sr: int, mag: Callable[[np.ndarray], np.ndarray], circular: bool = False,
               pad: int | None = None) -> np.ndarray:
    """Zero-phase filter with an arbitrary magnitude response ``mag(freqs_hz)``.

    Ideal for shaping stationary noise (apply amplitude envelopes afterwards).
    circular=True filters the buffer as one period of a loop.
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n == 0:
        return x.copy()
    N = n if circular else _next_len(n + (pad if pad is not None else min(n, ns(0.15, sr))))
    X = np.fft.rfft(x, N)
    f = np.fft.rfftfreq(N, 1.0 / sr)
    return np.fft.irfft(X * mag(f), N)[:n]


def mag_lp(fc: float, order: float = 2.0):
    return lambda f: 1.0 / np.sqrt(1.0 + (f / fc) ** (2.0 * order))


def mag_hp(fc: float, order: float = 2.0):
    return lambda f: 1.0 / np.sqrt(1.0 + (fc / np.maximum(f, 1e-6)) ** (2.0 * order))


def mag_bp(lo: float, hi: float, order: float = 2.0):
    lp, hp = mag_lp(hi, order), mag_hp(lo, order)
    return lambda f: lp(f) * hp(f)


def mag_reso(fc: float, bw: float, floor: float = 0.0):
    """Single resonance (Lorentzian amplitude), peak 1 at fc."""
    return lambda f: floor + (1.0 - floor) / np.sqrt(1.0 + ((f - fc) / (0.5 * bw)) ** 2)


def mag_mul(*mags):
    def m(f):
        out = np.ones_like(f)
        for g in mags:
            out = out * g(f)
        return out
    return m


def mag_sum(*pairs):
    """Sum of (gain, mag) pairs -- parallel resonators / formant banks."""
    def m(f):
        out = np.zeros_like(f)
        for gain, g in pairs:
            out = out + gain * g(f)
        return out
    return m


# Vowel formants: (freq Hz, bandwidth Hz, gain).  Adapted from the classic
# Csound/Dodge formant tables (alto-ish voice) with slightly widened bandwidths.
VOWELS: dict[str, list[tuple[float, float, float]]] = {
    "a": [(800, 110, 1.0), (1150, 120, 0.63), (2800, 160, 0.10), (3500, 180, 0.04)],
    "o": [(450, 90, 1.0), (800, 100, 0.36), (2830, 140, 0.16), (3500, 160, 0.04)],
    "u": [(325, 70, 1.0), (700, 90, 0.25), (2530, 200, 0.03), (3500, 200, 0.01)],
    "e": [(450, 80, 1.0), (1700, 120, 0.20), (2700, 150, 0.08), (3300, 180, 0.04)],
    "i": [(330, 70, 1.0), (1900, 130, 0.12), (2800, 150, 0.05), (3600, 180, 0.02)],
    "uh": [(600, 110, 1.0), (1050, 120, 0.45), (2500, 160, 0.10), (3400, 180, 0.03)],
}


def formant_gain(fk: np.ndarray, formants, bw_scale: float = 1.0, floor: float = 0.015,
                 tilt_hz: float = 0.0) -> np.ndarray:
    """Spectral envelope (sum of Lorentzian peaks) evaluated at harmonic frequencies fk."""
    g = np.full_like(fk, floor)
    for fF, bw, amp in formants:
        g = g + amp / np.sqrt(1.0 + ((fk - fF) / (0.5 * bw * bw_scale)) ** 2)
    if tilt_hz > 0:
        g = g / np.sqrt(1.0 + (fk / tilt_hz) ** 2)
    return g


def lerp_formants(fa, fb, u: float):
    return [(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u)
            for a, b in zip(fa, fb)]


# ---------------------------------------------------------------------------
# effects
# ---------------------------------------------------------------------------

def softclip(x: np.ndarray, drive: float = 1.0) -> np.ndarray:
    """tanh saturation, unity gain for small signals' peak (normalised by tanh(drive))."""
    if drive <= 0:
        return np.asarray(x, dtype=float)
    return np.tanh(drive * x) / math.tanh(drive)


def bitcrush(x: np.ndarray, bits: float = 8, hold: int = 1) -> np.ndarray:
    y = np.asarray(x, dtype=float)
    if hold > 1:
        y = y[(np.arange(len(y)) // hold) * hold]
    q = 2.0 ** (bits - 1)
    return np.round(y * q) / q


def convolve(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Linear FFT convolution (output length len(x)+len(h)-1)."""
    n = len(x) + len(h) - 1
    N = _next_len(n)
    return np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(h, N), N)[:n]


def convolve_circular(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Circular convolution: the IR tail wraps around (seamless loop reverb)."""
    n = len(x)
    hh = np.zeros(n)
    for i in range(0, len(h), n):
        chunk = h[i:i + n]
        hh[:len(chunk)] += chunk
    return np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(hh), n)


def make_ir(sr: int, rt60: float = 1.8, predelay: float = 0.015, damping: float = 0.55,
            lf_cut: float = 140.0, hf_cut: float = 11000.0, early: int = 10, er_time: float = 0.06,
            rng: np.random.Generator | None = None, density_ms: float = 8.0) -> np.ndarray:
    """Synthetic reverb impulse response (energy-normalised).

    Exponentially decaying noise split into octave-ish bands, each with its own
    decay time (high bands die faster by ``damping``), plus sparse early
    reflections and a predelay.  Convolving with this is a smooth, dense,
    colourless-ish hall/room.
    """
    rng = rng if rng is not None else rng_for("ir", sr, rt60, predelay, damping)
    n = ns(rt60 * 1.15 + 0.05, sr)
    t = np.arange(n) / sr
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / sr)
    lf = np.log2(np.maximum(f, 1.0))
    edges = [250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0]
    steps = [0.5 + 0.5 * np.tanh((lf - math.log2(e)) / 0.35) for e in edges]
    bounds = [np.ones_like(f)] + steps + [np.zeros_like(f)]
    centers = [150.0, 350.0, 700.0, 1400.0, 2800.0, 5600.0, 11000.0]
    ir = np.zeros(n)
    for b in range(len(centers)):
        band = bounds[b] - bounds[b + 1]
        u = np.clip(math.log2(centers[b] / 700.0) / math.log2(11000.0 / 700.0), 0.0, 1.0)
        t60 = rt60 * (1.0 - damping * u) * (1.08 if centers[b] < 300 else 1.0)
        ir += np.fft.irfft(spec * band, n) * np.exp(-LN1000 * t / max(t60, 0.05))
    ir *= 1.0 - np.exp(-t / (density_ms / 1000.0))
    ir = fft_filter(ir, sr, mag_mul(mag_hp(lf_cut, 1.0), mag_lp(hf_cut, 1.0)))
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-12
    # early reflections (sparse taps, a little louder than the diffuse onset)
    er = np.zeros(n)
    for i in range(early):
        tt = er_time * (0.08 + 0.92 * (i / max(early - 1, 1)) ** 1.3) * rng.uniform(0.85, 1.15)
        idx = ns(tt, sr)
        if idx < n:
            er[idx] += rng.choice([-1.0, 1.0]) * 0.11 * (1.0 - 0.6 * i / max(early, 1))
    er = fft_filter(er, sr, mag_lp(6000.0, 1.0))
    ir = ir + er
    ir = np.concatenate([np.zeros(ns(predelay, sr)), ir])
    return ir / (np.sqrt(np.sum(ir ** 2)) + 1e-12)


def reverb(x: np.ndarray, sr: int, ir: np.ndarray, wet: float = 0.25, dry: float = 1.0,
           circular: bool = False) -> np.ndarray:
    """Dry/wet convolution reverb.  Non-circular output is longer (holds the tail)."""
    if circular:
        return dry * x + wet * convolve_circular(x, ir)
    y = wet * convolve(x, ir)
    y[:len(x)] += dry * x
    return y


def echo(x: np.ndarray, sr: int, delay: float, feedback: float = 0.35, mix: float = 0.3,
         damp_hz: float = 5000.0, circular: bool = False) -> np.ndarray:
    """Wet output of a feedback delay with a one-pole lowpass in the loop.

    Computed exactly in the frequency domain:  H = mix*z^-D*L / (1 - fb*z^-D*L).
    circular=True gives the steady state of a looping buffer (echoes wrap).
    Non-circular output is extended to hold the echo tail.
    """
    n = len(x)
    D = delay * sr
    if circular:
        N = n
    else:
        reps = math.ceil(math.log(1e-4 / max(mix, 1e-6)) / math.log(max(min(feedback, 0.99), 1e-3))) + 1
        N = _next_len(n + int(D * max(reps, 1)) + 16)
    X = np.fft.rfft(x, N)
    w = TAU * np.arange(N // 2 + 1) / N
    zD = np.exp(-1j * w * D)
    a = math.exp(-TAU * damp_hz / sr)
    L = (1.0 - a) / (1.0 - a * np.exp(-1j * w))
    H = mix * zD * L / (1.0 - feedback * zD * L)
    y = np.fft.irfft(X * H, N)
    return y if circular else y[:min(N, n + int(D * 12))]


def frac_read(x: np.ndarray, pos: np.ndarray, circular: bool = False) -> np.ndarray:
    """Read x at fractional sample positions (linear interpolation)."""
    n = len(x)
    if circular:
        pos = np.mod(pos, n)
        i0 = np.floor(pos).astype(np.int64)
        fr = pos - i0
        return x[i0 % n] * (1.0 - fr) + x[(i0 + 1) % n] * fr
    pos = np.clip(pos, 0.0, n - 1.000001)
    i0 = np.floor(pos).astype(np.int64)
    fr = pos - i0
    return x[i0] * (1.0 - fr) + x[np.minimum(i0 + 1, n - 1)] * fr


def chorus(x: np.ndarray, sr: int, voices: int = 2, base_ms: float = 14.0, depth_ms: float = 4.0,
           rate_hz: float = 0.35, mix: float = 0.5, circular: bool = False) -> np.ndarray:
    """Mono chorus: several short delay lines modulated by phase-offset sine LFOs.

    For loops the LFO rate is snapped so it completes an integer number of
    cycles per buffer (keeps the loop seamless).
    """
    n = len(x)
    if circular:
        cycles = max(1, round(rate_hz * n / sr))
        rate_hz = cycles * sr / n
    t = np.arange(n)
    wet = np.zeros(n)
    for v in range(voices):
        ph = v / voices
        d = (base_ms + depth_ms * np.sin(TAU * (rate_hz * t / sr + ph))) * sr / 1000.0
        wet += frac_read(x, t - d, circular=circular)
    return (1.0 - 0.5 * mix) * x + mix * wet / voices


# ---------------------------------------------------------------------------
# synthesis building blocks
# ---------------------------------------------------------------------------

def modal(freqs, t60s, amps, n: int, sr: int, rng: np.random.Generator | None = None,
          pitch_env: np.ndarray | None = None, attack: float = 0.0) -> np.ndarray:
    """Sum of exponentially damped sinusoids (struck bars, bells, wood, stone, glass...).

    pitch_env: optional multiplicative frequency curve applied to every mode.
    """
    t = np.arange(n) / sr
    out = np.zeros(n)
    for f, d, a in zip(freqs, t60s, amps):
        if f <= 0 or f >= 0.47 * sr or a == 0:
            continue
        m = min(n, ns(d * 1.05, sr) + 1)
        ph = rng.uniform(0.0, 1.0) if rng is not None else 0.0
        if pitch_env is None:
            s = np.sin(TAU * (f * t[:m] + ph))
        else:
            s = np.sin(TAU * (phase_cycles(f * pitch_env[:m], m, sr) + ph))
        out[:m] += a * np.exp(-LN1000 * t[:m] / d) * s
    if attack > 0:
        out *= np.sin(0.5 * np.pi * np.clip(t / attack, 0.0, 1.0))
    # never truncate a still-ringing mode at the buffer end
    k = min(n, ns(0.005, sr))
    if k > 1:
        out[-k:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(1, k + 1) / k)
    return out


def fm(fc, n: int, sr: int, ratio: float = 1.0, index=1.0, phase0: float = 0.0) -> np.ndarray:
    """Two-operator phase modulation (FM). index may be a curve."""
    fcv = as_curve(fc, n)
    pm = phase_cycles(fcv * ratio, n, sr)
    pc = phase_cycles(fcv, n, sr, phase0)
    return np.sin(TAU * pc + as_curve(index, n) * np.sin(TAU * pm))


def karplus(freq: float, n: int, sr: int, rng: np.random.Generator, t60: float = 2.0,
            brightness: float = 0.6, pluck_pos: float = 0.22) -> np.ndarray:
    """Karplus-Strong plucked string with fractional (linear) tuning.

    Loop filter: g * (0.5(1-d) + 0.5 z^-1 + 0.5 d z^-2) * z^-L, total delay = sr/freq.
    Vectorised in blocks of L samples (every tap reaches back >= L samples).
    brightness 0..1 shapes the excitation; pluck_pos comb-filters it.
    """
    P = sr / freq
    L = max(2, int(math.floor(P - 0.5)))
    d = min(max(P - 0.5 - L, 0.0), 1.0)
    g = 10.0 ** (-3.0 / (max(t60, 0.05) * freq))
    c0, c1, c2 = g * 0.5 * (1.0 - d), g * 0.5, g * 0.5 * d
    exc = rng.uniform(-1.0, 1.0, L)
    exc = onepole_lp(np.tile(exc, 3), sr, freq * (1.5 + 30.0 * brightness ** 2))[L:2 * L]
    if 0 < pluck_pos < 1:
        exc = exc - np.roll(exc, int(round(pluck_pos * L)))
    exc -= exc.mean()
    exc /= np.max(np.abs(exc)) + 1e-12
    off = L + 2
    total = n + off
    nb = int(math.ceil(total / L)) + 1
    y = np.zeros(nb * L + off)
    y[off:off + L] = exc
    for b in range(1, nb):
        s = off + b * L
        if s + L > len(y):
            break
        y[s:s + L] += c0 * y[s - L:s] + c1 * y[s - L - 1:s - 1] + c2 * y[s - L - 2:s - 2]
    return y[off:off + n]


def grain_times(rate, dur: float, rng: np.random.Generator, sr: int = SFX_SR) -> np.ndarray:
    """Poisson event times (s) for a rate that may vary over time (scalar or callable t->rate)."""
    if not callable(rate):
        r = float(rate)
        rate = (lambda tt, r=r: r)
    times = []
    t = 0.0
    rmax = max(rate(x) for x in np.linspace(0, dur, 64)) + 1e-9
    while True:
        t += rng.exponential(1.0 / rmax)
        if t >= dur:
            break
        if rng.uniform() < rate(t) / rmax:
            times.append(t)
    return np.array(times)


# ---------------------------------------------------------------------------
# buffers & mixing
# ---------------------------------------------------------------------------

def place(dst: np.ndarray, src: np.ndarray, start: int, gain: float = 1.0) -> np.ndarray:
    """Add src into dst at sample index start (clipped to dst)."""
    s = int(start)
    a, b = max(0, s), min(len(dst), s + len(src))
    if b > a:
        dst[a:b] += gain * src[a - s:b - s]
    return dst


def place_circ(dst: np.ndarray, src: np.ndarray, start: int, gain: float = 1.0) -> np.ndarray:
    """Add src into dst at start, wrapping around the end (loop buffers)."""
    n = len(dst)
    pos = int(start) % n
    i = 0
    while i < len(src):
        m = min(n - pos, len(src) - i)
        dst[pos:pos + m] += gain * src[i:i + m]
        i += m
        pos = 0
    return dst


def mix_at(sr: int, *layers: tuple[float, np.ndarray, float]) -> np.ndarray:
    """Mix (time_s, signal, gain) layers into a new buffer long enough for all."""
    end = max(ns(t, sr) + len(s) for t, s, _ in layers)
    out = np.zeros(end)
    for t, s, g in layers:
        place(out, s, ns(t, sr), g)
    return out


def pad_to(x: np.ndarray, n: int) -> np.ndarray:
    return x[:n] if len(x) >= n else np.concatenate([x, np.zeros(n - len(x))])


# ---------------------------------------------------------------------------
# mastering & file io
# ---------------------------------------------------------------------------

def remove_dc(x: np.ndarray, sr: int, fc: float = 18.0, circular: bool = False) -> np.ndarray:
    """Sub-sonic highpass.  Linear: causal 2nd-order Butterworth.  Circular: zero-phase FFT."""
    if circular:
        y = fft_filter(x, sr, mag_hp(fc, 2.0), circular=True)
        return y - y.mean()
    return biquad(x, "hp", fc, sr, 0.7071)


def trim(x: np.ndarray, sr: int, lead_db: float = -50.0, tail_db: float = -60.0,
         lead_pad: float = 0.0005, tail_pad: float = 0.004) -> np.ndarray:
    """Cut leading/trailing near-silence (thresholds relative to the peak)."""
    a = np.abs(x)
    pk = a.max() if len(a) else 0.0
    if pk <= 0:
        return x
    first = int(np.argmax(a > pk * db2a(lead_db)))
    last = len(a) - 1 - int(np.argmax(a[::-1] > pk * db2a(tail_db)))
    s = max(0, first - ns(lead_pad, sr))
    e = min(len(x), last + 1 + ns(tail_pad, sr))
    return x[s:e]


def fade(x: np.ndarray, sr: int, fade_in: float = 0.005, fade_out: float = 0.010) -> np.ndarray:
    """Raised-cosine fades (so the first and last samples are exactly 0)."""
    y = np.array(x, dtype=float)
    n = len(y)
    fi = min(ns(fade_in, sr), n // 2)
    fo = min(ns(fade_out, sr), n // 2)
    if fi > 0:
        y[:fi] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(fi) / fi)
    if fo > 0:
        y[n - fo:] *= 0.5 + 0.5 * np.cos(np.pi * (np.arange(fo) + 1) / fo)
    return y


def normalize(x: np.ndarray, peak_db: float) -> np.ndarray:
    pk = np.max(np.abs(x)) if len(x) else 0.0
    return x if pk <= 0 else x * (db2a(peak_db) / pk)


def to_pcm16(x: np.ndarray) -> np.ndarray:
    return np.clip(np.round(np.asarray(x) * 32767.0), -32768, 32767).astype("<i2")


def write_wav(path: str, x: np.ndarray, sr: int, loop: bool = False) -> None:
    """16-bit PCM mono via the stdlib ``wave`` module.

    For loops a RIFF ``smpl`` chunk with one forward loop over the whole file
    is appended (Godot's WAV importer picks it up with Loop Mode = "Detect From WAV").
    """
    data = to_pcm16(x)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.tobytes())
    if loop:
        n = len(data)
        body = struct.pack("<9I", 0, 0, int(round(1e9 / sr)), 60, 0, 0, 0, 1, 0)
        body += struct.pack("<6I", 0, 0, 0, max(n - 1, 0), 0, 0)
        chunk = b"smpl" + struct.pack("<I", len(body)) + body
        with open(path, "r+b") as fh:
            fh.seek(0, 2)
            fh.write(chunk)
            size = fh.tell()
            fh.seek(4)
            fh.write(struct.pack("<I", size - 8))


def read_wav(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        nch = w.getnchannels()
        raw = w.readframes(w.getnframes())
    x = np.frombuffer(raw, dtype="<i2").astype(float) / 32767.0
    if nch > 1:
        x = x.reshape(-1, nch).mean(axis=1)
    return x, sr


def read_smpl_loop(path: str) -> tuple[int, int] | None:
    """Return (start, end) of the first smpl loop, if present."""
    with open(path, "rb") as fh:
        data = fh.read()
    i = 12
    while i + 8 <= len(data):
        cid = data[i:i + 4]
        size = struct.unpack("<I", data[i + 4:i + 8])[0]
        if cid == b"smpl" and size >= 60:
            vals = struct.unpack("<15I", data[i + 8:i + 8 + 60])
            return vals[11], vals[12]
        i += 8 + size + (size & 1)
    return None
