# IN BETWEEN

# Jak mocno „In Between" wpłynął na DanceLab — audyt na plikach

## Odpowiedź w jednym zdaniu

Wpływ jest realny, ale rozłożony bardzo nierówno: **na sposób podejmowania decyzji projektowych wpłynął mocno i dowodliwie**, **na warstwę obrazu wpłynął dosłownie — z progiem i czterema liczbami policzonymi z prawdziwych funkcji silnika**, a **na sam silnik decyzyjny nie wpłynął w ogóle**. W kodzie, który wybiera następny utwór, nie ma ani jednej litery z tego formalizmu.

Ważne dla porządku: kierunek wpływu jest odwrotny, niż sugeruje nazwa. To DanceLab urodził „In Between", nie odwrotnie. Twoje własne słowa z nagrania (`~/.codex/.codex-global-state.json`): *„wyszedłem z założenia design in between, że to się wzięło od dance labu, czyli tworzenie połączeń między utworami, że istotne jest to, co jest pomiędzy, a same utwory jedynie są takim motorem napędowym tego, co jest pomiędzy i odwrotnie. Więc właśnie ten sprzężony układ."*

---

## 1. Gdzie to REALNY wpływ

### a) Jedyne miejsce, gdzie cztery liczby są naprawdę policzone

`experiments_priv/2026-08-03_dj_mapa/profil_in_between.py` (161 linii). Nagłówek pliku cytuje Twoje polecenie z 13.08: *„pamiętaj, że wciąż to ma być sprzężone z naszym silnikiem"* — i faktycznie każda z czterech wielkości wychodzi z produkcyjnych funkcji DanceLaba: `harmonic_compatibility`, `bpm_score` z `set_builder`, `transition_prior_lift` z `corpus_priors`, wagi z `configs/descriptor_weights.yaml`.

Wynik leży na dysku jako gotowe dane: `docs/vj-system/szwy.json` — **317 przejść, 3 DJ-ów**, każde przejście z polami `C, D, Syn, U, K, okreslone` plus druga, osobna pętla `iDJ, iM, Cdj, Ddj` („sprzężenie DJ ↔ muzyka", opisane w kodzie jako *„to jest właśnie in between"*).

To jest twardy fakt: formalizm został zaimplementowany, uruchomiony i wyprodukował dane. Nie jest wyłącznie tekstem.

### b) Próg theta realnie odcina, a nie tylko zdobi

`const THETA = 0.18; // próg z definicji In Between` — trzy pliki: `docs/vj-system/portret-vj.js:57`, `docs/scena-v2/index.html:165`, `docs/mockup-dj-karty/portret.js`. Użycie: `if (C < THETA) continue; // poniżej progu nic nie zaistnieje`.

Policzyłem, ile razy to gryzie: **30 z 317 przejść (9,5%) nie zawiązuje żadnego węzła** i ma `D` ustawione na `null`. Czyli próg robi dokładnie to, co ma robić w definicji — poniżej sprzężenia kierunek jest nieokreślony, a nie zerowy.

Trzy warstwy portretu to bezpośrednie przełożenie formalizmu: pole możliwości → splatanie (węzły z `C`) → **rama, która przy szwie się poszerza, bo grają oba utwory, a po szwie zaciska wokół B**. Do tego Twój magnes: *„kropka powinna działać jak magnes… bo to moment bezpośredniej interakcji, już po in between"* (PROJECT_LEDGER.md, wpis 13.08).

### c) Realna zmiana kierunku produktu — raport stanu z 28.07

To jest najmocniejszy dowód wpływu i nie dotyczy obrazu, tylko planu prac. `docs/RAPORT_STANU_2026-07-28.md`, sekcja 7 „Sprzężenie, którego nie widać w grafie importów":

> „Graf importów mierzy sprzężenie **między modułami**. Ale produktem nie jest ani utwór, ani moduł — produktem jest **szew** […] A najważniejsza relacja w tym systemie to nie moduł↔moduł, tylko **DJ ↔ silnik**."

Dalej cztery warunki z oceną: symetria sprawcza ❌, komplementarność wkładów ⚠️, wspólny zewnętrzny obiekt ✅, protokół zatrzymania ✅. Konkluzja: *„To jest właściwa definicja tego, czego brakuje do »jednego organizmu« — nie kolejny moduł, tylko domknięcie pętli zwrotnej wewnątrz produktu."*

Z tej diagnozy wynikła cała sekcja 8 — rekomendacja zbudowania interfejsu terminalowego *„nie jako »ładniejszego menu« — jako narzędzia domykającego pętlę z sekcji 7"*. **Cały TUI istnieje z tego powodu.**

Ślad w kodzie produkcyjnym: `src/dancelab/decision/verdicts.py`, pierwsze zdanie docstringa: *„The status report's finding: engine and DJ are coupled asymmetrically. The engine proposes and explains, but the DJ's correction reaches it through an engineer rather than through the product. This module is the return path."*

### d) Formalizm jako narzędzie weta

13.08 zatrzymałeś gotową scenę jednym zdaniem: *„to nie jest in between, to nie jest nasza filozofia"* — i ustawiłeś nowy tryb: *„zacznijmy od zera na nowej wersji projektu, będę ci mówił co masz dodawać po kolei"*. Powstała `docs/scena-v2/`, warstwa po warstwie.

Wcześniej, 30.07, to samo pojęcie wygenerowało pomiar: *„skoro korpus gubi wnętrze szwu, zbudujmy narzędzie do mierzenia in between — co zostanie, jak od miksu odjąć utwory źródłowe?"* Z tego wyszedł `seam_decompose` i Twój profil szycia (nakładanie ~171 uderzeń, bas wstrzymany).

I trzeci raz jako nazwanie długu — PROJECT_LEDGER, wpis z 30.07: *„⚠️ RAMA (uwaga Janka o in between): silnik ocenia pary po własnościach utworów […] ale wykonalność szwu — punkt wejścia, zapas wyjścia, możliwa długość — NIE bierze udziału w wyborze kolejności. To jest różnica między »playlistą do zmiksowania« a »setem zaprojektowanym w szwie«."* Ten dług nadal stoi.

---

## 2. Gdzie to TYLKO język — i to trzeba powiedzieć twardo

### a) Silnik decyzyjny nie zna tego formalizmu w ogóle

Przeszukałem `src/` na `C`, `D`, `Syn`, `U`, `theta`, „in between", „sprzężenie", „asymetria": **zero trafień**. Ocena pary to niezmiennie `configs/descriptor_weights.yaml:86-89` — harmonia 0,35 + tempo 0,25 + energia 0,20 + miksowalność 0,20. Formalizm mieszka wyłącznie w `experiments_priv/` i w `docs/`.

### b) Czwarta wielkość nie niesie żadnej informacji

W `profil_in_between.py` pojemność `K` liczy się jako suma tych samych wag podzielona przez tę samą sumę wag, więc **`K = 1,0` zawsze**, a `U = C` zawsze. Sprawdziłem na całym pliku danych: **U równa się C w 317 na 317 przejść**. Czwarta z czterech wielkości jest w praktyce zdublowaną kolumną. Rama nie zmienia pojemności, bo pojemność została zdefiniowana tak, że zmienić się nie może.

### c) Trzy pozostałe wielkości to proxy, nie definicje

- **Syn** według definicji to informacja synergiczna (`I(H,S;X) − I(H;X) − I(S;X)`). W kodzie to `(lift − 1) × 2,2` z priorsów korpusu. Efekt: **`Syn = 0` w 200 z 317 przejść (63%)** — dla dwóch trzecich szwów wielkość „emergencji" jest po prostu wyzerowana.
- **D** według definicji to `ln(i_HS / i_SH)` po normalizacji entropią przyszłości. W kodzie siła strony to `0,62 × energia + 0,38 × groove + 0,05`. To założenie, nie pomiar.
- **theta** według definicji ma być *„wyznaczone z surogatów (test istotności)"* (`~/Developer/DanceLab-Design-In-Between/files/design-in-between.md`). W kodzie to stała `0,18` wpisana ręcznie, w trzech plikach niezależnie.

### d) Sprzężenie policzone z komponentów, o których wiemy, że nie przewidują

To jest najostrzejszy zarzut. `C` powstaje z harmonii (44% wagi po normalizacji), tempa (31%) i energii (25%). Dwa dni wcześniej, 11.08, audyt ablacyjny na **3612 realnych przejściach z mapy** dał werdykt: zarabiają tylko tempo i brzmienie, a *„harmonia, priorsy, mixability: zero"*, przy czym harmonia na podzbiorze z pewną tonacją **pogarszała** medianę (0,583 → 0,400).

Czyli około 69% wagi „sprzężenia" pochodzi z komponentów oznaczonych czerwoną flagą przez Twój własny pomiar. Liczba `C` jest matematycznie poprawna i empirycznie niepodparta.

### e) Skala jest mała i warto to mówić głośno

317 przejść, 3 DJ-ów — przy mapie liczącej 869 DJ-ów i 21 015 szwów. To jest demonstracja na wycinku, nie pomiar populacyjny.

### f) TERRAIN powstał bez tego języka

Siedem dokumentów `docs/TERRAIN_*` (biblia komponentów, audyt, pierwszy bieg, synteza z TUI) — **ani jednej wzmianki o „in between"**. Cały język wizualny produktu został zbudowany niezależnie. Zbieżność „szew jest jednostką pracy" jest domenowa, nie formalna.

### g) ADR-005 nie wywodzi się z progu theta i nie wolno tak mówić

Reguła „nie udawaj pewności" jest w `Claude_Code_Wejscie_do_DanceLab.md` z **6 lipca 2026, godz. 22:58**. Formalizm powstał 25–30 lipca. To zbieżność dwóch niezależnych dróg do tej samej dyscypliny — brak sygnału to nieokreśloność, nie odpowiedź — a nie związek przyczynowy. Jeśli kiedykolwiek będziesz to opowiadał na zewnątrz, ta kolejność jest sprawdzalna z dat plików i lepiej ją podać samemu.

---

## 3. Pętla, dla której zbudowano TUI, wciąż nie jest domknięta

Raport z 28.07 postawił kryterium sukcesu: *„werdykt ucha DJ-a ma trafiać do silnika bez pośrednika"*.

Stan faktyczny: w starym `src/dancelab/cli/tui.py:318` werdykt realnie wraca do rankingu (`score += store.score_adjustment(...)`). W nowym, Textualowym TUI (`src/dancelab/tui/app.py`) każda edycja **tylko się zapisuje** do dziennika `experiments_priv/2026-08-04_werdykty/` — i nikt tego dziennika nie czyta. Grep po `src/` i `scripts/` nie znajduje ani jednego konsumenta.

Czyli warunek „symetria sprawcza" jest nadal na czerwono, w narzędziu zbudowanym specjalnie po to, żeby go zapalić na zielono. To jest dziś najważniejsza otwarta pozycja wynikająca z tego programu.

---

## 4. Ocena końcowa, warstwa po warstwie

| warstwa | siła wpływu | dowód |
|---|---|---|
| decyzje projektowe | **wysoka, dowodliwa** | raport 28.07 sekcja 7–8 → cały TUI; docstring `verdicts.py`; weto 13.08; pomiar wnętrza szwu 30.07 |
| warstwa obrazu (portret, karty artystów) | **wysoka, dosłowna** | `THETA = 0.18` odcina 30/317; trzy warstwy = pole, splot, rama |
| dane pomocnicze | **średnia, z wadami** | `profil_in_between.py` liczy z prawdziwych funkcji, ale `U = C` w 100% przypadków i `Syn = 0` w 63% |
| silnik decyzyjny | **zerowa** | zero wystąpień formalizmu w `src/`; ranking to niezmiennie cztery wagi z 2026-07 |
| język interfejsu (TERRAIN) | **zerowa** | 7 dokumentów, ani jednej wzmianki |

Najuczciwsze podsumowanie brzmi tak: „In Between" działa w DanceLabie jako **narzędzie decyzyjne i jako gramatyka obrazu**, a nie jako matematyka produktu. Jego największym udokumentowanym osiągnięciem nie jest żaden wzór, tylko jedno zdanie z 28.07, które przestawiło projekt: że produktem jest szew, a najważniejszą relacją nie jest moduł do modułu, tylko DJ do silnika — i że ta relacja jest zmierzalnie asymetryczna.