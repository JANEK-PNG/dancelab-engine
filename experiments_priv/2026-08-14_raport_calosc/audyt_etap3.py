"""AUDYT NARASTAJĄCY 1–3 + POMIAR SPRZĘŻENIA MIĘDZY ETAPAMI.

Kontrola negatywna z etapu 3 wypadła źle: konforemna nad L0 — rozkładem
jednorodnym, który z definicji nic nie wie — dała pokrycie 91,0%, rozmiar 2,53
i sygnał odmowy +12,2 pkt proc., czyli MOCNIEJSZY niż nad LE (+7,5).

Zanim ogłoszę, że etap 2 jest do wyrzucenia, muszę sprawdzić, skąd ten sygnał
u L0 się bierze. Hipoteza, którą stawiam PRZED liczeniem:

    L0 daje wszystkim kandydatom p = 1/n, więc zbiór jest albo PEŁNY
    (gdy 1/n ≥ próg), albo PUSTY (gdy 1/n < próg) — zależnie WYŁĄCZNIE
    od liczby kandydatów. Model „odmawia" wtedy, gdy kandydatów jest dużo,
    a dużo kandydatów to po prostu trudniejsze pytanie.

Jeśli tak, to P3 nie mierzy wiedzy modelu, tylko liczebność zbioru kandydatów —
i trzeba je liczyć WEWNĄTRZ warstw o tej samej liczbie kandydatów.

SPRZĘŻENIE, które mierzę:
  E1→E2  czy krzywa punktu odniesienia z etapu 1 przewiduje rozmiary z etapu 2
  E1→E3  czy zachowanie L0 daje się wyprowadzić z samego rozkładu liczby
         kandydatów (czyli z etapu 1), bez żadnego modelu
  E2↔E3  czy LE odróżnia się od L0 po odjęciu wpływu liczby kandydatów
"""

from __future__ import annotations

import json
import pathlib
import statistics
import subprocess
import sys
from collections import defaultdict

import numpy as np

KATALOG = pathlib.Path(__file__).parent
sys.path.insert(0, str(KATALOG))


def main() -> int:
    problemy: list[str] = []
    uwagi: list[str] = []

    print("═══ ETAPY 0–2 — powtórka ═══")
    w = subprocess.run([sys.executable, str(KATALOG / "audyt_etap2.py")],
                       capture_output=True, text=True)
    ogon = [x for x in w.stdout.splitlines() if x.strip()]
    print("\n".join(ogon[-8:]))
    if w.returncode != 0:
        problemy.append("audyt etapów 0–2 przestał przechodzić")

    zamr = json.loads((KATALOG / "wszechswiat_zamrozony.json").read_text(encoding="utf-8"))
    progi = json.loads((KATALOG / "progi_odmowy.json").read_text(encoding="utf-8"))
    e2 = json.loads((KATALOG / "etap2_wynik.json").read_text(encoding="utf-8"))
    e3 = json.loads((KATALOG / "etap3_wynik.json").read_text(encoding="utf-8"))

    print("\n═══ SPÓJNOŚĆ 1 ↔ 2 ↔ 3 ═══")
    ok = e3["wszechswiat_odcisk"] == zamr["odcisk"] and \
        e3["progi_odcisk"] == progi["odcisk"]
    print(f"S1. etap 3 na tym samym wszechświecie i progach: {'OK' if ok else 'NIE'}")
    if not ok:
        problemy.append("etap 3 liczył na innym wszechświecie lub progach")

    le2 = e2["konforemna"]["0.9"]
    le3 = e3["wyniki"]["LE"]
    zgod = abs(le2["pokrycie"] - le3["pokrycie"]) < 1e-9 and \
        abs(le2["sredni_rozmiar"] - le3["sredni_rozmiar"]) < 1e-9
    print(f"S2. LE liczone w etapie 2 i 3 daje to samo: {'OK' if zgod else 'ROZJAZD'} "
          f"({100*le2['pokrycie']:.1f}% / {le2['sredni_rozmiar']:.2f} vs "
          f"{100*le3['pokrycie']:.1f}% / {le3['sredni_rozmiar']:.2f})")
    if not zgod:
        problemy.append("LE wychodzi inaczej w etapie 2 i 3 mimo tej samej procedury")

    # ---------- SPRZĘŻENIE ----------
    print("\n═══ SPRZĘŻENIE MIĘDZY ETAPAMI ═══")
    from dancelab.validation.djmix.ordering_models import (
        OrderingTrainingConfig, fit_conditional_ordering_model,
        load_ordering_feature_catalog, split_ordering_observations)
    from etap2_konforemna import prawdopodobienstwa, wczytaj_obserwacje

    katalog = load_ordering_feature_catalog(KATALOG / "features_lipiec.json")
    cz = split_ordering_observations(wczytaj_obserwacje(zamr))
    trening, kal, test = cz["train"], cz["validation"], cz["test"]

    m_le = fit_conditional_ordering_model(trening, katalog, family="E",
                                          config=OrderingTrainingConfig(max_iterations=2000))
    p_kal = prawdopodobienstwa(m_le, kal, katalog)
    p_test = prawdopodobienstwa(m_le, test, katalog)
    p0_kal = [np.full(len(o.candidate_track_ids), 1/len(o.candidate_track_ids)) for o in kal]
    p0_test = [np.full(len(o.candidate_track_ids), 1/len(o.candidate_track_ids)) for o in test]

    def praw(o):
        return o.candidate_track_ids.index(o.selected_track_id)

    def zbiory(pk, pt, cel=0.90):
        niezg = np.asarray([1.0 - p[praw(o)] for o, p in zip(kal, pk)])
        n = len(niezg)
        q = float(np.quantile(niezg, min(1.0, np.ceil((n+1)*cel)/n), method="higher"))
        return [np.nonzero(p >= 1.0 - q)[0] for p in pt]

    z_le, z_l0 = zbiory(p_kal, p_test), zbiory(p0_kal, p0_test)

    # E1→E3: czy zbiory L0 zależą WYŁĄCZNIE od liczby kandydatów
    wg_n = defaultdict(set)
    for o, z in zip(test, z_l0):
        wg_n[len(o.candidate_track_ids)].add(len(z))
    tylko_n = all(len(v) == 1 for v in wg_n.values())
    print(f"E1→E3. rozmiar zbioru L0 zależy WYŁĄCZNIE od liczby kandydatów: "
          f"{'TAK' if tylko_n else 'nie'}")
    for n_, v in sorted(wg_n.items()):
        print(f"        kandydatów {n_} → rozmiar zbioru {sorted(v)}")
    if tylko_n:
        print("        ⇒ odmowa L0 to nie wiedza, tylko licznik kandydatów.")

    # E2↔E3: P3 WEWNĄTRZ warstw o tej samej liczbie kandydatów
    print("\nE2↔E3. P3 policzone WEWNĄTRZ warstw (kontrola na liczbę kandydatów)")
    print(f"{'kand.':>6s} {'obs':>5s} {'LE pudło':>10s} {'LE trafione':>13s} "
          f"{'różnica':>9s} {'L0 różnica':>12s}")
    lacznie_le, lacznie_l0, waga = 0.0, 0.0, 0
    for n_ in sorted(wg_n):
        idx = [i for i, o in enumerate(test) if len(o.candidate_track_ids) == n_]
        if len(idx) < 8:
            continue
        def roznica(zb, pt):
            a, b = [], []
            for i in idx:
                trafil = int(np.argmax(pt[i])) == praw(test[i])
                (a if trafil else b).append(len(zb[i]))
            if not a or not b:
                return None, None, None
            return statistics.mean(b), statistics.mean(a), statistics.mean(b)-statistics.mean(a)
        pud, traf, r_le = roznica(z_le, p_test)
        _, _, r_l0 = roznica(z_l0, p0_test)
        if r_le is None:
            continue
        print(f"{n_:6d} {len(idx):5d} {pud:10.2f} {traf:13.2f} "
              f"{r_le:9.2f} {(r_l0 if r_l0 is not None else float('nan')):12.2f}")
        lacznie_le += r_le * len(idx); lacznie_l0 += (r_l0 or 0) * len(idx); waga += len(idx)
    if waga:
        sr_le, sr_l0 = lacznie_le/waga, lacznie_l0/waga
        print(f"\n  ważona średnia różnica WEWNĄTRZ warstw: "
              f"LE {sr_le:+.3f} · L0 {sr_l0:+.3f}")
        if abs(sr_l0) < 0.02 and sr_le > 0.05:
            print("  ⇒ po odjęciu wpływu liczby kandydatów sygnał ZOSTAJE u LE")
            print("    i ZNIKA u L0. Sygnał etapu 2 jest własnością modelu.")
        elif sr_le <= 0.05:
            print("  ⇒ po kontroli sygnał LE też znika — etap 2 do wyrzucenia.")
            problemy.append("sygnał P3 u LE znika po kontroli na liczbę kandydatów")

    # E1→E2
    print("\nE1→E2. czy krzywa z etapu 1 tłumaczy rozmiary z etapu 2")
    sr_kand = statistics.mean(len(o.candidate_track_ids) for o in test)
    print(f"  średnia liczba kandydatów {sr_kand:.2f} · "
          f"rozmiar LE {le2['sredni_rozmiar']:.2f} · "
          f"„oddaj wszystko” {progi['P2_oszczednosc']['darmowy_wariant_oddaj_wszystko']['sredni_rozmiar']:.2f}")
    print(f"  ⇒ konforemna ścina {100*(1-le2['sredni_rozmiar']/sr_kand):.1f}% "
          f"objętości wobec oddania wszystkiego")

    uwagi.append("P3 w postaci z etapu 1 jest skażone liczbą kandydatów — "
                 "wymaga liczenia wewnątrz warstw")

    print()
    if problemy:
        print(f"PROBLEMY: {len(problemy)}")
        for x in problemy:
            print("  ⛔", x)
    if uwagi:
        print(f"DO POPRAWY: {len(uwagi)}")
        for x in uwagi:
            print("  →", x)
    return 1 if problemy else 0


if __name__ == "__main__":
    sys.exit(main())
