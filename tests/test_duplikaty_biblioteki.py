"""Ten sam utwór w kilku kopiach — widok scala, dane zostają."""

from dancelab.core.models import AnalysisResult, BeatGrid, FeatureFrame, Track
from dancelab.tui.duplikaty import ile_kopii, klucz, scal


def _a(tid, sciezka, tytul, artysta="Bodhi", cechy=False):
    f = FeatureFrame(track_id=tid, timestamp_sec=0.0, rms=0.4)
    if cechy:
        f = FeatureFrame(track_id=tid, timestamp_sec=0.0, rms=0.4,
                         spectral_flux=12.0, onset_density=2.0,
                         bass_energy=900.0)
    return AnalysisResult(
        engine_version="test",
        track=Track(track_id=tid, source_path=sciezka, title=tytul,
                    artist=artysta, bpm_estimate=136.0, duration_sec=300.0),
        beatgrid=BeatGrid(bpm=136.0, reliable=True), features=[f])


def test_ten_sam_utwor_w_pieciu_folderach_to_jedna_pozycja(tmp_path):
    plik = tmp_path / "433.wav"
    plik.write_bytes(b"RIFF")
    lista = [
        _a("t1", "apple-music:tracks:1851449003", "433Mhz (Original Mix)"),
        _a("t2", str(plik), "433Mhz", cechy=True),
        _a("t3", "/nie/ma/LEKCJA nr5/433Mhz.wav", "433Mhz (Original Mix)"),
    ]
    widok, scalone = scal(lista)
    assert len(widok) == 1 and scalone == 2
    # przedstawicielem jest plik NA DYSKU z policzonymi cechami — tylko
    # takiego da się odsłuchać i tylko on wie o utworze więcej niż tempo
    assert widok[0].track.track_id == "t2"


def test_rozne_utwory_nie_sa_scalane():
    lista = [_a("a", "apple-music:tracks:1", "Peak"),
             _a("b", "apple-music:tracks:2", "Hydration")]
    widok, scalone = scal(lista)
    assert len(widok) == 2 and scalone == 0


def test_liczba_kopii_jest_raportowana(tmp_path):
    plik = tmp_path / "x.wav"
    plik.write_bytes(b"RIFF")
    lista = [_a("t1", str(plik), "Rave Cycle", cechy=True),
             _a("t2", "apple-music:tracks:9", "Rave Cycle"),
             _a("t3", "/nie/ma/Rave Cycle.wav", "Rave Cycle")]
    assert ile_kopii(lista)["t1"] == 3


def test_nawiasy_wersji_nie_robia_z_jednego_utworu_dwoch():
    assert klucz(_a("x", "/a.wav", "433Mhz (Original Mix)").track) == \
           klucz(_a("y", "/b.wav", "433Mhz").track)


# --- tożsamość Apple (11.09): bliźniak plik ↔ strumień o innym zapisie tytułu ---

def _an(tid, path, title, artist=None, cid=None):
    from dancelab.core.models import AnalysisResult, Track
    return AnalysisResult(engine_version="test", track=Track(
        track_id=tid, title=title, artist=artist, source_path=path, apple_catalog_id=cid))


def test_plik_i_strumien_o_tym_samym_id_apple_to_jedna_pozycja():
    from dancelab.tui import duplikaty as D
    plik = _an("f", "/nie/ma/a.aiff", "Sex Life (feat. Riko Dan)", "Riko Dan, Tracey", cid="42")
    strumien = _an("s", "apple-music:tracks:42", "Sex Life", "Tracey")
    assert D.klucz(plik.track) != D.klucz(strumien.track), "tytuł sam by ich nie scalił"
    widok, scalono = D.scal([plik, strumien])
    assert scalono == 1 and len(widok) == 1


def test_kopia_bez_isrc_zostaje_w_grupie_przez_tytul():
    from dancelab.tui import duplikaty as D
    z_isrc = _an("f1", "/nie/ma/a.aiff", "Life In A Mind", "Ross From Friends", cid="7")
    wav = _an("f2", "/nie/ma/a.wav", "Life In A Mind", "Ross From Friends")
    strumien = _an("s", "apple-music:tracks:7", "Life in a Mind", "Ross from Friends, X")
    widok, scalono = D.scal([z_isrc, wav, strumien])
    assert (len(widok), scalono) == (1, 2)
    assert D.ile_kopii([z_isrc, wav, strumien]) == {widok[0].track.track_id: 3}


def test_rozne_id_apple_i_rozne_tytuly_nie_sa_scalane():
    from dancelab.tui import duplikaty as D
    a = _an("s1", "apple-music:tracks:1", "Alpha", "X")
    b = _an("s2", "apple-music:tracks:2", "Beta", "Y")
    assert D.scal([a, b]) == ([a, b], 0)


def test_id_apple_ze_sciezki_strumienia_i_z_mostu():
    from dancelab.tui import duplikaty as D
    assert D.apple_id(_an("s", "apple-music:tracks:99", "t").track) == "99"
    assert D.apple_id(_an("f", "/x.aiff", "t", cid="5").track) == "5"
    assert D.apple_id(_an("f", "/x.aiff", "t").track) is None
