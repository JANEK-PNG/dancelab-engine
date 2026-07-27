"""Track -> Rekordbox ContentID resolver. Runs against a copy; skips if absent."""

import shutil
from pathlib import Path

import pytest

pytest.importorskip("pyrekordbox")

from dancelab.ingestion.rekordbox_match import (
    TrackRef, match_tracks, remap_plan_content_ids,
)
from dancelab.decision.cue_export_models import CuePlan, TrackCuePlan, PlannedCue

LIVE = Path.home() / "Library/Pioneer/rekordbox/master.db"


@pytest.fixture()
def db_tables(tmp_path):
    if not LIVE.exists():
        pytest.skip("no local master.db")
    dst = tmp_path / "master.db"
    shutil.copy2(LIVE, dst)
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables
    db = Rekordbox6Database(path=str(dst))
    yield db, tables
    db.close()


def _a_real_track(db, tables):
    row = db.session.query(tables.DjmdContent).filter(
        tables.DjmdContent.FolderPath != None,  # noqa: E711
        tables.DjmdContent.Title != None,  # noqa: E711
    ).first()
    return row


def test_match_by_exact_path(db_tables):
    db, tables = db_tables
    row = _a_real_track(db, tables)
    refs = [TrackRef(track_id="mine1", source_path=row.FolderPath, title="wrong title")]
    mapping, unmatched = match_tracks(refs, db, tables)
    assert mapping["mine1"] == str(row.ID)  # path wins over wrong title
    assert unmatched == []


def test_match_by_title_when_path_missing(db_tables):
    db, tables = db_tables
    row = _a_real_track(db, tables)
    refs = [TrackRef(track_id="mine2", source_path=None, title=row.Title)]
    mapping, _ = match_tracks(refs, db, tables)
    assert mapping.get("mine2") == str(row.ID)


def test_unmatched_reported_not_guessed(db_tables):
    db, tables = db_tables
    refs = [TrackRef(track_id="ghost", source_path="/nope/none.wav",
                     title="__definitely_not_in_library__")]
    mapping, unmatched = match_tracks(refs, db, tables)
    assert "ghost" not in mapping
    assert "ghost" in unmatched


def test_ambiguous_title_is_refused_not_guessed(db_tables):
    """Two library tracks share a title -> refuse to match on title alone."""
    db, tables = db_tables
    from sqlalchemy import func
    dup_title = (
        db.session.query(tables.DjmdContent.Title)
        .filter(tables.DjmdContent.Title != None)  # noqa: E711
        .group_by(tables.DjmdContent.Title)
        .having(func.count(tables.DjmdContent.ID) > 1)
        .first()
    )
    if dup_title is None:
        pytest.skip("library has no duplicate titles to test ambiguity")
    refs = [TrackRef(track_id="ambig", source_path=None, title=dup_title[0])]
    mapping, unmatched = match_tracks(refs, db, tables)
    assert "ambig" not in mapping      # never guesses between duplicates
    assert "ambig" in unmatched


def test_exact_path_still_matches_despite_duplicate_titles(db_tables):
    db, tables = db_tables
    row = _a_real_track(db, tables)
    refs = [TrackRef(track_id="p", source_path=row.FolderPath, title=row.Title)]
    mapping, _ = match_tracks(refs, db, tables)
    assert mapping["p"] == str(row.ID)


def test_remap_plan_swaps_ids_and_drops_unmatched(db_tables):
    db, tables = db_tables
    row = _a_real_track(db, tables)
    plan = CuePlan(tracks=[
        TrackCuePlan(content_id="mine", cues=[
            PlannedCue(content_id="mine", position_ms=1000, kind=1, pad_label="A")]),
        TrackCuePlan(content_id="ghost", cues=[
            PlannedCue(content_id="ghost", position_ms=1000, kind=1, pad_label="A")]),
    ])
    mapping = {"mine": str(row.ID)}
    new_plan, dropped = remap_plan_content_ids(plan, mapping)
    ids = [t.content_id for t in new_plan.tracks]
    assert ids == [str(row.ID)]                 # ghost dropped
    assert new_plan.tracks[0].cues[0].content_id == str(row.ID)
    assert dropped == ["ghost"]
