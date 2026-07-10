"""Build a practical validation pack for the current analyzed corpus.

The pack is intentionally bounded:
- validates the shipped annotation contracts,
- filters review sheets down to the active processed corpus,
- reports completion coverage honestly,
- computes metrics only where manual labels already exist.
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from dancelab.contracts.telemetry import DecisionTelemetryManifest
from dancelab.data.annotation_loader import (
    load_context_profiles,
    load_mixability_pairs,
    load_set_function_labels,
    load_track_metadata,
    load_transition_windows,
)
from dancelab.data.annotation_validator import validate_annotation_dataset
from dancelab.storage.repositories import FileAnalysisRepository
from dancelab.validation.dj_decision_metrics import (
    cohen_kappa,
    false_positive_rate,
    kendall_tau,
    mean_overlap,
    rating_correlation,
    spearman_rho,
    top_k_hit,
)
from dancelab.validation.review_ui import build_swipe_review_bundle


class ValidationPackSummary(BaseModel):
    generated_at: str
    processed_dir: str
    annotations_dir: str
    report_dir: str | None = None
    analyzed_track_count: int = Field(ge=0)
    annotation_valid: bool
    annotation_counts: dict[str, int] = Field(default_factory=dict)
    subset_counts: dict[str, int] = Field(default_factory=dict)
    overlap: dict[str, int | float] = Field(default_factory=dict)
    completion: dict[str, float] = Field(default_factory=dict)
    metrics: dict[str, dict[str, object]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)


def _read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write_csv_rows(
    rows: list[dict[str, object]],
    path: str | Path,
    fieldnames: list[str],
) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            payload: dict[str, object] = {}
            for field in fieldnames:
                value = row.get(field, "")
                if isinstance(value, list):
                    value = ";".join(str(item) for item in value)
                elif value is None:
                    value = ""
                payload[field] = value
            writer.writerow(payload)
    return out


def _write_json(data: object, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, sort_keys=False))
    return out


def _safe_fraction(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _parse_mmss_range(value: str | None) -> tuple[float, float] | None:
    raw = (value or "").strip()
    if not raw or "-" not in raw:
        return None
    left, right = raw.split("-", 1)
    return _parse_mmss(left), _parse_mmss(right)


def _parse_mmss(value: str) -> float:
    minutes, seconds = value.strip().split(":", 1)
    return float(int(minutes) * 60 + int(seconds))


def _filter_rows_by_track(rows: list[dict[str, str]], track_ids: set[str], key: str = "track_id") -> list[dict[str, str]]:
    return [row for row in rows if row.get(key, "") in track_ids]


def _build_transition_window_metrics(rows: list[dict[str, str]]) -> tuple[dict[str, object], list[str]]:
    warnings: list[str] = []
    by_track: dict[str, dict[str, list]] = {}
    verdict_rows = 0
    good_verdict_rows = 0
    for row in rows:
        track_id = row.get("track_id", "").strip()
        if not track_id:
            continue
        bucket = by_track.setdefault(track_id, {"engine": [], "manual": []})
        engine_window = _parse_mmss_range(row.get("engine_window(mm:ss)"))
        if engine_window is not None:
            bucket["engine"].append(engine_window)
        manual_window = _parse_mmss_range(row.get("dj_own_window(mm:ss-mm:ss)"))
        if manual_window is not None:
            bucket["manual"].append(manual_window)
        verdict = row.get("dj_verdict(good/bad)", "").strip().lower()
        if verdict:
            verdict_rows += 1
            if verdict == "good":
                good_verdict_rows += 1

    reviewed = [
        (track_id, data)
        for track_id, data in by_track.items()
        if data["engine"] and data["manual"]
    ]
    metrics: dict[str, object] = {
        "review_track_count": len(reviewed),
        "track_count": len(by_track),
        "row_count": len(rows),
        "verdict_row_count": verdict_rows,
        "good_verdict_ratio": _safe_fraction(good_verdict_rows, verdict_rows),
    }
    if not reviewed:
        warnings.append("no completed DJ own-window labels in exp009 review sheet")
        return metrics, warnings

    top1 = []
    top3 = []
    overlaps = []
    fprs = []
    for _, data in reviewed:
        engine = data["engine"]
        manual = data["manual"]
        top1.append(1.0 if top_k_hit(engine, manual, k=1) else 0.0)
        top3.append(1.0 if top_k_hit(engine, manual, k=3) else 0.0)
        overlaps.append(mean_overlap(engine[:3], manual))
        fpr = false_positive_rate(engine[:3], manual)
        if fpr is not None:  # AUD-L11: skip undefined (no engine windows) cases
            fprs.append(fpr)

    metrics.update(
        {
            "top1_hit_rate": round(sum(top1) / len(top1), 4),
            "top3_hit_rate": round(sum(top3) / len(top3), 4),
            "mean_overlap_iou": round(sum(overlaps) / len(overlaps), 4),
            "false_positive_rate": round(sum(fprs) / len(fprs), 4) if fprs else None,
        }
    )
    return metrics, warnings


def _build_set_function_metrics(rows: list[dict[str, str]]) -> tuple[dict[str, object], list[str]]:
    warnings: list[str] = []
    labeled = [row for row in rows if row.get("dj_primary", "").strip()]
    metrics: dict[str, object] = {
        "track_count": len(rows),
        "labeled_track_count": len(labeled),
    }
    if not labeled:
        warnings.append("no completed DJ set-function labels in exp011 review sheet")
        return metrics, warnings

    engine = [row.get("engine_primary", "").strip() for row in labeled]
    dj = [row.get("dj_primary", "").strip() for row in labeled]
    matches = sum(1 for lhs, rhs in zip(engine, dj) if lhs == rhs)
    metrics.update(
        {
            "exact_match_rate": _safe_fraction(matches, len(labeled)),
            "cohen_kappa": cohen_kappa(engine, dj),
        }
    )
    return metrics, warnings


def _build_mixability_metrics(rows: list[dict[str, str]]) -> tuple[dict[str, object], list[str]]:
    warnings: list[str] = []
    rated = [
        row for row in rows
        if row.get("dj_mixability_rating", "").strip()
        and row.get("engine_score", "").strip()
    ]
    metrics: dict[str, object] = {
        "pair_count": len(rows),
        "rated_pair_count": len(rated),
    }
    if len(rated) < 3:
        warnings.append("fewer than 3 rated pair-review rows with engine scores")
        return metrics, warnings

    engine_scores = [float(row["engine_score"]) for row in rated]
    dj_scores = [float(row["dj_mixability_rating"]) for row in rated]
    metrics.update(
        {
            "pearson_r": rating_correlation(engine_scores, dj_scores),
            "spearman_rho": spearman_rho(engine_scores, dj_scores),
            "kendall_tau": kendall_tau(engine_scores, dj_scores),
        }
    )
    return metrics, warnings


def _write_markdown(summary: ValidationPackSummary, path: str | Path) -> Path:
    lines = [
        "# Validation Pack Summary",
        "",
        f"- generated_at: {summary.generated_at}",
        f"- processed_dir: {summary.processed_dir}",
        f"- annotations_dir: {summary.annotations_dir}",
        f"- analyzed_track_count: {summary.analyzed_track_count}",
        f"- annotation_valid: {summary.annotation_valid}",
        "",
        "## Overlap",
        "",
    ]
    for key, value in summary.overlap.items():
        lines.append(f"- {key}: {value}")
    lines += [
        "",
        "## Completion",
        "",
    ]
    for key, value in summary.completion.items():
        lines.append(f"- {key}: {value}")
    lines += [
        "",
        "## Metrics",
        "",
    ]
    for section, payload in summary.metrics.items():
        lines.append(f"### {section}")
        lines.append("")
        for key, value in payload.items():
            lines.append(f"- {key}: {value}")
        lines.append("")
    if summary.warnings:
        lines += [
            "## Warnings",
            "",
        ]
        for warning in summary.warnings:
            lines.append(f"- {warning}")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    return out


def _load_decision_manifest(report_dir: str | Path | None) -> DecisionTelemetryManifest | None:
    if report_dir is None:
        return None
    manifest_path = Path(report_dir) / "decision_summary.json"
    if not manifest_path.exists():
        return None
    return DecisionTelemetryManifest.model_validate_json(manifest_path.read_text())


def build_validation_pack(
    processed_dir: str | Path,
    output_dir: str | Path,
    *,
    annotations_dir: str | Path = "data/annotations",
    report_dir: str | Path | None = None,
) -> dict[str, Path]:
    repo = FileAnalysisRepository(processed_dir)
    analyzed_track_ids = repo.list_track_ids()
    if not analyzed_track_ids:
        raise ValueError("need >=1 analyzed track to build a validation pack")

    processed_dir = Path(processed_dir)
    annotations_dir = Path(annotations_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    track_id_set = set(analyzed_track_ids)

    dataset_report = validate_annotation_dataset(annotations_dir)
    track_metadata = load_track_metadata(annotations_dir / "track_metadata.csv")
    transition_windows = load_transition_windows(annotations_dir / "transition_window_annotations.csv")
    mixability_pairs = load_mixability_pairs(annotations_dir / "mixability_pair_annotations.csv")
    set_function_labels = load_set_function_labels(annotations_dir / "set_function_labels.csv")
    contexts = load_context_profiles(annotations_dir / "context_profiles.csv")

    track_rows = [row.model_dump(mode="json") for row in track_metadata if row.track_id in track_id_set]
    window_rows = [row.model_dump(mode="json") for row in transition_windows if row.track_id in track_id_set]
    pair_rows = [
        row.model_dump(mode="json")
        for row in mixability_pairs
        if row.track_id_a in track_id_set and row.track_id_b in track_id_set
    ]
    set_rows = [row.model_dump(mode="json") for row in set_function_labels if row.track_id in track_id_set]
    context_rows = [row.model_dump(mode="json") for row in contexts]

    exp009_rows = _filter_rows_by_track(
        _read_csv_rows(annotations_dir / "exp009_dj_window_review.csv"),
        track_id_set,
    )
    exp011_rows = _filter_rows_by_track(
        _read_csv_rows(annotations_dir / "exp011_set_function_review.csv"),
        track_id_set,
    )
    annotation_sheet_rows = _filter_rows_by_track(
        _read_csv_rows(annotations_dir / "annotation_sheet.csv"),
        track_id_set,
    )

    artifacts: dict[str, Path] = {}
    decision_manifest = _load_decision_manifest(report_dir)
    artifacts["track_metadata_subset"] = _write_csv_rows(
        track_rows,
        output_dir / "track_metadata_subset.csv",
        ["track_id", "title", "artist", "duration_sec", "bpm", "style", "key", "source"],
    )
    artifacts["transition_window_annotations_subset"] = _write_csv_rows(
        window_rows,
        output_dir / "transition_window_annotations_subset.csv",
        ["window_id", "track_id", "window_type", "start_sec", "end_sec", "dj_rating", "engine_candidate", "reason_good", "risk_notes"],
    )
    artifacts["mixability_pair_annotations_subset"] = _write_csv_rows(
        pair_rows,
        output_dir / "mixability_pair_annotations_subset.csv",
        ["pair_id", "track_id_a", "track_id_b", "window_a_id", "window_b_id", "dj_mixability_rating", "tempo_fit_rating", "phrase_fit_rating", "bass_conflict_rating", "vocal_conflict_rating", "tension_fit_rating", "comment"],
    )
    artifacts["set_function_labels_subset"] = _write_csv_rows(
        set_rows,
        output_dir / "set_function_labels_subset.csv",
        ["track_id", "context_profile_id", "primary_function", "secondary_functions", "dj_confidence", "reasoning", "risk_notes"],
    )
    artifacts["context_profiles"] = _write_csv_rows(
        context_rows,
        output_dir / "context_profiles.csv",
        ["context_profile_id", "venue_type", "set_role", "time_of_night", "crowd_energy", "style_focus"],
    )
    if exp009_rows:
        artifacts["exp009_window_review_subset"] = _write_csv_rows(
            exp009_rows,
            output_dir / "exp009_dj_window_review_subset.csv",
            list(exp009_rows[0].keys()),
        )
    if exp011_rows:
        artifacts["exp011_set_function_review_subset"] = _write_csv_rows(
            exp011_rows,
            output_dir / "exp011_set_function_review_subset.csv",
            list(exp011_rows[0].keys()),
        )
    if annotation_sheet_rows:
        artifacts["annotation_sheet_subset"] = _write_csv_rows(
            annotation_sheet_rows,
            output_dir / "annotation_sheet_subset.csv",
            list(annotation_sheet_rows[0].keys()),
        )

    metrics: dict[str, dict[str, object]] = {}
    warnings = list(dataset_report.warnings)

    tw_metrics, tw_warnings = _build_transition_window_metrics(exp009_rows)
    metrics["transition_windows"] = tw_metrics
    warnings.extend(tw_warnings)

    sf_metrics, sf_warnings = _build_set_function_metrics(exp011_rows)
    metrics["set_function"] = sf_metrics
    warnings.extend(sf_warnings)

    pair_review_rows: list[dict[str, str]] = []
    resolved_report_dir = str(Path(report_dir).resolve()) if report_dir else None
    if report_dir:
        pair_review_path = (
            Path(decision_manifest.artifacts["edge_decision_review"])
            if decision_manifest and "edge_decision_review" in decision_manifest.artifacts
            else Path(report_dir) / "edge_decision_review.csv"
        )
        pair_review_rows = _read_csv_rows(pair_review_path)
        if pair_review_rows:
            artifacts["edge_decision_review"] = Path(pair_review_path)
            mix_metrics, mix_warnings = _build_mixability_metrics(pair_review_rows)
            metrics["mixability_pairs"] = mix_metrics
            warnings.extend(mix_warnings)
        else:
            metrics["mixability_pairs"] = {"pair_count": 0, "rated_pair_count": 0}
            warnings.append("edge_decision_review.csv missing or empty — pair rating metrics unavailable")
    else:
        metrics["mixability_pairs"] = {"pair_count": 0, "rated_pair_count": 0}
        warnings.append("no report_dir provided — pair rating metrics unavailable")

    reviewed_tw_tracks = len(
        {
            row.get("track_id", "").strip()
            for row in exp009_rows
            if row.get("dj_own_window(mm:ss-mm:ss)", "").strip()
        }
    )
    reviewed_sf_tracks = sum(1 for row in exp011_rows if row.get("dj_primary", "").strip())
    rated_pair_rows = sum(1 for row in pair_review_rows if row.get("dj_mixability_rating", "").strip())

    overlap_track_ids = {row.track_id for row in track_metadata if row.track_id in track_id_set}
    summary = ValidationPackSummary(
        generated_at=datetime.now(UTC).isoformat(),
        processed_dir=str(processed_dir.resolve()),
        annotations_dir=str(annotations_dir.resolve()),
        report_dir=resolved_report_dir,
        analyzed_track_count=len(analyzed_track_ids),
        annotation_valid=dataset_report.valid,
        annotation_counts=dataset_report.counts,
        subset_counts={
            "track_metadata": len(track_rows),
            "transition_windows": len(window_rows),
            "mixability_pairs": len(pair_rows),
            "set_function_labels": len(set_rows),
            "exp009_window_review_rows": len(exp009_rows),
            "exp011_set_function_review_rows": len(exp011_rows),
            "annotation_sheet_rows": len(annotation_sheet_rows),
        },
        overlap={
            "annotated_track_overlap_count": len(overlap_track_ids),
            "annotated_track_overlap_ratio": _safe_fraction(len(overlap_track_ids), len(track_id_set)),
        },
        completion={
            "exp009_reviewed_track_ratio": _safe_fraction(reviewed_tw_tracks, len(track_id_set)),
            "exp011_labeled_track_ratio": _safe_fraction(reviewed_sf_tracks, len(exp011_rows)),
            "pair_review_rated_row_ratio": _safe_fraction(rated_pair_rows, len(pair_review_rows)),
        },
        metrics=metrics,
        warnings=warnings,
        artifacts={key: str(path.resolve()) for key, path in artifacts.items()},
    )

    summary_json = _write_json(summary.model_dump(mode="json"), output_dir / "validation_pack_summary.json")
    summary_md = _write_markdown(summary, output_dir / "validation_pack_summary.md")
    swipe_paths = build_swipe_review_bundle(
        output_dir,
        report_dir=report_dir,
    )
    return {
        "summary_json": summary_json,
        "summary_md": summary_md,
        **swipe_paths,
        **artifacts,
    }
