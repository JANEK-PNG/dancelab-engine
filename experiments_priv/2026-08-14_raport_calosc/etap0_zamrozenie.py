"""ETAP 0 — zamrożenie wszechświata + sprawdzenie podziału.

Wszystko, co policzymy dalej, ma sens wyłącznie wtedy, gdy (a) liczy się na
DOKŁADNIE tym samym zbiorze co poprzedni bieg i (b) podział train/test nie
przecieka. Ten skrypt sprawdza jedno i drugie, i zapisuje zamrożony artefakt
z odciskiem palca.

Sprawdzane są trzy rodzaje przecieku, od najgroźniejszego:

  1. MIKS w dwóch częściach naraz — unieważnia wszystko, bo te same przejścia
     byłyby w treningu i w teście.
  2. UTWÓR w dwóch częściach — sam w sobie NIE jest wadą (model uczy się cech,
     nie tożsamości utworu), ale trzeba znać skalę, żeby nie tłumaczyć nią
     dobrego wyniku.
  3. DJ w dwóch częściach — dotyczy wyłącznie LHEI; raport i tak rozdziela
     `known_dj_count` od `unseen_dj_count`, więc to pomiar, nie alarm.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

KATALOG = pathlib.Path(__file__).parent
KORZEN = KATALOG.parents[1]
RAPORTY = KORZEN / "data" / "reports" / "corpus_ordering"


def main() -> int:
    from dancelab.validation.djmix.ordering_models import (
        eligible_five_model_observations,
        load_ordering_feature_catalog,
        split_ordering_observations,
    )

    sys.path.insert(0, str(KATALOG))
    from drabina_piec_modeli import wczytaj_zbior  # noqa: E402

    katalog = load_ordering_feature_catalog(KATALOG / "features_lipiec.json")
    pelny, _ = wczytaj_zbior()
    kwal = eligible_five_model_observations(pelny, katalog)

    # POPRAWKA po audycie: bliźniacze miksy (identyczny ciąg wybranych utworów
    # pod dwoma mix_id) przeciekają przez podział, bo podział pilnuje mix_id,
    # a nie treści. Zostaje ten o mniejszym identyfikatorze — wybór arbitralny,
    # ale deterministyczny.
    from collections import defaultdict
    po_miksie = defaultdict(list)
    for o in kwal:
        po_miksie[o.mix_id].append(o)
    podpis: dict[tuple, list[str]] = defaultdict(list)
    for mid, obs in po_miksie.items():
        klucz = tuple(o.selected_track_id
                      for o in sorted(obs, key=lambda x: (x.run_id, x.position)))
        podpis[klucz].append(mid)
    odrzucone = sorted(m for grupa in podpis.values() if len(grupa) > 1
                       for m in sorted(grupa)[1:])
    if odrzucone:
        print(f"bliźniaki usunięte: {odrzucone}")
        kwal = tuple(o for o in kwal if o.mix_id not in set(odrzucone))

    print(f"wszechświat: {len(kwal)} obserwacji · "
          f"{len({o.mix_id for o in kwal})} miksów · "
          f"{len({o.dj_id for o in kwal})} DJ-ów")

    czesci = split_ordering_observations(kwal)
    print("\nPODZIAŁ")
    for n, cz in czesci.items():
        print(f"  {n:11s} {len(cz):5d} obserwacji · {len({o.mix_id for o in cz}):4d} miksów")

    def zbior(cz, pole):
        if pole == "track":
            s = set()
            for o in cz:
                s |= set(o.history_track_ids) | set(o.candidate_track_ids)
                s.add(o.selected_track_id)
            return s
        return {getattr(o, pole) for o in cz}

    print("\nPRZECIEK")
    wynik = {}
    for pole, etykieta, grozny in (("mix_id", "miks", True),
                                   ("track", "utwór", False),
                                   ("dj_id", "DJ", False)):
        tr, te = zbior(czesci["train"], pole), zbior(czesci["test"], pole)
        wsp = tr & te
        udzial = 100 * len(wsp) / len(te) if te else 0.0
        flaga = "  ⛔ BLOKUJE" if (grozny and wsp) else ""
        print(f"  {etykieta:6s} wspólnych train∩test: {len(wsp):5d} "
              f"= {udzial:5.1f}% zbioru testowego{flaga}")
        wynik[pole] = {"wspolnych": len(wsp), "udzial_testu_proc": round(udzial, 2)}

    if wynik["mix_id"]["wspolnych"]:
        print("\nPRZERWANE: miks trafił do treningu i do testu naraz.")
        return 2

    # --- zamrożenie ---
    zamrozony = {
        "schema_version": "wszechswiat-drabiny-v1",
        "opis": "obserwacje z kompletem dowodów H+E+DJ, podstawa analiz LIPCOWA",
        "obserwacje": [
            {"mix_id": o.mix_id, "run_id": o.run_id, "position": o.position,
             "history_track_ids": list(o.history_track_ids),
             "candidate_track_ids": list(o.candidate_track_ids),
             "selected_track_id": o.selected_track_id,
             "genre_labels": list(o.genre_labels), "dj_id": o.dj_id}
            for o in kwal
        ],
        "katalog_cech_odcisk": katalog.fingerprint,
        "zbior_zrodlowy_odcisk": pelny.fingerprint,
        "podzial": {n: sorted({o.mix_id for o in cz}) for n, cz in czesci.items()},
        "przeciek": wynik,
        "usuniete_blizniaki": odrzucone,
        # ZASTRZEŻENIA jadą razem z danymi, żeby nie dało się zacytować liczby
        # bez nich. Wszystkie zmierzone w audycie i QC etapu 0.
        "zastrzezenia": {
            "kandydaci_z_tego_samego_miksu_proc": None,   # wypełniane niżej
            "zadanie": "wybór następnika ze zbioru kandydatów o medianie 3 pozycji, "
                       "w większości pochodzących z tracklisty TEGO SAMEGO miksu — "
                       "to NIE jest wybór z biblioteki",
            "test_latwiejszy_od_treningu": None,          # wypełniane niżej
            "porownania_miedzy_modelami": "ważne — wszystkie modele liczone na tym "
                                          "samym zbiorze testowym; nierówność części "
                                          "przesuwa liczby bezwzględne, nie kolejność",
        },
    }

    # domiar zastrzeżeń
    import statistics
    grane_w_miksie: dict[str, set] = {}
    for o in kwal:
        s = grane_w_miksie.setdefault(o.mix_id, set())
        s |= set(o.history_track_ids)
        s.add(o.selected_track_id)
    z_miksu = sum(1 for o in kwal for c in o.candidate_track_ids
                  if c in grane_w_miksie[o.mix_id])
    wszyscy = sum(len(o.candidate_track_ids) for o in kwal)
    zamrozony["zastrzezenia"]["kandydaci_z_tego_samego_miksu_proc"] = round(
        100 * z_miksu / wszyscy, 1)
    slepy = {n: round(100 * sum(1 / len(o.candidate_track_ids) for o in cz) / len(cz), 1)
             for n, cz in czesci.items()}
    srednie = {n: round(statistics.mean(len(o.candidate_track_ids) for o in cz), 2)
               for n, cz in czesci.items()}
    zamrozony["zastrzezenia"]["test_latwiejszy_od_treningu"] = {
        "slepy_top1_proc": slepy, "srednio_kandydatow": srednie}
    print(f"\nZASTRZEŻENIA wpisane do artefaktu:")
    print(f"  kandydaci z tego samego miksu: "
          f"{zamrozony['zastrzezenia']['kandydaci_z_tego_samego_miksu_proc']}%")
    print(f"  ślepy top-1 wg części: {slepy}")
    tresc = json.dumps(zamrozony, ensure_ascii=False, sort_keys=True)
    odcisk = hashlib.sha256(tresc.encode()).hexdigest()
    zamrozony["odcisk"] = odcisk
    cel = KATALOG / "wszechswiat_zamrozony.json"
    cel.write_text(json.dumps(zamrozony, ensure_ascii=False), encoding="utf-8")
    print(f"\nZAMROŻONE: {cel.name}")
    print(f"  odcisk: {odcisk}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
