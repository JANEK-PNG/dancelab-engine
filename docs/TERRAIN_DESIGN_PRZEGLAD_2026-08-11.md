# TERRAIN — potrójny przegląd projektowy (audyt systemu · krytyka · synteza badań)

**Data:** 2026-08-11 · Trzy przebiegi na zlecenie Janka: audyt systemu
projektowego, krytyka kierunku, synteza badań pod nowy UI („rdzeń TUI,
wygląd GUI"). Uzupełnia audyt implementacyjny
(`TERRAIN_BIBLIA_AUDYT_2026-08-11.md`) — tam status runtime'u, tu jakość
SAMEGO SYSTEMU projektowego.

---

## CZĘŚĆ 1 · Audyt systemu projektowego

**Zakres:** biblia (styles.css + app.js), inwentarz ruchu, blueprint,
SIMPLE_MODE_DESIGN_SYSTEM.md (historyczny). **Wynik: 62/100** — ruch
światowej klasy, tokeny kolorów częściowe, odstępy i typografia bez skali.

### Pokrycie tokenów

| kategoria | zdefiniowane | na twardo | werdykt |
|---|---|---|---|
| Ruch (czas) | 6 tokenów (90→420 ms + stagger 24) | — | ✅ wzorowe, z interaktywnym demo |
| Ruch (easing) | 6 (standard/enter/exit/spatial/snap/linear) | — | ✅ z przypisaniem do ról |
| Kolor | 18 w `:root` | **12 zabłąkanych hexów** poza tokenami | ⚠️ częściowe |
| Odstępy | **BRAK skali** | 76×1px, 30×10px, 27×9px, 27×8px, 5/7/9/18px… | ❌ wartości arbitralne |
| Typografia | 2 fonty (Manrope, IBM Plex Mono) | rozmiary na twardo, brak skali | ⚠️ |
| Promienie | 3 (8/14/22) | — | ✅ |

### Nazewnictwo

| problem | przykład | rekomendacja |
|---|---|---|
| Dwie konwencje kolorów naraz | semantyczne `--ink/--ground/--surface/--line/--volt` OBOK surowych `--cyan/--amber/--red/--green/--violet` | akcenty przemianować na ROLE. W tej domenie kluczowa para semantyczna to **deck-A / deck-B** (dziś cyan/amber pełnią tę rolę nienazwane) + positive/warning/danger |
| Tokeny jednoliterowe w demach | `--e`, `--h`, `--i`, `--m` | dopuszczalne lokalnie, ale nazwać przestrzeń (`--demo-*`) |
| Motyw | wyłącznie ciemny | OK dla domeny (klub, noc) — ale zapisać jako DECYZJĘ „dark-only by design", nie przemilczenie |

### Kompletność komponentów

Unikalna siła biblii: każdy z 83 komponentów ma właściciela, głos juniora,
ruch, czas i easing. Czego systemowo BRAK: **macierzy stanów**
(default/hover/focus/disabled/loading/error per komponent), wariantów
i rozmiarów. Biblia mapuje RUCH komponentów, nie ich pełną anatomię.
SIMPLE_MODE_DESIGN_SYSTEM.md miał zaczątki (Carbon-owa dyscyplina), ale
jest oznaczony jako historyczny.

### Działania priorytetowe

1. **Skala odstępów** (np. 4/8/12/16/24/32) + skala typograficzna — przed
   pierwszym ekranem GUI, bo potem każdy px trzeba będzie łapać ręcznie.
2. **Semantyzacja akcentów** z parą `--deck-a/--deck-b` na czele.
3. **Macierz stanów** dla komponentów P0 (przyciski, wiersze, pady, Gate).

---

## CZĘŚĆ 2 · Krytyka projektu

**Kontekst:** kierunek pre-implementacyjny dla desktopowego instrumentu
DJ-skiego; po syntezie TERRAIN×TUI. Etap: eksploracja → utrwalenie.

### Pierwsze wrażenie
Biblia wygląda jak laboratorium prawdziwego produktu, nie jak moodboard —
„specimen, nie mockup" to rzadka i cenna postawa. Tożsamość volt-na-czerni
mocna i własna (nie jest ani Rekordboxem, ani Abletonem).

### Użyteczność

| znalezisko | waga | rekomendacja |
|---|---|---|
| Model instrumentu (zakładki ≠ kroki) nie ma odpowiedzi na PIERWSZE uruchomienie — badanie person pokazało, że Zosia (rok grania, streaming) gubi się bez prowadzenia | 🔴 | „choreografia pierwszego biegu": readiness system prowadzi przez pierwszy import→pierwszy set→pierwszy szew BEZ wizarda — podświetlaniem jedynego aktywnego volta |
| 4 widoki + dock + inspector = gęsty chrome; na laptopie 13" może brakować przestrzeni roboczej | 🟡 | zdefiniować minimalny viewport i reguły zwijania (inspector chowany, dock kompaktowy) |
| „Jeden czasownik volt" — w praktyce TUI Set ma dwa uprawnione czasowniki (Buduj vs Wyślij) | 🟡 | Gate rozwiązuje zapis; przejrzeć per widok, czy volt jest naprawdę jeden |
| `emphasis 420 ms` przy „terrain revision" — jeśli Regrow będzie częsty, animacja zacznie irytować | 🟢 | test z realnym rytmem przebudowy |

### Hierarchia wizualna
Volt prowadzi wzrok bezbłędnie (jedna akcja główna). Ryzyko: pięć kolorów
akcentowych naraz w Automix (cyan/amber/green/red/violet) może rozmyć
hierarchię — reguła „maks jeden akcent uwagi na region" z inwentarza ruchu
musi obowiązywać też statycznie.

### Dostępność

| pomiar | wynik |
|---|---|
| `--ink` #f2f1e9 na `--ground` #11120f | ✅ ~15:1 |
| `--volt` na `--ground` | ✅ bardzo wysoki |
| **`--ink-dim` #73736c na `--ground`** | ⚠️ ~4:1 — poniżej AA dla małego tekstu; podnieść albo ograniczyć do tekstu ≥18 px |
| klawiatura | ✅ pełna klawiszologia TUI przechodzi — rzadka siła |
| reduced motion | ✅ wariant z zasady dla każdej animacji przestrzennej |

### Co działa świetnie
- Uczciwość jako prawo ruchu (zero fake progress) — spójna z ADR-005 silnika.
- SEAM jako pełnoprawny widok — teza produktu w architekturze informacji.
- Protokół przeglądu z zapisem sprzeciwu — kultura, nie tylko artefakt.

### Priorytety
1. **Choreografia pierwszego biegu** — jedyne krytyczne; reszta TERRAIN
   zakłada użytkownika, który już wie, po co przyszedł.
2. **Skale tokenów** (część 1) przed pierwszym ekranem.
3. **Kontrast ink-dim** — tania poprawka, zanim się rozmnoży.

---

## CZĘŚĆ 3 · Synteza badań

**Metody i próba:** test 4 person na instancjach aplikacji (biblioteki
z katalogu, 09–10.08) · obserwacja terenowa 1 realnego użytkownika przez
~5 tygodni (weta, iteracje, incydenty) · dane behawioralne 869 DJ-ów
z mapy (1 022 sety, 3 743 szwy) · diagnoza przypadku (Bartek → decyzja
zakresu). **Ograniczenia:** persony mierzą układ i komunikaty, nie gust;
jeden realny użytkownik; mapa przechyla ku setom publikowanym.

### Tematy

**T1 · Cisza jest wrogiem, odmowa nie.** (5/5 źródeł)
Każdy poważny incydent badań to była CICHA degradacja: brief gatunkowy
zdejmowany bez słowa (Immortal Technique w secie techno), pusta pula bez
powodu, klik w martwy przycisk („nie widzę cue"), zero ostrzeżeń przy
szwie 0,386. Użytkownik wybacza odmowę z powodem; nie wybacza milczenia.
→ **Implikacja:** readiness/ostrzeżenia/puste stany to GŁÓWNA powierzchnia
UX nowego UI, nie dekoracja. Standard: każda degradacja mówi, co i czemu.

**T2 · DJ wychodzi poza ramy co drugi ruch.** (dane 869 DJ-ów)
Sito 20% wycina 48% realnych następników; realny set robi medianę 5 zejść
energii, których stary łuk zabraniał; łuk obalony na dwóch instrumentach.
→ **Implikacja:** system PROPONUJE, nigdy nie zabrania; każde zawężenie
rozluźnialne i jawne. Dock terenu bez celu energetycznego.

**T3 · Tożsamość utworu > jego liczby.** (mapa + szkic Janka)
96% repertuaru gra się RAZ — liczby nie niosą tożsamości; niosą ją
konteksty: „czterech DJ-ów poszło z Dope w cztery światy" (kameleon)
vs „Page 1 mieszka w jednym świecie" (kotwica).
→ **Implikacja:** widok TRACK jako BIOGRAFIA (precedensy, funkcja,
występowanie), nie karta statystyk.

**T4 · Pady są święte i SĄ interfejsem szwu.** (Marta + Janek)
„Jedno nadpisane cue — odinstalowuje"; konflikt `skip` na zawsze; „szew
powstaje z moich padów"; pady na taktach RB („68.1, nie 68.2").
→ **Implikacja:** SEAM/CUE jeden widok; cudze pady nietykalne wizualnie
odróżnione od naszych (ledger UUID już to umie).

**T5 · Operator się nie skaluje.** (mapa TUI + audyt biblii)
Import RB i żniwa wektorów żyją w terminalu asystenta.
→ **Implikacja:** Job Center = P0 pierwszego ekranu z pracami w tle.

### Wnioski → szanse

| wniosek | szansa | wpływ | koszt |
|---|---|---|---|
| cisza = utrata zaufania (T1) | standard readiness + język komunikatów (po_polsku → GUI) | wysoki | średni |
| pierwsza sesja bez prowadzenia gubi (Zosia) | choreografia pierwszego biegu | wysoki | średni |
| tożsamość przez konteksty (T3) | TRACK-biografia z precedensami mapy | wysoki | średni |
| brak „Rest Tonight" (regres MOL05) | przywrócić wykluczenie na dziś | średni | niski |
| operator w pętli (T5) | Job Center | wysoki | średni |

### Segmenty (z badań person)

| segment | potrzeba rdzeniowa | dowód |
|---|---|---|
| purystka (Marta) | „pokaż, czego nie widzę — niczego nie ruszaj" | cue święte; sito jawne |
| rezydent jednego gatunku (Kuba) | kotwica spoza księgi → ★ z ulubionych | Amelie Lens nieobecna |
| pierwszy rok, streaming (Zosia) | prowadzenie bez wizarda; polszczyzna | odmowy odsłuchu muszą tłumaczyć |
| open-format (Bartek) | POZA ZAKRESEM (decyzja 10.08: na weselu nie ma szwu) | pomiar tempa/szwów |

### Pytania na dalsze badania
- Czy panel precedensów ZMIENIA wybory? (pętla werdyktów — po Job Center)
- Harmonia na uczciwych tonacjach (bieg RB w toku — rozstrzygnie flagę).
- Czy dock terenu realnie skraca nawigację? (test po pierwszym ekranie)
