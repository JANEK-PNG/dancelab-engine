"""Frazy Rekordboxa jako ogranicznik długości blendu.

Reguła: blend nie przeciąga się poza moment, w którym płyta zmienia sekcję.
Kolejne frazy TEGO SAMEGO typu (trzy UP-y pod rząd) to jedna ciągłość.
Człon jest opcjonalny — bez analizy fraz wszystko ma działać jak dotąd.
"""

from __future__ import annotations

from dancelab.decision.transition_length import phrase_runway_beats
from dancelab.ingestion.rekordbox_phrases import Phrase, PhraseAnalysis


def _p(i, label, a, b):
    return Phrase(index=i, kind=0, label=label, start_beat=int(a * 2),
                  start_sec=float(a), end_beat=int(b * 2), end_sec=float(b),
                  has_fill=False, fill_start_beat=None)


def _an(*ph):
    return PhraseAnalysis(mood=1, bank=0, end_beat=1000, phrases=list(ph))


BPM = 120.0     # 2 bity na sekundę — łatwo liczyć w głowie


def test_zapas_konczy_sie_na_zmianie_sekcji():
    an = _an(_p(1, "UP", 0, 30), _p(2, "DOWN", 30, 60))
    beats, why = phrase_runway_beats(an, 10.0, BPM)
    assert beats == 40.0, why          # 20 s do zmiany × 2 bity
    assert "UP" in why


def test_te_same_sekcje_pod_rzad_sie_lacza():
    """Trzy UP-y to jedna ciągłość — zapas ma sięgać do DOWN, nie do granicy fraz."""
    an = _an(_p(1, "UP", 0, 20), _p(2, "UP", 20, 40), _p(3, "UP", 40, 60),
             _p(4, "DOWN", 60, 90))
    beats, _ = phrase_runway_beats(an, 10.0, BPM)
    assert beats == 100.0, "zapas urwał się na granicy fraz zamiast na zmianie sekcji"


def test_ostatnia_sekcja_konczy_sie_na_koncu_utworu():
    an = _an(_p(1, "CHORUS", 0, 30), _p(2, "OUTRO", 30, 50))
    beats, _ = phrase_runway_beats(an, 40.0, BPM)
    assert beats == 20.0


def test_bez_analizy_fraz_odmawia_zamiast_zmyslac():
    beats, why = phrase_runway_beats(None, 10.0, BPM)
    assert beats is None and "brak analizy" in why


def test_bez_tempa_odmawia():
    an = _an(_p(1, "UP", 0, 30))
    beats, why = phrase_runway_beats(an, 5.0, None)
    assert beats is None and "tempa" in why


def test_niepotwierdzony_slownik_nie_daje_zapasu():
    """mood 3 wraca bez etykiet — wtedy ten człon musi milczeć, nie zgadywać."""
    an = _an(Phrase(index=1, kind=7, label=None, start_beat=1, start_sec=0.0,
                    end_beat=60, end_sec=30.0, has_fill=False, fill_start_beat=None))
    beats, why = phrase_runway_beats(an, 5.0, BPM)
    assert beats is None and "słownik" in why


def test_cue_poza_frazami_to_none():
    an = _an(_p(1, "UP", 0, 30))
    beats, why = phrase_runway_beats(an, 999.0, BPM)
    assert beats is None
