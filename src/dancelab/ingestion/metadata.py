"""Track metadata construction from an AudioSignal + optional user metadata."""

from __future__ import annotations

import hashlib
from pathlib import Path

from dancelab.core.audio_types import AudioSignal
from dancelab.core.models import Track


def make_track_id(source_path: str) -> str:
    """Deterministic track id from source path (deterministic outputs requirement)."""
    return hashlib.sha1(source_path.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def build_track(
    signal: AudioSignal,
    title: str | None = None,
    artist: str | None = None,
    style_label: str | None = None,
    bpm_estimate: float | None = None,
    key_estimate: str | None = None,
) -> Track:
    source = signal.source_path or "unknown"
    return Track(
        track_id=make_track_id(source),
        title=title or (Path(source).stem if signal.source_path else None),
        artist=artist,
        duration_sec=round(signal.duration_sec, 3),
        sample_rate=signal.sample_rate,
        channels=1 if signal.samples.ndim == 1 else int(signal.samples.shape[0]),
        source_path=signal.source_path,
        style_label=style_label,
        bpm_estimate=bpm_estimate,
        key_estimate=key_estimate,
    )
