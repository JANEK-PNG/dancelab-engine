from __future__ import annotations

from pathlib import Path

from dancelab.contracts.node_host import get_node_host_registry
from dancelab.core.models import (
    AnalysisResult,
    ContextProfile,
    ModelStatus,
    NextTrackCandidate,
    NextTrackRecommendation,
    RecommendationPolicy,
    ScoredOutput,
    Track,
)
from dancelab.host.runtime import DesktopHostRuntime, RuntimeConnection, RuntimeNodeState
from dancelab.storage.repositories import FileAnalysisRepository


class _DummyConfig:
    weights_file = "unused-weights.yaml"


class _DummyEngine:
    version = "test-host-runtime"


class _DummyPaths:
    data_dir = "data"
    processed_dir = "data/processed"


class _BridgeConfig:
    engine = _DummyEngine()
    paths = _DummyPaths()
    analysis = type("_DummyAnalysisSection", (), {"transition_top_n": 3})()
    weights_file = "configs/descriptor_weights.yaml"


def _analysis_from_path(path: str, _config: object) -> AnalysisResult:
    stem = Path(path).stem
    track_id = stem.lower().replace(" ", "_")
    return AnalysisResult(
        engine_version="test-host-runtime",
        track=Track(
            track_id=track_id,
            title=stem,
            source_path=path,
        ),
    )


def _edge_decision_stub(**kwargs) -> dict[str, object]:
    analysis_a = kwargs["analysis_a"]
    analysis_b = kwargs["analysis_b"]
    return {
        "track_id_a": analysis_a.track.track_id,
        "track_id_b": analysis_b.track.track_id,
        "decision_class": "strong_candidate",
        "core_dj_compatibility_score": {
            "value": 0.83,
            "status": "candidate",
            "confidence": 0.91,
            "explanation": "Stubbed desktop-host decision payload.",
        },
        "standard_blend_allowed": True,
        "recommended_transition_strategy": "standard_blend",
        "blend_profile_auto": "plain_blend",
        "tempo_gate_status": "pass",
        "harmonic_gate_status": "pass",
        "tempo_window_feasibility": "high",
        "risks": ["minor bass overlap"],
        "warnings": ["review phrase length"],
        "reasoning": ["Graph runtime executed through desktop host stubs."],
    }


def _recommend_next_stub(**kwargs) -> NextTrackRecommendation:
    current = kwargs["current"]
    candidates = kwargs["candidates"]
    context = kwargs.get("context")
    recent_history = kwargs.get("recent_history") or []
    ranking = [
        NextTrackCandidate(
            track_id=candidate.track.track_id,
            rank=index,
            score=ScoredOutput(
                value=0.92 - (index - 1) * 0.11,
                status=ModelStatus.candidate,
                confidence=0.84,
                explanation="Stubbed desktop-host recommend-next payload.",
            ),
            recommendation_policy=(
                RecommendationPolicy.allow if index == 1 else RecommendationPolicy.review_only
            ),
            policy_reasons=["Graph runtime executed through desktop host stubs."],
        )
        for index, candidate in enumerate(candidates, start=1)
    ]
    suppressed_track_ids = [
        analysis.track.track_id for analysis in recent_history if analysis.track.track_id not in {candidate.track_id for candidate in ranking}
    ]
    return NextTrackRecommendation(
        current_track_id=current.track.track_id,
        context_id=context.context_id if context is not None else None,
        arc_mode=str(kwargs.get("arc_mode") or "build"),
        recent_history_track_ids=[analysis.track.track_id for analysis in recent_history],
        ranking=ranking,
        suppressed_track_ids=suppressed_track_ids,
        recommendation_policy=RecommendationPolicy.review_only,
        warnings=["stub recommend-next warning"],
    )


def test_desktop_host_runtime_executes_first_flow_without_web_api():
    runtime = DesktopHostRuntime(
        get_node_host_registry(),
        analyze_track_fn=_analysis_from_path,
        edge_decision_fn=_edge_decision_stub,
        config_loader=lambda _path: _DummyConfig(),
        weights_loader=lambda _path: {"weights": "stub"},
    )

    upload_id = "desktop_upload_tracks_1"
    analyze_id = "desktop_analyze_tracks_2"
    select_pair_id = "desktop_select_pair_3"
    edge_id = "desktop_edge_decision_4"
    telemetry_id = "desktop_telemetry_screen_5"

    runtime.ensure_node_config(upload_id)["paths_text"] = "\n".join(
        [
            "/tmp/Track Alpha.mp3",
            "/tmp/Track Beta.mp3",
        ]
    )

    result = runtime.run(
        [
            RuntimeNodeState(instance_id=upload_id, node_id="upload_tracks"),
            RuntimeNodeState(instance_id=analyze_id, node_id="analyze_tracks"),
            RuntimeNodeState(instance_id=select_pair_id, node_id="select_pair"),
            RuntimeNodeState(instance_id=edge_id, node_id="edge_decision"),
            RuntimeNodeState(instance_id=telemetry_id, node_id="telemetry_screen"),
        ],
        [
            RuntimeConnection(
                from_instance_id=upload_id,
                from_port_key="tracks",
                to_instance_id=analyze_id,
                to_port_key="tracks",
            ),
            RuntimeConnection(
                from_instance_id=analyze_id,
                from_port_key="analysis",
                to_instance_id=select_pair_id,
                to_port_key="source",
            ),
            RuntimeConnection(
                from_instance_id=select_pair_id,
                from_port_key="pair",
                to_instance_id=edge_id,
                to_port_key="pair",
            ),
            RuntimeConnection(
                from_instance_id=edge_id,
                from_port_key="decision",
                to_instance_id=telemetry_id,
                to_port_key="source",
            ),
        ],
        telemetry_id,
    )

    assert result.node_id == "telemetry_screen"
    assert runtime.outputs[upload_id].ports["tracks"] == [
        "/tmp/Track Alpha.mp3",
        "/tmp/Track Beta.mp3",
    ]
    assert runtime.outputs[analyze_id].ports["track_ids"] == [
        "track_alpha",
        "track_beta",
    ]
    assert runtime.outputs[select_pair_id].ports["pair"] == {
        "track_id_a": "track_alpha",
        "track_id_b": "track_beta",
    }
    assert result.ports["snapshot"]["pair_label"] == "track_alpha -> track_beta"
    assert result.ports["snapshot"]["strategy"] == "standard_blend"
    assert result.ports["snapshot"]["score_text"] == "0.830"
    assert runtime.node_status[telemetry_id] == "done"
    assert runtime.session_message == "flow complete · telemetry_screen"


def test_desktop_host_runtime_select_track_returns_requested_analysis():
    runtime = DesktopHostRuntime(
        get_node_host_registry(),
        analyze_track_fn=_analysis_from_path,
        edge_decision_fn=_edge_decision_stub,
        config_loader=lambda _path: _DummyConfig(),
        weights_loader=lambda _path: {"weights": "stub"},
    )

    upload_id = "desktop_upload_tracks_1"
    analyze_id = "desktop_analyze_tracks_2"
    select_track_id = "desktop_select_track_3"

    runtime.ensure_node_config(upload_id)["paths_text"] = "\n".join(
        [
            "/tmp/Track Alpha.mp3",
            "/tmp/Track Beta.mp3",
        ]
    )
    runtime.ensure_node_config(select_track_id)["track_id"] = "track_beta"

    result = runtime.run(
        [
            RuntimeNodeState(instance_id=upload_id, node_id="upload_tracks"),
            RuntimeNodeState(instance_id=analyze_id, node_id="analyze_tracks"),
            RuntimeNodeState(instance_id=select_track_id, node_id="select_track"),
        ],
        [
            RuntimeConnection(
                from_instance_id=upload_id,
                from_port_key="tracks",
                to_instance_id=analyze_id,
                to_port_key="tracks",
            ),
            RuntimeConnection(
                from_instance_id=analyze_id,
                from_port_key="analysis",
                to_instance_id=select_track_id,
                to_port_key="source",
            ),
        ],
        select_track_id,
    )

    assert result.node_id == "select_track"
    assert result.ports["track_id"] == "track_beta"
    assert result.ports["track"].track.title == "Track Beta"


def test_desktop_host_runtime_select_context_returns_profile_payload():
    runtime = DesktopHostRuntime(
        get_node_host_registry(),
        analyze_track_fn=_analysis_from_path,
        edge_decision_fn=_edge_decision_stub,
        config_loader=lambda _path: _DummyConfig(),
        weights_loader=lambda _path: {"weights": "stub"},
    )
    runtime._context_profiles_cache = {
        "club_peak": {
            "venue_type": "club",
            "set_role": "peak",
            "crowd_energy": "high",
            "time_of_night": "01:00-03:00",
        },
        "festival_daytime": {
            "venue_type": "festival",
            "set_role": "builder",
            "crowd_energy": "medium",
            "time_of_night": "14:00-18:00",
        },
    }

    select_context_id = "desktop_select_context_1"
    runtime.ensure_node_config(select_context_id)["context_id"] = "festival_daytime"

    result = runtime.run(
        [
            RuntimeNodeState(instance_id=select_context_id, node_id="select_context"),
        ],
        [],
        select_context_id,
    )

    assert result.node_id == "select_context"
    assert result.ports["context"]["context_id"] == "festival_daytime"
    assert result.ports["context"]["venue_type"] == "festival"


def test_desktop_host_runtime_load_corpus_reads_repository_and_manifest(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    annotations_dir = tmp_path / "annotations"
    annotations_dir.mkdir()

    repo = FileAnalysisRepository(processed_dir)
    repo.save(_analysis_from_path("/tmp/Track Alpha.mp3", object()))
    repo.save(_analysis_from_path("/tmp/Track Beta.mp3", object()))

    runtime = DesktopHostRuntime(
        get_node_host_registry(),
        config_loader=lambda _path: _BridgeConfig(),
    )

    load_corpus_id = "desktop_load_corpus_1"
    config = runtime.ensure_node_config(load_corpus_id)
    config["processed_dir"] = str(processed_dir)
    config["annotations_dir"] = str(annotations_dir)
    config["load_mode"] = "analysis"

    result = runtime.run(
        [
            RuntimeNodeState(instance_id=load_corpus_id, node_id="load_corpus"),
        ],
        [],
        load_corpus_id,
    )

    assert result.node_id == "load_corpus"
    assert result.ports["track_ids"] == ["track_alpha", "track_beta"]
    assert len(result.ports["analysis"]) == 2
    assert result.ports["manifest"]["n_analyzed_tracks"] == 2
    assert result.ports["manifest"]["validation"]["valid"] is True


def test_desktop_host_runtime_build_set_from_corpus_track_ids(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    annotations_dir = tmp_path / "annotations"
    annotations_dir.mkdir()

    repo = FileAnalysisRepository(processed_dir)
    repo.save(_analysis_from_path("/tmp/Track Alpha.mp3", object()))
    repo.save(_analysis_from_path("/tmp/Track Beta.mp3", object()))

    runtime = DesktopHostRuntime(
        get_node_host_registry(),
        config_loader=lambda _path: _BridgeConfig(),
    )

    load_corpus_id = "desktop_load_corpus_1"
    build_set_id = "desktop_build_set_2"
    load_config = runtime.ensure_node_config(load_corpus_id)
    load_config["processed_dir"] = str(processed_dir)
    load_config["annotations_dir"] = str(annotations_dir)
    load_config["load_mode"] = "track_ids"
    build_config = runtime.ensure_node_config(build_set_id)
    build_config["arc"] = "build"
    build_config["start_track_id"] = "track_alpha"

    result = runtime.run(
        [
            RuntimeNodeState(instance_id=load_corpus_id, node_id="load_corpus"),
            RuntimeNodeState(instance_id=build_set_id, node_id="build_set"),
        ],
        [
            RuntimeConnection(
                from_instance_id=load_corpus_id,
                from_port_key="track_ids",
                to_instance_id=build_set_id,
                to_port_key="analysis",
            ),
        ],
        build_set_id,
    )

    assert result.node_id == "build_set"
    plan = result.ports["set_plan"]
    assert plan.arc == "build"
    assert plan.track_order[0] == "track_alpha"
    assert set(plan.track_order) == {"track_alpha", "track_beta"}


def test_desktop_host_runtime_exports_rekordbox_xml_from_set_plan(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    annotations_dir = tmp_path / "annotations"
    annotations_dir.mkdir()
    export_path = tmp_path / "exports" / "set.xml"

    repo = FileAnalysisRepository(processed_dir)
    repo.save(_analysis_from_path("/tmp/Track Alpha.mp3", object()))
    repo.save(_analysis_from_path("/tmp/Track Beta.mp3", object()))

    runtime = DesktopHostRuntime(
        get_node_host_registry(),
        config_loader=lambda _path: _BridgeConfig(),
    )

    load_corpus_id = "desktop_load_corpus_1"
    build_set_id = "desktop_build_set_2"
    export_id = "desktop_export_rekordbox_3"

    load_config = runtime.ensure_node_config(load_corpus_id)
    load_config["processed_dir"] = str(processed_dir)
    load_config["annotations_dir"] = str(annotations_dir)
    load_config["load_mode"] = "track_ids"

    runtime.ensure_node_config(build_set_id)["start_track_id"] = "track_alpha"
    export_config = runtime.ensure_node_config(export_id)
    export_config["output_path"] = str(export_path)
    export_config["playlist_name"] = "Host Test Set"

    result = runtime.run(
        [
            RuntimeNodeState(instance_id=load_corpus_id, node_id="load_corpus"),
            RuntimeNodeState(instance_id=build_set_id, node_id="build_set"),
            RuntimeNodeState(instance_id=export_id, node_id="export_rekordbox"),
        ],
        [
            RuntimeConnection(
                from_instance_id=load_corpus_id,
                from_port_key="track_ids",
                to_instance_id=build_set_id,
                to_port_key="analysis",
            ),
            RuntimeConnection(
                from_instance_id=load_corpus_id,
                from_port_key="track_ids",
                to_instance_id=export_id,
                to_port_key="analysis",
            ),
            RuntimeConnection(
                from_instance_id=build_set_id,
                from_port_key="set_plan",
                to_instance_id=export_id,
                to_port_key="set_plan",
            ),
        ],
        export_id,
    )

    assert result.node_id == "export_rekordbox"
    assert result.ports["artifact_path"] == str(export_path)
    assert export_path.exists()
    xml = export_path.read_text(encoding="utf-8")
    assert "Host Test Set" in xml
    assert "DJ_PLAYLISTS" in xml


def test_desktop_host_runtime_recommend_next_from_corpus_and_context(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    annotations_dir = tmp_path / "annotations"
    annotations_dir.mkdir()

    repo = FileAnalysisRepository(processed_dir)
    repo.save(_analysis_from_path("/tmp/Track Alpha.mp3", object()))
    repo.save(_analysis_from_path("/tmp/Track Beta.mp3", object()))
    repo.save(_analysis_from_path("/tmp/Track Gamma.mp3", object()))

    runtime = DesktopHostRuntime(
        get_node_host_registry(),
        config_loader=lambda _path: _BridgeConfig(),
        recommend_next_fn=_recommend_next_stub,
    )
    runtime._context_profiles_cache = {
        "festival_daytime": ContextProfile(
            context_id="festival_daytime",
            venue_type="festival",
            set_role="builder",
            crowd_energy="medium",
            time_of_night="14:00-18:00",
        ).model_dump(mode="json")
    }

    load_corpus_id = "desktop_load_corpus_1"
    select_track_id = "desktop_select_track_2"
    select_context_id = "desktop_select_context_3"
    recommend_next_id = "desktop_recommend_next_4"

    load_config = runtime.ensure_node_config(load_corpus_id)
    load_config["processed_dir"] = str(processed_dir)
    load_config["annotations_dir"] = str(annotations_dir)
    load_config["load_mode"] = "track_ids"

    runtime.ensure_node_config(select_track_id)["track_id"] = "track_alpha"
    recommend_config = runtime.ensure_node_config(recommend_next_id)
    recommend_config["arc_mode"] = "peak"
    recommend_config["recent_history_text"] = "track_gamma"

    result = runtime.run(
        [
            RuntimeNodeState(instance_id=load_corpus_id, node_id="load_corpus"),
            RuntimeNodeState(instance_id=select_track_id, node_id="select_track"),
            RuntimeNodeState(instance_id=select_context_id, node_id="select_context"),
            RuntimeNodeState(instance_id=recommend_next_id, node_id="recommend_next"),
        ],
        [
            RuntimeConnection(
                from_instance_id=load_corpus_id,
                from_port_key="track_ids",
                to_instance_id=select_track_id,
                to_port_key="source",
            ),
            RuntimeConnection(
                from_instance_id=select_track_id,
                from_port_key="track",
                to_instance_id=recommend_next_id,
                to_port_key="current",
            ),
            RuntimeConnection(
                from_instance_id=load_corpus_id,
                from_port_key="track_ids",
                to_instance_id=recommend_next_id,
                to_port_key="candidates",
            ),
            RuntimeConnection(
                from_instance_id=select_context_id,
                from_port_key="context",
                to_instance_id=recommend_next_id,
                to_port_key="context",
            ),
        ],
        recommend_next_id,
    )

    assert result.node_id == "recommend_next"
    recommendation = result.ports["recommendation"]
    assert recommendation.current_track_id == "track_alpha"
    assert recommendation.context_id == "festival_daytime"
    assert recommendation.arc_mode == "peak"
    assert recommendation.recent_history_track_ids == ["track_gamma"]
    assert [candidate.track_id for candidate in recommendation.ranking] == [
        "track_beta",
        "track_gamma",
    ]
    assert result.ports["warnings"] == {
        "warnings": ["stub recommend-next warning"],
        "suppressed_track_ids": [],
        "recommendation_policy": "review_only",
    }
    assert runtime.ensure_node_config(recommend_next_id)["current_track_id"] == "track_alpha"
