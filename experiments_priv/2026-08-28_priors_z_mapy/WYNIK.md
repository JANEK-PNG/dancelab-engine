# Wynik: baza jest PORZĄDKIEM, ale test znalazł coś innego i mocniejszego

Zmierzone 2026-08-28 na 2304 szwach z mapy DJ-ów (444 DJ-ów, 489 setów),
przeciw losowym parom z tych samych setów (661 pul). Metoda skopiowana bez
zmian z `scripts/corpus_priors.py`. Próg zarejestrowany w `HIPOTEZA.md` PRZED
policzeniem czegokolwiek.

## Rozliczenie z progiem

| lift | mapa | przedział 95% | korpus | różnica |
|---|---|---|---|---|
| harmonia `exact` | 1,158 | [0,983 – 1,363] | 1,25 | 7,3% |
| tempo `0-2%` | 1,432 | [1,309 – 1,566] | 1,219 | 17,5% |

Próg mówił: DŹWIGNIA przy ≥25% różnicy, PORZĄDEK przy obu w ±15%, między nimi
SZARA STREFA. Harmonia mieści się w ±15%, tempo wypada na 17,5%.

**Werdykt wg zarejestrowanego progu: SZARA STREFA.** Nie naginam go po fakcie.
Nowy sygnał nie jest na tyle silny, żeby przepisywać priors.

Odpowiedź na pytanie, które ten test miał zamknąć: **baza jest porządkiem, nie
dźwignią.** Oszczędza realną pracę przy zszywaniu czterech światów
identyfikatorów, ale nie ruszyła liczby, na której stoi decyzja.

## Czego próg nie przewidział, a co jest ważniejsze

Bootstrap (2000 losowań) pokazał rzecz, której nie obejmowało kryterium
wielkości efektu:

* **Tempo różni się od korpusu ISTOTNIE.** Przedział [1,309 – 1,566] nie
  zawiera wartości korpusowej 1,219. DJ-e z mapy trzymają się blisko tempem
  wyraźnie mocniej niż DJ-e z korpusu.
* **Harmonia nie działa.** Przedział [0,983 – 1,363] zawiera **1,0**, czyli
  nie da się odróżnić od braku efektu. Na 2304 szwach zgodność harmoniczna
  nie odróżnia wyboru DJ-a od losowej pary z tego samego setu.

To drugie potwierdza się w surowym rozkładzie: **59,7% wszystkich przejść na
mapie jest harmonicznie `risky`** (lift 0,961 — praktycznie przypadek).
Zgodność tonacji jest u tych DJ-ów mniejszością, a nie regułą.

Pełne lifty:

```
HARMONIA                 mapa   losowo    lift      n
  relative_major_minor   1,95%    1,39%   1,403     45
  exact                 10,81%    9,33%   1,159    249
  adjacent_same_mode    14,24%   13,50%   1,055    328
  cautious              13,32%   13,67%   0,974    307
  risky                 59,68%   62,11%   0,961   1375

TEMPO (ΔBPM)             mapa   losowo    lift      n
  0-2%                  34,81%   24,31%   1,432    802
  2-4%                  22,22%   20,36%   1,091    512
  4-6%                  12,15%   11,89%   1,022    280
  6-10%                 11,55%   14,80%   0,780    266
  >10%                  19,27%   28,65%   0,673    444
```

Tempo ma czysty, monotoniczny kierunek: im bliżej, tym częściej niż przypadek;
powyżej 10% różnicy DJ-e wyraźnie unikają (0,673). Harmonia takiego porządku
nie ma.

## Co z tym zrobić — i czego NIE zrobiłem

Nie zmieniam priors. Próg na to nie pozwala, a jedna sesja pomiarowa nie jest
podstawą do przepisania wag, które przeszły własną walidację.

Nowa hipoteza do OSOBNEGO sprawdzenia (nie wynik tego testu): **tempo niesie
istotnie więcej informacji o wyborze DJ-a niż harmonia**, przynajmniej na tej
scenie. Jeśli to się potwierdzi, `DescriptorWeights` przecenia harmonię.
Test, który to rozstrzygnie, musi być zarejestrowany osobno i z własnym progiem.

## Zastrzeżenie, którego nie wolno pominąć

Wszystkie 2304 szwy przeszły przez filtr „Janek ma ten plik w bibliotece".
To **nie jest losowa próbka** z mapy 21 015 szwów — jest warunkowana jego
zbiorem. Cokolwiek z tego wynika, dotyczy przecięcia mapy z jego biblioteką,
nie mapy jako takiej. Pomiar wykonany na jednorazową zgodę Janka z 28.08.
