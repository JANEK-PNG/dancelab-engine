# DanceLab — instrukcja użytkownika

| | |
|---|---|
| **Wersja dokumentu** | 2026-08-09 |
| **Dotyczy** | DanceLab (interfejs terminalowy), macOS |
| **Odbiorca** | DJ; wiedza techniczna niepotrzebna |
| **Wymagania** | Rekordbox 6 z biblioteką na tym komputerze; terminal Ghostty (do ostrych okładek); `ffmpeg` do odsłuchu |

DanceLab buduje sety z Twojej biblioteki: analizuje utwory, układa kolejność
wokół Twoich decyzji, pozwala ustawić hot cue i oddaje jedno i drugie do
Rekordboxa.

**Jak czytać ten dokument.** Rozdziały 1–3 czyta się raz, na początku.
Rozdział 4 to procedury — otwierasz konkretną, kiedy masz coś zrobić.
Rozdziały 5–7 służą do sprawdzania w trakcie pracy. Rozdział 8 to awarie.

---

## Spis treści

1. [Zanim zaczniesz](#1-zanim-zaczniesz)
2. [Słownik pojęć](#2-słownik-pojęć)
3. [Budowa ekranu](#3-budowa-ekranu)
4. [Procedury](#4-procedury)
5. [Skróty klawiszowe](#5-skróty-klawiszowe)
6. [Jak czytać ekran](#6-jak-czytać-ekran)
7. [Czego DanceLab nigdy nie robi](#7-czego-dancelab-nigdy-nie-robi)
8. [Rozwiązywanie problemów](#8-rozwiązywanie-problemów)

---

## 1. Zanim zaczniesz

### 1.1. Uruchomienie

**Cel:** uruchomić DanceLab.

**Kroki**

1. Kliknij dwukrotnie aplikację **DanceLab** na biurku.
2. Poczekaj, aż w oknie terminala **Ghostty** pojawi się zakładka
   **Biblioteka**.

**Wynik:** aplikacja działa i wczytuje bibliotekę w tle. Skrót zawsze
uruchamia aktualną wersję programu.

### 1.2. Uruchomienie zapasowe

Użyj tego sposobu, gdy skrót z biurka zginie.

| sposób | co zrobić |
|---|---|
| plik `.command` | Kliknij dwukrotnie **DanceLab.command** w `Developer/dancelab-engine` (kopia leży na biurku). Kliknięty w zwykłym Terminalu sam przenosi się do Ghostty. |
| linia poleceń | Wpisz w terminalu: `cd ~/Developer/dancelab-engine && .venv/bin/dancelab tui` |

**Uwaga:** przy pierwszym uruchomieniu macOS może poprosić o zgodę. Kliknij
plik prawym przyciskiem i wybierz **Otwórz**. Pytanie pojawia się tylko raz.

**Dlaczego akurat Ghostty:** ten terminal wyświetla grafikę, więc okładki są
ostre. W terminalach bez grafiki okładki są mozaikowe — reszta programu
działa tak samo.

---

## 2. Słownik pojęć

Nazwy z tej tabeli są używane w całym dokumencie i w samym programie
konsekwentnie — jedno pojęcie ma jedną nazwę.

| pojęcie | znaczenie |
|---|---|
| **silnik** | część DanceLab, która analizuje utwory i układa kolejność |
| **brief** | formularz po lewej w zakładce Set: długość, okno tempa, gatunki, kotwica, świeżość. Twoje zamówienie na set |
| **set** | ułożona kolejność utworów w tabeli |
| **filar** | utwór oznaczony w Bibliotece jako obowiązkowy: musi zagrać w budowanym secie. Filarów jest od 3 do 10 |
| **kotwica** | brzmienie „graj jak…": wybrany DJ, do którego silnik zbliża dobór utworów |
| **szew** | przejście między dwoma sąsiednimi utworami setu |
| **pasek szwu** | panel nad tabelą w zakładce Set (klawisz <kbd>C</kbd>) z faktami o szwie. Sam nic nie gra |
| **pad** | jedno z ośmiu miejsc A–H, w których leży hot cue — jak pady na CDJ |
| **hot cue** | punkt startowy zapisany na padzie; to on trafia do Rekordboksa |
| **plan** | zapisany na dysku stan setu, z nazwą. Można do niego wrócić po zamknięciu programu |
| **werdykt** | zapis Twojej decyzji (cięcie, podmiana, przesunięcie). Z tych zapisów silnik będzie uczył się Twojego gustu |
| **notki** | dziennik silnika: czego nie wie, co odrzucił i dlaczego (klawisz <kbd>L</kbd>) |
| **LUFS** | zmierzona głośność utworu. Im bliżej zera, tym głośniej |
| **seed** | liczba sterująca losowością świeżości. Ten sam seed powtarza identyczny set |

---

## 3. Budowa ekranu

### 3.1. Zakładki

Zakładki przełączasz klawiszami <kbd>Ctrl</kbd>+<kbd>Tab</kbd> albo
kliknięciem w nazwę.

| zakładka | do czego służy |
|---|---|
| **Biblioteka** | przeglądanie i szukanie utworów, odsłuch, ulubione, filary, dogrywanie nowych plików |
| **Set** | brief, budowa setu, poprawki, plany, wysyłka playlisty |
| **Eksport / Cue** | edytor hot cue dla zbudowanego setu, odsłuch szwów, wysyłka cue i playlisty |

### 3.2. Odtwarzacz

Odtwarzacz jest **przypięty do dolnej krawędzi w każdej zakładce** i jest
jeden wspólny: utwór puszczony w Bibliotece gra dalej po przejściu do Setu
i Eksportu.

Pasek zawiera, od lewej: przyciski **Poprz. · −8 · Graj · +8 · Nast.**,
okładkę, tytuł z wykonawcą, oś czasu z głowicą ▮ w bieżącym miejscu oraz
zegar „teraz / całość". Przyciski robią dokładnie to samo, co klawisze
z [rozdziału 5](#5-skróty-klawiszowe).

Utwór bez policzonej analizy pokazuje sam zegar, bez kształtu energii.

### 3.3. Pasek statusu

Ostatni wiersz ekranu pokazuje cztery rzeczy:

| element | znaczenie |
|---|---|
| stan Rekordboxa | „✅ zamknięty — W dostępne" albo „⛔ OTWARTY — zapis W zablokowany" |
| backupy | ile kopii bazy Rekordboxa leży na dysku |
| notki | licznik wpisów silnika; <kbd>L</kbd> pokazuje pełną listę |
| pula | katalog z przeanalizowanymi utworami |

### 3.4. Zakładka Eksport / Cue

<!-- zrzut: cue -->

| obszar | zawartość |
|---|---|
| karta u góry | wybrany utwór: oś energii, sekcje, pady na osi i podziałka czasu (po lewej); siatka padów 2×4 jak na CDJ (po prawej) |
| lista pośrodku | jeden wiersz = jeden utwór setu: oś energii z literami padów, liczba padów, pewność |
| dół | odtwarzacz, a pod nim przyciski **Wyślij cue do RB** i **Wyślij playlistę do RB** |

Siatka padów: A B C D w górnym rzędzie, E F G H w dolnym. Zajęty pad
pokazuje czas i znak stanu, pusty — przygaszoną kreskę.

| znak | znaczenie |
|---|---|
| ✓ | pozycja pewna |
| ? | posłuchaj przed graniem |
| ✋ | pad ustawiony Twoją ręką |

---

## 4. Procedury

Każda procedura ma ten sam układ: **cel**, **warunki wstępne**, **kroki**,
**wynik**.

### 4.1. Dograj nowe utwory do biblioteki

**Cel:** dodać pliki z dysku do puli, z której budowane są sety.

**Warunki wstępne:** pliki leżą w jednym folderze.

**Kroki**

1. Przejdź do zakładki **Biblioteka**.
2. Wklej ścieżkę folderu w pole **Analizuj** na dole ekranu.
3. Kliknij przycisk obok pola.

**Wynik:** utwory trafiają do puli. Pliki uszkodzone odpadają z imiennym
powodem w notkach, zamiast psuć analizę.

### 4.2. Zbuduj set z briefu

**Cel:** dostać ułożoną kolejność utworów.

**Warunki wstępne:** biblioteka jest przeanalizowana (procedura 4.1).

**Kroki**

1. Przejdź do zakładki **Set**.
2. Wypełnij brief: długość w minutach i okno tempa (na przykład `130-135`).
3. Opcjonalnie wybierz gatunki: naciśnij <kbd>Ctrl</kbd>+<kbd>G</kbd>,
   wskaż gatunek, naciśnij <kbd>Ctrl</kbd>+<kbd>G</kbd> ponownie, żeby go
   dodać lub zdjąć, i zamknij listę klawiszem <kbd>Esc</kbd>.
4. Opcjonalnie wybierz kotwicę: naciśnij <kbd>Ctrl</kbd>+<kbd>D</kbd>
   i wskaż DJ-a.
5. Naciśnij <kbd>B</kbd>.

**Wynik:** tabela pokazuje gotowy set; postęp budowy widać na żywo.

<!-- zrzut: set -->

**Uwaga:** lista gatunków zawiera tylko te, które faktycznie masz
w bibliotece, w nazewnictwie Beatportu, z liczbą utworów przy każdym. Tagi
spoza taksonomii Beatportu są w osobnej sekcji na końcu listy.

### 4.3. Zbuduj set na filarach

**Cel:** zbudować set wokół utworów, które muszą zagrać.

**Warunki wstępne:** brak.

**Kroki**

1. W zakładce **Biblioteka** oznacz klawiszem <kbd>F</kbd> od 3 do 10
   utworów.
2. Naciśnij <kbd>G</kbd>.
3. Wybierz tryb rozstawienia z okna, które się pojawi (tabela niżej).
4. Uzupełnij brief i naciśnij <kbd>B</kbd>.

**Wynik:** filary są w secie, oznaczone złotem i flagą ⚑, i zachowują się
jak zwykłe utwory.

| tryb | co robi |
|---|---|
| **Podpory** | silnik buduje set bez filarów, mierzy każde przejście i wstawia filary w najsłabsze miejsca |
| **Równy rozstaw** | filary rozłożone równomiernie po całym secie |
| **Rama** | najwolniejszy filar otwiera set, najszybszy zamyka |

Tryb zmienisz w każdej chwili drugim naciśnięciem <kbd>F</kbd> w zakładce
Set.

### 4.4. Popraw gotowy set

**Cel:** zmienić kolejność albo skład setu.

**Warunki wstępne:** set jest zbudowany (procedura 4.2 lub 4.3).

**Kroki**

1. Ustaw kursor na utworze.
2. Wykonaj jedną z czynności z tabeli niżej.

**Wynik:** set jest zmieniony, a każda zmiana zapisuje się jako werdykt.

| czynność | klawisze |
|---|---|
| podmień utwór | <kbd>Z</kbd>, kliknij propozycję, <kbd>Z</kbd> ponownie |
| dopisz utwór za zaznaczonym | <kbd>A</kbd>, kliknij propozycję, <kbd>A</kbd> ponownie |
| wytnij utwór | <kbd>X</kbd> |
| przesuń utwór | <kbd>Shift</kbd>+<kbd>↑</kbd> lub <kbd>Shift</kbd>+<kbd>↓</kbd> |

Panel propozycji pokazuje 10 utworów ocenionych w tym konkretnym miejscu
setu. Tryb oceny (smart / BPM najpierw / tonacja najpierw) wybierasz
w panelu. Wycięcie filaru zdejmuje też jego oznaczenie.

### 4.5. Zapisz plan i wróć do niego

**Cel:** zachować set na później.

**Warunki wstępne:** set jest zbudowany.

**Kroki — zapis**

1. Naciśnij <kbd>S</kbd>.
2. Wpisz nazwę i zatwierdź.

**Kroki — powrót**

1. Naciśnij <kbd>O</kbd>.
2. Kliknij plan na liście.
3. Naciśnij <kbd>O</kbd> ponownie.

**Wynik:** plan zawiera kolejność, brief i historię edycji. Działa także po
ponownym uruchomieniu programu.

**Uwaga:** <kbd>X</kbd> na liście planów usuwa plan do kosza obok planów.
Utwory, których nie ma już w puli, są przy wczytaniu pomijane z notką.

### 4.6. Posłuchaj utworu

**Cel:** sprawdzić utwór uchem.

**Warunki wstępne:** zainstalowany `ffmpeg` (`brew install ffmpeg`).

**Kroki**

1. Ustaw kursor na utworze.
2. Naciśnij <kbd>Spacja</kbd> albo <kbd>P</kbd>.

**Wynik:** utwór gra; oś czasu w odtwarzaczu pokazuje pozycję. Kolejne
naciśnięcie pauzuje, następne wznawia od miejsca pauzy.

Sterowanie w trakcie grania opisuje [rozdział 5](#5-skróty-klawiszowe).

### 4.7. Sprawdź szew między utworami

**Cel:** ocenić przejście z jednego utworu w następny.

**Warunki wstępne:** set jest zbudowany.

Szew ogląda się w zakładce Set, a słucha w zakładce Eksport / Cue —
dlatego, że w edytorze cue szew powstaje z padów, które masz na ekranie,
czyli z tego, co naprawdę pojedzie na CDJ-e.

**Kroki — fakty o szwie**

1. Przejdź do zakładki **Set** i ustaw kursor na utworze.
2. Naciśnij <kbd>C</kbd>.
3. Odczytaj pasek nad tabelą: liczba uderzeń, tempo, miejsce wyjścia
   i wejścia.
4. Naciśnij <kbd>C</kbd> albo <kbd>Esc</kbd>, żeby schować pasek.

**Kroki — odsłuch szwu**

1. Przejdź do zakładki **Eksport / Cue** i ustaw kursor na utworze.
2. Naciśnij <kbd>S</kbd>.

**Wynik:** słyszysz wyjście z tego utworu złożone z wejściem w następny.
Program wypisuje, których padów użył.

**Uwaga:** bez zaznaczonego pada szew idzie z ostatniego wyjścia w pierwsze
wejście następnego utworu; z zaznaczonym padem wychodzi właśnie z niego.
Ostatni utwór setu nie ma następnika i program mówi to wprost. Klawiszem
odsłuchu jest <kbd>S</kbd>, a nie <kbd>C</kbd>, ponieważ litery A–H należą
do padów.

### 4.8. Przestaw hot cue w czasie

**Cel:** przenieść pad w inne miejsce utworu.

**Warunki wstępne:** jesteś w zakładce **Eksport / Cue**, kursor stoi na
utworze.

Wybierz jeden z trzech sposobów.

**Kroki — sposób A: duży skok, „przenieś tutaj"**

1. Naciśnij <kbd>P</kbd>, żeby puścić utwór.
2. Strzałkami dojedź do miejsca, w którym pad ma stanąć.
3. Naciśnij literę pada raz, żeby go wybrać.
4. Naciśnij **tę samą literę drugi raz**.

**Wynik:** pad stoi pod głowicą odtwarzacza, dociągnięty do najbliższego
bitu.

**Kroki — sposób B: drobna poprawka**

1. Naciśnij literę pada.
2. Przesuwaj pad: <kbd>←</kbd>/<kbd>→</kbd> o jedno uderzenie,
   <kbd>Shift</kbd>+strzałka o osiem, <kbd>PgUp</kbd>/<kbd>PgDn</kbd>
   o trzydzieści dwa.

**Wynik:** pad jest przesunięty o dokładną liczbę uderzeń.

**Sposób C: wpisanie czasu z klawiatury** — patrz procedura 4.9.

**Uwaga:** <kbd>Z</kbd> cofa każdą zmianę o jeden krok. Po przesunięciu
propozycja silnika zostaje widoczna jako kropka, a pad jest opisany jako
ustawiony ręką — zawsze widzisz, o ile różnisz się od silnika.

### 4.9. Wpisz czas pada z klawiatury

**Cel:** ustawić pad na konkretnym czasie albo na początku frazy.

**Warunki wstępne:** pad jest wybrany literą.

**Kroki**

1. Naciśnij <kbd>T</kbd>. Czas w kratce pada zamienia się w pole do pisania.
2. Wykonaj jedną z czynności:
   - wpisz czas w formacie `2:31` albo `2:31.5` (przecinek działa jak
     kropka);
   - wybierz gotowy czas frazy z listy pod siatką klawiszami
     <kbd>↑</kbd>/<kbd>↓</kbd>.
3. Naciśnij <kbd>Enter</kbd>.

**Wynik:** pad stoi na wpisanym czasie, dociągniętym do siatki tak, jak
przy włączonym quantize w Rekordboksie: do taktu, gdy faza taktu jest
zweryfikowana, w przeciwnym razie do najbliższego bitu. Notka mówi, o ile
program dociągnął.

**Uwaga:** lista gotowych czasów zawiera początki sekcji utworu (intro,
break, groove, outro) oraz propozycję silnika. Lista **przewija się** —
licznik (na przykład `5/12`) i strzałki „↑ 4 wyżej / ↓ 3 niżej" mówią, ile
pozycji jest poza kadrem. <kbd>Esc</kbd> wychodzi bez zmiany. Przy
niepewnej siatce program zostawia dokładnie wpisany czas i pisze dlaczego.

### 4.10. Wyślij hot cue do Rekordboksa

**Cel:** przenieść pady z ekranu na pady w Rekordboksie.

**Warunki wstępne:** set jest zbudowany, a utwory są w kolekcji Rekordboxa.

**Ostrzeżenie:** kolejność kroków jest obowiązkowa. Pominięcie któregokolwiek
kończy się tym, że w Rekordboksie nie widać żadnych zmian.

**Kroki**

1. **Zamknij Rekordboksa.** Dopóki jest otwarty, przycisk **Wyślij cue do
   RB** jest wyszarzony i nazywa się *„Zamknij Rekordbox, żeby wysłać cue"*.
2. Naciśnij <kbd>W</kbd> (albo kliknij przycisk). Program liczy plan
   i pokazuje, ile padów wejdzie, ile ustąpiło Twoim własnym cue i czy
   któryś utwór jest spoza kolekcji. Przycisk zmienia nazwę na
   **„POTWIERDŹ: zapisz N padów"**.
3. Naciśnij <kbd>W</kbd> ponownie.
4. **Uruchom Rekordboksa.**

**Wynik:** pady są na miejscu. Program potwierdza liczbę zapisanych padów
i ścieżkę kopii bazy.

**Dlaczego tak:**

- Rekordbox musi być zamknięty, ponieważ zapis do jego bazy w trakcie pracy
  programu uszkodziłby ją.
- Rekordbox czyta bazę przy uruchomieniu, więc program otwarty od wcześniej
  pokaże stare pady.
- Przed zapisem powstaje kopia bazy, a po zapisie program sprawdza odczytem,
  czy pady naprawdę są. Jeśli nie — zmiana jest wycofywana.
- Padów, które ustawiłeś sam, program nigdy nie nadpisuje; ustępuje im
  i mówi o tym w podsumowaniu. Własne pady z poprzedniej wysyłki natomiast
  **odświeża**, żeby przesunięty pad dojechał do Rekordboksa. Rozpoznaje je
  po własnym rejestrze; cokolwiek w tym rejestrze nie leży, uchodzi za Twoje
  i zostaje nietknięte.

### 4.11. Wyślij playlistę do Rekordboksa

**Cel:** utworzyć w Rekordboksie playlistę z bieżącego setu.

**Warunki wstępne:** set jest zbudowany, Rekordbox jest zamknięty.

**Kroki**

1. Naciśnij <kbd>W</kbd> w zakładce **Set** albo kliknij **Wyślij playlistę
   do RB** w zakładce **Eksport / Cue**.

**Wynik:** playlista jest w bazie Rekordboxa. W tej samej chwili zapisuje
się werdykt końcowy — porównanie tego, co ułożył silnik, z tym, co
zostawiłeś. Nie ma osobnego klawisza do zapamiętania werdyktu.

### 4.12. Włącz okładki

**Cel:** zobaczyć miniatury okładek i uzupełnić brakujące.

**Warunki wstępne:** jesteś w zakładce **Biblioteka**.

**Kroki**

1. Naciśnij <kbd>K</kbd> albo kliknij przełącznik **okładki** pod polem
   szukania.

**Wynik:** lista pokazuje miniatury, a w tle rusza dociąganie braków.
Program znajduje pliki bez osadzonej okładki, pyta iTunes o wykonawcę
i tytuł i przy pewnym dopasowaniu wpisuje okładkę 600×600 do tagów pliku.
Trafienia niejednoznaczne są pomijane z powodem.

**Uwaga:** wyłączenie przełącznika tylko **chowa** okładki. Nic nie jest
kasowane, a okładki osadzone w plikach zostają tam na zawsze. Audio
pozostaje nietknięte.

**Ważne:** żeby okładki weszły do Rekordboxa i na ekrany CDJ, zaznacz utwory
w Rekordboksie i wybierz **Reload Tags**.

---

## 5. Skróty klawiszowe

### 5.1. Wszędzie

| klawisz | działanie |
|---|---|
| <kbd>Ctrl</kbd>+<kbd>Tab</kbd> | następna zakładka |
| <kbd>Spacja</kbd> / <kbd>P</kbd> | graj lub pauzuj zaznaczony utwór |
| <kbd>L</kbd> | pokaż lub schowaj notki |
| <kbd>Esc</kbd> | anuluj bieżącą czynność |
| <kbd>Q</kbd> | zamknij program |

### 5.2. W trakcie grania

| klawisz | działanie |
|---|---|
| <kbd>↓</kbd> / <kbd>↑</kbd> | przełącz odtwarzanie na następny lub poprzedni utwór z listy |
| <kbd>→</kbd> / <kbd>←</kbd> | skok o 8 uderzeń |
| <kbd>Shift</kbd>+<kbd>→</kbd> / <kbd>←</kbd> | skok o 32 uderzenia |
| <kbd>PgUp</kbd> / <kbd>PgDn</kbd> | skok o 128 uderzeń |

Przy pauzie i przy ciszy strzałki tylko poruszają kursorem po liście.
Zamiast <kbd>PgUp</kbd>/<kbd>PgDn</kbd> działa też
<kbd>⌘</kbd>+<kbd>Shift</kbd>+strzałka, o ile Twój terminal przepuszcza ten
skrót.

### 5.3. Biblioteka

| klawisz | działanie |
|---|---|
| <kbd>U</kbd> | przypnij lub odepnij ulubiony (♥) |
| <kbd>F</kbd> | oznacz lub odznacz filar (⚑) |
| <kbd>G</kbd> | wyślij filary do zakładki Set jako szkic |
| <kbd>K</kbd> | włącz lub wyłącz okładki |

### 5.4. Set

| klawisz | działanie |
|---|---|
| <kbd>B</kbd> | zbuduj set z briefu |
| <kbd>Z</kbd> | podmień zaznaczony utwór (dwa naciśnięcia) |
| <kbd>A</kbd> | dopisz utwór za zaznaczonym (dwa naciśnięcia) |
| <kbd>X</kbd> | wytnij zaznaczony utwór |
| <kbd>Shift</kbd>+<kbd>↑</kbd> / <kbd>↓</kbd> | przesuń utwór w kolejności |
| <kbd>C</kbd> | pokaż lub schowaj pasek szwu |
| <kbd>I</kbd> | karta utworu: metadane, plik na dysku, dane z Rekordboxa |
| <kbd>F</kbd> | zmień tryb rozstawienia filarów |
| <kbd>S</kbd> | zapisz plan |
| <kbd>O</kbd> | otwórz listę planów |
| <kbd>W</kbd> | wyślij playlistę do Rekordboxa |
| <kbd>Ctrl</kbd>+<kbd>G</kbd> | lista gatunków |
| <kbd>Ctrl</kbd>+<kbd>D</kbd> | lista DJ-ów do kotwicy |

### 5.5. Eksport / Cue

| klawisz | działanie |
|---|---|
| <kbd>A</kbd>–<kbd>H</kbd> | wybierz pad; na pustym slocie postaw nowy |
| ta sama litera drugi raz | przenieś pad pod głowicę odtwarzacza |
| <kbd>←</kbd> / <kbd>→</kbd> | przesuń pad o 1 uderzenie |
| <kbd>Shift</kbd>+strzałka | przesuń pad o 8 uderzeń |
| <kbd>PgUp</kbd> / <kbd>PgDn</kbd> | przesuń pad o 32 uderzenia |
| <kbd>T</kbd> | wpisz czas pada z klawiatury |
| <kbd>P</kbd> | graj utwór od wybranego pada |
| <kbd>S</kbd> | posłuchaj szwu do następnego utworu |
| <kbd>X</kbd> | zdejmij pad |
| <kbd>Z</kbd> | cofnij ostatnią zmianę |
| <kbd>W</kbd> | wyślij hot cue do Rekordboksa (dwa naciśnięcia) |

**Uwaga:** w tej zakładce litery A–H należą do padów, więc odsłuch szwu
siedzi pod <kbd>S</kbd>, a nie pod <kbd>C</kbd>.

---

## 6. Jak czytać ekran

### 6.1. Kolumny Biblioteki

<!-- zrzut: biblioteka -->

Tabela pokazuje: tempo, tonację, pewność tonacji, energię względną (0–100
w obrębie Twojej biblioteki), głośność LUFS, gatunek, długość oraz wykonawcę
i tytuł w osobnych kolumnach.

Po lewej stronie są stałe sekcje: **Cała biblioteka**, **♥ Ulubione utwory**,
**⚑ Filary**. Nad tabelą jest pole szukania (fragment nazwy pliku, wykonawcy,
tytułu lub gatunku) oraz filtry tonacji (na przykład `8A`) i okna tempa (na
przykład `125-140`). Filtry działają w trakcie pisania.

### 6.2. Sortowanie

Nagłówki kolumn są klikalne. Pierwsze kliknięcie sortuje rosnąco (↓), drugie
malejąco (↑), trzecie wyłącza sortowanie. Utwory bez wartości w sortowanej
kolumnie zawsze lądują na końcu.

### 6.3. Oznaczenia

| oznaczenie | znaczenie |
|---|---|
| pogrubione tempo i tonacja | wyróżnienie dla czytelności, w obu tabelach |
| **RB** w kolumnie pewności | tonacja pochodzi z analizy Rekordboxa |
| przygaszona tonacja z **?** | silnik nie jest jej pewny |
| **…** w kolumnie LUFS | głośność jeszcze nie zmierzona; pomiar idzie w tle |
| złoty wiersz z ⚑ | filar |

Pasek skrótów na dole ekranu pokazuje tylko klawisze aktywnej zakładki.

---

## 7. Czego DanceLab nigdy nie robi

To są gwarancje programu, nie zalecenia.

| gwarancja | znaczenie |
|---|---|
| nie zmyśla liczb | gdy silnik czegoś nie wie, pisze o tym wprost, zamiast pokazać wartość „mniej więcej" |
| nie gra sam z siebie | dźwięk startuje wyłącznie z Twojego klawisza |
| nie nadpisuje Twoich hot cue | pad ustawiony Twoją ręką jest nietykalny |
| nie pisze do otwartego Rekordboksa | przy otwartym programie zapis jest zablokowany |
| nie zapisuje bez kopii | przed każdą zmianą w bazie powstaje kopia, a wynik jest sprawdzany odczytem |
| nie kasuje okładek ani audio | wyłączenie okładek tylko je chowa |
| nie usuwa planów na twardo | <kbd>X</kbd> przenosi plan do kosza obok planów |

---

## 8. Rozwiązywanie problemów

| objaw | przyczyna | co zrobić |
|---|---|---|
| krzywy układ, ucięte kolumny | okno terminala jest za małe | powiększ okno; program sam się przerysuje |
| „command not found" | polecenie uruchomione spoza folderu programu | użyj skrótu z biurka (procedura 1.1) |
| <kbd>W</kbd> odmawia zapisu | Rekordbox jest otwarty | zamknij Rekordboksa i powtórz |
| wysłałem cue, ale nie widzę ich w Rekordboksie | Rekordbox był otwarty w chwili wysyłki | powtórz procedurę 4.10 od kroku 1 |
| wysłałem cue, ale nie widzę ich w Rekordboksie | naciśnięcie było tylko jedno; pierwsze wyłącznie liczy | naciśnij <kbd>W</kbd> ponownie, gdy przycisk pokazuje „POTWIERDŹ" |
| wysłałem cue, ale nie widzę ich w Rekordboksie | Rekordbox był uruchomiony od wcześniej i czyta bazę tylko przy starcie | zamknij Rekordboksa i uruchom ponownie |
| części utworów nie ma w Rekordboksie | utwory spoza kolekcji Rekordboxa są pomijane | sprawdź imienny powód w notkach (<kbd>L</kbd>) |
| budowa setu odmawia | brief nie da się spełnić z bieżącej puli | sprawdź powód w notkach (<kbd>L</kbd>) i w dymku |
| skoki <kbd>→</kbd>/<kbd>←</kbd> nie działają | brak `ffmpeg` | zainstaluj: `brew install ffmpeg` |
| okładki są mozaikowe | terminal bez obsługi grafiki | uruchom program przez skrót z biurka (Ghostty) |
| okładek nie widać w Rekordboksie | Rekordbox nie odczytał tagów ponownie | zaznacz utwory w Rekordboksie i wybierz **Reload Tags** |
