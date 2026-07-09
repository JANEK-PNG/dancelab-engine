"""Auto blend-profile classifier contracts."""

from dancelab.core.models import BlendProfile, TransitionStrategy
from dancelab.decision.blend_profile import classify_blend_profile


def test_classify_blend_profile_prefers_bass_swap_for_high_bass_conflict():
    out = classify_blend_profile(
        recommended_transition_strategy=TransitionStrategy.standard_blend,
        standard_blend_allowed=True,
        bass_risk=0.58,
        vocal_risk=0.08,
    )

    assert out.blend_profile_auto == BlendProfile.bass_swap
    assert "bass conflict risk 0.58" in out.explanation


def test_classify_blend_profile_prefers_contour_blend_for_vocal_exposure():
    out = classify_blend_profile(
        recommended_transition_strategy=TransitionStrategy.standard_blend,
        standard_blend_allowed=True,
        bass_risk=0.18,
        vocal_risk=0.31,
    )

    assert out.blend_profile_auto == BlendProfile.contour_blend
    assert "0.31" in out.explanation


def test_classify_blend_profile_prefers_tops_swap_for_short_blend():
    out = classify_blend_profile(
        recommended_transition_strategy=TransitionStrategy.short_blend,
        standard_blend_allowed=True,
        bass_risk=0.21,
        vocal_risk=0.12,
    )

    assert out.blend_profile_auto == BlendProfile.tops_swap
    assert "short blend" in out.explanation


def test_classify_blend_profile_falls_back_for_non_standard_exit():
    out = classify_blend_profile(
        recommended_transition_strategy=TransitionStrategy.echo_out,
        standard_blend_allowed=False,
        bass_risk=0.61,
        vocal_risk=0.34,
    )

    assert out.blend_profile_auto == BlendProfile.plain_blend
    assert "echo out" in out.explanation
