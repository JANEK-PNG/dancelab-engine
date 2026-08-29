"""Zanim kupisz: czy tego utworu nie ma już na dysku pod inną nazwą.

Strumień Apple Music i kupiony plik to dla nas dwa różne wpisy, ale mogą być
tym samym utworem. Porównanie po nazwie (wykonawca + tytuł, znormalizowane),
z progiem podobieństwa i ZAWSZE do ręcznego potwierdzenia — nigdy nie łączę
utworów automatycznie, bo pomyłka wchodzi potem do pomiaru jako fakt.
"""

from __future__ import annotations

import difflib
import json
import pathlib
import re
import unicodedata

TU = pathlib.Path(__file__).parent
ROOT = TU.parents[1]
OCENY = ROOT / "experiments_priv/2026-08-17_ocena_papierowa"
PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"
MUZ = pathlib.Path.home() / "Music"
ROZSZERZENIA = {".wav", ".mp3", ".aiff", ".aif", ".flac", ".m4a"}
PROG = 0.72


def klucz(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).lower()
    s = re.sub(r"\((original|extended|radio)[^)]*\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def main() -> int:
    from dancelab.storage.repositories import FileAnalysisRepository
    from dancelab.tui.duplikaty import scal

    dane = json.loads((OCENY / "playlisty_dane.json").read_text(encoding="utf-8"))
    potrzebne = {t["track_id"] for lista in dane.values() for t in lista}
    repo = FileAnalysisRepository(PROCESSED)
    widok, _ = scal([repo.get(t) for t in repo.list_track_ids()])
    by_id = {a.track.track_id: a for a in widok if a.track.track_id in potrzebne}

    pliki = []
    for p in MUZ.rglob("*"):
        if p.suffix.lower() in ROZSZERZENIA and not p.name.startswith("._"):
            pliki.append(p)
    print(f"plików audio w ~/Music: {len(pliki)}")
    indeks = {klucz(p.stem): p for p in pliki}
    klucze = list(indeks)

    trafienia = []
    for tid, a in by_id.items():
        raw = str(a.track.source_path or "")
        if not raw.startswith("apple-music:"):
            continue
        t = a.track
        szukane = klucz(f"{t.artist or ''} {t.title or ''}")
        if not szukane:
            continue
        bliskie = difflib.get_close_matches(szukane, klucze, n=1, cutoff=PROG)
        if bliskie:
            trafienia.append((t.artist, t.title, indeks[bliskie[0]],
                              difflib.SequenceMatcher(None, szukane, bliskie[0]).ratio()))

    print(f"strumieni Apple do sprawdzenia: "
          f"{sum(1 for a in by_id.values() if str(a.track.source_path).startswith('apple-music:'))}")
    print(f"możliwych trafień na dysku (do POTWIERDZENIA ręką): {len(trafienia)}\n")
    for art, tyt, p, r in sorted(trafienia, key=lambda x: -x[3])[:25]:
        print(f"  {r:.2f}  {str(art)[:22]:<22} {str(tyt)[:34]:<34} → {p.name[:48]}")
    (TU / "moze_juz_masz.json").write_text(
        json.dumps([{"wykonawca": a, "tytul": t, "plik": str(p), "podobienstwo": r}
                    for a, t, p, r in trafienia], ensure_ascii=False, indent=1),
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
