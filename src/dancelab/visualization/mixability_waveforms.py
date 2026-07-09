"""Waveform-based visualization for top mixability pairs."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from dancelab.contracts.telemetry import DecisionTelemetryManifest
from dancelab.core.models import AnalysisResult

_BG = "#f4efe6"
_PANEL = "#fff9ef"
_INK = "#1f2933"
_MUTED = "#5c6773"
_GRID = "#d4c9b8"
_A = "#0f766e"
_B = "#c2410c"
_A_HI = "#14b8a6"
_B_HI = "#fb923c"
_RISK = "#f59e0b"
_SCORE = "#111827"


@dataclass
class WaveformTrack:
    title: str
    duration_sec: float
    window_start_sec: float
    window_end_sec: float
    window_label: str
    peaks: list[tuple[float, float]]
    base_color: str
    accent_color: str


@dataclass
class MixabilityWaveformPair:
    rank: int
    mixability_score: float
    confidence: float
    risks: list[str]
    pair_score: float | None
    track_a: WaveformTrack
    track_b: WaveformTrack
    recommendation_policy: str | None = None
    decision_class: str | None = None
    recommended_strategy: str | None = None
    candidate_note: str | None = None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80] or "pair"


def _fmt_sec(value: float) -> str:
    total = max(int(round(value)), 0)
    minutes, seconds = divmod(total, 60)
    return f"{minutes}:{seconds:02d}"


def _load_peaks(source_path: str, bins: int = 1000, sample_rate: int = 11025) -> list[tuple[float, float]]:
    import librosa

    samples, _ = librosa.load(source_path, sr=sample_rate, mono=True)
    if len(samples) == 0:
        return [(0.0, 0.0)] * bins
    max_abs = float(np.max(np.abs(samples)))
    if max_abs > 1e-9:
        samples = samples / max_abs
    edges = np.linspace(0, len(samples), num=bins + 1, dtype=int)
    peaks: list[tuple[float, float]] = []
    for start, end in zip(edges[:-1], edges[1:]):
        if end <= start:
            peaks.append((0.0, 0.0))
            continue
        chunk = samples[start:end]
        peaks.append((float(chunk.min()), float(chunk.max())))
    return peaks


def _waveform_polygon(
    peaks: list[tuple[float, float]],
    *,
    x: float,
    y_mid: float,
    width: float,
    height: float,
) -> str:
    if not peaks:
        return ""
    step = width / max(len(peaks) - 1, 1)
    upper: list[str] = []
    lower: list[str] = []
    scale = height / 2.2
    for idx, (low, high) in enumerate(peaks):
        px = x + idx * step
        upper.append(f"{px:.2f},{(y_mid - high * scale):.2f}")
        lower.append(f"{px:.2f},{(y_mid - low * scale):.2f}")
    return " ".join(upper + list(reversed(lower)))


def _window_rect(
    start_sec: float,
    end_sec: float,
    duration_sec: float,
    *,
    x: float,
    width: float,
) -> tuple[float, float]:
    if duration_sec <= 0:
        return x, 0.0
    start = x + np.clip(start_sec / duration_sec, 0.0, 1.0) * width
    end = x + np.clip(end_sec / duration_sec, 0.0, 1.0) * width
    return float(start), float(max(end - start, 2.0))


def _risk_badges(risks: list[str], x: float, y: float) -> str:
    if not risks:
        return ""
    out: list[str] = []
    cursor = x
    for risk in risks[:3]:
        label = html.escape(risk)
        width = max(120, 7.2 * len(risk))
        out.append(
            f'<rect x="{cursor:.1f}" y="{y:.1f}" rx="14" ry="14" width="{width:.1f}" '
            f'height="28" fill="{_RISK}" fill-opacity="0.16" stroke="{_RISK}" stroke-opacity="0.45"/>'
        )
        out.append(
            f'<text x="{cursor + 12:.1f}" y="{y + 18:.1f}" font-size="13" fill="{_INK}">{label}</text>'
        )
        cursor += width + 10
    return "".join(out)


def _render_track_lane(track: WaveformTrack, *, x: float, y: float, width: float) -> str:
    poly = _waveform_polygon(track.peaks, x=x, y_mid=y + 42, width=width, height=72)
    win_x, win_w = _window_rect(
        track.window_start_sec,
        track.window_end_sec,
        track.duration_sec,
        x=x,
        width=width,
    )
    label_x = min(win_x + 8, x + width - 220)
    return "".join(
        [
            f'<text x="{x:.1f}" y="{y - 8:.1f}" font-size="18" font-weight="700" fill="{_INK}">'
            f"{html.escape(track.title)}</text>",
            f'<text x="{x:.1f}" y="{y + 12:.1f}" font-size="13" fill="{_MUTED}">'
            f"{html.escape(track.window_label)}</text>",
            f'<rect x="{x:.1f}" y="{y + 6:.1f}" width="{width:.1f}" height="72" rx="18" '
            f'fill="{track.base_color}" fill-opacity="0.07" stroke="{_GRID}" stroke-opacity="0.55"/>',
            f'<rect x="{win_x:.1f}" y="{y + 8:.1f}" width="{win_w:.1f}" height="68" rx="16" '
            f'fill="{track.accent_color}" fill-opacity="0.22" stroke="{track.accent_color}" stroke-opacity="0.7"/>',
            f'<polygon points="{poly}" fill="{track.base_color}" fill-opacity="0.9"/>',
            f'<line x1="{x:.1f}" y1="{y + 42:.1f}" x2="{x + width:.1f}" y2="{y + 42:.1f}" '
            f'stroke="{_GRID}" stroke-opacity="0.8"/>',
            f'<text x="{x:.1f}" y="{y + 98:.1f}" font-size="12" fill="{_MUTED}">0:00</text>',
            f'<text x="{x + width - 42:.1f}" y="{y + 98:.1f}" font-size="12" fill="{_MUTED}">'
            f"{_fmt_sec(track.duration_sec)}</text>",
            f'<text x="{label_x:.1f}" y="{y + 28:.1f}" font-size="12" font-weight="700" '
            f'fill="{_SCORE}">{html.escape(track.window_label)}</text>',
        ]
    )


def render_pair_waveform_svg(pair: MixabilityWaveformPair, out_path: str | Path) -> Path:
    width = 1440
    height = 420
    margin_x = 72
    lane_width = width - 2 * margin_x
    score_fill = max(0.0, min(pair.mixability_score, 1.0)) * 320.0
    pair_score = f"{pair.pair_score:.3f}" if pair.pair_score is not None else "n/a"
    strategy_line = ""
    if pair.decision_class or pair.recommended_strategy:
        decision = pair.decision_class.replace("_", " ") if pair.decision_class else "candidate"
        strategy = pair.recommended_strategy.replace("_", " ") if pair.recommended_strategy else "n/a"
        policy = pair.recommendation_policy.replace("_", " ") if pair.recommendation_policy else "review only"
        strategy_line = (
            f'<text x="{margin_x}" y="164" font-size="14" fill="{_MUTED}">'
            f"Decision class {html.escape(decision)} · policy {html.escape(policy)} · suggested strategy {html.escape(strategy)}</text>"
        )
    note = (
        pair.candidate_note
        or "Candidate overlap under the current model. Verify by ear before performance use."
    )
    body = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{_BG}"/>',
        f'<rect x="26" y="26" width="{width - 52}" height="{height - 52}" rx="28" fill="{_PANEL}" stroke="{_GRID}" stroke-width="1.5"/>',
        '<style>text{font-family:"Avenir Next","Futura","Trebuchet MS",sans-serif;}</style>',
        f'<text x="{margin_x}" y="70" font-size="18" font-weight="800" fill="{_MUTED}">CANDIDATE MIXABILITY PAIR #{pair.rank}</text>',
        f'<text x="{margin_x}" y="112" font-size="34" font-weight="800" fill="{_INK}">{html.escape(pair.track_a.title)} → {html.escape(pair.track_b.title)}</text>',
        f'<text x="{margin_x}" y="146" font-size="15" fill="{_MUTED}">Mixability score {pair.mixability_score:.4f} · confidence {pair.confidence:.2f} · pair window score {pair_score}</text>',
        strategy_line,
        f'<rect x="{margin_x}" y="168" width="320" height="14" rx="7" fill="{_GRID}" fill-opacity="0.55"/>',
        f'<rect x="{margin_x}" y="168" width="{score_fill:.1f}" height="14" rx="7" fill="{_SCORE}"/>',
        _risk_badges(pair.risks, margin_x + 350, 154),
        f'<text x="{margin_x}" y="196" font-size="13" fill="{_MUTED}">{html.escape(note)}</text>',
        _render_track_lane(pair.track_a, x=margin_x, y=218, width=lane_width),
        _render_track_lane(pair.track_b, x=margin_x, y=322, width=lane_width),
        "</svg>",
    ]
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(body))
    return path


def render_overview_svg(pairs: list[MixabilityWaveformPair], out_path: str | Path) -> Path:
    card_height = 420
    gap = 26
    width = 1440
    height = 40 + len(pairs) * (card_height + gap)
    body = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{_BG}"/>',
        '<style>text{font-family:"Avenir Next","Futura","Trebuchet MS",sans-serif;}</style>',
        '<text x="52" y="56" font-size="28" font-weight="800" fill="#1f2933">DanceLab Top Mixability Pairs</text>',
        '<text x="52" y="84" font-size="15" fill="#5c6773">Waveforms with highlighted mix-out and mix-in windows</text>',
    ]
    for idx, pair in enumerate(pairs):
        y = 110 + idx * (card_height + gap)
        svg = Path(render_pair_waveform_svg(pair, Path(out_path).with_name(f"_tmp_{idx}.svg"))).read_text()
        inner = svg.split(">", 1)[1].rsplit("</svg>", 1)[0]
        body.append(f'<g transform="translate(0,{y})">{inner}</g>')
        Path(Path(out_path).with_name(f"_tmp_{idx}.svg")).unlink(missing_ok=True)
    body.append("</svg>")
    path = Path(out_path)
    path.write_text("".join(body))
    return path


def render_mixability_waveform_gallery(
    report_root: str | Path,
    *,
    top_n: int = 10,
    bins: int = 1000,
) -> dict[str, Path]:
    report_dir = Path(report_root)
    decision_manifest = DecisionTelemetryManifest.model_validate_json(
        (report_dir / "decision_summary.json").read_text()
    )
    mixability_pairs_path = Path(
        decision_manifest.artifacts.get("mixability_pairs", str(report_dir / "mixability_pairs.json"))
    )
    pairs_raw = json.loads(mixability_pairs_path.read_text())
    analysis_summary_path = Path(
        decision_manifest.artifacts.get("analysis_summary", str(report_dir / "analysis_summary.json"))
    )
    if analysis_summary_path.exists():
        analysis_summary = json.loads(analysis_summary_path.read_text())
    else:
        analysis_summary = json.loads(
            (Path(decision_manifest.analysis_root) / "run_summary.json").read_text()
        )

    analysis_by_id: dict[str, AnalysisResult] = {}
    for item in analysis_summary["tracks"]:
        path = Path(item["json_path"])
        analysis_by_id[item["track_id"]] = AnalysisResult.model_validate_json(path.read_text())

    peak_cache: dict[str, list[tuple[float, float]]] = {}

    def get_peaks(track_id: str) -> list[tuple[float, float]]:
        if track_id not in peak_cache:
            analysis = analysis_by_id[track_id]
            peak_cache[track_id] = _load_peaks(analysis.track.source_path, bins=bins)
        return peak_cache[track_id]

    pair_views: list[MixabilityWaveformPair] = []
    for rank, row in enumerate(pairs_raw[:top_n], start=1):
        mix = row["mixability"]
        best = mix["best_pair_windows"][0] if mix["best_pair_windows"] else None
        if best is None:
            continue
        edge = row.get("edge_decision") or {}
        analysis_a = analysis_by_id[row["track_a_id"]]
        analysis_b = analysis_by_id[row["track_b_id"]]
        pair_views.append(
            MixabilityWaveformPair(
                rank=rank,
                mixability_score=float(mix["mixability_score"]),
                confidence=float(mix["confidence"]),
                risks=list(mix["risks"]),
                pair_score=float(best["pair_score"]),
                recommendation_policy=(
                    str(
                        (row.get("edge_decision") or {}).get(
                            "recommendation_policy",
                            mix.get("recommendation_policy", "review_only"),
                        )
                    )
                ),
                decision_class=edge.get("decision_class"),
                recommended_strategy=edge.get("recommended_transition_strategy"),
                candidate_note=(
                    "Candidate overlap from current transition-window and pair-decision models; "
                    "not DJ-validated."
                ),
                track_a=WaveformTrack(
                    title=analysis_a.track.title or row["track_a_title"],
                    duration_sec=float(analysis_a.track.duration_sec or 0.0),
                    window_start_sec=float(best["track_a_window"][0]),
                    window_end_sec=float(best["track_a_window"][1]),
                    window_label=(
                        f"mix-out window {_fmt_sec(best['track_a_window'][0])}"
                        f"–{_fmt_sec(best['track_a_window'][1])}"
                    ),
                    peaks=get_peaks(row["track_a_id"]),
                    base_color=_A,
                    accent_color=_A_HI,
                ),
                track_b=WaveformTrack(
                    title=analysis_b.track.title or row["track_b_title"],
                    duration_sec=float(analysis_b.track.duration_sec or 0.0),
                    window_start_sec=float(best["track_b_window"][0]),
                    window_end_sec=float(best["track_b_window"][1]),
                    window_label=(
                        f"mix-in window {_fmt_sec(best['track_b_window'][0])}"
                        f"–{_fmt_sec(best['track_b_window'][1])}"
                    ),
                    peaks=get_peaks(row["track_b_id"]),
                    base_color=_B,
                    accent_color=_B_HI,
                ),
            )
        )

    waveforms_dir = report_dir / "waveforms"
    waveforms_dir.mkdir(parents=True, exist_ok=True)

    pair_paths: list[Path] = []
    for pair in pair_views:
        filename = (
            f"pair_{pair.rank:02d}_"
            f"{_slug(pair.track_a.title)}_to_{_slug(pair.track_b.title)}.svg"
        )
        pair_paths.append(render_pair_waveform_svg(pair, waveforms_dir / filename))

    overview_path = render_overview_svg(pair_views, waveforms_dir / "top_mixability_overview.svg")

    cards: list[str] = []
    for pair, path in zip(pair_views, pair_paths):
        decision = pair.decision_class.replace("_", " ") if pair.decision_class else "candidate"
        strategy = pair.recommended_strategy.replace("_", " ") if pair.recommended_strategy else "n/a"
        policy = pair.recommendation_policy.replace("_", " ") if pair.recommendation_policy else "review only"
        cards.append(
            "".join(
                [
                    '<article class="card">',
                    f'<div class="meta">#{pair.rank} · {html.escape(policy)} · score {pair.mixability_score:.4f} · conf {pair.confidence:.2f}</div>',
                    f'<h2>{html.escape(pair.track_a.title)} → {html.escape(pair.track_b.title)}</h2>',
                    f'<p>Decision class: {html.escape(decision)} · Suggested strategy: {html.escape(strategy)}</p>',
                    f'<img src="{path.name}" alt="{html.escape(pair.track_a.title)} to {html.escape(pair.track_b.title)} waveform"/>',
                    "</article>",
                ]
            )
        )
    index_html = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en"><head><meta charset="utf-8"/>',
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>",
            "<title>DanceLab Top Mixability Waveforms</title>",
            "<style>",
            "body{margin:0;background:#f4efe6;color:#1f2933;font-family:'Avenir Next','Futura','Trebuchet MS',sans-serif;}",
            ".wrap{max-width:1480px;margin:0 auto;padding:32px 24px 56px;}",
            "h1{margin:0 0 8px;font-size:42px;line-height:1.05;}",
            "p{color:#5c6773;font-size:18px;max-width:880px;}",
            ".hero{background:#fff9ef;border:1px solid #d4c9b8;border-radius:28px;padding:24px;box-shadow:0 18px 48px rgba(31,41,51,.08);}",
            ".hero img{width:100%;height:auto;border-radius:22px;display:block;margin-top:18px;}",
            ".grid{display:grid;grid-template-columns:1fr;gap:22px;margin-top:26px;}",
            ".card{background:#fff9ef;border:1px solid #d4c9b8;border-radius:24px;padding:18px 18px 14px;box-shadow:0 12px 30px rgba(31,41,51,.07);}",
            ".card h2{font-size:24px;margin:8px 0 14px;line-height:1.15;}",
            ".meta{font-size:14px;color:#5c6773;font-weight:700;text-transform:uppercase;letter-spacing:.08em;}",
            ".card img{width:100%;height:auto;border-radius:18px;display:block;}",
            "</style></head><body><main class=\"wrap\">",
            "<section class=\"hero\">",
            "<h1>Top Mixability Pairs on Waveforms</h1>",
            "<p>Each card shows candidate mix-out and mix-in regions under the current model. Highlights come from transition-window, mixability, and optional edge-decision outputs, not manual DJ annotation or live validation.</p>",
            f'<img src="{overview_path.name}" alt="Top mixability overview"/>',
            "</section>",
            '<section class="grid">',
            *cards,
            "</section></main></body></html>",
        ]
    )
    index_path = waveforms_dir / "index.html"
    index_path.write_text(index_html)

    return {"overview": overview_path, "index": index_path}
