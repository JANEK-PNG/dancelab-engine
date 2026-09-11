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

from dancelab.sciezki import KORZEN

#: Nazwy plików, które są stemami, nie utworami. Kopia z `tui/app.py` — ta sama
#: lista, bo to ta sama higiena; gdyby kiedyś się rozjechały, to jest błąd.
STEM_NAMES = {"drums", "bass", "other", "vocals", "no_vocals", "accompaniment"}
MAX_TRACK_SEC = 15 * 60
# Historia świeżości — JEDNA dla obu skór, na korzeniu repo (była podwójna
# i względna do `cwd`; nazwa pliku zostaje, bo to dane tylko do przodu).
HISTORIA_SETOW = KORZEN / "data/cache/tui_historia_setow.jsonl"
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
    zrodlo_puli: str = "library"        # library | library-dysk | library-apple | folder
    folder: str = ""                    # dla zrodlo_puli == "folder"
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
            folder=str(dane.get("folder") or "").strip(),
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


def _skroc_notke(tekst: str, limit: int = 180) -> str:
    """Notka ma być zdaniem, nie zrzutem identyfikatorów.

    Silnik potrafi dopisać do ostrzeżenia całą listę par skrótów plików
    („removed 55 duplicate audio file(s): 1167…→0193…, …"). Na ekranie to
    ściana znaków, przez którą nie widać pozostałych ostrzeżeń — złapane na
    zrzucie 28.08. Zostawiamy zdanie i liczbę, listę ucinamy.
    """
    tekst = str(tekst)
    if len(tekst) <= limit:
        return tekst
    glowa, sep, ogon = tekst.partition(":")
    if sep and len(glowa) <= limit:
        ile = ogon.count(",") + 1
        return f"{glowa} — {ile} pozycji, lista pominięta"
    return tekst[:limit].rstrip() + "…"


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


def _kotwica(nazwa: str | None, analizy: list | None = None,
             stan_uzytkownika: dict | None = None) -> tuple[Any, list[str]]:
    """Rozwiąż „brzmi jak…". Niepowodzenie jest notką, nie wyjątkiem —
    set bez kotwicy jest prawomocny.

    „★ moje ulubione" to kotwica policzona z ♥ DJ-a, nie z księgi. Terminal
    umiał to od 12.08; okno pokazywało tę kartę na ścianie DJ-ów, a budowa
    odpowiadała „kotwica niedostępna" — ślepa uliczka zamknięta 02.09.
    """
    if not nazwa:
        return None, []
    from dancelab.decision.anchors import (MOJE_ULUBIONE, AnchorError,
                                           kotwica_z_utworow, resolve_anchor)

    if nazwa == MOJE_ULUBIONE:
        from dancelab.tui.user_store import resolve_tracks
        by_id = {a.track.track_id: a for a in (analizy or [])}
        ulubione, _brak = resolve_tracks(
            (stan_uzytkownika or {}).get("ulubione_utwory", []), by_id)
        try:
            kot = kotwica_z_utworow([a for a in (analizy or [])
                                     if a.track.track_id in ulubione])
        except AnchorError as exc:
            return None, [f"kotwica z ulubionych niemożliwa: {exc}"]
        return kot, [f"kotwica z Twoich ulubionych: {kot.n_tracks} utworów "
                     f"(kontur skoków niedostępny — to cecha sposobu grania, "
                     f"nie zbioru)"]
    try:
        return resolve_anchor(nazwa), []
    except AnchorError as exc:
        return None, [f"kotwica {nazwa!r} niedostępna: {exc}"]


def przeanalizuj_folder(folder: str, processed_dir: str, *,
                        mow: Postep | None = None,
                        przerwij: Callable[[], bool] | None = None
                        ) -> tuple[list, list[str]]:
    """Folder → pliki → bramkarz → analiza z postępem. Jedna droga dla:
    trybu Folder w budowie (obie skóry) i skanowania folderu (onboarding,
    do 02.09 tylko w terminalu i przepisane tam osobno). Odmawia Z POWODEM,
    gdy nie ma czego analizować — pusty wynik to nie jest wynik.
    """
    from dancelab.core.config import load_config
    from dancelab.ingestion.bramkarz import przesiej
    from dancelab.workflows.smart_playlist import analyze_files, discover_audio_files

    mow = mow or (lambda _s: None)
    folder = (folder or "").strip()
    if not folder:
        raise OdmowaBudowy("podaj ścieżkę folderu do analizy")
    znalezione = discover_audio_files(folder)
    if not znalezione:
        raise OdmowaBudowy(f"brak plików audio w: {folder}")
    notki: list[str] = []
    pliki, odrzucone = przesiej(znalezione)
    for sciezka, powod in odrzucone[:5]:
        notki.append(f"BRAMKARZ odrzucił: {pathlib.Path(sciezka).name[:40]} — {powod}")
    if len(odrzucone) > 5:
        notki.append(f"…i {len(odrzucone) - 5} kolejnych odrzutów")
    if not pliki:
        raise OdmowaBudowy("bramkarz odrzucił wszystko — nie ma co analizować")
    mow(f"Analiza {len(pliki)} plików…")
    analizy, porazki = analyze_files(
        pliki, load_config("configs/default.yaml"), processed_dir=processed_dir,
        stage_progress=lambda path, etap: mow(f"{etap}: {pathlib.Path(path).name[:40]}"),
        should_stop=(przerwij or (lambda: False)))
    for f in porazki[:5]:
        notki.append(f"nie przeanalizowano {pathlib.Path(f.source_path).name}: {f.error}")
    notka = zapisz_odrzuty(processed_dir, odrzucone,
                           [(str(f.source_path), str(f.error)) for f in porazki])
    if notka:
        notki.append(notka)
    notki.append(f"przeanalizowane: {len(analizy)} z {len(pliki)} plików")
    return list(analizy), notki


ODRZUTY_PLIK = "odrzuty_bramkarza.jsonl"


def zapisz_odrzuty(processed_dir: str, odrzucone: list, porazki: list) -> str | None:
    """Pełna lista plików, które NIE weszły do biblioteki — obok analiz.

    Notki pokazują pięć pierwszych; do 11.09 reszta znikała („…i N kolejnych")
    i nie dało się sprawdzić, które pliki odpadły. Plik ma rozszerzenie
    `.jsonl`, nie `.json`, żeby czytniki katalogu analiz (`*.json`) go nie
    brały. Nadpisywany przy każdym skanie: to stan OSTATNIEGO skanu. Nie
    tworzy katalogu — gdy go nie ma, mówi o tym zamiast zmyślać zapis.
    """
    import json
    import time

    wpisy = ([("bramkarz", p, r) for p, r in odrzucone]
             + [("analiza", p, r) for p, r in porazki])
    if not wpisy:
        return None
    cel = pathlib.Path(processed_dir) / ODRZUTY_PLIK
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        if not cel.parent.is_dir():
            raise OSError(f"nie ma katalogu {cel.parent}")
        cel.write_text("".join(
            json.dumps({"ts": ts, "etap": e, "sciezka": str(p), "powod": str(r)},
                       ensure_ascii=False) + "\n" for e, p, r in wpisy), encoding="utf-8")
    except OSError as exc:
        return f"pełnej listy odrzutów ({len(wpisy)}) nie zapisałem: {exc}"
    return f"pełna lista {len(wpisy)} plików, które nie weszły: {cel}"


def gatunki_w_secie(kolejnosc: list, by_id: dict) -> tuple[int, int]:
    """(ile utworów setu ma gatunek, ile jest w secie)."""
    z = sum(1 for tid in kolejnosc
            if getattr(getattr(by_id.get(tid), "track", None), "style_label", None))
    return z, len(kolejnosc)


def notka_gatunkow(z: int, n: int) -> str | None:
    """Znacznik przy secie: set bez gatunków nie może wyglądać jak set z gatunkami.

    Budowa odmawia, gdy dokarmianie pada; ale Rekordbox potrafi oddać zero
    gatunków BEZ błędu (np. brak pyrekordbox) — wtedy set powstaje, a styl
    nie brał udziału w doborze. Schemat linii produkcyjnej 03.09, stacja 3·04.
    """
    if n == 0 or z == n:
        return None
    if z == 0:
        return (f"BEZ GATUNKÓW: żaden z {n} utworów setu nie ma gatunku — "
                "styl nie brał udziału w doborze")
    if z * 2 < n:
        return f"mało gatunków: tylko {z} z {n} utworów setu ma gatunek"
    return None


def dokarm(analizy: list, *, wektory: bool = True) -> list[str]:
    """Dokarm analizy z Rekordboxa (gatunki, tonacje, wykonawca/tytuł) i —
    gdy ``wektory`` — wektorami brzmienia. Zwraca notki; awarię ZWRACA jako
    notkę zaczynającą się od „dokarmianie nie wyszło", nie rzuca.

    Jedno miejsce dla obu skór. Do 02.09 terminal dokarmiał w trzech
    (Biblioteka bez wektorów i tolerancyjnie, budowa i plan z wektorami),
    a okno tylko przy budowie — plan wczytany w oknie przed pierwszą budową
    szedł na SUROWEJ puli: bez tonacji z Rekordboxa, bez wektorów. Stan puli
    zależał od kolejności kliknięć.

    Wołający decyduje, czy awaria jest odmową: budowa — tak (set na gorszych
    danych bez słowa to to, czego ADR-005 zabrania); Biblioteka — nie
    (brak Rekordboxa nie znaczy martwej listy).
    """
    from dancelab.ingestion.analysis_enrichment import (
        attach_apple_genres, attach_apple_identity, attach_rekordbox_genres,
        attach_rekordbox_keys, attach_rekordbox_meta, attach_sound_embeddings)

    notki: list[str] = []
    n = len(analizy)
    try:
        czesci = []
        if wektory:
            emb = attach_sound_embeddings(analizy)
            czesci.append(f"wektory {emb.attached}/{n}")
            notki += emb.notes
        gen = attach_rekordbox_genres(analizy)
        ton = attach_rekordbox_keys(analizy)
        attach_rekordbox_meta(analizy)
        # Tożsamość Apple (strumień z ścieżki, plik lokalny z mostu ISRC) —
        # przed gatunkami Apple, bo most niesie też gatunek z katalogu.
        idn = attach_apple_identity(analizy)
        # Apple na końcu: uzupełnia tylko luki po Rekordboksie i tagach plików.
        ap = attach_apple_genres(analizy)
        czesci += [f"gatunki RB {gen.attached}/{n}", f"gatunki Apple {ap.attached}/{n}",
                   f"tonacje RB {ton.attached}/{n}", f"tożsamość Apple {idn.attached}/{n}"]
        notki += gen.notes + ton.notes + idn.notes + ap.notes
        notki.append("dokarmianie: " + ", ".join(czesci))
    except Exception as exc:                       # noqa: BLE001
        notki.append(f"dokarmianie nie wyszło: {exc}")
    return notki


def dokarmianie_padlo(notki: list[str]) -> str | None:
    """Powód awarii dokarmiania z listy notek albo None."""
    return next((n for n in notki if n.startswith("dokarmianie nie wyszło")), None)


def zbuduj(par: Parametry, *, processed_dir: str = PROCESSED_DOMYSLNY,
           postep: Postep | None = None, analizy: list | None = None,
           stan_uzytkownika: dict | None = None,
           dokarmione: bool = False,
           przerwij: Callable[[], bool] | None = None) -> dict[str, Any]:
    """Zbuduj set. Zwraca plan, pulę po id i notki — wszystko, co widok pokaże.

    ``postep`` dostaje krótkie komunikaty o etapie; ``None`` znaczy, że nikt
    nie słucha. ``analizy`` pozwala podać gotową pulę (test albo okno, które
    już ją ma) zamiast czytać z dysku po raz drugi; ``dokarmione`` mówi, że
    ta pula już przeszła `dokarm` — drugie dokarmianie to sekundy czytania
    master.db bez zysku. ``przerwij`` to pytanie „czy użytkownik anulował?"
    — odpowiedź „tak" kończy budowę odmową „anulowane".
    """
    from dancelab.core.config import load_config, load_weights
    from dancelab.decision.set_builder import build_set
    from dancelab.workflows.smart_playlist import estimate_track_count_for_duration

    mow = postep or (lambda _s: None)
    notki: list[str] = []

    if par.zrodlo_puli == "folder":
        analizy, notki_folderu = przeanalizuj_folder(
            par.folder, processed_dir, mow=mow, przerwij=przerwij)
        notki += notki_folderu
    else:
        if analizy is None:
            mow("Wczytuję analizy z biblioteki…")
            analizy, notki_puli = pula(processed_dir)
            notki += notki_puli
        analizy, notki_zrodla = _zawez_zrodlo(analizy, par.zrodlo_puli)
        notki += notki_zrodla
    if przerwij is not None and przerwij():
        raise OdmowaBudowy("anulowane")
    if not analizy:
        raise OdmowaBudowy("pusta pula — nie ma z czego budować")

    if not dokarmione:
        mow("Dokarmianie (wektory, gatunki, tonacje)…")
        notki_d = dokarm(analizy)
        padlo = dokarmianie_padlo(notki_d)
        if padlo:
            # jak dotąd: budowa na niedokarmionej puli to odmowa, nie set
            # z gorszych danych po cichu — tylko teraz z powodem po polsku
            raise OdmowaBudowy(padlo)
        notki += notki_d

    kotwica, notki_kotwicy = _kotwica(par.dj, analizy, stan_uzytkownika)
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
                from dancelab.tui.user_store import TRYBY_FILAROW
                etykieta = dict(TRYBY_FILAROW).get(tryb, tryb)
                notki.append(f"filary rozstawione ({etykieta}): pozycje "
                             + ", ".join(f"#{p}" for p in sorted(rozstawienie)))
        mow(f"Buduję set: {ile} utworów z {len(analizy)}…")
        # `locked_positions` to 1-indeksowane miejsca w gotowej playliście —
        # nazwa silnika, nie moja. `pinned_track_ids` gwarantuje SAMĄ obecność;
        # rozstawienie mówi dodatkowo GDZIE, i to ono realizuje metaforę filara.
        plan = build_set(
            analizy, wagi, target_track_count=ile,
            locked_positions=rozstawienie or None,
            pinned_track_ids=filary_ids or None, **wspolne)

    notki += [_skroc_notke(n) for n in (getattr(plan, "warnings", None) or [])]
    if par.ziarno is not None and par.nowosc != "deterministic":
        notki.append(f"świeżość: {par.nowosc} · ziarno {par.ziarno} — ten sam "
                     f"ziarno powtarza ten set; historię świeżości karmi dopiero "
                     f"UŻYCIE setu (zapis, wysyłka), nie każda budowa")

    # Odcisk czeka w wyniku — do historii trafia dopiero, gdy set zostanie
    # UŻYTY. Powód (zmierzony 06.08): dopisywanie przy każdej budowie zmieniało
    # historię między budowami i to samo ziarno dawało inny set. Do 02.09
    # liczył go tylko terminal; okno nie karmiło historii świeżości wcale.
    from dancelab.decision.history import context_hash, fingerprint_plan
    odcisk = fingerprint_plan(
        list(plan.track_order),
        ctx_hash=context_hash(bpm_min=par.bpm_min, bpm_max=par.bpm_max,
                              styles=tuple(par.style), dj=par.dj, arc=par.luk,
                              tempo=par.tempo, planner=par.planer),
        seed=par.ziarno, novelty_mode=par.nowosc, pinned_ids=filary_ids)

    z_gat, n_gat = gatunki_w_secie(list(plan.track_order), by_id)
    notka_g = notka_gatunkow(z_gat, n_gat)
    if notka_g:
        notki.append(notka_g)

    return {
        "plan": plan,
        "odcisk": odcisk,
        # znacznik „zbudowany bez gatunków": widok pokazuje go przy secie
        "gatunki_w_secie": {"z": z_gat, "z_ilu": n_gat},
        "kolejnosc": list(plan.track_order),
        "by_id": by_id,
        # Wagi wracają, bo tymi samymi liczy się potem propozycje padów.
        # Policzone drugi raz z konfiguracji mogłyby się rozjechać z setem.
        "wagi": wagi,
        "notki": notki,
        "kotwica": kotwica.name if kotwica else None,
        # Centroid wraca w całości, bo panel podmian ocenia kandydatów tą samą
        # kotwicą, którą set powstał — sugestie nie mogą mieć innego gustu.
        "kotwica_centroid": (list(kotwica.centroid) if kotwica else None),
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


def bez_pliku(track) -> str | None:
    """Powód odmowy, gdy czynność wymaga PLIKU, a utwór go nie ma.

    Utwory zaimportowane z analiz Rekordboxa (strumienie Apple Music) mają
    tempo, siatkę, energię i sekcje, ale nie mają audio na dysku — więc
    odsłuch i render szwu są niemożliwe. Mówimy to wprost, zamiast pokazywać
    błąd odtwarzacza.

    Zmierzone 01.09 na prawdziwej puli: 247 z 8261 analiz ma plik, 7935 to
    strumienie. W SETACH proporcja jest inna (9 i 13 z 17) — dlatego odmowa
    musi być zdaniem o TYM utworze, nie wyłączeniem całej funkcji.

    Kryterium: ścieżka NIE JEST ścieżką w systemie plików (strumień zapisany
    jako `apple-music:tracks:123`). Plik, który zniknął, to inny przypadek —
    tam odtwarzacz ma prawo powiedzieć swoje.
    """
    sciezka = str(getattr(track, "source_path", "") or "")
    if ma_plik(sciezka):
        return None
    nazwa = (getattr(track, "title", None) or sciezka or "ten utwór")[:38]
    if not sciezka:
        # Analiza bez ścieżki to trzeci przypadek, nie brak przypadku. Przed
        # 02.09 wypadał tu `None`, czyli „graj" — i okno rysowało ♪ przy
        # utworze, którego odtwarzacz dostawał jako napis "None".
        return f"{nazwa}: analiza nie zna ścieżki pliku — nie mam czego zagrać"
    return (f"{nazwa}: nie ma pliku na dysku "
            f"(utwór ze strumienia) — zagrasz go w Rekordboksie, "
            f"tutaj policzymy tylko dobór")


def ma_plik(sciezka: object) -> bool:
    """Czy ta ścieżka wskazuje plik na dysku. Jedno kryterium dla obu skór.

    Biblioteka okna czyta same NAGŁÓWKI analiz i ma słownik, nie obiekt
    `track`, więc potrzebuje predykatu bez `track` — ale kryterium musi być
    to samo, co w `bez_pliku`. Dwa oddzielne testy tej samej rzeczy rozjechały
    się dokładnie na pustej ścieżce: lista mówiła STR, tabela setu ♪.
    """
    return str(sciezka or "").startswith("/")
