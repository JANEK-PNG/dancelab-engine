# Czy powroty do utworu to technika powszechna, czy chwyt Janka?

**Zapisane 2026-08-28 PRZED zapytaniem do bazy.**

## Skąd pytanie

Na dwóch setach Janka powroty to **19% pozycji** (7 z 37), z regularnym
wzorcem: przerwa ~4,5 min, jeden utwór pomiędzy, drugie zagranie 42% krótsze.
n = 7, jeden DJ — za mało, żeby przebudowywać planer silnika.

Baza ma **42 904 pozycje tracklist** z map festiwalowych. Jeśli powroty są
powszechne, warto uczyć ich silnik. Jeśli to specjalność Janka, silnik ogólny
ich nie potrzebuje i zostają w jego prywatnym profilu.

## Co mierzę

Powrót = ten sam utwór na **dwóch różnych pozycjach w tym samym secie**
(`link_setu`), rozpoznany po `utwor_id` z dopasowania — nie po surowym tytule,
żeby nie liczyć różnych wersji jako jednej.

Liczę: ile setów ma choć jeden powrót, ile powrotów przypada na set, jaki
odstęp w pozycjach.

## Próg

* **POWSZECHNE** — powroty ma **≥ 10% setów**. Wtedy to technika, nie
  osobliwość, i planer powinien ją znać.
* **CHWYT JANKA** — **< 3% setów**. Zostaje w jego profilu, silnik ogólny bez
  zmian.
* **NIEROZSTRZYGNIĘTE** — między 3% a 10%. Zapisuję liczbę i nie przebudowuję
  planera na jej podstawie.

## Pułapka, na którą uważam

Tracklisty korpusu są zbierane z serwisów i **mogą zawierać ten sam utwór
wpisany dwa razy przez pomyłkę** albo pozycje bez czasu, które trafiły w złej
kolejności. Powtórka na **sąsiednich** pozycjach (odstęp 1) jest podejrzana —
u Janka odstęp wynosił zawsze 2 lub 3. Raportuję rozkład odstępów osobno i nie
wliczam sąsiednich do wyniku głównego.
