# DanceLab interface language — v0.1

Status: prototype specification, not a fully migrated component library.
Audience and task are defined in [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md).

## Foundations

Continue the existing Redakcja direction: warm dark surfaces, amber selection,
blue informational states, an explicit warning colour, and type-led hierarchy.
Reuse the repository's Bricolage Grotesque headings and IBM Plex text/monospace
fonts. The prototype references local copies; it makes no font network requests.

| Token | Value | Use |
| --- | --- | --- |
| background | #1a1917 | Main canvas |
| surface | #22211e | Supporting panels |
| text | #f1efe9 | Main text |
| muted text | #b2afa7 | Secondary labels, raised from the older low-contrast grey |
| accent | #e3a04a | Primary action, selection, keyboard focus |
| information | #a9c5e5 | Explanations and optional guidance |
| warning | #f0b2a3 | Missing files or a failed operation |
| spacing | 4, 8, 12, 16, 24, 32, 48 px | Consistent rhythm |
| body / table | 15 / 14 px | Reading and comparison |

## Components and behaviour

- Navigation: Library and Sets are task destinations. The active destination
  has text and an underline; optional tools do not compete with the main flow.
- Track row: title/artist left; BPM/key as comparable metadata; missing values
  displayed as “—”; unavailable audio carries a written reason. Row controls
  have labels independent of colour and icons.
- Set row: position, track, optional anchor, move up/down and remove. Undo is
  visible after removal. A saved state is distinct from an unsaved edit.
- Primary button: one principal action per state. Disabled controls explain
  their unavailable capability; they do not imply work happened.
- Feedback: persistent inline status for import/save/export, not a disappearing
  toast as the only record. A storage failure never produces “saved”.
- Return card: saved name, track count, timestamp and Resume. Resuming does not
  silently start playback or an export.
- Review/export: show the destination and excluded rows before writing. The
  prototype exports only explicitly labelled demo JSON.

## Accessibility and durable use

Native buttons and inputs, visible focus, labels, semantic tables/headings and
polite live status. Colour reinforces words. Keyboard controls are available
for reordering; dragging is not required. Maintain a readable narrow layout.
Respect reduced-motion settings. Changes to saved formats require a version and
a tested migration/fallback. Prototype localStorage has a separate demo key and
is never used as the production persistence implementation.

## Review criteria

Check first use, repeat use, empty search, unavailable audio, an empty set,
unsaved changes, failed save and export cancellation. Visual review does not
substitute for the observed user protocol in the brief. A complete design-system
rollout requires component documentation, integration tests and ownership.
