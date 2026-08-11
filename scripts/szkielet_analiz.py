"""Szkielet pod dane z analiz — wszystko poza samą analizą.

Janek 2026-08-10: „BPM, wszystkie analizy, czasy, tonacje i szwy zostawmy na
inny czat do tego dostosowany. Cała machineria ma zostać. My przygotujmy tego
excela tak, żeby tam później wpisać wszystkie brakujące elementy. Sami
uzupełnijmy wszystko bez liczenia i zróbmy super szkielet pod dane z analiz".

Podział jest czysty i wart zapisania: **tu nie liczymy nic z dźwięku.**
Wszystko, co ten skrypt wypełnia, da się wyprowadzić z tego, co już mamy —
zliczyć, ponumerować, połączyć. Wszystko, co wymaga posłuchania pliku,
dostaje kolumnę i zostaje puste.

Powstają trzy tabele, których dotąd nie było:

  * ENCJE ARTYSTY — `artysta_id` nadany raz i nigdy niezmieniany, plus aliasy.
    Dotąd łączyliśmy wszystko po ksywie, a 74% encji istniało wyłącznie jako
    łańcuch znaków. Ksywa przestaje być kluczem, zostaje atrybutem.
  * UTWORY KANONICZNE — 148 tysięcy pozycji tracklist to nie 148 tysięcy
    utworów. Ten sam kawałek wraca w dziesiątkach setów i dopiero zliczony
    mówi coś sensownego: ile razy grany, przez ilu DJ-ów, w jakich latach.
    To jest też jedyna sensowna jednostka do wpisania BPM i tonacji — raz
    na utwór, nie raz na wystąpienie.
  * SZWY — jednostka analizy DanceLab, która dotąd nie istniała jako tabela.
    Para „utwór wychodzący → utwór wchodzący" w obrębie jednego setu.

CZEGO NIE GENERUJEMY. Szwy tylko dla tracklist połączonych z setem PO LINKU.
Powód jest praktyczny: żeby policzyć cokolwiek o przejściu, trzeba mieć
nagranie. Tracklista bez pewnego adresu daje szew, którego nikt nie zmierzy —
byłby to wiersz do wypełnienia, którego nie da się wypełnić.
"""

from __future__ import annotations

import json
import pathlib
import re
import unicodedata as U

OUT = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")

# Kolumny czekające na analizę dźwięku. Zostają PUSTE — wypełni je osobny
# przebieg, w osobnym miejscu. Nazwy i jednostki ustalone tu, żeby ten, kto
# będzie je wypełniał, nie musiał niczego zgadywać.
KOLUMNY_UTWORU = [
    ("bpm", "tempo w uderzeniach na minutę, jedna liczba"),
    ("bpm_pewnosc", "0-1; niska przy podejrzeniu oktawy"),
    ("tonacja", "zapis Camelot, np. 8A"),
    ("tonacja_klasyczna", "np. A-moll"),
    ("tonacja_pewnosc", "0-1"),
    ("energia", "0-1, umowna skala DanceLab"),
    ("gestosc_groove", "0-1"),
    ("obecnosc_basu", "0-1"),
    ("dlugosc_s", "długość utworu w sekundach"),
    ("analiza_wersja", "wersja silnika, która to policzyła"),
    ("analiza_data", "RRRR-MM-DD"),
]

KOLUMNY_SZWU = [
    ("bpm_z", "tempo utworu wychodzącego"),
    ("bpm_do", "tempo utworu wchodzącego"),
    ("delta_bpm", "różnica; ujemna = zwolnienie"),
    ("delta_bpm_proc", "różnica w procentach — to ona decyduje o wykonalności"),
    ("tonacja_z", "Camelot"),
    ("tonacja_do", "Camelot"),
    ("zgodnosc_harmoniczna", "idealna | sasiednia | wzgledna | zadna"),
    ("dlugosc_przejscia_s", "ile trwa nakładanie"),
    ("typ_przejscia", "cut | blend | echo | loop | filtr | inne"),
    ("bas_wstrzymany", "tak | nie — reguła wejścia Janka"),
    ("energia_z", "0-1"),
    ("energia_do", "0-1"),
    ("delta_energii", "różnica"),
    ("analiza_wersja", ""),
    ("analiza_data", ""),
]


def _n(s: str) -> str:
    s = U.normalize("NFKD", s or "")
    s = "".join(c for c in s if not U.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def _n_utwor(wyk: str, tyt: str) -> str:
    """Klucz utworu. Wersje i remiksy to OSOBNE utwory — mają inne tempo
    i inną tonację, więc sklejenie ich zniszczyłoby to, po co je zbieramy.
    Usuwamy tylko szum zapisu, nie treść nawiasu."""
    t = re.sub(r"\s+", " ", (tyt or "").strip())
    return f"{_n(wyk)}|{_n(t)}"


# Tytuł-zaślepka to BRAK nazwy, nie nazwa. Złapane 2026-08-11 na mechanizmie
# tripletów Janka: „Lyra Pramuk – [Unreleased]" miało 12 kontekstów, bo klucz
# wykonawca+tytuł skleił RÓŻNE niewydane utwory w jedno ID — fabrykując
# powtórzenia, których nigdy nie było (76 sklejonych encji, do 33 wystąpień).
# Zaślepka nie skleja się nigdy: każde wystąpienie dostaje własną encję,
# z zachowanym wykonawcą (cenny dla pięter pośrednich podpowiedzi).
_STOP_ZASLEPKI = {"unreleased", "unnamed", "untitled", "unknown", "id", "ids",
                  "tba", "forthcoming", "dubplate", "white", "label"}


def _zaslepka(tyt: str) -> bool:
    t = (tyt or "").strip()
    if not t:
        return True
    # tokeny 1-literowe ignorujemy: zepsute kodowanie („â€“") wstrzykuje „a"
    slowa = [s for s in re.findall(r"[a-z]+", U.normalize("NFKD", t).lower())
             if len(s) > 1]
    if not slowa:
        # "?" to zaślepka; "1998" albo "303" to pełnoprawne tytuły
        return not any(c.isdigit() for c in t)
    return all(s in _STOP_ZASLEPKI for s in slowa)


def _klucz_utworu(wyk: str, tyt: str, nr_tracklisty: int, pozycja: int) -> str:
    """Zaślepka → klucz unikalny per WYSTĄPIENIE (nigdy się nie skleja)."""
    if _zaslepka(tyt):
        return f"__zaslepka__|{nr_tracklisty}|{pozycja}"
    return _n_utwor(wyk, tyt)


def main() -> int:
    miksy = json.loads((OUT / "miksy.json").read_text())
    tl = json.loads((OUT / "tracklisty_wszystkie.json").read_text())
    ra = json.loads((OUT / "ra.json").read_text()) if (OUT / "ra.json").exists() else {"artysci": []}
    soc = json.loads((OUT / "socials.json").read_text())
    bc = {}
    if (OUT / "bandcamp.json").exists():
        bc = {r["ksywa"]: r for r in json.loads((OUT / "bandcamp.json").read_text())["artysci"]}
    rap = {r["ksywa"]: r for r in ra["artysci"]}

    # ── 1. ENCJE ARTYSTY ────────────────────────────────────────────────────
    # Identyfikator nadajemy alfabetycznie i zapisujemy na stałe. Kolejność
    # jest obojętna, trwałość nie jest: raz nadany numer nie może się zmienić,
    # bo od tego zależą wszystkie tabele fakty.
    nazwy: dict[str, str] = {}          # klucz znormalizowany → nazwa kanoniczna
    for r in miksy:
        k = (r.get("ksywa") or "").strip()
        if k:
            nazwy.setdefault(_n(k), k)
    for k in list(rap) + list(bc) + list(soc):
        if k and _n(k):
            nazwy.setdefault(_n(k), k)

    artysci, alias = [], []
    for i, (klucz, nazwa) in enumerate(sorted(nazwy.items(), key=lambda x: x[1].lower()), 1):
        aid = f"A{i:05d}"
        r = rap.get(nazwa, {})
        b = bc.get(nazwa, {})
        s = soc.get(nazwa, {})
        artysci.append({
            "artysta_id": aid,
            "nazwa_kanoniczna": nazwa,
            "ra_id": r.get("ra_id", ""),
            "soundcloud": (s or {}).get("soundcloud", ""),
            "bandcamp": b.get("bandcamp", ""),
            "kraj": r.get("kraj", "") or (b.get("lokalizacja", "").split(",")[-1].strip()),
            "kraj_zamieszkania": r.get("kraj_zamieszkania", ""),
            "wytwornie": r.get("wytwornie", ""),
            "obserwujacych_ra": r.get("obserwujacych", ""),
        })
        alias.append({"ksywa": nazwa, "artysta_id": aid, "rodzaj": "kanoniczna"})
    po_kluczu = {a["nazwa_kanoniczna"]: a["artysta_id"] for a in artysci}
    id_po_normie = {_n(a["nazwa_kanoniczna"]): a["artysta_id"] for a in artysci}

    (OUT / "encje_artysta.json").write_text(json.dumps(artysci, ensure_ascii=False, indent=1))
    (OUT / "encje_alias.json").write_text(json.dumps(alias, ensure_ascii=False, indent=1))
    print(f"encje artysty:  {len(artysci)}  (z ra_id: {sum(1 for a in artysci if a['ra_id'])})")

    # ── 2. UTWORY KANONICZNE ────────────────────────────────────────────────
    utwory: dict[str, dict] = {}
    for wi, w in enumerate(tl):
        for j, p in enumerate(w["tracklista"]):
            tyt = (p.get("tytul") or "").strip()
            if not tyt or tyt == "ID":
                continue                      # „ID" to brak nazwy, nie utwór
            klucz = _klucz_utworu(p.get("wykonawca", ""), tyt, wi, j)
            u = utwory.setdefault(klucz, {
                "utwor_id": "", "wykonawca": (p.get("wykonawca") or "").strip(),
                "tytul": tyt, "wydawca": p.get("wydawca", "") or "",
                "wystapien": 0, "granych_przez": set(), "lata": set(),
                "zrodla": set(),
            })
            u["wystapien"] += 1
            if w.get("ksywa"):
                u["granych_przez"].add(w["ksywa"])
            if w.get("data"):
                u["lata"].add(str(w["data"])[:4])
            u["zrodla"].add(p.get("zrodlo", ""))
            if not u["wydawca"] and p.get("wydawca"):
                u["wydawca"] = p["wydawca"]

    lista_utworow = []
    for i, (klucz, u) in enumerate(
            sorted(utwory.items(), key=lambda x: (-x[1]["wystapien"], x[0])), 1):
        wiersz = {
            "utwor_id": f"U{i:06d}",
            "wykonawca": u["wykonawca"], "tytul": u["tytul"],
            "wydawca": u["wydawca"],
            "wystapien": u["wystapien"],
            "granych_przez": len(u["granych_przez"]),
            "lata": " ".join(sorted(x for x in u["lata"] if x)),
            "zrodla": " · ".join(sorted(x for x in u["zrodla"] if x)),
        }
        for pole, _ in KOLUMNY_UTWORU:
            wiersz[pole] = ""              # czeka na analizę
        lista_utworow.append(wiersz)
        u["utwor_id"] = wiersz["utwor_id"]
    (OUT / "encje_utwor.json").write_text(
        json.dumps(lista_utworow, ensure_ascii=False, indent=1))
    print(f"utwory kanoniczne: {len(lista_utworow)}  "
          f"(z {sum(w[chr(39)+chr(39)] if False else 0 for w in [])} ..." if False else f"(granych >1 raz: "
          f"{sum(1 for u in lista_utworow if u['wystapien'] > 1)})")

    # ── 3. SZWY ─────────────────────────────────────────────────────────────
    # Tylko dla tracklist połączonych z setem PO LINKU — inaczej powstałby
    # wiersz, którego nikt nie zmierzy, bo nie ma czego posłuchać.
    szwy = []
    nr = 0
    for wi, w in enumerate(tl):
        if w.get("polaczenie") != "link":
            continue
        poz = w["tracklista"]
        aid = id_po_normie.get(_n(w.get("ksywa", "")), "")
        for j in range(len(poz) - 1):
            a, b_ = poz[j], poz[j + 1]
            if (a.get("tytul") or "") in ("", "ID") and (b_.get("tytul") or "") in ("", "ID"):
                continue                  # oba nieznane — nie ma czego opisać
            nr += 1
            czas_ms = b_.get("ms")        # szew jest tam, gdzie WCHODZI nowy
            wiersz = {
                "szew_id": f"S{nr:06d}",
                "set_link": w.get("link_setu", ""),
                "artysta_id": aid, "ksywa": w.get("ksywa", ""),
                "wydarzenie": w.get("wydarzenie", ""), "data": w.get("data", ""),
                "pozycja_z": j + 1, "pozycja_do": j + 2,
                "utwor_z": f"{a.get('wykonawca','')} — {a.get('tytul','')}".strip(" —"),
                "utwor_do": f"{b_.get('wykonawca','')} — {b_.get('tytul','')}".strip(" —"),
                "utwor_z_id": utwory.get(
                    _klucz_utworu(a.get("wykonawca", ""), a.get("tytul", ""),
                                  wi, j), {}).get("utwor_id", ""),
                "utwor_do_id": utwory.get(
                    _klucz_utworu(b_.get("wykonawca", ""), b_.get("tytul", ""),
                                  wi, j + 1), {}).get("utwor_id", ""),
                "czas_ms": czas_ms if czas_ms is not None else "",
                "czas": b_.get("czas", ""),
                "zrodlo_czasu": ("zmierzony" if czas_ms is not None else "brak"),
                "zrodlo_pozycji": b_.get("zrodlo", ""),
            }
            for pole, _ in KOLUMNY_SZWU:
                wiersz[pole] = ""          # czeka na analizę
            szwy.append(wiersz)
    (OUT / "fakty_szew.json").write_text(json.dumps(szwy, ensure_ascii=False, indent=1))
    zc = sum(1 for s in szwy if s["czas_ms"] != "")
    print(f"szwy:           {len(szwy)}  (z czasem wejścia: {zc}, "
          f"czyli gotowych do zmierzenia od razu)")

    # ── 4. słownik pustych kolumn, żeby nikt nie zgadywał ───────────────────
    (OUT / "SZKIELET_ANALIZ.md").write_text(
        "# Kolumny czekające na analizę dźwięku\n\n"
        "Wypełnia je OSOBNY przebieg, w osobnym miejscu. Tu nie liczymy nic\n"
        "z dźwięku — ten plik ustala tylko nazwy i jednostki, żeby ten, kto\n"
        "będzie je wypełniał, nie musiał niczego zgadywać.\n\n"
        "## Tabela UTWORY (`encje_utwor.json`) — jedna analiza na utwór\n\n"
        "| kolumna | co wpisać |\n|---|---|\n"
        + "".join(f"| `{k}` | {o} |\n" for k, o in KOLUMNY_UTWORU)
        + "\nUtwór jest jednostką analizy, nie wystąpienie. Ten sam kawałek "
          "wraca w dziesiątkach setów — tempo i tonacja liczy się raz.\n\n"
        "## Tabela SZWY (`fakty_szew.json`) — jedna analiza na przejście\n\n"
        "| kolumna | co wpisać |\n|---|---|\n"
        + "".join(f"| `{k}` | {o} |\n" for k, o in KOLUMNY_SZWU)
        + "\n`delta_bpm_proc` liczy się względem utworu WYCHODZĄCEGO, bo to on\n"
          "wyznacza tempo, do którego DJ musi dociągnąć następny.\n\n"
          "`bas_wstrzymany` odsyła do reguły wejścia Janka: bas wstrzymany\n"
          "w 86% jego wejść. To jest pole do sprawdzenia tej reguły na cudzych\n"
          "setach.\n", encoding="utf-8")
    print(f"\nzapisane: encje_artysta · encje_alias · encje_utwor · fakty_szew "
          f"· SZKIELET_ANALIZ.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
