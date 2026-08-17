# Nazewnictwo mapy DJ-ów i setów

Ustalone 2026-08-03, po 587 wierszach — czyli w momencie, gdy migracja jest
jeszcze tania. Powód był konkretny: pole `kontekst` miało **147 różnych
wartości** (`festiwal`, `b2b/festiwal`, `festiwal/USA`, `radio/NYC`…), a w polu
`parkiet` siedziały `b2b`, `live` i `poranek`, które parkietami nie są.

Zasada nadrzędna: **jedno pole = jedno pytanie.** Jeśli wartość odpowiada na
dwa pytania naraz („b2b/festiwal"), to znaczy, że pól powinno być dwa.

---

## Pola opisujące SET

| pole | pytanie | słownik |
|---|---|---|
| `wydarzenie` | Jak nazywa się impreza lub cykl? | nazwa własna, wolny tekst |
| `typ` | Jakiego rodzaju to miejsce? | zamknięty, niżej |
| `scena` | Który parkiet? | słownik PER FESTIWAL, niżej |
| `format` | Jak grane? | zamknięty, niżej |
| `rola` | Które miejsce w programie? | zamknięty, niżej |
| `czas` | Kiedy dokładnie? | `dzień HH:MM-HH:MM`, np. `sobota 07:00-09:00` |
| `data` | Którego dnia? | `RRRR-MM-DD`, albo sam rok gdy nie wiadomo |
| `zrodlo` | Skąd ten wiersz? | `1001tracklists` \| `soundcloud` \| `youtube` |
| `pewnosc` | Czy to na pewno ten artysta? | `potwierdzone` \| `niepewne` |
| `opis` | Co artysta sam napisał pod setem? | wolny tekst, przepisany dosłownie |
| `dlugosc_min` | Ile trwa nagranie? | liczba minut |
| `konto` | Kto wrzucił? | nazwa konta — bywa kolektywem, nie artystą |
| `sasiedztwo` | Kto grał tuż przed i tuż po? | `po: X · przed: Y` |

`opis` doszedł 2026-08-14 razem z rocznikami Garbicza i jest najcenniejszym
polem w całej tabeli. Godziny, dni tygodnia i role wyciągamy właśnie z niego,
ale zostaje w całości, bo niesie też rzeczy, których nie da się wyliczyć:
pogodę, awarie sprzętu, to że set był ostatnim punktem programu.

`sasiedztwo` odpowiada na pytanie z samego środka DanceLab — **kto po kim**.
Wypełniane WYŁĄCZNIE ręcznie. Automat na wzorcu „after X" dawał 60% fałszywek
(„2 days before Garbicz.... Panic!" czytał jako sąsiada), więc na 579 opisów
zostało 7 wierszy, w których artysta napisał to wprost.

### `typ` — słownik zamknięty

```
festiwal      impreza plenerowa lub wielosceniczna
klub          lokal z parkietem
warehouse     hala, magazyn, przestrzeń tymczasowa
rave          impreza w miejscu nieoczywistym
plener        na zewnątrz, poza festiwalem (dach, plaża, góra)
radio         stacja albo audycja radiowa
studio        nagranie w studiu (HÖR, The Lab, Boiler Room bez publiczności)
podcast       cykl wydawnictwa albo medium
stream        transmisja bez publiczności
```

Kraj i miasto NIE należą do `typ`. Były wcześniej sklejane („festiwal/USA")
i przez to nie dało się policzyć, ile jest w ogóle festiwali.

### `scena` — słownik osobny dla każdego festiwalu

```
GARBICZ      Seebühne · Wiese · Wald · Lichtung · Juicy Bar · Buk Corner
             Crazy Paradise (dawniej Dickicht) · Pleasure Island · Teabar
             Ambient Floor · Loco Paraiso · Weinbar · See · Voodoohop
             Bachstelzen · Knüller · Kanton

AUDIORIVER   Circus · Park · Truly Unique · Kampus · W Punkt · Chillout
             OFF Piotrkowska · Main Stage · Plaża · Forest · SunDay
```

Słowniki są rozdzielone, bo nazwy się gryzą: „Park Stage" w Audioriver to
konkretna scena, a w Garbiczu „park" nie znaczy nic. Audioriver jest do tego
festiwalem ruchomym — do 2023 Płock, od 2024 Łódź — więc w słowniku muszą
siedzieć obie generacje nazw.

### `format` — słownik zamknięty

```
dj-set     domyślny, gdy nic nie wskazuje inaczej
live       artysta gra z instrumentów albo maszyn, nie z płyt
b2b        dwoje lub więcej na zmianę
winyl      set deklarowany jako tylko z płyt
hybryda    dj-set z elementami live
```

**Kiedy `format` zostaje PUSTY.** Słowo „live" w tytule znaczy dwie różne
rzeczy: „gram na maszynach" i „to jest nagranie z imprezy". Rozstrzyga
pozycja słowa — doklejone do nazwy artysty przed separatorem („SKINNERBOX
Live @ Garbicz") to deklaracja formatu; na początku tytułu („Live@ Garbicz
2014") opisuje nagranie. W tym drugim przypadku pole zostaje puste, bo
wpisanie `dj-set` byłoby zgadywaniem tak samo jak `live`. Dotyczy 50 wierszy.

### `rola` — słownik zamknięty

```
otwarcie        pierwszy set na scenie albo festiwalu
peak            szczyt wieczoru
zamkniecie      ostatni set sceny albo festiwalu
afterhour       po zamknięciu głównego programu
poranek         set poranny
popoludnie      set popołudniowy (afternoon, Nachmittag, day time)
wschod-slonca   deklarowany jako wschód słońca
zachod-slonca   sunset albo sundowner
noc             set nocny bez dokładniejszego określenia
all-night       jeden artysta przez całą noc
```

`popoludnie` i `zachod-slonca` dołożone 2026-08-14 przy rocznikach Garbicza —
34 sety opisane wprost tymi porami. Wciskanie ich do „noc" albo „poranek"
zmyłoby jedyną rzecz, którą te opisy niosą pewnie.

`rola` to miejsce w PROGRAMIE, `czas` to zegar. Set może mieć jedno bez
drugiego: „zamknięcie" bez godziny albo „22:00-00:00" bez roli.

---

## Pola opisujące ARTYSTĘ

| pole | uwagi |
|---|---|
| `ksywa` | dokładnie jak w line-upie festiwalu — to jest klucz łączący |
| `soundcloud` | sam uchwyt, bez `https://soundcloud.com/` |
| `apple_music` | pełny link (API zwraca pełny) |
| `kandydaci` | gdy nie wiadomo który profil — wszystkie, do rozstrzygnięcia przez DJ-a |

**`rezydencja` i `afiliacja` wypadły z arkusza 2026-08-14** (decyzja Janka).
Powód jest liczbowy: przy 1007 artystach wypełnione były 24 wiersze. Każdy
z nich wymagał osobnego wejścia na stronę klubu albo bio — jedyne pole
w całej tabeli bez źródła, które da się zaciągnąć hurtem. Kolumna, która
w 98% mówi „nie wiem", uczy ignorować całą tabelę.

Wartości nie zostały skasowane — leżą w `socials.json` pod kluczami
`rezydencja` i `afiliacja` i wrócą, gdy znajdzie się na nie sposób masowy.

---

## Czego NIE robimy

**Nie sklejamy dwóch wymiarów slashem.** `b2b/festiwal` → `format=b2b`,
`typ=festiwal`.

**Nie wpisujemy wartości spoza słownika.** Jeśli coś nie pasuje, dokładamy
pozycję do słownika w tym pliku i migrujemy istniejące wiersze — a nie
dopisujemy wariant obok.

**Nie zgadujemy.** Puste pole znaczy „nie wiem" i jest poprawną wartością
(ADR-005). `pewnosc=niepewne` znaczy „mam kandydata, ale go nie potwierdziłem".

## Podcasty i radio — osobna, mocna kategoria

Decyzja Janka 2026-08-14: podcasty (radiowe, radiowo-online, online) to
w środowisku DJ-skim osobna liga, a nie gorszy zamiennik grania. Cel:
**minimum 3 takie sety na każdego DJ-a**.

Granica, bez której ta kategoria zamienia się w śmietnik:

* **podcast, w którym DJ GRA** — „RA.1041 Chlär", „#SlamRadio 466 Chlär",
  „Dekmantel Podcast 170 – Nathan Fake". To jest set. Zbieramy;
* **audycja, w której ludzie GADAJĄ o muzyce** — „Strefa Ruchu #14:
  Audioriver, Cały Ten Rap, Denzel Curry, EURO 2024". To NIE jest set
  i nie zbieramy go w ogóle (Janek: „audycje gdzie gadają nie zbierajmy").

Zbierane po kontach CYKLI, nie artystów: set podcastowy prawie nigdy nie wisi
u artysty, tylko u serii. Jedno konto RA daje 761 odcinków, więc 30 zapytań
zastępuje 1200. Drugim przebiegiem idą konta artystów — tam leży ogon:
rezydencje w małych radiach i własne cykle.

**Nazwę cyklu odcinamy z tytułu PRZED dopasowaniem artysty.** Bez tego
„Truant: TAYSTII – Clangistan Vol. II" trafiało do artysty „Truant", a gra
tam TAYSTII.

---

**Nie przypisujemy setu do festiwalu na słowo honoru.** Ile zaufania ma opis,
zależy od tego, skąd wiersz przyszedł:

* **kolekcja kuratorowana** ręczy sama za siebie — ktoś zebrał te sety jako
  „Garbicz 2019", więc wzmianka gdziekolwiek wystarcza;
* **wyszukiwarka nie ręczy za nic** — fraza „audioriver" w opisie łapie
  odcinki podcastów, w których artysta tylko WSPOMINA, że tam grał
  („MELODIC SERIES #26", „#97 Sosia – DISCOnnect cast"). Przy tym źródle
  nazwa festiwalu musi stać w TYTULE. Ta jedna reguła odcięła 39 fałszywych
  przypisań w Audioriver.

Wiersz odcięty NIE jest kasowany — zostaje jako miks tego artysty, tylko
z pustym `wydarzenie`. Wyrzucenie go gubiłoby prawdziwy set tylko dlatego,
że zagrany gdzie indziej.


---

## Kolory

Kolor niesie znaczenie, nie ozdobę: **jedna rodzina barw = jeden wymiar**.
Nakładany jest na komórki w arkuszu `Miksy`; pełne mapowanie z opisami leży
w arkuszu `Legenda`.

### `typ` — ciepłe = z publicznością, chłodne = bez

| wartość | kolor | dlaczego tak |
|---|---|---|
| festiwal | `C6E0B4` zieleń | plener, tłum |
| plener | `E2EFDA` jasna zieleń | ta sama rodzina, mniejsza skala |
| klub | `D9C2E9` fiolet | noc, wnętrze |
| rave | `F4B8D8` magenta | miejsce nieoczywiste |
| warehouse | `D0CECE` szarość | surowa przestrzeń |
| radio | `BDD7EE` błękit | bez publiczności |
| studio | `DEEBF7` jaśniejszy błękit | ta sama rodzina |
| podcast | `D6E4F0` blady błękit | ta sama rodzina |
| stream | `EDF3F8` najbledszy | ta sama rodzina |

Podział ciepłe/chłodne nie jest estetyczny. To jest **podział, który najbardziej
zmienia sposób grania**: set do pustego studia i set do trzech tysięcy ludzi
w lesie to dwie różne czynności.

### `format` — bursztyn = człowiek robi coś więcej niż odtwarza

| wartość | kolor |
|---|---|
| dj-set | biały (domyślny, bez wyróżnienia) |
| live | `FFD966` bursztyn |
| b2b | `FFE699` jaśniejszy bursztyn |
| winyl | `E6D3B3` beż |

### `rola` — skala dobowa, od świtu do nocy

| wartość | kolor |
|---|---|
| wschod-slonca | `FFF2CC` najjaśniejszy |
| poranek | `FCE4D6` |
| otwarcie | `E2EFDA` |
| peak | `FF9999` czerwień — jedyny akcent |
| noc | `B4C7E7` |
| afterhour | `9DC3E6` |
| zamkniecie | `C9A0DC` |
| all-night | `8EA9DB` najciemniejszy |

### `zrodlo` i `pewnosc` — sygnalizacja zaufania

| wartość | kolor | znaczenie |
|---|---|---|
| 1001tracklists / potwierdzone | `C6E0B4` zielony | data i miejsce z bazy |
| soundcloud | `FFE699` bursztyn | wrzut artysty, bez metadanych |
| youtube / niepewne | `F8CBAD` / `FFD966` | wymaga oka — tam trafiały się składanki fanowskie |

Zielony–bursztyn–łosoś to celowo ta sama logika, co światła: im dalej od
zielonego, tym bardziej patrz sam.


---

## Pola pozycji w TRACKLIŚCIE

Tracklista to nie jest jedno pole miksu, tylko własna tabela — 147 964 wiersze.
Każda POZYCJA ma osobne źródło, bo pochodzą z sześciu miejsc o różnej
wiarygodności i mieszanie ich w jednej kolumnie zatarłoby całą różnicę.

| pole | pytanie | wartości |
|---|---|---|
| `poz.` | Który utwór z kolei? | liczba |
| `czas` | O której wchodzi? | `MM:SS` albo `H:MM:SS`; puste = nie wiadomo |
| `rozpoznany` | Czy ktoś wie, co to za utwór? | `nazwany` \| `ID` |
| `wykonawca utworu` | Kto to nagrał? | wolny tekst |
| `tytuł utworu` | Jak się nazywa? | wolny tekst |
| `wydawca` | Wytwórnia i numer katalogowy | tylko z MixesDB |
| `źródło pozycji` | Skąd ta pozycja? | słownik niżej |
| `pewność połączenia` | Czy to na pewno TEN set? | `link` \| `tytul+rok` \| `nowy` |

### `źródło pozycji` — słownik zamknięty

```
nts                   105 145   endpoint /tracklist, dane strukturalne
mixesdb                17 662   wiki, spisane po fakcie przez ludzi
ra podcast             17 303   spisane przez REDAKCJĘ RA
opis wrzutu             4 250   tracklista wklejona przez DJ-a pod setem
komentarz soundcloud    2 321   publiczność, przypięte do sekundy
opis hearthis           1 283   jak wyżej, inny serwis
```

**`ID` NIE JEST BRAKIEM DANYCH.** To osobna wartość, znacząca „ktoś zapytał
dokładnie tu, ale nikt nie rozpoznał". Przy znanym czasie mówi, GDZIE JEST
SZEW, nawet bez nazwy — a to jest połowa tego, po co ta baza powstała.
1937 pozycji wobec 146 027 nazwanych.

**`pewność połączenia` dotyczy SETU, nie utworu.** `link` znaczy, że po obu
stronach stoi ten sam adres SoundCloud — fakt. `tytul+rok` to poszlaka,
przyjmowana tylko gdy trafia w jeden wiersz. `nowy` znaczy, że tracklista
istnieje, ale nie wiadomo, do którego naszego setu ją doczepić.

---

## Migracja zbiorów z 2026-08-14

Pięć zbiorów zbudowanych tego dnia powstało poza konwencją i zostało do niej
sprowadzone tego samego wieczoru, po pytaniu Janka „czy wszystko otagowane,
z odpowiednim filenamingiem?".

| było | jest | dlaczego |
|---|---|---|
| `de_school.sala` | `scena` | to JEST scena wg tego słownika |
| `ra_kanon.artysta` | `ksywa` | `ksywa` jest kluczem łączącym w całej bazie |
| `ra_kanon.zrodlo` | `artykul` | `zrodlo` w bazie znaczy „skąd wiersz", nie „z którego tekstu" |
| `de_school.mixcloud` | `link` | pole `link` wszędzie znaczy „gdzie tego posłuchać" |

Do De School dołożone `typ=klub`, `format=dj-set`, `zrodlo`, `pewnosc`;
do występów RA `wydarzenie`, `zrodlo`, `pewnosc`. Bez tego nie dawały się
filtrować razem z resztą bazy, co jest jedynym powodem, dla którego ta
konwencja w ogóle istnieje.
