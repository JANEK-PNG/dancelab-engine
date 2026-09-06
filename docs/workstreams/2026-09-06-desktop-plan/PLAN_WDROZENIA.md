# DanceLab desktop GUI — evidence-backed implementation plan

Prepared: 2026-09-06. Baseline: `d5333c2`, branch `codex/audit-stage-a`.
Owner: Jan. Status: ready for sequencing; this document does not mean the new
production GUI has been implemented. The existing desktop window is running.

The first product increment is a desktop application that opens the owner's
library, builds a manual working set, saves it and restores it after restart.
Audio, suggestions and guarded Rekordbox publishing follow on that foundation.
A browser tab is not an accepted delivery surface for the new GUI.

## 1. Product result and boundaries

**Confirmed by the owner:** prepare sets from a personal library; launch an
application with its own macOS window. The owner explicitly rejected browser
previews as delivery of the application. There is no account/login requirement.
First use means a clean local profile; repeat use means reopening saved work.

**Actual foundation:** `dancelab gui` → `gui/okno.py` → WKWebView window + Python
`Most` bridge in the same process. TUI remains `dancelab tui`, using Textual.
The desktop shell already exists; this is an integration and product redesign,
not a new rendering-stack selection. FastAPI is not the GUI's transport.

**Two explicit delivery levels:**

- Development desktop build: a clearly named application/launcher on this Mac,
  attached to the checkout and its installed environment. No browser interaction
  or manual localhost server. This is not a portable installer.
- Distributable desktop build: an `.app` tested on a clean supported Mac without
  this checkout, its `.venv`, or the owner's dataset. Bundled runtime/resources,
  data paths, audio dependencies and upgrade/restore behaviour are acceptance
  work, not something a `.command` shortcut proves.

**In the first release:** personal-library browsing and filtering; manual sets;
explicit pillars; save/restore; track inspection; audio where available; existing
suggestions with provenance; preview and guarded playlist export to Rekordbox.
Preserve cue editing/export through the current implementation during migration.

**Separate or deferred:** new model training, FLX4 capture/replay, TouchDesigner,
cloud accounts, collaborative editing, a live DJ playback engine, additional
streaming-provider authentication and a full rewrite of Engine/TUI. Existing
model-backed capabilities remain available; they are not retrained for the GUI.

**Proposed UX, not yet validated:** Library and Sets as primary destinations,
track detail and cue editor as subordinate views, DJ sound references as an
optional tool. The prior Redakcja prototype and design system are inputs, not
an approved final replacement for the production interface.

## 2. Actual application and data inventory

Evidence labels: **observed** = native-window inspection; **measured** = the
read-only collector; **code** = implementation/test inspection; **proposed** =
new acceptance requirement. All measurements are local snapshots, not universal
product statistics. Reproduce from the repository root:

```bash
.venv/bin/python docs/workstreams/2026-09-06-desktop-plan/evidence/collect_inventory.py
```

See [inventory.json](evidence/inventory.json), [bridge inventory](evidence/bridge-inventory.json)
and [native observations](OBSERVATIONS.md).

| Fact | Current evidence | Implication |
| --- | --- | --- |
| Desktop GUI | Observed native DanceLab window, v0.1.1, actual track waveform and library | Extend this window; browser prototype is not the release |
| Library | 8260 header rows; 8261 JSON files, 1,327,971,332 bytes | The extra JSON is `library_manifest.json`, not a lost track |
| Existing local audio paths | 272 regular files at the time of collection | Native playback tests need this subset; existence does not verify decoding |
| Streaming references | 7910 Apple Music entries | Metadata-only set preparation must remain possible |
| Missing local paths | 78 entries | Keep them visible and explain unavailable operations |
| Inconsistent availability | GUI flags 325 playable; 78 flags refer to missing paths, 25 existing relative paths are flagged unavailable | Repair capability classification before accepting audio UX |
| User state | 8 playlists, 7 favourites, 6 pillars in the active playlist | Migration must preserve associations and roles |
| Saved plans | 9 readable/listable plans, none marked damaged by the current list reader | This does not establish full restore or audio availability |
| Current-plan pointer | File exists; target `/plany/B.json` does not | Resume cannot rely on this pointer; require visible recovery choices |
| Native Set screen | Badge 6, six pillars, empty generated-set section | Badge is not a count of an assembled working set |
| Bridge | 72 public methods; `most.py` 2370 lines, `app.js` 2149, TUI 3763 | Reuse operations; extract touched responsibilities incrementally |

The raw GUI headers have no missing BPM/key values and no duplicate track IDs
in this snapshot. That is not an accuracy assessment, audio measurement, or a
claim about every future import. File-source counts depend on mounted volumes
and the current repository working directory.

### Functional map: preserve, adapt or add

Sources below are relative to the repository root. Function symbols and the
bridge inventory make the mapping traceable without relying on old line counts.

| Area | Current TUI | Current desktop GUI / source | Decision for new GUI | Acceptance evidence |
| --- | --- | --- | --- | --- |
| Launch | `DanceLab.command` opens Ghostty/TUI | `DanceLab-GUI.command` → `gui/okno.py`; Desktop `DanceLab.app` still points to TUI | Give GUI a distinct launch identity; retire stale Qt entry instructions | Launch/relaunch from Finder with no browser |
| Library | Search, BPM/key, source sections, sorting | `Most.biblioteka`, `szukaj`; shared `stan/biblioteka.py` | Reuse filters; primary library destination with capability labels | Same query/source gives same IDs in both adapters |
| Folder import | `_lib_analyze_worker` | `skanuj_folder`, `postep_skanu` → `stan.budowa.przeanalizuj_folder` | Native folder picker, complete rejection report, cancellation | Empty/bad/mixed input, cancel and retry on disposable fixtures |
| Favourites and playlists | `tui/user_store.py` | `playlisty`, `nowa_playlista`, `wybierz_playliste`, `przelacz_ulubiony` | Preserve per-library state; distinguish pillar collections from saved sets | Existing 8 playlists and 7 favourites survive migration |
| Add first track | Pillar selection/build workflow | `+ do setu` calls pillar toggle; `dopisz_utwor` requires an existing position | Add explicit empty-draft and append operations | 0 → 1 → 2 tracks, with zero implicit pillars |
| Pillars and roles | 3–10 for pillar-based construction | `ustaw_filar`, `ustaw_tryb_filarow`, `szkic_z_filarow` | Separate optional constraints from manual order | Manual 1/2-track drafts work; generator minimum remains explicit |
| Set generation | `action_build` → shared `stan/budowa.py` | `buduj_set`/`postep_budowy` | Keep current scoring and settings; show progress and missing evidence | Deterministic fixture + visible refusal on invalid input |
| Edit order | Move/cut/add/replace actions | `przesun_utwor`, `wytnij`, `dopisz_utwor`, `podmien`, `cofnij` | Reuse where valid; enable edits without generator context | First/middle/last edits, duplicate rejection and undo |
| Save and restore | `action_save_plan` uses `plan_store.save_plan`; load uses shared matching | `zapisz_plan`, `lista_planow`, `wczytaj_plan` | One agreed current-set policy; saved/dirty/error states and resume | Native restart and TUI cross-read of same saved order |
| Track inspection | Track info, source details, cue screens | `wczytaj_utwor`, `info_utworu`, `przebieg_utworu`, `pady` | Preserve waveform, metadata provenance, local fonts and cue editor | Known/missing metadata and source states shown accurately |
| Audio and transitions | Shared player and seam services | `graj`, `przewin`, `graj_szew`, progress/state, close hook | One player; disable by capability, not library membership | Native play/pause/seek/close; stream/missing-path refusals |
| Suggestions and DJ references | Candidate panel, sound-reference collection | `kandydaci`, `porownaj_pare`, `djs` | Preserve as optional assistance; do not invent loaded-plan weights | No suggestion if context unknown; manual editing still works |
| Playlist export | Existing guarded writer | `podglad_playlisty` → `wyslij_playliste` | Keep review-first, backup and stale-preview invalidation | Copy-of-database tests, then explicit native export trial |
| Cue export | Shared cue logic, terminal writer | `przygotuj_zapis_cue` → `zapisz_cue` | Keep existing editor and two-step writer reachable during migration | Cue edit/review/export regression and collision cases |
| Recovery and jobs | Some stop/retry facilities | Daemon threads/polling; only artwork cancellation exposed | Define cancellation/close policy and persistence boundaries | Close during scan/build/save; no false success or orphan audio |

Relevant regression suites: `test_gui_plany`, `test_stan_plan`,
`test_plan_store`, `test_gui_edycja_setu`, `test_gui_cofanie`,
`test_wspolna_biblioteka`, `test_wspolny_skan`, `test_gui_odsluch`,
`test_gui_filary_biblioteka`, `test_gui_playlista`, `test_rekordbox_cue_writer`,
`test_gui_dziennik`, `test_audit_p1` and `gui_security.test.cjs`.
These are predominantly logic/adapter tests, not an end-to-end desktop UX suite.

### Blocking gaps demonstrated in the code

1. **Empty manual set is unsupported by the existing add operation.** Calling
   `Most().dopisz_utwor(0, "synthetic-track")` returns `pozycja 1 poza setem`.
   The pillar sketch requires `MIN_FILARY = 3`; renaming the button cannot fix it.
2. **A saved plan and a saved pillar collection are different objects.** The
   native badge shows pillars; the set can still be empty. Do not conflate them
   in the new navigation, counters or persistence model.
3. **Resume exists as a manual operation, not the proposed start experience.**
   `app.js::start` restores pad edits and playlists and selects the first track;
   it does not restore the last set. Plans and Save are under expanded build
   settings in the observed screen. TUI's named save does not update the shared
   pointer through `stan.plan.zapisz`; this needs an explicit shared policy.
4. **Some persistence is still unsafe or path-sensitive.** Stage A made plans,
   verdicts and pointer publication atomic. `user_store.save_state` and
   `Most.zapisz_edycje` still use direct `write_text`; user state has a relative
   `STATE_PATH`. The per-library state filename hashes the resolved pool path.
5. **Availability is contradictory.** `budowa.ma_plik` checks only whether a
   path starts with `/`; `tui.zrodlo.zrodlo` checks existence. Measured differences
   are in the table above. Source and playability need one explicit contract.
6. **Import reporting loses detail.** `przeanalizuj_folder` returns only the first
   five gate rejections and first five analysis failures in textual notes. It
   supports a cancellation callback, but GUI scan does not pass one.
7. **Jobs and close have no full product policy.** The GUI uses daemon threads;
   `okno.py` attaches the audio cleanup to `closed`. No native dirty-set close
   guard or GUI scan cancellation was found in the inspected paths.
8. **Restored sets lack generation context intentionally.** `_wczytaj_plan_teraz`
   clears weights and edit context; candidate calculation may refuse. Manual
   arrangement must work independently of those weights.
9. **Desktop distribution is unverified.** Current CI uses Ubuntu and does not
   exercise a macOS GUI profile. `sciezki.KORZEN` assumes a source checkout;
   `run_app.sh` still references removed `dancelab.host.desktop_app`.

**New test-isolation finding:** `test_gui_odsluch.py` mocked plan reading but left
`stan.plan.WSKAZNIK` pointing at personal storage while loading `/plany/B.json`.
The current pointer matches that synthetic value. This test is fixed in this
planning increment by redirecting the pointer to `tmp_path`; that is a test-only
repair, not implementation of the new GUI. The missing prior pointer value was
not guessed or replaced; the nine saved plans remain available for explicit
selection. Exact time/origin of the first overwrite was not established.

## 3. User journeys, including failure paths

| Scenario | Proposed visible sequence | Existing foundation | Required new work / acceptance |
| --- | --- | --- | --- |
| First use, existing library | Open desktop → choose detected library → see source/missing-data summary → browse | Header reader and filters | Profile/library choice; no hard-coded research directory presented as onboarding |
| First use, new folder | Open → choose folder → scan progress → complete accepted/rejected list → browse | Shared scanner and gate | Native picker, structured complete report, cancellation and independent profile |
| First manual set | Add one track → add another → reorder → optionally mark a pillar → name → save | Some edit primitives and plan store | Empty draft, explicit add, per-set constraints and visible dirty state |
| Return after restart | Open → last saved set summary → Resume → restore name/order/constraints → continue | Plan list and async loader | Resume surface, complete draft schema, no automatic playback/export |
| Broken pointer / moved source | Open → explain unavailable last reference → offer saved plans; show unavailable rows | Existing list and matching notes | Do not turn failure into a blank set or silently pick a different plan |
| Streaming entry | Browse/add/reorder → see audio unavailable → inspect export eligibility | Metadata and current matching/writer | Keep set preparation enabled; export matching remains separate from playback |
| Missing local file | Retain row and saved reference → show missing source → locate/retry or omit explicitly | Source helpers and notes | Unified capability result; restore placeholders instead of silently dropping from working view |
| Edit after export preview | Review → return to editing → change order/name → previous preview expires | Existing invalidation checks | Surface the requirement to review again; test with a disposable database |
| Save failure / app close | Failure keeps dirty work in memory → retry/change destination/recovery; close offers save/discard/cancel | Atomic plan publication | Native close handling and recovery; never label failed save as saved |
| Long operation | Show progress → cancel safely or wait → inspect partial results → retry | Existing worker/polling patterns | Job identity, cancellation, stale-result rejection, window-close policy |

**First acceptance run:** five known tracks from a disposable test library,
including one streaming reference and one missing-file case. Build a manual set,
change order, mark one explicit pillar, save, close and resume. Verify all
references and flags, then test export eligibility separately. Use a second
fixture with at least five Rekordbox-matchable tracks for the export acceptance.
This avoids expecting every metadata-only or missing-file row to be exportable.

**Repeat-use run:** reopen an existing named set with saved edits and multiple
library profiles; no forced onboarding, automatic audio or unexpected export.
Include corrupt/absent pointer, changed library path and interrupted operation.

## 4. GUI structure and design-system work

Proposed hierarchy for the existing desktop window:

- **Library:** source/profile selector; search/filter/sort; track list; visible
  Add action and source/capability labels. Inspection remains one click away.
- **Sets:** saved sets, Resume, New set; working order alongside the library;
  explicit pillars; name, dirty/saved state, undo and Save always discoverable.
- **Track detail / cue editor:** existing waveform, overview/zoom, pads and
  provenance. Preserve working controls while replacing surrounding navigation.
- **Review and export:** destination, actual match count, individual exclusions,
  backup outcome and confirm action. Playlist and cue export are distinct choices.
- **Optional tools:** generation settings, sound references and scan/job details.
  They do not hide Save/Resume or block manual preparation.

Reuse the current local Bricolage/IBM Plex fonts, warm dark surfaces and amber
selection. Consolidate tokens and components in the production static assets:
buttons, inputs, track rows, set rows, status messages, empty/error states,
progress, dialogs and focus handling. Record density/contrast/keyboard behaviour.
Keep the default supported minimum window size 1040×640 until a smaller layout
is explicitly implemented and tested. Test that size and 1440×900; desktop
window sizing is the target, not a mobile website release.

The new preparation route must be previewed and accepted **inside the desktop
shell**. A demo adapter can be used during layout work only if clearly marked;
the first vertical slice uses real Engine operations and durable files.

## 5. Integration design and data contracts

Retain `gui/okno.py`, WKWebView and `Most`; introduce narrow services in `stan/`
for the touched workflow. TUI and GUI consume the same services. Do not migrate
all of `most.py` or all of TUI before delivering the first slice.

| Contract / proposed responsibility | Current source | Planned change | Compatibility rule |
| --- | --- | --- | --- |
| Runtime paths and library identity | `sciezki.py`, `user_store.sciezka_stanu`, `Most.KATALOG_ANALIZ`, TUI default | Explicit profile/path service; stable library ID; separate runtime data from resources | Old path-hash state mapped to new library ID before switching roots |
| Library entry capabilities | `stan/biblioteka.py`, `budowa.ma_plik`, `tui/zrodlo.py` | Distinguish source, existence, can-add, can-preview and export eligibility with reasons | Unknown/missing state stays visible; no guessed audio features |
| Working draft | `Most._kolejnosc`, `_ctx_edycji`, user-store pillars | Proposed versioned draft: ID/name/library ID, ordered track references, per-set pillars/roles, revision and origin | Add does not imply pillar; no generator weights required for manual edits |
| Save/restore | `stan/plan.py`, `tui/plan_store.py`, cue overrides | Atomic files, snapshot/revision policy and resumable draft fields | Read existing plans; never silently discard unknown/missing references |
| Source provenance | `stan/dziennik.py`, `_kandydaci_meta` | Explicit manual vs suggested origin for new add route | Manual action must not inherit stale candidate rank/score |
| Background jobs | Bridge dictionaries and threads | Start/status/cancel with job identity and stale-result protection | Existing operations remain adapters until migrated; no silent partial success |
| Export | `stan/playlista.py`, `stan/zapis_cue.py`, ingestion writers | Reuse guarded prepare/commit semantics | Order/name/edit changes invalidate the prepared export |

These are proposed contracts, not new methods already present in the bridge.
Use the repository's existing Pydantic convention where new typed outputs are
introduced. Do not add another web server or require PostgreSQL just to open the
personal-library GUI. The optional catalog is a separate adapter opportunity.

**Migration sequence:** inventory and copy → verify copy/restore → assign stable
library identity → explicitly map legacy profile/plan references → validate on
copies → switch the selected profile → retain legacy data for rollback. Do not
move the 1.33 GB analysis collection or rewrite audio paths as a side effect of
redrawing the GUI. `~/Library/Application Support/DanceLab` is the proposed
writable desktop root; external libraries can remain in user-selected locations.

**Concurrent use:** sharing a file does not guarantee simultaneous edits are
safe. Until revision/conflict handling passes, designate one editing instance;
second instances should explain the restriction. Test stale GUI/TUI saves and
pointer updates instead of claiming live bidirectional synchronisation.

## 6. Work packages, order, estimates and acceptance

One implementation owner at a time in this checkout. ENG/DATA and UX are
responsibility labels, not newly spawned tasks or simultaneous writers. Jan owns
product acceptance; the implementing developer owns code, verification and the
handoff. ML/TWIN work is not on this critical path.

Estimates below are **engineering judgement**, not measurements, calendar dates
or a promise about agent runtime. One day means 6 focused engineering hours.
Ranges include implementation and its checks, but exclude waiting for review,
recruiting DJs, Apple account/signing arrangements and hardware availability.
Re-estimate after P2 and P5 using actual outcomes.

| Package | Result and concrete files / area | Depends on | Estimate | Done means / rollback |
| --- | --- | --- | --- | --- |
| P0 — trustworthy baseline | Isolate test writes, snapshot personal stores, enumerate the 9 saved plans and broken pointer; `tests/`, recovery evidence | None | 0.5–1 day | Isolated tests leave personal-file hashes unchanged; recovery choices explicit. Keep original snapshots; do not guess the last plan. |
| P1 — desktop entry and navigation specification | Distinct GUI launch identity; production shell route and design-component/state map; `gui/okno.py`, launch assets, `gui/statyczne/` | P0 | 1–2 days | Finder opens the native window; new route marked correctly; current track/cue route remains reachable. Old route is fallback. |
| P2 — profiles, persistence and restore foundation | Path/profile service, stable library identity, atomic user/cue saves, compatible plan reader; `sciezki.py`, `stan/`, `tui/user_store.py`, storage | P0; UI can be prepared in P1 | 2–3 days | Copy-based migration preserves 8 playlists, 7 favourites and plan references; old root remains usable; explicit concurrent-edit policy. |
| P3 — real library and import | Unified availability, shared filters, folder picker, complete rejection report/cancel; `stan/biblioteka.py`, `budowa.py`, GUI adapter | P1, P2 | 2–3 days | The actual 8260-entry library loads; streaming/missing/relative paths get correct capabilities; scan cancellation does not claim completion. Existing data source remains selectable. |
| P4 — manual working set | Empty draft, add/append/remove/reorder, separate pillars, undo, origin; new narrow `stan` service and GUI preparation view | P2, P3 | 3–5 days | 1- and 2-track drafts work without generation; add never creates a pillar; edits retain explicit origin and invalidate export preview. Feature-route fallback retains old GUI. |
| P5 — save, close and resume | Draft schema/revision, visible save state, native close guard, resume/recovery surface; plan store + both adapters | P4 | 2–3 days | Native close/reopen preserves name, order, pillars and edits; failure keeps work; legacy plan and TUI cross-read pass. Restore snapshot/legacy reader if migration fails. |
| P6 — inspection, audio and assistance | Integrate current waveform/cues/player, optional candidates and sound references | P5 | 2–4 days | Local-file play/pause/seek and close cleanup pass; streaming/missing audio explains refusal; unknown generator context never fabricates suggestions. Keep old detail route until parity. |
| P7 — reviewed export | Integrate existing playlist/cue prepare-and-write flows, per-track eligibility and backup result | P5, P6 | 2–4 days | Changed order invalidates preview; copied database confirms expected writes/backup; native trial explicitly reviewed. Preserve backup and old writer. |
| P8 — distributable macOS build | Packaging feasibility proof, bundled runtime/resources, data root, clean-Mac install/update test, macOS gate | Early feasibility after P2; final after P7 | 3–5 days | Runs without checkout/.venv on agreed macOS target; runtime/audio dependencies explicit; update preserves data. Keep previous app + compatible data snapshot. Packaging-tool choice follows proof. |
| P9 — observed acceptance and fixes | 3–5 target DJs, first/repeat-use sessions, task outcomes and blockers | P7 for dev-build trials; P8 for distribution acceptance | 2–3 days | Evidence recorded; no data loss/false success; blocked tasks resolved or release held. Current production GUI remains available. |

**Dependency chain:** P0 → P2 → P3 → P4 → P5 → P6 → P7 → final P8 → P9.
P1 must finish before P3. Investigate packaging after P2 so a runtime-distribution
problem is found before the final stage; do not wait until P7 to discover it.

**Milestones and scope totals:**

- P0–P5: real-library manual set + save/restart/restore in its own desktop window;
  approximately **10.5–17 focused days** under the assumptions above.
- P0–P7: preparation workflow with audio/assistance and reviewed export;
  approximately **14.5–25 focused days**.
- All packages: distributable build and acceptance/fixes;
  approximately **19.5–33 focused days**. External waiting is additional.

These are additive work estimates for a serial implementation, not a commitment
to elapsed delivery dates. A copy-only launcher must not be reported as P8 done.
The broad 140-document cleanup can continue as a separate DATA backlog; only
runtime-data ownership, recovery and current entry documentation block this GUI.

### First executable ticket

**P0: protect the development/acceptance data boundary.** The planning session
already fixes the one demonstrated test-pointer leak. Remaining steps: enumerate
all persistent write targets; direct acceptance runs to a disposable profile;
record source and restored-copy hashes; expose the missing current-plan target
without silently replacing it; choose the last set explicitly from the nine
saved plans if the owner wants to resume. No production data migration is part
of this first ticket.

### Release gate

- Repository gate and JS regressions pass; add native macOS profile/build checks.
- Before external distribution, exercise untrusted metadata rendering, allowed
  navigation and bridge input/file boundaries in WKWebView; unresolved security
  findings block the release. This is not a substitute for a full pentest.
- First and returning-user journeys run in the actual desktop window.
- Real-library versus synthetic fixtures are identified in each report.
- Backup/restore, save failure, missing source and concurrent-write cases pass.
- Native player shutdown and reviewed export behaviour have direct evidence.
- No use of an unknown value as a plausible measurement; no silent dropped rows.
- Each package has a local reviewed commit and reversible rollout. User-owned
  runtime files and audio never enter Git.

## Source anchors and evidence limits

- [Desktop shell](../../../src/dancelab/gui/okno.py),
  [bridge](../../../src/dancelab/gui/most.py),
  [production JS](../../../src/dancelab/gui/statyczne/app.js),
  [TUI](../../../src/dancelab/tui/app.py).
- [Shared plan](../../../src/dancelab/stan/plan.py),
  [plan store](../../../src/dancelab/tui/plan_store.py),
  [user state](../../../src/dancelab/tui/user_store.py),
  [scanner / availability](../../../src/dancelab/stan/budowa.py),
  [source classification](../../../src/dancelab/tui/zrodlo.py).
- [Stage A results](../2026-09-06-stage-a/README.md),
  [product brief](../2026-09-06-stage-a/PRODUCT_BRIEF.md),
  [design system](../2026-09-06-stage-a/DESIGN_SYSTEM.md),
  [original workstream plan](../../audits/2026-09-06/PLAN_PRACY.md).
- [Verification](VERIFICATION.md) separates fresh checks, prior results and work
  still unverified. Existing audits remain historical, not silently rewritten.

No interview, full native playback test, live Rekordbox write, clean-Mac package
acceptance, production migration or ML/TWIN implementation was performed while
preparing this plan. Native inspection was limited to navigation and reading.
