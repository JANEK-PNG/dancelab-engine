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
import traceback
from typing import Any

from dancelab.stan import cue, edycje, plan, przebieg


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
        self._plan: Any = None
        self._analizy: dict[str, Any] = {}
        self._katalog = katalog or self.KATALOG_ANALIZ
        self._spis: list[dict[str, Any]] = []

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
        if self._plan is not None:
            return {"pady": edycje.efektywne_pady(self._plan, self._edycje, track_id),
                    "zrodlo": "plan + ręczne"}
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
        edycje.postaw(self._edycje, track_id, pad, int(position_ms))
        return self.pady(track_id)

    @_bezpiecznie
    def przesun_pad(self, track_id: str, pad: str, uderzenia: int,
                    bpm: float) -> dict[str, Any]:
        """Przesuń o całe uderzenia — po to, żeby nie da się trafić między takty."""
        edycje.przesun(self._edycje, track_id, pad, int(uderzenia), float(bpm))
        return self.pady(track_id)

    @_bezpiecznie
    def zdejmij_pad(self, track_id: str, pad: str) -> dict[str, Any]:
        edycje.zdejmij(self._edycje, track_id, pad)
        return self.pady(track_id)

    @_bezpiecznie
    def cofnij(self, track_id: str) -> dict[str, Any]:
        """Cofnięcie jest w rdzeniu, nie w widoku — terminal ma je tak samo."""
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

    # ---------------------------------------------------------- plan setu

    @_bezpiecznie
    def biezacy_plan(self) -> dict[str, Any]:
        """Set, nad którym pracujemy — ten sam plik, który czyta terminal."""
        wynik = plan.wczytaj(self._analizy)
        self._plan = wynik.get("kolejnosc") or None
        return wynik

    @_bezpiecznie
    def lista_planow(self) -> dict[str, Any]:
        return {"plany": plan.lista()}

    @_bezpiecznie
    def wczytaj_plan(self, sciezka: str) -> dict[str, Any]:
        """Wczytaj wskazany plan i uczyń go bieżącym dla obu skór."""
        wynik = plan.wczytaj(self._analizy, sciezka)
        if wynik.get("kolejnosc"):
            self._plan = wynik["kolejnosc"]
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
