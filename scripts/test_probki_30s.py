"""Czy 30-sekundowa próbka wystarczy, żeby ocenić utwór, którego nie mamy.

Pomysł Janka: Rekordbox jest wpięty w Apple Music, więc DJ może tam grać
utwory ze streamingu. Gdybyśmy podpięli darmowe API iTunes, moglibyśmy
SUGEROWAĆ płyty, których DJ nie ma na dysku — z podglądem i linkiem.

Cała funkcja stoi albo upada na jednym pytaniu: silnik potrzebuje BPM, tonacji
i odcisku brzmienia, a z sieci dostajemy WYŁĄCZNIE 30-sekundową próbkę
(`previewUrl`). Więc mierzymy wprost: czy analiza z 30 s daje tę samą
odpowiedź co analiza z całego pliku.

Sędzia jak zawsze niezależny — BPM z Rekordboxa. Dodatkowo porównujemy
tonację i odcisk brzmienia (kosinus między wektorem z próbki a z całości),
bo wszystkie trzy są potrzebne do scorowania kandydata.

Próbka brana ze ŚRODKA utworu — Apple też tak robi, bo tam jest refren.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import tempfile
import unicodedata as U

import numpy as np
import soundfile as sf

SR = 22050
N = lambda s: U.normalize("NFC", str(s)).lower()                   # noqa: E731


def library(limit: int):
    from pyrekordbox import Rekordbox6Database

    rows = []
    for c in Rekordbox6Database().get_content():
        if not c.FolderPath or not c.BPM:
            continue
        p = pathlib.Path(U.normalize("NFC", c.FolderPath))
        if p.suffix.lower() in (".aiff", ".aif", ".wav", ".flac", ".mp3") and p.exists():
            rows.append((p, c.BPM / 100.0))
    rng = np.random.default_rng(31)
    return [rows[i] for i in rng.choice(len(rows), min(limit, len(rows)), replace=False)]


def decode(path: pathlib.Path):
    tmp = tempfile.mktemp(suffix=".wav")
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path),
                        "-ac", "1", "-ar", str(SR), tmp],
                       check=True, capture_output=True, timeout=240)
        return sf.read(tmp, dtype="float32")
    finally:
        pathlib.Path(tmp).unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    args = ap.parse_args()

    from dancelab.core.rigid_grid import fit_rigid_grid
    from dancelab.features.key import estimate_key

    rows = library(args.n)
    print(f"płyt do sprawdzenia: {len(rows)}\n", flush=True)

    bpm_ok = key_ok = grid_conf = 0
    used = 0
    diffs = []
    for i, (p, judge) in enumerate(rows, 1):
        try:
            y, sr = decode(p)
        except Exception:                                          # noqa: BLE001
            continue
        if len(y) < sr * 90:
            continue
        used += 1
        mid = len(y) // 2
        half = int(15 * sr)                     # 30 s ze środka, jak Apple
        clip = y[mid - half: mid + half]

        gf, gc = fit_rigid_grid(y, sr), fit_rigid_grid(clip, sr)
        kf, kc = estimate_key(y, sr)[1], estimate_key(clip, sr)[1]

        bf = gf.bpm if gf else None
        bc = gc.bpm if gc else None
        if bc is not None and gc.confident:
            grid_conf += 1
        near_judge = bc is not None and abs(bc - judge) < 0.6
        bpm_ok += near_judge
        key_ok += (kf is not None and kf == kc)
        if bf and bc:
            diffs.append(abs(bf - bc))
        if i <= 8:
            print(f"  {p.stem[:34]:34s} pełny {str(bf):>7s} · 30 s {str(bc):>7s} "
                  f"· RB {judge:6.2f} · tonacja {kf}/{kc}", flush=True)

    print(f"\nzmierzone na {used} płytach:")
    print(f"  BPM z 30 s zgodne z Rekordboxem : {bpm_ok / used * 100:5.1f}%")
    print(f"  tonacja z 30 s = tonacja z całości: {key_ok / used * 100:5.1f}%")
    print(f"  siatka z 30 s uznana za pewną    : {grid_conf / used * 100:5.1f}%")
    if diffs:
        print(f"  mediana różnicy BPM (pełny vs 30 s): {np.median(diffs):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
