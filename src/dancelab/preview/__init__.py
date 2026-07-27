"""Audio preview rendering: hear a proposed transition before playing it.

Preview material is derived output, never an input to engine scoring.
"""

from dancelab.preview.transition_simulation import (
    plan_transition_duration,
    render_transition_preview,
)

__all__ = ["plan_transition_duration", "render_transition_preview"]
