"""Sugestie podmiany w szczelinie — logika, nie widżety.

Reguły: kandydat oceniany między sąsiadami (obie strony), utwory z setu
wykluczone, okno tempa szanowane, brzeg setu nazwany w `why`, top-k stabilnie
posortowany. Ocena wstrzykiwana (`score_fn`) — testujemy logikę szczeliny,
nie transition_score, który ma własne testy.
"""

from __future__ import annotations

import pytest

from dancelab.decision.slot_suggest import suggest_for_slot


class _Track:
    def __init__(self, tid, bpm, emb=None):
        self.track_id = tid
        self.bpm_estimate = bpm
        self.sound_embedding = emb
        self.source_path = f"/m/{tid}.mp3"


class _A:
    def __init__(self, tid, bpm, emb=None):
        self.track = _Track(tid, bpm, emb)


def _pool(*specs):
    return {tid: _A(tid, bpm, emb) for tid, bpm, emb in specs}


def _fixed(scores):
    """score_fn z tabeli (a_id, b_id) → wynik; brak pary = 0.5."""
    return lambda a, b: scores.get((a.track.track_id, b.track.track_id), 0.5)


def test_ocenia_obie_strony_szczeliny_i_sortuje():
    by_id = _pool(("A", 130, None), ("B", 130, None), ("C", 130, None),
                  ("X", 130, None), ("Y", 130, None))
    scores = {("A", "X"): 0.9, ("X", "C"): 0.9,   # X: średnia 0.9
              ("A", "Y"): 0.4, ("Y", "C"): 0.6}   # Y: średnia 0.5
    out = suggest_for_slot(by_id, ["A", "B", "C"], 1, score_fn=_fixed(scores))
    assert [s.track_id for s in out] == ["X", "Y"]
    assert out[0].score == pytest.approx(0.9)
    assert "wejście" in out[0].why and "wyjście" in out[0].why


def test_utwory_z_setu_wykluczone():
    by_id = _pool(("A", 130, None), ("B", 130, None), ("C", 130, None))
    out = suggest_for_slot(by_id, ["A", "B", "C"], 1, score_fn=_fixed({}))
    assert out == [], "jedyni kandydaci grają już w secie — pusta lista, nie recykling"


def test_okno_tempa_szanowane():
    by_id = _pool(("A", 130, None), ("B", 130, None),
                  ("wolny", 100, None), ("dobry", 132, None))
    out = suggest_for_slot(by_id, ["A", "B"], 1, bpm_min=125, bpm_max=140,
                           score_fn=_fixed({}))
    assert [s.track_id for s in out] == ["dobry"]


def test_brzeg_setu_nazwany():
    by_id = _pool(("A", 130, None), ("B", 130, None), ("X", 130, None))
    out = suggest_for_slot(by_id, ["A", "B"], 1, score_fn=_fixed({}))  # ostatnia pozycja
    assert any("brzeg setu" in s.why for s in out)


def test_kotwica_przewaza_przy_rownych_sasiadach():
    by_id = _pool(("A", 130, [1.0, 0.0]), ("B", 130, [1.0, 0.0]),
                  ("blisko", 130, [0.95, 0.1]), ("daleko", 130, [-0.9, 0.3]))
    out = suggest_for_slot(by_id, ["A", "B"], 1, anchor=[1.0, 0.0],
                           score_fn=_fixed({}))
    assert out[0].track_id == "blisko"
    assert "kotwica" in out[0].why


def test_zly_indeks_odmawia():
    by_id = _pool(("A", 130, None))
    with pytest.raises(ValueError):
        suggest_for_slot(by_id, ["A"], 5, score_fn=_fixed({}))


def test_top_k_przycina():
    specs = [("A", 130, None), ("B", 130, None)] + [
        (f"c{i}", 130, None) for i in range(30)]
    by_id = _pool(*specs)
    out = suggest_for_slot(by_id, ["A", "B"], 1, k=10, score_fn=_fixed({}))
    assert len(out) == 10
