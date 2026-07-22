from __future__ import annotations

import json

import pytest

from dancelab.core.models import (
    AnalysisResult,
    BeatGrid,
    FeatureFrame,
    Segment,
    SegmentType,
    Track,
)
from dancelab.validation.djmix.ordering_features import (
    HANDCRAFTED_FEATURE_NAMES,
    build_ordering_feature_catalog,
    handcrafted_features_from_analysis,
    load_frozen_embedding_catalog,
)


def _analysis(*, missing_required: bool = False) -> AnalysisResult:
    return AnalysisResult(
        engine_version="fixture",
        track=Track(
            track_id="engine-hash",
            duration_sec=240.0,
            bpm_estimate=130.0,
            key_estimate="8A",
            key_confidence=0.75,
        ),
        beatgrid=BeatGrid(
            bpm=130.0,
            beat_times_sec=[0.0, 0.46, 0.92],
            reliable=True,
        ),
        segments=[
            Segment(
                segment_id="intro",
                track_id="engine-hash",
                start_sec=0.0,
                end_sec=32.0,
                segment_type=SegmentType.intro,
            ),
            Segment(
                segment_id="groove",
                track_id="engine-hash",
                start_sec=32.0,
                end_sec=240.0,
                segment_type=SegmentType.groove,
            ),
        ],
        features=[
            FeatureFrame(
                track_id="engine-hash",
                timestamp_sec=0.0,
                rms=None if missing_required else 0.2,
                spectral_flux=100.0,
                low_freq_energy_ratio=0.4,
                onset_density=3.0,
                bass_energy=2000.0,
                pulse_clarity_proxy=0.5,
            ),
            FeatureFrame(
                track_id="engine-hash",
                timestamp_sec=1.0,
                rms=0.3,
                spectral_flux=140.0,
                low_freq_energy_ratio=0.5,
                onset_density=4.0,
                bass_energy=3000.0,
                pulse_clarity_proxy=None,
            ),
        ],
    )


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _embedding_payload(*, tracks=None):
    return {
        "schema_version": "ordering-embeddings-v1",
        "embedding_name": "frozen-fixture-v1",
        "model": {
            "name": "fixture encoder",
            "version": "1",
            "sha256": "a" * 64,
            "source": "unit-test fixture",
            "license": "test-only",
            "frozen": True,
        },
        "tracks": tracks or {"catalog-track": [0.1, 0.2, 0.3]},
        "provenance": {"fixture": True},
    }


def test_handcrafted_features_have_stable_schema_and_explicit_missingness():
    vector = handcrafted_features_from_analysis(_analysis())

    assert len(vector) == len(HANDCRAFTED_FEATURE_NAMES)
    assert vector[HANDCRAFTED_FEATURE_NAMES.index("key_missing")] == 0.0
    assert vector[HANDCRAFTED_FEATURE_NAMES.index("pulse_clarity_proxy_missing_fraction")] == 0.5
    assert vector[HANDCRAFTED_FEATURE_NAMES.index("vocal_density_proxy_missing_fraction")] == 1.0


def test_handcrafted_features_fail_closed_when_core_measurement_is_missing():
    with pytest.raises(ValueError, match="required descriptor rms"):
        handcrafted_features_from_analysis(_analysis(missing_required=True))


def test_embedding_catalog_requires_frozen_pinned_nonzero_model(tmp_path):
    path = tmp_path / "embeddings.json"
    payload = _embedding_payload()
    payload["model"]["frozen"] = False
    _write_json(path, payload)

    with pytest.raises(ValueError, match="model.frozen"):
        load_frozen_embedding_catalog(path)

    payload["model"]["frozen"] = True
    payload["tracks"] = {"catalog-track": [0.0, 0.0, 0.0]}
    _write_json(path, payload)
    with pytest.raises(ValueError, match="all-zero"):
        load_frozen_embedding_catalog(path)


def test_catalog_builder_joins_only_explicit_source_backed_ids(tmp_path):
    analysis_root = tmp_path / "analyses"
    analysis_root.mkdir()
    analysis_path = analysis_root / "opaque.json"
    analysis_path.write_text(_analysis().model_dump_json(), encoding="utf-8")

    index_path = tmp_path / "analysis-index.json"
    _write_json(
        index_path,
        {
            "schema_version": "ordering-analysis-index-v1",
            "tracks": {"catalog-track": "opaque.json"},
        },
    )
    embedding_path = tmp_path / "embeddings.json"
    _write_json(embedding_path, _embedding_payload())
    dj_path = tmp_path / "dj-map.json"
    _write_json(
        dj_path,
        {
            "schema_version": "ordering-dj-map-v1",
            "dj_by_mix": {"mix-1": "dj-1"},
            "provenance": {"source": "fixture metadata"},
        },
    )

    first = build_ordering_feature_catalog(
        analysis_root=analysis_root,
        analysis_index_path=index_path,
        embedding_catalog_path=embedding_path,
        dj_mapping_path=dj_path,
    )
    second = build_ordering_feature_catalog(
        analysis_root=analysis_root,
        analysis_index_path=index_path,
        embedding_catalog_path=embedding_path,
        dj_mapping_path=dj_path,
    )

    assert set(first.tracks) == {"catalog-track"}
    assert first.fingerprint == second.fingerprint
    assert first.embedding_dimension == 3
    assert first.handcrafted_feature_names == HANDCRAFTED_FEATURE_NAMES
    assert first.provenance["scope"] == "offline-validation-only"


def test_catalog_builder_rejects_index_path_traversal(tmp_path):
    analysis_root = tmp_path / "analyses"
    analysis_root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text(_analysis().model_dump_json(), encoding="utf-8")
    index_path = tmp_path / "analysis-index.json"
    _write_json(
        index_path,
        {
            "schema_version": "ordering-analysis-index-v1",
            "tracks": {"catalog-track": "../outside.json"},
        },
    )
    embedding_path = tmp_path / "embeddings.json"
    _write_json(embedding_path, _embedding_payload())
    dj_path = tmp_path / "dj-map.json"
    _write_json(
        dj_path,
        {
            "schema_version": "ordering-dj-map-v1",
            "dj_by_mix": {"mix-1": "dj-1"},
            "provenance": {"source": "fixture metadata"},
        },
    )

    with pytest.raises(ValueError, match="escapes"):
        build_ordering_feature_catalog(
            analysis_root=analysis_root,
            analysis_index_path=index_path,
            embedding_catalog_path=embedding_path,
            dj_mapping_path=dj_path,
        )
