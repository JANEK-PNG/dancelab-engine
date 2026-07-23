# DanceLab Pro: blueprint adaptacji aktywnego produktu do TERRAIN

**Status decyzji:** TERRAIN jest zatwierdzonym, domyślnym UI produktu.  
**Data:** 2026-07-15  
**Zakres:** migracja aktywnego Simple Mode do TERRAIN bez przepisywania silnika.  
**Poza zakresem:** Graph Mode, strojenie algorytmów audio i dodawanie nowych modeli decyzyjnych.

Powiązana specyfikacja motion: `docs/TERRAIN_MOTION_INVENTORY_2026-07-15.md`.

## 1. Decyzja produktowa

DanceLab przestaje komunikować pracę jako liniowy proces instalacyjny:

`Import -> Initial Check -> Generate -> Review -> Export`

Docelowo staje się jednym, stale dostępnym instrumentem roboczym:

`LIBRARY | SET | SEAM | TRACK` + modalny `EXPORT GATE`

Zakładki nie są krokami. Nie oznaczają ukończenia ani nie blokują powrotu. Użytkownik może w dowolnej kolejności:

- dodawać i usuwać muzykę;
- obserwować analizę w tle;
- zmieniać brief;
- oglądać istniejący plan;
- otwierać dowolny track albo seam;
- wracać do biblioteki bez utraty setu;
- eksportować dopiero wtedy, kiedy jawny manifest eksportu jest gotowy.

Najważniejsza zasada migracji: **zmiana miejsca w UI nie zmienia ani nie usuwa stanu projektu**.

## 2. Reguły zachowania TERRAIN

| Reguła | Docelowe zachowanie |
|---|---|
| Nawigacja | `LIBRARY`, `SET`, `SEAM`, `TRACK` są równorzędnymi widokami tej samej sesji. |
| Brak `Next/Back` | Znikają przyciski następnego i poprzedniego kroku, numeracja etapów oraz wizualne checkmarki ukończenia. |
| Readiness zamiast kolejności | Brakujące dane wyłączają konkretną akcję i wyjaśniają dlaczego, ale nie zamykają całego widoku. |
| Import zawsze dostępny | Pliki, foldery i źródła Rekordbox można dodać z każdego widoku. |
| Niedestrukcyjne dodawanie | Nowe utwory trafiają do biblioteki i analizy. Nie zmieniają automatycznie istniejącej kolejności setu. |
| Niedestrukcyjny brief | Zmiana briefu oznacza plan jako `out of date`; stary plan pozostaje widoczny do jawnego `Regrow`. |
| Background jobs | Quick i Deep Analysis działają poza nawigacją; użytkownik może przełączać widoki podczas pracy jobu. |
| Jeden główny czasownik | W każdym kontekście istnieje najwyżej jedna akcja volt: np. `Draw terrain`, `Preview transition`, `Write XML`. |
| Stały kontekst setu | Gdy istnieje plan, dolny terrain dock pozostaje dostępny w `SET`, `SEAM` i `TRACK`. |
| Autosave bez utraty kontroli | Sesja zapisuje się automatycznie, ale desktopowe `File > Save / Save As / Open / Recent / Recover` pozostaje dostępne. |
| Eksport jako jedyna brama | Tylko zapis zewnętrznego pliku przechodzi przez modalny `EXPORT GATE`. |

## 3. Docelowy model aplikacji

### 3.1 Shell

Nowy `TerrainMainWindow` powinien zawierać pięć stałych regionów:

| Region | Odpowiedzialność | Zachowanie |
|---|---|---|
| Project bar | Nazwa projektu, autosave, liczba utworów, job status, wejście do Gate | Nie pokazuje numeru kroku ani `Simple Mode`. |
| Workspace tabs | `LIBRARY`, `SET`, `SEAM`, `TRACK` | Każdy dostępny zawsze; pusty widok ma własny uczciwy empty state. |
| Main workspace | Zawartość aktualnego poziomu | Zmiana zakładki nie uruchamia, nie anuluje i nie resetuje runtime'u. |
| Context inspector | Brief, track details, seam strategy albo job details | Zawartość zależy od zaznaczenia, nie od numeru strony. |
| Terrain dock | Skrócona kolejność, energia, jakość seamów, zaznaczenie | Pusty przed zbudowaniem setu; po planie jest wspólną mapą nawigacji. |

`EXPORT GATE` pozostaje modalem nad bieżącym widokiem, ponieważ wykonuje jawny zapis pliku poza projektem.

### 3.2 Wspólny stan sesji

Obecnie stan jest rozproszony po polach `SimpleModeWindow`. Przed zmianą shellu należy wprowadzić jeden `ProjectSession`, niezależny od konkretnych widgetów Qt.

| Fragment sesji | Minimalna zawartość |
|---|---|
| Project identity | Nazwa, ścieżka `.dlproj`, dirty/autosave state, format version. |
| Library | Source path, stabilny track ID, import source, analiza quick/deep, job state, błędy i confidence. |
| Brief | Długość, styl, BPM, rola, crowd energy, energy arc, planner, variation i seed. |
| Constraints | Must Have, Not Tonight, dokładne pozycje Lock. |
| Set revision | Plan, identyfikator rewizji, brief hash, library revision, status fresh/stale/partial. |
| Selection | Aktualny track, seam i pozycja setu. |
| Seam review | Verdict, strategia, komentarz, stan odsłuchu i użyta rewizja planu. |
| Cue decisions | Engine cues, imported cues, user corrections, provenance, confidence i final selection. |
| Jobs | Typ, track, stage, progress, ETA, stop requested i wynik. |
| Export | Manifest, blockers, warnings, output path i ostatni zapis. |

Widoki subskrybują sesję. Nie kopiują jej do prywatnych, rozjeżdżających się pól.

### 3.3 Komendy sesji

UI powinno wywoływać jawne komendy zamiast bezpośrednio mutować kilka widgetów:

| Komenda | Efekt |
|---|---|
| `import_sources(...)` | Dodaje pliki do biblioteki i kolejki Initial Check. |
| `remove_library_tracks(...)` | Usuwa z biblioteki po pokazaniu wpływu na plan. |
| `start_quick_analysis(...)` | Uruchamia brakujące quick tiers; cache pozostaje źródłem wznowienia. |
| `start_deep_analysis(...)` | Uruchamia deep tier dla setu albo jawnego zaznaczenia. |
| `update_brief(...)` | Aktualizuje brief i oznacza plan jako stale bez kasowania planu. |
| `grow_set()` | Buduje nową rewizję planu ze stabilnym snapshotem biblioteki i briefu. |
| `stop_after_current()` | Zatrzymuje job bez utraty ukończonych wyników. |
| `replace_slot(...)` | Zastępuje pozycję i przelicza dwa sąsiednie seamy. |
| `reorder_set(...)` | Zmienia kolejność i przelicza dotknięte przejścia. |
| `select_track(...)` | Otwiera ten sam track w bibliotece, mapie, docku lub TRACK. |
| `select_seam(...)` | Otwiera dokładną parę na poziomie SEAM. |
| `record_seam_verdict(...)` | Zapisuje decyzję użytkową niezależnie od ratingu R&D. |
| `move_cue(...)` | Tworzy wersjonowaną user correction w `CueDecisionStore`. |
| `build_export_manifest()` | Buduje deterministyczny diff i listę blockers/warnings. |
| `write_rekordbox_xml(...)` | Zapisuje dokładnie zatwierdzony manifest. |

## 4. Adaptacja istniejących funkcji do przestrzeni TERRAIN

### 4.1 Globalny Project Bar i Job Center

| Istniejąca możliwość | Docelowe miejsce | Sposób adaptacji |
|---|---|---|
| Nazwa projektu i status | Project bar | Zachować nazwę, usunąć numer kroku i chip `Simple Mode`. |
| Engine status | Project bar | Sprowadzić do krótkiego statusu całej sesji; szczegóły otwiera Job Center. |
| Cache ready / low disk | Job Center / storage popover | Nie zajmuje stałego miejsca, o ile nie wymaga uwagi. |
| Initial/Deep progress | Job Center | Jedna lista jobów z per-track stage, stop-after-current i błędami. |
| Autosave/dirty | Project bar | Tekst `saved HH:MM`, `saving...` albo `save failed`; menu File pozostaje. |
| Export | Project bar | `Export gate...` z liczbą blockers/warnings; nie jest osobną zakładką. |

### 4.2 LIBRARY

LIBRARY staje się trwałym crate drawerem i pełnym widokiem biblioteki. To ten sam zbiór danych w dwóch gęstościach, nie dwa osobne modele.

| Istniejąca możliwość | Docelowe miejsce | Sposób adaptacji |
|---|---|---|
| Wybór plików | Drop-zone + `Add files` | Zachować file finder i drag-and-drop. |
| Jeden lub wiele folderów | `Add folders` | Zachować multi-folder selection. |
| Rekordbox USB/imported cues | Menu importu w LIBRARY | Zachować źródło oraz cue provenance przy każdym tracku. |
| Pliki <2 min lub >10 min | Import review sheet | Pytać tylko o podejrzane pozycje; zaakceptowane od razu trafiają do kolejki. |
| Initial Check | Automatyczny background job | Nie jest stroną. Statusy: queued, analyzing stage, ready, warning, failed. |
| Analyzed Library | Library table/drawer | Reużyć model filtrowania, sortowania, BPM/key/style i reliable grid. |
| Must Have | Akcja `Pin` przy tracku | Ten sam constraint; widoczny również w briefie i docku. |
| Not Tonight | Akcja `Rest tonight` | Track zostaje w bibliotece, ale jest wykluczony z bieżącej sesji. |
| Search/filter/sort | Nagłówek LIBRARY | Zachować bez zmiany silnika. |
| Quick/deep tier | Badge przy tracku | Badge nie blokuje przejścia do innych widoków. |
| Błąd analizy | Badge + retry | Błąd jednego tracka nie zamyka biblioteki ani istniejącego setu. |

**Semantyka dodawania w trakcie pracy:** po dodaniu muzyki istniejący set pozostaje bez zmian. UI pokazuje `N new analyzed candidates available` i proponuje `Regrow` albo replacement dla wybranego slotu.

### 4.3 SET

SET jest główną przestrzenią produktu. Łączy brief, plan, energy terrain, jakość seamów i mapę kandydatów.

| Istniejąca możliwość | Docelowe miejsce | Sposób adaptacji |
|---|---|---|
| Set Brief | Prawy inspector | Długość, style, BPM, rola, crowd energy i arc widoczne bez opuszczania terrain. |
| Planner mode / variation / seed | `Advanced` w briefie | Zachować; nie przeciążać głównej intencji. |
| Presety | Początek inspectora | Custom, Calm UK/Bass i Warm-up deep/soft jako starting points. |
| Generate Set | `Draw terrain` / `Regrow terrain` | Ten sam `build_set()`, ale wynik trafia do nowej rewizji sesji. |
| Energy timeline | Centralny terrain canvas | Reużyć prawdziwe punkty i skalę biblioteki; nie wracać do sztucznej sinusoidy. |
| Transition quality | Paski pod seamami | Dane z istniejących `SetTransition`/`EdgeDecision`. |
| Mixability map | Alternatywny panel `Candidate map` | Zachować obecny ranking i selection bridge do tracka. |
| Pin / Lock / Rest | Menu kontekstowe tracka/slotu | Te same constraints, natychmiast widoczne w docku i briefie. |
| Artist diversity | Reason badge | Komunikować jako automatyczną regułę, nie kolejny parametr. |
| History-aware variation | `Regrow` options | Zachować historię i novelty mode. |
| Deep Analyze Set Tracks | Akcja przy statusie planu | Uruchamia background job, nie blokuje eksploracji planu. |
| Find Next / replacement ranking | Panel po zaznaczeniu slotu | Ranking musi oceniać oba dotknięte seamy przy replacement. |

**Zmiana briefu:** zachowujemy aktualny set i pokazujemy `Plan based on previous brief`. Dopiero `Regrow terrain` tworzy nową rewizję. Nie wolno po zmianie formularza po cichu kasować ani przebudowywać kolejności.

### 4.4 SEAM

SEAM wykorzystuje najbardziej dojrzały obecny komponent: `TransitionReviewWidget`.

| Istniejąca możliwość | Docelowe miejsce | Sposób adaptacji |
|---|---|---|
| Dokładna para track IDs | Selection w `ProjectSession` | Kliknięcie jointu zawsze otwiera tę samą parę z konkretnej rewizji setu. |
| Prawdziwe waveformy A/B | Główna część SEAM | Reużyć cache i obecny rendering, tylko zmienić kompozycję. |
| Zoom/pan/seek | Bez zmian funkcjonalnych | Zachować obsługę myszy i touchpada. |
| Beat sync preview | Preview controls | Pozostaje tylko odsłuchem aplikacji; nigdy danymi eksportowymi BPM. |
| 8-beat quantize | Preview/cue controls | Włączone wyłącznie dla reliable grid. |
| Region transition i cue drag | Waveform interaction | Każda korekta trafia do wspólnego `CueDecisionStore`. |
| Transition profiles | Strategy inspector | Linear, balanced, bass swap, tops swap, contour; z długością 32-256 beats. |
| EQ/fader simulation | Centralny transition simulation | Zachować jako preview, nie deklarować eksportu automatyki. |
| Stem audition | Source controls | Deep/Demucs albo jawny fallback. |
| Rating 1-5 + komentarz | Validation Mode | Nie mieszać z decyzją użytkową. |
| Nowy seam verdict | Stały action row | `Keep`, `Keep with strategy`, `Skip`, `Needs listen`. |
| Powody/ryzyko | Reason badges | Pokazywać runway, key, energy, overlap i warningi z silnika. |
| Terrain dock | Stały dół SEAM | Jointy, quality bars, verdict state i przejście do sąsiadów. |

### 4.5 TRACK

TRACK nie wymaga nowego analizera. Jest inspektorem jednego `AnalysisResult` oraz jego decyzji w bieżącej sesji.

| Dane/funkcja | Docelowa prezentacja |
|---|---|
| Identity | Tytuł, artysta, source path, stabilny track ID i import source. |
| Audio descriptors | BPM z confidence/provenance, key, energy, style i duration. |
| Structure | Pełny waveform, segmenty, windows, beatgrid confidence i cues. |
| Analysis tier | Quick/deep status, model/fallback provenance i akcja `Deep analyze`. |
| Session role | Must Have, Rest, Lock position oraz wystąpienie w planie. |
| Candidate context | Sąsiedzi Camelot/BPM/energy i wejście do `Find Next`. |
| Export preview | Final cues przeznaczone do manifestu oraz ich źródło. |

TRACK jest opcjonalnym poziomem szczegółu. Brak deep analysis nie może blokować jego otwarcia.

### 4.6 EXPORT GATE

GATE nie eksportuje bezpośrednio z przypadkowych pól widgetów. Najpierw wyświetla immutable `ExportManifest`.

| Sekcja Gate | Zawartość |
|---|---|
| Destination | Nazwa playlisty i ścieżka XML. |
| Will write | Track identity, final order i finalne hot cues z provenance. |
| Never touched | Audio, BPM i beatgrid. Ten invariant pozostaje niekonfigurowalny. |
| Blockers | Brak pliku, nierozpoznana identity, nierozwiązany conflict cue albo jawnie wymagany seam verdict. |
| Warnings | Unreliable grid, DSP fallback, nieodsłuchany rekomendowany seam lub brak deep tier. |
| Deep links | Kliknięcie problemu otwiera dokładny track albo seam i zamyka modal bez utraty manifestu. |
| Write XML | Zapisuje dokładnie manifest, który użytkownik widział. |

## 5. Mapa modułów kodu do docelowego hosta

| Obecny moduł | Docelowa rola | Działanie migracyjne |
|---|---|---|
| `host/simple_mode.py` | Tymczasowy facade starego hosta | Rozbić odpowiedzialności; nie przenosić całego pliku do nowej klasy. |
| `host/project.py` | Persistence dla `ProjectSession` | Wersja formatu 2; reader v1 mapuje `current_step` na selection/readiness. |
| `_AnalysisThread` z `simple_mode.py` | Background Job Coordinator | Wydzielić do headless job service z sygnałami stanu. |
| `host/import_dialogs.py` | LIBRARY import/review | Reużyć, zmienić właściciela z page na workspace. |
| `host/analyzed_library.py` | Library table + drawer model | Zachować filtrację i constraints; dodać selection signal i gęsty row delegate. |
| `host/energy_timeline.py` | SET terrain + persistent dock | Zachować prawdziwą skalę; dodać seam selection oraz później reorder. |
| `host/mixability_map.py` | Candidate map | Zachować ranking i EdgeDecision; osadzić jako panel SET. |
| `host/pair_review.py` | SEAM workspace i część TRACK | Reużyć waveform, decks, preview, stems i simulation. |
| `host/transition_simulation.py` | Preview renderer | Bez zmian algorytmicznych. |
| `decision/set_builder.py` | `grow_set()` runtime | Owinąć snapshotem brief/library i rewizją planu. |
| `decision/*` | Engine decisions | Bez zmian wynikających wyłącznie z migracji UI. |
| `validation/transition_edits.py` | R&D ground truth | Zachować; produkcyjne user edits najpierw trafiają do `CueDecisionStore`, a potem mogą być mirrorowane do CSV. |
| `export/rekordbox.py` | Final writer | Przyjmować zatwierdzony manifest/cue decisions zamiast samodzielnie odtwarzać intencję UI. |

### Proponowane nowe moduły

| Moduł | Odpowiedzialność |
|---|---|
| `host/terrain/main_window.py` | Shell, workspace tabs, project bar i modal Gate. |
| `host/terrain/session.py` | `ProjectSession`, selection, revisions i sygnały. |
| `host/terrain/jobs.py` | Quick/deep job lifecycle, queue, stop i status. |
| `host/terrain/library_workspace.py` | Import, crate drawer i library table. |
| `host/terrain/set_workspace.py` | Brief, terrain, candidate map i slot inspector. |
| `host/terrain/seam_workspace.py` | Adapter istniejącego Transition Review do sesji. |
| `host/terrain/track_workspace.py` | Inspector pojedynczego tracka. |
| `host/terrain/export_gate.py` | Manifest diff, blockers, warnings i write. |
| `host/terrain/cue_store.py` | Wersjonowany `CueDecisionStore`. |
| `host/terrain/export_manifest.py` | Czysty, testowalny builder manifestu. |
| `host/terrain/theme.py` | Tokeny TERRAIN i generowanie QSS bez kopiowania wartości po plikach. |

## 6. Dodatkowe funkcje obecnego produktu wymagające decyzji

To nie są funkcje do usunięcia. Nie zostały jasno rozstrzygnięte w concept TERRAIN, dlatego potrzebują jawnego miejsca i akceptacji.

| Funkcja dodatkowa | Moja inicjatywa w TERRAIN | Rekomendacja | Wymaga decyzji |
|---|---|---|---|
| Save / Save As / Open / Recent / Recovery | Zostawić standardowe menu `File`; top bar pokazuje tylko autosave status. | Zachować. Desktopowa aplikacja powinna mieć kontrolowany plik projektu. | Czy przycisk Save ma być całkowicie niewidoczny poza menu? |
| Suspicious duration preflight | Jedna import review sheet z listą <2 min i >10 min. | Zachować. Chroni czas, cache i użytkownika. | Czy progi pozostają 2/10 min jako default? |
| Blind rating 1-5 | Osobny `Validation Mode` uruchamiany z menu View/Developer. | Zachować poza codziennym flow. | Czy ma być dostępny testerom w publicznym buildzie? |
| Spearman/Kendall i raporty | Panel R&D/Validation, nie Project Bar. | Zachować jako narzędzie kalibracji. | Kto ma widzieć wyniki? |
| Validation CSV i exact pair edits | Mirror z produkcyjnego cue/seam store do datasetu badawczego. | Zachować po wersjonowaniu schematu. | Czy eksport datasetu ma wymagać zgody użytkownika? |
| Stop After Current Track | Job Center z akcją przy aktywnym jobie. | Zachować. | Brak, jeśli copy zostanie zaakceptowane. |
| Deep Analysis / Demucs | `Deep analyze set` w SET oraz `Deep analyze track` w TRACK. | Zachować jako jawny kosztowny job. | Czy auto-deep może istnieć jako opcja projektu? |
| Stem export | Context action w TRACK lub po zaznaczeniu wielu tracków w LIBRARY. | Nie umieszczać w głównym briefie/Gate playlisty. | Czy jest funkcją produktu v1 TERRAIN? |
| History / variation / seed | Zwinąć w `Regrow options`. | Zachować jako Advanced. | Czy seed ma być widoczny użytkownikowi, czy tylko `More variation`? |
| Artist diversity | Badge powodu wyboru i warning przy awaryjnym powtórzeniu. | Zachować automatycznie, bez nowego suwaka. | Czy użytkownik może wyłączyć tę regułę? |
| Imported Rekordbox cues | Pokazać provenance w TRACK/SEAM i scalić dopiero przez cue policy. | Zachować, ale nie deklarować merge przed roundtrip testem. | Polityka conflict: imported, engine czy user wins? |
| Cache/storage | Popover z lokalizacją, rozmiarem, estimate i clear selected tiers. | Zachować w Job Center/Settings. | Czy użytkownik może zmienić root cache z UI? |
| Mixability map | `Candidate map`: X=BPM, Y=relative energy, kolor=key. | Zachować obecny, bardziej informacyjny model i poprawić opis. | Czy product design wymaga dosłownie osi BPM x key z mocka? |
| Safe BPM/grid XML | Stała sekcja `Never touched` w Gate. | Zachować jako twardy invariant. | Nie rekomenduję opcji wyłączenia. |

## 7. Inicjatywy integracyjne wynikające z TERRAIN

### 7.1 Plan revision zamiast ukrytego resetu

Każdy plan otrzymuje:

- `plan_revision_id`;
- snapshot briefu;
- snapshot track IDs dostępnych przy generacji;
- timestamp;
- status `fresh`, `stale`, `partial` albo `invalid`.

Dodanie utworów lub zmiana briefu nie kasuje planu. UI pokazuje wpływ i oferuje jawny `Regrow`.

### 7.2 Selection bridge

Zaznaczenie tracka albo seamu jest wspólne:

- track kliknięty w LIBRARY zostaje zaznaczony na mapie i w docku;
- dot kliknięty w SET otwiera jego inspector;
- joint kliknięty w docku ustawia `selected_seam` i otwiera SEAM;
- deep link z Gate ustawia dokładnie ten sam selection state.

### 7.3 Job Center

Initial Check nie znika; przestaje być stroną. Job Center pokazuje prawdę runtime'u:

- queued/running/cached/done/failed;
- aktualny stage;
- ukończone i pozostałe tracki;
- estymację opartą na historii lokalnej, jeśli istnieje;
- `Stop after current`;
- retry dla pojedynczego tracka;
- disk/cache warning.

### 7.4 CueDecisionStore

Jeden track może mieć wiele propozycji cue, ale tylko jedną finalną decyzję dla danej roli i wersji projektu.

| Pole decyzji | Przykład |
|---|---|
| Track identity | Stabilny `track_id` + source fingerprint. |
| Role | `mix_in`, `mix_out`, `drop`, `break`, `memory`. |
| Position | Sekundy + beat index, jeśli grid reliable. |
| Source | `engine`, `rekordbox_import`, `user`. |
| Confidence | Wartość i przyczyna. |
| Quantize | `8-beat`, `beat-only`, `none` wraz z powodem. |
| Status | candidate, accepted, rejected, conflict. |
| Revision | Wersja analizy i planu, na której powstała decyzja. |

Domyślna rekomendacja: jawna korekta użytkownika ma najwyższy priorytet, ale konflikt z imported cue nie jest po cichu usuwany; Gate pokazuje diff.

### 7.5 Semantic Seam Review

Rating badawczy i decyzja produktowa pozostają rozdzielone:

| Stan produktowy | Znaczenie |
|---|---|
| `Keep` | Przejście zaakceptowane bez specjalnej strategii. |
| `Keep with strategy` | Akceptowane z profilem i notatką wykonawczą. |
| `Skip` | Para nie powinna trafić do finalnej sekwencji. |
| `Needs listen` | Wymaga odsłuchu przed spełnieniem polityki Gate. |

## 8. Kolejność wdrożenia

### Faza 0: zabezpieczenie kontraktów

1. Dodać characterization tests aktywnego flow bez zmian UI.
2. Wprowadzić `CueDecisionStore` w trybie shadow; wynik XML na początku ma pozostać identyczny.
3. Wprowadzić czysty `ExportManifest` i testy blockers/warnings.
4. Dodać roundtrip: imported cue -> user move -> save -> reopen -> manifest -> XML.

**Warunek wyjścia:** review i eksport odwołują się do tego samego źródła decyzji cue.

### Faza 1: ProjectSession i shell TERRAIN

1. Wydzielić `ProjectSession` ze stanu `SimpleModeWindow`.
2. Dodać nowy `TerrainMainWindow`, project bar i zakładki.
3. Zachować stare strony jako tymczasowe adaptery wewnątrz workspace'ów tylko do czasu migracji komponentów.
4. Usunąć z nowego hosta step list, numerację, `Next/Back` i `_step_ready()`.

**Warunek wyjścia:** można swobodnie przełączać LIBRARY/SET/SEAM/TRACK bez zmiany danych i bez crashu aktywnego jobu.

### Faza 2: LIBRARY i background analysis

1. Osadzić import i analyzed library w LIBRARY.
2. Wydzielić job coordinator.
3. Uruchamiać brakujący Initial Check po zaakceptowanym imporcie.
4. Dodać Job Center oraz niedestrukcyjne dodawanie tracków podczas istnienia planu.

**Warunek wyjścia:** użytkownik może dodać folder w SEAM, wrócić do review i nie utracić planu ani playback contextu.

### Faza 3: SET i revisions

1. Osadzić brief, energy timeline i mixability map w jednym workspace.
2. Zapisać plan revision/snapshot.
3. Zaimplementować stale state i jawny Regrow.
4. Dopiero później dodać live partial growth, replacement i reorder z undo.

**Warunek wyjścia:** wszystkie obecne constraints dają ten sam plan co przed migracją przy tym samym seedzie i danych.

### Faza 4: SEAM i TRACK

1. Osadzić `TransitionReviewWidget` bez zmiany audio runtime'u.
2. Dodać wspólny terrain dock i selection bridge.
3. Dodać semantic verdicts.
4. Podłączyć cue edits do `CueDecisionStore`.
5. Zbudować TRACK jako inspector istniejących analiz.

**Warunek wyjścia:** cue przesunięty w SEAM jest widoczny w TRACK, projekcie po ponownym otwarciu i ExportManifest.

### Faza 5: EXPORT GATE

1. Zastąpić stronę Export modalem Gate.
2. Pokazać will write / never touched / blockers / warnings.
3. Dodać deep links do tracków i seamów.
4. Zapisać wyłącznie zatwierdzony manifest.

**Warunek wyjścia:** XML zachowuje kolejność i final cues, nie zapisuje BPM/gridu oraz przechodzi roundtrip integration tests.

## 9. Elementy starego UI do wygaszenia

Po przejściu testów nowego shellu można usunąć z aktywnej ścieżki:

- welcome screen `Create a DJ set from your tracks in 5 guided steps`;
- lewy `step_list`;
- `QStackedWidget` traktowany jako kolejność procesu;
- przyciski `Back` i `Next`;
- `_step_ready()` jako mechanizm nawigacji;
- checkmarki ukończenia kroków;
- `current_step` z nowego formatu projektu;
- status `Simple Mode` w project barze;
- osobną stronę Initial Check;
- osobną stronę Export.

Reader projektu v1 musi nadal rozumieć `current_step`, ale mapuje go tylko na początkowy workspace/selection podczas migracji.

## 10. Kryteria akceptacji całej migracji

1. Ten sam zestaw danych i seed daje ten sam plan przed i po migracji.
2. Przełączanie workspace'ów nigdy nie kasuje biblioteki, planu, cue, verdictu ani jobu.
3. Użytkownik może dodać pliki z każdego workspace'u.
4. Existing set nie zmienia się po samym dodaniu lub przeanalizowaniu nowych utworów.
5. Zmiana briefu nie kasuje planu; pokazuje stale state i jawny Regrow.
6. Quick/deep analysis działa w tle i może zostać zatrzymane po bieżącym tracku.
7. SEAM używa dokładnych track IDs i tego samego source path co LIBRARY/SET.
8. User cue correction przechodzi przez save/reopen do finalnego manifestu i XML.
9. Rekordbox XML nie zapisuje BPM ani beatgridu.
10. Gate pokazuje dokładnie to, co writer zapisze.
11. Standardowe project open/save/recovery nadal działa.
12. Pełny regression suite przechodzi bez przepisywania modeli decyzji.

## 11. Najbliższy krok wykonawczy

Nie należy zaczynać od przerysowania QSS ani kopiowania HTML TERRAIN do Qt. Pierwszy commit powinien dostarczyć:

1. `ProjectSession` z selection i plan revision;
2. `CueDecisionStore` w trybie shadow;
3. `ExportManifest` w trybie read-only;
4. characterization tests aktywnego Simple Mode;
5. pusty `TerrainMainWindow` z przełączalnymi workspace'ami, pod feature flagą.

Dopiero na tym fundamencie można bezpiecznie przenosić istniejące widgety i usuwać instalacyjny wizard.
