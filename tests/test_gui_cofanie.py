"""Jeden stos cofania na całe okno — i uczciwa odpowiedź, gdy nie ma czego cofać.

Skarga wynikła ze schematu linii produkcyjnej (03.09): ⌘Z znało wyłącznie pady,
więc wycięta pozycja setu i utwór zdjęty z koszyka przepadały bez odwrotu. To
są jedyne edycje w oknie, które kosztują pracę — pad stawia się w sekundę,
a set buduje się minutami.

Testy pilnują pięciu rzeczy:

1. cofanie działa na WSZYSTKICH trzech rodzajach edycji (pad, set, koszyk);
2. kolejność jest odwrotna do robienia i NIE zależy od ekranu — stos jest
   jeden, więc ⌘Z na ekranie Set może cofnąć pada z ekranu Utwór;
3. nieudana edycja nie zostawia kroku na stosie — inaczej ⌘Z „cofałoby"
   coś, co się nigdy nie stało;
4. pusty stos mówi to zdaniem, zamiast milczeć albo udawać sukces;
5. stos ma sufit, żeby okno nie trzymało migawek bez końca.

Osobno: `stan_dzwieku` — sprawdzenie odtwarzaczy RAZ przy starcie, zamiast
odkrywania braku ffplay dopiero przy pierwszym kliknięciu na falę.
"""

import pytest

from dancelab.gui.most import Most
from dancelab.stan import dziennik, odtwarzacz as odt


class _Track:
    def __init__(self, tid: str) -> None:
        self.track_id = tid
        self.bpm_estimate = 128.0
        self.key_estimate = "8A"
        self.title = f"Utwór {tid}"
        self.artist = "Test"
        self.duration_sec = 300.0
        self.source_path = f"/muzyka/{tid}.aiff"
        self.sound_embedding = None
        self.genre = "Tech House"
        # `_wiersz` czyta źródło tonacji, żeby odróżnić pomiar od Rekordboxa —
        # bez tego pola atrapa wywraca każdą odpowiedź niosącą wiersze setu.
        self.key_detection_source = "pomiar"


class _Siatka:
    bpm = 128.0
    beats_sec = ()


class _Analiza:
    def __init__(self, tid: str) -> None:
        self.track = _Track(tid)
        self.beatgrid = _Siatka()
        self.features = []


@pytest.fixture()
def most(tmp_path, monkeypatch):
    monkeypatch.setattr(dziennik, "KATALOG", tmp_path / "werdykty")
    monkeypatch.setattr(dziennik, "PLIK_ZDARZEN", str(tmp_path / "dziennik.jsonl"))
    m = Most(katalog=str(tmp_path / "analizy"))
    m._analizy = {t: _Analiza(t) for t in ("t1", "t2", "t3", "t4")}
    m._kolejnosc = ["t1", "t2", "t3"]
    return m


# ----------------------------------------------------------------- pusty stos

def test_pusty_stos_mowi_ze_nie_ma_czego_cofac(most):
    odp = most.cofnij("")
    assert odp["cofnieto"] is False
    assert odp["powod"] == "nie ma czego cofać"


# ---------------------------------------------------------------------- set

def test_cofniecie_wraca_wycieta_pozycje_setu(most):
    most.wytnij(1)                              # wypada t2
    assert most._kolejnosc == ["t1", "t3"]

    odp = most.cofnij("")
    assert odp["cofnieto"] is True
    assert odp["rodzaj"] == "set"
    assert most._kolejnosc == ["t1", "t2", "t3"]
    assert [u["track_id"] for u in odp["utwory"]] == ["t1", "t2", "t3"]


def test_cofniecie_wraca_podmieniona_pozycje(most):
    most.podmien(0, "t4")
    assert most._kolejnosc == ["t4", "t2", "t3"]

    most.cofnij("")
    assert most._kolejnosc == ["t1", "t2", "t3"]


def test_cofniecie_wraca_dopisany_utwor(most):
    most.dopisz_utwor(0, "t4")
    assert most._kolejnosc == ["t1", "t4", "t2", "t3"]

    most.cofnij("")
    assert most._kolejnosc == ["t1", "t2", "t3"]


def test_cofniecie_wraca_przesuniecie(most):
    most.przesun_utwor(0, 1)
    assert most._kolejnosc == ["t2", "t1", "t3"]

    most.cofnij("")
    assert most._kolejnosc == ["t1", "t2", "t3"]


def test_seria_edycji_cofa_sie_po_kolei_wstecz(most):
    most.wytnij(2)                              # ["t1","t2"]
    most.wytnij(1)                              # ["t1"]
    most.podmien(0, "t4")                       # ["t4"]
    assert most._kolejnosc == ["t4"]

    most.cofnij("")
    assert most._kolejnosc == ["t1"]
    most.cofnij("")
    assert most._kolejnosc == ["t1", "t2"]
    most.cofnij("")
    assert most._kolejnosc == ["t1", "t2", "t3"]
    assert most.cofnij("")["cofnieto"] is False


def test_cofniecie_uniewaznia_policzony_zapis(most):
    """Liczby zapisu dotyczyły setu sprzed cofnięcia — nie wolno ich zostawić
    jako gotowych, bo przycisk wyglądałby na policzony dla innej kolejności."""
    most.wytnij(1)
    most._zapis_gotowy = {"udawany": True}
    most.cofnij("")
    assert most._zapis_gotowy is None


# ------------------------------------------------------------------- koszyk

def _playlista(most, nazwa="Piątek"):
    most.nowa_playlista(nazwa)


def test_cofniecie_zdejmuje_utwor_dodany_do_koszyka(most):
    _playlista(most)
    most.ustaw_filar("t1", "")
    assert [f["track_id"] for f in most.filary()["filary"]] == ["t1"]

    odp = most.cofnij("")
    assert odp["cofnieto"] is True
    assert odp["rodzaj"] == "filar"
    assert most.filary()["filary"] == []


def test_cofniecie_wraca_utwor_zdjety_z_koszyka(most):
    _playlista(most)
    most.ustaw_filar("t1", "")
    most.zdejmij_filar("t1")
    assert most.filary()["filary"] == []

    most.cofnij("")
    assert [f["track_id"] for f in most.filary()["filary"]] == ["t1"]


def test_nieudane_przypiecie_nie_zostawia_kroku_na_stosie(most):
    """Bez playlisty filar nie wchodzi. Krok na stosie kazałby ⌘Z cofnąć
    coś, co się nie stało — i zjadłby cofnięcie należne poprzedniej zmianie."""
    most.wytnij(1)
    przed = len(most._historia)
    odp = most.ustaw_filar("t1", "")
    assert "blad" in odp
    assert len(most._historia) == przed

    most.cofnij("")
    assert most._kolejnosc == ["t1", "t2", "t3"]


# --------------------------------------------------------------- jeden stos

def test_stos_jest_wspolny_i_cofa_ostatnia_zmiane_niezaleznie_od_rodzaju(most):
    """Sedno naprawy: pad, set i koszyk leżą na JEDNYM stosie. Cofa się to,
    co było ostatnie, a nie to, co pasuje do ekranu."""
    _playlista(most)
    most.postaw_pad("t1", "A", 60_000)
    most.wytnij(2)                              # ostatnia zmiana: set
    most.ustaw_filar("t1", "")                  # …a potem koszyk

    assert most.cofnij("")["rodzaj"] == "filar"
    assert most.cofnij("")["rodzaj"] == "set"
    assert most._kolejnosc == ["t1", "t2", "t3"]

    odp = most.cofnij("")
    assert odp["rodzaj"] == "pad"
    assert odp["cofnieto"] is True
    assert most.pady("t1")["pady"] == {}


def test_stos_ma_sufit(most):
    for _ in range(most.KROKI_COFANIA + 12):
        most.postaw_pad("t1", "A", 60_000)
    assert len(most._historia) == most.KROKI_COFANIA


# ------------------------------------------------------------ stan dźwięku

def test_stan_dzwieku_mowi_o_braku_ffplay(most, monkeypatch):
    monkeypatch.setattr(odt, "FFPLAY", None)
    monkeypatch.setattr(odt, "AFPLAY", "/fake/afplay")
    s = most.stan_dzwieku()
    assert s["pelny"] is False
    assert "ffplay" in s["powod"]
    assert "brew install ffmpeg" in s["powod"]


def test_stan_dzwieku_milczy_gdy_wszystko_jest(most, monkeypatch):
    monkeypatch.setattr(odt, "FFPLAY", "/fake/ffplay")
    monkeypatch.setattr(odt, "AFPLAY", "/fake/afplay")
    s = most.stan_dzwieku()
    assert s["pelny"] is True
    assert s["powod"] == ""


def test_stan_dzwieku_bez_zadnego_odtwarzacza_mowi_wprost(most, monkeypatch):
    monkeypatch.setattr(odt, "FFPLAY", None)
    monkeypatch.setattr(odt, "AFPLAY", None)
    s = most.stan_dzwieku()
    assert s["ffplay"] is False and s["afplay"] is False
    assert "dźwięku nie będzie" in s["powod"]
