# Sześć utworów bez zamka: czy to za krótkie granie, czy za drobny podział?

**Zapisane 2026-08-28 PRZED zmianą kodu.**

## Stan

Z 35 szwów w dwóch nagranych setach Janka zmierzonych jest **21**. Pominiętych
14, wszystkie z powodem „brak zamka".

Diagnoza: zawiodło **sześć utworów**, nie czternaście — ale jeden utwór bez
zamka psuje **dwa** szwy (przed nim i po nim).

| set | pozycja | grał | mediana setu |
|---|---|---|---|
| Open Deck | 3 | 61 s | 155 s |
| Open Deck | 7 | 98 s | |
| Open Deck | 11 | 120 s | |
| Premier | 5 | 77 s | 140 s |
| Premier | 7 | 78 s | |
| Premier | 13 | 50 s | |

**Wszystkie sześć grały krócej niż mediana.** Żaden inny wzorzec się nie
narzuca — pliki źródłowe istnieją dla wszystkich 37 utworów, sprawdzone.

## Hipoteza

`_try_window` dzieli okno zawsze na **cztery** odcinki. Przy krótkim graniu
tylko jedno z czterech okien kandydujących mieści się w czasie, ma około 37 s,
a po podziale zostają odcinki po 9 s — za krótkie, żeby dopasowanie było pewne.

Poprawka: liczba podziałów **zależna od długości okna**, tak żeby odcinek miał
co najmniej ~15 s. Krótkie okno → dwa dłuższe odcinki zamiast czterech krótkich.

**Czego NIE zmieniam:** progu zgodności. Nadal wymagane ≥2 niezależne kotwice
nazywające ten sam moment w granicach 0,4 s. Docstring mówi wprost, że ten test
„is kept strict and never relaxed" — zmieniam wyłącznie sposób dzielenia okna,
nie rygor.

## Próg

* **POPRAWKA ZOSTAJE** — przybywa co najmniej **3 zamki** (z 31 na ≥34), a
  rozrzut (`spread_ms`) nowych zamków mieści się w tym, co mają obecne
  (mediana obecnych to kilkanaście ms, żaden nie przekracza 35 ms).
* **POPRAWKA WRACA** — przybywa 0–1 zamków, albo nowe mają rozrzut powyżej
  100 ms. Zamek niepewny jest gorszy niż jego brak: mierzymy nim ruch ręki
  z dokładnością do dziesiątych sekundy.
* **NIEROZSTRZYGNIĘTE** — 2 nowe zamki. Zapisuję i zostawiam kod prostszy.

Dodatkowa kontrola: **żaden z 31 obecnych zamków nie może zniknąć ani pogorszyć
rozrzutu o więcej niż 10 ms.** Jeśli zniknie, poprawka psuje więcej niż naprawia.
