"""Build the ISRC bridge: local files → Apple Music catalog ids.

    .venv/bin/python scripts/apple_isrc_most.py

Reads the ISRC tag of every analysed local file that exists on disk, asks the
Apple Music catalog which song each ISRC is, and writes
``data/reports/isrc_most.json`` (gitignored). Idempotent: ISRCs already in the
bridge are not asked again. Prints counts only — no paths, no tokens.

Needs ``~/.dancelab/musickit/konfig.json`` and the stored user token (the
catalog call itself needs only the developer token, the client is shared).
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dancelab.ingestion.apple_music_api import (  # noqa: E402
    AppleMusicClient, ConfigError, catalog_ids,
)
from dancelab.ingestion.isrc_bridge import (  # noqa: E402
    BRIDGE_FILE, ResolvedSong, collect_isrcs, resolve_isrcs, write_bridge,
)

PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"
LIBRARY = ROOT / "data/reports/apple_library.json"


def local_paths(processed: pathlib.Path) -> tuple[list[str], set[str]]:
    """(local files on disk, catalog ids of streams) from the analysis catalog."""
    local: set[str] = set()
    streams: set[str] = set()
    for f in processed.glob("*.json"):
        sp = (json.loads(f.read_text()).get("track") or {}).get("source_path") or ""
        if sp.startswith("apple-music:tracks:"):
            streams.add(sp.rsplit(":", 1)[1])
        elif sp and pathlib.Path(sp).exists():
            local.add(sp)
    return sorted(local), streams


def main() -> None:
    """Collect ISRCs, resolve the missing ones, write the bridge, print counts."""
    bridge_path = ROOT / BRIDGE_FILE
    lib = json.loads(LIBRARY.read_text()) if LIBRARY.exists() else {}
    storefront = lib.get("storefront")
    if not storefront:
        sys.exit(f"brak {LIBRARY} albo storefrontu — najpierw: "
                 "scripts/apple_music_biblioteka.py biblioteka")
    library_ids = set(catalog_ids(lib.get("songs", [])).values())

    paths, stream_ids = local_paths(PROCESSED)
    files, per_ext = collect_isrcs(paths)
    print(f"pliki lokalne na dysku: {len(paths)}, z ISRC: {len(files)}")
    for ext, (a, b) in sorted(per_ext.items()):
        print(f"  {ext:6} {a}/{b}")

    known: dict[str, ResolvedSong] = {}
    if bridge_path.exists():
        old = json.loads(bridge_path.read_text())
        known = {k: ResolvedSong(**v) for k, v in (old.get("isrc") or {}).items()}
    todo = sorted(set(files.values()) - set(known))
    try:
        client = AppleMusicClient.from_config()
    except ConfigError as exc:
        sys.exit(str(exc))
    fresh = resolve_isrcs(client, todo, storefront, library_ids) if todo else {}
    songs = {**known, **fresh}
    write_bridge(bridge_path, storefront, files, songs)

    unique = set(files.values())
    resolved = unique & set(songs)
    resolved_files = [p for p, i in files.items() if i in songs]
    twins = {songs[i].catalog_id for i in resolved} & stream_ids
    pct = 100 * len(resolved) / len(unique) if unique else 0.0
    print(f"zapytane teraz: {len(todo)}, rozwiązane teraz: {len(fresh)}")
    print(f"ISRC unikalnych: {len(unique)}, rozwiązanych w katalogu {storefront}: "
          f"{len(resolved)} ({pct:.0f} %)")
    print(f"pliki z tożsamością katalogową: {len(resolved_files)}/{len(paths)}")
    print(f"  z tego w bibliotece Janka: "
          f"{sum(1 for i in resolved if songs[i].in_library)}")
    print(f"  bliźniaki plik ↔ strumień w puli: {len(twins)}")
    print(f"zapisane: {BRIDGE_FILE}")


if __name__ == "__main__":
    main()
