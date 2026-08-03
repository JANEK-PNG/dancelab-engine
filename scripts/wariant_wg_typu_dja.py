"""Czy wariant pomaga WSZYSTKIM DJ-om, czy tylko tym przewidywalnym.

Decyzja Janka (2026-08-03): produkt przestaje być strojony pod niego. Ale
„pod DJ-a" bez wskazania KTÓREGO jest pustym celem — zmierzone 01.08 na
60 miksach: percentyl bazowy rozkłada się od 0,44 do 0,97. To nie jest szum,
to są dwa różne sposoby grania.

Dlatego średnia po korpusie jest złą miarą produktu. Wariant, który podnosi
średnią, może to robić WYŁĄCZNIE na DJ-ach zachowawczych — czyli tych, którym
podpowiedzi są najmniej potrzebne, bo ich następny utwór i tak jest oczywisty.
DJ nieprzewidywalny, któremu silnik mógłby realnie pomóc, zostaje z tyłu,
a średnia tego nie pokaże.

Więc mierzymy trzy liczby zamiast jednej:

  * średnia po wszystkich miksach (to, co widzieliśmy do tej pory),
  * DJ-e ZACHOWAWCZY — górna tercja percentyla bazowego,
  * DJ-e NIEPRZEWIDYWALNI — dolna tercja.

Wariant przyjmujemy, jeśli podnosi dolną tercję. Wariant podnoszący wyłącznie
górną jest odrzucany, choćby średnia rosła.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark_przejsc import core_score, load_features            # noqa: E402

MIXES = pathlib.Path("/Volumes/MY_PC/DanceLabCorpus/djmix-dataset.json")


def unit(d) -> dict:
    out = {}
    for k, v in d.items():
        a = np.asarray(v, dtype=np.float32)
        n = float(np.linalg.norm(a))
        if n > 0:
            out[k] = a / n
    return out


def mix_percentile(pairs, exclude, feats, emb, ids, w) -> float:
    ranks = []
    for a, b in pairs:
        cand = [c for c in ids if c == b or c not in exclude]
        if len(cand) < 40:
            continue
        fa, ea = feats[a], emb.get(a)
        sc = []
        for c in cand:
            s = core_score(fa, feats[c])
            if w and ea is not None:
                ec = emb.get(c)
                if ec is not None:
                    s = (1 - w) * s + w * float((np.dot(ea, ec) + 1) / 2)
            sc.append((s, c))
        sc.sort(reverse=True)
        ranks.append(1 - ([c for _, c in sc].index(b)) / len(cand))
    return float(np.mean(ranks)) if ranks else float("nan")


def main() -> int:
    feats = load_features(None)
    emb = unit(json.loads(
        (ROOT / "data/reports/corpus_embeddings_full.json").read_text())["tracks"])
    ids = list(feats)

    mixes = json.loads(MIXES.read_text())
    sel = []
    for m in mixes:
        t = [x.get("id") for x in (m.get("tracklist") or []) if x.get("id")]
        pr = [(t[i], t[i + 1]) for i in range(len(t) - 1)
              if t[i] in feats and t[i + 1] in feats]
        if len(pr) >= 10:
            sel.append((m.get("title", "")[:44], pr[:14], set(t)))
    rng = np.random.default_rng(11)
    rng.shuffle(sel)
    sel = sel[:45]
    print(f"miksów w teście: {len(sel)}", flush=True)

    base = [(mix_percentile(pr, ex, feats, emb, ids, 0.0), title, pr, ex)
            for title, pr, ex in sel]
    base.sort()
    k = len(base) // 3
    grupy = {"nieprzewidywalni": base[:k], "środek": base[k:2 * k],
             "zachowawczy": base[2 * k:]}
    print(f"\n{'wariant':>22} │ {'wszyscy':>8} │ {'nieprzew.':>9} │ {'środek':>8} │ {'zachow.':>8}")
    print("─" * 68)
    for w in (0.0, 0.30, 0.60):
        row = {}
        for name, grp in grupy.items():
            row[name] = float(np.mean([
                mix_percentile(pr, ex, feats, emb, ids, w) for _, _, pr, ex in grp]))
        wszyscy = float(np.mean(list(row.values())))
        label = "dziś (bez brzmienia)" if w == 0 else f"brzmienie {w:.2f}"
        print(f"{label:>22} │ {wszyscy:>8.4f} │ {row['nieprzewidywalni']:>9.4f} │ "
              f"{row['środek']:>8.4f} │ {row['zachowawczy']:>8.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
