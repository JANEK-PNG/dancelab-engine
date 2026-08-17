"""KROK 5 · szkoły sekwencjonowania — grupowanie miksów po ZACHOWANIU DJ-a.

Decyzja Janka (03.08): trenujemy tylko na korpusie, a zamiast uśredniać
wszystkich DJ-ów — uczyć silnik grać jak konkretna szkoła, którą DJ wybiera.

Model per DJ jest niemożliwy: zmierzone, 299 z 388 DJ-ów ma w korpusie
JEDEN miks, a tylko 33 mają trzy lub więcej. Zostaje grupowanie.

Grupujemy po ZACHOWANIU, nie po gatunku — tak samo jak grupy brzmieniowe
biblioteki (decyzja Janka 31.07): silnik nie twierdzi „to jest techno",
twierdzi, że te miksy są szyte podobnie. Nazwy nadają im DJ-e, którzy
w danej grupie dominują — opisowo, nie normatywnie.

PODPIS MIKSU — same rzeczy zmierzone, żadnych tagów:
  bpm_med        mediana tempa miksu
  dbpm_med       mediana skoku tempa między utworami
  dbpm_locked    ułamek przejść z tempem zamkniętym (<1 BPM różnicy)
  clap_med       mediana podobieństwa brzmienia sąsiadów — jak daleko skacze
  clap_iqr       rozrzut tych skoków: równo czy raz blisko raz daleko
  palette        średnie podobieństwo WSZYSTKICH utworów miksu — szerokość palety
  drift          dryf tempa przez cały set, w BPM na utwór
  n_tracks       długość

Podpisy są skalowane, potem k-średnich. Liczbę grup wybiera sylwetka,
nie moje przeczucie.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).parent))
CORPUS = pathlib.Path("/Volumes/MY_PC/DanceLabCorpus")
OUT = pathlib.Path(__file__).parent / "krok5_szkoly.json"

from krok3_ranking import fold_bpm, global_bpm, load_corpus  # noqa: E402


def dj_of(meta: dict) -> str | None:
    """DJ z tytułu, POTWIERDZONY kategorią MixesDB. Brak potwierdzenia → None."""
    t = meta.get("title", "")
    cats = {x["key"][9:] for x in (meta.get("tags") or [])
            if isinstance(x, dict) and x.get("key", "").startswith("Category:")}
    m = re.search(r"^\s*[\d\-]{4,10}\s*-\s*(.+?)\s*(?:@|\||-\s|\()", t)
    cand = m.group(1).strip() if m else None
    if cand and cand in cats:
        return cand
    hits = [c for c in cats if cand and c.lower() in cand.lower()]
    return hits[0] if len(hits) == 1 else None


def signature(order, bpm_of, M, idx) -> list[float] | None:
    """Podpis miksu. None, gdy za mało danych — nie podstawiamy niczego."""
    ys = [y for y in order if y in idx]
    if len(ys) < 6:
        return None
    bp = [bpm_of.get(y, 0.0) for y in ys]
    pairs = [(a, b) for a, b in zip(bp, bp[1:]) if a > 0 and b > 0]
    if len(pairs) < 4:
        return None
    d = [fold_bpm(a, b) * b for a, b in pairs]          # skok w BPM
    cos = [float(M[idx[a]] @ M[idx[b]]) for a, b in zip(ys, ys[1:])]
    V = M[[idx[y] for y in ys]]
    G = V @ V.T
    palette = float((G.sum() - np.trace(G)) / (len(ys) * (len(ys) - 1)))
    good = [x for x in bp if x > 0]
    drift = (good[-1] - good[0]) / max(1, len(good) - 1) if len(good) > 2 else 0.0
    return [float(np.median(good)), float(np.median(d)),
            float(np.mean([x < 1.0 for x in d])), float(np.median(cos)),
            float(np.subtract(*np.percentile(cos, [75, 25]))),
            palette, drift, float(len(ys))]


NAMES = ["bpm_med", "dbpm_med", "dbpm_locked", "clap_med",
         "clap_iqr", "palette", "drift", "n_tracks"]


def main() -> int:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    idx, M, mixes = load_corpus()
    bpm_of = global_bpm(mixes)
    meta = {m["id"]: m for m in json.loads(
        (CORPUS / "djmix-dataset.json").read_text(encoding="utf-8", errors="replace"))}

    rows, ids, djs = [], [], []
    for mx in mixes:
        order, seen = [], set()
        for t in mx["ts"]:
            for k in ("previous_source_id", "next_source_id"):
                y = mx["meta"].get(t[k], {}).get("y")
                if y and y not in seen:
                    seen.add(y)
                    order.append(y)
        s = signature(order, bpm_of, M, idx)
        if s is None:
            continue
        rows.append(s)
        ids.append(mx["mix"])
        djs.append(dj_of(meta.get(mx["mix"], {})))

    X = StandardScaler().fit_transform(np.asarray(rows))
    print(f"miksów z podpisem: {len(X)} · z DJ-em: {sum(1 for d in djs if d)}\n")

    print("  ile grup — wybiera sylwetka, nie ja:")
    best, best_s = None, -1
    for k in range(3, 11):
        km = KMeans(n_clusters=k, n_init=20, random_state=20260803).fit(X)
        sc = silhouette_score(X, km.labels_)
        print(f"    k={k:2d}  sylwetka {sc:.3f}")
        if sc > best_s:
            best, best_s = km, sc
    k = best.n_clusters
    lab = best.labels_
    print(f"\n  wybrane: k={k} (sylwetka {best_s:.3f})\n")

    raw = np.asarray(rows)
    school = {}
    for c in range(k):
        m = lab == c
        djc = Counter(d for d, s in zip(djs, m) if s and d)
        med = raw[m].mean(axis=0)
        print(f"  ── grupa {c}: {m.sum()} miksów")
        print("     " + " · ".join(
            f"{n} {v:.2f}" for n, v in zip(NAMES, med)))
        print(f"     DJ-e: {', '.join(d for d, _ in djc.most_common(6)) or '—'}")
        school[str(c)] = {"n": int(m.sum()),
                          "mixes": [i for i, s in zip(ids, m) if s],
                          "profile": dict(zip(NAMES, med.tolist())),
                          "top_djs": djc.most_common(10)}
        print()

    OUT.write_text(json.dumps(
        {"k": k, "silhouette": float(best_s), "features": NAMES,
         "schools": school}, ensure_ascii=False))
    print(f"zapisane: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
