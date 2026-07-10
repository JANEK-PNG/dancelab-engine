"""Vocal density — bolt-on component. Proves that filling vocal_density_proxy
activates the already-present vocal_risk (transition windows) and vocal
(mixability) components with NO decision-logic change."""

import numpy as np
import pytest

from dancelab.core.config import load_weights
from dancelab.core.models import (
    AnalysisResult,
    FeatureFrame,
    MixabilityInput,
    Track,
    TransitionWindowInput,
)
from dancelab.decision.mixability import compute_mixability, vocal_conflict
from dancelab.decision.transition_windows import detect_transition_windows


@pytest.fixture
def weights():
    return load_weights("configs/descriptor_weights.yaml")


def analysis_with_vocal(tid, vocal, n=60):
    # bass dips around t=40..44 so a transition window forms (flat features → no maxima)
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(track_id=tid, bpm_estimate=128),
        features=[FeatureFrame(track_id=tid, timestamp_sec=float(t), rms=0.3,
                               spectral_flux=10.0,
                               bass_energy=(5.0 if 40 <= t <= 44 else 100.0),
                               low_freq_energy_ratio=0.5, vocal_density_proxy=vocal)
                  for t in range(n)],
    )


# --------------------------------------------------- transition windows (bolt-on)


def test_vocal_present_removes_neutral_warning(weights):
    with_vocal = analysis_with_vocal("t1", vocal=0.7)
    out = detect_transition_windows(
        TransitionWindowInput(track_id="t1", feature_frames=with_vocal.features),
        weights.transition_window,
    )
    # the "vocal risk unavailable" warning must be gone now that the field is filled
    assert not any("vocal risk unavailable" in w for w in out.warnings)


def test_no_vocal_field_still_warns_neutral(weights):
    no_vocal = AnalysisResult(engine_version="0.1.0", track=Track(track_id="t1"),
                              features=[FeatureFrame(track_id="t1", timestamp_sec=float(t),
                                        rms=0.3, spectral_flux=10.0, bass_energy=50.0)
                                        for t in range(40)])
    out = detect_transition_windows(
        TransitionWindowInput(track_id="t1", feature_frames=no_vocal.features),
        weights.transition_window,
    )
    assert any("vocal risk unavailable" in w for w in out.warnings)


def test_high_vocal_raises_window_risk(weights):
    quiet = detect_transition_windows(
        TransitionWindowInput(track_id="t1", feature_frames=analysis_with_vocal("t1", 0.0).features),
        weights.transition_window,
    )
    loud = detect_transition_windows(
        TransitionWindowInput(track_id="t2", feature_frames=analysis_with_vocal("t2", 0.9).features),
        weights.transition_window,
    )
    assert loud.windows[0].risk_score >= quiet.windows[0].risk_score


# ------------------------------------------------------------- mixability (bolt-on)


def test_vocal_conflict_both_vocal_vs_instrumental():
    a = analysis_with_vocal("a", 0.8)
    b = analysis_with_vocal("b", 0.7)
    instrumental = analysis_with_vocal("c", 0.05)
    assert vocal_conflict(a, b) == pytest.approx(0.7)          # both vocal → clash
    assert vocal_conflict(a, instrumental) == pytest.approx(0.05)  # one instrumental defuses


def test_mixability_flags_vocal_clash(weights):
    out = compute_mixability(
        MixabilityInput(track_a=analysis_with_vocal("a", 0.8),
                        track_b=analysis_with_vocal("b", 0.8)),
        weights.mixability, weights.mixability_conflict,
    )
    assert any("vocal clash" in r for r in out.risks)
    assert not any("vocal conflict unavailable" in w for w in out.warnings)


def test_hpss_backend_on_synthetic_signal():
    pytest.importorskip("librosa")
    from dancelab.features.vocals import vocal_activity

    sr = 22050
    t = np.arange(sr * 2) / sr
    # 1 kHz tone sits in the vocal band → high proxy; 60 Hz sub → low proxy
    mid = np.sin(2 * np.pi * 1000 * t).astype(np.float32)
    sub = np.sin(2 * np.pi * 60 * t).astype(np.float32)
    assert vocal_activity(mid, sr, method="hpss").mean() > \
        vocal_activity(sub, sr, method="hpss").mean()


def test_demucs_energy_ratio_silence_gate():
    # pure-numpy test of the demucs post-processing (no model needed)
    from dancelab.features.vocals import _energy_ratio_per_frame

    n = 44100 * 3
    rng = np.random.default_rng(0)
    mix = (rng.standard_normal(n) * 0.3).astype(np.float32)
    mix[: n // 3] *= 1e-4                       # first third = near silence
    vocals = mix.copy()                         # vocals == mix elsewhere → ratio ~1
    ratio = _energy_ratio_per_frame(vocals, mix, 2048, 512)
    n_frames = len(ratio)
    assert ratio[: n_frames // 4].max() == 0.0  # silent region gated to 0
    assert ratio[n_frames // 2 :].mean() > 0.5  # loud region keeps the ratio


def test_energy_ratio_gate_holds_when_mostly_silent():
    # AUD-M1: when >50% of frames are silent the all-frames median is 0, so the
    # old floor (0.05 * median) was 0 and the silence gate never fired — every
    # silent gap faked a full vocal peak. Reference must be the nonzero median.
    from dancelab.features.vocals import _energy_ratio_per_frame

    n = 44100 * 3
    rng = np.random.default_rng(1)
    mix = (rng.standard_normal(n) * 0.3).astype(np.float32)
    mix[: (2 * n) // 3] *= 1e-4                  # first TWO thirds = near silence
    vocals = mix.copy()                          # vocals == mix → naive ratio ~1
    ratio = _energy_ratio_per_frame(vocals, mix, 2048, 512)
    n_frames = len(ratio)
    assert ratio[: n_frames // 4].max() == 0.0   # silent majority still gated to 0
    assert ratio[(3 * n_frames) // 4 :].mean() > 0.5  # loud tail preserved


def test_auto_method_prefers_demucs_when_available():
    # ENV-2: assert behavior, not machine state — skip when [vocals] extra absent
    pytest.importorskip("demucs")
    from dancelab.features.vocals import _demucs_available

    assert _demucs_available() is True
