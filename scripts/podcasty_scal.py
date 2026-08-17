"""Scala sety podcastowe i radiowe do `miksy.json`.

Wejście trojakie, bo trojako je zbieraliśmy:

  * `podcasty_sety.json` i `podcasty_sety2.json` — konta CYKLI (RA, HÖR,
    Dekmantel, Rinse, Lot Radio…). Tu artysta jest w tytule odcinka i trzeba
    go dopasować do naszej listy.
  * `podcasty_konta.json` — konta samych ARTYSTÓW. Tu artysta jest znany
    z góry (to właściciel konta), ale trzeba rozstrzygnąć, które z jego
    wrzutów są w ogóle setem podcastowym, a które własnym utworem albo
    nagraniem z klubu.

Dwie pułapki, obie już raz kosztowały:

  * DOPASOWANIE PO PODCIĄGU. „Robert" siedzi w „Lee Ann Roberts", „Mikal"
    w „Mikalah Watego", „justi" w „Justice". Dopasowanie musi mieć granice
    słowa po obu stronach, a ksywy krótsze niż pięć znaków po normalizacji
    nie nadają się do szukania po tytule w ogóle.
  * AUDYCJA MÓWIONA. Podcast, w którym DJ gra, jest setem. Podcast, w którym
    dwoje ludzi rozmawia o festiwalu, Kendricku i Diunie, setem nie jest
    i nie zbieramy go (decyzja Janka 2026-08-14).
"""

from __future__ import annotations

import json
import pathlib
import re
import unicodedata as U

OUT = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")

# Ksywy, które nie są nazwami ludzi — wpadły z tytułów przy wcześniejszych
# przebiegach i, puszczone na 6666 tytułów, łapią wszystko.
SMIEC = re.compile(r"^\s*(?:\[?podcast\]?|recorded|live\s*mix|#?all\s*night|"
                   r"monster|river|justi|robert|truants?|opening|closing|set|mix|"
                   r"dj\s*set|promo|guest|special|part\s*\d+|vol\s*\d+)\s*$", re.I)

# Nazwa cyklu musi wypaść z tytułu PRZED dopasowaniem. Inaczej „Truant:
# TAYSTII — Clangistan Vol. II" zostaje przypisane do artysty „Truant",
# a naprawdę gra tam TAYSTII. To samo zrobiłby każdy inny cykl, którego nazwa
# przypadkiem jest też czyjąś ksywą.
PREFIKS = re.compile(r"^\s*[\w.#'&\- ]{0,32}?[#.]?\d{1,4}\s*[-–—:|]\s*|"
                     r"^\s*[\w.#'&\- ]{0,24}?\s*[:|]\s*", re.I)

# Kiedy wrzut z konta ARTYSTY jest setem podcastowym/radiowym. Konto artysty
# zawiera wszystko: własne utwory, nagrania z klubów, remiksy. Bez tego filtru
# do kategorii „podcast" wpadłby cały jego katalog.
# Konto, które jest STACJĄ albo KOLEKTYWEM, nie człowiekiem przy decku.
# Rozpoznajemy po nazwie i po objętości: 469 kont artystów dało 11216 wrzutów,
# ale mediana to kilkanaście — konto z setkami pozycji to archiwum, nie DJ.
STACJA = re.compile(r"\bradio\b|\bFM\b|\brecords?\b|\brecordings\b|\bcollective\b|"
                    r"\bcrew\b|\bpodcast\b|\bsessions\b|\bTV\b|\bmusic\b$|"
                    r"\bsounds?\b$|\blabel\b|\bstudio\b|\bcollectiv", re.I)
LIMIT_KONTA = 120        # powyżej tego konto jest archiwum, nie dyskografią DJ-a
LIMIT_ARTYSTY = 10       # cel to minimum 3 sety, nie maksimum wszystkiego

PODCASTOWE = re.compile(
    r"\bpodcast\b|\bradio\b|\bcast\s*#?\d|\b\w+cast\b|\bsessions?\b|\bshow\b|"
    r"\bguest\s*mix\b|\bresidency\b|\bmix\s*series\b|\bseries\s*#?\d|"
    r"\bNTS\b|\bRinse\b|H[ÖO]R\b|\bBoiler\s*Room\b|\bRA\.\d|\bEX\.\d|"
    r"\bTruancy\b|\bDekmantel\s*Podcast\b|\bXLR8R\b|\bfabric\b|\bCrack\s*Mix\b|"
    r"\bLot\s*Radio\b|\bKiosk\b|\bRefuge\b|\bFM\b|\bmixtape\b|\bepisode\b|"
    r"\bodcinek\b|\baudycj", re.I)

# `typ` wg NAZEWNICTWO.md, rozpoznawany z nazwy cyklu albo tytułu wrzutu.
def typ_z(tekst: str, domyslny: str = "podcast") -> str:
    if re.search(r"\bradio\b|\bFM\b|\bNTS\b|\bRinse\b|\bLot\s*Radio\b|"
                 r"\bKiosk\b|\bRefuge\b|\bstacj", tekst, re.I):
        return "radio"
    if re.search(r"H[ÖO]R\b|\bBoiler\s*Room\b|\blivestream\b|\bstream\b",
                 tekst, re.I):
        return "studio"
    return domyslny


def n2(s: str) -> str:
    """Normalizacja ZACHOWUJĄCA granice słów."""
    s = U.normalize("NFKD", s or "")
    s = "".join(c for c in s if not U.combining(c))
    return " " + re.sub(r"[^a-z0-9]+", " ", s.lower()).strip() + " "


def _n(s: str) -> str:
    s = U.normalize("NFKD", s or "")
    s = "".join(c for c in s if not U.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def wiersz(s: dict, ksywa: str, cykl: str, typ: str) -> dict:
    tekst = f"{s.get('tytul') or ''}\n{s.get('opis') or ''}"
    rok = re.search(r"\b(19[89]\d|20[0-3]\d)\b", s.get("tytul") or "")
    return {
        "ksywa": ksywa,
        "tytul": s.get("tytul") or "",
        "wydarzenie": cykl,
        "typ": typ,
        "scena": "",
        "format": ("b2b" if re.search(r"\bb2b\b|back\s?to\s?back", tekst, re.I)
                   else "live" if re.search(r"live\s?(?:set|act|pa\b)|\(live\)", tekst, re.I)
                   else "dj-set"),
        "rola": "",
        "czas": "",
        "data": rok.group(1) if rok else (s.get("data_wrzutu") or "")[:4],
        "zrodlo": "soundcloud",
        "pewnosc": "potwierdzone",
        "link": s.get("link") or "",
        "opis": s.get("opis") or "",
        "dlugosc_min": s.get("dlugosc_min") or "",
        "konto": s.get("uploader") or "",
        "sasiedztwo": "",
    }


def main() -> int:
    artysci = [a.strip() for a in (OUT / "artysci_wszyscy.txt").read_text().splitlines()
               if a.strip()]
    dopasowywalne = [a for a in artysci if len(n2(a)) >= 7 and not SMIEC.match(a)]
    wzory = [(a, re.compile(r"(?<![a-z0-9])"
                            + re.escape(n2(a).strip()).replace(r"\ ", r"\s+")
                            + r"(?![a-z0-9])")) for a in dopasowywalne]
    print(f"artystów: {len(artysci)}, dopasowywalnych po tytule: {len(dopasowywalne)}")

    nowe: list[dict] = []
    pominiete_stacje: list[tuple[str, int]] = []
    obszerne: list[tuple[str, int]] = []

    # --- konta CYKLI: artysta jest w tytule odcinka ---
    for plik in ("podcasty_sety.json", "podcasty_sety2.json"):
        if not (OUT / plik).exists():
            continue
        for k in json.loads((OUT / plik).read_text()):
            cykl_n = n2(k["playlista"]).strip()
            for s in k["sety"]:
                goly = PREFIKS.sub("", s.get("tytul") or "", count=1)
                t = n2(goly)
                if cykl_n:
                    t = t.replace(f" {cykl_n} ", " ")
                naj = None
                for a, w in wzory:
                    if w.search(t) and (naj is None or len(a) > len(naj)):
                        naj = a                        # najdłuższe trafienie wygrywa
                if naj:
                    nowe.append(wiersz(s, naj, k["playlista"],
                                       typ_z(k["playlista"] + " " + (s.get("tytul") or ""),
                                             k.get("typ", "podcast"))))

    # --- konta ARTYSTÓW: artysta znany, filtrujemy CO jest podcastem ---
    soc = json.loads((OUT / "socials.json").read_text())
    wg_uchwytu = {}
    for ks, v in soc.items():
        h = ((v or {}).get("soundcloud") or "").replace(
            "https://soundcloud.com/", "").replace("http://soundcloud.com/", "").strip("/")
        if h:
            wg_uchwytu[_n(h)] = ks
    if (OUT / "podcasty_konta.json").exists():
        for k in json.loads((OUT / "podcasty_konta.json").read_text()):
            uchwyt = k["url"].rsplit("/", 1)[-1]
            ksywa = wg_uchwytu.get(_n(uchwyt))
            if not ksywa:
                continue
            # Konto stacji albo kolektywu, które wpadło na listę artystów jako
            # „artysta". Refuge Worldwide wrzuciło 371 pozycji, THF Radio 302 —
            # to cały ich katalog, a nie sety jednego DJ-a. Wpisane pod ksywą
            # stacji zatapiają tabelę i mówią nieprawdę o tym, kto grał.
            # Wyklucza tylko NAZWA. Objętość sama w sobie nie dowodzi niczego:
            # „Siasia" i „Piasecki" mają po trzysta wrzutów i są realnymi DJ-ami
            # z dużym archiwum, nie stacjami. Wyrzucenie ich za sam rozmiar
            # ukarałoby pracowitych. Rozmiar tylko odnotowujemy.
            if STACJA.search(ksywa):
                pominiete_stacje.append((ksywa, len(k["sety"])))
                continue
            if len(k["sety"]) > LIMIT_KONTA:
                obszerne.append((ksywa, len(k["sety"])))
            kandydaci = [s for s in k["sety"]
                         if PODCASTOWE.search(f"{s.get('tytul') or ''}\n{s.get('opis') or ''}")]
            # Cel Janka to MINIMUM 3 sety podcastowe na DJ-a, nie maksimum
            # wszystkiego. Powyżej dziesięciu kolejne wiersze nie zmieniają
            # obrazu artysty, a rozmywają tabelę — bierzemy najnowsze.
            kandydaci.sort(key=lambda s: s.get("data_wrzutu") or "", reverse=True)
            for s in kandydaci[:LIMIT_ARTYSTY]:
                tekst = f"{s.get('tytul') or ''}\n{s.get('opis') or ''}"
                nowe.append(wiersz(s, ksywa, "", typ_z(tekst)))

    # --- scalenie po linku ---
    miksy = json.loads((OUT / "miksy.json").read_text())
    maja = {(r.get("link") or "").split("?")[0].rstrip("/").lower()
            for r in miksy if r.get("link")}
    dodane, widziane = [], set()
    for x in nowe:
        k = (x["link"] or "").split("?")[0].rstrip("/").lower()
        if not k or k in maja or k in widziane:
            continue
        widziane.add(k)
        dodane.append(x)
    miksy.extend(dodane)
    (OUT / "miksy.json").write_text(json.dumps(miksy, ensure_ascii=False, indent=1))

    import collections
    per = collections.Counter(
        r["ksywa"] for r in miksy
        if r.get("typ") in {"podcast", "radio", "studio"} and r.get("ksywa"))
    if obszerne:
        obszerne.sort(key=lambda x: -x[1])
        print(f"konta obszerne (przycięte do {LIMIT_ARTYSTY}, nie odrzucone): "
              + ", ".join(f"{a} ({b})" for a, b in obszerne[:6]))
    if pominiete_stacje:
        pominiete_stacje.sort(key=lambda x: -x[1])
        print(f"pominięte konta stacji/archiwów: {len(pominiete_stacje)} — "
              + ", ".join(f"{a} ({b})" for a, b in pominiete_stacje[:8]))
    print(f"dopisanych setów podcastowych/radiowych: {len(dodane)}")
    print(f"miksów w bazie: {len(miksy)}")
    print(f"artystów z >=1 setem podcastowym: {len(per)}")
    print(f"           z >=3 setami:          {sum(1 for v in per.values() if v >= 3)}")
    print("top 12:", per.most_common(12))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
