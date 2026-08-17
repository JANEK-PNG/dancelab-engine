"""Rubato: czwarte malowane pole ρ(f,t) — wzór Kordiego dostaje oś czasu.

ROZSZERZONY WZÓR
  S(f,t;F) = Γ(t)·{ A_ρ + B_ρ + C·R_D(A_ρ,B_ρ) + Syn·Φ(A_ρ,B_ρ,H;F) }
  X_ρ(f,t) ≡ X(f, t − δ(f,t)),   δ(f,t) = δ₀(t) + u(f)·δ₁(t),   ρ = ∂δ/∂t

KONWENCJA ZNAKU — jedno zdanie, zero odstępstw w całym pliku:
  δ w sekundach; zdarzenie napisane na zegarze partytury τ brzmi na zegarze
  ściany t = τ + δ; każdy ODCZYT z partytury robi τ = t − δ; ρ>0 = wolniej.

Skąd pole (fakty zmierzone w dysertacji Shoostovian 2018):
  δ₀(t)  część wspólna: melodia w górę → wolniej (fakt 2; średnia wysokość
         melodii z listy zdarzeń, pasmo frazowe 1,5 s / 9 s) plus ritenuta
         Cortota przed punktami strukturalnymi ramy (fakt 7). Trend odjęty:
         δ₀(0) = δ₀(168) = 0 — rama F jest twarda.
  u(f)   profil rejestrowy dyslokacji: dół +1 (późno), powietrze −1 (wcześnie).
  δ₁(t)  amplituda dyslokacji = L·σ(D) — jedzie po ISTNIEJĄCYM polu kierunku D:
         D>0 (ręka odkształca siatkę) → rejestry rozjeżdżają się (rubato
         STRUKTURALNE, Horowitz Chicago/Boston 1968); D<0 → dyslokacja
         zamyka się (rubato melodyczne). Fakt 5 (30–50 ms) jest tu wynikiem.
  Γ(t)   sprzężenie tempa i dynamiki (fakt 3): przyspiesza → głośniej.

Wpięcie WYŁĄCZNIE U ŹRÓDŁA — świadoma decyzja architektoniczna:
  (1) siatka B: bramka liczona jako G(t − δ(f,t)) — macierz per płótno;
  (2) ręka A: start każdej nuty przesunięty o δ czytane W JEJ PODSTAWIE,
      czas trwania bez zmian (fakt 6 Fabiana–Schuberta: deformację pochłania
      przerwa między nutami, nie proporcje nut).
  Zero przepróbkowania osi czasu, zero deformacji macierzy i `fr` w synth —
  tracker, repaint, podział linie/plamy, H, Φ, breath działają na jednej
  siatce czasu ściany i nie wymagają ani jednej poprawki. Trzymane tony nie
  dostają ani procenta vibrata.

ZAMIERZONA konsekwencja czytania δ w podstawie nuty: harmoniczne ręki
i zęby siatki w tym samym paśmie rozjeżdżają się do 2L = 120 ms — to JEST
dyslokacja. Strażnikiem zespołu harmonicznego jednej nuty jest miara fuzji
(obwiednie 60–220 vs 220–1200 Hz, próg 0,40).

Dół niesie wyłącznie frazową część δ (krok kolumny 85 ms kwantyzuje resztę);
wszystkie progi czasowe czytamy z powietrza (9–24 kHz) i środka (430–3000 Hz),
nigdy z dołu (puls/tło dołu ~−5 dB — szum udający sukces).

MECHANIZM: ten plik PODMIENIA hw.CAN na płótna RubatoCanvas (monkey-patch
świadomy, nie przypadkowy) i NIE DOTYKA hybryda_wielorozdzielcza.py ANI
W JEDNEJ LINII — wzór i synteza są dosłownie tymi samymi obiektami po obu
stronach porównania, więc plik kontrolny hybryda_wielorozdzielcza.wav
pozostaje ważną grupą kontrolną. Hasz kompozycji gwarantuje tożsamość
PARTYTURY; pliki NIE są porównywalne próbka po próbce (inne pola → inne
tory → inne fazy startowe) — wyłącznie miara po mierze.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import resource
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from scipy.ndimage import gaussian_filter1d, uniform_filter1d
from scipy.signal import butter, sosfiltfilt

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hybryda_wielorozdzielcza as hw                          # noqa: E402
from miary_rubata import puls_po_odkreceniu                     # noqa: E402

DIR = pathlib.Path(__file__).resolve().parent
assert hw.SR == 96000 and hw.TOTAL == 168.0 and hw.BPM == 84.0
SR = hw.SR
T8 = 60.0 / hw.BPM / 2            # 0,357142857 s
F8 = 1.0 / T8                     # 2,8 Hz
FS = 200.0                        # siatka pola ρ = siatka hw.T200
T = hw.T200

# ── kompozycja: JEDNO wywołanie compose_A na cały plik (drugie = inny utwór) ──
EV = hw.compose_A()
HASH_A = hashlib.sha256(json.dumps([[round(x, 12) for x in e] for e in EV],
                                   sort_keys=True).encode()).hexdigest()[:16]
assert HASH_A == "bfdda805712a4e68", \
    f"kompozycja się zmieniła ({HASH_A}) — grupa kontrolna nieważna"
assert len(EV) == 88

# ── pole ρ: melodia (fakt 2) + Cortot (fakt 7) + dyslokacja po D (fakty 1, 5) ──
SG_F, SG_S = 1.5, 9.0             # pasmo frazy melodii [s]
AC, SG_C = 0.120, 3.5             # Cortot: amplituda [s], szerokość [s]
PKT = (20.0, 34.0, 40.0, 70.0, 112.0, 148.0)     # punkty strukturalne ramy F
D0_MAX = 0.240                    # budżet |δ₀| [s]
L_DYS = 0.060                     # amplituda dyslokacji [s] (fakt 5 wynika)

_pitch = np.zeros_like(T)
_cnt = np.zeros_like(T)
for (t0, dur, m, dr) in EV:
    i0, i1 = int(t0 * FS), min(int((t0 + dur) * FS), len(T))
    _pitch[i0:i1] += (m + dr)
    _cnt[i0:i1] += 1
_idx = np.where(_cnt > 0)[0]
P_MEL = np.interp(np.arange(len(T)), _idx, (_pitch / np.maximum(_cnt, 1))[_idx])
_dev = gaussian_filter1d(P_MEL, SG_F * FS) - gaussian_filter1d(P_MEL, SG_S * FS)
_cor = sum(AC * np.exp(-0.5 * ((T - (tk - 2.0)) / SG_C) ** 2) for tk in PKT)
_cor = _cor - _cor.mean()


def _detr(x):
    """Rama F jest twarda: δ(0) = δ(TOTAL) = 0."""
    return x - np.linspace(x[0], x[-1], len(x))


_lo, _hi = 1e-3, 0.5
for _ in range(50):                # α bisekcją: deterministycznie, bez kantów clip
    _a = 0.5 * (_lo + _hi)
    if np.abs(_detr(_a * _dev + _cor)).max() > D0_MAX:
        _hi = _a
    else:
        _lo = _a
ALFA = 0.5 * (_lo + _hi)
D_MEL = _detr(ALFA * _dev)
D_COR = _detr(_cor)
D0 = _detr(ALFA * _dev + _cor)
RHO0 = np.gradient(D0, 1 / FS)

_d_t = 3.0 * np.cos(np.pi * np.clip((T - 40) / (hw.TOTAL - 40), 0, 1))  # 1:1 z silnikiem
D1 = L_DYS / (1.0 + np.exp(-_d_t))


def U(f):
    """Profil rejestrowy dyslokacji: dół +1 (późno), powietrze −1 (wcześnie)."""
    return 1.0 - 2.0 * np.clip((np.log(f) - np.log(300.0))
                               / (np.log(20000.0) - np.log(300.0)), 0.0, 1.0)


def delta_at(f, t):
    """δ(f,t) [s]; f i t broadcastują się."""
    return np.interp(t, T, D0) + U(f) * np.interp(t, T, D1)


assert np.isfinite(D0).all() and np.isfinite(D1).all()
assert abs(D0[0]) < 1e-12 and abs(D0[-1]) < 1e-12, "deformacja nie wraca do ramy"
RHO_MAX = float(np.abs(RHO0 + np.gradient(D1, 1 / FS)).max())
assert np.abs(D0).max() + D1.max() <= 0.32, "budżet |δ| przekroczony"
assert RHO_MAX < 0.35, f"tempo poza widełkami: ±{RHO_MAX:.3f}"

# Γ: sprzężenie tempa i dynamiki — β wyliczone, nie zgadywane (sd celu 1,0 dB)
BETA = (10 ** (1.0 / 20) - 1.0) / (RHO0.std() + 1e-12)
GAM = np.clip(1.0 - BETA * RHO0, 0.78, 1.30)


def gate_matrix(tax, bhz):
    """Bramka siatki czytana na zdeformowanym zegarze: G(t − δ(f,t)).

    JEDYNE miejsce w pliku, gdzie odejmuje się δ (odczyt z partytury).
    """
    tt = tax[None, :]
    arg = tt - (np.interp(tt, T, D0) + U(bhz[:, None]) * np.interp(tt, T, D1))
    return np.interp(arg, hw.T200, hw.G200).astype(np.float32)


class RubatoCanvas(hw.Canvas):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.gate_mat = gate_matrix(self.tax, self.bhz)          # (NB, cols)
        gs = self.gate_mat.mean(axis=0)          # bramka ODDZIAŁYWAŃ zostaje 1-D
        n = int(max(1, round(2.0 * 0.5 / self.dt)))
        for _ in range(3):
            gs = uniform_filter1d(gs, size=n, mode="nearest")
        self.gate_slow = gs.astype(np.float32)
        del self.gate                # nikt nie może użyć wersji niezdeformowanej

    def comb(self, field, f, amp, width_hz):
        fb = self.bin_of(f)
        w = max(0.8, width_hz / self.df)
        lo, hi = max(0, int(fb - 4 * w)), min(self.NB, int(fb + 4 * w) + 1)
        if lo >= hi:
            return
        prof = np.exp(-0.5 * ((np.arange(lo, hi) - fb) / w) ** 2).astype(np.float32)
        field[lo:hi] += amp * prof[:, None] * self.gate_mat[lo:hi]


# ── podmiana płócien w silniku (parametry z obiektów, nie z literałów) ──
_src = dict(hw.CAN)
CAN_R = {n: RubatoCanvas(c.name, c.lo, c.hi, c.nper, c.hop, c.max_poly,
                         c.fade_s, c.amp_sigma, c.blur_s, c.merge_hz)
         for n, c in _src.items()}
hw.CAN.clear()
hw.CAN.update(CAN_R)
del _src
assert all(isinstance(c, RubatoCanvas) for c in hw.CAN.values())
assert hw.G.name == "global" and hw.G.hop == 2048


def paint_all_rubato(ev):
    """Ręka: start nuty przesunięty o δ czytane W PODSTAWIE, trwanie bez zmian.

    Siatka B nie wymaga tu ani jednej zmiany — deformację niesie macierz bramki.
    """
    przes = np.empty(len(ev))
    for i, (t0, dur, m, dr) in enumerate(ev):
        f0 = hw.hz(m + dr)
        d0 = float(delta_at(f0, t0))
        przes[i] = d0
        t0r = t0 + d0
        for h in range(1, 25):
            f = f0 * h
            if f < hw.F_HI:
                for c in hw.CAN.values():
                    if c.lo <= f <= c.hi:
                        c.ridge(c.A, f, t0r, t0r + dur, 1.0 / h ** 1.25, 12 + 2 * h)
        if f0 / 2 > hw.F_LO:
            for c in hw.CAN.values():
                if c.lo <= f0 / 2 <= c.hi:
                    c.ridge(c.A, f0 / 2, t0r, t0r + dur, 0.5, 8)   # subharm.: to samo δ
    for m in hw.B_PITCHES:
        for h in range(1, 25):
            f = hw.hz(m) * h
            if f < hw.F_HI:
                for c in hw.CAN.values():
                    if c.lo <= f <= c.hi:
                        c.comb(c.B, f, 1.0 / h ** 1.1, 6)
    for m in hw.AIR:
        for h in (1, 2):
            f = hw.hz(m) * h
            if f < hw.F_HI:
                for c in hw.CAN.values():
                    if c.lo <= f <= c.hi:
                        c.comb(c.B, f, 0.10 / h, 60)
    return przes


# ── przyrządy (te same dla PRZED i PO — inaczej porównanie kłamie) ──
def band_env(x, lo, hi, fs=1000.0):
    sos = butter(4, [lo / (SR / 2), min(hi, SR / 2 * 0.99) / (SR / 2)],
                 btype="bandpass", output="sos")
    e = np.abs(sosfiltfilt(sos, x))
    e = sosfiltfilt(butter(2, 45 / (SR / 2), btype="lowpass", output="sos"), e)
    return e[:: int(SR / fs)]


def delta_curve(e, bw=0.15, fs=1000.0):
    """δ [s] z RESZTY FAZY nośnej 2,8 Hz. Bez różniczkowania, bez peak-pickingu."""
    t = np.arange(len(e)) / fs
    le = np.log(np.maximum(e, 1e-9))
    le -= uniform_filter1d(le, size=int(3 * fs) | 1, mode="nearest")
    z = le * np.exp(-2j * np.pi * F8 * t)
    sos = butter(4, bw / (fs / 2), btype="low", output="sos")
    z = sosfiltfilt(sos, z.real) + 1j * sosfiltfilt(sos, z.imag)
    return -np.unwrap(np.angle(z)) / (2 * np.pi * F8), np.abs(z)


def wrap_T8(x):
    return (x + T8 / 2) % T8 - T8 / 2


def detr_lin(d):
    n = np.arange(len(d))
    return d - np.polyval(np.polyfit(n, d, 1), n)


def purity_at(m, t0):
    """Czystość trzymanej składowej w oknie 6 s od t0; indeksy CLAMPOWANE."""
    y = m[int(t0 * SR): int((t0 + 6) * SR)]
    F = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    fr = np.fft.rfftfreq(len(y), 1 / SR)
    i = int(np.argmax(F * ((fr > 200) & (fr < 1000))))
    lo, hi = max(0, i - 220), min(len(F), i + 221)
    peak = float((F[max(0, i - 3): i + 4] ** 2).sum())
    halo = float((F[lo:hi] ** 2).sum()) - peak
    v = 10 * np.log10(peak / (halo + 1e-12))
    assert np.isfinite(v), f"purity NaN w oknie {t0}s"
    return v, float(fr[i])


def corr_env(m, p1, p2):
    e1 = band_env(m, *p1, fs=200.0)
    e2 = band_env(m, *p2, fs=200.0)
    n = min(len(e1), len(e2))
    return float(np.corrcoef(e1[:n], e2[:n])[0, 1])


OKNA_PURITY = (28.0, 46.0, 64.0, 82.0, 100.0, 118.0, 136.0, 150.0)
BRZEG = 8000                      # 8 s krawędzi filtrów przy bw 0,15 (oś 1 kHz)


def raport_miar(path):
    """Wszystkie liczby dla jednego pliku — PRZED i PO liczą się TYM kodem."""
    y, sr = sf.read(path, dtype="float64")
    assert sr == SR
    L, R = y[:, 0], y[:, 1]
    m = y.mean(axis=1)
    r = {}
    r["szczyt"] = float(np.abs(y).max())
    r["skonczony"] = bool(np.isfinite(y).all())

    e_air = band_env(m, 9000, 24000)
    e_mid = band_env(m, 430, 3000)
    d_air, _ = delta_curve(e_air)
    d_mid, _ = delta_curve(e_mid)
    w = slice(BRZEG, len(d_air) - BRZEG)
    r["d_air"] = d_air
    r["sd_air_ms"] = float(detr_lin(d_air[w]).std() * 1000)
    roz = wrap_T8(d_air[w] - d_mid[w])
    r["rozjazd_ms"] = float(roz.mean() * 1000)
    r["rozjazd_sd_ms"] = float(roz.std() * 1000)

    pur = [purity_at(m, t0) for t0 in OKNA_PURITY]
    r["purity"] = [p[0] for p in pur]
    r["purity_fr"] = [p[1] for p in pur]
    r["purity_med"] = float(np.median(r["purity"]))
    r["purity_min"] = float(np.min(r["purity"]))

    o, p = puls_po_odkreceniu(m, SR)
    r["takt_oddech"], r["takt_puls"] = float(o), float(p)
    okna = []
    for k in range(7):
        seg = m[int(k * 24 * SR): int((k + 1) * 24 * SR)]
        _, pk = puls_po_odkreceniu(seg, SR)
        okna.append(float(pk))
    r["takt_puls_okna"] = okna

    r["mod_oddech"], r["mod_puls"] = (float(v) for v in hw.mod_measures(m))

    hf = sosfiltfilt(butter(6, 46000 / (SR / 2), btype="highpass", output="sos"), m)
    tot = float((m ** 2).mean())
    r["hf_sekcje"] = [float(10 * np.log10(
        (hf[int(k * 14 * SR): int((k + 1) * 14 * SR)] ** 2).mean() / (tot + 1e-30)
        + 1e-30)) for k in range(12)]

    r["corr_30_150"] = hw.corr_band(L, R, 30, 150)
    r["corr_220_6000"] = hw.corr_band(L, R, 220, 6000)
    r["fuzja_nuty"] = corr_env(m, (60, 220), (220, 1200))
    r["fuzja_info"] = corr_env(m, (1500, 3000), (12000, 20000))

    seg = sosfiltfilt(butter(4, [30 / (SR / 2), 220 / (SR / 2)],
                             btype="bandpass", output="sos"),
                      m)[int(60 * SR): int(130 * SR)]
    r["crest"] = float(20 * np.log10(np.abs(seg).max()
                                     / (np.sqrt((seg ** 2).mean()) + 1e-12)))
    r["glosnosc"] = 20 * np.log10(np.maximum(
        band_env(m, 30, 24000, fs=200.0), 1e-9))
    return r


def sprawdz_przed_renderem(przes):
    """Sześć strażników: sekundy teraz zamiast ośmiu minut po fakcie."""
    # (2) tożsamość bramki przy δ ≡ 0 — rozstrzyga ZNAK bez renderu
    global D0, D1
    D0s, D1s = D0, D1
    D0, D1 = np.zeros_like(D0), np.zeros_like(D1)
    c = hw.CAN["srodek"]
    g0 = gate_matrix(c.tax, c.bhz)
    D0, D1 = D0s, D1s
    ref = np.interp(c.tax, hw.T200, hw.G200).astype(np.float32)
    dmax = float(np.abs(g0 - ref[None, :]).max())
    assert dmax == 0.0, f"bramka przy δ≡0 różni się o {dmax} — zły znak albo baza"

    # (4) kolejność i przerwy nut w każdym głosie
    t0s = np.array([e[0] for e in EV])
    durs = np.array([e[1] for e in EV])
    brk = np.where(np.diff(t0s) < 0)[0] + 1
    for g in np.split(np.arange(len(EV)), brk):
        n0 = t0s[g] + przes[g]
        assert np.all(np.diff(n0) > 0), "rubato przestawiło kolejność nut w głosie"
        gap = n0[1:] - (n0[:-1] + durs[g][:-1])
        assert gap.min() > 0.02, f"przerwa zjedzona do {gap.min() * 1000:.0f} ms"

    # (5) odczyt zwrotny δ z macierzy bramki — RÓŻNICOWO, wspólnym progiem.
    # Próg musi być JEDEN dla obu wierszy (kontrolnego i zdeformowanego):
    # max próbkowanej bramki zależy od przypadkowego trafienia siatki w szczyt
    # akcentu (±7%), a różne progi dawały −15 ms biasu na czystym teście.
    # Parowanie porządkowe (k-te przecięcie z k-tym), bo |δ| przekracza pół
    # okresu ósemki i "najbliższy sąsiad" myliłby ósemki.
    def _przejscia(row, dt, prog):
        wyz = np.where((row[:-1] < prog) & (row[1:] >= prog))[0]
        t = (wyz + (prog - row[wyz]) / (row[wyz + 1] - row[wyz] + 1e-12)) * dt
        return t[(t > 8) & (t < hw.TOTAL - 8)]

    for name, f_test in (("srodek", 2250.0), ("gora", 15000.0)):
        c = hw.CAN[name]
        row_r = c.gate_mat[min(int(round(c.bin_of(f_test))), c.NB - 1)]
        row_0 = np.interp(c.tax, hw.T200, hw.G200).astype(np.float32)
        prog = 0.5 * row_0.max()
        tr = _przejscia(row_r, c.dt, prog)
        t0 = _przejscia(row_0, c.dt, prog)
        n = min(len(tr), len(t0))
        dd = tr[:n] - t0[:n]
        zam = delta_at(f_test, t0[:n])
        med = float(np.median(np.abs(dd - zam)) * 1000)
        rr = float(np.corrcoef(dd, zam)[0, 1])
        assert med < 3.0 and rr > 0.98, \
            f"odczyt zwrotny {name}@{f_test:.0f} Hz: med {med:.2f} ms, r {rr:+.3f}"
        print(f"  odczyt zwrotny bramki {name}@{f_test / 1000:.2f} kHz: "
              f"med |δ_zm − δ| {med:.2f} ms · r {rr:+.3f} · uderzeń {n}")


def main() -> int:
    print("pole ρ (czwarte pole, deterministyczne):")
    print(f"  α {ALFA:.4f} (bisekcja do |δ₀|max = {D0_MAX * 1000:.0f} ms) · "
          f"L dyslokacji {L_DYS * 1000:.0f} ms · β {BETA:.2f}")
    print(f"  |δ|max {(np.abs(D0).max() + D1.max()) * 1000:.0f} ms · "
          f"sd(δ₀) {D0.std() * 1000:.0f} ms · sd(ρ₀) {RHO0.std():.4f} · "
          f"tempo w [{1 - RHO_MAX:.3f}, {1 + RHO_MAX:.3f}]")
    print(f"  Γ: {20 * np.log10(GAM.min()):+.2f}…{20 * np.log10(GAM.max()):+.2f} dB"
          f" · sd {(20 * np.log10(GAM)).std():.2f} dB")
    r_zam = float(np.corrcoef(
        np.gradient(gaussian_filter1d(P_MEL, SG_F * FS)), RHO0)[0, 1])
    print(f"  r(nachylenie melodii, ρ₀) w zamiarze: {r_zam:+.3f}")

    print("\nmaluję (starty nut + macierz bramki niosą δ)…", flush=True)
    przes = paint_all_rubato(EV)
    print(f"  przesunięcia zdarzeń: średnio {przes.mean() * 1000:+.0f} ms · "
          f"sd {przes.std() * 1000:.0f} ms · zakres "
          f"{przes.min() * 1000:+.0f}…{przes.max() * 1000:+.0f} ms")

    print("strażnicy przed renderem…", flush=True)
    sprawdz_przed_renderem(przes)

    print("miary PRZED (grupa kontrolna, ten sam kod co PO)…", flush=True)
    przed = raport_miar(DIR / "hybryda_wielorozdzielcza.wav")
    print(f"  kontrola: czystość med {przed['purity_med']:+.1f} dB · "
          f"puls(takt) {przed['takt_puls']:+.1f} dB · "
          f"rozjazd {przed['rozjazd_ms']:+.1f} ms · sd δ_air {przed['sd_air_ms']:.1f} ms")

    fields0 = {n: (c.A, c.B) for n, c in hw.CAN.items()}
    print("obrót 1 wzoru…", flush=True)
    pass1, _ = hw.one_pass(fields0)
    print(f"  RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 30:.1f} GB",
          flush=True)
    fields2 = {}
    for name, c in hw.CAN.items():
        A, B = fields0[name]
        Phic = pass1[name][1]
        fb = c.fb[None, :]
        fields2[name] = ((A + 0.35 * fb * Phic * A.max()).astype(np.float32),
                         (B + 0.25 * fb * Phic * B.max()).astype(np.float32))
    del pass1
    print("obrót 2 wzoru…", flush=True)
    pass2, _ = hw.one_pass(fields2)
    print(f"  RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 30:.1f} GB",
          flush=True)

    gam_c = {n: np.interp(c.tax, T, GAM).astype(np.float32)
             for n, c in hw.CAN.items()}
    Ss = {}
    for name, c in hw.CAN.items():
        Ss[name] = pass2[name][0] * c.intro[None, :] * gam_c[name][None, :]
    del pass2

    BAZA_TORY = {"dol": 86, "srodek": 2091, "gora": 803}
    Lm = np.zeros(hw.N_SAMP)
    Rm = np.zeros(hw.N_SAMP)
    for name, c in hw.CAN.items():
        S = Ss[name]
        print(f"czytam partyturę płótna {name}…", flush=True)
        tracks = hw.track_partials(c, S)
        Rr = hw.repaint(c, tracks, S.shape)
        if name == "dol":
            N = np.maximum(S - 2.0 * hw.repaint(c, tracks, S.shape, 6.0, 14), 0.0)
        else:
            N = np.maximum(S - Rr, 0.0)
        e_lin = float((np.minimum(Rr, S) ** 2).sum())
        e_pla = float((N ** 2).sum())
        fade = int(c.fade_s * SR)
        porzucone = sum(
            1 for tr in tracks
            if min(int(tr["t"][-1] * c.hop) + fade, hw.N_SAMP)
            - int(tr["t"][0] * c.hop) < fade * 2)
        odch = (len(tracks) / BAZA_TORY[name] - 1) * 100
        print(f"  {name:7s} linii {len(tracks):5d} ({odch:+.0f}% od kontroli) · "
              f"linie {e_lin / (e_lin + e_pla + 1e-9) * 100:3.0f}% · plamy "
              f"{e_pla / (e_lin + e_pla + 1e-9) * 100:3.0f}% · porzuconych {porzucone}",
              flush=True)
        assert porzucone == 0, "tor porzucony — deformacja weszła gdzieś jeszcze"

        if name == "dol":
            pan_of = lambda tr, j: 0.0
        elif name == "gora":
            pan_of = lambda tr, j: 0.5 if j % 2 else -0.5
        else:
            A, B = fields2[name]
            An = A / (A.max() + 1e-9)
            Bn = B / (B.max() + 1e-9)
            pan_field = (-0.62 * c.mA[None, :] * An + 0.62 * c.mB[None, :] * Bn) \
                / (c.mA[None, :] * An + c.mB[None, :] * Bn + 0.35)

            def pan_of(tr, j, pf=pan_field, cc=c):
                return np.array([pf[min(max(int(cc.bin_of(f)), 0), cc.NB - 1), t]
                                 for f, t in zip(tr["f"], tr["t"])])

        Ls, Rs = hw.synth(c, tracks, pan_of)
        xn = hw.noise_of(c, N, seed=11)
        yn = xn if name == "dol" else hw.noise_of(c, N, seed=12)
        s_rms = np.sqrt(((Ls + Rs) ** 2).mean()) + 1e-12
        n_rms = np.sqrt(((xn + yn) ** 2).mean()) + 1e-12
        gN = np.sqrt(e_pla / (e_lin + 1e-9)) * s_rms / n_rms
        Lm += Ls + gN * xn
        Rm += Rs + gN * yn

    mix = np.stack([Lm, Rm])
    mix *= 0.89 / (np.abs(mix).max() + 1e-9)

    # sidecar PRZED zapisem WAV — dokładnie te tablice, które zużyła synteza
    np.savez_compressed(
        DIR / "rubato_zamiar.npz",
        t=T.astype(np.float32), d0=D0.astype(np.float32),
        d_mel=D_MEL.astype(np.float32), d_cor=D_COR.astype(np.float32),
        d1=D1.astype(np.float32), rho0=RHO0.astype(np.float32),
        gam=GAM.astype(np.float32),
        u_srodek=U(hw.CAN["srodek"].bhz).astype(np.float32),
        u_gora=U(hw.CAN["gora"].bhz).astype(np.float32),
        przes=przes.astype(np.float32), ev=np.array(EV, dtype=np.float64),
        hasz_A=np.str_(HASH_A), alfa=np.float64(ALFA), l_dys=np.float64(L_DYS),
        beta=np.float64(BETA), ac=np.float64(AC))
    sf.write(DIR / "rubato.wav", mix.T.astype(np.float32), SR, subtype="PCM_24")
    y = mix.T.astype(np.float32)
    sf.write(DIR / "rubato.flac", y, SR, subtype="PCM_24")
    print(f"\nzapisane: rubato.wav / rubato.flac / rubato_zamiar.npz", flush=True)

    # ── miary PO i raport trzykolumnowy ──
    print("miary PO…", flush=True)
    po = raport_miar(DIR / "rubato.wav")

    twarde_stopy = []
    wiersze = []

    def wiersz(nazwa, prz, poo, sukces, regres, stop=False):
        w = "OK" if sukces else ("REGRES" if regres else "uwaga")
        if stop and regres:
            twarde_stopy.append(nazwa)
        wiersze.append((nazwa, prz, poo, w))

    sd_po = po["sd_air_ms"]
    wiersz("sd δ powietrza [ms]", f"{przed['sd_air_ms']:.1f}", f"{sd_po:.1f}",
           sd_po >= 60, sd_po < 35)

    os1k = np.arange(len(po["d_air"])) / 1000.0
    d0i = np.interp(os1k, T, D0)
    w = slice(BRZEG, len(po["d_air"]) - BRZEG)
    x = detr_lin(d0i[w])
    yv = detr_lin(po["d_air"][w])
    nach = float(np.polyfit(x, yv, 1)[0])
    rkor = float(np.corrcoef(x, yv)[0, 1])
    wiersz("regresja δ_zm~δ₀ (nachylenie / r)", "nieokreślona (δ₀≡0)",
           f"{nach:.2f} / {rkor:+.2f}",
           rkor >= 0.55 and 0.35 <= nach <= 1.25,
           rkor < 0.30 or nach < 0.25)

    roz = po["rozjazd_ms"] - przed["rozjazd_ms"]     # obciążenie kontroli odjęte
    wiersz("rozjazd rejestrów [ms]", f"{przed['rozjazd_ms']:+.1f}",
           f"{po['rozjazd_ms']:+.1f} (netto {roz:+.1f})",
           -58 <= roz <= -20, roz > -8 or roz < -90)

    wiersz("czystość mediana / min [dB]",
           f"{przed['purity_med']:+.1f} / {przed['purity_min']:+.1f}",
           f"{po['purity_med']:+.1f} / {po['purity_min']:+.1f}",
           po["purity_med"] >= 7.5 and po["purity_min"] >= -1.5,
           po["purity_med"] < 5.0 or po["purity_min"] < -3.0, stop=True)

    spadki = sum(1 for a, b in zip(po["takt_puls_okna"], przed["takt_puls_okna"])
                 if a < b - 4.0)
    wiersz("puls w czasie taktu [dB]", f"{przed['takt_puls']:+.1f}",
           f"{po['takt_puls']:+.1f} (okien poniżej −4 dB: {spadki})",
           po["takt_puls"] >= przed["takt_puls"] - 1.0 and spadki <= 1,
           po["takt_puls"] < przed["takt_puls"] - 2.0, stop=True)

    wiersz("oddech/puls na zegarze [dB] (informacyjnie)",
           f"{przed['mod_oddech']:+.1f} / {przed['mod_puls']:+.1f}",
           f"{po['mod_oddech']:+.1f} / {po['mod_puls']:+.1f} "
           "(spadek pulsu OCZEKIWANY: sztywny grzebień vs zamierzone ±8%)",
           True, False)

    skoki = [(k, a - b) for k, (a, b) in
             enumerate(zip(po["hf_sekcje"], przed["hf_sekcje"])) if a - b > 10]
    wiersz("energia 46–48 kHz per sekcja", "baza",
           "bez skoków" if not skoki else
           "; ".join(f"sekcja {k} ({k * 14}-{k * 14 + 14}s): {d:+.0f} dB"
                     for k, d in skoki),
           not skoki, bool(skoki), stop=True)

    wiersz("korelacja L/R 30–150 Hz", f"{przed['corr_30_150']:.4f}",
           f"{po['corr_30_150']:.4f}",
           po["corr_30_150"] >= 0.9990, po["corr_30_150"] < 0.9950)
    wiersz("korelacja L/R środek", f"{przed['corr_220_6000']:.3f}",
           f"{po['corr_220_6000']:.3f}",
           0.70 <= po["corr_220_6000"] <= 0.97,
           po["corr_220_6000"] > 0.99 or po["corr_220_6000"] < 0.65)
    wiersz("fuzja zespołu harmonicznego", f"{przed['fuzja_nuty']:.3f}",
           f"{po['fuzja_nuty']:.3f} (info wys.: {po['fuzja_info']:.3f}, "
           "MA spaść — to dyslokacja)",
           po["fuzja_nuty"] >= 0.45, po["fuzja_nuty"] < 0.40)
    wiersz("crest dołu 60–130 s [dB]", f"{przed['crest']:.1f}", f"{po['crest']:.1f}",
           11.0 <= po["crest"] <= 14.5, po["crest"] > 15.0)
    wiersz("szczyt / skończoność", f"{przed['szczyt']:.4f}",
           f"{po['szczyt']:.4f} / {po['skonczony']}",
           abs(po["szczyt"] - 0.89) < 1e-4 and po["skonczony"],
           not (abs(po["szczyt"] - 0.89) < 1e-4 and po["skonczony"]))

    # fakt 3 — miara RÓŻNICOWA (izoluje Γ, bo kompozycja identyczna)
    n = min(len(po["glosnosc"]), len(przed["glosnosc"]))
    dif = po["glosnosc"][:n] - przed["glosnosc"][:n]
    dif = gaussian_filter1d(dif, 3 * 200)
    dif -= uniform_filter1d(dif, size=30 * 200, mode="nearest")
    rho_i = np.interp(np.arange(n) / 200.0, T, RHO0)
    r3 = float(np.corrcoef(dif, -rho_i)[0, 1])
    wiersz("fakt 3: r(ΔdB, −ρ₀)", "różnicowa", f"{r3:+.2f}",
           r3 >= 0.45, r3 < 0.20)

    # fakty 2 i 7 — regresja dwuczłonowa δ_zm ~ d_mel + d_cor
    dm = np.interp(os1k, T, D_MEL)[w]
    dc = np.interp(os1k, T, D_COR)[w]
    X = np.column_stack([detr_lin(dm), detr_lin(dc), np.ones(w.stop - w.start)])
    b, res, *_ = np.linalg.lstsq(X, yv, rcond=None)
    resid = yv - X @ b
    n_ef = max((w.stop - w.start) / 6700.0, 3.0)
    s2 = float((resid ** 2).sum()) / max(n_ef - 3.0, 1.0)
    XtX = np.linalg.inv(X.T @ X * (n_ef / (w.stop - w.start)))
    se = np.sqrt(np.maximum(np.diag(XtX) * s2 / (w.stop - w.start), 1e-30))
    t_mel, t_cor = b[0] / se[0], b[1] / se[1]
    wiersz("fakt 2: wsp. melodii (t)", "nieokreślona",
           f"{b[0]:+.2f} (t={t_mel:.1f})",
           b[0] > 0 and t_mel > 4.0, b[0] < 0 and t_mel > 4.0)
    wiersz("fakt 7: wsp. Cortota (t)", "nieokreślona",
           f"{b[1]:+.2f} (t={t_cor:.1f})",
           b[1] > 0 and t_cor > 2.5, b[1] < 0 and t_cor > 2.5)

    print("\n" + "=" * 84)
    print(f"{'miara':44s} {'PRZED':>14s} → PO")
    print("-" * 84)
    for nazwa, prz, poo, wer in wiersze:
        print(f"[{wer:6s}] {nazwa:44s} {prz:>14s} → {poo}")
    print("=" * 84)

    # obraz: trzy płótna + czwarty panel z polem ρ
    mch = y.mean(axis=1).astype(np.float64)
    from scipy.signal import stft as _stft
    fig, axes = plt.subplots(4, 1, figsize=(14, 13), facecolor=hw.PAPER,
                             gridspec_kw={"hspace": 0.34},
                             height_ratios=[1.2, 1, 0.8, 0.7])
    plans = [("gora", 1024, 6000, 46000, axes[0]),
             ("srodek", 8192, 220, 6000, axes[1]),
             ("dol", 32768, 20, 220, axes[2])]
    for name, nper, lo, hi, ax in plans:
        f, t, Z = _stft(mch, SR, nperseg=nper, noverlap=int(nper * 0.75))
        Sd = 20 * np.log10(np.abs(Z) + 1e-10)
        k = (f >= lo) & (f <= hi)
        top = Sd[k].max()
        ax.pcolormesh(t, f[k], np.clip(Sd[k], top - 66, top),
                      shading="gouraud", cmap="magma", rasterized=True)
        ax.set_yscale("log")
        ax.set_ylim(lo, hi)
        ax.set_title(f"{name.upper()}  {lo}–{hi} Hz", color=hw.INK, fontsize=10,
                     loc="left", pad=6, family="monospace")
        ax.set_facecolor(hw.PAPER)
        for sp in ax.spines.values():
            sp.set_color(hw.INK)
        ax.tick_params(colors=hw.INK, labelsize=8)
    ax = axes[3]
    ax.plot(T, D0 * 1000, color=hw.INK, lw=1.6, label="δ₀(t) — część wspólna")
    for f_pl, kol in ((150, "#3a6ea5"), (2250, hw.ACC), (15000, "#7fd8d8")):
        ax.plot(T, (D0 + U(f_pl) * D1) * 1000, color=kol, lw=0.9,
                label=f"δ({f_pl / 1000:g} kHz, t)")
    for tk in PKT:
        ax.axvline(tk, color=hw.INK, lw=0.5, ls=":", alpha=0.5)
    ax.axhline(0, color=hw.INK, lw=0.4)
    ax.set_ylabel("δ [ms]", color=hw.INK, fontsize=9)
    ax.set_xlabel("czas [s]", color=hw.INK, fontsize=9)
    ax.set_xlim(0, hw.TOTAL)
    ax.set_title("ρ — CZWARTE POLE: opóźnienie zegara ściany względem partytury",
                 color=hw.INK, fontsize=10, loc="left", pad=6, family="monospace")
    ax.legend(loc="upper right", fontsize=7.5, framealpha=0.9)
    ax.set_facecolor(hw.PAPER)
    for sp in ax.spines.values():
        sp.set_color(hw.INK)
    ax.tick_params(colors=hw.INK, labelsize=8)
    fig.suptitle("RUBATO — S = Γ·{A_ρ + B_ρ + C·R_D + Syn·Φ},  X_ρ(f,t) = X(f, t−δ(f,t))",
                 color=hw.INK, fontsize=12, family="monospace", x=0.123, ha="left")
    fig.savefig(DIR / "rubato.png", dpi=150, facecolor=hw.PAPER,
                bbox_inches="tight")
    print(f"{DIR / 'rubato.png'}")

    if twarde_stopy:
        print(f"\nTWARDY STOP: {', '.join(twarde_stopy)} — plik zostaje do "
              "odsłuchu, ale render jest ODRZUCONY.")
        raise SystemExit(1)
    print("\nwerdykt: rubato jest w pliku i jest tym, które namalowano.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
