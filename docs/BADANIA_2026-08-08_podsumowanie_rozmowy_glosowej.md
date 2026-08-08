# DanceLab — pełne podsumowanie rozmowy

Sesja z 8 sierpnia 2026. Temat: budowa autorskiego silnika rekomendacji i analizy setów DJ-skich.

---

## SPIS TREŚCI

**CZĘŚĆ A — Fundamenty: skąd brać dane i jak je analizować**
1. Kontekst projektu i warunki brzegowe
2. API muzyczne — Apple Music vs Spotify
3. Essentia i sprawa licencji
4. Detekcja tonacji — pipeline od zera
5. Stan badań 2026 — od szablonów do self-supervised
6. Porównanie metod detekcji tonacji (tabela)

**CZĘŚĆ B — Rekomendacja: co robią inni, co robisz Ty**
7. Systemy rekomendacji na platformach streamingowych
8. Twoja teza autorska — triplety i „track pomiędzy"
9. Beatport jako punkt odniesienia
10. Metodologia walidacji tezy

**CZĘŚĆ C — Dane w praktyce**
11. Źródła danych — iTunes previews, Beatport, beets
12. Zbiór mir-aidj i jego ograniczenia gatunkowe
13. Twój własny generator datasetu (Apple Music → Claude Code → iTunes)
14. Timestampy, dwell time i granica tego, co da się wyciągnąć

**CZĘŚĆ D — Energia i łuk setu**
15. Ekstrakcja energii — cztery cechy
16. Normalizacja i wagi
17. Pełny pipeline energii

**CZĘŚĆ E — Wielka ambicja: rekonstrukcja performance'u**
18. Cel — mapowanie każdego ruchu na CDJ
19. Co da się dziś, a co jest jeszcze badaniami
20. Machine learning na wideo — tracking rąk
21. Fuzja wideo + audio (architektura „gdzie" + „ile")
22. Separacja stemów i metoda różnicy (Demucs)

**CZĘŚĆ F — Podsumowania**
23. Glosariusz — wszystkie nazwy, biblioteki, papery, zbiory danych
24. Frazy do wyszukania
25. Otwarte pytania i następne kroki

---

# CZĘŚĆ A — FUNDAMENTY

## 1. Kontekst projektu i warunki brzegowe

**DanceLab** — narzędzie dla DJ-ów (nazwa myląca, nie chodzi o tancerzy). Warunki: licencja Codex, zero budżetu, budowa od zera. To determinuje większość decyzji poniżej — wszędzie tam, gdzie jest wybór „zapłać albo zbuduj", wybór padał na zbuduj.

Stan wyjściowy, który już masz:
- tysiące ściągniętych miksów DJ-skich
- wyciągnięte track ID
- „profile ID" DJ-ów (kto co gra)
- generowanie playlist w stylu konkretnego DJ-a
- score przewidywalnościi/mixability per DJ (Ben UFO ≈ 0.6 = odważny, bezpieczni DJ-e ≈ 0.9)

## 2. API muzyczne — Apple Music vs Spotify

**Apple Music API / MusicKit** daje: wyszukiwanie katalogu, metadane utworu i albumu, dostęp do biblioteki i playlist, tworzenie playlist, rekomendacje, 30-sekundowe preview, okładki. Pola metadanych: tytuł, artysta, album, gatunek, data wydania, długość, **kody ISRC**, artwork. Kluczowe dla DJ-a: **tempo (BPM), tonacja, metrum**.

Rekomendacje Apple są zaszyte w ich ekosystemie (historia słuchania, biblioteka użytkownika) — nie da się ich puścić na dowolne pliki lokalne.

**Spotify** — API `audio-features` / `audio-analysis` zostało **wycofane (~2024)** dla nowych aplikacji. Zniknęły danceability, energy, valence itd. Efekt: Apple stało się pewniejszym źródłem BPM/tonacji/metrum, ale bez bogatych pól nastroju i energii. Stąd konieczność własnej analizy.

Obie platformy: **brak pobierania pełnych utworów** (DRM). Tylko metadane + 30-sekundowe preview.

## 3. Essentia i sprawa licencji

**Essentia** (GitHub: `MTG/essentia`, wersja JS: `MTG/essentia.js` przez WebAssembly) — biblioteka analizy audio z **MTG (Music Technology Group, Universitat Pompeu Fabra, Barcelona)**. To ten sam warsztat, na którym opierały się wycofane funkcje Spotify.

Jak działa: dekoduje audio → dzieli na ramki → FFT → agreguje do poziomu utworu. BPM przez detekcję onsetów + autokorelację. Tonacja przez chromagram + dopasowanie profili tonalnych. Wrapper `MusicExtractor` odpala cały pakiet naraz. Ma profile tonalne dostrojone pod muzykę elektroniczną, lepsze niż generyczne klasyczne — istotne przy Twoim problemie ze słabą detekcją tonacji.

Uzupełnienie: **Gaia** (`MTG/gaia`) — biblioteka C++ z bindingami Pythona do indeksowania i wyszukiwania podobieństwa, te same warunki licencyjne. Essentia ma też wrapper do inferencji modeli TensorFlow.

**Licencja: AGPLv3** — silne copyleft, blokuje zamknięte zastosowanie komercyjne. Licencja komercyjna dostępna od MTG, ale cena nieopublikowana („contact us"), negocjowana, kierowana do firm.

Tańsza alternatywa zauważona po drodze: `mtg/essentia-bpm` hostowany na **Replicate** (~$0.00036 za wywołanie).

**Decyzja:** budujesz własną detekcję tonacji i BPM. Ustalenie prawne: wolno studiować architekturę i algorytmy Essentii (algorytmy nie podlegają prawu autorskiemu), **nie wolno** kopiować ani tłumaczyć linijka po linijce ich kodu źródłowego. Krumhansl-Schmuckler, chromagram, autokorelacja to opublikowane metody akademickie — reimplementacja jest w pełni legalna.

## 4. Detekcja tonacji — pipeline od zera

Sześć kroków:

1. **Wczytanie i downsampling** audio
2. **Podział na ramki** ~0,5 s, nakładające się, z funkcją okna
3. **FFT** na każdej ramce
4. **Budowa chromagramu** — złożenie energii do 12 koszyków klas wysokości dźwięku
5. **Uśrednienie chromy** przez cały utwór
6. **Dopasowanie do 24 szablonów** (12 dur + 12 moll), najwyższa korelacja = tonacja

**Jakość chromagramu to krok, który decyduje o wszystkim:**
- wykrywaj rzeczywisty strój, nie zakładaj 440 Hz
- używaj **transformaty stałego Q (constant-Q)** — skala logarytmiczna, jeden bin na półton — zamiast zwykłego FFT; to największy pojedynczy skok jakości
- waż rejestr średni, ścinaj sub-bas
- modeluj i odejmuj przeciek harmoniczny

**Dopasowanie szablonów:**
- bazą są profile **Krumhansla-Schmucklera**; wystarczy jeden dur i jeden moll, resztę uzyskasz rotacją po 12 klasach
- używaj **korelacji**, nie surowego mnożenia
- rozważ profile wyprowadzone z muzyki elektronicznej zamiast klasycznych Krumhansla

Pokrewne pojęcie: **HPCP** (Harmonic Pitch Class Profile).

## 5. Stan badań 2026 — od szablonów do self-supervised

Pole przesuwa się z dopasowania szablonów w stronę uczenia samonadzorowanego.

**S-KEY** (Deezer, GitHub `deezer/s-key`, arXiv) — samonadzorowany model uczony na ~1 mln utworów, rozróżnia tonacje równoległe (C-dur vs a-moll), ~80% w punktacji typu MIREX, dorównuje nadzorowanemu state of the art. Rozszerza architekturę i cel uczenia modelu **STONE**, dokładając zadanie pomocnicze oparte na cechach chroma niezmienniczych względem transpozycji jako pseudo-etykietach. Dorównuje SOTA na zbiorach **FMAKv2** i **GTZAN** bez żadnych ludzkich adnotacji.

**Punkt odniesienia — dopasowanie szablonów (Krumhansl):** ~87 punktów na czystych zbiorach, ale **spadek do ok. 40** na **GiantSteps** (muzyka taneczna elektroniczna). To dokładnie Twój katalog — czyli wybór profilu/modelu waży więcej niż abstrakcyjny spór „szablony vs sieci".

**LLark** — multimodalny model muzyczny; zadania: globalna estymacja tonacji (punktacja MIREX na GiantSteps Key), estymacja tempa (Acc2 ±4% oktawy, GiantSteps Tempo), klasyfikacja gatunku (GTZAN, MedleyDB), identyfikacja instrumentów (MedleyDB, MusicNet). Osiąga wyniki bliskie SOTA dla tonacji, tempa i instrumentów. Testy zero-shot na **MusicCaps**, **MusicNet**, **FMA**. Jakość spada o 30–50 punktów przy podmianie enkodera **Jukebox** na **CLAP** albo **Llamy 2** na **MPT-1B**.

Metryka warta znajomości: **KSEA** (Key Signature Estimation Accuracy) — pełny punkt za trafienie, pół punktu za pomyłkę o kwintę czystą w górę lub w dół (zaimplementowana w `mir_eval`).

Zbiory danych przewijające się w literaturze: **Million Song Dataset**, **FMA** (Defferrard i in., 2016), **GTZAN**, **MedleyDB**, **MusicNet**, **MusicCaps**, **GiantSteps**, **FMAKv2**.

## 6. Porównanie metod detekcji tonacji

*(Tabela do rozbudowy — kolumny ustalone w rozmowie: nazwa, typ, dokładność MIREX, wynik na muzyce elektronicznej (GiantSteps), licencja, czy wymaga danych treningowych, koszt obliczeniowy.)*

| Metoda | Typ | MIREX | GiantSteps | Licencja | Trening | Koszt |
|---|---|---|---|---|---|---|
| Krumhansl (szablony) | szablon | ~87 | ~40 | brak ograniczeń | nie | znikomy |
| Essentia key extractor | biblioteka | wysoka | dobra (profile EDM) | AGPLv3 | nie | niski |
| librosa chroma | biblioteka | niższa | słabsza | ISC/BSD | nie | niski |
| S-KEY | neuronowy, self-supervised | ~80 | najlepsza | otwarta (repo Deezer) | tak (pretrenowany) | wysoki |
| Vision transformer (czasopismo *Information*) | neuronowy | wysoka | ? | zależnie | tak | wysoki |

**Wniosek praktyczny:** `librosa` = tani prototyp, Krumhansl = wytłumaczalny, S-KEY = najlepsza dokładność, ale ciężki setup.

---

# CZĘŚĆ B — REKOMENDACJA

## 7. Systemy rekomendacji na platformach

Żadna platforma nie publikuje pełnego algorytmu.

- **Spotify** — najbardziej rozbudowany: filtrowanie kolaboratywne + CNN na surowym audio (rozwiązanie problemu zimnego startu) + NLP zbierające playlisty i blogi. To napędza Discover Weekly.
- **Apple** — kuracja redakcyjna przez ludzi + historia słuchania + metadane (gatunek, nastrój, tempo, tonacja).
- **Tidal / Amazon** — najsłabiej udokumentowane, filtrowanie kolaboratywne + treściowe; Amazon przenosi DNA rekomendacji zakupowych.

Tylko Spotify i Apple dają realny dostęp deweloperski do rekomendacji.

**Zimny start** — przełomowy artykuł *Deep Content-Based Music Recommendation* (NeurIPS): trenujesz sieć, żeby przewidywała profil rekomendacyjny utworu **z samego audio**, dzięki czemu zupełnie nowe i nieznane tracki (zero odtworzeń) dają się rekomendować. Bardzo istotne dla DJ-ów polujących na świeżynki i underground.

Dalsza lektura: przegląd *Content-Driven Music Recommendation* (omawia 55 prac), *T-RECSYS: A Novel Music Recommendation System Using Deep Learning*.

## 8. Twoja teza autorska — triplety i „track pomiędzy"

**Sedno:** transakcje modelujesz nie jako pary (A→B), tylko jako **triplety**. Track B jest definiowany przez to, jak **mostkuje** A i C. Środkowy utwór to najważniejsza jednostka — jest „pytaniem", tkanką łączną między dwoma stałymi punktami, patrzącą do przodu (planującą, dokąd set zmierza), a nie tylko odpowiedzią na „co po A".

To przesuwa się jako **okno**: A-B-C ocenia B, potem B-C-D ocenia C, potem C-D-E ocenia D. Tylko pierwszy i ostatni utwór nie mają pełnego trójstronnego kontekstu.

**Walidacja wobec literatury.** Instynkt ma poparcie w badaniach, ale zostawia miejsce na Twój kąt:

- *Temporal Considerations in DJ Mix Information Retrieval* (2025) — najbliższy krewny; dowodzi, że generyczne rekomendery sekwencyjne zawodzą przy DJ-ingu, bo liczy się kontekst na poziomie przejścia.
- Prace o modelowaniu sekwencji odtworzeń **ukrytymi modelami Markowa (HMM)**.
- **DJ-MC: A Reinforcement-Learning Agent for Music Playlist Recommendation** — agent RL nagradzany osobno za utwór i osobno za przejście.
- *A Computational Analysis of Real-World DJ Mixes using Mix-To-Track Subsequence Alignment* (Taejun Kim i in.) — 1557 miksów, 13 728 utworów, 20 765 przejść z 1001Tracklists.

**Ale:** większość pola nadal kręci się wokół **par/przejść** albo łańcuchów patrzących wstecz. Twoje ujęcie — trigramowe, patrzące w przód, „środkowy track jako most" — **nie jest podejściem dominującym**. To realnie żyzny, nieobrobiony grunt.

## 9. Beatport jako punkt odniesienia

Rekomender Beatportu opiera się na zakupach, dodaniach do playlist, danych z koszyka oraz **DJ Charts** od kuratorów i społeczności. Uczy się, „które tracki pasują do siebie" — czyli **wyłącznie współwystępowania/grupowania**. **Nie modeluje sekwencji ani kolejności.**

Trzy poziomy, na których stoisz wyżej:
1. Beatport = współwystępowanie
2. Ty = kierunkowy sygnał z realnych przejść
3. Ty = modelowanie „pomiędzy" / przepływu

Jednozdaniowe pozycjonowanie: **„Beatport rekomenduje tracki, DanceLab układa sety."**

## 10. Metodologia walidacji tezy

**Plan testowy:** trzymasz z boku realne miksy DJ-skie. Pokazujesz modelowi track A i C, ukrywasz prawdziwy B, każesz wypełnić lukę, mierzysz trafialność względem faktycznego wyboru DJ-a na tysiącach odłożonych miksów. Potem **wyścig z modelem parowym** (widzącym tylko A) — jeśli triplet częściej trafia w prawdziwy środek, teza udowodniona (i publikowalna).

**Punktacja częściowa:** dokładne trafienie w utwór jest rzadkie, więc przyznajesz punkty cząstkowe — ta sama tonacja + kilka BPM różnicy + podobna energia = „muzycznie wymienne" = większość punktu. Ta sama filozofia, co połówkowa punktacja w MIREX. Korzysta z cech, które już wyciągasz.

**Kolejność:** najpierw **Opcja 1** — izolowane triplety A-B-C, czysta dokładność jak w testach jednostkowych. Dopiero potem **Opcja 2** — uzupełnianie co drugiego tracka w pełnych miksach, gdzie grozi propagacja i kumulacja błędów. Testy jednostkowe przed integracyjnymi.

**Generowanie:** ziarno → mocny drugi utwór → dalej każdy kolejny wybierany jako najlepszy „środek" dla bieżącego okna. Sterowanie pokrętłem przewidywalności (bezpiecznie = środki o wysokiej pewności, tryb Ben UFO = ryzykowniejsze skoki). Kierunkowość ma znaczenie — to graf skierowany, A→B ≠ B→A, energia w secie narasta.

---

# CZĘŚĆ C — DANE W PRAKTYCE

## 11. Źródła danych — iTunes previews, Beatport, beets

**30-sekundowe preview z iTunes** — możesz ściągać ~100 naraz, 10 tysięcy w kilka minut. **Wystarczą** do tonacji i BPM (obie stabilne w obrębie utworu). Zastrzeżenie: preview bierze **środek** utworu, więc mija intro i outro, czyli faktyczne punkty miksowania. Nadaje się do odcisku palca utworu, nie do analizy samych momentów przejścia — do tych używaj własnych, legalnie posiadanych plików.

**Beatport v4 REST API** (`api.beatport.com`, OAuth2) — zbudowane pod elektronikę, podaje BPM + tonację **już w notacji Camelot** + gatunek, podgatunek, wytwórnie, charty. Dla ich katalogu pomija analizę w całości. **Ale** oficjalny dostęp jest zamknięty: aplikacja i akceptacja przez Partner Portal (tylko zatwierdzeni partnerzy/firmy), brak publicznego klucza samoobsługowego, cena nieopublikowana. **Ścianą nie są pieniądze, tylko akceptacja** — najpewniej nie ma płatnego progu dla indie.

**Praktyczne obejście do użytku prywatnego:** strona Beatportu chodzi na tym samym API v4, więc open-source'owy **beets** (menedżer biblioteki muzycznej, B-E-E-T-S) z pluginem **beets-beatport4** loguje się **zwykłym kontem kupującego** (login/hasło) i ściąga BPM, tonację w Camelot i gatunek — bez zatwierdzenia partnerskiego. Potwierdziłeś użytek prywatny, więc jest to w porządku (do wysyłki komercyjnej potrzebna byłaby zgoda Beatportu).

**Otwarte pytanie:** czy wystarczy **darmowe** konto Beatport, czy potrzeba płatnej subskrypcji (streaming/LINK). Źródła tego nie potwierdziły. Przeczucie: darmowe powinno wystarczyć, bo metadane są publicznie widoczne na stronie — ale zweryfikuj w dokumentacji beets. (Jest też issue w repo `beetbox/beets` o pobieraniu tonacji, BPM i gatunku z Beatportu.)

Wspomniane po drodze, do sprawdzenia z rezerwą: **Tunebat** (spec API przez Parse.bot; nie zawiera pozycji chartowych ani liczby streamów), oraz różne komercyjne agregatory metadanych pojawiające się w wynikach wyszukiwania — traktuj jako reklamę, nie rekomendację.

**Strategia dwupoziomowa:**
- **Poziom 1:** Beatport przez beets → czysta tonacja Camelot i BPM dla katalogu elektronicznego (pokrywa większość materiału DJ-skiego)
- **Poziom 2:** własny pipeline chromagramowy na luki (stare tracki, edity, bootlegi, niszowe) z preview albo własnych plików

**Optymalizacja wydajności:** analizuj całą bibliotekę wsadowo z wyprzedzeniem i zapisz BPM oraz tonację dla każdego utworu. Podczas grania DanceLab czyta gotowe wartości natychmiast, bez opóźnienia analizy. Ciężka robota raz, z góry.

## 12. Zbiór mir-aidj i jego ograniczenia gatunkowe

Grupa badawcza **mir-aidj** udostępnia:
- **djmix-dataset** (`mir-aidj/djmix-dataset`) — pakiet Pythona `djmix`, instalujesz i ściągasz miksy razem z oryginalnymi utworami w nich zagranymi (`dj.download()`, `dj.mixes[1234].download()`, `dj.tracks['ID'].download()`; domyślnie katalog `~/djmix`, konfiguracja w `~/djmix.ini`; wymaga numpy i cython pod madmom)
- **djmix-analysis** (`mir-aidj/djmix-analysis`) — kod do *A Computational Analysis of Real-World DJ Mixes using Mix-To-Track Subsequence Alignment*, ISMIR 2020, Taejun Kim, Minsuk Choi, Evan Sacks, Yi-Hsuan Yang, Juhan Nam
- **transition-analysis** (`mir-aidj/transition-analysis`) — kod do *Reverse-Engineering The Transition Regions of Real-World DJ Mixes using Sub-band Analysis with Convex Optimization*, NIME 2021

Metoda: **wyrównanie podsekwencji miks-do-utworu przez DTW** (dynamic time warping), z wariantem niezmienniczym na transpozycję. Odzyskują **cue pointy**, zmiany tempa, transpozycję tonacji, długości przejść i zgodność cue pointów między DJ-ami. Ich statystyczne wnioski: DJ-e raczej nie zmieniają mocno tempa ani tonacji, żeby nie zniekształcić istoty utworu, i robią bezszwowe przejścia.

Pokrewne: **UnmixDB** (`Ircam-RnD/unmixdb-creation`, Schwarz i Fourer, ISMIR 2018) — zbiór z utworów na licencji Creative Commons, oparty na kolekcji mixotic, z automatycznie generowanymi miksami; oraz *Methods and Datasets for DJ-Mix Reverse Engineering*.

**Twój zarzut, w pełni słuszny:** zbiór jest głównie **house i trance**, świat mainstreamowego czwórkowego bitu. Brak **UK bass, jungle, garage, drum and bass, acid**. Model trenowany tylko na tym uczy się logiki tych gatunków i ślepnie wszędzie indziej — bo breakbeat, halftime, inne frazowanie i inne łuki energetyczne rządzą się innymi prawami. Model dostrojony do trance'u realnie źle oceni set jungle'owy.

**Rozgraniczenie:** oni **analizują i odwracają** istniejące miksy (opisowo). Ty **generujesz** nowe (twórczo). Świetny fundament danych i narzędzi, nie konkurencja dla Twojej głównej idei.

## 13. Twój własny generator datasetu

Pipeline, który zbudowałeś, żeby ominąć lukę gatunkową:

1. Znajdujesz mixtape'y na **Apple Music** w gatunkach, które akademicki zbiór ignoruje
2. Robisz **screenshoty** tracklist
3. **Claude Code** czyta tracklisty i wyciąga track ID
4. Ściąga 30-sekundowy sample dla każdego ID z **iTunes**
5. Dopasowuje sample z powrotem do mixtape'ów, żeby znać realną kolejność

Efekt: własny generator datasetu dla dowolnego gatunku. Tanie, skalowalne, pokrywa dokładnie te gatunki, gdzie Twoja teza tripletów robi się ciekawa, bo reguły miksowania są nieoczywiste. Dopasowanie ID działa u Ciebie niezawodnie.

## 14. Timestampy, dwell time i granica tego, co się da

**Dlaczego mixtape'y na Apple Music są już podzielone na tracki:** ten podział prawie na pewno nie jest automatyczny. Dostarcza go wytwórnia albo sam DJ w postaci **cue sheet** — pliku wskazującego, gdzie każdy utwór się zaczyna i kończy w ciągłym audio. Apple to wchłania i pokazuje czyste granice.

To złoto: punkty podziału wybiera **człowiek znający miks**, więc lądują na lub blisko realnego przejścia. Dostajesz cue pointy, które grupa akademicka musiała odzyskiwać całą matematyką DTW.

**Zastrzeżenie:** granica oznacza zmianę utworu, ale niekoniecznie dokładny obszar blendu, gdzie oba grają naraz. Blisko, ale nie zakładaj precyzji co do klatki.

**Dwell time.** Skoro zbierasz timestampy, masz nie tylko kolejność, ale i czas. Odstęp między znacznikami mówi, jak długo DJ faktycznie siedział na utworze. To realny sygnał przepływu: trzydziestosekundowe wrzucenie na chama to zupełnie inna decyzja niż czterominutowy blend. Track-most może dostać mało czasu, a kotwica peak-time bywa ujeżdżana długo. Środkowy utwór przestaje być oceniany tylko po tonacji i energii — dochodzi rytm trwania.

**Czego się NIE da (ważne ustalenie):**
- Timestampy Apple mówią, **gdzie w miksie** siedzi utwór — nie mówią, **którą sekcję** oryginału zagrano (intro, breakdown, drop). To mapowanie po prostu nie istnieje w metadanych.
- **Sample z iTunes nie pomoże** — to stały fragment, zwykle środek utworu, około 90. sekundy, ten sam dla wszystkich. Odpowiada na „co to za utwór i jakie ma tonację i tempo", nie na „którą część zagrano".
- **Pełnego utworu nie ściągniesz** z Apple Music — DRM.
- **Rekordbox nie jest obejściem.** Integracja z Apple Music jest realna, ale działa **strumieniowo**: Rekordbox odtwarza i potrafi analizować BPM oraz tonację w locie, ale **nie pozwala wyeksportować pliku audio**. DRM trzyma. Pomaga grać i analizować, nie wyciągać.

Jedyna czysta ścieżka do informacji o sekcji: **własne, legalnie posiadane pliki** wyrównane do własnych miksów.

---

# CZĘŚĆ D — ENERGIA I ŁUK SETU

## 15. Ekstrakcja energii — cztery cechy

Set ma łuk (budowanie, szczyt, ściągnięcie, znowu budowanie), a kierunek ma znaczenie — A→B zwykle powinno podnosić albo trzymać energię. Energia to mieszanka mierzalnych cech, wszystkie oparte na analizie, którą już robisz:

1. **Głośność** (ogólna moc i pełnia) — miara percepcyjna **LUFS**, nie surowa moc sygnału
2. **Gęstość rytmiczna / napędzający dół** (stopa + gęstość onsetów) — z detekcji onsetów używanej już do BPM
3. **Jasność widmowa** (zawartość wysokich częstotliwości) — mierzona **centroidem widmowym**
4. **Rozpiętość dynamiczna / drop** (huśtawka między cicho a głośno)

## 16. Normalizacja i wagi

**Wagi startowe:** głośność 40%, gęstość rytmiczna 30%, jasność widmowa 20%, dynamika 10% (dynamika jest szumniejsza w pomiarze, więc na starcie mniejsza waga).

**Normalizacja do 0–1 — krok, na którym większość się wykłada.** Skalowanie min-max, ale **na percentylach 5. i 95.**, nie na wartościach absolutnych, z obcinaniem wartości odstających. Inaczej jeden przemasterowany albo zepsuty plik rozciągnie skalę i zbije wszystko inne do wąskiego pasma.

**Kalibracja:** dostrajasz wagi względem swoich miksów — prawdą podstawową jest to, gdzie utwór faktycznie wylądował w realnym secie. Peak-time banger powinien punktować blisko szczytu, warm-up nisko. Typowy kształt łuku wyuczysz z tysięcy miksów.

## 17. Pełny pipeline energii

1. Weź każdy utwór (30-sekundowe preview albo własny plik)
2. Wyciągnij cztery surowe cechy (LUFS, gęstość onsetów, centroid widmowy, rozpiętość dynamiczna)
3. Znormalizuj każdą do 0–1 na percentylach 5/95
4. Zmieszaj wagami 40/30/20/10 → jedna liczba energii na utwór
5. Skalibruj wagi na realnych miksach
6. Podaj wynik do silnika tripletowego — każdy środkowy utwór oceniany za dopasowanie harmoniczne **i** za to, czy jego energia pasuje do łuku w tym momencie

---

# CZĘŚĆ E — REKONSTRUKCJA PERFORMANCE'U

## 18. Cel

Nie tylko kolejność utworów, ale **pełna transkrypcja tego, co DJ zrobił fizycznie na sprzęcie**: gdzie każdy track wszedł i wyszedł, timing crossfade'u, echa, loopy, ruchy EQ, korekty BPM — wszystko zmapowane na mixtape i z powrotem na utwory. Mapowanie każdego przycisku CDJ na nagranie.

Tu Twoja poprawka była słuszna: podejście „wystarczy kolejność + energia" jest za małe dla tego celu. Gdzie DJ wpadł i zapętlił **jest** performansem.

Realia: to najgłębszy koniec reverse-engineeringu miksów DJ-skich, świat akademicki rozpracował go tylko częściowo. Wspomniany paper o odwracaniu obszarów przejścia (analiza subpasmowa z optymalizacją wypukłą) zaszedł kawałek, głównie do obszarów blendu.

## 19. Co da się dziś, a co jest jeszcze badaniami

**Łatwe, w pełni wykonalne dziś — przechwytywanie własnych działań na żywo.** Warstwa capture zmapowana na typowy układ CDJ i miksera, logująca każdą akcję na osi czasu. To nie zgadywanie, to nagrywanie: większość setupów Pioneera wypluwa dane czasowe i sterujące przez swój protokół link, a kontrolery MIDI wysyłają każde pokrętło i przycisk jako komunikat MIDI. Logujesz strumień względem utworu i masz idealną transkrypcję performance'u. Makieta w godzinę — całkowicie realne.

**Trudne, problem badawczy:** zrobić to **wstecz** — wziąć cudzy gotowy mixtape, gdzie nigdy nie miałeś sprzętu, i wywnioskować, które przyciski wciśnięto.

**Strategia:** zbuduj najpierw aplikację przechwytującą na własnych deckach. Jest realna i szybka, a przy okazji **generuje idealnie oetykietowane dane treningowe** do rozgryzienia problemu odwrotnego.

## 20. Machine learning na wideo — tracking rąk

Twój pomysł: nagrania DJ-ów z góry (top view), rozpoznanie sprzętu, śledzenie rąk i wnioskowanie o ruchach. Formalnie: **estymacja pozy + rozpoznawanie akcji**. Klocki istnieją — tracking dłoni jest dojrzały, to ta sama technologia co sterowanie gestami.

**Ściana:** rozpoznanie, że ręka poszła do crossfadera, jest wykonalne. Odczytanie, **jak daleko** go pchnięto albo **które z czterech małych pokręteł EQ** ruszono o włos — z wideo jest brutalnie trudne. Precyzja pracy DJ-a jest drobniejsza niż rozdzielczość kamery, a dłonie **zasłaniają dokładnie te kontrolki**, które próbujesz odczytać.

Werdykt: wideo daje zgrubną warstwę gestów — mniej więcej kiedy i mniej więcej gdzie — nie czysty zapis wartości.

## 21. Fuzja wideo + audio — architektura „gdzie" + „ile"

To najmocniejszy pomysł całej sesji, sformułowany przez Ciebie:

- **Wideo robi „gdzie" i „co"** — ML patrzy na ręce i mówi: sięgnęli do sekcji efektów, dotknęli crossfadera, pracują na EQ. Zgrubne, ale niezawodne: która kontrolka była w grze i mniej więcej kiedy.
- **Audio robi „ile"** — skoro wiesz, że dotknęli echa, słyszysz jego feedback i timing. Skoro wiesz, że weszli filtrem, słyszysz sweep i mierzysz zasięg. Dźwięk podaje wartości, których wideo nie rozdzieliło.

**Dlaczego to eleganckie:** każda strona zawęża przestrzeń przeszukiwania drugiej. Wideo powstrzymuje audio przed ślepym zgadywaniem, co się zmieniło; audio dokłada precyzję, której kamera nie widzi. Osobno żadne nie dochodzi do celu, razem mogą.

To pomysł na poziomie badawczym i nie jest w literaturze postawiony w tak czystej formie.

## 22. Separacja stemów i metoda różnicy

**Problem:** w nagraniu słyszysz wszystko naraz — surowy utwór plus każdy efekt nałożony przez DJ-a (echo, pogłos, filtr), wypieczone w jeden sygnał. Chcesz to rozdzielić: co jest oryginałem, a co robotą DJ-a.

**Metoda różnicy** (Twoja analogia: tryb **Difference** w warstwach Photoshopa — dolna warstwa czysty oryginał, górna fragment miksu; co identyczne, robi się czarne, efekty i przejście świecą). Masz oryginały ze swojego zbioru, więc wyrównujesz oryginał z fragmentem miksu, a to, co zostaje, jest wkładem DJ-a.

**Trudności:** wyrównanie musi być niemal idealne, bo echo rozmazuje energię w czasie, a pogłos w częstotliwości. A gdy dwa utwory nakładają się w blendzie, masz dwa oryginały plus efekty splątane razem.

**Wzmocnienie przez separację źródeł — Demucs** (Twój wybór, najlepszy z otwartych separatorów):
1. Rozdziel **i oryginał, i fragment miksu** na stemy (perkusja, bas, wokal, melodia)
2. Wyrównaj każdy stem osobno
3. Zrób różnicę **per stem** — stopa do stopy, wokal do wokalu
4. Odczytaj efekty warstwa po warstwie

Jest czyściej, bo efekty zwykle uderzają w konkretne stemy (delay na wokalu, filtr na całej górze) — separacja przed odejmowaniem sprawia, że różnica ląduje tam, gdzie efekt naprawdę siedzi. Bonus: separacja pomaga rozplątać, która perkusja należy do tracka A, a która do B w obszarze blendu.

**Wskazówka:** Demucs ma warianty — standardowy czterostemowy i dostrojony, wolniejszy, ale czystszy. Skoro jakość separacji bezpośrednio decyduje o czystości różnicy, a nie robisz tego w czasie rzeczywistym, bierz wolniejszy, lepszy.

---

# CZĘŚĆ F — PODSUMOWANIA

## 23. Glosariusz — wszystkie nazwy z rozmowy

**Biblioteki i narzędzia**
- Essentia (`MTG/essentia`), Essentia.js (WebAssembly), MusicExtractor
- Gaia (`MTG/gaia`) — indeksowanie i podobieństwo
- librosa — chroma, najprostszy prototyp
- madmom — zależność djmix
- beets (`beetbox/beets`) + plugin beets-beatport4
- Demucs — separacja stemów
- Rekordbox — integracja z Apple Music, tylko streaming
- Replicate — hosting `mtg/essentia-bpm` (~$0.00036/wywołanie)
- Claude Code, Codex — Twój warsztat
- mir_eval — implementacja metryk

**Instytucje i grupy**
- MTG (Music Technology Group), Universitat Pompeu Fabra, Barcelona
- Deezer — S-KEY
- mir-aidj — grupa badawcza DJ MIR
- Ircam-RnD — UnmixDB
- ISMIR, NIME, NeurIPS, MIREX, IEEE Xplore

**Modele i metody**
- Krumhansl-Schmuckler (profile tonalne), HPCP, chromagram, constant-Q transform, FFT/Fourier, autokorelacja, detekcja onsetów
- STONE → S-KEY (self-supervised)
- LLark (enkoder Jukebox, alternatywy CLAP, Llama 2, MPT-1B)
- Vision transformery do estymacji tonacji (czasopismo *Information*)
- DTW (dynamic time warping), subsequence alignment
- HMM (ukryte modele Markowa), DJ-MC (reinforcement learning), T-RECSYS
- Filtrowanie kolaboratywne, CNN na surowym audio, deep content-based recommendation
- MFCC, mel, centroid widmowy, LUFS

**Zbiory danych**
- djmix-dataset (mir-aidj), UnmixDB, 1001Tracklists (źródło tracklist)
- GiantSteps (Key i Tempo), GTZAN, MedleyDB, MusicNet, MusicCaps, FMA, FMAKv2, Million Song Dataset

**Papery**
- *A Computational Analysis of Real-World DJ Mixes using Mix-To-Track Subsequence Alignment* (ISMIR 2020) — Taejun Kim, Minsuk Choi, Evan Sacks, Yi-Hsuan Yang, Juhan Nam
- *Reverse-Engineering The Transition Regions of Real-World DJ Mixes using Sub-band Analysis with Convex Optimization* (NIME 2021)
- *Temporal Considerations in DJ Mix Information Retrieval* (2025)
- *Deep Content-Based Music Recommendation* (NeurIPS)
- *Content-Driven Music Recommendation* (przegląd 55 prac)
- *Methods and Datasets for DJ-Mix Reverse Engineering*
- *UnmixDB: A Dataset for DJ-Mix Information Retrieval* (Schwarz, Fourer, ISMIR 2018)
- *DJ-MC: A Reinforcement-Learning Agent for Music Playlist Recommendation*
- *T-RECSYS: A Novel Music Recommendation System Using Deep Learning*

**Platformy, API, licencje**
- Apple Music API / MusicKit, iTunes preview (30 s)
- Spotify Web API (audio-features wycofane), Discover Weekly
- Beatport v4 REST API, Partner Portal, OAuth2, DJ Charts, Beatport LINK
- Tidal, Amazon Music, Tunebat, Parse.bot
- ISRC, notacja Camelot
- AGPLv3, GPLv3, LGPL, Affero

**Metryki**
- MIREX score, KSEA (Key Signature Estimation Accuracy), Acc2 ±4% oktawy, F₁

## 24. Frazy do wyszukania

Zebrane w rozmowie, bo tryb głosowy nie podaje linków:

- `S-KEY Deezer`
- `Krumhansl-Schmuckler key finding`
- `GiantSteps key dataset`
- `HPCP harmonic pitch class profile`
- `constant-Q transform key estimation`
- `musical key estimation vision transformers`
- `Essentia key extractor`
- `librosa chroma`
- `MIREX audio key detection`
- `GiantSteps versus MIREX dataset`
- `beets beatport four` (GitHub — dokumentacja setupu podaje wymagany poziom konta)
- `mir-aidj djmix-dataset`
- `Temporal Considerations in DJ Mix Information Retrieval`
- `Deep Content-Based Music Recommendation NeurIPS`

## 25. Otwarte pytania i następne kroki

**Nierozstrzygnięte:**
- Czy darmowe konto Beatport wystarczy do beets-beatport4, czy potrzebna płatna subskrypcja (LINK)?
- Jak dokładnie Apple dzieli mixtape'y — potwierdzenie hipotezy o cue sheet od wytwórni/DJ-a.

**Do zrobienia (ustalone, jeszcze nierobione):**
- Rozbudowa tabeli porównawczej detekcji tonacji o realnie zmierzone wyniki
- Wzór na score przewidywalności DJ-a — spisanie formuły
- Wpięcie dwell time w model łuku energetycznego
- Makieta warstwy capture na własnych deckach (Pioneer link / MIDI)

**Trzy luki wskazane jako warte uwagi:**
1. **Zimny start we własnym systemie** — jak umieścić track, który nie pojawił się w żadnym Twoim miksie? Ratuje analiza audio: wstawiasz go po samym brzmieniu, dopóki nie pojawią się realne dane z miksów.
2. **Ewaluacja poza dokładnością** — czy set faktycznie dobrze brzmi dla człowieka, a nie tylko trafia w odłożone dane? Mały test odsłuchowy z prawdziwymi DJ-ami powie to, czego liczby nie powiedzą.
3. **Nudne, ale krytyczne: czyszczenie danych** — dopasowywanie track ID w tysiącach miksów, obsługa remiksów i editów, które są technicznie innymi plikami, a muzycznie tym samym. To zrobi albo zabije cały zbiór.

---

## Jedno zdanie na koniec

Masz spójny, ambitny system: własne dane w gatunkach, które akademia pominęła, autorską tezę o tripletach, której nikt nie zajął, plan walidacji, który da się opublikować, i ścieżkę do rekonstrukcji performance'u przez fuzję wideo i audio. Reszta to praca do odrobienia.
