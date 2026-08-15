"""Kanon RA 2000-25 — miksy, wydawnictwa i utwory ćwierćwiecza.

Janek 2026-08-14: „to są według RA crème de la crème jeśli chodzi o miksy DJ…
jeśli dla RA to jest swoisty benchmark mixtapów to znaczy że tak jest.
Potraktujmy to z ogromną skrupulatnością".

RA wydało w grudniu 2025 trylogię podsumowującą ćwierćwiecze:

  4480  2000-25: The Century in Electronic Music   (metodologia)
  4481  The Best Electronic Tracks of 2000-25      (utwory)
  4482  The Best Electronic Records of 2000-25     (wydawnictwa)
  4483  The Best Electronic Mixes of 2000-25       (miksy)

Dlaczego to jest dla DanceLab co innego niż reszta bazy: wszystko, co
zebraliśmy dotąd, mówi CO SIĘ WYDARZYŁO — kto gdzie zagrał, co puścił.
Ta lista mówi, CO ZOSTAŁO UZNANE ZA WZORCOWE. To jest jedyny w tej bazie
sąd wartościujący, wystawiony przez redakcję, która robi to od 2001 roku.
Nie zastępuje pomiaru, ale daje punkt odniesienia, którego pomiar nie ma.

CZEGO NIE UDAJEMY:

  * RANKING MA TYLKO PIERWSZA DZIESIĄTKA. Pozostałe pozycje redakcja podała
    bez numerów, chronologicznie. Wpisywanie im miejsc od 11 w górę byłoby
    zmyśleniem porządku, którego autorzy nie ustalili — pole `miejsce`
    zostaje puste.
  * ARTYKUŁ 4481 (utwory) NIE MA LISTY W TREŚCI. Dwieście pozycji ładuje się
    po stronie przeglądarki z API, którego nie znalazłam. Zamiast zgadywać,
    bierzemy playlistę Apple Music linkowaną przez samo RA — ale to jest
    playlista ROZSZERZONA, 300 utworów bez numeracji, i tak jest opisana.
"""

from __future__ import annotations

import html
import json
import pathlib
import re
import urllib.request

OUT = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Content-Type": "application/json", "Referer": "https://ra.co/"}

# Dzielimy po TYTUŁACH pozycji, nie po sekcjach layoutu. Powód jest twardy:
# RA wcisnęło #2 i #1 do jednej sekcji `feature__entry-wrapper`, więc podział
# po sekcjach gubił numer jeden — czyli najważniejszą pozycję całej listy.
TYTUL_POZ = re.compile(r'feature__section-title[^"]*">')
RANK = re.compile(r'feature__rank[^"]*">#?(\d+)<')
ROK = re.compile(r'feature__year[^"]*">(\d{4})<')
NAGLOWEK = re.compile(r'feature__section-title[^"]*">(.*?)</div>', re.S)
ARTYSTA = re.compile(r'<a href="https://ra\.co/(dj|labels?|record-label)/([^"]+)"[^>]*>(.*?)</a>', re.S)
SC_ID = re.compile(r'tracks%253A(\d+)|api\.soundcloud\.com/tracks/(\d+)')
KOPIA = re.compile(r'feature__copy-section">(.*?)</div>', re.S)


def _txt(s: str) -> str:
    s = re.sub(r"<br\s*/?>", " · ", s or "")
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def feature(fid: str) -> dict:
    q = {"query": "query($id:ID!){feature(id:$id){id title blurb date content}}",
         "variables": {"id": fid}}
    req = urllib.request.Request("https://ra.co/graphql", headers=UA,
                                 data=json.dumps(q).encode())
    with urllib.request.urlopen(req, timeout=40) as r:
        return (json.loads(r.read().decode("utf-8"))["data"]["feature"]) or {}


def rozbierz(fid: str, kategoria: str) -> list[dict]:
    f = feature(fid)
    tresc = f.get("content") or ""
    granice = [m.start() for m in TYTUL_POZ.finditer(tresc)]
    bloki = []
    for j, g in enumerate(granice):
        # Blok pozycji sięga wstecz po nagłówek z rangą i rokiem, a w przód
        # do następnego tytułu — tam leży uzasadnienie i odtwarzacz.
        poczatek = max(0, tresc.rfind("feature__ranked-header", 0, g))
        poczatek = poczatek if poczatek and (g - poczatek) < 900 else max(0, g - 600)
        koniec = granice[j + 1] if j + 1 < len(granice) else len(tresc)
        bloki.append(tresc[poczatek:koniec])
    out = []
    for i, blok in enumerate(bloki, 1):
        naglowek = NAGLOWEK.search(blok)
        surowy = naglowek.group(1) if naglowek else ""
        # Układ nagłówka: <a>Artysta</a><br>Tytuł. Rozdzielamy je, bo to są
        # dwa różne pola i sklejenie ich uniemożliwiłoby dopasowanie do bazy.
        link = ARTYSTA.search(surowy)
        artysta = _txt(link.group(3)) if link else ""
        reszta = _txt(re.sub(r"<a .*?</a>", "", surowy, flags=re.S)).strip(" ·")
        rank = RANK.search(blok)
        rok = ROK.search(blok)
        sc = SC_ID.search(blok)
        kopia = KOPIA.search(blok)
        proza = _txt(kopia.group(1)) if kopia else ""
        # Podpis autora stoi na końcu prozy po półpauzie.
        podpis = ""
        m = re.search(r"[–-]\s*([A-ZŁŚŻĆ][^–\n]{3,60})\s*$", proza)
        if m:
            podpis = m.group(1).strip()
            proza = proza[:m.start()].strip()
        out.append({
            "kategoria": kategoria,
            "miejsce": rank.group(1) if rank else "",
            "kolejnosc": i,
            "artysta": artysta,
            "tytul": reszta,
            "rok": rok.group(1) if rok else "",
            "profil_ra": (f"https://ra.co/{link.group(1)}/{link.group(2)}"
                          if link else ""),
            "soundcloud_id": (sc.group(1) or sc.group(2)) if sc else "",
            "uzasadnienie": proza,
            "autor_tekstu": podpis,
            "zrodlo": f"RA feature {fid}: {f.get('title','').strip()}",
        })
    return out


def apple_playlista(url: str) -> list[dict]:
    """Utwory z playlisty Apple linkowanej przez RA.

    To jest playlista ROZSZERZONA (300 pozycji), nie ranking dwustu z artykułu.
    Nie ma numeracji i nie udajemy, że ma.
    """
    req = urllib.request.Request(url, headers={"User-Agent": UA["User-Agent"]})
    with urllib.request.urlopen(req, timeout=40) as r:
        h = r.read().decode("utf-8", "replace")
    m = re.search(r'type="application/ld\+json"[^>]*>(.*?)</script>', h, re.S)
    if not m:
        return []
    d = json.loads(m.group(1))
    out = []
    for i, t in enumerate(d.get("track") or [], 1):
        dur = t.get("duration") or ""
        mm = re.match(r"PT(?:(\d+)M)?(?:(\d+)S)?", dur)
        out.append({
            "kategoria": "utwór (playlista rozszerzona)",
            "miejsce": "", "kolejnosc": i,
            "artysta": "", "tytul": t.get("name") or "",
            "rok": "", "profil_ra": "",
            "apple_link": t.get("url") or "",
            "dlugosc_s": (int(mm.group(1) or 0) * 60 + int(mm.group(2) or 0)) if mm else "",
            "uzasadnienie": "", "autor_tekstu": "",
            "zrodlo": "Apple Music: playlista linkowana z RA feature 4481",
        })
    return out


def main() -> int:
    wynik = []
    for fid, kat in (("4483", "miks"), ("4482", "wydawnictwo")):
        poz = rozbierz(fid, kat)
        z_rankiem = sum(1 for p in poz if p["miejsce"])
        print(f"  {fid} {kat:12s} pozycji {len(poz):3d} | z miejscem w rankingu {z_rankiem:2d}"
              f" | z SoundCloud {sum(1 for p in poz if p['soundcloud_id']):3d}"
              f" | z uzasadnieniem {sum(1 for p in poz if p['uzasadnienie']):3d}")
        wynik += poz
    apple = apple_playlista(
        "https://music.apple.com/us/playlist/the-best-electronic-tracks-of-2000-25/"
        "pl.b6165e210ec540ef87678760510b10d8")
    print(f"  4481 utwory      pozycji {len(apple):3d} | z playlisty Apple (rozszerzona)")
    wynik += apple

    p = OUT / "ra_kanon.json"
    p.write_text(json.dumps(wynik, ensure_ascii=False, indent=1))
    print(f"\nrazem pozycji: {len(wynik)}")
    print(f"zapisane: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
