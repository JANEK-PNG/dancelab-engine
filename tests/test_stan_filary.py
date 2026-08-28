"""Filary — utwory, które MUSZĄ zagrać, i miejsce, w którym mają zagrać.

Powód istnienia tych testów jest zmierzony: przy samym „musi zagrać" sześć
filarów lądowało na pozycjach 13–18 z 18, czyli wszystkie w finale. Metafora
Janka mówi, że filar ma PODPIERAĆ konstrukcję — a to znaczy, że pozycje muszą
być wyznaczane z góry i te testy tego pilnują.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from dancelab.stan import filary as F
from dancelab.stan.budowa import OdmowaBudowy


@dataclass
class Slad:
    track_id: str
    source_path: str
    bpm_estimate: float | None = 128.0


@dataclass
class Klatka:
    rms: float


@dataclass
class Analiza:
    track: Slad
    features: list = field(default_factory=list)


def pula(*trojki) -> dict:
    """(id, tempo, rms albo None) → mapa analiz."""
    out = {}
    for tid, bpm, rms in trojki:
        klatki = [Klatka(rms)] if rms is not None else []
        out[tid] = Analiza(track=Slad(tid, f"/m/{tid}.aiff", bpm), features=klatki)
    return out


def stan_z_filarami(by_id, ids, role=None) -> dict:
    role = role or {}
    return {"aktywna_playlista": 0, "playlisty": [{
        "nazwa": "t", "kotwica": None, "utwory": [],
        "filary": [{"track_id": t, "path": by_id[t].track.source_path,
                    "rola": role.get(t, "")} for t in ids]}]}


# ------------------------------------------------------------- rozstaw

def test_filary_rozstawione_po_calym_secie():
    """Sedno metafory: trzy filary w secie na 12 nie mogą wylądować na końcu."""
    by_id = pula(("a", 124.0, .3), ("b", 128.0, .5), ("c", 132.0, .7))
    pozycje = F.rozstaw(["a", "b", "c"], by_id, 12, "rozstaw")
    miejsca = sorted(pozycje)
    assert len(miejsca) == 3
    assert miejsca[0] <= 4, f"pierwszy filar za późno: {miejsca}"
    assert miejsca[-1] >= 8, f"ostatni filar za wcześnie: {miejsca}"
    # rosnąco po tempie — zgodnie ze schodkami tempa
    assert [pozycje[m] for m in miejsca] == ["a", "b", "c"]


def test_tryb_rama_trzyma_krance():
    by_id = pula(("a", 124.0, .3), ("b", 128.0, .5), ("c", 132.0, .7))
    pozycje = F.rozstaw(["a", "b", "c"], by_id, 10, "rama")
    assert pozycje[1] == "a"
    assert pozycje[10] == "c"


def test_zaden_filar_nie_gubi_sie_przy_ciasnym_secie():
    by_id = pula(("a", 124.0, .3), ("b", 128.0, .5), ("c", 132.0, .7))
    pozycje = F.rozstaw(["a", "b", "c"], by_id, 3, "rozstaw")
    assert sorted(pozycje.values()) == ["a", "b", "c"]
    assert len(set(pozycje)) == 3, "dwa filary w tym samym miejscu"


# ------------------------------------------------------------- role

def test_role_krancowe_nadpisuja_rozstawienie():
    """Deklaracja DJ-a jest mocniejsza niż sortowanie po tempie."""
    pozycje = {2: "a", 5: "b", 8: "c"}
    nowe, notki = F.role_krancowe(pozycje, {"c": "otwarcie"}, 10)
    assert nowe[1] == "c"
    assert "c" not in [t for p, t in nowe.items() if p != 1]
    assert any("otwarcie" in n for n in notki)


def test_role_srodkowe_sa_nazwane_a_nie_udawane():
    """Oddech i buildup nie celują jeszcze miejscem — i mówimy to wprost."""
    _, notki = F.role_krancowe({2: "a"}, {"a": "oddech"}, 10)
    assert any("następny krok" in n for n in notki)


# ------------------------------------------------------------- wybór

def test_filar_poza_oknem_tempa_pomijany_z_nazwiskiem():
    """Okno tempa ustawił użytkownik — konflikt ma być widoczny, nie
    rozstrzygany po cichu.

    Czterech filarów, nie trzech: po odsianiu jednego muszą zostać co najmniej
    MIN_FILARY, inaczej sprawdzalibyśmy odmowę zamiast pomijania."""
    by_id = pula(("wolny", 100.0, .3), ("ok1", 126.0, .5),
                 ("ok2", 128.0, .5), ("ok3", 131.0, .5))
    stan = stan_z_filarami(by_id, ["wolny", "ok1", "ok2", "ok3"])
    ids, notki, _ = F.wybierz(stan, by_id, 120.0, 135.0, 10)
    assert ids == ["ok1", "ok2", "ok3"]
    assert any("poza oknem tempa" in n and "wolny" in n for n in notki)


def test_zbyt_malo_filarow_po_sitach_to_odmowa():
    """Reguła projektu: MIN_FILARY. Set z jednym wymuszonym utworem nie jest
    „setem na filarach" i lepiej powiedzieć to wprost."""
    from dancelab.tui.user_store import MIN_FILARY
    by_id = pula(("wolny", 100.0, .3), ("ok1", 126.0, .5), ("ok2", 128.0, .5))
    stan = stan_z_filarami(by_id, ["wolny", "ok1", "ok2"])
    with pytest.raises(OdmowaBudowy, match=f"minimum {MIN_FILARY}"):
        F.wybierz(stan, by_id, 120.0, 135.0, 10)


def test_wiecej_filarow_niz_miejsc_to_odmowa_z_liczbami():
    by_id = pula(("a", 126.0, .3), ("b", 127.0, .3), ("c", 128.0, .3))
    stan = stan_z_filarami(by_id, ["a", "b", "c"])
    with pytest.raises(OdmowaBudowy, match="więcej niż miejsc"):
        F.wybierz(stan, by_id, None, None, 2)


def test_odmowa_niesie_winowajcow():
    """Liczby bez nazwisk nie mówią, czy poszerzyć okno, czy wymienić filary."""
    by_id = pula(("z1", 100.0, .3), ("z2", 101.0, .3), ("ok", 126.0, .3))
    stan = stan_z_filarami(by_id, ["z1", "z2", "ok"])
    with pytest.raises(OdmowaBudowy) as exc:
        F.wybierz(stan, by_id, 120.0, 135.0, 10)
    tekst = str(exc.value)
    assert "z1" in tekst and "poza oknem" in tekst
    assert "120–135" in tekst, "odmowa musi podać okno, które wyciął użytkownik"


# ------------------------------------------------------------- podpory

def test_podpora_wchodzi_w_najslabsze_przeslo():
    """To jedyny tryb patrzący na zmierzoną jakość przejść, nie na arytmetykę."""
    konstrukcja = ["a", "b", "c", "d"]

    def ocena(x, y):                      # przęsło b→c jest najsłabsze
        return {("a", "b"): .9, ("b", "c"): .1, ("c", "d"): .8}.get((x, y), .5)

    wynik, notki = F.wstaw_podpory(konstrukcja, ["filar"], ocena)
    assert wynik.index("filar") == 2, f"podpora nie w najsłabszym miejscu: {wynik}"
    assert any("#2→#3" in n for n in notki)


def test_za_malo_przesel_to_odmowa_nie_cisza():
    with pytest.raises(OdmowaBudowy, match="za mało przęseł"):
        F.wstaw_podpory(["a", "b"], ["f1", "f2", "f3"], lambda x, y: .5)


# ------------------------------------------------------------- energia

def test_energia_surowa_odroznia_brak_od_ciszy():
    """Do WYŚWIETLANIA brak klatek to None, nie 0,5 — inaczej pokazywalibyśmy
    zmyśloną liczbę jako pomiar."""
    by_id = pula(("z", 128.0, .8), ("bez", 128.0, None))
    assert F.energia_surowa(by_id["z"]) == pytest.approx(.8)
    assert F.energia_surowa(by_id["bez"]) is None
    # do OCENY brak zastępujemy 0,5 — i to jest inna funkcja
    energia, _ = F.energia_do_oceny(by_id)
    assert energia["bez"] == 0.5
