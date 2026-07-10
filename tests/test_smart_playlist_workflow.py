from __future__ import annotations

from pathlib import Path

from dancelab.core.config import EngineConfig
from dancelab.core.models import AnalysisResult, BeatGrid, FeatureFrame, Track
from dancelab.workflows.smart_playlist import build_smart_playlist_from_folder


def _analysis_from_path(path: str | Path, _config: EngineConfig) -> AnalysisResult:
    stem = Path(path).stem
    index = int(stem.split("_")[-1])
    track_id = stem.lower()
    bpm = 124.0 + index
    return AnalysisResult(
        engine_version="test-smart-playlist",
        track=Track(
            track_id=track_id,
            title=stem,
            artist="DanceLab Test",
            bpm_estimate=bpm,
            key_estimate=f"{(index % 12) + 1}A",
            key_confidence=0.8,
            source_path=str(path),
            duration_sec=300.0,
            sample_rate=44100,
        ),
        beatgrid=BeatGrid(
            bpm=bpm,
            beat_times_sec=[float(t) for t in range(0, 300, 2)],
            downbeats_sec=[float(t) for t in range(0, 300, 8)],
        ),
        features=[
            FeatureFrame(
                track_id=track_id,
                timestamp_sec=float(t),
                rms=0.2 + 0.01 * index,
                spectral_flux=0.3,
                bass_energy=0.4 + 0.01 * (t % 5),
                vocal_density_proxy=0.05,
                tension_proxy=0.2,
            )
            for t in range(0, 300, 4)
        ],
    )


def test_build_smart_playlist_from_folder_writes_rekordbox_xml(tmp_path):
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    for index in range(1, 7):
        (music_dir / f"Track_{index}.wav").write_bytes(b"fake wav")

    output_path = tmp_path / "exports" / "tomorrow.xml"
    result = build_smart_playlist_from_folder(
        music_dir,
        EngineConfig(),
        target_track_count=5,
        playlist_name="Tomorrow Set",
        output_path=output_path,
        processed_dir=tmp_path / "processed",
        analyze_fn=_analysis_from_path,
    )

    assert result.source_track_count == 6
    assert result.analyzed_track_count == 6
    assert len(result.set_plan.track_order) == 5
    assert result.output_path == str(output_path)
    assert output_path.exists()
    xml = output_path.read_text(encoding="utf-8")
    assert "Tomorrow Set" in xml
    assert "POSITION_MARK" in xml
    assert xml.count("TrackID=") == 5


def test_build_smart_playlist_rejects_too_small_count(tmp_path):
    # Any count >= 2 is valid (no fixed 5/10/15/20 presets); below that a set
    # has no transitions to plan.
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    (music_dir / "Track_1.wav").write_bytes(b"fake wav")

    try:
        build_smart_playlist_from_folder(
            music_dir,
            EngineConfig(),
            target_track_count=1,
            analyze_fn=_analysis_from_path,
        )
    except ValueError as exc:
        assert "at least 2" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("too-small target_track_count should fail")


def test_estimate_track_count_for_duration():
    from dancelab.workflows.smart_playlist import estimate_track_count_for_duration

    analyses = [_analysis_from_path(f"/tmp/Track_{i}.wav", None) for i in range(20)]
    for analysis in analyses:
        analysis.track.duration_sec = 300.0  # 5-minute tracks

    assert estimate_track_count_for_duration(analyses, 60.0) == 12   # 1 h
    assert estimate_track_count_for_duration(analyses, 180.0) == 20  # 3 h clamps to library
    assert estimate_track_count_for_duration(analyses, 1.0) == 2     # floor at 2

    import pytest

    for analysis in analyses:
        analysis.track.duration_sec = None
    with pytest.raises(ValueError, match="known duration"):
        estimate_track_count_for_duration(analyses, 60.0)
