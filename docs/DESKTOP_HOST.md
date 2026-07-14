# DanceLab Pro Desktop

DanceLab Pro is a Python/PySide6 desktop application with one guided Simple
Mode workflow. It is backed directly by the engine and does not expose the
former visual graph editor or prototype HTML shell.

## Install

```bash
pip install .[desktop]
```

## Run

```bash
dancelab-host
```

## Build macOS App Bundle

Install the desktop build tooling:

```bash
pip install .[desktop-build]
```

Run the packaged bundle build:

```bash
dancelab-host-build
```

Preview the generated Nuitka command without compiling:

```bash
dancelab-host-build --dry-run
```

`--dry-run` only previews the packaging command. It does not run the macOS
codesign/xattr preflight, so you can inspect the bundle command even from a
blocked shell.

## Implemented in the Qt app

- Guided import, Initial Check, set generation, transition review, and export
- Multi-folder audio import and suspicious-duration confirmation
- Cached analysis library with set constraints
- Mixability map, energy timeline, and A/B transition review
- Quick initial analysis plus optional Deep/Demucs analysis for selected set tracks
- DanceLab project save, open, autosave, and recovery
- Rekordbox XML playlist and hot-cue export
- Direct use of engine analysis, planning, decision, and export modules

`src/dancelab/host/runtime.py` and `src/dancelab/contracts/node_host.py` remain
headless compatibility adapters for external diagnostics. They are not a
second desktop mode.

## Known environment note

`src/dancelab/host/desktop_app.py` sets Qt plugin paths automatically from the
installed PySide6 package. The Qt test suite skips live window tests when the
current shell cannot create a `QApplication`.

The engine/runtime adapters and the Simple Mode workflow are covered separately
by automated tests.

The packaging layer for macOS is handled through `pyside6-deploy` and
`pysidedeploy.spec`, with the desktop launcher rooted at
`scripts/dancelab_host_app.py`.

If the real bundle build stops early with a message about protected extended
attributes like `com.apple.provenance`, the preflight now reports two things:

- whether the known repo/build inputs still retain xattrs after cleanup
- whether a brand new temp probe file created by the current macOS session also
  keeps those attrs after cleanup

If that temp probe still keeps `com.apple.provenance`, the current session
itself is not capable of producing a signable `.app` bundle. In that case, run
the build from Apple's `Terminal.app`, make sure Terminal has Full Disk Access,
and verify a fresh temp file can be cleared before rerunning the build:

```bash
PROBE=$(mktemp /tmp/dancelab-host-probe.XXXXXX)
touch "$PROBE"
xattr "$PROBE"
xattr -d com.apple.provenance "$PROBE"
xattr "$PROBE"
```

If that shell probe is clean but `dancelab-host-build` still fails preflight,
the blocker is usually the Python interpreter behind the active virtualenv
rather than Terminal itself. In this repo, `.venv/bin/python` may resolve to a
uv-managed interpreter under `~/.local/share/uv/...`, and that interpreter can
still carry protected provenance attrs even when your shell-created temp files
do not.

In that case, create a fresh build virtualenv from a clean local Python
installation and reinstall the desktop build extras before bundling.

If the repo/build inputs are clean but only the fresh probe file still shows
`com.apple.provenance`, the preflight now emits a warning and continues into
the real bundle build. That lets `codesign` validate the actual generated app
outputs instead of stopping early on a heuristic-only signal.

The preflight is also intentionally softer for non-runtime repo files such as
`pysidedeploy.spec`. Those files can still report stubborn xattrs on some macOS
setups without preventing a usable final app bundle. The only hard preflight
blockers now are the active builder-interpreter binaries themselves.

On newer macOS builds, `pyside6-deploy`/Nuitka can still fail during its own
deep per-file `codesign` pass even though the final `.app` bundle has already
been materialized in `dist/desktop`. The host bundler now attempts a fallback
recovery step in that case:

- copy the generated `.app` with `ditto --noextattr --noqtn`
- remove root bundle metadata like `com.apple.FinderInfo`
- re-run ad-hoc `codesign` on the copied bundle
- verify it with `codesign --verify --deep --strict`

If that salvage pass succeeds, `dancelab-host-build` exits successfully and
keeps the recovered app at `dist/desktop/DanceLab Host.app`.
