"""Biblioteki person z PUBLICZNEGO KATALOGU — nie z biblioteki Janka.

Poprawka Janka 09.08: „nie buduj z mojej realnej biblioteki, budowanie z mojej
oznacza, że jest moja — ja nie mam industrial techno ani utworów na wesela".
Racja: pocięta biblioteka Janka to nadal jego gust. Persona musi mieć SWÓJ
repertuar, inaczej test mierzy jego zbiór w innym kształcie.

Katalog: Deezer (publiczne wyszukiwanie, bez klucza). iTunes odpadł — jego
`search` odpowiada 403, działa tylko odpytywanie po znanym identyfikatorze.

Zasady te same, co przy próbkach iTunes (zgoda Janka 02.08):
  pobierz → policz → SKASUJ audio, jeden plik naraz, katalog poza iCloud,
  wysyłamy tylko zapytania o katalog, nic o użytkowniku.

CO TE BIBLIOTEKI SĄ, A CZYM NIE SĄ:
  * tempo, tonacja, energia i sekcje są liczone NASZYM silnikiem z 30 s —
    to prawdziwy pomiar, ale FRAGMENTU, nie całego utworu;
  * długość utworu bierzemy z katalogu, więc jest prawdziwa;
  * `source_path` to `deezer:track:ID` — NIE jest to plik, więc odsłuch
    i render szwu odmówią, tak samo jak przy strumieniach Apple Music;
  * warstwy audio (odsłuch, szew) testuje się na realnych plikach Janka,
    a te biblioteki testują warstwę DECYZJI: sita, brief, kotwicę, komunikaty.

Użycie:
    .venv/bin/python .../zbuduj_z_katalogu.py --persona kuba --ile 150
    .venv/bin/python .../zbuduj_z_katalogu.py --wszystkie --ile 150
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

KORZEN = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN / "src"))
sys.path.insert(0, str(KORZEN / "scripts"))
KATALOG = pathlib.Path(__file__).resolve().parent
PULE = KATALOG / "pule"
TMP = KORZEN / "experiments_priv/_cache/persony"
UA = "DanceLab/1.0 (prywatne badanie lokalne)"
WERSJA = "deezer-preview-30s"

# Świat brzmieniowy każdej persony — zapytania do katalogu, nie do biblioteki
ZAPYTANIA = {
    "kuba": [                       # techno, wąsko i mocno
        "industrial techno", "hard techno", "peak time techno",
        "Amelie Lens", "Charlotte de Witte", "I Hate Models", "Perc",
        "Kobosil", "Rebekah", "hypnotic techno", "warehouse techno",
    ],
    "bartek": [                     # wesela i open format
        "wesele przeboje", "disco polo hity", "polskie przeboje taneczne",
        "wedding party hits", "party classics 80s", "r&b party hits",
        "pop hits dance remix", "rock classics party", "latino party",
    ],
    "zosia": [                      # początkująca: to, co słychać wszędzie
        "edm hits", "house chart hits", "dance pop 2024", "festival anthems",
        "tech house hits", "mainstage edm",
    ],
    "marta": [                      # leftfield, minimal, dub techno
        "dub techno", "minimal techno", "deep techno", "Basic Channel",
        "Donato Dozzy", "Move D", "ambient techno", "leftfield house",
    ],
}


def szukaj(zapytanie: str, ile: int) -> list[dict]:
    url = "https://api.deezer.com/search?" + urllib.parse.urlencode(
        {"q": zapytanie, "limit": ile})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as odp:
        return json.loads(odp.read().decode()).get("data", [])


_GATUNKI: dict[str, str | None] = {}


def gatunek_albumu(album_id: str) -> str | None:
    """Gatunek z katalogu (przy albumie) — prawdziwa etykieta, nie nasza."""
    if album_id in _GATUNKI:
        return _GATUNKI[album_id]
    nazwa = None
    try:
        req = urllib.request.Request(f"https://api.deezer.com/album/{album_id}",
                                     headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as odp:
            dane = json.loads(odp.read().decode())
        lista = ((dane.get("genres") or {}).get("data") or [])
        nazwa = lista[0].get("name") if lista else None
    except Exception:  # noqa: BLE001 — brak gatunku to STAN, nie awaria
        nazwa = None
    _GATUNKI[album_id] = nazwa
    return nazwa


def zbierz(persona: str, ile: int) -> list[dict]:
    """Utwory z katalogu: unikalne, z próbką, z sensowną długością."""
    zebrane: dict[str, dict] = {}
    na_zapytanie = max(ile // max(len(ZAPYTANIA[persona]), 1) * 2, 25)
    for q in ZAPYTANIA[persona]:
        try:
            wyniki = szukaj(q, min(na_zapytanie, 100))
        except Exception as exc:  # noqa: BLE001 — sieć bywa kapryśna
            print(f"  ⚠ {q!r}: {exc}")
            continue
        for x in wyniki:
            if not x.get("preview") or not x.get("id"):
                continue
            if not (60 <= int(x.get("duration") or 0) <= 900):
                continue
            zebrane.setdefault(str(x["id"]), x)
        time.sleep(0.4)
        if len(zebrane) >= ile:
            break
    return list(zebrane.values())[:ile]


def zbuduj(persona: str, ile: int, z_wektorem: bool = True) -> int:
    from dancelab.core.config import load_config
    from dancelab.core.pipeline import analyze_track
    from dancelab.storage.repositories import FileAnalysisRepository

    utwory = zbierz(persona, ile)
    print(f"{persona}: katalog dał {len(utwory)} utworów")
    if not utwory:
        return 0

    model = procesor = urzadzenie = None
    if z_wektorem:
        import torch
        from library_e_embeddings import MODEL_ID, embed_track  # noqa: F401
        from transformers import ClapModel, ClapProcessor
        urzadzenie = "mps" if torch.backends.mps.is_available() else "cpu"
        model = ClapModel.from_pretrained(MODEL_ID).to(urzadzenie).eval()
        procesor = ClapProcessor.from_pretrained(MODEL_ID)

    cfg = load_config()
    kat = PULE / persona
    kat.mkdir(parents=True, exist_ok=True)
    repo = FileAnalysisRepository(kat)
    TMP.mkdir(parents=True, exist_ok=True)
    ok = blad = 0
    for n, x in enumerate(utwory, 1):
        plik = TMP / f"{x['id']}.mp3"
        try:
            req = urllib.request.Request(x["preview"], headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r, plik.open("wb") as fh:
                fh.write(r.read())
            a = analyze_track(plik, cfg, title=x.get("title"),
                              artist=(x.get("artist") or {}).get("name"))
            if z_wektorem:
                from library_e_embeddings import embed_track
                a.track.sound_embedding = embed_track(plik, model, procesor,
                                                      urzadzenie)
        except Exception as exc:  # noqa: BLE001 — jeden utwór ≠ koniec puli
            print(f"  ⚠ {x.get('title','?')[:24]}: {type(exc).__name__} {exc}")
            blad += 1
            continue
        finally:
            plik.unlink(missing_ok=True)        # audio nie zostaje NIGDY

        a.engine_version = WERSJA
        a.track.track_id = f"dz{x['id']}"
        a.track.source_path = f"deezer:track:{x['id']}"
        a.track.duration_sec = float(x.get("duration") or 0) or a.track.duration_sec
        album_id = str((x.get("album") or {}).get("id") or "")
        a.track.style_label = gatunek_albumu(album_id) if album_id else None
        for s in a.segments:
            s.track_id = a.track.track_id
        for f in a.features:
            f.track_id = a.track.track_id
        repo.save(a)
        ok += 1
        if ok % 25 == 0:
            print(f"  … {n}/{len(utwory)} · policzone {ok} · błędy {blad}",
                  flush=True)
    (kat / "OPIS.txt").write_text(
        f"persona {persona}\nzapytania: {', '.join(ZAPYTANIA[persona])}\n"
        f"utworów: {ok}\nźródło: katalog Deezer, 30 s próbki, audio skasowane\n")
    print(f"{persona}: zapisane {ok}, błędy {blad}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona", choices=sorted(ZAPYTANIA))
    ap.add_argument("--wszystkie", action="store_true")
    ap.add_argument("--ile", type=int, default=150)
    ap.add_argument("--bez-wektorow", action="store_true")
    args = ap.parse_args()
    kogo = sorted(ZAPYTANIA) if args.wszystkie else [args.persona]
    if not kogo or kogo == [None]:
        ap.error("podaj --persona albo --wszystkie")
    for p in kogo:
        zbuduj(p, args.ile, z_wektorem=not args.bez_wektorow)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
