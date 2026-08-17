"""KROK 1 · rozstrzygnięcie: czy historia Rekordboxa to GRANIE, czy PRZEGLĄDANIE.

Model uczony na korpusie dostaje na historii grania Janka percentyl 0,653,
a na jego nagranych setach 0,583. Ta sama rozbieżność co między walidacją
z 28.07 (0,289) a testem przejść z 01.08 (0,597). Trzeba wiedzieć, czy to
własność zadania, czy zanieczyszczenie danych.

Hipoteza: `DjmdSongHistory` zapisuje ZAŁADOWANIE utworu na deck, nie zagranie.
Ładowanie zdarza się też przy przeglądaniu w słuchawkach, przy sesjach
przygotowawczych i przy sesjach po 151 utworów, które setami nie są.

Test: kolumna `created_at` daje czas załadowania KAŻDEGO wiersza. Odstęp między
kolejnymi załadowaniami mówi wprost, czy poprzedni utwór grał. Set: odstępy
rzędu 2–7 minut. Przeglądanie: sekundy.

Wynik ma odpowiedzieć na jedno pytanie produktowe: czy odfiltrowanie
„przeglądania" z 483 par treningowych podnosi wynik na nagranych setach.
"""

from __future__ import annotations

import json
import pathlib
import sys
import unicodedata as U
from collections import defaultdict

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

MIN_TRACKS = 5
PLAY_LO, PLAY_HI = 90.0, 600.0      # odstęp zgodny z granym utworem (1,5–10 min)
N = lambda s: U.normalize("NFC", str(s))  # noqa: E731


def load_history():
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    db = Rekordbox6Database()
    content = {str(r.ID): (r.FolderPath or "", r.Title or "") for r in
               db.session.query(tables.DjmdContent).all()}
    rows = defaultdict(list)
    for r in (db.session.query(tables.DjmdSongHistory)
              .order_by(tables.DjmdSongHistory.TrackNo).all()):
        rows[str(r.HistoryID)].append((r.TrackNo, str(r.ContentID), r.created_at))
    names = {str(h.ID): (h.Name, h.DateCreated) for h in
             db.session.query(tables.DjmdHistory).all()}
    db.close()
    return content, rows, names


def main() -> int:
    content, rows, names = load_history()
    sessions = {h: sorted(v) for h, v in rows.items() if len(v) >= MIN_TRACKS}
    print(f"sesji z >= {MIN_TRACKS} utworami: {len(sessions)}\n", flush=True)

    stats = []
    for h, v in sessions.items():
        gaps = [(v[i + 1][2] - v[i][2]).total_seconds()
                for i in range(len(v) - 1)
                if v[i + 1][2] and v[i][2]]
        gaps = [g for g in gaps if g >= 0]
        if not gaps:
            continue
        med = float(np.median(gaps))
        share_play = float(np.mean([(PLAY_LO <= g <= PLAY_HI) for g in gaps]))
        stats.append({"h": h, "name": names.get(h, ("?", ""))[0],
                      "date": names.get(h, ("", ""))[1], "n": len(v),
                      "med_gap": med, "share_play": share_play, "gaps": gaps})

    allg = np.concatenate([s["gaps"] for s in stats])
    print("ODSTĘPY MIĘDZY ZAŁADOWANIAMI (wszystkie sesje, sekundy):")
    for q in (10, 25, 50, 75, 90):
        print(f"  percentyl {q:2d}: {np.percentile(allg, q):8.1f} s")
    print(f"  poniżej 30 s : {100*np.mean(allg < 30):5.1f}%   ← na pewno nie zagrany")
    print(f"  poniżej 90 s : {100*np.mean(allg < 90):5.1f}%")
    print(f"  90–600 s     : {100*np.mean((allg >= 90) & (allg <= 600)):5.1f}%   ← zgodne z graniem")
    print(f"  powyżej 600 s: {100*np.mean(allg > 600):5.1f}%   ← przerwa/koniec sesji")

    setlike = [s for s in stats if s["share_play"] >= 0.5]
    browse = [s for s in stats if s["share_play"] < 0.5]
    print(f"\nKLASYFIKACJA SESJI (>=50% odstępów w oknie 90–600 s):")
    print(f"  wyglądające na SET        : {len(setlike):3d} sesji · "
          f"{sum(s['n'] for s in setlike):5d} zagrań")
    print(f"  wyglądające na PRZEGLĄDANIE: {len(browse):3d} sesji · "
          f"{sum(s['n'] for s in browse):5d} zagrań")

    print(f"\n  najdłuższe sesje (n, mediana odstępu, % odstępów 'granych'):")
    for s in sorted(stats, key=lambda x: -x["n"])[:8]:
        tag = "SET" if s["share_play"] >= 0.5 else "przegląd"
        print(f"    {s['n']:4d} utworów · {s['med_gap']:7.1f} s · "
              f"{100*s['share_play']:5.1f}%  {tag:9s} {str(s['name'])[:28]}")

    # ── ile PAR przeżywa filtr na poziomie pary, nie sesji
    kept = tot = 0
    per_sess_kept = defaultdict(int)
    for s in stats:
        v = sorted(sessions[s["h"]])
        for i in range(len(v) - 1):
            if not (v[i + 1][2] and v[i][2]):
                continue
            tot += 1
            g = (v[i + 1][2] - v[i][2]).total_seconds()
            if PLAY_LO <= g <= PLAY_HI and v[i][1] != v[i + 1][1]:
                kept += 1
                per_sess_kept[s["h"]] += 1
    print(f"\nFILTR NA POZIOMIE PARY (odstęp 90–600 s):")
    print(f"  par przed filtrem: {tot}")
    print(f"  par po filtrze   : {kept}  ({100*kept/max(1,tot):.1f}%)")
    print(f"  sesji z >= 3 parami po filtrze: "
          f"{sum(1 for v in per_sess_kept.values() if v >= 3)}")

    out = pathlib.Path(__file__).parent / "krok1_sesje.json"
    out.write_text(json.dumps(
        {"play_lo": PLAY_LO, "play_hi": PLAY_HI,
         "sessions": [{k: (str(v) if k == "date" else v)
                       for k, v in s.items() if k != "gaps"} for s in stats]},
        ensure_ascii=False))
    print(f"\nzapisane: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
