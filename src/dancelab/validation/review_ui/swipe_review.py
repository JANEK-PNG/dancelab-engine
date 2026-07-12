"""Static swipe-style review UIs for pilot validation work.

This module is validation-only. It is intentionally kept outside the core
engine/visualization path so review tooling can evolve without changing
scoring, recommendation, or planning behavior.
"""

from __future__ import annotations

from collections import Counter
import csv
import json
import os
import re
from math import sqrt
from pathlib import Path

from dancelab.contracts.telemetry import DecisionTelemetryManifest
from dancelab.host.preview_timing import (
    GRID_QUANTIZE_BEATS,
    PREVIEW_LEAD_BEATS,
    quantized_cue_and_start,
)


def _read_csv_rows(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    p = Path(path)
    if not p.exists():
        return [], []
    with p.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def _read_json(path: str | Path) -> object | None:
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def _write_text(path: str | Path, content: str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content)
    return out


def _relative_href(path: str | Path | None, *, output_dir: Path) -> str | None:
    if path is None:
        return None
    candidate = Path(path)
    if not candidate.exists():
        return None
    return os.path.relpath(candidate, output_dir)


def _load_decision_manifest(report_dir: str | Path | None) -> DecisionTelemetryManifest | None:
    if report_dir is None:
        return None
    manifest_path = Path(report_dir) / "decision_summary.json"
    if not manifest_path.exists():
        return None
    return DecisionTelemetryManifest.model_validate_json(manifest_path.read_text())


def _average(values: list[float]) -> float:
    filtered = [float(value) for value in values]
    if not filtered:
        return 0.0
    return sum(filtered) / len(filtered)


def _safe_fraction(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _edge_pair_id(edge: dict[str, object]) -> str:
    payload = edge.get("annotation_payload")
    if isinstance(payload, dict):
        pair_id = str(payload.get("pair_id", "")).strip()
        if pair_id:
            return pair_id
    return f"{edge.get('track_id_a', '')}__{edge.get('track_id_b', '')}"


def _count_entries(values: list[str], *, limit: int = 8) -> list[dict[str, object]]:
    counts = Counter(value for value in values if value)
    rows = [
        {"label": label.replace("_", " "), "count": count}
        for label, count in counts.most_common(limit)
    ]
    return rows


def _edge_risk_value(edge: dict[str, object]) -> float:
    return max(
        _float(edge.get("bass_conflict_risk"), 0.0),
        _float(edge.get("vocal_clash_risk"), 0.0),
        _float(edge.get("harmonic_risk"), 0.0),
        1.0 if bool(edge.get("hard_block")) else 0.0,
    )


def _build_control_center_snapshot(
    *,
    validation_summary: object | None,
    decision_summary: object | None,
    edge_decisions: object | None,
    mixability_pairs: object | None,
    analysis_summary: object | None,
) -> dict[str, object]:
    validation = validation_summary if isinstance(validation_summary, dict) else {}
    decision = decision_summary if isinstance(decision_summary, dict) else {}
    edges = edge_decisions if isinstance(edge_decisions, list) else []
    pairs = mixability_pairs if isinstance(mixability_pairs, list) else []
    analysis = analysis_summary if isinstance(analysis_summary, dict) else {}

    titles_by_pair: dict[str, str] = {}
    for row in pairs:
        if not isinstance(row, dict):
            continue
        pair_id = str(row.get("pair_id", "")).strip()
        if not pair_id:
            continue
        title_a = row.get("track_a_title") or row.get("track_a_id") or "Track A"
        title_b = row.get("track_b_title") or row.get("track_b_id") or "Track B"
        titles_by_pair[pair_id] = f"{title_a} -> {title_b}"

    sensor_pairs: list[dict[str, object]] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        pair_id = _edge_pair_id(edge)
        title = titles_by_pair.get(
            pair_id,
            f"{edge.get('track_id_a', 'Track A')} -> {edge.get('track_id_b', 'Track B')}",
        )
        score_payload = edge.get("core_dj_compatibility_score")
        score = _float(
            score_payload.get("value") if isinstance(score_payload, dict) else score_payload,
            0.0,
        )
        confidence = _float(
            score_payload.get("confidence") if isinstance(score_payload, dict) else 0.0,
            0.0,
        )
        sensor_pairs.append(
            {
                "pair_id": pair_id,
                "title": title,
                "score": round(score, 4),
                "confidence": round(confidence, 4),
                "risk": round(_edge_risk_value(edge), 4),
                "profile": str(edge.get("blend_profile_auto", "") or "plain_blend"),
                "strategy": str(edge.get("recommended_transition_strategy", "") or "n/a"),
                "decision_class": str(edge.get("decision_class", "") or "unknown"),
                "tempo_feasibility": str(edge.get("tempo_window_feasibility", "") or "unknown"),
                "tempo_relation": str(edge.get("tempo_relation", "") or "unknown"),
                "standard_blend_allowed": bool(edge.get("standard_blend_allowed")),
                "hard_block": bool(edge.get("hard_block")),
                "bass_risk": round(_float(edge.get("bass_conflict_risk"), 0.0), 4),
                "vocal_risk": round(_float(edge.get("vocal_clash_risk"), 0.0), 4),
                "harmonic_risk": round(_float(edge.get("harmonic_risk"), 0.0), 4),
                "risks": list(edge.get("risks") or []),
                "warnings": list(edge.get("warnings") or []),
            }
        )

    scores = [float(item["score"]) for item in sensor_pairs]
    confidences = [float(item["confidence"]) for item in sensor_pairs]
    risks = [float(item["risk"]) for item in sensor_pairs]
    bass_risks = [float(item["bass_risk"]) for item in sensor_pairs]
    vocal_risks = [float(item["vocal_risk"]) for item in sensor_pairs]
    harmonic_risks = [float(item["harmonic_risk"]) for item in sensor_pairs]

    alert_terms = _count_entries(
        [
            *(term for item in sensor_pairs for term in item["risks"]),
            *(term for item in sensor_pairs for term in item["warnings"]),
            *(str(term) for term in validation.get("warnings", [])),
        ],
        limit=10,
    )
    top_pairs = sorted(
        sensor_pairs,
        key=lambda item: (
            -float(item["score"]),
            -float(item["confidence"]),
            float(item["risk"]),
        ),
    )[:8]
    watch_pairs = sorted(
        sensor_pairs,
        key=lambda item: (
            not bool(item["hard_block"]),
            -float(item["risk"]),
            float(item["score"]),
        ),
    )[:8]

    return {
        "track_count": int(
            validation.get("analyzed_track_count")
            or decision.get("track_count")
            or analysis.get("track_count")
            or 0
        ),
        "pair_count": int(decision.get("ordered_pair_count") or len(sensor_pairs)),
        "rated_pair_count": int(
            ((validation.get("metrics") or {}).get("mixability_pairs") or {}).get("rated_pair_count", 0)
        ),
        "rated_pair_ratio": round(
            _safe_fraction(
                int(((validation.get("metrics") or {}).get("mixability_pairs") or {}).get("rated_pair_count", 0)),
                int(decision.get("ordered_pair_count") or len(sensor_pairs) or 0),
            ),
            4,
        ),
        "window_review_ratio": round(
            _float(((validation.get("completion") or {}).get("exp009_reviewed_track_ratio")), 0.0),
            4,
        ),
        "set_function_ratio": round(
            _float(((validation.get("completion") or {}).get("exp011_labeled_track_ratio")), 0.0),
            4,
        ),
        "pair_review_ratio": round(
            _float(((validation.get("completion") or {}).get("pair_review_rated_row_ratio")), 0.0),
            4,
        ),
        "mean_score": round(_average(scores), 4),
        "mean_confidence": round(_average(confidences), 4),
        "mean_risk": round(_average(risks), 4),
        "mean_bass_risk": round(_average(bass_risks), 4),
        "mean_vocal_risk": round(_average(vocal_risks), 4),
        "mean_harmonic_risk": round(_average(harmonic_risks), 4),
        "standard_blend_ratio": round(
            _safe_fraction(
                sum(1 for item in sensor_pairs if bool(item["standard_blend_allowed"])),
                len(sensor_pairs),
            ),
            4,
        ),
        "hard_block_count": sum(1 for item in sensor_pairs if bool(item["hard_block"])),
        "decision_counts": _count_entries(
            [str(item["decision_class"]) for item in sensor_pairs],
            limit=8,
        ),
        "policy_counts": _count_entries(
            [
                str(edge.get("recommendation_policy", "") or "review_only")
                for edge in edges
                if isinstance(edge, dict)
            ],
            limit=8,
        ),
        "blend_profile_counts": _count_entries(
            [str(item["profile"]) for item in sensor_pairs],
            limit=8,
        ),
        "strategy_counts": _count_entries(
            [str(item["strategy"]) for item in sensor_pairs],
            limit=8,
        ),
        "tempo_feasibility_counts": _count_entries(
            [str(item["tempo_feasibility"]) for item in sensor_pairs],
            limit=8,
        ),
        "tempo_relation_counts": _count_entries(
            [str(item["tempo_relation"]) for item in sensor_pairs],
            limit=8,
        ),
        "alert_terms": alert_terms,
        "top_pairs": top_pairs,
        "watch_pairs": watch_pairs,
        "scatter_points": sensor_pairs[:120],
        "times": {
            "validation_generated_at": str(validation.get("generated_at", "")),
            "decision_generated_at": str(decision.get("generated_at", "")),
            "analysis_generated_at": str(analysis.get("generated_at", "")),
        },
        "sources_available": {
            "validation": bool(validation),
            "decision": bool(decision),
            "edges": bool(edges),
            "pairs": bool(pairs),
            "analysis": bool(analysis),
        },
        "artifact_links": {
            "launcher": "index.html",
            "pair_deck": "pairs.html",
            "listen_board": "listen_board.html",
            "window_deck": "windows.html",
            "set_function_deck": "set_function.html",
        },
        "warnings": list(validation.get("warnings", []))[:8],
    }


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "review"


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return default


def _parse_time_seconds(value: str) -> float | None:
    raw = value.strip()
    if not raw:
        return None
    parts = raw.split(":")
    if not 1 <= len(parts) <= 3:
        return None
    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        return None
    if len(numbers) == 1:
        return numbers[0]
    if len(numbers) == 2:
        minutes, seconds = numbers
        return (minutes * 60.0) + seconds
    hours, minutes, seconds = numbers
    return (hours * 3600.0) + (minutes * 60.0) + seconds


def _parse_window_spec(value: str) -> tuple[float | None, float | None]:
    raw = value.strip()
    if not raw:
        return None, None
    start_raw, dash, end_raw = raw.partition("-")
    start = _parse_time_seconds(start_raw)
    end = _parse_time_seconds(end_raw) if dash else None
    return start, end


def _resolve_media_path(source_path: str, *, repo_root: Path, output_dir: Path) -> str | None:
    raw = source_path.strip()
    if not raw:
        return None
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        resolved = candidate
    else:
        resolved = repo_root / candidate
        if not resolved.exists():
            resolved = (output_dir / candidate).resolve()
    if not resolved.exists():
        return None
    return os.path.relpath(resolved, output_dir)


_PREVIEW_SYNC_TOLERANCE = 0.08
_PREVIEW_LEAD_IN_SEC = 8.0
_PREVIEW_MIN_DURATION_SEC = 18
_PREVIEW_MAX_DURATION_SEC = 32


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _preview_duration_seconds(window_a: str, window_b: str) -> int:
    start_a, end_a = _parse_window_spec(window_a)
    start_b, end_b = _parse_window_spec(window_b)
    active_window = max(
        (end_a or 0.0) - (start_a or 0.0),
        (end_b or 0.0) - (start_b or 0.0),
        8.0,
    )
    duration = _PREVIEW_LEAD_IN_SEC + active_window + 8.0
    return int(max(_PREVIEW_MIN_DURATION_SEC, min(_PREVIEW_MAX_DURATION_SEC, duration)))


def _load_processed_preview_meta(
    track_id: str,
    *,
    processed_dir: Path | None,
    cache: dict[str, dict[str, object]],
) -> dict[str, object]:
    if track_id in cache:
        return cache[track_id]
    if processed_dir is None or not track_id:
        cache[track_id] = {}
        return cache[track_id]
    path = processed_dir / f"{track_id}.json"
    if not path.exists():
        cache[track_id] = {}
        return cache[track_id]
    try:
        payload = json.loads(path.read_text())
    except Exception:
        cache[track_id] = {}
        return cache[track_id]
    beatgrid = payload.get("beatgrid") or {}
    beat_times = beatgrid.get("beat_times_sec") or []
    downbeats = beatgrid.get("downbeats_sec") or []
    cache[track_id] = {
        "bpm": _float(beatgrid.get("bpm"), 0.0) or None,
        "beat_times_sec": [float(value) for value in beat_times],
        "downbeats_sec": [float(value) for value in downbeats],
    }
    return cache[track_id]


def _format_timecode(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    total = max(float(seconds), 0.0)
    minutes = int(total // 60)
    remainder = total - (minutes * 60)
    return f"{minutes}:{remainder:05.2f}"


def _suggest_listen_blend(row: dict[str, str]) -> tuple[str, str]:
    engine_profile = (row.get("engine_blend_profile_auto", "") or "").strip()
    engine_explanation = (row.get("engine_blend_profile_explanation", "") or "").strip()
    if engine_profile in {"plain_blend", "bass_swap", "tops_swap", "contour_blend"}:
        if engine_explanation:
            return engine_profile, engine_explanation
        return (
            engine_profile,
            f"Auto mode from engine selects {engine_profile.replace('_', ' ')} for this pair.",
        )

    bass_risk = _float(row.get("engine_bass_conflict_risk"), 0.0)
    vocal_risk = _float(row.get("engine_vocal_clash_risk"), 0.0)
    strategy = row.get("engine_strategy", "") or "n/a"
    if bass_risk >= 0.45:
        return (
            "bass_swap",
            f"Suggested by engine: bass conflict {bass_risk:.2f} favors a deliberate low-end handoff.",
        )
    if vocal_risk >= 0.22:
        return (
            "contour_blend",
            f"Suggested by engine: vocal/mid exposure {vocal_risk:.2f} favors a shaped contour blend.",
        )
    if strategy in {"short_blend", "phrase_aligned_blend"}:
        return (
            "tops_swap",
            f"Suggested by engine: strategy {strategy.replace('_', ' ')} fits an early tops swap.",
        )
    return ("plain_blend", f"Suggested by engine: strategy {strategy.replace('_', ' ')} is close to a controlled plain blend.")


def _build_pair_preview_data(
    row: dict[str, str],
    *,
    repo_root: Path,
    output_dir: Path,
    processed_dir: Path | None,
    processed_cache: dict[str, dict[str, object]],
) -> dict[str, object]:
    track_id_a = row.get("track_id_a", "")
    track_id_b = row.get("track_id_b", "")
    window_a = row.get("engine_pair_window_a(mm:ss)", "")
    window_b = row.get("engine_pair_window_b(mm:ss)", "")
    cue_a_sec, _ = _parse_window_spec(window_a)
    cue_b_sec, _ = _parse_window_spec(window_b)
    meta_a = _load_processed_preview_meta(track_id_a, processed_dir=processed_dir, cache=processed_cache)
    meta_b = _load_processed_preview_meta(track_id_b, processed_dir=processed_dir, cache=processed_cache)
    beat_times_a = list(meta_a.get("beat_times_sec") or [])
    beat_times_b = list(meta_b.get("beat_times_sec") or [])
    downbeats_a = list(meta_a.get("downbeats_sec") or [])
    downbeats_b = list(meta_b.get("downbeats_sec") or [])

    preview_cue_a = cue_a_sec or 0.0
    preview_cue_b = cue_b_sec or 0.0
    preview_start_a = max(preview_cue_a - _PREVIEW_LEAD_IN_SEC, 0.0)
    preview_start_b = max(preview_cue_b - _PREVIEW_LEAD_IN_SEC, 0.0)
    quantize_status = "fallback"
    quantize_label = "fallback"
    quantize_note = "8-beat grid quantize unavailable, so preview falls back to second-based cueing."
    quantize_lead_beats = 0

    if beat_times_a and beat_times_b:
        preview_cue_a, preview_start_a, lead_a = quantized_cue_and_start(
            preview_cue_a,
            beat_times_a,
            downbeats_a,
            lead_beats=PREVIEW_LEAD_BEATS,
            grid_beats=GRID_QUANTIZE_BEATS,
        )
        preview_cue_b, preview_start_b, lead_b = quantized_cue_and_start(
            preview_cue_b,
            beat_times_b,
            downbeats_b,
            lead_beats=PREVIEW_LEAD_BEATS,
            grid_beats=GRID_QUANTIZE_BEATS,
        )
        quantize_lead_beats = min(lead_a, lead_b)
        quantize_status = "grid"
        if quantize_lead_beats > 0:
            quantize_label = f"8-beat grid -{quantize_lead_beats} beats"
            quantize_note = (
                f"Quantize snaps cue points and preview starts to {GRID_QUANTIZE_BEATS}-beat "
                f"grid boundaries; preview starts {quantize_lead_beats} beats before the "
                "transition point when enough lead-in exists."
            )
        else:
            quantize_label = "8-beat grid cue"
            quantize_note = (
                f"Quantize snaps cue points to {GRID_QUANTIZE_BEATS}-beat grid boundaries; "
                "preview starts at the cue because one deck has no earlier 8-beat lead-in."
            )

    bpm_a = meta_a.get("bpm")
    bpm_b = meta_b.get("bpm")
    tempo_relation = row.get("engine_tempo_relation", "unknown") or "unknown"
    sync_status = "raw"
    sync_label = "raw"
    sync_note = "Auto beat sync is off for this pair."
    sync_target_bpm = None
    sync_rate_a = 1.0
    sync_rate_b = 1.0

    if tempo_relation == "direct" and bpm_a and bpm_b:
        sync_target_bpm = sqrt(float(bpm_a) * float(bpm_b))
        desired_rate_a = sync_target_bpm / float(bpm_a)
        desired_rate_b = sync_target_bpm / float(bpm_b)
        max_shift = max(abs(desired_rate_a - 1.0), abs(desired_rate_b - 1.0))
        if max_shift <= _PREVIEW_SYNC_TOLERANCE:
            sync_status = "locked"
            sync_label = f"locked @ {sync_target_bpm:.2f}"
            sync_note = (
                f"Auto beat sync locks both previews to {sync_target_bpm:.2f} BPM "
                f"inside the engine's +/-{int(_PREVIEW_SYNC_TOLERANCE * 100)}% tempo band."
            )
            sync_rate_a = desired_rate_a
            sync_rate_b = desired_rate_b
        else:
            sync_rate_a = _clamp(desired_rate_a, 1.0 - _PREVIEW_SYNC_TOLERANCE, 1.0 + _PREVIEW_SYNC_TOLERANCE)
            sync_rate_b = _clamp(desired_rate_b, 1.0 - _PREVIEW_SYNC_TOLERANCE, 1.0 + _PREVIEW_SYNC_TOLERANCE)
            effective_a = float(bpm_a) * sync_rate_a
            effective_b = float(bpm_b) * sync_rate_b
            residual_drift = abs(effective_a - effective_b) / max(effective_a, effective_b, 1e-9) * 100.0
            sync_status = "partial"
            sync_label = "partial"
            sync_note = (
                f"Auto beat sync uses the engine's +/-{int(_PREVIEW_SYNC_TOLERANCE * 100)}% tempo band, "
                f"but about {residual_drift:.1f}% drift remains."
            )
    elif tempo_relation != "direct":
        sync_note = (
            f"Auto beat sync stays off because the engine tagged this as "
            f"{tempo_relation.replace('_', ' ')} tempo relation, not a direct beatmatch."
        )
    elif not bpm_a or not bpm_b:
        sync_note = "Auto beat sync stays off because at least one track is missing beatgrid BPM."

    target_bpm_label = f"{sync_target_bpm:.2f} BPM" if sync_target_bpm is not None else "raw BPM"
    bpm_a_label = f"{float(bpm_a):.2f} BPM" if bpm_a else "BPM n/a"
    bpm_b_label = f"{float(bpm_b):.2f} BPM" if bpm_b else "BPM n/a"
    if sync_status in {"locked", "partial"} and bpm_a and bpm_b:
        sync_a_label = f"{bpm_a_label} -> {float(bpm_a) * sync_rate_a:.2f} BPM"
        sync_b_label = f"{bpm_b_label} -> {float(bpm_b) * sync_rate_b:.2f} BPM"
    else:
        sync_a_label = bpm_a_label
        sync_b_label = bpm_b_label
    auto_blend, auto_blend_reason = _suggest_listen_blend(row)

    return {
        "track_a_title": row.get("title_a", row.get("track_id_a", "Track A")),
        "track_b_title": row.get("title_b", row.get("track_id_b", "Track B")),
        "audio_a_path": _resolve_media_path(
            row.get("track_a_source_path", ""),
            repo_root=repo_root,
            output_dir=output_dir,
        ),
        "audio_b_path": _resolve_media_path(
            row.get("track_b_source_path", ""),
            repo_root=repo_root,
            output_dir=output_dir,
        ),
        "preview_a_cue_sec": preview_cue_a,
        "preview_b_cue_sec": preview_cue_b,
        "preview_a_start_sec": preview_start_a,
        "preview_b_start_sec": preview_start_b,
        "preview_a_label": window_a or "n/a",
        "preview_b_label": window_b or "n/a",
        "preview_lead_in_sec": int(_PREVIEW_LEAD_IN_SEC),
        "preview_duration_sec": _preview_duration_seconds(window_a, window_b),
        "quantize_status": quantize_status,
        "quantize_label": quantize_label,
        "quantize_note": quantize_note,
        "quantize_lead_beats": quantize_lead_beats,
        "grid_a_label": _format_timecode(preview_cue_a),
        "grid_b_label": _format_timecode(preview_cue_b),
        "bpm_a": bpm_a,
        "bpm_b": bpm_b,
        "sync_target_bpm": sync_target_bpm,
        "sync_rate_a": round(sync_rate_a, 4),
        "sync_rate_b": round(sync_rate_b, 4),
        "sync_status": sync_status,
        "sync_label": sync_label,
        "sync_note": sync_note,
        "sync_target_label": target_bpm_label,
        "sync_a_label": sync_a_label,
        "sync_b_label": sync_b_label,
        "listen_blend_auto": auto_blend,
        "listen_blend_reason": auto_blend_reason,
    }


def _pair_rank_key(row: dict[str, str]) -> tuple[int, float]:
    policy = row.get("engine_recommendation_policy", "review_only")
    policy_rank = {"allow": 0, "review_only": 1, "suppress": 2}.get(policy, 1)
    return (policy_rank, -_float(row.get("engine_score"), 0.0))


def _select_diverse_pair_rows(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    ordered = sorted(rows, key=_pair_rank_key)
    selected: list[dict[str, str]] = []
    seen_tracks: set[str] = set()
    seen_pair_ids: set[str] = set()

    for row in ordered:
        if len(selected) >= limit:
            break
        pair_id = row.get("pair_id", "")
        if pair_id in seen_pair_ids:
            continue
        track_a = row.get("track_id_a", "")
        track_b = row.get("track_id_b", "")
        if track_a not in seen_tracks or track_b not in seen_tracks:
            selected.append(row)
            seen_pair_ids.add(pair_id)
            seen_tracks.update({track_a, track_b})

    for row in ordered:
        if len(selected) >= limit:
            break
        pair_id = row.get("pair_id", "")
        if pair_id in seen_pair_ids:
            continue
        selected.append(row)
        seen_pair_ids.add(pair_id)

    return selected


def _select_window_rows(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    best_by_track: dict[str, dict[str, str]] = {}
    for row in rows:
        track_id = row.get("track_id", "")
        if not track_id:
            continue
        current = best_by_track.get(track_id)
        if current is None or _float(row.get("engine_score"), 0.0) > _float(current.get("engine_score"), 0.0):
            best_by_track[track_id] = row
    ordered = sorted(
        best_by_track.values(),
        key=lambda row: (-_float(row.get("engine_score"), 0.0), row.get("title", "")),
    )
    return ordered[:limit]


def _select_set_function_rows(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            -_float(row.get("engine_risk"), 0.0),
            _float(row.get("engine_conf"), 1.0),
            row.get("title", ""),
        ),
    )
    return ordered[:limit]


def _base_page_style() -> str:
    return """
body{
  margin:0;
  min-height:100vh;
  color:#17212b;
  background:
    radial-gradient(circle at top left, rgba(251,146,60,.16), transparent 32%),
    radial-gradient(circle at top right, rgba(20,184,166,.14), transparent 28%),
    linear-gradient(180deg, #f8f1e8 0%, #efe2d2 100%);
  font-family:'Avenir Next','Futura','Trebuchet MS',sans-serif;
}
.wrap{
  max-width:1080px;
  margin:0 auto;
  padding:24px 18px 48px;
}
.hero{
  background:rgba(255,249,239,.82);
  border:1px solid rgba(120,82,49,.14);
  border-radius:28px;
  box-shadow:0 24px 60px rgba(23,33,43,.10);
  padding:22px 22px 18px;
  backdrop-filter:blur(12px);
}
.eyebrow{
  font-size:12px;
  font-weight:800;
  letter-spacing:.16em;
  text-transform:uppercase;
  color:#935f27;
}
h1{
  margin:8px 0 10px;
  font-size:44px;
  line-height:1.02;
}
.hero p{
  margin:0;
  max-width:760px;
  color:#586373;
  font-size:17px;
  line-height:1.5;
}
.hud{
  display:flex;
  flex-wrap:wrap;
  gap:10px;
  margin-top:18px;
}
.pill{
  padding:10px 14px;
  border-radius:999px;
  background:rgba(255,255,255,.72);
  border:1px solid rgba(120,82,49,.14);
  font-size:13px;
  color:#374151;
}
.deck{
  position:relative;
  min-height:720px;
  margin-top:22px;
}
.empty{
  background:rgba(255,249,239,.76);
  border:1px dashed rgba(120,82,49,.24);
  border-radius:24px;
  padding:34px 22px;
  color:#586373;
}
.card-shell{
  position:relative;
  max-width:920px;
  margin:0 auto;
  touch-action:pan-y;
}
.card{
  background:rgba(255,249,239,.94);
  border:1px solid rgba(120,82,49,.14);
  border-radius:34px;
  box-shadow:0 30px 80px rgba(23,33,43,.16);
  overflow:hidden;
  transform-origin:center center;
  transition:transform .18s ease, opacity .18s ease;
}
.card.dragging{
  transition:none;
}
.topbar{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
  padding:20px 22px 0;
}
.tag{
  display:inline-flex;
  align-items:center;
  gap:8px;
  padding:9px 12px;
  border-radius:999px;
  background:rgba(20,184,166,.08);
  color:#0f766e;
  font-size:12px;
  font-weight:800;
  letter-spacing:.12em;
  text-transform:uppercase;
}
.tag.warn{
  background:rgba(245,158,11,.12);
  color:#9a6700;
}
.title{
  padding:10px 22px 0;
}
.title h2{
  margin:0;
  font-size:34px;
  line-height:1.06;
}
.subtitle{
  margin-top:8px;
  color:#586373;
  font-size:16px;
}
.metrics{
  display:flex;
  flex-wrap:wrap;
  gap:10px;
  padding:18px 22px 0;
}
.metric{
  min-width:120px;
  padding:10px 12px;
  border-radius:18px;
  background:#fff;
  border:1px solid rgba(120,82,49,.14);
}
.metric b{
  display:block;
  font-size:12px;
  letter-spacing:.08em;
  text-transform:uppercase;
  color:#7b8794;
  margin-bottom:4px;
}
.metric span{
  font-size:19px;
  font-weight:800;
}
.visual{
  padding:18px 22px 0;
}
.visual img{
  width:100%;
  height:auto;
  border-radius:24px;
  border:1px solid rgba(120,82,49,.12);
  background:#fff;
  display:block;
}
.listen-grid{
  display:grid;
  grid-template-columns:repeat(2, minmax(0, 1fr));
  gap:12px;
  padding:18px 22px 0;
}
.listen-card{
  background:#fffdf8;
  border:1px solid rgba(120,82,49,.14);
  border-radius:22px;
  padding:14px;
}
.listen-card b{
  display:block;
  font-size:12px;
  letter-spacing:.08em;
  text-transform:uppercase;
  color:#7b8794;
}
.listen-card strong{
  display:block;
  margin-top:6px;
  font-size:16px;
  line-height:1.35;
}
.listen-card .mini{
  display:block;
  margin-top:6px;
}
.listen-card audio{
  width:100%;
  margin-top:12px;
}
.listen-controls{
  display:flex;
  flex-wrap:wrap;
  gap:10px;
  padding:14px 22px 0;
}
.listen-controls label{
  display:inline-flex;
  align-items:center;
  gap:8px;
  color:#374151;
  font-size:13px;
  font-weight:700;
}
.listen-controls a{
  display:inline-flex;
  align-items:center;
  text-decoration:none;
}
.listen-select{
  border-radius:999px;
  border:1px solid rgba(120,82,49,.18);
  background:#fffdf8;
  color:#17212b;
  padding:11px 14px;
  font:inherit;
  font-weight:700;
}
.listen-action{
  border:none;
  border-radius:999px;
  padding:12px 16px;
  background:#17212b;
  color:#fff9ef;
  font:inherit;
  font-weight:800;
  letter-spacing:.03em;
  cursor:pointer;
}
.listen-action.alt{
  background:rgba(255,255,255,.84);
  color:#374151;
  border:1px solid rgba(120,82,49,.14);
}
.listen-note{
  padding:10px 22px 0;
  color:#586373;
  font-size:14px;
  line-height:1.45;
}
.copy{
  padding:18px 22px 0;
  color:#2e3a46;
  line-height:1.55;
  font-size:16px;
}
.chips{
  display:flex;
  flex-wrap:wrap;
  gap:8px;
  padding:14px 22px 0;
}
.chip{
  padding:8px 10px;
  border-radius:999px;
  border:1px solid rgba(120,82,49,.14);
  background:rgba(255,255,255,.84);
  color:#374151;
  font-size:13px;
}
.comment-wrap{
  padding:16px 22px 0;
}
.comment-wrap label{
  display:block;
  margin-bottom:8px;
  color:#7b8794;
  font-size:12px;
  font-weight:800;
  letter-spacing:.08em;
  text-transform:uppercase;
}
.comment-wrap textarea{
  width:100%;
  min-height:84px;
  resize:vertical;
  border-radius:18px;
  border:1px solid rgba(120,82,49,.16);
  padding:12px 14px;
  font:inherit;
  background:rgba(255,255,255,.92);
  color:#17212b;
  box-sizing:border-box;
}
.picker{
  display:none;
  gap:10px;
  flex-wrap:wrap;
  padding:18px 22px 4px;
}
.picker.active{
  display:flex;
}
.pick{
  border:none;
  border-radius:999px;
  padding:12px 14px;
  background:#17212b;
  color:#fff9ef;
  font:inherit;
  font-weight:700;
  cursor:pointer;
}
.controls{
  display:flex;
  flex-wrap:wrap;
  gap:12px;
  justify-content:center;
  margin-top:18px;
}
.action{
  border:none;
  border-radius:999px;
  padding:16px 20px;
  min-width:160px;
  font:inherit;
  font-size:15px;
  font-weight:800;
  letter-spacing:.04em;
  cursor:pointer;
  box-shadow:0 10px 30px rgba(23,33,43,.10);
}
.action.bad{
  background:#fff;
  color:#b91c1c;
}
.action.mid{
  background:#fff7ed;
  color:#9a6700;
}
.action.good{
  background:#0f766e;
  color:#f8fffd;
}
.action.ghost{
  background:rgba(255,255,255,.74);
  color:#374151;
}
.footer{
  display:flex;
  flex-wrap:wrap;
  gap:12px;
  justify-content:center;
  margin-top:14px;
}
.status{
  text-align:center;
  margin-top:16px;
  color:#586373;
  font-size:15px;
}
.mini{
  font-size:13px;
  color:#7b8794;
}
.nav{
  display:flex;
  gap:10px;
  flex-wrap:wrap;
  margin-top:18px;
}
.nav a{
  text-decoration:none;
  color:#17212b;
  background:rgba(255,255,255,.72);
  border:1px solid rgba(120,82,49,.14);
  border-radius:999px;
  padding:10px 14px;
  font-weight:700;
}
@media (max-width: 760px){
  h1{font-size:34px;}
  .title h2{font-size:28px;}
  .action{min-width:140px;flex:1 1 40%;}
  .listen-grid{grid-template-columns:1fr;}
}
"""


def _download_script() -> str:
    return """
function csvEscape(value) {
  const raw = value == null ? '' : String(value);
  if (/[",\\n]/.test(raw)) {
    return '"' + raw.replace(/"/g, '""') + '"';
  }
  return raw;
}

function downloadCsv(filename, headers, rows) {
  const lines = [headers.map(csvEscape).join(',')];
  for (const row of rows) {
    lines.push(headers.map((header) => csvEscape(row[header] ?? '')).join(','));
  }
  const blob = new Blob([lines.join('\\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
"""


def _render_pair_page(items: list[dict[str, object]], headers: list[str], path: str | Path) -> Path:
    if not items:
        body = "\n".join(
            [
                "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"/>",
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>",
                "<title>DanceLab Pair Swipe Review</title>",
                f"<style>{_base_page_style()}</style></head><body>",
                '<main class="wrap"><section class="hero"><div class="eyebrow">Swipe Review</div>',
                "<h1>Pair Review Deck</h1>",
                "<p>No pair cards were available for this bundle.</p></section>",
                '<section class="deck"><div class="empty">Run `decision-report` first or pass `--report-dir` so the pair deck can be generated.</div></section></main></body></html>',
            ]
        )
        return _write_text(path, body)

    data_json = json.dumps({"items": items, "headers": headers}, ensure_ascii=True)
    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>DanceLab Pair Swipe Review</title>
  <style>{_base_page_style()}</style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <div class="eyebrow">Swipe Review</div>
      <h1>Pair Review Deck</h1>
      <p>Right means this transition works. Left means no. Down or the middle button means “needs another listen”. This view puts the waveform first, so you can decide whether the highlighted transition zone is right or whether the mix should actually happen somewhere else.</p>
      <div class="hud">
        <div class="pill">Arrow keys: left reject, down review, right accept</div>
        <div class="pill">Swipe the card left or right on trackpads and touch screens</div>
        <div class="pill">Shaded regions are current engine guesses, not DJ ground truth</div>
        <div class="pill">{len(items)} focused cards instead of the full table</div>
      </div>
      <div class="nav"><a href="index.html">Back to review launcher</a></div>
    </section>
    <section id="deck" class="deck"></section>
    <div class="controls">
      <button id="badBtn" class="action bad" type="button">Left / Reject</button>
      <button id="midBtn" class="action mid" type="button">Down / Review</button>
      <button id="goodBtn" class="action good" type="button">Right / Accept</button>
    </div>
    <div class="footer">
      <button id="skipBtn" class="action ghost" type="button">Skip</button>
      <button id="undoBtn" class="action ghost" type="button">Undo</button>
      <button id="exportBtn" class="action ghost" type="button">Export CSV</button>
      <button id="resetBtn" class="action ghost" type="button">Reset Progress</button>
    </div>
    <div id="status" class="status"></div>
  </main>
  <script>
    const APP = {data_json};
    const STORAGE_KEY = 'dancelab-pair-swipe-review-v1';
    {_download_script()}

    const deckEl = document.getElementById('deck');
    const statusEl = document.getElementById('status');
    const state = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}');
    const history = [];
    let currentIndex = 0;
    let drag = null;
    let previewTimer = null;
    let deckAudio = null;

    function unresolvedIndexes() {{
      const indexes = [];
      APP.items.forEach((item, index) => {{
        if (!state[item.id]) indexes.push(index);
      }});
      return indexes;
    }}

    function nextIndex(start) {{
      for (let i = start; i < APP.items.length; i += 1) {{
        if (!state[APP.items[i].id]) return i;
      }}
      return -1;
    }}

    function save() {{
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }}

    function previewStart(item, prefix) {{
      return Math.max(Number(item[`preview_${{prefix}}_start_sec`] ?? 0), 0);
    }}

    function cueTime(item, prefix) {{
      return Math.max(Number(item[`preview_${{prefix}}_cue_sec`] ?? 0), 0);
    }}

    function applySyncProfile(item) {{
      const audioA = document.getElementById('audioA');
      const audioB = document.getElementById('audioB');
      const rateA = Number(item.sync_rate_a ?? 1);
      const rateB = Number(item.sync_rate_b ?? 1);
      [audioA, audioB].forEach((audio) => {{
        if (!audio) return;
        if ('preservesPitch' in audio) audio.preservesPitch = true;
        if ('webkitPreservesPitch' in audio) audio.webkitPreservesPitch = true;
        if ('mozPreservesPitch' in audio) audio.mozPreservesPitch = true;
      }});
      if (audioA) audioA.playbackRate = rateA;
      if (audioB) audioB.playbackRate = rateB;
    }}

    function disconnectDeckChannel(channel) {{
      if (!channel) return;
      [channel.source, channel.low, channel.mid, channel.high, channel.gain].forEach((node) => {{
        try {{
          node.disconnect();
        }} catch (_error) {{
          // best-effort cleanup for previous card nodes
        }}
      }});
    }}

    function buildDeckChannel(ctx, audio) {{
      const source = ctx.createMediaElementSource(audio);
      const low = ctx.createBiquadFilter();
      low.type = 'lowshelf';
      low.frequency.value = 180;
      const mid = ctx.createBiquadFilter();
      mid.type = 'peaking';
      mid.frequency.value = 1700;
      mid.Q.value = 0.8;
      const high = ctx.createBiquadFilter();
      high.type = 'highshelf';
      high.frequency.value = 5600;
      const gain = ctx.createGain();
      source.connect(low);
      low.connect(mid);
      mid.connect(high);
      high.connect(gain);
      gain.connect(ctx.destination);
      return {{ source, low, mid, high, gain }};
    }}

    function ensureDeckAudio() {{
      const audioA = document.getElementById('audioA');
      const audioB = document.getElementById('audioB');
      if (!audioA || !audioB) return null;
      if (deckAudio && deckAudio.audioA === audioA && deckAudio.audioB === audioB) return deckAudio;
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return null;
      const ctx = deckAudio?.ctx || new AudioCtx();
      if (deckAudio) {{
        disconnectDeckChannel(deckAudio.channelA);
        disconnectDeckChannel(deckAudio.channelB);
      }}
      deckAudio = {{
        ctx,
        audioA,
        audioB,
        channelA: buildDeckChannel(ctx, audioA),
        channelB: buildDeckChannel(ctx, audioB),
      }};
      return deckAudio;
    }}

    function setParam(param, when, value) {{
      param.cancelScheduledValues(when);
      param.setValueAtTime(value, when);
    }}

    function scheduleParam(param, when, points) {{
      if (!points.length) return;
      param.cancelScheduledValues(when);
      param.setValueAtTime(points[0][1], when + points[0][0]);
      for (let index = 1; index < points.length; index += 1) {{
        param.linearRampToValueAtTime(points[index][1], when + points[index][0]);
      }}
    }}

    function scheduleChannel(channel, when, plan) {{
      scheduleParam(channel.gain.gain, when, plan.gain);
      scheduleParam(channel.low.gain, when, plan.low);
      scheduleParam(channel.mid.gain, when, plan.mid);
      scheduleParam(channel.high.gain, when, plan.high);
    }}

    function selectedBlendMode(item) {{
      const selected = document.getElementById('blendMode')?.value || 'auto';
      if (selected === 'auto') return item.listen_blend_auto || 'plain_blend';
      return selected;
    }}

    function blendModeLabel(mode) {{
      return {{
        plain_blend: 'plain blend',
        bass_swap: 'bass swap',
        tops_swap: 'tops swap',
        contour_blend: 'contour blend',
      }}[mode] || mode.replaceAll('_', ' ');
    }}

    function applyBlendMode(item, when, durationSec) {{
      const mixer = ensureDeckAudio();
      if (!mixer) return null;
      const mode = selectedBlendMode(item);
      const span = Math.max(Number(durationSec || 0), 12);
      const early = span * 0.28;
      const mid = span * 0.55;
      const late = span * 0.78;

      const plans = {{
        plain_blend: {{
          a: {{
            gain: [[0, 1.0], [mid, 0.88], [span, 0.64]],
            low: [[0, 0], [mid, -4], [span, -8]],
            mid: [[0, 0], [span, -2]],
            high: [[0, 0], [span, -4]],
          }},
          b: {{
            gain: [[0, 0.78], [mid, 0.95], [span, 1.0]],
            low: [[0, -10], [mid, -4], [span, 0]],
            mid: [[0, -1], [span, 0]],
            high: [[0, 1], [span, 0]],
          }},
        }},
        bass_swap: {{
          a: {{
            gain: [[0, 1.0], [mid, 0.9], [span, 0.56]],
            low: [[0, 0], [mid, 0], [late, -18], [span, -22]],
            mid: [[0, 0], [span, -2]],
            high: [[0, 0], [span, -3]],
          }},
          b: {{
            gain: [[0, 0.76], [mid, 0.96], [span, 1.0]],
            low: [[0, -22], [mid, -18], [late, -2], [span, 0]],
            mid: [[0, -2], [mid, -1], [span, 0]],
            high: [[0, 2], [span, 1]],
          }},
        }},
        tops_swap: {{
          a: {{
            gain: [[0, 1.0], [mid, 0.9], [span, 0.62]],
            low: [[0, 0], [late, -10], [span, -16]],
            mid: [[0, 0], [span, -3]],
            high: [[0, 0], [early, -10], [mid, -14], [span, -10]],
          }},
          b: {{
            gain: [[0, 0.74], [mid, 0.95], [span, 1.0]],
            low: [[0, -18], [late, -8], [span, 0]],
            mid: [[0, -2], [mid, -1], [span, 0]],
            high: [[0, -10], [early, -2], [mid, 2], [span, 1]],
          }},
        }},
        contour_blend: {{
          a: {{
            gain: [[0, 1.0], [mid, 0.88], [span, 0.58]],
            low: [[0, 0], [late, -12], [span, -18]],
            mid: [[0, 0], [early, -3], [mid, -6], [span, -8]],
            high: [[0, 0], [span, -4]],
          }},
          b: {{
            gain: [[0, 0.78], [mid, 0.97], [span, 1.0]],
            low: [[0, -16], [late, -6], [span, 0]],
            mid: [[0, -6], [early, -3], [mid, 0], [span, 1]],
            high: [[0, -1], [mid, 1], [span, 1]],
          }},
        }},
      }};

      const plan = plans[mode] || plans.plain_blend;
      scheduleChannel(mixer.channelA, when, plan.a);
      scheduleChannel(mixer.channelB, when, plan.b);
      return {{ mixer, mode }};
    }}

    function stopPreview(reset = false) {{
      if (previewTimer) {{
        window.clearTimeout(previewTimer);
        previewTimer = null;
      }}
      ['audioA', 'audioB'].forEach((id) => {{
        const audio = document.getElementById(id);
        if (!audio) return;
        audio.pause();
      }});
      if (reset) {{
        const item = APP.items[currentIndex];
        if (!item) return;
        const audioA = document.getElementById('audioA');
        const audioB = document.getElementById('audioB');
        if (audioA) audioA.currentTime = previewStart(item, 'a');
        if (audioB) audioB.currentTime = previewStart(item, 'b');
      }}
    }}

    function pairResult(item, verdict, comment) {{
      const row = {{ ...item.row }};
      row['dj_verdict(accept/review/reject)'] = verdict;
      row['dj_mixability_rating'] = verdict === 'accept' ? '5' : verdict === 'review' ? '3' : '1';
      row['dj_transition_strategy'] = verdict === 'accept' ? (row['engine_strategy'] || '') : '';
      row['dj_comment'] = comment || '';
      return row;
    }}

    function setResult(item, verdict, comment) {{
      history.push({{ id: item.id, previous: state[item.id] || null }});
      state[item.id] = pairResult(item, verdict, comment);
      save();
      currentIndex = nextIndex(currentIndex + 1);
      render();
    }}

    function skipCurrent() {{
      currentIndex = nextIndex(currentIndex + 1);
      render();
    }}

    function undo() {{
      const last = history.pop();
      if (!last) return;
      if (last.previous) state[last.id] = last.previous;
      else delete state[last.id];
      save();
      currentIndex = APP.items.findIndex((item) => item.id === last.id);
      render();
    }}

    function exportRows() {{
      const rows = APP.items.map((item) => state[item.id] || item.row);
      downloadCsv('edge_decision_review_swipe.csv', APP.headers, rows);
    }}

    function resetAll() {{
      stopPreview(false);
      localStorage.removeItem(STORAGE_KEY);
      Object.keys(state).forEach((key) => delete state[key]);
      history.length = 0;
      currentIndex = 0;
      render();
    }}

    function applySwipe(direction) {{
      const item = APP.items[currentIndex];
      if (!item) return;
      stopPreview(false);
      const comment = document.getElementById('commentBox')?.value?.trim() || '';
      if (direction === 'good') setResult(item, 'accept', comment);
      if (direction === 'mid') setResult(item, 'review', comment);
      if (direction === 'bad') setResult(item, 'reject', comment);
    }}

    function renderAudioCard(item, prefix, label, title, fallback) {{
      const path = item[`audio_${{prefix}}_path`];
      const cueLabel = item[`preview_${{prefix}}_label`] || 'cue unavailable';
      const gridLabel = item[`grid_${{prefix}}_label`] || 'grid n/a';
      const bpmLabel = item[`sync_${{prefix}}_label`] || 'BPM n/a';
      if (!path) {{
        return `
          <div class="listen-card">
            <b>${{label}}</b>
            <strong>${{title}}</strong>
            <span class="mini">${{fallback}}</span>
          </div>`;
      }}
      return `
        <div class="listen-card">
          <b>${{label}}</b>
          <strong>${{title}}</strong>
          <span class="mini">Cue window: ${{cueLabel}}</span>
          <span class="mini">Grid cue: ${{gridLabel}}</span>
          <span class="mini">Tempo: ${{bpmLabel}}</span>
          <audio id="audio${{prefix.toUpperCase()}}" controls preload="metadata" src="${{path}}"></audio>
        </div>`;
    }}

    function renderCard(item) {{
      const image = item.image_path
        ? `<div class="visual"><img src="${{item.image_path}}" alt="${{item.image_alt}}"/></div>`
        : '<div class="listen-note">Waveform SVG unavailable for this card.</div>';
      const waveformLinks = `
        <div class="listen-controls">
          ${{item.image_path ? `<a class="listen-action" href="${{item.image_path}}" target="_blank" rel="noopener">Open SVG</a>` : ''}}
          ${{item.waveform_gallery_path ? `<a class="listen-action alt" href="${{item.waveform_gallery_path}}" target="_blank" rel="noopener">Open Waveform Gallery</a>` : ''}}
        </div>
        <div class="listen-note">
          Original windows: A ${{item.preview_a_label}}, B ${{item.preview_b_label}}. Quantized grid cues: A ${{item.grid_a_label}}, B ${{item.grid_b_label}}. If the highlighted region looks wrong, swipe down and leave the better section in a note.
        </div>`;
      const chips = (item.risks || []).map((risk) => `<div class="chip">${{risk}}</div>`).join('');
      return `
        <div id="cardShell" class="card-shell">
          <article id="card" class="card">
            <div class="topbar">
              <div class="tag">${{item.rank_label}}</div>
              <div class="tag warn">${{item.policy_label}}</div>
            </div>
            <div class="title">
              <h2>${{item.title}}</h2>
              <div class="subtitle">${{item.subtitle}}</div>
            </div>
            <div class="metrics">
              <div class="metric"><b>Score</b><span>${{item.score}}</span></div>
              <div class="metric"><b>Confidence</b><span>${{item.confidence}}</span></div>
              <div class="metric"><b>Strategy</b><span>${{item.strategy}}</span></div>
              <div class="metric"><b>Window</b><span>${{item.window_pair}}</span></div>
              <div class="metric"><b>Beat Sync</b><span>${{item.sync_label}}</span></div>
              <div class="metric"><b>Quantize</b><span>${{item.quantize_label}}</span></div>
            </div>
            ${{image}}
            ${{waveformLinks}}
            <div class="copy">${{item.copy}}</div>
            <div class="chips">${{chips}}</div>
            <div class="comment-wrap">
              <label for="commentBox">Quick note (optional)</label>
              <textarea id="commentBox" placeholder="Why yes, why no, or what to re-check by ear?"></textarea>
            </div>
          </article>
        </div>`;
    }}

    function bindPreview(item) {{
      const audioA = document.getElementById('audioA');
      const audioB = document.getElementById('audioB');
      const noteEl = document.getElementById('listenNote');
      const previewBtn = document.getElementById('previewBtn');
      const pauseBtn = document.getElementById('pausePreviewBtn');
      const recueBtn = document.getElementById('recuePreviewBtn');
      if (!previewBtn || !pauseBtn || !recueBtn) return;

      function setCuePositions() {{
        applySyncProfile(item);
        if (audioA) audioA.currentTime = previewStart(item, 'a');
        if (audioB) audioB.currentTime = previewStart(item, 'b');
      }}

      async function playPreview() {{
        stopPreview(false);
        setCuePositions();
        if (audioA) audioA.volume = 0.96;
        if (audioB) audioB.volume = 0.84;
        const playCalls = [audioA, audioB]
          .filter(Boolean)
          .map((audio) => audio.play());
        if (!playCalls.length) {{
          if (noteEl) noteEl.textContent = 'No local audio file was attached to this card.';
          return;
        }}
        const results = await Promise.allSettled(playCalls);
        const failed = results.some((result) => result.status === 'rejected');
        if (failed) {{
          if (noteEl) noteEl.textContent = 'Browser blocked at least one file. Try pressing the individual play button once, then Play preview again.';
          return;
        }}
        if (noteEl) noteEl.textContent = `Preview running in ${{item.sync_label}} + ${{item.quantize_label}} mode. Quantized cues are A ${{item.grid_a_label}} and B ${{item.grid_b_label}}.`;
        previewTimer = window.setTimeout(() => {{
          stopPreview(false);
          if (noteEl) noteEl.textContent = `Preview finished. Original cue windows: A ${{item.preview_a_label}}, B ${{item.preview_b_label}}. Quantized cues: A ${{item.grid_a_label}}, B ${{item.grid_b_label}}.`;
        }}, Number(item.preview_duration_sec) * 1000);
      }}

      previewBtn.addEventListener('click', () => {{
        void playPreview();
      }});
      pauseBtn.addEventListener('click', () => {{
        stopPreview(false);
        if (noteEl) noteEl.textContent = 'Preview paused.';
      }});
      recueBtn.addEventListener('click', () => {{
        stopPreview(true);
        if (noteEl) noteEl.textContent = `Players reset to quantized starts. Quantized cues: A ${{item.grid_a_label}}, B ${{item.grid_b_label}}.`;
      }});

      setCuePositions();
    }}

    function bindDrag() {{
      const shell = document.getElementById('cardShell');
      const card = document.getElementById('card');
      if (!shell || !card) return;
      shell.addEventListener('pointerdown', (event) => {{
        drag = {{ startX: event.clientX }};
        card.classList.add('dragging');
      }});
      shell.addEventListener('pointermove', (event) => {{
        if (!drag) return;
        const dx = event.clientX - drag.startX;
        card.style.transform = `translateX(${{dx}}px) rotate(${{dx / 18}}deg)`;
        card.style.opacity = String(Math.max(0.55, 1 - Math.abs(dx) / 320));
      }});
      function finish(event) {{
        if (!drag) return;
        const dx = event.clientX - drag.startX;
        card.classList.remove('dragging');
        card.style.transform = '';
        card.style.opacity = '';
        drag = null;
        if (dx > 96) applySwipe('good');
        else if (dx < -96) applySwipe('bad');
      }}
      shell.addEventListener('pointerup', finish);
      shell.addEventListener('pointercancel', finish);
      shell.addEventListener('pointerleave', (event) => {{
        if (!drag) return;
        finish(event);
      }});
    }}

    function render() {{
      const remaining = unresolvedIndexes();
      const decided = APP.items.length - remaining.length;
      if (currentIndex < 0 || currentIndex >= APP.items.length || state[APP.items[currentIndex]?.id]) {{
        currentIndex = nextIndex(0);
      }}

      stopPreview(false);
      if (currentIndex === -1) {{
        deckEl.innerHTML = `
          <div class="empty">
            <h2>Deck complete.</h2>
            <p>You can export the reviewed CSV now or reset the deck for another pass.</p>
            <p class="mini">Accepted cards map to rating 5, review to 3, reject to 1 so the exported file stays useful for quick pair validation.</p>
          </div>`;
      }} else {{
        const item = APP.items[currentIndex];
        deckEl.innerHTML = renderCard(item);
        bindDrag();
        bindPreview(item);
      }}
      statusEl.innerHTML = `${{decided}} / ${{APP.items.length}} reviewed · ${{remaining.length}} left`;
    }}

    document.getElementById('badBtn').addEventListener('click', () => applySwipe('bad'));
    document.getElementById('midBtn').addEventListener('click', () => applySwipe('mid'));
    document.getElementById('goodBtn').addEventListener('click', () => applySwipe('good'));
    document.getElementById('skipBtn').addEventListener('click', skipCurrent);
    document.getElementById('undoBtn').addEventListener('click', undo);
    document.getElementById('exportBtn').addEventListener('click', exportRows);
    document.getElementById('resetBtn').addEventListener('click', resetAll);

    window.addEventListener('keydown', (event) => {{
      if (['TEXTAREA', 'INPUT'].includes(document.activeElement?.tagName)) return;
      if (event.key === 'ArrowLeft') {{ event.preventDefault(); applySwipe('bad'); }}
      if (event.key === 'ArrowDown') {{ event.preventDefault(); applySwipe('mid'); }}
      if (event.key === 'ArrowRight') {{ event.preventDefault(); applySwipe('good'); }}
    }});

    render();
  </script>
</body>
</html>"""
    return _write_text(path, body)


def _render_listen_page(items: list[dict[str, object]], headers: list[str], path: str | Path) -> Path:
    if not items:
        body = "\n".join(
            [
                "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"/>",
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>",
                "<title>DanceLab Listen Board</title>",
                f"<style>{_base_page_style()}</style></head><body>",
                '<main class="wrap"><section class="hero"><div class="eyebrow">Listen Board</div>',
                "<h1>Pair Listen Board</h1>",
                "<p>No pair cards were available for this bundle.</p></section>",
                '<section class="deck"><div class="empty">Run `decision-report` first or pass `--report-dir` so the listen board can be generated.</div></section></main></body></html>',
            ]
        )
        return _write_text(path, body)

    data_json = json.dumps({"items": items, "headers": headers}, ensure_ascii=True)
    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>DanceLab Listen Board</title>
  <style>{_base_page_style()}</style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <div class="eyebrow">Listen Board</div>
      <h1>Pair Listen Board</h1>
      <p>This is the mechanic-tablet listen mode. Track B is cued to the suggested transition area, the preview snaps both starts to beatgrid cues, auto beat sync applies when the engine marks the pair as direct-tempo, and Auto blend mode now reads the engine's own overlap profile sensor.</p>
      <div class="hud">
        <div class="pill">Arrow keys: left reject, down review, right accept</div>
        <div class="pill">Play preview starts A and B from quantized preview starts</div>
        <div class="pill">Beat sync follows the same direct-tempo logic used by the engine</div>
        <div class="pill">{len(items)} focused listen cards instead of the full table</div>
      </div>
      <div class="nav">
        <a href="index.html">Back to review launcher</a>
        <a href="pairs.html">Open waveform board</a>
      </div>
    </section>
    <section id="deck" class="deck"></section>
    <div class="controls">
      <button id="badBtn" class="action bad" type="button">Left / Reject</button>
      <button id="midBtn" class="action mid" type="button">Down / Review</button>
      <button id="goodBtn" class="action good" type="button">Right / Accept</button>
    </div>
    <div class="footer">
      <button id="skipBtn" class="action ghost" type="button">Skip</button>
      <button id="undoBtn" class="action ghost" type="button">Undo</button>
      <button id="exportBtn" class="action ghost" type="button">Export CSV</button>
      <button id="resetBtn" class="action ghost" type="button">Reset Progress</button>
    </div>
    <div id="status" class="status"></div>
  </main>
  <script>
    const APP = {data_json};
    const STORAGE_KEY = 'dancelab-listen-board-v1';
    {_download_script()}

    const deckEl = document.getElementById('deck');
    const statusEl = document.getElementById('status');
    const state = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}');
    const history = [];
    let currentIndex = 0;
    let drag = null;
    let previewTimer = null;

    function unresolvedIndexes() {{
      const indexes = [];
      APP.items.forEach((item, index) => {{
        if (!state[item.id]) indexes.push(index);
      }});
      return indexes;
    }}

    function nextIndex(start) {{
      for (let i = start; i < APP.items.length; i += 1) {{
        if (!state[APP.items[i].id]) return i;
      }}
      return -1;
    }}

    function save() {{
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }}

    function previewStart(item, prefix) {{
      return Math.max(Number(item[`preview_${{prefix}}_start_sec`] ?? 0), 0);
    }}

    function applySyncProfile(item) {{
      const audioA = document.getElementById('audioA');
      const audioB = document.getElementById('audioB');
      const rateA = Number(item.sync_rate_a ?? 1);
      const rateB = Number(item.sync_rate_b ?? 1);
      [audioA, audioB].forEach((audio) => {{
        if (!audio) return;
        if ('preservesPitch' in audio) audio.preservesPitch = true;
        if ('webkitPreservesPitch' in audio) audio.webkitPreservesPitch = true;
        if ('mozPreservesPitch' in audio) audio.mozPreservesPitch = true;
      }});
      if (audioA) audioA.playbackRate = rateA;
      if (audioB) audioB.playbackRate = rateB;
    }}

    function stopPreview(reset = false) {{
      if (previewTimer) {{
        window.clearTimeout(previewTimer);
        previewTimer = null;
      }}
      ['audioA', 'audioB'].forEach((id) => {{
        const audio = document.getElementById(id);
        if (!audio) return;
        audio.pause();
      }});
      if (reset) {{
        const item = APP.items[currentIndex];
        if (!item) return;
        const audioA = document.getElementById('audioA');
        const audioB = document.getElementById('audioB');
        if (audioA) audioA.currentTime = previewStart(item, 'a');
        if (audioB) audioB.currentTime = previewStart(item, 'b');
      }}
    }}

    function pairResult(item, verdict, comment) {{
      const row = {{ ...item.row }};
      row['dj_verdict(accept/review/reject)'] = verdict;
      row['dj_mixability_rating'] = verdict === 'accept' ? '5' : verdict === 'review' ? '3' : '1';
      row['dj_transition_strategy'] = verdict === 'accept' ? (row['engine_strategy'] || '') : '';
      row['dj_comment'] = comment || '';
      return row;
    }}

    function setResult(item, verdict, comment) {{
      history.push({{ id: item.id, previous: state[item.id] || null }});
      state[item.id] = pairResult(item, verdict, comment);
      save();
      currentIndex = nextIndex(currentIndex + 1);
      render();
    }}

    function skipCurrent() {{
      currentIndex = nextIndex(currentIndex + 1);
      render();
    }}

    function undo() {{
      const last = history.pop();
      if (!last) return;
      if (last.previous) state[last.id] = last.previous;
      else delete state[last.id];
      save();
      currentIndex = APP.items.findIndex((item) => item.id === last.id);
      render();
    }}

    function exportRows() {{
      const rows = APP.items.map((item) => state[item.id] || item.row);
      downloadCsv('edge_decision_review_listen_board.csv', APP.headers, rows);
    }}

    function resetAll() {{
      stopPreview(false);
      localStorage.removeItem(STORAGE_KEY);
      Object.keys(state).forEach((key) => delete state[key]);
      history.length = 0;
      currentIndex = 0;
      render();
    }}

    function applySwipe(direction) {{
      const item = APP.items[currentIndex];
      if (!item) return;
      stopPreview(false);
      const comment = document.getElementById('commentBox')?.value?.trim() || '';
      if (direction === 'good') setResult(item, 'accept', comment);
      if (direction === 'mid') setResult(item, 'review', comment);
      if (direction === 'bad') setResult(item, 'reject', comment);
    }}

    function renderAudioCard(item, prefix, label, title, fallback) {{
      const path = item[`audio_${{prefix}}_path`];
      const cueLabel = item[`preview_${{prefix}}_label`] || 'cue unavailable';
      const gridLabel = item[`grid_${{prefix}}_label`] || 'grid n/a';
      const bpmLabel = item[`sync_${{prefix}}_label`] || 'BPM n/a';
      if (!path) {{
        return `
          <div class="listen-card">
            <b>${{label}}</b>
            <strong>${{title}}</strong>
            <span class="mini">${{fallback}}</span>
          </div>`;
      }}
      return `
        <div class="listen-card">
          <b>${{label}}</b>
          <strong>${{title}}</strong>
          <span class="mini">Cue window: ${{cueLabel}}</span>
          <span class="mini">Grid cue: ${{gridLabel}}</span>
          <span class="mini">Tempo: ${{bpmLabel}}</span>
          <audio id="audio${{prefix.toUpperCase()}}" controls preload="metadata" src="${{path}}"></audio>
        </div>`;
    }}

    function renderCard(item) {{
      const image = item.image_path
        ? `<div class="visual"><img src="${{item.image_path}}" alt="${{item.image_alt}}"/></div>`
        : '';
      const audio = `
        <div class="listen-grid">
          ${{renderAudioCard(item, 'a', 'Track A', item.track_a_title, 'Audio file unavailable for this card.')}}
          ${{renderAudioCard(item, 'b', 'Track B', item.track_b_title, 'Audio file unavailable for this card.')}}
        </div>
        <div class="listen-controls">
          <label for="blendMode">Blend mode
            <select id="blendMode" class="listen-select">
              <option value="auto" selected>Auto (${{blendModeLabel(item.listen_blend_auto || 'plain_blend')}})</option>
              <option value="plain_blend">Plain blend</option>
              <option value="bass_swap">Bass swap</option>
              <option value="tops_swap">Tops swap</option>
              <option value="contour_blend">Contour blend</option>
            </select>
          </label>
          <button id="previewBtn" class="listen-action" type="button">Play preview</button>
          <button id="pausePreviewBtn" class="listen-action alt" type="button">Pause</button>
          <button id="recuePreviewBtn" class="listen-action alt" type="button">Reset to cue</button>
          ${{item.image_path ? `<a class="listen-action alt" href="${{item.image_path}}" target="_blank" rel="noopener">Open waveform SVG</a>` : ''}}
        </div>
        <div id="listenNote" class="listen-note">
          ${{item.listen_blend_reason}} ${{item.quantize_note}} ${{item.sync_note}} Original windows: A ${{item.preview_a_label}}, B ${{item.preview_b_label}}. Quantized cues: A ${{item.grid_a_label}}, B ${{item.grid_b_label}}.
        </div>`;
      const chips = (item.risks || []).map((risk) => `<div class="chip">${{risk}}</div>`).join('');
      return `
        <div id="cardShell" class="card-shell">
          <article id="card" class="card">
            <div class="topbar">
              <div class="tag">${{item.rank_label}}</div>
              <div class="tag warn">${{item.policy_label}}</div>
            </div>
            <div class="title">
              <h2>${{item.title}}</h2>
              <div class="subtitle">${{item.subtitle}}</div>
            </div>
            <div class="metrics">
              <div class="metric"><b>Score</b><span>${{item.score}}</span></div>
              <div class="metric"><b>Confidence</b><span>${{item.confidence}}</span></div>
              <div class="metric"><b>Strategy</b><span>${{item.strategy}}</span></div>
              <div class="metric"><b>Window</b><span>${{item.window_pair}}</span></div>
              <div class="metric"><b>Beat Sync</b><span>${{item.sync_label}}</span></div>
              <div class="metric"><b>Quantize</b><span>${{item.quantize_label}}</span></div>
            </div>
            ${{audio}}
            ${{image}}
            <div class="copy">${{item.copy}}</div>
            <div class="chips">${{chips}}</div>
            <div class="comment-wrap">
              <label for="commentBox">Quick note (optional)</label>
              <textarea id="commentBox" placeholder="How did the overlap sound, and should the transition happen elsewhere?"></textarea>
            </div>
          </article>
        </div>`;
    }}

    function bindPreview(item) {{
      const audioA = document.getElementById('audioA');
      const audioB = document.getElementById('audioB');
      const noteEl = document.getElementById('listenNote');
      const previewBtn = document.getElementById('previewBtn');
      const pauseBtn = document.getElementById('pausePreviewBtn');
      const recueBtn = document.getElementById('recuePreviewBtn');
      const blendMode = document.getElementById('blendMode');
      if (!previewBtn || !pauseBtn || !recueBtn) return;

      function setCuePositions() {{
        applySyncProfile(item);
        const mixer = ensureDeckAudio();
        if (mixer) {{
          const now = mixer.ctx.currentTime;
          setParam(mixer.channelA.gain.gain, now, 1.0);
          setParam(mixer.channelA.low.gain, now, 0.0);
          setParam(mixer.channelA.mid.gain, now, 0.0);
          setParam(mixer.channelA.high.gain, now, 0.0);
          setParam(mixer.channelB.gain.gain, now, 1.0);
          setParam(mixer.channelB.low.gain, now, 0.0);
          setParam(mixer.channelB.mid.gain, now, 0.0);
          setParam(mixer.channelB.high.gain, now, 0.0);
        }}
        if (audioA) {{
          audioA.volume = 1.0;
          audioA.currentTime = previewStart(item, 'a');
        }}
        if (audioB) {{
          audioB.volume = 1.0;
          audioB.currentTime = previewStart(item, 'b');
        }}
      }}

      async function playPreview() {{
        stopPreview(false);
        setCuePositions();
        const mixer = ensureDeckAudio();
        if (mixer) await mixer.ctx.resume();
        const scheduled = mixer ? applyBlendMode(item, mixer.ctx.currentTime + 0.05, Number(item.preview_duration_sec)) : null;
        const playCalls = [audioA, audioB]
          .filter(Boolean)
          .map((audio) => audio.play());
        if (!playCalls.length) {{
          if (noteEl) noteEl.textContent = 'No local audio file was attached to this card.';
          return;
        }}
        const results = await Promise.allSettled(playCalls);
        const failed = results.some((result) => result.status === 'rejected');
        if (failed) {{
          if (noteEl) noteEl.textContent = 'Browser blocked at least one file. Try pressing the individual play button once, then Play preview again.';
          return;
        }}
        const activeMode = scheduled ? blendModeLabel(scheduled.mode) : blendModeLabel(selectedBlendMode(item));
        if (noteEl) noteEl.textContent = `Preview running in ${{item.sync_label}} + ${{item.quantize_label}} + ${{activeMode}} mode. Quantized cues are A ${{item.grid_a_label}} and B ${{item.grid_b_label}}.`;
        previewTimer = window.setTimeout(() => {{
          stopPreview(false);
          if (noteEl) noteEl.textContent = `${{item.listen_blend_reason}} Original cue windows: A ${{item.preview_a_label}}, B ${{item.preview_b_label}}. Quantized cues: A ${{item.grid_a_label}}, B ${{item.grid_b_label}}.`;
        }}, Number(item.preview_duration_sec) * 1000);
      }}

      previewBtn.addEventListener('click', () => {{
        void playPreview();
      }});
      pauseBtn.addEventListener('click', () => {{
        stopPreview(false);
        if (noteEl) noteEl.textContent = 'Preview paused.';
      }});
      recueBtn.addEventListener('click', () => {{
        stopPreview(true);
        if (noteEl) noteEl.textContent = `Players reset to quantized starts. Quantized cues: A ${{item.grid_a_label}}, B ${{item.grid_b_label}}.`;
      }});
      blendMode?.addEventListener('change', () => {{
        if (noteEl) noteEl.textContent = `${{item.listen_blend_reason}} Active blend mode: ${{blendModeLabel(selectedBlendMode(item))}}.`;
      }});

      setCuePositions();
    }}

    function bindDrag() {{
      const shell = document.getElementById('cardShell');
      const card = document.getElementById('card');
      if (!shell || !card) return;
      shell.addEventListener('pointerdown', (event) => {{
        drag = {{ startX: event.clientX }};
        card.classList.add('dragging');
      }});
      shell.addEventListener('pointermove', (event) => {{
        if (!drag) return;
        const dx = event.clientX - drag.startX;
        card.style.transform = `translateX(${{dx}}px) rotate(${{dx / 18}}deg)`;
        card.style.opacity = String(Math.max(0.55, 1 - Math.abs(dx) / 320));
      }});
      function finish(event) {{
        if (!drag) return;
        const dx = event.clientX - drag.startX;
        card.classList.remove('dragging');
        card.style.transform = '';
        card.style.opacity = '';
        drag = null;
        if (dx > 96) applySwipe('good');
        else if (dx < -96) applySwipe('bad');
      }}
      shell.addEventListener('pointerup', finish);
      shell.addEventListener('pointercancel', finish);
      shell.addEventListener('pointerleave', (event) => {{
        if (!drag) return;
        finish(event);
      }});
    }}

    function render() {{
      const remaining = unresolvedIndexes();
      const decided = APP.items.length - remaining.length;
      if (currentIndex < 0 || currentIndex >= APP.items.length || state[APP.items[currentIndex]?.id]) {{
        currentIndex = nextIndex(0);
      }}

      stopPreview(false);
      if (currentIndex === -1) {{
        deckEl.innerHTML = `
          <div class="empty">
            <h2>Listen board complete.</h2>
            <p>You can export the reviewed CSV now or reset the board for another pass.</p>
            <p class="mini">Accepted cards map to rating 5, review to 3, reject to 1 so the exported file stays useful for quick pair validation.</p>
          </div>`;
      }} else {{
        const item = APP.items[currentIndex];
        deckEl.innerHTML = renderCard(item);
        bindDrag();
        bindPreview(item);
      }}
      statusEl.innerHTML = `${{decided}} / ${{APP.items.length}} reviewed · ${{remaining.length}} left`;
    }}

    document.getElementById('badBtn').addEventListener('click', () => applySwipe('bad'));
    document.getElementById('midBtn').addEventListener('click', () => applySwipe('mid'));
    document.getElementById('goodBtn').addEventListener('click', () => applySwipe('good'));
    document.getElementById('skipBtn').addEventListener('click', skipCurrent);
    document.getElementById('undoBtn').addEventListener('click', undo);
    document.getElementById('exportBtn').addEventListener('click', exportRows);
    document.getElementById('resetBtn').addEventListener('click', resetAll);

    window.addEventListener('keydown', (event) => {{
      if (['TEXTAREA', 'INPUT'].includes(document.activeElement?.tagName)) return;
      if (event.key === 'ArrowLeft') {{ event.preventDefault(); applySwipe('bad'); }}
      if (event.key === 'ArrowDown') {{ event.preventDefault(); applySwipe('mid'); }}
      if (event.key === 'ArrowRight') {{ event.preventDefault(); applySwipe('good'); }}
    }});

    render();
  </script>
</body>
</html>"""
    return _write_text(path, body)


def _render_window_page(items: list[dict[str, object]], headers: list[str], path: str | Path) -> Path:
    data_json = json.dumps({"items": items, "headers": headers}, ensure_ascii=True)
    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>DanceLab Window Swipe Review</title>
  <style>{_base_page_style()}</style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <div class="eyebrow">Swipe Review</div>
      <h1>Transition Window Deck</h1>
      <p>One strongest engine window per track. Right means you would actually use it. Left means no. This pass is intentionally lightweight and binary so you can move fast.</p>
      <div class="hud">
        <div class="pill">Arrow keys: left bad, right good</div>
        <div class="pill">{len(items)} cards, one per track</div>
      </div>
      <div class="nav"><a href="index.html">Back to review launcher</a></div>
    </section>
    <section id="deck" class="deck"></section>
    <div class="controls">
      <button id="badBtn" class="action bad" type="button">Left / Bad</button>
      <button id="goodBtn" class="action good" type="button">Right / Good</button>
    </div>
    <div class="footer">
      <button id="skipBtn" class="action ghost" type="button">Skip</button>
      <button id="undoBtn" class="action ghost" type="button">Undo</button>
      <button id="exportBtn" class="action ghost" type="button">Export CSV</button>
      <button id="resetBtn" class="action ghost" type="button">Reset Progress</button>
    </div>
    <div id="status" class="status"></div>
  </main>
  <script>
    const APP = {data_json};
    const STORAGE_KEY = 'dancelab-window-swipe-review-v1';
    {_download_script()}

    const deckEl = document.getElementById('deck');
    const statusEl = document.getElementById('status');
    const state = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}');
    const history = [];
    let currentIndex = 0;
    let drag = null;

    function nextIndex(start) {{
      for (let i = start; i < APP.items.length; i += 1) {{
        if (!state[APP.items[i].id]) return i;
      }}
      return -1;
    }}

    function save() {{
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }}

    function setResult(item, verdict, comment) {{
      history.push({{ id: item.id, previous: state[item.id] || null }});
      const row = {{ ...item.row }};
      row['dj_verdict(good/bad)'] = verdict;
      row['dj_comment'] = comment || '';
      state[item.id] = row;
      save();
      currentIndex = nextIndex(currentIndex + 1);
      render();
    }}

    function skipCurrent() {{
      currentIndex = nextIndex(currentIndex + 1);
      render();
    }}

    function undo() {{
      const last = history.pop();
      if (!last) return;
      if (last.previous) state[last.id] = last.previous;
      else delete state[last.id];
      save();
      currentIndex = APP.items.findIndex((item) => item.id === last.id);
      render();
    }}

    function exportRows() {{
      const rows = APP.items.map((item) => state[item.id] || item.row);
      downloadCsv('exp009_window_swipe.csv', APP.headers, rows);
    }}

    function resetAll() {{
      localStorage.removeItem(STORAGE_KEY);
      Object.keys(state).forEach((key) => delete state[key]);
      history.length = 0;
      currentIndex = 0;
      render();
    }}

    function renderCard(item) {{
      return `
        <div id="cardShell" class="card-shell">
          <article id="card" class="card">
            <div class="topbar">
              <div class="tag">${{item.window_type}}</div>
              <div class="tag warn">Score ${{item.score}}</div>
            </div>
            <div class="title">
              <h2>${{item.title}}</h2>
              <div class="subtitle">${{item.subtitle}}</div>
            </div>
            <div class="metrics">
              <div class="metric"><b>Window</b><span>${{item.window_time}}</span></div>
              <div class="metric"><b>Type</b><span>${{item.window_type}}</span></div>
              <div class="metric"><b>Risk</b><span>${{item.risk}}</span></div>
            </div>
            <div class="copy">${{item.copy}}</div>
            <div class="comment-wrap">
              <label for="commentBox">Quick note (optional)</label>
              <textarea id="commentBox" placeholder="Why would you keep or reject this window?"></textarea>
            </div>
          </article>
        </div>`;
    }}

    function bindDrag() {{
      const shell = document.getElementById('cardShell');
      const card = document.getElementById('card');
      if (!shell || !card) return;
      shell.addEventListener('pointerdown', (event) => {{
        drag = {{ startX: event.clientX }};
        card.classList.add('dragging');
      }});
      shell.addEventListener('pointermove', (event) => {{
        if (!drag) return;
        const dx = event.clientX - drag.startX;
        card.style.transform = `translateX(${{dx}}px) rotate(${{dx / 18}}deg)`;
        card.style.opacity = String(Math.max(0.55, 1 - Math.abs(dx) / 320));
      }});
      function finish(event) {{
        if (!drag) return;
        const dx = event.clientX - drag.startX;
        card.classList.remove('dragging');
        card.style.transform = '';
        card.style.opacity = '';
        drag = null;
        const item = APP.items[currentIndex];
        const comment = document.getElementById('commentBox')?.value?.trim() || '';
        if (dx > 96) setResult(item, 'good', comment);
        else if (dx < -96) setResult(item, 'bad', comment);
      }}
      shell.addEventListener('pointerup', finish);
      shell.addEventListener('pointercancel', finish);
      shell.addEventListener('pointerleave', (event) => {{
        if (!drag) return;
        finish(event);
      }});
    }}

    function render() {{
      if (currentIndex < 0 || currentIndex >= APP.items.length || state[APP.items[currentIndex]?.id]) {{
        currentIndex = nextIndex(0);
      }}
      const decided = Object.keys(state).length;
      if (currentIndex === -1) {{
        deckEl.innerHTML = `
          <div class="empty">
            <h2>Window deck complete.</h2>
            <p>Export the CSV when you want to turn this pass into a validation artifact.</p>
          </div>`;
      }} else {{
        deckEl.innerHTML = renderCard(APP.items[currentIndex]);
        bindDrag();
      }}
      statusEl.innerHTML = `${{decided}} / ${{APP.items.length}} reviewed`;
    }}

    document.getElementById('badBtn').addEventListener('click', () => {{
      const comment = document.getElementById('commentBox')?.value?.trim() || '';
      setResult(APP.items[currentIndex], 'bad', comment);
    }});
    document.getElementById('goodBtn').addEventListener('click', () => {{
      const comment = document.getElementById('commentBox')?.value?.trim() || '';
      setResult(APP.items[currentIndex], 'good', comment);
    }});
    document.getElementById('skipBtn').addEventListener('click', skipCurrent);
    document.getElementById('undoBtn').addEventListener('click', undo);
    document.getElementById('exportBtn').addEventListener('click', exportRows);
    document.getElementById('resetBtn').addEventListener('click', resetAll);
    window.addEventListener('keydown', (event) => {{
      if (['TEXTAREA', 'INPUT'].includes(document.activeElement?.tagName)) return;
      const comment = document.getElementById('commentBox')?.value?.trim() || '';
      if (event.key === 'ArrowLeft') {{ event.preventDefault(); setResult(APP.items[currentIndex], 'bad', comment); }}
      if (event.key === 'ArrowRight') {{ event.preventDefault(); setResult(APP.items[currentIndex], 'good', comment); }}
    }});
    render();
  </script>
</body>
</html>"""
    return _write_text(path, body)


def _render_set_function_page(items: list[dict[str, object]], headers: list[str], path: str | Path) -> Path:
    role_options = ["opener", "builder", "bridge", "peak", "reset", "closer", "tool", "depends"]
    data_json = json.dumps({"items": items, "headers": headers, "roles": role_options}, ensure_ascii=True)
    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>DanceLab Set Function Swipe Review</title>
  <style>{_base_page_style()}</style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <div class="eyebrow">Swipe Review</div>
      <h1>Set Function Deck</h1>
      <p>Right means you agree with the engine role. Left opens a quick role picker so you can set the actual function without staring at a spreadsheet.</p>
      <div class="hud">
        <div class="pill">Arrow right = agree</div>
        <div class="pill">Arrow left = disagree and pick actual role</div>
        <div class="pill">{len(items)} focused cards chosen from the most uncertain roles</div>
      </div>
      <div class="nav"><a href="index.html">Back to review launcher</a></div>
    </section>
    <section id="deck" class="deck"></section>
    <div class="controls">
      <button id="badBtn" class="action bad" type="button">Left / Wrong Role</button>
      <button id="goodBtn" class="action good" type="button">Right / Agree</button>
    </div>
    <div class="footer">
      <button id="skipBtn" class="action ghost" type="button">Skip</button>
      <button id="undoBtn" class="action ghost" type="button">Undo</button>
      <button id="exportBtn" class="action ghost" type="button">Export CSV</button>
      <button id="resetBtn" class="action ghost" type="button">Reset Progress</button>
    </div>
    <div id="status" class="status"></div>
  </main>
  <script>
    const APP = {data_json};
    const STORAGE_KEY = 'dancelab-set-function-swipe-review-v1';
    {_download_script()}

    const deckEl = document.getElementById('deck');
    const statusEl = document.getElementById('status');
    const state = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}');
    const history = [];
    let currentIndex = 0;
    let pickerVisible = false;
    let drag = null;

    function nextIndex(start) {{
      for (let i = start; i < APP.items.length; i += 1) {{
        if (!state[APP.items[i].id]) return i;
      }}
      return -1;
    }}

    function save() {{
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }}

    function finalize(item, role, comment) {{
      history.push({{ id: item.id, previous: state[item.id] || null }});
      const row = {{ ...item.row }};
      row['dj_primary'] = role;
      row['dj_comment'] = comment || '';
      state[item.id] = row;
      save();
      pickerVisible = false;
      currentIndex = nextIndex(currentIndex + 1);
      render();
    }}

    function skipCurrent() {{
      pickerVisible = false;
      currentIndex = nextIndex(currentIndex + 1);
      render();
    }}

    function undo() {{
      const last = history.pop();
      if (!last) return;
      if (last.previous) state[last.id] = last.previous;
      else delete state[last.id];
      save();
      pickerVisible = false;
      currentIndex = APP.items.findIndex((item) => item.id === last.id);
      render();
    }}

    function exportRows() {{
      const rows = APP.items.map((item) => state[item.id] || item.row);
      downloadCsv('exp011_set_function_swipe.csv', APP.headers, rows);
    }}

    function resetAll() {{
      localStorage.removeItem(STORAGE_KEY);
      Object.keys(state).forEach((key) => delete state[key]);
      history.length = 0;
      pickerVisible = false;
      currentIndex = 0;
      render();
    }}

    function renderCard(item) {{
      const picker = APP.roles.map((role) => `<button class="pick" type="button" data-role="${{role}}">${{role}}</button>`).join('');
      return `
        <div id="cardShell" class="card-shell">
          <article id="card" class="card">
            <div class="topbar">
              <div class="tag">${{item.primary}}</div>
              <div class="tag warn">Risk ${{item.risk}}</div>
            </div>
            <div class="title">
              <h2>${{item.title}}</h2>
              <div class="subtitle">${{item.subtitle}}</div>
            </div>
            <div class="metrics">
              <div class="metric"><b>Primary</b><span>${{item.primary}}</span></div>
              <div class="metric"><b>Secondary</b><span>${{item.secondary}}</span></div>
              <div class="metric"><b>Confidence</b><span>${{item.confidence}}</span></div>
              <div class="metric"><b>Risk</b><span>${{item.risk}}</span></div>
            </div>
            <div class="copy">${{item.copy}}</div>
            <div class="comment-wrap">
              <label for="commentBox">Quick note (optional)</label>
              <textarea id="commentBox" placeholder="Why this role works or what it should be instead?"></textarea>
            </div>
            <div id="picker" class="picker ${{pickerVisible ? 'active' : ''}}">
              ${{picker}}
            </div>
          </article>
        </div>`;
    }}

    function bindPicker(item) {{
      document.querySelectorAll('[data-role]').forEach((button) => {{
        button.addEventListener('click', () => {{
          const comment = document.getElementById('commentBox')?.value?.trim() || '';
          finalize(item, button.dataset.role, comment);
        }});
      }});
    }}

    function bindDrag() {{
      const shell = document.getElementById('cardShell');
      const card = document.getElementById('card');
      if (!shell || !card || pickerVisible) return;
      shell.addEventListener('pointerdown', (event) => {{
        drag = {{ startX: event.clientX }};
        card.classList.add('dragging');
      }});
      shell.addEventListener('pointermove', (event) => {{
        if (!drag) return;
        const dx = event.clientX - drag.startX;
        card.style.transform = `translateX(${{dx}}px) rotate(${{dx / 18}}deg)`;
        card.style.opacity = String(Math.max(0.55, 1 - Math.abs(dx) / 320));
      }});
      function finish(event) {{
        if (!drag) return;
        const dx = event.clientX - drag.startX;
        card.classList.remove('dragging');
        card.style.transform = '';
        card.style.opacity = '';
        drag = null;
        const comment = document.getElementById('commentBox')?.value?.trim() || '';
        if (dx > 96) finalize(APP.items[currentIndex], APP.items[currentIndex].primary, comment);
        else if (dx < -96) {{
          pickerVisible = true;
          render();
        }}
      }}
      shell.addEventListener('pointerup', finish);
      shell.addEventListener('pointercancel', finish);
      shell.addEventListener('pointerleave', (event) => {{
        if (!drag) return;
        finish(event);
      }});
    }}

    function render() {{
      if (currentIndex < 0 || currentIndex >= APP.items.length || state[APP.items[currentIndex]?.id]) {{
        currentIndex = nextIndex(0);
      }}
      const decided = Object.keys(state).length;
      if (currentIndex === -1) {{
        deckEl.innerHTML = `
          <div class="empty">
            <h2>Set function deck complete.</h2>
            <p>Export the CSV to feed the next validation pass.</p>
          </div>`;
      }} else {{
        const item = APP.items[currentIndex];
        deckEl.innerHTML = renderCard(item);
        bindPicker(item);
        bindDrag();
      }}
      statusEl.innerHTML = `${{decided}} / ${{APP.items.length}} reviewed`;
    }}

    document.getElementById('badBtn').addEventListener('click', () => {{
      pickerVisible = true;
      render();
    }});
    document.getElementById('goodBtn').addEventListener('click', () => {{
      const comment = document.getElementById('commentBox')?.value?.trim() || '';
      finalize(APP.items[currentIndex], APP.items[currentIndex].primary, comment);
    }});
    document.getElementById('skipBtn').addEventListener('click', skipCurrent);
    document.getElementById('undoBtn').addEventListener('click', undo);
    document.getElementById('exportBtn').addEventListener('click', exportRows);
    document.getElementById('resetBtn').addEventListener('click', resetAll);
    window.addEventListener('keydown', (event) => {{
      if (['TEXTAREA', 'INPUT'].includes(document.activeElement?.tagName)) return;
      const comment = document.getElementById('commentBox')?.value?.trim() || '';
      if (event.key === 'ArrowRight') {{
        event.preventDefault();
        finalize(APP.items[currentIndex], APP.items[currentIndex].primary, comment);
      }}
      if (event.key === 'ArrowLeft') {{
        event.preventDefault();
        pickerVisible = true;
        render();
      }}
    }});
    render();
  </script>
</body>
</html>"""
    return _write_text(path, body)


def _render_control_center_page(
    validation_pack_dir: Path,
    *,
    report_dir: str | Path | None,
    output_dir: Path,
    decision_manifest: DecisionTelemetryManifest | None,
) -> Path:
    decision_root = Path(report_dir) if report_dir is not None else None
    validation_summary_path = validation_pack_dir / "validation_pack_summary.json"
    decision_summary_path = (
        decision_root / "decision_summary.json"
        if decision_root is not None else None
    )
    edge_decisions_path = (
        Path(decision_manifest.artifacts["edge_decisions"])
        if decision_manifest and "edge_decisions" in decision_manifest.artifacts else
        (decision_root / "edge_decisions.json" if decision_root is not None else None)
    )
    mixability_pairs_path = (
        Path(decision_manifest.artifacts["mixability_pairs"])
        if decision_manifest and "mixability_pairs" in decision_manifest.artifacts else
        (decision_root / "mixability_pairs.json" if decision_root is not None else None)
    )
    analysis_summary_path = (
        Path(decision_manifest.artifacts["analysis_summary"])
        if decision_manifest and "analysis_summary" in decision_manifest.artifacts else
        (decision_root / "analysis_summary.json" if decision_root is not None else None)
    )
    bootstrap = _build_control_center_snapshot(
        validation_summary=_read_json(validation_summary_path),
        decision_summary=_read_json(decision_summary_path) if decision_summary_path else None,
        edge_decisions=_read_json(edge_decisions_path) if edge_decisions_path else None,
        mixability_pairs=_read_json(mixability_pairs_path) if mixability_pairs_path else None,
        analysis_summary=_read_json(analysis_summary_path) if analysis_summary_path else None,
    )
    app_json = json.dumps(
        {
            "refresh_ms": 4000,
            "sources": {
                "validation_summary": _relative_href(validation_summary_path, output_dir=output_dir),
                "decision_summary": _relative_href(decision_summary_path, output_dir=output_dir),
                "edge_decisions": _relative_href(edge_decisions_path, output_dir=output_dir),
                "mixability_pairs": _relative_href(mixability_pairs_path, output_dir=output_dir),
                "analysis_summary": _relative_href(analysis_summary_path, output_dir=output_dir),
            },
            "bootstrap": bootstrap,
        },
        ensure_ascii=True,
    )
    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>DanceLab Control Center</title>
  <style>{_base_page_style()}
.toolbar{{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-top:20px;}}
.toolbar .listen-action{{text-decoration:none;}}
.control-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-top:22px;}}
.dash-card{{background:rgba(255,249,239,.94);border:1px solid rgba(120,82,49,.14);border-radius:24px;padding:16px 18px;box-shadow:0 16px 44px rgba(23,33,43,.10);}}
.dash-card b{{display:block;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#7b8794;margin-bottom:6px;}}
.dash-card strong{{display:block;font-size:30px;line-height:1.05;}}
.dash-card span{{display:block;margin-top:8px;color:#586373;font-size:13px;line-height:1.45;}}
.dash-layout{{display:grid;grid-template-columns:1.3fr .9fr;gap:18px;margin-top:22px;}}
.dash-stack{{display:grid;gap:18px;}}
.panel{{background:rgba(255,249,239,.94);border:1px solid rgba(120,82,49,.14);border-radius:28px;padding:18px;box-shadow:0 16px 44px rgba(23,33,43,.10);}}
.panel h2{{margin:0;font-size:24px;}}
.panel p{{margin:10px 0 0;color:#586373;font-size:14px;line-height:1.5;}}
.panel-head{{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:10px;margin-bottom:12px;}}
.spark-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;}}
.spark-card{{border-radius:20px;background:#fffdf8;border:1px solid rgba(120,82,49,.12);padding:12px;}}
.spark-card b{{display:block;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#7b8794;}}
.spark-card span{{display:block;margin-top:8px;font-weight:800;font-size:20px;}}
.spark-card small{{display:block;margin-top:4px;color:#586373;font-size:12px;}}
.sparkline{{display:block;width:100%;height:68px;margin-top:10px;}}
.bar-list{{display:grid;gap:10px;}}
.bar-row{{display:grid;grid-template-columns:140px 1fr 44px;gap:10px;align-items:center;}}
.bar-row label{{font-size:13px;color:#374151;font-weight:700;}}
.bar-track{{height:10px;border-radius:999px;background:rgba(23,33,43,.08);overflow:hidden;}}
.bar-fill{{height:100%;border-radius:999px;background:linear-gradient(90deg,#0f766e,#14b8a6);}}
.bar-row output{{font-size:12px;color:#586373;text-align:right;}}
.pair-list{{display:grid;gap:10px;}}
.pair-item{{border-radius:20px;background:#fffdf8;border:1px solid rgba(120,82,49,.12);padding:12px 14px;}}
.pair-item strong{{display:block;font-size:15px;line-height:1.35;}}
.pair-meta{{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;}}
.pair-meta .chip{{padding:6px 9px;font-size:12px;}}
.warning-list{{display:grid;gap:8px;}}
.warning-item{{display:flex;justify-content:space-between;gap:12px;padding:10px 12px;border-radius:18px;background:#fffdf8;border:1px solid rgba(120,82,49,.12);font-size:13px;color:#374151;}}
.warning-item b{{margin:0;color:#17212b;font-size:13px;letter-spacing:normal;text-transform:none;}}
.scatter-wrap{{margin-top:10px;border-radius:24px;background:#fffdf8;border:1px solid rgba(120,82,49,.12);padding:12px;}}
.scatter-svg{{display:block;width:100%;height:280px;}}
.legend{{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;}}
.legend .chip{{display:inline-flex;align-items:center;gap:8px;}}
.legend-swatch{{width:10px;height:10px;border-radius:999px;display:inline-block;}}
.source-strip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;}}
.source-card{{border-radius:20px;background:#fffdf8;border:1px solid rgba(120,82,49,.12);padding:12px 14px;}}
.source-card b{{display:block;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#7b8794;}}
.source-card strong{{display:block;margin-top:8px;font-size:16px;}}
.source-card span{{display:block;margin-top:6px;color:#586373;font-size:13px;line-height:1.45;}}
.status-note{{margin-top:14px;color:#586373;font-size:14px;line-height:1.5;}}
@media (max-width: 980px){{.dash-layout{{grid-template-columns:1fr;}}}}
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <div class="eyebrow">Live Diagnostics</div>
      <h1>Engine Control Center</h1>
      <p>This is the external dashboard layer. The engine emits sensors and telemetry; this board only reads them, refreshes live, and shows what the system is doing right now.</p>
      <div class="hud" id="heroHud"></div>
      <div class="toolbar">
        <button id="refreshBtn" class="listen-action" type="button">Refresh Now</button>
        <button id="autoBtn" class="listen-action alt" type="button">Auto Refresh: On</button>
        <a class="listen-action alt" href="index.html">Back to launcher</a>
        <a class="listen-action alt" href="listen_board.html">Open listen board</a>
        <a class="listen-action alt" href="pairs.html">Open waveform board</a>
      </div>
      <div id="pollStatus" class="status-note"></div>
    </section>
    <section id="sourceStrip" class="source-strip"></section>
    <section id="metricStrip" class="control-grid"></section>
    <section class="dash-layout">
      <div class="dash-stack">
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2>Live Trends</h2>
              <p>Recent polling history for the core engine sensors.</p>
            </div>
          </div>
          <div id="sparkGrid" class="spark-grid"></div>
        </article>
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2>Pair Risk Surface</h2>
              <p>Compatibility score on one axis, aggregate risk on the other, colored by auto blend profile.</p>
            </div>
          </div>
          <div class="scatter-wrap">
            <div id="scatterMount"></div>
          </div>
          <div id="scatterLegend" class="legend"></div>
        </article>
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2>Best Candidates</h2>
              <p>Top engine pairs by score and confidence.</p>
            </div>
          </div>
          <div id="topPairs" class="pair-list"></div>
        </article>
      </div>
      <div class="dash-stack">
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2>Decision Traffic</h2>
              <p>How the engine is classifying current pair traffic.</p>
            </div>
          </div>
          <div id="decisionCounts" class="bar-list"></div>
        </article>
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2>Blend Profiles</h2>
              <p>Auto overlap styles suggested by the engine sensors.</p>
            </div>
          </div>
          <div id="blendCounts" class="bar-list"></div>
        </article>
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2>Strategies And Tempo</h2>
              <p>Transition families and how feasible the tempo handling looks.</p>
            </div>
          </div>
          <div id="strategyCounts" class="bar-list"></div>
          <div style="height:14px"></div>
          <div id="tempoCounts" class="bar-list"></div>
        </article>
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2>Watch List</h2>
              <p>Pairs with the biggest current sensor pressure.</p>
            </div>
          </div>
          <div id="watchPairs" class="pair-list"></div>
        </article>
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2>Warning Bus</h2>
              <p>Most repeated warning and risk terms across telemetry.</p>
            </div>
          </div>
          <div id="warningList" class="warning-list"></div>
        </article>
      </div>
    </section>
  </main>
  <script>
    const APP = {app_json};
    const PROFILE_COLORS = {{
      bass_swap: '#ef4444',
      tops_swap: '#0ea5e9',
      contour_blend: '#f59e0b',
      plain_blend: '#10b981',
    }};
    const state = {{
      snapshot: APP.bootstrap || {{}},
      history: [],
      autoRefresh: true,
      timer: null,
      lastRefreshAt: null,
      liveMode: 'bootstrap',
      liveNote: 'Showing the build-time snapshot until the first live poll returns.',
    }};

    function numberValue(value, fallback = 0) {{
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : fallback;
    }}

    function average(values) {{
      const nums = values.filter((value) => Number.isFinite(value));
      if (!nums.length) return 0;
      return nums.reduce((sum, value) => sum + value, 0) / nums.length;
    }}

    function labelize(value) {{
      return String(value || 'unknown').replaceAll('_', ' ');
    }}

    function countEntries(values, limit = 8) {{
      const counts = new Map();
      values.forEach((value) => {{
        const label = String(value || '').trim();
        if (!label) return;
        counts.set(label, (counts.get(label) || 0) + 1);
      }});
      return [...counts.entries()]
        .sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0]))
        .slice(0, limit)
        .map(([label, count]) => ({{ label: labelize(label), count }}));
    }}

    function edgePairId(edge) {{
      return String(edge?.annotation_payload?.pair_id || `${{edge?.track_id_a || ''}}__${{edge?.track_id_b || ''}}`);
    }}

    function edgeRisk(edge) {{
      return Math.max(
        numberValue(edge?.bass_conflict_risk, 0),
        numberValue(edge?.vocal_clash_risk, 0),
        numberValue(edge?.harmonic_risk, 0),
        edge?.hard_block ? 1 : 0,
      );
    }}

    function buildSnapshot(payloads) {{
      const validation = payloads.validationSummary && typeof payloads.validationSummary === 'object' ? payloads.validationSummary : {{}};
      const decision = payloads.decisionSummary && typeof payloads.decisionSummary === 'object' ? payloads.decisionSummary : {{}};
      const edges = Array.isArray(payloads.edgeDecisions) ? payloads.edgeDecisions : [];
      const pairs = Array.isArray(payloads.mixabilityPairs) ? payloads.mixabilityPairs : [];
      const analysis = payloads.analysisSummary && typeof payloads.analysisSummary === 'object' ? payloads.analysisSummary : {{}};
      const titleMap = new Map();
      pairs.forEach((row) => {{
        const pairId = String(row?.pair_id || '').trim();
        if (!pairId) return;
        titleMap.set(
          pairId,
          `${{row?.track_a_title || row?.track_a_id || 'Track A'}} -> ${{row?.track_b_title || row?.track_b_id || 'Track B'}}`,
        );
      }});
      const sensorPairs = edges.map((edge) => {{
        const pairId = edgePairId(edge);
        const score = numberValue(edge?.core_dj_compatibility_score?.value, 0);
        const confidence = numberValue(edge?.core_dj_compatibility_score?.confidence, 0);
        return {{
          pair_id: pairId,
          title: titleMap.get(pairId) || `${{edge?.track_id_a || 'Track A'}} -> ${{edge?.track_id_b || 'Track B'}}`,
          score,
          confidence,
          risk: edgeRisk(edge),
          profile: String(edge?.blend_profile_auto || 'plain_blend'),
          strategy: String(edge?.recommended_transition_strategy || 'n/a'),
          decision_class: String(edge?.decision_class || 'unknown'),
          tempo_feasibility: String(edge?.tempo_window_feasibility || 'unknown'),
          tempo_relation: String(edge?.tempo_relation || 'unknown'),
          standard_blend_allowed: Boolean(edge?.standard_blend_allowed),
          hard_block: Boolean(edge?.hard_block),
          bass_risk: numberValue(edge?.bass_conflict_risk, 0),
          vocal_risk: numberValue(edge?.vocal_clash_risk, 0),
          harmonic_risk: numberValue(edge?.harmonic_risk, 0),
          risks: Array.isArray(edge?.risks) ? edge.risks : [],
          warnings: Array.isArray(edge?.warnings) ? edge.warnings : [],
        }};
      }});
      const topPairs = [...sensorPairs]
        .sort((a, b) => (b.score - a.score) || (b.confidence - a.confidence) || (a.risk - b.risk))
        .slice(0, 8);
      const watchPairs = [...sensorPairs]
        .sort((a, b) => (Number(b.hard_block) - Number(a.hard_block)) || (b.risk - a.risk) || (a.score - b.score))
        .slice(0, 8);
      const alertTerms = countEntries(
        [
          ...sensorPairs.flatMap((item) => item.risks),
          ...sensorPairs.flatMap((item) => item.warnings),
          ...(Array.isArray(validation?.warnings) ? validation.warnings : []),
        ],
        10,
      );
      return {{
        track_count: Number(validation?.analyzed_track_count || decision?.track_count || analysis?.track_count || 0),
        pair_count: Number(decision?.ordered_pair_count || sensorPairs.length || 0),
        rated_pair_count: Number(validation?.metrics?.mixability_pairs?.rated_pair_count || 0),
        rated_pair_ratio: numberValue(validation?.completion?.pair_review_rated_row_ratio, 0),
        window_review_ratio: numberValue(validation?.completion?.exp009_reviewed_track_ratio, 0),
        set_function_ratio: numberValue(validation?.completion?.exp011_labeled_track_ratio, 0),
        pair_review_ratio: numberValue(validation?.completion?.pair_review_rated_row_ratio, 0),
        mean_score: average(sensorPairs.map((item) => item.score)),
        mean_confidence: average(sensorPairs.map((item) => item.confidence)),
        mean_risk: average(sensorPairs.map((item) => item.risk)),
        mean_bass_risk: average(sensorPairs.map((item) => item.bass_risk)),
        mean_vocal_risk: average(sensorPairs.map((item) => item.vocal_risk)),
        mean_harmonic_risk: average(sensorPairs.map((item) => item.harmonic_risk)),
        standard_blend_ratio: sensorPairs.length ? sensorPairs.filter((item) => item.standard_blend_allowed).length / sensorPairs.length : 0,
        hard_block_count: sensorPairs.filter((item) => item.hard_block).length,
        decision_counts: countEntries(sensorPairs.map((item) => item.decision_class), 8),
        policy_counts: countEntries(edges.map((edge) => edge?.recommendation_policy || 'review_only'), 8),
        blend_profile_counts: countEntries(sensorPairs.map((item) => item.profile), 8),
        strategy_counts: countEntries(sensorPairs.map((item) => item.strategy), 8),
        tempo_feasibility_counts: countEntries(sensorPairs.map((item) => item.tempo_feasibility), 8),
        tempo_relation_counts: countEntries(sensorPairs.map((item) => item.tempo_relation), 8),
        alert_terms: alertTerms,
        top_pairs: topPairs,
        watch_pairs: watchPairs,
        scatter_points: sensorPairs.slice(0, 120),
        times: {{
          validation_generated_at: String(validation?.generated_at || ''),
          decision_generated_at: String(decision?.generated_at || ''),
          analysis_generated_at: String(analysis?.generated_at || ''),
        }},
        sources_available: {{
          validation: Boolean(Object.keys(validation).length),
          decision: Boolean(Object.keys(decision).length),
          edges: Boolean(edges.length),
          pairs: Boolean(pairs.length),
          analysis: Boolean(Object.keys(analysis).length),
        }},
        warnings: Array.isArray(validation?.warnings) ? validation.warnings.slice(0, 8) : [],
      }};
    }}

    function pct(value) {{
      return `${{Math.round(numberValue(value, 0) * 100)}}%`;
    }}

    function formatNumber(value) {{
      return numberValue(value, 0).toFixed(2);
    }}

    function timeAgo(isoText) {{
      if (!isoText) return 'n/a';
      const stamp = new Date(isoText);
      if (Number.isNaN(stamp.getTime())) return isoText;
      const diffSec = Math.max(0, Math.round((Date.now() - stamp.getTime()) / 1000));
      if (diffSec < 60) return `${{diffSec}}s ago`;
      if (diffSec < 3600) return `${{Math.round(diffSec / 60)}}m ago`;
      return `${{Math.round(diffSec / 3600)}}h ago`;
    }}

    function metricCard(label, value, note) {{
      return `<article class="dash-card"><b>${{label}}</b><strong>${{value}}</strong><span>${{note}}</span></article>`;
    }}

    function barList(entries, emptyCopy) {{
      if (!entries.length) return `<div class="mini">${{emptyCopy}}</div>`;
      const max = Math.max(...entries.map((entry) => entry.count), 1);
      return entries.map((entry) => `
        <div class="bar-row">
          <label>${{entry.label}}</label>
          <div class="bar-track"><div class="bar-fill" style="width:${{(entry.count / max) * 100}}%"></div></div>
          <output>${{entry.count}}</output>
        </div>
      `).join('');
    }}

    function sparklineSvg(values, color) {{
      const width = 240;
      const height = 68;
      const points = values.length ? values : [0];
      const max = Math.max(...points, 1);
      const min = Math.min(...points, 0);
      const span = Math.max(max - min, 0.001);
      const path = points.map((value, index) => {{
        const x = points.length === 1 ? width / 2 : (index / (points.length - 1)) * width;
        const y = height - ((value - min) / span) * (height - 6) - 3;
        return `${{index === 0 ? 'M' : 'L'}}${{x.toFixed(1)}},${{y.toFixed(1)}}`;
      }}).join(' ');
      return `<svg class="sparkline" viewBox="0 0 ${{width}} ${{height}}" preserveAspectRatio="none">
        <path d="${{path}}" fill="none" stroke="${{color}}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>
      </svg>`;
    }}

    function scatterSvg(points) {{
      if (!points.length) return '<div class="mini">No pair telemetry available yet.</div>';
      const width = 520;
      const height = 280;
      const pad = 26;
      const innerWidth = width - (pad * 2);
      const innerHeight = height - (pad * 2);
      const circles = points.map((point) => {{
        const x = pad + (numberValue(point.score, 0) * innerWidth);
        const y = height - pad - (numberValue(point.risk, 0) * innerHeight);
        const color = PROFILE_COLORS[point.profile] || '#64748b';
        return `<circle cx="${{x.toFixed(1)}}" cy="${{y.toFixed(1)}}" r="4.2" fill="${{color}}" opacity="0.88">
          <title>${{point.title}} | score ${{formatNumber(point.score)}} | risk ${{formatNumber(point.risk)}} | ${{labelize(point.profile)}}</title>
        </circle>`;
      }}).join('');
      return `<svg class="scatter-svg" viewBox="0 0 ${{width}} ${{height}}">
        <rect x="${{pad}}" y="${{pad}}" width="${{innerWidth}}" height="${{innerHeight}}" rx="18" fill="#fff9ef" stroke="rgba(120,82,49,.16)"></rect>
        <line x1="${{pad}}" y1="${{height - pad}}" x2="${{width - pad}}" y2="${{height - pad}}" stroke="rgba(23,33,43,.18)"></line>
        <line x1="${{pad}}" y1="${{pad}}" x2="${{pad}}" y2="${{height - pad}}" stroke="rgba(23,33,43,.18)"></line>
        <text x="${{width / 2}}" y="${{height - 4}}" text-anchor="middle" fill="#586373" font-size="12">Compatibility score</text>
        <text x="14" y="${{height / 2}}" text-anchor="middle" fill="#586373" font-size="12" transform="rotate(-90 14 ${{height / 2}})">Aggregate risk</text>
        ${{circles}}
      </svg>`;
    }}

    function pairItems(items, emptyCopy) {{
      if (!items.length) return `<div class="mini">${{emptyCopy}}</div>`;
      return items.map((item) => `
        <div class="pair-item">
          <strong>${{item.title}}</strong>
          <div class="pair-meta">
            <div class="chip">score ${{formatNumber(item.score)}}</div>
            <div class="chip">risk ${{formatNumber(item.risk)}}</div>
            <div class="chip">${{labelize(item.profile)}}</div>
            <div class="chip">${{labelize(item.strategy)}}</div>
          </div>
        </div>
      `).join('');
    }}

    function warningItems(items, emptyCopy) {{
      if (!items.length) return `<div class="mini">${{emptyCopy}}</div>`;
      return items.map((item) => `
        <div class="warning-item">
          <b>${{item.label}}</b>
          <span>${{item.count}}</span>
        </div>
      `).join('');
    }}

    function sourceCards(snapshot) {{
      const times = snapshot.times || {{}};
      const sources = snapshot.sources_available || {{}};
      return [
        {{
          label: 'Validation',
          state: sources.validation ? 'attached' : 'missing',
          note: times.validation_generated_at ? `Generated ${{timeAgo(times.validation_generated_at)}}` : 'Validation summary unavailable.',
        }},
        {{
          label: 'Decision telemetry',
          state: sources.decision ? 'attached' : 'missing',
          note: times.decision_generated_at ? `Generated ${{timeAgo(times.decision_generated_at)}}` : 'Decision manifest unavailable.',
        }},
        {{
          label: 'Pair sensors',
          state: sources.edges ? 'attached' : 'missing',
          note: `${{snapshot.pair_count || 0}} pairs currently visible to the dashboard.`,
        }},
        {{
          label: 'Live poll',
          state: state.liveMode,
          note: state.lastRefreshAt ? `Last refresh ${{timeAgo(new Date(state.lastRefreshAt).toISOString())}}` : state.liveNote,
        }},
      ].map((item) => `
        <article class="source-card">
          <b>${{item.label}}</b>
          <strong>${{labelize(item.state)}}</strong>
          <span>${{item.note}}</span>
        </article>
      `).join('');
    }}

    function render(snapshot) {{
      state.snapshot = snapshot;
      state.history.push({{
        ts: Date.now(),
        mean_score: numberValue(snapshot.mean_score, 0),
        mean_confidence: numberValue(snapshot.mean_confidence, 0),
        mean_risk: numberValue(snapshot.mean_risk, 0),
        pair_review_ratio: numberValue(snapshot.pair_review_ratio, 0),
      }});
      if (state.history.length > 40) state.history.shift();

      document.getElementById('heroHud').innerHTML = `
        <div class="pill">Tracks: ${{snapshot.track_count || 0}}</div>
        <div class="pill">Pairs: ${{snapshot.pair_count || 0}}</div>
        <div class="pill">Rated pairs: ${{snapshot.rated_pair_count || 0}}</div>
        <div class="pill">Hard blocks: ${{snapshot.hard_block_count || 0}}</div>
      `;
      document.getElementById('pollStatus').textContent = state.liveNote;
      document.getElementById('sourceStrip').innerHTML = sourceCards(snapshot);
      document.getElementById('metricStrip').innerHTML = [
        metricCard('Mean score', formatNumber(snapshot.mean_score), 'Average engine compatibility signal across visible pairs.'),
        metricCard('Mean confidence', formatNumber(snapshot.mean_confidence), 'How grounded the current pair traffic is.'),
        metricCard('Mean risk', formatNumber(snapshot.mean_risk), 'Max of bass, vocal, harmonic, and hard-block pressure.'),
        metricCard('Standard blend', pct(snapshot.standard_blend_ratio), 'Pairs where exposed standard overlap stays allowed.'),
        metricCard('Pair review', pct(snapshot.pair_review_ratio), 'How much pair validation has already been rated by a human.'),
        metricCard('Window review', pct(snapshot.window_review_ratio), 'Coverage of transition-window checking.'),
      ].join('');
      document.getElementById('decisionCounts').innerHTML = barList(snapshot.decision_counts || [], 'No decision traffic yet.');
      document.getElementById('blendCounts').innerHTML = barList(snapshot.blend_profile_counts || [], 'No auto blend profiles yet.');
      document.getElementById('strategyCounts').innerHTML = barList(snapshot.strategy_counts || [], 'No strategy counts yet.');
      document.getElementById('tempoCounts').innerHTML = barList(snapshot.tempo_feasibility_counts || [], 'No tempo feasibility counts yet.');
      document.getElementById('topPairs').innerHTML = pairItems(snapshot.top_pairs || [], 'No pair rankings yet.');
      document.getElementById('watchPairs').innerHTML = pairItems(snapshot.watch_pairs || [], 'No watch-list items yet.');
      document.getElementById('warningList').innerHTML = warningItems(snapshot.alert_terms || [], 'No repeated warning terms yet.');
      document.getElementById('scatterMount').innerHTML = scatterSvg(snapshot.scatter_points || []);
      document.getElementById('scatterLegend').innerHTML = Object.entries(PROFILE_COLORS).map(([key, color]) => `
        <div class="chip"><span class="legend-swatch" style="background:${{color}}"></span>${{labelize(key)}}</div>
      `).join('');
      document.getElementById('sparkGrid').innerHTML = [
        {{
          label: 'Mean score',
          value: formatNumber(snapshot.mean_score),
          note: 'Compatibility',
          color: '#0f766e',
          series: state.history.map((entry) => entry.mean_score),
        }},
        {{
          label: 'Mean confidence',
          value: formatNumber(snapshot.mean_confidence),
          note: 'Grounding',
          color: '#0ea5e9',
          series: state.history.map((entry) => entry.mean_confidence),
        }},
        {{
          label: 'Mean risk',
          value: formatNumber(snapshot.mean_risk),
          note: 'Pressure',
          color: '#ef4444',
          series: state.history.map((entry) => entry.mean_risk),
        }},
        {{
          label: 'Pair review',
          value: pct(snapshot.pair_review_ratio),
          note: 'Human coverage',
          color: '#f59e0b',
          series: state.history.map((entry) => entry.pair_review_ratio),
        }},
      ].map((card) => `
        <div class="spark-card">
          <b>${{card.label}}</b>
          <span>${{card.value}}</span>
          <small>${{card.note}}</small>
          ${{sparklineSvg(card.series, card.color)}}
        </div>
      `).join('');
    }}

    async function fetchJson(url) {{
      if (!url) return null;
      const joiner = url.includes('?') ? '&' : '?';
      const response = await fetch(`${{url}}${{joiner}}_=${{Date.now()}}`, {{ cache: 'no-store' }});
      if (!response.ok) {{
        throw new Error(`HTTP ${{response.status}} for ${{url}}`);
      }}
      return response.json();
    }}

    async function refreshNow() {{
      try {{
        const [validationSummary, decisionSummary, edgeDecisions, mixabilityPairs, analysisSummary] = await Promise.all([
          fetchJson(APP.sources.validation_summary),
          fetchJson(APP.sources.decision_summary),
          fetchJson(APP.sources.edge_decisions),
          fetchJson(APP.sources.mixability_pairs),
          fetchJson(APP.sources.analysis_summary),
        ]);
        state.lastRefreshAt = Date.now();
        state.liveMode = 'live';
        state.liveNote = `Live polling active every ${{Math.round(APP.refresh_ms / 1000)}}s. Last pull completed just now.`;
        render(buildSnapshot({{ validationSummary, decisionSummary, edgeDecisions, mixabilityPairs, analysisSummary }}));
      }} catch (error) {{
        state.lastRefreshAt = Date.now();
        state.liveMode = 'fallback';
        const fileHint = window.location.protocol === 'file:' ? ' Open the dashboard over HTTP if you want continuous polling.' : '';
        state.liveNote = `Live polling failed, so the dashboard is showing the latest cached snapshot. ${{String(error)}}.${{fileHint}}`;
        render(state.snapshot || APP.bootstrap || {{}});
      }}
    }}

    function syncAutoState() {{
      const button = document.getElementById('autoBtn');
      if (button) button.textContent = `Auto Refresh: ${{state.autoRefresh ? 'On' : 'Off'}}`;
    }}

    function startPolling() {{
      window.clearInterval(state.timer);
      if (!state.autoRefresh) return;
      state.timer = window.setInterval(() => {{
        void refreshNow();
      }}, APP.refresh_ms);
    }}

    document.getElementById('refreshBtn').addEventListener('click', () => {{
      void refreshNow();
    }});
    document.getElementById('autoBtn').addEventListener('click', () => {{
      state.autoRefresh = !state.autoRefresh;
      syncAutoState();
      startPolling();
    }});

    syncAutoState();
    render(APP.bootstrap || {{}});
    startPolling();
    void refreshNow();
  </script>
</body>
</html>"""
    return _write_text(output_dir / "control_center.html", body)


def _render_index_page(
    pair_count: int,
    window_count: int,
    set_count: int,
    has_pairs: bool,
    has_listen: bool,
    has_control_center: bool,
    output_dir: Path,
) -> Path:
    pair_link = (
        f'<a href="pairs.html">Open pair deck <span class="mini">({pair_count} cards)</span></a>'
        if has_pairs else
        '<span class="pill">Pair deck unavailable until a `decision-report` directory is attached</span>'
    )
    listen_link = (
        f'<a href="listen_board.html">Open listen board <span class="mini">({pair_count} cards)</span></a>'
        if has_listen else
        '<span class="pill">Listen board unavailable until pair telemetry is attached</span>'
    )
    control_center_link = (
        '<a href="control_center.html">Open control center <span class="mini">(live telemetry)</span></a>'
        if has_control_center else
        '<span class="pill">Control center unavailable until telemetry is attached</span>'
    )
    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>DanceLab Swipe Review</title>
  <style>{_base_page_style()}
.launcher{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px;margin-top:22px;}}
.launch-card{{background:rgba(255,249,239,.92);border:1px solid rgba(120,82,49,.14);border-radius:28px;padding:20px;box-shadow:0 20px 48px rgba(23,33,43,.11);}}
.launch-card h2{{margin:0 0 10px;font-size:28px;}}
.launch-card p{{color:#586373;font-size:15px;line-height:1.5;}}
.launch-card a{{display:inline-flex;margin-top:12px;text-decoration:none;background:#17212b;color:#fff9ef;padding:12px 16px;border-radius:999px;font-weight:800;}}
</style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <div class="eyebrow">Pilot Validation</div>
      <h1>Swipe Review Launcher</h1>
      <p>This is the lightweight pass: fewer cards, no spreadsheets, and direct exports back into review-ready CSV layouts. Start with pairs if you want the most visual deck.</p>
      <div class="hud">
        <div class="pill">Pairs: {pair_count}</div>
        <div class="pill">Windows: {window_count}</div>
        <div class="pill">Set function: {set_count}</div>
      </div>
    </section>
    <section class="launcher">
      <article class="launch-card">
        <h2>Waveform Board</h2>
        <p>Waveform cards for a small, track-diverse slice of top pair candidates. Right = accept, left = reject, down = review.</p>
        {pair_link}
      </article>
      <article class="launch-card">
        <h2>Listen Board</h2>
        <p>Dual-player diagnostics with auto cueing, beat sync, and quantize, so Track B starts from the transition fragment against Track A.</p>
        {listen_link}
      </article>
      <article class="launch-card">
        <h2>Control Center</h2>
        <p>Live dashboard for engine sensors: scores, risk pressure, strategy traffic, blend profiles, and telemetry freshness.</p>
        {control_center_link}
      </article>
      <article class="launch-card">
        <h2>Window Deck</h2>
        <p>One strongest candidate window per track. Fast yes/no pass for transition-window usefulness.</p>
        <a href="windows.html">Open window deck <span class="mini">({window_count} cards)</span></a>
      </article>
      <article class="launch-card">
        <h2>Set Function Deck</h2>
        <p>Agree by swiping right. If the role is wrong, swipe left and tap the real one.</p>
        <a href="set_function.html">Open set-function deck <span class="mini">({set_count} cards)</span></a>
      </article>
    </section>
  </main>
</body>
</html>"""
    return _write_text(output_dir / "index.html", body)


def build_swipe_review_bundle(
    validation_pack_dir: str | Path,
    *,
    report_dir: str | Path | None = None,
    max_pairs: int = 8,
    max_windows: int = 8,
    max_functions: int = 8,
) -> dict[str, Path]:
    validation_pack_dir = Path(validation_pack_dir)
    output_dir = validation_pack_dir / "swipe_review"
    output_dir.mkdir(parents=True, exist_ok=True)
    repo_root = validation_pack_dir.parents[2]
    decision_manifest = _load_decision_manifest(report_dir)
    waveform_gallery_path = (
        os.path.relpath(Path(decision_manifest.artifacts["waveform_index"]), output_dir)
        if decision_manifest and "waveform_index" in decision_manifest.artifacts else
        (
            os.path.relpath(Path(report_dir) / "waveforms" / "index.html", output_dir)
            if report_dir is not None else None
        )
    )
    processed_dir = (
        Path(decision_manifest.analysis_root)
        if decision_manifest is not None else
        (
            Path(report_dir).parents[1] / Path(report_dir).name / "processed"
            if report_dir is not None else None
        )
    )
    if processed_dir is not None and not processed_dir.exists():
        processed_dir = None

    window_headers, window_rows = _read_csv_rows(validation_pack_dir / "exp009_dj_window_review_subset.csv")
    set_headers, set_rows = _read_csv_rows(validation_pack_dir / "exp011_set_function_review_subset.csv")
    pair_headers, pair_rows = ([], [])
    if report_dir is not None:
        pair_review_path = (
            Path(decision_manifest.artifacts["edge_decision_review"])
            if decision_manifest and "edge_decision_review" in decision_manifest.artifacts
            else Path(report_dir) / "edge_decision_review.csv"
        )
        pair_headers, pair_rows = _read_csv_rows(pair_review_path)

    selected_windows = _select_window_rows(window_rows, max_windows)
    selected_sets = _select_set_function_rows(set_rows, max_functions)

    pair_items: list[dict[str, object]] = []
    processed_cache: dict[str, dict[str, object]] = {}
    if pair_rows:
        row_by_pair_id = {row.get("pair_id", ""): row for row in pair_rows}
        mix_rows_path = (
            Path(decision_manifest.artifacts["mixability_pairs"])
            if decision_manifest and "mixability_pairs" in decision_manifest.artifacts
            else Path(report_dir) / "mixability_pairs.json"
        )
        mix_rows = _read_json(mix_rows_path)
        waveforms_dir = (
            Path(decision_manifest.artifacts["waveform_index"]).parent
            if decision_manifest and "waveform_index" in decision_manifest.artifacts
            else (Path(report_dir) / "waveforms" if report_dir else None)
        )
        waveforms = sorted(waveforms_dir.glob("pair_*.svg")) if waveforms_dir else []
        if isinstance(mix_rows, list) and waveforms:
            enriched: list[dict[str, object]] = []
            for rank, (mix_row, svg_path) in enumerate(zip(mix_rows, waveforms), start=1):
                pair_id = str(mix_row.get("pair_id", ""))
                edge_row = row_by_pair_id.get(pair_id)
                if edge_row is None:
                    continue
                enriched.append(
                    {
                        "pair_id": pair_id,
                        "rank": rank,
                        "row": edge_row,
                        "image_path": Path(svg_path),
                    }
                )
            selected_pair_rows = _select_diverse_pair_rows([item["row"] for item in enriched], max_pairs)
            enriched_by_pair = {item["pair_id"]: item for item in enriched}
            for row in selected_pair_rows:
                enriched_item = enriched_by_pair.get(row.get("pair_id", ""))
                preview_data = _build_pair_preview_data(
                    row,
                    repo_root=repo_root,
                    output_dir=output_dir,
                    processed_dir=processed_dir,
                    processed_cache=processed_cache,
                )
                pair_items.append(
                    {
                        "id": row.get("pair_id", ""),
                        "row": row,
                        "rank_label": "Pair card",
                        "policy_label": (row.get("engine_recommendation_policy", "review_only") or "review only").replace("_", " "),
                        "title": f"{row.get('title_a', row.get('track_id_a', 'Track A'))} -> {row.get('title_b', row.get('track_id_b', 'Track B'))}",
                        "subtitle": f"{row.get('engine_decision_class', 'candidate').replace('_', ' ')} under the current model",
                        "score": row.get("engine_score", ""),
                        "confidence": row.get("engine_confidence", ""),
                        "strategy": (row.get("engine_strategy", "") or "n/a").replace("_", " "),
                        "window_pair": f"{row.get('engine_pair_window_a(mm:ss)', '')} / {row.get('engine_pair_window_b(mm:ss)', '')}",
                        "copy": "Would you actually play this transition in a set? Right keeps it. Left kills it. Down means another listen is needed.",
                        "risks": [risk for risk in (row.get("engine_risks", "") or "").split(";") if risk][:3],
                        "image_path": (
                            os.path.relpath(Path(enriched_item["image_path"]), output_dir)
                            if enriched_item is not None else None
                        ),
                        "image_alt": f"{row.get('title_a', 'Track A')} to {row.get('title_b', 'Track B')} waveform",
                        "waveform_gallery_path": waveform_gallery_path,
                        **preview_data,
                    }
                )
        else:
            for row in _select_diverse_pair_rows(pair_rows, max_pairs):
                preview_data = _build_pair_preview_data(
                    row,
                    repo_root=repo_root,
                    output_dir=output_dir,
                    processed_dir=processed_dir,
                    processed_cache=processed_cache,
                )
                pair_items.append(
                    {
                        "id": row.get("pair_id", ""),
                        "row": row,
                        "rank_label": "Pair card",
                        "policy_label": (row.get("engine_recommendation_policy", "review_only") or "review only").replace("_", " "),
                        "title": f"{row.get('title_a', row.get('track_id_a', 'Track A'))} -> {row.get('title_b', row.get('track_id_b', 'Track B'))}",
                        "subtitle": f"{row.get('engine_decision_class', 'candidate').replace('_', ' ')} under the current model",
                        "score": row.get("engine_score", ""),
                        "confidence": row.get("engine_confidence", ""),
                        "strategy": (row.get("engine_strategy", "") or "n/a").replace("_", " "),
                        "window_pair": f"{row.get('engine_pair_window_a(mm:ss)', '')} / {row.get('engine_pair_window_b(mm:ss)', '')}",
                        "copy": "Would you actually play this transition in a set? Right keeps it. Left kills it. Down means another listen is needed.",
                        "risks": [risk for risk in (row.get("engine_risks", "") or "").split(";") if risk][:3],
                        "image_path": None,
                        "image_alt": "",
                        "waveform_gallery_path": waveform_gallery_path,
                        **preview_data,
                    }
                )

    window_items = [
        {
            "id": row.get("window_id", f"window-{index}"),
            "row": row,
            "title": row.get("title", row.get("track_id", "Track")),
            "subtitle": "Fast yes/no pass for whether this engine-picked window is actually useful",
            "window_type": (row.get("engine_window_type", "window") or "window").replace("_", " "),
            "window_time": row.get("engine_window(mm:ss)", ""),
            "score": row.get("engine_score", ""),
            "risk": row.get("engine_risk", ""),
            "copy": "You are only judging the engine suggestion itself here. No need to type your own replacement window unless you want to leave a note.",
        }
        for index, row in enumerate(selected_windows, start=1)
    ]

    set_items = [
        {
            "id": row.get("track_id", f"track-{index}"),
            "row": row,
            "title": row.get("title", row.get("track_id", "Track")),
            "subtitle": "Agree with the engine role or quickly tap the real one",
            "primary": row.get("engine_primary", ""),
            "secondary": row.get("engine_secondary", "") or "none",
            "confidence": row.get("engine_conf", ""),
            "risk": row.get("engine_risk", ""),
            "copy": "Right keeps the predicted role. Left opens a short list so you can replace it without touching a table.",
        }
        for index, row in enumerate(selected_sets, start=1)
    ]

    pair_page = _render_pair_page(pair_items, pair_headers, output_dir / "pairs.html")
    listen_page = _render_listen_page(pair_items, pair_headers, output_dir / "listen_board.html")
    control_center_page = _render_control_center_page(
        validation_pack_dir,
        report_dir=report_dir,
        output_dir=output_dir,
        decision_manifest=decision_manifest,
    )
    window_page = _render_window_page(window_items, window_headers, output_dir / "windows.html")
    set_page = _render_set_function_page(set_items, set_headers, output_dir / "set_function.html")
    index_page = _render_index_page(
        pair_count=len(pair_items),
        window_count=len(window_items),
        set_count=len(set_items),
        has_pairs=bool(pair_items),
        has_listen=bool(pair_items),
        has_control_center=True,
        output_dir=output_dir,
    )
    return {
        "swipe_review_index": index_page,
        "swipe_review_pairs": pair_page,
        "swipe_review_listen": listen_page,
        "swipe_review_control_center": control_center_page,
        "swipe_review_windows": window_page,
        "swipe_review_set_function": set_page,
    }
