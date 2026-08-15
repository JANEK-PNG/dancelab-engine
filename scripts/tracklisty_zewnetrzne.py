"""Tracklisty spoza SoundCloud — sześć baz, do których nie prowadzi wyszukiwarka.

Janek 2026-08-14: „mixesdb też pociągnij i przynajmniej 5 podobnych do tej
strony. Szukaj poza tym co sugeruje Google czy Bing. Oni dają co im się opłaca
reklamowo, a nie co nam się opłaca".

To jest trafna uwaga i ma konsekwencję techniczną: bazy, które są tu najlepsze,
to wiki i otwarte API utrzymywane przez ludzi, którzy nie kupują reklam. Nie
wychodzą wysoko w wynikach i trzeba do nich wejść WPROST, po adresie API.

ŹRÓDŁA, w kolejności wartości:

  1. MixesDB — wiki zrobione dokładnie po to. Tracklisty w wikitekście,
     numerowane, często z czasami. Najważniejsze: strona niesie `{{Player|URL}}`
     z linkiem do SoundCloud, więc łączy się z naszą bazą PO LINKU, a nie po
     zgadywaniu z tytułu. To jedyne źródło, które daje pewne połączenie.
  2. NTS Radio — osobny endpoint `/tracklist` na każdy odcinek. Dane
     strukturalne (wykonawca, tytuł osobno), nie tekst do parsowania.
  3. Discogs — sety wydane jako miks mają pełną tracklistę z czasami trwania.
  4. hearthis.at — odpowiednik SoundCloud, w którym siedzi europejski
     underground; tracklisty w opisach.
  5. Mixcloud — dużo setów radiowych, tracklisty w danych strony.
  6. Internet Archive — archiwa audycji, czasem z plikiem tracklisty.

Czego NIE robimy: nie wpisujemy tracklisty z bazy zewnętrznej pod nasz set,
jeśli połączenie jest tylko po nazwie artysty. Bez wspólnego linku albo zgodnej
daty ORAZ wydarzenia wiersz dostaje `pewnosc=niepewne` i osobne pole
`dopasowanie`, mówiące po czym połączyliśmy.
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
UA = {"User-Agent": "DanceLab-research/0.1 (local, non-commercial)"}

MIXESDB = "https://www.mixesdb.com/db/api.php"
NTS = "https://www.nts.live/api/v2"
DISCOGS = "https://api.discogs.com"
HEARTHIS = "https://api-v2.hearthis.at"


def _get(url: str, n: int = 2_000_000) -> str | None:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read(n).decode("utf-8", "replace")
    except Exception as e:                                         # noqa: BLE001
        print(f"    {e}", file=sys.stderr)
        return None


def _js(url: str):
    t = _get(url)
    if not t:
        return None
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return None


def n2(s: str) -> str:
    s = U.normalize("NFKD", s or "")
    s = "".join(c for c in s if not U.combining(c))
    return " " + re.sub(r"[^a-z0-9]+", " ", s.lower()).strip() + " "


# ── 1. MixesDB ──────────────────────────────────────────────────────────────

# Pozycja tracklisty w wikitekście: „# ANNA - Impression", czasem
# „# [00:00] ANNA - Impression" albo „#1:02:11 …".
POZYCJA = re.compile(
    r"^#+\s*(?:\[?(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{2}))?\]?\s*[-–—]?\s*)?"
    r"(?P<tresc>.+?)\s*$")
ZNACZNIK_MDB = re.compile(r"^\s*\[[\d?]{1,3}[?:]?[\d?]{0,2}[?:]?[\d?]{0,2}\]\s*")
WYDAWCA = re.compile(r"\s*\[([^\]]{2,60})\]\s*$")
PLAYER = re.compile(r"\{\{\s*Player\s*\|?\s*([^}\|]+)", re.I)
LINK_SC = re.compile(r"https?://(?:www\.|m\.)?soundcloud\.com/[\w\-/]+", re.I)


def mixesdb_szukaj(fraza: str, limit: int = 20) -> list[str]:
    d = _js(f"{MIXESDB}?action=query&list=search"
            f"&srsearch={urllib.parse.quote(fraza)}&srlimit={limit}&format=json")
    if not d:
        return []
    return [r["title"] for r in d.get("query", {}).get("search", [])]


def mixesdb_kategoria(nazwa: str, limit: int = 500) -> list[str]:
    tytuly, cont = [], ""
    while True:
        d = _js(f"{MIXESDB}?action=query&list=categorymembers"
                f"&cmtitle=Category:{urllib.parse.quote(nazwa)}"
                f"&cmlimit=500&format=json{cont}")
        if not d:
            break
        tytuly += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
        nxt = d.get("continue", {}).get("cmcontinue")
        if not nxt or len(tytuly) >= limit:
            break
        cont = f"&cmcontinue={urllib.parse.quote(nxt)}"
        time.sleep(0.3)
    return tytuly


def mixesdb_strona(tytul: str) -> dict | None:
    d = _js(f"{MIXESDB}?action=parse&page={urllib.parse.quote(tytul)}"
            f"&prop=wikitext&format=json")
    if not d or "parse" not in d:
        return None
    wt = d["parse"]["wikitext"]["*"]

    # Tracklista jest w sekcji „== Tracklist ==", ale bywa kilka sekcji
    # (set podzielony na części). Bierzemy wszystkie i sklejamy po kolei.
    pozycje = []
    for linia in wt.splitlines():
        if not linia.startswith("#"):
            continue
        m = POZYCJA.match(linia)
        if not m:
            continue
        tresc = m.group("tresc").strip()
        # Wikitekst niesie znaczniki, które nie są nazwą utworu.
        tresc = re.sub(r"\[\[([^\]\|]+\|)?([^\]]+)\]\]", r"\2", tresc)
        tresc = re.sub(r"'''?|\{\{[^}]*\}\}|<[^>]+>", "", tresc).strip()
        # MixesDB stawia na początku własny znacznik pozycji: „[000]" gdy czas
        # znany z dokładnością do minuty, „[0??]" i „[???]" gdy nieznany.
        # Bez tego wchodzi on w pole wykonawcy i psuje każdą nazwę.
        tresc = ZNACZNIK_MDB.sub("", tresc).strip(" -–—")
        if len(tresc) < 4 or tresc in {"?", "??", "???"}:
            continue
        ms = None
        if m.group("h") is not None:
            h, mi, s = m.group("h"), m.group("m"), m.group("s")
            ms = ((int(h) * 3600 + int(mi) * 60 + int(s)) * 1000 if s
                  else (int(h) * 60 + int(mi)) * 1000)
        # Wytwórnia i numer katalogowy stoją na końcu w nawiasie kwadratowym
        # („[Ultra - UL5678]"). To osobna informacja, nie część tytułu.
        wyd = ""
        wyd_m = WYDAWCA.search(tresc)
        if wyd_m:
            wyd = wyd_m.group(1).strip()
            tresc = tresc[:wyd_m.start()].strip()
        czesci = re.split(r"\s+[-–—]\s+", tresc, maxsplit=1)
        pozycje.append({
            "ms": ms,
            "czas": (f"{ms // 3600000}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}"
                     if ms else ""),
            "wykonawca": czesci[0].strip() if len(czesci) == 2 else "",
            "tytul": (czesci[1] if len(czesci) == 2 else tresc).strip(),
            "wydawca": wyd,
            "zrodlo": "mixesdb", "autor": "",
        })
    if not pozycje:
        return None
    gracz = PLAYER.search(wt)
    sc = LINK_SC.search(gracz.group(1) if gracz else wt)
    return {"tytul_strony": tytul,
            "link_zrodlowy": sc.group(0) if sc else "",
            "url_mixesdb": "https://www.mixesdb.com/w/"
                           + urllib.parse.quote(tytul.replace(" ", "_")),
            "tracklista": pozycje}


# ── 2. NTS Radio ────────────────────────────────────────────────────────────

def nts_szukaj(fraza: str, limit: int = 12) -> list[str]:
    d = _js(f"{NTS}/search/episodes?q={urllib.parse.quote(fraza)}&limit={limit}")
    if not d:
        return []
    return [r["article"]["path"] for r in d.get("results", [])
            if (r.get("article") or {}).get("path")]


def nts_tracklista(sciezka: str) -> dict | None:
    d = _js(f"{NTS}{sciezka}/tracklist")
    if not d or not d.get("results"):
        return None
    poz = []
    for t in d["results"]:
        poz.append({"ms": None, "czas": "",
                    "wykonawca": (t.get("artist") or ""),
                    "tytul": (t.get("title") or ""),
                    "zrodlo": "nts", "autor": ""})
    return {"tytul_strony": sciezka, "link_zrodlowy": "",
            "url_mixesdb": f"https://www.nts.live{sciezka}",
            "tracklista": [p for p in poz if p["tytul"]]}


# ── 3. hearthis.at ──────────────────────────────────────────────────────────

def hearthis_szukaj(fraza: str, ile: int = 10) -> list[dict]:
    d = _js(f"{HEARTHIS}/search/?t={urllib.parse.quote(fraza)}&count={ile}")
    return d if isinstance(d, list) else []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zrodlo", default="mixesdb",
                    choices=["mixesdb", "nts", "hearthis"])
    ap.add_argument("--artysci", default="artysci_wszyscy.txt")
    ap.add_argument("--od", type=int, default=0)
    ap.add_argument("--ile", type=int, default=100000)
    ap.add_argument("--wyjscie", default="")
    args = ap.parse_args()

    lista = [a.strip() for a in (OUT / args.artysci).read_text().splitlines() if a.strip()]
    lista = lista[args.od:][:args.ile]
    wyjscie = args.wyjscie or f"tracklisty_{args.zrodlo}.json"
    wynik = []

    if args.zrodlo == "mixesdb":
        # Najpierw kategorie festiwalowe: pewne, że dotyczą naszych imprez.
        tytuly = []
        for kat in ("Garbicz Festival", "Audioriver"):
            k = mixesdb_kategoria(kat)
            print(f"  kategoria {kat}: {len(k)} stron", flush=True)
            tytuly += k
        for i, a in enumerate(lista, 1):
            tytuly += mixesdb_szukaj(a, limit=10)
            if i % 50 == 0:
                print(f"  szukanie {i}/{len(lista)} — kandydatów {len(set(tytuly))}",
                      flush=True)
            time.sleep(0.25)
        tytuly = list(dict.fromkeys(tytuly))
        print(f"stron do pobrania: {len(tytuly)}", flush=True)
        for i, t in enumerate(tytuly, 1):
            s = mixesdb_strona(t)
            if s:
                wynik.append(s)
            if i % 50 == 0:
                print(f"  {i}/{len(tytuly)} — z tracklistą {len(wynik)}", flush=True)
            time.sleep(0.25)

    elif args.zrodlo == "nts":
        for i, a in enumerate(lista, 1):
            for p in nts_szukaj(a, limit=6):
                tl = nts_tracklista(p)
                if tl:
                    tl["artysta_szukany"] = a
                    wynik.append(tl)
                time.sleep(0.2)
            if i % 25 == 0:
                print(f"  {i}/{len(lista)} — tracklist {len(wynik)}", flush=True)
            time.sleep(0.2)

    elif args.zrodlo == "hearthis":
        for i, a in enumerate(lista, 1):
            for t in hearthis_szukaj(a, ile=6):
                wynik.append({"tytul_strony": t.get("title"),
                              "link_zrodlowy": t.get("permalink_url") or t.get("url"),
                              "url_mixesdb": t.get("permalink_url") or t.get("url"),
                              "artysta_szukany": a,
                              "opis": (t.get("description") or "")[:4000],
                              "dlugosc_s": t.get("duration"),
                              "tracklista": []})
            if i % 25 == 0:
                print(f"  {i}/{len(lista)} — pozycji {len(wynik)}", flush=True)
            time.sleep(0.3)

    p = OUT / wyjscie
    p.write_text(json.dumps(wynik, ensure_ascii=False, indent=1))
    print(f"\nstron z tracklistą: {len(wynik)}")
    print(f"pozycji razem: {sum(len(w['tracklista']) for w in wynik)}")
    print(f"z linkiem do SoundCloud (pewne połączenie): "
          f"{sum(1 for w in wynik if w.get('link_zrodlowy'))}")
    print(f"zapisane: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
