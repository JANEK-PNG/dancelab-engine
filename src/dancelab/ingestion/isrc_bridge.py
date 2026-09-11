"""ISRC bridge: one identity for a local file and its Apple Music stream.

Why: the owner's pool is 82 % Apple Music streams (``apple-music:tracks:<id>``)
and 272 local files. The two never met — a file and its stream twin were two
tracks with two analyses, and a local file could not go into an Apple Music
playlist because it had no catalog id. Most local files carry an ISRC in
their tags (measured 2026-09-10: 207 of 272), and the Apple Music API resolves
ISRCs to catalog songs. That is the bridge.

Three parts, each testable alone:

* :func:`read_isrc` — the tag reader (ID3 ``TSRC``, MP4 freeform ISRC, Vorbis
  ``ISRC``), normalized to the 12-character form.
* :func:`resolve_isrcs` — batched ``GET /v1/catalog/{storefront}/songs
  ?filter[isrc]=…`` (25 per call, Apple's documented ceiling), keyed by the
  ISRC Apple returns, never by request order. One ISRC may return several
  songs; the one already in the owner's library wins, else the first.
* the bridge file (``data/reports/isrc_most.json``, gitignored) written once
  by ``scripts/apple_isrc_most.py`` and read by the enrichment pass.

Only counts leave this module; paths and ids stay in the gitignored file.
"""

from __future__ import annotations

import json
import pathlib
import re
import time
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from dancelab.ingestion.apple_music_api import AppleMusicClient

BRIDGE_FILE = pathlib.Path("data/reports/isrc_most.json")
ISRC_BATCH = 25  # "The maximum fetch limit is 25" — Apple Music API, songs by ISRC
_ISRC_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}[0-9]{7}$")


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


# ------------------------------------------------------------------ reader

def normalize_isrc(value: str | None) -> str | None:
    """Upper-case, drop dashes and spaces, accept only the 12-character form."""
    if not value:
        return None
    s = re.sub(r"[\s\-]", "", str(value)).upper()
    return s if _ISRC_RE.match(s) else None


def _first(values: Any) -> str | None:
    if values is None:
        return None
    if isinstance(values, (list, tuple)):
        values = values[0] if values else None
    if values is None:
        return None
    if isinstance(values, bytes):
        return values.decode("utf-8", errors="replace")
    text = getattr(values, "text", None)  # ID3 frames
    if isinstance(text, (list, tuple)):
        return str(text[0]) if text else None
    return str(values)


def read_isrc(path: str | pathlib.Path) -> str | None:
    """The ISRC from a file's tags, or ``None``. Never raises, never reads audio."""
    try:
        from mutagen import File
    except ImportError:
        return None
    p = pathlib.Path(path).expanduser()
    try:
        tagged = File(str(p))
    except Exception:  # noqa: BLE001
        tagged = None
    tags = getattr(tagged, "tags", None) if tagged is not None else None
    if tags is None:
        try:  # a bare ID3 block (test fixtures, odd AIFF/WAV exports)
            from mutagen.id3 import ID3
            tags = ID3(str(p))
        except Exception:  # noqa: BLE001
            return None
    for key in ("TSRC", "----:com.apple.iTunes:ISRC", "ISRC", "isrc"):
        try:
            raw = tags.get(key) if hasattr(tags, "get") else None
        except Exception:  # noqa: BLE001
            raw = None
        isrc = normalize_isrc(_first(raw))
        if isrc:
            return isrc
    # ID3 stores TSRC once; some writers use TXXX:ISRC
    getall = getattr(tags, "getall", None)
    if callable(getall):
        for frame in getall("TXXX"):
            if str(getattr(frame, "desc", "")).upper() == "ISRC":
                isrc = normalize_isrc(_first(frame))
                if isrc:
                    return isrc
    return None


def collect_isrcs(paths: Iterable[str]) -> tuple[dict[str, str], dict[str, tuple[int, int]]]:
    """(NFC path → ISRC) for local files that have one, plus per-extension counts.

    The counts are (with ISRC, total) per lower-case suffix — the shape the
    ledger wants when the reader is questioned.
    """
    found: dict[str, str] = {}
    per_ext: dict[str, list[int]] = {}
    for raw in paths:
        p = pathlib.Path(raw)
        ext = p.suffix.lower() or "(brak)"
        tally = per_ext.setdefault(ext, [0, 0])
        tally[1] += 1
        isrc = read_isrc(p)
        if isrc:
            tally[0] += 1
            found[_nfc(str(p))] = isrc
    return found, {k: (v[0], v[1]) for k, v in per_ext.items()}


# ---------------------------------------------------------------- resolver

@dataclass
class ResolvedSong:
    """What the catalog says about one ISRC — enough for identity and genre."""

    catalog_id: str
    in_library: bool = False
    genre_names: list[str] = field(default_factory=list)
    name: str | None = None
    artist: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"catalog_id": self.catalog_id, "in_library": self.in_library,
                "genre_names": list(self.genre_names), "name": self.name, "artist": self.artist}


def resolve_isrcs(client: AppleMusicClient, isrcs: Iterable[str], storefront: str,
                  library_ids: set[str] | None = None) -> dict[str, ResolvedSong]:
    """ISRC → catalog song, batched by 25, keyed by the ISRC Apple returns."""
    wanted = sorted({i for i in (normalize_isrc(x) for x in isrcs) if i})
    library_ids = library_ids or set()
    out: dict[str, ResolvedSong] = {}
    for start in range(0, len(wanted), ISRC_BATCH):
        chunk = wanted[start:start + ISRC_BATCH]
        page = client.get(f"/v1/catalog/{storefront}/songs", {"filter[isrc]": ",".join(chunk)})
        for song in page.get("data", []):
            attrs = song.get("attributes") or {}
            isrc = normalize_isrc(attrs.get("isrc"))
            cid = str(song.get("id") or "")
            if not isrc or not cid:
                continue
            cand = ResolvedSong(catalog_id=cid, in_library=cid in library_ids,
                                genre_names=[str(g) for g in attrs.get("genreNames") or []],
                                name=attrs.get("name"), artist=attrs.get("artistName"))
            prev = out.get(isrc)
            if prev is None or (cand.in_library and not prev.in_library):
                out[isrc] = cand
    return out


# ------------------------------------------------------------- bridge file

def write_bridge(path: pathlib.Path, storefront: str, files: dict[str, str],
                 songs: dict[str, ResolvedSong]) -> None:
    """Persist the bridge; ``files`` are NFC paths → ISRC, ``songs`` ISRC → catalog."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema_version": "isrc-most-v1", "storefront": storefront,
        "fetched_at": int(time.time()), "files": files,
        "isrc": {k: v.to_dict() for k, v in songs.items()},
    }, ensure_ascii=False, indent=1))


def load_bridge(path: str | pathlib.Path = BRIDGE_FILE) -> tuple[dict[str, dict[str, Any]], str]:
    """(NFC path → {catalog_id, genre_names, …}, note) — empty plus reason when absent."""
    p = pathlib.Path(path)
    if not p.exists():
        return {}, f"brak mostu ISRC: {p} (uruchom scripts/apple_isrc_most.py)"
    try:
        data = json.loads(p.read_text())
    except (OSError, ValueError) as exc:
        return {}, f"most ISRC nieczytelny ({type(exc).__name__}) — pominięty"
    songs = data.get("isrc") or {}
    out: dict[str, dict[str, Any]] = {}
    for file_path, isrc in (data.get("files") or {}).items():
        song = songs.get(isrc)
        if song and song.get("catalog_id"):
            out[_nfc(file_path)] = {"isrc": isrc, **song}
    return out, f"most ISRC: {len(out)} plików z tożsamością katalogową"
