"""Sugestie podmiany utworu w gotowym secie — „co pasuje w TO miejsce".

Prośba Janka (05.08, po pierwszym własnym przebiegu TUI): zaznaczam utwór,
chcę go podmienić i dostać 10 sugestii. Kandydat nie jest oceniany w próżni,
tylko W SZCZELINIE: liczy się, jak wchodzi po poprzednim i jak wychodzi
w następny — dokładnie tym samym `transition_score`, którym set powstał.
Kotwica brzmienia (gdy była użyta przy budowie) dokłada się tą samą wagą,
którą dokładała się przy budowie — sugestie nie mogą mieć innego gustu niż set.

Uczciwość: kandydaci przechodzą przez te same sita co budowa (okno tempa,
higiena puli); gdy szczelina jest na brzegu setu, oceniana jest jedna strona
i mówi to wprost w polu `why`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np

from dancelab.core.models import AnalysisResult
from dancelab.decision.steering import DEFAULT_ANCHOR_WEIGHT


@dataclass(frozen=True)
class SlotSuggestion:
    track_id: str
    score: float
    why: str


def _default_score_fn(weights, arc: str, planner_mode: str,
                      energy: dict[str, float], energy_range: float):
    from dancelab.decision.set_builder import transition_score

    def fn(a: AnalysisResult, b: AnalysisResult) -> float:
        s, _, _ = transition_score(
            a, b, weights, arc,
            energy.get(a.track.track_id, 0.5),
            energy.get(b.track.track_id, 0.5),
            energy_range, planner_mode)
        return float(s)
    return fn


def suggest_for_slot(
    by_id: dict[str, AnalysisResult],
    order: Sequence[str],
    index: int,
    *,
    k: int = 10,
    weights=None,
    arc: str = "build",
    planner_mode: str = "smart",
    energy: dict[str, float] | None = None,
    energy_range: float = 1.0,
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    anchor: Sequence[float] | None = None,
    anchor_weight: float = DEFAULT_ANCHOR_WEIGHT,
    score_fn: Callable[[AnalysisResult, AnalysisResult], float] | None = None,
) -> list[SlotSuggestion]:
    """Najlepsi kandydaci do podmiany `order[index]`, posortowani malejąco."""
    if not (0 <= index < len(order)):
        raise ValueError(f"index {index} poza setem ({len(order)} pozycji)")
    if score_fn is None:
        score_fn = _default_score_fn(weights, arc, planner_mode,
                                     energy or {}, energy_range)

    prev_id = order[index - 1] if index > 0 else None
    next_id = order[index + 1] if index + 1 < len(order) else None
    in_set = set(order)

    anchor_vec = None
    if anchor is not None:
        anchor_vec = np.asarray(anchor, dtype=float)
        anchor_vec /= np.linalg.norm(anchor_vec) + 1e-12

    out: list[SlotSuggestion] = []
    for tid, analysis in by_id.items():
        if tid in in_set:
            continue
        bpm = analysis.track.bpm_estimate or 0.0
        if bpm_min is not None and bpm < bpm_min:
            continue
        if bpm_max is not None and bpm > bpm_max:
            continue

        parts, why = [], []
        if prev_id is not None:
            s_in = score_fn(by_id[prev_id], analysis)
            parts.append(s_in)
            why.append(f"wejście {s_in:.2f}")
        if next_id is not None:
            s_out = score_fn(analysis, by_id[next_id])
            parts.append(s_out)
            why.append(f"wyjście {s_out:.2f}")
        if not parts:
            continue                       # set jednoelementowy — nie ma szczeliny
        score = float(np.mean(parts))
        if len(parts) == 1:
            why.append("brzeg setu — oceniona jedna strona")

        vec = analysis.track.sound_embedding
        if anchor_vec is not None and vec is not None:
            v = np.asarray(vec, dtype=float)
            aff = float(np.clip((v @ anchor_vec /
                                 (np.linalg.norm(v) + 1e-12) + 1.0) / 2.0, 0, 1))
            score = (1.0 - anchor_weight) * score + anchor_weight * aff
            why.append(f"kotwica {aff:.2f}")

        out.append(SlotSuggestion(tid, score, " · ".join(why)))

    out.sort(key=lambda s: (-s.score, s.track_id))
    return out[:k]
