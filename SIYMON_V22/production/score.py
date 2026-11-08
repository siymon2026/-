"""
Original score + sound design for the three SIYMON films.

Everything is synthesised here (no samples, no external audio): a modern
electronic bed at 104 BPM in A minor — sub bass, warm detuned pads, a plucked
arpeggio, soft kick/hats, plus UI-level sound design (whooshes, impacts, a
verification chime, a wallet shimmer). Cue points follow each film's cuts so
transitions land on the beat grid.
"""
from __future__ import annotations

import math
import os
import wave
import numpy as np

SR = 44100
BPM = 104.0
BEAT = 60.0 / BPM
BAR = BEAT * 4
SILENT = False

# A minor palette
NOTE = {"A1": 55.00, "C2": 65.41, "D2": 73.42, "E2": 82.41, "F2": 87.31, "G2": 98.00,
        "A2": 110.0, "C3": 130.81, "D3": 146.83, "E3": 164.81, "F3": 174.61,
        "G3": 196.0, "A3": 220.0, "C4": 261.63, "D4": 293.66, "E4": 329.63,
        "F4": 349.23, "G4": 392.0, "A4": 440.0, "C5": 523.25, "D5": 587.33,
        "E5": 659.25, "A5": 880.0}

# a four-bar minor progression: Am - F - C - G  (i - VI - III - VII)
PROG = [("A2", ["A3", "C4", "E4"]), ("F2", ["F3", "A3", "C4"]),
        ("C3", ["C4", "E4", "G4"]), ("G2", ["G3", "C4", "D4"])]


def _t(dur):
    return np.arange(int(dur * SR), dtype=np.float64) / SR


def env_adsr(n, a=0.01, d=0.1, s=0.7, r=0.2, sus=None):
    a_n = max(1, int(a * SR))
    d_n = max(1, int(d * SR))
    r_n = max(1, int(r * SR))
    sus = s if sus is None else sus
    e = np.ones(n) * sus
    a_n = min(a_n, n)
    e[:a_n] = np.linspace(0, 1, a_n)
    d_n = min(d_n, n - a_n) if n > a_n else 0
    if d_n > 0:
        e[a_n:a_n + d_n] = np.linspace(1, sus, d_n)
    if r_n > 0:
        r_n = min(r_n, n)
        e[n - r_n:] *= np.linspace(1, 0, r_n)
    return e


def exp_env(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def saw(f, dur, detune=0.0, phase=0.0):
    t = _t(dur)
    return 2.0 * ((t * (f + detune) + phase) % 1.0) - 1.0


def sine(f, dur, phase=0.0):
    t = _t(dur)
    return np.sin(2 * np.pi * f * t + phase)


def noise(dur, rng):
    return rng.standard_normal(int(dur * SR)) * 0.5


def lp(x, cutoff):
    """One-pole low-pass; cutoff in Hz (or an array)."""
    if np.isscalar(cutoff):
        a = math.exp(-2 * math.pi * cutoff / SR)
        out = np.empty_like(x)
        acc = 0.0
        for i in range(len(x)):
            acc = (1 - a) * x[i] + a * acc
            out[i] = acc
        return out
    out = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        a = math.exp(-2 * math.pi * max(40.0, cutoff[i]) / SR)
        acc = (1 - a) * x[i] + a * acc
        out[i] = acc
    return out


def hp(x, cutoff):
    return x - lp(x, cutoff)


def sat(x, drive=1.0):
    return np.tanh(x * drive) / np.tanh(drive)


class Mix:
    def __init__(self, dur):
        self.dur = dur
        self.n = int(dur * SR) + SR
        self.buf = np.zeros((self.n, 2), dtype=np.float32)
        self.send = np.zeros((self.n, 2), dtype=np.float32)  # reverb send
        self.rng = np.random.default_rng(20261108)

    def add(self, sig, at, gain=1.0, pan=0.0, rev=0.0):
        i = int(at * SR)
        if i >= self.n:
            return
        n = min(len(sig), self.n - i)
        if n <= 0:
            return
        s = sig[:n] * gain
        r = math.sqrt(0.5 * (1 + pan))
        l = math.sqrt(0.5 * (1 - pan))
        self.buf[i:i + n, 0] += s * r
        self.buf[i:i + n, 1] += s * l
        if rev:
            self.send[i:i + n, 0] += s * r * rev
            self.send[i:i + n, 1] += s * l * rev


# --------------------------------------------------------------------------
# instruments
# --------------------------------------------------------------------------
def pad_chord(root, notes, dur, bright=1.0):
    n = int(dur * SR)
    out = np.zeros(n)
    for k, nm in enumerate(notes):
        f = NOTE[nm]
        for det in (-0.12, 0.0, 0.13):
            v = saw(f, dur, detune=det, phase=self_phase(k, det))
            out[:len(v)] += v * (0.30 if det == 0 else 0.18)
    env = env_adsr(len(out), a=min(0.5, dur * 0.25), d=0.3, s=0.85, r=min(0.8, dur * 0.4))
    body = lp(out * env / len(notes), 900 * bright)
    air = hp(out * env / len(notes), 1800) * 0.12
    return body + air


def self_phase(k, det):
    return (k * 0.37 + det * 3.1) % 1.0


def bass_note(f, dur, drive=1.4):
    t = _t(dur)
    v = np.sin(2 * np.pi * f * t) * 0.62 + np.sin(2 * np.pi * f * 2 * t) * 0.55
    v += np.sin(2 * np.pi * f * 3 * t) * 0.20
    v += np.sign(np.sin(2 * np.pi * f * t)) * 0.10
    env = env_adsr(len(v), a=0.006, d=0.12, s=0.55, r=0.06)
    return sat(v * env, drive) * 0.5


def pluck(f, dur, bright=2.0):
    t = _t(dur)
    mod = np.sin(2 * np.pi * f * 2.01 * t) * bright * np.exp(-t * 9)
    v = np.sin(2 * np.pi * f * t + mod)
    v += np.sin(2 * np.pi * f * 2 * t) * 0.3 * np.exp(-t * 14)
    return v * exp_env(len(v), 0.14) * 0.35


def kick(dur=0.42, f0=120, f1=44, click=0.5):
    t = _t(dur)
    f = f1 + (f0 - f1) * np.exp(-t * 26)
    ph = 2 * np.pi * np.cumsum(f) / SR
    v = np.sin(ph) * np.exp(-t * 5.2)
    v += noise(dur, np.random.default_rng(3)) * click * np.exp(-t * 220)
    return sat(v, 1.6) * 0.55


def hat(dur=0.06, amp=0.18):
    n = noise(dur, np.random.default_rng(int(dur * 1e5) % 9999))
    v = lp(hp(n, 5200), 11000) * exp_env(len(n), 0.018)
    return v * amp * 0.62


def snare(dur=0.2):
    n = noise(dur, np.random.default_rng(11))
    v = hp(n, 1400) * exp_env(len(n), 0.07) * 0.30
    v += np.sin(2 * np.pi * 190 * _t(dur)) * exp_env(int(dur * SR), 0.05) * 0.16
    return v


def whoosh(dur=0.6, up=True):
    n = noise(dur, np.random.default_rng(5))
    t = np.arange(len(n)) / len(n)
    cut = np.linspace(400, 7000, len(n)) if up else np.linspace(7000, 400, len(n))
    v = lp(n, cut) * np.sin(np.pi * t) ** 1.6
    return v * 0.4


def impact(dur=0.9, amp=0.5):
    t = _t(dur)
    v = np.sin(2 * np.pi * (58 * np.exp(-t * 1.5) + 30) * t) * np.exp(-t * 4.0)
    n = noise(dur, np.random.default_rng(7)) * np.exp(-t * 9) * 0.25
    return sat(v + lp(n, 900), 1.3) * amp


def chime(f=NOTE["E5"], dur=0.9):
    """Two-note verification chime (perfect fifth up)."""
    a = pluck(f, dur, 1.6) * 1.2
    t = _t(dur)
    b = np.sin(2 * np.pi * f * 1.5 * t) * np.exp(-t * 6) * 0.28
    c = np.sin(2 * np.pi * f * 2 * t) * np.exp(-t * 9) * 0.12
    return a + b + c


def shimmer(dur=1.6, base=NOTE["A4"]):
    out = np.zeros(int(dur * SR) + 1)
    for k, mult in enumerate((1, 1.25, 1.5, 2.0, 2.5, 3.0)):
        t = _t(dur)
        out[:len(t)] += np.sin(2 * np.pi * base * mult * t + k) * np.exp(-t * (1.6 + k * 0.4)) * 0.16
    return out


def riser(dur=2.0):
    n = int(dur * SR)
    x = noise(dur, np.random.default_rng(9))
    cut = np.linspace(300, 9000, n) ** 1.0
    v = lp(x, cut) * np.linspace(0, 1, n) ** 2.2
    t = np.arange(n) / SR
    v += np.sin(2 * np.pi * (110 * (1 + t * 2.5)) * t) * 0.05 * np.linspace(0, 1, n)
    return v * 0.42


# --------------------------------------------------------------------------
# arrangement
# --------------------------------------------------------------------------
def reverb(send):
    """Cheap stereo reverb: a few decaying taps + low-pass."""
    out = np.zeros_like(send)
    taps = [(0.031, 0.62), (0.047, 0.50), (0.073, 0.42), (0.101, 0.33), (0.137, 0.26),
            (0.181, 0.20), (0.233, 0.15), (0.301, 0.11)]
    mono = send.mean(axis=1)
    for dly, g in taps:
        d = int(dly * SR)
        out[d:, 0] += mono[:-d] * g * 0.6
        out[d:, 1] += mono[:-d] * g * 0.55
    out[:, 0] = lp(out[:, 0], 4200)
    out[:, 1] = lp(out[:, 1], 4200)
    return out


def build(key, film, out_path):
    dur = film.duration + 0.6
    mx = Mix(dur)
    cuts = [s["start"] for s in film.scenes] + [dur]

    # ---- pad bed
    bar = 0.0
    i = 0
    while bar < dur:
        root, notes = PROG[i % len(PROG)]
        bright = 1.0
        seg = min(BAR * 1.05, dur - bar)
        if seg <= 0.1:
            break
        mx.add(pad_chord(root, notes, seg, bright), bar, gain=0.30, rev=0.35)
        # sustained root an octave up for sparkle in the second half
        if bar > dur * 0.45:
            mx.add(pluck(NOTE[notes[0]], seg * 0.9, 0.8), bar, gain=0.10, pan=0.35, rev=0.5)
        bar += BAR
        i += 1

    # ---- drums enter after the intro, drop in the last beat of each film
    start_beat = 8 * BEAT
    t = start_beat
    b = 0
    while t < dur - 1.2:
        bar_pos = b % 4
        mx.add(kick(), t, gain=0.55)
        if bar_pos in (1, 3):
            mx.add(snare(), t, gain=0.35, rev=0.25)
        # off-beat hats
        mx.add(hat(), t + BEAT * 0.5, gain=0.55, pan=0.22)
        mx.add(hat(0.04, 0.10), t + BEAT * 0.75, gain=0.40, pan=-0.18)
        t += BEAT
        b += 1

    # ---- bass line
    t = 8 * BEAT
    step = 0
    while t < dur - 1.0:
        root, notes = PROG[(step // 8) % len(PROG)]
        f = NOTE[root]
        pat = [0, 0, 7, 0, 12, 0, 7, 3]
        semis = pat[step % 8]
        mx.add(bass_note(f * (2 ** (semis / 12)), BEAT * 0.92), t, gain=0.34)
        t += BEAT * 0.5
        step += 1

    # ---- arpeggio sparkle
    t = 4 * BAR
    step = 0
    while t < dur - 1.0:
        root, notes = PROG[(step // 8) % len(PROG)]
        nm = notes[step % len(notes)]
        f = NOTE[nm] * (2 if step % 8 >= 4 else 1)
        mx.add(pluck(f, 0.5, 1.2), t, gain=0.12, pan=(-0.35 if step % 2 else 0.35), rev=0.45)
        t += BEAT * 0.5
        step += 1

    # ---- sound design on cuts
    for k, c in enumerate(cuts[1:-1]):
        name = film.scenes[k]["name"]
        if k > 0:
            mx.add(whoosh(0.7, up=(k % 2 == 0)), max(0.0, c - 0.35), gain=0.30, pan=0.15 if k % 2 else -0.15,
                   rev=0.3)
        if "brand" in name or name == "end" or "hex" in name or "address" in name:
            mx.add(impact(0.9, 0.45), c, gain=0.6, rev=0.4)

    # verification moments
    for sc in film.scenes:
        nm = sc["name"]
        if nm in ("pickup", "delivery", "handoff"):
            mx.add(chime(NOTE["E5"]), sc["start"] + sc["dur"] * 0.58, gain=0.30, rev=0.5)
            mx.add(chime(NOTE["A5"], 0.6), sc["start"] + sc["dur"] * 0.72, gain=0.18, rev=0.5)
        if nm == "earnings":
            mx.add(shimmer(1.8), sc["start"] + 0.4, gain=0.34, rev=0.6)
            mx.add(chime(NOTE["D5"], 1.1), sc["start"] + 0.55, gain=0.22, rev=0.5)
        if nm == "prepare" or nm == "packing":
            mx.add(impact(0.5, 0.22), sc["start"] + 0.1, gain=0.5, rev=0.2)
        if nm in ("offer", "new-order"):
            mx.add(pluck(NOTE["A4"], 0.5, 1.4), sc["start"], gain=0.20, rev=0.4)
            mx.add(pluck(NOTE["E5"], 0.5, 1.4), sc["start"] + 0.12, gain=0.16, rev=0.4)

    # risers into the brand close and the middle
    mx.add(riser(2.2), max(0.0, dur - 4.4), gain=0.5, rev=0.3)
    mx.add(riser(1.8), film.scenes[3]["start"] - 1.6, gain=0.28, rev=0.3)

    # ---- finalise
    wet = reverb(mx.send)
    mix = mx.buf + wet * 0.85
    mix = mix[:int(dur * SR)]
    # tame the very top and remove sub-rumble phones cannot play
    for ch in range(2):
        mix[:, ch] = hp(mix[:, ch], 36.0)
        mix[:, ch] = mix[:, ch] * 0.72 + lp(mix[:, ch], 9500) * 0.34
    mix = np.tanh(mix * 1.25) * 0.92
    # gentle fade in / out so nothing clicks
    fi = int(0.12 * SR)
    mix[:fi] *= np.linspace(0, 1, fi)[:, None]
    fo = int(0.9 * SR)
    mix[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 1.5
    peak = np.max(np.abs(mix)) or 1.0
    mix = mix / peak * 0.89
    data = (mix * 32767).astype(np.int16)
    with wave.open(out_path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    return out_path
