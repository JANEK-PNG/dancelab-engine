# Research 02 — enkodowanie resztki (warstwa 3 płótna szwu)

Data: 2026-08-20. Pytanie: jaką formę dać `residual`, żeby nie skłamać.

## Co to jest (z kodu, `scripts/seam_decompose.py::fit_gains`)

Na każde pasmo i blok czasu dopasowanie NNLS: moc miksu ≈ w_A·moc(A) +
w_B·moc(B). `residual` = ‖M − Xw‖ / ‖M‖ — **znormalizowany ułamek energii
miksu, którego nie tłumaczy żaden z dwóch utworów** przy najlepszym możliwym
ustawieniu ich głośności. To obcy głos: sampler, efekty, powietrze, błąd
dopasowania. Rozkład na 23 szwach: mediana ~0,6, kwartyle 0,4–0,8, pełny
zakres 0–1 (wysoka podłoga jest własnością pomiaru, nie rysujemy jej w dół).

## Dlaczego NIE trzecia linia

`a`/`b` to wzmocnienia amplitudy (fader), `residual` to ułamek niewyjaśnienia
dopasowania — **inna wielkość fizyczna**. Ta sama oś i ten sam język wizualny
(linia w pozycji) twierdziłyby, że to trzeci fader — fałsz semantyczny, ta
sama klasa błędu co „deterministic construal" z Research 01. Konwencja
statystyczna od zawsze trzyma resztę OSOBNO (panel reszt pod dopasowaniem,
wspólna oś czasu, własna skala).

## Wybrany kanał: wstęga luminancji pod każdym piętrem

Wg rankingu skuteczności kanałów Munzner (Visualization Analysis & Design,
rozdz. 5 — pozycja > długość > kąt > pole > luminancja/nasycenie; slajdy
autorki: cs.ubc.ca/~tmm/courses/436V-20/slides/marks-4x4.pdf):

* pozycję (najsilniejszy kanał) REZERWUJEMY dla obecności A/B — tam potrzebna
  precyzja odczytu;
* resztka dostaje **luminancję**: świadomy krok w dół hierarchii, bo jej
  zadaniem jest mówić „tu działo się coś spoza utworów — przybliż", a nie
  być odczytywaną co do setnej;
* wstęga 12 px pod pasem piętra, wspólna oś czasu (konwencja panelu reszt),
  czerń 0 → biel 1, liniowo, bez odejmowania podłogi (surowość);
* barwy NIE dostaje (bursztyn=A, błękit=B, volt=rdzeń — języka kolorów nie
  rozmywamy; neutralna biel nie twierdzi przynależności);
* skala wstęgi jest stała 0–1 i NIE reaguje na zoom osi Y (to ułamek, nie
  amplituda) — reaguje tylko na oś czasu.

Odrzucone po drodze: wypełnienie pod krzywymi (ta sama oś = to samo
kłamstwo), tekstura (najsłabszy kanał, szum przy 426 ramkach), osobne pełne
pasy reszt (podwaja wysokość, a precyzja niepotrzebna).
