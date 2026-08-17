# Warstwa kuratorska — jak powstaje wydarzenie i kto naprawdę wybiera

Założone 2026-08-14. Wątek osobny od mapy DJ-ów i osobny od silnika.

Punkt wyjścia — zdanie Janka, które uruchomiło ten wątek:

> „To już chyba trzeba wejść w system, jak tworzy się i organizuje eventy.
> I jaką rolę pełnią kuratorzy. Jak są kuratorzy dzieł sztuki, którzy tworzą
> galerie, tak samo DJ-e są swoistymi dziełami sztuki w galerii festiwalowej."

Analogia jest trafna i — co ważniejsze — **sprawdzalna w danych, które już mamy**.
Ten dokument robi trzy rzeczy: opisuje realny łańcuch powstawania line-upu,
pokazuje gdzie analogia z galerią trzyma a gdzie pęka, i podaje **pierwsze
pomiary**, które z niej wynikły.

---

## Część I — jak naprawdę powstaje line-up

Kolejność jest sztywna. Prawie nikt spoza branży jej nie zna, a ona wyjaśnia
większość tego, co w danych wygląda na gust.

**1. Teren i data.** Pozwolenia, cisza nocna, sąsiedzi, kolizja z innym
festiwalem w regionie. Ustalane, zanim padnie jakiekolwiek nazwisko.

**2. Podział budżetu.** Honoraria to tylko część kosztu — produkcja,
nagłośnienie, ochrona i ubezpieczenie potrafią być większe. Headliner potrafi
zjeść trzydzieści do pięćdziesięciu procent budżetu na artystów.

**3. Kotwica.** Headliner bookowany pół roku do roku wcześniej, **u agencji,
nie u artysty**. Artysta bywa informowany później.

**4. Reszta** — i tu wchodzi warstwa niewidoczna w danych publicznych, która
kształtuje line-up mocniej niż czyjkolwiek gust:

| mechanizm | co robi | czy widać w danych |
|---|---|---|
| **klauzula promienia** | zakaz gry w promieniu X km przez Y tygodni przed i po | **nie** — widać tylko skutek: artysta „znika" z regionu |
| **pakiet agencyjny** | bierzesz headlinera, bierzesz trzech z tej samej stajni | **nie** wprost; pośrednio przez współwystępowanie |
| **klauzula plakatowa** | pozycja na plakacie i wielkość czcionki, negocjowane w umowie | częściowo — kolejność w line-upie |
| **wyłączność** | „jedyny występ w Polsce tego lata" | pośrednio — luka w kalendarzu |
| **slot w kontrakcie** | „gra nie wcześniej niż o północy" jako zapis umowy | **nie** — wygląda jak decyzja artystyczna |
| **takeover / oddanie sceny** | label albo kolektyw obsadza całą scenę | **tak** — w nazwie wydarzenia |

Ostatni wiersz jest strukturalnie najważniejszy: **duża część programu
festiwalu nie jest kuratorowana przez festiwal.** Scena bywa oddana labelowi
albo kolektywowi. Festiwal daje ścianę, wiesza ktoś inny.

To jest dokładnie model galerii z kuratorem gościnnym.

**Kto decyduje — role, często mylone:**

* **promotor / dyrektor** — bierze ryzyko finansowe
* **booker (*talent buyer*)** — robi umowy, rozmawia z agencjami
* **programmer / kurator** — projektuje kształt; przy małym festiwalu ta sama
  osoba co booker, przy dużym osobna
* **gospodarz sceny** — label albo kolektyw z oddaną sceną

---

## Część II — gdzie analogia z galerią trzyma

**Selekcja jest dziełem.** Kurator nie maluje. Wystawa jest pracą. Festiwal nie
robi muzyki — robi wybór i porządek.

**Sąsiedztwo tworzy znaczenie.** Dwa obrazy obok siebie czyta się inaczej niż
osobno. To jest domena DanceLab słowo w słowo: my projektujemy szew, kurator
projektuje ścianę. **To ta sama operacja na innej skali.**

**Legitymizacja idzie w obie strony.** Galeria uwiarygodnia artystę, artysta
uwiarygodnia galerię.

**Rynek pierwotny jest niejawny.** Ceny w galerii nie są publiczne. Honoraria
DJ-ów nie są publiczne. W obu przypadkach celowo.

**Rezydencja to reprezentacja.** Rezydent klubu jest tym, czym artysta
reprezentowany przez galerię. Ta sama umowa, inna nazwa. **I to okazało się
mierzalne — patrz część IV.**

**Instytucja archiwizuje.** De School po zamknięciu wydała własne archiwum
z metadanymi. To jest akt muzealny: uznanie własnego programu za kolekcję
wartą zachowania.

---

## Część III — gdzie pęka, i dlaczego pęknięcie jest produktem

**Obraz nie występuje.** Powieszony wygląda tak samo za każdym razem. Kurator
galerii wie, co wiesza. Kurator festiwalu **wiesza rozkład prawdopodobieństwa**
— kupuje nazwisko i dostaje jedno losowanie z tego, co ten człowiek potrafi
zagrać. Ten sam DJ o północy na dużej scenie i o piątej rano w namiocie to są
dwie różne prace.

**To jest luka rynkowa.** Chartmetric, Soundcharts i Viberate sprzedają
**rozmiar nazwiska**. Nikt nie sprzedaje **rozkładu tego, co z nazwiska
wychodzi**.

**Ścianą jest czas, nie przestrzeń.** Zwiedzający galerię wybiera trasę, może
wrócić, może ominąć. Publiczność festiwalu dostaje jedną kolejność, w jedną
stronę, bez powrotu. Kuratorowanie festiwalu jest więc **bardziej związane**
niż kuratorowanie wystawy, nie mniej.

**Publiczność jest częścią dzieła.** Obraz w pustej sali to ten sam obraz. Set
w pustej sali to inny set. Dlatego tak trudno o miarę wyniku.

**Pieniądze płyną odwrotnie.** W galerii kolekcjoner płaci za obiekt po fakcie.
Na festiwalu publiczność płaci za **dostęp do czasu**, a artysta dostaje
honorarium z góry, niezależnie od wyniku. Całe ryzyko leży na organizatorze.

---

## Część IV — pierwsze pomiary (2026-08-14)

Policzone skryptem `scripts/kuratorzy_wyciag.py` z `ra.json` i `de_school.json`.
Bez dźwięku, bez pobierania. Wyniki w `wyciag/`.

### Podstawa

```
występów zagranych (RA)        20 967
artystów z historią RA            609    ← NIE 1466; RA pokrywa część mapy
miejsc (galerii)                4 906
par artysta-miejsce            14 656
```

### Powrót — czyli sąd wydany PO obejrzeniu

```
par z powrotem (≥2 razy)        2 492    17,0%
par ≥5 razy                       406
```

Pierwszy booking to hype. **Drugi to ktoś, kto widział ten set i zdecydował się
powtórzyć.** To jest najbliższa rzecz „wynikowi", jaką ten rynek publikuje.

### Odkrycie główne: rezydenci i podróżnicy to dwie różne populacje

Wśród 568 artystów z co najmniej dziesięcioma występami:

| | rezydenci (≥30% występów w jednym miejscu) | podróżnicy (<10%) |
|---|---:|---:|
| ilu | **96** | **177** |
| mediana obserwujących na RA | **36** | **2 871** |
| mediana liczby miejsc | 14 | 36 |

**Osiemdziesięciokrotna różnica w zasięgu przy tym samym zawodzie.**

Wniosek, który trzeba powiedzieć wprost: **zasięg mierzy podróżowanie, nie
granie.** Człowiek, który 32 razy zagrał w jednym klubie, ma trzydzieści sześć
obserwujących. Nie dlatego, że gra gorzej — dlatego, że obserwujących zdobywa
się objazdem, a nie parkietem.

**Ostrzeżenie o obciążeniu:** RA słabiej pokrywa lokalnych rezydentów niż
artystów objazdowych, więc część tej różnicy to artefakt zbierania, nie
zjawisko. Kierunek jest jednak zbyt silny, żeby wyjaśnić go samym obciążeniem.
**Do rozstrzygnięcia w tym wątku.**

### Galerie ze stajnią

Miejsca o najwyższym stosunku występów do artystów (od 40 występów wzwyż):

| wyst./artystę | występów | artystów | % wraca | miejsce |
|---:|---:|---:|---:|---|
| 5,79 | 139 | 24 | 62,5% | Prozak 2.0, Kraków |
| 4,50 | 99 | 22 | 72,7% | Luzztro, Warszawa |
| 4,32 | 294 | 68 | 66,2% | Smolna, Warszawa |
| 4,19 | 917 | 219 | 67,6% | Kater, Berlin |
| 3,17 | 168 | 53 | 60,4% | Golden Gate, Berlin |

Miejsce z 900 występami i 100 artystami prowadzi **stajnię**. Miejsce z 900
występami i 800 artystami prowadzi **przepustownię**. To są dwa różne modele
kuratorskie i dane je rozdzielają.

### Znaczniki kuratorskie w tytułach

4 143 występy (19,8%) mają w tytule jawny ślad kuratora:

```
kolaboracja (X × Y)  1 833      label            283
presents             1 176      invites          259
rocznica               623      showcase         185
                                takeover          86
                                rezydencja        53
```

**Uwaga:** te regexy mylą. „with" łapie zwykłe wyliczenie składu, „records"
łapie nazwę artysty. Plik `wyciag/znaczniki_kuratorskie.csv` jest **do
przejrzenia okiem**, nie do liczenia na ślepo.

---

## Część V — teza, która z tego wynika

Rynek sztuki ma **katalog dzieł**: udokumentowany spis wszystkiego, co artysta
zrobił, gdzie było wystawiane i u kogo wisiało. To on czyni rynek czytelnym —
bez niego nie da się ani wycenić, ani uwierzytelnić.

Muzyka elektroniczna ma tylko kawałki:

* **RA** = lista wystaw (gdzie był, kiedy) — mamy 20 967 pozycji
* **Discogs** = lista wydań (co wypuścił)
* **nikt** = **same prace** — co faktycznie zagrał, w jakiej kolejności, o której

DanceLab ma 21 015 zidentyfikowanych szwów (zalążek katalogu) i 492 z czasem
(**proweniencja** — to, co w sztuce tworzy wartość, bo odpowiada na pytanie
„skąd wiemy, że to prawda").

**Zdanie robocze:** *DanceLab buduje katalog i proweniencję setów DJ-skich.
Rynek kupuje nazwiska, nie wiedząc, co kupuje.*

Do sprawdzenia, nie do ogłoszenia. Patrz `PYTANIA.md`.

---

## Czego ten wątek NIE robi

**Nie liczy dźwięku.** BPM, tonacje, czasy i szwy mają własny wątek.

**Nie zbiera nowych danych bez pytania.** Wszystko powyżej wyciśnięte z tego,
co już leżało na dysku.

**Nie ogłasza tezy z części V jako ustalonej.** To jest hipoteza o rynku,
oparta na analogii. Analogie bywają ładne i fałszywe.
