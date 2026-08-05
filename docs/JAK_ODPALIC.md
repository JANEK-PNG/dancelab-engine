# DanceLab — instrukcja użytkownika

Wersja z 2026-08-06. Dla DJ-a, bez wiedzy technicznej.
DanceLab buduje sety z Twojej biblioteki: analizuje utwory, układa
kolejność wokół Twoich decyzji i oddaje gotową playlistę do Rekordboxa.

---

## 1. Uruchamianie

**Sposób podstawowy:** na biurku leży aplikacja **DanceLab** — kliknij ją
dwa razy. Otworzy się okno terminala **Ghostty** (terminal z obsługą
grafiki: okładki są w nim OSTRE, nie mozaikowe) i wstanie aplikacja.
Skrót zawsze uruchamia aktualną wersję.

Zapasowo: plik **DanceLab.command** w `Developer/dancelab-engine` otwiera
aplikację w zwykłym Terminalu (okładki jako mozaika).

**Sposób ręczny** (gdyby skrót zginął):

```bash
cd ~/Developer/dancelab-engine && .venv/bin/dancelab tui
```

Przy pierwszym uruchomieniu macOS może dopytać — kliknij plik prawym
przyciskiem i wybierz **Otwórz**; więcej nie zapyta.

---

## 2. Pojęcia

| pojęcie | znaczenie |
|---|---|
| **brief** | formularz po lewej w zakładce Set: długość, okno tempa, gatunki, kotwica, świeżość — Twoje zamówienie na set |
| **set** | ułożona przez silnik kolejność utworów w tabeli |
| **filar** | utwór oznaczony w Bibliotece jako obowiązkowy: MUSI zagrać w budowanym secie; filarów jest od 3 do 10 |
| **kotwica** | brzmienie „graj jak…" — wybrany DJ, do którego silnik zbliża dobór utworów |
| **szew** | przejście między dwoma sąsiednimi utworami setu |
| **pasek szwu** | panel nad tabelą (klawisz C) z faktami o szwie i odtwarzaniem pary |
| **plan** | zapisany na dysku stan setu, z nazwą — można do niego wrócić po zamknięciu aplikacji |
| **werdykt** | zapis Twojej decyzji (cięcie, podmiana, przesunięcie) — z tych zapisów silnik będzie uczył się Twojego gustu |
| **notki** | dziennik silnika: czego nie wie, co odrzucił i dlaczego (klawisz L) |
| **LUFS** | zmierzona głośność utworu; im bliżej zera, tym głośniej |
| **seed** | liczba sterująca losowością świeżości: ten sam seed powtarza identyczny set |

---

## 3. Zakładki

Aplikacja ma trzy zakładki — przełączasz je klawiszami **Ctrl+Tab** albo
kliknięciem w nazwę:

1. **Biblioteka** — wszystkie przeanalizowane utwory: przeglądanie,
   szukanie, odsłuch, ulubione i filary.
2. **Set** — brief, budowa setu, edycja i wysyłka do Rekordboxa.
3. **Eksport / Cue** — w budowie (edytor hot cue).

---

## 4. Biblioteka

### Co widzisz
Po lewej stałe **sekcje**: Cała biblioteka, ♥ Ulubione utwory, ⚑ Filary.
Na górze **szukajka** (fragment nazwy, wykonawcy, tytułu lub gatunku)
oraz **filtry**: tonacja (np. `8A`) i okno tempa (np. `125-140`) —
działają w trakcie pisania.

Tabela pokazuje wszystko, co silnik wie o utworze: tempo, tonację,
pewność tonacji, energię względną (0–100 w obrębie Twojej biblioteki),
głośność LUFS, gatunek, długość oraz wykonawcę i tytuł w osobnych
kolumnach.

### Sortowanie
Nagłówki kolumn to klikalne kafelki. Pierwsze kliknięcie sortuje rosnąco
(strzałka ↓ w nagłówku), drugie malejąco (↑), trzecie wyłącza sortowanie.
Utwory bez wartości w sortowanej kolumnie zawsze lądują na końcu.

### Co możesz zrobić
| klawisz | działanie |
|---|---|
| **U** | przypnij / odepnij ulubiony (♥) |
| **K** | okładki w liście: włącz / wyłącz (galeria z miniaturami — wiersze rosną, widać mniej utworów naraz; wybór zapamiętany) |
| **F** | oznacz / odznacz utwór jako filar |
| **G** | wyślij filary do zakładki Set jako szkic setu |
| **P** | odsłuch zaznaczonego utworu (rozdział 6) |

Na dole jest wiersz **Analizuj**: wklej ścieżkę folderu z muzyką
i kliknij przycisk — tak dogrywasz nowe pliki (i tak zaczyna pierwszy
użytkownik). Przed analizą każdy plik sprawdza bramkarz: uszkodzone
odpadają z imiennym powodem, zamiast psuć analizę.

Obok jest przycisk **Artwork** — synchronizacja okładek: aplikacja
znajduje pliki bez osadzonej okładki, pyta iTunes o artystę i tytuł
i przy PEWNYM dopasowaniu wpisuje okładkę (600×600) do tagów pliku —
niejednoznaczne trafienia są pomijane z powodem (raport w notkach
i w pliku). Audio nietknięte. **Ważne:** żeby okładki weszły do
Rekordboxa (i na ekrany CDJ), zaznacz potem utwory w RB i wybierz
**Reload Tags**.

---

## 5. Set — od briefu do playlisty

### Krok po kroku: zwykły set
1. Wypełnij **brief** po lewej: długość w minutach, okno tempa
   (np. `130-135`), ewentualnie gatunki i kotwicę.
2. Naciśnij **B** — silnik buduje set; postęp widzisz na żywo.
3. Przejrzyj tabelę, posłuchaj wątpliwych miejsc (rozdział 6), popraw
   set edycją (niżej).
4. Zapisz plan (**S**) i/lub wyślij do Rekordboxa (**W**).

### Krok po kroku: set na filarach
1. W Bibliotece oznacz **F** od 3 do 10 utworów, które muszą zagrać.
2. Naciśnij **G** — filary trafiają do zakładki Set jako złote wiersze
   z flagą ⚑, a aplikacja pyta o **tryb rozstawienia**:
   - **Podpory** — silnik najpierw buduje set bez filarów, mierzy każde
     przejście i wstawia filary w najsłabsze miejsca;
   - **Równy rozstaw** — filary równomiernie po całym secie;
   - **Rama** — najwolniejszy filar otwiera set, najszybszy zamyka.
   Tryb zmienisz w każdej chwili drugim naciśnięciem **F** w Secie.
3. Uzupełnij brief i naciśnij **B**. Filary pozostają oznaczone złotem
   także w gotowym secie i zachowują się jak zwykłe utwory.

### Świeżość i seed
Pole **Świeżość** w briefie decyduje, czy ten sam brief daje zawsze ten
sam set (`deterministyczny` — ustawienie domyślne), czy silnik ma omijać
utwory i przejścia z setów już użytych (`zachowawczy` → `odkrywczy`,
coraz mocniej). „Użyty" znaczy: zapisany (**S**) albo wysłany (**W**) —
samo klikanie **B** nie liczy się jako granie. Przy trybach świeżości
aplikacja losuje **seed** i pokazuje go nad tabelą; wpisanie tego samego
seeda w brief powtarza set co do utworu.

### Edycja setu
| klawisz | działanie |
|---|---|
| **Z** | podmień zaznaczony utwór: panel po prawej pokazuje 10 propozycji ocenionych w tym miejscu setu; klik na propozycję i drugie **Z** wykonuje podmianę. W panelu wybierzesz tryb oceny: smart / BPM najpierw / tonacja najpierw |
| **A** | dopisz nowy utwór ZA zaznaczonym — ten sam panel propozycji, klik i drugie **A** |
| **X** | wytnij zaznaczony utwór; wycięcie filaru zdejmuje też jego pin |
| **Shift+↑ / Shift+↓** | przesuń zaznaczony utwór w górę / w dół |

Każda edycja zapisuje się jako werdykt.

### Plany: zapis i powrót
- **S** — pyta o **nazwę** i zapisuje plan (kolejność, brief, historię
  edycji).
- **O** — pokazuje listę planów z pełnym opisem (nazwa · liczba utworów ·
  okno tempa · kotwica · data). Klik i drugie **O** wczytuje — także po
  ponownym uruchomieniu aplikacji. **X** na liście usuwa plan (miękko,
  do kosza obok planów). Utwory, których nie ma już w puli, są przy
  wczytaniu pomijane z wyraźną notką.

### Werdykt i informacje
- **V** — zapisuje obok siebie „co ułożył silnik" i „co zostawiłeś po
  swoich zmianach".
- **I** — karta zaznaczonego utworu: metadane silnika, położenie pliku
  na dysku oraz to, co wie Rekordbox (jego tonacja i tempo, komentarz,
  playlisty, w których utwór leży). Drugie **I** lub **Esc** zamyka.

### Wysyłka do Rekordboxa
**W** tworzy playlistę z bieżącego setu w bazie Rekordboxa.
**Rekordbox musi być zamknięty** — przy otwartym aplikacja odmówi i nic
nie dotknie. Przed każdym zapisem sama robi kopię bazy, a po zapisie
sprawdza odczytem, czy w bazie jest dokładnie to, co miało być.

---

## 6. Odsłuch

Sterowanie jak w każdym odtwarzaczu (Spotify, Apple Music, Quick Look
Findera) — bez własnych wynalazków:

- **Spacja** — graj / pauza zaznaczonego utworu (działa w Bibliotece
  i w Secie; **P** robi to samo). Spacja na tym samym utworze wznawia
  od miejsca pauzy.
- **↓ / ↑ w trakcie grania** — działa jak „następny / poprzedni utwór":
  odtwarzanie przełącza się na nowo zaznaczony utwór (poprzedni zawsze
  zatrzymany). Przy pauzie lub ciszy strzałki tylko poruszają się
  po liście.
- **→ / ← w trakcie grania** — skok o **8 uderzeń** (równe 2 takty,
  liczone z tempa utworu); z **Shift** skok o **32**, a **PgUp/PgDn**
  (albo ⌘⇧ ze strzałką, jeśli Twój terminal go przepuszcza) o **128**.
  Gdy nic nie gra, klawisze działają normalnie.
- **C** w Secie otwiera **pasek szwu** nad tabelą — fakty o parze
  zaznaczony→następny i przycisk **▶ Graj oba**. Przy otwartym pasku
  spacja/P gra przejście pary. Drugie **C** lub **Esc** chowa pasek.

W Bibliotece, pod listą utworów, jest **odtwarzacz** w układzie
Apple Music: po lewej przyciski Poprz. · -8 · Graj/Pauza · +8 · Nast.,
obok **okładka** grającego utworu (mozaika z grafiki osadzonej w tagach
pliku), dalej tytuł, wykonawca i pozycja. Przyciski robią dokładnie to
samo, co klawisze. Gdy utwór skończy się sam, automatycznie gra następny
z listy; na końcu listy zapada cisza.

Dźwięk startuje wyłącznie z Twojego klawisza — nic nigdy nie gra samo.

---

## 7. Jak czytać ekran

- **Pogrubione tempo i tonacja** — dla czytelności, w obu tabelach.
- **„RB" w kolumnie pewności** — tonacja pochodzi z analizy Rekordboxa
  (źródło, nie liczba). Przygaszona tonacja z „?" — silnik nie jest jej
  pewny.
- **„…" w kolumnie LUFS** — głośność jeszcze nie zmierzona (tło mierzy
  po jednym utworze; wynik trafia do trwałej pamięci).
- **Notki (L)** — silnik zapisuje tam, czego nie wie i co odrzucił;
  licznik notek zawsze widać w pasku statusu, a odmowy i wynik wysyłki
  wyskakują same jako dymek.
- **Pasek skrótów na dole** pokazuje tylko klawisze aktywnej zakładki.

Zasada całej aplikacji: **żadna liczba nie jest zmyślona** — gdy silnik
czegoś nie wie, widzisz to wprost.

---

## 8. Gdy coś nie działa

| objaw | co zrobić |
|---|---|
| krzywy układ, ucięte kolumny | powiększ okno Terminala — aplikacja sama się przerysuje |
| „command not found" | uruchamiasz spoza folderu silnika — użyj skrótu z biurka |
| **W** odmawia | to nie błąd: Rekordbox jest otwarty; zamknij go i ponów |
| budowa odmawia | powód jest zawsze w notkach (**L**) i w dymku |
| skoki →/← nie działają | wymagają zainstalowanego ffplay (`brew install ffmpeg`) |
