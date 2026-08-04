"""Sugestie podmiany utworu w gotowym secie — „co pasuje w TO miejsce".

Prośba Janka (05.08, po pierwszym własnym przebiegu TUI): zaznaczam utwór,
chcę go podmienić i dostać 10 sugestii. Kandydat nie jest oceniany w próżni,
tylko W SZCZELINIE: liczy się, jak wchodzi po poprzednim i jak wychodzi
w następny — dokładnie tym samym `transition_score`, którym set powstał.
Kotwica brzmienia (gdy była użyta przy budowie) dokłada się tą samą wagą,
którą dokładała się przy budowie — sugestie nie mogą mieć innego gustu niż set.

Drugi wariant tej samej szczeliny (Janek, 04.08 wieczór: „dopiszmy kilka
utworów"): `suggest_for_insertion` ocenia kandydata MIĘDZY dwoma istniejącymi
utworami, niczego nie wyrzucając — szczelina to (order[i], order[i+1]).

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


def _suggest_for_gap(
    by_id: dict[str, AnalysisResult],
    prev_id: str | None,
    next_id: str | None,
    exclude: set[str],
    *,
    k: int,
    weights,
    arc: str,
    planner_mode: str,
    energy: dict[str, float] | None,
    energy_range: float,
    bpm_min: float | None,
    bpm_max: float | None,
    anchor: Sequence[float] | None,
    anchor_weight: float,
    score_fn: Callable[[AnalysisResult, AnalysisResult], float] | None,
) -> list[SlotSuggestion]:
    """Wspólny rdzeń: oceń kandydatów w szczelinie (prev → kandydat → next)."""
    if score_fn is None:
        score_fn = _default_score_fn(weights, arc, planner_mode,
                                     energy or {}, energy_range)

    anchor_vec = None
    if anchor is not None:
        anchor_vec = np.asarray(anchor, dtype=float)
        anchor_vec /= np.linalg.norm(anchor_vec) + 1e-12

    out: list[SlotSuggestion] = []
    for tid, analysis in by_id.items():
        if tid in exclude:
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
    """Najlepsi kandydaci do PODMIANY `order[index]`, posortowani malejąco."""
    if not (0 <= index < len(order)):
        raise ValueError(f"index {index} poza setem ({len(order)} pozycji)")
    return _suggest_for_gap(
        by_id,
        order[index - 1] if index > 0 else None,
        order[index + 1] if index + 1 < len(order) else None,
        set(order),
        k=k, weights=weights, arc=arc, planner_mode=planner_mode,
        energy=energy, energy_range=energy_range,
        bpm_min=bpm_min, bpm_max=bpm_max,
        anchor=anchor, anchor_weight=anchor_weight, score_fn=score_fn)


def suggest_for_insertion(
    by_id: dict[str, AnalysisResult],
    order: Sequence[str],
    after_index: int,
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
    """Najlepsi kandydaci do DOPISANIA za `order[after_index]` — nikt nie wypada.

    Szczelina to (order[after_index], order[after_index+1]); za ostatnim
    utworem szczelina ma jedną stronę i `why` mówi o brzegu setu.
    """
    if not order:
        raise ValueError("pusty set — nie ma za czym dopisywać (najpierw budowa)")
    if not (0 <= after_index < len(order)):
        raise ValueError(
            f"after_index {after_index} poza setem ({len(order)} pozycji)")
    return _suggest_for_gap(
        by_id,
        order[after_index],
        order[after_index + 1] if after_index + 1 < len(order) else None,
        set(order),
        k=k, weights=weights, arc=arc, planner_mode=planner_mode,
        energy=energy, energy_range=energy_range,
        bpm_min=bpm_min, bpm_max=bpm_max,
        anchor=anchor, anchor_weight=anchor_weight, score_fn=score_fn)
