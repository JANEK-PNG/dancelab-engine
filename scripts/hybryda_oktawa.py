"""Czy da się skrócić analizę, nie oddając trafności oktawy.

Pomiar z 2026-08-03 (skrocona_analiza.py) pokazał, że skrócenie utworu do 150 s
kosztuje 1,1 punktu zgodności z Rekordboxem — ale WSZYSTKIE osiem rozjazdów to
błędy oktawy (140 vs 70, 160 vs 120, 130 vs 65), ani jeden nie dotyczy
dziesiętnych. Skrócenie nie psuje precyzji okresu, psuje wybór oktawy.

W rigid_grid te dwie rzeczy są osobnymi krokami o bardzo różnej cenie:
  * dokładny skan  — 151 foldów, to on zjada czas,
  * wybór oktawy   — 3 foldy, tani.
Więc pytanie brzmi: czy można zostawić oktawę na całym utworze, a skrócić tylko
dokładny skan.

PIERWSZE PODEJŚCIE BYŁO ZŁE i zostawiam to zapisane, bo to pouczające. Wstawiłem
_settle_relatives PRZED _refine, czyli rozstrzygałem oktawę na kandydacie
zgrubnym. Zgrubny kandydat jest rozmazany (Daphni: 1,202 zamiast 3,496) i
porównanie oktaw dostaje zły punkt odniesienia — to jest ten sam błąd kolejności,
który zepsuł Daphni przy pierwszej poprawce oktawy. Wynik: 93,0% zamiast 95,3%,
czyli GORZEJ niż zwykłe skrócenie.

Tu jest kolejność poprawna, ta sama co w fit_rigid_grid:
    1. dokładny skan na OKNIE            (tanio)
    2. rozstrzygnięcie oktawy na CAŁYM   (tanio, ale ma pełne dowody)
    3. jeśli oktawa spadła — skan jeszcze raz na oknie

Sędzia niezależny: BPM z Rekordboxa. Kryterium przyjęcia postawione przed
pomiarem: wariant wchodzi tylko wtedy, gdy nie pogarsza zgodności z sędzią.
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
OUT = pathlib.Path("experiments_priv/2026-08-03_hybryda_oktawa")


def library_with_judge(limit: int):
    from pyrekordbox import Rekordbox6Database

    rows = []
    for c in Rekordbox6Database().get_content():
        if not c.FolderPath or not c.BPM:
            continue
        p = pathlib.Path(U.normalize("NFC", c.FolderPath))
        if p.suffix.lower() not in (".aiff", ".aif", ".wav", ".flac", ".mp3", ".m4a"):
            continue
        if p.exists():
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
        return sf.read(tmp, dtype="float32")
    finally:
        pathlib.Path(tmp).unlink(missing_ok=True)


def middle(y: np.ndarray, sr: int, seconds: float) -> np.ndarray:
    half = int(seconds * sr / 2)
    mid = len(y) // 2
    return y[max(0, mid - half): mid + half]


HOP = 128


def hybrid_bpm(y: np.ndarray, sr: int, window_sec: float = 150.0) -> float | None:
    """Dokładność z okna, oktawa z całego utworu.

    Nic tu nie trzeba przepisywać: `_fit_one` już przyjmuje `arbiter`, czyli
    pasmo stopy, którym rozstrzyga oktawę — osobno od materiału, na którym robi
    skan. Ten szew powstał, żeby widok pełnopasmowy sądzić stopą; tutaj używamy
    go po to samo, tylko z drugiej strony: sędzia z CAŁEGO utworu, skan z OKNA.
    Kolejność kroków zostaje wtedy dokładnie ta z produkcji.
    """
    import dancelab.core.rigid_grid as RG

    seg = middle(y, sr, window_sec)
    if seg.size < sr * 8:
        return None
    arbiter = RG._onset_envelope(y, sr, HOP, kick_only=True)      # cały utwór
    fits = [f for f in (RG._fit_one(seg, sr, HOP, True, RG.MUSICAL_TOLERANCE, arbiter),
                        RG._fit_one(seg, sr, HOP, False, RG.MUSICAL_TOLERANCE, arbiter)) if f]
    if not fits:
        return None
    confident = [g for g in fits if g.confident]
    return float(max(confident or fits, key=lambda g: g.contrast).bpm)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--okno", type=float, default=150.0)
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
        if len(y) < sr * 90:
            continue
        rec = {"plik": p.name, "sedzia": judge}

        t = time.time()
        g = fit_rigid_grid(y, sr)
        rec["pelny_czas"] = time.time() - t
        rec["pelny_bpm"] = float(g.bpm) if g else None

        t = time.time()
        g = fit_rigid_grid(middle(y, sr, args.okno), sr)
        rec["okno_czas"] = time.time() - t
        rec["okno_bpm"] = float(g.bpm) if g else None

        t = time.time()
        rec["hybryda_bpm"] = hybrid_bpm(y, sr, args.okno)
        rec["hybryda_czas"] = time.time() - t

        res.append(rec)
        if i % 25 == 0:
            print(f"  {i}/{len(rows)}", flush=True)
            (OUT / "wyniki.json").write_text(json.dumps(res, ensure_ascii=False))
    (OUT / "wyniki.json").write_text(json.dumps(res, ensure_ascii=False))

    def agree(a, b, tol=0.6):
        return a is not None and b is not None and abs(a - b) < tol

    base = float(np.median([r["pelny_czas"] for r in res]))
    print(f"\nzmierzone na {len(res)} płytach\n")
    print(f"{'wariant':>10} │ {'zgodny z RB':>12} │ {'czas/utwór':>11} │ {'przyspieszenie':>14}")
    print("─" * 58)
    for label in ("pelny", "okno", "hybryda"):
        ok = sum(agree(r[f"{label}_bpm"], r["sedzia"]) for r in res) / len(res)
        t = float(np.median([r[f"{label}_czas"] for r in res]))
        print(f"{label:>10} │ {ok * 100:>11.1f}% │ {t:>10.2f}s │ {base / max(t, 1e-6):>13.1f}×")

    print("\npłyty, na których hybryda różni się od pełnej:")
    for r in [r for r in res if not agree(r["hybryda_bpm"], r["pelny_bpm"])][:10]:
        w = ("RB z pełną" if agree(r["pelny_bpm"], r["sedzia"])
             else "RB z hybrydą" if agree(r["hybryda_bpm"], r["sedzia"]) else "RB z żadną")
        print(f"  {r['plik'][:38]:38s} pełna {r['pelny_bpm']} · hyb {r['hybryda_bpm']} "
              f"· RB {r['sedzia']}  → {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
