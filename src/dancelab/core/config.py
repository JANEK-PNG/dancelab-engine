"""Engine configuration loading (YAML → typed Pydantic models)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from dancelab.core.errors import ConfigError


class AudioConfig(BaseModel):
    sample_rate: int = 44100
    mono: bool = True
    frame_size: int = 2048
    hop_size: int = 512
    normalize: bool = True


class AnalysisConfig(BaseModel):
    onset_window_sec: float = 4.0
    segment_min_len_sec: float = 8.0
    transition_top_n: int = 3
    tempo_min: float = 90.0   # octave-fold target range [tempo_min, tempo_max)
    tempo_max: float = 180.0
    # vocal proxy backend when the stem layer is off: "hpss" (fast, default) |
    # "demucs" (slow, accurate) | "auto" (demucs if installed). Keeps a plain
    # analyze fast (~seconds); opt into demucs for quality.
    vocal_method: str = "hpss"


class StemConfig(BaseModel):
    enabled: bool = False
    method: str = "auto"
    fallback_confidence_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    max_artifact_flag: str = "clear"
    min_required_stems: int = Field(default=4, ge=1, le=4)
    export_stems: bool = False


class EngineSection(BaseModel):
    version: str = "0.1.0"
    random_seed: int = 42


class PathsConfig(BaseModel):
    data_dir: str = "data"
    raw_dir: str = "data/raw"
    processed_dir: str = "data/processed"
    examples_dir: str = "data/examples"


class CacheConfig(BaseModel):
    """PRODUCT_SPEC §8 — visible, bounded, relocatable cache."""

    root: str = ""  # "" → platform default (~/Library/Application Support/DanceLab/cache)
    max_bytes: int = 10 * 1024**3
    low_disk_floor_bytes: int = 2 * 1024**3
    keep_stem_cache: bool = True


class EngineConfig(BaseModel):
    engine: EngineSection = Field(default_factory=EngineSection)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    stems: StemConfig = Field(default_factory=StemConfig)
    bands: dict[str, list[float]] = Field(default_factory=lambda: {"bass": [20.0, 150.0]})
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    weights_file: str = "configs/descriptor_weights.yaml"
    context_profiles_file: str = "configs/context_profiles.yaml"
    model_cards_file: str = "configs/model_cards.yaml"
    formula_terms_file: str = "configs/formula_terms.yaml"


class WeightGroup(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    status: str
    weights: dict[str, float]
    model_version: str | None = None


class DescriptorWeights(BaseModel):
    """Versioned descriptor weight sets (Sprint Zero: weight config versioning)."""

    version: str
    groove_density: WeightGroup
    bass_salience: WeightGroup
    tension: WeightGroup
    transition_window: WeightGroup
    mixability: WeightGroup
    mixability_conflict: WeightGroup | None = None
    set_builder: WeightGroup | None = None
    sequence: WeightGroup | None = None


def _read_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Config file not found: {p}")
    with p.open() as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ConfigError(f"Config file is not a mapping: {p}")
    return data


def load_config(path: str | Path = "configs/default.yaml") -> EngineConfig:
    return EngineConfig.model_validate(_read_yaml(path))


def load_weights(path: str | Path = "configs/descriptor_weights.yaml") -> DescriptorWeights:
    return DescriptorWeights.model_validate(_read_yaml(path))


def load_context_profiles(path: str | Path = "configs/context_profiles.yaml") -> dict:
    """Returns {profile_id: ContextProfile-like dict}."""
    data = _read_yaml(path)
    return data.get("profiles", {})
