# Rzeczy obalone — czego NIE próbować drugi raz

Spisane 2026-08-17. Towarzysz `PROJECT_LEDGER.md` i leży obok niego celowo:
ledger ma 326 KB i mówi, **co zrobiliśmy**. Ten plik mówi, **czego nie robić**,
i mieści się na kilku stronach.

**Dla kogo:** każdy, kto wchodzi do projektu. Do przeczytania w pierwszym
tygodniu, przed pierwszym pomysłem. Częściowa wersja tej listy istniała dotąd
wyłącznie wewnątrz jednego wpisu ledgera i w arkuszu na pulpicie Janka — czyli
praktycznie nie istniała.

**Jak czytać:** każda pozycja ma hipotezę, pomiar, werdykt i to, co robić
zamiast. Liczby są z pomiarów, nie z pamięci. Data przy każdej pozycji wskazuje
wpis w ledgerze, gdzie leży pełny zapis.

**Czego ta lista NIE znaczy.** Nie znaczy „to jest niemożliwe". Znaczy „to
zmierzyliśmy w tych warunkach i nie zapłaciło". Jeśli warunki się zmienią —
więcej danych, inne narzędzie, inna definicja — wracamy. Ale wracamy
**świadomie i z tym zapisem w ręku**, nie przypadkiem.

---

## A. Kierunki produktowe zamknięte

### A1. Cała aplikacja na jednej sieci neuronowej
**2026-08-09 · oznaczone CRITICAL**

Wraca regularnie, bo brzmi nowocześnie. Nie ma czym jej nakarmić: realny zbiór
uczący to **492 zlokalizowane w czasie szwy z 40 389 możliwych (1,22%)**.
Sieć od końca do końca przy takiej próbce uczy się zbioru, nie zjawiska.

**Zamiast:** cechy jawne plus wagi mierzone z korpusu. Działa i jest
sprawdzalne — patrz A6.

### A2. Grupowanie DJ-ów po gatunku albo klubie
**2026-08-09 · CRITICAL**

Gatunek jest etykietą marketingową, klub jest geografią. Ani jedno, ani drugie
nie mówi, **jak ktoś szyje**.

**Zamiast:** grupowanie po zachowaniu — podpis z tempa, skoków tempa i brzmienia,
szerokości palety, dryfu. To działa i samo oddzieliło trzymających się blisko od
skaczących (patrz B5), choć rozdzielenie jest słabe.

### A3. Ślepe wykrywanie szwów w nagraniu
**eksperyment 05 · CRITICAL**

Znajdowanie przejść bez znajomości utworów źródłowych: **F1 = 0,26** na realnym
secie. Gorzej niż zgadywanie w połowie przypadków.

**Zamiast:** dopasowanie do utworów źródłowych (kierunek M11). Jeśli wiemy, co
grało, przejście lokalizuje się o rzędy wielkości pewniej.

### A4. Rozkład szwu przez odejmowanie
**CRITICAL**

Pomysł: miks minus utwory źródłowe = to, co zrobiły ręce. Brzmi elegancko,
w praktyce zostaje szum — fazy nie da się odjąć bez idealnego wyrównania,
a idealnego wyrównania nie ma.

**Uwaga na niuans:** pomiar wnętrza szwu z 30.07 (blend 171 uderzeń, bas
wstrzymany w 86% wejść) **działa** — ale nie przez naiwne odejmowanie.

### A5. MuQ zamiast CLAP
**2026-07-22, werdykt R&D exp01 przyjęty do produkcji**

MuQ-MuLan zmierzony na bibliotece 296 utworów: remis w podobieństwie brzmienia
**11:10**, MuQ ma **hubness** (kilka utworów wychodzi na sąsiadów wszystkiego),
a licencja **CC-BY-NC** to ślepa uliczka komercyjna.

**Werdykt: CLAP zostaje.** Następca — priorytet niski.

### A6. Kopiowanie tempa z Rekordboxa zamiast liczenia
**CRITICAL**

Rekordbox jest **niezależnym sędzią** tempa i w tej roli jest bezcenny
(zgodność 94,9%, zero podwojeń przy weryfikacji z 10.08). Ale jako **źródło**
odbiera nam możliwość wykrycia własnego błędu i wiąże produkt z cudzym plikiem.

**Zamiast:** liczymy sami, Rekordbox służy do konfrontacji.

---

## B. Hipotezy modelowe, które padły przy pomiarze

### B1. Triplet jest lepszy od pary (hide-B na mapie)
**2026-08-11 · protokół zarejestrowany PRZED policzeniem wektorów**

Teza: utwór B jest mostem między A i C, więc model widzący trójkę powinien bić
model widzący parę.

Pomiar: **2 085 trójek** A→B→C z setów spiętych po linku, wektory CLAP
7 117/7 117 bez błędu.

```
los                      0,500 · top-1  7,0% · top-5 38,3%
tempo-para               0,633 · 11,7%
tempo-triplet            0,636 · 12,6%
clap-para                0,607 · 12,1%
clap-triplet             0,636 · 12,2%
```

**Δ mediany para → triplet: +0,000 w KAŻDEJ rodzinie.**

**Najważniejsza nauczka nie dotyczy tripletu.** Wczesny pomiar na **n = 21**
wyglądał obiecująco (0,67, top-5 70%) i **wyparował przy n = 2 085**. Odmowa
cytowania zapowiedzi była słuszna.

**Trzy uczciwe powody płaskiego wyniku**, żeby nie przeciągać wniosku: pula
kandydatów z tego samego setu jest niemal nasycona; wektory z próbek 30 s to
cieńszy instrument niż pełne pliki; tu CLAP to goły kosinus.

### B2. „Czegoś takiego jeszcze nie słyszałem" przewiduje błąd modelu
**2026-08-17 · progi zarejestrowane przed biegiem**

Teza: im dalej utwór od tego, co model widział w treningu, tym częściej się
pomyli — więc nowość mogłaby być mechanizmem odmowy.

Próg przed biegiem: rho ≥ +0,15 przy p < 0,05.
**Wynik: rho = +0,015, p = 0,85.** Kontrole czyste, pomiar działa, hipoteza
padła.

**Wyjaśnienie zmierzone w audycie i to jest właściwy wynik tego etapu:
przestrzeń jest GĘSTA.** Mediana odległości do najbliższego sąsiada w puli
2 855 utworów to **0,0715** kosinusa, a mediana nowości zapytań testowych
**0,078** — typowe zapytanie jest od treningu dokładnie tak daleko, jak dowolny
utwór od swojego sąsiada.

**Czytać jako „nowość nie istnieje w tej puli", NIE jako „nowość nie ma
znaczenia".**

### B3. Dołóż cechy z domeny szwu, a model ruszy
**2026-08-02**

Dołożone `entry_score` i `runway_in` (stabilny rozbieg wchodzącego, mediana
25 bitów), 100% pokrycia na 243 utworach, braki jako 0 **plus osobna kolumna
„nie wiem"** zgodnie z ADR-005.

Wynik: bramka 0,595 → **0,603**, ale top-10 spadło z 14,3% na 7,1%. **Żadna
z dwóch cech nie mieści się w pierwszej szóstce wag** — dominują `clap_cos`
(−1,263), `clap_ctx` (+1,209), `korpus` (+1,135), `bpm_diff` (+1,118).

**Werdykt: na tych dwóch cechach hipoteza się nie potwierdziła.** Model rusza
od reprezentacji brzmienia i kontekstu, nie od rzemiosła.

### B4. Model uczący się konkretnego DJ-a z korpusu
**2026-08-03**

Atrybucja z tytułów MixesDB, potwierdzona kategorią: 666 z 801 miksów ma DJ-a.
**388 unikalnych DJ-ów, z czego 299 ma JEDEN miks**, tylko 33 ma trzy lub
więcej. Największy — Adam Beyer, 21.

**Model per DJ jest niemożliwy z korpusu.** Decyzja Janka: trenujemy wyłącznie
na korpusie, a jego własne przejścia zostają jako **czujnik, nie cel** — silnik
strojony na korpusie będzie się od Janka oddalał i musi być widać, kiedy.

### B5. Szkoły sekwencjonowania jako produkt
**2026-08-03**

Grupowanie po zachowaniu **zadziałało jakościowo**: bez żadnych tagów
gatunkowych samo oddzieliło trzymających się blisko od skaczących, a Ben UFO
wylądował w grupie „skoki".

Ale liczby są słabe: k = 3 wybrane sylwetką o wartości **0,270**, czyli słabe
rozdzielenie — i trzeba to mówić.

**Werdykt: pomysł nie płaci w tej postaci.** Jako opis — tak. Jako funkcja
produktu — nie.

### B6. Odmowa („nie wiem") z sygnałów, które mamy
**2026-08-14 → 17 · cztery mechanizmy, cztery ślepe uliczki · progi przed każdym biegiem**

Warunek z 01.08: element uczący się wchodzi do silnika tylko, gdy umie
odmówić. Cztery kandydatury na mechanizm odmowy, wszystkie rozstrzygnięte:

1. **Pewność samego modelu** — pozornie działała (+0,28 pozycji), po kontroli
   wewnątrz warstw o tej samej liczbie kandydatów zostaje **+0,03**. Sygnał
   był artefaktem liczby kandydatów; rozkład jednorodny „odmawiał" mocniej
   niż model.
2. **Nowość zapytania** (odległość od treningu) — rho **+0,015**, p 0,85,
   przy progu +0,15. Wyjaśnienie: przestrzeń jest gęsta (mediana odległości
   sąsiada 0,0715 ≈ mediana nowości 0,078). Patrz B2.
3. **Nowość wskazanego kandydata** — rho +0,008 (eksploracja, poza progiem).
4. **Ubóstwo danych o zapytaniu** (strumień vs plik, na bibliotece Janka,
   za jego zgodą) — **NIEMIERZALNE**: tylko **9 z 83 sesji** miesza klasy;
   komórki krzyżowe mają 5 i 9 par, a bez warstwowania po klasie prawdy
   pomiar wpada w pułapkę „model rozpoznaje źródło" (AUC 0,889).

**Zamiast odmowy działa odpowiedź ZBIOREM:** mediana pozycji prawdy 17 z 200
na korpusie (etap 4), a produkcyjny `transition_score` na historii Janka
(932 pary, kandydaci z jego puli) — **mediana 34 z 200**. „Oto dwadzieścia,
wybierz" pokrywa ponad połowę przypadków bez żadnego mechanizmu odmowy.

**Wraca, jeśli:** pojawią się sesje mieszane (Janek gra strumienie i pliki
w jednym secie) albo pула przestanie być gęsta (obce gatunki w bibliotece).

---

## C. Kształt setu

### C1. Nasz łuk „build" jest aktywnie gorszy niż płaska linia
**2026-08-14 · to jest najbardziej niewygodny wynik w projekcie**

`arc="build"` to jedna szeroka wspinaczka (wykładnik 1,15 od percentyla 15 do
85) plus twarda reguła zakazująca schodzenia niżej.

Realne sety tego nie robią:

```
mediana rho (pozycja vs energia), 29 sesji     +0,150
  rosnących          7/29
  bez kierunku      22/29
  malejących         0/29
nagrane sety Janka   rho +0,04 (Open Deck) · +0,21 (Premier)
```

**Płaska linia opisuje set LEPIEJ niż nasz łuk: 22/29 sesji i 6/6 przypadków na
nagraniach** (mediana błędu 0,260 vs 0,319).

Do tego realne sety mają **medianę 5 spadków energii powyżej 8% na sesję**
(na nagraniach 5–6 na set) — a nasz łuk **zabrania ich w ogóle**.

**To nie jest wina miary.** Wszystkie trzy miary energii (szerokopasmowy RMS,
pasmo 40–150 Hz, pasmo powyżej 4 kHz) dają to samo, rho od −0,04 do +0,21.

**Silnik pozostaje nietknięty — decyzja należy do Janka.** Ale nikt nie powinien
budować niczego na łuku „build", nie wiedząc o tym pomiarze.

### C2. Bloki w secie — nie istnieją
**2026-08-14**

Test permutacyjny (300 przetasowań, pyta wyłącznie o kolejność):

```
sesje, energia    realna 0,163 vs przetasowana 0,186 · istotne 4/29 · mediana p 0,282
sesje, tempo      istotne 5/29 · mediana p 0,336
nagrane sety      0 przypadków na 6, trzema miarami
```

**Struktura blokowa, którą widać gołym okiem, jest artefaktem dopasowania, a nie
kolejnością.**

**Konsekwencja produktowa: brief wieloblokowy — NIE BUDOWAĆ.** Pomiar zrobiony
zanim cokolwiek powstało; pomysł przyszedł od persony weselnej, którą tego
samego dnia wyrzuciliśmy z zakresu, i groził zbudowaniem funkcji dla nikogo.

---

## D. Źródła danych, które kłamały

### D1. Tonacje z Rekordboxa nie nadają się na prawdę
**2026-08-13 · szczebel harmoniczny ZOSTAJE ZABLOKOWANY**

Biblioteka 8 250 utworów, dopasowanie po artyście ORAZ tytule dało 5 580 utworów
z tonacją, czyli 2 341 szwów (11,1%) z tonacją po obu stronach.

**Ale tam, gdzie tonację mają oba źródła, zgadzają się w 36,6% przypadków —
nawet gdy TEMPO potwierdza, że to ta sama wersja nagrania.** Przy parach
odrzuconych przez tempo: 31,7%, czyli praktycznie tyle samo — **więc to nie
wina parowania utworów**.

Struktura: gdy mapa mówi dur, Rekordbox mówi moll w 26,4% przypadków. Cała
biblioteka RB to **87,7% moll** wobec 67,6% w mapie — rozkład niewiarygodny dla
jakiejkolwiek biblioteki.

**Trzy hipotezy sprawdzone i odrzucone:** różnica zapisu (nie — oba używają
Camelota); normalizacja myląca remiks z oryginałem (nie — 33,6% vs 35,8%);
zły odczyt pola (nie — `Key.ScaleName` trzyma Camelot wprost).

### D2. NTS — API ignorowało zapytanie
**2026-08-14 · pomyłka, która zawyżała bazę o 71%**

Endpoint `nts.live/api/v2/search/episodes` **ignoruje parametr `q`**: dla „Ben
Klock", dla „Paramida" i dla bzdury „zzzzqqq" zwraca identyczne `count=87318`
i te same najnowsze odcinki. 1 237 zapytań o artystów zwróciło **te same
4 odcinki**.

**Stąd zasada, która od tej pory obowiązuje przy KAŻDYM nowym źródle:
pierwszym testem jest zapytanie, które NIE POWINNO nic zwrócić.** Jeśli coś
wraca — źródło kłamie. Zastosowane od pierwszej minuty przy następnym
zaciągnięciu („Xqzvw Blorptak" nie przechodzi zapory).

### D3. Historia Rekordboxa to załadowanie na deck, nie granie
**2026-08-02**

`DjmdSongHistory.created_at` daje czas załadowania wiersza. Odstęp mówi, czy
poprzedni utwór w ogóle grał:

```
mediana odstępu        161,7 s
poniżej 30 s           19,7%   ← na pewno nie zagrany
90–600 s               65,0%
powyżej 600 s           8,5%
sesje: 70 z 91 wygląda na sety, 21 na przeglądanie biblioteki
```

**Około jednej trzeciej par to nie przejścia.** Filtr 90–600 s zostawia 1 464
z 2 317 (63,2%) i włączony jest na stałe — uzasadniony fizycznie, nie dobrany
pod wynik.

**Ale rozbieżność nie znika po filtrze** — to także różnica zadań, nie tylko
zanieczyszczenie.

### D4. Mediana różnic przy siatce bitów
**Klasyka, wraca przy każdym dotknięciu siatki**

Okres bitu liczony **medianą różnic między uderzeniami** daje **48 ms rozjazdu
na 32 bitach**. Wygląda wiarygodnie, dopóki nie sprawdzi się o twardą liczbę.

**Zamiast: najmniejsze kwadraty. Nigdy mediana różnic.**

### D5. Korpus gubi szwy
**Skaziło raz wagi**

Dopasowanie utworów do miksu **odcina strefę nakładania** — czyli dokładnie to,
co chcemy mierzyć. Z 23 tysięcy nominalnych przejść zostaje **49 realnie
użytecznych szwów**.

**Liczba do zapamiętania przy każdym zdaniu zaczynającym się od „mamy 23
tysiące…".**

### D6. „Wagi zmierzone z korpusu biją ręczne" — pomiar był zepsuty
**Obalone 2026-08-28. Wniosek żył od 2026-08 i wszedł do ledgera oraz do pamięci.**

`scripts/priors_validation.py` liczył składnik harmoniczny jako
`0.4 * harmonic_compatibility(...)`, a ta funkcja zwraca **obiekt**
`HarmonicResult`, nie liczbę. Mnożenie rzucało `TypeError` prosto w
`except Exception: pass` kilka linii niżej, więc **harmonia nigdy nie weszła do
żadnego wyniku „wag ręcznych"** podanego przez ten skrypt.

Porównanie „24,3% zmierzone przeciw 20,7% ręczne" nie porównywało więc wag.
Porównywało **model z harmonią przeciw modelowi bez harmonii**.

Po naprawie: ręczne **25,2%**, zmierzone 24,3%, percentyl 0,423 wobec 0,427,
**p = 0,668**. Kierunek się odwrócił, ale różnica jest nieistotna w obie strony.

**Uczciwy stan: na tych danych nie da się rozróżnić wag ręcznych od
zmierzonych.** Nie „ręczne wygrywają" — to byłby ten sam błąd w drugą stronę.

**Zamiast:** przy każdym porównaniu modeli sprawdzić najpierw ablacją, że każdy
składnik w ogóle wpływa na wynik. Wariant „bez X" dający wynik identyczny co do
trzeciego miejsca po przecinku to nie odkrycie, że X nie działa — to prawie
zawsze martwy kod.

### D7. „Harmonia nie odróżnia wyboru DJ-a" — nie replikuje się
**Obalone 2026-08-28, dzień po postawieniu.**

Na 2304 szwach z mapy DJ-ów lift harmoniczny miał przedział ufności zawierający
1,0, a 59,7% przejść było harmonicznie „risky". Wyglądało to na mocne
ustalenie i zapisałem je jako hipotezę do zmiany wag silnika.

Na niezależnym zbiorze (1604 obserwacje z kandydatami, których DJ nie wybrał)
**usunięcie harmonii istotnie pogarsza przewidywanie** — top1 spada z 25,2% na
20,7%, p = 0,0093.

Najprawdopodobniejsza przyczyna rozbieżności: baseline w tamtym pomiarze
losował pary **z tego samego setu**, a DJ-e grają w wąskim zakresie tonacji, więc
losowa para z ich setu jest harmonicznie podobna do prawdziwego przejścia.
Test nie miał czego odróżniać.

**Zamiast:** przy pytaniu „czy składnik niesie informację" używać zbioru z
**odrzuconymi kandydatami**, nie baseline'u losowanego z tej samej puli.

---

## E. Wzorce błędu, które wracają

To nie są zdarzenia, tylko klasy pomyłek. Każda wystąpiła więcej niż raz.

**Mała próbka wygląda obiecująco i wyparowuje.** n = 21 dało 0,67 i top-5 70%;
n = 2 085 dało zero różnicy. **Nie cytować zapowiedzi przed pełnym biegiem.**

**Dane dobrane pod aparaturę, nie pod produkt.** Wystąpiło **trzy razy**
(np. CLAP ograniczony do 2 881 utworów uniwersum bramki zamiast pełnego
korpusu). Objaw: zbiór zawężony tak, żeby narzędzie zadziałało.

**Ogłoszenie czegoś, co już było zrobione.** Sprostowanie z 11.08: most do
filara był wdrożony od 09.08, a mimo to dwa razy tego samego dnia ogłoszono go
jako nowość. **Przed ogłoszeniem — sprawdzić git.**

**Struktura widoczna gołym okiem jako artefakt dopasowania.** Bloki w secie
(C2) i łuk „build" (C1) to ten sam błąd: model z wolnymi parametrami dopasuje
się do czegokolwiek. **Porównywać wyłącznie modele bez swobodnych parametrów,
albo robić test permutacyjny.**

---

## Jak dopisywać do tej listy

Pozycja wchodzi tu wtedy, gdy **hipoteza została zmierzona i nie zapłaciła** —
nie wtedy, gdy ktoś uznał ją za nietrafioną.

Wzór: hipoteza · próg ustalony PRZED pomiarem · wynik z liczbami · werdykt ·
co robić zamiast · data wpisu w ledgerze.

Próg przed pomiarem jest częścią obowiązkową. Bez niego wynik da się
opowiedzieć w obie strony i pozycja nic nie waży.
