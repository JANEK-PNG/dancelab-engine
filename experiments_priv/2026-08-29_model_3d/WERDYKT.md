# Model 3D CDJ-3000 — co z niego wyszło, a co nie (29.08.2026)

## Kryterium 1 (zapisane przed otwarciem pliku): NIESPEŁNIONE

Model to **cztery zlepione bryły** — kable, DJM-A9 i dwa CDJ — a nie osobne
obiekty per kontrolka. Próg brzmiał: co najmniej 30 obiektów siatkowych.
Geometrii z obwiedni obiektów nie ma i nie będzie.

## Model jest jednak wierny w proporcjach

Po jednym wspólnym współczynniku wziętym z szerokości (329 mm):

```
szerokość  329,0 mm  (wzorzec)
głębokość  454,1 mm  wobec 453,0 z instrukcji   → +0,25%
wysokość   137,6 mm  wobec 118,0 z instrukcji   → +16,6% (obwiednia liczy gałki,
                                                  talerz i suwak — nie samą obudowę)
```

Renderowany rzut ortograficzny z góry potwierdza to niezależnie: panel wychodzi
na obrazie **454,0 mm głębokości wobec 453,0** ze specyfikacji. Skala renderu
jest w porządku.

## Kryterium 2 (zapisane przed renderem): NIESPEŁNIONE

Żeby czytać z renderu pozycje kontrolek, trzy wielkości musiały się zgodzić
z instrukcją w ±2 mm. Nie zgodziły się:

```
wielkość                      z renderu   z instrukcji   różnica
talerz (średnica)                 162,6         202,2      −39,6
ekran (szerokość)                 335,5         199,5     +136,0
ekran (wysokość)                  231,5         108,8     +122,7
listwa hot cue (szerokość)        251,8         268,5      −16,7
listwa hot cue (wysokość)          21,2          18,8       +2,4
```

**Ale to nie jest werdykt o renderze — to werdykt o moim mierniku.** Ekran
„szerszy niż cały panel" jest fizycznie niemożliwy; detektor łapał połysk na
całej górnej płycie zamiast samego wyświetlacza. Po poprawce (największa spójna
bryła zamiast sumy plamek) ekran nadal wychodził tak samo, listwa hot cue dała
46 „padów" zamiast ośmiu, a profil krawędzi talerza pokazał sześć
współśrodkowych pierścieni — ⌀162,6 · ⌀207,7 · ⌀219,1 · ⌀221,4 · ⌀166,5 · ⌀67,0
— i sam z siebie nie wie, który z nich jest talerzem.

Jeden z nich, **⌀207,7 mm**, leży 2,7% od zmierzonych z instrukcji 202,2 mm.
To wskazuje, że render jest wymiarowo rozsądny, ale **nie mieści się w ±2 mm**,
które sam sobie zapisałem.

## Werdykt wg zapisanych kryteriów

**Geometria zostaje na rastrze z instrukcji (±1 mm), render zostaje źródłem
materiału i detalu.** Progu nie ruszam, bo próg był zapisany przed pomiarem.

## Co z tego jest cenne mimo dwóch niespełnionych kryteriów

1. **Dziesięć renderów referencyjnych** (rzut z góry 3948 × 5449 px, perspektywa,
   przód, bok, talerz, ekran, cały zestaw, mikser) — to jest etap 4 metody
   („materiał ze zdjęć, nie z wyobraźni"), którego panel klubowy nigdy nie miał.
   Zastępują polowanie na zdjęcia sklepowe: dają dowolne ujęcie, w dowolnej
   rozdzielczości, bez cudzych praw do fotografii.
2. **Paleta i faktura z tekstur modelu** — czarne ciało, srebrne gałki, barwne
   pady hot cue, zielony PLAY, bursztynowy CUE, mierniki poziomu.
3. **Potwierdzenie skali** niezależne od instrukcji.

## Droga do geometrii, która zostaje

Nie automat, tylko **kalka**: render w znanej skali jako podkład pod SVG,
pozycje odczytywane okiem i sprawdzane audytorem — dokładnie tak, jak powstał
FLX4. Dokładność rzędu ±1–2 mm, źródło jawnie oznaczone jako „obrys z renderu",
nie „zmierzone z rysunku technicznego".
