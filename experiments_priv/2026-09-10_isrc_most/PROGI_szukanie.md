# Most przez wyszukiwanie (wykonawca + tytuł) — progi PRZED pomiarem (2026-09-11)

Most ISRC dał tożsamość Apple 171 z 272 plików. Zostaje 101: 61 bez ISRC w tagu
(w tym wszystkie 25 WAV) i 40 z ISRC, którego katalog `pl` nie zna.

Droga zastępcza: `GET /v1/catalog/{sf}/search?types=songs&term=<wykonawca tytuł>`.

## Reguła dopasowania (ustalona teraz, nie po wyniku)
Kandydat przechodzi tylko, gdy JEDNOCZEŚNIE:
1. znormalizowany tytuł zgadza się dokładnie (NFKD bez akcentów, małe litery, bez
   nawiasów wersji, bez „feat. …", tylko litery i cyfry);
2. co najmniej jeden wykonawca z pliku jest w wykonawcach kandydata (ta sama normalizacja);
3. długość różni się o ≤ 3 s (gdy plik zna długość; bez długości — odrzucamy).
Dokładnie jeden kandydat po regule → dopasowanie. Zero albo więcej niż jeden → brak.

## Sprawdzian (prawda z ISRC)
Tę samą regułę puszczamy na plikach, których id już znamy z ISRC (128 ISRC, 171 plików).
- **Precyzja** = trafione id / wszystkie dopasowania. **Próg: ≥ 98 %.**
- Pokrycie raportujemy, bez progu.
- Precyzja < 98 % → reguła nie wchodzi do produktu, pliki bez ISRC zostają bez tożsamości.

## Zastosowanie
Tylko przy zdanym progu: reguła na 101 plikach bez tożsamości, wynik do mostu jako
osobne źródło (`zrodlo: "szukanie"`), żeby dało się je odróżnić od ISRC.
