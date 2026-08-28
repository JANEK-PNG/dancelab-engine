# Czy harmonia w ogóle wnosi informację o wyborze DJ-a?

**Zarejestrowane 2026-08-28, PRZED policzeniem czegokolwiek.** Ziarna: bootstrap 3.

## Skąd pytanie

Na 2304 szwach z mapy DJ-ów zgodność harmoniczna nie odróżniła wyboru DJ-a od
losowej pary z tego samego setu — przedział ufności liftu `exact` zawierał 1,0
(`experiments_priv/2026-08-28_priors_z_mapy/WYNIK.md`). Tempo działało mocno.

Tamten pomiar nie może sam siebie potwierdzić. Ten test idzie na **zupełnie
innym zbiorze**: 1604 obserwacje z korpusu, w których znamy nie tylko to, co DJ
zagrał, ale też **czego nie wybrał** (kandydaci). To pozwala zapytać wprost:
czy model bez harmonii przewiduje wybór DJ-a gorzej?

## Metoda — ablacja

Biorę scorery ze `scripts/priors_validation.py` bez zmiany i odejmuję po jednym
składniku:

* `pelny` — tempo + harmonia (to, co dziś),
* `bez_harmonii` — samo tempo,
* `bez_tempa` — sama harmonia,
* `losowy` — podłoga odniesienia.

Dla wag ręcznych (`score_hand`) i mierzonych (`score_measured`) osobno.

Metryki: `pct_rank_mean` na wszystkich przypadkach (0 = ideał, 0,5 = losowo),
`top1_pct` na przypadkach z ≥5 kandydatami, oraz **sparowany bootstrap** na
tych samych przypadkach — bo porównuję modele na tych samych danych.

## Próg — ustalony teraz

**Pytanie główne: czy `bez_harmonii` jest gorszy od `pelny`?**

* **HARMONIA NIC NIE WNOSI** — `pct_rank_mean` pogarsza się o mniej niż 0,01,
  a sparowany bootstrap daje **p > 0,05**. Wtedy ustalenie z mapy potwierdza
  się na drugim, niezależnym zbiorze i mam prawo zaproponować zmianę wag.
* **HARMONIA DZIAŁA** — bootstrap daje **p ≤ 0,05**. Wtedy efekt z mapy był
  własnością tamtej sceny (albo tamtego filtra „Janek ma ten plik”), a nie
  własnością harmonii. Silnika nie ruszam i tak to zapisuję.
* **NIEROZSTRZYGNIĘTE** — cokolwiek pomiędzy. Nie dopisuję wniosku.

## Kontrola poprawności testu (sanity check)

Jeżeli `bez_tempa` **nie jest** istotnie gorszy od `pelny`, to znaczy, że ten
zestaw danych nie mierzy niczego i **cały test jest nieważny** — bo wiemy z
dwóch niezależnych pomiarów, że tempo niesie sygnał. W takim wypadku nie
raportuję wyniku o harmonii, tylko zgłaszam, że narzędzie pomiarowe jest ślepe.

Druga kontrola: `losowy` musi wypaść wyraźnie najgorzej. Jeśli nie wypada,
znaczy to samo.

## Czego ten test NIE rozstrzyga

Nie mówi, że harmonia jest nieważna w graniu. Mówi wyłącznie, czy **nasza
reprezentacja** harmonii (Camelot + `harmonic_relation`) niesie informację o
tym, który utwór DJ wybrał następny. DJ może zestrajać tonacje uchem, a nasz
opis może tego nie łapać — to dwie różne rzeczy i wynik nie odróżni ich od
siebie.
