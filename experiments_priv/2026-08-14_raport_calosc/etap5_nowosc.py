"""ETAP 5 — czy „nie znam tego utworu" przewiduje, że model się pomyli.

PO CO TEN POMIAR
----------------
Warunek z 01.08: element uczący się wchodzi do silnika tylko wtedy, gdy umie
odmówić. Etap 3 pokazał, że pewność samego modelu NIE wskazuje, gdzie model
się myli (P3 wewnątrz warstw ~0). Potrzebny jest sygnał Z ZEWNĄTRZ modelu.

Kandydat numer jeden: NOWOŚĆ zapytania — jak daleko utwór, który właśnie gra,
leży od utworów, na których model się uczył. Intuicja jest banalna: „czegoś
takiego jeszcze nie słyszałem" powinno oznaczać „nie ufaj mojej odpowiedzi".
Ale intuicja to nie pomiar. TEN skrypt mierzy wyłącznie tę jedną rzecz —
zanim ktokolwiek wepnie nowość do modelu czy do konforemnej.

DEFINICJA NOWOŚCI (ustalona przed biegiem)
------------------------------------------
Zbiór odniesienia = utwory REALNIE ZAGRANE w miksach treningowych: historia,
utwór grający i wybrany następnik. CELOWO BEZ wylosowanych negatywów — przy
200 kandydatach na obserwację niemal każdy utwór puli pojawia się gdzieś jako
negatyw i nowość zdegenerowałaby się do zera dla wszystkich.

    nowosc(utwór) = 1 − max po zbiorze odniesienia (kosinus wektorów CLAP)

Nowość ZAPYTANIA = nowość utworu grającego. To jest sygnał dostępny w chwili
predykcji, bez znajomości prawdy.

PROGI ZAREJESTROWANE PRZED BIEGIEM
----------------------------------
  N1 (główny): korelacja rang Spearmana między nowością zapytania a POZYCJĄ
      prawdziwej odpowiedzi w rankingu 200 kandydatów:
      rho ≥ +0,15 przy p < 0,05, w wariancie ŁATWYM (negatywy z całej puli —
      to jest kształt produktu). Dodatnia, bo wyższa nowość → gorsza pozycja.
  N2 (kontrola negatywna): ta sama korelacja liczona na rankingu LOSOWYM
      (permutacja z ziarna) musi wyjść nieistotna. Jeśli nowość „przewiduje"
      błąd modelu, który nie istnieje — pomiar jest zepsuty.
  N3 (sanity): utwory obecne w zbiorze treningowym mają nowość ≈ 0.

Miara to POZYCJA (rank), nie trafność top-1 — przy 166 obserwacjach i ~5%
trafień top-1 tercyle miałyby po 2-3 trafienia i pomiar nie miałby mocy.

Wariant TRUDNY (negatywy brzmiące podobnie) raportowany obok, bez progu:
tam negatywy są Z KONSTRUKCJI blisko zapytania, więc nowość zapytania
i trudność zadania są splecione — wynik czytać ostrożnie.
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

N = 200
ZIARNO = "dancelab-zadanie-produktowe-v1"   # TEN SAM co etap 4 — identyczny zbiór


def los(k: str) -> np.random.Generator:
    return np.random.default_rng(
        int(hashlib.sha256((ZIARNO + k).encode()).hexdigest()[:16], 16))


def spearman(a, b):
    """Korelacja rang + p (permutacyjnie, 10 000 losowań, deterministycznie)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean(); rb -= rb.mean()
    mian = float(np.sqrt((ra ** 2).sum() * (rb ** 2).sum()))
    if mian == 0:
        return 0.0, 1.0
    rho = float((ra * rb).sum() / mian)
    g = los("permutacje-spearman")
    licznik = 0
    for _ in range(10_000):
        rp = g.permutation(rb)
        if abs(float((ra * rp).sum() / mian)) >= abs(rho):
            licznik += 1
    return rho, (licznik + 1) / 10_001


def main() -> int:
    from dancelab.validation.djmix.ordering import OrderingObservation
    from dancelab.validation.djmix.ordering_models import (
        OrderingTrainingConfig, fit_conditional_ordering_model,
        load_ordering_feature_catalog, split_ordering_observations)
    from etap2_konforemna import prawdopodobienstwa, wczytaj_obserwacje

    zamr = json.loads((KATALOG / "wszechswiat_zamrozony.json").read_text(encoding="utf-8"))
    katalog = load_ordering_feature_catalog(KATALOG / "features_lipiec.json")
    stare = wczytaj_obserwacje(zamr)
    pula = sorted(katalog.tracks)
    wek = np.asarray([katalog.tracks[t].embedding for t in pula], dtype=np.float64)
    wek /= (np.linalg.norm(wek, axis=1, keepdims=True) + 1e-12)
    poz = {t: i for i, t in enumerate(pula)}

    def przebuduj(obs, tryb):
        """DOKŁADNIE ta sama procedura i ziarno co etap 4 — ten sam zbiór."""
        out = []
        for o in obs:
            g = los(f"{tryb}|{o.run_id}|{o.position}")
            zak = set(o.history_track_ids) | {o.selected_track_id}
            if tryb == "latwy":
                kand = [pula[i] for i in g.choice(len(pula), size=N * 2, replace=False)]
            else:
                v = wek[poz[o.current_track_id]]
                bl = np.argsort(-(wek @ v))[:800]
                w = g.choice(len(bl), size=min(N * 2, len(bl)), replace=False)
                kand = [pula[bl[i]] for i in w]
            kand = [k for k in kand if k not in zak][:N - 1]
            out.append(OrderingObservation(
                mix_id=o.mix_id, run_id=o.run_id, position=o.position,
                history_track_ids=o.history_track_ids,
                candidate_track_ids=tuple(sorted(set([o.selected_track_id] + kand))),
                selected_track_id=o.selected_track_id,
                genre_labels=o.genre_labels, dj_id=o.dj_id))
        return tuple(out)

    wyniki = {}
    for tryb in ("latwy", "trudny"):
        obs = przebuduj(stare, tryb)
        cz = split_ordering_observations(obs)
        tr, te = cz["train"], cz["test"]

        # zbiór odniesienia: utwory REALNIE ZAGRANE w treningu
        widziane = set()
        for o in tr:
            widziane |= set(o.history_track_ids)
            widziane.add(o.current_track_id)
            widziane.add(o.selected_track_id)
        wt = wek[[poz[t] for t in sorted(widziane)]]
        print(f"\n═══ WARIANT {tryb.upper()} ═══")
        print(f"trening {len(tr)} obs · test {len(te)} obs · "
              f"utworów zagranych w treningu: {len(widziane)} z {len(pula)}")

        def nowosc(tid: str) -> float:
            return float(1.0 - np.max(wt @ wek[poz[tid]]))

        # N3 — sanity na utworach z treningu
        probka = sorted(widziane)[:50]
        n3 = max(nowosc(t) for t in probka)
        print(f"N3 sanity: maks. nowość utworu Z treningu = {n3:.6f} "
              f"{'✓' if n3 < 1e-9 else '⛔'}")

        m = fit_conditional_ordering_model(
            tr, katalog, family="E",
            config=OrderingTrainingConfig(max_iterations=2000))
        p_te = prawdopodobienstwa(m, te, katalog)

        nowosci, pozycje, pozycje_los = [], [], []
        for o, p in zip(te, p_te):
            i = o.candidate_track_ids.index(o.selected_track_id)
            r = int(np.where(np.argsort(-p) == i)[0][0]) + 1
            nowosci.append(nowosc(o.current_track_id))
            pozycje.append(r)
            # kontrola: pozycja z rankingu LOSOWEGO (deterministyczne ziarno)
            g = los(f"kontrola|{o.run_id}|{o.position}")
            pozycje_los.append(int(g.integers(1, len(p) + 1)))

        rho, pval = spearman(nowosci, pozycje)
        rho0, pval0 = spearman(nowosci, pozycje_los)

        # tercyle — do opowieści, próg stoi na rho
        kol = np.argsort(nowosci)
        t3 = len(kol) // 3
        med = [statistics.median([pozycje[i] for i in kol[a:b]])
               for a, b in ((0, t3), (t3, 2 * t3), (2 * t3, len(kol)))]

        print(f"nowość zapytań: min {min(nowosci):.3f} · mediana "
              f"{statistics.median(nowosci):.3f} · maks {max(nowosci):.3f}")
        print(f"N1: rho(nowość, pozycja prawdy) = {rho:+.3f}  p = {pval:.4f}")
        print(f"N2: kontrola na rankingu losowym = {rho0:+.3f}  p = {pval0:.4f}")
        print(f"tercyle nowości → mediana pozycji: "
              f"znane {med[0]:.0f} · środek {med[1]:.0f} · nowe {med[2]:.0f}")

        wyniki[tryb] = {
            "widzianych_utworow": len(widziane),
            "nowosc_min_med_max": [min(nowosci), statistics.median(nowosci), max(nowosci)],
            "N1_rho": rho, "N1_p": pval,
            "N2_rho_kontrola": rho0, "N2_p_kontrola": pval0,
            "N3_maks_nowosc_znanego": n3,
            "tercyle_mediana_pozycji": med,
        }

    glowny = wyniki["latwy"]
    n1 = glowny["N1_rho"] >= 0.15 and glowny["N1_p"] < 0.05
    n2 = glowny["N2_p_kontrola"] >= 0.05 or abs(glowny["N2_rho_kontrola"]) < 0.10
    n3ok = glowny["N3_maks_nowosc_znanego"] < 1e-9
    print(f"\n═══ WERDYKT (progi zapisane przed biegiem) ═══")
    print(f"  N1 nowość przewiduje błąd: {'ZDANY' if n1 else 'NIEZDANY'} "
          f"(rho {glowny['N1_rho']:+.3f}, próg +0,15, p {glowny['N1_p']:.4f})")
    print(f"  N2 kontrola czysta:        {'ZDANY' if n2 else 'NIEZDANY — pomiar zepsuty'}")
    print(f"  N3 sanity:                 {'ZDANY' if n3ok else 'NIEZDANY'}")

    (KATALOG / "etap5_wynik.json").write_text(json.dumps({
        "wszechswiat_odcisk": zamr["odcisk"], "ziarno": ZIARNO,
        "definicja": "nowosc = 1 - maks. kosinus do utworow ZAGRANYCH w treningu",
        "wyniki": wyniki,
        "werdykt": {"N1": bool(n1), "N2": bool(n2), "N3": bool(n3ok)},
    }, ensure_ascii=False), encoding="utf-8")
    print("\nzapisano: etap5_wynik.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
