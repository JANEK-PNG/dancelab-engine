"""Odtwarzacz podglądu (P) — ffplay z pozycją, pauzą i skokami po uderzeniach.

Dlaczego nie afplay: nie umie startować od środka utworu (zero seeka), więc
skoki „co 8 uderzeń" (życzenie Janka 06.08) są z nim niewykonalne. ffplay
(Homebrew, natywny arm64) startuje od dowolnej sekundy — odtwarzacz trzyma
własny licznik pozycji: pauza = stop + zapamiętanie miejsca, wznowienie tego
samego utworu = start od miejsca, skok = restart o ±N uderzeń liczonych
z TEMPA NASZEJ SIATKI (60/BPM · N — skok muzyczny, nie „o ileś sekund").
Restart procesu przy skoku daje ~0,1–0,2 s ciszy — podgląd, nie live-mix.

Brak ffplay = uczciwa degradacja do afplay: granie działa, skoki zgłaszają
brak narzędzia. DŹWIĘK startuje wyłącznie z jawnego klawisza użytkownika —
twarda zasada projektu; testy podmieniają procesy atrapami.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import time

def _znajdz(nazwa: str,
            katalogi: tuple[str, ...] = ("/opt/homebrew/bin",
                                         "/usr/local/bin")) -> str | None:
    """which + znane gniazda Homebrew. Aplikacja odpalana z IKONY dostaje
    goły PATH launchd (bez /opt/homebrew/bin) — złapane 09.08, gdy odsłuch
    od pada milczał w Ghostty, choć w terminalu działał."""
    znaleziony = shutil.which(nazwa)
    if znaleziony:
        return znaleziony
    for katalog in katalogi:
        sciezka = pathlib.Path(katalog) / nazwa
        if sciezka.is_file():
            return str(sciezka)
    return None


FFPLAY = _znajdz("ffplay")
AFPLAY = _znajdz("afplay")

# HYBRYDA (skarga Janka 06.08: sekunda przerwy przy przełączaniu utworów):
# ffplay wolno startuje (inicjalizacja audio ~0,5 s), afplay startuje niemal
# natychmiast, ale nie umie seeka. Więc: start OD ZERA (przełączanie
# utworów strzałkami) gra afplayem, a ffplay wchodzi tylko tam, gdzie
# trzeba wystartować od środka (skok, wznowienie z pauzy).


class Odtwarzacz:
    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._path: str | None = None
        self._bpm: float | None = None
        self._offset = 0.0          # pozycja startu bieżącego procesu
        self._od_kiedy: float | None = None   # monotonic startu

    # ------------------------------------------------------------- stan

    @property
    def sciezka(self) -> str | None:
        return self._path

    def gra(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def pozycja(self) -> float:
        if self.gra() and self._od_kiedy is not None:
            return self._offset + (time.monotonic() - self._od_kiedy)
        return self._offset

    def opis(self) -> str:
        if not self._path:
            return ""
        m, s = divmod(int(self.pozycja()), 60)
        return f"{pathlib.Path(self._path).stem[:36]} @ {m}:{s:02d}"

    # ------------------------------------------------------------ sterowanie

    def _uruchom(self, offset: float) -> str | None:
        od_zera = offset <= 0.05
        if od_zera and AFPLAY:
            cmd = [AFPLAY, str(self._path)]
            offset = 0.0
        elif FFPLAY:
            cmd = [FFPLAY, "-nodisp", "-autoexit", "-loglevel", "quiet",
                   "-ss", f"{max(offset, 0.0):.3f}", str(self._path)]
        elif od_zera:
            cmd = ["afplay", str(self._path)]
            offset = 0.0
        else:
            return "skoki i wznowienie wymagają ffplay (brew install ffmpeg)"
        self._proc = subprocess.Popen(cmd)
        self._offset = max(offset, 0.0)
        self._od_kiedy = time.monotonic()
        return None

    def przelacz(self, path: str, bpm: float | None) -> tuple[str, str | None]:
        """P na utworze: gra→pauza; ten sam utwór→wznowienie; inny→od zera.
        Zwraca (akcja, błąd): akcja ∈ pauza|wznowienie|start."""
        if self.gra():
            self.stop()
            return "pauza", None
        if path == self._path and self._offset > 0:
            return "wznowienie", self._uruchom(self._offset)
        self._path, self._bpm, self._offset = path, bpm, 0.0
        return "start", self._uruchom(0.0)

    def graj_od_zera(self, path: str, bpm: float | None) -> str | None:
        """Auto-podgląd: bezwzględnie zatrzymaj poprzedni, graj nowy od 0."""
        self.stop()
        self._path, self._bpm, self._offset = path, bpm, 0.0
        return self._uruchom(0.0)

    def graj_od(self, path: str, bpm: float | None,
                sekunda: float) -> str | None:
        """Odsłuch od pada (edytor cue, etap 3): start od wskazanej sekundy.
        Start od środka to działka ffplay; bez niego degradacja jawna."""
        self.stop()
        self._path, self._bpm = path, bpm
        self._offset = max(float(sekunda), 0.0)
        return self._uruchom(self._offset)

    def skocz(self, uderzenia: int) -> tuple[float, str | None]:
        """±N uderzeń wg tempa utworu (siatka silnika). Tylko gdy gra."""
        if not self.gra():
            return self._offset, "nic nie gra"
        bpm = self._bpm or 120.0
        cel = max(self.pozycja() + uderzenia * 60.0 / bpm, 0.0)
        self._zabij()
        return cel, self._uruchom(cel)

    def skonczyl_sie(self) -> str | None:
        """Ścieżka utworu, który skończył się SAM (proces wyszedł bez stop());
        None, gdy nic się nie skończyło. Zeruje pozycję — koniec to koniec."""
        if self._proc is not None and self._proc.poll() is not None:
            self._zabij()
            self._offset = 0.0
            return self._path
        return None

    def stop(self) -> bool:
        """Pauza z zapamiętaniem pozycji. True, jeśli coś grało."""
        gralo = self.gra()
        if gralo:
            self._offset = self.pozycja()
        self._zabij()
        return gralo

    def _zabij(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
        self._proc = None
        self._od_kiedy = None
