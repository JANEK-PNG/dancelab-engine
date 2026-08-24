"""Rejestr ruchów rąk → dźwięk. Twój set odtworzony bez Rekordboxa i bez kontrolera.

DECYZJA JANKA (24.08): Rekordbox na darmowym planie nie da się sterować bez
wpiętego sprzętu, a podrabiania klucza sprzętowego nie robimy. Więc zamiast
udawać kontroler — sami gramy to, co nagrał rejestrator: ruchy rąk z dokładnym
czasem stają się automatyką miksera, a my renderujemy wynik do pliku.

CO JEST ODTWARZANE (bo mamy to zmierzone w rejestrze):
  * transport: PLAY/PAUSE, CUE (powrót do punktu i pauza),
  * fader kanału i crossfader — krzywe równomocowe,
  * EQ trzypasmowy jako IZOLATOR: skala z panelu FLX4 (−26 dB … +6 dB,
    na samym minimum kill), granice pasm 200 Hz / 3 kHz jak w automiksie,
  * TRIM jako wzmocnienie wejścia,
  * TEMPO (suwak) jako zmiana prędkości odtwarzania.

CZEGO ŚWIADOMIE NIE UDAJEMY (i dlatego nie zmyślamy):
  * JOG — scratch i pitch bend przesuwają FAZĘ utworu; odtworzenie tego
    wymagałoby modelu bezwładności talerza. Ruchy jogiem są w rejestrze i są
    RAPORTOWANE (ile, kiedy, którym deckiem), ale nie zmieniają dźwięku.
  * Efekty (BEAT FX, Smart CFX) — to procesory Rekordboxa, nie nasze.
  * Smart Fader — gdy był włączony, Rekordbox sam ruszał EQ i echem, a tego
    w MIDI nie widać (patrz NOTATKI_INSTRUKCJA). Skrypt ostrzega, gdy wykryje
    włączenie w rejestrze.

UŻYCIE:
    uv run --with soundfile --with librosa --with scipy python graj_rejestr.py \
        rejestr_*.jsonl --deck1 utwor_A.wav --deck2 utwor_B.wav --out set.wav

Bez --deck1/--deck2 robi PRÓBĘ NA SUCHO: wypisuje, co jest w rejestrze
i jak długi byłby render (nie dotyka żadnych plików audio).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

SR = 44100
BLOK = 512                      # próbek na krok automatyki (~11,6 ms)
LOW_HZ, HIGH_HZ = 200.0, 3000.0
EQ_MIN_DB, EQ_MAX_DB = -26.0, 6.0     # skala z panelu FLX4
TRIM_MIN_DB, TRIM_MAX_DB = -60.0, 9.0
PELNA = 16383

# ---- mapa MIDI (0-based, zmierzona 23.08) ----
CC_DECK = {0: "tempo", 4: "trim", 7: "hi", 11: "mid", 15: "low", 19: "fader"}
CC_GLOB = {31: "crossfader"}
NUTY_DECK = {11: "play", 12: "cue"}
JOG_CC = {33, 34, 35, 41}


def wczytaj(sciezka: pathlib.Path) -> list[dict]:
    return [json.loads(l) for l in sciezka.read_text(encoding="utf-8").splitlines() if l.strip()]


def automatyka(zdarzenia: list[dict]) -> dict:
    """Rejestr → ścieżki sterowania. Wartości 14-bit składane z par MSB/LSB."""
    t0 = zdarzenia[0]["t"]
    tor: dict[str, list[tuple[float, float]]] = {}
    zdarz: list[tuple[float, int, str]] = []       # (czas, deck, co)
    jog = {1: 0, 2: 0}
    smart = []
    msb: dict[tuple, int] = {}

    def dopisz(nazwa: str, t: float, v: float) -> None:
        tor.setdefault(nazwa, []).append((t - t0, v))

    for r in zdarzenia:
        ch, d1, d2, t = r["ch"], r["d1"], r["d2"], r["t"]
        if r["type"] == "control_change":
            if ch in (0, 1):
                d = ch + 1
                if d1 in JOG_CC:
                    jog[d] += abs(d2 - 64)
                elif d1 in CC_DECK:
                    msb[(ch, d1)] = d2
                elif (d1 - 32) in CC_DECK and (ch, d1 - 32) in msb:
                    dopisz(f"d{d}_{CC_DECK[d1 - 32]}", t, ((msb[(ch, d1 - 32)] << 7) | d2) / PELNA)
            elif ch == 6:
                if d1 in CC_GLOB:
                    msb[(ch, d1)] = d2
                elif (d1 - 32) in CC_GLOB and (ch, d1 - 32) in msb:
                    dopisz(CC_GLOB[d1 - 32], t, ((msb[(ch, d1 - 32)] << 7) | d2) / PELNA)
        elif r["type"] == "note_on" and d2 > 0:
            if ch in (0, 1) and d1 in NUTY_DECK:
                zdarz.append((t - t0, ch + 1, NUTY_DECK[d1]))
            elif ch == 6 and d1 in (0, 1):
                smart.append((t - t0, "SMART CFX" if d1 == 0 else "SMART FADER"))
    dlugosc = zdarzenia[-1]["t"] - t0
    return {"tor": tor, "zdarzenia": zdarz, "jog": jog, "smart": smart, "dlugosc": dlugosc}


def probkuj(punkty: list[tuple[float, float]] | None, czasy: np.ndarray,
            domyslna: float) -> np.ndarray:
    """Wartość kontrolki w każdym kroku — trzymana do następnego ruchu (jak sprzęt)."""
    if not punkty:
        return np.full(len(czasy), domyslna, dtype=np.float32)
    tp = np.array([p[0] for p in punkty]); vp = np.array([p[1] for p in punkty])
    idx = np.searchsorted(tp, czasy, side="right") - 1
    out = np.where(idx < 0, vp[0], vp[np.clip(idx, 0, len(vp) - 1)])
    return out.astype(np.float32)


def db_z_pozycji(poz: np.ndarray, min_db: float, max_db: float,
                 kill_ponizej: float = 0.02) -> np.ndarray:
    """Gałka EQ/TRIM: środek = 0 dB, dół = kill, góra = max."""
    srodek = 0.5
    dol = poz < srodek
    wzm = np.where(dol, min_db * (srodek - poz) / srodek, max_db * (poz - srodek) / srodek)
    g = 10.0 ** (wzm / 20.0)
    return np.where(poz <= kill_ponizej, 0.0, g).astype(np.float32)


def pasma(y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rozbicie na trzy pasma, które po zsumowaniu odtwarzają wejście."""
    from scipy.signal import butter, sosfiltfilt
    sos_lo = butter(4, LOW_HZ / (SR / 2), btype="lowpass", output="sos")
    sos_hi = butter(4, HIGH_HZ / (SR / 2), btype="highpass", output="sos")
    low = sosfiltfilt(sos_lo, y, axis=0).astype(np.float32)
    hi = sosfiltfilt(sos_hi, y, axis=0).astype(np.float32)
    return low, (y - low - hi).astype(np.float32), hi


def wczytaj_audio(sciezka: str) -> np.ndarray:
    import librosa
    import soundfile as sf
    dane, sr = sf.read(sciezka, dtype="float32", always_2d=True)
    if dane.shape[1] == 1:
        dane = np.repeat(dane, 2, axis=1)
    if sr != SR:
        dane = librosa.resample(dane.T, orig_sr=sr, target_sr=SR).T
    return np.ascontiguousarray(dane[:, :2])


def render(a: dict, sciezki: dict[int, str], wyjscie: pathlib.Path,
           start: dict[int, float]) -> dict:
    import soundfile as sf
    n_krokow = int(np.ceil(a["dlugosc"] * SR / BLOK)) + 1
    czasy = np.arange(n_krokow) * BLOK / SR
    mix = np.zeros((n_krokow * BLOK, 2), dtype=np.float32)

    cross = probkuj(a["tor"].get("crossfader"), czasy, 0.5)
    raport = {}
    for deck, sciezka in sciezki.items():
        y = wczytaj_audio(sciezka)
        low, mid, hi = pasma(y)
        g_fader = probkuj(a["tor"].get(f"d{deck}_fader"), czasy, 1.0)
        g_trim = db_z_pozycji(probkuj(a["tor"].get(f"d{deck}_trim"), czasy, 0.5),
                              TRIM_MIN_DB, TRIM_MAX_DB, kill_ponizej=0.0)
        g_low = db_z_pozycji(probkuj(a["tor"].get(f"d{deck}_low"), czasy, 0.5), EQ_MIN_DB, EQ_MAX_DB)
        g_mid = db_z_pozycji(probkuj(a["tor"].get(f"d{deck}_mid"), czasy, 0.5), EQ_MIN_DB, EQ_MAX_DB)
        g_hi = db_z_pozycji(probkuj(a["tor"].get(f"d{deck}_hi"), czasy, 0.5), EQ_MIN_DB, EQ_MAX_DB)
        # crossfader równomocowy: deck 1 z lewej, deck 2 z prawej
        g_cross = np.cos(cross * np.pi / 2) if deck == 1 else np.sin(cross * np.pi / 2)
        tempo = probkuj(a["tor"].get(f"d{deck}_tempo"), czasy, 0.5)
        predkosc = 1.0 + (0.5 - tempo) * 0.16       # ±8 % jak zakres pitch fadera

        # wzmocnienia zmieniają się PŁYNNIE wewnątrz bloku — inaczej każdy ruch
        # fadera czy EQ dawałby trzask na styku bloków (11,6 ms to słyszalny skok)
        rampa = np.linspace(0.0, 1.0, BLOK, dtype=np.float32)[:, None]
        poprz = {"low": None, "mid": None, "hi": None, "sum": None}

        gra = False
        poz = start.get(deck, 0.0) * SR             # pozycja w próbkach źródła
        cue = poz
        zdarz = [z for z in a["zdarzenia"] if z[1] == deck]
        i_zd = 0
        grane_kroki = 0
        for k in range(n_krokow):
            while i_zd < len(zdarz) and zdarz[i_zd][0] <= czasy[k]:
                co = zdarz[i_zd][2]
                if co == "play":
                    gra = not gra
                elif co == "cue":
                    gra = False; poz = cue
                i_zd += 1
            if not gra:
                continue
            krok = BLOK * float(predkosc[k])
            a0 = int(poz); a1 = a0 + int(np.ceil(krok))
            if a1 >= len(y):
                break
            if abs(predkosc[k] - 1.0) < 1e-6:
                seg_l, seg_m, seg_h = low[a0:a0 + BLOK], mid[a0:a0 + BLOK], hi[a0:a0 + BLOK]
            else:                                    # zmiana tempa: interpolacja pozycji
                idx = poz + np.arange(BLOK) * float(predkosc[k])
                c = np.clip(idx.astype(int), 0, len(y) - 2); f = (idx - c)[:, None]
                seg_l = low[c] * (1 - f) + low[c + 1] * f
                seg_m = mid[c] * (1 - f) + mid[c + 1] * f
                seg_h = hi[c] * (1 - f) + hi[c + 1] * f
            if len(seg_l) < BLOK:
                break
            g = float(g_fader[k] * g_trim[k] * g_cross[k])
            biez = {"low": float(g_low[k]), "mid": float(g_mid[k]), "hi": float(g_hi[k]), "sum": g}
            krzywe = {}
            for nazwa, wart in biez.items():
                start_w = poprz[nazwa] if poprz[nazwa] is not None else wart
                krzywe[nazwa] = start_w + (wart - start_w) * rampa
                poprz[nazwa] = wart
            blok = (seg_l * krzywe["low"] + seg_m * krzywe["mid"]
                    + seg_h * krzywe["hi"]) * krzywe["sum"]
            mix[k * BLOK:(k + 1) * BLOK] += blok
            poz += krok
            grane_kroki += 1
        raport[deck] = {"plik": pathlib.Path(sciezka).name,
                        "grał_sekund": round(grane_kroki * BLOK / SR, 1)}

    szczyt = float(np.abs(mix).max())
    if szczyt > 1.0:                                 # tylko zapobiegawczo, bez kompresji
        mix /= szczyt
        raport["uwaga_poziom"] = f"suma przekraczała skalę ({szczyt:.2f}×) — ściszone o stałą"
    sf.write(wyjscie, mix, SR, subtype="PCM_24")
    raport["plik"] = str(wyjscie)
    raport["sekund"] = round(len(mix) / SR, 1)
    return raport


def main() -> int:
    ap = argparse.ArgumentParser(description="Rejestr ruchów rąk → dźwięk")
    ap.add_argument("rejestr")
    ap.add_argument("--deck1"); ap.add_argument("--deck2")
    ap.add_argument("--start1", type=float, default=0.0, help="sekunda startu utworu na decku 1")
    ap.add_argument("--start2", type=float, default=0.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    p = pathlib.Path(args.rejestr)
    if not p.exists():
        p = pathlib.Path(__file__).parent / args.rejestr
    zd = wczytaj(p)
    a = automatyka(zd)

    print(f"rejestr: {p.name} · {len(zd)} zdarzeń · {a['dlugosc']:.1f} s")
    print("ruchy kontrolek:")
    for nazwa, punkty in sorted(a["tor"].items()):
        print(f"   {nazwa:14s} {len(punkty):4d} zmian, "
              f"od {punkty[0][1]*100:.0f}% do {punkty[-1][1]*100:.0f}%")
    for t, deck, co in a["zdarzenia"]:
        print(f"   {t:6.2f}s  deck {deck}  {co.upper()}")
    for d, ile in a["jog"].items():
        if ile:
            print(f"   ⚠ deck {d}: jog {ile} tyknięć — NIE odtwarzane (scratch/bend zmienia fazę)")
    for t, co in a["smart"]:
        print(f"   ⚠ {t:.1f}s {co} — Rekordbox robił wtedy coś, czego MIDI nie pokazuje")

    if not (args.deck1 or args.deck2):
        print("\nPRÓBA NA SUCHO — podaj --deck1/--deck2 (pliki audio), żeby usłyszeć set.")
        return 0

    sciezki = {d: s for d, s in ((1, args.deck1), (2, args.deck2)) if s}
    out = pathlib.Path(args.out or (p.parent / (p.stem + "_odtworzony.wav")))
    print(f"\nrenderuję → {out.name}")
    raport = render(a, sciezki, out, {1: args.start1, 2: args.start2})
    print(json.dumps(raport, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
