from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from dancelab.validation.djmix.warehouse_catalog import (
    WAREHOUSE_CATALOG_SCHEMA_VERSION,
    WAREHOUSE_RAW_SCHEMA_VERSION,
    WarehouseCatalogError,
    normalize_warehouse_catalog,
    parse_warehouse_album_html,
    parse_warehouse_curator_html,
    write_warehouse_catalog_sqlite,
)


def _script(script_id: str, payload: object) -> str:
    return f'<script id="{script_id}">{json.dumps(payload)}</script>'


def _page_html(page: dict[str, object], jsonld: dict[str, object] | None = None) -> str:
    serialized = {"data": [{"data": page}]}
    scripts = [_script("serialized-server-data", serialized)]
    if jsonld is not None:
        scripts.append(_script("schema:music-album", jsonld))
    return "<html><head>" + "".join(scripts) + "</head></html>"


def _artist(name: str, artist_id: str) -> dict[str, object]:
    return {
        "title": name,
        "segue": {
            "destination": {
                "contentDescriptor": {
                    "kind": "artist",
                    "identifiers": {"storeAdamID": artist_id},
                    "url": f"https://music.apple.com/pl/artist/{name}/{artist_id}",
                }
            }
        },
    }


def _jsonld_artist(name: str, artist_id: str) -> dict[str, str]:
    return {
        "@type": "MusicGroup",
        "name": name,
        "url": f"https://music.apple.com/pl/artist/{name}/{artist_id}",
    }


def _album_html(
    *,
    album_id: str,
    title: str,
    creators: list[tuple[str, str]],
    tracks: list[tuple[str, str, list[tuple[str, str]]]],
    direct_track_urls: bool = False,
    jsonld_title: str | None = None,
    jsonld_track_limit: int | None = None,
) -> str:
    creator_links = [_artist(name, artist_id) for name, artist_id in creators]
    header = {
        "contentDescriptor": {
            "kind": "album",
            "identifiers": {"storeAdamID": album_id},
            "url": f"https://music.apple.com/pl/album/test/{album_id}",
        },
        "title": title,
        "subtitleLinks": creator_links,
        "trackCount": len(tracks),
        "modalPresentationDescriptor": {"paragraphText": "Fixture description"},
    }
    rows: list[dict[str, object]] = []
    jsonld_tracks: list[dict[str, str]] = []
    for position, (song_id, track_title, artists) in enumerate(tracks, start=1):
        track_url = (
            f"https://music.apple.com/pl/song/tune/{song_id}"
            if direct_track_urls
            else f"https://music.apple.com/pl/album/test/{album_id}?i={song_id}"
        )
        rows.append(
            {
                "contentDescriptor": {
                    "kind": "song",
                    "identifiers": {"storeAdamID": song_id},
                    "url": track_url,
                },
                "title": track_title,
                "trackNumber": position,
                "duration": 123_000,
                "subtitleLinks": [_artist(name, artist_id) for name, artist_id in artists],
            }
        )
        jsonld_tracks.append(
            {
                "@type": "MusicRecording",
                "name": track_title,
                "url": f"https://music.apple.com/pl/song/tune/{song_id}",
            }
        )
    if jsonld_track_limit is not None:
        jsonld_tracks = jsonld_tracks[:jsonld_track_limit]
    page = {
        "sections": [
            {"items": [header]},
            {"id": f"track-list - {album_id}", "items": rows},
        ]
    }
    jsonld = {
        "@type": "MusicAlbum",
        "name": jsonld_title if jsonld_title is not None else title,
        "url": f"https://music.apple.com/pl/album/test/{album_id}",
        "datePublished": "2026-01-02",
        "genre": ["Dance"],
        "byArtist": [_jsonld_artist(name, artist_id) for name, artist_id in creators],
        "tracks": jsonld_tracks,
    }
    return _page_html(page, jsonld)


def _curator_item(album_id: str, title: str) -> dict[str, object]:
    return {
        "contentDescriptor": {
            "kind": "album",
            "identifiers": {"storeAdamID": album_id},
            "url": f"https://music.apple.com/pl/album/test/{album_id}",
        },
        "titleLinks": [{"title": title}],
        "subtitleLinks": [{"title": "Published DJ"}],
    }


def _curator_section(
    title: str,
    room_id: str,
    items: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "header": {
            "item": {
                "titleLink": {
                    "title": title,
                    "url": f"https://music.apple.com/pl/room/{room_id}",
                    "segue": {"destination": {"intent": {"id": room_id}}},
                }
            }
        },
        "items": items,
    }


def _parsed_album(
    *,
    album_id: str,
    title: str,
    creators: list[tuple[str, str]],
    tracks: list[tuple[str, str, list[tuple[str, str]]]],
    direct_track_urls: bool = False,
) -> dict[str, object]:
    return parse_warehouse_album_html(
        _album_html(
            album_id=album_id,
            title=title,
            creators=creators,
            tracks=tracks,
            direct_track_urls=direct_track_urls,
        ),
        expected_album_id=album_id,
        expected_title=title,
    )


def _raw(
    albums: list[dict[str, object]],
    *,
    rejected: list[tuple[str, str]] | None = None,
) -> dict[str, object]:
    program = {
        "program_id": "apple_music:room:500",
        "apple_room_id": "500",
        "title": "2026 DJ Mixes",
        "source_url": "https://music.apple.com/pl/room/500",
        "section_index": 1,
        "program_type": "dj_mix_program",
    }
    catalog_items = [
        {
            "apple_album_id": album["apple_album_id"],
            "catalog_title": album["album_name"],
            "album_url": album["album_url"],
            "published_subtitles": [],
            "catalog_classification": "dj_mix",
            "classification_evidence": "explicit_title_dj_mix_suffix",
            "program_memberships": [
                {
                    "apple_album_id": album["apple_album_id"],
                    "program_id": program["program_id"],
                    "shelf_position": position,
                }
            ],
        }
        for position, album in enumerate(albums, start=1)
    ]
    for album_id, title in rejected or []:
        catalog_items.append(
            {
                "apple_album_id": album_id,
                "catalog_title": title,
                "album_url": f"https://music.apple.com/pl/album/test/{album_id}",
                "published_subtitles": [],
                "catalog_classification": "non_dj_release",
                "classification_evidence": "missing_explicit_dj_mix_suffix",
                "program_memberships": [
                    {
                        "apple_album_id": album_id,
                        "program_id": program["program_id"],
                        "shelf_position": len(catalog_items) + 1,
                    }
                ],
            }
        )
    return {
        "schema_version": WAREHOUSE_RAW_SCHEMA_VERSION,
        "storefront": "pl",
        "source_name": "Apple Music public catalog",
        "fetched_at": "2026-07-22T12:00:00Z",
        "source_file_sha256": "a" * 64,
        "curator_page_sha256": "b" * 64,
        "curator": {
            "apple_curator_id": "1735396087",
            "title": "The Warehouse Project DJ Mixes",
            "canonical_url": ("https://music.apple.com/pl/curator/test/1735396087"),
        },
        "programs": [program],
        "catalog_items": catalog_items,
        "albums": albums,
    }


def test_curator_deduplicates_mix_across_programs_and_rejects_single():
    mix_title = "The Warehouse Project: DJ A in Manchester (DJ Mix)"
    mix = _curator_item("100", mix_title)
    single = _curator_item("200", "Warehouse Project - Single")
    page = {
        "canonicalURL": (
            "https://music.apple.com/pl/curator/the-warehouse-project-dj-mixes/1735396087"
        ),
        "sections": [
            _curator_section("2026 DJ Mixes", "501", [mix, single]),
            _curator_section("More DJ Mixes", "502", [mix]),
        ],
    }

    parsed = parse_warehouse_curator_html(_page_html(page))

    assert parsed["analysis"]["unique_album_count"] == 2
    assert parsed["analysis"]["accepted_dj_mix_count"] == 1
    assert parsed["analysis"]["rejected_non_dj_release_count"] == 1
    accepted = next(
        item for item in parsed["catalog_items"] if item["catalog_classification"] == "dj_mix"
    )
    assert len(accepted["program_memberships"]) == 2


def test_album_parser_matches_query_and_direct_song_url_identity():
    title = "The Warehouse Project: DJ A in Manchester (DJ Mix)"
    parsed = _parsed_album(
        album_id="100",
        title=title,
        creators=[("DJ A", "10")],
        tracks=[("200", "Tune A (Mixed)", [("Artist A", "20")])],
    )

    assert parsed["apple_album_id"] == "100"
    assert parsed["tracks"][0]["apple_song_id"] == "200"
    assert parsed["tracks"][0]["jsonld_song_id"] == "200"
    assert parsed["tracks"][0]["duration_ms"] == 123_000


def test_role_classification_keeps_b2b_and_with_mc_distinct():
    b2b_title = "The Warehouse Project: DJ A b2b DJ B in Manchester (DJ Mix)"
    with_title = "The Warehouse Project: DJ Marky with MC GQ in Manchester (DJ Mix)"
    b2b = _parsed_album(
        album_id="100",
        title=b2b_title,
        creators=[("DJ A", "10"), ("DJ B", "11")],
        tracks=[("200", "Tune A (Mixed)", [("Artist A", "20")])],
    )
    with_mc = _parsed_album(
        album_id="101",
        title=with_title,
        creators=[("DJ Marky", "12"), ("MC GQ", "13")],
        tracks=[("201", "Tune B (Mixed)", [("Artist B", "21")])],
    )

    catalog = normalize_warehouse_catalog(_raw([b2b, with_mc]))
    roles = {
        mix["apple_album_id"]: (
            mix["performance_role_suggestion"],
            mix["manual_role_review_required"],
        )
        for mix in catalog["mixes"]
    }
    assert roles == {"100": ("b2b", False), "101": ("with_support", True)}
    assert catalog["analysis"]["explicit_b2b_mix_count"] == 1
    assert catalog["analysis"]["manual_role_review_mix_count"] == 1


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"jsonld_title": "Wrong title"}, "titles disagree"),
        ({"jsonld_track_limit": 0}, "JSON-LD tracks are missing"),
    ],
)
def test_album_source_disagreements_fail_closed(kwargs: dict[str, object], message: str):
    title = "The Warehouse Project: DJ A in Manchester (DJ Mix)"
    html = _album_html(
        album_id="100",
        title=title,
        creators=[("DJ A", "10")],
        tracks=[("200", "Tune A (Mixed)", [("Artist A", "20")])],
        **kwargs,
    )

    with pytest.raises(WarehouseCatalogError, match=message):
        parse_warehouse_album_html(
            html,
            expected_album_id="100",
            expected_title=title,
        )


def test_repeated_segment_artist_credit_is_deduplicated():
    first_title = "The Warehouse Project: DJ A in Manchester (DJ Mix)"
    second_title = "The Warehouse Project: DJ B in Manchester (DJ Mix)"
    shared_track = [("200", "Shared Tune (Mixed)", [("Artist A", "20")])]
    first = _parsed_album(
        album_id="100",
        title=first_title,
        creators=[("DJ A", "10")],
        tracks=shared_track,
        direct_track_urls=True,
    )
    second = _parsed_album(
        album_id="101",
        title=second_title,
        creators=[("DJ B", "11")],
        tracks=shared_track,
        direct_track_urls=True,
    )

    catalog = normalize_warehouse_catalog(_raw([first, second]))

    assert len(catalog["tracks"]) == 1
    assert len(catalog["track_artists"]) == 1
    assert len(catalog["mix_tracks"]) == 2


def test_conflicting_repeated_segment_artist_credit_fails_closed():
    first_title = "The Warehouse Project: DJ A in Manchester (DJ Mix)"
    second_title = "The Warehouse Project: DJ B in Manchester (DJ Mix)"
    first = _parsed_album(
        album_id="100",
        title=first_title,
        creators=[("DJ A", "10")],
        tracks=[("200", "Shared Tune (Mixed)", [("Artist A", "20")])],
        direct_track_urls=True,
    )
    second = _parsed_album(
        album_id="101",
        title=second_title,
        creators=[("DJ B", "11")],
        tracks=[("200", "Shared Tune (Mixed)", [("Artist B", "21")])],
        direct_track_urls=True,
    )

    with pytest.raises(WarehouseCatalogError, match="conflicting artist credit"):
        normalize_warehouse_catalog(_raw([first, second]))


def test_sqlite_writer_enforces_relations_and_counts(tmp_path: Path):
    title = "The Warehouse Project: DJ A in Manchester (DJ Mix)"
    album = _parsed_album(
        album_id="100",
        title=title,
        creators=[("DJ A", "10")],
        tracks=[
            ("200", "Tune A (Mixed)", [("Artist A", "20")]),
            ("201", "Tune B (Mixed)", [("Artist B", "21")]),
        ],
    )
    catalog = normalize_warehouse_catalog(
        _raw([album], rejected=[("900", "Warehouse Project - Single")])
    )
    database = write_warehouse_catalog_sqlite(catalog, tmp_path / "catalog.sqlite3")

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT COUNT(*) FROM mixes").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM mix_tracks").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM observed_adjacencies").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM rejected_catalog_items").fetchone()[0] == 1
        fingerprint = connection.execute(
            "SELECT value FROM metadata WHERE key = 'catalog_fingerprint'"
        ).fetchone()[0]
        assert fingerprint == catalog["fingerprint"]


def test_catalog_fingerprint_is_deterministic():
    title = "The Warehouse Project: DJ A in Manchester (DJ Mix)"
    album = _parsed_album(
        album_id="100",
        title=title,
        creators=[("DJ A", "10")],
        tracks=[("200", "Tune A (Mixed)", [("Artist A", "20")])],
    )
    raw = _raw([album])

    first = normalize_warehouse_catalog(json.loads(json.dumps(raw)))
    second = normalize_warehouse_catalog(json.loads(json.dumps(raw)))

    assert first["schema_version"] == WAREHOUSE_CATALOG_SCHEMA_VERSION
    assert first["fingerprint"] == second["fingerprint"]
