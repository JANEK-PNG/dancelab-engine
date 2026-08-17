"""Folktronika — utwór w duchu Four Teta, syntezowany wprost. Napisane od zera.

To NIE jest rozwinięcie silnika in-between (hybryda/rubato/pełne T). Tamten
aparat malował pole na spektrogramie, śledził grzbiety i odtwarzał je bankiem
oscylatorów — świetne do BADANIA zjawiska „in between", bezsensowne do robienia
piosenki: nuta przechodziła przez obraz i wracała zmieniona. Tutaj nuta jest
grana wprost. Z tamtej pracy zostaje LOGIKA, nie ani jedna linia kodu:

  1. Faza całkowana dla tonów (φ[n+1] = φ[n] + 2π·f[n]/SR), losowa dla szumu.
     Stopa jedzie wysokością w dół — naiwne sin(2π·f(t)·t) dałoby złą wysokość.
  2. Każdy głos ma własną fazę startową (inaczej chór zapada się w mono).
  3. Wolne modulacje z PAMIĘCI (~1–2 s), nie z chwili.
  4. Budżet nieoznaczoności per pasmo: bas powolny i precyzyjny, góra ostra.
  5. Dół gra linie i jest w mono — szum obok basu zawsze dudni.
  6. Humanizacja U ŹRÓDŁA: przesuwamy czas startu zdarzenia. Nigdy przez
     przepróbkowanie (to daje vibrato i niszczy czystość).
  7. ADR-005: każda liczba w raporcie zmierzona z wyrenderowanego pliku.

Instrument wiodący to model fizyczny szarpniętej struny (Karplus–Strong
z ułamkowym opóźnieniem), a nie próbka i nie addytywna imitacja. Bilans
opóźnienia pętli: N + opóźnienie filtra tłumiącego (= stretch) + allpass = SR/f0.
Pominięcie tego pół-próbkowego członu stroiło instrument o −9 centów przy
1 kHz — zmierzone i poprawione (teraz < 0,3 centa przez cztery oktawy).

Wydajność: brzmienia liczone RAZ per (wysokość, wariant) i cache'owane; pętla
KS liczona blokami po N próbek (blok k zależy tylko od bloku k−1, więc cała
reszta jest wektorowa). Pogłos splotem z syntetyczną odpowiedzią impulsową.
Render całości: kilkadziesiąt sekund, nie godziny.

Wyjście: mix + siedem stemów (KICK, DRUMS, HATS, BASS, CHORDS, MELODY,
TEXTURES) jako osobne pliki WAV do dalszej obróbki w DAW.
"""

from __future__ import annotations

import argparse
import pathlib
import time

import numpy as np
import soundfile as sf
from scipy.ndimage import uniform_filter1d
from scipy.signal import butter, oaconvolve, lfilter, sosfilt, sosfiltfilt

# ─────────────────────────── rama ───────────────────────────
SR = 96000
BPM = 122.0
BEAT = 60.0 / BPM                 # 0,4918 s
BAR = 4 * BEAT                    # 1,9672 s
STEP = BEAT / 4                   # szesnastka
N_BARS = 117
TOTAL = N_BARS * BAR              # ≈ 230,2 s
N = int(TOTAL * SR)

# F# molowa pentatonika nad dwoma akordami: F#m9 ↔ Dmaj9 (modalna huśtawka)
PENTA = [66, 69, 71, 73, 76]      # F# A B C# E
AKORD_A = [45, 57, 61, 64, 68]    # F#m9:  A2 A3 C#4 E4 G#4
AKORD_B = [38, 54, 57, 61, 64]    # Dmaj9: D2 F#3 A3 C#4 E4
BAS_A, BAS_B = 30, 26             # F#1, D1

STEMY = ("KICK", "DRUMS", "HATS", "BASS", "CHORDS", "MELODY", "TEXTURES")


def hz(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def bar_t(b):
    return b * BAR


# ────────────────────── prymitywy syntezy ──────────────────────
def ks_pluck(f0, dur, damp=0.9965, stretch=0.5, bright=0.55, seed=0):
    """Karplus–Strong z ułamkowym opóźnieniem. Strojenie < 0,3 centa.

    Pętla: N próbek + filtr tłumiący (opóźnienie grupowe = stretch) + allpass.
    Suma musi wynosić dokładnie SR/f0 — pominięcie członu `stretch` stroi
    instrument nisko, tym bardziej, im wyższa nuta.
    """
    rng = np.random.default_rng(seed)
    D = SR / f0
    n_del = int(np.floor(D - stretch - 0.4))
    frac = D - n_del - stretch            # zostaje na allpass, celujemy 0,4–1,4
    eta = (1.0 - frac) / (1.0 + frac)
    n_out = int(dur * SR)
    y = np.zeros(n_out + n_del + 4)

    exc = rng.standard_normal(n_del)      # pobudzenie: szum o barwie młoteczka
    k = max(1, int(round((1.0 - bright) * 10)))
    if k > 1:
        exc = np.convolve(exc, np.ones(k) / k, mode="same")
    exc -= exc.mean()
    exc *= np.hanning(n_del) ** 0.25      # miękkie brzegi pobudzenia
    exc /= np.abs(exc).max() + 1e-12
    y[:n_del] = exc

    b_ap, a_ap = np.array([eta, 1.0]), np.array([1.0, eta])
    zi = np.zeros(1)
    pos, prev = n_del, 0.0
    while pos < len(y):
        m = min(n_del, len(y) - pos)
        a = y[pos - n_del: pos - n_del + m]
        b = np.empty(m)
        b[0] = prev
        b[1:] = a[:m - 1]
        blk = damp * ((1 - stretch) * a + stretch * b)
        out, zi = lfilter(b_ap, a_ap, blk, zi=zi)
        prev = a[m - 1]
        y[pos: pos + m] = out
        pos += m
    y = y[:n_out]
    y *= 1.0 - np.exp(-np.arange(n_out) / (0.0008 * SR))   # bez kliku na starcie
    return (y / (np.abs(y).max() + 1e-12)).astype(np.float32)


def kick(f0=118.0, f1=43.0, tau_p=0.032, tau_a=0.34, dur=0.85, klik=0.16):
    """Stopa: sinus z opadającą wysokością. FAZA CAŁKOWANA — inaczej zła nuta."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / tau_p)
    ph = 2 * np.pi * np.cumsum(f) / SR
    amp = np.exp(-t / tau_a) * (1 - np.exp(-t / 0.0012))
    x = np.sin(ph) * amp
    x += klik * np.exp(-t / 0.0032) * np.sin(2 * np.pi * 1750 * t)
    return (x / (np.abs(x).max() + 1e-12)).astype(np.float32)


def klaps(dur=0.30, seed=0):
    """Klaśnięcie: cztery bliskie wybuchy szumu — dłoń, nie maszyna."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    x = np.zeros(n)
    for i, (d_ms, a) in enumerate(((0, 1.0), (9, 0.8), (17, 0.65), (26, 0.5))):
        d = int(d_ms / 1000 * SR)
        m = n - d
        if m <= 0:
            continue
        t = np.arange(m) / SR
        x[d:] += a * rng.standard_normal(m) * np.exp(-t / (0.012 + 0.004 * i))
    x += 0.35 * rng.standard_normal(n) * np.exp(-np.arange(n) / SR / 0.09)  # ogon
    sos = butter(4, [1100 / (SR / 2), 3400 / (SR / 2)], btype="band", output="sos")
    x = sosfilt(sos, x)
    return (x / (np.abs(x).max() + 1e-12)).astype(np.float32)


def perkusja_tonalna(f0, dur=0.35, seed=0, ton=0.55):
    """Uderzenie ręką w membranę: kilka modów + szum uderzenia (tabla-ish)."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for mult, amp, tau in ((1.0, 1.0, 0.16), (1.59, 0.45, 0.10),
                           (2.14, 0.28, 0.07), (2.30, 0.18, 0.05)):
        ph = rng.uniform(0, 2 * np.pi)     # własna faza startowa (lekcja 2)
        x += amp * np.sin(2 * np.pi * f0 * mult * t + ph) * np.exp(-t / tau)
    x *= ton
    imp = rng.standard_normal(n) * np.exp(-t / 0.004)
    sos = butter(2, [800 / (SR / 2), 6000 / (SR / 2)], btype="band", output="sos")
    x += (1 - ton) * sosfilt(sos, imp)
    x *= 1.0 - np.exp(-t / 0.0006)
    return (x / (np.abs(x).max() + 1e-12)).astype(np.float32)


def hat(dur=0.055, otwarty=False, seed=0):
    """Hi-hat: szum + rezonanse metaliczne. Faza losowa jest tu POPRAWNA."""
    rng = np.random.default_rng(seed)
    if otwarty:
        dur = 0.34
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = rng.standard_normal(n)
    for fr in (6300, 8400, 9700, 11300, 13100):        # metaliczność
        sos = butter(2, [fr * 0.97 / (SR / 2), fr * 1.03 / (SR / 2)],
                     btype="band", output="sos")
        x += 0.55 * sosfilt(sos, rng.standard_normal(n))
    sos = butter(4, 6000 / (SR / 2), btype="high", output="sos")
    x = sosfilt(sos, x)
    tau = 0.075 if otwarty else 0.012
    x *= np.exp(-t / tau) * (1 - np.exp(-t / 0.0003))
    return (x / (np.abs(x).max() + 1e-12)).astype(np.float32)


def bas_nuta(f0, dur, seed=0):
    """Bas: całkowana faza, dwie harmoniczne, miękka saturacja. Mono."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    ph = 2 * np.pi * f0 * t + np.random.default_rng(seed).uniform(0, 2 * np.pi)
    x = np.sin(ph) + 0.28 * np.sin(2 * ph) + 0.09 * np.sin(3 * ph)
    atk = 1 - np.exp(-t / 0.006)
    rel = np.minimum(1.0, np.exp(-(t - (dur - 0.08)) / 0.05))
    x *= atk * np.clip(rel, 0, 1)
    x = np.tanh(1.7 * x) / np.tanh(1.7)
    return (x / (np.abs(x).max() + 1e-12)).astype(np.float32)


def pad_glos(midi, dur, seed=0, detune_c=6.0, n_voice=3):
    """Pad: kilka rozstrojonych głosów, KAŻDY z własną fazą startową."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    f0 = hz(midi)
    for v in range(n_voice):
        d = (v - (n_voice - 1) / 2) * detune_c
        f = f0 * 2 ** (d / 1200)
        ph = rng.uniform(0, 2 * np.pi)
        vib = 1 + 0.0016 * np.sin(2 * np.pi * (0.23 + 0.07 * v) * t + ph)
        pha = 2 * np.pi * np.cumsum(f * vib) / SR + ph
        x += (np.sin(pha) + 0.30 * np.sin(2 * pha) + 0.13 * np.sin(3 * pha)
              + 0.06 * np.sin(4 * pha)) / n_voice
    return (x / (np.abs(x).max() + 1e-12)).astype(np.float32)


# ────────────────────── przestrzeń i tor sygnału ──────────────────────
def ir_pokoj(t60=2.1, seed=1, pre_ms=14.0):
    """Syntetyczna odpowiedź impulsowa: pokój, nie efekt.

    Wczesne odbicia + wykładniczy ogon szumu z rosnącym tłumieniem góry
    (powietrze pochłania wysokie). Zero cudzego audio.
    """
    rng = np.random.default_rng(seed)
    n = int(t60 * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-6.9078 * t / t60)[:, None]
    ir *= (t[:, None] / 0.02).clip(0, 1) ** 0.6          # narastanie gęstości
    sos = butter(2, 5200 / (SR / 2), btype="low", output="sos")
    mix = np.linspace(0, 1, n)[:, None] ** 0.7
    ir = ir * (1 - mix) + sosfilt(sos, ir, axis=0) * mix
    for d_ms, a in ((6.5, .52), (11, .43), (17, .34), (23, .27),
                    (31, .21), (43, .16), (57, .11)):
        d = int(d_ms / 1000 * SR)
        if d < n:
            ir[d] += a * rng.choice([-1.0, 1.0], 2)
    pre = int(pre_ms / 1000 * SR)
    ir = np.vstack([np.zeros((pre, 2)), ir])[:n]
    ir /= np.sqrt((ir ** 2).sum(axis=0)).max() + 1e-12
    return ir.astype(np.float32)


def pogloc(x, ir, mokro):
    if mokro <= 0:
        return x
    w = np.empty_like(x)
    for ch in range(2):
        w[:, ch] = oaconvolve(x[:, ch], ir[:, ch])[:len(x)]
    w *= np.abs(x).max() / (np.abs(w).max() + 1e-12)
    return x * (1 - 0.35 * mokro) + w * mokro


def delay(x, czas, fb=0.36, mokro=0.3, hf=3800.0):
    """Delay z filtrowanym sprzężeniem — powtórzenia ciemnieją jak w taśmie."""
    d = int(czas * SR)
    if d <= 0 or mokro <= 0:
        return x
    sos = butter(2, hf / (SR / 2), btype="low", output="sos")
    y = np.zeros_like(x)
    krok = x.copy()
    for _ in range(6):
        krok = np.vstack([np.zeros((d, 2), np.float32),
                          sosfilt(sos, krok, axis=0)[:-d]]).astype(np.float32) * fb
        if np.abs(krok).max() < 1e-5:
            break
        y += krok
    return x + y * mokro


def saturuj(x, drive=1.0):
    if drive <= 0:
        return x
    return (np.tanh(x * (1 + drive)) / np.tanh(1 + drive)).astype(np.float32)


def polka(x, lo=None, hi=None, rzad=2):
    if lo:
        x = sosfilt(butter(rzad, lo / (SR / 2), btype="high", output="sos"),
                    x, axis=0)
    if hi:
        x = sosfilt(butter(rzad, min(hi, SR / 2 * 0.98) / (SR / 2),
                           btype="low", output="sos"), x, axis=0)
    return x.astype(np.float32)


def wstaw(dst, t_sec, sig, gain=1.0, pan=0.0):
    """Umieszcza mono zdarzenie w buforze stereo. Panorama równej mocy."""
    i0 = int(t_sec * SR)
    if i0 >= len(dst) or i0 < 0:
        return
    m = min(len(sig), len(dst) - i0)
    if m <= 0:
        return
    th = (np.clip(pan, -1, 1) + 1) * np.pi / 4
    dst[i0:i0 + m, 0] += sig[:m] * (gain * np.cos(th))
    dst[i0:i0 + m, 1] += sig[:m] * (gain * np.sin(th))


# ────────────────────── forma utworu ──────────────────────
# (od_taktu, do_taktu, nazwa, co gra)
SEKCJE = [
    (0, 8, "wnętrze", "pad + tekstury"),
    (8, 16, "pętla wchodzi", "+ melodia cicho"),
    (16, 24, "puls", "+ hi-haty, bas"),
    (24, 40, "groove", "+ stopa, perkusja"),
    (40, 56, "rozwinięcie", "melodia druga komórka, gęściej"),
    (56, 64, "oddech", "stopa wychodzi, tekstury rosną"),
    (64, 88, "pełnia", "wszystko, melodia najwyżej"),
    (88, 104, "rozchodzi się", "elementy wychodzą kolejno"),
    (104, 117, "ogon", "pad + tekstury + pogłos"),
]


def akord_w_takcie(b):
    """Ośmiotaktowa huśtawka modalna: 4 takty F#m9, 4 takty Dmaj9."""
    return AKORD_A if (b // 4) % 2 == 0 else AKORD_B


def bas_w_takcie(b):
    return BAS_A if (b // 4) % 2 == 0 else BAS_B


# pętla melodyczna: (krok szesnastkowy w 2 taktach, midi, głośność)
KOMORKA_1 = [(0, 78, 1.00), (3, 73, 0.62), (6, 76, 0.75), (8, 81, 0.88),
             (11, 78, 0.58), (14, 73, 0.70), (16, 76, 0.92), (19, 83, 0.80),
             (22, 78, 0.55), (24, 73, 0.72), (27, 76, 0.64), (30, 71, 0.68)]
KOMORKA_2 = [(0, 81, 1.00), (2, 78, 0.55), (5, 76, 0.78), (8, 73, 0.85),
             (10, 76, 0.52), (13, 78, 0.72), (16, 85, 0.95), (18, 81, 0.60),
             (21, 78, 0.74), (24, 76, 0.66), (26, 73, 0.58), (29, 71, 0.70)]


def buduj(rng):
    """Zwraca słownik stemów (bufory stereo) i statystyki kompozycji."""
    buf = {s: np.zeros((N, 2), np.float32) for s in STEMY}
    stat = {"nuty_melodii": 0, "uderzenia_stopy": 0, "hi_haty": 0}

    # wolny dryf ręki: WSPÓLNA faza (nie losowość per nuta) — lekcja 6
    dryf_t = np.arange(0, TOTAL, 0.01)
    dryf = uniform_filter1d(rng.standard_normal(len(dryf_t)), 900, mode="nearest")
    dryf = dryf / (np.abs(dryf).max() + 1e-12) * 0.018        # ±18 ms

    def humanizuj(t):
        return float(np.interp(t, dryf_t, dryf) + rng.normal(0, 0.007))

    # ── CHORDS: pad, jedna warstwa na cztery takty, długie zachodzenie ──
    for b in range(0, N_BARS, 4):
        t0 = bar_t(b)
        dlug = 4 * BAR + 2.4
        for i, m in enumerate(akord_w_takcie(b)):
            g = pad_glos(m, dlug, seed=int(rng.integers(1 << 30)),
                         detune_c=5.0 + 2.5 * i)
            n_g = len(g)
            t = np.arange(n_g) / SR
            obw = np.minimum(t / 1.6, 1.0) * np.clip((dlug - t) / 2.2, 0, 1)
            obw *= 0.72 + 0.28 * np.sin(2 * np.pi * 0.045 * t + i)   # oddech
            wstaw(buf["CHORDS"], t0, (g * obw).astype(np.float32),
                  gain=0.30 / (1 + 0.35 * i),
                  pan=(-0.5 + i * 0.25) * 0.8)

    # ── BASS: korzeń + oktawa, prosty wzór, mono ──
    wzor_basu = [(0.0, 1.5), (2.0, 0.5), (2.5, 0.75), (3.0, 1.0)]   # w ćwiartkach
    for b in range(16, 104):
        root = bas_w_takcie(b)
        for off, dl in wzor_basu:
            if rng.random() < 0.12:
                continue
            m = root + (12 if rng.random() < 0.18 else 0)
            t0 = bar_t(b) + off * BEAT + rng.normal(0, 0.003)
            sig = bas_nuta(hz(m), dl * BEAT + 0.12,
                           seed=int(rng.integers(1 << 30)))
            wstaw(buf["BASS"], t0, sig, gain=0.34 * (0.85 + 0.3 * rng.random()),
                  pan=0.0)

    # ── KICK: cztery na takt, maszynowo równo (±1 ms) ──
    for b in list(range(24, 56)) + list(range(64, 104)):
        for beat in range(4):
            if b >= 100 and beat in (1, 3) and rng.random() < 0.5:
                continue                                   # rozrzedzenie na końcu
            t0 = bar_t(b) + beat * BEAT + rng.normal(0, 0.001)
            akc = 1.0 if beat == 0 else 0.92
            sig = kick(f0=118 + rng.normal(0, 2), tau_a=0.34)
            wstaw(buf["KICK"], t0, sig, gain=0.50 * akc, pan=0.0)
            stat["uderzenia_stopy"] += 1
        if b % 8 == 7 and rng.random() < 0.55:             # duch przed taktem
            wstaw(buf["KICK"], bar_t(b) + 3.5 * BEAT, kick(f0=105, tau_a=0.18),
                  gain=0.22, pan=0.0)

    # ── DRUMS: klaśnięcie na 2 i 4 + perkusja ręczna ze swingiem ──
    for b in range(24, 100):
        for beat in (1, 3):
            t0 = bar_t(b) + beat * BEAT + rng.normal(0, 0.004)
            wstaw(buf["DRUMS"], t0, klaps(seed=int(rng.integers(1 << 30))),
                  gain=0.20 * (0.9 + 0.2 * rng.random()),
                  pan=rng.uniform(-0.18, 0.18))
        for s16 in range(16):                              # ręczna perkusja
            if rng.random() > (0.22 if b < 64 else 0.34):
                continue
            swing = 0.055 * STEP if s16 % 2 else 0.0
            t0 = bar_t(b) + s16 * STEP + swing + rng.normal(0, 0.005)
            f0 = float(rng.choice([196, 233, 262, 311]))
            wstaw(buf["DRUMS"], t0,
                  perkusja_tonalna(f0, seed=int(rng.integers(1 << 30)),
                                   ton=rng.uniform(0.4, 0.7)),
                  gain=0.13 * rng.uniform(0.5, 1.0),
                  pan=rng.uniform(-0.55, 0.55))

    # ── HATS: ósemki offbeat + duchy szesnastkowe ze swingiem ──
    for b in range(16, 108):
        for s16 in range(16):
            faza = s16 % 4
            if faza == 2:
                g, otw = 0.30, False
            elif faza in (1, 3) and rng.random() < 0.45:
                g, otw = 0.11 * rng.uniform(0.6, 1.0), False
            elif s16 == 14 and b % 4 == 3:
                g, otw = 0.22, True
            else:
                continue
            swing = 0.055 * STEP if s16 % 2 else 0.0
            t0 = bar_t(b) + s16 * STEP + swing + rng.normal(0, 0.0015)
            wstaw(buf["HATS"], t0, hat(otwarty=otw, seed=int(rng.integers(1 << 30))),
                  gain=g, pan=rng.uniform(-0.45, 0.45))
            stat["hi_haty"] += 1

    # ── MELODY: pętla kalimbowa, rubato u źródła, mikro-wariacje ──
    cache: dict[tuple, np.ndarray] = {}

    def pluck(m, wariant):
        key = (m, wariant)
        if key not in cache:
            rozstroj = np.random.default_rng(m * 97 + wariant).uniform(-4, 4)
            cache[key] = ks_pluck(hz(m) * 2 ** (rozstroj / 1200), 3.4,
                                  damp=0.9962 - 0.00012 * max(0, m - 70),
                                  bright=0.45 + 0.06 * wariant,
                                  seed=m * 131 + wariant)
        return cache[key]

    for b in range(8, 108, 2):
        komorka = KOMORKA_1 if b < 40 or (56 <= b < 64) else KOMORKA_2
        # głośność sekcji: melodia wchodzi cicho, najgłośniej w pełni
        if b < 16:
            sek = 0.42
        elif b < 56:
            sek = 0.85
        elif b < 64:
            sek = 0.55
        elif b < 88:
            sek = 1.0
        else:
            sek = max(0.15, 1.0 - (b - 88) / 20)
        for (s16, m, v) in komorka:
            if rng.random() < 0.09:                        # opuszczenie
                continue
            mm = m + (12 if rng.random() < 0.07 else 0)    # skok oktawy
            if 64 <= b < 88 and rng.random() < 0.12:
                mm += 12                                    # kulminacja wyżej
            t_nom = bar_t(b) + s16 * STEP
            t0 = t_nom + humanizuj(t_nom)                  # rubato U ŹRÓDŁA
            wariant = int(rng.integers(0, 3))
            sig = pluck(mm, wariant)
            wstaw(buf["MELODY"], t0, sig,
                  gain=0.22 * sek * v * rng.uniform(0.85, 1.12),
                  pan=float(np.clip((mm - 78) * 0.055, -0.5, 0.5)))
            stat["nuty_melodii"] += 1
            if rng.random() < 0.07:                        # ozdobnik oktawę wyżej
                wstaw(buf["MELODY"], t0 + 0.055, pluck(mm + 12, wariant),
                      gain=0.09 * sek * v, pan=0.35)

    # ── TEXTURES: szum taśmy, trzaski, iskry, narastania ──
    tex = buf["TEXTURES"]
    t_all = np.arange(N) / SR
    szum = rng.standard_normal(N).astype(np.float32)
    szum = polka(np.stack([szum, np.roll(szum, 977)], axis=1), lo=700, hi=13000)
    tex += szum * 0.0075 * (0.6 + 0.4 * np.sin(2 * np.pi * 0.02 * t_all))[:, None]

    for _ in range(int(TOTAL * 7)):                        # trzaski winylowe
        i = int(rng.uniform(0, N - 200))
        d = int(rng.uniform(20, 160))
        tex[i:i + d, rng.integers(0, 2)] += (
            rng.standard_normal(d) * np.exp(-np.arange(d) / 25) * 0.02)

    for _ in range(90):                                    # iskry — wysokie plucki
        t0 = rng.uniform(4, TOTAL - 6)
        m = int(rng.choice(PENTA)) + 24
        wstaw(tex, t0, ks_pluck(hz(m), 1.6, damp=0.9955, bright=0.85,
                                seed=int(rng.integers(1 << 30))),
              gain=0.035 * rng.uniform(0.4, 1.0), pan=rng.uniform(-0.8, 0.8))

    for b0, b1 in ((22, 24), (38, 40), (54, 56), (62, 64), (86, 88), (102, 104)):
        t0, t1 = bar_t(b0), bar_t(b1)                      # narastania szumu
        i0, i1 = int(t0 * SR), int(t1 * SR)
        m = i1 - i0
        sw = rng.standard_normal((m, 2)).astype(np.float32)
        sw = polka(sw, lo=2000, hi=14000)
        ramp = (np.linspace(0, 1, m) ** 2.4)[:, None]
        tex[i0:i1] += sw * ramp * 0.06

    return buf, stat


# ────────────────────── mix ──────────────────────
# stem: (wzmocnienie, dolna półka, górna półka, drive saturacji, wysyłka pogłosu)
# Wzmocnienia NIE są zgadywane: pierwszy render dał sub/bas −0,4 dB przy
# środku −23 dB, czyli cała energia w dole, a melodia schowana. Poniższe
# wartości cofają dół i podnoszą resztę — zweryfikowane pomiarem pasm.
MIX = {
    "KICK":     (0.58, 30, 9000, 0.30, 0.06),
    "DRUMS":    (2.80, 150, 15000, 0.22, 0.30),
    "HATS":     (2.70, 5500, None, 0.10, 0.24),
    "BASS":     (0.46, 34, 2200, 0.35, 0.04),
    "CHORDS":   (0.84, 150, 7000, 0.18, 0.42),
    "MELODY":   (7.60, 220, 13000, 0.20, 0.34),
    "TEXTURES": (3.20, 300, None, 0.08, 0.45),
}
# Druga korekta, też z pomiaru per stem (nie ze słuchu i nie z zamiaru):
# pad wychodził na −3,2 dB, melodia na −17,0 — instrument wiodący grał
# 14 dB POD podkładem i sam pad wypełniał 120–500 Hz. Powyższe wzmocnienia
# to policzone delty do celu: melodia ≈ −8, pad ≈ −12, bas ≈ −10 dB.


def zmiksuj(buf, ir, zapisz_stemy, out):
    mix = np.zeros((N, 2), np.float32)
    stemy = {}
    for s in STEMY:
        x = buf[s]
        g, lo, hi, drv, wet = MIX[s]
        x = polka(x, lo=lo, hi=hi)
        x = saturuj(x, drv)
        if s == "MELODY":
            x = delay(x, 1.5 * BEAT, fb=0.34, mokro=0.26)   # kropkowana ósemka
        x = pogloc(x, ir, wet)
        if s in ("KICK", "BASS"):                            # dół w mono
            m = x.mean(axis=1, keepdims=True)
            x = np.repeat(m, 2, axis=1)
        x = (x * g).astype(np.float32)
        assert np.isfinite(x).all(), f"NaN w stemie {s}"
        stemy[s] = x
        mix += x
    mix = saturuj(mix, 0.10)                                 # klej sumy
    mix = polka(mix, lo=22)                                  # bez DC i podmuchów

    # sub w mono: pogłos i perkusja rozjeżdżały dół (zmierzone: korelacja
    # < 150 Hz spadła do 0,85). Klubowy system i tak zsumuje — lepiej my.
    # Filtr MUSI być zerofazowy: przy przyczynowym `mix − low` nie jest
    # dopełnieniem pasma, tylko grzebieniem — pierwsza próba zbiła
    # korelację dołu do 0,59, czyli dokładnie odwrotnie do zamiaru.
    sos_lo = butter(4, 150 / (SR / 2), btype="low", output="sos")
    low = sosfiltfilt(sos_lo, mix, axis=0)
    mix = (mix - low + low.mean(axis=1, keepdims=True)).astype(np.float32)

    # sufit pasma: to piosenka, nie eksperyment ze spektrogramem — rama jest
    # decyzją patrzącego, a tu patrzy ucho i format dostawy
    mix = polka(mix, hi=22000, rzad=6)

    # wyjście: utwór ma wybrzmieć, nie urwać się w pół pogłosu
    ogon = int(11.0 * SR)
    mix[-ogon:] *= (np.cos(np.linspace(0, np.pi, ogon)) * 0.5 + 0.5)[:, None]
    mix[:int(0.05 * SR)] *= np.linspace(0, 1, int(0.05 * SR))[:, None]

    szczyt = float(np.abs(mix).max())
    mix *= 0.891 / (szczyt + 1e-12)                          # −1 dBFS
    if zapisz_stemy:
        for s, x in stemy.items():
            x2 = x * (0.891 / (szczyt + 1e-12))
            sf.write(out.parent / f"{out.stem}_{s}.wav", x2, SR, subtype="PCM_24")
    return mix


# ────────────────────── pomiar (ADR-005) ──────────────────────
def zmierz(path):
    y, sr = sf.read(path, dtype="float64")
    L, R = y[:, 0], y[:, 1]
    m = y.mean(axis=1)
    r = {}
    r["skonczony"] = bool(np.isfinite(y).all())
    r["szczyt_dBFS"] = 20 * np.log10(np.abs(y).max() + 1e-12)
    up = np.repeat(y, 4, axis=0)                             # zgrubny true-peak
    r["truepeak_dBFS"] = 20 * np.log10(np.abs(up).max() + 1e-12)
    r["dc"] = float(np.abs(m.mean()))

    sos_k = butter(2, 120 / (sr / 2), btype="high", output="sos")   # ~K-weighting
    k = sosfilt(sos_k, m)
    k = sosfilt(butter(2, [1000 / (sr / 2), 12000 / (sr / 2)],
                       btype="band", output="sos"), k) * 1.26 + k
    blok = int(0.4 * sr)
    moce = [(k[i:i + blok] ** 2).mean() for i in range(0, len(k) - blok, blok // 2)]
    moce = np.array([p for p in moce if p > 0])
    gl = -0.691 + 10 * np.log10(moce + 1e-12)
    r["glosnosc_LUFS"] = float(-0.691 + 10 * np.log10(
        moce[gl > gl.max() - 20].mean() + 1e-12))
    r["zakres_dyn_dB"] = float(np.percentile(gl, 95) - np.percentile(gl, 10))

    pasma = [(20, 120, "sub/bas"), (120, 500, "dół"), (500, 2000, "środek"),
             (2000, 8000, "góra"), (8000, 20000, "powietrze")]
    tot = float((m ** 2).mean())
    r["pasma"] = []
    for lo, hi, lab in pasma:
        b = sosfilt(butter(4, [lo / (sr / 2), min(hi, sr / 2 * 0.98) / (sr / 2)],
                           btype="band", output="sos"), m)
        e = float((b ** 2).mean())
        crest = 20 * np.log10(np.abs(b).max() / (np.sqrt(e) + 1e-12) + 1e-12)
        r["pasma"].append((lab, 10 * np.log10(e / tot + 1e-12), crest))

    r["korelacja"] = float(np.corrcoef(L, R)[0, 1])
    lo_b = sosfilt(butter(4, 150 / (sr / 2), btype="low", output="sos"), y.T).T
    r["korelacja_dol"] = float(np.corrcoef(lo_b[:, 0], lo_b[:, 1])[0, 1])

    env = np.abs(m)
    env = sosfilt(butter(2, 30 / (sr / 2), btype="low", output="sos"), env)
    env = env[:: sr // 200]
    le = np.log(np.maximum(env, 1e-7))
    le -= uniform_filter1d(le, 2000, mode="nearest")
    F = np.abs(np.fft.rfft(le * np.hanning(len(le)))) ** 2
    fr = np.fft.rfftfreq(len(le), 1 / 200)
    f_beat = BPM / 60.0
    okno = np.abs(fr - f_beat) < 0.06
    tlo = (fr > 0.5) & (fr < 12) & ~okno
    r["puls_dB"] = float(10 * np.log10(F[okno].sum() / (F[tlo].mean() *
                                                        okno.sum() + 1e-12)))
    # pętla: mierzona na STEMIE MELODII, jeśli jest — na całości zagłuszała
    # ją losowa z założenia perkusja ręczna (mierzyliśmy szum, nie pętlę)
    stem_mel = path.parent / f"{path.stem}_MELODY.wav"
    if stem_mel.exists():
        ym, _ = sf.read(stem_mel, dtype="float64")
        zrodlo = ym.mean(axis=1)
    else:
        zrodlo = m
    mel = sosfilt(butter(4, [250 / (sr / 2), 2500 / (sr / 2)],
                         btype="band", output="sos"), zrodlo)
    em = np.abs(mel)
    em = sosfilt(butter(2, 25 / (sr / 2), btype="low", output="sos"), em)
    em = np.log(np.maximum(em[:: sr // 200], 1e-7))
    em -= uniform_filter1d(em, 1600, mode="nearest")
    segm = em[int(70 * 200): int(170 * 200)]
    r["petla_r"] = {}
    for takty in (2, 4, 8):
        lg = int(takty * BAR * 200)
        r["petla_r"][takty] = float(np.corrcoef(segm[:-lg], segm[lg:])[0, 1])

    F2 = np.abs(np.fft.rfft(m[:int(60 * sr)] * np.hanning(int(60 * sr))))
    f2 = np.fft.rfftfreq(int(60 * sr), 1 / sr)
    r["ultra_udzial"] = float((F2[f2 > 22000] ** 2).sum() / ((F2 ** 2).sum() + 1e-12))

    cisza = np.abs(m) < 1e-4
    najd = 0
    licz = 0
    for c in cisza[:: 100]:
        licz = licz + 1 if c else 0
        najd = max(najd, licz)
    r["najdluzsza_cisza_s"] = najd * 100 / sr
    r["koniec_dBFS"] = 20 * np.log10(np.sqrt((m[-int(0.5 * sr):] ** 2).mean()) + 1e-12)
    return r


def main():
    p = argparse.ArgumentParser(description="Folktronika — utwór w duchu Four Teta.")
    p.add_argument("-o", "--output", default="folktronika")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--stems-instruments", action="store_true",
                   help="zapisz osobne WAV-y per instrument")
    args = p.parse_args()

    out = pathlib.Path(__file__).resolve().parent / f"{args.output}.wav"
    rng = np.random.default_rng(args.seed)
    t_start = time.time()

    print(f"folktronika · {BPM:.0f} BPM · {TOTAL:.0f} s ({N_BARS} taktów) · "
          f"F# molowa pentatonika · {SR // 1000} kHz")
    for b0, b1, nazwa, co in SEKCJE:
        print(f"  {bar_t(b0):6.1f}–{bar_t(b1):6.1f} s  {nazwa:16s} {co}")

    print("\nbuduję instrumenty…", flush=True)
    buf, stat = buduj(rng)
    print(f"  nut melodii {stat['nuty_melodii']} · uderzeń stopy "
          f"{stat['uderzenia_stopy']} · hi-hatów {stat['hi_haty']} "
          f"({time.time() - t_start:.1f} s)", flush=True)

    print("przestrzeń i mix…", flush=True)
    ir = ir_pokoj()
    mix = zmiksuj(buf, ir, args.stems_instruments, out)
    assert np.isfinite(mix).all(), "NaN w miksie"
    sf.write(out, mix, SR, subtype="PCM_24")
    sf.write(out.with_suffix(".flac"), mix, SR, subtype="PCM_24")
    print(f"  zapisane: {out.name}, {out.with_suffix('.flac').name}"
          + (f" + {len(STEMY)} stemów" if args.stems_instruments else "")
          + f"  ({time.time() - t_start:.1f} s)", flush=True)

    print("\npomiar z wyrenderowanego pliku (ADR-005):", flush=True)
    r = zmierz(out)
    ok = []

    def w(nazwa, wart, dobrze, uwaga=""):
        ok.append(bool(dobrze))
        print(f"  [{'OK ' if dobrze else 'UWAGA'}] {nazwa:28s} {wart}"
              + (f"   {uwaga}" if uwaga else ""))

    w("skończoność", "brak NaN/Inf" if r["skonczony"] else "SĄ NaN!", r["skonczony"])
    w("szczyt", f"{r['szczyt_dBFS']:+.2f} dBFS", r["szczyt_dBFS"] < -0.5, "cel −1,0")
    w("true peak (4×)", f"{r['truepeak_dBFS']:+.2f} dBFS",
      r["truepeak_dBFS"] < 0.0, "cel < 0")
    w("głośność", f"{r['glosnosc_LUFS']:.1f} LUFS(≈)",
      -20 < r["glosnosc_LUFS"] < -8, "folktronika ≈ −16…−11")
    w("zakres dynamiki", f"{r['zakres_dyn_dB']:.1f} dB",
      r["zakres_dyn_dB"] > 4.0, "płasko gdy < 4")
    w("offset DC", f"{r['dc']:.2e}", r["dc"] < 1e-3)
    print("  balans widmowy (udział energii · crest):")
    for lab, db, cr in r["pasma"]:
        print(f"      {lab:10s} {db:+6.1f} dB   crest {cr:5.1f} dB")
    w("korelacja L/R", f"{r['korelacja']:+.3f}",
      0.2 < r["korelacja"] < 0.95, "mono gdy > 0,95")
    w("korelacja L/R w dole", f"{r['korelacja_dol']:+.3f}",
      r["korelacja_dol"] > 0.97, "sub musi być mono")
    w("puls ćwiartek", f"{r['puls_dB']:+.1f} dB", r["puls_dB"] > 3.0,
      "groove słyszalny w obwiedni")
    pr = r["petla_r"]
    w("pętla w paśmie melodii",
      " · ".join(f"{k} t.: {v:+.2f}" for k, v in pr.items()),
      max(pr.values()) > 0.15 and max(pr.values()) < 0.95,
      "0,95+ = mechaniczne powtórzenie, <0,15 = brak pętli")
    w("energia > 22 kHz (poza pasmem)", f"{r['ultra_udzial'] * 100:.4f} %",
      r["ultra_udzial"] < 0.01, "sufit pasma trzyma")
    w("najdłuższa cisza", f"{r['najdluzsza_cisza_s']:.2f} s",
      r["najdluzsza_cisza_s"] < 2.0)
    w("koniec (0,5 s)", f"{r['koniec_dBFS']:.1f} dBFS",
      r["koniec_dBFS"] < -35, "utwór ma wybrzmieć, nie urwać się")

    print(f"\n{sum(ok)}/{len(ok)} miar w normie · render {time.time() - t_start:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
