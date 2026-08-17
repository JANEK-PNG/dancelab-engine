# Muzyka generatywna — osobny wątek (decyzja Janka, 2026-08-01)

Ten katalog to całość wątku „tworzenie muzyki" wydzielonego z R&D DanceLab Pro,
żeby nie rozmywać rdzenia. Wszystko działa, wszystko jest odtwarzalne — każdy
utwór ma swój skrypt, zero cudzego audio, same sinusy, szum i filtry.

## Utwory (chronologicznie — każdy uczył czegoś nowego)

| plik | co udowodnił |
|---|---|
| `utwor.py` | pierwszy utwór z czystego DSP (Sigur Rós × Bon Iver × house) |
| `in_between.py` | dwa głosy + reszta z jednego kanału = in between gra samo |
| `autoportret.py` | 40 głosów, poprawki malejące, brak ciągłości; spektrogram → `spektrogram.py` |
| `wzor_kordiego.py` | wzór S = A + B + C·R_D + Syn·Φ(H) malowany na spektrogramie; Griffin–Lim |
| `dluga_ekspozycja.py` | ISO w dół (110 iter. z pędem, okno 2×) + smugi 1,4 s; +2,5 dB realnej energii |
| `calkowanie.py` | linie grane oscylatorami, faza całkowana: czystość −9,9 → +7,1 dB |
| `hybryda.py` | Serra SMS: linie + plamy jako szum (losowa faza POPRAWNA dla szumu) |
| `szeroka_rama.py` | rama 25 Hz–18 kHz: 48 % Φ żyło poza starą ramą; przestrzeń = 3. wymiar |
| `wielorozdzielcza.py` | 3 płótna (341/85/11 ms), 96 kHz do 46 kHz, dół mono |
| `oddech.py` | in between z PAMIĘCI, nie z chwili; wdech 1,2 s / wydech 4 s; krawędzie −16 dB |
| `nasze_in_between.py` | wszystko naraz + liczby Janka (szew 171, wejście liczone, bas 97 %) |
| `zawsze_pierwszy_raz.py` | autoportret-piosenka; rój zwęża się w przestrzeni gdy się zgadza |
| `hybryda_wielorozdzielcza.py` | pełny wzór (D, T, Φ z pamięci, sprzężenie) na 3 płótnach do 46 kHz; dół gra same linie |
| `miary_rubata.py` | przyrządy do rubata, każdy skalibrowany na wzorcu o ZNANYM rubacie zanim zmierzył utwór |
| `rubato.py` | czwarte pole ρ(f,t): S = Γ·{A_ρ+B_ρ+C·R_D+Syn·Φ}, X_ρ(f,t)=X(f,t−δ); reguły z dysertacji Shoostovian |

## Twarde lekcje (przenośne do każdej dalszej pracy)

1. **Faza: całkować dla tonów, losować dla szumu.** Griffin–Lim zgaduje i zostawia
   szkło; oscylator liczy i jest czysty; szum MA fazę losową z natury.
2. **H wewnątrz Φ**: trzeci materiał rodzi się z tego, co zalega (wygładzenie ~2 s),
   nie z ataków — inaczej dziedziczy siekanie źródeł. (Przeczucie Janka > moje wykonanie.)
3. **Budżet nieoznaczoności wydaje się per pasmo**, nie raz dla wszystkiego.
4. **Rama jest decyzją patrzącego** — wąska rama ucinała 48 % in between (sumy wysoko,
   różnice nisko).
5. **Głosy roju muszą mieć własną fazę startową i wejścia ±60 ms**, inaczej chór
   zapada się w mono (korelacja 0,994).
6. **Miary też się psują**: log(0) → NaN; puls ≠ trzepot (mierzyć wielokrotności
   bramki, nie całość); globalne −33 dB może ukrywać artefakt CO 2 SEKUNDY na stopie.
7. **Szum obok trzymanego basu zawsze dudni.** Wąskopasmowy szum o losowej fazie
   ma własne falowanie 4–30 Hz (Rayleigh), a w paśmie krytycznym dołu ucho słyszy
   je jako dudnienie z linią. Zmierzone osobno: linie dołu +2,1 dB, szum dołu
   +5,6 dB, ich suma −5,1 dB — dopiero razem robią szkodę. Lek nie jest w
   syntezie, tylko w POLITYCE PASMA: dół gra praktycznie same linie (szeroki
   karb wokół każdej z nich), mgła zostaje środkowi i górze. Po tym +2,9 dB.
8. **NaN wchodzi tam, gdzie liczy się pierwiastek z iloczynu pól.** Wygładzanie
   w float32 zostawia −1e−12; √(ujemne) = NaN, a NaN wsiąka w pamięć H i zatruwa
   cały utwór po cichu (raport pokazywał `nan%`, plik i tak by powstał).
   Przycinać do zera przed √ i asertować skończoność S po każdym obrocie wzoru.
9. **Przyrząd porównawczy musi mieć WSPÓLNĄ bazę.** Próg „0,5·max wiersza"
   liczony osobno dla bramki zdeformowanej i kontrolnej dawał −15 ms biasu
   (max próbkowanej bramki zależy od przypadkowego trafienia siatki w szczyt
   akcentu, ±7%). Miara różnicowa z JEDNYM progiem: bias znika, błąd spada
   z 14 ms na 1,2 ms. Ta sama zasada co lekcja 6, od strony przyrządu: zanim
   uwierzysz odchyleniu, sprawdź przyrząd na znanej stałej (δ ≡ −50 ms).
10. **Przy deformacji czasu miara pulsu musi jechać z tempem.** Sztywny
   grzebień 2,8 Hz liczy własne rubato jako trzepot (fałszywy regres −20 dB
   na wzorcu ±15%). Odkręcenie: faza Hilberta pasma pulsu → obwiednia
   przepróbkowana na czas taktu → dopiero tam stara wąska miara.
11. **Dwa rendery „tego samego" różnią się o 9–15% RMS widma** — losowe fazy
   startowe torów i realizacja szumu. To podłoga każdego eksperymentu A/B na
   tym silniku: zmiana, która maluje mniej niż ~10% obrazu, jest z audio
   niedowodliwa (i pewnie niesłyszalna), choćby była realna. Zanim porównasz
   dwa rendery, porównaj przewidzianą zmianę z tą podłogą. Chcesz mierzyć
   subtelniej — najpierw przypnij fazy (np. hasz z częstotliwości toru
   zamiast kolejności z generatora).
12. **Porównując odległości do dwóch zbiorów celów, wyrównaj gęstości** —
   gęstszy zbiór wygrywa medianę niezależnie od prawdy. I wyrównaj gain,
   zanim odejmiesz widma: bez tego „różnica" to głośność (35 tys. komórek
   „pojawionych" vs 2,4 tys. „znikłych"; po wyrównaniu 6,3 vs 6,4 tys.).

## Związek z DanceLab Pro (nie ciągnąć do rdzenia bez decyzji Janka)

Wspólny silnik pojęć: wzór Kordiego = uogólnienie naszego pomiaru szwu; liczby
Janka (szew 171 uderzeń, wejście „perkusja w górę/bas w dół", bas na 97 %) działają
jako parametry kompozycji. Transfer wymaga osobnej decyzji.

## Stan i możliwe następne kroki

**Zrobione 2026-08-01: hybryda wielorozdzielcza** — `hybryda_wielorozdzielcza.py`.
Dwie połówki silnika zeszły się w jednym rendererze: pełny wzór (kierunek D,
obie deformacje T, Φ z pamięci ~2 s z oddechem 1,2/4 s, sprzężenie zwrotne)
liczony na trzech płótnach o różnej rozdzielczości, rama 96 kHz do 46 kHz,
linie grane oscylatorami z fazą całkowaną, plamy szumem o losowej fazie.

Zmierzone na wyrenderowanym pliku (168 s, 96 kHz / 24 bit, szczyt 0,890):

| miara | hybryda | poprzednicy |
|---|---|---|
| czystość trzymanej składowej | **+14,2 dB** | zdjęcie −9,9 · same linie +7,1 |
| oddech / trzepot (puls osobno) | **+2,9 dB** | oddech.py +3,0 · wielorozdz. +0,9 |
| puls / trzepot | +1,5 dB | wielorozdz. +8,5 (za dużo — to był trzepot) |
| korelacja L/R dół | +0,961 (mono z wyboru) | — |
| korelacja L/R środek | +0,824 (chór żyje) | — |
| crest dołu 60–130 s | 12,4 dB | wielorozdz. 15,4 · oddech 14,9 |
| linie / plamy | dół 93/7 · środek 89/11 · góra 79/21 | — |

Czystość jest dwa razy lepsza niż w najlepszym poprzedniku, bo pełny wzór
i trzy płótna zeszły się bez Griffin–Lima. Oddech dorównał `oddech.py`
dopiero po wycięciu mgły z dołu (lekcja 7).

**Zrobione 2026-08-04: rubato jako CZWARTE pole** — `rubato.py` (+ `miary_rubata.py`).
Wzór dostał oś czasu:

    S(f,t;F) = Γ(t)·{ A_ρ + B_ρ + C·R_D(A_ρ,B_ρ) + Syn·Φ(A_ρ,B_ρ,H;F) }
    X_ρ(f,t) = X(f, t−δ(f,t)),  δ = δ₀(t) + u(f)·δ₁(t),  ρ = ∂δ/∂t

Pole ρ jest deterministyczne i wynika ze zmierzonych reguł (dysertacja
Shoostovian o Chopinie): melodia w górę → wolniej; ritenuta przed punktami
strukturalnymi (Cortot); dyslokacja rejestrów jedzie po istniejącym polu D
(rubato strukturalne ↔ melodyczne); tempo szybciej → głośniej (Γ).
Wpięcie U ŹRÓDŁA (starty nut + macierz bramki), zero przepróbkowania —
tracker, faza całkowana, H, Φ, oddech nietknięte. Deformację pochłania
przerwa między nutami (Fabian–Schubert), nie proporcje nut.

Dowody z wyrenderowanego pliku (kontrola = hybryda, ten sam kod miar):

| miara | kontrola → rubato |
|---|---|
| sd δ w powietrzu | 18,3 ms (podłoga przyrządu) → **119,5 ms** |
| regresja δ_zm ~ δ₀ zamiaru | — → nachylenie 1,16 · r +0,79 |
| rozjazd rejestrów (dyslokacja) | −1,5 → −42,2 ms (powietrze przodem) |
| fakt 2 (melodia↔tempo) | — → wsp. +1,15 przy t = 22,1 |
| fakt 7 (Cortot) | — → wsp. +1,20 przy t = 16,0 |
| fakt 3 (tempo↔dynamika, różnicowo) | — → r +0,67 |
| czystość mediana / min | +9,3 / +0,4 → +9,3 / **+1,1 dB** |
| puls w czasie taktu | +2,0 → +1,9 dB (puls żyje, tylko płynie) |
| fuzja zespołu harmonicznego | 0,578 → 0,566 (nuta cała) |

Znane i przyjęte: crest dołu 12,4 → 17,1 dB przez JEDEN zbieg przesuniętej
nuty ręki z basem siatki przy 126,8 s (pozostałe okna ≤ 12,1; szczyt globalny
mieszka gdzie indziej — headroom nieruszony). Całość o 2,1 dB cichsza od
kontroli (Γ moduluje szczyty). Sidecar `rubato_zamiar.npz` niesie całe pole —
dowód nie jest samopotwierdzeniem, bo δ_zm czyta się z audio, a zamiar z pola.

**Zrobione 2026-08-04: pełne T_(B→A)** — `pelne_t.py` + `pelne_t_dowod.py`.
Wynik NEGATYWNY i wart tyle co pozytywne: cele kwantyzacji czytane per
kolumna z żywych szczytów B (pamięć 1,2 s, transformata odległości,
portamento 0,45 s) zamiast z wiecznej drabiny. Strażnicy potwierdzili
mechanikę (cel podąża za B co do 0,01 bina) i żywość (środek 8%, góra
29–50% energii ręki widzi cele ≠ drabina; dół 0% — jego comby TO drabina).
Ale miara przewidziane-kontra-zmierzone pokazała: zmiana obrazu to
0,4–1,0% RMS, a podłoga chaosu między renderami (lekcja 11) — 9–15%.
Przy parametrach legendy (siła 0,65, ±9 binów) **legenda była już w ~92%
pełnym T** — odstępstwo mieszka tylko tam, gdzie harmoniczne różnych
dźwięków zlewają się w grzbiet, i gdzie Φ wlewa się w B w ostatniej
tercji. pelne_t.wav brzmi jak rubato.wav i tak ma być. Jeśli odstępstwo
ma być SŁYSZALNE, trzeba je wzmocnić świadomie (siła 1,0, bez rozcieńczania
0,45 s, Φ w celach od pierwszego obrotu) — to osobna decyzja kompozycyjna,
nie poprawka błędu.

**2026-08-04: PIOSENKA, nie eksperyment** — `folktronika.py`. Decyzja Janka:
in between było stanowiskiem badawczym, nie fundamentem kodu — „to była
jedynie logika, którą mamy się kierować". Więc utwór w duchu Four Teta
napisany OD ZERA, bez jednego importu z silnika. Malowanie na spektrogramie
i odczyt grzbietów wyrzucone: nuta jest grana wprost. Zostają zasady 1–12.

Instrument wiodący: Karplus–Strong z ułamkowym opóźnieniem (model fizyczny,
nie próbka i nie addytywna imitacja). Bilans pętli musi wynosić dokładnie
SR/f0 = N + opóźnienie filtra tłumiącego + allpass; pominięcie tego
pół-próbkowego członu stroiło instrument o −9 centów przy 1 kHz. Po
poprawce **< 0,3 centa przez cztery oktawy**. Pętla liczona blokami po N
próbek (blok k zależy tylko od k−1) → 21 nut po 3 s w 0,15 s.

Siedem stemów do DAW: KICK, DRUMS, HATS, BASS, CHORDS, MELODY, TEXTURES.
Render całości 29 s. Wszystkie 13 miar w normie: −1,0 dBFS, −15,5 LUFS,
dynamika 14,9 dB, korelacja L/R 0,78 (sub 0,996 — mono), puls +13,2 dB,
pętla melodii r = +0,28 (żyje, nie mechaniczna).

**Lekcja 13: balans mixu wyprowadzać z pomiaru PER STEM, nie ze słuchu
i nie z zamiaru.** Pierwszy render: cała energia w dole (sub −0,4 dB,
środek −23 dB). Po korekcie globalnej dalej źle — dopiero tabela udziału
per stem pokazała, że pad grał na −3,2 dB, a melodia na −17,0, czyli
instrument wiodący był 14 dB POD podkładem. Policzone delty do celu
naprawiły to za jednym razem, a zakres dynamiki skoczył 4,5 → 14,9 dB,
bo pad przestał maskować resztę.

**Lekcja 14: mono-maker wymaga filtra ZEROFAZOWEGO.** `mix − sosfilt(low)`
nie jest dopełnieniem pasma, tylko grzebieniem — pierwsza próba zbiła
korelację dołu z 0,85 na 0,59, czyli dokładnie odwrotnie do zamiaru.
Z `sosfiltfilt` wychodzi 0,996.

**2026-08-04: `klub.py` — celowanie w ZMIERZONY profil, nie w wyobrażenie.**
Janek dał 12 referencji (Burial, Jamie xx, Bicep, Tessela, Boys Noize,
Parallx, Detlef, Anthony Naples, Brenda, Les Petits Pilous, Bodhi) ze
słowami „nie wymyślaj koła na nowo". Z plików wyciągnięto WYŁĄCZNIE liczby
(CORPUS_ETHICS.md — cechy zostają, audio nigdy nie jest kopiowane ani
samplowane). Profil celu = mediana z 12; utwór budowany wprost na niego.
Wynik: wszystkie 14 miar w zakresie referencji, trzy trafione co do
dziesiątej (−14,1 LUFS · DR 5,5 dB · crest 10,2 dB).

Cztery lekcje, każda kosztowała render i każda była wbrew intuicji:

15. **Muzyka klubowa z górnej półki jest RZADSZA, nie bogatsza.** Moja
   folktronika miała 11,2 zdarzenia/s, referencje 4,2–6,0. Przestrzeń
   między uderzeniami jest instrumentem.
16. **Balansuj stemy na RMS, nie na szczyt.** Rzadkie uderzenia mają crest
   26–32 dB; przy normalizacji do szczytu wnoszą do sumy same szpice,
   a średnią trzyma pad. Stąd crest 15 dB i −21 LUFS przy szczycie −1 dBFS.
   Ale samo RMS też nie wystarczy: najpierw ŚCIŚNIJ stem do zadanego
   crestu, potem balansuj — inaczej szczyty hatów lądują powyżej zera.
17. **Kompresor z progiem pod poziomem ciągłym PODNOSI crest.** Zmierzone:
   21,3 → 23,1 dB. Dławi to, co trzymane, a transient i tak ucieka przez
   atak 5 ms. Głośność robi limiter z WYPRZEDZENIEM (wzmocnienie schodzi,
   zanim przyjdzie szczyt) plus iterowane wzmocnienie wejściowe — tak
   działa limiter masteringowy i dopiero to dało −21 → −14 LUFS.
18. **Miernik gęstości musi mieć stałą liczbę klatek na sekundę.** Stały
   skok 512 próbek liczy przy 96 kHz 2,18× częściej niż przy 44,1 kHz
   referencji — porównywałem gęstość w różnych jednostkach i „16,8/s"
   było artefaktem. Po naprawie 4,9/s przy celu 5,05: gęstość była dobra
   od początku, kłamał przyrząd. (To lekcja 6 jeszcze raz, od strony
   porównywania dwóch źródeł o różnym próbkowaniu.)

**2026-08-04: `klub2.py` — cztery zarzuty z odsłuchu, każdy zmierzony.**
Janek po `klub.wav`: „duży szum, słaby bass, midy i harmonie bez życia,
percussion powinno być bardziej zróżnicowane" + 15 nowych referencji
(katalog „Lekcja nr6"). Rozszerzono analizator o wymiary, których stary
profil nie widział: płaskość widmowa per pasmo, bogactwo harmoniczne basu,
ruch poziomu i barwy środka, rozrzut barwy uderzeń. Wynik: 11/13 miar
z tych czterech osi w zakresie referencji, profil głośnościowy utrzymany
(−14,1 LUFS · crest 10,0 · wszystkie pasma w zakresie).

19. **„Za dużo szumu" i „monotonna perkusja" to była JEDNA przyczyna.**
   Mediana barwy uderzeń wychodziła 6292 Hz przy zakresie referencji
   2697–5921: wszystko, co uderzało, było wysokie i szumowe. Dodanie
   perkusji w ŚRODKU pasma (tomy 88–165 Hz, kongi 196–392, klawes
   1,6–2,6 kHz) obniżyło medianę do 4398 Hz i jednocześnie zdjęło
   wrażenie szumu — bez dotykania hi-hatów.
20. **„Słaby bas" przy poziomach W ZAKRESIE znaczy: bez charakteru.**
   30–60 Hz i 60–120 Hz były prawidłowe. Brakowało treści harmonicznej:
   czysty sinus jest CZUĆ, ale nie SŁYCHAĆ na małym głośniku. Warstwa
   Reese (dwie rozstrojone piły przez ruchomy filtr rezonansowy) plus
   ruchoma linia z glissandami: bogactwo harmoniczne −1,3 → +0,9 dB.
21. **Barwa hi-hatu to prążki tonalne, nie filtrowany szum.** Odwrócenie
   proporcji (88 % szkieletu sinusowego o niewspółmiernych odstępach,
   12 % szumu) zbiło płaskość widmową powietrza 0,766 → 0,632.
22. **Profil trafiony co do dziesiątej to nie to samo co dobrze brzmiący
   utwór.** `klub.wav` miał wszystkie 14 miar w zakresie i mimo to cztery
   słyszalne wady. Każda miara mierzy to, co mierzy — jeśli wada jest
   poza zestawem osi, profil jej nie zobaczy. Ucho pozostaje detektorem
   BRAKUJĄCYCH osi; pomiar zostaje sposobem ich naprawy.

Pozostały kierunek (nie zaczęty):

- panorama jako trzecie pole malowane P(f,t), nie reguła per źródło
