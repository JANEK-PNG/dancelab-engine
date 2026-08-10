"""Wektory brzmienia dla CAŁEJ kolekcji strumieniowej — z 30-sekundowych próbek.

Kotwica „graj jak…" była martwa: zmierzone 09.08 — 0 z 201 utworów puli miało
wektor brzmienia, więc sterowanie nie zmieniało doboru ani o utwór. Utwory
z pliku mają wektory z 21.07, a strumienie (82% kolekcji Janka) nie mają
żadnych, bo nie ma z czego liczyć.

Rekordbox zapisuje takie utwory jako `apple-music:tracks:1459041006`, a ten
numer to wprost identyfikator katalogu iTunes — dopasowanie jeden-do-jednego,
bez zgadywania po tytule. Publiczne API zwraca `previewUrl` do ~30 s próbki.

Ten skrypt to rozszerzenie sprawdzonej ścieżki z 02.08 (`experiments_priv/
2026-08-01_ml_krok0/krok4_probki_itunes.py`) z HISTORII na całą kolekcję;
pisze do tego samego pliku i pomija to, co już policzone.

ZASADY (zgoda Janka 02.08, potwierdzona 09.08):
  * pobierz → policz → SKASUJ audio; na dysku nigdy nie leży więcej niż jeden plik;
  * katalog roboczy w repo (poza iCloud), nigdy na Pulpicie;
  * wysyłamy wyłącznie numery katalogowe, nic o użytkowniku;
  * każdy wektor dostaje `source: "preview"` — powstał z 30 s, nie z całości.

CZEGO TO NIE DA: struktury, początku utworu ani wykonalności szwu. Tego nie
ma w 30 sekundach i żadne przeliczenie tego nie wyczaruje.

Użycie:
    .venv/bin/python scripts/probki_itunes_kolekcja.py --probe   # tylko policz
    .venv/bin/python scripts/probki_itunes_kolekcja.py [--limit N]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

KORZEN = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KORZEN / "src"))
sys.path.insert(0, str(KORZEN / "scripts"))

WYJSCIE = KORZEN / "data/reports/apple_preview_embeddings.json"
TMP = KORZEN / "experiments_priv/_cache/previews"
LOOKUP = "https://itunes.apple.com/lookup"
UA = "DanceLab/1.0 (prywatne badanie lokalne)"
PACZKA = 100          # API przyjmuje do 200 ID naraz
PRZERWA = 3.0         # sekundy między zapytaniami — limit to ~20/min
SCHEMA = "apple-preview-embeddings-v1"


def strumienie_kolekcji() -> dict[str, str]:
    """{itunes_id: ContentID} dla wszystkich strumieni w kolekcji."""
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    db = Rekordbox6Database()
    try:
        out = {}
        for r in db.session.query(tables.DjmdContent).all():
            fp = str(r.FolderPath or "")
            if fp.startswith("apple-music:tracks:"):
                out[fp.rsplit(":", 1)[1]] = str(r.ID)
        return out
    finally:
        db.close()


def zapytaj(ids: list[str]) -> dict[str, dict]:
    url = f"{LOOKUP}?{urllib.parse.urlencode({'id': ','.join(ids)})}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        dane = json.loads(r.read().decode("utf-8"))
    return {str(x.get("trackId")): x for x in dane.get("results", [])
            if x.get("trackId")}


def _zapisz(gotowe: dict, model_id: str) -> None:
    WYJSCIE.parent.mkdir(parents=True, exist_ok=True)
    WYJSCIE.write_text(json.dumps(
        {"schema_version": SCHEMA, "model": model_id,
         "note": "wektory z 30-sekundowych próbek iTunes; audio skasowane",
         "tracks": gotowe}, ensure_ascii=False))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true",
                    help="tylko policz pokrycie, nic nie pobieraj")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    chce = strumienie_kolekcji()
    gotowe = (json.loads(WYJSCIE.read_text()).get("tracks", {})
              if WYJSCIE.exists() else {})
    brakuje = sorted(set(chce) - set(gotowe))
    print(f"strumieni w kolekcji : {len(chce)}")
    print(f"wektory już policzone: {len(set(chce) & set(gotowe))}")
    print(f"do dociągnięcia      : {len(brakuje)}")
    if args.limit:
        brakuje = brakuje[:args.limit]
    if not brakuje:
        print("nic do roboty")
        return 0

    # ── adresy próbek, paczkami
    meta: dict[str, dict] = {}
    for i in range(0, len(brakuje), PACZKA):
        paczka = brakuje[i:i + PACZKA]
        try:
            meta.update(zapytaj(paczka))
        except Exception as exc:  # noqa: BLE001 — sieć bywa kapryśna
            print(f"  ⚠ zapytanie {i // PACZKA + 1}: {exc}")
        if i + PACZKA < len(brakuje):
            time.sleep(PRZERWA)
    z_probka = {k: v for k, v in meta.items() if v.get("previewUrl")}
    print(f"katalog zna          : {len(meta)} · z próbką: {len(z_probka)}")
    if args.probe:
        print("--probe: nic nie pobrano")
        return 0
    if not z_probka:
        return 1

    import torch
    from library_e_embeddings import MODEL_ID, embed_track
    from transformers import ClapModel, ClapProcessor

    urzadzenie = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"ładuję CLAP ({MODEL_ID}) na {urzadzenie}…", flush=True)
    model = ClapModel.from_pretrained(MODEL_ID).to(urzadzenie).eval()
    procesor = ClapProcessor.from_pretrained(MODEL_ID)

    TMP.mkdir(parents=True, exist_ok=True)
    ok = blad = 0
    for n, (tid, m) in enumerate(sorted(z_probka.items()), 1):
        plik = TMP / f"{tid}.m4a"
        try:
            req = urllib.request.Request(m["previewUrl"],
                                         headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r, plik.open("wb") as fh:
                fh.write(r.read())
            wektor = embed_track(plik, model, procesor, urzadzenie)
        except Exception as exc:  # noqa: BLE001 — jeden utwór ≠ koniec zbioru
            print(f"  ⚠ {tid}: {type(exc).__name__} {exc}", flush=True)
            wektor = None
        finally:
            plik.unlink(missing_ok=True)       # audio nie zostaje NIGDY

        if wektor is None:
            blad += 1
            continue
        gotowe[tid] = {"vector": wektor, "content_id": chce.get(tid),
                       "artist": m.get("artistName"), "title": m.get("trackName"),
                       "source": "preview", "preview_sec": 30}
        ok += 1
        if ok % 25 == 0:
            _zapisz(gotowe, MODEL_ID)
            print(f"  … {n}/{len(z_probka)} · policzone {ok} · błędy {blad}",
                  flush=True)

    _zapisz(gotowe, MODEL_ID)
    print(f"\ngotowe: {ok} nowych wektorów · błędy {blad} · "
          f"razem w pliku {len(gotowe)}")
    zostalo = list(TMP.glob("*.m4a"))
    print("plików audio na dysku po robocie:", len(zostalo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
