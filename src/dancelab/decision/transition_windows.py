"""Transition Windows Engine v0.1 (Sprint 2 — Engineering Ticket).

    W(t) = g1*S_struct + g2*S_rhythm + g3*S_energy + g4*S_phrase + g5*S_bass
           - g6*S_vocal_risk - g7*S_tension_conflict
    windows = TopK(localmax(W))

STATUS: candidate (Transition Windows Model v0.1) — experimental, ADR-005.

Core principle (C008 / H018): a good transition window is NOT just a
low-energy moment — structure, rhythm, energy, bass, vocals, tension and
context must not fight each other.

Honesty contract: components computable from the provided inputs are computed;
unavailable components get a NEUTRAL value and an explicit warning, confidence
is scaled by input coverage. Nothing is silently invented.
"""

from __future__ import annotations

import numpy as np

from dancelab.core.config import WeightGroup
from dancelab.core.models import (
    ContextProfile,
    ModelStatus,
    TempoFeasibility,
    TransitionStrategy,
    TransitionWindow,
    TransitionWindowInput,
    TransitionWindowOutput,
    WindowType,
)
from dancelab.core.normalization import minmax_01 as _minmax
from dancelab.core.normalization import robust_01 as _robust
from dancelab.core.phrasing import phrase_alignment_curve
from dancelab.core.provenance import guardrail_warnings, provenance_for

MODEL_VERSION = "transition_windows_v0.1"
STATUS = "candidate"

POSITIVE_COMPONENTS = ("structural", "rhythm", "energy", "phrase", "bass")
PENALTY_COMPONENTS = ("vocal_risk", "tension_conflict")

_NEUTRAL_POSITIVE = 0.5  # unknown quality → middle of [0,1]
_NEUTRAL_PENALTY = 0.0  # unknown risk → no penalty, but confidence drops


def _rolling_std(x: np.ndarray, w: int = 5) -> np.ndarray:
    pad = w // 2
    xp = np.pad(x, pad, mode="edge")
    return np.array([xp[i : i + w].std() for i in range(len(x))])


def compute_components(
    inp: TransitionWindowInput,
) -> tuple[dict[str, np.ndarray], np.ndarray, list[str]]:
    """Build the seven component curves from available inputs.

    Returns (components, times_sec, warnings). Missing inputs → neutral curve
    + warning; the caller lowers confidence accordingly.
    """
    frames = sorted(inp.feature_frames, key=lambda f: f.timestamp_sec)
    times = np.array([f.timestamp_sec for f in frames], dtype=np.float64)
    n = len(frames)
    warnings: list[str] = []
    comp: dict[str, np.ndarray] = {}

    def col(name: str) -> np.ndarray | None:
        vals = [getattr(f, name) for f in frames]
        if any(v is None for v in vals):
            return None
        return np.array(vals, dtype=np.float64)

    # S_energy — controlled energy change: stable RMS is transition-friendly
    rms = col("rms")
    if rms is not None:
        comp["energy"] = 1.0 - _minmax(np.abs(np.gradient(rms)))
    else:
        comp["energy"] = np.full(n, _NEUTRAL_POSITIVE)
        warnings.append("energy component unavailable (no rms) — neutral")

    # S_bass — freedom from bass conflict: low relative bass energy scores high.
    # Robust percentile norm: bass energy is spiky (drops), outliers must not
    # crush the scale (Normalization Protocol v0.1).
    bass = col("bass_energy")
    if bass is not None:
        comp["bass"] = 1.0 - _robust(bass)
    else:
        comp["bass"] = np.full(n, _NEUTRAL_POSITIVE)
        warnings.append("bass component unavailable (no bass_energy) — neutral")

    # S_rhythm — v0 proxy: spectral-flux stability (beat-level stability needs beatgrid)
    flux = col("spectral_flux")
    if flux is not None:
        comp["rhythm"] = 1.0 - _minmax(_rolling_std(flux))
        if inp.beatgrid is None:
            warnings.append("rhythm stability is a spectral-flux proxy (no beatgrid)")
    else:
        comp["rhythm"] = np.full(n, _NEUTRAL_POSITIVE)
        warnings.append("rhythm component unavailable (no spectral_flux) — neutral")

    # S_struct — proximity to segment boundaries (segments = intro/build/drop/... map)
    if inp.segments:
        boundaries = sorted({s.start_sec for s in inp.segments} | {s.end_sec for s in inp.segments})
        dist = np.min(
            np.abs(times[:, None] - np.array(boundaries)[None, :]), axis=1
        )
        comp["structural"] = np.exp(-dist / 8.0)  # within ~8 s of a boundary scores high
    else:
        comp["structural"] = np.full(n, _NEUTRAL_POSITIVE)
        warnings.append("structural component unavailable (no segment map) — neutral")

    # S_phrase — beatgrid phrase anchors, strengthened by structural boundaries.
    phrase_curve = phrase_alignment_curve(times, inp.beatgrid, inp.segments)
    if phrase_curve is not None:
        comp["phrase"] = phrase_curve
        if inp.beatgrid is None and inp.segments:
            warnings.append("phrase alignment uses segment-boundary fallback (no beatgrid)")
    else:
        comp["phrase"] = np.full(n, _NEUTRAL_POSITIVE)
        if inp.segments:
            warnings.append("phrase component unavailable (no beatgrid/phrase anchors) — neutral")
        else:
            warnings.append("phrase component unavailable (no beatgrid or segment map) — neutral")

    # S_vocal_risk — vocal density at candidate time
    vocal = col("vocal_density_proxy")
    if vocal is not None:
        comp["vocal_risk"] = np.clip(vocal, 0.0, 1.0)
    else:
        comp["vocal_risk"] = np.full(n, _NEUTRAL_PENALTY)
        warnings.append("vocal risk unavailable (no vocal_density_proxy) — no penalty applied")

    # S_tension_conflict — cutting into high tension breaks the arc
    tension = col("tension_proxy")
    if tension is not None:
        comp["tension_conflict"] = _robust(tension)
    else:
        comp["tension_conflict"] = np.full(n, _NEUTRAL_PENALTY)
        warnings.append("tension conflict unavailable (no tension_proxy) — no penalty applied")

    return comp, times, warnings


def score_transition(components: dict[str, np.ndarray], weights: WeightGroup) -> np.ndarray:
    """Pure weighted sum per Transition Windows Model v0.1. Unit-testable."""
    w = weights.weights
    score = np.zeros_like(next(iter(components.values())), dtype=np.float64)
    for name in POSITIVE_COMPONENTS:
        score += w[name] * components[name]
    for name in PENALTY_COMPONENTS:
        score -= w[name] * components[name]
    return score


def local_maxima(score: np.ndarray) -> np.ndarray:
    """Indices of strict local maxima (plateaus: first index). Endpoints excluded."""
    if len(score) < 3:
        return np.array([], dtype=int)
    left = score[1:-1] > score[:-2]
    right = score[1:-1] >= score[2:]
    return np.where(left & right)[0] + 1


def top_k_windows(
    score: np.ndarray,
    times: np.ndarray,
    k: int,
    half_width_sec: float = 8.0,
    min_separation_sec: float | None = None,
) -> list[tuple[int, float, float]]:
    """TopK(localmax(W)) → [(peak_idx, start_sec, end_sec)], best first.

    Greedy non-maximum suppression: peaks closer than min_separation_sec
    (default: window width) to an already selected peak are skipped, so the
    top-K windows are distinct moments, not one moment counted twice.
    """
    peaks = local_maxima(score)
    if len(peaks) == 0:
        return []
    min_sep = 2 * half_width_sec if min_separation_sec is None else min_separation_sec
    selected: list[int] = []
    for idx in peaks[np.argsort(score[peaks])[::-1]]:
        if any(abs(times[idx] - times[j]) < min_sep for j in selected):
            continue
        selected.append(int(idx))
        if len(selected) == k:
            break
    out = []
    for idx in selected:
        start = max(float(times[0]), float(times[idx]) - half_width_sec)
        end = min(float(times[-1]), float(times[idx]) + half_width_sec)
        out.append((idx, start, end))
    return out


def _window_type(peak_sec: float, duration_sec: float) -> WindowType:
    """v0 position heuristic; segment-type-aware typing is Sprint 3."""
    if duration_sec <= 0:
        return WindowType.unknown
    pos = peak_sec / duration_sec
    if pos < 1 / 3:
        return WindowType.mix_in
    if pos > 2 / 3:
        return WindowType.mix_out
    return WindowType.bridge


def _role_window_fit(
    profile: ContextProfile,
    *,
    window_type: WindowType,
    score_norm: float,
    energy: float,
    bass_freedom: float,
    vocal_risk: float,
    risk: float,
) -> float:
    role = (profile.set_role or "").strip().lower() or "builder"
    mix_in = 1.0 if window_type == WindowType.mix_in else 0.45 if window_type == WindowType.bridge else 0.1
    mix_out = 1.0 if window_type == WindowType.mix_out else 0.45 if window_type == WindowType.bridge else 0.1
    bridge = 1.0 if window_type == WindowType.bridge else 0.2
    low_risk = 1.0 - risk
    low_vocal = 1.0 - vocal_risk
    if role == "opener":
        return float(np.clip(0.35 * mix_in + 0.25 * energy + 0.20 * bass_freedom + 0.20 * low_vocal, 0.0, 1.0))
    if role == "peak":
        return float(np.clip(0.30 * max(mix_out, bridge) + 0.25 * score_norm + 0.15 * energy + 0.15 * bass_freedom + 0.15 * low_risk, 0.0, 1.0))
    if role == "closer":
        return float(np.clip(0.35 * mix_out + 0.20 * bass_freedom + 0.20 * low_vocal + 0.15 * low_risk + 0.10 * energy, 0.0, 1.0))
    return float(np.clip(0.25 * max(mix_in, bridge) + 0.25 * energy + 0.20 * bass_freedom + 0.15 * score_norm + 0.15 * low_risk, 0.0, 1.0))


def _infer_compatible_contexts(
    *,
    profiles: list[ContextProfile],
    current_context: ContextProfile | None,
    window_type: WindowType,
    score_norm: float,
    energy: float,
    bass_freedom: float,
    vocal_risk: float,
    risk: float,
) -> list[str]:
    if not profiles:
        return [current_context.context_id] if current_context else []
    scored = [
        (
            profile.context_id,
            _role_window_fit(
                profile,
                window_type=window_type,
                score_norm=score_norm,
                energy=energy,
                bass_freedom=bass_freedom,
                vocal_risk=vocal_risk,
                risk=risk,
            ),
        )
        for profile in profiles
    ]
    compatible = [context_id for context_id, fit in scored if fit >= 0.60]
    if not compatible and scored:
        best_id, best_fit = max(scored, key=lambda item: item[1])
        if best_fit >= 0.52:
            compatible = [best_id]
    if current_context is not None:
        current_fit = next((fit for context_id, fit in scored if context_id == current_context.context_id), None)
        if current_fit is not None and current_fit >= 0.55 and current_context.context_id not in compatible:
            compatible.append(current_context.context_id)
    return sorted(set(compatible))


def _window_strategy_hints(
    window_type: WindowType,
    *,
    bass_freedom: float,
    vocal_risk: float,
    risk: float,
) -> list[TransitionStrategy]:
    if risk >= 0.7 or vocal_risk >= 0.7:
        return [TransitionStrategy.echo_out, TransitionStrategy.hard_cut]
    if window_type == WindowType.bridge:
        return [TransitionStrategy.break_transition, TransitionStrategy.short_blend]
    if window_type == WindowType.mix_out and bass_freedom >= 0.65 and vocal_risk <= 0.35:
        return [TransitionStrategy.standard_blend, TransitionStrategy.short_blend]
    if window_type == WindowType.mix_in:
        return [TransitionStrategy.short_blend, TransitionStrategy.tool_mix]
    return [TransitionStrategy.short_blend]


def detect_transition_windows(
    inp: TransitionWindowInput,
    weights: WeightGroup,
    top_k: int = 3,
    half_width_sec: float = 8.0,
) -> TransitionWindowOutput:
    """Main entry (Engineering Ticket DoD). Output always carries reasoning,
    risk_score, confidence and warnings."""
    provenance = provenance_for("transition_windows")
    if len(inp.feature_frames) < 3:
        return TransitionWindowOutput(
            track_id=inp.track_id,
            windows=[],
            model_version=MODEL_VERSION,
            warnings=["track too short for transition analysis (<3 feature frames)"],
            provenance=provenance,
        )

    components, times, warnings = compute_components(inp)
    score = score_transition(components, weights)
    duration = float(times[-1])

    # input coverage drives confidence: 7 components, count the neutral ones
    n_missing = sum(1 for w in warnings if "unavailable" in w)
    coverage = (7 - n_missing) / 7
    warnings += guardrail_warnings(
        has_beatgrid=inp.beatgrid is not None,
        has_context=inp.context is not None,
        source_grounding=coverage,
    )

    windows: list[TransitionWindow] = []
    for rank, (idx, start, end) in enumerate(
        top_k_windows(score, times, top_k, half_width_sec), start=1
    ):
        window_type = _window_type(float(times[idx]), duration)
        reasoning = [
            f"{name}={components[name][idx]:.2f}" for name in POSITIVE_COMPONENTS
        ] + [f"{name} penalty={components[name][idx]:.2f}" for name in PENALTY_COMPONENTS]
        w_warnings = []
        vocal_at = float(components["vocal_risk"][idx])
        if vocal_at > 0.6:
            w_warnings.append(f"high vocal density in window ({vocal_at:.2f})")
        risk = float(
            np.clip(
                0.5 * components["vocal_risk"][idx]
                + 0.3 * components["tension_conflict"][idx]
                + 0.1 * n_missing,
                0.0,
                1.0,
            )
        )
        compatible_contexts = _infer_compatible_contexts(
            profiles=inp.available_contexts,
            current_context=inp.context,
            window_type=window_type,
            score_norm=float(np.clip(score[idx], 0.0, 1.0)),
            energy=float(np.clip(components["energy"][idx], 0.0, 1.0)),
            bass_freedom=float(np.clip(components["bass"][idx], 0.0, 1.0)),
            vocal_risk=vocal_at,
            risk=risk,
        )
        windows.append(
            TransitionWindow(
                transition_window_id=f"{inp.track_id}_tw{rank}",
                start_sec=round(start, 2),
                end_sec=round(end, 2),
                score=round(float(score[idx]), 4),
                status=ModelStatus.candidate,
                window_type=window_type,
                confidence=round(float(np.clip(coverage * 0.8, 0.0, 1.0)), 2),
                risk_score=round(risk, 2),
                reasoning=reasoning,
                warnings=w_warnings,
                compatible_contexts=compatible_contexts,
                tempo_window_feasibility=TempoFeasibility.medium,
                recommended_strategies=_window_strategy_hints(
                    window_type,
                    bass_freedom=float(np.clip(components["bass"][idx], 0.0, 1.0)),
                    vocal_risk=vocal_at,
                    risk=risk,
                ),
                explanation=(
                    f"local maximum #{rank} of W_transition "
                    f"({MODEL_VERSION}, input coverage {coverage:.0%})"
                ),
            )
        )

    return TransitionWindowOutput(
        track_id=inp.track_id,
        windows=windows,
        model_version=MODEL_VERSION,
        warnings=warnings,
        provenance=provenance,
    )
