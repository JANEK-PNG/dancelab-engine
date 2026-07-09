"""Per-track analysis report (HTML/Markdown). STATUS: planned — Sprint 1+."""

from __future__ import annotations

from pathlib import Path

from dancelab.core.errors import NotImplementedFeature
from dancelab.core.models import AnalysisResult


def render_report(analysis: AnalysisResult, out_path: str | Path) -> Path:
    raise NotImplementedFeature("analysis report", status="planned")
