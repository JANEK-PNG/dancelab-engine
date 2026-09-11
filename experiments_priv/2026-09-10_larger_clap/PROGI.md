# larger_clap_music vs clap-htsat-unfused — progi zapisane PRZED pomiarem

Data: 2026-09-10. Pytanie: czy `laion/larger_clap_music` (Apache-2.0) ma zastąpić
`laion/clap-htsat-unfused` jako odcisk brzmienia. Wzór: OBALONE A5 (MuQ vs CLAP,
22.07): hubness + ślepy odsłuch 6 kotwic. Raport A5 nie istnieje już na dysku,
metoda odtworzona z ledgera.

Materiał: wszystkie analizy z `experiments_priv/2026-07-30_rebuild/processed`,
których `source_path` istnieje na dysku (272 pliki; strumienie Apple wykluczone —
brak audio). Oba modele liczone tą samą metodą co `scripts/corpus_e_embeddings.py`:
48 kHz mono, 5 okien po 10 s rozłożonych równo, średnia, L2. Dedup: pary o kosinusie
≥ 0,999 w OBU modelach traktowane jako duplikat i usuwane przed liczeniem (caveat
z recenzji A5: eksperyment na nie-zdedupowanej bibliotece).

Warunki wymiany (wszystkie trzy naraz):

(a) **hubness nie gorszy** — dla k = 10: największa liczba wystąpień jednego utworu
    w listach sąsiadów (N_k max) dla larger ≤ 1,2 × N_k max dla htsat; dodatkowo
    skośność rozkładu N_k nie większa o więcej niż 0,5.
(b) **czystość gatunkowa top-10** — udział sąsiadów z tym samym `genre` co utwór
    (liczony tylko dla utworów z gatunkiem) dla larger ≥ htsat + 3 punkty procentowe.
(c) **ślepy odsłuch Janka** — 6 kotwic wybranych losowo (ziarno 20260910) spośród
    utworów z gatunkiem; dla każdej kotwicy 3 pary (najbliższy sąsiad wg larger vs
    najbliższy wg htsat, pozycje 1–3, z pominięciem sąsiadów wspólnych); Janek wskazuje,
    który brzmi bliżej kotwicy, nie wiedząc, który model go dał. Wymiana, gdy larger
    wygrywa ≥ 60 % rozstrzygniętych par (remisy nie liczą się do mianownika).

Co obala: niespełnienie (a) LUB (b) kończy pomiar bez odsłuchu — wynik idzie do OBALONE.
Spełnienie (a) i (b), a przegrana w (c) — też do OBALONE, z zapisem par.

Czego ten pomiar NIE mówi: nic o strumieniach Apple (82 % kolekcji) — tam wektory
są z 30-sekundowych próbek i musiałyby być przeliczone osobno.

## Uzupełnienie po przejrzeniu metadanych (PRZED załadowaniem modeli)

Metadane 272 plików: 5 krótsze niż 60 s (one-shoty), 267 ≥ 60 s. Gatunek: pole
`style_label` z tagów plików 87/267; gatunek z bazy Rekordboxa (tylko odczyt,
`load_rekordbox_genre_map`) 100/267; złączone (Rekordbox wygrywa, tag pliku jako
zapas) **151/267, 30 klas, 12 klas ≥ 5**. Lipcowe wektory htsat
(`data/reports/library_embeddings.json`, 296) pokrywają 240/267 po ścieżce.

Doprecyzowania:
* wykluczone `duration_sec < 60` (5 plików);
* gatunek normalizowany WYŁĄCZNIE mechanicznie: małe litery, „-" → spacja, zbite
  spacje. „techno (peak time" i „techno (peak time / driving)" zostają osobno —
  sklejanie to osąd, nie poprawka. Zaniża to (b) obu modelom jednakowo;
* (b) liczone tylko dla utworów z gatunkiem; mianownik = sąsiedzi z gatunkiem;
  próg materiału: ≥ 120 utworów z gatunkiem i ≥ 2 klasy po ≥ 5 — spełniony (151, 12);
* kontrola potoku: kosinus między moim htsat a lipcowym htsat na 240 wspólnych —
  mediana ≥ 0,99, inaczej potok jest zły i pomiar nieważny;
* liczba opisowa bez progu: średni Jaccard list top-10 między modelami;
* pary do (c): kotwice losowane z ziarnem 20260910 spośród utworów z gatunkiem;
  top-3 obu modeli, wspólni sąsiedzi odpadają, parowanie po randze; kotwica bez
  pary pomijana, losowanie do 6 kotwic z ≥ 1 parą; A/B losowo per para,
  klucz w osobnym pliku.
