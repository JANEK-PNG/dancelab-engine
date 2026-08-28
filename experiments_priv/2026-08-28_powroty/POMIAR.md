# Reguła powrotu: zagraj, wpuść jeden, wróć na krócej

Zmierzone 2026-08-28 na dwóch nagranych setach Janka (Open Deck 47 min,
Premier 42 min, razem 37 pozycji w tracklistach z plików cue).

Odkryte przypadkiem: sześć utworów, których nie dało się zsynchronizować z
nagraniem, okazało się **drugimi zagraniami** tego samego utworu. Zapytany
wprost, czy to chwyt czy przypadek, Janek odpowiedział: **świadomy chwyt**.

## Liczby

**7 powrotów na 37 pozycji (19%)** — co piąta pozycja w tracklistach to powrót
do utworu granego wcześniej.

| cecha | wartość |
|---|---|
| przerwa przed powrotem | 3,2 – 6,1 min, **mediana 4,5 min** |
| utworów pomiędzy | **jeden w 6 z 7** przypadków (raz dwa) |
| drugie zagranie krótsze | **7 z 7 — zawsze** |
| ile krótsze | 33 – 70% pierwszego, **mediana 42%** |
| typowa długość | pierwsze 140 s → drugie 77 s |
| korelacja długości pierwszego i drugiego | **0,85** |

Ta ostatnia liczba jest najciekawsza: im dłużej utwór grał za pierwszym razem,
tym dłużej wraca. To nie jest odruch — to proporcja.

## Kształt chwytu

```
   utwór A  ──────────────  (140 s)
   utwór B                  ──────────  (jeden, inny)
   utwór A  ────────         (77 s, około 42% pierwszego)
```

Klasyczna forma **A–B–A**, tylko że powrót jest skrócony. Do tego, co widać w
dopasowaniu kotwic, przy powrocie Janek **skacze wewnątrz utworu** hot cue'ami
albo pętlą: cztery kolejne odcinki miksu trafiły w 30 s, 119 s, 39 s i 112 s
tego samego nagrania. Nie odtwarza go od nowa — wybiera z niego fragmenty.

## Czego silnik nie umie

Dziś `set_builder` układa **ciąg różnych utworów**. Nie ma w nim pojęcia:

* **powrotu** — utwór raz zagrany wypada z puli;
* **skróconego wznowienia** — każde wejście traktowane jest tak samo;
* **skoku wewnątrz nagrania** — plan mówi „graj od cue", nie „graj 30 s, skocz
  na 119 s, wróć".

Skoro to jest 19% pozycji w realnych setach Janka i wykonywane z regularną
proporcją, silnik pomija jedną piątą tego, co ten DJ faktycznie robi.

## Zastrzeżenia

* **n = 7**, dwa sety, jeden DJ. To jest obserwacja o Janku, nie o DJ-ach.
  Sprawdzenie na mapie (2304 szwy z analizami) wymagałoby wykrycia powtórek w
  tracklistach korpusu — do zrobienia, bo dane są.
* Nie wiem, **czy powrót brzmi tak samo** jak pierwsze zagranie — skoki
  wewnątrz utworu sugerują, że nie, ale tego nie zmierzyłem.
* Nie wiem, **dlaczego** akurat jeden utwór pomiędzy. Może to długość, po
  której ucho zapomina, a może po prostu tak wyszło przy siedmiu przypadkach.
