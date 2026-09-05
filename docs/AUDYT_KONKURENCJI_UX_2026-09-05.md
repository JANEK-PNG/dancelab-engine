# Audyt doświadczenia konkurencji: aplikacje do przygotowania setu DJ-skiego

**Kształt produktu:** narzędzie desktopowe do prepu (fala + hot cue + biblioteka) — żaden z kształtów
stron www ze skillu nie pasuje, więc nie naginam.
**Data:** 2026-09-05
**Pole:** 6 aplikacji · **na żywo:** 2 · **zrzuty producenta:** 3 · **nic:** 1
**Stan audytu:** `partial` — pełne pole nie zostało wyrenderowane, patrz „Nieoceniane”.

Plik leży w `docs/` po polsku (konwencja repo), nie w korzeniu jako
`experience-audit-*.md`, jak każe skill. Zrzutów nie wkładam do repo: pokazują
prawdziwą kolekcję i nazwy playlist.

---

## Pole

| Aplikacja | Jak obejrzana | Co realnie widać |
|---|---|---|
| rekordbox 7 | **na żywo**, tryb PERFORMANCE, decki puste | siatka 8 padów A–H, loop, browser z kolumną Preview (miniatury fal), szukajka. **Tryb EXPORT — właściwy tryb prepu — nieobejrzany** (przełącznik to popup, którego nie da się kliknąć w tle przy zablokowanym ekranie). Załadowana fala: nieoceniana. |
| djay Pro | **na żywo**, decki puste | siatka 2×4 „+” na deck, LOOP/FX, karty biblioteki, panel Automix. Fala: nieoceniana. |
| Serato DJ Pro | zrzuty producenta (widok domyślny + Prepare) | wszystko poniżej — ale to stan wyreżyserowany, nie pusty |
| Traktor Pro 4 | jeden zrzut producenta | 4 decki, browser; liczba padów nieczytelna → nieoceniana |
| Lexicon | zrzuty producenta (demo3 = ekran utworu, demo5 = narzędzie Smart Fix) | fala przeglądowa, siatka biblioteki, edytor zbiorczy |
| Mixed In Key Pro | **nic** — strona nie wyrenderowała się w panelu | każdy wymiar `nieoceniany` |

Asymetria, którą trzeba nazwać: aplikacje na żywo pokazały **stany puste**, zrzuty
producenta pokazują **stany wypełnione i wyreżyserowane**. Porównanie gęstości przez tę
granicę nie jest oceniane. Porównanie stanu pustego istnieje tylko dla dwóch apek.
Reguła „3 z N” liczy się przy **N = 5**.

## Tłumaczenie wymiarów

Skill jest napisany pod sklepy. Dla tego pola:

| Wymiar ze skillu | Tutaj znaczy |
|---|---|
| zadanie główne | załadować utwór → zobaczyć falę z cue |
| powierzchnia towaru | ile biblioteki widać naraz i w jakim kształcie |
| nawigacja / szukanie | drzewo playlist vs pole szukania |
| sygnały zaufania | skąd wiadomo, że BPM, tonacja i siatka są pewne (źródło, blokada analizy, ocena) |

---

## Podsumowanie

| Wymiar | Wynik | Wzorzec jednym zdaniem |
|---|---|---|
| 1. Zadanie główne | wzorzec | deck (fala + transport + pady) na górze, biblioteka na dole; **4 z 5** |
| 2. Rejestr i gęstość | wzorzec | ciemnoszary „panel instrumentu”, tekst 9–11 px, zero pustki; 5 z 5 |
| 3. Powierzchnia biblioteki | wzorzec | tabela z okładką, BPM, tonacją jako kolorowym chipem, oceną; **4 z 5** |
| 4. Nawigacja i szukanie | wzorzec | drzewo źródeł/playlist po lewej + szukajka wtórna; 5 z 5 |
| 5. Rejestr marki | mieszany | instrument (rekordbox, Traktor, Serato) vs konsumencki (djay) vs narzędziowy (Lexicon) |
| 6. Sygnały zaufania | wzorzec | tonacja i BPM zawsze widoczne w liście; źródło analizy **nie** |
| 7. Konwencje pola | patrz niżej | |

---

## Wzorce w polu

### 1. Zadanie główne

Największy i najwcześniejszy element interaktywny: **deck** — fala, platter, transport,
siatka padów. Biblioteka zawsze pod spodem (rekordbox, djay, Serato, Traktor; 4 z 5).
Lexicon odwraca: jedna fala przeglądowa na całą szerokość u góry, reszta ekranu to
biblioteka — bo Lexicon jest narzędziem do biblioteki, nie do grania.

Droga do zadania: w obu apkach na żywo puste decki mówią „Not Loaded” / „No Playlist
Selected” **bez jednego zdania, co zrobić**; djay dodatkowo otwiera dymek o zewnętrznym
mikserze, niezwiązany z pierwszym krokiem. To obserwacja **2 z 2 wyrenderowanych**, nie
konwencja — ale tylko taka jest dostępna.

**Wzorzec:** deck nad biblioteką. **Odstępstwo:** Lexicon (fala przeglądowa zamiast decka).

### 2. Rejestr i gęstość

Wszystkie 5: tło ciemnoszare/czarne, tekst wielokrotnie mniejszy niż tytuł 40 px w oknie
DanceLab (nagłówki kolumn i podpisy transportu w jednym, drobnym rozmiarze), wiele modułów nad zgięciem
(rekordbox na żywo: FX ×2, CFX, 2 decki, mikser, transport, browser — 7+ modułów na
jednym ekranie). Białe pole nie istnieje; hierarchia idzie kolorem i obramowaniem, nie
rozmiarem pisma. Rejestr: **gęsty panel instrumentu**, bliżej kokpitu niż redakcji.

**Wzorzec:** gęsty, ciemny, instrumentowy. **Odstępstwo:** brak. djay jest najmniej gęsty,
ale nadal w tym rejestrze.

### 3. Powierzchnia biblioteki

Tabela wielokolumnowa z **okładką** (rekordbox kolumna Artwork, djay, Serato, Traktor,
Lexicon — 5 z 5), **BPM i tonacją w liście** (5 z 5), **tonacją jako kolorowym chipem
Camelot** (Serato, Traktor, Lexicon — 3 z 5; rekordbox na żywo miał kolumnę poza
kadrem → nieoceniane; djay nieoceniane), **oceną gwiazdkami** (Serato, Traktor,
Lexicon — 3 z 5). rekordbox dodaje **kolumnę Preview** — miniaturę fali w każdym
wierszu, jeszcze przed załadowaniem. Lexicon dodaje chipy tagów własnych w wierszu
(„Techno · Drop Deep · No Vocals”) i edytor zbiorczy („Editing 66 tracks”).

**Wzorzec:** okładka + BPM + tonacja-chip + ocena w jednym wierszu. **Odstępstwo:**
rekordbox z falą w wierszu; Lexicon z tagami w wierszu.

### 4. Nawigacja i szukanie

Drzewo po lewej: rekordbox (Collection → All/Date Added/Genre/Artist/Album), djay
(ikony źródeł: Music, Spotify, TIDAL, SoundCloud, Beatport…, potem playlisty), Serato
(crates), Traktor (Track Collection, Playlists, Played in this session, Recently added,
Top rated, **Preparation**), Lexicon (Playlists/Genres/Smart lists). 5 z 5 — drzewo
jest drogą główną. Szukajka: małe pole w nagłówku listy, **wtórna** we wszystkich pięciu.

Osobno: Serato ma widok **Prepare** i Traktor playlistę **Preparation** — „koszyk na
następny set” to nazwana konwencja u 2 z 5. Nie 3, więc nie konwencja, ale najbliższy
odpowiednik naszego koszyka filarów.

**Wzorzec:** drzewo główne, szukajka wtórna.

### 5. Rejestr marki

Mieszany, i to jest jedyny wymiar, w którym pole się nie zgadza:

* **instrument** — rekordbox, Traktor, Serato: szarości + jeden kolor firmowy (niebieski
  / pomarańcz / niebieski), czcionka systemowa/geometryczna, mikrokopia techniczna
  (KEY SYNC, SLIP, CUP, FLX);
* **konsumencki** — djay: kolorowe ikony źródeł, „Start Automix”, Apple-owe karty;
* **narzędziowy** — Lexicon: monochrom + zielony akcent, dużo tekstu, listy narzędzi
  („Fix cueing”, „Remove garbage”).

**Wzorzec:** brak jednego. Nowa apka może wybrać, ale musi wybrać **jeden** i trzymać.

### 6. Sygnały zaufania

BPM i tonacja **zawsze** w liście (5 z 5) — to jest „cena widoczna bez klikania”.
Ocena gwiazdkowa u 3 z 5. Czego **nie ma nigdzie** w widocznym kadrze: skąd tonacja
(pomiar vs Rekordbox vs ręcznie), czy siatka była poprawiana ręcznie, czy analiza jest
zablokowana (rekordbox ma to w menu Track → Analysis Lock, ale nie w liście).

**Wzorzec:** liczby tak, pochodzenie liczb nie.

### 7. Konwencje pola

Apka, która tego nie ma, czyta się jako spoza pola:

* deck (fala + transport + pady) nad biblioteką;
* fala **wielokolorowa** — Serato, Traktor, Lexicon (3 z 5; rekordbox i djay nieoceniane,
  decki puste). Że kolor koduje pasmo częstotliwości, czytelne u Serato i Traktora;
  u Lexicona nieczytelne;
* **dwa paski fali** (przeglądowy + zbliżony): Serato i Traktor — **2 z 5, więc nie
  konwencja**; Lexicon ma jeden pasek przeglądowy na całą szerokość;
* siatka **padów** widoczna zawsze, nie po kliknięciu: 8 potwierdzone u 2 z 5 (rekordbox
  A–H, djay 2×4); Serato — co najmniej 4 nazwane (Start/Intro/Build/Drop), druga linia
  nieczytelna; Traktor nieczytelny. **Widoczność tak, liczba 8 — nie dowiedziona jako
  konwencja**;
* wiersz biblioteki = okładka + BPM + tonacja-chip;
* drzewo playlist po lewej;
* ciemny, gęsty rejestr.

---

## Luki (gdzie nawet liderzy leżą)

* **Pusty start milczy.** 2 z 2 na żywo: „Not Loaded” i dymek o mikserze. Żadnej
  instrukcji. To jest jedyna luka poparta obserwacją; wpisuje się w pusty start, który
  okno dostało w 85ffea3.
* **Pochodzenie liczb niewidoczne.** 5 z 5 pokazują tonację, 0 z 5 pokazuje, skąd.
  DanceLab już to ma w tytule utworu („Rekordbox zamknięty, zapis dostępny”) i w polu
  `key_detection_source` — to realna przewaga, jeśli zostanie w liście, nie tylko w nagłówku.
* **Koszyk na set to sierota.** Prepare/Preparation u 2 z 5, u reszty playlista jak
  każda inna. Nazwany koszyk filarów z licznikiem to wyróżnik, nie brak.

Nieoceniane z nieruchomych obrazków: cofanie, usuwanie cue, zależność od odtwarzacza.

---

## Poprzeczka dla okna DanceLab

Zestawiam z niemym podglądem okna (stan po 85ffea3), bez ocen smaku — tylko wzorzec
vs obecność:

| Konwencja | Okno dziś | Werdykt |
|---|---|---|
| deck nad biblioteką | fala po lewej, lista po prawej, oba widoczne | równoważne — układ 2-kolumnowy zamiast 2-rzędowego, zadanie główne tak samo pierwsze |
| fala wielopasmowa | **jeden kolor** (bursztyn) + niebieski znacznik | **poza polem** |
| pasek przeglądowy + zbliżony (2 z 5 — obserwacja, nie konwencja) | jedna fala + zoom; pasek sekcji pod spodem | po zoomie nie ma widoku całości — problem orientacji zobaczony w naszym oknie, nie wymóg pola |
| 8 padów zawsze widocznych | 8 kafli A–H | w polu |
| wiersz = okładka + BPM + tonacja-chip | tytuł + BPM + tonacja **tekstem** | **poza polem** w dwóch punktach: brak okładki, tonacja bez koloru |
| drzewo playlist po lewej | chipy filtrów nad listą (wszystko/ulubione/filary/dysk/Apple/brak) | odstępstwo — płaskie zamiast drzewa; dla 400 utworów działa, dla 8 251 (rekordbox Janka) nie sprawdzone |
| ciemny, gęsty rejestr | ciemny, **rzadki** (tytuł 40 px, oddech) | **poza polem** — świadomie, kierunek „Redakcja” |

**Musi**, żeby nie czytało się jako spoza pola, a jednocześnie nie porzucać „Redakcji”:

1. **Tonacja jako kolorowy chip Camelot** w liście i w liczbach nad listą — 3 z 5,
   tani, nie zmienia rejestru.
2. **Fala w dwóch pasmach** (bas / reszta) w istniejących tokenach — bursztyn na
   niski zakres, cichy na wysoki. Zostaje jednobarwna paleta, ale fala mówi coś o
   dźwięku.
3. **Pasek przeglądowy** po zoomie — mały, pełny utwór nad falą, z ramką aktualnego
   okna. Uzasadnienie z własnego okna (po zoomie nie widać, gdzie się jest), nie
   z pola — tam to tylko 2 z 5.
4. **Okładka w wierszu listy** — jeśli plik ma tag; 5 z 5 ją mają.

**Świadome odstępstwo z nazwaną ceną:** rzadki rejestr. Cena: DJ przyzwyczajony do
kokpitu odbiera oddech jako „mniej programu” — dokładnie tak brzmiała opinia kumpla
(„player z lat 2000”). Zysk: hierarchia bez ramek, czytelność dla obcego. Ta luka nie
domyka się poprawką, tylko decyzją: zostajemy przy oddechu, ale punkty 1–4 dają
sygnały, po których DJ poznaje narzędzie DJ-skie.

**Ruch pozycjonujący:** pokazać **pochodzenie liczb** w wierszu (ikona: pomiar /
Rekordbox / ręcznie) — 0 z 5 to robi, a w tym repo dane już są.

---

## Nieoceniane

* **Mixed In Key Pro — wszystko.** Strona producenta nie wyrenderowała się w panelu
  (białe tło). Potrzebny zrzut z uruchomionej apki albo instrukcji.
* **rekordbox EXPORT** — tryb prepu nieobejrzany; PERFORMANCE nie jest odpowiednikiem
  okna DanceLab. Potrzebne: odblokowany ekran, przełączenie trybu, wybór utworu.
* **Fala załadowana w rekordbox i djay** — decki puste, załadowanie w tle nie działa
  (drag i dwuklik bez efektu; djay nie wystawia drzewa dostępności).
* **Liczba padów w Traktor** — na jedynym zrzucie nieczytelna.
* **Gęstość porównana między „na żywo” a „producent”** — stany puste vs wyreżyserowane.
* **Ruch, animacje, dźwięk, cofanie, usuwanie cue** — nie z nieruchomych obrazów.

---
