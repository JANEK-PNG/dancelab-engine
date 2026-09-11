"""Krok 2 scalania skór (02.09): wybór padów do szwu i źródło kandydata.

Obie reguły były przepisane w terminalu i w oknie osobno. Różniły się już:
okno nie honorowało ZAZNACZONEGO pada jako wyjścia. Teraz jest jedna
definicja i te testy pilnują jej z obu stron — przez to, co woła terminal,
i przez to, co woła okno.
"""

from dancelab.stan import dziennik
from dancelab.tui.seam_preview import wybierz_pady_szwu


def _pady(**gdzie):
    """{'A': (ms, typ), ...} → słownik w kształcie `efektywne_pady`."""
    return {k: {"position_ms": ms, "typ": typ} for k, (ms, typ) in gdzie.items()}


def test_zaznaczony_pad_jest_wyjsciem_nawet_gdy_nie_jest_mix_out():
    a = _pady(A=(10_000, "mix_in"), B=(200_000, "mix_out"), C=(120_000, "reczny"))
    b = _pady(A=(5_000, "mix_in"))
    pad_a, p_a, pad_b, _ = wybierz_pady_szwu(a, b, wybrany="C")
    assert (pad_a, p_a["position_ms"]) == ("C", 120_000)
    assert pad_b == "A"


def test_bez_zaznaczenia_ostatni_mix_out_i_pierwszy_mix_in():
    a = _pady(A=(10_000, "mix_out"), B=(200_000, "mix_out"))
    b = _pady(A=(90_000, "mix_in"), B=(5_000, "mix_in"))
    pad_a, _, pad_b, _ = wybierz_pady_szwu(a, b)
    assert pad_a == "B"          # ostatni na osi
    assert pad_b == "B"          # pierwszy na osi


def test_zaznaczenie_spoza_utworu_nie_psuje_wyboru():
    a = _pady(A=(10_000, "mix_out"))
    b = _pady(A=(5_000, "mix_in"))
    pad_a, _, _, _ = wybierz_pady_szwu(a, b, wybrany="Z")
    assert pad_a == "A"


def test_bez_typu_wybor_spada_na_dowolny_pad():
    """Pady BEZ pola `typ` (surowe nadpisania) — reguła ma działać, nie paść."""
    a = {"A": {"position_ms": 10_000}, "B": {"position_ms": 50_000}}
    b = {"A": {"position_ms": 7_000}}
    pad_a, _, pad_b, _ = wybierz_pady_szwu(a, b)
    assert (pad_a, pad_b) == ("B", "A")


def test_zrodlo_kandydata_z_panelu_i_z_reki():
    meta = {"t1": {"zrodlo": "panel_silnika", "ranga": 3, "score": 0.81}}
    assert dziennik.zrodlo_kandydata(meta, "t1") == meta["t1"]
    assert dziennik.zrodlo_kandydata(meta, "t1") is not meta["t1"]   # kopia
    assert dziennik.zrodlo_kandydata(meta, "obcy") == {"zrodlo": "reka_dj"}
    assert dziennik.zrodlo_kandydata({}, "t1") == {"zrodlo": "reka_dj"}
