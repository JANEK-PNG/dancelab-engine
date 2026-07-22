# DanceLab Pro: audyt pokrycia designu przez kod

**Data audytu:** 2026-07-15  
**Zakres:** aktywny Simple Mode, silnik, review, projekt/cache i eksport Rekordbox  
**Poza zakresem:** rozwijanie dawnego Graph Mode

## 1. Material wejściowy i metoda

Przeanalizowane źródła projektowe:

- `Design system for DanceLab.zip`
  - `DanceLab Design System.dc.html` - warianty komponentowe oraz wcześniejszy model krokowy.
  - `DanceLab Pro Concept.dc.html` - docelowa koncepcja `TERRAIN`: `DROP -> BRIEF -> GROW -> WALK THE SEAMS -> GATE`.
  - `DanceLab Pro Concept-print-j4jvpm.dc.html` - wersja przeznaczona do wydruku; funkcjonalnie powiela concept.
  - źródłowe zrzuty ekranu i skrypt interaktywnego prototypu.
- `Design system for DanceLab.pdf`
  - dwie strony; pierwsza jest rastrowym podglądem planszy, druga jest pusta.
  - PDF jest materiałem wizualnym, nie samodzielną specyfikacją zachowania.

Przeanalizowany kod:

- aktywny host Qt i projekt: `src/dancelab/host/`;
- silnik decyzji: `src/dancelab/decision/`;
- eksport Rekordbox: `src/dancelab/export/rekordbox.py`;
- separacja i eksport stemów: `src/dancelab/stems/`;
- cache, walidacja, API i testy integracyjne.

Metoda klasyfikacji:

| Status | Znaczenie |
|---|---|
| `E2E` | Funkcja istnieje w UI, prowadzi do prawdziwego runtime'u i ma test lub bezpośrednio zweryfikowaną ścieżkę. |
| `PARTIAL` | Istnieje znacząca część funkcji, ale brakuje zachowania, stanu albo połączenia opisanego w designie. |
| `ENGINE-ONLY` | Silnik/runtime istnieje, lecz docelowe UI go nie ujawnia albo nie domyka. |
| `DESIGN-ONLY` | Funkcja występuje wyłącznie w makiecie lub jej skrypcie demonstracyjnym. |
| `CONFLICT` | Design składa obietnicę sprzeczną z aktywnym kodem albo sam jest wewnętrznie niespójny. |

## 2. Werdykt bez upiększania

DanceLab ma już znacznie więcej prawdziwej logiki produktu, niż sugeruje obecny interfejs. Import, szybka i głęboka analiza, budowanie sekwencji, ograniczenia DJ-skie, waveform, odsłuch A/B, 8-beat quantize, 24-bitowy render przejścia, walidacja oraz bezpieczny eksport playlisty i hot cues są realnymi ścieżkami kodu.

Nie jest natomiast zaimplementowany nowy model produktu `TERRAIN`. Aktywna aplikacja pozostaje pięciostopniowym wizardem Qt. Największa luka nie znajduje się w algorytmach audio, lecz w warstwie sesji produktu: wspólnym stanie biblioteki, setu, seamów, korekt użytkownika i eksportu.

Najważniejszy problem kontraktowy: korekty hot cue i regionów przejścia wykonane na waveformie są zapisywane do CSV walidacyjnego i przywracane w review, ale nie są źródłem danych dla eksportu Rekordbox. Eksporter ponownie wylicza cues z okien silnika. Design pokazuje odwrotną obietnicę.

## 3. Mapa modułów designu do kodu

| Moduł designu | Aktywny UI | Runtime / kod źródłowy | Pokrycie | Najważniejsza różnica |
|---|---|---|---|---|
| Shell projektu | Pasek projektu, status silnika/cache/zapisu, menu File | `host/simple_mode.py`, `host/project.py` | `E2E` | Design TERRAIN usuwa jawny Save; kod ma Save, Save As, Open, Recent i Recover Autosave. |
| `J1 DROP` - import audio | Wybór plików, jednego lub wielu folderów, usuwanie pozycji | `host/simple_mode.py`, `host/import_dialogs.py`, `ingestion/preflight.py` | `E2E` | Brak drop-zone działającego w dowolnym miejscu aplikacji. |
| Import Rekordbox | Import urządzenia/USB wraz z cues | `ingestion/rekordbox_device.py`, `SimpleModeWindow.import_rekordbox_usb()` | `PARTIAL` | Nie jest to ogólny drag-and-drop dowolnego Rekordbox XML z designu. |
| Ochrona przed sample/setem | Modal dla plików <2 min lub >10 min | `ingestion/preflight.py`, `host/import_dialogs.py` | `E2E` | To wartościowa funkcja kodu, której concept TERRAIN prawie nie eksponuje. |
| Automatyczna analiza po dropie | Brak; użytkownik przechodzi do kroku 2 i uruchamia Initial Check | `_AnalysisThread`, `run_analysis()` | `DESIGN-ONLY` | Design obiecuje analizę w tle bez bram; obecny workflow jest bramkowany. |
| Etapy i postęp analizy | Pasek postępu, prawdziwy stage per track, stop po bieżącym utworze | `_AnalysisThread`, pipeline stage callbacks, cache manager | `PARTIAL` | Brakuje stale widocznej kolejki biblioteki z per-track ETA wyliczanym jak w designie. |
| Initial Check | Osobny krok 2; BPM, key, energy, style, windows; cache reuse | `SimpleModeWindow.run_analysis()` | `E2E` | Działa, ale nowy design chce wchłonąć ten krok do biblioteki i badge'y. |
| Analyzed Library | Tabela, wyszukiwanie, BPM/key/style, reliable-grid, sortowanie | `host/analyzed_library.py` | `E2E` | Design używa wysuwanego crate drawer, a nie osobnej strony wyników. |
| `J2 BRIEF` - długość | Liczba tracków albo czas setu | `SimpleModeWindow._build_generate_page()` | `E2E` | Funkcjonalnie zgodne. |
| `J2 BRIEF` - intencja | Style, BPM min/max, rola setu, crowd energy, arc, planner, variation, seed | `host/simple_mode.py`, `decision/library_profile.py` | `E2E` | Design upraszcza część opcji; obecny kod ma więcej jawnych parametrów. |
| Presety briefu | Custom, Calm UK/Bass, Warm-up deep/soft | `SET_BRIEF_PRESETS` | `E2E` | Design pokazuje intencję, ale nie definiuje kompletnego kontraktu presetów. |
| `J3 GROW` - zbudowanie setu | Jeden przycisk Generate Set, wynik po zakończeniu | `decision/set_builder.py`, `decision/sequence.py`, `decision/rules.py` | `PARTIAL` | Silnik działa, lecz brak animowanego/live wypełniania slotów i częściowego setu. |
| Powody wyboru/rejekcji | Ostrzeżenia i score istnieją w modelach; ograniczone w głównym widoku | `EdgeDecision`, `SetTransition`, guardrails | `ENGINE-ONLY` | Brak pełnego live logu oraz panelu kandydatów zastępczych dla każdego slotu. |
| Energy terrain | Klikalna dyskretna linia energii z peak i jakością przejść | `host/energy_timeline.py` | `PARTIAL` | Brak stałego docka, drag-reorder i live re-score; kod celowo nie tworzy sztucznej sinusoidy. |
| Mixability map | BPM na osi X, relative energy na osi Y, Camelot jako kolor, ranking po kliknięciu | `host/mixability_map.py`, `decision/next_track.py`, `decision/edge_decision.py` | `PARTIAL` | Design opisuje/rysuje BPM i key jako osie. To inny model wizualny. |
| Must Have | Akcja w bibliotece i przy sekwencji | constraints w `set_builder.py` | `E2E` | Zgodne znaczeniowo. |
| Not Tonight / Rest | Akcja wykluczająca track | constraints w `set_builder.py` | `E2E` | Zgodne znaczeniowo. |
| Lock slot | Blokada utworu na konkretnej pozycji | `locked_positions`, `build_set()` | `E2E` | Zgodne znaczeniowo. |
| Historia i variation | Seed, novelty mode, historia poprzednich playlist | `decision/history.py`, `HistoryStore`, `build_set()` | `E2E` | To jest bardziej rozwinięte w kodzie niż w makiecie. |
| Różnorodność artystów | Unikanie tych samych artystów, ostrzeżenia, awaryjne rozluźnienie | `decision/set_builder.py` | `ENGINE-ONLY` | Design nie komunikuje tej ważnej reguły. |
| Deep Analysis | Na żądanie tylko dla utworów z wygenerowanego setu, Demucs, cache, stop | `run_deep_upgrade()`, `preprocessing/stems.py` | `E2E` | Design sugeruje analizę background-first; kod uruchamia ją jawnie po generacji. |
| `J4 WALK THE SEAMS` - lista przejść | Osobny krok 4 z dokładnymi parami track ID | `SimpleModeWindow._populate_review()` | `E2E` | Brak stałego dolnego terrain docka. |
| Prawdziwy waveform | Streaming źródła audio, cache peak/low/mid/high, zoom, pan, seek | `host/waveform_cache.py`, `pair_review.StructureStrip` | `E2E` | To nie jest syntetyczny waveform z prototypu; implementacja jest bardziej prawdziwa niż mock designu. |
| Edycja regionu przejścia | Drag regionu, 8-beat snap przy wiarygodnym gridzie | `StructureStrip`, `preview_timing.py` | `E2E` dla review | Korekta nie trafia do eksportu XML. |
| Edycja hot cues | Drag markerów, zapis i przywracanie per dokładna para/track | `validation/transition_edits.py`, `_record_transition_annotation()` | `PARTIAL` | Działa jako dane testowe; nie ma wspólnego modelu cue używanego przez eksport. |
| Beat sync preview | Incoming follow outgoing; half/double-time aware; clamp | `pair_review.beat_sync_rate()` | `E2E` | Poprawnie ograniczone do odsłuchu aplikacji; nie jest eksportowane do Rekordbox. |
| Quantize | Domyślnie siatka co 8 beatów, tylko dla wiarygodnego gridu | `preview_timing.py`, `pair_review.py` | `E2E` | Zgodne z aktualnym kontraktem bezpieczeństwa. |
| Loop 8 Beats | Brak osobnego kontrolera loop | brak | `DESIGN-ONLY` | Design System pokazuje przycisk, runtime nie ma tej funkcji. |
| Profile przejścia | Linear baseline, balanced blend, bass swap, tops swap, contour blend; długość 32-256 beats | `host/transition_simulation.py`, `TransitionReviewWidget` | `E2E` | Profile są szablonami odsłuchowymi, nie prawdą DJ-validated. |
| 24-bit transition render | Stereo PCM 24-bit, sample-level render, phrase duration/runway guards | `render_transition_preview()` | `E2E` | Render jest tymczasowym preview WAV; nie jest instrukcją zapisywaną do Rekordbox XML. |
| EQ/fadery na symulacji | Wizualizacja obwiedni low/mid/high i faderów A/B | `TransitionSimulationView` | `E2E` | Obecnie wizualizacja, nie ręczny edytor wszystkich knotów. |
| Stem audition | Demucs 4-stem albo jawnie opisany fallback DSP | `pair_review.render_preview_stems()` | `E2E` | Nie myli fallbacku z prawdziwą separacją Demucs. |
| Verdict seam | Rating 1-5, blind review i komentarz | validation UI/CSV | `PARTIAL` | Brak semantycznych akcji Keep / Keep with strategy / Skip / Needs listen z designu. |
| Walidacja użytkownika | CSV, korelacja Spearmana i Kendall tau | `validation/dj_decision_metrics.py` | `E2E` | To funkcja ponad zakresem conceptu, bardzo przydatna dla R&D. |
| `J5 GATE` - XML | Nazwa playlisty, ścieżka, zapis XML, kolejność i hot cues | `host/simple_mode.py`, `export/rekordbox.py` | `E2E` | Jest stroną wizardu, nie modalnym diff/gate. |
| Bezpieczny BPM/grid export | Domyślnie brak `AverageBpm` i `TEMPO`; Rekordbox analizuje grid | `build_rekordbox_xml(..., export_beatgrid=False)` | `E2E` | To świadoma i przetestowana ochrona przed wcześniejszym błędem wspólnego BPM. |
| Export blockers i deep links | Brak listy blokad i przejścia bezpośrednio do problematycznego seam/track | brak wspólnego gate modelu | `DESIGN-ONLY` | Przycisk eksportuje po podstawowym sprawdzeniu obecności planu. |
| Merge existing cues | Importowane cues są widoczne w review | `device_cues` w projekcie i deckach | `CONFLICT` | Eksporter nie scala ich z generowanymi cue. |
| Memory cues / MyTag | Brak | brak | `DESIGN-ONLY` | Makieta pokazuje je jako `WILL WRITE`, co dziś byłoby nieprawdziwe. |
| Cache/storage | Zewnętrzny cache, szacunek miejsca, low-disk guard, status w top bar | `storage/cache_manager.py`, Simple Mode | `PARTIAL` | Brak pełnego panelu zarządzania cache z docelowego design systemu. |
| SET/SEAM/TRACK zoom | Brak; osobne strony i widoki | brak kontrolera poziomów | `DESIGN-ONLY` | To największa zmiana architektury UI w concept TERRAIN. |

## 3A. Pokrycie systemu wizualnego

Materiały nie definiują jednego kierunku wizualnego. `DanceLab Design System.dc.html` jest chłodny, granatowo-cyanowy i zbliżony do aktualnego Simple Mode. `DanceLab Pro Concept.dc.html` zastępuje go ciepłym grafitem, typografią Space Grotesk/IBM Plex/JetBrains Mono i akcentem volt. Przed wdrożeniem trzeba wskazać concept TERRAIN jako nadrzędny albo pozostawić obecne tokeny; mieszanie obu da trzeci, przypadkowy system.

| Warstwa UI | Design System / TERRAIN | Aktywny kod Qt | Pokrycie | Wniosek |
|---|---|---|---|---|
| Paleta bazowa | Starszy system: deep navy + cyan; TERRAIN: `#131110` warm graphite + volt | `#05070B`, `#0B0F14`, `#5CC8FF` | `PARTIAL` | Obecny wygląd realizuje starszy kierunek, nie nowszy TERRAIN. |
| Kolory statusów | Green complete, amber review, red danger, neutral locked | QSS ma osobne stany `complete`, `review`, `danger`, `running`, `ready` | `E2E` | Semantyka statusów jest poprawnie rozdzielona. |
| Typografia | TERRAIN: Space Grotesk headings, IBM Plex Sans body, JetBrains Mono data | SF Pro Text -> Inter -> IBM Plex -> system fallback; brak osobnej mono/data role | `PARTIAL` | Hierarchia istnieje, ale nie odpowiada typograficznemu charakterowi conceptu. |
| Tokeny | Jawne role kolorów, odstępów, radiusów, type scale | Jeden duży string QSS z powtarzanymi wartościami | `PARTIAL` | Wartości są spójne lokalnie, lecz nie stanowią wymiennego token layer. |
| App shell | TERRAIN jako ciągła przestrzeń z crate drawer i bottom dock | Sidebar stepper + project bar + stacked pages | `CONFLICT` | To różnica architektury, nie kosmetyki. |
| Hierarchia działań | Jeden volt primary action | Role `hero`, `secondary`, `quiet`, `danger`; zwykle jeden hero per step | `E2E` | Dobry fundament można zachować. |
| Cards/panele | Niskokontrastowe, spokojne powierzchnie z subtelnym obramowaniem | `card`, `context_panel`, `metric_card`, `control_tile` | `E2E` | Język komponentów istnieje, choć radiusy 2/10/12/16 są niejednolite. |
| Formularze | Brief jako kompaktowy inspector obok danych | Rozbudowany formularz w osobnym kroku | `PARTIAL` | Komponenty działają, lecz zajmują główną przestrzeń zamiast być panelem kontekstowym. |
| Progress/runtime | Per-track status, stage, ETA i worker provenance | Global progress + prawdziwy stage per row + worker count; brak stabilnego ETA per track | `PARTIAL` | Dane runtime są uczciwe, prezentacja nie osiąga poziomu conceptu. |
| Library rows | Gęsty drawer z metadanymi, stripem i job status | Pełna tabela po analizie oraz lista statusowa w trakcie | `PARTIAL` | Te dwa obecne widoki trzeba scalić, nie pisać analizera od nowa. |
| Waveform | Główny, gęsty instrument z strukturą, cues i regionem miksu | Prawdziwy custom-painted waveform z zoom/pan/edit | `E2E` | Najbliższy docelowemu poziomowi wizualno-funkcjonalnemu. |
| Data visualization | Energy terrain, quality bars, mix map, tooltips i selection state | Energy timeline i mix map z realnych danych | `PARTIAL` | Dane są prawdziwe; brak wspólnej skali/interakcji oraz zgodności osi mix mapy. |
| Ikony | Spójny zestaw symboli i skrótów | Głównie tekst, Unicode `check`, `play`, strzałki i standardowe kontrolki Qt | `PARTIAL` | Funkcjonalne, ale nie tworzą systemu ikon. |
| Motion | Live growth, płynne przejścia poziomów, feedback runtime | Standardowe zmiany widgetów; animowany playhead preview | `PARTIAL` | Motion istnieje tylko tam, gdzie niesie sygnał audio. |
| Responsywność | Adaptacyjny układ paneli; concept boards same są projektowane na 1440x900 | `_sync_responsive_layout()` głównie dla Generate; pozostałe strony mają stałe założenia | `PARTIAL` | Nie ma jeszcze aplikacyjnej strategii compact/regular/wide. |
| Keyboard | Design podaje B/P/A/S/R/L oraz Cmd +/- | Standardowa nawigacja Qt, brak pełnej mapy komend TERRAIN | `DESIGN-ONLY` | Skróty wymagają command registry i kontroli konfliktów z edycją tekstu. |
| Accessibility | Czytelny status nieoparty wyłącznie na kolorze, duże targets, focus | Tekst statusów istnieje, focus częściowo systemowy; brak audytu kontrastu i screen reader names | `PARTIAL` | Potrzebny osobny accessibility pass po ustaleniu finalnego shellu. |

## 4. Funkcjonalności pokryte kod + UI

| Funkcjonalność użytkowa | Dowód implementacyjny | Dowód testowy | Ocena |
|---|---|---|---|
| Nowy/otwórz/zapisz/zapisz jako/recent/recovery | `SimpleModeWindow` i `.dlproj` | `test_host_project.py`, testy roundtrip/autosave Simple Mode | Gotowe |
| Wiele folderów oraz plików audio | `choose_audio_directories()` i import page | `test_import_clear_and_remove_selected` | Gotowe |
| Ochrona przed przypadkowym samplem lub nagranym setem | duration preflight i modal | `test_import_preflight.py` | Gotowe |
| Initial Check z prawdziwymi etapami | `_AnalysisThread.stage`, pipeline callbacks | `test_simple_mode_wizard_end_to_end` | Gotowe |
| Wznawianie z cache po zatrzymaniu | cooperative stop i tier manifest | `test_stop_processing_saves_progress_and_new_selection_works` | Gotowe |
| Biblioteka po analizie | `AnalyzedLibraryWidget` | test filtrów, sortowania i constraints | Gotowe |
| Brief: liczba/czas/style/BPM/rola/energia | Generate page + `LibraryProfile` | test calm UK/Bass brief | Gotowe |
| Budowa sekwencji z łukiem i guardrails | `build_set()`, `recommend_sequence()`, `rules.py` | zestaw testów set builder/sequence/rules | Gotowe |
| Pin, exact lock i Not Tonight | planner constraints | `test_dj_control_pin_lock_rest` | Gotowe |
| Różnorodność artystów i historia setów | `set_builder.py`, `history.py` | testy set builder/history/variation | Gotowe w silniku |
| Energy timeline na realnych wynikach | `EnergyTimelineCanvas` | `test_energy_timeline_preserves_plan_order_and_library_scale` | Gotowe, interakcje częściowe |
| Ranking Find Next i EdgeDecision na mapie | `MixabilityMapWidget` | `test_mixability_map_uses_engine_ranking_and_edge_decisions` | Gotowe |
| Deep-on-demand z Demucs dla wybranego setu | `run_deep_upgrade()` | `test_deep_on_demand_upgrades_only_set_tracks` | Gotowe |
| Poprawne wiązanie nazwy, track ID i pliku audio | review row -> exact transition IDs; deck czyści stare media | wizard E2E + `test_deck_set_track_clears_previous_player_source` | Gotowe |
| Prawdziwy waveform i cache | `load_or_build_waveform()` | `test_waveform_cache_builds_truthful_peaks_and_reuses_file` | Gotowe |
| Zoom/pan/seek i drag cue/regionu | `StructureStrip` | `test_waveform_drag_selects_quantized_transition_and_moves_hot_cue` | Gotowe w review |
| 8-beat quantize | `preview_timing.py` | testy snap/quantized cue/unreliable grid | Gotowe |
| Half/double-aware beat sync | `beat_sync_rate()` | trzy testy beat-sync | Gotowe |
| 24-bit stereo transition preview | `transition_simulation.py` | sample-accurate, stereo, runway, cache tests | Gotowe |
| M8-M10 tempo plan jako shadow | `tempo_adjustment.py` + review | test zachowania validated preview clock | Gotowe jako shadow, nie tuning aktywny |
| Ocena przejść i zapis feedbacku | rating/annotation CSV | test validation mode i korekt waveformu | Gotowe dla R&D |
| Rekordbox XML bez nadpisania BPM/gridu | `export_beatgrid=False` | eksport schema, grid safety, roundtrip integration | Gotowe |
| Hot cues rozdzielone rolami i w czasie | `track_windows_as_cues()` | phrase snap, clustering, runway tests | Gotowe dla cues wyliczonych przez silnik |

## 5. Backend istnieje, lecz docelowy UI go nie wykorzystuje w pełni

| Możliwość silnika/runtime'u | Obecne użycie | Brak w docelowym przepływie |
|---|---|---|
| Szczegółowy `EdgeDecision` z klasą, strategiami, powodami i ryzykiem | Lista/ranking mapy i opisy przejść | Pełny inspector decyzji i replacement drawer dla slotu. |
| Sekwencyjna pamięć energii, tempa, funkcji i napięcia | Automatycznie w plannerze | Czytelne explanation trail dla każdej pozycji setu. |
| Twarde guardrails ryzyka, BPM driftu i regionu energii | Wpływają na plan i warnings | Export Gate pokazujący każdą blokadę i jej lokalizację. |
| Artist diversity | Automatycznie w builderze | Badge/wyjaśnienie dla użytkownika. |
| Osobny stem export workflow i API | Dostępne headless/legacy runtime | W Simple Mode nie ma użytkowego panelu eksportu wybranych stemów. |
| Headless API/CLI | Testy i integracje | Concept skupia się wyłącznie na desktop UI. |
| Priory DJmix/Raveform i metryki walidacyjne | R&D i scoring | Brak source/confidence provenance w głównym UI. |
| Importowane hot cues z urządzenia | Deck review | Brak jednego cue store łączącego import, korektę, engine cue i finalny XML. |

## 6. Funkcjonalności UI wykraczające poza kod

| Funkcjonalność z designu | Stan faktyczny | Ryzyko, jeśli pokażemy ją dziś użytkownikowi |
|---|---|---|
| Jedna ciągła przestrzeń `TERRAIN` | Nie istnieje | Użytkownik zobaczy zupełnie inną nawigację niż w makiecie. |
| Zoom poziomów LIBRARY/SET/SEAM/TRACK i `Cmd +/-` | Nie istnieje | To wymaga kontrolera stanu/nawigacji, nie samego stylingu. |
| Analiza zawsze w tle, bez bram | Nie istnieje | Obecny krok 2 blokuje dalszy workflow do ukończenia minimum analizy. |
| Live `GROW`: sloty pojawiają się podczas planowania | Nie istnieje | `build_set()` działa synchronicznie i zwraca gotowy plan. |
| Stop here zachowuje częściowy set | Nie istnieje | Planner nie publikuje częściowych wyników do UI. |
| Drag tracka w terrain i live re-score seamów | Nie istnieje | Wymaga mutowalnego planu, re-score oraz historii undo. |
| Panel replacement candidates per slot | Nie istnieje jako spójny element | Map ranking może dostarczyć kandydatów, ale nie podmienia pozycji w planie. |
| Stały terrain dock w Transition Lab | Nie istnieje | Review traci kontekst całego setu. |
| Verdict: Keep / Strategy / Skip / Needs listen | Nie istnieje | Rating 1-5 nie zastępuje stanu dopuszczenia seam do eksportu. |
| Loop 8 Beats | Nie istnieje | Przycisk byłby martwy. |
| Export Gate jako diff z blockerami | Nie istnieje | Aktualny eksport nie potrafi udowodnić kompletności korekt. |
| 38 engine + user hot cues | Liczba z mocka | Faktyczna liczba zależy od planu i windows; user edits nie trafiają do XML. |
| Memory cues na seamach | Nie istnieje | XML nie zapisuje ich. |
| MyTag `DL verified` | Nie istnieje | XML nie zapisuje tagu. |
| Existing cues merged, not replaced | Nie istnieje w eksporcie | Import cues służy review, ale finalny XML buduje nowe cue od zera. |
| Ta sama envelope math w preview i export | Sprzeczne z formatem eksportu | Rekordbox XML eksportuje kolejność/cues, nie EQ/fader automation. |
| Autosave bez Save button | Częściowo istnieje | Kod autosave'uje, ale ma jawne Save/Save As i dirty state. |

## 7. Funkcjonalności kodu wykraczające poza design

| Funkcjonalność kodu | Wartość produktu | Rekomendacja projektowa |
|---|---|---|
| Blind rating i komentarz 1-5 | Pozwala kalibrować model bez anchoringu scorem | Zachować jako Validation Mode, poza głównym flow. |
| Spearman rho i Kendall tau po ocenach | Uczciwa miara zgodności silnika z DJ-em | Pokazywać w panelu R&D, nie w codziennym Simple Mode. |
| CSV korekt waveformu z dokładnym pair/track/deck/beat | Buduje ground truth dla cue i transition windows | Zachować; połączyć z produkcyjnym cue store dopiero po wersjonowaniu schematu. |
| Suspicious-duration preflight | Chroni czas i cache użytkownika | Zachować jako modal przy imporcie. |
| Stop After Current Track z bezpiecznym cache | Chroni przed utratą długiej analizy | Zachować i przenieść do background job drawer. |
| Project Open/Recent/Recovery | Bezpieczna praca desktopowa | Zachować, mimo że concept chce ukryć Save. |
| History-aware variation i seed | Umożliwia kontrolowaną regenerację | Pokazać jako Advanced, zgodnie z obecnym UI. |
| Artist diversity | Rozwiązuje realny błąd playlisty | Dodać krótki badge/reason do terrain, nie nowy parametr. |
| Bezpieczne pomijanie BPM/TEMPO w XML | Chroni Rekordbox przed błędnym wspólnym BPM | Musi pozostać twardym invariantem eksportu. |
| Osobny stem export/API | Przydatne poza budowaniem playlisty | Nie wciskać do głównego flow; osobny action po Deep Analysis. |

## 8. Niespójności wewnątrz samych materiałów projektowych

1. `DanceLab Design System.dc.html` utrzymuje model krokowy, podczas gdy `DanceLab Pro Concept.dc.html` deklaruje jego całkowite usunięcie. Nie można implementować obu shelli naraz bez podwojenia produktu.
2. Concept opisuje mapę jako `BPM x key`. Jego mock pozycjonuje punkty według key i BPM. Aktywny kod używa BPM i relative energy, a key koduje kolorem. To wymaga decyzji produktowej, nie poprawki CSS.
3. Prototyp używa deterministycznie syntetyzowanych waveformów i mock danych. Nie wolno traktować jego wykresów jako dowodu, że dane są już podłączone.
4. Hasło `the same envelope math the export writes` nie pasuje do eksportu Rekordbox XML: XML nie niesie automatyki EQ/faderów.
5. `zero gates` koliduje z uczciwym bezpieczeństwem eksportu. Minimum analiz, identyfikacja tracków i wiarygodność gridu nadal muszą być walidowane; można zamienić blokującą stronę na background state, ale nie usunąć invariantów.
6. `the gate is the app's only file write` jest technicznie nieprawdziwe: aplikacja zapisuje project/autosave, cache, validation CSV, transition edits, preview i stems.

## 9. Krytyczne luki danych i kontraktów

### P0. Brak jednego modelu cue

Obecnie cue występuje w kilku odrębnych światach:

| Źródło cue | Gdzie żyje | Czy trafia do review | Czy trafia do eksportu |
|---|---|---:|---:|
| Transition windows silnika | `AnalysisResult` / recompute | Tak | Tak |
| Importowane Rekordbox hot cues | `device_cues` w projekcie | Tak | Nie |
| Korekty użytkownika na waveformie | validation `transition_edits.csv` | Tak, po restore | Nie |
| Transition cue per para | `decision/transition_cues.py` | Tak, jako wskazówka | Nie bezpośrednio |
| Cues eksportowe | budowane od nowa przez `track_windows_as_cues()` | Nie jako osobny edytowalny model | Tak |

To jest główna przyczyna, dla której design nie może jeszcze uczciwie pokazać `engine + user cues`, `merged` ani export blockers.

### P0. Brak manifestu Export Gate

Eksport przyjmuje plan i analizy, generuje windows, buduje XML i zapisuje plik. Brakuje pośredniego, wersjonowanego manifestu zawierającego:

- dokładną tożsamość każdego pliku/track ID;
- finalną kolejność;
- finalne cues wraz ze źródłem i confidence;
- decyzję o quantize albo świadomym braku quantize;
- verdict seamów;
- listę blockers/warnings;
- diff względem importowanych cues;
- audyt, czego eksport nigdy nie zmienia: BPM, beatgrid i audio.

### P1. Shell UI nie odpowiada nowemu modelowi sesji

Silnik można przenieść pod TERRAIN, ale nie przez przepisywanie algorytmów. Potrzebny jest wspólny `ProjectSession`/view-model, który publikuje library jobs, brief, plan, selected track/seam, reviews, cue store oraz export manifest.

## 10. Rekomendowana kolejność wdrożenia

| Priorytet | Krok | Dlaczego najpierw |
|---|---|---|
| `P0` | Wprowadzić wersjonowany `CueDecisionStore` łączący engine, import i user edits bez zmiany aktualnego XML outputu | Zapobiega dalszemu rozjeżdżaniu review i eksportu. |
| `P0` | Zbudować czysty `ExportManifest` oraz walidator blockers/warnings | Pozwala uczciwie stworzyć `GATE`, zanim powstanie nowy shell. |
| `P0` | Dodać roundtrip test: import cue -> move cue -> save project -> reopen -> export -> assert exact track/cue | Pokrywa najbardziej ryzykowną ścieżkę wskazaną przez użytkownika. |
| `P1` | Wydzielić `ProjectSession`/view-model z `SimpleModeWindow` | Umożliwia zmianę UI bez przepisywania silnika. |
| `P1` | Zbudować library-first shell `DROP + BRIEF + SET` nad istniejącymi widgetami i runtime'em | Daje największy wzrost UX przy najmniejszym ryzyku audio. |
| `P1` | Osadzić istniejący TransitionReviewWidget jako poziom `SEAM` i dodać stały set dock | Wykorzystuje najbardziej dojrzałą część obecnego UI. |
| `P1` | Dodać semantyczny verdict seam i powiązać go z Export Gate | Zamienia rating R&D w decyzję użytkową bez usuwania ratingu. |
| `P2` | Drag reorder + incremental re-score + replacement candidates | Wymaga już stabilnego session modelu i undo. |
| `P2` | SET/SEAM/TRACK zoom i skróty | To warstwa nawigacji, nie fundament danych. |
| `P2` | Memory cues, MyTag i merge policy | Dopiero po potwierdzeniu realnego roundtripu Rekordbox i kontraktu XML. |

## 11. Rzeczy, których nie należy robić

- Nie przepisywać silnika decyzji tylko po to, aby dopasować go do makiety.
- Nie przenosić syntetycznych waveformów ani mock datasets z HTML do aplikacji.
- Nie deklarować `existing cues merged`, dopóki finalny XML nie przechodzi testu roundtrip.
- Nie deklarować, że preview EQ jest eksportowane do Rekordbox.
- Nie aktywować eksportu BPM/beatgridu; bezpieczne `export_beatgrid=False` jest poprawnym invariantem.
- Nie budować live GROW bez możliwości anulowania, częściowego wyniku i deterministycznego re-score.
- Nie usuwać walidacji, cache, recovery i projektu tylko dlatego, że design chce wizualnie ukryć bramy.
- Nie wracać do Graph Mode jako sposobu implementacji TERRAIN; to inny problem produktowy.

## 12. Weryfikacja audytu

Uruchomiono skoncentrowany zestaw testów obejmujący:

- Simple Mode end-to-end;
- projekty, autosave i recovery;
- import preflight;
- waveform cache i korekty;
- beat sync oraz 8-beat quantize;
- transition simulation i 24-bit stereo render;
- Rekordbox XML oraz hot cues;
- analyze -> build -> export roundtrip.

Wynik skoncentrowanego zestawu: wszystkie testy przeszły. Następnie uruchomiono cały regression suite: **428 passed, 1 skipped, 7 warnings**. Ostrzeżenia dotyczą deprecated fallbacku `librosa/audioread` w teście importu oraz krótkich syntetycznych sygnałów `librosa`; nie wskazują błędu funkcjonalnego audytowanych ścieżek.

## 13. Ostateczna ocena gotowości modułów

| Obszar | Gotowość | Wniosek |
|---|---|---|
| Import i ochrona wejścia | Wysoka | Można zachować runtime i przeprojektować shell. |
| Quick/deep analysis i cache | Wysoka | Brakuje głównie background-job UX i ETA. |
| Brief i planowanie | Wysoka w silniku, średnia w prezentacji | Nie przepisywać algorytmów; poprawić explanation i session state. |
| Energy/mixability exploration | Średnia | Dane są realne, ale model interakcji TERRAIN nie istnieje. |
| Transition review | Wysoka | Najbliższy designowi i najlepiej przetestowany moduł produktu. |
| Cue correction -> export | Niska | Krytyczna luka kontraktowa. |
| Rekordbox playlist/hot-cue export | Wysoka dla engine cues | Bezpieczny wobec BPM/gridu, ale bez merge/user edits/gate. |
| Project/cache/recovery | Wysoka | Design powinien je ukryć lub uprościć, nie usuwać. |
| TERRAIN shell | Niska | To nadal concept, nie aktywny UI. |

**Konkluzja:** nie trzeba budować nowego silnika. Trzeba ujednolicić stan projektu, cue i eksportu, a następnie osadzić istniejące, przetestowane moduły w nowym shellu. Bez tej kolejności nowy wygląd będzie tylko atrakcyjną nakładką na nadal rozdzielone źródła prawdy.
