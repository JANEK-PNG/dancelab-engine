"""Podcasty RA — tracklista OFICJALNA plus link do SoundCloud w jednym miejscu.

Janek 2026-08-14, po wejściu na `ra.co/podcast/1070`: „każdy podkast ma link
do soundclouda i pod każdym artykułem tracklistę!".

To jest najlepsze źródło tracklist w całej tej sesji i z konkretnego powodu.
Wszystko, co zbieraliśmy dotąd, miało jedną z dwóch wad:

  * MixesDB — 110 tysięcy pozycji, ale tracklisty pisane przez ludzi po fakcie
    i tylko 913 stron z linkiem, po którym da się je przypiąć do naszego setu;
  * komentarze SoundCloud — czasy co do sekundy, ale nazwy zgadywane przez
    publiczność, w większości „ID".

Podcast RA ma jedno i drugie naraz:

  * `tracklist` — spisana przez REDAKCJĘ, nie przez tłum;
  * `streamingUrl` — adres SoundCloud tego samego nagrania, czyli połączenie
    z naszą bazą jest FAKTEM, a nie wnioskiem z tytułu;
  * `artist{id,name}` — kanoniczny identyfikator RA, ten sam, który zbiera
    `ra_szkielet.py`.

Czego tracklisty RA NIE mają: znaczników czasu. Kolejność owszem, godziny nie.
Czasy dokłada nasz własny przebieg po komentarzach SoundCloud — i dopiero
złożenie obu daje pełny obraz szwu: RA mówi CO, komentarze mówią KIEDY.

Identyfikator w adresie nie jest numerem odcinka: `podcast/1070` to „RA.1051".
Dlatego lecimy po identyfikatorach, a numer odcinka czytamy z tytułu.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.request

OUT = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")
API = "https://ra.co/graphql"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Content-Type": "application/json", "Referer": "https://ra.co/podcast"}

ZAPYTANIE = """query($id:ID!){podcast(id:$id){id title date duration
 streamingUrl contentUrl artist{id name} tracklist blurb}}"""

NUMER = re.compile(r"\bRA\.?\s*(\d{1,4})", re.I)


def ra(zmienne: dict):
    dane = json.dumps({"query": ZAPYTANIE, "variables": zmienne}).encode()
    try:
        req = urllib.request.Request(API, headers=UA, data=dane)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                                         # noqa: BLE001
        print(f"    {e}", file=sys.stderr)
        return None


def rozbierz_tracklise(html: str) -> list[dict]:
    """HTML → pozycje. Bez czasów, bo RA ich nie podaje — i nie udajemy."""
    if not html:
        return []
    tekst = re.sub(r"<br\s*/?>|</p>|</li>|</div>", "\n", html, flags=re.I)
    tekst = re.sub(r"<[^>]+>", "", tekst)
    tekst = (tekst.replace("&amp;", "&").replace("&#39;", "'")
             .replace("&quot;", '"').replace("&nbsp;", " "))
    out = []
    for l in tekst.split("\n"):
        l = l.strip().strip("*")
        # Numeracja z przodu bywa i nie jest częścią nazwy.
        l = re.sub(r"^\s*\d{1,3}[.)]\s*", "", l)
        if len(l) < 4 or len(l) > 200:
            continue
        czesci = re.split(r"\s+[-–—]\s+", l, maxsplit=1)
        out.append({
            "ms": None, "czas": "",
            "wykonawca": czesci[0].strip() if len(czesci) == 2 else "",
            "tytul": (czesci[1] if len(czesci) == 2 else l).strip(),
            "zrodlo": "ra podcast", "autor": "",
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--od", type=int, default=1)
    ap.add_argument("--do", type=int, default=1075)
    ap.add_argument("--pauza", type=float, default=0.45)
    ap.add_argument("--wyjscie", default="ra_podcasty.json")
    args = ap.parse_args()

    p = OUT / args.wyjscie
    wynik: list[dict] = []
    zrobione: set[str] = set()
    if p.exists():
        wynik = json.loads(p.read_text())
        zrobione = {str(w["id"]) for w in wynik}
        print(f"wznawiam — mam już {len(zrobione)} odcinków")

    puste = 0
    for i in range(args.od, args.do + 1):
        if str(i) in zrobione:
            continue
        d = ra({"id": str(i)})
        pod = ((d or {}).get("data") or {}).get("podcast")
        if not pod:
            puste += 1
            time.sleep(args.pauza)
            continue
        poz = rozbierz_tracklise(pod.get("tracklist") or "")
        num = NUMER.search(pod.get("title") or "")
        wynik.append({
            "id": pod.get("id"),
            "numer": num.group(1) if num else "",
            "tytul": pod.get("title") or "",
            "data": (pod.get("date") or "")[:10],
            "dlugosc": pod.get("duration") or "",
            "ksywa": (pod.get("artist") or {}).get("name") or "",
            "ra_id_artysty": (pod.get("artist") or {}).get("id") or "",
            # To jest najważniejsze pole: ten sam adres, co w `miksy.json`,
            # czyli połączenie tracklisty z setem jest faktem.
            "link": pod.get("streamingUrl") or "",
            "strona": "https://ra.co" + (pod.get("contentUrl") or ""),
            "pozycji": len(poz),
            "tracklista": poz,
        })
        if len(wynik) % 25 == 0:
            print(f"  {i}/{args.do} — odcinków {len(wynik)}", flush=True)
            p.write_text(json.dumps(wynik, ensure_ascii=False, indent=1))
        time.sleep(args.pauza)

    p.write_text(json.dumps(wynik, ensure_ascii=False, indent=1))
    zsc = sum(1 for w in wynik if "soundcloud.com" in (w["link"] or ""))
    print(f"\nodcinków: {len(wynik)}   (identyfikatorów bez odcinka: {puste})")
    print(f"  z tracklistą:            {sum(1 for w in wynik if w['pozycji'])}")
    print(f"  pozycji razem:           {sum(w['pozycji'] for w in wynik)}")
    print(f"  z linkiem SoundCloud:    {zsc}   <- pewne połączenie z bazą")
    print(f"  z przypisanym artystą:   {sum(1 for w in wynik if w['ksywa'])}")
    print(f"zapisane: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
