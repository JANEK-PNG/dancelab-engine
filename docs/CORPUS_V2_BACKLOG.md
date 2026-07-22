# Korpus v2 — backlog (po dokończeniu obecnego korpusu + kalibracji bramki BPM)

Zaparkowane świadomie 2026-07-17. Kolejność: dokończ 1857 → kalibracja
oktawy → potem to. Nie zaczynać, dopóki darmowe dane się ściągają.

## 1. Transition Reverse-Engineering (priorytet wyższy — głębsza wiedza z danych, które JUŻ mamy)

Pomysł Janka: mając miks + track A + track B, odzyskaj JAK DJ je zmiksował
(odwrotność naszego automiksu TransitionSimulationView).

- Warunek wstępny: alignment DTW (JUŻ produkujemy — mówi GDZIE A, B siedzą).
- KLUCZOWE: naiwny "difference" (miks − A − B) NIE działa. Miks to
  `fader_A(t)·[EQ_A·A] + fader_B(t)·[EQ_B·B]` ze zmiennymi w czasie,
  nieznanymi gainami i 3-pasmowym EQ. Prawdziwy prymityw = ROZWIĄZAĆ dla
  gainów (least squares / convex optimization per klatka per pasmo).
- Uwaga Janka (trafna): w strefie nakładania bywają 3 tracki (ogon
  poprzedniego + obecny + głowa następnego) — estymacja musi to uwzględnić.
- Prior art (ci sami autorzy, mir-aidj): `transition-analysis` (NIME 2021,
  sub-band + convex opt), `djmixer-estimation` (DAFx 2022, joint fader+EQ).
  PRZECZYTAĆ przed budową, nie wynajdywać.
- Wynik: obiektywne ETYKIETY typu przejścia z realnych miksów (bass swap /
  cięcie / długi blend EQ). Karmi: priory silnika + PRZEJŚCIA (portret =
  styl blendu) + walidację naszego automiksu.

## 2. Rozszerzenie zakresu 2022-2026 (źródło: 1001Tracklists — decyzja Janka 2026-07-17)

Obecny dataset (mir-aidj) zamrożony na 2022 → mixy do ~2021. Rozszerzenie:
- Źródło metadanych: 1001Tracklists (jak inni; NIE budujemy ślepego
  rozpoznawania — fingerprinting/blind ID pada na dubplatach, ~70% max, i
  to research na lata). MixesDB też żywy (wrócił 2024) jako zapas.
- Do dobudowy: scraper tracklist + resolver track→YouTube-ID (yt-dlp search,
  wybór najlepszego trafienia — nowa, błędogenna warstwa).
- Reszta (download, cechy, DTW, cue) — mamy w 100%.
- GŁÓWNY powód: świeżi ulubieńcy Janka poza datasetem — Anish Kumar (#5,
  za nowy), aktualne sety Four Teta/O'Flynna. Warunek dla "influence pack"
  i PRZEJŚCIA obejmujących AKTUALNych mistrzów, nie tylko sprzed 2021.

## Odrzucone (świadomie)

- Ślepe rozpoznawanie tracków w miksie bez tracklisty (fingerprinting jako
  główna droga). Powód: ta sama ściana co niski match Four Teta — dubplaty
  i niewydane edity nie istnieją w żadnej bazie. Nasz aligner DTW pozostaje
  metodą rozpoznania "z kandydatami" + do weryfikacji i precyzji cue.
