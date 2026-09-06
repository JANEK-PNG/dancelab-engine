"""Publish complete UTF-8 files without exposing partial writes to readers."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_text_atomic(path: Path, content: str, *, overwrite: bool = True) -> Path:
    """Flush a private sibling file, then publish it atomically.

    With ``overwrite=False``, an existing destination raises FileExistsError
    and remains untouched. Temporary files are removed on publication failure.
    This protects readers from partial JSON; it is not a backup system.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        if overwrite:
            temporary_path.replace(path)
        else:
            # Same filesystem; unlike rename/replace, link cannot clobber a file.
            os.link(temporary_path, path)
        return path
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
