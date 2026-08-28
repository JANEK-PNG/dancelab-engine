"""Przebieg dla GUI musi pokazywać ten sam kształt co pasek w terminalu.

To jest warunek architektury „dwie skóry, jeden rdzeń": jeśli okno i terminal
rysują co innego z tej samej analizy, znaczy że jedna z nich ma własną logikę,
czego cała warstwa stanu ma unikać.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pytest

from dancelab.stan import przebieg as P
from dancelab.tui.cue_podglad import BLOKI, os_energii


@dataclass
class Klatka:
    timestamp_sec: float
    rms: float | None


@dataclass
class Segment:
    start_sec: float
    end_sec: float
    segment_type: str


@dataclass
class Slad:
    bpm_estimate: float | None = 128.0
    duration_sec: float = 240.0


@dataclass
class Siatka:
    bpm: float = 128.0
    first_beat_sec: float = 0.25


@dataclass
class Analiza:
    features: list = field(default_factory=list)
    segments: list = field(default_factory=list)
    track: Slad = field(default_factory=Slad)
    beatgrid: Siatka = field(default_factory=Siatka)


def zrob_analize(dlugosc=240.0, klatek=2400, dziury=()):
    """Analiza z falą, która ma wyraźny kształt — żeby porównanie coś znaczyło."""
    klatki = []
    for i in range(klatek):
        t = i / klatek * dlugosc
        if any(a <= t < b for a, b in dziury):
            klatki.append(Klatka(t, None))       # miejsce bez pomiaru
            continue
        rms = 0.2 + 0.6 * abs(math.sin(t / 18)) * (0.4 + 0.6 * (t / dlugosc))
        klatki.append(Klatka(t, rms))
    segmenty = [
        Segment(0.0, 32.0, "intro"),
        Segment(32.0, 150.0, "build"),
        Segment(150.0, dlugosc, "outro"),
    ]
    return Analiza(features=klatki, segments=segmenty,
                   track=Slad(duration_sec=dlugosc), beatgrid=Siatka())


def test_ksztalt_zgadza_sie_z_terminalem():
    """Ten sam kształt po skwantowaniu do znaków, jakich używa terminal."""
    a = zrob_analize()
    szer = 60
    z_terminala = os_energii(a, szer)
    p = P.zbuduj(a, punktow=szer)

    # ta sama kwantyzacja, jakiej używa os_energii
    z_gui = "".join(BLOKI[int(v * (len(BLOKI) - 1))] for v in p.obwiednia)
    assert z_gui == z_terminala


def test_brak_pomiaru_to_nie_cisza():
    """Miejsce bez pomiaru musi być rozpoznawalne, nie udawać zera.

    ADR-005: każde „nie wiem" ma swój piksel. Widok ma prawo narysować dziurę
    inaczej niż ciszę, ale tylko jeśli dostanie tę informację.
    """
    a = zrob_analize(dziury=((100.0, 130.0),))
    p = P.zbuduj(a, punktow=120)
    assert len(p.ma_dane) == 120
    assert not all(p.ma_dane), "dziura w danych zniknęła"
    # dziura wypada mniej więcej w połowie utworu
    puste = [i for i, m in enumerate(p.ma_dane) if not m]
    assert 40 <= puste[0] <= 60


def test_sekcje_i_takty():
    a = zrob_analize()
    p = P.zbuduj(a, punktow=100)
    assert [s.typ for s in p.sekcje] == ["intro", "build", "outro"]
    assert p.sekcje[0].od_sec == 0.0 and p.sekcje[-1].do_sec == 240.0
    assert p.bpm == 128.0
    # takt = 4 uderzenia; przy 128 BPM to 1,875 s
    assert p.takty_sec, "brak siatki taktów mimo znanego tempa"
    assert p.takty_sec[0] == pytest.approx(0.25)
    assert p.takty_sec[1] - p.takty_sec[0] == pytest.approx(4 * 60 / 128)


def test_pusta_analiza_nie_wybucha():
    """Utwór bez klatek musi dać pusty przebieg, nie wyjątek."""
    p = P.zbuduj(Analiza(track=Slad(duration_sec=0.0)), punktow=50)
    assert p.dlugosc_sec == 0.0
    assert p.obwiednia == [] and p.sekcje == []


def test_slownik_dla_mostu_jest_serializowalny():
    import json
    a = zrob_analize()
    d = P.zbuduj(a, punktow=40).do_slownika()
    json.dumps(d)                    # most wysyła to do JavaScriptu
    assert len(d["obwiednia"]) == 40
    assert d["sekcje"][0]["nazwa"]


def test_zgodnosc_na_PRAWDZIWEJ_analizie():
    """To samo porównanie, ale na realnym AnalysisResult z cache.

    Zewnętrzny przegląd 28.08 zauważył, że wszystkie pozostałe testy w tym
    pliku stoją na atrapach: sprawdzają zgodność algorytmu, nie zgodność z
    danymi, jakie naprawdę produkuje silnik. Atrapa nie wyłapie zmiany w
    kształcie `AnalysisResult` ani w tym, jak liczone są klatki.

    Test pomija się, gdy nie ma katalogu analiz — nie każdy klon repo go ma.
    """
    import json
    from pathlib import Path

    katalog = Path("experiments_priv/2026-07-30_rebuild/processed")
    if not katalog.exists():
        pytest.skip("brak katalogu analiz")
    pliki = sorted(katalog.glob("*.json"))
    if not pliki:
        pytest.skip("katalog analiz pusty")

    from dancelab.core.models import AnalysisResult

    # pierwszy plik z sensowną liczbą klatek — malutkie nie sprawdzają niczego
    for plik in pliki[:40]:
        dane = json.loads(plik.read_text())
        if len(dane.get("features") or []) >= 200:
            break
    else:
        pytest.skip("brak analizy z wystarczającą liczbą klatek")

    analiza = AnalysisResult.model_validate(dane)
    szer = 80
    z_terminala = os_energii(analiza, szer)
    p = P.zbuduj(analiza, punktow=szer)

    assert len(p.obwiednia) == szer
    z_gui = "".join(BLOKI[int(v * (len(BLOKI) - 1))] for v in p.obwiednia)
    assert z_gui == z_terminala, (
        "okno i terminal rysują różny kształt z tej samej analizy"
    )
    # dane, na których stoi ekran, muszą naprawdę być
    assert p.dlugosc_sec > 0
    assert any(p.ma_dane), "żaden punkt nie ma pomiaru"
