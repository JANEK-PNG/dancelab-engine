# Raport stanu — 2026-08-02

Audyt całego projektu **z dysku**, nie z GitHuba. Moduł po module, plik po pliku.
Każda liczba niżej jest zmierzona dzisiaj, nie zapamiętana.

Powód: „nie wiem, w jakim stanie jest moja aplikacja". Ten dokument ma to zamknąć.

---

## 1 · Co masz, w jednym akapicie

Silnik ma **151 modułów i 30 529 linii Pythona**, 590 testów przechodzących
z czystego klona, 13 komend w wierszu poleceń, CI na GitHubie w kolorze zielonym.
Analizuje utwór, buduje set, eksportuje playlistę do XML-a i **potrafi zapisać
hot cue wprost do bazy Rekordboxa, respektując Twoje własne cue**. To wszystko
jest zbudowane i sprawdzone od zera dzisiaj.

I jednocześnie: droga, którą uczy README, jest tą, o której Twój własny brief
z 22 lipca mówi, że u DJ-a nie działa. A najlepsza część produktu nie da się
uruchomić jedną komendą.

---

## 2 · Rozkład kodu — gdzie naprawdę siedzi projekt

| Pakiet | Modułów | Linii | Udział |
|---|---:|---:|---:|
| `validation/` | 35 | 11 421 | **37%** |
| `decision/` | 27 | 7 100 | 23% |
| `core/` | 12 | 2 331 | 8% |
| `cli/` | 9 | 1 887 | 6% |
| `api/` | 9 | 1 209 | 4% |
| `ingestion/` | 10 | 1 179 | 4% |
| `features/` | 10 | 760 | 2% |
| `stems/` | 6 | 744 | 2% |
| pozostałe 8 pakietów | 33 | 3 898 | 13% |

**Czytanie tego:** ponad jedna trzecia repozytorium to aparatura badawcza,
a nie produkt. To jest pytanie #10 w kolejce, postawione 24 lipca i wciąż
otwarte — z poprawką, że dziś to 37%, nie 44%.

---

## 3 · Co działa od końca do końca (sprawdzone dzisiaj)

- **Instalacja z czystego klona** komendą z README — przechodzi, ~3 minuty.
- **Analiza utworu** — ~65 s na utwór 3-minutowy. Zwraca tempo, siatkę bitów
  z oceną jakości, segmenty, 172 pozycje cech, oraz pole `notes` z zastrzeżeniami
  („ten deskryptor jest przybliżeniem", „etykiety segmentów są heurystyką").
- **Katalog → set → XML** — `smart-playlist` daje poprawny plik Rekordboxa
  z tonacją, tempem i nazwanymi znacznikami.
- **Zapis cue do `master.db`** — udowodniony end-to-end 24 lipca; paczka z tamtego
  dnia nadal leży w `data/reports/cue_export_bundle.json`.
- **Testy i bramki** — 590 testów, lint, bramka pokrycia dokumentacji, audyt
  bezpieczeństwa, weryfikacja czystej instalacji. Wszystko zielone.

---

## 4 · Silnik cue — to jest lepsze, niż myślisz

Sprawdzone w kodzie, nie z pamięci:

- `ingestion/rekordbox_cue_writer.py` **czyta Twoje istniejące cue** z bazy
  (`read_existing_cues`, wiersze `DjmdCue`).
- `decision/cue_conflict.py` rozstrzyga kolizje w trzech trybach: **skip /
  replace / merge**. Domyślny `merge` **zachowuje cue DJ-a** i przenosi nasze na
  wolny pad; gdy cue już siedzi w tym samym miejscu (tolerancja 750 ms), nasze
  jest kasowane — nigdy nie robi duplikatu.
- Każda decyzja ma etykietę w raporcie: `placed`, `skipped`, `relocated`,
  `replaced`, `deduped`, `no_free_pad`, plus flagę `needs_decision`.
- **Twardy niezmiennik:** pisze wyłącznie wiersze `DjmdCue`. Nigdy nie dotyka
  BPM ani siatki bitów.
- Zapis domyślnie **planuje i nie zapisuje** — potrzeba jawnego `--write`.
  Do żywej biblioteki dodatkowo `--allow-live`. Domyślnie pisze na zweryfikowanej
  kopii i podmienia. Odmawia, gdy Rekordbox jest otwarty.

**Tryby treści:** `in_out` stawia Mix In / Mix Out / Bridge, `structural` stawia
znaczniki sekcji.

---

## 5 · Dziura, która tłumaczy Twoje zamieszanie

**Nie istnieje komenda prowadząca od biblioteki do paczki cue.** Robi to skrypt
`scripts/cue_export_e2e.py`, działający na wcześniej policzonym cache'u analiz.

Czyli produkt ma udowodnioną pierwszą milę (analiza, set) i udowodnioną ostatnią
(zapis cue z rozstrzyganiem konfliktów), a **brakuje szwu między nimi w CLI**.
Dlatego README uczy XML-a — bo XML jest jedyną drogą przechodzącą jedną komendą.

A o XML-u Twój brief `RND_CUE_DELIVERY_USE_CASE.md` z 22 lipca mówi wprost:
wyeksportowano 26 poprawnych hot cue, DJ **nie zobaczył ani jednego**, bo
Rekordbox nie nadpisuje wpisów już będących w kolekcji. Zasada z tamtego
dokumentu: *„Jeśli eksport wymaga instrukcji — eksport jest niedokończony."*

**Do zrobienia, jedna komenda:** `dancelab cue-plan` — od przeanalizowanych
utworów prosto do paczki, żeby cała droga dała się przejść bez skryptu.

---

## 6 · Zbudowane, ale wyłączone albo niepodpięte

| Co | Stan | Skutek |
|---|---|---|
| **Separacja na stemy (Demucs)** | `stems.enabled: false` we **wszystkich** konfiguracjach, łącznie z domyślną | Pakiet `stems/` (744 linie) nieaktywny. Zależy od niego `features/vocals.py`, który spada na przybliżenie z pełnego miksu |
| **Analiza w mono** | `mono: true` wszędzie | Cała analiza traci obraz stereo. Zmierzone wcześniej: stem „other" ma korelację kanałów 0,004 — pady żyją w bokach |
| **Sztywna siatka bitów** (`core/rigid_grid.py`) | Importowana **tylko przez skrypty**, nie przez silnik | Pipeline analizy nadal używa śledzenia dynamicznego. Sztywna siatka działa w renderze setu, nie w produkcie |
| **`core/tempo_refine.py`** | **Podpięty** (`preprocessing/beatgrid.py`) | Działa. Wcześniejsze notatki mówiące inaczej są nieaktualne |
| **8 modułów nieimportowanych nigdzie** | 5 tras API, `data/dataset_manifest`, 2 pliki `__main__` | Trasy API są prawdopodobnie rejestrowane dynamicznie; `dataset_manifest` do sprawdzenia |
| **Wykonalność szwu** | Nie bierze udziału w wyborze kolejności setu | Silnik układa „playlistę do zmiksowania", nie „set zaprojektowany w szwie" |

---

## 7 · Pytania do Ciebie — 16 w kolejce, ale nie wszystkie żywe

**Martwe, rozwiązane przez fakty. Do skreślenia z kolejki:**

- **#6 — włączyć CI?** CI jest włączone i zielone. Zamknięte.
- **#8 — sprzątanie trupów?** `.venv_uv_blocked`, `tmp/`, `dist/`, stare
  `AUDIT_REPORT*`, pliki designu w korzeniu — **nic z tego już nie istnieje**.
  Zamknięte.
- **#9 — wycinamy `swipe_review.py` (3474 linie)?** Plik nie istnieje. Zamknięte.

**Zdezaktualizowane co do liczby:**

- **#10 — `validation/` to 44% repo?** Dziś **37%** (11 421 z 30 529). Pytanie
  merytoryczne stoi: aparatura badawcza zostaje w repo silnika czy wydzielamy?

**Żywe i czekają — 12 sztuk:**

| # | O co pyta | Skąd |
|---|---|---|
| 1 | Weta do domyślnie przyjętych decyzji — przejrzysz? | rejestr |
| 2 | Terrain: „zatwierdzony domyślny UI" — potwierdzasz, czy to wisiało na słowie? | ⚠️ tabela |
| 3 | Konflikt bramki 26+96 — czekamy, czy przygotować rekomendację re-scope? | 🔒 |
| 4 | Klucz Last.fm — robisz? Odblokowuje graf artystów | zaparkowane |
| 5 | Rytm przeglądu rejestru: co sesja czy raz w tygodniu? | reguły |
| 7 | Apple Developer ID (99 $/rok) + notaryzacja — kiedy na serio? Bez tego apka działa tylko na Twoim Macu | audyt 23.07 |
| 10 | `validation/` zostaje w repo silnika czy osobno? | mapa modułów |
| 11 | ML: który krok pierwszy? | ML 01.08 |
| 12 | ML: czy „model bezpieczniejszy niż Ty" to wada? Trzeba rozstrzygnąć **przed** uczeniem | ML 01.08 |
| 13 | ML: osobny pakiet `dancelab.learn`? | ML 01.08 |
| 14 | **ML: logujemy Twoje akceptacje/odrzucenia? Decyzja pilna — dane zbierają się tylko do przodu** | ML 01.08 |
| 15 | ML: temat zostaje w `RnD-DanceLab-Pro/` czy wchodzi do repo? | ML 01.08 |
| 16 | **`entry_point`: domyślnie początek wyrównany do frazy, czy dalej skanowanie?** | ML 01.08 |

**Dlaczego było ich tyle:** kolejka rosła, a nikt nie zamykał pytań, gdy
odpowiadały na nie fakty. Stąd wrażenie chaosu. **Reguła na przyszłość:
przegląd kolejki na starcie sesji i skreślanie tego, co przestało być pytaniem.**

---

## 8 · Dwa tory i co w nich leży

**Silnik** (`~/Developer/dancelab-engine`) — produkt. 181 commitów, wszystko
wypchnięte poza jedną rzeczą (niżej).

**R&D** (`~/Desktop/AI/RnD-DanceLab-Pro`) — osobny tor, 8 eksperymentów:
MuQ vs CLAP, realne sety, cue-DETR, dekonstrukcja miksu, uczciwy detektor,
metoda różnicowa, przechwytywanie MIDI, DJ Wrapped. Plus tor ML z wczoraj:
9 dokumentów, kroki 0, 2 i 3 policzone.

**Dane eksperymentów** (`experiments_priv/` w repo, gitignored) — 10 katalogów
z ostatnich czterech dni.

---

## 9 · Co nie jest zapisane

```
 M PROJECT_LEDGER.md          ← wpisy z nocy 01.08: kroki ML 0, 2, 3 + pytania #11–#16
 ?? scripts/benchmark_corpus_transitions.py
 ?? scripts/corpus_h_analysis_full.py
 ?? scripts/start_corpus_h_analysis_full.sh
```

Ledger jest plikiem śledzonym, więc dopóki nie trafi do commita, **cała
wczorajsza noc pracy ML żyje wyłącznie na tym dysku**. Trzy skrypty są
nieśledzone.

---

## 10 · Co zrobiłabym w tej kolejności

1. **Zacommitować ledger.** Jedna komenda, a chroni noc pracy.
2. **Odpowiedzieć na #14** — logowanie akceptacji. Jedyne pytanie, w którym
   czekanie kosztuje: dane zbierają się tylko do przodu, każdy dzień zwłoki to
   dzień bez danych.
3. **Odpowiedzieć na #16** — jedno słowo, A albo B, i `entry_point` przestaje
   być sprzeczny z tym, jak realnie grasz.
4. **Dobudować `dancelab cue-plan`** — domyka drogę biblioteka → set → cue
   w bazie, bez skryptu. To jest ta jedna rzecz, przez którą produkt wygląda na
   niedokończony, mimo że oba końce są gotowe.
5. **Rozstrzygnąć #10** — czy 37% repo, które jest aparaturą badawczą, zostaje.

Reszta może czekać.
