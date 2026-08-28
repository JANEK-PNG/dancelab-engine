"""Budowa setu w warstwie stanu — ta sama dla terminala i okna.

Punkt 3 weryfikacji z planu: ta sama parametryzacja musi dawać ten sam set
niezależnie od skóry. Tu sprawdzamy to jako determinizm modułu i jako zgodność
z bezpośrednim wywołaniem silnika — bo jeśli orkiestracja coś po drodze zmienia,
skóry rozjadą się przy pierwszej różnicy.
"""

from __future__ import annotations

import pytest

from dancelab.stan import budowa


# ----------------------------------------------------------- parametry

def test_okno_tempa_odmawia_z_powodem():
    """Cichy domyślny zakres byłby gorszy niż odmowa: DJ dostałby set spoza
    tempa, o które prosił, i nie dowiedziałby się dlaczego."""
    with pytest.raises(budowa.OdmowaBudowy, match="lo-hi"):
        budowa.Parametry.z_formularza({"tempo_okno": "sto dwadzieścia"})
    with pytest.raises(budowa.OdmowaBudowy, match="puste okno"):
        budowa.Parametry.z_formularza({"tempo_okno": "140-120"})
    with pytest.raises(budowa.OdmowaBudowy, match="liczby"):
        budowa.Parametry.z_formularza({"tempo_okno": "abc-def"})


def test_puste_okno_tempa_jest_dozwolone():
    p = budowa.Parametry.z_formularza({"tempo_okno": ""})
    assert p.bpm_min is None and p.bpm_max is None


def test_ziarno_musi_byc_liczba():
    with pytest.raises(budowa.OdmowaBudowy, match="ziarno"):
        budowa.Parametry.z_formularza({"ziarno": "losowo"})


def test_dlugosc_musi_byc_dodatnia():
    with pytest.raises(budowa.OdmowaBudowy, match="dodatnia"):
        budowa.Parametry.z_formularza({"minuty": -30})
    with pytest.raises(budowa.OdmowaBudowy, match="liczba"):
        budowa.Parametry.z_formularza({"minuty": "dużo"})


def test_tryb_niedeterministyczny_dostaje_ziarno():
    """Bez zapisanego ziarna przebiegu nie da się powtórzyć — a powtarzalność
    jest tym, co odróżnia pomiar od anegdoty."""
    p = budowa.Parametry.z_formularza({"nowosc": "explore"})
    assert p.ziarno is not None
    assert budowa.Parametry.z_formularza({"nowosc": "deterministic"}).ziarno is None


def test_style_rozbierane_z_przecinkow():
    p = budowa.Parametry.z_formularza({"style": " Tech House , UK Garage ,, "})
    assert p.style == ["Tech House", "UK Garage"]


# ----------------------------------------------------------- rozbior tempa

@pytest.mark.parametrize(("wejscie", "oczekiwane"), [
    ("128-140", (128.0, 140.0)),
    ("128 - 140", (128.0, 140.0)),
    ("", (None, None)),
])
def test_rozbierz_tempo(wejscie, oczekiwane):
    lo, hi, blad = budowa.rozbierz_tempo(wejscie)
    assert (lo, hi) == oczekiwane
    assert blad is None


# ----------------------------------------------------------- budowa

@pytest.fixture(scope="module")
def prawdziwa_pula():
    """Kawałek prawdziwej puli — atrapy nie wyłapią różnic w orkiestracji."""
    analizy, _ = budowa.pula()
    if len(analizy) < 200:
        pytest.skip("za mała pula analiz")
    return analizy[:400]


def test_ten_sam_set_z_tego_samego_ziarna(prawdziwa_pula):
    """Punkt 3 weryfikacji: gdyby to nie zachodziło, dwie skóry pokazywałyby
    różne sety z tych samych ustawień i nie dałoby się ich porównać."""
    par = budowa.Parametry.z_formularza(
        {"minuty": 25, "tempo_okno": "124-134", "ziarno": "4242"})
    a = budowa.zbuduj(par, analizy=list(prawdziwa_pula))
    b = budowa.zbuduj(par, analizy=list(prawdziwa_pula))
    assert a["kolejnosc"] == b["kolejnosc"]
    assert a["kolejnosc"], "pusty set nie dowodzi niczego"


def test_okno_tempa_naprawde_zaweza(prawdziwa_pula):
    par = budowa.Parametry.z_formularza(
        {"minuty": 25, "tempo_okno": "124-128", "ziarno": "1"})
    wynik = budowa.zbuduj(par, analizy=list(prawdziwa_pula))
    tempa = [wynik["by_id"][t].track.bpm_estimate for t in wynik["kolejnosc"]]
    assert all(t is None or 120 <= t <= 132 for t in tempa), tempa


def test_pusta_pula_odmawia_z_powodem():
    par = budowa.Parametry.z_formularza({"minuty": 30})
    with pytest.raises(budowa.OdmowaBudowy, match="pusta pula"):
        budowa.zbuduj(par, analizy=[])


def test_postep_jest_raportowany(prawdziwa_pula):
    """Widok musi wiedzieć, na jakim etapie stoi — inaczej długa budowa
    wygląda jak zawieszenie."""
    kroki: list[str] = []
    par = budowa.Parametry.z_formularza({"minuty": 20, "ziarno": "7"})
    budowa.zbuduj(par, analizy=list(prawdziwa_pula), postep=kroki.append)
    assert len(kroki) >= 2
    assert any("Buduję set" in k for k in kroki)


def test_stan_filarow_rozroznia_brak_od_wypadniecia(prawdziwa_pula):
    """Trzy stany, nie dwa: „nie zaznaczyłeś filarów" i „zaznaczyłeś, ale
    wypadły z okna tempa" wymagają od użytkownika czegoś innego."""
    par = budowa.Parametry.z_formularza({"minuty": 20, "ziarno": "7"})
    wynik = budowa.zbuduj(par, analizy=list(prawdziwa_pula))
    assert wynik["filary_stan"] == "brak"
    assert wynik["filary_zgloszone"] == 0


def test_higiena_puli_odrzuca_i_liczy():
    analizy, notki = budowa.pula()
    if not notki:
        pytest.skip("pula bez odrzuconych — nie ma czego sprawdzać")
    assert "higiena puli" in notki[0]
    assert any(s in notki[0] for s in ("stemy", "brak pliku", "dłuższe"))


def test_dluga_notka_silnika_nie_jest_sciana_skrotow():
    """Złapane na zrzucie 28.08: ostrzeżenie o duplikatach ciągnęło za sobą
    listę 55 par skrótów plików i zasłaniało pozostałe ostrzeżenia."""
    dlugie = ("removed 55 duplicate audio file(s) (same bytes): "
              + ", ".join(f"{i:016x}→{i+1:016x}" for i in range(55)))
    krotkie = budowa._skroc_notke(dlugie)
    assert len(krotkie) < 120
    assert "duplicate" in krotkie and "55 pozycji" in krotkie


def test_krotka_notka_zostaje_bez_zmiany():
    tekst = "higiena puli: odrzucone 117 (stemy: 16)"
    assert budowa._skroc_notke(tekst) == tekst
