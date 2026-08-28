"""Filary — utwory, które MUSZĄ zagrać, i miejsce, w którym mają zagrać.

Metafora jest Janka (05.08) i nie jest ozdobnikiem: filar ma **podpierać
konstrukcję**, nie leżeć na końcu. Zmierzone wtedy: przy samym „musi zagrać"
sześć filarów lądowało na pozycjach 13–18 z 18, czyli wszystkie w finale.
Dlatego pozycje wyznacza się Z GÓRY, a silnik projektuje przęsła między nimi.

Przeniesione z `tui/app.py` **bez zmiany zachowania** — to jest ten sam kod,
który terminal ma sprawdzony w boju. Zmieniona jest jedna rzecz: odmowy lecą
jako `OdmowaBudowy` z `stan.budowa`, żeby okno i terminal łapały ten sam typ.

Trzy tryby, bo to trzy różne pytania:

* ``rozstaw`` — równomiernie po całym secie;
* ``rama`` — pierwszy filar otwiera, ostatni zamyka, reszta równomiernie;
* ``podpory`` — najpierw konstrukcja BEZ filarów, potem pomiar każdego przęsła
  i filar wchodzi tam, gdzie jest najsłabiej. To jedyny tryb, który patrzy na
  zmierzoną jakość przejść, a nie na arytmetykę pozycji.
"""

from __future__ import annotations

import pathlib
from typing import Any, Callable

from dancelab.stan.budowa import OdmowaBudowy

Ocena = Callable[[str, str], float]


def energia_surowa(a: Any) -> float | None:
    """Średni RMS z klatek — do WYŚWIETLANIA: brak klatek to None, nie 0,5."""
    wartosci = [f.rms for f in (getattr(a, "features", None) or [])
                if getattr(f, "rms", None) is not None]
    return float(sum(wartosci) / len(wartosci)) if wartosci else None


def energia_do_oceny(by_id: dict) -> tuple[dict[str, float], float]:
    """Mapa energii pod ocenę przejścia (0,5 przy braku klatek — do OCENY,
    nie do pokazania) oraz rozpiętość."""
    energia = {tid: (energia_surowa(a) if energia_surowa(a) is not None else 0.5)
               for tid, a in by_id.items()}
    rozpietosc = (max(energia.values()) - min(energia.values())) or 1.0
    return energia, rozpietosc


def wybierz(stan_uzytkownika: dict, by_id: dict, bpm_min: float | None,
            bpm_max: float | None, ile_miejsc: int | None
            ) -> tuple[list[str], list[str], dict[str, str]]:
    """Filary aktywnej playlisty → lista id, notki i role.

    Każdy konflikt ma jawny los: filar spoza puli i filar poza oknem tempa są
    POMIJANE z imienną notką — okno tempa ustawił użytkownik, więc konflikt ma
    być widoczny, a nie rozstrzygany po cichu. Więcej filarów niż miejsc to
    odmowa z liczbami.
    """
    from dancelab.tui.user_store import MIN_FILARY, filary_wpisy, resolve_tracks

    wpisy = filary_wpisy(stan_uzytkownika)
    ids, brakujace = resolve_tracks(wpisy, by_id)
    po_sciezce = {a.track.source_path: tid for tid, a in by_id.items()}

    role: dict[str, str] = {}
    for e in wpisy:
        tid = e.get("track_id")
        if tid not in by_id:
            tid = po_sciezce.get(e.get("path", ""))
        if tid and e.get("rola"):
            role[tid] = e["rola"]

    notki = [f"FILAR nieobecny w puli (pominięty): {m}" for m in brakujace]
    wyciete = [f"{m} (spoza puli)" for m in brakujace]

    zostawione: list[str] = []
    for tid in ids:
        bpm = by_id[tid].track.bpm_estimate or 0.0
        if (bpm_min is not None and bpm < bpm_min) or \
                (bpm_max is not None and bpm > bpm_max):
            nazwa = pathlib.Path(by_id[tid].track.source_path).stem[:40]
            notki.append(f"FILAR poza oknem tempa (pominięty): {nazwa} ({bpm:.1f})")
            wyciete.append(f"{nazwa} ({bpm:.0f} — poza oknem)")
            continue
        zostawione.append(tid)

    if zostawione and len(zostawione) < MIN_FILARY:
        # Odmowa musi nieść winowajców: liczby bez nazwisk nie mówią, czy
        # poszerzyć okno, czy wymienić filary (skarga Janka 09.08).
        #
        # Ale gdy NIC nie wypadło, winowajcy nie ma. Złapane 28.08 na
        # prawdziwych danych: przy jednym zaznaczonym filarze komunikat kazał
        # poszerzać okno tempa, które nie miało z tym nic wspólnego — a set
        # nie budował się w ogóle.
        if not wyciete:
            raise OdmowaBudowy(
                f"masz zaznaczony {len(zostawione)} filar, a minimum to "
                f"{MIN_FILARY} — zaznacz kolejne albo zdejmij ten jeden "
                f"(bez filarów set zbuduje się normalnie)")
        kogo = "; ".join(wyciete[:3])
        if len(wyciete) > 3:
            kogo += f" i {len(wyciete) - 3} dalszych"
        okno = (f"{bpm_min:g}–{bpm_max:g}"
                if bpm_min is not None and bpm_max is not None else "ustawione")
        raise OdmowaBudowy(
            f"filary to minimum {MIN_FILARY}, a po sitach zostało "
            f"{len(zostawione)} — wypadły: {kogo}. Poszerz okno tempa ({okno}) "
            f"albo wymień filary")

    if ile_miejsc is not None and len(zostawione) > ile_miejsc:
        raise OdmowaBudowy(
            f"filarów ({len(zostawione)}) więcej niż miejsc w secie "
            f"({ile_miejsc}) — wydłuż set albo zdejmij filary")

    if zostawione:
        notki.append(f"filary w budowie: {len(zostawione)} (każdy MUSI zagrać)")
    role = {tid: r for tid, r in role.items() if tid in set(zostawione)}
    if role:
        notki.append("role filarów: "
                     + ", ".join(sorted(set(role.values()))))
    return zostawione, notki, role


def rozstaw(filary: list[str], by_id: dict, ile_miejsc: int,
            tryb: str = "rozstaw") -> dict[int, str]:
    """Filary → pozycje w secie.

    Kolejność wzdłuż setu: rosnąco po tempie, zgodnie ze schodkami tempa i
    łukiem, którymi Janek gra. Ograniczenie v1 nazwane wprost: przy łuku
    ``peak`` przydział powinien kiedyś patrzeć w krzywą tempa, nie tylko rosnąć.
    """
    posortowane = sorted(filary,
                         key=lambda t: by_id[t].track.bpm_estimate or 0.0)
    k = len(posortowane)
    pozycje: dict[int, str] = {}
    if not k:
        return pozycje

    if tryb == "rama" and k >= 2 and ile_miejsc >= k:
        pozycje[1] = posortowane[0]
        pozycje[ile_miejsc] = posortowane[-1]
        srodek = posortowane[1:-1]
        m = len(srodek)
        poprz = 1
        for i, tid in enumerate(srodek):
            poz = int((i + 0.5) * (ile_miejsc - 2) / m + 0.5) + 1
            poz = min(max(poz, poprz + 1), ile_miejsc - 1 - (m - 1 - i))
            pozycje[poz] = tid
            poprz = poz
        return pozycje

    poprz = 0
    for i, tid in enumerate(posortowane):
        poz = int((i + 0.5) * ile_miejsc / k + 0.5)
        poz = min(max(poz, poprz + 1), ile_miejsc - (k - 1 - i))
        pozycje[poz] = tid
        poprz = poz
    return pozycje


def role_krancowe(pozycje: dict[int, str], role: dict[str, str],
                  ile_miejsc: int) -> tuple[dict[int, str], list[str]]:
    """Role OTWARCIE i ZAMKNIĘCIE wymuszają krańce setu.

    Nadpisują rozstawienie: deklaracja DJ-a jest mocniejsza niż sortowanie po
    tempie. Role ODDECH i BUILDUP na razie NIE celują miejscem — silnik
    gwarantuje obecność i most do filara, a celowanie rolą w środku setu to
    następny krok. Mówimy to wprost, zamiast udawać (ADR-005).
    """
    nowe = dict(pozycje)
    notki: list[str] = []
    for rola, gdzie in (("otwarcie", 1), ("zamkniecie", ile_miejsc)):
        tid = next((t for t, r in role.items() if r == rola), None)
        if tid is None:
            continue
        nowe = {p: t for p, t in nowe.items() if t != tid and p != gdzie}
        nowe[gdzie] = tid
        notki.append(f"rola {rola}: pozycja #{gdzie} "
                     f"(deklaracja DJ-a nadpisuje rozstawienie trybu)")
    if any(r in ("oddech", "buildup") for r in role.values()):
        notki.append("role oddech/buildup: zapisane — silnik gwarantuje "
                     "obecność i most; celowanie miejscem to następny krok")
    return nowe, notki


def wstaw_podpory(konstrukcja: list[str], filary: list[str],
                  ocena: Ocena) -> tuple[list[str], list[str]]:
    """Tryb PODPORY: filar wchodzi tam, gdzie konstrukcja jest najsłabsza.

    Najpierw set BEZ filarów, potem pomiar każdego przęsła tą samą oceną
    przejścia, którą stoi budowa, i dla każdego z k najsłabszych przęseł
    wybieramy filar, który je najlepiej mostkuje (średnia wejścia i wyjścia).

    Wymaga przęseł ≥ filarów. Wołający przy braku spada na równy rozstaw
    Z NOTKĄ, nigdy po cichu.
    """
    if len(konstrukcja) - 1 < len(filary):
        raise OdmowaBudowy("za mało przęseł na tryb Podpory")

    przesla = sorted((ocena(konstrukcja[i], konstrukcja[i + 1]), i)
                     for i in range(len(konstrukcja) - 1))
    wolne = list(filary)
    wstawki: dict[int, str] = {}
    notki: list[str] = []
    for slabosc, i in przesla[:len(filary)]:
        najlepszy = max(wolne, key=lambda p: (ocena(konstrukcja[i], p)
                                              + ocena(p, konstrukcja[i + 1])) / 2)
        wolne.remove(najlepszy)
        wstawki[i] = najlepszy
        notki.append(f"podpora w przęśle #{i + 1}→#{i + 2} (było {slabosc:.2f})")

    wynik: list[str] = []
    for i, tid in enumerate(konstrukcja):
        wynik.append(tid)
        if i in wstawki:
            wynik.append(wstawki[i])
    return wynik, notki
