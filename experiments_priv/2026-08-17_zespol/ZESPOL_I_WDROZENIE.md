# Zespół, kompetencje i wdrożenie — DanceLab Pro

Spisane 2026-08-17. Materiał z rozmowy: *„budujemy aplikację DanceLab Pro —
jaki minimalnie zespół musiałby powstać, oprzyj na realnych danych"*, plus
cztery pytania, które po niej padły.

**Dlaczego ten plik leży tutaj, a nie w `docs/`.** `docs/` jest w całości po
angielsku (sprawdzone: zero polskich słów w README, CONTRIBUTING,
architecture, DECISIONS, PRODUCT_SPEC). Ten dokument jest po polsku, jak cała
warstwa planistyczna i badawcza. Wrzucenie go do `docs/` pogłębiłoby dokładnie
to pęknięcie, które rozdział 6 opisuje jako brak numer jeden.

---

## 1. Punkt wyjścia — co zmierzone, nie co się wydaje

Wszystkie liczby policzone na repo 2026-08-17.

```
kod Pythona (nasz, bez .venv)     95 614 linii   496 plików
  src/                            40 108         187
  tests/                          18 049         116   (115 plików testowych)
  scripts/                        18 484          97
  experiments_priv/               18 841          93
warstwa danych (JSON)             67,6 mln linii

historia git                      462 commity    2026-07-09 → 2026-08-17
                                  28 dni z pracą, 979 plików dotkniętych
                                  jeden autor
przyspieszenie                    tydz. 28: 45 → tydz. 33: 158 commitów

stan jakości                      testy przechodzą w całości (kod wyjścia 0)
                                  zero TODO/FIXME w src/
                                  CI: macierz 2 Pythonów, ruff, pytest,
                                  zapadka pokrycia docstringami, osobny
                                  etat bezpieczeństwa (bandit, pip-audit),
                                  akcje przypięte po SHA
```

**Wniosek, który zmienia rozmowę o zespole:** nie ma zaległości technicznej do
nadrobienia. Zespół dostawałby czystą kuchnię, nie sprzątanie.

### To nie jest jedna aplikacja

| podsystem | linii | dziedzina |
|---|---:|---|
| `validation` | 11 421 | inżynieria jakości — **największy podsystem w repo** |
| `decision` | 8 518 | algorytmy i uczenie maszynowe |
| `tui` | 6 248 | interfejs i produkt |
| `ingestion` | 2 910 | inżynieria danych |
| `features`+`stems`+`preview`+`preprocessing` | 3 031 | cyfrowe przetwarzanie sygnału |
| `api`+`cli`+`storage`+`core` | 6 196 | backend |

Stos zależności potwierdza rozstrzał: `librosa`+`scipy`+`numba` (DSP),
`torch`+`demucs`+`scikit-learn` (ML), `fastapi` (serwis), `textual`
(aplikacja), `pyrekordbox`+SQLCipher (integracja z zamkniętą bazą).

**W firmie IT te pięć rzeczy robi pięć różnych osób.**

---

## 2. Minimalny zespół — cztery osoby plus Janek

Poniżej czterech wypada coś, czego nie da się nie robić.

**1. Inżynier dźwięku (DSP).** Siatka bitów, tempo, tonacja, rozdzielanie
ścieżek. Najrzadszy i najdroższy człowiek na liście.

**2. Inżynier uczenia maszynowego.** Warstwa `decision`, wagi z korpusu,
wektory brzmienia, podziały treningowe. Inna osoba niż wyżej: DSP to fizyka
sygnału, ML to statystyka decyzji.

**3. Inżynier danych.** 67,6 mln linii JSON, korpus, pobieranie, `ingestion`,
`storage`. Jego etat to `PLAN_BAZY.md`, fazy 0-6.

**4. Inżynier produktu.** TUI dziś, interfejs dla DJ-a jutro. Osobny zawód.

**5. Janek — właściciel dziedziny.** Nie do zatrudnienia i nie do delegowania.
Reguła wejścia (71% vs 18%), bas wstrzymany w 86% wejść, łuk „build" gorszy od
płaskiej linii — **żaden z tych czterech nie wymyśliłby tego z danych.**

### Czego świadomie NIE ma na liście

Osobnego testera (`validation` z 11 421 liniami pokazuje, że robimy to
w kodzie — taniej). DevOps-a (CI już jest i jest lepszy niż w wielu
finansowanych firmach). Menedżera — przy czterech osobach to koszt, nie pomoc.

### Kontrargument, który jest ważniejszy niż lista

**Pierwszy zatrudniony spowolni projekt, i to na kwartał.** Brooks opisał to
w *The Mythical Man-Month* (1975): ścieżek komunikacji przybywa kwadratowo —
przy dwóch osobach jedna, przy pięciu dziesięć. Nowa osoba wchodzi w 95 tysięcy
linii, w których połowa decyzji jest zapisana jako komentarz uzasadniający,
dlaczego *nie* zrobiono rzeczy oczywistej.

Czteroosobowy zespół ma sens dopiero przy horyzoncie dłuższym niż pół roku
i przy terminie wobec kogoś z zewnątrz. Bez terminu to wydatek bez funkcji.

### I rzecz, która wychodzi z własnych pomiarów

Wąskim gardłem **nie jest liczba rąk do kodu**. Lejek szwów: 40 389 możliwych
przejść → 22 276 zaobserwowanych → 21 015 zidentyfikowanych → **492
zlokalizowane w czasie (1,22%)**. Czterech inżynierów tej liczby nie podniesie,
bo ona nie zależy od kodu — zależy od tego, że **znacznika czasu nikt na
świecie nie zapisuje**.

**Gdyby budżet starczał na jedną osobę, nie brałbym żadnej z tej listy.**
Wziąłbym kogoś, kto przynosi dane i dostęp do ludzi z branży.

**Kolejność:** dane i dostęp → inżynier danych → DSP → ML → produkt. Interfejs
ostatni, bo interfejs do rzeczy, która nie wie jeszcze, co pokazuje, przepisuje
się dwa razy.

---

## 3. Dzień po dniu

**Inżynier dźwięku.** Rano: kolejka z nocnego przebiegu, przegląd przypadków
o niskiej pewności tempa — zawsze jest garść, gdzie silnik podał 128 zamiast
64. Słucha, rozstrzyga, zapisuje jako test. Dzień: jedno pytanie na raz; teraz
w kolejce leży to, że **ślepe wykrywanie szwów nie zadziałało** (F1 0,26 na
realnym secie) i trzeba iść w dopasowanie do utworów źródłowych. Odblokowuje
26 pustych kolumn w szkielecie analiz (11 na utwór, 15 na szew).

**Inżynier ML.** Rano: wynik nocnego treningu kontra poprzednia wersja, jedna
liczba. Dzień: fazy 4 i 5 planu bazy — podział grupowy po artyście, podział
chronologiczny, kontrprzykłady. Popołudnie: dokończenie biblioteki wektorów
(stan 1660 z 1912). Codzienna walka: **492 przykłady uczące, nie 40 tysięcy.**

**Inżynier danych.** Rano: czy nocne pobierania przeszły, czy źródło nie
zmieniło formatu. Pierwsze trzy tygodnie: fazy 0-3 planu bazy, których nikt nie
zaczął. Potem na stałe: podnoszenie liczby 492. Robota, która stoi: 59 artystów
z line-upów bez miksu, 182 z 1459 artystów z trzema podcastami.

**Inżynier produktu.** Rano: zgłoszenia od DJ-ów testujących (na razie od
jednego). Dzień: cztery dokumenty projektowe z 11 sierpnia leżą gotowe
i nietknięte; plus zamiana ręcznej podmiany cue w Rekordboksie na funkcję.
Popołudnie: wersja dla DJ-a, który nie otwiera terminala.

**Janek.** Rano: dwadzieścia minut werdyktów — **jedyne źródło prawdy
w projekcie.** Dzień: rozstrzyganie spornych; bramka korpusu stoi uśpiona od
23 lipca z powodu **sporu definicyjnego, nie technicznego**. Raz w tygodniu:
gra. Poza tym: rozmowy, których żaden z czwórki nie odbędzie.

**Rytm tygodnia:** poniedziałek 30 min — jedna liczba na osobę · codziennie —
CI zielony przed końcem dnia · środa — wspólny odsłuch, Janek rozstrzyga ·
piątek — wpis do ledgera.

---

## 4. Kompetencje i szwy między nimi

**Reguła:** zazębienie ma dawać **zdolność do zakwestionowania, nie do
zastąpienia**. Za płytkie — ludzie podają sobie liczby, których nie rozumieją.
Za głębokie — wszyscy w połowie kompetentni we wszystkim, nikt za nic nie
odpowiada.

### Rdzeń kompetencji

| osoba | rdzeń | rzecz nietechniczna, bez której jest bezużyteczna |
|---|---|---|
| DSP | transformata Fouriera i jej granice, obwiednie energii, HPSS, faza | **musi słyszeć** — rozpoznać ze słuchu, że wejście jest o pół taktu obok |
| ML | statystyka małej próbki, walidacja, wycieki, przeuczenie | odporność na własny wynik; najgroźniejszy jest ten, który się ucieszył |
| dane | modelowanie encji, klucze trwałe, warstwy niezmienne, pochodzenie | podejrzliwość wobec własnego zbioru |
| produkt | projektowanie interakcji, pisanie w interfejsie | ton: kumpel, nie oceniający ojciec |
| Janek | dziedzina | **czytanie liczby razem z jej niepewnością** — jedyna rzecz techniczna, którą musi opanować |

### Szwy — z nazwanym wspólnym przedmiotem

**Dźwięk ↔ ML.** Przedmiot: `src/dancelab/core/models.py`, obiekt
`AnalysisResult` — **importowany 130 razy, używany w 83 plikach.**
Obaj muszą rozumieć tak samo, że każda cecha ma pewność i że pewność nie jest
ozdobą. Zdanie przy przekazaniu: *„Ta cecha ma pewność poniżej progu w 12%
przypadków — odfiltrować czy zważyć?"* Bez tego model uczy się błędów
detektora, a błąd jest niewidoczny, bo systematyczny.

**Dane ↔ ML.** Przedmiot: definicja przykładu uczącego i jego waga. `pewnosc:
"link"` kontra `"tytuł+rok"` to nie metadana, tylko **waga liczbowa** (1,0 /
0,4 / 0,0). Zdanie: *„Ten podział ma tego samego artystę po obu stronach?"*

**Dane ↔ dźwięk.** Przedmiot: tożsamość pliku. Łączenie po nazwie w NFC, nigdy
po ścieżce. Korpus **gubi szwy** — dopasowanie odcina strefę nakładania, więc
z 23 tysięcy zostaje 49 użytecznych; raz to skaziło wagi. Zdanie: *„Ile z tych
wierszy ma pewny adres nagrania, a ile tylko tytuł?"*

**Produkt ↔ trzej pozostali.** Przedmiot: lista liczb, które wolno pokazać.
**Pusta kolumna znaczy „nie wiem", nie „nie".** Interfejs pokazujący zero tam,
gdzie brakuje pomiaru, kłamie tak samo mocno jak liczba zmyślona. Zdanie: *„Co
ta liczba znaczy dla DJ-a o czwartej rano?"*

**Janek ↔ wszyscy.** Przedmiot: werdykt. Jego „nie podoba mi się" jest
**danymi**, nie humorem — ich robota to zamienić to w mierzalną cechę (tak
powstała reguła wejścia). Ale jeśli powie „nie" bez powodu, **zgadną powód —
i zgadną źle**.

### Trzy przedmioty trzymające to razem

`core/models.py` — kto go zmienia, zmienia **przy drugiej osobie**; to jedyna
reguła procesu, jakiej bym bronił przy czterech osobach. Zestaw testów (115
plików) — tu spory się kończą: nie „mnie się wydaje", tylko „napisz test".
`PROJECT_LEDGER.md` — szew w czasie; wpis „to obaliliśmy" oszczędza tydzień,
którego nikt nie zauważy, że nie stracił.

### Zdanie na ścianę

W miksie szew działa, bo dwa utwory dzielą **coś mierzalnego** — nie dlatego,
że pasują klimatem. W zespole tak samo. Ludzie mówiący tym samym żargonem, ale
niepatrzący w ten sam plik, dogadują się **pozornie** — i to wychodzi dopiero
po trzech miesiącach.

---

## 5. Dowody z rynku pracy

Sprawdzone **2026-08-17**. Ogłoszenia wygasają — stąd data przy każdym.

### Zastrzeżenie o metodzie

Cztery ogłoszenia Apple, które wyszukiwarka pokazała jako trafiające idealnie
(*Machine Learning Researcher — Music Intelligence*, *Machine Learning/DSP
Engineer*, dwa razy *Data Engineering Software Engineer*), **są już wygaszone**
— strony zwracają „this role does not exist or is no longer available".
Rozdzielam więc potwierdzone na żywo od cytatów z indeksu wyszukiwarki.

### Potwierdzone na żywo

**Apple Music: 198 otwartych ról** pod filtrem `product=apple-music-APPMU`.

> **Senior Machine Learning Engineer — Music Recommendation Engine**
> Londyn · Machine Learning and AI · 200656273-2114 · 09.06.2026
>
> *„The Music ML team within Apple Services Engineering is responsible for
> personalisation and recommendation in Apple Music… these teams remain small,
> nimble, and cross-functional."*

Ostatnie zdanie jest podpisem Apple pod rozdziałem 2: **zespoły są małe
i przekrojowe.**

Inne żywe role Apple Music istotne dla nas: *Applied AI & Data Engineer*
(200677759), *Software Development Engineer — Data* (200667248), *Machine
Learning Scientist — ASE GenAI & ML Frameworks* (200653268).

### Cytaty z ogłoszeń już wygaszonych

**Apple, Music Intelligence:** rola to *„rozwijać i wdrażać algorytmy
rozumienia dźwięku, metadanych, tekstów i zachowań użytkownika, aby
reprezentować, wyszukiwać, kategoryzować i opisywać muzykę"* — czyli nasze role
1 i 2 w jednym etacie.

**Apple, ML/DSP Engineer:** wymagał *„dogłębnej wiedzy z Audio DSP oraz
teoretycznej i praktycznej znajomości technik uczenia maszynowego"*.

### Widełki — kotwica kosztowa (Spotify, jawne)

```
ML Engineer, Music Promotion        170 000 – 212 000 USD + akcje
ML Engineer, Personalization        148 901 – 212 716 USD + akcje
Senior Staff ML Engineer            264 641 – 378 058 USD + akcje
```

**Tidal** (Block): 5+ lat doświadczenia, Apache Spark, AWS, zespół
personalizacji. **Deezer Research**: *„analiza muzyki, wyszukiwanie informacji,
uczenie maszynowe i rekomendacja"* — ale **zero otwartych rekrutacji**
(sprawdzone przez API SmartRecruiters, `totalFound: 0`). **AlphaTheta** (Pioneer
DJ, rekordbox): **nie publikuje ogłoszeń w ogóle**, rekrutacja mailem na
`support.vacancy@pioneerdj.com`.

### Odkrycie, którego się nie spodziewałem

**Żadna z pięciu firm nie zatrudnia na to, co robi DanceLab.**

Wszystkie zatrudniają na **rekomendację** — co zagrać następne **słuchaczowi**.
Apple: „reprezentować, wyszukiwać, kategoryzować, opisywać". Spotify:
personalizacja i content understanding. Tidal: personalizacja. Deezer:
rekomendacja.

**Nikt nie zatrudnia na przejście** — na to, jak dostać się z A do B ręką
człowieka, na sprzęcie, przed ludźmi.

To nie przypadek, tylko model biznesowy: streaming zarabia na **następnym
odtworzeniu**, więc płaci za rozumienie muzyki jako **katalogu**. Szew nie ma
tam funkcji, bo nikt nie płaci za to, co dzieje się *między* utworami. Jedyna
firma z powodem — AlphaTheta — nie ogłasza się publicznie.

**Konsekwencje, obie ważne:**

* Inżyniera dźwięku **nie kupimy gotowego** — rynek go nie kształci. Trzeba
  wziąć kogoś od DSP z rekomendacji i nauczyć dziedziny: wdrożenie rośnie
  z trzech miesięcy do sześciu i o tyle trzeba przesunąć plan.
* **Jesteśmy jedyni, którzy zbierają dane o szwie.** Gdyby ta kompetencja była
  rozpowszechniona, 492 zmierzone szwy byłyby śmieszne. Skoro nie jest — to
  najlepszy zbiór tego typu, jaki ktokolwiek ma, bo nikt inny go nie buduje.

Dla zgłoszenia do Apple Music jest to gotowa teza: **oni zatrudniają ludzi od
opisywania muzyki, my przychodzimy z jedynym zbiorem o tym, co muzyka robi
w ruchu.**

---

## 6. Wdrożenie — co dostaje każda osoba pierwszego dnia

Repo jest w lepszym stanie, niż zakładałam. `docs/README.md` **już jest
kuratorowanym punktem wejścia** i już oddziela dokumentację aktualną od
historycznej. Wszystkie **117 śledzonych plików z `experiments_priv/` jedzie
razem z klonem** (`docs/` ma 131). Wdrożenie to więc **kuratorstwo, nie pisanie
od zera**.

### Dzień pierwszy, rano — to samo dla całej czwórki, dwie godziny

1. **Uruchom, zanim przeczytasz.** `README.md` → *Quickstart: See It Work In
   Ten Minutes*. Jeśli komuś nie ruszy — dzień pierwszy jest o tym.
2. `CONTRIBUTING.md` → *„Two rules that are not negotiable"*.
3. `docs/DECISIONS.md` — sześć ADR-ów, szczególnie **ADR-005: silnik nigdy nie
   fabrykuje wyniku.** Kto tego nie kupuje, nie powinien tu pracować.
4. `docs/architecture.md`.
5. `src/dancelab/core/models.py` — **wszyscy czterej tego samego ranka**, żeby
   mieli w głowie ten sam obiekt.
6. **Godzina przy sprzęcie z Jankiem.** Bez slajdów. Jedyna część, której nie
   da się dostarczyć plikiem.

### Ścieżki na osobę + zadanie pierwszego tygodnia

**Dźwięk:** `docs/TEMPO_VALIDATION.md`, `docs/formulas.md` ·
`core/rigid_grid.py`, `tempo_refine.py`, `phrasing.py` · `features/`,
`preprocessing/`, `stems/` · `tests/test_beatgrid.py`.
**Zadanie:** dziesięć utworów, które Janek zna na pamięć — znaleźć te,
w których silnik się myli, i **wyjaśnić dlaczego**. Nie poprawić.
*Kto powie „wszystko wygląda dobrze", nie słucha.*

**ML:** `LEJEK_SZWOW.md` (**czytać pierwsze**) · `CORPUS_ORDERING_DATASET_V1.md`,
`EVALUATION.md` · `RAVEFORM_PRIORS.md`, `corpus_predictions.md` · `decision/` ·
`experiments_priv/2026-08-10_ksztalt_setu`, `2026-08-11_ablacja`.
**Zadanie:** **odtworzyć** wynik wag z korpusu (24,3% / 20,7% / 18%). Nie
ulepszyć. Jeśli nie umie odtworzyć cudzego wyniku z zapisu — to problem naszej
dokumentacji i lepiej wiedzieć w pierwszym tygodniu.

**Dane:** `PLAN_BAZY.md` (**gotowy etat na miesiąc**) · `NAZEWNICTWO.md` ·
`CORPUS_RUNBOOK.md`, `CORPUS_SAVE_AND_CACHE_PROTOCOL.md` ·
`CORPUS_ETHICS.pl.md` · `ingestion/`, `storage/`.
**Zadanie:** faza 0 — zamrożenie warstwy surowej, daty pobrania w każdym
zapisie. **Kończy w trzy dni — jedyna rola oddająca działającą rzecz
w pierwszym tygodniu.** Dlatego bym ją brał pierwszą.

**Produkt:** `PRODUCT_SPEC.md` (40 KB) · `ux-pierwszego-grania.md` ·
`TUI_MAPA.md` · `README.md` → *Honesty Boundaries* · `tui/`.
**Ostrzeżenie do powiedzenia na głos:** `SIMPLE_MODE_DESIGN_SYSTEM.md` (33 KB)
i wszystkie `TERRAIN_*` to **historia, nie plan**.
**Zadanie:** trzydzieści minut obok Janka, **nic nie mówi**, zapisuje każde
zawahanie.

---

## 7. Cztery braki — do odhaczenia przed pierwszym dniem

- [ ] **Pęknięcie językowe.** Dokumentacja techniczna po angielsku (README,
      CONTRIBUTING, architecture, DECISIONS, PRODUCT_SPEC — **zero** polskich
      słów), a `PROJECT_LEDGER.md` (326 KB) i cała warstwa badawcza po polsku
      (231 trafień). Osoba nieznająca polskiego dostaje kod i **traci
      „dlaczego"**. Decyzja do podjęcia teraz: albo rekrutacja wyłącznie po
      polsku, albo ktoś tłumaczy ledger. Trzeciej drogi nie ma.

- [ ] **Nie ma dokumentu „stan na dziś".** Najnowszy `RAPORT_STANU` jest
      z 2 sierpnia — **piętnaście dni stary**, sprzed mapy DJ-ów, sprzed
      kształtu setu, sprzed warstwy kuratorskiej.

- [ ] **Ledger ma 326 KB** — bezcenny i nieczytalny jako materiał wprowadzający.
      Potrzebuje wyciągu: dwadzieścia wpisów, które trzeba znać.

- [ ] **Nie ma listy rzeczy obalonych.** Ślepe wykrywanie szwów nie działa
      (F1 0,26), łuk „build" gorszy od płaskiej linii, bloków nie ma. Bez tej
      listy każda nowa osoba **powtórzy te eksperymenty** — i będzie miała
      rację, że próbuje, bo skąd ma wiedzieć. **Najtańszy punkt z czterech:
      jedna strona, pół godziny, oszczędza każdemu po kilka tygodni.**

---

## 8. Czego ten dokument NIE rozstrzyga

**Czy w ogóle zatrudniać.** Cały rozdział 2 opisuje zespół przy założeniu, że
istnieje termin wobec kogoś z zewnątrz. Takiego terminu dziś nie ma.

**Widełek dla polskiego rynku.** Podane liczby są amerykańskie (Spotify) i nie
przenoszą się wprost.

**Formy zatrudnienia.** Etat, kontrakt, udziały — nie ruszane.

**Czy DanceLab Pro ma być firmą.** Osobny wątek, otwarty i nierozstrzygnięty.
