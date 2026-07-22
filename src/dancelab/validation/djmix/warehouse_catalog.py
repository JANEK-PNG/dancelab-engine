"""Build a source-backed Warehouse Project DJ-mix catalogue from Apple Music.

The module is an offline validation add-on. It parses public Apple Music curator
and album pages, validates the duplicated page representations against each
other, and emits reviewable JSON/SQLite data. Apple mixed-song identifiers are
kept explicitly separate from source-master identifiers and DanceLab audio
fingerprints.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sqlite3
from typing import Mapping, Sequence
from urllib.parse import parse_qs, urlparse


WAREHOUSE_RAW_SCHEMA_VERSION = "warehouse-apple-music-raw-v1"
WAREHOUSE_CATALOG_SCHEMA_VERSION = "warehouse-catalog-v1"
WAREHOUSE_SQLITE_SCHEMA_VERSION = "1"

_DJ_MIX_SUFFIX_RE = re.compile(r"\s*\(DJ Mix\)\s*$", re.IGNORECASE)
_MIXED_SUFFIX_RE = re.compile(r"\s*(?:\[Mixed\]|\(Mixed\))\s*$", re.IGNORECASE)
_ID_TITLE_RE = re.compile(r"^ID(?:\d+)?\b", re.IGNORECASE)
_B2B_RE = re.compile(r"\bb2b\b", re.IGNORECASE)
_WITH_RE = re.compile(r"\bwith\b|\bw/\b", re.IGNORECASE)
_FEATURING_RE = re.compile(r"\bfeaturing\b", re.IGNORECASE)
_EVENT_DATE_RE = re.compile(
    r",\s*(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"(?P<day>\d{1,2}),\s*(?P<year>\d{4})\s*\(DJ Mix\)\s*$",
    re.IGNORECASE,
)
_APPLE_ID_RE = re.compile(r"(?P<identifier>\d+)(?:\?.*)?/?$")


class WarehouseCatalogError(ValueError):
    """Raised when public source data fails a fail-closed catalogue check."""


class _ScriptCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.scripts: dict[str, str] = {}
        self._script_id: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "script":
            return
        attributes = {key: value for key, value in attrs}
        self._script_id = attributes.get("id")
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._script_id is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "script" or self._script_id is None:
            return
        if self._script_id in self.scripts:
            raise WarehouseCatalogError(f"duplicate script id: {self._script_id}")
        self.scripts[self._script_id] = "".join(self._parts)
        self._script_id = None
        self._parts = []


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _fingerprint(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _text_sha256(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_text(mapping: Mapping[str, object], key: str, *, context: str) -> str:
    value = str(mapping.get(key) or "").strip()
    if not value:
        raise WarehouseCatalogError(f"{context}: missing {key}")
    return value


def _required_int(mapping: Mapping[str, object], key: str, *, context: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool):
        raise WarehouseCatalogError(f"{context}: invalid {key}")
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise WarehouseCatalogError(f"{context}: invalid {key}") from exc


def _extract_scripts(html: str) -> dict[str, str]:
    collector = _ScriptCollector()
    collector.feed(html)
    collector.close()
    return collector.scripts


def _json_script(scripts: Mapping[str, str], script_id: str) -> object:
    raw = str(scripts.get(script_id) or "").strip()
    if not raw:
        raise WarehouseCatalogError(f"missing {script_id!r} script")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WarehouseCatalogError(f"invalid JSON in {script_id!r} script") from exc


def _serialized_page(scripts: Mapping[str, str]) -> Mapping[str, object]:
    payload = _json_script(scripts, "serialized-server-data")
    if not isinstance(payload, Mapping):
        raise WarehouseCatalogError("serialized-server-data root must be an object")
    data = payload.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], Mapping):
        raise WarehouseCatalogError("serialized-server-data has no page payload")
    page = data[0].get("data")
    if not isinstance(page, Mapping):
        raise WarehouseCatalogError("serialized-server-data page is missing")
    return page


def _content_descriptor(item: Mapping[str, object]) -> Mapping[str, object]:
    descriptor = item.get("contentDescriptor")
    if not isinstance(descriptor, Mapping):
        raise WarehouseCatalogError("catalogue item is missing contentDescriptor")
    return descriptor


def _store_adam_id(descriptor: Mapping[str, object], *, context: str) -> str:
    identifiers = descriptor.get("identifiers")
    if not isinstance(identifiers, Mapping):
        raise WarehouseCatalogError(f"{context}: missing Apple identifiers")
    identifier = str(identifiers.get("storeAdamID") or "").strip()
    if not identifier.isdigit():
        raise WarehouseCatalogError(f"{context}: invalid storeAdamID")
    return identifier


def _apple_id_from_url(url: object, *, context: str) -> str:
    value = str(url or "").strip()
    match = _APPLE_ID_RE.search(value)
    if match is None:
        raise WarehouseCatalogError(f"{context}: URL has no trailing Apple ID")
    return match.group("identifier")


def _song_id_from_url(url: object, *, context: str) -> str:
    """Read a song ID from either Apple Music's album or direct-song URL form."""

    value = str(url or "").strip()
    if not value:
        raise WarehouseCatalogError(f"{context}: missing song URL")
    query_ids = parse_qs(urlparse(value).query, keep_blank_values=True).get("i", [])
    if query_ids:
        if len(query_ids) != 1 or not query_ids[0].isdigit():
            raise WarehouseCatalogError(f"{context}: ambiguous song ID in URL query")
        return query_ids[0]
    return _apple_id_from_url(value, context=context)


def _title_link(item: Mapping[str, object], *, context: str) -> tuple[str, str]:
    links = item.get("titleLinks")
    if not isinstance(links, list) or not links or not isinstance(links[0], Mapping):
        raise WarehouseCatalogError(f"{context}: missing title link")
    title = _required_text(links[0], "title", context=context)
    descriptor = _content_descriptor(item)
    url = _required_text(descriptor, "url", context=context)
    return title, url


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "untitled"


def _program_from_section(
    section: Mapping[str, object], section_index: int
) -> dict[str, object] | None:
    header = section.get("header")
    if not isinstance(header, Mapping):
        return None
    item = header.get("item")
    if not isinstance(item, Mapping):
        return None
    title_link = item.get("titleLink")
    if not isinstance(title_link, Mapping):
        return None
    title = str(title_link.get("title") or "").strip()
    if not title:
        return None
    url = str(title_link.get("url") or "").strip() or None
    room_id: str | None = None
    segue = title_link.get("segue")
    if isinstance(segue, Mapping):
        destination = segue.get("destination")
        if isinstance(destination, Mapping):
            intent = destination.get("intent")
            if isinstance(intent, Mapping):
                candidate = str(intent.get("id") or "").strip()
                if candidate.isdigit():
                    room_id = candidate
    program_id = (
        f"apple_music:room:{room_id}"
        if room_id is not None
        else f"warehouse:section:{section_index}:{_slug(title)}"
    )
    return {
        "program_id": program_id,
        "apple_room_id": room_id,
        "title": title,
        "source_url": url,
        "section_index": section_index,
        "program_type": "release_shelf" if title.casefold() == "releases" else "dj_mix_program",
    }


def parse_warehouse_curator_html(html: str) -> dict[str, object]:
    """Parse and deduplicate the official Warehouse Project curator page."""

    scripts = _extract_scripts(html)
    page = _serialized_page(scripts)
    sections = page.get("sections")
    if not isinstance(sections, list):
        raise WarehouseCatalogError("curator page has no sections")

    programs: list[dict[str, object]] = []
    items_by_id: dict[str, dict[str, object]] = {}
    memberships: list[dict[str, object]] = []
    shelf_row_count = 0

    for section_index, raw_section in enumerate(sections):
        if not isinstance(raw_section, Mapping):
            continue
        raw_items = raw_section.get("items")
        if not isinstance(raw_items, list):
            continue
        album_items = [
            item
            for item in raw_items
            if isinstance(item, Mapping)
            and isinstance(item.get("contentDescriptor"), Mapping)
            and item["contentDescriptor"].get("kind") == "album"  # type: ignore[index]
        ]
        if not album_items:
            continue
        program = _program_from_section(raw_section, section_index)
        if program is None:
            continue
        programs.append(program)
        for shelf_position, item in enumerate(album_items, start=1):
            descriptor = _content_descriptor(item)
            album_id = _store_adam_id(descriptor, context=f"section {section_index}")
            title, url = _title_link(item, context=f"album {album_id}")
            if _apple_id_from_url(url, context=f"album {album_id}") != album_id:
                raise WarehouseCatalogError(f"album {album_id}: URL ID disagrees")
            subtitle_links = item.get("subtitleLinks")
            published_subtitles = (
                [
                    str(link.get("title") or "").strip()
                    for link in subtitle_links
                    if isinstance(link, Mapping) and str(link.get("title") or "").strip()
                ]
                if isinstance(subtitle_links, list)
                else []
            )
            record = {
                "apple_album_id": album_id,
                "catalog_title": title,
                "album_url": url,
                "published_subtitles": published_subtitles,
            }
            existing = items_by_id.get(album_id)
            if existing is not None and existing != record:
                raise WarehouseCatalogError(f"album {album_id}: conflicting curator metadata")
            items_by_id[album_id] = record
            memberships.append(
                {
                    "apple_album_id": album_id,
                    "program_id": program["program_id"],
                    "shelf_position": shelf_position,
                }
            )
            shelf_row_count += 1

    if not items_by_id:
        raise WarehouseCatalogError("curator page yielded no album items")
    memberships_by_album: dict[str, list[dict[str, object]]] = {}
    for membership in memberships:
        memberships_by_album.setdefault(str(membership["apple_album_id"]), []).append(membership)

    catalog_items: list[dict[str, object]] = []
    for album_id, record in sorted(items_by_id.items(), key=lambda pair: int(pair[0])):
        is_dj_mix = bool(_DJ_MIX_SUFFIX_RE.search(str(record["catalog_title"])))
        observed_memberships = sorted(
            memberships_by_album.get(album_id, []),
            key=lambda item: (str(item["program_id"]), int(item["shelf_position"])),
        )
        catalog_items.append(
            {
                **record,
                "catalog_classification": "dj_mix" if is_dj_mix else "non_dj_release",
                "classification_evidence": (
                    "explicit_title_dj_mix_suffix"
                    if is_dj_mix
                    else "missing_explicit_dj_mix_suffix"
                ),
                "program_memberships": observed_memberships,
            }
        )

    accepted = [item for item in catalog_items if item["catalog_classification"] == "dj_mix"]
    rejected = [
        item for item in catalog_items if item["catalog_classification"] == "non_dj_release"
    ]
    canonical_url = str(page.get("canonicalURL") or "").strip()
    curator_id = _apple_id_from_url(canonical_url, context="curator")
    return {
        "curator": {
            "apple_curator_id": curator_id,
            "title": "The Warehouse Project DJ Mixes",
            "canonical_url": canonical_url,
        },
        "programs": sorted(programs, key=lambda item: int(item["section_index"])),
        "catalog_items": catalog_items,
        "analysis": {
            "section_count": len(sections),
            "program_count": len(programs),
            "shelf_row_count": shelf_row_count,
            "unique_album_count": len(catalog_items),
            "accepted_dj_mix_count": len(accepted),
            "rejected_non_dj_release_count": len(rejected),
        },
        "source_page_sha256": _text_sha256(html),
    }


def _credit_from_link(link: Mapping[str, object]) -> dict[str, object]:
    name = _required_text(link, "title", context="artist credit")
    artist_id: str | None = None
    source_url: str | None = None
    segue = link.get("segue")
    if isinstance(segue, Mapping):
        destination = segue.get("destination")
        if isinstance(destination, Mapping):
            descriptor = destination.get("contentDescriptor")
            if isinstance(descriptor, Mapping) and descriptor.get("kind") == "artist":
                identifiers = descriptor.get("identifiers")
                candidate = (
                    str(identifiers.get("storeAdamID") or "").strip()
                    if isinstance(identifiers, Mapping)
                    else ""
                )
                if candidate:
                    if not candidate.isdigit():
                        raise WarehouseCatalogError(f"artist {name!r}: invalid Apple ID")
                    artist_id = candidate
                source_url = str(descriptor.get("url") or "").strip() or None
                if source_url is not None:
                    url_id = _apple_id_from_url(source_url, context=f"artist {name!r}")
                    if artist_id is not None and url_id != artist_id:
                        raise WarehouseCatalogError(f"artist {name!r}: URL ID disagrees")
                    artist_id = artist_id or url_id
    return {
        "name": name,
        "apple_artist_id": artist_id,
        "url": source_url,
    }


def _jsonld_credit(raw_credit: Mapping[str, object]) -> dict[str, object]:
    name = _required_text(raw_credit, "name", context="JSON-LD artist")
    url = str(raw_credit.get("url") or "").strip() or None
    artist_id = _apple_id_from_url(url, context=f"JSON-LD artist {name!r}") if url else None
    return {"name": name, "apple_artist_id": artist_id, "url": url}


def _find_header(page: Mapping[str, object]) -> Mapping[str, object]:
    sections = page.get("sections")
    if not isinstance(sections, list):
        raise WarehouseCatalogError("album page has no sections")
    for section in sections:
        if not isinstance(section, Mapping):
            continue
        items = section.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, Mapping):
                continue
            descriptor = item.get("contentDescriptor")
            if isinstance(descriptor, Mapping) and descriptor.get("kind") == "album":
                return item
    raise WarehouseCatalogError("album page header is missing")


def _find_track_rows(page: Mapping[str, object], album_id: str) -> list[Mapping[str, object]]:
    sections = page.get("sections")
    if not isinstance(sections, list):
        raise WarehouseCatalogError(f"album {album_id}: page has no sections")
    for section in sections:
        if not isinstance(section, Mapping):
            continue
        section_id = str(section.get("id") or "")
        if not section_id.startswith("track-list - "):
            continue
        items = section.get("items")
        if not isinstance(items, list):
            break
        rows = [
            item
            for item in items
            if isinstance(item, Mapping)
            and isinstance(item.get("contentDescriptor"), Mapping)
            and item["contentDescriptor"].get("kind") == "song"  # type: ignore[index]
        ]
        if rows:
            return rows
    raise WarehouseCatalogError(f"album {album_id}: track rows are missing")


def _performance_role(
    title: str, creators: Sequence[Mapping[str, object]]
) -> tuple[str, str, bool]:
    if _B2B_RE.search(title):
        return "b2b", "title_explicit_b2b", False
    if _FEATURING_RE.search(title):
        return "featuring", "title_explicit_featuring", True
    if _WITH_RE.search(title):
        return "with_support", "title_explicit_with", True
    if len(creators) == 1:
        return "single_billing", "single_album_creator", False
    if len(creators) > 1:
        return "multi_artist_billing", "multiple_album_creators_without_b2b", True
    return "ambiguous", "missing_album_creator", True


def _event_date(title: str) -> str | None:
    match = _EVENT_DATE_RE.search(title)
    if match is None:
        return None
    value = f"{match.group('month')} {match.group('day')} {match.group('year')}"
    return datetime.strptime(value, "%b %d %Y").strftime("%Y-%m-%d")


def _region(title: str, programs: Sequence[str] = ()) -> tuple[str, str]:
    evidence = " | ".join([title, *programs]).casefold()
    if "india" in evidence or "mumbai" in evidence:
        return "india", "title_or_program"
    if "australia" in evidence or "melbourne" in evidence:
        return "australia", "title_or_program"
    if "manchester" in evidence or "haçienda" in evidence or "hacienda" in evidence:
        return "united_kingdom", "title_or_program"
    return "unknown", "no_source_backed_region_marker"


def parse_warehouse_album_html(
    html: str,
    *,
    expected_album_id: str,
    expected_title: str,
) -> dict[str, object]:
    """Parse one DJ-mix album and cross-check DOM data against JSON-LD."""

    scripts = _extract_scripts(html)
    page = _serialized_page(scripts)
    jsonld = _json_script(scripts, "schema:music-album")
    if not isinstance(jsonld, Mapping) or jsonld.get("@type") != "MusicAlbum":
        raise WarehouseCatalogError(f"album {expected_album_id}: invalid MusicAlbum JSON-LD")

    header = _find_header(page)
    descriptor = _content_descriptor(header)
    album_id = _store_adam_id(descriptor, context="album header")
    if album_id != expected_album_id:
        raise WarehouseCatalogError(f"album {expected_album_id}: header ID is {album_id}")
    album_url = _required_text(descriptor, "url", context=f"album {album_id}")
    if _apple_id_from_url(album_url, context=f"album {album_id}") != album_id:
        raise WarehouseCatalogError(f"album {album_id}: URL ID disagrees")
    title = _required_text(header, "title", context=f"album {album_id}")
    jsonld_title = _required_text(jsonld, "name", context=f"album {album_id} JSON-LD")
    if title != expected_title or jsonld_title != title:
        raise WarehouseCatalogError(
            f"album {album_id}: curator, header, and JSON-LD titles disagree"
        )
    if not _DJ_MIX_SUFFIX_RE.search(title):
        raise WarehouseCatalogError(f"album {album_id}: title lacks explicit DJ Mix suffix")

    raw_creator_links = header.get("subtitleLinks")
    if not isinstance(raw_creator_links, list):
        raise WarehouseCatalogError(f"album {album_id}: creator links are missing")
    creators = [_credit_from_link(link) for link in raw_creator_links if isinstance(link, Mapping)]
    raw_jsonld_creators = jsonld.get("byArtist")
    if isinstance(raw_jsonld_creators, Mapping):
        raw_jsonld_creators = [raw_jsonld_creators]
    if not isinstance(raw_jsonld_creators, list):
        raise WarehouseCatalogError(f"album {album_id}: JSON-LD creators are missing")
    jsonld_creators = [
        _jsonld_credit(credit) for credit in raw_jsonld_creators if isinstance(credit, Mapping)
    ]
    if creators != jsonld_creators:
        raise WarehouseCatalogError(f"album {album_id}: creator representations disagree")

    track_rows = _find_track_rows(page, album_id)
    jsonld_tracks = jsonld.get("tracks")
    if not isinstance(jsonld_tracks, list) or not jsonld_tracks:
        raise WarehouseCatalogError(f"album {album_id}: JSON-LD tracks are missing")
    header_count = _required_int(header, "trackCount", context=f"album {album_id}")
    if header_count != len(track_rows) or header_count != len(jsonld_tracks):
        raise WarehouseCatalogError(
            f"album {album_id}: track counts disagree "
            f"(header={header_count}, rows={len(track_rows)}, jsonld={len(jsonld_tracks)})"
        )

    tracks: list[dict[str, object]] = []
    for position, (raw_track, raw_jsonld_track) in enumerate(
        zip(track_rows, jsonld_tracks, strict=True),
        start=1,
    ):
        if not isinstance(raw_jsonld_track, Mapping):
            raise WarehouseCatalogError(f"album {album_id} position {position}: bad JSON-LD row")
        track_number = _required_int(raw_track, "trackNumber", context=f"album {album_id}")
        if track_number != position:
            raise WarehouseCatalogError(f"album {album_id}: positions are not contiguous from 1")
        track_descriptor = _content_descriptor(raw_track)
        song_id = _store_adam_id(
            track_descriptor,
            context=f"album {album_id} position {position}",
        )
        track_url = _required_text(
            track_descriptor,
            "url",
            context=f"album {album_id} position {position}",
        )
        if _song_id_from_url(track_url, context=f"song {song_id}") != song_id:
            raise WarehouseCatalogError(f"album {album_id} position {position}: URL ID disagrees")
        jsonld_song_id = _song_id_from_url(
            raw_jsonld_track.get("url"),
            context=f"album {album_id} JSON-LD position {position}",
        )
        title_value = _required_text(raw_track, "title", context=f"song {song_id}")
        jsonld_track_title = _required_text(
            raw_jsonld_track,
            "name",
            context=f"album {album_id} JSON-LD position {position}",
        )
        if song_id != jsonld_song_id or title_value != jsonld_track_title:
            raise WarehouseCatalogError(
                f"album {album_id} position {position}: row and JSON-LD identity disagree"
            )
        duration_ms = _required_int(
            raw_track,
            "duration",
            context=f"album {album_id} position {position}",
        )
        if duration_ms <= 0:
            raise WarehouseCatalogError(
                f"album {album_id} position {position}: duration must be positive"
            )

        subtitle_links = raw_track.get("subtitleLinks")
        artists: list[dict[str, object]] = []
        artist_credit_source = "subtitle_links"
        if isinstance(subtitle_links, list):
            artists = [
                _credit_from_link(link) for link in subtitle_links if isinstance(link, Mapping)
            ]
        if not artists:
            artist_name = str(raw_track.get("artistName") or "").strip()
            if artist_name:
                artists = [{"name": artist_name, "apple_artist_id": None, "url": None}]
                artist_credit_source = "artist_name_fallback"
            else:
                artist_credit_source = "missing"

        tracks.append(
            {
                "position": position,
                "apple_song_id": song_id,
                "jsonld_song_id": jsonld_song_id,
                "title": title_value,
                "jsonld_title": jsonld_track_title,
                "url": track_url,
                "duration_ms": duration_ms,
                "artists": artists,
                "artist_credit_source": artist_credit_source,
            }
        )

    date_published = _required_text(jsonld, "datePublished", context=f"album {album_id}")
    try:
        datetime.strptime(date_published, "%Y-%m-%d")
    except ValueError as exc:
        raise WarehouseCatalogError(f"album {album_id}: invalid datePublished") from exc
    genres = jsonld.get("genre")
    if isinstance(genres, str):
        genres = [genres]
    if not isinstance(genres, list):
        genres = []
    modal = header.get("modalPresentationDescriptor")
    description = (
        str(modal.get("paragraphText") or "").strip() if isinstance(modal, Mapping) else ""
    )
    return {
        "apple_album_id": album_id,
        "album_name": title,
        "album_url": album_url,
        "date_published": date_published,
        "event_date": _event_date(title),
        "genres": [str(value).strip() for value in genres if str(value).strip()],
        "description": description,
        "creators": creators,
        "header_track_count": header_count,
        "jsonld_track_count": len(jsonld_tracks),
        "tracks": tracks,
        "source_page_sha256": _text_sha256(html),
    }


def load_warehouse_raw_snapshot(path: Path) -> dict[str, object]:
    """Load a raw snapshot and append file-level provenance."""

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise WarehouseCatalogError("raw catalogue root must be an object")
    payload = dict(payload)
    payload["source_file_sha256"] = _file_sha256(path)
    return payload


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


def normalize_warehouse_catalog(raw_payload: Mapping[str, object]) -> dict[str, object]:
    """Validate and normalize a Warehouse snapshot without inferred identities."""

    if raw_payload.get("schema_version") != WAREHOUSE_RAW_SCHEMA_VERSION:
        raise WarehouseCatalogError(
            f"unsupported raw schema: {raw_payload.get('schema_version')!r}"
        )
    raw_programs = raw_payload.get("programs")
    raw_items = raw_payload.get("catalog_items")
    raw_albums = raw_payload.get("albums")
    if not isinstance(raw_programs, list) or not isinstance(raw_items, list):
        raise WarehouseCatalogError("raw snapshot must contain programs and catalog_items")
    if not isinstance(raw_albums, list) or not raw_albums:
        raise WarehouseCatalogError("raw snapshot must contain non-empty albums")

    source_sha256 = str(raw_payload.get("source_file_sha256") or "").strip()
    if source_sha256 and not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise WarehouseCatalogError("source_file_sha256 must be a lowercase SHA-256 digest")

    programs: list[dict[str, object]] = []
    program_ids: set[str] = set()
    for raw_program in raw_programs:
        if not isinstance(raw_program, Mapping):
            raise WarehouseCatalogError("program entries must be objects")
        program_id = _required_text(raw_program, "program_id", context="program")
        if program_id in program_ids:
            raise WarehouseCatalogError(f"duplicate program ID: {program_id}")
        program_ids.add(program_id)
        programs.append(
            {
                "program_id": program_id,
                "apple_room_id": str(raw_program.get("apple_room_id") or "").strip() or None,
                "title": _required_text(raw_program, "title", context=program_id),
                "source_url": str(raw_program.get("source_url") or "").strip() or None,
                "section_index": _required_int(raw_program, "section_index", context=program_id),
                "program_type": _required_text(raw_program, "program_type", context=program_id),
            }
        )

    catalog_items_by_id: dict[str, Mapping[str, object]] = {}
    accepted_ids: set[str] = set()
    rejected_catalog_items: list[dict[str, object]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, Mapping):
            raise WarehouseCatalogError("catalog item entries must be objects")
        album_id = _required_text(raw_item, "apple_album_id", context="catalog item")
        if album_id in catalog_items_by_id:
            raise WarehouseCatalogError(f"duplicate catalog item: {album_id}")
        catalog_items_by_id[album_id] = raw_item
        classification = _required_text(
            raw_item,
            "catalog_classification",
            context=f"catalog item {album_id}",
        )
        if classification == "dj_mix":
            accepted_ids.add(album_id)
        elif classification == "non_dj_release":
            rejected_catalog_items.append(
                {
                    "rejected_item_id": f"apple_music:album:{album_id}",
                    "apple_album_id": album_id,
                    "title": _required_text(raw_item, "catalog_title", context=album_id),
                    "source_url": _required_text(raw_item, "album_url", context=album_id),
                    "reason_code": _required_text(
                        raw_item,
                        "classification_evidence",
                        context=album_id,
                    ),
                }
            )
        else:
            raise WarehouseCatalogError(f"catalog item {album_id}: unknown classification")

    album_ids = {
        _required_text(album, "apple_album_id", context="album")
        for album in raw_albums
        if isinstance(album, Mapping)
    }
    if len(album_ids) != len(raw_albums):
        raise WarehouseCatalogError("albums contain duplicate or invalid IDs")
    if album_ids != accepted_ids:
        missing = sorted(accepted_ids - album_ids)
        extra = sorted(album_ids - accepted_ids)
        raise WarehouseCatalogError(
            f"accepted catalogue and fetched albums disagree; missing={missing[:5]}, extra={extra[:5]}"
        )

    performers_by_id: dict[str, dict[str, object]] = {}
    mixes: list[dict[str, object]] = []
    mix_programs: list[dict[str, object]] = []
    mix_performers: list[dict[str, object]] = []
    tracks_by_id: dict[str, dict[str, object]] = {}
    track_artists_by_key: dict[tuple[str, int], dict[str, object]] = {}
    mix_tracks: list[dict[str, object]] = []
    adjacencies: list[dict[str, object]] = []
    review_items: list[dict[str, object]] = []

    program_titles = {str(item["program_id"]): str(item["title"]) for item in programs}

    def register_performer(raw_credit: Mapping[str, object], context: str) -> str | None:
        artist_id = str(raw_credit.get("apple_artist_id") or "").strip()
        if not artist_id:
            return None
        if not artist_id.isdigit():
            raise WarehouseCatalogError(f"{context}: invalid Apple artist ID")
        performer_id = f"apple_music:artist:{artist_id}"
        performer = {
            "performer_id": performer_id,
            "apple_artist_id": artist_id,
            "name": _required_text(raw_credit, "name", context=context),
            "source_url": str(raw_credit.get("url") or "").strip() or None,
        }
        existing = performers_by_id.get(performer_id)
        if existing is not None and existing != performer:
            raise WarehouseCatalogError(f"{context}: conflicting metadata for {artist_id}")
        performers_by_id[performer_id] = performer
        return performer_id

    for raw_album in sorted(
        raw_albums,
        key=lambda item: int(item.get("apple_album_id", 0)) if isinstance(item, Mapping) else 0,
    ):
        if not isinstance(raw_album, Mapping):
            raise WarehouseCatalogError("album entries must be objects")
        album_id = _required_text(raw_album, "apple_album_id", context="album")
        context = f"album {album_id}"
        catalog_item = catalog_items_by_id[album_id]
        title = _required_text(raw_album, "album_name", context=context)
        if title != _required_text(catalog_item, "catalog_title", context=context):
            raise WarehouseCatalogError(f"{context}: album title differs from curator")
        mix_id = f"apple_music:album:{album_id}"
        raw_creators = raw_album.get("creators")
        if not isinstance(raw_creators, list) or not raw_creators:
            raise WarehouseCatalogError(f"{context}: creators must be a non-empty list")
        creators = [credit for credit in raw_creators if isinstance(credit, Mapping)]
        if len(creators) != len(raw_creators):
            raise WarehouseCatalogError(f"{context}: creator must be an object")
        role, role_evidence, role_review_required = _performance_role(title, creators)

        raw_memberships = catalog_item.get("program_memberships")
        if not isinstance(raw_memberships, list) or not raw_memberships:
            raise WarehouseCatalogError(f"{context}: program memberships are missing")
        membership_program_ids: list[str] = []
        for membership in raw_memberships:
            if not isinstance(membership, Mapping):
                raise WarehouseCatalogError(f"{context}: invalid program membership")
            program_id = _required_text(membership, "program_id", context=context)
            if program_id not in program_ids:
                raise WarehouseCatalogError(f"{context}: unknown program {program_id}")
            membership_program_ids.append(program_id)
            mix_programs.append(
                {
                    "mix_id": mix_id,
                    "program_id": program_id,
                    "shelf_position": _required_int(
                        membership,
                        "shelf_position",
                        context=context,
                    ),
                }
            )
        region, region_evidence = _region(
            title,
            [program_titles[program_id] for program_id in membership_program_ids],
        )
        date_published = _required_text(raw_album, "date_published", context=context)
        try:
            datetime.strptime(date_published, "%Y-%m-%d")
        except ValueError as exc:
            raise WarehouseCatalogError(f"{context}: invalid date_published") from exc

        raw_tracks = raw_album.get("tracks")
        if not isinstance(raw_tracks, list) or not raw_tracks:
            raise WarehouseCatalogError(f"{context}: tracks must be a non-empty list")
        header_count = _required_int(raw_album, "header_track_count", context=context)
        jsonld_count = _required_int(raw_album, "jsonld_track_count", context=context)
        if header_count != jsonld_count or header_count != len(raw_tracks):
            raise WarehouseCatalogError(f"{context}: source track counts disagree")

        mixes.append(
            {
                "mix_id": mix_id,
                "apple_album_id": album_id,
                "title": title,
                "published_billing": " & ".join(
                    _required_text(credit, "name", context=context) for credit in creators
                ),
                "date_published": date_published,
                "event_date": str(raw_album.get("event_date") or "").strip() or None,
                "source_url": _required_text(raw_album, "album_url", context=context),
                "description": str(raw_album.get("description") or "").strip(),
                "performance_role_suggestion": role,
                "performance_role_evidence": role_evidence,
                "manual_role_review_required": role_review_required,
                "region_suggestion": region,
                "region_evidence": region_evidence,
                "track_count": len(raw_tracks),
                "genres": list(raw_album.get("genres") or []),
                "program_count": len(membership_program_ids),
            }
        )
        for creator_index, creator in enumerate(creators, start=1):
            performer_id = register_performer(creator, context)
            mix_performers.append(
                {
                    "mix_id": mix_id,
                    "published_order": creator_index,
                    "performer_id": performer_id,
                    "published_name": _required_text(creator, "name", context=context),
                    "credit_source": "apple_music_album_creator",
                }
            )
            if performer_id is None:
                review_items.append(
                    _review_item(
                        item_id=f"mix-performer-id:{album_id}:{creator_index}",
                        entity_type="mix_performer_credit",
                        entity_id=f"{mix_id}:{creator_index}",
                        issue_code="missing_apple_artist_id",
                        severity="data_gap",
                        details="Published creator name is preserved without inventing an artist ID.",
                    )
                )
        if role_review_required:
            review_items.append(
                _review_item(
                    item_id=f"mix-role:{album_id}",
                    entity_type="mix",
                    entity_id=mix_id,
                    issue_code="performance_role_requires_review",
                    severity="blocking_for_role_specific_training",
                    details=f"Role {role!r} is preserved from title/creator evidence, not collapsed to b2b.",
                )
            )

        positions: list[int] = []
        previous_source_track_id: str | None = None
        for raw_track in raw_tracks:
            if not isinstance(raw_track, Mapping):
                raise WarehouseCatalogError(f"{context}: track rows must be objects")
            position = _required_int(raw_track, "position", context=context)
            positions.append(position)
            song_id = _required_text(raw_track, "apple_song_id", context=context)
            jsonld_song_id = _required_text(raw_track, "jsonld_song_id", context=context)
            title_value = _required_text(raw_track, "title", context=context)
            jsonld_title = _required_text(raw_track, "jsonld_title", context=context)
            if song_id != jsonld_song_id or title_value != jsonld_title:
                raise WarehouseCatalogError(f"{context} position {position}: identity mismatch")
            source_track_id = f"apple_music:song:{song_id}"
            source_track = {
                "source_track_id": source_track_id,
                "apple_mixed_song_id": song_id,
                "title": title_value,
                "display_title": _MIXED_SUFFIX_RE.sub("", title_value).strip(),
                "source_url": _required_text(raw_track, "url", context=context),
                "duration_ms": _required_int(raw_track, "duration_ms", context=context),
                "identity_scope": "apple_music_mixed_album_segment",
                "underlying_recording_id": None,
                "is_placeholder_id": bool(_ID_TITLE_RE.match(title_value)),
            }
            existing_track = tracks_by_id.get(source_track_id)
            if existing_track is not None and existing_track != source_track:
                raise WarehouseCatalogError(f"conflicting source-track metadata for {song_id}")
            tracks_by_id[source_track_id] = source_track

            raw_artists = raw_track.get("artists")
            if not isinstance(raw_artists, list):
                raise WarehouseCatalogError(
                    f"{context} position {position}: artists must be a list"
                )
            credit_source = _required_text(raw_track, "artist_credit_source", context=context)
            for artist_index, raw_artist in enumerate(raw_artists, start=1):
                if not isinstance(raw_artist, Mapping):
                    raise WarehouseCatalogError(f"{context}: artist credit must be an object")
                performer_id = register_performer(raw_artist, context)
                track_artist = {
                    "source_track_id": source_track_id,
                    "credit_order": artist_index,
                    "performer_id": performer_id,
                    "published_name": _required_text(raw_artist, "name", context=context),
                    "credit_source": credit_source,
                    "manual_review_required": performer_id is None,
                }
                track_artist_key = (source_track_id, artist_index)
                existing_track_artist = track_artists_by_key.get(track_artist_key)
                if existing_track_artist is not None and existing_track_artist != track_artist:
                    raise WarehouseCatalogError(
                        f"{context}: conflicting artist credit for {song_id} "
                        f"at order {artist_index}"
                    )
                track_artists_by_key[track_artist_key] = track_artist
                if performer_id is None:
                    review_items.append(
                        _review_item(
                            item_id=f"track-artist-id:{album_id}:{position}:{artist_index}",
                            entity_type="track_artist_credit",
                            entity_id=f"{mix_id}:{position}:{artist_index}",
                            issue_code="missing_apple_artist_id",
                            severity="data_gap",
                            details=(
                                f"Position {position} credit {raw_artist.get('name')!r} is retained "
                                "without inventing an artist ID."
                            ),
                        )
                    )
            if not raw_artists:
                review_items.append(
                    _review_item(
                        item_id=f"track-artist-missing:{album_id}:{position}",
                        entity_type="mix_track",
                        entity_id=f"{mix_id}:{position}",
                        issue_code="missing_track_artist_credit",
                        severity="data_gap",
                        details="Apple Music publishes no row-level artist credit for this segment.",
                    )
                )

            mix_tracks.append(
                {
                    "mix_id": mix_id,
                    "position": position,
                    "source_track_id": source_track_id,
                    "title": title_value,
                    "artist_credit_source": credit_source,
                }
            )
            if source_track["is_placeholder_id"]:
                review_items.append(
                    _review_item(
                        item_id=f"placeholder:{album_id}:{position}",
                        entity_type="source_track",
                        entity_id=source_track_id,
                        issue_code="unidentified_track_placeholder",
                        severity="data_gap",
                        details=f"Album {album_id} position {position} is published as {title_value!r}.",
                    )
                )
            if previous_source_track_id is not None:
                adjacency_position = position - 1
                adjacencies.append(
                    {
                        "adjacency_id": f"{mix_id}:adjacency:{adjacency_position}",
                        "mix_id": mix_id,
                        "position": adjacency_position,
                        "from_source_track_id": previous_source_track_id,
                        "to_source_track_id": source_track_id,
                        "evidence_scope": "published_tracklist_adjacency",
                    }
                )
            previous_source_track_id = source_track_id
        if positions != list(range(1, len(raw_tracks) + 1)):
            raise WarehouseCatalogError(f"{context}: positions are not contiguous from 1")

    performers = sorted(performers_by_id.values(), key=lambda item: item["performer_id"])
    tracks = sorted(tracks_by_id.values(), key=lambda item: item["source_track_id"])
    track_artists = [
        track_artists_by_key[key]
        for key in sorted(track_artists_by_key, key=lambda item: (item[0], item[1]))
    ]
    review_counts = Counter(str(item["issue_code"]) for item in review_items)
    analysis = {
        "date_range": [
            min(str(mix["date_published"]) for mix in mixes),
            max(str(mix["date_published"]) for mix in mixes),
        ],
        "mix_count": len(mixes),
        "program_count": len(programs),
        "mix_program_membership_count": len(mix_programs),
        "multi_program_mix_count": sum(int(mix["program_count"]) > 1 for mix in mixes),
        "rejected_catalog_item_count": len(rejected_catalog_items),
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
            "Published adjacency is an ordering outcome, not a measured transition boundary.",
            "Apple mixed-song IDs identify album segments, not necessarily source masters.",
            "An explicit b2b title is required before assigning the b2b role.",
            "Credits without Apple IDs remain named but unresolved; no identifier is invented.",
            "Curator shelf membership is descriptive and can be many-to-many.",
            "No rejected crate candidates or causal DJ intent are observed in this catalogue.",
        ],
    }
    curator = raw_payload.get("curator")
    if not isinstance(curator, Mapping):
        raise WarehouseCatalogError("raw snapshot is missing curator metadata")
    normalized_body: dict[str, object] = {
        "schema_version": WAREHOUSE_CATALOG_SCHEMA_VERSION,
        "source": {
            "name": str(raw_payload.get("source_name") or "Apple Music public catalog"),
            "storefront": str(raw_payload.get("storefront") or ""),
            "raw_schema_version": WAREHOUSE_RAW_SCHEMA_VERSION,
            "raw_snapshot_sha256": source_sha256 or _fingerprint(raw_payload),
            "curator": dict(curator),
            "curator_page_sha256": str(raw_payload.get("curator_page_sha256") or ""),
            "fetched_at": str(raw_payload.get("fetched_at") or ""),
        },
        "analysis": analysis,
        "programs": programs,
        "mixes": mixes,
        "mix_programs": mix_programs,
        "performers": performers,
        "mix_performers": mix_performers,
        "tracks": tracks,
        "track_artists": track_artists,
        "mix_tracks": mix_tracks,
        "observed_adjacencies": adjacencies,
        "rejected_catalog_items": rejected_catalog_items,
        "review_items": review_items,
    }
    normalized_body["fingerprint"] = _fingerprint(normalized_body)
    return normalized_body


def write_warehouse_catalog_json(catalog: Mapping[str, object], path: Path) -> Path:
    """Write a deterministic normalized JSON catalogue."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def write_warehouse_catalog_sqlite(catalog: Mapping[str, object], path: Path) -> Path:
    """Atomically write the normalized catalogue to a foreign-keyed SQLite DB."""

    if catalog.get("schema_version") != WAREHOUSE_CATALOG_SCHEMA_VERSION:
        raise WarehouseCatalogError("unsupported normalized catalogue schema")
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
                source_url TEXT
            );
            CREATE TABLE programs (
                program_id TEXT PRIMARY KEY,
                apple_room_id TEXT,
                title TEXT NOT NULL,
                source_url TEXT,
                section_index INTEGER NOT NULL,
                program_type TEXT NOT NULL
            );
            CREATE TABLE mixes (
                mix_id TEXT PRIMARY KEY,
                apple_album_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                published_billing TEXT NOT NULL,
                date_published TEXT NOT NULL,
                event_date TEXT,
                source_url TEXT NOT NULL,
                description TEXT NOT NULL,
                performance_role_suggestion TEXT NOT NULL,
                performance_role_evidence TEXT NOT NULL,
                manual_role_review_required INTEGER NOT NULL CHECK (
                    manual_role_review_required IN (0, 1)
                ),
                region_suggestion TEXT NOT NULL,
                region_evidence TEXT NOT NULL,
                track_count INTEGER NOT NULL CHECK (track_count > 0),
                genres_json TEXT NOT NULL,
                program_count INTEGER NOT NULL CHECK (program_count > 0)
            );
            CREATE TABLE mix_programs (
                mix_id TEXT NOT NULL REFERENCES mixes(mix_id) ON DELETE CASCADE,
                program_id TEXT NOT NULL REFERENCES programs(program_id),
                shelf_position INTEGER NOT NULL CHECK (shelf_position > 0),
                PRIMARY KEY (mix_id, program_id)
            );
            CREATE TABLE mix_performers (
                mix_id TEXT NOT NULL REFERENCES mixes(mix_id) ON DELETE CASCADE,
                published_order INTEGER NOT NULL CHECK (published_order > 0),
                performer_id TEXT REFERENCES performers(performer_id),
                published_name TEXT NOT NULL,
                credit_source TEXT NOT NULL,
                PRIMARY KEY (mix_id, published_order)
            );
            CREATE TABLE tracks (
                source_track_id TEXT PRIMARY KEY,
                apple_mixed_song_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                display_title TEXT NOT NULL,
                source_url TEXT NOT NULL,
                duration_ms INTEGER NOT NULL CHECK (duration_ms > 0),
                identity_scope TEXT NOT NULL,
                underlying_recording_id TEXT,
                is_placeholder_id INTEGER NOT NULL CHECK (is_placeholder_id IN (0, 1))
            );
            CREATE TABLE track_artists (
                source_track_id TEXT NOT NULL REFERENCES tracks(source_track_id),
                credit_order INTEGER NOT NULL CHECK (credit_order > 0),
                performer_id TEXT REFERENCES performers(performer_id),
                published_name TEXT NOT NULL,
                credit_source TEXT NOT NULL,
                manual_review_required INTEGER NOT NULL CHECK (
                    manual_review_required IN (0, 1)
                ),
                PRIMARY KEY (source_track_id, credit_order)
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
            CREATE TABLE rejected_catalog_items (
                rejected_item_id TEXT PRIMARY KEY,
                apple_album_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                source_url TEXT NOT NULL,
                reason_code TEXT NOT NULL
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
            CREATE INDEX idx_mix_programs_program ON mix_programs(program_id);
            CREATE INDEX idx_mix_tracks_track ON mix_tracks(source_track_id);
            CREATE INDEX idx_track_artists_performer ON track_artists(performer_id);
            CREATE INDEX idx_review_issue_status ON review_items(issue_code, status);
            """
        )
        source = catalog.get("source")
        analysis = catalog.get("analysis")
        if not isinstance(source, Mapping) or not isinstance(analysis, Mapping):
            raise WarehouseCatalogError("normalized catalogue is missing source or analysis")
        metadata = {
            "schema_version": WAREHOUSE_SQLITE_SCHEMA_VERSION,
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
            "INSERT INTO programs VALUES (:program_id, :apple_room_id, :title, :source_url, :section_index, :program_type)",
            catalog["programs"],
        )
        connection.executemany(
            """
            INSERT INTO mixes VALUES (
                :mix_id, :apple_album_id, :title, :published_billing,
                :date_published, :event_date, :source_url, :description,
                :performance_role_suggestion, :performance_role_evidence,
                :manual_role_review_required, :region_suggestion, :region_evidence,
                :track_count, :genres_json, :program_count
            )
            """,
            (
                {**mix, "genres_json": _json_text(mix.get("genres") or [])}
                for mix in catalog["mixes"]
            ),
        )
        connection.executemany(
            "INSERT INTO mix_programs VALUES (:mix_id, :program_id, :shelf_position)",
            catalog["mix_programs"],
        )
        connection.executemany(
            "INSERT INTO mix_performers VALUES (:mix_id, :published_order, :performer_id, :published_name, :credit_source)",
            catalog["mix_performers"],
        )
        connection.executemany(
            """
            INSERT INTO tracks VALUES (
                :source_track_id, :apple_mixed_song_id, :title, :display_title,
                :source_url, :duration_ms, :identity_scope,
                :underlying_recording_id, :is_placeholder_id
            )
            """,
            catalog["tracks"],
        )
        connection.executemany(
            """
            INSERT INTO track_artists VALUES (
                :source_track_id, :credit_order, :performer_id, :published_name,
                :credit_source, :manual_review_required
            )
            """,
            catalog["track_artists"],
        )
        connection.executemany(
            "INSERT INTO mix_tracks VALUES (:mix_id, :position, :source_track_id, :title, :artist_credit_source)",
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
            "INSERT INTO rejected_catalog_items VALUES (:rejected_item_id, :apple_album_id, :title, :source_url, :reason_code)",
            catalog["rejected_catalog_items"],
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
            raise WarehouseCatalogError(f"SQLite foreign-key check failed: {violations[:3]}")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    temporary_path.replace(path)
    return path
