# DanceLab TUI — mapa komponentów silnika na interfejs

Stan: 2026-08-04. Ekran 1 (budowa setu) ZBUDOWANY (`dancelab tui`, `src/dancelab/tui/`).
Ekrany 2–4 zaprojektowane, nie zbudowane. Framework: Textual (czysty Python, ten sam venv,
testy headless przez `run_test()`).

Zasada nadrzędna (ADR-005 jako zasada UI): każde „nie wiem" silnika ma swój piksel —
warnings zawsze widoczne, tonacja o pewności <0,5 przygaszona, stan Rekordboxa w pasku.

## Ekran 1 · BUDOWA SETU ✅
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
| `SetPlan.warnings` + notki dokarmiania | Log #warnings — stały, nigdy zwinięty |
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
