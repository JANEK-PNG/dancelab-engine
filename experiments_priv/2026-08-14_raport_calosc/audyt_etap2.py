"""AUDYT NARASTAJĄCY — etapy 0, 1 i 2, każdy z osobna i wszystkie wobec siebie.

Poza powtórką poprzednich audytów sprawdzam tu dwie rzeczy, które przy
oglądaniu wyniku etapu 2 wyglądają na zdolne go unieważnić:

  K1 · ZBIEŻNOŚĆ. Model zgłosił `zbiezny=False` po 400 iteracjach. Jeśli
       optymalizacja się nie domknęła, to wszystkie prawdopodobieństwa — a więc
       i cała konforemna — stoją na modelu zatrzymanym w pół kroku.

  K2 · MIARA P3 JEST SKAŻONA. P3 mierzy różnicę średniego rozmiaru zbioru
       przy pudle i przy trafieniu. Ale PUSTY zbiór ma rozmiar 0, a pusty
       zbiór to najsilniejsza możliwa odmowa. Przy 90% jest ich 11, przy 70%
       aż 48 — więc miara liczy najostrzejsze odmowy jako „model był pewny".
       To jest ten sam błąd co miernik pokazujący zero, bo mierzy nie to.

Sprawdzam też zgodność MIĘDZY etapami, w tym jedną, która jest niezależnym
potwierdzeniem: stałe top-1 modelu z etapu 2 musi równać się trafności LE
z drabiny, bo to ta sama liczba policzona dwiema drogami.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

KATALOG = pathlib.Path(__file__).parent


def main() -> int:
    problemy: list[str] = []
    uwagi: list[str] = []

    print("═══ ETAPY 0–1 — powtórka ═══")
    w = subprocess.run([sys.executable, str(KATALOG / "audyt_etap1.py")],
                       capture_output=True, text=True)
    ogon = [x for x in w.stdout.splitlines() if x.strip()]
    print("\n".join(ogon[-10:]))
    if w.returncode != 0:
        problemy.append("audyt etapów 0–1 przestał przechodzić")

    zamr = json.loads((KATALOG / "wszechswiat_zamrozony.json").read_text(encoding="utf-8"))
    progi = json.loads((KATALOG / "progi_odmowy.json").read_text(encoding="utf-8"))
    e2 = json.loads((KATALOG / "etap2_wynik.json").read_text(encoding="utf-8"))
    drab = json.loads((KATALOG / "drabina_wynik.json").read_text(encoding="utf-8"))

    print("\n═══ SPÓJNOŚĆ 0 ↔ 1 ↔ 2 ═══")
    ok1 = e2["wszechswiat_odcisk"] == zamr["odcisk"]
    ok2 = e2["progi_odcisk"] == progi["odcisk"]
    print(f"S1. etap 2 na zamrożonym wszechświecie: {'OK' if ok1 else 'INNY'}")
    print(f"S2. etap 2 wobec progów z etapu 1:      {'OK' if ok2 else 'INNE'}")
    if not ok1:
        problemy.append("etap 2 liczył na innym wszechświecie niż etap 0")
    if not ok2:
        problemy.append("etap 2 użył innych progów niż zapisane w etapie 1")

    # S3 — niezależne potwierdzenie: top-1 modelu = trafność LE z drabiny
    top1 = e2["stale_topk_modelu"]["1"]["pokrycie"]
    le = drab["test_metrics"]["LE"]["top1_accuracy"]
    ok3 = abs(top1 - le) < 0.001
    print(f"S3. top-1 modelu z etapu 2 = trafność LE z drabiny: "
          f"{'OK' if ok3 else 'ROZJAZD'} ({100*top1:.1f}% vs {100*le:.1f}%)")
    if not ok3:
        problemy.append("ta sama liczba wyszła inaczej w etapie 2 i w drabinie")

    # S4 — pokrycie stałego top-k nie może być NIŻSZE niż losowego
    print("S4. stałe top-k modelu bije losowe (inaczej model jest gorszy od losu):")
    gorsze = []
    for k, w2 in e2["stale_topk_modelu"].items():
        los = progi["krzywa_losowa"].get(k)
        if los and w2["pokrycie"] < los["pokrycie"] - 0.001:
            gorsze.append((k, w2["pokrycie"], los["pokrycie"]))
    if gorsze:
        for k, a, b in gorsze[:4]:
            print(f"    k={k}: model {100*a:.1f}% < los {100*b:.1f}%")
        uwagi.append(f"dla {len(gorsze)} wartości k model przegrywa z losowaniem")
    else:
        print("    OK dla wszystkich k")

    print("\n═══ KRYTYKA ETAPU 2 ═══")
    # K1 zbieżność
    zb = e2["model"]["zbiezny"]
    stabilny = e2["model"].get("cel_stabilny")
    sonda = e2["model"].get("sonda_zbieznosci") or []
    print(f"K1. flaga zbieżności: {'zapalona' if zb else 'NIEZAPALONA'} · "
          f"funkcja celu stabilna przy {len(sonda)} limitach iteracji: "
          f"{'TAK' if stabilny else 'NIE'}")
    for x in sonda:
        print(f"      limit {x['limit']:6d} → cel {x['cel']:.9f}")
    if not zb and not stabilny:
        uwagi.append("model nie osiągnął zbieżności ANI stabilnej funkcji celu")
    elif not zb and stabilny:
        print("    → optymalizacja stoi w miejscu mimo 75× więcej iteracji;")
        print("      flaga jest fałszywym alarmem, wynik na niej nie stoi.")

    # K2 skażenie P3
    g = e2["konforemna"]["0.9"]
    puste = g["pustych"]
    print(f"K2. pustych zbiorów przy 90%: {puste} z 166 "
          f"({100*puste/166:.1f}%) — a pusty zbiór to NAJSILNIEJSZA odmowa,")
    print(f"    liczona przez P3 jako rozmiar 0, czyli jako „model był pewny”.")
    naprawione = "P3_odmowa_roznica" in g
    print(f"    miara odmowy rozdzielona od miary rozmiaru: "
          f"{'OK' if naprawione else 'NIE'}")
    if not naprawione:
        uwagi.append("P3 skażone: pusty zbiór (odmowa) wchodzi do średniej jako "
                     "rozmiar 0; potrzebna osobna miara odmowy")

    # K3 — czy P3 jest ujemne przy niższych celach (to sygnał, nie szum)
    ujemne = [c for c, v in e2["konforemna"].items() if v["P3_roznica"] < 0]
    if not ujemne:
        print("K3. P3 dodatnie dla WSZYSTKICH celów — wcześniejsze wartości "
              "ujemne były artefaktem liczenia pustych zbiorów jako rozmiar 0.")
    if ujemne:
        print(f"K3. P3 UJEMNE dla celów {sorted(ujemne)} — zbiór jest MNIEJSZY "
              f"tam, gdzie model się myli.")
        print(f"    To nie jest brak sygnału, tylko sygnał odwrotny do żądanego.")
        uwagi.append("P3 ujemne przy niższych celach — sprawdzić po naprawie K2, "
                     "czy to artefakt pustych zbiorów")

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
