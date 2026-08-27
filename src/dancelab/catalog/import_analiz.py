"""Index the analysis JSONs without reading their payload.

Each analysis file is a few hundred kilobytes, almost all of it beatgrid and
descriptor curves; the ``track`` header we need sits in the first kilobyte.
Reading whole files would mean parsing ~3.6 GB to collect ~8k rows, so the
header is extracted by scanning a small prefix and brace-matching the
``"track"`` object. Files whose prefix does not contain the full header fall
back to a normal parse, so nothing is skipped on structural grounds.

Local library versus corpus is recorded in ``analiza.zrodlo``. The 11.08 rule
confines measurements and arguments to the DJ map, and a query cannot honour
that rule unless the origin is stored next to the row.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

DEFAULT_DIR = Path("experiments_priv/2026-07-30_rebuild/processed")

# Enough for the header of every file seen so far; grown on demand below.
_PREFIX_BYTES = 8192

# Corpus material lives in the dedicated corpus tree; everything else in this
# directory came off the DJ's own drives. The classifier therefore lists what
# counts as corpus and treats the remainder as the personal library, so a path
# shape nobody anticipated is filed on the restricted side rather than the
# permissive one. The 11.08 rule is a hard limit and defaults must not erode it.
_CORPUS_MARKERS = ("DanceLabCorpus", "MY_PC/DanceLab", "/corpus/")


def _extract_header(path: Path) -> dict[str, Any] | None:
    """Return the top-level scalars plus the ``track`` object, or None."""
    with path.open("rb") as handle:
        prefix = handle.read(_PREFIX_BYTES)
        marker = prefix.find(b'"track"')
        if marker == -1:
            handle.seek(0)
            try:
                whole = json.load(handle)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
            return {**{k: v for k, v in whole.items() if not isinstance(v, (list, dict))},
                    "track": whole.get("track") or {}}

        start = prefix.find(b"{", marker)
        if start == -1:
            return None
        # Brace-match the track object, growing the buffer if it runs past the
        # prefix. Strings are tracked so a brace inside a title cannot fool it.
        depth, index, in_string, escaped = 0, start, False, False
        buffer = prefix
        while True:
            if index >= len(buffer):
                more = handle.read(_PREFIX_BYTES)
                if not more:
                    return None
                buffer += more
            char = buffer[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == 0x5C:  # backslash
                    escaped = True
                elif char == 0x22:  # quote
                    in_string = False
            elif char == 0x22:
                in_string = True
            elif char == 0x7B:  # {
                depth += 1
            elif char == 0x7D:  # }
                depth -= 1
                if depth == 0:
                    break
            index += 1

        try:
            track = json.loads(buffer[start : index + 1].decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    head: dict[str, Any] = {"track": track}
    # The version scalars precede "track", so they are already in the prefix.
    for name in ("schema_version", "engine_version", "weights_version"):
        needle = f'"{name}"'.encode()
        at = prefix.find(needle)
        if at != -1:
            fragment = prefix[at + len(needle) :].lstrip(b" :")
            if fragment.startswith(b'"'):
                end = fragment.find(b'"', 1)
                head[name] = fragment[1:end].decode("utf-8", "replace")
    return head


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _classify(source_path: str | None) -> str:
    """Corpus only when the path says so; everything else is the local library."""
    if not source_path:
        return "nieznane"
    if any(marker in source_path for marker in _CORPUS_MARKERS):
        return "korpus"
    return "biblioteka_lokalna"


def scan(directory: Path, *, with_checksums: bool = True) -> Iterator[tuple[Any, ...]]:
    """Yield one catalog row per analysis file."""
    for path in sorted(directory.glob("*.json")):
        head = _extract_header(path)
        if head is None:
            continue
        track = head.get("track") or {}
        source_path = track.get("source_path")
        yield (
            track.get("track_id") or path.stem,
            str(path),
            _sha256(path) if with_checksums else None,
            path.stat().st_size,
            track.get("artist"),
            track.get("title"),
            source_path,
            track.get("bpm_estimate"),
            track.get("key_estimate"),
            track.get("key_detection_source"),
            track.get("key_confidence"),
            track.get("duration_sec"),
            head.get("engine_version") or head.get("schema_version"),
            track.get("analysis_date"),
            _classify(source_path),
        )


def run(
    conn: Any,
    directory: Path | None = None,
    *,
    with_checksums: bool = True,
) -> dict[str, int]:
    """Rebuild the ``analiza`` table from a directory of analysis JSONs."""
    target = Path(directory or DEFAULT_DIR)
    if not target.exists():
        raise FileNotFoundError(f"nie znalazlem katalogu analiz: {target}")

    columns = [
        "track_id", "sciezka_json", "suma_kontrolna", "rozmiar_b", "wykonawca",
        "tytul", "sciezka_audio", "bpm", "tonacja", "zrodlo_tonacji",
        "pewnosc_tonacji", "dlugosc_s", "wersja", "data_analizy", "zrodlo",
    ]
    cols = ", ".join(f'"{c}"' for c in columns)

    with conn.cursor() as cur:
        cur.execute("TRUNCATE analiza CASCADE")
        seen: set[str] = set()
        duplikaty = 0
        written = 0
        with cur.copy(f"COPY analiza ({cols}) FROM STDIN") as copy:  # noqa: S608
            for row in scan(target, with_checksums=with_checksums):
                if row[0] in seen:
                    duplikaty += 1
                    continue
                seen.add(row[0])
                copy.write_row(row)
                written += 1
        cur.execute("SELECT zrodlo, count(*) FROM analiza GROUP BY zrodlo")
        wg_zrodla = dict(cur.fetchall())
    conn.commit()
    return {"analiza": written, "_duplikaty_track_id": duplikaty, **{f"_zrodlo_{k}": v for k, v in wg_zrodla.items()}}
