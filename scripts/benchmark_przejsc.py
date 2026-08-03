"""Benchmark przejść na korpusie — to samo pytanie, co na setach Janka.

Mając utwór A na stole i CAŁĄ dostępną bibliotekę jako kandydatów, jak wysoko
produkcyjny `transition_score` stawia utwór, który prawdziwy DJ zagrał następny?

Różnica wobec testu na setach Janka: tam było 28 przejść, tu są tysiące — więc
da się na tym STROIĆ, a jego sety zostają sędzią ostatecznym (inaczej stroimy
i sprawdzamy na tych samych danych, co jest wynikiem zawyżonym).

Uczciwość metody, trzy rzeczy:

  * pula kandydatów = trudność produktu (cała biblioteka z cechami), nie
    „20 utworów z tego samego miksu" — poprzednie 24,3 % z pętli priors
    dotyczyło tego łatwiejszego zadania i nie wolno tych liczb porównywać;
  * kandydaci z TEGO SAMEGO miksu (poza prawdziwym następnym) są wykluczani,
    bo inaczej model dostaje darmową podpowiedź „to jest set z tej samej szuflady";
  * `--wersja N` liczy benchmark na pierwszych N przeanalizowanych utworach —
    stąd krzywa uczenia: czy wniosek zmienia się z ilością danych, czy stoi.

Mixability i energia liczone z cech, których dla korpusu NIE MAMY (klatki RMS,
wokal, groove), więc scoring ogranicza się do warstwy harmonia+BPM+energia
z liftami korpusu. To jest jawne ograniczenie i jest wypisane w wyniku:
porównujemy dwa warianty tego samego rdzenia, nie pełny produkt.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from dancelab.decision.harmonic import harmonic_compatibility     # noqa: E402
from dancelab.decision.set_builder import bpm_score               # noqa: E402
from dancelab.decision.corpus_priors import transition_prior_lift  # noqa: E402

FEATURES = ROOT / "data/reports/corpus_features_ext/features.jsonl"
FROZEN = ROOT / "data/reports/corpus_ordering/analysis_index.json"
MIXES = pathlib.Path("/Volumes/MY_PC/DanceLabCorpus/djmix-dataset.json")


def load_features(limit: int | None) -> dict[str, dict]:
    """Cechy: nasze świeże (w kolejności liczenia) + zamrożone 2881 Korda."""
    feats: dict[str, dict] = {}
    if FEATURES.exists():
        rows = []
        for line in FEATURES.read_text().splitlines():
            try:
                r = json.loads(line)
            except Exception:                                      # noqa: BLE001
                continue
            if r.get("bpm") and r.get("camelot"):
                rows.append(r)
        if limit:
            rows = rows[:limit]
        for r in rows:
            feats[r["id"]] = {"bpm": r["bpm"], "camelot": r["camelot"],
                              "conf": r.get("key_conf", 0.0),
                              "energy": r.get("energy", 0.1), "src": "nowe"}
    # Zamrożone 2881 Korda: indeks mapuje id → NAZWĘ PLIKU analizy w h_analysis/,
    # nie na same cechy. Bez tego kroku benchmark widział 0 utworów Korda
    # i wyrzucał do kosza gotową, policzoną wcześniej trzecią część korpusu.
    index = json.loads(FROZEN.read_text()).get("tracks", {})
    hdir = FROZEN.parent / "h_analysis"
    for tid, fname in index.items():
        if tid in feats:
            continue
        f = hdir / fname
        if not f.exists():
            continue
        try:
            t = json.loads(f.read_text()).get("track", {})
        except Exception:                                          # noqa: BLE001
            continue
        if t.get("bpm_estimate") and t.get("key_estimate"):
            feats[tid] = {"bpm": t["bpm_estimate"], "camelot": t["key_estimate"],
                          "conf": t.get("key_confidence") or 0.0,
                          "energy": 0.10, "src": "kord"}
    return feats


def core_score(a: dict, b: dict, use_priors: bool = True) -> float:
    """Rdzeń produkcyjnego scoringu: harmonia + BPM + energia + lift korpusu.

    Wagi jak w produkcyjnym trybie smart po odjęciu mixability (której dla
    korpusu nie da się policzyć — brak klatek cech). Znormalizowane do 1.
    """
    h = harmonic_compatibility(a["camelot"], b["camelot"], a["conf"], b["conf"])
    bp = bpm_score(a["bpm"], b["bpm"])
    d = (b["energy"] - a["energy"]) / 0.15
    en = float(np.exp(-((d - 0.15) ** 2) / 0.5))          # łuk „build"
    s = 0.42 * h.harmonic_compatibility_score + 0.34 * bp + 0.24 * en
    if use_priors:
        lift, _ = transition_prior_lift(h.harmonic_relation, a["bpm"], b["bpm"])
        s = float(np.clip(s * lift, 0.0, 1.0))
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wersja", type=int, default=0,
                    help="ile pierwszych policzonych utworów wziąć (0 = wszystkie)")
    ap.add_argument("--max-par", type=int, default=1200)
    ap.add_argument("--bez-priorow", action="store_true",
                    help="wyłącz lifty korpusu — kontrola błędnego koła: "
                         "lifty ZMIERZONO na tym korpusie, więc ocenianie nimi "
                         "korpusu może zawyżać wynik")
    args = ap.parse_args()

    feats = load_features(args.wersja or None)
    nowe = sum(1 for f in feats.values() if f["src"] == "nowe")

    mixes = json.loads(MIXES.read_text())
    pairs = []
    for m in mixes:
        ids = [t.get("id") for t in (m.get("tracklist") or []) if t.get("id")]
        keep = [i for i in ids if i in feats]
        for i in range(len(ids) - 1):
            a, b = ids[i], ids[i + 1]
            if a in feats and b in feats:
                pairs.append((a, b, set(ids)))
    rng = np.random.default_rng(23)
    if len(pairs) > args.max_par:
        idx = rng.choice(len(pairs), args.max_par, replace=False)
        pairs = [pairs[i] for i in idx]

    all_ids = list(feats)
    print(f"wersja: {nowe} nowych utworów + {len(feats) - nowe} Korda "
          f"= {len(feats)} z cechami · {len(pairs)} par do oceny", flush=True)
    if not pairs:
        print("brak par — poczekaj, aż policzy się więcej utworów")
        return 0

    ranks = []
    for a, b, same_mix in pairs:
        fa = feats[a]
        # kandydaci: cała biblioteka MINUS reszta tego samego miksu
        cand = [c for c in all_ids if c == b or c not in same_mix]
        if len(cand) < 50:
            continue
        sc = [(core_score(fa, feats[c], not args.bez_priorow), c) for c in cand]
        sc.sort(reverse=True)
        rank = [c for _, c in sc].index(b) + 1
        ranks.append((rank, len(cand)))

    n = len(ranks)
    pct = float(np.mean([1 - (r - 1) / p for r, p in ranks]))
    top5 = sum(1 for r, _ in ranks if r <= 5) / n
    top10 = sum(1 for r, _ in ranks if r <= 10) / n
    med_pool = float(np.median([p for _, p in ranks]))
    print(f"  ocenionych przejść: {n}")
    print(f"  percentyl prawdziwego następnego: {pct:.4f}   (0,5 = ślepy)")
    print(f"  top-5 : {top5 * 100:5.2f}%  (losowo {5 / med_pool * 100:.2f}%)")
    print(f"  top-10: {top10 * 100:5.2f}%  (losowo {10 / med_pool * 100:.2f}%)")
    print(f"  mediana puli kandydatów: {med_pool:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
