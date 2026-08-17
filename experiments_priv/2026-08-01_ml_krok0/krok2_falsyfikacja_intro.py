"""KROK 2 · test falsyfikujący: czy reguła wejścia mówi o WYBORZE, czy o INTRACH.

Powód. Punkty wejścia Janka, przeliczone z zegara miksu na zegar utworu:
18 z 21 leży poniżej 15 sekundy, 17 z 21 poniżej piątej, mediana −0,1 s.
Czyli on w tych szwach nie WYBIERA miejsca w utworze — puszcza płytę od góry.

Skutek dla pomiaru z 30.07. „Perkusja w górę + bas w dół w 71% wejść wobec 18%
losowych momentów" porównywało 21 okien, z których 18 to były PIERWSZE 15 SEKUND
utworu, przeciwko oknom rozrzuconym po całym utworze. Jeżeli intra w muzyce
tanecznej z zasady opierają się na perkusji i trzymają bas z tyłu, to ta liczba
opisuje budowę gatunku, a nie gust Janka — i nie wolno jej używać jako reguły
wyboru.

Test. Ta sama miara, na całej bibliotece, BEZ udziału Janka: dla każdego utworu
pierwsze 15 sekund przeciwko pięciu oknom rozrzuconym po utworze. Jeśli intro
wygrywa w okolicach 71%, hipoteza „to są intra, nie wybory" się potwierdza.

Miara wzięta z produkcyjnego `render_set.entry_point` (podział pasm 200 Hz),
nie ze stemów — bo to jest ta, która realnie stawia cue, i nie wymaga Demucsa,
więc test idzie po całej bibliotece zamiast po trzydziestu utworach z cache'u.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from dancelab.storage.repositories import FileAnalysisRepository  # noqa: E402

PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"
SR = 44100
WINDOW_SEC = 15.0
N_CONTROLS = 5
SEED = 20260801
LOW_HZ = 200.0


def score_windows(path: str) -> tuple[float, list[float]] | None:
    """(wynik intra, wyniki okien kontrolnych) — wynik jak w entry_point."""
    try:
        y, sr = sf.read(path, dtype="float32", always_2d=True)
    except Exception:
        return None
    y = y.mean(axis=1)
    if sr != SR:
        n = int(len(y) * SR / sr)
        y = np.interp(np.linspace(0, len(y) - 1, n), np.arange(len(y)), y).astype(np.float32)
    span = len(y) / SR
    if span < 90:
        return None

    sos = butter(4, LOW_HZ / (SR / 2), btype="lowpass", output="sos")
    low = sosfiltfilt(sos, y).astype(np.float32)
    mid = (y - low).astype(np.float32)
    ref_lo = float((low ** 2).mean())
    ref_md = float((mid ** 2).mean())
    if ref_lo <= 0 or ref_md <= 0:
        return None

    def sc(t0: float) -> float | None:
        a, b = int(t0 * SR), int((t0 + WINDOW_SEC) * SR)
        if b > len(y) or a < 0:
            return None
        md = float((mid[a:b] ** 2).mean()) / ref_md
        lo = float((low[a:b] ** 2).mean()) / ref_lo
        if md <= 0.33:          # ta sama podłoga „musi grać" co w produkcji
            return None
        return md - lo

    intro = sc(0.0)
    if intro is None:
        return None
    rng = np.random.default_rng(abs(hash(path)) % (2 ** 32))
    usable = span - WINDOW_SEC
    cand = list(rng.uniform(0.10 * usable, 0.95 * usable, N_CONTROLS * 4))
    ctrl = []
    for t in cand:
        if len(ctrl) >= N_CONTROLS:
            break
        s = sc(float(t))
        if s is not None:
            ctrl.append(s)
    if len(ctrl) < 3:
        return None
    return intro, ctrl


def main() -> int:
    repo = FileAnalysisRepository(PROCESSED)
    paths = []
    for tid in repo.list_track_ids():
        try:
            p = repo.get(tid).track.source_path
        except Exception:
            continue
        if pathlib.Path(p).exists():
            paths.append(p)
    print(f"biblioteka: {len(paths)} utworów z plikiem\n", flush=True)

    wins = fails = 0
    margins = []
    for i, p in enumerate(paths, 1):
        r = score_windows(p)
        if r is None:
            fails += 1
            continue
        intro, ctrl = r
        wins += intro > max(ctrl)
        margins.append(intro - float(np.mean(ctrl)))
        if i % 40 == 0:
            print(f"  … {i}/{len(paths)}", flush=True)

    n = len(margins)
    if not n:
        print("brak danych")
        return 1

    rate = wins / n
    print("\n" + "═" * 68)
    print("WYNIK · czy intro wygrywa z oknami z wnętrza utworu")
    print("═" * 68)
    print(f"\n  utworów policzonych: {n}   (pominiętych: {fails})")
    print(f"  intro najlepsze z {N_CONTROLS + 1} okien: {wins} = {rate*100:.1f}%")
    print(f"  losowo byłoby:                       {100/(N_CONTROLS+1):.1f}%")
    print(f"  przewaga intra nad średnią kontrolą: {np.mean(margins):+.3f} "
          f"(mediana {np.median(margins):+.3f})")
    print(f"  utworów, gdzie intro jest POWYŻEJ średniej kontroli: "
          f"{100*np.mean(np.array(margins) > 0):.1f}%")
    print("\n  ODCZYT:")
    print(f"  Jeśli ta liczba jest bliska 71%, pomiar z 30.07 opisuje BUDOWĘ INTR,")
    print(f"  a nie wybory Janka — bo 18 z jego 21 wejść to pierwsze sekundy utworu.")
    print(f"  Jeśli jest bliska {100/(N_CONTROLS+1):.0f}%, reguła niesie informację o wyborze.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
