"""ETAP 4 — przebudowa zadania treningowego tak, żeby wyglądało jak produkt.

DLACZEGO
--------
Dotąd model uczył się wybierać 1 z 3 kandydatów, z których 71,1% pochodziło
z tracklisty TEGO SAMEGO miksu. Czyli spośród utworów, które ten DJ i tak
zagrał tego wieczoru. Produkt pyta o coś innego: 1 z ~236, z całej biblioteki.

Tu zmieniamy WYŁĄCZNIE listę kandydatów. Model, kod treningu i cała drabina
zostają nietknięte — `candidate_track_ids` przyjmuje dowolną długość.

PUŁAPKA, NA KTÓRĄ PROJEKT PRZEJECHAŁ SIĘ TRZY RAZY
--------------------------------------------------
Negatyw musi być NIEODRÓŻNIALNY OD POZYTYWU PO POCHODZENIU. 02.08 model
dostawał punkty za rozpoznanie, czy wektor pochodzi z 30-sekundowej próbki
czy z pełnego pliku (AUC 0,889). Ta sama rodzina błędu: „tempo puste" i
`bpm_known`.

Tutaj wszystkie 2855 utworów mają cechy z jednego źródła (h_analysis lipiec
+ te same wektory), więc rozróżnienie po źródle nie istnieje z konstrukcji.
Zostaje drugie ryzyko: negatyw losowany z całej puli może być trywialnie
odrzucalny po tempie. Dlatego liczymy DWA warianty i porównujemy:

  ŁATWY   — negatywy losowane jednorodnie z całej puli
  TRUDNY  — negatywy losowane z tego samego pasma tempa co pozytyw

Jeśli model wygrywa tylko w łatwym, to znaczy, że nauczył się tempa, a nie
szwu — i trzeba to wiedzieć, zanim ktokolwiek nazwie to sukcesem.

CO POWINNO WYJŚĆ (przewidywanie zapisane PRZED biegiem)
-------------------------------------------------------
Ślepy punkt odniesienia spada z 37,5% na ~0,5% (1 z 200). Jeśli po zmianie
model dalej daje ~46%, to NIE jest sukces — to znak, że coś przecieka.
Spodziewam się top-1 rzędu kilku procent i top-20 rzędu kilkunastu.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import statistics
import sys

import numpy as np

KATALOG = pathlib.Path(__file__).parent
sys.path.insert(0, str(KATALOG))

KANDYDATOW = 200          # mediana puli Janka to 236
ZIARNO = "dancelab-zadanie-produktowe-v1"


def _los(klucz: str) -> np.random.Generator:
    """Deterministyczny generator — ten sam zbiór przy każdym biegu."""
    ziarno = int(hashlib.sha256((ZIARNO + klucz).encode()).hexdigest()[:16], 16)
    return np.random.default_rng(ziarno)


def main() -> int:
    from dancelab.validation.djmix.ordering import (
        CorpusOrderingDataset, OrderingObservation)
    from dancelab.validation.djmix.ordering_models import (
        OrderingTrainingConfig, evaluate_conditional_ordering_model,
        fit_conditional_ordering_model, load_ordering_feature_catalog,
        split_ordering_observations, uniform_ordering_metrics)
    from etap2_konforemna import wczytaj_obserwacje

    zamr = json.loads((KATALOG / "wszechswiat_zamrozony.json").read_text(encoding="utf-8"))
    katalog = load_ordering_feature_catalog(KATALOG / "features_lipiec.json")
    stare = wczytaj_obserwacje(zamr)
    pula = sorted(katalog.tracks)
    print(f"pula utworów z cechami: {len(pula)}")
    print(f"obserwacji: {len(stare)} · kandydatów na obserwację: "
          f"{statistics.mean(len(o.candidate_track_ids) for o in stare):.2f} → {KANDYDATOW}")

    # pasma tempa z cech rzemieślniczych nie są tu dostępne wprost, więc
    # „podobieństwo" definiujemy w przestrzeni brzmienia — to jedyna cecha,
    # co do której wiemy, że niesie sygnał. Wariant TRUDNY losuje negatywy
    # spośród najbliższych brzmieniowo, czyli takich, których nie da się
    # odrzucić „bo brzmi zupełnie inaczej".
    wektory = np.asarray([katalog.tracks[t].embedding for t in pula], dtype=np.float64)
    wektory /= (np.linalg.norm(wektory, axis=1, keepdims=True) + 1e-12)
    poz = {t: i for i, t in enumerate(pula)}

    def przebuduj(obserwacje, tryb: str):
        nowe = []
        for o in obserwacje:
            g = _los(f"{tryb}|{o.run_id}|{o.position}")
            zakazane = set(o.history_track_ids) | {o.selected_track_id}
            if tryb == "latwy":
                kand = [pula[i] for i in g.choice(len(pula), size=KANDYDATOW * 2,
                                                  replace=False)]
            else:
                # 800 najbliższych brzmieniowo do utworu grającego, z nich losujemy
                v = wektory[poz[o.current_track_id]]
                bliscy = np.argsort(-(wektory @ v))[:800]
                wyb = g.choice(len(bliscy), size=min(KANDYDATOW * 2, len(bliscy)),
                               replace=False)
                kand = [pula[bliscy[i]] for i in wyb]
            kand = [k for k in kand if k not in zakazane][:KANDYDATOW - 1]
            # Kolejność MUSI być kanoniczna (sortowana) — `OrderingObservation`
            # tego pilnuje i słusznie: gdyby prawidłowa odpowiedź stała zawsze
            # w tym samym miejscu listy, model nauczyłby się pozycji.
            lista = sorted(set([o.selected_track_id] + kand))
            nowe.append(OrderingObservation(
                mix_id=o.mix_id, run_id=o.run_id, position=o.position,
                history_track_ids=o.history_track_ids,
                candidate_track_ids=tuple(lista),
                selected_track_id=o.selected_track_id,
                genre_labels=o.genre_labels, dj_id=o.dj_id))
        return tuple(nowe)

    wyniki = {}
    for tryb in ("latwy", "trudny"):
        print(f"\n{'='*62}\nWARIANT: {tryb.upper()}\n{'='*62}")
        obs = przebuduj(stare, tryb)
        cz = split_ordering_observations(obs)
        tr, te = cz["train"], cz["test"]
        sr = statistics.mean(len(o.candidate_track_ids) for o in te)
        print(f"kandydatów w teście: {sr:.1f}")

        slepy = uniform_ordering_metrics(te)
        print(f"ŚLEPY   top-1 {100*slepy.top1_accuracy:5.2f}%  MRR {slepy.mean_reciprocal_rank:.4f}")

        row = {"kandydatow": sr, "slepy_top1": slepy.top1_accuracy,
               "slepy_mrr": slepy.mean_reciprocal_rank}
        for nazwa, rodzina in (("LE", "E"), ("LH", "H")):
            m = fit_conditional_ordering_model(
                tr, katalog, family=rodzina,
                config=OrderingTrainingConfig(max_iterations=2000))
            met = evaluate_conditional_ordering_model(m, te, katalog)
            print(f"{nazwa:6s}  top-1 {100*met.top1_accuracy:5.2f}%  "
                  f"MRR {met.mean_reciprocal_rank:.4f}  "
                  f"NLL/obs {met.mean_nll:.4f}  "
                  f"(×{met.top1_accuracy/max(slepy.top1_accuracy,1e-9):.1f} nad ślepym)")
            row[nazwa] = {"top1": met.top1_accuracy, "mrr": met.mean_reciprocal_rank,
                          "mean_nll": met.mean_nll,
                          "krotnosc_nad_slepym": met.top1_accuracy / max(slepy.top1_accuracy, 1e-9)}
        wyniki[tryb] = row

    print(f"\n{'='*62}\nODCZYT\n{'='*62}")
    l, t = wyniki["latwy"], wyniki["trudny"]
    print(f"LE nad ślepym:  łatwy ×{l['LE']['krotnosc_nad_slepym']:.1f} · "
          f"trudny ×{t['LE']['krotnosc_nad_slepym']:.1f}")
    if t["LE"]["krotnosc_nad_slepym"] < 0.5 * l["LE"]["krotnosc_nad_slepym"]:
        print("  ⇒ przewaga znika, gdy negatywy brzmią podobnie: model odrzucał")
        print("    kandydatów po tym, że brzmią zupełnie inaczej, nie po szwie.")
    else:
        print("  ⇒ przewaga zostaje także przy negatywach brzmiących podobnie.")

    (KATALOG / "etap4_wynik.json").write_text(json.dumps({
        "wszechswiat_odcisk": zamr["odcisk"], "kandydatow": KANDYDATOW,
        "ziarno": ZIARNO, "wyniki": wyniki}, ensure_ascii=False), encoding="utf-8")
    print("\nzapisano: etap4_wynik.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
