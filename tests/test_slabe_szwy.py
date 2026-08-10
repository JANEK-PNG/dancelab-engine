"""Ostrzeżenie o słabych szwach — set nie ma się degradować po cichu.

Złapane 09.08 testem person: ta sama biblioteka 150 utworów daje przy secie
na 10 najsłabszy szew 0,695, a przy secie na 30 — 0,386 i skok tempa 26 BPM,
i ani jednego ostrzeżenia. Początkująca DJ-ka prosi o dwie godziny ze 150
utworów, dostaje sklejkę i nie wie, że przesadziła.
"""

from dancelab.core.models import SetTransition
from dancelab.decision.set_builder import (
    SLABY_SZEW,
    _ostrzezenia_o_slabych_szwach,
)


def _szwy(*oceny: float) -> list[SetTransition]:
    return [SetTransition(from_track_id=f"t{i}", to_track_id=f"t{i+1}",
                          transition_score=o, harmonic_relation="unknown")
            for i, o in enumerate(oceny)]


def test_dobre_szwy_nie_wywoluja_alarmu():
    szwy = _szwy(0.95, 0.88, 0.70, 0.61)
    assert _ostrzezenia_o_slabych_szwach(szwy, ["a"] * 5, 500) == [], \
        "próg ma milczeć na secie, który jest po prostu dobry"


def test_slabe_szwy_sa_policzone_i_ZLOKALIZOWANE():
    szwy = _szwy(0.95, 0.30, 0.88, 0.55)
    uwagi = _ostrzezenia_o_slabych_szwach(szwy, ["a"] * 5, 150)
    assert uwagi, "dwa szwy pod progiem mają dać ostrzeżenie"
    assert "2 z 4" in uwagi[0]
    assert "0.30" in uwagi[0], "najsłabszy ma być podany liczbą"
    assert "2→3" in uwagi[0], "DJ ma wiedzieć, GDZIE to jest"
    assert "150" in uwagi[1] and "5" in uwagi[1], \
        "druga linia wiąże długość setu z wielkością puli"


def test_prog_stoi_miedzy_losem_a_przyzwoitym():
    """Zmierzone na 3000 losowych par: mediana 0,357, przyzwoity szew ~0,89.
    Próg ma leżeć wyraźnie nad losem i wyraźnie pod przyzwoitym."""
    assert 0.40 < SLABY_SZEW < 0.80


def test_na_zdrowej_puli_ostrzezenia_nie_ma(tmp_path):
    """Regresja odwrotna: alarm, który krzyczy zawsze, jest bezużyteczny."""
    szwy = _szwy(*[0.99] * 29)
    assert _ostrzezenia_o_slabych_szwach(szwy, ["a"] * 30, 1900) == []
