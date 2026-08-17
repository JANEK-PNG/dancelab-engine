"""KROK 0 · pomiar 3 — punkty odniesienia dla bramki 28 przejść.

Bramka (`../2026-08-01_test_przejsc/test_przejsc_janka.py`) mówi, jak radzi
sobie produkcyjny `transition_score`. Nie mówi, ile z tego jest umiejętnością,
bo nie ma się do czego przyłożyć. Ten skrypt liczy TĘ SAMĄ metrykę dla trzech
prostych strategii — na tych samych 28 przejściach, tą samą procedurą.

  losowy            — sufit głupoty; percentyl powinien wyjść ~0,5.
                      Jeśli nie wyjdzie, błąd jest w aparaturze, nie w silniku.
  najbliższe tempo  — jedna cecha, zero harmonii, zero korpusu.
  najbliższe brzmienie (CLAP) — jedna cecha, ta, której w produkcyjnym
                      score NIE MA. Najtańszy możliwy sprawdzian, czy
                      podobieństwo brzmienia w ogóle niesie sygnał.

Bramki NIE modyfikuję — to jest osobny plik obok niej.

Percentyl liczony jak w bramce: 1 − (ranga−1)/pula. 0,5 = ślepy, więcej = lepiej.
"""

from __future__ import annotations

import json
import pathlib
import sys
import unicodedata as U

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from cue_parse import parse_cue          # noqa: E402
from grid_cache import grid_for          # noqa: E402

from dancelab.storage.repositories import FileAnalysisRepository  # noqa: E402

PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"
EMBEDS = ROOT / "data/reports/library_embeddings.json"
CUES = [
    "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Unknown Album/01 Premier.cue",
    "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Spring/01 Open Deck.cue",
]

N = lambda s: U.normalize("NFC", str(s))  # noqa: E731
SEED = 17


def fold(bpm_a: float, bpm_b: float) -> float:
    """Różnica tempa z uwzględnieniem oktawy (half/double time)."""
    if not bpm_a or not bpm_b:
        return 999.0
    return min(abs(bpm_a - bpm_b),
               abs(bpm_a - 2 * bpm_b), abs(bpm_a - bpm_b / 2))


def load_embeds():
    d = json.loads(EMBEDS.read_text())
    root = N(d.get("library_root", ""))
    out = {}
    for rel, vec in d.get("tracks", {}).items():
        v = np.asarray(vec, dtype=float)
        n = np.linalg.norm(v)
        out[N(f"{root}/{rel}")] = v / n if n else v
    return out


def main() -> int:
    repo = FileAnalysisRepository(PROCESSED)
    analyses = [repo.get(t) for t in repo.list_track_ids()]
    by_path = {N(a.track.source_path): a for a in analyses}

    patched = 0
    for a in analyses:
        g = grid_for(a.track.source_path)
        if g:
            a.track.bpm_estimate = g["bpm"]
            patched += 1

    embeds = load_embeds()
    vec = {}
    for a in analyses:
        v = embeds.get(N(a.track.source_path))
        if v is not None:
            vec[a.track.track_id] = v
    print(f"biblioteka: {len(analyses)} analiz · tempo z siatek: {patched} "
          f"· wektor CLAP: {len(vec)}", flush=True)

    rng = np.random.default_rng(SEED)

    def sc_random(_a, _c):
        return float(rng.random())

    def sc_tempo(a, c):
        return -fold(a.track.bpm_estimate or 0.0, c.track.bpm_estimate or 0.0)

    def sc_clap(a, c):
        va, vc = vec.get(a.track.track_id), vec.get(c.track.track_id)
        return float(va @ vc) if va is not None and vc is not None else None

    strategies = [("losowy", sc_random),
                  ("najblizsze tempo", sc_tempo),
                  ("najblizsze brzmienie (CLAP)", sc_clap)]

    results = {name: {"ranks": [], "skipped": 0} for name, _ in strategies}
    n_pairs = 0

    for cue in CUES:
        _, entries = parse_cue(cue)
        order = []
        for e in entries:
            a = by_path.get(N(e.path))
            if a is not None and (not order or order[-1].track.track_id != a.track.track_id):
                order.append(a)

        for i in range(len(order) - 1):
            a, real_b = order[i], order[i + 1]
            played = {t.track.track_id for t in order[: i + 1]}
            pool = [c for c in analyses if c.track.track_id not in played]
            ids_pool = {c.track.track_id for c in pool}
            if real_b.track.track_id not in ids_pool:
                continue
            n_pairs += 1

            for name, fn in strategies:
                scored = []
                bad = False
                for c in pool:
                    s = fn(a, c)
                    if s is None:
                        if c.track.track_id == real_b.track.track_id:
                            bad = True
                        continue
                    scored.append((s, c.track.track_id))
                if bad or not scored:
                    results[name]["skipped"] += 1
                    continue
                scored.sort(reverse=True)
                ids = [t for _, t in scored]
                rank = ids.index(real_b.track.track_id) + 1
                results[name]["ranks"].append((rank, len(scored)))

    print(f"\n══ {n_pairs} prawdziwych przejść Janka ══\n")
    print(f"  {'strategia':<30} {'n':>4}  {'top-5':>7} {'top-10':>7} {'percentyl':>10}")
    print("  " + "─" * 62)
    for name, _ in strategies:
        r = results[name]["ranks"]
        sk = results[name]["skipped"]
        if not r:
            print(f"  {name:<30} — brak danych ({sk} pominięte)")
            continue
        top5 = sum(1 for x, _ in r if x <= 5) / len(r)
        top10 = sum(1 for x, _ in r if x <= 10) / len(r)
        pct = float(np.mean([1 - (x - 1) / p for x, p in r]))
        note = f"  ({sk} pominiętych)" if sk else ""
        print(f"  {name:<30} {len(r):>4}  {top5*100:6.1f}% {top10*100:6.1f}% "
              f"{pct:10.3f}{note}")

    print("\n  dla porównania — PRODUKCYJNY transition_score (pomiar 01.08):")
    print(f"  {'transition_score (smart)':<30} {'28':>4}  {0.0:6.1f}% {3.6:6.1f}% "
          f"{0.597:10.3f}")
    print("\n  0,500 = ślepy. Strategia poniżej 0,500 działa NA ODWRÓT.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
