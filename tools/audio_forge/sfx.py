"""Wildbound SFX recipes (all procedural, 44.1 kHz mono).

Each recipe is ``fn(rng) -> np.ndarray`` registered with :func:`sfx` together
with its target peak level, category and loop flag.  ``build.py`` runs the
recipe with a per-name deterministic RNG and then applies :func:`finalize`
(DC removal, silence trim, 5/10 ms fades, peak normalisation; loops are only
DC-corrected and normalised so the wrap stays seamless).

Design vocabulary used throughout:
  * transient  -- a 2-6 ms burst of band-passed noise (``click``)
  * body       -- a sine with a fast exponential pitch drop (``thump``)
  * texture    -- band-limited noise shaped by envelopes (``bn``)
  * resonance  -- damped modes (``S.modal``) for wood / stone / glass / bells
  * clouds     -- Poisson grain clouds for fire crackle and debris
  * voices     -- formant-filtered harmonic sources for creatures and crowds
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import partial
from typing import Callable

import numpy as np

import instruments as I
import music as M
import synth as S

SR = S.SFX_SR
LN = S.LN1000


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

@dataclass
class Recipe:
    name: str
    fn: Callable[[np.random.Generator], np.ndarray]
    peak: float                   # target peak, dBFS
    loop: bool = False
    cat: str = ""
    fade_in: float = 0.005
    fade_out: float = 0.010
    tail_db: float = -60.0
    max_dur: float | None = None  # hard cap (s), with a longer fade-out


REGISTRY: dict[str, Recipe] = {}


def sfx(name: str, peak: float, cat: str, loop: bool = False, **kw):
    def deco(fn):
        REGISTRY[name] = Recipe(name, fn, peak, loop, cat, **kw)
        return fn
    return deco


def finalize(rec: Recipe, x: np.ndarray) -> np.ndarray:
    x = np.nan_to_num(np.asarray(x, dtype=float))
    if rec.loop:
        x = S.remove_dc(x, SR, 18.0, circular=True)
        return S.normalize(x, rec.peak)
    x = S.remove_dc(x, SR, 18.0)
    # trim tails at -60 dB re peak, or where they will sit below -64 dBFS after normalisation
    x = S.trim(x, SR, lead_db=-50.0, tail_db=max(rec.tail_db, -64.0 - rec.peak))
    if rec.max_dur and len(x) > N(rec.max_dur):
        x = S.fade(x[:N(rec.max_dur)], SR, 0.0, 0.3)  # long fade where the cap cuts a ringing tail
        x = S.trim(x, SR, lead_db=-200.0, tail_db=max(rec.tail_db, -64.0 - rec.peak))
    x = S.fade(x, SR, rec.fade_in, rec.fade_out)
    # a short transient can carry a net offset the highpass cannot reach; project it out
    # with a Hann-shaped correction (inaudible, keeps the end samples at exactly 0)
    w = np.hanning(len(x))
    if len(x) > 8 and w.mean() > 0:
        x = x - (x.mean() / w.mean()) * w
    return S.normalize(x, rec.peak)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def N(d: float) -> int:
    return S.ns(d, SR)


def T(n: int) -> np.ndarray:
    return np.arange(n) / SR


def nz(x: np.ndarray) -> np.ndarray:
    """Peak-normalise a layer to 1 (so layer gains are meaningful)."""
    pk = np.max(np.abs(x)) if len(x) else 0.0
    return x / pk if pk > 0 else x


def add(*parts: np.ndarray) -> np.ndarray:
    """Sum signals of different lengths (aligned at their starts)."""
    out = np.zeros(max(len(p) for p in parts))
    for p in parts:
        out[:len(p)] += p
    return out


def lay(*layers: tuple[float, np.ndarray, float]) -> np.ndarray:
    """Mix (start_s, signal, gain) layers."""
    return S.mix_at(SR, *layers)


def bn(n: int, rng, lo: float | None = None, hi: float | None = None, color: float = 0.0,
       order: float = 2.0, circular: bool = False) -> np.ndarray:
    """Band-limited noise (optionally pink/brown-ish), unit std."""
    x = S.colored(n, rng, color, SR) if color else rng.standard_normal(n)
    mags = []
    if lo:
        mags.append(S.mag_hp(lo, order))
    if hi:
        mags.append(S.mag_lp(hi, order))
    if mags:
        x = S.fft_filter(x, SR, S.mag_mul(*mags), circular=circular)
    return x / (np.std(x) + 1e-12)


def flutter(n: int, rng, rate: float = 400.0) -> np.ndarray:
    """Fast random amplitude texture in [0, 1] (crunch, rustle, droplets)."""
    g = np.abs(S.fft_filter(rng.standard_normal(n), SR, S.mag_lp(rate, 2.0)))
    return g / (g.max() + 1e-12)


def click(rng, dur: float = 0.004, lo: float = 1500.0, hi: float = 12000.0, t60: float = 0.003) -> np.ndarray:
    n = N(dur)
    return bn(n, rng, lo, hi) * S.perc(n, SR, 0.0002, t60)


def thump(f0: float, f1: float, tau: float, t60: float, attack: float = 0.0008, curve_pow: float = 1.0,
          h2: float = 0.0, dur: float | None = None) -> np.ndarray:
    """Sine body with an exponential pitch drop f0 -> f1 (kicks, punches, booms)."""
    n = N(dur if dur else t60 * 1.05)
    ph = S.phase_cycles(S.pitch_drop(f0, f1, tau, n, SR), n, SR)
    y = np.sin(S.TAU * ph) + h2 * np.sin(2 * S.TAU * ph)
    return y * S.perc(n, SR, attack, t60, curve_pow=curve_pow)


def whoosh(rng, dur: float, f0: float, f1: float, f2: float, peak: float = 0.45, q: float = 1.1,
           color: float = 1.0, rise: float = 2.0, fall: float = 1.6, air: float = 0.2) -> np.ndarray:
    """Noise through a swept band-pass (f0 -> f1 at the peak -> f2) with a bell envelope."""
    n = N(dur)
    tp = dur * peak
    fc = S.curve([(0.0, f0), (tp, f1), (dur, f2)], n, SR, "exp")
    y = S.svf(bn(n, rng, 40.0, 16000.0, color), SR, fc, q, "bp")
    t = T(n)
    env = np.where(t < tp, (t / tp) ** rise, np.clip(1.0 - (t - tp) / max(dur - tp, 1e-6), 0, 1) ** fall)
    y = nz(y) * env
    if air:
        y = y + air * bn(n, rng, 4500.0, 15000.0) * env ** 1.5 * 0.35
    return y


def crackle(n: int, rng, rate, bright: float = 1.0, size: float = 1.0, pop: float = 0.12,
            circular: bool = False, hp: float = 500.0) -> np.ndarray:
    """Fire crackle: Poisson micro-bursts (noise + ringing tick) with heavy-tailed sizes."""
    out = np.zeros(n)
    for t0 in S.grain_times(rate, n / SR, rng):
        is_pop = rng.uniform() < pop
        if is_pop:
            f, d, g = rng.uniform(500.0, 1500.0), rng.uniform(0.006, 0.018), 1.6
        else:
            f, d, g = rng.uniform(1800.0, 6500.0) * bright, rng.uniform(0.0012, 0.005), 1.0
        m = N(d * 1.2) + 4
        tt = T(m)
        e = np.exp(-LN * tt / d)
        grain = (0.6 * rng.standard_normal(m) + np.sin(S.TAU * min(f, 0.45 * SR) * tt + rng.uniform(0, S.TAU))) * e
        amp = size * g * rng.lognormal(0.0, 0.6)
        if circular:
            S.place_circ(out, grain, N(t0), amp)
        else:
            S.place(out, grain, N(t0), amp)
    if hp:
        out = S.fft_filter(out, SR, S.mag_hp(hp, 1.0), circular=circular)
    return out


def debris(rng, dur: float, count: int, mean_t: float = 0.15, f_lo: float = 500.0, f_hi: float = 4500.0,
           size: float = 1.0, start: float = 0.0, t60=(0.008, 0.04)) -> np.ndarray:
    """Pebbles / chunks: little modal clicks scattered with exponentially thinning density."""
    n = N(dur)
    out = np.zeros(n)
    for _ in range(count):
        t0 = start + rng.exponential(mean_t)
        if t0 > dur - 0.03:
            continue
        k = int(rng.integers(1, 4))
        fs = np.exp(rng.uniform(math.log(f_lo), math.log(f_hi), k))
        ds = rng.uniform(t60[0], t60[1], k)
        m = N(float(ds.max()) * 1.1) + 8
        g = S.modal(fs, ds, rng.uniform(0.4, 1.0, k), m, SR, rng, attack=0.0002)
        c = click(rng, 0.002, 1500.0, 10000.0, 0.001)
        g[:len(c)] += 0.4 * c[:len(g)]
        amp = size * rng.lognormal(0.0, 0.5) * math.exp(-(t0 - start) / (mean_t * 3.0))
        S.place(out, g, N(t0), amp)
    return out


def glints(rng, dur: float, count: int, f_lo: float = 3000.0, f_hi: float = 9000.0, t60=(0.08, 0.3),
           start: float = 0.0, end: float | None = None, curve_pow: float = 1.0, level: float = 1.0) -> np.ndarray:
    """Magical sparkles: tiny FM pings scattered in time."""
    n = N(dur)
    out = np.zeros(n)
    end = dur if end is None else end
    for _ in range(count):
        t0 = start + rng.uniform() ** curve_pow * (end - start)
        f = math.exp(rng.uniform(math.log(f_lo), math.log(f_hi)))
        d = rng.uniform(*t60)
        m = N(d * 1.05)
        tt = T(m)
        tone = S.fm(f, m, SR, 2.0, 0.6 * np.exp(-tt / 0.02)) * S.perc(m, SR, 0.001, d)
        S.place(out, tone, N(t0), level * rng.uniform(0.4, 1.0))
    return out


def voice(f0, n: int, vowel="a", vowel_to=None, morph=None, bw: float = 1.3, kmax: int = 80,
          tilt: float = 4500.0, src: str = "saw") -> np.ndarray:
    """Formant-filtered harmonic voice (creatures, crowd voices, dialogue blips)."""
    f0 = S.as_curve(f0, n)
    fa = S.VOWELS[vowel] if isinstance(vowel, str) else vowel
    fb = None
    if vowel_to is not None:
        fb = S.VOWELS[vowel_to] if isinstance(vowel_to, str) else vowel_to
    u = S.as_curve(0.0 if morph is None else morph, n)
    amps = S.harmonic_amps(src, kmax)

    def spectral(fk, k):
        ga = S.formant_gain(fk, fa, bw, 0.01, tilt)
        if fb is None:
            return ga
        return ga + (S.formant_gain(fk, fb, bw, 0.01, tilt) - ga) * u

    return S.additive(f0, n, SR, amps, spectral=spectral)


def formant_noise(n: int, rng, vowel: str, bw: float = 2.0, circular: bool = False) -> np.ndarray:
    """Whispered vowel: noise through a formant envelope (crowds)."""
    fm_ = S.VOWELS[vowel]
    y = S.fft_filter(rng.standard_normal(n), SR,
                     lambda f: S.formant_gain(f, fm_, bw, 0.02, 5000.0) * (f > 120.0), circular=circular)
    return y / (np.std(y) + 1e-12)


_IRS: dict = {}


def _ir(rt60: float, predelay: float = 0.008, damping: float = 0.5) -> np.ndarray:
    key = (rt60, predelay, damping)
    if key not in _IRS:
        _IRS[key] = S.make_ir(SR, rt60, predelay, damping, rng=S.rng_for("sfx-ir", *key))
    return _IRS[key]


def verb(x: np.ndarray, rt60: float = 1.0, wet: float = 0.2, predelay: float = 0.008,
         damping: float = 0.5) -> np.ndarray:
    return S.reverb(x, SR, _ir(rt60, predelay, damping), wet)


def gated_ramp(n: int, points) -> np.ndarray:
    return S.curve(points, n, SR, "cos")


def comb(x: np.ndarray, delay, g: float) -> np.ndarray:
    """Feedback comb y[i] = x[i] + g*y[i - D(i)]; D in seconds, may be a curve (>= 2 samples).

    Peaks at multiples of 1/D: a hollow, pipe-like resonance; sweeping D glides it.
    """
    n = len(x)
    d = np.maximum(S.as_curve(delay, n) * SR, 2.0).tolist()
    xs = np.asarray(x, dtype=float).tolist()
    y = [0.0] * n
    for i in range(n):
        p = i - d[i]
        if p >= 0.0:
            i0 = int(p)
            fr = p - i0
            y[i] = xs[i] + g * (y[i0] + fr * (y[i0 + 1] - y[i0]))
        else:
            y[i] = xs[i]
    return np.array(y)


# ===========================================================================
# UI
# ===========================================================================

@sfx("ui_move", -12.0, "ui")
def ui_move(rng):
    n = N(0.07)
    tick = S.modal([1850.0, 2950.0, 4100.0], [0.035, 0.02, 0.012], [1.0, 0.35, 0.15], n, SR, rng, attack=0.0006)
    body = S.modal([930.0], [0.025], [0.45], n, SR, rng, attack=0.0008)
    y = tick + body
    c = click(rng, 0.003, 2000.0, 8000.0, 0.0015)
    y[:len(c)] += 0.25 * c
    return S.onepole_lp(y, SR, 7000.0)


@sfx("ui_select", -10.0, "ui")
def ui_select(rng):
    def mallet(f, dur, vel):
        n = N(dur)
        y = S.modal([f, 2 * f, 3 * f, 4.2 * f], [dur * 0.9, dur * 0.45, dur * 0.25, dur * 0.1],
                    [1.0, 0.22, 0.07, 0.03], n, SR, rng, attack=0.002)
        y += 0.12 * S.modal([f * 0.5], [dur * 0.5], [1.0], n, SR, rng, attack=0.004)  # warmth
        return y * vel
    y = lay((0.0, mallet(S.hz("G5"), 0.35, 0.8), 1.0), (0.075, mallet(S.hz("D6"), 0.5, 1.0), 1.0))
    return verb(y, 0.7, 0.14)


@sfx("ui_back", -8.0, "ui")
def ui_back(rng):
    n = N(0.14)
    f = S.curve([(0.0, 880.0), (0.09, 520.0)], n, SR, "exp")
    y = (0.7 * S.tri(f, n, SR) + 0.3 * S.sine(f, n, SR)) * S.perc(n, SR, 0.002, 0.12)
    return S.onepole_lp(y, SR, 4000.0)


@sfx("ui_error", -13.0, "ui")
def ui_error(rng):
    def buzz(f, dur):
        n = N(dur)
        src = 0.6 * S.pulse(f, n, SR, 0.4) + 0.4 * S.saw(f * 1.006, n, SR)
        y = S.svf(src, SR, 850.0, 0.9, "lp")
        return y * S.adsr(n, SR, a=0.004, d=0.03, s=0.85, r=0.025, gate=dur - 0.025)
    return lay((0.0, buzz(156.0, 0.085), 1.0), (0.115, buzz(147.0, 0.095), 1.0))


def _dialogue_blip(rng, f0: float, vowel: str, vowel_to: str):
    dur = 0.058
    n = N(dur)
    t = T(n)
    u = np.clip(t / dur, 0, 1)
    cents = 40.0 * np.sin(np.pi * u) - 30.0 * u
    y = voice(f0 * 2.0 ** (cents / 1200.0), n, vowel, vowel_to, morph=u, bw=1.4, kmax=40, tilt=3500.0)
    env = S.adsr(n, SR, a=0.006, d=0.02, s=0.8, r=0.02, gate=dur - 0.02)
    return S.onepole_lp(y * env, SR, 5000.0)


for _i, (_f0, _va, _vb) in enumerate([(420.0, "a", "o"), (447.0, "e", "a"), (396.0, "o", "a")], 1):
    REGISTRY[f"dialogue_blip_{_i}"] = Recipe(f"dialogue_blip_{_i}",
                                             partial(_dialogue_blip, f0=_f0, vowel=_va, vowel_to=_vb),
                                             -13.0, False, "ui")


@sfx("quest_update", -9.0, "ui")
def quest_update(rng):
    layers = []
    for i, nm in enumerate(["E5", "A5", "B5", "E6"]):
        f = S.hz(nm)
        last = i == 3
        g = add(I.glock(f, 0.3, 0.75 + 0.08 * i, SR, rng, t60=0.55 + 0.45 * last),
                0.5 * I.celesta(f, 0.3, 0.6, SR, rng, t60=0.6 + 0.5 * last))
        layers.append((0.065 * i, g, 1.0))
    return verb(lay(*layers), 1.0, 0.22)


@sfx("save_chime", -9.0, "ui")
def save_chime(rng):
    layers = []
    for i, (nm, v) in enumerate([("A5", 0.8), ("C#6", 0.75), ("E6", 0.8), ("A6", 0.55)]):
        f = S.hz(nm)
        b = add(I.bell(f, 1.0, v, SR, rng, ratio=3.5, index=0.9, t60=1.4, index_t60=0.3, warm=0.25),
                0.6 * I.celesta(f, 1.0, v, SR, rng, t60=1.2))
        layers.append((0.035 * i, b, 1.0))
    sp = glints(rng, 1.4, 8, 4000.0, 9000.0, (0.1, 0.3), 0.05, 0.6, level=0.5)
    return verb(lay(*layers, (0.0, sp, 0.15)), 1.4, 0.28)


# ===========================================================================
# exploration: footsteps
# ===========================================================================

def _step_grass(rng, v: int):
    tilt = 1.0 + 0.07 * (v - 2)
    parts = []
    for t0, g in [(0.0, 1.0), (0.032 + 0.012 * rng.uniform(), 0.65)]:
        n = N(0.13)
        blades = bn(n, rng, 1800.0 * tilt, 7500.0 * tilt, 0.5)
        env = S.perc(n, SR, 0.003, 0.085 * (1 + 0.15 * rng.uniform(-1, 1)))
        rust = blades * (0.35 + 0.65 * flutter(n, rng, 350.0)) * env
        low = bn(n, rng, 250.0, 1400.0) * S.perc(n, SR, 0.002, 0.05)
        th = thump(95.0 + 10.0 * rng.uniform(), 68.0, 0.012, 0.05)
        parts.append((t0, lay((0.0, rust, 1.0), (0.0, low, 0.35), (0.0, th, 0.22)), g))
    return S.onepole_lp(lay(*parts), SR, 8500.0)


def _step_dirt(rng, v: int):
    tilt = 1.0 + 0.08 * (v - 2)
    parts = []
    for t0, g in [(0.0, 1.0), (0.028 + 0.01 * rng.uniform(), 0.55)]:
        n = N(0.11)
        thud = bn(n, rng, 90.0, 700.0 * tilt, 1.0) * S.perc(n, SR, 0.002, 0.055)
        th = thump((110.0 + 15.0 * rng.uniform()) * tilt, 62.0, 0.01, 0.06)
        grit = crackle(n, rng, lambda t: 900.0 * math.exp(-t / 0.03) if t < 0.06 else 0.0, bright=0.6, size=0.5,
                       pop=0.0, hp=900.0)
        parts.append((t0, lay((0.0, nz(thud), 0.8), (0.0, th, 0.45), (0.0, nz(grit), 0.3)), g))
    return S.onepole_lp(lay(*parts), SR, 6000.0)


def _step_stone(rng, v: int):
    def strike(scale, g):
        n = N(0.1)
        f1 = 750.0 * scale
        tock = S.modal([f1, f1 * 2.13, f1 * 3.47, f1 * 5.1], [0.028, 0.018, 0.011, 0.007],
                       [1.0, 0.55, 0.3, 0.15], n, SR, rng, attack=0.0004)
        c = click(rng, 0.004, 2500.0, 9000.0, 0.0025)
        m = N(0.06)
        scuff = bn(m, rng, 2000.0, 8000.0) * S.perc(m, SR, 0.004, 0.035)
        th = thump(150.0 * scale, 95.0, 0.008, 0.04)
        return lay((0.0, tock, 0.55), (0.0, c, 0.6), (0.0, th, 0.35), (0.008, scuff, 0.18)) * g
    s = (1.0 + 0.06 * (v - 2)) * (1.0 + 0.05 * rng.uniform(-1, 1))
    return lay((0.0, strike(s, 1.0), 1.0), (0.03 + 0.008 * rng.uniform(), strike(s * 1.18, 0.4), 1.0))


def _step_wood(rng, v: int):
    def knock(scale, g):
        n = N(0.12)
        f0 = 190.0 * scale
        y = S.modal([f0, f0 * 2.35, f0 * 4.1, f0 * 6.7], [0.075, 0.045, 0.028, 0.014],
                    [1.0, 0.55, 0.3, 0.15], n, SR, rng, attack=0.0006)
        c = click(rng, 0.004, 1500.0, 6000.0, 0.003)
        y[:len(c)] += 0.35 * c
        return y * g
    s = (1.0 + 0.05 * (v - 2)) * (1.0 + 0.04 * rng.uniform(-1, 1))
    return lay((0.0, knock(s, 1.0), 1.0), (0.03 + 0.01 * rng.uniform(), knock(s * 1.12, 0.45), 1.0))


for _surface, _fn in [("grass", _step_grass), ("dirt", _step_dirt), ("stone", _step_stone), ("wood", _step_wood)]:
    for _v in (1, 2, 3):
        _name = f"step_{_surface}_{_v}"
        REGISTRY[_name] = Recipe(_name, partial(_fn, v=_v), -9.0, False, "step")


# ===========================================================================
# exploration: interactions, creatures, world
# ===========================================================================

@sfx("interact", -7.0, "explore")
def interact(rng):
    n = N(0.2)
    leaves = bn(n, rng, 2000.0, 8000.0, 0.5) * (0.3 + 0.7 * flutter(n, rng, 250.0)) * S.swell(n, SR, 0.03, 0.15)
    latch = S.modal([1450.0, 2380.0, 3600.0], [0.025, 0.018, 0.01], [1.0, 0.6, 0.3], N(0.05), SR, rng,
                    attack=0.0005)
    soft = thump(220.0, 160.0, 0.01, 0.04)
    return lay((0.0, leaves, 0.5), (0.012, latch, 0.6), (0.012, soft, 0.25))


@sfx("item_pickup", -8.0, "explore")
def item_pickup(rng):
    layers = []
    for i, nm in enumerate(["C6", "E6", "G6", "C7"]):
        f = S.hz(nm)
        last = i == 3
        g = add(I.glock(f, 0.2, 0.7 + 0.1 * i, SR, rng, t60=0.35 + 0.5 * last),
                0.4 * I.celesta(f, 0.2, 0.6, SR, rng, t60=0.4 + 0.4 * last))
        layers.append((0.045 * i, g, 1.0))
    sp = glints(rng, 0.7, 14, 4500.0, 10000.0, (0.05, 0.2), 0.08, 0.55, level=0.5)
    return verb(lay(*layers, (0.0, sp, 0.25)), 0.8, 0.18)


@sfx("trust_up", -8.0, "explore")
def trust_up(rng):
    layers = []
    for i, (nm, t0) in enumerate([("F5", 0.0), ("A5", 0.11), ("C6", 0.22)]):
        layers.append((t0, I.celesta(S.hz(nm), 0.5, 0.7 + 0.1 * i, SR, rng, t60=0.9 + 0.3 * i), 1.0))
    n = N(1.0)
    bed = sum(S.sine(S.hz(nm), n, SR) for nm in ["F4", "A4", "C5"]) / 3.0 * S.swell(n, SR, 0.25, 0.7)
    gl = glints(rng, 0.9, 5, 3500.0, 6000.0, (0.15, 0.4), 0.3, 0.6, level=0.6)
    return verb(lay(*layers, (0.0, bed, 0.22), (0.0, gl, 0.15)), 1.2, 0.25)


@sfx("befriend_success", -5.0, "explore", max_dur=3.0)
def befriend_success(rng):
    layers = []
    arp = ["D5", "F#5", "A5", "C#6", "E6", "F#6", "A6"]
    for i, nm in enumerate(arp):
        f = S.hz(nm)
        g = add(0.7 * I.bell(f, 1.0, 0.6 + 0.05 * i, SR, rng, ratio=3.5, index=0.8, t60=1.6, index_t60=0.25, warm=0.2),
                0.6 * I.celesta(f, 1.0, 0.65, SR, rng, t60=1.3))
        layers.append((0.075 * i, g, 1.0))
    tb = 0.075 * len(arp) + 0.05
    for nm, v in [("D6", 0.7), ("F#6", 0.6), ("A6", 0.6), ("D7", 0.35)]:
        f = S.hz(nm)
        bloom = add(I.celesta(f, 1.0, v, SR, rng, t60=2.0), 0.5 * I.bell(f, 1.0, v, SR, rng, ratio=2.0, index=0.7, t60=2.2))
        layers.append((tb, bloom, 0.8))
    pad = add(*[I.pad(S.hz(nm), 1.3, 0.8, SR, rng, cutoff=1500.0, attack=0.55, release=0.9)
                for nm in ["D4", "A4", "F#5"]])
    n = N(2.9)
    bed = bn(n, rng, 6000.0, 12000.0) * (0.5 + 0.5 * flutter(n, rng, 30.0)) * \
        gated_ramp(n, [(0.0, 0.0), (0.4, 0.3), (0.9, 1.0), (2.9, 0.0)])
    sp = glints(rng, 2.9, 40, 4000.0, 11000.0, (0.1, 0.5), 0.2, 2.3, curve_pow=1.3, level=0.5)
    y = lay(*layers, (0.05, nz(pad), 0.28), (0.0, bed, 0.035), (0.0, sp, 0.18))
    return verb(y, 2.2, 0.35)


@sfx("emberlyn_chirp", -8.0, "creature")
def emberlyn_chirp(rng):
    def syl(dur, pts, trill=0.0):
        n = N(dur)
        t = T(n)
        ph = S.phase_cycles(S.curve(pts, n, SR, "exp"), n, SR)
        y = np.sin(S.TAU * ph) + 0.3 * np.sin(2 * S.TAU * ph) + 0.08 * np.sin(3 * S.TAU * ph)
        if trill:
            y *= 1.0 - trill * (0.5 + 0.5 * np.sin(S.TAU * 38.0 * t))
        return y * S.adsr(n, SR, a=0.006, d=0.03, s=0.8, r=0.025, gate=dur - 0.025)
    s1 = syl(0.07, [(0.0, 1750.0), (0.05, 2600.0), (0.07, 2450.0)])
    s2 = syl(0.13, [(0.0, 2050.0), (0.06, 3150.0), (0.13, 2650.0)], trill=0.45)
    n = N(0.55)
    cr = crackle(n, rng, lambda t: 120.0 * math.exp(-t / 0.22), size=0.5, pop=0.25)
    hiss = bn(n, rng, 3000.0, 9000.0) * S.swell(n, SR, 0.04, 0.35) * (0.4 + 0.6 * flutter(n, rng, 60.0))
    return lay((0.0, s1, 0.8), (0.095, s2, 1.0), (0.015, nz(cr), 0.7), (0.0, hiss, 0.08))


@sfx("emberlyn_hiss", -7.0, "creature")
def emberlyn_hiss(rng):
    dur = 0.55
    n = N(dur)
    t = T(n)
    mouth = S.fft_filter(bn(n, rng, 2200.0, 10000.0, 0.3), SR,
                         S.mag_sum((1.0, S.mag_reso(4300.0, 2600.0, 0.25)), (0.5, S.mag_reso(7200.0, 3000.0))))
    mouth = mouth / (np.std(mouth) + 1e-9)
    trem = 1.0 - 0.3 * (0.5 + 0.5 * np.sin(S.TAU * 17.0 * t + 0.7 * np.sin(S.TAU * 3.1 * t)))
    hiss = mouth * trem * S.adsr(n, SR, a=0.025, d=0.25, s=0.7, r=0.12, gate=dur - 0.12)
    m = N(0.09)
    ph = S.phase_cycles(S.curve([(0.0, 2300.0), (0.04, 3300.0), (0.09, 2700.0)], m, SR, "exp"), m, SR)
    sq = (np.sin(S.TAU * ph) + 0.2 * np.sin(2 * S.TAU * ph)) * S.adsr(m, SR, 0.005, 0.02, 0.7, 0.03, gate=0.06)
    cr = crackle(n, rng, 30.0, size=0.4, pop=0.1)
    return lay((0.0, nz(hiss), 1.0), (0.0, sq, 0.35), (0.05, nz(cr), 0.25))


@sfx("stoneback_grunt", -3.0, "creature")
def stoneback_grunt(rng):
    dur = 0.62
    n = N(dur)
    t = T(n)
    f0 = S.curve([(0.0, 92.0), (0.12, 100.0), (0.6, 74.0)], n, SR, "exp") * (1 + 0.06 * S.lfo_noise(n, SR, 30.0, rng))
    v = voice(f0, n, "uh", "o", morph=np.clip(t / dur, 0, 1), bw=1.6, kmax=70, tilt=1500.0)
    sub_ph = S.phase_cycles(f0 * 0.5, n, SR)
    fry = 1.0 - 0.45 * (0.5 + 0.5 * np.sin(S.TAU * sub_ph))
    vo = (nz(v) * fry + 0.25 * np.sin(S.TAU * sub_ph)) * S.adsr(n, SR, a=0.035, d=0.2, s=0.75, r=0.18,
                                                               gate=dur - 0.18)
    rumble = bn(n, rng, 30.0, 260.0, 2.0) * S.swell(n, SR, 0.06, 0.5)
    rattle = debris(rng, dur, 14, 0.18, 250.0, 1400.0, 0.5, 0.02, (0.01, 0.04))
    return lay((0.0, nz(vo), 1.0), (0.0, nz(rumble), 0.5), (0.0, nz(rattle), 0.35))


@sfx("mossling_squeak", -9.0, "creature")
def mossling_squeak(rng):
    def sq(dur, pts, g):
        n = N(dur)
        t = T(n)
        f = S.curve(pts, n, SR, "exp") * (1 + 0.025 * np.sin(S.TAU * 42.0 * t))
        ph = S.phase_cycles(f, n, SR)
        y = np.sin(S.TAU * ph) + 0.18 * np.sin(2 * S.TAU * ph)
        return y * S.adsr(n, SR, 0.005, 0.03, 0.75, 0.03, gate=dur - 0.03) * g
    return lay((0.0, sq(0.1, [(0.0, 2500.0), (0.035, 3450.0), (0.1, 3000.0)], 1.0), 1.0),
               (0.115, sq(0.055, [(0.0, 2900.0), (0.02, 3600.0), (0.055, 3300.0)], 0.45), 1.0))


@sfx("lanternmoth_flutter", -9.0, "creature")
def lanternmoth_flutter(rng):
    dur = 0.65
    n = N(dur)
    t = T(n)
    # wing-beat rate wobbles around 21 Hz; every beat is a soft, overlapping swish of air
    rate = 21.0 + 3.0 * np.sin(S.TAU * 1.3 * t) + 1.5 * S.lfo_noise(n, SR, 6.0, rng)
    beat = (0.5 - 0.5 * np.cos(S.TAU * S.phase_cycles(rate, n, SR))) ** 2.5
    air = S.fft_filter(bn(n, rng, 180.0, None, 1.0), SR, S.mag_lp(2200.0, 2.0))
    flap = nz(air) * (0.15 + 0.85 * beat) * gated_ramp(n, [(0.0, 0.0), (0.12, 1.0), (0.4, 0.85), (dur, 0.0)])
    gl = glints(rng, dur, 3, 5000.0, 7500.0, (0.1, 0.25), 0.1, 0.5, level=0.5)
    return lay((0.0, nz(flap), 1.0), (0.0, gl, 0.1))


@sfx("gate_open", -3.0, "explore")
def gate_open(rng):
    dur = 2.0
    n = N(dur)
    # stick-slip creak: an irregular impulse train exciting wooden body modes
    rate = S.curve([(0.0, 55.0), (0.3, 120.0), (0.8, 85.0), (1.2, 140.0), (1.6, 70.0), (1.75, 50.0)], n, SR, "cos")
    ph = S.phase_cycles(rate * (1 + 0.12 * S.lfo_noise(n, SR, 9.0, rng)), n, SR)
    idx = np.nonzero(np.diff(np.floor(ph)) > 0)[0]
    imp = np.zeros(n)
    imp[idx] = rng.uniform(0.5, 1.0, len(idx))
    inten = np.clip(0.55 + 0.6 * S.lfo_noise(n, SR, 2.5, rng), 0.0, 1.0)
    imp *= inten * gated_ramp(n, [(0.0, 0.0), (0.12, 1.0), (1.6, 1.0), (1.75, 0.0)])
    body_ir = S.modal([310.0, 655.0, 1130.0, 1790.0, 2600.0], [0.06, 0.05, 0.035, 0.025, 0.015],
                      [1.0, 0.8, 0.6, 0.35, 0.2], N(0.08), SR, rng)
    creak = S.convolve(imp, body_ir)[:n]
    grind = bn(n, rng, 40.0, 380.0, 2.0) * (0.5 + 0.5 * np.clip(S.lfo_noise(n, SR, 7.0, rng), -1, 1)) * \
        gated_ramp(n, [(0.0, 0.0), (0.2, 1.0), (1.65, 0.9), (1.8, 0.0)])
    grit = crackle(n, rng, lambda tt: 140.0 if 0.1 < tt < 1.7 else 0.0, bright=0.45, size=0.4, pop=0.3, hp=400.0)
    th = thump(85.0, 48.0, 0.03, 0.4, curve_pow=1.2)
    dust = debris(rng, 0.5, 10, 0.08, 300.0, 2000.0, 0.6)
    return lay((0.0, nz(creak), 1.0), (0.0, nz(grind), 0.4), (0.0, nz(grit), 0.25), (1.72, th, 0.9),
               (1.72, nz(dust), 0.3))


@sfx("splash", -3.0, "explore")
def splash(rng):
    dur = 0.85
    n = N(dur)
    m1 = N(0.25)
    impact = bn(m1, rng, 150.0, 2500.0, 1.0) * S.perc(m1, SR, 0.002, 0.13)
    th = thump(130.0, 60.0, 0.015, 0.08)
    m2 = N(0.6)
    spray = bn(m2, rng, 2000.0, 11000.0) * (0.4 + 0.6 * flutter(m2, rng, 400.0)) * S.perc(m2, SR, 0.006, 0.42)
    bubbles = np.zeros(n)
    for _ in range(30):
        t0 = 0.015 + rng.exponential(0.12)
        if t0 > dur - 0.1:
            continue
        f0 = math.exp(rng.uniform(math.log(450.0), math.log(2400.0)))
        d = rng.uniform(0.025, 0.07)
        m = N(d * 1.1)
        tt = T(m)
        f = f0 * (1.0 + rng.uniform(0.6, 1.5) * tt / d)
        b = np.sin(S.TAU * S.phase_cycles(f, m, SR)) * np.exp(-LN * tt / d) * np.clip(tt / 0.002, 0, 1)
        S.place(bubbles, b, N(t0), rng.uniform(0.3, 1.0) * math.exp(-t0 / 0.25))
    drops = glints(rng, dur, 7, 1500.0, 4000.0, (0.03, 0.06), 0.25, 0.8, level=0.6)
    return lay((0.0, nz(impact), 0.8), (0.0, th, 0.4), (0.01, nz(spray), 0.55), (0.0, nz(bubbles), 0.45),
               (0.0, drops, 0.2))


@sfx("fire_light", -4.0, "explore")
def fire_light(rng):
    dur = 1.1
    n = N(dur)
    fc = S.curve([(0.0, 180.0), (0.13, 1900.0), (0.45, 900.0), (1.1, 450.0)], n, SR, "exp")
    whoomp = S.svf(bn(n, rng, 40.0, 9000.0, 1.0), SR, fc, 0.8, "lp") * \
        gated_ramp(n, [(0.0, 0.0), (0.05, 0.5), (0.12, 1.0), (0.3, 0.55), (1.1, 0.0)])
    pf = S.curve([(0.0, 55.0), (0.12, 105.0), (0.5, 62.0)], n, SR, "exp")
    pump = np.sin(S.TAU * S.phase_cycles(pf, n, SR)) * gated_ramp(n, [(0.0, 0.0), (0.1, 1.0), (0.5, 0.2), (0.8, 0.0)])
    cr = crackle(n, rng, lambda tt: 0.0 if tt < 0.08 else 55.0 * math.exp(-(tt - 0.08) / 0.5), size=0.6, pop=0.2)
    roar = bn(n, rng, 250.0, 1600.0, 1.0) * (0.6 + 0.4 * S.lfo_noise(n, SR, 9.0, rng)) * \
        gated_ramp(n, [(0.0, 0.0), (0.15, 1.0), (1.1, 0.0)])
    return lay((0.0, nz(whoomp), 1.0), (0.0, pump, 0.45), (0.0, nz(cr), 0.35), (0.0, nz(roar), 0.25))


@sfx("fire_crackle_loop", -7.0, "loop", loop=True)
def fire_crackle_loop(rng):
    n = N(2.0)
    bed = S.fft_filter(S.colored(n, rng, 1.5, SR), SR, S.mag_bp(80.0, 650.0, 1.5), circular=True)
    bed = bed / np.std(bed) * (0.75 + 0.25 * S.lfo_noise(n, SR, 3.0, rng))
    hiss = S.fft_filter(rng.standard_normal(n), SR, S.mag_bp(2500.0, 7000.0, 1.5), circular=True)
    hiss = hiss / np.std(hiss) * (0.5 + 0.5 * S.lfo_noise(n, SR, 6.0, rng))
    small = crackle(n, rng, 30.0, bright=1.0, size=0.5, pop=0.05, circular=True)
    big = crackle(n, rng, 3.5, bright=0.8, size=1.4, pop=0.6, circular=True)
    return 0.09 * bed + 0.03 * hiss + 0.45 * nz(small) + 0.8 * nz(big)


@sfx("tremor", -1.0, "impact")
def tremor(rng):
    dur = 2.5
    n = N(dur)
    env = gated_ramp(n, [(0.0, 0.0), (0.35, 0.8), (0.6, 1.0), (1.5, 0.9), (2.5, 0.0)])
    surge = np.clip(0.6 + 0.5 * S.lfo_noise(n, SR, 4.0, rng), 0.1, 1.2)
    rumble = bn(n, rng, 20.0, 110.0, 2.0, order=3.0)
    sub = np.sin(S.TAU * S.phase_cycles(33.0 * (1 + 0.08 * S.lfo_noise(n, SR, 0.8, rng)), n, SR)) + \
        0.6 * np.sin(S.TAU * S.phase_cycles(44.0 * (1 + 0.06 * S.lfo_noise(n, SR, 1.1, rng)), n, SR))
    mid = bn(n, rng, 80.0, 420.0, 1.0) * np.clip(0.5 + 0.6 * S.lfo_noise(n, SR, 7.0, rng), 0.0, 1.2)
    y = (nz(rumble) + 0.45 * nz(sub) + 0.4 * nz(mid)) * env * surge
    y = S.softclip(nz(y) * 1.4, 1.5)
    rattle = crackle(n, rng, lambda tt: 160.0 * float(np.interp(tt, [0, 0.4, 1.5, 2.5], [0, 1, 0.9, 0])),
                     bright=0.4, size=0.6, pop=0.4, hp=250.0)
    stones = debris(rng, dur, 18, 0.9, 300.0, 2500.0, 0.6, 0.2)
    return y + 0.22 * nz(rattle) * env + 0.18 * nz(stones)


@sfx("mural_awaken", -5.0, "magic", max_dur=3.0)
def mural_awaken(rng):
    choir = lay(*[(0.0, I.choir(S.hz(nm), 1.9, 0.8, SR, rng, vowel="u", vowel_to="a", attack=1.3, release=0.9,
                                voices=3), 1.0) for nm in ["D4", "A4", "D5", "E5"]])
    times = [0.55, 0.85, 1.1, 1.3, 1.5, 1.68, 1.85, 2.0]
    notes = ["A5", "D6", "E6", "G6", "A6", "D7", "E6", "A6"]
    chimes = lay(*[(tt, add(I.celesta(S.hz(nm), 0.4, 0.5 + 0.06 * i, SR, rng, t60=1.2),
                            0.5 * I.bell(S.hz(nm), 1.0, 0.4, SR, rng, ratio=3.5, index=0.6, t60=1.0)), 1.0)
                   for i, (tt, nm) in enumerate(zip(times, notes))])
    n = N(3.0)
    shimmer = bn(n, rng, 5000.0, 12000.0) * gated_ramp(n, [(0.0, 0.0), (1.5, 0.5), (2.1, 1.0), (3.0, 0.0)]) * \
        (0.6 + 0.4 * S.lfo_noise(n, SR, 12.0, rng))
    low = np.sin(S.TAU * S.hz("D2") * T(n)) * gated_ramp(n, [(0.0, 0.0), (1.8, 1.0), (3.0, 0.0)])
    y = lay((0.0, nz(choir), 1.0), (0.0, nz(chimes), 0.45), (0.0, shimmer, 0.03), (0.0, low, 0.18))
    return verb(y, 2.6, 0.35)


# ===========================================================================
# combat: flow
# ===========================================================================

@sfx("countdown_tick", -5.0, "combat")
def countdown_tick(rng):
    n = N(0.09)
    block = S.modal([2150.0, 3780.0, 5250.0], [0.045, 0.02, 0.01], [1.0, 0.45, 0.2], n, SR, rng, attack=0.0003)
    body = S.modal([1080.0], [0.03], [0.5], n, SR, rng, attack=0.0005)
    return lay((0.0, block, 1.0), (0.0, body, 1.0), (0.0, click(rng, 0.003, 3000.0, 12000.0, 0.0015), 0.4))


@sfx("fight_start", -1.0, "combat")
def fight_start(rng):
    th = 0.18
    pre = whoosh(rng, th, 300.0, 2800.0, 3200.0, peak=0.98, q=0.9, rise=2.5)
    f0 = 98.0
    ratios = [1.0, 1.52, 2.01, 2.48, 2.97, 3.56, 4.13, 4.77, 5.33, 6.08, 6.92, 7.86, 8.71, 9.9, 11.2, 12.7]
    n = N(1.8)
    t = T(n)
    pe = 1.0 + 0.015 * np.exp(-t / 0.08)
    amps = [1.0, 0.8, 0.75, 0.6, 0.55, 0.5, 0.45, 0.4, 0.35, 0.3, 0.27, 0.22, 0.2, 0.16, 0.12, 0.1]
    decs = [1.8 - 0.09 * i for i in range(len(ratios))]
    gong = S.modal([f0 * r * (1 + 0.004 * rng.uniform(-1, 1)) for r in ratios], decs, amps, n, SR, rng,
                   pitch_env=pe, attack=0.002)
    bloom = S.modal([f0 * r for r in [13.9, 15.3, 17.1, 19.4, 22.0]], [1.0] * 5, [0.3] * 5, n, SR, rng) * \
        np.clip(t / 0.25, 0, 1)
    punch = thump(160.0, 48.0, 0.02, 0.35, curve_pow=1.3)
    sub = thump(52.0, 38.0, 0.1, 0.9, attack=0.003)
    crash_n = bn(n, rng, 2500.0, 11000.0) * S.perc(n, SR, 0.001, 0.7)
    c = click(rng, 0.005, 1500.0, 10000.0, 0.003)
    hit = lay((0.0, nz(gong), 0.55), (0.0, nz(bloom), 0.12), (0.0, punch, 0.9), (0.0, sub, 0.6),
              (0.0, crash_n, 0.05), (0.0, c, 0.6))
    hit = S.softclip(nz(hit), 1.4)
    return verb(lay((0.0, nz(pre), 0.45), (th, hit, 1.0)), 1.6, 0.2)


# ===========================================================================
# combat: movement
# ===========================================================================

@sfx("dash_whoosh", -5.0, "combat")
def dash_whoosh(rng):
    dur = 0.19
    w = whoosh(rng, dur, 650.0, 3400.0, 1300.0, peak=0.38, q=1.7, color=0.7, rise=1.6, fall=1.4, air=0.35)
    body = whoosh(rng, dur, 220.0, 600.0, 300.0, peak=0.4, q=0.9, color=1.5, air=0.0)
    return lay((0.0, nz(w), 1.0), (0.0, nz(body), 0.2))


@sfx("dash_roll", -4.0, "combat")
def dash_roll(rng):
    dur = 0.27
    n = N(dur)
    env = gated_ramp(n, [(0.0, 0.0), (0.03, 1.0), (0.2, 0.85), (dur, 0.0)])
    rumble = bn(n, rng, 40.0, 380.0, 2.0)
    bumps = np.zeros(n)
    tt = 0.0
    while tt < dur - 0.03:
        S.place(bumps, thump(105.0 + 25.0 * rng.uniform(), 70.0, 0.006, 0.03), N(tt), rng.uniform(0.6, 1.0))
        tt += rng.uniform(0.026, 0.038)
    gravel = crackle(n, rng, 380.0, bright=0.45, size=0.5, pop=0.25, hp=500.0)
    w = whoosh(rng, dur, 200.0, 900.0, 380.0, peak=0.4, q=1.1, color=1.2, air=0.0)
    y = (nz(rumble) * 0.7 + nz(bumps) * 0.9 + nz(gravel) * 0.35) * env + 0.35 * nz(w)
    return S.softclip(y, 1.3)


@sfx("dash_through_hit", -3.0, "combat")
def dash_through_hit(rng):
    w = whoosh(rng, 0.16, 900.0, 4200.0, 2000.0, peak=0.6, q=0.9, rise=2.0)
    n = N(0.32)
    ph = S.phase_cycles(S.curve([(0.0, 640.0), (0.06, 330.0), (0.3, 300.0)], n, SR, "exp"), n, SR)
    bonk = (np.sin(S.TAU * ph) + 0.35 * np.sin(S.TAU * 1.52 * ph) + 0.12 * np.sin(S.TAU * 2.7 * ph)) * \
        S.perc(n, SR, 0.001, 0.22, curve_pow=1.2)
    knock = thump(260.0, 140.0, 0.01, 0.07)
    c = click(rng, 0.004, 1500.0, 9000.0, 0.0025)
    ding = I.glock(S.hz("E7"), 0.3, 0.5, SR, rng, t60=0.45)
    hit = lay((0.0, nz(bonk), 1.0), (0.0, knock, 0.5), (0.0, c, 0.5), (0.03, nz(ding), 0.16))
    return lay((0.0, nz(w), 0.55), (0.12, hit, 1.0))


@sfx("stun_chime", -14.0, "combat", loop=True)
def stun_chime(rng):
    n = N(0.5)
    out = np.zeros(n)
    for i, t0 in enumerate([0.07, 0.235, 0.40]):
        m = N(0.075)
        base = [2900.0, 3150.0, 2750.0][i]
        ph = S.phase_cycles(S.curve([(0.0, base), (0.028, base * 1.25), (0.075, base * 1.05)], m, SR, "exp"), m, SR)
        tw = (np.sin(S.TAU * ph) + 0.15 * np.sin(2 * S.TAU * ph)) * S.adsr(m, SR, 0.004, 0.02, 0.7, 0.025, gate=0.05)
        S.place_circ(out, tw, N(t0), 1.0)
        S.place_circ(out, I.glock(S.hz(["E7", "C#7", "A6"][i]), 0.2, 0.5, SR, rng, t60=0.35), N(t0 + 0.04), 0.35)
    return out + 0.18 * S.convolve_circular(out, _ir(0.5, 0.005, 0.5))


# ===========================================================================
# combat: drag-to-dash
#   aim ticks while dragging -> windup (coil) -> launch -> ram / whiff / clash /
#   blocked -> land.  Sounds with a sharp onset use a 1 ms fade-in so that
#   finalize() keeps their transient.
# ===========================================================================

@sfx("dash_aim_tick", -13.0, "ui", fade_in=0.001)
def dash_aim_tick(rng):
    n = N(0.05)
    f = 1175.0  # D6; the engine pitches it up one step per aimed cell
    bar = S.modal([f, f * 3.93, f * 5.6], [0.04, 0.014, 0.007], [1.0, 0.16, 0.05], n, SR, rng, attack=0.0007)
    return S.onepole_lp(lay((0.0, bar, 1.0), (0.0, click(rng, 0.002, 2500.0, 8000.0, 0.0008), 0.12)), SR, 6000.0)


@sfx("dash_windup", -11.0, "combat")
def dash_windup(rng):
    dur = 0.072
    n = N(dur)
    t = T(n)
    tp = 0.054  # the inhale peaks here and is gone by the time the launch fires
    fc = S.curve([(0.0, 650.0), (tp, 2700.0), (dur, 3100.0)], n, SR, "exp")
    breath = nz(S.svf(bn(n, rng, 200.0, 12000.0, 0.6), SR, fc, 2.2, "bp"))
    env = np.where(t < tp, (t / tp) ** 2.2, np.clip(1.0 - (t - tp) / (dur - tp), 0.0, 1.0) ** 1.5)
    tension = bn(n, rng, 3000.0, 9000.0) * flutter(n, rng, 300.0) ** 2 * env  # fur / muscle creak
    tuck = thump(250.0, 180.0, 0.01, 0.03, attack=0.002)  # the crouch
    return lay((0.0, breath * env, 1.0), (0.0, nz(tension), 0.2), (0.0, tuck, 0.1))


def _dash_launch(rng, v: int):
    dur = (0.22, 0.25, 0.2)[v - 1]
    k = (1.0, 0.9, 1.1)[v - 1]  # each variant tears a little brighter or darker
    n = N(dur)
    t = T(n)
    u = t / dur
    att = np.sin(0.5 * np.pi * np.clip(t / 0.0025, 0.0, 1.0))
    # air tear: a resonant band that starts high and falls away (something leaving fast) ...
    fc = S.curve([(0.0, 7500.0 * k), (0.02, 4800.0 * k), (dur, 1100.0 * k)], n, SR, "exp")
    tear = nz(S.svf(bn(n, rng, 300.0, 15000.0, 0.3), SR, fc, 2.6, "bp"))
    rag = 0.25 + 0.75 * flutter(n, rng, 700.0 + 150.0 * v)   # ... with a ragged, ripping grain
    rag = rag + (1.0 - rag) * np.clip(t / 0.07, 0.0, 1.0)     # that smooths into a clean tail
    tenv = att * (0.55 * np.exp(-t / 0.025) + 0.45 * np.exp(-t / 0.09)) * (1.0 - u) ** 1.3
    # wind: a broad, darker band under it
    wind = nz(S.svf(bn(n, rng, 100.0, 12000.0, 1.0), SR, S.curve([(0.0, 2600.0 * k), (dur, 600.0 * k)], n, SR, "exp"),
                    0.7, "bp"))
    wenv = np.clip(t / 0.008, 0.0, 1.0) * np.exp(-t / 0.06) * (1.0 - u) ** 1.2
    # push-off: a short, sharp kick, a scuff of dirt and a little sand spray
    push = thump(200.0 * (1.0 + 0.04 * (v - 2)), 105.0, 0.008, 0.05, h2=0.3)
    m = N(0.05)
    scuff = bn(m, rng, 150.0, 2000.0, 1.0) * S.perc(m, SR, 0.0008, 0.03)
    spray = crackle(N(0.08), rng, lambda tt: 2000.0 * math.exp(-tt / 0.02), bright=0.8, size=0.5, pop=0.0, hp=2000.0)
    y = lay((0.0, tear * rag * tenv, 1.0), (0.0, wind * wenv, 0.4), (0.0, push, 0.3), (0.0, nz(scuff), 0.25),
            (0.0, nz(spray), 0.12), (0.0, click(rng, 0.003, 2500.0, 12000.0, 0.0015), 0.4))
    y = S.softclip(nz(y) * 1.2, 1.2)
    return S.fft_filter(y, SR, S.mag_lp(12500.0, 3.0))  # headroom for the engine's pitch-up on long dashes


def _dash_land(rng, v: int):
    dur = (0.18, 0.21, 0.16)[v - 1]
    k = (1.0, 0.93, 1.07)[v - 1]
    n = N(dur)
    t = T(n)
    u = t / dur
    # the skid builds just behind the footfall and fades as the creature slows
    senv = np.clip(t / 0.012, 0.0, 1.0) ** 1.5 * (1.0 - u)
    # stick-slip: the grit catches and releases ever more slowly as the creature brakes ("skrrrt" -> "k-k-k")
    rate = S.curve([(0.0, 150.0 * k), (dur, 32.0 * k)], n, SR, "exp") * (1.0 + 0.35 * S.lfo_noise(n, SR, 120.0, rng))
    ph = S.phase_cycles(rate, n, SR)
    idx = np.nonzero(np.diff(np.floor(ph)) > 0)[0]
    imp = np.zeros(n)
    imp[idx] = rng.uniform(0.3, 1.0, len(idx))
    slips = S.convolve(imp, np.exp(-T(N(0.01)) / 0.0016))[:n]
    # a lower, narrower band than the launch's air tear: claws and grit, not wind
    fc = S.curve([(0.0, 2400.0 * k), (dur, 900.0 * k)], n, SR, "exp")
    scrape = S.svf(bn(n, rng, 300.0, 9000.0, 0.3), SR, fc, 1.2, "bp") * (0.12 + slips) * senv
    # level the scrape by its energy and soft-limit its random loudest grains, so the (deterministic) thump
    # sets the peak and every variant comes out equally loud
    scrape = 0.5 * np.tanh(0.25 * scrape / np.sqrt(np.mean(scrape ** 2)))
    sand = crackle(n, rng, lambda tt: 1400.0 * max(0.0, 1.0 - tt / dur), bright=0.6, size=0.5, pop=0.0, hp=1500.0)
    # weight settling: a soft low thump, a dull puff of packed sand and a pebble or two
    body = thump(105.0 * k, 52.0, 0.018, 0.12, attack=0.003, h2=0.3)
    m = N(0.09)
    puff = bn(m, rng, 80.0, 800.0, 1.5) * S.perc(m, SR, 0.003, 0.06)
    pebbles = debris(rng, dur, 4, 0.05, 1500.0, 5500.0, 0.5, 0.03, (0.005, 0.018))
    y = lay((0.0, scrape, 1.0), (0.0, nz(sand), 0.1), (0.0, body, 0.65), (0.0, nz(puff), 0.35),
            (0.0, nz(pebbles), 0.15))
    return S.softclip(nz(y) * 1.1, 1.1)


# the engine picks a variant at random, so each one's peak is trimmed to make them equally loud
for _v, _launch_pk, _land_pk in [(1, -4.3, -4.1), (2, -3.2, -6.0), (3, -3.0, -5.0)]:
    REGISTRY[f"dash_launch_{_v}"] = Recipe(f"dash_launch_{_v}", partial(_dash_launch, v=_v), _launch_pk, False,
                                           "combat", fade_in=0.001)
    REGISTRY[f"dash_land_{_v}"] = Recipe(f"dash_land_{_v}", partial(_dash_land, v=_v), _land_pk, False, "combat",
                                         fade_in=0.001)


@sfx("ram_impact", -1.0, "impact", fade_in=0.001)
def ram_impact(rng):
    dur = 0.55
    n = N(dur)
    t = T(n)
    # body and sub drop in ONE oscillator (nothing to beat against): a punch that falls 260 -> ~100 Hz within
    # ~30 ms, then a slow glide down to 46 Hz.  The punch is saturated on its own -- its harmonics are what
    # laptop and phone speakers reproduce -- while a quieter sub tail keeps going underneath for headphones.
    ph = S.TAU * S.phase_cycles(46.0 + 62.0 * np.exp(-t / 0.12) + 152.0 * np.exp(-t / 0.012), n, SR)
    punch = (np.sin(ph) + 0.3 * np.sin(2 * ph)) * S.perc(n, SR, 0.0008, 0.2, curve_pow=1.5)
    punch = S.fft_filter(S.softclip(punch * 2.0, 2.2), SR, S.mag_lp(2500.0, 2.0))
    tail = np.sin(ph) * S.perc(n, SR, 0.004, 0.45) * np.clip(t / 0.03, 0.0, 1.0)
    knock = thump(720.0, 330.0, 0.005, 0.05)  # the mid "pok"
    # whack: resonant low-mid noise (the "wha" of thwack) ...
    m = N(0.15)
    meat = bn(m, rng, 150.0, 2500.0, 1.0)
    whack = S.fft_filter(meat, SR, S.mag_sum((0.8, S.mag_reso(420.0, 300.0)), (1.0, S.mag_reso(1100.0, 700.0)))) * \
        S.perc(m, SR, 0.0006, 0.15, curve_pow=1.8)
    # ... and a crunchy crack on top (the "th")
    m = N(0.12)
    crack = S.softclip(bn(m, rng, 1500.0, 9000.0, 0.3), 2.5) * (0.45 + 0.55 * flutter(m, rng, 700.0)) * \
        S.perc(m, SR, 0.0003, 0.09, curve_pow=1.2)
    core = lay((0.0, nz(punch), 1.0), (0.0, tail, 0.4), (0.0, knock, 0.3), (0.0, nz(whack), 1.0))
    # shimmer tail: sparkling fizz, pings and two slowly beating pairs that grow out of the crack, kept above
    # the harsh 2-4 kHz band
    d = N(0.45)
    tt = T(d)
    fizz = bn(d, rng, 5000.0, 11000.0) * (0.35 + 0.65 * flutter(d, rng, 90.0)) * S.perc(d, SR, 0.006, 0.28)
    ring = np.zeros(d)
    for a, b in [(5310.0, 5318.0), (6730.0, 6741.0)]:
        ring += np.sin(S.TAU * a * tt + rng.uniform(0, S.TAU)) + np.sin(S.TAU * b * tt + rng.uniform(0, S.TAU))
    ring *= S.perc(d, SR, 0.004, 0.32) / 4.0
    pings = np.zeros(d)  # a sparkle cloud that thins out (and quietens) as it goes, so no late ping sticks out
    for _ in range(18):
        t0 = 0.004 + rng.exponential(0.05)
        if t0 > 0.3:
            continue
        dd = rng.uniform(0.04, 0.12)
        mm = N(dd * 1.05)
        ping = S.fm(math.exp(rng.uniform(math.log(5000.0), math.log(9000.0))), mm, SR, 2.0,
                    0.6 * np.exp(-T(mm) / 0.02)) * S.perc(mm, SR, 0.001, dd)
        S.place(pings, ping, N(t0), rng.uniform(0.5, 1.0) * math.exp(-t0 / 0.1))
    shimmer = verb(lay((0.0, nz(fizz), 1.0), (0.0, ring, 0.25), (0.0, nz(pings), 0.4)), 0.6, 0.25)
    y = lay((0.0, core, 1.0), (0.0, crack, 0.9), (0.0, click(rng, 0.004, 1500.0, 12000.0, 0.0025), 0.55),
            (0.006, nz(shimmer), 0.45))
    return S.softclip(nz(y) * 1.3, 1.3)  # round off the transient peak so the body can sit louder


@sfx("ram_whiff", -6.0, "combat")
def ram_whiff(rng):
    dur = 0.2
    n = N(dur)
    t = T(n)
    # noise through a feedback comb whose pipe grows longer: a hollow, ghostly "hwoo" that deflates
    src = bn(n, rng, 200.0, 9000.0, 0.7)
    hollow = comb(src, S.curve([(0.0, 0.0021), (dur, 0.0034)], n, SR, "exp"), 0.72)
    hollow = S.fft_filter(hollow, SR, S.mag_bp(250.0, 4000.0, 1.5))
    tp = 0.075
    env = np.where(t < tp, (t / tp) ** 1.6, np.clip(1.0 - (t - tp) / (dur - tp), 0.0, 1.0) ** 1.8)
    air = whoosh(rng, dur, 3000.0, 6500.0, 2500.0, peak=0.38, q=1.0, color=0.3, air=0.3)
    return lay((0.0, nz(hollow) * env, 1.0), (0.0, nz(air), 0.25))


@sfx("dash_clash", -2.0, "combat", fade_in=0.001)
def dash_clash(rng):
    dur = 0.55
    n = N(dur)
    t = T(n)
    # the clang: bright struck-plate modes with an impact bend.  Pairs beat slowly (a shimmer, not a rasp);
    # the bright 3-4 kHz modes flash and die fast so no edge lingers, while E6 over a warm E5 (the battle
    # theme's dominant) carries the ring.
    f0 = S.hz("E6")
    ratios = [0.5, 1.0, 1.0045, 2.32, 2.97, 4.13, 5.4, 5.406]
    t60s = [0.36, 0.42, 0.38, 0.16, 0.12, 0.2, 0.24, 0.24]
    amps = [0.55, 1.0, 0.25, 0.55, 0.4, 0.35, 0.2, 0.18]
    clang = S.modal([f0 * r for r in ratios], t60s, amps, n, SR, rng, pitch_env=1.0 + 0.03 * np.exp(-t / 0.01),
                    attack=0.0005)
    # the air burst: a puff of displaced air whose brightness collapses fast
    m = N(0.3)
    burst = S.svf(bn(m, rng, 400.0, 14000.0, 0.5), SR,
                  S.curve([(0.0, 9000.0), (0.12, 1500.0), (0.3, 1000.0)], m, SR, "exp"), 0.8, "lp") * \
        S.perc(m, SR, 0.001, 0.18)
    # both bodies knocked back: a short receding swish
    back = whoosh(rng, 0.16, 2600.0, 3000.0, 900.0, peak=0.15, q=1.2, color=0.5, rise=1.5, fall=1.8, air=0.1)
    th = thump(260.0, 120.0, 0.01, 0.11, h2=0.25)
    sub = thump(95.0, 55.0, 0.04, 0.22, attack=0.002)
    y = lay((0.0, nz(clang), 0.7), (0.0, nz(burst), 0.55), (0.05, nz(back), 0.18), (0.0, th, 0.5), (0.0, sub, 0.3),
            (0.0, click(rng, 0.004, 1500.0, 12000.0, 0.002), 0.4))
    return verb(S.softclip(nz(y) * 1.2, 1.2), 0.7, 0.18)


@sfx("dash_blocked", -4.0, "combat", fade_in=0.001)
def dash_blocked(rng):
    n = N(0.13)
    # a dull knock whose pitch sags: "bonk" -- physical, but clearly a "no".  Pitched high enough (with
    # harmonics) that phone speakers still carry it.
    ph = S.TAU * S.phase_cycles(S.curve([(0.0, 340.0), (0.016, 235.0), (0.13, 200.0)], n, SR, "exp"), n, SR)
    bonk = (np.sin(ph) + 0.55 * np.sin(2 * ph) + 0.25 * np.sin(3 * ph) + 0.1 * np.sin(4 * ph)) * \
        S.perc(n, SR, 0.001, 0.11, curve_pow=1.2)
    wood = S.modal([290.0, 700.0, 1240.0], [0.06, 0.035, 0.018], [1.0, 0.6, 0.3], n, SR, rng, attack=0.0005)
    th = thump(150.0, 85.0, 0.01, 0.07)
    m = N(0.04)
    dull = bn(m, rng, 150.0, 1500.0, 1.0) * S.perc(m, SR, 0.0008, 0.03)
    y = lay((0.0, bonk, 1.0), (0.0, wood, 0.45), (0.0, th, 0.35), (0.0, nz(dull), 0.3))
    return S.onepole_lp(S.softclip(nz(y) * 1.4, 1.5), SR, 2200.0)


# ===========================================================================
# combat: hits & guards
# ===========================================================================

@sfx("hit_light", -3.0, "combat")
def hit_light(rng):
    n = N(0.07)
    slap = bn(n, rng, 900.0, 5500.0, 0.3) * S.perc(n, SR, 0.0004, 0.045)
    body = thump(290.0, 105.0, 0.011, 0.085, h2=0.15)
    core = S.softclip(nz(lay((0.0, body, 1.0), (0.0, slap, 0.5))), 1.8)
    return lay((0.0, core, 1.0), (0.0, click(rng, 0.004, 2000.0, 12000.0, 0.0022), 0.45))


@sfx("hit_heavy", -1.0, "combat")
def hit_heavy(rng):
    body = thump(175.0, 50.0, 0.024, 0.36, curve_pow=1.25)
    knock = thump(360.0, 185.0, 0.009, 0.06)
    sub = thump(52.0, 42.0, 0.05, 0.42, attack=0.004)
    n = N(0.2)
    meat = bn(n, rng, 40.0, 520.0, 1.5) * S.perc(n, SR, 0.0015, 0.14)
    n2 = N(0.16)
    crunch = S.softclip(bn(n2, rng, 700.0, 4200.0), 3.0) * (0.4 + 0.6 * flutter(n2, rng, 600.0)) * \
        S.perc(n2, SR, 0.0008, 0.15)
    core = lay((0.0, body, 1.0), (0.0, knock, 0.4), (0.0, sub, 0.5), (0.0, nz(meat), 0.6))
    core = S.softclip(nz(core) * 1.6, 2.0)
    return lay((0.0, core, 1.0), (0.001, nz(crunch), 0.5), (0.0, click(rng, 0.005, 1500.0, 10000.0, 0.003), 0.45))


@sfx("hit_effective", -2.0, "combat")
def hit_effective(rng):
    body = thump(230.0, 75.0, 0.016, 0.2, curve_pow=1.2)
    n = N(0.1)
    slap = bn(n, rng, 900.0, 6000.0) * S.perc(n, SR, 0.0005, 0.06)
    core = S.softclip(nz(lay((0.0, body, 1.0), (0.0, slap, 0.45))) * 1.4, 1.8)
    f = 2350.0
    m = N(0.5)
    sting = S.modal([f, f * 2.32, f * 3.86, f * 5.1], [0.45, 0.25, 0.14, 0.08], [1.0, 0.45, 0.25, 0.12], m, SR, rng,
                    attack=0.001)
    mg = N(0.06)
    gl = np.sin(S.TAU * S.phase_cycles(S.curve([(0.0, 1800.0), (0.04, 3600.0)], mg, SR, "exp"), mg, SR)) * \
        S.perc(mg, SR, 0.002, 0.05)
    st = verb(lay((0.0, sting, 1.0), (0.0, gl, 0.4)), 0.6, 0.15)
    return lay((0.0, core, 1.0), (0.0, click(rng, 0.004, 2000.0, 12000.0, 0.0025), 0.4), (0.004, nz(st), 0.42))


@sfx("hit_resisted", -6.0, "combat")
def hit_resisted(rng):
    body = thump(150.0, 72.0, 0.02, 0.14, curve_pow=1.3)
    n = N(0.1)
    muff = bn(n, rng, 60.0, 600.0, 1.0) * S.perc(n, SR, 0.002, 0.06)
    c = click(rng, 0.004, 400.0, 1800.0, 0.003)
    return S.onepole_lp(lay((0.0, body, 1.0), (0.0, muff, 0.35), (0.0, c, 0.15)), SR, 1800.0)


@sfx("guard_block", -3.0, "combat")
def guard_block(rng):
    n = N(0.12)
    clack = S.modal([1050.0, 1790.0, 2640.0, 3920.0], [0.06, 0.045, 0.03, 0.02], [1.0, 0.7, 0.5, 0.3], n, SR, rng,
                    attack=0.0003)
    th = thump(230.0, 140.0, 0.008, 0.05)
    m = N(0.45)
    tt = T(m)
    sh = np.zeros(m)
    for a, b in [(3200.0, 3207.0), (4300.0, 4311.0), (5650.0, 5662.0)]:
        sh += np.sin(S.TAU * a * tt) + np.sin(S.TAU * b * tt + 1.0)
    sh *= S.perc(m, SR, 0.006, 0.35) / 6.0
    shn = bn(m, rng, 5000.0, 11000.0) * S.perc(m, SR, 0.004, 0.22)
    return lay((0.0, nz(clack), 1.0), (0.0, th, 0.45), (0.0, click(rng, 0.004, 2000.0, 11000.0, 0.002), 0.55),
               (0.003, sh, 0.3), (0.003, shn, 0.05))


@sfx("perfect_guard", -4.0, "combat")
def perfect_guard(rng):
    rs = 0.12
    f = S.hz("A6")
    tone = S.modal([f, f * 2.0, f * 3.01, f * 4.17, f * 5.43], [0.5, 0.35, 0.25, 0.15, 0.1],
                   [1.0, 0.5, 0.3, 0.2, 0.12], N(0.5), SR, rng)
    rev = verb(tone, 0.8, 0.6)[:N(0.5)][::-1]
    swell = rev[-N(rs):] * np.linspace(0.0, 1.0, N(rs)) ** 2
    noise_sw = bn(N(rs), rng, 3000.0, 11000.0) * np.linspace(0.0, 1.0, N(rs)) ** 3
    m = N(0.7)
    ting = S.modal([f, f * 2.0, f * 2.76, f * 4.1, f * 5.4], [0.6, 0.42, 0.3, 0.2, 0.12],
                   [1.0, 0.45, 0.3, 0.18, 0.1], m, SR, rng, attack=0.0005)
    sparkle = S.fm(f * 2.0, m, SR, 1.5, 0.8 * np.exp(-T(m) / 0.05)) * S.perc(m, SR, 0.001, 0.4)
    hit = lay((0.0, ting, 1.0), (0.0, sparkle, 0.25), (0.0, click(rng, 0.003, 4000.0, 14000.0, 0.0015), 0.4))
    return lay((0.0, nz(swell), 0.5), (0.0, noise_sw, 0.08), (rs, verb(hit, 1.0, 0.2), 1.0))


@sfx("guard_break", -1.0, "combat")
def guard_break(rng):
    dur = 0.9
    n = N(dur)
    th = thump(210.0, 70.0, 0.012, 0.16)
    n1 = N(0.15)
    crunch = S.softclip(bn(n1, rng, 900.0, 6000.0), 2.5) * S.perc(n1, SR, 0.0005, 0.1)
    shards = np.zeros(n)
    for _ in range(80):
        t0 = rng.exponential(0.09)
        if t0 > 0.65:
            continue
        fs = np.exp(rng.uniform(math.log(2200.0), math.log(9500.0), 2))
        ds = rng.uniform(0.015, 0.09, 2)
        g = S.modal(fs, ds, [1.0, 0.6], N(float(ds.max()) * 1.05) + 4, SR, rng, attack=0.0002)
        S.place(shards, g, N(t0), rng.lognormal(0.0, 0.4) * math.exp(-t0 / 0.25))
    chunks = debris(rng, dur, 10, 0.07, 600.0, 1800.0, 1.0, 0.0, (0.02, 0.06))
    glass = bn(n, rng, 4000.0, 13000.0) * S.perc(n, SR, 0.001, 0.32)
    m = N(0.1)
    crack = bn(m, rng, 300.0, 1500.0) * S.perc(m, SR, 0.0008, 0.07)
    y = lay((0.0, th, 0.8), (0.0, click(rng, 0.005, 1500.0, 12000.0, 0.003), 0.6), (0.0, crunch, 0.4),
            (0.002, nz(shards), 0.7), (0.005, nz(chunks), 0.35), (0.0, glass, 0.12), (0.0, crack, 0.35))
    return verb(y, 0.7, 0.14)


# ===========================================================================
# combat: focus & stamina
# ===========================================================================

@sfx("focus_start", -6.0, "combat")
def focus_start(rng):
    dur = 0.7
    n = N(dur)
    t = T(n)
    breath = S.svf(bn(n, rng, 200.0, 9000.0, 0.5), SR, S.curve([(0.0, 450.0), (0.62, 2300.0)], n, SR, "exp"),
                   1.4, "bp")
    benv = np.clip(t / 0.6, 0, 1) ** 1.5 * gated_ramp(n, [(0.0, 1.0), (0.58, 1.0), (0.7, 0.0)])
    ph = S.phase_cycles(S.curve([(0.0, 110.0), (0.62, 220.0)], n, SR, "exp"), n, SR)
    hum = np.sin(S.TAU * ph) + 0.4 * np.sin(2 * S.TAU * ph) + 0.18 * np.sin(3 * S.TAU * ph) + \
        0.25 * np.sin(1.5 * S.TAU * ph)
    henv = np.clip(t / 0.62, 0, 1) ** 2 * gated_ramp(n, [(0.0, 1.0), (0.6, 1.0), (0.7, 0.0)])
    return lay((0.0, nz(breath) * benv, 0.55), (0.0, hum * henv / 2.0, 0.7))


@sfx("focus_loop", -14.0, "loop", loop=True)
def focus_loop(rng):
    n = N(1.0)  # 44100 samples: integer-Hz partials complete whole cycles -> seamless
    t = T(n)
    partials = [(110, 1.0), (111, 0.45), (165, 0.5), (220, 0.35), (221, 0.2), (330, 0.15), (440, 0.06)]
    hum = sum(a * np.sin(S.TAU * f * t + rng.uniform(0, S.TAU)) for f, a in partials)
    pulse = 0.72 + 0.28 * np.sin(S.TAU * 2.0 * t - np.pi / 2)
    shimmer = S.fft_filter(rng.standard_normal(n), SR, S.mag_bp(2500.0, 6500.0, 1.5), circular=True)
    shimmer = shimmer / np.std(shimmer) * (0.5 + 0.5 * np.sin(S.TAU * 4.0 * t))
    return nz(hum) * pulse + 0.035 * shimmer


@sfx("focus_full", -6.0, "combat")
def focus_full(rng):
    f = S.hz("A6")
    ding = S.modal([f, f * 2.0, f * 3.0, f * 4.2], [0.7, 0.4, 0.25, 0.12], [1.0, 0.4, 0.2, 0.1], N(0.75), SR, rng,
                   attack=0.0008)
    under = I.celesta(S.hz("A5"), 0.5, 0.6, SR, rng, t60=0.7)
    sp = glints(rng, 0.7, 16, 4500.0, 10000.0, (0.05, 0.22), 0.02, 0.5, level=0.6)
    return verb(lay((0.0, ding, 1.0), (0.0, under, 0.5), (0.0, sp, 0.22)), 1.0, 0.22)


@sfx("surge_stage", -7.0, "combat")
def surge_stage(rng):
    """A Surge stage fills: a rising two-note chime on a short bright swell
    (the game pitches it up a step for each stage)."""
    a = I.celesta(S.hz("E6"), 0.4, 0.8, SR, rng, t60=0.45)
    b = I.celesta(S.hz("B6"), 0.4, 0.9, SR, rng, t60=0.6)
    sw = whoosh(rng, 0.22, 900.0, 5200.0, 7000.0, peak=0.8, q=1.4, color=0.5, rise=1.6, fall=2.5, air=0.4)
    sp = glints(rng, 0.5, 10, 5000.0, 11000.0, (0.04, 0.16), 0.06, 0.4, level=0.5)
    return verb(lay((0.0, nz(sw), 0.3), (0.05, a, 0.8), (0.12, b, 1.0), (0.1, sp, 0.25)), 0.8, 0.2)


@sfx("surge_release", -4.0, "spell")
def surge_release(rng):
    """A big special spends its Surge: a low swell rising into a bright burst."""
    n = N(0.7)
    f = S.curve([(0.0, 70.0), (0.32, 210.0), (0.7, 160.0)], n, SR, "exp")
    swell = S.fm(f, n, SR, 2.0, 1.6) * S.swell(n, SR, 0.3, 0.38)
    rise = whoosh(rng, 0.42, 300.0, 4200.0, 2000.0, peak=0.85, q=0.9, color=1.0, rise=2.2, fall=1.4, air=0.3)
    burst = thump(420.0, 110.0, 0.02, 0.22)
    chord = lay((0.0, I.bell(S.hz("A5"), 0.6, 0.8, SR, rng, t60=0.9), 0.6),
                (0.0, I.celesta(S.hz("E6"), 0.5, 0.9, SR, rng, t60=0.7), 0.5))
    sp = glints(rng, 0.6, 18, 4000.0, 11000.0, (0.05, 0.25), 0.0, 0.5, level=0.6)
    y = lay((0.0, nz(swell), 0.55), (0.0, nz(rise), 0.6), (0.36, nz(burst), 0.7), (0.36, nz(chord), 0.45),
            (0.38, sp, 0.25))
    return verb(S.softclip(nz(y), 1.1), 1.1, 0.22)


@sfx("stamina_empty", -10.0, "combat")
def stamina_empty(rng):
    def blip(f, dur):
        n = N(dur)
        y = S.svf(0.55 * S.pulse(f, n, SR, 0.5) + 0.45 * S.sine(f, n, SR), SR, 2400.0, 0.7, "lp")
        return y * S.adsr(n, SR, a=0.003, d=0.02, s=0.85, r=0.018, gate=dur - 0.018)
    return lay((0.0, blip(659.0, 0.075), 1.0), (0.125, blip(659.0, 0.075), 0.9))


# ===========================================================================
# combat: Emberlyn moves (fire)
# ===========================================================================

@sfx("ember_bolt_cast", -5.0, "spell")
def ember_bolt_cast(rng):
    n = N(0.24)
    t = T(n)
    f = S.curve([(0.0, 1750.0), (0.13, 380.0), (0.24, 300.0)], n, SR, "exp")
    zap = S.fm(f, n, SR, 1.5, 2.2 * np.exp(-t / 0.06) + 0.3) * S.perc(n, SR, 0.002, 0.2)
    fw = whoosh(rng, 0.34, 420.0, 2600.0, 900.0, peak=0.25, q=0.9, color=1.0, rise=1.4)
    m = N(0.34)
    cr = crackle(m, rng, lambda tt: 90.0 * math.exp(-tt / 0.15), size=0.5, pop=0.1)
    body = bn(m, rng, 80.0, 800.0, 1.5) * S.swell(m, SR, 0.06, 0.25)
    y = lay((0.0, zap, 0.6), (0.0, nz(fw), 0.8), (0.01, nz(cr), 0.3), (0.0, nz(body), 0.35))
    return S.softclip(nz(y), 1.2)


@sfx("ember_bolt_impact", -3.0, "spell")
def ember_bolt_impact(rng):
    pop = thump(320.0, 90.0, 0.008, 0.07)
    n1 = N(0.08)
    burst = bn(n1, rng, 500.0, 4500.0) * S.perc(n1, SR, 0.0005, 0.05)
    n = N(0.4)
    puff = S.svf(bn(n, rng, 60.0, 9000.0, 1.0), SR, S.curve([(0.0, 2600.0), (0.3, 420.0)], n, SR, "exp"), 0.7, "lp") * \
        S.perc(n, SR, 0.003, 0.28)
    cr = crackle(n, rng, lambda tt: 75.0 * math.exp(-tt / 0.12), size=0.6, pop=0.2)
    y = lay((0.0, pop, 0.8), (0.0, click(rng, 0.004, 1200.0, 10000.0, 0.0025), 0.5), (0.0, burst, 0.45),
            (0.0, nz(puff), 0.6), (0.01, nz(cr), 0.35))
    return S.softclip(nz(y), 1.4)


@sfx("cinder_arc", -3.0, "spell")
def cinder_arc(rng):
    dur = 0.55
    n = N(dur)
    broad = whoosh(rng, dur, 300.0, 1800.0, 550.0, peak=0.4, q=0.7, color=1.3, rise=1.6, fall=1.3)
    roar = bn(n, rng, 60.0, 600.0, 1.5) * (0.7 + 0.3 * S.lfo_noise(n, SR, 11.0, rng)) * S.swell(n, SR, 0.2, 0.4, shape=1.5)
    thin = whoosh(rng, dur, 1800.0, 6500.0, 3000.0, peak=0.5, q=1.0, color=0.0)
    cr = crackle(n, rng, lambda tt: 80.0 * float(np.interp(tt, [0.0, 0.2, 0.55], [0.2, 1.0, 0.4])), size=0.5, pop=0.15)
    return lay((0.0, nz(broad), 1.0), (0.0, nz(roar), 0.45), (0.03, nz(thin), 0.25), (0.0, nz(cr), 0.3))


@sfx("flash_strike", -2.0, "combat")
def flash_strike(rng):
    layers = []
    for i, t0 in enumerate([0.0, 0.085, 0.17]):
        last = i == 2
        g = 0.75 + 0.25 * i
        sw = whoosh(rng, 0.06, 2500.0, 9000.0, 5000.0, peak=0.65, q=0.8, color=0.0, rise=2.2, fall=1.5)
        f = 3100.0 + 260.0 * i
        ring = S.modal([f, f * 1.5, f * 2.03], [0.12 + 0.2 * last, 0.08 + 0.12 * last, 0.05 + 0.08 * last],
                       [1.0, 0.5, 0.3], N(0.35 if last else 0.15), SR, rng, attack=0.0005)
        layers += [(t0, nz(sw), 0.7 * g), (t0 + 0.035, ring, 0.25 * g),
                   (t0 + 0.035, click(rng, 0.003, 3000.0, 14000.0, 0.0015), 0.4 * g)]
        if last:
            layers.append((t0 + 0.035, thump(190.0, 80.0, 0.012, 0.12), 0.5))
    return lay(*layers)


@sfx("heat_ring_charge", -5.0, "spell")
def heat_ring_charge(rng):
    dur = 0.6
    n = N(dur)
    t = T(n)
    siz = S.svf(bn(n, rng, 1500.0, 14000.0), SR, S.curve([(0.0, 2500.0), (dur, 7000.0)], n, SR, "exp"), 1.2, "bp")
    siz *= 0.3 + 0.7 * flutter(n, rng, 900.0)
    cr = crackle(n, rng, lambda tt: 40.0 + 220.0 * (tt / dur) ** 2, size=0.5, pop=0.05)
    ph = S.phase_cycles(S.curve([(0.0, 180.0), (dur, 720.0)], n, SR, "exp"), n, SR)
    trem = 0.6 + 0.4 * np.sin(S.TAU * S.phase_cycles(S.curve([(0.0, 8.0), (dur, 30.0)], n, SR, "exp"), n, SR))
    tone = (np.sin(S.TAU * ph) + 0.3 * np.sin(2 * S.TAU * ph)) * trem
    return (nz(siz) * 0.6 + nz(cr) * 0.3 + tone * 0.35) * np.clip(t / dur, 0, 1) ** 1.5


@sfx("heat_ring_burst", -1.0, "spell")
def heat_ring_burst(rng):
    dur = 1.0
    n = N(dur)
    boom = thump(125.0, 40.0, 0.03, 0.5, curve_pow=1.2)
    sub = thump(48.0, 36.0, 0.08, 0.6, attack=0.004)
    blast = S.svf(bn(n, rng, 40.0, 12000.0, 1.0), SR, S.curve([(0.0, 6000.0), (0.5, 500.0), (1.0, 300.0)], n, SR, "exp"),
                  0.7, "lp") * S.perc(n, SR, 0.002, 0.5)
    ring = S.svf(bn(n, rng, 100.0, 10000.0, 0.5), SR, S.curve([(0.0, 3200.0), (0.6, 380.0)], n, SR, "exp"), 2.2, "bp") * \
        S.swell(n, SR, 0.04, 0.65, shape=1.2)
    cr = crackle(n, rng, lambda tt: 140.0 * math.exp(-tt / 0.3), size=0.6, pop=0.25)
    roar = bn(n, rng, 120.0, 1500.0, 1.0) * (0.7 + 0.3 * S.lfo_noise(n, SR, 10.0, rng)) * S.perc(n, SR, 0.02, 0.8)
    y = lay((0.0, boom, 1.0), (0.0, sub, 0.6), (0.0, nz(blast), 0.7), (0.0, nz(ring), 0.45), (0.0, nz(cr), 0.3),
            (0.0, nz(roar), 0.3), (0.0, click(rng, 0.005, 1000.0, 9000.0, 0.003), 0.5))
    return S.softclip(nz(y) * 1.3, 1.6)


@sfx("burn_tick", -8.0, "spell")
def burn_tick(rng):
    n = N(0.16)
    siz = bn(n, rng, 3000.0, 11000.0) * (0.25 + 0.75 * flutter(n, rng, 700.0)) * S.perc(n, SR, 0.005, 0.11)
    cr = crackle(n, rng, 45.0, size=0.6, pop=0.1)
    return lay((0.0, siz, 0.6), (0.0, nz(cr), 0.5))


# ===========================================================================
# combat: Stoneback moves (earth)
# ===========================================================================

@sfx("boulder_toss", -3.0, "combat")
def boulder_toss(rng):
    gd = 0.2
    m = N(gd)
    f0 = S.curve([(0.0, 118.0), (0.05, 125.0), (gd, 88.0)], m, SR, "exp") * (1 + 0.03 * S.lfo_noise(m, SR, 30.0, rng))
    gr = voice(f0, m, "uh", None, bw=1.6, kmax=60, tilt=2400.0)
    gr = nz(gr) * (1.0 - 0.4 * (0.5 + 0.5 * np.sin(S.TAU * S.phase_cycles(f0 * 0.5, m, SR)))) * \
        S.adsr(m, SR, 0.02, 0.08, 0.8, 0.06, gate=gd - 0.06)
    w = whoosh(rng, 0.42, 160.0, 750.0, 300.0, peak=0.45, q=1.0, color=1.4, air=0.1)
    n = N(0.42)
    tumble = bn(n, rng, 40.0, 260.0, 2.0) * (0.5 + 0.5 * np.sin(S.TAU * 9.0 * T(n))) * S.swell(n, SR, 0.15, 0.3)
    return lay((0.0, nz(gr), 0.75), (0.13, nz(w), 1.0), (0.13, nz(tumble), 0.3))


@sfx("boulder_impact", -1.0, "impact")
def boulder_impact(rng):
    dur = 0.9
    thud = thump(135.0, 42.0, 0.03, 0.45, curve_pow=1.2)
    sub = thump(44.0, 36.0, 0.08, 0.5, attack=0.004)
    n1 = N(0.12)
    crack = bn(n1, rng, 800.0, 5000.0) * S.perc(n1, SR, 0.0005, 0.08)
    crunch = crackle(N(0.35), rng, lambda tt: 900.0 * math.exp(-tt / 0.06), bright=0.5, size=1.0, pop=0.4, hp=300.0)
    deb = debris(rng, dur, 42, 0.15, 400.0, 4000.0, 1.0, 0.02)
    n = N(dur)
    dust = bn(n, rng, 200.0, 1500.0, 1.0) * S.perc(n, SR, 0.02, 0.5)
    core = S.softclip(nz(lay((0.0, thud, 1.0), (0.0, sub, 0.55))) * 1.5, 1.8)
    return lay((0.0, core, 1.0), (0.0, click(rng, 0.005, 1200.0, 10000.0, 0.003), 0.5), (0.0, crack, 0.35),
               (0.0, nz(crunch), 0.45), (0.01, nz(deb), 0.35), (0.0, dust, 0.06))


@sfx("ground_pound", -1.0, "impact")
def ground_pound(rng):
    dur = 1.6
    n = N(dur)
    boom = thump(100.0, 32.0, 0.04, 1.0, curve_pow=1.15)
    sub = thump(36.0, 29.0, 0.15, 1.2, attack=0.006)
    n1 = N(0.2)
    crunch = S.softclip(bn(n1, rng, 200.0, 3000.0, 0.5), 2.0) * S.perc(n1, SR, 0.0008, 0.15)
    blast = S.svf(bn(n, rng, 30.0, 8000.0, 1.0), SR, S.curve([(0.0, 3200.0), (0.6, 220.0)], n, SR, "exp"), 0.7, "lp") * \
        S.perc(n, SR, 0.003, 0.6)
    deb = debris(rng, dur, 90, 0.35, 350.0, 4500.0, 1.0, 0.06)
    rumble = bn(n, rng, 20.0, 130.0, 2.0) * S.perc(n, SR, 0.05, 1.3) * (0.7 + 0.3 * S.lfo_noise(n, SR, 5.0, rng))
    core = S.softclip(nz(lay((0.0, boom, 1.0), (0.0, sub, 0.65))) * 1.6, 2.0)
    return lay((0.0, core, 1.0), (0.0, click(rng, 0.006, 900.0, 9000.0, 0.004), 0.5), (0.0, crunch, 0.4),
               (0.0, nz(blast), 0.45), (0.02, nz(deb), 0.3), (0.0, nz(rumble), 0.3))


@sfx("stone_guard_on", -3.0, "combat")
def stone_guard_on(rng):
    layers = []
    for t0, sc, g in [(0.0, 1.0, 0.8), (0.07, 1.12, 0.75), (0.15, 0.92, 0.85), (0.25, 0.8, 1.0)]:
        n = N(0.1)
        f = 900.0 * sc
        clk = S.modal([f, f * 1.78, f * 2.79, f * 4.0], [0.05, 0.035, 0.02, 0.014], [1.0, 0.6, 0.4, 0.2], n, SR, rng,
                      attack=0.0003)
        th = thump(260.0 * sc, 150.0 * sc, 0.008, 0.05)
        layers.append((t0, lay((0.0, clk, 1.0), (0.0, th, 0.5),
                                (0.0, click(rng, 0.003, 2000.0, 10000.0, 0.0018), 0.5)), g))
    dur = 0.95
    n = N(dur)
    t = T(n)
    hum = sum(a * np.sin(S.TAU * f * t) for f, a in [(98.0, 1.0), (99.0, 0.5), (147.0, 0.5), (196.0, 0.3), (294.0, 0.12)])
    hum *= gated_ramp(n, [(0.0, 0.0), (0.1, 0.0), (0.45, 1.0), (dur, 0.0)])
    grit = crackle(n, rng, lambda tt: 120.0 if tt < 0.3 else 20.0, bright=0.5, size=0.3, pop=0.2)
    return lay(*layers, (0.0, hum / 3.0, 0.6), (0.0, nz(grit), 0.12))


@sfx("stone_guard_block", -2.0, "combat")
def stone_guard_block(rng):
    n = N(0.4)
    clank = S.modal([620.0, 1340.0, 2210.0, 3170.0, 4400.0], [0.18, 0.12, 0.09, 0.06, 0.04],
                    [1.0, 0.7, 0.5, 0.35, 0.2], n, SR, rng, attack=0.0003)
    th = thump(210.0, 110.0, 0.01, 0.08)
    m = N(0.25)
    tt = T(m)
    f = S.curve([(0.0, 3300.0), (0.2, 1800.0)], m, SR, "exp") * (1 + 0.01 * np.sin(S.TAU * 30.0 * tt))
    zing = np.sin(S.TAU * S.phase_cycles(f, m, SR)) * S.perc(m, SR, 0.003, 0.22)
    deb = debris(rng, 0.4, 6, 0.05, 700.0, 3500.0, 0.6)
    return lay((0.0, nz(clank), 0.9), (0.0, th, 0.5), (0.0, click(rng, 0.004, 1800.0, 12000.0, 0.002), 0.55),
               (0.012, zing, 0.22), (0.01, nz(deb), 0.2))


@sfx("fault_line_charge", -3.0, "spell")
def fault_line_charge(rng):
    dur = 1.1
    n = N(dur)
    t = T(n)
    rate = S.curve([(0.0, 12.0), (dur, 42.0)], n, SR, "exp")
    ph = S.phase_cycles(rate * (1 + 0.15 * S.lfo_noise(n, SR, 20.0, rng)), n, SR)
    grind = np.zeros(n)
    for i in np.nonzero(np.diff(np.floor(ph)) > 0)[0]:
        m = N(0.025)
        S.place(grind, bn(m, rng, 150.0, 1600.0) * S.perc(m, SR, 0.002, 0.02), int(i), rng.uniform(0.5, 1.0))
    rumble = bn(n, rng, 20.0, 150.0, 2.0)
    tone = S.additive(S.curve([(0.0, 45.0), (dur, 72.0)], n, SR, "exp"), n, SR, S.harmonic_amps("saw", 12),
                      lowpass=300.0)
    grit = crackle(n, rng, lambda tt: 30.0 + 200.0 * (tt / dur) ** 2, bright=0.6, size=0.4, pop=0.3)
    y = (nz(grind) * 0.6 + nz(rumble) * 0.6 + nz(tone) * 0.4 + nz(grit) * 0.2) * np.clip(t / dur, 0, 1) ** 1.4
    return S.softclip(nz(y) * 1.2, 1.3)


@sfx("fault_line_erupt", -2.0, "impact")
def fault_line_erupt(rng):
    layers = []
    for i, t0 in enumerate([0.0, 0.125, 0.235, 0.335, 0.43, 0.52]):
        th = thump(rng.uniform(115.0, 150.0), rng.uniform(44.0, 55.0), 0.02, 0.26, curve_pow=1.2)
        n1 = N(0.09)
        cr = bn(n1, rng, 500.0, 4500.0) * S.perc(n1, SR, 0.0005, 0.06)
        deb = debris(rng, 0.35, 9, 0.08, 500.0, 4000.0, 1.0)
        ev = lay((0.0, th, 1.0), (0.0, cr, 0.4), (0.0, click(rng, 0.004, 1200.0, 10000.0, 0.0025), 0.45),
                 (0.01, nz(deb), 0.3))
        layers.append((t0, ev, 1.0 - 0.06 * i))
    n = N(0.85)
    rumble = bn(n, rng, 20.0, 140.0, 2.0) * gated_ramp(n, [(0.0, 0.3), (0.1, 1.0), (0.6, 0.8), (0.85, 0.0)])
    return S.softclip(nz(lay(*layers, (0.0, nz(rumble), 0.35))) * 1.3, 1.6)


@sfx("projectile_clash", -2.0, "spell")
def projectile_clash(rng):
    pop = thump(420.0, 120.0, 0.006, 0.07)
    n1 = N(0.06)
    burst = bn(n1, rng, 1000.0, 7000.0) * S.perc(n1, SR, 0.0004, 0.04)
    m = N(0.12)
    zap = S.fm(S.curve([(0.0, 1300.0), (0.1, 600.0)], m, SR, "exp"), m, SR, 2.3, 3.0 * np.exp(-T(m) / 0.03)) * \
        S.perc(m, SR, 0.001, 0.09)
    n = N(0.5)
    cr = crackle(n, rng, lambda t: 170.0 * math.exp(-t / 0.12), bright=1.2, size=0.6, pop=0.08)
    sp = glints(rng, 0.5, 6, 3000.0, 7000.0, (0.04, 0.12), 0.0, 0.25)
    return lay((0.0, pop, 0.8), (0.0, click(rng, 0.004, 1500.0, 12000.0, 0.0025), 0.5), (0.0, burst, 0.45),
               (0.0, zap, 0.3), (0.005, nz(cr), 0.4), (0.01, nz(sp), 0.15))


# ===========================================================================
# combat: knockouts, results, crowd
# ===========================================================================

@sfx("ko_hit", -1.0, "impact")
def ko_hit(rng):
    dur = 3.0
    n = N(dur)
    t = T(n)
    body = thump(150.0, 38.0, 0.03, 0.65, curve_pow=1.2)
    sub = thump(42.0, 33.0, 0.12, 1.0, attack=0.005)
    knock = thump(380.0, 190.0, 0.008, 0.07)
    n1 = N(0.2)
    crunch = S.softclip(bn(n1, rng, 600.0, 5000.0), 2.5) * S.perc(n1, SR, 0.0008, 0.13)
    blast = S.svf(bn(n, rng, 30.0, 9000.0, 1.0), SR, S.curve([(0.0, 4500.0), (0.5, 300.0)], n, SR, "exp"), 0.7, "lp") * \
        S.perc(n, SR, 0.002, 0.45)
    core = S.softclip(nz(lay((0.0, body, 1.0), (0.0, sub, 0.6), (0.0, knock, 0.35))) * 1.6, 2.0)
    ring = (np.sin(S.TAU * 2217.0 * t) + np.sin(S.TAU * 2224.0 * t + 0.5) + 0.4 * np.sin(S.TAU * 3480.0 * t) +
            0.25 * np.sin(S.TAU * 4410.0 * t)) * S.perc(n, SR, 0.004, 3.2) / 2.0
    gong = S.modal([196.0 * r for r in [1.0, 1.5, 2.02, 2.51, 3.03]], [2.5, 2.0, 1.6, 1.2, 0.9],
                   [1.0, 0.6, 0.45, 0.3, 0.2], n, SR, rng, attack=0.003)
    y = lay((0.0, core, 1.0), (0.0, click(rng, 0.006, 1200.0, 12000.0, 0.0035), 0.5), (0.0, crunch, 0.35),
            (0.0, nz(blast), 0.4), (0.005, ring, 0.2), (0.0, nz(gong), 0.24))
    return verb(y, 2.0, 0.25)


@sfx("ko_fall", -3.0, "impact")
def ko_fall(rng):
    def thud(g, sc):
        th = thump(120.0 * sc, 50.0 * sc, 0.02, 0.25, curve_pow=1.3)
        m = N(0.15)
        body = bn(m, rng, 40.0, 450.0, 1.5) * S.perc(m, SR, 0.002, 0.12)
        return lay((0.0, th, 1.0), (0.0, nz(body), 0.5)) * g
    n = N(0.5)
    dust = bn(n, rng, 300.0, 2500.0, 1.0) * S.perc(n, SR, 0.01, 0.35)
    m = N(0.2)
    rustle = bn(m, rng, 1000.0, 5000.0) * S.perc(m, SR, 0.005, 0.15)
    return lay((0.0, thud(1.0, 1.0), 1.0), (0.17, thud(0.35, 1.15), 1.0), (0.005, dust, 0.06), (0.0, rustle, 0.05))


@sfx("victory_jingle", -3.0, "jingle", max_dur=3.2)
def victory_jingle(rng):
    return M.render_song(M.victory_jingle_song(SR))


@sfx("defeat_jingle", -7.0, "jingle", max_dur=3.4)
def defeat_jingle(rng):
    return M.render_song(M.defeat_jingle_song(SR))


@sfx("crowd_cheer", -5.0, "crowd", max_dur=2.6)
def crowd_cheer(rng):
    dur = 2.5
    n = N(dur)
    t = T(n)
    master = gated_ramp(n, [(0.0, 0.0), (0.18, 0.85), (0.5, 1.0), (1.9, 0.9), (2.5, 0.0)])
    pulse = 0.68 + 0.32 * np.sin(S.TAU * 2.1 * t - 1.2) ** 2
    voices = np.zeros(n)
    for i in range(18):
        x = formant_noise(n, rng, ["a", "e", "o", "a", "uh"][i % 5], bw=2.2)
        voices += x * np.clip(0.6 + 0.5 * S.lfo_noise(n, SR, rng.uniform(2.0, 4.0), rng), 0, 1.3) * rng.uniform(0.5, 1.0)
    voiced = np.zeros(n)
    for i in range(10):
        st, ln = rng.uniform(0.0, 0.6), rng.uniform(0.6, 1.6)
        m = N(ln)
        tt = T(m)
        f0 = rng.uniform(170.0, 330.0) * S.curve([(0.0, 1.0), (0.15, 1.12), (ln, 0.92)], m, SR, "exp") * \
            (1 + 0.02 * np.sin(S.TAU * 5.5 * tt))
        v = voice(f0, m, ["a", "e", "o"][i % 3], "a", morph=np.clip(tt / ln, 0, 1), bw=1.5, kmax=30, tilt=3000.0)
        v = nz(v) * S.adsr(m, SR, 0.08, 0.2, 0.8, 0.3, gate=ln - 0.3)
        S.place(voiced, v, N(st), rng.uniform(0.3, 0.7))
    claps = np.zeros(n)
    for t0 in S.grain_times(lambda tt: 160.0 * float(np.interp(tt, [0.0, 0.3, 2.0, 2.5], [0.1, 1.0, 0.9, 0.2])), dur, rng):
        m = N(0.03)
        S.place(claps, bn(m, rng, 800.0, 5000.0) * S.perc(m, SR, 0.0005, 0.02), N(t0), rng.uniform(0.3, 1.0))
    whist = np.zeros(n)
    for t0, fa, fb in [(0.35, 1900.0, 2900.0), (1.25, 2200.0, 3100.0)]:
        m = N(0.45)
        f = S.curve([(0.0, fa), (0.12, fb), (0.45, fb * 0.93)], m, SR, "exp")
        S.place(whist, np.sin(S.TAU * S.phase_cycles(f, m, SR)) * S.adsr(m, SR, 0.03, 0.1, 0.8, 0.12, gate=0.33), N(t0))
    bed = bn(n, rng, 250.0, 3500.0, 1.0)
    y = (nz(voices) * 0.8 + nz(voiced) * 0.25 + nz(claps) * 0.35 + nz(bed) * 0.3) * master * pulse + \
        0.06 * whist * master
    return S.fft_filter(y, SR, S.mag_lp(5000.0, 1.5))


@sfx("crowd_gasp", -7.0, "crowd")
def crowd_gasp(rng):
    dur = 0.9
    n = N(dur)
    out = np.zeros(n)
    for _ in range(16):
        st, ln = rng.uniform(0.0, 0.06), rng.uniform(0.55, 0.8)
        m = N(ln)
        tt = T(m)
        f0 = rng.uniform(150.0, 300.0) * S.curve([(0.0, 1.0), (0.12, 1.04), (ln, 0.88)], m, SR, "exp")
        v = nz(voice(f0, m, "u", "o", morph=np.clip(tt / 0.3, 0, 1), bw=1.6, kmax=24, tilt=2200.0))
        br = formant_noise(m, rng, "u", bw=2.0) * 0.25
        e = gated_ramp(m, [(0.0, 0.0), (0.09, 1.0), (0.2, 0.85), (ln, 0.0)])
        S.place(out, (v + br) * e, N(st), rng.uniform(0.5, 1.0))
    m = N(0.14)
    inhale = bn(m, rng, 1000.0, 6000.0) * S.swell(m, SR, 0.06, 0.08)
    return lay((0.0, nz(out), 1.0), (0.0, inhale, 0.12))


@sfx("crowd_ambience_loop", -14.0, "loop", loop=True)
def crowd_ambience_loop(rng):
    n = N(4.0)
    babble = np.zeros(n)
    for i in range(16):  # whispered syllables: periodic noise x periodic syllable envelopes
        x = formant_noise(n, rng, ["a", "e", "o", "uh", "i"][i % 5], bw=2.0, circular=True)
        syl = np.maximum(S.lfo_noise(n, SR, rng.uniform(3.5, 6.0), rng), 0.0) ** 1.2
        slow = np.clip(0.5 + 0.5 * S.lfo_noise(n, SR, 0.3, rng), 0.0, 1.0)
        babble += x * syl * (0.4 + 0.6 * slow) * rng.uniform(0.4, 1.0)
    voiced = np.zeros(n)
    for i in range(14):  # voiced murmurs: finite events wrapped around the loop
        ln = rng.uniform(0.3, 0.8)
        m = N(ln)
        tt = T(m)
        f0 = rng.uniform(110.0, 240.0) * S.curve([(0.0, 1.0), (ln * 0.4, 1.06), (ln, 0.9)], m, SR, "exp")
        v = voice(f0, m, ["a", "o", "e"][i % 3], "uh", morph=np.clip(tt / ln, 0, 1), bw=1.6, kmax=20, tilt=1800.0)
        v = nz(v) * S.adsr(m, SR, 0.05, 0.1, 0.8, 0.15, gate=ln - 0.15)
        S.place_circ(voiced, v, N(rng.uniform(0.0, 4.0)), rng.uniform(0.5, 1.0))
    bed = S.fft_filter(S.colored(n, rng, 1.0, SR), SR, S.mag_bp(200.0, 2500.0, 1.5), circular=True)
    y = nz(babble) + 0.3 * nz(voiced) + 0.12 * bed / np.std(bed)
    return S.fft_filter(y, SR, S.mag_lp(3500.0, 1.0), circular=True)
