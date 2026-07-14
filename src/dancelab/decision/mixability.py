"""Mixability Engine v0.1 (Sprint 2 Final — Engineering Ticket).

    M_ix(x,y) = l1*S_tempo + l2*S_phrase + l3*S_energy + l4*S_bass + l5*S_vocal
                + l6*S_tension + l7*S_style + l8*S_context
    M_pair(x,y,tx,ty) = M_ix + W_x(tx) + W_y(ty) - R_conflict
    R_conflict = r1*R_bass + r2*R_vocal + r3*R_phrase + r4*R_tension

STATUS: candidate — experimental (ADR-005). Claim C009: mixability is
contextual compatibility, NOT audio similarity.

Honesty contract (same as transition windows): components computable from
available inputs are computed; unavailable ones get neutral 0.5 + warning,
and confidence is scaled by input coverage.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np

from dancelab.context.conditioning import ContextScoreSummary, track_context_score
from dancelab.core.config import WeightGroup
from dancelab.core.models import (
    AnalysisResult,
    BeatGrid,
    ContextProfile,
    MixabilityInput,
    MixabilityOutput,
    PairWindow,
    Segment,
    TransitionWindow,
    WindowType,
)
from dancelab.core.phrasing import window_phrase_score
from dancelab.core.provenance import guardrail_warnings, provenance_for
from dancelab.decision.harmonic import harmonic_compatibility
from dancelab.decision.rules import evaluate_pair_policy, evaluate_pair_rules

MODEL_VERSION = "mixability_v0.1_harmonic"
STATUS = "candidate"
COMPONENTS = ("tempo", "phrase", "energy", "bass", "vocal", "tension", "style", "context", "harmonic")

_NEUTRAL = 0.5
_BPM_TOLERANCE = 0.08  # ±8% pitch-fader range for full tempo compatibility
_MEAN_FEATURE_NAMES = (
    "rms",
    "low_freq_energy_ratio",
    "vocal_density_proxy",
    "tension_proxy",
)


@dataclass(frozen=True)
class MixabilityPrecomputation:
    """Pair-invariant descriptor values for one set-planning run."""

    feature_means: Mapping[str, Mapping[str, float | None]]
    context_scores: Mapping[str, ContextScoreSummary]
    context: ContextProfile | None


def precompute_mixability_inputs(
    analyses: Iterable[AnalysisResult],
    *,
    context: ContextProfile | None = None,
) -> MixabilityPrecomputation:
    """Compute values reused by every candidate pair exactly once per track."""
    feature_means: dict[str, dict[str, float | None]] = {}
    context_scores: dict[str, ContextScoreSummary] = {}
    for analysis in analyses:
        values: dict[str, list[float]] = {name: [] for name in _MEAN_FEATURE_NAMES}
        for frame in analysis.features:
            for name in _MEAN_FEATURE_NAMES:
                value = getattr(frame, name)
                if value is not None:
                    values[name].append(float(value))
        feature_means[analysis.track.track_id] = {
            name: float(np.mean(series)) if series else None
            for name, series in values.items()
        }
        if context is not None:
            context_scores[analysis.track.track_id] = track_context_score(analysis, context)
    return MixabilityPrecomputation(
        feature_means=feature_means,
        context_scores=context_scores,
        context=context,
    )


def _append_unique(items: list[str], extra: list[str]) -> None:
    for value in extra:
        if value not in items:
            items.append(value)


def tempo_fit(bpm_a: float | None, bpm_b: float | None) -> float | None:
    """1.0 at equal BPM → 0.0 at 2× tolerance. Checks half/double time too.
    None when either BPM is unknown (never guessed)."""
    if not bpm_a or not bpm_b:
        return None
    ratios = (bpm_b, bpm_b * 2.0, bpm_b / 2.0)  # direct, half-time, double-time
    best = min(abs(bpm_a - r) / bpm_a for r in ratios)
    return float(np.clip(1.0 - best / (2 * _BPM_TOLERANCE), 0.0, 1.0))


def _mean_feature(
    analysis: AnalysisResult,
    name: str,
    precomputed: MixabilityPrecomputation | None = None,
) -> float | None:
    if precomputed is not None:
        track_values = precomputed.feature_means.get(analysis.track.track_id)
        if track_values is not None and name in track_values:
            return track_values[name]
    vals = [getattr(f, name) for f in analysis.features]
    vals = [v for v in vals if v is not None]
    return float(np.mean(vals)) if vals else None


def _window_feature_mean(
    analysis: AnalysisResult,
    name: str,
    window: TransitionWindow | None = None,
) -> float | None:
    values: list[float] = []
    for frame in analysis.features:
        value = getattr(frame, name)
        if value is None:
            continue
        if window is not None and not (window.start_sec <= frame.timestamp_sec <= window.end_sec):
            continue
        values.append(float(value))
    return float(np.mean(values)) if values else None


def energy_fit(
    analysis_a: AnalysisResult,
    analysis_b: AnalysisResult,
    precomputed: MixabilityPrecomputation | None = None,
) -> float | None:
    """Controlled energy difference: similar mean RMS → high fit."""
    a = _mean_feature(analysis_a, "rms", precomputed)
    b = _mean_feature(analysis_b, "rms", precomputed)
    if a is None or b is None:
        return None
    return float(1.0 - abs(a - b) / max(a, b, 1e-9))


def bass_conflict(
    analysis_a: AnalysisResult,
    analysis_b: AnalysisResult,
    precomputed: MixabilityPrecomputation | None = None,
) -> float | None:
    """Conflict risk in [0,1]: high only when BOTH tracks are bass-heavy
    (min of mean LFERs) — one bass-light track defuses the conflict."""
    a = _mean_feature(analysis_a, "low_freq_energy_ratio", precomputed)
    b = _mean_feature(analysis_b, "low_freq_energy_ratio", precomputed)
    if a is None or b is None:
        return None
    return float(np.clip(min(a, b), 0.0, 1.0))


def vocal_conflict(
    analysis_a: AnalysisResult,
    analysis_b: AnalysisResult,
    precomputed: MixabilityPrecomputation | None = None,
) -> float | None:
    """Vocal clash risk in [0,1]: high only when BOTH tracks carry vocals
    (min of mean vocal density) — an instrumental defuses the clash. Mirrors
    bass_conflict. None if either track lacks the proxy."""
    a = _mean_feature(analysis_a, "vocal_density_proxy", precomputed)
    b = _mean_feature(analysis_b, "vocal_density_proxy", precomputed)
    if a is None or b is None:
        return None
    return float(np.clip(min(a, b), 0.0, 1.0))


def style_fit(analysis_a: AnalysisResult, analysis_b: AnalysisResult) -> float | None:
    sa, sb = analysis_a.track.style_label, analysis_b.track.style_label
    if not sa or not sb:
        return None
    return 1.0 if sa == sb else 0.5  # cross-style ≠ bad, just less certain


def _phrase_window_score(
    window: TransitionWindow,
    beatgrid: BeatGrid | None,
    segments: list[Segment],
) -> float | None:
    return window_phrase_score(
        window.start_sec,
        window.end_sec,
        beatgrid,
        segments,
    )


def phrase_fit(
    analysis_a: AnalysisResult,
    analysis_b: AnalysisResult,
    windows_a: list[TransitionWindow],
    windows_b: list[TransitionWindow],
) -> float | None:
    outs = [window for window in windows_a if window.window_type == WindowType.mix_out] or windows_a
    ins = [window for window in windows_b if window.window_type == WindowType.mix_in] or windows_b
    if not outs or not ins:
        return None

    scores: list[float] = []
    for window_a in outs:
        score_a = _phrase_window_score(window_a, analysis_a.beatgrid, analysis_a.segments)
        for window_b in ins:
            score_b = _phrase_window_score(window_b, analysis_b.beatgrid, analysis_b.segments)
            if score_a is None or score_b is None:
                continue
            duration_a = window_a.end_sec - window_a.start_sec
            duration_b = window_b.end_sec - window_b.start_sec
            duration_fit = 1.0 - abs(duration_a - duration_b) / max(duration_a, duration_b, 1e-9)
            scores.append(float(np.clip(0.4 * score_a + 0.4 * score_b + 0.2 * duration_fit, 0.0, 1.0)))
    return max(scores) if scores else None


def tension_fit(
    analysis_a: AnalysisResult,
    analysis_b: AnalysisResult,
    windows_a: list[TransitionWindow],
    windows_b: list[TransitionWindow],
    precomputed: MixabilityPrecomputation | None = None,
) -> float | None:
    outs = [window for window in windows_a if window.window_type == WindowType.mix_out] or windows_a
    ins = [window for window in windows_b if window.window_type == WindowType.mix_in] or windows_b
    if not outs or not ins:
        mean_a = _mean_feature(analysis_a, "tension_proxy", precomputed)
        mean_b = _mean_feature(analysis_b, "tension_proxy", precomputed)
        if mean_a is None or mean_b is None:
            return None
        return float(np.clip(1.0 - abs(mean_a - mean_b), 0.0, 1.0))

    scores: list[float] = []
    for window_a in outs:
        a_tension = _window_feature_mean(analysis_a, "tension_proxy", window_a)
        a_release = _window_feature_mean(analysis_a, "release_proxy", window_a)
        for window_b in ins:
            b_tension = _window_feature_mean(analysis_b, "tension_proxy", window_b)
            if a_tension is None or b_tension is None:
                continue
            continuity = 1.0 - abs(a_tension - b_tension)
            release_handoff = 1.0 - max(0.0, b_tension - (a_release if a_release is not None else a_tension))
            scores.append(float(np.clip(0.7 * continuity + 0.3 * release_handoff, 0.0, 1.0)))
    return max(scores) if scores else None


def pair_window_score(
    m_ix: float,
    window_a: TransitionWindow,
    window_b: TransitionWindow,
    conflict_weights: WeightGroup | None,
) -> float:
    """M_pair = M_ix + W_x(tx) + W_y(ty) − R_conflict.

    v0 R_conflict uses each window's own risk_score for bass/vocal terms;
    phrase/tension conflict terms are zero until those inputs exist.
    """
    r_conflict = 0.0
    if conflict_weights is not None:
        risk = ((window_a.risk_score or 0.0) + (window_b.risk_score or 0.0)) / 2
        w = conflict_weights.weights
        r_conflict = (w.get("bass", 0) + w.get("vocal", 0)) * risk
    return float(m_ix + window_a.score + window_b.score - r_conflict)


def compute_mixability(
    inp: MixabilityInput,
    weights: WeightGroup,
    conflict_weights: WeightGroup | None = None,
    top_pairs: int = 3,
    precomputed: MixabilityPrecomputation | None = None,
) -> MixabilityOutput:
    """Main entry (ticket DoD). Output always carries reasoning, risks,
    best_pair_windows, confidence and warnings."""
    a, b = inp.track_a, inp.track_b
    warnings: list[str] = []
    risks: list[str] = []
    reasoning: list[str] = []
    components: dict[str, float] = {}
    available: dict[str, bool] = {}

    def put(name: str, value: float | None, missing_msg: str, reason_fmt: str):
        if value is None:
            components[name] = _NEUTRAL
            available[name] = False
            warnings.append(missing_msg)
        else:
            components[name] = value
            available[name] = True
            reasoning.append(reason_fmt.format(value))

    put("tempo", tempo_fit(a.track.bpm_estimate, b.track.bpm_estimate),
        "tempo fit unavailable (missing BPM estimate) — neutral", "tempo fit {:.2f}")
    put("energy", energy_fit(a, b, precomputed),
        "energy fit unavailable (no rms) — neutral", "energy fit {:.2f}")

    phrase_value = phrase_fit(a, b, inp.transition_windows_a, inp.transition_windows_b)
    put(
        "phrase",
        phrase_value,
        "phrase fit unavailable (no phrase-aware windows or phrase anchors) — neutral",
        "phrase fit {:.2f}",
    )
    if phrase_value is not None and phrase_value < 0.45:
        risks.append(f"weak phrase alignment ({phrase_value:.2f})")

    bass_risk = bass_conflict(a, b, precomputed)
    if bass_risk is None:
        components["bass"] = _NEUTRAL
        available["bass"] = False
        warnings.append("bass conflict unavailable (no LFER) — neutral")
    else:
        components["bass"] = 1.0 - bass_risk
        available["bass"] = True
        reasoning.append(f"bass conflict {bass_risk:.2f}")
        if bass_risk > 0.6:
            risks.append(f"high bass conflict ({bass_risk:.2f}) — both tracks bass-heavy")
        elif bass_risk > 0.4:
            risks.append(f"moderate bass conflict ({bass_risk:.2f})")

    put("style", style_fit(a, b),
        "style fit unavailable (missing style labels) — neutral", "style fit {:.2f}")

    # S_vocal — compatibility = 1 − clash risk (both-vocal tracks clash)
    vocal_risk = vocal_conflict(a, b, precomputed)
    if vocal_risk is None:
        components["vocal"] = _NEUTRAL
        available["vocal"] = False
        warnings.append("vocal conflict unavailable (no vocal density) — neutral")
    else:
        components["vocal"] = 1.0 - vocal_risk
        available["vocal"] = True
        reasoning.append(f"vocal clash {vocal_risk:.2f}")
        if vocal_risk > 0.5:
            risks.append(f"high vocal clash ({vocal_risk:.2f}) — both tracks carry vocals")

    # S_harmonic — Camelot key compatibility (Sprint 5.1 hotfix). Exposure proxy
    # = mean vocal density of both tracks (vocals expose harmonic content).
    exposure = None
    va = _mean_feature(a, "vocal_density_proxy", precomputed)
    vb = _mean_feature(b, "vocal_density_proxy", precomputed)
    if va is not None and vb is not None:
        exposure = (va + vb) / 2
    harm = harmonic_compatibility(
        a.track.key_estimate, b.track.key_estimate,
        a.track.key_confidence, b.track.key_confidence, exposure,
    )
    if a.track.key_estimate is None or b.track.key_estimate is None:
        components["harmonic"] = _NEUTRAL
        available["harmonic"] = False
        warnings.append("harmonic compatibility unavailable (missing key) — neutral")
    else:
        components["harmonic"] = harm.harmonic_compatibility_score
        available["harmonic"] = True
        reasoning.append(
            f"harmonic {harm.harmonic_relation} ({harm.key_a}->{harm.key_b}) "
            f"score {harm.harmonic_compatibility_score:.2f} risk {harm.harmonic_risk:.2f}"
        )
        if harm.harmonic_risk > 0.5:
            risks.append(f"harmonic risk {harm.harmonic_risk:.2f} — {harm.harmonic_relation} key move")
        if harm.harmonic_warning:
            warnings.append(harm.harmonic_warning)

    tension_value = tension_fit(
        a,
        b,
        inp.transition_windows_a,
        inp.transition_windows_b,
        precomputed,
    )
    put(
        "tension",
        tension_value,
        "tension fit unavailable (no tension/release curves) — neutral",
        "tension fit {:.2f}",
    )
    if tension_value is not None and tension_value < 0.45:
        risks.append(f"awkward tension handoff ({tension_value:.2f})")

    context_fit_score = None
    if inp.context is None:
        components["context"] = _NEUTRAL
        available["context"] = False
        warnings.append("context fit unavailable (no context profile) — neutral")
    else:
        context_cache = precomputed if precomputed is not None and precomputed.context == inp.context else None
        ctx_a = context_cache.context_scores.get(a.track.track_id) if context_cache is not None else None
        ctx_b = context_cache.context_scores.get(b.track.track_id) if context_cache is not None else None
        if ctx_a is None:
            ctx_a = track_context_score(a, inp.context)
        if ctx_b is None:
            ctx_b = track_context_score(b, inp.context)
        ctx_value = (ctx_a.value + ctx_b.value) / 2
        context_fit_score = round(ctx_value, 4)
        components["context"] = context_fit_score
        available["context"] = True
        reasoning.append(
            f"context fit {ctx_value:.2f} "
            f"({a.track.track_id}={ctx_a.value:.2f}, {b.track.track_id}={ctx_b.value:.2f})"
        )
        _append_unique(warnings, ctx_a.warnings)
        _append_unique(warnings, ctx_b.warnings)

    w = weights.weights
    m_ix = float(sum(w[name] * components[name] for name in COMPONENTS))
    coverage = sum(1 for name in COMPONENTS if available.get(name, False)) / len(COMPONENTS)
    confidence = round(coverage * 0.8, 2)
    pair_rules = evaluate_pair_rules(
        bpm_a=a.track.bpm_estimate,
        bpm_b=b.track.bpm_estimate,
        harmonic_risk=harm.harmonic_risk if a.track.key_estimate and b.track.key_estimate else None,
        vocal_risk=vocal_risk,
        bass_risk=bass_risk,
        phrase_fit=phrase_value,
        tension_fit=tension_value,
    )
    pair_policy = evaluate_pair_policy(
        confidence=confidence,
        pair_rules=pair_rules,
        harmonic_risk=harm.harmonic_risk if a.track.key_estimate and b.track.key_estimate else None,
        vocal_risk=vocal_risk,
        bass_risk=bass_risk,
        phrase_fit=phrase_value,
        tension_fit=tension_value,
        score_value=m_ix,
    )
    _append_unique(risks, pair_rules.flags)
    if pair_rules.flags:
        reasoning.append(
            "shared rules: "
            + "; ".join(pair_rules.flags)
            + f" (penalty {pair_rules.penalty:.2f})"
        )
    if pair_policy.reasons:
        reasoning.append(
            "recommendation policy: "
            + pair_policy.recommendation_policy.value
            + " because "
            + "; ".join(pair_policy.reasons)
        )

    # pair windows: mix_out (or any) of A × mix_in (or any) of B
    outs = [x for x in inp.transition_windows_a if x.window_type == WindowType.mix_out] \
        or inp.transition_windows_a
    ins = [x for x in inp.transition_windows_b if x.window_type == WindowType.mix_in] \
        or inp.transition_windows_b
    pairs = sorted(
        (
            PairWindow(
                track_a_window=(wa.start_sec, wa.end_sec),
                track_b_window=(wb.start_sec, wb.end_sec),
                pair_score=round(pair_window_score(m_ix, wa, wb, conflict_weights), 4),
                explanation=f"M_pair = M_ix + W_a({wa.window_type.value}) + W_b({wb.window_type.value}) − R_conflict",
            )
            for wa in outs
            for wb in ins
        ),
        key=lambda p: -p.pair_score,
    )[:top_pairs]
    if not pairs:
        warnings.append("no transition windows provided — best_pair_windows empty")

    warnings += guardrail_warnings(
        has_context=inp.context is not None,
        source_grounding=coverage,
        conflicting=bool(risks),
    )
    return MixabilityOutput(
        track_id_a=a.track.track_id,
        track_id_b=b.track.track_id,
        mixability_score=round(m_ix, 4),
        confidence=confidence,
        best_pair_windows=pairs,
        risks=risks,
        reasoning=reasoning + [f"input coverage {coverage:.0%} of {len(COMPONENTS)} components"],
        warnings=warnings,
        model_version=MODEL_VERSION,
        provenance=provenance_for("mixability"),
        tempo_fit=components["tempo"] if available.get("tempo") else None,
        phrase_fit=components["phrase"] if available.get("phrase") else None,
        energy_fit=components["energy"] if available.get("energy") else None,
        tension_fit=components["tension"] if available.get("tension") else None,
        style_fit=components["style"] if available.get("style") else None,
        context_fit_score=context_fit_score,
        bass_conflict_risk=bass_risk,
        vocal_clash_risk=vocal_risk,
        harmonic_relation=harm.harmonic_relation,
        harmonic_risk=harm.harmonic_risk,
        key_a=a.track.key_estimate,
        key_b=b.track.key_estimate,
        key_confidence_min=harm.key_confidence_min,
        tempo_relation=pair_rules.tempo_relation,
        bpm_delta_pct=pair_rules.bpm_delta_pct,
        effective_bpm_delta_pct=pair_rules.effective_bpm_delta_pct,
        tempo_gate_status=pair_rules.tempo_gate_status,
        harmonic_gate_status=pair_rules.harmonic_gate_status,
        standard_blend_allowed=pair_rules.standard_blend_allowed,
        rule_flags=pair_rules.flags,
        hard_block=pair_rules.hard_block,
        rule_penalty=pair_rules.penalty,
        recommendation_policy=pair_policy.recommendation_policy,
        policy_reasons=pair_policy.reasons,
    )
