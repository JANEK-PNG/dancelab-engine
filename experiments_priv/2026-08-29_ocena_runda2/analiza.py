"""Analiza ocen papierowych OCENA A–J — dokładnie wg PLAN_ANALIZY.md.

Progi zarejestrowane 18.08 PRZED danymi. Ten skrypt je tylko wykonuje.

Bramka kompletności: bez kompletu 158 ocen NIC nie liczy i NIE otwiera
`PRZYDZIAL_NIE_OTWIERAC.json`. Przydział czyta wyłącznie ten skrypt.

Użycie:
    uv run python analiza.py            # dane z katalogu skryptu
    uv run python analiza.py --katalog X  # test na sztucznych danych
"""

from __future__ import annotations

import csv
import itertools
import json
import pathlib
import sys
from collections import defaultdict

import numpy as np

ZIARNO = 20260818
PERMUTACJE = 10_000
LITERY = {"T": "bpm_grid_sync", "S": "style_genre_mood", "E": "energy_curve",
          "M": "transition_timing", "D": "duplicates_same_album",
          "K": "playlist_context"}


def dolacz_wyniki_silnika(katalog: pathlib.Path, wiersze: list[dict]) -> None:
    """Wynik silnika wchodzi DOPIERO po bramce — bo zdradza przydział.

    Złapane w przeglądzie 29.08: w rundzie 1 żadne przejście z grupy silnika
    nie miało wyniku poniżej 1,0, a w kontroli miało go 53%. Kolumna leżąca
    w arkuszu ocen odtwarzała więc przydział bezbłędnie i pieczęć na
    PRZYDZIAL_NIE_OTWIERAC.json była ozdobą. Od rundy 2 wyniki leżą osobno,
    zapieczętowane tak samo jak przydział.
    """
    plik = katalog / "WYNIKI_SILNIKA_NIE_OTWIERAC.json"
    if not plik.exists():
        return                      # runda 1: kolumna została w arkuszach
    wyniki = json.loads(plik.read_text(encoding="utf-8"))["wyniki"]
    for r in wiersze:
        r["engine_score"] = wyniki[r["pair_id"]]


def wczytaj_przejscia(katalog: pathlib.Path) -> list[dict]:
    wiersze = []
    for p in sorted(katalog.glob("SESJA_*_transition_ratings.csv")):
        with open(p, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                r["playlista"] = r["pair_id"].rsplit("_", 1)[0].replace("_", " ")
                wiersze.append(r)
    return wiersze


def wczytaj_wylaczenia(katalog: pathlib.Path) -> dict[str, dict]:
    """Przejścia świadomie wyłączone z analizy, z powodem i datą decyzji.

    Odstępstwo od planu z 18.08, dopisane 29.08: plan zakładał komplet 158
    ocen albo zero liczenia. Jedno przejście (OCENA_J_13) nie zostało
    ocenione na papierze i Janek zdecydował je pominąć. Lista jest jawna,
    bo wyłączanie obserwacji BEZ zapisu jest doborem wyniku — a z zapisem
    jest brakiem danych, który każdy czytający zobaczy.
    """
    plik = katalog / "WYLACZENIA.json"
    if not plik.exists():
        return {}
    dane = json.loads(plik.read_text(encoding="utf-8"))
    return {w["pair_id"]: w for w in dane.get("wylaczenia", [])}


def bramka_kompletnosci(wiersze: list[dict],
                        wylaczone: dict[str, dict] | None = None) -> list[str]:
    wylaczone = wylaczone or {}
    braki = [r["pair_id"] for r in wiersze
             if r["pair_id"] not in wylaczone
             and not str(r.get("dj_mixability_rating", "")).strip()]
    zle = [r["pair_id"] for r in wiersze
           if str(r.get("dj_mixability_rating", "")).strip()
           and r["dj_mixability_rating"].strip() not in {"1", "2", "3", "4", "5"}]
    problemy = []
    if len(wiersze) != 158:
        problemy.append(f"wierszy {len(wiersze)}, oczekiwano 158")
    if braki:
        problemy.append(f"bez oceny: {len(braki)} (np. {braki[:4]})")
    if zle:
        problemy.append(f"oceny spoza 1–5: {zle[:4]}")
    return problemy


def h1_kolejnosc(srednie: dict[str, float], przydzial: dict[str, str]) -> dict:
    """Dokładna permutacja po wszystkich C(10,4) przydziałach kontroli."""
    nazwy = sorted(srednie)
    wart = np.array([srednie[n] for n in nazwy])
    kontrola = frozenset(i for i, n in enumerate(nazwy)
                         if przydzial[n] != "SILNIK")
    def delta(kontr: frozenset) -> float:
        maska = np.array([i in kontr for i in range(len(nazwy))])
        return float(wart[~maska].mean() - wart[maska].mean())
    obserwowana = delta(kontrola)
    wszystkie = [delta(frozenset(k))
                 for k in itertools.combinations(range(len(nazwy)), len(kontrola))]
    p = sum(1 for d in wszystkie if d >= obserwowana - 1e-12) / len(wszystkie)
    if p < 0.05 and obserwowana >= 0.5:
        werdykt = "SUKCES: kolejność silnika słyszalna"
    elif p < 0.05 and obserwowana >= 0.25:
        werdykt = "słaby, realny sygnał (bez ogłaszania sukcesu)"
    else:
        werdykt = "brak słyszalnego efektu kolejności → OBALONE.md"
    return {"delta": round(obserwowana, 3), "p": round(p, 4),
            "przydzialow": len(wszystkie), "werdykt": werdykt}


def h2_score_vs_ucho(wiersze: list[dict]) -> dict:
    from scipy.stats import spearmanr
    score = np.array([float(r["engine_score"]) for r in wiersze])
    ocena = np.array([float(r["dj_mixability_rating"]) for r in wiersze])
    play = np.array([r["playlista"] for r in wiersze])
    rho = float(spearmanr(score, ocena).statistic)
    g = np.random.default_rng(ZIARNO)
    licznik = 0
    for _ in range(PERMUTACJE):
        perm = ocena.copy()
        for nazwa in np.unique(play):
            m = play == nazwa
            perm[m] = g.permutation(perm[m])
        if float(spearmanr(score, perm).statistic) >= rho - 1e-12:
            licznik += 1
    p = licznik / PERMUTACJE
    if rho >= 0.30 and p < 0.05:
        werdykt = "silnik widzi to, co ucho"
    elif rho >= 0.15 and p < 0.05:
        werdykt = "słaby sygnał"
    else:
        werdykt = "brak związku wynik↔ucho → OBALONE.md"
    fp = sum(1 for r in wiersze if float(r["engine_score"]) >= 0.70
             and float(r["dj_mixability_rating"]) <= 2)
    return {"rho": round(rho, 3), "p": round(p, 4),
            "falszywe_alarmy": fp, "werdykt": werdykt}


def h3_calosci(katalog: pathlib.Path, przydzial: dict[str, str]) -> dict:
    plik = katalog / "oceny_playlist.csv"
    if not plik.exists():
        return {"uwaga": "brak oceny_playlist.csv — H3 pominięta"}
    with open(plik, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    wynik = {}
    for wymiar in ("spojnosc", "roznorodnosc", "przebieg", "zagralbym"):
        pary = {r["playlista"]: r.get(wymiar, "").strip() for r in rows}
        if any(not v for v in pary.values()):
            wynik[wymiar] = "niekompletne — pominięte"
            continue
        srednie = {k: float(v) for k, v in pary.items()}
        wynik[wymiar] = h1_kolejnosc(srednie, przydzial) | {"werdykt": "opisowo"}
    return wynik


def zgrzyty(wiersze: list[dict], przydzial: dict[str, str]) -> dict:
    """Ile razy która kategoria zgrzytu pada w każdej grupie — i JAK CZĘSTO.

    Kategorie czytamy z kolumny `zgrzyt`, nie z `comment`. Do 29.08 licznik
    szukał liter T/S/E/M/D/K w całym komentarzu, więc każde polskie zdanie
    dorzucało po kilka kategorii z powietrza („Nu 8beat to loop" → E i T).
    Fallback na `comment` zostaje wyłącznie dla starych plików bez kolumny.

    Surowe liczby są nieporównywalne między grupami — grup nie ma po tyle samo
    przejść — więc obok liczby idzie odsetek przejść w tej grupie.
    """
    licz: dict[str, dict[str, int]] = {"SILNIK": defaultdict(int),
                                       "KONTROLA": defaultdict(int)}
    ile_przejsc: dict[str, int] = defaultdict(int)
    for r in wiersze:
        grupa = ("SILNIK" if przydzial[r["playlista"]] == "SILNIK"
                 else "KONTROLA")
        ile_przejsc[grupa] += 1
        pole = r.get("zgrzyt")
        if pole is None:
            tekst = str(r.get("comment", "")).upper()
            trafienia = {L for L in LITERY if L in tekst}
        else:
            trafienia = {L.strip().upper() for L in str(pole).split(",")
                         if L.strip()}
        for litera in trafienia:
            if litera in LITERY:
                licz[grupa][LITERY[litera]] += 1
    return {
        "przejsc_w_grupie": dict(ile_przejsc),
        "liczby": {g: dict(sorted(v.items())) for g, v in licz.items()},
        "odsetek_przejsc": {
            g: {t: round(n / ile_przejsc[g], 3) for t, n in sorted(v.items())}
            for g, v in licz.items() if ile_przejsc[g]},
    }


def main() -> int:
    katalog = pathlib.Path(__file__).parent
    if "--katalog" in sys.argv:
        katalog = pathlib.Path(sys.argv[sys.argv.index("--katalog") + 1])

    wiersze = wczytaj_przejscia(katalog)
    wylaczone = wczytaj_wylaczenia(katalog)
    problemy = bramka_kompletnosci(wiersze, wylaczone)
    if problemy:
        print("⛔ BRAMKA KOMPLETNOŚCI — analiza nie rusza, przydział zostaje "
              "zamknięty:")
        for p in problemy:
            print(f"   • {p}")
        return 2
    # Wyłączone wiersze wypadają ze WSZYSTKICH liczeń, nie tylko z bramki.
    wiersze = [r for r in wiersze if r["pair_id"] not in wylaczone]
    print(f"bramka kompletności: ✓ {len(wiersze)}/158 ocen"
          + (f" · wyłączone: {len(wylaczone)} "
             f"({', '.join(sorted(wylaczone))})" if wylaczone else ""))
    for pid, w in sorted(wylaczone.items()):
        print(f"   • {pid} wyłączone — {w.get('powod', 'bez powodu')} "
              f"[{w.get('decyzja', 'bez decyzji')}]")

    # dopiero teraz wolno otworzyć obie pieczęcie: przydział i wyniki silnika
    dolacz_wyniki_silnika(katalog, wiersze)
    przydzial = json.loads((katalog / "PRZYDZIAL_NIE_OTWIERAC.json")
                           .read_text(encoding="utf-8"))["przydzial"]

    per_playlista: dict[str, list[float]] = defaultdict(list)
    for r in wiersze:
        per_playlista[r["playlista"]].append(float(r["dj_mixability_rating"]))
    srednie = {k: float(np.mean(v)) for k, v in per_playlista.items()}

    wynik = {
        "wylaczone_przejscia": {k: v.get("powod") for k, v in sorted(wylaczone.items())},
        "ocen_w_analizie": len(wiersze),
        "H1_kolejnosc": h1_kolejnosc(srednie, przydzial),
        "H2_score_vs_ucho": h2_score_vs_ucho(wiersze),
        "H3_calosci": h3_calosci(katalog, przydzial),
        "zgrzyty": zgrzyty(wiersze, przydzial),
        "srednie_per_playlista": {k: round(v, 2)
                                  for k, v in sorted(srednie.items())},
        "przydzial": przydzial,
    }
    out = katalog / "wynik_analizy.json"
    out.write_text(json.dumps(wynik, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps(wynik, ensure_ascii=False, indent=1))
    print(f"\nzapisano: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
