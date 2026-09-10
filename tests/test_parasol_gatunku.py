"""An umbrella genre label scores like a missing one — never below it.

Before 2026-09-10 `_style_fit` gave "Electronic" 0.35 against a brief of
"Techno" while a track with no genre got 0.5, and confidence rose as if the
genre were known. 4 360 of the owner's 7 910 streams carry such a label.
"""

from __future__ import annotations

from dancelab.context.conditioning import _style_fit, track_context_score
from dancelab.core.models import AnalysisResult, ContextProfile, Track
from dancelab.core.style_labels import effective_style_label, is_umbrella_style_label


def test_umbrella_is_unknown_not_a_mismatch():
    assert _style_fit("Electronic", ["techno"]) == 0.5 == _style_fit(None, ["techno"])
    assert _style_fit("Dance", ["techno"]) == 0.5
    assert _style_fit("Trance", ["techno"]) == 0.35, "a real mismatch still costs"
    assert _style_fit("Techno", ["techno"]) == 1.0


def test_helpers():
    assert is_umbrella_style_label(" electronic ") and is_umbrella_style_label("DANCE")
    assert not is_umbrella_style_label("Electronica") and not is_umbrella_style_label(None)
    assert effective_style_label("Dance") is None and effective_style_label("Garage") == "Garage"


def _analysis(style):
    track = Track(track_id="t", source_path="apple-music:tracks:1", style_label=style,
                  bpm_estimate=128.0, duration_sec=300.0)
    return AnalysisResult(engine_version="test", track=track)


def test_context_score_treats_umbrella_like_missing_including_confidence():
    ctx = ContextProfile(context_id="c", venue_type="club", set_role="peak",
                         time_of_night="late", crowd_energy="high", style_focus=["techno"])
    umbrella = track_context_score(_analysis("Electronic"), ctx)
    missing = track_context_score(_analysis(None), ctx)
    assert umbrella.value == missing.value
    assert umbrella.confidence == missing.confidence
    assert any("umbrella" in w for w in umbrella.warnings)
