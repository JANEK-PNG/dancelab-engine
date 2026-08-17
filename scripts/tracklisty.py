"""Tracklisty ze znacznikami czasu — czyli gdzie w secie kończy się szew.

Janek 2026-08-14: „mapował track id do każdego setu oraz rozpisze time stampy
w każdym secie na dany track id… 1001Tracklists, komentarze na YT, SoundCloud,
Reddit, szukaj wszędzie".

To jest, z punktu widzenia DanceLab, najcenniejsze wejście w całej mapie DJ-ów.
Sam set to dwie godziny dźwięku. Set Z TRACKLISTĄ I CZASAMI to lista miejsc,
w których jeden utwór ustępuje drugiemu — a projektujemy szew MIĘDZY trackami,
nie tracki.

KOLEJNOŚĆ ŹRÓDEŁ jest tu decyzją, nie przypadkiem:

  1. KOMENTARZE SOUNDCLOUD. Najlepsze i najczęściej pomijane. Komentarz na
     SoundCloud jest PRZYPIĘTY DO SEKUNDY nagrania — serwis podaje `timestamp`
     w milisekundach jako osobne pole. To nie jest tekst, z którego trzeba
     wyłuskiwać godziny; to gotowa oś czasu. „ID?" o 47:12 znaczy, że o 47:12
     wchodzi utwór, którego nikt nie rozpoznał — a więc TAM JEST SZEW, nawet
     gdy nazwy nie znamy.
  2. OPIS WRZUTU. DJ-e często wklejają całą tracklistę pod setem, z czasami
     albo bez. Mamy ją już pobraną — trzeba tylko przestać ją ucinać.
  3. 1001Tracklists, YouTube, Reddit — osobnymi przebiegami, bo każde wymaga
     innego obejścia i innej oceny wiarygodności.

Czego NIE robimy: nie zgadujemy nazw utworów. „ID" zostaje „ID" — brak nazwy
przy znanym czasie jest pełnowartościową informacją o szwie i zapisujemy go
wprost, zamiast wstawiać najbliższy pasujący tytuł.
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
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
API = "https://api-v2.soundcloud.com"

# Komentarz, który JEST identyfikacją utworu. Ludzie piszą to na kilka sposobów,
# ale wszystkie mają wspólny kształt: „wykonawca – tytuł" albo samo „ID".
WYKONAWCA_TYTUL = re.compile(
    r"^\s*(?:\d{1,2}[.)]\s*)?"                       # opcjonalna numeracja
    r"(?P<a>[^\n]{2,60}?)\s*(?:-|–|—|~|\|)\s*"
    r"(?P<t>[^\n]{2,80}?)\s*$")
SAMO_ID = re.compile(r"^\s*(?:track\s*)?id\s*\??\s*$|^\s*\?+\s*$", re.I)

# Zdanie, nie pozycja tracklisty. Podziękowania i wzmianki o kontach mają
# ten sam myślnik co „Wykonawca - Tytuł", więc rozstrzyga słownictwo.
PROZA = re.compile(r"\bthank(?:s| you)\b|\bdzi[eę]k|\bshout\s?out\b|"
                   r"\brecorded\b|\bfollow\b|\bdownload\b|\bsupport\b|"
                   r"@[\w-]{3,}|https?://|\bwas\b|\bwere\b|\bhope\b|"
                   r"\benjoy\b|\blove you\b|\bsee you\b", re.I)

# Komentarze, które NIE są tracklistą. Bez tego 90% wyniku to „🔥🔥🔥" i „banger".
SMIEC = re.compile(
    r"^\s*(?:[\W_]+|nice|banger|tune|fire|love|wow|sick|yes+|omg|thanks?|"
    r"thank you|great|amazing|perfect|goat|classic|wow+|huh|lol|damn|"
    r"boom|yeah+|woo+|beautiful|masterpiece|mad|heavy|massive|"
    r"\d{1,2}:\d{2}|[\d\s:.-]+)\s*$", re.I)

# Tracklista w OPISIE: „00:00 Artysta - Tytuł", „1. Artysta - Tytuł",
# „[12:34] Artysta - Tytuł". Czas bywa, ale nie musi.
LINIA_OPISU = re.compile(
    r"^\s*(?:\[?(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{2}))?\]?\s*[-–—.)]?\s*)?"
    r"(?:(?P<nr>\d{1,3})\s*[.)]\s*)?"
    r"(?P<reszta>\S.{3,140})\s*$")


def _json(url: str):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                                         # noqa: BLE001
        print(f"    {e}", file=sys.stderr)
        return None


def client_id() -> str | None:
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


def czas(ms: int) -> str:
    s = ms // 1000
    return f"{s // 3600:d}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 \
        else f"{s // 60:d}:{s % 60:02d}"


def rozbierz(tekst: str) -> tuple[str, str] | None:
    """(wykonawca, tytuł) albo None. „ID" zwraca ('', 'ID') — brak nazwy przy
    znanym czasie to informacja o szwie, nie brak informacji."""
    tekst = tekst.strip().strip("*_`\"'")
    if SAMO_ID.match(tekst):
        return ("", "ID")
    if SMIEC.match(tekst) or len(tekst) < 5 or len(tekst) > 140:
        return None
    m = WYKONAWCA_TYTUL.match(tekst)
    if not m:
        return None
    a, t = m.group("a").strip(), m.group("t").strip()
    if len(a) < 2 or len(t) < 2:
        return None
    return (a, t)


def komentarze(track_id: int, cid: str, dlugosc_ms: int | None = None,
               pauza: float = 0.25) -> list[dict]:
    """Komentarze przypięte do czasu. Serwis podaje `timestamp` w ms.

    Z komentarzy bierzemy tylko dwie rzeczy i nic poza nimi:

      * ZNACZNIK „ID" — nikt nie rozpoznał utworu, ale KTOŚ ZAPYTAŁ AKURAT
        TAM. To jest pozycja szwu, nawet bez nazwy, i dla nas równie cenna.
      * CZYSTE „Wykonawca — Tytuł" — bez znaku zapytania, wykrzyknika, małpy
        i bez zdaniowego słownictwa. Reszta to zachwyty z myślnikiem
        („Lovely stuff - track?", „This is incredibly elegant - I feel love"),
        które udają tracklistę i zatruwają ją nazwiskami, których tam nie ma.
    """
    out, url = [], (f"{API}/tracks/{track_id}/comments?client_id={cid}"
                    f"&threaded=0&filter_replies=0&limit=200")
    while url:
        d = _json(url)
        if not isinstance(d, dict):
            break
        for c in d.get("collection") or []:
            ts = c.get("timestamp")
            if ts is None:                        # komentarz nieprzypięty do czasu
                continue
            # SoundCloud zwraca czasem wartownika bliskiego maksimum int32
            # (596:31:23 przy secie na 2 godziny). Poza długością nagrania
            # znacznik nic nie znaczy.
            if dlugosc_ms and ts > dlugosc_ms * 1.02:
                continue
            body = (c.get("body") or "").strip()
            rozb = rozbierz(body)
            if not rozb:
                continue
            if rozb[1] != "ID":                   # zwykły komentarz — surowe sito
                if (len(body) > 60 or PROZA.search(body)
                        or re.search(r"[?!@]", body)
                        or rozb[0][:1].islower() and " " in rozb[0]):
                    continue
            out.append({"ms": ts, "czas": czas(ts),
                        "wykonawca": rozb[0], "tytul": rozb[1],
                        "zrodlo": "komentarz soundcloud",
                        "autor": (c.get("user") or {}).get("username") or ""})
        url = d.get("next_href")
        if url and "client_id" not in url:
            url += f"&client_id={cid}"
        time.sleep(pauza)
    out.sort(key=lambda x: x["ms"])
    return out


def z_opisu(opis: str) -> list[dict]:
    """Tracklista wklejona pod setem. Czas bywa, ale nie musi."""
    if not opis:
        return []
    linie = [l for l in re.split(r"[\r\n]+", opis) if l.strip()]

    # Tracklista jest BLOKIEM kolejnych linii, nie rozsypanymi trafieniami.
    # Bez tego warunku podziękowania z tym samym myślnikiem („Once again -
    # thank you Garbicz, you were simply wonderful") lądują w tracklistach
    # jako utwory. Bierzemy najdłuższy nieprzerwany ciąg.
    biezacy: list[dict] = []
    najlepszy: list[dict] = []
    for l in linie:
        m = LINIA_OPISU.match(l)
        rozb = rozbierz(m.group("reszta")) if m else None
        if not rozb or PROZA.search(l):
            if len(biezacy) > len(najlepszy):
                najlepszy = biezacy
            biezacy = []
            continue
        ms = None
        if m.group("h") is not None:
            h, mi, s = m.group("h"), m.group("m"), m.group("s")
            ms = ((int(h) * 3600 + int(mi) * 60 + int(s)) * 1000 if s
                  else (int(h) * 60 + int(mi)) * 1000)
        biezacy.append({"ms": ms, "czas": czas(ms) if ms is not None else "",
                        "wykonawca": rozb[0], "tytul": rozb[1],
                        "zrodlo": "opis wrzutu", "autor": ""})
    if len(biezacy) > len(najlepszy):
        najlepszy = biezacy
    return najlepszy if len(najlepszy) >= 4 else []


def pelne_opisy(ids: list[int], cid: str, pauza: float = 0.3) -> dict[int, str]:
    """Opisy bez obcinania — w `miksy.json` trzymamy tylko 600 znaków, a
    tracklista bywa dłuższa niż cały opis, który zapisaliśmy."""
    out = {}
    for i in range(0, len(ids), 50):
        chunk = ",".join(str(x) for x in ids[i:i + 50])
        d = _json(f"{API}/tracks?ids={chunk}&client_id={cid}")
        for t in d or []:
            out[t.get("id")] = t.get("description") or ""
        time.sleep(pauza)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--od", type=int, default=0, help="Od którego miksu zacząć")
    ap.add_argument("--ile", type=int, default=100000)
    ap.add_argument("--wyjscie", default="tracklisty.json")
    ap.add_argument("--wznow", action="store_true",
                    help="Pomiń sety już zapisane w pliku wynikowym i dopisz "
                         "do niego resztę. Baza rośnie pod przebiegiem.")
    args = ap.parse_args()

    cid = client_id()
    if not cid:
        print("Brak client_id — api-v2 nie odpowie.")
        return 1

    miksy = json.loads((OUT / "miksy.json").read_text())
    # Identyfikator wrzutu wyciągamy z surowych zrzutów; miksy.json trzyma link.
    id_po_linku = {}
    for plik in ("roczniki_sety.json", "garbicz_szukanie.json", "audioriver_sety.json",
                 "podcasty_sety.json", "podcasty_sety2.json", "podcasty_konta.json"):
        if not (OUT / plik).exists():
            continue
        for k in json.loads((OUT / plik).read_text()):
            for s in k["sety"]:
                if s.get("link") and s.get("id"):
                    id_po_linku[s["link"].split("?")[0].rstrip("/")] = s["id"]

    cele = []
    for m in miksy:
        link = (m.get("link") or "").split("?")[0].rstrip("/")
        tid = id_po_linku.get(link)
        if tid:
            cele.append((tid, m))
    # Wznawianie. Baza rośnie pod przebiegiem: kiedy ten skrypt ruszał
    # pierwszy raz, miksów było 1352; po dołożeniu setów podcastowych jest
    # 2389. Bez tego dobicie kosztowałoby ponowne odpytanie o 503 już zrobione.
    zrobione: set[str] = set()
    if args.wznow and (OUT / args.wyjscie).exists():
        for w in json.loads((OUT / args.wyjscie).read_text()):
            zrobione.add((w.get("link") or "").split("?")[0].rstrip("/"))
        cele = [(t, m) for t, m in cele
                if (m.get("link") or "").split("?")[0].rstrip("/") not in zrobione]
        print(f"wznawiam — pomijam {len(zrobione)} już sprawdzonych")

    cele = cele[args.od:][:args.ile]
    print(f"miksów z identyfikatorem SoundCloud do sprawdzenia: {len(cele)}")

    opisy = pelne_opisy([t for t, _ in cele], cid)
    print(f"pełnych opisów pobranych: {len(opisy)}")

    wynik, z_kom, z_op = [], 0, 0
    for i, (tid, m) in enumerate(cele, 1):
        dl = m.get('dlugosc_min')
        poz = komentarze(tid, cid, int(dl) * 60000 if dl else None)
        skad = "komentarze"
        if len(poz) < 3:
            poz2 = z_opisu(opisy.get(tid, "") or m.get("opis") or "")
            if len(poz2) > len(poz):
                poz, skad = poz2, "opis"
        if not poz:
            continue
        wynik.append({
            "link": m.get("link"), "ksywa": m.get("ksywa"),
            "tytul": m.get("tytul"), "wydarzenie": m.get("wydarzenie"),
            "data": m.get("data"), "dlugosc_min": m.get("dlugosc_min"),
            "zrodlo_tracklisty": skad,
            "pozycji": len(poz),
            "z_czasem": sum(1 for p in poz if p["ms"] is not None),
            "nierozpoznanych": sum(1 for p in poz if p["tytul"] == "ID"),
            "tracklista": poz,
        })
        z_kom += skad == "komentarze"
        z_op += skad == "opis"
        if i % 25 == 0:
            print(f"  {i}/{len(cele)} — tracklist: {len(wynik)}", flush=True)

    p = OUT / args.wyjscie
    if args.wznow and p.exists():
        wynik = json.loads(p.read_text()) + wynik      # dopisujemy, nie kasujemy
    p.write_text(json.dumps(wynik, ensure_ascii=False, indent=1))
    print(f"\nsetów z tracklistą: {len(wynik)} (w tym przebiegu z {len(cele)})")
    print(f"  z komentarzy: {z_kom}   z opisu: {z_op}")
    print(f"  pozycji razem: {sum(w['pozycji'] for w in wynik)}")
    print(f"  z czasem:      {sum(w['z_czasem'] for w in wynik)}")
    print(f"  nierozpoznanych (ID): {sum(w['nierozpoznanych'] for w in wynik)}")
    print(f"zapisane: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
