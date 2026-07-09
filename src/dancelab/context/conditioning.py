"""Context conditioning: C_fit and X_eff = X_audio * C_fit (Core Equations).

STATUS: candidate — a heuristic context-fit model built from the descriptors we
actually have today (RMS, bass profile, vocal activity proxy, optional style
label). It is explicitly NOT a crowd-response predictor.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

import numpy as np

from dancelab.core.models import (
    AnalysisResult,
    ContextEvaluation,
    ContextProfile,
    ModelStatus,
    ScoredOutput,
)
from dancelab.core.provenance import guardrail_warnings, provenance_for

STATUS = "candidate"
MODEL_VERSION = "context_evaluation_v0.1"
_DEFAULT_ROLE = "builder"
_ROLE_TARGETS = {
    "opener": {"energy_start": 0.20, "energy_end": 0.45, "bass": 0.35, "vocal": 0.45},
    "builder": {"energy_start": 0.40, "energy_end": 0.72, "bass": 0.55, "vocal": 0.30},
    "bridge": {"energy_start": 0.45, "energy_end": 0.58, "bass": 0.42, "vocal": 0.35},
    "peak": {"energy_start": 0.72, "energy_end": 0.92, "bass": 0.75, "vocal": 0.20},
    "reset": {"energy_start": 0.35, "energy_end": 0.22, "bass": 0.30, "vocal": 0.35},
    "closer": {"energy_start": 0.58, "energy_end": 0.32, "bass": 0.45, "vocal": 0.50},
    "tool": {"energy_start": 0.35, "energy_end": 0.50, "bass": 0.40, "vocal": 0.25},
}
_ROLE_PROBES = ("opener", "builder", "peak", "closer")
_CROWD_ENERGY_SHIFT = {"low": -0.10, "medium": 0.00, "high": 0.10, "descending": -0.06}
_VENUE_BASS_SHIFT = {"club": 0.00, "festival": 0.05}


@dataclass(frozen=True)
class ContextScoreSummary:
    value: float
    confidence: float
    reasoning: list[str]
    warnings: list[str]
    style_fit: float
    role_fits: dict[str, float]


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def _descriptor_length(descriptors: dict[str, np.ndarray]) -> int:
    for value in descriptors.values():
        arr = np.asarray(value, dtype=float).reshape(-1)
        if arr.size:
            return int(arr.size)
    return 0


def _normalize01(values: np.ndarray, default: float = 0.5) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    if arr.size == 0:
        return arr
    mask = ~np.isnan(arr)
    if not mask.any():
        return np.full(arr.shape, default, dtype=float)
    filled = arr.copy()
    mean = float(np.nanmean(filled))
    filled[~mask] = mean
    lo = float(np.nanmin(filled))
    hi = float(np.nanmax(filled))
    if hi - lo < 1e-9:
        return np.full(filled.shape, default, dtype=float)
    return np.clip((filled - lo) / (hi - lo), 0.0, 1.0)


def _bounded_descriptor(
    descriptors: dict[str, np.ndarray], name: str, length: int, default: float = 0.5
) -> tuple[np.ndarray, bool]:
    raw = descriptors.get(name)
    if raw is None:
        return np.full(length, default, dtype=float), False
    arr = np.asarray(raw, dtype=float).reshape(-1)
    if arr.size == 0 or np.all(np.isnan(arr)):
        return np.full(length, default, dtype=float), False
    if arr.size != length:
        xs = np.linspace(0.0, 1.0, arr.size)
        target = np.linspace(0.0, 1.0, length)
        valid = ~np.isnan(arr)
        if valid.any():
            arr = np.interp(target, xs[valid], arr[valid])
        else:
            return np.full(length, default, dtype=float), False
    mean = float(np.nanmean(arr))
    arr = np.where(np.isnan(arr), mean, arr)
    return np.clip(arr, 0.0, 1.0), True


def _start_hour(time_of_night: str | None) -> int | None:
    if not time_of_night:
        return None
    match = re.match(r"^\s*(\d{1,2}):\d{2}", time_of_night)
    if not match:
        return None
    return int(match.group(1))


def _infer_role(context: ContextProfile) -> str:
    role = (context.set_role or "").strip().lower()
    if role in _ROLE_TARGETS:
        return role

    hour = _start_hour(context.time_of_night)
    crowd = (context.crowd_energy or "").strip().lower()
    if crowd == "high" or (hour is not None and 0 <= hour < 3):
        return "peak"
    if crowd == "descending" or (hour is not None and 4 <= hour <= 8):
        return "closer"
    if crowd == "low" or (hour is not None and (hour >= 22 or hour < 1)):
        return "opener"
    return _DEFAULT_ROLE


def _target_profile(context: ContextProfile, length: int) -> dict[str, np.ndarray]:
    role = _infer_role(context)
    base = _ROLE_TARGETS.get(role, _ROLE_TARGETS[_DEFAULT_ROLE])
    energy = np.linspace(base["energy_start"], base["energy_end"], length)
    energy += _CROWD_ENERGY_SHIFT.get((context.crowd_energy or "").strip().lower(), 0.0)

    hour = _start_hour(context.time_of_night)
    if hour is not None:
        if 0 <= hour < 3:
            energy += 0.04
        elif 4 <= hour <= 8:
            energy -= 0.05
        elif 14 <= hour < 18:
            energy -= 0.02

    bass = np.full(length, base["bass"], dtype=float)
    bass += _VENUE_BASS_SHIFT.get((context.venue_type or "").strip().lower(), 0.0)
    vocal = np.full(length, base["vocal"], dtype=float)
    return {
        "energy": np.clip(energy, 0.0, 1.0),
        "bass": np.clip(bass, 0.0, 1.0),
        "vocal": np.clip(vocal, 0.0, 1.0),
    }


def _style_fit(style_label: str | None, style_focus: list[str]) -> float:
    if not style_focus:
        return 0.5
    if not style_label:
        return 0.5
    style = style_label.strip().lower()
    focuses = [value.strip().lower() for value in style_focus if value.strip()]
    if style in focuses:
        return 1.0
    if any(style in focus or focus in style for focus in focuses):
        return 0.8
    style_tokens = {tok for tok in re.split(r"[\s/_-]+", style) if tok}
    focus_tokens = {tok for focus in focuses for tok in re.split(r"[\s/_-]+", focus) if tok}
    if style_tokens & focus_tokens:
        return 0.65
    return 0.35


def analysis_descriptors(analysis: AnalysisResult) -> dict[str, np.ndarray]:
    frames = sorted(analysis.features, key=lambda frame: frame.timestamp_sec)

    def series(name: str) -> np.ndarray:
        return np.array(
            [getattr(frame, name) if getattr(frame, name) is not None else np.nan for frame in frames],
            dtype=float,
        )

    return {
        "rms": _normalize01(series("rms")),
        "low_freq_energy_ratio": series("low_freq_energy_ratio"),
        "vocal_density_proxy": series("vocal_density_proxy"),
    }


def context_fit(descriptors: dict[str, np.ndarray], context: ContextProfile) -> np.ndarray:
    """C_fit(t|c) ∈ [0, 1].

    Candidate implementation: fit a track's normalized energy, bass, and vocal
    curves to a role-conditioned target profile derived from the context.
    """
    length = _descriptor_length(descriptors)
    if length == 0:
        return np.array([], dtype=float)

    targets = _target_profile(context, length)
    energy, _ = _bounded_descriptor(descriptors, "rms", length)
    bass, _ = _bounded_descriptor(descriptors, "low_freq_energy_ratio", length)
    vocal, _ = _bounded_descriptor(descriptors, "vocal_density_proxy", length, default=0.35)

    energy_fit = 1.0 - np.abs(energy - targets["energy"])
    bass_fit = 1.0 - np.abs(bass - targets["bass"])
    vocal_fit = 1.0 - np.abs(vocal - targets["vocal"])
    curve = 0.65 * energy_fit + 0.20 * bass_fit + 0.15 * vocal_fit
    return np.clip(curve, 0.0, 1.0)


def track_context_score(analysis: AnalysisResult, context: ContextProfile) -> ContextScoreSummary:
    descriptors = analysis_descriptors(analysis)
    length = _descriptor_length(descriptors)
    warnings: list[str] = []

    if length == 0:
        style_fit = _style_fit(analysis.track.style_label, context.style_focus)
        warnings.append("no feature frames — context fit defaults to neutral")
        return ContextScoreSummary(
            value=round(0.5 * 0.85 + style_fit * 0.15, 4),
            confidence=0.2,
            reasoning=["no descriptor frames available — candidate context fit is mostly neutral"],
            warnings=warnings,
            style_fit=round(style_fit, 4),
            role_fits={role: 0.5 for role in _ROLE_PROBES},
        )

    available = 0
    for name, msg in (
        ("rms", "energy descriptor unavailable — context fit leans neutral"),
        ("low_freq_energy_ratio", "bass descriptor unavailable — context fit leans neutral"),
        ("vocal_density_proxy", "vocal descriptor unavailable — context fit leans neutral"),
    ):
        raw = descriptors.get(name)
        if raw is not None and raw.size and not np.all(np.isnan(raw)):
            available += 1
        else:
            warnings.append(msg)

    curve = context_fit(descriptors, context)
    base_value = float(curve.mean()) if curve.size else 0.5
    style_fit = _style_fit(analysis.track.style_label, context.style_focus)
    value = float(np.clip(0.85 * base_value + 0.15 * style_fit, 0.0, 1.0))

    role_fits: dict[str, float] = {}
    for role in _ROLE_PROBES:
        probe_context = ContextProfile(
            context_id=f"{context.context_id}:{role}",
            venue_type=context.venue_type,
            set_role=role,
            time_of_night=context.time_of_night,
            crowd_energy=context.crowd_energy,
            style_focus=context.style_focus,
        )
        probe_curve = context_fit(descriptors, probe_context)
        role_fits[role] = round(float(probe_curve.mean()) if probe_curve.size else 0.5, 4)

    coverage = available / 3.0
    style_known = 1.0 if (not context.style_focus or analysis.track.style_label) else 0.6
    confidence = float(np.clip(0.30 + 0.45 * coverage + 0.15 * style_known, 0.0, 1.0))
    reasoning = [
        f"context role {_infer_role(context)}",
        f"mean role-conditioned fit {base_value:.2f}",
        f"style fit {style_fit:.2f}",
        "role probes: " + ", ".join(f"{role}={score:.2f}" for role, score in role_fits.items()),
    ]

    if context.style_focus and not analysis.track.style_label:
        warnings.append("style label missing — style-context fit is neutral")

    return ContextScoreSummary(
        value=round(value, 4),
        confidence=round(confidence, 2),
        reasoning=reasoning,
        warnings=_dedupe(warnings),
        style_fit=round(style_fit, 4),
        role_fits=role_fits,
    )


def _score(value: float, confidence: float, explanation: str) -> ScoredOutput:
    return ScoredOutput(
        value=round(value, 4),
        status=ModelStatus.candidate,
        confidence=round(confidence, 2),
        explanation=explanation,
    )


def evaluate_context(analysis: AnalysisResult, context: ContextProfile) -> ContextEvaluation:
    summary = track_context_score(analysis, context)
    role_fits = summary.role_fits
    role = _infer_role(context)
    sorted_roles = sorted(role_fits.items(), key=lambda item: -item[1])
    top_score = sorted_roles[0][1] if sorted_roles else summary.value
    second_score = sorted_roles[1][1] if len(sorted_roles) > 1 else top_score
    requested_fit = role_fits.get(role, summary.value)
    role_margin = max(0.0, top_score - second_score)
    risk = float(np.clip(0.50 * (1.0 - summary.value) + 0.30 * (1.0 - role_margin) +
                         0.20 * (1.0 - summary.style_fit), 0.0, 1.0))

    warnings = list(summary.warnings)
    if role_fits and role not in {sorted_roles[0][0]} and top_score - requested_fit > 0.12:
        warnings.append(
            f"track profile leans more toward '{sorted_roles[0][0]}' than requested '{role}'"
        )
    warnings += guardrail_warnings(
        has_context=True,
        source_grounding=summary.confidence,
        conflicting=role_margin < 0.08,
        risk_score=risk,
    )

    return ContextEvaluation(
        track_id=analysis.track.track_id,
        context_id=context.context_id,
        context_fit=_score(
            summary.value,
            summary.confidence,
            f"mean context fit {summary.value:.2f}; role '{role}' target {requested_fit:.2f}; "
            f"style fit {summary.style_fit:.2f}",
        ),
        peak_time_fit=_score(
            role_fits.get("peak", 0.5),
            summary.confidence,
            "fit against the peak-time target profile",
        ),
        opening_fit=_score(
            role_fits.get("opener", 0.5),
            summary.confidence,
            "fit against the opening / warm-up target profile",
        ),
        closing_fit=_score(
            role_fits.get("closer", 0.5),
            summary.confidence,
            "fit against the closing / descent target profile",
        ),
        risk_score=_score(
            risk,
            summary.confidence,
            "risk rises when requested context fit is low, role fit is ambiguous, "
            "or the style-context match is weak",
        ),
        model_version=MODEL_VERSION,
        warnings=_dedupe(warnings),
        provenance=provenance_for("context_evaluation"),
    )


def condition(curve: np.ndarray, c_fit: np.ndarray) -> np.ndarray:
    """X_eff(t|s,c) = X_audio(t|s) * C_fit(t|c)."""
    if curve.shape != c_fit.shape:
        raise ValueError("curve and c_fit must have the same shape")
    return curve * c_fit
