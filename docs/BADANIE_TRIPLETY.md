# Triplety: środkowy utwór jako most — teoria i pomiary

*Wstęp do opisu badania. Autor tezy: Jan Trybus (DanceLab). Pomiary:
sierpień 2026, silnik DanceLab. Wszystkie liczby odtwarzalne ze skryptów
w repozytorium (`scripts/triplet_validation.py`, `experiments_priv/`).*

## 1. Teza

Systemy rekomendacji sekwencji muzycznych — od playlist po narzędzia
DJ-skie — modelują przejścia jako **pary**: „co pasuje po A?". Teza tego
badania brzmi inaczej: podstawową jednostką setu DJ-skiego jest
**triplet A–B–C**, a środkowy utwór B jest definiowany przez to, jak
**mostkuje** dwa punkty — skąd przychodzi *i dokąd prowadzi*. Okno
przesuwa się po secie: A-B-C ocenia B, B-C-D ocenia C. Środkowy utwór
nie jest odpowiedzią na przeszłość, tylko zobowiązaniem wobec przyszłości.

Pozycjonowanie wobec stanu wiedzy: literatura DJ-MIR kręci się wokół par
i przejść (mir-aidj, *Temporal Considerations in DJ Mix IR* 2025) albo
łańcuchów patrzących wstecz (HMM, rekomendery sekwencyjne); komercyjne
rekomendery (Beatport) modelują współwystępowanie bez kolejności.
Ujęcie trigramowe, patrzące w przód, nie jest podejściem dominującym.

## 2. Dane

* **Korpus miksów** (istniejący zasób DanceLab): 801 wyrównanych miksów,
  zbiór porządkowy 1604 obserwacji „historia → kandydaci → faktyczny
  wybór DJ-a".
* **Żniwa Apple Music** (zbudowane w tym badaniu, własny generator
  datasetu): zrzuty katalogu „Miksy DJ-skie" → OCR lokalny → iTunes
  Search jako czyściciel (pewne dopasowanie albo odmowa) → tracklisty
  z osadzonego JSON-a stron albumów → cechy z 30-sekundowych preview.
  Wynik: **152 realne sety · 2777 utworów · 2473 tripletów**, z czasami
  utworów (dwell time). Domena świeża względem korpusu — zero przecieku
  z wcześniejszego strojenia.
* **Studium przypadku**: Four Tet @ Awakenings ADE 2024 (4 h 28 min,
  56 utworów, tracklista ze znacznikami).

Cechy utworów wszędzie te same trzy: tempo (sztywna siatka), tonacja
(Camelot), energia (RMS). Scorery: „ręczny" (komponenty silnika:
0,4·tempo + 0,4·harmonia + 0,2·energia) i „zmierzony" (ilorazy
wiarygodności z korpusu, real vs chance).

## 3. Metodologia

Test „ukryj B": model widzi A i C, ma wskazać prawdziwe B wśród
kandydatów. Metryki: percentyl rangi (0 = zawsze pierwszy strzał,
0,5 = losowo), top-1, MRR oraz punktacja częściowa „muzycznie wymienny"
(ta sama tonacja, złożone ΔBPM ≤ 4% — duch połówek MIREX). Istotność:
parowany bootstrap. Strojenie (wagi α, rekalibracja liftów) wyłącznie
na połowie miksów; wszystkie tabele z drugiej połowy.

Dwie pułapki złapane i udokumentowane po drodze: (1) w zbiorze
porządkowym kandydaci to utwory, które *dopiero zagrają*, więc C siedzi
w puli i scorer tripletowy „wygrywa" zdegenerowanym przejściem C→C —
C musi wylecieć z puli; (2) liczby absolutne zależą od trudności puli —
raportujemy zawsze wyścig parowany na identycznych pulach, nie liczby
w próżni.

## 4. Wyniki

**(a) Korpus, pule realistyczne (B\* + 24 dystraktory), 895 przypadków:**
triplet wygrywa na każdej metryce; wagi ręczne p<0,0001, zmierzone
top-1 25,0% vs 22,0% (p=0,082). Pula wewnątrz-miksowa (~3,5 kandydata,
sami pasujący) jest nasycona — tam różnic nie widać.

**(b) Świeża domena (żniwa Apple), 2473 przypadki:** triplet
**56,8% vs 47,7%** top-1 (ręczne), 35,9% vs 29,5% (zmierzone) — oba
p<0,0001. Wynik trzyma się przy podwojeniu próby i przenosi między
gatunkami (Dance +11, House +13, Electronic +10 pp).

**(c) Symetria zmierzona, nie założona:** strojenie wagi α między
członem przeszłości s(A→B) a przyszłości s(B→C) na siatce 0,25–1,5
daje optimum **α = 1,0** dla obu scorerów. Przyszłość waży dokładnie
tyle, co przeszłość.

**(d) Reżim trudny (kandydaci z tego samego miksu — „worek DJ-a"):**
triplet 29,6% vs 14,8% top-1 (p<0,0001) — w worku, gdzie wszystko
z grubsza pasuje, most **podwaja** trafialność.

**(e) Granica nr 1 — wielka pula.** Ukrycie co drugiego utworu w secie
Four Teta i szukanie wśród 2816 kandydatów: most lepszy od pary
(mediana rangi 549 vs 743; losowo ~1408), ale zero trafień top-10.
Trzy zgrubne cechy wybierają w worku ~25, nie wyszukują jednego utworu
w tysiącach — do dużych pul konieczny prefiltr brzmieniowy (embedding).
Zbieżne z wcześniejszym pomiarem priors: podobieństwo brzmienia rządzi
doborem puli, nie następnym wyborem.

**(f) Granica nr 2 — budowa otwarta.** Rekonstrukcja 152 setów
(worek miksu + prawdziwy opener): budowniczy z patrzeniem w przód NIE
bije parowego (11,6% vs 12,5% odtworzonych sąsiedztw, p=0,88). Gdy C
jest dowolne, człon przyszłości („max po wszystkim, co zostało") jest
niemal stały i tylko szumi.

**(g) Budowa między filarami — most wraca.** Filary = co 4. utwór
realnego seta przybity na pozycji; 636 segmentów; optymalizator
doskonały (pełny przegląd permutacji) po obu stronach; różnica
wyłącznie w celu (most widzi krawędź wejścia w prawy filar):
krawędzie odtworzone **48,9% vs 42,3%**, segment ułożony **dokładnie**
jak DJ **36,2% vs 28,1%** — oba p<0,0001.

## 5. Teoria (synteza)

**Most potrzebuje drugiego brzegu.** Gdy C jest ustalone — luka
w secie, szczelina przy podmianie, nadchodzący filar — patrzenie
w przód wygrywa zawsze i wyraźnie (+8–15 pp, p<0,0001). Gdy C jest
dowolne — otwarta budowa — nie daje nic. A przy pulach rzędu tysięcy
potrzebny jest brzmieniowy prefiltr, bo trzy zgrubne cechy nie niosą
dość informacji. Siła tripletu to siła **ograniczenia**, nie spekulacji.

## 6. Konsekwencje praktyczne (DanceLab)

* Podpowiedzi do szczeliny (podmiana/wstawienie) już liczą średnią
  wejścia i wyjścia — czyli dokładnie zwycięską formułę α=1; badanie
  zamienia intuicję w dowód.
* Budowa zwykła zostaje parowa z łukiem globalnym (zmierzone: lookahead
  nie płaci).
* **Wdrożone (09.08.2026):** budowa w trybach filarowych liczy krawędź
  DO nadchodzącego filara (`set_builder._best_successor`, parametr
  `bridge_to`; zmierzony zysk +8 pp dokładnych rekonstrukcji; ścieżka
  bez filarów niezmieniona bajt w bajt).
* Architektura dwupoziomowa potwierdzona: embedding zawęża worek,
  most wybiera w worku.

## 7. Ograniczenia i dalsza praca

Cechy z 30-sekundowych preview (środek utworu); detekcja tonacji
szumna (bazowo 47% zgodności z sędzią Rekordbox); znaczniki tracklist
ludzkie i przybliżone; przewaga gatunkowa Dance/House w żniwach.
Dalej: dwell time jako sygnał rytmu trwania, prefiltr CLAP dla dużych
pul, warstwa capture (idealne etykiety z własnych decków), test
odsłuchowy z DJ-ami (ewaluacja poza trafialnością), publikacja
(ISMIR LBD).
