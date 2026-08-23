# DDJ-FLX4 — notatki z oficjalnej instrukcji i listy komunikatów MIDI

Źródła (pobrane 23.08.2026, leżą obok; PDF-y są gitignored, notatka wchodzi do repo):

* `DDJ-FLX4_manual_DRI1804A.pdf` — Instruction Manual, 165 stron (AlphaTheta,
  `downloads.support.alphatheta.com/manuals/DDJ_FLX4_DRI1804A_manual.pdf`).
* `DDJ-FLX4_MIDI_message_List_E1.pdf` — List of MIDI messages, Ver 1.0, 5 stron
  (`downloads.support.alphatheta.com/software_info/dj-controllers/DDJ-FLX4/DDJ-FLX4_MIDI_message_List_E1.pdf`).
* Dotychczasowa mapa w repo `docs/fullstack-handoff/11_DDJ_FLX4_CONTROL_MAP.md`
  opierała się na mapowaniu Mixxx (firmware 1.02) — NIE na tych dokumentach.

## Co z instrukcji ma znaczenie dla mapowania

* Urządzenie jest **USB audio/MIDI class-compliant** — na macOS bez sterownika
  (instr. s. 161: „outputs operating data for the buttons and knobs in MIDI format").
* Pioneer: „nie uruchamiać dwóch aplikacji DJ naraz" — to ostrzeżenie dotyczy
  WALKI o sterowanie i diody (MIDI-OUT). Nasz rejestrator ma być **tylko
  nasłuchem wejścia, zero MIDI-OUT** — wtedy CoreMIDI pozwala mieć Rekordboxa
  i nasz nasłuch równolegle. HIPOTEZA do sprawdzenia przy wpiętym sprzęcie.
* **Smart Fader** (s. 71–73): gdy włączony, Beat Sync jest wymuszony, EQ LOW
  i echo są sterowane AUTOMATYCZNIE przez oprogramowanie według pozycji fadera,
  a „actual EQ LOW knob position isn't reflected on screen". **Wniosek dla
  pomiaru szwu**: z MIDI widzimy tylko rękę Janka, nie to, co Rekordbox dołożył.
  Przy nagrywaniu ruchów rąk Smart Fader ma być WYŁĄCZONY, albo trzeba to
  zapisać jako osobny stan sesji. Inaczej „bas wstrzymany w 86% wejść" może być
  ręką ALBO automatem — nie do odróżnienia.
* **Smart CFX** (s. 70): podobnie — jedna gałka steruje pakietem efektów (także
  pętlami i tonacją), ekran nie pokazuje szczegółów.
* **Fader Start** (s. 67): SHIFT + fader kanału/crossfader wysyła osobne nuty
  PLAY/CUE (patrz tabela) — rejestrator ma je traktować jak zdarzenia transportu.
* **Utilities mode** (s. 144): SHIFT + PLAY/PAUSE lewego decka podczas wpinania
  USB → ustawienia sprzętowe (Back Spin, Fader Start, odwrócenie crossfadera,
  cut lag 0,3–5,5 mm, tryb demo). **Tryb demo** włącza się po 10 min bezczynności
  (domyślnie) — światełka; czy emituje MIDI, nieznane → źródło szumu do
  sprawdzenia; można wyłączyć (pad 1 w Utilities).
* Pady: 8 na deck; w Rekordboksie 16 hot cue na utwór, ale z urządzenia
  dostępnych 8 (A–H). Tryby padów: HOT CUE, PAD FX1/2, BEAT JUMP, SAMPLER,
  KEYBOARD, BEAT LOOP, KEY SHIFT (SHIFT + przycisk trybu = drugi tryb).
* Zakres TEMPO (SHIFT + BEAT SYNC): ±6 / ±10 / ±16 / WIDE. BEAT SYNC
  przytrzymany ≥1 s = master.
* LOAD ×2 = Instant Doubles (ten sam utwór na drugi deck od tej samej pozycji).

## Lista komunikatów MIDI — wyciąg (wszystko z oficjalnego PDF)

Kanały są podane tak, jak Pioneer: **1-based**. Bajt statusu zdradza prawdę
0-based: kanał 1 = `0x90/0xB0`. **PUŁAPKA**: `mido`/`rtmidi` liczą kanały od 0,
więc „Deck 1 = kanał 1" w PDF to `channel=0` w kodzie.

| Grupa | Kanał (PDF) | Status |
|---|---|---|
| Deck 1 (przyciski, jog, tempo, trim, EQ, fader kanału, CH CUE) | 1 | 0x90 / 0xB0 |
| Deck 2 (j.w.) | 2 | 0x91 / 0xB1 |
| Efekty jednostka 1 (CH1 albo CH1&CH2) | 5 | 0x94 |
| Efekty jednostka 2 (CH2) + LEVEL/DEPTH (CC) | 6 | 0x95 / 0xB5 (LEVEL/DEPTH: B4?) — patrz niżej |
| Mikser globalny: master, crossfader, CFX, słuchawki, mic, SMART CFX/FADER, BROWSE, LOAD | 7 | 0x96 / 0xB6 |
| Pady deck 1 / +SHIFT | 8 / 9 | 0x97 / 0x98 |
| Pady deck 2 / +SHIFT | 10 / 11 | 0x99 / 0x9A |
| Podświetlenie „track loaded" (tylko MIDI-OUT) | 16 | 0x9F |

Uwaga do LEVEL/DEPTH: PDF podaje kanał 6 i status `B4` (czyli kanał 5
0-based) — rozbieżność w samym dokumencie; rozstrzygnąć nasłuchem.

### Przyciski (NOTE; ON = 0x7F, OFF = 0x00) — kanał decka

| Kontrolka | nuta | +SHIFT |
|---|---|---|
| PLAY/PAUSE | 11 (0x0B) | 14 (0x0E) |
| CUE | 12 (0x0C) | 72 (0x48) |
| SHIFT | 63 (0x3F) | — |
| JOG touch | 54 (0x36) | 103 (0x67) |
| IN | 16 (0x10) | 76 (0x4C) |
| OUT | 17 (0x11) | 78 (0x4E) |
| 4 BEAT / EXIT | 77 (0x4D) | 80 (0x50) |
| CUE/LOOP CALL ◁ | 81 (0x51) | 62 (0x3E) |
| CUE/LOOP CALL ▷ | 83 (0x53) | 61 (0x3D) |
| BEAT SYNC (*3: wysyła przy PUSZCZENIU, nie naciśnięciu) | 88 (0x58); long press 92 (0x5C) | 96 (0x60) |
| HOT CUE mode | 27 (0x1B) | 105 (0x69) |
| PAD FX1 mode | 30 (0x1E) | 107 (0x6B) |
| BEAT JUMP mode | 32 (0x20) | 109 (0x6D) |
| SAMPLER mode | 34 (0x22) | 111 (0x6F) |
| CH CUE (słuchawki kanału) | 84 (0x54) | 104 (0x68) |
| Fader start: fader kanału z dołu w górę → PLAY | 102 (0x66) | tylko z SHIFT |
| Fader start: fader kanału do dołu → CUE | 82 (0x52) | tylko z SHIFT |

Crossfader start (z SHIFT): te same nuty 102/82, status 0x90 (ruch w stronę
decka 1) albo 0x91 (w stronę decka 2).

### Przyciski globalne — kanał 7 (0x96)

| Kontrolka | nuta | +SHIFT |
|---|---|---|
| MASTER CUE | 99 (0x63) | 120 (0x78) |
| SMART CFX | 0 (0x00) | 8 (0x08) |
| SMART FADER | 1 (0x01) | 9 (0x09) |
| BROWSE press | 65 (0x41) | 66 (0x42) |
| LOAD deck 1 | 70 (0x46) | 104 (0x68) |
| LOAD deck 2 | 71 (0x47) | 122 (0x7A) |
| Android MONO/STEREO | 109 (0x6D): STEREO=0x00, MONO=0x7F | — |

### Efekty

| Kontrolka | kanał | nuta / CC | +SHIFT |
|---|---|---|---|
| FX SELECT | 5 | NOTE 99 (0x63) | 100 (0x64) |
| BEAT ◁ | 5 | NOTE 74 (0x4A) | 102 (0x66) |
| BEAT ▷ | 5 | NOTE 75 (0x4B) | 107 (0x6B) |
| FX ON/OFF (*4) | 5 dla CH1 i CH1&CH2; 6 dla CH2 | NOTE 71 (0x47) | 67 (0x43) = Release FX |
| LEVEL/DEPTH | 6 (status B4 w PDF) | CC 2 / 34 (MSB/LSB) | — |
| FX CH SELECT (przełącznik) | 5 i 6 | NOTE 16/17 z wartościami 0x7F/0x00 w kombinacji: CH1 → ch5 n16=7F; CH2 → ch6 n17=7F; CH1&CH2 → ch5 n16=7F i ch6 n17=7F | — |

### Potencjometry i suwaki — 14-bit (CC MSB / CC LSB), min 0x00/0x00, max 0x7F/0x7F

| Kontrolka | kanał | CC MSB / LSB |
|---|---|---|
| TEMPO (min = strona „−", max = strona „+") | deck | 0 / 32 |
| TRIM | deck | 4 / 36 |
| EQ HI | deck | 7 / 39 |
| EQ MID | deck | 11 / 43 |
| EQ LOW | deck | 15 / 47 |
| CH FADER (min = dół) | deck | 19 / 51 |
| CFX deck 1 | 7 | 23 / 55 |
| CFX deck 2 | 7 | 24 / 56 |
| CROSSFADER (min = lewo) | 7 | 31 / 63 |
| MASTER LEVEL | 7 | 8 / 40 |
| MIC LEVEL | 7 | 5 / 37 |
| HEADPHONES MIX | 7 | 12 / 44 |
| HEADPHONES LEVEL | 7 | 13 / 45 |

### Enkodery względne

| Kontrolka | kanał | CC | wartości |
|---|---|---|---|
| JOG talerz (vinyl ON) | deck | 34 (0x22) | względne: w prawo rośnie od 0x41, w lewo maleje od 0x3F |
| JOG talerz (vinyl OFF) | deck | 35 (0x23) | j.w. |
| JOG talerz +SHIFT | deck | 41 (0x29) | j.w. |
| JOG bok (wheel side) | deck | 33 (0x21) | j.w. (także z SHIFT) |
| BROWSE obrót | 7 | 64 (0x40); +SHIFT 100 (0x64) | w prawo rośnie od 0x01, w lewo maleje od 0x7F |

### Pady (NOTE; kanał 8/10, +SHIFT 9/11) — nuta = baza trybu + (pad − 1)

| Tryb | baza |
|---|---|
| HOT CUE | 0x00 |
| PAD FX 1 | 0x10 |
| BEAT JUMP | 0x20 |
| SAMPLER | 0x30 |
| KEYBOARD | 0x40 |
| PAD FX 2 | 0x50 |
| BEAT LOOP | 0x60 |
| KEY SHIFT | 0x70 |

Czyli pad 3 w trybie BEAT JUMP na decku 2 = status 0x99, nuta 0x22 (34).
**Pułapka**: sam komunikat pada nie mówi, w jakim trybie jest deck — tryb
trzeba ŚLEDZIĆ z przycisków trybu (HOT CUE/PAD FX1/BEAT JUMP/SAMPLER
± SHIFT), a jeszcze bezpieczniej: PDF podaje nuty PER TRYB, więc numer nuty
zdradza tryb wprost (baza w górnych 4 bitach). To drugie jest pewniejsze.

### MIDI-OUT (do urządzenia — nasz rejestrator tego NIE robi)

* Diody przycisków: te same nuty, 0x7F/0x00.
* Miernik poziomu kanału: CC 2 na 0xB0/0xB1; zakresy: zielony1 0x26–0x40,
  zielony2 0x41–0x56, pomarańcz1 0x57–0x64, pomarańcz2 0x65–0x76, czerwony 0x77–0x7F.
* Vinyl mode: NOTE 23 (0x17) na 0x90/0x91 — **nie da się przełączyć z urządzenia**,
  tylko z aplikacji (domyślnie ON). Ważne: od tego zależy, czy talerz wysyła CC 34 czy 35.
* „Track loaded": kanał 16, nuta 0/1, 0x7F.

## Co z tego wynika dla naszych dwóch zastosowań

1. **Rejestrator ruchów rąk (pomiar szwu, „MIDI = idealne etykiety")**:
   nasłuch wejścia bez MIDI-OUT; logować surowe komunikaty z czasem
   monotonicznym; 14-bit składać z par MSB/LSB (LSB przychodzi po MSB);
   fader start i BEAT SYNC-przy-puszczeniu traktować jako zdarzenia;
   Smart Fader/Smart CFX = stan sesji, bo zmieniają znaczenie faderów i gałek.
2. **Kontrakt konsoli DanceLab Player** (`11_DDJ_FLX4_CONTROL_MAP.md`):
   przepisać odniesienie z Mixxx na ten oficjalny wyciąg; semantyka kontrolek
   z instrukcji (s. 12–33) jest pełniejsza niż z Mixxx (Instant Doubles,
   Active Loop, Cue Point Sampler, tapping tempa SHIFT+CH CUE).

## Do sprawdzenia przy wpiętym sprzęcie (hipotezy, nie fakty)

* Czy nasłuch równolegle z Rekordboxem działa (CoreMIDI, wielu klientów).
* Prawdziwy kanał LEVEL/DEPTH (PDF: kanał 6 vs status B4).
* Czy tryb demo emituje MIDI.
* Który fizyczny koniec TEMPO to 0x00 (PDF: strona „−").
* Czy LSB zawsze następuje po MSB i czy urządzenie wysyła LSB przy małych ruchach.

## ZMIERZONE na sprzęcie 23.08.2026 (nasluch.py, 120 s, 5059 komunikatów, Rekordbox ZAMKNIĘTY)

Choreografia Janka: PLAY, crossfader, TEMPO deck 1 góra→dół, LEVEL/DEPTH,
HOT CUE + pad 1 i 3 na decku 2, jog deck 1, BEAT SYNC. (Krok „SHIFT + fader
kanału" nie zmieścił się w 2 minutach — do powtórki.)

| Hipoteza z papieru | Wynik |
|---|---|
| LSB zawsze po MSB | **TAK**: 533/533 par crossfadera w kolejności MSB→LSB; pełny zakres 14-bit 0–16383, lewo = 0 |
| TEMPO: strona „−" = 0 | **TAK**: ruch suwaka W DÓŁ zwiększa wartość; góra (−) = 0, dół (+) = 16383, środek = 8192 |
| LEVEL/DEPTH: kanał 6 czy status B4? | **OBA**: każdy ruch idzie na kanał 4 I 5 (0-based; `B4 02/22` i `B5 02/22`) z tą samą wartością. PDF ma błąd/uproszczenie |
| BEAT SYNC wysyła przy puszczeniu (*3) | **TAK**: ON i OFF przychodzą w odstępie 0 ms (para przy puszczeniu). Dla porównania PLAY: ON przy naciśnięciu, OFF 140 ms później |
| Jog względny 0x41 w prawo / 0x3F w lewo | **TAK**: CC 34 (vinyl ON) wartości 65/66/67 w prawo zależnie od prędkości, 63 przy drgnięciu w lewo; bok koła CC 33 tak samo; JOG touch nuta 54 ON/OFF |
| Pady: nuta = baza trybu + pad | **TAK**: deck 2 = `0x99`, HOT CUE pad 1 = nuta 0, pad 3 = nuta 2 |
| Przycisk trybu HOT CUE deck 2 | **TAK**: `91 1B 7F/00` |
| Nieznane komunikaty podczas gestów | **BRAK** (0 z 5059). Jednorazowo w pierwszym 5-sekundowym teście: `96 6D 00` (MONO/STEREO = STEREO) + `B4/B5 64 08` i `B4/B5 50 15` (CC 100 i CC 80 na kanałach FX — NIE ma ich w oficjalnej liście; nie powtórzyły się) |

Do zrobienia: fader start (SHIFT + fader), nasłuch PRZY OTWARTYM Rekordboksie,
tryb demo.

## ZMIERZONE 23.08 c.d. — PRZY OTWARTYM REKORDBOKSIE (90 s, 3820 komunikatów)

| Hipoteza | Wynik |
|---|---|
| Nasłuch (tylko wejście) działa równolegle z Rekordboxem | **TAK**: 3820 komunikatów dotarło, gdy Rekordbox trzymał urządzenie i grał. CoreMIDI rozdaje wejście wielu klientom; ostrzeżenie Pioneera dotyczy sterowania/diod, nie nasłuchu |
| Fader start (SHIFT + fader kanału) | **TAK, co do bajtu**: SHIFT = nuta 63 ON przez cały czas trzymania; fader z dołu w górę → `90 66 7F` + `90 66 00` (PLAY, para w odstępie 0 ms); fader na sam dół → `90 52 7F` + `90 52 00` (CUE, para 0 ms). Powtórzone 8 razy, zawsze tak samo |
| Nieznane komunikaty | **BRAK** (0 z 3820) |

Wniosek: rejestrator ruchów rąk może działać obok Rekordboxa bez żadnej
ingerencji — Janek gra normalnie, my słuchamy. Fader start i BEAT SYNC są
zdarzeniami „bez czasu trzymania" (para ON/OFF w 0 ms) — w rejestratorze
traktować jako impulsy, nie przedziały.
