"""Execution runtime for the desktop node host.

The desktop UI should be a control surface over this runtime rather than the
place where graph execution logic lives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from dancelab.contracts.node_host import NodeHostRegistry, get_node_host_registry
from dancelab.core.config import (
    DescriptorWeights,
    EngineConfig,
    load_config,
    load_context_profiles,
    load_weights,
)
from dancelab.core.models import (
    AnalysisResult,
    ContextProfile,
    EdgeDecision,
    MixabilityInput,
    NextTrackRecommendation,
    TransitionWindowInput,
)
from dancelab.core.pipeline import analyze_track
from dancelab.data.dataset_manifest import build_dataset_manifest
from dancelab.decision.edge_decision import build_edge_decision
from dancelab.decision.mixability import compute_mixability
from dancelab.decision.next_track import recommend_next
from dancelab.decision.set_builder import build_set
from dancelab.export.rekordbox import build_rekordbox_xml, write_rekordbox_xml
from dancelab.decision.transition_windows import detect_transition_windows
from dancelab.storage.repositories import FileAnalysisRepository, TrackNotFoundError


@dataclass
class RuntimeNodeState:
    instance_id: str
    node_id: str


@dataclass
class RuntimeConnection:
    from_instance_id: str
    from_port_key: str
    to_instance_id: str
    to_port_key: str


@dataclass
class NodeExecutionResult:
    node_id: str
    ports: dict[str, Any] = field(default_factory=dict)


def _default_edge_decision_payload(
    *,
    analysis_a: AnalysisResult,
    analysis_b: AnalysisResult,
    config: EngineConfig,
    weights: DescriptorWeights,
) -> EdgeDecision:
    windows_a = detect_transition_windows(
        TransitionWindowInput(
            track_id=analysis_a.track.track_id,
            segments=analysis_a.segments,
            feature_frames=analysis_a.features,
            beatgrid=analysis_a.beatgrid,
        ),
        weights.transition_window,
        top_k=config.analysis.transition_top_n,
    ).windows
    windows_b = detect_transition_windows(
        TransitionWindowInput(
            track_id=analysis_b.track.track_id,
            segments=analysis_b.segments,
            feature_frames=analysis_b.features,
            beatgrid=analysis_b.beatgrid,
        ),
        weights.transition_window,
        top_k=config.analysis.transition_top_n,
    ).windows
    mixability = compute_mixability(
        MixabilityInput(
            track_a=analysis_a,
            track_b=analysis_b,
            transition_windows_a=windows_a,
            transition_windows_b=windows_b,
        ),
        weights.mixability,
        conflict_weights=weights.mixability_conflict,
    )
    return build_edge_decision(
        analysis_a,
        analysis_b,
        weights,
        transition_windows_a=windows_a,
        transition_windows_b=windows_b,
        mixability=mixability,
        top_k=config.analysis.transition_top_n,
    )


class DesktopHostRuntime:
    """Graph execution runtime for the Qt host MVP."""

    SUPPORTED_NODE_IDS = {
        "engine",
        "upload_tracks",
        "load_corpus",
        "select_track",
        "select_pair",
        "select_context",
        "analyze_tracks",
        "edge_decision",
        "telemetry_screen",
        "build_set",
        "export_rekordbox",
        "recommend_next",
    }

    def __init__(
        self,
        registry: NodeHostRegistry | None = None,
        *,
        config_path: str | Path = "configs/default.yaml",
        analyze_track_fn: Callable[..., AnalysisResult] = analyze_track,
        edge_decision_fn: Callable[..., EdgeDecision] = _default_edge_decision_payload,
        recommend_next_fn: Callable[..., NextTrackRecommendation] = recommend_next,
        config_loader: Callable[[str | Path], EngineConfig] = load_config,
        weights_loader: Callable[[str | Path], DescriptorWeights] = load_weights,
    ):
        self.registry = registry or get_node_host_registry()
        self.config_path = Path(config_path)
        self._analyze_track = analyze_track_fn
        self._edge_decision = edge_decision_fn
        self._recommend_next = recommend_next_fn
        self._config_loader = config_loader
        self._weights_loader = weights_loader

        self.node_configs: dict[str, dict[str, Any]] = {}
        self.outputs: dict[str, NodeExecutionResult] = {}
        self.errors: dict[str, str] = {}
        self.node_status: dict[str, str] = {}
        self.analysis_index: dict[str, AnalysisResult] = {}
        self.session_message: str = "idle"

        self._config_cache: EngineConfig | None = None
        self._weights_cache: DescriptorWeights | None = None
        self._context_profiles_cache: dict[str, dict[str, Any]] | None = None
        self._repository_cache: dict[str, FileAnalysisRepository] = {}
        self._session_processed_dir: Path | None = None

    @classmethod
    def supports_node(cls, node_id: str) -> bool:
        return node_id in cls.SUPPORTED_NODE_IDS

    def reset_runtime(self) -> None:
        self.outputs.clear()
        self.errors.clear()
        self.node_status.clear()
        self.analysis_index.clear()
        self.session_message = "idle"
        self._session_processed_dir = None

    def ensure_node_config(self, instance_id: str) -> dict[str, Any]:
        return self.node_configs.setdefault(instance_id, {})

    def config(self) -> EngineConfig:
        if self._config_cache is None:
            self._config_cache = self._config_loader(self.config_path)
        return self._config_cache

    def weights(self) -> DescriptorWeights:
        if self._weights_cache is None:
            self._weights_cache = self._weights_loader(self.config().weights_file)
        return self._weights_cache

    def context_profiles(self) -> dict[str, dict[str, Any]]:
        if self._context_profiles_cache is None:
            profiles_path = getattr(self.config(), "context_profiles_file", "configs/context_profiles.yaml")
            self._context_profiles_cache = load_context_profiles(profiles_path)
        return self._context_profiles_cache

    def _processed_dir(self, instance_id: str | None = None) -> Path:
        if instance_id is not None:
            config = self.ensure_node_config(instance_id)
            configured = str(config.get("processed_dir", "")).strip()
            if configured:
                return Path(configured).expanduser()
        if self._session_processed_dir is not None:
            return self._session_processed_dir
        return Path(self.config().paths.processed_dir).expanduser()

    def _annotations_dir(self, instance_id: str | None = None) -> Path:
        if instance_id is not None:
            config = self.ensure_node_config(instance_id)
            configured = str(config.get("annotations_dir", "")).strip()
            if configured:
                return Path(configured).expanduser()
        return Path(self.config().paths.data_dir).expanduser() / "annotations"

    def _repository(self, processed_dir: Path) -> FileAnalysisRepository:
        key = str(processed_dir)
        repo = self._repository_cache.get(key)
        if repo is None:
            repo = FileAnalysisRepository(processed_dir)
            self._repository_cache[key] = repo
        return repo

    def _analysis_for_track_id(
        self,
        track_id: str,
        *,
        processed_dir: Path | None = None,
    ) -> AnalysisResult:
        cached = self.analysis_index.get(track_id)
        if cached is not None:
            return cached
        repo = self._repository(processed_dir or self._processed_dir())
        analysis = repo.get(track_id)
        self.analysis_index[track_id] = analysis
        return analysis

    def _analysis_from_single_source(
        self,
        source: Any,
        *,
        processed_dir: Path | None = None,
    ) -> AnalysisResult | None:
        if isinstance(source, AnalysisResult):
            self.analysis_index[source.track.track_id] = source
            return source
        if isinstance(source, str) and source:
            return self._analysis_for_track_id(str(source), processed_dir=processed_dir)
        return None

    def _track_ids_from_source(self, source: Any) -> list[str]:
        if isinstance(source, list) and source:
            if isinstance(source[0], AnalysisResult):
                return [analysis.track.track_id for analysis in source]
            if isinstance(source[0], str):
                return [str(track_id) for track_id in source]
        return []

    def _analyses_from_source(
        self,
        source: Any,
        *,
        processed_dir: Path | None = None,
    ) -> list[AnalysisResult]:
        if isinstance(source, list) and source:
            if isinstance(source[0], AnalysisResult):
                analyses = [analysis for analysis in source]
                for analysis in analyses:
                    self.analysis_index[analysis.track.track_id] = analysis
                return analyses
            if isinstance(source[0], str):
                return [
                    self._analysis_for_track_id(str(track_id), processed_dir=processed_dir)
                    for track_id in source
                ]
        return []

    def _context_profile_from_source(self, source: Any) -> ContextProfile | None:
        if source is None:
            return None
        if isinstance(source, ContextProfile):
            return source
        if isinstance(source, dict):
            return ContextProfile.model_validate(source)
        return None

    def run(
        self,
        node_states: list[RuntimeNodeState],
        connections: list[RuntimeConnection],
        target_instance_id: str,
    ) -> NodeExecutionResult:
        self.reset_runtime()
        index = {node.instance_id: node for node in node_states}
        result = self._resolve_node(index, connections, target_instance_id, [])
        self.session_message = f"flow complete · {index[target_instance_id].node_id}"
        return result

    def _resolve_node(
        self,
        index: dict[str, RuntimeNodeState],
        connections: list[RuntimeConnection],
        instance_id: str,
        stack: list[str],
    ) -> NodeExecutionResult:
        if instance_id in stack:
            raise RuntimeError(f"cycle detected at {instance_id}")
        if instance_id in self.outputs:
            return self.outputs[instance_id]

        node = index.get(instance_id)
        if node is None:
            raise RuntimeError(f"missing runtime node {instance_id}")

        self.node_status[instance_id] = "running"
        next_stack = [*stack, instance_id]
        try:
            if node.node_id == "upload_tracks":
                result = self._run_upload_tracks(instance_id)
            elif node.node_id == "load_corpus":
                result = self._run_load_corpus(instance_id)
            elif node.node_id == "select_track":
                result = self._run_select_track(index, connections, instance_id, next_stack)
            elif node.node_id == "analyze_tracks":
                result = self._run_analyze_tracks(index, connections, instance_id, next_stack)
            elif node.node_id == "select_pair":
                result = self._run_select_pair(index, connections, instance_id, next_stack)
            elif node.node_id == "select_context":
                result = self._run_select_context(instance_id)
            elif node.node_id == "edge_decision":
                result = self._run_edge_decision(index, connections, instance_id, next_stack)
            elif node.node_id == "telemetry_screen":
                result = self._run_telemetry_screen(index, connections, instance_id, next_stack)
            elif node.node_id == "build_set":
                result = self._run_build_set(index, connections, instance_id, next_stack)
            elif node.node_id == "export_rekordbox":
                result = self._run_export_rekordbox(index, connections, instance_id, next_stack)
            elif node.node_id == "recommend_next":
                result = self._run_recommend_next(index, connections, instance_id, next_stack)
            elif node.node_id == "engine":
                result = NodeExecutionResult(node_id=node.node_id)
            else:
                raise RuntimeError(
                    f"desktop runtime does not execute node `{node.node_id}` yet"
                )
        except Exception as exc:
            self.node_status[instance_id] = "error"
            self.errors[instance_id] = str(exc)
            self.session_message = str(exc)
            raise

        self.outputs[instance_id] = result
        self.node_status[instance_id] = "done"
        self.errors.pop(instance_id, None)
        return result

    def _connected_into(
        self,
        connections: list[RuntimeConnection],
        instance_id: str,
        input_port_key: str,
    ) -> RuntimeConnection | None:
        for edge in connections:
            if edge.to_instance_id == instance_id and edge.to_port_key == input_port_key:
                return edge
        return None

    def _resolve_connected_value(
        self,
        index: dict[str, RuntimeNodeState],
        connections: list[RuntimeConnection],
        instance_id: str,
        input_port_key: str,
        stack: list[str],
    ) -> Any:
        edge = self._connected_into(connections, instance_id, input_port_key)
        if edge is None:
            return None
        upstream = self._resolve_node(index, connections, edge.from_instance_id, stack)
        return upstream.ports.get(edge.from_port_key)

    def _run_upload_tracks(self, instance_id: str) -> NodeExecutionResult:
        config = self.ensure_node_config(instance_id)
        paths = [
            line.strip()
            for line in str(config.get("paths_text", "")).splitlines()
            if line.strip()
        ]
        if not paths:
            raise RuntimeError(
                "Upload Tracks is empty. Add one server-visible audio path per line."
            )
        return NodeExecutionResult(
            node_id="upload_tracks",
            ports={"tracks": paths},
        )

    def _run_load_corpus(self, instance_id: str) -> NodeExecutionResult:
        processed_dir = self._processed_dir(instance_id)
        annotations_dir = self._annotations_dir(instance_id)
        self._session_processed_dir = processed_dir

        repo = self._repository(processed_dir)
        track_ids = repo.list_track_ids()
        config = self.ensure_node_config(instance_id)
        load_mode = str(config.get("load_mode") or "track_ids")

        analyses: list[AnalysisResult] = []
        if load_mode == "analysis":
            analyses = [
                self._analysis_for_track_id(track_id, processed_dir=processed_dir)
                for track_id in track_ids
            ]

        manifest, report = build_dataset_manifest(
            processed_dir,
            annotations_dir=annotations_dir,
            engine_version=self.config().engine.version,
        )
        manifest_payload = {
            **manifest.model_dump(mode="json"),
            "validation": report.model_dump(mode="json"),
            "processed_dir": str(processed_dir),
            "annotations_dir": str(annotations_dir),
            "analysis_loaded": len(analyses),
        }
        return NodeExecutionResult(
            node_id="load_corpus",
            ports={
                "track_ids": track_ids,
                "analysis": analyses,
                "manifest": manifest_payload,
            },
        )

    def _run_select_track(
        self,
        index: dict[str, RuntimeNodeState],
        connections: list[RuntimeConnection],
        instance_id: str,
        stack: list[str],
    ) -> NodeExecutionResult:
        source = self._resolve_connected_value(index, connections, instance_id, "source", stack)
        analyses = self._analyses_from_source(source)
        track_ids = self._track_ids_from_source(source)

        if not track_ids:
            analyses = list(self.analysis_index.values())
            track_ids = [analysis.track.track_id for analysis in analyses]

        if not track_ids:
            raise RuntimeError("Select Track needs at least one upstream track or analyzed result.")

        config = self.ensure_node_config(instance_id)
        selected_track_id = str(config.get("track_id") or track_ids[0])
        if selected_track_id not in track_ids:
            selected_track_id = track_ids[0]
        config["track_id"] = selected_track_id

        selected_analysis = next(
            (analysis for analysis in analyses if analysis.track.track_id == selected_track_id),
            None,
        )
        if selected_analysis is None:
            try:
                selected_analysis = self._analysis_for_track_id(selected_track_id)
            except TrackNotFoundError:
                selected_analysis = None
        return NodeExecutionResult(
            node_id="select_track",
            ports={
                "track": selected_analysis or selected_track_id,
                "track_id": selected_track_id,
            },
        )

    def _run_analyze_tracks(
        self,
        index: dict[str, RuntimeNodeState],
        connections: list[RuntimeConnection],
        instance_id: str,
        stack: list[str],
    ) -> NodeExecutionResult:
        track_files = self._resolve_connected_value(index, connections, instance_id, "tracks", stack)
        if not isinstance(track_files, list) or not track_files:
            raise RuntimeError("Analyze Tracks needs upstream track files.")

        analyses: list[AnalysisResult] = []
        cfg = self.config()
        for path in track_files:
            analysis = self._analyze_track(path, cfg)
            analyses.append(analysis)
            self.analysis_index[analysis.track.track_id] = analysis

        return NodeExecutionResult(
            node_id="analyze_tracks",
            ports={
                "analysis": analyses,
                "track_ids": [analysis.track.track_id for analysis in analyses],
            },
        )

    def _run_select_pair(
        self,
        index: dict[str, RuntimeNodeState],
        connections: list[RuntimeConnection],
        instance_id: str,
        stack: list[str],
    ) -> NodeExecutionResult:
        source = self._resolve_connected_value(index, connections, instance_id, "source", stack)
        track_ids = self._track_ids_from_source(source)
        analyses = self._analyses_from_source(source)
        if not track_ids:
            if analyses:
                track_ids = [analysis.track.track_id for analysis in analyses]
            else:
                track_ids = [analysis.track.track_id for analysis in self.analysis_index.values()]
        if len(track_ids) < 2:
            raise RuntimeError("Select Pair needs at least two analyzed tracks.")

        config = self.ensure_node_config(instance_id)
        track_id_a = str(config.get("track_id_a") or track_ids[0])
        if track_id_a not in track_ids:
            track_id_a = track_ids[0]

        track_id_b = str(config.get("track_id_b") or "")
        if track_id_b not in track_ids or track_id_b == track_id_a:
            track_id_b = next((track_id for track_id in track_ids if track_id != track_id_a), "")

        if not track_id_b or track_id_a == track_id_b:
            raise RuntimeError("Select Pair must resolve two distinct tracks.")

        config["track_id_a"] = track_id_a
        config["track_id_b"] = track_id_b
        return NodeExecutionResult(
            node_id="select_pair",
            ports={
                "pair": {
                    "track_id_a": track_id_a,
                    "track_id_b": track_id_b,
                }
            },
        )

    def _run_select_context(self, instance_id: str) -> NodeExecutionResult:
        profiles = self.context_profiles()
        if not profiles:
            raise RuntimeError("Select Context cannot find any configured context profiles.")

        ordered_ids = sorted(profiles.keys())
        config = self.ensure_node_config(instance_id)
        context_id = str(config.get("context_id") or ordered_ids[0])
        if context_id not in profiles:
            context_id = ordered_ids[0]
        config["context_id"] = context_id

        payload = {
            "context_id": context_id,
            **profiles[context_id],
        }
        return NodeExecutionResult(
            node_id="select_context",
            ports={
                "context": payload,
            },
        )

    def _run_edge_decision(
        self,
        index: dict[str, RuntimeNodeState],
        connections: list[RuntimeConnection],
        instance_id: str,
        stack: list[str],
    ) -> NodeExecutionResult:
        pair = self._resolve_connected_value(index, connections, instance_id, "pair", stack)
        if not isinstance(pair, dict):
            raise RuntimeError("Edge Decision needs an upstream pair selection.")

        track_id_a = str(pair.get("track_id_a") or "")
        track_id_b = str(pair.get("track_id_b") or "")
        try:
            analysis_a = self._analysis_for_track_id(track_id_a)
            analysis_b = self._analysis_for_track_id(track_id_b)
        except TrackNotFoundError:
            raise RuntimeError("Edge Decision cannot find analyzed tracks for the selected pair.")

        decision = self._edge_decision(
            analysis_a=analysis_a,
            analysis_b=analysis_b,
            config=self.config(),
            weights=self.weights(),
        )
        decision_payload = (
            decision.model_dump(mode="json") if hasattr(decision, "model_dump") else dict(decision)
        )
        return NodeExecutionResult(
            node_id="edge_decision",
            ports={
                "decision": decision_payload,
                "warnings": {
                    "risks": list(decision_payload.get("risks") or []),
                    "warnings": list(decision_payload.get("warnings") or []),
                },
            },
        )

    def _run_telemetry_screen(
        self,
        index: dict[str, RuntimeNodeState],
        connections: list[RuntimeConnection],
        instance_id: str,
        stack: list[str],
    ) -> NodeExecutionResult:
        source = self._resolve_connected_value(index, connections, instance_id, "source", stack)
        if not isinstance(source, dict):
            raise RuntimeError("Telemetry Screen currently expects an upstream edge decision.")

        score = None
        if isinstance(source.get("core_dj_compatibility_score"), dict):
            score = source["core_dj_compatibility_score"].get("value")
        snapshot = {
            "pair_label": f"{source.get('track_id_a', '--')} -> {source.get('track_id_b', '--')}",
            "score_text": "--" if score is None else f"{float(score):.3f}",
            "strategy": source.get("recommended_transition_strategy", "--"),
            "profile": source.get("blend_profile_auto", "--"),
            "decision_class": source.get("decision_class", "--"),
            "risks": list(source.get("risks") or []),
            "warnings": list(source.get("warnings") or []),
            "reasoning": list(source.get("reasoning") or []),
        }
        return NodeExecutionResult(
            node_id="telemetry_screen",
            ports={
                "snapshot": snapshot,
                "source": source,
            },
        )

    def _run_build_set(
        self,
        index: dict[str, RuntimeNodeState],
        connections: list[RuntimeConnection],
        instance_id: str,
        stack: list[str],
    ) -> NodeExecutionResult:
        source = self._resolve_connected_value(index, connections, instance_id, "analysis", stack)
        analyses = self._analyses_from_source(source)
        if not analyses:
            analyses = list(self.analysis_index.values())
        if not analyses:
            raise RuntimeError("Build Set needs upstream analyses or repository-backed track IDs.")

        config = self.ensure_node_config(instance_id)
        arc = str(config.get("arc") or "build")
        start_track_id = str(config.get("start_track_id") or "").strip() or None
        plan = build_set(
            analyses,
            self.weights(),
            arc=arc,
            start_track_id=start_track_id,
        )
        return NodeExecutionResult(
            node_id="build_set",
            ports={
                "set_plan": plan,
            },
        )

    def _run_export_rekordbox(
        self,
        index: dict[str, RuntimeNodeState],
        connections: list[RuntimeConnection],
        instance_id: str,
        stack: list[str],
    ) -> NodeExecutionResult:
        analysis_source = self._resolve_connected_value(index, connections, instance_id, "analysis", stack)
        analyses = self._analyses_from_source(analysis_source)
        if not analyses:
            analyses = list(self.analysis_index.values())
        if not analyses:
            raise RuntimeError("Export Rekordbox needs upstream analyses or repository-backed track IDs.")

        set_plan_source = self._resolve_connected_value(index, connections, instance_id, "set_plan", stack)
        set_plan = set_plan_source if hasattr(set_plan_source, "track_order") else None

        config = self.ensure_node_config(instance_id)
        playlist_name = str(config.get("playlist_name") or "DanceLab Set")
        output_path_value = str(config.get("output_path") or "").strip()
        output_path = (
            Path(output_path_value).expanduser()
            if output_path_value
            else Path(self.config().paths.data_dir).expanduser() / "exports" / "dancelab_rekordbox.xml"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        xml = build_rekordbox_xml(
            analyses,
            set_plan=set_plan,
            playlist_name=playlist_name,
        )
        written_path = write_rekordbox_xml(xml, output_path)
        config["output_path"] = str(written_path)
        config["playlist_name"] = playlist_name
        return NodeExecutionResult(
            node_id="export_rekordbox",
            ports={
                "xml": xml,
                "artifact_path": str(written_path),
                "playlist_name": playlist_name,
                "track_count": len(analyses),
            },
        )

    def _run_recommend_next(
        self,
        index: dict[str, RuntimeNodeState],
        connections: list[RuntimeConnection],
        instance_id: str,
        stack: list[str],
    ) -> NodeExecutionResult:
        current_source = self._resolve_connected_value(index, connections, instance_id, "current", stack)
        candidates_source = self._resolve_connected_value(index, connections, instance_id, "candidates", stack)
        context_source = self._resolve_connected_value(index, connections, instance_id, "context", stack)

        candidates = self._analyses_from_source(candidates_source)
        candidate_track_ids = self._track_ids_from_source(candidates_source)
        if not candidate_track_ids:
            candidate_track_ids = [analysis.track.track_id for analysis in candidates]
        if not candidate_track_ids:
            candidate_track_ids = [analysis.track.track_id for analysis in self.analysis_index.values()]
        if not candidate_track_ids:
            candidate_track_ids = self._repository(self._processed_dir()).list_track_ids()

        config = self.ensure_node_config(instance_id)
        current_analysis = self._analysis_from_single_source(current_source)
        if current_analysis is None:
            current_track_id = str(
                config.get("current_track_id") or (candidate_track_ids[0] if candidate_track_ids else "")
            ).strip()
            if not current_track_id:
                raise RuntimeError(
                    "Recommend Next needs a current track or a candidate pool to choose from."
                )
            current_analysis = self._analysis_for_track_id(current_track_id)
        config["current_track_id"] = current_analysis.track.track_id

        filtered_candidate_track_ids: list[str] = []
        seen_track_ids: set[str] = set()
        for track_id in candidate_track_ids:
            normalized_track_id = str(track_id).strip()
            if (
                not normalized_track_id
                or normalized_track_id == current_analysis.track.track_id
                or normalized_track_id in seen_track_ids
            ):
                continue
            filtered_candidate_track_ids.append(normalized_track_id)
            seen_track_ids.add(normalized_track_id)

        filtered_candidates: list[AnalysisResult] = []
        seen_candidate_analysis_ids: set[str] = set()
        for analysis in candidates:
            track_id = analysis.track.track_id
            if (
                not track_id
                or track_id == current_analysis.track.track_id
                or track_id in seen_candidate_analysis_ids
            ):
                continue
            filtered_candidates.append(analysis)
            seen_candidate_analysis_ids.add(track_id)

        candidates = filtered_candidates
        if not candidates:
            candidates = [
                self._analysis_for_track_id(track_id)
                for track_id in filtered_candidate_track_ids
            ]
        if not candidates:
            raise RuntimeError("Recommend Next needs candidate tracks to rank.")

        recent_history_ids = [
            line.strip()
            for line in str(config.get("recent_history_text", "")).splitlines()
            if line.strip()
        ]
        recent_history = [
            self._analysis_for_track_id(track_id)
            for track_id in recent_history_ids
            if track_id != current_analysis.track.track_id
        ]
        arc_mode = str(config.get("arc_mode") or "build")
        context = self._context_profile_from_source(context_source)
        recommendation = self._recommend_next(
            current=current_analysis,
            candidates=candidates,
            context=context,
            weights=self.weights(),
            top_k=self.config().analysis.transition_top_n,
            recent_history=recent_history,
            arc_mode=arc_mode,
        )
        payload = (
            recommendation.model_dump(mode="json")
            if hasattr(recommendation, "model_dump")
            else dict(recommendation)
        )
        return NodeExecutionResult(
            node_id="recommend_next",
            ports={
                "recommendation": recommendation,
                "warnings": {
                    "warnings": list(payload.get("warnings") or []),
                    "suppressed_track_ids": list(payload.get("suppressed_track_ids") or []),
                    "recommendation_policy": str(payload.get("recommendation_policy") or ""),
                },
            },
        )
