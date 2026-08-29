# CDJ-3000 — wymiary zmierzone z rzutu płaskiego (29.08.2026)

**Źródło geometrii:** instrukcja obsługi CDJ-3000, **strona 14 „Part names →
Top panel"** — rzut z góry, płaski. Nie zdjęcie, nie ujęcie pod kątem.
To jest warunek z `docs/metoda-ui-konsoli.md`: przy FLX4 pomiar z rysunku
w perspektywie dał jog 104 mm zamiast 140 i kosztował rundę poprawek.

**Skala:** ze specyfikacji na **stronie 83**: *„Max. external dimensions
329 mm (W) × 453 mm (D) × 118 mm (H)"*. Szerokość 329 mm podana ręcznie,
przyrząd (`scripts/rzut_na_siatke.py`, 1000 dpi) wyliczył **9,888 px/mm**.

**Kontrola poprawności:** wysokość obwiedni wyszła **446,5 mm** wobec 453 mm
ze specyfikacji — **1,4% poniżej**. Rzut nie obejmuje tylnego zawinięcia
obudowy, więc różnica w tę stronę jest oczekiwana. Skala liczona jest
z szerokości, więc ten naddatek nie wchodzi do wyniku.

## Zmierzone punkty odniesienia

Współrzędne od lewego górnego rogu panelu, w milimetrach.

| element | pozycja (x, y) | wymiar |
|---|---|---|
| panel | 0, 0 | 329 × 453 (446,5 zmierzone) |
| talerz jog — obrys zewnętrzny | 163,6 · 296,5 | **⌀ 202,2** |
| pierścień wewnętrzny jogu | 163,8 · 296,5 | ⌀ 167,5 |
| tarcza środkowa jogu | 163,8 · 296,5 | ⌀ 89,0 |
| wyświetlacz dotykowy (z ramką) | 163,0 · 81,6 | 199,5 × 108,8 |
| wyświetlacz — pole aktywne | 164,0 · 81,0 | 192,0 × 104,5 |
| listwa HOT CUE (8 padów) | 142,8 · 155,6 | 268,5 × 18,8 |
| pokrętło ROTARY SELECTOR | 290,9 · 78,6 | ⌀ ok. 40 |

**Sprawdzian zewnętrzny:** przekątna pola aktywnego wyświetlacza wychodzi
219 mm, a specyfikacja (s. 83) mówi **9 cali = 228,6 mm**. Różnica to ramka
wliczona w przekątną katalogową — proporcja się zgadza, więc pomiar nie jest
przypadkowy.

## Czego jeszcze NIE ma

* **Pozycje pozostałych ~45 kontrolek.** Automatyczne wykrywanie
  (`wykryj_kontrolki.py`, `wykryj_v2.py`) daje szkielet i duże elementy, ale
  na drobnych przyciskach produkuje setki fałszywych trafień — na rysunku
  technicznym każda przerwa między kreskami wygląda jak koło. Te pozycje
  trzeba odczytać z siatki po kolei, tak jak przy FLX4.
* **Wymiary DJM-900NXS2.** Instrukcja, którą dostałem (`manuals.plus`,
  24 strony), to skrócona wersja **bez tabeli danych technicznych** — ma za to
  rzut panelu na stronie 7, i to rzut wektorowy z tekstem, więc pozycje
  kontrolek da się z niego wyciągnąć dokładniej niż z obrazka. Brakuje samych
  wymiarów zewnętrznych do wyskalowania.
