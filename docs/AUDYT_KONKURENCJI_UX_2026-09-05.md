# Audyt doświadczenia konkurencji: aplikacje do przygotowania setu DJ-skiego

**Kształt produktu:** narzędzie desktopowe do prepu (fala + hot cue + biblioteka) — żaden z kształtów
stron www ze skillu nie pasuje, więc nie naginam.
**Data:** 2026-09-05 (dwa przebiegi: ekran zablokowany → puste decki; ekran odblokowany → decki z utworem)
**Pole:** 6 aplikacji · **na żywo:** 2 · **zrzuty producenta:** 4
**Stan audytu:** `partial` — 4 z 6 widziane wyłącznie w stanach wyreżyserowanych przez producenta.

Plik leży w `docs/` po polsku (konwencja repo), nie w korzeniu jako
`experience-audit-*.md`, jak każe skill. Zrzutów nie wkładam do repo: pokazują
prawdziwą kolekcję i nazwy playlist.

---

## Pole

| Aplikacja | Jak obejrzana | Co realnie widać |
|---|---|---|
| rekordbox 7 | **na żywo**: PERFORMANCE z pustymi deckami, potem **EXPORT z załadowanym utworem** | fala dwupasmowa (niebieski/pomarańcz), pasek przeglądowy + pasek zbliżony z ⊕/⊖, lista hot cue A–H po prawej (pusta), CUE/▶ po lewej, karty MEMORY/HOT CUE/INFO, tonacja w nagłówku tekstem („11B"), browser z kolumną Preview (miniatury fal) |
| djay Pro | **na żywo**: puste decki, potem utwór załadowany | pasek przeglądowy wielokolorowy, pionowa fala zbliżona z numerami taktów, tonacja jako **kolorowy chip** w nagłówku decka, 2×4 pady „+", panel Automix z dopasowaniami (okładka + BPM + tonacja). **Ładowanie startuje odtwarzanie samo** |
| Serato DJ Pro | zrzuty producenta (widok domyślny + Prepare) | stan wyreżyserowany |
| Traktor Pro 4 | jeden zrzut producenta | 4 decki, browser; liczba padów nieczytelna |
| Lexicon | zrzuty producenta (demo3 = ekran utworu, demo5 = Smart Fix) | fala przeglądowa, siatka biblioteki, edytor zbiorczy |
| Mixed In Key 11 Pro | zrzuty producenta (DJ Mix, Looping) | dwa decki nad listą, fala **jednobarwna**, flagi Cue 1–8 nad falą, chip tonacji, Energy, lista z Cover Art / Key / Tempo / Energy / Cue Points / Rating |

Asymetria do nazwania: na żywo widziałem stany puste **i** załadowane; producent
pokazuje wyłącznie wypełnione i wyreżyserowane. Porównanie stanu pustego istnieje tylko
dla dwóch apek. Reguła „3 z N" liczona przy **N = 6**.

## Tłumaczenie wymiarów

Skill jest napisany pod sklepy. Tutaj: zadanie główne = załadować utwór → zobaczyć falę
z cue; powierzchnia towaru = ile biblioteki widać naraz; nawigacja = drzewo playlist vs
pole szukania; sygnały zaufania = skąd wiadomo, że BPM, tonacja i siatka są pewne.

---

## Podsumowanie

| Wymiar | Wynik | Wzorzec jednym zdaniem |
|---|---|---|
| 1. Zadanie główne | wzorzec | deck (fala + transport + pady) na górze, biblioteka na dole; 5 z 6 |
| 2. Rejestr i gęstość | wzorzec | ciemny „panel instrumentu", drobny tekst, zero pustki; 6 z 6 |
| 3. Powierzchnia biblioteki | wzorzec | tabela z okładką, BPM, tonacją; tonacja jako kolorowy chip w liście 4 z 6; ocena 4 z 6 |
| 4. Nawigacja i szukanie | wzorzec | drzewo źródeł/playlist po lewej + szukajka wtórna; 6 z 6 |
| 5. Rejestr marki | mieszany | instrument (rekordbox, Traktor, Serato) vs konsumencki (djay) vs narzędziowy (Lexicon, MIK) |
| 6. Sygnały zaufania | wzorzec | tonacja i BPM zawsze widoczne; źródło analizy **nigdzie** |
| 7. Konwencje pola | patrz niżej | |

---

## Wzorce w polu

### 1. Zadanie główne

Największy i najwcześniejszy element interaktywny: **deck** — fala, transport, pady.
Biblioteka pod spodem: rekordbox, djay, Serato, Traktor, MIK (5 z 6). Lexicon odwraca —
jedna fala przeglądowa na całą szerokość u góry, reszta to biblioteka, bo to narzędzie
do biblioteki, nie do grania.

Droga do zadania w stanie pustym (2 z 2 na żywo): „Not Loaded" / „No Playlist Selected"
**bez jednego zdania, co zrobić**; djay dodatkowo otwiera dymek o zewnętrznym mikserze,
niezwiązany z pierwszym krokiem. Po załadowaniu: rekordbox EXPORT czeka (▶ po lewej,
nic nie gra), **djay startuje odtwarzanie sam** — obserwacja z jednej apki, nie
konwencja; w naszym oknie dźwięk rusza wyłącznie z gestu i to zostaje.

**Wzorzec:** deck nad biblioteką. **Odstępstwo:** Lexicon.

### 2. Rejestr i gęstość

Wszystkie 6: tło ciemnoszare/czarne, tekst wielokrotnie mniejszy niż tytuł 40 px w oknie
DanceLab (nagłówki kolumn i podpisy transportu w jednym, drobnym rozmiarze), wiele
modułów nad zgięciem (rekordbox PERFORMANCE: FX ×2, CFX, 2 decki, mikser, transport,
browser — 7+ modułów na jednym ekranie). Białe pole nie istnieje; hierarchia idzie
kolorem i obramowaniem, nie rozmiarem pisma. Rejestr: **gęsty panel instrumentu**.

**Wzorzec:** gęsty, ciemny, instrumentowy. **Najluźniejsze:** MIK i djay — i one też
w tym rejestrze.

### 3. Powierzchnia biblioteki

Tabela wielokolumnowa z **okładką** (6 z 6), **BPM w liście** (6 z 6), **tonacją jako
kolorowym chipem w liście** (Serato, Traktor, Lexicon, MIK — 4 z 6; djay ma chip tylko
w nagłówku decka, rekordbox w nagłówku tekstem), **oceną gwiazdkami** (Serato, Traktor,
Lexicon, MIK — 4 z 6). rekordbox dodaje **kolumnę Preview** — miniaturę fali w każdym
wierszu przed załadowaniem. Lexicon dodaje chipy tagów własnych w wierszu i edytor
zbiorczy („Editing 66 tracks"). MIK dodaje **Energy** i **liczbę cue** jako kolumny.

**Wzorzec:** okładka + BPM + tonacja-chip + ocena w jednym wierszu.

### 4. Nawigacja i szukanie

Drzewo po lewej u 6 z 6: rekordbox (Collection → All/Date Added/Genre/Artist/Album),
djay (ikony źródeł: Music, Spotify, TIDAL, SoundCloud, Beatport…, potem playlisty),
Serato (crates), Traktor (Track Collection, Playlists, Played in this session, Recently
added, Top rated, **Preparation**), Lexicon (Playlists/Genres/Smart lists), MIK
(Playlists / Analysis Queue / Favorite Mashups / My Music → gatunki). Szukajka: małe pole
w nagłówku listy, **wtórna** u wszystkich.

Osobno: Serato **Prepare** i Traktor **Preparation** — nazwany „koszyk na następny set"
u 2 z 6. Nie konwencja, ale najbliższy odpowiednik naszego koszyka filarów.

**Wzorzec:** drzewo główne, szukajka wtórna.

### 5. Rejestr marki

Mieszany — jedyny wymiar, w którym pole się nie zgadza:

* **instrument** — rekordbox, Traktor, Serato: szarości + jeden kolor firmowy,
  mikrokopia techniczna (KEY SYNC, SLIP, CUP, FLX, MEMORY);
* **konsumencki** — djay: kolorowe ikony źródeł, „Start Automix", okładki jak w Apple Music;
* **narzędziowy** — Lexicon (monochrom + zieleń, listy narzędzi „Fix cueing", „Remove
  garbage"), MIK (błękit firmowy, guziki słowne: Change key, Stems, Loop, Export).

**Wzorzec:** brak jednego. Nowa apka musi wybrać **jeden** i trzymać.

### 6. Sygnały zaufania

BPM i tonacja **zawsze** na ekranie (6 z 6). Ocena u 4 z 6. MIK dodaje Energy jako
liczbę. Czego **nie ma nigdzie**: skąd tonacja (pomiar vs Rekordbox vs ręcznie), czy
siatka była poprawiana, czy analiza jest zablokowana (rekordbox ma to w menu
Track → Analysis Lock, nie w liście).

**Wzorzec:** liczby tak, pochodzenie liczb nie.

### 7. Konwencje pola

Apka, która tego nie ma, czyta się jako spoza pola:

* deck (fala + transport + pady) nad biblioteką (5 z 6);
* fala **kolorowana pasmem**: rekordbox dwupasmowa (niebieski/pomarańcz), djay, Serato,
  Traktor, Lexicon wielokolorowe — **5 z 6**; że kolor koduje częstotliwość, czytelne u
  Serato, Traktora i rekordboxa. **Jedyny wyjątek: MIK — jednobarwna**, a to apka
  najbliższa naszej (prep, nie granie);
* **dwa paski fali** (przeglądowy + zbliżony): rekordbox, djay, Serato, Traktor — **4 z 6**;
  Lexicon i MIK mają jeden;
* **8 miejsc na cue widocznych zawsze**: rekordbox lista A–H, djay 2×4, MIK flagi
  Cue 1–8 — 3 z 6 potwierdzone; Serato co najmniej 4 nazwane (Start/Intro/Build/Drop),
  druga linia nieczytelna; Traktor nieczytelny;
* wiersz biblioteki = okładka + BPM + tonacja-chip (4 z 6);
* drzewo playlist po lewej (6 z 6);
* ciemny, gęsty rejestr (6 z 6).

---

## Luki (gdzie nawet liderzy leżą)

* **Pusty start milczy.** 2 z 2 na żywo: „Not Loaded" i dymek o mikserze. Żadnej
  instrukcji. Wpisuje się w pusty start, który okno dostało w 85ffea3.
* **Pochodzenie liczb niewidoczne.** 6 z 6 pokazują tonację, 0 z 6 pokazuje, skąd.
  DanceLab ma to w polu `key_detection_source` — przewaga, jeśli trafi do listy, nie
  tylko do nagłówka.
* **Koszyk na set to sierota.** Prepare/Preparation u 2 z 6, u reszty playlista jak każda
  inna. Nazwany koszyk filarów z licznikiem to wyróżnik, nie brak.
* **Hot cue bez nazwy i bez usuwania w zasięgu wzroku.** rekordbox: lista A–H z „×"
  przy wierszu; djay: „+" bez śladu, jak zdjąć; MIK: flagi bez guzika. Nasz kafel ma
  krzyżyk (8fc9705) — w polu.

Nieoceniane z nieruchomych obrazków: cofanie, zależność od odtwarzacza.

---

## Poprzeczka dla okna DanceLab

Zestawienie z niemym podglądem okna (stan po 85ffea3), bez ocen smaku:

| Konwencja | Okno dziś | Werdykt |
|---|---|---|
| deck nad biblioteką | fala po lewej, lista po prawej, oba widoczne | równoważne — 2 kolumny zamiast 2 rzędów, zadanie główne tak samo pierwsze |
| fala kolorowana pasmem (5 z 6) | **jeden kolor** (bursztyn) + niebieski znacznik | **poza polem** — w towarzystwie tylko MIK |
| dwa paski fali (4 z 6) | jedna fala + zoom; pasek sekcji pod spodem | **poza polem** — po zoomie nie ma widoku całości |
| 8 miejsc na cue zawsze widocznych | 8 kafli A–H | w polu |
| wiersz = okładka + BPM + tonacja-chip | tytuł + BPM + tonacja **tekstem** | **poza polem** w dwóch punktach: brak okładki, tonacja bez koloru |
| drzewo playlist po lewej | chipy filtrów nad listą (wszystko/ulubione/filary/dysk/Apple/brak) | odstępstwo — płaskie zamiast drzewa; dla 400 utworów działa, dla 8 251 (rekordbox Janka) nie sprawdzone |
| ciemny, gęsty rejestr | ciemny, **rzadki** (tytuł 40 px, oddech) | **poza polem** — świadomie, kierunek „Redakcja" |

**Musi**, żeby nie czytało się jako spoza pola, a jednocześnie nie porzucać „Redakcji":

1. **Tonacja jako kolorowy chip Camelot** w liście i w liczbach nad listą — 4 z 6, tani,
   nie zmienia rejestru.
2. **Fala w dwóch pasmach** w istniejących tokenach — bursztyn na niski zakres, cichy na
   wysoki. rekordbox robi dokładnie to dwoma kolorami; paleta zostaje, fala zaczyna mówić
   o dźwięku.
3. **Pasek przeglądowy** po zoomie — mały, pełny utwór nad falą, z ramką aktualnego okna.
   4 z 6; bez tego zoom to zgubienie się.
4. **Okładka w wierszu listy** — jeśli plik ma tag; 6 z 6 ją mają.

**Świadome odstępstwo z nazwaną ceną:** rzadki rejestr. Cena: DJ przyzwyczajony do
kokpitu odbiera oddech jako „mniej programu" — dokładnie tak brzmiała opinia kumpla
(„player z lat 2000"). Zysk: hierarchia bez ramek, czytelność dla obcego. Ta luka nie
domyka się poprawką, tylko decyzją: zostajemy przy oddechu, ale punkty 1–4 dają sygnały,
po których DJ poznaje narzędzie DJ-skie.

**Ruch pozycjonujący:** **pochodzenie liczb** w wierszu (ikona: pomiar / Rekordbox /
ręcznie) — 0 z 6 to robi, a w tym repo dane już są. Drugi: dźwięk tylko z gestu — djay
pokazał, czemu to ma znaczenie.

---

## Nieoceniane

* **Serato, Traktor, Lexicon, MIK w stanie pustym** — producent pokazuje tylko wypełnione.
* **Liczba padów w Traktor** — na jedynym zrzucie nieczytelna.
* **Gęstość między „na żywo" a „producent"** — różne warunki (własna kolekcja vs
  wyreżyserowana).
* **Ruch, animacje, cofanie** — nie z nieruchomych obrazów. Dźwięk: tylko jedno
  zdarzenie (djay gra po załadowaniu).
* **Tryb PERFORMANCE rekordboxa z utworem** — widziany tylko EXPORT z utworem; do okna
  DanceLab właściwy jest EXPORT, więc nie dociągałem.
