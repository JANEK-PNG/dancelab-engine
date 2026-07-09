"""Risk score: warning against wrong use of a track in a context.

STATUS: planned — ADR-005. Output Taxonomy: "ostrzeżenie przed złym użyciem tracka".
"""

from __future__ import annotations

from dancelab.core.errors import NotImplementedFeature
from dancelab.core.models import AnalysisResult, ContextProfile, ScoredOutput

STATUS = "planned"


def risk_score(analysis: AnalysisResult, context: ContextProfile) -> ScoredOutput:
    raise NotImplementedFeature("risk score", status=STATUS)
