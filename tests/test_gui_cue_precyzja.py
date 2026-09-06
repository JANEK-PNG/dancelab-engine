"""Faza 2, grupa 2 (02.09): precyzja cue, gatunki i szkic z filarów w oknie.

Wszystko istniało w terminalu od 09.08: T (wpisany czas z kwantyzacją do
taktu), druga litera pada (przeniesienie do głowicy), gotowe czasy fraz,
Ctrl+G (gatunki z pokryciem) i G (szkic z filarów bez automatycznej budowy).
"""

import pytest

from dancelab.gui.most import Most


class _Siatka:
    bpm = 120.0
    downbeat_phase_verified = False


class _T:
    def __init__(self, tid):
        self.track_id, self.source_path, self.title, self.artist = tid, f"/m/{tid}.aiff", tid, "X"
        self.bpm_estimate, self.key_estimate, self.duration_sec = 120.0, "8A", 300.0
        self.key_detection_source = self.key_confidence = self.style_label = None
        self.sound_embedding = None


class _A:
    def __init__(self, tid):
        self.track, self.features, self.beatgrid, self.segments = _T(tid), [], _Siatka(), []


@pytest.fixture()
def most(tmp_path, monkeypatch):
    from dancelab.tui import cue_edycje as CE
    # bez siatki Rekordboxa: kwantyzacja do NASZEJ siatki, tu = identyczność
    monkeypatch.setattr(Most, "_takty", lambda self, tid: [])
    monkeypatch.setattr(CE, "snap_cue_start", lambda siatka, sek: float(sek), raising=False)
    m = Most(katalog=str(tmp_path / "analizy"))
    m._analizy = {"t1": _A("t1")}
    m.pady("t1")
    m.postaw_pad("t1", "A", 10_000)
    return m


def test_wpisany_czas_przesuwa_pad_o_cale_uderzenia(most, monkeypatch):
    from dancelab.tui import cue_edycje as CE
    monkeypatch.setattr(CE, "czas_po_kwantyzacji", lambda siatka, sek, takty=None: (sek, "trafione w siatkę"))
    odp = most.ustaw_czas_pada("t1", "A", "2:31")
    assert "blad" not in odp, odp
    assert odp["position_ms"] == 151_000          # 120 BPM: 141 s = 282 uderzenia
    assert odp["pady"]["A"]["position_ms"] == 151_000
    assert "trafione" in odp["powod"]


def test_wpisany_czas_odmawia_z_powodem(most):
    assert "nie rozumiem czasu" in most.ustaw_czas_pada("t1", "A", "dwie minuty")["blad"]
    assert "za końcem utworu" in most.ustaw_czas_pada("t1", "A", "9:00")["blad"]
    assert "nie jest postawiony" in most.ustaw_czas_pada("t1", "Z", "1:00")["blad"]


def test_przeniesienie_na_glowice_wymaga_odtwarzacza_na_tym_utworze(most, monkeypatch):
    odp = most.przenies_pad_na_glowice("t1", "A")
    assert "najpierw P" in odp["blad"]

    from dancelab.tui import cue_edycje as CE
    monkeypatch.setattr(CE, "czas_po_kwantyzacji", lambda siatka, sek, takty=None: (sek, "trafione"))
    most._audio._path, most._audio._offset = "/m/t1.aiff", 60.0     # stoi na t1, 1:00
    odp = most.przenies_pad_na_glowice("t1", "A")
    assert "blad" not in odp, odp
    assert odp["position_ms"] == 60_000


def test_propozycje_fraz_wracaja_nazwane(most):
    class _Seg:
        def __init__(self, t, s): self.segment_type, self.start_sec = t, s
    most._analizy["t1"].segments = [_Seg("intro", 0.0), _Seg("breakdown", 95.5)]
    odp = most.propozycje("t1", 45_000)
    nazwy = [p["nazwa"] for p in odp["propozycje"]]
    assert "silnik" in nazwy and nazwy == sorted(nazwy, key=lambda n: [p["sec"] for p in odp["propozycje"] if p["nazwa"] == n][0])
    assert any(abs(p["sec"] - 95.5) < 0.01 for p in odp["propozycje"])
    assert any(p["nazwa"] == "silnik" and abs(p["sec"] - 45.0) < 0.01 for p in odp["propozycje"])


def test_gatunki_licza_pule_i_przelaczaja_wybor(most, monkeypatch):
    t = most._analizy["t1"].track
    t.style_label = "Tech House"
    most._analizy_pula = [most._analizy["t1"]]
    odp = most.gatunki("")
    assert odp["mam"] == 1 and odp["bez_tagu"] == 0
    assert odp["sekcje"][0]["gatunki"][0] == {"nazwa": "Tech House", "ile": 1, "wybrany": False}
    assert most.przelacz_gatunek("", "Tech House")["wybrane"] == "Tech House"
    assert most.przelacz_gatunek("Tech House", "Tech House")["wybrane"] == ""


def test_gatunki_bez_puli_rusza_w_tle(most, monkeypatch):
    monkeypatch.setattr(most, "_pula", lambda: most._analizy_pula.__setitem__(slice(None), []) if False else None)
    assert most.gatunki("") == {"ruszylo": True}


def test_szkic_z_filarow_bez_automatycznej_budowy(most, monkeypatch, tmp_path):
    from dancelab.tui import user_store
    monkeypatch.setattr(user_store, "MIN_FILARY", 2)
    stan = {"playlisty": [{"nazwa": "P", "kotwica": None, "filary": [
        {"track_id": "t1", "path": "/m/t1.aiff", "rola": "otwarcie"},
        {"track_id": "t2", "path": "/m/t2.aiff", "rola": ""},
        {"track_id": "znikl", "path": "/m/znikl.aiff", "rola": ""}]}],
        "aktywna_playlista": 0, "filary": []}
    most._stan_dja = stan

    class _Repo:
        def __init__(self, katalog): pass
        def get(self, tid):
            if tid == "znikl":
                raise FileNotFoundError(tid)
            return _A(tid)
    from dancelab.storage import repositories
    monkeypatch.setattr(repositories, "FileAnalysisRepository", _Repo)

    odp = most.szkic_z_filarow({"minuty": "60", "tempo_okno": "124-134"})
    assert "blad" not in odp, odp
    assert most._kolejnosc == ["t1", "t2"]
    assert [u["track_id"] for u in odp["utwory"]] == ["t1", "t2"]
    assert odp["filary"] == ["t1", "t2"]
    assert any("nieobecny" in n and "znikl" in n for n in odp["notki"])
    assert any("SZKIC" in n for n in odp["notki"])
    assert most._ctx_edycji["bpm_min"] == 124.0 and most._ctx_edycji["wagi"] is not None
    assert most._plan_silnika == []               # szkic to nie propozycja silnika


def test_szkic_odmawia_ponizej_minimum(most):
    most._stan_dja = {"playlisty": [{"nazwa": "P", "kotwica": None, "filary": [
        {"track_id": "t1", "path": "/m/t1.aiff", "rola": ""}]}], "aktywna_playlista": 0, "filary": []}
    assert "minimum" in most.szkic_z_filarow({})["blad"]
