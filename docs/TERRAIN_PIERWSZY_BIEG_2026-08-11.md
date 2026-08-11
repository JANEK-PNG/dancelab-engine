# Choreografia pierwszego biegu — pierwsza sesja bez wizarda

**Data:** 2026-08-11 · Odpowiedź na jedyne krytyczne znalezisko krytyki
TERRAIN: model instrumentu (zakładki ≠ kroki) nie mówił, jak wygląda
PIERWSZE uruchomienie. Badanie person: Zosia (rok grania, sam streaming)
gubi się bez prowadzenia; Marta odinstaluje przy pierwszym naruszeniu jej
rzeczy. Choreografia musi prowadzić NIE wprowadzając kroków.

## 0 · Decyzja projektowa nadrzędna

**Choreografia nie jest osobnym silnikiem samouczka. Jest WIDOKIEM stanu
gotowości.** Aplikacja i tak wie, co jest możliwe (readiness); pierwszy
bieg to tylko dwie rzeczy ponad to:

1. **W każdej chwili świeci dokładnie JEDEN volt** — akcja, która
   popycha świat do przodu. Wszystko inne widoczne i uczciwie wyłączone
   z powodem. To jest reguła TERRAIN („jeden czasownik główny"),
   choreografia jej nie dodaje — tylko ją EGZEKWUJE od pierwszej sekundy.
2. **Nowość wita się raz.** Kiedy coś istnieje pierwszy raz (pierwsza
   analiza, pierwszy set, dock, pierwszy szew), dostaje jednorazowy ruch
   orientacji (token `emphasis`, 420 ms) i ani razu więcej.

Zakazy twarde: żadnych modalnych dymków „czy wiesz, że…", żadnych
checkmarków ukończenia, żadnego blokowania WIDOKÓW (blokują się AKCJE,
z powodem), żadnego kroku „dalej/wstecz". Użytkownik może w każdej chwili
zejść ze ścieżki — choreografia nie zawraca, tylko dalej pokazuje jedyny
aktywny volt tam, gdzie jest.

## 1 · Graf gotowości (kontrakt warstwy stanu — wspólny dla obu skór)

```
ReadinessState:
  biblioteka: pusta | analiza_w_toku | gotowa
  set:        brak | jest | niezgodny_z_briefem
  pady:       brak | sa
  rekordbox:  niepodpiety | otwarty | zamkniety
  pliki:      zero | czesc | wszystkie     # odsłuch zależy od plików, nie od analiz

volt(widok, stan) -> (etykieta, akcja) | (etykieta, powod_wylaczenia)
nowosc(byt) -> bool                        # pierwsza analiza / pierwszy set / pierwszy szew / pierwszy zapis
```

Choreografia = czysta funkcja z ReadinessState; zero własnej pamięci poza
flagami `nowosc` (gasną po jednym pokazaniu; trwałe w stanie użytkownika).

## 2 · Sceny

### Scena 1 · Pusta aplikacja (LIBRARY)

Widok: pusta tabela NIE jest pustką — jest zaproszeniem.

> **Tu zamieszka Twoja muzyka.**
> Wskaż folder z plikami albo podepnij Rekordboxa. Analiza policzy każdemu
> utworowi tempo, tonację i energię — od tego zaczyna się wszystko.

Volt: **„Dodaj muzykę"** (folder / Rekordbox — dwa źródła, jeden przycisk
z wyborem). Pozostałe widoki: dostępne; ich puste stany mówią, czego im
brakuje, i linkują do Biblioteki (readiness deep-link, nie zamknięte drzwi):

> SET: „Set buduje się z przeanalizowanej biblioteki — a ona jest jeszcze
> pusta. Zacznij od dodania muzyki." → [Do Biblioteki]

Ruch: brak. Nic się nie dzieje, dopóki użytkownik nie działa.

### Scena 2 · Analiza w toku

Job Center pokazuje prawdę i tylko prawdę (`A07/A08` z biblii):

> Analizuję **47 z 230** · „Balearic Breeze" · ~4 min

Wiersze tabeli pojawiają się w miarę ukończenia (stagger 24 ms, tylko
widoczne). Odrzuty bramkarza — imiennie, od razu, nie na końcu:

> 3 pliki odłożone: uszkodzone albo bez audio. [Pokaż które]

Volt w LIBRARY gaśnie na rzecz joba; volt w SET zapala się już przy
pierwszych N gotowych analizach (nie czekamy na komplet — uczciwie:
„Zbuduj set z tego, co już policzone (58)").

### Scena 3 · Pierwszy set

Volt: **„Zbuduj pierwszy set"**. Brief wstępnie wypełniony uczciwymi
domyślnymi (30 min · bez gatunku · bez kotwicy · **łuk: bez łuku —
zmierzone**), wszystko widoczne i zmienialne, nic nie ukryte „dla
uproszczenia". Po budowie:

- tabela setu wjeżdża (base 220 ms),
- **dock terenu pojawia się pierwszy raz** — jedyny moment choreografii
  z ruchem `emphasis`: dock wysuwa się i raz podświetla całość,
- ostrzeżenia, jeśli są, od razu widoczne (licznik + dymek dla ważnych) —
  pierwszy bieg NICZEGO nie wycisza; zaufanie buduje się od pierwszej
  minuty (T1 syntezy: cisza jest wrogiem).

> Nowość (raz): „To jest teren Twojego setu — kolejność, energia i jakość
> każdego połączenia. Będzie z Tobą w każdym widoku."

### Scena 4 · Pierwszy szew

Po istnieniu setu volt przenosi się: **„Obejrzyj pierwszy szew"** —
wskazuje styk o NAJWYŻSZEJ ocenie (pierwsze wrażenie ma być prawdziwe
i dobre; najsłabszy szew pokazujemy w ostrzeżeniach, nie na powitanie).
Klik → SEAM/CUE z anatomią: okna, pady zaproponowane przez silnik
(z kropką „silnik proponował"), oś.

Przypadek Zosi (pliki: zero — sama biblioteka strumieniowa) — odmowa
z powodem i z drogą wyjścia, nie ślepy zaułek:

> **Nie zagram odsłuchu: ten utwór to strumień, nie mam jego pliku.**
> Plan, pady i wysyłka do Rekordboxa działają normalnie — odsłuch obudzi
> się przy utworach z plikami.

### Scena 5 · Pierwszy zapis (Gate)

Volt: **„Wyślij pady do Rekordboxa"** — zapala się tylko, gdy pady
istnieją. Gate pokazuje manifest (co, gdzie, czyje pady ustępują — pad
DJ-a NIETYKALNY, mówimy ile ustąpiło), wymaga drugiego potwierdzenia
(wzorzec dwóch naciśnięć z TUI). Rekordbox otwarty = przycisk wyszarzony
Z POWODEM („Zamknij Rekordbox, żeby zapisać — baza musi być wolna").

Po pierwszym udanym zapisie:

> Nowość (raz): „Pady są w Rekordboksie. Od teraz to jest pętla: biblioteka
> → set → szwy → pady. Twoja."

**I choreografia się rozpuszcza.** Flagi nowości zgaszone, volt przestaje
być „jedyny prowadzący" — wraca zwykła reguła TERRAIN (jeden czasownik na
kontekst). Żadnego „ukończyłeś wprowadzenie", żadnej odznaki.

## 3 · Zejścia ze ścieżki (to nie są błędy)

| ruch użytkownika | odpowiedź choreografii |
|---|---|
| wchodzi w SEAM przed setem | pusty stan: „Szew powstaje między utworami setu — a setu jeszcze nie ma." → [Zbuduj set] ; volt globalny się NIE zmienia |
| buduje set z 12 utworów zamiast czekać na 230 | wolno; ostrzeżenia sit mówią, ile puli brakowało |
| ignoruje szwy, od razu Gate | Gate uczciwie: „Nie ma jeszcze żadnych padów do wysłania." → [Do szwów] |
| zamyka aplikację w połowie | autosave; po powrocie choreografia liczy się z ReadinessState od nowa — nie pamięta „gdzie byłeś", bo nie musi |
| mówi „znam się" (ustawienie) | flagi nowości zgaszone hurtem; readiness zostaje (on nie jest samouczkiem) |

## 4 · Ruch (tokeny z biblii, nic nowego)

| moment | token | uwaga |
|---|---|---|
| zapalenie/przeniesienie volta | fast 140 | jedyny stały akcent choreografii |
| wjazd wierszy analizy | stagger 24 | tylko widoczne wiersze |
| wjazd tabeli setu | base 220 | |
| pierwsze pojawienie docku | emphasis 420 | RAZ w życiu aplikacji |
| komunikat nowości | enter/exit, base | znika sam po przeczytaniu (dismiss lub 8 s) |
| odmowy i powody | bez animacji | uczciwość nie potrzebuje ruchu |

## 5 · Język

Wszystkie teksty po polsku, ton: kumpel pokazujący coś fajnego — nigdy
oceniająco. Zakaz żargonu bez wyjaśnienia przy pierwszym użyciu (Camelot,
BPM — Zosia nie wie, co to Camelot: pierwsze użycie ma dopisek „(koło
tonacji — sąsiednie numery dobrze brzmią obok siebie)"). Komunikaty
silnika przechodzą przez tę samą warstwę tłumaczeń co TUI (`po_polsku`),
więc obie skóry mówią jednym głosem.

## 6 · Pomiar sukcesu (bez zgadywania)

Instrumentacja pierwszego biegu (lokalna, jak werdykty TUI):
- czas do pierwszego setu i do pierwszego zapisu padów;
- gdzie bieg utknął (ostatnia scena przed porzuceniem sesji);
- ile razy kliknięto wyłączoną akcję (miara: czy powody są czytane);
- czy użyto „znam się".

Progi sukcesu ustalimy po pierwszych realnych biegach — nie zmyślamy
liczb przed pomiarem (ADR-005).

## 7 · Co obie skóry biorą od razu

TUI może przejąć TERAZ, bez GUI: teksty pustych stanów ze Scen 1–5
(obecne są uczciwe, ale nie prowadzą), regułę „najlepszy szew na
powitanie" i komunikat odmowy odsłuchu dla strumieni w brzmieniu ze
Sceny 4. Kontrakt `ReadinessState` wchodzi do warstwy stanu jako pierwszy
kontrakt nowego UI — mały, czysty, testowalny.
