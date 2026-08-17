## Skąd wzięły się wagi — odpowiedź krótka

Żadna z czterech wag wzoru `0,35 · harmonia + 0,25 · tempo + 0,20 · energia + 0,20 · mixability` **nie została zmierzona**. Plik wag mówi to o sobie sam, w trzeciej linii: `configs/descriptor_weights.yaml:3` — „Initial values are uniform-ish priors; they MUST be tuned against the annotated dataset (…) before any claim of correctness". Jedyne uzasadnienie 0,35 przy harmonii to zdanie w komentarzu (`configs/descriptor_weights.yaml:82`): „key clash is the most audible set-flow error" — twierdzenie domenowe, nie pomiar.

Zmierzone są natomiast **dwie rzeczy, które siedzą POZA tym wzorem** i modyfikują go mocniej niż on sam: waga brzmienia 0,60 i priory z korpusu. I to jest pierwsza asymetria tego przekroju: wzór, który jest wizytówką projektu, ma najsłabszą proweniencję ze wszystkiego, co go dotyka.

Wszystkie liczby oznaczone **[mój pomiar]** policzyłem dziś na realnej bibliotece Janka (`experiments_priv/2026-07-30_rebuild/processed`, 8261 plików analiz) prawdziwymi funkcjami silnika, nie odtworzeniem wzoru.

---

## 1. Człon harmoniczny (0,35) — najwyższa waga, najsłabsza podstawa

**Waga:** `configs/descriptor_weights.yaml:86`. Bez pomiaru.

**Oceny relacji:** `harmonic.py:25-32` — exact 1,0 / relative 0,85 / adjacent 0,85 / cautious 0,6 / **risky 0,15** / unknown 0,5. Nagłówek pliku podaje uczciwie źródło: Mixed In Key (S049) i Serato (S050), czyli **standardowa praktyka DJ-ska, nie pomiar DanceLabu**, z zastrzeżeniem C011 („zgodność Camelota wspiera decyzję, ale NIE waliduje miksu").

**I tu jest sprzeczność z własnym korpusem projektu.** `data/reports/corpus_priors/priors_v1.json` (6144 dopasowane przejścia prawdziwych DJ-ów):

| relacja | prawdziwi DJ-e | przypadek | lift |
|---|---|---|---|
| risky | **63,2%** | 69,8% | ×0,906 |
| cautious | 12,2% | 11,0% | ×1,109 |
| exact | 11,0% | 8,8% | ×1,250 |
| adjacent | 9,5% | 7,0% | ×1,357 |
| relative | 4,1% | 3,5% | ×1,171 |

Prawdziwi DJ-e robią ruch, który silnik nazywa „risky", w **prawie dwóch trzecich przejść**. Cała rozpiętość, jaką korpus przypisuje osi Camelota, to czynnik **1,50×** (od 0,906 do 1,357). Człon harmoniczny rozciąga tę samą oś na czynnik **6,7×** (0,15 vs 1,0) — i robi to z najwyższą wagą w silniku. Silnik karze więc ruch harmoniczny **ok. 4,5 razy ostrzej, niż uzasadnia to jego własny pomiar**. Priory tego nie odkręcają, bo mnożą CAŁĄ ocenę, a nie ten jeden składnik.

Uczciwe zastrzeżenie do mojego zarzutu: kubełek „risky" w tej taksonomii to worek na wszystko, co nie jest exact/relative/±1/±2, więc 63,2% częściowo odzwierciedla zgrubność podziału, a nie odwagę DJ-ów. Ale kierunek wniosku to nie zmienia.

**Jedna rzecz jest tu wzorowa** — naprawa niesymetrii ±2 (`harmonic.py:73-80`): stary warunek `(nb−na)%12==2` łapał tylko ruch w górę, więc 8A→6A dostawało 0,15, a 6A→8A 0,60. Komentarz nazywa to wprost „nieudokumentowaną niesymetrią w składniku o najwyższej wadze".

### Tonacje: skąd naprawdę pochodzą (pytanie kluczowe)

**[mój pomiar]** Skład 8260 analiz z tonacją w bibliotece roboczej:

| źródło | ile | pewność |
|---|---|---|
| Rekordbox (7910 strumieni Apple Music + 77 lokalnych) | **7987 = 96,7%** | **1,0 wpisane na sztywno** |
| nasz detektor (248 lokalnych + 25 innych) | 273 = 3,3% | **mediana 0,290** |

Rozkład pewności naszego detektora: **28% poniżej 0,15**, **51% poniżej 0,30**, p10 = 0,034.

To ma trzy konsekwencje, których nie widać z kodu:

**(a) Mechanizm pewności jest w praktyce martwy.** `harmonic.py:125` liczy `score = base_score · conf_min + 0,5 · (1 − conf_min)` — czyli niepewna tonacja ma ściągać ocenę do neutralnej. Przy 96,7% biblioteki z pewnością 1,0 to tłumienie **nigdy się nie odpala**. Ta 1,0 nie jest pomiarem: `analysis_enrichment.py:227` i `rekordbox_import.py:213` wpisują ją „wg ustalonej konwencji zaufanego źródła". Sama konwencja jest obroniona pomiarem (`analysis_enrichment.py:200`: nasz detektor trafia w werdykt Rekordboxa w **47%** na 191 wspólnych utworach) — ale ten pomiar mówi, że NASZ detektor jest słaby, a nie że Rekordbox ma rację. Rekordbox jest tu użyty jako prawda, choć w module walidacji tempa ten sam program jest jawnie nazwany „referencją operacyjną, nie prawdą naukową" (`validation/tempo/benchmark.py:276`).

**(b) Dla 96% biblioteki nikt nigdy nie sprawdził tej tonacji.** 47% zgodności zmierzono na 191 plikach LOKALNYCH — bo `load_rekordbox_key_map` (`analysis_enrichment.py:184`) bierze tylko wiersze ze ścieżką zaczynającą się od „/". Tonacje 7910 strumieni Apple Music nie były porównane z niczym.

**(c) Dwie drogi produktowe mają różne tonacje.** TUI dokarmia tonacje z Rekordboxa przed budową (`tui/app.py:3111`). Droga CLI i API — `build_smart_playlist_from_folder` — **nie**: dokarmia wyłącznie wektory brzmienia i gatunki (`workflows/smart_playlist.py:588-594`). Czyli `dancelab zagraj <folder>` i endpoint `/sets/smart-playlist` liczą człon o wadze 0,35 na tonacjach z detektora o medianie pewności 0,29, podczas gdy ten sam set zbudowany w TUI stoi na tonacjach Rekordboxa. Nigdzie tego nie widać ani nie ostrzega.

**Drobiazg:** `camelot_number` i `camelot_mode` są tylko ZAPISYWANE (3 miejsca), nigdy nie czytane — `harmonic.parse_camelot` parsuje z tekstu `key_estimate`. Detektor ich nie wypełnia (273 utwory), i nic z tego nie wynika.

**Ryzyko utajone, zmierzone:** `rekordbox_import.py:238` buduje mapę tonacji **bez sprawdzenia formatu** (bliźniacza funkcja `analysis_enrichment.py:185` sprawdza). Gdyby Rekordbox był ustawiony na notację klasyczną, 7910 utworów dostałoby `key_estimate="Am"` z pewnością 1,0, relacja wyszłaby „unknown" (0,5), a mixability liczyłaby ten składnik jako DOSTĘPNY. **[mój pomiar, odczyt na żywej master.db]**: wszystkie 24 wiersze `DjmdKey` u Janka są w Camelocie, więc dziś ryzyko śpi. Ale śpi przez ustawienie w cudzym programie, nie przez kod.

---

## 2. Człon tempa (0,25) — jedyna waga z jakąkolwiek kalibracją na uchu

**Waga 0,25:** `configs/descriptor_weights.yaml:87`. Bez pomiaru.

**Kształt funkcji:** `set_builder.py:497` → `_common.tempo_proximity_score`, tolerancja 6%, składanie oktaw (×1, ×2, ÷2).

**Jedyna liczba w całym wzorze z jakimkolwiek dowodem to `SAME_OCTAVE_PREFERENCE = 0,9`** (`set_builder.py:478-484`), i komentarz jest wzorowy, bo podaje też **dlaczego dowód jest cienki**: korpus 6142 sąsiadujących par pokazuje 99,1% przejść w tej samej oktawie, a przemiatanie tej wagi podnosiło korelację rangową z ocenami Janka z 0,272 do 0,344 monotonicznie — ale „thin leverage (2/35 pairs crossed octaves, both rated 1/5)". Dwie pary z 35. Autor sam to zapisał i sam kazał wrócić do tego przy badaniu pięciu oceniających.

**Wiarygodność wejścia. [mój pomiar]:** 96% tempa w bibliotece nie pochodzi z naszej siatki, tylko wprost z Rekordboxa (`rekordbox_import.py:184`, `BPM/100`). To praktycznie unieważnia w produkcie znaną wadę podwajania wolnych tempo z `core/rigid_grid.py:190-195` (zmierzone: 38,3% płyt o prawdziwym tempie 80–99 wracało podwojonych) — ta wada dotyka dziś tylko ~4% biblioteki. Dobra wiadomość, ale ubocznie znaczy, że dwa najcięższe wejścia do wzoru (tonacja i tempo) to w 96% werdykt cudzego programu.

**Dług:** `mixability.py:47` używa własnej tolerancji `_BPM_TOLERANCE = 0,08` i **nie korzysta** ze wspólnego modułu `_common.py`, mimo że nagłówek `_common.py:3-8` deklaruje ujednolicenie „wszędzie" (AUD-M8). Ten sam odstęp tempa dostaje więc dwie różne oceny w zależności od tego, która warstwa pyta — a obie trafiają do jednej sumy.

---

## 3. Człon energii (0,20) — w domyślnej konfiguracji jest stałą

**Waga 0,20:** `configs/descriptor_weights.yaml:88`.

`_energy_score` (`set_builder.py:516-533`) przy `arc="off"` — a to jest **domyślne od 11.08** (`set_builder.py:1206`) — zwraca **stałe 1,0**. Powód jest zmierzony i to jedna z lepszych decyzji w projekcie: rampa „build" opisywała prawdziwe sety gorzej niż płaska linia, a realne sety mają medianę 5 spadków energii powyżej 8%.

Ale skutek arytmetyczny nie jest nigdzie zapisany: **do każdej oceny dodawana jest stała 0,20**. Rdzeń nie może więc zejść poniżej 0,20 ani różnicować w tym zakresie — cała rozróżnialność mieszka w pozostałych 0,80 skali, po czym jest jeszcze mnożona przez 0,4 przy domieszce brzmienia. To nie jest błąd, ale to jest 20% wzoru, które nie niesie informacji, i nie ma na to komentarza.

**Wiarygodność wejścia. [mój pomiar]** — tu jest rzecz, której chyba nikt nie zauważył. `track_energy` (`set_builder.py:510`) to średnia z pola `rms`. W bibliotece to pole ma **dwa różne znaczenia**:
- 98% analiz (strumienie): `rms` to **wysokość słupka fali Pioneera podzielona przez 31** (`rekordbox_import.py:110`) — wielkość wyświetlaniowa,
- 2% analiz (pliki lokalne): `rms` to nasze prawdziwe RMS z audio.

Sprawdziłem rozkłady: lokalne mediana 0,2888 (p10 0,186 / p90 0,507), strumienie mediana 0,2658 (p10 0,117 / p90 0,446). **Zakresy się pokrywają**, więc dziś to ryzyko utajone, a nie udowodnione zafałszowanie — i tak to zgłaszam. Ale to są dwie różne wielkości fizyczne w jednym polu, bez ani jednego komentarza o tym, a `energy_fit` w mixability (`mixability.py:145-149`) porównuje je wprost jako to samo.

**[mój pomiar]** Tylko **4 z 200** losowych analiz mają komplet cech; 98% ma wyłącznie `rms` i `timestamp_sec`.

---

## 4. Człon mixability (0,20) — 47% jego własnej wagi to stała 0,5

**Waga 0,20:** `configs/descriptor_weights.yaml:89`. Wagi wewnętrzne (`:60-68`) sumują się do 1,0, opisane jako hotfix Sprintu 5.1, z regułą „harmonia ważna, ale nie może dominować". Bez pomiaru.

**[mój pomiar] na 1491 realnych parach, ścieżką `build_set` (bez okien przejść):** mediana `confidence` = 0,36, a `confidence = coverage · 0,8` (`mixability.py:422`), czyli dostępne są **dokładnie 4 z 9 składników**. Brakujące w **100% par**: phrase (0,13), bass (0,13), vocal (0,08), tension (0,08), context (0,05) — razem **0,47 wagi przypięte na sztywno do 0,5**. Zostaje: tempo 0,17, energia 0,13, harmonia 0,15, styl 0,08.

Skutek widać w rozkładzie: mixability daje **0,304–0,761, mediana 0,480** — składnik o wadze 0,20 porusza się w niecałej połowie swojej skali, a połowa tego ruchu to arytmetyczna stała.

Do tego **podwójne liczenie**: mixability liczy jeszcze raz harmonię (0,15) i tempo (0,17) — innymi wzorami. Realny udział harmonii to 0,35 + 0,20·0,15 = **0,38**, tempa 0,25 + 0,20·0,17 = **0,284**. Nagłówek pliku prezentuje te wagi jako rozłączne. Co więcej, wewnętrzna harmonia ma parametr `exposure` liczony z gęstości wokalu (`mixability.py:355-360`), a `vocal_density_proxy` brakuje w 98% biblioteki — więc `exposure` to zawsze `None` → neutralne 0,5.

---

## 5. Priory z korpusu — najlepiej udokumentowana liczba w całym wzorze, w najgorszym miejscu

**Waga:** `corpus_priors_weight: 1.0` (`configs/descriptor_weights.yaml:110`), wykładnik siły. Dowód jest realny i sprawdzalny: 6144 dopasowane przejścia prawdziwych DJ-ów wobec bazy losowej **w tym samym miksie** (`priors_v1.json`). To jest porządna konstrukcja pomiarowa.

Kontrakt uczciwości też jest wzorowy (`corpus_priors.py:8-15`): brak pliku albo brak wejścia = neutralne 1,0 z notatką, nigdy zgadywanie; wykładnik żyje w pliku wag, żeby był wersjonowany razem z nimi.

**Zmierzone mnożniki** (policzone z pliku): harmonia — exact ×1,25, adjacent ×1,357, relative ×1,171, cautious ×1,109, risky ×0,906; tempo — 0–2% ×1,219, 2–4% ×0,906, 4–6% ×0,986, 6–10% ×0,843, >10% ×0,503. Iloczyn od **0,455** (risky + skok >10%) do **1,654** (adjacent + 0–2%).

**Trzy problemy z tym, JAK to jest użyte:**

1. **Kolejność.** Priory zmierzono na dwóch wymiarach (relacja Camelota, odstęp tempa), a mnożą to, co zostało **po** wmieszaniu kosinusa CLAP-a (`set_builder.py:806-823`). Mnożnik zmierzony na jednej rzeczy jest nakładany na inną. Nie jest to samo w sobie błędne, ale nie jest nigdzie uzasadnione ani przetestowane.

2. **Ten mnożnik rozsadza sufit skali** — patrz sekcja 7, to jest najważniejsze ustalenie tego przekroju.

3. **Nie ma testu na ścieżce produktowej.** `grep` po testach nie znajduje wywołania `transition_prior_lift` w kontekście `set_buildera`, a mnożnik potrafi zmienić ocenę o połowę.

---

## 6. Sito brzmienia i waga 0,60 — pomiar jest, ale wejścia brakuje dla 80% biblioteki

**Waga 0,60** (`configs/descriptor_weights.yaml:113-117`, `sound_affinity.py`) jest **jedyną wagą we wzorze z pełnym, zapisanym pomiarem**: 45 miksów korpusu, kryterium „dolna tercja DJ-ów", nieprzewidywalni 0,6826 → 0,7537 (+0,071), środek +0,039, zachowawczy +0,036. Komentarz zapisuje też **znany limit**: na setach samego Janka ten sam składnik dał **−0,008**. Wzorcowa notatka.

`sito_brzmienia.py:18-29` zawiera diagnozę, którą uważam za najlepszy fragment analityczny w tym repozytorium: utwór bez wektora nie dostawał ŻADNEJ korekty, więc zostawał przy rdzeniu (często 1,000), podczas gdy każdy oceniony był ściągany w dół — i „utwory niemożliwe do oceny systematycznie WYGRYWAŁY", z nazwiskami (Farsight 100%, K-LONE 100%, HAAi 71%).

**[mój pomiar] — ta diagnoza jest dziś nadal aktualna i skala jest większa, niż mówi notatka:**

- katalog wektorów: **1709** (296 z plików + 1413 z 30-sekundowych próbek); biblioteka: 8261 analiz → pokrycie **~19%** (próbka 1500: 295 z wektorem);
- rozkład afinicji CLAP na 4000 par: mediana **0,835**, p90 0,916, **powyżej 0,96 tylko 0,30% par**;
- ponieważ mieszanie jest wypukłe (`sound_affinity.py:56`), kandydat z wektorem bije równorzędnego kandydata bez wektora **dokładnie wtedy, gdy afinicja > rdzeń**. To jest cały mechanizm, w jednym zdaniu.

Konsekwencja: **kierunek błędu zależy od poziomu rdzenia i nikt tego nie zapisał.** W puli, gdzie rdzeń jest niski, brzmienie PODNOSI utwory z wektorem (w moim losowym kroku wygrywały w 40–45% przy bazie 19%). W reżimie, w którym silnik naprawdę pracuje — `premia_gatunku.py:81` podaje zmierzoną średnią ocenę szwu w puli Janka jako **0,96** — sytuacja się odwraca i utwór z wektorem **praktycznie nie ma jak wygrać**, bo mniej niż jedna trzysetna par osiąga afinicję powyżej 0,96.

Bez kotwicy (`--jak`) sito nie działa w ogóle, więc na zwykłej budowie problem stoi nietknięty — dla 80% biblioteki, nie dla kilku DJ-ów.

**Poza kontraktem uczciwości:** `configs/formula_terms.yaml` ma wpisy dla wszystkich składników mixability, set_buildera i sekwencji, ale **nie ma ani jednego wpisu dla `sound_affinity` ani `corpus_prior`**. Testy `tests/test_quickwins.py:120-145` pilnują wyłącznie krotek `COMPONENTS`, a te dwa modyfikatory nie są składnikami — więc dwie największe siły w domyślnej ocenie są jedynymi, które wymknęły się regule „żadnych anonimowych zmiennych".

---

## 7. Ustalenie najważniejsze: przy tej bibliotece wzór przestaje różnicować dokładnie w punkcie decyzji

**[mój pomiar, prawdziwą funkcją `SB.transition_score`, tryb smart, arc="off", pula 500 utworów z realnej biblioteki, kandydaci w paśmie ±6% tempa, mediana 148 kandydatów na krok]:**

> W **30 krokach na 30** na suficie 1,000 stoi więcej niż jeden kandydat. **Mediana 38 kandydatów remisuje z oceną dokładnie 1,000**, maksimum 88.

Mechanizm: `set_builder.py:823` liczy `score = min(1,0; max(0,0; score · lift))`. Rdzeń ma podłogę 0,20 (stała energia), w paśmie tempa mediana rdzenia to 0,595 a p90 0,832, a lift sięga 1,654 — więc **18% par w paśmie przekracza 1,0 jeszcze przed obcięciem** (rozkład przed obcięciem: mediana 0,652, p90 1,044, maksimum 1,482).

Rozstrzygnięcie remisu: `set_builder.py:1010`, `scored.sort(key=lambda item: (-item[0], item[1]))` — czyli **alfabetycznie po `track_id`**, a `track_id` to skrót ze ścieżki pliku. Świeżość (losowe rozstrzyganie remisów) jest domyślnie wyłączona.

Innymi słowy: w domyślnej konfiguracji, na prawdziwej bibliotece Janka, o tym, który utwór zagra jako następny, w typowym kroku decyduje **nazwa pliku wybrana spośród ~38 remisujących kandydatów**, a nie 0,35 harmonii, 0,25 tempa, 0,20 energii i 0,20 mixability.

**Projekt to już raz odkrył — i załatał obok, zamiast u źródła.** `premia_gatunku.py:76-83`: „zmierzona średnia ocena szwu w jego puli to 0,96, więc premia wpadała w sufit i remis rozstrzygała nazwa pliku" — dlatego premia za gatunek świadomie NIE jest przycinana do 1,0. To trafna diagnoza tego samego zjawiska, ale zastosowana tylko do premii i tylko wtedy, gdy DJ poda brief gatunkowy. Sam sufit `transition_score` został nietknięty.

---

## 8. Jedyna walidacja tego wzoru na uchu DJ-a

**[mój pomiar, uruchomiłem `build_benchmark_summary` na faktycznej pamięci walidacji]:**

- łącznie: n = 48 ocen, Pearson **r = 0,184**, Spearman 0,274, Kendall τ-b 0,204;
- sesja Janka: n = 36, r = 0,302, **0 ocen w ciemno**;
- sesja anonimowa: n = 12, r = **−0,064**, z czego 8 w ciemno (przy n = 12 to nie jest wynik, tylko brak wyniku — nie wolno tego cytować w żadną stronę);
- bramka mówi poprawnie: 2 sesje z 5, brakuje 4 do progu strojenia (`dj_benchmark.py:24-25`).

Trzy fałszywe trafienia z sesji Janka (ocena silnika ≥0,70, ocena DJ-a ≤2) są pouczające: dwa dotyczą **duplikatów i utworów z tej samej płyty**, jeden „zabija cały klimat". Żadnego z nich nie łapie oś harmonia/tempo/energia.

---

## Podsumowanie: proweniencja członów, od najmocniejszej do najsłabszej

| element | waga | skąd | dowód w komentarzu | wejście wiarygodne? |
|---|---|---|---|---|
| brzmienie CLAP | 0,60 | 45 miksów korpusu, dolna tercja | **tak, z limitem** (−0,008 u Janka) | **nie** — pokrycie 19% biblioteki |
| priory korpusu | ×0,455–1,654 | 6144 przejścia vs baza losowa | **tak** | tak, ale nakładane po domieszce brzmienia i rozsadzają sufit |
| oktawa tempa (0,9) | wewnątrz 0,25 | 6142 pary + 35 ocen Janka | **tak, z jawnym „cienka dźwignia"** | tak (tempo z RB) |
| tempo | 0,25 | brak pomiaru | nie | tak (96% z Rekordboxa) |
| harmonia | 0,35 | brak pomiaru; źródło = MIK/Serato | nie — twierdzenie, nie liczba | **wątpliwe**: 96,7% tonacji to werdykt RB z pewnością wpisaną na sztywno; 3,3% z detektora o medianie pewności 0,29 i 47% zgodności |
| mixability | 0,20 | brak pomiaru | nie | **nie** — 4 z 9 składników, 0,47 wagi to stała 0,5 |
| energia | 0,20 | brak pomiaru | powód wyłączenia — tak; skutek arytmetyczny — nie | nieistotne (stała 1,0), ale samo pole `rms` miesza dwie różne wielkości |

## Cztery rzeczy, które sprawdziłbym najpierw

1. **Sufit skali.** Zmierzyć, ile kroków budowy kończy się remisem po alfabecie — na prawdziwej puli i prawdziwym briefie, nie na mojej symulacji. Jeśli potwierdzi się rząd 38 remisów, to każda dyskusja o wagach jest przedwczesna, bo wagi i tak nie docierają do decyzji.
2. **Klucz do klucza.** 96,7% tonacji nigdy nie było z niczym porównane. Minimum: policzyć rozkład relacji harmonicznych realnych setów Janka na tonacjach z RB i sprawdzić, czy człon 0,35 w ogóle je opisuje. Korpus już sugeruje, że nie (63,2% „risky").
3. **Dwie drogi produktowe, dwie różne tonacje.** Albo dopiąć `attach_rekordbox_keys` do `build_smart_playlist_from_folder`, albo dopisać ostrzeżenie — dziś CLI i API budują set o wadze 0,35 na tonacjach z pewnością 0,29 i nikt się o tym nie dowiaduje.
4. **Wpisać `sound_affinity` i `corpus_prior` do `formula_terms.yaml`** i objąć je testem. To dwie najsilniejsze rzeczy w domyślnej ocenie i jedyne, które umknęły własnej regule projektu.