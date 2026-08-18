"""AUDYT ETAPU 5 — czy wynik negatywny jest prawdziwy, czy pomiar był ślepy.

Etap 5 dał rho = +0,015 (p = 0,85): nowość zapytania NIE przewiduje, gdzie
model się myli. Zanim to ogłoszę, trzy pytania, które mogą ten wynik obalić:

  G1 · GĘSTOŚĆ. Może nowość nie działa, bo W TEJ PULI nowość nie istnieje —
       każdy utwór ma bliskiego bliźniaka w treningu. Mierzę rozkład
       odległości do najbliższego sąsiada. Jeśli przestrzeń jest gęsta,
       wynik negatywny znaczy „sygnał nie ma się czego chwycić", a nie
       „nowość nie ma znaczenia". To są dwa różne zdania.

  G2 · SPÓJNOŚĆ Z ETAPEM 4. Mediany pozycji w tercylach (16/19/17) muszą
       zgadzać się z medianą 17 z etapu 4 — to ten sam model i zbiór,
       policzone niezależnie.

  G3 · EKSPLORACJA (bez progu, wyraźnie oznaczona). Nowość ZAPYTANIA nie
       działa — a nowość PO STRONIE KANDYDATÓW? Dostępna w chwili predykcji:
       nowość kandydata wskazanego przez model na 1. miejscu. Liczona TERAZ,
       po zobaczeniu wyniku głównego, więc NIE wolno jej ogłosić jako wynik —
       najwyżej jako hipotezę do zarejestrowania na przyszłość.
"""

from __future__ import annotations

import json
import pathlib
import statistics
import sys

import numpy as np

KATALOG = pathlib.Path(__file__).parent
sys.path.insert(0, str(KATALOG))


def main() -> int:
    from dancelab.validation.djmix.ordering_models import (
        OrderingTrainingConfig, fit_conditional_ordering_model,
        load_ordering_feature_catalog, split_ordering_observations)
    from etap2_konforemna import prawdopodobienstwa, wczytaj_obserwacje
    from etap5_nowosc import los, spearman

    e4 = json.loads((KATALOG / "etap4_wynik.json").read_text(encoding="utf-8"))
    e5 = json.loads((KATALOG / "etap5_wynik.json").read_text(encoding="utf-8"))
    zamr = json.loads((KATALOG / "wszechswiat_zamrozony.json").read_text(encoding="utf-8"))
    problemy, uwagi = [], []

    ok = e5["wszechswiat_odcisk"] == zamr["odcisk"] == e4["wszechswiat_odcisk"]
    print(f"S1. etapy 4 i 5 na tym samym zamrożonym wszechświecie: "
          f"{'OK' if ok else 'NIE'}")
    if not ok:
        problemy.append("etap 5 na innym wszechświecie")

    katalog = load_ordering_feature_catalog(KATALOG / "features_lipiec.json")
    pula = sorted(katalog.tracks)
    wek = np.asarray([katalog.tracks[t].embedding for t in pula], dtype=np.float64)
    wek /= (np.linalg.norm(wek, axis=1, keepdims=True) + 1e-12)

    # G1 — gęstość przestrzeni: odległość każdego utworu do najbliższego INNEGO
    print("\nG1 · GĘSTOŚĆ PRZESTRZENI BRZMIENIA (cała pula, 2855 utworów)")
    podob = wek @ wek.T
    np.fill_diagonal(podob, -1.0)
    najblizszy = 1.0 - podob.max(axis=1)
    print(f"  odległość do najbliższego sąsiada: "
          f"p10 {np.percentile(najblizszy, 10):.4f} · "
          f"mediana {np.median(najblizszy):.4f} · "
          f"p90 {np.percentile(najblizszy, 90):.4f} · "
          f"maks {najblizszy.max():.4f}")
    med_nn = float(np.median(najblizszy))
    med_now = e5["wyniki"]["latwy"]["nowosc_min_med_max"][1]
    print(f"  mediana NOWOŚCI zapytań ({med_now:.3f}) vs mediana odległości "
          f"sąsiada w puli ({med_nn:.4f})")
    if med_now < 0.12:
        uwagi.append(
            f"przestrzeń jest GĘSTA: mediana nowości {med_now:.3f} — połowa "
            f"zapytań ma w treningu utwór odległy o mniej niż 0,08 kosinusa; "
            f"sygnał nie miał się czego chwycić")

    # G2 — spójność z etapem 4
    med_e4 = None
    print("\nG2 · SPÓJNOŚĆ Z ETAPEM 4")
    terc = e5["wyniki"]["latwy"]["tercyle_mediana_pozycji"]
    print(f"  tercyle etapu 5 (łatwy): {[round(x) for x in terc]} — "
          f"etap 4 podał medianę pozycji 17")
    if not (10 <= statistics.median(terc) <= 25):
        problemy.append("mediany pozycji w etapie 5 nie zgadzają się z etapem 4")
    else:
        print("  zgodne ✓")

    # G3 — EKSPLORACJA: nowość kandydata z 1. miejsca (dostępna w predykcji)
    print("\nG3 · EKSPLORACJA (po zobaczeniu wyniku — NIE jest to wynik)")
    # odtwarzamy zbiór łatwy identycznie jak etap 5
    import etap5_nowosc as E5
    from dancelab.validation.djmix.ordering import OrderingObservation
    stare = wczytaj_obserwacje(zamr)
    poz = {t: i for i, t in enumerate(pula)}

    def przebuduj(obs):
        out = []
        for o in obs:
            g = los(f"latwy|{o.run_id}|{o.position}")
            zak = set(o.history_track_ids) | {o.selected_track_id}
            kand = [pula[i] for i in g.choice(len(pula), size=E5.N * 2, replace=False)]
            kand = [k for k in kand if k not in zak][:E5.N - 1]
            out.append(OrderingObservation(
                mix_id=o.mix_id, run_id=o.run_id, position=o.position,
                history_track_ids=o.history_track_ids,
                candidate_track_ids=tuple(sorted(set([o.selected_track_id] + kand))),
                selected_track_id=o.selected_track_id,
                genre_labels=o.genre_labels, dj_id=o.dj_id))
        return tuple(out)

    obs = przebuduj(stare)
    cz = split_ordering_observations(obs)
    tr, te = cz["train"], cz["test"]
    widziane = set()
    for o in tr:
        widziane |= set(o.history_track_ids)
        widziane.add(o.current_track_id)
        widziane.add(o.selected_track_id)
    wt = wek[[poz[t] for t in sorted(widziane)]]

    def nowosc(tid):
        return float(1.0 - np.max(wt @ wek[poz[tid]]))

    m = fit_conditional_ordering_model(
        tr, katalog, family="E", config=OrderingTrainingConfig(max_iterations=2000))
    p_te = prawdopodobienstwa(m, te, katalog)
    now_top, pozycje = [], []
    for o, p in zip(te, p_te):
        i = o.candidate_track_ids.index(o.selected_track_id)
        pozycje.append(int(np.where(np.argsort(-p) == i)[0][0]) + 1)
        now_top.append(nowosc(o.candidate_track_ids[int(np.argmax(p))]))
    rho, pval = spearman(now_top, pozycje)
    print(f"  nowość kandydata z 1. miejsca vs pozycja prawdy: "
          f"rho {rho:+.3f}  p {pval:.4f}")
    print("  (gdyby coś tu było, to jest HIPOTEZA do zarejestrowania na świeżych"
          " danych, nie wynik)")

    print()
    if problemy:
        print(f"PROBLEMY: {len(problemy)}")
        for x in problemy:
            print("  ⛔", x)
    else:
        print("POMIAR WIARYGODNY — wynik negatywny stoi.")
    for x in uwagi:
        print("  →", x)
    return 1 if problemy else 0


if __name__ == "__main__":
    raise SystemExit(main())
