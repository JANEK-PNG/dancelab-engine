# Warstwa graficzna DanceLab — transfer wiedzy z wątku R&D

Decyzja Janka 18.08.2026 (wątek „DanceLab Pro machine learning integration"):
budujemy WARSTWĘ GRAFICZNĄ w osobnym wątku. Ten dokument przenosi to, co
istotne. Kurz zamiatamy później — jeśli czegoś tu nie ma, a jest potrzebne,
szukać w `PROJECT_LEDGER.md` i `OBALONE.md` (korzeń repo).

## Ramy decyzji

* **Porzucamy przyjęte normy UI** (gotowe tabelki, dashboardy, rankingi).
  **UX na razie zostaje** — jak się rzeczy obsługuje, nie ruszamy.
* **Sprzężenie zwrotne**: kod napędza UI, ale UI może wymusić zmianę w kodzie.
  Precedens już był: żeby ekran uczciwie pokazał „skąd ta tonacja", silnik
  dostał pole `key_detection_source`.
* **Zasada nr 1: wizualna uczciwość przed urodą.** Wygładzona krzywa na
  poszarpanych danych = miernik pokazujący zero, którego nie zmierzył
  (lekcja etapu 6). Nigdy nie udajemy wyniku (twarde ADR silnika).
* Metafora robocza: dom stoi (silnik = fundament), mieszkamy na materacu
  (TUI). Meble NIE ze sklepu — wbudowane w ściany, zrobione z tego, co ten
  dom ZMIERZYŁ. Kabina statku, nie salon z katalogu.

## Szkielet aplikacji (fundament, na którym wisimy meble)

* Silnik: `~/Developer/dancelab-engine` (repo prywatne JANEK-PNG/dancelab-engine).
* Rdzeń decyzji: `src/dancelab/decision/set_builder.py` → `transition_score`
  = harmonic + bpm + energy + mixability (wagi z
  `configs/descriptor_weights.yaml`), potem brzmienie (CLAP, `sound_affinity`)
  i priors z korpusu. Wynik pary w [0,1] Z UZASADNIENIEM (lista `reasoning`)
  — silnik zawsze umie powiedzieć DLACZEGO; UI ma to pokazywać, nie chować.
* Analizy utworów: `AnalysisResult` (ten sam typ co w SPLOT), magazyn
  `experiments_priv/2026-07-30_rebuild/processed`.
* Obecna twarz: TUI (Textual, `src/dancelab/tui/`) — zostaje jako narzędzie
  operacyjne; warstwa graficzna powstaje OBOK, nie zamiast.
* Wejście/wyjście świata: Rekordbox. Ground truth wchodzi z Rekordboxa
  (tempo, nagrane sety), wynik wychodzi do master.db (hot cue, playlisty —
  ścieżka zapisu UDOWODNIONA: zamknięty RB, backup, weryfikacja świeżym
  połączeniem). Projektujemy warstwę MIĘDZY — nie odtwarzacz, nie edytor.

## Zmierzone prawdy, które MUSZĄ być widoczne gołym okiem

Każda pozycja to lekcja opłacona pomiarem w wątku R&D — meble się z nich robią:

1. **Odpowiedź zbiorem, nie odmową.** Cztery mechanizmy „nie wiem" zmierzone
   i martwe (OBALONE.md B6). UI nigdy nie pokazuje jednego „najlepszego"
   utworu — pokazuje PÓŁKĘ (top-20). Mediana pozycji prawdy: 17/200.
   Komponent listy kandydatów = półka, nie ranking.
2. **Niezmierzone ≠ zero i ≠ pewne.** Tonacja bez pomiaru pewności dostaje
   0,5 (`NIEZMIERZONA` w `decision/harmonic.py`). Każda liczba na ekranie
   nosi pochodzenie: zmierzona / ręczna / niezmierzona — odróżnialne od
   pierwszego spojrzenia. Rozróżniamy też „zmierzone 0" od „niemierzalne".
3. **Szew przed utworem (Design In Between).** Projektujemy przejście MIĘDZY
   trackami. Pierwszy obiekt na ekranie = szew; utwory są tłem. Norma
   „lista utworów" idzie do kosza.
4. **Styl to rozkład, nie średnia.** Celowanie w medianę gasi charakter
   (lekcja Four Teta: 8. percentyl skoków — skacze dalej niż 92% DJ-ów).
   Pokazujemy KONTUR (kolejne skoki po kolei), nie uśrednione słupki.
5. **Łuk „build" przegrał z płaską linią** (22/29 i 6/6, pomiar 10.08).
   Żadnych dramatycznych wizualizacji narastania sugerujących, że tak jest
   „dobrze". Krzywa energii = to, co zmierzone.
6. **Wagi z korpusu biją ręczne** (24,3% > 20,7% > 18%). UI pokazuje, skąd
   liczba: z korpusu / z ręki. Provenance wszędzie.
7. **Kultura ślepej próby.** Interfejs umie SCHOWAĆ własne wyniki, gdy DJ ma
   słuchać uchem (dokładnie tak działa trwające badanie papierowe OCENA A–J).
8. **Wnętrze szwu jest policzalne**: mix minus utwory = ruchy rąk (blend
   ~171 uderzeń, bas wstrzymany w 86% wejść u Janka; reguła wejścia: perkusja
   bez basu, 71% vs 18%). SeamProfile mówi JAK szew jest szyty — to jest
   materiał na najciekawszy mebel.

## Istniejące wizualne DNA (nie zaczynamy od zera)

* **PORTRET · system VJ**: `docs/vj-system/portret-vj.js` (port 8653) — już
  wpięty w karty artystów; każdy kolor ma znaczenie i są rzeczy, których
  świadomie NIE rysuje.
* **Prism** (z uśpionego projektu CURVE): ciemno, liquid glass, sidebar
  224 px, separator `·` — gotowy język, wolno go kanibalizować.
* **Formalizacja In Between**: arkusze w repo DanceLab-Design-In-Between/
  (Janek pracuje na nich ręcznie) — źródło geometrii szwu.
* **Ton głosu DanceLab**: kumpel pokazujący coś fajnego; nigdy oceniająco.
  Dotyczy też mikrotekstów w UI.

## Czego w nowym wątku NIE ruszać

* Playlisty OCENA A–J i `PRZYDZIAL_NIE_OTWIERAC.json` — trwa ślepe badanie;
  pieczęć otwiera wyłącznie `analiza.py` po komplecie ocen.
* master.db — zapis tylko udowodnioną ścieżką i tylko za słowem Janka.
* Ikona aplikacji — odłożona (5 szkiców odrzuconych; wrócimy z referencjami).

## Zasady pracy (obowiązują wszędzie, także tam)

* Dźwięk NIGDY nie gra w panelu podglądu. Eksperymenty w `experiments_priv/`
  (nie w temp). Bez fan-outów agentów. Wpis do `PROJECT_LEDGER.md` na koniec
  bloku pracy. Próg przed pomiarem; obalone hipotezy → `OBALONE.md`.
