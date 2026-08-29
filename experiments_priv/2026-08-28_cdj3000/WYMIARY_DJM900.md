# DJM-900NXS2 — pozycje z rzutu wektorowego (29.08.2026)

**Źródło:** instrukcja DJM-900NXS2 (`manuals.plus`, wersja skrócona),
**strona 7 „Part names → Control Panel"**. To nie jest obrazek — to grafika
wektorowa: mamy współrzędne każdej kreski i każdego napisu na panelu.
Dlatego pozycje wyciągamy z pliku, a nie z pikseli po progu jasności.

## Skala — założenie, które się obroniło

Ta instrukcja **nie ma tabeli danych technicznych**, więc szerokości 332 mm
nie wziąłem z niej, tylko z danych katalogowych producenta. To było założenie.

Sprawdzian, który je potwierdza: obrys panelu na rysunku ma **381,3 × 474,6 pt**,
czyli proporcję **0,803**. Katalogowe 332 × 414,5 mm dają **0,801**.
Różnica **0,3%** — rysunek zgadza się z liczbą, której z niego nie wziąłem.
Gdyby założenie było fałszywe, proporcja by się rozjechała.

Skala: **0,8707 mm/pt**. Wysokość panelu wyliczona z rysunku: **413,2 mm**
wobec katalogowych 414,5.

## Zmierzone

| element | pozycja (x, y) mm | wymiar |
|---|---|---|
| panel | 0, 0 | 332 × 413,2 |
| TRIM kanału 1–4 | 82,0 · 124,6 · 167,4 · 210,2 | — |
| **rozstaw kanałów** | — | **42,6 / 42,8 / 42,8 mm** |
| bloki EQ kanałów 1–4 | (81,2 · 124,8 · 167,8 · 211,0), y 207,8 | 39,9 × 35,2 |
| sekcja prawa (BEAT FX / wyświetlacz) | 296,6 · 161,5 | 57,6 × 124,6 |
| sekcja lewa (mikrofon / słuchawki) | 30,9 · 223,9 | 52,0 × 67,4 |
| napis CROSS FADER | ok. 140 · 367 | — |

**Dlaczego rozstaw kanałów jest dowodem, a nie ciekawostką:** trzy kolejne
odstępy wyszły 42,6, 42,8 i 42,8 mm. Gdyby skala albo obrys były źle dobrane,
te trzy liczby nie byłyby równe — a są, z dokładnością do dwóch dziesiątych.

## Czego brakuje

* **Suwaki kanałów i crossfader** są narysowane ścieżkami, nie prostokątami,
  więc nie wpadły w to sito. Mamy ich okolicę z napisów; same suwaki trzeba
  wyciągnąć osobno (albo ze ścieżek, albo odczytać z siatki).
* **Potwierdzenie 332 mm z instrukcji pełnej** — proporcja je popiera, ale to
  nadal liczba spoza dokumentu, który mamy w ręku.
