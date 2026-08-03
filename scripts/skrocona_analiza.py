"""Czy sztywna siatka potrzebuje całego utworu — sędzią jest Rekordbox.

Skan biblioteki 1837 utworów to dziś 52 minuty na sześciu wątkach, a wąskim
gardłem jest dokładny skan tempa chodzący po CAŁYM nagraniu (mediana 8,35 s
na utwór; na 50-minutowym pliku 131 s). Próbka sześciu płyt pokazała 2,3×
przyspieszenia przy oknie 150 s i jeden rozjazd — ale na naszym własnym stemie,
nie na muzyce.

Sześć płyt to za mało, żeby to wpiąć. Przy poprzedniej poprawce oktawy trzy
utwory wyszły dobrze, a czwarty się zepsuł — dokładnie na takiej próbce.
Więc mierzymy na kilkuset płytach i rozstrzyga NIEZALEŻNY sędzia: BPM
z Rekordboxa, którego nie liczyliśmy my.

Trzy warianty okna, każdy porównany osobno:
  * pełny utwór (dziś),
  * 150 s ze środka,
  * 240 s ze środka.

Dla każdego: zgodność z Rekordboxem, zgodność z pełną analizą, czas. Wariant
przyjmujemy tylko wtedy, gdy NIE POGARSZA zgodności z sędzią — samo
przyspieszenie nie wystarcza.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import tempfile
import time
import unicodedata as U

import numpy as np
import soundfile as sf

SR = 22050
OUT = pathlib.Path("experiments_priv/2026-08-03_skrocona_analiza")
N = lambda s: U.normalize("NFC", str(s)).lower()                   # noqa: E731


def library_with_judge(limit: int):
    """Płyty, dla których Rekordbox ma własne BPM — tylko takie są rozstrzygalne."""
    from pyrekordbox import Rekordbox6Database

    rows = []
    for c in Rekordbox6Database().get_content():
        if not c.FolderPath or not c.BPM:
            continue
        p = pathlib.Path(U.normalize("NFC", c.FolderPath))
        if p.suffix.lower() not in (".aiff", ".aif", ".wav", ".flac", ".mp3", ".m4a"):
            continue
        if not p.exists():
            continue
        rows.append((p, c.BPM / 100.0))
    rng = np.random.default_rng(17)
    if len(rows) > limit:
        rows = [rows[i] for i in rng.choice(len(rows), limit, replace=False)]
    return rows


def decode(path: pathlib.Path):
    tmp = tempfile.mktemp(suffix=".wav")
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path),
                        "-ac", "1", "-ar", str(SR), tmp],
                       check=True, capture_output=True, timeout=240)
        y, sr = sf.read(tmp, dtype="float32")
    finally:
        pathlib.Path(tmp).unlink(missing_ok=True)
    return y, sr


def middle(y: np.ndarray, sr: int, seconds: float) -> np.ndarray:
    half = int(seconds * sr / 2)
    mid = len(y) // 2
    return y[max(0, mid - half): mid + half]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=250)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    from dancelab.core.rigid_grid import fit_rigid_grid

    rows = library_with_judge(args.n)
    print(f"płyt z niezależnym BPM z Rekordboxa: {len(rows)}", flush=True)

    res = []
    for i, (p, judge) in enumerate(rows, 1):
        try:
            y, sr = decode(p)
        except Exception:                                          # noqa: BLE001
            continue
        if len(y) < sr * 60:
            continue
        rec = {"plik": p.name, "sedzia": judge, "min": len(y) / sr / 60}
        for label, sec in (("pelny", None), ("150s", 150.0), ("240s", 240.0)):
            seg = y if sec is None else middle(y, sr, sec)
            t = time.time()
            g = fit_rigid_grid(seg, sr)
            rec[f"{label}_czas"] = time.time() - t
            rec[f"{label}_bpm"] = float(g.bpm) if g else None
            rec[f"{label}_pewny"] = bool(g.confident) if g else False
        res.append(rec)
        if i % 25 == 0:
            print(f"  {i}/{len(rows)}", flush=True)
            (OUT / "wyniki.json").write_text(json.dumps(res, ensure_ascii=False))
    (OUT / "wyniki.json").write_text(json.dumps(res, ensure_ascii=False))

    def agree(a, b, tol=0.6):
        return a is not None and b is not None and abs(a - b) < tol

    print(f"\nzmierzone na {len(res)} płytach "
          f"(mediana długości {np.median([r['min'] for r in res]):.1f} min)\n")
    print(f"{'wariant':>10} │ {'zgodny z RB':>12} │ {'zgodny z pełną':>15} │ "
          f"{'czas/utwór':>11} │ {'przyspieszenie':>14}")
    print("─" * 76)
    base_t = float(np.median([r["pelny_czas"] for r in res]))
    for label in ("pelny", "150s", "240s"):
        b = [r[f"{label}_bpm"] for r in res]
        rb = sum(agree(x, r["sedzia"]) for x, r in zip(b, res)) / len(res)
        vs = sum(agree(x, r["pelny_bpm"]) for x, r in zip(b, res)) / len(res)
        t = float(np.median([r[f"{label}_czas"] for r in res]))
        print(f"{label:>10} │ {rb * 100:>11.1f}% │ {vs * 100:>14.1f}% │ "
              f"{t:>10.2f}s │ {base_t / max(t, 1e-6):>13.1f}×")

    print("\npłyty, na których skrócenie do 150 s zmienia odpowiedź:")
    bad = [r for r in res if not agree(r["150s_bpm"], r["pelny_bpm"])]
    for r in bad[:8]:
        w = "RB zgadza się z pełną" if agree(r["pelny_bpm"], r["sedzia"]) else \
            "RB zgadza się ze skróconą" if agree(r["150s_bpm"], r["sedzia"]) else "RB z żadną"
        print(f"  {r['plik'][:40]:40s} pełna {r['pelny_bpm']} · 150s {r['150s_bpm']} "
              f"· RB {r['sedzia']}  → {w}")
    print(f"\n  rozjazdów: {len(bad)} z {len(res)} ({len(bad) / len(res) * 100:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
