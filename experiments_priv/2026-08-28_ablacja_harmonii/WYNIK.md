# Wynik: harmonia DZIAŁA. Mój wniosek z mapy nie przeszedł replikacji.
# Przy okazji: pętla priors stała na zepsutym pomiarze.

Zmierzone 2026-08-28 na 1604 obserwacjach z korpusu (znamy wybór DJ-a **i**
kandydatów, których pominął). Próg zarejestrowany w `HIPOTEZA.md` przed
liczeniem.

## Najpierw: błąd, który unieważnił poprzedni pomiar

`scripts/priors_validation.py` liczył wagi ręczne tak:

```python
s += 0.4 * harmonic_compatibility(a["camelot"], b["camelot"])   # ŹLE
```

`harmonic_compatibility` zwraca obiekt `HarmonicResult`, nie liczbę. Mnożenie
rzucało `TypeError` prosto w `except Exception: pass` kilka linii niżej, więc
**składnik harmoniczny nigdy nie wszedł do żadnego wyniku ręcznego** podanego
przez ten skrypt. Wykryte przypadkiem: w ablacji wariant „bez harmonii" dawał
wynik identyczny co do trzeciego miejsca po przecinku, co jest niemożliwe,
jeśli składnik cokolwiek robi.

Silnik jest zdrowy — `set_builder`, `mixability`, `tui` i pozostałe skrypty
używają `harm.harmonic_compatibility_score` poprawnie. Błąd był wyłącznie w
narzędziu pomiarowym.

### Co to zmienia w pętli priors

| | przed naprawą | po naprawie |
|---|---|---|
| wagi ręczne, top1 | 20,7% | **25,2%** |
| wagi zmierzone, top1 | 24,3% | 24,3% |
| percentyl rangi (mniej = lepiej) | 0,442 / 0,427 | **0,423** / 0,427 |
| werdykt | „zmierzone biją ręczne" | **odwrócony**, p = 0,668 |

Uczciwy wniosek: **wagi zmierzone nie biją ręcznych.** Kierunek się odwrócił,
ale przy p = 0,668 różnica jest nieistotna w obie strony — poprawna odpowiedź
brzmi „nie da się ich rozróżnić na tych danych", a nie „ręczne wygrywają".
Poprzedni wniosek („zmierzone > ręczne") był artefaktem porównania modelu
z harmonią przeciw modelowi, któremu harmonia po cichu wypadła.

Kopia poprzedniego raportu: `validation_v1_PRZED_NAPRAWA.json`.

## Właściwy test: ablacja

```
=== wagi ręczne                        === wagi zmierzone
wariant        pct_rank  top1%      p   |  pct_rank  top1%       p
  pełny           0,423   25,2      —   |     0,427   24,3       —
  bez harmonii    0,442   20,7  0,0093  |     0,439   19,5  0,0833
  bez tempa       0,466   24,9  0,0000  |     0,455   21,3  0,0013
  losowy          0,490   14,4  0,0000  |     0,505   14,1  0,0000
```

**Kontrole poprawności przeszły:** usunięcie tempa istotnie szkodzi (p ≈ 0),
losowy wypada najgorzej. Narzędzie mierzy.

**Werdykt wg zarejestrowanego progu: HARMONIA DZIAŁA.** Usunięcie jej z wag
ręcznych pogarsza wynik istotnie (p = 0,0093; top1 spada z 25,2% na 20,7%).
Próg mówił wprost, co wtedy zrobić: *„efekt z mapy był własnością tamtej sceny
albo tamtego filtra, a nie własnością harmonii. Silnika nie ruszam i tak to
zapisuję."* Tak robię.

## Co to znaczy dla wczorajszego ustalenia z mapy DJ-ów

Na 2304 szwach z mapy lift harmoniczny miał przedział zawierający 1,0 i
wyglądało to na „harmonia nie odróżnia wyboru DJ-a". **Nie replikuje się.**
Na niezależnym zbiorze z kandydatami harmonia wnosi istotną informację.

Najprostsze wyjaśnienie różnicy — i na razie tylko hipoteza — jest takie, że
tamten pomiar nie miał czego porównywać: baseline losował pary z tego samego
setu, a DJ-e i tak grają w obrębie wąskiego zakresu tonacji, więc „losowa para
z tego setu" jest harmonicznie podobna do prawdziwego przejścia. Zbiór z
kandydatami tego problemu nie ma, bo kandydaci są realną alternatywą, którą DJ
odrzucił.

**Wniosek praktyczny: nie ruszam wag silnika.** Propozycja obniżenia wagi
harmonii, którą wczoraj zapisałem jako hipotezę, zostaje obalona przez ten test.
