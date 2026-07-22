from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from dancelab.validation.djmix.naina_catalog import (
    NAINA_CATALOG_SCHEMA_VERSION,
    NAINA_RAW_SCHEMA_VERSION,
    NainaCatalogError,
    normalize_naina_catalog,
    write_naina_catalog_sqlite,
)


def _artist(artist_id: str, name: str) -> dict[str, str]:
    return {
        "apple_artist_id": artist_id,
        "name": name,
        "url": f"https://music.apple.com/pl/artist/{name}/{artist_id}",
    }


def _track(
    song_id: str,
    position: int,
    title: str,
    artists: list[dict[str, str]],
) -> dict[str, object]:
    return {
        "apple_song_id": song_id,
        "artists": artists,
        "duration_iso": "PT2M3S",
        "duration_text": "2:03",
        "jsonld_song_id": song_id,
        "jsonld_title": title,
        "position": position,
        "title": title,
        "url": f"https://music.apple.com/pl/song/test/{song_id}",
    }


def _album(
    volume: int,
    album_id: str,
    billing: str,
    creators: list[dict[str, str]],
    tracks: list[dict[str, object]],
) -> dict[str, object]:
    title = f"NAINA Presents: {billing}, Vol. {volume} (DJ Mix)"
    return {
        "href": f"https://music.apple.com/pl/album/test/{album_id}",
        "txt": title,
        "volume": volume,
        "apple_album_id": album_id,
        "fetched_at": "2026-07-22T12:00:00Z",
        "album_name": title,
        "album_url": f"https://music.apple.com/pl/album/test/{album_id}",
        "creators": creators,
        "date_published": f"2026-01-{volume:02d}",
        "description": "fixture",
        "dom_track_count": len(tracks),
        "genres": ["Dance"],
        "jsonld_track_count": len(tracks),
        "tracks": tracks,
    }


def _raw(albums: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": NAINA_RAW_SCHEMA_VERSION,
        "storefront": "pl",
        "source_name": "Apple Music public catalog",
        "series_urls": ["https://music.apple.com/pl/curator/test"],
        "fetched_at": "2026-07-22T12:00:00Z",
        "source_file_sha256": "a" * 64,
        "albums": albums,
    }


def test_normalization_preserves_three_identity_layers_and_adjacency():
    dj_a = _artist("10", "DJ A")
    dj_b = _artist("11", "DJ B")
    source_artist = _artist("20", "Source Artist")
    raw = _raw(
        [
            _album(
                1,
                "100",
                "DJ A b2b DJ B",
                [dj_a, dj_b],
                [
                    _track("200", 1, "First Tune (Mixed)", [source_artist]),
                    _track("201", 2, "ID1 (from NAINA) [Mixed]", []),
                ],
            )
        ]
    )

    catalog = normalize_naina_catalog(raw)

    assert catalog["schema_version"] == NAINA_CATALOG_SCHEMA_VERSION
    assert catalog["mixes"][0]["mix_id"] == "apple_music:album:100"
    assert catalog["mixes"][0]["performance_role_suggestion"] == "b2b"
    assert catalog["tracks"][0]["identity_scope"] == "apple_music_mixed_album_segment"
    assert catalog["tracks"][0]["underlying_recording_id"] is None
    assert catalog["analysis"]["observed_adjacency_count"] == 1
    assert catalog["observed_adjacencies"][0]["evidence_scope"] == ("published_tracklist_adjacency")
    issue_codes = {item["issue_code"] for item in catalog["review_items"]}
    assert issue_codes == {"artist_credit_fallback", "unidentified_track_placeholder"}


def test_multiple_creators_without_b2b_stays_in_manual_review():
    dj_a = _artist("10", "DJ A")
    dj_b = _artist("11", "DJ B")
    catalog = normalize_naina_catalog(
        _raw(
            [
                _album(
                    1,
                    "100",
                    "Collective Name",
                    [dj_a, dj_b],
                    [_track("200", 1, "Tune (Mixed)", [dj_a])],
                )
            ]
        )
    )

    mix = catalog["mixes"][0]
    assert mix["performance_role_suggestion"] == "multi_artist_billing"
    assert mix["manual_role_review_required"] is True
    assert any(
        item["issue_code"] == "performance_role_ambiguous" for item in catalog["review_items"]
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda album: album.update(dom_track_count=2), "track counts disagree"),
        (
            lambda album: album["tracks"][0].update(jsonld_song_id="different"),
            "song IDs disagree",
        ),
        (lambda album: album["tracks"][0].update(position=2), "positions are not contiguous"),
    ],
)
def test_source_disagreements_fail_closed(mutation, message: str):
    dj = _artist("10", "DJ A")
    album = _album(
        1,
        "100",
        "DJ A",
        [dj],
        [_track("200", 1, "Tune (Mixed)", [dj])],
    )
    mutation(album)

    with pytest.raises(NainaCatalogError, match=message):
        normalize_naina_catalog(_raw([album]))


def test_sqlite_writer_enforces_relations_and_counts(tmp_path: Path):
    dj = _artist("10", "DJ A")
    catalog = normalize_naina_catalog(
        _raw(
            [
                _album(
                    1,
                    "100",
                    "DJ A",
                    [dj],
                    [
                        _track("200", 1, "Tune A (Mixed)", [dj]),
                        _track("201", 2, "Tune B (Mixed)", [dj]),
                    ],
                )
            ]
        )
    )
    database = write_naina_catalog_sqlite(catalog, tmp_path / "catalog.sqlite3")

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT COUNT(*) FROM mixes").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM mix_tracks").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM observed_adjacencies").fetchone()[0] == 1
        fingerprint = connection.execute(
            "SELECT value FROM metadata WHERE key = 'catalog_fingerprint'"
        ).fetchone()[0]
        assert fingerprint == catalog["fingerprint"]


def test_catalog_fingerprint_is_deterministic():
    dj = _artist("10", "DJ A")
    raw = _raw(
        [
            _album(
                1,
                "100",
                "DJ A",
                [dj],
                [_track("200", 1, "Tune (Mixed)", [dj])],
            )
        ]
    )

    first = normalize_naina_catalog(json.loads(json.dumps(raw)))
    second = normalize_naina_catalog(json.loads(json.dumps(raw)))

    assert first["fingerprint"] == second["fingerprint"]
