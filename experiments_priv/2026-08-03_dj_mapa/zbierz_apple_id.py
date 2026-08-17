"""Identyfikatory Apple Music dla policzonych utworów mapy.

PO CO. Pomysł Janka (11.08): playlista w Apple Music z utworami mapy →
Rekordbox mieli je w całości → pewne tonacje i tempo pełnoplikowe dla
kolumn mapy (uczciwa powtórka szczebla harmonii z ablacji). Playlisty nie
da się zbudować bez trackId — ten skrypt je zbiera.

JAK. Wyszukiwarka iTunes (public, bez klucza; 403 sprzed tygodnia było
kaprysem sygnatury — z przeglądarkowym UA działa, sprawdzone 11.08).
Zapora ta sama, co przy Deezerze i Bandcampie: znormalizowany wykonawca
I tytuł muszą się zgadzać; wątpliwe = brak, nie zgadywanie. Limit iTunes
~20 zapytań/min → sleep 3 s, bieg kilkugodzinny, wznawialny po utwor_id.

Wynik: apple_id.jsonl — {utwor_id, apple_id, apple_artysta, apple_tytul}.

Użycie:
    .venv/bin/python zbierz_apple_id.py [--ile N]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import time
import unicodedata
import urllib.parse
import urllib.request

KATALOG = pathlib.Path(__file__).resolve().parent
MANIFEST = KATALOG / "pomiar_utworow.jsonl"
WYJSCIE = KATALOG / "apple_id.jsonl"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/605.1.15"}


def norm(tekst: str) -> str:
    t = unicodedata.normalize("NFKD", tekst or "").encode("ascii", "ignore").decode()
    t = t.lower()
    t = re.sub(r"\((original|extended|club|radio)[^)]*\)", " ", t)
    t = re.sub(r"\b(original|extended)\s+mix\b", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def pasuje(nw, nt, iw, it):
    nw, nt, iw, it = norm(nw), norm(nt), norm(iw), norm(it)
    if not nw or not nt or not iw or not it:
        return False
    w_ok = nw in iw or iw in nw or bool(set(nw.split()) & set(iw.split()))
    t_ok = nt == it or nt in it or it in nt
    return w_ok and t_ok


def szukaj(wyk: str, tyt: str) -> dict | None:
    # country=pl: trackId musi istnieć w sklepie Janka — pilotaż pokazał, że
    # id z indeksu US wypadają przy dodawaniu do playlisty (Breathe, 1/10).
    q = urllib.parse.urlencode({"term": f"{wyk} {tyt}"[:120],
                                "entity": "song", "limit": 5,
                                "country": "pl"})
    req = urllib.request.Request(f"https://itunes.apple.com/search?{q}",
                                 headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        wyniki = json.loads(r.read().decode()).get("results", [])
    for w in wyniki:
        if w.get("kind") != "song":
            continue
        if pasuje(wyk, tyt, w.get("artistName", ""), w.get("trackName", "")):
            return w
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ile", type=int, default=0)
    args = ap.parse_args()

    # test-bzdura przed biegiem (twarda reguła)
    for wyk, tyt in (("Xqzvw Blorptak", "Grumblefish Zzzyx"),):
        if szukaj(wyk, tyt) is not None:
            print("⛔ zapora nie trzyma na zapytaniu-bzdurze — nie ruszam")
            return 1
    print("✓ zapora trzyma", flush=True)

    praca = []
    for linia in MANIFEST.read_text().splitlines():
        w = json.loads(linia)
        if w.get("status") == "ok":
            praca.append((w["utwor_id"], w["wykonawca"], w["tytul"]))
    zrobione = set()
    if WYJSCIE.exists():
        for linia in WYJSCIE.read_text().splitlines():
            try:
                zrobione.add(json.loads(linia)["utwor_id"])
            except Exception:
                pass
    praca = [p for p in praca if p[0] not in zrobione]
    if args.ile:
        praca = praca[: args.ile]
    print(f"do wyszukania: {len(praca)}", flush=True)

    ok = brak = zle = 0
    t0 = time.time()
    with WYJSCIE.open("a") as out:
        for n, (uid, wyk, tyt) in enumerate(praca, 1):
            wpis = {"utwor_id": uid}
            try:
                hit = szukaj(wyk, tyt)
                if hit:
                    wpis.update(apple_id=hit["trackId"],
                                apple_artysta=hit.get("artistName"),
                                apple_tytul=hit.get("trackName"))
                    ok += 1
                else:
                    wpis["status"] = "brak"
                    brak += 1
            except Exception as exc:  # noqa: BLE001
                wpis["status"] = f"blad:{type(exc).__name__}"
                zle += 1
                if "429" in str(exc) or "403" in str(exc):
                    time.sleep(60)          # przycisk hamulca na limit
            out.write(json.dumps(wpis, ensure_ascii=False) + "\n")
            out.flush()
            time.sleep(3.0)                 # limit iTunes ~20/min
            if n % 200 == 0:
                zostalo = (time.time() - t0) / n * (len(praca) - n) / 3600
                print(f"  {n}/{len(praca)} · znalezione {ok} · brak {brak} · "
                      f"błędy {zle} · ~{zostalo:.1f} h", flush=True)
    print(f"KONIEC: znalezione {ok} · brak {brak} · błędy {zle} → {WYJSCIE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
