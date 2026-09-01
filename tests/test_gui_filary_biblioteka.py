"""Filary, playlisty, ulubione i filtry biblioteki w oknie.

Okno pisze do TEGO SAMEGO pliku stanu co terminal, więc filar przypięty
w oknie musi być widoczny w terminalu i odwrotnie. Testy pilnują:

1. że stan idzie na dysk od razu (okno bywa zamykane nagle) i jest to ten
   sam plik, z którego czyta terminal;
2. że budowa używa filarów zmienionych W OKNIE, nie tych sprzed zmian;
3. że filtry biblioteki mają te same reguły co terminal — okno tempa znaczy
   to, co mówi, więc utwór bez tempa przy aktywnym oknie odpada.
"""

import json

import pytest

from dancelab.gui.most import Most
from dancelab.tui import user_store


@pytest.fixture()
def most(tmp_path, monkeypatch):
    """Most ze stanem DJ-a w tmp_path — nie ruszamy prawdziwego pliku."""
    stan_plik = tmp_path / "stan.json"
    monkeypatch.setattr(user_store, "sciezka_stanu", lambda pula=None: stan_plik)
    monkeypatch.setattr(user_store, "STATE_PATH", stan_plik)
    m = Most(katalog=str(tmp_path / "analizy"))
    m._spis = [
        {"track_id": "t1", "tytul": "Alfa", "wykonawca": "A", "bpm": 126.0,
         "tonacja": "8A", "gatunek": "house", "sciezka": "/m/t1.aiff",
         "dlugosc_sec": 300.0},
        {"track_id": "t2", "tytul": "Beta", "wykonawca": "B", "bpm": 140.0,
         "tonacja": "9A", "gatunek": "techno", "sciezka": "/m/t2.aiff",
         "dlugosc_sec": 400.0},
        {"track_id": "t3", "tytul": "Gamma", "wykonawca": None, "bpm": None,
         "tonacja": None, "gatunek": None, "sciezka": "/m/t3.aiff",
         "dlugosc_sec": 200.0},
    ]
    return m, stan_plik


def test_filar_bez_playlisty_odmawia_z_powodem(most):
    m, _ = most
    odp = m.ustaw_filar("t1", "otwarcie")
    assert "blad" in odp
    assert "playlist" in odp["blad"]          # mówi CZEGO brakuje


def test_filar_z_rola_ladu_je_na_dysku_od_razu(most):
    m, plik = most
    m.nowa_playlista("Piątek")
    odp = m.ustaw_filar("t1", "otwarcie")
    assert "blad" not in odp
    assert odp["filary"] == [{"track_id": "t1", "rola": "otwarcie",
                              "tytul": "Alfa"}]

    # Okno bywa zamykane nagle — stan musi być na dysku PRZED zamknięciem,
    # i musi to być plik, z którego czyta terminal.
    zapisane = json.loads(plik.read_text())
    wpisy = zapisane["playlisty"][0]["filary"]
    assert wpisy == [{"track_id": "t1", "path": "/m/t1.aiff",
                      "rola": "otwarcie"}]
    assert user_store.filary_wpisy(user_store.load_state()) == wpisy


def test_role_wylacznosci_wypieraja_poprzednika(most):
    m, _ = most
    m.nowa_playlista("Piątek")
    m.ustaw_filar("t1", "otwarcie")
    odp = m.ustaw_filar("t2", "otwarcie")     # dwóch otwierających = sprzeczność
    role = {f["track_id"]: f["rola"] for f in odp["filary"]}
    assert role == {"t1": "", "t2": "otwarcie"}


def test_zdjecie_filaru_i_odmowa_dla_nieprzypietego(most):
    m, _ = most
    m.nowa_playlista("Piątek")
    m.ustaw_filar("t1", "")
    assert m.zdejmij_filar("t1")["filary"] == []
    assert "blad" in m.zdejmij_filar("t1")    # drugi raz nie ma czego zdejmować


def test_budowa_widzi_filary_zmienione_w_oknie(most, monkeypatch):
    """Gdyby budowa wczytywała stan z dysku osobno, użyłaby filarów sprzed
    zmian zrobionych w tym samym oknie."""
    m, _ = most
    m.nowa_playlista("Piątek")
    m.ustaw_filar("t1", "otwarcie")
    stan_w_budowie = m._stan_uzytkownika()
    assert user_store.filary_wpisy(stan_w_budowie)[0]["track_id"] == "t1"

    m.ustaw_filar("t2", "oddech")
    # ten sam obiekt, nie kopia sprzed zmiany
    assert {e["track_id"] for e in user_store.filary_wpisy(m._stan_uzytkownika())} \
        == {"t1", "t2"}


def test_tryb_filarow_zapisany_i_walidowany(most, monkeypatch):
    m, plik = most
    assert m.ustaw_tryb_filarow("podpory")["tryb_filarow"] == "podpory"
    assert json.loads(plik.read_text())["tryb_filarow"] == "podpory"
    assert "blad" in m.ustaw_tryb_filarow("kosmos")


def test_ulubione_przelaczaja_sie_i_widac_je_w_spisie(most):
    m, _ = most
    assert m.przelacz_ulubiony("t1")["ulubiony"] is True
    assert m.ulubione()["ulubione"] == ["t1"]
    assert m.przelacz_ulubiony("t1")["ulubiony"] is False
    assert m.ulubione()["ulubione"] == []


def test_filtry_biblioteki_maja_reguly_terminala(most):
    m, _ = most
    m.nowa_playlista("Piątek")
    m.ustaw_filar("t2", "")
    m.przelacz_ulubiony("t1")

    # okno tempa: utwór BEZ tempa odpada, bo okno ma znaczyć to, co mówi
    wynik = m.szukaj(bpm="120-130")
    assert [u["track_id"] for u in wynik["utwory"]] == ["t1"]
    assert wynik["znalezione"] == 1 and wynik["wszystkich"] == 3

    # tonacja dokładna, nie „zaczyna się na"
    assert [u["track_id"] for u in m.szukaj(tonacja="9a")["utwory"]] == ["t2"]

    # fraza szuka też po gatunku i wykonawcy
    assert [u["track_id"] for u in m.szukaj("techno")["utwory"]] == ["t2"]

    # znaczniki ♥ i ⚑ jadą razem z wierszem
    wszystko = {u["track_id"]: u for u in m.szukaj()["utwory"]}
    assert wszystko["t1"]["ulubiony"] and not wszystko["t1"]["filar"]
    assert wszystko["t2"]["filar"] and not wszystko["t2"]["ulubiony"]

    # tylko ulubione
    assert [u["track_id"] for u in
            m.szukaj(tylko_ulubione=True)["utwory"]] == ["t1"]


def test_zle_okno_tempa_wraca_jako_odmowa_nie_pustka(most):
    m, _ = most
    odp = m.szukaj(bpm="sto")
    assert "blad" in odp and odp["pole"] == "bpm"


def test_sortowanie_stawia_braki_na_koncu(most):
    m, _ = most
    kolejnosc = [u["track_id"] for u in m.szukaj(sortuj="bpm")["utwory"]]
    assert kolejnosc == ["t1", "t2", "t3"]     # t3 bez tempa — na końcu
    assert [u["track_id"] for u in m.szukaj(sortuj="tytul")["utwory"]] \
        == ["t1", "t2", "t3"]


def test_wczytanie_planu_dociaga_pule_zanim_dopasuje(most, monkeypatch, tmp_path):
    """Bez puli plan dopasowałby ZERO utworów i wyglądałoby to jak pusty plan.

    Most ma najpierw dociągnąć pulę, potem dopasowywać — i robić to w wątku,
    bo pula to ~20 sekund przy zimnym starcie.
    """
    import time
    from dancelab.stan import plan as plan_modul

    m, _ = most

    class _T:
        def __init__(self, tid):
            self.track_id, self.source_path = tid, f"/m/{tid}.aiff"
            self.title, self.artist = tid, None
            self.bpm_estimate, self.key_estimate = 128.0, "8A"
            self.key_detection_source, self.duration_sec = None, 300.0

    class _A:
        def __init__(self, tid):
            self.track = _T(tid)

    pula_wolana = []

    def fake_pula():
        pula_wolana.append(True)
        return [_A("t1"), _A("t2")]

    monkeypatch.setattr(m, "_pula", fake_pula)
    monkeypatch.setattr(plan_modul, "wczytaj", lambda by_id, sc: {
        "kolejnosc": [t for t in ("t1", "t2") if t in by_id],
        "notki": ["BRAK W PULI (pominięty): stary"], "plan": sc,
        "nazwa": "Piątek", "zapisanych": 3, "parametry": {"dj": "Ben UFO"}})
    monkeypatch.setattr(plan_modul, "WSKAZNIK", tmp_path / "biezacy.json")

    assert m.wczytaj_plan("/plany/p.json") == {"ruszylo": True}
    for _ in range(50):
        s = m.postep_planu()
        if s["stan"] != "trwa":
            break
        time.sleep(0.05)
    assert s["stan"] == "gotowe"
    assert pula_wolana, "pula nie została dociągnięta"
    assert [u["track_id"] for u in s["utwory"]] == ["t1", "t2"]
    assert s["notki"] == ["BRAK W PULI (pominięty): stary"]
    assert m._kolejnosc == ["t1", "t2"]
    # plan z pliku nie niesie wag budowy — panel kandydatów ma odmówić
    assert m._ctx_edycji is None
    assert "wag budowy" in m.kandydaci(0)["blad"]


def test_info_utworu_nazywa_zrodlo_kazdej_liczby(most, monkeypatch):
    """Karta INFO składa się TYM SAMYM formatterem co terminal, więc tempo
    z Rekordboxa stoi osobno — jest niezależnym sędzią naszego pomiaru."""
    m, _ = most

    class _T:
        track_id, source_path = "t1", "/m/t1.aiff"
        bpm_estimate, key_estimate, key_confidence = 127.0, "5A", 0.62
        key_detection_source, style_label = None, "house"
        duration_sec, sound_embedding = 277.0, None

    class _A:
        track = _T()

    m._analizy["t1"] = _A()
    monkeypatch.setattr("dancelab.ingestion.rekordbox_lookup.track_in_rekordbox",
                        lambda p: {"bpm": 127.0, "playlists": ["Piątek"]})
    tekst = m.info_utworu("t1")["tekst"]
    assert "SILNIK:" in tekst and "REKORDBOX:" in tekst
    assert "BPM wg Rekordboxa: 127.0" in tekst
    assert "wektor brzmienia: brak" in tekst


def test_info_mowi_czego_nie_wie_zamiast_milczec(most, monkeypatch):
    m, _ = most

    class _T:
        track_id, source_path = "t1", "/m/t1.aiff"
        bpm_estimate, key_estimate, key_confidence = 127.0, "5A", None
        key_detection_source, style_label = None, None
        duration_sec, sound_embedding = 277.0, None

    class _A:
        track = _T()

    m._analizy["t1"] = _A()

    def wybuch(_p):
        raise RuntimeError("baza zajęta")

    monkeypatch.setattr("dancelab.ingestion.rekordbox_lookup.track_in_rekordbox",
                        wybuch)
    tekst = m.info_utworu("t1")["tekst"]
    assert "master.db nieodczytany: baza zajęta" in tekst


def test_porownanie_ostatniej_pozycji_odmawia_z_powodem(most):
    m, _ = most
    m._kolejnosc = ["t1", "t2"]
    m._ctx_edycji = {"wagi": object()}
    assert "następnika" in m.porownaj_pare(1)["blad"]
    assert "poza setem" in m.porownaj_pare(9)["blad"]


def test_kolekcja_djow_zapisuje_sie_na_dysku(most, tmp_path):
    m, plik = most
    assert m.przelacz_kolekcje_dj("Ben UFO")["w_kolekcji"] is True
    assert json.loads(plik.read_text())["kolekcja_djow"] == ["Ben UFO"]
    assert m.przelacz_kolekcje_dj("Ben UFO")["w_kolekcji"] is False
    assert json.loads(plik.read_text())["kolekcja_djow"] == []


def test_brak_ksiegi_kotwic_to_stan_nie_awaria(most, monkeypatch):
    m, _ = most
    from dancelab.decision import anchors

    def brak(*a, **kw):
        raise anchors.AnchorError("brak pliku kotwic")

    monkeypatch.setattr(anchors, "load_anchor_book", brak)
    odp = m.djs()
    assert "blad" in odp and "kotwice niedostępne" in odp["blad"]
