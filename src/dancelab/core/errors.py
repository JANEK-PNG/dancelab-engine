"""Engine error hierarchy. Core must stay framework-free (ADR-003)."""


class DanceLabError(Exception):
    """Base for all engine errors."""


class ConfigError(DanceLabError):
    """Invalid or missing configuration."""


class IngestionError(DanceLabError):
    """Audio file could not be loaded or metadata is invalid."""


class MissingDependencyError(DanceLabError):
    """An optional dependency (e.g. librosa) is required for this operation.

    Install with: pip install "dancelab-engine[audio]"
    """


class NotImplementedFeature(DanceLabError):
    """Computation is specified (see docs/formulas.md) but not implemented yet.

    Carries the formula status so callers (API/CLI) can report honestly
    instead of returning fake numbers (ADR-005).
    """

    def __init__(self, feature: str, status: str = "candidate", detail: str = ""):
        self.feature = feature
        self.status = status
        self.detail = detail
        super().__init__(
            f"'{feature}' is specified (status={status}) but not implemented yet. {detail}".strip()
        )
