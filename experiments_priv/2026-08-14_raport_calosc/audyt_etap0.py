"""AUDYT ETAPU 0 — czy zamrożony wszechświat i podział naprawdę trzymają.

ŹRÓDŁEM PRAWDY JEST ARTEFAKT, nie ponowne wyliczenie. Pierwsza wersja tego
audytu odtwarzała zbiór od zera i po pierwszej poprawce zaczęła się z nim nie
zgadzać — czyli sprawdzała własną kopię reguł zamiast umowy. To jest dokładnie
ten rodzaj miernika, który pokazuje zero, bo mierzy nie to.

Sprawdzane:
  A. odcisk odtwarza się z zapisanej treści
  B. podział zapisany w artefakcie jest rozłączny i pokrywa cały zbiór
  C. ponowne wywołanie podziału daje to samo, co zapisano
  D. w zamrożonym zbiorze nie ma już bliźniaczych miksów
  E. zastrzeżenia w artefakcie zgadzają się z przeliczeniem z jego danych
  F. czy wynik drabiny liczył się na TYM wszechświecie (jeśli nie — wymaga
     przeliczenia, i to jest stan do zaraportowania, nie awaria)
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import statistics
import sys
from collections import Counter, defaultdict

KATALOG = pathlib.Path(__file__).parent


def main() -> int:
    zamr = json.loads((KATALOG / "wszechswiat_zamrozony.json").read_text(encoding="utf-8"))
    obs = zamr["obserwacje"]
    problemy: list[str] = []
    uwagi: list[str] = []

    # A. odcisk
    kopia = {k: v for k, v in zamr.items() if k != "odcisk"}
    ponownie = hashlib.sha256(
        json.dumps(kopia, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    ok_a = ponownie == zamr["odcisk"]
    print(f"A. odcisk odtwarza się z treści: {'OK' if ok_a else 'NIE'}")
    if not ok_a:
        problemy.append("odcisk nie odtwarza się z zapisanej treści")

    # B. podział rozłączny i pełny
    p = zamr["podzial"]
    wszystkie = {o["mix_id"] for o in obs}
    suma, przeciecia = set(), []
    for a in p:
        for b in p:
            if a < b and set(p[a]) & set(p[b]):
                przeciecia.append((a, b))
        suma |= set(p[a])
    ok_b = not przeciecia and suma == wszystkie
    print(f"B. podział rozłączny i pełny: {'OK' if ok_b else 'NIE'} "
          f"(miksów w podziale {len(suma)}, w zbiorze {len(wszystkie)})")
    if not ok_b:
        problemy.append(f"podział wadliwy: przecięcia {przeciecia}, "
                        f"brakuje {len(wszystkie - suma)} miksów")

    # C. podział powtarzalny
    from dancelab.validation.djmix.ordering import OrderingObservation
    from dancelab.validation.djmix.ordering_models import split_ordering_observations
    odtworzone = tuple(
        OrderingObservation(
            mix_id=o["mix_id"], run_id=o["run_id"], position=o["position"],
            history_track_ids=tuple(o["history_track_ids"]),
            candidate_track_ids=tuple(o["candidate_track_ids"]),
            selected_track_id=o["selected_track_id"],
            genre_labels=tuple(o["genre_labels"]), dj_id=o["dj_id"])
        for o in obs)
    cz = split_ordering_observations(odtworzone)
    ok_c = all(sorted({x.mix_id for x in cz[k]}) == p[k] for k in cz)
    print(f"C. podział powtarzalny: {'OK' if ok_c else 'ROZJAZD'}")
    if not ok_c:
        problemy.append("ponowny podział daje inny wynik niż zapisany")

    # D. bliźniaki
    po_miksie = defaultdict(list)
    for o in obs:
        po_miksie[o["mix_id"]].append(o)
    podpisy = Counter()
    for mid, lista in po_miksie.items():
        lista = sorted(lista, key=lambda x: (x["run_id"], x["position"]))
        podpisy[tuple(x["selected_token"] if False else x["selected_track_id"]
                      for x in lista)] += 1
    blizn = sum(1 for n in podpisy.values() if n > 1)
    print(f"D. bliźniacze miksy w zamrożonym zbiorze: {blizn} "
          f"(usunięto wcześniej: {zamr.get('usuniete_blizniaki')})")
    if blizn:
        problemy.append(f"{blizn} grup bliźniaczych miksów nadal w zbiorze")

    # E. zastrzeżenia zgodne z danymi
    z = zamr["zastrzezenia"]
    grane = {}
    for o in obs:
        s = grane.setdefault(o["mix_id"], set())
        s |= set(o["history_track_ids"]); s.add(o["selected_track_id"])
    zm = sum(1 for o in obs for c in o["candidate_track_ids"] if c in grane[o["mix_id"]])
    wsz = sum(len(o["candidate_track_ids"]) for o in obs)
    policzone = round(100 * zm / wsz, 1)
    ok_e1 = abs(policzone - z["kandydaci_z_tego_samego_miksu_proc"]) < 0.05
    slepy = {n: round(100 * sum(1/len(x.candidate_track_ids) for x in cz[n]) / len(cz[n]), 1)
             for n in cz}
    ok_e2 = slepy == z["test_latwiejszy_od_treningu"]["slepy_top1_proc"]
    print(f"E. zastrzeżenia zgodne z danymi: kandydaci-z-miksu "
          f"{'OK' if ok_e1 else 'ROZJAZD'} ({policzone}%) · ślepy top-1 "
          f"{'OK' if ok_e2 else 'ROZJAZD'} ({slepy})")
    if not (ok_e1 and ok_e2):
        problemy.append("zastrzeżenia w artefakcie nie zgadzają się z jego danymi")

    # F. czy drabina liczyła się na tym wszechświecie
    wynik = KATALOG / "drabina_wynik.json"
    if wynik.exists():
        r = json.loads(wynik.read_text(encoding="utf-8"))
        ile = r["readiness"]["eligible_observations"]
        zgodne = ile == len(obs) and \
            r["feature_catalog_fingerprint"] == zamr["katalog_cech_odcisk"]
        print(f"F. drabina liczona na tym wszechświecie: "
              f"{'OK' if zgodne else f'NIE ({ile} vs {len(obs)}) → wymaga przeliczenia'}")
        if not zgodne:
            uwagi.append(f"wynik drabiny pochodzi z {ile} obserwacji, "
                         f"a wszechświat ma {len(obs)} — przeliczyć")
    print()
    if problemy:
        print(f"PROBLEMY: {len(problemy)}")
        for x in problemy:
            print("  ⛔", x)
    if uwagi:
        print(f"DO ZROBIENIA: {len(uwagi)}")
        for x in uwagi:
            print("  →", x)
    if not problemy and not uwagi:
        print("AUDYT CZYSTY")
    return 1 if problemy else 0


if __name__ == "__main__":
    sys.exit(main())
