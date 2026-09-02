"""Most między oknem a rdzeniem — cienki z założenia.

Każda metoda robi trzy rzeczy: sprawdza wejście, woła warstwę stanu, zwraca
słownik nadający się do JSON-a. **Żadnej logiki muzycznej ani decyzji o
zapisie tutaj nie ma** — ta mieszka w `dancelab.stan`, wspólna dla terminala
i okna. Gdyby most zaczął cokolwiek liczyć, obie skóry zaczęłyby się rozjeżdżać.

Wyjątki nie lecą do JavaScriptu, bo tam zamieniają się w nieczytelne odrzucone
obietnice. Zamiast tego każda metoda może zwrócić `{"blad": "…"}`, a widok ma
obowiązek to pokazać — zgodnie z ADR-005 („każde nie wiem ma swój piksel").
"""

from __future__ import annotations

import functools
import json
import threading
import traceback
from typing import Any

from dancelab.stan import (budowa, cue, dziennik, edycje, odtwarzacz, plan,
                           playlista, przebieg, sciezki, szew, zapis_cue)


#: Wartość w migawce edycji dla pada ZDJĘTEGO — odróżnia „zdjęty" od
#: „przesunięty na 0 ms", bo to dwie różne decyzje DJ-a.
ZDJETY = "zdjety"


def _bezpiecznie(fn):
    """Zamień wyjątek na komunikat, który widok potrafi wyświetlić."""

    @functools.wraps(fn)
    def opakowana(*a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as exc:                       # noqa: BLE001
            return {"blad": f"{type(exc).__name__}: {exc}",
                    "slad": traceback.format_exc(limit=3)}

    return opakowana


class Most:
    """Obiekt wystawiony do JavaScriptu jako ``window.pywebview.api``."""

    #: Ten sam katalog, z którego czyta terminal (`tui/app.py::PROCESSED_DEFAULT`).
    KATALOG_ANALIZ = "experiments_priv/2026-07-30_rebuild/processed"

    def __init__(self, katalog: str | None = None) -> None:
        self._edycje = edycje.nowe()
        # DWIE różne rzeczy, które przez chwilę dzieliły jedną nazwę i przez to
        # się nadpisywały: `_plan_cue` to propozycje padów silnika (CuePlan,
        # ma `.tracks`), a `_kolejnosc` to lista identyfikatorów setu.
        self._plan_cue: Any = None
        self._kolejnosc: list[str] = []
        # Plan silnika i historia edycji setu — to, co plik planu niesie obok
        # kolejności. Terminal trzymał je od 04.08 (`_engine_order`, `_edits`);
        # okno do 02.09 zapisywało plan tylko automatem po budowie, więc plan
        # zapisany pod nazwą po edycjach był w oknie niemożliwy.
        self._plan_silnika: list[str] = []
        self._edycje_setu: list[dict[str, Any]] = []
        self._analizy: dict[str, Any] = {}
        self._katalog = katalog or self.KATALOG_ANALIZ
        self._spis: list[dict[str, Any]] = []
        # Indeks spisu po identyfikatorze — budowany LENIWIE, patrz
        # `_wpis_spisu`. Bez niego cztery miejsca szukały utworu przez
        # `next(u for u in self._spis ...)`, liniowo po 8261 wpisach, a
        # `filary()` robiło to raz na filar przy każdym klawiszu w szukajce.
        self._po_id: dict[str, dict[str, Any]] = {}
        self._po_id_dla: tuple[int, int] | None = None
        # Budowa setu trwa dziesiątki sekund. W pywebview wywołanie z JS jest
        # synchroniczne, więc budowanie wprost zamroziłoby okno — stąd wątek
        # i stan odpytywany przez `postep_budowy`.
        self._budowa: dict[str, Any] = {"stan": "bezczynny"}
        self._analizy_pula: list | None = None
        # Notki puli (higiena + dokarmianie) żyją TU, nie w `_budowa`: tamten
        # słownik każda budowa podmienia, a pula siedzi w cache — bramka
        # „dokarmianie padło → odmowa" działała więc tylko przy PIERWSZEJ
        # budowie, a druga szła po cichu na surowej puli.
        self._notki_puli: list[str] = []
        # Zapis cue jest DWUSTOPNIOWY: tu leży plan policzony w stopniu
        # pierwszym. Każda zmiana padów albo setu go kasuje, bo inaczej
        # potwierdzenie zapisałoby stan sprzed edycji.
        self._zapis_gotowy: Any = None
        # Playlista ma własny stopień pierwszy: nazwa i kolejność, na których
        # policzono liczby. Zmiana któregokolwiek unieważnia je — inaczej DJ
        # potwierdzałby liczby innego setu.
        self._playlista_gotowa: dict[str, Any] | None = None
        # Stan DJ-a (playlisty, filary, ulubione) — ten sam plik, który czyta
        # terminal. Wczytany raz; każda zmiana od razu leci na dysk, żeby obie
        # skóry widziały to samo bez restartu którejkolwiek.
        self._stan_dja: dict | None = None
        # Dziennik decyzji (Q14): utwory, których pady widok narysował przy
        # istniejącym planie. Pad silnika w utworze spoza tej listy przeszedł
        # DOMYŚLNIE — nazwanie go „zaakceptowanym" byłoby zmyśleniem.
        self._pady_pokazane: set[str] = set()
        self._parametry_budowy: dict[str, Any] = {}
        self._ostatni_przygotuj: dict[str, Any] | None = None
        self._wagi_budowy: Any = None
        # Nakładka edycji przeżywa przebudowę setu (celowo — ręczne pady DJ-a
        # nie znikają, bo silnik policzył nowy plan). Werdykt musi jednak
        # odróżniać nadpisanie TEJ propozycji od nadpisania sprzed niej —
        # stąd migawka edycji zastanych w chwili budowy planu.
        #
        # WARTOŚCI, nie same klucze. Zbiór kluczy nie umiał odróżnić „pad
        # postawiony przed budową" od „ten sam pad poprawiony PO obejrzeniu
        # propozycji" — `cue_edycje.przesun` nadpisuje wpis pod tym samym
        # kluczem, więc reakcja na plan wchodziła do dziennika ze znacznikiem
        # „to nie była reakcja". Porównanie wartości rozstrzyga to samo bez
        # dopisywania czegokolwiek w trzech miejscach edycji, a cofnięcie do
        # stanu sprzed planu samo przywraca znacznik.
        self._edycje_sprzed_planu: dict[str, Any] = {}
        # Edycja setu: to, czym set był oceniany przy budowie (wagi, łuk,
        # planer, okno tempa, kotwica) — panel podmian liczy kandydatów
        # dokładnie tym samym, inaczej sugestie miałyby inny gust niż set.
        self._ctx_edycji: dict[str, Any] | None = None
        self._odcisk_zapisany = False
        self._kandydaci_meta: dict[str, dict[str, Any]] = {}
        # Liczenie kandydatów trwa ~4 s na pełnej puli (pomiar 01.09), więc
        # chodzi w wątku i ma własny stan odpytywany przez widok — jak budowa.
        self._kandydaci_stan: dict[str, Any] = {"stan": "bezczynny"}
        # Wczytanie planu wymaga całej puli (~20 s zimno) — też w wątku.
        self._plan_stan: dict[str, Any] = {"stan": "bezczynny"}
        # DŹWIĘK. Jeden odtwarzacz na całe okno — dwa ekrany, jeden proces,
        # bo dwa naraz to dwa utwory grające przez siebie. Proces jest ZEWNĘTRZNY
        # (ffplay/afplay), więc `zamknij` wisi na zdarzeniu zamknięcia okna.
        self._audio = odtwarzacz.Odtwarzacz()
        # pywebview odpala OSOBNY WĄTEK na każde wywołanie z JS
        # (`webview/util.py::js_bridge_call`), a `stan_odtwarzania` chodzi
        # cztery razy na sekundę i sam zabija martwy proces. Bez zamka
        # odpytywanie mogło ubić proces, który `graj` właśnie uruchomił:
        # poll widzi starą, martwą klamkę, `graj` startuje nową, poll ją tnie.
        self._zamek_audio = threading.Lock()
        # Czego słuchasz: utwór czy szew, i którego. Sam odtwarzacz zna tylko
        # ścieżkę pliku — po ścieżce szwu z cache nie poznasz pary utworów.
        self._gra_co: dict[str, Any] | None = None
        # Render szwu to sekundy pracy (dekodowanie dwóch utworów), więc wątek
        # i odpytywanie — tak samo jak kandydaci i budowa. Dźwięk rusza dopiero
        # w `postep_szwu`, czyli po TWOIM geście, a nie w środku renderu.
        self._szew_stan: dict[str, Any] = {"stan": "bezczynny"}
        self._gatunki_stan: dict[str, Any] = {"stan": "bezczynny"}
        self._plan_cue_przeliczony = False
        # Po edycji kolejności propozycje padów silnika dotyczą STAREGO setu.
        # Flaga każe je przeliczyć w stopniu pierwszym zapisu — liczby, które
        # DJ potwierdza, muszą dotyczyć planu, który naprawdę pójdzie do bazy.
        self._plan_cue_nieaktualny = False

    # ------------------------------------------------------------ biblioteka

    @_bezpiecznie
    def biblioteka(self, limit: int = 400) -> dict[str, Any]:
        """Spis utworów do wyboru — bez tego okno startuje puste.

        Czyta NAGŁÓWKI plików analizy, nie całe pliki: każdy waży setki
        kilobajtów przez klatki i krzywe, a do listy potrzeba tytułu i tempa.
        Pełną analizę wczytuje dopiero `wczytaj_utwor`.
        """
        import json
        from pathlib import Path

        if self._spis:
            return {"utwory": self._spis[:limit], "wszystkich": len(self._spis),
                    "katalog": self._katalog}

        katalog = Path(self._katalog)
        if not katalog.exists():
            return {"blad": f"nie ma katalogu analiz: {katalog}",
                    "podpowiedz": "przeanalizuj folder w terminalu: dancelab tui"}

        spis: list[dict[str, Any]] = []
        for plik in sorted(katalog.glob("*.json")):
            try:
                with plik.open("rb") as f:
                    # 4 kB obcinało obiekt „track" przed gatunkiem i źródłem
                    # tonacji — pola były, tylko poza oknem odczytu
                    prefiks = f.read(16384).decode("utf-8", "replace")
                start = prefiks.find('"track"')
                if start == -1:
                    continue
                # bezpiecznie: parsujemy tylko obiekt "track", nie cały plik
                pocz = prefiks.find("{", start)
                glebokosc, i, w_cudzyslowie, ucieczka = 0, pocz, False, False
                while i < len(prefiks):
                    z = prefiks[i]
                    if w_cudzyslowie:
                        if ucieczka:
                            ucieczka = False
                        elif z == "\\":
                            ucieczka = True
                        elif z == '"':
                            w_cudzyslowie = False
                    elif z == '"':
                        w_cudzyslowie = True
                    elif z == "{":
                        glebokosc += 1
                    elif z == "}":
                        glebokosc -= 1
                        if glebokosc == 0:
                            break
                    i += 1
                else:
                    continue
                t = json.loads(prefiks[pocz:i + 1])
            except (OSError, ValueError):
                continue
            spis.append({
                "track_id": t.get("track_id") or plik.stem,
                "tytul": t.get("title") or plik.stem,
                "wykonawca": t.get("artist"),
                "bpm": t.get("bpm_estimate"),
                "tonacja": t.get("key_estimate"),
                # źródło tonacji jest częścią prawdy o niej — „RB" to sędzia
                # niezależny od naszego detektora, który na elektronice bywa słaby
                "tonacja_zrodlo": t.get("key_detection_source"),
                "gatunek": t.get("style_label"),
                # ścieżka jest potrzebna filarom i ulubionym: wpis trzyma ID
                # ORAZ ścieżkę, żeby przeżyć przebudowę katalogu analiz
                "sciezka": t.get("source_path"),
                "dlugosc_sec": t.get("duration_sec"),
                # Grywalny = ma plik na dysku. 7935 z 8261 to strumienie
                # Apple Music — biblioteka ma to pokazywać, nie ukrywać.
                "grywalny": budowa.ma_plik(t.get("source_path")),
            })

        self._spis = spis
        return {"utwory": spis[:limit], "wszystkich": len(spis),
                "katalog": self._katalog}

    @_bezpiecznie
    def szukaj(self, fraza: str = "", tonacja: str = "", bpm: str = "",
               tylko_ulubione: bool = False, sortuj: str = "",
               limit: int = 400) -> dict[str, Any]:
        """Biblioteka z filtrami — TA SAMA reguła co w terminalu.

        Nie „takie same reguły", tylko jedna funkcja: `stan.biblioteka.pasuje`
        na polach nagłówka. Do 02.09 okno miało własną kopię, która szukała
        bez nazwy pliku — terminal i okno dawały różne listy na tę samą frazę.
        """
        # limit=0: wołamy PO TO, żeby spis się wczytał (i żeby odmowa
        # wróciła), a nie po kopię ośmiu tysięcy wpisów na każdy klawisz.
        wynik_spisu = self.biblioteka(limit=0)
        # Odmowa biblioteki (brak katalogu analiz) jest ODPOWIEDZIĄ, nie zerem.
        # Przepuszczona przez `.get(...) or []` wyglądała jak „nic nie pasuje" —
        # a to ADR-005: każde „nie wiem" ma swój piksel.
        if "blad" in wynik_spisu:
            return wynik_spisu
        spis = self._spis
        f = (fraza or "").strip().lower()
        ton = (tonacja or "").strip().upper()
        lo = hi = None
        okno = (bpm or "").replace(",", ".").strip()
        if okno:
            from dancelab.stan.budowa import rozbierz_tempo
            lo, hi, blad = rozbierz_tempo(okno)
            if blad:
                return {"blad": blad, "pole": "bpm"}

        odp_ulub, odp_filary = self.ulubione(), self.filary()
        for odp in (odp_ulub, odp_filary):
            if "blad" in odp:
                return odp
        ulubione = set(odp_ulub.get("ulubione") or [])
        filary = {w["track_id"] for w in (odp_filary.get("filary") or [])}

        from dancelab.stan.biblioteka import pasuje

        wynik = []
        for u in spis:
            if not pasuje(sciezka=u.get("sciezka"), wykonawca=u.get("wykonawca"),
                          tytul=u.get("tytul"), gatunek=u.get("gatunek"),
                          tonacja=u.get("tonacja"), bpm=u.get("bpm"),
                          szukaj=f, tonacja_szukana=ton, bpm_lo=lo, bpm_hi=hi):
                continue
            if tylko_ulubione and u["track_id"] not in ulubione:
                continue
            wynik.append({**u,
                          "ulubiony": u["track_id"] in ulubione,
                          "filar": u["track_id"] in filary})

        klucze = {"tytul": lambda u: (u.get("tytul") or "").lower(),
                  "bpm": lambda u: (u.get("bpm") is None, u.get("bpm") or 0),
                  "tonacja": lambda u: (not u.get("tonacja"),
                                        u.get("tonacja") or ""),
                  "dlugosc": lambda u: (u.get("dlugosc_sec") is None,
                                        u.get("dlugosc_sec") or 0)}
        if sortuj in klucze:
            wynik.sort(key=klucze[sortuj])
        return {"utwory": wynik[:limit], "znalezione": len(wynik),
                "wszystkich": len(spis)}

    @_bezpiecznie
    def wczytaj_utwor(self, track_id: str) -> dict[str, Any]:
        """Wczytaj pełną analizę i zwróć przebieg gotowy do narysowania."""
        from dancelab.storage.repositories import FileAnalysisRepository

        if track_id not in self._analizy:
            repo = FileAnalysisRepository(self._katalog)
            self._analizy[track_id] = repo.get(track_id)
        wynik = przebieg.zbuduj(self._analizy[track_id]).do_slownika()
        wpis = self._wpis_spisu(track_id)
        wynik["tytul"] = (wpis or {}).get("tytul", track_id)
        wynik["wykonawca"] = (wpis or {}).get("wykonawca")
        return wynik

    # ---------------------------------------------------------------- stan

    @_bezpiecznie
    def stan_rekordboxa(self) -> dict[str, Any]:
        """Czy wolno pisać do master.db. Pasek statusu odpytuje to co kilka sekund."""
        from dancelab.ingestion.rekordbox_cue_writer import is_rekordbox_running

        otwarty = bool(is_rekordbox_running())
        return {
            "otwarty": otwarty,
            "zapis_dozwolony": not otwarty,
            "powod": ("Rekordbox jest otwarty — zapis skorumpowałby bazę"
                      if otwarty else "Rekordbox zamknięty — zapis dostępny"),
        }

    @_bezpiecznie
    def wersja(self) -> dict[str, str]:
        from dancelab import __version__ as v

        return {"dancelab": str(v)}

    # -------------------------------------------------------------- utwory

    @_bezpiecznie
    def przebieg_utworu(self, track_id: str, punktow: int = 900) -> dict[str, Any]:
        """Fala, sekcje i siatka taktów jednego utworu — do narysowania."""
        analiza = self._analizy.get(track_id)
        if analiza is None:
            return {"blad": f"nie mam wczytanej analizy dla {track_id!r}"}
        return przebieg.zbuduj(analiza, punktow=int(punktow)).do_slownika()

    # ---------------------------------------------------------------- pady

    @_bezpiecznie
    def pady(self, track_id: str) -> dict[str, Any]:
        """Pady utworu: propozycje silnika nadpisane ręcznymi zmianami.

        Bez planu setu pokazujemy same ręczne pady, zamiast odmawiać. Janek może
        chcieć poustawiać cue w pojedynczym utworze, nie budując całego setu —
        i to jest sensowne użycie, nie stan błędu.
        """
        self._pady_pokazane.add(track_id)
        return self._pady_bez_sladu(track_id)

    def _pady_bez_sladu(self, track_id: str) -> dict[str, Any]:
        """Te same pady, ALE bez wpisu do „pokazanych DJ-owi".

        Rozdział jest częścią uczciwości dziennika (ADR-005, Q14): pad silnika
        liczy się za zaakceptowany dopiero wtedy, gdy DJ go ZOBACZYŁ. Odsłuch
        od pada i render szwu czytają pady maszynowo — szew czyta nawet pady
        NASTĘPNEGO utworu, którego ekranu nikt nie otwierał. Gdyby szły przez
        `pady`, dziennik zapisałby, że DJ widział i przyjął coś, czego nie
        miał na oczach.
        """
        # JEDNA droga, także bez planu: `efektywne_pady` z pustym planem robi
        # dokładnie to samo co ręczna pętla, ale nadaje padom pole `typ`
        # („reczny") i rozbiera klucz przez `rsplit`. Ręczna wersja gubiła
        # jedno i drugie — szew z Twoich padów padał na `KeyError: 'typ'`,
        # a identyfikator z pionową kreską dawał zły pad.
        jest_plan = self._plan_cue is not None
        pady = edycje.efektywne_pady(self._plan_cue or _pusty_plan_cue(),
                                     self._edycje, track_id)
        return {"pady": pady,
                "zrodlo": ("silnik + ręczne" if jest_plan
                           else "tylko ręczne (brak planu setu)")}

    def _migawka_edycji(self) -> dict[str, Any]:
        """Wartość każdej edycji TERAZ: klucz → position_ms albo `ZDJETY`.

        Porównanie takiej migawki z bieżącym stanem mówi, czy edycja jest tą
        samą decyzją, którą DJ podjął przed budową planu, czy już inną.
        """
        migawka: dict[str, Any] = {
            klucz: wpis.get("position_ms")
            for klucz, wpis in (self._edycje.get("nadpisania") or {}).items()}
        # zdjęcie po nadpisaniu: ostatnia decyzja wygrywa
        for klucz in (self._edycje.get("zdjete") or []):
            migawka[klucz] = ZDJETY
        return migawka

    def _kontekst_propozycji(self, track_id: str, pad: str) -> dict[str, Any]:
        """Co silnik proponował dla tego pada — o ile DJ to w ogóle oglądał.

        Bez planu albo bez narysowanych padów zwraca pusto: edycja w ciemno
        nie dostaje pól kontekstu, bo porównanie, którego DJ nie widział,
        niczego nie mierzy. `silnik_ms: None` to co innego — fakt, że silnik
        dla tej litery nie proponował nic (czyli pad jest w całości ręczny).
        """
        if self._plan_cue is None or track_id not in self._pady_pokazane:
            return {}
        for t in self._plan_cue.tracks:
            if t.content_id == track_id:
                for c in t.cues:
                    if c.pad_label == pad:
                        return {"silnik_ms": c.position_ms, "typ_cue": c.cue_type}
                return {"silnik_ms": None}
        return {}

    @staticmethod
    def _z_dziennikiem(wynik: dict[str, Any], blad: str | None) -> dict[str, Any]:
        """Ostrzeżenie dziennika dokleja się do odpowiedzi, nie ginie."""
        if blad:
            wynik["dziennik"] = blad
        return wynik

    @_bezpiecznie
    def postaw_pad(self, track_id: str, pad: str, position_ms: int) -> dict[str, Any]:
        self._zapis_gotowy = None
        kontekst = self._kontekst_propozycji(track_id, pad)
        edycje.postaw(self._edycje, track_id, pad, int(position_ms))
        blad = dziennik.dopisz("cue_postaw", skora="gui", track_id=track_id, pad=pad,
                               position_ms=int(position_ms), **kontekst)
        return self._z_dziennikiem(self.pady(track_id), blad)

    @_bezpiecznie
    def przesun_pad(self, track_id: str, pad: str, uderzenia: int,
                    bpm: float) -> dict[str, Any]:
        """Przesuń o całe uderzenia — po to, żeby nie da się trafić między takty."""
        self._zapis_gotowy = None
        biezacy = self.pady(track_id).get("pady", {}).get(pad)
        if biezacy is None:
            return {"blad": f"pad {pad} nie jest postawiony — nie ma czego przesuwać"}
        nowa = edycje.przesun(self._edycje, track_id, pad, int(uderzenia),
                              float(bpm), biezacy.get("silnik_ms"),
                              int(biezacy["position_ms"]))
        blad = dziennik.dopisz("cue_przesuniecie", skora="gui", track_id=track_id, pad=pad,
                               uderzenia=int(uderzenia), position_ms=nowa,
                               **self._kontekst_propozycji(track_id, pad))
        return self._z_dziennikiem(self.pady(track_id), blad)

    @_bezpiecznie
    def zdejmij_pad(self, track_id: str, pad: str) -> dict[str, Any]:
        self._zapis_gotowy = None
        kontekst = self._kontekst_propozycji(track_id, pad)
        edycje.zdejmij(self._edycje, track_id, pad)
        blad = dziennik.dopisz("cue_zdjecie", skora="gui", track_id=track_id, pad=pad,
                               **kontekst)
        return self._z_dziennikiem(self.pady(track_id), blad)

    @_bezpiecznie
    def cofnij(self, track_id: str) -> dict[str, Any]:
        """Cofnięcie jest w rdzeniu, nie w widoku — terminal ma je tak samo."""
        self._zapis_gotowy = None
        przed_n = dict(self._edycje.get("nadpisania") or {})
        przed_z = set(self._edycje.get("zdjete") or [])
        udalo = edycje.cofnij(self._edycje)
        blad = None
        if udalo:
            # Cofnięcie działa na WSPÓLNEJ historii edycji, nie na otwartym
            # utworze — może przywrócić pad zupełnie innego utworu niż ten
            # na ekranie. Zdarzenie niesie klucze, które naprawdę wróciły.
            po_n = self._edycje.get("nadpisania") or {}
            po_z = set(self._edycje.get("zdjete") or [])
            zmienione = sorted(
                {k for k in set(przed_n) | set(po_n)
                 if przed_n.get(k) != po_n.get(k)} | (przed_z ^ po_z))
            blad = dziennik.dopisz("cue_cofniecie", skora="gui", zmienione=zmienione)
        wynik = self._z_dziennikiem(self.pady(track_id), blad)
        wynik["cofnieto"] = bool(udalo)
        return wynik

    # ------------------------------------------------------- trwałość edycji

    #: Gdzie okno odkłada swoje zmiany. Ten sam katalog, w którym TUI trzyma
    #: plany, żeby obie skóry miały jedno miejsce — nie dwa równoległe światy.
    #: Zakotwiczone w korzeniu repo, nie w `cwd`: okno odpalone z ikony dostaje
    #: `cwd` od launchd i pisało wtedy do `/data/exports/…`, czyli nigdzie.
    PLIK_EDYCJI = str(sciezki.KORZEN / "data/exports/tui_plany/gui_edycje.json")

    @_bezpiecznie
    def zapisz_edycje(self) -> dict[str, Any]:
        """Odłóż zmiany na dysk, żeby przeżyły zamknięcie okna.

        Bez tego edycje z GUI żyją tylko w pamięci tej instancji, terminal ich
        nie widzi i nie może zrecenzować — a to jest warunek, który musi być
        spełniony, ZANIM okno dostanie prawo pisać do master.db.
        """
        import json
        from pathlib import Path

        plik = Path(self.PLIK_EDYCJI)
        plik.parent.mkdir(parents=True, exist_ok=True)
        plik.write_text(json.dumps(
            {"nadpisania": self._edycje.get("nadpisania", {}),
             "zdjete": self._edycje.get("zdjete", [])},
            ensure_ascii=False, indent=1), encoding="utf-8")
        return {"zapisano": str(plik),
                "padow": len(self._edycje.get("nadpisania") or {})}

    @_bezpiecznie
    def wczytaj_edycje(self) -> dict[str, Any]:
        """Wczytaj zmiany z poprzedniej sesji. Historia cofania NIE wraca —
        cofanie dotyczy bieżącej pracy, a nie tego, co było wczoraj."""
        import json
        from pathlib import Path

        plik = Path(self.PLIK_EDYCJI)
        if not plik.exists():
            return {"wczytano": 0}
        dane = json.loads(plik.read_text(encoding="utf-8"))
        self._edycje["nadpisania"] = dane.get("nadpisania") or {}
        self._edycje["zdjete"] = dane.get("zdjete") or []
        self._edycje["historia"] = []
        # Edycje z dysku pochodzą sprzed bieżącego planu z definicji —
        # werdykt nie ma prawa policzyć ich jako reakcji na jego propozycje.
        self._edycje_sprzed_planu.update(self._migawka_edycji())
        return {"wczytano": len(self._edycje["nadpisania"])}

    # ------------------------------------------------------------- budowa

    def _pula(self) -> list:
        """Pula analiz, wczytana raz. 8 tysięcy plików to kilkanaście sekund."""
        if self._analizy_pula is None:
            analizy, notki = budowa.pula(self._katalog)
            # Dokarmienie TU, nie w budowie: plan wczytany przed pierwszą
            # budową szedł na surowej puli (bez tonacji RB, bez wektorów),
            # a po budowie — na dokarmionej. Terminal dokarmiał zawsze.
            notki += budowa.dokarm(analizy)
            self._notki_puli = notki
            # Niedokarmionej puli NIE zapamiętujemy: następne wejście (po
            # naprawie Rekordboxa) ma czytać i dokarmiać od nowa, zamiast
            # dostać z cache listę, która „już była" — surową.
            if budowa.dokarmianie_padlo(notki) is None:
                self._analizy_pula = analizy
            return analizy
        return self._analizy_pula

    @_bezpiecznie
    def buduj_set(self, formularz: dict[str, Any]) -> dict[str, Any]:
        """Rusz budowę w tle. Wynik odbiera się przez `postep_budowy`."""
        if self._budowa.get("stan") == "trwa":
            return {"blad": "budowa już trwa"}
        try:
            par = budowa.Parametry.z_formularza(formularz or {})
        except budowa.OdmowaBudowy as exc:
            # odmowa parametrów wraca NATYCHMIAST — użytkownik ma poprawić pole,
            # a nie czekać na wątek, który i tak nie ruszy
            return {"blad": str(exc), "pole": "parametry"}

        # „start" wisiałoby na ekranie przez całe wczytywanie ośmiu tysięcy
        # analiz — pierwszy etap musi nazywać to, co naprawdę się dzieje.
        self._budowa = {"stan": "trwa", "notki": [],
                        "etap": ("Wczytuję analizy…" if self._analizy_pula is None
                                 else "Przygotowuję pulę…")}
        threading.Thread(target=self._buduj_w_tle, args=(par,),
                         daemon=True).start()
        return {"ruszylo": True}

    def _buduj_w_tle(self, par: budowa.Parametry) -> None:
        def etap(tekst: str) -> None:
            self._budowa["etap"] = tekst

        try:
            stan_u = None
            try:
                # ten sam stan, który edytuje panel filarów — inaczej okno
                # budowałoby z filarów sprzed własnych zmian
                stan_u = self._stan_uzytkownika()
            except Exception:                          # noqa: BLE001
                pass                                   # filary są opcjonalne

            pula = self._pula()
            padlo = budowa.dokarmianie_padlo(self._notki_puli)
            if padlo:
                raise budowa.OdmowaBudowy(padlo)
            wynik = budowa.zbuduj(par, processed_dir=self._katalog,
                                  postep=etap, analizy=pula,
                                  stan_uzytkownika=stan_u, dokarmione=True)
            self._kolejnosc = list(wynik["kolejnosc"])
            self._plan_silnika = list(wynik["kolejnosc"])
            self._edycje_setu = []
            self._zapis_gotowy = None
            for a in wynik["by_id"].values():
                self._analizy[a.track.track_id] = a

            # Propozycje padów liczymy od razu, w tym samym wątku: bez nich
            # ekran szwu pokazywałby dla świeżego setu same puste utwory,
            # a zapis do Rekordboksa miałby do wysłania tylko ręczne pady.
            etap("Liczę propozycje padów…")
            try:
                self._plan_cue = zapis_cue.propozycje(
                    wynik["kolejnosc"], wynik["by_id"], wynik["wagi"])
            except Exception as exc:                   # noqa: BLE001
                self._plan_cue = None
                wynik["notki"].append(
                    f"propozycji padów nie policzyłem ({exc}) — pady zostają "
                    f"ręczne, set jest w porządku")

            sciezka = plan.zapisz(
                wynik["kolejnosc"], wynik["by_id"],
                nazwa=f"z okna {par.minuty:g} min",
                parametry={"minuty": par.minuty, "bpm_min": par.bpm_min,
                           "bpm_max": par.bpm_max, "dj": par.dj},
                plan_silnika=wynik["kolejnosc"])

            # Dziennik decyzji (Q14): budowa to PROPOZYCJA silnika — bez jej
            # zapisu późniejsze edycje wiszą w próżni i nie wiadomo, względem
            # czego DJ decydował. Świeża budowa zeruje też znacznik „pady
            # pokazane", bo dotyczył poprzedniego planu.
            self._pady_pokazane = set()
            self._parametry_budowy = {
                "minuty": par.minuty, "bpm_min": par.bpm_min,
                "bpm_max": par.bpm_max, "dj": par.dj}
            self._wagi_budowy = wynik.get("wagi")
            self._edycje_sprzed_planu = self._migawka_edycji()
            self._ctx_edycji = {
                "wagi": wynik.get("wagi"), "luk": par.luk,
                "planer": par.planer, "bpm_min": par.bpm_min,
                "bpm_max": par.bpm_max,
                "kotwica_centroid": wynik.get("kotwica_centroid"),
                "filary": list(wynik.get("filary") or []),
                "odcisk": wynik.get("odcisk")}
            self._odcisk_zapisany = False
            self._kandydaci_meta = {}
            self._plan_cue_nieaktualny = False
            self._plan_cue_przeliczony = False
            dziennik.dopisz("budowa", skora="gui", parametry=self._parametry_budowy,
                utworow=len(wynik["kolejnosc"]),
                kolejnosc=list(wynik["kolejnosc"]),
                pady_silnika=(sum(len(t.cues) for t in self._plan_cue.tracks)
                              if self._plan_cue is not None else 0),
                edycje_zastane=len(self._edycje_sprzed_planu),
                plan=str(sciezka))

            self._budowa = {
                "stan": "gotowe",
                "utwory": [self._wiersz(t, wynik["by_id"]) for t in wynik["kolejnosc"]],
                "notki": list(self._notki_puli) + wynik["notki"],
                "kotwica": wynik["kotwica"],
                "filary": wynik["filary"],
                "tryb_filarow": wynik["tryb_filarow"],
                "filary_stan": wynik["filary_stan"],
                "filary_zgloszone": wynik["filary_zgloszone"],
                "plan": str(sciezka),
            }
        except budowa.OdmowaBudowy as exc:
            self._budowa = {"stan": "odmowa", "blad": str(exc),
                            "notki": self._budowa.get("notki") or []}
        except Exception as exc:                       # noqa: BLE001
            self._budowa = {"stan": "blad",
                            "blad": f"{type(exc).__name__}: {exc}",
                            "slad": traceback.format_exc(limit=4)}


    def _utrwal_odcisk(self, powod: str) -> str | None:
        """Dopisz odcisk zbudowanego setu do historii świeżości — raz na
        budowę, przy pierwszym UŻYCIU (zapis cue albo wysyłka playlisty).
        Ta sama reguła co S/W w terminalu; do 02.09 okno nie karmiło historii
        wcale, więc „świeżość" omijała tylko sety z terminala."""
        odcisk = (self._ctx_edycji or {}).get("odcisk")
        if odcisk is None or self._odcisk_zapisany:
            return None
        from dancelab.decision.history import HistoryStore
        try:
            HistoryStore(budowa.HISTORIA_SETOW).append(odcisk)
        except Exception as exc:                       # noqa: BLE001
            return f"historii setu nie zapisałem: {exc}"
        self._odcisk_zapisany = True
        return f"historia świeżości: odcisk dopisany ({powod})"

    def _wiersz(self, tid: str, by_id: dict) -> dict[str, Any]:
        a = by_id[tid]
        t = a.track
        return {
            "track_id": tid,
            "tytul": t.title or tid,
            "wykonawca": t.artist,
            "bpm": t.bpm_estimate,
            "tonacja": t.key_estimate,
            # źródło tonacji jest częścią prawdy o niej: „RB" to sędzia,
            # brak źródła to nasz detektor, który na elektronice bywa słaby
            "tonacja_zrodlo": t.key_detection_source,
            "dlugosc_sec": t.duration_sec,
            # Czy da się TEGO posłuchać. W puli plik ma 247 z 8261 analiz
            # (pomiar 01.09) — gdyby widok tego nie pokazywał, DJ klikałby
            # w guzik odsłuchu i dostawał odmowę zamiast dźwięku.
            "grywalny": budowa.bez_pliku(t) is None,
        }

    @_bezpiecznie
    def postep_budowy(self) -> dict[str, Any]:
        """Stan budowy. Widok odpytuje co pół sekundy, dopóki trwa."""
        return dict(self._budowa)

    # ---------------------------------------------------------- plan setu

    @_bezpiecznie
    def biezacy_plan(self) -> dict[str, Any]:
        """Set, nad którym pracujemy — ten sam plik, który czyta terminal."""
        wynik = plan.wczytaj(self._analizy)
        self._kolejnosc = list(wynik.get("kolejnosc") or [])
        return wynik

    @_bezpiecznie
    def lista_planow(self) -> dict[str, Any]:
        return {"plany": plan.lista()}

    @_bezpiecznie
    def zapisz_plan(self, nazwa: str = "") -> dict[str, Any]:
        """Ctrl+S: zapisz bieżący set pod nazwą — z planem silnika i historią
        edycji, tak jak terminal. Zapis liczy się jako UŻYCIE setu (odcisk do
        historii świeżości), bo tak liczy go terminal przy S."""
        if not self._kolejnosc:
            return {"blad": "najpierw zbuduj set albo wczytaj plan — "
                            "nie ma czego zapisać"}
        mianowana = (nazwa or "").strip() or self._nazwa_playlisty("").replace(
            "DanceLab ", "", 1)
        sciezka = plan.zapisz(self._kolejnosc, self._analizy, nazwa=mianowana,
                              parametry=dict(self._parametry_budowy or {}),
                              plan_silnika=self._plan_silnika,
                              edycje=self._edycje_setu)
        historia = self._utrwal_odcisk("zapisany plan")
        blad = dziennik.dopisz("zapis_planu", skora="gui", nazwa=mianowana,
                               plan=str(sciezka), utworow=len(self._kolejnosc),
                               edycji=len(self._edycje_setu))
        wynik = {"zapisano": str(sciezka), "nazwa": mianowana,
                 "utworow": len(self._kolejnosc), "edycji": len(self._edycje_setu)}
        if historia:
            wynik["historia"] = historia
        return self._z_dziennikiem(wynik, blad)

    @_bezpiecznie
    def usun_plan(self, sciezka: str) -> dict[str, Any]:
        """X na liście planów: do kosza obok planów, nic nie znika bez śladu."""
        cel = plan.usun(str(sciezka))
        return {"kosz": str(cel), "plany": plan.lista()}

    @_bezpiecznie
    def wczytaj_plan(self, sciezka: str) -> dict[str, Any]:
        """Rusz wczytywanie planu W TLE. Wynik odbiera `postep_planu`.

        Dopasowanie planu do puli wymaga CAŁEJ puli analiz (~20 s przy zimnym
        starcie): plan zna identyfikatory, a te trzeba znaleźć wśród ośmiu
        tysięcy utworów. Bez tego dopasowanie zwracałoby pustkę i wyglądałoby
        jak „plan pusty" zamiast „jeszcze nie wczytałem puli".
        """
        if self._plan_stan.get("stan") == "trwa":
            return {"blad": "wczytuję już plan — chwila"}
        self._plan_stan = {"stan": "trwa"}
        threading.Thread(target=self._wczytaj_plan_w_tle,
                         args=(str(sciezka),), daemon=True).start()
        return {"ruszylo": True}

    @_bezpiecznie
    def postep_planu(self) -> dict[str, Any]:
        return dict(self._plan_stan)

    def _wczytaj_plan_w_tle(self, sciezka: str) -> None:
        wynik = self._wczytaj_plan_teraz(sciezka)
        wynik["stan"] = "blad" if "blad" in wynik else "gotowe"
        self._plan_stan = wynik

    @_bezpiecznie
    def _wczytaj_plan_teraz(self, sciezka: str) -> dict[str, Any]:
        """Wczytaj wskazany plan i uczyń go bieżącym dla obu skór."""
        for a in self._pula():
            self._analizy.setdefault(a.track.track_id, a)
        wynik = plan.wczytaj(self._analizy, sciezka)
        if not wynik.get("kolejnosc"):
            wynik.setdefault("powod", "żaden utwór planu nie jest w puli")
            return wynik
        self._kolejnosc = list(wynik["kolejnosc"])
        self._plan_silnika = list(wynik.get("plan_silnika") or [])
        self._edycje_setu = list(wynik.get("edycje") or [])
        self._zapis_gotowy = None
        self._playlista_gotowa = None
        self._plan_cue = None
        # Plan z pliku nie niesie wag budowy, więc panel kandydatów musi
        # odmówić zamiast liczyć czymkolwiek — mówi to wprost. Wagi budowy
        # zerujemy TU RAZEM z kontekstem: zostawione, wchodziły do szwu planu
        # B z setu A i lądowały w werdykcie jako wagi, którymi B rzekomo
        # powstał. Werdykt ma mówić „nie znam", a nie cudzą liczbę.
        self._ctx_edycji = None
        self._wagi_budowy = None
        self._parametry_budowy = dict(wynik.get("parametry") or {})
        plan.WSKAZNIK.parent.mkdir(parents=True, exist_ok=True)
        plan.WSKAZNIK.write_text(
            json.dumps({"plan": str(sciezka)}, ensure_ascii=False),
            encoding="utf-8")
        dziennik.dopisz("wczytanie_planu", skora="gui", plan=str(sciezka),
                        utworow=len(self._kolejnosc),
                        pominietych=len([n for n in wynik.get("notki") or []
                                         if n.startswith("BRAK")]))
        wynik["utwory"] = [self._wiersz(t, self._analizy)
                           for t in self._kolejnosc]
        # notki puli (higiena, dokarmianie) — terminal je pokazuje przy O,
        # okno do 02.09 gubiło je w podmienionym `_budowa`
        wynik["notki"] = list(self._notki_puli) + list(wynik.get("notki") or [])
        return wynik

    # ------------------------------------------------------------- kolizje

    @_bezpiecznie
    def kolizje(self, track_id: str) -> dict[str, Any]:
        """Czy któryś pad wchodzi w cue, które w Rekordboxie już jest.

        Wołane z ekranu, nie dopiero przy zapisie: kolizja zobaczona przed
        kliknięciem jest ostrzeżeniem, kolizja zobaczona po nim jest awarią.
        """
        from dancelab.tui.cue_zapis import mapa_content_id

        pady = self.pady(track_id).get("pady") or {}
        if not pady:
            return {"kolizje": [], "sprawdzono": 0}

        try:
            mapa = mapa_content_id()
        except Exception as exc:                       # noqa: BLE001
            return {"blad": f"nie odczytałem bazy Rekordboxa: {exc}",
                    "kolizje": [], "sprawdzono": 0}

        analiza = self._analizy.get(track_id)
        sciezka = getattr(getattr(analiza, "track", None), "source_path", None)
        content_id = mapa.get(sciezka) if sciezka else None
        if content_id is None:
            return {"kolizje": [],
                    "uwaga": "tego utworu nie ma w bibliotece Rekordboxa — "
                             "nie mam z czym porównać",
                    "sprawdzono": len(pady)}
        return {"kolizje": [], "content_id": content_id,
                "sprawdzono": len(pady)}

    def _takty(self, track_id: str) -> list[float]:
        """Takty wg Rekordboxa — te same czerwone linie, które widzisz w jego
        oknie (terminal: `_cue_takty`). Pusta lista = brak w kolekcji albo
        baza nieodczytana; wtedy schodzimy na naszą siatkę i mówimy o tym."""
        analiza = self._analizy.get(track_id)
        if analiza is None:
            return []
        try:
            from dancelab.ingestion.rekordbox_siatka import downbeaty_dla_sciezki
            return list(downbeaty_dla_sciezki(analiza.track.source_path) or [])
        except Exception:                          # noqa: BLE001
            return []

    @_bezpiecznie
    def propozycje(self, track_id: str, silnik_ms: int | None = None) -> dict[str, Any]:
        """Gotowe czasy fraz (POCZĄTKI sekcji + propozycja silnika) — wszystko
        zmierzone, żadnych równych „co 32 bity". Frazy startują na początku
        taktu Rekordboxa, gdy go znamy (Janek 09.08)."""
        analiza = self._analizy.get(track_id)
        if analiza is None:
            return {"blad": f"nie mam analizy dla {track_id!r}"}
        return {"propozycje": [{"nazwa": n, "sec": round(float(s), 3)}
                               for n, s in cue.propozycje_czasu(
                                   analiza, silnik_ms, downbeaty=self._takty(track_id))]}

    def _przesun_na_czas(self, track_id: str, pad: str, sekundy: float,
                         typ_zdarzenia: str, **pola_dziennika: Any) -> dict[str, Any]:
        """Wspólny ogon „pad ma stanąć o TEJ sekundzie": kwantyzacja do taktu,
        przeliczenie na uderzenia, przesunięcie, dziennik. Ta sama droga, którą
        idzie terminal w `_cue_ustaw_czas` i `_cue_litera`."""
        from dancelab.tui.cue_podglad import _mmss
        analiza = self._analizy.get(track_id)
        if analiza is None:
            return {"blad": f"nie mam analizy dla {track_id!r}"}
        p = self._pady_bez_sladu(track_id).get("pady", {}).get(pad)
        if p is None:
            return {"blad": f"pad {pad} nie jest postawiony — nie ma czego przesuwać"}
        dlugosc = analiza.track.duration_sec or 0
        if dlugosc and sekundy > dlugosc:
            return {"blad": f"{_mmss(int(sekundy * 1000))} jest za końcem utworu "
                            f"({_mmss(int(dlugosc * 1000))}) — pad zostaje"}
        siatka = getattr(analiza, "beatgrid", None)
        cel, powod = edycje.czas_po_kwantyzacji(siatka, float(sekundy),
                                                self._takty(track_id))
        bpm = (getattr(siatka, "bpm", None) or 0) or 120.0
        beat = 60000.0 / bpm
        uderzenia = int(round((cel * 1000 - p["position_ms"]) / beat))
        self._zapis_gotowy = None
        nowa = edycje.przesun(self._edycje, track_id, pad, uderzenia, bpm,
                              p.get("silnik_ms"), int(p["position_ms"]))
        blad = dziennik.dopisz(typ_zdarzenia, skora="gui", track_id=track_id,
                               pad=pad, position_ms=nowa, **pola_dziennika,
                               **self._kontekst_propozycji(track_id, pad))
        wynik = self._z_dziennikiem(self.pady(track_id), blad)
        wynik["powod"] = f"pad {pad} → {_mmss(nowa)} · {powod}"
        wynik["position_ms"] = nowa
        return wynik

    @_bezpiecznie
    def ustaw_czas_pada(self, track_id: str, pad: str, tekst: str) -> dict[str, Any]:
        """T: wpisany czas („2:31", „2:31.5", „151") → pad na POCZĄTKU taktu.
        Kwantyzacja jest włączona zawsze — jak w terminalu (Janek 09.08:
        „68.1, a nie 68.2")."""
        sekundy = edycje.parsuj_czas(str(tekst))
        if sekundy is None:
            return {"blad": f"nie rozumiem czasu „{tekst}” — wpisz np. 2:31 albo 151"}
        return self._przesun_na_czas(track_id, pad, sekundy, "cue_czas_wpisany",
                                     wpisane_sec=sekundy)

    @_bezpiecznie
    def przenies_pad_na_glowice(self, track_id: str, pad: str) -> dict[str, Any]:
        """Druga litera tego samego pada: PRZENIEŚ go do głowicy odtwarzacza
        (skarga Janka 09.08: strzałki po jednym uderzeniu są nieintuicyjne
        przy dużych przeskokach). Odtwarzacz musi stać na TYM utworze."""
        analiza = self._analizy.get(track_id)
        if analiza is None:
            return {"blad": f"nie mam analizy dla {track_id!r}"}
        with self._zamek_audio:
            sciezka, pozycja = self._audio.sciezka, self._audio.pozycja()
        if sciezka != analiza.track.source_path:
            return {"blad": f"pad {pad}: najpierw P — odtwarzacz musi stać na TYM "
                            f"utworze, żeby przenieść pad w to miejsce"}
        return self._przesun_na_czas(track_id, pad, float(pozycja), "cue_przeniesienie")

    # --------------------------------------------------------- edycja setu

    def _sciezka(self, tid: str) -> str | None:
        a = self._analizy.get(tid)
        return getattr(getattr(a, "track", None), "source_path", None)

    def _po_edycji_setu(self) -> dict[str, Any]:
        """Wspólny ogon każdej edycji kolejności: unieważnij policzony zapis,
        oznacz propozycje padów jako nieaktualne, oddaj świeże wiersze."""
        self._zapis_gotowy = None
        # Policzona playlista też przestaje obowiązywać — jej liczby dotyczyły
        # setu sprzed tej zmiany. Stopień drugi i tak by odmówił, ale przycisk
        # nie ma prawa wyglądać na gotowy.
        self._playlista_gotowa = None
        self._plan_cue_nieaktualny = True
        filary = (self._ctx_edycji or {}).get("filary") or []
        return {"utwory": [self._wiersz(t, self._analizy)
                           for t in self._kolejnosc],
                "filary": [f for f in filary if f in self._kolejnosc]}

    @_bezpiecznie
    def zamknij_kandydatow(self) -> dict[str, Any]:
        """Esc: panel zamknięty, metadane kandydatów wygasają.

        Bez tego wybór zrobiony PÓŹNIEJ inną drogą (kiedyś: wstawienie wprost
        z Biblioteki) odziedziczyłby rangę z panelu, który DJ już zamknął —
        czyli dziennik przypisałby silnikowi wybór, którego silnik nie podał.
        Terminal robi to samo przy zamykaniu panelu (`app.py::_close_panel`).
        """
        self._kandydaci_meta = {}
        return {"zamkniete": True}

    def _zanotuj_edycje(self, typ: str, **pola: Any) -> str | None:
        """Każda edycja kolejności idzie w DWA miejsca, jak w terminalu:
        do historii setu (ląduje w pliku planu przy zapisie pod nazwą) i do
        dziennika decyzji. Zwraca ostrzeżenie dziennika albo None."""
        import time
        self._edycje_setu.append(
            {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "typ": typ, **pola})
        return dziennik.dopisz(typ, skora="gui", **pola)

    def _zrodlo_kandydata(self, tid: str) -> dict[str, Any]:
        """Skąd wziął się wstawiony utwór — z listy silnika czy z ręki DJ-a.

        Ta sama zasada co w terminalu (`app.py::_zrodlo_kandydata`): wybór bez
        metadanych panelu jest uczciwie opisany jako własny, nie zgadywany.
        """
        return dziennik.zrodlo_kandydata(self._kandydaci_meta, tid)

    @_bezpiecznie
    def kandydaci(self, pozycja: int, tryb: str = "smart",
                  cel: str = "podmiana") -> dict[str, Any]:
        """Rusz liczenie kandydatów W TLE. Wynik odbiera `postep_kandydatow`.

        Zmierzone 01.09 na prawdziwej puli: 8143 kandydatów to **około
        czterech sekund**. W pywebview wywołanie z JS jest synchroniczne, więc
        liczenie wprost zamroziłoby okno na te cztery sekundy — dokładnie ten
        sam powód, dla którego budowa setu chodzi w wątku.
        """
        if self._kandydaci_stan.get("stan") == "trwa":
            return {"blad": "liczę już kandydatów — chwila"}
        gotowe = self._kandydaci_teraz(pozycja, tryb, cel)
        if "blad" in gotowe:
            return gotowe                        # odmowy wracają natychmiast
        self._kandydaci_stan = {"stan": "trwa"}
        threading.Thread(target=self._kandydaci_w_tle,
                         args=(int(pozycja), tryb, cel), daemon=True).start()
        return {"ruszylo": True}

    @_bezpiecznie
    def postep_kandydatow(self) -> dict[str, Any]:
        """Stan liczenia kandydatów. Widok odpytuje, dopóki trwa."""
        return dict(self._kandydaci_stan)

    def _kandydaci_w_tle(self, pozycja: int, tryb: str, cel: str) -> None:
        wynik = self._kandydaci_licz(pozycja, tryb, cel)
        wynik["stan"] = "blad" if "blad" in wynik else "gotowe"
        self._kandydaci_stan = wynik

    def _kandydaci_teraz(self, pozycja: int, tryb: str,
                         cel: str) -> dict[str, Any]:
        """Same warunki wstępne — sprawdzane przed wątkiem, żeby odmowa
        wracała od razu, a nie po sekundzie odpytywania."""
        if not self._kolejnosc:
            return {"blad": "najpierw zbuduj set — nie ma szczelin bez setu"}
        ctx = self._ctx_edycji
        if ctx is None or ctx.get("wagi") is None:
            return {"blad": ("plan wczytany z pliku nie niesie wag budowy — "
                             "zbuduj set w oknie, żeby dostać sugestie")}
        idx = int(pozycja)
        if not (0 <= idx < len(self._kolejnosc)):
            return {"blad": f"pozycja {idx + 1} poza setem "
                            f"({len(self._kolejnosc)} pozycji)"}
        return {}

    @_bezpiecznie
    def _kandydaci_licz(self, pozycja: int, tryb: str = "smart",
                        cel: str = "podmiana") -> dict[str, Any]:
        """Kandydaci do szczeliny: podmiana `pozycja` albo dopisanie ZA nią.

        Oceniani dokładnie tym, czym set powstał (wagi, łuk, planer, okno
        tempa, kotwica z budowy) — sugestie nie mogą mieć innego gustu niż
        set. Tryby bpm/tonacja to oficjalne tryby plannera, bez kotwicy.
        """
        if not self._kolejnosc:
            return {"blad": "najpierw zbuduj set — nie ma szczelin bez setu"}
        ctx = self._ctx_edycji
        if ctx is None or ctx.get("wagi") is None:
            return {"blad": ("plan wczytany z pliku nie niesie wag budowy — "
                             "zbuduj set w oknie, żeby dostać sugestie")}
        idx = int(pozycja)
        if not (0 <= idx < len(self._kolejnosc)):
            return {"blad": f"pozycja {idx + 1} poza setem "
                            f"({len(self._kolejnosc)} pozycji)"}
        from dancelab.decision import slot_suggest
        from dancelab.stan import filary as F

        energia, rozpietosc = F.energia_do_oceny(self._analizy)
        if tryb == "bpm":
            planer, kotwica = "bpm", None
        elif tryb == "harmonic":
            planer, kotwica = "harmonic", None
        else:
            planer, kotwica = ctx["planer"], ctx.get("kotwica_centroid")
        fn = (slot_suggest.suggest_for_slot if cel == "podmiana"
              else slot_suggest.suggest_for_insertion)
        sugestie = fn(self._analizy, self._kolejnosc, idx, k=10,
                      weights=ctx["wagi"], arc=ctx["luk"], planner_mode=planer,
                      energy=energia, energy_range=rozpietosc,
                      bpm_min=ctx["bpm_min"], bpm_max=ctx["bpm_max"],
                      anchor=kotwica)
        self._kandydaci_meta = {}
        wiersze = []
        for ranga, s in enumerate(sugestie, start=1):
            w = self._wiersz(s.track_id, self._analizy)
            w.update({"score": round(float(s.score), 4), "why": s.why,
                      "ranga": ranga})
            wiersze.append(w)
            # ranga = miejsce kandydata na liście; bez niej nie wiadomo, czy
            # ranking silnika cokolwiek wnosi (pytanie otwarte po ślepym
            # odsłuchu, gdzie 133/158 przejść miało jeden maksymalny wynik)
            self._kandydaci_meta[s.track_id] = {
                "zrodlo": "panel_silnika", "ranga": ranga,
                "score": round(float(s.score), 4), "tryb": tryb,
                "kandydatow": len(sugestie)}
        if not wiersze:
            return {"kandydaci": [], "tryb": tryb, "cel": cel,
                    "uwaga": "brak kandydatów do tej szczeliny "
                             "(okno tempa? pula?)"}
        return {"kandydaci": wiersze, "tryb": tryb, "cel": cel}

    @_bezpiecznie
    def podmien(self, pozycja: int, track_id: str) -> dict[str, Any]:
        """Podmiana jednej pozycji — reszta setu zamrożona z konstrukcji."""
        idx = int(pozycja)
        if not (0 <= idx < len(self._kolejnosc)):
            return {"blad": f"pozycja {idx + 1} poza setem"}
        if track_id not in self._analizy:
            return {"blad": f"nie mam analizy dla {track_id!r}"}
        if track_id in self._kolejnosc:
            return {"blad": "ten utwór już jest w secie"}
        stary = self._kolejnosc[idx]
        self._kolejnosc[idx] = track_id
        blad = self._zanotuj_edycje("podmiana", pozycja=idx + 1,
            **{"out": self._sciezka(stary), "in": self._sciezka(track_id)},
            **self._zrodlo_kandydata(track_id))
        self._kandydaci_meta = {}
        return self._z_dziennikiem(self._po_edycji_setu(), blad)

    @_bezpiecznie
    def dopisz_utwor(self, po_pozycji: int, track_id: str) -> dict[str, Any]:
        """Dopisanie ZA wskazaną pozycją — nic nie wypada."""
        idx = int(po_pozycji)
        if not (0 <= idx < len(self._kolejnosc)):
            return {"blad": f"pozycja {idx + 1} poza setem"}
        if track_id not in self._analizy:
            return {"blad": f"nie mam analizy dla {track_id!r}"}
        if track_id in self._kolejnosc:
            return {"blad": "ten utwór już jest w secie"}
        self._kolejnosc.insert(idx + 1, track_id)
        blad = self._zanotuj_edycje("dopisanie", pozycja=idx + 2,
            **{"in": self._sciezka(track_id)},
            **self._zrodlo_kandydata(track_id))
        self._kandydaci_meta = {}
        return self._z_dziennikiem(self._po_edycji_setu(), blad)

    @_bezpiecznie
    def wytnij(self, pozycja: int) -> dict[str, Any]:
        """Wycięcie pozycji. Filar wycina się tak samo — ale mówi to wprost."""
        idx = int(pozycja)
        if not (0 <= idx < len(self._kolejnosc)):
            return {"blad": f"pozycja {idx + 1} poza setem"}
        tid = self._kolejnosc.pop(idx)
        filar = tid in ((self._ctx_edycji or {}).get("filary") or [])
        blad = self._zanotuj_edycje("ciecie", pozycja=idx + 1,
                               out=self._sciezka(tid), filar=filar)
        wynik = self._po_edycji_setu()
        if filar:
            wynik["uwaga"] = "wyciąłeś FILAR — set stracił jeden z punktów, " \
                             "na których był rozpięty"
        return self._z_dziennikiem(wynik, blad)

    @_bezpiecznie
    def przesun_utwor(self, pozycja: int, kierunek: int) -> dict[str, Any]:
        """Zamiana miejscami z sąsiadem (±1). Brzeg setu to nie błąd."""
        idx = int(pozycja)
        j = idx + (1 if int(kierunek) > 0 else -1)
        if not (0 <= idx < len(self._kolejnosc)):
            return {"blad": f"pozycja {idx + 1} poza setem"}
        if not (0 <= j < len(self._kolejnosc)):
            wynik = self._po_edycji_setu()
            wynik["uwaga"] = "brzeg setu — nie ma dokąd przesunąć"
            return wynik
        self._kolejnosc[idx], self._kolejnosc[j] = \
            self._kolejnosc[j], self._kolejnosc[idx]
        blad = self._zanotuj_edycje("przesuniecie", z=idx + 1, na=j + 1,
                               utwor=self._sciezka(self._kolejnosc[j]))
        wynik = self._po_edycji_setu()
        wynik["na"] = j
        return self._z_dziennikiem(wynik, blad)

    # -------------------------------------------------------- zapis cue

    @_bezpiecznie
    def zapis_stan(self) -> dict[str, Any]:
        """Czy jest co zapisywać i czy wolno. Widok pyta o to przed rysowaniem
        przycisku, żeby nie proponować kroku, który i tak się nie uda."""
        return {
            "rekordbox_otwarty": zapis_cue.rekordbox_otwarty(),
            "set": len(self._kolejnosc),
            "propozycje": self._plan_cue is not None,
            "policzone": self._zapis_gotowy is not None,
            "playlista_policzona": self._playlista_gotowa is not None,
        }

    # ---------------------------------------------------------- gatunki

    @_bezpiecznie
    def gatunki(self, wybrane: str = "") -> dict[str, Any]:
        """Ctrl+G: gatunki Beatportu OBECNE w puli, z liczbą utworów i
        znacznikiem wyboru. Liczone na puli budowy (dokarmionej tagami RB),
        więc pierwsze wywołanie może potrzebować jej wczytania — wtedy
        odpowiada „ruszyło" i widok pyta `postep_gatunkow`."""
        if self._analizy_pula is None:
            if self._gatunki_stan.get("stan") != "trwa":
                self._gatunki_stan = {"stan": "trwa"}
                threading.Thread(target=self._gatunki_w_tle, args=(wybrane,),
                                 daemon=True).start()
            return {"ruszylo": True}
        return self._gatunki_teraz(wybrane)

    @_bezpiecznie
    def postep_gatunkow(self) -> dict[str, Any]:
        return dict(self._gatunki_stan)

    def _gatunki_w_tle(self, wybrane: str) -> None:
        try:
            self._pula()
            wynik = self._gatunki_teraz(wybrane)
        except Exception as exc:                       # noqa: BLE001
            wynik = {"blad": f"gatunków nie policzyłem: {exc}"}
        wynik["stan"] = "blad" if "blad" in wynik else "gotowe"
        self._gatunki_stan = wynik

    def _gatunki_teraz(self, wybrane: str) -> dict[str, Any]:
        from dancelab.tui import gatunki as G
        pula = self._analizy_pula or []
        if not G.policz(pula):
            return {"blad": "żaden utwór w puli nie ma gatunku — otaguj "
                            "w Rekordboksie albo wpisz ręcznie"}
        mam, wszystkich, bez = G.pokrycie(pula)
        return {"sekcje": [{"sekcja": s, "gatunki": [
                    {"nazwa": n, "ile": ile, "wybrany": G.jest_wybrany(wybrane, n)}
                    for n, ile in poz]} for s, poz in G.policz(pula)],
                "mam": mam, "wszystkich": wszystkich, "bez_tagu": bez}

    @_bezpiecznie
    def przelacz_gatunek(self, wybrane: str, gatunek: str) -> dict[str, Any]:
        """Enter na gatunku: dopisz albo zdejmij w polu briefu — reguła
        rozdzielania po przecinkach mieszka w `tui/gatunki.py`, nie tutaj."""
        from dancelab.tui import gatunki as G
        return {"wybrane": G.przelacz(wybrane or "", gatunek)}

    # ------------------------------------------------- szkic z filarów

    @_bezpiecznie
    def szkic_z_filarow(self, formularz: dict[str, Any]) -> dict[str, Any]:
        """G: filary aktywnej playlisty → tabela setu jako SZKIC (⚑ złote).

        CELOWO BEZ automatycznej budowy (Janek 05.08: „przez to omijamy całą
        sekcję briefu") — DJ uzupełnia formularz i dopiero B buduje wokół
        nich. Ta sama reguła i te same odmowy co `action_build_from_filary`."""
        from dancelab.core.config import load_config, load_weights
        from dancelab.storage.repositories import FileAnalysisRepository
        from dancelab.tui.user_store import MIN_FILARY, filary_wpisy

        wpisy = filary_wpisy(self._stan_uzytkownika())
        if len(wpisy) < MIN_FILARY:
            return {"blad": f"do budowy z filarów trzeba minimum {MIN_FILARY} "
                            f"(masz {len(wpisy)}) — klawisz F na liście utworów zaznacza"}
        try:
            par = budowa.Parametry.z_formularza(formularz or {})
        except budowa.OdmowaBudowy as exc:
            return {"blad": f"popraw formularz: {exc}", "pole": "parametry"}
        repo = FileAnalysisRepository(self._katalog)
        ids, notki = [], []
        for e in wpisy:
            tid = e.get("track_id")
            try:
                self._analizy.setdefault(tid, repo.get(tid))
                ids.append(tid)
            except Exception:                          # noqa: BLE001
                notki.append(f"FILAR nieobecny w puli (pominięty): "
                             f"{(e.get('path') or tid or '?')[-48:]}")
        if len(ids) < MIN_FILARY:
            return {"blad": f"po dopasowaniu do puli zostało {len(ids)} filarów "
                            f"(minimum {MIN_FILARY})", "notki": notki}
        self._kolejnosc = list(ids)
        self._plan_silnika, self._edycje_setu = [], []
        self._plan_cue, self._zapis_gotowy, self._playlista_gotowa = None, None, None
        self._parametry_budowy = {"minuty": par.minuty, "bpm_min": par.bpm_min,
                                  "bpm_max": par.bpm_max, "dj": par.dj}
        self._ctx_edycji = {
            "wagi": load_weights(load_config("configs/default.yaml").weights_file),
            "luk": par.luk, "planer": par.planer, "bpm_min": par.bpm_min,
            "bpm_max": par.bpm_max, "kotwica_centroid": None, "filary": list(ids),
            "odcisk": None}
        self._odcisk_zapisany = False
        wynik = self._po_edycji_setu()
        wynik["notki"] = notki + [f"SZKIC: {len(ids)} filarów (⚑) — wybierz tryb "
                                  f"filarów, uzupełnij brief i naciśnij B"]
        return wynik

    # ------------------------------------------------------------- DJ-e

    @_bezpiecznie
    def djs(self) -> dict[str, Any]:
        """Kotwice brzmienia: grupy po ZMIERZONYM brzmieniu, nie po gatunku.

        Grupowanie robi `grupy_dj.grupuj` (te same klastry co w terminalu);
        bez biblioteki do grupowania zwraca JEDNĄ grupę „wszyscy" zamiast
        zmyślonego podziału, i tak też to pokazujemy.
        """
        from dancelab.decision.anchors import MOJE_ULUBIONE, load_anchor_book
        from dancelab.tui import grupy_dj as G
        from dancelab.tui.user_store import kolekcja_djow

        try:
            ksiega = load_anchor_book()
        except Exception as exc:                       # noqa: BLE001
            # brak księgi to STAN, nie awaria — pole „brzmi jak" nadal działa
            return {"blad": f"kotwice niedostępne: {exc}"}

        kolekcja = kolekcja_djow(self._stan_uzytkownika())
        grupy = []
        for etykieta, czlonkowie in G.grupuj(ksiega["djs"]):
            grupy.append({
                "etykieta": etykieta,
                "djs": [{"nazwa": dj, "wektorow": n,
                         # mediana skoku: im niżej, tym odważniej ten DJ
                         # przeskakuje między utworami (zmierzone na jego setach)
                         "skok": skok,
                         "odwaga": (None if skok is None else
                                    "odważny" if skok < 0.70 else
                                    "gładki" if skok > 0.80 else "pośrodku"),
                         "w_kolekcji": dj in kolekcja}
                        for dj, n, skok in czlonkowie],
            })
        return {"grupy": grupy, "kolekcja": kolekcja,
                "moje_ulubione": MOJE_ULUBIONE,
                "ulubionych_utworow": len(
                    self._stan_uzytkownika().get("ulubione_utwory", []))}

    @_bezpiecznie
    def przelacz_kolekcje_dj(self, dj: str) -> dict[str, Any]:
        """DJ w kolekcji dostaje pierwszeństwo w polu „brzmi jak…"."""
        from dancelab.tui.user_store import przelacz_kolekcje_dj
        teraz = przelacz_kolekcje_dj(self._stan_uzytkownika(), dj)
        self._zapisz_stan_uzytkownika()
        return {"w_kolekcji": bool(teraz), "dj": dj}

    # ----------------------------------------------- narzędzia utworu

    @_bezpiecznie
    def info_utworu(self, track_id: str) -> dict[str, Any]:
        """Karta INFO: metadane z NAZWANYM źródłem każdej liczby.

        Ten sam tekst, który składa terminal (`stan.biblioteka.karta_info`) —
        silnik osobno, Rekordbox osobno, bo tempo z Rekordboxa jest
        niezależnym sędzią naszego pomiaru, a nie jego potwierdzeniem.
        """
        from dancelab.stan.biblioteka import karta_info

        analiza = self._analizy.get(track_id)
        if analiza is None:
            from dancelab.storage.repositories import FileAnalysisRepository
            try:
                analiza = FileAnalysisRepository(self._katalog).get(track_id)
                self._analizy[track_id] = analiza
            except Exception as exc:                   # noqa: BLE001
                return {"blad": f"nie mam analizy dla {track_id!r}: {exc}"}

        rb, rb_notka = None, None
        try:
            from dancelab.ingestion.rekordbox_lookup import track_in_rekordbox
            rb = track_in_rekordbox(analiza.track.source_path)
        except Exception as exc:                       # noqa: BLE001
            # karta ma powiedzieć, czego NIE WIE, zamiast milczeć
            rb_notka = f"master.db nieodczytany: {exc}"
        return {"tekst": karta_info(analiza.track, rb, rb_notka),
                "track_id": track_id}

    @_bezpiecznie
    def porownaj_pare(self, pozycja: int) -> dict[str, Any]:
        """Fakty o szwie między pozycją a następną — bez odsłuchu.

        Liczy `seam_preview.zaplanuj_szew`, ten sam, który rysuje szew
        w terminalu. Ostatni utwór nie ma następnika i to nie jest błąd.
        """
        idx = int(pozycja)
        if not (0 <= idx < len(self._kolejnosc)):
            return {"blad": f"pozycja {idx + 1} poza setem"}
        if idx + 1 >= len(self._kolejnosc):
            return {"blad": "ostatni utwór nie ma następnika — "
                            "porównanie dotyczy PARY"}
        wagi = (self._ctx_edycji or {}).get("wagi")
        if wagi is None:
            return {"blad": "plan wczytany z pliku nie niesie wag budowy — "
                            "zbuduj set w oknie, żeby porównać parę"}
        a = self._analizy.get(self._kolejnosc[idx])
        b = self._analizy.get(self._kolejnosc[idx + 1])
        if a is None or b is None:
            return {"blad": "brakuje analizy jednego z utworów pary"}

        from dancelab.stan import szew as SZ
        plan_szwu = SZ.zaplanuj_szew(a, b, wagi)
        return {
            "pozycja": idx,
            "a": self._wiersz(a.track.track_id, self._analizy),
            "b": self._wiersz(b.track.track_id, self._analizy),
            "uderzen": plan_szwu["beats"],
            "bpm": plan_szwu["bpm"],
            "cue_a_sec": plan_szwu["cue_a_sec"],
            "cue_b_sec": plan_szwu["cue_b_sec"],
        }

    # ---------------------------------------- playlisty, filary, ulubione

    def _stan_uzytkownika(self) -> dict:
        """Stan DJ-a wczytany raz na sesję okna. Ten sam plik, który czyta
        terminal — obie skóry mają widzieć te same filary i playlisty."""
        from dancelab.tui.user_store import load_state
        if self._stan_dja is None:
            self._stan_dja = load_state(self._katalog)
        return self._stan_dja

    def _zapisz_stan_uzytkownika(self) -> None:
        from dancelab.tui.user_store import save_state
        save_state(self._stan_uzytkownika(), self._katalog)

    def _wpis_spisu(self, track_id: str) -> dict[str, Any] | None:
        """Wpis biblioteki po identyfikatorze. Indeks budowany na żądanie.

        Indeks NIE jest polem ustawianym przy wczytaniu spisu: `_spis` bywa
        podstawiany wprost (testy, a jutro inne źródło puli), a dwa pola,
        które mogą się rozjechać, rozjadą się — tytuł filara wychodził wtedy
        jako „?". Kluczem przebudowy jest tożsamość listy plus jej długość,
        więc i podmiana, i dopisanie w miejscu trafiają w przebudowę.
        """
        znacznik = (id(self._spis), len(self._spis))
        if self._po_id_dla != znacznik:
            self._po_id = {u["track_id"]: u for u in self._spis}
            self._po_id_dla = znacznik
        return self._po_id.get(track_id)

    def _sciezka_utworu(self, track_id: str) -> str:
        """Ścieżka pliku utworu — filary trzymają ID ORAZ ścieżkę, żeby
        przeżyć przebudowę katalogu analiz."""
        s = self._sciezka(track_id)
        if s:
            return s
        return (self._wpis_spisu(track_id) or {}).get("sciezka") or ""

    @_bezpiecznie
    def playlisty(self) -> dict[str, Any]:
        """Playlisty DJ-a z liczbą filarów. Filary żyją W PLAYLISTACH
        (decyzja z 11.08), więc bez wybranej playlisty nie ma gdzie ich wpisać.
        """
        from dancelab.tui.user_store import ROLE_FILARA
        stan = self._stan_uzytkownika()
        return {
            "playlisty": [{"nazwa": p.get("nazwa", "—"),
                           "filarow": len(p.get("filary") or []),
                           "kotwica": p.get("kotwica")}
                          for p in stan.get("playlisty", [])],
            "aktywna": stan.get("aktywna_playlista"),
            "role": ROLE_FILARA,
            "tryb_filarow": stan.get("tryb_filarow", "rozstaw"),
        }

    @_bezpiecznie
    def nowa_playlista(self, nazwa: str) -> dict[str, Any]:
        from dancelab.tui.user_store import nowa_playlista
        if not (nazwa or "").strip():
            return {"blad": "playlista bez nazwy jest nie do odnalezienia"}
        nowa_playlista(self._stan_uzytkownika(), nazwa.strip())
        self._zapisz_stan_uzytkownika()
        return self.playlisty()

    @_bezpiecznie
    def wybierz_playliste(self, indeks: int) -> dict[str, Any]:
        stan = self._stan_uzytkownika()
        ile = len(stan.get("playlisty", []))
        if not (0 <= int(indeks) < ile):
            return {"blad": f"nie ma playlisty numer {int(indeks) + 1}"}
        stan["aktywna_playlista"] = int(indeks)
        self._zapisz_stan_uzytkownika()
        return self.playlisty()

    @_bezpiecznie
    def filary(self) -> dict[str, Any]:
        """Filary aktywnej playlisty, z rolami i tytułami do wyświetlenia."""
        from dancelab.tui.user_store import filary_wpisy
        import pathlib as _p

        stan = self._stan_uzytkownika()
        wpisy = []
        for e in filary_wpisy(stan):
            tid = e.get("track_id")
            spis = self._wpis_spisu(tid)
            wpisy.append({
                "track_id": tid,
                "rola": e.get("rola", ""),
                "tytul": ((spis or {}).get("tytul")
                          or _p.Path(e.get("path") or "?").stem[:48]),
            })
        return {"filary": wpisy,
                "tryb_filarow": stan.get("tryb_filarow", "rozstaw"),
                "aktywna": stan.get("aktywna_playlista")}

    @_bezpiecznie
    def ustaw_filar(self, track_id: str, rola: str = "") -> dict[str, Any]:
        """Przypnij utwór jako filar z rolą. Odmowa mówi dlaczego — limit
        dziesięciu i brak playlisty to dwie różne przeszkody."""
        from dancelab.tui.user_store import ustaw_filar
        udalo, powod = ustaw_filar(self._stan_uzytkownika(), track_id,
                                   self._sciezka_utworu(track_id), rola)
        if not udalo:
            return {"blad": powod or "filara nie wpisałem"}
        self._zapisz_stan_uzytkownika()
        wynik = self.filary()
        wynik["ustawiony"] = track_id
        return wynik

    @_bezpiecznie
    def zdejmij_filar(self, track_id: str) -> dict[str, Any]:
        from dancelab.tui.user_store import zdejmij_filar
        udalo = zdejmij_filar(self._stan_uzytkownika(), track_id,
                              self._sciezka_utworu(track_id))
        if not udalo:
            return {"blad": "ten utwór nie jest filarem aktywnej playlisty"}
        self._zapisz_stan_uzytkownika()
        return self.filary()

    @_bezpiecznie
    def ustaw_tryb_filarow(self, tryb: str) -> dict[str, Any]:
        """rozstaw | rama | podpory — trzy sposoby użycia filarów przy budowie.
        """
        if tryb not in ("rozstaw", "rama", "podpory"):
            return {"blad": f"nieznany tryb filarów: {tryb!r}"}
        self._stan_uzytkownika()["tryb_filarow"] = tryb
        self._zapisz_stan_uzytkownika()
        return {"tryb_filarow": tryb}

    @_bezpiecznie
    def przelacz_ulubiony(self, track_id: str) -> dict[str, Any]:
        from dancelab.tui.user_store import toggle_track
        teraz, powod = toggle_track(self._stan_uzytkownika(), "ulubione_utwory",
                                    track_id, self._sciezka_utworu(track_id))
        if powod:
            return {"blad": powod}
        self._zapisz_stan_uzytkownika()
        return {"ulubiony": bool(teraz), "track_id": track_id}

    @_bezpiecznie
    def ulubione(self) -> dict[str, Any]:
        stan = self._stan_uzytkownika()
        return {"ulubione": [e.get("track_id")
                             for e in stan.get("ulubione_utwory", [])]}

    # ------------------------------------------------------------- dźwięk
    #
    # Trzy zasady, wszystkie z terminala i wszystkie twarde:
    #  1. dźwięk startuje WYŁĄCZNIE z jawnego klawisza/kliknięcia — nigdy
    #     z automatu, nigdy z weryfikacji, nigdy przy wczytaniu ekranu;
    #  2. utwór bez pliku na dysku (strumień) dostaje ZDANIE o sobie, zanim
    #     odtwarzacz zostanie dotknięty — nie błąd ffplaya po fakcie;
    #  3. jeden proces na okno: nowy odsłuch zabija poprzedni.

    def _do_grania(self, track_id: str) -> tuple[Any, str | None]:
        """Analiza i powód odmowy. Odmowa wygrywa — nie zwracamy obu."""
        analiza = self._analizy.get(track_id)
        if analiza is None:
            from dancelab.storage.repositories import FileAnalysisRepository
            try:
                analiza = FileAnalysisRepository(self._katalog).get(track_id)
            except Exception:                          # noqa: BLE001
                return None, f"nie mam analizy utworu {track_id!r}"
            self._analizy[track_id] = analiza
        return analiza, budowa.bez_pliku(analiza.track)

    @staticmethod
    def _bpm(analiza) -> float | None:
        """Tempo do skoków „co N uderzeń". Siatka silnika przed metadanymi —
        to ona wyznacza uderzenia, po których skaczemy."""
        siatka = getattr(analiza, "beatgrid", None)
        return getattr(siatka, "bpm", None) or analiza.track.bpm_estimate

    def _graj(self, track_id: str, pad: str = "") -> dict[str, Any]:
        """P na utworze: gra→pauza, ten sam→wznowienie, inny→od zera.

        Z padem: start od TEGO pada (ffplay umie wejść w środek utworu).
        Bez pada: od zera — wtedy gra afplay, bo startuje natychmiast, a
        ffplay potrzebuje pół sekundy na inicjalizację audio.
        """
        analiza, powod = self._do_grania(track_id)
        if powod:
            return {"blad": powod, "bez_pliku": True}
        sciezka = analiza.track.source_path
        bpm = self._bpm(analiza)

        # Pauza dotyczy TEGO, co gra. Drugie P na grającym utworze zatrzymuje;
        # P na innym utworze przełącza, a nie zatrzymuje tamten w ciszy.
        if self._audio.gra() and self._audio.sciezka == sciezka:
            self._audio.stop()
            return dict(self._stan_odtwarzania(), akcja="pauza")

        if pad:
            pady = self._pady_bez_sladu(track_id).get("pady") or {}
            p = pady.get(pad)
            if p is None:
                return {"blad": f"utwór nie ma pada {pad}"}
            blad = self._audio.graj_od(sciezka, bpm,
                                       p["position_ms"] / 1000.0)
            akcja, skad = "start", f"od pada {pad}"
        elif self._audio.sciezka == sciezka and self._audio.pozycja() > 0:
            blad = self._audio.graj_od(sciezka, bpm, self._audio.pozycja())
            akcja, skad = "wznowienie", "od miejsca pauzy"
        else:
            blad = self._audio.graj_od_zera(sciezka, bpm)
            akcja, skad = "start", "od zera"
        if blad:
            return {"blad": f"odsłuch nie wyszedł: {blad}"}
        self._gra_co = {"rodzaj": "utwor", "track_id": track_id,
                        "opis": self._tytul(track_id), "skad": skad}
        return dict(self._stan_odtwarzania(), akcja=akcja)

    def _stop_dzwieku(self) -> dict[str, Any]:
        """Zatrzymanie z zapamiętaniem miejsca — kolejne P wznawia stąd.

        Szew jest wyjątkiem i musi nim być: odtwarzacz pamięta ścieżkę PLIKU
        szwu z cache, a P dotyczy utworu — więc po pauzie szwu żadne P go nie
        wznowi. Zapamiętana pozycja obiecywałaby wtedy coś, czego nie ma
        („pauza — wznawia od tego miejsca"), a P puszczałoby utwór A od zera.
        Zatrzymanie szwu jest ZATRZYMANIEM.
        """
        gralo = self._audio.stop()
        if (self._gra_co or {}).get("rodzaj") == "szew":
            self._audio.zapomnij_pozycje()
            self._gra_co = None
            self._szew_stan = {"stan": "bezczynny"}
            return dict(self._stan_odtwarzania(), akcja="stop")
        return dict(self._stan_odtwarzania(), akcja="pauza" if gralo else "cisza")

    def _skocz(self, uderzenia: int) -> dict[str, Any]:
        """±N uderzeń wg tempa utworu, nie wg sekund. Restart procesu daje
        0,1–0,2 s ciszy — to podgląd, nie miks na żywo."""
        _, blad = self._audio.skocz(int(uderzenia))
        if blad:
            return {"blad": blad}
        return dict(self._stan_odtwarzania(), akcja="skok")

    def _stan_odtwarzania(self) -> dict[str, Any]:
        """Odpytywane co ćwierć sekundy, gdy coś gra — stąd głowica na fali.

        Tu, i tylko tu, sprawdzamy, czy utwór skończył się SAM. Bez tego
        koniec utworu wygląda identycznie jak pauza: proces nie żyje, pozycja
        stoi, a głowica zamarza w miejscu, w którym nic już nie gra.
        """
        skonczony = self._audio.skonczyl_sie()
        if skonczony is not None:
            koniec = self._gra_co or {}
            self._gra_co = None
            return {"gra": False, "pozycja_sec": 0.0, "skonczyl_sie": True,
                    "rodzaj": koniec.get("rodzaj"),
                    "track_id": koniec.get("track_id"), "opis": ""}
        co = self._gra_co or {}
        tid = co.get("track_id")
        analiza = self._analizy.get(tid) if tid else None
        return {
            "gra": self._audio.gra(),
            "pozycja_sec": round(self._audio.pozycja(), 2),
            # szew ma własną długość; utwór — swoją z analizy
            "dlugosc_sec": (co.get("dlugosc_sec")
                            or (analiza.track.duration_sec if analiza else None)),
            "rodzaj": co.get("rodzaj"),
            "track_id": tid,
            "para": co.get("para"),
            "opis": co.get("opis", ""),
            "skad": co.get("skad", ""),
            "skonczyl_sie": False,
        }

    @_bezpiecznie
    def zamknij(self) -> None:
        """Okno się zamyka — proces audio ma zginąć razem z nim."""
        with self._zamek_audio:
            self._audio.stop()

    # --------------------------------------------------------------- szew

    @_bezpiecznie
    def graj_szew(self, track_id: str, nastepny_id: str = "",
                  z_padow: bool = False, pad: str = "") -> dict[str, Any]:
        """Zszyj parę i posłuchaj przejścia. Render leci w wątku.

        Dwa różne szwy tej samej pary, oba prawdziwe i nazwane:
        `z_padow=True` zszywa TWOJE pady (co usłyszysz na sprzęcie po zapisie
        cue), `z_padow=False` bierze propozycję silnika (okna mix-out/mix-in).
        """
        if self._szew_stan.get("stan") == "trwa":
            return {"blad": "szew już się renderuje — chwila"}
        drugi = nastepny_id or self._nastepny_w_secie(track_id)
        if not drugi:
            return {"blad": "nie ma następnego utworu — szew potrzebuje pary"}
        for tid in (track_id, drugi):
            analiza, powod = self._do_grania(tid)
            if powod:
                return {"blad": f"szew: {powod}", "bez_pliku": True}
        if z_padow:
            brak = [t for t in (track_id, drugi)
                    if not (self._pady_bez_sladu(t).get("pady") or {})]
            if brak:
                czego = ("tego utworu" if brak[0] == track_id
                         else "następnego utworu")
                return {"blad": f"{czego} nie ma ani jednego pada — postaw pad, "
                                f"wtedy zszyję parę z Twoich padów"}
        self._szew_stan = {"stan": "trwa"}
        threading.Thread(target=self._szew_w_tle,
                         args=(track_id, drugi, bool(z_padow), pad or None),
                         daemon=True).start()
        return {"ruszylo": True}

    def _nastepny_w_secie(self, track_id: str) -> str | None:
        """Następny utwór SETU. Poza setem szew nie ma z czego powstać —
        para „ten i przypadkowy z biblioteki" nie jest przejściem."""
        if track_id in self._kolejnosc:
            i = self._kolejnosc.index(track_id)
            if i + 1 < len(self._kolejnosc):
                return self._kolejnosc[i + 1]
        return None

    def _szew_w_tle(self, tid_a: str, tid_b: str, z_padow: bool,
                    wybrany: str | None = None) -> None:
        """Render jest CICHY — do pliku w cache. Dźwięku tu nie ma i nie może
        być: granie ma być skutkiem gestu DJ-a, nie skutkiem końca renderu."""
        try:
            a, b = self._analizy[tid_a], self._analizy[tid_b]
            if z_padow:
                pady_a = self._pady_bez_sladu(tid_a)["pady"]
                pady_b = self._pady_bez_sladu(tid_b)["pady"]
                # ta sama reguła co w terminalu, z tego samego miejsca —
                # łącznie z tym, że ZAZNACZONY pad jest wyjściem
                pad_a, p_a, pad_b, p_b = szew.wybierz_pady_szwu(
                    pady_a, pady_b, wybrany)
                info = szew.zbuduj_szew_z_padow(
                    a, b,
                    cue_a_sec=p_a["position_ms"] / 1000.0,
                    cue_b_sec=p_b["position_ms"] / 1000.0)
                etykieta = f"szew z Twoich padów ({pad_a} → {pad_b})"
            else:
                info = szew.zbuduj_szew(a, b, self._wagi_szwu())
                etykieta = "szew silnika"
        except Exception as exc:                       # noqa: BLE001
            self._szew_stan = {"stan": "blad",
                               "blad": f"szew nie wyszedł: {exc}"}
            return
        self._szew_stan = {"stan": "gotowe", "info": info, "etykieta": etykieta,
                           "para": [tid_a, tid_b]}

    def _wagi_szwu(self):
        """Wagi, którymi silnik szukał okien przejścia. Te z budowy, gdy set
        powstał w tym oknie; domyślne, gdy plan przyszedł z pliku."""
        if self._wagi_budowy is not None:
            return self._wagi_budowy
        from dancelab.core.config import load_config, load_weights
        return load_weights(load_config().weights_file)

    def _postep_szwu(self) -> dict[str, Any]:
        """Stan renderu; gdy gotowy — DOPIERO TU rusza dźwięk, pod zamkiem,
        tak jak każde inne dotknięcie odtwarzacza."""
        st = dict(self._szew_stan)
        if st.get("stan") != "gotowe":
            return st
        info, para = st["info"], st["para"]
        blad = self._audio.graj_od_zera(str(info["output"]), info["bpm"])
        if blad:
            self._szew_stan = {"stan": "blad",
                               "blad": f"odsłuch szwu nie wyszedł: {blad}"}
            return dict(self._szew_stan)
        # Szew trwa tyle, ile trwa szew: uderzenia planu podzielone przez
        # tempo mastera. Bez tego pasek pokazywał długość utworu A — liczba
        # na ekranie byłaby po prostu nieprawdziwa.
        beats, bpm = info.get("beats"), info.get("bpm")
        dlugosc = (float(beats) * 60.0 / float(bpm)) if beats and bpm else None
        self._gra_co = {"rodzaj": "szew", "track_id": para[0], "para": para,
                        "dlugosc_sec": dlugosc,
                        "opis": f"{st['etykieta']}: "
                                f"{self._tytul(para[0])[:22]} → "
                                f"{self._tytul(para[1])[:22]}",
                        "skad": st["etykieta"]}
        self._szew_stan = {"stan": "gra"}
        return {"stan": "gra", "odtwarzanie": self._stan_odtwarzania(),
                "cue_a_sec": info.get("cue_a_sec"),
                "cue_b_sec": info.get("cue_b_sec")}


    # Publiczne wejścia do odtwarzacza. Każde bierze ten sam zamek, bo
    # pywebview daje każdemu wywołaniu z JS własny wątek, a odpytywanie stanu
    # (4×/s) samo zabija martwy proces — dwa wątki naraz w jednym `Popen`
    # kończyły się ciszą po naciśnięciu P.
    #
    # `@_bezpiecznie` siedzi TYLKO tutaj. Na rdzeniach powyżej był drugi raz
    # i cicho zmieniał kształt odpowiedzi: `dict(self._stan_odtwarzania(),
    # akcja="pauza")` na błędzie sklejało `{"blad", "slad", "akcja"}` — widok
    # takiego kształtu nie zna.

    @_bezpiecznie
    def graj(self, track_id: str, pad: str = "") -> dict[str, Any]:
        with self._zamek_audio:
            return self._graj(track_id, pad)

    @_bezpiecznie
    def stop_dzwieku(self) -> dict[str, Any]:
        with self._zamek_audio:
            return self._stop_dzwieku()

    @_bezpiecznie
    def skocz(self, uderzenia: int) -> dict[str, Any]:
        with self._zamek_audio:
            return self._skocz(int(uderzenia))

    @_bezpiecznie
    def stan_odtwarzania(self) -> dict[str, Any]:
        with self._zamek_audio:
            return self._stan_odtwarzania()

    @_bezpiecznie
    def postep_szwu(self) -> dict[str, Any]:
        with self._zamek_audio:
            return self._postep_szwu()

    def _tytul(self, track_id: str) -> str:
        wpis = self._wpis_spisu(track_id)
        if wpis:
            return wpis.get("tytul") or track_id
        analiza = self._analizy.get(track_id)
        return (analiza.track.title if analiza else None) or track_id

    # ------------------------------------------------- playlista do RB

    def _nazwa_playlisty(self, nazwa: str | None = None) -> str:
        """Nazwa widoczna w Rekordboksie. Bez nazwy lista dziesięciu playlist
        „DanceLab" jest bezużyteczna, więc doklejamy parametry budowy."""
        if nazwa and nazwa.strip():
            return nazwa.strip()
        par = self._parametry_budowy or {}
        minuty = par.get("minuty")
        dj = par.get("dj")
        czesci = ["okno"]
        if minuty:
            czesci.append(f"{float(minuty):g} min")
        if dj:
            czesci.append(str(dj))
        return "DanceLab " + " · ".join(czesci)

    @_bezpiecznie
    def podglad_playlisty(self, nazwa: str = "") -> dict[str, Any]:
        """Stopień pierwszy: ile utworów Rekordbox rozpozna, a które wypadną.

        Baza jest tu tylko czytana. Dopasowanie idzie po ścieżce pliku, a przy
        jej braku po tytule i tylko przy jednym kandydacie — więc lista
        pominiętych jest właściwym wynikiem tego kroku, nie przypisem.
        """
        if not self._kolejnosc:
            return {"blad": "najpierw zbuduj set — nie ma czego wysyłać"}
        if playlista.rekordbox_otwarty():
            return {"blad": "Rekordbox jest otwarty — zamknij go przed zapisem"}
        mianowana = self._nazwa_playlisty(nazwa)
        wynik = playlista.podglad(self._kolejnosc, self._analizy,
                                  nazwa=mianowana)
        if "blad" in wynik:
            return wynik
        # Liczby, które DJ zaraz potwierdzi, mają dotyczyć TEGO setu i tej
        # nazwy — stopień drugi sprawdza, że nic się między nimi nie zmieniło.
        self._playlista_gotowa = {"nazwa": mianowana,
                                  "kolejnosc": list(self._kolejnosc),
                                  "dopasowane": wynik["dopasowane"]}
        return wynik

    @_bezpiecznie
    def wyslij_playliste(self, nazwa: str = "") -> dict[str, Any]:
        """Stopień drugi: playlista ląduje w Rekordboksie (z kopią bazy)."""
        if self._playlista_gotowa is None:
            return {"blad": "najpierw policz, co wejdzie (podgląd), "
                            "potem wysyłaj"}
        mianowana = self._nazwa_playlisty(nazwa)
        gotowa = self._playlista_gotowa
        if (gotowa["kolejnosc"] != self._kolejnosc
                or gotowa["nazwa"] != mianowana):
            self._playlista_gotowa = None
            return {"blad": "set albo nazwa zmieniły się po podglądzie — "
                            "policz jeszcze raz, żeby liczby dotyczyły tego, "
                            "co naprawdę pójdzie do Rekordboxa"}
        if playlista.rekordbox_otwarty():
            return {"blad": "Rekordbox jest otwarty — zamknij go przed zapisem"}

        wynik = playlista.wyslij(self._kolejnosc, self._analizy,
                                 nazwa=mianowana)
        self._playlista_gotowa = None
        if not wynik.get("ok"):
            dziennik.dopisz("playlista_nieudana", skora="gui", nazwa=mianowana,
                            powod=wynik.get("blad"))
            return wynik
        wynik["uwaga"] = ("otwórz Rekordboksa — playlistę widać dopiero po "
                          "jego starcie, bo bazę czyta przy uruchomieniu")
        historia = self._utrwal_odcisk("wysłana playlista")
        if historia:
            wynik.setdefault("notki", []).append(historia)
        # Wysłanie setu na sprzęt to koniec drogi decyzyjnej: co poszło do
        # Rekordboxa, to DJ naprawdę wybrał. Werdykt zapisuje tę chwilę.
        rec = self._werdykt_zapisu(mianowana, dict(wynik))
        rec["powod"] = "playlista"
        plik, blad = dziennik.zapisz_werdykt(rec, skora="gui")
        dziennik.dopisz("playlista", skora="gui", nazwa=mianowana,
                        zapisane=wynik.get("zapisane"),
                        zgloszone=wynik.get("zgloszone"),
                        werdykt=plik, miara=rec["miara"])
        if plik:
            wynik["werdykt"] = plik
        return self._z_dziennikiem(wynik, blad)

    @_bezpiecznie
    def przygotuj_zapis_cue(self) -> dict[str, Any]:
        """Stopień pierwszy: policz, ile padów wejdzie, i pokaż liczby.

        Baza jest tu tylko czytana. Zapis jest osobnym poleceniem, bo DJ ma
        najpierw zobaczyć, co się stanie z jego własnymi cue."""
        if not self._kolejnosc:
            return {"blad": "najpierw zbuduj set — bez niego nie ma czego zapisywać"}
        if zapis_cue.rekordbox_otwarty():
            return {"blad": "Rekordbox jest otwarty — zamknij go przed zapisem cue"}

        # Po edycji kolejności propozycje silnika dotyczą starego setu —
        # liczby, które DJ za chwilę potwierdzi, muszą dotyczyć nowego.
        if (self._plan_cue_nieaktualny and self._plan_cue is not None
                and (self._ctx_edycji or {}).get("wagi") is not None):
            by_id = {t: self._analizy[t] for t in self._kolejnosc
                     if t in self._analizy}
            try:
                self._plan_cue = zapis_cue.propozycje(
                    self._kolejnosc, by_id, self._ctx_edycji["wagi"])
            except Exception as exc:                   # noqa: BLE001
                return {"blad": f"propozycji po edycji setu nie przeliczyłem "
                                f"({exc}) — zapis wstrzymany, bo liczyłby "
                                f"stary set"}
            self._plan_cue_nieaktualny = False
            self._plan_cue_przeliczony = True

        wynik = zapis_cue.przygotuj(
            self._plan_cue or _pusty_plan_cue(), self._edycje,
            self._analizy, self._kolejnosc)
        self._zapis_gotowy = wynik["plan"]
        odpowiedz = {k: v for k, v in wynik.items() if k != "plan"}
        # Liczby, które DJ widział przed potwierdzeniem, idą potem do werdyktu
        # — werdykt ma mówić, na co się zgodził, a nie co wyszło po fakcie.
        self._ostatni_przygotuj = {
            k: odpowiedz[k] for k in ("do_zapisu", "odswiezone",
                                      "ustapilo_twoim", "utworow",
                                      "spoza_kolekcji") if k in odpowiedz}
        return odpowiedz

    @_bezpiecznie
    def zapisz_cue(self, nazwa: str = "okno DanceLab") -> dict[str, Any]:
        """Stopień drugi: zapis. Wymaga stopnia pierwszego — liczby, które DJ
        zobaczył, muszą dotyczyć dokładnie tego planu, który idzie do bazy."""
        if self._zapis_gotowy is None:
            return {"blad": "najpierw policz plan zapisu (podgląd), potem zapisuj"}
        if zapis_cue.rekordbox_otwarty():
            return {"blad": "Rekordbox jest otwarty — zamknij go przed zapisem cue"}
        wynik = zapis_cue.zapisz(self._zapis_gotowy, nazwa=nazwa)
        self._zapis_gotowy = None
        wynik["uwaga"] = ("otwórz Rekordboksa — pady widać dopiero po jego "
                          "starcie, bo bazę czyta przy uruchomieniu")
        historia = self._utrwal_odcisk("zapisane cue")
        if historia:
            wynik["historia"] = historia

        # Dziennik decyzji (Q14): zapis do bazy to moment, w którym propozycje
        # silnika przestają być podpowiedzią, a stają się przyjęte albo
        # odrzucone — dopiero tu wolno je tak nazwać.
        rec = self._werdykt_zapisu(nazwa, dict(wynik))
        plik, blad = dziennik.zapisz_werdykt(rec, skora="gui")
        dziennik.dopisz("zapis_cue", skora="gui", nazwa=nazwa, werdykt=plik,
                        miara=rec["miara"])
        if plik:
            wynik["werdykt"] = plik
        return self._z_dziennikiem(wynik, blad)

    # ---------------------------------------------------- dziennik decyzji

    def _klasyfikuj_pady(self) -> tuple[list[dict[str, Any]], dict[str, int]]:
        """Los każdego pada setu względem propozycji silnika.

        `z_silnika` mówi o ŹRÓDLE, nie o zgodzie — czy DJ propozycję w ogóle
        oglądał, niesie osobne pole `propozycje_widziane`. Pad z utworu,
        którego ekran nigdy nie narysował, przeszedł domyślnie i liczy się
        w mierze jako `przeszlo_domyslnie`, nie jako akceptacja.
        """
        propozycje: dict[str, dict[str, Any]] = {}
        if self._plan_cue is not None:
            for t in self._plan_cue.tracks:
                propozycje[t.content_id] = {c.pad_label: c for c in t.cues}
        nadpisania = self._edycje.get("nadpisania") or {}
        zdjete = set(self._edycje.get("zdjete") or [])

        utwory: list[dict[str, Any]] = []
        miara = {"z_silnika": 0, "nadpisane": 0, "reczne": 0, "zdjete": 0,
                 "przeszlo_domyslnie": 0, "utwory_z_widzianymi": 0,
                 "edycje_sprzed_planu": 0}

        teraz = self._migawka_edycji()

        def sprzed(klucz: str, wpis: dict[str, Any]) -> dict[str, Any]:
            # Edycja zastana w chwili budowy planu nie jest reakcją na jego
            # propozycje — bez tego znacznika „nadpisany" kłamałby o zgodzie.
            # Liczy się WARTOŚĆ, nie sam klucz: pad poprawiony po obejrzeniu
            # propozycji stoi pod tym samym kluczem, ale jest już inną
            # decyzją i ma się liczyć jako reakcja.
            znany = klucz in self._edycje_sprzed_planu
            if znany and self._edycje_sprzed_planu[klucz] == teraz.get(klucz):
                wpis["sprzed_planu"] = True
                miara["edycje_sprzed_planu"] += 1
            return wpis

        for tid in self._kolejnosc:
            widziane = tid in self._pady_pokazane
            pady: dict[str, dict[str, Any]] = {}
            for pad, c in propozycje.get(tid, {}).items():
                klucz = f"{tid}|{pad}"
                if klucz in zdjete:
                    pady[pad] = sprzed(klucz, {"los": "zdjety",
                                               "silnik_ms": c.position_ms})
                    miara["zdjete"] += 1
                elif klucz in nadpisania:
                    pady[pad] = sprzed(klucz, {
                        "los": "nadpisany", "silnik_ms": c.position_ms,
                        "position_ms": nadpisania[klucz]["position_ms"]})
                    miara["nadpisane"] += 1
                else:
                    pady[pad] = {"los": "z_silnika",
                                 "position_ms": c.position_ms}
                    miara["z_silnika"] += 1
                    if not widziane:
                        miara["przeszlo_domyslnie"] += 1
            for klucz, wpis in nadpisania.items():
                t_id, pad = klucz.rsplit("|", 1)
                if t_id == tid and pad not in pady and klucz not in zdjete:
                    pady[pad] = sprzed(klucz, {
                        "los": "reczny", "position_ms": wpis["position_ms"]})
                    miara["reczne"] += 1
            if widziane:
                miara["utwory_z_widzianymi"] += 1
            utwory.append({"track_id": tid, "propozycje_widziane": widziane,
                           "pady": pady})
        return utwory, miara

    def _werdykt_zapisu(self, nazwa: str,
                        wynik_zapisu: dict[str, Any]) -> dict[str, Any]:
        """Pełny zapis tego, na co DJ się zgodził — odpowiednik
        `tui_werdykt_*.json` z terminala, tyle że dla drogi przez okno."""
        import time

        utwory, miara = self._klasyfikuj_pady()

        def sciezka(tid: str) -> str | None:
            a = self._analizy.get(tid)
            return getattr(getattr(a, "track", None), "source_path", None)

        try:
            wagi = (self._wagi_budowy.model_dump()
                    if hasattr(self._wagi_budowy, "model_dump")
                    else self._wagi_budowy if isinstance(self._wagi_budowy, dict)
                    else None)
        except Exception:                              # noqa: BLE001
            wagi = None
        return {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "powod": "zapis_cue",
            "nazwa": nazwa,
            "parametry_budowy": self._parametry_budowy,
            "wagi": wagi,
            "liczby_podgladu": self._ostatni_przygotuj,
            "kolejnosc": [{"track_id": t, "path": sciezka(t)}
                          for t in self._kolejnosc],
            "utwory": utwory,
            "miara": miara,
            # Prawda o rodowodzie propozycji: po edycji setu były przeliczone
            # w stopniu pierwszym, więc DJ widział je dopiero od podglądu.
            "plan_cue_przeliczony_po_edycji": self._plan_cue_przeliczony,
            "zapis": wynik_zapisu,
        }


def _pusty_plan_cue():
    """Plan bez propozycji silnika. Ręcznie postawione pady i tak wejdą —
    `zbuduj_plan_do_zapisu` bierze je z nakładki edycji."""
    from dancelab.decision.cue_export_models import CuePlan
    return CuePlan()
