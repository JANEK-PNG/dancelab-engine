"""Zapis cue z okna trafia dokładnie tam, gdzie zapis z terminala.

Test jedzie na KOPII `master.db` i porównuje obie drogi co do milisekundy.
To jest warunek postawiony w planie kroku 4: okno nie dostaje własnej drogi
do bazy, więc jakakolwiek różnica pozycji oznacza, że dostało.

Pomija się czysto, gdy nie ma lokalnej bazy Rekordboksa (CI, świeży klon).
"""

import shutil
from pathlib import Path

import pytest

pytest.importorskip("pyrekordbox")

from dancelab.decision.cue_export_models import CuePlan
from dancelab.stan import zapis_cue
from dancelab.tui import cue_edycje, cue_zapis as CZ

LIVE = Path.home() / "Library/Pioneer/rekordbox/master.db"


class _Track:
    def __init__(self, tid: str, sciezka: str) -> None:
        self.track_id = tid
        self.source_path = sciezka
        self.title = "Utwór testowy"
        self.artist = "Test"


class _Analiza:
    def __init__(self, tid: str, sciezka: str) -> None:
        self.track = _Track(tid, sciezka)


@pytest.fixture()
def kopia_bazy(tmp_path, monkeypatch):
    """Kopia biblioteki plus zdjęta blokada procesu.

    pyrekordbox odmawia zapisu przy otwartym Rekordboksie — to chroni ŻYWĄ
    bazę. Tu piszemy do kopii w tmp_path, więc blokada decydowałaby tylko
    o tym, czy zestaw testów przechodzi zależnie od tego, czy Janek ma akurat
    otwarty program. Zdjęta wyłącznie dla kopii; własna odmowa `write_plan`
    zostaje nietknięta i ma swój osobny test.
    """
    if not LIVE.exists():
        pytest.skip("brak lokalnej master.db do skopiowania")
    import pyrekordbox.db6.database as _db
    from dancelab.ingestion import cue_ledger, rekordbox_cue_writer as W

    monkeypatch.setattr(_db, "get_rekordbox_pid", lambda *a, **k: 0)
    monkeypatch.setattr(W, "is_rekordbox_running", lambda: False)
    monkeypatch.setattr(cue_ledger, "SCIEZKA", tmp_path / "rejestr.json")
    dst = tmp_path / "master.db"
    shutil.copy2(LIVE, dst)
    return dst


def _pierwszy_utwor(baza):
    """(ContentID, ścieżka pliku) pierwszego utworu z kolekcji."""
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables
    db = Rekordbox6Database(path=str(baza))
    try:
        r = db.session.query(tables.DjmdContent).filter(
            tables.DjmdContent.FolderPath != None  # noqa: E711
        ).first()
        return str(r.ID), str(r.FolderPath)
    finally:
        db.close()


def _edycje_z_padem(tid: str, pad: str, ms: int) -> dict:
    e = cue_edycje.nowe()
    cue_edycje.postaw(e, tid, pad, ms)
    return e


POZYCJA_MS = 61_500


def test_okno_i_terminal_licza_ten_sam_plan(kopia_bazy):
    """Ta sama nakładka edycji → identyczne pozycje w obu drogach."""
    cid, sciezka = _pierwszy_utwor(kopia_bazy)
    by_id = {"t1": _Analiza("t1", sciezka)}
    edycje = _edycje_z_padem("t1", "D", POZYCJA_MS)

    # droga terminala — dokładnie te wywołania, które robi tui/app.py
    content_ids = CZ.mapa_content_id(kopia_bazy)
    plan_tui, _ids, _pominiete = CZ.zbuduj_plan_do_zapisu(
        CuePlan(), edycje, by_id, ["t1"], content_ids)

    # droga okna — jedno wywołanie warstwy stanu
    wynik = zapis_cue.przygotuj(CuePlan(), edycje, by_id, ["t1"],
                                baza=kopia_bazy)

    poz_tui = [(t.content_id, c.pad_label, c.position_ms)
               for t in plan_tui.tracks for c in t.cues]
    poz_gui = [(t.content_id, c.pad_label, c.position_ms)
               for t in wynik["plan"].tracks for c in t.cues]
    assert poz_tui == poz_gui == [(cid, "D", POZYCJA_MS)]


def test_zapis_z_okna_lezy_w_bazie_co_do_milisekundy(kopia_bazy, tmp_path):
    """Pełna droga okna: policz → zapisz → odczytaj świeżym połączeniem."""
    cid, sciezka = _pierwszy_utwor(kopia_bazy)
    by_id = {"t1": _Analiza("t1", sciezka)}
    edycje = _edycje_z_padem("t1", "D", POZYCJA_MS)

    wynik = zapis_cue.przygotuj(CuePlan(), edycje, by_id, ["t1"],
                                baza=kopia_bazy)
    assert wynik["do_zapisu"] == 1
    assert wynik["spoza_kolekcji"] == []

    zapisane = zapis_cue.zapisz(wynik["plan"], nazwa="test",
                                baza=kopia_bazy,
                                katalog_kopii=tmp_path / "kopie")
    assert zapisane["zapisane"] == 1
    assert zapisane["kopia"]

    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables
    db = Rekordbox6Database(path=str(kopia_bazy))
    try:
        wiersze = db.session.query(tables.DjmdCue).filter(
            tables.DjmdCue.ContentID == cid,
            tables.DjmdCue.Kind == 5).all()
    finally:
        db.close()
    assert [int(w.InMsec) for w in wiersze] == [POZYCJA_MS]


def test_utwor_spoza_kolekcji_wraca_imiennie(kopia_bazy):
    """Nie zgadujemy dopasowania: utwór, którego nie ma w bazie, jest
    pomijany z nazwy, a nie po cichu."""
    by_id = {"widmo": _Analiza("widmo", "/nie/ma/takiego/Utwór Widmo.aiff")}
    edycje = _edycje_z_padem("widmo", "A", 1000)
    wynik = zapis_cue.przygotuj(CuePlan(), edycje, by_id, ["widmo"],
                                baza=kopia_bazy)
    assert wynik["do_zapisu"] == 0
    assert any("Widmo" in n for n in wynik["spoza_kolekcji"])
