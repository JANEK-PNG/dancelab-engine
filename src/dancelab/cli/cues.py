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
    write_changes: bool = typer.Option(
        False, "--write",
        help="Actually write. Without it the command only plans and reports (safe default).",
    ),
    allow_live: bool = typer.Option(
        False, "--allow-live",
        help="Required to write the LIVE Rekordbox library. Test on a copy first.",
    ),
    safe_swap: bool = typer.Option(
        True, "--safe-swap/--in-place",
        help="Write to a verified copy and swap it in (default). --in-place edits directly.",
    ),
    db: Path = typer.Option(None, "--db",
                            help="master.db to write. Defaults to the live library, "
                                 "which additionally requires --allow-live."),
    labels: Path = typer.Option(None, "--labels", help="cue_labels.yaml override"),
    backup_dir: Path = typer.Option(DEFAULT_BACKUP_DIR, "--backup-dir"),
    playlist: bool = typer.Option(True, "--playlist/--no-playlist",
                                  help="Also create a native Rekordbox playlist"),
    playlist_name: str = typer.Option(None, "--playlist-name",
                                      help="Playlist name (default: DanceLab set <timestamp>)"),
    timestamp: str = typer.Option(..., "--timestamp", help="backup timestamp, e.g. 20260724_1300"),
):
    target_db = Path(db) if db is not None else DEFAULT_DB
    is_live = target_db.resolve() == DEFAULT_DB.resolve()
    if write_changes and is_live and not allow_live:
        typer.echo("Refusing to write the LIVE Rekordbox library without --allow-live.")
        typer.echo("Test on a copy first:  --db /path/to/copy.db --write")
        raise typer.Exit(2)

    set_plan, analyses, windows = _load_bundle(set)
    label_map = load_cue_labels(labels)
    plan = plan_cues(set_plan, analyses=analyses, windows_by_track=windows,
                     labels=label_map, mode=mode)
    for w in plan.warnings:
        typer.echo(f"⚠ {w}")

    # Resolve against the DB's real tracks + existing cues when the DB is present.
    existing_by_cid: dict = {}
    playlist_ids: list[str] = []
    if target_db.exists():
        from pyrekordbox import Rekordbox6Database
        from pyrekordbox.db6 import tables
        from dancelab.ingestion.rekordbox_match import (
            build_track_refs, match_tracks, remap_plan_content_ids,
        )
        from dancelab.ingestion.rekordbox_cue_writer import read_existing_cues

        rdb = Rekordbox6Database(path=str(target_db))
        mapping, unmatched = match_tracks(build_track_refs(analyses), rdb, tables)
        for tid in unmatched:
            typer.echo(f"⚠ no Rekordbox match for track {tid} — skipped")
        plan, dropped = remap_plan_content_ids(plan, mapping)
        existing_by_cid = read_existing_cues(rdb, tables)
        # ordered ContentIDs for the native playlist (full set order, matched only)
        playlist_ids = [mapping[tid] for tid in set_plan.track_order if tid in mapping]
        rdb.close()

    plan, report = resolve_conflicts(plan, existing_by_cid,
                                     action=on_conflict, review=review)
    typer.echo(render_report(report))

    if not write_changes:
        typer.echo("\n(plan only — nothing written; pass --write to apply)")
        raise typer.Exit(0)

    pl_name = (playlist_name or f"DanceLab set {timestamp}") if playlist else None
    from dancelab.ingestion.rekordbox_cue_writer import write_plan
    result = write_plan(plan, db_path=target_db, backup_dir=backup_dir,
                        timestamp=timestamp, meta={"mode": mode.value}, safe_swap=safe_swap,
                        playlist_name=pl_name, playlist_content_ids=playlist_ids)
    typer.echo(f"✓ wrote {result.written} cues, deleted {result.deleted}, "
               f"verified={result.verified}, backup={result.backup_path}")
    if pl_name:
        typer.echo(f"✓ playlist '{pl_name}' ({len(playlist_ids)} tracks) in DanceLab folder")


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
