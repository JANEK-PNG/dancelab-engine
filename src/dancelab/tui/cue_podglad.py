"""Podgląd planu cue dla zakładki Eksport/Cue — etap 1: patrzysz, nie piszesz.

Czysta warstwa POZA skórą interfejsu (ustalenie z Jankiem 08.08: zostajemy
przy TUI, ale logika edytora cue ma być przenośna do przyszłego GUI): funkcje
biorą bieżącą kolejność setu + analizy i zwracają CuePlan gotowy do
wyświetlenia. Zapis do Rekordboksa to osobny etap (4) — ten moduł niczego
nie dotyka.

Uczciwość:
* pozycje cue wyłącznie z okien silnika przyciągniętych do siatki
  (`plan_cues` pilnuje reguł: „pewne" tylko przy wiarygodnych siatkach);
* sztuczne SetTransition dla par sąsiadów niosą transition_score=0.0 —
  planner cue TEJ liczby nie czyta i nie pokazujemy jej nigdzie
  (nie zmyślamy wyniku, którego nie policzyliśmy);
* utwór bez analizy w puli = imienne ostrzeżenie, nie zgadywanie.
"""

from __future__ import annotations

from dancelab.core.models import SetPlan, SetTransition, TransitionWindowInput
from dancelab.decision.cue_export_models import CueContentMode, CuePlan
from dancelab.decision.cue_labels import load_cue_labels
from dancelab.decision.cue_plan import plan_cues
from dancelab.decision.harmonic import harmonic_relation
from dancelab.decision.transition_windows import detect_transition_windows

TYPY_PO_POLSKU = {"mix_in": "wejście", "mix_out": "wyjście",
                  "drop": "drop", "breakdown": "breakdown",
                  "phrase": "fraza", "unverified": "niepewny"}


def _okna(analysis, weights):
    return detect_transition_windows(
        TransitionWindowInput(track_id=analysis.track.track_id,
                              segments=analysis.segments,
                              feature_frames=analysis.features,
                              beatgrid=analysis.beatgrid),
        weights.transition_window).windows


def zbuduj_plan_cue(order: list[str], by_id: dict, weights,
                    mode: CueContentMode = CueContentMode.in_out) -> CuePlan:
    """CuePlan dla bieżącej kolejności setu (po edycjach — z tego, co GRA)."""
    obecne = [tid for tid in order if tid in by_id]
    brakujace = [tid for tid in order if tid not in by_id]

    windows: dict[str, list] = {}
    ostrzezenia: list[str] = []
    for tid in obecne:
        try:
            windows[tid] = _okna(by_id[tid], weights)
        except Exception as exc:  # noqa: BLE001 — jeden chory utwór ≠ brak planu
            windows[tid] = []
            ostrzezenia.append(f"okna przejść nie policzone dla {tid}: {exc}")

    transitions = [
        SetTransition(
            from_track_id=a, to_track_id=b,
            transition_score=0.0,   # NIEUŻYWANE przez plan_cues, nie pokazujemy
            harmonic_relation=harmonic_relation(
                by_id[a].track.key_estimate, by_id[b].track.key_estimate),
        )
        for a, b in zip(obecne, obecne[1:])
    ]
    plan = plan_cues(
        SetPlan(track_order=obecne, transitions=transitions),
        analyses={tid: by_id[tid] for tid in obecne},
        windows_by_track=windows,
        labels=load_cue_labels(),
        mode=mode,
    )
    plan.warnings = [
        *(f"utwór {tid} bez analizy w puli — pominięty" for tid in brakujace),
        *ostrzezenia,
        *plan.warnings,
    ]
    return plan


def _mmss(ms: int) -> str:
    m, s = divmod(ms / 1000.0, 60.0)
    return f"{int(m)}:{s:04.1f}"


# ---------------------------------------------------------------- oś utworu
# Sparkline Tufte'a: grafika wielkości słowa w wierszu tabeli. Energia z
# NASZYCH klatek cech (rms) — zero zmyślania: brak klatek = płaska kreska,
# nie wymyślony kształt.

BLOKI = "▁▂▃▄▅▆▇█"
NAZWY_SEKCJI = {"intro": "INTRO", "build": "UP", "drop": "DROP",
                "breakdown": "BREAK", "groove": "GROOVE", "outro": "OUTRO",
                "unknown": "?"}


def czas_utworu(analysis) -> float:
    """Długość w sekundach: metadana → ostatnia klatka → ostatni segment."""
    dur = getattr(analysis.track, "duration_sec", None)
    if dur:
        return float(dur)
    if analysis.features:
        return float(analysis.features[-1].timestamp_sec)
    if analysis.segments:
        return float(max(s.end_sec for s in analysis.segments))
    return 0.0


def os_energii(analysis, szer: int) -> str:
    """Pasek energii ▁▂▅█ o szerokości `szer` komórek; bez danych = kreski."""
    frames = [f for f in analysis.features if f.rms is not None]
    dur = czas_utworu(analysis)
    if not frames or dur <= 0 or szer <= 0:
        return "─" * max(szer, 0)
    kosze = [0.0] * szer
    ile = [0] * szer
    for f in frames:
        i = min(int(f.timestamp_sec / dur * szer), szer - 1)
        kosze[i] += f.rms
        ile[i] += 1
    srednie = [k / n if n else None for k, n in zip(kosze, ile)]
    znane = [s for s in srednie if s is not None]
    lo, hi = min(znane), max(znane)
    zakres = (hi - lo) or 1.0
    return "".join(
        "─" if s is None else BLOKI[int((s - lo) / zakres * (len(BLOKI) - 1))]
        for s in srednie)


def pas_sekcji(analysis, szer: int) -> str:
    """Pasek sekcji INTRO─┤UP─┤… z naszej segmentacji (odpowiednik
    kolorowych fraz Rekordboksa). Bez segmentów = pusto."""
    dur = czas_utworu(analysis)
    if not analysis.segments or dur <= 0 or szer <= 0:
        return ""
    pas = [" "] * szer
    for seg in sorted(analysis.segments, key=lambda s: s.start_sec):
        a = min(int(seg.start_sec / dur * szer), szer - 1)
        b = min(int(seg.end_sec / dur * szer), szer)
        if b <= a:
            b = a + 1
        nazwa = NAZWY_SEKCJI.get(str(seg.segment_type.value
                                     if hasattr(seg.segment_type, "value")
                                     else seg.segment_type), "?")
        pole = b - a
        wpis = (nazwa[:pole - 1] + "┤") if pole > 1 else "┤"
        wpis = wpis.ljust(pole, "─")[:pole]
        pas[a:b] = list(wpis)
    return "".join(pas)


def linijka_czasu(dur_sec: float, szer: int) -> str:
    """Podziałka „0:00   1:00   …" dopasowana do szerokości osi."""
    if dur_sec <= 0 or szer <= 0:
        return ""
    linia = [" "] * szer
    krok = 60.0 if dur_sec / 60.0 <= szer / 8 else 120.0
    t = 0.0
    while t <= dur_sec:
        i = min(int(t / dur_sec * (szer - 1)), szer - 1)
        et = f"{int(t // 60)}:{int(t % 60):02d}"
        for j, ch in enumerate(et):
            if i + j < szer and linia[i + j] == " ":
                linia[i + j] = ch
        t += krok
    return "".join(linia)


def komorka_pada(position_ms: int, dur_sec: float, szer: int) -> int:
    """Indeks komórki osi dla pozycji cue."""
    if dur_sec <= 0 or szer <= 0:
        return 0
    return min(int(position_ms / 1000.0 / dur_sec * szer), szer - 1)


def wiersze_podgladu(plan: CuePlan, order: list[str],
                     nazwy: dict[str, str]) -> list[tuple[str, ...]]:
    """Wiersze tabeli podglądu: (poz, utwór, pad, pozycja, typ, pewność, uwagi).

    Kolejność wierszy = kolejność setu; w obrębie utworu pady po pozycji.
    „Pewność" mówi wprost, co zrobić: ✓ albo POSŁUCHAJ."""
    cues_by_track = {t.content_id: t for t in plan.tracks}
    wiersze: list[tuple[str, ...]] = []
    for poz, tid in enumerate(order, start=1):
        track_plan = cues_by_track.get(tid)
        if track_plan is None or not track_plan.cues:
            continue
        for cue in sorted(track_plan.cues, key=lambda c: c.position_ms):
            uwagi = cue.comment or (cue.reasoning[0] if cue.reasoning else "")
            wiersze.append((
                str(poz),
                nazwy.get(tid, tid)[:40],
                cue.pad_label,
                _mmss(cue.position_ms),
                TYPY_PO_POLSKU.get(cue.cue_type, cue.cue_type),
                "✓" if cue.confident else "POSŁUCHAJ",
                uwagi[:60],
            ))
    return wiersze
