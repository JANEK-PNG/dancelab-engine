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
import traceback
from typing import Any

from dancelab.stan import cue, edycje, przebieg


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

    def __init__(self) -> None:
        self._edycje = edycje.nowe()
        self._plan: Any = None
        self._analizy: dict[str, Any] = {}

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

    @_bezpiecznie
    def propozycje(self, track_id: str, silnik_ms: int | None = None) -> dict[str, Any]:
        """Gdzie silnik proponuje pad — podpowiedź, nie nakaz."""
        analiza = self._analizy.get(track_id)
        if analiza is None:
            return {"blad": f"nie mam analizy dla {track_id!r}"}
        return {"propozycje": cue.propozycje_czasu(analiza, silnik_ms)}
