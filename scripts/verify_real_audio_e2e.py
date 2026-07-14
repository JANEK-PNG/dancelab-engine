#!/usr/bin/env python3
"""Verify a real DanceLab analysis -> set -> preview -> Rekordbox run.

This script consumes analyses produced by the normal engine pipeline. It does
not use fixtures or synthetic audio. The JSON and Markdown reports separate
pipeline integrity checks from measurement values that still need DJ review.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlparse

import numpy as np

from dancelab.core.config import load_config, load_weights
from dancelab.core.models import AnalysisResult, TransitionWindowInput, WindowType
from dancelab.decision.tempo_adjustment import nearest_octave_candidate
from dancelab.decision.transition_windows import detect_transition_windows, rank_windows_for_role
from dancelab.host.preview_timing import snap_to_grid
from dancelab.host.transition_simulation import plan_transition_duration, render_transition_preview
from dancelab.storage.repositories import FileAnalysisRepository


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("processed_dir", type=Path)
    parser.add_argument("rekordbox_xml", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--requested-beats", type=int, default=64)
    return parser


def _source_from_location(location: str) -> Path:
    parsed = urlparse(location)
    return Path(unquote(parsed.path)).resolve()


def _bpm(analysis: AnalysisResult) -> float | None:
    if analysis.beatgrid is not None and analysis.beatgrid.reliable:
        return float(analysis.beatgrid.bpm)
    if analysis.track.bpm_estimate:
        return float(analysis.track.bpm_estimate)
    return None


def _detect_windows(
    analysis: AnalysisResult,
    *,
    top_k: int,
    weights,
):
    return detect_transition_windows(
        TransitionWindowInput(
            track_id=analysis.track.track_id,
            segments=analysis.segments,
            feature_frames=analysis.features,
            beatgrid=analysis.beatgrid,
        ),
        weights.transition_window,
        top_k=top_k,
    ).windows


def _ranked_window(
    analysis: AnalysisResult,
    windows,
    role: WindowType,
    *,
    transition_beats: int,
):
    bpm = _bpm(analysis)
    ranked = rank_windows_for_role(
        windows,
        role,
        track_duration_sec=analysis.track.duration_sec,
        bpm=bpm,
        transition_beats=transition_beats,
        allow_infeasible_fallback=False,
    )
    return ranked[0] if ranked else None


def _quantized_cue(analysis: AnalysisResult, cue_sec: float) -> float:
    beatgrid = analysis.beatgrid
    if beatgrid is None or not beatgrid.reliable:
        return float(cue_sec)
    return snap_to_grid(
        float(cue_sec),
        beatgrid.beat_times_sec,
        beatgrid.downbeats_sec,
        grid_beats=8,
    )


def _check_beat_alignment(analysis: AnalysisResult, cue_sec: float) -> tuple[bool, str]:
    beatgrid = analysis.beatgrid
    if beatgrid is None or not beatgrid.reliable or not beatgrid.beat_times_sec:
        return False, "reliable beatgrid unavailable"
    nearest_index = min(
        range(len(beatgrid.beat_times_sec)),
        key=lambda index: abs(beatgrid.beat_times_sec[index] - float(cue_sec)),
    )
    timing_error_sec = abs(beatgrid.beat_times_sec[nearest_index] - float(cue_sec))
    aligned = timing_error_sec <= 0.025
    return aligned, f"tracked_beat={nearest_index}, error={timing_error_sec:.4f}s"


def _markdown(report: dict[str, object]) -> str:
    lines = [
        "# DanceLab real-audio E2E",
        "",
        f"Status: **{report['status']}**",
        f"Checks: {report['passed_checks']}/{report['check_count']} passed",
        "",
        "## Tracks",
        "",
        "| Order | Title | Artist | BPM | Grid quality | Hot cues |",
        "|---:|---|---|---:|---:|---:|",
    ]
    for index, track in enumerate(report["tracks"], start=1):
        lines.append(
            f"| {index} | {track['title']} | {track['artist']} | "
            f"{track['bpm']} | {track['beatgrid_quality']} | {track['hot_cues']} |"
        )
    preview = report.get("preview")
    if preview:
        lines.extend(
            [
                "",
                "## Rendered transition",
                "",
                f"- A: {preview['track_a']} @ {preview['cue_a_sec']:.3f}s",
                f"- B: {preview['track_b']} @ {preview['cue_b_sec']:.3f}s",
                f"- Duration: {preview['duration_beats']} beats / "
                f"{preview['duration_sec']:.3f}s",
                f"- Tempo: {preview['preview_bpm']:.3f} BPM, "
                f"B rate x{preview['playback_rate_b']:.5f}",
                f"- Audio: {preview['channels']} ch, {preview['sample_rate']} Hz, "
                f"{preview['output_subtype']}",
            ]
        )
    failed = [item for item in report["checks"] if not item["passed"]]
    lines.extend(["", "## Failed checks", ""])
    if failed:
        lines.extend(f"- {item['name']}: {item['detail']}" for item in failed)
    else:
        lines.append("None.")
    lines.extend(["", "## Measurement review", ""])
    lines.append(
        "A passing E2E proves identity, orchestration, cue export and rendering. "
        "It does not make estimated BPM/key/structure ground truth; those values "
        "remain inputs to the separate large-library validation."
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = _parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    repo = FileAnalysisRepository(args.processed_dir)
    analyses = [repo.get(track_id) for track_id in repo.list_track_ids()]
    by_source = {
        Path(analysis.track.source_path).resolve(): analysis
        for analysis in analyses
        if analysis.track.source_path
    }

    xml_root = ET.parse(args.rekordbox_xml).getroot()
    xml_tracks = xml_root.findall("./COLLECTION/TRACK")
    ordered: list[AnalysisResult] = []
    missing_sources: list[str] = []
    for node in xml_tracks:
        source = _source_from_location(node.attrib.get("Location", ""))
        analysis = by_source.get(source)
        if analysis is None:
            missing_sources.append(str(source))
        else:
            ordered.append(analysis)

    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check("analysis_count", len(analyses) >= 2, f"{len(analyses)} analyses")
    check(
        "unique_track_ids",
        len({item.track.track_id for item in analyses}) == len(analyses),
        f"{len(analyses)} analyses",
    )
    check(
        "unique_source_paths",
        len(by_source) == len(analyses),
        f"{len(by_source)} mapped sources",
    )
    check(
        "xml_identity_mapping",
        not missing_sources and len(ordered) == len(xml_tracks) == len(analyses),
        f"xml={len(xml_tracks)}, mapped={len(ordered)}, missing={missing_sources}",
    )
    check(
        "rekordbox_keeps_native_bpm_grid",
        all("AverageBpm" not in node.attrib for node in xml_tracks)
        and not xml_root.findall(".//TEMPO"),
        "AverageBpm and TEMPO must be absent by default",
    )

    cue_counts: dict[str, int] = {}
    cue_alignment_failures: list[str] = []
    duplicate_cue_tracks: list[str] = []
    for node, analysis in zip(xml_tracks, ordered, strict=False):
        markers = node.findall("POSITION_MARK")
        cue_counts[analysis.track.track_id] = len(markers)
        starts = [float(marker.attrib["Start"]) for marker in markers]
        if len({round(value, 3) for value in starts}) != len(starts):
            duplicate_cue_tracks.append(analysis.track.track_id)
        for cue_sec in starts:
            aligned, detail = _check_beat_alignment(analysis, cue_sec)
            if not aligned:
                cue_alignment_failures.append(
                    f"{analysis.track.track_id}@{cue_sec:.3f}s ({detail})"
                )
    check(
        "hot_cues_present",
        bool(ordered) and all(1 <= cue_counts.get(item.track.track_id, 0) <= 4 for item in ordered),
        str(cue_counts),
    )
    check(
        "hot_cues_unique_per_track",
        not duplicate_cue_tracks,
        str(duplicate_cue_tracks),
    )
    check(
        "hot_cues_on_detected_beats",
        not cue_alignment_failures,
        str(cue_alignment_failures[:8]),
    )

    cfg = load_config(args.config)
    weights = load_weights(cfg.weights_file)
    top_k = max(cfg.analysis.transition_top_n, 6)
    windows = {
        analysis.track.track_id: _detect_windows(analysis, top_k=top_k, weights=weights)
        for analysis in ordered
    }

    preview_payload: dict[str, object] | None = None
    pair_failure = "no adjacent pair has reliable grids and safe mix-out/mix-in windows"
    for analysis_a, analysis_b in zip(ordered, ordered[1:]):
        bpm_a = _bpm(analysis_a)
        bpm_b = _bpm(analysis_b)
        if bpm_a is None or bpm_b is None:
            continue
        window_a = _ranked_window(
            analysis_a,
            windows[analysis_a.track.track_id],
            WindowType.mix_out,
            transition_beats=args.requested_beats,
        )
        window_b = _ranked_window(
            analysis_b,
            windows[analysis_b.track.track_id],
            WindowType.mix_in,
            transition_beats=args.requested_beats,
        )
        if window_a is None or window_b is None:
            continue
        cue_a = _quantized_cue(analysis_a, window_a.start_sec)
        cue_b = _quantized_cue(analysis_b, window_b.start_sec)
        duration_a = float(analysis_a.track.duration_sec or 0.0)
        duration_b = float(analysis_b.track.duration_sec or 0.0)
        metrical_b = nearest_octave_candidate(bpm_a, bpm_b)
        rate_b = bpm_a / metrical_b.bpm
        available_a = max(duration_a - cue_a, 0.0) * bpm_a / 60.0
        available_b = max(duration_b - cue_b, 0.0) / rate_b * bpm_a / 60.0
        duration_plan = plan_transition_duration(
            args.requested_beats,
            available_a_beats=available_a,
            available_b_beats=available_b,
        )
        if duration_plan.selected_beats is None:
            continue
        source_a = Path(analysis_a.track.source_path or "")
        source_b = Path(analysis_b.track.source_path or "")
        if not source_a.exists() or not source_b.exists():
            continue
        output_path = args.output_dir / "transition_preview.wav"
        rendered = render_transition_preview(
            source_a=source_a,
            source_b=source_b,
            cue_a_sec=cue_a,
            cue_b_sec=cue_b,
            bpm_master=bpm_a,
            playback_rate_b=rate_b,
            profile_id="bass_swap",
            output_path=output_path,
            duration_beats=duration_plan.selected_beats,
            grid_beats=8,
        )
        try:
            import soundfile as sf
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("soundfile is required for E2E audio verification") from exc
        audio, sample_rate = sf.read(output_path, always_2d=True, dtype="float32")
        tail = audio[-max(1, sample_rate // 2) :]
        tail_rms = float(np.sqrt(np.mean(np.square(tail), dtype=np.float64)))
        preview_payload = {
            "track_a": analysis_a.track.title or analysis_a.track.track_id,
            "track_b": analysis_b.track.title or analysis_b.track.track_id,
            "source_file_a": source_a.name,
            "source_file_b": source_b.name,
            "cue_a_sec": rendered.cue_a_sec,
            "cue_b_sec": rendered.cue_b_sec,
            "duration_beats": rendered.envelope.duration_beats,
            "duration_sec": rendered.duration_sec,
            "preview_bpm": rendered.preview_bpm,
            "playback_rate_b": rendered.playback_rate_b,
            "octave_b": metrical_b.octave_exponent,
            "channels": rendered.channels,
            "sample_rate": rendered.sample_rate,
            "output_subtype": rendered.output_subtype,
            "tail_rms": tail_rms,
            "output_path": str(output_path),
            "duration_plan": asdict(duration_plan),
        }
        check("preview_file_written", output_path.exists(), str(output_path))
        check(
            "preview_pcm24_stereo",
            rendered.output_subtype == "PCM_24" and rendered.channels == 2,
            f"{rendered.output_subtype}, {rendered.channels} channels",
        )
        check("preview_has_no_silent_tail", tail_rms > 1e-5, f"tail RMS={tail_rms:.8f}")
        pair_failure = ""
        break

    check("renderable_transition_pair", preview_payload is not None, pair_failure)

    track_rows = []
    for analysis in ordered:
        beatgrid = analysis.beatgrid
        track_rows.append(
            {
                "track_id": analysis.track.track_id,
                "title": analysis.track.title or "",
                "artist": analysis.track.artist or "",
                "source_file": Path(analysis.track.source_path or "").name,
                "bpm": _bpm(analysis),
                "beatgrid_reliable": bool(beatgrid and beatgrid.reliable),
                "beatgrid_quality": beatgrid.quality_score if beatgrid else None,
                "hot_cues": cue_counts.get(analysis.track.track_id, 0),
            }
        )
    passed = sum(1 for item in checks if item["passed"])
    report: dict[str, object] = {
        "status": "PASS" if passed == len(checks) else "FAIL",
        "check_count": len(checks),
        "passed_checks": passed,
        "checks": checks,
        "tracks": track_rows,
        "preview": preview_payload,
        "analysis_cache_track_count": len(analyses),
        "rekordbox_xml_file": args.rekordbox_xml.name,
    }
    json_path = args.output_dir / "summary.json"
    markdown_path = args.output_dir / "summary.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    print(f"{report['status']}: {passed}/{len(checks)} checks")
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
