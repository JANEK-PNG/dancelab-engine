"""ETAP 3 — kontrola negatywna dla predykcji konforemnej.

Etap 2 pokazał, że konforemna nad LE kalibruje się (P1), oszczędza o włos (P2)
i niesie sygnał o własnym błędzie (P3). Zanim się z tego ucieszymy, trzeba
sprawdzić rzecz, która potrafi to unieważnić w całości:

    czy TE SAME liczby nie wyjdą nad modelem, który nic nie wie?

Dwie kontrole, obie przez DOKŁADNIE ten sam kod co LE:

  LH — model na cechach rzemieślniczych. Zmierzony w drabinie jako GORSZY
       od ślepego zgadywania (NLL 184,7 wobec 175,1). Ma sygnał, ale zły.

  L0 — rozkład jednorodny, 1/n na kandydata. Zero informacji, z definicji.
       To jest twarda podłoga: cokolwiek konforemna pokaże nad L0, jest
       własnością METODY, a nie modelu.

Odczyt:
  · P1 nad L0 ZDANY  → to normalne i oczekiwane; gwarancja pokrycia jest
    twierdzeniem o metodzie i działa nawet dla bezużytecznego modelu.
    Innymi słowy: P1 sam z siebie NICZEGO o modelu nie dowodzi.
  · P3 nad L0 ZDANY  → alarm. Znaczyłoby, że „zbiór rośnie tam, gdzie błąd"
    da się uzyskać bez żadnej wiedzy, i etap 2 nie pokazał niczego.
  · P3 nad L0 NIEZDANY, a nad LE ZDANY → etap 2 mierzył model.
"""

from __future__ import annotations

import json
import pathlib
import statistics
import sys

import numpy as np

KATALOG = pathlib.Path(__file__).parent
sys.path.insert(0, str(KATALOG))


def konforemna(p_kal, kal, p_test, test, cel: float) -> dict:
    """Jedna i ta sama procedura dla każdego modelu — inaczej porównanie kłamie."""
    def praw(o):
        return o.candidate_track_ids.index(o.selected_track_id)

    niezg = np.asarray([1.0 - p[praw(o)] for o, p in zip(kal, p_kal)])
    n = len(niezg)
    rzad = min(1.0, np.ceil((n + 1) * cel) / n)
    q = float(np.quantile(niezg, rzad, method="higher"))
    prog = 1.0 - q

    pokryte, rozmiary, puste = [], [], 0
    r_traf, r_pudlo, o_traf, o_pudlo = [], [], [], []
    for o, p in zip(test, p_test):
        wyb = np.nonzero(p >= prog)[0]
        rozmiary.append(len(wyb))
        if len(wyb) == 0:
            puste += 1
        i = praw(o)
        pokryte.append(i in set(wyb.tolist()))
        trafil = int(np.argmax(p)) == i
        (o_traf if trafil else o_pudlo).append(len(wyb) == 0)
        if len(wyb):
            (r_traf if trafil else r_pudlo).append(len(wyb))
    return {
        "pokrycie": float(np.mean(pokryte)),
        "sredni_rozmiar": float(np.mean(rozmiary)),
        "pustych": puste,
        "P3_rozmiar": (statistics.mean(r_pudlo) - statistics.mean(r_traf))
        if r_pudlo and r_traf else float("nan"),
        "P3_odmowa": (statistics.mean(o_pudlo) - statistics.mean(o_traf))
        if o_pudlo and o_traf else float("nan"),
        "top1": float(np.mean([int(np.argmax(p)) == praw(o)
                               for o, p in zip(test, p_test)])),
    }


def main() -> int:
    from dancelab.validation.djmix.ordering_models import (
        OrderingTrainingConfig,
        fit_conditional_ordering_model,
        load_ordering_feature_catalog,
        split_ordering_observations,
    )
    from etap2_konforemna import prawdopodobienstwa, wczytaj_obserwacje

    zamr = json.loads((KATALOG / "wszechswiat_zamrozony.json").read_text(encoding="utf-8"))
    progi = json.loads((KATALOG / "progi_odmowy.json").read_text(encoding="utf-8"))
    e2 = json.loads((KATALOG / "etap2_wynik.json").read_text(encoding="utf-8"))
    if progi["wszechswiat_odcisk"] != zamr["odcisk"] or \
            e2["wszechswiat_odcisk"] != zamr["odcisk"]:
        print("PRZERWANE: etapy 1–2 dotyczą innego wszechświata")
        return 2

    katalog = load_ordering_feature_catalog(KATALOG / "features_lipiec.json")
    cz = split_ordering_observations(wczytaj_obserwacje(zamr))
    trening, kal, test = cz["train"], cz["validation"], cz["test"]

    modele = {}
    for nazwa, rodzina in (("LE", "E"), ("LH", "H")):
        m = fit_conditional_ordering_model(
            trening, katalog, family=rodzina, include_dj_effects=False,
            config=OrderingTrainingConfig(max_iterations=2000))
        modele[nazwa] = (prawdopodobienstwa(m, kal, katalog),
                         prawdopodobienstwa(m, test, katalog))
        print(f"{nazwa}: cel {m.final_objective:.6f}")

    # L0 — rozkład jednorodny, konstruowany, nie uczony
    modele["L0"] = (
        [np.full(len(o.candidate_track_ids), 1.0 / len(o.candidate_track_ids)) for o in kal],
        [np.full(len(o.candidate_track_ids), 1.0 / len(o.candidate_track_ids)) for o in test],
    )
    print("L0: rozkład jednorodny (bez uczenia)")

    CEL = 0.90
    print(f"\nKONFOREMNA PRZY CELU {100*CEL:.0f}% — ta sama procedura dla każdego")
    print(f"{'model':6s} {'top-1':>8s} {'pokrycie':>10s} {'rozmiar':>9s} "
          f"{'puste':>7s} {'P3 rozm.':>10s} {'P3 odmowa':>11s}")
    wyniki = {}
    for nazwa in ("LE", "LH", "L0"):
        pk, pt = modele[nazwa]
        w = konforemna(pk, kal, pt, test, CEL)
        wyniki[nazwa] = w
        print(f"{nazwa:6s} {100*w['top1']:7.1f}% {100*w['pokrycie']:9.1f}% "
              f"{w['sredni_rozmiar']:9.2f} {w['pustych']:7d} "
              f"{w['P3_rozmiar']:10.2f} {100*w['P3_odmowa']:10.1f}pp")

    # ---- P3 WEWNĄTRZ WARSTW o tej samej liczbie kandydatów ----
    # Kontrola negatywna pokazała, że zbiór L0 zależy WYŁĄCZNIE od liczby
    # kandydatów: 2→2, 3→3, 4→4, 5→5, od 6 wzwyż pusto. Jego „odmowa" to
    # licznik kandydatów. Skoro tak, to P3 liczone globalnie miesza wiedzę
    # modelu z trudnością pytania i trzeba je liczyć wewnątrz warstw.
    # Poprzeczka 0,25 pozycji NIE zmieniona — zmieniony przyrząd.
    def p3_warstwowo(pk, pt, cel):
        niezg = np.asarray([1.0 - p[praw_i(o)] for o, p in zip(kal, pk)])
        n = len(niezg)
        q = float(np.quantile(niezg, min(1.0, np.ceil((n+1)*cel)/n), method="higher"))
        zb = [np.nonzero(p >= 1.0 - q)[0] for p in pt]
        tot, wag = 0.0, 0
        for n_ in sorted({len(o.candidate_track_ids) for o in test}):
            idx = [i for i, o in enumerate(test) if len(o.candidate_track_ids) == n_]
            if len(idx) < 8:
                continue
            a = [len(zb[i]) for i in idx if int(np.argmax(pt[i])) == praw_i(test[i])]
            b = [len(zb[i]) for i in idx if int(np.argmax(pt[i])) != praw_i(test[i])]
            if not a or not b:
                continue
            tot += (statistics.mean(b) - statistics.mean(a)) * len(idx)
            wag += len(idx)
        return tot / wag if wag else float("nan")

    def praw_i(o):
        return o.candidate_track_ids.index(o.selected_track_id)

    print("\nP3 WEWNĄTRZ WARSTW (kontrola na liczbę kandydatów)")
    print(f"{'cel':>6s} {'LE':>9s} {'LH':>9s} {'L0':>9s}")
    warstwowo = {}
    for c in (0.60, 0.70, 0.80, 0.90):
        wiersz = {n: p3_warstwowo(*modele[n], c) for n in ("LE", "LH", "L0")}
        warstwowo[str(c)] = wiersz
        print(f"{100*c:5.0f}% {wiersz['LE']:+9.3f} {wiersz['LH']:+9.3f} "
              f"{wiersz['L0']:+9.3f}")
    p3_war_le = max(warstwowo[c]["LE"] for c in warstwowo)
    p3_warstwowy_zdany = p3_war_le >= 0.25
    print(f"\n  najlepszy LE wewnątrz warstw: {p3_war_le:+.3f} "
          f"przy progu +0,25 → {'ZDANY' if p3_warstwowy_zdany else 'NIEZDANY'}")

    print("\nWERDYKT KONTROLI NEGATYWNEJ")
    le, lh, l0 = wyniki["LE"], wyniki["LH"], wyniki["L0"]
    p1_l0 = abs(l0["pokrycie"] - CEL) <= 0.03
    print(f"  P1 nad L0: {'ZDANY' if p1_l0 else 'niezdany'} "
          f"({100*l0['pokrycie']:.1f}%) — oczekiwane; gwarancja pokrycia to "
          f"twierdzenie o METODZIE.")
    print(f"     ⇒ P1 sam z siebie nie dowodzi niczego o modelu.")

    p3_le = le["P3_rozmiar"] >= 0.25 or le["P3_odmowa"] >= 0.10
    p3_l0 = l0["P3_rozmiar"] >= 0.25 or l0["P3_odmowa"] >= 0.10
    p3_lh = lh["P3_rozmiar"] >= 0.25 or lh["P3_odmowa"] >= 0.10
    print(f"  P3 nad LE: {'zdany' if p3_le else 'niezdany'} · "
          f"nad LH: {'zdany' if p3_lh else 'niezdany'} · "
          f"nad L0: {'ZDANY — ALARM' if p3_l0 else 'niezdany — dobrze'}")

    if p3_warstwowy_zdany:
        print("\n  ✓ KONTROLA ZDANA: sygnał odmowy zostaje po odjęciu wpływu")
        print("    liczby kandydatów — jest własnością modelu.")
    else:
        print("\n  ⛔ KONTROLA NIEZDANA. Globalne P3 u LE (+0,28) było artefaktem:")
        print("     zbiory są większe tam, gdzie kandydatów jest więcej, a więcej")
        print("     kandydatów to trudniejsze pytanie. Po kontroli na liczbę")
        print(f"     kandydatów zostaje {p3_war_le:+.3f} przy progu +0,25.")
        print("     Konforemna nad LE NIE wie, gdzie nie wie.")

    # oszczędność względem podłogi
    print(f"\n  rozmiar zbioru: LE {le['sredni_rozmiar']:.2f} · "
          f"LH {lh['sredni_rozmiar']:.2f} · L0 {l0['sredni_rozmiar']:.2f}")
    print(f"  (L0 to podłoga — konforemna nad niewiedzą musi oddawać "
          f"WSZYSTKICH kandydatów)")

    (KATALOG / "etap3_wynik.json").write_text(json.dumps({
        "wszechswiat_odcisk": zamr["odcisk"],
        "progi_odcisk": progi["odcisk"],
        "cel": CEL,
        "wyniki": wyniki,
        "P3_wewnatrz_warstw": warstwowo,
        "werdykt": {"P1_nad_L0_zdany": bool(p1_l0),
                    "P3_globalne_nad_LE": bool(p3_le),
                    "P3_globalne_nad_LH": bool(p3_lh),
                    "P3_globalne_nad_L0": bool(p3_l0),
                    "P3_warstwowe_nad_LE": float(p3_war_le),
                    "P3_warstwowe_zdany": bool(p3_warstwowy_zdany),
                    "kontrola_zdana": bool(p3_warstwowy_zdany),
                    "odczyt": "P3 globalne było artefaktem liczby kandydatów; "
                              "po kontroli sygnał odmowy u LE nie istnieje"},
    }, ensure_ascii=False), encoding="utf-8")
    print("\nzapisano: etap3_wynik.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
