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

FFPLAY = shutil.which("ffplay")


class Odtwarzacz:
    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._path: str | None = None
        self._bpm: float | None = None
        self._offset = 0.0          # pozycja startu bieżącego procesu
        self._od_kiedy: float | None = None   # monotonic startu

    # ------------------------------------------------------------- stan

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
        if FFPLAY:
            cmd = [FFPLAY, "-nodisp", "-autoexit", "-loglevel", "quiet",
                   "-ss", f"{max(offset, 0.0):.3f}", str(self._path)]
        else:
            if offset > 0:
                return "skoki i wznowienie wymagają ffplay (brew install ffmpeg)"
            cmd = ["afplay", str(self._path)]
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

    def skocz(self, uderzenia: int) -> tuple[float, str | None]:
        """±N uderzeń wg tempa utworu (siatka silnika). Tylko gdy gra."""
        if not self.gra():
            return self._offset, "nic nie gra"
        bpm = self._bpm or 120.0
        cel = max(self.pozycja() + uderzenia * 60.0 / bpm, 0.0)
        self._zabij()
        return cel, self._uruchom(cel)

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
