from __future__ import annotations

import json

import pytest

from dancelab.validation.djmix.ordering import (
    CorpusOrderingDataset,
    OrderingObservation,
    observation_fingerprint,
)
from dancelab.validation.djmix.ordering_models import (
    OrderingTrainingConfig,
    assess_ordering_model_readiness,
    evaluate_conditional_ordering_model,
    feature_catalog_from_payload,
    fit_conditional_ordering_model,
    split_ordering_observations,
    train_five_model_ordering_evaluation,
    write_five_model_ordering_report,
)


def _synthetic_fixture(
    *,
    mix_count: int = 12,
) -> tuple[CorpusOrderingDataset, object]:
    observations: list[OrderingObservation] = []
    tracks: dict[str, dict[str, list[float]]] = {}
    dj_by_mix: dict[str, str] = {}

    for mix_index in range(mix_count):
        mix_id = f"mix-{mix_index:02d}"
        dj_id = "dj-a" if mix_index % 2 == 0 else "dj-b"
        dj_by_mix[mix_id] = dj_id
        prefix = f"t-{mix_index:02d}"
        feature_by_suffix = {
            "open": [0.0, 0.0],
            "red": [1.0, 0.0],
            "blue": [0.0, 1.0],
            "end": [-1.0, -1.0],
        }
        for suffix, handcrafted in feature_by_suffix.items():
            tracks[f"{prefix}-{suffix}"] = {
                "handcrafted": handcrafted,
                "embedding": [handcrafted[0], handcrafted[1], 0.5],
            }

        opener = f"{prefix}-open"
        first = f"{prefix}-red" if dj_id == "dj-a" else f"{prefix}-blue"
        second = f"{prefix}-blue" if dj_id == "dj-a" else f"{prefix}-red"
        final = f"{prefix}-end"
        sequence = (opener, first, second, final)
        observations.extend(
            (
                OrderingObservation(
                    mix_id=mix_id,
                    run_id=f"{mix_id}:run-1",
                    position=1,
                    history_track_ids=(opener,),
                    candidate_track_ids=tuple(sorted(sequence[1:])),
                    selected_track_id=first,
                    dj_id=dj_id,
                ),
                OrderingObservation(
                    mix_id=mix_id,
                    run_id=f"{mix_id}:run-1",
                    position=2,
                    history_track_ids=sequence[:2],
                    candidate_track_ids=tuple(sorted(sequence[2:])),
                    selected_track_id=second,
                    dj_id=dj_id,
                ),
            )
        )

    dataset = CorpusOrderingDataset(
        observations=tuple(observations),
        audit={"fixture": True},
        fingerprint=observation_fingerprint(observations),
    )
    catalog = feature_catalog_from_payload(
        {
            "schema_version": "ordering-features-v1",
            "handcrafted_feature_names": ["descriptor-a", "descriptor-b"],
            "embedding_name": "synthetic-frozen-embedding",
            "tracks": tracks,
            "dj_by_mix": dj_by_mix,
            "provenance": {
                "source": "deterministic unit-test fixture",
                "generated_audio_features": False,
            },
        }
    )
    return dataset, catalog


def _fast_config() -> OrderingTrainingConfig:
    return OrderingTrainingConfig(
        l2=0.02,
        dj_l2=0.05,
        learning_rate=0.04,
        max_iterations=250,
        tolerance=1e-9,
        patience=15,
    )


def test_feature_catalog_is_strict_and_has_stable_fingerprint():
    _, left = _synthetic_fixture(mix_count=3)
    _, right = _synthetic_fixture(mix_count=3)

    assert left.fingerprint == right.fingerprint
    assert left.handcrafted_dimension == 2
    assert left.embedding_dimension == 3
    with pytest.raises(ValueError, match="schema"):
        feature_catalog_from_payload(
            {
                "schema_version": "wrong",
                "handcrafted_feature_names": ["x"],
                "embedding_name": "e",
                "tracks": {},
            }
        )


def test_readiness_blocks_missing_features_and_untrusted_identity():
    dataset, catalog = _synthetic_fixture(mix_count=3)
    first_track = next(iter(catalog.tracks))
    incomplete = feature_catalog_from_payload(
        {
            "schema_version": "ordering-features-v1",
            "handcrafted_feature_names": ["a", "b"],
            "embedding_name": "fixture",
            "tracks": {
                first_track: {
                    "handcrafted": [0.0, 0.0],
                    "embedding": [0.0, 0.0, 0.0],
                }
            },
            "dj_by_mix": {},
            "provenance": {},
        }
    )

    readiness = assess_ordering_model_readiness(dataset, incomplete)

    assert readiness.ready_for_five_models is False
    assert readiness.missing_feature_observations == len(dataset.observations)
    assert any("feature coverage" in blocker for blocker in readiness.blockers)


def test_grouped_split_never_leaks_one_mix_across_partitions():
    dataset, _ = _synthetic_fixture()

    first = split_ordering_observations(dataset.observations, seed="fixture")
    second = split_ordering_observations(dataset.observations, seed="fixture")
    mix_sets = {
        name: {item.mix_id for item in observations} for name, observations in first.items()
    }

    assert first == second
    assert mix_sets["train"].isdisjoint(mix_sets["validation"])
    assert mix_sets["train"].isdisjoint(mix_sets["test"])
    assert mix_sets["validation"].isdisjoint(mix_sets["test"])
    assert set.union(*mix_sets.values()) == set(dataset.mix_ids)


def test_dj_effect_is_a_feature_interaction_and_improves_conflicting_fixture():
    dataset, catalog = _synthetic_fixture()
    global_model = fit_conditional_ordering_model(
        dataset.observations,
        catalog,
        family="HE",
        config=_fast_config(),
    )
    dj_model = fit_conditional_ordering_model(
        dataset.observations,
        catalog,
        family="HE",
        include_dj_effects=True,
        config=_fast_config(),
    )

    global_metrics = evaluate_conditional_ordering_model(
        global_model,
        dataset.observations,
        catalog,
    )
    dj_metrics = evaluate_conditional_ordering_model(
        dj_model,
        dataset.observations,
        catalog,
    )

    assert dj_model.uses_dj_effects is True
    assert set(dj_model.dj_weights) == {"dj-a", "dj-b"}
    assert dj_metrics.total_nll < global_metrics.total_nll
    assert dj_metrics.top1_accuracy > global_metrics.top1_accuracy


def test_unseen_dj_uses_global_weights_instead_of_fabricated_identity():
    dataset, catalog = _synthetic_fixture()
    train = tuple(item for item in dataset.observations if item.dj_id != "not-used")
    model = fit_conditional_ordering_model(
        train,
        catalog,
        family="HE",
        include_dj_effects=True,
        config=_fast_config(),
    )
    original = dataset.observations[0]
    unseen = OrderingObservation(
        mix_id=original.mix_id,
        run_id=original.run_id,
        position=original.position,
        history_track_ids=original.history_track_ids,
        candidate_track_ids=original.candidate_track_ids,
        selected_track_id=original.selected_track_id,
        dj_id="new-dj",
    )

    metrics = evaluate_conditional_ordering_model(model, (unseen,), catalog)

    assert metrics.known_dj_count == 0
    assert metrics.unseen_dj_count == 1
    assert metrics.total_nll > 0.0


def test_five_models_share_exact_test_universe_and_emit_report(tmp_path):
    dataset, catalog = _synthetic_fixture()

    report = train_five_model_ordering_evaluation(
        dataset,
        catalog,
        config=_fast_config(),
    )
    output = write_five_model_ordering_report(
        report,
        tmp_path / "five-models.json",
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert report.readiness.ready_for_five_models is True
    assert set(report.test_metrics) == {"L0", "LH", "LE", "LHE", "LHEI"}
    assert len({metric.count for metric in report.test_metrics.values()}) == 1
    assert report.losses.evaluation_hash == report.evaluation_hash
    assert report.decomposition.evaluation_hash == report.evaluation_hash
    assert report.decomposition.total == pytest.approx(1.0)
    assert payload["scope"] == "ordering-given-observed-crate"
    assert payload["evaluation_hash"] == report.evaluation_hash
    assert "models" not in payload
    assert set(payload["model_summaries"]) == {"LH", "LE", "LHE", "LHEI"}
