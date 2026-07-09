"""Transition strategy classifier contracts."""

from dancelab.core.models import (
    AnalysisResult,
    FeatureFrame,
    Track,
    TransitionWindow,
    TransitionStrategy,
    WindowType,
)
from dancelab.decision.mixability import compute_mixability
from dancelab.decision.transition_strategy import classify_transition_strategy
from dancelab.core.config import load_weights
from dancelab.core.models import MixabilityInput


def make_analysis(track_id, bpm, camelot="8A", vocal=0.1, lfer=0.45, style="techno"):
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(
            track_id=track_id,
            bpm_estimate=bpm,
            key_estimate=camelot,
            key_confidence=0.9,
            style_label=style,
        ),
        features=[
            FeatureFrame(
                track_id=track_id,
                timestamp_sec=float(t),
                rms=0.4,
                low_freq_energy_ratio=lfer,
                vocal_density_proxy=vocal,
                bass_energy=45.0,
            )
            for t in range(60)
        ],
    )


def test_small_direct_bpm_gap_allows_standard_blend():
    weights = load_weights("configs/descriptor_weights.yaml")
    a = make_analysis("a", 128, camelot="8A")
    b = make_analysis("b", 129, camelot="9A")
    mix = compute_mixability(MixabilityInput(track_a=a, track_b=b), weights.mixability, weights.mixability_conflict)
    strategy = classify_transition_strategy(
        a,
        b,
        mix,
        selected_window_a=TransitionWindow(start_sec=100, end_sec=116, score=0.8, window_type=WindowType.mix_out, risk_score=0.2),
        selected_window_b=TransitionWindow(start_sec=8, end_sec=24, score=0.8, window_type=WindowType.mix_in, risk_score=0.2),
    )
    assert strategy.standard_blend_allowed is True
    assert strategy.recommended_transition_strategy in {
        TransitionStrategy.standard_blend,
        TransitionStrategy.short_blend,
    }


def test_large_bpm_gap_requires_non_standard_strategy():
    weights = load_weights("configs/descriptor_weights.yaml")
    a = make_analysis("a", 128, camelot="8A")
    b = make_analysis("b", 150, camelot="3B", vocal=0.55, lfer=0.7, style="trance")
    mix = compute_mixability(MixabilityInput(track_a=a, track_b=b), weights.mixability, weights.mixability_conflict)
    strategy = classify_transition_strategy(
        a,
        b,
        mix,
        selected_window_a=TransitionWindow(start_sec=100, end_sec=116, score=0.6, window_type=WindowType.bridge, risk_score=0.45),
        selected_window_b=TransitionWindow(start_sec=8, end_sec=24, score=0.5, window_type=WindowType.bridge, risk_score=0.5),
    )
    assert strategy.standard_blend_allowed is False
    assert strategy.recommended_transition_strategy in {
        TransitionStrategy.tempo_ramp,
        TransitionStrategy.break_transition,
        TransitionStrategy.echo_out,
        TransitionStrategy.hard_cut,
        TransitionStrategy.reset,
    }


def test_half_time_relation_prefers_switch_strategy():
    weights = load_weights("configs/descriptor_weights.yaml")
    a = make_analysis("a", 140, camelot="8A")
    b = make_analysis("b", 70, camelot="9A")
    mix = compute_mixability(MixabilityInput(track_a=a, track_b=b), weights.mixability, weights.mixability_conflict)
    strategy = classify_transition_strategy(a, b, mix)
    assert strategy.recommended_transition_strategy == TransitionStrategy.half_time_double_time_switch
