"""Data contracts for source-backed Raveform population priors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np


DURATION_BUCKETS_BEATS = (32, 64, 96, 128, 160, 192, 224, 256)


def normalize_context_label(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", "-").split())


@dataclass(frozen=True)
class TransitionObservation:
    """One qualified adjacent performed transition estimate."""

    mix_id: str
    previous_track_id: str
    next_track_id: str
    overlap_beats: float
    duration_bucket_beats: int
    tracklist_position: int = 0
    genres: tuple[str, ...] = ()
    outgoing_section: str | None = None
    incoming_section: str | None = None
    previous_match_rate: float = 0.0
    next_match_rate: float = 0.0

    @property
    def section_pair(self) -> str | None:
        if self.outgoing_section is None or self.incoming_section is None:
            return None
        return f"{self.outgoing_section}>{self.incoming_section}"


@dataclass(frozen=True)
class ConditionalDistribution:
    sample_count: int
    probabilities: tuple[float, ...]

    def as_dict(self, buckets: tuple[int, ...]) -> dict[str, object]:
        return {
            "sample_count": self.sample_count,
            "probabilities": {
                str(bucket): probability
                for bucket, probability in zip(buckets, self.probabilities, strict=True)
            },
        }


@dataclass(frozen=True)
class TransitionDurationPrior:
    """Hierarchically smoothed categorical prior over blend durations."""

    buckets_beats: tuple[int, ...]
    global_distribution: ConditionalDistribution
    genre_distributions: Mapping[str, ConditionalDistribution]
    section_pair_distributions: Mapping[str, ConditionalDistribution]
    genre_prior_strength: float
    section_prior_strength: float
    symmetric_alpha: float
    genre_context_enabled: bool = True
    section_context_enabled: bool = False
    formula_version: str = "raveform-dirichlet-duration-v1"
    calibrated_probability: bool = False

    def _genre_probabilities(self, genres: tuple[str, ...]) -> np.ndarray | None:
        labels = tuple(dict.fromkeys(normalize_context_label(value) for value in genres))
        available = [
            self.genre_distributions[label].probabilities
            for label in labels
            if label in self.genre_distributions
        ]
        if not available:
            return None
        probabilities = np.mean(np.asarray(available, dtype=np.float64), axis=0)
        return probabilities / probabilities.sum()

    def predict(
        self,
        *,
        genres: tuple[str, ...] = (),
        outgoing_section: str | None = None,
        incoming_section: str | None = None,
        mode: str = "hybrid",
    ) -> tuple[tuple[float, ...], str]:
        """Return probabilities and the context level that produced them."""

        if mode not in {"global", "genre", "section", "hybrid"}:
            raise ValueError("mode must be global, genre, section, or hybrid")
        global_probabilities = np.asarray(
            self.global_distribution.probabilities,
            dtype=np.float64,
        )
        section_key = None
        if outgoing_section and incoming_section:
            section_key = (
                f"{normalize_context_label(outgoing_section)}>"
                f"{normalize_context_label(incoming_section)}"
            )
        section_requested = mode == "section" or (
            mode == "hybrid" and self.section_context_enabled
        )
        if section_requested and section_key in self.section_pair_distributions:
            return self.section_pair_distributions[section_key].probabilities, "section_pair"
        genre_probabilities = self._genre_probabilities(genres)
        genre_requested = mode == "genre" or (
            mode == "hybrid" and self.genre_context_enabled
        )
        if genre_requested and genre_probabilities is not None:
            return tuple(float(value) for value in genre_probabilities), "genre"
        return tuple(float(value) for value in global_probabilities), "global"

    def as_dict(self) -> dict[str, object]:
        return {
            "formula_version": self.formula_version,
            "calibrated_probability": self.calibrated_probability,
            "buckets_beats": list(self.buckets_beats),
            "symmetric_alpha": self.symmetric_alpha,
            "genre_prior_strength": self.genre_prior_strength,
            "section_prior_strength": self.section_prior_strength,
            "genre_context_enabled": self.genre_context_enabled,
            "section_context_enabled": self.section_context_enabled,
            "global": self.global_distribution.as_dict(self.buckets_beats),
            "by_genre": {
                key: value.as_dict(self.buckets_beats)
                for key, value in sorted(self.genre_distributions.items())
            },
            "by_section_pair": {
                key: value.as_dict(self.buckets_beats)
                for key, value in sorted(self.section_pair_distributions.items())
            },
        }


@dataclass(frozen=True)
class MulticlassMetrics:
    count: int
    negative_log_likelihood: float
    brier_score: float
    top1_accuracy: float
    expected_calibration_error: float
    prediction_sources: tuple[tuple[str, int], ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "count": self.count,
            "negative_log_likelihood": self.negative_log_likelihood,
            "brier_score": self.brier_score,
            "top1_accuracy": self.top1_accuracy,
            "expected_calibration_error": self.expected_calibration_error,
            "prediction_sources": dict(self.prediction_sources),
        }
