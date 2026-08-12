# Wybór DJ-a bez znajomości nazwisk: „Brzmi jak…", rekomendacje i karty DJ-ów

> **Language note (English).** Like PROJECT_LEDGER.md, this design spec is kept
> in Polish deliberately: it is the project owner's review artifact and he
> reviews specs in Polish. Code and commits stay English per
> docs/DOCUMENTATION_STANDARD.md.

**Data:** 2026-08-12 · **Status:** projekt zatwierdzony ustnie przez Janka
(wariant C + B+C + katalog ze znaczkiem „poznany"), spisany do przeglądu.

## Problem

Pole „Graj jak…" wymaga znajomości nazwisk DJ-ów. Kto ich nie zna (w tym
autor aplikacji), stoi przed egzaminem, nie wyborem. Osobno: chcemy, żeby
temat DJ-ów CIEKAWIŁ — aplikacja może uczyć, nie tylko obsługiwać.

Diagnoza z rozmowy: to są DWIE prace, nie jedna —
1. szybki wybór kotwicy bez nazwisk (narzędzie),
2. wciągnięcie w świat DJ-ów (odkrywanie).

Decyzja Janka: obsługujemy obie, w dwóch miejscach, spięte jednym mostkiem.

## Znalezisko badawcze

Kotwica z ulubionych utworów JUŻ ISTNIEJE w silniku (build: „kotwica z
Twoich ulubionych: N utworów") i jest niewidoczna — autor o niej nie
wiedział. Wniosek: zanim dobudujemy nowe, wyciągamy istniejące na światło.

## Projekt

### 1. Brief: „Brzmi jak te utwory" (fundament)

Pole „Graj jak…" dostaje równorzędną alternatywę: użytkownik wskazuje 2–3
utwory ze swojej biblioteki i one stają się kotwicą brzmienia.
**Decyzja copy (Janek 12.08, wdrożona):** pole nazywa się od teraz
„Brzmi jak…" — jedna rodzina kotwic (DJ, utwory, karty) pod jednym
czasownikiem brzmienia; zmienione w TUI, pomocy CLI i wiernej makiecie. Silnik już
to umie — zmiana dotyczy widoczności: wybór wprost (nie przez serduszka),
jasna etykieta w briefie, czym set będzie pachniał.

### 2. Rekomendacje: „kto brzmi jak moja biblioteka?" (drugi krok)

Guzik w briefie → trzy nazwiska z odległością brzmieniową („Twoja muzyka
leży najbliżej setów X, Y, Z"). Klik = kotwica; druga droga = otwarcie
karty DJ-a. Pierwszym DJ-em, którego użytkownik poznaje, jest ten, który
brzmi jak on sam — to jest most między pracą 1 i 2.

**BRAMKA POMIAROWA (blokująca):** profile DJ-ów liczone z próbek 30 s,
biblioteka użytkownika z pełnych plików; źródła są odróżnialne
(AUC 0,889). Przed włączeniem guzika: test na znanych parach, czy
porównanie między źródłami nie kłamie. Jak kłamie — wektory użytkownika
przeliczamy z 30-sekundowych wycinków (zgodność źródeł) i test powtarzamy.
Bez zdanej bramki guzik nie wchodzi do UI. Reguła ta sama co zawsze:
najpierw zapytanie-bzdura / pary kontrolne, potem produkt.

### 3. Zakładka „DJ-e": ściana kart

- **Katalog od razu, KOLEKCJA zamiast „poznanych"** (Janek 12.08,
  nadpisuje wcześniejszy znaczek „poznany"): karta ma guzik
  „＋ DO KOLEKCJI"; DJ-e z kolekcji są pełnokolorowi ze znaczkiem
  „✓ W KOLEKCJI", reszta wyszarzona, licznik „w kolekcji: N z M".
  Kolekcja to RĘCZNY wybór użytkownika (odsłuch może kiedyś podpowiadać,
  ale nie dodaje sam). Zero zamkniętych drzwi — wszystkie karty widoczne.
  **Kolekcja karmi brief:** w polu „Brzmi jak…" DJ-e z kolekcji mają
  PIERWSZEŃSTWO na liście i zielony checkmark obok nazwiska — kolekcjonujesz
  na ścianie kart, zbierasz owoce przy budowie.
- **Karta = wyłącznie pomiary z prawdziwych setów DJ-a w mapie:**
  zakres temp (percentyle 10–90 + mediana), % przejść zgodnych
  harmonicznie, mediana skoku tempa na szwie, energia / gęstość groove'u /
  obecność basu (mediany po utworach), liczba setów i szwów w mapie,
  festiwale/źródła. Pola bez pomiaru = „—", nigdy zmyślone.
- **Zero zdjęć** (prawa autorskie: 869 cudzych fotek prasowych to prawne
  bagno). W miejscu grafiki Pokémona — **portret brzmienia**: deterministyczna
  grafika generowana WYŁĄCZNIE z pomiarów DJ-a (ziarno = ksywa; energia →
  wysokość szczytów, typowy skok tempa → poszarpanie grani, mediana tempa →
  ciepło koloru, bas → ciemność pierwszego planu). Unikalna jak odcisk palca,
  legalnie nasza, skaluje się na 869 kart bez jednego maila o licencję.
  Opcja na przyszłość (Pro): DJ odbiera swoją kartę i sam wgrywa zdjęcie —
  wtedy prawa załatwia właściciel twarzy.
- **Zero rankingów** „lepszy/gorszy" — karty się porównuje, nie ocenia
  (ton DanceLab: kumpel, nie oceniający). Oś „komercyjny ↔ uznany" wejdzie
  dopiero, gdy będzie policzona dla wszystkich kart naraz — jako współrzędna,
  nie ocena.
- **Odsłuch (pomysł Janka 12.08):** kartę da się USŁYSZEĆ — „▶ posłuchaj
  setu" rozwija wbudowany odtwarzacz SoundCloud z prawdziwym setem z mapy
  (set_link z bazy). Świadomie NIE zamiast portretu, tylko obok: (1) 551
  iframe'ów na ścianie zabija przeglądarkę → odtwarzacz ładuje się na klik,
  (2) linki do setów umierają, portret z pomiarów renderuje się zawsze,
  (3) embed niesie brand SoundCloud — twarzą karty zostaje nasz portret.
  Dźwięk startuje wyłącznie od kliknięcia użytkownika w play. Prawa czyste:
  embed hostuje SoundCloud z pełną atrybucją artysty. Furtka: odsłuch może
  w przyszłości oznaczać kartę jako „poznaną".
- **Mostek:** na każdej karcie jeden czasownik — „＋ DO KOLEKCJI"
  (trzecia iteracja copy 12.08: „Graj jak ten" odrzucone — wiszący
  zaimek i ton rozkazu; „Buduj w tym stylu" nadpisane decyzją Janka —
  karta nie odpala budowy, karta się KOLEKCJONUJE, a budowę w stylu
  robi pole „Brzmi jak…", gdzie kolekcja ma pierwszeństwo).
- Karty bez pełnego profilu (mało szwów policzonych) = karta uproszczona:
  nazwa + to, co wiemy, z uczciwą etykietą „profil w budowie".

### 4. Kolejność budowy

1. **Mockup HTML** karty i ściany kart na prawdziwych danych 3 DJ-ów
   z mapy (Tim Reaper, Piasecki, Catz 'n Dogz — `karty_pilot3.json`),
   w języku wizualnym TERRAIN (grafit, volt tylko na wybór/czasownik,
   promień ≤3 px). Janek ogląda i wetuje.
2. Równolegle: bramka pomiarowa rekomendacji (pkt 2).
3. Punkt 1 (brief „brzmi jak te utwory") w prawdziwym TUI.
4. Reszta wedle werdyktu z mockupu.

## Poza zakresem (świadomie)

- Zdjęcia/biogramy DJ-ów, scrapowanie socialí.
- Rankingi i oceny.
- Kafelki brzmienia („ciemno/jasno") — odłożone: słowa znaczą różnie
  dla różnych ludzi, wraca jak będzie pomysł na kalibrację.
- Odblokowywanie kart (grywalizacja przez ukrywanie) — odrzucone.

## Kryteria sukcesu

- Użytkownik nieznający ŻADNEGO nazwiska buduje set z kotwicą w ≤3 ruchy.
- Każda liczba na karcie ma źródło w mapie (spot-check: karta vs zapytanie
  do fakty_szew/encje_utwor daje te same wartości).
- Mostek „graj jak ten" ustawia kotwicę bez wpisywania czegokolwiek.
