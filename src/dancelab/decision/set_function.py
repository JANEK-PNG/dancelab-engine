"""Set Function Engine v0.1 (Sprint 2 Final — Engineering Ticket).

Roles R = {opener, builder, bridge, peak, reset, closer, tool}
    S_r(x,c) = w_r · φ(x) + b_r − R_r(x,c)
    confidence = softmax(S_r*) over all roles

STATUS: candidate. Model note: "Na start może być regułowy / heurystyczny.
ML dopiero po zebraniu etykiet set function." — this IS the rule-based start.
Claim C010: track role is not a fixed property — context shifts it.

φ(x) in v0 uses only implemented features (energy shape over time, LFER,
transition-window quality); heuristic role weights are hand-set priors to be
replaced by fits against EXP011 labels. Every output carries reasoning,
confidence, risk and warnings.
"""

from __future__ import annotations

import numpy as np

from dancelab.core.models import (
    SetFunction,
    SetFunctionInput,
    SetFunctionOutput,
)
from dancelab.core.provenance import guardrail_warnings, provenance_for

MODEL_VERSION = "set_function_v0.1"
STATUS = "candidate"

ROLES = (
    SetFunction.opener,
    SetFunction.builder,
    SetFunction.bridge,
    SetFunction.peak,
    SetFunction.reset,
    SetFunction.closer,
    SetFunction.tool,
)


def _phi(inp: SetFunctionInput) -> tuple[dict[str, float], list[str]]:
    """Feature vector from implemented features. Missing → neutral + warning."""
    warnings: list[str] = []
    feats = sorted(inp.track_analysis.features, key=lambda f: f.timestamp_sec)
    rms = np.array([f.rms for f in feats if f.rms is not None])
    lfer = np.array([f.low_freq_energy_ratio for f in feats
                     if f.low_freq_energy_ratio is not None])

    if len(rms) < 10:
        warnings.append("energy profile too short — role scores are near-uniform")
        return {k: 0.5 for k in ("e_start", "e_end", "e_mean", "slope",
                                 "sustain", "dip", "bass", "windows", "short")}, warnings

    n = len(rms)
    peak_level = np.percentile(rms, 95) + 1e-9
    norm = rms / peak_level
    fifth = max(1, n // 5)
    phi = {
        "e_start": float(norm[:fifth].mean()),          # energy floor at intro
        "e_end": float(norm[-fifth:].mean()),           # energy at outro
        "e_mean": float(norm.mean()),
        "slope": float(np.clip(                          # overall build direction
            (norm[-fifth:].mean() - norm[:fifth].mean()) * 2 + 0.5, 0, 1)),
        "sustain": float((norm > 0.8).mean()),           # fraction of time near peak
        "dip": float(np.clip((norm.mean() - norm.min()) , 0, 1)),  # mid-track drop depth
        "bass": float(lfer.mean()) if len(lfer) else 0.5,
        "windows": float(np.mean([w.score for w in inp.transition_windows]))
        if inp.transition_windows else 0.5,
        "short": float(np.clip(1.0 - (feats[-1].timestamp_sec / 240.0), 0, 1)),  # <4 min → tool-ish
    }
    if not len(lfer):
        warnings.append("bass feature unavailable — neutral")
    if not inp.transition_windows:
        warnings.append("no transition windows provided — window quality neutral")
    return phi, warnings


# Hand-set heuristic priors (w_r · φ + b_r). Rows sum roughly comparable so no
# role dominates by construction. TO BE FIT against EXP011 DJ labels.
_ROLE_WEIGHTS: dict[SetFunction, dict[str, float]] = {
    SetFunction.opener: {"e_start": -0.8, "e_mean": -0.5, "slope": 0.4, "sustain": -0.4, "b": 0.9},
    SetFunction.builder: {"slope": 0.9, "e_mean": 0.2, "sustain": -0.2, "b": 0.25},
    SetFunction.bridge: {"windows": 0.7, "sustain": -0.3, "dip": 0.2, "b": 0.35},
    SetFunction.peak: {"e_mean": 0.6, "sustain": 0.7, "bass": 0.4, "b": -0.5},
    SetFunction.reset: {"dip": 0.7, "e_mean": -0.4, "slope": -0.2, "b": 0.35},
    SetFunction.closer: {"slope": -0.8, "e_end": -0.5, "b": 0.7},
    SetFunction.tool: {"short": 0.8, "windows": 0.4, "b": 0.0},
}


def role_scores(phi: dict[str, float]) -> dict[SetFunction, float]:
    """S_r = w_r · φ + b_r (pure, unit-testable)."""
    return {
        role: sum(w * phi.get(k, 0.0) for k, w in ws.items() if k != "b") + ws.get("b", 0.0)
        for role, ws in _ROLE_WEIGHTS.items()
    }


def _softmax_confidence(scores: dict[SetFunction, float]) -> float:
    vals = np.array(list(scores.values()))
    e = np.exp(vals - vals.max())
    return float(e.max() / e.sum())


def classify_set_function(inp: SetFunctionInput) -> SetFunctionOutput:
    """Main entry (ticket DoD)."""
    phi, warnings = _phi(inp)
    scores = role_scores(phi)

    # context sensitivity (C010): matching declared set_role gets a bonus
    context_fit = None
    if inp.context is not None and inp.context.set_role:
        wanted = inp.context.set_role
        for role in scores:
            if role.value == wanted:
                scores[role] += 0.2
    else:
        warnings.append("no context profile — classification is context-free (C010 caveat)")

    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    primary, top = ranked[0]
    secondary = [r for r, s in ranked[1:] if s >= 0.8 * top and s > 0]
    confidence = _softmax_confidence(scores)

    if inp.context is not None and inp.context.set_role:
        context_fit = 0.8 if primary.value == inp.context.set_role else round(
            float(np.clip(scores.get(SetFunction(inp.context.set_role), 0.0) / (top + 1e-9), 0, 1)) * 0.8, 2
        ) if inp.context.set_role in SetFunction._value2member_map_ else None

    margin = top - ranked[1][1]
    risk = float(np.clip(0.6 - margin + 0.1 * len(warnings), 0.0, 1.0))
    warnings = warnings + guardrail_warnings(
        has_context=inp.context is not None,
        conflicting=margin < 0.1,
        risk_score=risk,
    )
    reasoning = [
        f"energy: start={phi['e_start']:.2f} mean={phi['e_mean']:.2f} "
        f"end={phi['e_end']:.2f} slope={phi['slope']:.2f} sustain={phi['sustain']:.2f}",
        f"bass(LFER)={phi['bass']:.2f}, window quality={phi['windows']:.2f}",
        "top roles: " + ", ".join(f"{r.value}={s:.2f}" for r, s in ranked[:3]),
        f"decision margin {margin:.2f} (small margin → track is multi-role, C010)",
    ]

    return SetFunctionOutput(
        track_id=inp.track_analysis.track.track_id,
        primary_function=primary,
        secondary_functions=secondary,
        confidence=round(confidence, 2),
        context_fit=context_fit,
        risk_score=round(risk, 2),
        role_scores={r.value: round(s, 3) for r, s in ranked},
        reasoning=reasoning,
        warnings=warnings,
        model_version=MODEL_VERSION,
        provenance=provenance_for("set_function"),
    )
