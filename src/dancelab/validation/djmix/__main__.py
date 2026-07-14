"""Local CLI for the DJ-mix validation add-on.

Example:
    python -m dancelab.validation.djmix --mix mix.wav --track original.wav
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import numpy as np

from dancelab.core.audio_types import AudioSignal
from dancelab.preprocessing.beatgrid import estimate_beatgrid
from dancelab.validation.djmix.alignment import align_feature_sequences
from dancelab.validation.djmix.confidence import score_cue_candidates
from dancelab.validation.djmix.cues import extract_cue_candidates
from dancelab.validation.djmix.features import extract_beat_synchronous_features
from dancelab.validation.djmix.identity import identify_audio_file
from dancelab.validation.djmix.models import (
    M11_CODE_VERSION,
    M11_FORMULA_VERSION,
    M11_SOURCE_BASIS,
)
from dancelab.validation.djmix.transitions import assemble_transition_evidence


def _load_audio(path: Path, sample_rate: int) -> AudioSignal:
    try:
        import librosa
    except ImportError as exc:  # pragma: no cover - command requires audio extra
        raise RuntimeError("install the DanceLab audio extra before using djmix validation") from exc
    samples, loaded_rate = librosa.load(path, sr=sample_rate, mono=True)
    return AudioSignal(
        samples=np.asarray(samples, dtype=np.float32),
        sample_rate=int(loaded_rate),
        source_path=str(path.resolve()),
    )


def _feature_sequence(path: Path, sample_rate: int, feature_names: Sequence[str]):
    signal = _load_audio(path, sample_rate)
    grid = estimate_beatgrid(signal)
    sequence = extract_beat_synchronous_features(
        signal,
        grid.beat_times_sec,
        feature_names=feature_names,
        beatgrid_reliable=grid.reliable,
        beatgrid_quality=grid.quality_score,
        warnings=grid.diagnostic_flags,
    )
    return sequence, grid


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m dancelab.validation.djmix",
        description="Align local original tracks to a local DJ mix using beat-synchronous SDTW.",
    )
    parser.add_argument("--mix", type=Path, required=True, help="Local DJ mix audio file")
    parser.add_argument(
        "--track",
        type=Path,
        action="append",
        required=True,
        help="Local original track; repeat for multiple tracks",
    )
    parser.add_argument("--output", "-o", type=Path, help="Write JSON report here")
    parser.add_argument("--sample-rate", type=int, default=22050)
    parser.add_argument("--features", default="chroma,mfcc", help="chroma,mfcc or a subset")
    parser.add_argument("--normalization", default="source_global")
    parser.add_argument("--match-threshold", type=float, default=0.4)
    parser.add_argument("--no-key-invariant", action="store_true")
    parser.add_argument("--include-path", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    feature_names = tuple(name.strip().lower() for name in args.features.split(",") if name.strip())
    missing = [path for path in [args.mix, *args.track] if not path.is_file()]
    if missing:
        raise SystemExit("missing audio file(s): " + ", ".join(str(path) for path in missing))

    mix_identity = identify_audio_file(args.mix)
    track_identities = [identify_audio_file(path) for path in args.track]
    fingerprints = [identity.sha256 for identity in track_identities]
    duplicate_fingerprints = sorted({value for value in fingerprints if fingerprints.count(value) > 1})
    if duplicate_fingerprints:
        duplicate_paths = [
            identity.resolved_path
            for identity in track_identities
            if identity.sha256 in duplicate_fingerprints
        ]
        raise SystemExit(
            "duplicate track audio identities are not valid in one M11 run: "
            + ", ".join(duplicate_paths)
        )

    mix_features, mix_grid = _feature_sequence(args.mix, args.sample_rate, feature_names)
    results: list[dict[str, object]] = []
    alignment_records = []
    for track_path, track_identity in zip(args.track, track_identities, strict=True):
        track_features, track_grid = _feature_sequence(
            track_path,
            args.sample_rate,
            feature_names,
        )
        alignment = align_feature_sequences(
            track_features,
            mix_features,
            feature_names=feature_names,
            key_invariant=not args.no_key_invariant,
            normalization=args.normalization,
            match_threshold=args.match_threshold,
        )
        cues = extract_cue_candidates(
            alignment.path,
            mix_beat_times_sec=mix_features.beat_times_sec,
            track_beat_times_sec=track_features.beat_times_sec,
        )
        cues = score_cue_candidates(
            cues,
            alignment,
            track=track_features,
            mix=mix_features,
        )
        alignment_records.append((track_identity, alignment, cues))
        results.append({
            "track_id": track_identity.source_id,
            "display_name": track_identity.display_name,
            "audio_identity": track_identity.as_dict(),
            "track_beatgrid": {
                "bpm": track_grid.bpm,
                "reliable": track_grid.reliable,
                "quality_score": track_grid.quality_score,
                "warnings": track_grid.diagnostic_flags,
            },
            "alignment": alignment.as_dict(include_path=args.include_path),
            "cue_candidates": [candidate.as_dict() for candidate in cues],
        })

    transitions = []
    for previous, following in zip(alignment_records, alignment_records[1:], strict=False):
        previous_identity, previous_alignment, previous_cues = previous
        next_identity, next_alignment, next_cues = following
        transitions.extend(assemble_transition_evidence(
            mix=mix_identity,
            previous_track=previous_identity,
            next_track=next_identity,
            previous_alignment=previous_alignment,
            next_alignment=next_alignment,
            previous_cues=previous_cues,
            next_cues=next_cues,
        ))

    report = {
        "schema_version": "1.1.0",
        "method": "beat-synchronous mix-to-track subsequence DTW",
        "formula_version": M11_FORMULA_VERSION,
        "code_version": M11_CODE_VERSION,
        "source_basis": list(M11_SOURCE_BASIS),
        "scope": "offline local validation; no engine mutation",
        "confidence_status": "diagnostic_equal_weights_untuned_not_probability",
        "mix_identity": mix_identity.as_dict(),
        "mix_beatgrid": {
            "bpm": mix_grid.bpm,
            "reliable": mix_grid.reliable,
            "quality_score": mix_grid.quality_score,
            "warnings": mix_grid.diagnostic_flags,
        },
        "results": results,
        "transitions": [transition.as_dict() for transition in transitions],
    }
    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
