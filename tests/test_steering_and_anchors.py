"""Sterowanie brzmieniem (kotwica/kontur) i kotwice DJ-ów — granice uczciwości.
import pytest


Zasady pilnowane tu testami:
  * ścieżka DOMYŚLNA nie zmienia się ani o bit, gdy sterowania nie ma;
  * kandydat bez wektora dostaje rdzeń bez zmian (nigdy karę za brak danych);
  * nieznana nazwa DJ-a to odmowa z podpowiedzią, nie zgadywanie;
  * dokarmianie uzupełnia braki i nie nadpisuje zmierzonych wartości.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from dancelab.decision.anchors import AnchorError, list_anchors, resolve_anchor
from dancelab.decision.steering import SoundSteering
from dancelab.ingestion.analysis_enrichment import (
    attach_rekordbox_genres,
    attach_sound_embeddings,
)


def _track_stub(embedding=None):
    class T:
        sound_embedding = embedding
    class A:
        track = T()
    return A()


# ---------------------------------------------------------------- steering

def test_nieaktywne_sterowanie_nie_dotyka_oceny():
    st = SoundSteering()
    score, why = st.adjust(0.42, _track_stub([1, 0]), _track_stub([0, 1]), 3)
    assert score == 0.42 and why == []


def test_brak_wektora_kandydata_to_rdzen_bez_zmian_nie_kara():
    st = SoundSteering(anchor=np.array([1.0, 0.0]))
    score, why = st.adjust(0.6, _track_stub([1, 0]), _track_stub(None), 1)
    assert score == 0.6
    assert any("bez wektora" in w for w in why)
    assert any("bez wektora" in w for w in st.coverage_warnings())


def test_kotwica_podnosi_blizszego_kandydata():
    st = SoundSteering(anchor=np.array([1.0, 0.0]), anchor_weight=0.5)
    prev = _track_stub([1.0, 0.0])
    close, _ = st.adjust(0.5, prev, _track_stub([0.99, 0.1]), 1)
    far, _ = st.adjust(0.5, prev, _track_stub([-0.9, 0.4]), 1)
    assert close > far, "kandydat bliższy kotwicy ma wygrywać przy równym rdzeniu"


def test_kontur_celuje_w_zadany_skok_nie_w_najblizszy():
    """Kontur z celem DALEKIM ma preferować kandydata odległego — to jest cała
    różnica między „graj jak Four Tet" a „graj gładko" (pomiar 03.08)."""
    st = SoundSteering(contour=[-0.2], contour_weight=1.0)  # cel: daleki skok
    prev = _track_stub([1.0, 0.0])
    smooth, _ = st.adjust(0.5, prev, _track_stub([0.98, 0.2]), 1)
    jumpy, _ = st.adjust(0.5, prev, _track_stub([-0.35, 0.94]), 1)
    assert jumpy > smooth


def test_kontur_zawija_sie_cyklicznie():
    st = SoundSteering(contour=[0.1, 0.9])
    assert st.contour_target(1) == 0.1
    assert st.contour_target(2) == 0.9
    assert st.contour_target(3) == 0.1


# ---------------------------------------------------------------- anchors

@pytest.fixture()
def anchor_book(tmp_path):
    book = {
        "schema_version": "dj-anchors-v1",
        "source": "test",
        "djs": {
            "Ben UFO": {"n_tracks": 64, "n_mixes": 3, "centroid": [1.0, 0.0],
                        "contour": [0.6, 0.4], "cos_median": 0.637,
                        "cos_q25": 0.5, "cos_q75": 0.75},
            "Adam Beyer": {"n_tracks": 55, "n_mixes": 2, "centroid": [0.0, 1.0],
                           "contour": [0.8], "cos_median": 0.804,
                           "cos_q25": 0.78, "cos_q75": 0.85},
        },
    }
    p = tmp_path / "dj_anchors.json"
    p.write_text(json.dumps(book))
    return p


def test_rozstrzyga_nazwe_bez_wzgledu_na_wielkosc_liter(anchor_book):
    a = resolve_anchor("ben ufo", path=anchor_book)
    assert a.name == "Ben UFO" and a.n_tracks == 64 and a.contour == [0.6, 0.4]


def test_nieznana_nazwa_to_odmowa_z_podpowiedzia(anchor_book):
    with pytest.raises(AnchorError) as err:
        resolve_anchor("Ben", path=anchor_book)
    assert "Ben UFO" in str(err.value), "odmowa ma podpowiadać, nie zgadywać"


def test_brak_pliku_kotwic_mowi_jak_go_zbudowac(tmp_path):
    with pytest.raises(AnchorError) as err:
        resolve_anchor("ktokolwiek", path=tmp_path / "nie_ma.json")
    assert "build_dj_anchors" in str(err.value)


def test_lista_kotwic_sortowana_po_probce(anchor_book):
    rows = list_anchors(path=anchor_book)
    assert rows[0][0] == "Ben UFO" and rows[0][1] == 64


# ---------------------------------------------------------------- enrichment

def _analysis(path, embedding=None, style=None):
    class T:
        source_path = path
        sound_embedding = embedding
        style_label = style
    class A:
        track = T()
    return A()


def test_dokarmianie_wektorow_uzupelnia_braki_nie_nadpisuje():
    zmierzone = [9.0, 9.0]
    analyses = [_analysis("/m/a.mp3"), _analysis("/m/b.mp3", embedding=zmierzone),
                _analysis("/m/c.mp3")]
    report = attach_sound_embeddings(
        analyses, catalogue={"/m/a.mp3": [1.0, 0.0]})
    assert report.attached == 1 and report.missing == 1
    assert analyses[0].track.sound_embedding == [1.0, 0.0]
    assert analyses[1].track.sound_embedding is zmierzone, "istniejący wektor nietykalny"
    assert analyses[2].track.sound_embedding is None, "brak zostaje brakiem, nie zerem"


def test_gatunek_rekordboxa_wygrywa_z_tagiem_pliku():
    """Pomiar 03.08: tagi plików/iTunes wrzucają wszystko do „Dance";
    taksonomia Janka w Rekordboksie rozróżnia garage/breaks/bass. Ręczny tag
    człowieka > automatyczny tag pliku."""
    a = _analysis("/m/x.mp3", style="Dance")
    report = attach_rekordbox_genres([a], genre_map={"/m/x.mp3": "UK Garage / Bassline"})
    assert report.attached == 1
    assert a.track.style_label == "UK Garage / Bassline"


def test_brak_rekordboxa_nie_wywala_tylko_raportuje():
    a = _analysis("/m/x.mp3", style="Breaks")
    report = attach_rekordbox_genres([a], genre_map={})
    assert report.attached == 0 and report.missing == 1
    assert a.track.style_label == "Breaks"


# ---------------------------------------------------------------- tonacje RB

def _key_track(cam=None, conf=None, source=None, path="/m/x.mp3"):
    from dancelab.core.models import Track
    class A:
        track = Track(track_id="t1", source_path=path, key_estimate=cam,
                      key_confidence=conf, key_detection_source=source)
    return A()


def test_tonacja_rekordboxa_zastepuje_slaby_detektor():
    """Decyzja Janka 05.08 (pomiar: detektor 47% vs sędzia RB): apka gra
    tonacją z Rekordboxa; źródło jawne, pewność wg konwencji zaufanego źródła."""
    from dancelab.ingestion.analysis_enrichment import attach_rekordbox_keys
    a = _key_track(cam="3B", conf=0.12, source="detector")
    report = attach_rekordbox_keys([a], key_map={"/m/x.mp3": "8A"})
    t = a.track
    # Pewność zostaje NIEZMIERZONA: nigdy nie sprawdziliśmy, jak często
    # Rekordbox ma rację. Zapisujemy PROWENIENCJĘ (skąd tonacja), a nie
    # deklarację pewności — 1.0 było umową, nie pomiarem (zmiana 17.08).
    assert (t.key_estimate, t.key_confidence) == ("8A", None)
    assert t.key_detection_source == "rekordbox"
    assert (t.camelot_number, t.camelot_mode) == (8, "A")
    assert report.attached == 1


def test_reczna_tonacja_dja_nie_jest_nadpisywana():
    from dancelab.ingestion.analysis_enrichment import attach_rekordbox_keys
    a = _key_track(cam="5A", conf=1.0, source="manual")
    attach_rekordbox_keys([a], key_map={"/m/x.mp3": "8A"})
    assert a.track.key_estimate == "5A"
    assert a.track.key_detection_source == "manual"


def test_brak_tonacji_w_rb_zostawia_detektor_z_jego_pewnoscia():
    from dancelab.ingestion.analysis_enrichment import attach_rekordbox_keys
    a = _key_track(cam="3B", conf=0.12, source="detector")
    report = attach_rekordbox_keys([a], key_map={})
    assert a.track.key_estimate == "3B" and a.track.key_confidence == 0.12
    assert report.missing == 1
    assert any("zostaje detektor" in n for n in report.notes)


def test_wysrodkowanie_odsiewa_to_co_wspolne_wszystkim():
    """Kotwice DJ-ów leżą blisko siebie (zmierzone 09.08: mediana kosinusa
    0,886 na 363 parach), bo wektor każdego zawiera to samo „to jest muzyka
    taneczna". Odjęcie środka przestrzeni zostawia to, co danego DJ-a
    WYRÓŻNIA — i dopiero wtedy dwie kotwice wskazują różne utwory."""
    import numpy as np

    from dancelab.core.models import AnalysisResult, Track
    from dancelab.decision.steering import SoundSteering

    wspolne = np.array([1.0, 1.0, 0.0, 0.0])      # to, co mają wszyscy
    dj_a = wspolne + np.array([0.0, 0.0, 0.3, 0.0])
    dj_b = wspolne + np.array([0.0, 0.0, 0.0, 0.3])
    utwor_a = wspolne + np.array([0.0, 0.0, 0.4, 0.0])
    utwor_b = wspolne + np.array([0.0, 0.0, 0.0, 0.4])
    srodek = np.mean([dj_a, dj_b, utwor_a, utwor_b], axis=0)

    def kandydat(wektor):
        return AnalysisResult(engine_version="t", track=Track(
            track_id="k", source_path="/m/k.wav",
            sound_embedding=list(wektor)))

    def ocena(kotwica, wektor, srodkuj):
        st = SoundSteering(anchor=kotwica, anchor_weight=0.5,
                           srodek=srodek if srodkuj else None)
        return st.adjust(1.0, kandydat(wspolne), kandydat(wektor), 1)[0]

    # BEZ środka obie kotwice wolą ten sam utwór prawie tak samo
    bez = [ocena(dj_a, utwor_a, False), ocena(dj_a, utwor_b, False)]
    assert abs(bez[0] - bez[1]) < 0.02, \
        "bez wyśrodkowania kotwica ledwie odróżnia utwory"

    # PO wyśrodkowaniu kotwica A wyraźnie woli utwór A, a B utwór B
    assert ocena(dj_a, utwor_a, True) > ocena(dj_a, utwor_b, True) + 0.1
    assert ocena(dj_b, utwor_b, True) > ocena(dj_b, utwor_a, True) + 0.1


def test_kotwica_z_wlasnych_utworow_gdy_DJ_A_NIE_MA_W_KSIEDZE():
    """Test person 09.08: księga ma 285 DJ-ów zmierzonych z ich setów, a Kuba
    gra jak Amelie Lens, której tam nie ma — i nie da się jej dopisać bez jej
    setlist. Własne utwory rozwiązują to bez zgadywania."""
    from dancelab.core.models import AnalysisResult, Track
    from dancelab.decision.anchors import (MOJE_ULUBIONE, kotwica_z_utworow)

    def utwor(i: int, wektor):
        return AnalysisResult(engine_version="t", track=Track(
            track_id=f"t{i}", source_path=f"/m/{i}.wav",
            sound_embedding=list(wektor)))

    ulubione = [utwor(0, [1.0, 0.0]), utwor(1, [0.8, 0.2]), utwor(2, [0.9, 0.1])]
    kotwica = kotwica_z_utworow(ulubione)
    assert kotwica.name == MOJE_ULUBIONE
    assert kotwica.n_tracks == 3
    assert kotwica.centroid == pytest.approx([0.9, 0.1], abs=1e-9), \
        "kotwica to ŚREDNIA wskazanych utworów"
    assert kotwica.contour == [], \
        "kontur skoków to cecha SPOSOBU GRANIA — ze zbioru utworów go nie ma"
    assert kotwica.source == "wlasne utwory"


def test_za_malo_utworow_na_wlasna_kotwice_to_ODMOWA_z_powodem():
    from dancelab.core.models import AnalysisResult, Track
    from dancelab.decision.anchors import AnchorError, kotwica_z_utworow

    dwa = [AnalysisResult(engine_version="t", track=Track(
        track_id=f"t{i}", source_path=f"/m/{i}.wav",
        sound_embedding=[1.0, 0.0])) for i in range(2)]
    with pytest.raises(AnchorError, match="co najmniej 3"):
        kotwica_z_utworow(dwa)
