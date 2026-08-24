"""Nagranie z Rekordboxa vs nasz render z rejestru — ile rozumiemy z szwu.

Nagranie REC jest PRAWDĄ (tak zabrzmiało). Render z rejestru jest HIPOTEZĄ
(tak powinno zabrzmieć, jeśli dobrze czytamy ruchy rąk). Różnica między nimi
to miara naszej niewiedzy — i o to w tym pomiarze chodzi, nie o ocenę setu.

METODA (świadomie ostrożna):
  * przesunięcie czasu znajdujemy KORELACJĄ obwiedni — nie zgadujemy startu;
  * poziom wyrównujemy jedną stałą (mediana ilorazu), bo Rekordbox nagrywa
    przez master z własnym wzmocnieniem; nie wolno tego mylić z błędem;
  * porównujemy OBWIEDNIE w trzech pasmach (200 Hz / 3 kHz — te same granice,
    których używa render), bo szew to gra głośnością pasm w czasie;
  * raportujemy też, gdzie różnica jest największa — tam siedzi to,
    czego model nie odtwarza (jog, efekty, automatyka Smart).

UŻYCIE:
    uv run --with numpy --with soundfile --with scipy python porownaj.py \
        nagranie_rekordbox.wav render_z_rejestru.wav [--od 0 --do 120]
"""

from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np

SR = 44100
LOW_HZ, HIGH_HZ = 200.0, 3000.0
OKNO = 0.05          # 50 ms — obwiednia dość gęsta, żeby złapać ruch ręki


def wczytaj(p: str, od: float | None, do: float | None) -> np.ndarray:
    import librosa
    import soundfile as sf
    y, sr = sf.read(p, dtype="float32", always_2d=True)
    y = y.mean(axis=1)
    if sr != SR:
        y = librosa.resample(y, orig_sr=sr, target_sr=SR)
    a = int((od or 0) * SR)
    b = int(do * SR) if do else len(y)
    return y[a:b]


def pasma(y: np.ndarray) -> dict[str, np.ndarray]:
    from scipy.signal import butter, sosfiltfilt
    lo = butter(4, LOW_HZ / (SR / 2), btype="lowpass", output="sos")
    hi = butter(4, HIGH_HZ / (SR / 2), btype="highpass", output="sos")
    low = sosfiltfilt(lo, y).astype(np.float32)
    high = sosfiltfilt(hi, y).astype(np.float32)
    return {"bas": low, "środek": (y - low - high).astype(np.float32), "góra": high,
            "całość": y}


def obwiednia(y: np.ndarray) -> np.ndarray:
    n = int(OKNO * SR)
    ile = len(y) // n
    return np.sqrt((y[:ile * n].reshape(ile, n) ** 2).mean(axis=1) + 1e-12)


def dopasuj(a: np.ndarray, b: np.ndarray) -> tuple[int, float]:
    """Przesunięcie b względem a (w krokach obwiedni) + zgodność w tym punkcie."""
    ea, eb = obwiednia(a), obwiednia(b)
    ea = (ea - ea.mean()) / (ea.std() + 1e-9)
    eb = (eb - eb.mean()) / (eb.std() + 1e-9)
    k = np.correlate(ea, eb, mode="full") / max(len(ea), len(eb))
    i = int(np.argmax(k))
    return i - (len(eb) - 1), float(k[i])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("nagranie"); ap.add_argument("render")
    ap.add_argument("--od", type=float, default=None)
    ap.add_argument("--do", type=float, default=None)
    ap.add_argument("--raport", default=None)
    args = ap.parse_args()

    praw = wczytaj(args.nagranie, args.od, args.do)
    hip = wczytaj(args.render, None, None)
    przes, zgodnosc = dopasuj(praw, hip)
    print(f"dopasowanie czasu: przesunięcie {przes * OKNO:+.2f} s "
          f"(zgodność kształtu {zgodnosc:.3f})")
    if zgodnosc < 0.3:
        print("⚠ NISKA zgodność kształtu — to nie wygląda na ten sam fragment; "
              "sprawdź, czy nagranie i rejestr są z tego samego przejścia")

    # wyrównaj oś czasu
    if przes > 0:
        praw = praw[przes * int(OKNO * SR):]
    elif przes < 0:
        hip = hip[-przes * int(OKNO * SR):]
    n = min(len(praw), len(hip))
    praw, hip = praw[:n], hip[:n]

    pp, ph = pasma(praw), pasma(hip)
    # jedna stała poziomu z CAŁOŚCI — master Rekordboxa ma własne wzmocnienie
    ea, eb = obwiednia(pp["całość"]), obwiednia(ph["całość"])
    maska = (ea > np.percentile(ea, 40)) & (eb > np.percentile(eb, 40))
    skala = float(np.median(ea[maska] / (eb[maska] + 1e-9))) if maska.any() else 1.0
    print(f"wyrównanie poziomu: nasz render ×{skala:.2f} "
          f"({20 * np.log10(skala):+.1f} dB — to master Rekordboxa, nie błąd)")

    wynik = {"przesuniecie_s": round(przes * OKNO, 3), "zgodnosc_ksztaltu": round(zgodnosc, 3),
             "skala_poziomu_db": round(20 * float(np.log10(skala)), 2), "pasma": {}}
    print("\nZGODNOŚĆ OBWIEDNI (1,00 = idealnie ten sam przebieg):")
    for nazwa in ("całość", "bas", "środek", "góra"):
        x, y = obwiednia(pp[nazwa]), obwiednia(ph[nazwa]) * skala
        m = min(len(x), len(y)); x, y = x[:m], y[:m]
        gra = (x > np.percentile(x, 25))              # cisza nie mówi nic o modelu
        r = float(np.corrcoef(x[gra], y[gra])[0, 1]) if gra.sum() > 10 else float("nan")
        blad_db = 20 * np.log10((y[gra] + 1e-9) / (x[gra] + 1e-9))
        med = float(np.median(np.abs(blad_db)))
        wynik["pasma"][nazwa] = {"zgodnosc": round(r, 3), "typowy_blad_db": round(med, 2)}
        ocena = "bardzo dobra" if r > .9 else "dobra" if r > .75 else "słaba" if r > .5 else "zła"
        print(f"  {nazwa:8s} zgodność {r:.3f} ({ocena}) · typowa różnica {med:.1f} dB")

    # gdzie model rozjeżdża się najbardziej
    x, y = obwiednia(pp["całość"]), obwiednia(ph["całość"]) * skala
    m = min(len(x), len(y))
    roznica = np.abs(20 * np.log10((y[:m] + 1e-9) / (x[:m] + 1e-9)))
    okna = [(i * OKNO, float(roznica[i])) for i in np.argsort(roznica)[-5:][::-1]]
    print("\nNAJWIĘKSZE ROZJAZDY (tam siedzi to, czego model nie odtwarza):")
    for t, d in okna:
        print(f"  {t:6.1f} s → różnica {d:.1f} dB")
    wynik["rozjazdy"] = [{"sekunda": round(t, 2), "roznica_db": round(d, 1)} for t, d in okna]

    if args.raport:
        pathlib.Path(args.raport).write_text(json.dumps(wynik, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
        print(f"\nzapisano: {args.raport}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
