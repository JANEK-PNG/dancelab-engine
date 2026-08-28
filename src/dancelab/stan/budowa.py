"""Budowa setu — orkiestracja wspólna dla terminala i okna.

Logika układania setu mieszka w silniku (`decision.set_builder.build_set`).
To, co siedziało dotąd wyłącznie w `tui/app.py`, to **orkiestracja**: skąd wziąć
pulę, jak ją oczyścić, czym wzbogacić, jak rozwiązać kotwicę i co zrobić z
wynikiem. Okno potrzebuje dokładnie tego samego, więc leży to tutaj.

Jedyna różnica wobec `app.py`: postęp jest raportowany **wywołaniem zwrotnym**,
a nie dotykaniem widgetu. Dzięki temu terminal może wpisywać go w swój pasek,
okno w swój, a moduł nie wie o żadnym z nich.

Filary (utwory wymuszone w secie) mieszkają w `stan.filary` i wchodzą tu przez
parametr ``stan_uzytkownika``. Bez niego budowa działa jak wcześniej — bez
wymuszonych utworów — i mówi to wprost polem ``filary_pominiete``.

Tryb Folder (analiza nowych plików) też tu nie wchodzi: to długa operacja z
anulowaniem, a okno startuje z gotowej puli analiz.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any, Callable

#: Nazwy plików, które są stemami, nie utworami. Kopia z `tui/app.py` — ta sama
#: lista, bo to ta sama higiena; gdyby kiedyś się rozjechały, to jest błąd.
STEM_NAMES = {"drums", "bass", "other", "vocals", "no_vocals", "accompaniment"}
MAX_TRACK_SEC = 15 * 60
HISTORIA_SETOW = pathlib.Path("data/cache/tui_historia_setow.jsonl")
PROCESSED_DOMYSLNY = "experiments_priv/2026-07-30_rebuild/processed"

Postep = Callable[[str], None]


class OdmowaBudowy(ValueError):
    """Powód, dla którego setu nie da się zbudować — do pokazania, nie do zjedzenia."""


@dataclass
class Parametry:
    """To, co użytkownik ustawia w formularzu. Walidacja przy tworzeniu."""

    minuty: float = 90.0
    bpm_min: float | None = None
    bpm_max: float | None = None
    style: list[str] = field(default_factory=list)
    dj: str | None = None
    kontur: bool = False
    luk: str = "bez łuku (zmierzone)"
    tempo: str = "staircase"
    planer: str = "smart"
    nowosc: str = "deterministic"
    ziarno: int | None = None
    zrodlo_puli: str = "library"        # library | library-dysk | library-apple
    tryb_filarow: str = "rozstaw"       # rozstaw | rama | podpory

    @classmethod
    def z_formularza(cls, dane: dict[str, Any]) -> Parametry:
        """Zbuduj parametry z surowych pól, odmawiając Z POWODEM.

        Odmowa z powodem zamiast cichego domyślnego zachowania to zasada z TUI:
        „okno tempa to 'lo-hi', dostałem 'sto'" jest użyteczne, a podstawienie
        pełnego zakresu w tle — nie.
        """
        lo, hi, blad = rozbierz_tempo(str(dane.get("tempo_okno") or ""))
        if blad:
            raise OdmowaBudowy(blad)

        surowe_ziarno = str(dane.get("ziarno") or "").strip()
        if surowe_ziarno and not surowe_ziarno.lstrip("-").isdigit():
            raise OdmowaBudowy(
                f"ziarno to liczba całkowita, dostałem {surowe_ziarno!r}")
        ziarno = int(surowe_ziarno) if surowe_ziarno else None

        nowosc = str(dane.get("nowosc") or "deterministic") or "deterministic"
        if nowosc != "deterministic" and ziarno is None:
            import random
            # ziarno pokazujemy w wyniku — bez niego przebiegu nie da się powtórzyć
            ziarno = random.randint(1, 999_999)

        try:
            minuty = float(dane.get("minuty") or 90)
        except (TypeError, ValueError):
            raise OdmowaBudowy(
                f"długość w minutach to liczba, dostałem {dane.get('minuty')!r}"
            ) from None
        if minuty <= 0:
            raise OdmowaBudowy(f"długość musi być dodatnia, dostałem {minuty:g}")

        return cls(
            minuty=minuty, bpm_min=lo, bpm_max=hi,
            style=[s.strip() for s in str(dane.get("style") or "").split(",")
                   if s.strip()],
            dj=(dane.get("dj") or None) or None,
            kontur=bool(dane.get("kontur")),
            luk=str(dane.get("luk") or "bez łuku (zmierzone)"),
            tempo=str(dane.get("tempo") or "staircase"),
            planer=str(dane.get("planer") or "smart"),
            nowosc=nowosc, ziarno=ziarno,
            zrodlo_puli=str(dane.get("zrodlo_puli") or "library"),
            tryb_filarow=str(dane.get("tryb_filarow") or "rozstaw"),
        )


def rozbierz_tempo(tekst: str) -> tuple[float | None, float | None, str | None]:
    """'128-140' → (128.0, 140.0). Puste = brak okna. Błąd = komunikat.

    Przeniesione z `tui/app.py::_parse_bpm` bez zmiany zachowania.
    """
    t = tekst.replace(" ", "")
    if not t:
        return None, None, None
    if "-" not in t:
        return None, None, f"okno tempa to 'lo-hi', dostałem {tekst!r}"
    lo_s, hi_s = t.split("-", 1)
    try:
        lo, hi = float(lo_s), float(hi_s)
    except ValueError:
        return None, None, f"okno tempa to liczby, dostałem {tekst!r}"
    if lo >= hi:
        return None, None, f"puste okno: {lo:g} >= {hi:g}"
    return lo, hi, None


def pula(processed_dir: str = PROCESSED_DOMYSLNY) -> tuple[list, list[str]]:
    """Analizy z cache po higienie. Zwraca (analizy, notki o odrzuconych).

    Przeniesione z `tui/app.py::_library_analyses`. Kryterium „brak pliku"
    dotyczy WYŁĄCZNIE ścieżek wyglądających jak ścieżki: utwór ze źródła bez
    pliku (strumień Apple Music) jest normalny i przechodzi.
    """
    from dancelab.storage.repositories import FileAnalysisRepository

    repo = FileAnalysisRepository(processed_dir)
    analizy = [repo.get(t) for t in repo.list_track_ids()]
    przed = len(analizy)
    odrzucone = {"stem": 0, "dlugosc": 0, "brak_pliku": 0}

    def zdrowy(a) -> bool:
        if (a.track.duration_sec or 0) > MAX_TRACK_SEC:
            odrzucone["dlugosc"] += 1
            return False
        sciezka = str(a.track.source_path or "")
        if not sciezka.startswith("/"):
            return True
        p = pathlib.Path(sciezka)
        if not p.exists():
            odrzucone["brak_pliku"] += 1
            return False
        if p.stem.strip().lower() in STEM_NAMES:
            odrzucone["stem"] += 1
            return False
        return True

    analizy = [a for a in analizy if zdrowy(a)]
    notki: list[str] = []
    if przed - len(analizy):
        powody = ", ".join(f"{n}: {i}" for n, i in (
            ("stemy", odrzucone["stem"]),
            ("dłuższe niż 15 min", odrzucone["dlugosc"]),
            ("brak pliku na dysku", odrzucone["brak_pliku"])) if i)
        notki.append(f"higiena puli: odrzucone {przed - len(analizy)} ({powody})")
    return analizy, notki


def _zawez_zrodlo(analizy: list, zrodlo_puli: str) -> tuple[list, list[str]]:
    """Utwory z Apple Music Rekordbox pokazuje, ale nie ładuje na deck.

    Set z nich wygląda dobrze i nie da się go zagrać — dlatego wybór źródła
    jest jawny, a odrzucenie zawsze z liczbą.
    """
    if zrodlo_puli not in ("library-dysk", "library-apple"):
        return analizy, []
    from dancelab.tui import zrodlo as Z

    chce = Z.DYSK if zrodlo_puli == "library-dysk" else Z.APPLE
    przed = len(analizy)
    wybrane = [a for a in analizy if Z.zrodlo(a.track.source_path) == chce]
    return wybrane, [f"pula {Z.NAZWA[chce].lower()}: {len(wybrane)} z {przed} utworów"]


def _kotwica(nazwa: str | None) -> tuple[Any, list[str]]:
    """Rozwiąż „brzmi jak…". Niepowodzenie jest notką, nie wyjątkiem —
    set bez kotwicy jest prawomocny."""
    if not nazwa:
        return None, []
    from dancelab.decision.anchors import AnchorError, resolve_anchor

    try:
        return resolve_anchor(nazwa), []
    except AnchorError as exc:
        return None, [f"kotwica {nazwa!r} niedostępna: {exc}"]


def zbuduj(par: Parametry, *, processed_dir: str = PROCESSED_DOMYSLNY,
           postep: Postep | None = None, analizy: list | None = None,
           stan_uzytkownika: dict | None = None) -> dict[str, Any]:
    """Zbuduj set. Zwraca plan, pulę po id i notki — wszystko, co widok pokaże.

    ``postep`` dostaje krótkie komunikaty o etapie; ``None`` znaczy, że nikt
    nie słucha. ``analizy`` pozwala podać gotową pulę (test albo okno, które
    już ją ma) zamiast czytać z dysku po raz drugi.
    """
    from dancelab.core.config import load_config, load_weights
    from dancelab.decision.set_builder import build_set
    from dancelab.ingestion.analysis_enrichment import (
        attach_rekordbox_genres, attach_rekordbox_keys, attach_rekordbox_meta,
        attach_sound_embeddings)
    from dancelab.workflows.smart_playlist import estimate_track_count_for_duration

    mow = postep or (lambda _s: None)
    notki: list[str] = []

    if analizy is None:
        mow("Wczytuję analizy z biblioteki…")
        analizy, notki_puli = pula(processed_dir)
        notki += notki_puli

    analizy, notki_zrodla = _zawez_zrodlo(analizy, par.zrodlo_puli)
    notki += notki_zrodla
    if not analizy:
        raise OdmowaBudowy("pusta pula — nie ma z czego budować")

    mow("Dokarmianie (wektory, gatunki, tonacje)…")
    attach_sound_embeddings(analizy)
    attach_rekordbox_genres(analizy)
    attach_rekordbox_keys(analizy)
    attach_rekordbox_meta(analizy)

    kotwica, notki_kotwicy = _kotwica(par.dj)
    notki += notki_kotwicy

    ile = estimate_track_count_for_duration(analizy, par.minuty)
    cfg = load_config("configs/default.yaml")
    wagi = load_weights(cfg.weights_file)
    by_id = {a.track.track_id: a for a in analizy}

    # --- filary: utwory, które MUSZĄ zagrać -----------------------------
    filary_ids: list[str] = []
    role: dict[str, str] = {}
    tryb = par.tryb_filarow
    filary_zgloszone = 0
    if stan_uzytkownika:
        from dancelab.decision.dedup import canonical_ids
        from dancelab.stan import filary as F

        from dancelab.tui.user_store import filary_wpisy
        filary_zgloszone = len(filary_wpisy(stan_uzytkownika))
        filary_ids, notki_filarow, role = F.wybierz(
            stan_uzytkownika, by_id, par.bpm_min, par.bpm_max, ile)
        notki += notki_filarow
        # filar może wskazywać duplikat bajt-w-bajt, który dedup wytnie —
        # mapujemy na egzemplarz kanoniczny, żeby budowa nie odmawiała o utwór,
        # który muzycznie w puli JEST (złapane E2E 05.08)
        mapa = canonical_ids(analizy)
        filary_ids = list(dict.fromkeys(mapa.get(t, t) for t in filary_ids))
        role = {mapa.get(t, t): r for t, r in role.items()}
        if filary_ids and tryb == "podpory" and (ile - len(filary_ids)) - 1 < len(filary_ids):
            notki.append("za krótki set na tryb Podpory — spadam na równy rozstaw")
            tryb = "rozstaw"

    from dancelab.decision.history import HistoryStore

    historia = HistoryStore(HISTORIA_SETOW).recent(limit=20)
    wspolne = dict(
        novelty_mode=par.nowosc, seed=par.ziarno, history=historia,
        arc=par.luk, planner_mode=par.planer, tempo_shape=par.tempo,
        preferred_styles=par.style or None,
        bpm_min=par.bpm_min, bpm_max=par.bpm_max,
        sound_anchor=kotwica.centroid if kotwica else None,
        anchor_name=kotwica.name if kotwica else None,
        jump_contour=(kotwica.contour if (kotwica and par.kontur) else None),
    )

    if filary_ids and tryb == "podpory":
        plan, notki_podpor = _zbuduj_z_podporami(
            analizy, by_id, wagi, filary_ids, role, ile, par, wspolne, mow)
        notki += notki_podpor
    else:
        rozstawienie = {}
        if filary_ids:
            from dancelab.stan import filary as F
            rozstawienie = F.rozstaw(filary_ids, by_id, ile, tryb)
            rozstawienie, notki_rol = F.role_krancowe(rozstawienie, role, ile)
            notki += notki_rol
            if rozstawienie:
                notki.append(f"filary rozstawione ({tryb}): pozycje "
                             + ", ".join(f"#{p}" for p in sorted(rozstawienie)))
        mow(f"Buduję set: {ile} utworów z {len(analizy)}…")
        # `locked_positions` to 1-indeksowane miejsca w gotowej playliście —
        # nazwa silnika, nie moja. `pinned_track_ids` gwarantuje SAMĄ obecność;
        # rozstawienie mówi dodatkowo GDZIE, i to ono realizuje metaforę filara.
        plan = build_set(
            analizy, wagi, target_track_count=ile,
            locked_positions=rozstawienie or None,
            pinned_track_ids=filary_ids or None, **wspolne)

    notki += list(getattr(plan, "warnings", None) or [])
    if par.ziarno is not None and par.nowosc != "deterministic":
        notki.append(f"ziarno {par.ziarno} — zapisz je, żeby powtórzyć ten set")

    return {
        "plan": plan,
        "kolejnosc": list(plan.track_order),
        "by_id": by_id,
        # Wagi wracają, bo tymi samymi liczy się potem propozycje padów.
        # Policzone drugi raz z konfiguracji mogłyby się rozjechać z setem.
        "wagi": wagi,
        "notki": notki,
        "kotwica": kotwica.name if kotwica else None,
        "filary": filary_ids,
        "tryb_filarow": tryb if filary_ids else None,
        # Trzy różne stany, nie dwa. „Nie zaznaczyłeś filarów" i „zaznaczyłeś,
        # ale wszystkie wypadły z okna tempa" wymagają od użytkownika czegoś
        # zupełnie innego, więc nie mogą dzielić jednej flagi.
        "filary_zgloszone": filary_zgloszone,
        "filary_stan": ("uzyte" if filary_ids
                        else "wypadly" if filary_zgloszone
                        else "brak"),
    }


def _zbuduj_z_podporami(analizy, by_id, wagi, filary_ids, role, ile, par,
                        wspolne, mow) -> tuple[Any, list[str]]:
    """Tryb PODPORY: konstrukcja bez filarów, pomiar przęseł, filar w najsłabsze.

    Metafora dosłownie: plan tempa i łuk kształtują KONSTRUKCJĘ, a podpory
    wchodzą dopiero po pomiarze. Role krańcowe wyjmujemy z podpór, bo otwarcie
    i zamknięcie to deklaracje miejsc, a podpory szukają najsłabszych przęseł
    W ŚRODKU.
    """
    from dancelab.decision.set_builder import build_set
    from dancelab.decision.slot_suggest import _default_score_fn
    from dancelab.stan import filary as F

    notki: list[str] = []
    otwarcie = next((t for t, r in role.items() if r == "otwarcie"), None)
    zamkniecie = next((t for t, r in role.items() if r == "zamkniecie"), None)

    rdzen = [a for a in analizy if a.track.track_id not in set(filary_ids)]
    mow(f"Budowa konstrukcji: {ile - len(filary_ids)} utworów, "
        f"potem {len(filary_ids)} podpór…")
    plan = build_set(rdzen, wagi, target_track_count=ile - len(filary_ids),
                     **wspolne)

    energia, rozpietosc = F.energia_do_oceny(by_id)
    fn = _default_score_fn(wagi, par.luk, par.planer, energia, rozpietosc)
    srodkowe = [t for t in filary_ids if t not in (otwarcie, zamkniecie)]
    wynik, notki_podpor = F.wstaw_podpory(
        list(plan.track_order), srodkowe,
        lambda x, y: fn(by_id[x], by_id[y]))
    notki += notki_podpor

    if otwarcie:
        wynik = [otwarcie, *wynik]
        notki.append("rola otwarcie: pozycja #1 (poza pomiarem przęseł — "
                     "deklaracja DJ-a)")
    if zamkniecie:
        wynik = [*wynik, zamkniecie]
        notki.append(f"rola zamknięcie: pozycja #{len(wynik)} (deklaracja DJ-a)")

    notki.append(f"zgodność konstrukcji (bez podpór): {plan.mean_transition_score}")
    # zgodność CAŁOŚCI nie jest tą samą liczbą co z budowy — nie udajemy
    return plan.model_copy(update={"track_order": wynik,
                                   "mean_transition_score": None}), notki
