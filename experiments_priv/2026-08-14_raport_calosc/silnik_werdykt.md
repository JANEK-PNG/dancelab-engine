# Ocena DanceLab Engine

Piszę to jako architekt, który przeczytał kod, a nie jako recenzent, który przeczytał opis. Sprawdziłem dziś w repozytorium cztery rzeczy, na których opiera się najwięcej poniższych twierdzeń: HEAD to `3a23d1a` (13.08, 23:58, „S plays the seam in the Set tab"), zakładki nazywają się `tab-lib / tab-dj / tab-set / tab-export` (`src/dancelab/tui/app.py:94`) i nie ma wśród nich `tab-cue`, ocena przejścia jest przycinana do 1,0 (`set_builder.py:823`), a remis rozstrzyga sortowanie `(-score, candidate)` (`set_builder.py:1010`).

**Werdykt w jednym zdaniu:** to jest prawdziwy silnik badawczy z niezwykle rzadką dyscypliną dowodową i realnym wyjściem do narzędzia, w którym się gra — obudowany produktem, który w dzisiejszym commicie się wywala, i podpięty do wzoru, który w typowym kroku nie dociera do decyzji.

---

## 1. Co ten projekt naprawdę osiągnął

**Tor od pliku audio do padu na CDJ-u, domknięty.** Folder → analiza → set → hot cue wpisane do `master.db` Rekordboxa, z kopią zapasową całego kompletu plików WAL i weryfikacją treści każdego cue po zapisie (`ingestion/rb_backup.py:144-164`, `rekordbox_cue_writer.py:158-183`, domyślnie na kopii bazy, `:247`). To jest ta część, której większość projektów „AI dla DJ-ów" nie ma: wyjście do programu, w którym DJ naprawdę pracuje, a nie do osobnego widoku obok.

**Pomiar czasu lepszy od niezależnego odniesienia.** Sztywna siatka bitów: średni błąd **1,7 milibitu wobec 8,0** dla trackera, na 183 utworach, mierzone względem Rekordboxa — czyli algorytmu, który nie jest własny (`preprocessing/rigid_beatgrid.py:10-11`). To nie jest deklaracja, tylko wynik, i jest obroniony trzema kalibracjami z zapisanym rozkładem: próg zaufania 2,2 leży w zmierzonej luce między materiałem arytmicznym (1,09–1,99) a płytami klubowymi (2,42–4,08) na 49 płytach (`core/rigid_grid.py:29-40`); margines oktawy 1,27 stoi na 184 płytach, gdzie złe degradacje kończą się na 1,210, a dobre zaczynają od 1,323 (`rigid_grid.py:55-73`).

**Wynik negatywny o własnym produkcie, wdrożony.** Rampa energii „build" opisywała prawdziwe sety **gorzej niż płaska linia**, a realne sety mają medianę 5 spadków energii powyżej 8% — czyli dokładnie to, czego „build" zabraniał. Kształt nie został poprawiony, tylko zdjęty: `arc="off"` jest domyślne, a człon energii zwraca stałe 1,0 (sprawdzone: `set_builder.py:516-533`). Bardzo niewiele zespołów kasuje własną funkcję na podstawie pomiaru, który ją obala.

**Potwierdzenie i obalenie w jednym akapicie.** Krawędź mostowa podnosi dokładne rekonstrukcje z **28,1% na 36,2%** na 636 segmentach prawdziwych setów, p<0,0001 — a spekulacyjny lookahead bez celu zmierzono jako bezwartościowy (p=0,88 na 152 setach) i **celowo go nie ma** (`set_builder.py:976-983`).

**Pomysł metodologiczny, nie tylko implementacyjny.** Wyśrodkowanie przestrzeni CLAP przed porównaniem z kotwicą: mediana kosinusa między centroidami 363 par DJ-ów spada z **0,886 do 0,008**, a para faktycznie pokrewna zostaje przy +0,458 (`decision/steering.py:50-56`). Bez tego kroku każda kotwica dawała ten sam set — i to zostało zdiagnozowane pomiarem, nie odczuciem.

**Priory z korpusu z poprawną konstrukcją pomiarową.** 6144 dopasowane przejścia prawdziwych DJ-ów wobec bazy losowej **w tym samym miksie** (`data/reports/corpus_priors/priors_v1.json`). Baza w tym samym miksie, a nie globalna, to różnica między pomiarem a artefaktem.

**Skala.** ~8500 linii warstwy decyzyjnej, 11 421 walidacji, 6178 aplikacji terminalowej, 17 701 linii testów w 114 plikach (827 funkcji testowych, przebieg ~2,5 min).

**I teraz druga strona tego samego bilansu, żeby nie było zawyżenia.** Jedyna liczba mówiąca, czy silnik zgadza się z uchem DJ-a, to **Pearson r = 0,184 przy n = 48** (sesja Janka r = 0,302 przy n = 36, zero ocen w ciemno). Bramka poprawnie mówi „NOT READY FOR TUNING, brakuje 4 sesji" (`validation/dj_benchmark.py:24-25`). Autorska drabina pięciu modeli (C_rule / C_sim / I / N) **nigdy nie policzyła się na prawdziwych danych** i przy obecnej regule bramki nie da się jej odpalić — wymaga 100% pokrycia wszechświata, który z definicji zawiera 96 miksów odrzuconych przez człowieka podczas adjudykacji (`validation/djmix/ordering_models.py:312-315`). Bramka repertuaru stoi na 86 obserwacjach przy wymaganych 100. Czyli: warstwa pomiarowa jest zbudowana, ale najważniejsze pomiary jeszcze nie zapadły.

---

## 2. Co jest nietypowo dobre jak na jedną osobę bez wykształcenia inżynierskiego

Nietypowe nie jest to, że kod działa. Nietypowe jest **to, czego kod odmawia**.

- **Kontrakt uczciwości jest egzekwowany kodem, nie regulaminem.** Wczytywanie kart modeli *odmawia* przyjęcia deklaracji stopnia dowodu E5/E6 (`core/provenance.py:41-50`). `quality_score` zostaje pusty na torze sztywnym, bo kontrast to nie prawdopodobieństwo. `downbeat_phase_verified` zostaje na fałszu i jest realnie wpięte w bramkę eksportu (`decision/cue_grid.py:36-44`). Nieznana energia dostaje medianę puli i wypada ze skali, nigdy zero (`set_builder.py:1372-1402`). To jest zasada zamieniona w mechanizm, którego nie da się obejść przez nieuwagę — a nie w akapit w dokumentacji.
- **Zero znaczników TODO/FIXME/HACK w 8500 liniach warstwy decyzyjnej.** Dług nie jest odkładany na karteczkach, tylko opisywany jako zmierzony fakt z liczbą i datą.
- **Odrzucenie własnego, już wpiętego wyniku po audycie pola źródłowego.** Mediana długości przejścia z korpusu (94 uderzenia) była w kodzie. Audyt pokazał, że 14,3% wartości tego pola jest **ujemnych** (do −14526), a 28,7% przekracza cztery minuty — pole mierzy odstęp między dopasowanymi obszarami, nie długość miksowania. Liczba została wypięta, a test pilnuje, żeby nie wróciła (`core/phrasing.py:95-113`, `tests/test_corpus_transition_length.py`).
- **Obalenie własnej wcześniejszej hipotezy z liczbami.** „Red Light Fever: silnik 120,01, realnie 117,45" — sprawdzone: dopasowanie przy 120,00 to 3,00, przy 117,45 tylko 1,02. Komentarz kończy się zdaniem „przesłanka tamtej poprawki była fałszywa i tamtej poprawki nie ma po co pisać" (`ingestion/rekordbox_grid_snap.py:119-134`).
- **Debugowanie na poziomie, którego nie ma większość zawodowych zespołów.** Diagnoza „utwory nieocenialne systematycznie WYGRYWAJĄ z ocenionymi" — z mechanizmem, z zależnością od wagi i z nazwiskami zwycięzców (Farsight 100% bez wektora, K-LONE 100%, HAAi 71%) — `decision/sito_brzmienia.py:18-29`.
- **Najniebezpieczniejsza logika wyjęta z miejsca, gdzie się nie dało jej testować.** Reguły chroniące bibliotekę DJ-a mieszkały w pisarzu Rekordboxa, więc ich testy cicho się pomijały na CI i przy otwartym Rekordboksie. Zostały przeniesione do czystej funkcji nad zwykłymi danymi (`decision/cue_write_ops.py:1-12`).
- **Pas ostrzegawczy odwracający domyślne zachowanie pytest** (`tests/conftest.py:30-53`): pominięty test nie jest cichą kropką, bo „ciche pominięcie zamienia zielony przebieg w fałszywe uspokojenie".
- **Świadome puste miejsca.** Kotwica z własnych utworów ma **pusty kontur**, bo to cecha sposobu grania, której ze zbioru utworów odczytać się nie da (`decision/anchors.py:58-83`). Tryb nastroju nr 3 Pioneera nie ma etykiet, bo numeracja się nie zgadza na zrzutach.

**Uczciwa obserwacja o źródle mocnych i słabych stron.** Wszystko, co w tym projekcie jest najlepsze, wymaga dyscypliny myślenia i można to wymyślić samemu. Wszystko, co jest najsłabsze — brak wspólnych modułów, brak granic pakietów, brak jednego źródła prawdy, dziewięć kopii tej samej funkcji sumy kontrolnej, sześć kopii `_nfc`, cztery czytniki tego samego pliku Pioneera — to są rzeczy, których się nie wymyśla, tylko przejmuje z pracy w zespole. Brak dyplomu nie jest tu widoczny; brak zespołu jest widoczny wszędzie.

---

## 3. Gdzie jest realny dług i co on kosztuje

### Poziom 1 — psuje produkt dzisiaj

**(a) Aplikacja wywala się na klawisz S w zakładce Set.** `app.py:2471` ustawia aktywną zakładkę na `"tab-cue"`, a taka zakładka nie istnieje (sprawdziłem: `_TAB_ORDER` w linii 94 zawiera cztery inne identyfikatory). Textual rzuca `ValueError` i ubija program. To jest **ostatni commit w repozytorium** — czyli stan, w jakim projekt stoi. Commit dodał 32 linie i zero nowych testów, a instrukcja użytkownika (także w PDF na biurku) wciąż każe naciskać S, żeby zapisać plan.

**(b) Bramka jakości jest czerwona.** `pytest`: 1 failed / 835 passed. `ruff check src tests`: 26 błędów. Padł strażnik nomenklatury (`tests/test_nomenklatura.py:55`), bo ten sam commit przeniósł zapis planu na Ctrl+S i nie poprawił słownika. **Strażnik zadziałał dokładnie tak, jak miał — i nikt nie zareagował.** Koszt: od tej chwili każda prawdziwa nowa awaria wygląda identycznie jak ta znana. To jest mechanizm, przez który zespoły przestają patrzeć na testy.

**(c) Wagi wzoru nie docierają do decyzji.** Sprawdzone w kodzie: rdzeń ma podłogę 0,20 (stała energia przy `arc="off"`), mnożnik priorów sięga 1,654, a wynik jest przycinany do 1,0 (`set_builder.py:823`). Pomiar z przekroju na prawdziwej puli: w **30 krokach na 30** na suficie 1,000 stoi więcej niż jeden kandydat, **mediana 38 remisujących**, maksimum 88 — a remis rozstrzyga sortowanie po `track_id`, czyli skrót ze ścieżki pliku (`set_builder.py:1010`). Koszt jest maksymalny: dyskusja o tym, czy harmonia ma ważyć 0,35 czy 0,30, jest bezprzedmiotowa, dopóki w typowym kroku o wyborze utworu decyduje nazwa pliku. Projekt zdiagnozował to zjawisko raz i załatał **obok** — premia za gatunek świadomie nie jest przycinana do 1,0, z uzasadnieniem „premia wpadała w sufit i remis rozstrzygała nazwa pliku" (`premia_gatunku.py:76-83`) — ale sam sufit `transition_score` został nietknięty.

**(d) Filar może po cichu wypchnąć inny filar z setu.** Nadanie roli krańcowej czyści z rozstawienia filar stojący na docelowej pozycji, a budowa dostaje wyłącznie `locked_positions`, nigdy listy „te utwory muszą się znaleźć" (`app.py:250-273` wobec `:3227-3228`). Aplikacja chwilę wcześniej pisze DJ-owi „filary w budowie: N (każdy MUSI zagrać)". Istniejący test utrwala to zachowanie zamiast je łapać.

**(e) Dwie drogi zapisu cue rozjeżdżają się w sposób, który uszkadza bibliotekę.** CLI `dancelab cues write` nie notuje UUID w rejestrze (`cli/cues.py:181-184`) — czyli wraca błąd z 09.08, dla którego rejestr powstał (8 z 26 padów odpadało, w tym 2 zablokowane naszym własnym zapisem). CLI dopasowuje ścieżki **bez normalizacji NFC** (sprawdziłem: `ingestion/rekordbox_match.py:26` to `normcase(normpath(p))` i nic więcej), a TUI z NFC — zmierzone dwa utwory spadają przez to na dopasowanie po samym tytule, przy 222 nadmiarowych wpisach w 159 grupach duplikatów. Weryfikacja zapisu tego nie złapie, bo sprawdza (utwór, pad, pozycja, komentarz), a nie „czy to ten plik, o który chodziło".

**(f) `dancelab cues restore` nadpisuje żywą bazę bez `--allow-live` i bez sprawdzenia, czy Rekordbox działa** (`cli/cues.py:191-215`) — mimo że zapis ma obie te bramki. Osobno: nieudane kopiowanie kopii z powrotem na żywy plik wywołuje blok ratunkowy, który **kasuje żywą bazę** (`rekordbox_cue_writer.py:300` + `rb_backup.py:157-173`), poza zasięgiem automatycznego przywracania. Prawdopodobieństwo małe, skutek maksymalny.

**(g) Drobniejsze, ale widoczne:** kolumna LUFS nigdy się nie wypełni, bo funkcja robocza straciła jedyne wywołanie (`app.py:2766-2804`); higiena puli przepuszcza wszystko, co nie zaczyna się od „/", czyli 25 dzisiejszych wpisów omija bezpiecznik przeciw stemom (`app.py:3032`); sortowanie po kolumnie „źr." sortuje po tytule i rysuje strzałkę przy złej kolumnie.

### Poziom 2 — psuje wiedzę o produkcie

- **96,7% tonacji w bibliotece to werdykt Rekordboxa z pewnością wpisaną na sztywno jako 1,0**, i dla 7910 strumieni Apple Music **nikt tego nigdy z niczym nie porównał** (47% zgodności zmierzono na 191 plikach lokalnych). Skutkiem ubocznym jest to, że mechanizm tłumienia oceny przy niepewnej tonacji (`harmonic.py:125`) w praktyce nigdy się nie odpala. Człon o najwyższej wadze stoi na cudzym werdykcie przyjętym jako prawda — w projekcie, który w module walidacji tempa nazywa ten sam program „referencją operacyjną, nie prawdą naukową".
- **TUI dokarmia tonacje z Rekordboxa przed budową, CLI i API nie** (`workflows/smart_playlist.py:588-594`). Ta sama komenda daje set liczony na innych danych zależnie od tego, przez które drzwi się weszło. Nikt o tym nie jest informowany.
- **Człon harmoniczny karze około 4,5× ostrzej, niż uzasadnia własny korpus projektu**: oceny relacji rozciągają oś Camelota na czynnik 6,7× (0,15 vs 1,0), a zmierzone lifty na 6144 przejściach — na 1,50×. Prawdziwi DJ-e robią ruch nazwany „risky" w 63,2% przejść.
- **Mixability ma dostępne 4 z 9 składników** na ścieżce budowy setu (mediana pewności 0,36), czyli 0,47 jego wagi to arytmetyczna stała 0,5. Do tego harmonia i tempo są liczone dwa razy, różnymi wzorami — realny udział harmonii to 0,38, tempa 0,284, a nagłówek pliku przedstawia je jako rozłączne.
- **Pole `rms` znaczy dwie różne rzeczy**: dla 98% analiz to wysokość słupka fali Pioneera podzielona przez 31, dla reszty prawdziwe RMS z audio. Nigdzie nie ma o tym komentarza, a `energy_fit` porównuje je wprost.
- **Dwie najsilniejsze rzeczy w domyślnej ocenie — waga brzmienia 0,6 i mnożnik priorów — nie mają wpisu w `configs/formula_terms.yaml`** i wymykają się testowi „każdy składnik ma opis". Do tego wektory CLAP pokrywają ~19% biblioteki.

### Poziom 3 — kosztuje czas, nie poprawność

Zamrożone aktywa: planer sekwencji (1005 linii) bez drogi z produktu; menedżer cache'u (361 linii, limit 10 GB) niepodłączony, podczas gdy `~/.dancelab/seams` rośnie bez ograniczeń po ~16 MB na szew; dwa katalogi Apple Music (1996 linii) bez konsumenta; `stems/envelopes.py` bez wywołania; równoległość analizy nieosiągalna z produktu; czytnik pendrive'a martwy, przez co warunek `verified_cue` w `cue_plan.py:152` jest zawsze fałszywy. Powielenia: 9 kopii sumy kontrolnej, 6 `_nfc`, 4 czytniki PQTZ, 5 dróg wczytania audio, 28 fabryk `AnalysisResult` w testach, dwa progi „za długie, żeby być płytą" (10 i 15 minut — 115 utworów w szarej strefie). Suma kontrolna każdego pliku przy każdym uruchomieniu (kilkanaście–kilkadziesiąt GB przy 1900 utworach). Rejestr zawsze zapisuje poziom „quick", więc `--analysis-depth deep` przelicza cały folder od zera.

### Dług osobnej kategorii

**System „In Between" — `P = (C, D, Syn, U)`, rama `F`, próg `theta = 0,18` — nie istnieje w kodzie.** Występuje wyłącznie w warstwie rysunkowej (`docs/vj-system/portret-vj.js:57`, `docs/mockup-dj-karty/portret.js:3`, `docs/scena-v2/index.html:165`), która czyta gotowe liczby z pliku i powołuje się na `profil_in_between.py` — skrypt, którego w repozytorium nie ma. To jest ryzyko komunikacyjne, nie techniczne, ale w kontekście rekrutacyjnym jest to najdroższy możliwy rodzaj błędu: jeśli „In Between" jest przedstawiane jako to, co liczy silnik, to przedstawiane jest coś, czego silnik nie liczy — w projekcie, którego największą wartością jest właśnie to, że nigdy nie udaje wyniku.

---

## 4. Trzy najważniejsze rzeczy do zrobienia, w kolejności

Zanim trójka: naprawa `"tab-cue"` w `app.py:2471` to nie jest priorytet, tylko obowiązek na dziś — jedna linia plus test naciskający „s".

**1. Zdjąć sufit skali i zmierzyć, ile decyzji naprawdę zapada wzorem.**
Policzyć na prawdziwej puli i prawdziwym briefie, ile kroków budowy kończy się remisem rozstrzyganym alfabetycznie. Jeśli potwierdzi się rząd 38 kandydatów, to obcięcie w `set_builder.py:823` trzeba zdjąć dokładnie tak, jak zrobiono to już świadomie dla premii za gatunek (`premia_gatunku.py:77-83`) — ta liczba jest kluczem porządkującym wewnątrz wyboru następnika, a nie oceną pokazywaną DJ-owi. **Dlaczego pierwsze:** dopóki wzór nie dociera do decyzji, każdy kolejny pomiar wag, priorów i brzmienia mierzy nazwę pliku. To unieważnia najwięcej dotychczasowej pracy naraz i jest najtańsze do naprawienia.

**2. Przywrócić zieloną bramkę i zamknąć drogi, którymi da się uszkodzić bibliotekę.**
Jedno zadanie, bo to jedna kategoria: `pytest` i `ruff` do zera; `restore` pod te same dwie bramki co `write`; NFC w `rekordbox_match._norm_path` (jedna linia, wzorzec już istnieje w `rekordbox_lookup.py:18`); dopisanie do rejestru UUID w ścieżce CLI; wyjęcie ostatniego kroku bezpiecznej podmiany spod funkcji, która przy błędzie kasuje cel. **Dlaczego drugie:** ten projekt broni się jednym mechanizmem — strażnikami, które krzyczą, gdy coś się rozjedzie. Strażnik świecący na czerwono na stałe przestaje być strażnikiem, a wtedy cała reszta dyscypliny przestaje działać niezależnie od tego, jak dobrze jest napisana.

**3. Zamknąć pętlę z uchem — na wzorze, którym naprawdę stoi produkt.**
Dobrać brakujące 4 sesje po 30 ocen, z realnym udziałem ocen w ciemno, i **najpierw naprawić pokój przejść**: dziś układa propozycje wzorem `0,5 × harmonia + 0,5 × tempo` (`cli/tui.py:105`), którego produkt nie używa nigdzie indziej, więc zbierane werdykty opisują ranking, jakiego silnik nigdy nie wyprodukuje. Przy okazji podpiąć werdykty do silnika — dziś nie docierają nigdzie i są kluczowane po `ContentID` Rekordboxa, a cały silnik po `make_track_id`. **Dlaczego trzecie, a nie pierwsze:** r = 0,184 przy n = 48 to jedyna liczba mówiąca, czy to działa dla człowieka — ale zbieranie kolejnych ocen na rankingu, który w typowym kroku rozstrzyga się alfabetycznie, i na wzorze innym niż produkcyjny, dołoży dane, których i tak nie będzie wolno użyć.

**Poza trójką, bo to nie jest inżynieria:** rozstrzygnąć status „In Between" — albo zaimplementować, albo przestać mówić o nim jako o tym, co liczy silnik. Projekt, który odrzucił własną zmierzoną medianę 94 uderzeń po audycie pola źródłowego, nie może sobie pozwolić na prezentowanie formalizmu, którego nie ma w kodzie.