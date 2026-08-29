"""Wektory brzmienia (CLAP) dla ocenianych utworów, którym ich brakuje.

Powód: pomiar kontekstu setu padł, bo 107 ze 155 ocenianych utworów ma
w analizach wyłącznie głośność, a wektorów brzmienia jest 47. „Świat”, o
którym Janek pisze w notatkach, jest cechą barwy — bez wektorów nie ma czym
go zmierzyć.

Czyta pliki z dysku Janka (nic nie pobiera), liczy dokładnie tym samym
modelem i tą samą procedurą co `scripts/library_e_embeddings.py`
(laion/clap-htsat-unfused, pięć okien po 10 s, średnia, norma 1), i dopisuje
do tego samego katalogu wektorów. Ma punkt wznowienia — przerwane liczenie
wraca tam, gdzie stanęło.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

KATALOG = ROOT / "data/reports/library_embeddings.json"
BIBLIOTEKA = pathlib.Path.home() / "Music"
OCENY = ROOT / "experiments_priv/2026-08-17_ocena_papierowa"
PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def main() -> int:
    from dancelab.storage.repositories import FileAnalysisRepository
    from dancelab.tui.duplikaty import scal

    dane = json.loads((OCENY / "playlisty_dane.json").read_text(encoding="utf-8"))
    potrzebne = {t["track_id"] for lista in dane.values() for t in lista}
    repo = FileAnalysisRepository(PROCESSED)
    widok, _ = scal([repo.get(t) for t in repo.list_track_ids()])
    oceniane = [a for a in widok if a.track.track_id in potrzebne]

    katalog = json.loads(KATALOG.read_text(encoding="utf-8"))
    maja = {nfc(k) for k in katalog["tracks"]}

    braki: list[tuple[str, pathlib.Path]] = []
    poza_biblioteka: list[str] = []
    strumienie: list[str] = []
    for a in oceniane:
        raw = str(a.track.source_path or "")
        sciezka = pathlib.Path(nfc(raw))
        # Strumień Apple Music NIE MA pliku na dysku — nie da się go policzyć
        # ani teraz, ani później. Wcześniej ten `continue` po cichu wliczał je
        # do „mają już wektor" i licznik pokazywał 154 zamiast 47.
        if raw.startswith("apple-music:") or not sciezka.is_absolute():
            strumienie.append(raw[:60])
            continue
        try:
            rel = nfc(str(sciezka.relative_to(BIBLIOTEKA)))
        except ValueError:
            poza_biblioteka.append(sciezka.name)
            continue
        if rel in maja:
            continue
        if not sciezka.exists():
            poza_biblioteka.append(f"{sciezka.name} (brak pliku)")
            continue
        braki.append((rel, sciezka))

    braki = sorted(set(braki))
    ma_wektor = len(oceniane) - len(braki) - len(poza_biblioteka) - len(strumienie)
    print(f"ocenianych utworów: {len(oceniane)}")
    print(f"mają już wektor: {ma_wektor}")
    print(f"strumienie Apple Music (pliku NIE MA, nigdy nie policzymy): "
          f"{len(strumienie)}")
    print(f"do policzenia: {len(braki)}")
    if poza_biblioteka:
        print(f"pomijam (poza ~/Music albo brak pliku): {len(poza_biblioteka)}")
        for n in poza_biblioteka[:5]:
            print(f"   • {n}")
    if not braki:
        return 0
    if "--tylko-lista" in sys.argv:
        return 0

    import torch
    from library_e_embeddings import embed_track
    from transformers import ClapModel, ClapProcessor

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"\nładuję CLAP na {device}…", flush=True)
    model = ClapModel.from_pretrained("laion/clap-htsat-unfused").to(device).eval()
    processor = ClapProcessor.from_pretrained("laion/clap-htsat-unfused")

    t0 = time.time()
    dodane = padly = 0
    for i, (rel, sciezka) in enumerate(braki, 1):
        try:
            vec = embed_track(sciezka, model, processor, device)
        except Exception as exc:                      # noqa: BLE001
            print(f"  ✗ {sciezka.name[:52]}: {type(exc).__name__}: {exc}", flush=True)
            padly += 1
            continue
        if vec is None:
            print(f"  ✗ {sciezka.name[:52]}: za krótki albo pusty", flush=True)
            padly += 1
            continue
        katalog["tracks"][rel] = vec
        dodane += 1
        if i % 10 == 0 or i == len(braki):
            KATALOG.write_text(json.dumps(katalog, ensure_ascii=False),
                               encoding="utf-8")
            tempo = (time.time() - t0) / i
            print(f"  {i}/{len(braki)} · dodane {dodane} · padły {padly} · "
                  f"{tempo:.1f} s/utwór · zostało ~{tempo * (len(braki) - i) / 60:.1f} min",
                  flush=True)

    KATALOG.write_text(json.dumps(katalog, ensure_ascii=False), encoding="utf-8")
    print(f"\ngotowe: dodane {dodane}, padły {padly}, "
          f"katalog ma teraz {len(katalog['tracks'])} wektorów")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
