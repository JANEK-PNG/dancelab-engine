"""Context profile access (ContextProfile entity + configs/context_profiles.yaml)."""

from __future__ import annotations

from dancelab.core.config import load_context_profiles
from dancelab.core.errors import ConfigError
from dancelab.core.models import ContextProfile


def get_context_profile(
    context_id: str, profiles_path: str = "configs/context_profiles.yaml"
) -> ContextProfile:
    profiles = load_context_profiles(profiles_path)
    if context_id not in profiles:
        raise ConfigError(
            f"Unknown context profile '{context_id}'. Available: {sorted(profiles)}"
        )
    return ContextProfile(context_id=context_id, **profiles[context_id])
