# Podgląd okna w przeglądarce (28.08)

Janek był na telefonie, Mac zablokowany, `screencapture` łapał ekran blokady.
Bez obrazu nie da się sprawdzić, czy ekran wygląda jak trzeba — a dwa razy
w tej sesji obraz złapał błąd, którego testy nie widziały.

**Co to jest.** `zrzut_danych.py` liczy dokładnie to, co liczy most GUI, i
zapisuje wynik do `dane.json`. `zbuduj_podglad.py` kopiuje PRAWDZIWE
`index.html`, `styl.css` i `app.js` (bez zmiany jednej litery) i dokłada
`stub.js` — udawany most, który oddaje zapisane odpowiedzi. Przeglądarka
rysuje więc ten sam kod, który rysuje okno.

**Czego to NIE jest.** To nie działa: nie zbudujesz tu setu i nie zapiszesz
cue do bazy. To jest wyłącznie obraz.

**Dwie rzeczy robione na potrzeby podglądu, jawnie:**

1. Filary wyłączone (`user_store.load_state → None`). Janek ma zaznaczony
   JEDEN filar, a reguła projektu wymaga trzech, więc każda budowa kończy się
   odmową. W oknie odmowa zostaje — podgląd ma pokazać ekran, nie obejść regułę.
2. Liczby zapisu policzone na KOPII `master.db`, bo Rekordbox był otwarty,
   a przy nim zapis na żywej bazie jest (słusznie) zablokowany.

**Jak odpalić**

    uv run python experiments_priv/2026-08-28_podglad_gui/zrzut_danych.py
    uv run python experiments_priv/2026-08-28_podglad_gui/zbuduj_podglad.py
    (cd experiments_priv/2026-08-28_podglad_gui/podglad && python3 -m http.server 8677)

**Co złapał 28.08** — trzy błędy, wszystkie niewidoczne dla testów:

* ekran Set ściskał się do 264 px z uciętą tabelą (znikająca lista zabierała
  swoją kolumnę w siatce, główny obszar wskakiwał na jej miejsce),
* pasek postępu zostawał na ekranie po zbudowaniu setu (`display:flex`
  wygrywał z atrybutem `hidden` — ta sama pułapka, co przy dwóch ekranach),
* podpowiedź na ekranie szwu mówiła, że zapis do Rekordboxa robi się „na razie
  w terminalu", choć od tego samego dnia robi się w oknie.
