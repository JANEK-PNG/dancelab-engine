"""`dancelab cues` — plan and write DanceLab hot cues into Rekordbox.

Input is a "bundle" JSON produced upstream (set builder + analysis):
    {
      "set_plan": <SetPlan>,
      "analyses": {track_id: <AnalysisResult>},
      "windows":  {track_id: [<TransitionWindow>]}
    }

`write --dry-run` plans + prints the conflict report and touches nothing.
Without --dry-run it writes to --db (default: live master.db) via the safe
writer, which refuses while Rekordbox is running and backs up first.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from dancelab.core.models import SetPlan, AnalysisResult, TransitionWindow
from dancelab.decision.cue_labels import load_cue_labels
from dancelab.decision.cue_plan import plan_cues
from dancelab.decision.cue_conflict import resolve_conflicts, render_report
from dancelab.decision.cue_export_models import CueContentMode, ConflictAction

app = typer.Typer(name="cues", help="Plan/write DanceLab hot cues into Rekordbox",
                  no_args_is_help=True)

DEFAULT_DB = Path.home() / "Library/Pioneer/rekordbox/master.db"
DEFAULT_BACKUP_DIR = Path.home() / "Library/Pioneer/rekordbox/DanceLab_backups"


def _load_bundle(path: Path):
    data = json.loads(Path(path).read_text())
    set_plan = SetPlan.model_validate(data["set_plan"])
    analyses = {k: AnalysisResult.model_validate(v) for k, v in data.get("analyses", {}).items()}
    windows = {
        k: [TransitionWindow.model_validate(w) for w in v]
        for k, v in data.get("windows", {}).items()
    }
    return set_plan, analyses, windows


@app.command()
def write(
    set: Path = typer.Option(..., "--set", "--bundle", help="Cue-export bundle JSON"),
    mode: CueContentMode = typer.Option(CueContentMode.in_out, "--mode"),
    on_conflict: ConflictAction = typer.Option(ConflictAction.merge, "--on-conflict"),
    review: bool = typer.Option(False, "--review", help="Flag every cue for decision"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan + report only, no write"),
    safe_swap: bool = typer.Option(False, "--safe-swap"),
    db: Path = typer.Option(DEFAULT_DB, "--db", help="master.db to write (default: live)"),
    labels: Path = typer.Option(None, "--labels", help="cue_labels.yaml override"),
    backup_dir: Path = typer.Option(DEFAULT_BACKUP_DIR, "--backup-dir"),
    timestamp: str = typer.Option(..., "--timestamp", help="backup timestamp, e.g. 20260724_1300"),
):
    set_plan, analyses, windows = _load_bundle(set)
    label_map = load_cue_labels(labels)
    plan = plan_cues(set_plan, analyses=analyses, windows_by_track=windows,
                     labels=label_map, mode=mode)
    for w in plan.warnings:
        typer.echo(f"⚠ {w}")

    # Resolve against the DB's real tracks + existing cues when the DB is present.
    existing_by_cid: dict = {}
    if Path(db).exists():
        from pyrekordbox import Rekordbox6Database
        from pyrekordbox.db6 import tables
        from dancelab.ingestion.rekordbox_match import (
            build_track_refs, match_tracks, remap_plan_content_ids,
        )
        from dancelab.ingestion.rekordbox_cue_writer import read_existing_cues

        rdb = Rekordbox6Database(path=str(db))
        mapping, unmatched = match_tracks(build_track_refs(analyses), rdb, tables)
        for tid in unmatched:
            typer.echo(f"⚠ no Rekordbox match for track {tid} — skipped")
        plan, dropped = remap_plan_content_ids(plan, mapping)
        existing_by_cid = read_existing_cues(rdb, tables)
        rdb.close()

    plan, report = resolve_conflicts(plan, existing_by_cid,
                                     action=on_conflict, review=review)
    typer.echo(render_report(report))

    if dry_run:
        typer.echo("\n(dry-run — nothing written)")
        raise typer.Exit(0)

    from dancelab.ingestion.rekordbox_cue_writer import write_plan
    result = write_plan(plan, db_path=db, backup_dir=backup_dir,
                        timestamp=timestamp, meta={"mode": mode.value}, safe_swap=safe_swap)
    typer.echo(f"✓ wrote {result.written} cues, deleted {result.deleted}, "
               f"verified={result.verified}, backup={result.backup_path}")


@app.command()
def restore(
    list_: bool = typer.Option(False, "--list", help="List available backups"),
    to: str = typer.Option(None, "--to", help="Restore the backup with this timestamp"),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
):
    from dancelab.ingestion.rb_backup import list_backups, restore_backup
    if list_:
        for e in list_backups(DEFAULT_BACKUP_DIR):
            meta = e.get("meta", {})
            typer.echo(f"{e['timestamp']}  {e['file']}  {meta}")
        raise typer.Exit(0)
    if to:
        restore_backup(DEFAULT_BACKUP_DIR, db, timestamp=to)
        typer.echo(f"✓ restored {to} → {db}")
        raise typer.Exit(0)
    typer.echo("use --list or --to <timestamp>")
