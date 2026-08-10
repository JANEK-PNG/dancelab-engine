"""Sterowanie doborem: kotwica brzmienia i kontur skoków — jawne wejście DJ-a.

Domyślna ścieżka silnika NIE zmienia się ani o bit: sterowanie działa tylko,
gdy DJ o nie poprosił (`--jak`, `--kontur`). To ta sama zasada, co przy planie
tempa i czystych trybach harmonic/bpm — jawna wola usera jest ramą, silnik
układa wewnątrz niej.

Dwa człony, oba zmierzone zanim powstały:

  KOTWICA — „graj jak X": premia za bliskość kandydata do centroidu brzmienia
  DJ-a z `dj_anchors.json`. Selekcja, nie ocena par — dokładnie wniosek
  z pomiaru 21.07 (CLAP należy do selekcji; w parach sam nie niesie sygnału,
  p=0,378 na bramce 01.08).

  KONTUR — sposób prowadzenia: cel podobieństwa sąsiadów DLA KAŻDEGO KROKU
  z realnego miksu DJ-a. Zmierzone 03.08: styl to rozkład i jego kształt, nie
  średnia — celowanie w medianę 0,71 Four Teta dawało kwartyle 0,71–0,82
  zamiast jego 0,61–0,79 i gasiło rozrzut, który jest całą treścią stylu.

Uczciwość pokrycia: kandydat bez wektora dostaje ocenę rdzenia bez zmian
(waga rozłożona — konwencja `sound_affinity.blend`), a sterowanie liczy braki
i mówi o nich w ostrzeżeniach. Poniżej połowy pokrycia sterowanie samo
zgłasza, że działa na mniejszości puli.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from dancelab.core.models import AnalysisResult
from dancelab.decision.sound_affinity import cosine_affinity

# Wagi rzemieślnicze, nie pomiarowe: dobrane odsłuchem i pomiarem podpisu
# 03.08 (v4 trafiła kwartyl 0,79 i skok 0,46 przy celach 0,79/0,44).
DEFAULT_ANCHOR_WEIGHT = 0.35
DEFAULT_CONTOUR_WEIGHT = 0.45
# |cos - cel| równy tej wartości zeruje dopasowanie konturu; mniejszy mianownik
# robiłby z konturu twardy filtr, większy — ozdobnik.
CONTOUR_TOLERANCE = 0.35


@dataclass
class SoundSteering:
    """Stan sterowania na czas budowy jednego setu."""

    anchor: np.ndarray | None = None
    anchor_weight: float = DEFAULT_ANCHOR_WEIGHT
    # Środek przestrzeni brzmienia (średni wektor puli). Odjęty od OBU stron
    # porównania sprawia, że kotwica mierzy to, co danego DJ-a WYRÓŻNIA,
    # zamiast tego, co łączy wszystkich. Zmierzone 09.08: bez tego mediana
    # kosinusa między centroidami 363 par DJ-ów to 0,886, więc „graj jak
    # Four Tet" i „graj jak Ben UFO" dawały ten sam set; po wyśrodkowaniu
    # mediana spada do 0,008, a ta para zostaje blisko (+0,458).
    srodek: np.ndarray | None = None
    contour: list[float] | None = None
    contour_weight: float = DEFAULT_CONTOUR_WEIGHT
    anchor_name: str | None = None
    _missing: int = 0
    _seen: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return self.anchor is not None or bool(self.contour)

    def contour_target(self, position: int) -> float | None:
        """Cel skoku dla przejścia NA pozycję `position` (1-indeksowane wejście).

        Kontur jest krótszy niż długi set — zawijamy cyklicznie. To świadomy
        kompromis: kształt frazy prowadzenia się powtarza, zamiast urywać.
        """
        if not self.contour:
            return None
        return float(self.contour[(position - 1) % len(self.contour)])

    def adjust(
        self,
        base_score: float,
        previous: AnalysisResult,
        candidate: AnalysisResult,
        position: int,
    ) -> tuple[float, list[str]]:
        """Ocena rdzenia + człony sterowania. Zwraca (ocena, zdania do uzasadnienia)."""
        if not self.active:
            return base_score, []
        self._seen += 1
        cand_vec = candidate.track.sound_embedding
        if cand_vec is None:
            self._missing += 1
            return base_score, ["steering: kandydat bez wektora — rdzeń bez zmian"]

        score = float(base_score)
        why: list[str] = []

        if self.anchor is not None:
            kotwica = self.anchor
            wektor = np.asarray(cand_vec, dtype=float)
            if self.srodek is not None:
                # KONTUR zostaje na surowych wektorach: jego cele zmierzono
                # na nich i wyśrodkowanie unieważniłoby kalibrację.
                kotwica = kotwica - self.srodek
                wektor = wektor - self.srodek
            aff = cosine_affinity(kotwica, wektor)
            if aff is not None:
                w = self.anchor_weight
                score = (1.0 - w) * score + w * aff
                why.append(f"kotwica {self.anchor_name or '?'}: bliskość {aff:.2f} (w={w:.2f})")

        target = self.contour_target(position)
        if target is not None:
            cos = cosine_affinity(
                np.asarray(previous.track.sound_embedding)
                if previous.track.sound_embedding is not None else None,
                np.asarray(cand_vec),
            )
            if cos is None:
                why.append("kontur: brak wektora poprzednika — człon pominięty")
            else:
                # cosine_affinity mapuje do [0,1]; kontur z artefaktu jest w
                # surowym cos [-1,1] — sprowadzamy cel do tej samej skali.
                target01 = (target + 1.0) / 2.0
                fit = max(0.0, 1.0 - abs(cos - target01) / CONTOUR_TOLERANCE)
                w = self.contour_weight
                score = (1.0 - w) * score + w * fit
                why.append(
                    f"kontur krok {position}: cel {target01:.2f}, jest {cos:.2f}, "
                    f"dopasowanie {fit:.2f} (w={w:.2f})")

        return float(np.clip(score, 0.0, 1.0)), why

    def coverage_warnings(self) -> list[str]:
        out = list(self.notes)
        if self._seen and self._missing:
            frac = self._missing / self._seen
            out.append(
                f"sterowanie brzmieniem: {self._missing}/{self._seen} ocen bez "
                f"wektora kandydata ({frac:.0%})")
            if frac > 0.5:
                out.append(
                    "sterowanie działało na MNIEJSZOŚCI puli — wynik bliżej "
                    "zwykłego setu niż proszonego stylu")
        return out
