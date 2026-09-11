# Jak narysować konsolę, żeby wyglądała jak sprzęt

Metoda wyciągnięta z dziewięciu rund poprawek modelu DDJ-FLX4 (`docs/flx4-konsola/`,
23–24.08.2026). Każda runda była korektą po zrzucie ekranu od Janka. Ten dokument
istnieje po to, żeby następna konsola nie kosztowała dziewięciu rund.

**Wzorzec odniesienia:** model FLX4 na porcie 8655. Janek o nim: *„teraz działa
git"*. Jeśli nowy model wygląda gorzej, to nie jest kwestia gustu — czegoś z tej
listy nie zrobiłem.

---

## Kolejność ma znaczenie

Każda zamiana kolejności kosztowała nas rundę. Etapy 1–3 są tanie i odwracalne,
4–9 zakładają, że fundament stoi.

### 1. Szkielet mechaniczny, zanim cokolwiek wygląda

Kontrolki reagują na sygnał, zanim mają fakturę. Identyfikatory ustalone **raz**
i nietykalne przez wszystkie kolejne rundy — dzięki temu trzykrotna przebudowa
wizualna FLX4 nie zepsuła ani mapowania, ani wykresów, ani panelu pokrycia.

Wynikiem etapu jest **panel pokrycia**: ile z N kontrolek już widziano. To jest
jednocześnie test mechaniki i lista rzeczy do narysowania.

### 2. Geometria z płaskiego rzutu — nigdy z perspektywy

**Najdroższy błąd całej serii.** Rysunek w liście MIDI to ujęcie pod kątem;
mierzenie z niego dało jog 104 mm zamiast 140. Jedynym uczciwym źródłem wymiarów
jest **płaski rzut z instrukcji obsługi**.

Sposób: render strony w wysokim DPI → wykrycie krawędzi panelu progowaniem →
siatka milimetrowa → odczyt każdej kontrolki. Narzędzie:
`scripts/rzut_na_siatke.py`. Wynik zapisać jako tabelę współrzędnych w
notatkach eksperymentu — **przetrwa dłużej niż kod, który ją wyprodukował**.

Czego nie zakładać: że drugi deck jest lustrem pierwszego. Na FLX4 to
**przesunięta kopia** (PLAY po lewej na obu deckach). Sprawdzić w rzucie.

### 3. Semantyka światła: co świeci i skąd to wiemy

Zanim dojdzie faktura, trzeba rozstrzygnąć, co dioda **znaczy**. Na FLX4
przeszliśmy tu pełny cykl:

* pierwsza wersja: dioda gaśnie z puszczeniem przycisku — Janek: na sprzęcie
  świeci do odklikania;
* druga wersja: stany **wnioskowane** z naciśnięć (CUE i SYNC jako przełączniki,
  hot cue jako zbiór);
* wersja końcowa, po testach na sprzęcie: **dioda = dotyk**. Stany wnioskowane
  rozjeżdżały się z prawdą, bo diodami steruje Rekordbox przez MIDI-OUT, którego
  nie podsłuchujemy.

Trwałe zostały tylko trzy rzeczy, wszystkie wywnioskowane z pewnością:
aktywny tryb padów (grupa radiowa), ustawione hot cue, FX ON/OFF.

**Reguła ogólna: czego nie mierzymy, tego nie udajemy.** Mierniki poziomu są
narysowane wygaszone z podpisem — świecą z sygnału, którego nie widzimy.

### 4. Materiał ze zdjęć, nie z wyobraźni

Rysunek techniczny daje wymiary. Kolory, faktury i głębia są **tylko na
zdjęciach**. Diody FLX4 są **pomarańczowe** (PLAY zielony) — rysowałem je
cyjanowe, dopóki Janek nie przysłał zdjęć.

Z fotografii czytać: kolor każdego rodzaju światła, materiał (matowy pad
mleczny, błyszczący talerz), kierunek podświetlenia (pady świecą **od spodu** —
osobna warstwa blasku), fakturę korpusu (drobny szum + winieta).

### 5. Detale, których nie ma na rysunku technicznym

Rowki między sekcjami, opona joga z wgłębieniami, obwódki chipów, nadrukowane
łuki skal, nacięcia w gniazdach suwaków. Wszystko z fotografii, wskazane przez
osobę, która ma ten sprzęt na biurku.

To ten etap zamienia „schemat" w „sprzęt".

### 6–9. Audyt: geometria, typografia, wyrównania, szlify

Te cztery etapy mają jedną wspólną regułę, wywalczoną najdrożej.

---

## Reguła, która kosztowała najwięcej

Janek, po kilkunastu zrzutach z zaznaczonymi błędami:

> *„coś masz problemy z designem jeśli chodzi o takie podstawowe rzeczy jak
> centrowanie, wyrównanie do osi x czy y"*

Miał rację. Jego uwagi układają się w cztery powtarzalne klasy błędu — i wszystkie
cztery są **mierzalne**:

| co pisał | klasa |
|---|---|
| „popraw paddingi bo ucina teksty albo wyjeżdżają poza ramy" | tekst poza kształtem |
| „napis nie jest wycentrowany między wgłębieniami, idzie bardziej w lewo" | centrowanie |
| „podpisy pod guzikami nie są wyrównane względem osi X na decku 1 i 2" | oś |
| „dalej brak równego odstępu" | rytm |
| „okręgi najeżdżają na teksty", „łuki przechodziły przez napisy" | kolizja |

**Wniosek: oko zawodzi przy tych czterech rzeczach, więc sprawdza je maszyna.**

Narzędzie: `docs/audyt-ui.js`, wpinane do strony i uruchamiane przez `?audyt=1`.
Zgłasza wszystkie pięć klas, wypisuje raport do konsoli i rysuje ramki wokół
znalezisk.

Audytor jest **skalibrowany na modelu FLX4**: strona zaakceptowana przez Janka
daje zero błędów. Jeśli krzyczy na nią po zmianie — zły jest próg, nie strona.

---

## Pułapki, w które wpadłem

Wszystkie przeżyte, każda kosztowała rundę.

**Odstęp międzyliterowy dolicza się za ostatnią literą.** Przeglądarka wlicza go
do szerokości napisu, więc każdy tekst `text-anchor="middle"` wisi w lewo o pół
odstępu. Kompensować, ale **nie przy napisach jednoznakowych**.

**Filtr poświaty na kresce o zerowej ramce kasuje ją całkiem.** Pionowa linia
uchwytu suwaka zniknęła po dodaniu blasku.

**Napis nie może przecinać rowka sekcji.** Reguła Janka: *„w realu byłoby to
niemożliwe"* — rowek to fizyczna szczelina w obudowie.

**Niewidzialne strefy dotyku kolidują ze wszystkim.** Warstwy interakcji mają
puste wypełnienie i audytor musi je pomijać — inaczej zgłasza napis SHIFT jako
kolidujący ze strefą joga o promieniu 67 px.

**Kolejność w pliku SVG nie mówi, co na czym leży.** Pierwsza wersja audytora
parowała napis z poprzednim rodzeństwem i produkowała „napis odjechał o 576 px".
Parować **geometrycznie**: tłem jest najmniejszy kształt zawierający napis, przy
czym kandydat wyraźnie większy w którejkolwiek osi to płyta, nie etykieta.

**Żadnych emoji jako ikon.** Ikona słuchawek była emoji — zastąpiona rysunkiem.

**Czysty SVG, zero bibliotek.** Strona ma się otworzyć bez sieci za pięć lat.
Model FLX4 to jeden plik HTML: 14 gradientów promienistych, 8 liniowych, 3 filtry.
Tyle wystarcza na fakturę, głębię i poświatę.

---

## Sprawdzian gotowości

Model jest gotowy, gdy:

1. `?audyt=1` daje **zero błędów** (ostrzeżenia o kolizjach poniżej 3 px są
   dopuszczalne — na FLX4 zostały dwa takie);
2. każda kontrolka reaguje na sygnał, a panel pokrycia dochodzi do kompletu;
3. wszystko, czego nie mierzymy, jest narysowane wygaszone i podpisane;
4. osoba, która ma ten sprzęt, patrzy na zrzut i nie wskazuje różnicy.

Punkt 4 jest jedynym prawdziwym testem. Trzy pierwsze mają sprawić, żeby na
czwartym nie tracić rund na centrowanie.


## Etap dodatkowy (03.09): mapowanie 1:1 między dwoma panelami

Dwa gotowe panele (`flx4-konsola/`, `sprzet-klubowy/`) łączy trzecia strona
(`mapowanie/`) przez dwie ramki i `postMessage` — bez kopiowania rysunków.
Dane relacji żyją w jednym pliku (`sprzet-klubowy/mapowanie.json`), a relacja
pary bierze się ze stanu kontrolki w `kontrolki.json`; nadpisanie stanu musi
być jawne i mieć powód. Reguła: cztery liczby na górze panelu klubu i pary
w mapowaniu muszą się zgadzać **testem** (`tests/test_mapowanie_flx4_klub.py`),
nie zapewnieniem. Kontrolka bez odpowiednika mówi to na karcie po obu
stronach. Pułapka techniczna do zapamiętania: stała leksykalna strony nie jest
`window.X` dla ramki-rodzica, a przeglądarka trzyma panele w cache — ramki
dostają parametr czasu w `src`.

## Etap dodatkowy (29.08–11.09): model 3D i rzut wektorowy jako źródła

Panel klubowy (CDJ-3000 + DJM-900NXS2) nie miał osoby ze sprzętem na biurku,
więc etapy 2, 4 i 5 szły z trzech innych źródeł. Każde dało co innego i każde
miało swoją pułapkę.

**Model 3D — materiał tak, geometria nie wprost.** Kryterium zapisane przed
otwarciem pliku (co najmniej 30 osobnych obiektów) padło: model to cztery
zlepione bryły. Dał za to dwie rzeczy. Rendery z góry, z przodu, z boku — to jest
etap 4 („materiał ze zdjęć") dla sprzętu, którego nikt nie sfotografował; PLAY
zielony i CUE bursztynowy są z renderu, nie z pamięci. I pozycje: siatkę da się
rozciąć na wyspy części (`experiments_priv/2026-08-29_model_3d/`), a wyspy
wyrównać do instrukcji dwoma punktami odniesienia (listwa hot cue, środek
talerza). Skalę sprawdza się niezależnie: głębokość panelu z renderu 454,0 mm
wobec 453,0 ze specyfikacji.

**Rzut wektorowy — czytać ŚCIEŻKI, nie tylko prostokąty.** Strona instrukcji
DJM to grafika wektorowa: każda kreska i każdy napis ma współrzędne. Pierwszy
wyciąg (29.08) brał tylko prostokąty i przez dwa tygodnie nikt nie zauważył, że
tym samym sitem wypadło wszystko, co jest rysowane krzywymi — każda gałka,
fadery, crossfader. `get_drawings()` z pymupdf oddaje także ścieżki; koło to
ścieżka z krzywymi o obwiedni prawie kwadratowej. Skalę sprawdzać czymś, czego
się z rysunku nie brało: proporcja obrysu 0,803 wobec katalogowych 0,801 i trzy
równe odstępy kanałów (42,6 / 42,8 / 42,8 mm).

**Napisy z renderu — OCR daje pozycję, instrukcja daje nazwę.** Nadruk na
panelu jest stylizowany i OCR (macOS Vision) czyta „RELOOP/EXIT" jako
„NLCOPDOT", a „SEARCH" jako „MARCH". Położenie ma jednak dobre. Nazwa idzie więc
z listy części instrukcji, pozycja z OCR, przeliczona **tym samym wyrównaniem co
części modelu** — inaczej napisy i kontrolki leżałyby w dwóch różnych układach.

**Reguła: trzy źródła na jedną kontrolkę, zapisane przy niej.** Pole `zrodlo`
w `uklad.json` mówi dla każdego elementu: która część modelu (albo ścieżka
wektorowa), jaki napis stoi przy niej na renderze, jaki numer ma na liście
części instrukcji. Przypisanie z jednego źródła wyglądało dobrze i było złe
trzy razy: KEY SYNC siedział na listwie JOG MODE, „słuchawki" na pudełku SOUND
COLOR FX, rząd CUE na przełącznikach A THRU B. Każdy z tych błędów miał flagę
`zmierzone: true` — **zmierzone nie znaczy przypisane dobrze.** Wyłapał je
dopiero napis na renderze albo w rzucie, czyli drugie źródło.

**Audyt przed i po, na tej samej maszynie.** Liczba ostrzeżeń sama nic nie
mówi. Przed zmianą: podmienić plik na wersję z gita, przeładować, zapisać
`window.__audyt`; po zmianie to samo; porównać napis po napisie. Nowe
ostrzeżenie trzeba sklasyfikować **geometrycznie** — czy napis leży na własnej
kontrolce (znana klasa, jak pady A–H), czy na sąsiedniej (błąd) — zanim się je
przyjmie.

**Pułapka: serializer zmienia cały plik.** `json.dumps` bez wcięcia z oryginału
spłaszczył `uklad.json` do jednej linii i diff pokazał 474 usunięte wiersze przy
ośmiu zmienionych elementach. Zapisywać tym samym formatem, który plik już ma
(tu: wcięcie 1, `ensure_ascii=False`), i sprawdzić to, odtwarzając wersję
z gita bajt w bajt.
