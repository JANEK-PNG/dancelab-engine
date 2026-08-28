# Czy baza jest dźwignią, czy porządkiem?

**Zarejestrowane 2026-08-28, PRZED policzeniem czegokolwiek.**
Ziarno losowe: 20260828. Baseline losowany ziarnem 11 (jak w `scripts/corpus_priors.py`).

## Skąd to pytanie

Zewnętrzny recenzent postawił zarzut, którego nie da się odeprzeć kodem: baza
nie dodała ani jednego pomiaru (`bas_wstrzymany` 0 z 21 015, oceny 0 ze 158).
Jeśli to prawda, baza jest porządkiem w identyfikatorach — realną oszczędnością
pracy, ale nie dźwignią wyniku. Nazwanie tego wprost jest warte więcej niż
ładna narracja.

## Co dokładnie mierzę

Powtarzam metodę z `scripts/corpus_priors.py` — bez zmian, żeby liczby były
porównywalne:

* **real** = 2304 szwy z mapy DJ-ów, dla których mamy analizę OBU utworów
  (444 DJ-ów, 489 setów). Cechy liczone funkcją silnika `harmonic_relation()`
  i `nearest_bpm_variant()`, dokładnie jak w korpusie.
* **chance** = losowe pary utworów **z tego samego setu** (658 setów ma pulę
  ≥2 utworów z analizą), tyle samo par co real.
* **lift** = udział(real) / udział(chance), osobno dla relacji harmonicznej
  i dla kubełka ΔBPM.

Porównuję z korpusem (6144 przejść, `validation_v1.json` + `priors_v1.json`):
harmonia `exact` = **1,25**, tempo `0-2%` = **1,219**.

## Próg — ustalony teraz, nie po wyniku

Kotwicą jest **kierunek i siła dwóch liftów, które w korpusie są najmocniejsze**:
`exact` (harmonia) i `0-2%` (tempo).

* **DŹWIGNIA** — mapa mówi coś, czego korpus nie mówił: przynajmniej jeden
  z dwóch liftów różni się od korpusowego o **≥ 25% względnie**, przy ≥200
  parach w tym kubełku. Wtedy 2304 szwy niosą własny sygnał i warto je wpiąć
  w priors.
* **PORZĄDEK** — oba lifty mieszczą się w **± 15%** korpusowych. Wtedy baza
  potwierdza to, co już wiedzieliśmy, i tak trzeba ją nazwać w ledgerze:
  oszczędza pracę, nie rusza wyniku.
* **SZARA STREFA** — różnica między 15% a 25%, albo za mało par. Nie
  dopisuję wtedy niczego do priors i mówię wprost, że test nie rozstrzygnął.

Dodatkowo, niezależnie od powyższego: jeśli lift `exact` wyjdzie **< 1,0**
(czyli DJ-e z mapy unikaliby zgodności harmonicznej), traktuję to jako sygnał
błędu w danych, nie jako odkrycie — i szukam błędu, zanim cokolwiek ogłoszę.

## Czego ten test NIE rozstrzygnie

Nie powie, czy silnik gra lepiej. Mierzy wyłącznie, czy nowe 2304 szwy niosą
inny rozkład preferencji niż korpus. Zgodność z korpusem nie jest porażką —
jest potwierdzeniem sygnału na **innej scenie** (festiwale, 444 DJ-ów) niż ta,
z której priors powstały.

## Warunek brzegowy (zgoda Janka z 28.08)

Wszystkie 8260 analiz pochodzi z biblioteki Janka. Szwy są cudze — z mapy —
ale cecha przypisana każdemu szwu (bpm, tonacja) jest liczona z pliku, który
akurat on ma. Zapytany wprost, czy wolno tak zrobić, odpowiedział „działaj".
Traktuję to jako **jednorazowe zwolnienie z zakazu z 11.08 dla tego pomiaru**,
nie jako zniesienie reguły.

Skutek uboczny do zapamiętania: pokrycie 2304 szwów jest warunkowane tym, co
Janek posiada w bibliotece. To nie jest losowa próbka z mapy i nie wolno
raportować jej jako „szwy DJ-ów festiwalowych" bez tego zastrzeżenia.
