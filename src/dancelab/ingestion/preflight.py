"""Fast import preflight checks before full audio analysis."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

MIN_TRACK_DURATION_SEC = 2 * 60.0
MAX_TRACK_DURATION_SEC = 10 * 60.0


@dataclass(frozen=True)
class SuspiciousAudioFile:
    path: Path
    duration_sec: float
    reason: str


def probe_audio_duration_sec(path: str | Path) -> float | None:
    """Read duration from file metadata without running the full analysis pipeline."""
    audio_path = Path(path).expanduser()
    try:
        import soundfile as sf

        info = sf.info(str(audio_path))
        if info.samplerate and info.frames:
            return float(info.frames) / float(info.samplerate)
    except Exception:
        pass

    try:
        import librosa

        return float(librosa.get_duration(path=str(audio_path)))
    except Exception:
        return None


def suspicious_duration_reason(
    duration_sec: float | None,
    *,
    min_sec: float = MIN_TRACK_DURATION_SEC,
    max_sec: float = MAX_TRACK_DURATION_SEC,
) -> str | None:
    if duration_sec is None:
        return None
    if duration_sec < min_sec:
        return "shorter than 2 minutes"
    if duration_sec > max_sec:
        return "longer than 10 minutes"
    return None


def find_suspicious_audio_files(
    files: Sequence[str | Path],
    *,
    duration_probe: Callable[[str | Path], float | None] = probe_audio_duration_sec,
    min_sec: float = MIN_TRACK_DURATION_SEC,
    max_sec: float = MAX_TRACK_DURATION_SEC,
) -> list[SuspiciousAudioFile]:
    suspicious: list[SuspiciousAudioFile] = []
    for source in files:
        path = Path(source).expanduser()
        duration = duration_probe(path)
        reason = suspicious_duration_reason(duration, min_sec=min_sec, max_sec=max_sec)
        if duration is not None and reason is not None:
            suspicious.append(
                SuspiciousAudioFile(
                    path=path,
                    duration_sec=float(duration),
                    reason=reason,
                )
            )
    return suspicious


def format_duration(duration_sec: float) -> str:
    seconds = max(int(round(duration_sec)), 0)
    minutes, sec = divmod(seconds, 60)
    return f"{minutes}:{sec:02d}"
