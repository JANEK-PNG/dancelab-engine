# CZEGO BRAKUJE

# Krytyka kompletności materiału

Sprawdziłem dysk, żeby nie oceniać z pamięci. Poniżej to, czego w materiale nie ma — z policzonymi rozmiarami dziur.

---

## A. Dziury, które podważają tezę „cały dorobek"

**1. Cała warstwa KODU silnika jest nieobecna — mimo że została przeczytana.**
Materiał deklaruje przy obszarze `dancelab-engine`: „docs/ + PROJECT_LEDGER.md + README.md (kod świadomie pominięty)". Tymczasem własny dziennik pracy tej operacji, `/Users/jantrybus/Developer/dancelab-engine/experiments_priv/2026-08-14_raport_calosc/STAN.md`, mówi: „Silnik 5/12" skończone — przeczytano `decision`, `ingestion`, `features+preproc+stems`, `cli+api+workflows`, `testy`. Wyników tych pięciu agentów **nie ma w materiale, który dostałem**. Padło siedem kolejnych: `tui`, `validation`, `core`, przekrój spójności, przekrój wzoru, kronika z komentarzy, werdykt architekta.
Skala nieopisana: **187 plików `src/`, 100 skryptów `scripts/`, 114 plików testów**. To jest miejsce, gdzie w tym projekcie mieszkają nieudokumentowane decyzje — wszystkie osiem pogłębień znalazło najmocniejsze cytaty właśnie w docstringach skryptów (`artist_graph_crawler.py`, `dj_style_harvester.py`, `pomysly_niewdrozone.py`). To najdroższa dziura.

**2. Nikt nie zauważył, że na dysku są CZTERY dodatkowe klony silnika — i to w nich jest najnowsza praca.**
Materiał zna tylko `dancelab-engine` i `dancelab-mine`. Poza nimi leżą:
- `/Users/jantrybus/Developer/DANCELAB-DEMO` (HEAD `3a23d1a`, 453 commity, ruszany do 13.08 23:58; `Desktop/DANCELAB` to skrót właśnie tutaj)
- `/Users/jantrybus/Developer/dl-github` (HEAD `622cdb2`, 445 commitów — „Ledger: pre-presentation audit, four demo-blockers fixed")
- `/Users/jantrybus/Developer/dl-final` (HEAD `547a191`, 444 commity)
- `/Users/jantrybus/Developer/dl-swieza` (HEAD `ade9449`, 439 commitów, **niezacommitowane zmiany w `src/dancelab/tui/app.py` i `pyproject.toml`** — praca, której nie ma w żadnej historii gita)

Trzy z nich mają cztery różne wersje `PROJECT_LEDGER.md` (304 825 / 307 391 / 309 249 bajtów). Materiał opisuje jedną z nich jako „ledger" i traktuje jak jedyne źródło.

**3. `experiments_priv/` — 24 katalogi surowych wyników, praktycznie nieprzeczytane.**
Materiał cytuje z nich tylko `2026-08-03_dj_mapa` i `2026-08-09_fourtet_awakenings`, i to z drugiej ręki. Tymczasem **każda liczba w ledgerze pochodzi stąd** i żadna nie została zweryfikowana u źródła:
`2026-07-30_rebuild` (8267 plików, 1,3 GB), `2026-07-31_utwor` (5,1 GB), `2026-08-08_apple_mixy` (2966 plików, 200 MB — tu leżą pliki tripletów), `2026-08-09_persony_dj` (609 plików), `2026-08-10_ksztalt_setu`, `2026-08-11_ablacja`, `2026-08-04_werdykty` (jedyne realne werdykty DJ-a), `2026-08-03_pierwszy_set` (cztery kopie master.db).

**4. Korpus jest dziś fizycznie niedostępny — i nikt tego nie sprawdził.**
`/Volumes/MY_PC` **nie jest podpięty**. Wszystkie twierdzenia o korpusie (163 GB, 801 wyrównanych miksów, 23 644 przejścia, 12 668 wektorów CLAP) są w tej chwili nieweryfikowalne. Raport, który się na nich opiera, powinien to mówić wprost.

**5. Transkrypty rozmów — świadomie pominięte, a to jedyne miejsce z własnymi słowami Janka.**
`/Users/jantrybus/.claude/projects` — **361 plików .jsonl, 452 MB** (samo `-Users-jantrybus-Desktop-AI` to 377 MB). `/Users/jantrybus/.codex` — **13 GB, 156 plików `rollout-*.jsonl`**, wykluczonych jedną linijką („Pominięte świadomie: transkrypty rozmów").
Skutek jest widoczny w samym materiale: `ZNALEZISKO_CURVE.md` twierdzi, że „Projekt DJ CURVE" to „jedyne w vaulcie notatki pisane PRZEZ JANKA, pierwszą osobą, na gorąco". To prawda o vaulcie, ale nieprawda o dysku — w transkryptach są setki jego dyktowanych wypowiedzi i cała historia poleceń. Teza „ile tu jest Janka, a ile maszyny" stoi na nieprzeczytanym źródle.

---

## B. Obszary przeczytane pobieżnie

- **Trzy ZIP-y sprintów** (`DanceLab_SPRINT_4_CLOSED_FINAL.zip`, `..._5_1_...`, `..._5_4_...`, razem 9,5 MB / 1682 wpisy) — materiał wprost mówi, że wylistowano je „po nazwach plików, bez rozpakowywania". Cały pakiet pilotażu DJ-skiego (36 dokumentów, 14 szablonów CSV) jest opisany z nazw katalogów.
- **`~/Music`** — nagrania ground truth (`rekordbox/Recording/.../01 Open Deck.wav` 552 MB + `.cue`, `01 Premier.wav` 495 MB + `.cue`) znane tylko z pamięci projektu, nieotwarte. Nietknięte też: `Dj Sets/`, `DanceLab Samples/`, `debYOU/`, `djay/`, `Ableton/` oraz katalogi `LEKCJA nr5`, `Lekcja nr6`, `Lekcja nr6.5`, `PREMIER`, `OpenDeck_Balagan`, `DEBIUTY`, `PLAYLIST` — czyli fizyczna historia nauki DJ-ingu, równoległa do playlist w XML-u.
- **Żywa baza Rekordboxa** — `/Users/jantrybus/Library/Pioneer/rekordbox/master.db` (59 MB, **ruszany 14.08 o 01:07**) plus trzy kopie zapasowe z 13–14.08. Materiał analizuje eksport XML z **19.06.2026**, starszy o dwa miesiące, i na nim opiera wszystkie liczby o cue i bibliotece.
- **Warstwa dostarczenia produktu** — `/Users/jantrybus/Desktop/DanceLab.app`, `DanceLab.command`, `DANCELAB-DEMO/START.command`, `/Users/jantrybus/Desktop/DanceLab — jak odpalic.pdf` (1,3 MB). Ani słowa, mimo że to jedyne miejsce, gdzie widać, jak produkt trafia do ręki (przeskok do Ghostty, PATH bez Homebrew, tryb demo bez przeskoku terminala).
- **`/Users/jantrybus/Desktop/DanceLab playlisty/`** — 15 plików `DANCELAB 01–15.txt` z 11.08, po ~15 KB, każdy to gotowa tracklista (Ruskin & DVS1, Butch, Donna Summer, Regis, LFO…). Nigdzie nie wspomniane. To prawdopodobnie największa partia wygenerowanych setów, jaka istnieje.
- **`/Users/jantrybus/Desktop/AI`** — opisano cztery podkatalogi, a jest ich dziewięć. Nietknięte: `Neurosync/`, `Budget/`, `Suno/`, `Templater API/`, `Templater Studio/`, `.claude/`. Nawet jeśli nie dotyczą DanceLaba, trzeba to stwierdzić, a nie pominąć milcząco.
- **Luka w samym dzienniku** — ledger `dancelab-engine` ma ostatnią modyfikację 13.08 o 22:38, a `data/exports/cue_rejestr.json` w klonie DEMO o **14.08 01:07** i `tui_stan` o **07:18**. Praca po ostatnim wpisie do ledgera nie ma nigdzie opisu.

---

## C. Wątki urwane bez rozstrzygnięcia

1. **Osiem pogłębień dotyczy wyłącznie vaultu „DJ ID"** — trzydniowego projektu sprzed dwóch miesięcy. Żadne nie dotyczy DanceLaba. A to właśnie tam materiał sam wpisał „warto wrócić: BEZWZGLĘDNIE TAK": pilotaż DJ-ski ze Sprintu 5 (gotowy, zero sesji), pakiet M11 (DTW), `score(tau)` z DLASOT-12, Faza Przejścia, rejestrator MIDI (`experiments/07-midi-capture/midi_logger.py` — napisany, nigdy nieuruchomiony), Set Arc Engine, Crowd Response Proxy. To jest nierównowaga redakcyjna, nie brak danych.
2. **Pytanie „ile z DanceLaba to Janek, a ile model"** postawione trzy razy (autokorekta w `Moody Good.md`, „nie napisał ani jednej linijki kodu", partie notatek generowane hurtem) i ani razu rozstrzygnięte — bo rozstrzygnąć je da się tylko w transkryptach, których nie otwarto.
3. **Bramka korpusu uśpiona od 23.07** — opisana jako spór definicyjny, bez sprawdzenia, czy dane w ogóle są (dysk niepodpięty).
4. **Cztery syntezy z planu nie powstały** (`STAN.md`): łuk nauki, In Between, portret pracy, czego brakuje. Materiał, który dostałem, to surowiec bez trzech z czterech dachów.
5. **Sprzeczność niezamknięta**: `STAN.md` notuje „moje nocne »sprostowanie« było błędne" przy pytaniu, czy In Between jest w kodzie. Materiał niesie obie wersje i nie mówi, która obowiązuje.

---

## D. Konkretne ścieżki do douczytania (kolejność = priorytet)

**Poziom 1 — bez tego raport jest nieprawdziwy**
```
/Users/jantrybus/Developer/dancelab-engine/src/dancelab/          (187 plików)
/Users/jantrybus/Developer/dancelab-engine/scripts/                (100 plików)
/Users/jantrybus/Developer/dancelab-engine/experiments_priv/       (24 katalogi)
  ↳ 2026-08-04_werdykty/, 2026-08-08_apple_mixy/, 2026-08-10_ksztalt_setu/,
    2026-08-11_ablacja/, 2026-08-09_persony_dj/, 2026-08-03_dj_mapa/
/Users/jantrybus/Developer/DANCELAB-DEMO/     (+ dl-github, dl-final, dl-swieza)
  ↳ git log/diff między czterema HEAD-ami i dancelab-engine
  ↳ git -C dl-swieza diff  (niezacommitowane: src/dancelab/tui/app.py)
```

**Poziom 2 — jedyne źródło własnych słów Janka**
```
/Users/jantrybus/.claude/projects/-Users-jantrybus-Desktop-AI/            (377 MB)
/Users/jantrybus/.claude/projects/-Users-jantrybus-Desktop-AI-ai-room-sandbox-klaris/
/Users/jantrybus/.claude/projects/-Users-jantrybus-Developer-dancelab-engine--claude-worktrees-*/
/Users/jantrybus/.codex/sessions/**/rollout-*.jsonl                       (156 plików)
```

**Poziom 3 — materiał wylistowany, nieotwarty**
```
/Users/jantrybus/Documents/Obsidian Vault/DanceLab_SPRINT_4_CLOSED_FINAL.zip
/Users/jantrybus/Documents/Obsidian Vault/DanceLab_SPRINT_5_1_HARMONIC_CAMELOT_HOTFIX_CLOSED.zip
/Users/jantrybus/Documents/Obsidian Vault/DanceLab_SPRINT_5_4_DESCRIPTOR_COVERAGE_HOTFIX_CLOSED.zip
/Users/jantrybus/Desktop/DanceLab playlisty/DANCELAB 01–15.txt
/Users/jantrybus/Desktop/DanceLab — jak odpalic.pdf
/Users/jantrybus/Desktop/DanceLab — pomysły niewdrożone.xlsx   (czytany fragmentami)
/Users/jantrybus/Desktop/DanceLab.app/, DanceLab.command, DANCELAB-DEMO/START.command
```

**Poziom 4 — stan faktyczny do sprawdzenia przed cytowaniem liczb**
```
/Users/jantrybus/Library/Pioneer/rekordbox/master.db        (żywa baza, 14.08 01:07)
/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/**    (2 sety WAV + .cue)
/Users/jantrybus/Music/{Dj Sets,DanceLab Samples,debYOU,LEKCJA nr5,Lekcja nr6,Lekcja nr6.5,PREMIER,OpenDeck_Balagan,DEBIUTY,PLAYLIST}
/Volumes/MY_PC/DanceLabCorpus                                (NIEPODPIĘTY — sprawdzić)
/Users/jantrybus/Desktop/AI/{Neurosync,Budget,Suno,Templater API,Templater Studio}
```

---

## E. Jedno zdanie podsumowania

Materiał jest mocny tam, gdzie leżą notatki, i pusty tam, gdzie leży praca: nie ma kodu (187+100+114 plików), nie ma surowych wyników (24 eksperymenty), nie ma czterech najnowszych klonów repozytorium ani transkryptów rozmów (13,5 GB), a wszystkie osiem pogłębień dotyczy najmniejszego i najstarszego projektu w całym dorobku.