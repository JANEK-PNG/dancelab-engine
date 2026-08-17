# ŁUK NAUKI

# ŁUK NAUKI DANCELAB
## Od katalogu do pomiaru — czerwiec–sierpień 2026

Ten dokument nie jest kroniką. Jest ciągiem: **co założono → co zmierzono → co się okazało → co z tego wynikło**. Każdy akt kończy się w innym miejscu, niż się zaczął, i prawie zawsze dlatego, że liczba obaliła przekonanie.

Jedna obserwacja przekrojowa, którą warto postawić na początku, bo organizuje całą resztę: **intuicja Janka o MUZYCE wygrywała z założeniami modelu za każdym razem, gdy doszło do pomiaru. Jego intuicja o APARATURZE pomiarowej — przegrywała.** To rozróżnienie jest zmierzone, nie deklarowane, i wraca w każdym akcie.

---

## AKT 0 · KATALOG (18–20.06.2026)
**Założenie: wiedzę o muzyce da się spisać ręcznie.**

Vault „DJ ID" powstał w trzy dni: 68 artystów, 118 utworów, 38 labeli, jedno narzędzie (Kreator Playlist), które budowało set z grafu znajomości artystów wzdłuż krzywej energii `[1,2,3,4,5,4,3,2]`.

**Pomiar (wykonany dopiero teraz, 14.08.2026):**
- Notatki utworów powstały **19.06 o 14:27**, czyli **56 sekund** po wgraniu eksportu Rekordboxa. Dla 104 ze 118 utworów tempo i tonacja zgadzają się z Rekordboksem co do jednostki.
- Ale **7 utworów**, których w eksporcie nie było, dostało tę samą wypełniaczową parę: `bpm: 79, key: 10A`. To **6% bazy zmyślone bez żadnego znacznika** — wizualnie nieodróżnialne od 104 prawdziwych.
- **1369 z 1629** pozycji biblioteki (84%) to strumienie Apple Music bez pliku. Jakakolwiek analiza dźwięku mogła dotknąć najwyżej 16% biblioteki.
- Kreator NIGDY nie wyprodukował ani jednego setu — w folderze Sets nie ma pliku o typie `set`.
- Rozpoznanie twierdziło, że winna była rzadkość grafu. **To nieprawda:** przy głębokości 2 Kreator sięgał 74 ze 118 utworów (63%). Prawdziwa przyczyna: graf był **zadeklarowany przez model językowy, nie zmierzony**.

**Wynikło:** vault umarł 20.06 o 12:38 i nigdy nie został tknięty. Ostatnie dwa wygenerowane sety brały utwory już nie z vaulta, tylko wprost z Rekordboxa — baza wiedzy i narzędzie decyzyjne się rozjechały, a wtedy baza przestała mieć funkcję.

**Reguła, która się tu urodziła (choć nazwana rok później):** liczba bez proweniencji jest nieodróżnialna od zmyślonej. To jest korzeń ADR-005.

---

## AKT I · LITERATURA (06–14.07.2026)
**Założenie: odpowiedź jest w papierach i w cudzym korpusie.**

06.07 o 23:02 powstaje repozytorium silnika. W dwa dni powstaje 597 notatek badawczych, a przed nimi — i to jest nietypowa kolejność — **standardy, które nimi rządzą**: skala dowodowa E0–E6, polityka cytowania, twarda reguła „język inwestorski nie może przekroczyć poziomu dowodu".

13.07: pakiet 13 papierów, 232 strony, ~145 911 słów. W środku EUREKA: praca mierząca **1 557 realnych miksów, 13 728 utworów, 20 765 przejść**.

**Pomiar 1 (13.07, 23:12):** audyt publicznego repozytorium `mir-aidj/djmix-analysis`, przypięty do commita `a2ae903`.
**OBALONE:** repo NIE zawiera korpusu. Jedyna zacommitowana tabela ma **32 wiersze — 31 utworów z JEDNEGO miksu**, rozmiar repo ~1,5 MB. Nadzieja na 20 765 gotowych przejść treningowych umiera tej nocy.

**Pomiar 2 (14.07, 02:45, nocny audyt własnej pracy sprzed kilkunastu godzin):**
**OBALONE:** własna lista wzorów M1–M12 była brana za spis kompletny. Powstaje spis strona po stronie — **232 wiersze, po jednym na każdą stronę PDF, także dla stron, na których nic nie znaleziono**. Rozkład: 26 stron z jawnym równaniem, 68 wtórnych, **108 bez żadnej reguły**.

**Wynikło:** do pliku startowego dopisano regułę nr 11: *„A formula shortlist is never evidence of source completeness."* I decyzję końcową całego pakietu, przeciwną do oczekiwanej: **„to uzasadnia ograniczony upgrade walidacji, a nie nieograniczoną przebudowę silnika"**. Po przeczytaniu 232 stron literatury wniosek brzmiał: napraw dane, nie buduj nowego modelu.

**Pomiar 3 (14.07, 04:19):** priory długości szwu z archiwum Raveform, 24 558 nakładek. Mediana 66 uderzeń, 48,6% mieści się w 64. Osobno sprawdzono hipotezę „długie intro ⇒ dłuższy szew" na 1 181 przejściach.
**OBALONE mimo istotności:** rho = 0,1008 przy **p = 0,000525**. Wynik istotny statystycznie, odrzucony jako podstawa reguły. Rzadki przypadek: ktoś ma w ręku wynik istotny i sam sobie go zabiera.

---

## AKT II · KORPUS (15–22.07.2026)
**Założenie: cudze sety powiedzą nam, jak grać.**

15.07 — cztery przewidywania zarejestrowane **PRZED** pomiarem, z regułą „żadnego »wiedziałem«".

**Werdykty (16–17.07):**

| | Przewidywanie | Autor | Wynik |
|---|---|---|---|
| P1 | przejścia przez oktawę < 2% | Janek (domena) | **potwierdzone: 0,9%** |
| P2 | jungle nie zapada się do half-time | Janek (domena) | **potwierdzone** |
| P3 | D&B ma najkrótsze przejścia | inżynier | **OBALONE:** house 110 < bass 132 < techno 163 < trance 174 uderzeń |
| P5 | po naprawie oktawy rho skoczy 0,30 → 0,65 | Janek (aparatura) | **OBALONE:** rho **spadło do 0,272** |

To jest moment, w którym rozróżnienie z wstępu zostaje zmierzone. **Domenowe przeczucia Janka: 2/2. Przewidywanie o zachowaniu aparatury: 0/1. Przewidywanie modelu: 0/1.**

**Konsekwencja P5 jest ostrzejsza niż sam wynik:** skoro naprawa siatki nie podniosła korelacji, to znaczy, że **35 ślepych ocen Janka częściowo oceniało zepsuty odtwarzacz, a nie muzykę**. 21.07 zostają wycofane z pętli strojenia.

**Pomiar (21.07): czy zmierzone wagi biją ręczne?**
Tak — top-1 **24,3% (zmierzone) > 20,7% (ręczne)** na realnych wyborach DJ-ów. Ale drugie ustalenie jest ważniejsze: **wagi ręczne ledwo odstawały od losowania.** Percentylowo różnica ma p = 0,12, więc raportowana jako „prowadzą, dowodu brak".

**Pomiar (22.07): CLAP jako waga w ocenie par.**
DJ-e faktycznie wolą podobnie brzmiące utwory — lift **1,52×** przy kosinusie ≥0,90.
**OBALONE zastosowanie:** dodanie tego liftu do oceny par **obniżyło top-1 z 24,3% na 20,1%**. Diagnoza: kandydaci pochodzą ze skrzynki, którą DJ już wykurował pod brzmienie, więc sygnał jest prawie stały wewnątrz zbioru wyboru. To jest **exposure bias** — realny sygnał populacyjny, który POGARSZA ranking. Jedyny materiał w projekcie o kształcie publikowalnym.

**Pomiar (22.07): prior energii.** Lifty 0,94–1,04, czyli szum. Reguła „płasko ⇒ nie dodajemy" ogłoszona przed pomiarem i **dotrzymana**.

**Pomiar (22.07): eksport.** Wyeksportowano 26 poprawnych hot cue w `rekordbox.xml`. Janek nie zobaczył **ani jednego** — Rekordbox nie nadpisuje utworów już będących w kolekcji, a główny przypadek użycia to zawsze jego własna biblioteka.
**Wynikło:** zmiana definicji „gotowe". *„Jeśli eksport wymaga instrukcji — eksport jest niedokończony."* 24.07 udowodniony zapis wprost do `master.db`, end-to-end.

---

## AKT III · UCZCIWOŚĆ I UCHO (24–31.07.2026)
**Założenie: silnik jest zdrowy, brakuje mu tylko interfejsu.**

24.07 Janek każe wyciąć **8 117 linii** interfejsu Qt. Pełny zestaw testów po raz pierwszy dobiega do końca: 506 zielonych w 11,6 s.

**Pomiar (25.07): siedem napraw uczciwości.** Wzorzec był jeden: brakujące dane dostawały „rozsądną" wartość domyślną, która potem **PODNOSIŁA pewność**. Silnik był tym pewniejszy, im mniej wiedział.

**Pomiar (25.07): graf importów, 146 plików.**
**OBALONE „jeden organizm":** badania to **44% kodu**, a wpływają na produkt przez **JEDEN plik JSON**. Moduł kontekstu występu istniał i nigdy nie był karmiony. Podgląd renderował audio bez żadnej komendy. Werdykt: *„sprawny układ krwionośny i mózg, zmysły odłączone od skóry"*.

**Pomiar (27.07): red-team własnego wyniku sprzed czterech dni.**
**WERDYKT WYCOFANY.** Detektor zwracał 5 wykryć na 1 prawdziwe przejście, a chwalony „błąd 1,46 s" liczono jako `min()` **przy znajomości odpowiedzi**. Próg percentylowy zawsze zwraca 10% klatek. Macierz podobieństwa na 60 minutach wymagałaby 192 GB przy maszynie 24 GB.

**Pomiar (27.07): ślepe wykrywanie szwów na realnym secie (52,2 min, 18 przejść).**
**OBALONE:** trafność 25,0%, pokrycie 27,8%, **F1 = 0,263** — 5 z 18 złapanych przy 15 fałszywych alarmach. Kontrola negatywna niezdana o włos (0,21 wykrycia/min przy bramce 0,20). Przy okazji umarło założenie „stała siatka taktów jest ważna przez cały set": realne tempo lokalne waha się 89–141 BPM, a globalne dopasowanie odpłynęło o **28 taktów**.

**Pomiar (27.07): ile szwów naprawdę daje korpus.**
**OBALONE „~6500":** 23 644 przejść → 16 675 po deduplikacji → **162 prawdziwe nałożenia** → 128 z audio → **49 z wiarygodnym zaczepieniem**. Dopasowanie DTW odcina strefę nakładania, czyli **korpus systematycznie gubi dokładnie to, co jest produktem**.

**Pomiar (28.07): mediana długości przejścia 94 uderzeń — wpięta rano, WYCOFANA tego samego dnia.**
Audyt pola źródłowego na 11 405 przejściach: **14,3% wartości UJEMNYCH** (do −14 526), 28,7% dłuższych niż 4 minuty (do 15 771), tylko **42,4% fizycznie możliwych**. Pole mierzyło odstęp między dopasowanymi regionami, nie długość blendu.
**Wynikło:** w jej miejsce weszła jawna reguła rzemieślnicza, oznaczana w każdym wyjściu jako *„craft rule, not a measurement"*.

**ZWROT (30.07).** Janek: *„jak mam wiedzieć, że rozumiesz przejścia, jeśli sam nie zrobisz przejść"*. Powstaje Automix grający cały set. Werdykt: „jest bardzo ładnie". Droga tam prowadzi przez ~12 usterek, z których **KAŻDĄ wskazało jego ucho, zanim znalazł ją pomiar** (m.in. „podbijasz ISO zamiast otworzyć przysłonę" — soft-clip podbijał ciche fragmenty o 3,1 dB, głośne o 0,5).

Skoro korpus gubi szew — zmierzmy własne. Pytanie Janka: *co zostanie, jak od miksu odjąć utwory źródłowe?*
**Wynik:** profil szycia — nakładanie mediana **75,3 s (~171 uderzeń)**, bas wchodzącego wstrzymany w 18 z 21 przejść. Reguła wejścia: **„perkusja w górę, bas w dół" w 71% jego wejść wobec 18% losowych momentów utworu.**

Dwa sprostowania w tym samym pakiecie:
- **OBALONA hipoteza komplementarności szwu:** prawdziwe pary +0,125, pary **PRZETASOWANE +0,173**. Wartość prawdziwa leży wewnątrz rozrzutu przypadkowego.
- **„Bas wycięty ręką w 86%" → 62%**, gdy strażnik odróżnił bas USUNIĘTY od utworu, który nigdy nie miał basu w intrze.
- **WYCOFANE porównanie „Janek szyje 2,1× dłużej niż typowy DJ"** — bo korpusowe 77 uderzeń to luka w dopasowaniu DTW, a u Janka mierzono całe słyszalne nakładanie. Dwie różne rzeczy.

**Pomiar (31.07): sztywna siatka bitów.** Błąd średni **1,7 milibitu wobec 8,0**, sprawdzone na 183 utworach przeciwko Rekordboksowi. Ale pierwsza wersja poprawki naprawiła trzy utwory i **po cichu zepsuła czwarty** — złapane tylko dlatego, że porównano stare siatki z nowymi.

---

## AKT IV · POKORA (01–03.08.2026)
**Założenie: silnik zna Janka.**

**01.08 — NAJWAŻNIEJSZY POMIAR CAŁEGO PROJEKTU.** Test na **28 realnych przejściach** z jego nagranych setów.

**OBALONE, całkowicie:**
- **top-5 = 0%**
- średni percentyl **0,597** (0,5 = ślepy traf)

Diagnoza jednym zdaniem: *„w score NIE MA niczego, co zmierzyliśmy o Janku"*. Silnik trafia w gust na poziomie biblioteki (percentyl 0,289) i jest ślepy na realnych przejściach. Wszystko, co o nim zmierzono — reguła wejścia, brzmienie CLAP, ciągłość grupy — leżało **OBOK** silnika, nie w nim.

Tego samego dnia Krok 0 obala jeszcze dwa własne założenia:
- **81,4% historii Janka (695 z 853 utworów) to strumienie Apple Music bez pliku.** Par z pełnymi cechami jest **451, nie 2345**.
- **Cały silnik nie bije sortowania po samej różnicy tempa: 0,597 vs 0,606.**

A potem trzecie, najbardziej niewygodne: **sama bramka jest za słaba, żeby cokolwiek potwierdzić.** 95% przedział czystego przypadku przy n=28 to **0,396–0,609**, a silnik stoi na 0,597. Bramka może model ODRZUCIĆ, nie może go zatwierdzić.

**01.08 — Krok 2, model stawiający cue wejścia: NIE POWSTAŁ, bo zadanie nie istnieje w danych.**
Mediana czasu wejścia: **−0,1 s**. W **18 z 21** zmierzonych szwów Janek po prostu puszcza płytę od początku. Test domykający: produkcyjna reguła wejścia wskazuje intro jako najlepsze miejsce w **1 z 15** jego utworów (6,7%) wobec 25,9% w bibliotece i 16,7% czystego przypadku, **p = 0,989**.
*(Dopowiedzenie z 14.08: jego 338 ręcznie postawionych cue ma medianę na **52,8% długości utworu**, a pady idą monotonicznie w prawo — A 0,468, B 0,651, C 0,688, D 0,803. Jego cue to WYJŚCIA, nie wejścia. Mix out pozostaje nietknięty przez jakikolwiek pomiar.)*

**02.08 — trzeci przeciek danych tego samego dnia.** Klasyfikator „próbka 30 s czy pełny plik" osiąga **AUC 0,889 na samych wektorach**. Model dostawał punkty za rozpoznanie ŹRÓDŁA, nie za wybór. Po warstwowaniu negatywów wynik spadł 0,685 → 0,678.

**03.08 — szkoły sekwencjonowania.** Model per DJ niemożliwy: **388 unikalnych DJ-ów, 299 z jednym miksem**. Trzy szkoły z zachowania: zachowawcza 429 miksów, drum&bass 44, skoki 292 (tam wylądował Ben UFO).
**OBALONE:** osobne modele nie płacą. Zachowawcza +0,020, D&B **−0,022**, a szkoła skoków — jedyna, która nas interesuje — **+0,001**.
Wniosek, najgłębszy w całym projekcie: *„zbiór ludzi, których łączy to, że są nieprzewidywalni, nie ma wspólnej logiki do wyuczenia — bo nieprzewidywalny to nie styl, tylko brak stylu w sensie statystycznym"*. To domyka wątek „czemu silnik nie przewiduje Janka": powód może być TEN SAM.
Efekt uboczny, darmowy: model nieliniowy zamiast logistycznego, **0,617 → 0,635**, jedna linijka.

**03.08 — trzy warianty skrócenia analizy tempa, wszystkie ODRZUCONE kryterium postawionym przed pomiarem.** Pełny 97,4%, okno 96,3% (2,1× szybciej), hybryda 96,8% (1,6×). Wszystkie 8 rozjazdów to błędy **oktawy**. Wniosek: wycinanie audio to zła dźwignia, bo okno pozbawia wybór oktawy dowodów.

**03.08 — największy brak silnika zamknięty bez uczenia czegokolwiek:** struktura utworu leży już policzona przez Rekordbox w plikach analiz, tag PSSI. Pokrycie **1740 z 1874 (92,8%)**, słowniki odczytane ze zrzutów, nie zgadnięte; jeden nierozpoznany nastrój zostaje **BEZ etykiety**.

---

## AKT V · ŁAWKA (08–11.08.2026)
**Założenie: mierzmy na kimś innym niż Janek.**

Powstaje mapa DJ-ów z festiwali: **39 267 utworów, 21 015 szwów, 1022 sety od 869 DJ-ów**, 9770 utworów zmierzonych z 30-sekundowych próbek (pobierz → policz → skasuj).

**POTWIERDZENIE (08–09.08) — jedyne duże w tym akcie.** Teza tripletów Janka: B jest mostem między A i C.
Na 152 świeżych setach i 2473 przypadkach: **triplet 56,8% vs para 47,7% top-1, p < 0,0001**. Optymalne alfa = 1,0, czyli **przyszłość waży dokładnie tyle, co przeszłość**. W worku DJ-a 29,6% vs 14,8% (podwojenie), między filarami 36,2% vs 28,1%.
**Ale przy otwartej budowie zysk to ZERO (p = 0,88).** Synteza w jednym zdaniu: *„most potrzebuje drugiego brzegu"* — siła tripletu bierze się z OGRANICZENIA, nie ze spekulacji.

**10.08 — błąd, który zawyżał bazę o 71%.** Endpoint wyszukiwania NTS **ignoruje parametr zapytania**: dla „Ben Klock" i dla bzdury „zzzzqqq" zwraca to samo. NTS wniósł **85 pozycji, nie 105 145**.
**Wynikło:** twarda reguła — przy każdym nowym API pierwszym testem ma być zapytanie, które NIE POWINNO nic zwrócić. Zastosowana nazajutrz.

**10.08 — KSZTAŁT SETU. Największe obalenie w warstwie produktu.**
Łuk „build" był w silniku od początku, jako oczywistość odziedziczona jeszcze po Kreatorze z czerwca.
**OBALONY na dwóch niezależnych instrumentach:** na 29 sesjach z mapy i na 2 nagranych setach Janka **płaska linia opisuje set LEPIEJ niż nasz łuk — 22/29 i 6/6**, mediana błędu 0,260 vs 0,319. Realne sety mają medianę **5 spadków energii na set**, których łuk zabraniał. Bloków też nie ma: test permutacyjny istotny w 4 z 29.
**Wynikło (11.08):** Janek — *„to wywalmy, jak śmierdzi"*. Domyślny łuk zmienia się na `off`, a wierność łukowi jest raportowana jako **None, nie jako liczba** — bo wierność celowi, którego nie ma, nie jest pomiarem.

**11.08 — AUDYT ABLACYJNY z progami czerwonej flagi zarejestrowanymi PRZED biegiem.** Na 3612 realnych przejściach z mapy:

| składnik | wkład |
|---|---|
| naiwna różnica tempa | 0,500 → **0,615** |
| oktawowe bpm_score | +0,010 |
| brzmienie | +0,018 |
| harmonia | **0** (czerwona flaga) |
| priorsy z korpusu | **0** |
| energia | **0** |
| mixability | **0** |

**Cztery z sześciu składników rdzenia nie zarabiają nic.** Naiwna różnica tempa robi prawie całą robotę. Kontrola dla harmonii na podzbiorze z pewną tonacją (n=159) pokazała, że mediana wręcz **SPADA: 0,583 → 0,400**.

**09.08 — sito brzmienia, wynik dwustronny.** Sito 20% zatrzymuje **51,8%** realnych wyborów DJ-a (2,6× nad losem) — ale ta sama liczba mówi, że **WYCINA ~48%**. Realny DJ wychodzi poza sąsiedztwo brzmieniowe co drugi wybór.

---

## AKT VI · INSTALACJA WODNA (12–14.08.2026)
**Założenie: to, co zmierzone, jest w produkcie.**

**13.08 — audyt na czystym klonie, w noc przed prezentacją.**
**OBALONE:** plik `priors_v1.json` ze zmierzonymi wagami wpadł pod zbiorczą regułę `.gitignore`. Odczyt cicho cofał się do domyślnych, więc **czysta instalka rankowała przejścia inaczej niż maszyna dewelopera**. Lipcowy wynik, którego poza Jankiem nikt nigdy nie miał.

**13.08 — naprawa oktawy poniżej 100 uderzeń COFNIĘTA.**
Przed naprawą zgodność z Rekordboksem **97,5% (192/197)**, po naprawie **80,2% (158/197)** — zepsute **33 prawdziwe utwory**. Przyczyna: próg dobrany na **syntetycznych click-trackach** (dają 0,51), podczas gdy prawdziwy house daje powyżej 0,80.
**Reguła:** syntetyczne nagrania wystarczą, żeby wadę ZNALEŹĆ, ale nie wolno na nich dobierać progu.

**13.08 — wykrywanie tonacji zawodne w OBU narzędziach.** Nasza analiza zgadza się z Rekordboksem w **36,0%**; nawet przy naszej najwyższej pewności — **54,3%**. Przejść z pewną tonacją po obu stronach: **197 z 21 015 = 0,94%**.
**Wynikło:** szczebel harmoniczny ablacji zablokowany — z powodu zmierzonego, nie z podejrzenia. Waga 0,35 na członie harmonicznym opiera się na wejściu, o którym wiadomo, że dwa niezależne algorytmy zgadzają się w połowie przypadków.

**14.08 (dziś) — dwa domknięcia archeologiczne, oba przez pomiar:**
- **Graf pokrewieństwa artystów PRZEGRYWA z listą popularności** na każdym progu: pokrycie@20 1,92% vs 2,11%, @50 2,99% vs 3,84%, **@100 4,07% vs 5,57%**. Przyczyna strukturalna: **84,1% wykonawców (11 616 z 13 804) występuje w dokładnie jednym secie**, a tylko 152 z 18 949 par (0,8%) powtarza się więcej niż raz. Wymiar „artysta" jest za rzadki, żeby zrobić z niego graf.
- **Lista zakupowa z czerwca nie wyprodukowała ani jednego zakupu.** Z 35 pozycji istnieją dziś jako pliki trzy — i wszystkie trzy były na dysku ZANIM lista powstała. Cztery pozycje oznaczone jako „nieznalezione" leżały wtedy w jego kolekcji.

---

## CO Z TEGO WYNIKŁO — reguły z datą urodzenia

Każda z tych reguł jest kupiona konkretną porażką, nie wymyślona:

| Reguła | Cena, którą zapłaciła |
|---|---|
| **Nie zmyślać wyniku; brak = `None` + ostrzeżenie, nigdy wartość domyślna** (ADR-005, cytowana 71 razy w kodzie) | 7 wierszy `bpm 79 / key 10A` z 19.06 i siedem napraw z 25.07 |
| **Rejestruj przewidywanie i próg PRZED pomiarem** | P1–P5 (17.07), próg 100 przy bramce repertuaru (20.07), czerwone flagi ablacji (11.08) |
| **Pierwszy test API = zapytanie, które NIC nie powinno zwrócić** | 105 145 → 85 pozycji, baza zawyżona o 71% (10.08) |
| **Zawsze kontrola negatywna** | przetasowane pary (30.07), przypadek jako klasa kontrastowa, negatywy warstwowane po źródle (02.08) |
| **Miernik pokazujący zero może mierzyć nie to** | 350 plików „pustych" przy „0 problemów", duplikaty ID H006, pusty wynik agenta nieodróżnialny od „kod czysty" (25.07) |
| **Najdroższe błędy siedzą w WEJŚCIU, nie w modelu** | pole 94 uderzeń (28.07), zapytanie NTS (10.08), przeciek źródła AUC 0,889 (02.08), `.gitignore` na priorsach (13.08) |
| **Syntetyk znajduje wadę, ale nie kalibruje progu** | 33 zepsute utwory i git revert (13.08) |
| **Wagi nie są faktami; nie stroić, bo demo lepiej wygląda** | 35 wycofanych ocen (21.07) |
| **Dobra decyzja ze słabym uzasadnieniem zostanie odwrócona** | poprawka uzasadnienia „nie dla DJ-ów weselnych": nie „psują algorytm", tylko „na weselu nie ma szwu" (10.08) |
| **Mierz dolną tercję, nie średnią** | percentyl bazowy rozkłada się 0,44–0,97 na 60 miksach — wariant może podnieść średnią, obsługując wyłącznie DJ-ów, którym podpowiedzi są najmniej potrzebne (03.08) |
| **Przed „tego nie ma w kodzie" — grep, nie pamięć** | kotwica z ulubionych istniała od 09.08 i była niewidoczna przez trzy dni (12.08) |

---

## KSZTAŁT CAŁEGO ŁUKU

Przedmiot badania **zwężał się i za każdym razem stawał uczciwszy**:

**opisać muzykę** (czerwiec, vault) → **opisać utwór** (lipiec, deskryptory) → **opisać parę** (korpus, priorsy) → **opisać SZEW** (30.07, pomiar różnicowy) → **opisać szew TEGO DJ-a** (01.08, test 28 przejść) → **opisać, czego NIE WIEMY** (11–13.08, ablacja i tonacje).

I druga oś, równoległa: **źródło prawdy przenosiło się od deklaracji do pomiaru**. Graf artystów napisany przez model → graf mierzony z dźwięku. Energia wpisana ręką do notatki → energia liczona z sygnału. Ocena 1–5 wystawiona przez jednego człowieka → 21 015 szwów od 869 DJ-ów. Łuk energii przyjęty jako oczywistość → łuk zmierzony i obalony.

Stan na 14.08.2026, powiedziany bez upiększeń: **silnik ma dwa zarabiające składniki na sześć, jest ślepy na realnych przejściach swojego jedynego użytkownika (0,597 przy losie 0,5), jego bramka pomiarowa jest zbyt słaba, żeby cokolwiek potwierdzić (n=28), a jedyne twardo potwierdzone tezy to reguła wejścia (71% vs 18%), triplety przy ustalonym drugim brzegu (+9,1 pp) i sztywna siatka bitów (1,7 vs 8,0 milibitu).**

I to jest, paradoksalnie, najlepszy wynik tego łuku. Projekt **wie, czego nie wie**, i każde „nie wiem" ma datę, liczbę i skrypt, którym da się je powtórzyć. W czerwcu miał 118 notatek, z których 7 było zmyślonych i nikt nie umiał ich odróżnić.