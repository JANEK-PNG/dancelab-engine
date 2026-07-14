"""Strong local file identities for offline DJ-mix validation."""

from __future__ import annotations

import hashlib
from pathlib import Path

from dancelab.validation.djmix.models import AudioIdentity


DEFAULT_HASH_CHUNK_BYTES = 1024 * 1024


def identify_audio_file(
    path: str | Path,
    *,
    chunk_bytes: int = DEFAULT_HASH_CHUNK_BYTES,
) -> AudioIdentity:
    """Return a deterministic SHA-256 identity without loading audio into memory."""

    if chunk_bytes <= 0:
        raise ValueError("chunk_bytes must be positive")
    resolved = Path(path).expanduser().resolve(strict=True)
    if not resolved.is_file():
        raise ValueError(f"audio source is not a regular file: {resolved}")

    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        while chunk := handle.read(chunk_bytes):
            digest.update(chunk)
    sha256 = digest.hexdigest()
    return AudioIdentity(
        source_id=f"sha256:{sha256}",
        display_name=resolved.stem,
        resolved_path=str(resolved),
        byte_size=resolved.stat().st_size,
        sha256=sha256,
    )
