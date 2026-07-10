from __future__ import annotations

from pathlib import Path

from dancelab.ingestion.preflight import (
    find_suspicious_audio_files,
    format_duration,
    suspicious_duration_reason,
)


def test_suspicious_duration_reason_flags_samples_and_long_sets():
    assert suspicious_duration_reason(119.9) == "shorter than 2 minutes"
    assert suspicious_duration_reason(120.0) is None
    assert suspicious_duration_reason(600.0) is None
    assert suspicious_duration_reason(600.1) == "longer than 10 minutes"
    assert suspicious_duration_reason(None) is None


def test_find_suspicious_audio_files_uses_duration_probe(tmp_path):
    short = tmp_path / "loop.wav"
    normal = tmp_path / "track.wav"
    long = tmp_path / "recorded_set.wav"
    for path in (short, normal, long):
        path.write_bytes(b"stub")

    durations = {
        short: 42.0,
        normal: 300.0,
        long: 3600.0,
    }

    suspicious = find_suspicious_audio_files(
        [short, normal, long],
        duration_probe=lambda path: durations[Path(path)],
    )

    assert [(item.path.name, item.reason) for item in suspicious] == [
        ("loop.wav", "shorter than 2 minutes"),
        ("recorded_set.wav", "longer than 10 minutes"),
    ]


def test_format_duration():
    assert format_duration(42.2) == "0:42"
    assert format_duration(305.0) == "5:05"
