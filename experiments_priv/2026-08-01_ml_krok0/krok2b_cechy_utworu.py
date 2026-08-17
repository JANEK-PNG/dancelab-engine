"""KROK 2b · cechy utworu, których model rankingu nie widzi.

Raport z 01.08: „w score NIE MA niczego, co zmierzyliśmy o Janku". Krok 3 dołożył
brzmienie (CLAP) i kontekst setu, ale nadal nie ma nic z domeny szwu.

Dwie rzeczy dają się policzyć **dla pojedynczego utworu, bez partnera** — więc
wchodzą do rankingu jako cecha kandydata, a nie wymagają pary:

  entry_score  Czy początek tej płyty da się wprowadzić: (środek/średnia) −
               (dół/średnia) w pierwszych 15 sekundach. Ta sama miara, którą
               liczy produkcyjny `render_set.entry_point`. Krok 2 pokazał,
               że Janek w 18 z 21 szwów puszcza płytę OD POCZĄTKU — więc
               „jak brzmi początek" jest własnością wyboru, nie pozycji cue.

  runway_in    Ile bitów płyta trzyma albo buduje od swojego startu —
               `decision.transition_length.stability_runway_beats(side=incoming)`,
               reguła rzemieślnicza Janka z 28.07. Mówi, ile blendu ta płyta
               UNIESIE. Zwraca None, gdy nie ma podstaw, i tego nie podstawiamy.

Czego tu NIE MA i dlaczego: `runway_out` strony wychodzącej jest stałe w obrębie
jednego zapytania (A jest jedno), więc na kolejność kandydatów nie wpływa —
liczenie go byłoby ozdobnikiem. Pełna wykonalność szwu wymaga polityki cue
MIX OUT, której jeszcze nie ma.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from grid_cache import grid_for                                       # noqa: E402
from dancelab.decision.transition_length import stability_runway_beats  # noqa: E402
from dancelab.storage.repositories import FileAnalysisRepository        # noqa: E402

PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"
OUT = pathlib.Path(__file__).parent / "krok2b_cechy.json"
SR = 44100
WINDOW_SEC = 15.0
LOW_HZ = 200.0


def entry_score(path: str) -> float | None:
    """Wynik początku utworu: środek w górę, dół w dół, względem własnej średniej."""
    try:
        y, sr = sf.read(path, dtype="float32", always_2d=True)
    except Exception:
        return None
    y = y.mean(axis=1)
    if sr != SR:
        n = int(len(y) * SR / sr)
        y = np.interp(np.linspace(0, len(y) - 1, n), np.arange(len(y)), y).astype(np.float32)
    if len(y) < int(SR * (WINDOW_SEC + 30)):
        return None
    sos = butter(4, LOW_HZ / (SR / 2), btype="lowpass", output="sos")
    low = sosfiltfilt(sos, y).astype(np.float32)
    mid = (y - low).astype(np.float32)
    ref_lo, ref_md = float((low ** 2).mean()), float((mid ** 2).mean())
    if ref_lo <= 0 or ref_md <= 0:
        return None
    b = int(WINDOW_SEC * SR)
    md = float((mid[:b] ** 2).mean()) / ref_md
    lo = float((low[:b] ** 2).mean()) / ref_lo
    return float(md - lo)


def main() -> int:
    repo = FileAnalysisRepository(PROCESSED)
    ids = repo.list_track_ids()
    out = {}
    miss_entry = miss_runway = 0

    for i, tid in enumerate(ids, 1):
        try:
            a = repo.get(tid)
        except Exception:
            continue
        path = a.track.source_path
        if not pathlib.Path(path).exists():
            continue

        g = grid_for(path)
        if g:
            a.track.bpm_estimate = g["bpm"]

        es = entry_score(path)
        if es is None:
            miss_entry += 1

        # cue MIX IN = pierwszy bit siatki, bo tam Janek realnie wchodzi (18 z 21)
        cue = float(g["first"]) if g else 0.0
        rw, why = stability_runway_beats(a, cue, side="incoming")
        if rw is None:
            miss_runway += 1

        out[tid] = {"entry_score": es, "runway_in": rw,
                    "grid_ok": bool(g), "why": why}
        if i % 40 == 0:
            print(f"  … {i}/{len(ids)}", flush=True)

    have_e = [v["entry_score"] for v in out.values() if v["entry_score"] is not None]
    have_r = [v["runway_in"] for v in out.values() if v["runway_in"] is not None]
    print("\n" + "═" * 60)
    print(f"  utworów: {len(out)}")
    print(f"  entry_score policzony: {len(have_e)}  (brak: {miss_entry})")
    if have_e:
        print(f"    mediana {np.median(have_e):+.3f} · "
              f"kwartyle {np.percentile(have_e,25):+.3f} … {np.percentile(have_e,75):+.3f}")
    print(f"  runway_in policzony:   {len(have_r)}  (brak: {miss_runway})")
    if have_r:
        print(f"    mediana {np.median(have_r):.0f} bitów · "
              f"kwartyle {np.percentile(have_r,25):.0f} … {np.percentile(have_r,75):.0f}")
    OUT.write_text(json.dumps(out, ensure_ascii=False))
    print(f"\n  zapisane: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
