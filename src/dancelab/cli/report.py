"""Decision-report CLI command."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from dancelab.core.errors import DanceLabError
from dancelab.validation.decision_report import build_decision_report


def decision_report(
    processed_dir: Path = typer.Argument(Path("data/processed"), help="Dir of analyzed track JSONs"),
    output_dir: Path = typer.Option(Path("data/reports/decision_report"), "--output-dir", "-o"),
    context: str = typer.Option(None, "--context", help="Optional context profile id, e.g. club_peak"),
    config: str = typer.Option("configs/default.yaml", "--config", "-c"),
) -> None:
    """Build a headless pair-decision report with edge decisions and review data."""
    try:
        paths = build_decision_report(
            processed_dir,
            output_dir,
            config_path=config,
            context_id=context,
        )
    except ValueError as exc:
        typer.secho(f"INPUT ERROR: {exc}", fg="red", err=True)
        sys.exit(2)
    except DanceLabError as exc:
        typer.secho(f"ERROR: {exc}", fg="red", err=True)
        sys.exit(1)

    typer.echo(f"Wrote {paths['decision_summary']}")
    typer.echo(f"Wrote {paths['mixability_pairs']}")
    typer.echo(f"Wrote {paths['edge_decisions']}")
    typer.echo(f"Wrote {paths['edge_decision_payloads']}")
    typer.echo(f"Wrote {paths['edge_decision_review']}")
