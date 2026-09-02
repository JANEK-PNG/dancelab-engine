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
