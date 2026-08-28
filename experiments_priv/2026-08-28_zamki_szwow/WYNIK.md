# Wynik: hipoteza obalona. Prawdziwa przyczyna to POWTÓRKI, nie krótkie granie.

Zmierzone 2026-08-28. Próg zapisany w `HIPOTEZA.md` przed zmianą kodu.

## Rozliczenie z progiem

Poprawka: adaptacyjna liczba podziałów okna (krótkie okno → mniej, dłuższych
odcinków). Próg wymagał **≥3 nowych zamków**.

| | przed | po |
|---|---|---|
| zamki w secie Open Deck | 16 / 19 | **16 / 19** |
| zamki, które zniknęły | — | 0 |
| zamki pogorszone o >10 ms | — | 0 |

**Zero nowych zamków. Poprawka cofnięta**, zgodnie z progiem („przybywa 0–1 →
wraca"). Powód cofnięcia zapisany w docstringu `_try_window`, żeby nikt nie
próbował tego drugi raz.

## Co się okazało zamiast

Sprawdziłem, czym te sześć utworów różni się od pozostałych. Odpowiedź jest
jednoznaczna i nie ma nic wspólnego z długością grania:

**Wszystkie sześć to DRUGIE wystąpienie utworu, który Janek zagrał dwa razy.**
Sześć na sześć.

| set | pozycje tego samego pliku | bez zamka |
|---|---|---|
| Open Deck | 1 i **3**, 5 i **7**, 9 i **11** | 3, 7, 11 |
| Premier | 3 i **5**, 4 i **7**, 11 i **13** | 5, 7, 13 |

Open Deck ma 19 pozycji, ale tylko **16 unikalnych plików**; Premier 18 pozycji
i **14 plików**. To nie są różne utwory — to powroty do tego samego nagrania.

Dlaczego to psuje zamek: dopasowanie szuka odcisku całego utworu w oknie miksu,
a przy powtórce ten sam odcisk pasuje w dwóch miejscach nagrania. Kotwice z
różnych odcinków okna mogą wskazać **różne wystąpienia**, konsensus się nie
zbiera i zamek nie powstaje. Mechanizm zadziałał prawidłowo: odmówił zamiast
zgadnąć, które wystąpienie ma na myśli.

## Ile to kosztuje

Jeden utwór bez zamka psuje **dwa** szwy — ten przed nim i ten po nim. Sześć
utworów zabiera więc około dwunastu szwów z trzydziestu pięciu.

## Co by to naprawiło (nie zrobione, do osobnej decyzji)

Ograniczyć obszar szukania tak, żeby okno drugiego wystąpienia **nie mogło**
sięgnąć pierwszego — dziś jedno z okien kandydujących wychodzi 35 s poza koniec
markera. To zmiana w rygorze dopasowania, a nie w sposobie cięcia okna, więc
wymaga własnego progu i własnego pomiaru. Ryzyko jest realne: zbyt ciasne okno
odbierze zamki, które dziś działają.

## Uwaga uboczna z przebiegu

Przy okazji pełnego przeliczenia wyszły dwa szwy pominięte z **innego** powodu
niż brak zamka: „jeden z decków nigdy nie przekroczył podłogi" (szwy 8 i 12 w
Open Deck). To osobna sprawa — utwór był w miksie tak cicho, że nie dało się
zmierzyć jego obecności.
