"""Style profiles: how descriptor interpretation shifts per style/genre (s).

Example: high microtiming variance = sloppy in techno, groovy in some house.
STATUS: draft — profiles must come from the annotated dataset, not intuition.
"""

from __future__ import annotations

from dancelab.core.errors import NotImplementedFeature


def load_style_profile(style_label: str) -> dict:
    raise NotImplementedFeature("style profiles", status="draft")
