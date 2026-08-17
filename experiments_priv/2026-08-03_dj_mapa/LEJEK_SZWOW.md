# Lejek szwów — ile relacji naprawdę mamy i gdzie się gubią

Policzone 2026-08-14, po zarzucie: „bez mianownika 492 nic nie znaczy".
Zarzut był słuszny i mianownik zmienia wniosek.

## Lejek

| poziom | ile | z możliwych |
|---|---:|---:|
| **możliwe** — każda para sąsiadów w każdej tracklistcie | 40 389 | 100% |
| **zaobserwowane** — set ma pewny adres nagrania | 22 276 | 55,2% |
| **zidentyfikowane** — oba końce mają nazwę | 21 015 | 52,0% |
| **zlokalizowane w czasie** | **492** | **1,22%** |
| zweryfikowane przez człowieka | 0 | 0% |

Materiał na trajektorię, nie pojedyncze przejście:
**174 sety mają ≥1 zmierzony szew · 28 ma ≥5 · 7 ma ≥10.**
Najlepszy: `Justin Shaffer — Phonobar all night vinyl session`, **29 zmierzonych szwów**.

## Wniosek, który obala tezę ogólniejszą

Spadek NIE jest równomierny. Między „możliwe" a „zidentyfikowane" tracimy
połowę — i to z powodu banalnego: brakującego adresu nagrania. **Ale między
„zidentyfikowane" a „zmierzone" tracimy czterdziestokrotnie.**

Czyli teza „relacje są drogie" jest **za gruba**. Rozkładając koszt relacji
na składowe, jak proponuje krytyka:

```
C_relacji = C_identyfikacji + C_dopasowania + C_temporalizacji
          + C_kontekstu + C_walidacji
```

nasz pomiar mówi wprost: **`C_identyfikacji` jest prawie darmowa,
`C_temporalizacji` zjada wszystko.** 94% zaobserwowanych szwów ma oba końce
nazwane. Zaledwie 2,2% ma czas.

## Dlaczego akurat czas — i to jest sedno

Bo **nazwy ktoś już zapisuje, a czasu nie zapisuje nikt.**

Tracklisty istnieją, bo pełnią czyjąś funkcję: oddają autorstwo, pozwalają
znaleźć kawałek, budują prestiż serii. RA płaci redakcji za ich spisywanie.
MixesDB ma wolontariuszy. To są dane, które powstają, bo komuś się opłacają.

Znacznik czasu nie opłaca się nikomu. Nie służy ani artyście, ani wydawcy,
ani serwisowi. Stąd rozkład źródeł tego, co zmierzone:

```
komentarz SoundCloud   461   ← publiczność, przypadkiem
opis wrzutu             31   ← sam DJ, rzadko
baza kuratorowana        0   ← RA, MixesDB, NTS: ANI JEDEN
```

**Jedyne źródło rzeczy, której najbardziej potrzebujemy, to produkt uboczny
zachowania fanów.** Ktoś pisze „ID?" o 47:12, bo chce znać kawałek — i przy
okazji zostawia nam znacznik szwu.

## Poprawiona teza

Nie: *relacje są droższe od obiektów*.

Lecz: **koszt relacji jest zdominowany przez ten jej wymiar, którego żaden
uczestnik ekosystemu nie ma powodu rejestrować.**

To jest mocniejsze, bo mówi też, gdzie szukać: nie „więcej danych", tylko
**ten wymiar, na którym nikomu nie zależy**. I daje przewidywanie sprawdzalne
w innych domenach: wszędzie tam, gdzie relacja ma wymiar bez właściciela,
tam będzie wąskie gardło.

## Czego ten pomiar NIE mówi

* Nie mierzy kosztu w czasie ani pieniądzu — tylko pokrycie. Prawdziwy
  `RCR` wymaga policzenia, ile zapytań i ile minut kosztuje jeden rekord
  na każdym poziomie.
* Mianownik „możliwe" liczy pary sąsiadów **w tracklistach, które mamy**.
  Prawdziwe „możliwe" to wszystkie przejścia we wszystkich setach świata —
  liczba nieznana i pewnie o kolejne rzędy wielkości większa.
* Zero zweryfikowanych przez człowieka. Kolumna istnieje i jest pusta;
  puste znaczy „nie wiem", nie „nie".
