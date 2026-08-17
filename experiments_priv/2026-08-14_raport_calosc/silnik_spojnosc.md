# Przekrój: SPÓJNOŚĆ I DŁUG — te same rzeczy robione na dwa sposoby

Repo: `/Users/jantrybus/Developer/dancelab-engine`. Wszystkie liczby oznaczone **[pomiar mój]** policzyłem dziś na realnych danych; reszta pochodzi z komentarzy w kodzie.

**Pula, na której pracuje aplikacja**, to `experiments_priv/2026-07-30_rebuild/processed` (stała `PROCESSED_DEFAULT`, `src/dancelab/tui/app.py:56`) — 8261 analiz. Rozkład ścieżek **[pomiar mój]**: 7910 strumieni `apple-music:`, 325 ścieżek bezwzględnych (247 plików istnieje, 78 nie), **25 ścieżek WZGLĘDNYCH**, 1 pusta. Te 25 względnych ścieżek to oś połowy poniższych rozjazdów.

---

## 1. Wczytywanie audio — pięć niezależnych dróg

| gdzie | czym | co robi inaczej |
|---|---|---|
| `src/dancelab/ingestion/loader.py:23` (`load_audio`) | librosa | jedyna droga, która **sprawdza rozszerzenie** (`:31`) i wymusza `config.audio.sample_rate` + mono (`:43`); **nie robi** `expanduser()` |
| `src/dancelab/preview/transition_simulation.py:414` (`_read_audio_segment`) | librosa | `expanduser()` (`:424`), `mono=False`, własny `offset`/`duration`, **zero kontroli rozszerzenia** |
| `src/dancelab/stems/extractor.py:134` (`_stereo_source`) | soundfile | dociąga prawdziwe stereo z pliku; przy jakimkolwiek wyjątku **cicho** wraca do zdublowanego mono (`:137 except Exception: pass`) |
| `src/dancelab/cli/tui.py:249` (`_snippet`) | soundfile | wycina 20 s do odsłuchu w pokoju przejść; przy wyjątku **zwraca None bez powodu** (`:251`) |
| `src/dancelab/validation/djmix/__main__.py:31` (`_load_audio`) | librosa | trzecia kopia tego samego, z `path.resolve()` w `source_path` |

Do tego cztery zestawy dozwolonych rozszerzeń: `loader.py:17-20` (10 pozycji), `validation/djmix/checkpoint.py:25` (dokłada `.aac`, gubi `.mp4`), `scripts/brief_set.py:56` (6 pozycji), a `validation/djmix/model_gate.py:33` jako jedyny robi to poprawnie — liczy sumę dwóch zbiorów.

**Ryzyko realne, dziś uśpione.** `soundfile` w tym środowisku (libsndfile 1.2.2) **nie umie M4A/MP4/WEBM/OPUS** **[pomiar mój]**, a `loader.SUPPORTED_EXTENSIONS` te formaty dopuszcza. Silnik przeanalizuje `.m4a`, ale `_stereo_source` odpadnie bez śladu i separacja dostanie zdublowane mono — czyli dokładnie to, co komentarz w `extractor.py:121-124` opisuje jako błąd 11-12 % (perkusja, bas) i 35-40 % („other", wokal). Dziś lokalna pula to wyłącznie `.mp3` (69), `.aiff` (151), `.wav` (25), `.aif` (2) **[pomiar mój]**, więc nic nie boli. Ale korpus M11 to 2275 plików `.webm` i 222 `.m4a` (wg `data/reports/revealed_repertoire/gate.json`) — tam ta ścieżka jest martwa od pierwszego dnia i nikt się o tym nie dowie.

---

## 2. Dopasowywanie utworów po nazwie i ścieżce — sześć różnych reguł

Trzy reguły dopasowania utworu do wiersza w Rekordboxie:

- `src/dancelab/ingestion/rekordbox_match.py:26` — `os.path.normcase(os.path.normpath(p))`, **bez NFC**, potem tytuł+wykonawca, potem sam tytuł (`:88-92`), każdy tylko przy jednym kandydacie.
- `src/dancelab/tui/cue_zapis.py:37` (`mapa_content_id`) — **tylko NFC pełnej ścieżki**, żadnego zapasowego dopasowania.
- `src/dancelab/ingestion/playlist_publish.py:92-105` — NFC ścieżki, potem „bliźniak" po `_norm_title(stem)` (`:35`), tylko przy jednym kandydacie. `rekordbox_lookup.py:18` importuje te dwie funkcje — jedyne miejsce, gdzie ktoś nie przepisał kodu, tylko go użył.

**To jest najpoważniejszy rozjazd w całym przekroju, bo obie drogi kończą się ZAPISEM do biblioteki Janka.** CLI `dancelab cues write` używa `match_tracks` (`src/dancelab/cli/cues.py:144`), TUI klawisz `W` używa `mapa_content_id` (`src/dancelab/tui/app.py:1420`). Ta sama paczka cue, dwa różne zestawy trafionych utworów.

**Pomiar na żywej kolekcji [pomiar mój]:** 8250 wierszy w Rekordboksie, 309 ścieżek lokalnych, 61 z polskimi/obcymi znakami — wszystkie 61 zapisane w NFC. Nasze 325 ścieżek bezwzględnych trafia:
- regułą `rekordbox_match` (bez NFC): **266**
- regułą NFC (`cue_zapis` / `playlist_publish`): **268**

Dwa utwory gubione **wyłącznie** przez brak NFC: `…/Lekcja nr6.5/Wost, Entranas - Selvática (Pangaea Remix).aiff` i `…/HOT WEEKEND IN EUROPE/Âme, Busiswa - Pha Na Pha - 01 Pha Na Pha.aiff`. Nasz magazyn trzyma je w NFD, Rekordbox w NFC. To nie jest tylko „dwa pominięte utwory": obie spadają na dopasowanie po samym tytule, a biblioteka ma zmierzone 222 nadmiarowe wpisy w 159 grupach (`src/dancelab/tui/duplikaty.py:8-10`) — czyli tytuł może wskazać INNĄ kopię tego samego utworu, w innym folderze, z innym ContentID. Wtedy cue ląduje na złym pliku i weryfikacja tego nie złapie, bo sprawdza (utwór, pad, pozycja, komentarz), a nie „czy to ten plik, o który chodziło". Pamięć projektu mówi wprost: *łączyć po NAZWIE pliku + NFC, nigdy po ścieżce* — `rekordbox_match.py` robi odwrotnie w obu punktach.

Trzy dalsze, niezależne normalizatory nazw:
- `src/dancelab/tui/duplikaty.py:31` (`klucz`) — NFC + casefold + wycięcie nawiasów + tylko `[0-9a-zà-ɏ]`; kluczuje **scalanie widoku biblioteki**.
- `src/dancelab/tui/dj_profile.py:44` — NFC + casefold + strip; kluczuje **karty DJ-ów**.
- `src/dancelab/ingestion/artwork_sync.py:49` (`_pasuje`) — sprowadza do samych liter i cyfr i sprawdza **zawieranie podciągu w obie strony**. Nagłówek modułu (`:8-11`) obiecuje „TYLKO przy pewnym dopasowaniu", a kod dopasuje wykonawcę „Air" do „Airbase" i „Air France". Skutek: cudza okładka wgrana na stałe w tag pliku i pokazana na ekranie CDJ-a. **Realny błąd, choć nie niszczy danych.**

Do kompletu: pomocnik `_nfc` jest przepisany w sześciu plikach (`analysis_enrichment.py:41`, `rekordbox_import.py:47`, `playlist_publish.py:31`, `rekordbox_siatka.py:29`, `cue_zapis.py:33` plus wersja wpisana wprost w `rekordbox_phrases.py:171`).

---

## 3. „Utwór bez pliku" — trzy reguły, trzy różne odpowiedzi o TYM SAMYM utworze

| gdzie | reguła |
|---|---|
| `src/dancelab/tui/zrodlo.py:35` | prefiks `apple-music:` → Apple; inaczej `Path(sp).exists()` → dysk; inaczej brak (trzy kategorie) |
| `src/dancelab/tui/duplikaty.py:52-62` | `not startswith("apple-music:")` **i** `exists()` → „na dysku" |
| `src/dancelab/tui/app.py:1087-1098` (`_bez_pliku`) | `not sciezka.startswith("/")` → „to strumień, nie ma pliku" |
| `src/dancelab/tui/app.py:3032` (higiena puli) | `not sciezka.startswith("/")` → **przepuść bez żadnych sprawdzeń** |
| `src/dancelab/ingestion/loader.py:29` | `not p.exists()` → `IngestionError` |

Komentarz w `app.py:3017` twierdzi: *„Kryterium jest to samo, co przy odmowie odsłuchu"*. Jest to samo co `_bez_pliku`, ale **nie jest to samo, co `zrodlo.py` ani `duplikaty.py`** — a wszystkie trzy rysują ten sam wiersz tabeli.

**To już się dzieje, zmierzone [pomiar mój].** 25 utworów w puli ma ścieżki względne (`experiments_priv/2026-08-04_pula_set/…`). Wszystkie 25 plików **istnieją**. Dla każdego z nich:
- kolumna „źr." pokazuje **▣ Na dysku** (`zrodlo()` zwraca `dysk`),
- `duplikaty._ranga` uznaje je za „na dysku" i promuje na przedstawiciela grupy,
- naciśnięcie **P** (odsłuch, `app.py:3849`), **P** w edytorze cue (`app.py:1364`) i **C** (szew, `app.py:1232`) odmawia komunikatem: *„nie ma pliku na dysku (utwór ze strumienia) — zagrasz go w Rekordboksie"*.

Jednocześnie higiena puli (`app.py:3032`) wychodzi z gałęzi „źródło bez pliku — w porządku" **zanim** dojdzie do sprawdzenia stemów i istnienia pliku. Czyli plik `vocals.mp3` ze ścieżką względną wjedzie do setu — to jest dokładnie ta awaria, którą opisuje komentarz w `app.py:57-59` („vocals wylądowało w secie Janka DWA RAZY, pozycje 18 i 19"). Dziś nie ma takiego przypadku (0 stemów wśród 25 względnych, 16 stemów ma ścieżki bezwzględne i jest łapanych) **[pomiar mój]** — ale bezpiecznik jest wyłączony dla całej tej klasy wpisów.

Ta sama pułapka czeka na ścieżki z tyldą: `~/Music/…` przejdzie `expanduser()` w podglądzie (`transition_simulation.py:424`) i w preflight (`preflight.py:57`), a `_bez_pliku` i `loader.load_audio` uznają ją odpowiednio za strumień i za nieistniejący plik. Dziś takich wpisów nie ma **[pomiar mój]**.

---

## 4. Filtrowanie puli — cztery sita, dwa progi długości, jedna nazwa na dwie rzeczy

| droga | co odsiewa |
|---|---|
| `workflows/smart_playlist.py:66-73` (`discover_audio_files`) | rozszerzenie + `suspicious_path_reason` (stem w nazwie, folder `recordings`). **Bez progu długości, bez ffprobe.** |
| `tui/app.py:2823` i `:3072` | to samo **plus** `bramkarz.przesiej` (ffprobe) — jedyne dwa wywołania bramkarza w repo |
| `tui/app.py:3022-3040` (higiena puli) | `MAX_TRACK_SEC` = **15 min** (`app.py:60`), nazwy stemów, istnienie pliku. Nie sprawdza folderu `recordings`. |
| `scripts/brief_set.py:66-67` | `suspicious_path_reason` + `suspicious_duration_reason` — próg **10 min** (`preflight.py:25`) |
| `api/security.py:252-258` | tylko rozszerzenie + limit liczby plików |

Dwa progi na to samo pojęcie („to za długie, żeby być płytą"): 10 minut w `preflight.py:25`, 15 minut w `app.py:60`. **Pomiar na realnej puli [pomiar mój]:** 139 utworów dłuższych niż 10 minut, 24 dłuższe niż 15 — czyli **115 utworów leży w szarej strefie**, którą jedna droga produktu odrzuca, a druga wpuszcza (m.in. „Hold On Tight (Nalin & Kane Remix)" 12,5 min, „Nuits Sonores" 11,9 min). Nie umiem rozstrzygnąć, który próg jest słuszny — ale nie mogą być oba, a żaden komentarz nie mówi, że rozbieżność jest celowa.

Zbiór nazw stemów zdefiniowany dwa razy, identycznie: `preflight.py:28` i `app.py:59`.

Osobno drobiazg czytelności: **`przesiej` znaczy dwie zupełnie różne rzeczy** — `ingestion/bramkarz.py:45` (odsiew uszkodzonych plików) i `decision/sito_brzmienia.py:90` (zawężenie puli do kotwicy brzmieniowej, wołane z `set_builder.py:1353`).

---

## 5. Ścieżki do dźwięku — trzy korzenie, wszystkie inne

- `src/dancelab/tui/seam_preview.py:19` → `data/cache/seam_preview` (**względna**)
- `src/dancelab/ingestion/loudness.py:17` → `data/cache/lufs.json` (**względna**)
- `src/dancelab/tui/app.py:70` → `data/cache/tui_historia_setow.jsonl` (**względna**)
- `src/dancelab/stems/envelopes.py:74` → `data/cache` (**względna**)
- `src/dancelab/cli/tui.py:242, :333` → `~/.dancelab/snippets`, `~/.dancelab/seams`
- `src/dancelab/storage/cache_manager.py:46` → `~/Library/Application Support/DanceLab/cache` — **jedyny korzeń z limitem 10 GB i sprzątaniem, i jedyny, którego nikt nie używa** (brak wywołań `cache_manager_for` poza definicją).

Wszystko poza `~/.dancelab` działa tylko dlatego, że `DanceLab.command:22` robi `cd` do korzenia repo. Ten sam wzorzec dotyczy `experiments_priv/2026-08-04_werdykty` (`app.py:66`) i rejestru cue.

Katalog analiz Pioneera zapisany cztery razy: `rekordbox_grid_snap.py:55` (`DEFAULT_SHARE`), `rekordbox_import.py:41` i `rekordbox_siatka.py:23` (`KATALOG_ANALIZ`), `rekordbox_phrases.py:41` (`SHARE`). Te same pliki `.DAT` czyta czterema różnymi API: `read_anlz_files` (`rekordbox_grid_snap.py:90`), `AnlzFile.parse_file` + `getall_tags` (`rekordbox_siatka.py:37-39` oraz `rekordbox_import.py:62-63`), `get_tag` (`rekordbox_phrases.py:106`). **Skutek praktyczny:** przyciąganie cue do siatki Rekordboxa w linii poleceń idzie przez `rekordbox_grid_snap`, a w edytorze TUI przez `rekordbox_siatka` (`app.py:1104` → `downbeaty_dla_sciezki`, `rekordbox_siatka.py:78`). Rozbieżność między nimi objawi się jako „w konsoli cue stoi w innym miejscu niż na ekranie".

---

## Co realnie grozi błędem, a co jest kosmetyką

**Naprawić w pierwszej kolejności (może uszkodzić bibliotekę albo dać zły wynik):**

1. **`rekordbox_match._norm_path` bez NFC** (`rekordbox_match.py:26`) — dwa zmierzone utwory spadają na dopasowanie po tytule, a przy 159 grupach duplikatów tytuł może wskazać inną kopię i cue pojedzie na zły plik. Naprawa to jedna linia: dołożyć `unicodedata.normalize("NFC", …)`, najlepiej importując `_nfc` tak, jak zrobił to `rekordbox_lookup.py:18`.
2. **Higiena puli przepuszcza wszystko, co nie zaczyna się od `/`** (`app.py:3032`) — bezpiecznik przeciw stemom i za długim plikom jest wyłączony dla 25 wpisów w dzisiejszej puli. Naprawa: rozstrzygać po `zrodlo.zrodlo()`, nie po pierwszym znaku ścieżki.
3. **Trzy sprzeczne odpowiedzi o tym samym utworze** (`zrodlo.py:35` vs `duplikaty.py:52` vs `app.py:1098`) — DJ widzi ikonę „na dysku" i dostaje odmowę „to strumień". Naprawa: `zrodlo.zrodlo()` zostaje jedynym sędzią, dwa pozostałe miejsca go wołają.
4. **`artwork_sync._pasuje` po zawieraniu podciągu** (`artwork_sync.py:49`) — obiecuje pewne dopasowanie, robi luźne, a wynik zapisuje na stałe w tagu pliku Janka.
5. **Dwie drogi zapisu cue rozjeżdżają się nie tylko dopasowaniem** — CLI woła `snap_plan_to_rekordbox_grid` (`cli/cues.py:152`) i **nie** dopisuje do rejestru UUID, TUI dopisuje (`app.py:1478`) i przyciąga siatkę wcześniej, innym czytnikiem. Przy następnym zapisie cue postawione z konsoli zostaną uznane za cudze i zablokują odświeżenie — czyli wróci błąd, dla którego rejestr powstał 09.08.

**Naprawić, bo daje niepowtarzalne wyniki, ale nie niszczy danych:**

6. Dwa progi długości (10 vs 15 min) — 115 utworów decydowanych inaczej zależnie od drogi.
7. `_stereo_source` cicho wraca do zdublowanego mono (`extractor.py:137`) — dziś uśpione na bibliotece Janka, aktywne na całym korpusie `.webm`/`.m4a`.
8. Cztery czytniki PQTZ — dwie drogi produktowe dochodzą do pozycji cue różnym kodem.
9. Ścieżki względne we wszystkich cache'ach — działa wyłącznie dzięki `cd` w launcherze; `dancelab cues write` odpalone z innego katalogu zobaczy **pusty rejestr cue**.

**Kosmetyka (uporządkować przy okazji, nic nie grozi):**

10. Sześć kopii `_nfc`, cztery stałe wskazujące ten sam katalog `share`, dwa identyczne zbiory `STEM_NAMES`, cztery listy dozwolonych rozszerzeń audio.
11. Nazwa `przesiej` na dwie różne funkcje (`bramkarz.py:45` i `sito_brzmienia.py:90`).
12. Pięć osobnych sposobów wczytania audio — same w sobie poprawne, ale bez wspólnego miejsca każda przyszła poprawka (np. `expanduser`) trafi tylko do jednego z nich; ta sama pułapka co przy `_nfc`.

**Rzecz osobna, wykryta przy okazji:** `storage/cache_manager.py` (361 linii, limit 10 GB, wyrzucanie najstarszych) nie ma ani jednego wywołania w `src/` i `scripts/`, podczas gdy `~/.dancelab/seams` i `data/cache/seam_preview` rosną bez żadnego ograniczenia. Gotowe rozwiązanie leży obok problemu i nie jest podłączone.