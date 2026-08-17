"""KROK 3 · ranking następnego utworu, uczony na korpusie.

Zadanie postawione tak, jak wygląda naprawdę: mając utwór A i pulę kandydatów,
ustaw ich w kolejce tak, żeby ten, który DJ naprawdę zagrał, wylądował wysoko.
To jest learning-to-rank, a dane to 23 644 przejścia z 800 miksów, w których
audio i wektor CLAP są obecne po obu stronach dla 100% par.

Wagi silnika są dziś WYMYŚLONE (bpm 0,4 / harmonia 0,4 / energia 0,2). Ten
skrypt nie dokłada nowej cechy — dobiera wagi tych, które już są, z danych.

CECHY — wyłącznie takie, które są policzone dla całego korpusu:
  clap_cos        podobieństwo brzmienia A↔B (wektory z 22.07)
  bpm_diff        różnica tempa złożona po oktawie
  bpm_ratio       B/A, żeby kierunek zmiany tempa nie ginął w wartości bezwzględnej
  key_shift       odległość tonacji po kole kwintowym, z przesunięcia
                  key-invariant DTW (różnica, nie tonacja bezwzględna)
  grids_ok        czy obie siatki wiarygodne
  pos_in_mix      gdzie w secie jesteśmy
  clap_ctx        podobieństwo B do ŚREDNIEJ ostatnich 3 utworów — czyli
                  czy kandydat pasuje do tego, co się dzieje, a nie tylko do A

CZEGO TU NIE MA I DLACZEGO: `transition_length_beats` z tych samych plików ma
wartości ujemne i wielogodzinne i raz już skaziło priorsy (8b#2 rejestru).
Bierzemy z korpusu KOLEJNOŚĆ, nie długości.

WALIDACJA: GroupKFold po miksach — cały miks wypada z treningu razem ze swoimi
przejściami. Podział losowy dałby wynik zawyżony o nieznaną wartość.
"""

from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
CORPUS = pathlib.Path("/Volumes/MY_PC/DanceLabCorpus")
EMBEDS = ROOT / "data/reports/corpus_embeddings_full.json"

N_NEG = 20          # kandydatów-negatywów na jedno przejście
N_FOLDS = 5
SEED = 20260801
CTX = 3             # ile ostatnich utworów tworzy kontekst


def fold_bpm(a: float, b: float) -> float:
    if a <= 0 or b <= 0:
        return 9.99
    r = b / a
    while r > 1.5:
        r /= 2
    while r < 0.67:
        r *= 2
    return abs(r - 1.0)


def key_distance(sa: int | None, sb: int | None) -> float:
    """Odległość po kole kwintowym z przesunięć key-invariant DTW.

    Bezwzględnej tonacji korpus nie ma. Ma za to, ile półtonów trzeba przesunąć
    KAŻDY utwór, żeby pasował do miksu — a różnica tych przesunięć to jest
    względna odległość tonacji między dwoma utworami. Po kole kwintowym,
    bo tam sąsiedztwo znaczy to, co dla DJ-a.
    """
    if sa is None or sb is None:
        return 6.0
    d = (sb - sa) % 12
    fifths = (d * 7) % 12            # półtony → kroki kwintowe
    return float(min(fifths, 12 - fifths))


def load_corpus():
    print("wczytuję wektory CLAP…", flush=True)
    tracks = json.loads(EMBEDS.read_text())["tracks"]
    ids = list(tracks)
    idx = {y: i for i, y in enumerate(ids)}
    M = np.asarray([tracks[y] for y in ids], dtype=np.float32)
    M /= (np.linalg.norm(M, axis=1, keepdims=True) + 1e-9)
    print(f"  {len(ids)} wektorów", flush=True)

    files = [p for p in sorted((CORPUS / "alignments").glob("*.json"))
             if not p.name.startswith("._")]
    mixes = []
    for p in files:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        meta = {}
        for r in d.get("results", []):
            y = r.get("youtube_id")
            if y is None or y not in idx:
                continue
            g = r.get("track_beatgrid") or {}
            al = r.get("alignment") or {}
            meta[r["track_id"]] = {
                "y": y,
                "bpm": float(g.get("bpm") or 0.0),
                "ok": bool(g.get("reliable")),
                "shift": al.get("key_shift_semitones"),
            }
        ts = [t for t in (d.get("transitions") or [])
              if t.get("previous_source_id") in meta and t.get("next_source_id") in meta]
        if len(ts) >= 2:
            mixes.append({"mix": p.stem, "meta": meta, "ts": ts})
    print(f"  {len(mixes)} miksów użytecznych", flush=True)
    return idx, M, mixes


def global_bpm(mixes):
    """yid → tempo, złożone ze WSZYSTKICH miksów, w których utwór występuje.

    Bez tego negatywy nie mają tempa, cecha „puste = zły" rozstrzyga zadanie
    trywialnie i cały wynik jest fałszywy. Pierwszy przebieg dał tak 100%
    trafień i to była jedyna informacja, jaką niósł.
    """
    acc: dict[str, list[float]] = {}
    for m in mixes:
        for v in m["meta"].values():
            if v["ok"] and v["bpm"] > 0:
                acc.setdefault(v["y"], []).append(v["bpm"])
    return {y: float(np.median(v)) for y, v in acc.items()}


def build(idx, M, mixes, bpm_of, hard: bool):
    """hard=False: negatywy z całego korpusu. hard=True: z TEGO SAMEGO miksu.

    Wariant trudny jest tym, który odpowiada rzeczywistości — DJ wybiera
    z własnej, już dobranej stylistycznie skrzynki, a nie z 12 tysięcy
    przypadkowych płyt. Rejestr zapisał tę pułapkę przy priorsach:
    „pula wewnątrz jednego miksu to inne, ŁATWIEJSZE zadanie" — tu jest
    odwrotnie i dlatego trzeba policzyć oba.
    """
    rng = np.random.default_rng(SEED)
    pool = np.arange(M.shape[0])
    X, y, g, q = [], [], [], []
    qid = 0

    for m in mixes:
        meta, ts = m["meta"], m["ts"]
        in_mix = [idx[v["y"]] for v in meta.values() if v["y"] in idx]
        hist: list[int] = []
        for k, t in enumerate(ts):
            A = meta[t["previous_source_id"]]
            B = meta[t["next_source_id"]]
            ia, ib = idx[A["y"]], idx[B["y"]]
            hist.append(ia)
            ctx = M[hist[-CTX:]].mean(axis=0)
            ctx = ctx / (np.linalg.norm(ctx) + 1e-9)
            pos = k / max(1, len(ts) - 1)

            if hard:
                cand = [n for n in in_mix if n not in (ia, ib)]
                if len(cand) < 4:
                    continue
                rng.shuffle(cand)
                negs = cand[:N_NEG]
            else:
                draw = rng.choice(pool, size=N_NEG + 4, replace=False)
                negs = [int(n) for n in draw if n not in (ia, ib)][:N_NEG]

            bpm_a = bpm_of.get(A["y"], 0.0)
            for cand_i, is_true in [(ib, 1)] + [(int(n), 0) for n in negs]:
                yid = None
                for yy, ii in ((A["y"], ia), (B["y"], ib)):
                    if ii == cand_i:
                        yid = yy
                bpm_b = bpm_of.get(yid, 0.0) if yid else _bpm_by_index(bpm_of, idx, cand_i)
                X.append([
                    float(M[ia] @ M[cand_i]),
                    fold_bpm(bpm_a, bpm_b),
                    (bpm_b / bpm_a) if (bpm_b and bpm_a) else 1.0,
                    pos,
                    float(ctx @ M[cand_i]),
                    1.0 if bpm_b else 0.0,      # czy w ogóle znamy tempo kandydata
                ])
                y.append(is_true)
                g.append(m["mix"])
                q.append(qid)
            qid += 1

    return (np.asarray(X, dtype=np.float32), np.asarray(y),
            np.asarray(g), np.asarray(q))


_REV: dict[int, str] = {}


def _bpm_by_index(bpm_of, idx, i: int) -> float:
    if not _REV:
        _REV.update({v: k for k, v in idx.items()})
    return bpm_of.get(_REV.get(i, ""), 0.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="both", choices=["logit", "gbm", "both"])
    args = ap.parse_args()

    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold
    from sklearn.preprocessing import StandardScaler

    idx, M, mixes = load_corpus()
    bpm_of = global_bpm(mixes)
    print(f"  tempo znane dla {len(bpm_of)} utworów korpusu\n", flush=True)

    COLS = ["clap_cos", "bpm_diff", "bpm_ratio", "pos", "clap_ctx", "bpm_known"]

    for hard in (False, True):
        label = ("PULA TRUDNA — kandydaci z TEGO SAMEGO miksu"
                 if hard else "pula łatwa — kandydaci z całego korpusu")
        X, y, g, q = build(idx, M, mixes, bpm_of, hard)
        if not len(y):
            print(f"\n{label}: brak danych")
            continue
        nq = len(set(q.tolist()))
        print("═" * 66)
        print(label)
        print("═" * 66)
        print(f"  {len(y)} wierszy · {nq} przejść · {len(set(g))} miksów", flush=True)

        variants = {
            "tylko CLAP": [0],
            "CLAP + kontekst setu": [0, 4],
            "CLAP + kontekst + tempo": [0, 1, 2, 4, 5],
            "wszystko (z pozycją)": list(range(X.shape[1])),
        }
        print(f"\n  {'wariant':<28} {'percentyl':>10} {'top-1':>7} {'top-5':>7}")
        print("  " + "─" * 56)
        print(f"  {'losowo':<28} {0.500:10.3f} {100/(N_NEG+1):6.1f}% "
              f"{min(100.0, 100*5/(N_NEG+1)):6.1f}%")

        for name, cols in variants.items():
            Xv = X[:, cols]
            proba = np.zeros(len(y))
            for tr, te in GroupKFold(n_splits=N_FOLDS).split(Xv, y, groups=g):
                sc = StandardScaler().fit(Xv[tr])
                mdl = LogisticRegression(C=1.0, max_iter=1000)
                mdl.fit(sc.transform(Xv[tr]), y[tr])
                proba[te] = mdl.predict_proba(sc.transform(Xv[te]))[:, 1]

            pcts, t1, t5, n = [], 0, 0, 0
            for qq in sorted(set(q.tolist())):
                sel = q == qq
                s, yy = proba[sel], y[sel]
                order = np.argsort(-s)
                hit = np.where(yy[order] == 1)[0]
                if not len(hit):
                    continue
                rank = int(hit[0]) + 1
                pcts.append(1 - (rank - 1) / len(s))
                t1 += rank == 1
                t5 += rank <= 5
                n += 1
            print(f"  {name:<28} {np.mean(pcts):10.3f} "
                  f"{100*t1/n:6.1f}% {100*t5/n:6.1f}%")

        sc = StandardScaler().fit(X)
        mdl = LogisticRegression(C=1.0, max_iter=1000).fit(sc.transform(X), y)
        print("\n  wagi (na cechach skalowanych):")
        for c, w in sorted(zip(COLS, mdl.coef_[0]), key=lambda t: -abs(t[1])):
            print(f"    {c:<12} {w:+.3f}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
