# Wildbound audio forge

Procedural synthesizer that generates **every** sound effect and music cue for
Wildbound from code: no samples, no recorded audio, no borrowed melodies.
It's pure Python + numpy (PIL is optional, for spectrogram previews), and builds are
deterministic: every recipe draws from an RNG seeded by its own name, so
re-running the build reproduces the same files bit for bit.

```bash
python3 tools/audio_forge/build.py                 # render everything, then write report.txt
python3 tools/audio_forge/build.py --only hit_heavy village_theme
python3 tools/audio_forge/build.py --sfx           # or --music
python3 tools/audio_forge/build.py --previews      # + spectrogram PNGs in tools/audio_forge/previews/ (gitignored)
python3 tools/audio_forge/build.py --report-only   # re-analyse what is on disk
```

A full build takes about 1 minute on 4 cores. The exit code is non-zero if any
check in the report fails.

## Output

| | folder | format | levels |
|---|---|---|---|
| SFX (89) | `assets/audio/sfx/` | 44.1 kHz mono 16-bit PCM | peak-normalised per category: impacts -1 dBFS, most hits/spells -2..-5, creatures -3..-9, UI -8..-13, footsteps -9, ambient loops -7..-14 |
| Music (6) | `assets/audio/music/` | 32 kHz mono 16-bit PCM | peaks ≈ -3..-5 dBFS, integrated loudness capped at -20 LUFS so music sits under the SFX |

Non-looping SFX are DC-free, trimmed of silence and have 5 ms / 10 ms
raised-cosine fades (first and last samples are exactly 0). Hits whose snap
has to survive (the dash family) use a 1 ms fade-in instead.

**Loops** (`fire_crackle_loop`, `focus_loop`, `stun_chime`, `crowd_ambience_loop`
and the five music loops) are rendered *circularly*: note tails, echoes and
reverb that run past the end are wrapped onto the start. The file therefore
plays seamlessly end -> start, and a loop has no fades. Each loop carries a RIFF `smpl`
chunk with one forward loop over the whole file.

### Godot import notes

* Loops: Godot's WAV importer default *Loop Mode = Detect From WAV* reads the
  `smpl` chunk. To be explicit, set *Loop Mode = Forward*, *Loop Begin = 0*, and
  *Loop End = -1* (whole file) in the Import dock for the loop files.
* Every other file should stay non-looping.
* `victory_fanfare.wav` (music folder) and the `*_jingle.wav` SFX are one-shots.
* `dialogue_blip_1/2/3` are meant to be picked round-robin or at random every
  2-3 characters. `step_<surface>_1..3` are random variations for each surface.
* `focus_start` -> `focus_loop` (while focusing) -> `focus_full`, and
  `heat_ring_charge` -> `heat_ring_burst`, are designed to chain.
* Drag-to-dash: `dash_aim_tick` (pitch it up one step per aimed cell) ->
  `dash_windup` -> `dash_launch` -> `ram_impact` / `ram_whiff` / `dash_clash`
  / `dash_blocked` -> `dash_land`. `dash_launch_1..3` and `dash_land_1..3` are
  round-robin variants (`Audio.sfx` picks one at random), with per-variant
  peaks trimmed so they are equally loud. The launches are low-passed at
  12.5 kHz so they can be pitched up for long dashes.

## Files

| file | what it is |
|---|---|
| `synth.py` | DSP toolkit: oscillators (polyBLEP saw/pulse with PWM, triangle, additive with per-harmonic swept lowpass / formants), coloured noise, envelopes, RBJ biquads, time-varying SVF, FFT filters, modal resonators, FM, Karplus-Strong, convolution reverb with synthetic IRs, circular delay/chorus, mastering and WAV I/O |
| `instruments.py` | instrument voices shared by music and jingles: harp, pluck, lead, chip, bass, pad, choir, glock, bell, celesta, twinkle, brass, soft_sine, plus drums |
| `sfx.py` | the 89 SFX recipes, registered with `@sfx(name, peak_dbfs, category, loop=...)` |
| `music.py` | step sequencer, melody notation, voice leading, and the six cues |
| `analyze.py` | levels, approximate BS.1770 loudness, DC/NaN/clip/edge checks, loop-seam metrics, spectrogram PNGs |
| `build.py` | entry point (parallel, deterministic) |
| `report.txt` | the last build's analysis (duration, peak, RMS, LUFS, DC, clipping, loop seams) |

## Sound design notes

Every SFX is layered from a small vocabulary:

* **Transient**: 2-6 ms band-passed noise click.
* **Body**: a sine with an exponential pitch drop (kicks, punches, booms).
* **Texture**: band-limited, shaped noise.
* **Resonance**: damped modes for wood, stone, glass and bells.
* **Clouds**: Poisson grain clouds for fire crackle and debris.
* **Voices**: formant-filtered harmonic sources for creatures, crowds and the dialogue blips.

Hits use soft saturation on the body with the transient added afterwards, so
they stay crisp.

## Music

| cue | key / tempo | length | structure |
|---|---|---|---|
| `title_theme` | D major, 84 BPM, 4/4 | 45.7 s (16 bars) | A (D Bm G A) / A' rising to C#6 (D F#m G A) / B climbing to D6 (Bm G D A G A D D-A/C#). Pulse lead with delayed vibrato and dotted-8th echo, KS harp arpeggios, voice-led pad, triangle bass; soft drums and timpani in the second half. |
| `village_theme` | G major, 100 BPM, light swing | 48.0 s (20 bars) | Plucked melody, walking bass, ukulele chops on 2 and 4, brushes and shaker; glockenspiel countermelody from bar 9. |
| `forest_theme` | E dorian, 72 BPM | 40.0 s (12 bars) | Em9 - A/E - Em9 - Cmaj7/E - D/E - Bm7/E over an E drone; airy pad, sparse FM bell motif with echo, harp glimmers, twinkles, wind. |
| `battle_theme` | A minor, 150 BPM | 51.2 s (32 bars) | Main theme (A, A'), driving B section with brass stabs, 4-bar bridge in C major (half-time), then a return. 8th-note bass, pluck ostinato, fills. |
| `shrine_theme` | D minor/modal, 60 BPM, 3/4 | 36.0 s (12 bars) | Formant choir (Dm - Bbmaj7 - G/D (dorian) - Dm - Eb/D (phrygian) - Asus4 - Am), distant bells, D pedal drone, a slow heartbeat each bar. |
| `victory_fanfare` | C major, 120 BPM | ≈6.3 s, one-shot | Brass fanfare, harp glissando, timpani roll into the final chord, glock sparkle. |

Melodies are written in `music.py` as `pitch:beats` tokens with `|` bar lines.
A bar that doesn't add up to the time signature raises an error. Stems are
balanced "by numbers": each track declares a target loudness (`level`, in LUFS)
and is scaled to it before the reverb and delay buses.

## Extending

* **New SFX**: add a function to `sfx.py` decorated with
  `@sfx("name", peak_dbfs, "category")` that returns a float array at 44.1 kHz.
  Use the `rng` you're given for all randomness.
* **New cue**: write a builder returning a `Song` in `music.py` and add it to
  `MUSIC`.
* Run with `--previews` and look at the PNGs. Check `report.txt` for levels and
  failed checks.

## Limitations

Everything is mono. Since nothing could be auditioned while building this, all
tuning was done from measurements: loudness, spectra and spectrograms, per-bar
chroma checks of the harmony, and onset timing.
