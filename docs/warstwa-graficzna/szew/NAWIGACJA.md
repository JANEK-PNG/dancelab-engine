# Nawigacja płótna szwu — mapa opcji z edytora krzywych Blendera

Źródło: oficjalny manual Blendera 5.2, rozdział Graph Editor (przeczytany
20.08.2026; docs.blender.org/manual/en/latest/editors/graph_editor/).
Zasada nadrzędna: z Blendera bierzemy **nawigację (czytanie)**, świadomie NIE
bierzemy **edycji** — pomiaru nie przesuwa się ręką.

## Pełna lista opcji widoku/nawigacji Blendera → decyzja

| Blender (klawisz) | Co robi | Decyzja dla płótna |
|---|---|---|
| Pan (przeciąganie MMB) | przesuwa widok w obu osiach | **TERAZ** — u nas przeciąganie LMB (w przeglądarce środkowy przycisk jest zawodny, a lewy nie ma innej roli) |
| Zoom (kółko) | przybliża/oddala do kursora | **TERAZ** — kółko = zoom obu osi wokół kursora; szczypnięcie na gładziku = to samo |
| Scale View (Ctrl+MMB, kierunkowo) | ruch poziomy skaluje X, pionowy Y | **TERAZ** — Ctrl+przeciąganie, wiernie kierunkowo; dodatkowo Shift+kółko = sama oś X, Alt+kółko = sama oś Y |
| Scrollbary z uchwytami zoomu | pasek przewija, końce paska skalują oś | PÓŹNIEJ — dopiero gdy będzie więcej paneli; na razie zbędny mebel |
| Frame All (Home) | dopasowuje widok do wszystkich danych | **TERAZ** — Home i dwuklik; UWAGA: uczciwie obejmuje też ramki „poza skalą" (artefakt 9,9 staje się widoczny w całości) |
| Frame Scene/Preview Range | wraca do zakresu sceny | **TERAZ** jako „widok domyślny" (Esc lub 0): okno szwu × sufit 2,0 |
| Frame Selected (Numpad.) | dopasowuje do zaznaczenia | PÓŹNIEJ — nie ma jeszcze zaznaczania |
| Local View (/) — izolacja krzywych | pokazuje tylko wybrane krzywe | PÓŹNIEJ — jako izolacja głosu A/B albo piętra (klik w legendę); dobry kandydat na następną warstwę |
| Playhead + 2D Cursor | kursor czasu i wartości, oś odczytu | PÓŹNIEJ — kursor czasu z odczytem wartości pod spodem TAK (bez dźwięku — dźwięk w panelu zakazany); pivot do rotacji NIE (nie edytujemy) |
| Set/Clear Preview Range (P) | ogranicza odtwarzanie do zakresu | PÓŹNIEJ — u nas jako „zakres porównania", nie odtwarzania |
| Normalize (+Auto) | każda krzywa osobno skalowana do −1..1, reszta przyciemniona | ODRZUCONE na teraz — per-krzywa skala łamie wspólną skalę pięter (nasza norma); jeśli kiedyś wróci, to z jawnym przyciemnieniem jak w Blenderze |
| Ghost Curves | zamrożona kopia krzywych w tle jako odniesienie | PÓŹNIEJ — świetny kandydat: nakładka drugiego szwu do porównania |
| Sync Visible Range | synchronizuje oś czasu między edytorami | PÓŹNIEJ — gdy będzie więcej płócien naraz |
| Use Timecode (Ctrl+T) | sekundy zamiast klatek | MAMY z natury (mm:ss) |
| Show Extrapolation | pokazuje przedłużenia krzywych | NIE DOTYCZY — nie ekstrapolujemy pomiaru, poza oknem nie ma danych |
| Edycja: keyframes/uchwyty, selekcje (A/B/C/K/[…]), snap, proportional, sliders, auto-merge | zmienianie krzywych | **ODRZUCONE trwale** — płótno czyta pomiar, nie edytuje go |

## Ustalenia implementacyjne (rdzeń, wdrożony 20.08)

* Widok = zakres danych (x0–x1 czasu, y0–y1 wartości), wspólny dla trzech
  pięter — piętra pozostają porównywalne przy każdym zoomie.
* **Sufit 2,0 z decyzji Janka staje się własnością WIDOKU domyślnego**, nie
  rysunku: trójkąt ▲ znaczy „wartość powyżej górnej krawędzi widoku" i znika,
  gdy zoom obejmie wartość. Licznik przy dole pasa mówi ile ramek i jakie
  maksimum. Dane zawsze nietknięte.
* Oś Y przycięta od dołu do 0 (obecność ujemna nie istnieje w pomiarze);
  granice zoomu: X od 2 s do 1,2× okna szwu, Y od 0,2 do 1,2× maksimum danych.
* Podziałki obu osi dobierają krok do zoomu (czas: 1 s–60 s; wartość:
  0,1–1,0), żeby liczby były czytelne zamiast się tłoczyć.
* Klawisze: Home / dwuklik = całość danych · Esc / 0 = widok domyślny.
  Mysz/gładzik: przeciąganie = pan · kółko / szczypnięcie = zoom · Shift+kółko
  = X · Alt+kółko = Y · Ctrl+przeciąganie = skala kierunkowa.
