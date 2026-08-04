"""One-shot folder analysis -> set plan -> Rekordbox playlist workflow."""

from __future__ import annotations

import json

import inspect
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from dancelab import __version__ as ENGINE_VERSION
from dancelab.core.config import EngineConfig, load_weights
from dancelab.core.models import AnalysisResult, ContextProfile, SetPlan, TransitionWindowInput
from dancelab.core.pipeline import analyze_track, analyze_track_with_stems
from dancelab.decision.set_builder import build_set
from dancelab.decision.transition_windows import detect_transition_windows
# XML wycięty z drogi produktowej (decyzja Janka 01.08): lądował w osobnym
# widoku „rekordbox xml", a nie w bibliotece DJ-a. Produkt pisze teraz paczkę
# cue, którą `dancelab cues write` wkłada wprost do master.db — cue na padach
# i playlista w prawdziwej bibliotece.
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
    bundle_path: str
    analyzed_track_ids: list[str] = field(default_factory=list)
    failed_tracks: list[SmartPlaylistFailure] = field(default_factory=list)


def discover_audio_files(folder_path: str | Path, *, recursive: bool = True) -> list[Path]:
    folder = Path(folder_path).expanduser()
    if not folder.exists():
        raise ValueError(f"folder_path does not exist: {folder}")
    if not folder.is_dir():
        raise ValueError(f"folder_path must be a directory: {folder}")
    # `preflight` istniał od dawna i nie był wołany z żadnej ścieżki produktowej
    # — dlatego 52-minutowe nagranie setu Janka trafiło do listy kandydatów.
    # Tu działa jego tania połowa (po ścieżce); próg długości wymaga otwarcia
    # pliku i pilnuje go wybór kandydatów.
    from dancelab.ingestion.preflight import suspicious_path_reason

    iterator = folder.rglob("*") if recursive else folder.glob("*")
    return sorted(
        path
        for path in iterator
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and suspicious_path_reason(path) is None
    )


def _safe_filename(value: str) -> str:
    text = re.sub(r"[^\w.\-() ]+", "_", value, flags=re.ASCII).strip()
    return text[:120] or "dancelab_playlist"


def _default_output_path(config: EngineConfig, playlist_name: str) -> Path:
    return Path(config.paths.data_dir).expanduser() / "exports" / f"{_safe_filename(playlist_name)}.cues.json"


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


def auto_analysis_workers() -> int:
    """Parallel analysis width (§18): performance cores on Apple Silicon,
    else half the logical CPUs. Capped at 8; at least 1."""
    import os as _os
    import subprocess as _sp
    import sys as _sys

    if _sys.platform == "darwin":
        try:
            perf = int(
                _sp.run(
                    ["sysctl", "-n", "hw.perflevel0.physicalcpu"],
                    capture_output=True, text=True, check=False, timeout=2,
                ).stdout.strip() or 0
            )
            if perf > 0:
                return max(1, min(perf, 8))
        except Exception:
            pass
    return max(1, min((_os.cpu_count() or 2) // 2, 8))


def adopt_orphan_analysis(
    repo: FileAnalysisRepository,
    manifest,
    track_id: str,
    *,
    source_path: Path,
    source_checksum: str,
    tier: str,
    weights_hash: str,
) -> bool:
    """Przygarnij analizę, która leży na dysku, ale nie ma jej w rejestrze.

    Janek zapłacił za to godziną: podał katalog z 243 gotowymi analizami, a silnik
    przeliczył wszystko od nowa. Pliki BYŁY, klucze się zgadzały — brakowało wpisu
    w rejestrze, a to rejestr trzyma sumę kontrolną i odcisk wag. Bez wpisu silnik
    nie wie, CZYM policzono to, co widzi, więc liczy jeszcze raz. Ostrożność jest
    słuszna: analiza naprawdę zależy od wag (groove_density, bass_salience,
    tension), więc użycie cudzego pliku w ciemno dałoby wynik z nieznanych wag.

    Odkąd analiza nosi w sobie `formula_version`, da się to sprawdzić bez rejestru
    — i wtedy, i tylko wtedy, plik zostaje przygarnięty i dopisany do rejestru.
    Analizy sprzed tego pola nie mają jak się wylegitymować i przeliczą się;
    to jednorazowy koszt, nie stały.
    """
    if not repo._path(track_id).exists():
        return False
    try:
        stored = repo.get(track_id)
    except Exception:                                              # noqa: BLE001
        return False
    if stored.engine_version != ENGINE_VERSION:
        return False
    if getattr(stored, "formula_version", None) != weights_hash:
        return False
    manifest.mark_analyzed(
        track_id,
        source_path=str(source_path),
        source_checksum=source_checksum,
        analysis_tier=tier,
        formula_version=weights_hash,
    )
    return True


def _analyze_one_subprocess(
    path_str: str, config_json: str, processed_dir_str: str
) -> tuple[str, str | None]:
    """Worker-process entry: analyze one file, save to repo, return (track_id,
    error). The AnalysisResult itself stays on disk — IPC payload is tiny."""
    from dancelab.core.config import EngineConfig as _EngineConfig

    config = _EngineConfig.model_validate_json(config_json)
    track_id = make_track_id(path_str)
    try:
        result = analyze_track(Path(path_str), config)
        FileAnalysisRepository(processed_dir_str).save(result)
    except Exception as exc:
        return track_id, str(exc)
    return track_id, None


def analyze_files(
    source_files: Sequence[str | Path],
    config: EngineConfig,
    *,
    processed_dir: str | Path | None = None,
    recompute: bool = False,
    tier: str = "quick",
    workers: int = 1,
    analyze_fn: Callable[..., AnalysisResult] = analyze_track,
    progress: Callable[[int, int, str], None] | None = None,
    stage_progress: Callable[[str, str], None] | None = None,
    track_done: Callable[[str, str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> tuple[list[AnalysisResult], list[SmartPlaylistFailure]]:
    """Analyze (or load cached) analyses for a list of audio files.

    Failures are collected per file, never raised — the caller decides whether
    a partial library is usable. `progress(done, total, current_path)` fires
    before each file; `stage_progress(path, stage)` relays the pipeline's real
    per-stage hook (key detection, beat tracking, ...) when the analyze
    function supports it — stages are reported by the engine, never simulated.

    Cooperative cancellation (PRODUCT_SPEC §9): `should_stop()` is checked
    between tracks. On stop, everything analyzed so far is already committed
    to the repository per track, so nothing is lost — the remainder simply
    stays pending and a re-run continues from cache.
    """
    from dancelab.storage.library_manifest import (
        LibraryManifest,
        file_checksum,
        formula_hash,
    )

    processed_root = (
        Path(processed_dir).expanduser() if processed_dir else _default_processed_dir(config)
    )
    repo = FileAnalysisRepository(processed_root)
    manifest = LibraryManifest(processed_root)
    weights_hash = formula_hash(config.weights_file)

    effective_analyze_fn = analyze_fn
    if stage_progress is not None and "on_stage" in inspect.signature(analyze_fn).parameters:
        def effective_analyze_fn(path, cfg, _fn=analyze_fn):  # noqa: ANN001
            return _fn(path, cfg, on_stage=lambda stage: stage_progress(str(path), stage))

    analyses: list[AnalysisResult] = []
    failures: list[SmartPlaylistFailure] = []
    total = len(source_files)

    # §18 CPU parallelism: only for the real, picklable pipeline entry point.
    # Custom analyze_fn (tests, stubs, stage relays) stays sequential.
    if workers > 1 and analyze_fn is analyze_track:
        return _analyze_files_parallel(
            source_files,
            config,
            processed_root=processed_root,
            repo=repo,
            manifest=manifest,
            weights_hash=weights_hash,
            recompute=recompute,
            tier=tier,
            workers=workers,
            progress=progress,
            stage_progress=stage_progress,
            track_done=track_done,
            should_stop=should_stop,
        )
    for index, source_path in enumerate(source_files):
        if should_stop is not None and should_stop():
            break  # stop between tracks; completed work already saved per track
        path = Path(source_path)
        if progress is not None:
            progress(index + 1, total, str(path))
        try:
            track_id = make_track_id(str(path))
            checksum = file_checksum(path)
            reason = (
                "recompute requested"
                if recompute
                else manifest.reuse_reason_or_none(
                    track_id,
                    source_checksum=checksum,
                    requested_tier=tier,
                    formula_version=weights_hash,
                    analysis_file_exists=repo._path(track_id).exists(),
                )
            )
            # „Jeszcze nie liczone" bywa nieprawdą: analiza może leżeć obok,
            # tylko powstała inną drogą (skrypt, inny katalog, poprzednia
            # sesja). Jeśli sama potwierdzi, czym ją policzono — bierzemy ją.
            if reason == "not analyzed yet" and not recompute and adopt_orphan_analysis(
                repo, manifest, track_id,
                source_path=path, source_checksum=checksum,
                tier=tier, weights_hash=weights_hash,
            ):
                reason = None
            if reason is None:
                result = repo.get(track_id)  # §7: valid analysis → zero compute
                if track_done is not None:
                    track_done(str(path), "cached")
            else:
                if stage_progress is not None:
                    stage_progress(str(path), f"Re-analysis: {reason}")
                result = effective_analyze_fn(path, config)
                repo.save(result)
                # manifest identity = source file (make_track_id), matching the
                # repo cache key — stable even when analyzers set custom ids
                manifest.mark_analyzed(
                    track_id,
                    source_path=str(path),
                    source_checksum=checksum,
                    analysis_tier=tier,
                    formula_version=weights_hash,
                )
                if track_done is not None:
                    track_done(str(path), "done")
            analyses.append(result)
        except Exception as exc:
            failures.append(SmartPlaylistFailure(source_path=str(path), error=str(exc)))
            manifest.mark_failed(make_track_id(str(path)), source_path=str(path), error=str(exc))
            if track_done is not None:
                track_done(str(path), "failed")
    return analyses, failures


def _analyze_files_parallel(
    source_files: Sequence[str | Path],
    config: EngineConfig,
    *,
    processed_root: Path,
    repo: FileAnalysisRepository,
    manifest,
    weights_hash: str,
    recompute: bool,
    tier: str,
    workers: int,
    progress: Callable[[int, int, str], None] | None,
    stage_progress: Callable[[str, str], None] | None,
    track_done: Callable[[str, str], None] | None,
    should_stop: Callable[[], bool] | None,
) -> tuple[list[AnalysisResult], list[SmartPlaylistFailure]]:
    """Process-pool fan-out over tracks (§18). Reuse decisions and manifest
    writes stay in the main process; workers only analyze+save. Results are
    reassembled in input order. Per-stage hooks cannot cross processes, so
    parallel mode reports per-track completion, never simulated stages."""
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
    from dancelab.storage.library_manifest import file_checksum

    total = len(source_files)
    results: dict[str, AnalysisResult] = {}
    failures: dict[str, SmartPlaylistFailure] = {}
    checksums: dict[str, str] = {}
    to_compute: list[str] = []
    done_count = 0

    for source_path in source_files:
        path_str = str(Path(source_path))
        track_id = make_track_id(path_str)
        checksum = file_checksum(path_str)
        checksums[path_str] = checksum
        reason = (
            "recompute requested"
            if recompute
            else manifest.reuse_reason_or_none(
                track_id,
                source_checksum=checksum,
                requested_tier=tier,
                formula_version=weights_hash,
                analysis_file_exists=repo._path(track_id).exists(),
            )
        )
        if reason == "not analyzed yet" and not recompute and adopt_orphan_analysis(
            repo, manifest, track_id,
            source_path=Path(path_str), source_checksum=checksum,
            tier=tier, weights_hash=weights_hash,
        ):
            reason = None
        if reason is None:
            results[path_str] = repo.get(track_id)
            done_count += 1
            if progress is not None:
                progress(done_count, total, path_str)
            if track_done is not None:
                track_done(path_str, "cached")
        else:
            to_compute.append(path_str)

    config_json = config.model_dump_json()
    stopped = False
    if to_compute and not (should_stop is not None and should_stop()):
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    _analyze_one_subprocess, path_str, config_json, str(processed_root)
                ): path_str
                for path_str in to_compute
            }
            pending = set(futures)
            while pending:
                finished, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in finished:
                    path_str = futures[future]
                    track_id, error = future.result()
                    done_count += 1
                    if progress is not None:
                        progress(done_count, total, path_str)
                    if error is not None:
                        failures[path_str] = SmartPlaylistFailure(
                            source_path=path_str, error=error
                        )
                        manifest.mark_failed(track_id, source_path=path_str, error=error)
                        if track_done is not None:
                            track_done(path_str, "failed")
                    else:
                        results[path_str] = repo.get(track_id)
                        manifest.mark_analyzed(
                            track_id,
                            source_path=path_str,
                            source_checksum=checksums[path_str],
                            analysis_tier=tier,
                            formula_version=weights_hash,
                        )
                        if track_done is not None:
                            track_done(path_str, "done")
                if should_stop is not None and should_stop() and pending:
                    for future in pending:
                        future.cancel()  # not-yet-started tracks stay pending
                    stopped = True
                    pending = {f for f in pending if f.running()}
    _ = stopped  # running tracks finish and are saved; the rest stays pending

    ordered = [
        results[str(Path(p))] for p in source_files if str(Path(p)) in results
    ]
    ordered_failures = [
        failures[str(Path(p))] for p in source_files if str(Path(p)) in failures
    ]
    return ordered, ordered_failures


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
        if hasattr(cfg, "stems"):
            # M4 benchmark 2026-07-11: overlap 0.10 → ×1.25 faster, cosine
            # 0.99994 vs the 0.25 default — quality-identical fast profile.
            # Recorded in stem provenance via config_hash (stems config hashed).
            cfg.stems.overlap = min(cfg.stems.overlap, 0.10)
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
    target_track_count: int | None = None,
    target_minutes: float | None = None,
    playlist_name: str = "DanceLab Smart Set",
    output_path: str | Path | None = None,
    processed_dir: str | Path | None = None,
    arc: str = "build",
    planner_mode: str = "smart",
    tempo_shape: str = "off",
    analysis_depth: str = "normal",
    recursive: bool = True,
    recompute: bool = False,
    context: ContextProfile | None = None,
    analyze_fn: Callable[..., AnalysisResult] = analyze_track,
    preferred_styles: Sequence[str] | None = None,
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    play_like: str | None = None,
    use_contour: bool = False,
    enrich: bool = True,
) -> SmartPlaylistResult:
    """Analiza folderu → set → paczka cue gotowa do wpisania w master.db.

    `target_minutes` celuje w CZAS setu zamiast liczby utworów (liczba wychodzi
    z realnych długości przeanalizowanej puli — `estimate_track_count_for_duration`).
    `play_like` bierze kotwicę i (przy `use_contour`) kontur prowadzenia
    z `data/reports/dj_anchors.json`; nieznana nazwa = odmowa z podpowiedzią,
    zanim cokolwiek zacznie się analizować.
    """
    if target_track_count is None and target_minutes is None:
        raise ValueError("podaj target_track_count albo target_minutes")
    if target_track_count is not None and target_track_count < MIN_PLAYLIST_TRACKS:
        raise ValueError(f"target_track_count must be at least {MIN_PLAYLIST_TRACKS}")

    # Kotwicę rozstrzygamy PRZED analizą folderu: literówka w nazwisku ma
    # odmówić w sekundę, a nie po dziesięciu minutach liczenia audio.
    anchor = None
    if play_like:
        from dancelab.decision.anchors import resolve_anchor
        anchor = resolve_anchor(play_like)

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

    enrichment_notes: list[str] = []
    if enrich:
        from dancelab.ingestion.analysis_enrichment import (
            attach_rekordbox_genres,
            attach_sound_embeddings,
        )
        emb = attach_sound_embeddings(analyses)
        gen = attach_rekordbox_genres(analyses)
        enrichment_notes += emb.notes + gen.notes
        enrichment_notes.append(
            f"dokarmianie: wektory {emb.attached}, gatunki {gen.attached} "
            f"(braki: {emb.missing}/{gen.missing})")

    if target_track_count is None:
        target_track_count = estimate_track_count_for_duration(
            analyses, float(target_minutes))
        enrichment_notes.append(
            f"cel {target_minutes:.0f} min → {target_track_count} utworów "
            f"(ze średniej realnych długości puli)")
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
        context=context,
        tempo_shape=tempo_shape,
        preferred_styles=preferred_styles,
        bpm_min=bpm_min,
        bpm_max=bpm_max,
        sound_anchor=anchor.centroid if anchor else None,
        anchor_name=anchor.name if anchor else None,
        jump_contour=(anchor.contour if (anchor and use_contour) else None),
    )
    if enrichment_notes:
        plan = plan.model_copy(update={
            "warnings": [*plan.warnings, *enrichment_notes]})
    selected_ids = set(plan.track_order)
    selected_analyses = [analysis for analysis in analyses if analysis.track.track_id in selected_ids]
    windows = _transition_windows_for_playlist(selected_analyses, config=effective_config)
    # Paczka w kształcie, którego oczekuje `dancelab cues write`:
    # {set_plan, analyses, windows}. Sam zapis do master.db zostaje osobną,
    # jawną komendą — nic nie dotyka biblioteki DJ-a bez jego decyzji.
    bundle = {
        "set_plan": plan.model_dump(mode="json"),
        "analyses": {a.track.track_id: a.model_dump(mode="json")
                     for a in selected_analyses},
        "windows": {tid: [w.model_dump(mode="json") for w in ws]
                    for tid, ws in windows.items()},
        "playlist_name": playlist_name,
    }
    final_output_path = (Path(output_path).expanduser() if output_path
                         else _default_output_path(config, playlist_name))
    final_output_path.parent.mkdir(parents=True, exist_ok=True)
    final_output_path.write_text(json.dumps(bundle, ensure_ascii=False))
    written_path = final_output_path
    return SmartPlaylistResult(
        playlist_name=playlist_name,
        source_folder=str(Path(folder_path).expanduser()),
        source_track_count=len(source_files),
        analyzed_track_count=len(analyses),
        target_track_count=target_track_count,
        processed_dir=str(processed_root),
        output_path=str(written_path),
        set_plan=plan,
        bundle_path=str(written_path),
        analyzed_track_ids=[analysis.track.track_id for analysis in analyses],
        failed_tracks=failures,
    )
