"""Playlisty jako projekty + filary z rolami (decyzje Janka 11.08).

Trzy decyzje przybite testami, żeby nie cofnęły się po cichu:
1. filary żyją W PLAYLISTACH, nie globalnie (stare globalne migrują
   do playlisty „Moje filary" i nikt nic nie traci);
2. filar niesie ROLĘ (otwarcie / buildup / oddech / zamknięcie / bez roli),
   a role wyłączności wypierają poprzednika jawnie, nie po cichu;
3. nazwa nowej playlisty jest proponowana z metadanych puli.
"""

import json

from dancelab.core.models import AnalysisResult, Track
from dancelab.tui import user_store as U


def _analiza(tid, bpm=128.0, gatunek="House"):
    return AnalysisResult(engine_version="t", track=Track(
        track_id=tid, bpm_estimate=bpm, style_label=gatunek,
        source_path=f"/m/{tid}.aiff"))


def _stan():
    return {k: (list(v) if isinstance(v, list) else v)
            for k, v in U._EMPTY.items()}


def test_migracja_globalnych_filarow_do_playlisty(tmp_path, monkeypatch):
    """Stare filary NIE giną: stają się aktywną playlistą „Moje filary"."""
    stary = tmp_path / "stan.json"
    stary.write_text(json.dumps({
        "ulubione_utwory": [], "ulubione_playlisty": [],
        "filary": [{"track_id": "a", "path": "/m/a.aiff"},
                   {"track_id": "b", "path": "/m/b.aiff"}]}))
    monkeypatch.setattr(U, "STATE_PATH", stary)
    state = U.load_state()
    assert [p["nazwa"] for p in state["playlisty"]] == ["Moje filary"]
    assert state["aktywna_playlista"] == 0
    wpisy = U.filary_wpisy(state)
    assert [e["track_id"] for e in wpisy] == ["a", "b"]
    assert all(e["rola"] == "" for e in wpisy)   # ról nie zgadujemy


def test_bez_playlisty_filar_odmawia_z_powodem():
    state = _stan()
    ok, powod = U.ustaw_filar(state, "x", "/m/x.aiff", "otwarcie")
    assert not ok and "playlist" in powod


def test_role_wylacznosci_wypieraja_jawnie():
    """Dwóch otwierających to sprzeczność — poprzedni traci rolę, nie znika."""
    state = _stan()
    U.nowa_playlista(state, "Piątek")
    U.ustaw_filar(state, "a", "/m/a.aiff", "otwarcie")
    U.ustaw_filar(state, "b", "/m/b.aiff", "otwarcie")
    role = {e["track_id"]: e["rola"] for e in U.filary_wpisy(state)}
    assert role == {"a": "", "b": "otwarcie"}   # a został filarem bez roli


def test_kotwica_nalezy_do_playlisty():
    state = _stan()
    U.nowa_playlista(state, "Piątek")
    assert U.ustaw_kotwice_playlisty(state, "Ben UFO")
    U.nowa_playlista(state, "Sobota")
    assert U.aktywna_playlista(state)["kotwica"] is None
    state["aktywna_playlista"] = 0
    assert U.aktywna_playlista(state)["kotwica"] == "Ben UFO"


def test_zdejmowanie_i_limit():
    state = _stan()
    U.nowa_playlista(state, "P")
    for i in range(U.MAX_FILARY):
        ok, _ = U.ustaw_filar(state, f"t{i}", f"/m/t{i}.aiff", "")
        assert ok
    ok, powod = U.ustaw_filar(state, "za_duzo", "/m/z.aiff", "")
    assert not ok and "limit" in powod
    assert U.zdejmij_filar(state, "t0", "/m/t0.aiff")
    assert len(U.filary_wpisy(state)) == U.MAX_FILARY - 1


def test_nazwa_z_metadanych_sklada_sie_z_puli():
    by_id = {f"t{i}": _analiza(f"t{i}", bpm=120 + i,
                               gatunek="Breaks / UK Bass" if i < 7 else "House")
             for i in range(10)}
    nazwa = U.nazwa_z_metadanych(by_id)
    assert "120–129" in nazwa and "Breaks / UK Bass" in nazwa
    # dzień tygodnia jest pierwszym członem
    assert nazwa.split(" · ")[0] in ["Poniedziałek", "Wtorek", "Środa",
                                     "Czwartek", "Piątek", "Sobota",
                                     "Niedziela"]


def test_zbudowany_set_zapisuje_sie_do_aktywnej_playlisty():
    """Janek 12.08: klik „buduj" = utwory automatycznie W playliście.
    Ostatnia budowa wygrywa — playlista trzyma jeden, aktualny set."""
    state = _stan()
    assert not U.zapisz_utwory_playlisty(state, [{"track_id": "a",
                                                  "path": "/m/a.aiff"}])
    U.nowa_playlista(state, "Piątek")
    assert U.zapisz_utwory_playlisty(
        state, [{"track_id": "a", "path": "/m/a.aiff"},
                {"track_id": "b", "path": "/m/b.aiff"}])
    assert [e["track_id"] for e in U.utwory_playlisty(state)] == ["a", "b"]
    U.zapisz_utwory_playlisty(state, [{"track_id": "c", "path": "/m/c.aiff"}])
    assert [e["track_id"] for e in U.utwory_playlisty(state)] == ["c"]


def test_utwory_naleza_do_playlisty_nie_do_stanu():
    state = _stan()
    U.nowa_playlista(state, "Piątek")
    U.zapisz_utwory_playlisty(state, [{"track_id": "a", "path": "/m/a.aiff"}])
    U.nowa_playlista(state, "Sobota")
    assert U.utwory_playlisty(state) == []          # nowa — pusta
    state["aktywna_playlista"] = 0
    assert [e["track_id"] for e in U.utwory_playlisty(state)] == ["a"]


def test_stan_przezywa_zapis_i_odczyt(tmp_path, monkeypatch):
    monkeypatch.setattr(U, "STATE_PATH", tmp_path / "stan.json")
    state = _stan()
    U.nowa_playlista(state, "Piątek · 130–135 · jak Ben UFO")
    U.ustaw_kotwice_playlisty(state, "Ben UFO")
    U.ustaw_filar(state, "a", "/m/a.aiff", "zamkniecie")
    U.zapisz_utwory_playlisty(state, [{"track_id": "a", "path": "/m/a.aiff"}])
    U.save_state(state)
    wczytany = U.load_state()
    pl = U.aktywna_playlista(wczytany)
    assert pl["nazwa"].startswith("Piątek")
    assert pl["kotwica"] == "Ben UFO"
    assert U.rola_filara(wczytany, "a", "/m/a.aiff") == "zamkniecie"
    assert [e["track_id"] for e in U.utwory_playlisty(wczytany)] == ["a"]
