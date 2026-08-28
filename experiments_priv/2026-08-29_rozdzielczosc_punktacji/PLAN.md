# Rozdzielczość punktacji przejść — plan i progi (zarejestrowane 2026-08-29 PRZED pomiarem)

## Skąd to się wzięło

Ślepy odsłuch A–J (29.08) pokazał, że wynik silnika prawie nie różnicuje:
**133 przejścia ze 158 mają dokładnie 1,0**. Zgodność z uchem jest (rho 0,315,
p 0,0043), ale bierze się wyłącznie z 25 przejść, które silnik oflagował —
tam średnia ucha 2,84, przy maksimum 4,01. Silnik umie powiedzieć „tu będzie
źle”, a nie umie powiedzieć, jak bardzo będzie dobrze.

## Co pokazała diagnoza (`diagnoza.py`, bez zmieniania silnika)

| składowa | odchylenie | unikalnych ze 158 | rho z uchem |
|---|---|---|---|
| harmonia | 0,200 | 64 | +0,111 |
| tempo | 0,160 | 105 | +0,093 |
| **energia** | **0,000** | **1** | — |
| mixability | 0,052 | 153 | +0,167 |
| **rdzeń (suma ważona)** | 0,084 | **153** | +0,154 |
| po brzmieniu | 0,084 | 153 | +0,154 |
| **po priorze korpusowym** | 0,129 | **26** | **+0,315** |

Trzy fakty, nie domysły:

1. **Rdzeń MA rozdzielczość** (153 różne wartości), traci ją dopiero prior
   korpusowy: mnoży przez `lift` (clamp 0,4–2,0) z wagą 1,0 i **przycina do
   1,0**. Wszystko, co miało rdzeń ≥ 0,731 i dodatni lift, ląduje na 1,0.
2. **Prior niesie prawdziwy sygnał**: to on podnosi zgodność z uchem z 0,154
   do 0,315. Nie wolno go wyrzucić — trzeba przestać go przycinać.
3. **Energia jest stała** (1,0 dla wszystkich 158), bo `arc="off"` to domyślny
   tryb od 11.08. Jej waga 0,20 nie różnicuje niczego, tylko dolewa stałą
   i ściska rozstęp pozostałych składowych. Osobno: brzmienie ma wagę 0,60,
   ale na tych utworach nie ma wektorów, więc `blend` oddaje rdzeń bez zmian.

## Co robimy

Dwie zmiany, każda mierzona osobno i razem:

* **A — renormalizacja wag**, gdy składowa jest stała lub niedostępna
  (energia przy `arc="off"`). Wagi pozostałych składowych skalowane do sumy 1.
* **B — prior bez przycinania**: zamiast `min(1, core · lift^w)` mieszanie
  w logitach: `sigmoid(logit(core) + w·ln(lift))`. Monotoniczne, ograniczone
  do (0,1), zachowuje kolejność i nie ma sufitu.

## Progi — ZAPISANE PRZED POMIAREM

Poprawka wchodzi do silnika **tylko** jeśli spełni wszystkie trzy:

1. **Rozdzielczość:** ≥ 120 unikalnych wartości na 158 przejściach
   (dziś: 26).
2. **Zgodność z uchem nie spada:** Spearman rho ≥ 0,315 na komplecie
   (dziś: 0,315). Ogłaszam poprawę dopiero przy **rho ≥ 0,40**.
3. **Uczciwość poza próbką:** walidacja „bez jednej playlisty” — model
   liczony bez playlisty X, rho mierzone NA X, uśrednione po dziesięciu.
   Nowy wynik musi mieć średnie rho z-poza-próbki **nie gorsze** niż stary.
   *(Punkty A i B nie mają parametrów dopasowywanych do ocen, więc ryzyko
   przeuczenia jest małe — ale walidacja i tak biegnie, żeby to pokazać,
   a nie zadeklarować.)*

**Wynik przeciwny progom idzie do `OBALONE.md`, a silnik zostaje jak jest.**
Zakaz: nie wolno po pomiarze podkręcać progów ani dobierać wag pod te 158 ocen
— to jedyne oceny ucha, jakie mamy, i spalenie ich na strojenie zostawia nas
bez miary.

## Czego ten eksperyment NIE rozstrzyga

Oceny pochodzą od jednego DJ-a i z playlist, w których kontrolą było
tasowanie. Lepsza rozdzielczość punktacji to warunek konieczny, żeby silnik
umiał wybierać między dobrymi przejściami — ale nie dowód, że wybiera dobrze.

---

## WYNIK (2026-08-29, po pomiarze)

Żaden wariant nie spełnił progów. **Silnik zostaje bez zmian**, wpis trafił do
`OBALONE.md`.

```
wariant                          unikalnych    rho   rho bez jednej playlisty  złych w top 50%
dziś (mnożenie + przycięcie)         26/158  +0,315                   +0,426                8
A — renormalizacja wag               71/158  +0,192                   +0,221               10
B — prior w logitach                153/158  +0,171                   +0,159                9
A+B                                 152/158  +0,170                   +0,158                9
sam lift (goła flaga)                17/158  +0,208                   +0,178                9
sam rdzeń (bez prioru)              153/158  +0,154                   +0,078                8
```

Dwa warianty **post-hoc** (C i D — rozstrzyganie remisów rdzeniem albo
mixability), zaproponowane dopiero po porażce A i B, też przegrały:
rho +0,181 i +0,219. Oznaczam je jawnie jako post-hoc, bo dokładanie kandydatów
po zobaczeniu wyniku zwiększa szansę, że któryś przejdzie przypadkiem.

**Przyczyna:** wewnątrz grupy 133 przejść z maksymalną punktacją żadna składowa
nie koreluje z uchem (od −0,036 do +0,019). Rozdzielczość dołożona do składowych
bez sygnału to dosypanie szumu. **15 z 27 przejść ocenionych 1–2 leży w tej
grupie** — są dla punktacji niewidzialne, a nie źle uszeregowane.
