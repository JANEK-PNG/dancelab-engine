"""In-memory audio representation passed between pipeline stages.

Kept as a plain dataclass (not Pydantic) — raw sample arrays are not part of
any JSON contract; only derived features/descriptors are serialized (ADR-004).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AudioSignal:
    samples: Any  # numpy.ndarray, shape (n,) mono or (2, n) stereo
    sample_rate: int
    source_path: str | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def duration_sec(self) -> float:
        n = self.samples.shape[-1]
        return float(n) / float(self.sample_rate)
