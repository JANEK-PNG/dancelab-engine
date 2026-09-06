# Prototype verification — 2026-09-06

Observed in the Codex in-app browser at http://127.0.0.1:8874/, using the visible
interface and screenshots. These are implementation checks, not user research
or measurements of improvement over the production GUI.

- First start showed one sample-library entry action and the persistent demo
  banner. Import produced seven fictional rows, including one unavailable file.
- Unavailable audio could not be added; unknown key appeared as a dash in the
  library and as unknown in the set. No placeholder was presented as a measurement.
- Add, explicit anchor selection, reorder, remove and undo were exercised. Adding
  a track did not implicitly select an anchor.
- The name “Piątek — próba UX”, order Between Rooms / Soft Arrival / Open Window,
  and the Soft Arrival anchor survived save, a real page reload, and resume.
- Export review displayed the working order. The downloaded
  `dancelab-szkic-demo.json` was read from Downloads and verified: schema
  `dancelab.prototype.set.v1`, `demo: true`, order `t2,t1,t5`, anchor `t1`.
  The browser event-wait helper timed out despite the file being downloaded;
  the filesystem artifact, not that event helper, established this result.
- Search with no matches produced a visible empty state while preserving the
  working set. Clearing search restored the full library.
- Screenshots of the first start and working set were inspected at the existing
  desktop viewport. No warning/error console entries were returned by the browser.
- Polish count labels were corrected after observation (e.g. 3 utwory / 1 filar).

Not verified: physical audio, Rekordbox writes, a native webview, mobile/narrow
viewport layouts, screen-reader operation, every keyboard path, browser storage
failure injection, real imports, user comprehension, or measured task completion
with target DJs. The brief defines the next user validation protocol.
