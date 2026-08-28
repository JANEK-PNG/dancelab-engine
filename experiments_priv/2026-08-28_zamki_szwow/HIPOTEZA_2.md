# Druga próba: okno, które nie sięga poprzedniego zagrania

**Zapisane 2026-08-28 PRZED zmianą kodu.** Po obaleniu pierwszej hipotezy
(patrz `WYNIK.md`: podział okna nie miał z tym nic wspólnego).

## Co wiemy na pewno

Sześć utworów bez zamka to **drugie zagranie** utworu granego dwa razy — sześć
na sześć. Ten sam odcisk dźwiękowy pasuje w dwóch miejscach nagrania, więc
kotwice z różnych odcinków okna wskazują różne wystąpienia i konsensus nie
powstaje.

## Co zmieniam

`lock()` próbuje czterech okien kandydujących:

```
(marker + 8, end - 5)        (marker + 8, marker + 95)
(marker + 40, marker + 170)  (end - 95, end + 35)
```

Dwa z nich mogą sięgnąć poza czas tego zagrania: `marker + 95` i `marker + 170`
przy krótkim graniu wychodzą za `end`, a `end + 35` wchodzi w następny utwór.
Przy powtórce to znaczy, że okno może objąć **poprzednie** wystąpienie tego
samego nagrania.

Poprawka: dla utworu, który już wcześniej wystąpił w tym secie, okna są
**przycinane do jego własnego czasu grania** — nie mogą sięgnąć ani przed
`marker`, ani za `end`. Dla utworów granych raz nic się nie zmienia.

**Rygor konsensusu zostaje nietknięty**: nadal ≥2 niezależne kotwice nazywające
ten sam moment w granicach 0,4 s.

## Próg

* **ZOSTAJE** — przybywają **≥3 zamki** (z 31 na ≥34 w obu setach razem),
  **żaden obecny nie znika**, i żaden nowy nie ma rozrzutu powyżej 40 ms
  (najgorszy dzisiejszy ma 35 ms).
* **WRACA** — przybywa 0–1 zamków, ALBO znika choć jeden obecny, ALBO nowy
  zamek ma rozrzut ponad 40 ms. Zamek niepewny jest gorszy niż jego brak:
  mierzymy nim ruch ręki z dokładnością do dziesiątych sekundy.
* **NIEROZSTRZYGNIĘTE** — 2 nowe zamki bez strat. Zapisuję, zostawiam kod
  prostszy.

## Ryzyko, które przyjmuję świadomie

Przycięte okno jest krótsze, więc może nie zebrać dwóch kotwic tam, gdzie
dłuższe je zbierało. Dlatego warunek „żaden obecny nie znika" jest twardy, a nie
uznaniowy — sprawdzam go pozycja po pozycji przeciw zapisanemu stanowi sprzed
zmiany (`locks_przed_*.json`).
