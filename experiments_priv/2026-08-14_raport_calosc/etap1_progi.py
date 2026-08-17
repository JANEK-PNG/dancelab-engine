"""ETAP 1 — punkt odniesienia dla odmowy + progi zapisane PRZED biegiem.

Po co: żeby nie dało się później dopasować kryterium do wyniku. Wszystko tutaj
liczy się BEZ ŻADNEGO MODELU, na zamrożonym zbiorze testowym z etapu 0.

Kluczowa obserwacja, która ustawia poprzeczkę: zbiory kandydatów są malutkie
(mediana 3). „Oddaj wszystkich kandydatów" daje więc pokrycie 100% przy średnim
rozmiarze ~3,1 — i to jest darmowe. Predykcja konforemna ma sens WYŁĄCZNIE
wtedy, gdy przy zadanym pokryciu oddaje zbiór wyraźnie mniejszy niż stała
liczba kandydatów potrzebna do tego samego pokrycia.

TRZY PROGI, rejestrowane teraz:

  P1 · KALIBRACJA. Zmierzone pokrycie mieści się w ±3 pkt proc. od zadanego.
       Bez tego mechanizm nie jest tym, za co się podaje.

  P2 · OSZCZĘDNOŚĆ. Średni rozmiar zbioru konforemnego jest MNIEJSZY niż
       najmniejsze stałe k dające to samo pokrycie. Inaczej zmienny rozmiar
       nic nie kupuje i prościej wziąć stałe top-k.

  P3 · ODMOWA DZIAŁA. Zbiór ma być większy tam, gdzie model się myli.
       Miara: średni rozmiar zbioru dla obserwacji, w których prawidłowa
       odpowiedź NIE jest na pierwszym miejscu, MINUS średni rozmiar tam,
       gdzie jest. Wymagane: dodatnie i większe niż 0,25 pozycji.

P3 jest najważniejszy. P1 i P2 może spełnić mechanizm, który tylko ładnie
skaluje próg. Dopiero P3 mówi, że model wie, GDZIE nie wie — a to jest jedyna
niespełniona przesłanka z 01.08.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import statistics
import sys
from collections import Counter

KATALOG = pathlib.Path(__file__).parent


def main() -> int:
    from dancelab.validation.djmix.ordering import OrderingObservation
    from dancelab.validation.djmix.ordering_models import split_ordering_observations

    zamr = json.loads((KATALOG / "wszechswiat_zamrozony.json").read_text(encoding="utf-8"))
    obs = tuple(
        OrderingObservation(
            mix_id=o["mix_id"], run_id=o["run_id"], position=o["position"],
            history_track_ids=tuple(o["history_track_ids"]),
            candidate_track_ids=tuple(o["candidate_track_ids"]),
            selected_track_id=o["selected_track_id"],
            genre_labels=tuple(o["genre_labels"]), dj_id=o["dj_id"])
        for o in zamr["obserwacje"])
    czesci = split_ordering_observations(obs)
    test = czesci["test"]
    kal = czesci["validation"]
    print(f"zbiór testowy: {len(test)} obserwacji · "
          f"kalibracyjny: {len(kal)}")

    rozmiary = [len(o.candidate_track_ids) for o in test]
    print(f"\nkandydaci w teście: średnio {statistics.mean(rozmiary):.2f} · "
          f"mediana {statistics.median(rozmiary):.0f} · "
          f"min {min(rozmiary)} · maks {max(rozmiary)}")
    print(f"rozkład: {dict(sorted(Counter(rozmiary).items()))}")

    # --- punkt odniesienia: LOSOWY zbiór stałego rozmiaru k ---
    # pokrycie = szansa, że prawidłowy kandydat wpadnie do losowych k z n
    print("\nPUNKT ODNIESIENIA — losowy zbiór stałego rozmiaru k")
    print(f"{'k':>3s} {'pokrycie':>10s} {'śr. rozmiar':>12s}")
    krzywa = {}
    for k in range(1, max(rozmiary) + 1):
        pokrycie = statistics.mean(min(k, n) / n for n in rozmiary)
        sredni = statistics.mean(min(k, n) for n in rozmiary)
        krzywa[k] = {"pokrycie": round(pokrycie, 4), "sredni_rozmiar": round(sredni, 3)}
        if k <= 6 or k == max(rozmiary):
            print(f"{k:3d} {100*pokrycie:9.1f}% {sredni:12.2f}")

    # najmniejsze stale k dla progow pokrycia
    print("\nnajmniejsze STAŁE k dające zadane pokrycie (to jest poprzeczka dla P2)")
    poprzeczki = {}
    for cel in (0.70, 0.80, 0.90, 0.95):
        wybrane = next((k for k in krzywa if krzywa[k]["pokrycie"] >= cel), None)
        if wybrane:
            poprzeczki[str(cel)] = {
                "k": wybrane,
                "pokrycie": krzywa[wybrane]["pokrycie"],
                "sredni_rozmiar": krzywa[wybrane]["sredni_rozmiar"],
            }
            print(f"  cel {100*cel:4.0f}%  →  k = {wybrane}  "
                  f"(realne {100*krzywa[wybrane]['pokrycie']:.1f}%, "
                  f"średni rozmiar {krzywa[wybrane]['sredni_rozmiar']:.2f})")
        else:
            print(f"  cel {100*cel:4.0f}%  →  nieosiągalne stałym k")

    # --- darmowy wariant: oddaj wszystko ---
    print(f"\n„oddaj wszystkich kandydatów”: pokrycie 100,0% · "
          f"średni rozmiar {statistics.mean(rozmiary):.2f}  ← to jest za darmo")

    progi = {
        "schema_version": "progi-odmowy-v1",
        "zapisane_przed": "policzeniem czegokolwiek konforemnego",
        "wszechswiat_odcisk": zamr["odcisk"],
        "test_obserwacji": len(test),
        "kalibracja_obserwacji": len(kal),
        "P1_kalibracja": {
            "warunek": "|pokrycie zmierzone − pokrycie zadane| ≤ 3 pkt proc.",
            "cel_domyslny": 0.90,
        },
        "P2_oszczednosc": {
            # POPRAWKA po audycie etapu 1, wprowadzona PRZED policzeniem
            # czegokolwiek konforemnego: pierwsza wersja porównywała z losowym
            # podzbiorem stałego rozmiaru. To za słaba poprzeczka — realnym
            # konkurentem predykcji konforemnej jest stałe top-k WEDŁUG MODELU,
            # które bije losowe. Poprzeczką jest więc top-k modelu; krzywa
            # losowa zostaje jako podłoga zdrowego rozsądku.
            "warunek": "średni rozmiar zbioru konforemnego < średni rozmiar "
                       "stałego top-k WEDŁUG MODELU o tym samym pokryciu "
                       "(liczone na tym samym zbiorze testowym w etapie 2)",
            "poprzeczka_glowna": "stałe top-k modelu LE — do policzenia w etapie 2",
            "podloga_losowa": poprzeczki,
            "darmowy_wariant_oddaj_wszystko": {
                "pokrycie": 1.0,
                "sredni_rozmiar": statistics.mean(rozmiary),
            },
            "poprawka": "P2 wzmocnione po audycie etapu 1; żaden wynik "
                        "konforemny nie był wtedy jeszcze policzony",
        },
        "P3_odmowa_dziala": {
            "warunek": "średni rozmiar zbioru przy BŁĘDNYM pierwszym strzale "
                       "minus przy trafionym ≥ 0,25 pozycji",
            "prog": 0.25,
            "dlaczego": "P1 i P2 może spełnić samo skalowanie progu; dopiero to "
                        "pokazuje, że model wie, GDZIE nie wie",
        },
        "krzywa_losowa": krzywa,
    }
    tresc = json.dumps(progi, ensure_ascii=False, sort_keys=True)
    progi["odcisk"] = hashlib.sha256(tresc.encode()).hexdigest()
    cel = KATALOG / "progi_odmowy.json"
    cel.write_text(json.dumps(progi, ensure_ascii=False), encoding="utf-8")
    print(f"\nPROGI ZAPISANE: {cel.name}")
    print(f"  odcisk: {progi['odcisk']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
