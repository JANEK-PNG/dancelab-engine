"""Sprawdza, czy linki w bazie faktycznie działają.

Zbieraliśmy je z siedmiu źródeł przez cały dzień i ani razu nie zapytaliśmy
serwera, czy to, na co wskazują, jeszcze istnieje. Link, który wygląda dobrze
i nie działa, jest gorszy niż puste pole — bo puste pole mówi prawdę.

Trzy powody, dla których adres z naszej bazy może być martwy:

  * WRZUT ZNIKNĄŁ. Sety na SoundCloud padają od zgłoszeń praw autorskich
    częściej niż cokolwiek innego w tej bazie; archiwa festiwalowe sprzed
    dziesięciu lat są tego pełne.
  * KONTO ZNIKNĘŁO. Wtedy pada cały dorobek artysty naraz — i to widać
    dopiero w zestawieniu, nie po jednym linku.
  * ŹLE ZŁOŻYŁAM ADRES. Tak było z Mixcloud w De School: parametr `feed`
    bywa pełnym adresem albo samą ścieżką, więc przez chwilę mieliśmy
    874 adresy „mixcloud.comhttps://…". Sprawdzanie łapie własne błędy.

METODA. SoundCloud sprawdzamy HURTEM przez `api-v2/tracks?ids=` — pięćdziesiąt
identyfikatorów w jednym zapytaniu zamiast pięćdziesięciu zapytań. Resztę
metodą HEAD, równolegle, ale oszczędnie: to nie jest test obciążeniowy cudzego
serwera, tylko weryfikacja własnej bazy.
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import random
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

OUT = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def _kod(url: str, timeout: int = 15) -> int:
    """Kod odpowiedzi. 0 = nie udało się połączyć w ogóle."""
    try:
        req = urllib.request.Request(url, headers=UA, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        # Część serwisów nie lubi HEAD i odpowiada 405 na żywy adres.
        if e.code in (403, 405):
            try:
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return r.status
            except Exception:                                      # noqa: BLE001
                return e.code
        return e.code
    except Exception:                                              # noqa: BLE001
        return 0


def sprawdz_rownolegle(adresy: list[str], watkow: int = 8) -> dict[str, int]:
    with ThreadPoolExecutor(max_workers=watkow) as ex:
        return dict(zip(adresy, ex.map(_kod, adresy)))


def soundcloud_hurtem(ids: list[str], cid: str) -> set[str]:
    """Które identyfikatory SoundCloud jeszcze żyją. Po 50 na zapytanie."""
    zyje: set[str] = set()
    for i in range(0, len(ids), 50):
        paczka = ",".join(ids[i:i + 50])
        url = f"https://api-v2.soundcloud.com/tracks?ids={paczka}&client_id={cid}"
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                for t in json.loads(r.read().decode("utf-8")):
                    zyje.add(str(t.get("id")))
        except Exception:                                          # noqa: BLE001
            continue
    return zyje


def zbierz() -> dict[str, list[str]]:
    """Adresy wg zbioru, żeby dało się powiedzieć GDZIE jest problem."""
    grupy: dict[str, list[str]] = collections.defaultdict(list)
    if (OUT / "miksy.json").exists():
        for r in json.loads((OUT / "miksy.json").read_text()):
            if r.get("link"):
                grupy["miksy"].append(r["link"])
    if (OUT / "de_school.json").exists():
        for r in json.loads((OUT / "de_school.json").read_text()):
            if r.get("mixcloud"):
                grupy["de school (mixcloud)"].append(r["mixcloud"])
            if r.get("link_strony"):
                grupy["de school (strona)"].append(r["link_strony"])
    if (OUT / "ra.json").exists():
        for r in json.loads((OUT / "ra.json").read_text())["wystepy"]:
            if r.get("link"):
                grupy["występy RA"].append(r["link"])
    if (OUT / "bandcamp.json").exists():
        b = json.loads((OUT / "bandcamp.json").read_text())
        for r in b["artysci"]:
            if r.get("bandcamp"):
                grupy["bandcamp"].append(r["bandcamp"])
        for r in b["wydawnictwa"]:
            if r.get("link"):
                grupy["wydawnictwa bandcamp"].append(r["link"])
    for plik in ("apple.json", "apple_roczniki.json", "apple_audioriver.json",
                 "apple_reszta.json", "apple_wisloujscie.json"):
        if (OUT / plik).exists():
            for r in json.loads((OUT / plik).read_text())["artysci"]:
                if r.get("apple_music"):
                    grupy["apple"].append(r["apple_music"])
    return grupy


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probka", type=int, default=120,
                    help="Ile adresów na zbiór. 0 = wszystkie.")
    ap.add_argument("--watkow", type=int, default=8)
    ap.add_argument("--wyjscie", default="linki_sprawdzone.json")
    args = ap.parse_args()

    grupy = zbierz()
    los = random.Random(11)
    raport, martwe = {}, []

    for nazwa, adresy in sorted(grupy.items()):
        unikaty = sorted(set(adresy))
        badane = (unikaty if args.probka == 0 or len(unikaty) <= args.probka
                  else los.sample(unikaty, args.probka))
        kody = sprawdz_rownolegle(badane, args.watkow)
        licz = collections.Counter(kody.values())
        ok = sum(v for k, v in licz.items() if 200 <= k < 400)
        raport[nazwa] = {
            "wszystkich": len(unikaty), "sprawdzonych": len(badane),
            "dzialajacych": ok,
            "udzial": round(ok / max(len(badane), 1) * 100, 1),
            "kody": dict(licz),
        }
        martwe += [{"zbior": nazwa, "link": u, "kod": k}
                   for u, k in kody.items() if not (200 <= k < 400)]
        print(f"  {nazwa:24s} {ok:4d}/{len(badane):4d} działa "
              f"({raport[nazwa]['udzial']:5.1f}%)  z {len(unikaty)}  {dict(licz)}",
              flush=True)

    (OUT / args.wyjscie).write_text(json.dumps(
        {"raport": raport, "martwe": martwe}, ensure_ascii=False, indent=1))
    print(f"\nmartwych adresów w próbce: {len(martwe)}")
    print(f"zapisane: {OUT / args.wyjscie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
