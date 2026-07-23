# DanceLab Pro TERRAIN: product team charter

**Data:** 2026-07-15  
**Zakres:** wspólny zespół odpowiedzialny za UI, motion, runtime i jakość TERRAIN  
**Liczebność:** 21 ról: 3 Seniorów, 9 Midów i 9 Juniorów

## 1. Zasada zespołu

Wszyscy pracują nad jednym produktem i jednym backlogiem. Senior jest odpowiedzialny za decyzję końcową w swojej domenie, ale nie jest jedynym źródłem pomysłów. Każda osoba ma obowiązek zgłosić ryzyko albo lepsze rozwiązanie niezależnie od poziomu stanowiska.

Junior może zatrzymać decyzję, jeśli pokaże reprodukowalny błąd, naruszenie dostępności, rozjazd audio/UI albo sprzeczność ze źródłem prawdy. Sprzeciw nie może zostać usunięty z dokumentacji bez odpowiedzi.

## 2. Struktura

### 2.1 Engineering

**E-SR - Senior Full-Stack / Desktop Architect**  
Odpowiada za architekturę hosta, granice silnik/UI, stan sesji, wydajność i możliwość przejęcia projektu przez innego developera.

| Mid | Zakres | Junior | Wkład Juniora |
|---|---|---|---|
| E-M1 Desktop UI / Qt | Qt Widgets, event loop, komponenty, accessibility API | E-J1 UI Runtime | implementacyjne spike'i, keyboard paths, edge cases widgetów |
| E-M2 Audio / Realtime | transport, preview, synchronizacja, threading, cache | E-J2 Playback QA | seek/pause/resume tests, logi driftu, reprodukcja audio bugs |
| E-M3 QA / Tooling | test pyramid, profiling, packaging, handoff | E-J3 Test Automation | fixtures, screenshot tests, test matrix i raport regresji |

### 2.2 Product Design

**PD-SR - Senior Product Designer / Design System Architect**  
Odpowiada za model mentalny produktu, hierarchię, workflow TERRAIN, komponenty i spójność z realnymi zadaniami DJ-a.

| Mid | Zakres | Junior | Wkład Juniora |
|---|---|---|---|
| PD-M1 Information Architecture | LIBRARY/SET/SEAM/TRACK, navigation, selection continuity | PD-J1 UX Research | testy zrozumiałości, first-click notes, terminologia użytkowników |
| PD-M2 Design Systems | atomy, molekuły, organizmy, tokeny, responsive rules | PD-J2 Component QA | stany brakujące, porównania ekranów, consistency checklist |
| PD-M3 Accessibility / Content | keyboard, contrast, copy, errors, progressive disclosure | PD-J3 Content QA | mikrocopy, tooltip clarity, empty/error state review |

### 2.3 Motion Design

**MD-SR - Senior Motion Designer / Motion System Lead**  
Odpowiada za język ruchu, timing, easing, choreografię, reduced motion i zgodność animacji z fizyką interakcji oraz transportem audio.

| Mid | Zakres | Junior | Wkład Juniora |
|---|---|---|---|
| MD-M1 Interaction Motion | taby, drawers, selection, drag/snap, modale | MD-J1 Microinteraction QA | replay tests, timing porównawczy, wykrywanie nadmiarowego ruchu |
| MD-M2 Audio-Reactive Motion | Automix, playhead, beat phase, EQ/fader envelope | MD-J2 Sync QA | frame-by-frame porównanie audio/UI, drift i seek tests |
| MD-M3 Motion Prototyping | motion tokens, prototypy, performance budgets | MD-J3 Timing QA | katalog easingów, reduced-motion variants, dropped-frame notes |

## 3. Rozmowa projektowa

Każdy komponent przechodzi krótką rundę w tej kolejności:

1. **Junior evidence** - reprodukcja, obserwacja użytkownika, screenshot, pomiar albo brakujący stan.
2. **Mid synthesis** - konsekwencje dla swojej specjalizacji i propozycja rozwiązania.
3. **Cross-discipline challenge** - pozostałe dwie domeny wskazują konflikt albo koszt.
4. **Senior decision** - decyzja, warunki akceptacji i właściciel implementacji.
5. **Dissent record** - nierozwiązane zastrzeżenie pozostaje jawne z datą powrotu.

Nie organizujemy głosowania popularności. Decyzja musi być zgodna z runtime truth, potrzebą użytkownika i budżetem wydajności.

## 4. Obowiązkowy zapis przy komponencie

Każdy interaktywny komponent w Biblii posiada:

- właściciela kodu;
- właściciela produktu;
- właściciela motion;
- źródło stanu;
- trigger;
- finalny stan;
- timing i easing;
- reduced-motion variant;
- test keyboard/pointer;
- test performance;
- głos Juniora: obserwacja albo potwierdzenie braku uwag;
- status Engineering, Product i Motion;
- jawny dissent, jeśli istnieje.

## 5. Statusy review

| Status | Znaczenie |
|---|---|
| `DISCOVERY` | komponent istnieje jako potrzeba, ale kontrakt nie jest zamknięty |
| `SPEC READY` | mapowanie kod/UI/motion i kryteria są kompletne |
| `PROTOTYPE` | zachowanie można obejrzeć i przerwać, ale nie jest jeszcze spięte z runtime |
| `IMPLEMENTED` | komponent działa z prawdziwym stanem aplikacji |
| `VALIDATED` | przeszedł test funkcjonalny, motion, accessibility i performance |
| `DEFERRED` | świadomie poza bieżącym zakresem z zapisanym powodem |

## 6. Definition of Ready

Komponent może wejść do implementacji, gdy:

- Product potwierdził zadanie użytkownika i hierarchy;
- Engineering potwierdził źródło stanu i granicę wątku GUI;
- Motion potwierdził choreografię, timing i reduced motion;
- Midowie uzupełnili stany loading/empty/error/interrupted;
- Juniorzy wykonali checklistę i zgłosili brakujące przypadki;
- nie istnieje nierozwiązany blocker dotyczący identity tracka, transportu audio albo zapisu danych.

## 7. Definition of Done

`VALIDATED` wymaga równocześnie:

- **Engineering:** test finalnego stanu, przerwania, pamięci i GUI-thread budget;
- **Product:** first-click test, czytelny next action i brak utraty kontekstu;
- **Motion:** zgodność z tokenami, brak konkurujących akcentów i reduced motion;
- **Junior QA:** niezależna reprodukcja na małym/dużym oknie, myszą, touchpadem i klawiaturą.

Seniorzy podpisują wynik dopiero po przeczytaniu głosów Midów i Juniorów.

## 8. Pierwszy wspólny wniosek dla Automix

| Rola | Wkład |
|---|---|
| E-J2 Playback QA | Jeden timer na gałkę stworzy drift; wymagany jest jeden frame oparty na transport position. |
| E-M2 Audio / Realtime | Audio render pozostaje poza GUI thread; UI interpoluje gotowy `TransitionEnvelope`. |
| E-SR Full-Stack | `ProjectSession` przechowuje wybór i plan, ale chwilowy frame playbacku należy do kontrolera transportu. |
| PD-J1 UX Research | Użytkownik musi rozumieć moment cue-in, handover i cue-out bez czytania legendy wykresu. |
| PD-M1 IA | Automix jest częścią `SEAM`, nie nowym trybem całej aplikacji. |
| PD-SR Product | Główną akcją jest `Preview transition`; ręczna edycja automatyki nie wchodzi do pierwszej wersji. |
| MD-J2 Sync QA | Pause musi zatrzymać playhead, beat phase, EQ i fadery w tej samej klatce. |
| MD-M2 Audio Motion | Wszystkie warstwy używają jednej domeny czasu przejścia. |
| MD-SR Motion | Sprężyna służy cue snap, nie ruchowi wartości audio. EQ/fadery poruszają się deterministycznie. |

**Decyzja:** pierwszy Automix wizualizuje i odtwarza plan silnika. Nie udaje live miksera, nie zapisuje automatyki i nie uruchamia niezależnych animacji.
