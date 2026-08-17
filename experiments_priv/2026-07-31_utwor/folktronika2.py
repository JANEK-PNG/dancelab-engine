"""Folktronika II — „ruchoma ziemia". Pięć nut stoi, grunt pod nimi się zmienia.

Cała mechanika utworu w jednym zdaniu: górny zbiór {D, E, F#, A, B} nie
rusza się przez 240 sekund, a korzeń basu przechodzi D2 → B1 → G1 → A1,
więc ten sam materiał melodyczny brzmi kolejno jako D6/9, Bm11, Gmaj9(6)
i A9sus4. Harmonia się zmienia, a nikt nie transponuje ani jednej nuty —
stąd bierze się jednocześnie ruch i hipnoza.

Napisane od zera, jak `folktronika.py`: zero próbek, zero importu z silnika
in-between. Względem pierwszej wersji zmieniło się to, co słychać:

  • RUCHOMA ZIEMIA zamiast huśtawki dwóch akordów (powyżej).
  • STRÓJ NATURALNY: 5-graniczne interwały względem D, A4 = 439 Hz. Do tego
    stała tablica rozstrojeń per (klasa, oktawa), losowana RAZ — instrument
    jest „znaleziony", ale zawsze ten sam. Rozstrojenie losowane per nuta
    brzmi jak usterka; stałe brzmi jak drewno.
  • MELODIA TO JEDNO PUDŁO, nie bank oscylatorów: struna (Karplus–Strong)
    + kalimba oktawę niżej (analityczny bank modalny pręta zamocowanego,
    stosunki 1 : 6,267 : 17,547) + metalofon na akcentach.
  • MIKROCZAS JAKO TABELA: stopa ma sigma = 0 i jest KOTWICĄ — bez jednej
    warstwy maszynowo równej dryf reszty jest niesłyszalny. Bas wyprzedza
    (−4 ms), perkusja zostaje z tyłu (+6 ms), pad wchodzi w kreskę (−15 ms),
    melodia płynie z dryfem w całości (k = 1,0).
  • DUCKING DETERMINISTYCZNY: znamy czasy stopy, więc nie potrzeba
    kompresora ani detekcji — obwiednia liczona wprost.
  • FILTR RUCHOMY jako bank filtrów STAŁYCH z przenikaniem. Przeliczanie
    współczynników blokami daje skoki na granicach (stan biquada żyje
    w układzie starych współczynników); przenikanie nie ma czego zipperować.
  • PĘTLE WZAJEMNIE PIERWSZE: perkusja 4 takty, tekstury 5, melodia 8 —
    zbieżność dopiero co 40 taktów, czyli dwa razy w utworze.

Zasady przeniesione z in between (logika, nie kod): faza całkowana dla
tonów i losowa dla szumu; własna faza startowa każdego głosu; modulacje
z pamięci ~1,4 s; dół gra linie i jest w mono; humanizacja u źródła;
ADR-005 — każda liczba zmierzona z wyrenderowanego pliku.

Pułapka 96 kHz, na którą trzeba uważać w każdym miejscu: biały szum ma
tu ~58% mocy powyżej 20 kHz. Każde źródło szumu jest najpierw ścinane
filtrem 18 kHz, inaczej perkusja świeci w pasmie, którego nikt nie usłyszy,
a które zjada zapas.
"""

from __future__ import annotations

import argparse
import pathlib
import time

import numpy as np
import soundfile as sf
from scipy.signal import butter, iirpeak, lfilter, oaconvolve, sosfilt, sosfiltfilt, tf2sos

# ─────────────────────────── rama ───────────────────────────
SR = 96000
BPM = 112.0
BEAT = 60.0 / BPM                  # 0,535714286 s
BAR = 4 * BEAT                     # 2,142857143 s
S16 = BEAT / 4                     # 0,133928571 s
N_BARS = 112
TOTAL = N_BARS * BAR               # 240,000000 s dokładnie
N = int(round(TOTAL * SR))         # 23 040 000 próbek
STEMY = ("KICK", "DRUMS", "HATS", "BASS", "CHORDS", "MELODY", "TEXTURES")

# strój naturalny: 5-graniczne interwały względem D, A4 = 439 Hz
A4 = 439.0
D3 = A4 * (2.0 / 3.0) / 2.0        # 146,3333 Hz
JI = {"D": 1.0, "E": 9 / 8, "F#": 5 / 4, "G": 4 / 3, "A": 3 / 2, "B": 5 / 3,
      "C": 16 / 9}
_ROZSTROJ: dict[tuple, float] = {}


def ton(klasa, okt):
    """Hz w stroju naturalnym + stałe rozstrojenie „znalezionego instrumentu"."""
    if (klasa, okt) not in _ROZSTROJ:
        r = np.random.default_rng(hash((klasa, okt)) & 0xFFFF)
        _ROZSTROJ[(klasa, okt)] = float(np.clip(r.normal(0, 4.5), -11, 11))
    return D3 * JI[klasa] * 2.0 ** (okt - 3) * 2 ** (_ROZSTROJ[(klasa, okt)] / 1200)


# pentatonika melodii: stopnie 0..7
PENTA = [("D", 5), ("E", 5), ("F#", 5), ("A", 5), ("B", 5),
         ("D", 6), ("E", 6), ("F#", 6)]
# wołowania pada — pięć nut, bez tercji w górze (otwarte kwarty i kwinty)
V_D = [("A", 3), ("D", 4), ("E", 4), ("A", 4), ("D", 5)]
V_B = [("B", 3), ("D", 4), ("F#", 4), ("A", 4), ("D", 5)]
V_G = [("B", 3), ("D", 4), ("F#", 4), ("A", 4), ("D", 5)]
V_A = [("A", 3), ("D", 4), ("E", 4), ("A", 4), ("E", 5)]
V_MIX = [("C", 4), ("D", 4), ("E", 4), ("A", 4), ("C", 5)]   # C naturalne, B out
V_SUS = [("B", 3), ("D", 4), ("G", 4), ("A", 4), ("D", 5)]   # F# → G: bez tercji


def bar_t(b):
    return b * BAR


def ss(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def szum(n, rng):
    """Szum ZAWSZE ścinany na 18 kHz: przy 96 kHz biały ma 58% mocy >20 kHz."""
    return sosfilt(butter(8, 18000 / (SR / 2), btype="low", output="sos"),
                   rng.standard_normal(n))


# ────────────────── prymitywy: struna, pręt, membrana ──────────────────
def ks(f0, dur, t60=1.6, mi=0.19, s=0.28, seed=0):
    """Karplus–Strong blokowy z kompensacją opóźnienia filtra pętli.

    Bez odjęcia opóźnienia grupowego filtra tłumiącego strój ucieka w dół
    tym mocniej, im wyższa nuta (zmierzone −9 centów przy 1 kHz).
    Blok o długości L−3 liczy się wektorowo, bo y[n] zależy tylko od
    próbek starszych o co najmniej L−3.
    """
    w0 = 2 * np.pi * f0 / SR
    H = (1 - s) + s * np.exp(-1j * w0)          # filtr pętli [1-s, s]
    pd = -np.angle(H) / w0                       # jego opóźnienie grupowe
    total = SR / f0 - pd
    L = int(np.floor(total)) - 1
    D = total - L                                # ∈ [1,2) — Lagrange 3. rzędu
    if L < 4:
        return np.zeros(int(dur * SR), np.float32)
    g = min(10 ** (-3.0 / (f0 * t60)) / abs(H), 0.99999 / abs(H))

    rng = np.random.default_rng(seed)
    n_out = int(dur * SR)
    M = L + 4
    y = np.zeros(n_out + M + 8)
    L_exc = max(4, int(SR / f0))
    e = szum(L_exc, rng)
    e = sosfilt(butter(2, np.clip(f0 * 6, 400, 16000) / (SR / 2),
                       btype="low", output="sos"), e)
    e *= np.sin(np.pi * np.arange(L_exc) / L_exc) ** 0.35     # bez kliku
    e -= e.mean()                                # DC w pętli sczytuje wysokość
    e /= np.abs(e).max() + 1e-12
    buf = np.zeros(M)
    idx = np.arange(L_exc) % M
    np.add.at(buf, idx, e[:len(idx)])
    np.add.at(buf, (idx + int(round(mi * L))) % M, -e[:len(idx)])   # grzebień
    y[:M] = buf

    # Lagrange 3. rzędu na ułamek D ∈ [1,2)
    d = D - 1.0
    h = np.array([-d * (d - 1) * (d - 2) / 6.0,
                  (d + 1) * (d - 1) * (d - 2) / 2.0,
                  -(d + 1) * d * (d - 2) / 2.0,
                  (d + 1) * d * (d - 1) / 6.0])
    B = L - 3
    pos = M
    while pos < len(y):
        m = min(B, len(y) - pos)
        acc = np.zeros(m)
        for k in range(4):
            acc += h[k] * y[pos - L - 1 + k: pos - L - 1 + k + m]
        blk = g * ((1 - s) * acc + s * np.concatenate(
            ([y[pos - L - 2]], acc[:m - 1])))
        y[pos: pos + m] = blk
        pos += m
    y = y[:n_out]
    return (y / (np.abs(y).max() + 1e-12)).astype(np.float32)


def modalny(f1, ratios, amps, t60s, dur, seed=0, gliss=0.0, gliss_tau=0.012):
    """Bank modalny liczony analitycznie — każdy mod z własną fazą startową."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for r, a, t60 in zip(ratios, amps, t60s):
        f = f1 * r
        if f > SR / 2 * 0.95:
            continue
        if gliss:
            ph = 2 * np.pi * np.cumsum(f * (1 + gliss * np.exp(-t / gliss_tau))) / SR
        else:
            ph = 2 * np.pi * f * t
        y += a * np.sin(ph + rng.uniform(0, 2 * np.pi)) * np.exp(-6.9078 * t / t60)
    y *= 1 - np.exp(-t / 0.0006)
    return (y / (np.abs(y).max() + 1e-12)).astype(np.float32)


PRET = ([1.0, 6.267, 17.547, 34.386], [1.0, 0.42, 0.16, 0.07],
        [2.2, 0.30, 0.10, 0.045])                      # kalimba (pręt)
METAL = ([1.0, 4.0, 10.0, 20.8], [1.0, 0.5, 0.22, 0.09],
         [3.2, 1.1, 0.5, 0.2])                          # metalofon


def glos_melodii(f0, dur, t60, seed, metal=0.0):
    """Trzy warstwy w JEDNYM pudle: struna + kalimba oktawę niżej + metal."""
    a = ks(f0, dur, t60=t60, mi=0.19, seed=seed) * 0.62
    b = modalny(f0 / 2, *PRET, dur, seed=seed + 1) * 0.28
    y = a + b[:len(a)]
    if metal > 0:
        c = modalny(f0, *METAL, dur, seed=seed + 2) * metal
        y = y + c[:len(y)]
    return (y / (np.abs(y).max() + 1e-12)).astype(np.float32)


def kick(f0=122.0, f1=43.0, tau_p=0.028, tau_a=0.055, dur=0.75, drive=1.7,
         klik_db=-15.0, seed=0):
    """Stopa: FAZA CAŁKOWANA. sin(2π·f(t)·t) daje f + t·f′ — czynnik (1−t/τ)
    zmienia znak i stopa nurkuje 465 centów pod projektowane dno."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / tau_p)
    ph = np.cumsum(2 * np.pi * f / SR, dtype=np.float64)
    ph -= ph[0]
    body = np.sin(ph) * (1 - np.exp(-t / 0.0012)) * np.exp(-t / tau_a)
    kl = sosfilt(butter(2, 1400 / (SR / 2), btype="high", output="sos"),
                 szum(n, rng)) * np.exp(-t / 0.00045)
    kl += 0.5 * np.sin(2 * np.pi * 2200 * t) * np.exp(-t / 0.0022)
    x = body + kl * 10 ** (klik_db / 20)
    x = np.tanh(drive * x) / np.tanh(drive)
    x = sosfilt(butter(2, 22 / (SR / 2), btype="high", output="sos"), x)
    return (x / (np.abs(x).max() + 1e-12)).astype(np.float32)


def klask(dur=0.32, seed=0):
    """Cztery bursty mnożące TEN SAM przebieg szumu — jedne dłonie, nie cztery."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    z = szum(n, rng)
    y = np.zeros(n)
    for d_ms, a in ((0, 0.8), (11, 1.0), (21, 0.85), (30, 0.6)):
        d = int(d_ms / 1000 * SR)
        y[d:] += a * z[d:] * np.exp(-t[:n - d] / 0.0035)
    y += 0.33 * z * np.exp(-t / 0.115)
    sos = butter(4, [900 / (SR / 2), 2900 / (SR / 2)], btype="band", output="sos")
    y = sosfilt(sos, y)
    return (y / (np.abs(y).max() + 1e-12)).astype(np.float32)


def hat(otwarty=False, pedal=False, seed=0):
    """Metaliczność = siedem wąskich prążków o niewspółmiernych odstępach."""
    rng = np.random.default_rng(seed)
    t60 = 0.36 if otwarty else (0.090 if pedal else 0.050)
    n = int((t60 * 1.6 + 0.02) * SR)
    t = np.arange(n) / SR
    z = szum(n, rng)
    y = np.zeros(n)
    war = 1 + rng.normal(0, 0.015)
    for f in (3180, 4210, 5310, 6790, 8330, 10250, 12400):
        fr = f * war * (0.92 if pedal else 1.0)
        if fr >= SR / 2 * 0.95:
            continue
        b, a = iirpeak(fr / (SR / 2), 38)
        y += sosfilt(tf2sos(b, a), z)          # NIGDY postać (b,a): bieguny >1
    y = sosfilt(butter(2, (2400 if pedal else 3200) / (SR / 2),
                       btype="high", output="sos"), y)
    y *= (1 - np.exp(-t / 0.0004)) * np.exp(-6.9078 * t / (t60 * (1 + rng.normal(0, .08))))
    return (y / (np.abs(y).max() + 1e-12)).astype(np.float32)


def bas_nuta(f0, dur, vel=1.0, seed=0):
    """Linia, nie szum. ERB(73 Hz) = 33 Hz — cokolwiek szumowego obok basu
    wpada w to samo pasmo krytyczne i daje szorstkość zamiast barwy."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    ph = 2 * np.pi * f0 * t
    drive = 1.3 + 0.6 * vel
    x = np.tanh(drive * (np.sin(ph) + 0.10 * np.sin(2 * ph + 0.7))) / np.tanh(drive)
    body = sosfilt(butter(2, 700 / (SR / 2), btype="low", output="sos"), x)
    env = (1 - np.exp(-t / 0.006)) * (0.55 + 0.45 * np.exp(-t / 0.38)) * np.exp(-t / 1.2)
    y = (0.75 * np.sin(ph) + 0.35 * body) * env
    y = sosfilt(butter(4, 28 / (SR / 2), btype="high", output="sos"), y)
    return (y / (np.abs(y).max() + 1e-12)).astype(np.float32)


def pad_glos(f0, dur, seed=0, K=8):
    """Głos pada: faza całkowana, własna faza startowa, grubość Z PAMIĘCI."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    ph = np.arange(n, dtype=np.float64) * (f0 / SR)      # obroty, nie radiany
    y = np.zeros(n)
    ns = max(2, int(dur * 40))
    for k in range(1, K + 1):
        wolno = np.interp(np.arange(n), np.linspace(0, n, ns),
                          rng.standard_normal(ns))       # pamięć ~1,4 s
        wolno /= np.abs(wolno).max() + 1e-12
        y += k ** -1.35 * (1 + 0.08 * wolno) * np.sin(
            2 * np.pi * (k * ph + rng.uniform(0, 1)))
    return (y / (np.abs(y).max() + 1e-12)).astype(np.float32)


def ruchomy_lp(x, fc_t):
    """Filtr ruchomy = bank filtrów STAŁYCH + przenikanie.

    Przeliczanie współczynników blokami daje skoki na granicach: stan biquada
    żyje w układzie współrzędnych STARYCH współczynników. Przenikanie nie ma
    czego zipperować, bo jest mnożeniem przez gładką obwiednię.
    """
    bank = np.exp(np.linspace(np.log(250), np.log(8000), 9))
    Y = [sosfilt(butter(2, f / (SR / 2), btype="low", output="sos"), x, axis=0)
         for f in bank]
    u = np.interp(np.log(np.clip(fc_t, bank[0], bank[-1])), np.log(bank),
                  np.arange(9))
    i0 = np.clip(u.astype(int), 0, 7)
    w = (u - i0)[:, None]
    out = np.zeros_like(x)
    for i in range(8):
        m = i0 == i
        if m.any():
            out[m] = Y[i][m] * (1 - w[m]) + Y[i + 1][m] * w[m]
    return out.astype(np.float32)


# ────────────────── mikroczas: jedna kotwica, reszta płynie ──────────────────
# stem: (sigma [s], bias [s], sprzężenie z dryfem k)
CZAS = {"KICK": (0.000, 0.000, 0.00),      # KOTWICA — bez niej dryf jest niesłyszalny
        "DRUMS": (0.003, +0.006, 0.25),     # zostaje z tyłu
        "HATS": (0.002, 0.000, 0.15),
        "BASS": (0.0035, -0.004, 0.40),     # ciągnie do przodu
        "CHORDS": (0.006, -0.015, 0.60),    # wchodzi W kreskę
        "MELODY": (0.007, +0.002, 1.00),    # płynie z dryfem w całości
        "TEXTURES": (0.025, 0.000, 0.00)}   # własny czas
LIMIT = 0.25 * S16                          # 33,5 ms — definicja „rozjechane"


def wstaw(dst, t_sec, sig, gain=1.0, pan=0.0):
    i0 = int(t_sec * SR)
    if i0 < 0 or i0 >= len(dst):
        return
    m = min(len(sig), len(dst) - i0)
    if m <= 0:
        return
    th = (np.clip(pan, -1, 1) + 1) * np.pi / 4
    dst[i0:i0 + m, 0] += sig[:m] * (gain * np.cos(th))
    dst[i0:i0 + m, 1] += sig[:m] * (gain * np.sin(th))


# ────────────────── komórki melodii i silnik wariacji ──────────────────
# (szesnastka w 2 taktach, stopień PENTA, rola)  F = filar, W = wewnętrzna, O = ozdobnik
CELA_A = [(0, 3, "F"), (3, 4, "W"), (6, 2, "O"), (10, 1, "W"),
          (16, 0, "F"), (19, 2, "W"), (22, 3, "O"), (27, 4, "W")]
CELA_B = [(0, 3, "F"), (4, 1, "W"), (7, 2, "W"), (12, 0, "O"),
          (16, 4, "F"), (22, 3, "W"), (26, 2, "O"), (30, 1, "W")]
CELA_C = [(0, 6, "F"), (8, 5, "W"), (16, 4, "F"), (24, 3, "W")]
P_DROP = {"F": 0.00, "W": 0.10, "O": 0.35}
P_OKT = {"F": 0.04, "W": 0.10, "O": 0.18}
P_SASIAD = {"F": 0.00, "W": 0.15, "O": 0.25}


def plan_basu(b):
    """Ruchoma ziemia: ten sam zbiór na górze, inny korzeń pod spodem."""
    if b < 24:
        return None
    if b < 44:
        return ("D", 2)
    if b < 48:
        return [("D", 2), ("B", 1), ("G", 1), ("A", 1)][(b - 44) % 4]
    if b < 56:
        return ("D", 2)
    if b < 72:
        return [("D", 2), ("B", 1), ("G", 1), ("A", 1)][(b - 56) % 4]
    if b < 80:
        return ("B", 1)          # pedał — Bm11
    if b < 88:
        return ("G", 1)          # tercja wraca nad G = Gmaj9, najjaśniej
    if b < 106:
        return ("D", 2)
    return None


def plan_pada(b):
    if 48 <= b < 56:
        return V_MIX             # oddech: C naturalne, B usunięte
    if 72 <= b < 80:
        return V_SUS             # kulminacja: F# → G, bez tercji
    if 56 <= b < 72:
        return [V_D, V_B, V_G, V_A][(b - 56) % 4]
    if 80 <= b < 88:
        return V_B
    return V_D


def buduj(rng):
    buf = {s: np.zeros((N, 2), np.float32) for s in STEMY}
    stat = {"melodia": 0, "stopa": 0, "haty": 0, "przyciete": 0}

    # wspólny wolny dryf zespołu (pamięć, nie losowość per zdarzenie)
    dt_ax = np.arange(0, TOTAL + 1, 0.05)
    dr = np.interp(dt_ax, np.linspace(0, TOTAL, 60), rng.standard_normal(60))
    dryf = dr / (np.abs(dr).max() + 1e-12) * 0.016

    def czas(stem, t_nom):
        sg, bias, k = CZAS[stem]
        d = k * float(np.interp(t_nom, dt_ax, dryf)) + bias
        if sg:
            d += rng.normal(0, sg)
        if abs(d) > LIMIT:
            stat["przyciete"] += 1
            d = np.clip(d, -LIMIT, LIMIT)
        return t_nom + d

    def swing(b, s16):
        return (0.055 + 0.045 * ss((b - 52) / 12)) * S16 if s16 % 2 else 0.0

    # ── CHORDS: pad + arpeggio ──
    for b in range(0, N_BARS):
        wol = plan_pada(b)
        if b > 0 and plan_pada(b - 1) == wol:
            continue                                   # trzymaj, nie przegrywaj
        b_end = b
        while b_end < N_BARS and plan_pada(b_end) == wol:
            b_end += 1
        dl = (b_end - b) * BAR + 2.6
        atak = 3.0 if b < 8 else 0.55
        for i, (kl, ok) in enumerate(wol):
            g = pad_glos(ton(kl, ok), dl, seed=int(rng.integers(1 << 30)))
            t = np.arange(len(g)) / SR
            env = np.minimum(t / atak, 1.0) ** 1.4 * np.clip((dl - t) / 2.2, 0, 1)
            env *= 0.75 + 0.25 * np.sin(2 * np.pi * 0.04208 * t + i)
            wstaw(buf["CHORDS"], czas("CHORDS", bar_t(b)),
                  (g * env).astype(np.float32),
                  gain=0.34 / (1 + 0.30 * i), pan=(-0.45 + i * 0.225))
    for b in range(64, 88):                            # arpeggio KS pod padem
        wol = plan_pada(b)
        for s8 in range(8):
            kl, ok = wol[s8 % len(wol)]
            wstaw(buf["CHORDS"], czas("CHORDS", bar_t(b) + s8 * BEAT / 2),
                  ks(ton(kl, ok), 1.1, t60=0.9, seed=int(rng.integers(1 << 30))),
                  gain=0.085, pan=rng.uniform(-0.4, 0.4))

    # ── KICK: kotwica. Cztery na takt, sigma = 0 ──
    kick_t = []
    for b in list(range(16, 48)) + list(range(56, 96)):
        war = dict(f0=118.0, f1=38.5) if 72 <= b < 88 else dict(f0=122.0, f1=43.0)
        for q in range(4):
            if b % 8 == 7 and q == 3:
                continue
            t0 = czas("KICK", bar_t(b) + q * BEAT)
            akc = (1.00, 0.88, 0.94, 0.86)[q]
            wstaw(buf["KICK"], t0, kick(seed=int(rng.integers(1 << 30)), **war),
                  gain=0.62 * akc, pan=0.0)
            kick_t.append(t0)
            stat["stopa"] += 1
        if b == 55:
            wstaw(buf["KICK"], bar_t(b) + 15 * S16, kick(f0=110, tau_a=0.04),
                  gain=0.30, pan=0.0)

    # ── BASS: ruchoma ziemia + ducking deterministyczny ──
    kick_arr = np.array(kick_t)
    for b in range(24, 106):
        korz = plan_basu(b)
        if korz is None:
            continue
        f0 = ton(*korz)
        zmiana = b > 0 and plan_basu(b - 1) != korz
        for s8 in range(8):
            if s8 == 0:
                vel = 1.00
            elif rng.random() > 0.30:
                continue
            else:
                vel = rng.uniform(0.62, 0.75)
            if s8 == 0 and zmiana:
                vel = 1.00
            t0 = czas("BASS", bar_t(b) + s8 * BEAT / 2)
            wstaw(buf["BASS"], t0,
                  bas_nuta(f0, 0.9, vel=vel, seed=int(rng.integers(1 << 30))),
                  gain=0.42 * vel, pan=0.0)
    if len(kick_arr):                                  # −4 dB, atak 10 ms
        t_ax = np.arange(N) / SR
        g = np.ones(N, np.float32)
        for tk in kick_arr:
            i0 = int(tk * SR)
            i1 = min(N, i0 + int(0.30 * SR))
            if i1 <= i0:
                continue
            dt = t_ax[i0:i1] - tk
            g[i0:i1] *= 1 - 0.37 * np.exp(-dt / 0.055) * (1 - np.exp(-dt / 0.010))
        buf["BASS"] *= g[:, None]

    # ── DRUMS: klask + bęben ramowy strojony do tonacji (G = 4/3) ──
    for b in range(28, 96):
        if 48 <= b < 56:
            continue
        for q in (1, 3):
            if b >= 36:
                wstaw(buf["DRUMS"], czas("DRUMS", bar_t(b) + q * BEAT),
                      klask(seed=int(rng.integers(1 << 30))),
                      gain=0.30 * (0.85 if q == 1 else 1.00),
                      pan=0.35 * (1 if b % 2 else -1))
        for s16 in range(16):
            if rng.random() > 0.35:
                continue
            akcent = s16 % 8 in (2, 6)
            t60s = [0.55, 0.30, 0.18, 0.10] if akcent else [0.10, 0.054, 0.032, 0.018]
            sig = modalny(ton("G", 3), [1.0, 2.0, 3.0, 4.0],
                          [1.0, 0.55, 0.30, 0.15], t60s, 0.6,
                          seed=int(rng.integers(1 << 30)), gliss=0.06)
            wstaw(buf["DRUMS"],
                  czas("DRUMS", bar_t(b) + s16 * S16 + swing(b, s16)), sig,
                  gain=0.20 * (1.0 if akcent else 0.6) * rng.uniform(0.8, 1.1),
                  pan=rng.uniform(-0.35, 0.35))

    # ── HATS ──
    WZOR = "x.x.xxx.x.x..xx."
    for b in range(8, 104):
        for s16 in range(16):
            if b < 20:
                if s16 % 4 != 2:
                    continue
                g, otw = 0.55, False
            else:
                c = WZOR[s16]
                if c == ".":
                    if not (68 <= b < 72 and rng.random() < 0.5):
                        continue
                    g, otw = 0.30, False
                else:
                    g = 1.00 if s16 % 8 in (0, 4) else 0.55
                    otw = (s16 == 14 and b % 4 == 3)
            if s16 % 2:
                g *= 0.35 / 0.55
            else:
                g *= 1.15 if s16 % 4 == 2 else 1.0
            wstaw(buf["HATS"],
                  czas("HATS", bar_t(b) + s16 * S16 + swing(b, s16)),
                  hat(otwarty=otw, seed=int(rng.integers(1 << 30))),
                  gain=0.26 * g,
                  pan=0.55 * np.sin(2 * np.pi * bar_t(b) / 14.687))
            stat["haty"] += 1

    # ── MELODY: trzy komórki, wariacja NA POWTÓRZENIE ──
    cache: dict[tuple, np.ndarray] = {}

    def dzwiek(stopien, okt_up, t60, metal):
        key = (stopien, okt_up, round(t60, 2), round(metal, 2))
        if key not in cache:
            kl, ok = PENTA[stopien]
            cache[key] = glos_melodii(ton(kl, ok + okt_up), min(t60 * 1.6, 3.2),
                                      t60, seed=stopien * 97 + okt_up * 7,
                                      metal=metal)
        return cache[key]

    for b in range(32, 108, 2):
        if b < 48:
            cela, poziom, t60 = CELA_A, 0.85, 0.62
        elif b < 56:
            cela, poziom, t60 = CELA_A, 0.45, 0.62      # oddech: same filary
        elif b < 72:
            cela, poziom, t60 = CELA_B, 0.95, 0.62
        elif b < 80:
            cela, poziom, t60 = CELA_C, 1.00, 0.90      # augmentacja, oktawę wyżej
        elif b < 88:
            cela, poziom, t60 = CELA_C, 1.00, 0.90
        else:
            cela, poziom, t60 = CELA_A, max(0.25, 1.0 - (b - 88) / 26), 0.62
        p_extra = 0.35 * ss((b - 88) / 16)               # pętla się rozpada
        zdarzenia = list(cela)
        if 80 <= b < 88:                                  # jedyny dwugłos
            zdarzenia += [(s, st, r) for (s, st, r) in CELA_A]
        for j, (s16, st, rola) in enumerate(zdarzenia):
            drugi = 80 <= b < 88 and j >= len(cela)
            if 48 <= b < 56 and rola != "F":
                continue
            if rng.random() < P_DROP[rola] + p_extra:
                continue
            stp = st
            if rng.random() < P_SASIAD[rola]:
                stp = int(np.clip(st + rng.choice([-1, 1]), 0, len(PENTA) - 1))
            okt = 1 if rng.random() < P_OKT[rola] else 0
            t_nom = bar_t(b) + s16 * S16 + swing(b, s16)
            t0 = czas("MELODY", t_nom)
            metal = 0.10 if rola == "F" else 0.0
            sig = dzwiek(stp, okt, t60 * (0.45 if rng.random() < 0.15 else 1.0),
                         metal)
            amp = (1.0 if rola == "F" else 0.72 if rola == "W" else 0.5)
            wstaw(buf["MELODY"], t0, sig,
                  gain=0.30 * poziom * amp * (0.55 if drugi else 1.0)
                  * rng.uniform(0.88, 1.10),
                  pan=float(np.clip((stp - 3) * 0.06, -0.25, 0.25)))
            stat["melodia"] += 1
            if rng.random() < 0.12 and rola != "O":      # przednutka
                wstaw(buf["MELODY"], t0 - 0.055,
                      dzwiek(min(stp + 1, len(PENTA) - 1), okt, t60 * 0.3, 0.0),
                      gain=0.30 * poziom * amp * 0.35, pan=0.2)

    # ── TEXTURES: syntetyczny „odwrócony wokal", dzwonki, powietrze ──
    tex = buf["TEXTURES"]
    for b in range(4, 110, 2):                            # głos
        kl, ok = PENTA[int(rng.integers(0, 4))]
        f0 = ton(kl, ok - 1)
        dur = 3.2
        n = int(dur * SR)
        t = np.arange(n) / SR
        ns = max(2, int(dur * 40))
        wolno = np.interp(np.arange(n), np.linspace(0, n, ns),
                          rng.standard_normal(ns))
        wolno /= np.abs(wolno).max() + 1e-12
        K = max(2, int(8000 / f0))
        ph = np.cumsum(2 * np.pi * f0 * (1 + 0.0035 * wolno) / SR)
        x = sum(np.cos(k * ph) / k ** 0.9 for k in range(1, K + 1))
        form = ((380, 60), (940, 90), (2400, 140)) if rng.random() < 0.5 else \
               ((620, 80), (1180, 90), (2650, 130))
        v = np.zeros(n)
        for F, BW in form:
            bq, aq = iirpeak(F / (SR / 2), F / BW)
            v += sosfilt(tf2sos(bq, aq), x)
        v *= np.minimum(1, t / 0.45) ** 2 * np.exp(-t / 2.2)   # obwiednia ODWRÓCONA
        if rng.random() < 0.30:                                # stutter obwiednią
            per = int(S16 / 2 * SR)
            gate = ((np.arange(n) // per) % 2 == 0).astype(np.float64)
            gate = np.convolve(gate, np.ones(int(0.004 * SR)) / int(0.004 * SR),
                               mode="same")
            v *= 0.5 + 0.5 * gate
        v /= np.abs(v).max() + 1e-12
        wstaw(tex, czas("TEXTURES", bar_t(b)), v.astype(np.float32),
              gain=0.13, pan=rng.uniform(-0.7, 0.7))
    for b in range(20, 108, 5):                            # dzwonki, pętla 5-taktowa
        for s in (0, 3, 6, 11):
            kl, ok = PENTA[int(rng.integers(2, 8))]
            wstaw(tex, czas("TEXTURES", bar_t(b) + s * S16 * 2),
                  modalny(ton(kl, ok), *METAL, 2.0,
                          seed=int(rng.integers(1 << 30))),
                  gain=0.05 * rng.uniform(0.5, 1.0), pan=rng.uniform(-0.7, 0.7))
    b_pink, a_pink = ([0.049922035, -0.095993537, 0.050612699, -0.004408786],
                      [1, -2.494956002, 2.017265875, -0.5221894])
    powietrze = lfilter(b_pink, a_pink, rng.standard_normal(N))
    powietrze = sosfilt(butter(2, [2200 / (SR / 2), 16000 / (SR / 2)],
                              btype="band", output="sos"), powietrze)
    powietrze /= np.abs(powietrze).max() + 1e-12
    lfo = 0.55 + 0.45 * np.sin(2 * np.pi * np.arange(N) / SR / 62.217)
    tex[:, 0] += (powietrze * lfo * 0.05).astype(np.float32)
    tex[:, 1] += (np.roll(powietrze, 1301) * lfo * 0.05).astype(np.float32)
    tex += 0.25 * tex.mean(axis=1, keepdims=True)          # inaczej korelacja ≈ 0
    return buf, stat


# ────────────────── mix ──────────────────
MIX = {   # (wzmocnienie, HP, LP, drive, wysyłka pogłosu)
    "KICK":     (1.00, 22, 9000, 0.00, 0.00),
    "DRUMS":    (0.85, 140, 15000, 0.10, 0.06),
    "HATS":     (0.62, 5500, None, 0.00, 0.04),
    "BASS":     (1.05, 28, 700, 0.00, 0.00),
    "CHORDS":   (0.70, 150, 7000, 0.22, 0.22),
    "MELODY":   (1.55, 400, 12000, 0.18, 0.16),
    "TEXTURES": (0.75, 260, None, 0.05, 0.30),
}
CEL_DBFS = {"KICK": -7.5, "DRUMS": -13.0, "HATS": -19.5, "BASS": -9.0,
            "CHORDS": -14.5, "MELODY": -14.0, "TEXTURES": -21.0}


def ir_pokoj(t60=2.4, seed=1, pre_ms=16.0):
    rng = np.random.default_rng(seed)
    n = int(t60 * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-6.9078 * t / t60)[:, None]
    ir *= (t[:, None] / 0.025).clip(0, 1) ** 0.6
    sos = butter(2, 5000 / (SR / 2), btype="low", output="sos")
    mixf = np.linspace(0, 1, n)[:, None] ** 0.7
    ir = ir * (1 - mixf) + sosfilt(sos, ir, axis=0) * mixf
    for d_ms, a in ((7, .5), (11, .42), (17, .34), (23, .27), (31, .21), (43, .15)):
        d = int(d_ms / 1000 * SR)
        ir[d] += a * rng.choice([-1.0, 1.0], 2)
    ir = np.vstack([np.zeros((int(pre_ms / 1000 * SR), 2)), ir])[:n]
    ir /= np.sqrt((ir ** 2).sum(axis=0)).max() + 1e-12
    return ir.astype(np.float32)


def zmiksuj(buf, ir, zapisz, out):
    mix = np.zeros((N, 2), np.float32)
    stemy = {}
    for s in STEMY:
        x = buf[s]
        g, hp, lp, drv, wet = MIX[s]
        if hp:
            x = sosfilt(butter(2, hp / (SR / 2), btype="high", output="sos"),
                        x, axis=0).astype(np.float32)
        if lp:
            x = sosfilt(butter(4, lp / (SR / 2), btype="low", output="sos"),
                        x, axis=0).astype(np.float32)
        if drv:
            x = (np.tanh(x * (1 + drv)) / np.tanh(1 + drv)).astype(np.float32)
        if wet > 0:
            send = sosfilt(butter(2, 180 / (SR / 2), btype="high", output="sos"),
                           x, axis=0)                    # sub nigdy w pogłos
            w = np.empty_like(x)
            for ch in range(2):
                w[:, ch] = oaconvolve(send[:, ch], ir[:, ch])[:N]
            w *= np.abs(x).max() / (np.abs(w).max() + 1e-12)
            x = (x + w * wet).astype(np.float32)
        if s in ("KICK", "BASS"):
            x = np.repeat(x.mean(axis=1, keepdims=True), 2, axis=1)
        szczyt = float(np.abs(x).max()) + 1e-12
        x = (x * (10 ** (CEL_DBFS[s] / 20) / szczyt) * g).astype(np.float32)
        assert np.isfinite(x).all(), f"NaN w stemie {s}"
        stemy[s] = x
        mix += x

    mix = (np.tanh(mix * 1.10) / np.tanh(1.10)).astype(np.float32)
    mix = sosfilt(butter(2, 24 / (SR / 2), btype="high", output="sos"),
                  mix, axis=0).astype(np.float32)
    low = sosfiltfilt(butter(4, 150 / (SR / 2), btype="low", output="sos"),
                      mix, axis=0)                       # ZEROFAZOWY — inaczej grzebień
    mix = (mix - low + low.mean(axis=1, keepdims=True)).astype(np.float32)
    mix = sosfilt(butter(6, 22000 / (SR / 2), btype="low", output="sos"),
                  mix, axis=0).astype(np.float32)
    ogon = int(6.857 * SR)                                # fade od taktu 109
    mix[-ogon:] *= (np.cos(np.linspace(0, np.pi, ogon)) * 0.5 + 0.5)[:, None]
    mix[:int(0.03 * SR)] *= np.linspace(0, 1, int(0.03 * SR))[:, None]
    sz = float(np.abs(mix).max())
    mix *= 0.891 / (sz + 1e-12)
    if zapisz:
        for s, x in stemy.items():
            sf.write(out.parent / f"{out.stem}_{s}.wav",
                     x * (0.891 / (sz + 1e-12)), SR, subtype="PCM_24")
    return mix


def zmierz(path):
    y, sr = sf.read(path, dtype="float64")
    L, R = y[:, 0], y[:, 1]
    m = y.mean(axis=1)
    r = {"skonczony": bool(np.isfinite(y).all()),
         "szczyt": 20 * np.log10(np.abs(y).max() + 1e-12),
         "truepeak": 20 * np.log10(np.abs(np.repeat(y, 4, axis=0)).max() + 1e-12),
         "dc": float(np.abs(m.mean()))}
    k = sosfilt(butter(2, 120 / (sr / 2), btype="high", output="sos"), m)
    k = k + 1.26 * sosfilt(butter(2, [1000 / (sr / 2), 12000 / (sr / 2)],
                                  btype="band", output="sos"), k)
    blok = int(0.4 * sr)
    moce = np.array([p for p in ((k[i:i + blok] ** 2).mean()
                                 for i in range(0, len(k) - blok, blok // 2))
                     if p > 0])
    gl = -0.691 + 10 * np.log10(moce)
    r["lufs"] = float(-0.691 + 10 * np.log10(moce[gl > gl.max() - 20].mean()))
    r["dr"] = float(np.percentile(gl, 95) - np.percentile(gl, 10))
    r["pasma"] = []
    tot = float((m ** 2).mean())
    for lo, hi, lab in ((20, 120, "sub"), (120, 500, "dół"), (500, 2000, "środek"),
                        (2000, 8000, "góra"), (8000, 20000, "powietrze")):
        b = sosfilt(butter(4, [lo / (sr / 2), min(hi, sr / 2 * .98) / (sr / 2)],
                           btype="band", output="sos"), m)
        e = float((b ** 2).mean())
        r["pasma"].append((lab, 10 * np.log10(e / tot + 1e-12),
                           20 * np.log10(np.abs(b).max() / np.sqrt(e + 1e-30))))
    r["kor"] = float(np.corrcoef(L, R)[0, 1])
    lob = sosfilt(butter(4, 150 / (sr / 2), btype="low", output="sos"), y.T).T
    r["kor_dol"] = float(np.corrcoef(lob[:, 0], lob[:, 1])[0, 1])
    F = np.abs(np.fft.rfft(m[:int(60 * sr)] * np.hanning(int(60 * sr))))
    fr = np.fft.rfftfreq(int(60 * sr), 1 / sr)
    r["ultra"] = float((F[fr > 22000] ** 2).sum() / ((F ** 2).sum() + 1e-12))
    r["koniec"] = 20 * np.log10(np.sqrt((m[-int(.5 * sr):] ** 2).mean()) + 1e-12)
    return r


def main():
    p = argparse.ArgumentParser(description="Folktronika II — ruchoma ziemia.")
    p.add_argument("-o", "--output", default="folktronika2")
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--stems-instruments", action="store_true")
    a = p.parse_args()
    out = pathlib.Path(__file__).resolve().parent / f"{a.output}.wav"
    rng = np.random.default_rng(a.seed)
    t0 = time.time()

    print(f"folktronika II · {BPM:.0f} BPM · {TOTAL:.1f} s ({N_BARS} taktów) · "
          f"strój naturalny od D, A4 = {A4:.0f} Hz")
    print("  ruchoma ziemia: {D,E,F#,A,B} stoi · korzeń D2→B1→G1→A1")
    print("  = D6/9 → Bm11 → Gmaj9(6) → A9sus4 bez transpozycji melodii\n")

    print("buduję…", flush=True)
    buf, stat = buduj(rng)
    print(f"  melodia {stat['melodia']} · stopa {stat['stopa']} · haty "
          f"{stat['haty']} · przycięte do ±33 ms: {stat['przyciete']} "
          f"({time.time() - t0:.1f} s)", flush=True)

    print("przestrzeń i mix…", flush=True)
    mix = zmiksuj(buf, ir_pokoj(), a.stems_instruments, out)
    assert np.isfinite(mix).all()
    sf.write(out, mix, SR, subtype="PCM_24")
    sf.write(out.with_suffix(".flac"), mix, SR, subtype="PCM_24")
    print(f"  zapisane ({time.time() - t0:.1f} s)", flush=True)

    r = zmierz(out)
    print("\npomiar z wyrenderowanego pliku (ADR-005):")
    ok = []

    def w(nz, v, dobrze, uw=""):
        ok.append(bool(dobrze))
        print(f"  [{'OK ' if dobrze else 'UWAGA'}] {nz:26s} {v}" +
              (f"   {uw}" if uw else ""))

    w("skończoność", "brak NaN", r["skonczony"], "")
    w("szczyt", f"{r['szczyt']:+.2f} dBFS", r["szczyt"] < -0.5)
    w("true peak", f"{r['truepeak']:+.2f} dBFS", r["truepeak"] < 0.0)
    w("głośność", f"{r['lufs']:.1f} LUFS(≈)", -20 < r["lufs"] < -8)
    w("zakres dynamiki", f"{r['dr']:.1f} dB", r["dr"] > 4.0)
    w("offset DC", f"{r['dc']:.2e}", r["dc"] < 1e-3)
    print("  balans widmowy:")
    for lab, db, cr in r["pasma"]:
        print(f"      {lab:10s} {db:+6.1f} dB   crest {cr:5.1f} dB")
    w("korelacja L/R", f"{r['kor']:+.3f}", 0.2 < r["kor"] < 0.95)
    w("korelacja L/R w dole", f"{r['kor_dol']:+.3f}", r["kor_dol"] > 0.97)
    w("energia > 22 kHz", f"{r['ultra'] * 100:.4f} %", r["ultra"] < 0.01)
    w("koniec (0,5 s)", f"{r['koniec']:.1f} dBFS", r["koniec"] < -40)
    print(f"\n{sum(ok)}/{len(ok)} miar w normie · render {time.time() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
