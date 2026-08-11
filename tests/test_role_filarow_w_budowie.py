"""Role krańcowe filarów w budowie (Janek 11.08).

Deklaracja DJ-a (otwarcie/zamknięcie) jest mocniejsza niż rozstawienie
z trybu filarów — i mówimy jawnie, że oddech/buildup na razie nie celują
miejscem (obecność + most tak, pozycja jeszcze nie)."""

from dancelab.tui.app import _filary_for_build, _zastosuj_role_krancowe
from dancelab.core.models import AnalysisResult, Track


def _a(tid, bpm=128.0):
    return AnalysisResult(engine_version="t", track=Track(
        track_id=tid, bpm_estimate=bpm, source_path=f"/m/{tid}.aiff"))


def test_otwarcie_i_zamkniecie_nadpisuja_rozstaw():
    rozstaw = {1: "x", 5: "otw", 10: "zam"}     # tryb posadził je w środku
    nowe, notes = _zastosuj_role_krancowe(
        rozstaw, {"otw": "otwarcie", "zam": "zamkniecie"}, count=10)
    assert nowe[1] == "otw" and nowe[10] == "zam"
    assert "x" not in nowe.values()             # x stał na #1 — ustąpił
    assert any("otwarcie" in n for n in notes)


def test_role_srodkowe_nie_celuja_ale_mowia_o_tym():
    nowe, notes = _zastosuj_role_krancowe({}, {"o": "oddech"}, count=8)
    assert nowe == {}
    assert any("oddech/buildup" in n for n in notes)


def test_filary_for_build_niesie_role_z_aktywnej_playlisty():
    by_id = {t: _a(t) for t in ("a", "b", "c")}
    state = {"filary": [], "playlisty": [{
        "nazwa": "P", "kotwica": None, "filary": [
            {"track_id": "a", "path": "/m/a.aiff", "rola": "otwarcie"},
            {"track_id": "b", "path": "/m/b.aiff", "rola": ""},
            {"track_id": "c", "path": "/m/c.aiff", "rola": "zamkniecie"}]}],
        "aktywna_playlista": 0}
    kept, notes, role = _filary_for_build(state, by_id, None, None, 10)
    assert set(kept) == {"a", "b", "c"}
    assert role == {"a": "otwarcie", "c": "zamkniecie"}


def test_bez_aktywnej_playlisty_budowa_bez_filarow():
    """Stare globalne filary NIE przeciekają do budowy — źródłem prawdy
    jest aktywna playlista (migracja i tak robi z nich playlistę)."""
    by_id = {"a": _a("a")}
    state = {"filary": [{"track_id": "a", "path": "/m/a.aiff"}],
             "playlisty": [], "aktywna_playlista": None}
    kept, notes, role = _filary_for_build(state, by_id, None, None, 10)
    assert kept == [] and role == {}
