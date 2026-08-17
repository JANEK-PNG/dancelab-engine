"""AUDYT NARASTAJĄCY — etapy 0 i 1, każdy z osobna i oba wobec siebie.

Zasada: etap N sprawdza etapy 1..N i ich wzajemną zgodność. Tu więc:
  · powtórka całego audytu etapu 0 (nie ufam, że dalej przechodzi),
  · sprawdzenie etapu 1,
  · sprawdzenie SPÓJNOŚCI między nimi — bo etap 1 liczył na zbiorze
    testowym, który musi być dokładnie tym z etapu 0.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import statistics
import subprocess
import sys

KATALOG = pathlib.Path(__file__).parent


def main() -> int:
    problemy: list[str] = []
    uwagi: list[str] = []

    # ---------- ETAP 0, powtórka ----------
    print("═══ ETAP 0 — powtórka pełnego audytu ═══")
    wynik = subprocess.run(
        [sys.executable, str(KATALOG / "audyt_etap0.py")],
        capture_output=True, text=True)
    print(wynik.stdout.rstrip())
    if wynik.returncode != 0:
        problemy.append("audyt etapu 0 przestał przechodzić")

    # ---------- ETAP 1 ----------
    print("\n═══ ETAP 1 — progi odmowy ═══")
    progi = json.loads((KATALOG / "progi_odmowy.json").read_text(encoding="utf-8"))
    zamr = json.loads((KATALOG / "wszechswiat_zamrozony.json").read_text(encoding="utf-8"))

    kopia = {k: v for k, v in progi.items() if k != "odcisk"}
    ok = hashlib.sha256(
        json.dumps(kopia, ensure_ascii=False, sort_keys=True).encode()).hexdigest() \
        == progi["odcisk"]
    print(f"1A. odcisk progów odtwarza się: {'OK' if ok else 'NIE'}")
    if not ok:
        problemy.append("odcisk progów nie odtwarza się z treści")

    # ---------- SPÓJNOŚĆ 0 ↔ 1 ----------
    print("\n═══ SPÓJNOŚĆ ETAP 0 ↔ ETAP 1 ═══")
    ten_sam = progi["wszechswiat_odcisk"] == zamr["odcisk"]
    print(f"S1. progi liczone na zamrożonym wszechświecie: {'OK' if ten_sam else 'INNY'}")
    if not ten_sam:
        problemy.append("progi policzone na innym wszechświecie niż zamrożony")

    from dancelab.validation.djmix.ordering import OrderingObservation
    from dancelab.validation.djmix.ordering_models import split_ordering_observations
    obs = tuple(
        OrderingObservation(
            mix_id=o["mix_id"], run_id=o["run_id"], position=o["position"],
            history_track_ids=tuple(o["history_track_ids"]),
            candidate_track_ids=tuple(o["candidate_track_ids"]),
            selected_track_id=o["selected_track_id"],
            genre_labels=tuple(o["genre_labels"]), dj_id=o["dj_id"])
        for o in zamr["obserwacje"])
    cz = split_ordering_observations(obs)
    zgodny_test = len(cz["test"]) == progi["test_obserwacji"]
    zgodna_kal = len(cz["validation"]) == progi["kalibracja_obserwacji"]
    print(f"S2. rozmiar testu {'OK' if zgodny_test else 'ROZJAZD'} "
          f"({len(cz['test'])} vs {progi['test_obserwacji']}) · "
          f"kalibracji {'OK' if zgodna_kal else 'ROZJAZD'}")
    if not (zgodny_test and zgodna_kal):
        problemy.append("etap 1 liczył na innym podziale niż etap 0")

    # S3: krzywa losowa przeliczona niezależnie
    rozm = [len(o.candidate_track_ids) for o in cz["test"]]
    zgodne = True
    for k, w in progi["krzywa_losowa"].items():
        p = statistics.mean(min(int(k), n) / n for n in rozm)
        if abs(p - w["pokrycie"]) > 0.0005:
            zgodne = False
    print(f"S3. krzywa losowa przelicza się niezależnie: {'OK' if zgodne else 'ROZJAZD'}")
    if not zgodne:
        problemy.append("krzywa punktu odniesienia nie odtwarza się")

    # S4: czy zastrzeżenie o „test łatwiejszy” z etapu 0 zgadza się z etapem 1
    slepy_e0 = zamr["zastrzezenia"]["test_latwiejszy_od_treningu"]["slepy_top1_proc"]["test"]
    slepy_e1 = 100 * progi["krzywa_losowa"]["1"]["pokrycie"]
    ok_s4 = abs(slepy_e0 - slepy_e1) < 0.1
    print(f"S4. ślepy top-1 zgodny między etapami: {'OK' if ok_s4 else 'ROZJAZD'} "
          f"({slepy_e0}% vs {slepy_e1:.1f}%)")
    if not ok_s4:
        problemy.append("ślepy punkt odniesienia różni się między etapami 0 i 1")

    # ---------- KRYTYKA WŁASNYCH PROGÓW ----------
    print("\n═══ KRYTYKA PROGÓW (czy mierzą to, co trzeba) ═══")
    p2 = progi["P2_oszczednosc"]
    wzmocnione = "top-k WEDŁUG MODELU" in p2["warunek"]
    print(f"K1. P2 mierzy się z właściwym konkurentem: "
          f"{'OK — stałe top-k modelu' if wzmocnione else 'NIE — tylko losowy podzbiór'}")
    if not wzmocnione:
        uwagi.append("P2 wymaga poprawki: poprzeczką ma być stałe top-k modelu, "
                     "nie losowy podzbiór")
    darmo = p2["darmowy_wariant_oddaj_wszystko"]
    k90 = p2.get("podloga_losowa", p2.get("poprzeczki_stalego_k", {})).get("0.9", {})
    print(f"K2. okno, w którym konforemna ma szansę coś udowodnić, jest wąskie:")
    print(f"    stałe k=4 daje {100*k90.get('pokrycie',0):.1f}% przy rozmiarze "
          f"{k90.get('sredni_rozmiar'):.2f}, a „oddaj wszystko” "
          f"{darmo['sredni_rozmiar']:.2f} przy 100%.")

    print()
    if problemy:
        print(f"PROBLEMY: {len(problemy)}")
        for x in problemy:
            print("  ⛔", x)
    if uwagi:
        print(f"DO POPRAWY: {len(uwagi)}")
        for x in uwagi:
            print("  →", x)
    if not problemy and not uwagi:
        print("AUDYT CZYSTY")
    return 1 if problemy else 0


if __name__ == "__main__":
    sys.exit(main())
