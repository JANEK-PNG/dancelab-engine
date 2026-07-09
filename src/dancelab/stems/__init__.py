"""Stem-aware preprocessing package."""

from dancelab.stems.exporter import export_stem_artifacts
from dancelab.stems.extractor import StemBundle, extract_stems
from dancelab.stems.window_features import build_stem_window_features, stem_energy_ratio_per_frame

__all__ = [
    "StemBundle",
    "build_stem_window_features",
    "export_stem_artifacts",
    "extract_stems",
    "stem_energy_ratio_per_frame",
]
