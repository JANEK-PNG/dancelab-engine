# DanceLab preparation workflow — product brief v0.1

Status: audience confirmed by the owner on 2026-09-06; workflow and interface
hypotheses await observed user trials. This brief starts workstream UX.

## Audience and promise

Primary audience: DJs preparing sets from their own music library. The owner
explicitly selected this direction over beginner tuition or live performance.
Rekordbox is the existing export integration, not a requirement to understand
the first screen or a source of fabricated audio measurements.

Promise: prepare a set you understand, retain control of its order, and return
to your work safely. User knowledge of their tracks matters; the application
supports selection and comparison without claiming to predict a crowd.

## First useful outcome

A new user can bring in a library, identify unavailable material, assemble a
set, inspect it, save it, and understand what will be exported. A returning user
resumes the saved order and settings without repeating onboarding. The local
application has no account login; first use means a clean application profile.

The core journey is library → set → review → export. Editing is always allowed
before export. Optional suggestions show their reason, evidence and missing
information; the user can continue arranging tracks manually.

## Shared vocabulary

| Polish UI term | Meaning | Boundary |
| --- | --- | --- |
| Biblioteka | The user's available tracks and their metadata | Missing audio remains visible |
| Set | An ordered working selection | Adding a track does not silently make it mandatory |
| Dodaj do setu | Insert a track into the working order | No hidden change to generation constraints |
| Filar | A track explicitly marked as required in generated suggestions | Separate toggle with an explanation |
| Propozycja | A candidate offered by the engine | Includes why, uncertainty and provenance |
| Przejście | The relation between two adjacent tracks | No assertion of quality from MIDI effort alone |
| Odsłuch | Listen to available source audio or a declared preview | Never a promise of a live DJ playback engine |
| Zapisz set | Preserve the working state for later | Different from publishing to Rekordbox |
| Eksport | Review and write the chosen output | State destination and any omitted tracks |

The prototype demonstrates the proposed separation of “add” and “anchor”. The
production GUI still uses its existing behaviour until that migration is tested.

## First use and return

First use: one primary entry action; explain that files stay local. During
import show progress and a final report of accepted, rejected and unavailable
tracks. Missing BPM/key is unknown, not zero. The library is useful before all
optional analysis completes. A saved set must be recoverable after restart.

Return: lead with the last saved set, its timestamp and explicit resume action.
Offer access to the library and other sets. Keep import onboarding out of this
path. Missing files, incomplete prior settings and failed saves remain visible.

## Validation protocol

Observe 3–5 DJs preparing sets from their own libraries. This is a proposed
qualitative study, not completed research. Use a clean test profile and a safe
copy of any data used in the trial. Ask the participant to add tracks, mark one
required track, change order, save, restart and resume, then explain the export.

Record completion, interventions, time to first saved set, mistaken actions,
save/restore failures and the participant's explanation of “filar”. Establish
the current UI baseline before claiming an improvement. A blocker is any lost
work, misleading success message, hidden import rejection or unexpected write.

## Prototype scope

Open [the interactive prototype](ux/index.html). Its persistent banner marks
all music and examples as demo data. It offers a sample import, search, manual
ordering, explicit anchors, removal/undo, local prototype save, return and a
downloadable demo JSON sketch. It neither analyses music nor writes Rekordbox.
Playback is explicitly unavailable because the sample rows contain no audio.

The next integration increment replaces the demo adapter with tested Engine
operations. UI acceptance and hardware/audio validation remain separate gates.
