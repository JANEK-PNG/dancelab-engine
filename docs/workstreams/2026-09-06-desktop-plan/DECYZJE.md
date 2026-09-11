# Planning decisions — 2026-09-06

- The owner confirms native desktop delivery. A browser preview is not acceptance
  of the GUI; a repo-bound launcher is not a distributable application.
- Preserve the current WKWebView/Python architecture and TUI. New preparation
  operations are shared services; no framework replacement or training project
  is needed for the first GUI slice.
- Personal-library preparation includes cached streaming metadata. Measured
  source/capability differences must be resolved before playback UX is accepted.
- Adding a manual track and selecting a generation pillar are separate actions.
  Existing generator constraints remain explicit rather than being silently removed.
- Data/profile identity and restore precede production migration. Do not infer
  which existing plan the owner intended from file sort order or a broken pointer.
- A discovered test wrote its synthetic current-plan pointer into personal data.
  Redirect that test write to tmp_path immediately and verify it leaves the
  personal pointer unchanged. Do not guess the overwritten historical value.
- The work package durations are serial engineering estimates, not measured
  throughput or promised dates. Re-estimate after data and save/restore increments.
- This session produces a populated implementation plan, not a new GUI release,
  new user-owned tasks, a runtime data migration, or an off-machine backup.
