"""How long a blend the material at the seam can carry.

Janek's craft rule, encoded explicitly (2026-07-28): look at the waveform, not
the clock. If the outgoing material past the mix-out cue stays long and barely
changing — and the incoming material past the mix-in cue feels the same — the
seam tolerates a long transition. Dense or shifting material wants a short one.
The pair's length is governed by the weaker side.

This is DELIBERATELY a rule, not a measurement. The corpus cannot answer it
(its transition_length field is alignment-gap noise — see corpus-loses-the-seams
and the audit in core/phrasing), so the thresholds below are craft defaults,
named and tunable, never presented as measured. When the inputs needed to apply
the rule are missing, the answer is None with a reason — a caller falls back to
its default openly instead of this module inventing a number (ADR-005).

"Stable" here means the RMS envelope holds its level: no single jump beyond
JUMP_FRACTION between neighbouring frames, and no drift beyond DRIFT_FRACTION
away from the level at the cue. Both are ways of saying "the waveform looks the
same further down the page".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dancelab.core.models import AnalysisResult

# Craft thresholds — explicit and tunable, not measured constants.
JUMP_FRACTION = 0.35    # one frame-to-frame RMS step larger than this ends the runway
DRIFT_FRACTION = 0.5    # drifting this far from the cue-time level ends the runway
MAX_RUNWAY_BEATS = 256.0

# Phrase lengths the preview renderer can actually produce.
SUGGESTION_OPTIONS = (32, 64, 96, 128, 160, 192, 224, 256)


@dataclass(frozen=True)
class LengthSuggestion:
    beats: int | None
    runway_a_beats: float | None
    runway_b_beats: float | None
    reasoning: list[str] = field(default_factory=list)


def _bpm(analysis: AnalysisResult) -> float | None:
    if analysis.beatgrid and analysis.beatgrid.bpm > 0:
        return float(analysis.beatgrid.bpm)
    bpm = analysis.track.bpm_estimate
    return float(bpm) if bpm and bpm > 0 else None


def stability_runway_beats(
    analysis: AnalysisResult,
    cue_sec: float,
    *,
    max_beats: float = MAX_RUNWAY_BEATS,
) -> tuple[float | None, str]:
    """Beats past the cue for which the RMS envelope holds its level.

    Returns (runway, reason). Runway is None when the rule cannot be applied —
    no tempo, or no RMS frames past the cue — never a substituted number.
    """
    bpm = _bpm(analysis)
    if bpm is None:
        return None, "no tempo — cannot express a runway in beats"

    frames = sorted(
        (f for f in analysis.features
         if f.rms is not None and f.timestamp_sec >= cue_sec),
        key=lambda f: f.timestamp_sec,
    )
    if len(frames) < 2:
        return None, "no RMS frames past the cue — nothing to look at"

    beat_len = 60.0 / bpm
    horizon = cue_sec + max_beats * beat_len
    anchor = float(frames[0].rms)
    if anchor <= 0:
        return None, "silent at the cue — level comparisons are meaningless"

    prev = anchor
    end_sec = frames[0].timestamp_sec
    reason = f"stable to the {max_beats:.0f}-beat horizon"
    for frame in frames[1:]:
        if frame.timestamp_sec > horizon:
            break
        value = float(frame.rms)
        if abs(value - prev) / max(anchor, 1e-9) > JUMP_FRACTION:
            reason = f"level jump at {frame.timestamp_sec:.1f}s"
            break
        if abs(value - anchor) / anchor > DRIFT_FRACTION:
            reason = f"level drifted away by {frame.timestamp_sec:.1f}s"
            break
        prev = value
        end_sec = frame.timestamp_sec

    runway = min((end_sec - cue_sec) / beat_len, max_beats)
    return runway, reason


def suggest_transition_beats(
    analysis_a: AnalysisResult,
    cue_a_sec: float,
    analysis_b: AnalysisResult,
    cue_b_sec: float,
) -> LengthSuggestion:
    """Suggested blend length for this pair, from the weaker side's runway.

    beats is None when either side's runway cannot be established; the caller
    decides its own fallback and says so.
    """
    runway_a, why_a = stability_runway_beats(analysis_a, cue_a_sec)
    runway_b, why_b = stability_runway_beats(analysis_b, cue_b_sec)
    reasoning = [f"A out: {why_a}", f"B in: {why_b}"]

    if runway_a is None or runway_b is None:
        return LengthSuggestion(None, runway_a, runway_b, reasoning)

    governed = min(runway_a, runway_b)
    side = "A" if runway_a <= runway_b else "B"
    fitting = [o for o in SUGGESTION_OPTIONS if o <= governed]
    beats = max(fitting) if fitting else SUGGESTION_OPTIONS[0]
    reasoning.append(
        f"runway A {runway_a:.0f} / B {runway_b:.0f} beats — side {side} governs; "
        f"suggesting {beats}"
        + ("" if fitting else " (shortest option; runway is thinner than that)")
    )
    return LengthSuggestion(beats, runway_a, runway_b, reasoning)
