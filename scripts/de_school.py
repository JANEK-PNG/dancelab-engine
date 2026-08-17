"""Archiwum De School Amsterdam — klub, który sam się zarchiwizował.

Janek podrzucił `hetarchief.deschoolamsterdam.nl`. De School działała
2016-2020 w dawnej szkole technicznej przy Jan van Galenstraat i była jednym
z najważniejszych klubów tamtej dekady — 24-godzinna licencja, brak zdjęć na
parkiecie, sety po kilkanaście godzin. Po zamknięciu klub wydał WŁASNE
archiwum: sety na Mixcloud, z metadanymi.

Dla nas jest to zbiór innego rodzaju niż wszystko dotąd, bo ADRES KAŻDEGO SETU
NIESIE KOMPLET OPISU:

    /sets/01-07-2016_friday_de-zomernacht_delta-funktionen_club/
           └ data    └ dzień  └ wydarzenie   └ artysta        └ SALA

Data, dzień tygodnia, nazwa cyklu, artysta i sala — z samego adresu, bez
parsowania strony. To jest dokładnie „kto, kiedy i w jakich warunkach",
tylko na poziomie JEDNEGO KLUBU I JEDNEJ SALI, a nie festiwalu.

Sala ma tu znaczenie, którego nie ma nigdzie indziej w bazie: De School miała
`club` (główny parkiet, techno) i `de-club` (mniejsza, bardziej house'owa),
a do tego `muziekzaal` na koncerty. Ten sam artysta grał inaczej w każdej.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

OUT = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")
BAZA = "https://hetarchief.deschoolamsterdam.nl"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

LINK = re.compile(r'href="(/sets/[^"]+)"')
# Odtwarzacz nie jest na stronie setu, tylko pod jej podadresem `/embed/`,
# a adres Mixcloud siedzi tam zakodowany w parametrze `feed` widżetu.
MIXCLOUD = re.compile(r'player-widget\.mixcloud\.com/widget/iframe/\?[^"]*feed=([^"&]+)')
# data_dzień_wydarzenie_artysta_sala — ostatni człon to zawsze sala.
SLUG = re.compile(r"^/sets/(\d{2}-\d{2}-\d{4})_([a-z]+)_(.+)/$")

DNI = {"monday": "poniedziałek", "tuesday": "wtorek", "wednesday": "środa",
       "thursday": "czwartek", "friday": "piątek", "saturday": "sobota",
       "sunday": "niedziela"}

# Sale De School. „club" i „de-club" to DWA RÓŻNE parkiety, mimo mylącej
# nazwy — pierwszy to duży techno, drugi mniejszy i bardziej house'owy.
# Sale De School, od NAJDŁUŻSZEJ nazwy. Kolejność jest istotna: cięcie na
# ostatnim podkreśleniu wpychało do sali kawałek ksywy („Dj Maria De Club",
# „Bjarki Live De Club"), bo nazwy sal bywają dwu- i trzyczłonowe.
SALE_KOLEJNOSC = [
    ("het-muzieklokaal", "Het Muzieklokaal"),
    ("de-binnentuin", "De Binnentuin"),
    ("de-meetkamer", "De Meetkamer"),
    ("de-lasserij", "De Lasserij"),
    ("het-terras", "Het Terras"),
    ("de-club", "De Club"),
    ("de-aula", "De Aula"),
    ("terras", "Het Terras"),
    ("cotl", "COTL"),
    ("club", "Club"),
]


def _get(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:                                         # noqa: BLE001
        print(f"    {e}", file=sys.stderr)
        return None


def rozbierz_slug(s: str) -> dict | None:
    m = SLUG.match(s)
    if not m:
        return None
    data, dzien, reszta = m.groups()
    # Salę odcinamy po ZNANEJ nazwie z końca, nie po ostatnim podkreśleniu.
    sala, rdzen = "", reszta
    for koncowka, ladna in SALE_KOLEJNOSC:
        if reszta.endswith("_" + koncowka):
            sala, rdzen = ladna, reszta[: -len(koncowka) - 1]
            break
    # Rdzeń to `wydarzenie_artysta`; wydarzenie jest nazwą cyklu i stoi z przodu.
    if "_" in rdzen:
        wyd, art = rdzen.rsplit("_", 1)
    else:
        wyd, art = "", rdzen
    d, mm, rr = data.split("-")
    return {
        "data": f"{rr}-{mm}-{d}",
        "dzien": DNI.get(dzien, dzien),
        "wydarzenie": wyd.replace("-", " ").strip(),
        "ksywa": art.replace("-", " ").strip(),
        "sala": sala,
        "link_strony": BAZA + s,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stron", type=int, default=200)
    ap.add_argument("--mixcloud", action="store_true",
                    help="Dociągnij link do Mixcloud z każdej strony setu "
                         "(jedno zapytanie na set — wolniej, ale daje nagranie)")
    ap.add_argument("--wyjscie", default="de_school.json")
    args = ap.parse_args()

    slugi: list[str] = []
    for strona in range(1, args.stron + 1):
        url = f"{BAZA}/index/" if strona == 1 else f"{BAZA}/index/page{strona}/"
        h = _get(url)
        if not h:
            break
        znal = sorted(set(LINK.findall(h)))
        nowe = [s for s in znal if s not in slugi]
        if not nowe:
            print(f"  strona {strona}: nic nowego — koniec")
            break
        slugi += nowe
        if strona % 10 == 0:
            print(f"  strona {strona} — setów {len(slugi)}", flush=True)
        time.sleep(0.25)

    wynik, bez_slugu = [], 0
    for s in slugi:
        w = rozbierz_slug(s)
        if not w:
            bez_slugu += 1
            continue
        wynik.append(w)

    if args.mixcloud:
        for i, w in enumerate(wynik, 1):
            h = _get(w["link_strony"].rstrip("/") + "/embed/")
            # Pierwsze trafienie bywa zakomentowanym przykładem („testtesttest"),
            # więc bierzemy pierwsze, które NIE jest w komentarzu HTML.
            czysty = re.sub(r"<!--.*?-->", "", h or "", flags=re.S)
            m = MIXCLOUD.search(czysty)
            # `feed` bywa pełnym adresem ALBO samą ścieżką („/DSAMS/…").
            # Doklejanie przedrostka na ślepo dawało „mixcloud.comhttps://…".
            surowy = urllib.parse.unquote(m.group(1)) if m else ""
            w["mixcloud"] = (surowy if surowy.startswith("http")
                             else ("https://www.mixcloud.com" + surowy)
                             ).rstrip("/") + "/" if surowy else ""
            if i % 50 == 0:
                print(f"  mixcloud {i}/{len(wynik)}", flush=True)
                (OUT / args.wyjscie).write_text(
                    json.dumps(wynik, ensure_ascii=False, indent=1))
            time.sleep(0.25)

    p = OUT / args.wyjscie
    p.write_text(json.dumps(wynik, ensure_ascii=False, indent=1))
    import collections
    print(f"\nsetów: {len(wynik)}  (adresów nie do rozebrania: {bez_slugu})")
    print(f"  artystów:    {len({w['ksywa'] for w in wynik})}")
    print(f"  lata:        {sorted({w['data'][:4] for w in wynik})}")
    print(f"  sale:        {collections.Counter(w['sala'] for w in wynik).most_common()}")
    print(f"  wydarzenia:  {len({w['wydarzenie'] for w in wynik})} cykli")
    if args.mixcloud:
        print(f"  z linkiem Mixcloud: {sum(1 for w in wynik if w.get('mixcloud'))}")
    print(f"zapisane: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
