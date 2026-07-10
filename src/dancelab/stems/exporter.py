"""Export audio stem artifacts for one analyzed track."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import numpy as np

from dancelab.core.models import AnalysisResult
from dancelab.storage.artifact_store import save_json
from dancelab.stems.extractor import StemBundle


def _safe_name(value: str) -> str:
    text = re.sub(r"[^\w.\-() ]+", "_", value, flags=re.ASCII).strip()
    return text[:120] or "track"


def _audio_matrix(samples: np.ndarray) -> np.ndarray:
    arr = np.asarray(samples, dtype=np.float32)
    if arr.ndim == 1:
        return arr
    return arr.T


def export_stem_artifacts(
    result: AnalysisResult,
    stem_bundle: StemBundle | None,
    output_root: str | Path,
) -> Path:
    """Create a per-track folder with source audio, analysis JSON, and stem WAVs."""
    title = result.track.title or result.track.track_id
    folder_name = f"{_safe_name(title)} [{result.track.track_id}]"
    out_dir = Path(output_root) / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)

    source_path = Path(result.track.source_path) if result.track.source_path else None
    if source_path is not None and source_path.exists():
        shutil.copy2(source_path, out_dir / source_path.name)

    save_json(result, out_dir / "analysis.json")

    manifest: dict[str, object] = {
        "track_id": result.track.track_id,
        "title": result.track.title,
        "source_path": result.track.source_path,
        "stems_written": [],
        "stem_source_status": (
            result.stem_extraction.source_status.value if result.stem_extraction else None
        ),
        "warnings": result.stem_extraction.warnings if result.stem_extraction else [],
    }

    if stem_bundle is not None and stem_bundle.channels:
        import soundfile as sf

        for stem_type, signal in sorted(stem_bundle.channels.items(), key=lambda item: item[0].value):
            path = out_dir / f"{stem_type.value}.wav"
            sf.write(path, _audio_matrix(signal.samples), signal.sample_rate)
            manifest["stems_written"].append(path.name)

    (out_dir / "stem_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out_dir
