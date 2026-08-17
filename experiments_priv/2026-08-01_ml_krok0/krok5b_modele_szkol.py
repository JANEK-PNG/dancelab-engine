"""KROK 5b · model na szkołę — i pytanie, do której szkoły należy Janek.

Trzy rzeczy do rozstrzygnięcia, każda pomiarem:

  1. Czy model uczony na JEDNEJ szkole bije model uczony na wszystkich —
     sprawdzany na miksach tej samej szkoły. Jeśli nie, cały pomysł upada
     i trzeba to powiedzieć.
  2. Czy modele szkół różnią się MIĘDZY sobą — model szkoły A puszczony
     na miksy szkoły B powinien wypaść gorzej niż własny. Bez tego
     „szkoły" są nazwą bez treści.
  3. Do której szkoły należy Janek. Jego 28 przejść jako CZUJNIK
     (decyzja z 03.08: weto, nie cel — nic na tym nie stroimy).

Walidacja wszędzie: GroupKFold po miksach. Nigdy losowo.
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

from krok3_ranking import build, global_bpm, load_corpus, CTX   # noqa: E402
from krok3_bramka_janek import COLS, fold_bpm                    # noqa: E402
from cue_parse import parse_cue                                  # noqa: E402
from grid_cache import grid_for                                  # noqa: E402
from dancelab.storage.repositories import FileAnalysisRepository  # noqa: E402

SCHOOLS = pathlib.Path(__file__).parent / "krok5_szkoly.json"
PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"
LIB_EMB = ROOT / "data/reports/library_embeddings.json"
CUES = [
    "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Unknown Album/01 Premier.cue",
    "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Spring/01 Open Deck.cue",
]
N = lambda s: U.normalize("NFC", str(s))  # noqa: E731
LABELS = {"0": "zachowawcza (Beyer/Armin/Afrojack)",
          "1": "drum & bass (Doc Scott/John B)",
          "2": "skoki (Surgeon/Ben UFO/Joris Voorn)"}


def fit(X, y, cols):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    sc = StandardScaler().fit(X[:, cols])
    m = LogisticRegression(C=1.0, max_iter=1000).fit(sc.transform(X[:, cols]), y)
    return sc, m


def percentile(proba, q, y):
    out = []
    for u in sorted(set(q.tolist())):
        s = q == u
        o = np.argsort(-proba[s])
        h = np.where(y[s][o] == 1)[0]
        if len(h):
            out.append(1 - int(h[0]) / int(s.sum()))
    return float(np.mean(out)), len(out)


def main() -> int:
    from sklearn.model_selection import GroupKFold

    sch = json.loads(SCHOOLS.read_text())["schools"]
    idx, M, mixes = load_corpus()
    bpm_of = global_bpm(mixes)
    by_id = {m["mix"]: m for m in mixes}

    data = {}
    for c, s in sch.items():
        sub = [by_id[m] for m in s["mixes"] if m in by_id]
        X, y, g, q = build(idx, M, mixes=sub, bpm_of=bpm_of, hard=True)
        data[c] = (X, y, g, q, sub)
        print(f"szkoła {c}: {len(sub)} miksów · {len(set(q.tolist()))} przejść",
              flush=True)

    Xa, ya, ga, qa = build(idx, M, mixes, bpm_of, hard=True)
    print(f"wszystkie:  {len(mixes)} miksów · {len(set(qa.tolist()))} przejść\n",
          flush=True)

    # ── 1+2. własna szkoła vs globalny vs cudza szkoła
    print("═" * 72)
    print("MODEL WŁASNEJ SZKOŁY vs GLOBALNY vs CUDZE SZKOŁY (percentyl)")
    print("═" * 72)
    hdr = f"\n  {'testowane na':<34}" + "".join(f"{'m'+c:>8}" for c in sch) + f"{'globalny':>10}"
    print(hdr)
    print("  " + "─" * (34 + 8 * len(sch) + 10))

    models = {}
    for c in sch:                                    # model każdej szkoły, na całej szkole
        X, y, g, q, _ = data[c]
        models[c] = fit(X, y, COLS)
    sc_all, m_all = fit(Xa, ya, COLS)

    for c in sch:
        X, y, g, q, _ = data[c]
        row = []
        for c2 in sch:
            if c2 == c:                              # własna szkoła → uczciwie, po miksach
                p = np.zeros(len(y))
                for tr, te in GroupKFold(n_splits=5).split(X, y, groups=g):
                    s2, m2 = fit(X[tr], y[tr], COLS)
                    p[te] = m2.predict_proba(s2.transform(X[te][:, COLS]))[:, 1]
            else:
                s2, m2 = models[c2]
                p = m2.predict_proba(s2.transform(X[:, COLS]))[:, 1]
            row.append(percentile(p, q, y)[0])
        pg = m_all.predict_proba(sc_all.transform(X[:, COLS]))[:, 1]
        gl = percentile(pg, q, y)[0]
        print(f"  {LABELS[c][:33]:<34}" + "".join(f"{v:8.3f}" for v in row) +
              f"{gl:10.3f}")
    print("\n  przekątna = własna szkoła (GroupKFold). Reszta = model cudzej szkoły.")
    print("  globalny liczony na WSZYSTKICH miksach, więc ma przewagę wielkości.")

    # ── 3. Janek jako czujnik
    repo = FileAnalysisRepository(PROCESSED)
    an = [repo.get(t) for t in repo.list_track_ids()]
    bp = {N(a.track.source_path): a for a in an}
    d = json.loads(LIB_EMB.read_text())
    root = N(d.get("library_root", ""))
    vec, bpm = {}, {}
    for a in an:
        g = grid_for(a.track.source_path)
        bpm[a.track.track_id] = float(g["bpm"]) if g else 0.0
        v = d["tracks"].get(N(a.track.source_path)[len(root):].lstrip("/"))
        if v is not None:
            w = np.asarray(v, dtype=np.float32)
            vec[a.track.track_id] = w / (np.linalg.norm(w) + 1e-9)

    rows, qs, ys = [], [], []
    qid = 0
    for cue in CUES:
        _, ent = parse_cue(cue)
        order = []
        for e in ent:
            a = bp.get(N(e.path))
            if a is not None and (not order or order[-1].track.track_id != a.track.track_id):
                order.append(a)
        hist = []
        for i in range(len(order) - 1):
            a, rb = order[i], order[i + 1]
            hist.append(a.track.track_id)
            played = {t.track.track_id for t in order[: i + 1]}
            pool = [c.track.track_id for c in an
                    if c.track.track_id not in played and c.track.track_id in vec]
            if rb.track.track_id not in pool or a.track.track_id not in vec:
                continue
            hv = [vec[t] for t in hist[-CTX:] if t in vec] or [vec[a.track.track_id]]
            ctx = np.mean(hv, axis=0)
            ctx /= (np.linalg.norm(ctx) + 1e-9)
            va, ba = vec[a.track.track_id], bpm.get(a.track.track_id, 0.0)
            pos = i / max(1, len(order) - 2)
            for cid in pool:
                bb = bpm.get(cid, 0.0)
                rows.append([float(va @ vec[cid]), fold_bpm(ba, bb),
                             (bb / ba) if (bb and ba) else 1.0, pos,
                             float(ctx @ vec[cid]), 1.0 if bb else 0.0])
                ys.append(1 if cid == rb.track.track_id else 0)
                qs.append(qid)
            qid += 1
    Xj = np.asarray(rows, dtype=np.float32)
    yj = np.asarray(ys)
    qj = np.asarray(qs)

    print("\n" + "═" * 72)
    print("CZUJNIK · do której szkoły należy Janek (28 przejść, zero w treningu)")
    print("═" * 72)
    print(f"\n  {'model':<44} {'percentyl':>10}")
    print("  " + "─" * 56)
    print(f"  {'losowo (rozkład zerowy)':<44} {0.502:10.3f}")
    print(f"  {'produkcyjny transition_score':<44} {0.597:10.3f}")
    res = {}
    for c in sch:
        s2, m2 = models[c]
        p = m2.predict_proba(s2.transform(Xj[:, COLS]))[:, 1]
        v, n = percentile(p, qj, yj)
        res[c] = v
        print(f"  {('szkoła ' + c + ' — ' + LABELS[c])[:43]:<44} {v:10.3f}")
    pg = m_all.predict_proba(sc_all.transform(Xj[:, COLS]))[:, 1]
    print(f"  {'model globalny (wszystkie szkoły)':<44} "
          f"{percentile(pg, qj, yj)[0]:10.3f}")
    best = max(res, key=res.get)
    print(f"\n  NAJBLIŻEJ: szkoła {best} — {LABELS[best]}")
    print("  95% przedział czystego przypadku przy n=28: 0,396 – 0,609")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
