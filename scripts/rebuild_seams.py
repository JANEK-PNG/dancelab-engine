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

from dancelab.preview.transition_simulation import (
    TRANSITION_DURATION_OPTIONS,
    render_transition_preview,
)

MIX_BPM = 136.0
LEAD_SEC = 8.0          # a little of the outgoing record alone, to hear the join arrive


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
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

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
            dur = beats * 60.0 / MIX_BPM
            # position inside each record at the instant the incoming one arrives
            cue_a = (s["b_in_sec"] - a["origin"]) * a["rate"]
            cue_b = max((s["b_in_sec"] - b["origin"]) * b["rate"], 0.0)
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
                   "cue_a_sec": cue_a, "cue_b_sec": cue_b}
            try:
                render_transition_preview(
                    source_a=a["path"], source_b=b["path"],
                    cue_a_sec=max(cue_a - LEAD_SEC, 0.0),
                    cue_b_sec=max(cue_b - LEAD_SEC * b["rate"] / a["rate"], 0.0),
                    bpm_master=MIX_BPM,
                    playback_rate_a=a["rate"], playback_rate_b=b["rate"],
                    profile_id=row["profile"],
                    duration_beats=beats,
                    bass_open_at=open_at,
                    output_path=out / "moje" / f"{name}.wav",
                    tempo_mode="varispeed")
                row["mine"] = f"moje/{name}.wav"
            except Exception as exc:                       # noqa: BLE001
                row["mine"] = None
                row["error"] = f"{type(exc).__name__}: {exc}"[:160]
            if mix and his_audio(mix, s["b_in_sec"] - LEAD_SEC, dur + LEAD_SEC,
                                 out / "twoje" / f"{name}.wav"):
                row["his"] = f"twoje/{name}.wav"
            rows.append(row)
            state = "ok  " if row.get("mine") else "BŁĄD"
            print(f"  {state} {name}  {beats:3d} uderzeń · {row['profile']:11s} "
                  f"{row['from'].split('—')[-1].strip()[:20]} → "
                  f"{row['to'].split('—')[-1].strip()[:18]}"
                  + (f"  bas@{open_at*100:.0f}%" if open_at else "")
                  + (f"   {row.get('error','')}" if not row.get("mine") else ""), flush=True)

    (out / "pairs.json").write_text(json.dumps(rows, ensure_ascii=False))
    ok = sum(1 for r in rows if r.get("mine"))
    print(f"\nzrenderowane {ok} z {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
