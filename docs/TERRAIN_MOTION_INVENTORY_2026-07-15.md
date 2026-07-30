# DanceLab Pro TERRAIN: atomic motion inventory

> **Dokument historyczny (2026-07-28).** Interfejs TERRAIN został usunięty z
> obsługiwanego produktu. Ta lista pozostaje wyłącznie zapisem decyzji
> projektowych; aktualny produkt jest terminalowy. Zobacz
> [indeks dokumentacji](README.md).

**Status:** specyfikacja do implementacji po kontraktach `ProjectSession` i `ExportManifest`  
**Data:** 2026-07-15  
**Zakres:** aktywny interfejs TERRAIN: `LIBRARY | SET | SEAM | TRACK` oraz `EXPORT GATE`  
**Poza zakresem:** Graph Mode, animacje marketingowe i zmiany algorytmów audio

## 1. Cel motion

Motion w DanceLab ma wykonywać jedną z czterech prac:

1. **Orientacja** - pokazywać, skąd element przyszedł i gdzie trafił.
2. **Stan** - pokazywać rzeczywistą pracę silnika, zapis, render albo playback.
3. **Relacja** - łączyć track, seam, cue i pozycję setu między widokami.
4. **Manipulacja** - dawać fizyczny feedback podczas drag, snap, zoom i scrub.

Animacja, która nie wykonuje żadnej z tych prac, nie wchodzi do produktu.

## 2. Zasady systemowe

| Zasada | Kontrakt |
|---|---|
| Jedno źródło prawdy | Motion odczytuje stan z `ProjectSession`, jobów albo transportu audio. Nie tworzy własnego stanu biznesowego. |
| Dane przed dekoracją | Playhead, EQ, progress i waveform pokazują prawdziwe wartości. Nie używamy fake progress, fake meterów ani losowego ruchu. |
| Ciągłość selekcji | Ten sam track albo seam zachowuje swoją tożsamość podczas przechodzenia między `SET`, `SEAM` i `TRACK`. |
| Motion nie blokuje | Nawigacja i akcje pozostają dostępne w trakcie animacji, chyba że trwa atomowy zapis pliku. |
| Przerwanie jest bezpieczne | Nowa akcja przejmuje animację od aktualnej wartości, zamiast resetować ją do początku. |
| Reduced Motion | Każda animacja przestrzenna ma wariant zredukowany. Funkcjonalny playhead i progress pozostają. |
| Maksymalnie jeden akcent | W jednym regionie nie mogą jednocześnie rywalizować dwie animacje przyciągające uwagę. |
| Stabilny layout | Duże layouty nie pulsują i nie zmieniają rozmiaru bez działania użytkownika. |

## 3. Tokeny

### 3.1 Czas

| Token | Wartość | Użycie |
|---|---:|---|
| `motion.instant` | 90 ms | press, focus, mała korekta koloru |
| `motion.fast` | 140 ms | hover, chip, selection ring |
| `motion.base` | 220 ms | tab content, drawer, inspector |
| `motion.spatial` | 320 ms | zmiana poziomu TRACK/SEAM, modal sheet |
| `motion.emphasis` | 420 ms max | narysowanie nowej rewizji terrain, pierwszy reveal |
| `motion.stagger` | 24 ms | widoczne elementy listy, maksymalnie 8 pozycji |

### 3.2 Easing

| Token | Znaczenie | Qt approximation |
|---|---|---|
| `ease.standard` | zmiana stanu w miejscu | `QEasingCurve.InOutCubic` |
| `ease.enter` | element wchodzi i wyhamowuje | `QEasingCurve.OutCubic` |
| `ease.exit` | element opuszcza widok | `QEasingCurve.InCubic` |
| `ease.spatial` | zachowanie ciągłości przestrzennej | custom cubic / `OutQuart` |
| `ease.snap` | fizyczny powrót cue/drag | tłumiona sprężyna bez wielokrotnego bounce |
| `ease.linear` | playhead i upływ czasu | linear |

Sprężyna jest dozwolona tylko dla elementu, który użytkownik przeciąga albo który fizycznie snapuje do celu. Statusy, modale i tekst nie sprężynują.

### 3.3 Odległość

| Token | Wartość | Użycie |
|---|---:|---|
| `distance.micro` | 2 px | press |
| `distance.local` | 8 px | tooltip, chip, row feedback |
| `distance.panel` | 16 px | inspector, drawer |
| `distance.spatial` | 24 px | przejście między workspace'ami |

## 4. Hierarchia atomiczna

### 4.1 Atomy

Atomy są najmniejszymi elementami motion. Nie uruchamiają procesów samodzielnie.

| ID | Atom | Trigger | Motion | Źródło prawdy | Priorytet |
|---|---|---|---|---|---|
| A01 | Button press | pointer/key down | skala lub przesunięcie 2 px, powrót | input event | P1 |
| A02 | Button busy | command accepted | label -> spinner + stabilna szerokość | command/job state | P0 |
| A03 | Focus ring | keyboard focus | opacity/outline | Qt focus | P0 |
| A04 | Tab indicator | workspace selection | przesunięcie pod aktywny tab | session selection | P0 |
| A05 | Toggle thumb | value change | pozycja + kolor | ustawienie sesji | P1 |
| A06 | Status dot | state change | crossfade koloru, bez pulsowania w idle | session/job state | P0 |
| A07 | Progress fill | progress callback | interpolacja do nowej wartości | real job progress | P0 |
| A08 | Indeterminate progress | etap bez mierzalnego postępu | spokojna pętla tylko podczas pracy | real running state | P0 |
| A09 | Selection ring | selection change | opacity + 1.0 -> 1.04 -> 1.0 | selected ID | P0 |
| A10 | Tooltip | hover/focus delay | 8 px + fade | hover/focus | P1 |
| A11 | Disclosure chevron | expand/collapse | obrót 90 stopni | expanded state | P1 |
| A12 | Cue marker | drag/restore/update | pozycja x | `CueDecisionStore` draft/final | P0 |
| A13 | Cue snap | drag release | tłumiony snap do punktu gridu | quantizer result | P0 |
| A14 | Region handle | drag | pozycja x bez easing podczas drag | pointer + bounded time | P0 |
| A15 | Playhead | playback | ruch liniowy po osi czasu | media position | P0 |
| A16 | Beat phase tick | playback | aktywny krok 1..8 | reliable beatgrid + transport | P0 Automix |
| A17 | EQ knob value | preview playback/scrub | obrót/arc do wartości | transition envelope | P0 Automix |
| A18 | Channel fader | preview playback/scrub | pozycja pionowa | transition envelope | P0 Automix |
| A19 | Crossfader | preview playback/scrub | pozycja pozioma | transition envelope | P0 Automix |
| A20 | Meter bar | audio callback | attack/release wartości | prawdziwy level meter | P1 Automix |
| A21 | Warning badge | blocker appears | fade + jeden local nudge | manifest/runtime warning | P0 |
| A22 | Saved state | save lifecycle | `Saving` -> `Saved HH:MM` crossfade | persistence callback | P0 |
| A23 | Drag ghost | drag start | opacity + elevation | drag payload | P0 |
| A24 | Drop target | compatible drag enters | outline/fill interpolation | drag compatibility | P0 |
| A25 | Zoom scale label | pinch/wheel | value crossfade | viewport scale | P1 |

### 4.2 Molekuły

Molekuła składa atomy w jedną rozpoznawalną interakcję.

| ID | Molekuła | Skład | Motion | Priorytet |
|---|---|---|---|---|
| MOL01 | Track row selection | A09 + tekst + actions | highlight przesuwa kontekst bez skakania tabeli | P0 |
| MOL02 | Track row insertion | row + status + badge | reveal wysokości i opacity; tylko widoczne wiersze | P1 |
| MOL03 | Track analysis state | A06 + A07/A08 + label | queued -> stage -> ready/warning/failed | P0 |
| MOL04 | Must Have action | pin + row badge | badge materializuje się przy tracku i w docku | P0 |
| MOL05 | Rest Tonight action | row + exclusion badge | kolor wycisza się, bez znikania tracka | P0 |
| MOL06 | Filter result update | chips + count + rows | count morph/crossfade, bez animowania 1000 wierszy | P1 |
| MOL07 | Import drop zone | A23 + A24 + counter | przyjęcie plików i przejście do kolejki | P0 |
| MOL08 | Job item | status + stage + progress + ETA | aktualizacja z realnych callbacków | P0 |
| MOL09 | Track card in terrain | energy point + identity + state | selection, lock/pin/rest feedback | P0 |
| MOL10 | Seam joint | quality bar + verdict + warning | selection i zmiana stanu quality/verdict | P0 |
| MOL11 | Candidate result | rank + reasons + score | reveal po zakończeniu rankingu | P1 |
| MOL12 | Cue control | marker + label + grid state | drag, snap, commit, undo | P0 |
| MOL13 | Transition region | two handles + fill + duration | resize region + duration label | P0 |
| MOL14 | Transport control | play/pause + time + playhead | spójna zmiana stanu playback | P0 Automix |
| MOL15 | EQ band control | knob + value + curve legend | live value, hover compare planned/actual | P0 Automix |
| MOL16 | Mixer channel | 3x EQ + gain/fader + meter | jeden zsynchronizowany frame | P0 Automix |
| MOL17 | Transition moment | marker + label | cue-in/bass swap/handover/cue-out aktywuje się na osi | P0 Automix |
| MOL18 | Verdict action row | Keep/Strategy/Skip/Listen | selection moves, saved confirmation | P0 |
| MOL19 | Export issue row | severity + title + deep link | highlight po otwarciu Gate | P0 |
| MOL20 | Toast | icon + message + action | enter, hold, exit; bez stosu nad krytycznym UI | P1 |

### 4.3 Organizmy

| ID | Organizm | Elementy wymagające motion | Priorytet |
|---|---|---|---|
| O01 | Project Bar | save state, global job state, Export Gate count | P0 |
| O02 | Workspace Tabs | active indicator i krótki content transition | P0 |
| O03 | Context Inspector | wymiana treści po selection, expand sections | P0 |
| O04 | Job Center | badge -> drawer, lista jobów, stop-after-current | P0 |
| O05 | Library Table | insert, selection, analysis state, constraint state | P0/P1 |
| O06 | Import Review Sheet | sheet entrance, accepted/rejected rows, confirm state | P0 |
| O07 | Set Terrain | tworzenie rewizji, selection, reorder, affected seams | P0 |
| O08 | Candidate Map | selected point, neighbor links, ranking reveal | P1 |
| O09 | Terrain Dock | active track/seam, quality/verdict updates, scroll-to-selection | P0 |
| O10 | Track Inspector | row/card -> detail continuity, waveform/cues, tier status | P0 |
| O11 | Seam Workspace | A/B waveform, region, cue, transport, reasons, verdict | P0 |
| O12 | Automix Console | timeline, decks, mixer, envelope i playback | P0 krytyczny |
| O13 | Export Gate | modal entrance, blockers, write progress, success/failure | P0 |
| O14 | Empty/Error State | local reveal i recovery action | P1 |

## 5. Przepływy produktowe

### 5.1 Import i analiza

1. Drop target reaguje dopiero po wejściu kompatybilnych plików.
2. Zaakceptowane pliki przechodzą do kolejki jako track rows.
3. Podejrzane długości otwierają jeden review sheet.
4. Status każdego tracka przechodzi przez prawdziwe etapy analizy.
5. Job Center agreguje postęp bez blokowania nawigacji.
6. Gotowy track nie skacze automatycznie do setu.
7. Jeśli istnieje set, pojawia się spokojny komunikat o nowych kandydatach.

### 5.2 Draw / Regrow Terrain

1. Kliknięcie `Draw terrain` przechodzi w busy state.
2. Istniejący plan pozostaje widoczny podczas obliczeń.
3. Po gotowym wyniku nowa rewizja jest rysowana od lewej do prawej.
4. Maksymalnie osiem widocznych pozycji dostaje stagger; reszta pojawia się razem.
5. Zmienione sloty i seamy są wskazane, ale nie migają.
6. Stary plan znika dopiero po zatwierdzeniu nowej rewizji w sesji.
7. Błąd pozostawia poprzedni plan bez zmian.

### 5.3 Selection bridge

| Wejście | Wyjście | Motion continuity |
|---|---|---|
| LIBRARY row | TRACK | identity/header przejmuje highlight wybranego tracka |
| SET point | TRACK | point zostaje aktywny w docku, TRACK otwiera tę samą tożsamość |
| SET joint | SEAM | joint rozszerza kontekst do pary A/B |
| SEAM deck | TRACK | aktywny deck określa track docelowy |
| TRACK occurrence | SET | dock przewija do pozycji i zaznacza ją |
| Export issue | TRACK/SEAM | Gate ustępuje, a docelowy problem dostaje pojedynczy highlight |

Nie wymagamy dosłownej animacji piksel-po-pikselu między odległymi widgetami. Wymagamy zachowania kierunku, identyfikatora, koloru selekcji i miejsca w terrain docku.

## 6. Automix: pełny motion storyboard

Automix jest najbardziej rozbudowaną powierzchnią motion, ale nadal jest narzędziem pomiarowym. Każdy ruch odpowiada planowi przejścia albo rzeczywistemu playbackowi.

### 6.1 Stany Automix

```text
EMPTY -> ARMED -> RENDERING -> READY -> PLAYING <-> PAUSED -> COMPLETE
                         \-> ERROR
```

| Stan | Co się porusza | Czego nie wolno udawać |
|---|---|---|
| EMPTY | tylko empty-state action | brak waveformu zastępczego |
| ARMED | cue/region i planowane envelope są widoczne | brak meterów bez audio |
| RENDERING | real render progress/stage | brak procentu, jeśli renderer go nie raportuje |
| READY | preview playhead wraca do początku regionu | brak automatycznego autoplay |
| PLAYING | playhead, beat phase, EQ, faders, meters | brak niezależnych timerów rozjeżdżających się z audio |
| PAUSED | wszystkie wartości zamarzają w tej samej klatce | brak dalszej animacji krzywych |
| COMPLETE | playhead na końcu, final state mixer | brak automatycznego resetu bez informacji |
| ERROR | status i recovery action | poprzedni poprawny render nie znika bez potrzeby |

### 6.2 Warstwy timeline

Od góry do dołu:

1. **Track A waveform** - realny waveform, beatgrid i outgoing cue.
2. **Track B waveform** - realny waveform, beatgrid i incoming cue.
3. **Overlap region** - wspólna oś przejścia z punktami semantycznymi.
4. **Mixer envelope** - planowane wartości high/mid/low, channel gain i crossfader.
5. **Transport lane** - playhead, beat 1..8, czas i stan render/playback.

Wszystkie warstwy używają jednej domeny czasu transition preview. Nie mogą mieć osobnych zegarów.

### 6.3 Elementy Automix wymagające animacji

| ID | Element | Zachowanie |
|---|---|---|
| AM01 | Master playhead | jeden liniowy playhead przechodzi przez wszystkie warstwy |
| AM02 | Deck A source playhead | mapuje master time na źródłowy czas A |
| AM03 | Deck B source playhead | mapuje master time na źródłowy czas B z rate/offset |
| AM04 | Beat phase 1..8 | pokazuje pozycję w aktywnym bloku kwantyzacji |
| AM05 | Phrase boundary | krótki state highlight przy przekroczeniu granicy, bez flash |
| AM06 | Cue-in marker | aktywuje się, gdy transport przekracza wejście B |
| AM07 | Cue-out marker | aktywuje się, gdy transport przekracza wyjście A |
| AM08 | Transition region | zakres pozostaje widoczny; played część dostaje subtelny fill |
| AM09 | Track A high/mid/low | gałki i krzywe odczytują envelope A |
| AM10 | Track B high/mid/low | gałki i krzywe odczytują envelope B |
| AM11 | Bass swap | moment wymiany low jest nazwany i widoczny na waveformie |
| AM12 | Tops swap | moment wymiany high/mid jest nazwany i widoczny na waveformie |
| AM13 | Channel fader A/B | pozycje wynikają z tego samego envelope co render audio |
| AM14 | Crossfader | pokazuje wartość planu, jeśli profil go używa |
| AM15 | Level meters | opcjonalne, tylko po wdrożeniu realnego pomiaru RMS/peak |
| AM16 | Sync rate | liczba i subtelna pozycja pokazują faktyczny playback rate B |
| AM17 | Quantize correction | marker snapuje tylko przy reliable grid; w przeciwnym razie pokazuje manual |
| AM18 | Profile switch | krzywe morphują do nowego planu dopiero po gotowym envelope |
| AM19 | Duration switch | timeline przeskalowuje się z zachowaniem centralnego momentu |
| AM20 | Stem state | aktywne źródło/stem crossfade tylko po gotowym player source |
| AM21 | Scrub | wszystkie kontrolki natychmiast aktualizują się do scrub time |
| AM22 | Hover compare | planned curve/value może pokazać ghost value dla wskazanego czasu |
| AM23 | Render ready | skeleton/progress zostaje zastąpiony prawdziwym waveformem/renderem |
| AM24 | Risk moment | marker ostrzegawczy wskazuje dokładny czas i powód, nie pulsuje stale |

### 6.4 Atomowy frame update

Podczas playbacku jeden update frame wykonuje kolejno:

1. odczyt pozycji transportu;
2. obliczenie wspólnej `transition_fraction`;
3. mapowanie pozycji źródłowych A/B;
4. odczyt envelope high/mid/low/fader dla tej samej fraction;
5. aktualizację playheadów, beat phase i kontrolek;
6. pojedyncze odrysowanie widocznych powierzchni.

Nie uruchamiamy osobnego timera dla każdej gałki. Audio i UI nie mogą dryfować.

### 6.5 Interakcje Automix

| Interakcja | Motion feedback | Commit |
|---|---|---|
| Drag cue | marker pod kursorem, bez easing | release -> quantize preview -> `CueDecisionStore` |
| Resize transition | uchwyt i fill aktualizują się live | release -> nowy duration/region draft |
| Scrub waveform | playhead śledzi pointer | release zachowuje transport position |
| Zmiana profilu | stare krzywe pozostają do gotowego nowego planu | atomic swap envelope |
| Zmiana 32/64/128/256 beats | oś skaluje się wokół handover | regenerate preview plan |
| Play | atomowy start wszystkich warstw | media player state |
| Pause | atomowe zatrzymanie wszystkich warstw | media player state |
| Bass/Tops swap marker drag | marker snapuje do 8-beat gridu | profile override draft |

Ręczne EQ live nie jest częścią pierwszego Automix. Najpierw wizualizujemy i odsłuchujemy plan silnika. Edycję automatyki dodajemy dopiero po osobnym kontrakcie danych.

## 7. Performance contract

| Obszar | Budżet/zasada |
|---|---|
| Playback UI | cel 60 FPS; dopuszczalne 30 FPS przy ciężkim waveformie, bez wpływu na audio |
| Main thread | żadnej analizy audio, Demucs ani renderu preview |
| Frame source | jeden zegar oparty na transport position / monotonic time |
| Repaint | tylko widoczny region i tylko zmienione custom-painted widgets |
| Lists | brak animacji wszystkich wierszy dużej biblioteki |
| Waveform | cache danych; animowany jest viewport/playhead, nie ponowne liczenie envelope |
| EQ curves | interpolacja gotowego envelope, nie ponowny DSP w paint event |
| Hidden views | zatrzymują dekoracyjne tickery i repaint |
| Profiling | log frame time i dropped frames dla SEAM/Automix |

## 8. Reduced Motion

W trybie zredukowanym:

- taby używają crossfade 90 ms zamiast slide;
- inspector i Job Center pojawiają się bez ruchu przestrzennego;
- set revision zmienia się przez crossfade bez stagger;
- cue podczas drag działa normalnie, ale snap nie ma overshoot;
- modale używają krótkiego fade;
- playhead, progress i niezbędny beat phase pozostają, bo przenoszą informację;
- nie ma startup reveal ani dekoracyjnego hover lift.

## 9. Motion zakazany

- fake waveform, spectrum albo level meter;
- fake progress dochodzący do 90% bez danych;
- pulsowanie każdego aktywnego statusu;
- sprężynujące teksty, tabele i modale;
- sinusoidalna lub dekoracyjna animacja energy terrain;
- automatyczne przesuwanie selection podczas playbacku bez polecenia użytkownika;
- animowanie BPM albo key tak, jakby były płynnymi wartościami;
- ukrywanie zmiany track ID pod crossfade bez aktualizacji całego kontekstu;
- transition curves poruszające się po pauzie;
- motion, który sugeruje zapis cue przed potwierdzonym commitem;
- pełnoekranowe zoomy i parallax odciągające uwagę od audio.

## 10. Kolejność implementacji

### P0 - motion funkcjonalny

1. Motion tokens i jeden `MotionController`.
2. Workspace tabs i context inspector.
3. Save/job/progress states.
4. Track/seam selection bridge.
5. Set revision reveal i stale/fresh transition.
6. Waveform playhead, cue drag/snap i region handles.
7. Automix: jeden transport clock, A/B playheads, EQ/fader envelope, beat phase.
8. Export Gate lifecycle.
9. Reduced Motion.

### P1 - ciągłość i czytelność

1. Track row insertion i constraint feedback.
2. Job Center drawer.
3. Terrain dock scroll-to-selection.
4. Candidate ranking reveal.
5. Deep links Gate -> TRACK/SEAM.
6. Toasts i local recovery states.

### P2 - polish

1. Shared-context transition row/point -> detail header.
2. Pierwszy reveal pustego projektu.
3. Subtelne hover elevation.
4. Planned-vs-current ghost values w Automix.
5. Real level meters, dopiero po źródle danych i teście wydajności.

## 11. Definition of Done dla animowanego komponentu

Komponent motion jest ukończony tylko wtedy, gdy:

- ma jawny trigger i finalny stan;
- nie przechowuje duplikatu stanu biznesowego;
- można przerwać animację bez złego stanu;
- działa klawiaturą i myszą/touchpadem;
- ma reduced-motion fallback;
- nie blokuje GUI ani audio;
- ma test finalnego stanu po zakończeniu/przerwaniu;
- dla audio ma test synchronizacji po seek, pause i resume;
- nie pokazuje danych, których runtime nie dostarczył;
- przechodzi wizualny test przy małym i dużym oknie.
