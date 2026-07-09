"""Breakdown/drop candidate detector behavior."""

from __future__ import annotations

import numpy as np

from dancelab.core.models import Segment, SegmentType
from dancelab.descriptors.breakdown_drop import (
    breakdown_drop_curves,
    relabel_breakdown_drop_segments,
)


def test_breakdown_drop_curves_separate_sparse_vs_release_moments():
    rms = np.array([0.2, 0.3, 0.95, 0.98], dtype=np.float64)
    bass = np.array([0.15, 0.25, 0.85, 0.95], dtype=np.float64)
    onset = np.array([0.1, 0.2, 0.9, 0.95], dtype=np.float64)
    tension = np.array([0.8, 0.75, 0.35, 0.2], dtype=np.float64)
    release = np.array([0.05, 0.1, 0.7, 0.95], dtype=np.float64)
    groove = np.array([0.2, 0.3, 0.75, 0.9], dtype=np.float64)

    breakdown, drop = breakdown_drop_curves(rms, bass, onset, tension, release, groove)

    assert breakdown.shape == rms.shape
    assert drop.shape == rms.shape
    assert np.all((0.0 <= breakdown) & (breakdown <= 1.0))
    assert np.all((0.0 <= drop) & (drop <= 1.0))
    assert breakdown[0] > drop[0]
    assert drop[-1] > breakdown[-1]


def test_relabel_breakdown_drop_segments_refines_only_non_edge_segments():
    segments = [
        Segment(
            segment_id="s0",
            track_id="t1",
            start_sec=0.0,
            end_sec=10.0,
            segment_type=SegmentType.intro,
        ),
        Segment(
            segment_id="s1",
            track_id="t1",
            start_sec=10.0,
            end_sec=20.0,
            segment_type=SegmentType.groove,
        ),
        Segment(
            segment_id="s2",
            track_id="t1",
            start_sec=20.0,
            end_sec=30.0,
            segment_type=SegmentType.groove,
        ),
        Segment(
            segment_id="s3",
            track_id="t1",
            start_sec=30.0,
            end_sec=40.0,
            segment_type=SegmentType.groove,
        ),
        Segment(
            segment_id="s4",
            track_id="t1",
            start_sec=40.0,
            end_sec=50.0,
            segment_type=SegmentType.outro,
        ),
    ]
    times = np.array([5.0, 15.0, 25.0, 31.0, 35.0, 39.0, 45.0], dtype=np.float64)
    breakdown = np.array([0.1, 0.82, 0.2, 0.18, 0.2, 0.22, 0.1], dtype=np.float64)
    drop = np.array([0.1, 0.2, 0.85, 0.2, 0.22, 0.24, 0.1], dtype=np.float64)
    energy = np.array([0.2, 0.32, 0.75, 0.24, 0.42, 0.64, 0.2], dtype=np.float64)
    release = np.array([0.1, 0.2, 0.72, 0.18, 0.2, 0.22, 0.1], dtype=np.float64)

    refined = relabel_breakdown_drop_segments(
        segments,
        times,
        breakdown,
        drop,
        energy,
        release,
    )

    assert refined[0].segment_type == SegmentType.intro
    assert refined[1].segment_type == SegmentType.breakdown
    assert refined[2].segment_type == SegmentType.drop
    assert refined[3].segment_type == SegmentType.build
    assert refined[4].segment_type == SegmentType.outro
