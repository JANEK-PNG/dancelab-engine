"""Batch analysis over a directory of audio files (Runtime Strategy: batch mode)."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from dancelab.core.config import load_config
from dancelab.core.errors import NotImplementedFeature
from dancelab.core.pipeline import analyze_track
from dancelab.ingestion.loader import SUPPORTED_EXTENSIONS
from dancelab.storage.artifact_store import save_json


def batch(
    directory: Path,
    output_dir: Path = typer.Option(Path("data/processed"), "--output-dir", "-o"),
    config: str = typer.Option("configs/default.yaml", "--config", "-c"),
    skip_existing: bool = typer.Option(
        True, "--skip-existing/--recompute", help="Skip tracks with an existing output JSON"
    ),
) -> None:
    """Analyze every supported audio file in DIRECTORY."""
    from dancelab.ingestion.metadata import make_track_id

    cfg = load_config(config)
    files = sorted(
        p for p in directory.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not files:
        typer.secho(f"No audio files found in {directory}", fg="red", err=True)
        sys.exit(2)

    failures = 0
    skipped = 0
    for f in files:
        if skip_existing and (output_dir / f"{make_track_id(str(f))}.json").exists():
            skipped += 1
            continue
        try:
            result = analyze_track(f, cfg)
            save_json(result, output_dir / f"{result.track.track_id}.json")
            typer.echo(f"ok  {f.name}")
        except NotImplementedFeature as exc:
            typer.secho(f"skip {f.name}: not implemented ({exc.status})", fg="yellow")
            failures += 1
        except Exception as exc:  # per-file isolation: one bad file must not kill the batch
            typer.secho(f"fail {f.name}: {exc}", fg="red")
            failures += 1

    typer.echo(
        f"done: {len(files) - failures - skipped}/{len(files)} analyzed, "
        f"{skipped} skipped (existing), {failures} failed"
    )
    if failures == len(files):
        sys.exit(3)
