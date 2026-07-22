"""Audio file loading via librosa (audioread/ffmpeg backend).

Lossless/PCM (.wav, .aiff, .flac) and lossy/container formats (.mp3, .m4a,
.mp4, .webm, .opus, .ogg) all decode through the same librosa path, so the
supported set covers the compressed formats a DJ library (or a downloaded
research corpus) actually contains, not just the original PCM shortlist.
"""

from __future__ import annotations

from pathlib import Path

from dancelab.core.audio_types import AudioSignal
from dancelab.core.config import EngineConfig
from dancelab.core.errors import IngestionError, MissingDependencyError

SUPPORTED_EXTENSIONS = {
    ".wav", ".aiff", ".aif", ".flac",  # PCM / lossless
    ".mp3", ".m4a", ".mp4", ".webm", ".opus", ".ogg",  # lossy (librosa+ffmpeg)
}


def load_audio(path: str | Path, config: EngineConfig) -> AudioSignal:
    """Load an audio file, resampled to config.audio.sample_rate.

    Requires the optional audio stack: pip install "dancelab-engine[audio]".
    """
    p = Path(path)
    if not p.exists():
        raise IngestionError(f"Audio file not found: {p}")
    if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise IngestionError(
            f"Unsupported audio format '{p.suffix}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    try:
        import librosa
    except ImportError as exc:
        raise MissingDependencyError(
            "librosa is required to load audio. Install with: pip install 'dancelab-engine[audio]'"
        ) from exc

    samples, sr = librosa.load(
        p, sr=config.audio.sample_rate, mono=config.audio.mono
    )
    return AudioSignal(samples=samples, sample_rate=int(sr), source_path=str(p))
