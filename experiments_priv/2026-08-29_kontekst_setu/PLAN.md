# Kontekst setu — plan i progi (zarejestrowane 2026-08-29 PRZED pomiarem)

## Skąd to się bierze

Ślepy odsłuch: druga najczęstsza kategoria zgrzytu to **kontekst setu (27 na
158 przejść)**, a przy niej Janek pisał „świat A → B", „inne światy",
„przeszliśmy z pogodnego na mroczny i z powrotem", „wybija narzucony klimat".
To nie jest własność pary utworów — para nie wie, co grało trzy utwory temu.

Poprzedni pomiar (`2026-08-29_rozdzielczosc_punktacji`) pokazał, że wewnątrz
133 przejść z maksymalną punktacją **żadna dzisiejsza składowa nie ma związku
z uchem** (od −0,036 do +0,019). Szukamy więc informacji NOWEJ, nie przewagi.

## Czym dysponujemy (sprawdzone, nie założone)

* **rms (głośność) — 155/155 utworów.**
* Bogatsze deskryptory (bas, gęstość uderzeń, wokal, napięcie) — **tylko 48/155**.
* Wektory brzmienia CLAP — **0/155**.
* `style_label` — 110/155 („Electronic", „House", „Dance", „Techno"…).
* tempo i tonacja (camelot) — komplet.

Kontekst budujemy więc z energii, tempa, tonacji i etykiety stylu. Jeśli te
cechy nie wystarczą, następnym krokiem jest **dopolicowanie deskryptorów dla
tych 155 utworów**, a nie wymyślanie kolejnych wzorów na tych samych danych.

## Pięć cech kontekstu — okno trzech poprzednich utworów

Liczone dla przejścia do utworu B, patrząc na trzy utwory przed nim:

1. `skok_energii` — o ile głośność B odstaje od średniej okna, w jednostkach
   rozrzutu tego okna.
2. `dryf_tempa` — odległość tempa B od średniej tempa okna, względnie.
3. `zygzak_energii` — ile razy energia zmieniła kierunek w oknie („poszliśmy
   w mrok i z powrotem").
4. `obcosc_stylu` — czy etykieta stylu B różni się od dominującej w oknie
   (nieznana etykieta = neutralnie 0,5, nigdy zgadywana).
5. `niezgodnosc_tonacji_w_oknie` — ile kroków w oknie było harmonicznie
   niezgodnych.

## Jak mierzymy — i dlaczego właśnie tak

Zgodność liczona **wewnątrz playlisty** (średnia po dziesięciu), nie na
wspólnej kupie. Powód jest twardy: playlisty kontrolne są potasowane i mają
zarazem gorszy kontekst i gorsze oceny, więc na wspólnej kupie każda cecha
kontekstu dostałaby korelację za samo rozpoznanie „to jest tasowanie".
Wewnątrz playlisty ten efekt znika.

Dzisiejsza punktacja ma średnie rho wewnątrz playlist **+0,426**.

## Progi — ZAPISANE PRZED POMIAREM

1. **Cecha sama w sobie:** |średnie rho wewnątrz playlist| ≥ **0,20**,
   istotność z permutacji wewnątrz playlist **p < 0,01** (Bonferroni dla
   pięciu cech: 0,05 / 5).
2. **Tam, gdzie dziś jest ślepota:** wewnątrz 133 przejść z maksymalną
   punktacją |rho| ≥ **0,15** (dziś: od −0,036 do +0,019).
3. **Połączenie:** punktacja z dołożoną cechą musi mieć średnie rho wewnątrz
   playlist ≥ **0,50** (dziś 0,426), żeby ogłosić poprawę; wynik poniżej
   0,426 = pogorszenie i koniec.

**Wynik przeciwny progom → `OBALONE.md`, silnik bez zmian.** Zakaz strojenia
wag pod te 158 ocen; testujemy dokładnie pięć cech wymienionych wyżej i żadnej
dorzuconej po zobaczeniu wyników — a jeśli jakąś dorzucę, będzie oznaczona
jako post-hoc i traktowana jako hipoteza do sprawdzenia na nowych danych.

## Czego to nie rozstrzygnie

Okno wstecz to nie jest „kontekst setu" w pełnym sensie — nie wie o łuku
całości ani o tym, co Janek zagrał na poprzedniej imprezie. Sprawdzamy
najtańszą wersję tezy: czy trzy poprzednie utwory niosą informację, której
para nie ma.

---

## WYNIK (2026-08-29, po pomiarze)

Żadna z pięciu cech nie spełniła progu podstawowego.

```
cecha                     rho w playlistach       p     rho tam, gdzie silnik ślepy
dzisiejsza punktacja                 +0,426       —     brak zmienności (stała 1,0)
skok_energii                         −0,132  0,1725                         −0,167
dryf_tempa                           +0,122  0,2106                         +0,183
zygzak_energii                       +0,017  0,8579                         +0,153
obcosc_stylu                         +0,059  0,5532                         +0,101
niezgodnosc_tonacji                  −0,088  0,3693                         −0,015
```

Próg brzmiał: |rho| ≥ 0,20 przy p < 0,01. Najlepsza cecha ma 0,132 przy
p = 0,17 — czyli w granicach szumu. Progu drugiego (0,15 w grupie nasyconej)
dotykają trzy cechy, ale przy pięciu testowanych i nieistotnym progu pierwszym
to nie jest wynik, tylko rozrzut.

**Czego to NIE obala:** tezy, że kontekst setu ma znaczenie. Obala konkretną
próbę zmierzenia go **z tych deskryptorów, które mamy**. A mamy mało:
107 ze 155 utworów ma w analizach wyłącznie głośność, wektorów brzmienia jest
**47 ze 155**. „Świat”, o którym Janek pisze w notatkach, jest cechą barwy
i klimatu — a barwy w tych danych praktycznie nie ma.

**Następny krok jest więc o dane, nie o wzory:** dopolicować wektory brzmienia
(albo pełne deskryptory) dla brakujących ~108 utworów i powtórzyć dokładnie
ten sam pomiar, z tymi samymi progami.
