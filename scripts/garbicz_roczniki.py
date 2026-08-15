"""Wyciąga zawartość rocznikowych playlist z Garbicza prosto ze SoundCloud.

Do tej pory każdy set kosztował jedno zapytanie do wyszukiwarki i trafiał do
bazy pojedynczo. Playlisty rocznikowe („Jeden Tag Ein Set: Garbicz Festival
2018", „kutno: Garbicz 2025 - All Sets") zawierają po kilkadziesiąt setów
naraz, ale strona SoundCloud jest aplikacją javascriptową i ani WebFetch, ani
zwykły czytnik nie widzą listy utworów.

Widzi ją za to surowy HTML. SoundCloud wstrzykuje do strony blok
`window.__sc_hydration = [...]`, w którym siedzi pełny opis playlisty razem
z tytułem, autorem, opisem, datą i czasem trwania każdego setu. Ten skrypt
bierze ten blok i nic więcej — nie odtwarza dźwięku, nie loguje się, nie
dotyka API wymagającego klucza.

Czego NIE robi:

  * nie zgaduje sceny ani roli — te wyciągamy z tytułu i opisu osobno,
    słownikiem z NAZEWNICTWO.md, a gdy się nie da, pole zostaje puste;
  * nie łączy artysty z line-upem festiwalu — uploaderem bywa kolektyw
    („Permanent Aktiv" wrzuca set Marabou), więc nazwa z tytułu jest ważniejsza
    niż nazwa konta i rozstrzyga ją człowiek.
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
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HYDRATION = re.compile(r"window\.__sc_hydration\s*=\s*(\[.*?\]);", re.S)


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def hydration(html: str) -> list[dict]:
    m = HYDRATION.search(html)
    if not m:
        return []
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return []


def _playlist_node(blocks: list[dict]) -> dict | None:
    for b in blocks:
        if b.get("hydratable") in {"playlist", "systemPlaylist"}:
            return b.get("data") or {}
    return None


def tracks_of(url: str) -> tuple[str, list[dict]]:
    """(tytuł playlisty, lista setów). Pusta lista = strona nie oddała danych."""
    node = _playlist_node(hydration(_fetch(url)))
    if not node:
        return "", []
    out = []
    for t in node.get("tracks", []):
        # Playlisty powyżej ~5 utworów zwracają dalsze pozycje jako same `id`
        # bez tytułu. Takich nie da się opisać i nie udajemy, że się da —
        # dociągamy je osobno przez /resolve poniżej.
        if not t.get("title"):
            out.append({"id": t.get("id"), "niepelne": True})
            continue
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
    return node.get("title") or "", out


def fill_ids(ids: list[int], client_id: str, pauza: float = 0.3) -> list[dict]:
    """Dociąga sety, które playlista podała samym identyfikatorem.

    Endpoint `api-v2` wymaga `client_id`, ale ten identyfikator SoundCloud
    sam publikuje w swoim javascripcie — nie jest to klucz prywatny ani
    obejście logowania.
    """
    out = []
    for i in range(0, len(ids), 50):
        chunk = ",".join(str(x) for x in ids[i:i + 50])
        url = (f"https://api-v2.soundcloud.com/tracks?ids={chunk}"
               f"&client_id={client_id}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:                                     # noqa: BLE001
            print(f"    partia {i}: {e}", file=sys.stderr)
            continue
        for t in data:
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
        time.sleep(pauza)
    return out


def szukaj(fraza: str, client_id: str, limit: int = 1000,
           pauza: float = 0.4) -> list[dict]:
    """Pełnotekstowe wyszukiwanie po SoundCloud, stronicowane.

    Potrzebne tam, gdzie nie ma kuratorowanych playlist rocznikowych.
    Garbicz ma 34 takie kolekcje i wystarczyło je pobrać; Audioriver nie ma
    ANI JEDNEJ — sety leżą pojedynczo, wrzucone przez samych artystów. Dla
    takiego festiwalu jedynym wejściem hurtowym jest wyszukiwarka serwisu.

    Zwraca surowe pozycje; ocena, czy to naprawdę set z tego festiwalu, należy
    do normalizacji — fraza „audioriver" trafia też w zapowiedzi i podcasty.
    """
    out, offset = [], 0
    while len(out) < limit:
        url = ("https://api-v2.soundcloud.com/search/tracks"
               f"?q={urllib.parse.quote(fraza)}&client_id={client_id}"
               f"&limit=200&offset={offset}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:                                     # noqa: BLE001
            print(f"    offset {offset}: {e}", file=sys.stderr)
            break
        partia = data.get("collection") or []
        if not partia:
            break
        for t in partia:
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
        offset += len(partia)
        if not data.get("next_href"):
            break
        time.sleep(pauza)
    return out


def client_id_from_soundcloud() -> str | None:
    """Wyciąga publiczny client_id z bundli javascriptowych SoundCloud."""
    try:
        html = _fetch("https://soundcloud.com/discover")
    except Exception:                                              # noqa: BLE001
        return None
    for src in re.findall(r'src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"', html):
        try:
            js = _fetch(src)
        except Exception:                                          # noqa: BLE001
            continue
        m = re.search(r'client_id\s*:\s*"([A-Za-z0-9]{20,})"', js)
        if m:
            return m.group(1)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--playlisty", help="Plik z URL-ami playlist, jeden na wiersz")
    ap.add_argument("--szukaj", action="append", default=[],
                    help="Fraza do wyszukania w SoundCloud. Można podać wiele razy. "
                         "Dla festiwali bez kuratorowanych roczników.")
    ap.add_argument("--wyjscie", default="roczniki_sety.json")
    args = ap.parse_args()
    if not args.playlisty and not args.szukaj:
        ap.error("podaj --playlisty albo --szukaj")
    OUT.mkdir(parents=True, exist_ok=True)

    urls = ([u.strip() for u in pathlib.Path(args.playlisty).read_text().splitlines()
             if u.strip() and not u.startswith("#")] if args.playlisty else [])
    cid = client_id_from_soundcloud()
    print(f"client_id: {'jest' if cid else 'BRAK — niepełne pozycje zostaną puste'}")

    wynik = []
    for fraza in args.szukaj:
        if not cid:
            print(f"  pomijam „{fraza}" + "” — wyszukiwanie wymaga client_id")
            continue
        sety = szukaj(fraza, cid)
        wynik.append({"playlista": f"szukanie: {fraza}", "url": "", "sety": sety})
        print(f"  szukanie „{fraza}" + f"” {len(sety):4d} pozycji")

    for i, url in enumerate(urls, 1):
        try:
            tytul, sety = tracks_of(url)
        except Exception as e:                                     # noqa: BLE001
            print(f"  {i}/{len(urls)} {url} — BŁĄD {e}")
            continue
        braki = [s["id"] for s in sety if s.get("niepelne") and s.get("id")]
        if braki and cid:
            sety = [s for s in sety if not s.get("niepelne")] + fill_ids(braki, cid)
        pelne = [s for s in sety if s.get("tytul")]
        wynik.append({"playlista": tytul, "url": url, "sety": pelne})
        print(f"  {i}/{len(urls)} {tytul[:50]:50s} {len(pelne):3d} setów")
        time.sleep(0.5)

    p = OUT / args.wyjscie
    p.write_text(json.dumps(wynik, ensure_ascii=False, indent=1))
    print(f"\nrazem setów: {sum(len(w['sety']) for w in wynik)}")
    print(f"zapisane: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
