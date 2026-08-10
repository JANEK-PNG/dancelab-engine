"""Sito brzmieniowe: kotwica decyduje, KTO wchodzi do puli kandydatów.

Zmierzone 09.08 i to jest powód powstania tego modułu: kotwica jako DODATEK
do oceny nie zmieniała setu. Przy 400–800 kandydatach na krok zwycięzcy mieli
rdzeń 1,000 i leżeli blisko WSZYSTKICH kotwic naraz, więc „graj jak Four Tet"
i „graj jak Jamie xx" dawały ten sam set — waga od 0,35 do 0,90 nie zmieniała
niczego, co dało się zmierzyć.

Wniosek: premia do oceny wybiera CZĘŚĆ WSPÓLNĄ DJ-ów. Żeby kotwica wybrała
to, co danego DJ-a WYRÓŻNIA, musi zadziałać wcześniej — zawęzić pulę, zanim
rdzeń zacznie układać kolejność. DJ decyduje, kto wchodzi do sali; silnik
decyduje, w jakiej kolejności grają.

Mechanizm jest ten sam co przy gatunku (`set_builder`): zawężamy pulę, a gdy
zostałoby mniej utworów niż długość setu — rozluźniamy CAŁKOWICIE i mówimy
o tym wprost, zamiast oddawać set zbudowany z resztek.

PRAWDZIWA PRZYCZYNA, znaleziona przy okazji i ważniejsza od samego sita:
utwór BEZ wektora nie dostawał od sterowania ŻADNEJ korekty, więc zostawał
przy swojej ocenie rdzenia (często 1,000), podczas gdy każdy kandydat, którego
DAŁO SIĘ ocenić, był ściągany w dół o (1 − bliskość)·waga. Utwory niemożliwe
do oceny systematycznie WYGRYWAŁY z ocenionymi — i im wyższa waga kotwicy,
tym mocniej. Stąd zmierzona nieczułość na wagę. Sprawdzone imiennie na
zwycięzcach, którzy wychodzili tak samo dla każdej kotwicy: Farsight 100%
utworów bez wektora, K-LONE 100%, HAAi 71%, Olof Dreijer 50%.

Dlatego przy włączonej kotwicy utwór bez wektora opuszcza pulę — ale to nie
jest wyrok „nie pasuje", tylko „nie wiemy". Liczba takich utworów idzie do
ostrzeżenia, żeby DJ wiedział, jaka część biblioteki nie brała udziału.

ZMIERZONE (09.08, pula 1857 z wektorami, sety po 10, trzy kotwice: Four Tet,
Ben UFO, Jamie xx) — udział puli po sicie / średnia liczba wspólnych utworów
między parami kotwic / średnia ocena szwu:

    100% → 1,0/10 · 0,9992      50% → 0,0/10 · 0,9867
     30% → 0,3/10 · 0,9974      20% → 0,3/10 · 0,9970
     10% → 0,3/10 · 0,9995       5% → 0,3/10 · 0,9742

Rozróżnialność wysyca się od razu — bierze się głównie z odsunięcia utworów
nieocenialnych, nie z ostrości sita. 20% zostawia ~320 kandydatów, więcej niż
potrzeba, i nie kosztuje jakości; 5% zaczyna kosztować.
"""

from __future__ import annotations

from typing import Sequence

# Ile puli zostaje po sicie. ZMIERZONE — tabela w PROJECT_LEDGER (wpis
# z 09.08): udział vs rozbieżność setów dwóch DJ-ów vs średnia ocena szwu.
DOMYSLNY_UDZIAL = 0.20


def srodek_puli(wektory: Sequence[Sequence[float]]) -> list[float] | None:
    """Średni wektor puli — to, co wspólne wszystkim; odejmowane od obu stron."""
    dobre = [w for w in wektory if w]
    if len(dobre) < 20:
        return None
    import numpy as np

    return list(np.asarray(dobre, dtype=float).mean(axis=0))


def bliskosci(by_id: dict, kotwica: Sequence[float],
              srodek: Sequence[float] | None) -> dict[str, float]:
    """{track_id: bliskość do kotwicy} — tylko dla utworów z wektorem."""
    import numpy as np

    k = np.asarray(kotwica, dtype=float)
    s = np.asarray(srodek, dtype=float) if srodek is not None else None
    if s is not None:
        k = k - s
    nk = float(np.linalg.norm(k))
    if nk <= 0:
        return {}
    out: dict[str, float] = {}
    for tid, analiza in by_id.items():
        wek = getattr(analiza.track, "sound_embedding", None)
        if not wek:
            continue
        v = np.asarray(wek, dtype=float)
        if s is not None:
            v = v - s
        nv = float(np.linalg.norm(v))
        if nv <= 0:
            continue
        out[tid] = float(np.dot(v, k) / (nv * nk))
    return out


def przesiej(by_id: dict, kotwica: Sequence[float] | None,
             *, wymagane: set[str], ile_utworow: int,
             udzial: float = DOMYSLNY_UDZIAL,
             srodek: Sequence[float] | None = None,
             ) -> tuple[dict, list[str]]:
    """(pula po sicie, ostrzeżenia). Bez kotwicy zwraca pulę bez zmian."""
    if kotwica is None or not by_id:
        return by_id, []

    bliskosc = bliskosci(by_id, kotwica, srodek)
    bez_wektora = len(by_id) - len(bliskosc)
    if not bliskosc:
        return by_id, ["sito brzmieniowe pominięte — żaden utwór puli nie ma "
                       "wektora brzmienia"]

    ile = max(int(round(len(bliskosc) * max(min(udzial, 1.0), 0.0))), 1)
    najblizsi = sorted(bliskosc, key=lambda t: -bliskosc[t])[:ile]
    zostaje = set(najblizsi) | (wymagane & set(by_id))

    if len(zostaje) < ile_utworow:
        return by_id, [
            f"sito brzmieniowe ROZLUŹNIONE — po zawężeniu zostałoby "
            f"{len(zostaje)} utworów przy secie na {ile_utworow}"]

    nowa = {tid: a for tid, a in by_id.items() if tid in zostaje}
    ostrzezenia = [
        f"sito brzmieniowe: pula {len(by_id)} → {len(nowa)} utworów "
        f"najbliższych kotwice ({udzial:.0%} puli)"]
    if bez_wektora:
        ostrzezenia.append(
            f"{bez_wektora} utworów bez wektora brzmienia nie brało udziału "
            f"w sicie — o nich nie wiemy, czy pasują")
    return nowa, ostrzezenia
