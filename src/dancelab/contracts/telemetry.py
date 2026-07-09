"""Telemetry contracts exported by the engine for external diagnostics.

The engine should expose measurements and artifact pointers, while validation
UIs, plugins, and test harnesses live outside the engine and consume those
signals as read-only telemetry.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DecisionTelemetryManifest(BaseModel):
    """Manifest of external artifacts produced by one decision-report run."""

    generated_at: str = ""
    analysis_root: str
    report_root: str = ""
    context_id: str | None = None
    track_count: int = Field(default=0, ge=0)
    ordered_pair_count: int = Field(default=0, ge=0)
    top_n_waveforms: int = Field(default=0, ge=0)
    artifacts: dict[str, str] = Field(default_factory=dict)
