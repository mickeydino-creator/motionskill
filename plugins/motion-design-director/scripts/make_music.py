#!/usr/bin/env python3
"""Original, royalty-free procedural music bed for motion-design-director videos.

Synthesises a beat-locked track with numpy (no samples, no copyrighted material), so the
picture can be cut to the same BPM grid. Structure, all times in seconds:

  0 .. drop        intro: kick + hats (+ filtered chord pulse), riser into the drop
  drop .. impact   groove: kick, clap on 2 & 4, offbeat hats, bass line, chord stabs;
                   snare roll in the last 2 beats before the impact
  impact .. end    impact hit + sustained pad and soft kick, fading out

  make_music.py --out music.wav --duration 15 --bpm 120 --drop 5 --impact 12 \
                [--key A --minor] [--style energetic|chill] [--seed 1]

Tell the user the track is an original synthesised bed. For real campaigns they should
license or commission music. Pass the WAV to render_video.mjs with --audio.
"""
import argparse
import wave

import numpy as np

SR = 44100
NOTES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def hz(semitone_from_a4):
    return 440.0 * 2 ** (semitone_from_a4 / 12)


def env(n, a=0.005, d=0.2, s=0.0, r=0.05, hold=None):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4))
    dec = np.exp(-(t - a).clip(0) / max(d, 1e-4)) * (1 - s) + s
    e = e * dec
    if hold is not None:
        rel = ((t - hold) / max(r, 1e-4)).clip(0, 1)
        e *= 1 - rel
    return e


def place(buf, sig, t, gain=1.0):
    i = int(t * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


def kick(rng, punch=1.0):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 28) * punch
    ph = 2 * np.pi * np.cumsum(f) / SR
    click = rng.standard_normal(n) * np.exp(-t * 400) * 0.25
    return (np.sin(ph) * np.exp(-t * 7) + click) * 0.95


def hat(rng, open_=False):
    n = int((0.25 if open_ else 0.06) * SR)
    x = rng.standard_normal(n)
    x = np.diff(np.concatenate([[0], x]))  # crude highpass
    return x * np.exp(-np.arange(n) / SR * (12 if open_ else 70)) * 0.22


def clap(rng):
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    x = rng.standard_normal(n)
    x = x - np.convolve(x, np.ones(8) / 8, "same")
    e = sum(np.exp(-((t - o).clip(0)) * 60) * (t >= o) for o in (0, 0.011, 0.023)) / 3 + np.exp(-t * 18) * 0.6
    return x * e * 0.5


def saw(f, n, detune=0.0):
    t = np.arange(n) / SR
    out = np.zeros(n)
    for dt in (-detune, 0, detune):
        out += 2 * ((t * f * (1 + dt)) % 1) - 1
    return out / 3


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):  # one-pole; called on short notes only
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def chord_stab(root, minor, length, cutoff):
    n = int(length * SR)
    third = 3 if minor else 4
    sig = sum(saw(hz(root + iv), n, 0.006) for iv in (0, third, 7, 12)) / 4
    return lowpass(sig, cutoff) * env(n, 0.004, length * 0.6, 0.0) * 0.5


def bass_note(semi, length):
    n = int(length * SR)
    f = hz(semi)
    t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * f * t) * 0.8 + saw(f, n) * 0.25
    return lowpass(sig, 600) * env(n, 0.005, length * 0.8, 0.2, 0.03, hold=length * 0.85) * 0.7


def pad(root, minor, length):
    n = int(length * SR)
    third = 3 if minor else 4
    sig = sum(saw(hz(root + iv), n, 0.01) for iv in (-12, 0, third, 7)) / 4
    t = np.arange(n) / SR
    return lowpass(sig, 1400) * np.minimum(1, t / 0.4) * np.exp(-t / (length * 0.7)) * 0.35


def riser(rng, length):
    n = int(length * SR)
    t = np.arange(n) / SR
    x = rng.standard_normal(n)
    sweep = np.sin(2 * np.pi * np.cumsum(200 + 2400 * (t / length) ** 2) / SR)
    return (x * 0.15 + sweep * 0.1) * (t / length) ** 2


def impact(rng):
    n = int(2.0 * SR)
    t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(30 + 90 * np.exp(-t * 6)) / SR) * np.exp(-t * 1.8)
    crash = rng.standard_normal(n) * np.exp(-t * 2.5) * 0.25
    return boom * 0.9 + crash


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--duration", type=float, default=10)
    ap.add_argument("--bpm", type=float, default=120)
    ap.add_argument("--drop", type=float, default=None, help="seconds; default = 1/3 of duration on a bar")
    ap.add_argument("--impact", type=float, default=None, help="seconds; default = last ~20%% on a bar")
    ap.add_argument("--key", default="A", choices=NOTES.keys())
    ap.add_argument("--minor", action="store_true", default=True)
    ap.add_argument("--major", dest="minor", action="store_false")
    ap.add_argument("--style", choices=["energetic", "chill"], default="energetic")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    beat = 60 / a.bpm
    bar = beat * 4
    dur = a.duration
    drop = a.drop if a.drop is not None else round(dur / 3 / bar) * bar
    imp = a.impact if a.impact is not None else round(dur * 0.8 / bar) * bar
    imp = min(imp, max(beat * 2, dur - beat * 2))   # leave room for the impact tail
    drop = min(drop, max(0.0, imp - beat * 2))
    L = np.zeros(int((dur + 0.05) * SR))
    R = np.zeros_like(L)
    mono = np.zeros_like(L)
    root = NOTES[a.key] - 9 - 12  # A3 region
    prog = [0, -4, 3, -2] if a.minor else [0, 5, -3, 7]   # i-VI-III-VII  /  I-IV-vi-V
    chill = a.style == "chill"

    k_sig, c_sig = kick(rng, 0.7 if chill else 1.0), clap(rng)
    nbeats = int(dur / beat)
    for bi in range(nbeats):
        t = bi * beat
        bar_i = bi // 4
        chord = root + prog[bar_i % 4]
        if t < imp:
            place(mono, k_sig, t, 0.9 if t >= drop else 0.7)
            if t >= drop and bi % 4 in (1, 3):
                place(mono, c_sig, t, 0.8)
            place(L, hat(rng), t + beat / 2, 0.8)
            place(R, hat(rng), t + beat / 2, 0.8)
            if t >= drop:
                place(R, hat(rng), t + beat / 4, 0.35)
                place(L, hat(rng), t + 3 * beat / 4, 0.35)
                place(mono, bass_note(chord - 12, beat * 0.45), t + beat / 2, 0.9)
                if bi % 2 == 0 and not chill:
                    st = chord_stab(chord + 12, a.minor, beat * 0.9, 2600)
                    place(L, st, t, 0.7); place(R, st, t + 0.012, 0.7)
            elif bi % 4 == 0:
                st = chord_stab(chord + 12, a.minor, beat * 1.8, 900)
                place(L, st, t, 0.6); place(R, st, t + 0.01, 0.6)
        else:
            if bi % 2 == 0:
                place(mono, k_sig, t, 0.45)
            place(L, hat(rng), t + beat / 2, 0.35)
    # riser into the drop, snare roll into the impact
    if drop > bar:
        rs = riser(rng, min(bar, drop))
        place(L, rs, drop - len(rs) / SR); place(R, rs, drop - len(rs) / SR)
    roll_start = imp - 2 * beat
    for i in range(16):
        place(mono, c_sig, roll_start + i * beat / 8, 0.25 + 0.5 * i / 16)
    # impact + outro pad
    place(mono, impact(rng), imp, 0.9)
    p = pad(root + prog[0] + 12, a.minor, dur - imp + 0.5)
    place(L, p, imp); place(R, p, imp + 0.015)

    stereo = np.stack([L + mono, R + mono], axis=1)
    # gentle master: soft clip + fade-out tail + normalise
    stereo = np.tanh(stereo * 1.2)
    fade = int(0.8 * SR)
    stereo[-fade:] *= np.linspace(1, 0, fade)[:, None]
    stereo[: int(0.01 * SR)] *= np.linspace(0, 1, int(0.01 * SR))[:, None]
    stereo /= max(1e-6, np.abs(stereo).max()) / 0.89
    pcm = (stereo[: int(dur * SR)] * 32767).astype("<i2")
    with wave.open(a.out, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"wrote {a.out}: {dur}s @ {a.bpm} BPM, drop {drop:.2f}s, impact {imp:.2f}s, key {a.key}{'m' if a.minor else ''}, style {a.style}")
    print(f"beat grid: every {beat:.3f}s (bar {bar:.3f}s) - align picture hits to these")


if __name__ == "__main__":
    main()
