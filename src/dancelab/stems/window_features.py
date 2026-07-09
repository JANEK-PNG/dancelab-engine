"""Stem-aware feature helpers built on separated channels."""

from __future__ import annotations

import numpy as np

from dancelab.core.audio_types import AudioSignal
from dancelab.core.models import SourceStatus, StemExtractionResult, StemType, StemWindowFeature
from dancelab.features.rms import frame_signal, frame_times


def _mono(x: np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=np.float64)
    return arr.mean(axis=0) if arr.ndim > 1 else arr


def stem_energy_ratio_per_frame(
    stem: np.ndarray,
    mix: np.ndarray,
    frame_size: int,
    hop_size: int,
) -> np.ndarray:
    """Per-frame fraction of full-mix energy carried by one stem."""
    stem_arr = _mono(np.asarray(stem, dtype=np.float64))
    mix_arr = _mono(np.asarray(mix, dtype=np.float64))
    n = min(len(stem_arr), len(mix_arr))
    if n < frame_size:
        return np.zeros(0, dtype=np.float64)
    stem_frames = frame_signal(stem_arr[:n], frame_size, hop_size)
    mix_frames = frame_signal(mix_arr[:n], frame_size, hop_size)
    if stem_frames.shape[0] == 0:
        return np.zeros(0, dtype=np.float64)
    stem_energy = np.mean(stem_frames**2, axis=1)
    mix_energy = np.mean(mix_frames**2, axis=1)
    ratio = np.clip(stem_energy / np.maximum(mix_energy, 1e-9), 0.0, 1.0)
    floor = 0.05 * np.median(mix_energy)
    ratio[mix_energy < floor] = 0.0
    return ratio


def _continuity_curve(activity: np.ndarray) -> np.ndarray:
    if len(activity) == 0:
        return activity
    if len(activity) == 1:
        return np.ones(1, dtype=np.float64)
    delta = np.abs(np.gradient(activity))
    top = float(delta.max())
    if top <= 1e-9:
        return np.ones_like(activity)
    return np.clip(1.0 - delta / top, 0.0, 1.0)


def build_stem_window_features(
    *,
    track_id: str,
    mix_signal: AudioSignal,
    channels: dict[StemType, AudioSignal],
    summary: StemExtractionResult,
    frame_size: int,
    hop_size: int,
) -> list[StemWindowFeature]:
    """Aggregate stem-aware proxies into 1-second windows for downstream pilots.

    The current pipeline does not yet have transition windows at analyze-time,
    so these are 1-second candidate windows aligned with the main feature frames.
    """
    if summary.source_status != SourceStatus.source_backed:
        return []

    mix = _mono(np.asarray(mix_signal.samples, dtype=np.float64))
    out: list[StemWindowFeature] = []
    channel_lookup = {channel.stem_type: channel for channel in summary.channels}
    for stem_type, signal in channels.items():
        if stem_type not in channel_lookup or not channel_lookup[stem_type].available:
            continue
        activity = stem_energy_ratio_per_frame(signal.samples, mix, frame_size, hop_size)
        if len(activity) == 0:
            continue
        density = activity.copy()
        continuity = _continuity_curve(activity)
        times = frame_times(len(activity), hop_size, mix_signal.sample_rate, frame_size)
        buckets = times.astype(int)
        unique_secs = np.unique(buckets)
        meta = channel_lookup[stem_type]
        for sec in unique_secs:
            mask = buckets == sec
            out.append(
                StemWindowFeature(
                    track_id=track_id,
                    window_id=f"{track_id}_{stem_type.value}_{int(sec):06d}",
                    stem_type=stem_type,
                    start_sec=float(sec),
                    end_sec=float(sec + 1),
                    activity_score=round(float(activity[mask].mean()), 4),
                    density_score=round(float(density[mask].mean()), 4),
                    continuity_score=round(float(continuity[mask].mean()), 4),
                    confidence_score=round(float(meta.confidence or 0.0), 4),
                    warning_level=summary.warning_level,
                    source_status=summary.source_status,
                    validation_status=summary.validation_status,
                    cannot_claim=summary.cannot_claim,
                    provenance_pointer=summary.provenance.provenance_id,
                )
            )
    return out
