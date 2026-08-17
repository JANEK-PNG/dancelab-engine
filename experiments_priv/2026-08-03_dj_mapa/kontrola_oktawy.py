"""Czy naprawa oktawy niczego nie zepsuła na PRAWDZIWYM materiale.

Wyjątek udzielony przez Janka 13.08: jednorazowo wolno przeczytać utwory
z jego folderu `~/Music`. Czytamy je W MIEJSCU — nic nie kopiujemy, nic
nie zapisujemy do biblioteki.

Czego ten pomiar NIE jest w stanie sprawdzić: w tym folderze nie ma ani
jednego utworu poniżej 100 uderzeń, a naprawiona wada dotyczy pasma
60–99. Więc to nie jest dowód, że naprawa działa — to dowód, że nie
psuje tego, co działało (100–180, w tym cała talia house/techno Janka).

Sędzią jest Rekordbox po pełnym Analyze — jak zawsze przy weryfikacji,
nigdy jako składnik odpowiedzi.

Uruchamiać dwa razy: raz na naprawionym silniku, raz z cofniętą zmianą
(`git stash push src/dancelab/core/rigid_grid.py`), i porównać pliki
wynikowe.
"""

from __future__ import annotations

import json
import pathlib
import sys
import warnings

warnings.filterwarnings("ignore")

TU = pathlib.Path(__file__).parent
SR = 22050
SEKUND = 120.0            # tyle wystarczy na siatkę, a nie czekamy pół dnia


def main() -> None:
    wyjscie = TU / (sys.argv[1] if len(sys.argv) > 1 else "kontrola_po.json")
    sys.path.insert(0, str(TU.parents[1] / "src"))
    import librosa

    from dancelab.core.rigid_grid import fit_rigid_grid

    pliki = json.loads((TU / "pliki_music.json").read_text())
    wyniki = []
    for i, x in enumerate(pliki, 1):
        try:
            y, sr = librosa.load(x["sciezka"], sr=SR, mono=True, duration=SEKUND)
        except Exception as exc:                                  # noqa: BLE001
            wyniki.append({**x, "nasz": None, "blad": str(exc)[:60]})
            continue
        g = fit_rigid_grid(y, sr)
        wyniki.append({**x, "nasz": round(g.bpm, 2) if g else None,
                       "kontrast": round(g.contrast, 2) if g else None})
        if i % 25 == 0:
            print(f"  {i}/{len(pliki)}", flush=True)
    wyjscie.write_text(json.dumps(wyniki, ensure_ascii=False))
    ok = sum(1 for w in wyniki if w.get("nasz")
             and abs(w["nasz"] - w["bpm_rb"]) <= 1.0)
    podw = sum(1 for w in wyniki if w.get("nasz")
               and abs(w["nasz"] / w["bpm_rb"] - 2) < 0.03)
    pol = sum(1 for w in wyniki if w.get("nasz")
              and abs(w["nasz"] / w["bpm_rb"] - 0.5) < 0.03)
    n = sum(1 for w in wyniki if w.get("nasz"))
    print(f"\n{wyjscie.name}: policzonych {n}/{len(wyniki)}")
    print(f"  zgodne z Rekordboxem (≤1 bpm): {ok}  ({ok / max(n, 1) * 100:.1f}%)")
    print(f"  my 2× za szybko: {podw}   my 2× za wolno: {pol}")


if __name__ == "__main__":
    main()
