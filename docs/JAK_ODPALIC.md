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

**Jak czytać ten dokument.** Rozdziały idą tak, jak idzie praca i jak idą
zakładki w programie: **Biblioteka → Set → Eksport / Cue**. Każda opcja ma
własny zrzut ekranu, żeby dało się porównać z tym, co widzisz. Czynności
mają zawsze ten sam układ: **cel → warunki wstępne → kroki → wynik**.

---

## Spis treści

1. [Zanim zaczniesz](#1-zanim-zaczniesz)
2. [Słownik pojęć](#2-słownik-pojęć)
3. [Zakładka Biblioteka](#3-zakładka-biblioteka)
4. [Zakładka Set](#4-zakładka-set)
5. [Zakładka Eksport / Cue](#5-zakładka-eksport--cue)
6. [Odtwarzacz](#6-odtwarzacz)
7. [Skróty klawiszowe](#7-skróty-klawiszowe)
8. [Czego DanceLab nigdy nie robi](#8-czego-dancelab-nigdy-nie-robi)
9. [Rozwiązywanie problemów](#9-rozwiązywanie-problemów)

---

## 1. Zanim zaczniesz

### 1.1. Uruchomienie

**Cel:** uruchomić DanceLab.

**Warunki wstępne:** brak.

**Kroki**

1. Kliknij dwukrotnie aplikację **DanceLab** na biurku.
2. Poczekaj, aż pojawi się zakładka **Biblioteka**.

**Wynik:** program działa i wczytuje bibliotekę w tle. Skrót zawsze
uruchamia aktualną wersję.

<!-- zrzut: lib_widok -->

### 1.2. Uruchomienie zapasowe

Użyj tego sposobu, gdy skrót z biurka zginie.

| sposób | co zrobić |
|---|---|
| plik `.command` | Kliknij dwukrotnie **DanceLab.command** w `Developer/dancelab-engine` (kopia leży na biurku). Kliknięty w zwykłym Terminalu sam przenosi się do Ghostty. |
| linia poleceń | Wpisz w terminalu: `cd ~/Developer/dancelab-engine && .venv/bin/dancelab tui` |

**Uwaga:** przy pierwszym uruchomieniu macOS może poprosić o zgodę. Kliknij
plik prawym przyciskiem i wybierz **Otwórz**. Pytanie pojawia się raz.

**Dlaczego akurat Ghostty:** ten terminal wyświetla grafikę, więc okładki są
ostre. W terminalach bez grafiki okładki są mozaikowe — reszta programu
działa tak samo.

### 1.3. Przełączanie zakładek

Zakładki przełączasz klawiszami <kbd>Ctrl</kbd>+<kbd>Tab</kbd> albo
kliknięciem w nazwę. Idą w kolejności pracy:

| zakładka | do czego służy | rozdział |
|---|---|---|
| **Biblioteka** | przeglądanie, szukanie, ulubione, filary, dogrywanie plików | [3](#3-zakładka-biblioteka) |
| **Set** | brief, budowa, poprawki, plany, wysyłka playlisty | [4](#4-zakładka-set) |
| **Eksport / Cue** | hot cue, odsłuch szwów, wysyłka cue | [5](#5-zakładka-eksport--cue) |

Pasek statusu na dole widać zawsze:

| element | znaczenie |
|---|---|
| stan Rekordboxa | „✅ zamknięty — W dostępne" albo „⛔ OTWARTY — zapis W zablokowany" |
| backupy | ile kopii bazy Rekordboxa leży na dysku |
| notki | licznik wpisów silnika; <kbd>L</kbd> pokazuje pełną listę |
| pula | katalog z przeanalizowanymi utworami |

---

## 2. Słownik pojęć

Nazwy z tej tabeli są używane w całym dokumencie i w programie konsekwentnie
— jedno pojęcie ma jedną nazwę.

| pojęcie | znaczenie |
|---|---|
| **silnik** | część DanceLab, która analizuje utwory i układa kolejność |
| **brief** | formularz po lewej w zakładce Set: długość, okno tempa, gatunki, kotwica, świeżość. Twoje zamówienie na set |
| **set** | ułożona kolejność utworów w tabeli |
| **filar** | utwór oznaczony w Bibliotece jako obowiązkowy: musi zagrać w budowanym secie. Filarów jest od 3 do 10 |
| **kotwica** | brzmienie „graj jak…": wybrany DJ, do którego silnik zbliża dobór utworów |
| **szew** | przejście między dwoma sąsiednimi utworami setu |
| **pad** | jedno z ośmiu miejsc A–H, w których leży hot cue — jak pady na CDJ |
| **hot cue** | punkt startowy zapisany na padzie; to on trafia do Rekordboksa |
| **plan** | zapisany na dysku stan setu, z nazwą. Można do niego wrócić po zamknięciu programu |
| **werdykt** | zapis Twojej decyzji (cięcie, podmiana, przesunięcie). Z tych zapisów silnik będzie uczył się Twojego gustu |
| **notki** | dziennik silnika: czego nie wie, co odrzucił i dlaczego (klawisz <kbd>L</kbd>) |
| **LUFS** | zmierzona głośność utworu. Im bliżej zera, tym głośniej |
| **seed** | liczba sterująca losowością świeżości. Ten sam seed powtarza identyczny set |

---

## 3. Zakładka Biblioteka

### 3.1. Co widać na ekranie

<!-- zrzut: lib_widok -->

| obszar | zawartość |
|---|---|
| kolumna po lewej | stałe sekcje: **Cała biblioteka**, **♥ Ulubione utwory**, **⚑ Filary** |
| góra | pole szukania oraz filtry: tonacja i okno tempa |
| środek | tabela utworów |
| dół | wiersz **Analizuj**, odtwarzacz i pasek statusu |

Kolumny tabeli: tempo, tonacja, pewność tonacji, energia względna (0–100
w obrębie Twojej biblioteki), głośność LUFS, gatunek, długość, wykonawca,
tytuł.

| oznaczenie w tabeli | znaczenie |
|---|---|
| pogrubione tempo i tonacja | wyróżnienie dla czytelności |
| **RB** w kolumnie pewności | tonacja pochodzi z analizy Rekordboxa |
| przygaszona tonacja z **?** | silnik nie jest jej pewny |
| **…** w kolumnie LUFS | głośność jeszcze nie zmierzona; pomiar idzie w tle |

### 3.2. Znajdź utwór

**Cel:** zawęzić listę do interesujących utworów.

**Warunki wstępne:** biblioteka jest przeanalizowana.

**Kroki**

1. Kliknij pole szukania na górze i wpisz fragment nazwy pliku, wykonawcy,
   tytułu lub gatunku.
2. Opcjonalnie wpisz tonację w pole obok (na przykład `8A`).
3. Opcjonalnie wpisz okno tempa (na przykład `128-140`).

**Wynik:** lista zawęża się w trakcie pisania; licznik nad tabelą pokazuje,
ile utworów zostało.

<!-- zrzut: lib_szukanie -->

### 3.3. Posortuj listę

**Cel:** ustawić kolejność według wybranej kolumny.

**Warunki wstępne:** brak.

**Kroki**

1. Kliknij nagłówek kolumny — sortowanie rosnące (↓).
2. Kliknij ponownie — sortowanie malejące (↑).
3. Kliknij trzeci raz — sortowanie wyłączone.

**Wynik:** tabela jest posortowana. Utwory bez wartości w sortowanej
kolumnie zawsze lądują na końcu.

<!-- zrzut: lib_sortowanie -->

### 3.4. Oznacz ulubiony i filar

**Cel:** przypiąć utwór do ulubionych albo wyznaczyć go jako obowiązkowy
w następnym secie.

**Warunki wstępne:** kursor stoi na utworze.

**Kroki**

1. Naciśnij <kbd>U</kbd>, żeby przypiąć lub odpiąć **ulubiony (♥)**.
2. Naciśnij <kbd>F</kbd>, żeby oznaczyć lub odznaczyć **filar (⚑)**.

**Wynik:** znaki pojawiają się w pierwszych kolumnach, a utwory trafiają do
sekcji **♥ Ulubione utwory** i **⚑ Filary** po lewej stronie.

<!-- zrzut: lib_oznaczenia -->

### 3.5. Włącz okładki

**Cel:** zobaczyć miniatury okładek i uzupełnić brakujące.

**Warunki wstępne:** brak.

**Kroki**

1. Naciśnij <kbd>K</kbd> albo kliknij przełącznik **okładki** pod polem
   szukania.

**Wynik:** lista pokazuje miniatury (wiersze rosną, więc widać mniej utworów
naraz), a w tle rusza dociąganie braków: program znajduje pliki bez
osadzonej okładki, pyta iTunes o wykonawcę i tytuł i przy pewnym dopasowaniu
wpisuje okładkę 600×600 do tagów pliku. Trafienia niejednoznaczne są
pomijane z powodem.

<!-- zrzut: lib_okladki -->

**Uwaga:** wyłączenie przełącznika tylko **chowa** okładki. Nic nie jest
kasowane, a okładki osadzone w plikach zostają tam na zawsze. Audio
pozostaje nietknięte.

**Ważne:** żeby okładki weszły do Rekordboxa i na ekrany CDJ, zaznacz utwory
w Rekordboksie i wybierz **Reload Tags**.

### 3.6. Dograj nowe utwory

**Cel:** dodać pliki z dysku do puli, z której budowane są sety.

**Warunki wstępne:** pliki leżą w jednym folderze.

**Kroki**

1. Wklej ścieżkę folderu w pole **Analizuj** na dole ekranu.
2. Kliknij przycisk obok pola.

**Wynik:** utwory trafiają do puli. Pliki uszkodzone odpadają z imiennym
powodem w notkach, zamiast psuć analizę.

<!-- zrzut: lib_analizuj -->

### 3.7. Zajrzyj do notek

**Cel:** sprawdzić, czego silnik nie wie i co odrzucił.

**Warunki wstępne:** brak.

**Kroki**

1. Naciśnij <kbd>L</kbd>.
2. Naciśnij <kbd>L</kbd> ponownie, żeby schować listę.

**Wynik:** widać dziennik silnika. Licznik notek jest zawsze w pasku
statusu, a odmowy i wyniki wysyłki wyskakują dodatkowo jako dymek.

<!-- zrzut: lib_notki -->

### 3.8. Wyślij filary do zakładki Set

**Cel:** zacząć budowę setu od utworów, które muszą zagrać.

**Warunki wstępne:** oznaczonych jest od 3 do 10 filarów (punkt 3.4).

**Kroki**

1. Naciśnij <kbd>G</kbd>.

**Wynik:** filary trafiają do zakładki Set jako złote wiersze z flagą ⚑,
a program pyta o tryb rozstawienia (punkt 4.4).

---

## 4. Zakładka Set

### 4.1. Co widać na ekranie

<!-- zrzut: set_brief -->

| obszar | zawartość |
|---|---|
| kolumna po lewej | **brief**: pula, długość, okno tempa, gatunki, kotwica, świeżość; na dole przypięty przycisk **Buduj set** |
| środek | tabela setu, nad nią wiersz postępu, pod nią odtwarzacz i notki |
| prawa strona | panel, który wysuwa się po naciśnięciu klawisza (gatunki, kotwica, propozycje, plany, karta utworu) |

Przycisk **Buduj set** jest przypięty do dołu kolumny — pola briefu przewijają
się pod nim, więc nie trzeba go szukać.

### 4.2. Wybierz gatunki

**Cel:** ograniczyć dobór utworów do wybranych gatunków.

**Warunki wstępne:** biblioteka jest wczytana.

**Kroki**

1. Naciśnij <kbd>Ctrl</kbd>+<kbd>G</kbd>, żeby otworzyć listę.
2. Strzałkami <kbd>↑</kbd>/<kbd>↓</kbd> stań na gatunku.
3. Naciśnij <kbd>Enter</kbd> — gatunek zostaje dodany, a przy jego nazwie
   pojawia się ✓. Ponowny <kbd>Enter</kbd> na tym samym gatunku go zdejmuje.
4. Powtórz kroki 2–3 dla kolejnych gatunków — lista zostaje otwarta.
5. Naciśnij <kbd>Ctrl</kbd>+<kbd>G</kbd> albo <kbd>Esc</kbd>, żeby zamknąć
   listę.

**Wynik:** wybrane gatunki wpisują się do pola **Gatunki** w briefie, a na
liście widać przy nich ✓.

<!-- zrzut: set_gatunki -->

Lista pokazuje **tylko te gatunki, które faktycznie masz w bibliotece**,
w nazewnictwie Beatportu, z liczbą utworów przy każdym. Nagłówek mówi, ile
z 46 gatunków Beatportu występuje u Ciebie. Tagi spoza tej taksonomii są
w osobnej sekcji **poza taksonomią** na końcu listy — nic nie ginie.

### 4.3. Wybierz kotwicę „graj jak…"

**Cel:** zbliżyć dobór utworów do brzmienia wybranego DJ-a.

**Warunki wstępne:** brak.

**Kroki**

1. Naciśnij <kbd>Ctrl</kbd>+<kbd>D</kbd>, żeby otworzyć listę.
2. Strzałkami <kbd>↑</kbd>/<kbd>↓</kbd> stań na DJ-u.
3. Naciśnij <kbd>Enter</kbd>.

**Wynik:** kotwica wpisuje się w pole **Graj jak…**, a lista sama się
zamyka — kotwica jest jedna, więc nie ma czego dobierać.

**Uwaga:** <kbd>Ctrl</kbd>+<kbd>D</kbd> albo <kbd>Esc</kbd> zamyka listę bez
wybierania.

<!-- zrzut: set_djs -->

DJ-e są pogrupowani w **rodziny brzmieniowe** policzone z nagrań, a nie
z gatunków przypisanych ręcznie. Przy każdym nazwisku jest krótki opis
brzmienia i liczba przeanalizowanych setów.

### 4.4. Ustaw tryb rozstawienia filarów

**Cel:** zdecydować, gdzie w secie mają wylądować filary.

**Warunki wstępne:** filary są wysłane do zakładki Set (punkt 3.8).

**Kroki**

1. Naciśnij <kbd>F</kbd>.
2. Wskaż tryb na liście.

**Wynik:** tryb jest ustawiony i widać go w notce. Można go zmienić
w każdej chwili kolejnym naciśnięciem <kbd>F</kbd>.

<!-- zrzut: set_filary_tryb -->

| tryb | co robi |
|---|---|
| **Podpory** | silnik buduje set bez filarów, mierzy każde przejście i wstawia filary w najsłabsze miejsca |
| **Równy rozstaw** | filary rozłożone równomiernie po całym secie |
| **Rama** | najwolniejszy filar otwiera set, najszybszy zamyka |

### 4.5. Zbuduj set

**Cel:** dostać ułożoną kolejność utworów.

**Warunki wstępne:** brief jest wypełniony (co najmniej długość).

**Kroki**

1. Wypełnij **Długość** w minutach.
2. Opcjonalnie wypełnij **Okno tempa** (na przykład `130-135`), gatunki
   (punkt 4.2) i kotwicę (punkt 4.3).
3. Ustaw **Świeżość** (tabela niżej).
4. Naciśnij <kbd>B</kbd> albo kliknij **Buduj set**.

**Wynik:** tabela pokazuje gotowy set; postęp budowy widać na żywo.

<!-- zrzut: set_lista -->

| świeżość | co robi |
|---|---|
| **deterministyczny** (domyślnie) | ten sam brief daje zawsze ten sam set |
| **zachowawczy → odkrywczy** | silnik coraz mocniej omija utwory i przejścia z setów już użytych |

„Użyty" znaczy: zapisany (<kbd>S</kbd>) albo wysłany (<kbd>W</kbd>). Samo
naciskanie <kbd>B</kbd> nie liczy się jako granie. Przy trybach świeżości
program losuje **seed** i pokazuje go nad tabelą; wpisanie tego samego seeda
w brief powtarza set co do utworu.

### 4.6. Podmień utwór

**Cel:** zastąpić utwór innym, lepiej pasującym w tym miejscu setu.

**Warunki wstępne:** set jest zbudowany, kursor stoi na utworze.

**Kroki**

1. Naciśnij <kbd>Z</kbd>.
2. Kliknij propozycję na liście po prawej.
3. Naciśnij <kbd>Z</kbd> ponownie.

**Wynik:** utwór jest podmieniony, a zmiana zapisuje się jako werdykt.

<!-- zrzut: set_podmiana -->

Panel pokazuje 10 utworów ocenionych **w tym konkretnym miejscu setu**.
Tryb oceny wybierasz u góry panelu: **smart** (pełna ocena z kotwicą),
**BPM najpierw** albo **tonacja najpierw**.

### 4.7. Dopisz, wytnij, przesuń utwór

**Cel:** poprawić skład i kolejność setu.

**Warunki wstępne:** set jest zbudowany, kursor stoi na utworze.

**Kroki**

1. Wykonaj jedną z czynności z tabeli niżej.

**Wynik:** set jest zmieniony, a każda zmiana zapisuje się jako werdykt.

| czynność | klawisze | uwagi |
|---|---|---|
| dopisz utwór **za** zaznaczonym | <kbd>A</kbd>, kliknij propozycję, <kbd>A</kbd> | ten sam panel propozycji co przy podmianie (punkt 4.6) |
| wytnij zaznaczony utwór | <kbd>X</kbd> | wycięcie filaru zdejmuje też jego oznaczenie |
| przesuń utwór w kolejności | <kbd>Shift</kbd>+<kbd>↑</kbd> / <kbd>Shift</kbd>+<kbd>↓</kbd> | — |

<!-- zrzut: set_dopisz -->

### 4.8. Sprawdź szew między utworami

**Cel:** zobaczyć fakty o przejściu z zaznaczonego utworu w następny.

**Warunki wstępne:** set jest zbudowany, kursor stoi na utworze.

**Kroki**

1. Naciśnij <kbd>C</kbd>.
2. Odczytaj pasek nad tabelą.
3. Naciśnij <kbd>C</kbd> albo <kbd>Esc</kbd>, żeby schować pasek.

**Wynik:** pasek pokazuje liczbę uderzeń, tempo oraz miejsce wyjścia
i wejścia.

<!-- zrzut: set_szew -->

**Uwaga:** pasek sam nic nie gra. Szwu **słucha się** w zakładce Eksport /
Cue (punkt 5.6), ponieważ tam powstaje on z Twoich padów — czyli z tego, co
naprawdę pojedzie na CDJ-e.

### 4.9. Sprawdź, co program wie o utworze

**Cel:** zobaczyć metadane, położenie pliku i dane z Rekordboksa.

**Warunki wstępne:** kursor stoi na utworze.

**Kroki**

1. Naciśnij <kbd>I</kbd>.
2. Naciśnij <kbd>I</kbd> albo <kbd>Esc</kbd>, żeby zamknąć kartę.

**Wynik:** karta pokazuje metadane silnika, ścieżkę pliku na dysku oraz to,
co wie Rekordbox: jego tonację i tempo, komentarz i playlisty, w których
utwór leży.

<!-- zrzut: set_info -->

### 4.10. Zapisz plan

**Cel:** zachować set na później.

**Warunki wstępne:** set jest zbudowany.

**Kroki**

1. Naciśnij <kbd>S</kbd>.
2. Wpisz nazwę w oknie, które się pojawi.
3. Naciśnij <kbd>Enter</kbd> albo kliknij **Zapisz**.

**Wynik:** plan zawiera kolejność, brief i historię edycji. <kbd>Esc</kbd>
albo **Anuluj** wychodzi bez zapisu.

<!-- zrzut: set_nazwa_planu -->

### 4.11. Wczytaj zapisany plan

**Cel:** wrócić do wcześniej zapisanego setu.

**Warunki wstępne:** istnieje co najmniej jeden zapisany plan.

**Kroki**

1. Naciśnij <kbd>O</kbd>.
2. Kliknij plan na liście.
3. Naciśnij <kbd>O</kbd> ponownie.

**Wynik:** set wraca w całości — działa także po ponownym uruchomieniu
programu. Utwory, których nie ma już w puli, są pomijane z wyraźną notką.

<!-- zrzut: set_plany -->

Lista pokazuje przy każdym planie: nazwę, liczbę utworów, okno tempa,
kotwicę i datę. <kbd>X</kbd> usuwa plan **miękko** — do kosza obok planów.

### 4.12. Wyślij playlistę do Rekordboksa

**Cel:** utworzyć w Rekordboksie playlistę z bieżącego setu.

**Warunki wstępne:** set jest zbudowany, **Rekordbox jest zamknięty**.

**Kroki**

1. Naciśnij <kbd>W</kbd>.

**Wynik:** playlista jest w bazie Rekordboxa. W tej samej chwili zapisuje
się werdykt końcowy — porównanie tego, co ułożył silnik, z tym, co
zostawiłeś. Nie ma osobnego klawisza do zapamiętania werdyktu.

**Uwaga:** przy otwartym Rekordboksie program odmawia i niczego nie dotyka.
Przed każdym zapisem sam robi kopię bazy, a po zapisie sprawdza odczytem,
czy w bazie jest dokładnie to, co miało być.

---

## 5. Zakładka Eksport / Cue

### 5.1. Co widać na ekranie

<!-- zrzut: cue_widok -->

| obszar | zawartość |
|---|---|
| karta u góry | wybrany utwór: po lewej oś energii, sekcje, pady na osi i podziałka czasu; po prawej siatka padów 2×4 jak na CDJ |
| wiersz podpowiedzi | wszystkie klawisze edytora, zawsze widoczne |
| lista pośrodku | jeden wiersz = jeden utwór setu: oś energii z literami padów, liczba padów, pewność |
| dół | odtwarzacz, a pod nim przyciski **Wyślij cue do RB** i **Wyślij playlistę do RB** |

Siatka padów: A B C D w górnym rzędzie, E F G H w dolnym. Zajęty pad
pokazuje czas i znak stanu, pusty — przygaszoną kreskę.

| znak | znaczenie |
|---|---|
| ✓ | pozycja pewna |
| ? | posłuchaj przed graniem |
| ✋ | pad ustawiony Twoją ręką |

Dla każdego przejścia silnik proponuje pad z wyjściem z utworu i pad
z wejściem w następny, przyciągnięte do siatki bitów.

### 5.2. Wybierz pad i postaw nowy

**Cel:** wskazać pad do edycji albo utworzyć nowy.

**Warunki wstępne:** kursor stoi na utworze listy.

**Kroki**

1. Naciśnij literę <kbd>A</kbd>–<kbd>H</kbd>.

**Wynik:** jeśli pad istnieje — jest wybrany, a pod siatką pojawiają się
jego szczegóły. Jeśli slot był pusty — powstaje nowy pad: w miejscu, gdzie
stoi odtwarzacz (gdy ten utwór gra) albo na środku utworu.

<!-- zrzut: cue_pad -->

**Uwaga:** <kbd>Esc</kbd> odznacza pad, <kbd>X</kbd> go zdejmuje,
a <kbd>Z</kbd> cofa każdą zmianę o jeden krok.

### 5.3. Przestaw pad — duży skok

**Cel:** przenieść pad w zupełnie inne miejsce utworu.

**Warunki wstępne:** pad jest wybrany, odtwarzacz stoi na tym samym utworze.

**Kroki**

1. Naciśnij <kbd>P</kbd>, żeby puścić utwór.
2. Strzałkami dojedź do miejsca, w którym pad ma stanąć.
3. Naciśnij **tę samą literę drugi raz**.

**Wynik:** pad stoi pod głowicą odtwarzacza, dociągnięty do najbliższego
bitu. Program odmawia z powodem, jeżeli odtwarzacz stoi na innym utworze.

### 5.4. Przestaw pad — drobna poprawka

**Cel:** przesunąć pad o dokładną liczbę uderzeń.

**Warunki wstępne:** pad jest wybrany.

**Kroki**

1. Naciśnij <kbd>←</kbd> lub <kbd>→</kbd> — przesunięcie o 1 uderzenie.
2. Z <kbd>Shift</kbd> — o 8 uderzeń.
3. <kbd>PgUp</kbd> / <kbd>PgDn</kbd> — o 32 uderzenia.

**Wynik:** pad jest przesunięty. Propozycja silnika zostaje widoczna jako
kropka, a pad jest opisany jako ustawiony ręką — zawsze widzisz, o ile
różnisz się od silnika.

<!-- zrzut: cue_przesuniety -->

### 5.5. Wpisz czas pada z klawiatury

**Cel:** ustawić pad na konkretnym czasie albo na początku frazy.

**Warunki wstępne:** pad jest wybrany.

**Kroki**

1. Naciśnij <kbd>T</kbd>. Czas w kratce pada zamienia się w pole do pisania.
2. Wykonaj jedną z czynności:
   - wpisz czas w formacie `2:31` albo `2:31.5` (przecinek działa jak
     kropka);
   - wybierz gotowy czas frazy z listy pod siatką klawiszami
     <kbd>↑</kbd>/<kbd>↓</kbd>.
3. Naciśnij <kbd>Enter</kbd>.

**Wynik:** pad stoi na wpisanym czasie, dociągniętym do siatki tak, jak przy
włączonym quantize w Rekordboksie: do taktu, gdy faza taktu jest
zweryfikowana, w przeciwnym razie do najbliższego bitu. Notka mówi, o ile
program dociągnął.

<!-- zrzut: cue_czas -->

**Uwaga:** lista gotowych czasów zawiera początki sekcji utworu (intro,
break, groove, outro) oraz propozycję silnika. Lista **przewija się** —
licznik (na przykład `5/12`) i strzałki „↑ 4 wyżej / ↓ 3 niżej" mówią, ile
pozycji jest poza kadrem. <kbd>Esc</kbd> wychodzi bez zmiany. Przy niepewnej
siatce program zostawia dokładnie wpisany czas i pisze dlaczego.

### 5.6. Posłuchaj szwu do następnego utworu

**Cel:** sprawdzić uchem przejście złożone z Twoich padów.

**Warunki wstępne:** zainstalowany `ffmpeg`; utwór ma następnika w secie.

**Kroki**

1. Ustaw kursor na utworze.
2. Naciśnij <kbd>S</kbd>.

**Wynik:** słyszysz wyjście z tego utworu złożone z wejściem w następny —
**dokładnie z padów, które masz na ekranie**, a nie z propozycji silnika.
Program wypisuje, których padów użył.

**Uwaga:** bez zaznaczonego pada szew idzie z ostatniego wyjścia w pierwsze
wejście następnego utworu; z zaznaczonym padem wychodzi właśnie z niego.
Ostatni utwór setu nie ma następnika i program mówi to wprost. Klawiszem
odsłuchu jest <kbd>S</kbd>, a nie <kbd>C</kbd>, ponieważ litery A–H należą
do padów. Ten punkt jako jedyny nie ma zrzutu ekranu: zrzut wymagałby
uruchomienia dźwięku, a dźwięk startuje wyłącznie z Twojego klawisza.

### 5.7. Wyślij hot cue do Rekordboksa

**Cel:** przenieść pady z ekranu na pady w Rekordboksie.

**Warunki wstępne:** set jest zbudowany, utwory są w kolekcji Rekordboxa.

**Ostrzeżenie:** kolejność kroków jest obowiązkowa. Pominięcie któregokolwiek
kończy się tym, że w Rekordboksie nie widać żadnych zmian.

**Kroki**

1. **Zamknij Rekordboksa.**
2. Naciśnij <kbd>W</kbd> albo kliknij przycisk. Program liczy plan
   i pokazuje, ile padów wejdzie, ile ustąpiło Twoim własnym cue i czy
   któryś utwór jest spoza kolekcji.
3. Naciśnij <kbd>W</kbd> ponownie, gdy przycisk pokazuje **POTWIERDŹ**.
4. **Uruchom Rekordboksa.**

**Wynik:** pady są na miejscu. Program potwierdza liczbę zapisanych padów
i ścieżkę kopii bazy.

<!-- zrzut: cue_potwierdz -->

Przycisk zawsze mówi, w jakim jest stanie:

| stan | wygląd przycisku |
|---|---|
| Rekordbox otwarty | wyszarzony, napis **Zamknij Rekordbox, by wysłać cue** |
| gotowy do liczenia | **Wyślij cue do RB [W]** |
| plan policzony | pomarańczowy, **POTWIERDŹ zapis N padów [W]** |

<!-- zrzut: cue_rb_otwarty -->

**Dlaczego tak:**

- Rekordbox musi być zamknięty, ponieważ zapis do jego bazy w trakcie pracy
  programu uszkodziłby ją.
- Rekordbox czyta bazę przy uruchomieniu, więc program otwarty od wcześniej
  pokaże stare pady.
- Przed zapisem powstaje kopia bazy, a po zapisie program sprawdza odczytem,
  czy pady naprawdę są. Jeśli nie — zmiana jest wycofywana.
- Padów, które ustawiłeś sam, program nigdy nie nadpisuje; ustępuje im i mówi
  o tym w podsumowaniu. Własne pady z poprzedniej wysyłki natomiast
  **odświeża**, żeby przesunięty pad dojechał do Rekordboksa. Rozpoznaje je
  po własnym rejestrze; cokolwiek w tym rejestrze nie leży, uchodzi za Twoje
  i zostaje nietknięte.

### 5.8. Wyślij playlistę z tej zakładki

**Cel:** utworzyć playlistę bez wracania do zakładki Set.

**Warunki wstępne:** jak w punkcie 4.12.

**Kroki**

1. Kliknij **Wyślij playlistę do RB** w prawym dolnym rogu.

**Wynik:** to samo, co <kbd>W</kbd> w zakładce Set (punkt 4.12).

---

## 6. Odtwarzacz

Odtwarzacz jest **przypięty do dolnej krawędzi w każdej zakładce** i jest
jeden wspólny: utwór puszczony w Bibliotece gra dalej po przejściu do Setu
i do Eksportu.

Pasek zawiera, od lewej: przyciski **Poprz. · −8 · Graj · +8 · Nast.**,
okładkę, tytuł z wykonawcą, oś czasu z głowicą ▮ w bieżącym miejscu oraz
zegar „teraz / całość". Przyciski robią dokładnie to samo, co klawisze.
Utwór bez policzonej analizy pokazuje sam zegar, bez kształtu energii.

### 6.1. Posłuchaj utworu

**Cel:** sprawdzić utwór uchem.

**Warunki wstępne:** zainstalowany `ffmpeg` (`brew install ffmpeg`).

**Kroki**

1. Ustaw kursor na utworze.
2. Naciśnij <kbd>Spacja</kbd> albo <kbd>P</kbd>.

**Wynik:** utwór gra, a oś czasu pokazuje pozycję. Kolejne naciśnięcie
pauzuje, następne wznawia od miejsca pauzy.

### 6.2. Sterowanie w trakcie grania

| klawisz | działanie |
|---|---|
| <kbd>↓</kbd> / <kbd>↑</kbd> | przełącz odtwarzanie na następny lub poprzedni utwór z listy |
| <kbd>→</kbd> / <kbd>←</kbd> | skok o 8 uderzeń |
| <kbd>Shift</kbd>+<kbd>→</kbd> / <kbd>←</kbd> | skok o 32 uderzenia |
| <kbd>PgUp</kbd> / <kbd>PgDn</kbd> | skok o 128 uderzeń |

Przy pauzie i przy ciszy strzałki tylko poruszają kursorem po liście.
Zamiast <kbd>PgUp</kbd>/<kbd>PgDn</kbd> działa też
<kbd>⌘</kbd>+<kbd>Shift</kbd>+strzałka, o ile terminal przepuszcza ten skrót.
Gdy utwór skończy się sam, gra następny z listy; na końcu listy zapada cisza.

---

## 7. Skróty klawiszowe

### 7.1. Wszędzie

| klawisz | działanie |
|---|---|
| <kbd>Ctrl</kbd>+<kbd>Tab</kbd> | następna zakładka |
| <kbd>Spacja</kbd> / <kbd>P</kbd> | graj lub pauzuj zaznaczony utwór |
| <kbd>L</kbd> | pokaż lub schowaj notki |
| <kbd>Esc</kbd> | anuluj bieżącą czynność |
| <kbd>Q</kbd> | zamknij program |

### 7.2. Biblioteka

| klawisz | działanie | punkt |
|---|---|---|
| <kbd>U</kbd> | ulubiony (♥) | 3.4 |
| <kbd>F</kbd> | filar (⚑) | 3.4 |
| <kbd>K</kbd> | okładki | 3.5 |
| <kbd>G</kbd> | wyślij filary do zakładki Set | 3.8 |

### 7.3. Set

| klawisz | działanie | punkt |
|---|---|---|
| <kbd>Ctrl</kbd>+<kbd>G</kbd> | otwórz lub zamknij listę gatunków | 4.2 |
| <kbd>Ctrl</kbd>+<kbd>D</kbd> | otwórz lub zamknij listę DJ-ów | 4.3 |
| <kbd>Enter</kbd> | w otwartej liście: dodaj gatunek / wybierz kotwicę | 4.2, 4.3 |
| <kbd>F</kbd> | tryb rozstawienia filarów | 4.4 |
| <kbd>B</kbd> | zbuduj set | 4.5 |
| <kbd>Z</kbd> | podmień utwór (dwa naciśnięcia) | 4.6 |
| <kbd>A</kbd> | dopisz utwór (dwa naciśnięcia) | 4.7 |
| <kbd>X</kbd> | wytnij utwór | 4.7 |
| <kbd>Shift</kbd>+<kbd>↑</kbd> / <kbd>↓</kbd> | przesuń utwór | 4.7 |
| <kbd>C</kbd> | pasek szwu | 4.8 |
| <kbd>I</kbd> | karta utworu | 4.9 |
| <kbd>S</kbd> | zapisz plan | 4.10 |
| <kbd>O</kbd> | wczytaj plan | 4.11 |
| <kbd>W</kbd> | wyślij playlistę | 4.12 |

### 7.4. Eksport / Cue

| klawisz | działanie | punkt |
|---|---|---|
| <kbd>A</kbd>–<kbd>H</kbd> | wybierz pad; na pustym slocie postaw nowy | 5.2 |
| ta sama litera drugi raz | przenieś pad pod głowicę odtwarzacza | 5.3 |
| <kbd>←</kbd> / <kbd>→</kbd> | przesuń pad o 1 uderzenie | 5.4 |
| <kbd>Shift</kbd>+strzałka | przesuń pad o 8 uderzeń | 5.4 |
| <kbd>PgUp</kbd> / <kbd>PgDn</kbd> | przesuń pad o 32 uderzenia | 5.4 |
| <kbd>T</kbd> | wpisz czas pada z klawiatury | 5.5 |
| <kbd>P</kbd> | graj utwór od wybranego pada | 5.2 |
| <kbd>S</kbd> | posłuchaj szwu do następnego utworu | 5.6 |
| <kbd>X</kbd> | zdejmij pad | 5.2 |
| <kbd>Z</kbd> | cofnij ostatnią zmianę | 5.2 |
| <kbd>W</kbd> | wyślij hot cue (dwa naciśnięcia) | 5.7 |

---

## 8. Czego DanceLab nigdy nie robi

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

## 9. Rozwiązywanie problemów

| objaw | przyczyna | co zrobić |
|---|---|---|
| krzywy układ, ucięte kolumny | okno terminala jest za małe | powiększ okno; program sam się przerysuje |
| „command not found" | polecenie uruchomione spoza folderu programu | użyj skrótu z biurka (punkt 1.1) |
| <kbd>W</kbd> odmawia zapisu | Rekordbox jest otwarty | zamknij Rekordboksa i powtórz |
| wysłałem cue, ale nie widzę ich w Rekordboksie | Rekordbox był otwarty w chwili wysyłki | powtórz punkt 5.7 od kroku 1 |
| wysłałem cue, ale nie widzę ich w Rekordboksie | naciśnięcie było tylko jedno; pierwsze wyłącznie liczy | naciśnij <kbd>W</kbd> ponownie, gdy przycisk pokazuje „POTWIERDŹ" |
| wysłałem cue, ale nie widzę ich w Rekordboksie | Rekordbox był uruchomiony od wcześniej i czyta bazę tylko przy starcie | zamknij Rekordboksa i uruchom ponownie |
| części utworów nie ma w Rekordboksie | utwory spoza kolekcji Rekordboxa są pomijane | sprawdź imienny powód w notkach (<kbd>L</kbd>) |
| budowa setu odmawia | brief nie da się spełnić z bieżącej puli | sprawdź powód w notkach (<kbd>L</kbd>) i w dymku |
| skoki <kbd>→</kbd>/<kbd>←</kbd> nie działają | brak `ffmpeg` | zainstaluj: `brew install ffmpeg` |
| okładki są mozaikowe | terminal bez obsługi grafiki | uruchom program przez skrót z biurka (Ghostty) |
| okładek nie widać w Rekordboksie | Rekordbox nie odczytał tagów ponownie | zaznacz utwory w Rekordboksie i wybierz **Reload Tags** |
