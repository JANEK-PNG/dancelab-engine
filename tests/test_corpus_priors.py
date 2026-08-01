"""Corpus-measured transition priors: lifts, bucketing, graceful degradation."""

import json

import pytest

from dancelab.core.models import AnalysisResult, FeatureFrame, Track
from dancelab.decision import corpus_priors as cp


def _track(track_id: str, camelot: str, bpm: float, rms: float) -> AnalysisResult:
    return AnalysisResult(
        engine_version="0.1.0",
        track=Track(track_id=track_id, key_estimate=camelot, bpm_estimate=bpm),
        features=[
            FeatureFrame(
                track_id=track_id,
                timestamp_sec=float(timestamp),
                rms=rms,
                low_freq_energy_ratio=0.5,
                bass_energy=50.0,
            )
            for timestamp in range(30)
        ],
    )


@pytest.fixture()
def priors_file(tmp_path, monkeypatch):
    """Minimal valid priors JSON matching scripts/corpus_priors.py output."""
    payload = {
        "camelot_relation_pct": {
            "real_djs": {"exact": 11.0, "adjacent_same_mode": 9.5, "risky": 63.2},
            "chance_baseline": {"exact": 8.8, "adjacent_same_mode": 7.0, "risky": 69.8},
        },
        "bpm_delta_folded_pct": {
            "real_djs": {"0-2%": 62.9, ">10%": 8.6},
            "chance_baseline": {"0-2%": 51.6, ">10%": 17.1},
        },
    }
    path = tmp_path / "priors.json"
    path.write_text(json.dumps(payload))
    monkeypatch.setenv(cp.ENV_OVERRIDE, str(path))
    cp._load.cache_clear()
    yield path
    cp._load.cache_clear()


def test_bpm_bucket_octave_folds():
    # 88 vs 175: double-time fold → ~0.6% delta, not >10%
    assert cp.bpm_delta_bucket(88.0, 175.0) == "0-2%"
    assert cp.bpm_delta_bucket(128.0, 129.0) == "0-2%"
    assert cp.bpm_delta_bucket(128.0, 145.0) == ">10%"


def test_lift_rewards_measured_dj_behaviour(priors_file):
    # tight bpm + adjacent key = what DJs actually do → lift > 1
    lift, notes = cp.transition_prior_lift("adjacent_same_mode", 128.0, 129.0)
    assert lift > 1.0
    assert any("bpm prior" in n for n in notes) and any("harmonic prior" in n for n in notes)
    # huge unfoldable jump = what DJs avoid → lift < 1
    lift_bad, _ = cp.transition_prior_lift("risky", 128.0, 145.0)
    assert lift_bad < 1.0
    assert lift_bad >= cp.LIFT_CLAMP[0]


def test_missing_inputs_are_neutral_not_guessed(priors_file):
    lift, notes = cp.transition_prior_lift(None, None, None)
    assert lift == 1.0
    assert any("neutral" in n for n in notes)


def test_missing_priors_file_degrades_gracefully(tmp_path, monkeypatch):
    monkeypatch.setenv(cp.ENV_OVERRIDE, str(tmp_path / "nope.json"))
    cp._load.cache_clear()
    lift, notes = cp.transition_prior_lift("exact", 128.0, 128.0)
    assert lift == 1.0
    assert any("unavailable" in n for n in notes)
    cp._load.cache_clear()


def test_lift_is_clamped(priors_file):
    lift, _ = cp.transition_prior_lift("adjacent_same_mode", 128.0, 128.0)
    assert cp.LIFT_CLAMP[0] <= lift <= cp.LIFT_CLAMP[1]


def test_weight_zero_leaves_transition_score_untouched(priors_file):
    """set_builder applies the lift only when corpus_priors_weight > 0."""
    from dancelab.core.config import load_weights
    from dancelab.decision.set_builder import build_set

    weights_on = load_weights("configs/descriptor_weights.yaml")
    weights_off = weights_on.model_copy(update={"corpus_priors_weight": 0.0})

    tracks = [
        _track("t1", "8A", 128, 0.2),
        _track("t2", "9A", 129, 0.3),
        _track("t3", "3B", 140, 0.4),
    ]
    plan_on = build_set(tracks, weights_on, arc="build")
    plan_off = build_set(tracks, weights_off, arc="build")
    # both produce a full plan; prior notes appear only when enabled
    assert len(plan_on.track_order) == 3 and len(plan_off.track_order) == 3
    on_notes = [r for t in plan_on.transitions for r in t.reasoning if "corpus" in r]
    off_notes = [r for t in plan_off.transitions for r in t.reasoning if "corpus" in r]
    assert on_notes and not off_notes
