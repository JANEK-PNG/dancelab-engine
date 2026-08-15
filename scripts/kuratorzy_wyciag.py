"""Warstwa kuratorska — wyciąg z mapy DJ-ów do osobnego wątku badawczego.

Janek 2026-08-14: „to już chyba trzeba wejść w system, jak tworzy się i
organizuje eventy. I jaką rolę pełnią kuratorzy. Jak są kuratorzy dzieł sztuki,
którzy tworzą galerie, tak samo DJ-e są swoistymi dziełami sztuki w galerii
festiwalowej".

Ten skrypt NIE liczy niczego z dźwięku i niczego nie pobiera. Bierze to, co już
leży na dysku (`ra.json`, `de_school.json`, `miksy.json`) i wyciska z tego
warstwę, której dotąd nie patrzyliśmy: **kto kogo stawia**.

Powód techniczny osobnego wyciągu: surowe zbiory ważą 8-20 MB każdy i nie
wejdą do projektu w przeglądarce. Tu powstają pliki rzędu kilkudziesięciu
kilobajtów, które da się tam wrzucić jako wiedzę.

TRZY JEDNOSTKI KURATORSKIE, w kolejności od najpewniejszej:

  1. MIEJSCE — klub albo festiwal. Najtwardsze, bo RA podaje je osobnym polem
     i nie trzeba niczego parsować. Klub jest odpowiednikiem galerii: ma stały
     adres, stałą publiczność i program układany przez tę samą osobę.
  2. CYKL — powtarzalna nazwa wydarzenia („club night", „het weekend").
     Miękkie, bo wyciągane z tytułu, ale w De School siedzi wprost w adresie.
  3. ZNACZNIK W TYTULE — „X presents", „takeover", „showcase", „invites".
     Najsłabsze i najrzadsze, ale jako jedyne nazywają kuratora Z IMIENIA,
     gdy nie jest nim gospodarz miejsca.

CZEGO TEN WYCIĄG NIE ROZSTRZYGA. Powrót do miejsca nie odróżnia rezydenta od
gościa zaproszonego drugi raz — a to są dwie różne rzeczy (patrz KURATORZY.md,
rozdział o reprezentacji). Rozdziela je dopiero rozkład: rezydent ma dużo
występów w JEDNYM miejscu, gość ma mało w wielu. Liczymy więc oba wskaźniki
i zostawiamy próg człowiekowi.
"""

from __future__ import annotations

import collections
import csv
import json
import pathlib
import re

ZRODLO = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")
OUT = pathlib.Path("experiments_priv/2026-08-14_kuratorzy/wyciag")

# Znaczniki kuratorskie w tytule wydarzenia. Kolejność bez znaczenia — jeden
# tytuł może trafić do kilku kubełków („Label X presents: Y takeover").
ZNACZNIKI = {
    "presents": re.compile(r"\b(presents?|pres\.|präsentiert|prezentuje)\b", re.I),
    "takeover": re.compile(r"\btake\s*-?\s*over\b", re.I),
    "showcase": re.compile(r"\bshowcase\b", re.I),
    "label": re.compile(r"\b(records?|recordings?|label)\b", re.I),
    "invites": re.compile(r"\b(invites?|zaprasza)\b", re.I),
    "rezydencja": re.compile(r"\b(residen(cy|ts?))\b", re.I),
    "rocznica": re.compile(r"\b(\d+\s*(years?|lat|jahre)|anniversary|urodziny)\b", re.I),
    "kolaboracja": re.compile(r"\s[x×]\s", re.I),
}

# Miejsca-śmieci. „TBA" to brak danych, nie klub — gdyby zostało, wyszłoby
# w czołówce galerii z 252 występami i skaziło każdą statystykę powrotu.
PUSTE_MIEJSCA = {"", "tba", "tba - tba", "secret location", "unknown"}


def _zapisz(nazwa: str, naglowki: list[str], wiersze: list[tuple]) -> None:
    p = OUT / nazwa
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(naglowki)
        w.writerows(wiersze)
    print(f"  {p}  ({len(wiersze)} wierszy, {p.stat().st_size // 1024} KB)")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ra = json.loads((ZRODLO / "ra.json").read_text())
    wystepy = [r for r in ra["wystepy"] if r.get("kiedy") == "zagrane"]
    artysci = {a["ksywa"]: a for a in ra["artysci"]}
    print(f"występów zagranych: {len(wystepy)}   artystów: {len(artysci)}")

    def czyste(r) -> str:
        m = (r.get("miejsce") or "").strip()
        return "" if m.lower() in PUSTE_MIEJSCA else m

    # ── 1. GALERIE (miejsca) ────────────────────────────────────────────────
    # Dla każdego miejsca: ile występów, ilu różnych artystów i jaka część
    # z nich wróciła. Stosunek występów do artystów jest tu ciekawszy niż
    # sama wielkość: miejsce z 900 występami i 100 artystami prowadzi
    # STAJNIĘ, miejsce z 900 występami i 800 artystami prowadzi PRZEPUSTOWNIĘ.
    per_miejsce: dict[str, list] = collections.defaultdict(list)
    for r in wystepy:
        if m := czyste(r):
            per_miejsce[m].append(r)

    galerie = []
    for m, rr in per_miejsce.items():
        art = collections.Counter(x["ksywa"] for x in rr)
        wroc = sum(1 for v in art.values() if v >= 2)
        lata = sorted({x["data"][:4] for x in rr if x.get("data")})
        kraj = collections.Counter(x.get("kraj", "") for x in rr).most_common(1)[0][0]
        miasto = collections.Counter(x.get("miasto", "") for x in rr).most_common(1)[0][0]
        galerie.append((
            m, kraj, miasto, len(rr), len(art),
            round(len(rr) / len(art), 2),                    # występów na artystę
            wroc, round(100 * wroc / len(art), 1),           # ilu i % wracających
            lata[0] if lata else "", lata[-1] if lata else "",
        ))
    galerie.sort(key=lambda x: -x[3])
    _zapisz("galerie.csv",
            ["miejsce", "kraj", "miasto", "wystepow", "artystow",
             "wystepow_na_artyste", "wracajacych", "wracajacych_proc",
             "rok_od", "rok_do"], galerie)

    # ── 2. REPREZENTACJA (pary artysta-miejsce) ─────────────────────────────
    # Wysoka liczba w JEDNYM miejscu = rezydencja, czyli odpowiednik artysty
    # reprezentowanego przez galerię. Zapisujemy od 2 wzwyż, bo dopiero drugi
    # występ jest decyzją PO obejrzeniu pierwszego.
    par = collections.Counter()
    rozpietosc: dict[tuple, list] = collections.defaultdict(list)
    for r in wystepy:
        if m := czyste(r):
            par[(r["ksywa"], m)] += 1
            if r.get("data"):
                rozpietosc[(r["ksywa"], m)].append(r["data"][:4])

    pary = []
    for (a, m), v in par.items():
        if v < 2:
            continue
        lata = sorted(rozpietosc[(a, m)])
        pary.append((a, m, v, lata[0] if lata else "", lata[-1] if lata else "",
                     len(set(lata))))
    pary.sort(key=lambda x: -x[2])
    _zapisz("reprezentacja.csv",
            ["ksywa", "miejsce", "razy", "rok_od", "rok_do", "roznych_lat"], pary)

    # ── 3. PROFIL ARTYSTY: rezydent czy podróżnik ───────────────────────────
    # Dwie liczby rozstrzygają: ile RÓŻNYCH miejsc i jaka część występów
    # przypada na to najczęstsze. Rezydent gra dużo w jednym, podróżnik
    # mało w wielu. Trzecia kolumna — ilu RÓŻNYCH gospodarzy zaprosiło go
    # PONOWNIE — to jest reputacja, która przeszła dalej.
    per_art: dict[str, list] = collections.defaultdict(list)
    for r in wystepy:
        if m := czyste(r):
            per_art[r["ksywa"]].append(m)

    profile = []
    for a, mm in per_art.items():
        c = collections.Counter(mm)
        top, ile_top = c.most_common(1)[0]
        powtorni = sum(1 for v in c.values() if v >= 2)
        meta = artysci.get(a, {})
        profile.append((
            a, meta.get("ra_id", ""), meta.get("kraj", ""),
            meta.get("obserwujacych", ""),
            len(mm), len(c), round(100 * ile_top / len(mm), 1), top,
            powtorni,                       # u ilu gospodarzy jest powrót
        ))
    profile.sort(key=lambda x: -x[4])
    _zapisz("profil_artysty.csv",
            ["ksywa", "ra_id", "kraj", "obserwujacych_ra", "wystepow",
             "roznych_miejsc", "proc_w_glownym", "glowne_miejsce",
             "gospodarzy_z_powrotem"], profile)

    # ── 4. ZNACZNIKI KURATORSKIE W TYTULE ───────────────────────────────────
    # Jedyne miejsce, gdzie kurator bywa nazwany Z IMIENIA, gdy nie jest nim
    # gospodarz. Zapisujemy same trafienia, żeby dało się je przejrzeć okiem —
    # bo regex tu MYLI („with" łapie zwykłe wyliczenie składu).
    znal = []
    licznik = collections.Counter()
    for r in wystepy:
        t = r.get("tytul", "") or ""
        trafy = [k for k, rx in ZNACZNIKI.items() if rx.search(t)]
        if not trafy:
            continue
        for k in trafy:
            licznik[k] += 1
        znal.append((r["ksywa"], t, "+".join(trafy), r.get("data", ""),
                     czyste(r), r.get("kraj", ""), r.get("link", "")))
    znal.sort(key=lambda x: x[3], reverse=True)
    _zapisz("znaczniki_kuratorskie.csv",
            ["ksywa", "tytul", "znaczniki", "data", "miejsce", "kraj", "link"], znal)

    # ── 5. DE SCHOOL — cykle i sale ─────────────────────────────────────────
    # Osobno, bo to jedyny zbiór, w którym SALA i CYKL są danymi pewnymi
    # (siedzą w adresie strony), a nie zgadywane z tytułu.
    p_ds = ZRODLO / "de_school.json"
    if p_ds.exists():
        ds = json.loads(p_ds.read_text())
        cykle = collections.defaultdict(list)
        for r in ds:
            cykle[(r.get("wydarzenie", ""), r.get("scena", ""))].append(r)
        wiersze = []
        for (cykl, sala), rr in sorted(cykle.items(), key=lambda x: -len(x[1])):
            lata = sorted({r["data"][:4] for r in rr if r.get("data")})
            wiersze.append((cykl, sala, len(rr),
                            len({r["ksywa"] for r in rr}),
                            lata[0] if lata else "", lata[-1] if lata else ""))
        _zapisz("de_school_cykle.csv",
                ["cykl", "sala", "setow", "artystow", "rok_od", "rok_do"], wiersze)

    # ── PODSUMOWANIE ────────────────────────────────────────────────────────
    n_par = len(par)
    n_wroc = sum(1 for v in par.values() if v >= 2)
    print(f"\ngalerie (miejsca):        {len(galerie)}")
    print(f"pary artysta-miejsce:     {n_par}")
    print(f"  z powrotem (>=2):       {n_wroc}  ({100 * n_wroc / n_par:.1f}%)")
    print(f"  >=5 razy:               {sum(1 for v in par.values() if v >= 5)}")
    print(f"wystepow ze znacznikiem:  {len(znal)}  "
          f"({100 * len(znal) / len(wystepy):.1f}%)")
    print(f"  rozklad: {dict(licznik.most_common())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
