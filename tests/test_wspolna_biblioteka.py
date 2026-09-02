"""Krok 3 scalania skór (02.09): filtr biblioteki jest JEDNĄ regułą.

Terminal filtruje analizy (`filtruj`), okno — słowniki nagłówków (`pasuje`).
Ten test karmi obie drogi tymi samymi utworami i żąda tej samej listy —
także w dwóch miejscach, w których kopie zdążyły się rozjechać.
"""

from dancelab.stan import biblioteka as B


class _T:
    def __init__(self, tid, sciezka, bpm, key, genre, artist=None, title=None):
        self.track_id, self.source_path = tid, sciezka
        self.bpm_estimate, self.key_estimate, self.style_label = bpm, key, genre
        self.artist, self.title = artist, title
        self.key_confidence, self.duration_sec, self.sound_embedding = 0.9, 300.0, None


class _A:
    def __init__(self, *a, **k):
        self.track = _T(*a, **k)
        self.features = []


LIB = [
    _A("a", "/m/Mercy System - Steppers.mp3", 132.0, "4A", "breaks"),
    _A("b", "/m/Detlef - Lil Bunny.mp3", 130.0, "2A", "Tech House",
       artist="Detlef", title="Lil Bunny"),
    _A("c", "/m/Hodge - Wiggler.mp3", 135.0, "1A", "UK Bass"),
    _A("d", "/m/Bez Tempa.mp3", None, None, None),
    _A("e", "/m/plik_bez_tagow_xyz.aiff", 131.0, "5A", "breaks",
       artist="Overmono", title="So U Kno"),
]


def _naglowek(a):
    """Dokładnie to, co `Most.biblioteka` wyciąga z nagłówka analizy."""
    t = a.track
    art, tit = B.wykonawca_tytul(t)
    return {"track_id": t.track_id, "sciezka": t.source_path, "wykonawca": art,
            "tytul": tit, "gatunek": t.style_label, "tonacja": t.key_estimate,
            "bpm": t.bpm_estimate}


def _okno(szukaj="", ton="", lo=None, hi=None):
    return [u["track_id"] for u in map(_naglowek, LIB)
            if B.pasuje(sciezka=u["sciezka"], wykonawca=u["wykonawca"],
                        tytul=u["tytul"], gatunek=u["gatunek"],
                        tonacja=u["tonacja"], bpm=u["bpm"], szukaj=szukaj,
                        tonacja_szukana=ton, bpm_lo=lo, bpm_hi=hi)]


def _terminal(szukaj="", ton="", lo=None, hi=None):
    return [a.track.track_id for a in B.filtruj(LIB, search=szukaj, key=ton,
                                                  bpm_lo=lo, bpm_hi=hi)]


def test_obie_skory_daja_te_sama_liste_na_te_sama_fraze():
    for zapytanie in ({"szukaj": "mercy"}, {"szukaj": "uk bass"},
                      {"ton": "2a"}, {"lo": 130, "hi": 132},
                      {"szukaj": "e", "lo": 129, "hi": 133, "ton": "2A"}):
        assert _okno(**zapytanie) == _terminal(**zapytanie), zapytanie


def test_rozjazd_1_nazwa_pliku_wchodzi_do_szukania_w_obu():
    """Okno szukało bez nazwy pliku: „xyz" znajdował tylko terminal."""
    assert _okno(szukaj="xyz") == _terminal(szukaj="xyz") == ["e"]


def test_rozjazd_2_brak_tempa_odpada_przy_kazdym_progu_w_obu():
    """Terminal zostawiał utwór bez tempa przy samym górnym progu."""
    assert "d" not in _okno(hi=140)
    assert "d" not in _terminal(hi=140)
    assert _okno(hi=140) == _terminal(hi=140)


# ------------------------------------------------ sekcje i sortowanie (3b)

def _pola(u):
    return dict(sciezka=u["sciezka"], wykonawca=u["wykonawca"], tytul=u["tytul"],
                bpm=u["bpm"], tonacja=u["tonacja"], dlugosc=u.get("dlugosc"),
                gatunek=u["gatunek"])


def test_braki_ida_na_koniec_niezaleznie_od_kierunku():
    """Reguła terminala: brak to brak, nie zero — ani na początku listy
    rosnącej, ani na początku malejącej."""
    wiersze = [_naglowek(a) for a in LIB]
    rosnaco = [u["track_id"] for u in B.sortuj(wiersze, "bpm", pola=_pola)]
    malejaco = [u["track_id"] for u in B.sortuj(wiersze, "bpm", malejaco=True, pola=_pola)]
    assert rosnaco == ["b", "e", "a", "c", "d"]
    assert malejaco == ["c", "a", "e", "b", "d"]        # „d" bez tempa ZAWSZE ostatni


def test_tonacja_sortuje_po_numerze_camelota_nie_alfabetycznie():
    wiersze = [_naglowek(a) for a in LIB]
    assert [u["tonacja"] for u in B.sortuj(wiersze, "tonacja", pola=_pola)] == \
        ["1A", "2A", "4A", "5A", None]


def test_terminal_sortuje_tym_samym_kluczem():
    """`_lib_sort_key` terminala dla kolumn wspólnych z oknem woła
    `stan.biblioteka.klucz_sortu` — jedna kolejność tonacji w obu skórach."""
    from dancelab.tui.app import _lib_sort_key, _lib_sort_missing
    klucz = _lib_sort_key(4, set(), set(), {}, {})          # 4 = tonacja
    posortowane = sorted([a for a in LIB if a.track.key_estimate], key=klucz)
    assert [a.track.key_estimate for a in posortowane] == ["1A", "2A", "4A", "5A"]
    assert _lib_sort_missing(3, LIB[3], {}, {}) is True     # „d" bez tempa
    assert _lib_sort_missing(3, LIB[0], {}, {}) is False


def test_sekcje_okna_filtruja_po_zrodle_i_znakach(monkeypatch, tmp_path):
    from dancelab.gui.most import Most
    from dancelab.tui import zrodlo as Z
    monkeypatch.setattr(Z, "zrodlo", lambda p: "apple" if str(p).startswith("apple") else "dysk")
    m = Most(katalog=str(tmp_path))
    m._spis = [{"track_id": "a", "tytul": "A", "sciezka": "/m/a.aiff", "bpm": 120.0},
               {"track_id": "s", "tytul": "S", "sciezka": "apple-music:tracks:1", "bpm": 121.0}]
    monkeypatch.setattr(m, "biblioteka", lambda limit=400: {"utwory": [], "wszystkich": 2})
    monkeypatch.setattr(m, "ulubione", lambda: {"ulubione": ["s"]})
    monkeypatch.setattr(m, "filary", lambda: {"filary": [{"track_id": "a"}]})
    ids = lambda odp: [u["track_id"] for u in odp["utwory"]]
    assert ids(m.szukaj(sekcja="dysk")) == ["a"]
    assert ids(m.szukaj(sekcja="apple")) == ["s"]
    assert ids(m.szukaj(sekcja="ulubione")) == ["s"]
    assert ids(m.szukaj(tylko_ulubione=True)) == ["s"]     # stara nazwa sekcji ♥
    assert ids(m.szukaj(sekcja="filary")) == ["a"]
    assert ids(m.szukaj(sortuj="-bpm")) == ["s", "a"]
    assert "nieznana sekcja" in m.szukaj(sekcja="xyz")["blad"]
