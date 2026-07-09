"""Decision layer: honest contracts + config prerequisites.

Deep behavior lives in test_transition_windows.py / test_mixability.py /
test_set_function.py; this file guards the layer's shared invariants.
"""

import pytest

from dancelab.core.config import load_config, load_weights
from dancelab.core.errors import ConfigError
from dancelab.context.context_profile import get_context_profile
from dancelab.core.models import AnalysisResult, SetFunctionInput, Track
from dancelab.decision.set_function import MODEL_VERSION, classify_set_function


def _dummy_analysis() -> AnalysisResult:
    return AnalysisResult(engine_version="0.1.0", track=Track(track_id="t1"))


def test_set_function_empty_track_is_candidate_and_honest():
    # implemented in Sprint 2 Final — degenerate input must not crash: it
    # returns a candidate output with a warning, never a fabricated certainty.
    out = classify_set_function(SetFunctionInput(track_analysis=_dummy_analysis()))
    assert out.model_version == MODEL_VERSION
    assert 0 <= out.confidence <= 1
    assert any("too short" in w for w in out.warnings)


def test_transition_windows_short_input_is_honest():
    # implemented in Sprint 2 — empty-input contract: no windows + explicit warning
    from dancelab.core.models import TransitionWindowInput
    from dancelab.decision.transition_windows import detect_transition_windows

    w = load_weights("configs/descriptor_weights.yaml")
    out = detect_transition_windows(
        TransitionWindowInput(track_id="t1", feature_frames=[]), w.transition_window
    )
    assert out.windows == []
    assert any("too short" in msg for msg in out.warnings)


def test_context_profile_lookup():
    profile = get_context_profile("club_peak")
    assert profile.venue_type == "club"
    assert "techno" in profile.style_focus


def test_unknown_context_profile_raises():
    with pytest.raises(ConfigError):
        get_context_profile("stadium_sunrise")


def test_default_config_transition_top_n():
    cfg = load_config("configs/default.yaml")
    assert cfg.analysis.transition_top_n == 3
