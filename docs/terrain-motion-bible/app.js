const item = (
  id, level, workspace, name, status, priority, code, source, trigger,
  motion, timing, easing, demo, owner, junior
) => ({
  id, level, workspace, name, status, priority, code, source, trigger,
  motion, timing, easing, demo, owner, junior
});

const components = [
  item("A01", "Atom", "Global", "Button press", "adapt", "P1",
    "Qt Widgets: QPushButton\nplanned: host/terrain/motion.py::press_feedback",
    "Pointer / keyboard event", "press / release",
    "2 px compression; no bounce", "90 ms", "standard", "button",
    "E-M1 + MD-M1", "E-J1: verify keyboard press has the same final state."),
  item("A02", "Atom", "Global", "Button busy", "adapt", "P0",
    "simple_mode.py::preview_button\nplanned: TerrainActionButton",
    "Command + JobState", "command accepted / completed",
    "Label swaps to spinner without width shift", "140 ms", "enter", "busy",
    "E-M1 + PD-M2", "PD-J2: preserve button geometry in every label state."),
  item("A03", "Atom", "Global", "Focus ring", "existing", "P0",
    "Qt focus system + host stylesheet",
    "QWidget focus state", "focus in / focus out",
    "Outline appears without moving layout", "90 ms", "standard", "focus",
    "E-M1 + PD-M3", "PD-J3: check every custom-painted control has a visible focus path."),
  item("A04", "Atom", "Global", "Workspace tab indicator", "planned", "P0",
    "planned: host/terrain/main_window.py::WorkspaceTabs",
    "ProjectSession.selection.workspace", "workspace selection",
    "Indicator preserves horizontal direction", "220 ms", "spatial", "tabs",
    "PD-M1 + MD-M1", "PD-J1: tabs must not resemble completed wizard steps."),
  item("A05", "Atom", "Global", "Toggle thumb", "adapt", "P1",
    "pair_review.py::beat_sync_check / quantize_check",
    "Session setting", "boolean value change",
    "Thumb position and role color", "140 ms", "standard", "toggle",
    "E-M1 + MD-M1", "E-J1: verify state remains readable without color."),
  item("A06", "Atom", "Global", "Status dot", "adapt", "P0",
    "simple_mode.py::_set_engine_status\nplanned: ProjectSession.jobs",
    "Session / JobState", "state change",
    "Color crossfade; breathing only while running", "140 ms", "standard", "status",
    "PD-M2 + MD-M1", "PD-J2: idle and complete must never pulse."),
  item("A07", "Atom", "Library", "Determinate progress", "existing", "P0",
    "simple_mode.py::_AnalysisThread.progress",
    "Real completed / total callbacks", "progress callback",
    "Fill interpolates only to reported value", "220 ms", "standard", "progress",
    "E-M3 + MD-M1", "E-J3: test monotonic updates and completion at exactly 100%."),
  item("A08", "Atom", "Library", "Indeterminate progress", "existing", "P0",
    "simple_mode.py::_AnalysisThread.stage",
    "Real running stage without measurable fraction", "stage entered / exited",
    "Single quiet loop; removed immediately on terminal state", "1200 ms loop", "standard", "indeterminate",
    "E-M3 + MD-M1", "E-J3: do not display a fabricated percentage."),
  item("A09", "Atom", "Global", "Selection ring", "adapt", "P0",
    "energy_timeline.py::select_track\nmixability_map.py::set_selected_track",
    "Stable selected track/seam ID", "selection change",
    "One local emphasis, then static selected state", "140 ms", "enter", "selection",
    "PD-M1 + MD-M1", "PD-J1: verify the same identity remains selected across workspaces."),
  item("A10", "Atom", "Global", "Tooltip", "existing", "P1",
    "Qt QWidget.setToolTip + planned Terrain help layer",
    "Hover / focus", "delay elapsed",
    "8 px rise and fade", "140 ms", "enter", "tooltip",
    "PD-M3 + MD-M1", "PD-J3: tooltip copy must explain action, not repeat the label."),
  item("A11", "Atom", "Global", "Disclosure chevron", "planned", "P1",
    "planned: host/terrain/components.py::Disclosure",
    "Expanded state", "expand / collapse",
    "Quarter rotation with reversible state", "140 ms", "standard", "disclosure",
    "PD-M2 + MD-M1", "PD-J2: expansion cannot change unrelated panel positions."),
  item("A12", "Atom", "Seam", "Cue marker", "adapt", "P0",
    "pair_review.py::StructureStrip\nplanned: CueDecisionStore",
    "Cue draft / final decision", "drag / restore / update",
    "Direct tracking while dragged; committed marker remains exact", "frame bound", "linear", "cue",
    "E-M2 + MD-M2", "E-J2: compare marker time with stored seconds and beat index."),
  item("A13", "Atom", "Seam", "Cue snap", "existing", "P0",
    "pair_review.py::StructureStrip._quantize_time",
    "Reliable beatgrid + quantizer result", "drag release",
    "Damped snap to valid 8-beat target", "220 ms", "snap", "snap",
    "E-M2 + MD-M1", "MD-J2: overshoot may be visual only and cannot alter final time."),
  item("A14", "Atom", "Seam", "Transition region handle", "existing", "P0",
    "pair_review.py::StructureStrip mouse handlers",
    "Pointer position bounded by source duration", "drag",
    "No easing during drag; fill follows both handles", "frame bound", "linear", "region",
    "E-M1 + MD-M1", "E-J1: test crossing prevention and minimum region width."),
  item("A15", "Atom", "Seam", "Playhead", "existing", "P0",
    "StructureStrip.set_playhead\nTransitionSimulationView.set_playhead_fraction",
    "QMediaPlayer.position", "play / seek / pause",
    "Linear motion on one time domain", "33 ms current tick", "linear", "playhead",
    "E-M2 + MD-M2", "MD-J2: pause must freeze every dependent surface in one frame."),
  item("A16", "Atom", "Automix", "8-beat phase tick", "planned", "P0",
    "pair_review.py::_beat_index\nplanned: AutomixTransportFrame",
    "Reliable beatgrid + transport", "beat boundary crossed",
    "Exactly one of eight ticks active", "transport frame", "steps(8)", "beat",
    "E-M2 + MD-M2", "MD-J2: unreliable grid must switch to manual state, not guess."),
  item("A17", "Atom", "Automix", "EQ knob value", "existing", "P0",
    "pair_review.py::TransitionSimulationView._draw_knob",
    "TransitionEnvelope sample", "transport frame / scrub",
    "Deterministic arc rotation", "33 ms current tick", "linear", "knob",
    "E-M2 + MD-M2", "E-J2: rendered audio and displayed envelope need the same profile revision."),
  item("A18", "Atom", "Automix", "Channel fader", "existing", "P0",
    "pair_review.py::TransitionSimulationView._draw_fader_panel",
    "TransitionEnvelope fader_a / fader_b", "transport frame / scrub",
    "Deterministic linear position", "33 ms current tick", "linear", "fader",
    "E-M2 + MD-M2", "MD-J2: no independent animation timer."),
  item("A19", "Atom", "Automix", "Crossfader", "planned", "P0",
    "planned: host/terrain/automix.py::CrossfaderView",
    "Transition profile when crossfader is used", "transport frame / scrub",
    "Position follows the committed profile", "transport frame", "linear", "crossfader",
    "E-M2 + MD-M2", "PD-J1: hide the control when the selected strategy does not use it."),
  item("A20", "Atom", "Automix", "Level meter", "deferred", "P1",
    "planned after real RMS/peak tap",
    "Measured audio level", "audio meter callback",
    "Fast attack, slower release; never synthetic", "audio callback", "attack/release", "meter",
    "E-M2 + MD-M2", "E-J2: blocker until a real level source exists."),
  item("A21", "Atom", "Export", "Warning badge", "planned", "P0",
    "planned: export_manifest.py + export_gate.py",
    "Manifest blocker / warning", "issue appears / resolves",
    "Fade and one local nudge; then static", "140 ms", "enter", "warning",
    "PD-M3 + MD-M1", "PD-J3: severity must be carried by label and icon, not color alone."),
  item("A22", "Atom", "Global", "Saved state", "adapt", "P0",
    "simple_mode.py::_mark_project_saved / _write_autosave",
    "Persistence callback", "dirty / saving / saved / failed",
    "Text crossfade without moving Project Bar", "140 ms", "standard", "save",
    "E-M3 + PD-M3", "E-J3: never show Saved before the write callback returns."),
  item("A23", "Atom", "Library", "Drag ghost", "planned", "P0",
    "planned: host/terrain/library_workspace.py",
    "Drag payload with stable track/source IDs", "drag start / end",
    "Opacity and elevation only", "140 ms", "enter", "drag",
    "E-M1 + MD-M1", "E-J1: ghost must not be mistaken for an imported track."),
  item("A24", "Atom", "Library", "Drop target", "planned", "P0",
    "planned: host/terrain/library_workspace.py::ImportDropZone",
    "Compatible file/folder payload", "drag enter / leave / drop",
    "Outline and fill interpolate; no auto-import before drop", "140 ms", "standard", "drop",
    "PD-M1 + MD-M1", "PD-J1: distinguish files, folders and Rekordbox sources."),
  item("A25", "Atom", "Track", "Zoom scale label", "existing", "P1",
    "pair_review.py::StructureStrip.zoom_at / wheelEvent / NativeGesture",
    "Waveform viewport scale", "wheel / pinch / fit",
    "Value crossfade; waveform remains anchored at pointer", "140 ms", "standard", "zoom",
    "E-M1 + MD-M1", "E-J1: verify touchpad direction and pointer anchor."),

  item("MOL01", "Molecule", "Library", "Track row selection", "adapt", "P0",
    "analyzed_library.py::AnalyzedLibraryWidget",
    "ProjectSession.selection.track_id", "row selected",
    "Highlight and actions enter without row movement", "140 ms", "enter", "track-row",
    "PD-M1 + E-M1", "PD-J1: selected title must match TRACK header and source path."),
  item("MOL02", "Molecule", "Library", "Track row insertion", "planned", "P1",
    "planned: library_workspace.py + library model",
    "Library revision", "accepted import committed",
    "Visible row reveals height and opacity; max eight staggered", "220 ms + 24 ms", "enter", "insert",
    "E-M1 + MD-M1", "E-J1: large folders must not animate every row."),
  item("MOL03", "Molecule", "Library", "Track analysis state", "adapt", "P0",
    "_AnalysisThread.stage/progress/track_done",
    "queued / stage / ready / warning / failed", "analysis callback",
    "Status, label and progress transition atomically", "220 ms", "standard", "analysis",
    "E-M3 + PD-M2", "E-J3: terminal states cancel all running loops."),
  item("MOL04", "Molecule", "Library", "Must Have action", "existing", "P0",
    "analyzed_library.py::must_have_requested\nsimple_mode.py::toggle_must_have",
    "Session constraint", "Pin command committed",
    "Badge appears in row and terrain dock", "140 ms", "enter", "pin",
    "PD-M1 + E-M1", "PD-J2: confirm one command updates every view."),
  item("MOL05", "Molecule", "Library", "Rest Tonight action", "existing", "P0",
    "analyzed_library.py::not_tonight_requested\nsimple_mode.py::toggle_not_tonight",
    "Session exclusion constraint", "Rest command committed",
    "Row desaturates but remains discoverable", "140 ms", "standard", "rest",
    "PD-M1 + MD-M1", "PD-J1: exclusion must not look like file deletion."),
  item("MOL06", "Molecule", "Library", "Filter result update", "existing", "P1",
    "analyzed_library.py::filter_library_rows / refresh",
    "Filter model result", "filter value changed",
    "Count crossfades; table updates without mass animation", "140 ms", "standard", "filter",
    "E-M1 + PD-M2", "E-J1: preserve selected track if it remains in results."),
  item("MOL07", "Molecule", "Library", "Import drop zone", "planned", "P0",
    "import_dialogs.py + planned ImportDropZone",
    "Validated source payload", "drop / picker result",
    "Drop feedback hands off to queued track rows", "220 ms", "spatial", "import",
    "PD-M1 + E-M1", "PD-J1: suspicious duration review happens before analysis starts."),
  item("MOL08", "Molecule", "Global", "Job item", "adapt", "P0",
    "_AnalysisThread signals\nplanned: host/terrain/jobs.py::JobRecord",
    "Job type, stage, progress, ETA, stop request", "job lifecycle",
    "Real progress and calm terminal transition", "220 ms", "standard", "job",
    "E-M3 + MD-M1", "E-J3: Stop after current cannot discard completed results."),
  item("MOL09", "Molecule", "Set", "Track card in terrain", "adapt", "P0",
    "energy_timeline.py::SetEnergyPoint / EnergyTimelineCanvas",
    "Plan revision + selection + constraints", "plan or selection update",
    "Card reveal, selection and constraint badges", "420 ms max", "spatial", "terrain-track",
    "PD-M2 + MD-M3", "PD-J2: energy height must represent real relative library energy."),
  item("MOL10", "Molecule", "Set", "Seam joint", "adapt", "P0",
    "energy_timeline.py::transition_score_to_next\nSetTransition",
    "Pair IDs + score + warnings + verdict", "selection / verdict update",
    "Joint expands locally and preserves pair identity", "220 ms", "spatial", "seam",
    "PD-M1 + MD-M1", "PD-J1: opening SEAM must display the exact A/B pair."),
  item("MOL11", "Molecule", "Set", "Candidate result", "existing", "P1",
    "mixability_map.py::_MixabilityRankingThread / MixabilityMapWidget",
    "Ranked candidate result", "ranking completed",
    "Visible results reveal once; selection remains static", "220 ms + 24 ms", "enter", "candidate",
    "E-M3 + PD-M1", "E-J3: failure keeps the previous valid ranking clearly marked stale."),
  item("MOL12", "Molecule", "Seam", "Cue control", "adapt", "P0",
    "StructureStrip.cueMoved / Deck._on_cue_moved\nplanned: CueDecisionStore",
    "Cue provenance, draft/final, grid state", "drag / commit / undo",
    "Marker, label and commit status change as one unit", "frame + 220 ms snap", "snap", "cue-control",
    "E-M2 + MD-M2", "E-J2: user correction must survive save/reopen and reach manifest."),
  item("MOL13", "Molecule", "Seam", "Transition region", "existing", "P0",
    "StructureStrip.selectionCommitted / _paint_region",
    "Start/end seconds and beat indices", "resize / restore",
    "Handles and fill track live; duration updates in place", "frame bound", "linear", "transition-region",
    "E-M2 + MD-M2", "MD-J2: bounds must map to the same transition test record."),
  item("MOL14", "Molecule", "Automix", "Transport control", "adapt", "P0",
    "TransitionReviewWidget preview player + QMediaPlayer",
    "Playback state and media position", "play / pause / seek / stop",
    "Button, time, playhead and dependent controls update atomically", "transport frame", "linear", "transport",
    "E-M2 + MD-M2", "E-J2: rapid play-pause-seek cannot split UI states."),
  item("MOL15", "Molecule", "Automix", "EQ band control", "existing", "P0",
    "TransitionSimulationView.current_mixer_values / _draw_knob",
    "One TransitionEnvelope curve", "transport frame / scrub",
    "Knob arc and value follow the same sample", "33 ms current tick", "linear", "eq",
    "E-M2 + MD-M2", "MD-J2: compare curve knot and knob value frame-by-frame."),
  item("MOL16", "Molecule", "Automix", "Mixer channel", "adapt", "P0",
    "TransitionSimulationView EQ + fader panels",
    "Three EQ curves + channel fader + optional meter", "transport frame",
    "One batched repaint per channel", "33 ms current tick", "linear", "mixer",
    "E-M2 + MD-M2", "E-J2: no per-control timer or DSP in paintEvent."),
  item("MOL17", "Molecule", "Automix", "Transition moment", "planned", "P0",
    "TransitionEnvelope beat_positions + planned semantic markers",
    "Cue-in / bass swap / handover / cue-out", "transport crosses marker",
    "One local state highlight, no flashing", "140 ms", "enter", "moment",
    "PD-M1 + MD-M2", "PD-J1: labels must be understandable without chart legend."),
  item("MOL18", "Molecule", "Seam", "Verdict action row", "planned", "P0",
    "planned: ProjectSession.record_seam_verdict",
    "Keep / Strategy / Skip / Needs listen", "user decision committed",
    "Selection moves and confirms save", "140 ms", "standard", "verdict",
    "PD-M1 + E-M1", "PD-J3: verdict is separate from blind R&D rating."),
  item("MOL19", "Molecule", "Export", "Export issue row", "planned", "P0",
    "planned: ExportManifest blocker/warning + deep link",
    "Manifest issue with target track/seam ID", "Gate built / issue resolved",
    "Severity enters once; deep link preserves issue context", "140 ms", "enter", "issue",
    "PD-M3 + E-M3", "E-J3: Gate and writer must use the exact same manifest revision."),
  item("MOL20", "Molecule", "Global", "Toast", "planned", "P1",
    "planned: host/terrain/notifications.py",
    "Non-blocking completed/recovery event", "event emitted",
    "Enter, readable hold, exit; never covers critical transport", "320 ms", "spatial", "toast",
    "PD-M3 + MD-M1", "PD-J3: errors requiring action belong in context, not transient toast."),

  item("O01", "Organism", "Global", "Project Bar", "adapt", "P0",
    "simple_mode.py::_build_project_bar\nplanned: terrain/main_window.py",
    "Project identity, save state, global jobs, Gate count", "session update",
    "Local state transitions; bar geometry remains stable", "140-220 ms", "standard", "projectbar",
    "PD-SR + E-SR", "PD-J2: remove Simple Mode and wizard completion language."),
  item("O02", "Organism", "Global", "Workspace Tabs", "planned", "P0",
    "planned: TerrainMainWindow workspace navigation",
    "ProjectSession selection", "LIBRARY / SET / SEAM / TRACK",
    "Indicator plus short content transition", "220 ms", "spatial", "workspaces",
    "PD-SR + MD-SR", "PD-J1: every workspace stays reachable regardless of readiness."),
  item("O03", "Organism", "Global", "Context Inspector", "planned", "P0",
    "planned: terrain/main_window.py::ContextInspector",
    "Selected workspace/track/seam/job", "selection update",
    "Content swaps from current visual position", "220 ms", "enter", "inspector",
    "PD-M1 + MD-M1", "PD-J1: inspector cannot duplicate editable state from workspace."),
  item("O04", "Organism", "Global", "Job Center", "planned", "P0",
    "planned: terrain/jobs.py + JobCenter",
    "Collection of JobRecord", "open / job lifecycle",
    "Status badge expands into a drawer", "220 ms", "spatial", "jobcenter",
    "E-M3 + PD-M1", "E-J3: opening/closing cannot pause background processing."),
  item("O05", "Organism", "Library", "Library Table", "adapt", "P0",
    "analyzed_library.py::AnalyzedLibraryWidget",
    "Library rows, filters, analysis and constraints", "library revision",
    "Only local/visible changes animate", "140-220 ms", "standard", "library",
    "E-M1 + PD-M2", "E-J1: test with 1000 rows and preserve keyboard selection."),
  item("O06", "Organism", "Library", "Import Review Sheet", "adapt", "P0",
    "import_dialogs.py duration preflight",
    "Suspicious <2 min or >10 min sources", "preflight finds exceptions",
    "Modal sheet enters; row decisions update locally", "320 ms", "spatial", "sheet",
    "PD-M1 + PD-M3", "PD-J3: copy explains sample/set risk without blocking valid music."),
  item("O07", "Organism", "Set", "Set Terrain", "adapt", "P0",
    "energy_timeline.py + decision/set_builder.py",
    "Immutable plan revision", "Draw / Regrow result committed",
    "New revision draws left-to-right; old plan remains on failure", "420 ms max", "spatial", "terrain",
    "PD-SR + MD-SR", "PD-J2: no synthetic sinusoid; points are real track energies."),
  item("O08", "Organism", "Set", "Candidate Map", "adapt", "P1",
    "mixability_map.py::MixMapCanvas / MixabilityMapWidget",
    "Analyses + ranking + selected track", "selection / ranking result",
    "Point selection and links reveal, axes stay fixed", "220 ms", "enter", "map",
    "PD-M2 + E-M1", "PD-J1: chart axes and score uncertainty need explicit labels."),
  item("O09", "Organism", "Set", "Terrain Dock", "planned", "P0",
    "planned: terrain/components.py::TerrainDock",
    "Plan revision + selection + seam verdicts", "selection / verdict update",
    "Scroll-to-selection with restrained highlight", "220 ms", "spatial", "dock",
    "PD-M1 + MD-M1", "PD-J1: dock is navigation context, not a second editable set list."),
  item("O10", "Organism", "Track", "Track Inspector", "adapt", "P0",
    "AnalysisResult + pair_review.StructureStrip\nplanned: track_workspace.py",
    "Selected track analysis, cues and session role", "track selection",
    "Identity continuity plus local content reveal", "320 ms", "spatial", "track",
    "PD-M1 + E-M1", "PD-J1: source path and stable track ID remain inspectable."),
  item("O11", "Organism", "Seam", "Seam Workspace", "adapt", "P0",
    "pair_review.py::TransitionReviewWidget",
    "Exact A/B pair from one plan revision", "seam selection",
    "Waveforms, controls and reasons bind to one pair", "320 ms", "spatial", "seamwork",
    "PD-SR + E-M2", "E-J2: reject any duplicated or swapped track identity."),
  item("O12", "Organism", "Automix", "Automix Console", "adapt", "P0",
    "TransitionSimulationView + render_transition_preview",
    "TransportFrame + TransitionRenderResult + TransitionEnvelope", "render / playback lifecycle",
    "One clock drives timeline, mixer and moments", "33 ms current / 60 FPS target", "linear", "automix",
    "E-SR + MD-SR", "MD-J2: log drift and dropped frames during every preview test."),
  item("O13", "Organism", "Export", "Export Gate", "planned", "P0",
    "planned: export_gate.py + export_manifest.py + export/rekordbox.py",
    "Immutable ExportManifest revision", "Gate open / write / result",
    "Focused sheet, blocker deep links and honest write state", "320 ms", "spatial", "gate",
    "E-SR + PD-SR", "E-J3: Will write must exactly equal the final XML writer input."),
  item("O14", "Organism", "Global", "Empty / Error State", "planned", "P1",
    "planned per Terrain workspace",
    "Missing prerequisites or terminal error", "view opens / error emitted",
    "Local reveal with one recovery action", "220 ms", "enter", "empty",
    "PD-M3 + MD-M1", "PD-J3: message answers what is missing and what to click next."),

  item("AM01", "Automix", "Automix", "Master playhead", "adapt", "P0",
    "TransitionSimulationView.set_playhead_fraction",
    "QMediaPlayer.position / duration", "transport frame",
    "One playhead across all Automix layers", "33 ms current", "linear", "playhead",
    "E-M2 + MD-M2", "MD-J2: use as the reference trace for all sync tests."),
  item("AM02", "Automix", "Automix", "Deck A source playhead", "adapt", "P0",
    "TransitionRenderResult.cue_a_sec + playback_rate_a",
    "Master fraction mapped to source A time", "transport frame",
    "Source viewport follows exact outgoing time", "transport frame", "linear", "playhead",
    "E-M2 + MD-M2", "E-J2: compare source time with rendered segment boundaries."),
  item("AM03", "Automix", "Automix", "Deck B source playhead", "adapt", "P0",
    "TransitionRenderResult.cue_b_sec + playback_rate_b",
    "Master fraction mapped to source B time", "transport frame",
    "Incoming viewport includes rate and cue offset", "transport frame", "linear", "playhead",
    "E-M2 + MD-M2", "E-J2: half/double-aware rate must not alter exported BPM."),
  item("AM04", "Automix", "Automix", "Beat phase 1..8", "planned", "P0",
    "preview_timing.py + planned AutomixTransportFrame",
    "Reliable beatgrid and master time", "beat boundary",
    "Eight-step state with phrase anchor", "transport frame", "steps(8)", "beat",
    "E-M2 + MD-M2", "MD-J2: validate seek lands on the same active beat."),
  item("AM05", "Automix", "Automix", "Phrase boundary", "planned", "P0",
    "TransitionEnvelope.grid_beats / beat_positions",
    "Phrase-grid boundary", "boundary crossed",
    "Single restrained local highlight", "140 ms", "enter", "moment",
    "PD-M1 + MD-M2", "PD-J1: boundary cannot be confused with a hot cue."),
  item("AM06", "Automix", "Automix", "Cue-in marker", "adapt", "P0",
    "transition_cues.build_transition_cue + StructureStrip",
    "Incoming cue decision", "preview loaded / crossed",
    "Static marker plus active state on crossing", "140 ms", "enter", "cue",
    "E-M2 + PD-M1", "E-J2: marker time equals final selected cue revision."),
  item("AM07", "Automix", "Automix", "Cue-out marker", "adapt", "P0",
    "transition_cues.build_transition_cue + StructureStrip",
    "Outgoing cue/window decision", "preview loaded / crossed",
    "Static marker plus active state on crossing", "140 ms", "enter", "cue",
    "E-M2 + PD-M1", "E-J2: outgoing guard runway remains visible."),
  item("AM08", "Automix", "Automix", "Transition region playback", "existing", "P0",
    "StructureStrip._paint_region / TransitionSimulationView",
    "Committed transition start/end", "transport frame",
    "Played fill grows under a static region", "transport frame", "linear", "transition-region",
    "E-M2 + MD-M2", "MD-J2: region length and audio duration must agree."),
  item("AM09", "Automix", "Automix", "Deck A EQ envelope", "existing", "P0",
    "TransitionEnvelope low_a/mid_a/high_a",
    "Profile curve sample", "transport frame / scrub",
    "Three deterministic controls and curves", "33 ms current", "linear", "eq",
    "E-M2 + MD-M2", "E-J2: values stay in [0,1] and match render input."),
  item("AM10", "Automix", "Automix", "Deck B EQ envelope", "existing", "P0",
    "TransitionEnvelope low_b/mid_b/high_b",
    "Profile curve sample", "transport frame / scrub",
    "Three deterministic controls and curves", "33 ms current", "linear", "eq",
    "E-M2 + MD-M2", "E-J2: values stay in [0,1] and match render input."),
  item("AM11", "Automix", "Automix", "Bass swap moment", "adapt", "P0",
    "transition_simulation.py::build_transition_envelope('bass_swap')",
    "Low-band handover knot", "profile loaded / crossed",
    "Named moment aligned to low curves", "140 ms", "enter", "moment",
    "PD-M1 + MD-M2", "PD-J1: label must describe the action, not research provenance."),
  item("AM12", "Automix", "Automix", "Tops swap moment", "adapt", "P0",
    "transition_simulation.py::build_transition_envelope('tops_swap')",
    "High/mid handover knots", "profile loaded / crossed",
    "Named moment aligned to upper-band curves", "140 ms", "enter", "moment",
    "PD-M1 + MD-M2", "PD-J1: show whether highs or mids move first."),
  item("AM13", "Automix", "Automix", "Channel faders A/B", "existing", "P0",
    "TransitionEnvelope fader_a/fader_b",
    "Envelope sample", "transport frame / scrub",
    "Both faders update in one repaint", "33 ms current", "linear", "mixer",
    "E-M2 + MD-M2", "MD-J2: frame capture confirms complementary timing."),
  item("AM14", "Automix", "Automix", "Crossfader profile", "planned", "P0",
    "planned explicit crossfader curve in preview schema",
    "Selected transition strategy", "transport frame",
    "Visible only when profile owns a crossfader curve", "transport frame", "linear", "crossfader",
    "E-M2 + PD-M2", "E-J2: do not infer a hidden curve from channel faders."),
  item("AM15", "Automix", "Automix", "Real level meters", "deferred", "P1",
    "blocked: no real RMS/peak UI tap yet",
    "Measured preview output", "audio callback",
    "Attack/release meter after data source exists", "audio callback", "attack/release", "meter",
    "E-M2 + MD-M2", "E-J2: synthetic meter is a release blocker."),
  item("AM16", "Automix", "Automix", "Sync rate display", "existing", "P0",
    "TransitionRenderResult.playback_rate_a/playback_rate_b",
    "Validated preview rate", "pair/profile loaded",
    "Number crossfades; does not animate BPM", "140 ms", "standard", "save",
    "E-M2 + PD-M3", "PD-J3: copy states Preview only and Never exported."),
  item("AM17", "Automix", "Automix", "Quantize correction", "existing", "P0",
    "StructureStrip._quantize_time + quantize_check",
    "Reliable grid gate", "cue release / seek",
    "Damped marker snap; manual state otherwise", "220 ms", "snap", "snap",
    "E-M2 + MD-M1", "MD-J2: quantize interval remains eight beats."),
  item("AM18", "Automix", "Automix", "Profile switch", "adapt", "P0",
    "TransitionReviewWidget._on_profile_changed\nbuild_transition_envelope",
    "New complete TransitionEnvelope", "profile selection",
    "Old curves remain until atomic new envelope swap", "220 ms", "standard", "eq",
    "E-M2 + MD-M2", "E-J2: previous valid preview remains if render fails."),
  item("AM19", "Automix", "Automix", "Duration switch", "adapt", "P0",
    "TransitionReviewWidget._on_duration_changed\nplan_transition_duration",
    "32..256 beat duration plan", "duration selection",
    "Timeline rescales around handover", "320 ms", "spatial", "transition-region",
    "E-M2 + MD-M2", "PD-J1: shortened source-runway result needs an explicit reason."),
  item("AM20", "Automix", "Automix", "Stem source state", "existing", "P1",
    "Deck.render_stems / select_source / _StemWorker",
    "Ready stem source or fallback", "stem ready / selected",
    "Source label and active state crossfade", "140 ms", "standard", "toggle",
    "E-M2 + PD-M2", "E-J2: never imply stem isolation before the file is ready."),
  item("AM21", "Automix", "Automix", "Scrub synchronization", "existing", "P0",
    "TransitionSimulationView.seekRequested\nseek_preview_fraction",
    "Pointer fraction -> media position", "scrub input",
    "All controls update immediately to scrub time", "frame bound", "linear", "transport",
    "E-M2 + MD-M2", "MD-J2: scrub backwards and forwards without lagging controls."),
  item("AM22", "Automix", "Automix", "Planned value hover", "planned", "P2",
    "planned: Automix curve hover inspector",
    "Envelope value at pointer time", "hover / keyboard inspect",
    "Ghost value appears locally without moving controls", "140 ms", "enter", "tooltip",
    "MD-M3 + PD-M3", "PD-J3: keyboard users need the same time/value inspection."),
  item("AM23", "Automix", "Automix", "Render-ready handoff", "adapt", "P0",
    "_TransitionRenderWorker.finished\n_on_transition_rendered",
    "TransitionRenderResult or error", "render terminal state",
    "Progress is atomically replaced by real rendered data", "220 ms", "standard", "analysis",
    "E-M2 + MD-M1", "E-J2: stale worker token cannot replace a newer pair."),
  item("AM24", "Automix", "Automix", "Risk moment marker", "planned", "P1",
    "SetTransition warnings + planned time mapping",
    "Actionable warning with exact pair/time/reason", "preview loaded / marker crossed",
    "One static marker and local detail on selection", "140 ms", "enter", "warning",
    "PD-M3 + MD-M2", "PD-J3: warning without a time mapping stays outside waveform."),
];

const teams = [
  {
    code: "ENGINEERING",
    senior: "Senior Full-Stack / Desktop Architect",
    branches: [
      ["E-M1", "Desktop UI / Qt", "E-J1", "UI Runtime"],
      ["E-M2", "Audio / Realtime", "E-J2", "Playback QA"],
      ["E-M3", "QA / Tooling", "E-J3", "Test Automation"],
    ],
  },
  {
    code: "PRODUCT",
    senior: "Senior Product Designer / System Architect",
    branches: [
      ["PD-M1", "Information Architecture", "PD-J1", "UX Research"],
      ["PD-M2", "Design Systems", "PD-J2", "Component QA"],
      ["PD-M3", "Accessibility / Content", "PD-J3", "Content QA"],
    ],
  },
  {
    code: "MOTION",
    senior: "Senior Motion Designer / Motion System Lead",
    branches: [
      ["MD-M1", "Interaction Motion", "MD-J1", "Microinteraction QA"],
      ["MD-M2", "Audio-Reactive Motion", "MD-J2", "Sync QA"],
      ["MD-M3", "Motion Prototyping", "MD-J3", "Timing QA"],
    ],
  },
];

const timingTokens = [
  ["instant", 90, "press / focus"],
  ["fast", 140, "hover / selection"],
  ["base", 220, "panel / state"],
  ["spatial", 320, "workspace / sheet"],
  ["emphasis", 420, "terrain revision"],
  ["stagger", 24, "visible rows only"],
];

const statusLabels = { existing: "Existing", adapt: "Adapt", planned: "Planned", deferred: "Deferred" };
let rowObserver;

function renderTiming() {
  const root = document.getElementById("timing-stage");
  root.innerHTML = timingTokens.map(([name, ms, use]) => `
    <div class="timing-row run" style="--duration:${ms}ms" role="button" aria-label="Replay ${name}, ${ms} milliseconds">
      <code>${name}</code>
      <div class="timing-track"><i class="timing-dot"></i></div>
      <b>${ms} ms<br>${use}</b>
    </div>`).join("");
  root.addEventListener("click", (event) => {
    const row = event.target.closest(".timing-row");
    if (!row) return;
    row.classList.remove("run");
    void row.offsetWidth;
    row.classList.add("run");
  });
}

function renderTeam() {
  document.getElementById("team-grid").innerHTML = teams.map((team) => `
    <article class="discipline">
      <header><span>${team.code} / SENIOR</span><h3>${team.senior}</h3></header>
      ${team.branches.map(([midCode, mid, juniorCode, junior]) => `
        <div class="team-branch">
          <div class="team-role"><code>${midCode} / MID</code><b>${mid}</b><span>synthesis + delivery</span></div>
          <div class="team-role"><code>${juniorCode} / JUNIOR</code><b>${junior}</b><span>evidence + independent QA</span></div>
        </div>`).join("")}
    </article>`).join("");
}

function waveMarkup(extraClass = "") {
  const bars = Array.from({ length: 42 }, (_, index) => {
    const value = 24 + ((index * 37 + index * index * 7) % 68);
    return `<b style="--h:${value}"></b>`;
  }).join("");
  return `<div class="mini-wave ${extraClass}">${bars}<i class="mini-playhead"></i><i class="mini-cue"></i>${extraClass.includes("region") ? '<span class="mini-region"></span>' : ""}</div>`;
}

function terrainMarkup() {
  const levels = [38, 52, 47, 68, 63, 79, 61, 73];
  return `<div class="demo-terrain">${levels.map((level, index) => `<i style="--e:${level};--i:${index}"></i>`).join("")}</div>`;
}

function meterMarkup() {
  return `<div class="demo-meter">${[38, 66, 52, 82, 44, 72].map((value, index) => `<i style="--m:${value};--i:${index}"></i>`).join("")}</div>`;
}

function renderDemo(kind) {
  const demos = {
    button: `<button type="button" class="demo-button">Generate set</button>`,
    busy: `<button type="button" class="demo-button"><span class="demo-spinner"></span></button>`,
    focus: `<div class="demo-focus">Keyboard focus</div>`,
    tabs: `<div class="demo-tabs cycle"><span>LIBRARY</span><span>SET</span><span>SEAM</span><i></i></div>`,
    toggle: `<button type="button" class="demo-toggle on" aria-pressed="true"><i></i></button>`,
    status: `<div class="demo-status running"><i></i><span>Analyzing structure</span></div>`,
    progress: `<div class="demo-progress"><i></i></div>`,
    indeterminate: `<div class="demo-progress indeterminate"><i></i></div>`,
    selection: `<div class="demo-selection">Track 07</div>`,
    tooltip: `<div class="demo-tooltip-wrap"><button type="button">?</button><span class="demo-tooltip">Opens exact A/B seam</span></div>`,
    disclosure: `<span class="demo-chevron">›</span>`,
    cue: waveMarkup(),
    snap: waveMarkup("snap"),
    region: waveMarkup("region"),
    playhead: waveMarkup(),
    beat: `<div class="demo-beats">${Array.from({length:8}, (_, i) => `<i style="--i:${i}"></i>`).join("")}</div>`,
    knob: `<div class="demo-knob"></div>`,
    fader: `<div class="demo-fader"><i></i></div>`,
    crossfader: `<div class="demo-cross"><i></i></div>`,
    meter: meterMarkup(),
    warning: `<div class="demo-warning">Grid confidence low</div>`,
    save: `<div class="demo-save"><span>Saving... / Saved 14:32</span></div>`,
    drag: `<div class="demo-row selected" style="transform:rotate(-2deg);box-shadow:0 16px 30px rgba(0,0,0,.25)"><b>Mercedes</b><span>132 BPM</span></div>`,
    drop: `<div class="demo-drop">Drop files or folders</div>`,
    zoom: `<div class="demo-zoom">Waveform 128%</div>`,
    "track-row": `<div class="demo-row selected"><b>Rave Cycle</b><span>130 BPM · 6A</span></div>`,
    insert: `<div class="demo-row insert"><b>New analyzed track</b><span>READY</span></div>`,
    analysis: `<div class="demo-stack"><div class="demo-row"><b>Track analysis</b><span>STRUCTURE</span></div><div class="demo-progress"><i></i></div></div>`,
    pin: `<div class="demo-row selected"><b>Glue</b><span class="demo-pin">PINNED</span></div>`,
    rest: `<div class="demo-row" style="opacity:.5"><b>Peak</b><span>REST TONIGHT</span></div>`,
    filter: `<div class="demo-stack"><div class="demo-row"><b>UK Bass</b><span>24 tracks</span></div><div class="demo-row"><b>Breaks</b><span>18 tracks</span></div></div>`,
    import: `<div class="demo-drop">+ 12 compatible tracks</div>`,
    job: `<div class="demo-stack"><div class="demo-row"><b>Deep analysis</b><span>8 / 12</span></div><div class="demo-progress"><i></i></div></div>`,
    "terrain-track": terrainMarkup(),
    seam: `<div class="demo-seam"><b></b><i></i><b></b></div>`,
    candidate: `<div class="demo-candidate">${Array.from({length:4}, (_, i) => `<i style="--i:${i}"></i>`).join("")}</div>`,
    "cue-control": waveMarkup("snap"),
    "transition-region": waveMarkup("region"),
    transport: `<div class="demo-stack">${waveMarkup()}<button type="button" class="demo-button">Pause</button></div>`,
    eq: `<div style="display:flex;gap:18px"><div class="demo-knob" style="color:var(--amber)"></div><div class="demo-knob"></div></div>`,
    mixer: `<div style="display:flex;gap:38px;align-items:center"><div class="demo-fader"><i></i></div><div class="demo-cross"><i></i></div><div class="demo-fader"><i></i></div></div>`,
    moment: `<div class="demo-warning" style="color:var(--volt);border-color:rgba(217,255,67,.35)">BASS SWAP · BEAT 32</div>`,
    verdict: `<div class="demo-verdict"><button class="active">KEEP</button><button>STRATEGY</button><button>SKIP</button></div>`,
    issue: `<div class="demo-row"><b>2 cue conflicts</b><span style="color:var(--red)">OPEN SEAM</span></div>`,
    toast: `<div class="demo-toast">12 new candidates ready</div>`,
    projectbar: `<div class="demo-panel"><header><b>Friday Courtyard</b><span style="color:var(--green)">Saved 14:32</span></header><p>240 tracks · 12-track plan · 1 job running</p></div>`,
    workspaces: `<div class="demo-tabs cycle"><span>LIBRARY</span><span>SET</span><span>SEAM</span><i></i></div>`,
    inspector: `<div class="demo-panel"><header><b>SEAM / 04</b><span>0.82</span></header><p>Balanced blend · 64 beats · reliable grid</p></div>`,
    jobcenter: `<div class="demo-panel"><header><b>JOB CENTER</b><span style="color:var(--cyan)">RUNNING</span></header><div class="demo-progress" style="width:100%;margin-top:18px"><i></i></div></div>`,
    library: `<div class="demo-stack"><div class="demo-row selected"><b>Glue</b><span>130 · 9A</span></div><div class="demo-row"><b>Lockup</b><span>130 · 12A</span></div><div class="demo-row"><b>Rave Cycle</b><span>130 · 6A</span></div></div>`,
    sheet: `<div class="demo-gate"><b>Review 3 unusual durations</b><span>Accept tracks shorter than 2 min or longer than 10 min?</span></div>`,
    terrain: terrainMarkup(),
    map: `<div class="demo-candidate">${Array.from({length:4}, (_, i) => `<i style="--i:${i}"></i>`).join("")}</div>`,
    dock: `<div class="demo-seam"><b></b><i></i><b></b><i style="background:var(--amber)"></i><b></b></div>`,
    track: `<div class="demo-panel"><header><b>GLUE / BICEP</b><span>130 BPM · 9A</span></header>${waveMarkup()}</div>`,
    seamwork: `<div class="demo-stack">${waveMarkup("region")}<div class="demo-verdict"><button class="active">KEEP</button><button>SKIP</button></div></div>`,
    automix: `<div style="display:flex;gap:24px;align-items:center">${waveMarkup("region")}<div class="demo-knob"></div><div class="demo-fader"><i></i></div></div>`,
    gate: `<div class="demo-gate"><b>EXPORT GATE</b><span>12 tracks · 18 hot cues · BPM/grid untouched</span></div>`,
    empty: `<div class="demo-panel"><header><b>No set yet</b><span>EMPTY</span></header><p>Set a brief, then Draw terrain.</p></div>`,
  };
  return demos[kind] || demos.empty;
}

function statusClass(status) { return `status-${status}`; }

function renderRows(data) {
  const root = document.getElementById("component-rows");
  root.innerHTML = data.map((component) => `
    <article class="component-row" role="row" data-id="${component.id}">
      <div class="component-cell" role="cell">
        <div class="component-title"><code class="component-id">${component.id}</code><div><h3>${component.name}</h3><span class="contract-state">${component.level} / ${component.workspace}</span></div></div>
        <div class="component-tags"><span class="tag ${statusClass(component.status)}">${statusLabels[component.status]}</span><span class="tag">${component.priority}</span><span class="tag">${component.workspace}</span></div>
      </div>
      <div class="component-cell" role="cell">
        <code class="code-path">${component.code.replaceAll("\n", "<br>")}</code>
        <p class="contract-state"><b>Source of truth:</b> ${component.source}</p>
      </div>
      <div class="component-cell" role="cell">
        <div class="motion-copy"><b>${component.trigger}</b><br>${component.motion}</div>
        <div class="motion-spec"><div><span>Timing</span><b>${component.timing}</b></div><div><span>Easing</span><b>${component.easing}</b></div><div><span>Owner</span><b>${component.owner}</b></div><div><span>Reduced</span><b>required</b></div></div>
        <div class="review-stamps" aria-label="Zakres mapowania dyscyplin"><span>ENG MAPPED</span><span>PRODUCT MAPPED</span><span>MOTION MAPPED</span></div>
        <div class="review-mini"><b>Junior voice:</b> ${component.junior}</div>
      </div>
      <div class="component-cell specimen-cell" role="cell">
        <div class="specimen auto" data-demo="${component.demo}">${renderDemo(component.demo)}</div>
        <button class="replay-button" type="button">Replay specimen</button>
      </div>
    </article>`).join("");

  document.getElementById("visible-count").textContent = `${data.length} components`;
  document.getElementById("empty-results").hidden = data.length !== 0;
  observeVisibleRows();
}

function observeVisibleRows() {
  if (rowObserver) rowObserver.disconnect();
  const rows = document.querySelectorAll(".component-row");
  if (!("IntersectionObserver" in window)) {
    rows.forEach((row) => row.classList.add("is-in-viewport"));
    return;
  }
  rowObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => entry.target.classList.toggle("is-in-viewport", entry.isIntersecting));
  }, { rootMargin: "240px 0px" });
  rows.forEach((row) => rowObserver.observe(row));
}

function uniqueValues(field) {
  return [...new Set(components.map((entry) => entry[field]))].sort((a, b) => a.localeCompare(b));
}

function populateFilter(id, field) {
  const select = document.getElementById(id);
  select.insertAdjacentHTML("beforeend", uniqueValues(field).map((value) => `<option value="${value}">${value}</option>`).join(""));
}

function filterRows() {
  const query = document.getElementById("component-search").value.trim().toLowerCase();
  const fields = ["level", "workspace", "status", "priority"];
  const selected = fields.map((field) => document.getElementById(`${field}-filter`).value);
  const result = components.filter((component) => {
    const haystack = Object.values(component).join(" ").toLowerCase();
    return (!query || haystack.includes(query)) && fields.every((field, index) => selected[index] === "all" || component[field] === selected[index]);
  });
  renderRows(result);
}

function bindComponentControls() {
  ["level", "workspace", "status", "priority"].forEach((field) => populateFilter(`${field}-filter`, field));
  document.getElementById("component-search").addEventListener("input", filterRows);
  ["level", "workspace", "status", "priority"].forEach((field) => document.getElementById(`${field}-filter`).addEventListener("change", filterRows));
  document.getElementById("speed-control").addEventListener("change", (event) => {
    document.documentElement.style.setProperty("--time-scale", event.target.value);
  });
  document.getElementById("pause-motion").addEventListener("click", (event) => {
    const active = document.body.classList.toggle("motion-paused");
    event.currentTarget.setAttribute("aria-pressed", String(active));
    event.currentTarget.textContent = active ? "Resume demos" : "Pause demos";
  });
  document.getElementById("reduce-motion").addEventListener("click", (event) => {
    const active = document.body.classList.toggle("reduced-motion");
    event.currentTarget.setAttribute("aria-pressed", String(active));
  });
  document.getElementById("component-rows").addEventListener("click", (event) => {
    const replay = event.target.closest(".replay-button");
    if (replay) {
      const specimen = replay.parentElement.querySelector(".specimen");
      specimen.classList.remove("auto");
      specimen.innerHTML = renderDemo(specimen.dataset.demo);
      void specimen.offsetWidth;
      specimen.classList.add("auto");
      return;
    }
    const toggle = event.target.closest(".demo-toggle");
    if (toggle) {
      const active = toggle.classList.toggle("on");
      toggle.setAttribute("aria-pressed", String(active));
    }
    const verdict = event.target.closest(".demo-verdict button");
    if (verdict) {
      verdict.parentElement.querySelectorAll("button").forEach((button) => button.classList.remove("active"));
      verdict.classList.add("active");
    }
  });
}

function initializeAutomix() {
  document.querySelectorAll(".wave-bars").forEach((lane, laneIndex) => {
    lane.innerHTML = Array.from({ length: 112 }, (_, index) => {
      const base = 22 + ((index * (laneIndex ? 29 : 41) + index * index * 3) % 72);
      const shape = laneIndex === 0 ? 1 - index / 180 : .5 + index / 230;
      return `<i style="--amp:${Math.max(12, Math.min(96, base * shape))}"></i>`;
    }).join("");
  });
  document.getElementById("beat-phase").innerHTML = Array.from({ length: 8 }, () => "<i></i>").join("");
  document.querySelectorAll(".knob-row").forEach((row) => {
    row.innerHTML = ["HIGH", "MID", "LOW"].map((label) => `<div class="knob-control"><div class="knob" data-band="${label.toLowerCase()}"></div><span>${label}</span></div>`).join("");
  });

  const lab = document.getElementById("automix-lab");
  const scrub = document.getElementById("automix-scrub");
  const play = document.getElementById("automix-play");
  const profile = document.getElementById("automix-profile");
  let progress = 0;
  let playing = true;
  let previous = performance.now();

  function smoothstep(edge0, edge1, value) {
    const x = Math.max(0, Math.min(1, (value - edge0) / Math.max(edge1 - edge0, .0001)));
    return x * x * (3 - 2 * x);
  }

  function valuesAt(p) {
    const selected = profile.value;
    const fadeB = Math.sin(p * Math.PI / 2);
    const fadeA = Math.cos(p * Math.PI / 2);
    if (selected === "bass") {
      return {
        a: { high: 1 - .88 * smoothstep(.38, 1, p), mid: 1 - .9 * smoothstep(.3, .96, p), low: 1 - .97 * smoothstep(.43, .56, p), fader: fadeA },
        b: { high: .14 + .86 * smoothstep(.03, .54, p), mid: .08 + .92 * smoothstep(.16, .72, p), low: .03 + .97 * smoothstep(.46, .57, p), fader: fadeB },
      };
    }
    if (selected === "tops") {
      return {
        a: { high: 1 - .98 * smoothstep(.14, .34, p), mid: 1 - .9 * smoothstep(.34, .8, p), low: 1 - .98 * smoothstep(.58, .88, p), fader: fadeA },
        b: { high: .05 + .95 * smoothstep(.1, .3, p), mid: .05 + .95 * smoothstep(.24, .72, p), low: .02 + .98 * smoothstep(.54, .82, p), fader: fadeB },
      };
    }
    return {
      a: { high: 1, mid: 1, low: 1, fader: fadeA },
      b: { high: 1, mid: 1, low: 1, fader: fadeB },
    };
  }

  function render(progressValue) {
    const p = Math.max(0, Math.min(1, progressValue));
    lab.style.setProperty("--playhead", p);
    scrub.value = String(Math.round(p * 1000));
    document.getElementById("automix-time").textContent = `00:${String((p * 30).toFixed(1)).padStart(4, "0")}`;
    const beat = Math.min(7, Math.floor((p * 64) % 8));
    document.querySelectorAll("#beat-phase i").forEach((tick, index) => tick.classList.toggle("active", index === beat));
    const values = valuesAt(p);
    ["a", "b"].forEach((channel) => {
      Object.entries(values[channel]).forEach(([band, value]) => {
        const knob = document.querySelector(`.channel-${channel} .knob[data-band="${band}"]`);
        if (knob) knob.style.setProperty("--knob", value);
      });
      document.querySelector(`.channel-${channel} .channel-fader`).style.setProperty("--fader", values[channel].fader);
    });
    document.querySelector(".crossfader").style.setProperty("--cross", p);
  }

  function frame(now) {
    const delta = Math.min(100, now - previous);
    previous = now;
    if (playing && !document.body.classList.contains("motion-paused")) {
      progress += delta / 8000;
      if (progress >= 1) progress = 0;
      render(progress);
    }
    requestAnimationFrame(frame);
  }

  play.addEventListener("click", () => {
    playing = !playing;
    play.textContent = playing ? "Pause transition" : "Play transition";
  });
  scrub.addEventListener("input", () => {
    progress = Number(scrub.value) / 1000;
    render(progress);
  });
  profile.addEventListener("change", () => render(progress));
  play.textContent = "Pause transition";
  render(0);
  requestAnimationFrame(frame);
}

function initialize() {
  renderTiming();
  renderTeam();
  renderRows(components);
  bindComponentControls();
  initializeAutomix();
  document.getElementById("component-count").textContent = components.length;
  document.getElementById("existing-count").textContent = components.filter((entry) => entry.status === "existing" || entry.status === "adapt").length;
  document.getElementById("automix-count").textContent = components.filter((entry) => entry.level === "Automix").length;
}

initialize();
