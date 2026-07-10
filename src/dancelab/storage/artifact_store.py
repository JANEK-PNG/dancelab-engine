"""Artifact store: JSON outputs, Parquet feature tables, PNG/SVG plots, .npy/.npz.

v0: local filesystem under data/processed/. Object storage later.
JSON write is implemented now — it is the primary exchange format (ADR-004).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


def save_json(model: BaseModel, path: str | Path) -> Path:
    """Serialize any engine Pydantic model to pretty JSON. Deterministic key order.

    AUD-M7: encoding pinned — model_dump_json emits raw non-ASCII (accents,
    emoji in track titles); relying on the locale default crashes on
    cp1252/Windows hosts."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    return p


def load_json(model_cls: type[BaseModel], path: str | Path) -> BaseModel:
    return model_cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
