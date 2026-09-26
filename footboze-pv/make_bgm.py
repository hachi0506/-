"""FOOTBOZE FUTSAL リール用 BGM をゼロから合成する（著作権フリー・自作音源）。

120 BPM / A minor / 30 秒。映像側 (render_pv.py) のシーン切替と同じ拍に
キック・インパクト・ライザーが来るように組んである。

    python3 make_bgm.py  ->  output/bgm.wav (48kHz / 16bit / stereo)
"""
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000
BPM = 120
BEAT = 60 / BPM          # 0.5 s
BAR = BEAT * 4           # 2.0 s
DURATION = 30.0
N = int(SR * DURATION)

rng = np.random.default_rng(1998)  # 創設年をシードに


# ---------------------------------------------------------------- utilities
def t_axis(sec):
    return np.arange(int(SR * sec)) / SR


def lp(x, hz, order=2):
    return sosfilt(butter(order, hz, "low", fs=SR, output="sos"), x)


def hp(x, hz, order=2):
    return sosfilt(butter(order, hz, "high", fs=SR, output="sos"), x)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def place(buf, sig, at, gain=1.0):
    i = int(at * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


def note_hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def saw(freq, sec, detune_cents=(0,)):
    t = t_axis(sec)
    out = np.zeros_like(t)
    for c in detune_cents:
        f = freq * 2 ** (c / 1200)
        ph = rng.random()
        out += 2 * ((t * f + ph) % 1.0) - 1
    return out / len(detune_cents)


# ---------------------------------------------------------------- drum voices
def kick(sec=0.45):
    t = t_axis(sec)
    f = 45 + 110 * np.exp(-t * 28)
    phase = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(phase) * np.exp(-t * 7.5)
    click = hp(rng.standard_normal(len(t)), 3000) * np.exp(-t * 400) * 0.35
    return np.tanh((body + click) * 1.6)


def clap(sec=0.35):
    t = t_axis(sec)
    noise = bp(rng.standard_normal(len(t)), 900, 5000)
    env = np.zeros_like(t)
    for k, d in enumerate((0.0, 0.011, 0.022)):
        env += (t >= d) * np.exp(-(t - d).clip(0) * (220 if k < 2 else 26))
    return noise * env * 0.6


def hat(sec=0.06, open_=False):
    t = t_axis(0.35 if open_ else sec)
    noise = hp(rng.standard_normal(len(t)), 7500, 4)
    return noise * np.exp(-t * (11 if open_ else 90)) * 0.35


def snare(sec=0.25):
    t = t_axis(sec)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * 0.5
    noise = bp(rng.standard_normal(len(t)), 1500, 8000) * np.exp(-t * 22)
    return (tone + noise) * 0.55


def impact(sec=2.2):
    t = t_axis(sec)
    f = 32 + 70 * np.exp(-t * 9)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.4)
    crash = hp(rng.standard_normal(len(t)), 2500) * np.exp(-t * 3.2) * 0.35
    return np.tanh((boom * 1.4 + crash) * 1.3)


def riser(sec):
    t = t_axis(sec)
    x = t / sec
    noise = rng.standard_normal(len(t))
    # 帯域を時間とともに上げる：2 本のフィルタをクロスフェード
    low = bp(noise, 300, 1500)
    high = bp(noise, 2500, 12000)
    sweep = np.sin(2 * np.pi * np.cumsum(200 + 1400 * x ** 2) / SR) * 0.25
    return ((1 - x) * low + x * high) * x ** 2 * 0.6 + sweep * x ** 1.5


def reverse_swell(sec=0.9):
    t = t_axis(sec)
    noise = hp(rng.standard_normal(len(t)), 1800)
    return noise * (t / sec) ** 3 * 0.45


# ---------------------------------------------------------------- tonal voices
# Am - F - C - G （1 小節ずつ）
PROG = [(57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62)]
ROOTS = [45, 41, 48, 43]  # A2 F2 C3 G2 （ベースは 1 oct 下で鳴らす）


def bass_note(midi, sec):
    s = saw(note_hz(midi - 12), sec, (0, 7))
    s = lp(s, 380)
    t = t_axis(sec)
    env = np.minimum(1, t / 0.005) * np.exp(-t * 1.2)
    sub = np.sin(2 * np.pi * note_hz(midi - 12) * t) * 0.6
    return (s + sub) * env


def pluck_chord(chord, sec=0.45, bright=2400):
    out = np.zeros(int(SR * sec))
    for m in chord:
        out += saw(note_hz(m + 12), sec, (-9, 0, 9))
    t = t_axis(sec)
    out = lp(out, bright) * np.exp(-t * 7) * np.minimum(1, t / 0.003)
    return out / len(chord)


def pad_chord(chord, sec):
    out = np.zeros(int(SR * sec))
    for m in chord:
        out += saw(note_hz(m), sec, (-12, -4, 4, 12))
    t = t_axis(sec)
    env = np.minimum(1, t / 0.4) * np.minimum(1, (sec - t) / 0.4).clip(0)
    return lp(out, 1400) * env / len(chord)


def lead_note(midi, sec):
    t = t_axis(sec)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t)
    f = note_hz(midi + 12) * vib
    sq = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.5
    sq += np.sin(2 * np.pi * np.cumsum(f * 2) / SR) * 0.3
    env = np.minimum(1, t / 0.01) * np.exp(-t * 3.5)
    return lp(sq, 3200) * env


# ---------------------------------------------------------------- arrangement
drums = np.zeros(N)
bass = np.zeros(N)
music = np.zeros(N)
fx = np.zeros(N)
sidechain = np.ones(N)


def duck(at, depth=0.75, rel=0.22):
    i = int(at * SR)
    t = t_axis(rel)
    env = 1 - depth * (1 - t / rel) ** 2
    j = min(N, i + len(env))
    sidechain[i:j] = np.minimum(sidechain[i:j], env[: j - i])


K, CL, HC, HO, SN, IMP = kick(), clap(), hat(), hat(open_=True), snare(), impact()

# ---- 0-3s HOOK : 言葉ごとに重いヒット
for at in (0.0, 1.0, 2.0):
    place(fx, IMP, at, 0.55)
    place(drums, K, at, 1.0)
    duck(at, 0.6, 0.4)
place(fx, reverse_swell(0.5), 0.5, 0.8)
place(fx, reverse_swell(0.5), 1.5, 0.8)
place(fx, riser(1.0), 2.0, 0.9)
drone = pad_chord((45, 52, 57), 3.0)
place(music, drone, 0.0, 0.35)

# ---- 3-30s グルーヴ
def groove(start, end, hats16=False, clap_on=True, kick_on=True):
    beat = start
    while beat < end - 1e-6:
        idx = round((beat - start) / BEAT)
        if kick_on:
            place(drums, K, beat, 0.95)
            duck(beat)
        if clap_on and idx % 2 == 1:
            place(drums, CL, beat, 0.8)
        place(drums, HO, beat + BEAT / 2, 0.35)
        if hats16:
            for q in (0.25, 0.75):
                place(drums, HC, beat + BEAT * q, 0.28)
        else:
            place(drums, HC, beat, 0.22)
        beat += BEAT


def harmony(start, end, pluck=True, lead=False):
    bar_start = start
    while bar_start < end - 1e-6:
        k = int(round(bar_start / BAR)) % 4
        chord, root = PROG[k], ROOTS[k]
        # ベースは 8 分でオフビート強調
        for e in range(8):
            at = bar_start + e * BEAT / 2
            if at >= end:
                break
            place(bass, bass_note(root, BEAT / 2 * 0.95), at, 0.55 if e % 2 else 0.35)
        if pluck:
            for e in (1, 3, 4, 6):
                at = bar_start + e * BEAT / 2
                if at < end:
                    place(music, pluck_chord(chord), at, 0.30)
        if lead:
            melody = {0: [69, 72, 76, 74], 1: [72, 69, 65, 69], 2: [67, 72, 76, 79], 3: [74, 71, 67, 71]}[k]
            for q, m in enumerate(melody):
                at = bar_start + q * BEAT
                if at < end:
                    place(music, lead_note(m - 12, BEAT * 0.9), at, 0.16)
        bar_start += BAR


# 3-6 ロゴ：ドロップ
place(fx, IMP, 3.0, 0.7)
groove(3.0, 6.0)
harmony(3.0, 6.0)
# 6-14 コンセプト
place(fx, IMP, 6.0, 0.35)
groove(6.0, 14.0)
harmony(6.0, 14.0, lead=True)
place(fx, reverse_swell(0.5), 9.5, 0.6)
place(fx, reverse_swell(0.5), 13.5, 0.6)
# 14-22 3つのチカラ / 実績：16 分ハットで密度 UP
place(fx, IMP, 14.0, 0.45)
groove(14.0, 22.0, hats16=True)
harmony(14.0, 22.0, lead=True)
for at in (14.5, 15.5, 16.5, 18.0, 19.0, 20.0):
    place(fx, snare(), at, 0.35)
place(fx, IMP, 18.0, 0.4)
# 22-25 カテゴリー → ビルド
place(fx, IMP, 22.0, 0.45)
groove(22.0, 24.0, hats16=True)
harmony(22.0, 25.0, pluck=True)
roll_t = 24.0
step = BEAT / 2
while roll_t < 25.0 - 1e-6:
    place(drums, SN, roll_t, 0.25 + 0.5 * (roll_t - 24.0))
    roll_t += step
    if roll_t >= 24.5:
        step = BEAT / 4
place(fx, riser(1.5), 23.5, 1.0)
# 25-27 「目指すは、日本一。」 ブレイク
place(fx, IMP, 25.0, 0.9)
place(drums, K, 25.0, 1.0)
duck(25.0, 0.8, 0.6)
place(music, pad_chord((57, 60, 64, 69), 2.0), 25.0, 0.45)
place(bass, bass_note(45, 1.9), 25.0, 0.6)
place(fx, reverse_swell(0.5), 26.5, 0.8)
# 27-30 エンドカード：ラストのグルーヴ → フィニッシュ
place(fx, IMP, 27.0, 0.8)
groove(27.0, 29.0, hats16=True)
harmony(27.0, 29.0, lead=True)
place(fx, IMP, 29.0, 0.8)
place(drums, K, 29.0, 1.0)
place(music, pad_chord((45, 57, 60, 64), 1.0), 29.0, 0.4)


# ---------------------------------------------------------------- mix
def simple_reverb(x, sec=1.2, wet=0.18):
    t = t_axis(sec)
    ir = rng.standard_normal(len(t)) * np.exp(-t * 4.5)
    ir = lp(ir, 5000)
    ir /= np.sqrt(np.sum(ir ** 2))
    return x + fftconvolve(x, ir)[: len(x)] * wet


music_rev = simple_reverb(music, wet=0.25)
fx_rev = simple_reverb(fx, sec=1.8, wet=0.22)

mono = drums * 0.9 + bass * sidechain * 0.9 + music_rev * sidechain + fx_rev * 0.85

# ステレオ化：音楽成分を少しだけ左右に広げる（Haas）
d = int(0.012 * SR)
wide = np.concatenate([np.zeros(d), music_rev[:-d]]) * sidechain * 0.35
left = mono + wide
right = mono - wide * 0.6

stereo = np.stack([left, right], axis=1)
stereo = np.tanh(stereo * 1.15)                 # ソフトリミッター
stereo /= np.max(np.abs(stereo)) / 0.8          # 約 -2 dBFS（AAC 変換時のクリップ防止）

fade = int(0.35 * SR)                           # 終端のクリック防止
stereo[-fade:] *= np.linspace(1, 0, fade)[:, None]

out = Path(__file__).parent / "output" / "bgm.wav"
out.parent.mkdir(exist_ok=True)
wavfile.write(out, SR, (stereo * 32767).astype(np.int16))
print(f"wrote {out}  ({DURATION:.1f}s, {SR} Hz)")
