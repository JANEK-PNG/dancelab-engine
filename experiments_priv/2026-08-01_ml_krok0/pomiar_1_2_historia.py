"""KROK 0 · pomiary 1 i 2 — ile danych treningowych Janek MA NAPRAWDĘ.

Rekomendacja z `RnD-DanceLab-Pro/dancelab-pro-ml/05` mówi: zanim powstanie
pierwsza linijka warstwy uczącej się, trzeba znać dwie liczby. Nie oszacowania —
pomiary. Ten skrypt liczy obie i wypisuje je jako LEJEK, żeby było widać,
na którym filtrze ile odpada.

  POMIAR 1 · ile realnych par następstwa zostaje w historii z Rekordboxa
             po odfiltrowaniu przeładowań, braków i sesji za krótkich.
             Liczba 2481 z 28.07 to ZAGRANIA, nie użyteczne pary.

  POMIAR 2 · ile utworów z tej historii ma KOMPLET cech (siatka bitów,
             tonacja, wektor CLAP, analiza, stemy). Przykład bez cech
             nie jest przykładem.

Baza otwierana TYLKO DO ODCZYTU. Nic nie zapisuje, nic nie kasuje.
Zamknij Rekordbox przed uruchomieniem — inaczej część wierszy może być
w trakcie zapisu.

Uczciwość zakresu — przeczytaj przed cytowaniem liczby:
  * `DjmdSongHistory` zapisuje ZAŁADOWANIE utworu na deck, nie fakt zagrania go
    do końca. Para A→B to „załadował B po A", a nie „zmiksował B po A".
  * Kolejność bierzemy z `TrackNo`, tak samo jak `validate_on_my_history.py`.
  * Dopasowanie do plików na dysku po pełnej ścieżce (NFC). Przy
    niejednoznaczności skrypt LICZY ją osobno i NIE zgaduje.
"""

from __future__ import annotations

import json
import pathlib
import statistics as st
import unicodedata as U
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]

MIN_TRACKS = 5  # tak samo jak validate_on_my_history.py — nie zmieniać bez powodu

GRIDS = ROOT / "experiments_priv/_cache/rigid_grids.json"
EMBEDS = ROOT / "data/reports/library_embeddings.json"
STEMS = ROOT / "experiments_priv/_cache/stems"
ANALYSES = [
    ROOT / "experiments_priv/2026-07-30_rebuild/processed",
    ROOT / "data/processed",
]

N = lambda s: U.normalize("NFC", str(s))  # noqa: E731


def bar(label: str, n: int, total: int, note: str = "") -> None:
    pct = 100.0 * n / total if total else 0.0
    print(f"  {label:<52} {n:6d}  ({pct:5.1f}%) {note}")


# ─────────────────────────────────────────────────────────────── POMIAR 1

def pomiar_1():
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    db = Rekordbox6Database()

    keys = {k.ID: k.ScaleName for k in db.session.query(tables.DjmdKey).all()}
    content = {}
    for row in db.session.query(tables.DjmdContent).all():
        bpm = float(row.BPM or 0)
        if bpm > 300:  # Rekordbox trzyma BPM ×100
            bpm /= 100.0
        content[str(row.ID)] = {
            "bpm": bpm,
            "camelot": keys.get(row.KeyID),
            "folder": row.FolderPath,
            "title": row.Title,
        }

    plays = defaultdict(list)
    for row in (db.session.query(tables.DjmdSongHistory)
                .order_by(tables.DjmdSongHistory.TrackNo).all()):
        plays[row.HistoryID].append(str(row.ContentID))
    names = {h.ID: h.Name for h in db.session.query(tables.DjmdHistory).all()}
    db.close()

    total_sessions = len(plays)
    total_plays = sum(len(v) for v in plays.values())

    print("═" * 78)
    print("POMIAR 1 · LEJEK: od zagrań do użytecznych par treningowych")
    print("═" * 78)
    print(f"\n  sesji w historii: {total_sessions}   ·   zagrań łącznie: {total_plays}\n")

    lens = sorted(len(v) for v in plays.values())
    print(f"  długość sesji: mediana {st.median(lens):.0f} · "
          f"kwartyle {lens[len(lens)//4]}–{lens[3*len(lens)//4]} · "
          f"min {lens[0]} · max {lens[-1]}")
    print(f"  sesji krótszych niż {MIN_TRACKS} utworów: "
          f"{sum(1 for x in lens if x < MIN_TRACKS)}\n")

    kept = {h: ids for h, ids in plays.items() if len(ids) >= MIN_TRACKS}

    raw_pairs = []
    for hid, ids in kept.items():
        for a, b in zip(ids, ids[1:]):
            raw_pairs.append((hid, a, b))

    base = len(raw_pairs)
    print(f"  {'pary kolejne w sesjach >= ' + str(MIN_TRACKS) + ' utworów':<52} {base:6d}  (100.0%)  ← baza")

    step = [p for p in raw_pairs if p[1] != p[2]]
    bar("minus przeładowania tego samego utworu (A == B)", len(step), base)

    step = [p for p in step if p[1] in content and p[2] in content]
    bar("minus utwory nieistniejące już w kolekcji", len(step), base)

    step_bpm = [p for p in step
                if content[p[1]]["bpm"] > 0 and content[p[2]]["bpm"] > 0]
    bar("minus brak BPM po którejkolwiek stronie", len(step_bpm), base)

    step_key = [p for p in step_bpm
                if content[p[1]]["camelot"] and content[p[2]]["camelot"]]
    bar("minus brak tonacji po którejkolwiek stronie", len(step_key), base)

    usable = step_key
    print()
    print(f"  ► UŻYTECZNE PARY (BPM + tonacja po obu stronach): {len(usable)}")

    uniq_pairs = {(a, b) for _, a, b in usable}
    dup = len(usable) - len(uniq_pairs)
    print(f"  ► unikalnych par A→B: {len(uniq_pairs)}   "
          f"(powtórzeń: {dup} — ta sama para grana wielokrotnie)")

    tracks = {t for _, a, b in usable for t in (a, b)}
    print(f"  ► unikalnych utworów w tych parach: {len(tracks)}")

    sess_used = {h for h, _, _ in usable}
    print(f"  ► sesji, które cokolwiek wniosły: {len(sess_used)}")

    # Ile razy ten sam utwór wraca — to jest miara ryzyka wycieku przez utwór.
    freq = Counter(t for _, a, b in usable for t in (a, b))
    top = freq.most_common(5)
    once = sum(1 for v in freq.values() if v == 1)
    print(f"\n  ryzyko wycieku przez utwór: {once} utworów pojawia się raz, "
          f"{len(freq) - once} wielokrotnie")
    print(f"  najczęstsze: " + " · ".join(
        f"{content[t]['title'][:26]} ×{c}" for t, c in top))

    # Rozmiar najmniejszego sensownego podziału po sesjach.
    per_sess = Counter(h for h, _, _ in usable)
    ps = sorted(per_sess.values())
    if ps:
        print(f"  par na sesję: mediana {st.median(ps):.0f} · min {ps[0]} · max {ps[-1]}")

    print("\n  UWAGA: to są ZAŁADOWANIA na deck, nie potwierdzone zagrania.")
    print("  Górna granica danych treningowych, nie ich rzeczywista liczba.")

    return usable, tracks, content, names


# ─────────────────────────────────────────────────────────────── POMIAR 2

def _load_grids():
    if not GRIDS.exists():
        return {}
    raw = json.loads(GRIDS.read_text())
    return {N(k): v for k, v in raw.items()}


def _load_embeds():
    if not EMBEDS.exists():
        return {}, ""
    d = json.loads(EMBEDS.read_text())
    root = d.get("library_root", "")
    return {N(k): v for k, v in d.get("tracks", {}).items()}, root


def _load_analyses():
    """track_id -> source_path, dla wszystkich repozytoriów analiz."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from dancelab.storage.repositories import FileAnalysisRepository

    by_path = {}
    for d in ANALYSES:
        if not d.exists():
            continue
        repo = FileAnalysisRepository(d)
        for tid in repo.list_track_ids():
            try:
                a = repo.get(tid)
            except Exception:
                continue
            by_path[N(a.track.source_path)] = (tid, a)
    return by_path


def pomiar_2(tracks, content):
    grids = _load_grids()
    embeds, lib_root = _load_embeds()
    analyses = _load_analyses()
    stem_ids = {p.name for p in STEMS.iterdir()} if STEMS.exists() else set()

    print()
    print("═" * 78)
    print("POMIAR 2 · ile utworów z historii ma KOMPLET cech")
    print("═" * 78)
    print(f"\n  źródła: siatki {len(grids)} · CLAP {len(embeds)} "
          f"(root: {lib_root}) · analizy {len(analyses)} · stemy {len(stem_ids)}\n")

    total = len(tracks)
    have = Counter()
    ambiguous = 0
    detail = []

    # Odwrotny indeks po nazwie pliku — TYLKO do policzenia niejednoznaczności.
    by_name = defaultdict(list)
    for p in analyses:
        by_name[pathlib.Path(p).name].append(p)

    for cid in tracks:
        c = content[cid]
        folder = c.get("folder") or ""
        path = N(folder)
        name = pathlib.Path(path).name

        on_disk = bool(path) and pathlib.Path(path).exists()

        g = grids.get(path)
        grid_ok = bool(g) and float(g.get("contrast", 0)) >= 2.2

        rel = path[len(N(lib_root)):].lstrip("/") if lib_root else ""
        clap = rel in embeds

        rec = analyses.get(path)
        if rec is None and len(by_name.get(name, [])) > 1:
            ambiguous += 1
        anal_ok = rec is not None
        stems_ok = anal_ok and rec[0] in stem_ids

        have["na dysku"] += on_disk
        have["siatka bitów (contrast >= 2.2)"] += grid_ok
        have["wektor CLAP"] += clap
        have["analiza DanceLaba"] += anal_ok
        have["stemy"] += stems_ok
        have["KOMPLET (siatka + CLAP + analiza)"] += grid_ok and clap and anal_ok
        have["KOMPLET + stemy"] += grid_ok and clap and anal_ok and stems_ok

        detail.append((cid, on_disk, grid_ok, clap, anal_ok, stems_ok))

    print(f"  utworów w użytecznych parach: {total}\n")
    for k in ["na dysku", "siatka bitów (contrast >= 2.2)", "wektor CLAP",
              "analiza DanceLaba", "stemy",
              "KOMPLET (siatka + CLAP + analiza)", "KOMPLET + stemy"]:
        bar(k, have[k], total)

    if ambiguous:
        print(f"\n  ⚠ {ambiguous} utworów NIE dopasowano po ścieżce, a ich nazwa "
              f"pliku występuje w bibliotece wielokrotnie — NIE zgadywano.")

    return detail, have, total


# ─────────────────────────────────────────────────────────────── PARY z cechami

def pary_z_cechami(usable, detail):
    ok = {cid for cid, _on, g, c, a, _s in detail if g and c and a}
    ok_stems = {cid for cid, _on, g, c, a, s in detail if g and c and a and s}

    full = [p for p in usable if p[1] in ok and p[2] in ok]
    full_s = [p for p in usable if p[1] in ok_stems and p[2] in ok_stems]

    print()
    print("═" * 78)
    print("WYNIK ŁĄCZNY · ile par nadaje się do uczenia")
    print("═" * 78)
    print()
    base = len(usable)
    bar("pary z BPM + tonacją (POMIAR 1)", base, base)
    bar("pary, gdzie OBA utwory mają komplet cech", len(full), base)
    bar("pary, gdzie OBA mają komplet + stemy", len(full_s), base)

    sess = len({h for h, _, _ in full})
    print(f"\n  sesji w zbiorze z kompletem cech: {sess}")
    print(f"  → przy GroupKFold po sesjach: {min(5, sess)} foldów wykonalne"
          if sess >= 2 else "  → za mało sesji na podział po sesjach")

    print()
    print("  SUFIT PARAMETRÓW (reguła 10–50 przykładów na parametr, muzyka = 50):")
    for label, n in [("wszystkie użyteczne", base),
                     ("z kompletem cech", len(full)),
                     ("z kompletem + stemy", len(full_s))]:
        print(f"    {label:<26} {n:5d} par  →  uczciwie {n // 50:3d}–{n // 10:3d} parametrów")

    return full, full_s


def main() -> int:
    usable, tracks, content, _names = pomiar_1()
    detail, _have, _total = pomiar_2(tracks, content)
    pary_z_cechami(usable, detail)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
