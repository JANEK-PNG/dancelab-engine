"""Host-side waveform cache for the transition review surface.

Waveforms are visualization data, not engine decisions.  They are derived
from the source audio and stored under the host cache so the review UI can
zoom without decoding the track again or inflating ``AnalysisResult``.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re
from uuid import uuid4

import numpy as np


WAVEFORM_SCHEMA_VERSION = 1
DEFAULT_WAVEFORM_BINS = 4096


@dataclass(frozen=True)
class WaveformData:
    """Compact peak envelope plus display-only low/mid/high colour weights."""

    duration_sec: float
    sample_rate: int
    minimum: np.ndarray
    maximum: np.ndarray
    low: np.ndarray
    mid: np.ndarray
    high: np.ndarray

    @property
    def bin_count(self) -> int:
        return int(self.minimum.size)


def _source_fingerprint(path: Path) -> str:
    stat = path.stat()
    payload = f"{path.resolve()}\0{stat.st_size}\0{stat.st_mtime_ns}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def waveform_cache_path(
    source_path: str | Path,
    track_id: str,
    cache_dir: str | Path,
) -> Path:
    source = Path(source_path).expanduser()
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", track_id).strip("._") or "track"
    return Path(cache_dir).expanduser() / f"{safe_id}-{_source_fingerprint(source)}.npz"


def _band_level(power: np.ndarray, frequencies: np.ndarray, low: float, high: float) -> float:
    mask = (frequencies >= low) & (frequencies < high)
    if not np.any(mask):
        return 0.0
    return float(np.sqrt(np.mean(power[mask])))


def build_waveform_data(
    source_path: str | Path,
    *,
    target_bins: int = DEFAULT_WAVEFORM_BINS,
) -> WaveformData:
    """Decode an audio file in bounded blocks and build a detailed overview.

    ``soundfile`` streams MP3/WAV/AIFF/FLAC data, so memory stays bounded.  The
    peak envelope is truthful sample amplitude.  The three spectral values are
    relative display weights only; they are never fed into engine scoring.
    """
    try:
        import soundfile as sf
    except ImportError as exc:  # pragma: no cover - desktop audio extra owns this
        raise RuntimeError("soundfile is required for detailed waveform rendering") from exc

    source = Path(source_path).expanduser()
    if not source.exists():
        raise FileNotFoundError(source)
    target_bins = max(256, int(target_bins))

    minima: list[float] = []
    maxima: list[float] = []
    lows: list[float] = []
    mids: list[float] = []
    highs: list[float] = []

    with sf.SoundFile(source) as audio:
        sample_rate = int(audio.samplerate)
        total_frames = int(len(audio))
        duration_sec = total_frames / sample_rate if sample_rate > 0 else 0.0
        frames_per_bin = max(256, int(math.ceil(total_frames / target_bins)))

        while True:
            block = audio.read(frames_per_bin, dtype="float32", always_2d=True)
            if block.size == 0:
                break
            mono = np.asarray(block.mean(axis=1), dtype=np.float64)
            minima.append(float(mono.min(initial=0.0)))
            maxima.append(float(mono.max(initial=0.0)))

            if mono.size < 8 or not np.any(mono):
                lows.append(0.0)
                mids.append(0.0)
                highs.append(0.0)
                continue
            windowed = mono * np.hanning(mono.size)
            spectrum = np.fft.rfft(windowed)
            power = np.abs(spectrum) ** 2
            frequencies = np.fft.rfftfreq(mono.size, d=1.0 / sample_rate)
            nyquist = sample_rate / 2.0
            lows.append(_band_level(power, frequencies, 20.0, min(250.0, nyquist)))
            mids.append(_band_level(power, frequencies, 250.0, min(2500.0, nyquist)))
            highs.append(_band_level(power, frequencies, 2500.0, nyquist + 1.0))

    minimum = np.asarray(minima, dtype=np.float32)
    maximum = np.asarray(maxima, dtype=np.float32)
    if minimum.size == 0:
        minimum = np.zeros(1, dtype=np.float32)
        maximum = np.zeros(1, dtype=np.float32)
        lows = [0.0]
        mids = [0.0]
        highs = [0.0]

    absolute_peak = np.maximum(np.abs(minimum), np.abs(maximum))
    nonzero = absolute_peak[absolute_peak > 0]
    scale = float(np.percentile(nonzero, 99.5)) if nonzero.size else 1.0
    scale = max(scale, 1e-9)
    minimum = np.clip(minimum / scale, -1.0, 1.0)
    maximum = np.clip(maximum / scale, -1.0, 1.0)

    bands = np.vstack(
        [
            np.asarray(lows, dtype=np.float32),
            np.asarray(mids, dtype=np.float32),
            np.asarray(highs, dtype=np.float32),
        ]
    )
    # Per-band log compression keeps quiet hats/mids visible beside dominant
    # sub-bass without changing the truthful amplitude envelope.
    bands = np.log1p(bands)
    for index in range(bands.shape[0]):
        nonzero_band = bands[index][bands[index] > 0]
        scale = float(np.percentile(nonzero_band, 95.0)) if nonzero_band.size else 1.0
        bands[index] = np.clip(bands[index] / max(scale, 1e-12), 0.0, 1.0)
    totals = bands.sum(axis=0)
    totals[totals <= 1e-12] = 1.0
    bands = bands / totals

    return WaveformData(
        duration_sec=float(duration_sec),
        sample_rate=sample_rate,
        minimum=minimum,
        maximum=maximum,
        low=bands[0],
        mid=bands[1],
        high=bands[2],
    )


def save_waveform_data(path: str | Path, data: WaveformData) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + f".{uuid4().hex}.tmp")
    with temp.open("wb") as handle:
        np.savez_compressed(
            handle,
            schema_version=np.asarray([WAVEFORM_SCHEMA_VERSION], dtype=np.int16),
            duration_sec=np.asarray([data.duration_sec], dtype=np.float64),
            sample_rate=np.asarray([data.sample_rate], dtype=np.int32),
            minimum=data.minimum.astype(np.float32),
            maximum=data.maximum.astype(np.float32),
            low=data.low.astype(np.float32),
            mid=data.mid.astype(np.float32),
            high=data.high.astype(np.float32),
        )
    temp.replace(destination)
    return destination


def load_waveform_data(path: str | Path) -> WaveformData:
    with np.load(Path(path), allow_pickle=False) as payload:
        version = int(payload["schema_version"][0])
        if version != WAVEFORM_SCHEMA_VERSION:
            raise ValueError(f"unsupported waveform cache schema {version}")
        return WaveformData(
            duration_sec=float(payload["duration_sec"][0]),
            sample_rate=int(payload["sample_rate"][0]),
            minimum=np.asarray(payload["minimum"], dtype=np.float32),
            maximum=np.asarray(payload["maximum"], dtype=np.float32),
            low=np.asarray(payload["low"], dtype=np.float32),
            mid=np.asarray(payload["mid"], dtype=np.float32),
            high=np.asarray(payload["high"], dtype=np.float32),
        )


def load_or_build_waveform(
    source_path: str | Path,
    track_id: str,
    cache_dir: str | Path,
    *,
    target_bins: int = DEFAULT_WAVEFORM_BINS,
) -> tuple[WaveformData, Path, bool]:
    """Return ``(data, cache_path, built_now)`` for one source file."""
    path = waveform_cache_path(source_path, track_id, cache_dir)
    if path.exists():
        try:
            return load_waveform_data(path), path, False
        except (OSError, KeyError, ValueError):
            path.unlink(missing_ok=True)
    data = build_waveform_data(source_path, target_bins=target_bins)
    save_waveform_data(path, data)
    return data, path, True
