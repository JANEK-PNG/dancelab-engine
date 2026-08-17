"""Przyrządy do mierzenia rubata w gotowym pliku — sprawdzone na znanym wzorcu.

Zanim zmierzymy cokolwiek w utworze, miernik musi udowodnić, że działa. Dlatego
każda funkcja tutaj ma test na sygnale syntetycznym, w którym rubato jest ZNANE
co do milisekundy, a test sprawdza, czy odczyt zgadza się z prawdą. Miernik,
którego nie skalibrowano, jest wrażeniem przebranym za liczbę (ADR-005).

Trzy przyrządy:

  1. TEMPO_CHWILOWE — krzywa lokalnego tempa. Nasza siatka tyka ósemkami
     (84 BPM → 2,8 Hz). Obwiednia nagrania niesie tę częstotliwość; jeśli
     wykonanie zwalnia i przyspiesza, to składowa 2,8 Hz zmienia częstotliwość
     chwilową. Odczyt: filtr pasmowy wokół 2,8 Hz na obwiedni, transformata
     Hilberta, pochodna fazy. To ta sama zasada co faza całkowana, tylko czytana
     wstecz: skoro faza jest całką z częstotliwości, to częstotliwość jest
     pochodną fazy.

  2. ROZJAZD_PASM — o ile milisekund góra wyprzedza dół (dislocation).
     Funkcja nowości widmowej liczona osobno w każdym paśmie, potem korelacja
     wzajemna w oknach. Dodatni wynik = góra przed dołem, jak prawa ręka przed
     lewą u Horowitza.

  3. PULS_KONTRA_TRZEPOT z ruchomym prążkiem — stara miara zakłada, że puls
     stoi dokładnie na 2,8 Hz. Przy rubacie puls WĘDRUJE, więc stara miara
     policzyłaby go jako trzepot i pokazała regres tam, gdzie jest zamiar.
     Ta wersja śledzi puls tam, gdzie faktycznie jest.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import butter, hilbert, sosfiltfilt, stft

ENV_SR = 200.0            # obwiednie próbkowane 200 Hz — dość na modulacje do 30 Hz
F_OSEMKI = 84.0 / 60.0 * 2   # 2,8 Hz


def obwiednia(y: np.ndarray, sr: int, lo: float = 0.0, hi: float = 0.0) -> np.ndarray:
    """Obwiednia energii, opcjonalnie z jednego pasma, próbkowana ENV_SR."""
    x = y
    if hi > 0:
        nyq = sr / 2
        if lo <= 0:
            sos = butter(4, min(hi, nyq * 0.99) / nyq, btype="lowpass", output="sos")
        else:
            sos = butter(4, [lo / nyq, min(hi, nyq * 0.99) / nyq],
                         btype="bandpass", output="sos")
        x = sosfiltfilt(sos, x)
    e = np.abs(x)
    e = sosfiltfilt(butter(2, 40 / (sr / 2), btype="lowpass", output="sos"), e)
    k = int(round(sr / ENV_SR))
    return e[::k]


def tempo_chwilowe(y: np.ndarray, sr: int, f_ref: float = F_OSEMKI,
                   szerokosc: float = 0.9, lo: float = 0.0, hi: float = 0.0):
    """Krzywa tempa w Hz (ile uderzeń siatki na sekundę) w funkcji czasu.

    szerokosc: półszerokość okna wokół f_ref w Hz. Musi objąć spodziewany
    zakres wahań tempa, ale nie sięgnąć sąsiedniej wielokrotności (5,6 Hz).
    """
    e = obwiednia(y, sr, lo, hi)
    e = np.log(np.maximum(e, 1e-7))
    e = e - uniform_filter1d(e, size=int(4 * ENV_SR), mode="nearest")   # bez trendu
    sos = butter(3, [(f_ref - szerokosc) / (ENV_SR / 2),
                     (f_ref + szerokosc) / (ENV_SR / 2)],
                 btype="bandpass", output="sos")
    puls = sosfiltfilt(sos, e)
    an = hilbert(puls)
    faza = np.unwrap(np.angle(an))
    # pochodna fazy = częstotliwość chwilowa; wygładzona, bo pochodna wzmacnia szum
    f_chw = np.gradient(faza) * ENV_SR / (2 * np.pi)
    f_chw = uniform_filter1d(f_chw, size=int(0.7 * ENV_SR), mode="nearest")
    moc = uniform_filter1d(np.abs(an), size=int(0.7 * ENV_SR), mode="nearest")
    t = np.arange(len(f_chw)) / ENV_SR
    return t, f_chw, moc


def rozjazd_pasm(y: np.ndarray, sr: int, pasmo_a=(220.0, 6000.0),
                 pasmo_b=(20.0, 220.0), okno_s: float = 4.0,
                 max_ms: float = 250.0):
    """O ile ms pasmo A wyprzedza pasmo B. Dodatnie = A wcześniej (góra przed dołem).

    Funkcja nowości widmowej (przyrost energii, część dodatnia) w każdym paśmie,
    potem korelacja wzajemna w oknach — mediana po oknach jest odporna na to,
    że w niektórych fragmentach jedno z pasm milczy.
    """
    def nowosc(pasmo):
        f, t, Z = stft(y, sr, nperseg=2048, noverlap=1536)
        k = (f >= pasmo[0]) & (f <= pasmo[1])
        M = np.abs(Z[k])
        d = np.diff(M, axis=1, prepend=M[:, :1])
        n = np.maximum(d, 0).sum(axis=0)
        krok = t[1] - t[0]
        return n, krok

    na, krok = nowosc(pasmo_a)
    nb, _ = nowosc(pasmo_b)
    na = na - uniform_filter1d(na, size=int(2.0 / krok), mode="nearest")
    nb = nb - uniform_filter1d(nb, size=int(2.0 / krok), mode="nearest")
    max_lag = int(round(max_ms / 1000 / krok))
    w = int(round(okno_s / krok))
    wyniki = []
    for i in range(0, len(na) - w, w // 2):
        a, b = na[i:i + w], nb[i:i + w]
        if a.std() < 1e-9 or b.std() < 1e-9:
            continue
        a = (a - a.mean()) / a.std()
        b = (b - b.mean()) / b.std()
        c = np.correlate(a, b, mode="full") / len(a)
        srodek = len(a) - 1
        wyc = c[srodek - max_lag: srodek + max_lag + 1]
        lag = int(np.argmax(wyc)) - max_lag
        wyniki.append((-lag * krok * 1000, float(wyc.max())))
    if not wyniki:
        return float("nan"), float("nan"), 0
    ms = np.array([w[0] for w in wyniki])
    si = np.array([w[1] for w in wyniki])
    dobre = si > 0.25
    if dobre.sum() < 3:
        return float(np.median(ms)), float(np.median(si)), int(len(ms))
    return float(np.median(ms[dobre])), float(np.median(si[dobre])), int(dobre.sum())


def puls_po_odkreceniu(y: np.ndarray, sr: int, f_ref: float = F_OSEMKI,
                       szerokosc: float = 1.0):
    """Oddech/puls/trzepot liczone w CZASIE MUZYCZNYM — po odkręceniu rubata.

    Rubato przesuwa puls w częstotliwości, więc sztywna miara zaliczyłaby go
    do trzepotu i pokazała regres tam, gdzie jest zamiar. Zamiast poszerzać
    prążki (to gasi mianownik), odkręcamy deformację: z pasma pulsu czytamy
    fazę (Hilbert), a faza to zegar muzyczny — przepróbkowanie obwiedni na
    równe kroki fazy stawia puls z powrotem dokładnie na 2,8 Hz. Dopiero tam
    przykładamy starą, wąską miarę. Trzepot (szum obwiedni niezwiązany
    z pulsem) tej operacji nie zauważa.
    """
    e = obwiednia(y, sr)
    le = np.log(np.maximum(e, 1e-7))
    le = le - uniform_filter1d(le, size=int(4 * ENV_SR), mode="nearest")
    sos = butter(3, [(f_ref - szerokosc) / (ENV_SR / 2),
                     (f_ref + szerokosc) / (ENV_SR / 2)],
                 btype="bandpass", output="sos")
    faza = np.unwrap(np.angle(hilbert(sosfiltfilt(sos, le))))
    # czas muzyczny: co (2π/f_ref)/ENV_SR fazy przypada jedna próbka nowej osi,
    # więc na nowej osi puls ma z powrotem dokładnie f_ref
    faza_row = np.arange(len(le)) * 2 * np.pi * f_ref / ENV_SR
    cel = np.linspace(faza[0], faza[-1], len(le))
    t_muz = np.interp(cel, faza, np.arange(len(le)))
    le_muz = np.interp(t_muz, np.arange(len(le)), np.log(np.maximum(e, 1e-7)))
    F = np.abs(np.fft.rfft(le_muz * np.hanning(len(le_muz)))) ** 2
    fr = np.fft.rfftfreq(len(le_muz), 1 / ENV_SR)
    puls = np.zeros_like(fr, dtype=bool)
    for k in range(1, 11):
        puls |= np.abs(fr - k * f_ref) < 0.35
    oddech = F[(fr > 0.3) & (fr < 3) & ~puls].sum()
    pulsE = F[(fr > 0.3) & (fr < 30) & puls].sum()
    trzepot = F[(fr > 4) & (fr < 30) & ~puls].sum()
    return (10 * np.log10(oddech / (trzepot + 1e-12)),
            10 * np.log10(pulsE / (trzepot + 1e-12)))


# ────────────────────── kalibracja: sygnał o ZNANYM rubacie ──────────────────
def wzorzec(sr=48000, dur=120.0, glebokosc=0.0, f_mod=0.05, opoznienie_ms=0.0,
            seed=5):
    """Ton z bramką ósemkową o zadanym rubacie i zadanym rozjeździe pasm.

    glebokosc: względne wahanie tempa (0,15 = ±15%).
    opoznienie_ms: o ile pasmo górne wyprzedza dolne (dodatnie = góra pierwsza).
    Zwraca sygnał i PRAWDZIWĄ krzywą tempa (do porównania z odczytem).
    """
    n = int(dur * sr)
    t = np.arange(n) / sr
    # tempo(t) = f0·(1 + g·sin) ; faza siatki = całka z tempa (ta sama zasada co
    # faza oscylatora — inaczej rubato „migałoby" zamiast płynąć)
    tempo = F_OSEMKI * (1 + glebokosc * np.sin(2 * np.pi * f_mod * t))
    faza = 2 * np.pi * np.cumsum(tempo) / sr
    bramka = np.maximum(0.0, np.cos(faza)) ** 6            # ostre, ale gładkie uderzenia
    rng = np.random.default_rng(seed)

    def glos(f_nosna, przesun_s):
        p = int(round(przesun_s * sr))
        b = np.roll(bramka, -p) if p else bramka
        ph = 2 * np.pi * f_nosna * t + rng.uniform(0, 2 * np.pi)
        return b * np.sin(ph)

    dol = glos(80.0, 0.0) + 0.5 * glos(160.0, 0.0)
    gora = 0.7 * (glos(880.0, opoznienie_ms / 1000) + 0.5 * glos(1760.0, opoznienie_ms / 1000))
    y = dol + gora
    y *= 0.7 / (np.abs(y).max() + 1e-9)
    return y.astype(np.float64), sr, t, tempo


def main() -> int:
    print("KALIBRACJA PRZYRZĄDÓW — wzorzec o znanym rubacie\n")

    print("1. tempo chwilowe (prawda kontra odczyt):")
    for g in (0.0, 0.08, 0.15, 0.25):
        y, sr, t, tempo_praw = wzorzec(glebokosc=g)
        tt, f_chw, _ = tempo_chwilowe(y, sr)
        praw = np.interp(tt, t, tempo_praw)
        m = (tt > 6) & (tt < 114)                       # bez krawędzi filtrów
        blad = np.abs(f_chw[m] - praw[m])
        zakres_praw = praw[m].max() - praw[m].min()
        zakres_odcz = f_chw[m].max() - f_chw[m].min()
        r = np.corrcoef(f_chw[m], praw[m])[0, 1] if g > 0 else float("nan")
        print(f"   wahanie ±{g * 100:4.0f}%  ·  prawdziwy rozstęp {zakres_praw:5.3f} Hz"
              f"  ·  odczytany {zakres_odcz:5.3f} Hz"
              f"  ·  błąd med. {np.median(blad) * 1000:5.1f} mHz"
              f"  ·  korelacja {r:+.3f}")

    print("\n2. rozjazd pasm (prawda kontra odczyt):")
    for d in (0.0, 20.0, 40.0, 80.0, -40.0):
        y, sr, _, _ = wzorzec(glebokosc=0.10, opoznienie_ms=d)
        ms, sila, n = rozjazd_pasm(y, sr)
        print(f"   zadane {d:+6.1f} ms  ·  odczytane {ms:+6.1f} ms"
              f"  ·  siła {sila:.2f}  ·  okien {n}")

    print("\n3. puls kontra trzepot — sztywny prążek vs po odkręceniu rubata:")
    print("   (dodany szum obwiedni, żeby mianownik-trzepot nie był pusty)")
    for g in (0.0, 0.15, 0.30):
        y, sr, _, _ = wzorzec(glebokosc=g)
        rng = np.random.default_rng(7)
        nm = sosfiltfilt(butter(2, [4 / (sr / 2), 30 / (sr / 2)],
                                btype="bandpass", output="sos"),
                         rng.standard_normal(len(y)))
        y = y * (1 + 0.12 * nm / (nm.std() + 1e-12))
        e = obwiednia(y, sr)
        le = np.log(np.maximum(e, 1e-7))
        F = np.abs(np.fft.rfft(le * np.hanning(len(le)))) ** 2
        fr = np.fft.rfftfreq(len(le), 1 / ENV_SR)
        sztywny = np.zeros_like(fr, dtype=bool)
        for k in range(1, 11):
            sztywny |= np.abs(fr - k * F_OSEMKI) < 0.35
        p_szt = 10 * np.log10(F[(fr > 0.3) & (fr < 30) & sztywny].sum()
                              / (F[(fr > 4) & (fr < 30) & ~sztywny].sum() + 1e-12))
        _, p_odk = puls_po_odkreceniu(y, sr)
        print(f"   wahanie ±{g * 100:4.0f}%  ·  sztywna {p_szt:+6.1f} dB"
              f"  ·  po odkręceniu {p_odk:+6.1f} dB")
    print("   oczekiwanie: sztywna SPADA z rubatem (fałszywy regres),")
    print("   po odkręceniu zostaje z grubsza stała (puls odzyskany).")

    print("\nWniosek: przyrząd jest wiarygodny w zakresie, w którym zgadza się")
    print("z prawdą na wzorcu. Poza tym zakresem jego wskazania nie są dowodem.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
