"""Play the DJ's own seams back at him: same two records, my hands.

An order is a choice; a seam is a performance. Reproducing a set means making the
joins, so each measured seam is rebuilt from the atlas — where the incoming record
came in, how long the two ran together, whether its bass was held — and rendered
next to the DJ's own recording of that same moment.

Two numbers per seam are worth more than the audio. The measured values say what
he did; the rule-derived values say what the engine would have done knowing only
the general profile. Printing both is the only part of this that predicts
anything — the rebuilt audio only shows the join can be executed once it is known.
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import soundfile as sf

import seam_decompose as S
from dancelab.preview.transition_simulation import (
    TRANSITION_DURATION_OPTIONS,
    render_transition_preview,
)

MIX_BPM = 136.0
LEAD_BEATS = 16         # a bar or four of the outgoing record alone, on the grid


def grid(analysis: dict) -> tuple[float, float, float] | None:
    """Beat period, first downbeat, and bar length — extended past the analysed span.

    The period comes from a least-squares fit over every beat, never from the
    median gap: beat times are rounded to the analysis frame, and the rounding
    accumulates into tens of milliseconds across a phrase. Beyond the analysed
    coverage the grid is continued arithmetically rather than abandoned, because
    a cue lands wherever the DJ put it, which is regularly past that point.
    """
    bg = analysis.get("beatgrid") or {}
    beats = np.asarray(bg.get("beat_times_sec") or [], dtype=float)
    downs = np.asarray(bg.get("downbeats_sec") or [], dtype=float)
    if beats.size < 8 or not bg.get("reliable"):
        return None
    n = np.arange(beats.size)
    period, first = np.polyfit(n, beats, 1)
    if not np.isfinite(period) or period <= 0.1:
        return None
    bar = 4.0 * period
    origin = float(downs[0]) if downs.size else float(first)
    return float(period), origin, bar


def snap(seconds: float, g: tuple[float, float, float], to_bar: bool = True) -> float:
    """Move a cue onto the nearest beat, or onto the nearest bar line."""
    period, origin, bar = g
    step = bar if to_bar else period
    return origin + round((seconds - origin) / step) * step


def fold(bpm: float, target: float, measured_rate: float) -> float:
    """Put a detected BPM in the octave the record was actually played in.

    Beat trackers routinely land an octave out — one record in this set came back
    at half speed, which would have rendered the whole seam at 89 BPM. The
    alignment already knows how fast the record ran relative to the mix, so the
    octave that agrees with it is the right one; nothing here trusts the detector
    over the measurement.
    """
    k = target / max(bpm * measured_rate, 1e-9)
    power = 2.0 ** round(np.log2(max(k, 1e-9)))
    return bpm * power


def deck_tempo(bpm: float, measured_rate: float, anchor: float = MIX_BPM) -> float:
    """What this record was actually running at, in the octave that fits the mix.

    Not asked of a beat tracker on a slice of the mix: run on a minute of a blend
    it answered 129 and 132 where the set holds 136, and a target that wrong makes
    every rate wrong with it. The alignment already measured how fast the record
    played, so the tempo is its own BPM times that rate — with only the octave
    left to settle, and the mix's known tempo settles it.
    """
    played = bpm * measured_rate
    power = 2.0 ** round(np.log2(max(anchor / max(played, 1e-9), 1e-9)))
    return played * power


def snap_beats(seconds: float) -> int:
    """Nearest renderable phrase length, never longer than the seam actually ran."""
    beats = seconds * MIX_BPM / 60.0
    usable = [b for b in TRANSITION_DURATION_OPTIONS if b <= beats]
    return usable[-1] if usable else TRANSITION_DURATION_OPTIONS[0]


def profile_for(seam) -> str:
    """bass_swap only where the bass was closed by a hand, not by the pressing."""
    if seam.get("b_bass_hold_is_hand") and (seam.get("b_bass_held_sec") or 0) >= 6:
        return "bass_swap"
    if (seam.get("a_thinned_sec") or 0) >= 4:
        return "tops_swap"
    return "plain_blend"


def his_audio(mix: str, start: float, seconds: float, out: Path) -> bool:
    info = sf.info(mix)
    a = int(max(start, 0) * info.samplerate)
    b = min(int((start + seconds) * info.samplerate), info.frames)
    if b - a < info.samplerate:
        return False
    data, sr = sf.read(mix, start=a, stop=b, dtype="float32")
    sf.write(out, data, sr)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("seam_dirs", nargs="+")
    ap.add_argument("--mix", action="append", required=True,
                    help="set_dir_name=path/to/mix.wav")
    ap.add_argument("--analyses", required=True,
                    help="Dir of AnalysisResult JSONs — the beat grids live here")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    analyses = {}
    for f in glob.glob(str(Path(args.analyses) / "*.json")):
        d = json.loads(Path(f).read_text())
        analyses[Path(d["track"]["source_path"]).stem] = d

    mixes = dict(m.split("=", 1) for m in args.mix)
    out = Path(args.out)
    (out / "moje").mkdir(parents=True, exist_ok=True)
    (out / "twoje").mkdir(parents=True, exist_ok=True)

    rows = []
    for d in args.seam_dirs:
        set_name = Path(d).name
        mix = mixes.get(set_name)
        for f in sorted(glob.glob(str(Path(d) / "seam_*.json"))):
            s = json.loads(Path(f).read_text())
            if not s.get("blend_sec"):
                continue
            a, b = s["deck_a"], s["deck_b"]
            beats = snap_beats(s["blend_sec"])
            ga = grid(analyses.get(Path(a["path"]).stem, {}))
            gb = grid(analyses.get(Path(b["path"]).stem, {}))
            if not ga or not gb:
                print(f"  POMIJAM {Path(f).stem}: brak wiarygodnej siatki bitów",
                      flush=True)
                continue

            # Both decks run at ONE tempo, derived from each record's own BPM, so
            # the two cannot drift apart at all. The measured playback rate is a
            # 0.15 % grid search — fine for saying what happened, and worth up to
            # three quarters of a beat of slip across a long render, which is the
            # gallop. His tempo is preserved by taking the target from what he was
            # actually running on the outgoing deck.
            raw_a = analyses[Path(a["path"]).stem]["beatgrid"]["bpm"]
            raw_b = analyses[Path(b["path"]).stem]["beatgrid"]["bpm"]
            # The outgoing record sets the tempo, exactly as it does on a mixer;
            # the incoming one is pitched onto it, so the two are identical by
            # construction and cannot slip apart however long the blend runs.
            target_bpm = deck_tempo(raw_a, a["rate"])
            bpm_a = raw_a * 2.0 ** round(np.log2(target_bpm / max(raw_a, 1e-9)
                                                 / max(a["rate"], 1e-9)))
            bpm_b = raw_b * 2.0 ** round(np.log2(target_bpm / max(raw_b, 1e-9)
                                                 / max(b["rate"], 1e-9)))
            rate_a, rate_b = target_bpm / bpm_a, target_bpm / bpm_b
            if not (0.85 < rate_a < 1.18 and 0.85 < rate_b < 1.18):
                print(f"  POMIJAM {Path(f).stem}: tempo poza zakresem suwaka "
                      f"({rate_a:.3f} / {rate_b:.3f}) — siatka bitów jednego "
                      f"z utworów nie zgadza się z pomiarem", flush=True)
                continue
            dur = beats * 60.0 / target_bpm

            # Cues land on bar lines of their own record. Raw measured times sit a
            # median 168 ms off the nearest beat, because what was measured is when
            # a deck crossed the noise floor, not when a hand pressed play.
            # Each deck goes onto its OWN bar line. Deriving the incoming record's
            # position from the outgoing one instead — which sounds more correct,
            # since the DJ had already beatmatched them — was tried and measured
            # worse: grid evenness in the output went from 19 ms to 38 ms, because
            # that route carries the alignment's own residual error into the audio.
            # Two records each landing cleanly on their own grid at one tempo beat
            # one record placed accurately and one placed by inference.
            cue_a = snap((s["b_in_sec"] - a["origin"]) * a["rate"], ga)
            cue_b = snap(max((s["b_in_sec"] - b["origin"]) * b["rate"], 0.0), gb)
            at_mix = a["origin"] + cue_a / a["rate"]
            # His clip has to start on the same musical instant as mine, or the
            # two are not being compared at all — so it is cut from the snapped
            # cue converted back to mix time, not from the raw measurement.
            his_start = at_mix
            # Where he opened the incoming bass, as a fraction of this blend —
            # the textbook midpoint would misrepresent nearly every seam here.
            open_at = None
            if s.get("b_bass_hold_is_hand") and s.get("b_bass_held_at_sec") is not None:
                end = s["b_bass_held_at_sec"] + (s.get("b_bass_held_sec") or 0)
                open_at = (end - s["b_in_sec"]) / max(s["blend_sec"], 1e-9)
                open_at = float(min(max(open_at, 0.05), 1.0))
            name = f"{set_name}_{Path(f).stem[-2:]}"
            row = {"seam": name, "set": set_name, "bass_open_at": open_at,
                   "from": s["from"], "to": s["to"],
                   "blend_measured_sec": s["blend_sec"], "beats_rendered": beats,
                   "profile": profile_for(s),
                   "bass_held_sec": s.get("b_bass_held_sec") or 0,
                   "bass_verdict": s.get("b_bass_hold_verdict"),
                   "thinned_sec": s.get("a_thinned_sec") or 0,
                   "cue_a_sec": cue_a, "cue_b_sec": cue_b,
                   "target_bpm": target_bpm, "bpm_a": bpm_a, "bpm_b": bpm_b,
                   "his_start": at_mix, "b_in_sec": s["b_in_sec"], "a_out_sec": s["a_out_sec"],
                   "rate_a": rate_a, "rate_b": rate_b}
            try:
                render_transition_preview(
                    source_a=a["path"], source_b=b["path"],
                    cue_a_sec=cue_a, cue_b_sec=cue_b,
                    bpm_master=target_bpm,
                    playback_rate_a=rate_a, playback_rate_b=rate_b,
                    profile_id=row["profile"],
                    duration_beats=beats,
                    bass_open_at=open_at,
                    output_path=out / "moje" / f"{name}.wav",
                    tempo_mode="varispeed")
                row["mine"] = f"moje/{name}.wav"
                # Measure the render exactly as his recording was measured. Drawing
                # the envelope instead compares a measurement against an intention:
                # it comes out perfectly smooth because it is what was asked for,
                # not what came back, and that is not a comparison at all.
                rendered = out / "moje" / f"{name}.wav"
                Em = S.sub_energy(S.load_mono(str(rendered)))
                row["measured"] = S.fit_gains(
                    Em,
                    S.sub_energy(S.warp(S.load_mono(a["path"]),
                                        -cue_a / rate_a, rate_a, 0.0, dur)),
                    S.sub_energy(S.warp(S.load_mono(b["path"]),
                                        -cue_b / rate_b, rate_b, 0.0, dur)))
            except Exception as exc:                       # noqa: BLE001
                row["mine"] = None
                row["error"] = f"{type(exc).__name__}: {exc}"[:160]
            if mix and his_audio(mix, his_start, dur,
                                 out / "twoje" / f"{name}.wav"):
                row["his"] = f"twoje/{name}.wav"
            rows.append(row)
            state = "ok  " if row.get("mine") else "BŁĄD"
            print(f"  {state} {name}  {beats:3d} uderzeń · {row['profile']:11s} "
                  f"{row['from'].split('—')[-1].strip()[:20]} → "
                  f"{row['to'].split('—')[-1].strip()[:18]}"
                  + f"  {target_bpm:.1f} BPM"
                  + (f"  bas@{open_at*100:.0f}%" if open_at else "")
                  + (f"   {row.get('error','')}" if not row.get("mine") else ""), flush=True)

    (out / "pairs.json").write_text(json.dumps(rows, ensure_ascii=False))
    ok = sum(1 for r in rows if r.get("mine"))
    print(f"\nzrenderowane {ok} z {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
