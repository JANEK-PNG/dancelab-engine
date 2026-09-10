# Co daje konto deweloperskie Apple w sprawie Apple Music — i co z tego dla DanceLab

**Data:** 2026-09-10. Źródła: dokumentacja Apple (Apple Music API, MusicKit, ShazamKit,
Apple Music Feed — czytane przez `developer.apple.com/tutorials/data/...json`), plus trzy
pomiary na koncie Janka tego dnia. Zaloguj-się-i-przejmij-Chrome nie było potrzebne:
dokumentacja jest publiczna.

## Twarde granice (najpierw, żeby nie budować na piasku)

| Nie ma | Skutek |
|---|---|
| **Surowego audio** pełnych utworów — odtwarzanie tylko przez odtwarzacz MusicKit (DRM) | tempo, siatka, tonacja, CLAP dla strumieni nadal wyłącznie z 30-sekundowej próbki |
| **BPM ani tonacji** w `Songs.Attributes` | Apple nie liczy tego za nas |
| **Podgatunków** — jeden `genreNames[0]` na utwór; pomiar: Electronic + Dance = 56 % biblioteki | patrz parasol, `core/style_labels.py` |
| **Apple Music Feed** poza promocją Apple Music — licencja wprost zabrania „zasilania wewnętrznych narzędzi" i „analizy informacji o muzyce" | nie dotykać |
| MusicKit (Swift), ShazamKit — tylko Swift/ObjC | z Pythona przez osobny mały pomocnik na macOS |

## Co jest — z pomiarem, gdzie go zrobiłem

| Możliwość | Token | Zmierzone / stan | Dla DanceLab |
|---|---|---|---|
| **Biblioteka użytkownika**: utwory, playlisty, ulubione, historia, Replay | użytkownika | **10 286 utworów, 150 playlist; 99,4 % strumieni z rekordboxa ma wpis** (`apple_music_biblioteka.py`) | zrobione — `data/reports/apple_library.json` |
| **Zapis**: nowa playlista w bibliotece + dopisanie utworów (`POST /v1/me/library/playlists`, 201; `/tracks`, 204) | użytkownika | endpointy potwierdzone w dokumentacji, nie użyte | **set → playlista Apple Music**; rekordbox widzi playlisty Apple Music, więc set trafia do rekordboxa **bez pisania do master.db** — droga zgodna ze STRAŻNIKIEM |
| **ISRC → katalog** (`filter[isrc]`, do wielu naraz) | deweloperski | **207 z 272 plików lokalnych ma ISRC w tagu; 17 z 25 próbki rozwiązuje się w katalogu (68 %)** | jedna tożsamość utworu między plikiem a strumieniem: dedup, okładka, próbka, gruby gatunek dla 211 plików bez gatunku |
| Katalog: wyszukiwanie, `genreNames`, `isrc`, `releaseDate`, `previews`, `artwork`, `audioVariants`, `editorialNotes`, wytwórnie, kuratorzy | deweloperski | działa (test 200 na `/catalog/pl`) | już używamy próbek przez publiczne API; tu to samo bez limitu 20/min |
| **Rekomendacje**, **ostatnio grane**, **Replay** | użytkownika | w dokumentacji, nie użyte | sygnał „co Janek naprawdę gra" obok rejestru; kandydaci spoza biblioteki |
| **Charts** po gatunku/kraju (`/catalog/{sf}/charts?genre=`) | deweloperski | w dokumentacji | zewnętrzny prior popularności — osobny pomiar, czy coś wnosi (RAVEFORM_PRIORS) |
| **MusicKit na Web** — odtwarzanie pełnych utworów w przeglądarce dla subskrybenta | oba | działa w Safari (autoryzacja przeszła); **w oknie DanceLab (WKWebView, `file://`) zmierzone 2026-09-10: FairPlay jest, logowanie tokenem przez adres strony działa, pełny utwór zagrał (434 s, nie próbka); logowanie przez wyskakujące okno Apple nie działa (pywebview blokuje `window.open`)** | odsłuch 82 % kolekcji w oknie zamiast 30 s próbki — jeśli WKWebView przepuści DRM |
| **MusicKit (Swift)**: `ApplicationMusicPlayer`, `MusicLibrary`, subskrypcja, oferty | oba | dokumentacja | dopiero przy natywnej apce / Mac App Store |
| **ShazamKit**: `SHCustomCatalog` z własnych nagrań, dopasowanie z zaszumionego audio | brak | dokumentacja | **nagranie setu → lista utworów z czasem** z sygnatur WŁASNEJ biblioteki; A3 (ślepe wykrywanie szwów) było odrzucone — to inna rzecz (identyfikacja, nie szew), ale decyzja Janka |

## Ranking — co posuwa produkt, od najtańszego

1. **Set → playlista Apple Music.** Dwa endpointy, token już jest. Zysk: set widoczny w Apple Music i w rekordboxie przez jego integrację, zero ryzyka dla master.db. Test: czy rekordbox pokazuje nową playlistę po odświeżeniu. ~pół dnia.
2. **Most ISRC.** 68 % plików dostaje tożsamość katalogową → dedup plik/strumień, okładki, próbki, gruby gatunek. Reguła: gatunek z Apple wchodzi jako `apple` tylko poza parasolem (już zaimplementowane w `attach_apple_genres`; brakuje tylko mapowania ISRC → `apple-music:tracks:ID`). ~pół dnia.
   **Zbudowane 2026-09-10 (`scripts/apple_isrc_most.py`, `ingestion/isrc_bridge.py`), zmierzone:** 211 z 272 plików ma ISRC w tagu (WAV 0 z 25); 161 unikalnych ISRC, 128 rozwiązanych w katalogu `pl` (80 %); **171 z 272 plików ma tożsamość katalogową**, 101 z nich to bliźniaki strumieni już obecnych w puli. **Gatunek zyskało tylko 8 ze 121 plików bez gatunku** — 34 dostają z Apple sam parasol (Electronic/Dance) i reguła parasola je odrzuca. Obietnica „gruby gatunek dla 211 plików" z tej listy była przeszacowana; realny zysk mostu to tożsamość (playlista Apple, dedup), nie gatunek.
3. **Odsłuch strumieni w oknie.** Najpierw 30-minutowy test: MusicKit JS w WKWebView (pywebview) — gra czy nie. Jeśli gra: odsłuch pełnych utworów dla 82 % kolekcji. Jeśli nie: zostaje 30 s i trzeba to powiedzieć. **Zmierzone 2026-09-10 (`experiments_priv/2026-09-10_musickit_okno/`): gra.** Pełny utwór w oknie pywebview na `file://`, zalogowanym tokenem Janka przekazanym przez adres strony. Otwarte: kraj sklepu (MusicKit bez podanego kraju bierze `us`, Janek ma `pl`) i wpięcie do prawdziwego okna.
4. **Ostatnio grane + Replay** jako źródło do rejestru — tani odczyt, wartość do zmierzenia przeciw ocenom papierowym.
5. **ShazamKit na nagraniu setu** — wymaga pomocnika w Swift i decyzji wobec A3.
6. **Charts** — prior, tylko po pomiarze.

## Czego to nie zmienia

Silnik nie dostanie od Apple ani tempa, ani tonacji, ani podgatunków, ani audio. Wszystko
powyżej to **identyfikacja, dystrybucja i odsłuch**, nie analiza. Analiza zostaje nasza.
