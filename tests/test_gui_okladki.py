"""Faza 2, grupa 3c (02.09): okładki w oknie — z tagów, jak mozaika w terminalu."""

import time

from dancelab.gui import most as M
from dancelab.gui.most import Most


def _most(tmp_path, monkeypatch, sciezka="/m/a.aiff"):
    m = Most(katalog=str(tmp_path))
    m._spis = [{"track_id": "a", "sciezka": sciezka, "tytul": "A"},
               {"track_id": "s", "sciezka": "apple-music:tracks:1", "tytul": "S"}]
    m._stan_dja = {"okladki_w_liscie": False}
    monkeypatch.setattr(m, "_zapisz_stan_uzytkownika", lambda: None)
    M._OKLADKI.clear()
    return m


def test_okladka_z_tagow_jako_data_uri_a_strumien_pusto(tmp_path, monkeypatch):
    from dancelab.tui import okladki as O
    monkeypatch.setattr(O, "_bajty_okladki", lambda p: b"\xff\xd8\xff\xe0JFIF" if p == "/m/a.aiff" else None)
    m = _most(tmp_path, monkeypatch)
    dane = m.okladka("a")["dane"]
    assert dane.startswith("data:image/jpeg;base64,")
    assert m.okladka("s")["dane"] is None          # strumień: nie ma pliku, nie ma tagów
    monkeypatch.setattr(O, "_bajty_okladki", lambda p: b"\x89PNG\r\n\x1a\n...")
    assert m.okladka("a")["dane"] is dane          # cache na sesję: nie czyta pliku drugi raz


def test_przelacznik_okladek_jest_wspolnym_stanem_dja(tmp_path, monkeypatch):
    m = _most(tmp_path, monkeypatch)
    assert m.okladki_stan()["wlaczone"] is False
    assert m.przelacz_okladki()["wlaczone"] is True
    assert m._stan_dja["okladki_w_liscie"] is True   # ten sam klucz, który czyta terminal (K)
    assert m.przelacz_okladki()["wlaczone"] is False


def test_dociaganie_w_tle_raportuje_i_czysci_cache(tmp_path, monkeypatch):
    from dancelab.ingestion import artwork_sync as AS
    monkeypatch.setattr(AS, "synchronizuj", lambda analizy, progress=None, should_stop=None: (
        progress(1, 2, "/m/a.aiff") or {"osadzone": ["/m/a.aiff"], "niejednoznaczne": [],
                                        "nieznalezione": [{"plik": "/m/b.aiff", "powod": "x"}],
                                        "bledy": [], "z_okladka_juz": 5}))
    m = _most(tmp_path, monkeypatch)
    monkeypatch.setattr(m, "_pula", lambda: [])
    M._OKLADKI["/m/a.aiff"] = "stare"
    assert m.dociagnij_okladki() == {"ruszylo": True}
    for _ in range(50):
        if m.postep_okladek()["stan"] != "trwa":
            break
        time.sleep(0.02)
    st = m.postep_okladek()
    assert st["stan"] == "gotowe" and (st["osadzone"], st["nieznalezione"], st["mialy_juz"]) == (1, 1, 5)
    assert "Reload Tags" in st["uwaga"] and st["raport"].endswith("artwork_raport.json")
    assert M._OKLADKI == {}                        # tagi się zmieniły — okładki od nowa
