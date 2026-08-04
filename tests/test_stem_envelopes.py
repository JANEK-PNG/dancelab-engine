"""Krzywe stemów na żądanie — cache, uczciwość przy braku danych, sens liczby.

Decyzja Janka 2026-08-03: stemy tylko na żądanie, analiza zostaje szybka.
Te testy pilnują, że „na żądanie" znaczy „raz na utwór", a brak rozdzielacza
kończy się odmową, nie zmyśloną krzywą.
"""

from __future__ import annotations

import numpy as np
import soundfile as sf

from dancelab.stems.envelopes import STEMS, stem_envelopes

SR = 8000


def _fake_separate(calls: list):
    """Rozdzielacz-atrapa: perkusja głośnieje, bas cichnie. Bez Demucsa."""
    def sep(path):
        calls.append(path)
        n = SR * 30
        t = np.linspace(0, 1, n, dtype=np.float32)
        return {
            "drums": (0.2 + 0.8 * t).astype(np.float32),
            "bass": (1.0 - 0.9 * t).astype(np.float32),
            "other": np.full(n, 0.5, dtype=np.float32),
            "vocals": np.full(n, 0.1, dtype=np.float32),
        }
    return sep


def _wav(tmp_path):
    p = tmp_path / "t.wav"
    sf.write(p, np.zeros(SR * 30, dtype=np.float32), SR)
    return p


def test_liczy_i_zapamietuje_raz(tmp_path):
    calls: list = []
    p, root = _wav(tmp_path), tmp_path / "cache"
    e1, why1 = stem_envelopes(p, cache_root=root, separate=_fake_separate(calls), sr=SR)
    assert why1 == "policzone" and e1 is not None
    e2, why2 = stem_envelopes(p, cache_root=root, separate=_fake_separate(calls), sr=SR)
    assert why2 == "cache", "drugi raz ma iść z dysku, nie liczyć od nowa"
    assert len(calls) == 1, "rozdzielacz wołany więcej niż raz"
    assert set(e2.stems) == set(STEMS)
    assert len(e2.curves["drums"]) == 30, "jedna wartość na sekundę"


def test_krzywa_pokazuje_kierunek(tmp_path):
    """Perkusja narasta, bas opada — udział na końcu musi to oddać."""
    e, _ = stem_envelopes(_wav(tmp_path), cache_root=tmp_path / "c",
                          separate=_fake_separate([]), sr=SR)
    poczatek = e.share_delta(0.0, 5.0)
    koniec = e.share_delta(25.0, 30.0)
    assert koniec["drums"] > poczatek["drums"]
    assert koniec["bass"] < poczatek["bass"]


def test_bez_rozdzielacza_odmawia_zamiast_zmyslac(tmp_path):
    """ADR-005: brak Demucsa to None i powód, nigdy krzywa z pełnego miksu
    udająca perkusję."""
    def boom(_):
        raise RuntimeError("nie ma demucsa")
    e, why = stem_envelopes(_wav(tmp_path), cache_root=tmp_path / "c",
                            separate=boom, sr=SR)
    assert e is None
    assert "nie powiodło" in why or "brak" in why


def test_brak_pliku_to_odmowa(tmp_path):
    e, why = stem_envelopes(tmp_path / "nie_ma.wav", cache_root=tmp_path / "c",
                            separate=_fake_separate([]), sr=SR)
    assert e is None and why == "brak pliku"


def test_okno_poza_utworem_to_none(tmp_path):
    e, _ = stem_envelopes(_wav(tmp_path), cache_root=tmp_path / "c",
                          separate=_fake_separate([]), sr=SR)
    assert e.share_delta(100.0, 120.0) is None, "poza materiałem = nie wiem"
