"""Bandcamp dla wszystkich DJ-ów — bo brak w Apple nie znaczy brak muzyki.

Janek 2026-08-14: „jak ktoś nie wrzuca na Apple Music to sprawdźmy Bandcampa,
przecież. I nawet dodaj do wszystkich DJ-ów Bandcampa, bo dużo może nawet nie
dodawać tego, co dodają na Bandcamp".

Obie części tej uwagi są trafne i każda z osobna:

  * BRAK W APPLE TO NIE BRAK MUZYKI. Apple trafiło 484 z 1466 artystów, ale na
    Wisłoujściu — line-up wyłącznie polski i undergroundowy — tylko 14%. Ci
    ludzie wydają na Bandcampie i winylu, więc puste pole w Apple mówiło
    dotąd nieprawdę o scenie.
  * BANDCAMP MA RZECZY, KTÓRYCH NIGDZIE INDZIEJ NIE MA. Edyty, remiksy do
    pobrania, wydawnictwa własne, nagrania na cegiełkę. Artysta obecny w obu
    miejscach i tak wrzuca tam co innego.

Bandcamp wyłączył publiczne API, ale wyszukiwarka strony chodzi po zwykłym
POST-cie na `bcsearch_public_api` i oddaje dane strukturalne. Przy okazji
niesie dwie rzeczy, których nie mieliśmy znikąd:

  * LOKALIZACJĘ — miasto i kraj, wpisane przez samego artystę;
  * FLAGĘ `is_label` — bo na Bandcampie wytwórnia i artysta wyglądają tak samo,
    a to są dwie różne rzeczy (ta sama pomyłka, przez którą wcześniej
    „Refuge Worldwide" wpadło do bazy jako DJ).

Dopasowanie jest po dokładnej nazwie, tak samo jak w Apple. Nie zgadujemy:
lepszy brak niż link do kogoś innego o podobnej ksywie.
"""

from __future__ import annotations

import argparse
import html as _html
import json
import pathlib
import re
import sys
import time
import unicodedata as U
import urllib.request

OUT = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Content-Type": "application/json"}
SZUKAJ = "https://bandcamp.com/api/bcsearch_public_api/1/autocomplete_elastic"

# Gatunki, przy których zgodna nazwa jest wiarygodna. Lista jest ta sama co
# w `dj_mapa.py` dla Apple, z tego samego powodu: filtr, który krzyczy na
# poprawne trafienia, uczy ignorować własne ostrzeżenia.
GATUNKI_OK = {"electronic", "dance", "techno", "house", "dj mix", "trance",
              "drum & bass", "dubstep", "breakbeat", "downtempo", "experimental",
              "ambient", "alternative", "world", "jazz", "pop", "rock",
              "r&b/soul", "hip-hop/rap", "reggae", "latin", "afrobeats",
              "new age", "soundtrack", "electronica", "industrial",
              "singer/songwriter", "funk / soul", "folk", "punk", "devotional",
              "spoken word", "acoustic", "blues", "classical"}

POZYCJA = re.compile(
    r'<li data-item-id="(?P<typ>track|album)-(?P<id>\d+)".*?'
    r'<a href="(?P<link>/(?:track|album)/[^"]+)".*?'
    r'<p class="title">\s*(?P<tytul>.*?)\s*(?:<|$)', re.S)


def _n(s: str) -> str:
    s = U.normalize("NFKD", s or "")
    s = "".join(c for c in s if not U.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def szukaj(nazwa: str) -> dict | None:
    """Profil o DOKŁADNIE tej nazwie albo nic."""
    dane = json.dumps({"search_text": nazwa, "search_filter": "b",
                       "full_page": False, "fan_id": None}).encode()
    try:
        req = urllib.request.Request(SZUKAJ, headers=UA, data=dane)
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception as e:                                         # noqa: BLE001
        print(f"    {e}", file=sys.stderr)
        return None
    cel = _n(nazwa)
    for w in (d.get("auto") or {}).get("results", []):
        if w.get("type") != "b" or _n(w.get("name", "")) != cel:
            continue
        gatunek = w.get("genre_name") or ""
        return {
            "bandcamp": w.get("item_url_root"),
            "nazwa_profilu": w.get("name"),
            "lokalizacja": w.get("location") or "",
            "gatunek_bandcamp": gatunek,
            "tagi": ", ".join(w.get("tag_names") or []),
            # Ta sama pułapka co w Apple: zgodna nazwa nie wystarcza.
            # „Acid Tears — Zimbabwe, Metal" i „#allNight — Portland, Metal"
            # to prawie na pewno inni ludzie niż DJ-e z Garbicza. Oznaczamy
            # do sprawdzenia zamiast po cichu wpisywać cudzy link.
            "do_sprawdzenia": gatunek.lower() not in GATUNKI_OK,
            # Na Bandcampie wytwórnia i artysta wyglądają tak samo. Ta flaga
            # jest jedynym miejscem, gdzie serwis sam mówi, co to jest.
            "to_wytwornia": bool(w.get("is_label")),
        }
    return None


def wydawnictwa(url: str, limit: int = 6) -> list[dict]:
    """Wydawnictwa z zakładki /music. Kolejność taka, jak ustawił artysta."""
    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/music",
                                     headers={"User-Agent": UA["User-Agent"]})
        with urllib.request.urlopen(req, timeout=25) as r:
            h = r.read().decode("utf-8", "replace")
    except Exception:                                              # noqa: BLE001
        return []
    out = []
    for m in POZYCJA.finditer(h):
        tytul = _html.unescape(re.sub(r"<[^>]+>", " ", m.group("tytul"))).strip()
        if not tytul:
            continue
        out.append({"tytul": tytul, "typ": m.group("typ"),
                    "link": url.rstrip("/") + m.group("link"),
                    "zrodlo": "Bandcamp (zakładka /music artysty)"})
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artysci", default="artysci_wszyscy.txt")
    ap.add_argument("--pauza", type=float, default=0.4)
    ap.add_argument("--wydawnictw", type=int, default=6)
    ap.add_argument("--min-znakow", type=int, default=3)
    ap.add_argument("--wyjscie", default="bandcamp.json")
    args = ap.parse_args()

    lista = [a.strip() for a in (OUT / args.artysci).read_text().splitlines() if a.strip()]
    lista = [a for a in lista if len(_n(a)) >= args.min_znakow]

    profile, plyty, wytwornie = [], [], 0
    for i, a in enumerate(lista, 1):
        w = szukaj(a)
        if w:
            wytwornie += w["to_wytwornia"]
            for p in wydawnictwa(w["bandcamp"], args.wydawnictw):
                plyty.append({"ksywa": a, **p})
            profile.append({"ksywa": a, **w})
            time.sleep(args.pauza)
        if i % 50 == 0:
            print(f"  {i}/{len(lista)} — profili {len(profile)}, wydawnictw {len(plyty)}",
                  flush=True)
        time.sleep(args.pauza)

    p = OUT / args.wyjscie
    p.write_text(json.dumps({"artysci": profile, "wydawnictwa": plyty},
                            ensure_ascii=False, indent=1))
    print(f"\nprofili Bandcamp: {len(profile)}/{len(lista)} "
          f"({len(profile) / len(lista) * 100:.0f}%)")
    print(f"  oznaczonych jako WYTWÓRNIA (nie artysta): {wytwornie}")
    print(f"  ⚠ gatunek spoza muzyki klubowej — do sprawdzenia: "
          f"{sum(1 for x in profile if x['do_sprawdzenia'])}")
    print(f"  z podaną lokalizacją: {sum(1 for x in profile if x['lokalizacja'])}")
    print(f"wydawnictw zebranych: {len(plyty)}")
    print(f"zapisane: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
