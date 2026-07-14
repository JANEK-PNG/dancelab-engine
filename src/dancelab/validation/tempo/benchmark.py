"""Reproducible BPM and beat-grid benchmark using Rekordbox XML exports."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from dancelab.preprocessing.tempo_precision import refine_bpm_from_beat_times
from dancelab.validation.tempo.reference import (
    RekordboxTempoReference,
    TempoMarker,
    load_rekordbox_tempo_references,
    normalize_audio_path,
)

BENCHMARK_VERSION = "rekordbox-operational-tempo-v1"

_METRIC_RATIOS = {
    "1:2": 0.5,
    "2:3": 2.0 / 3.0,
    "3:4": 0.75,
    "4:5": 0.8,
    "1:1": 1.0,
    "5:4": 1.25,
    "4:3": 4.0 / 3.0,
    "3:2": 1.5,
    "2:1": 2.0,
}


def _round(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(float(value), digits)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalized_name(value: str) -> str:
    stem = Path(value).stem
    return re.sub(r"\s+", " ", stem).strip().casefold()


def _percent_error(estimate: float, reference: float) -> float:
    return abs(estimate - reference) / reference * 100.0


def _metric_relation(estimate: float, reference: float) -> str:
    ratio = reference / estimate
    label, expected = min(_METRIC_RATIOS.items(), key=lambda item: abs(ratio - item[1]))
    relative_distance = abs(ratio - expected) / expected
    return label if relative_distance <= 0.03 else "other"


def _marker_for_time(markers: Sequence[TempoMarker], time_sec: float) -> TempoMarker | None:
    if not markers:
        return None
    selected = markers[0]
    for marker in markers:
        if marker.time_sec > time_sec:
            break
        selected = marker
    return selected


def _reference_beat_position(marker: TempoMarker, time_sec: float) -> float:
    return (marker.beat_in_bar - 1) + (time_sec - marker.time_sec) * marker.bpm / 60.0


def _phase_audit(
    beat_times_sec: Sequence[float],
    markers: Sequence[TempoMarker],
) -> dict[str, Any]:
    beats = np.asarray(beat_times_sec, dtype=np.float64)
    beats = np.sort(beats[np.isfinite(beats)])
    if len(beats) == 0 or not markers:
        return {
            "sample_count": 0,
            "p50_error_beats": None,
            "p90_error_beats": None,
            "first_proxy_reference_beat": None,
            "first_proxy_is_downbeat": None,
        }

    errors: list[float] = []
    for beat_time in beats:
        marker = _marker_for_time(markers, float(beat_time))
        if marker is None:
            continue
        position = _reference_beat_position(marker, float(beat_time))
        errors.append(abs(position - round(position)))

    first_marker = _marker_for_time(markers, float(beats[0]))
    first_reference_beat: int | None = None
    if first_marker is not None:
        position = _reference_beat_position(first_marker, float(beats[0]))
        first_reference_beat = int(round(position)) % 4 + 1

    return {
        "sample_count": len(errors),
        "p50_error_beats": _round(float(np.quantile(errors, 0.5))) if errors else None,
        "p90_error_beats": _round(float(np.quantile(errors, 0.9))) if errors else None,
        "first_proxy_reference_beat": first_reference_beat,
        "first_proxy_is_downbeat": first_reference_beat == 1 if first_reference_beat else None,
    }


def _load_analyses(directory: Path) -> tuple[dict[str, Any], ...]:
    analyses: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(payload.get("track"), dict) and isinstance(payload.get("beatgrid"), dict):
            payload["_analysis_file"] = path.name
            analyses.append(payload)
    return tuple(analyses)


def _reference_indices(
    references: Sequence[RekordboxTempoReference],
) -> tuple[dict[str, RekordboxTempoReference], dict[str, list[RekordboxTempoReference]]]:
    by_path: dict[str, RekordboxTempoReference] = {}
    by_name: dict[str, list[RekordboxTempoReference]] = defaultdict(list)
    for reference in references:
        by_path[reference.source_path] = reference
        by_name[_normalized_name(Path(reference.source_path).name)].append(reference)
        by_name[_normalized_name(reference.title)].append(reference)
    return by_path, by_name


def _match_reference(
    analysis: dict[str, Any],
    by_path: dict[str, RekordboxTempoReference],
    by_name: dict[str, list[RekordboxTempoReference]],
) -> tuple[RekordboxTempoReference | None, str]:
    track = analysis["track"]
    source_path = track.get("source_path") or ""
    if source_path:
        exact = by_path.get(normalize_audio_path(source_path))
        if exact is not None:
            return exact, "exact_path"

    names = {
        _normalized_name(track.get("title") or ""),
        _normalized_name(Path(source_path).name) if source_path else "",
    }
    candidates: dict[str, RekordboxTempoReference] = {}
    for name in names - {""}:
        for candidate in by_name.get(name, []):
            candidates[candidate.track_id] = candidate
    if len(candidates) == 1:
        return next(iter(candidates.values())), "unique_name_fallback"
    return None, "unmatched"


def _benchmark_record(
    analysis: dict[str, Any],
    reference: RekordboxTempoReference,
    match_method: str,
) -> dict[str, Any]:
    track = analysis["track"]
    beatgrid = analysis["beatgrid"]
    raw_bpm = float(beatgrid["bpm"])
    refined = refine_bpm_from_beat_times(beatgrid.get("beat_times_sec", []), raw_bpm)
    refined_bpm = float(refined["bpm"])
    phase = _phase_audit(beatgrid.get("beat_times_sec", []), reference.tempo_markers)
    return {
        "track_id": str(track.get("track_id", "")),
        "title": str(track.get("title") or Path(track.get("source_path") or "").stem),
        "match_method": match_method,
        "reference_bpm": _round(reference.average_bpm),
        "raw_bpm": _round(raw_bpm),
        "raw_error_pct": _round(_percent_error(raw_bpm, reference.average_bpm)),
        "refined_bpm": _round(refined_bpm),
        "refined_error_pct": _round(_percent_error(refined_bpm, reference.average_bpm)),
        "refinement_accepted": bool(refined["accepted"]),
        "refinement_reason": refined["reason"],
        "refinement_robust_cv": _round(refined.get("robust_cv")),
        "metric_relation": _metric_relation(raw_bpm, reference.average_bpm),
        "phase": phase,
    }


def _error_metrics(records: Sequence[dict[str, Any]], field: str) -> dict[str, Any]:
    values = np.asarray([record[field] for record in records], dtype=np.float64)
    if len(values) == 0:
        return {"count": 0}
    return {
        "count": int(len(values)),
        "mean_pct": _round(float(np.mean(values))),
        "median_pct": _round(float(np.median(values))),
        "p90_pct": _round(float(np.quantile(values, 0.9))),
        "max_pct": _round(float(np.max(values))),
        "within_0_1_pct": int(np.sum(values <= 0.1)),
        "within_1_pct": int(np.sum(values <= 1.0)),
        "within_2_pct": int(np.sum(values <= 2.0)),
        "gross_over_2_pct": int(np.sum(values > 2.0)),
    }


def _scope_metrics(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    phase_records = [record for record in records if record["phase"]["sample_count"]]
    downbeat_records = [
        record for record in records
        if record["phase"]["first_proxy_is_downbeat"] is not None
    ]
    p90_values = [record["phase"]["p90_error_beats"] for record in phase_records]
    return {
        "count": len(records),
        "raw_bpm": _error_metrics(records, "raw_error_pct"),
        "refined_bpm": _error_metrics(records, "refined_error_pct"),
        "refinement_accepted": sum(record["refinement_accepted"] for record in records),
        "metric_relations": dict(sorted(Counter(
            record["metric_relation"] for record in records
        ).items())),
        "phase": {
            "count": len(phase_records),
            "median_p90_error_beats": _round(float(np.median(p90_values)))
            if p90_values else None,
            "p90_within_0_05_beat": sum(value <= 0.05 for value in p90_values),
            "proxy_downbeat_count": len(downbeat_records),
            "proxy_downbeat_correct": sum(
                record["phase"]["first_proxy_is_downbeat"] for record in downbeat_records
            ),
            "proxy_reference_beat_counts": dict(sorted(Counter(
                str(record["phase"]["first_proxy_reference_beat"])
                for record in downbeat_records
            ).items())),
        },
    }


def run_tempo_benchmark(
    analyses_dir: Path,
    rekordbox_xml: Sequence[Path],
) -> dict[str, Any]:
    analyses = _load_analyses(analyses_dir)
    references = tuple(
        reference
        for source in rekordbox_xml
        for reference in load_rekordbox_tempo_references(source)
    )
    by_path, by_name = _reference_indices(references)

    records: list[dict[str, Any]] = []
    match_counts: Counter[str] = Counter()
    for analysis in analyses:
        reference, method = _match_reference(analysis, by_path, by_name)
        match_counts[method] += 1
        if reference is not None:
            records.append(_benchmark_record(analysis, reference, method))
    records.sort(key=lambda item: (item["match_method"], item["track_id"]))

    exact = [record for record in records if record["match_method"] == "exact_path"]
    fallback = [record for record in records if record["match_method"] == "unique_name_fallback"]
    exact_metrics = _scope_metrics(exact)
    raw = exact_metrics["raw_bpm"]
    refined = exact_metrics["refined_bpm"]
    return {
        "schema_version": "1.0.0",
        "benchmark_version": BENCHMARK_VERSION,
        "reference_role": "operational_reference_not_scientific_ground_truth",
        "sources": [
            {"file_name": path.name, "sha256": _sha256(path)}
            for path in sorted(rekordbox_xml, key=lambda item: item.name)
        ],
        "inventory": {
            "analysis_count": len(analyses),
            "rekordbox_positive_bpm_count": len(references),
            "match_counts": dict(sorted(match_counts.items())),
        },
        "metrics": {
            "primary_exact_path": exact_metrics,
            "diagnostic_unique_name_fallback": _scope_metrics(fallback),
        },
        "gates": {
            "long_span_refinement_improves_median": (
                raw.get("count", 0) > 0
                and refined["median_pct"] < raw["median_pct"]
                and refined["p90_pct"] < raw["p90_pct"]
            ),
            "proxy_downbeats_safe_for_phrase_quantization": (
                exact_metrics["phase"]["proxy_downbeat_count"] > 0
                and exact_metrics["phase"]["proxy_downbeat_correct"]
                == exact_metrics["phase"]["proxy_downbeat_count"]
            ),
            "metric_level_autocorrection_validated": False,
            "engine_mutation_authorized_by_report": False,
        },
        "records": records,
    }


def write_tempo_benchmark(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "benchmark.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    columns = [
        "track_id", "title", "match_method", "reference_bpm", "raw_bpm",
        "raw_error_pct", "refined_bpm", "refined_error_pct", "refinement_accepted",
        "refinement_reason", "refinement_robust_cv", "metric_relation",
        "phase_p90_error_beats", "first_proxy_reference_beat",
        "first_proxy_is_downbeat",
    ]
    with (output_dir / "tracks.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for record in report["records"]:
            flat = {key: record.get(key) for key in columns}
            flat["phase_p90_error_beats"] = record["phase"]["p90_error_beats"]
            flat["first_proxy_reference_beat"] = record["phase"]["first_proxy_reference_beat"]
            flat["first_proxy_is_downbeat"] = record["phase"]["first_proxy_is_downbeat"]
            writer.writerow(flat)

    primary = report["metrics"]["primary_exact_path"]
    raw = primary["raw_bpm"]
    refined = primary["refined_bpm"]
    phase = primary["phase"]
    lines = [
        "# Tempo and beat-grid operational benchmark",
        "",
        "Rekordbox XML is used as a read-only operational reference, not scientific ground truth.",
        "Only exact-path matches are included in the primary metrics.",
        "",
        "## Coverage",
        "",
        f"- DanceLab analyses: {report['inventory']['analysis_count']}",
        f"- Exact-path matches: {primary['count']}",
        f"- Unique-name fallback matches (diagnostic only): "
        f"{report['metrics']['diagnostic_unique_name_fallback']['count']}",
        "",
        "## BPM precision",
        "",
        f"- Raw median / p90 error: {raw.get('median_pct')}% / {raw.get('p90_pct')}%",
        f"- 32-beat refined median / p90 error: "
        f"{refined.get('median_pct')}% / {refined.get('p90_pct')}%",
        f"- Gross metric-level errors above 2% remain: {refined.get('gross_over_2_pct')}",
        "",
        "## Grid phase",
        "",
        f"- Median per-track p90 phase error: {phase['median_p90_error_beats']} beat",
        f"- Tracks with p90 phase error <= 0.05 beat: "
        f"{phase['p90_within_0_05_beat']} / {phase['count']}",
        f"- First tracked beat is a true downbeat: "
        f"{phase['proxy_downbeat_correct']} / {phase['proxy_downbeat_count']}",
        "",
        "## Decision gates",
        "",
        f"- Long-span BPM precision candidate: "
        f"{'PASS' if report['gates']['long_span_refinement_improves_median'] else 'FAIL'}",
        "- Proxy downbeats for 8/16/32-beat phrase claims: "
        f"{'PASS' if report['gates']['proxy_downbeats_safe_for_phrase_quantization'] else 'FAIL'}",
        "- Automatic 3:2 / 4:3 / 5:4 metric correction: NOT VALIDATED",
        "- This report mutates engine weights or Rekordbox data: NO",
        "",
    ]
    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
