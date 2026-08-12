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
    for fragment in ("Tim Reaper", "✓ w kolekcji", "mediana [b]140",
                     "24%", "±5", "0.55", "177 szwów", "RA Podcast 2025"):
        assert fragment in k, fragment


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
