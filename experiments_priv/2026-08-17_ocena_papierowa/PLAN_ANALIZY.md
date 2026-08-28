# Plan analizy — ocena papierowa OCENA A–J (zarejestrowany PRZED danymi)

Zarejestrowano 2026-08-18, w trakcie oceniania przez Janka (sesja 1 z 5 skończona,
żadna ocena nie została jeszcze przepisana ani ujawniona). Progi poniżej są
ostateczne — po wpisaniu ocen wolno je tylko RAPORTOWAĆ, nie zmieniać.
Kultura projektu: próg przed pomiarem, wynik przeciwny progu idzie do OBALONE.md.

## Dane

* 10 playlist (OCENA A–J), 158 przejść, oceny 1–5 z papieru, przepisane do
  `SESJA_*_transition_ratings.csv` (kolumna `dj_mixability_rating`).
* Oceny całych playlist (spójność, różnorodność, przebieg, „zagrałbym
  publicznie") przepisane do `oceny_playlist.csv`.
* `engine_score` policzone deterministycznie 18.08 PRZED poznaniem ocen
  (`wypelnij_engine_score.py`), skala energii po unii utworów 10 playlist.
* Przydział silnik/kontrola w `PRZYDZIAL_NIE_OTWIERAC.json` — otwiera go
  wyłącznie `analiza.py` i wyłącznie po przejściu bramki kompletności.

## Bramka kompletności (fail-closed)

Analiza NIE rusza, dopóki wszystkie 158 przejść nie ma oceny 1–5.
Częściowe dane = zero liczenia, zero zaglądania do przydziału.

## H1 (główna): czy KOLEJNOŚĆ od silnika jest słyszalna?

* Jednostka: playlista (n=10; 6 silnik, 4 kontrola z tasowaną kolejnością).
* Statystyka: średnia ocen przejść w playliście; różnica średnich
  silnik − kontrola.
* Test: DOKŁADNA permutacja po wszystkich C(10,4)=210 możliwych przydziałach
  kontroli, jednostronna (silnik > kontrola). Minimalne osiągalne p = 1/210
  ≈ 0,0048 — zapisujemy to jawnie, żeby nie udawać precyzji, której nie ma.
* Progi (obie części muszą przejść, żeby ogłosić sukces):
  * p < 0,05 (istotność),
  * Δ ≥ 0,5 punktu MOS (słyszalność — pół oceny na pięciostopniowej skali).
* Δ w przedziale 0,25–0,5 przy p < 0,05: raportujemy jako „słaby, realny
  sygnał", bez ogłaszania sukcesu. Δ < 0,25 albo p ≥ 0,05: kolejność silnika
  nie wnosi nic słyszalnego → wpis do OBALONE.md.

## H2: czy wynik silnika przewiduje ocenę ucha?

* Statystyka: Spearman rho między `engine_score` a oceną, wszystkie 158
  przejść razem.
* Test: permutacja ocen WEWNĄTRZ playlist (kontroluje różnice między
  playlistami), 10 000 permutacji, ziarno 20260818, jednostronna (rho > 0).
* Progi: rho ≥ +0,30 i p < 0,05 → silnik widzi to, co ucho;
  rho +0,15–0,30 przy p < 0,05 → słaby sygnał; poniżej → brak, do OBALONE.md.
* Dodatkowo licznik z istniejącej bramki: fałszywe alarmy
  (engine_score ≥ 0,70 a ocena ≤ 2) — raportowane bez progu.

## H3 (opisowa, bez twardego progu): oceny całych playlist

* Spójność / różnorodność / przebieg / „zagrałbym publicznie":
  średnie silnik vs kontrola, ta sama dokładna permutacja co w H1.
* n=10 to za mało na twardy próg — raportujemy kierunek i p, bez werdyktu.
* Krzywe energii z papieru: porównanie jakościowe (oko), bez statystyki.

## Kategorie zgrzytów (T S E M D K)

Zliczenia per kategoria, silnik vs kontrola — opisowo. Litery mapują się
1:1 na słownik `TOPIC_KEYWORDS` z `validation/dj_benchmark.py`:
T→bpm_grid_sync, S→style_genre_mood, E→energy_curve, M→transition_timing,
D→duplicates_same_album, K→playlist_context.

---

## Aneks z 2026-08-29 — jedno odstępstwo od planu, zapisane PRZED liczeniem

Plan z 18.08 mówił: komplet 158 ocen albo zero liczenia. Po przepisaniu ocen
ze skanów okazało się, że **przy jednym przejściu (`OCENA_J_13`) nie jest
zakreślona żadna cyfra** — nie zostało ocenione przy słuchaniu. Cztery inne
pola były niejednoznaczne (dwie cyfry zakreślone naraz, dopisek „5?”) i te
Janek rozstrzygnął tego samego dnia: `OCENA_I_06` = 4, `OCENA_I_16` = 1,
`OCENA_J_02` = 4, `OCENA_J_05` = 4.

**Decyzja Janka (formularz, 29.08): `OCENA_J_13` wypada z analizy.**
Liczymy 157 przejść zamiast 158.

Dlaczego to jest odstępstwo, a nie drobiazg: bramka miała być „wszystko albo
nic" właśnie po to, żeby nie dało się wyrzucić niewygodnej obserwacji po
zobaczeniu danych. Dlatego wyłączenie **musi być jawne i uzasadnione**:

* Powód jest brakiem zapisu na kartce, nie własnością przejścia ani playlisty.
* W chwili decyzji przydział silnik/kontrola był **nadal zapieczętowany** —
  ani Janek, ani ja nie wiedzieliśmy, do której grupy należy OCENA J.
* Lista wyłączeń leży w `WYLACZENIA.json`, a `analiza.py` wypisuje ją przy
  każdym uruchomieniu i zapisuje w wyniku. Wyłączenie bez zapisu byłoby
  doborem wyniku; wyłączenie z zapisem jest brakiem danych.

**Progi z 18.08 pozostają bez zmian.** Ten aneks zmienia liczbę obserwacji,
nie kryteria. Średnia dla OCENA J liczy się teraz z 12 przejść, nie 13.
