"""Bug reports from the window: one folder per report, readable without questions."""

from __future__ import annotations

import json

from dancelab.gui import zgloszenia as Z
from dancelab.gui.most import Most
from dancelab.gui.zrzut_okna import zrzut_png

PNG = b"\x89PNG\r\n\x1a\nfake"


def _okno(**extra):
    return {"ekran": "szew", "tytul": "Bodhi — 433Mhz", "opis_gry": "pauza",
            "notki": ["BEZ GATUNKÓW: żaden z 20 utworów setu nie ma gatunku"],
            "bledy_konsoli": [f"err {i}" for i in range(30)], **extra}


def test_report_folder_has_json_markdown_and_screenshot(tmp_path):
    odp = Z.zapisz("strumień gra dalej po skoku", "powazny", _okno(), PNG,
                   {"dancelab": "0.1"}, katalog=tmp_path, teraz=1789000000)
    cel = tmp_path / odp["id"]
    assert odp["zrzut"] is True and (cel / "zrzut.png").read_bytes() == PNG
    d = json.loads((cel / "zgloszenie.json").read_text())
    assert d["opis"] == "strumień gra dalej po skoku" and d["waga"] == "powazny"
    assert d["okno"]["ekran"] == "szew" and "bledy_konsoli" not in d["okno"]
    assert d["bledy_konsoli"] == [f"err {i}" for i in range(10, 30)], "last 20 console errors"
    md = (cel / "ZGLOSZENIE.md").read_text()
    assert md.startswith(f"# {odp['id']} · poważny")
    assert "strumień gra dalej po skoku" in md and "BEZ GATUNKÓW" in md and "zrzut.png" in md


def test_report_without_screenshot_says_so(tmp_path):
    odp = Z.zapisz("coś", "drobny", {}, None, katalog=tmp_path)
    cel = tmp_path / odp["id"]
    assert odp["zrzut"] is False and not (cel / "zrzut.png").exists()
    assert "Zrzutu okna nie ma" in (cel / "ZGLOSZENIE.md").read_text()


def test_empty_description_or_unknown_weight_is_refused(tmp_path):
    assert "blad" in Z.zapisz("   ", "powazny", {}, PNG, katalog=tmp_path)
    assert "blad" in Z.zapisz("coś", "krytyczny", {}, PNG, katalog=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_two_reports_in_one_second_do_not_overwrite(tmp_path):
    a = Z.zapisz("pierwsze", "drobny", {}, None, katalog=tmp_path, teraz=1789000000)
    b = Z.zapisz("drugie", "drobny", {}, None, katalog=tmp_path, teraz=1789000000)
    assert b["id"] == a["id"] + "-2"
    assert [x["opis"] for x in Z.lista(tmp_path)] == ["drugie", "pierwsze"]


def test_screenshot_without_a_window_is_refused_not_raised():
    assert zrzut_png(None) == (None, "okno nie jest otwarte")


def test_bridge_keeps_the_screenshot_until_saved_or_dropped(tmp_path, monkeypatch):
    monkeypatch.setenv("DANCELAB_ZGLOSZENIA", str(tmp_path / "zgl"))
    m = Most(katalog=str(tmp_path))
    odp = m.zrzut_do_zgloszenia()
    assert odp["ok"] is False and odp["blad_zrzutu"] == "okno nie jest otwarte"
    m._zrzut_zgloszenia = (PNG, None)
    zapis = m.zapisz_zgloszenie("po skoku nie pauzuje", "blokujacy", _okno())
    cel = tmp_path / "zgl" / zapis["id"]
    d = json.loads((cel / "zgloszenie.json").read_text())
    assert zapis["zrzut"] is True and d["srodowisko"]["zrzut"] == "ok"
    assert d["srodowisko"]["katalog_analiz"] == str(tmp_path)
    assert m._zrzut_zgloszenia is None, "the screenshot is not reused for the next report"
    m._zrzut_zgloszenia = (PNG, None)
    assert m.porzuc_zgloszenie() == {"ok": True} and m._zrzut_zgloszenia is None
