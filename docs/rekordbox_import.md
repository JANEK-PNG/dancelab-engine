# Importing a DanceLab set into Rekordbox

DanceLab exports a `rekordbox.xml` (`DJ_PLAYLISTS` format) carrying, per track:
BPM + beatgrid (TEMPO) + key (Tonality, Camelot) + HOT CUEs at the engine's mix
points, plus a playlist in the set order.

## Honest expectations (researched)

Rekordbox's XML is a **one-way bridge into a separate "rekordbox xml" view**, not
a direct merge. What transfers: playlists + order, cue points, BPM, key,
beatgrid (conditionally). What does NOT: MyTags, active loops, memory-cue
colours, phrase lanes (CHORUS/UP/DOWN — that is Rekordbox's own analysis, not in
the XML). **No re-analysis is conditional** — you must tell Rekordbox not to
overwrite the imported grid.

## Steps

1. **Point Rekordbox at the file**
   Preferences → Advanced → Database → *rekordbox xml* → set "Imported Library"
   to the exported `dancelab_set.xml`.

2. **Show the bridge view**
   View / Layout → enable **rekordbox xml**. Your DanceLab playlist appears
   under that pane.

3. **Stop Rekordbox re-analyzing the grid**
   Preferences → Analysis → set Track Analysis so BPM/**Beatgrid** is NOT
   re-computed (uncheck Beatgrid; you may leave Phrase on). Otherwise Rekordbox
   decodes with its own codec and can drift the grid.

4. **Import into your collection**
   In the rekordbox-xml view, **right-click the playlist AND the individual
   tracks** → Import to Collection. (Known Rekordbox 5/6/7 quirk: importing only
   the playlist does not pull the tracks — you must right-click the tracks too.)

5. **Verify**
   Check BPM, key, hot cues (A–H) and beatgrid on a couple of tracks.

## Notes

- Keep the XML in a **local, non-cloud, non-external-drive** folder — cloud/USB
  paths break cue import.
- Camelot keys go into the `Tonality` field; low-confidence keys are omitted
  rather than faked.
- Alternative (not used here): `pyrekordbox` can write straight into the
  Rekordbox 6/7 `master.db`, bypassing the bridge — more powerful but unofficial,
  encrypted, and fragile across Rekordbox updates.
