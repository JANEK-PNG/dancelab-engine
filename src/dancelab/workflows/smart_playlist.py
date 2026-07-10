"""One-shot folder analysis -> set plan -> Rekordbox playlist workflow."""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from dancelab.core.config import EngineConfig, load_weights
from dancelab.core.models import AnalysisResult, SetPlan, TransitionWindowInput
from dancelab.core.pipeline import analyze_track, analyze_track_with_stems
from dancelab.decision.set_builder import build_set
from dancelab.decision.transition_windows import detect_transition_windows
from dancelab.export.rekordbox import build_rekordbox_xml, write_rekordbox_xml
from dancelab.ingestion.loader import SUPPORTED_EXTENSIONS
from dancelab.ingestion.metadata import make_track_id
from dancelab.stems.workflow import stem_enabled_config
from dancelab.storage.repositories import FileAnalysisRepository

# Suggested preset lengths for UIs — NOT a validation gate. Any count >= 2 is
# valid; users can also target a set duration via
# estimate_track_count_for_duration().
SUGGESTED_PLAYLIST_COUNTS = (5, 10, 15, 20)
MIN_PLAYLIST_TRACKS = 2


@dataclass(frozen=True)
class SmartPlaylistFailure:
    source_path: str
    error: str


@dataclass(frozen=True)
class SmartPlaylistResult:
    playlist_name: str
    source_folder: str
    source_track_count: int
    analyzed_track_count: int
    target_track_count: int
    processed_dir: str
    output_path: str
    set_plan: SetPlan
    xml: str
    analyzed_track_ids: list[str] = field(default_factory=list)
    failed_tracks: list[SmartPlaylistFailure] = field(default_factory=list)


def discover_audio_files(folder_path: str | Path, *, recursive: bool = True) -> list[Path]:
    folder = Path(folder_path).expanduser()
    if not folder.exists():
        raise ValueError(f"folder_path does not exist: {folder}")
    if not folder.is_dir():
        raise ValueError(f"folder_path must be a directory: {folder}")
    iterator = folder.rglob("*") if recursive else folder.glob("*")
    return sorted(
        path
        for path in iterator
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def _safe_filename(value: str) -> str:
    text = re.sub(r"[^\w.\-() ]+", "_", value, flags=re.ASCII).strip()
    return text[:120] or "dancelab_playlist"


def _default_output_path(config: EngineConfig, playlist_name: str) -> Path:
    return Path(config.paths.data_dir).expanduser() / "exports" / f"{_safe_filename(playlist_name)}.xml"


def _default_processed_dir(config: EngineConfig) -> Path:
    return Path(config.paths.processed_dir).expanduser() / "smart_playlist"


def _load_or_analyze(
    path: Path,
    *,
    config: EngineConfig,
    repo: FileAnalysisRepository,
    recompute: bool,
    analyze_fn: Callable[..., AnalysisResult],
) -> AnalysisResult:
    track_id = make_track_id(str(path))
    if not recompute and repo._path(track_id).exists():
        return repo.get(track_id)
    result = analyze_fn(path, config)
    repo.save(result)
    return result


def estimate_track_count_for_duration(
    analyses: Sequence[AnalysisResult],
    target_minutes: float,
) -> int:
    """How many tracks fit a target set length, from the analyzed durations.

    Uses the mean duration of tracks whose duration is known. Honest failure:
    if no analyzed track has a known duration, the estimate is impossible —
    raise instead of assuming a made-up average track length.
    """
    if target_minutes <= 0:
        raise ValueError("target_minutes must be positive")
    durations = [
        analysis.track.duration_sec
        for analysis in analyses
        if analysis.track.duration_sec
    ]
    if not durations:
        raise ValueError(
            "no analyzed track has a known duration — pick a track count instead"
        )
    mean_duration_sec = sum(durations) / len(durations)
    count = round((target_minutes * 60.0) / mean_duration_sec)
    return max(MIN_PLAYLIST_TRACKS, min(count, len(analyses)))


def analyze_files(
    source_files: Sequence[str | Path],
    config: EngineConfig,
    *,
    processed_dir: str | Path | None = None,
    recompute: bool = False,
    analyze_fn: Callable[..., AnalysisResult] = analyze_track,
    progress: Callable[[int, int, str], None] | None = None,
    stage_progress: Callable[[str, str], None] | None = None,
) -> tuple[list[AnalysisResult], list[SmartPlaylistFailure]]:
    """Analyze (or load cached) analyses for a list of audio files.

    Failures are collected per file, never raised — the caller decides whether
    a partial library is usable. `progress(done, total, current_path)` fires
    before each file; `stage_progress(path, stage)` relays the pipeline's real
    per-stage hook (key detection, beat tracking, ...) when the analyze
    function supports it — stages are reported by the engine, never simulated.
    """
    processed_root = (
        Path(processed_dir).expanduser() if processed_dir else _default_processed_dir(config)
    )
    repo = FileAnalysisRepository(processed_root)

    effective_analyze_fn = analyze_fn
    if stage_progress is not None and "on_stage" in inspect.signature(analyze_fn).parameters:
        def effective_analyze_fn(path, cfg, _fn=analyze_fn):  # noqa: ANN001
            return _fn(path, cfg, on_stage=lambda stage: stage_progress(str(path), stage))

    analyses: list[AnalysisResult] = []
    failures: list[SmartPlaylistFailure] = []
    total = len(source_files)
    for index, source_path in enumerate(source_files):
        path = Path(source_path)
        if progress is not None:
            progress(index + 1, total, str(path))
        try:
            analyses.append(
                _load_or_analyze(
                    path,
                    config=config,
                    repo=repo,
                    recompute=recompute,
                    analyze_fn=effective_analyze_fn,
                )
            )
        except Exception as exc:
            failures.append(SmartPlaylistFailure(source_path=str(path), error=str(exc)))
    return analyses, failures


def _normalize_analysis_depth(analysis_depth: str) -> str:
    return (analysis_depth or "normal").strip().lower()


def analyze_track_with_stems_only(
    path: str | Path,
    config: EngineConfig,
    *,
    on_stage: Callable[[str], None] | None = None,
) -> AnalysisResult:
    """Run the stem-aware pipeline but return the analysis payload only."""
    result, _stem_bundle = analyze_track_with_stems(path, config, on_stage=on_stage)
    return result


def analysis_function_for_depth(
    analyze_fn: Callable[..., AnalysisResult],
    analysis_depth: str,
) -> Callable[..., AnalysisResult]:
    """Use stem-aware analysis for Deep when the caller uses the default engine."""
    if _normalize_analysis_depth(analysis_depth) == "deep" and analyze_fn is analyze_track:
        return analyze_track_with_stems_only
    return analyze_fn


def config_for_analysis_depth(config: EngineConfig, analysis_depth: str) -> EngineConfig:
    cfg = config.model_copy(deep=True) if hasattr(config, "model_copy") else config
    if _normalize_analysis_depth(analysis_depth) == "deep":
        if hasattr(cfg, "stems") and hasattr(cfg, "analysis"):
            cfg = stem_enabled_config(
                cfg,
                stem_method="demucs",
                vocal_method="demucs",
            )
        if hasattr(cfg, "analysis"):
            cfg.analysis.transition_top_n = max(cfg.analysis.transition_top_n, 8)
    return cfg


def _transition_windows_for_playlist(
    analyses: Sequence[AnalysisResult],
    *,
    config: EngineConfig,
) -> dict[str, list]:
    weights = load_weights(config.weights_file)
    top_k = max(config.analysis.transition_top_n, 6)
    return {
        analysis.track.track_id: detect_transition_windows(
            TransitionWindowInput(
                track_id=analysis.track.track_id,
                segments=analysis.segments,
                feature_frames=analysis.features,
                beatgrid=analysis.beatgrid,
            ),
            weights.transition_window,
            top_k=top_k,
        ).windows
        for analysis in analyses
    }


def build_smart_playlist_from_folder(
    folder_path: str | Path,
    config: EngineConfig,
    *,
    target_track_count: int,
    playlist_name: str = "DanceLab Smart Set",
    output_path: str | Path | None = None,
    processed_dir: str | Path | None = None,
    arc: str = "build",
    planner_mode: str = "smart",
    analysis_depth: str = "normal",
    recursive: bool = True,
    recompute: bool = False,
    analyze_fn: Callable[..., AnalysisResult] = analyze_track,
) -> SmartPlaylistResult:
    """Analyze a music folder and write a Rekordbox XML playlist."""
    if target_track_count < MIN_PLAYLIST_TRACKS:
        raise ValueError(f"target_track_count must be at least {MIN_PLAYLIST_TRACKS}")

    source_files = discover_audio_files(folder_path, recursive=recursive)
    if not source_files:
        raise ValueError(f"no supported audio files found in {folder_path}")

    processed_root = (
        Path(processed_dir).expanduser() if processed_dir else _default_processed_dir(config)
    )
    effective_config = config_for_analysis_depth(config, analysis_depth)
    effective_recompute = recompute or _normalize_analysis_depth(analysis_depth) == "deep"
    effective_analyze_fn = analysis_function_for_depth(analyze_fn, analysis_depth)
    analyses, failures = analyze_files(
        source_files,
        effective_config,
        processed_dir=processed_root,
        recompute=effective_recompute,
        analyze_fn=effective_analyze_fn,
    )

    if not analyses:
        raise ValueError("no tracks could be analyzed from the selected folder")
    if len(analyses) < target_track_count:
        raise ValueError(
            f"target_track_count={target_track_count} needs at least "
            f"{target_track_count} analyzed tracks; got {len(analyses)}"
        )

    weights = load_weights(config.weights_file)
    plan = build_set(
        analyses,
        weights,
        arc=arc,
        target_track_count=target_track_count,
        planner_mode=planner_mode,
    )
    selected_ids = set(plan.track_order)
    selected_analyses = [analysis for analysis in analyses if analysis.track.track_id in selected_ids]
    windows = _transition_windows_for_playlist(selected_analyses, config=effective_config)
    xml = build_rekordbox_xml(
        selected_analyses,
        set_plan=plan,
        windows_by_track=windows,
        playlist_name=playlist_name,
    )
    final_output_path = Path(output_path).expanduser() if output_path else _default_output_path(config, playlist_name)
    written_path = write_rekordbox_xml(xml, final_output_path)
    return SmartPlaylistResult(
        playlist_name=playlist_name,
        source_folder=str(Path(folder_path).expanduser()),
        source_track_count=len(source_files),
        analyzed_track_count=len(analyses),
        target_track_count=target_track_count,
        processed_dir=str(processed_root),
        output_path=str(written_path),
        set_plan=plan,
        xml=xml,
        analyzed_track_ids=[analysis.track.track_id for analysis in analyses],
        failed_tracks=failures,
    )
