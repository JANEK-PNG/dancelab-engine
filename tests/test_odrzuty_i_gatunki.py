"""Two silent failures from the production-line schematic (03.09), made loud.

* Gatekeeper rejections were cut at five in the notes and the rest vanished;
  the full list now lands in ``odrzuty_bramkarza.jsonl`` beside the analyses.
* A set built with zero genres looked like one built with genres; the build
  now counts genre coverage and says "BEZ GATUNKÓW" when there is none.
"""

from __future__ import annotations

import json

from dancelab.stan import budowa


def test_full_rejection_list_lands_beside_the_analyses(tmp_path):
    odrzucone = [(f"/m/zly{i}.aiff", "stem") for i in range(8)]
    notka = budowa.zapisz_odrzuty(str(tmp_path), odrzucone, [("/m/pad.wav", "decode")])
    plik = tmp_path / budowa.ODRZUTY_PLIK
    wiersze = [json.loads(w) for w in plik.read_text(encoding="utf-8").splitlines()]
    assert len(wiersze) == 9, "all eight rejections and the failed analysis, not five"
    assert {w["etap"] for w in wiersze} == {"bramkarz", "analiza"}
    assert wiersze[7]["sciezka"] == "/m/zly7.aiff" and wiersze[7]["powod"] == "stem"
    assert "9 plików" in notka and str(plik) in notka
    assert not plik.name.endswith(".json"), "catalog readers glob *.json and must skip it"


def test_nothing_rejected_writes_nothing(tmp_path):
    assert budowa.zapisz_odrzuty(str(tmp_path), [], []) is None
    assert not (tmp_path / budowa.ODRZUTY_PLIK).exists()


def test_missing_directory_is_said_not_created(tmp_path):
    brak = tmp_path / "nie_ma"
    notka = budowa.zapisz_odrzuty(str(brak), [("/m/a.aiff", "stem")], [])
    assert "nie zapisałem" in notka and not brak.exists()


def test_scan_writes_the_list_and_keeps_its_last_note(monkeypatch, tmp_path):
    from dancelab.core import config as C
    from dancelab.ingestion import bramkarz as B
    from dancelab.workflows import smart_playlist as SP

    pliki = [f"/m/{i}.aiff" for i in range(9)]
    monkeypatch.setattr(SP, "discover_audio_files", lambda folder, **k: list(pliki))
    monkeypatch.setattr(B, "przesiej", lambda p, run_fn=None: (
        [pliki[0]], [(x, "stem") for x in pliki[1:]]))
    monkeypatch.setattr(C, "load_config", lambda *a, **k: object())
    monkeypatch.setattr(SP, "analyze_files", lambda files, cfg, **k: ([f"a:{f}" for f in files], []))
    _, notki = budowa.przeanalizuj_folder("/m", str(tmp_path))
    assert (tmp_path / budowa.ODRZUTY_PLIK).read_text().count("\n") == 8
    assert any("…i 3 kolejnych odrzutów" in n for n in notki)
    assert any("pełna lista 8 plików" in n for n in notki)
    assert notki[-1] == "przeanalizowane: 1 z 1 plików"


class _T:
    def __init__(self, gatunek):
        self.style_label = gatunek


class _A:
    def __init__(self, gatunek):
        self.track = _T(gatunek)


def test_genre_coverage_and_the_no_genre_marker():
    by_id = {"a": _A("Techno"), "b": _A(None), "c": _A(None), "d": _A("House")}
    assert budowa.gatunki_w_secie(["a", "b", "c", "d"], by_id) == (2, 4)
    assert budowa.notka_gatunkow(0, 20).startswith("BEZ GATUNKÓW")
    assert "3 z 10" in budowa.notka_gatunkow(3, 10)
    assert budowa.notka_gatunkow(5, 10) is None
    assert budowa.notka_gatunkow(10, 10) is None
    assert budowa.notka_gatunkow(0, 0) is None
