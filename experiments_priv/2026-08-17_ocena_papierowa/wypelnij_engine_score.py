"""Uzupełnia `engine_score` w szkieletach SESJA_*_transition_ratings.csv.

Robione W TRAKCIE oceny Janka (17–18.08) i to jest CZYSTE: wynik silnika
jest deterministyczny, więc policzenie go przed poznaniem ocen niczego nie
podgląda. Bez tej kolumny istniejąca bramka (`validation/dj_benchmark.py`)
nie ma czego korelować z ocenami z papieru.

Definicja wyniku pary = `transition_score` z set_buildera (arc="off",
tryb domyślny), czyli dokładnie ta funkcja, którą silnik oceniał krawędzie
przy budowie tych playlist. Skala energii liczona po UNII utworów
wszystkich 10 playlist — jedna wspólna, deterministyczna skala (w budowie
setów skala szła po puli kandydatów, która była losowana per playlista,
więc nie da się jej odtworzyć wspólnie; unia jest zapisana i powtarzalna).

OCHRONA ŚLEPEJ PRÓBY: skrypt NIE wypisuje żadnych agregatów per playlista
(średnie wyniki silnika zdradziłyby, które playlisty są tasowaną kontrolą).
Wypisuje tylko liczbę uzupełnionych wierszy.
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys

KATALOG = pathlib.Path(__file__).parent
ROOT = KATALOG.parents[1]
PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"


def main() -> int:
    from dancelab.core.config import load_weights
    from dancelab.decision.mixability import precompute_mixability_inputs
    from dancelab.decision.set_builder import transition_score
    from dancelab.storage.repositories import FileAnalysisRepository
    from dancelab.tui.duplikaty import scal

    dane = json.loads((KATALOG / "playlisty_dane.json").read_text(encoding="utf-8"))
    potrzebne = {t["track_id"] for lista in dane.values() for t in lista}

    print("wczytuję analizy…")
    repo = FileAnalysisRepository(PROCESSED)
    widok, _ = scal([repo.get(t) for t in repo.list_track_ids()])
    by_id = {a.track.track_id: a for a in widok if a.track.track_id in potrzebne}
    brak = potrzebne - set(by_id)
    if brak:
        print(f"⛔ brak analiz dla {len(brak)} utworów z playlist: {sorted(brak)[:5]}")
        return 2

    W = load_weights("configs/descriptor_weights.yaml")
    pre = precompute_mixability_inputs(by_id.values())

    # skala energii jak w set_builderze: RMS-y zmierzone, mediana dla braków
    zmierzone = {t: m["rms"] for t, m in pre.feature_means.items()
                 if m["rms"] is not None}
    e_min = min(zmierzone.values())
    e_range = (max(zmierzone.values()) - e_min) or 1.0
    import numpy as np
    mediana = float(np.median(list(zmierzone.values())))
    energia = {t: float(zmierzone.get(t, mediana)) for t in by_id}

    wyniki: dict[tuple[str, str], float] = {}
    for lista in dane.values():
        for i in range(len(lista) - 1):
            ta, tb = lista[i]["track_id"], lista[i + 1]["track_id"]
            score, _, _ = transition_score(
                by_id[ta], by_id[tb], W, "off",
                energia[ta], energia[tb], e_range,
                mixability_precomputation=pre)
            wyniki[(ta, tb)] = round(score, 4)

    uzupelnione = 0
    for sciezka in sorted(KATALOG.glob("SESJA_*_transition_ratings.csv")):
        with open(sciezka, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            klucz = (r["track_id_a"], r["track_id_b"])
            if klucz not in wyniki:
                print(f"⛔ para spoza playlist w {sciezka.name}: {klucz}")
                return 2
            r["engine_score"] = f"{wyniki[klucz]:.4f}"
            uzupelnione += 1
        with open(sciezka, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"uzupełnione engine_score: {uzupelnione} wierszy "
          f"(par policzonych: {len(wyniki)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
