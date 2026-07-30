# DanceLab Engine — raport stanu projektu
**Data:** 28 lipca 2026 · **Autor:** zespół inżynieryjny · **Dla:** kierownictwo

Wszystkie liczby w tym dokumencie pochodzą z pomiaru wykonanego w dniu raportu,
nie z szacunków. Metody pomiaru są opisane przy każdej sekcji, żeby dało się je
powtórzyć.

---

## 1 · Odpowiedź w jednym akapicie

DanceLab jest **spójnym, sprzężonym systemem** — 18 modułów, z których **każdy
ma realnych konsumentów** poza jednym świadomie zaparkowanym (`api`). Rdzeń
analityczno-decyzyjny działa jako jeden organizm: analiza karmi decyzje, decyzje
karmią eksport do Rekordboxa, a pomiar z korpusu wraca do decyzji. Warstwa
graficzna została **w całości usunięta** i jest to zweryfikowane pomiarem
(zero pozostałości). Produkt jest dziś aplikacją terminalową z 13 komendami,
pokrytą **548 testami przechodzącymi w 24 sekundy**.

---

## 2 · Czy moduły współgrają — pomiar sprzężenia

Metoda: analiza grafu importów w `src/dancelab` (AST wszystkich 146 plików).

| moduł | linie | używany przez |
|---|---:|---|
| `core` (modele, konfiguracja, pipeline) | 1 952 | **14 modułów** — węzeł centralny |
| `decision` (mózg: dobór, przejścia, cue) | 6 980 | 7 |
| `storage` | 639 | 7 |
| `ingestion` (wejście audio + Rekordbox) | 1 179 | 6 |
| `context` (warunki występu) | 376 | 4 |
| `stems` · `export` | 703 · 349 | 3 · 3 |
| `features` · `preprocessing` · `data` · `workflows` | 760 · 550 · 363 · 527 | 2 każdy |
| `descriptors` · `preview` · `security` · `contracts` | 329 · 612 · 17 · 17 | 1 każdy |
| `validation` (aparatura badawcza) | 11 206 | 1 (CLI) |
| **`api`** | 1 209 | **0 — zaparkowane** |

**Wniosek:** brak modułów-sierot. Jedyny bez konsumenta to `api` (interfejs HTTP),
który stracił odbiorcę po usunięciu warstwy graficznej. To znana, zapisana
decyzja do podjęcia — nie przeoczenie.

**Kształt zależności jest zdrowy:** `core` to wspólny fundament, `decision`
nadbudowuje nad nim, a moduły wejścia/wyjścia zależą od obu. Nie ma cykli
architektonicznych ani modułu, który „wie wszystko o wszystkim".

---

## 3 · Czy to jeden organizm

Organizm poznaje się po tym, że **bodziec zmienia zachowanie całości**. Trzy
połączenia zamknięte w ostatnim tygodniu:

1. **Kontekst występu → wynik.** Warstwa warunkowania (klub/festiwal, rola w
   secie, pora nocy) istniała i była przetestowana, ale interfejs nigdy jej nie
   karmił — działała „na sucho". Podłączona: `--context club_peak` realnie
   zmienia dobór par.
2. **Pomiar → decyzja.** Dane z korpusu wracają do silnika przez wersjonowany
   plik parametrów, nie przez liczby wpisane w kod.
3. **Decyzja → zmysł.** Każde proponowane przejście można **usłyszeć** przed
   zagraniem (render audio szwu) i **zobaczyć** w Rekordboxie (znaczniki cue
   zapisywane wprost do biblioteki, bez importu plików pośrednich).

Czwarte połączenie — warstwa HTTP — pozostaje odłączone i czeka na decyzję
biznesową (czy powstanie odbiorca, czy idzie do archiwum).

**Ocena:** system działa jak organizm w części analityczno-wykonawczej. Nie jest
jeszcze produktem dla klienta zewnętrznego — brakuje interfejsu dla osoby, która
nie zna terminala (patrz sekcja 6).

---

## 4 · Obecny przepływ pracy

Aplikacja to jedna komenda `dancelab` z 13 podkomendami. Typowa ścieżka:

| krok | komenda | co robi |
|---|---|---|
| 1 | `analyze` / `batch` | analiza utworu lub folderu (tempo, tonacja, struktura) |
| 2 | `smart-playlist --context …` | zbudowanie setu z folderu, z uwzględnieniem miejsca występu |
| 3 | `preview A B` | **odsłuch przejścia** przed zagraniem, z uzasadnieniem długości |
| 4 | `cues write --set … --write` | zapis znaczników i playlisty **wprost do biblioteki Rekordbox** |
| 5 | `cues restore` | wycofanie zmian z kopii zapasowej |

Ścieżki pomocnicze: `export-rekordbox` (starszy format XML), `decision-report`
(raport decyzji dla pary), `corpus-ordering` i `validation-*` (aparatura
badawcza).

**Bezpieczeństwo biblioteki użytkownika** (po audycie zewnętrznym): zapis
domyślnie tylko planuje i raportuje; realny zapis wymaga jawnej flagi, a zapis do
głównej biblioteki — drugiej. Każdy zapis poprzedza kopia zapasowa z sumą
kontrolną, po zapisie następuje weryfikacja każdego znacznika, a niepowodzenie
automatycznie przywraca stan sprzed operacji.

---

## 5 · Czy usunęliśmy zbędny kod i grafikę — pomiar

| co sprawdzono | wynik |
|---|---|
| pozostałości Qt/PySide6 w kodzie i testach | **0 plików** |
| generatory HTML w kodzie źródłowym | **0 plików** |
| binaria projektowe (`.fig`, `.sketch`, `.psd`) | **0 plików** |
| moduły bez konsumenta | **1** (`api`, świadomie) |

Usunięte w ostatnim tygodniu:
- **8 117 linii** interfejsu graficznego Qt (7 modułów testowych, zależność
  PySide6, osobne środowisko Docker do testów) — z archiwum odzyskiwalnym;
- **3 474 linie** generatora interfejsu HTML do ocen (narzędzie badawcze, którego
  produkt przestał być używany w pętli strojenia);
- ~100 duplikatów plików powstałych przy synchronizacji chmurowej.

Efekt uboczny o wymiernej wartości: pełny zestaw testów **przestał się wywalać**
(wcześniej przerywał pracę błędem środowiska graficznego) i wykonuje się w
24 sekundy — co przywróciło sens automatycznej kontroli jakości.

---

## 6 · Jakość i ryzyka

**Jakość:** 548 testów przechodzących, 1 pomijany. Ciągła integracja przywrócona.
W ostatnim tygodniu wykryto i naprawiono 16 realnych defektów w dwóch przeglądach
modułowych, w tym cztery dotyczące bezpieczeństwa danych użytkownika.

**Zasada nadrzędna projektu:** system nigdy nie podaje wartości, której nie
zmierzył. Brakująca dana daje jawny brak z uzasadnieniem, nie „rozsądną"
wartość zastępczą. Zasada jest egzekwowana testami, nie tylko konwencją —
w tym testem strukturalnym pilnującym, że eksport nigdy nie nadpisze tempa ani
siatki rytmicznej w bibliotece użytkownika.

**Otwarte ryzyka:**
1. `api` bez odbiorcy — decyzja: rozwijać czy archiwizować.
2. `validation` to 38% kodu i jest aparaturą badawczą, nie produktem — do
   rozważenia wydzielenie.
3. Aplikacja działa dziś na maszynie deweloperskiej; dystrybucja dla innych
   użytkowników wymaga podpisu i notaryzacji (koszt licencyjny).
4. Interfejs zakłada znajomość terminala — bariera dla użytkownika docelowego.

---

## 7 · Sprzężenie, którego nie widać w grafie importów

Projekt prowadzi własny program metodologiczny („Design in Between"), który
stawia ostrzejsze kryterium niż to z sekcji 2. Graf importów mierzy sprzężenie
**między modułami**. Ale produktem nie jest ani utwór, ani moduł — produktem jest
**szew**: to, co dzieje się pomiędzy. A najważniejsza relacja w tym systemie to
nie moduł↔moduł, tylko **DJ ↔ silnik**.

Zmierzone uczciwie, ta relacja jest dziś **asymetryczna**. Silnik proponuje i
uzasadnia — to działa. Ale korekta w drugą stronę **nie przechodzi przez
produkt**. Przykład z dnia raportu: pierwsza wygenerowana pętla została oceniona
przez DJ-a jako brzmiąca sztucznie; poprawka (dwie zmiany w kryterium wyboru)
trafiła do silnika **przez inżyniera jako pośrednika**, nie przez aplikację.
Efekt był dobry, droga — nie. Relacja sprzężona przez pośrednika jest krucha:
znika, gdy pośrednika nie ma.

Program nazywa warunki, które musi spełnić narzędzie mające tę asymetrię
zmniejszyć. W przełożeniu na nasz produkt:

| warunek | co znaczy tutaj | stan |
|---|---|---|
| **symetria sprawcza** | DJ musi móc poprawić decyzję silnika tym samym kosztem, jakim silnik ją zgłasza | ❌ korekta wymaga inżyniera |
| **komplementarność wkładów** | zadanie musi wymagać wiedzy obu stron: silnik ma pomiar, DJ ma gust i pamięć sali | ⚠️ częściowo — silnik liczy, DJ tylko akceptuje |
| **wspólny zewnętrzny obiekt** | rozmowa toczy się wokół rzeczy, na którą obie strony mogą wskazać, nie wokół komunikatów | ✅ **jest** — odsłuch szwu, znaczniki w Rekordboxie, pętla |
| **protokół zatrzymania** | tania i pewna droga wycofania każdej zmiany | ✅ kopie zapasowe + weryfikacja + przywracanie |

Dwa warunki spełnione, dwa nie. **To jest właściwa definicja tego, czego brakuje
do „jednego organizmu"** — nie kolejny moduł, tylko domknięcie pętli zwrotnej
wewnątrz produktu.

---

## 8 · Rekomendacja

Fundament jest gotowy i sprawdzony. Rekomendujemy zbudowanie **interaktywnego
interfejsu terminalowego**, ale nie jako „ładniejszego menu" — jako narzędzia
domykającego pętlę z sekcji 7. Kryterium sukcesu: **werdykt ucha DJ-a ma trafiać
do silnika bez pośrednika**, a rozmowa ma się toczyć wokół wspólnego obiektu
(szwu, który obie strony słyszą), nie wokół komunikatów.

W praktyce oznacza to interfejs zbudowany wokół **pary utworów i ich szwu**, a
nie wokół listy plików — bo to szew jest produktem. Ekran pokazuje propozycję
silnika z uzasadnieniem, pozwala jej **posłuchać jednym klawiszem** i przyjąć,
odrzucić lub poprawić — a ta ocena zostaje zapisana i wraca do doboru.

Uzasadnienie wyboru terminala nad interfejsem graficznym:

- nie wymaga odbudowy warstwy graficznej ani jej kosztów utrzymania (to właśnie
  ona była największym źródłem awarii testów i długu);
- działa wszędzie tam, gdzie działa aplikacja, bez dodatkowych zależności;
- obniża barierę wejścia bez zmiany architektury — interfejs korzysta z tych
  samych komend, które są już pokryte testami;
- pozwala odłożyć decyzję o warstwie HTTP i pełnym interfejsie graficznym do
  momentu, gdy będzie znany odbiorca.
