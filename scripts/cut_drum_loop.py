#!/usr/bin/env python
"""Cut a grid-locked, sampler-ready drum loop out of a track.

The mix-in-with-a-loop figure (Janek, 2026-07-28): trigger an 8/16-beat drum
loop of the incoming track from the Rekordbox sampler over the outgoing track,
blend, then hand over to the full track on deck. The sampler plays an ordinary
file, so this is performable on CDJs with no live stems.

Region choice is Demucs-informed: per-beat RMS of the drums stem vs everything
else. A good loop region has strong, steady drums and little melodic content —
so the score is drums-mean minus its own variability minus the other stems'
level. The chosen window is snapped to the beatgrid and cut from the ORIGINAL
audio (the loop should sound like the record, not like a stem); a drums-only
variant is exported too, clearly named as the separated stem.

Usage: python scripts/cut_drum_loop.py "track.aiff" --beats 8 --out-dir DIR
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("track", type=Path)
    parser.add_argument("--beats", type=int, default=8, choices=(4, 8, 16, 32))
    parser.add_argument("--out-dir", type=Path, default=Path.home() / "Desktop/DanceLab-Preview")
    parser.add_argument("--config", default="configs/default.yaml")
    args = parser.parse_args()

    import soundfile as sf

    from dancelab.core.config import load_config
    from dancelab.core.pipeline import analyze_track
    from dancelab.ingestion.loader import load_audio
    from dancelab.stems.extractor import _extract_demucs_channels

    config = load_config(args.config)
    print(f"analyzing {args.track.name} …")
    analysis = analyze_track(args.track, config)
    grid = analysis.beatgrid
    if grid is None or not grid.reliable or not grid.beat_times_sec:
        raise SystemExit("no reliable beatgrid — a loop must be grid-locked, aborting")
    beats = grid.beat_times_sec

    print("separating stems (demucs, this takes a moment) …")
    signal = load_audio(args.track, config)
    channels, _status = _extract_demucs_channels(signal, config)
    by_name = {stem.value if hasattr(stem, "value") else str(stem): sig
               for stem, sig in channels.items()}
    drums = next((sig for name, sig in by_name.items() if "drum" in name.lower()), None)
    if drums is None:
        raise SystemExit(f"no drums stem in demucs output ({list(by_name)})")
    sr = drums.sample_rate

    def per_beat_rms(samples: np.ndarray) -> np.ndarray:
        mono = samples.mean(axis=0) if samples.ndim == 2 else samples
        out = []
        for t0, t1 in zip(beats, beats[1:]):
            seg = mono[int(t0 * sr):int(t1 * sr)]
            out.append(float(np.sqrt(np.mean(seg ** 2))) if seg.size else 0.0)
        return np.asarray(out)

    drums_rms = per_beat_rms(np.asarray(drums.samples))
    # A loop is a GROOVE: drums and bass belong in it. Only vocals and melodic
    # content fight a loop played under another track — penalize those alone.
    melodic = [per_beat_rms(np.asarray(sig.samples))
               for name, sig in by_name.items()
               if not any(k in name.lower() for k in ("drum", "bass"))]
    melodic_rms = np.sum(melodic, axis=0) if melodic else np.zeros_like(drums_rms)

    # A loop must start on the "1": candidate starts are downbeats only. An
    # off-phase loop sounds mechanical no matter what plays in it.
    downbeat_idx = sorted({int(np.argmin(np.abs(np.asarray(beats) - d)))
                           for d in (grid.downbeats_sec or [])})
    if not downbeat_idx:
        raise SystemExit("no downbeats on the grid — cannot phase-lock a loop")

    n = args.beats
    scale = max(float(drums_rms.max()), 1e-9)
    best_i, best_score = None, -1e9
    for i in downbeat_idx:
        if i + n >= len(drums_rms):
            continue
        d = drums_rms[i:i + n] / scale
        m = melodic_rms[i:i + n] / scale
        score = float(d.mean() - 2.0 * d.std() - 1.5 * m.mean())
        if score > best_score:
            best_i, best_score = i, score
    if best_i is None:
        raise SystemExit("track shorter than the requested loop")

    t0, t1 = beats[best_i], beats[best_i + n]
    print(f"chosen region: beats {best_i}..{best_i + n}  ({t0:.2f}s – {t1:.2f}s)"
          f"  score {best_score:.3f}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem_name = args.track.stem.replace(" ", "_")[:24]

    original, orig_sr = sf.read(str(args.track), dtype="float32", always_2d=True)
    cut = original[int(t0 * orig_sr):int(t1 * orig_sr)]
    full_path = args.out_dir / f"LOOP_{stem_name}_{n}beats_ORIGINAL.wav"
    sf.write(str(full_path), cut, orig_sr, subtype="PCM_24")

    dsam = np.asarray(drums.samples)
    dmono = dsam if dsam.ndim == 2 else dsam[np.newaxis, :]
    dcut = dmono[:, int(t0 * sr):int(t1 * sr)].T
    drums_path = args.out_dir / f"LOOP_{stem_name}_{n}beats_DRUMS-STEM.wav"
    sf.write(str(drums_path), dcut, sr, subtype="PCM_24")

    print(f"✓ {full_path}")
    print(f"✓ {drums_path}")
    print(f"  {n} beats @ {grid.bpm:.1f} BPM · grid-locked at beat {best_i}")


if __name__ == "__main__":
    main()
