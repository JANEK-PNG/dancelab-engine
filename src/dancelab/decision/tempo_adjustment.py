"""Preview-only tempo adjustment mathematics from DLASOT-12.

M8-M10 are deliberately isolated from engine scoring and export.  They model
audition playback rates after reliable BPM/beatgrid analysis; they never infer
or overwrite a track's native tempo.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite, sqrt
from typing import Iterable


M8_SPEED_UP_WEIGHT = 0.765
M8_SLOW_DOWN_WEIGHT = 1.0
M9_OCTAVE_EXPONENTS: tuple[int, ...] = (-2, -1, 0, 1, 2)
M9_PREVIEW_EXPONENTS: tuple[int, ...] = (-1, 0, 1)
TEMPO_FORMULA_VERSION = "dlasot12_preview_v1"
TEMPO_SOURCE_IDS: tuple[str, ...] = ("DLASOT-12",)


def _positive_finite(value: float, name: str) -> float:
    number = float(value)
    if not isfinite(number) or number <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return number


def _quality(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return number


@dataclass(frozen=True)
class TempoCandidate:
    """One M9 metrical representation, not a claim about tempo ground truth."""

    native_bpm: float
    bpm: float
    octave_exponent: int

    @property
    def factor(self) -> float:
        return 2.0**self.octave_exponent


@dataclass(frozen=True)
class TempoPlan:
    """Audition-only balanced tempo plan with formula and input provenance."""

    native_a_bpm: float
    native_b_bpm: float
    selected_a_bpm: float
    selected_b_bpm: float
    target_bpm: float
    rate_a: float
    rate_b: float
    discomfort_a: float
    discomfort_b: float
    octave_a: int
    octave_b: int
    beatgrid_quality_a: float | None
    beatgrid_quality_b: float | None
    confidence: float
    within_review_band: bool
    max_rate_delta: float
    warnings: tuple[str, ...]
    strategy_id: str = "balanced_m10"
    formula_ids: tuple[str, ...] = ("M8", "M9", "M10")
    formula_version: str = TEMPO_FORMULA_VERSION
    source_ids: tuple[str, ...] = TEMPO_SOURCE_IDS


def tempo_discomfort(
    factor: float,
    *,
    speed_up: float = M8_SPEED_UP_WEIGHT,
    slow_down: float = M8_SLOW_DOWN_WEIGHT,
) -> float:
    """Return the M8 asymmetric playback-rate discomfort for ``factor``."""

    rate = _positive_finite(factor, "factor")
    a = _positive_finite(speed_up, "speed_up")
    b = _positive_finite(slow_down, "slow_down")
    if rate > 1.0:
        return a * (rate - 1.0)
    if rate < 1.0:
        return b * ((1.0 / rate) - 1.0)
    return 0.0


def octave_tempo_candidates(
    bpm: float,
    *,
    exponents: Iterable[int] = M9_OCTAVE_EXPONENTS,
) -> tuple[TempoCandidate, ...]:
    """Enumerate M9 octave-related tempi without selecting tempo truth."""

    native = _positive_finite(bpm, "bpm")
    normalized = tuple(dict.fromkeys(int(exponent) for exponent in exponents))
    if not normalized:
        raise ValueError("exponents must contain at least one octave exponent")
    return tuple(
        TempoCandidate(
            native_bpm=native,
            bpm=native * (2.0**exponent),
            octave_exponent=exponent,
        )
        for exponent in normalized
    )


def nearest_octave_candidate(
    reference_bpm: float,
    candidate_bpm: float,
    *,
    exponents: Iterable[int] = M9_PREVIEW_EXPONENTS,
    minimum_bpm: float | None = None,
    maximum_bpm: float | None = None,
) -> TempoCandidate:
    """Choose the nearest allowed M9 representation for pair preview.

    The default intentionally preserves DanceLab's current direct/half/double
    comparison.  Full M9 enumeration remains available for diagnostics, but a
    wide 0.25x or 4x candidate is never introduced into playback silently.
    """

    reference = _positive_finite(reference_bpm, "reference_bpm")
    candidates = list(octave_tempo_candidates(candidate_bpm, exponents=exponents))
    if minimum_bpm is not None:
        minimum = _positive_finite(minimum_bpm, "minimum_bpm")
        candidates = [candidate for candidate in candidates if candidate.bpm >= minimum]
    if maximum_bpm is not None:
        maximum = _positive_finite(maximum_bpm, "maximum_bpm")
        candidates = [candidate for candidate in candidates if candidate.bpm <= maximum]
    if not candidates:
        raise ValueError("no octave tempo candidate remains inside the requested bounds")
    return min(
        candidates,
        key=lambda candidate: (
            abs(reference - candidate.bpm),
            abs(candidate.octave_exponent),
            candidate.octave_exponent,
        ),
    )


def shared_target_tempo(
    tempo_a_bpm: float,
    tempo_b_bpm: float,
    *,
    speed_up: float = M8_SPEED_UP_WEIGHT,
    slow_down: float = M8_SLOW_DOWN_WEIGHT,
) -> float:
    """Return the M10 target that balances M8 discomfort for two tempi."""

    tempo_a = _positive_finite(tempo_a_bpm, "tempo_a_bpm")
    tempo_b = _positive_finite(tempo_b_bpm, "tempo_b_bpm")
    a = _positive_finite(speed_up, "speed_up")
    b = _positive_finite(slow_down, "slow_down")
    low, high = sorted((tempo_a, tempo_b))
    if isclose(low, high, rel_tol=0.0, abs_tol=1e-12):
        return low
    discriminant = ((a - b) ** 2) * (low**2) + 4.0 * a * b * high * low
    target = (((a - b) * low) + sqrt(discriminant)) / (2.0 * a)
    if not isfinite(target) or target < low - 1e-9 or target > high + 1e-9:
        raise ArithmeticError("M10 produced a target outside the selected tempo interval")
    return min(high, max(low, target))


def build_balanced_tempo_plan(
    native_a_bpm: float,
    native_b_bpm: float,
    *,
    selected_a_bpm: float | None = None,
    selected_b_bpm: float | None = None,
    octave_a: int = 0,
    octave_b: int = 0,
    beatgrid_reliable_a: bool,
    beatgrid_reliable_b: bool,
    beatgrid_quality_a: float | None = None,
    beatgrid_quality_b: float | None = None,
    max_rate_delta: float = 0.10,
    speed_up: float = M8_SPEED_UP_WEIGHT,
    slow_down: float = M8_SLOW_DOWN_WEIGHT,
) -> TempoPlan | None:
    """Build a provenance-rich M8-M10 plan, or ``None`` if grids are unsafe."""

    if not beatgrid_reliable_a or not beatgrid_reliable_b:
        return None
    native_a = _positive_finite(native_a_bpm, "native_a_bpm")
    native_b = _positive_finite(native_b_bpm, "native_b_bpm")
    selected_a = _positive_finite(
        selected_a_bpm if selected_a_bpm is not None else native_a,
        "selected_a_bpm",
    )
    selected_b = _positive_finite(
        selected_b_bpm if selected_b_bpm is not None else native_b,
        "selected_b_bpm",
    )
    expected_a = native_a * (2.0**int(octave_a))
    expected_b = native_b * (2.0**int(octave_b))
    if not isclose(selected_a, expected_a, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("selected_a_bpm does not match native_a_bpm and octave_a")
    if not isclose(selected_b, expected_b, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("selected_b_bpm does not match native_b_bpm and octave_b")

    quality_a = _quality(beatgrid_quality_a, "beatgrid_quality_a")
    quality_b = _quality(beatgrid_quality_b, "beatgrid_quality_b")
    review_band = float(max_rate_delta)
    if not isfinite(review_band) or review_band < 0.0:
        raise ValueError("max_rate_delta must be finite and non-negative")

    target = shared_target_tempo(
        selected_a,
        selected_b,
        speed_up=speed_up,
        slow_down=slow_down,
    )
    rate_a = target / selected_a
    rate_b = target / selected_b
    discomfort_a = tempo_discomfort(rate_a, speed_up=speed_up, slow_down=slow_down)
    discomfort_b = tempo_discomfort(rate_b, speed_up=speed_up, slow_down=slow_down)
    warnings: list[str] = []
    if quality_a is None or quality_b is None:
        warnings.append("beatgrid quality score unavailable; confidence capped at 0.50")
    confidence = min(
        quality_a if quality_a is not None else 0.5,
        quality_b if quality_b is not None else 0.5,
    )
    within_review_band = max(abs(rate_a - 1.0), abs(rate_b - 1.0)) <= review_band + 1e-12
    if not within_review_band:
        warnings.append(
            f"balanced rates exceed the visible ±{review_band * 100.0:.1f}% preview band"
        )

    return TempoPlan(
        native_a_bpm=native_a,
        native_b_bpm=native_b,
        selected_a_bpm=selected_a,
        selected_b_bpm=selected_b,
        target_bpm=target,
        rate_a=rate_a,
        rate_b=rate_b,
        discomfort_a=discomfort_a,
        discomfort_b=discomfort_b,
        octave_a=int(octave_a),
        octave_b=int(octave_b),
        beatgrid_quality_a=quality_a,
        beatgrid_quality_b=quality_b,
        confidence=confidence,
        within_review_band=within_review_band,
        max_rate_delta=review_band,
        warnings=tuple(warnings),
    )
