"""KAIRA SOL — "Neón en la Piel"
Genera la voz cantada (espeak-ng + afinación PSOLA con Praat) y el beat
(reggaetón / dembow sintetizado), y los mezcla.

Requisitos: espeak-ng, ffmpeg, pip install numpy scipy praat-parselmouth
Uso: python3 crear_cancion.py  ->  kaira_sol_neon_en_la_piel.{wav,mp3}, beat_instrumental.wav, voz_acapella.wav
"""
import os, subprocess, tempfile
import numpy as np
import parselmouth as pm
from parselmouth.praat import call
from scipy.signal import butter, sosfilt, fftconvolve
from scipy.io import wavfile

SR = 44100
BPM = 92
BEAT = 60 / BPM
BAR = 4 * BEAT
E8 = BEAT / 2  # corchea
OUT = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(7)

def hz(m): return 440 * 2 ** ((m - 69) / 12)

# ---------------------------------------------------------------- BEAT ---
# Progresión en La menor: Am - F - C - G (raíces MIDI para el 808)
PROG = [(45, [57, 60, 64]), (41, [53, 57, 60]), (48, [55, 60, 64]), (43, [55, 59, 62])]

def env(n, a=0.002, d=0.2):
    t = np.arange(n) / SR
    e = np.minimum(1, t / a) * np.exp(-t / d)
    return e

def kick(n=int(0.35 * SR)):
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 30)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.tanh(2.2 * np.sin(ph) * np.exp(-t * 7))

def snare(n=int(0.22 * SR)):
    t = np.arange(n) / SR
    nz = sosfilt(butter(2, [1500, 9000], 'band', fs=SR, output='sos'), rng.standard_normal(n))
    return 0.7 * nz * np.exp(-t * 22) + 0.4 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30)

def hat(n=int(0.05 * SR)):
    nz = sosfilt(butter(4, 7000, 'high', fs=SR, output='sos'), rng.standard_normal(n))
    return nz * np.exp(-np.arange(n) / SR * 90)

def bass808(m, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    f = hz(m) * (1 + 0.5 * np.exp(-t * 40))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR)
    return np.tanh(1.8 * s) * np.minimum(1, t / 0.005) * np.exp(-t * 1.2) * np.minimum(1, (dur - t) / 0.03)

def pad(notes, dur):
    n = int(dur * SR); t = np.arange(n) / SR; s = np.zeros(n)
    for m in notes:
        for det in (-0.12, 0, 0.12):
            f = hz(m + det)
            s += 2 * ((t * f) % 1) - 1  # sierra
    s = sosfilt(butter(2, 1400, 'low', fs=SR, output='sos'), s) / 9
    return s * np.minimum(1, t / 0.25) * np.minimum(1, (dur - t) / 0.3)

def pluck(m, dur=0.3):
    n = int(dur * SR); t = np.arange(n) / SR
    s = np.sign(np.sin(2 * np.pi * hz(m) * t)) * 0.5 + np.sin(2 * np.pi * hz(m) * 2 * t) * 0.3
    return sosfilt(butter(2, 3000, 'low', fs=SR, output='sos'), s) * np.exp(-t * 9)

def place(buf, x, t, g=1.0):
    i = int(t * SR); j = min(len(buf), i + len(x))
    if i < len(buf): buf[i:j] += g * x[:j - i]

# Estructura (compases): intro 4 | coro 8 | verso 8 | pre 4 | coro 8 | outro 4
SECTIONS = [('intro', 4), ('coro', 8), ('verso', 8), ('pre', 4), ('coro', 8), ('outro', 4)]
TOTAL_BARS = sum(b for _, b in SECTIONS)
LEN = int((TOTAL_BARS * BAR + 3) * SR)

drums = np.zeros(LEN); bass = np.zeros(LEN); keys = np.zeros(LEN); lead = np.zeros(LEN)
K, S, H = kick(), snare(), hat()
ARP = [0, 2, 1, 2, 0, 2, 1, 2]
bar = 0
for name, nb in SECTIONS:
    for b in range(nb):
        t0 = (bar + b) * BAR
        root, chord = PROG[(bar + b) % 4]
        place(keys, pad(chord, BAR), t0, 0.5 if name != 'intro' else 0.7)
        full = name in ('coro', 'verso', 'outro') or (name == 'pre' and b < 3)
        if name == 'intro' or full:
            for k, step in enumerate(ARP):  # arpegio pluck
                if name != 'verso' or k % 2 == 0:
                    place(lead, pluck(chord[step] + 12), t0 + k * E8, 0.18)
        if not full:
            if name == 'pre':  # redoble antes del coro
                for k in range(16): place(drums, S, t0 + k * BEAT / 4, 0.3 + 0.04 * k)
            continue
        # Dembow: bombo en cada negra, caja en 3/16 y 2/4 de cada medio compás
        for q in range(4):
            place(drums, K, t0 + q * BEAT, 0.9)
        for half in (0, 2):
            place(drums, S, t0 + (half + 0.75) * BEAT, 0.55)
            place(drums, S, t0 + (half + 1.5) * BEAT, 0.55)
        for k in range(8):
            place(drums, H, t0 + k * E8 + (0.02 if k % 2 else 0), 0.25 if k % 2 else 0.4)
        place(bass, bass808(root, BAR * 0.62), t0, 0.75)
        place(bass, bass808(root + (7 if b % 2 else 12), BAR * 0.3), t0 + 2.5 * BEAT, 0.6)
    bar += nb

# ---------------------------------------------------------------- VOZ ---
# Cada línea = 2 compases (16 corcheas). (sílaba, nota MIDI, corcheas); sílaba None = silencio
def L(*items): return list(items)
CORO = [
    L(('Ba',69,1),('jo',69,1),('la',69,1),('luz',72,2),('de',71,1),('ne',69,1),('ón',67,4),(None,0,5)),
    L(('tu',67,1),('nom',69,1),('bre',69,1),('sue',72,2),('na en',71,1),('mi',69,1),('voz',64,4),(None,0,5)),
    L(('bai',69,1),('la',69,1),('con',72,1),('mi',72,1),('go',74,2),('ha',72,1),('sta el',71,1),('sol',69,4),(None,0,4)),
    L(('ne',67,1),('ón',69,1),('en',69,1),('la',71,1),('piel',72,4),('e',71,1),('o',69,1),('e',67,2),(None,0,4)),
]
VERSO = [
    L(('Lle',64,1),('go',64,1),('del',64,1),('ba',67,1),('rrio',64,1),('con',64,1),('un',62,1),('sue',64,1),('ño',64,2),(None,0,6)),
    L(('ca',64,1),('mi',64,1),('nan',64,1),('do',67,1),('so',69,1),('la',67,1),('bajo el',64,1),('cie',62,1),('lo',64,2),(None,0,6)),
    L(('la',64,1),('ciu',64,1),('dad',64,1),('me',67,1),('lla',69,1),('ma',67,1),('con',64,1),('su',62,1),('rit',64,1),('mo',60,2),(None,0,5)),
    L(('y yo',64,1),('can',67,1),('to',69,1),('pa',69,1),('ra',67,1),('no',64,1),('per',62,1),('der',60,1),('me',57,3),(None,0,5)),
]
PRE = [
    L(('Si',69,2),('me',71,2),('mi',72,2),('ras',74,2),('a',72,1),('sí',71,1),(None,0,6)),
    L(('to',72,2),('do',74,2),('se en',76,2),('cien',74,2),('de',76,4),(None,0,4)),
]
LYRICS = {'coro': CORO, 'verso': VERSO, 'pre': PRE}

tmp = tempfile.mkdtemp()
cache = {}

def sing(syl, midi, dur):
    key = syl
    if key not in cache:
        p = os.path.join(tmp, f'{len(cache)}.wav')
        subprocess.run(['espeak-ng', '-v', 'es-419+f3', '-s', '130', '-w', p, syl], check=True)
        s = pm.Sound(p)
        x = s.values[0]
        idx = np.where(np.abs(x) > 0.02 * np.abs(x).max())[0]
        s = pm.Sound(x[idx[0]:idx[-1] + 1], s.sampling_frequency)
        cache[key] = s
    s = cache[key]
    target = max(dur * 0.92, 0.08)
    try:
        o = call(s, 'Change gender', 75, 600, 1.08, hz(midi), 0, target / s.duration)
    except Exception:
        o = s
    o = o.resample(SR)
    y = o.values[0]
    fade = int(0.012 * SR)
    y[:fade] *= np.linspace(0, 1, fade); y[-fade:] *= np.linspace(1, 0, fade)
    return y / (np.abs(y).max() + 1e-9)

voc = np.zeros(LEN)
bar = 0
for name, nb in SECTIONS:
    lines = LYRICS.get(name)
    if lines:
        for li in range(nb // 2):
            t = (bar + li * 2) * BAR
            for syl, m, n8 in lines[li % len(lines)]:
                d = n8 * E8
                if syl: place(voc, sing(syl, m, d), t, 0.8)
                t += d
    bar += nb

# Doble de voz en el coro (octava baja suave) + filtro de presencia
voc = sosfilt(butter(2, 120, 'high', fs=SR, output='sos'), voc)

# ---------------------------------------------------------------- MEZCLA ---
def reverb(x, sec=1.8, wet=0.25):
    n = int(sec * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 3.5)
    ir = sosfilt(butter(2, 5000, 'low', fs=SR, output='sos'), ir)
    w = fftconvolve(x, ir)[:len(x)]
    return x + wet * w / (np.abs(w).max() + 1e-9) * np.abs(x).max()

def delay(x, t=BEAT * 0.75, fb=0.3, g=0.25):
    y = x.copy(); d = int(t * SR)
    for k in range(1, 4):
        y[d * k:] += x[:-d * k] * g * fb ** (k - 1)
    return y

# Sidechain: el pad y el bajo "respiran" con el bombo
side = np.ones(LEN)
for b in range(TOTAL_BARS * 4):
    i = int(b * BEAT * SR); n = int(0.25 * SR)
    side[i:i + n] = np.minimum(side[i:i + n], 0.4 + 0.6 * np.linspace(0, 1, n))

beat_mix = drums * 0.9 + bass * 0.8 + reverb(keys, 2.5, 0.4) * side * 0.5 + reverb(lead, 1.2, 0.3) * 0.6
vox_mix = reverb(delay(voc), 1.6, 0.3)

def master(x):
    x = x / (np.abs(x).max() + 1e-9)
    x = np.tanh(1.4 * x) / np.tanh(1.4)
    return (x * 0.95).astype(np.float32)

def stereo(x, width=0.0):
    d = int(0.012 * SR)
    r = np.concatenate([np.zeros(d), x[:-d]])
    return np.stack([x, (1 - width) * x + width * r], 1)

song = stereo(beat_mix, 0.3) + stereo(vox_mix * 1.1, 0.1)
song = master(song)
wavfile.write(os.path.join(OUT, 'kaira_sol_neon_en_la_piel.wav'), SR, song)
wavfile.write(os.path.join(OUT, 'beat_instrumental.wav'), SR, master(stereo(beat_mix, 0.3)))
wavfile.write(os.path.join(OUT, 'voz_acapella.wav'), SR, master(vox_mix))
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', os.path.join(OUT, 'kaira_sol_neon_en_la_piel.wav'),
                '-b:a', '192k', os.path.join(OUT, 'kaira_sol_neon_en_la_piel.mp3')], check=True)
print('Listo:', round(LEN / SR, 1), 's')
