"""Licznik składników pomiaru — pilnuje, żeby cichy skip nie uchodził za wynik.

Regresja do D6: `except Exception: pass` ukrył TypeError, przez co składnik
harmoniczny nie wszedł do żadnego wyniku „wag ręcznych", a porównanie przez
trzy tygodnie uchodziło za porównanie wag.
"""

from __future__ import annotations

import pytest
from dancelab.validation.wejscie import BrakDanychWejsciowych, wymagaj_plikow

from dancelab.validation.skladniki import Skladniki


def test_skladnik_nieobecny_w_kazdej_probie_jest_nazwany_wprost():
    skl = Skladniki()
    for _ in range(11326):
        skl.probuje("hand.harmonic")
        try:
            raise TypeError("unsupported operand type(s) for *: 'float' and 'HarmonicResult'")
        except Exception as exc:  # noqa: BLE001
            skl.pominiete("hand.harmonic", exc)

    assert skl.nieobecne() == ["hand.harmonic"]
    raport = skl.raport()
    assert "NIEOBECNY W WYNIKU" in raport
    assert "100.0%" in raport
    assert "HarmonicResult" in raport          # przyczyna, nie sam licznik
    assert "D6" in raport                      # odsyła do obalenia, nie do domysłów


def test_policzony_skladnik_nie_podnosi_alarmu():
    skl = Skladniki()
    for _ in range(5):
        skl.probuje("measured.harmonic")

    assert skl.nieobecne() == []
    assert "wszystkie policzone" in skl.raport()
    assert "UWAGA" not in skl.raport()


def test_czesciowe_pominiecie_odroznia_sie_od_calkowitego():
    skl = Skladniki()
    for i in range(10):
        skl.probuje("clap.harmonic")
        if i < 3:
            try:
                raise ValueError("zły camelot")
            except Exception as exc:  # noqa: BLE001
                skl.pominiete("clap.harmonic", exc)

    assert skl.nieobecne() == []               # częściowe ≠ nieobecne
    raport = skl.raport()
    assert "częściowo pominięty" in raport
    assert "30.0%" in raport
    assert "UWAGA" not in raport


def test_pierwsza_przyczyna_zostaje_zapamietana():
    skl = Skladniki()
    for tekst in ("pierwsza", "druga"):
        skl.probuje("x")
        try:
            raise RuntimeError(tekst)
        except Exception as exc:  # noqa: BLE001
            skl.pominiete("x", exc)

    d = skl.jako_dict()["x"]
    assert d == {"prob": 2, "pominiete": 2, "przyczyna": "RuntimeError('pierwsza')"}


def test_pusty_licznik_mowi_ze_nic_nie_liczono():
    assert "nic nie było liczone" in Skladniki().raport()


# --- bramka danych wejściowych -------------------------------------------------




def test_nieistniejacy_katalog_odmawia_zamiast_zwrocic_pustke(tmp_path):
    """Regresja 2026-09-01: glob po niepodpiętym dysku dał zero plików, pomiar
    policzył statystyki z pustki i nadpisał priors_v1.json wartościami None."""
    with pytest.raises(BrakDanychWejsciowych) as e:
        wymagaj_plikow(tmp_path / "nie_ma_dysku", "mix*.json", "priory z korpusu")

    assert "priory z korpusu" in str(e.value)      # który pomiar odmówił
    assert "nie_ma_dysku" in str(e.value)          # czego brakuje
    assert "NIE nadpisuję" in str(e.value)         # i co z tego wynika


def test_pusty_katalog_tez_odmawia(tmp_path):
    (tmp_path / "alignments").mkdir()
    with pytest.raises(BrakDanychWejsciowych, match="nie ma w nim nic pasującego"):
        wymagaj_plikow(tmp_path / "alignments", "mix*.json", "priory CLAP")


def test_pliki_wracaja_posortowane(tmp_path):
    for n in ("mix2.json", "mix1.json", "inne.txt"):
        (tmp_path / n).write_text("{}")

    pliki = wymagaj_plikow(tmp_path, "mix*.json", "priory")
    assert [p.name for p in pliki] == ["mix1.json", "mix2.json"]
