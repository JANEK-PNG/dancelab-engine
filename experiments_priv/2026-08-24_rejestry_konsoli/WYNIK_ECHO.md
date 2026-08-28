# Kanałowanie echa: naprawa wierności, której pomiar NIE potwierdził

Zmierzone 2026-08-28. Próg zapisany w `PROG_ECHO.md` przed renderem.

## Co zmieniono

`graj_rejestr.py` dodawał echo do **całego miksu**. Na FLX4 BEAT FX działa na
wybrany kanał, a rejestr zapisuje pozycję przełącznika (`fx["kanal"]`) — model
po prostu tego pola nie czytał. Kanały są teraz trzymane osobno do końca
renderu, echo trafia na wybrany, suma powstaje na samym końcu.

## Wynik — poniżej progu

| miara | przed | po | zmiana |
|---|---|---|---|
| zgodność kształtu | 0,551 | 0,555 | +0,004 |
| całość | 0,557 | 0,563 | +0,006 |
| bas | 0,434 | 0,443 | +0,009 |
| środek | 0,408 | 0,407 | −0,001 |
| góra | 0,426 | 0,419 | −0,007 |

Próg wymagał **≥ 0,02** wzrostu, żeby poprawkę uznać za potwierdzoną, i mówił
wprost: przy zmianie poniżej 0,01 poprawka wraca, żeby nie zostawiać
skomplikowania bez pokrycia w pomiarze.

## Dlaczego mimo to zostaje

Bo test okazał się **bezprzedmiotowy**, a to jest inny stan niż „nie zadziałało".

W sesji `test_1` efekt był włączony od **28,5 s**, ale przełącznik kanału FX
ruszył się dopiero na **234 s** i **308 s**. Przez 200 z 312 sekund kanał stał
w pozycji, której nie znamy (ta sesja nie ma zapisu pozycji startowych), więc
model przyjmował CH1&2 — czyli zachowywał się **identycznie jak przed
poprawką**. Zmiana mogła zadziałać tylko na ostatnich ~78 sekundach.

Klasyfikuję to więc jako **naprawę wierności, nie poprawę wyniku**: model
przestał ignorować dane, które rejestr ma zapisane. Ta sama klasa co naprawa
`harmonic_compatibility` — kod robił coś innego, niż deklarował.

**Czego brakuje, żeby to sprawdzić:** sesji, w której przełącznik kanału FX
pracuje w środku grania, przy włączonym efekcie, najlepiej z zapisanymi
pozycjami startowymi. `ocena_sesja` (73,5 min, pozycje startowe TAK) może się
nadać, ale nie ma do niej nagrania audio.

## Uwaga o punkcie odniesienia

Ten baseline (0,551) jest **gorszy niż zapisany wcześniej w
`porownanie_test1.json`** (0,659), bo renderowałem bez parametrów hot cue,
których tamten przebieg używał. Do porównania A/B to bez znaczenia — obie
strony liczone tak samo — ale nie wolno tych liczb zestawiać z tamtymi.
