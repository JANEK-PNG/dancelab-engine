# FLX4 → 2× CDJ-3000 + DJM-900NXS2: co się tłumaczy, a co nie

Decyzje Janka 28.08: odwzorowujemy **CDJ-3000** (nie 3000X — w klubach go jeszcze
nie ma) i **DJM-900NXS2** (standard riderowy). Oba decki FLX4 sterują dwoma
CDJ-ami, sekcja miksująca FLX4 steruje DJM-em.

Źródło mapowania FLX4: `experiments_priv/2026-08-23_flx4_mapowanie/NOTATKI_INSTRUKCJA.md`
— zmierzone na sprzęcie 23.08, nie przepisane z PDF.

**Stan:** czekam na instrukcje CDJ-3000 i DJM-900NXS2 (Janek pobiera).
Wszystko poniżej opisuje FUNKCJE, nie geometrię. Pozycje i wymiary dojdą
z rysunków technicznych, tak jak przy FLX4 (siatka mm, 1000 dpi).

## 1. Deck: FLX4 → CDJ-3000

| co robię na FLX4 | MIDI (zmierzone) | co się dzieje na CDJ-3000 |
|---|---|---|
| PLAY/PAUSE | nuta 11, kanał decka | PLAY/PAUSE |
| CUE | nuta 12 | CUE |
| jog talerz (vinyl ON) | CC 34, względne | jog w trybie VINYL — scratch |
| jog talerz (vinyl OFF) | CC 35, względne | jog w trybie CDJ — bend |
| jog bok | CC 33, względne | bok talerza — bend tempa |
| jog dotyk | nuta 54 | dotyk płyty (czujnik pojemnościowy) |
| TEMPO | CC 0/32, 14-bit | suwak TEMPO |
| BEAT SYNC | nuta 88 (przy PUSZCZENIU) | BEAT SYNC |
| IN / OUT | nuty 16 / 17 | LOOP IN / LOOP OUT |
| 4 BEAT / EXIT | nuta 77 | AUTO BEAT LOOP / EXIT |
| CUE/LOOP CALL ◁ ▷ | nuty 81 / 83 | CALL ◁ ▷ |
| pady HOT CUE | nuty 27 + indeks, kanał 8/10 | HOT CUE A–H (osiem, nie cztery) |
| LOAD deck 1 / 2 | nuty 70 / 71, kanał 7 | LOAD na wybrany odtwarzacz |
| BROWSE obrót / press | CC 64 / nuta 65, kanał 7 | pokrętło ROTARY SELECTOR + ekran dotykowy |

## 2. Mikser: FLX4 → DJM-900NXS2

| co robię na FLX4 | MIDI (zmierzone) | co się dzieje na DJM-900NXS2 |
|---|---|---|
| TRIM | CC 4/36, 14-bit | TRIM kanału |
| EQ HI / MID / LOW | CC 7/39, 11/43, 15/47 | EQ trzypasmowy (ten sam układ) |
| CH FADER | CC 19/51 | fader kanału |
| CROSSFADER | CC 31/63, kanał 7 | crossfader |
| CH CUE | nuta 84 | CUE kanału (słuchawki) |
| MASTER CUE | nuta 99, kanał 7 | MASTER CUE |
| MASTER LEVEL | CC 8/40, kanał 7 | MASTER LEVEL |
| HEADPHONES MIX / LEVEL | CC 12/44, 13/45 | MIXING / LEVEL |
| CFX (deck 1/2) | CC 23/55, 24/56, kanał 7 | **przybliżenie** → SOUND COLOR FX |
| BEAT FX (SELECT, BEAT ◁▷, ON/OFF, LEVEL/DEPTH) | kanał 5/6 | BEAT FX (ta sama rodzina efektów) |

## 3. Czego na FLX4 NIE MA — i to jest najważniejsza część

To jest odpowiedź na pytanie „czego nie nauczę się na kontrolerze za 1/40 ceny".
Symulator ma te rzeczy **pokazywać jako nieaktywne z wyjaśnieniem**, a nie
udawać, że ich nie ma.

**Na CDJ-3000, czego FLX4 nie ma:**
- ekran dotykowy 9" z falą, siatką i przeglądaniem — FLX4 nie ma żadnego ekranu;
- **osiem** hot cue zamiast czterech (pady FLX4 to 4 na deck);
- QUANTIZE, SLIP, VINYL SPEED ADJUST (TOUCH/RELEASE) jako osobne przyciski;
- KEY SYNC i KEY RESET (zmiana tonacji niezależna od tempa);
- TEMPO RANGE (±6/10/16/WIDE) — FLX4 ma jeden stały zakres ±6%;
- MASTER TEMPO jako fizyczny przycisk;
- pokrętło jog o pełnej średnicy z regulacją oporu (FLX4 ma mały talerz, bez oporu);
- ekran na talerzu (pozycja, BPM, ostrzeżenia);
- REVERSE, CALL, TAG LIST, dwa gniazda USB, sieć PRO DJ LINK.

**Na DJM-900NXS2, czego FLX4 nie ma:**
- cztery kanały zamiast dwóch;
- fizyczny przełącznik krzywej crossfadera i faderów kanałowych;
- osobne wyjścia BOOTH z własnym poziomem;
- SEND/RETURN dla zewnętrznego efektu;
- filtr kanałowy jako osobne pokrętło na każdym kanale;
- pełna sekcja mikrofonowa z EQ.

**Rzeczy, które FLX4 ma, a klubowy zestaw NIE:**
- SMART CFX i SMART FADER (automatyka Pioneera dla początkujących);
- fader start i crossfader start jako domyślne zachowanie;
- sterowanie jednym kablem USB z laptopa.

To ostatnie jest istotne dydaktycznie: **jeśli nauczysz się polegać na SMART
FADER, przy prawdziwym pulpicie zostaniesz bez niego.** Symulator powinien to
mówić wprost w chwili, gdy Janek go użyje.

## 4. Kolejność budowy

1. Model **jednego CDJ-3000** sterowany lewym deckiem — jog, play, cue, tempo,
   pady. Sprawdzian: czy ruch talerza na FLX4 wygląda wiarygodnie na modelu.
2. Drugi CDJ (prawy deck) — to samo, bez nowej logiki.
3. **DJM-900NXS2** — EQ, fadery, crossfader, CUE.
4. Warstwa „czego tu nie ma": kontrolki obecne na klubowym sprzęcie rysowane
   przygaszone, z podpowiedzią po najechaniu.

Punkt 4 jest właściwym produktem, nie ozdobą: pokazuje, czego Janek **nie
przećwiczy** na swoim sprzęcie, zanim stanie za pulpitem.
