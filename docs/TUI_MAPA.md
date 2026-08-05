# DanceLab TUI — mapa komponentów silnika na interfejs

Stan: 2026-08-05. Układ 2.0 wg TUI_WIZJA_2 (zatwierdzony): ZAKŁADKI
**Biblioteka · Set · Eksport/Cue**, Ctrl+Tab krąży. JĘZYK: interfejs w 100%
po polsku — komunikaty silnika (po angielsku, konwencja kodu) tłumaczy
`tui/po_polsku.py` na granicy UI; nieznany komunikat przechodzi bez zmian. Framework: Textual
(czysty Python, ten sam venv, testy headless przez `run_test()`).

## Zakładka BIBLIOTEKA ✅ (krok a+b+c wizji)
| komponent silnika | widget |
|---|---|
| pula = `_library_analyses` (te same sita higieny co budowa) | DataTable #lib-table: ♥ · F · BPM · ton · pew. · energia · gatunek · min · utwór |
| `filter_library` — podciąg nazwa/gatunek, dokładna tonacja, domknięte okno BPM | Inputy #lib-search #lib-key #lib-bpm, filtr na żywo; zły filtr = powód w liczniku |
| energia RELATYWNA 0-100 w obrębie biblioteki; brak ramek RMS = „—", nie zmyślona | kolumna „energia" |
| `tui/user_store` — ulubione (2 piny: utwory + playlisty) i FILARY (3–10; minimum egzekwuje budowa, nie przełącznik) | klawisze U i F na tabeli (widoczne w stopce); legenda U/F/G na stałe w #lib-count; znaczniki ♥/F; stan w `data/exports/tui_stan.json` |
| G / przycisk: SZKIC w Set (zlote flagi, BEZ budowy - brief zostaje w grze; decyzja Janka 05.08); po G panel TRYBOW FILAROW (auto; drugie F w Secie zawsze; wybor trwaly w stanie): PODPORY = konstrukcja bez filarow -> pomiar przesel tym samym transition_score -> `_wstaw_podpory` w najslabsze (zgodnosc calosci uczciwie brak, konstrukcji w notce) / ROWNY ROZSTAW i RAMA = `_rozstaw_filary` -> `locked_positions` silnika; X na filarze ZDEJMUJE PIN (decyzja Janka; duplikaty przez mape kanoniczna); `_filary_for_build` pomija imiennie filar spoza puli/okna, odmawia przy <3 i przy filarach > miejsc; flagi z ctx.filary takze w gotowym secie | budowa w zakladce Set |
| onboarding: folder → `analyze_files` z postępem etapów | wiersz #lib-folder + przycisk Analizuj |
| sortowanie po kolumnach: cykl `_cycle_sort` (liczby ↓→↑→kasacja, teksty A-Z→Z-A→kasacja; braki ZAWSZE na końcu — brak≠zero); aktywny sort w liczniku | klik w nagłówek #lib-table |
| wykonawca/tytuł OSOBNO: tag z analizy → `attach_rekordbox_meta` (kolekcja RB uzupełnia TYLKO braki) → parsowanie „Artysta - Tytuł" → stem | kolumny 8/9; szukajka patrzy w oba |
| sekcje po lewej (wzór Apple Music): Cała / ♥ Ulubione / ⚑ Filary (+ playlisty wkrótce) | OptionList #lib-side-list, zawsze widoczna; klik zawęża tabelę, nazwa sekcji w liczniku |

## Zakładka EXPORT/CUE — atrapa (krok f wizji: edytor hot cue)

Zasada nadrzędna (ADR-005 jako zasada UI): każde „nie wiem" silnika ma swój piksel —
warnings zawsze widoczne, tonacja o pewności <0,5 przygaszona, stan Rekordboxa w pasku.

## Zakładka SET (dawny Ekran 1 · BUDOWA SETU) ✅
| komponent silnika | widget |
|---|---|
| pula: cache analiz / folder | Select #pool + Input #folder (tryb Folder = `analyze_files` z realnym `stage_progress` i `should_stop` — hooki po Qt, pierwszy konsument od 24.07) |
| `--minutes` → `estimate_track_count_for_duration` | Input #minutes |
| `--bpm lo-hi` | Input #bpm (parser odmawia z powodem) |
| `--gatunki` (tagi Janka z RB, enrichment) | Input #styles |
| kotwice 284 DJ-ów (`dj_anchors.json`) | Select #dj (nazwa · wektory · mediana skoku) |
| kontur skoków | Switch #contour |
| łuk / plan tempa / tryb | Selecty #arc #tempo #planner |
| `SetPlan.track_order` | DataTable: # · BPM · ton · pewność · gatunek · Σ min · utwór |
| `SetPlan.warnings` + notki dokarmiania | Log #warnings — SCHOWANY domyślnie (decyzja Janka 04.08), klawisz L (log) przełącza; licznik notek ZAWSZE w pasku statusu, ODMOWA i wynik zapisu dodatkowo dymkiem (kanał uczciwości przeniesiony, nie usunięty) |
| tonacja z analizy Rekordboxa (`attach_rekordbox_keys`; pomiar 05.08: detektor 47% vs sędzia na 191 utworach) — źródło jawne `key_detection_source=rekordbox`, pewność 1,0 wg konwencji zaufanego źródła; manual DJ-a NIGDY nie nadpisany; cache na dysku zostaje silnikowy (sędzia mierzalny) | kolumna pew. pokazuje „RB”/„ręka” zamiast liczby; karta INFO nazywa źródło |
| P = odsłuch szwu pary: `tui/seam_preview.zbuduj_szew` na maszynerii `preview/transition_simulation` (fraz-lock, krzywe deckowe, varispeed, cache w `data/cache/seam_preview/`); okna+cue+długość z silnika; DŹWIĘK tylko z jawnego P (afplay), drugie P/Esc stop, koniec z aplikacją | klawisz P w zakładce Set |
| karta INFO utworu: metadane silnika + ścieżka + `ingestion.rekordbox_lookup` (BPM wg RB, komentarz, playlisty z master.db — TYLKO odczyt, działa przy otwartym RB; dopasowanie jak w publikatorze: ścieżka NFC, potem jedyny bliźniak po tytule, inaczej „nie ma w kolekcji") | klawisz I — panel po prawej w trybie info; drugie I / Esc zamyka |
| tryby oceny sugestii = `_planner_component_weights` silnika (smart / bpm 0,55 / harmonic 0,55) | Select #suggest-mode w panelu; zmiana przelicza sugestie na żywo; bpm/harmonic bez kotwicy — tryb nazywa to, co ocenia |
| poswiata influence - USUNIETA (pomysl Janka 04.08, jego weto 05.08 po uzyciu: rozprasza, nic nie mowi); notka w kodzie pilnuje pamieci o werdykcie | - |
| BPM i tonacja BOLDEM w obu tabelach (podkladka tla wycofana 06.08 — weto Janka po jasnym motywie; ramki na komorce terminal nie ma) | `_bpm_cell` / `_key_cell` |
| pasek skrotow KONTEKSTOWY per zakladka (`check_action` + `refresh_bindings`) | Footer pokazuje tylko klawisze aktywnej zakladki |
| `ingestion.playlist_publish` (backup→dopasowanie→weryfikacja odczytem) | klawisz W |
| `decision.slot_suggest` — kandydat oceniany W SZCZELINIE (wejście+wyjście, ta sama kotwica co budowa) | klawisz Z → doszyty panel po prawej (42 kolumny); klik propozycji + Z = podmiana |
| `decision.slot_suggest.suggest_for_insertion` — szczelina MIĘDZY utworami, nikt nie wypada | klawisz A (dopisz ZA zaznaczonym) — ten sam panel i wzorzec dwóch naciśnięć co Z |
| edycja setu = werdykty DJ-a (cięcie, przesunięcie, dopisanie, podmiana → `tui_edycje.jsonl`) | X wycina · Shift+↑/↓ przesuwa · każda edycja logowana |
| `tui.plan_store` — plan przeżywa zamknięcie okna; braki w puli pomijane Z NOTKĄ | S zapisuje · O wczytuje (panel listy planów, wzorzec dwóch naciśnięć); O bez wcześniejszej budowy sam wczytuje pulę i kontekst oceniania z parametrów planu |
| werdykt „plan silnika vs stan DJ-a" (`tui_werdykt_*.json`) | klawisz V — zrzut obu kolejności + dziennika edycji |
| stan Rekordboxa + liczba backupów | Static #status, odświeżany co 5 s |
| anulowanie | Esc → `threading.Event` → `should_stop` (Esc najpierw zamyka panel) |

## Ekran 2 · BIBLIOTEKA (projekt)
analizy (sztywna siatka, tonacja+pewność, energia) → tabela z filtrami; frazy RB (1740
utworów, `ingestion/rekordbox_phrases`) → pasek sekcji INTRO▮UP▮DOWN▮CHORUS▮OUTRO;
krzywe stemów (`stems/envelopes`, na żądanie) → klawisz S.

## Ekran 3 · PARA (projekt)
`transition_score` z pełnym uzasadnieniem; okna mix-in/out + `transition_length`
(zapas + frazy) → oś czasu; `preview` (WAV) → klawisz P, odtwarzanie TYLKO na jawny klawisz.

## Ekran 4 · KOTWICE (projekt)
przeglądarka `dj_anchors.json`: n miksów, kwartyle skoków, kontur jako sparkline.

## Werdykty (w toku ręcznie)
zapis „plan silnika vs cięcia DJ-a" → docelowo klawisz V na Ekranie 1
(dziś: `experiments_priv/2026-08-04_werdykty/`).
