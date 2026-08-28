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

---

# Druga próba (`HIPOTEZA_2.md`): też obalona — i tym razem wiemy dlaczego

Poprawka: dla utworu granego drugi raz okna szukania przycięte do jego własnego
czasu, żeby nie mogły sięgnąć poprzedniego zagrania.

**Wynik: zero nowych zamków** (16/19 przed i po), żaden nie zniknął. Zgodnie z
progiem — cofnięte.

## Prawdziwy powód, odczytany z kotwic

Dla pozycji 3 (Medjool, drugie zagranie, 61 s) cztery kolejne odcinki miksu
dopasowały się do **tych miejsc w utworze**:

| odcinek miksu | pozycja w utworze | wyliczony origin |
|---|---|---|
| 241–253 s | 30,3 s | 212,5 s |
| 253–265 s | 118,6 s | 141,4 s |
| 265–277 s | 38,8 s | 228,5 s |
| 277–289 s | 112,0 s | 171,5 s |

Gdyby utwór leciał normalnie, pozycje rosłyby równo: 30 → 42 → 54 → 66.
Zamiast tego **skaczą tam i z powrotem między okolicą 30–40 s a 112–119 s**.

**Janek nie odtwarza tego utworu — on po nim skacze**, hot cue'ami albo pętlą.
Rozrzut origin wynosi 87 sekund przy tolerancji 0,4 s.

## Co to znaczy

`lock()` opiera się na założeniu, że nagranie ma **jeden** punkt startu na
zegarze miksu. Przy skakaniu po utworze to założenie po prostu przestaje
obowiązywać — nie ma jednego origin, który cokolwiek by opisywał.

To jest **granica metody, nie usterka**. Mechanizm zachował się prawidłowo:
odmówił zamiast wybrać jeden z czterech sprzecznych wyników.

Naprawa wymagałaby innego podejścia — dopasowania **odcinkami** zamiast jednego
origin, czyli w praktyce wykrywania skoków w utworze. To osobne zadanie, nie
regulacja okna, i wymaga własnej hipotezy z własnym progiem.

## Obserwacja o graniu, nie o kodzie

Sześć powrotów do utworu na 37 pozycji w dwóch setach, za każdym razem ze
skakaniem po nagraniu. To nie jest artefakt — to technika. **Silnik dziś nie
umie zaplanować powrotu do utworu ani skoku wewnątrz niego**, a Janek robi
jedno i drugie regularnie.
