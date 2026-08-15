"""Przekłada surowe sety z playlist rocznikowych na słownik z NAZEWNICTWO.md.

Wejście: `roczniki_sety.json` (25 kolekcji, 1574 pozycje, 770 unikalnych).
Wyjście: wiersze gotowe do `miksy.json` — jedno pole = jedno pytanie.

Trzy miejsca, w których świadomie NIE zgadujemy:

  * FORMAT `live`. Słowo „live" w tytule znaczy dwie różne rzeczy: „gram na
    maszynach" („SKINNERBOX Live @ Garbicz") albo „to jest nagranie z imprezy"
    („Live@ Garbicz Festival 2014"). Rozstrzyga pozycja: „live" doklejone do
    nazwy artysty, przed separatorem, to deklaracja formatu. „Live" na
    początku tytułu opisuje nagranie i zostawia pole puste — ADR-005 mówi, że
    puste znaczy „nie wiem" i jest poprawną wartością.

  * ROK. Bierzemy go z kolekcji, do której set należy, a nie z daty wrzutu.
    Dave Dinger wrzucił zamknięcie Garbicza 2014 dopiero 9 września, a niektóre
    sety wiszą wrzucone rok po fakcie.

  * KSYWA. Nazwa z tytułu wygrywa z nazwą konta, bo konta bywają kolektywami
    („Permanent Aktiv" wrzuca set Marabou). Gdy z tytułu nic sensownego nie
    wychodzi, wpada nazwa konta i wiersz dostaje `pewnosc=niepewne`.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import unicodedata as U

OUT = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")

# Parkiety Garbicza. Klucz = wariant zapisu spotykany w tytułach i opisach,
# wartość = nazwa kanoniczna. Kolejność ma znaczenie: „seebühne" musi trafić
# przed gołym „see", bo inaczej każdy Seebühne zostanie zapisany jako See.
SCENY_GARBICZ: list[tuple[str, str]] = [
    (r"seeb[üue]hne", "Seebühne"),
    (r"wiese(?:n?floor)?", "Wiese"),
    (r"\bwald\b", "Wald"),
    (r"lichtung", "Lichtung"),
    (r"juicy(?:\s*bar)?", "Juicy Bar"),
    (r"buk\s*corner", "Buk Corner"),
    (r"crazy\s*parad[ií]se", "Crazy Paradise"),
    (r"dickicht", "Crazy Paradise"),          # dawna nazwa tego samego parkietu
    (r"pleasure\s*island", "Pleasure Island"),
    (r"(?:ali'?s\s*)?tee?[\s-]?bar", "Teabar"),
    (r"ambient\s*floor", "Ambient Floor"),
    (r"loco\s*para[ií]so", "Loco Paraiso"),
    (r"weinbar", "Weinbar"),
    (r"voodoohop", "Voodoohop"),
    (r"bachstelzen", "Bachstelzen"),
    (r"kn[üu]ller", "Knüller"),
    (r"\bkanton\b", "Kanton"),
    (r"\bsee\b", "See"),
]

# Parkiety Audioriver. Osobny słownik, bo nazwy się gryzą: „Park Stage"
# w Audioriver to konkretna scena, a w Garbiczu „park" nie znaczy nic.
# Festiwal jest też ruchomy — do 2023 Płock, od 2024 Łódź — więc nazwy scen
# zmieniały się razem z miejscem i obie generacje muszą tu być.
SCENY_AUDIORIVER: list[tuple[str, str]] = [
    (r"circus\s*(?:stage)?", "Circus"),
    (r"\bpark\s*stage\b", "Park"),
    (r"truly\s*unique", "Truly Unique"),
    (r"radio\s*kampus|kampus\s*stage", "Kampus"),
    (r"w\s*punkt", "W Punkt"),
    (r"chill\s*out\s*(?:stage)?|chillout|chill\s*stage", "Chillout"),
    (r"off\s*piotrkowska", "OFF Piotrkowska"),
    (r"main\s*stage|scena\s*g[łl][óo]wna", "Main Stage"),
    (r"beach\s*(?:stage)?|pla[żz]a", "Plaża"),
    (r"forest\s*(?:stage)?|le[śs]na", "Forest"),
    (r"sunday\s*stage", "SunDay"),
]

# Parkiety Wisłoujścia. Cztery, każdy z własnym gatunkiem — festiwal sam je
# tak opisuje, więc scena niesie tu więcej niż miejsce: Twierdza to techno,
# Szaniec tech-house i disco, Raj downtempo i chillout, Bastion industrial,
# acid i rave.
SCENY_WISLOUJSCIE: list[tuple[str, str]] = [
    (r"twierdz[ay]", "Twierdza"),
    (r"szaniec|szańc", "Szaniec"),
    (r"\braj\b", "Raj"),
    (r"bastion", "Bastion"),
]

SCENY_WG_FESTIWALU = {
    "Garbicz Festival": SCENY_GARBICZ,
    "Audioriver": SCENY_AUDIORIVER,
    "Wisłoujście": SCENY_WISLOUJSCIE,
}

# `rola` to miejsce w PROGRAMIE. Dwie pozycje dołożone przy tej partii:
# `zachod-slonca` (sunset/sundowner) i `popoludnie` — obie wystąpiły
# w opisach na tyle często, żeby nie wpychać ich do „noc".
ROLE: list[tuple[str, str]] = [
    (r"sunrise|sonnenaufgang|sun\s?rise", "wschod-slonca"),
    (r"after[\s-]?hour", "afterhour"),
    (r"closing|closer\b|abschluss", "zamkniecie"),
    (r"opening|warm[\s-]?up|er[öo]ffnung", "otwarcie"),
    (r"sunset|sundowner|sonnenuntergang", "zachod-slonca"),
    (r"morning|morgen(?:s)?\b", "poranek"),
    (r"afternoon|nachmittag|day\s?time", "popoludnie"),
    (r"all[\s-]?night", "all-night"),
    (r"peak[\s-]?time", "peak"),
    (r"\bnight\b|\bnacht\b", "noc"),
]

DNI = {"monday": "poniedziałek", "tuesday": "wtorek", "wednesday": "środa",
       "thursday": "czwartek", "friday": "piątek", "saturday": "sobota",
       "sunday": "niedziela", "montag": "poniedziałek", "dienstag": "wtorek",
       "mittwoch": "środa", "donnerstag": "czwartek", "freitag": "piątek",
       "samstag": "sobota", "sonntag": "niedziela"}

# Separatory między nazwą artysty a resztą tytułu, od najpewniejszego.
SEP = re.compile(r"\s*(?:@|(?<=\s)at\s|\blive\s*@|\||//|\s[-–—*]\s|\bin\s+garbicz)", re.I)
# Kandydat na ksywę, który zawiera którekolwiek z tych słów, jest tytułem
# imprezy albo sceny, nie nazwą człowieka.
SZUM = re.compile(r"garbicz|audio\s?river|festival|festiwal|\bstage\b|"
                  r"^\s*(?:closing|opening|sunrise|sunset|afterhour|warm[\s-]?up)"
                  r"(?:\s*set)?\s*$|^\s*live\s*set\s*$", re.I)


def _norm(s: str) -> str:
    s = U.normalize("NFKD", s or "")
    s = "".join(c for c in s if not U.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def scena_z(tekst: str, festiwal: str = "Garbicz Festival") -> str | None:
    for wzor, nazwa in SCENY_WG_FESTIWALU.get(festiwal, []):
        if re.search(wzor, tekst, re.I):
            return nazwa
    return None


def rola_z(tekst: str) -> str | None:
    for wzor, nazwa in ROLE:
        if re.search(wzor, tekst, re.I):
            return nazwa
    return None


def format_z(tytul: str, opis: str) -> str:
    """Patrz nagłówek modułu — pozycja słowa „live" niesie znaczenie."""
    if re.search(r"\bb2b\b|back\s?to\s?back", tytul + opis, re.I):
        return "b2b"
    if re.search(r"\ball\s?vinyl\b|only\s+vinyl|winyl", tytul + opis, re.I):
        return "winyl"
    if re.search(r"live\s?(?:set|act|pa\b)|liveset|\(live\)", tytul + opis, re.I):
        return "live"
    przed = SEP.split(tytul, 1)[0]
    if re.search(r"\blive\b", przed, re.I) and not re.match(r"\s*live\b", tytul, re.I):
        return "live"
    if re.search(r"\blive\b", tytul, re.I):
        return ""                      # niejednoznaczne — pole zostaje puste
    return "dj-set"


def czas_z(tekst: str) -> str:
    """`dzień HH:MM-HH:MM`, tyle ile faktycznie stoi w tekście."""
    dzien = ""
    for ang, pl in DNI.items():
        if re.search(rf"\b{ang}\b", tekst, re.I):
            dzien = pl
            break
    zakres = re.search(r"\b(\d{1,2})[:.](\d{2})\s*(?:-|–|—|to|bis)\s*(\d{1,2})[:.](\d{2})", tekst)
    if zakres:
        h1, m1, h2, m2 = zakres.groups()
        return f"{dzien} {int(h1):02d}:{m1}-{int(h2):02d}:{m2}".strip()
    ampm = re.search(r"\b(\d{1,2})\s?(am|pm)\s*(?:-|–|—|to)\s*(\d{1,2})\s?(am|pm)", tekst, re.I)
    if ampm:
        def h24(h, s):
            h = int(h) % 12
            return h + (12 if s.lower() == "pm" else 0)
        return f"{dzien} {h24(ampm[1], ampm[2]):02d}:00-{h24(ampm[3], ampm[4]):02d}:00".strip()
    poj = re.search(r"\b(\d{1,2})[:.](\d{2})\b", tekst)
    if poj:
        return f"{dzien} {int(poj[1]):02d}:{poj[2]}".strip()
    return dzien


# Dwa układy tytułu, w których nazwa artysty NIE stoi na początku, i przez
# które wpadały nazwy kanałów zamiast ludzi:
#   „Shaun Reeves Recorded Live from Audioriver 2011" → konto „Dance TV"
#   „Spectrum Radio 223 by JORIS VOORN"              → konto „Spectrum Radio"
PRZED_LIVE = re.compile(r"^(.{2,45}?)\s+(?:recorded\s+)?live\s+(?:from|at|@)\b", re.I)
PO_BY = re.compile(r"\bby\s+([A-Za-zÀ-ž0-9][\w'’.&\- ]{1,40}?)\s*$", re.I)


def ksywa_z(tytul: str, uploader: str) -> tuple[str, str]:
    """(ksywa, pewnosc). Nazwa z tytułu bije nazwę konta."""
    cykl = CYKL.match(tytul)
    if cykl and not SZUM.search(cykl.group(1)):
        return cykl.group(1).strip(" -–—*_|."), "potwierdzone"
    dopisek = PRZED_LIVE.match(tytul)
    if dopisek and not SZUM.search(dopisek.group(1)):
        k = dopisek.group(1).strip(" -–—*_|.")
        return k, ("potwierdzone" if _norm(k) == _norm(uploader) else "niepewne")
    ogon = PO_BY.search(tytul)
    if ogon and not SZUM.search(ogon.group(1)):
        k = ogon.group(1).strip(" -–—*_|.")
        return k, ("potwierdzone" if _norm(k) == _norm(uploader) else "niepewne")
    kandydat = SEP.split(tytul, 1)[0].strip(" -–—*_|.")
    # „Spectrum Radio 223 by JORIS VOORN | Live from Audioriver" — `by` stoi na
    # końcu PIERWSZEGO członu, nie całego tytułu, więc PO_BY musi wejść jeszcze
    # raz, już po rozcięciu.
    ogon = PO_BY.search(kandydat)
    if ogon and not SZUM.search(ogon.group(1)):
        k = ogon.group(1).strip(" -–—*_|.")
        return k, ("potwierdzone" if _norm(k) == _norm(uploader) else "niepewne")
    kandydat = re.sub(r"\b(live|dj\s?set|set|b2b)\b\s*$", "", kandydat, flags=re.I).strip()
    dobra = (kandydat and len(kandydat) <= 45 and not SZUM.search(kandydat)
             and not kandydat.isdigit())
    if not dobra:
        return uploader or "", "niepewne"
    if _norm(kandydat) == _norm(uploader):
        return kandydat, "potwierdzone"
    # Konto bywa kolektywem; nazwa z tytułu zostaje, ale bez pieczątki.
    return kandydat, "niepewne"


# Czy wiersz naprawdę jest setem Z TEGO festiwalu. Sama fraza w tytule nie
# wystarcza: kolekcja „Garbicz Lineup 2024" to ZAPOWIEDŹ line-upu — 106 ze 198
# pozycji to sety tych artystów zagrane gdzie indziej. Ratują nas nazwy
# parkietów występujących wyłącznie na danym festiwalu. „Wiese", „Wald"
# i „See" NIE liczą — to zwykłe niemieckie słowa. „Main Stage" i „Park"
# w Audioriver też nie, bo tak nazywa się scena na połowie festiwali świata.
NIE_ZAGRANE = re.compile(r"\bpromo(?:mix|\s?mix)?\b|\bkonkurs\b|\bcontest\b|"
                         r"\bcompetition\b|\bwarm[\s-]?up\s+mix\b|\bzapowied", re.I)

# Audycja MÓWIONA. „Strefa Ruchu #14 — Audioriver 2024, Cały Ten Rap, Hatti
# Vatti, Bicep, Denzel Curry" to podcast, w którym dwoje ludzi OPOWIADA
# o festiwalu obok Kendricka, Diuny i EURO 2024. Rozpoznaje się po opisie:
# spis tematów z minutażem i lista prowadzących.
#
# UWAGA NA RÓŻNICĘ, bo łatwo ją zgubić: to NIE to samo, co podcast, w którym
# DJ gra („RA.842 Fadi Mohem", „DRONE Podcast 053", „Spectrum Radio 223 by
# Joris Voorn"). Tamte są pełnoprawnymi setami i cała ta kategoria — radio,
# radio-online, cykle online — jest w środowisku DJ-skim osobna i mocna.
# Audycja gadana wypada z bazy (decyzja Janka 2026-08-14: „audycje gdzie
# gadają nie zbierajmy"). Podcast, w którym DJ GRA, zbieramy — i to osobno,
# skryptem `podcasty.py`.
GADANE = re.compile(r"\bw \w+ odcinku\b|\bwyst[ąa]pili\b|\bzarejestrowano\b|"
                    r"\bprowadz[ąa]cy\b|\bomawiam", re.I)

# Cykl podcastowy, który PUBLIKUJE cudzy set. Set jest prawdziwy, ale ksywą
# musi być artysta, nie nazwa cyklu: „Breaky Vibes Podcast 022 - SICK" →
# SICK, „DRONE Podcast 053 - Michal Jablonski LIVE at Audioriver" → Michal
# Jablonski. Bez tego w tabeli artystów rosną wiersze typu „Podcast 022".
CYKL = re.compile(r"^.{2,40}?\b(?:podcast|cast|radio|sessions?|series)\s*"
                  r"#?\d{1,4}\s*[-–—:|]\s*(.{2,40}?)"
                  r"(?=\s*[-–—:|(]|\s+live\b|\s+@|\s*$)", re.I)

NALEZY = {
    "Garbicz Festival": (
        re.compile(r"garbi[ct]", re.I),
        re.compile(r"seeb[üue]hne|bu[ck]k?\s*corner|juicy\s*bar|crazy\s*parad|"
                   r"dickicht|lichtung|loco\s*para|pleasure\s*island", re.I),
    ),
    "Audioriver": (
        re.compile(r"audio\s?river", re.I),
        re.compile(r"truly\s*unique|off\s*piotrkowska|w\s*punkt", re.I),
    ),
    "Wisłoujście": (
        re.compile(r"wis[łl]ouj[śs]cie|wisloujscie", re.I),
        # „Twierdza" sama w sobie znaczy po prostu „forteca" i stoi w nazwach
        # innych imprez, więc do wyłącznych nie trafia. Zostaje sama nazwa.
        re.compile(r"(?!x)x^"),
    ),
}


def nalezy_do(tytul: str, opis: str, festiwal: str, *, tylko_tytul: bool) -> bool:
    """Czy to set z tego festiwalu.

    `tylko_tytul` rozstrzyga, ile zaufania ma opis, i zależy od źródła:

      * KOLEKCJA KURATOROWANA ręczy sama za siebie — ktoś zebrał te sety jako
        „Garbicz 2019", więc wystarczy wzmianka gdziekolwiek.
      * WYSZUKIWARKA nie ręczy za nic. Fraza „audioriver" w opisie łapie
        odcinki podcastów, w których artysta tylko WSPOMINA, że tam grał
        („MELODIC SERIES #26", „#97 Sosia – DISCOnnect cast"). Nazwa musi
        wtedy stać w tytule.
    """
    # Miks NA festiwal to nie miks Z festiwalu. „AudioRiver 2009 Promo"
    # i „Konkurs Audioriver DJset" to zapowiedź i zgłoszenie konkursowe —
    # prawdziwe miksy, ale nikt ich tam nie zagrał.
    if NIE_ZAGRANE.search(tytul):
        return False
    nazwa, wylaczne = NALEZY[festiwal]
    gdzie = tytul if tylko_tytul else f"{tytul}\n{opis}"
    return bool(nazwa.search(gdzie) or wylaczne.search(gdzie))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wejscie", default="roczniki_sety.json")
    ap.add_argument("--wyjscie", default="roczniki_wiersze.json")
    ap.add_argument("--festiwal", default="Garbicz Festival",
                    choices=sorted(NALEZY))
    ap.add_argument("--min-minut", type=int, default=20,
                    help="Krótsze pozycje to zapowiedzi i zajawki, nie sety.")
    ap.add_argument("--z-wyszukiwarki", action="store_true",
                    help="Źródło to wyszukiwanie, nie kuratorowana kolekcja: "
                         "nazwa festiwalu musi stać w TYTULE, bo opis łapie "
                         "podcasty, które tylko wspominają, że artysta tam grał.")
    args = ap.parse_args()
    surowe = json.loads((OUT / args.wejscie).read_text())
    # Rok bierzemy z kolekcji, nie z daty wrzutu (patrz nagłówek).
    rok_kolekcji: dict[int, str] = {}
    uniq: dict[int, dict] = {}
    for kol in surowe:
        m = re.search(r"(20\d{2})", kol["playlista"]) or re.search(r"(20\d{2})", kol["url"])
        rok = m.group(1) if m else ""
        for s in kol["sety"]:
            uniq.setdefault(s["id"], s)
            if rok and s["id"] not in rok_kolekcji:
                rok_kolekcji[s["id"]] = rok

    wiersze = []
    krotkie = obce = gadane = 0
    for sid, s in uniq.items():
        tytul = (s.get("tytul") or "").strip()
        opis = (s.get("opis") or "").strip()
        tekst = f"{tytul}\n{opis}"
        if (s.get("dlugosc_min") or 0) < args.min_minut:
            krotkie += 1
            continue
        if GADANE.search(opis):
            gadane += 1
            continue
        # Wiersz, który nie należy do festiwalu, NIE jest kasowany — zostaje
        # jako miks tego artysty, tylko z pustym `wydarzenie`. Wyrzucenie go
        # zgubiłoby prawdziwy set tylko dlatego, że zagrany gdzie indziej.
        swoj = nalezy_do(tytul, opis, args.festiwal,
                         tylko_tytul=args.z_wyszukiwarki)
        if not swoj:
            obce += 1
        rok_tytul = re.search(r"\b(20\d{2})\b", tytul)
        rok = (rok_tytul.group(1) if rok_tytul
               else rok_kolekcji.get(sid) or (s.get("data_wrzutu") or "")[:4])
        ksywa, pewnosc = ksywa_z(tytul, s.get("uploader") or "")
        wiersze.append({
            "ksywa": ksywa,
            "tytul": tytul,
            "wydarzenie": args.festiwal if swoj else "",
            "typ": "festiwal" if swoj else "",
            "scena": (scena_z(tekst, args.festiwal) or "") if swoj else "",
            "format": format_z(tytul, opis),
            "rola": rola_z(tekst) or "",
            "czas": czas_z(opis),
            "data": rok,
            "zrodlo": "soundcloud",
            "pewnosc": pewnosc,
            "link": s.get("link") or "",
            "opis": opis,
            "dlugosc_min": s.get("dlugosc_min") or "",
            "konto": s.get("uploader") or "",
        })

    p = OUT / args.wyjscie
    p.write_text(json.dumps(wiersze, ensure_ascii=False, indent=1))

    def ile(pole):
        return sum(1 for w in wiersze if w[pole])
    print(f"wierszy: {len(wiersze)}   "
          f"(odrzucone: za krótkie {krotkie}, audycje mówione {gadane}; "
          f"zagrane poza {args.festiwal}: {obce})")
    for pole in ("scena", "rola", "czas", "opis", "data"):
        print(f"  {pole:8s} wypełnione: {ile(pole):3d}  ({ile(pole)/len(wiersze)*100:.0f}%)")
    print(f"  format live/b2b/winyl: "
          f"{sum(1 for w in wiersze if w['format'] in {'live','b2b','winyl'})}, "
          f"pustych: {sum(1 for w in wiersze if not w['format'])}")
    print(f"  pewnosc potwierdzone: {sum(1 for w in wiersze if w['pewnosc']=='potwierdzone')}")
    print(f"zapisane: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
