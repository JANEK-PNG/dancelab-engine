from __future__ import annotations

from pathlib import Path

from dancelab.core.config import EngineConfig
from dancelab.core.models import AnalysisResult, BeatGrid, FeatureFrame, Track
from dancelab.workflows.smart_playlist import (
    build_smart_playlist_from_folder,
    config_for_analysis_depth,
)


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
        (music_dir / f"Track_{index}.wav").write_bytes(f"fake wav {index}".encode())

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


def test_analysis_repository_ignores_incremental_library_manifest(tmp_path):
    from dancelab.storage.repositories import FileAnalysisRepository

    repo = FileAnalysisRepository(tmp_path)
    analysis = _analysis_from_path(tmp_path / "Track_1.wav", EngineConfig())
    repo.save(analysis)
    (tmp_path / "library_manifest.json").write_text('{"tracks": {}}', encoding="utf-8")

    assert repo.list_track_ids() == [analysis.track.track_id]
    assert repo.get(repo.list_track_ids()[0]).track.track_id == analysis.track.track_id


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


def test_analyze_files_relays_real_pipeline_stages(tmp_path):
    # stage_progress relays the engine's on_stage hook — no simulated stages
    from dancelab.workflows.smart_playlist import analyze_files

    music_dir = tmp_path / "music"
    music_dir.mkdir()
    (music_dir / "Track_1.wav").write_bytes(b"fake wav")

    def analyze_with_stages(path, config, on_stage=None):
        if on_stage is not None:
            on_stage("Key detection")
            on_stage("Beat tracking (BPM)")
        return _analysis_from_path(path, config)

    stages: list[tuple[str, str]] = []
    analyses, failures = analyze_files(
        [music_dir / "Track_1.wav"],
        EngineConfig(),
        processed_dir=tmp_path / "processed",
        analyze_fn=analyze_with_stages,
        stage_progress=lambda path, stage: stages.append((path, stage)),
    )
    assert len(analyses) == 1 and not failures
    stage_names = [stage for _, stage in stages]
    # §7 prepends the honest re-analysis reason; engine stages follow in order
    assert stage_names[0].startswith("Re-analysis:")
    assert stage_names[1:] == ["Key detection", "Beat tracking (BPM)"]
    assert all(path.endswith("Track_1.wav") for path, _ in stages)


def test_deep_analysis_depth_enables_demucs_stem_layer():
    cfg = config_for_analysis_depth(EngineConfig(), "deep")

    assert cfg.stems.enabled is True
    assert cfg.stems.method == "demucs"
    assert cfg.stems.export_stems is True
    assert cfg.analysis.vocal_method == "demucs"
    assert cfg.analysis.transition_top_n >= 8
    # M4-benchmarked fast separation profile (x1.25, cosine 0.99994 vs 0.25)
    assert cfg.stems.overlap == 0.10
    assert EngineConfig().stems.overlap == 0.25  # normal tier untouched


def test_analyze_files_cooperative_stop(tmp_path):
    # §9: should_stop checked between tracks; completed tracks already saved
    from dancelab.workflows.smart_playlist import analyze_files

    music_dir = tmp_path / "music"
    music_dir.mkdir()
    files = []
    for i in range(1, 6):
        p = music_dir / f"Track_{i}.wav"
        p.write_bytes(f"fake {i}".encode())
        files.append(p)

    from dancelab.ingestion.metadata import make_track_id

    calls = {"n": 0}

    def analyze_counting(path, config):
        calls["n"] += 1
        result = _analysis_from_path(path, config)
        # cache key is make_track_id(path) — align so the re-run hits cache
        result.track.track_id = make_track_id(str(path))
        return result

    analyses, failures = analyze_files(
        files,
        EngineConfig(),
        processed_dir=tmp_path / "processed",
        analyze_fn=analyze_counting,
        should_stop=lambda: calls["n"] >= 2,  # stop after two tracks complete
    )
    assert len(analyses) == 2 and not failures
    assert calls["n"] == 2

    # re-run without stop: continues from cache, analyzes only the remaining 3
    analyses2, _ = analyze_files(
        files,
        EngineConfig(),
        processed_dir=tmp_path / "processed",
        analyze_fn=analyze_counting,
    )
    assert len(analyses2) == 5
    assert calls["n"] == 5  # 2 cached + 3 new — nothing processed twice


def test_incremental_manifest_reuse_and_invalidation(tmp_path):
    # §7 hard rule: valid stored analysis → zero compute. Each trigger re-runs.
    from dancelab.ingestion.metadata import make_track_id
    from dancelab.storage.library_manifest import LibraryManifest, file_checksum
    from dancelab.workflows.smart_playlist import analyze_files

    music_dir = tmp_path / "music"
    music_dir.mkdir()
    track = music_dir / "Track_1.wav"
    track.write_bytes(b"original-content")
    processed = tmp_path / "processed"
    calls = {"n": 0}

    def analyze_counting(path, config):
        calls["n"] += 1
        result = _analysis_from_path(path, config)
        result.track.track_id = make_track_id(str(path))
        return result

    def run(tier="quick"):
        return analyze_files(
            [track], EngineConfig(), processed_dir=processed,
            analyze_fn=analyze_counting, tier=tier,
        )

    run()
    assert calls["n"] == 1
    run()
    assert calls["n"] == 1          # unchanged → zero compute
    run(tier="quick")
    assert calls["n"] == 1

    run(tier="deep")
    assert calls["n"] == 2   # tier upgrade recomputes
    run(tier="quick")
    assert calls["n"] == 2  # deep satisfies quick — reuse

    track.write_bytes(b"CHANGED-content")       # checksum change
    run(tier="deep")
    assert calls["n"] == 3

    # engine-version change invalidates
    manifest = LibraryManifest(processed)
    record = manifest.record(make_track_id(str(track)))
    record.engine_version = "0.0.1-old"
    manifest._save()
    run(tier="deep")
    assert calls["n"] == 4

    # reuse reason API is explicit about why
    manifest = LibraryManifest(processed)
    assert manifest.reuse_reason_or_none(
        "unknown-track", source_checksum="x", requested_tier="quick",
        formula_version="f", analysis_file_exists=False,
    ) == "not analyzed yet"
    checksum = file_checksum(track)
    assert manifest.reuse_reason_or_none(
        make_track_id(str(track)), source_checksum=checksum,
        requested_tier="quick",
        formula_version=manifest.record(make_track_id(str(track))).formula_version,
        analysis_file_exists=True,
    ) is None


def test_parallel_analysis_matches_sequential(tmp_path):
    # §18: process-pool fan-out uses the REAL pipeline and must produce the
    # same library as sequential — order preserved, manifest reuse intact.
    import numpy as np
    import pytest

    sf = pytest.importorskip("soundfile")
    pytest.importorskip("librosa")
    from dancelab.workflows.smart_playlist import analyze_files

    music_dir = tmp_path / "music"
    music_dir.mkdir()
    sr = 22050
    files = []
    for i in range(4):
        t = np.arange(sr) / sr
        tone = (0.4 * np.sin(2 * np.pi * (220 + 40 * i) * t)).astype("float32")
        p = music_dir / f"tone_{i}.wav"
        sf.write(p, tone, sr)
        files.append(p)

    par_dir = tmp_path / "par"
    analyses_par, failures_par = analyze_files(
        files, EngineConfig(), processed_dir=par_dir, workers=3,
    )
    assert not failures_par
    assert [a.track.source_path for a in analyses_par] == [str(f) for f in files]

    seq_dir = tmp_path / "seq"
    analyses_seq, _ = analyze_files(files, EngineConfig(), processed_dir=seq_dir)
    assert [a.track.track_id for a in analyses_par] == [
        a.track.track_id for a in analyses_seq
    ]
    assert [a.beatgrid.bpm for a in analyses_par] == [
        a.beatgrid.bpm for a in analyses_seq
    ]

    # second parallel run: manifest reuse → all four from cache, zero compute
    progress_events = []
    analyses_again, _ = analyze_files(
        files, EngineConfig(), processed_dir=par_dir, workers=3,
        progress=lambda done, total, path: progress_events.append(done),
    )
    assert len(analyses_again) == 4
    assert progress_events == [1, 2, 3, 4]  # instant cache hits, in order
