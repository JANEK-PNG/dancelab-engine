"""Audio preprocessing: normalization, framing (System Architecture §2).

Status: stub — Sprint 1.
"""

from __future__ import annotations

from dancelab.core.audio_types import AudioSignal
from dancelab.core.config import EngineConfig
from dancelab.core.errors import NotImplementedFeature


def preprocess(signal: AudioSignal, config: EngineConfig) -> AudioSignal:
    """Normalize level, enforce standard sample rate, prepare frames/windows."""
    raise NotImplementedFeature("audio preprocessing", status="planned")
