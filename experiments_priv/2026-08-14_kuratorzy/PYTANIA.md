# Otwarte pytania wątku kuratorskiego

Kolejność nie jest dowolna. Pierwsze dwa rozstrzygają, czy reszta ma sens —
jeśli wyjdzie, że różnica rezydent/podróżnik to artefakt zbierania, połowa
tej listy odpada.

Każde pytanie ma zapisane, **czym byłaby odpowiedź**, żeby dało się poznać,
kiedy jest gotowa. Pytanie bez tego pola to nie pytanie, tylko temat.

---

## 1. Czy różnica rezydent/podróżnik jest realna?

Rezydenci: mediana 36 obserwujących na RA. Podróżnicy: 2871. Osiemdziesiąt razy.

**Podejrzenie:** RA jest serwisem międzynarodowym i lokalny rezydent nie ma
powodu tam być obserwowany, nawet jeśli gra co tydzień przed pełną salą.
Wtedy mierzymy zasięg serwisu, nie zasięg człowieka.

**Odpowiedzią byłoby:** ta sama różnica (albo jej brak) policzona na zasięgu
**spoza RA** — obserwujący na SoundCloud, których mamy w `socials.json`.
Jeśli tam różnica zniknie, to artefakt. Jeśli zostanie, to zjawisko.

**Do policzenia w Claude Code.** Dane są.

---

## 2. Czy powrót w ogóle coś przewiduje?

17,0% par artysta-miejsce ma powrót. Zakładamy, że powrót znaczy „zadziałało".

**Podejrzenie:** powrót może znaczyć „mieszka w tym mieście i jest tani".
Wtedy mierzymy geografię i budżet, nie jakość.

**Odpowiedzią byłoby:** porównanie odsetka powrotów dla artystów **z tego
samego miasta co miejsce** i **z innego kraju**. Jeśli powrót lokalnych jest
radykalnie wyższy, to potwierdza podejrzenie i trzeba liczyć osobno.

**Do policzenia w Claude Code.** Kraj artysty i kraj miejsca są w danych.

---

## 3. Czy reputacja przechodzi między galeriami?

To jest pytanie o to, czy istnieje coś takiego jak „uznanie", które podróżuje.

**Odpowiedzią byłoby:** czy występ w miejscu o wysokim prestiżu **poprzedza**
występy w innych takich miejscach częściej, niż wynikałoby z przypadku.
Wymaga uporządkowania po dacie i jakiejś miary prestiżu miejsca.

**Uwaga:** tu bardzo łatwo pomylić przyczynę ze skutkiem. Agencja, która
załatwia jedno, załatwia i drugie. Bez wiedzy o agencji ten pomiar jest ślepy.

---

## 4. Ile programu festiwalu jest oddane na zewnątrz?

Takeover, showcase, label night. Mamy 86 wystąpień znacznika „takeover"
i 185 „showcase" na 20 967 występów — czyli **prawie nic**.

**Podejrzenie:** to nie znaczy, że zjawiska nie ma. Znaczy, że nie nazywa się
go w tytule wydarzenia na RA.

**Odpowiedzią byłoby:** ręczny przegląd kilkunastu dużych festiwali z ich
własnych materiałów (strona, plakat, timetable) i porównanie z tym, co widać
w RA. To jest robota na oko, nie na regex.

---

## 5. Jak wygląda umowa bookingowa naprawdę?

Klauzula promienia, pakiet agencyjny, klauzula plakatowa, wyłączność. Opisane
w KURATORZY.md z pamięci i z ogólnej znajomości branży — **nie ze źródeł**.

**Odpowiedzią byłoby:** dwa, trzy sprawdzalne źródła (wzór umowy, artykuł
branżowy z autorem i datą, wypowiedź bookera) na każdy z tych mechanizmów.
Albo, taniej i pewniej: **jedna rozmowa z bookerem**, który to robi.

**To jest pytanie, na które nie odpowie żaden model językowy.** Trzeba zapytać
człowieka.

---

## 6. Czy ktoś już to sprzedaje?

Sprawdzone 2026-08-14: Chartmetric, Soundcharts, Viberate, Next Big Sound,
Pollstar — wszystkie odpowiadają na pytanie *jak duży jest ten artysta*.
Żadne nie odpowiada na *co on faktycznie gra*.

**Zostało do sprawdzenia:** narzędzia dla samych bookerów i agencji, nie dla
artystów i wytwórni. Inny rynek, inne nazwy, prawdopodobnie inne ceny.

---

## 7. Czy analogia z galerią wytrzyma kontakt z kimś z rynku sztuki

Cała część II i III w KURATORZY.md to **moja konstrukcja**. Brzmi spójnie,
co jest osobnym powodem do nieufności.

**Odpowiedzią byłoby:** przeczytanie tego przez kogoś, kto pracuje w galerii
albo instytucji sztuki, i wskazanie miejsc, gdzie to jest naiwne. Analogia
ładna i fałszywa jest gorsza niż brak analogii, bo zamyka myślenie.

---

## Czego świadomie NIE ma na tej liście

**Wszystkiego, co wymaga posłuchania nagrania.** BPM, tonacja, długość
przejścia, typ szwu — osobny wątek, osobne narzędzia.

**Generatora line-upów.** Ustalone 2026-08-14: nie da się go zrobić sensownie,
bo prawdziwe ograniczenia bookera (dostępność, honorarium, pakiety agencyjne,
klauzule promienia, sponsorzy) **nie istnieją w danych publicznych**. Wracamy
do tego dopiero, gdy pytanie 5 dostanie odpowiedź od żywego bookera.
