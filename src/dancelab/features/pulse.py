"""Pulse clarity proxy (spec §2.2). STATUS: candidate baseline.

C_pulse(t) = A_beat(t) / (sum_i A_i(t) + ε)

v0 proxy:
- novelty curve = non-negative spectral flux
- A_beat = positive autocorrelation at the local beat lag
- denominator = sum of positive autocorrelation magnitudes in a local lag band

This is a beat-aligned periodicity ratio, not a validated perceptual pulse
model yet, so the feature stays explicitly candidate / to-validate.
"""

from __future__ import annotations

import numpy as np

EPS = 1e-12


def _positive_autocorrelation(segment: np.ndarray, lags: np.ndarray) -> np.ndarray:
    values = np.zeros(len(lags), dtype=np.float64)
    for i, lag in enumerate(lags):
        if lag <= 0 or lag >= len(segment):
            continue
        values[i] = max(0.0, float(np.dot(segment[:-lag], segment[lag:])))
    return values


def pulse_clarity(
    novelty: np.ndarray,
    beat_times_sec: np.ndarray,
    sample_rate: float,
    query_times_sec: np.ndarray | None = None,
    window_beats: int = 8,
) -> np.ndarray:
    """Beat-aligned periodicity ratio on a novelty curve.

    `sample_rate` is the sampling rate of the novelty curve itself (for example
    STFT frames per second), not the raw audio sample rate.
    """
    novelty_arr = np.clip(np.nan_to_num(np.asarray(novelty, dtype=np.float64)), 0.0, None)
    beats = np.sort(np.asarray(beat_times_sec, dtype=np.float64))

    if query_times_sec is None:
        queries = np.arange(len(novelty_arr), dtype=np.float64) / float(sample_rate)
    else:
        queries = np.asarray(query_times_sec, dtype=np.float64)

    if (
        len(novelty_arr) == 0
        or len(queries) == 0
        or sample_rate <= 0
        or len(beats) < 2
        or np.allclose(novelty_arr, 0.0)
    ):
        return np.zeros(len(queries), dtype=np.float64)

    intervals = np.diff(beats)
    out = np.zeros(len(queries), dtype=np.float64)
    half_beats = max(window_beats // 2, 2)

    for i, q in enumerate(queries):
        beat_ix = int(np.searchsorted(beats, q, side="left"))
        lo_ix = max(0, beat_ix - 2)
        hi_ix = min(len(intervals), beat_ix + 2)
        local_intervals = intervals[lo_ix:hi_ix]
        if len(local_intervals) == 0:
            local_intervals = intervals

        beat_period_sec = float(np.median(local_intervals))
        if not np.isfinite(beat_period_sec) or beat_period_sec <= 0:
            continue

        beat_lag = int(round(beat_period_sec * sample_rate))
        if beat_lag < 1:
            continue

        center = int(round(q * sample_rate))
        half_window = beat_lag * half_beats
        lo = max(0, center - half_window)
        hi = min(len(novelty_arr), center + half_window + 1)
        segment = novelty_arr[lo:hi]
        if len(segment) <= beat_lag * 2:
            continue

        segment = segment - float(segment.mean())
        if np.allclose(segment, 0.0):
            continue

        min_lag = max(1, beat_lag // 2)
        max_lag = min(len(segment) - 2, beat_lag * 2)
        if max_lag < min_lag:
            continue

        lags = np.arange(min_lag, max_lag + 1, dtype=int)
        autocorr = _positive_autocorrelation(segment, lags)
        denom = float(autocorr.sum()) + EPS
        beat_pos = int(np.argmin(np.abs(lags - beat_lag)))
        out[i] = autocorr[beat_pos] / denom

    return np.clip(out, 0.0, 1.0)
