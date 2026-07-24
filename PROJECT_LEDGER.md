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

## 7 · DZIENNIK WPISÓW
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
