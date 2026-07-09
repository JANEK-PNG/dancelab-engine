"""Waveform visualization tests."""

from __future__ import annotations

from pathlib import Path

from dancelab.visualization.mixability_waveforms import (
    MixabilityWaveformPair,
    WaveformTrack,
    render_pair_waveform_svg,
)


def test_render_pair_waveform_svg_writes_visual_card(tmp_path):
    pair = MixabilityWaveformPair(
        rank=1,
        mixability_score=0.72,
        confidence=0.4,
        risks=["moderate bass conflict (0.49)"],
        pair_score=2.18,
        track_a=WaveformTrack(
            title="Track A",
            duration_sec=300.0,
            window_start_sec=120.0,
            window_end_sec=136.0,
            window_label="mix-out window 2:00–2:16",
            peaks=[(-0.3, 0.4), (-0.8, 0.7), (-0.2, 0.2)],
            base_color="#000000",
            accent_color="#222222",
        ),
        track_b=WaveformTrack(
            title="Track B",
            duration_sec=240.0,
            window_start_sec=12.0,
            window_end_sec=28.0,
            window_label="mix-in window 0:12–0:28",
            peaks=[(-0.4, 0.5), (-0.7, 0.6), (-0.3, 0.3)],
            base_color="#333333",
            accent_color="#555555",
        ),
        decision_class="review_required",
        recommended_strategy="echo_out",
    )

    out = render_pair_waveform_svg(pair, tmp_path / "pair.svg")

    text = out.read_text()
    assert out == Path(tmp_path / "pair.svg")
    assert "CANDIDATE MIXABILITY PAIR #1" in text
    assert "Track A" in text
    assert "Track B" in text
    assert "mix-out window 2:00" in text
    assert "suggested strategy echo out" in text
