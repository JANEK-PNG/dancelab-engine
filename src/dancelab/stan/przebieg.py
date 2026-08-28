"""Przebieg utworu jako LICZBY — do rysowania, nie do wypisania w terminalu.

`tui/cue_podglad.os_energii()` i `pas_sekcji()` zwracają znaki (▁▂▅█, INTRO─┤),
bo powstały dla terminala i tam działają dobrze. GUI potrzebuje tych samych
danych przed zamianą na znaki: obwiedni w N punktach, granic sekcji w sekundach
i siatki taktów.

To jedyna nowa logika w warstwie stanu. Reszta modułów TUI jest czysta i wchodzi
do GUI bez zmian — patrz `stan/__init__.py`.

Kwantyzacja jest CELOWO ta sama co w terminalu (średnia RMS w koszu, potem
skalowanie min–max), żeby obie skóry pokazywały ten sam kształt. Test
`test_stan_przebieg.py` porównuje jedno z drugim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Ile punktów obwiedni domyślnie. 900 to około jeden na piksel przy szerokim
# oknie — ale to jest SUFIT, nie cel: analizy mają około jednej klatki na
# sekundę (zmierzone na 60 plikach: mediana 315 klatek, 1,00 klatki/s), więc
# żądanie 900 koszy z trzyminutowego utworu zostawiało 65% z nich pustych i
# fala wyglądała jak grzebień. Liczba punktów jest teraz ograniczana do liczby
# klatek, które naprawdę są.
PUNKTOW = 900


@dataclass
class Sekcja:
    """Fragment utworu z naszej segmentacji (odpowiednik fraz Rekordboxa)."""

    od_sec: float
    do_sec: float
    typ: str
    nazwa: str


@dataclass
class Przebieg:
    """Wszystko, czego widok potrzebuje do narysowania jednego utworu."""

    dlugosc_sec: float
    obwiednia: list[float] = field(default_factory=list)   # 0..1, None → 0
    ma_dane: list[bool] = field(default_factory=list)      # gdzie NAPRAWDĘ mierzono
    sekcje: list[Sekcja] = field(default_factory=list)
    takty_sec: list[float] = field(default_factory=list)
    bpm: float | None = None

    def do_slownika(self) -> dict[str, Any]:
        """Postać przekazywana do JavaScriptu przez most."""
        return {
            "dlugosc_sec": round(self.dlugosc_sec, 3),
            "obwiednia": [round(v, 4) for v in self.obwiednia],
            "ma_dane": self.ma_dane,
            "sekcje": [
                {"od": round(s.od_sec, 3), "do": round(s.do_sec, 3),
                 "typ": s.typ, "nazwa": s.nazwa}
                for s in self.sekcje
            ],
            "takty_sec": [round(t, 3) for t in self.takty_sec],
            "bpm": self.bpm,
        }


def _typ_sekcji(seg: Any) -> str:
    t = getattr(seg, "segment_type", None)
    return str(getattr(t, "value", t) or "?")


def zbuduj(analysis: Any, punktow: int = PUNKTOW,
           takty_do: int = 512) -> Przebieg:
    """Zamień wynik analizy na dane do narysowania.

    ``ma_dane`` jest osobną listą, a nie zerem w obwiedni, bo to dwie różne
    rzeczy: „tu jest cicho" i „tu nie mierzyliśmy". Widok ma prawo pokazać je
    inaczej — ADR-005 mówi, że każde „nie wiem" ma swój piksel.
    """
    from dancelab.tui.cue_podglad import NAZWY_SEKCJI, czas_utworu

    dlugosc = float(czas_utworu(analysis) or 0.0)
    p = Przebieg(dlugosc_sec=dlugosc)
    if dlugosc <= 0 or punktow <= 0:
        return p

    klatki = [f for f in (getattr(analysis, "features", None) or [])
              if getattr(f, "rms", None) is not None]

    # Nie żądaj większej rozdzielczości, niż dają dane. Rysowanie 900 słupków
    # z 315 pomiarów nie dodaje informacji — produkuje dziury, które wyglądają
    # jak brak sygnału, choć są tylko brakiem próbek.
    if klatki:
        punktow = max(1, min(punktow, len(klatki)))

    sumy = [0.0] * punktow
    ile = [0] * punktow
    for f in klatki:
        i = min(int(f.timestamp_sec / dlugosc * punktow), punktow - 1)
        if i >= 0:
            sumy[i] += f.rms
            ile[i] += 1

    srednie = [s / n if n else None for s, n in zip(sumy, ile, strict=False)]
    znane = [s for s in srednie if s is not None]
    if znane:
        lo, hi = min(znane), max(znane)
        zakres = (hi - lo) or 1.0
        p.obwiednia = [0.0 if s is None else (s - lo) / zakres for s in srednie]
    else:
        p.obwiednia = [0.0] * punktow
    p.ma_dane = [s is not None for s in srednie]

    for seg in sorted(getattr(analysis, "segments", None) or [],
                      key=lambda s: s.start_sec):
        typ = _typ_sekcji(seg)
        p.sekcje.append(Sekcja(
            od_sec=float(seg.start_sec), do_sec=float(seg.end_sec),
            typ=typ, nazwa=NAZWY_SEKCJI.get(typ, "?")))

    siatka = getattr(analysis, "beatgrid", None)
    bpm = getattr(siatka, "bpm", None) or getattr(
        getattr(analysis, "track", None), "bpm_estimate", None)
    p.bpm = float(bpm) if bpm else None

    # Kreski taktów co 4 uderzenia. Ograniczone liczbą, bo przy 8-minutowym
    # utworze to ponad tysiąc linii, których i tak nikt nie odróżni.
    if p.bpm and p.bpm > 0:
        krok = 4 * 60.0 / p.bpm
        pierwszy = float(getattr(siatka, "first_beat_sec", 0.0) or 0.0)
        n = int((dlugosc - pierwszy) / krok) if krok > 0 else 0
        if 0 < n <= takty_do:
            p.takty_sec = [pierwszy + i * krok for i in range(n + 1)]

    return p
