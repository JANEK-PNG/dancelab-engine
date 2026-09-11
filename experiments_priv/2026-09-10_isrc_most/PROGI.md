# Most ISRC — progi zapisane PRZED pomiarem (2026-09-10)

Pomiar wstępny z przeglądu możliwości Apple Music: 207 z 272 plików lokalnych
ma ISRC w tagu, 17 z 25 próbki rozwiązuje się w katalogu (68 %).

## Punkt kontrolny 0 — czytnik tagów
Czytnik ma odtworzyć ~207 plików z ISRC (±5). Mniej → najpierw naprawić
czytnik, dopiero potem pytać Apple.

## Próg wpięcia do `dokarm`
- Oczekiwane: ≈68 % plików z ISRC rozwiązuje się w katalogu `pl`.
- **Poniżej 50 % → raport i NIE wpinamy do `dokarm`.**
- Gatunek: parasol (Electronic/Dance/Music) jest odrzucany jak dotąd, więc
  realny zysk gatunku podajemy jako „gatunek zyskało N z plików bez gatunku",
  nie jako liczbę rozwiązanych.

## Czego ten krok nie robi
- Nie scala bliźniaków w widoku biblioteki (to `tui/duplikaty.py`, inny folder) —
  tylko liczy je.
- Nie pobiera okładek z Apple (okno: „zero sieci" dla okładek).
- Pliki bez ISRC w tagu zostają bez tożsamości.
