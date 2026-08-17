# KRONIKA UCZENIA SIĘ DANCELAB ENGINE — wyciągnięta z komentarzy w kodzie

Repo: `/Users/jantrybus/Developer/dancelab-engine`. Przeczytane: 187 plików w `src/`, 114 w `tests/`. Każdy wpis ma format **ZAŁOŻENIE → POMIAR → WYNIK** i źródło `plik:linia`. Cytaty liczbowe pochodzą dosłownie z komentarzy.

---

## I. LIPIEC — fundament pomiarowy (tempo, sprzęt, korpus)

### 11.07 — hipoteza obalona, a potem obalone samo obalenie
**Jedyny przypadek w repo, gdzie POMIAR okazał się błędem, a nie kod.**
`/Users/jantrybus/Developer/dancelab-engine/src/dancelab/core/backend.py:20-28`
> `2026-07-11 first run: cosine 0.61 vs CPU → gate blocked MPS (honest).`
> `2026-07-12 re-gate (…): cosine 0.999986 across repeated runs …, ×1.55 faster. The first measurement was erroneous (first-run contamination — likely initial MPS kernel compilation mid-benchmark).`

Wynik: `MPS_VERIFIED = True`, a strażnik w `test_backend.py` pilnuje teraz **odwrotnego** kierunku — ma paść, jeśli przyszły torch/demucs znowu rozjedzie MPS z CPU.

### 11.07 — dwa benchmarki, które zamknęły temat równoległości
- `src/dancelab/stems/extractor.py:157-160`: `2 workers × 5 threads gave only ×1.18 over 1 worker × default threads — torch already parallelizes internally` → `parallel_workers` domyślnie 1; pokrętło zostaje „for bigger machines".
- `src/dancelab/workflows/smart_playlist.py:492-494`: `overlap 0.10 → ×1.25 faster, cosine 0.99994 vs the 0.25 default — quality-identical fast profile`.
- `src/dancelab/ingestion/rekordbox_device.py:6`: eksport urządzenia `reverse-verified byte-by-byte against a real device export on 2026-07-11`; ground truth przypięty w `tests/test_rekordbox_device.py:128`.

### 17.07 — pierwszy prior z korpusu i jego uczciwy asterisk
`src/dancelab/decision/set_builder.py:477-484`
> `The corpus (2026-07-17, n=6142 adjacent pairs) shows DJs keep the same octave in 99.1% of transitions. Calibrated on Janek's 35 blind ratings: sweeping this preference rose rho 0.272→0.344 monotonically; set to 0.9 … Thin leverage (2/35 pairs crossed octaves, both rated 1/5) — revisit with the 5-rater study.`

Wynik: `SAME_OCTAVE_PREFERENCE = 0.9`. **Perełka honestii:** komentarz sam podważa własną wiarygodność (2 pary na 35 to dźwignia).

### 21.07 — CLAP: co potrafi, a czego nie
`src/dancelab/decision/steering.py:12-13`
> `CLAP należy do selekcji; w parach sam nie niesie sygnału, p=0,378 na bramce 01.08`

To zdanie jest **przyczyną całej późniejszej architektury sterowania** (patrz 09.08, sito brzmienia). Wektory policzone i zapisane 21.07 (`src/dancelab/ingestion/analysis_enrichment.py:8`) — i leżały nieużywane do 04.08.

### 24.07 — audyt duplikatów tytułów
`src/dancelab/decision/anchors.py:11-13`, `src/dancelab/ingestion/playlist_publish.py:12`
> `Biblioteka Janka ma duplikaty tytułów i ta klasa błędów już raz wystrzeliła … niejednoznaczność = odmowa (audyt 24.07).`

Ta reguła (odmowa zamiast zgadywania) rozlała się potem na cue-writer, kotwice i publikację playlist. Osobny dług z tego samego dnia: po wycofaniu Qt hooki `stage_progress`/`should_stop` `od 24.07 nie miały konsumenta` (`src/dancelab/tui/app.py:10-12`) — wrócą dopiero w TUI.

### 28.07 — diagnoza relacji DJ↔silnik
`src/dancelab/cli/tui.py:3-7` oraz `src/dancelab/decision/verdicts.py:3-6`
> `The status report of 2026-07-28 measured the DJ-to-engine relation as asymmetric: the engine proposes and explains, but the DJ's correction reaches it through an engineer rather than through the product.`

Wynik: `dancelab room` + moduł `verdicts.py` jako **droga powrotna**, z celowo wąskimi zasadami: werdykt pamięta się dla PARY i niczego więcej („z garści osądów uogólnienie »nie lubi molowych« byłoby wymysłem, nie uczeniem"), ocena silnika nigdy nie jest nadpisywana.

### 28.07 — reguła długości blendu ŚWIADOMIE nie-pomiarowa
`src/dancelab/decision/transition_length.py:9-14`
> `This is DELIBERATELY a rule, not a measurement. The corpus cannot answer it (its transition_length field is alignment-gap noise …), so the thresholds below are craft defaults, named and tunable, never presented as measured.`

### 30.07 — reguła wejścia Janka, zmierzona
`src/dancelab/stems/envelopes.py:7-9`
> `„utwór opiera się tu na perkusji i schodzi z basu", zmierzona 2026-07-30 na 21 szwach (71% jego wejść wobec 18% losowych momentów)`

### 30.07 — dług odkryty: lepsza siatka istniała i nie docierała do produktu
`src/dancelab/preprocessing/rigid_beatgrid.py:3-8`, `tests/test_rigid_beatgrid_pipeline.py:3-6`
> `The engine has had two beat grids since 2026-07-30 and the better one never reached the product.`

### 31.07 — sztywna siatka wygrywa z trackerem
`src/dancelab/preprocessing/rigid_beatgrid.py:10-11`, `src/dancelab/core/config.py:31-35`
> `Measured 2026-07-31 against Rekordbox (an algorithm that is not ours, 183 tracks): mean error 1.7 millibeats for the rigid fit against 8.0 for the tracker.`

Wynik: `rigid_grid: bool = True`. Dwie granice, których siatka nie przekracza: `downbeat_phase_verified` zostaje `False` (fold ustala fazę BITU, nie TAKTU), a `quality_score` zostaje `None` (kontrast to nie prawdopodobieństwo).

### Lipiec/sierpień — trzy kalibracje wewnątrz `rigid_grid`, każda z historią porażki

| Stała | Co się stało | Źródło |
|---|---|---|
| `MIN_CONTRAST = 2.2` | Próg **BYŁ 2.0**, skalibrowany przed dodaniem drobnego skanu tempa; skan może tylko podnieść wynik i podniósł „Archangel" Buriala do 2.06, przepuszczając płytę zrobioną bez metronomu przez bramkę, która ją wcześniej słusznie odrzuciła. Próba 49 płyt: stemy i mowa 1.09–1.99, prawdziwe płyty klubowe 2.42–4.08 — próg leży w luce. | `core/rigid_grid.py:29-40` |
| `OCTAVE_MARGIN = 1.27` | Bicep „Glue" dopasowany na 195 zamiast 130, COIDO 184 zamiast 138, Ahoona 160 zamiast 120 — i wszystkie trzy wypadły z setu jako „32% od tempa", stojąc dwa procent od niego. Na 184 płytach vs Rekordbox: **1074 przypadki, gdzie wolniejsza relacja jest zła, i 3 gdzie dobra**. Na paśmie stopy się rozdzielają (złe do 1.210, dobre od 1.323); na pełnym widmie **całkowicie się nakładają** (0.880–1.097 vs 95. percentyl 0.873). | `core/rigid_grid.py:55-73` |
| `KICK_HZ = 160` | Pełne widmo pozwalało hi-hatom, klaśnięciom i ogonom pogłosu przegłosować stopę: `a 135 BPM record read as 169, a jungle tune as 131`. | `core/rigid_grid.py:99-107` |
| `OCTAVE_WINDOW_SEC = 60` | Przy 128.3 najbliższy kandydat gruby to 128.5, który przez 90 s dryfuje o jedną trzecią bitu i rozmazuje pik, a 192.5 stoi 0.05 od 1.5× prawdy, zostaje ostry i **wygrywa na połowie energii**. | `core/rigid_grid.py:48-54` |

Perełka autorska w tym samym pliku: **„three positive examples is thin evidence for the exact number; the thousand negatives below it are not"** (`rigid_grid.py:70-71`) — próg broniony asymetrycznie, świadomie.

---

## II. POCZĄTEK SIERPNIA — czyszczenie danych i pierwsze obalenia

### 01.08 — eksport XML wycięty
`src/dancelab/export/__init__.py:1-5`
> `Eksport XML wycięty 01.08 (decyzja Janka): lądował w osobnym widoku Rekordboxa zamiast w bibliotece DJ-a. … Kod XML jest w historii gita, gdyby zapis do bazy kiedyś przestał działać.`

### 02.08 — wektor z próbki ≠ wektor z pliku
`src/dancelab/ingestion/analysis_enrichment.py:69-70`
> `zmierzone 02.08: klasyfikator „próbka czy … plik" osiąga AUC 0,889 na samych wektorach`

Wniosek wbudowany w kod: porównywać wolno **w obrębie jednej grupy**.

### 03.08 — największy brak silnika okazał się nie do policzenia, tylko do odczytania
`src/dancelab/ingestion/rekordbox_phrases.py:3-27`
> `segmenty istniały, ale wszystkie 1881 były bez etykiety (zmierzone 2026-08-03 na 243 utworach) … Okazało się, że liczyć tego nie trzeba. Rekordbox … zapisuje ją na dysku Janka dla 1871 utworów.`

Słowniki odczytane ze **zrzutów ekranu**, nie zgadnięte. **Mood 3 świadomie nieobsłużony** — Sister i Nature Boy używają słownika piosenkowego, ale numeracja się nie zgadza; `Zgadnięcie tutaj byłoby dokładnie tym rodzajem liczby, która wygląda na zmierzoną (ADR-005)`.

### 03.08 — brzmienie w ocenie pary: działa, ale nie u Janka
`src/dancelab/decision/sound_affinity.py:3-23`
> `Zmierzone 2026-08-03 na 45 miksach korpusu, przy nowej regule przyjmowania wariantów (liczy się dolna tercja, nie średnia):`
> `nieprzewidywalni 0,6826 → 0,7537 (+0,071) · środek 0,7946 → 0,8336 (+0,039) · zachowawczy 0,8641 → 0,8997 (+0,036)`
> `TO NIE JEST UNIWERSALNE. Na setach Janka ten sam składnik dał −0,008. … Zapisane jako znany limit, nie zamiecione.`

Wynik: `sound_affinity_weight = 0.60` (`core/config.py:113-116`), wmieszane PO rdzeniu i tylko w trybie smart (`set_builder.py:797-806`).

### 03.08 — kontur: styl to ROZKŁAD, nie średnia
`src/dancelab/decision/steering.py:15-18`
> `celowanie w medianę 0,71 Four Teta dawało kwartyle 0,71–0,82 zamiast jego 0,61–0,79 i gasiło rozrzut, który jest całą treścią stylu`

Wagi konturu są **jawnie oznaczone jako rzemieślnicze, nie pomiarowe** (`steering.py:35-38`): `v4 trafiła kwartyl 0,79 i skok 0,46 przy celach 0,79/0,44`.

### 03.08 — przesłanka lipcowej poprawki okazała się FAŁSZYWA
Najczystsze obalenie w repo. `src/dancelab/ingestion/rekordbox_grid_snap.py:122-134`
> `Lipcowy wpis w rejestrze mówił, że trzeba dorobić cross-check tempogramem, bo „Red Light Fever: silnik 120,01, realnie 117,45". Sprawdzone 2026-08-03 wprost na tym pliku: dopasowanie przy 120,00 wynosi 3,00, a przy 117,45 tylko 1,02 — i jest to wąski pik, nie plateau. Utwór stoi na 120. Rekordbox mówi 120,02. Przesłanka tamtej poprawki była fałszywa i tamtej poprawki nie ma po co pisać.`
> `Ale klasa błędu istnieje, tylko inna. Na 191 płytach nasze tempo rozjeżdża się z Rekordboxem powyżej 1,5% w czterech przypadkach, z czego TRZY silnik oznaczył jako pewne — i wszystkie trzy to wybór oktawy albo relacji (70 zamiast 140, 69 zamiast 138, 101 zamiast 135), nie dryf.`

Wynik: `TEMPO_DISPUTE_PCT = 1.5` — nie kopiujemy wartości Rekordboxa, tylko **przestajemy twierdzić, że wiemy**.

### 03.08 — progi „co nie jest płytą"
`src/dancelab/ingestion/preflight.py:7-13`
> `Progi 2–10 min są potwierdzone pomiarem 2026-08-03 na paśmie 130–135 BPM …: prawdziwe płyty rozciągają się od 2:53 do 8:48 przy medianie 4:55, a jedyny odstający plik miał 52:13 (jego własny nagrany set „Open Deck").`
> `Ten moduł ISTNIAŁ i nie był wołany z żadnej ścieżki produktowej — dlatego to nagranie weszło do pierwszej listy kandydatów na set.`

### 03.08 — stemy wyłączone z normalnej analizy (decyzja z liczbą na dysku)
`src/dancelab/stems/envelopes.py:12-17`
> `cache surowych śladów waży 5860 MB przy 31 utworach, czyli ~190 MB na utwór — biblioteka 243 utworów zajęłaby ~47 GB, a wolnego jest 37.`

Wynik: zostają **krzywe** (1 Hz, kilkadziesiąt KB), nie stemy.

### 04.08 — dwa organy podłączone do mózgu i nigdy niekarmione
`src/dancelab/ingestion/analysis_enrichment.py:3-13`
> `Track.sound_embedding — pole istnieje od dawna, transition_score miesza je w ocenę w trybie smart (sound_affinity_weight 0,6 …), ale ŻADNA ścieżka go nie wypełniała.`
> `Track.style_label — … etykieta szła wyłącznie z tagów PLIKÓW, których 72% biblioteki nie ma. Tymczasem Janek opisał gatunki we WŁASNEJ taksonomii w Rekordboksie — i ona jest trafna (pomiar 03.08: iTunes wrzuca wszystko do „Dance", jego tagi rozróżniają garage/breaks/bass/dubstep).`

---

## III. 04–08.08 — TUI, weta i rzeczy, które żyły jeden dzień

To jedyna część kroniki, gdzie „pomiarem" jest **własna reakcja Janka na użycie produktu**. Komentarze są tu świadomie pisane jako **nagrobki**, żeby pomysł nie wrócił bez pamięci o werdykcie.

| Data | Co założono | Co się stało | Źródło |
|---|---|---|---|
| 04.08 → 05.08 | Poświata „influence" pokaże wpływ kotwicy | **Żyła jeden dzień.** Pomysł Janka 04.08, jego własne weto 05.08 po użyciu: „makes no sense and it's distracting" — usunięta w całości | `tui/app.py:276-278` |
| 05.08 rano → 06.08 | BPM/tonacja wyróżnione podkładką (tłem) | Weto po zobaczeniu jasnego motywu: „ciemne tło wygląda tam jak dziury" → BOLD, bo działa w obu motywach | `tui/app.py:283-287` |
| 06.08 → 06.08 wieczór | Waveformy w panelu porównania (RGB, warstwy basu, siatka, frazy) | **Żyły dwa dni.** Weto: „they are not even functional, just for the look purposes". Powrót do wzorca z CURVE: jeden przycisk odsłuchu między parą | `tui/app.py:294-298` |
| 05.08 | — | Higiena puli: stem „vocals" wylądował w secie Janka **DWA RAZY, pozycje 18 i 19**; „Janek.mp3" (43-minutowy cudzy set) wskoczył na 1. miejsce | `tui/app.py:58-62` |
| 05.08 | Detektor tonacji wystarczy | **Krumhansl-Schmuckler trafia w sędziego RB w 47%** → decyzja: „apka gra tym, co widzę w Rekordboksie" | `ingestion/analysis_enrichment.py:198-201`, `tests/test_steering_and_anchors.py:171` |
| 05.08 | — | Regres: puste „Graj jak…" dawało obiekt `NoSelection` zamiast `None` | `tests/test_tui_and_publish.py:176` |
| 05.08 (E2E) | — | Budowa odmawiała „unknown track" o utworze, który **W SENSIE MUZYKI w puli JEST** — dedup wycinał duplikat, na który wskazywał filar → `canonical_ids` | `decision/dedup.py:52` |
| 06.08 | Historia setów dopisywana przy każdym B | **Zmierzone 06.08:** dopisywanie przy każdym B zmieniało historię między budowami i **TEN SAM seed dawał inny set** — obietnica powtórki złamana. Świeżość ma omijać sety UŻYTE, nie każdy eksperymentalny B | `tui/app.py:3229-3232` |
| 06.08 | afplay wystarczy | afplay nie umie seeka → skoki „co 8 uderzeń" niewykonalne. Potem skarga „sekunda przerwy przy przełączaniu" → **hybryda**: afplay od zera, ffplay tylko od środka | `tui/odtwarzacz.py:3-9, 42-46` |
| 06.08 (na żywo) | Najlepsza para okien zawsze da się zagrać | „żadnemu z utworów nie starcza zapasu" → schodzenie po parach okien wg łącznej oceny, z jawną notką | `tui/seam_preview.py:60-64` |
| 06.08 (regres z życia) | — | szukajka → play → wyczyszczenie filtra **ubijało grany utwór i grało inny** | `tests/test_tui_library.py:658` |
| 08.08 | — | Regresja: O (wczytaj plan) bez wcześniejszej budowy wołało nieistniejącą rzecz | `tests/test_tui_library.py:776` |

---

## IV. 09.08 — DZIEŃ TESTU PERSON. Najgęstszy dzień w całym repo

Jeden test (przejście aplikacji „jako ktoś inny": Kuba, Zosia) wywalił **osiem niezależnych klas błędów naraz**. To najlepiej udokumentowany moment projektu.

### 1. Kotwica brzmienia była BEZWŁADNA — i przyczyna była gdzie indziej niż myślano
`src/dancelab/decision/sito_brzmienia.py:3-41` — najważniejszy komentarz w repo.

> **Zmierzone:** `waga od 0,35 do 0,90 nie zmieniała niczego, co dało się zmierzyć` — „graj jak Four Tet" i „graj jak Jamie xx" dawały ten sam set.
>
> **PRAWDZIWA PRZYCZYNA, znaleziona przy okazji i ważniejsza od samego sita:** utwór BEZ wektora nie dostawał od sterowania ŻADNEJ korekty (zostawał przy rdzeniu, często 1,000), a każdy kandydat, którego DAŁO SIĘ ocenić, był ściągany w dół o `(1 − bliskość)·waga`. **Utwory niemożliwe do oceny systematycznie WYGRYWAŁY z ocenionymi — i im wyższa waga kotwicy, tym mocniej.** Sprawdzone imiennie: `Farsight 100% utworów bez wektora, K-LONE 100%, HAAi 71%, Olof Dreijer 50%`.

Druga przyczyna, geometryczna (`decision/steering.py:52-55`):
> `mediana kosinusa między centroidami 363 par DJ-ów to 0,886 … po wyśrodkowaniu mediana spada do 0,008, a ta para (Four Tet / Ben UFO) zostaje blisko (+0,458)`

**Wynik — zmiana architektury, nie parametru:** kotwica przestaje być dodatkiem do OCENY i staje się **sitem** — decyduje, kto wchodzi do puli, zanim rdzeń zacznie układać kolejność. Tabela strojenia udziału (pula 1857 z wektorami, sety po 10, trzy kotwice), `sito_brzmienia.py:31-41`:

```
100% → 1,0/10 · 0,9992     50% → 0,0/10 · 0,9867
 30% → 0,3/10 · 0,9974     20% → 0,3/10 · 0,9970
 10% → 0,3/10 · 0,9995      5% → 0,3/10 · 0,9742
```
> `Rozróżnialność wysyca się od razu — bierze się głównie z odsunięcia utworów nieocenialnych, nie z ostrości sita.` → `DOMYSLNY_UDZIAL = 0.20`

### 2. Teza tripletów potwierdzona — i jej spekulacyjna połowa OBALONA
`src/dancelab/decision/set_builder.py:976-983`, test w `tests/test_set_builder.py:444-450`
> `KRAWĘDŹ MOSTOWA (badanie tripletów, 09.08.2026): gdy następny slot to FILAR, kandydat jest oceniany także za wejście W NIEGO — suma obu krawędzi, wagi równe (zmierzone α=1,0). Na 636 segmentach realnych setów podnosi dokładne rekonstrukcje 28,1%→36,2% (p<0,0001). Tylko ustalone C — spekulacyjny lookahead bez celu zmierzony jako bezwartościowy i celowo NIEobecny (p=0,88 na 152 setach).`

To wzorcowy wpis: **potwierdzenie i obalenie w jednym akapicie, oba z p-wartością, i obalona wersja jest jawnie nazwana jako nieobecna.**

### 3. Set dłuższy niż pula degradował się PO CICHU
`src/dancelab/decision/set_builder.py:916-920`, `tests/test_slabe_szwy.py:3-6`
> `ta sama biblioteka 150 utworów daje przy secie na 10 średnią 0,955 i najsłabszy szew 0,695, a przy secie na 30 — najsłabszy 0,386 i skok tempa 26 BPM, i ani jednego ostrzeżenia. Zosia (pierwszy rok grania) prosi o dwie godziny ze 150 utworów, dostaje sklejkę i nie wie, że przesadziła.`

Próg z rozkładu (`set_builder.py:906-909`): `3000 losowych par z puli 1913 utworów: mediana pary losowej 0,357, pierwszy kwartyl 0,164, a przyzwoity szew ~0,89` → `SLABY_SZEW = 0.60`.

### 4. Brief gatunkowy znikał po cichu i wpuszczał hip-hop do setu techno
`src/dancelab/decision/set_builder.py:1290-1297`
> `Kuba wpisał „Techno (Peak Time / Driving)" (nazwa Beatportu), a jego biblioteka ma „Electro" ×100 i „Films/Games" ×22 z katalogu — brief pasował do zera utworów i został po cichu zdjęty, więc do setu techno wszedł hip-hop.`

### 5. Preferencja gatunku była WYŁĄCZNIKIEM — a pierwsza naprawa też została obalona
`src/dancelab/decision/premia_gatunku.py:3-24`
> `Do 09.08 … albo zawężała pulę w całości, albo — gdy pasujących utworów było mniej niż długość setu — znikała BEZ RESZTY.`
> `Pierwsza wersja przesuwała ocenę ku jedynce (ocena + w · (1 − ocena)) i **została odrzucona pomiarem**: przy dobrym szwie 0,892 dawała ledwie 0,016 premii, więc dokładnie tam, gdzie silnik pracuje najczęściej, gatunek nie zmieniał nic.`

Waga z tabeli (`premia_gatunku.py:34-42`; 256 utworów, set na 18, brief „House" przy 7 dostępnych):
```
0,00 → 2/7 · 0,9595    0,08 → 2/7 · 0,9688
0,15 → 3/7 · 0,9609    0,25 → 3/7 · 0,9504
```
→ `DOMYSLNA_WAGA = 0.15`. Dodatkowo **bez przycinania do sufitu**, bo `zmierzona średnia ocena szwu w jego puli to 0,96, więc premia wpadała w sufit i remis rozstrzygała nazwa pliku` (`premia_gatunku.py:77-83`).

### 6. Dopasowanie gatunku po słowach zawyżało pulę 3–5×
`src/dancelab/decision/library_profile.py:31-38`
> `brief „House" wciągał 32 utwory zamiast 7 (Tech House, Deep House, Afro House, Melodic House & Techno), „Breaks / Breakbeat / UK Bass" 49 zamiast 11, „Bass / Club" 30 zamiast 8. … wybieraczka została poprawiona 09.08, silnik dopiero teraz.`

### 7. Filary Janka pojawiały się w cudzych bibliotekach
`src/dancelab/tui/user_store.py:30-37`
> `filary Janka pojawiały się w KAŻDEJ innej bibliotece („FILAR nieobecny w puli" ×9 u każdej persony), bo stan leżał w jednym pliku niezależnym od puli`

### 8. Księga kotwic nie obejmuje DJ-ki, której gra Kuba
`src/dancelab/decision/anchors.py:58-70`, `src/dancelab/tui/app.py:2861-2864`
> `księga ma 285 DJ-ów zmierzonych z ich setów, a Kuba gra jak Amelie Lens, której tam nie ma — i nie ma jak jej dodać bez jej setlist.`

Rozwiązanie: kotwica z WŁASNYCH utworów. **Kontur zostaje PUSTY** — „to cecha sposobu grania DJ-a, której z samego zbioru utworów nie da się odczytać, a udawanie jej byłoby zmyślaniem".

### Pozostałe znaleziska tego samego dnia

| Znalezisko | Liczba | Źródło |
|---|---|---|
| Nasze własne pady blokowały nas jak cudze | `8 z 26 padów odpadało, w tym 2 zablokowane naszym własnym zapisem` | `ingestion/cue_ledger.py:3-7` |
| Cue mijały czerwone linie taktów Rekordboxa | `25 z 26 padów mijało linię, czasem o 0,9 s` (stąd „68.1, a nie 68.2") | `tui/cue_podglad.py:44-49` |
| Przyczyna: stary podział 2-bitowy | `The old 2-beat division put cues on beat 3 and was the source of that complaint` → wszystkie podziały to całe TAKTY | `decision/cue_grid.py:19-22` |
| 1571 z 1880 pozycji to strumienie Apple Music | DanceLab widział **229 utworów zamiast ~1800** | `ingestion/rekordbox_import.py:3-9` |
| Przepustka przywiązana do jednej wersji silnika | biblioteka z innego źródła **znikała w całości**, user dostawał „pusta pula" i notkę o stemach | `tui/app.py:3021-3025` |
| Pokrycie wektorami w realnej puli | `0 z 201 utworów puli miało wektor` | `tests/test_sound_affinity.py:122` |
| Druga metoda o tej samej nazwie w klasie | `po cichu KASOWAŁA pierwszą — Enter w panelu nie działał` | `tests/test_grupy_dj.py:139-141` |
| Aplikacja z ikony dostaje goły PATH launchd | odsłuch od pada milczał w Ghostty, choć w terminalu działał | `tui/odtwarzacz.py:26-28` |
| Dwa razy wywalona budowa (`ui`, `notes`) | `testy tego nie łapały, bo żaden nie przechodził jej w TUI` | `tests/test_kotwica_wlasna_w_apce.py:3-5` |
| Audyt nomenklatury | odsłuch nazywał się w aplikacji **na pięć sposobów** | `tests/test_nomenklatura.py:1-8` |

### 09.08 — grupowanie DJ-ów: pomiar DWÓCH ODRZUCONYCH pomysłów przed trzecim
`src/dancelab/tui/grupy_dj.py:3-14`
> `* gatunek — pole genres jest puste w 100% naszych profili DJ-skich; dopisanie go 284 nazwiskom byłoby zgadywaniem;`
> `* miejsce/event — w tytułach miksów mamy Boiler Room (301) i Warehouse Project (61), ale to jest ŹRÓDŁO NASZEGO SCRAPINGU, nie tożsamość artysty; grupowanie po tym kłamałoby.`

Zostaje centroid CLAP + k-średnie z ustalonym ziarnem, a **grupy nazywają się swoimi najbardziej typowymi członkami**, bo etykiet gatunkowych nie zmierzono.

---

## V. 10–11.08 — ŁUK ENERGII OBALONY

Największa merytoryczna zmiana w silniku.

`src/dancelab/decision/set_builder.py:519-525`
> `arc="off" is the DEFAULT since 2026-08-11 (Janek's call after the shape measurement). **Measured three independent ways, the "build" ramp described real sets WORSE than a flat line**, and real sets take a median of 5 energy drops >8% — which "build" forbade outright.`

Konsekwencje przypięte w kodzie:
- `_energy_score` przy `arc="off"` zwraca `1.0` — człon energii jest neutralny, rdzeń parowy decyduje sam (`set_builder.py:667-68`).
- `arc_adherence` zostaje `None`, bo `Inventing an adherence number here would be fabricating a measurement (ADR-005)` (`set_builder.py:655-670`).
- Testy `tests/test_luk_off.py:1-8` istnieją wyłącznie po to, żeby `a silent revert cannot happen`.

**A oto najciekawsze: obalenie natychmiast wyprodukowało nową funkcję produktową.**
`src/dancelab/tui/user_store.py:48-52`
> `Role filarów (Janek, 11.08): filar przestaje być tylko „musi zagrać" — niesie deklarację MIEJSCA w secie. **To jest odpowiedź na obalony łuk: zamiast narzuconej krzywej DJ deklaruje punkty stałe, a silnik napina set między nimi.** Nazwa „filar" została świadomie (Janek: „nie rozstawiasz 5 kotwic, a filary już tak").`

To domknięcie pętli: pomiar → obalenie → nowa metafora produktowa → nowa struktura danych.

---

## VI. 12–14.08 — porządkowanie

- **12.08:** playlista = projekt; filary żyją W PLAYLISTACH, nie globalnie (`tui/user_store.py:88`); po nazwie OD RAZU Biblioteka, kotwica przestaje być wymuszonym krokiem (`tui/app.py:527`); paleta TERRAIN z makiet GUI **nadpisuje monokai z 06.08** (`tui/app.py:899-901`); kolekcja DJ-ów przeniesiona ze ściany kart (`tui/user_store.py:200`).
- **12.08 (test):** `DataTable` nie przyjmuje dwóch pozycji o tym samym id — złapane testem (`tui/app.py:1606`).
- **13.08 — duplikaty zmierzone.** `src/dancelab/tui/duplikaty.py:3-9`:
  > `1914 analiz to w rzeczywistości 1690 utworów — 222 wpisy nadmiarowe w 159 grupach. „Bodhi — 433Mhz" występuje sześć razy. To NIE jest błąd silnika. Ten sam plik leży w kilku folderach … a do tego dochodzi bliźniak z Apple Music.`
  Rozwiązanie: `Scalamy WIDOK, nie dane`.
- **13.08:** Rekordbox Analyze oddał utwór z **pierwszą frazą na bicie 3** (`tests/test_rekordbox_phrases.py:81`); LUFS nie liczy się sam na starcie (`tui/app.py:2107`); utwory nie na dysku jawnie oznaczone (`tui/zrodlo.py:3`).
- **14.08:** ostatnia zmiana w kodzie — `tui/app.py:651` (odsłuch szwu tylko w Eksport/Cue).

---

## VII. WĄTEK RÓWNOLEGŁY — audyt „AUD-*": pomiary, które nie mają daty, ale mają numer

W repo istnieje ponumerowana seria znalezisk audytowych, każde **przypięte testem**. To osobna, cichsza kronika:

| Numer | Co było złe | Źródło |
|---|---|---|
| AUD-H2 | Odległość do najbliższego bitu jest **z konstrukcji** ≤ 0.5·okres, więc stara tolerancja 0.5 wpuszczała wszystko (łącznie z dokładnymi off-beatami) i **nasycała proxy na materiale synkopowanym** → 0.15 | `features/microtiming.py:59-65` |
| AUD-M1 | Utwór, który jest w >50% ciszą, ma medianę wszystkich ramek = 0 → referencją musi być mediana ramek NIEZEROWYCH | `features/vocals.py:115-121` |
| AUD-M3 | Brak treści tonalnej → jawne „nieznane", nigdy zmyślone „C major/8B" | `features/key.py:45` |
| AUD-M6 | Wagi nagrody w beam searchu sumują się do **1.24** przy domyślnych, więc nieznormalizowana suma obcinałaby każdy wynik | `decision/sequence.py:599` |
| AUD-M8 | Logika half/double-time była **skopiowana** w set_builder i innych → wyciągnięta do `_common.py` | `decision/_common.py:3` |
| AUD-M9 | `--context` był przyjmowany i **po cichu ignorowany**; `engine.random_seed` był reklamowanym, ale nieużywanym pokrętłem | `core/pipeline.py:199-203`, `cli/analyze.py:79`, `api/schemas.py:49` |
| AUD-M10 | Każdy ważony człon musi mieć wpis w `formula_terms.yaml` — **egzekwowane testem**, brak anonimowych zmiennych | `set_builder.py:63`, `sequence.py:50` |
| AUD-H3 | `bpm_hint` był walidowany, a potem **wyrzucany** | `api/routes_tracks.py:61` |
| AUD-H4 | Stały oceniający nie wyraża rankingu → wstrzymanie się, nie 0.0 | `tests/test_quickwins.py:162-169` |
| AUD-L7 | Późna noc 00:00–03:59 to peak — 03:xx wpadało wcześniej do „builder" | `context/conditioning.py:122` |
| AUD-L11 | 0 okien silnika → 0/0 jest niezdefiniowane, nie zmyślone 0.0 | `tests/test_annotations.py:148` |

---

## VIII. NAJCZYSTSZE OBALENIE W CAŁYM REPO — pole korpusu, które wyglądało na pomiar

`src/dancelab/core/phrasing.py:99-111` + `tests/test_corpus_transition_length.py:1-12`

> **Założenie:** korpus zna medianę długości przejścia (`transition_length_beats_median = 94`) i ta liczba **została na chwilę wpięta** w ocenę fraz.
> **Audyt źródłowego pola:** `across 11,405 corpus transitions, 14.3% of transition_length_beats are NEGATIVE (down to −14526) and 28.7% exceed four minutes (up to 15771).`
> **Diagnoza:** `The field measures the gap between two aligned regions — negative when alignments overlap, enormous when unaligned material sits between them — not how long a DJ blended.`
> **Wynik:** `CLASSIC_TRANSITION_BEATS = (8.0, 16.0, 32.0)` — liczby, które DJ **wyliczą ręką**, jawnie oznaczone jako `structural, not measured, and they are deliberately NOT extended with the corpus figure`.

**Perełka inżynierska:** liczba nie została skasowana, tylko **odcięta od ścieżki oceniającej i przypięta testem**. `corpus_priors.transition_length_beats()` dalej ją czyta (`corpus_priors.py:88-94`), ale **nie ma ani jednego wywołania produkcyjnego** — jedyny caller to `tests/test_corpus_transition_length.py:35`. Drugi test (`:40-45`) pilnuje, że `preferred_transition_beats()` wciąż zwraca dokładnie `{8, 16, 32}`, z komunikatem błędu `a corpus-derived length leaked into scoring`. Dowód: `grep -rn "transition_length_beats" src tests scripts` — w `src/` tylko definicja i komentarz.

---

## IX. TRZY RZECZY, KTÓRE ZNALAZŁEM I KTÓRE WARTO ROZSTRZYGNĄĆ

**1. Bezwładna ścieżka oceny NIE została usunięta — dołożono przed nią sito.**
`sito_brzmienia.py:3-7` mówi, że premia do oceny nie zmieniała setu, ale `steering.adjust()` dalej jest wołane w `set_builder.py:999`, a `DEFAULT_ANCHOR_WEIGHT = 0.35` dalej stoi w `steering.py:37`. To prawdopodobnie **jest poprawne** (sito usunęło korzeń problemu — utwory bez wektora opuszczają pulę, więc premia nie konkuruje już z nieskorygowanymi 1,000), ale żaden komentarz tego nie mówi wprost. Ktoś czytający `sito_brzmienia.py` może uznać, że ścieżka premii jest martwa — nie jest.

**2. Jedna liczba w tabeli sita wyłamuje się i komentarz tego nie tłumaczy.**
`sito_brzmienia.py:35`: przy udziale **50% wychodzi `0,0/10` wspólnych utworów**, podczas gdy przy 30%, 20%, 10% i 5% wychodzi `0,3/10`, a przy 100% — `1,0/10`. Jeśli mniejsze sito ma dawać większą rozróżnialność, 50% powinno leżeć między 100% a 30%, a leży poza. Albo to szum przy małej próbce (3 kotwice), albo literówka — w obu przypadkach warto dopisać jedno zdanie, bo to jedyna liczba w tym module bez wyjaśnienia.

**3. Drobny rozjazd w opisie tego samego pomiaru łuku.**
`set_builder.py:520` mówi `Measured three independent ways`, a `tests/test_luk_off.py:5` mówi `on two independent instruments`. Sam wynik (build gorszy niż płaska linia, mediana 5 spadków >8%) jest w obu miejscach zgodny — rozjeżdża się tylko liczba narzędzi.

---

## X. CZEGO NIE MA W KODZIE

**System „In Between" — `P = (C, D, Syn, U)`, rama `F`, próg `theta` — nie ma w repo żadnego śladu.**
Dowód: `grep -rniE "in.between|theta|θ|rama F|próg" src tests --include="*.py"` zwraca wyłącznie trafienia niezwiązane (`próg` w znaczeniu „threshold" w `test_slabe_szwy.py`, `syncopation_proxy` jako cecha sygnału w `features/microtiming.py:115` i `core/models.py:330`). Nie ma modułu, klasy, stałej ani komentarza z tym formalizmem.

Najbliższą realizacją tej samej idei w kodzie jest **domena szwu**, ale zapisana zupełnie innym słownikiem: `transition_score` (harmonic/bpm/energy/mixability), `SeamVerdict`, `transition_length.stability_runway_beats` i `stems/envelopes.share_delta`. Jeśli „In Between" ma być traktowane jako spec, to **spec i kod jeszcze się nie spotkały** — i to jest chyba najważniejsza luka, jaką kronika komentarzy ujawnia przez milczenie.