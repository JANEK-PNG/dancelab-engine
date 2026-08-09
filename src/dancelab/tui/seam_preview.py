"""P w zakładce Set — usłysz szew zaznaczonej pary (szczebel 2 drabinki dźwięku).

Zero nowej matematyki: to maszyneria `preview/transition_simulation` (render
zablokowany frazowo, trójpasmowe krzywe deckowe jak w mikserze, varispeed,
cache po treści źródeł), która istniała od ery Qt bez konsumenta — tu dostaje
pierwszego. Liczymy na JUŻ policzonych analizach: okna mix-out/mix-in silnika,
cue przyciągnięte tą samą regułą co eksporter cue, długość ze stabilności szwu.

Render jest CICHY (plik w cache). DŹWIĘK uruchamia wyłącznie jawne naciśnięcie
P przez użytkownika (afplay) — nigdy automat, nigdy weryfikacja; to twarda
zasada projektu. Pełny odtwarzacz całego setu w czasie rzeczywistym
z ingerencją w trakcie to osobny szczebel (3).
"""

from __future__ import annotations

import pathlib

CACHE_DIR = pathlib.Path("data/cache/seam_preview")
DEFAULT_PROFILE = "contour_blend"


def zaplanuj_szew(analysis_a, analysis_b, weights, *,
                  beatsync: bool = True, quantize: bool = True) -> dict:
    """Sam PLAN szwu (cue, długość, tempo) bez dotykania audio — wspólny
    dla odsłuchu (P) i porównania pary (C). ValueError z powodem po polsku.

    Przełączniki są PRAWDZIWE (uczciwe guziki albo żadne — Janek chciał
    klikalne): beatsync=False gra B w jego własnym tempie (słychać zderzenie),
    quantize=False nie przyciąga cue do siatki (surowe okna silnika)."""
    from dancelab.core.models import TransitionWindowInput, WindowType
    from dancelab.decision.cue_grid import snap_cue_start
    from dancelab.decision.tempo_adjustment import nearest_octave_candidate
    from dancelab.decision.transition_length import suggest_transition_beats
    from dancelab.decision.transition_windows import detect_transition_windows
    from dancelab.preview.transition_simulation import plan_transition_duration

    a, b = analysis_a, analysis_b
    bpm_a, bpm_b = a.track.bpm_estimate, b.track.bpm_estimate
    if not bpm_a or not bpm_b:
        raise ValueError("szew jest zablokowany frazowo — oba utwory muszą "
                         "mieć tempo z analizy")

    def _okna(analysis, kind):
        ws = detect_transition_windows(
            TransitionWindowInput(
                track_id=analysis.track.track_id,
                segments=analysis.segments,
                feature_frames=analysis.features,
                beatgrid=analysis.beatgrid,
            ), weights.transition_window).windows
        match = [w for w in ws if w.window_type == kind] or list(ws)
        return sorted(match, key=lambda w: -w.score)

    okna_a = _okna(a, WindowType.mix_out)[:3]
    okna_b = _okna(b, WindowType.mix_in)[:3]
    if not okna_a or not okna_b:
        raise ValueError("silnik nie znalazł okna mix-out/mix-in dla tej pary")

    # Najlepsza para okien może nie mieć ZAPASU (wyjście tuż przy końcu A —
    # złapane na żywo 06.08: „żadnemu z utworów nie starcza zapasu").
    # DJ bierze wtedy odrobinę gorszy zjazd — planista też: schodzimy po
    # parach okien wg łącznej oceny, z jawną notką o użyciu zapasowego.
    rate_b = (bpm_a / nearest_octave_candidate(bpm_a, bpm_b).bpm
              if beatsync else 1.0)
    pary = sorted(((ow.score + iw.score, ow, iw)
                   for ow in okna_a for iw in okna_b),
                  key=lambda x: -x[0])
    for ktora, (_, out_w, in_w) in enumerate(pary):
        if quantize:
            cue_a = snap_cue_start(a.beatgrid, out_w.start_sec)
            cue_b = snap_cue_start(b.beatgrid, in_w.start_sec)
        else:
            cue_a = float(out_w.start_sec)
            cue_b = float(in_w.start_sec)
        sug = suggest_transition_beats(a, out_w.start_sec, b, in_w.start_sec)
        beats = sug.beats if sug.beats is not None else 64
        plan = plan_transition_duration(
            beats,
            available_a_beats=max((a.track.duration_sec or 0) - cue_a, 0.0)
            * bpm_a / 60.0,
            available_b_beats=max((b.track.duration_sec or 0) - cue_b, 0.0)
            / rate_b * bpm_a / 60.0,
        )
        if plan.selected_beats is None:
            continue
        rozumowanie = list(sug.reasoning)
        if ktora > 0:
            rozumowanie.insert(
                0, f"najlepszej parze okien zabrakło zapasu — użyta "
                   f"zapasowa (nr {ktora + 1} wg oceny)")
        return {"cue_a_sec": cue_a, "cue_b_sec": cue_b,
                "beats": plan.selected_beats, "bpm": float(bpm_a),
                "rate_b": rate_b, "beatsync": beatsync, "quantize": quantize,
                "rozumowanie": rozumowanie}
    raise ValueError("żadnej parze okien mix-out/mix-in nie starcza zapasu "
                     "od cue na ten szew")


def zbuduj_szew(analysis_a, analysis_b, weights, *,
                beatsync: bool = True, quantize: bool = True) -> dict:
    """Wyrenderuj (albo weź z cache) WAV szwu A→B wg planu z zaplanuj_szew.
    Cache rozróżnia ustawienia sam z siebie (cue i tempo wchodzą w klucz)."""
    from dancelab.preview.transition_simulation import (
        render_transition_preview,
        transition_preview_cache_path,
    )
    a, b = analysis_a, analysis_b
    info = zaplanuj_szew(a, b, weights, beatsync=beatsync, quantize=quantize)
    cue_a, cue_b = info["cue_a_sec"], info["cue_b_sec"]
    rate_b, bpm_a = info["rate_b"], info["bpm"]

    out = transition_preview_cache_path(
        CACHE_DIR,
        source_a=a.track.source_path, source_b=b.track.source_path,
        track_id_a=a.track.track_id, track_id_b=b.track.track_id,
        cue_a_sec=cue_a, cue_b_sec=cue_b, playback_rate_b=rate_b,
        profile_id=DEFAULT_PROFILE, duration_beats=info["beats"],
    )
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        render_transition_preview(
            source_a=a.track.source_path, source_b=b.track.source_path,
            cue_a_sec=cue_a, cue_b_sec=cue_b, bpm_master=bpm_a,
            playback_rate_b=rate_b, profile_id=DEFAULT_PROFILE,
            output_path=out, duration_beats=info["beats"],
        )
    return {"output": out, **info}


def zbuduj_szew_z_padow(analysis_a, analysis_b, *, cue_a_sec: float,
                        cue_b_sec: float) -> dict:
    """Szew renderowany z TWOICH PADÓW, nie z propozycji silnika.

    Decyzja Janka 09.08 (przeniesienie porównania do Eksport/Cue): w edytorze
    cue słuchasz dokładnie tego, co za chwilę pojedzie na CDJ-e — wyjścia
    z pada utworu A i wejścia z pada utworu B. Renderer przyjmuje konkretne
    pozycje, więc nic tu nie zgadujemy: bierzemy to, co stoi na ekranie.

    Reszta liczb jest liczona TAK SAMO jak w planie silnika (to samo
    dopasowanie oktawy tempa, ta sama reguła długości i zapasu), żeby dwa
    odsłuchy tej samej pary różniły się WYŁĄCZNIE pozycją cue. Brak zapasu
    = ValueError z powodem po polsku, nie cichy krótszy szew.
    """
    from dancelab.decision.tempo_adjustment import nearest_octave_candidate
    from dancelab.decision.transition_length import suggest_transition_beats
    from dancelab.preview.transition_simulation import (
        plan_transition_duration,
        render_transition_preview,
        transition_preview_cache_path,
    )
    a, b = analysis_a, analysis_b
    bpm_a, bpm_b = a.track.bpm_estimate, b.track.bpm_estimate
    if not bpm_a or not bpm_b:
        raise ValueError("szew jest zablokowany frazowo — oba utwory muszą "
                         "mieć tempo z analizy")
    rate_b = bpm_a / nearest_octave_candidate(bpm_a, bpm_b).bpm

    sug = suggest_transition_beats(a, cue_a_sec, b, cue_b_sec)
    plan = plan_transition_duration(
        sug.beats if sug.beats is not None else 64,
        available_a_beats=max((a.track.duration_sec or 0) - cue_a_sec, 0.0)
        * bpm_a / 60.0,
        available_b_beats=max((b.track.duration_sec or 0) - cue_b_sec, 0.0)
        / rate_b * bpm_a / 60.0,
    )
    if plan.selected_beats is None:
        raise ValueError("od tych padów nie starcza zapasu na szew — "
                         "przesuń wyjście wcześniej albo wejście dalej")
    beats = plan.selected_beats

    out = transition_preview_cache_path(
        CACHE_DIR,
        source_a=a.track.source_path, source_b=b.track.source_path,
        track_id_a=a.track.track_id, track_id_b=b.track.track_id,
        cue_a_sec=cue_a_sec, cue_b_sec=cue_b_sec, playback_rate_b=rate_b,
        profile_id=DEFAULT_PROFILE, duration_beats=beats,
    )
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        render_transition_preview(
            source_a=a.track.source_path, source_b=b.track.source_path,
            cue_a_sec=cue_a_sec, cue_b_sec=cue_b_sec, bpm_master=float(bpm_a),
            playback_rate_b=rate_b, profile_id=DEFAULT_PROFILE,
            output_path=out, duration_beats=beats,
        )
    return {"output": out, "cue_a_sec": cue_a_sec, "cue_b_sec": cue_b_sec,
            "bpm": float(bpm_a), "rate_b": rate_b, "beats": beats,
            "rozumowanie": list(sug.reasoning), "zrodlo": "pady DJ-a"}
