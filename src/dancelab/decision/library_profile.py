"""Library-level profile extraction from analyzed tracks."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence

from dancelab.core.models import AnalysisResult, ContextProfile, LibraryProfile


def normalize_style_label(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"\s+", "-", value.strip().lower())
    return text or None


def normalize_style_list(values: Sequence[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        normalized = normalize_style_label(value)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def style_matches(style: str | None, preferred_styles: Sequence[str] | None) -> bool:
    """Czy utwór jest w którymś z żądanych gatunków — po CAŁEJ NAZWIE.

    Do 09.08 dopasowanie szło po pojedynczych słowach: nazwa była rozbijana
    na człony (spacja, ukośnik, myślnik) i wystarczyło JEDNO wspólne słowo.
    Zmierzone na bibliotece Janka: brief „House" wciągał 32 utwory zamiast 7
    (Tech House, Deep House, Afro House, Melodic House & Techno), „Breaks /
    Breakbeat / UK Bass" 49 zamiast 11, „Bass / Club" 30 zamiast 8. To jest
    dokładnie ta reguła, którą Janek zawetował przy liście gatunków („140"
    nie jest gatunkiem, bo nazwa Beatportu jest CAŁOŚCIĄ) — wybieraczka
    została poprawiona 09.08, silnik dopiero teraz.

    Reguła: obie strony sprowadzamy do nazwy kanonicznej Beatportu (jeśli
    tag ją ma) i porównujemy w całości. Tag spoza taksonomii porównuje się
    dosłownie sam ze sobą — nie jest naciągany na najbliższy gatunek.
    """
    normalized = normalize_style_label(style)
    if not normalized:
        return False
    preferences = normalize_style_list(preferred_styles)
    if not preferences:
        return True

    from dancelab.decision.gatunki_beatport import kanoniczny

    def kanon(tekst: str) -> str:
        pelna = kanoniczny(tekst.replace("-", " "))
        return normalize_style_label(pelna) or tekst

    tag = kanon(normalized)
    return any(tag == kanon(preferred) for preferred in preferences)


def bpm_in_range(
    bpm: float | None,
    bpm_min: float | None = None,
    bpm_max: float | None = None,
) -> bool:
    if bpm is None:
        return False
    if bpm_min is not None and bpm < bpm_min:
        return False
    if bpm_max is not None and bpm > bpm_max:
        return False
    return True


def build_library_profile(
    analyses: Sequence[AnalysisResult],
    *,
    context: ContextProfile | None = None,
    preferred_styles: Sequence[str] | None = None,
    bpm_min: float | None = None,
    bpm_max: float | None = None,
) -> LibraryProfile:
    styles = [
        normalized
        for analysis in analyses
        if (normalized := normalize_style_label(analysis.track.style_label)) is not None
    ]
    style_counts = dict(sorted(Counter(styles).items(), key=lambda item: (-item[1], item[0])))
    dominant_style = next(iter(style_counts), None)
    bpms = [
        float(analysis.track.bpm_estimate)
        for analysis in analyses
        if analysis.track.bpm_estimate is not None
    ]

    preferences = normalize_style_list(preferred_styles)
    if not preferences and context is not None:
        preferences = normalize_style_list(context.style_focus)
    bpm_min = bpm_min if bpm_min is not None else (context.bpm_min if context else None)
    bpm_max = bpm_max if bpm_max is not None else (context.bpm_max if context else None)

    preferred_style_count = sum(
        1 for analysis in analyses if style_matches(analysis.track.style_label, preferences)
    )
    bpm_preference_count = sum(
        1 for analysis in analyses if bpm_in_range(analysis.track.bpm_estimate, bpm_min, bpm_max)
    )

    warnings: list[str] = []
    missing_style_count = len(analyses) - len(styles)
    if missing_style_count:
        warnings.append(
            f"{missing_style_count} track(s) have no source-backed style/genre label"
        )
    if preferences and preferred_style_count == 0:
        warnings.append("no analyzed tracks match the selected style preference")
    if (bpm_min is not None or bpm_max is not None) and bpm_preference_count == 0:
        warnings.append("no analyzed tracks match the selected BPM range")

    return LibraryProfile(
        track_count=len(analyses),
        bpm_min=round(min(bpms), 2) if bpms else None,
        bpm_max=round(max(bpms), 2) if bpms else None,
        bpm_mean=round(sum(bpms) / len(bpms), 2) if bpms else None,
        style_counts=style_counts,
        dominant_style=dominant_style,
        missing_style_count=missing_style_count,
        preferred_styles=preferences,
        preferred_style_track_count=preferred_style_count,
        bpm_preference_min=bpm_min,
        bpm_preference_max=bpm_max,
        bpm_preference_track_count=bpm_preference_count,
        context_id=context.context_id if context is not None else None,
        warnings=warnings,
    )
