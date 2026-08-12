"""Karta DJ-a z mostu danych mapy (spec 12.08) — układ 1:1 z kartą GUI.

Przybite: pasek temp na wspólnej osi z kreską mediany, mierniki z „—"
przy braku pomiaru, karta „profil w budowie" mówi ile brakuje, a DJ
spoza mapy dostaje uczciwą skromną kartę zamiast zgadywania.
"""

from __future__ import annotations

import json

from dancelab.tui import dj_profile as P


def test_pasek_tempa_zakres_i_mediana_na_osi():
    p = P.pasek_tempa(119, 140, 173, szer=34)
    assert "┃" in p, "kreska mediany"
    assert p.count("█") > 5, "zakres wypełniony"
    assert P.CHLODNY in p and P.CIEPLY in p, "chłodna i ciepła połowa"


def test_miernik_brak_pomiaru_to_kreska_nie_zero():
    assert P.miernik(None, P.CIEPLY).endswith("—")
    assert "0.55" in P.miernik(0.55, P.CIEPLY)


def test_karta_pelna_niesie_pomiary_gui():
    profil = {"bpm_lo": 119, "bpm_med": 140, "bpm_hi": 173, "harm_proc": 24,
              "skok_bpm": 5.0, "energia": 0.55, "groove": 0.43, "bas": 0.54,
              "sety": 2, "szwy_pelne": 177, "utwory_zmierzone": 215,
              "edycje": ["RA Podcast 2020", "RA Podcast 2025"]}
    k = P.karta("Tim Reaper", profil, w_kolekcji=True, grupa="brzmi jak: X")
    for fragment in ("Tim Reaper", "✓ w kolekcji", "K = ✕ wyrzuca",
                     "mediana [b]140", "24%", "±5", "0.55", "177 szwów",
                     "RA PODCAST 2025"):        # tagon-chip, wielkie litery
        assert fragment in k, fragment
    poza = P.karta("Tim Reaper", profil, w_kolekcji=False, grupa=None)
    assert "＋" in poza and "K dodaje do kolekcji" in poza


def test_karta_w_budowie_mowi_ile_brakuje():
    k = P.karta("Jyoty", {"sety": 1, "szwy": 39, "szwy_pelne": 4,
                          "edycje": []}, w_kolekcji=False, grupa=None)
    assert "profil w budowie" in k and "4 z 10" in k
    assert "nic tu nie zgadujemy" in k


def test_dj_spoza_mapy_dostaje_skromna_karte():
    k = P.karta("Ktoś Nowy", None, w_kolekcji=False, grupa="brzmi jak: Y")
    assert "nie ma w mapie" in k and "brzmi jak: Y" in k


def test_wczytaj_normalizuje_ksywy(tmp_path):
    plik = tmp_path / "dj_profile.json"
    plik.write_text(json.dumps({"djs": {"Catz 'n Dogz": {"sety": 9}}}))
    profile = P.wczytaj(plik)
    assert P.znajdz(profile, "catz 'n dogz")["sety"] == 9
    assert P.znajdz(profile, "nie ma") is None
    assert P.wczytaj(tmp_path / "brak.json") == {}


def test_wejscie_w_zakladke_pokazuje_pelne_karty_z_mostu(
        tmp_path, monkeypatch):
    """Wejście w DJ-e od razu pokazuje ścianę z pomiarami mostu — karta
    z pełnym profilem niesie medianę i harmonię, licznik zna filtry edycji."""
    import asyncio
    import json as _json

    import dancelab.decision.anchors as A
    import dancelab.tui.user_store as U
    from dancelab.tui.app import DanceLabTUI, KartaDJ
    monkeypatch.setattr(U, "STATE_PATH", tmp_path / "stan.json")
    monkeypatch.setattr(A, "load_anchor_book", lambda *a, **k: {"djs": {
        "Ayesha": {"centroid": [1, 0], "n_tracks": 39, "cos_median": 0.7},
        "Ben UFO": {"centroid": [0, 1], "n_tracks": 28, "cos_median": 0.8},
        "Tim Reaper": {"centroid": [1, 1], "n_tracks": 177,
                       "cos_median": 0.75}}})
    monkeypatch.setattr(A, "list_anchors", lambda *a, **k: [
        ("Ayesha", 39, 0.7), ("Ben UFO", 28, 0.8), ("Tim Reaper", 177, 0.75)])
    plik = tmp_path / "dj_profile.json"
    plik.write_text(_json.dumps({"djs": {"Ben UFO": {
        "bpm_lo": 120, "bpm_med": 133, "bpm_hi": 150, "harm_proc": 31,
        "skok_bpm": 4.0, "energia": 0.5, "groove": 0.4, "bas": 0.6,
        "sety": 3, "szwy": 40, "szwy_pelne": 28,
        "edycje": ["Garbicz Festival 2026"]}}}))
    monkeypatch.setattr(P, "PROFIL_PATH", plik)

    async def go():
        from textual.widgets import Button, TabbedContent
        app = DanceLabTUI(processed_dir="/nieistniejacy/katalog")
        async with app.run_test() as pilot:
            app.query_one("#tabs", TabbedContent).active = "tab-dj"
            await pilot.pause()
            karty = app.query(KartaDJ).nodes
            assert [k.dj for k in karty][0] == "Ben UFO", \
                "pełny profil przed resztą"
            tresc = str(karty[0].content)
            assert "mediana [b]133" in tresc and "31%" in tresc
            etykiety = [str(b.label) for b in
                        app.query_one("#dj-filtry").children
                        if isinstance(b, Button)]
            assert "Garbicz Festival 2026" in etykiety, "filtr edycji z danych"
    asyncio.run(go())
