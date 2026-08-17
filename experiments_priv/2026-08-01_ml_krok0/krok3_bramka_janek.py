"""KROK 3 · bramka: czy model uczony na cudzych miksach działa NA JANKU.

Model z `krok3_ranking.py` uczy się na 772 miksach z korpusu. Pytanie, które
rozstrzyga, czy to jest cokolwiek warte: przeniesiony na bibliotekę Janka
i jego 28 realnych przejść, bije produkcyjny silnik (percentyl 0,597) czy nie.

Trening: KORPUS, pula trudna (kandydaci z tego samego miksu).
Test: 28 przejść Janka, pula = cała jego biblioteka, dokładnie jak w bramce.
Zero danych Janka w treningu.
"""

from __future__ import annotations

import json
import pathlib
import sys
import unicodedata as U

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from krok3_ranking import CTX, build, global_bpm, load_corpus  # noqa: E402

from cue_parse import parse_cue          # noqa: E402
from grid_cache import grid_for          # noqa: E402
from dancelab.storage.repositories import FileAnalysisRepository  # noqa: E402

PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"
LIB_EMB = ROOT / "data/reports/library_embeddings.json"
CUES = [
    "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Unknown Album/01 Premier.cue",
    "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Spring/01 Open Deck.cue",
]
N = lambda s: U.normalize("NFC", str(s))  # noqa: E731
COLS = [0, 1, 2, 4, 5]                    # clap, bpm_diff, bpm_ratio, clap_ctx, bpm_known


def fold_bpm(a: float, b: float) -> float:
    if a <= 0 or b <= 0:
        return 9.99
    r = b / a
    while r > 1.5:
        r /= 2
    while r < 0.67:
        r *= 2
    return abs(r - 1.0)


def main() -> int:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    # ── 1. trening na korpusie
    idx, M, mixes = load_corpus()
    bpm_of = global_bpm(mixes)
    X, y, _g, _q = build(idx, M, mixes, bpm_of, hard=True)
    sc = StandardScaler().fit(X[:, COLS])
    model = LogisticRegression(C=1.0, max_iter=1000).fit(sc.transform(X[:, COLS]), y)
    print(f"model wytrenowany na {len(y)} wierszach korpusu\n", flush=True)

    # ── 2. biblioteka Janka
    repo = FileAnalysisRepository(PROCESSED)
    analyses = [repo.get(t) for t in repo.list_track_ids()]
    by_path = {N(a.track.source_path): a for a in analyses}
    bpm = {}
    for a in analyses:
        g = grid_for(a.track.source_path)
        bpm[a.track.track_id] = float(g["bpm"]) if g else 0.0

    d = json.loads(LIB_EMB.read_text())
    root = N(d.get("library_root", ""))
    vec = {}
    for a in analyses:
        rel = N(a.track.source_path)[len(root):].lstrip("/")
        v = d["tracks"].get(rel)
        if v is not None:
            w = np.asarray(v, dtype=np.float32)
            vec[a.track.track_id] = w / (np.linalg.norm(w) + 1e-9)
    print(f"biblioteka: {len(analyses)} analiz · CLAP {len(vec)} · "
          f"tempo {sum(1 for v in bpm.values() if v)}\n", flush=True)

    # ── 3. te same 28 przejść co w bramce
    ranks_model, ranks_clap, skipped = [], [], 0
    for cue in CUES:
        _, entries = parse_cue(cue)
        order = []
        for e in entries:
            a = by_path.get(N(e.path))
            if a is not None and (not order or order[-1].track.track_id != a.track.track_id):
                order.append(a)

        hist = []
        for i in range(len(order) - 1):
            a, real_b = order[i], order[i + 1]
            hist.append(a.track.track_id)
            played = {t.track.track_id for t in order[: i + 1]}
            pool = [c for c in analyses if c.track.track_id not in played]
            if real_b.track.track_id not in {c.track.track_id for c in pool}:
                continue
            if a.track.track_id not in vec:
                skipped += 1
                continue

            hv = [vec[t] for t in hist[-CTX:] if t in vec]
            ctx = np.mean(hv, axis=0) if hv else vec[a.track.track_id]
            ctx = ctx / (np.linalg.norm(ctx) + 1e-9)
            va, ba = vec[a.track.track_id], bpm.get(a.track.track_id, 0.0)
            pos = i / max(1, len(order) - 2)

            rows, ids = [], []
            for c in pool:
                cid = c.track.track_id
                if cid not in vec:
                    continue
                bb = bpm.get(cid, 0.0)
                rows.append([float(va @ vec[cid]), fold_bpm(ba, bb),
                             (bb / ba) if (bb and ba) else 1.0, pos,
                             float(ctx @ vec[cid]), 1.0 if bb else 0.0])
                ids.append(cid)
            if real_b.track.track_id not in ids:
                skipped += 1
                continue

            Z = np.asarray(rows, dtype=np.float32)
            p = model.predict_proba(sc.transform(Z[:, COLS]))[:, 1]
            o = np.argsort(-p)
            ranks_model.append((int(np.where(np.asarray(ids)[o] ==
                                             real_b.track.track_id)[0][0]) + 1, len(ids)))
            oc = np.argsort(-Z[:, 0])
            ranks_clap.append((int(np.where(np.asarray(ids)[oc] ==
                                            real_b.track.track_id)[0][0]) + 1, len(ids)))

    def report(name, r):
        if not r:
            print(f"  {name:<34} brak danych")
            return
        pct = float(np.mean([1 - (x - 1) / p for x, p in r]))
        t5 = 100 * np.mean([x <= 5 for x, _ in r])
        t10 = 100 * np.mean([x <= 10 for x, _ in r])
        print(f"  {name:<34} {pct:9.3f} {t5:7.1f}% {t10:7.1f}%")

    print("═" * 66)
    print(f"BRAMKA · {len(ranks_model)} przejść Janka "
          f"(pominięte: {skipped})")
    print("═" * 66)
    print(f"\n  {'':<34} {'percentyl':>9} {'top-5':>8} {'top-10':>8}")
    print("  " + "─" * 62)
    print(f"  {'losowo (rozkład zerowy, n=28)':<34} {0.502:9.3f} "
          f"{2.1:7.1f}% {4.2:7.1f}%")
    print(f"  {'produkcyjny transition_score':<34} {0.597:9.3f} "
          f"{0.0:7.1f}% {3.6:7.1f}%")
    print(f"  {'najbliższe tempo (1 cecha)':<34} {0.606:9.3f} "
          f"{7.1:7.1f}% {7.1:7.1f}%")
    report("sam CLAP", ranks_clap)
    report("MODEL z korpusu (772 miksy)", ranks_model)
    print("\n  95% przedział czystego przypadku przy n=28: 0,396 – 0,609")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
