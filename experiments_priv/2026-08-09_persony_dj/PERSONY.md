# Persony DJ-ów do testów DanceLaba

**Data:** 2026-08-09 · **Po co:** znaleźć miejsca, w których program się łamie,
zanim znajdzie je ktoś obcy.

## Zasada, na której są zbudowane

Persony NIE są zmyślonymi ludźmi z ładnymi biografiami. Każda jest **zestawem
liczb, które łamią inny mechanizm** — dobrane z tego, co przez ostatnie dni
zmierzyliśmy jako punkty pęknięcia:

| oś | dlaczego akurat ta |
|---|---|
| pliki kontra strumienie | u Janka 1571 z 1880 pozycji to strumienie; program widział 229 utworów zamiast 1900 |
| wielkość puli | przy 7 pasujących utworach sito gatunku znika; przy 167 trzyma |
| nazewnictwo gatunków | „House" po całej nazwie to 7 utworów, po słowach było 32 |
| wektory brzmienia | bez nich kotwica nie działa, a utwory nieocenialne wygrywają domyślnie |
| DJ w księdze kotwic | mamy 284 DJ-ów; Amelie Lens, Solomun, Fisher i Michael Bibi **nie mają** wpisu |
| własne hot cue | nasz pad musi ustąpić padowi DJ-a, a nasz własny ma się odświeżyć |
| filary | filar w odległym tempie kosztuje szew (zmierzone: 0,203 na styku 175→112 BPM) |

**Uczciwe ograniczenie, spisane z poprzednich testów person (01.08):** persony
mierzą **układ, teksty i granice**, a nie gust. Gust w każdej z nich jest wciąż
nasz. Persona powie „program odmówił i nie wiem dlaczego", ale nie powie
„ten set brzmi źle".

---

## P1 · Janek (odniesienie)

**Kto:** DJ klubowy, breaks i UK bass, gra co dwa tygodnie. Rekordbox od lat,
CDJ-e w klubie.

**Biblioteka:** 1880 pozycji, z tego 1571 strumieni Apple Music i 229 plików.
Gatunki mieszane: 20 z 46 nazw Beatportu plus tagi Apple („Electronic",
„Dance"). Tonacja i tempo z Rekordboxa w 100%. Dziewięć filarów zapisanych na
stałe. Hot cue ustawia sam, ale nie wszędzie.

**Czego chce:** set na 90 minut wokół kilku utworów, które musi zagrać.

**Co łamie:** wszystko naraz — to jest przypadek odniesienia, nie test.

---

## P2 · Marta · winylowa purystka, mała biblioteka

**Kto:** gra 10 lat, przeszła z winyli na CDJ niechętnie. Kupuje mało i słucha
w całości. Ceni „dlaczego", nie „zrób za mnie".

**Biblioteka:** **310 plików na dysku**, zero strumieni. Wszystko otagowane
ręcznie po Beatportcie. Hot cue ustawia w **każdym** utworze, po dwa–trzy,
i traktuje je jak świętość.

**Czego chce:** żeby program pokazał jej przejścia, których sama by nie
zauważyła, i **niczego nie ruszał**.

**Co łamie:**
- pula 310 przy secie na 20 → sito gatunku i sito brzmienia **muszą się
  rozluźnić**; sprawdzamy, czy mówią o tym zrozumiale;
- ma własne cue na wszystkich padach → nasz zapis powinien ustąpić prawie
  wszędzie i powiedzieć, ile ustąpił;
- brak strumieni → wszystkie utwory grywalne, więc odsłuch i szew mają działać
  bez wyjątku.

**Co ją odrzuci:** jedno nadpisane cue. Koniec, odinstaluje.

---

## P3 · Bartek · wesela i imprezy firmowe, open format

**Kto:** gra 200 imprez rocznie, od Zenka po techno o trzeciej. Zarabia na tym
i nie ma czasu na eksperymenty.

**Biblioteka:** **8400 utworów**, w tym duża część spoza elektroniki: Pop,
R&B, Rock, disco polo. Tonacji nie używa i nie ufa jej. Tempo od 60 do 180.
Hot cue tylko na wejściach.

**Czego chce:** „daj mi 40 minut pod kolację, a potem 60 pod parkiet".

**Co łamie:**
- gatunki spoza taksonomii Beatportu (sekcja „poza taksonomią") — czy lista
  Ctrl+G jest jeszcze czytelna przy 60 pozycjach;
- ogromna rozpiętość tempa → plan tempa i łuk energii;
- **8400 utworów** → czas budowy, czas importu, czy sito 20% to nadal 1700
  kandydatów i czy to ma sens;
- brak zaufania do tonacji → czy da się zbudować set trybem „BPM najpierw".

**Co go odrzuci:** czekanie dłużej niż minutę i każdy komunikat, którego nie
rozumie w trzy sekundy.

---

## P4 · Kuba · techno, jeden gatunek, wąskie tempo

**Kto:** gra techno 138–145, rezydent w jednym klubie. Kupuje z Beatportu
co tydzień, wszystko otagowane poprawnie.

**Biblioteka:** **1200 plików**, 90% w dwóch gatunkach Beatportu (Techno Peak
Time / Driving, Techno Raw / Deep / Hypnotic). Wszystko przeanalizowane
w Rekordboksie, tonacje pewne.

**Czego chce:** set, który rośnie przez dwie godziny i nie schodzi.

**Co łamie:**
- **jednorodna pula** → czy sito brzmienia w ogóle coś zawęża, skoro wszystko
  brzmi podobnie; czy kotwica ma jeszcze sens;
- wąskie okno tempa → czy plan tempa nie zostaje bez kandydatów;
- jego kotwice: **Amelie Lens i Michael Bibi NIE MAJĄ wpisu** w naszej księdze
  284 DJ-ów → co program mówi, gdy DJ-a nie ma;
- łuk „build" przez 2 godziny → czy energia rośnie, czy się poddaje.

**Co go odrzuci:** set, który w połowie zwalnia.

---

## P5 · Zosia · pierwszy rok, tylko streaming

**Kto:** gra od roku, głównie domówki i jeden bar. Uczyła się z YouTube'a.
Nie wie, co to Camelot.

**Biblioteka:** **180 pozycji, wszystkie ze strumieni**, zero plików. Nie ma
ani jednego hot cue. Nie tagowała nic — gatunki są takie, jakie przyszły
z Apple Music.

**Czego chce:** „zrób mi set na dwie godziny, żeby ludzie tańczyli".

**Co łamie:**
- **zero plików** → odsłuch, szew i render odmawiają WSZĘDZIE; czy odmowy są
  zrozumiałe, czy wyglądają jak awaria;
- 180 utworów → prawie każde sito się rozluźni;
- wektory brzmienia: jej utwory są w katalogu iTunes, więc powinny się
  dociągnąć — ale przy 180 pozycjach kotwica i tak niewiele zmieni;
- brak wiedzy o tonacji → czy kolumny „ton" i „pew." cokolwiek jej mówią;
- pierwsze uruchomienie: pusta pula, zanim coś zaimportuje.

**Co ją odrzuci:** pierwszy komunikat po angielsku albo słowo, którego nie zna.

---

## P6 · Olek · producent, gra własne kawałki

**Kto:** producent, gra sety z własnych, niewydanych utworów i cudzych
promek. Połowa jego plików nigdy nie widziała Rekordboxa.

**Biblioteka:** 600 plików, z czego **220 nie ma wpisu w Rekordboksie** —
świeże bounce'y z DAW-a, bez analizy, bez tagów, nazwy plików typu
`mixdown_v7_FINAL.wav`.

**Czego chce:** poukładać materiał na występ i wyeksportować cue na CDJ-e.

**Co łamie:**
- **utwory bez analizy Rekordboxa** → nie mają jego siatki, więc hot cue
  muszą siąść na NASZEJ; czy potrafimy powiedzieć „nie znam fazy taktu";
- brak tagów gatunku → jak zachowuje się brief z gatunkiem, gdy połowa puli
  nie ma etykiety;
- brak wpisu w kolekcji → **wysyłka cue musi pominąć je imiennie**;
- nazwy plików bez artysty i tytułu → jak wygląda tabela i czy da się szukać.

**Co go odrzuci:** cue wysłane w złe miejsce na jego własnym kawałku.

---

## Macierz testów

| co sprawdzamy | P1 | P2 | P3 | P4 | P5 | P6 |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| rozluźnienie sita gatunku | | ● | ● | | ● | ● |
| rozluźnienie sita brzmienia | | ● | | ● | ● | |
| kotwica: DJ spoza księgi | | | ● | ● | | |
| odmowy przy utworach bez pliku | | | | | ● | |
| kolizje z własnymi hot cue | | ● | | ● | | |
| utwory spoza kolekcji Rekordboxa | | | | | | ● |
| brak fazy taktu (cue na naszej siatce) | | | | | | ● |
| czas budowy i importu | | | ● | | | |
| czytelność list przy wielu gatunkach | | | ● | | | |
| język i zrozumiałość komunikatów | | | ● | | ● | |

---

## Co dalej

1. **Zbudować biblioteki person** — nie zmyślone utwory, tylko podzbiory
   i przekształcenia realnej puli (odciąć do 180 pozycji, usunąć wektory,
   podmienić gatunki na Apple'owe, usunąć wpisy z kolekcji). Dzięki temu
   liczby zostają prawdziwe, a łamie się dokładnie ta jedna rzecz, o którą
   chodzi.
2. **Przejść scenariusz każdej persony** w aplikacji i zapisać, co program
   powiedział — dosłownie, z komunikatami.
3. **Zebrać wyniki** w tabeli „persona → co się stało → czy to jest do
   naprawy".

Katalog na wyniki: `experiments_priv/2026-08-09_persony_dj/`.
