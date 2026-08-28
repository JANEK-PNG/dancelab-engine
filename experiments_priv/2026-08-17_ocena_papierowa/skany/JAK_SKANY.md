# Skany ocen papierowych — jak je wrzucać

Zdjęcia i skany **zostają na dysku**, nie idą na GitHuba (`.gitignore` w tym
katalogu wypuszcza tylko ten plik).

**Gdzie:** dowolna nazwa, byle w tym katalogu. Najwygodniej jedna kartka =
jeden plik, nazwa mówiąca którą playlistę widać, np. `OCENA_C_str1.jpg`.

**Co z nimi robię:** przepisuję oceny 1–5 do
`SESJA_*_transition_ratings.csv` (kolumna `dj_mixability_rating`) i oceny
całych playlist do `oceny_playlist.csv`. Przy każdej ocenie, której nie
odczytam pewnie, pytam — **nie zgaduję**.

**Bramka zostaje zamknięta.** `analiza.py` nie ruszy, dopóki wszystkie 158
przejść nie ma oceny, a `PRZYDZIAL_NIE_OTWIERAC.json` (kto silnik, kto
kontrola) otwiera się dopiero po tej bramce. Progi są zarejestrowane w
`PLAN_ANALIZY.md` z 18.08 i po wpisaniu ocen wolno je tylko raportować.
