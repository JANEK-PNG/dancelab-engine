"""Niespójny czy po prostu inny — dwa rodzaje nieprzewidywalności.

Janek: „moja nieprzewidywalność wynika chyba z braku doświadczenia".
Hipoteza sprawdzalna, i warta sprawdzenia nie ze względu na niego — bo DJ,
który się uczy, to prawdopodobnie większość przyszłych użytkowników.

Rozróżnienie:

  * NIEDOŚWIADCZENIE = niespójność. Wybory rozrzucone, bez własnego wzorca:
    raz skok tonacji, raz nie, raz duży skok tempa, raz mały. Wysoki rozrzut
    WEWNĄTRZ jednego DJ-a.
  * ŚWIADOMY KONTRAST = spójność inna niż norma. Wzorzec jest, tylko nie ten,
    którego szuka silnik. Niski rozrzut wewnętrzny, przesunięta średnia.

W rankingu oba wyglądają tak samo (silnik nie trafia), więc trzeba mierzyć
osobno. Mierzymy trzy podpisy przejścia i pytamy o ich ROZRZUT wewnątrz DJ-a:

  * odległość brzmienia (1 − kosinus CLAP) — jak daleko skacze między utworami,
  * różnica tempa w procentach,
  * udział przejść harmonicznie „bezpiecznych" (ta sama tonacja / sąsiad).

Punkt odniesienia: ci sami DJ-e z korpusu, podzieleni na przewidywalnych
i nieprzewidywalnych. Jeśli rozrzut Janka jest jak u nich — jest spójny,
tylko inny. Jeśli wyraźnie wyższy — jego hipoteza się broni.
"""

from __future__ import annotations

import json
import pathlib
import sys
import unicodedata as U

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark_przejsc import load_features                        # noqa: E402
from cue_parse import parse_cue                                    # noqa: E402
from grid_cache import grid_for                                    # noqa: E402
from dancelab.decision.harmonic import harmonic_relation           # noqa: E402
from dancelab.storage.repositories import FileAnalysisRepository   # noqa: E402

N = lambda s: U.normalize("NFC", str(s)).lower()                   # noqa: E731
MIXES = pathlib.Path("/Volumes/MY_PC/DanceLabCorpus/djmix-dataset.json")
SAFE = {"exact", "relative_major_minor", "adjacent_same_mode"}
CUES = [
    "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Unknown Album/01 Premier.cue",
    "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Spring/01 Open Deck.cue",
]


def unit(d) -> dict:
    out = {}
    for k, v in d.items():
        a = np.asarray(v, dtype=np.float32)
        n = float(np.linalg.norm(a))
        if n > 0:
            out[k] = a / n
    return out


def signature(pairs, feats, emb, keyfn):
    """Podpis DJ-a: trzy wielkości na przejście."""
    dist, dbpm, safe = [], [], []
    for a, b in pairs:
        ea, eb = emb.get(keyfn(a)), emb.get(keyfn(b))
        if ea is not None and eb is not None:
            dist.append(1 - float(np.dot(ea, eb)))
        fa, fb = feats[a], feats[b]
        if fa["bpm"] and fb["bpm"]:
            dbpm.append(abs(fb["bpm"] - fa["bpm"]) / fa["bpm"] * 100)
        rel = harmonic_relation(fa["camelot"], fb["camelot"])
        r = rel.relation if hasattr(rel, "relation") else str(rel)
        safe.append(1.0 if r in SAFE else 0.0)
    if len(dist) < 5 or len(dbpm) < 5:
        return None
    return {
        "brzmienie_śr": float(np.mean(dist)), "brzmienie_rozrzut": float(np.std(dist)),
        "tempo_śr": float(np.mean(dbpm)), "tempo_rozrzut": float(np.std(dbpm)),
        "bezpieczne": float(np.mean(safe)), "n": len(dist),
    }


def main() -> int:
    feats = load_features(None)
    emb = unit(json.loads(
        (ROOT / "data/reports/corpus_embeddings_full.json").read_text())["tracks"])

    mixes = json.loads(MIXES.read_text())
    sigs = []
    for m in mixes:
        t = [x.get("id") for x in (m.get("tracklist") or []) if x.get("id")]
        pr = [(t[i], t[i + 1]) for i in range(len(t) - 1)
              if t[i] in feats and t[i + 1] in feats]
        if len(pr) < 8:
            continue
        s = signature(pr, feats, emb, lambda x: x)
        if s:
            sigs.append(s)
    print(f"DJ-ów z korpusu z podpisem: {len(sigs)}\n")

    # Janek
    repo = FileAnalysisRepository("experiments_priv/2026-07-30_rebuild/processed")
    jf = {}
    for a in (repo.get(t) for t in repo.list_track_ids()):
        g = grid_for(a.track.source_path)
        if g and a.track.key_estimate:
            jf[N(a.track.source_path)] = {"bpm": g["bpm"],
                                          "camelot": a.track.key_estimate}
    jemb = unit({N(pathlib.Path(k).name): v for k, v in json.loads(
        (ROOT / "data/reports/library_embeddings.json").read_text())["tracks"].items()})
    jp = []
    for cue in CUES:
        _, e = parse_cue(cue)
        o = [N(x.path) for x in e]
        o = [p for i, p in enumerate(o) if p in jf and (i == 0 or p != o[i - 1])]
        jp += [(o[i], o[i + 1]) for i in range(len(o) - 1)]
    js = signature(jp, jf, jemb, lambda x: N(pathlib.Path(x).name))

    def col(k):
        return np.array([s[k] for s in sigs])

    print(f"{'miara':>20} │ {'korpus 25c':>10} │ {'mediana':>9} │ {'75c':>8} │ {'JANEK':>8}")
    print("─" * 68)
    for k, label in (("brzmienie_śr", "skok brzmienia"),
                     ("brzmienie_rozrzut", "  rozrzut skoków"),
                     ("tempo_śr", "skok tempa %"),
                     ("tempo_rozrzut", "  rozrzut skoków"),
                     ("bezpieczne", "% bezp. harmonii")):
        v = col(k)
        print(f"{label:>20} │ {np.percentile(v, 25):>10.3f} │ "
              f"{np.median(v):>9.3f} │ {np.percentile(v, 75):>8.3f} │ {js[k]:>8.3f}")
    print(f"\n  Janek: {js['n']} przejść · korpus: mediana {np.median([s['n'] for s in sigs]):.0f}")

    # werdykt liczbowy: gdzie rozrzut Janka leży w rozkładzie rozrzutów DJ-ów
    for k, label in (("brzmienie_rozrzut", "rozrzut skoków brzmienia"),
                     ("tempo_rozrzut", "rozrzut skoków tempa")):
        v = col(k)
        pct = float((v < js[k]).mean() * 100)
        print(f"  {label}: Janek wyżej niż {pct:.0f}% DJ-ów z korpusu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
