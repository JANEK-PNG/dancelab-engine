"""Normalize the source-backed Apple Music NAINA Presents catalogue.

This module is an offline measurement add-on.  It consumes an immutable JSON
snapshot collected from public Apple Music catalogue pages and emits a
normalized, reviewable catalogue.  It deliberately keeps Apple Music mixed
segment identifiers separate from DanceLab audio fingerprints and ISRCs.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Mapping, Sequence


NAINA_RAW_SCHEMA_VERSION = "naina-apple-music-raw-v1"
NAINA_CATALOG_SCHEMA_VERSION = "naina-catalog-v1"
NAINA_SQLITE_SCHEMA_VERSION = "1"

_B2B_RE = re.compile(r"\bb2b\b", re.IGNORECASE)
_ID_TITLE_RE = re.compile(r"^ID(?:\d+)?\b", re.IGNORECASE)
_VOLUME_RE = re.compile(r",\s*Vol\.\s*(?P<volume>\d+)\b", re.IGNORECASE)
_DJ_MIX_SUFFIX_RE = re.compile(
    r"(?:\s*(?:\(DJ Mix\)|\[DJ Mix\]))+\s*$",
    re.IGNORECASE,
)
_MIXED_SUFFIX_RE = re.compile(r"\s*\[Mixed\]\s*$", re.IGNORECASE)
_ISO_DURATION_RE = re.compile(
    r"^PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
)


class NainaCatalogError(ValueError):
    """Raised when source data fails a fail-closed catalogue check."""


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _fingerprint(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_text(mapping: Mapping[str, object], key: str, *, context: str) -> str:
    value = str(mapping.get(key) or "").strip()
    if not value:
        raise NainaCatalogError(f"{context}: missing {key}")
    return value


def _required_int(mapping: Mapping[str, object], key: str, *, context: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool):
        raise NainaCatalogError(f"{context}: invalid {key}")
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise NainaCatalogError(f"{context}: invalid {key}") from exc
    return parsed


def _duration_seconds(value: object, *, context: str) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = _ISO_DURATION_RE.fullmatch(text)
    if match is None:
        raise NainaCatalogError(f"{context}: invalid ISO duration {text!r}")
    return (
        int(match.group("hours") or 0) * 3600
        + int(match.group("minutes") or 0) * 60
        + int(match.group("seconds") or 0)
    )


def _published_billing(title: str, volume: int) -> str:
    prefix = "NAINA Presents:"
    if not title.casefold().startswith(prefix.casefold()):
        raise NainaCatalogError(f"Vol. {volume}: title does not start with {prefix!r}")
    body = title[len(prefix) :].strip()
    match = _VOLUME_RE.search(body)
    if match is None or int(match.group("volume")) != volume:
        raise NainaCatalogError(f"Vol. {volume}: title volume is missing or inconsistent")
    billing = body[: match.start()].strip()
    if not billing:
        raise NainaCatalogError(f"Vol. {volume}: empty published billing")
    return billing


def _strip_dj_mix_suffix(title: str) -> str:
    return _DJ_MIX_SUFFIX_RE.sub("", title).strip()


def _performance_role(
    billing: str,
    creators: Sequence[Mapping[str, object]],
) -> tuple[str, str, bool]:
    if _B2B_RE.search(billing):
        return "b2b", "title_explicit_b2b", False
    if len(creators) == 1:
        return "single_billing", "single_album_creator", False
    if len(creators) > 1:
        return "multi_artist_billing", "multiple_album_creators_without_b2b", True
    return "ambiguous", "missing_album_creator", True


def _review_item(
    *,
    item_id: str,
    entity_type: str,
    entity_id: str,
    issue_code: str,
    severity: str,
    details: str,
) -> dict[str, object]:
    return {
        "review_item_id": item_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "issue_code": issue_code,
        "severity": severity,
        "status": "pending",
        "details": details,
    }


def load_naina_raw_snapshot(path: Path) -> dict[str, object]:
    """Load a source snapshot and preserve its file-level provenance."""

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise NainaCatalogError("raw catalogue root must be an object")
    payload = dict(payload)
    payload["source_file_sha256"] = _file_sha256(path)
    return payload


def normalize_naina_catalog(raw_payload: Mapping[str, object]) -> dict[str, object]:
    """Validate and normalize a NAINA snapshot without adding inferred truth."""

    if raw_payload.get("schema_version") != NAINA_RAW_SCHEMA_VERSION:
        raise NainaCatalogError(f"unsupported raw schema: {raw_payload.get('schema_version')!r}")
    raw_albums = raw_payload.get("albums")
    if not isinstance(raw_albums, list) or not raw_albums:
        raise NainaCatalogError("raw catalogue must contain a non-empty albums list")

    source_sha256 = str(raw_payload.get("source_file_sha256") or "").strip()
    if source_sha256 and not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise NainaCatalogError("source_file_sha256 must be a lowercase SHA-256 digest")

    mixes: list[dict[str, object]] = []
    performers_by_id: dict[str, dict[str, object]] = {}
    mix_performers: list[dict[str, object]] = []
    tracks_by_id: dict[str, dict[str, object]] = {}
    track_artists: list[dict[str, object]] = []
    mix_tracks: list[dict[str, object]] = []
    adjacencies: list[dict[str, object]] = []
    review_items: list[dict[str, object]] = []
    seen_volumes: set[int] = set()
    seen_album_ids: set[str] = set()

    for raw_album in sorted(
        raw_albums,
        key=lambda item: int(item.get("volume", 0)) if isinstance(item, Mapping) else 0,
    ):
        if not isinstance(raw_album, Mapping):
            raise NainaCatalogError("album entries must be objects")
        volume = _required_int(raw_album, "volume", context="album")
        context = f"Vol. {volume}"
        if volume in seen_volumes:
            raise NainaCatalogError(f"duplicate volume: {volume}")
        seen_volumes.add(volume)

        album_id = _required_text(raw_album, "apple_album_id", context=context)
        if album_id in seen_album_ids:
            raise NainaCatalogError(f"duplicate Apple album ID: {album_id}")
        seen_album_ids.add(album_id)
        mix_id = f"apple_music:album:{album_id}"
        album_title = _required_text(raw_album, "album_name", context=context)
        billing = _published_billing(album_title, volume)
        source_url = _required_text(raw_album, "album_url", context=context)
        date_published = _required_text(raw_album, "date_published", context=context)
        try:
            datetime.strptime(date_published, "%Y-%m-%d")
        except ValueError as exc:
            raise NainaCatalogError(f"{context}: invalid date_published") from exc

        raw_creators = raw_album.get("creators")
        if not isinstance(raw_creators, list):
            raise NainaCatalogError(f"{context}: creators must be a list")
        creators: list[Mapping[str, object]] = []
        for creator_index, raw_creator in enumerate(raw_creators, start=1):
            if not isinstance(raw_creator, Mapping):
                raise NainaCatalogError(f"{context}: creator must be an object")
            artist_id = _required_text(raw_creator, "apple_artist_id", context=context)
            performer_id = f"apple_music:artist:{artist_id}"
            performer = {
                "performer_id": performer_id,
                "apple_artist_id": artist_id,
                "name": _required_text(raw_creator, "name", context=context),
                "source_url": _required_text(raw_creator, "url", context=context),
            }
            existing = performers_by_id.get(performer_id)
            if existing is not None and existing != performer:
                raise NainaCatalogError(f"{context}: conflicting creator metadata {artist_id}")
            performers_by_id[performer_id] = performer
            creators.append(raw_creator)
            mix_performers.append(
                {
                    "mix_id": mix_id,
                    "performer_id": performer_id,
                    "published_order": creator_index,
                    "credit_source": "apple_music_album_creator",
                }
            )

        role, role_evidence, role_review_required = _performance_role(billing, creators)
        raw_tracks = raw_album.get("tracks")
        if not isinstance(raw_tracks, list) or not raw_tracks:
            raise NainaCatalogError(f"{context}: tracks must be a non-empty list")
        jsonld_count = _required_int(raw_album, "jsonld_track_count", context=context)
        dom_count = _required_int(raw_album, "dom_track_count", context=context)
        if jsonld_count != dom_count or jsonld_count != len(raw_tracks):
            raise NainaCatalogError(
                f"{context}: track counts disagree "
                f"(jsonld={jsonld_count}, dom={dom_count}, rows={len(raw_tracks)})"
            )

        mix_record = {
            "mix_id": mix_id,
            "apple_album_id": album_id,
            "volume": volume,
            "title": album_title,
            "published_billing": billing,
            "date_published": date_published,
            "source_url": source_url,
            "performance_role_suggestion": role,
            "performance_role_evidence": role_evidence,
            "manual_role_review_required": role_review_required,
            "track_count": len(raw_tracks),
            "genres": list(raw_album.get("genres") or []),
        }
        mixes.append(mix_record)
        if role_review_required:
            review_items.append(
                _review_item(
                    item_id=f"mix-role:{album_id}",
                    entity_type="mix",
                    entity_id=mix_id,
                    issue_code="performance_role_ambiguous",
                    severity="blocking_for_solo_training",
                    details=(
                        f"Published billing {billing!r} has {len(creators)} album creators "
                        "without an explicit b2b marker."
                    ),
                )
            )

        previous_mix_track: dict[str, object] | None = None
        positions: list[int] = []
        for raw_track in raw_tracks:
            if not isinstance(raw_track, Mapping):
                raise NainaCatalogError(f"{context}: track rows must be objects")
            position = _required_int(raw_track, "position", context=context)
            positions.append(position)
            song_id = _required_text(raw_track, "apple_song_id", context=context)
            jsonld_song_id = _required_text(raw_track, "jsonld_song_id", context=context)
            title = _required_text(raw_track, "title", context=context)
            jsonld_title = _required_text(raw_track, "jsonld_title", context=context)
            if song_id != jsonld_song_id:
                raise NainaCatalogError(
                    f"{context} position {position}: DOM and JSON-LD song IDs disagree"
                )
            if title != jsonld_title:
                raise NainaCatalogError(
                    f"{context} position {position}: DOM and JSON-LD titles disagree"
                )
            source_track_id = f"apple_music:song:{song_id}"
            source_track = {
                "source_track_id": source_track_id,
                "apple_mixed_song_id": song_id,
                "title": title,
                "display_title": _MIXED_SUFFIX_RE.sub("", title).strip(),
                "source_url": _required_text(raw_track, "url", context=context),
                "duration_seconds": _duration_seconds(
                    raw_track.get("duration_iso"),
                    context=f"{context} position {position}",
                ),
                "identity_scope": "apple_music_mixed_album_segment",
                "underlying_recording_id": None,
                "is_placeholder_id": bool(_ID_TITLE_RE.match(title)),
            }
            existing_track = tracks_by_id.get(source_track_id)
            if existing_track is not None and existing_track != source_track:
                raise NainaCatalogError(f"conflicting source-track metadata for {song_id}")
            tracks_by_id[source_track_id] = source_track

            raw_artists = raw_track.get("artists")
            if not isinstance(raw_artists, list):
                raise NainaCatalogError(f"{context} position {position}: artists must be a list")
            artist_source = "track_row"
            effective_artists: Sequence[Mapping[str, object]] = raw_artists
            artist_review_required = False
            if not raw_artists:
                effective_artists = creators
                artist_source = "album_creator_fallback"
                artist_review_required = True
                review_items.append(
                    _review_item(
                        item_id=f"track-artist:{song_id}",
                        entity_type="source_track",
                        entity_id=source_track_id,
                        issue_code="artist_credit_fallback",
                        severity="review",
                        details=(
                            f"Vol. {volume} position {position} omits a row-level artist; "
                            "album creators are retained as a provisional fallback."
                        ),
                    )
                )
            for artist_index, raw_artist in enumerate(effective_artists, start=1):
                artist_id = _required_text(raw_artist, "apple_artist_id", context=context)
                performer_id = f"apple_music:artist:{artist_id}"
                performer = {
                    "performer_id": performer_id,
                    "apple_artist_id": artist_id,
                    "name": _required_text(raw_artist, "name", context=context),
                    "source_url": _required_text(raw_artist, "url", context=context),
                }
                existing_performer = performers_by_id.get(performer_id)
                if existing_performer is not None and existing_performer != performer:
                    raise NainaCatalogError(
                        f"{context}: conflicting artist metadata for {artist_id}"
                    )
                performers_by_id[performer_id] = performer
                track_artists.append(
                    {
                        "source_track_id": source_track_id,
                        "performer_id": performer_id,
                        "credit_order": artist_index,
                        "credit_source": artist_source,
                        "manual_review_required": artist_review_required,
                    }
                )

            mix_track = {
                "mix_id": mix_id,
                "position": position,
                "source_track_id": source_track_id,
                "title": title,
                "artist_credit_source": artist_source,
            }
            mix_tracks.append(mix_track)
            if source_track["is_placeholder_id"]:
                review_items.append(
                    _review_item(
                        item_id=f"placeholder:{song_id}",
                        entity_type="source_track",
                        entity_id=source_track_id,
                        issue_code="unidentified_track_placeholder",
                        severity="data_gap",
                        details=f"Vol. {volume} position {position} is published as {title!r}.",
                    )
                )
            if previous_mix_track is not None:
                adjacency_position = position - 1
                adjacencies.append(
                    {
                        "adjacency_id": f"{mix_id}:adjacency:{adjacency_position}",
                        "mix_id": mix_id,
                        "position": adjacency_position,
                        "from_source_track_id": previous_mix_track["source_track_id"],
                        "to_source_track_id": source_track_id,
                        "evidence_scope": "published_tracklist_adjacency",
                    }
                )
            previous_mix_track = mix_track

        expected_positions = list(range(1, len(raw_tracks) + 1))
        if positions != expected_positions:
            raise NainaCatalogError(f"{context}: positions are not contiguous from 1")

    expected_volumes = set(range(1, max(seen_volumes) + 1))
    if seen_volumes != expected_volumes:
        missing = sorted(expected_volumes - seen_volumes)
        raise NainaCatalogError(f"catalogue volumes are not contiguous; missing {missing}")

    performers = sorted(performers_by_id.values(), key=lambda item: item["performer_id"])
    tracks = sorted(tracks_by_id.values(), key=lambda item: item["source_track_id"])
    review_counts = Counter(str(item["issue_code"]) for item in review_items)
    analysis = {
        "volume_range": [min(seen_volumes), max(seen_volumes)],
        "date_range": [
            min(str(mix["date_published"]) for mix in mixes),
            max(str(mix["date_published"]) for mix in mixes),
        ],
        "mix_count": len(mixes),
        "track_slot_count": len(mix_tracks),
        "unique_mixed_segment_count": len(tracks),
        "observed_adjacency_count": len(adjacencies),
        "performer_count": len(performers),
        "explicit_b2b_mix_count": sum(mix["performance_role_suggestion"] == "b2b" for mix in mixes),
        "manual_role_review_mix_count": sum(
            bool(mix["manual_role_review_required"]) for mix in mixes
        ),
        "placeholder_id_track_count": sum(bool(track["is_placeholder_id"]) for track in tracks),
        "review_item_count": len(review_items),
        "review_counts_by_issue": dict(sorted(review_counts.items())),
        "interpretation_limits": [
            "Published adjacency is an observed ordering outcome, not a measured transition boundary.",
            "Apple mixed-song IDs identify compilation segments, not necessarily source masters.",
            "Album-creator fallbacks are provisional artist credits and remain reviewable.",
            "No rejected crate candidates or causal DJ intent are observed in this catalogue.",
        ],
    }
    normalized_body: dict[str, object] = {
        "schema_version": NAINA_CATALOG_SCHEMA_VERSION,
        "source": {
            "name": str(raw_payload.get("source_name") or "Apple Music public catalog"),
            "storefront": str(raw_payload.get("storefront") or ""),
            "raw_schema_version": NAINA_RAW_SCHEMA_VERSION,
            "raw_snapshot_sha256": source_sha256 or _fingerprint(raw_payload),
            "series_urls": list(raw_payload.get("series_urls") or []),
            "fetched_at": str(raw_payload.get("fetched_at") or ""),
        },
        "analysis": analysis,
        "mixes": mixes,
        "performers": performers,
        "mix_performers": mix_performers,
        "tracks": tracks,
        "track_artists": track_artists,
        "mix_tracks": mix_tracks,
        "observed_adjacencies": adjacencies,
        "review_items": review_items,
    }
    normalized_body["fingerprint"] = _fingerprint(normalized_body)
    return normalized_body


def write_naina_catalog_json(catalog: Mapping[str, object], path: Path) -> Path:
    """Write a deterministic normalized JSON catalogue."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def write_naina_catalog_sqlite(catalog: Mapping[str, object], path: Path) -> Path:
    """Atomically write the normalized catalogue to a foreign-keyed SQLite DB."""

    if catalog.get("schema_version") != NAINA_CATALOG_SCHEMA_VERSION:
        raise NainaCatalogError("unsupported normalized catalogue schema")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.unlink(missing_ok=True)
    connection = sqlite3.connect(temporary_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE performers (
                performer_id TEXT PRIMARY KEY,
                apple_artist_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                source_url TEXT NOT NULL
            );
            CREATE TABLE mixes (
                mix_id TEXT PRIMARY KEY,
                apple_album_id TEXT NOT NULL UNIQUE,
                volume INTEGER NOT NULL UNIQUE CHECK (volume > 0),
                title TEXT NOT NULL,
                published_billing TEXT NOT NULL,
                date_published TEXT NOT NULL,
                source_url TEXT NOT NULL,
                performance_role_suggestion TEXT NOT NULL,
                performance_role_evidence TEXT NOT NULL,
                manual_role_review_required INTEGER NOT NULL CHECK (
                    manual_role_review_required IN (0, 1)
                ),
                track_count INTEGER NOT NULL CHECK (track_count > 0),
                genres_json TEXT NOT NULL
            );
            CREATE TABLE mix_performers (
                mix_id TEXT NOT NULL REFERENCES mixes(mix_id) ON DELETE CASCADE,
                performer_id TEXT NOT NULL REFERENCES performers(performer_id),
                published_order INTEGER NOT NULL CHECK (published_order > 0),
                credit_source TEXT NOT NULL,
                PRIMARY KEY (mix_id, published_order),
                UNIQUE (mix_id, performer_id)
            );
            CREATE TABLE tracks (
                source_track_id TEXT PRIMARY KEY,
                apple_mixed_song_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                display_title TEXT NOT NULL,
                source_url TEXT NOT NULL,
                duration_seconds INTEGER,
                identity_scope TEXT NOT NULL,
                underlying_recording_id TEXT,
                is_placeholder_id INTEGER NOT NULL CHECK (is_placeholder_id IN (0, 1))
            );
            CREATE TABLE track_artists (
                source_track_id TEXT NOT NULL REFERENCES tracks(source_track_id),
                performer_id TEXT NOT NULL REFERENCES performers(performer_id),
                credit_order INTEGER NOT NULL CHECK (credit_order > 0),
                credit_source TEXT NOT NULL,
                manual_review_required INTEGER NOT NULL CHECK (
                    manual_review_required IN (0, 1)
                ),
                PRIMARY KEY (source_track_id, credit_order),
                UNIQUE (source_track_id, performer_id, credit_source)
            );
            CREATE TABLE mix_tracks (
                mix_id TEXT NOT NULL REFERENCES mixes(mix_id) ON DELETE CASCADE,
                position INTEGER NOT NULL CHECK (position > 0),
                source_track_id TEXT NOT NULL REFERENCES tracks(source_track_id),
                title TEXT NOT NULL,
                artist_credit_source TEXT NOT NULL,
                PRIMARY KEY (mix_id, position)
            );
            CREATE TABLE observed_adjacencies (
                adjacency_id TEXT PRIMARY KEY,
                mix_id TEXT NOT NULL REFERENCES mixes(mix_id) ON DELETE CASCADE,
                position INTEGER NOT NULL CHECK (position > 0),
                from_source_track_id TEXT NOT NULL REFERENCES tracks(source_track_id),
                to_source_track_id TEXT NOT NULL REFERENCES tracks(source_track_id),
                evidence_scope TEXT NOT NULL,
                UNIQUE (mix_id, position)
            );
            CREATE TABLE review_items (
                review_item_id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                issue_code TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT NOT NULL
            );
            CREATE INDEX idx_mix_tracks_track ON mix_tracks(source_track_id);
            CREATE INDEX idx_track_artists_performer ON track_artists(performer_id);
            CREATE INDEX idx_review_issue_status ON review_items(issue_code, status);
            """
        )
        source = catalog.get("source")
        analysis = catalog.get("analysis")
        if not isinstance(source, Mapping) or not isinstance(analysis, Mapping):
            raise NainaCatalogError("normalized catalogue is missing source or analysis")
        metadata = {
            "schema_version": NAINA_SQLITE_SCHEMA_VERSION,
            "catalog_schema_version": str(catalog["schema_version"]),
            "catalog_fingerprint": str(catalog.get("fingerprint") or ""),
            "source_snapshot_sha256": str(source.get("raw_snapshot_sha256") or ""),
            "source_json": _json_text(source),
            "analysis_json": _json_text(analysis),
        }
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            metadata.items(),
        )
        connection.executemany(
            "INSERT INTO performers VALUES (:performer_id, :apple_artist_id, :name, :source_url)",
            catalog["performers"],
        )
        connection.executemany(
            """
            INSERT INTO mixes VALUES (
                :mix_id, :apple_album_id, :volume, :title, :published_billing,
                :date_published, :source_url, :performance_role_suggestion,
                :performance_role_evidence, :manual_role_review_required, :track_count,
                :genres_json
            )
            """,
            (
                {**mix, "genres_json": _json_text(mix.get("genres") or [])}
                for mix in catalog["mixes"]
            ),
        )
        connection.executemany(
            "INSERT INTO mix_performers VALUES (:mix_id, :performer_id, :published_order, :credit_source)",
            catalog["mix_performers"],
        )
        connection.executemany(
            """
            INSERT INTO tracks VALUES (
                :source_track_id, :apple_mixed_song_id, :title, :display_title,
                :source_url, :duration_seconds, :identity_scope,
                :underlying_recording_id, :is_placeholder_id
            )
            """,
            catalog["tracks"],
        )
        connection.executemany(
            """
            INSERT INTO track_artists VALUES (
                :source_track_id, :performer_id, :credit_order, :credit_source,
                :manual_review_required
            )
            """,
            catalog["track_artists"],
        )
        connection.executemany(
            """
            INSERT INTO mix_tracks VALUES (
                :mix_id, :position, :source_track_id, :title, :artist_credit_source
            )
            """,
            catalog["mix_tracks"],
        )
        connection.executemany(
            """
            INSERT INTO observed_adjacencies VALUES (
                :adjacency_id, :mix_id, :position, :from_source_track_id,
                :to_source_track_id, :evidence_scope
            )
            """,
            catalog["observed_adjacencies"],
        )
        connection.executemany(
            """
            INSERT INTO review_items VALUES (
                :review_item_id, :entity_type, :entity_id, :issue_code,
                :severity, :status, :details
            )
            """,
            catalog["review_items"],
        )
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise NainaCatalogError(f"SQLite foreign-key check failed: {violations[:3]}")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    temporary_path.replace(path)
    return path
