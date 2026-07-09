"""Candidate breakdown / drop detectors for Phase 2 coverage."""

from __future__ import annotations

import numpy as np

from dancelab.core.models import Segment, SegmentType
from dancelab.descriptors._shared import prepare_curve, validate_same_length


def breakdown_drop_curves(
    rms: np.ndarray,
    bass_salience: np.ndarray,
    onset_density: np.ndarray,
    tension: np.ndarray,
    release: np.ndarray,
    groove_density: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-frame candidate likelihoods for breakdowns and drops.

    Breakdowns lean toward low energy / sparse low-end moments with elevated
    tension and limited release. Drops lean toward release plus renewed energy,
    bass, and onset activity. This is a candidate detector, not structure truth.
    """
    validate_same_length(rms, bass_salience, onset_density, tension, release)
    energy_curve = prepare_curve(rms, keep_constant=0.5)
    bass_curve = prepare_curve(bass_salience, keep_constant=0.5)
    onset_curve = prepare_curve(onset_density, keep_constant=0.5)
    tension_curve = prepare_curve(tension, keep_constant=0.5)
    release_curve = prepare_curve(release, keep_constant=0.0)
    groove_curve = (
        prepare_curve(groove_density, keep_constant=0.5)
        if groove_density is not None
        else np.full_like(energy_curve, 0.5)
    )

    if len(energy_curve) > 1:
        energy_rise = prepare_curve(np.clip(np.gradient(energy_curve), 0.0, None), keep_constant=0.0)
        bass_rise = prepare_curve(np.clip(np.gradient(bass_curve), 0.0, None), keep_constant=0.0)
    else:
        energy_rise = np.zeros_like(energy_curve)
        bass_rise = np.zeros_like(energy_curve)

    breakdown = np.clip(
        0.28 * (1.0 - energy_curve)
        + 0.22 * (1.0 - bass_curve)
        + 0.18 * (1.0 - onset_curve)
        + 0.16 * tension_curve
        + 0.10 * (1.0 - release_curve)
        + 0.06 * (1.0 - groove_curve),
        0.0,
        1.0,
    )
    drop = np.clip(
        0.32 * release_curve
        + 0.20 * energy_rise
        + 0.16 * bass_rise
        + 0.14 * onset_curve
        + 0.10 * bass_curve
        + 0.08 * groove_curve,
        0.0,
        1.0,
    )
    return breakdown, drop


def relabel_breakdown_drop_segments(
    segments: list[Segment],
    times_sec: np.ndarray,
    breakdown_curve: np.ndarray,
    drop_curve: np.ndarray,
    energy_curve: np.ndarray,
    release_curve: np.ndarray,
) -> list[Segment]:
    """Refine non-edge segment labels using candidate breakdown/drop signals."""
    if not segments:
        return []

    times = np.asarray(times_sec, dtype=np.float64)
    validate_same_length(times, breakdown_curve, drop_curve, energy_curve, release_curve)

    refined: list[Segment] = []
    for segment in segments:
        if segment.segment_type in (SegmentType.intro, SegmentType.outro, SegmentType.unknown):
            refined.append(segment)
            continue

        mask = (times >= segment.start_sec) & (times <= segment.end_sec)
        if not mask.any():
            midpoint = (segment.start_sec + segment.end_sec) / 2.0
            nearest = int(np.argmin(np.abs(times - midpoint)))
            mask = np.zeros_like(times, dtype=bool)
            mask[nearest] = True

        breakdown_mean = float(np.mean(breakdown_curve[mask]))
        drop_mean = float(np.mean(drop_curve[mask]))
        energy_mean = float(np.mean(energy_curve[mask]))
        release_mean = float(np.mean(release_curve[mask]))
        energy_slope = float(
            energy_curve[np.where(mask)[0][-1]] - energy_curve[np.where(mask)[0][0]]
        )

        label = segment.segment_type
        if breakdown_mean >= 0.58 and breakdown_mean >= drop_mean + 0.06 and energy_mean <= 0.58:
            label = SegmentType.breakdown
        elif drop_mean >= 0.58 and (drop_mean >= breakdown_mean or release_mean >= 0.55):
            label = SegmentType.drop
        elif energy_slope >= 0.08 and energy_mean < 0.72:
            label = SegmentType.build
        elif label not in (SegmentType.breakdown, SegmentType.drop):
            label = SegmentType.groove

        refined.append(segment.model_copy(update={"segment_type": label}))
    return refined
