# Czy powroty są powszechne? Główna liczba mówi „nierozstrzygnięte",
# ale jej struktura mówi więcej niż ona sama

Zmierzone 2026-08-28 na 42 904 pozycjach tracklist z mapy DJ-ów.
Próg zapisany w `HIPOTEZA_MAPA.md` przed zapytaniem.

## Rozliczenie z progiem

Powrót liczony jako ten sam `utwor_id` na dwóch pozycjach tego samego setu,
z odstępem **≥ 2** (sąsiednie odsiane jako podejrzane — u Janka odstęp wynosił
zawsze 2 lub 3; w korpusie 18 przypadków miało odstęp 1, co wygląda na
podwójny wpis, nie na powrót).

**Wynik główny: 80 z 2071 setów = 3,9%.**

Próg mówił: ≥10% powszechne, <3% chwyt Janka, pomiędzy nierozstrzygnięte.
**Formalnie: NIEROZSTRZYGNIĘTE** — i tak to nazywam, planera nie przebudowuję.

## Struktura, której próg nie przewidział

Sety, w których wykryto powrót, są **ponad dwa razy dłuższe** od pozostałych:
38,4 pozycji wobec 16,9. To skłoniło mnie do sprawdzenia zależności od
kompletności zapisu:

| tracklisty o długości | ile setów | z powrotem |
|---|---|---|
| wszystkie | 2071 | **3,9%** |
| ≥ 20 pozycji | 790 | **7,2%** |
| ≥ 30 pozycji | 294 | **12,6%** |
| ≥ 40 pozycji | 107 | **16,8%** |

Wzrost jest **monotoniczny**. Najprostsze wyjaśnienie: tracklisty są spisywane
ręcznie przez ludzi w serwisach, a **powrót do utworu jest tym, co najłatwiej
pominąć** — wygląda jak duplikat i bywa usuwany przy przepisywaniu. Krótkie
tracklisty to zapisy niepełne, nie sety bez powrotów.

Jeśli tak jest, **3,9% to dolna granica, nie częstość**. Przy najpełniejszych
zapisach wychodzi 16,8%, czyli blisko 19%, które zmierzyłem u Janka.

**Czego to NIE dowodzi:** podzbiór „długie sety" wybrałem po zobaczeniu wyniku,
więc to nie jest niezależny test. Pokazuję strukturę, nie ogłaszam progu za
przekroczony.

## Co z tym zrobić

**Nie przebudowuję planera** — próg na to nie pozwala, a dowód jest poszlakowy.

Test, który by to rozstrzygnął uczciwie: wziąć sety, dla których mamy
**nagranie audio** (nie tylko tracklistę spisaną ręcznie) i policzyć powroty
z dźwięku. Wtedy nikt niczego nie pominął przy przepisywaniu. Mamy takie dwa —
oba Janka, oba z powrotami. Trzeci by wystarczył, żeby to przestało być n=2.

## Liczba, która została

Odstęp w pozycjach między pierwszym a drugim zagraniem, w całym korpusie:
**najczęstszy jest 2** (24 przypadki), potem 3 (10). Dokładnie tak, jak u
Janka — jeden utwór pomiędzy. To akurat nie jest artefaktem zapisu i wspiera
tezę, że kształt chwytu jest wspólny, nawet jeśli częstość jest sporna.
