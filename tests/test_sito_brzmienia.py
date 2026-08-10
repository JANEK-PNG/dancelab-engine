"""Sito brzmieniowe — kotwica decyduje, KTO wchodzi do puli kandydatów.

Zmierzone 09.08: kotwica jako dodatek do oceny nie zmieniała setu, bo utwory
BEZ wektora nie dostawały żadnej korekty i systematycznie wygrywały
z ocenionymi. Te testy pilnują obu stron naprawy: sito zawęża pulę do
brzmienia kotwicy, ale nigdy nie oddaje setu zbudowanego z resztek.
"""

from dancelab.core.models import AnalysisResult, Track
from dancelab.decision import sito_brzmienia as S


def _utwor(tid: str, wektor=None) -> AnalysisResult:
    return AnalysisResult(engine_version="t", track=Track(
        track_id=tid, source_path=f"/m/{tid}.wav",
        sound_embedding=list(wektor) if wektor else None))


def _pula(n_blisko: int, n_daleko: int, n_bez: int) -> dict:
    pula = {}
    for i in range(n_blisko):
        pula[f"b{i}"] = _utwor(f"b{i}", [1.0, 0.0, 0.01 * i])
    for i in range(n_daleko):
        pula[f"d{i}"] = _utwor(f"d{i}", [0.0, 1.0, 0.01 * i])
    for i in range(n_bez):
        pula[f"n{i}"] = _utwor(f"n{i}")
    return pula


def test_sito_zostawia_utwory_najblizsze_kotwice():
    pula = _pula(20, 20, 0)
    nowa, uwagi = S.przesiej(pula, [1.0, 0.0, 0.0], wymagane=set(),
                             ile_utworow=5, udzial=0.25)
    assert len(nowa) == 10
    assert all(t.startswith("b") for t in nowa), \
        "zostają utwory z okolicy kotwicy, nie z drugiego końca"
    assert any("pula 40 → 10" in u for u in uwagi)


def test_utwor_bez_wektora_wypada_ale_JEST_POLICZONY():
    """Nie wiemy, czy pasuje — więc nie może wygrać przez to, że nie da się
    go ocenić. Ale DJ ma wiedzieć, ile biblioteki nie brało udziału."""
    pula = _pula(20, 10, 12)
    nowa, uwagi = S.przesiej(pula, [1.0, 0.0, 0.0], wymagane=set(),
                             ile_utworow=5, udzial=0.5)
    assert not any(t.startswith("n") for t in nowa)
    assert any("12 utworów bez wektora" in u for u in uwagi)


def test_filary_przechodza_przez_sito_zawsze():
    """Ta sama zasada co przy gatunku: filar jest ponad filtrem."""
    pula = _pula(20, 20, 0)
    nowa, _ = S.przesiej(pula, [1.0, 0.0, 0.0], wymagane={"d7"},
                         ile_utworow=5, udzial=0.1)
    assert "d7" in nowa, "filar zostaje nawet z drugiego końca brzmienia"


def test_za_ostre_sito_ROZLUZNIA_SIE_i_mowi_o_tym():
    pula = _pula(10, 10, 0)
    nowa, uwagi = S.przesiej(pula, [1.0, 0.0, 0.0], wymagane=set(),
                             ile_utworow=12, udzial=0.1)
    assert len(nowa) == len(pula), "wolimy pełną pulę niż set z resztek"
    assert any("ROZLUŹNIONE" in u for u in uwagi)


def test_bez_kotwicy_sito_nic_nie_robi():
    pula = _pula(5, 5, 5)
    nowa, uwagi = S.przesiej(pula, None, wymagane=set(), ile_utworow=3)
    assert nowa is pula and uwagi == []


def test_pula_bez_wektorow_nie_udaje_ze_przesiala():
    pula = _pula(0, 0, 10)
    nowa, uwagi = S.przesiej(pula, [1.0, 0.0, 0.0], wymagane=set(),
                             ile_utworow=3)
    assert nowa is pula
    assert any("żaden utwór puli nie ma wektora" in u for u in uwagi)
