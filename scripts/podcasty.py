"""Sety podcastowe i radiowe — osobna, mocna kategoria w świecie DJ-skim.

Janek 2026-08-14: „osobną w sumie i mocną kategorią w środowisku DJ są
podcasty, czy to radiowe, radiowo-online, online itp. Warto dodać do każdego
DJ-a przynajmniej 3 tego typu sety".

Rozróżnienie, bez którego ta kategoria zamienia się w śmietnik:

  * PODCAST, W KTÓRYM DJ GRA — „RA.842 Fadi Mohem", „HÖR — Anetha",
    „DRONE Podcast 053 — Michal Jablonski". To jest set. Zbieramy.
  * AUDYCJA, W KTÓREJ LUDZIE GADAJĄ o muzyce — „Strefa Ruchu #14: Audioriver,
    Cały Ten Rap, Denzel Curry, EURO 2024". To nie set. NIE zbieramy
    (decyzja Janka tego samego dnia). Odsiewa je `GADANE` w normalizacji.

Dlaczego po CYKLACH, a nie po artystach: set podcastowy prawie nigdy nie wisi
na koncie artysty — wisi na koncie serii. „RA.842" jest u Resident Advisor,
HÖR u HÖR, Boiler Room u Boiler Room. Jedno konto cyklu daje setki odcinków
naraz, więc 30 zapytań zastępuje 1200. Dopiero potem dopasowujemy tytuły
odcinków do naszej listy artystów.

Drugi przebieg (`--konta`) idzie po kontach samych artystów i wyławia to, co
publikują u siebie: rezydencje w małych radiach, własne cykle, gościnne
odcinki. Tam trafia ogon, którego duże serie nie mają.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import unicodedata as U
import urllib.parse
import urllib.request

OUT = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
API = "https://api-v2.soundcloud.com"

# Cykle, które w środowisku DJ-skim znaczą coś same z siebie: wejście do nich
# jest wyróżnieniem, a nie zamówionym mixtapem. `typ` wg NAZEWNICTWO.md —
# `radio` gdy to stacja, `studio` gdy nagranie bez publiczności, `podcast`
# gdy cykl wydawnictwa albo medium.
CYKLE: list[tuple[str, str, str]] = [
    # (uchwyt konta, nazwa cyklu, typ)
    ("resident-advisor",  "RA Podcast",            "podcast"),
    ("hoerberlin",        "HÖR Berlin",            "studio"),
    ("platform",          "Boiler Room",           "studio"),
    ("dkmntl",            "Dekmantel Podcast",     "podcast"),
    ("rinsefm",           "Rinse FM",              "radio"),
    ("crackmagazine",     "Crack Mix",             "podcast"),
    ("truants",           "Truancy Volume",        "podcast"),
    ("xlr8r",             "XLR8R Podcast",         "podcast"),
    ("groove-magazin",    "Groove Podcast",        "podcast"),
    ("mixmag",            "Mixmag",                "podcast"),
    ("fabric",            "fabric Promo Mix",      "podcast"),
    ("beatsinspace",      "Beats In Space",        "radio"),
    ("slam_djs",          "Slam Radio",            "radio"),
    ("trommelmusic",      "Trommel",               "podcast"),
    ("hate-music",        "HATE Podcast",          "podcast"),
    ("thelotradio",       "The Lot Radio",         "radio"),
    ("refugeworldwide",   "Refuge Worldwide",      "radio"),
    ("kioskradio",        "Kiosk Radio",           "radio"),
    ("discwoman",         "Discwoman",             "podcast"),
    ("semanticarecords",  "Semantica Radio",       "radio"),
    ("bunkerpodcast",     "Bunker Podcast",        "podcast"),
    ("lente-kabinet",     "Lente Kabinet",         "podcast"),
    ("klasse-wrecks",     "Klasse Wrecks",         "podcast"),
    ("blowinguptheworkshop", "Blowing Up The Workshop", "podcast"),
    ("intergalacticfm",   "Intergalactic FM",      "radio"),
    ("jedentageinset",    "Jeden Tag Ein Set",     "podcast"),
    # polskie — bo line-up, od którego zaczęliśmy, jest polski
    ("radiokapital",      "Radio Kapitał",         "radio"),
    ("radiokampus",       "Radio Kampus",          "radio"),
    ("newonce",           "newonce",               "radio"),
    ("munopl",            "Muno.pl",               "podcast"),
    ("czystapodloga",     "Czysta Podłoga",        "podcast"),
    ("brutaz",            "Brutaż",                "podcast"),
]

# Ten sam filtr co w normalizacji: audycja mówiona nie jest setem.
GADANE = re.compile(r"\bw \w+ odcinku\b|\bwyst[ąa]pili\b|\bzarejestrowano\b|"
                    r"\bprowadz[ąa]cy\b|\bomawiam|\btalk\s?show\b|"
                    r"\bin conversation\b|\binterview with\b", re.I)


def _norm(s: str) -> str:
    s = U.normalize("NFKD", s or "")
    s = "".join(c for c in s if not U.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def _json(url: str) -> dict | list | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                                         # noqa: BLE001
        print(f"    {e}", file=sys.stderr)
        return None


def client_id() -> str | None:
    """Publiczny `client_id` ze skryptów SoundCloud — nie obejście logowania."""
    req = urllib.request.Request("https://soundcloud.com/discover",
                                 headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception:                                              # noqa: BLE001
        return None
    for src in re.findall(r'src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"', html):
        try:
            req = urllib.request.Request(src, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                js = r.read().decode("utf-8", "replace")
        except Exception:                                          # noqa: BLE001
            continue
        m = re.search(r'client_id\s*:\s*"([A-Za-z0-9]{20,})"', js)
        if m:
            return m.group(1)
    return None


def user_id(handle: str, cid: str) -> int | None:
    url = (f"{API}/resolve?url=https://soundcloud.com/"
           f"{urllib.parse.quote(handle)}&client_id={cid}")
    d = _json(url)
    return d.get("id") if isinstance(d, dict) and d.get("kind") == "user" else None


def uploads(uid: int, cid: str, limit: int, pauza: float = 0.3) -> list[dict]:
    """Wrzuty konta, stronicowane. Minimalny opis — reszta w normalizacji."""
    out: list[dict] = []
    url = f"{API}/users/{uid}/tracks?client_id={cid}&limit=200&linked_partitioning=1"
    while url and len(out) < limit:
        d = _json(url)
        if not isinstance(d, dict):
            break
        for t in d.get("collection") or []:
            out.append({
                "id": t.get("id"),
                "tytul": t.get("title"),
                "uploader": (t.get("user") or {}).get("username"),
                "uploader_url": (t.get("user") or {}).get("permalink"),
                "link": t.get("permalink_url"),
                "opis": (t.get("description") or "")[:600],
                "data_wrzutu": (t.get("created_at") or "")[:10],
                "dlugosc_min": round((t.get("duration") or 0) / 60000),
            })
        url = d.get("next_href")
        if url and "client_id" not in url:
            url += f"&client_id={cid}"
        time.sleep(pauza)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--konta", help="Plik z uchwytami kont artystów (drugi przebieg)")
    ap.add_argument("--tylko-konta", action="store_true",
                    help="Pomiń duże cykle — one łapią tylko znane nazwiska. "
                         "Ogon (rezydencje w małych radiach, własne cykle) "
                         "leży na kontach samych artystów.")
    ap.add_argument("--limit", type=int, default=600,
                    help="Ile wrzutów maksymalnie na konto")
    ap.add_argument("--min-minut", type=int, default=20)
    ap.add_argument("--wyjscie", default="podcasty_sety.json")
    args = ap.parse_args()

    cid = client_id()
    if not cid:
        print("Nie udało się pobrać client_id — bez niego api-v2 nie odpowiada.")
        return 1

    zrodla: list[tuple[str, str, str]] = [] if args.tylko_konta else list(CYKLE)
    if args.konta:
        for h in pathlib.Path(args.konta).read_text().splitlines():
            h = h.strip()
            if h:
                zrodla.append((h, "", "podcast"))

    wynik, gadane, krotkie = [], 0, 0
    for i, (handle, cykl, typ) in enumerate(zrodla, 1):
        uid = user_id(handle, cid)
        if uid is None:
            print(f"  {i}/{len(zrodla)} {handle[:28]:28s} — konta nie ma", flush=True)
            continue
        sety = uploads(uid, cid, args.limit)
        zostaje = []
        for s in sety:
            if (s.get("dlugosc_min") or 0) < args.min_minut:
                krotkie += 1
                continue
            if GADANE.search(s.get("opis") or ""):
                gadane += 1
                continue
            zostaje.append(s)
        wynik.append({"playlista": cykl or handle,
                      "url": f"https://soundcloud.com/{handle}",
                      "typ": typ, "sety": zostaje})
        print(f"  {i}/{len(zrodla)} {(cykl or handle)[:28]:28s} {len(zostaje):4d} odcinków", flush=True)
        time.sleep(0.4)

    p = OUT / args.wyjscie
    p.write_text(json.dumps(wynik, ensure_ascii=False, indent=1))
    print(f"\nodcinków razem: {sum(len(w['sety']) for w in wynik)}")
    print(f"odrzucone: za krótkie {krotkie}, audycje mówione {gadane}")
    print(f"zapisane: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
