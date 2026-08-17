"""Premia za gatunek — miękkie trzymanie briefu, gdy twarde sito nie wchodzi.

Do 09.08 preferencja gatunków była wyłącznikiem: jeden pasujący utwór poniżej
długości setu i brief znikał BEZ RESZTY. Te testy pilnują trzech rzeczy:
premia przesuwa ocenę ku jedynce i nigdy ponad nią, nie robi ze słabego szwu
dobrego, a w budowie setu naprawdę zmienia wybór — ale tylko wtedy, gdy
twarde sito nie przeszło.
"""

from dancelab.core.models import AnalysisResult, Track
from dancelab.decision import premia_gatunku as P


def _analiza(tid: str, styl: str | None) -> AnalysisResult:
    return AnalysisResult(
        engine_version="test",
        track=Track(track_id=tid, source_path=f"/m/{tid}.wav",
                    style_label=styl, bpm_estimate=128.0, duration_sec=300.0))


def test_premia_jest_stalym_marginesem_na_calej_skali():
    premia = P.zbuduj(["House"])
    for ocena in (0.0, 0.2, 0.6, 0.89):
        po, _ = premia.dopasuj(ocena, _analiza("a", "House"))
        assert abs(po - (ocena + P.DOMYSLNA_WAGA)) < 1e-9, (
            f"{ocena} → {po}: premia ma być JEDNAKOWA na całej skali, "
            "inaczej przy dobrych szwach gatunek nie zmienia nic")
    # Sufitu NIE ma celowo: to klucz porządkujący wewnątrz wyboru
    # następnika, a nie ocena pokazywana DJ-owi. Przycinanie do 1,0
    # kasowało premię tam, gdzie biblioteka Janka żyje (średnia 0,96).
    po, _ = premia.dopasuj(1.0, _analiza("a", "House"))
    assert po > 1.0, "przy suficie premia przestałaby cokolwiek rozstrzygać"


def test_slaby_szew_nie_robi_sie_dobry_przez_gatunek():
    """Premia ma rozstrzygać remisy, nie przebijać muzyki."""
    premia = P.zbuduj(["House"])
    ryzykowny, _ = premia.dopasuj(0.59, _analiza("a", "House"))
    assert ryzykowny < 0.90, (
        f"ryzykowny szew z premią wyszedł {ryzykowny} — przebiłby dobry")
    # a przy zbliżonych ocenach gatunek ma wygrywać
    z_gatunkiem, _ = premia.dopasuj(0.89, _analiza("a", "House"))
    bez_gatunku, _ = premia.dopasuj(0.93, _analiza("b", "Drum & Bass"))
    assert z_gatunkiem > bez_gatunku, "różnica 0,04 ma się dać przestawić"


def test_utwor_bez_gatunku_nie_dostaje_nic():
    premia = P.zbuduj(["House"])
    po, powod = premia.dopasuj(0.5, _analiza("a", None))
    assert po == 0.5 and powod is None


def test_brak_preferencji_to_brak_premii():
    assert P.zbuduj(None) is None
    assert P.zbuduj([]) is None
    assert P.zbuduj(["   "]) is None


def test_podsumowanie_liczy_trafienia():
    premia = P.zbuduj(["House"])
    premia.dopasuj(0.5, _analiza("a", "House"))
    premia.dopasuj(0.5, _analiza("b", "Techno"))
    tekst = premia.podsumowanie()
    assert "1 z 2" in tekst and "house" in tekst.lower()


def _stol():
    """Stolik do testów wyboru: start + dwaj kandydaci o ZMIERZONYCH ocenach.

    „z_idealny" (8A→10A) dostaje 0,932, „a_gatunek" (8A→8A, ale 125 BPM)
    0,796 — różnica 0,135 leży w zasięgu premii 0,15. Nazwy dobrane tak, by
    ALFABET sprzyjał gorszemu kandydatowi: gdyby premia nie działała, remis
    rozstrzygnąłby się na jego korzyść i test nic by nie mierzył.

    PRZELICZONE 17.08, gdy „nie wiem" o tonacji przestało znaczyć 1,0.
    Utwory testowe nie podają pewności tonacji, więc dostają domyślne 0,5 —
    i to jest właściwe, bo taki jest teraz produkcyjny stan 96,7% biblioteki.
    Przy dawnej jedynce te same utwory dawały 0,957 i 0,883, różnica 0,074.
    Zmiana uderzyła MOCNIEJ w kandydata z tą samą tonacją (−0,108) niż
    w tego z odległą (−0,026) — czyli dokładnie tak, jak zamierzono: ta sama
    tonacja przestaje być kartą atutową. Tempo przesunięte 124 → 125, żeby
    różnica z powrotem zmieściła się w zasięgu premii i test mierzył PREMIĘ,
    a nie przypadek.
    """
    from dancelab.core.config import load_weights
    from dancelab.core.models import BeatGrid
    from dancelab.decision.mixability import precompute_mixability_inputs

    def utwor(tid, styl, ton, bpm):
        return AnalysisResult(
            engine_version="test",
            track=Track(track_id=tid, source_path=f"/m/{tid}.wav",
                        style_label=styl, bpm_estimate=bpm,
                        key_estimate=ton, duration_sec=300.0),
            beatgrid=BeatGrid(bpm=bpm, reliable=True))

    by_id = {
        "start": utwor("start", "Techno", "8A", 128.0),
        "z_idealny": utwor("z_idealny", "Techno", "10A", 128.0),
        "a_gatunek": utwor("a_gatunek", "House", "8A", 125.0),
    }
    return dict(
        by_id=by_id, weights=load_weights("configs/descriptor_weights.yaml"),
        arc="build", energy={tid: 0.5 for tid in by_id}, energy_range=1.0,
        planner_mode="smart", context=None,
        mixability_precomputation=precompute_mixability_inputs(
            list(by_id.values())))


def test_premia_zmienia_WYBOR_nastepnika():
    """Wpięcie w silnik, mierzone na samym wyborze: kandydat pożądanego
    gatunku jest odrobinę GORSZY, więc bez premii przegrywa — z premią
    wygrywa. To jest cała obietnica „trzymaj się gatunku, ile się da":
    premia rozstrzyga bliskie przypadki, nie przebija muzyki."""
    from dancelab.decision.set_builder import _best_successor

    wspolne = _stol()
    kandydaci = ["z_idealny", "a_gatunek"]

    assert _best_successor("start", kandydaci, **wspolne) == "z_idealny", \
        "bez premii wygrywa lepsza harmonia"
    assert _best_successor("start", kandydaci, premia=P.zbuduj(["House"]),
                           **wspolne) == "a_gatunek", \
        "premia ma rozstrzygnąć na rzecz gatunku"


def test_premia_nie_przebija_zlego_szwu():
    """Druga strona tej samej obietnicy: kandydat pożądanego gatunku, ale
    harmonicznie odległy, NIE ma wygrywać."""
    from dancelab.core.config import load_weights
    from dancelab.core.models import BeatGrid
    from dancelab.decision.mixability import precompute_mixability_inputs
    from dancelab.decision.set_builder import _best_successor

    def utwor(tid: str, styl: str, ton: str, bpm: float) -> AnalysisResult:
        return AnalysisResult(
            engine_version="test",
            track=Track(track_id=tid, source_path=f"/m/{tid}.wav",
                        style_label=styl, bpm_estimate=bpm,
                        key_estimate=ton, duration_sec=300.0),
            beatgrid=BeatGrid(bpm=bpm, reliable=True))

    by_id = {
        "start": utwor("start", "Techno", "8A", 128.0),
        "idealny": utwor("idealny", "Techno", "8A", 128.0),
        "gatunek": utwor("gatunek", "House", "3B", 100.0),   # obcy i wolny
    }
    energia = {tid: 0.5 for tid in by_id}
    wybor = _best_successor(
        "start", ["idealny", "gatunek"], by_id=by_id,
        weights=load_weights("configs/descriptor_weights.yaml"), arc="build",
        energy=energia, energy_range=1.0, planner_mode="smart", context=None,
        mixability_precomputation=precompute_mixability_inputs(list(by_id.values())),
        premia=P.zbuduj(["House"]))
    assert wybor == "idealny", "gatunek nie usprawiedliwia złego szwu"


def test_premia_nie_psuje_reguly_tripletow():
    """Pytanie Janka 09.08: „czy w tym wszystkim cały czas zachowujemy zasadę
    tripletów?". Tak — most do filaru liczy się PRZED premią i zostaje
    nietknięty, a premia skaluje się z liczbą krawędzi, żeby przy filarze
    znaczyła dokładnie tyle samo, co w zwykłym slocie."""
    from dancelab.decision.set_builder import _best_successor

    wspolne = _stol()
    by_id = wspolne["by_id"]
    from dancelab.core.models import BeatGrid
    # filar w tonacji 10A: wejście w niego jest łatwe z „z_idealny" (10A),
    # a trudniejsze z „a_gatunek" (8A) — most ma to widzieć
    by_id["filar"] = AnalysisResult(
        engine_version="test",
        track=Track(track_id="filar", source_path="/m/filar.wav",
                    style_label="Techno", key_estimate="10A",
                    bpm_estimate=128.0, duration_sec=300.0),
        beatgrid=BeatGrid(bpm=128.0, reliable=True))
    wspolne["energy"]["filar"] = 0.5
    from dancelab.decision.mixability import precompute_mixability_inputs
    wspolne["mixability_precomputation"] = precompute_mixability_inputs(
        list(by_id.values()))
    kandydaci = ["z_idealny", "a_gatunek"]

    # BEZ premii most rozstrzyga na rzecz utworu, który wchodzi w filar
    assert _best_successor("start", kandydaci, bridge_to="filar",
                           **wspolne) == "z_idealny"

    # Z premią gatunek nadal może przestawić wybór — ale most dalej działa:
    # premia jest tu podwojona, więc znaczy tyle samo co w zwykłym slocie.
    premia = P.zbuduj(["House"])
    _best_successor("start", kandydaci, bridge_to="filar", premia=premia,
                    **wspolne)
    assert premia.ocenione == 2 and premia.trafione == 1, \
        "premia ocenia kandydatów także przy filarze"
