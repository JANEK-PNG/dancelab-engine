# Przegląd Hugging Face: modele i zbiory muzyczne, z licencjami

**Data:** 2026-09-10 · **Źródło liczb:** `experiments_priv/2026-09-10_hf_przeglad/hf_szukaj.py`
(API HF, 16 zapytań o modele, 22 o zbiory, sortowanie po pobraniach; surowy wynik
w `hf_wynik_2026-09-10.txt`, 624 wiersze). Licencja = tag na stronie HF; tam, gdzie
tag mówi co innego niż oryginalny autor, piszę to wprost. Pobrania = ostatni miesiąc.

**Werdykt w jednym zdaniu:** wszystko, co muzyczne i mocne, jest **CC-BY-NC** (MuQ, MERT,
MusicGen, EnCodec); jedyna rodzina użyteczna komercyjnie to **CLAP od LAION (Apache-2.0)**,
którą już mamy — a **zbioru z decyzjami DJ-a (szwy, cue, kolejność) nie ma na HF wcale**.

---

## Modele do rozumienia muzyki (nie generatory)

| Model | Licencja | Do czego | Pobrania | Dla DanceLab |
|---|---|---|---|---|
| `laion/clap-htsat-fused` / `-unfused` | Apache-2.0 | osadzenie dźwięk↔tekst | 8,5 mln / 0,95 mln | **mamy** (`core/models.py:294`) |
| `laion/larger_clap_music`, `larger_clap_music_and_speech`, `larger_clap_general` | Apache-2.0 | to samo, większe, uczone na muzyce | 34 tys. / 281 tys. / 334 tys. | kandydat na podmianę wagi CLAP — ta sama licencja, ten sam interfejs; **pomiar jak A5, próg przed** |
| `OpenMuQ/MuQ-large-msd-iter`, `MuQ-MuLan-large` | **CC-BY-NC-4.0** | osadzenie muzyki | 453 tys. / 109 tys. | **OBALONE A5** — remis 11:10, hubness, licencja |
| `m-a-p/MERT-v1-330M`, `-95M`, `MERT-v0`, `MERT-v0-public` | **CC-BY-NC-4.0** (wszystkie cztery, także `v0-public`) | cechy 75 Hz z 25 warstw | 148 tys. / 95 tys. | nie — licencja; wcześniejsze zdanie, że `v0-public` jest Apache, było **błędne** |
| `MIT/ast-finetuned-audioset-10-10-0.4593` | BSD-3 | 527 klas AudioSet (dźwięki ogólne) | — | tylko jako filtr „to nie utwór" (sample, szumy) |
| `facebook/encodec_24khz` / `_32khz` / `_48khz` | brak tagu / brak / MIT | kodek neuronowy, nie osadzenie | 232 tys. | nie dotyczy |
| `tky823/MusicFM` | MIT + Apache (tag mirrora) | osadzenie muzyki (ByteDance) | 243 | licencja **oryginalnych wag do sprawdzenia u autora**, mirror nie jest źródłem |
| `nvidia/music-flamingo-hf` | „other" (licencja NVIDIA) | muzyka → tekst (LLM) | 6,9 tys. | nie — licencja własnościowa |
| `dima806/music_genres_classification` i podobne (GTZAN, 10 gatunków) | Apache-2.0 | gatunek | 2,5 tys. | bezużyteczne — 10 gatunków w stylu „rock/jazz/disco", zero podziałów elektroniki |
| `stanford-crfm/music-small-800k` | Apache-2.0 | muzyka symboliczna (MIDI) | 16 tys. | nie dotyczy |
| Demucs (mirrory `jasonvassallo/…-mlx`, `nsosu/demucs-onnx`) | MIT | rozdzielanie na stemy | ~30 | poza zakresem produktu; oryginał `facebook/demucs` jest MIT |

**Czego na HF nie ma jako gotowego modelu:** tempo, siatka bitów, tonacja, faza frazy —
nic z tego nie pojawia się w wynikach. To żyje poza HF (Essentia — AGPL + wagi
CC-BY-NC-SA; `beat_this` CPJKU — MIT; madmom — licencja własna z klauzulą niekomercyjną).
Te trzy licencje spisane z pamięci, **nie sprawdzone dziś** — przed użyciem sprawdzić.

## Zbiory

| Zbiór | Licencja | Co zawiera | Dla DanceLab |
|---|---|---|---|
| FMA (`benjamin-paine/free-music-archive-full` 3,7 tys. pobrań, `-large`, `MYJOKERML/fma_large`, `rudraml/fma`) | metadane CC-BY-4.0; **audio per utwór** (CC-BY / CC-BY-NC / inne, trzeba filtrować) | 106 tys. utworów, drzewo 161 gatunków z podgałęziami elektroniki (Techno, House, Drum & Bass, Dubstep…) | **jedyny kandydat** na naukę gatunku awaryjnego; komercyjnie tylko po odfiltrowaniu NC |
| MTG-Jamendo (`rkstgr/mtg-jamendo`) | tag mirrora „Apache" — **oryginał: audio CC różne, adnotacje CC-BY-NC-SA-4.0** | 55 tys. utworów, 195 tagów (gatunek, instrument, nastrój) | adnotacje NC → nie do produktu; audio tak, tagi nie |
| `google/MusicCaps` | CC-BY-SA-4.0 | 5,5 tys. opisów tekstowych klipów z YouTube — **bez audio** | nie dotyczy (opisy, nie decyzje) |
| `amaai-lab/JamendoMaxCaps` | CC-BY-SA-3.0 | 200 tys. utworów Jamendo z opisami | jak wyżej |
| AudioSet (`agkphysics/AudioSet`, 57 tys. pobrań) | CC-BY-4.0 (etykiety) | 2 mln klipów YouTube, dźwięki ogólne | nie dotyczy |
| GTZAN (`marsyas/gtzan`, `m-a-p/GTZAN`) | brak / CC-BY-4.0 na mirrorze | 1000 klipów, 10 gatunków, znane duplikaty i błędy | nie |
| MUSDB18-HQ (`danjacobellis/musdb18HQ`, `roro128/musdb18-hq-flac`) | **tylko badania** (CC-BY-NC-SA na mirrorze) | 150 utworów ze stemami | nie dotyczy |
| Music4All (`Leon299/music4all`) | umowa badawcza | 109 tys. klipów z metadanymi | licencja zamyka |
| `ccmusic-database/music_genre` | CC-BY-NC-ND | gatunki | nie |
| `vishnupriyavr/spotify-million-song-dataset` | CC0 | teksty piosenek | nie dotyczy |
| `music-arena/music-arena-dataset` | CC-BY-4.0 | preferencje ludzi wobec generatorów | nie dotyczy |

**Zapytania, które zwróciły ZERO trafień muzycznych:** `beatport`, `dj mix`, `techno`
(tylko szum z nazw użytkowników), `discogs`, `disco-10m`, `harmonic`, `chords` (jeden
zbiór akordów gitarowych), `key` (szum). **Na HF nie istnieje zbiór szwów, hot cue ani
kolejności setu.** Nasz rejestr (150 tys. zdarzeń z 27.08, oceny setów, `gui_dziennik`)
jest jedynym takim zasobem, jaki widzę — i to jest właściwy wniosek z tego przeglądu.

## Co z tego wynika

1. **CLAP zostaje**, ale warto zmierzyć `larger_clap_music` — ta sama licencja, ten sam
   kod, potencjalnie lepsze osadzenie muzyki. Pomiar jak w A5 (296 utworów, remis lub
   wygrana ≥ 60 % par), próg zapisany przed uruchomieniem.
2. **Gatunek awaryjny** (pozycja z rankingu schematu) — jeśli w ogóle, to z FMA po
   odfiltrowaniu NC, nie z GTZAN i nie z AudioSet.
3. **MERT, MuQ, MusicGen, EnCodec, Music Flamingo** — NC albo własnościowe; do
   `experiments_priv/` wolno, do produktu nie.
4. Nie szukać na HF danych o DJ-owaniu — ich tam nie ma. Zbierać własne.
