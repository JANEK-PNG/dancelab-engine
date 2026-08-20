# Research 01 — jak uczciwie narysować zmierzony szew

Data: 2026-08-20. Reguła wątku (Janek): decyzji projektowych NIE zgadujemy —
najpierw literatura/kursy/fora, z każdego artykułu idziemy po jego bibliografii.
Ten plik = jawne pochodzenie decyzji projektowych, tak jak każda liczba w
silniku ma pochodzenie.

## Punkt odniesienia (4 artykuły od Janka, Desktop/DanceLab-Design)

1. **Katherine Yeh, „A Designer's Guide to Claude Code"** (Medium/Bootcamp) —
   wiedza projektowa w trzech warstwach: zasady (dlaczego) / specyfikacja (co)
   / umiejętności (jak). Kluczowe: *specyfikacja wykonuje, zasady oceniają*.
2. **Nick Babich, „Claude Design Critique"** (UX Planet) — krytyka = osobne
   wyspecjalizowane przejścia w ustalonej kolejności, nie jedno „co jest źle".
   U nas kolejność własna: 1. wizualna uczciwość → 2. hierarchia → 3. ton
   głosu → 4. stany.
3. **Nick Babich, „Claude Skills for Product Designers"** — mechanika spisywania
   rytuałów; potwierdza: powtarzalny proces wart pliku.
4. **Maya Brennan, „How to become an AI Designer"** (UX Collective) — źródło
   prawdy = sam produkt, nie makiety; szkic do 90% tani, ostatnie 10% szlifu
   drogie — decydować świadomie; reguła trzech prób (trzecia poprawka tego
   samego = stop, zmiana podejścia albo zapis wniosku na stałe).
   **Bibliografia do przejścia:** Wattenberger „Our Interfaces Have Lost Their
   Senses"; Emil Kowalski „7 Practical Animation Tips"; Jakub Krehel „Details
   That Make Interfaces Feel Better"; AI Design Field Guide; wywiad z Jenny
   Wen (Anthropic) u Lenny'ego.

## Przebieg 1 — literatura pod pierwszy mebel (zmierzony szew)

### Warstwy ułożone jedna na drugiej (nasze piętra bas/środek/góra)

**Byron & Wattenberg, „Stacked Graphs – Geometry & Aesthetics"**
(https://leebyron.com/streamgraph/stackedgraphs_byron_wattenberg.pdf — pełny
tekst przeczytany):
- Wykres warstwowy realizuje zasadę makro/mikro Tufte'a: pokazuje sumę i
  składniki naraz, ale **za cenę**: zmiana środkowej warstwy faluje sąsiadami
  (fałszywe „ruchy" niezwiązane z danymi), a grubość warstwy o innym nachyleniu
  czyta się błędnie.
- **Wybór linii bazowej to policzalna decyzja**, nie gust: różne bazy
  minimalizują różne miary zniekształcenia (tradycyjna baza zero = czytelna
  suma, symetryczna ThemeRiver = minimalne nachylenia, streamgraph =
  „weighted wiggle", czytelność grubych warstw). Dokładnie nasz język: wybrać
  bazę pod to, CO ma być czytane, i umieć powiedzieć dlaczego.
- Kolor u nich: ciemność/nasycenie = istotność serii; ostrzeżenie przed
  kolorem-dekoracją. Publiczność myliła skalę przy organicznej formie
  (komentarze „vertical scale is basically irrelevant") — **uroda kosztuje
  czytelność skali; kompromis ma być świadomy**, co jest literaturowym
  odpowiednikiem naszej zasady „uczciwość przed urodą".
- Ich bibliografia do przejścia dalej: Tufte (makro/mikro), Cleveland
  (banking do 45°), Bertin (proporcje a czytelność nachyleń), Havre
  ThemeRiver.

**Heer et al., „Sizing the Horizon" (CHI 2009)** — pobranie PDF padło na
certyfikacie (mirror do znalezienia); z omówień: wykresy horyzontowe
zwiększają dokładność odczytu na małej wysokości, ale **powyżej trzech pasm
błąd i czas odczytu rosną**. Wniosek dla nas: nasze trzy piętra (bas / środek
/ góra) to dokładnie tyle, ile percepcja unosi — nie dokładać czwartego.

### Niepewność i pochodzenie liczb (norma „niezmierzone ≠ zero")

**Claus Wilke, „Fundamentals of Data Visualization", rozdz. Visualizing
Uncertainty** (darmowa książka: https://clauswilke.com/dataviz/) oraz
**Padilla, Kay, Hullman, „Uncertainty Visualization" (2022)**
(http://space.ucmerced.edu/Downloads/publications/Uncertainty_Visualization_Padilla_Kay_Hullman_2022.pdf):
- Nazwany w literaturze błąd, przed którym broni nas norma provenance:
  **deterministic construal error** — widz odczytuje element obrazu jako
  pewnik, choć to szacunek. Ramka bez pomiaru narysowana „na płasko" =
  dokładnie miernik pokazujący zero, którego nie zmierzył (lekcja etapu 6).
- Działa: stopniowane przedziały (ciemniej = pewniej), kropki kwantylowe
  (dyskretne obiekty liczymy lepiej niż pola), animowane losowania (HOPs).
  Nie działa: goły słupek błędu bez podpisu, fałszywa precyzja linii.
- Dla szwu: okna bez pomiaru — szare i INNE fakturą, nie tylko jaśniejsze;
  „zmierzone 0" ≠ „niemierzalne" także na poziomie enkodowania.

### Głos praktyków (jak DJ-e naprawdę czytają przebiegi)

**Chris M, „The Secret Language of Waveforms"**
(https://reallychrism.substack.com/p/the-secret-language-of-waveforms) i
**DeeJay Plaza o kolorach w Rekordboksie**
(https://www.deejayplaza.com/en/articles/color-waveform-rekordbox):
- Przebieg to dla DJ-a „spis treści" utworu: gdzie energia, gdzie zmiana,
  gdzie planować wejście — czyli czytany jest STRUKTURALNIE, nie estetycznie.
- Konwencje kolorów są w mięśniach zawodowców: RB 3-band = niebieski bas /
  bursztynowe środki / białe góry; Serato = czerwony bas / zielone środki /
  niebieskie góry. **Nasz panel porównania w TUI (bas niebieski / środek
  bursztyn / góra biała) już siedzi w konwencji Rekordboxa — nie wymyślać
  nowej, DJ ma to w odruchu** („user is familiar", jak przy układzie panelu).
- Tryby różnią się celem: 3-band = szybkie znajdowanie stopy, RGB = głębsze
  czytanie faktury. Wniosek: jedna forma nie musi obsłużyć obu zadań naraz.

### Luki tego przebiegu (uczciwie)

- **Reddit/Quora**: crawler ma zablokowany dostęp do reddit.com — dyskusje
  praktyków (r/DJs, r/Beatmatch, r/dataisbeautiful) do przejścia ręcznie albo
  przez panel przeglądarki w osobnym posiedzeniu.
- **Heer „Sizing the Horizon"**: przeczytać pełny tekst z działającego mirrora.
- **Darmowe kursy** (wykłady wizualizacji danych, np. materiały Munzner):
  jeszcze nietknięte.
- Bibliografia Brennan (Wattenberger, Kowalski, Krehel) — do przejścia przed
  decyzjami o RUCHU na scenie, nie o statyce.

## Co z tego wynika dla warstwy 1 płótna szwu

1. Trzy piętra pasm to sufit percepcji (Heer) — trzymamy bas/środek/górę.
2. Kolory pasm dziedziczymy z konwencji Rekordboxa, już użytej w TUI —
   niebieski/bursztyn/biały; kolor mówi, nie zdobi (prawo koloru PORTRETU).
3. Jeżeli piętra układamy jedno na drugim, wybór linii bazowej deklarujemy
   i uzasadniamy miarą (co ma być czytane: suma czy pojedyncze piętro) —
   Byron & Wattenberg dają gotowy słownik tych kompromisów.
4. Brak pomiaru dostaje własne enkodowanie (szarość + inna faktura), odrębne
   od „zmierzonego zera" — inaczej popełniamy nazwany w literaturze błąd
   deterministycznego odczytu.
5. Forma czytana strukturalnie jak przebieg u DJ-a (spis treści szwu), nie
   jak infografika — zgodnie z lekcją „kreatywne, ale infografiki" z nocnej
   pracowni.
