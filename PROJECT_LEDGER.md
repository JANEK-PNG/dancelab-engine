# REJESTR PROJEKTU — DanceLab

**Cel:** żadna istotna decyzja nie zapada niewidocznie. Janek nie czyta kodu —
ten plik to jego panel kontrolny.

**Zespół:** Janek (szef — decyzje/weto) · Klaris (silnik/dane/analiza) ·
Kord (bramka/walidacja/statystyka; śpi do 29.07).

**Reguły (obowiązują Klaris i Korda):**
1. **Koniec każdej sesji = RAPORT DNIA** — każdy pracownik pisze Jankowi, co
   zrobił (sekcja 6), + wpis do dziennika (sekcja 7).
2. Początek sesji = przegląd rejestru + `docs/` po dacie modyfikacji.
3. Każda karta pracy ma WŁAŚCICIELA (Klaris / Kord / Janek).
4. Statusy decyzji: ✅ `zatwierdził Janek` · ⚠️ `przyjęta domyślnie` (podlega
   wetu Janka) · 🔒 `zamrożona przez Korda` (zmiana wymaga Korda).
5. Swoboda WYKONANIA — tak. Swoboda DECYZJI — nie: rzeczy istotne trafiają
   najpierw do sekcji PYTANIA.

**Widok Janka:** artefakt „Tablica zespołu" (kolumny = osoby). Ten plik = kopia
tekstowa dla Korda; obie formy trzymamy w synchronizacji.

---

## 1 · DECYZJE

### ✅ Zatwierdzone przez Janka
| data | decyzja |
|---|---|
| 07-16 | Inspiration Board: tylko zmierzone dane, silnik neutralny, talia inspiracji = jawna warstwa profilu (nie ukryty bias) |
| 07-17 | Konwencja pozytywnego języka: „preferencja/nagroda", nigdy „kara" |
| 07-17 | Preferencja tej samej oktawy BPM (0.9) + dedup audio wpięte do silnika (ρ 0.30→0.42) |
| ~07-13 | Pobranie całego korpusu djmix na dysk zewnętrzny; stop przy blokadzie YouTube („mamy dość", ~12.6k tracków) |
| 07-20 | CLAP (laion/clap-htsat-unfused) jako embedding E |
| 07-21 | Siatka testów Qt uruchamiana w Dockerze/Linux (macOS provenance blokuje offscreen; 54 testy zielone) |
| 07-21 | Eksperyment PySide6 6.11 → porażka (degraduje tak samo) → powrót do 6.7.3 |
| 07-21 | **35 ślepych ocen Janka WYCOFANE z pętli strojenia** (skażone zepsutym beatgridem; n=1). Strojenie: korpus vs przypadek. Walidacja: 1604 realne wybory DJ-ów. Świeży odsłuch tylko do oceny renderów — później |
| 07-21 | CLAP na PEŁNYM korpusie (~12.6k), nie tylko 2881 pod bramkę |
| 07-21 | Wizja „kotwice": Generate → ranking kandydatów → Janek wybiera 2–3 kotwice (siła: luźna/twarda, bez pozycji) → set rośnie wokół; dobór = liczby (filtr) + brzmienie (sortowanie) |
| 07-22 | **Pełny korpus CLAP GOTOWY: 12 668 wektorów, 0 błędów (zweryfikowane).** `corpus_embeddings_full.json`, osobno od zamrożonego 2881 Korda. Odblokowane: 12k-sąsiedztwa kotwic + centroidy brzmienia mistrzów |
| 07-22 | **Prior energii: zmierzony → PŁASKI → NIE wchodzi do silnika.** Kwintyle Δenergii DJ-e vs przypadek: lifty 0.94–1.04 (szum). Wniosek architektoniczny: energia działa na poziomie ŁUKU setu (silnik ma w `arc`/`_energy_score`), nie na poziomie par. Drugi zmierzony wynik negatywny — zasada „płasko ⇒ nie dodajemy" ustalona PRZED pomiarem i dotrzymana |
| 07-22 | **Werdykt R&D exp01 przyjęty do produkcji:** MuQ-MuLan vs CLAP na bibliotece (296) → **CLAP zostaje** (sound-alike remis 11:10, MuQ ma hubness, licencja CC-BY-NC = ślepa uliczka). Zero zmian w silniku. Embeddingi MuQ zachowane (przyszły ensemble, zaparkowane). Caveaty recenzji Klaris: n=6 kotwic; eksperyment na nie-zdedupowanej bibliotece (dupy w tabelach obu modeli) — następne eksperymenty R&D na dedupie. Raport: `RnD-DanceLab-Pro/experiments/01-muq-vs-clap/results/report.md` |
| 07-22 | **Reguła albumowa (rzemiosło):** max z 1 albumu/składanki: 1 na ~10 tracków, 2/20, 3/30, 4/40 — twardy sufit 4 do setki. Klauzula ekstremalna: 2. z albumu TYLKO zamiast outliera tempa, nigdy 3. WHY (Janek): „nikt nie chce być oskarżony, że gra playlistę z jednej płyty — nie ma w tym nic kreatywnego". + Okno tempa ±18% od kotwicy (fold); brak kandydatów ⇒ set KRÓTSZY zamiast śmieciowych przejść. Zaimplementowane w generatorze; docelowo do warstwy selekcji silnika |
| 07-21 | Ten rejestr + rytuał przeglądu |
| 07-21 | **Zmierzone lifty WPIĘTE w produkcyjny silnik** — `decision/corpus_priors.py`, mnożnik `lift^waga` w `transition_score` TYLKO w trybie smart (czyste tryby harmonic/bpm = jawna wola usera, nietknięte), klamra 0.4–2.0, neutralne przy braku danych, `corpus_priors_weight: 1.0` w wagach. 6 nowych testów, regres warstwy decyzji zielony (76). Do recenzji Korda 29.07 |

### ⚠️ Przyjęte domyślnie — DO PRZEGLĄDU / WETA JANKA
| data | decyzja | kto | ryzyko/uwaga |
|---|---|---|---|
| ~07-19 | E-pass CLAP ograniczony do 2881 (uniwersum bramki), nie cały korpus | Kord+Klaris | naprawione 07-21 (pełny korpus), ale wzorzec „dane pod aparaturę, nie produkt" wystąpił 3× |
| od początku | Ręczne wagi silnika (blend bpm 0.4 / harmonia 0.4 / energia 0.2 itd.) — wymyślone, nieoparte na danych | Klaris (historycznie) | zmierzone: ledwo lepsze od losowania (0.442 vs 0.490); zamiana na zmierzone — W TOKU |
| 07-21 | Rozszerzenie loadera o webm/m4a/opus/ogg — kaskaduje na bramkę Korda (`ENGINE_AUDIO_EXTENSIONS`) | Klaris | konieczne dla H (korpus=webm), ale zmienia zachowanie zamrożonej aparatury — Kord powinien porachować |
| 07-21 | Konwersja review Korda → `dj_map.json` i podanie bramce (`--dj-map`) → DJ 0/433→337/433 | Klaris | czysta hydraulika jego adjudykacji; bez nowych decyzji o zaufaniu |
| 07-21 | Metodologia priors: baseline = losowe pary wewnątrz-miksowe; lifty = iloraz rozkładów; scorer = iloczyn liftów (Naive Bayes) | Klaris | Kord powinien zrecenzować (jego działka statystyczna) |
| 07-21 | Playlist-generator: max 1 track/artystę, pliki >15 min = nie-tracki, przycinanie do celu czasu po podobieństwie | Klaris | drobne, ale kształtują wynik który słyszysz |
| wcześniej | Terrain = zatwierdzony domyślny UI (wg docs Korda) | Kord (podpisane jako zatwierdzone) | Janek: potwierdź, że to faktycznie Twoja akceptacja, nie tylko zapis Korda |

### 🔒 Zamrożone przez Korda (zmiana = jego decyzja, wraca 29.07 ~13:00)
| co | stan |
|---|---|
| Uniwersum bramki: 2881 tracków / 433 miksy / fail-closed / progi pre-rejestrowane | konflikt: 26 tracków bez pewnego beatgridu (H max 2855) + 96 miksów b2b bez pojedynczego DJ-a → bramka żąda kompletu, adjudykacja mówi „legalnie nie istnieje". Re-scope albo polityka „excluded=rozstrzygnięte" |
| Proxy repertuaru: 86 obserwacji < próg 100 (nie obniżono po wyniku — dobrze) | czeka |
| Zamrożone artefakty (embeddings.json 2881, dataset, fingerprints) | Klaris ich NIE nadpisuje — osobne katalogi |

---

## 2 · ZAPARKOWANE (odłożone ŚWIADOMIE — nie „zapomniane")
| co | czemu czeka | odblokowuje |
|---|---|---|
| Wpięcie zmierzonych liftów w produkcyjny `set_builder`/`mixability` + prior energii | zatwierdzone kierunkowo, przerwane rejestrem | Klaris, zaraz |
| **BPM cross-check przy słabym gridzie** — case „Red Light Fever": silnik 120.01, realnie 117.45 (+2.2%), quality 0.5555 a `reliable=True` przepuściło; ucho Janka złapało. Fix: cross-walidacja tempogramem gdy quality&lt;0.7, rozjazd &gt;1.5% ⇒ unreliable | realny przypadek 22.07, cache poprawiony z prowenancją | Klaris/Kord |
| Przeliczenie setu Four-Tet z pełnego 12k-sąsiedztwa | pełny CLAP liczy się w tle (ETA ~2h od 21.07) | koniec runu |
| Gotowy zróżnicowany set 1h (max 1/artystę) — POLICZONY, nieobejrzany | Janek pivotował na dane | 1 komenda |
| Faza 0 Terrain (ProjectSession, CueDecisionStore, ExportManifest) | Kord 29.07 + dziury pokrycia | Kord |
| **Centroidy brzmienia mistrzów** — ✅ policzone (549 mistrzów, `master_centroids.json`, `scripts/master_sound_centroids.py`) + ✅ demo-konsument DZIAŁA: centroid odtwarza scenę mistrza z dokładnością do wytwórni (Beyer→Drumcode/Intec, Armin→Armada/FSOE, John B→Hospital/Shogun). Caveat: przestrzeń ściśnięta (0.86–0.97) → używać do RANKINGU, nie progów. Zostało z definicji „użyte": bias selekcji w inspiration board | 22.07 | Klaris → board |
| **12k-sąsiedztwa (digging)** — ✅ ZBUDOWANE i działa (`scripts/digging_list.py` → `digging_list.md` + artefakt ⛏️): 25 tracków z setów realnych DJ-ów najbliższych bibliotece Janka, których nie posiada, z „bo brzmi jak twój X"; wykluczanie posiadanych (cos>0.985), dedup, tylko metadane (etyka). Dowód jakości: sam znalazł kolejne tracki artystów, których Janek MA (G-Man, Herbert) — po brzmieniu. v2 (23.07): anti-hub cap=2 z fallbackiem (różnorodność wyjaśnień 12→19/25) + **wariant z kotwicą** (`--anchor`, seed=kotwica+4 sąsiadów) — leftfield czysty: Ron Trent, Pépé Bradock, Buttrich&Jonson, HNNY, Deetron; EDM zniknęło. Dwa artefakty: ⛏️ cała biblioteka + 🌱 kotwica | 23.07 | Klaris |
| **Cue Export → Rekordbox: PLAN IMPLEMENTACJI GOTOWY** (R&D 23.07, handoff dla Korda): droga = zapis `djmdCue` w `master.db` przez pyrekordbox (decyzja Janka; USB-direct odłożony). Fakty udowodnione (Kind→pad, InMsec/InFrame, warunki zapisu, backupy RB); 1 niewiadoma: USN (metoda: reverse z pyrekordbox). Fazy 0–5 z bramkami, ~5–8 dni. Plan: `RnD-DanceLab-Pro/notes/IMPLEMENTATION_PLAN_cue_export.md`. Brief źródłowy: `docs/RND_CUE_DELIVERY_USE_CASE.md`. **Do zszycia przez Korda: polityka konfliktów planu ≡ CueDecisionStore z Fazy 0 (jedno źródło prawdy).** Klaris buduje engine-side kontrakt SetExport przed 29.07 | plan przyjęty przez produkcję 23.07 | Kord (impl) + Klaris (SetExport) |
| Dziury siatki: golden-snapshot AC1, e2e-guard AC9, testy `_AnalysisThread`, roundtrip `current_step` | audyt z 21.07; do zrobienia przed Fazą 0 | ktokolwiek |
| Formalny design „kotwic" (brainstorm przerwany w połowie) | wizja spisana, spec nie | Janek+Klaris |
| Inspiration Board v1 | czeka na: profile mistrzów wpięte + pełny CLAP | po lewej |
| DJ Style Dex (wizualne karty 551 mistrzów) | przerwane w połowie budowy | 1 sesja |
| Graf artystów Last.fm (crawler gotowy, depth 2) | brak klucza API (darmowy, 2 min) | Janek: klucz |
| Badanie 5 oceniających | po stabilizacji silnika na zmierzonych wagach | później |
| Korpus v2 (1001Tracklists) · projekt PRZEJŚCIA · higiena gita (branch calibration niezmergowany, sterta nowych skryptów) | backlog | później |

---

## 3 · ZAŁOŻENIA (na czym jedziemy)
1. **ADR-005:** nie wiemy → `None` + ostrzeżenie. Nigdy nie zmyślamy liczb.
2. **Silnik neutralny;** gust (Janka czy każdego usera) = jawna warstwa profilu.
3. **Etyka korpusu:** tylko cechy (features), audio korpusu NIGDY nie gra w apce.
4. **Eksport NIGDY nie rusza BPM/beatgridu** — twardy invariant.
5. Opublikowane sety = klasa pozytywna; kontrast = przypadek (nie ludzkie oceny).
6. Testy Qt żyją w Dockerze; lokalny macOS = tylko spot-check (nigdy nie re-signować dylibów!).
7. Mentor mode: kwestionuj wszystko; wykonanie swobodne, decyzje — nie.

---

## 4 · PYTANIA DO JANKA (kolejka)
| # | pytanie | kontekst |
|---|---|---|
| 1 | Weta do sekcji ⚠️? Przejrzyj tabelę „przyjęte domyślnie" — każdą możesz cofnąć | ten wpis |
| 2 | Terrain: potwierdzasz „zatwierdzony domyślny UI", czy to wisiało na słowie Korda? | ⚠️ tabela |
| 3 | Konflikt bramki (26+96): czekamy na Korda 29.07, czy przygotować mu rekomendację re-scope do zatwierdzenia? | 🔒 |
| 4 | Klucz Last.fm — robisz? (odblokowuje graf artystów) | zaparkowane |
| 5 | Rytm przeglądu rejestru: koniec każdej sesji czy raz w tygodniu? | reguły |
| 6 | Włączyć CI z powrotem? Wymaga `gh auth refresh -s workflow`, potem `git mv docs/github-ci.yml.txt .github/workflows/ci.yml` + push | sanacja gita 23.07 |
| 7 | Standardy Apple (Developer ID $99/rok + notarization + test bundla na czystym Macu) — kiedy na serio? Bez tego appka „działa tylko u Janka" | audyt 23.07 |
| 8 | Sprzątanie trupów: `.venv_uv_blocked`, `tmp/`, `dist/`, stare `AUDIT_REPORT*.md`, 103MB designu w root → do `design/` poza repo? | audyt 23.07 |
| 9 | **`validation/review_ui/swipe_review.py` — 3474 linie generatora HTML do ocen swipe'em. Twoje oceny wypadły z pętli strojenia (zastąpił je korpus), kod żyje tylko przez `pilot_pack.py`. Wycinamy?** | czystka UI 24.07 |
| 10 | Po wycięciu Qt: `validation/` to 44% repo (14 456 linii) i jest to aparatura badawcza, nie produkt. Zostaje w repo silnika czy wydzielamy? | mapa modułów 24.07 |

---

## 6 · RAPORTY DNIA (pracownik → Janek)

**Klaris → Janek · 2026-07-21:** Naprawiłam siatkę Qt (Docker, 54 zielone).
Zamknęłam pętlę priors — 6144 realnych przejść, wagi zmierzone prowadzą nad
ręcznymi (percentyl 0.427 vs 0.442, p=0.12 — jeszcze bez dowodu). Zmierzyłam,
że brzmienie CLAP należy do selekcji, nie oceny par (negatyw uratował złą
wagę). Wpięłam review Korda → bramka DJ 0→337/433. Puściłam pełny CLAP 12.6k
(w tle). Postawiłam rejestr + tablicę. **Jutro:** lifty w produkcyjny silnik +
prior energii.

**Kord → Janek · 2026-07-20 (ostatni przed snem):** Domknąłem adjudykację 433
miksów (337 solo / 96 wykluczonych, fingerprint zamrożony). Zbudowałem
revealed-repertoire + bramkę pięciu modeli. 21–24.07 śpię (limit tokenów),
raport wznawiam 29.07.

## 8 · MAPA MODUŁÓW (stan 2026-07-24, po wycięciu Qt)

18 modułów · **32 636 linii** w `src/` (146 plików) · testy 70 plików / 11 443 linie · skrypty 29 / 4 552.
Przegląd „moduł po module" idzie paczkami — żeby ogrom nie przerażał:

| paczka | moduły | linie | status |
|---|---|---|---|
| **A. Ścieżka Rekordbox** | ingestion 1144 · cli 1133 · preview 601 · export 429 | 3 307 | ✅ **zamknięta 24.07** |
| **B. Mózg silnika** | decision 6558 · descriptors 329 · context 376 | 7 263 | ⚠️ **oś „uczciwość" zamknięta (7 napraw)**; 5 osi wciąż otwartych |
| **C. Audio pipeline** | core 1919 · preprocessing 550 · features 760 · stems 705 | 3 934 | czeka |
| **D. Dane i powierzchnie** | storage 638 · data 363 · api 1210 · visualization 871 · workflows 527 · contracts 30 | 3 639 | czeka |
| **E. Validation** | djmix 8273 · review_ui 3474 · raveform 950 · tempo 498 · luzem 1261 | 14 456 | czeka (2-3 podejścia) |

Zasada przeglądu: martwy kod / duplikaty / błędy / uczciwość(ADR-005) + inwarianty / uproszczenia / testy —
każde znalezisko **adwersarialnie weryfikowane** zanim trafi do naprawy (bez zgłaszania fałszywek).

⛔ **BEZ fan-outów agentów.** Trzy równoległe przeglądy zjadły 2,7 mln tokenów i 5-godzinny limit Janka
w jednym posiedzeniu; dwa z trzech padły w połowie i zwróciły `{"confirmed_sorted":[]}`, co **wygląda
identycznie jak „kod czysty"**. Przegląd robimy ręcznie i sekwencyjnie — tak powstało wszystkie 9 znalezisk
paczki A. Fan-out tylko za wyraźną zgodą Janka i z podaną ceną.

### 8b · OBRAZ ARCHITEKTONICZNY (zmierzony 2026-07-25)

Pytanie Janka: *„czy DanceLab to jeden funkcjonujący organizm?"* — zmierzone grafem importów, nie zgadywane.

**Krwiobieg produktu działa:** `ingestion → preprocessing → features → stems → descriptors → decision →
export/cues`. Zero sierot na poziomie pakietów, każdy moduł ma realnych konsumentów. Rdzeń JEST spięty.

**Ale cztery asymetrie — i to one są odpowiedzią:**

| | co zmierzone | znaczenie |
|---|---|---|
| **1. Badania = 44% kodu, wpływ przez JEDEN plik** | `validation/` 35 plików / 14 456 linii; **kod produktu nie importuje jej ani razu**; cały wpływ płynie przez `data/reports/corpus_priors/priors_v1.json` (skrypt pisze → `decision/corpus_priors.py` czyta) | Architektura **dobra** (badania nie każą silnika), ale **niewykorzystana**: korpus zmierzył medianę przejścia 94 bity, 551 profili DJ, centroidy brzmienia, 12 668 wektorów CLAP — przez rurkę przeszły tylko lifty BPM i harmonii |
| **2. `context/` — mały moduł przyćmiony** | 376 linii, wpina się w `mixability` i realnie zmienia wynik; **`ContextProfile` powstaje WYŁĄCZNIE w `api/` i `validation/`** — ścieżka CLI nigdy go nie podaje | Warstwa wiedząca, że festiwal 15:00 ≠ zamknięcie 4:00, jest **ciemna w produkcji**. Nie martwy kod — narząd podłączony do mózgu, nigdy niekarmiony |
| **3. `preview/` — narząd bez ust** | 601 linii, renderuje AUDIO przejścia; konsumenci: 2 skrypty weryfikacyjne, **zero komend CLI** | Realna wartość (usłysz szew zanim zagrasz) bez wejścia dla użytkownika |
| **4. `api/` — narząd w słoiku** | 9 plików, po wycięciu Qt **bez konsumenta** | Świadoma decyzja (droga powrotna dla frontendu), dziś koszt bez odbiorcy |

**Werdykt.** Jako **silnik** — organizm żyje: analiza→decyzja→eksport ma jeden dowiedziony wylot (cue do
Rekordboxa) i wewnętrzną spójność. Jako **produkt** — jeszcze nie, bo organizm poznaje się po tym, że bodziec
zmienia zachowanie całości: dziś powiesz „gram na festiwalu" i nic się nie zmieni, bo nie ma jak to powiedzieć.
**Sprawny układ krwionośny i mózg, zmysły odłączone od skóry.**

**Kolejność podłączania zmysłów:**
1. ✅ **`context` → CLI** (flaga `--context`) — najtańsze, największy efekt: cały istniejący, przetestowany kod warunkowania zaczyna działać. *Zrobione 2026-07-25.*
2. ❌→✅ **Długość przejścia: liczba 94 WYCOFANA po audycie; zamiast niej jawna reguła rzemieślnicza.** *2026-07-28.* Rano wpięta mediana 94 bity z priorsów; audyt pola źródłowego tego samego dnia: na 11 405 przejść korpusu **14,3% długości UJEMNYCH** (do −14 526), **28,7% dłuższych niż 4 min** (do 15 771), tylko 42,4% w fizycznym 8–256 — pole mierzy odstęp między dopasowanymi regionami, nie długość blendu; mediana liczona filtrem truthy Z ujemnymi. Wycofane, scoring wrócił do fraz 8/16/32; audyt został w kodzie. **Zamiast tego (decyzja Janka): `decision/transition_length.py` — zapas stabilności.** Reguła jawna („craft rule, not a measurement" w każdym wyjściu): zapas = ile bitów od cue obwiednia RMS trzyma poziom; długość pary = minimum z obu stron, przyciete do fraz renderu. **Strona wchodząca (B) ma prawo BUDOWAĆ** (doprecyzowanie Janka): tylko skoki i załamania w dół kończą jej zapas; wychodząca (A) musi trzymać poziom w obie strony. `dancelab preview` bez `--beats` = auto z reguły + wypisany powód; brak danych → głośny fallback 64. 10 testów.
3. ✅ **`preview` ma komendę CLI.** *Zrobione 2026-07-25.* `dancelab preview A B [--profile --beats]` — analizuje oba tracki, bierze własne okna mix-out/mix-in silnika, snapuje kanonicznym `snap_cue_start` (niewiarygodna siatka nie snapuje nic), dopasowuje długość do realnego zapasu obu plików i pisze jeden WAV zblokowany na frazę; raportuje gdzie wyszedł i wszedł, żeby liczby dało się skonfrontować z uchem. **Zweryfikowane na realnej muzyce Janka:** Kola 2:37 → Nuits Sonores 1:11, 64 bity @ 117.2 BPM.
4. **Decyzja o `api`** — albo dostaje konsumenta, albo idzie do archiwum jak Qt. → PYTANIE do Janka.

---

### 8a · PACZKA B — 7 napraw ✅ ZROBIONE (2026-07-25)

Wszystkie siedem naprawione, każda z testem, suite **530 zielonych**. Poniżej dla historii —
co było zepsute i jak naprawione. **Dwie zweryfikowane mutacją** (cofnięcie poprawki wywala test): #4
oraz strażnik inwariantu z paczki A.

**Dług świadomie zostawiony:** `decision/set_builder.track_energy` ma to samo `else 0.0` co naprawiony
`build_set`; używa jej `sequence.py` w 8 miejscach (m.in. `observed_energy_profile`), więc zmiana sygnatury
na `float | None` to osobna robota z realnym zasięgiem. Nie zmieniałam na ślepo. **DO ZROBIENIA.**

**Wciąż nieprzejrzane osie paczki B:** martwy kod, duplikaty, correctness, uproszczenia, testy —
ich agenci padli na limicie, żadne z ich znalezisk nie przeszło weryfikacji, więc nie są policzone.
Przejrzana i naprawiona jest **tylko oś „uczciwość"**.



Wspólny wzorzec: **liczba wygląda na zmierzoną, choć pomiaru nie było** — naruszenia ADR-005.
Zweryfikowana adwersarialnie była **tylko oś „uczciwość"**; osie martwy-kod / duplikaty / correctness /
uproszczenia / testy padły na limicie w fazie weryfikacji, więc ich znaleziska **odrzucono jako niepewne** —
te osie paczki B są nadal DO ZROBIENIA.

| # | plik | rzecz | naprawa |
|---|---|---|---|
| 1 | `decision/transition_cues.py:114` | **HIGH.** `requires_manual_listen` zwalniane, gdy B nie ma okna mix-in: warunek sprawdza `b_source`+`out_window`+`grids_reliable`, ale **nie `in_window`**. Ścieżka „najwcześniejszy hot cue" (linie 69-76) ma własny komentarz „still needs a listen", a mimo to zwalnia. Zweryfikowane ręcznie przez Klaris w kodzie. | dodać `in_window is not None` do warunku + test ścieżki bez okna mix-in |
| 2 | `decision/mixability.py:213` | `phrase_fit` liczony z siatki bez sprawdzenia `reliable`/`downbeat_phase_verified`, a wynik liczy się jako komponent „available" → **podnosi coverage i confidence** | przekazywać beatgrid tylko gdy `reliable`, inaczej fallback na granice segmentów + warning |
| 3 | `decision/transition_windows.py:126` | to samo dla `S_phrase`: `phrase_alignment_curve` dostaje `inp.beatgrid` bez bramki; warning tylko gdy grid = None, więc **niewiarygodna siatka podbija pewność okien** | bramka na `reliable`; warning liczony do coverage |
| 4 | `decision/edge_decision.py:313` | premia pewności 0.15 za „realne zmierzone okno pary" przyznawana **także syntetycznemu fallbackowi** (score 0.5/risk 0.45 zmyślone); gałąź 0.35 praktycznie martwa | flaga `pair_is_fallback` → gałąź 0.35, albo przemnożyć przez confidence syntetycznego okna (0.2) |
| 5 | `decision/set_builder.py:245,890` | brak klatek RMS → `track_energy` zwraca **0.0 zamiast None+warning**; taki track **kotwiczy `e_min`**, wykrzywia profil łuku całej puli i produkuje zmyślone `energy_delta` | `track_energy → None`; wykluczyć z `e_min`/`e_range`/łuku + warning; `sequence.py` też (importuje ją) |
| 6 | `decision/transition_windows.py:485`, `edge_decision.py:83` | każde okno dostaje `tempo_window_feasibility=medium`, choć **nie ma wejścia o parze temp**; pole jest Optional właśnie na wypadek „nie wiem" | usunąć stałą, zostawić `None` |
| 7 | `decision/transition_cues.py:111` | `TransitionCue.confidence` = `transition_score` pary — **wynik zgodności użyty jako pewność cue**, więc cue „window_only" wymagające odsłuchu może raportować 0.9 | liczyć z własnych przesłanek cue (źródło, oba okna, siatki) albo przemianować pole |

---

## 7 · DZIENNIK WPISÓW
- **2026-07-25 wieczór (Klaris): 7 NAPRAW UCZCIWOŚCI W MÓZGU SILNIKA — 530 zielonych.** Cała sekcja 8a zrobiona, ręcznie, bez agentów, każda naprawa z testem. **Wzorzec był jeden i systemowy: brakujące dane dostawały „rozsądną" wartość domyślną, która potem PODNOSIŁA pewność — czyli silnik był tym bardziej przekonany, im mniej wiedział.** Konkretnie: (1) `transition_cues` zwalniało `requires_manual_listen` dla hot cue wybranego BEZ okna mix-in, wbrew własnemu komentarzowi „still needs a listen" — cue bez potwierdzenia raportowało się jako zweryfikowane; (2+3) `mixability.phrase_fit` i `transition_windows.S_phrase` liczyły frazy z siatki bez sprawdzenia `reliable` — dowód liczbowy: **0,518 wyprodukowane z siatki, którą analiza oznaczyła jako szum**, i co gorsza liczyło się to jako komponent OBECNY, więc podbijało coverage i confidence dokładnie tam, gdzie siatce nie wolno ufać; obie ścieżki używają teraz `usable_beat_grid` z `decision/cue_grid` (bramka z paczki A) zamiast czwartej kopii tej samej reguły; (4) `edge_decision` — człon pewności nagradzający „realne zmierzone okno pary" trafiał też do syntetycznego fallbacku, bo `best_pair` było nadpisywane przed policzeniem pewności; **gałąź 0.35 była praktycznie martwa, co samo w sobie było sygnałem** (człon mający odróżniać dowód od jego braku nigdy nie umiał zgłosić braku); pewność spadła 0,64 → 0,55, **zweryfikowane mutacją**; (5) `build_set` podstawiał `0.0` za brak RMS i **brał z tego `e_min`**, więc jeden niezmierzony track stawał się podłogą skali energii CAŁEJ puli i przy łuku „build" pchał się na otwarcie — teraz skala liczona wyłącznie z realnie zmierzonych, nieznane siedzą na medianie i są wymienione w warningach; (6) każde okno dostawało `tempo_window_feasibility=medium`, choć wykonalność tempowa to własność PARY, a detektor widzi jeden track — pole `None`; (7) `TransitionCue.confidence` to była zgodność pary, więc cue „window_only" wymagające odsłuchu mogło raportować 0,9 — liczone teraz ze słabszego z okien definiujących cue, `None` gdy nie ma na czym oprzeć. **Dług zostawiony świadomie:** `track_energy` ma to samo `0.0` i karmi `sequence.py` w 8 miejscach — osobna robota, nie zmieniałam na ślepo. **Zakres uczciwie:** to była oś „uczciwość"; pięć pozostałych osi paczki B nadal nieprzejrzanych.
- **2026-07-25 (Klaris): PACZKA B PRZEJRZANA — 1 naprawa, 7 czeka; nauczka o koszcie agentów.** Ręcznie zweryfikowany rdzeń decyzyjny jest **czysty**: `corpus_priors` trzyma kontrakt co do litery (smart-only, `lift**weight`, klamra 0.4–2.0, neutral przy braku danych) i **używa dokładnie tej samej formuły bucketa co skrypt pomiarowy** oraz wspólnego `nearest_bpm_variant`; `harmonic` uczciwy (brak klucza → unknown → 0.5, niska pewność tłumi zamiast udawać, symetria AUD-H1 przypięta testem); pętla zachłanna deterministyczna `(-score, id)` z losowością tylko w epsilon-remisach; bramki `hard_block`/`suppress` w `next_track` na miejscu; **martwy kod: zero, ciche skipy: zero**. Naprawione: komentarz przy `SetTransition.harmonic_relation` dokumentował słownik (`same/adjacent/energy_boost/dissonant`), który **nie występuje nigdzie w kodzie** — realny słownik to ten z `decision/harmonic.py`, identyczny z kluczami pomiaru priorsów. **7 znalezisk czeka na naprawę — patrz sekcja 8a.** Wszystkie z osi „uczciwość", wszystkie ten sam wzorzec: liczba wygląda na zmierzoną, choć pomiaru nie było. **Koszt:** trzy równoległe przeglądy agentami = **2,7 mln tokenów i cały 5-godzinny limit Janka**; dwa padły w połowie i zwróciły pusty wynik nie do odróżnienia od „kod czysty" (dwa razy prawie zaraportowałam to jako czystość). Reguła spisana w sekcji 8: **bez fan-outów, przegląd ręczny**. Zacommitowane też trzy zmiany z równoległej sesji Codexa (bundle WAL dla backupów, wybór urządzenia torch dla demucs) + odświeżony `uv.lock` po wycięciu PySide6 — leżały niezacommitowane i **wracały do kontekstu przy każdej turze**. Suite **522 zielone**.
- **2026-07-24 noc (Klaris): PACZKA A PRZEJRZANA — 9 realnych błędów, 8 commitów.** Przegląd równoległy (6 agentów) **padł na limicie sesji i zwrócił „0 znalezisk"** — to była fałszywa informacja, nic się nie wykonało; przegląd zrobiony ręcznie. **Znaleziska:** (1) **trzy implementacje snapowania cue** — eksporter XML miał przemyślaną (frazy 64/32/16/8/4/2, bramkowaną zweryfikowaną fazą, odmawiającą niewiarygodnej siatki), a ja w nowej ścieżce master.db napisałem od zera słabszą, która **nie sprawdzała `beatgrid.reliable`** → snapowała cue do bitów siatki uznanej przez silnik za szum; scalone w `decision/cue_grid.py`, obie ścieżki konsumują jedną regułę (XML bez zmian zachowania, master.db zyskuje frazy + strażnika). (2) **Writer kasował cue DJ-a bez pozwolenia** — `_apply` czyścił pad bezwarunkowo, opierając się na regule egzekwowanej w INNEJ warstwie; pozwolenie jest teraz jawną daną (`PlannedCue.replace_existing`, nadaje wyłącznie `resolve_conflicts`), a writer bez niego odmawia i nazywa blokujący pad. (3) **18 testów znikało po cichu** — wszystkie testy zapisu do biblioteki wyłączały się bez `master.db` (CI, świeży klon, otwarty RB): reguły bezpieczeństwa wyciągnięte do czystego `decision/cue_write_ops.py` (7 testów działa wszędzie) + głośne podsumowanie „REKORDBOX LIBRARY TESTS DID NOT RUN". (4) **Hard-inwariant BPM/beatgrid nie był pilnowany na CI** → strażnik strukturalny parsujący źródło writera, **zweryfikowany mutacją** (wstrzyknięte `BPM=128.0` → test pada). (5) CLI: `--timestamp` był wymagany i musiał być unikalny (drugi bieg się wysypywał) → domyślnie „teraz"; **`restore` miał katalog backupów na sztywno**, więc zapisu z własnym `--backup-dir` nie dało się odzyskać; raport bez bazy mówił „N cue · 0 zbieżności" **udając wynik sprawdzony**; `dropped` liczony i nigdy nie pokazany; `set` przesłaniał wbudowany typ. (6) `write_plan` (98 linii) rozdzielony na kopertę bezpieczeństwa + `_execute_write`; przy okazji **wyciek plików**: ścieżka błędu `--safe-swap` usuwała tylko główny plik, zostawiając `-wal`/`-shm` w folderze Pioneer. **Sprawdzone i celowo NIE ruszone:** `loader` nie opakowuje błędów librosy, ale `batch.py` izoluje per-plik. Suite **506 → 521**, pełny bieg 12 s.
- **2026-07-24 noc (Klaris + Janek): WYCIĘTE CAŁE UI — projekt jest terminalowy.** Decyzja Janka: „usuń całe UI, pracujemy tylko w terminalu, kod ma być czysty do granic". Usunięte `src/dancelab/host/` — **8 117 linii Qt/PySide6** (simple_mode 3548, pair_review 2422, mixability_map 686, desktop_bundle 474, analyzed_library 430, energy_timeline 377, desktop_app+import_dialogs 180) + 7 modułów testów + Docker-Qt (`Dockerfile.test`, `run_qt_tests_docker.sh`) + zależności PySide6 + entry pointy `dancelab-host*`. Uratowane: `transition_simulation` → nowy pakiet **`dancelab.preview`** (render audio przejścia, bez Qt, używany przez E2E). Umarły z UI: `project.py` (stan sesji Simple Mode), `waveform_cache.py` (dla review UI), `preview_timing.py` (był tylko shimem nad `validation/preview_timing`). **Archiwum: tag `ui-archive-2026-07-24`** (wypchnięty; odzysk `git checkout ui-archive-2026-07-24 -- src/dancelab/host`) — dla Korda, bo Terrain był jego robotą. **Dwa P1 audytu zamknięte STRUKTURALNIE** (rdzeń nie może zaimportować Qt, bo Qt nie ma; nic nie mutuje env przy imporcie). **Pełny `pytest` po raz pierwszy dobiega do końca: 506 passed, 0 failed, 11.6 s** (wcześniej padał sygnałem 134). Naprawiony też zastany test bramki: zakładał że `.webm` jest nieczytelny dla silnika, a loader go obsługuje od „webm fix" — przykład zmieniony na `.aac` (naprawdę spoza `SUPPORTED_EXTENSIONS`), intencja testu zachowana. P2: `httpx2`→`httpx`. **Mój błąd do protokołu:** commit `80d2d2a` wciągnął 100 usunięć duplikatów `* 2` z równoległej sesji (commitowałem bez jawnych ścieżek) — efekt zgodny z audytem, ale opis commita tego nie oddaje; wypchniętej historii nie przepisuję, od tamtej pory commituję z `-- <ścieżki>`. Zostało z audytu: **CI nadal martwe** (PYTANIE #6).
- **2026-07-24 wieczór (Klaris, po audycie zewnętrznym):** ⚠️ **AUDYT MIAŁ RACJĘ — cue-writer NIE był bezpieczny domyślnie.** Potwierdzone i naprawione u źródła: (1) CLI celowało domyślnie w ŻYWĄ bazę, dry-run wyłączony → teraz **plan-only jest domyślny**, zapis wymaga `--write`, a zapis do żywej biblioteki dodatkowo `--allow-live`; safe-swap domyślnie ON; (2) weryfikacja **tylko liczyła wiersze** → teraz sprawdza KAŻDY cue po (ContentID, Kind, InMsec) + komentarz; (3) nieudana weryfikacja **zostawiała zapis w bazie** → teraz przywraca backup i rzuca błąd; (4) matcher miał **cichy fallback po samym tytule** (biblioteka Janka MA duplikaty tytułów: 2× Movement, 2× Rapture in Blue, 3× Srekye) → teraz **odmawia przy niejednoznaczności** zamiast zgadywać; (5) `psutil` brak → fail-**closed**; (6) backup przy zapisie z `deduplicate=False`, bo dedup mógł zostawić brak punktu rollbacku. Retro-check: nasze wcześniejsze E2E **nie trafiło w zły track** (wszystkie 5 dopasowane po ścieżce pliku, nie po tytule) — ryzyko było realne, ale nie wystrzeliło. **Branch `feature/rekordbox-cue-export` wypchnięty na origin** (16+ commitów było TYLKO lokalnie). Nowy `scripts/cue_cleanup.py` — chirurgiczne usunięcie naszych cue bez restore całej bazy (żywa baza Janka miała 425 własnych cue vs 352 w backupie → wholesale restore skasowałby ~73). **Status uczciwie: solidny prototyp, NIE wydanie.** Otwarte (nie moje/nie zrobione): CI nadal martwe (`docs/github-ci.yml.txt`, token bez scope `workflow`), Qt niedoseparowany od core (pełne `pytest` potrafi paść 134), `desktop_app.py` mutuje env Qt przy imporcie, `httpx2` zbędna zależność.
- **2026-07-24 (Klaris + Janek, „all in"):** 🎯 **ZAPIS CUE DO REKORDBOX UDOWODNIONY E2E.** Nie czekaliśmy na Korda. Spike na KOPII master.db → hot cue wstrzyknięty (pyrekordbox 0.4.4) → **sam Rekordbox otworzył bazę i pokazał cue** (pad D @ 1:30, track #Sickdrum/MoBlack), ZERO promptu „repair library". Potem restore z backupu PRETEST (cue znikł). **„Jedyna niewiadoma" z planu R&D (USN/integrity → RB odrzuci) = martwa** — `db.autoincrement_usn(set_row_usn=True)` robi księgowość za darmo; SQLCipher klucz auto. Przepis w pamięci [[dancelab-cue-write-proven]]. Skutek: **bez XML-importu, bez USB** — silnik pisze cue prosto do master.db, Janek recenzuje w RB. SAFETY trzymane: praca na KOPII, live swap wyłącznie ręką Janka (harness blokuje zapis do `~/Library/Pioneer/`), RB zamknięty przy każdym write, backup PRETEST przed każdą zamianą. Export dalej NIGDY nie pisze BPM/beatgrid. NASTĘPNE: wpiąć na prawdziwy set DanceLab (cue przejść z `set_builder` na realne tracki).
- **2026-07-23 (Klaris + Janek):** SPRZĄTANIE + PRZEPROWADZKA. Wycięto residuum grafu-nodów (node-host backend, 2289 linii + testy, rdzeń zero-zależny). Usunięto trupy (.venv_uv_blocked, tmp, dist, stare AUDIT_REPORTy), design→`~/Desktop/DanceLab-Design`. **REPO PRZENIESIONE z iCloud (Desktop) → `~/Developer/dancelab-engine`** — iCloud robił kopie-konflikty („PROJECT_LEDGER 2.md" itd.) i groził korupcją .git. venv przeżył (python=symlink homebrew), ścieżki naprawione, testy zielone z nowego domu. **Nowa ścieżka repo: `~/Developer/dancelab-engine`.**
- **2026-07-23 noc (Klaris, autonomicznie — Janek śpi):** SANACJA GITA. Diagnoza: repo miało ZERO remote, ostatni commit 18.07, 5 dni pracy niezacommitowane, `.git` tylko w folderze iCloud (ryzyko korupcji). Zrobione: rozszerzony `.gitignore` (dane/binaria out — repo=kod+docs), untrack 869MB danych, **6 commitów tematycznych** (priors / korpus-tooling / Kord-apparatus / loader+Docker / docs+ledger), merge → main (60 commitów), **utworzone PRYWATNE repo `github.com/JANEK-PNG/dancelab-engine` + push main+calibration.** Kod bezpieczny poza iCloud. Uwaga: `.github/workflows/ci.yml` przeniesiony do `docs/github-ci.yml.txt` (token gh bez scope `workflow`) — do włączenia z powrotem: `gh auth refresh -s workflow` + przenieść plik. NIE usuwałem niczego destrukcyjnie (trupy `.venv_uv_blocked`/`tmp`/`dist` zostają — do decyzji Janka).
- **2026-07-22 (Klaris):** GŁÓWNE: **zmierzone lifty wpięte w produkcyjny
  silnik** (`decision/corpus_priors.py`; tryb smart only; 6 nowych testów,
  regres warstwy decyzji 76 zielonych) — stacja 5 domknięta na całego.
  Wcześniej: walidacja v2 na pełnych 1604 obserwacjach (0.427<0.442<0.490,
  p=0.12 — prowadzą, dowód wymaga więcej danych); pomiar negatywny CLAP-w-parach
  zablokował złą wagę; DJ-mapping uznany za KOMPLETNY na 337 (92/96 wykluczeń
  pryncypialne — wyświetlanie „337/433" mylące, do poprawy). Pełny CLAP stanął
  11 931/12 668 — **dysk odpięty, czeka na podpięcie**; prior energii też.
  NASTĘPNE: energia+CLAP po dysku, rekomendacja re-scope bramki dla Korda.
- **2026-07-21 (Klaris):** rejestr + tablica zespołu utworzone z pełnym
  back-fillem. Reszta w Raporcie dnia. Wzorzec dnia: **każdą istotną rzecz
  wyłapał Janek** — stąd ten plik.
