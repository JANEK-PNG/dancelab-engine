"""Node-host contracts for external graph shells.

This registry is the source of truth for the first DanceLab node host.
It names the real engine-backed nodes, the host-only helper nodes, and the
planned placeholders that are approved directionally but not yet runnable.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field

NodeCategory = Literal[
    "system",
    "input",
    "engine_ops",
    "sensors",
    "screens",
    "utility",
    "output",
]
NodeRuntimeSide = Literal["engine", "host", "bridge"]
NodeStatus = Literal["implemented", "adapter_needed", "host_only", "planned"]
NodeHostExecutionStatus = Literal["runnable", "planned", "engine_only", "adapter_needed"]
NodeExecutionMode = Literal["system", "compute", "query", "view", "utility", "export"]
PortDirection = Literal["input", "output"]


HOST_RUNNABLE_NODE_IDS = frozenset(
    {
        "engine",
        "upload_tracks",
        "load_corpus",
        "select_track",
        "select_pair",
        "select_context",
        "analyze_tracks",
        "extract_stems",
        "edge_decision",
        "telemetry_screen",
        "build_set",
        "export_rekordbox",
        "stem_export",
        "recommend_next",
    }
)


class PortTypeSpec(BaseModel):
    key: str
    label: str
    description: str


class NodePortSpec(BaseModel):
    key: str
    direction: PortDirection
    port_types: list[str] = Field(min_length=1)
    required: bool = True
    multiple: bool = False
    description: str


class NodeSpec(BaseModel):
    node_id: str
    label: str
    category: NodeCategory
    runtime_side: NodeRuntimeSide
    status: NodeStatus
    host_execution_status: NodeHostExecutionStatus = "planned"
    execution_mode: NodeExecutionMode
    summary: str
    default_visible: bool = False
    pinned: bool = False
    deletable: bool = True
    inputs: list[NodePortSpec] = Field(default_factory=list)
    outputs: list[NodePortSpec] = Field(default_factory=list)
    backed_by: list[str] = Field(default_factory=list)
    api_routes: list[str] = Field(default_factory=list)
    recommended_next: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class NodeHostRegistry(BaseModel):
    version: str = "node_host_v0.1"
    design_contract: str = "docs/NODE_HOST_DESIGN_CONTRACT.md"
    dictionary_doc: str = "docs/NODE_DICTIONARY.md"
    port_types: list[PortTypeSpec] = Field(default_factory=list)
    nodes: list[NodeSpec] = Field(default_factory=list)


def _port(
    key: str,
    direction: PortDirection,
    port_types: list[str],
    description: str,
    *,
    required: bool = True,
    multiple: bool = False,
) -> NodePortSpec:
    return NodePortSpec(
        key=key,
        direction=direction,
        port_types=port_types,
        required=required,
        multiple=multiple,
        description=description,
    )


def _in(
    key: str,
    port_types: list[str],
    description: str,
    *,
    required: bool = True,
    multiple: bool = False,
) -> NodePortSpec:
    return _port(
        key,
        "input",
        port_types,
        description,
        required=required,
        multiple=multiple,
    )


def _out(
    key: str,
    port_types: list[str],
    description: str,
    *,
    required: bool = True,
    multiple: bool = False,
) -> NodePortSpec:
    return _port(
        key,
        "output",
        port_types,
        description,
        required=required,
        multiple=multiple,
    )


def _port_types() -> list[PortTypeSpec]:
    return [
        PortTypeSpec(
            key="track_files",
            label="Track Files",
            description="Server-visible audio file paths selected by the host.",
        ),
        PortTypeSpec(
            key="track_id",
            label="Track ID",
            description="One analyzed track identifier stored in the repository.",
        ),
        PortTypeSpec(
            key="track_id_list",
            label="Track ID List",
            description="A list of analyzed track identifiers.",
        ),
        PortTypeSpec(
            key="track_pair_selection",
            label="Track Pair Selection",
            description="A selected ordered pair of track IDs plus optional ranking metadata.",
        ),
        PortTypeSpec(
            key="context_profile",
            label="Context Profile",
            description="A DanceLab context profile such as club peak or warmup.",
        ),
        PortTypeSpec(
            key="analysis_result",
            label="Analysis Result",
            description="One AnalysisResult payload.",
        ),
        PortTypeSpec(
            key="analysis_set",
            label="Analysis Set",
            description="A collection of AnalysisResult payloads.",
        ),
        PortTypeSpec(
            key="transition_window_set",
            label="Transition Window Set",
            description="Candidate mix-in and mix-out windows for one track or pair.",
        ),
        PortTypeSpec(
            key="mixability_result",
            label="Mixability Result",
            description="A MixabilityOutput payload for one ordered track pair.",
        ),
        PortTypeSpec(
            key="edge_decision",
            label="Edge Decision",
            description="A unified pair-level DJ decision payload.",
        ),
        PortTypeSpec(
            key="set_function_output",
            label="Set Function Output",
            description="A classified functional role for one track in a set.",
        ),
        PortTypeSpec(
            key="context_evaluation",
            label="Context Evaluation",
            description="Fit of one track against a context profile.",
        ),
        PortTypeSpec(
            key="next_track_recommendation",
            label="Next Track Recommendation",
            description="Ranked next-track recommendation output.",
        ),
        PortTypeSpec(
            key="sequence_decision",
            label="Sequence Decision",
            description="Short-horizon sequence planner output.",
        ),
        PortTypeSpec(
            key="set_plan",
            label="Set Plan",
            description="Ordered track plan with transition rationale.",
        ),
        PortTypeSpec(
            key="telemetry_manifest",
            label="Telemetry Manifest",
            description="Decision telemetry manifest pointing to external artifacts.",
        ),
        PortTypeSpec(
            key="artifact_bundle",
            label="Artifact Bundle",
            description="A host- or engine-produced bundle of file paths and generated assets.",
        ),
        PortTypeSpec(
            key="dataset_manifest",
            label="Dataset Manifest",
            description="Corpus-level manifest describing available analyzed tracks and annotations.",
        ),
        PortTypeSpec(
            key="stem_bundle",
            label="Stem Bundle",
            description="In-memory or exported stem-aware separation bundle.",
        ),
        PortTypeSpec(
            key="stem_window_feature_set",
            label="Stem Window Feature Set",
            description="Stem-aware 1-second window summaries for vocals, bass, drums, and other.",
        ),
        PortTypeSpec(
            key="scalar_signal",
            label="Scalar Signal",
            description="A narrow sensor stream extracted from a larger contract.",
        ),
        PortTypeSpec(
            key="warning_stream",
            label="Warning Stream",
            description="Warnings, risks, and guardrail flags extracted for monitoring.",
        ),
        PortTypeSpec(
            key="rekordbox_xml",
            label="Rekordbox XML",
            description="A rekordbox XML export artifact.",
        ),
        PortTypeSpec(
            key="host_snapshot",
            label="Host Snapshot",
            description="A host-side visual state or screen snapshot reference.",
        ),
    ]


def _nodes() -> list[NodeSpec]:
    return [
        NodeSpec(
            node_id="engine",
            label="Engine",
            category="system",
            runtime_side="engine",
            status="implemented",
            execution_mode="system",
            summary="Pinned runtime core that anchors the graph and emits engine signals.",
            default_visible=True,
            pinned=True,
            deletable=False,
            inputs=[
                _in("tracks_in", ["track_files", "track_id_list"], "Audio files or analyzed track IDs."),
                _in("context_in", ["context_profile"], "Optional context profile."),
                _in(
                    "pair_request_in",
                    ["track_pair_selection"],
                    "Ordered track pair for pairwise decision nodes.",
                    required=False,
                ),
                _in(
                    "sequence_request_in",
                    ["track_id_list"],
                    "Candidate history or sequence request payload.",
                    required=False,
                ),
            ],
            outputs=[
                _out("analysis_out", ["analysis_set"], "Track analysis outputs."),
                _out("windows_out", ["transition_window_set"], "Transition window outputs."),
                _out("mixability_out", ["mixability_result"], "Pair mixability outputs."),
                _out("edge_decision_out", ["edge_decision"], "Unified pair decision outputs."),
                _out(
                    "next_track_out",
                    ["next_track_recommendation"],
                    "Ranked next-track recommendation outputs.",
                ),
                _out("sequence_out", ["sequence_decision"], "Sequence planner outputs."),
                _out("telemetry_out", ["telemetry_manifest"], "Telemetry manifest outputs."),
                _out("warnings_out", ["warning_stream"], "Warnings and guardrail flags."),
            ],
            backed_by=[
                "dancelab.core.pipeline.analyze_track",
                "dancelab.decision.transition_windows.detect_transition_windows",
                "dancelab.decision.mixability.compute_mixability",
                "dancelab.decision.edge_decision.build_edge_decision",
                "dancelab.decision.next_track.recommend_next",
                "dancelab.decision.sequence.recommend_sequence",
            ],
            recommended_next=[
                "upload_tracks",
                "load_corpus",
                "analyze_tracks",
                "transition_windows",
                "edge_decision",
            ],
            notes=[
                "Only the Engine node should be visible on boot in the host shell.",
                "The Engine node is a graph anchor, not a dashboard widget.",
            ],
        ),
        NodeSpec(
            node_id="upload_tracks",
            label="Upload Tracks",
            category="input",
            runtime_side="host",
            status="host_only",
            execution_mode="utility",
            summary="Host-side file picker that introduces raw audio files into the graph.",
            outputs=[
                _out("tracks", ["track_files"], "Selected audio files for downstream analysis."),
            ],
            recommended_next=["analyze_tracks", "extract_stems"],
            notes=[
                "This node should not auto-mount on startup.",
                "It exists only when the user explicitly starts a session.",
            ],
        ),
        NodeSpec(
            node_id="load_corpus",
            label="Load Track Library",
            category="input",
            runtime_side="bridge",
            status="implemented",
            execution_mode="query",
            summary="Reads analyzed corpus metadata and repository-backed track IDs.",
            outputs=[
                _out("track_ids", ["track_id_list"], "Available analyzed tracks."),
                _out("analysis", ["analysis_set"], "Loaded analysis payloads.", required=False),
                _out("manifest", ["dataset_manifest"], "Corpus manifest and annotation counts."),
            ],
            backed_by=[
                "dancelab.storage.repositories.FileAnalysisRepository.list_track_ids",
                "dancelab.data.dataset_manifest.build_dataset_manifest",
            ],
            recommended_next=["select_track", "select_pair", "build_set", "decision_report"],
            notes=[
                "The desktop host can bridge the local repository directly.",
                "A dedicated public API route still does not exist.",
            ],
        ),
        NodeSpec(
            node_id="select_track",
            label="Select Track",
            category="input",
            runtime_side="host",
            status="host_only",
            execution_mode="utility",
            summary="Host-side selector that narrows a corpus or analysis set to one track.",
            inputs=[
                _in("source", ["track_id_list", "analysis_set"], "Available tracks to pick from."),
            ],
            outputs=[
                _out("track", ["track_id", "analysis_result"], "Selected track reference or payload."),
            ],
            recommended_next=["transition_windows", "set_function", "context_evaluate"],
        ),
        NodeSpec(
            node_id="select_pair",
            label="Select Pair",
            category="input",
            runtime_side="host",
            status="host_only",
            execution_mode="utility",
            summary="Host-side selector for one ordered A->B transition candidate.",
            inputs=[
                _in(
                    "source",
                    ["track_id_list", "analysis_set", "mixability_result", "edge_decision"],
                    "Available tracks or scored pair candidates.",
                ),
            ],
            outputs=[
                _out("pair", ["track_pair_selection"], "One ordered track pair selection."),
            ],
            recommended_next=["mixability", "edge_decision", "listen_screen"],
        ),
        NodeSpec(
            node_id="select_context",
            label="Select Context",
            category="input",
            runtime_side="host",
            status="host_only",
            execution_mode="utility",
            summary="Host-side source for a context profile.",
            outputs=[
                _out("context", ["context_profile"], "Selected context profile."),
            ],
            backed_by=["GET /contexts/profiles"],
            api_routes=["/contexts/profiles"],
            recommended_next=[
                "analyze_tracks",
                "transition_windows",
                "mixability",
                "edge_decision",
                "recommend_sequence",
            ],
        ),
        NodeSpec(
            node_id="analyze_tracks",
            label="Analyze Tracks",
            category="engine_ops",
            runtime_side="bridge",
            status="implemented",
            execution_mode="compute",
            summary="Runs the main analysis pipeline for one or more audio files.",
            inputs=[
                _in("tracks", ["track_files"], "Track files selected by the host."),
                _in("context", ["context_profile"], "Optional context profile.", required=False),
            ],
            outputs=[
                _out("analysis", ["analysis_set"], "AnalysisResult payloads."),
            ],
            backed_by=[
                "dancelab.core.pipeline.analyze_track",
                "POST /tracks/analyze",
                "dancelab.cli.batch",
            ],
            api_routes=["/tracks/analyze"],
            recommended_next=[
                "transition_windows",
                "set_function",
                "select_pair",
                "decision_report",
            ],
        ),
        NodeSpec(
            node_id="extract_stems",
            label="Extract Stems",
            category="engine_ops",
            runtime_side="bridge",
            status="implemented",
            execution_mode="compute",
            summary="Runs stem-aware analysis and optional source separation for one track.",
            inputs=[
                _in("tracks", ["track_files"], "Track files selected by the host."),
                _in("context", ["context_profile"], "Optional context profile.", required=False),
            ],
            outputs=[
                _out("analysis", ["analysis_set"], "Stem-aware AnalysisResult payloads."),
                _out("stems", ["stem_bundle"], "Stem separation bundle and provenance."),
                _out(
                    "stem_windows",
                    ["stem_window_feature_set"],
                    "Stem-aware window features for downstream sensing.",
                ),
            ],
            backed_by=[
                "dancelab.core.pipeline.analyze_track_with_stems",
                "dancelab.stems.extractor.extract_stems",
                "dancelab.stems.window_features.build_stem_window_features",
            ],
            api_routes=["/stems/export"],
            recommended_next=["stem_window_sensor", "stem_export"],
            notes=[
                "Desktop/API bridge enables explicit stem-aware analysis for export workflows.",
            ],
        ),
        NodeSpec(
            node_id="transition_windows",
            label="Transition Windows",
            category="engine_ops",
            runtime_side="bridge",
            status="implemented",
            execution_mode="compute",
            summary="Computes candidate mix-in and mix-out windows for a track.",
            inputs=[
                _in(
                    "track",
                    ["track_id", "analysis_result"],
                    "Track reference or loaded analysis payload.",
                ),
                _in("context", ["context_profile"], "Optional context profile.", required=False),
            ],
            outputs=[
                _out("windows", ["transition_window_set"], "TransitionWindowOutput payload."),
            ],
            backed_by=[
                "dancelab.decision.transition_windows.detect_transition_windows",
                "POST /tracks/{track_id}/transition-windows",
            ],
            api_routes=["/tracks/{track_id}/transition-windows"],
            recommended_next=["window_sensor", "set_function", "waveform_screen"],
        ),
        NodeSpec(
            node_id="mixability",
            label="Mixability",
            category="engine_ops",
            runtime_side="bridge",
            status="implemented",
            execution_mode="compute",
            summary="Scores pair compatibility and returns best paired windows plus risks.",
            inputs=[
                _in("pair", ["track_pair_selection"], "Ordered pair selection."),
                _in("context", ["context_profile"], "Optional context profile.", required=False),
            ],
            outputs=[
                _out("mixability", ["mixability_result"], "MixabilityOutput payload."),
            ],
            backed_by=[
                "dancelab.decision.mixability.compute_mixability",
                "POST /pairs/mixability",
            ],
            api_routes=["/pairs/mixability"],
            recommended_next=["edge_decision", "waveform_screen", "pair_review_screen"],
        ),
        NodeSpec(
            node_id="edge_decision",
            label="Edge Decision",
            category="engine_ops",
            runtime_side="bridge",
            status="implemented",
            execution_mode="compute",
            summary="Builds the unified pair-level DJ decision payload.",
            inputs=[
                _in("pair", ["track_pair_selection"], "Ordered pair selection."),
                _in("context", ["context_profile"], "Optional context profile.", required=False),
            ],
            outputs=[
                _out("decision", ["edge_decision"], "Unified EdgeDecision payload."),
                _out("warnings", ["warning_stream"], "Rule flags, risks, and warnings."),
            ],
            backed_by=[
                "dancelab.decision.edge_decision.build_edge_decision",
                "POST /pairs/edge-decision",
            ],
            api_routes=["/pairs/edge-decision"],
            recommended_next=[
                "blend_profile_sensor",
                "risk_sensor",
                "listen_screen",
                "telemetry_screen",
            ],
        ),
        NodeSpec(
            node_id="context_evaluate",
            label="Evaluate Context Fit",
            category="engine_ops",
            runtime_side="bridge",
            status="implemented",
            execution_mode="compute",
            summary="Evaluates one track against a selected context profile.",
            inputs=[
                _in("track", ["track_id", "analysis_result"], "Track reference or analysis payload."),
                _in("context", ["context_profile"], "Context profile to evaluate."),
            ],
            outputs=[
                _out("evaluation", ["context_evaluation"], "ContextEvaluation payload."),
            ],
            backed_by=[
                "dancelab.context.conditioning.evaluate_context",
                "POST /contexts/evaluate",
            ],
            api_routes=["/contexts/evaluate"],
            recommended_next=["risk_sensor", "telemetry_screen"],
        ),
        NodeSpec(
            node_id="set_function",
            label="Classify Track Role",
            category="engine_ops",
            runtime_side="bridge",
            status="implemented",
            execution_mode="compute",
            summary="Classifies the role of one track inside a set.",
            inputs=[
                _in("track", ["track_id", "analysis_result"], "Track reference or analysis payload."),
                _in("context", ["context_profile"], "Optional context profile.", required=False),
            ],
            outputs=[
                _out("function", ["set_function_output"], "SetFunctionOutput payload."),
            ],
            backed_by=[
                "dancelab.decision.set_function.classify_set_function",
                "POST /tracks/{track_id}/set-function",
            ],
            api_routes=["/tracks/{track_id}/set-function"],
            recommended_next=["telemetry_screen", "recommend_sequence"],
        ),
        NodeSpec(
            node_id="recommend_next",
            label="Recommend Next Track",
            category="engine_ops",
            runtime_side="bridge",
            status="implemented",
            execution_mode="compute",
            summary="Ranks candidate next tracks with set-history-aware policy checks.",
            inputs=[
                _in("current", ["track_id"], "Current track ID."),
                _in("candidates", ["track_id_list"], "Candidate next-track IDs."),
                _in("context", ["context_profile"], "Optional context profile.", required=False),
            ],
            outputs=[
                _out("recommendation", ["next_track_recommendation"], "NextTrackRecommendation payload."),
                _out("warnings", ["warning_stream"], "Policy flags and warnings."),
            ],
            backed_by=[
                "dancelab.decision.next_track.recommend_next",
                "POST /sets/recommend-next",
            ],
            api_routes=["/sets/recommend-next"],
            recommended_next=["filter", "top_n", "telemetry_screen"],
        ),
        NodeSpec(
            node_id="recommend_sequence",
            label="Recommend Full Sequence",
            category="engine_ops",
            runtime_side="bridge",
            status="implemented",
            execution_mode="compute",
            summary="Builds a short-horizon sequence using local and global arc scoring plus guardrails.",
            inputs=[
                _in("current", ["track_id"], "Current track ID."),
                _in("candidates", ["track_id_list"], "Candidate track IDs."),
                _in("context", ["context_profile"], "Optional context profile.", required=False),
            ],
            outputs=[
                _out("sequence", ["sequence_decision"], "SequenceDecision payload."),
                _out("warnings", ["warning_stream"], "Sequence guardrails and policy flags."),
            ],
            backed_by=[
                "dancelab.decision.sequence.recommend_sequence",
                "POST /sets/recommend-sequence",
            ],
            api_routes=["/sets/recommend-sequence"],
            recommended_next=["risk_sensor", "telemetry_screen"],
        ),
        NodeSpec(
            node_id="build_set",
            label="Generate Set Sequence",
            category="engine_ops",
            runtime_side="bridge",
            status="implemented",
            execution_mode="compute",
            summary="Builds a simple ordered set plan from analyzed tracks.",
            inputs=[
                _in("analysis", ["analysis_set", "track_id_list"], "Analyzed tracks or their IDs."),
            ],
            outputs=[
                _out("set_plan", ["set_plan"], "SetPlan payload."),
            ],
            backed_by=[
                "dancelab.decision.set_builder.build_set",
                "dancelab.cli.export_rekordbox",
            ],
            recommended_next=["export_rekordbox"],
            notes=[
                "The desktop host can execute set building directly from loaded analyses or repository-backed track IDs.",
                "A dedicated public API route still does not exist.",
            ],
        ),
        NodeSpec(
            node_id="bpm_sensor",
            label="BPM Signal",
            category="sensors",
            runtime_side="host",
            status="implemented",
            execution_mode="query",
            summary="Extracts tempo-related measurements from analysis and decision outputs.",
            inputs=[
                _in(
                    "source",
                    ["analysis_result", "analysis_set", "edge_decision", "sequence_decision"],
                    "Contracts containing BPM or effective BPM metadata.",
                ),
            ],
            outputs=[_out("signal", ["scalar_signal"], "Tempo-oriented scalar stream.")],
            backed_by=["AnalysisResult.track.bpm_estimate", "EdgeDecision.bpm_delta_pct"],
            recommended_next=["telemetry_screen", "control_center_screen"],
        ),
        NodeSpec(
            node_id="key_sensor",
            label="Key Detection Signal",
            category="sensors",
            runtime_side="host",
            status="implemented",
            execution_mode="query",
            summary="Extracts tonal and harmonic compatibility fields.",
            inputs=[
                _in(
                    "source",
                    ["analysis_result", "mixability_result", "edge_decision"],
                    "Contracts containing key or harmonic fields.",
                ),
            ],
            outputs=[_out("signal", ["scalar_signal"], "Key or harmonic scalar stream.")],
            backed_by=["AnalysisResult.track.key_estimate", "MixabilityOutput.harmonic_relation"],
            recommended_next=["telemetry_screen", "control_center_screen"],
        ),
        NodeSpec(
            node_id="energy_sensor",
            label="Energy Signal",
            category="sensors",
            runtime_side="host",
            status="implemented",
            execution_mode="query",
            summary="Extracts energy, tension, release, and intensity-oriented signals.",
            inputs=[
                _in(
                    "source",
                    ["analysis_result", "set_function_output", "sequence_decision"],
                    "Contracts containing energy-profile fields.",
                ),
            ],
            outputs=[_out("signal", ["scalar_signal"], "Energy-oriented scalar stream.")],
            backed_by=["AnalysisResult.features", "SequenceDecision.target_energy_profile"],
            recommended_next=["telemetry_screen", "control_center_screen"],
        ),
        NodeSpec(
            node_id="risk_sensor",
            label="Risk Signal",
            category="sensors",
            runtime_side="host",
            status="implemented",
            execution_mode="query",
            summary="Extracts risk, warnings, and policy flags from decision outputs.",
            inputs=[
                _in(
                    "source",
                    [
                        "mixability_result",
                        "edge_decision",
                        "context_evaluation",
                        "next_track_recommendation",
                        "sequence_decision",
                    ],
                    "Contracts containing risks or warnings.",
                ),
            ],
            outputs=[_out("warnings", ["warning_stream"], "Risk and warning stream.")],
            backed_by=["EdgeDecision.risks", "SequenceDecision.guardrail_flags"],
            recommended_next=["warning_console", "control_center_screen", "telemetry_screen"],
        ),
        NodeSpec(
            node_id="blend_profile_sensor",
            label="Blend Compatibility Signal",
            category="sensors",
            runtime_side="host",
            status="implemented",
            execution_mode="query",
            summary="Extracts the engine-selected automatic blend profile.",
            inputs=[
                _in("source", ["edge_decision"], "EdgeDecision payload."),
            ],
            outputs=[_out("signal", ["scalar_signal"], "Blend-profile signal.")],
            backed_by=["EdgeDecision.blend_profile_auto"],
            recommended_next=["listen_screen", "telemetry_screen"],
        ),
        NodeSpec(
            node_id="window_sensor",
            label="Transition Window Signal",
            category="sensors",
            runtime_side="host",
            status="implemented",
            execution_mode="query",
            summary="Extracts transition window timing and score measurements.",
            inputs=[
                _in(
                    "source",
                    ["transition_window_set", "mixability_result", "edge_decision"],
                    "Contracts containing transition window timing.",
                ),
            ],
            outputs=[_out("signal", ["scalar_signal"], "Window timing signal.")],
            backed_by=["TransitionWindowOutput.windows", "EdgeDecision.selected_window_a"],
            recommended_next=["waveform_screen", "listen_screen"],
        ),
        NodeSpec(
            node_id="harmonic_sensor",
            label="Harmonic Signal",
            category="sensors",
            runtime_side="host",
            status="implemented",
            execution_mode="query",
            summary="Extracts harmonic relation and tonal risk data for pair decisions.",
            inputs=[
                _in("source", ["mixability_result", "edge_decision"], "Pair decision contracts."),
            ],
            outputs=[_out("signal", ["scalar_signal"], "Harmonic compatibility signal.")],
            backed_by=["MixabilityOutput.harmonic_relation", "EdgeDecision.harmonic_risk"],
            recommended_next=["telemetry_screen", "control_center_screen"],
        ),
        NodeSpec(
            node_id="stem_window_sensor",
            label="Stem Window Signal",
            category="sensors",
            runtime_side="host",
            status="adapter_needed",
            execution_mode="query",
            summary="Extracts stem-aware activity windows for vocals, bass, drums, and other.",
            inputs=[
                _in(
                    "source",
                    ["analysis_result", "stem_window_feature_set"],
                    "Stem-aware analysis payload or explicit stem windows.",
                ),
            ],
            outputs=[
                _out("signal", ["stem_window_feature_set", "scalar_signal"], "Stem activity signal."),
            ],
            backed_by=["AnalysisResult.stem_window_features"],
            recommended_next=["listen_screen", "waveform_screen"],
            notes=[
                "The underlying data exists, but a dedicated host adapter still needs to be formalized.",
            ],
        ),
        NodeSpec(
            node_id="telemetry_screen",
            label="Telemetry Summary View",
            category="screens",
            runtime_side="host",
            status="adapter_needed",
            execution_mode="view",
            summary="Visual screen for decision summaries, metrics, and sensor readouts.",
            inputs=[
                _in(
                    "source",
                    ["telemetry_manifest", "edge_decision", "mixability_result", "sequence_decision"],
                    "Telemetry manifest or direct decision payloads.",
                ),
            ],
            outputs=[_out("snapshot", ["host_snapshot"], "Rendered host-side view snapshot.")],
            backed_by=[
                "dancelab.validation.review_ui.swipe_review._render_control_center_page",
                "dancelab.validation.review_ui.swipe_review._render_index_page",
            ],
            recommended_next=["save_snapshot"],
            notes=[
                "Current implementations are standalone diagnostics pages and should be wrapped, not moved into the engine.",
            ],
        ),
        NodeSpec(
            node_id="waveform_screen",
            label="Waveform Comparison View",
            category="screens",
            runtime_side="host",
            status="adapter_needed",
            execution_mode="view",
            summary="Visual waveform comparison screen for pair windows and transition timing.",
            inputs=[
                _in(
                    "source",
                    ["telemetry_manifest", "mixability_result", "edge_decision", "transition_window_set"],
                    "Waveform-capable telemetry or pair outputs.",
                ),
            ],
            outputs=[_out("snapshot", ["host_snapshot"], "Rendered waveform view.")],
            backed_by=["dancelab.visualization.mixability_waveforms"],
            recommended_next=["save_snapshot"],
        ),
        NodeSpec(
            node_id="listen_screen",
            label="A/B Audition View",
            category="screens",
            runtime_side="host",
            status="adapter_needed",
            execution_mode="view",
            summary="External listen board for A/B transition audition with engine hints.",
            inputs=[
                _in(
                    "source",
                    ["telemetry_manifest", "edge_decision", "mixability_result"],
                    "Pair telemetry or direct pair contracts.",
                ),
            ],
            outputs=[_out("snapshot", ["host_snapshot"], "Rendered listen-board view.")],
            backed_by=["dancelab.validation.review_ui.swipe_review._render_listen_page"],
            recommended_next=["save_snapshot"],
            notes=[
                "Beat sync, quantize, and DJ-style layer logic must stay host-side unless formalized as engine outputs.",
            ],
        ),
        NodeSpec(
            node_id="pair_review_screen",
            label="Pair Review View",
            category="screens",
            runtime_side="host",
            status="adapter_needed",
            execution_mode="view",
            summary="Swipe-style pair review screen for bounded validation.",
            inputs=[
                _in("source", ["telemetry_manifest"], "Decision report telemetry manifest."),
            ],
            outputs=[_out("snapshot", ["host_snapshot"], "Rendered pair review view.")],
            backed_by=["dancelab.validation.review_ui.swipe_review._render_pair_page"],
            recommended_next=["save_snapshot"],
        ),
        NodeSpec(
            node_id="control_center_screen",
            label="Engine Telemetry Dashboard",
            category="screens",
            runtime_side="host",
            status="adapter_needed",
            execution_mode="view",
            summary="Live diagnostics-style dashboard over engine telemetry and sensor signals.",
            inputs=[
                _in("source", ["telemetry_manifest", "warning_stream"], "Telemetry manifest or warning stream."),
            ],
            outputs=[_out("snapshot", ["host_snapshot"], "Rendered control-center view.")],
            backed_by=["dancelab.validation.review_ui.swipe_review._render_control_center_page"],
            recommended_next=["save_snapshot"],
        ),
        NodeSpec(
            node_id="warning_console",
            label="Warning Console",
            category="screens",
            runtime_side="host",
            status="planned",
            execution_mode="view",
            summary="Compact stream of warnings, risks, and guardrail flags.",
            inputs=[
                _in("source", ["warning_stream"], "Warning and risk stream."),
            ],
            outputs=[_out("snapshot", ["host_snapshot"], "Rendered warning console view.")],
            recommended_next=["save_snapshot"],
        ),
        NodeSpec(
            node_id="filter",
            label="Filter",
            category="utility",
            runtime_side="host",
            status="planned",
            execution_mode="utility",
            summary="Keep only results matching selected conditions.",
            inputs=[
                _in(
                    "source",
                    [
                        "track_id_list",
                        "analysis_set",
                        "next_track_recommendation",
                        "sequence_decision",
                        "artifact_bundle",
                    ],
                    "Typed source collection.",
                ),
            ],
            outputs=[_out("result", ["track_id_list", "analysis_set", "artifact_bundle"], "Filtered result.")],
            recommended_next=["sort", "top_n"],
        ),
        NodeSpec(
            node_id="sort",
            label="Sort",
            category="utility",
            runtime_side="host",
            status="planned",
            execution_mode="utility",
            summary="Sort results by score, BPM, key, energy, risk or confidence.",
            inputs=[
                _in(
                    "source",
                    ["track_id_list", "analysis_set", "next_track_recommendation"],
                    "Typed source collection.",
                ),
            ],
            outputs=[_out("result", ["track_id_list", "analysis_set"], "Sorted result.")],
            recommended_next=["top_n", "select_pair"],
        ),
        NodeSpec(
            node_id="top_n",
            label="Top N",
            category="utility",
            runtime_side="host",
            status="planned",
            execution_mode="utility",
            summary="Keep only the top N ranked results.",
            inputs=[
                _in(
                    "source",
                    ["next_track_recommendation", "sequence_decision", "track_id_list"],
                    "Ranked source collection.",
                ),
            ],
            outputs=[_out("result", ["track_id_list", "artifact_bundle"], "Top-ranked subset.")],
            recommended_next=["telemetry_screen", "pair_review_screen"],
        ),
        NodeSpec(
            node_id="threshold",
            label="Threshold",
            category="utility",
            runtime_side="host",
            status="planned",
            execution_mode="utility",
            summary="Remove or flag results below/above a selected score.",
            inputs=[
                _in("source", ["scalar_signal", "warning_stream"], "Scalar or warning signal."),
            ],
            outputs=[_out("result", ["scalar_signal", "warning_stream"], "Thresholded signal.")],
            recommended_next=["warning_console", "control_center_screen"],
        ),
        NodeSpec(
            node_id="compare",
            label="Compare",
            category="utility",
            runtime_side="host",
            status="planned",
            execution_mode="utility",
            summary="Compare two result sets or two transition candidates.",
            inputs=[
                _in("left", ["scalar_signal", "analysis_result", "edge_decision"], "Left input."),
                _in("right", ["scalar_signal", "analysis_result", "edge_decision"], "Right input."),
            ],
            outputs=[_out("result", ["artifact_bundle", "scalar_signal"], "Comparison output.")],
            recommended_next=["telemetry_screen"],
        ),
        NodeSpec(
            node_id="route",
            label="Router / Fan-out",
            category="utility",
            runtime_side="host",
            status="planned",
            execution_mode="utility",
            summary="Send one output into multiple downstream nodes for cleaner graph layout.",
            inputs=[
                _in(
                    "source",
                    [
                        "track_id_list",
                        "analysis_set",
                        "edge_decision",
                        "telemetry_manifest",
                        "warning_stream",
                    ],
                    "Typed source signal.",
                ),
            ],
            outputs=[
                _out(
                    "result",
                    [
                        "track_id_list",
                        "analysis_set",
                        "edge_decision",
                        "telemetry_manifest",
                        "warning_stream",
                    ],
                    "Rerouted signal.",
                ),
            ],
            recommended_next=["telemetry_screen", "listen_screen", "warning_console"],
        ),
        NodeSpec(
            node_id="decision_report",
            label="Decision Report",
            category="output",
            runtime_side="bridge",
            status="implemented",
            execution_mode="export",
            summary="Builds pairwise decision artifacts and the telemetry manifest used by external diagnostics.",
            inputs=[
                _in("analysis", ["analysis_set", "track_id_list"], "Analyzed tracks or their IDs."),
                _in("context", ["context_profile"], "Optional context profile.", required=False),
            ],
            outputs=[
                _out("telemetry", ["telemetry_manifest"], "Decision telemetry manifest."),
                _out("artifacts", ["artifact_bundle"], "Generated CSV, JSON, and waveform artifacts."),
            ],
            backed_by=[
                "dancelab.visualization.decision_report.build_decision_report",
                "dancelab.contracts.telemetry.DecisionTelemetryManifest",
                "dancelab.cli.report.decision_report",
            ],
            recommended_next=[
                "telemetry_screen",
                "waveform_screen",
                "listen_screen",
                "pair_review_screen",
            ],
        ),
        NodeSpec(
            node_id="validation_pack",
            label="Validation Pack",
            category="output",
            runtime_side="bridge",
            status="implemented",
            execution_mode="export",
            summary="Builds the bounded validation pack and review surfaces from analyzed tracks.",
            inputs=[
                _in("analysis", ["analysis_set", "track_id_list"], "Analyzed tracks or their IDs."),
                _in(
                    "telemetry",
                    ["telemetry_manifest"],
                    "Optional decision telemetry manifest.",
                    required=False,
                ),
            ],
            outputs=[
                _out("artifacts", ["artifact_bundle"], "Generated validation artifacts and reports."),
            ],
            backed_by=[
                "dancelab.validation.pilot_pack.build_validation_pack",
                "dancelab.cli.validation_pack",
            ],
            recommended_next=["pair_review_screen", "control_center_screen", "listen_screen"],
        ),
        NodeSpec(
            node_id="export_rekordbox",
            label="Export Rekordbox",
            category="output",
            runtime_side="bridge",
            status="implemented",
            execution_mode="export",
            summary="Exports analyzed tracks and optional set plan to rekordbox XML.",
            inputs=[
                _in("analysis", ["analysis_set", "track_id_list"], "Analyzed tracks or their IDs."),
                _in("set_plan", ["set_plan"], "Optional ordered set plan.", required=False),
            ],
            outputs=[
                _out("xml", ["rekordbox_xml"], "Rekordbox XML artifact."),
            ],
            backed_by=[
                "dancelab.export.rekordbox.build_rekordbox_xml",
                "dancelab.cli.export_rekordbox",
            ],
        ),
        NodeSpec(
            node_id="stem_export",
            label="Stem Export",
            category="output",
            runtime_side="bridge",
            status="implemented",
            execution_mode="export",
            summary="Writes per-track folders with source audio, analysis JSON, and separated stems.",
            inputs=[
                _in("analysis", ["analysis_result", "analysis_set"], "Stem-aware analysis payload."),
                _in("stems", ["stem_bundle"], "Stem separation bundle."),
            ],
            outputs=[
                _out("artifacts", ["artifact_bundle"], "Per-track stem artifact folders."),
            ],
            backed_by=["dancelab.stems.exporter.export_stem_artifacts"],
            api_routes=["/stems/export"],
            notes=[
                "Writes user-selected external artifact folders; it does not persist raw stems inside the engine store.",
            ],
        ),
        NodeSpec(
            node_id="save_snapshot",
            label="Save Snapshot",
            category="output",
            runtime_side="host",
            status="planned",
            execution_mode="export",
            summary="Persists host-side screens or graph states outside the engine.",
            inputs=[
                _in("snapshot", ["host_snapshot", "artifact_bundle"], "Host-rendered view or bundle."),
            ],
            outputs=[
                _out("artifacts", ["artifact_bundle"], "Persisted snapshot artifact bundle."),
            ],
        ),
    ]


def _host_execution_status(node: NodeSpec) -> NodeHostExecutionStatus:
    if node.node_id in HOST_RUNNABLE_NODE_IDS:
        return "runnable"
    if node.status == "planned":
        return "planned"
    if node.status == "adapter_needed":
        return "adapter_needed"
    if node.runtime_side == "bridge" and node.status == "implemented":
        return "engine_only"
    return "adapter_needed"


def _with_host_execution_status(node: NodeSpec) -> NodeSpec:
    return node.model_copy(update={"host_execution_status": _host_execution_status(node)})


@lru_cache(maxsize=1)
def get_node_host_registry() -> NodeHostRegistry:
    return NodeHostRegistry(
        port_types=_port_types(),
        nodes=[_with_host_execution_status(node) for node in _nodes()],
    )
