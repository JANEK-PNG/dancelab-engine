# Szew na strumieniu — progi (2026-09-11)

## Próba 1 (zapisana w `szew_sonda.py` przed uruchomieniem) — WYNIK
- (a) dwa odtwarzacze MusicKit naraz: **zdane** — A grał (stan 2) przez cały czas grania B, oba zalogowane, żadnego DEVICE_LIMIT.
- (b) rozrzut opóźnienia startu B w 5 próbach ≤ 469 ms: **NIE zdane** — 4123, 982, 988, 986, 957 ms → rozrzut 3166 ms.
  Pierwszy start był „na zimno" (pierwsze odtworzenie B). **Wersja szwu bez rozgrzewki odpada.**

## Próba 2 — nowa hipoteza, zapisana PRZED pomiarem
Hipoteza: po rozgrzewce (B raz zagrany ~1 s i zapauzowany, cicho) start B jest przewidywalny.
- Dwie pary utworów, po 5 startów B po rozgrzewce.
- **Kryterium:** w każdej parze rozrzut ≤ 469 ms (jedno uderzenie przy 128 BPM) i żaden start > 3000 ms.
- Nie zdane → szew na strumieniu nie powstaje; okno mówi uczciwie „Apple nie daje dźwięku do miksowania".
- Zdane → szew na żywo: B startuje wcześniej o zmierzone opóźnienie, tempo zgrane `rate_b`, faza tylko przybliżona — i tak ma być nazwane w oknie.
- Cicho: głośność 0 w obu odtwarzaczach.
