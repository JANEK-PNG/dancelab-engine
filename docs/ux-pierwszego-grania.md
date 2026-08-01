# UX pierwszego grania — specyfikacja bez ekranów

**Status:** projekt do akceptacji Janka · 2026-08-01
**Zakres:** cała ścieżka od briefu do zagranego setu. Zero UI — ta specyfikacja
najpierw jedzie na CLI + Rekordboksie (pierwsze testy), a CURVE dostaje ją
później jako mapę do implementacji. UX to kolejność pytań, język odpowiedzi,
stany, i co wolno pokazać — nie kolory.

---

## 0 · Zasady nadrzędne (wynikają z decyzji już podjętych)

1. **Ręka Janka zawsze wygrywa.** Silnik niczego nie blokuje i o nic nie błaga.
   Każda sugestia jest do odrzucenia jednym gestem; każdy element playlisty da
   się zmienić, przypiąć albo wyrzucić. System bez briefu = system filtrów
   (BPM / tonacja / styl / energia) i nic więcej — to jest pełnoprawny tryb,
   nie degradacja.
2. **Domyślne ≠ narzucone.** Każdy plan (tempo, łuk, długość) jest w całości
   widoczny PRZED policzeniem czegokolwiek i odrzucalny na widok. Zasada
   z klatki schodowej: silnik podaje przestrzeń grywalnych planów, kształt
   wybiera DJ.
3. **Uczciwość liczb (ADR-005 przełożony na UX).** Nieznane pokazujemy jako
   nieznane: tonacja z niską pewnością dostaje „?", styl nieznany dostaje
   „stylu nie znam", płyta bez sztywnej siatki dostaje „ta płyta nie trzyma
   stałego tempa" — nigdy pustego pola i nigdy zmyślonej wartości.
4. **Liczby tylko te, które wolno pokazać** (audyt profilu DJ-a): pokazujemy
   BPM, pitch w %, tonację w Camelocie, styl słowem. NIE pokazujemy surowych
   score'ów (0.9302 nic nie mówi) — zamiast nich język DJ-a: „ta sama tonacja",
   „sąsiad na kole", „ostrożnie", „ryzykownie", „suwak ledwo ruszony".
5. **Język pozytywny** (decyzja 07-17): „preferencja/nagroda", nigdy „kara".
   Ton: kumpel pokazujący coś fajnego — nigdy oceniający.
6. **Rekordbox jest wejściem i wyjściem.** Niczego nie każemy robić w naszym
   narzędziu, co DJ woli zrobić u siebie. Oryginalna baza jest nietykalna;
   podmiana zawsze ręką DJ-a.

---

## 1 · Mapa ścieżki

```
BRIEF (≤3 pytania) → PROPOZYCJA (lista + krzywa + dlaczego)
   → PRZEGLĄD (słuchaj / podmień / przypnij / przestaw)
   → EKSPORT (hot cue → KOPIA master.db → recenzja w RB → podmiana ręką)
   → GRANIE → [po secie: co poszło, co wyleciało — wejście do następnego briefu]
```

Każdy krok ma wyjście awaryjne: z briefu można skoczyć od razu do „pokaż
bibliotekę z filtrami", z propozycji do „buduję sam od zera".

---

## 2 · Brief — trzy pytania, reszta to domyślne do obejrzenia

**Zasada: maksymalnie trzy pytania na start** (progressive disclosure — nie
przytłaczać na wejściu). Wszystko inne ma jawne domyślne wartości pokazane
jako plan, nie jako formularz.

| # | Pytanie | Forma odpowiedzi | Skąd silnik bierze resztę |
|---|---|---|---|
| 1 | **Co gramy?** | grupy brzmieniowe DJ-a (jego nazwy z profilu) + style z Discogs jako podpowiedź; wielokrotny wybór | styl nieznany dla części biblioteki → jawny chip „stylu nie znam (46%)" — te utwory NIE wypadają, są oznaczone |
| 2 | **Jak długo?** | 45 min / 1 h / 90 min / własne | liczba utworów z mediany długości slotu |
| 3 | **Tempo?** | „płasko przy X" / „rosnąco od X do Y" / „bez zdania — pokaż, co biblioteka umie" | odpowiedź silnika ZAWSZE zawiera raport wykonalności: „wszystkie naraz grają 126–134; najgęściej przy 127" — zanim DJ wybierze |

**Pytania, których NIE zadajemy na starcie** (dostępne po rozwinięciu):
co z zagranym wcześniej (jedno pokrętło: nie tykaj / rzadziej / bez znaczenia —
intencja, nie mechanizm), przypięte pozycje (pierwszy/ostatni utwór), waga
doświadczenia innych DJ-ów (corpus priors 0–1).

**Stan pusty:** brak profilu / pierwsze uruchomienie → brief działa od razu na
samych filtrach twardych (BPM, tonacja), z komunikatem czego jeszcze nie wie
i co da mu skan („po skanie Rekordboxa będę znał Twoje wejścia i szwy").

---

## 3 · Propozycja — lista, która tłumaczy się sama

**Jeden wiersz = jedna decyzja silnika, wyjaśniona w jednym zdaniu.**

Wiersz zawiera: pozycję · wykonawcę/tytuł · BPM oryginału → tempo w planie
(pitch w %, ostrzeżenie dopiero >4%) · tonację (z „?" przy niskiej pewności) ·
chip stylu (albo „stylu nie znam") · **linijkę „dlaczego tu"** w języku DJ-a:

> „wchodzi na perkusji, bas oddaje późno — jak Ty” · „ta sama tonacja,
> suwak ledwo ruszony” · „ryzykownie harmonicznie, ale 38 DJ-ów z korpusu
> grało to przejście”

**Krzywa jest wynikiem, nie celem** (decyzja z CURVE, obowiązuje wszędzie):
nad listą leży krzywa energii NARYSOWANA z pomiarów wybranych utworów — DJ
patrzy, czy łuk mu się podoba; nie wciska utworów w narysowany kształt.
Druga oś tej samej grafiki: plan tempa (klatka schodowa) z zaznaczeniem,
który utwór ile płaci suwakiem.

**Nagłówek propozycji = paragon uczciwości:** ile utworów z puli odpadło
i dlaczego, po polsku, per utwór — dokładnie jak dziś w logu propose_set
(„poza pulą: 122 BPM, 9% od tempa setu”). Nic nie znika po cichu.

---

## 4 · Przegląd — słuchanie, podmiana, ręka

### 4a · Odsłuch (dwa tryby, oba już istnieją w silniku)

- **Szew po szwie:** klik między dwoma sąsiadami → podgląd przejścia
  (`dancelab preview A B` — silnik sam wybiera okna mix-out/mix-in).
  Odpowiada na pytanie „czy TA para działa".
- **Usiądź i słuchaj:** render całego setu jednym ciągiem (automix) — tryb
  „godzina spokoju". Odpowiada na pytanie „czy CAŁOŚĆ płynie".
  Zawsze plik do odsłuchu u siebie — nigdy autoodtwarzanie.

### 4b · Podmiana („te dwa mi nie siedzą")

Interakcja docelowa, w CLI jako komenda, w CURVE jako panel:

1. DJ zaznacza 1–n utworów jako „nie ten".
2. Silnik pokazuje po **3–5 kandydatów na slot**, każdy z:
   - tym samym wierszem informacyjnym co w propozycji (BPM/pitch/tonacja/styl),
   - **dlaczego ten** (jedno zdanie),
   - **co zmienia u sąsiadów** („przejście z 7. robi się ostrożne zamiast
     tej samej tonacji") — bo podmiana ma skutki po obu stronach slotu.
3. Reszta playlisty jest podczas podmiany ZAMROŻONA (locked) — wymiana jednego
   klocka nie może przetasować całości bez zgody DJ-a.
4. Brak dobrego kandydata to legalna odpowiedź: „w tej tonacji i tempie nie mam
   nic lepszego — najbliższy kompromis to…" (pusty stan z propozycją drogi).

### 4c · Ręka

- Przeciągnij/przestaw dowolnie — silnik po każdym ruchu przelicza i **mówi**,
  co się zmieniło („to przejście jest teraz ryzykowne"), ale NIE cofa i NIE
  blokuje. Werdykt to informacja, nie bramka.
- Przypnij utwór do pozycji (otwarcie/zamknięcie setu) — planner układa resztę
  wokół przypiętych (`locked_positions`/`pinned` już istnieją w silniku).
- „Buduję sam": pusta playlista + biblioteka z filtrami (BPM / Camelot / styl /
  energia / zagrane-niezagrane). Silnik = podpowiadacz następnego utworu na
  życzenie, nie z automatu.

---

## 5 · Eksport — zaufanie przez procedurę

Sekwencja jest częścią UX, bo buduje albo niszczy zaufanie:

1. **Zawsze kopia.** Zapis hot cue idzie do kopii master.db. Komunikat mówi
   wprost: „Twój oryginał nietknięty; pracuję na kopii z {ścieżka}".
2. **Paragon zapisu:** lista co dokładnie zapisano — utwór po utworze, który
   pad, jaki znacznik (MIX IN wg reguły wejścia), w której sekundzie.
3. **Podmiana ręką DJ-a** według krótkiej instrukcji (Rekordbox zamknięty →
   podmień → otwórz). Program NIGDY nie podmienia sam — to decyzja z ledgera
   i zostaje decyzją na zawsze.
4. Po otwarciu w RB: playlist + cue na padach; DJ recenzuje u siebie,
   eksportuje na SWÓJ USB swoim eksportem. Nasza rola się kończy, zanim
   zaczyna się klub.

---

## 6 · Po secie (domknięcie pętli — szkic, do osobnej decyzji)

Nagranie + .cue z wieczoru wraca do silnika (ścieżka pomiaru szwów już
istnieje). Program mówi: co z propozycji poszło, co wyleciało, gdzie DJ wszedł
inaczej niż planowaliśmy — i **to jest wejście do następnego briefu**, nie
ocena występu. Ton: ciekawość, nie rozliczanie.

---

## 7 · Stany brzegowe (każdy ma treść, żaden nie jest pusty)

| Stan | Komunikat (wzór tonu) |
|---|---|
| brak siatki dla utworu | „ta płyta nie trzyma stałego tempa — mogę ją dać, ale beatmatch będzie ręczny" |
| tonacja niepewna | „12A?" + w szczegółach: „pewność niska — traktuj jak podpowiedź" |
| styl nieznany | chip „stylu nie znam" + akcja „nazwij grupę brzmieniową" (zasila profil) |
| pusta pula po filtrach | „przy 140–145 BPM i tej tonacji zostały 3 utwory — poluzować tempo czy tonację?" |
| utwór za krótki na slot | „2,5 min materiału, slot potrzebuje 2,9 — dam radę, jeśli wejdzie później" |
| nic nie gra w zadanym tempie | raport wykonalności zamiast odmowy: „nikt nie dosięga 150; najbliżej jest 138–144" |

---

## 8 · Co mierzy pierwszy test (UX bez metryk to opinia)

- ile propozycji przeżywa przegląd bez podmiany (cel: >60% slotów),
- ile podmian kończy się wyborem z naszych kandydatów vs własnym z biblioteki,
- ile setów zostaje ZAGRANYCH z wyeksportowanych (twarda miara zaufania),
- gdzie DJ wszedł inaczej niż nasz MIX IN (paliwo do reguły wejścia v2).

---

## 9 · Mapowanie na dziś (CLI) i na jutro (CURVE)

| Krok UX | Dziś (test) | Docelowo (CURVE) |
|---|---|---|
| Brief | flagi `propose_set` + raport wykonalności | 3 pytania + plan do obejrzenia |
| Propozycja | log z „dlaczego" po polsku | lista + krzywa-wynik |
| Odsłuch szwu | `dancelab preview A B` | panel porównania (już zbudowany) |
| Cały set | render automix → FLAC | przycisk „posłuchaj całości" |
| Podmiana | komenda swap z kandydatami | panel z lewej, reszta zamrożona |
| Eksport | cue-write na kopię (ścieżka sprawdzona E2E) | ten sam mechanizm, jeden przycisk |
