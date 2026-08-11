# TERRAIN × TUI: zderzenie i synteza — nowy UI o rdzeniu TUI i wyglądzie GUI

**Data:** 2026-08-11 · **Decyzja Janka:** „odbijmy od siebie te dwa pomysły
i zobaczmy, co wypełni braki w jednym i drugim; części wspólne
zaimplementujmy do nowego UI, który rdzeń będzie miał TUI, ale wygląd GUI".

**Strony zderzenia:** TERRAIN (zatwierdzony kierunek z 2026-07-15: blueprint
+ inwentarz ruchu + karta zespołu + biblia komponentów) kontra TUI
(żywy interfejs, ~5 tygodni codziennej praktyki i pomiarów, stan w
`docs/TUI_MAPA.md`).

---

## 1 · Czego TERRAIN nie wiedział (wnosi TUI)

TERRAIN powstał 15.07 — przed całym dojrzewaniem cue, kotwic i pomiarów.
Miesiąc praktyki wnosi do syntezy rzeczy ZMIERZONE, nie wymyślone:

1. **Cała maszyneria CUE, której blueprint nie zna.** Pady na taktach
   Rekordboxa, kwantyzacja ręcznego czasu, konflikt `skip` (pad DJ-a
   nietykalny), rejestr UUID naszych padów (tylko swoje wolno odświeżyć),
   guzik trójstanowy zapisu, odsłuch szwu Z PADÓW. Blueprint w bramie
   eksportu mówi „Write XML" — to jest martwa droga; realny, **udowodniony
   E2E** eksport to zapis hot cue do master.db (backup → safe-swap →
   weryfikacja), a USB-export robi DJ w Rekordboksie.
2. **Nowe prawdy silnika** (wszystkie po 15.07): łuk energii domyślnie OFF
   (dock terenu ma pokazywać energię jako DANE, nigdy jako cel do gonienia);
   kotwica ★ z własnych ulubionych; sito brzmienia z jawnym rozluźnianiem;
   most do filara; głośne zero briefu gatunkowego; ostrzeżenie o słabych
   szwach; tonacja ze źródłem („RB"/„ręka").
3. **Zmierzone werdykty UX** — miesiąc wet i iteracji Janka:
   - jedna nakładka, pięć trybów; Enter kontekstowy (gatunki: dodaje
     i lista zostaje; DJ: ustawia i zamyka);
   - odsłuch wg standardu graczy (Spacja graj/pauza; gdy gra ↓/↑ =
     next/previous; skoki 8/32/128);
   - operacje nieodwracalne = dwa naciśnięcia (W liczy i pokazuje,
     drugie W zapisuje);
   - ostrzeżenia schowane z licznikiem zawsze widocznym; ważne dymkiem;
   - okładki jako przełącznik z nazwanym kompromisem (×3 wysokość wiersza);
   - sekcje biblioteki po lewej (wzór Apple Music): Cała · ♥ · ⚑;
   - plany S/O/X z koszem i pełnym opisem; seed novelty POKAZANY.
4. **Aktywa danych, których TERRAIN nie znał:** mapa DJ-ów (39 267 track id,
   7 117+ z pełną analizą i wektorem, 3 743 pełne szwy), pamięć precedensów
   (konteksty A|B|C; typ utworu kameleon/kotwica), LUFS, okładki z tagów,
   księga 285 kotwic z grupowaniem po brzmieniu.
5. **Brak nazwany przez mapę komponentów:** import z Rekordboxa i żniwa
   wektorów żyją w skryptach terminalowych operatora — **nowy UI musi mieć
   te guziki**, inaczej pozostaje laboratorium z asystentem.

## 2 · Czego TUI nie ma (wnosi TERRAIN)

1. **TRACK jako pełny widok.** TUI ma kartę INFO (panel boczny). TERRAIN
   robi z wnętrza utworu równorzędny widok — i dopiero mapa precedensów
   daje mu treść, której w lipcu nie było: „czterech DJ-ów poszło z tego
   utworu w cztery światy" (proweniencja, nie predykcja).
2. **SEAM jako pełny widok.** TUI ma pasek faktów (C) i kartę cue.
   TERRAIN wynosi szew do rangi ekranu — to jest teza domeny w UI.
3. **Terrain dock** — stała mapa setu na dole (kolejność, energia, jakość
   szwów, zaznaczenie), wspólna dla SET/SEAM/TRACK. W TUI kontekst setu
   ginie przy przełączaniu tabów.
4. **Ciągłość tożsamości** — ten sam utwór/szew zachowuje tożsamość
   (i animowaną relację) przy zmianie widoku.
5. **System ruchu**: 6 tokenów czasu, spring tylko dla przeciąganych
   obiektów, linear tylko dla czasu/playbacku, animacje przerywalne,
   wariant reduced — plus zasada „ruch bez pracy nie wchodzi".
6. **Readiness zamiast kolejności** — brakujące dane wyłączają KONKRETNĄ
   akcję z powodem; widok nigdy nie jest zamknięty.
7. **Joby w tle jako obywatel UI** (status w pasku projektu) — dokładnie
   miejsce dla przycisków importu/żniw z punktu 1.5.
8. **Sesja-projekt**: autosave + File > Save/Open/Recent — TUI ma plany,
   TERRAIN ma projekt.
9. **Jeden czasownik główny na kontekst** (volt) i **Export Gate** jako
   jedyna brama zapisu zewnętrznego.

## 3 · Konflikty i rozstrzygnięcia

| konflikt | rozstrzygnięcie syntezy |
|---|---|
| 3 taby (TUI) vs 4 widoki + Gate (TERRAIN) | **4 widoki, ale SEAM i CUE to JEDEN widok.** Miesiąc TUI dowiódł: dla DJ-a interfejsem szwu SĄ pady („szew powstaje z moich padów" — Janek 09.08). SEAM = anatomia przejścia + pady na przebiegu + odsłuch; zapis przez Gate. |
| Export Gate: „Write XML" | Gate ZOSTAJE (formalizuje dwa naciśnięcia W), treść wymieniona: manifest = pady → master.db (konflikty, backup, ledger UUID), playlisty RB. XML wypada. |
| waveformy: weto z TUI (06.08) vs TERRAIN | Sprzeczność pozorna. Weto dotyczyło waveformów-DEKORACJI w terminalu („not even functional, just for the look"). W TERRAIN przebieg wykonuje pracę MANIPULACJI (pady przeciąga się PO nim) — zgodne z prawem ruchu. Wchodzi jako narzędzie, nie ozdoba. |
| Qt Widgets (założenie blueprintu) | **Decyzja stacku OTWARTA — celowo poza tym dokumentem.** Fakty do niej: Qt headless na Darwin 25 kruchy (testy przez Dockera); rdzeń i warstwy stanu są w Pythonie; kontrakty czyste, więc synteza jest stack-agnostyczna. |
| energia w docku terenu | Po pomiarze kształtu setu (10–11.08): energia to DANE o secie, nie cel. Dock nie sugeruje „powinno rosnąć". |
| karta zespołu 21 ról | Zostaje jako protokół przeglądu biblii (junior może zatrzymać dowodem); nie jest strukturą zatrudnienia. |

## 4 · Część wspólna — rdzeń, który obie strony już mają

To jest fundament nowego UI, bo obie strony doszły do niego NIEZALEŻNIE:

1. **Uczciwość jako prawo interfejsu** (ADR-005): każde „nie wiem" silnika
   ma swój piksel; zero fałszywego postępu; playhead/progress czytają
   prawdziwy stan. TUI robi to w praktyce, TERRAIN wpisał to w prawo ruchu.
2. **Zakładki to nie kroki** — TUI już tak działa, TERRAIN to formalizuje.
3. **Nakładka #suggest ↔ Context inspector** — to samo zjawisko; inspector
   to dorosła wersja jednego panelu o pięciu trybach.
4. **Dwa naciśnięcia ↔ Export Gate** — ta sama zasada nieodwracalności.
5. **Puste stany uczciwe** („zbuduj w Set (B)" zamiast pustki bez powodu).
6. **Dźwięk wyłącznie z ręki użytkownika.**

## 5 · Kształt nowego UI — „rdzeń TUI, wygląd GUI"

**Architektura dwóch skór na jednym rdzeniu.** Czyste moduły TUI
(`cue_podglad`, `cue_edycje`, `cue_zapis`, `seam_preview`, `plan_store`,
`user_store`, `gatunki`, `grupy_dj`) awansują na oficjalną **warstwę stanu
UI** (kontrakty: pady efektywne, plan cue, propozycje, stan użytkownika).
Obie skóry — terminalowa i graficzna — konsumują te same kontrakty. TUI
NIE umiera: zostaje powierzchnią laboratoryjną i dla power-userów; GUI
jest skórą TERRAIN. Test nowej funkcji: najpierw kontrakt w warstwie
stanu, potem dwie skóry.

**Widoki:**
- **LIBRARY** — tabela z sekcjami ♥/⚑, filtry, okładki, LUFS; przyciski
  jobów: import z Rekordboxa, żniwa wektorów, analiza folderu (bramkarz).
- **SET** — brief (gatunki, BPM, łuk jako świadoma opcja, plan tempa,
  novelty z seedem) + kotwica (285 + ★) + tabela + ostrzeżenia + dock.
- **SEAM/CUE** — anatomia wybranego przejścia: okna, strategia, PADY NA
  PRZEBIEGU (spring przy drag, snap do taktu RB), odsłuch od pada,
  precedensy pary z mapy; zapis wyłącznie przez Gate.
- **TRACK** — wnętrze utworu: przebieg, sekcje, tonacja ze źródłem,
  energia/groove/bas, pady, występowanie w setach + konteksty precedensów
  (kameleon/kotwica).
- **EXPORT GATE** — manifest zapisu do master.db: co, czyje pady ustępują,
  backup, wynik weryfikacji; playlisty RB.
- **Terrain dock** — kolejność, energia (dane), jakość szwów
  (transition_score, próg 0,60), zaznaczenie; wspólna nawigacja.

**Klawiszologia TUI przechodzi w całości** (B/W/Z/X/A/S/O/Spacja/skoki/
Ctrl+G/Ctrl+D…) — GUI dostaje mysz i drag, nie traci klawiatury.

**Ruch:** tokeny i zasady z biblii bez zmian; audyt statusów biblii
przeciwko dzisiejszemu runtime'owi = osobny krok.

## 6 · Czego świadomie NIE ma w syntezie

- Graph Mode (poza zakresem TERRAIN — zostaje poza).
- Poświata influence (weto 05.08 po użyciu).
- Waveformy-dekoracje bez pracy manipulacji.
- Kroki/wizard/checkmarki ukończenia.
- Automatyczny dźwięk czegokolwiek.
- Fałszywy postęp i zmyślone liczby (w tym „wierność łukowi", gdy łuk OFF).

## 7 · Kolejność wdrożenia (propozycja do decyzji)

1. Audyt statusów biblii vs runtime (Existing/Adapt/Planned/Deferred
   z dowodami z kodu) — aktualizacja ledgera implementacyjnego.
2. Decyzja stacku (fakty z §3) — osobna, świadoma.
3. Kontrakty warstwy stanu: nazwać i domknąć istniejące czyste moduły
   (bez pisania nowej logiki — ona już jest).
4. Pierwszy ekran skóry GUI: **SEAM/CUE** (największy zysk vs terminal:
   pady na prawdziwym przebiegu) — z Gate jako drugim krokiem.
5. Dock + LIBRARY + SET; TRACK z precedensami na końcu (zależy od mapy).
