"""Create a native Rekordbox playlist (in a DanceLab folder) directly in
master.db — so a set shows up in Rekordbox's Playlists tree with no XML import
and no path re-linking.

pyrekordbox owns folder/playlist creation + USN bookkeeping; we only add the
DanceLab folder (reused across runs) and one playlist per set.
"""

from __future__ import annotations

DEFAULT_FOLDER = "DanceLab"


def ensure_folder(db, tables, name: str = DEFAULT_FOLDER):
    """Return the DanceLab playlist folder, creating it once if absent."""
    existing = db.session.query(tables.DjmdPlaylist).filter(
        tables.DjmdPlaylist.Name == name,
        tables.DjmdPlaylist.Attribute == 1,        # 1 = folder
        tables.DjmdPlaylist.rb_local_deleted == 0,
    ).first()
    if existing is not None:
        return existing
    return db.create_playlist_folder(name)


def create_set_playlist(db, tables, *, name: str, content_ids: list[str],
                        folder_name: str = DEFAULT_FOLDER):
    """Create a playlist under the DanceLab folder and add tracks in order."""
    folder = ensure_folder(db, tables, folder_name)
    playlist = db.create_playlist(name, parent=folder)
    for i, cid in enumerate(content_ids, start=1):
        db.add_to_playlist(playlist, cid, track_no=i)
    return playlist
