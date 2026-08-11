# Audyt biblii TERRAIN przeciwko runtime'owi 2026-08-11

**Protokół:** własny protokół biblii (dowód → synteza → decyzja; sprzeciw
zostaje w dokumencie). **Kontekst rozstrzygający:** cały runtime Qt, na który
biblia wskazuje, został **skasowany 27.07** (commit `252d917`, 8 117 linii:
simple_mode, pair_review, energy_timeline, mixability_map, analyzed_library,
import_dialogs; archiwum: tag `ui-archive-2026-07-24`). Logika wolna od Qt
przeżyła: `transition_simulation` → `dancelab/preview`, `preview_timing` →
`validation`, stems w `dancelab/stems`. Od tamtej pory żywym interfejsem
jest TUI (`docs/TUI_MAPA.md`), a silnik urósł o rzeczy, których biblia nie
zna (cue na taktach RB, rejestr padów, kotwica ★, sito, most do filara,
łuk OFF, mapa DJ-ów z precedensami).

**Słownik dzisiejszych statusów:**
- `E(silnik)` — fundament danych/logiki żyje w silniku (dowód w kolumnie);
- `E(TUI)` — zachowanie żyje w TUI;
- `Adapt` — fundament żyje, potrzebna skóra TERRAIN;
- `Planned` — nic nie żyje, do zbudowania;
- `Deferred` — nadal zablokowane brakiem źródła danych.

Werdykt „biblia mówiła Existing, a wskazany kod nie istnieje" oznaczam
`†` (martwa referencja) — status merytoryczny liczy się od dzisiejszego
fundamentu, nie od martwego pliku.

## Atomy

| id | nazwa | biblia | dziś | dowód / notka |
|---|---|---|---|---|
| A01 | Button press | adapt | Planned | czysto skórowe; TUI ma przyciski Textual |
| A02 | Button busy | adapt† | Adapt | wzorzec żyje: 3-stanowy #cue-write (`tui/app.py::_odswiez_guzik_cue`) + workery |
| A03 | Focus ring | existing† | Adapt | Qt padł; Textual ma własny focus; w GUI od nowa |
| A04 | Workspace tab indicator | planned | Adapt | TUI ma TabbedContent (3 taby); TERRAIN doda TRACK |
| A05 | Toggle thumb | adapt† | Adapt | przełączniki żyją: #contour, #lib-artwork |
| A06 | Status dot | adapt† | Adapt | #status (stan RB, odświeżany 5 s) |
| A07 | Determinate progress | existing† | E(TUI) | `analyze_files` z realnym `stage_progress` → licznik w TUI |
| A08 | Indeterminate progress | existing† | E(TUI) | etapy bez ułamka raportowane uczciwie (bramkarz, LUFS „…") |
| A09 | Selection ring | adapt† | Adapt | tożsamość wyboru częściowa (kursor tabel; karta cue trzyma `_cue_track`); ciągłość między widokami = TERRAIN |
| A10 | Tooltip | existing† | Planned | Qt padł; TUI nie ma tooltipów |
| A11 | Disclosure chevron | planned | Planned | bez zmian |
| A12 | Cue marker | adapt† | Adapt | fundament MOCNIEJSZY niż w lipcu: `tui/cue_edycje` (pady, migawki cofania) + `cue_ledger` UUID |
| A13 | Cue snap | existing† | E(silnik) | `decision/cue_grid.snap_cue_start` + `rekordbox_siatka.do_taktu` — snap do TAKTÓW RB, nie tylko 8 uderzeń |
| A14 | Transition region handle | existing† | Planned(GUI) | dane okien żyją (`transition_windows`), uchwyt interaktywny padł z Qt |
| A15 | Playhead | existing† | Adapt | `tui/pasek.os_z_glowica` + ticker 1 s; frame-bound wymaga GUI |
| A16 | 8-beat phase tick | planned | Adapt | lepiej niż w lipcu: `validation/preview_timing` + faza taktu 1–4 z PQTZ (`rekordbox_import`) |
| A17 | EQ knob value | existing† | E(silnik)/Planned(GUI) | dane: `TransitionEnvelope` low/mid/high; rysowanie padło z Qt |
| A18 | Channel fader | existing† | E(silnik)/Planned(GUI) | `TransitionEnvelope.fader_a/b` |
| A19 | Crossfader | planned | Planned | bez zmian; automix silnika gra bez crossfadera (bas poza faderem) — kontrakt do przemyślenia |
| A20 | Level meter | deferred | Deferred | nadal brak realnego RMS-tap w odtwarzaniu |
| A21 | Warning badge | planned | Adapt | treść już jest: ostrzeżenia słabych szwów, zero-gatunku, rozluźnień sit |
| A22 | Saved state | adapt† | Adapt | `plan_store` (S/O/X, kosz) + `user_store` per pula; autosave sesji = TERRAIN |
| A23 | Drag ghost | planned | Planned | — |
| A24 | Drop target | planned | Planned | — |
| A25 | Zoom scale label | existing† | Planned | zoom padł z Qt |

## Molekuły

| id | nazwa | biblia | dziś | dowód / notka |
|---|---|---|---|---|
| MOL01 | Track row selection | adapt† | Adapt | DataTable biblioteki |
| MOL02 | Track row insertion | planned | Adapt | wzorzec dwóch naciśnięć A (dopisz) już żyje w TUI |
| MOL03 | Track analysis state | adapt† | E(TUI) | worker + licznik + imienne odrzuty bramkarza |
| MOL04 | Must Have action | existing† | Adapt | dziś: filary ⚑ (F) + piny; semantyka „musi zagrać" żyje |
| MOL05 | Rest Tonight action | existing† | **Planned** | JEDYNY REGRES: wykluczenia „nie dziś" nie ma w TUI w ogóle |
| MOL06 | Filter result update | existing† | E(TUI) | `filter_library` na żywo, zły filtr = powód |
| MOL07 | Import drop zone | planned | Planned | — |
| MOL08 | Job item | adapt† | Adapt | workery + notki; JobRecord = TERRAIN |
| MOL09 | Track card in terrain | adapt† | Planned(GUI) | dane energii są; wizualizacja padła z Qt |
| MOL10 | Seam joint | adapt† | E(silnik)/Planned(GUI) | `SetTransition.transition_score` + próg 0,60 |
| MOL11 | Candidate result | existing† | Adapt | ŻYWE w TUI: panel `slot_suggest` (Z/A, 42 kolumny) |
| MOL12 | Cue control | adapt† | Adapt | `cue_edycje` + ledger; mocniejsze niż w lipcu |
| MOL13 | Transition region | existing† | E(silnik) | `transition_windows.detect_transition_windows` |
| MOL14 | Transport control | adapt† | Adapt | `tui/odtwarzacz` (ffplay: pauza z pozycją, graj_od) |
| MOL15 | EQ band control | existing† | E(silnik)/Planned(GUI) | dane envelope |
| MOL16 | Mixer channel | adapt† | Planned(GUI) | rysowanie padło |
| MOL17 | Transition moment | planned | Adapt | `bass_swap`/`tops_swap` w `preview/transition_simulation` + beat_positions |
| MOL18 | Verdict action row | planned | Adapt | żyje inaczej: edycje→`tui_edycje.jsonl`, V = werdykt plan-vs-DJ |
| MOL19 | Export issue row | planned | Adapt | treść jest: imienne pominięcia, raport konfliktów `cue_zapis` |
| MOL20 | Toast | planned | E(TUI) | dymki `notify` (ważne ostrzeżenia) już standardem |

## Organizmy

| id | nazwa | biblia | dziś | dowód / notka |
|---|---|---|---|---|
| O01 | Project Bar | adapt† | Adapt | pasek statusu TUI (RB, backupy, licznik); sesja-projekt = TERRAIN |
| O02 | Workspace Tabs | planned | Adapt | 3 taby żyją; TRACK do dodania; „taby to nie kroki" już spełnione |
| O03 | Context Inspector | planned | Adapt | prekursor żyje: nakładka #suggest (5 trybów) + karta INFO |
| O04 | Job Center | planned | **Planned (P0, najpilniejsze)** | import RB i żniwa wektorów = skrypty operatora; luka potwierdzona mapą TUI |
| O05 | Library Table | adapt† | Adapt | tabela + sekcje ♥/⚑ + sort + LUFS + okładki |
| O06 | Import Review Sheet | adapt† | Adapt | bramkarz ffprobe z imiennymi odrzutami |
| O07 | Set Terrain | adapt† | Planned(GUI) | dane żyją; UWAGA: łuk OFF — teren pokazuje energię jako DANE, bez celu |
| O08 | Candidate Map | adapt† | Adapt | `slot_suggest` + sito brzmienia; mapa 2D padła z Qt |
| O09 | Terrain Dock | planned | Planned | — |
| O10 | Track Inspector | adapt† | Adapt | karta INFO + NOWE aktywo: precedensy z mapy (kameleon/kotwica) — treść, której biblia nie znała |
| O11 | Seam Workspace | adapt† | Adapt | Eksport/Cue + pasek C; per synteza: SEAM/CUE = jeden widok |
| O12 | Automix Console | adapt† | E(silnik)/Planned(GUI) | automix gra CAŁY set (nowe po 15.07); konsoli brak |
| O13 | Export Gate | planned | Adapt | fundament PRZEROSŁA biblię: zapis master.db E2E (backup/swap/weryfikacja/ledger); „Write XML" martwe |
| O14 | Empty / Error State | planned | E(TUI) | uczciwe pustki są standardem TUI |

## Kontrakty Automix

| id | nazwa | biblia | dziś | dowód / notka |
|---|---|---|---|---|
| AM01–03 | playheady (master, deck A/B) | adapt† | E(silnik)/Adapt | `TransitionRenderResult.cue_a/b_sec`, `playback_rate_a/b` żyją w `preview` |
| AM04 | Beat phase 1..8 | planned | Adapt | `preview_timing` + faza z PQTZ |
| AM05 | Phrase boundary | planned | Adapt | `TransitionEnvelope.grid_beats`; frazy z PSSI w `rekordbox_import` |
| AM06–07 | Cue-in/out markers | adapt† | Adapt | `transition_cues.build_transition_cue` + pady efektywne z TUI |
| AM08 | Region playback | existing† | Adapt | render żyje; UI padło |
| AM09–10 | EQ envelopes A/B | existing† | E(silnik) | `TransitionEnvelope` low/mid/high a/b |
| AM11–12 | Bass/Tops swap | adapt† | E(silnik) | profile w `preview/transition_simulation` (`bass_swap`, `tops_swap`) |
| AM13 | Channel faders | existing† | E(silnik) | `fader_a/fader_b` |
| AM14 | Crossfader profile | planned | Planned | patrz A19: automix celowo gra bez crossfadera |
| AM15 | Real level meters | deferred | Deferred | bez zmian |
| AM16 | Sync rate display | existing† | E(silnik) | `playback_rate_a/b` |
| AM17 | Quantize correction | existing† | E(silnik) | `cue_grid` + takty RB — mocniejsze niż w lipcu |
| AM18–19 | Profile/Duration switch | adapt† | Adapt | `build_transition_envelope(profil)` + `transition_length` |
| AM20 | Stem source state | existing† | E(silnik) | pakiet `dancelab/stems` |
| AM21 | Scrub synchronization | existing† | Adapt | `odtwarzacz.graj_od` (ffplay -ss); scrub ciągły = GUI |
| AM22 | Planned value hover | planned | Planned | — |
| AM23 | Render-ready handoff | adapt† | Adapt | workery TUI; wzorzec ten sam |
| AM24 | Risk moment marker | planned | Adapt | ostrzeżenia słabych szwów z numerem styku — mapowanie na czas do zrobienia |

## Podsumowanie liczbowe

Biblia (15.07): existing 24 · adapt 33 · planned 24 · deferred 2.
**Dziś:** E(silnik) 15 · E(TUI) 6 · Adapt 38 · Planned 22 · Deferred 2
(liczone po rozbiciu wierszy zbiorczych; wiersze z podwójnym statusem
liczone po stronie fundamentu).

**Najważniejsze ustalenia:**

1. **34 referencje kodu są martwe** (`†`) — wskazują pliki skasowane 27.07.
   Merytorycznie NIE oznacza to regresu: fundament przeniósł się do
   silnika i TUI. Realny regres jest JEDEN: **MOL05 „Rest Tonight"**
   (wykluczenie utworu na dziś) — nie istnieje nigdzie.
2. **Silnik przerósł biblię w pięciu miejscach:** snap do taktów
   Rekordboxa (nie 8 uderzeń), zapis master.db zamiast „Write XML",
   rejestr UUID padów, automix całego setu, precedensy z mapy dla
   widoku TRACK.
3. **Największa dziura pozostaje ta sama i awansuje na P0: Job Center**
   (O04) — import z RB i żniwa wektorów wciąż żyją w terminalu operatora.
4. **Łuk OFF zmienia kontrakt O07/O09:** teren i dock pokazują energię
   jako dane o secie, nigdy jako cel; „wierność łukowi" nie istnieje
   (`SetCoherence.arc_adherence = None`).
5. **Crossfader (A19/AM14) wymaga decyzji projektowej,** nie implementacji:
   automix silnika celowo gra bez crossfadera (bas poza faderem, zero
   limitera) — kontrakt z biblii może być sprzeczny ze zmierzoną praktyką.
