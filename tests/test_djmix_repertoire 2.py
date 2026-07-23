from __future__ import annotations

import json
from pathlib import Path

from dancelab.validation.djmix.ordering import (
    CorpusOrderingDataset,
    OrderingObservation,
)
from dancelab.validation.djmix.ordering_models import feature_catalog_from_payload
from dancelab.validation.djmix.repertoire import (
    RepertoireBuildConfig,
    build_repertoire_candidate_report,
    build_revealed_repertoire_gate,
    inspect_repertoire_review,
    write_repertoire_candidate_report,
    write_repertoire_review_template,
    write_revealed_repertoire_dataset,
    write_revealed_repertoire_gate,
)


def _ordering_dataset(mix_ids: tuple[str, ...]) -> CorpusOrderingDataset:
    observations = tuple(
        OrderingObservation(
            mix_id=mix_id,
            run_id=f"{mix_id}:run-1",
            position=1,
            history_track_ids=(f"history-{index}",),
            candidate_track_ids=(f"candidate-{index}-a", f"candidate-{index}-b"),
            selected_track_id=f"candidate-{index}-a",
        )
        for index, mix_id in enumerate(mix_ids)
    )
    return CorpusOrderingDataset(
        observations=observations,
        audit={"source": {"dataset_sha256": "a" * 64}},
        fingerprint="d" * 64,
    )


def _mix(
    mix_id: str,
    performed_on: str,
    actor: str,
    track_ids: list[str | None],
) -> dict[str, object]:
    return {
        "id": mix_id,
        "title": f"{performed_on} - {actor} @ Fixture Club",
        "tags": [{"key": f"Category:{actor}"}],
        "tracklist": [
            {"id": track_id, "title": track_id or "unidentified"} for track_id in track_ids
        ],
    }


def _write_corpus(root: Path, mixes: list[dict[str, object]]) -> Path:
    dataset_dir = root / "dataset"
    dataset_dir.mkdir(parents=True)
    (root / "tracks").mkdir()
    (dataset_dir / "dataset.json").write_text(json.dumps(mixes), encoding="utf-8")
    return root


def _write_review(
    path: Path,
    *,
    candidate_fingerprint: str,
    entries: dict[str, dict[str, object]],
) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "revealed-repertoire-review-v1",
                "candidate_report_fingerprint": candidate_fingerprint,
                "mixes": entries,
                "provenance": {
                    "reviewer": "unit-test",
                    "method": "fixture evidence",
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _approved(dj_id: str, performed_on: str) -> dict[str, object]:
    return {
        "status": "approved",
        "dj_id": dj_id,
        "performed_on": performed_on,
        "performance_role": "solo",
        "evidence": ["unit-test fixture"],
    }


def _small_config() -> RepertoireBuildConfig:
    return RepertoireBuildConfig(
        min_prior_tracks=2,
        min_prior_mixes=1,
        min_selected_tracks=2,
        min_unlabelled_alternatives=1,
        min_identified_fraction=0.75,
        min_observations=2,
        min_djs=1,
    )


def test_candidate_report_is_explicitly_untrusted_and_classifies_review_risk(
    tmp_path: Path,
):
    mixes = [
        _mix("solo", "2020-01-01", "DJ A", ["a", "b", "c"]),
        _mix("b2b", "2020-02-01", "DJ A b2b DJ B", ["d", "e", "f"]),
        _mix("month", "2020-03", "DJ C", ["g", "h", "i"]),
    ]
    root = _write_corpus(tmp_path / "corpus", mixes)
    report = build_repertoire_candidate_report(
        root,
        _ordering_dataset(("solo", "b2b", "month")),
    )

    by_id = {candidate.mix_id: candidate for candidate in report.candidates}
    assert by_id["solo"].classification == "solo_like"
    assert by_id["solo"].suggested_disposition == "review_for_approval"
    assert by_id["b2b"].classification == "b2b"
    assert by_id["month"].date_precision == "month"
    assert report.as_dict()["trust_boundary"]["trusted"] is False
    assert report.as_dict()["trust_boundary"]["may_enter_dataset_directly"] is False


def test_review_requires_complete_adjudication_and_matching_candidate_fingerprint(
    tmp_path: Path,
):
    root = _write_corpus(
        tmp_path / "corpus",
        [
            _mix("m1", "2020-01-01", "DJ A", ["a", "b"]),
            _mix("m2", "2020-02-01", "DJ A", ["c", "d"]),
        ],
    )
    ordering = _ordering_dataset(("m1", "m2"))
    candidates = build_repertoire_candidate_report(root, ordering)
    review_path = _write_review(
        tmp_path / "review.json",
        candidate_fingerprint="0" * 64,
        entries={"m1": _approved("dj-a", "2020-01-01")},
    )

    inspection, approved = inspect_repertoire_review(review_path, candidates)

    assert inspection.ready is False
    assert inspection.candidate_fingerprint_matches is False
    assert inspection.missing_ids == ("m2",)
    assert set(approved) == {"m1"}


def test_revealed_repertoire_uses_only_strictly_earlier_sets(
    tmp_path: Path,
):
    mixes = [
        _mix("m1", "2020-01-01", "DJ A", ["a", "b", "c"]),
        _mix("m2", "2020-02-01", "DJ A", ["b", "d", "e"]),
        _mix("m3", "2020-03-01", "DJ A", ["d", "f", "g"]),
        _mix("m4", "2020-04-01", "DJ A", ["future", "h", "i"]),
    ]
    root = _write_corpus(tmp_path / "corpus", mixes)
    ordering = _ordering_dataset(("m1", "m2", "m3", "m4"))
    candidates = build_repertoire_candidate_report(root, ordering)
    review_path = _write_review(
        tmp_path / "review.json",
        candidate_fingerprint=candidates.fingerprint,
        entries={
            mix["id"]: _approved("dj-a", str(mix["title"]).split(" - ", 1)[0]) for mix in mixes
        },
    )

    _, report, proxy = build_revealed_repertoire_gate(
        root,
        ordering_dataset=ordering,
        review_path=review_path,
        config=_small_config(),
    )

    assert proxy is not None
    by_mix = {observation.mix_id: observation for observation in proxy.observations}
    assert by_mix["m2"].prior_mix_ids == ("m1",)
    assert by_mix["m2"].unlabelled_alternative_track_ids == ("a", "c")
    assert by_mix["m2"].previously_seen_selected_track_ids == ("b",)
    assert by_mix["m3"].prior_mix_ids == ("m1", "m2")
    assert "future" not in by_mix["m3"].prior_repertoire_track_ids
    assert not (
        set(by_mix["m3"].selected_track_ids) & set(by_mix["m3"].unlabelled_alternative_track_ids)
    )
    assert report.readiness["proxy_dataset_built"] is True
    assert report.readiness["feature_evidence_ready"] is False
    assert report.readiness["handcrafted_complete"] is False
    assert report.readiness["frozen_embeddings_complete"] is False
    assert report.ready_for_proxy_evaluation is False


def test_same_day_mix_never_becomes_history_for_its_peer(tmp_path: Path):
    mixes = [
        _mix("m1", "2020-01-01", "DJ A", ["a", "b", "c"]),
        _mix("m2", "2020-01-01", "DJ A", ["d", "e", "f"]),
        _mix("m3", "2020-02-01", "DJ A", ["a", "d", "g"]),
    ]
    root = _write_corpus(tmp_path / "corpus", mixes)
    ordering = _ordering_dataset(("m1", "m2", "m3"))
    candidates = build_repertoire_candidate_report(root, ordering)
    review_path = _write_review(
        tmp_path / "review.json",
        candidate_fingerprint=candidates.fingerprint,
        entries={
            "m1": _approved("dj-a", "2020-01-01"),
            "m2": _approved("dj-a", "2020-01-01"),
            "m3": _approved("dj-a", "2020-02-01"),
        },
    )
    config = RepertoireBuildConfig(
        min_prior_tracks=2,
        min_prior_mixes=1,
        min_selected_tracks=2,
        min_unlabelled_alternatives=1,
        min_identified_fraction=1.0,
        min_observations=1,
        min_djs=1,
    )

    _, _, proxy = build_revealed_repertoire_gate(
        root,
        ordering_dataset=ordering,
        review_path=review_path,
        config=config,
    )

    assert proxy is not None
    assert proxy.mix_ids == ("m3",)
    assert proxy.observations[0].prior_mix_ids == ("m1", "m2")


def test_quality_filters_are_deterministic_and_visible_in_audit(tmp_path: Path):
    mixes = [
        _mix("m1", "2020-01-01", "DJ A", ["a", "b", "c"]),
        _mix("m2", "2020-02-01", "DJ A", ["d", "d", "e"]),
        _mix("m3", "2020-03-01", "DJ A", ["a", None, None, "f"]),
        _mix("m4", "2020-04-01", "DJ A", ["g", "h", "i"]),
    ]
    root = _write_corpus(tmp_path / "corpus", mixes)
    ordering = _ordering_dataset(("m1", "m2", "m3", "m4"))
    candidates = build_repertoire_candidate_report(root, ordering)
    review_path = _write_review(
        tmp_path / "review.json",
        candidate_fingerprint=candidates.fingerprint,
        entries={
            mix["id"]: _approved("dj-a", str(mix["title"]).split(" - ", 1)[0]) for mix in mixes
        },
    )

    _, _, proxy = build_revealed_repertoire_gate(
        root,
        ordering_dataset=ordering,
        review_path=review_path,
        config=_small_config(),
    )

    assert proxy is not None
    assert proxy.audit["counts"]["excluded_duplicate_target_tracks"] == 1
    assert proxy.audit["counts"]["excluded_low_identified_fraction"] == 1


def test_gate_opens_only_with_complete_h_and_e_for_exact_proxy_universe(
    tmp_path: Path,
):
    mixes = [
        _mix("m1", "2020-01-01", "DJ A", ["a", "b", "c"]),
        _mix("m2", "2020-02-01", "DJ A", ["b", "d", "e"]),
        _mix("m3", "2020-03-01", "DJ A", ["d", "f", "g"]),
    ]
    root = _write_corpus(tmp_path / "corpus", mixes)
    ordering = _ordering_dataset(("m1", "m2", "m3"))
    candidates = build_repertoire_candidate_report(root, ordering)
    review_path = _write_review(
        tmp_path / "review.json",
        candidate_fingerprint=candidates.fingerprint,
        entries={
            "m1": _approved("dj-a", "2020-01-01"),
            "m2": _approved("dj-a", "2020-02-01"),
            "m3": _approved("dj-a", "2020-03-01"),
        },
    )
    _, blocked, proxy = build_revealed_repertoire_gate(
        root,
        ordering_dataset=ordering,
        review_path=review_path,
        config=_small_config(),
    )
    assert proxy is not None
    assert blocked.ready_for_proxy_evaluation is False

    features = feature_catalog_from_payload(
        {
            "schema_version": "ordering-features-v1",
            "handcrafted_feature_names": ["h"],
            "embedding_name": "fixture-e",
            "tracks": {
                track_id: {
                    "handcrafted": [float(index + 1)],
                    "embedding": [float(index + 1), 0.5],
                }
                for index, track_id in enumerate(proxy.track_ids)
            },
            "dj_by_mix": {},
            "provenance": {"source": "unit-test"},
        }
    )
    first_candidates, first, first_proxy = build_revealed_repertoire_gate(
        root,
        ordering_dataset=ordering,
        review_path=review_path,
        feature_catalog=features,
        config=_small_config(),
        expected_ordering_dataset_fingerprint=ordering.fingerprint,
    )
    _, second, second_proxy = build_revealed_repertoire_gate(
        root,
        ordering_dataset=ordering,
        review_path=review_path,
        feature_catalog=features,
        config=_small_config(),
        expected_ordering_dataset_fingerprint=ordering.fingerprint,
    )

    assert first.ready_for_proxy_evaluation
    assert first.blockers == ()
    assert first.handcrafted.ready
    assert first.embeddings.ready
    assert first.readiness["source_audio_complete"] is False
    assert first_proxy is not None and second_proxy is not None
    assert first_proxy.fingerprint == second_proxy.fingerprint
    assert first.fingerprint == second.fingerprint
    assert first_candidates.fingerprint == candidates.fingerprint


def test_repertoire_artifacts_write_complete_fingerprinted_json(tmp_path: Path):
    mixes = [
        _mix("m1", "2020-01-01", "DJ A", ["a", "b", "c"]),
        _mix("m2", "2020-02-01", "DJ A", ["b", "d", "e"]),
        _mix("m3", "2020-03-01", "DJ A", ["d", "f", "g"]),
    ]
    root = _write_corpus(tmp_path / "corpus", mixes)
    ordering = _ordering_dataset(("m1", "m2", "m3"))
    candidates = build_repertoire_candidate_report(root, ordering)
    review_path = _write_review(
        tmp_path / "review.json",
        candidate_fingerprint=candidates.fingerprint,
        entries={
            "m1": _approved("dj-a", "2020-01-01"),
            "m2": _approved("dj-a", "2020-02-01"),
            "m3": _approved("dj-a", "2020-03-01"),
        },
    )
    _, report, proxy = build_revealed_repertoire_gate(
        root,
        ordering_dataset=ordering,
        review_path=review_path,
        config=_small_config(),
    )
    assert proxy is not None

    candidate_path = write_repertoire_candidate_report(
        candidates,
        tmp_path / "out" / "candidates.json",
    )
    template_path = write_repertoire_review_template(
        candidates,
        tmp_path / "out" / "review.template.json",
    )
    gate_path = write_revealed_repertoire_gate(
        report,
        tmp_path / "out" / "gate.json",
    )
    dataset_path = write_revealed_repertoire_dataset(
        proxy,
        tmp_path / "out" / "dataset.json",
    )

    candidate_payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    template_payload = json.loads(template_path.read_text(encoding="utf-8"))
    gate_payload = json.loads(gate_path.read_text(encoding="utf-8"))
    dataset_payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    assert candidate_payload["fingerprint"] == candidates.fingerprint
    assert template_payload["candidate_report_fingerprint"] == candidates.fingerprint
    assert {item["status"] for item in template_payload["mixes"].values()} == {"pending"}
    assert gate_payload["fingerprint"] == report.fingerprint
    assert dataset_payload["fingerprint"] == proxy.fingerprint
    assert dataset_payload["audit"]["label_semantics"]["unlabelled_alternative_track_ids"].endswith(
        "not confirmed negatives"
    )
