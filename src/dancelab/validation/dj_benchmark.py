"""DJ validation benchmark aggregation.

This module treats exported ``*_transition_ratings.csv`` files as human review
artifacts. It does not tune the engine; it only measures how well engine scores
match DJ judgment across repeated listening sessions.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean, median
from typing import Any

from dancelab.validation.dj_decision_metrics import (
    kendall_tau,
    rating_correlation,
    spearman_rho,
)

MIN_BENCHMARK_SESSIONS = 5
MIN_RATED_TRANSITIONS_PER_SESSION = 30

TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "bpm_grid_sync": (
        "bpm",
        "bmp",
        "beat",
        "beats",
        "sync",
        "synch",
        "grid",
        "quant",
        "quanta",
    ),
    "style_genre_mood": (
        "styl",
        "gatunk",
        "charakter",
        "klimat",
        "emoc",
        "melanch",
        "mistycz",
        "weso",
        "smut",
        "jungle",
        "dubstep",
        "electronic",
        "disco",
        "funk",
    ),
    "energy_curve": (
        "energia",
        "energy",
        "buildup",
        "podbij",
        "opada",
        "spad",
        "skacze",
    ),
    "transition_timing": (
        "przejscie",
        "przejście",
        "cue",
        "czas",
        "dłużej",
        "dlugie",
        "krótki",
        "krotki",
    ),
    "duplicates_same_album": (
        "duplik",
        "same utwory",
        "ta sama",
        "tej samej płyty",
        "samej plyty",
        "płyty",
        "plyty",
    ),
    "playlist_context": (
        "playlista",
        "set",
        "closing",
        "rano",
        "srodku",
        "środku",
        "spokojna",
        "koniec",
        "konie",
    ),
}


@dataclass(frozen=True)
class RatingRow:
    pair_id: str
    track_id_a: str
    track_id_b: str
    engine_score: float
    dj_mixability_rating: float
    comment: str = ""
    blind: bool = False
    source_path: str = ""
    row_number: int = 0


@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    source_path: str
    rated_count: int
    comment_count: int
    blind_count: int
    mean_engine_score: float | None
    mean_dj_rating: float | None
    median_dj_rating: float | None
    pearson_r: float | None
    spearman_rho: float | None
    kendall_tau: float | None
    rating_counts: dict[str, int]
    duplicate_pair_count: int
    false_positive_count: int
    topic_counts: dict[str, int]
    complete: bool


@dataclass(frozen=True)
class FalsePositiveCase:
    session_id: str
    source_path: str
    row_number: int
    pair_id: str
    track_id_a: str
    track_id_b: str
    engine_score: float
    dj_mixability_rating: float
    comment: str


@dataclass(frozen=True)
class BenchmarkSummary:
    generated_from: list[str]
    min_sessions: int
    min_rated_transitions_per_session: int
    session_count: int
    complete_session_count: int
    required_additional_sessions: int
    total_rated_count: int
    total_comment_count: int
    overall_mean_engine_score: float | None
    overall_mean_dj_rating: float | None
    overall_pearson_r: float | None
    overall_spearman_rho: float | None
    overall_kendall_tau: float | None
    rating_counts: dict[str, int]
    topic_counts: dict[str, int]
    false_positive_count: int
    sessions: list[SessionSummary] = field(default_factory=list)
    top_false_positives: list[FalsePositiveCase] = field(default_factory=list)

    @property
    def is_ready_for_tuning(self) -> bool:
        return (
            self.session_count >= self.min_sessions
            and self.complete_session_count >= self.min_sessions
        )


def default_validation_cache_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "DanceLab" / "cache" / "validation"


def find_rating_csvs(paths: list[Path]) -> list[Path]:
    """Resolve files and directories into sorted rating CSV paths."""
    found: set[Path] = set()
    for path in paths:
        if path.is_file() and path.name.endswith("_transition_ratings.csv"):
            found.add(path)
        elif path.is_dir():
            found.update(path.glob("*_transition_ratings.csv"))
    return sorted(found)


def load_rating_rows(path: Path) -> list[RatingRow]:
    rows: list[RatingRow] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row_number, record in enumerate(csv.DictReader(handle), start=2):
            rating_text = (record.get("dj_mixability_rating") or "").strip()
            score_text = (record.get("engine_score") or "").strip()
            if not rating_text or not score_text:
                continue
            rows.append(
                RatingRow(
                    pair_id=(record.get("pair_id") or "").strip(),
                    track_id_a=(record.get("track_id_a") or "").strip(),
                    track_id_b=(record.get("track_id_b") or "").strip(),
                    engine_score=float(score_text),
                    dj_mixability_rating=float(rating_text),
                    comment=(record.get("comment") or "").strip(),
                    blind=(record.get("blind") or "").strip() in {"1", "true", "True"},
                    source_path=str(path),
                    row_number=row_number,
                )
            )
    return rows


def summarize_session(
    path: Path,
    *,
    min_rated_transitions: int = MIN_RATED_TRANSITIONS_PER_SESSION,
) -> tuple[SessionSummary, list[FalsePositiveCase], list[RatingRow]]:
    rows = load_rating_rows(path)
    engine_scores = [row.engine_score for row in rows]
    ratings = [row.dj_mixability_rating for row in rows]
    pair_counts = Counter(row.pair_id for row in rows if row.pair_id)
    false_positives = [
        FalsePositiveCase(
            session_id=_session_id(path),
            source_path=str(path),
            row_number=row.row_number,
            pair_id=row.pair_id,
            track_id_a=row.track_id_a,
            track_id_b=row.track_id_b,
            engine_score=row.engine_score,
            dj_mixability_rating=row.dj_mixability_rating,
            comment=row.comment,
        )
        for row in rows
        if row.engine_score >= 0.70 and row.dj_mixability_rating <= 2
    ]
    summary = SessionSummary(
        session_id=_session_id(path),
        source_path=str(path),
        rated_count=len(rows),
        comment_count=sum(1 for row in rows if row.comment),
        blind_count=sum(1 for row in rows if row.blind),
        mean_engine_score=_safe_mean(engine_scores),
        mean_dj_rating=_safe_mean(ratings),
        median_dj_rating=median(ratings) if ratings else None,
        pearson_r=rating_correlation(engine_scores, ratings),
        spearman_rho=spearman_rho(engine_scores, ratings),
        kendall_tau=kendall_tau(engine_scores, ratings),
        rating_counts=dict(sorted(Counter(_rating_label(row.dj_mixability_rating) for row in rows).items())),
        duplicate_pair_count=sum(count - 1 for count in pair_counts.values() if count > 1),
        false_positive_count=len(false_positives),
        topic_counts=_topic_counts(rows),
        complete=len(rows) >= min_rated_transitions,
    )
    return summary, false_positives, rows


def build_benchmark_summary(
    paths: list[Path],
    *,
    min_sessions: int = MIN_BENCHMARK_SESSIONS,
    min_rated_transitions_per_session: int = MIN_RATED_TRANSITIONS_PER_SESSION,
) -> BenchmarkSummary:
    csv_paths = find_rating_csvs(paths)
    sessions: list[SessionSummary] = []
    false_positives: list[FalsePositiveCase] = []
    all_rows: list[RatingRow] = []
    for path in csv_paths:
        session, session_false_positives, rows = summarize_session(
            path,
            min_rated_transitions=min_rated_transitions_per_session,
        )
        sessions.append(session)
        false_positives.extend(session_false_positives)
        all_rows.extend(rows)

    engine_scores = [row.engine_score for row in all_rows]
    ratings = [row.dj_mixability_rating for row in all_rows]
    rating_counts = Counter(_rating_label(row.dj_mixability_rating) for row in all_rows)
    topic_counts = Counter()
    for session in sessions:
        topic_counts.update(session.topic_counts)
    false_positives.sort(
        key=lambda case: (
            case.engine_score - (case.dj_mixability_rating / 5.0),
            case.engine_score,
        ),
        reverse=True,
    )
    complete_session_count = sum(1 for session in sessions if session.complete)
    required = max(0, min_sessions - complete_session_count)
    return BenchmarkSummary(
        generated_from=[str(path) for path in csv_paths],
        min_sessions=min_sessions,
        min_rated_transitions_per_session=min_rated_transitions_per_session,
        session_count=len(sessions),
        complete_session_count=complete_session_count,
        required_additional_sessions=required,
        total_rated_count=len(all_rows),
        total_comment_count=sum(1 for row in all_rows if row.comment),
        overall_mean_engine_score=_safe_mean(engine_scores),
        overall_mean_dj_rating=_safe_mean(ratings),
        overall_pearson_r=rating_correlation(engine_scores, ratings),
        overall_spearman_rho=spearman_rho(engine_scores, ratings),
        overall_kendall_tau=kendall_tau(engine_scores, ratings),
        rating_counts=dict(sorted(rating_counts.items())),
        topic_counts=dict(sorted(topic_counts.items())),
        false_positive_count=len(false_positives),
        sessions=sessions,
        top_false_positives=false_positives[:20],
    )


def write_benchmark_report(summary: BenchmarkSummary, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "dj_benchmark_summary.json"
    md_path = output_dir / "dj_benchmark_summary.md"
    json_path.write_text(json.dumps(asdict(summary), indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_benchmark_markdown(summary), encoding="utf-8")
    return {"summary_json": json_path, "summary_md": md_path}


def render_benchmark_markdown(summary: BenchmarkSummary) -> str:
    readiness = "READY FOR TUNING" if summary.is_ready_for_tuning else "NOT READY FOR TUNING"
    lines = [
        "# DJ Validation Benchmark",
        "",
        f"Status: **{readiness}**",
        "",
        f"- Sessions: {summary.complete_session_count}/{summary.min_sessions} complete "
        f"({summary.session_count} CSV file(s) found)",
        f"- Minimum per session: {summary.min_rated_transitions_per_session} rated transitions",
        f"- Additional complete sessions needed: {summary.required_additional_sessions}",
        f"- Rated transitions: {summary.total_rated_count}",
        f"- Comments: {summary.total_comment_count}",
        f"- Mean DJ rating: {_fmt(summary.overall_mean_dj_rating)}",
        f"- Mean engine score: {_fmt(summary.overall_mean_engine_score)}",
        f"- Pearson r: {_fmt(summary.overall_pearson_r)}",
        f"- Spearman rho: {_fmt(summary.overall_spearman_rho)}",
        f"- Kendall tau: {_fmt(summary.overall_kendall_tau)}",
        f"- False positives (engine >= 0.70 and DJ <= 2): {summary.false_positive_count}",
        "",
        "## Sessions",
        "",
    ]
    if not summary.sessions:
        lines.append("No `*_transition_ratings.csv` files found.")
    for session in summary.sessions:
        status = "complete" if session.complete else "needs more ratings"
        lines.extend(
            [
                f"### {session.session_id}",
                "",
                f"- Status: {status}",
                f"- Rated: {session.rated_count}",
                f"- Comments: {session.comment_count}",
                f"- Blind ratings: {session.blind_count}",
                f"- Mean DJ rating: {_fmt(session.mean_dj_rating)}",
                f"- Pearson r: {_fmt(session.pearson_r)}",
                f"- Spearman rho: {_fmt(session.spearman_rho)}",
                f"- Kendall tau: {_fmt(session.kendall_tau)}",
                f"- False positives: {session.false_positive_count}",
                f"- Duplicate pair rows: {session.duplicate_pair_count}",
                f"- Source: `{session.source_path}`",
                "",
            ]
        )
    lines.extend(["## Issue Topics", ""])
    if summary.topic_counts:
        for topic, count in sorted(summary.topic_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {topic}: {count}")
    else:
        lines.append("No commented issue topics detected yet.")
    lines.extend(["", "## Top False Positives", ""])
    if summary.top_false_positives:
        for case in summary.top_false_positives[:10]:
            comment = case.comment.replace("\n", " ").strip()
            lines.append(
                f"- {case.session_id} row {case.row_number}: engine {case.engine_score:.3f}, "
                f"DJ {case.dj_mixability_rating:g}/5, `{case.pair_id}`"
                + (f" — {comment}" if comment else "")
            )
    else:
        lines.append("No false positives under the current threshold.")
    lines.append("")
    return "\n".join(lines)


def _safe_mean(values: list[float]) -> float | None:
    return float(mean(values)) if values else None


def _session_id(path: Path) -> str:
    name = path.name.removesuffix("_transition_ratings.csv")
    return name or path.stem


def _rating_label(rating: float) -> str:
    return str(int(rating)) if float(rating).is_integer() else f"{rating:g}"


def _topic_counts(rows: list[RatingRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        count = 0
        for row in rows:
            text = row.comment.lower()
            if text and any(keyword in text for keyword in keywords):
                count += 1
        counts[topic] = count
    return counts


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)
