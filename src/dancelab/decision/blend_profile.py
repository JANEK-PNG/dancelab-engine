"""Auto blend-profile classifier for pair-level engine outputs."""

from __future__ import annotations

from dancelab.core.models import BlendProfile, BlendProfileDecision, TransitionStrategy

_BASS_SWAP_THRESHOLD = 0.45
_CONTOUR_BLEND_THRESHOLD = 0.22
_TOPS_SWAP_STRATEGIES = {
    TransitionStrategy.short_blend,
    TransitionStrategy.phrase_aligned_blend,
}
_NON_STANDARD_EXIT_STRATEGIES = {
    TransitionStrategy.echo_out,
    TransitionStrategy.break_transition,
    TransitionStrategy.hard_cut,
    TransitionStrategy.reset,
    TransitionStrategy.tempo_ramp,
    TransitionStrategy.half_time_double_time_switch,
    TransitionStrategy.tool_mix,
}


def classify_blend_profile(
    *,
    recommended_transition_strategy: TransitionStrategy,
    standard_blend_allowed: bool,
    bass_risk: float | None,
    vocal_risk: float | None,
) -> BlendProfileDecision:
    """Pick an auto blend profile from existing pair descriptors.

    This is intentionally lightweight: it does not synthesize audio instructions,
    only exposes the engine's preferred overlap shape so external tooling can
    decide how to render or execute it.
    """

    bass_value = max(float(bass_risk or 0.0), 0.0)
    vocal_value = max(float(vocal_risk or 0.0), 0.0)

    if recommended_transition_strategy in _NON_STANDARD_EXIT_STRATEGIES:
        return BlendProfileDecision(
            blend_profile_auto=BlendProfile.plain_blend,
            explanation=(
                "Auto mode falls back to plain blend because the engine prefers "
                f"{recommended_transition_strategy.value.replace('_', ' ')} over a standard overlap."
            ),
        )

    if bass_value >= _BASS_SWAP_THRESHOLD:
        return BlendProfileDecision(
            blend_profile_auto=BlendProfile.bass_swap,
            explanation=(
                f"Auto mode selects bass swap because bass conflict risk {bass_value:.2f} "
                "favors a deliberate low-end handoff."
            ),
        )

    if vocal_value >= _CONTOUR_BLEND_THRESHOLD:
        return BlendProfileDecision(
            blend_profile_auto=BlendProfile.contour_blend,
            explanation=(
                f"Auto mode selects contour blend because vocal or mid exposure {vocal_value:.2f} "
                "favors a shaped overlap."
            ),
        )

    if recommended_transition_strategy in _TOPS_SWAP_STRATEGIES:
        return BlendProfileDecision(
            blend_profile_auto=BlendProfile.tops_swap,
            explanation=(
                "Auto mode selects tops swap because "
                f"{recommended_transition_strategy.value.replace('_', ' ')} prefers a tighter upper-band handoff."
            ),
        )

    if standard_blend_allowed:
        return BlendProfileDecision(
            blend_profile_auto=BlendProfile.plain_blend,
            explanation=(
                "Auto mode selects plain blend because standard overlap is allowed "
                "and bass or vocal conflict stays controlled."
            ),
        )

    return BlendProfileDecision(
        blend_profile_auto=BlendProfile.plain_blend,
        explanation=(
            "Auto mode falls back to plain blend because no stronger overlap profile "
            "was supported by the current descriptors."
        ),
    )
