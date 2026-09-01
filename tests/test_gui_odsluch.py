"""Odsłuch w oknie: P na utworze, głowica, skoki, szew — i uczciwa odmowa.

Skarga Janka 01.09: „nie działa odtwarzanie muzyki". Nie było czego naprawiać
— w oknie nie było ani jednej linii dźwięku, a guzik `#btn-graj` w stopce był
narysowany i martwy. Cały odtwarzacz siedział w terminalu.

Testy pilnują czterech rzeczy, na których ta funkcja stoi:

1. utwór ZE STRUMIENIA dostaje zdanie o sobie, a odtwarzacz nie jest dotykany —
   zmierzone 01.09: 7935 z 8261 analiz nie ma pliku na dysku, więc odmowa jest
   przypadkiem NORMALNYM, nie błędem;
2. P jest przełącznikiem: start → pauza → wznowienie od zapamiętanego miejsca;
3. koniec utworu jest odróżnialny od pauzy — bez tego głowica zamarza w miejscu,
   w którym nic już nie gra;
4. render szwu chodzi w wątku i jest CICHY; dźwięk rusza dopiero w `postep_szwu`,
   czyli na wątku wywołania z JS, i tylko po Twoim geście.

Dźwięk w testach nie startuje nigdy: proces odtwarzacza jest atrapą.
"""

import subprocess

import pytest

from dancelab.gui.most import Most
from dancelab.stan import dziennik, odtwarzacz as odt


class _Track:
    def __init__(self, tid: str, sciezka: str) -> None:
        self.track_id = tid
        self.bpm_estimate = 128.0
        self.key_estimate = "8A"
        self.title = f"Utwór {tid}"
        self.artist = "Test"
        self.duration_sec = 300.0
        self.source_path = sciezka
        self.sound_embedding = None


class _Siatka:
    bpm = 130.0


class _Analiza:
    def __init__(self, tid: str, sciezka: str) -> None:
        self.track = _Track(tid, sciezka)
        self.beatgrid = _Siatka()
        self.features = []


class _FakeProc:
    """Proces, który nie robi dźwięku — tylko pamięta, czym go wywołano."""

    def __init__(self, cmd) -> None:
        self.cmd = cmd
        self.zakonczony = False

    def poll(self):
        return 0 if self.zakonczony else None

    def terminate(self) -> None:
        self.zakonczony = True


@pytest.fixture()
def most(tmp_path, monkeypatch):
    monkeypatch.setattr(dziennik, "KATALOG", tmp_path / "werdykty")
    monkeypatch.setattr(odt, "FFPLAY", "/fake/ffplay")
    monkeypatch.setattr(odt, "AFPLAY", "/fake/afplay")
    m = Most(katalog=str(tmp_path / "analizy"))
    m._analizy = {
        "t1": _Analiza("t1", "/muzyka/t1.aiff"),
        "t2": _Analiza("t2", "/muzyka/t2.aiff"),
        # strumień Apple Music: ma tempo i siatkę, nie ma pliku
        "s1": _Analiza("s1", "apple-music:tracks:123"),
    }
    m._kolejnosc = ["t1", "t2"]
    return m


@pytest.fixture()
def procesy(monkeypatch):
    ruszone = []
    monkeypatch.setattr(
        subprocess, "Popen",
        lambda cmd: ruszone.append(_FakeProc(cmd)) or ruszone[-1])
    return ruszone


def test_strumien_odmawia_zdaniem_i_nie_rusza_procesu(most, procesy):
    wynik = most.graj("s1")
    assert wynik["bez_pliku"] is True
    assert "nie ma pliku na dysku" in wynik["blad"]
    assert "Rekordboksie" in wynik["blad"]
    assert procesy == []                    # odtwarzacz nietknięty


def test_p_jest_przelacznikiem_start_pauza_wznowienie(most, procesy):
    start = most.graj("t1")
    assert start["akcja"] == "start"
    assert start["gra"] is True
    assert start["track_id"] == "t1"
    assert len(procesy) == 1

    pauza = most.graj("t1")
    assert pauza["akcja"] == "pauza"
    assert pauza["gra"] is False
    assert procesy[0].zakonczony is True

    wznowienie = most.graj("t1")
    assert wznowienie["akcja"] == "wznowienie"
    assert len(procesy) == 2


def test_start_od_zera_gra_afplayem_a_od_srodka_ffplayem(most, procesy):
    """Hybryda z terminala: afplay startuje natychmiast, ale nie umie seeka."""
    most.graj("t1")
    assert procesy[-1].cmd[0] == "/fake/afplay"

    most._analizy["t1"].pady = None
    most._audio._offset = 42.0               # udajemy pauzę w środku utworu
    most.graj("t1")                          # gra → pauza
    most.graj("t1")                          # pauza → wznowienie
    assert procesy[-1].cmd[0] == "/fake/ffplay"
    assert "-ss" in procesy[-1].cmd


def test_inny_utwor_przelacza_a_nie_zatrzymuje_w_ciszy(most, procesy):
    most.graj("t1")
    drugi = most.graj("t2")
    assert drugi["akcja"] == "start"
    assert drugi["track_id"] == "t2"
    assert drugi["gra"] is True
    assert procesy[0].zakonczony is True      # poprzedni zabity


def test_koniec_utworu_to_nie_pauza(most, procesy):
    most.graj("t1")
    procesy[-1].zakonczony = True             # utwór doszedł do końca sam
    stan = most.stan_odtwarzania()
    assert stan["skonczyl_sie"] is True
    assert stan["gra"] is False
    assert stan["pozycja_sec"] == 0.0
    assert stan["track_id"] == "t1"           # widok wie, co się skończyło


def test_skok_bez_grania_mowi_dlaczego(most, procesy):
    assert most.skocz(8)["blad"] == "nic nie gra"


def test_skok_liczy_uderzenia_tempem_siatki(most, procesy):
    """Skok jest MUZYCZNY: 8 uderzeń przy 130 BPM to 3,69 s, nie 8 s."""
    most.graj("t1")
    most.skocz(8)
    ss = procesy[-1].cmd[procesy[-1].cmd.index("-ss") + 1]
    assert 3.5 < float(ss) < 4.0


def test_zamkniecie_okna_zabija_dzwiek(most, procesy):
    most.graj("t1")
    most.zamknij()
    assert procesy[-1].zakonczony is True


def test_szew_bez_nastepnego_odmawia(most, procesy):
    assert "nie ma następnego" in most.graj_szew("t2")["blad"]


def test_szew_ze_strumieniem_odmawia_przed_renderem(most, procesy):
    most._kolejnosc = ["t1", "s1"]
    wynik = most.graj_szew("t1")
    assert wynik["bez_pliku"] is True
    assert most._szew_stan["stan"] == "bezczynny"   # wątek nie ruszył


def test_render_szwu_jest_cichy_a_dzwiek_rusza_dopiero_w_postepie(most,
                                                                  procesy,
                                                                  tmp_path):
    """Rozdział, na którym stoi zasada „dźwięk tylko z Twojego gestu":
    wątek renderuje plik i milczy, granie dzieje się na wątku wywołań z JS."""
    plik = tmp_path / "szew.wav"
    plik.write_bytes(b"RIFF")
    most._szew_stan = {"stan": "gotowe", "etykieta": "szew silnika",
                       "para": ["t1", "t2"],
                       "info": {"output": plik, "bpm": 128.0,
                                "cue_a_sec": 200.0, "cue_b_sec": 12.0}}
    assert procesy == []                       # po renderze nic nie gra

    wynik = most.postep_szwu()
    assert wynik["stan"] == "gra"
    assert len(procesy) == 1
    stan = most.stan_odtwarzania()
    assert stan["rodzaj"] == "szew"
    assert stan["para"] == ["t1", "t2"]
    assert "szew silnika" in stan["opis"]


def test_szew_juz_renderowany_nie_rusza_drugi_raz(most, procesy):
    most._szew_stan = {"stan": "trwa"}
    assert "już się renderuje" in most.graj_szew("t1")["blad"]


def test_odsluch_od_pada_nie_udaje_ze_dj_widzial_pady(most, procesy):
    """Uczciwość dziennika (Q14): pad silnika liczy się za zaakceptowany
    dopiero, gdy DJ go ZOBACZYŁ. Odsłuch czyta pady maszynowo — i szew czyta
    nawet pady NASTĘPNEGO utworu, którego ekranu nikt nie otwierał."""
    from dancelab.decision.cue_export_models import CuePlan, PlannedCue, TrackCuePlan

    most._plan_cue = CuePlan(tracks=[TrackCuePlan(content_id="t1", cues=[
        PlannedCue(content_id="t1", position_ms=1000, kind=1,
                   pad_label="A")])])
    most.graj("t1", pad="A")
    assert most._pady_pokazane == set()          # odsłuch nie jest pokazaniem

    most.pady("t1")                              # ekran otwarty — TO jest pokazanie
    assert most._pady_pokazane == {"t1"}
