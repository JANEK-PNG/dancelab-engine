"""DanceLab CLI. Usage:

    dancelab analyze track.wav --output out.json
    dancelab batch path/to/dir/
    dancelab version

Exit codes: 0 ok · 1 error · 2 bad input · 3 feature specified but not implemented.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from dancelab.core.config import load_config
from dancelab.core.errors import (
    DanceLabError,
    IngestionError,
    NotImplementedFeature,
)
from dancelab.core.pipeline import analyze_track, engine_versions
from dancelab.storage.artifact_store import save_json

app = typer.Typer(name="dancelab", help="DanceLab Engine CLI", no_args_is_help=True)

CONFIG_OPT = typer.Option("configs/default.yaml", "--config", "-c", help="Engine config YAML")


@app.command()
def version(config: str = CONFIG_OPT) -> None:
    """Print engine, config and weights versions."""
    for key, value in engine_versions(load_config(config)).items():
        typer.echo(f"{key}: {value}")


@app.command()
def analyze(
    audio_path: Path,
    output: Path = typer.Option(None, "--output", "-o", help="Write AnalysisResult JSON here"),
    style: str = typer.Option(None, "--style", help="Style label, e.g. techno"),
    bpm: float = typer.Option(None, "--bpm", help="Known BPM hint (tightens beat tracking)"),
    title: str = typer.Option(None, "--title", help="Override track title"),
    artist: str = typer.Option(None, "--artist", help="Override artist"),
    config: str = CONFIG_OPT,
) -> None:
    """Analyze a single track → JSON output.

    AUD-M9: the --context flag was removed — it was a silent no-op (context
    conditioning happens at decision time, e.g. /tracks/{id}/set-function).
    """
    try:
        result = analyze_track(
            audio_path, load_config(config), style_label=style, bpm_hint=bpm,
            title=title, artist=artist,
        )
    except NotImplementedFeature as exc:
        typer.secho(f"NOT IMPLEMENTED (status={exc.status}): {exc}", fg="yellow", err=True)
        sys.exit(3)
    except IngestionError as exc:
        typer.secho(f"INPUT ERROR: {exc}", fg="red", err=True)
        sys.exit(2)
    except DanceLabError as exc:
        typer.secho(f"ERROR: {exc}", fg="red", err=True)
        sys.exit(1)

    if output:
        save_json(result, output)
        typer.echo(f"Wrote {output}")
    else:
        typer.echo(result.model_dump_json(indent=2))


@app.command(name="export-rekordbox")
def export_rekordbox(
    processed_dir: Path = typer.Argument(Path("data/processed"), help="Dir of analysis JSONs"),
    output: Path = typer.Option(Path("dancelab_set.xml"), "--output", "-o"),
    playlist_name: str = typer.Option("DanceLab Set", "--name"),
    arc: str = typer.Option("build", "--arc", help="Energy arc: build/peak/flat"),
    planner_mode: str = typer.Option("smart", "--planner-mode", help="smart/harmonic/bpm"),
    config: str = CONFIG_OPT,
) -> None:
    """Build a set from analyzed tracks and export a Rekordbox XML."""
    from dancelab.core.config import load_weights
    from dancelab.core.models import TransitionWindowInput
    from dancelab.decision.set_builder import build_set
    from dancelab.decision.transition_windows import detect_transition_windows
    from dancelab.export.rekordbox import build_rekordbox_xml, write_rekordbox_xml
    from dancelab.storage.repositories import FileAnalysisRepository

    cfg = load_config(config)
    weights = load_weights(cfg.weights_file)
    repo = FileAnalysisRepository(processed_dir)
    analyses = [repo.get(t) for t in repo.list_track_ids()]
    if len(analyses) < 2:
        typer.secho("need >=2 analyzed tracks", fg="red", err=True)
        sys.exit(2)

    plan = build_set(analyses, weights, arc=arc, planner_mode=planner_mode)
    windows = {
        a.track.track_id: detect_transition_windows(
            TransitionWindowInput(track_id=a.track.track_id, segments=a.segments,
                                  feature_frames=a.features, beatgrid=a.beatgrid),
            weights.transition_window, top_k=cfg.analysis.transition_top_n).windows
        for a in analyses
    }
    xml = build_rekordbox_xml(analyses, set_plan=plan, windows_by_track=windows,
                              playlist_name=playlist_name)
    write_rekordbox_xml(xml, output)
    typer.echo(f"Wrote {output} — {len(plan.track_order)} tracks, mean transition {plan.mean_transition_score}")
    typer.echo("Import: see docs/rekordbox_import.md (enable rekordbox-xml view, uncheck Beatgrid analysis)")


@app.command(name="smart-playlist")
def smart_playlist(
    directory: Path = typer.Argument(..., help="Folder with music files"),
    count: int = typer.Option(10, "--count", "-n", help="Playlist length: 5, 10, 15, or 20"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write Rekordbox XML here"),
    processed_dir: Path | None = typer.Option(None, "--processed-dir", help="Where analysis JSONs are cached"),
    playlist_name: str = typer.Option("DanceLab Smart Set", "--name"),
    arc: str = typer.Option("build", "--arc", help="Energy arc: build/peak/flat"),
    planner_mode: str = typer.Option("smart", "--planner-mode", help="smart/harmonic/bpm"),
    analysis_depth: str = typer.Option("normal", "--analysis-depth", help="normal/deep"),
    recompute: bool = typer.Option(False, "--recompute", help="Re-analyze tracks even if cached"),
    config: str = CONFIG_OPT,
) -> None:
    """Analyze a folder, build a smart set, and export Rekordbox XML."""
    from dancelab.workflows.smart_playlist import build_smart_playlist_from_folder

    try:
        result = build_smart_playlist_from_folder(
            directory,
            load_config(config),
            target_track_count=count,
            playlist_name=playlist_name,
            output_path=output,
            processed_dir=processed_dir,
            arc=arc,
            planner_mode=planner_mode,
            analysis_depth=analysis_depth,
            recompute=recompute,
        )
    except ValueError as exc:
        typer.secho(f"INPUT ERROR: {exc}", fg="red", err=True)
        sys.exit(2)
    except DanceLabError as exc:
        typer.secho(f"ERROR: {exc}", fg="red", err=True)
        sys.exit(1)

    typer.echo(f"Wrote {result.output_path}")
    typer.echo(
        f"Playlist: {result.playlist_name} · {len(result.set_plan.track_order)} tracks "
        f"· mean transition {result.set_plan.mean_transition_score}"
    )
    if result.failed_tracks:
        typer.secho(f"Warnings: {len(result.failed_tracks)} file(s) failed analysis", fg="yellow")
        for failure in result.failed_tracks[:8]:
            typer.secho(f"fail {Path(failure.source_path).name}: {failure.error}", fg="yellow")


@app.command(name="validate-annotations")
def validate_annotations(
    annotations_dir: Path = typer.Argument(Path("data/annotations")),
) -> None:
    """Validate the annotation dataset CSVs (works without audio files)."""
    from dancelab.data.annotation_validator import validate_annotation_dataset

    report = validate_annotation_dataset(annotations_dir)
    for key, count in report.counts.items():
        typer.echo(f"{key}: {count} rows")
    for warning in report.warnings:
        typer.secho(f"warn: {warning}", fg="yellow")
    for error in report.errors:
        typer.secho(f"ERROR: {error}", fg="red")
    if report.valid:
        typer.secho("dataset VALID", fg="green")
    else:
        typer.secho(f"dataset INVALID ({len(report.errors)} errors)", fg="red")
        sys.exit(1)


@app.command(name="validation-pack")
def validation_pack(
    processed_dir: Path = typer.Argument(Path("data/processed")),
    output_dir: Path = typer.Option(Path("data/reports/validation_pack"), "--output-dir", "-o"),
    annotations_dir: Path = typer.Option(Path("data/annotations"), "--annotations-dir"),
    report_dir: Path | None = typer.Option(None, "--report-dir"),
) -> None:
    """Build a bounded validation pack for the current analyzed corpus."""
    from dancelab.validation.pilot_pack import build_validation_pack

    try:
        paths = build_validation_pack(
            processed_dir,
            output_dir,
            annotations_dir=annotations_dir,
            report_dir=report_dir,
        )
    except ValueError as exc:
        typer.secho(f"INPUT ERROR: {exc}", fg="red", err=True)
        sys.exit(2)
    except DanceLabError as exc:
        typer.secho(f"ERROR: {exc}", fg="red", err=True)
        sys.exit(1)

    typer.echo(f"Wrote {paths['summary_json']}")
    typer.echo(f"Wrote {paths['summary_md']}")


@app.command(name="validation-benchmark")
def validation_benchmark(
    ratings_path: list[Path] | None = typer.Argument(
        None,
        help="Rating CSV files or directories. Defaults to the DanceLab validation cache.",
    ),
    output_dir: Path = typer.Option(Path("data/reports/dj_benchmark"), "--output-dir", "-o"),
    min_sessions: int = typer.Option(5, "--min-sessions", help="Minimum complete DJ sessions"),
    min_ratings: int = typer.Option(
        30,
        "--min-ratings",
        help="Minimum rated transitions required for a complete session",
    ),
) -> None:
    """Aggregate DJ transition rating CSVs into a 5-session benchmark report."""
    from dancelab.validation.dj_benchmark import (
        build_benchmark_summary,
        default_validation_cache_dir,
        write_benchmark_report,
    )

    paths = ratings_path or [default_validation_cache_dir()]
    summary = build_benchmark_summary(
        paths,
        min_sessions=min_sessions,
        min_rated_transitions_per_session=min_ratings,
    )
    outputs = write_benchmark_report(summary, output_dir)
    status = "READY FOR TUNING" if summary.is_ready_for_tuning else "NOT READY FOR TUNING"
    typer.echo(f"{status}: {summary.complete_session_count}/{summary.min_sessions} complete sessions")
    typer.echo(f"Rated transitions: {summary.total_rated_count}")
    typer.echo(f"Wrote {outputs['summary_json']}")
    typer.echo(f"Wrote {outputs['summary_md']}")


# batch is registered from cli.batch to keep files per blueprint
from dancelab.cli.batch import batch as _batch  # noqa: E402
from dancelab.cli.corpus_ordering import app as _corpus_ordering_app  # noqa: E402
from dancelab.cli.report import decision_report as _decision_report  # noqa: E402

app.command(name="batch")(_batch)
app.command(name="decision-report")(_decision_report)
app.add_typer(_corpus_ordering_app, name="corpus-ordering")

from dancelab.cli.cues import app as _cues_app  # noqa: E402

app.add_typer(_cues_app, name="cues")


if __name__ == "__main__":
    app()
