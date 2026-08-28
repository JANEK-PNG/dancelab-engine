"""Dlaczego 133 przejścia ze 158 mają identyczną, maksymalną punktację.

Ślepy odsłuch (29.08) pokazał, że wynik silnika prawie nie różnicuje: przy
maksymalnej punktacji ucho daje średnio 4,01, poniżej 2,84 — czyli sygnał
jest, ale tylko w 25 oflagowanych przejściach. Dla pozostałych 133 silnik
mówi „wszystko idealne" i nie umie wybrać między dwoma dobrymi przejściami.

Ten skrypt NICZEGO nie zmienia w silniku. Rozkłada wynik na składowe
(harmonia, tempo, energia, mixability, brzmienie, prior korpusowy) dla tych
samych 158 przejść i pokazuje, gdzie ginie rozdzielczość. Diagnoza przed
naprawą — inaczej „naprawa" trafia w miejsce, które nie było zepsute.
"""

from __future__ import annotations

import csv
import json
import pathlib

import numpy as np

TU = pathlib.Path(__file__).parent
ROOT = TU.parents[1]
OCENY = ROOT / "experiments_priv/2026-08-17_ocena_papierowa"
PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"


def opis(nazwa: str, w: np.ndarray) -> str:
    unikalnych = len(np.unique(np.round(w, 4)))
    return (f"{nazwa:<14} min {w.min():.3f}  mediana {np.median(w):.3f}  "
            f"max {w.max():.3f}  odch {w.std():.3f}  "
            f"unikalnych {unikalnych:3d}/{len(w)}  "
            f"=max: {int((np.round(w, 4) >= np.round(w.max(), 4)).sum()):3d}")


def main() -> int:
    from dancelab.core.config import load_weights
    from dancelab.decision.mixability import (MixabilityInput,
                                              compute_mixability,
                                              precompute_mixability_inputs)
    from dancelab.decision.harmonic import harmonic_compatibility
    from dancelab.decision.set_builder import (_energy_score,
                                               _planner_component_weights,
                                               bpm_score)
    from dancelab.decision.sound_affinity import blend, cosine_affinity
    from dancelab.storage.repositories import FileAnalysisRepository
    from dancelab.tui.duplikaty import scal

    dane = json.loads((OCENY / "playlisty_dane.json").read_text(encoding="utf-8"))
    potrzebne = {t["track_id"] for lista in dane.values() for t in lista}
    repo = FileAnalysisRepository(PROCESSED)
    widok, _ = scal([repo.get(t) for t in repo.list_track_ids()])
    by_id = {a.track.track_id: a for a in widok if a.track.track_id in potrzebne}

    W = load_weights("configs/descriptor_weights.yaml")
    pre = precompute_mixability_inputs(by_id.values())
    zmierzone = {t: m["rms"] for t, m in pre.feature_means.items()
                 if m["rms"] is not None}
    e_min, e_max = min(zmierzone.values()), max(zmierzone.values())
    e_range = (e_max - e_min) or 1.0
    mediana = float(np.median(list(zmierzone.values())))
    energia = {t: float(zmierzone.get(t, mediana)) for t in by_id}

    wagi = _planner_component_weights(W, "smart")
    sound_w = getattr(W, "sound_affinity_weight", 0.0) or 0.0
    prior_w = getattr(W, "corpus_priors_weight", 0.0) or 0.0
    print(f"wagi składowych: {dict(wagi)}")
    print(f"waga brzmienia: {sound_w} · waga priorów korpusu: {prior_w}\n")

    oceny: dict[tuple[str, str], int] = {}
    for p in sorted(OCENY.glob("SESJA_*_transition_ratings.csv")):
        for r in csv.DictReader(p.open(encoding="utf-8")):
            oceny[(r["track_id_a"], r["track_id_b"])] = int(r["dj_mixability_rating"])

    kol: dict[str, list] = {k: [] for k in
                            ("harmonia", "tempo", "energia", "mixability",
                             "rdzeń", "po brzmieniu", "po priorze", "ucho",
                             "lift", "playlista")}
    pary_playlist = {}
    for nazwa, lista in dane.items():
        for i in range(len(lista) - 1):
            pary_playlist[(lista[i]["track_id"], lista[i + 1]["track_id"])] = nazwa
    for (ta, tb), ocena in oceny.items():
        a, b = by_id[ta], by_id[tb]
        harm = harmonic_compatibility(a.track.key_estimate, b.track.key_estimate,
                                      a.track.key_confidence, b.track.key_confidence)
        h = harm.harmonic_compatibility_score
        bp = bpm_score(a.track.bpm_estimate, b.track.bpm_estimate)
        d_e = (energia[tb] - energia[ta]) / (e_range + 1e-9)
        en = _energy_score(d_e, "off")
        mix = compute_mixability(MixabilityInput(track_a=a, track_b=b, context=None),
                                 W.mixability, W.mixability_conflict,
                                 precomputed=pre).mixability_score
        rdzen = (wagi["harmonic"] * h + wagi["bpm"] * bp
                 + wagi["energy"] * en + wagi["mixability"] * mix)
        po_brzm = rdzen
        if sound_w > 0:
            aff = cosine_affinity(a.track.sound_embedding, b.track.sound_embedding)
            po_brzm, _ = blend(rdzen, aff, sound_w)
        po_prior = po_brzm
        from dancelab.decision.corpus_priors import transition_prior_lift
        lift, _ = transition_prior_lift(harm.harmonic_relation,
                                        a.track.bpm_estimate, b.track.bpm_estimate)
        if prior_w > 0 and lift != 1.0:
            po_prior = min(1.0, max(0.0, po_brzm * (lift ** prior_w)))
        for k, v in (("harmonia", h), ("tempo", bp), ("energia", en),
                     ("mixability", mix), ("rdzeń", rdzen),
                     ("po brzmieniu", po_brzm), ("po priorze", po_prior),
                     ("ucho", float(ocena)), ("lift", float(lift)),
                     ("playlista", pary_playlist[(ta, tb)])):
            kol[k].append(v)

    print("ROZKŁADY (158 przejść):")
    for k in ("harmonia", "tempo", "energia", "mixability",
              "rdzeń", "po brzmieniu", "po priorze"):
        print("  " + opis(k, np.array(kol[k])))

    from scipy.stats import spearmanr
    ucho = np.array(kol["ucho"])
    print("\nZGODNOŚĆ Z UCHEM (Spearman, im wyżej tym lepiej):")
    for k in ("harmonia", "tempo", "energia", "mixability",
              "rdzeń", "po brzmieniu", "po priorze"):
        w = np.array(kol[k])
        rho = float(spearmanr(w, ucho).statistic) if w.std() > 0 else float("nan")
        print(f"  {k:<14} rho {rho:+.3f}")

    (TU / "skladowe.json").write_text(
        json.dumps({k: (v if k == "playlista"
                        else [round(float(x), 5) for x in v])
                    for k, v in kol.items()}, ensure_ascii=False),
        encoding="utf-8")
    (TU / "meta.json").write_text(
        json.dumps({"wagi": dict(wagi), "prior_w": prior_w,
                    "sound_w": sound_w}, ensure_ascii=False), encoding="utf-8")
    print(f"\nzapisane składowe → {TU / 'skladowe.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
