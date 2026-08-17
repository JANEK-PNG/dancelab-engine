"""Straż słownika interfejsu (audyt nomenklatury 09.08.2026).

Zasada z audytu: JEDNA rzecz = JEDNO słowo. Odsłuch nazywał się w aplikacji
na pięć sposobów („odsłuch", „auto-podgląd", „GRA:", „Graj/Pauza",
„Posłuchaj"), a jedyne angielskie słowo w polskim UI wisiało na przełączniku
okładek. Ten test nie sprawdza działania — pilnuje, żeby słownik nie
rozjechał się ponownie przy kolejnych zmianach.
"""

from __future__ import annotations

import pathlib
import re

ZRODLO = pathlib.Path("src/dancelab/tui/app.py").read_text(encoding="utf-8")


def _widoczne_napisy() -> str:
    """Napisy trafiające do użytkownika: noty, etykiety, podpowiedzi."""
    kawalki = re.findall(r'_note\((?:f)?"([^"]+)"', ZRODLO)
    kawalki += re.findall(r'Label\("([^"]+)"', ZRODLO)
    kawalki += re.findall(r'Binding\("[^"]+", "[^"]+", "([^"]+)"', ZRODLO)
    return " · ".join(kawalki)


def test_odsluch_ma_jedna_nazwe():
    """Rzeczownik zawsze „odsłuch"; „podgląd" zarezerwowany dla PATRZENIA
    (zakładka Cue: „TYLKO PODGLĄD, nic nie zapisuję")."""
    napisy = _widoczne_napisy()
    assert "auto-podgląd" not in napisy
    assert "GRA:" not in napisy and "GRA szew" not in napisy
    assert "odsłuch" in napisy


def test_interfejs_jest_po_polsku():
    """Etykiety widoczne dla DJ-a bez angielskich wtrętów (poza nazwami
    własnymi: Rekordbox, RB, LUFS, BPM, DanceLab)."""
    wlasne = {"rekordbox", "rb", "lufs", "bpm", "dancelab", "cdj", "id"}
    angielskie = {"artwork", "preview", "cue point", "playlist", "settings",
                  "loading", "search", "save", "load", "export"}
    napisy = _widoczne_napisy().lower()
    for slowo in angielskie:
        # granice słów: polska odmiana („playlisty", „playlistach") zawiera
        # angielski rdzeń jako podciąg i NIE jest wtrętem
        assert not re.search(rf"\b{re.escape(slowo)}\b", napisy), \
            f"angielskie słowo w UI: {slowo}"
    assert wlasne, "nazwy własne wolno zostawić"


def test_klawisze_mowia_co_robia_i_z_czym():
    """Czasownik + dopełnienie: „Wczytaj plan", nie samo „Wczytaj"."""
    etykiety = dict(re.findall(
        r'Binding\("([^"]+)", "[^"]+", "([^"]+)"', ZRODLO))
    assert etykiety["o"] == "Wczytaj plan"
    # 13.08 zapis planu przeniesiony na Ctrl+S, bo S w Secie gra szew
    assert etykiety["ctrl+s"] == "Zapisz plan"
    assert etykiety["s"] == "Zagraj szew"
    assert etykiety["w"] == "Wyślij do RB"
    assert etykiety["l"] == "Notki", "panel i klawisz muszą mówić tak samo"
