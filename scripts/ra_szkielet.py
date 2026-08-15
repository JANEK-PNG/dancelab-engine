"""Resident Advisor jako GLOBALNY SZKIELET mapy DJ-ów.

Janek 2026-08-14, po zmierzeniu, gdzie na świecie sety są najlepiej
udokumentowane: „wpinaj RA jako globalny szkielet".

RA ma żywe API GraphQL pod `ra.co/graphql`, bez klucza. Odpowiada na trzy
pytania naraz, a każde z nich osobno kosztowało nas dotąd godziny:

  * KTO — `search(indices:[ARTIST])` daje kanoniczny identyfikator artysty.
    To jest klucz, którego nie mieliśmy: dotąd łączyliśmy wszystko po ksywie,
    a ksywa jest zawodna („Robert", „Mikal", „justi").
  * KIEDY I W JAKICH WARUNKACH — `artist(id).events` zwraca historię grania
    z datą, miejscem, miastem i krajem. Osobno dla przeszłych i przyszłych.
  * CZYM JEST — `labels`, `country`, `residentCountry`, `followerCount`
    oraz **uchwyt SoundCloud**, podany przez samego artystę.

Trzy kolumny, które to naprawia:

  * AFILIACJA. Janek kazał ją usunąć 2026-08-14, bo przy 1466 artystach
    wypełnionych było 24 wiersze — jedyne pole bez źródła hurtowego.
    RA podaje dla Bena Klocka dziesięć wytwórni w jednym zapytaniu.
    Kolumna wraca, bo wraca jej źródło.
  * SOUNDCLOUD. Zbieraliśmy uchwyty ubocznie z wrzutów i przez zgadywanie po
    nazwie; RA ma je wpisane przez artystę.
  * KRAJ. Bandcamp dał lokalizację dla 496 osób. RA dokłada `country`
    i `residentCountry` — a to nie to samo: skąd pochodzi i gdzie mieszka.

Dopasowanie po DOKŁADNEJ nazwie, jak wszędzie. „Ben Klock" ma na RA jeden
profil o tej nazwie i to jest pewne; przy zgodzie częściowej wolimy puste.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import unicodedata as U
import urllib.request

OUT = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")
API = "https://ra.co/graphql"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Content-Type": "application/json", "Referer": "https://ra.co/"}

SZUKAJ = """query($t:String!){search(searchTerm:$t,limit:8,indices:[ARTIST])
 {id value contentUrl}}"""

# Enum `EventQueryType` NIE ma wartości UPCOMING — introspekcja daje:
# PICKS, TODAY, FROMDATE, LATEST, PREVIOUS, ARCHIVE, POPULAR, FIRST, ONDATE,
# BYIDS. Zgadywanie po angielsku kosztowało 502 na całym pierwszym przebiegu.
# `PREVIOUS` to historia grania, `LATEST` to zapowiedziane.
PROFIL = """query($id:ID!){artist(id:$id){id name followerCount
 country{name} residentCountry{name} labels{name}
 soundcloud facebook website
 przeszle:events(limit:%d,type:PREVIOUS){id title date contentUrl
   venue{name area{name country{name}}}}
 przyszle:events(limit:%d,type:LATEST){id title date contentUrl
   venue{name area{name country{name}}}}}}"""


def _n(s: str) -> str:
    s = U.normalize("NFKD", s or "")
    s = "".join(c for c in s if not U.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def ra(zapytanie: str, zmienne: dict | None = None):
    dane = json.dumps({"query": zapytanie, "variables": zmienne or {}}).encode()
    try:
        req = urllib.request.Request(API, headers=UA, data=dane)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                                         # noqa: BLE001
        print(f"    {e}", file=sys.stderr)
        return None


def znajdz(ksywa: str) -> str | None:
    """Identyfikator RA albo nic. Zgoda nazwy musi być dokładna."""
    d = ra(SZUKAJ, {"t": ksywa})
    if not d:
        return None
    cel = _n(ksywa)
    for w in (d.get("data") or {}).get("search") or []:
        if _n(w.get("value", "")) == cel:
            return w.get("id")
    return None


def profil(rid: str, ile_gigow: int) -> dict | None:
    d = ra(PROFIL % (ile_gigow, ile_gigow), {"id": rid})
    a = ((d or {}).get("data") or {}).get("artist")
    return a or None


def _gig(e: dict, kiedy: str) -> dict:
    v = e.get("venue") or {}
    ar = v.get("area") or {}
    return {
        "kiedy": kiedy,
        "data": (e.get("date") or "")[:10],
        "tytul": e.get("title") or "",
        "miejsce": v.get("name") or "",
        "miasto": ar.get("name") or "",
        "kraj": (ar.get("country") or {}).get("name") or "",
        "link": "https://ra.co" + (e.get("contentUrl") or ""),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artysci", default="artysci_wszyscy.txt")
    ap.add_argument("--gigow", type=int, default=40,
                    help="Ile występów pobrać w każdą stronę czasu")
    ap.add_argument("--pauza", type=float, default=0.5)
    ap.add_argument("--od", type=int, default=0)
    ap.add_argument("--wyjscie", default="ra.json")
    args = ap.parse_args()

    lista = [a.strip() for a in (OUT / args.artysci).read_text().splitlines() if a.strip()]
    lista = lista[args.od:]

    # Wznawianie, bo baza rosła pod każdym dotychczasowym przebiegiem.
    profile: list[dict] = []
    gigi: list[dict] = []
    zrobione: set[str] = set()
    p = OUT / args.wyjscie
    if p.exists():
        stare = json.loads(p.read_text())
        profile, gigi = stare["artysci"], stare["wystepy"]
        zrobione = {_n(x["ksywa"]) for x in profile}
        print(f"wznawiam — mam już {len(zrobione)} profili")

    trafione = 0
    for i, a in enumerate(lista, 1):
        if _n(a) in zrobione:
            continue
        rid = znajdz(a)
        if rid:
            pr = profil(rid, args.gigow)
            if pr:
                trafione += 1
                profile.append({
                    "ksywa": a, "ra_id": pr.get("id"), "nazwa_ra": pr.get("name"),
                    "obserwujacych": pr.get("followerCount") or 0,
                    "kraj": (pr.get("country") or {}).get("name") or "",
                    "kraj_zamieszkania": (pr.get("residentCountry") or {}).get("name") or "",
                    "wytwornie": ", ".join(l["name"] for l in (pr.get("labels") or [])),
                    "soundcloud_ra": pr.get("soundcloud") or "",
                    "www": pr.get("website") or "",
                    "wystepow_przeszlych": len(pr.get("przeszle") or []),
                    "wystepow_przyszlych": len(pr.get("przyszle") or []),
                })
                for e in pr.get("przeszle") or []:
                    gigi.append({"ksywa": a, **_gig(e, "zagrane")})
                for e in pr.get("przyszle") or []:
                    gigi.append({"ksywa": a, **_gig(e, "zapowiedziane")})
            time.sleep(args.pauza)
        if i % 25 == 0:
            print(f"  {i}/{len(lista)} — profili {len(profile)}, występów {len(gigi)}",
                  flush=True)
            p.write_text(json.dumps({"artysci": profile, "wystepy": gigi},
                                    ensure_ascii=False, indent=1))
        time.sleep(args.pauza)

    p.write_text(json.dumps({"artysci": profile, "wystepy": gigi},
                            ensure_ascii=False, indent=1))
    print(f"\nprofili RA: {len(profile)}  (w tym przebiegu nowych: {trafione})")
    print(f"  z wytwórniami:   {sum(1 for x in profile if x['wytwornie'])}")
    print(f"  z SoundCloudem:  {sum(1 for x in profile if x['soundcloud_ra'])}")
    print(f"  z krajem:        {sum(1 for x in profile if x['kraj'])}")
    print(f"występów zebranych: {len(gigi)}")
    print(f"zapisane: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
