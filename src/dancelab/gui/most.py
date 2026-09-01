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

from dancelab.stan import budowa, cue, dziennik, edycje, plan, przebieg, zapis_cue


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
        self._analizy: dict[str, Any] = {}
        self._katalog = katalog or self.KATALOG_ANALIZ
        self._spis: list[dict[str, Any]] = []
        # Budowa setu trwa dziesiątki sekund. W pywebview wywołanie z JS jest
        # synchroniczne, więc budowanie wprost zamroziłoby okno — stąd wątek
        # i stan odpytywany przez `postep_budowy`.
        self._budowa: dict[str, Any] = {"stan": "bezczynny"}
        self._analizy_pula: list | None = None
        # Zapis cue jest DWUSTOPNIOWY: tu leży plan policzony w stopniu
        # pierwszym. Każda zmiana padów albo setu go kasuje, bo inaczej
        # potwierdzenie zapisałoby stan sprzed edycji.
        self._zapis_gotowy: Any = None
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
        # stąd migawka kluczy edycji zastanych w chwili budowy planu.
        self._edycje_sprzed_planu: set[str] = set()
        # Edycja setu: to, czym set był oceniany przy budowie (wagi, łuk,
        # planer, okno tempa, kotwica) — panel podmian liczy kandydatów
        # dokładnie tym samym, inaczej sugestie miałyby inny gust niż set.
        self._ctx_edycji: dict[str, Any] | None = None
        self._kandydaci_meta: dict[str, dict[str, Any]] = {}
        # Liczenie kandydatów trwa ~4 s na pełnej puli (pomiar 01.09), więc
        # chodzi w wątku i ma własny stan odpytywany przez widok — jak budowa.
        self._kandydaci_stan: dict[str, Any] = {"stan": "bezczynny"}
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
                    prefiks = f.read(4096).decode("utf-8", "replace")
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
                "dlugosc_sec": t.get("duration_sec"),
            })

        self._spis = spis
        return {"utwory": spis[:limit], "wszystkich": len(spis),
                "katalog": self._katalog}

    @_bezpiecznie
    def wczytaj_utwor(self, track_id: str) -> dict[str, Any]:
        """Wczytaj pełną analizę i zwróć przebieg gotowy do narysowania."""
        from dancelab.storage.repositories import FileAnalysisRepository

        if track_id not in self._analizy:
            repo = FileAnalysisRepository(self._katalog)
            self._analizy[track_id] = repo.get(track_id)
        wynik = przebieg.zbuduj(self._analizy[track_id]).do_slownika()
        wpis = next((u for u in self._spis if u["track_id"] == track_id), None)
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
        if self._plan_cue is not None:
            self._pady_pokazane.add(track_id)
            return {"pady": edycje.efektywne_pady(self._plan_cue, self._edycje,
                                                  track_id),
                    "zrodlo": "silnik + ręczne"}
        # Klucz w cue_edycje ma postać "track_id|pad"; zdjęte trzymane osobno.
        zdjete = set(self._edycje.get("zdjete") or [])
        wlasne = {
            klucz.split("|", 1)[1]: wart
            for klucz, wart in (self._edycje.get("nadpisania") or {}).items()
            if klucz.startswith(f"{track_id}|") and klucz not in zdjete
        }
        return {"pady": wlasne, "zrodlo": "tylko ręczne (brak planu setu)"}

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
        blad = dziennik.dopisz("cue_postaw", track_id=track_id, pad=pad,
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
        blad = dziennik.dopisz("cue_przesuniecie", track_id=track_id, pad=pad,
                               uderzenia=int(uderzenia), position_ms=nowa,
                               **self._kontekst_propozycji(track_id, pad))
        return self._z_dziennikiem(self.pady(track_id), blad)

    @_bezpiecznie
    def zdejmij_pad(self, track_id: str, pad: str) -> dict[str, Any]:
        self._zapis_gotowy = None
        kontekst = self._kontekst_propozycji(track_id, pad)
        edycje.zdejmij(self._edycje, track_id, pad)
        blad = dziennik.dopisz("cue_zdjecie", track_id=track_id, pad=pad,
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
            blad = dziennik.dopisz("cue_cofniecie", zmienione=zmienione)
        wynik = self._z_dziennikiem(self.pady(track_id), blad)
        wynik["cofnieto"] = bool(udalo)
        return wynik

    # ------------------------------------------------------- trwałość edycji

    #: Gdzie okno odkłada swoje zmiany. Ten sam katalog, w którym TUI trzyma
    #: plany, żeby obie skóry miały jedno miejsce — nie dwa równoległe światy.
    PLIK_EDYCJI = "data/exports/tui_plany/gui_edycje.json"

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
        self._edycje_sprzed_planu |= (set(self._edycje["nadpisania"])
                                      | set(self._edycje["zdjete"]))
        return {"wczytano": len(self._edycje["nadpisania"])}

    # ------------------------------------------------------------- budowa

    def _pula(self) -> list:
        """Pula analiz, wczytana raz. 8 tysięcy plików to kilkanaście sekund."""
        if self._analizy_pula is None:
            analizy, notki = budowa.pula(self._katalog)
            self._analizy_pula = analizy
            self._budowa["notki_puli"] = notki
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
                from dancelab.tui.user_store import load_state
                stan_u = load_state(self._katalog)
            except Exception:                          # noqa: BLE001
                pass                                   # filary są opcjonalne

            pula = self._pula()
            wynik = budowa.zbuduj(par, processed_dir=self._katalog,
                                  postep=etap, analizy=pula,
                                  stan_uzytkownika=stan_u)
            self._kolejnosc = list(wynik["kolejnosc"])
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
            self._edycje_sprzed_planu = (
                set(self._edycje.get("nadpisania") or {})
                | set(self._edycje.get("zdjete") or []))
            self._ctx_edycji = {
                "wagi": wynik.get("wagi"), "luk": par.luk,
                "planer": par.planer, "bpm_min": par.bpm_min,
                "bpm_max": par.bpm_max,
                "kotwica_centroid": wynik.get("kotwica_centroid"),
                "filary": list(wynik.get("filary") or [])}
            self._kandydaci_meta = {}
            self._plan_cue_nieaktualny = False
            self._plan_cue_przeliczony = False
            dziennik.dopisz(
                "budowa", parametry=self._parametry_budowy,
                utworow=len(wynik["kolejnosc"]),
                kolejnosc=list(wynik["kolejnosc"]),
                pady_silnika=(sum(len(t.cues) for t in self._plan_cue.tracks)
                              if self._plan_cue is not None else 0),
                edycje_zastane=len(self._edycje_sprzed_planu),
                plan=str(sciezka))

            self._budowa = {
                "stan": "gotowe",
                "utwory": [self._wiersz(t, wynik["by_id"]) for t in wynik["kolejnosc"]],
                "notki": (self._budowa.get("notki_puli") or []) + wynik["notki"],
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
    def wczytaj_plan(self, sciezka: str) -> dict[str, Any]:
        """Wczytaj wskazany plan i uczyń go bieżącym dla obu skór."""
        wynik = plan.wczytaj(self._analizy, sciezka)
        if wynik.get("kolejnosc"):
            self._kolejnosc = list(wynik["kolejnosc"])
            plan.WSKAZNIK.parent.mkdir(parents=True, exist_ok=True)
            plan.WSKAZNIK.write_text(
                json.dumps({"plan": str(sciezka)}, ensure_ascii=False),
                encoding="utf-8")
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

    @_bezpiecznie
    def propozycje(self, track_id: str, silnik_ms: int | None = None) -> dict[str, Any]:
        """Gdzie silnik proponuje pad — podpowiedź, nie nakaz."""
        analiza = self._analizy.get(track_id)
        if analiza is None:
            return {"blad": f"nie mam analizy dla {track_id!r}"}
        return {"propozycje": cue.propozycje_czasu(analiza, silnik_ms)}

    # --------------------------------------------------------- edycja setu

    def _sciezka(self, tid: str) -> str | None:
        a = self._analizy.get(tid)
        return getattr(getattr(a, "track", None), "source_path", None)

    def _po_edycji_setu(self) -> dict[str, Any]:
        """Wspólny ogon każdej edycji kolejności: unieważnij policzony zapis,
        oznacz propozycje padów jako nieaktualne, oddaj świeże wiersze."""
        self._zapis_gotowy = None
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

    def _zrodlo_kandydata(self, tid: str) -> dict[str, Any]:
        """Skąd wziął się wstawiony utwór — z listy silnika czy z ręki DJ-a.

        Ta sama zasada co w terminalu (`app.py::_zrodlo_kandydata`): wybór bez
        metadanych panelu jest uczciwie opisany jako własny, nie zgadywany.
        """
        meta = self._kandydaci_meta.get(tid)
        return dict(meta) if meta else {"zrodlo": "reka_dj"}

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
        blad = dziennik.dopisz(
            "podmiana", pozycja=idx + 1,
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
        blad = dziennik.dopisz(
            "dopisanie", pozycja=idx + 2,
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
        blad = dziennik.dopisz("ciecie", pozycja=idx + 1,
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
        blad = dziennik.dopisz("przesuniecie", z=idx + 1, na=j + 1,
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
        }

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

        # Dziennik decyzji (Q14): zapis do bazy to moment, w którym propozycje
        # silnika przestają być podpowiedzią, a stają się przyjęte albo
        # odrzucone — dopiero tu wolno je tak nazwać.
        rec = self._werdykt_zapisu(nazwa, dict(wynik))
        plik, blad = dziennik.zapisz_werdykt(rec)
        dziennik.dopisz("zapis_cue", nazwa=nazwa, werdykt=plik,
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

        def sprzed(klucz: str, wpis: dict[str, Any]) -> dict[str, Any]:
            # Edycja zastana w chwili budowy planu nie jest reakcją na jego
            # propozycje — bez tego znacznika „nadpisany" kłamałby o zgodzie.
            if klucz in self._edycje_sprzed_planu:
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
