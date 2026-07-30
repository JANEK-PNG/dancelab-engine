#!/usr/bin/env python
"""Remove DanceLab-written cues (and the DanceLab playlist folder) from a
Rekordbox database, leaving everything else — including the DJ's own cues —
untouched.

Surgical alternative to a wholesale restore: use it when the library has moved
on since the backup was taken. Rekordbox must be closed.

    python scripts/cue_cleanup.py <master.db> [--apply]

Without --apply it only reports what it would delete.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Comment markers written by DanceLab's cue exporter.
MARKERS = ("MIX IN", "MIX OUT", "BREAKDOWN", "DROP", "PHRASE", "DANCELAB", "check by ear")
FOLDER_NAME = "DanceLab"


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    if not args:
        raise SystemExit(__doc__)
    db_path = Path(args[0])
    if not db_path.exists():
        raise SystemExit(f"no such database: {db_path}")

    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables
    from pyrekordbox.utils import get_rekordbox_pid

    if get_rekordbox_pid():
        raise SystemExit("Rekordbox is running — close it first.")

    db = Rekordbox6Database(path=str(db_path))
    cues = [
        r for r in db.session.query(tables.DjmdCue).all()
        if r.Comment and any(m in r.Comment for m in MARKERS)
    ]
    folder = db.session.query(tables.DjmdPlaylist).filter(
        tables.DjmdPlaylist.Name == FOLDER_NAME,
        tables.DjmdPlaylist.Attribute == 1,
    ).first()
    children = []
    if folder is not None:
        children = db.session.query(tables.DjmdPlaylist).filter(
            tables.DjmdPlaylist.ParentID == folder.ID
        ).all()

    total = db.session.query(tables.DjmdCue).count()
    print(f"database : {db_path}")
    print(f"cues total: {total}  |  DanceLab cues to remove: {len(cues)}")
    print(f"DanceLab folder: {'yes' if folder else 'no'}  |  playlists inside: {len(children)}")
    for c in cues[:10]:
        print(f"   - Kind={c.Kind} @{c.InMsec}ms  {c.Comment!r}")
    if len(cues) > 10:
        print(f"   ... and {len(cues) - 10} more")

    if not apply:
        print("\n(dry run — pass --apply to delete)")
        db.close()
        return

    for c in cues:
        db.session.delete(c)
    for pl in children:
        for song in db.session.query(tables.DjmdSongPlaylist).filter(
            tables.DjmdSongPlaylist.PlaylistID == pl.ID
        ).all():
            db.session.delete(song)
        db.session.delete(pl)
    if folder is not None:
        db.session.delete(folder)

    db.autoincrement_usn(set_row_usn=True)
    db.commit()
    from sqlalchemy import text
    db.session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
    db.session.commit()
    remaining = db.session.query(tables.DjmdCue).count()
    db.close()
    print(f"\n✓ removed {len(cues)} cues + DanceLab playlists. Cues remaining: {remaining}")


if __name__ == "__main__":
    main()
