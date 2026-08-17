"""Klub II — poprawki z odsłuchu Janka, każda zmierzona na 15 nowych referencjach.

Zarzuty i co pokazał pomiar (katalog „Lekcja nr6": Fred again.., Skrillex/PEEKABOO,
HAAi, O'Flynn, Sister Zo, Silcrow, Anish Kumar, Riko Dan, Era4, Jasmin i in.):

  1. „duży szum" — POTWIERDZONE. Płaskość widmowa w 2–8 kHz: moje 0,82 przy
     zakresie referencji 0,64–0,79 (1 = biały szum, 0 = czysty ton). Hi-haty
     były czystym szumem pasmowym. Teraz mają dominujący szkielet tonalny:
     sześć prążków o Q = 90 plus tylko 25 % szumu.
  2. „słaby bass" — poziomy BYŁY w zakresie (30–60 Hz −3,4 dB, 60–120 −6,9),
     więc „słaby" znaczyło BEZ CHARAKTERU: czysty sinus nie ma czym zabrzmieć
     na małym głośniku i nie porusza się. Teraz sub (sinus) + osobna warstwa
     Reese (dwie rozstrojone piły przez filtr rezonansowy) + ruchoma linia
     z glissandami zamiast jednej nuty na cztery takty.
  3. „midy i harmonie bez życia" — ruch poziomu środka 3,3 dB przy medianie
     referencji 3,9. Harmonia stała. Teraz: sztaby akordowe na offbeatach
     z ruchomym filtrem, progresja co 2 takty zamiast co 4, kontrmelodia.
  4. „percussion bardziej zróżnicowane" — POTWIERDZONE i to była też
     przyczyna wrażenia szumu: mediana barwy uderzeń 6292 Hz przy zakresie
     referencji 2697–5921, rozrzut 1058 przy medianie 1386. WSZYSTKO, co
     uderzało, było wysokie. Teraz paleta w środku pasma: tomy, kongi,
     rim, klawes, plus trzy różne werble.

Poprzednia wersja (klub.py) trafiała w profil głośnościowy co do dziesiątej,
ale profil to nie wszystko — te cztery rzeczy słychać, a tamte miary ich
nie widziały. Stąd nowe miary: płaskość widmowa per pasmo, bogactwo
harmoniczne basu, ruch poziomu i barwy środka, rozrzut barwy uderzeń.

Utwór celowany w ZMIERZONY profil referencji.

Nie folktronika. Punktem odniesienia jest dwanaście produkcji z półki
Burial / Jamie xx / Bicep / Tessela / Boys Noize / Parallx / Detlef /
Anthony Naples / Brenda / Les Petits Pilous / Bodhi. Z tych plików NIE
POCHODZI ANI JEDNA PRÓBKA — wyciągnięto z nich wyłącznie liczby (tempo,
głośność, dynamika, balans pasm, gęstość zdarzeń, korelacja), zgodnie
z CORPUS_ETHICS.md: cechy zostają, audio nigdy nie jest redystrybuowane.

ZMIERZONY PROFIL CELU (mediana z 12, w nawiasie zakres):
  BPM             124,6   (85,5 … 134,3)  → wybrane 128, środek klastra klubowego
  głośność        −14,1   (−16,1 … −12,0) LUFS
  dynamika          5,5   (3,5 … 11,0) dB
  crest            10,2   (8,8 … 12,1) dB
  gęstość zdarzeń   5,05  (4,2 … 6,0) na sekundę
  korelacja L/R     0,93  (0,32 … 0,99);  dół 0,99
  pasma [dB]: sub −4,0 · bas −5,5 · dół −7,2 · środek −12,9 · góra −14,3
              · powietrze −21,4

CZEGO NAUCZYŁ POMIAR — trzy rzeczy wbrew intuicji, każda zmierzona na
poprzednim utworze (folktronika.wav) w porównaniu z tą dwunastką:
  1. GĘSTOŚĆ. Miałem 11,2 zdarzenia na sekundę, referencje mają 4,2–6,0.
     Muzyka klubowa z górnej półki jest RZADSZA, nie bogatsza. Przestrzeń
     między uderzeniami jest instrumentem.
  2. PION. Miałem dynamikę 14,9 dB i crest 15,5 dB, referencje 3,5–11,0
     i 8,8–12,1. Tam pracuje realna kompresja szyny, nie samo tanh.
  3. BARWA. Miałem środek +5,6 dB i górę +7,3 dB ponad medianę referencji.
     Te miksy są CIEMNE i oparte na dole; góra jest detalem, nie treścią.

Rytm: 2-step / broken beat ze swingiem na szesnastkach (Burial, Jamie xx),
a nie four-on-the-floor. Stopa nie stoi na każdej ćwiartce — stąd bierze
się miejsce na sub i na ciszę.

Silnik syntezy jest ten sam, co w poprzednich utworach (faza całkowana dla
tonów, losowa dla szumu, własna faza startowa per głos, modulacje z pamięci,
dół w mono, humanizacja u źródła, ADR-005). Nowe są tylko dwie rzeczy,
których poprzednio brakowało: prawdziwy kompresor szyny i celowanie
w zmierzony profil zamiast w wyobrażenie.
"""

from __future__ import annotations

import argparse
import pathlib
import time

import numpy as np
import soundfile as sf
from scipy.ndimage import minimum_filter1d
from scipy.signal import butter, iirpeak, lfilter, oaconvolve, sosfilt, sosfiltfilt, tf2sos

SR = 96000
BPM = 128.0
BEAT = 60.0 / BPM                  # 0,46875 s
BAR = 4 * BEAT                     # 1,875 s
S16 = BEAT / 4                     # 0,1171875 s
N_BARS = 128
TOTAL = N_BARS * BAR               # 240,0 s dokładnie
N = int(round(TOTAL * SR))
SWING = 0.14                       # 16,4 ms — garage'owy shuffle na nieparzystych

STEMY = ("KICK", "SUB", "BASS", "DRUMS", "PERC", "HATS", "STABS",
         "CHORDS", "LEAD", "TEXTURES")

# strój naturalny od D (jak poprzednio), tonacja molowa: D, F, G, A, C
A4 = 439.0
D3 = A4 * (2 / 3) / 2
JI = {"D": 1.0, "E": 9 / 8, "F": 6 / 5, "G": 4 / 3, "A": 3 / 2, "Bb": 8 / 5,
      "C": 16 / 9}
_ROZ: dict[tuple, float] = {}


def ton(kl, okt):
    if (kl, okt) not in _ROZ:
        r = np.random.default_rng(abs(hash((kl, okt))) & 0xFFFF)
        _ROZ[(kl, okt)] = float(np.clip(r.normal(0, 3.5), -8, 8))
    return D3 * JI[kl] * 2.0 ** (okt - 3) * 2 ** (_ROZ[(kl, okt)] / 1200)


def ss(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def szum(n, rng):
    """Zawsze ścinany na 18 kHz: przy 96 kHz biały ma 58% mocy >20 kHz."""
    return sosfilt(butter(8, 18000 / (SR / 2), btype="low", output="sos"),
                   rng.standard_normal(n))


def bar_t(b):
    return b * BAR


# ────────────────────────── instrumenty ──────────────────────────
def kick(f0=125.0, f1=45.0, tau_p=0.024, tau_a=0.075, dur=0.60, drive=2.1,
         seed=0):
    """Stopa klubowa: krótka, gruba, z klikiem. FAZA CAŁKOWANA."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / tau_p)
    ph = np.cumsum(2 * np.pi * f / SR, dtype=np.float64)
    ph -= ph[0]
    body = np.sin(ph) * (1 - np.exp(-t / 0.0009)) * np.exp(-t / tau_a)
    kl = sosfilt(butter(2, 1600 / (SR / 2), btype="high", output="sos"),
                 szum(n, rng)) * np.exp(-t / 0.0006)
    x = np.tanh(drive * (body + 0.22 * kl)) / np.tanh(drive)
    x = sosfilt(butter(2, 24 / (SR / 2), btype="high", output="sos"), x)
    return (x / (np.abs(x).max() + 1e-12)).astype(np.float32)


def sub_nuta(f0, dur, seed=0):
    """Sub: prawie czysty sinus. Nic szumowego obok — ERB(50 Hz) ≈ 30 Hz."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    ph = 2 * np.pi * f0 * t
    # warstwa uderzenia oktawę wyżej: sam sub (36–49 Hz) zostawia pasmo
    # 60–120 Hz puste, a referencje mają tam −5,5 dB. Druga harmoniczna
    # z własną, krótszą obwiednią to klasyczny podział sub + bas.
    x = np.sin(ph) + 0.62 * np.sin(2 * ph + 0.6) * np.exp(-t / 0.10) \
        + 0.12 * np.sin(3 * ph + 1.1) * np.exp(-t / 0.045)
    env = (1 - np.exp(-t / 0.008)) * np.clip((dur - t) / 0.06, 0, 1)
    x = np.tanh(1.25 * x * env) / np.tanh(1.25)
    x = sosfilt(butter(4, 24 / (SR / 2), btype="high", output="sos"), x)
    return (x / (np.abs(x).max() + 1e-12)).astype(np.float32)


def reese(f0, dur, seed=0, det=0.018):
    """Reese: dwie rozstrojone piły przez filtr rezonansowy. To ona sprawia,
    że bas SŁYCHAĆ na małym głośniku — sam sinus jest tylko czuć."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    K = max(4, int(2600 / f0))
    for d in (-det, +det):
        f = f0 * (1 + d)
        ph = 2 * np.pi * f * t + rng.uniform(0, 6.28)
        y += sum(np.sin(k * ph) / k for k in range(1, K + 1))
    fc = 220 + 340 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * t))
    ban = np.exp(np.linspace(np.log(160), np.log(1400), 7))
    Y = [sosfilt(butter(2, f / (SR / 2), btype="low", output="sos"), y) for f in ban]
    u = np.interp(np.log(np.clip(fc, ban[0], ban[-1])), np.log(ban), np.arange(7))
    i0 = np.clip(u.astype(int), 0, 5)
    w = u - i0
    out = np.zeros(n)
    for i in range(6):
        msk = i0 == i
        if msk.any():
            out[msk] = Y[i][msk] * (1 - w[msk]) + Y[i + 1][msk] * w[msk]
    out *= (1 - np.exp(-t / 0.010)) * np.clip((dur - t) / 0.07, 0, 1)
    out = np.tanh(1.9 * out) / np.tanh(1.9)
    return (out / (np.abs(out).max() + 1e-12)).astype(np.float32)


def sztaba(f_list, dur=0.42, seed=0):
    """Sztaba akordowa: krótkie, filtrowane uderzenie akordu — to ona daje
    życie środkowi. Ruch poziomu środka wychodził 3,3 dB przy medianie 3,9."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for f0 in f_list:
        ph = 2 * np.pi * f0 * t + rng.uniform(0, 6.28)
        y += sum(np.sin(k * ph) / k ** 1.15 for k in range(1, 9))
    fc = 900 + 2600 * np.exp(-t / 0.11)
    ban = np.exp(np.linspace(np.log(500), np.log(6000), 7))
    Y = [sosfilt(butter(2, f / (SR / 2), btype="low", output="sos"), y) for f in ban]
    u = np.interp(np.log(np.clip(fc, ban[0], ban[-1])), np.log(ban), np.arange(7))
    i0 = np.clip(u.astype(int), 0, 5)
    w = u - i0
    out = np.zeros(n)
    for i in range(6):
        msk = i0 == i
        if msk.any():
            out[msk] = Y[i][msk] * (1 - w[msk]) + Y[i + 1][msk] * w[msk]
    out *= np.exp(-t / 0.16) * (1 - np.exp(-t / 0.003))
    return (out / (np.abs(out).max() + 1e-12)).astype(np.float32)


def werbel(dur=0.34, seed=0, jasny=True):
    """Werbel/rimshot: szum + dwa mody membrany, każdy z własną fazą."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    z = szum(n, rng)
    lo, hi = (220, 9000) if jasny else (180, 5200)
    y = sosfilt(butter(4, [lo / (SR / 2), hi / (SR / 2)], btype="band",
                       output="sos"), z) * np.exp(-t / 0.040)
    for f, a, tau in ((185.0, 0.45, 0.028), (331.0, 0.30, 0.019)):
        y += a * np.sin(2 * np.pi * f * t + rng.uniform(0, 2 * np.pi)) \
            * np.exp(-t / tau)
    spr = np.zeros(n)                                   # „sprężyna"
    for _ in range(12):
        d = int(rng.uniform(0.003, 0.028) * SR)
        spr[d:] += szum(n - d, rng) * np.exp(-t[:n - d] / 0.02)
    y += 0.10 * sosfilt(butter(4, [3000 / (SR / 2), 7000 / (SR / 2)],
                               btype="band", output="sos"), spr)
    y *= 1 - np.exp(-t / 0.0004)
    return (y / (np.abs(y).max() + 1e-12)).astype(np.float32)


def hat(otwarty=False, seed=0):
    """Metaliczność = siedem wąskich prążków o niewspółmiernych odstępach."""
    rng = np.random.default_rng(seed)
    t60 = 0.26 if otwarty else 0.035
    n = int((t60 * 1.6 + 0.01) * SR)
    t = np.arange(n) / SR
    z = szum(n, rng)
    y = np.zeros(n)
    war = 1 + rng.normal(0, 0.015)
    # SZKIELET TONALNY: sinusy o niewspółmiernych odstępach niosą barwę,
    # szum tylko ją brudzi. Poprzednio było odwrotnie i płaskość widmowa
    # w 2–8 kHz wychodziła 0,82 przy zakresie referencji 0,64–0,79.
    tt = np.arange(n) / SR
    for f, a in ((3180, 1.0), (4210, .85), (5310, .7), (6790, .55),
                 (8330, .4), (10250, .3)):
        fr = f * war
        if fr < SR / 2 * 0.95:
            y += a * np.sin(2 * np.pi * fr * tt + rng.uniform(0, 2 * np.pi))
    y = 0.88 * y / (np.abs(y).max() + 1e-12) + 0.12 * z
    y = sosfilt(butter(2, 3000 / (SR / 2), btype="high", output="sos"), y)
    y *= (1 - np.exp(-t / 0.0003)) * np.exp(-6.9078 * t / t60)
    return (y / (np.abs(y).max() + 1e-12)).astype(np.float32)


def tom(f0, dur=0.55, seed=0):
    """Tom: membrana z opadającą wysokością. Barwa ~250–600 Hz."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f0 * (1 + 0.35 * np.exp(-t / 0.045))
    ph = np.cumsum(2 * np.pi * f / SR, dtype=np.float64)
    y = np.sin(ph) + 0.42 * np.sin(1.59 * ph + rng.uniform(0, 6.28)) \
        + 0.18 * np.sin(2.14 * ph + rng.uniform(0, 6.28))
    y *= np.exp(-t / 0.13) * (1 - np.exp(-t / 0.0008))
    y += 0.13 * szum(n, rng) * np.exp(-t / 0.004)
    return (y / (np.abs(y).max() + 1e-12)).astype(np.float32)


def konga(f0, dur=0.30, seed=0, otwarta=True):
    """Konga/bongo: mody skóry, barwa ~700–2000 Hz."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    tau = 0.11 if otwarta else 0.028
    for r_, a, td in ((1.0, 1.0, tau), (1.5, .55, tau * .6),
                      (2.0, .30, tau * .45), (2.7, .16, tau * .3)):
        y += a * np.sin(2 * np.pi * f0 * r_ * t + rng.uniform(0, 6.28)) \
            * np.exp(-t / td)
    y += 0.22 * sosfilt(butter(2, [1200 / (SR / 2), 7000 / (SR / 2)],
                               btype="band", output="sos"), szum(n, rng)) \
        * np.exp(-t / 0.0035)
    y *= 1 - np.exp(-t / 0.0005)
    return (y / (np.abs(y).max() + 1e-12)).astype(np.float32)


def klawes(f0=2100.0, dur=0.12, seed=0):
    """Klawes/rim: krótki, drewniany, silnie tonalny — obniża barwę perkusji."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = (np.sin(2 * np.pi * f0 * t) + 0.5 * np.sin(2 * np.pi * f0 * 2.76 * t
                                                   + rng.uniform(0, 6.28)))
    y *= np.exp(-t / 0.020) * (1 - np.exp(-t / 0.0002))
    y += 0.10 * szum(n, rng) * np.exp(-t / 0.0015)
    return (y / (np.abs(y).max() + 1e-12)).astype(np.float32)


def szejker(dur=0.09, seed=0):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = sosfilt(butter(4, [5000 / (SR / 2), 13000 / (SR / 2)], btype="band",
                       output="sos"), szum(n, rng))
    y *= np.exp(-t / 0.018) * (1 - np.exp(-t / 0.002))
    return (y / (np.abs(y).max() + 1e-12)).astype(np.float32)


def pad_glos(f0, dur, seed=0, K=7):
    """Ciemny pad: faza całkowana, własna faza startowa, grubość z pamięci."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    ph = np.arange(n, dtype=np.float64) * (f0 / SR)
    y = np.zeros(n)
    ns = max(2, int(dur * 30))
    for k in range(1, K + 1):
        w = np.interp(np.arange(n), np.linspace(0, n, ns),
                      rng.standard_normal(ns))
        w /= np.abs(w).max() + 1e-12
        y += k ** -1.55 * (1 + 0.07 * w) * np.sin(2 * np.pi * (k * ph + rng.uniform(0, 1)))
    return (y / (np.abs(y).max() + 1e-12)).astype(np.float32)


def ks(f0, dur, t60=1.1, s=0.30, seed=0):
    """Karplus–Strong z kompensacją opóźnienia filtra pętli (< 0,3 centa)."""
    w0 = 2 * np.pi * f0 / SR
    H = (1 - s) + s * np.exp(-1j * w0)
    L = int(np.floor(SR / f0 + np.angle(H) / w0)) - 1
    if L < 5:
        return np.zeros(int(dur * SR), np.float32)
    frac = (SR / f0 + np.angle(H) / w0) - L
    eta = (1.0 - frac) / (1.0 + frac)
    rng = np.random.default_rng(seed)
    n_out = int(dur * SR)
    y = np.zeros(n_out + L + 4)
    e = szum(L, rng)
    e -= e.mean()
    e *= np.sin(np.pi * np.arange(L) / L) ** 0.35
    y[:L] = e / (np.abs(e).max() + 1e-12)
    g = min(10 ** (-3.0 / (f0 * t60)) / abs(H), 0.9999 / abs(H))
    zi = np.zeros(1)
    pos, prev = L, 0.0
    while pos < len(y):
        m = min(L, len(y) - pos)
        a = y[pos - L: pos - L + m]
        b = np.empty(m)
        b[0] = prev
        b[1:] = a[:m - 1]
        blk = g * ((1 - s) * a + s * b)
        out, zi = lfilter([eta, 1.0], [1.0, eta], blk, zi=zi)
        prev = a[m - 1]
        y[pos: pos + m] = out
        pos += m
    y = y[:n_out] * (1 - np.exp(-np.arange(n_out) / (0.0008 * SR)))
    return (y / (np.abs(y).max() + 1e-12)).astype(np.float32)


# ────────────────────────── mikroczas ──────────────────────────
# stem: (sigma, bias, sprzężenie z dryfem) — KICK jest kotwicą (sigma 0)
CZAS = {"KICK": (0.000, 0.000, 0.0), "SUB": (0.002, -0.003, 0.3),
        "DRUMS": (0.004, +0.005, 0.3), "HATS": (0.002, 0.000, 0.2),
        "CHORDS": (0.006, -0.012, 0.5), "LEAD": (0.007, +0.002, 1.0),
        "TEXTURES": (0.020, 0.000, 0.0)}
LIMIT = 0.25 * S16


def wstaw(dst, t, sig, gain=1.0, pan=0.0):
    i0 = int(t * SR)
    if i0 < 0 or i0 >= len(dst):
        return
    m = min(len(sig), len(dst) - i0)
    if m <= 0:
        return
    th = (np.clip(pan, -1, 1) + 1) * np.pi / 4
    dst[i0:i0 + m, 0] += sig[:m] * (gain * np.cos(th))
    dst[i0:i0 + m, 1] += sig[:m] * (gain * np.sin(th))


# ── forma: 128 taktów. Warstwy wchodzą osobno, nigdy dwie naraz ──
def aktywne(b):
    return {"kick": 8 <= b < 58 or 62 <= b < 118,
            "sub": 12 <= b < 58 or 62 <= b < 122,
            "drums": 20 <= b < 58 or 62 <= b < 118,
            "hats": 4 <= b < 60 or 61 <= b < 124,
            "chords": True,
            "lead": 32 <= b < 56 or 68 <= b < 116,
            "tex": True}


# 2-step: stopa NIE na każdej ćwiartce — stąd miejsce na sub i ciszę
WZ_KICK = [0, 10, 18, 24]            # szesnastki w takcie (2 takty = 32)
WZ_WERBEL = [8, 24]                  # klasyczne 2 i 4
AKORDY = [("D", 1), ("D", 1), ("F", 1), ("C", 1),
          ("D", 1), ("Bb", 1), ("G", 1), ("A", 1)]   # zmiana co 2 takty
WOLOWANIA = {"D": [("D", 3), ("F", 3), ("A", 3), ("D", 4)],
             "F": [("F", 3), ("A", 3), ("C", 4), ("F", 4)],
             "C": [("C", 3), ("E", 3), ("G", 3), ("C", 4)],
             "G": [("G", 2), ("Bb", 3), ("D", 4), ("G", 4)]}
FRAZA_LEAD = [(0, ("A", 4)), (6, ("D", 5)), (14, ("C", 5)), (22, ("A", 4)),
              (26, ("F", 4))]


def buduj(rng):
    buf = {s: np.zeros((N, 2), np.float32) for s in STEMY}
    stat = {"zdarzenia": 0, "przyciete": 0}
    dt_ax = np.arange(0, TOTAL + 1, 0.05)
    dr = np.interp(dt_ax, np.linspace(0, TOTAL, 50), rng.standard_normal(50))
    dryf = dr / (np.abs(dr).max() + 1e-12) * 0.012

    def czas(stem, t_nom):
        sg, bias, k = CZAS[stem]
        d = k * float(np.interp(t_nom, dt_ax, dryf)) + bias
        if sg:
            d += rng.normal(0, sg)
        if abs(d) > LIMIT:
            stat["przyciete"] += 1
            d = np.clip(d, -LIMIT, LIMIT)
        return t_nom + d

    def sw(s16):
        return SWING * S16 if s16 % 2 else 0.0

    kick_t = []
    for b in range(N_BARS):
        akt = aktywne(b)
        t_b = bar_t(b)
        par = b % 2                                   # pozycja w parze taktów

        if akt["kick"]:
            for s16 in WZ_KICK:
                if s16 // 16 != par:
                    continue
                loc = s16 % 16
                if b % 8 == 7 and loc == 24 % 16:
                    continue
                t0 = czas("KICK", t_b + loc * S16)
                wstaw(buf["KICK"], t0, kick(seed=int(rng.integers(1 << 30))),
                      gain=0.95 if loc == 0 else 0.86)
                kick_t.append(t0)
                stat["zdarzenia"] += 1

        if akt["sub"]:                                 # sub gra MIĘDZY stopami
            kl, ok = AKORDY[(b // 2) % 8]
            f0 = ton(kl, ok)
            # warstwa Reese: to ona sprawia, że bas SŁYCHAĆ, nie tylko czuć
            for s16, dl in ((2, 3), (7, 2), (11, 4), (20, 3), (26, 5)):
                if s16 // 16 != par or rng.random() < 0.25:
                    continue
                loc = s16 % 16
                okt = 1 if rng.random() < 0.22 else 0
                wstaw(buf["BASS"],
                      czas("SUB", t_b + loc * S16 + sw(loc)),
                      reese(f0 * 2 ** okt, dl * S16 + 0.10,
                            seed=int(rng.integers(1 << 30))),
                      gain=0.55 * rng.uniform(0.85, 1.05))
                stat["zdarzenia"] += 1
            for s16 in (4, 12, 20, 28):
                if s16 // 16 != par:
                    continue
                if rng.random() < 0.18:
                    continue
                loc = s16 % 16
                wstaw(buf["SUB"], czas("SUB", t_b + loc * S16 + sw(loc)),
                      sub_nuta(f0, 0.42, seed=int(rng.integers(1 << 30))),
                      gain=0.80 * rng.uniform(0.9, 1.0))
                stat["zdarzenia"] += 1

        if akt["drums"]:
            for s16 in WZ_WERBEL:
                if s16 // 16 != par:
                    continue
                loc = s16 % 16
                wstaw(buf["DRUMS"], czas("DRUMS", t_b + loc * S16),
                      werbel(seed=int(rng.integers(1 << 30)),
                             jasny=(b % 4 != 3)),
                      gain=0.62, pan=rng.uniform(-0.12, 0.12))
                stat["zdarzenia"] += 1
            if rng.random() < 0.35:                    # duch, rzadko
                loc = int(rng.choice([3, 7, 11, 14]))
                wstaw(buf["DRUMS"], czas("DRUMS", t_b + loc * S16 + sw(loc)),
                      werbel(0.16, seed=int(rng.integers(1 << 30)), jasny=False),
                      gain=0.16, pan=rng.uniform(-0.5, 0.5))
                stat["zdarzenia"] += 1

        if akt["hats"]:                                # ÓSEMKI, nie szesnastki
            for loc in range(0, 16, 2):
                if loc == 0 and akt["kick"]:
                    continue                            # nie dubluj stopy
                otw = (loc == 12 and b % 4 == 3)
                wstaw(buf["HATS"], czas("HATS", t_b + loc * S16 + sw(loc)),
                      hat(otwarty=otw, seed=int(rng.integers(1 << 30))),
                      gain=0.30 * (1.0 if loc % 4 == 0 else 0.62),
                      pan=0.45 * np.sin(2 * np.pi * t_b / 11.3))
                stat["zdarzenia"] += 1
            if rng.random() < 0.30:
                loc = int(rng.choice([5, 9, 13]))
                wstaw(buf["HATS"], czas("HATS", t_b + loc * S16 + sw(loc)),
                      szejker(seed=int(rng.integers(1 << 30))),
                      gain=0.13, pan=rng.uniform(-0.6, 0.6))
                stat["zdarzenia"] += 1

        if akt["drums"]:      # PERKUSJA W ŚRODKU PASMA — mediana barwy uderzeń
            wzor = [(3, "konga"), (6, "klawes"), (10, "konga"), (13, "tom"),
                    (14, "klawes"), (9, "tom"), (5, "konga"), (11, "klawes")]
            for loc, rodzaj in wzor:
                if rng.random() > 0.29:
                    continue
                sd = int(rng.integers(1 << 30))
                if rodzaj == "tom":
                    sig = tom(float(rng.choice([88, 110, 132, 165])), seed=sd)
                    g, pn = 0.34, rng.uniform(-0.4, 0.4)
                elif rodzaj == "konga":
                    sig = konga(float(rng.choice([196, 262, 330, 392])), seed=sd,
                                otwarta=rng.random() < 0.6)
                    g, pn = 0.26, rng.uniform(-0.55, 0.55)
                else:
                    sig = klawes(float(rng.choice([1600, 2100, 2600])), seed=sd)
                    g, pn = 0.18, rng.uniform(-0.65, 0.65)
                wstaw(buf["PERC"], czas("DRUMS", t_b + loc * S16 + sw(loc)),
                      sig, gain=g * rng.uniform(0.7, 1.05), pan=pn)
                stat["zdarzenia"] += 1

        if akt["lead"]:       # SZTABY: życie środka, offbeatowe ósemki
            kl, ok = AKORDY[(b // 2) % 8]
            akord = [ton(kl, ok + 3), ton(kl, ok + 3) * 6 / 5,
                     ton(kl, ok + 3) * 3 / 2, ton(kl, ok + 4)]
            for loc in (2, 6, 10, 14):
                if rng.random() > 0.55:
                    continue
                wstaw(buf["STABS"], czas("CHORDS", t_b + loc * S16 + sw(loc)),
                      sztaba(akord, seed=int(rng.integers(1 << 30))),
                      gain=0.30 * rng.uniform(0.8, 1.1),
                      pan=rng.uniform(-0.35, 0.35))
                stat["zdarzenia"] += 1

        if b % 4 == 0:                                 # pad: cztery takty
            kl, _ = AKORDY[(b // 2) % 8]
            for i, (k2, o2) in enumerate(WOLOWANIA[kl]):
                dl = 4 * BAR + 1.8
                g = pad_glos(ton(k2, o2), dl, seed=int(rng.integers(1 << 30)))
                t = np.arange(len(g)) / SR
                env = np.minimum(t / 0.45, 1) ** 1.3 * np.clip((dl - t) / 1.6, 0, 1)
                env *= 0.78 + 0.22 * np.sin(2 * np.pi * 0.037 * t + i)
                wstaw(buf["CHORDS"], czas("CHORDS", t_b),
                      (g * env).astype(np.float32),
                      gain=0.30 / (1 + 0.32 * i), pan=-0.4 + i * 0.27)

        if akt["lead"] and b % 4 == 2:                 # lead: RZADKO, po 4 takty
            for s16, (kl, ok) in FRAZA_LEAD:
                if rng.random() < 0.25:
                    continue
                loc = s16 % 16
                wstaw(buf["LEAD"], czas("LEAD", t_b + loc * S16 + sw(loc)),
                      ks(ton(kl, ok), 1.6, t60=1.0,
                         seed=int(rng.integers(1 << 30))),
                      gain=0.34 * rng.uniform(0.85, 1.05),
                      pan=rng.uniform(-0.3, 0.3))
                stat["zdarzenia"] += 1

    # ── TEXTURES: kurz winylowy, powietrze, dalekie plamy ──
    tex = buf["TEXTURES"]
    b_p, a_p = ([0.049922035, -0.095993537, 0.050612699, -0.004408786],
                [1, -2.494956002, 2.017265875, -0.5221894])
    pow_ = lfilter(b_p, a_p, rng.standard_normal(N))
    pow_ = sosfilt(butter(2, [1800 / (SR / 2), 15000 / (SR / 2)], btype="band",
                          output="sos"), pow_)
    pow_ /= np.abs(pow_).max() + 1e-12
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * np.arange(N) / SR / 47.3)
    tex[:, 0] += (pow_ * lfo * 0.022).astype(np.float32)
    tex[:, 1] += (np.roll(pow_, 1301) * lfo * 0.022).astype(np.float32)
    for _ in range(int(TOTAL * 0.6)):                  # trzaski — jeszcze mniej
        i = int(rng.uniform(0, N - 400))
        d = int(rng.uniform(30, 240))
        tex[i:i + d, int(rng.integers(0, 2))] += (
            rng.standard_normal(d) * np.exp(-np.arange(d) / 40) * 0.03)
    for b in range(0, N_BARS, 8):                      # dalekie plamy pada
        kl, ok = AKORDY[(b // 2) % 8]
        wstaw(tex, czas("TEXTURES", bar_t(b) + rng.uniform(0, BAR)),
              ks(ton(kl, ok + 2), 2.4, t60=1.8, seed=int(rng.integers(1 << 30))),
              gain=0.06, pan=rng.uniform(-0.75, 0.75))
    tex += 0.25 * tex.mean(axis=1, keepdims=True)      # inaczej korelacja ≈ 0
    return buf, stat, np.array(kick_t)


# ────────────────────────── tor sygnału ──────────────────────────
def ir_pokoj(t60=2.0, seed=3, pre_ms=18.0):
    rng = np.random.default_rng(seed)
    n = int(t60 * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-6.9078 * t / t60)[:, None]
    ir *= (t[:, None] / 0.03).clip(0, 1) ** 0.6
    mix = np.linspace(0, 1, n)[:, None] ** 0.7
    ir = ir * (1 - mix) + sosfilt(butter(2, 4200 / (SR / 2), btype="low",
                                         output="sos"), ir, axis=0) * mix
    for d_ms, a in ((9, .5), (14, .4), (21, .32), (29, .24), (41, .17)):
        ir[int(d_ms / 1000 * SR)] += a * rng.choice([-1.0, 1.0], 2)
    ir = np.vstack([np.zeros((int(pre_ms / 1000 * SR), 2)), ir])[:n]
    ir /= np.sqrt((ir ** 2).sum(axis=0)).max() + 1e-12
    return ir.astype(np.float32)


def kompresor(x, prog_db=-20.0, ratio=3.2, atk=0.008, rel=0.110, fs_det=1000):
    """Kompresor stemu. Uwaga: próg MUSI leżeć nad poziomem ciągłym, inaczej
    dławi to, co trzymane, a transient i tak ucieka — zmierzono wzrost crestu
    z 21,3 na 23,1 dB przy progu pod sygnałem ciągłym."""
    m = np.abs(x).max(axis=1)
    krok = SR // fs_det
    det = np.maximum.reduceat(m, np.arange(0, len(m), krok))
    cel = np.minimum(0.0, (prog_db - 20 * np.log10(det + 1e-9)) * (1 - 1 / ratio))
    ka = 1 - np.exp(-1.0 / (atk * fs_det))
    kr = 1 - np.exp(-1.0 / (rel * fs_det))
    g = np.empty_like(cel)
    acc = 0.0
    for i, c in enumerate(cel):
        acc += (c - acc) * (ka if c < acc else kr)
        g[i] = acc
    lin = 10 ** (np.interp(np.arange(len(m)), np.arange(len(g)) * krok, g) / 20)
    return (x * lin[:, None]).astype(np.float32)


def limiter(x, sufit=0.891, look=0.0015, rel=0.060, fs_det=2000):
    """Limiter z WYPRZEDZENIEM: wzmocnienie schodzi ZANIM przyjdzie szczyt.

    Bez wyprzedzenia żaden atak nie zdąży — dlatego kompresor z atakiem 5 ms
    podnosił crest zamiast go obniżać. Tu wymagane wzmocnienie liczone jest
    per blok, brane jako MINIMUM w oknie wyprzedzenia, a wracać wolno mu
    tylko z zadaną stałą powrotu.
    """
    m = np.abs(x).max(axis=1)
    krok = max(1, SR // fs_det)
    szczyt = np.maximum.reduceat(m, np.arange(0, len(m), krok))
    wym = np.minimum(1.0, sufit / (szczyt + 1e-12))
    L = max(1, int(look * fs_det))
    wym = minimum_filter1d(wym, size=2 * L + 1, mode="nearest")
    kr = 1 - np.exp(-1.0 / (rel * fs_det))
    g = np.empty_like(wym)
    acc = 1.0
    for i, w in enumerate(wym):
        acc = w if w < acc else acc + (w - acc) * kr
        g[i] = acc
    lin = np.interp(np.arange(len(m)), np.arange(len(g)) * krok, g)
    y = (x * lin[:, None]).astype(np.float32)
    sz = np.abs(y).max()
    return y if sz <= sufit else (y * (sufit / sz)).astype(np.float32)


def _lufs(x):
    m = x.mean(axis=1).astype(np.float64)
    k = sosfilt(butter(2, 120 / (SR / 2), btype="high", output="sos"), m)
    k = k + 1.26 * sosfilt(butter(2, [1000 / (SR / 2), 12000 / (SR / 2)],
                                  btype="band", output="sos"), k)
    b = int(0.4 * SR)
    p = np.array([v for v in ((k[i:i + b] ** 2).mean()
                              for i in range(0, len(k) - b, b // 2)) if v > 0])
    g = -0.691 + 10 * np.log10(p)
    return float(-0.691 + 10 * np.log10(p[g > g.max() - 20].mean()))


def maksymalizuj(x, cel_lufs=-14.0, sufit=0.891, iteracje=6):
    """Wzmocnienie wejściowe + limiter, iterowane do zadanej głośności —
    tak działa limiter masteringowy. Referencje siedzą na −12…−16 LUFS."""
    for _ in range(iteracje):
        obecnie = _lufs(x)
        if abs(obecnie - cel_lufs) < 0.15:
            break
        x = limiter((x * 10 ** ((cel_lufs - obecnie) / 20)).astype(np.float32),
                    sufit=sufit)
    return x


MIX = {
    "KICK":     (26, 8000, 0.00, 0.00, -18.0, 13.0),
    "BASS":     (45, 1050, 0.26, 0.03, -20.5, 12.0),
    "PERC":     (110, 9000, 0.15, 0.16, -22.5, 15.0),
    "STABS":    (240, 7000, 0.22, 0.24, -23.0, 14.0),
    "SUB":      (22, 260, 0.05, 0.00, -16.0, 12.0),
    "DRUMS":    (150, 16000, 0.12, 0.10, -24.0, 14.0),
    "HATS":     (3000, 15000, 0.00, 0.08, -32.0, 14.0),
    "CHORDS":   (140, 6500, 0.20, 0.26, -21.5, 14.0),
    "LEAD":     (260, 12000, 0.15, 0.30, -29.0, 14.0),
    "TEXTURES": (200, 13000, 0.05, 0.22, -37.0, 16.0),
}


def zmiksuj(buf, ir, kick_t, zapisz, out):
    if len(kick_t):                                    # ducking deterministyczny
        t_ax = np.arange(N) / SR
        duck = np.ones(N, np.float32)
        for tk in kick_t:
            i0, i1 = int(tk * SR), min(N, int(tk * SR) + int(0.28 * SR))
            if i1 > i0:
                dt = t_ax[i0:i1] - tk
                duck[i0:i1] *= 1 - 0.42 * np.exp(-dt / 0.070) * (1 - np.exp(-dt / 0.008))
        for s in ("SUB", "BASS", "CHORDS", "TEXTURES", "STABS"):
            buf[s] *= duck[:, None]

    mix = np.zeros((N, 2), np.float32)
    stemy = {}
    for s in STEMY:
        x = buf[s]
        hp, lp, drv, wet, cel, krest = MIX[s]
        if hp:
            x = sosfilt(butter(2, hp / (SR / 2), btype="high", output="sos"),
                        x, axis=0).astype(np.float32)
        if lp:
            x = sosfilt(butter(4, lp / (SR / 2), btype="low", output="sos"),
                        x, axis=0).astype(np.float32)
        if drv:
            x = (np.tanh(x * (1 + drv)) / np.tanh(1 + drv)).astype(np.float32)
        if wet > 0:
            send = sosfilt(butter(2, 200 / (SR / 2), btype="high", output="sos"),
                           x, axis=0)                  # sub nigdy w pogłos
            w = np.empty_like(x)
            for ch in range(2):
                w[:, ch] = oaconvolve(send[:, ch], ir[:, ch])[:N]
            w *= np.abs(x).max() / (np.abs(w).max() + 1e-12)
            x = (x + w * wet).astype(np.float32)
        if s in ("KICK", "SUB"):
            x = np.repeat(x.mean(axis=1, keepdims=True), 2, axis=1)
        # kompresja stemu: rzadkie uderzenia mają crest 26–32 dB, więc przy
        # balansie na RMS ich szczyty lądują powyżej zera. Realizator ściska
        # perkusję ZANIM ją zbalansuje — tu tak samo, do zadanego crestu.
        rms = float(np.sqrt((x.mean(axis=1) ** 2).mean())) + 1e-12
        x = (x / rms * 0.1).astype(np.float32)          # RMS = −20 dBFS
        cr = 20 * np.log10(np.abs(x).max() / 0.1 + 1e-12)
        if cr > krest:
            x = kompresor(x, prog_db=-20.0 + krest - 6.0, ratio=6.0,
                          atk=0.002, rel=0.080)
        rms = float(np.sqrt((x.mean(axis=1) ** 2).mean())) + 1e-12
        x = (x * (10 ** (cel / 20) / rms)).astype(np.float32)
        assert np.isfinite(x).all(), f"NaN w {s}"
        stemy[s] = x
        mix += x

    # pochylenie widma: różnice do zmierzonego profilu celu, nie do ucha.
    # Zmierzono: góra −5,9 dB, środek −1,9 dB, sub +1,5 dB od mediany 12 referencji.
    # Bez tego głośność K-ważona zostaje na −21 LUFS, choć szczyt jest przy −1 dBFS.
    lo_sh = sosfilt(butter(2, 70 / (SR / 2), btype="low", output="sos"), mix, axis=0)
    hi_sh = sosfilt(butter(2, 2600 / (SR / 2), btype="high", output="sos"), mix, axis=0)
    md_sh = sosfilt(butter(2, [700 / (SR / 2), 2600 / (SR / 2)], btype="band",
                           output="sos"), mix, axis=0)
    # dzwon 85 Hz: pasmo uderzenia basu wychodziło −2,4 dB poniżej zakresu
    # referencji. Podnoszenie harmonicznych w samym subie nic nie dawało,
    # bo normalizacja RMS podnosi razem z nimi podstawę.
    punch = sosfilt(butter(2, [62 / (SR / 2), 118 / (SR / 2)], btype="band",
                           output="sos"), mix, axis=0)
    mix = (mix - 0.18 * lo_sh + 0.22 * hi_sh + 0.12 * md_sh
           + 0.55 * punch).astype(np.float32)

    mix = kompresor(mix, prog_db=-11.0, ratio=2.2, atk=0.020, rel=0.140)  # klej
    mix = sosfilt(butter(2, 25 / (SR / 2), btype="high", output="sos"),
                  mix, axis=0).astype(np.float32)
    low = sosfiltfilt(butter(4, 140 / (SR / 2), btype="low", output="sos"),
                      mix, axis=0)                     # ZEROFAZOWY, inaczej grzebień
    mix = (mix - low + low.mean(axis=1, keepdims=True)).astype(np.float32)
    mix = sosfilt(butter(6, 21000 / (SR / 2), btype="low", output="sos"),
                  mix, axis=0).astype(np.float32)
    og = int(7.5 * SR)
    mix[-og:] *= (np.cos(np.linspace(0, np.pi, og)) * .5 + .5)[:, None]
    mix[:int(.03 * SR)] *= np.linspace(0, 1, int(.03 * SR))[:, None]
    mix = maksymalizuj(mix, cel_lufs=-14.0, sufit=0.891)
    sz = max(float(np.abs(mix).max()), 1e-12)
    if zapisz:
        for s, x in stemy.items():
            sf.write(out.parent / f"{out.stem}_{s}.wav",
                     np.clip(x, -0.98, 0.98), SR, subtype="PCM_24")
    return mix


def main():
    p = argparse.ArgumentParser(description="Klub — celowany w zmierzony profil.")
    p.add_argument("-o", "--output", default="klub2")
    p.add_argument("--seed", type=int, default=5)
    p.add_argument("--stems-instruments", action="store_true")
    a = p.parse_args()
    out = pathlib.Path(__file__).resolve().parent / f"{a.output}.wav"
    rng = np.random.default_rng(a.seed)
    t0 = time.time()
    print(f"klub · {BPM:.0f} BPM · {TOTAL:.0f} s ({N_BARS} taktów) · 2-step, "
          f"swing {SWING * S16 * 1000:.0f} ms · d-moll")
    print("cel (mediana 12 referencji): −14,1 LUFS · DR 5,5 dB · crest 10,2 dB")
    print("  · 5,05 zdarzeń/s · sub −4,0 / bas −5,5 / dół −7,2 / środek −12,9 "
          "/ góra −14,3 / powietrze −21,4 dB\n")
    print("buduję…", flush=True)
    buf, stat, kick_t = buduj(rng)
    print(f"  zdarzeń rytmicznych {stat['zdarzenia']} "
          f"({stat['zdarzenia'] / TOTAL:.1f}/s wobec celu 5,05) · "
          f"przycięte {stat['przyciete']} ({time.time() - t0:.1f} s)", flush=True)
    print("mix…", flush=True)
    mix = zmiksuj(buf, ir_pokoj(), kick_t, a.stems_instruments, out)
    assert np.isfinite(mix).all()
    sf.write(out, mix, SR, subtype="PCM_24")
    sf.write(out.with_suffix(".flac"), mix, SR, subtype="PCM_24")
    print(f"  zapisane ({time.time() - t0:.1f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
