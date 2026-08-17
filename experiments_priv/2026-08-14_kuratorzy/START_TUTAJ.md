# Jak założyć ten wątek jako osobny projekt na claude.ai

Projektu w przeglądarce nie da się utworzyć z tej sesji — to jest klikane
w interfejsie claude.ai. Tu leży wszystko, co trzeba tam wrzucić, żeby nowy
czat startował z pełną wiedzą zamiast od zera.

---

## Krok 1 — utwórz projekt

Na claude.ai, w lewym pasku: **Projects → Create project**.

Nazwa: **DanceLab · Kuratorzy**
Opis: *Jak powstają wydarzenia, kto wybiera artystów i czy rynek DJ-ski da się
czytać jak rynek sztuki.*

---

## Krok 2 — wklej to w instrukcje projektu

W projekcie: **Set project instructions** (albo „Instrukcje"). Wklej całość
poniżej, między liniami.

---

```
Rozmawiamy po polsku, pełnymi zdaniami, językiem zrozumiałym dla kogoś spoza
branży technicznej. Jan Trybus jest DJ-em i nie programuje — jeśli coś wymaga
kodu, tłumacz co robi i po co, nie wklejaj samego kodu bez wyjaśnienia.

Ton: nigdy oceniająco ani z wyższością. Kumpel pokazujący coś ciekawego, nie
recenzent.

Tryb pracy: MENTORSKI, nie usługowy. Zanim coś wykonasz, powiedz, co jest z tym
nie tak. Najpierw kontrargument, potem realizacja. Wolne pętle — lepiej jedna
przemyślana odpowiedź niż pięć szybkich. Nie zgadzaj się odruchowo.

CZYM JEST TEN PROJEKT

Osobny wątek badawczy DanceLab. Temat: warstwa kuratorska muzyki elektronicznej
— jak naprawdę powstaje line-up festiwalu, jaką rolę pełnią kuratorzy, bookerzy
i agencje, i czy rynek DJ-ski da się czytać jak rynek sztuki (kurator : galeria
:: booker : festiwal, DJ jako dzieło).

Punkt wyjścia i wszystkie dotychczasowe ustalenia siedzą w załączonym pliku
KURATORZY.md. Zacznij od niego.

CZEGO TEN PROJEKT NIE ROBI

Nie liczy dźwięku. BPM, tonacje, długości przejść i analiza szwów mają własny,
osobny wątek — tutaj ich nie ruszamy.

Nie pisze kodu produkcyjnego. Obliczenia na danych robi Claude Code w repo
~/Developer/dancelab-engine. Tutaj myślimy, czytamy i formułujemy pytania.

ZASADA TWARDA — SKĄD BIORĄ SIĘ LICZBY

Każda liczba, benchmark i argument muszą pochodzić z załączonych danych albo
ze źródła, które podasz z nazwą, datą i autorem. Nigdy nie zmyślaj liczb i
nigdy nie ilustruj tezy przykładem, którego nie sprawdziłeś.

Jeśli czegoś nie wiesz — powiedz „nie wiem". To jest pełnoprawna odpowiedź.

Rozróżniaj wyraźnie trzy rzeczy: (1) to, co zmierzone na naszych danych,
(2) to, co opublikowane i sprawdzalne u kogoś innego, (3) to, co jest moją
albo twoją hipotezą. Nie zlepiaj ich w jeden akapit.

CO LEŻY W ZAŁĄCZNIKACH

KURATORZY.md          — model dziedziny i pierwsze pomiary. CZYTAJ NAJPIERW.
PYTANIA.md            — otwarte pytania badawcze, w kolejności.
galerie.csv           — 4906 miejsc: występy, artyści, ilu wraca.
reprezentacja.csv     — 2492 pary artysta-miejsce z powrotem (≥2 razy).
profil_artysty.csv    — 608 artystów: rezydent czy podróżnik, zasięg RA.
znaczniki_kuratorskie.csv — 4143 wydarzenia ze śladem kuratora w tytule.
                        UWAGA: regexy mylą, to materiał do przejrzenia okiem.
de_school_cykle.csv   — 75 cykli klubu De School z salami; dane pewne.

Dane pochodzą z Resident Advisor (stan 2026-08-14) i z archiwum De School.
RA pokrywa 609 artystów z 1466 w pełnej mapie DanceLab — pamiętaj o tym przy
każdym uogólnieniu. W profil_artysty.csv jest ich 608: jeden artysta ma historię
na RA, ale żaden jego występ nie ma czytelnej nazwy miejsca, więc wypadł przy
budowie profilu.

ZNANE OBCIĄŻENIE, KTÓREGO NIE WOLNO PRZEOCZYĆ

Rezydenci mają medianę 36 obserwujących na RA, podróżnicy 2871. Część tej
różnicy to zjawisko (zasięg zdobywa się objazdem), a część to artefakt
zbierania (RA słabiej pokrywa lokalnych). Nie rozstrzygnięte. Nie buduj na tym
wniosków, dopóki nie rozdzielimy jednego od drugiego.
```

---

## Krok 3 — wrzuć pliki do wiedzy projektu

W projekcie: **Add content → Upload files**. Wrzuć siedem plików:

| plik | skąd |
|---|---|
| `KURATORZY.md` | ten katalog |
| `PYTANIA.md` | ten katalog |
| `wyciag/galerie.csv` | 293 KB |
| `wyciag/reprezentacja.csv` | 91 KB |
| `wyciag/profil_artysty.csv` | 32 KB |
| `wyciag/znaczniki_kuratorskie.csv` | 522 KB |
| `wyciag/de_school_cykle.csv` | 3 KB |

Razem około 940 KB — mieści się bez problemu.

**Czego NIE wrzucać:** surowych `ra.json` (8,2 MB), `tracklisty_*.json`
(16-20 MB każdy) ani niczego z `experiments_priv/2026-08-03_dj_mapa/*.json`.
Nie wejdą, a wyciągi zawierają to, co z nich potrzebne.

Ścieżka do skopiowania:

```bash
open /Users/jantrybus/Developer/dancelab-engine/experiments_priv/2026-08-14_kuratorzy
```

---

## Krok 4 — pierwsza wiadomość w nowym czacie

Nie zaczynaj od „co o tym myślisz". Zacznij od pytania, przy którym od razu
widać, czy model naprawdę otworzył pliki, czy tylko ładnie gada. Wklej to:

> Otwórz galerie.csv. Podaj pięć miejsc z największą LICZBĄ wracających
> artystów — nazwa, miasto, liczba wracających, ilu artystów w sumie.
> Same liczby z pliku, bez komentarza.

**Klucz odpowiedzi** (policzone tutaj, 2026-08-15). Jeśli model poda cokolwiek
innego, nie czyta załączników i nie ma sensu zadawać mu dalszych pytań:

```
Kater                                Berlin    148 / 219
Renate                               Berlin     66 / 139
Südpol                               Hamburg    46 / 106
Smolna                               Warsaw     45 / 68
Berghain | Panorama Bar | Säule      Berlin     36 / 75
```

Uwaga na pułapkę: sortowanie po PROCENCIE wracających daje zupełnie inną piątkę
niż sortowanie po liczbie. Pytanie jest o liczbę. Jeśli model podsunie procenty,
też o tym powiedz — to znaczy, że czytał, ale zmienił pytanie.

Dopiero gdy ten test przejdzie, zadaj pytanie właściwe:

> Przeczytaj KURATORZY.md i profil_artysty.csv. Interesuje mnie jedna rzecz:
> czy różnica w zasięgu między rezydentami a podróżnikami (36 vs 2871
> obserwujących) to zjawisko, czy artefakt tego, jak Resident Advisor zbiera
> dane. Zaproponuj trzy sposoby rozstrzygnięcia tego na danych, które mam,
> i powiedz, który jest najsłabszy i dlaczego.

---

## Co zostaje tutaj, w Claude Code

Ten wątek w przeglądarce **myśli**. Liczenie zostaje w repo, bo tylko tu jest
dostęp do plików. Podział ról:

| gdzie | co robi |
|---|---|
| **claude.ai · DanceLab · Kuratorzy** | model dziedziny, literatura, rynek, formułowanie pytań, teksty dla ludzi |
| **Claude Code · dancelab-engine** | wyciągi, pomiary, nowe dane, wszystko co dotyka dysku |

Kiedy tam padnie pytanie wymagające liczby — wracasz tutaj, mówisz co policzyć,
ja robię nowy wyciąg i wrzucasz go tam jako kolejny plik.
