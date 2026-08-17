"""Drabina pięciu modeli kolejności (L0 / LH / LE / LHE / LHEI) — pierwszy bieg.

DLACZEGO TEN SKRYPT ISTNIEJE
----------------------------
Drabina była zbudowana w lipcu i **nigdy się nie policzyła**. Raport bramki
(`data/reports/corpus_ordering/model_gate.json`, 21.07) podaje dwie blokady:

    H incomplete:           26 / 2881 utworów
    DJ identity incomplete: 96 / 433  miksów

Bramka działa `fail_closed` na ZAMROŻONYM zbiorze — wymaga stu procent pokrycia.
96 miksów nie ma zaufanej tożsamości DJ-a i **nigdy jej nie dostanie**, bo
polityka zabrania czytać nazwiska z tytułu (`dj_identity_from_titles_or_
general_tags: False`). Przy zamrożonym zbiorze bramka nie może więc otworzyć
się sama, nigdy. To jest spór definicyjny, nie brak pracy.

CO ROBI TEN SKRYPT — i czego NIE robi
-------------------------------------
NIE osłabia bramki. `assess_ordering_model_readiness` zostaje nietknięte i dalej
wymaga stu procent. Zamiast tego **zawężamy WSZECHŚWIAT do obserwacji, które
mają komplet dowodów**, i zapisujemy w audycie dokładnie, co wypadło i dlaczego.
Wynik wolno czytać wyłącznie jako „drabina na tym podzbiorze", nigdy jako
„drabina na korpusie".

Zmierzony koszt zawężenia (14.08, na `dataset.json` z 20.07):

    sam wymóg tożsamości DJ-a   443 / 1604 obserwacji (27,6%)
    same siatki bitów (lipiec)   46 / 1604 obserwacji ( 2,9%)
    zostaje                    1122 / 1604 obserwacji (69,9%)
                               330 miksów · 198 DJ-ów

Podstawa to analiza LIPCOWA (`h_analysis`), nie sierpniowa. Zmierzone: nowa
analiza z 01–04.08 ma dla tego korpusu **90 niewiarygodnych siatek wobec 26** —
naprawiła 16, zepsuła 80, i zostawia 981 obserwacji zamiast 1122. Dlaczego
sztywna siatka, lepsza na bibliotece Janka (1,7 wobec 8,0 milibitu na 183
utworach), wypada tu gorzej — jest osobnym pytaniem i NIE jest tu rozstrzygane.
"""

from __future__ import annotations

import json
import pathlib
import sys

KATALOG = pathlib.Path(__file__).parent
KORZEN = KATALOG.parents[1]
RAPORTY = KORZEN / "data" / "reports" / "corpus_ordering"


def wczytaj_zbior():
    from dancelab.validation.djmix.ordering import (
        CorpusOrderingDataset,
        OrderingObservation,
    )

    surowy = json.loads((RAPORTY / "dataset.json").read_text(encoding="utf-8"))
    obserwacje = tuple(
        OrderingObservation(
            mix_id=o["mix_id"],
            run_id=o["run_id"],
            position=o["position"],
            history_track_ids=tuple(o["history_track_ids"]),
            candidate_track_ids=tuple(o["candidate_track_ids"]),
            selected_track_id=o["selected_track_id"],
            genre_labels=tuple(o.get("genre_labels") or ()),
            dj_id=o.get("dj_id"),
        )
        for o in surowy["observations"]
    )
    return CorpusOrderingDataset(
        observations=obserwacje,
        audit=surowy["audit"],
        fingerprint=surowy["fingerprint"],
        schema_version=surowy["schema_version"],
    ), surowy


def main() -> int:
    from dancelab.validation.djmix.ordering import CorpusOrderingDataset  # noqa
    from dancelab.validation.djmix.ordering_models import (
        OrderingTrainingConfig,
        assess_ordering_model_readiness,
        eligible_five_model_observations,
        load_ordering_feature_catalog,
        train_five_model_ordering_evaluation,
        write_five_model_ordering_report,
    )

    from dancelab.validation.djmix.ordering import OrderingObservation

    katalog = load_ordering_feature_catalog(KATALOG / "features_lipiec.json")
    pelny, surowy = wczytaj_zbior()

    # ETAP 0: jeśli istnieje zamrożony wszechświat, jest on JEDYNYM źródłem
    # prawdy. Bez tego każdy bieg liczyłby się na trochę innym zbiorze —
    # dokładnie tak powstał rozjazd 1122 vs 1121 po usunięciu bliźniaka.
    zamr_plik = KATALOG / "wszechswiat_zamrozony.json"
    zamrozony = None
    if zamr_plik.exists():
        zamrozony = json.loads(zamr_plik.read_text(encoding="utf-8"))
        if zamrozony["katalog_cech_odcisk"] != katalog.fingerprint:
            print("PRZERWANE: katalog cech nie zgadza się z zamrożonym wszechświatem")
            return 2
        # Zamrożenie usuwa WYŁĄCZNIE bliźniacze miksy. Odsiewanie obserwacji
        # bez kompletu dowodów należy do `eligible_five_model_observations` —
        # gdyby robić je tu, raport bramki podawałby zaniżony mianownik
        # i przestałby mówić prawdę o tym, ile zbioru odpada.
        usuniete = set(zamrozony.get("usuniete_blizniaki") or ())
        if usuniete:
            pelny = CorpusOrderingDataset(
                observations=tuple(o for o in pelny.observations
                                   if o.mix_id not in usuniete),
                audit=pelny.audit, fingerprint=pelny.fingerprint,
                schema_version=pelny.schema_version)
        print(f"wszechświat zamrożony: odcisk {zamrozony['odcisk'][:16]}… · "
              f"{len(zamrozony['obserwacje'])} obserwacji "
              f"(usunięte bliźniaki: {sorted(usuniete) or 'brak'})")

    stan = assess_ordering_model_readiness(pelny, katalog)
    print("PEŁNY ZBIÓR — stan bramki")
    print(f"  obserwacji:            {stan.total_observations}")
    print(f"  z kompletem dowodów:   {stan.eligible_observations}")
    print(f"  bez cech H/E:          {stan.missing_feature_observations}")
    print(f"  bez tożsamości DJ-a:   {stan.missing_dj_observations}")
    print(f"  gotowa do drabiny:     {stan.ready_for_five_models}")
    for b in stan.blockers:
        print(f"  - {b}")

    kwalifikowane = eligible_five_model_observations(pelny, katalog)
    if not kwalifikowane:
        print("\nBRAK obserwacji z kompletem dowodów — nie ma czego liczyć.")
        return 2

    audyt = dict(surowy["audit"])
    audyt["zawezenie_14_08"] = {
        "powod": "bramka fail_closed na zamrożonym zbiorze nigdy się nie otworzy: "
                 "96 miksów nie ma i nie będzie miało zaufanej tożsamości DJ-a",
        "obserwacje_przed": stan.total_observations,
        "obserwacje_po": len(kwalifikowane),
        "odrzucone_brak_cech": stan.missing_feature_observations,
        "odrzucone_brak_dj": stan.missing_dj_observations,
        "podstawa_analiz": "h_analysis (lipiec) — 2855 utworów",
        "czytac_jako": "drabina NA TYM PODZBIORZE, nigdy jako drabina na korpusie",
    }
    zawezony = CorpusOrderingDataset(
        observations=kwalifikowane,
        audit=audyt,
        fingerprint=pelny.fingerprint,
        schema_version=pelny.schema_version,
    )

    print(f"\nZAWĘŻONY ZBIÓR: {len(kwalifikowane)} obserwacji · "
          f"{len(zawezony.mix_ids)} miksów")
    print("Liczę drabinę…\n")

    raport = train_five_model_ordering_evaluation(
        zawezony, katalog, config=OrderingTrainingConfig()
    )

    print("WYNIK NA ZBIORZE TESTOWYM")
    print(f"{'model':6s} {'NLL':>10s} {'top-1':>9s}")
    for nazwa, m in raport.test_metrics.items():
        print(f"{nazwa:6s} {m.total_nll:10.4f} {m.top1_accuracy:8.1%}")

    d = raport.decomposition
    print("\nROZKŁAD")
    print(f"  C_rule       {d.c_rule:.3f}   (ile wnoszą cechy rzemieślnicze)")
    print(f"  C_similarity {d.c_similarity:.3f}   (ile wnosi brzmienie)")
    for pole in ("interaction", "i_dj", "n_residual", "n", "i"):
        if hasattr(d, pole):
            print(f"  {pole:12s} {getattr(d, pole):.3f}")

    cel = KATALOG / "drabina_wynik.json"
    write_five_model_ordering_report(raport, cel, include_model_parameters=False)
    print(f"\nzapisano: {cel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
