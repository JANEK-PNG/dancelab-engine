"""Batch decision report builder for analyzed tracks."""

from __future__ import annotations

import csv
import json
from datetime import datetime, UTC
from itertools import permutations
from pathlib import Path

from dancelab.contracts.telemetry import DecisionTelemetryManifest
from dancelab.context.context_profile import get_context_profile
from dancelab.core.config import load_config, load_context_profiles, load_weights
from dancelab.core.models import (
    AnalysisResult,
    ContextProfile,
    EdgeDecision,
    MixabilityInput,
    PairWindow,
    TransitionWindow,
    TransitionWindowInput,
)
from dancelab.decision.edge_decision import build_edge_decision
from dancelab.decision.mixability import compute_mixability
from dancelab.decision.transition_windows import detect_transition_windows
from dancelab.storage.repositories import FileAnalysisRepository
from dancelab.visualization.mixability_waveforms import render_mixability_waveform_gallery


def _write_json(data: object, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, sort_keys=False))
    return out


def _write_jsonl(rows: list[dict[str, object]], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=False))
            f.write("\n")
    return out


def _write_csv(rows: list[dict[str, object]], path: str | Path, fieldnames: list[str]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return out


def _available_contexts(config) -> list[ContextProfile]:
    return [
        ContextProfile(context_id=context_id, **payload)
        for context_id, payload in load_context_profiles(config.context_profiles_file).items()
    ]


def _pair_id(track_id_a: str, track_id_b: str) -> str:
    return f"{track_id_a}__{track_id_b}"


def _format_mmss(seconds: float | None) -> str:
    if seconds is None:
        return ""
    total_seconds = max(0, int(round(seconds)))
    minutes, secs = divmod(total_seconds, 60)
    return f"{minutes}:{secs:02d}"


def _format_time_range(start_sec: float | None, end_sec: float | None) -> str:
    if start_sec is None or end_sec is None:
        return ""
    return f"{_format_mmss(start_sec)}-{_format_mmss(end_sec)}"


def _format_transition_window(window: TransitionWindow | None) -> str:
    if window is None:
        return ""
    return _format_time_range(window.start_sec, window.end_sec)


def _format_pair_window(window: PairWindow | None, *, side: str) -> str:
    if window is None:
        return ""
    if side == "a":
        start_sec, end_sec = window.track_a_window
    else:
        start_sec, end_sec = window.track_b_window
    return _format_time_range(start_sec, end_sec)


def _join_values(values: list[object]) -> str:
    return ";".join(str(value) for value in values if value not in ("", None))


EDGE_REVIEW_FIELDS = [
    "pair_id",
    "context_id",
    "title_a",
    "title_b",
    "track_id_a",
    "track_id_b",
    "track_a_source_path",
    "track_b_source_path",
    "engine_decision_class",
    "engine_recommendation_policy",
    "engine_score",
    "engine_confidence",
    "engine_strategy",
    "engine_blend_profile_auto",
    "engine_blend_profile_explanation",
    "engine_alternative_strategies",
    "engine_standard_blend_allowed",
    "engine_tempo_gate",
    "engine_harmonic_gate",
    "engine_tempo_feasibility",
    "engine_tempo_relation",
    "engine_harmonic_relation",
    "engine_context_fit",
    "engine_bass_conflict_risk",
    "engine_vocal_clash_risk",
    "engine_window_a_id",
    "engine_window_a_type",
    "engine_window_a(mm:ss)",
    "engine_window_b_id",
    "engine_window_b_type",
    "engine_window_b(mm:ss)",
    "engine_pair_window_a(mm:ss)",
    "engine_pair_window_b(mm:ss)",
    "engine_pair_score",
    "engine_compatible_contexts",
    "engine_policy_reasons",
    "engine_risks",
    "engine_warnings",
    "dj_verdict(accept/review/reject)",
    "dj_mixability_rating",
    "dj_transition_strategy",
    "dj_comment",
]


def _build_edge_annotation_payload_row(
    pair_id: str,
    analysis_a: AnalysisResult,
    analysis_b: AnalysisResult,
    edge: EdgeDecision,
    *,
    context_id: str | None,
) -> dict[str, object]:
    return {
        "pair_id": pair_id,
        "context_id": context_id,
        "track_id_a": analysis_a.track.track_id,
        "track_id_b": analysis_b.track.track_id,
        "track_a_title": analysis_a.track.title,
        "track_b_title": analysis_b.track.title,
        "track_a_source_path": analysis_a.track.source_path,
        "track_b_source_path": analysis_b.track.source_path,
        "engine_decision_class": edge.decision_class.value,
        "engine_recommendation_policy": edge.recommendation_policy.value,
        "engine_score": edge.core_dj_compatibility_score.value,
        "engine_confidence": edge.core_dj_compatibility_score.confidence,
        "engine_strategy": edge.recommended_transition_strategy.value,
        "engine_blend_profile_auto": edge.blend_profile_auto.value,
        "engine_blend_profile_explanation": edge.blend_profile_explanation,
        "engine_standard_blend_allowed": edge.standard_blend_allowed,
        "engine_tempo_gate": edge.tempo_gate_status.value,
        "engine_harmonic_gate": edge.harmonic_gate_status.value,
        "engine_tempo_feasibility": edge.tempo_window_feasibility.value,
        "engine_tempo_relation": edge.tempo_relation,
        "engine_harmonic_relation": edge.harmonic_relation,
        "engine_context_fit": edge.context_fit_score,
        "engine_bass_conflict_risk": edge.bass_conflict_risk,
        "engine_vocal_clash_risk": edge.vocal_clash_risk,
        "selected_window_a": (
            edge.selected_window_a.model_dump(mode="json") if edge.selected_window_a else None
        ),
        "selected_window_b": (
            edge.selected_window_b.model_dump(mode="json") if edge.selected_window_b else None
        ),
        "selected_pair_window": (
            edge.selected_pair_window.model_dump(mode="json") if edge.selected_pair_window else None
        ),
        "compatible_contexts": edge.compatible_contexts,
        "policy_reasons": edge.policy_reasons,
        "risks": edge.risks,
        "warnings": edge.warnings,
        "reasoning": edge.reasoning,
        "annotation_payload": edge.annotation_payload,
        "provenance": edge.provenance.model_dump(mode="json") if edge.provenance else None,
    }


def _build_edge_review_row(
    pair_id: str,
    analysis_a: AnalysisResult,
    analysis_b: AnalysisResult,
    edge: EdgeDecision,
    *,
    context_id: str | None,
) -> dict[str, object]:
    return {
        "pair_id": pair_id,
        "context_id": context_id or "",
        "title_a": analysis_a.track.title or analysis_a.track.track_id,
        "title_b": analysis_b.track.title or analysis_b.track.track_id,
        "track_id_a": analysis_a.track.track_id,
        "track_id_b": analysis_b.track.track_id,
        "track_a_source_path": analysis_a.track.source_path or "",
        "track_b_source_path": analysis_b.track.source_path or "",
        "engine_decision_class": edge.decision_class.value,
        "engine_recommendation_policy": edge.recommendation_policy.value,
        "engine_score": round(edge.core_dj_compatibility_score.value, 4),
        "engine_confidence": round(edge.core_dj_compatibility_score.confidence, 2),
        "engine_strategy": edge.recommended_transition_strategy.value,
        "engine_blend_profile_auto": edge.blend_profile_auto.value,
        "engine_blend_profile_explanation": edge.blend_profile_explanation,
        "engine_alternative_strategies": _join_values(
            [strategy.value for strategy in edge.alternative_transition_strategies]
        ),
        "engine_standard_blend_allowed": edge.standard_blend_allowed,
        "engine_tempo_gate": edge.tempo_gate_status.value,
        "engine_harmonic_gate": edge.harmonic_gate_status.value,
        "engine_tempo_feasibility": edge.tempo_window_feasibility.value,
        "engine_tempo_relation": edge.tempo_relation,
        "engine_harmonic_relation": edge.harmonic_relation or "",
        "engine_context_fit": (
            round(edge.context_fit_score, 4) if edge.context_fit_score is not None else ""
        ),
        "engine_bass_conflict_risk": (
            round(edge.bass_conflict_risk, 4) if edge.bass_conflict_risk is not None else ""
        ),
        "engine_vocal_clash_risk": (
            round(edge.vocal_clash_risk, 4) if edge.vocal_clash_risk is not None else ""
        ),
        "engine_window_a_id": (
            edge.selected_window_a.transition_window_id if edge.selected_window_a else ""
        ),
        "engine_window_a_type": (
            edge.selected_window_a.window_type.value if edge.selected_window_a else ""
        ),
        "engine_window_a(mm:ss)": _format_transition_window(edge.selected_window_a),
        "engine_window_b_id": (
            edge.selected_window_b.transition_window_id if edge.selected_window_b else ""
        ),
        "engine_window_b_type": (
            edge.selected_window_b.window_type.value if edge.selected_window_b else ""
        ),
        "engine_window_b(mm:ss)": _format_transition_window(edge.selected_window_b),
        "engine_pair_window_a(mm:ss)": _format_pair_window(edge.selected_pair_window, side="a"),
        "engine_pair_window_b(mm:ss)": _format_pair_window(edge.selected_pair_window, side="b"),
        "engine_pair_score": (
            round(edge.selected_pair_window.pair_score, 4) if edge.selected_pair_window else ""
        ),
        "engine_compatible_contexts": _join_values(edge.compatible_contexts),
        "engine_policy_reasons": _join_values(edge.policy_reasons),
        "engine_risks": _join_values(edge.risks),
        "engine_warnings": _join_values(edge.warnings),
        "dj_verdict(accept/review/reject)": "",
        "dj_mixability_rating": "",
        "dj_transition_strategy": "",
        "dj_comment": "",
    }


def build_decision_report(
    processed_dir: str | Path,
    output_dir: str | Path,
    *,
    config_path: str = "configs/default.yaml",
    context_id: str | None = None,
    top_n_waveforms: int = 10,
) -> dict[str, Path]:
    """Create a disk report with pair decisions and waveform visuals."""
    cfg = load_config(config_path)
    weights = load_weights(cfg.weights_file)
    repo = FileAnalysisRepository(processed_dir)
    track_ids = repo.list_track_ids()
    analyses = [repo.get(track_id) for track_id in track_ids]
    if len(analyses) < 2:
        raise ValueError("need >=2 analyzed tracks to build a decision report")

    context = get_context_profile(context_id, cfg.context_profiles_file) if context_id else None
    available_contexts = _available_contexts(cfg)
    report_dir = Path(output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    analysis_summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "analysis_root": str(Path(processed_dir).resolve()),
        "track_count": len(analyses),
        "tracks": [
            {
                "track_id": analysis.track.track_id,
                "title": analysis.track.title,
                "artist": analysis.track.artist,
                "source_path": analysis.track.source_path,
                "json_path": str((Path(processed_dir) / f"{analysis.track.track_id}.json").resolve()),
            }
            for analysis in analyses
        ],
    }
    analysis_summary_path = _write_json(analysis_summary, report_dir / "analysis_summary.json")

    windows_by_track = {
        analysis.track.track_id: detect_transition_windows(
            TransitionWindowInput(
                track_id=analysis.track.track_id,
                segments=analysis.segments,
                feature_frames=analysis.features,
                beatgrid=analysis.beatgrid,
                context=context,
                available_contexts=available_contexts,
            ),
            weights.transition_window,
            top_k=cfg.analysis.transition_top_n,
        ).windows
        for analysis in analyses
    }

    pair_rows: list[dict[str, object]] = []
    edge_rows: list[dict[str, object]] = []
    edge_payload_rows: list[dict[str, object]] = []
    edge_review_rows: list[dict[str, object]] = []
    by_id = {analysis.track.track_id: analysis for analysis in analyses}
    for track_id_a, track_id_b in permutations(track_ids, 2):
        analysis_a = by_id[track_id_a]
        analysis_b = by_id[track_id_b]
        pair_id = _pair_id(track_id_a, track_id_b)
        mix = compute_mixability(
            MixabilityInput(
                track_a=analysis_a,
                track_b=analysis_b,
                context=context,
                transition_windows_a=windows_by_track[track_id_a],
                transition_windows_b=windows_by_track[track_id_b],
            ),
            weights.mixability,
            conflict_weights=weights.mixability_conflict,
        )
        edge = build_edge_decision(
            analysis_a,
            analysis_b,
            weights,
            context=context,
            transition_windows_a=windows_by_track[track_id_a],
            transition_windows_b=windows_by_track[track_id_b],
            mixability=mix,
            top_k=cfg.analysis.transition_top_n,
        )
        row = {
            "pair_id": pair_id,
            "track_a_id": track_id_a,
            "track_b_id": track_id_b,
            "track_a_title": analysis_a.track.title,
            "track_b_title": analysis_b.track.title,
            "mixability": mix.model_dump(mode="json"),
            "edge_decision": edge.model_dump(mode="json"),
        }
        pair_rows.append(row)
        edge_rows.append(edge.model_dump(mode="json"))
        edge_payload_rows.append(
            _build_edge_annotation_payload_row(
                pair_id,
                analysis_a,
                analysis_b,
                edge,
                context_id=context.context_id if context else None,
            )
        )
        edge_review_rows.append(
            _build_edge_review_row(
                pair_id,
                analysis_a,
                analysis_b,
                edge,
                context_id=context.context_id if context else None,
            )
        )

    pair_rows.sort(
        key=lambda row: (
            {
                "allow": 0,
                "review_only": 1,
                "suppress": 2,
            }.get(str(row["edge_decision"].get("recommendation_policy", "review_only")), 1),
            -float(row["edge_decision"]["core_dj_compatibility_score"]["value"]),
            -float(row["mixability"]["mixability_score"]),
            row["track_a_id"],
            row["track_b_id"],
        )
    )
    mixability_pairs_path = _write_json(pair_rows, report_dir / "mixability_pairs.json")
    edge_decisions_path = _write_json(edge_rows, report_dir / "edge_decisions.json")
    edge_payloads_path = _write_jsonl(
        edge_payload_rows,
        report_dir / "edge_decision_payloads.jsonl",
    )
    edge_review_path = _write_csv(
        edge_review_rows,
        report_dir / "edge_decision_review.csv",
        EDGE_REVIEW_FIELDS,
    )

    decision_manifest = DecisionTelemetryManifest(
        generated_at=datetime.now(UTC).isoformat(),
        analysis_root=str(Path(processed_dir).resolve()),
        report_root=str(report_dir.resolve()),
        context_id=context.context_id if context else None,
        track_count=len(analyses),
        ordered_pair_count=len(pair_rows),
        top_n_waveforms=min(top_n_waveforms, len(pair_rows)),
        artifacts={
            "analysis_summary": str(analysis_summary_path.resolve()),
            "mixability_pairs": str(mixability_pairs_path.resolve()),
            "edge_decisions": str(edge_decisions_path.resolve()),
            "edge_decision_payloads": str(edge_payloads_path.resolve()),
            "edge_decision_review": str(edge_review_path.resolve()),
        },
    )
    decision_summary_path = _write_json(
        decision_manifest.model_dump(mode="json"),
        report_dir / "decision_summary.json",
    )
    waveform_paths = render_mixability_waveform_gallery(
        report_dir,
        top_n=min(top_n_waveforms, len(pair_rows)),
    )
    decision_manifest = decision_manifest.model_copy(
        update={
            "artifacts": {
                **decision_manifest.artifacts,
                "waveform_overview": str(waveform_paths["overview"].resolve()),
                "waveform_index": str(waveform_paths["index"].resolve()),
            }
        }
    )
    decision_summary_path = _write_json(
        decision_manifest.model_dump(mode="json"),
        report_dir / "decision_summary.json",
    )

    return {
        "analysis_summary": analysis_summary_path,
        "mixability_pairs": mixability_pairs_path,
        "edge_decisions": edge_decisions_path,
        "edge_decision_payloads": edge_payloads_path,
        "edge_decision_review": edge_review_path,
        "decision_telemetry_manifest": decision_summary_path,
        "decision_summary": decision_summary_path,
        "waveform_overview": waveform_paths["overview"],
        "waveform_index": waveform_paths["index"],
    }
