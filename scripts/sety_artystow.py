"""Dobija miksy artystom, którzy w bazie mają zero albo prawie zero.

Dotąd miksy przychodziły OD STRONY WYDARZENIA: archiwa Garbicza, wyszukiwanie
po nazwie festiwalu, konta cykli podcastowych. To działa dla tych, którzy grali
w Garbiczu wcześniej albo weszli do dużej serii — ale zostawia bez niczego
artystę, który zagra w 2026 po raz pierwszy i nie ma za sobą RA ani Boiler Room.

W line-upie 2026 tak ma **239 z 456 osób**: 214 z Garbicza i 25 z Audioriver.
Dla nich trzeba wejść OD STRONY ARTYSTY.

Dwie drogi, w tej kolejności:

  1. KONTO, jeśli znamy uchwyt — pewne, bo to jego własne wrzuty.
  2. WYSZUKIWANIE PO NAZWIE, gdy uchwytu nie ma. Tu dopasowanie musi być
     ostrzejsze: bierzemy tylko wrzuty, w których nazwa artysty stoi w tytule
     ALBO jest nazwą konta — inaczej pod „Kotoe" wpadnie każdy, kto zagrał
     jej utwór.

Bierzemy DŁUGIE nagrania (domyślnie od 25 minut). Poniżej tego to najczęściej
własny utwór albo edit, a szukamy setów — czyli tego, co ma szew w środku.
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
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
API = "https://api-v2.soundcloud.com"


def _n(s: str) -> str:
    s = U.normalize("NFKD", s or "")
    s = "".join(c for c in s if not U.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def n2(s: str) -> str:
    s = U.normalize("NFKD", s or "")
    s = "".join(c for c in s if not U.combining(c))
    return " " + re.sub(r"[^a-z0-9]+", " ", s.lower()).strip() + " "


def _js(url: str):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                                         # noqa: BLE001
        print(f"    {e}", file=sys.stderr)
        return None


def client_id() -> str | None:
    try:
        req = urllib.request.Request("https://soundcloud.com/discover", headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception:                                              # noqa: BLE001
        return None
    for src in re.findall(r'src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"', html):
        try:
            req = urllib.request.Request(src, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                js = r.read().decode("utf-8", "replace")
        except Exception:                                          # noqa: BLE001
            continue
        m = re.search(r'client_id\s*:\s*"([A-Za-z0-9]{20,})"', js)
        if m:
            return m.group(1)
    return None


def _wiersz(t: dict) -> dict:
    return {"id": t.get("id"), "tytul": t.get("title"),
            "uploader": (t.get("user") or {}).get("username"),
            "uploader_url": (t.get("user") or {}).get("permalink"),
            "link": t.get("permalink_url"),
            "opis": (t.get("description") or "")[:600],
            "data_wrzutu": (t.get("created_at") or "")[:10],
            "dlugosc_min": round((t.get("duration") or 0) / 60000)}


def z_konta(uchwyt: str, cid: str, min_min: int) -> list[dict]:
    d = _js(f"{API}/resolve?url=https://soundcloud.com/"
            f"{urllib.parse.quote(uchwyt)}&client_id={cid}")
    if not isinstance(d, dict) or d.get("kind") != "user":
        return []
    d2 = _js(f"{API}/users/{d['id']}/tracks?client_id={cid}&limit=200")
    if not isinstance(d2, dict):
        return []
    return [_wiersz(t) for t in d2.get("collection") or []
            if (t.get("duration") or 0) >= min_min * 60000]


def z_szukania(ksywa: str, cid: str, min_min: int) -> list[dict]:
    d = _js(f"{API}/search/tracks?q={urllib.parse.quote(ksywa)}"
            f"&client_id={cid}&limit=50")
    if not isinstance(d, dict):
        return []
    cel_luzny, cel_scisly = n2(ksywa).strip(), _n(ksywa)
    wzor = re.compile(r"(?<![a-z0-9])" + re.escape(cel_luzny).replace(r"\ ", r"\s+")
                      + r"(?![a-z0-9])")
    out = []
    for t in d.get("collection") or []:
        if (t.get("duration") or 0) < min_min * 60000:
            continue
        # Nazwa w tytule ALBO konto należące do artysty. Bez tego pod „Kotoe"
        # wpada każdy, kto zagrał jej utwór i wpisał ją do tracklisty.
        w_tytule = bool(wzor.search(n2(t.get("title") or "")))
        to_konto = _n((t.get("user") or {}).get("username", "")) == cel_scisly
        if w_tytule or to_konto:
            out.append(_wiersz(t))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-minut", type=int, default=25,
                    help="Krótsze nagrania to zwykle własne utwory, nie sety.")
    ap.add_argument("--na-artyste", type=int, default=8)
    ap.add_argument("--tylko-lineup", action="store_true",
                    help="Tylko artyści z line-upu 2026 — oni grają najbliżej.")
    ap.add_argument("--wyjscie", default="sety_artystow.json")
    args = ap.parse_args()

    cid = client_id()
    if not cid:
        print("Brak client_id.")
        return 1

    miksy = json.loads((OUT / "miksy.json").read_text())
    maja = {_n(m.get("ksywa") or "") for m in miksy if m.get("ksywa")}
    soc = json.loads((OUT / "socials.json").read_text())

    if args.tylko_lineup:
        fest = json.loads((OUT / "festiwale.json").read_text())
        lista = [v["ksywa"] for v in fest.values()]
    else:
        lista = [a.strip() for a in (OUT / "artysci_wszyscy.txt").read_text().splitlines()
                 if a.strip()]
    braki = [a for a in lista if _n(a) not in maja]
    print(f"artystów bez ani jednego miksu: {len(braki)} z {len(lista)}")

    wynik, z_kont, z_szuk = [], 0, 0
    for i, a in enumerate(braki, 1):
        uchwyt = ((soc.get(a) or {}).get("soundcloud") or "").replace(
            "https://soundcloud.com/", "").strip("/")
        sety = z_konta(uchwyt, cid, args.min_minut) if uchwyt else []
        skad = "konto"
        if not sety:
            sety = z_szukania(a, cid, args.min_minut)
            skad = "szukanie"
        if sety:
            sety.sort(key=lambda s: -(s.get("dlugosc_min") or 0))
            wynik.append({"playlista": "", "url": "", "ksywa": a,
                          "skad": skad, "sety": sety[:args.na_artyste]})
            z_kont += skad == "konto"
            z_szuk += skad == "szukanie"
        if i % 25 == 0:
            print(f"  {i}/{len(braki)} — z setami {len(wynik)}", flush=True)
        time.sleep(0.35)

    p = OUT / args.wyjscie
    p.write_text(json.dumps(wynik, ensure_ascii=False, indent=1))
    print(f"\nartystów uratowanych: {len(wynik)} z {len(braki)}")
    print(f"  z konta: {z_kont}   z wyszukiwania: {z_szuk}")
    print(f"  setów razem: {sum(len(w['sety']) for w in wynik)}")
    print(f"zapisane: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
