# R&D Brief — „Ostatnia mila": cue do Rekordboxa BEZ instrukcji

**Zleceniodawca:** Janek (Product Owner) · **Data:** 2026-07-22 · **Priorytet:** wysoki
**Właściciel R&D:** Kord (od 25.07) + Klaris (research wspierający)
**Zasada nadrzędna (rejestr 22.07):** *„Jeśli eksport wymaga instrukcji — eksport jest niedokończony."*

---

## 1 · Problem (case źródłowy, 2026-07-22)

Wyeksportowaliśmy playlistę z 26 poprawnymi hot cue (pady A/B/C, `POSITION_MARK
Num 0..2`) w formacie rekordbox.xml. Product Owner — doświadczony DJ — **nie
zobaczył ani jednego cue.** Powody systemowe:

1. M3U nie niesie cue (użytkownik nie ma jak tego wiedzieć).
2. Rekordbox **nie nadpisuje** wpisów istniejących w kolekcji przy imporcie
   z gałęzi xml — a tracki użytkownika Z DEFINICJI już są w jego kolekcji
   (to jego biblioteka!). Nasz główny przypadek = zawsze konflikt.
3. Obejście („załaduj na deck z gałęzi xml") wymaga instrukcji → churn po
   drugim użyciu.

## 2 · Use case AS-IS (dzisiejszy, bolesny)

Persona: **Kasia, 27, DJ-ka weekendowa.** Zna Rekordbox z YouTube. Nie czyta
dokumentacji. Ceni swoje własne hot cue jak własne dziecko.

1. Kasia buduje set w DanceLab, klika „Eksport". Dostaje plik.
2. Musi: Preferences → Advanced → wskazać xml → włączyć widok rekordbox xml
   → znaleźć gałąź → przeciągnąć playlistę.
3. Cue nie widać (tracki już w kolekcji). Kasia nie wie dlaczego.
4. Po drugim takim razie: **„nie chce mi się"** → churn. Produkt umiera na
   ostatniej mili, mimo że silnik zrobił wszystko dobrze.

## 3 · Use case TO-BE (definicja snu)

1. Kasia klika **„Wyślij do Rekordbox"**.
2. Otwiera Rekordbox.
3. Playlista jest. **Cue świecą na padach** w wersji tracka, którą gra.
4. Koniec.

Dopuszczalne: JEDEN kreator konfiguracyjny przy pierwszym uruchomieniu
(z obrazkiem), nigdy więcej.

## 4 · Kryteria akceptacji (Definition of Solved)

| # | kryterium |
|---|---|
| A1 | Od **drugiego** eksportu: zero instrukcji, ≤3 kliknięcia od „Eksport" do grania z cue |
| A2 | Cue widoczne jako **hot cues na padach** w wersji tracka, którą user faktycznie ładuje |
| A3 | **Nigdy** nie niszczymy/nadpisujemy danych usera bez jawnej zgody — w szczególności JEGO własnych cue (konflikt → user wins albo jawny wybór; spójne z planowanym CueDecisionStore) |
| A4 | Update Rekordboxa nie powoduje korupcji: rozwiązanie działa albo **bezpiecznie degraduje z komunikatem** |
| A5 | Invariant nietykalny: BPM/beatgrid nie są zapisywane |
| A6 | Bez chmury; wszystko lokalnie |

## 5 · Ścieżki do zbadania (otwarte — R&D decyduje po dowodach)

**A. Fixed-path XML + auto-setup** *(ryzyko: średnie)*
Aplikacja pisze ZAWSZE w jedną ścieżkę xml; kreator (raz) ustawia preferencję
Rekordboxa. Zbadać: czy ścieżka xml w ustawieniach RB jest edytowalna plikowo
przy zamkniętym RB (gdzie żyją ustawienia, format, checksumy?). Quirk
tracków-już-w-kolekcji ZOSTAJE — mitygować UX-em? Czy to przechodzi A2?

**B. Zapis wprost do bazy Rekordboxa** *(precedens: Lexicon — ryzyko: wysokie)*
master.db = SQLCipher. Zbadać: czy klucz jest publicznie znany i stabilny
między wersjami; jak dokładnie robi to Lexicon (tryb, backupy, tylko przy
zamkniętym RB?); test destrukcyjny 100 cykli zapisu na bazie testowej;
rollback <5 s. Jedyna ścieżka w pełni spełniająca A2 dla tracków w kolekcji.

**C. Eksport device/USB (PDB)** *(ryzyko: wysokie)*
Format zamknięty; istnieją biblioteki do CZYTANIA (deep-symmetry
crate-digger). Zapis = teren nieznany. Zbadać wykonalność zapisu.

**D. Automatyzacja UI Rekordboxa** *(ryzyko: średnie/kruche)*
AppleScript/dostępność: aplikacja sama przeprowadza kroki importu w RB.
Kruche na wersje/układ okien — raczej fallback niż rozwiązanie.

**E. Oficjalne API** — potwierdzić stan 2026 (historycznie: brak publicznego
API zapisu). Jeśli się pojawiło — zmienia wszystko.

## 6 · Pytania badawcze (konkretne, po kolei)

1. Gdzie i w jakim formacie żyją ustawienia RB (ścieżka xml, widok)? Edytowalne?
2. Czym Lexicon pisze do RB6/7? (changelog, fora, analiza) Jak mityguje ryzyko?
3. Klucz SQLCipher master.db: publiczny? stabilny między 6.x/7.x?
4. Dokładne zachowanie kolizji kolekcja-vs-xml w RB 7 (test empiryczny, macierz wersji).
5. Czy RB w ogóle odświeża cue z xml dla tracka NIEobecnego w kolekcji po
   ponownym imporcie? (test)

## 7 · Mierniki sukcesu prototypu

- Świeży RB 7.x + biblioteka testowa z traками JUŻ w kolekcji → po eksporcie
  z DanceLab **pady świecą bez żadnej instrukcji** (nagranie wideo jako dowód).
- 100 cykli zapisu bez korupcji; restore z backupu <5 s.
- Zero utraconych user-cue w teście konfliktowym (nasze vs jego).

## 8 · Powiązania

- **EXPORT GATE (Terrain blueprint)** — ten brief ZMIENIA definicję done bramki:
  nie „zapisz poprawny plik", tylko „dostarcz cue na pady bez instrukcji".
- **CueDecisionStore** (planowany) — polityka konfliktów cue (user wins).
- Rejestr projektu: zasada „eksport bez instrukcji" + pytanie #6 do Janka
  (kierunek A-bezpieczny vs B-Lexicon-style).
