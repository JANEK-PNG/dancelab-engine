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

from dancelab.stan import budowa, cue, edycje, plan, przebieg, zapis_cue


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

    @_bezpiecznie
    def postaw_pad(self, track_id: str, pad: str, position_ms: int) -> dict[str, Any]:
        self._zapis_gotowy = None
        edycje.postaw(self._edycje, track_id, pad, int(position_ms))
        return self.pady(track_id)

    @_bezpiecznie
    def przesun_pad(self, track_id: str, pad: str, uderzenia: int,
                    bpm: float) -> dict[str, Any]:
        """Przesuń o całe uderzenia — po to, żeby nie da się trafić między takty."""
        self._zapis_gotowy = None
        edycje.przesun(self._edycje, track_id, pad, int(uderzenia), float(bpm))
        return self.pady(track_id)

    @_bezpiecznie
    def zdejmij_pad(self, track_id: str, pad: str) -> dict[str, Any]:
        self._zapis_gotowy = None
        edycje.zdejmij(self._edycje, track_id, pad)
        return self.pady(track_id)

    @_bezpiecznie
    def cofnij(self, track_id: str) -> dict[str, Any]:
        """Cofnięcie jest w rdzeniu, nie w widoku — terminal ma je tak samo."""
        self._zapis_gotowy = None
        udalo = edycje.cofnij(self._edycje)
        wynik = self.pady(track_id)
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

        self._budowa = {"stan": "trwa", "etap": "start", "notki": []}
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

            wynik = budowa.zbuduj(par, processed_dir=self._katalog,
                                  postep=etap, analizy=self._pula(),
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

        wynik = zapis_cue.przygotuj(
            self._plan_cue or _pusty_plan_cue(), self._edycje,
            self._analizy, self._kolejnosc)
        self._zapis_gotowy = wynik["plan"]
        return {k: v for k, v in wynik.items() if k != "plan"}

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
        return wynik


def _pusty_plan_cue():
    """Plan bez propozycji silnika. Ręcznie postawione pady i tak wejdą —
    `zbuduj_plan_do_zapisu` bierze je z nakładki edycji."""
    from dancelab.decision.cue_export_models import CuePlan
    return CuePlan()
