# DanceLab — jak samemu odpalić aplikację (TUI)

Stan: 2026-08-04. Ta instrukcja jest dla Ciebie (i dla Barta) — zero wiedzy
technicznej nie przeszkadza.

## Sposób 1 — podwójne kliknięcie (polecany)

Na biurku leży **`DanceLab.command`** — kliknij dwa razy i aplikacja wstaje.
Skrót zawsze odpala AKTUALNY kod z repo, więc po każdej aktualizacji
dostajesz nową wersję bez robienia czegokolwiek.

(Drugi egzemplarz tego pliku leży w `Developer/dancelab-engine` — gdyby ten
z biurka kiedyś zginął. Przy pierwszym uruchomieniu macOS może zapytać, czy
na pewno otworzyć — kliknij prawym → **Otwórz**, potem już nie pyta.)

## Sposób 2 — ręcznie w Terminalu

```bash
cd ~/Developer/dancelab-engine && .venv/bin/dancelab tui
```

## Zakładki

Aplikacja ma trzy zakładki: **Biblioteka · Set · Eksport/Cue** — przełączasz
je **Ctrl+Tab** (albo kliknięciem; część terminali połyka Ctrl+Tab).

### Biblioteka
- **Sekcje po lewej** (zawsze widoczne, jak w Apple Music): Cała biblioteka,
  ♥ Ulubione utwory, ⚑ Filary; przypięte playlisty dojdą z widokiem playlist.
- **Szukajka i filtry** na górze: fragment nazwy lub gatunku, dokładna
  tonacja (np. `8A`), okno tempa (np. `125-140`). Filtrują na żywo.
- Tabela pokazuje wszystko, co silnik wie: BPM, tonację (tam, gdzie
  Rekordbox ją zna, gra jego tonacja — w kolumnie pewności widzisz „RB"
  zamiast liczby; pytajnik został tylko dla utworów bez tonacji w RB),
  względną energię (0–100 w obrębie Twojej biblioteki; „—" = silnik nie wie),
  gatunek, długość.
- **U** — przypina utwór do ulubionych (♥). **F** — robi z utworu **FILAR**:
  utwór, który MUSI zagrać w budowanym secie. Filarów jest **od 3 do 10** —
  silnik projektuje drogę MIĘDZY filarami, reszta należy do niego.
  Legenda z tymi skrótami jest cały czas widoczna nad tabelą.
- **G** albo przycisk **„→ Zbuduj z filarów"** — przenosi filary do zakładki
  Set jako **szkic** (złote wiersze z flagą ⚑), CELOWO bez budowania. Po G
  otwiera się **panel trybów filarów** (drugie **F** w zakładce Set otwiera go
  w każdej chwili; klik + F wybiera):
  - **Podpory** — silnik najpierw buduje konstrukcję bez filarów, mierzy
    każde przęsło i wstawia filary w zmierzone najsłabsze miejsca;
  - **Równy rozstaw** — filary równomiernie po całym secie;
  - **Rama** — najwolniejszy filar otwiera set, najszybszy zamyka, środek
    równomiernie.
  Potem uzupełniasz brief po lewej (minuty, okno tempa, gatunki, kotwica)
  i **B** buduje. Filary w gotowym secie są oznaczone ⚑ i złotem, a zachowują
  się jak zwykłe utwory (przesuwanie, dopisywanie, podmiana);
  **wycięcie filaru (X) zdejmuje też pin** — F w Bibliotece przypina
  z powrotem.
- **Sortowanie**: nagłówki kolumn to klikalne kafelki. Klik = **↓** (od
  małego do większego), drugi klik = **↑** (odwrotnie), trzeci kasuje —
  strzałka znika. Strzałkę widać w samym nagłówku i w liczniku; utwory bez
  wartości idą zawsze na koniec.
- Kolumny **wykonawca** i **tytuł** są osobno — tam, gdzie plik nie ma tagów,
  dane dociągają się z Twojej kolekcji Rekordboxa, a w ostateczności
  z nazwy pliku.
- Na dole wiersz **Analizuj**: wklej ścieżkę folderu z muzyką i kliknij —
  tak dogrywasz nowe pliki do puli (i tak zaczyna pierwszy użytkownik).

### Set — budowa i edycja (szczegóły niżej)

### Eksport/Cue — w budowie (edytor hot cue wg wizji 2.0)

## Co robisz w środku (zakładka Set)

1. **Formularz** (góra): pula utworów, długość w minutach, okno tempa
   (np. `130-135`), gatunki (Twoje tagi z Rekordboxa), DJ z listy kotwic
   („graj jak X"), kontur skoków.
2. **B** — buduje set. Postęp leci na żywo, wynik ląduje w tabeli.
3. Klikasz utwór w tabeli i **Z** — po prawej otwiera się panel z 10 propozycjami
   podmiany, ocenianymi w TYM miejscu setu (jak wchodzi po poprzednim i jak
   wychodzi w następny). Klikasz propozycję i znów **Z** — podmiana zrobiona.
   - W panelu jest **wybór trybu oceny**: `smart` (pełna ocena, którą powstał
     set, plus kotwica), `BPM najpierw` albo `tonacja najpierw` — zmiana trybu
     od razu przelicza propozycje.
4. **Edycja setu** (te same ruchy, które robiłeś ręcznie w Rekordboksie):
   - **X** — wycina zaznaczony utwór;
   - **Shift+↑ / Shift+↓** — przesuwa zaznaczony utwór w górę/dół;
   - **A** — dopisuje NOWY utwór ZA zaznaczonym: panel 10 propozycji jak przy Z,
     klik + drugie **A** dopisuje (nikt nie wypada).
   Każda taka edycja zapisuje się jako Twój werdykt — silnik się z nich uczy.
5. **S** — zapisuje plan: najpierw pyta o **nazwę** (po niej go potem
   znajdziesz). **O** — lista zapisanych planów z pełnym opisem: nazwa,
   liczba utworów, okno BPM, kotwica, data; klik + drugie **O** wczytuje
   (także po ponownym uruchomieniu; braki w puli pomijane z notką),
   **X** usuwa zaznaczony plan (miękko, do kosza obok planów).
6. **C** — PASEK SZWU (wzorzec z CURVE: „+" między dwoma utworami):
   nad tabelą pojawia się jedna linia faktów o parze zaznaczony→następny
   (kto z kim, ile uderzeń, czasy wyjścia i wejścia) i JEDEN przycisk
   **▶ Graj oba**. Beatsync i kwantyzacja są zawsze włączone — siedzą
   w naturze renderu. Drugie **C** albo **Esc** chowa.
   **P** — odsłuch SAMEGO zaznaczonego utworu (drugie **P** albo **Esc**
   zatrzymuje). Przejście pary gra przycisk **▶ Graj oba** w pasku szwu (C).
   Dźwięk zawsze startuje tylko z Twojego klawisza.
7. **V** — świadomy werdykt: zrzuca obok siebie „co ułożył silnik" i „co
   zostawiłeś po swoich zmianach".
   **I** — karta informacji o zaznaczonym utworze: metadane silnika (BPM,
   tonacja z pewnością, gatunek, długość), lokalizacja pliku na dysku oraz
   to, co wie Rekordbox (jego BPM, komentarz i playlisty, w których utwór
   aktualnie leży — prosto z master.db). Drugie **I** albo **Esc** zamyka.
8. **W** — wgrywa playlistę do Rekordboxa. **Rekordbox musi być ZAMKNIĘTY** —
   inaczej aplikacja odmówi i nic nie dotknie. Przed każdym zapisem sama robi
   kopię bazy (`DanceLab_backups/`), a po zapisie sprawdza odczytem, czy w bazie
   jest dokładnie to, co miało być.
9. **Esc** — zamyka panel po prawej / zatrzymuje odsłuch / przerywa budowę.
   **Q** — wyjście.

## Jak czytać ekran (zasada uczciwości)

- BPM i tonacja są pogrubione — czytelne w jasnym i ciemnym motywie.
- Przygaszona tonacja ze znakiem „?" = silnik nie jest jej pewny (pewność
  poniżej 0,5).
- Pasek skrótów na dole jest kontekstowy: w Bibliotece widzisz klawisze
  Biblioteki, w Secie — Setu.
- Notki silnika („czego nie wiem, co odrzuciłem") są schowane — **L** (log)
  je pokazuje i chowa; licznik notek widać zawsze w pasku statusu. Odmowy
  i wynik zapisu do Rekordboxa wyskakują same jako dymek.
- Pasek statusu pokazuje, czy Rekordbox chodzi i ile jest kopii zapasowych.

## Gdy coś nie działa

- **Krzywo wygląda / ucięte kolumny** → powiększ okno Terminala, aplikacja
  sama się przerysuje.
- **„command not found"** → uruchamiasz spoza folderu silnika; użyj Sposobu 1.
- **W odmawia** → to nie błąd: Rekordbox jest otwarty. Zamknij go i spróbuj
  jeszcze raz.
