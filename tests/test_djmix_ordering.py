from __future__ import annotations

import json
from pathlib import Path

import pytest

from dancelab.validation.djmix.ordering import (
    OrderingBuildConfig,
    OrderingObservation,
    build_corpus_ordering_dataset,
    observation_fingerprint,
    write_ordering_dataset_snapshot,
)


def _result(
    track_id: str,
    *,
    source_id: str | None = None,
    matched: bool = True,
    match_rate: float = 0.8,
    reliable: bool = True,
) -> dict[str, object]:
    return {
        "youtube_id": track_id,
        "track_id": source_id or f"sha-{track_id}",
        "alignment": {
            "matched": matched,
            "match_rate": match_rate,
            "normalized_cost": 0.2,
        },
        "track_beatgrid": {
            "reliable": reliable,
            "bpm": 130.0,
            "quality_score": 0.9,
        },
    }


def _write_corpus(
    root: Path,
    *,
    mixes: list[dict[str, object]],
    reports: dict[str, list[dict[str, object]]],
    production_layout: bool = False,
) -> Path:
    dataset_dir = root / "dataset"
    alignments_dir = root / "alignments"
    dataset_dir.mkdir(parents=True)
    alignments_dir.mkdir(parents=True)
    dataset_path = (
        root / "djmix-dataset.json" if production_layout else dataset_dir / "dataset.json"
    )
    dataset_path.write_text(
        json.dumps(mixes),
        encoding="utf-8",
    )
    for mix_id, results in reports.items():
        (alignments_dir / f"{mix_id}.json").write_text(
            json.dumps(
                {
                    "mix_id": mix_id,
                    "schema_version": "1.1.0",
                    "results": results,
                }
            ),
            encoding="utf-8",
        )
    return root


def _mix(mix_id: str, track_ids: list[str]) -> dict[str, object]:
    return {
        "id": mix_id,
        "title": f"Do not parse DJ identity from {mix_id}",
        "genres": ["House", "house"],
        "tags": [
            {"key": "Category:Example DJ"},
            {"key": "Category:Example Venue"},
        ],
        "tracklist": [{"id": track_id, "title": track_id} for track_id in track_ids],
    }


def test_builder_creates_canonical_remaining_crate_choices(tmp_path: Path):
    root = _write_corpus(
        tmp_path / "corpus",
        mixes=[_mix("mix-a", ["a", "b", "c", "d"])],
        reports={
            "mix-a": [_result(track_id) for track_id in ("a", "b", "c", "d")],
        },
    )

    dataset = build_corpus_ordering_dataset(
        root,
        dj_by_mix={"mix-a": "trusted-dj"},
    )

    assert len(dataset.observations) == 2
    first, second = dataset.observations
    assert first.history_track_ids == ("a",)
    assert first.candidate_track_ids == ("b", "c", "d")
    assert first.selected_track_id == "b"
    assert second.history_track_ids == ("a", "b")
    assert second.candidate_track_ids == ("c", "d")
    assert second.selected_track_id == "c"
    assert first.genre_labels == ("house",)
    assert first.dj_id == "trusted-dj"
    assert dataset.audit["scope"] == "P(next track | observed crate, performed history)"
    assert dataset.audit["identity"]["title_parsing_used"] is False


def test_general_tags_are_not_silently_reclassified_as_genres(tmp_path: Path):
    mix = _mix("mix-a", ["a", "b", "c"])
    mix.pop("genres")
    mix["tags"] = [
        {"key": "Category:Example DJ"},
        {"key": "Category:Essential Mix"},
        {"key": "Category:House"},
    ]
    root = _write_corpus(
        tmp_path / "corpus",
        mixes=[mix],
        reports={
            "mix-a": [_result(track_id) for track_id in ("a", "b", "c")],
        },
    )

    dataset = build_corpus_ordering_dataset(root)

    assert dataset.observations[0].genre_labels == ()
    assert dataset.audit["counts"]["mix_without_explicit_genres"] == 1


def test_missing_alignment_splits_run_instead_of_fabricating_adjacency(
    tmp_path: Path,
):
    root = _write_corpus(
        tmp_path / "corpus",
        mixes=[_mix("mix-a", ["a", "missing", "b", "c", "d"])],
        reports={
            "mix-a": [_result(track_id) for track_id in ("a", "b", "c", "d")],
        },
    )

    dataset = build_corpus_ordering_dataset(root)

    assert len(dataset.observations) == 1
    observation = dataset.observations[0]
    assert observation.history_track_ids == ("b",)
    assert observation.selected_track_id == "c"
    assert "a" not in observation.history_track_ids
    assert dataset.audit["counts"]["missing_alignment_result"] == 1
    assert dataset.audit["counts"]["short_runs"] == 1


@pytest.mark.parametrize(
    ("results", "reason"),
    [
        (
            [_result("a"), _result("b", matched=False), _result("c"), _result("d")],
            "quality_not_matched",
        ),
        (
            [_result("a"), _result("b", match_rate=0.39), _result("c"), _result("d")],
            "quality_low_match_rate",
        ),
        (
            [_result("a"), _result("b", reliable=False), _result("c"), _result("d")],
            "quality_unreliable_beatgrid",
        ),
    ],
)
def test_quality_failures_break_runs(
    tmp_path: Path,
    results: list[dict[str, object]],
    reason: str,
):
    root = _write_corpus(
        tmp_path / reason,
        mixes=[_mix("mix-a", ["a", "b", "c", "d"])],
        reports={"mix-a": results},
    )

    dataset = build_corpus_ordering_dataset(root)

    assert dataset.observations == ()
    assert dataset.audit["counts"][reason] == 1


def test_duplicate_audio_breaks_ambiguous_candidate_run(tmp_path: Path):
    root = _write_corpus(
        tmp_path / "corpus",
        mixes=[_mix("mix-a", ["a", "b", "c", "d", "e"])],
        reports={
            "mix-a": [
                _result("a"),
                _result("b"),
                _result("c", source_id="sha-b"),
                _result("d"),
                _result("e"),
            ],
        },
    )

    dataset = build_corpus_ordering_dataset(root)

    assert len(dataset.observations) == 1
    assert dataset.observations[0].history_track_ids == ("c",)
    assert dataset.observations[0].selected_track_id == "d"
    assert dataset.audit["counts"]["duplicate_track_breaks"] == 1


def test_fingerprint_is_stable_and_changes_with_choice_set(tmp_path: Path):
    root = _write_corpus(
        tmp_path / "corpus",
        mixes=[_mix("mix-a", ["a", "b", "c", "d"])],
        reports={
            "mix-a": [_result(track_id) for track_id in ("a", "b", "c", "d")],
        },
    )

    left = build_corpus_ordering_dataset(root)
    right = build_corpus_ordering_dataset(root)

    assert left.fingerprint == right.fingerprint
    assert observation_fingerprint(left.observations) == observation_fingerprint(right.observations)
    changed = OrderingObservation(
        mix_id="mix-a",
        run_id="mix-a:run-1",
        position=1,
        history_track_ids=("a",),
        candidate_track_ids=("b", "c"),
        selected_track_id="b",
    )
    assert observation_fingerprint((changed,)) != observation_fingerprint(left.observations)


def test_snapshot_round_trip_contains_provenance(tmp_path: Path):
    root = _write_corpus(
        tmp_path / "corpus",
        mixes=[_mix("mix-a", ["a", "b", "c"])],
        reports={
            "mix-a": [_result(track_id) for track_id in ("a", "b", "c")],
        },
    )
    dataset = build_corpus_ordering_dataset(root)

    output = write_ordering_dataset_snapshot(dataset, tmp_path / "out" / "ordering.json")
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "corpus-ordering-v1"
    assert payload["fingerprint"] == dataset.fingerprint
    assert payload["observation_count"] == 1
    assert payload["audit"]["explicitly_not_modeled"].endswith("complete library)")


def test_builder_supports_the_production_corpus_layout(tmp_path: Path):
    root = _write_corpus(
        tmp_path / "corpus",
        mixes=[_mix("mix-a", ["a", "b", "c"])],
        reports={
            "mix-a": [_result(track_id) for track_id in ("a", "b", "c")],
        },
        production_layout=True,
    )

    dataset = build_corpus_ordering_dataset(root)

    assert len(dataset.observations) == 1
    assert dataset.audit["source"]["dataset_path"].endswith("djmix-dataset.json")


def test_conflicting_dataset_layouts_fail_closed(tmp_path: Path):
    root = _write_corpus(
        tmp_path / "corpus",
        mixes=[_mix("mix-a", ["a", "b", "c"])],
        reports={
            "mix-a": [_result(track_id) for track_id in ("a", "b", "c")],
        },
        production_layout=True,
    )
    nested = root / "dataset" / "dataset.json"
    nested.write_text(json.dumps([_mix("different", ["x", "y", "z"])]), encoding="utf-8")

    with pytest.raises(ValueError, match="ambiguous corpus metadata"):
        build_corpus_ordering_dataset(root)


def test_build_config_rejects_weak_or_non_informative_universes():
    with pytest.raises(ValueError, match="between 0 and 1"):
        OrderingBuildConfig(min_match_rate=1.1)
    with pytest.raises(ValueError, match="at least 3"):
        OrderingBuildConfig(min_run_tracks=2)
