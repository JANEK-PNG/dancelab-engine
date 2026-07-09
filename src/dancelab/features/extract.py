"""Feature extraction stage: runs all IMPLEMENTED features over a signal.

Currently: RMS, spectral flux, low-frequency energy ratio, bass energy,
onset density, vocal density proxy, and pulse clarity proxy. Planned features
join here as they land - never before (ADR-005).

Frames are computed block-wise to bound memory (a 7-minute track at
hop=512 is ~36k frames; a full float64 spectrogram would be ~0.5 GB).
Per-frame values are aggregated to 1-second FeatureFrames for JSON output.
"""

from __future__ import annotations

import numpy as np

from dancelab.core.audio_types import AudioSignal
from dancelab.core.config import EngineConfig
from dancelab.core.models import FeatureFrame
from dancelab.features.bass import bass_energy
from dancelab.features.onset_density import onset_density_at
from dancelab.features.pulse import pulse_clarity
from dancelab.features.rms import frame_signal, frame_times
from dancelab.features.spectral_flux import (
    low_freq_energy_ratio,
    magnitude_spectrogram,
    spectral_flux,
)

BLOCK_FRAMES = 4096  # ~48 s of frames at hop 512 / 44.1 kHz per block


def extract_features(
    signal: AudioSignal,
    config: EngineConfig,
    track_id: str,
    onset_times_sec: np.ndarray | None = None,
    beat_times_sec: np.ndarray | list[float] | None = None,
    vocal_proxy: np.ndarray | None = None,
) -> list[FeatureFrame]:
    """Per-second FeatureFrames with all implemented features filled in.

    onset_times_sec -> fills onset_density; beat_times_sec + spectral flux ->
    pulse_clarity_proxy; vocal_proxy (per STFT frame) -> aggregated to per-second
    vocal_density_proxy. Optional inputs are left None when absent.
    Deterministic: pure numpy, fixed framing from config.
    """
    x = np.asarray(signal.samples, dtype=np.float64)
    if x.ndim > 1:  # defensive: loader delivers mono when config.audio.mono
        x = x.mean(axis=0)

    frame = config.audio.frame_size
    hop = config.audio.hop_size
    sr = signal.sample_rate
    band = tuple(config.bands.get("bass", [20.0, 150.0]))

    if len(x) < frame:
        return []

    n_frames = 1 + (len(x) - frame) // hop

    rms_all: list[np.ndarray] = []
    flux_all: list[np.ndarray] = []
    lfer_all: list[np.ndarray] = []
    bass_all: list[np.ndarray] = []

    prev_last_mag: np.ndarray | None = None
    for i0 in range(0, n_frames, BLOCK_FRAMES):
        i1 = min(i0 + BLOCK_FRAMES, n_frames)
        chunk = x[i0 * hop : (i1 - 1) * hop + frame]
        mag = magnitude_spectrogram(chunk, frame, hop)

        frames = frame_signal(chunk, frame, hop)
        rms_all.append(np.sqrt(np.mean(frames**2, axis=1)))
        lfer_all.append(low_freq_energy_ratio(mag, sr, frame, band))
        bass_all.append(bass_energy(mag, sr, frame, band))

        # flux needs the previous frame's spectrum across the block boundary
        if prev_last_mag is None:
            flux_all.append(spectral_flux(mag))
        else:
            flux_all.append(spectral_flux(np.vstack([prev_last_mag, mag]))[1:])
        prev_last_mag = mag[-1:]

    rms = np.concatenate(rms_all)
    flux = np.concatenate(flux_all)
    lfer = np.concatenate(lfer_all)
    bass = np.concatenate(bass_all)
    times = frame_times(n_frames, hop, sr, frame)

    # aggregate frame-level -> 1-second buckets (mean), keyed by bucket start
    buckets = times.astype(int)
    unique_secs = np.unique(buckets)
    onset_density = None
    if onset_times_sec is not None:
        onset_density = onset_density_at(
            np.asarray(onset_times_sec, dtype=np.float64),
            unique_secs.astype(np.float64),
            config.analysis.onset_window_sec,
        )

    pulse = None
    if beat_times_sec is not None:
        pulse = pulse_clarity(
            flux,
            np.asarray(beat_times_sec, dtype=np.float64),
            sample_rate=sr / hop,
            query_times_sec=unique_secs.astype(np.float64),
        )

    # vocal_proxy is per STFT frame (same framing as rms) -> average per 1-s bucket
    vocal = None
    if vocal_proxy is not None:
        vp = np.asarray(vocal_proxy, dtype=np.float64)
        vp = vp[:n_frames] if len(vp) >= n_frames else np.pad(vp, (0, n_frames - len(vp)))

    result: list[FeatureFrame] = []
    for i, sec in enumerate(unique_secs):
        m = buckets == sec
        if vocal_proxy is not None:
            vocal = round(float(vp[m].mean()), 4)
        result.append(
            FeatureFrame(
                track_id=track_id,
                timestamp_sec=float(sec),
                rms=round(float(rms[m].mean()), 6),
                spectral_flux=round(float(flux[m].mean()), 6),
                low_freq_energy_ratio=round(float(lfer[m].mean()), 6),
                bass_energy=round(float(bass[m].mean()), 6),
                onset_density=round(float(onset_density[i]), 4)
                if onset_density is not None else None,
                pulse_clarity_proxy=round(float(pulse[i]), 4) if pulse is not None else None,
                vocal_density_proxy=vocal,
            )
        )
    return result
