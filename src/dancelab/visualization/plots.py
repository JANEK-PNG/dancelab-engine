"""Descriptor curve plots (matplotlib, optional [viz] extra). STATUS: planned.

Minimal visualization outputs only — UI is a client, not part of the engine
(Universal Engine Architecture §5).
"""

from __future__ import annotations

from pathlib import Path

from dancelab.core.errors import NotImplementedFeature
from dancelab.core.models import AnalysisResult


def plot_descriptor_curves(analysis: AnalysisResult, out_path: str | Path) -> Path:
    """Render descriptor curves (groove, tension, release, ...) to PNG/SVG."""
    raise NotImplementedFeature("descriptor plots", status="planned")
