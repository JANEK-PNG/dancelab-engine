"""Sterowanie brzmieniem (kotwica/kontur) i kotwice DJ-ów — granice uczciwości.

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
