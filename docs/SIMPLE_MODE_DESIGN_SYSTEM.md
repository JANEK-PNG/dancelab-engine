# DanceLab Pro Simple Mode Design System

> **Historical document (2026-07-28).** The desktop product described below
> has been removed and is not a supported launch or QA path. DanceLab is
> terminal-first; see [the documentation index](README.md).

Status: current-state design system, v0.1  
Scope: the guided DanceLab Pro desktop product only. The legacy visual graph
editor has been removed; headless engine adapters remain an implementation detail.

This document describes the interface that exists today or is directly implied by the current Simple Mode implementation in:

- `src/dancelab/host/simple_mode.py`
- `src/dancelab/host/pair_review.py`
- `src/dancelab/workflows/smart_playlist.py`
- `src/dancelab/export/rekordbox.py`

## 0. Sources And Direction

Reference principles, not copied visuals:

- Apple Human Interface Guidelines: hierarchy, feedback, sidebars, progress, subtle materials.
- IBM Carbon: token discipline, component documentation, accessibility checklist mindset.
- Material 3: semantic color roles, adaptive layout, runtime progress and loading state clarity.

DanceLab combines these as:

- Apple-like clarity: simple hierarchy, visible feedback, calm surfaces.
- IBM-like structure: tokenized decisions, component states, accessibility discipline.
- Material-like runtime logic: clear loading/progress states, semantic color roles, adaptive panes.

Do not copy Apple, IBM, Google, Rekordbox, Ableton, or any existing brand 1:1.

Useful source pages:

- Apple HIG: sidebars, feedback, progress indicators, materials.
- IBM Carbon: component checklist, accessibility, typography, token discipline.
- Material 3: design tokens, spacing tokens, progress indicators.

Current product priority:

```text
Simple Mode = product
Visual Graph Mode = removed
Headless engine/runtime adapters = retained
Do not design or rebuild a visual graph without a new product decision
```

DanceLab Simple Mode is a guided professional workflow, not a dashboard and not a developer tool.

Every Simple Mode screen must answer:

- Where am I?
- What is done?
- What is missing?
- What do I click next?
- Is the engine running?
- How long will it take?
- Is the project saved or exported?
- Where is cache stored?

## 1. Product Principles

- Guided first: the default experience is a linear DJ workflow, not a technical workspace.
- Honest engine: labels must say candidate, estimated, cached, failed, stopped, or exported when that is the true state.
- One primary action per step: each screen has one blue action that moves the user forward.
- Runtime clarity: every long-running action shows determinate progress when the total is known.
- DJ control without settings overload: intent controls are exposed as set brief, BPM range, style focus, energy arc, planner preference, Must Have, Lock, and Rest.
- Safe export: Rekordbox export sends playlist order and hot cues, not forced beat sync or BPM/grid override.

## 2. Visual Direction

- Dark professional interface with matte graphite and deep navy surfaces.
- Active accent is cyan/blue.
- Complete state is green.
- Review/caution is amber.
- Danger is red.
- Disabled/locked is gray.
- No flashy gradients, no neon dashboard, no toy mascots in the production UI.
- Depth should be subtle: borders, surface steps, and soft focus states instead of heavy shadows.

Reference moodboard translation:

- Use modular dashboard cards with generous spacing and clear grouping.
- Use large, calm status numbers for important facts: analyzed tracks, target set size, BPM window, export state.
- Use pill controls for compact mode switches only when the choices are mutually exclusive.
- Use soft raised cards and border-based depth; avoid heavy glassmorphism or glossy panels.
- Use one strong active accent per screen; do not color every metric as if everything is urgent.
- Keep controls near the data they affect, like professional finance/analytics tools.

Do not copy from the references:

- Donut/radar/bubble charts that look premium but make comparison harder.
- Generic AI helper cards unless there is a real engine recommendation and a real next action.
- Marketing dashboard tiles that do not affect the DJ workflow.
- White/light mode in this phase; DanceLab remains dark professional until core usability is stable.

## 3. Color Tokens

Canonical DanceLab tokens for the next Simple Mode visual pass:

```css
--dl-bg-canvas: #05070B;
--dl-bg-surface: #0B0F14;
--dl-bg-surface-elevated: #111821;
--dl-bg-surface-soft: #151C25;
--dl-bg-glass: rgba(18, 24, 32, 0.78);

--dl-border-subtle: #232B36;
--dl-border-strong: #354151;

--dl-text-primary: #F5F7FA;
--dl-text-secondary: #B6C0CC;
--dl-text-tertiary: #7E8A99;
--dl-text-disabled: #566170;

--dl-accent-primary: #5CC8FF;
--dl-accent-secondary: #7CF7D4;
--dl-accent-muted: #2A5E78;

--dl-status-complete: #38D996;
--dl-status-active: #5CC8FF;
--dl-status-running: #B9A7FF;
--dl-status-review: #FFB454;
--dl-status-danger: #FF5A66;
--dl-status-locked: #5D6875;

--dl-genre-safe: #38D996;
--dl-genre-review: #FFB454;
--dl-genre-bridge: #B9A7FF;
--dl-genre-reset: #FF8A4C;
--dl-genre-not-recommended: #FF5A66;
```

Current Qt polish pass uses close first-pass equivalents. Future UI edits should migrate hardcoded QSS colors to these token names.

| Role | Token |
|---|---|
| Main app background | `--dl-bg-canvas` |
| Pane/list/card surface | `--dl-bg-surface` |
| Raised controls and selected panels | `--dl-bg-surface-elevated` |
| Primary action, active step, progress | `--dl-accent-primary` |
| Complete/analyzed state | `--dl-status-complete` |
| Running process state | `--dl-status-running` |
| Review/manual-listen state | `--dl-status-review` |
| Danger/failure state | `--dl-status-danger` |
| Disabled/locked state | `--dl-status-locked` |

## 4. Typography Tokens

Font stack:

```css
--dl-font-ui: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "IBM Plex Sans", system-ui, sans-serif;
--dl-font-mono: "SF Mono", "IBM Plex Mono", "Roboto Mono", monospace;
```

Type scale:

```css
--dl-type-display-size: 32px;
--dl-type-display-line: 40px;
--dl-type-display-weight: 650;

--dl-type-title-size: 24px;
--dl-type-title-line: 32px;
--dl-type-title-weight: 650;

--dl-type-section-size: 18px;
--dl-type-section-line: 26px;
--dl-type-section-weight: 600;

--dl-type-body-size: 14px;
--dl-type-body-line: 22px;
--dl-type-body-weight: 400;
--dl-type-body-strong-weight: 560;

--dl-type-caption-size: 12px;
--dl-type-caption-line: 16px;
--dl-type-caption-weight: 450;

--dl-type-mono-size: 12px;
--dl-type-mono-line: 16px;
```

Current Simple Mode uses productive/tool typography, not marketing typography. Default body is `14px` for the design system; current Qt polish still has some `13px` first-pass styling and should migrate gradually.

## 5. Spacing Tokens

```css
--dl-space-0: 0;
--dl-space-1: 4px;
--dl-space-2: 8px;
--dl-space-3: 12px;
--dl-space-4: 16px;
--dl-space-5: 20px;
--dl-space-6: 24px;
--dl-space-8: 32px;
--dl-space-10: 40px;
--dl-space-12: 48px;
--dl-space-16: 64px;
```

Usage:

- Small component gap: `8px`.
- Card internal padding: `16-20px`.
- Panel padding: `24px`.
- Screen margin: `24-32px`.
- Column gap: `16-24px`.

## 6. Radius Tokens

```css
--dl-radius-xs: 6px;
--dl-radius-sm: 10px;
--dl-radius-md: 14px;
--dl-radius-lg: 18px;
--dl-radius-xl: 24px;
--dl-radius-pill: 999px;
```

Usage:

- Controls: `10-12px`.
- Cards/lists: `14-18px`.
- Large sheets: `24px`.
- Status chips: `pill`.

## 7. Elevation/Depth Tokens

```css
--dl-shadow-0: none;
--dl-shadow-1: 0 1px 2px rgba(0,0,0,0.24);
--dl-shadow-2: 0 8px 24px rgba(0,0,0,0.28);
--dl-shadow-3: 0 16px 48px rgba(0,0,0,0.38);
```

Depth roles:

- `depth.none`: flat background, no border.
- `depth.surface`: subtle border on `--dl-bg-surface`.
- `depth.control`: control border with hover fill.
- `depth.active`: blue/cyan border or fill, never both unless primary button.
- `depth.modal`: sheet/modal surface with dark overlay and elevated border.

Current app uses border-based depth only. Do not add large shadows in this pass.

## 8. Motion Tokens

```css
--dl-motion-fast: 140ms;
--dl-motion-base: 220ms;
--dl-motion-slow: 360ms;

--dl-ease-standard: cubic-bezier(0.2, 0, 0, 1);
--dl-ease-exit: cubic-bezier(0.4, 0, 1, 1);
--dl-ease-enter: cubic-bezier(0, 0, 0.2, 1);
```

Usage:

- Hover/focus: fast.
- Panel open: base.
- Progress update: base, driven by real callbacks.
- Modal sheet: slow.
- Reduced motion: all decorative motion removable.

Current Qt implementation is mostly static; do not add decorative animation until performance is stable.

## 9. Icon Rules

- Use icons only when they clarify state or DJ action.
- Current accepted icons: `✓` complete, `○` pending, `●` current, `▶` running/primary action, `✗` failed, `📌` Must Have, `🔒` Lock, `🌙` Rest/Not Tonight, `⚠` review warning.
- Icons must always have nearby text.
- No icon-only primary buttons.
- Emoji controls are tolerated in current Simple Mode but should become consistent symbol icons in a later visual pass.

## 10. Layout Grid

- Current app shell: left sidebar fixed at `250px`, right workspace flexible.
- Target Simple Mode shell: top project bar, left workflow stepper, center workspace, optional right context/status panel.
- Target desktop widths: left workflow `280-320px`, right status `320-380px`, top bar `56-64px`, center flexible.
- Main page margin: `24-32px`.
- Current bottom nav/status bar: fixed height content strip with Back, guidance text, Next.
- Step workspace: vertical rhythm; one action row near the top, primary content/list below.
- Review workspace: two-pane split; transition list left, A/B review player right.

## 11. App Shell

Current shell:

- Left sidebar with product name and workflow stepper.
- Main stacked workspace.
- Bottom navigation/status bar.

Target shell, not yet fully implemented:

```text
Top Project Bar
Left Workflow Stepper | Current Step Workspace | Context/Status Panel
```

Rules:

- Do not expose technical editor controls in the Simple Mode shell.
- Keep the primary flow visible at all times.
- The bottom bar owns “what next?” guidance.
- The stepper owns “where am I?” and “what is done?”.
- A future right context panel may show step explanation, engine status, cache status, warnings, and next recommended action.

## 12. Project Top Bar

Current implementation does not have a separate project top bar. Current project-level state is distributed across:

- Window title: `DanceLab Pro`.
- Welcome actions: `New Set`, `Open Project...`.
- Export screen: playlist name and XML path.
- Bottom nav hint.

Current-state design rule:

- Do not invent a complex top bar until project save/open is a Simple Mode-first feature.
- If added later, top bar may show app name, project name, saved/unsaved state, last saved time, New/Open/Save, current mode label, cache root shortcut, and engine idle/running state.
- Do not include zoom, graph controls, sensor debug, or developer actions.

## 13. Workflow Stepper

Current steps:

1. Import Tracks
2. Initial Check
3. Generate Set
4. Review Transitions
5. Export

Target workflow map from the product brief, not fully split into UI screens yet:

1. New Project
2. Import Tracks / Rekordbox source
3. Choose Analysis Mode
4. Analyze Library
5. Choose Current Track
6. Set DJ Intent
7. Generate Mix Ideas
8. Review Transitions
9. Build Set Sequence
10. Export / Save

Current Simple Mode compresses this target map into the five shipped steps above. Do not add more visible steps until each has real functionality and a clear next action.

Visual states:

- Current: `●`, white text, blue/navy active background.
- Complete: `✓`, green text.
- Pending: `○`, muted gray text.

Rules:

- Stepper is not a button cluster today; it is orientation.
- The active step must remain visually stronger than completed steps.
- Completed state means the step has enough data to proceed, not that the result is musically validated.
- Future step items may include number, title, status icon, short status, result count, and CTA hint.

Supported state vocabulary:

- `locked`
- `ready`
- `active`
- `running`
- `complete`
- `error`
- `needs_review`
- `cached`
- `skipped`

## 14. Current Step Workspace

Current component structure:

- Title.
- One short hint.
- Primary action row.
- Main list/table/review panel.
- Local status text.

Rules:

- The first control after the hint should be the next likely action.
- Long explanations go in tooltips or status panel, not title area.
- Empty main content must explain what to do next.

## 15. Context/Status Panel

Current status surfaces:

- Bottom nav hint.
- Import summary.
- Analyze status.
- Generate status.
- Deep status.
- Validation status.
- Export status.

Rules:

- Status copy must be factual and short.
- Runtime status must include count when known: `Analyzing 3/24`.
- Cache status must include estimated size, free disk, cache root, and backend label where available.

## 16. Buttons

Current roles:

- `hero`: primary forward action, blue.
- `secondary`: normal alternative action.
- `quiet`: low-emphasis action.
- `danger`: destructive or stop action.
- `rating`: compact validation score button.

Rules:

- One `hero` action per screen section.
- Cancel/Stop must never look like the next step.
- Disabled buttons must remain visible but muted.
- Button labels should be verbs: `Choose Folder(s)...`, `Run Initial Check`, `Generate Set`, `Export Rekordbox XML`.

## 17. Inputs

Current inputs:

- Folder/file/USB pickers.
- Combo boxes for arc, planner preference, variation, preset, set role, energy.
- Text input for style focus.
- BPM min/max numeric inputs.
- Count/duration controls.
- Playlist name and export path.
- Rater and comment fields.

Rules:

- Every input must have a visible label or immediate contextual label.
- Placeholder text is helpful, not a replacement for label.
- Numeric ranges must be bounded and explain `No min` / `No max`.

## 18. Status Chips

Current app mostly uses text statuses, not chips. Current accepted chip semantics for future small additions:

- Complete: green, e.g. `Cached`, `Analyzed`, `Exported`.
- Review: amber, e.g. `Manual listen`, `Risky key`.
- Danger: red, e.g. `Failed`, `Low disk`.
- Locked: gray, e.g. `Locked`, `Not Tonight`.
- Active: blue, e.g. `Running`, `Current`.

Do not add decorative chips that duplicate obvious text.

## 19. Cards

Current app uses lists and review panels more than cards. Card treatment should apply to:

- Future cache/storage panel.
- Future set brief summary.
- Future export summary.
- Transition review blocks if list readability becomes poor.

Card rules:

- Surface background `color.bg.surface`.
- 1px subtle border.
- Title, one metric row, one action row maximum.

## 20. Tables/Lists

Current lists:

- Imported tracks.
- Per-track analysis checklist.
- Generated set sequence.
- Transition list.

Rules:

- Lists should show status prefix first: `✓`, `▶`, `✗`.
- Track list rows may include title, BPM, key, duration, style.
- Generated set rows may include position, Must Have/Lock badges, title, BPM, key, style.
- Transition rows should show `A → B`, score only when not in blind mode, and warning only when actionable.

## 20A. Data Visualization Rules

Reference: UX Planet, "Data visualization. How to make it understandable" by Erik Messaki, Jan 24 2026.

Purpose:

- DanceLab visualizations must reduce DJ decision effort, not become puzzles.
- The user is often under time pressure before a set; every visual must be readable at first glance.
- Pretty but ambiguous analytics are treated as product defects.

Core rules:

- Prefer position, length, and timeline alignment over angle, area, volume, or decorative geometry.
- Use text labels and short explanations near the visual; never assume the chart explains itself.
- Use color as a status layer, not as the only carrier of meaning.
- Avoid visual forms that imply certainty when the engine result is an estimate.
- If a visual cannot answer "what do I do next?", it is not ready for Simple Mode.

Allowed default forms:

- Horizontal bars for style distribution, BPM spread, energy comparison, risk components, and transition score components.
- Linear timelines for waveform, phrase structure, beatgrid, hot cues, mix-in, and mix-out.
- Ordered lists for set sequence, transition candidates, failed tracks, and cache actions.
- Small inline badges only for discrete states such as `Cached`, `Manual listen`, `Risky key`, `Locked`, `Rested`.

Avoid by default:

- Donut and pie charts for style distribution; use sorted horizontal bars instead.
- Radar/spider charts for track compatibility; use row-by-row components with labels instead.
- Bubble charts for mixability; use ranked rows or scatter only if tooltips and axes are explicit.
- Heatmaps without a visible scale, legend, and written interpretation.
- Dual-axis charts for BPM/energy/key relationships; split into separate panels instead.
- 3D, radial, decorative lollipop, or outline-only charts.

DanceLab-specific application:

- Style summary: sorted horizontal bars with count and percentage labels, not a donut.
- BPM library summary: histogram or range strip with min, median/mean, and selected range markers.
- Generated sequence: ordered list plus optional small linear energy/BPM strip, not a complex network view.
- Transition review: Rekordbox-like horizontal waveform/structure timeline with labeled mix-in/out, beatgrid, and cue markers.
- Mixability explanation: compact component rows such as BPM fit, key fit, energy fit, phrase fit, vocal/bass risk.
- Confidence: show `estimated`, `source tag`, `cached`, `manual listen recommended`, or `exported` directly in text.

QC checklist:

- Can a non-technical DJ understand the visual in under 5 seconds?
- Is there a visible label for every axis, marker, and color role?
- Does the visual preserve honest uncertainty?
- Does it avoid angle/area comparison unless there is no better option?
- Does it support the next action: generate, review, deep-analyze, pin, rest, export, or listen?

## 21. Progress Components

Current progress:

- Determinate progress bar for Initial Check.
- Per-track checklist with real pipeline stages.
- Stop Processing button.
- Deep analysis status text.
- Runtime estimate text with cache size, free disk, cache path, and backend label.

Rules:

- Use determinate progress when total track count is known.
- Never show a bare spinner for library analysis.
- The current stage text must come from real engine callbacks.
- The stop button copy must explain that completed tracks remain cached.
- Progress bar text is hidden; detail lives in status copy and checklist rows.

Required analysis estimate fields:

- Tracks selected.
- Already cached/analyzed tracks when known.
- New tracks to process when known.
- Analysis mode.
- Estimated time when available.
- Estimated cache size.
- Available disk.
- Hardware backend.

Processing panel anatomy:

```text
Title: Processing tracks
Progress: 12 / 24
Current task: Separating stems
ETA: 03:20
[Stop Processing]
[View Details]      # future; not current
```

Current Simple Mode has Stop Processing but does not yet expose a dedicated View Details panel.

## 22. Modals/Sheets

Current modals:

- Suspicious audio confirmation.
- Stop processing confirmation.
- Must Have removal confirmation.
- Must Have vs Not Tonight conflict dialog.
- File/folder/export pickers.

Rules:

- Modal title is the user question.
- Body explains consequence.
- Default action should be safe.
- Destructive action must be visibly secondary/danger, not blue.

Stop modal copy pattern:

```text
Stop this job?

DanceLab will stop after the current track.
Tracks already processed will be saved and will not need to be processed again.

[Keep Running]
[Stop After Current Track]
```

`Stop Now` is not current behavior; cooperative stop after current track is the implemented model.

## 23. Toasts/Notifications

Current app uses inline status labels, not toast notifications.

Current-state rule:

- Keep inline status for now.
- Toasts may be added only for non-blocking events like “Project saved” or “Export complete”.
- Errors that require action stay inline or modal.

## 24. Tooltips/Help

Current tooltips exist for USB import, duration estimate, variation, DJ controls, deep analysis, and project/advanced actions.

Rules:

- Tooltip copy must answer “why would I use this?” in one sentence.
- Avoid formula language in tooltips.
- Tooltips should not hide required instructions.

## 25. Empty States

Current empty states:

- Import list: `No tracks yet.`
- Analyze: `Not started.`
- Generate: `Analyze tracks first.`
- Review: empty until set exists.
- Export: generate required.

Rules:

- Empty state must include next action.
- Empty state should not blame user.
- Use one sentence plus a button if possible.

## 26. Error States

Current error states:

- No supported audio files.
- Analysis failed.
- Track failed.
- Constraint problem.
- Low disk blocks deep analysis.
- Export requires generated set.

Rules:

- Error copy must state what failed and what remains safe.
- Failed tracks stay visible in the checklist.
- Constraint errors must preserve user intent rather than silently dropping pins/locks.

## 27. Cache/Storage Panels

Current implementation exposes cache info in estimate text:

- Estimated cache.
- Free disk.
- Cache path.
- Backend label.
- Low disk blocks deep analysis.

Current-state design rule:

- This is currently text, not a dedicated panel.
- If promoted, use a compact card in Analyze and Deep Analysis areas.
- Always show cache root when storage is discussed.
- Never silently write large stem artifacts without user-visible path/status.

## 28. Must Have Controls

Current controls:

- `Pin`: Must Have, max 10.
- `Lock`: exact slot.
- `Rest`: Not Tonight.

Rules:

- Must Have means “include if possible; engine chooses slot unless locked”.
- Lock means “keep this exact set position”.
- Rest means “exclude this session; do not delete file”.
- Conflicts must open a dialog, not auto-resolve silently.
- Must Have counts as intentional carryover and does not remove risk warnings.

Current copy patterns:

- Limit: `You have to make a sacrifice. You can only have 10 Must Have tracks. Choose wisely.`
- Removal title: `Don't you love me?`
- Conflict title: `Two intentions`

## 29. Overplayed Controls

Current implementation has no dedicated Overplayed control.

Current equivalents:

- `Rest` for explicit “not tonight”.
- Variation/novelty mode and playlist history to reduce repeated set outcomes.
- Same-album/same-artist diversity pressure belongs in the planner, not a visible Overplayed panel today.

Current-state rule:

- Do not design a standalone Overplayed panel until the app exposes that data.
- If needed later, it should be a status/filter in Generate Set, not a new workflow step.

Not current:

- Exclude for 7 days.
- Exclude for 30 days.
- Lower priority as a persistent library flag.
- Last-used table column.

## 30. Mix Idea Cards

Current implementation does not have standalone Mix Idea Cards.

Current equivalents:

- Generated set sequence.
- Transition list.
- TransitionReviewWidget with A/B decks, waveform/structure strips, beat sync, quantized cueing, and rating.

Current-state rule:

- Do not invent a separate mix ideas screen now.
- If introduced later, cards should summarize pair idea, fit reason, risk, and one `Review` action.

Candidate future Mix Idea Card anatomy, not current:

- Track title and artist.
- BPM and Camelot key.
- Transition type.
- Fit reasons.
- Risk reasons.
- Confidence.
- One `Review` action.
- Explicit note that crowd-response prediction is blocked.

## 31. Transition Review Cards

Current transition review consists of:

- Left transition list.
- Right A/B transition review widget.
- Blind rating mode.
- Rater/comment fields.
- 1-5 rating buttons.
- CSV validation logging.

Rules:

- Review must make clear that candidates are estimates, not ground truth.
- Blind mode must hide score/risk framing that can bias the rater.
- Beat sync and quantize are preview-only behaviors.
- If user Rekordbox hot cues exist, verified cue reasoning can be shown.
- Transition review should surface cue source, recommended strategy, BPM/key relation, bass conflict, vocal clash, and manual-listen warning when available.

## 32. Export Panels

Current export screen:

- Playlist name.
- Output XML path.
- Browse.
- Export Rekordbox XML.
- Export status with hot cue count and Rekordbox instruction.

Rules:

- State that Rekordbox should analyze BPM/beatgrid.
- State what DanceLab exported: playlist order and hot cues.
- Show path after export.
- Show hot cue marker count.
- Export errors must preserve generated set state.

Not current in Simple Mode export:

- Export JSON.
- Export report.
- Export pilot annotation CSV.
- Export selected stem separations.

Stem export copy rule for future work:

```text
Deep Analysis prepares data for recommendations.
It does not automatically export stem files.
```

## 33. Accessibility Rules

- Minimum interactive height: 34px; primary action 42px.
- Text must maintain high contrast on dark surfaces.
- Do not rely on color alone: use icon/text state labels.
- Keyboard focus uses blue outline/border.
- Disabled controls remain legible.
- Modals must have safe default action.
- Validation/rating controls must be reachable without waveform interaction.

## 34. Copywriting Rules

- Use DJ language when it clarifies: `set`, `transition`, `hot cue`, `BPM`, `key`.
- Use engine language only when necessary: `Initial Check`, `Deep-Analyze`, `cached`.
- Never overclaim: say `candidate`, `estimate`, `review`, `manual listen`.
- Keep button labels short.
- Avoid “AI magic” language.
- Avoid repeating “analysis” everywhere; use `Initial Check`, `Deep-Analyze Set Tracks`, `Review`.

## 35. QC Checklist

Before showing Simple Mode to testers:

- The welcome screen has one obvious `New Set` action.
- The sidebar shows current, complete, and pending states.
- Every step has a primary next action.
- Import can accept folders and individual files.
- Suspicious files are confirmed before analysis.
- Initial Check shows determinate progress and per-track status.
- Stop Processing explains cached work is preserved.
- Generate Set exposes count/duration, style, BPM, role, energy, arc, preference, variation.
- Must Have/Lock/Rest controls are visible after a set exists.
- Review shows transition list and A/B review widget.
- Blind rating can save CSV rows.
- Export says no BPM/beatgrid override.
- Cache root/free disk is visible where storage is discussed.
- No Simple Mode copy depends on the deprecated advanced editor.

## 36. Figma Page Structure

Recommended Figma pages for this current-state system:

1. `00 Principles`: product principles, scope, current gaps.
2. `01 Tokens`: color, typography, spacing, radius, depth, motion.
3. `02 Foundations`: layout, icon rules, copy rules, accessibility rules.
4. `03 Components`: buttons, inputs, lists, progress, modals, tooltips, status text.
5. `04 Simple Mode Screens`: Import, Initial Check, Generate Set, Review, Export.
6. `05 Runtime States`: estimates, processing, stop modal, cached/failed/low disk.
7. `06 DJ Intent`: Must Have, Lock, Rest, variation, set brief controls.
8. `07 Export Cache Storage`: Rekordbox XML panel, cache/storage panels, success/error states.
9. `08 Copy System`: buttons, empty states, warnings, blocked claims.
10. `09 Accessibility`: contrast, keyboard, focus, state language.
11. `10 QC Checklist`: screenshot QA and component stability gates.

Do not create deprecated advanced editor pages in this design file.

Each component page must include purpose, anatomy, variants, states, spacing, tokens, behavior, accessibility, do/don't, and QC checklist.

## 37. Component Stability Rules

- Stable: app shell, workflow stepper, buttons, inputs, import list, analysis progress, generated set list, transition review, export panel.
- Beta: Deep-Analyze Set Tracks, validation rating flow, cache/storage text.
- Experimental/not current: Overplayed panel, standalone Mix Idea Cards, project top bar, toast system.
- Deprecated/out of current scope: previous advanced editor design.

No component becomes stable until:

- It has default, hover/focus, disabled, running, success, warning, and error state when applicable.
- It has copy rules.
- It has keyboard/accessibility behavior.
- It has empty, loading, and error behavior when applicable.
- It has responsive/adaptive behavior notes.
- It is represented in tests or screenshot QA.

Component lifecycle:

- `draft`
- `candidate`
- `ready for implementation`
- `stable`
- `deprecated`

## Key Simple Mode Screen Descriptions

Design-first screen set from the supplement:

1. No Project / Start Screen — current.
2. New Project Created — partially current through welcome/import state.
3. Import Tracks / XML — partially current; folders/files/USB current, XML not primary.
4. Large Sample Folder Warning — current through suspicious audio confirmation.
5. Choose Quick vs Deep — not a separate current step; quick is Initial Check, deep is after set generation.
6. Analysis Estimate — current as text; not yet a card.
7. Processing Running — current.
8. Stop Processing Modal — current.
9. Analysis Complete — current.
10. Choose Current Track — not a standalone current step.
11. Set DJ Intent — current in Generate Set.
12. Generate Mix Ideas — current as generated sequence/transitions, not cards.
13. Review Transitions — current.
14. Build Set Sequence — current inside Generate Set.
15. Export / Save — export current, save not first-class in Simple Mode.
16. Cache Settings / Low Disk Warning — low disk current, settings panel not current.

### 1. New Project

Current screen: welcome page.

- Answers “where am I?” with `DanceLab Pro`.
- Primary action: `New Set`.
- Secondary: open existing project through the legacy advanced editor, currently de-emphasized.
- Missing state: no project top bar or saved-state indicator yet.

### 2. Import Tracks / Rekordbox Source

Current screen: Step 1.

- Actions: `Choose Folder(s)...`, `Choose Files...`, `Import from USB...`.
- USB import reads Rekordbox device data and user hot cues when available.
- Shows imported track list and summary.
- Supports remove selected and clear import.
- Current app does not import Rekordbox XML as a primary Simple Mode source.

### 3. Choose Analysis Mode

Current screen equivalent: Step 2 Initial Check.

- There is no user-facing normal/deep picker at the start.
- Current behavior: Initial Check is normal/fast.
- Deep Demucs analysis is available later for generated set tracks only.
- This matches current product direction: do not make users choose deep analysis before knowing the set.

### 4. Analyze Library

Current screen: Step 2.

- Primary action: `Run Initial Check`.
- Shows progress bar, status text, per-track checklist, real pipeline stage callbacks, and stop processing.
- Shows estimated cache, free disk, cache path, and backend label in estimate text.

### 5. Choose Current Track

Current implementation has no standalone “current track” step.

Current equivalent:

- Selected row in generated set list.
- Selected row in transition review list.
- A/B decks in transition review.

Do not design a new step until the app supports a current-track-first workflow.

### 6. Set DJ Intent

Current screen: Step 3 Generate Set.

- Intent controls: track count or duration, energy arc, planner preference, variation/seed, set brief preset, style focus, BPM range, set role, crowd energy.
- Library profile summary reports detected styles and matching tracks after analysis.

### 7. Generate Mix Ideas

Current implementation does not expose separate mix idea cards.

Current equivalent:

- `Generate Set` produces set sequence and transitions.
- Transition list becomes the reviewable set of mix ideas.

### 8. Review Transitions

Current screen: Step 4.

- Left list: transitions.
- Right panel: A/B decks, waveform/structure strips, beat sync preview, 8-beat quantized cueing, stem isolation control, risk/score context when not blind.
- Validation row: blind mode, rater, 1-5 rating, comment.

### 9. Build Set Sequence

Current screen: Step 3.

- Generated set list is the sequence.
- DJ controls: Pin/Must Have, Lock, Rest/Not Tonight.
- Deep-Analyze Set Tracks can upgrade only selected set tracks after generation.

### 10. Export / Save

Current screen: Step 5.

- Inputs: playlist name, output XML path.
- Primary action: `Export Rekordbox XML`.
- Success copy includes path, hot cue marker count, and instruction that Rekordbox analyzes BPM/beatgrid.
- Current Simple Mode does not yet have a full `.dlproj` save workflow as a first-class top-bar feature.
