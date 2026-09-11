# Desktop observations — 2026-09-06

Surface: the running Python 3.12 application, native window titled DanceLab.
Content: `src/dancelab/gui/statyczne/index.html` in WKWebView. This is the
production GUI, not the Stage A browser prototype. The owner had explicitly
requested this desktop surface in the preceding conversation.

Observed without playback, source-library changes, generation or export:

1. Track view displayed v0.1.1, a populated waveform, BPM 123.0, key 9A,
   duration 10:25, library count 8260, and a closed-Rekordbox status.
2. Navigation offered Utwór, Set 6 and DJ. The library appeared in the right
   column; the waveform occupied most of the workspace.
3. Opening Set showed six selected pillars out of a maximum ten. Pillar mode
   was podpory. The actual set section remained empty and asked for generation.
   This confirms that the six-item navigation badge is not a saved working order.
4. Build summary showed 90 min, MIX, tempo from the library. Expanded settings
   exposed source pool, duration, tempo, sound reference, seed, genres, arc,
   tempo plan, scoring, freshness and contour.
5. Plany and Zapisz plan appeared inside those expanded settings, alongside the
   plan-name field. Save/resume is therefore not a primary visible destination
   in this observed collapsed state.
6. Playback controls were disabled on the empty Set view. No audio was started.
7. Settings were collapsed and the application returned to Utwór after reading.

Screenshots and accessibility output were inspected through native computer-use
tools in this conversation. No screenshot containing the owner's track names
was copied into this planning folder. The attached TUI screenshot supplied by
the owner and TUI source inspection support the TUI mapping; a fresh TUI
end-to-end task run was not performed here.

This is expert observation of current behaviour, not a usability study. No
participant task times, preference scores or performance improvements are claimed.
