"""Host/API workflow helpers for explicit stem artifact export."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from dancelab.core.config import EngineConfig
from dancelab.core.models import AnalysisResult
from dancelab.core.pipeline import analyze_track_with_stems
from dancelab.stems.exporter import export_stem_artifacts
from dancelab.stems.extractor import StemBundle

STEM_METHODS = {"auto", "demucs", "none"}
VOCAL_METHODS = {"hpss", "auto", "demucs"}


@dataclass(frozen=True)
class StemExportArtifact:
    track_id: str
    title: str | None
    artifact_path: str
    stems_written: list[str]
    stem_source_status: str | None
    warnings: list[str]


def stem_enabled_config(
    config: EngineConfig,
    *,
    stem_method: str = "auto",
    vocal_method: str | None = None,
) -> EngineConfig:
    """Return a copy of engine config with explicit stem export enabled."""
    if stem_method not in STEM_METHODS:
        raise ValueError(
            f"stem_method must be one of {sorted(STEM_METHODS)}, got {stem_method!r}"
        )

    updates: dict[str, object] = {
        "stems": config.stems.model_copy(
            update={
                "enabled": True,
                "method": stem_method,
                "export_stems": True,
            }
        )
    }
    if vocal_method is not None:
        if vocal_method not in VOCAL_METHODS:
            raise ValueError(
                f"vocal_method must be one of {sorted(VOCAL_METHODS)}, got {vocal_method!r}"
            )
        updates["analysis"] = config.analysis.model_copy(
            update={"vocal_method": vocal_method}
        )
    return config.model_copy(update=updates)


def stem_manifest_payload(out_dir: Path) -> dict[str, object]:
    manifest_path = out_dir / "stem_manifest.json"
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def artifact_from_export_dir(result: AnalysisResult, out_dir: Path) -> StemExportArtifact:
    manifest = stem_manifest_payload(out_dir)
    return StemExportArtifact(
        track_id=result.track.track_id,
        title=result.track.title,
        artifact_path=str(out_dir),
        stems_written=list(manifest.get("stems_written") or []),
        stem_source_status=(
            str(manifest["stem_source_status"])
            if manifest.get("stem_source_status") is not None
            else None
        ),
        warnings=list(manifest.get("warnings") or []),
    )


def export_stems_for_paths(
    source_paths: Sequence[str],
    config: EngineConfig,
    output_root: str | Path,
    *,
    stem_method: str = "auto",
    vocal_method: str | None = None,
    analyze_fn: Callable[
        [str, EngineConfig], tuple[AnalysisResult, StemBundle | None]
    ] = analyze_track_with_stems,
    export_fn: Callable[
        [AnalysisResult, StemBundle | None, str | Path], Path
    ] = export_stem_artifacts,
) -> list[StemExportArtifact]:
    """Analyze source paths with stems enabled and write per-track artifact folders."""
    if not source_paths:
        raise ValueError("source_paths must contain at least one audio file")

    stem_config = stem_enabled_config(
        config,
        stem_method=stem_method,
        vocal_method=vocal_method,
    )
    artifacts: list[StemExportArtifact] = []
    for source_path in source_paths:
        result, stem_bundle = analyze_fn(str(source_path), stem_config)
        out_dir = export_fn(result, stem_bundle, output_root)
        artifacts.append(artifact_from_export_dir(result, out_dir))
    return artifacts
